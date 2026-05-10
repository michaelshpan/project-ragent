"""Web pipeline wrapper — async generator that yields SSE event dicts."""

import os
import asyncio
from datetime import datetime
from typing import AsyncGenerator, Dict, Any, Optional

from dotenv import load_dotenv
from fastmcp import Client

from data import (
    SourceLogger,
    fetch_quant_data,
    fetch_sentiment_data,
    fetch_technical_data,
)
from agents import (
    AgentResult,
    call_agent_traced,
    format_data_for_prompt,
)
from models import get_model_config, get_model_for_role
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


def _debug_payload(result: AgentResult) -> Dict[str, Any]:
    """Build the demo-mode debug payload from a traced agent result."""
    return {
        "model_id": result.model_id,
        "display_name": result.display_name,
        "system_prompt": result.system_prompt,
        "user_prompt": result.user_prompt,
        "thinking": result.thinking,
        "duration_ms": result.duration_ms,
    }


def _pre_call_debug(model_key: str, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    """Build a pre-call debug payload (prompts only — no response yet)."""
    config = get_model_config(model_key)
    return {
        "model_id": config["model_id"],
        "display_name": config.get("display_name", config["model_id"]),
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
    }


async def run_pipeline_web(
    ticker: str,
    demo_mode: bool = False,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Run the investment committee pipeline, yielding SSE events.

    Each yielded dict has at minimum an ``event`` key.  The FastAPI layer
    serialises these as ``text/event-stream`` lines.

    When ``demo_mode`` is True, additional events and ``debug`` payloads are
    emitted: ``agent_started`` events fire pre-call with prompts, and
    ``agent_done`` / ``stage_done`` events carry full traces (model id,
    duration, thinking trace). Anthropic extended thinking is also enabled
    only in demo mode (it incurs extra token cost).
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

        quant_user = f"Data for analysis:\n{format_data_for_prompt(quant_data, role='quant')}"
        sentiment_user = f"Data for analysis:\n{format_data_for_prompt(sentiment_data, role='sentiment')}"
        technical_user = f"Data for analysis:\n{format_data_for_prompt(technical_data, role='technical')}"

        agent_specs = [
            ("quant", get_model_for_role("quant_researcher"), quant_prompt, quant_user, "Quantitative Valuation"),
            ("sentiment", get_model_for_role("sentiment_researcher"), sentiment_prompt, sentiment_user, "Sentiment"),
            ("technical", get_model_for_role("technical_researcher"), technical_prompt, technical_user, "Technical Signals"),
        ]

        if demo_mode:
            for agent_name, model_key, sys_prompt, user_prompt, _ in agent_specs:
                yield {
                    "event": "agent_started",
                    "stage": "research",
                    "agent": agent_name,
                    "debug": _pre_call_debug(model_key, sys_prompt, user_prompt),
                }

        async def _named(name: str, label: str, coro):
            try:
                return name, label, await coro
            except Exception as exc:
                return name, label, exc

        tasks = [
            asyncio.create_task(
                _named(
                    name,
                    label,
                    call_agent_traced(model_key, sys_prompt, user_prompt),
                )
            )
            for name, model_key, sys_prompt, user_prompt, label in agent_specs
        ]

        research_results: Dict[str, AgentResult] = {}
        research_reports: Dict[str, str] = {}

        for fut in asyncio.as_completed(tasks):
            name, label, outcome = await fut
            if isinstance(outcome, Exception):
                report_text = (
                    f"## {label} Report: ERROR\n\n"
                    "This research agent encountered an error and could not complete analysis.\n\n"
                    "**Opinion: Neutral**"
                )
                research_reports[name] = report_text
                save_research_report(ticker, name, report_text, research_dir)
                event: Dict[str, Any] = {
                    "event": "agent_done",
                    "stage": "research",
                    "agent": name,
                    "report": report_text,
                }
                if demo_mode:
                    event["debug"] = {"error": str(outcome)}
                yield event
            else:
                research_results[name] = outcome
                research_reports[name] = outcome.text
                save_research_report(ticker, name, outcome.text, research_dir)
                event = {
                    "event": "agent_done",
                    "stage": "research",
                    "agent": name,
                    "report": outcome.text,
                }
                if demo_mode:
                    event["debug"] = _debug_payload(outcome)
                yield event

        quant_report = research_reports["quant"]
        sentiment_report = research_reports["sentiment"]
        technical_report = research_reports["technical"]

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

        if demo_mode:
            yield {
                "event": "agent_started",
                "stage": "pm_decision",
                "debug": _pre_call_debug(pm_model, pm_system, pm_user),
            }

        pm_result = await call_agent_traced(
            pm_model, pm_system, pm_user,
            enable_anthropic_thinking=demo_mode,
        )
        pm_decision = pm_result.text

        save_research_report(ticker, "portfolio_manager_stage2", pm_decision, research_dir)

        pm_event: Dict[str, Any] = {
            "event": "stage_done",
            "stage": "pm_decision",
            "content": pm_decision,
        }
        if demo_mode:
            pm_event["debug"] = _debug_payload(pm_result)
        yield pm_event

        # ── Phase 3: Devil's Advocate ────────────────────────────────────
        yield {
            "event": "status",
            "stage": "da_challenge",
            "message": "Devil's Advocate challenging...",
        }

        da_data = format_da_research_data(quant_data, sentiment_data, technical_data)
        da_system, da_user = build_devil_advocate_prompt(ticker, pm_decision, da_data)
        da_model = get_model_for_role("devil_advocate")

        if demo_mode:
            yield {
                "event": "agent_started",
                "stage": "da_challenge",
                "debug": _pre_call_debug(da_model, da_system, da_user),
            }

        da_result = await call_agent_traced(
            da_model, da_system, da_user,
            enable_anthropic_thinking=demo_mode,
        )
        da_report = da_result.text

        save_research_report(ticker, "devil_advocate", da_report, research_dir)

        da_event: Dict[str, Any] = {
            "event": "stage_done",
            "stage": "da_challenge",
            "content": da_report,
        }
        if demo_mode:
            da_event["debug"] = _debug_payload(da_result)
        yield da_event

        # ── Phase 4: Final decision ──────────────────────────────────────
        yield {
            "event": "status",
            "stage": "final_decision",
            "message": "Portfolio Manager making final decision...",
        }

        final_system, final_user = build_portfolio_manager_final_prompt(
            ticker, pm_decision, da_report,
        )

        if demo_mode:
            yield {
                "event": "agent_started",
                "stage": "final_decision",
                "debug": _pre_call_debug(pm_model, final_system, final_user),
            }

        final_result = await call_agent_traced(
            pm_model, final_system, final_user,
            enable_anthropic_thinking=demo_mode,
        )
        final_decision = final_result.text

        save_research_report(ticker, "final_decision", final_decision, research_dir)

        final_event: Dict[str, Any] = {
            "event": "stage_done",
            "stage": "final_decision",
            "content": final_decision,
        }
        if demo_mode:
            final_event["debug"] = _debug_payload(final_result)
        yield final_event

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
        complete_event: Dict[str, Any] = {
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
        if demo_mode:
            complete_event["all_debug"] = {
                **{name: _debug_payload(r) for name, r in research_results.items()},
                "pm_decision": _debug_payload(pm_result),
                "da_challenge": _debug_payload(da_result),
                "final_decision": _debug_payload(final_result),
            }
        yield complete_event

    except Exception as exc:
        import traceback
        traceback.print_exc()
        yield {
            "event": "error",
            "message": f"{type(exc).__name__}: {exc}",
        }
