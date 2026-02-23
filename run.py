#!/usr/bin/env python3
"""
Investment Committee Agent Framework
Main CLI entry point and pipeline orchestrator.
"""

import os
import sys
import argparse
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from fastmcp import Client

# Load environment variables
load_dotenv()

# Import all modules
from data import fetch_quant_data, fetch_sentiment_data, fetch_technical_data, source_logger
from models import check_all_models_available, get_model_for_role
from agents import call_agent, call_research_agents_parallel
from prompts import (
    build_quant_researcher_prompt,
    build_sentiment_researcher_prompt,
    build_technical_researcher_prompt,
    build_portfolio_manager_stage2_prompt,
    build_devil_advocate_prompt,
    build_portfolio_manager_final_prompt,
    combine_research_reports,
    format_da_research_data
)
from report import ReportBuilder, save_report, save_research_report, save_data_archive, print_stage_progress


def validate_environment() -> bool:
    """Validate that all required environment variables are set."""
    required_keys = [
        "ANTHROPIC_API_KEY",
        "XAI_API_KEY", 
        "ZAI_API_KEY",
        "MOONSHOT_API_KEY",
        "FMP_API_KEY",
        "FRED_API_KEY",
        "SCRAPINGDOG_API_KEY"
    ]
    
    missing = []
    for key in required_keys:
        if not os.environ.get(key):
            missing.append(key)
    
    if missing:
        print("❌ Missing required environment variables:")
        for key in missing:
            print(f"   - {key}")
        print("\nPlease set these in your .env file (see .env.example for template)")
        return False
    
    # Check model availability
    all_available, missing_models = check_all_models_available()
    if not all_available:
        print("❌ Some required models are not available:")
        for model_info in missing_models:
            print(f"   - {model_info['display_name']}: {model_info['env_var']} not set")
        return False
    
    return True


