"""Web pipeline wrapper — async generator that yields SSE event dicts."""

import os
import asyncio
from datetime import datetime
from typing import AsyncGenerator, Dict, Any

from dotenv import load_dotenv
from fastmcp import Client

from data import (
    SourceLogger,
    fetch_quant_data,
    fetch_sentiment_data,
    fetch_technical_data,
)
from agents import call_agent, call_research_agents_parallel, format_data_for_prompt
from models import get_model_for_role
from prompts import (
    build_quant_researcher_prompt,
    build_sentiment_researcher_prompt,
    build_technical_researcher_prompt,
    build_portfolio_manager_stage2_prompt,
    build_devil_advocate_prompt,
    build_portfolio_manager_final_prompt,
    combine_research_reports,
    format_da_research_data,
)
from report import ReportBuilder, save_report, save_research_report, save_data_archive
from curation import (
    curate_quant_summary,
    curate_sentiment_summary,
    curate_technical_summary,
)

load_dotenv()


async def run_pipeline_web(ticker: str) -> AsyncGenerator[Dict[str, Any], None]:
    """Run the investment committee pipeline, yielding SSE events.

    Each yielded dict has at minimum an ``event`` key.  The FastAPI layer
    serialises these as ``text/event-stream`` lines.
    """
    start = datetime.now()
    request_logger = SourceLogger()

    def _elapsed() -> float:
        return (datetime.now() - start).total_seconds()

    try:
        # ── Phase 0: Data fetch ──────────────────────────────────────────
        yield {
            "event": "status",
            "stage": "data_fetch",
            "message": "Collecting market data...",
        }

        fmp_api_key = os.environ.get("FMP_API_KEY")
        if not fmp_api_key:
            raise ValueError("FMP_API_KEY not set")

        fmp_url = f"https://financialmodelingprep.com/mcp?apikey={fmp_api_key}"

        async with Client(fmp_url) as fmp_client:
            quant_data, sentiment_data, technical_data = await asyncio.gather(
                fetch_quant_data(ticker, fmp_client=fmp_client, logger=request_logger),
                fetch_sentiment_data(ticker, fmp_client=fmp_client, logger=request_logger),
                fetch_technical_data(ticker, fmp_client=fmp_client, logger=request_logger),
                return_exceptions=True,
            )

        # Check for data-fetch errors
        for label, result in [
            ("quant", quant_data),
            ("sentiment", sentiment_data),
            ("technical", technical_data),
        ]:
            if isinstance(result, Exception):
                raise RuntimeError(f"{label} data fetch failed: {result}")

        # Build curated summaries for the frontend
        data_summaries = {
            "quant": curate_quant_summary(quant_data),
            "sentiment": curate_sentiment_summary(sentiment_data),
            "technical": curate_technical_summary(technical_data),
        }

        # Extract current price from quant data
        current_price = None
        if isinstance(quant_data, dict):
            quote = quant_data.get("quote")
            if isinstance(quote, dict):
                current_price = quote.get("price")

        yield {
            "event": "data_ready",
            "stage": "data_fetch",
            "elapsed": round(_elapsed(), 1),
            "summary": data_summaries,
            "current_price": current_price,
        }

        # Archive raw data
        research_dir = "./reports/agent-research"
        save_data_archive(ticker, quant_data, sentiment_data, technical_data, research_dir)

        # ── Phase 1: Parallel research agents ────────────────────────────
        yield {
            "event": "status",
            "stage": "research",
            "message": "Research agents analyzing...",
        }

        quant_prompt = build_quant_researcher_prompt(ticker)
        sentiment_prompt = build_sentiment_researcher_prompt(ticker)
        technical_prompt = build_technical_researcher_prompt(ticker)

        quant_report, sentiment_report, technical_report = (
            await call_research_agents_parallel(
                quant_data, sentiment_data, technical_data,
                quant_prompt, sentiment_prompt, technical_prompt,
            )
        )

        for agent_name, report in [
            ("quant", quant_report),
            ("sentiment", sentiment_report),
            ("technical", technical_report),
        ]:
            save_research_report(ticker, agent_name, report, research_dir)
            yield {
                "event": "agent_done",
                "stage": "research",
                "agent": agent_name,
                "report": report,
            }

        # ── Phase 2: Portfolio Manager decision ──────────────────────────
        yield {
            "event": "status",
            "stage": "pm_decision",
            "message": "Portfolio Manager deliberating...",
        }

        combined_reports = combine_research_reports(
            quant_report, sentiment_report, technical_report,
        )
        pm_system, pm_user = build_portfolio_manager_stage2_prompt(ticker, combined_reports)
        pm_model = get_model_for_role("portfolio_manager")
        pm_decision = await call_agent(pm_model, pm_system, pm_user)

        save_research_report(ticker, "portfolio_manager_stage2", pm_decision, research_dir)

        yield {
            "event": "stage_done",
            "stage": "pm_decision",
            "content": pm_decision,
        }

        # ── Phase 3: Devil's Advocate ────────────────────────────────────
        yield {
            "event": "status",
            "stage": "da_challenge",
            "message": "Devil's Advocate challenging...",
        }

        da_data = format_da_research_data(quant_data, sentiment_data, technical_data)
        da_system, da_user = build_devil_advocate_prompt(ticker, pm_decision, da_data)
        da_model = get_model_for_role("devil_advocate")
        da_report = await call_agent(da_model, da_system, da_user)

        save_research_report(ticker, "devil_advocate", da_report, research_dir)

        yield {
            "event": "stage_done",
            "stage": "da_challenge",
            "content": da_report,
        }

        # ── Phase 4: Final decision ──────────────────────────────────────
        yield {
            "event": "status",
            "stage": "final_decision",
            "message": "Portfolio Manager making final decision...",
        }

        final_system, final_user = build_portfolio_manager_final_prompt(
            ticker, pm_decision, da_report,
        )
        final_decision = await call_agent(pm_model, final_system, final_user)

        save_research_report(ticker, "final_decision", final_decision, research_dir)

        yield {
            "event": "stage_done",
            "stage": "final_decision",
            "content": final_decision,
        }

        # ── Save full report ─────────────────────────────────────────────
        report_builder = ReportBuilder(ticker)
        report_builder.add_stage("research", {
            "quant": quant_report,
            "sentiment": sentiment_report,
            "technical": technical_report,
        })
        report_builder.add_stage("stage2", pm_decision)
        report_builder.add_stage("devil_advocate", da_report)
        report_builder.add_stage("final", final_decision)
        report_builder.set_source_log(request_logger.get_log())
        save_report(report_builder)

        # ── Complete ─────────────────────────────────────────────────────
        yield {
            "event": "complete",
            "elapsed": round(_elapsed(), 1),
            "source_log": request_logger.get_log(),
            "all_reports": {
                "quant": quant_report,
                "sentiment": sentiment_report,
                "technical": technical_report,
                "pm_decision": pm_decision,
                "da_challenge": da_report,
                "final_decision": final_decision,
            },
            "data_summaries": data_summaries,
        }

    except Exception as exc:
        yield {
            "event": "error",
            "message": str(exc),
        }
