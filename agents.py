"""Agent call functions for Investment Committee Agent Framework."""

import os
import re
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import anthropic
import openai
from dotenv import load_dotenv

from models import get_model_config

load_dotenv()


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


def clean_thinking_tokens(text: str) -> str:
    """Remove thinking/reasoning tokens from model output."""
    # Remove <think>...</think> blocks
    cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    
    # Remove any other common thinking patterns
    cleaned = re.sub(r'<reasoning>.*?</reasoning>', '', cleaned, flags=re.DOTALL)
    cleaned = re.sub(r'<thought>.*?</thought>', '', cleaned, flags=re.DOTALL)
    
    # For Qwen models, the thinking might be returned separately via reasoning_content
    # but we'll handle it here just in case it's embedded
    cleaned = re.sub(r'<thinking>.*?</thinking>', '', cleaned, flags=re.DOTALL)
    
    return cleaned.strip()


async def call_anthropic_agent(
    model_id: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 2000
) -> str:
    """Call an Anthropic model."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")
    
    # Rate limiting for Anthropic
    await rate_limiter.wait_if_needed("anthropic")
    
    # Use asyncio.to_thread for sync SDK
    def call_sync():
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model_id,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        return response.content[0].text
    
    return await asyncio.to_thread(call_sync)


async def call_openai_compat_agent(
    model_id: str,
    base_url: str,
    system_prompt: str,
    user_prompt: str,
    api_key_env: str,
    max_tokens: int = 2000,
    extra_params: Optional[Dict[str, Any]] = None
) -> str:
    """Call an OpenAI-compatible model."""
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
        # Thinking models (e.g. Kimi K2.5) may put the answer in content
        # but leave it empty if reasoning_content consumed the token budget.
        # Fall back to reasoning_content so we don't return a blank report.
        if not content.strip():
            reasoning = getattr(msg, "reasoning_content", None)
            if reasoning:
                content = reasoning
        return content

    return await asyncio.to_thread(call_sync)


async def call_agent(
    model_key: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 2000,
    timeout: int = 120
) -> str:
    """
    Unified interface to call any agent model.
    
    Args:
        model_key: Key from the model registry
        system_prompt: System prompt for the agent
        user_prompt: User prompt/data for the agent
        max_tokens: Maximum tokens to generate
        timeout: Timeout in seconds (default 120)
    
    Returns:
        Agent response text (cleaned of thinking tokens if applicable)
    """
    config = get_model_config(model_key)

    # Use model-specific max_tokens for thinking models (reasoning tokens
    # count toward the budget, so they need a larger allowance).
    effective_max_tokens = config.get("max_tokens", max_tokens)

    try:
        # Set timeout for the call
        async def _call():
            if config["provider"] == "anthropic":
                return await call_anthropic_agent(
                    model_id=config["model_id"],
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    max_tokens=max_tokens
                )
            else:  # openai_compat
                return await call_openai_compat_agent(
                    model_id=config["model_id"],
                    base_url=config["base_url"],
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    api_key_env=config["api_key_env"],
                    max_tokens=effective_max_tokens,
                    extra_params=config.get("extra_params")
                )

        response = await asyncio.wait_for(_call(), timeout=timeout)

        # Clean thinking tokens for thinking models
        if config.get("is_thinking_model"):
            response = clean_thinking_tokens(response)
        
        # Word count check
        word_count = len(response.split())
        if word_count > 250:
            print(f"  ⚠️  Warning: {model_key} response has {word_count} words (target: 200)")
        
        return response
        
    except asyncio.TimeoutError:
        print(f"  ❌ Timeout: {model_key} took longer than {timeout} seconds")
        raise
    except Exception as e:
        print(f"  ❌ Error calling {model_key}: {e}")
        raise


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