async def run_pipeline(ticker: str, output_dir: str = "./reports", verbose: bool = True) -> Optional[Path]:
    """
    Run the complete investment committee pipeline.
    
    Args:
        ticker: Stock ticker symbol
        output_dir: Directory to save report
        verbose: Print progress messages
    
    Returns:
        Path to the saved report file
    """
    start_time = datetime.now()
    report_builder = ReportBuilder(ticker)
    
    try:
        # Phase 0: Fetch all data concurrently via MCP + REST
        if verbose:
            print(f"[00:00] Starting Investment Committee analysis for {ticker}...")
            print("[00:01] Connecting to FMP MCP server & fetching market data...")

        fmp_api_key = os.environ.get("FMP_API_KEY")
        if not fmp_api_key:
            raise ValueError("FMP_API_KEY not set")

        fmp_url = f"https://financialmodelingprep.com/mcp?apikey={fmp_api_key}"

        async with Client(fmp_url) as fmp_client:
            quant_data, sentiment_data, technical_data = await asyncio.gather(
                fetch_quant_data(ticker, fmp_client=fmp_client),
                fetch_sentiment_data(ticker, fmp_client=fmp_client),
                fetch_technical_data(ticker, fmp_client=fmp_client),
                return_exceptions=True
            )
        # MCP client closes here — rest of pipeline uses cached data

        # Check for data fetch errors
        if isinstance(quant_data, Exception):
            print(f"❌ Error fetching quantitative data: {quant_data}")
            raise quant_data
        if isinstance(sentiment_data, Exception):
            print(f"❌ Error fetching sentiment data: {sentiment_data}")
            raise sentiment_data
        if isinstance(technical_data, Exception):
            print(f"❌ Error fetching technical data: {technical_data}")
            raise technical_data

        if verbose:
            print_stage_progress(start_time, "Data fetched successfully ✓")

        # Archive raw data for auditability
        research_dir = Path(output_dir) / "agent-research"
        archive_path = save_data_archive(ticker, quant_data, sentiment_data, technical_data, str(research_dir))
        if verbose:
            print_stage_progress(start_time, f"Data archive saved: {archive_path}", indent=1)

        # Phase 1: Run 3 research agents in parallel
        if verbose:
            print_stage_progress(start_time, "Stage 1: Running parallel research agents...")
        
        # Build prompts for research agents
        quant_prompt = build_quant_researcher_prompt(ticker)
        sentiment_prompt = build_sentiment_researcher_prompt(ticker)
        technical_prompt = build_technical_researcher_prompt(ticker)
        
        # Track individual agent timing
        agent_start = datetime.now()
        
        # Run agents in parallel
        quant_report, sentiment_report, technical_report = await call_research_agents_parallel(
            quant_data, sentiment_data, technical_data,
            quant_prompt, sentiment_prompt, technical_prompt
        )
        
        agent_duration = (datetime.now() - agent_start).total_seconds()
        
        if verbose:
            print_stage_progress(start_time, f"→ Quantitative Valuation Researcher... ✓ ({agent_duration:.1f}s)", indent=1)
            print_stage_progress(start_time, f"→ Sentiment Researcher... ✓ ({agent_duration:.1f}s)", indent=1)
            print_stage_progress(start_time, f"→ Technical Signals Researcher... ✓ ({agent_duration:.1f}s)", indent=1)
        
        # Save individual research reports to agent-research folder
        quant_path = save_research_report(ticker, "quant", quant_report, str(research_dir))
        sentiment_path = save_research_report(ticker, "sentiment", sentiment_report, str(research_dir))
        technical_path = save_research_report(ticker, "technical", technical_report, str(research_dir))
        
        if verbose:
            print_stage_progress(start_time, f"Research reports saved to {research_dir}/", indent=1)
        
        # Save research reports to main report builder
        report_builder.add_stage("research", {
            "quant": quant_report,
            "sentiment": sentiment_report,
            "technical": technical_report
        })
        
        # Phase 2: Portfolio Manager decision (sequential)
        if verbose:
            print_stage_progress(start_time, "Stage 2: Portfolio Manager decision...")
        
        combined_reports = combine_research_reports(quant_report, sentiment_report, technical_report)
        pm_system, pm_user = build_portfolio_manager_stage2_prompt(ticker, combined_reports)
        
        pm_model = get_model_for_role("portfolio_manager")
        pm_decision = await call_agent(pm_model, pm_system, pm_user)
        
        # Save Stage 2 decision to agent-research folder
        pm_stage2_path = save_research_report(ticker, "portfolio_manager_stage2", pm_decision, str(research_dir))
        
        report_builder.add_stage("stage2", pm_decision)
        
        if verbose:
            print_stage_progress(start_time, "Portfolio Manager decision complete ✓", indent=1)
        
        # Phase 3: Devil's Advocate (sequential)
        if verbose:
            print_stage_progress(start_time, "Stage 3: Devil's Advocate challenge...")
        
        # Format data for Devil's Advocate
        da_data = format_da_research_data(quant_data, sentiment_data, technical_data)
        da_system, da_user = build_devil_advocate_prompt(ticker, pm_decision, da_data)
        
        da_model = get_model_for_role("devil_advocate")
        da_report = await call_agent(da_model, da_system, da_user)
        
        # Save Devil's Advocate report to agent-research folder
        da_path = save_research_report(ticker, "devil_advocate", da_report, str(research_dir))
        
        report_builder.add_stage("devil_advocate", da_report)
        
        if verbose:
            print_stage_progress(start_time, "Devil's Advocate complete ✓", indent=1)
        
        # Phase 4: Final decision (sequential)
        if verbose:
            print_stage_progress(start_time, "Stage 4: Final decision...")
        
        final_system, final_user = build_portfolio_manager_final_prompt(ticker, pm_decision, da_report)
        final_decision = await call_agent(pm_model, final_system, final_user)
        
        # Save Final Decision to agent-research folder
        final_path = save_research_report(ticker, "final_decision", final_decision, str(research_dir))
        
        report_builder.add_stage("final", final_decision)
        
        if verbose:
            print_stage_progress(start_time, "Final decision complete ✓", indent=1)
            print_stage_progress(start_time, f"All agent reports saved to {research_dir}/", indent=1)
        
        # Get source log and save report
        report_builder.set_source_log(source_logger.get_log())
        report_path = save_report(report_builder, output_dir)
        
        if verbose:
            total_duration = (datetime.now() - start_time).total_seconds()
            print_stage_progress(start_time, f"Report saved: {report_path}")
            print(f"\n✅ Analysis complete in {total_duration:.1f} seconds")
        
        return report_path
        
    except Exception as e:
        print(f"\n❌ Pipeline error: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Investment Committee Agent Framework - Generate Buy/Sell decisions for stocks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py AAPL                    # Analyze Apple stock
  python run.py TSLA --verbose          # Analyze Tesla with detailed output
  python run.py MSFT --output-dir ./out # Save report to custom directory
        """
    )
    
    parser.add_argument(
        "ticker",
        type=str,
        help="Stock ticker symbol to analyze (e.g., AAPL, TSLA, MSFT)"
    )
    
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./reports",
        help="Directory to save the report (default: ./reports)"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=True,
        help="Print detailed progress messages (default: True)"
    )
    
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress messages"
    )
    
    args = parser.parse_args()
    
    # Handle quiet flag
    if args.quiet:
        args.verbose = False
    
    # Validate environment first
    if not validate_environment():
        sys.exit(1)
    
    # Convert ticker to uppercase
    ticker = args.ticker.upper()
    
    # Run the pipeline
    try:
        report_path = asyncio.run(run_pipeline(
            ticker=ticker,
            output_dir=args.output_dir,
            verbose=args.verbose
        ))
        
        if report_path:
            print(f"\n📄 Report saved to: {report_path}")
            sys.exit(0)
        else:
            print("\n❌ Pipeline failed to complete")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Analysis interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()