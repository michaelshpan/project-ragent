"""Agent call functions for Investment Committee Agent Framework."""

import os
import re
import time
import asyncio
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
import anthropic
import openai
from dotenv import load_dotenv

from models import get_model_config

load_dotenv()


@dataclass
class AgentResult:
    """Structured agent response with full trace metadata.

    Used by demo-mode visualization to surface prompts, thinking traces, and
    timing alongside the final text. Clean-mode callers just read ``.text``.
    """

    text: str
    thinking: Optional[str] = None
    system_prompt: str = ""
    user_prompt: str = ""
    model_id: str = ""
    display_name: str = ""
    duration_ms: int = 0


class RateLimiter:
    """Rate limiter to prevent hitting API rate limits."""

    def __init__(self, delay: float = 1.0):
        self.delay = delay  # Delay in seconds between calls to same provider
        self.last_call: Dict[str, datetime] = {}

    async def wait_if_needed(self, provider: str):
        """Wait if needed to avoid rate limits for a specific provider."""
        if provider in self.last_call:
            elapsed = (datetime.now() - self.last_call[provider]).total_seconds()
            if elapsed < self.delay:
                await asyncio.sleep(self.delay - elapsed)

        self.last_call[provider] = datetime.now()


# Global rate limiter instance
rate_limiter = RateLimiter()


_THINK_TAG_PATTERNS = [
    r'<think>(.*?)</think>',
    r'<reasoning>(.*?)</reasoning>',
    r'<thought>(.*?)</thought>',
    r'<thinking>(.*?)</thinking>',
]


def extract_thinking_block(text: str) -> Tuple[str, Optional[str]]:
    """Split a thinking-model response into (cleaned_text, thinking).

    Concatenates content from any of the supported tag families into a single
    thinking trace, then strips all such blocks from the visible text.
    """
    thinking_parts: list[str] = []
    cleaned = text
    for pattern in _THINK_TAG_PATTERNS:
        for match in re.finditer(pattern, cleaned, flags=re.DOTALL):
            thinking_parts.append(match.group(1).strip())
        cleaned = re.sub(pattern, '', cleaned, flags=re.DOTALL)
    thinking = "\n\n".join(p for p in thinking_parts if p) or None
    return cleaned.strip(), thinking


def clean_thinking_tokens(text: str) -> str:
    """Remove thinking/reasoning tokens from model output (legacy helper)."""
    cleaned, _ = extract_thinking_block(text)
    return cleaned


async def call_anthropic_agent(
    model_id: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 2000,
    enable_thinking: bool = False,
) -> Tuple[str, Optional[str]]:
    """Call an Anthropic model. Returns (text, thinking_trace_or_None)."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")

    # Rate limiting for Anthropic
    await rate_limiter.wait_if_needed("anthropic")

    # Use asyncio.to_thread for sync SDK
    def call_sync():
        client = anthropic.Anthropic(api_key=api_key)
        kwargs: Dict[str, Any] = {
            "model": model_id,
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        if enable_thinking:
            # Opus 4.7 / Sonnet 4.6 require adaptive thinking; legacy
            # {"type": "enabled", "budget_tokens": N} is rejected (400).
            # display: "summarized" is the only way to surface thinking — full
            # chain-of-thought is encrypted and unrecoverable.
            # Effort tuning: Opus 4.7 needs "max" to *force* thinking on
            # short synthesis tasks (at "high" it often skips thinking and
            # returns an empty summary). Sonnet 4.6 doesn't accept "max" /
            # "xhigh" — they're Opus-only — so cap at "high" for it.
            effort = "max" if "opus" in model_id.lower() else "high"
            kwargs["thinking"] = {"type": "adaptive", "display": "summarized"}
            kwargs["output_config"] = {"effort": effort}
            # Adaptive mode shares max_tokens between thinking + text — give
            # it room above the ~200-word answer target.
            kwargs["max_tokens"] = max(max_tokens, 8000)
        response = client.messages.create(**kwargs)

        text_parts: list[str] = []
        thinking_parts: list[str] = []
        for block in response.content:
            block_type = getattr(block, "type", None)
            if block_type == "thinking":
                thinking_parts.append(getattr(block, "thinking", "") or "")
            elif block_type == "text":
                text_parts.append(getattr(block, "text", "") or "")
            elif hasattr(block, "text"):
                text_parts.append(block.text)
        text = "".join(text_parts)
        thinking = "\n\n".join(p for p in thinking_parts if p) or None
        return text, thinking

    return await asyncio.to_thread(call_sync)


async def call_openai_compat_agent(
    model_id: str,
    base_url: str,
    system_prompt: str,
    user_prompt: str,
    api_key_env: str,
    max_tokens: int = 2000,
    extra_params: Optional[Dict[str, Any]] = None,
) -> Tuple[str, Optional[str]]:
    """Call an OpenAI-compatible model. Returns (raw_text, reasoning_content_or_None).

    The raw_text may include inline ``<think>`` blocks for some providers; the
    caller is responsible for stripping them via :func:`extract_thinking_block`.
    """
    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise ValueError(f"{api_key_env} not set")

    # Rate limiting per provider
    provider = base_url.split("//")[1].split("/")[0]  # Extract domain
    await rate_limiter.wait_if_needed(provider)

    # Use asyncio.to_thread for sync SDK
    def call_sync():
        client = openai.OpenAI(api_key=api_key, base_url=base_url)

        # Build kwargs for the API call
        kwargs = {
            "model": model_id,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        }

        # Add extra_body for models like Qwen that need it
        if extra_params:
            kwargs["extra_body"] = extra_params

        response = client.chat.completions.create(**kwargs)
        msg = response.choices[0].message
        content = msg.content or ""
        reasoning = getattr(msg, "reasoning_content", None)
        # Some thinking models leave content empty when reasoning consumed the
        # token budget — fall back to reasoning_content as the visible answer.
        if not content.strip() and reasoning:
            return reasoning, None
        return content, reasoning

    return await asyncio.to_thread(call_sync)


async def call_agent_traced(
    model_key: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 2000,
    timeout: int = 120,
    enable_anthropic_thinking: bool = False,
) -> AgentResult:
    """Call a model and return a fully-traced :class:`AgentResult`.

    For Anthropic models, ``enable_anthropic_thinking`` toggles extended
    thinking (extra token cost) — wired to demo mode only. For thinking
    OpenAI-compat models (Grok/Kimi), the ``<think>`` block is always
    captured into ``thinking`` instead of being silently stripped.
    """
    config = get_model_config(model_key)
    effective_max_tokens = config.get("max_tokens", max_tokens)
    started = time.monotonic()

    try:
        async def _call():
            if config["provider"] == "anthropic":
                return await call_anthropic_agent(
                    model_id=config["model_id"],
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    max_tokens=max_tokens,
                    enable_thinking=enable_anthropic_thinking,
                )
            return await call_openai_compat_agent(
                model_id=config["model_id"],
                base_url=config["base_url"],
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                api_key_env=config["api_key_env"],
                max_tokens=effective_max_tokens,
                extra_params=config.get("extra_params"),
            )

        raw_text, raw_reasoning = await asyncio.wait_for(_call(), timeout=timeout)

        if config["provider"] == "anthropic":
            text = raw_text
            thinking = raw_reasoning
        elif config.get("is_thinking_model"):
            text, inline_thinking = extract_thinking_block(raw_text)
            thinking = inline_thinking or raw_reasoning
        else:
            text = raw_text
            thinking = raw_reasoning

        word_count = len(text.split())
        if word_count > 250:
            print(f"  ⚠️  Warning: {model_key} response has {word_count} words (target: 200)")

        return AgentResult(
            text=text,
            thinking=thinking,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model_id=config["model_id"],
            display_name=config.get("display_name", config["model_id"]),
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    except asyncio.TimeoutError:
        print(f"  ❌ Timeout: {model_key} took longer than {timeout} seconds")
        raise
    except Exception as e:
        print(f"  ❌ Error calling {model_key}: {e}")
        raise


async def call_agent(
    model_key: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 2000,
    timeout: int = 120,
) -> str:
    """Backward-compatible wrapper returning only the visible response text."""
    result = await call_agent_traced(
        model_key=model_key,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=max_tokens,
        timeout=timeout,
    )
    return result.text


async def call_research_agents_parallel(
    quant_data: Dict[str, Any],
    sentiment_data: Dict[str, Any],
    technical_data: Dict[str, Any],
    quant_prompt: str,
    sentiment_prompt: str,
    technical_prompt: str
) -> tuple[str, str, str]:
    """
    Call all three research agents in parallel.

    Returns:
        Tuple of (quant_report, sentiment_report, technical_report)
    """
    from models import get_model_for_role

    # Get model keys for each role
    quant_model = get_model_for_role("quant_researcher")
    sentiment_model = get_model_for_role("sentiment_researcher")
    technical_model = get_model_for_role("technical_researcher")

    # Format data as user prompts (curated role-specific summaries)
    quant_user = f"Data for analysis:\n{format_data_for_prompt(quant_data, role='quant')}"
    sentiment_user = f"Data for analysis:\n{format_data_for_prompt(sentiment_data, role='sentiment')}"
    technical_user = f"Data for analysis:\n{format_data_for_prompt(technical_data, role='technical')}"

    # Call all three agents in parallel
    results = await asyncio.gather(
        call_agent(quant_model, quant_prompt, quant_user),
        call_agent(sentiment_model, sentiment_prompt, sentiment_user),
        call_agent(technical_model, technical_prompt, technical_user),
        return_exceptions=True
    )

    # Handle errors gracefully
    reports = []
    names = ["Quantitative Valuation", "Sentiment", "Technical Signals"]

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"  ⚠️  {names[i]} Researcher failed: {result}")
            reports.append(f"## {names[i]} Report: ERROR\n\nThis research agent encountered an error and could not complete analysis.\n\n**Opinion: Neutral**")
        else:
            reports.append(result)

    return tuple(reports)


def format_data_for_prompt(data: Dict[str, Any], role: str = "generic") -> str:
    """Format data dictionary into a curated text summary for agent prompt.

    Uses the curation layer for role-specific summaries (much smaller than raw JSON).
    Falls back to JSON for unknown roles.
    """
    from curation import curate_quant_summary, curate_sentiment_summary, curate_technical_summary

    match role:
        case "quant":
            return curate_quant_summary(data)
        case "sentiment":
            return curate_sentiment_summary(data)
        case "technical":
            return curate_technical_summary(data)
        case _:
            import json
            return json.dumps(data, indent=2, default=str)
