"""Data fetching module for Investment Committee Agent Framework.

FMP data is fetched via MCP (Model Context Protocol) using the fastmcp Client.
FRED and Scraping Dog data remain as REST calls via aiohttp.
"""

import os
import asyncio
import json as json_module
from typing import Dict, List, Any
from datetime import datetime, timedelta
import aiohttp
from dotenv import load_dotenv
from fastmcp import Client

load_dotenv()


class SourceLogger:
    """Track all external API calls and search results."""

    def __init__(self):
        self.sources: List[Dict[str, str]] = []

    def log(self, source: str, data_type: str, url: str):
        """Log a data source access."""
        self.sources.append({
            "source": source,
            "type": data_type,
            "url": url,
            "timestamp": datetime.now().isoformat()
        })

    def get_log(self) -> List[Dict[str, str]]:
        """Return the accumulated source log."""
        return self.sources


source_logger = SourceLogger()


# ── MCP helpers ───────────────────────────────────────────────────────────────


async def _mcp_call(client: Client, tool_name: str, args: dict) -> dict | list:
    """Call MCP tool, extract data from CallToolResult."""
    result = await client.call_tool(tool_name, args)
    # Try structured_content first
    if hasattr(result, "structured_content") and result.structured_content:
        return result.structured_content.get("data", result.structured_content)
    # Fall back to text content blocks
    for block in (result.content or []):
        if hasattr(block, "text"):
            return json_module.loads(block.text)
    return {}


async def _safe_mcp(client: Client, tool: str, args: dict, default=None, logger: "SourceLogger | None" = None) -> dict | list:
    """MCP call with graceful failure + source logging."""
    _logger = logger or source_logger
    try:
        data = await _mcp_call(client, tool, args)
        _logger.log("FMP-MCP", tool, f"mcp://{tool}?{args}")
        return data
    except Exception as e:
        print(f"  Warning: MCP {tool} failed: {e}")
        return default if default is not None else {}


# ── REST helpers (FRED, Scraping Dog) ─────────────────────────────────────────


async def fetch_with_retry(session: aiohttp.ClientSession, url: str, params: Dict = None, max_retries: int = 3) -> Dict:
    """Fetch URL with retry logic for rate limits and errors."""
    headers = {"Accept-Encoding": "gzip, deflate"}
    for attempt in range(max_retries):
        try:
            async with session.get(url, params=params, headers=headers) as response:
                if response.status == 429:
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
                    continue
                response.raise_for_status()
                return await response.json(content_type=None)
        except aiohttp.ClientError as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(1)
    return {}


# ── Manual indicator calculations (fallbacks) ────────────────────────────────


def _calculate_rsi(closes: List[float], period: int = 14) -> float | None:
    """Calculate RSI from closing prices (most recent first)."""
    if len(closes) < period + 1:
        return None

    prices = list(reversed(closes[:period + 50]))

    gains = []
    losses = []
    for i in range(1, len(prices)):
        change = prices[i] - prices[i - 1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))

    if len(gains) < period:
        return None

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def _calculate_sma(closes: List[float], period: int) -> float | None:
    """Calculate Simple Moving Average from closing prices (most recent first)."""
    if len(closes) < period:
        return None
    return round(sum(closes[:period]) / period, 2)


def _calculate_price_changes(closes: List[float], quote: Any) -> Dict[str, float]:
    """Calculate price change percentages over various periods."""
    changes = {}

    if isinstance(quote, dict) and quote.get("changePercentage") is not None:
        changes["1D"] = round(quote["changePercentage"], 2)

    current = closes[0] if closes else None
    if current:
        periods = {"5D": 5, "1M": 21, "3M": 63, "6M": 126, "1Y": 252}
        for label, days in periods.items():
            if len(closes) > days:
                past = closes[days]
                if past and past != 0:
                    changes[label] = round(((current - past) / past) * 100, 2)

    return changes


def _calculate_support_resistance(historical: List[Dict]) -> Dict[str, Any]:
    """Identify support and resistance levels from recent price action."""
    if not historical:
        return {"support": None, "resistance": None}

    highs = [d["high"] for d in historical if isinstance(d, dict) and "high" in d]
    lows = [d["low"] for d in historical if isinstance(d, dict) and "low" in d]

    if not highs or not lows:
        return {"support": None, "resistance": None}

    resistance_90d = max(highs)
    support_90d = min(lows)
    resistance_30d = max(highs[:min(30, len(highs))])
    support_30d = min(lows[:min(30, len(lows))])

    return {
        "resistance_90d": round(resistance_90d, 2),
        "support_90d": round(support_90d, 2),
        "resistance_30d": round(resistance_30d, 2),
        "support_30d": round(support_30d, 2),
    }


# ── Fetch functions ───────────────────────────────────────────────────────────


async def fetch_quant_data(ticker: str, fmp_client: Client | None = None, logger: "SourceLogger | None" = None) -> Dict[str, Any]:
    """Fetch quantitative data from FMP (MCP) and FRED (REST)."""
    _logger = logger or source_logger
    fred_key = os.environ.get("FRED_API_KEY")
    if not fred_key:
        raise ValueError("FRED_API_KEY not set")

    if fmp_client is None:
        raise ValueError("fmp_client is required — MCP client must be provided")

    today = datetime.now().strftime("%Y-%m-%d")
    from_date = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d")

    # ── MCP calls (all FMP data) ──────────────────────────────────────────
    (
        quote, income, balance_sheet, cash_flow,
        ratios, key_metrics, enterprise_values, growth,
        profile, analyst_estimates, price_targets,
        dcf, advanced_dcf, financial_scores,
        ttm_income, ttm_metrics,
        sector_pe, industry_pe, rev_seg,
    ) = await asyncio.gather(
        _safe_mcp(fmp_client, "quote", {"symbol": ticker}, logger=_logger),
        _safe_mcp(fmp_client, "income-statement", {"symbol": ticker, "period": "annual", "limit": 5}, default=[], logger=_logger),
        _safe_mcp(fmp_client, "balance-sheet-statement", {"symbol": ticker, "period": "annual"}, default=[], logger=_logger),
        _safe_mcp(fmp_client, "cashflow-statement", {"symbol": ticker, "period": "annual"}, default=[], logger=_logger),
        _safe_mcp(fmp_client, "metrics-ratios", {"symbol": ticker, "period": "annual"}, default=[], logger=_logger),
        _safe_mcp(fmp_client, "key-metrics", {"symbol": ticker, "period": "annual"}, default=[], logger=_logger),
        _safe_mcp(fmp_client, "enterprise-values", {"symbol": ticker, "period": "annual"}, default=[], logger=_logger),
        _safe_mcp(fmp_client, "financial-statement-growth", {"symbol": ticker}, default=[], logger=_logger),
        _safe_mcp(fmp_client, "profile-symbol", {"symbol": ticker}, logger=_logger),
        _safe_mcp(fmp_client, "financial-estimates", {"symbol": ticker, "period": "annual"}, default=[], logger=_logger),
        _safe_mcp(fmp_client, "price-target-summary", {"symbol": ticker}, logger=_logger),
        _safe_mcp(fmp_client, "dcf-advanced", {"symbol": ticker}, logger=_logger),
        _safe_mcp(fmp_client, "dcf-levered", {"symbol": ticker}, logger=_logger),
        _safe_mcp(fmp_client, "financial-scores", {"symbol": ticker}, logger=_logger),
        _safe_mcp(fmp_client, "income-statements-ttm", {"symbol": ticker}, default=[], logger=_logger),
        _safe_mcp(fmp_client, "key-metrics-ttm", {"symbol": ticker}, logger=_logger),
        _safe_mcp(fmp_client, "sector-PE-snapshot", {"date": today}, logger=_logger),
        _safe_mcp(fmp_client, "industry-PE-snapshot", {"date": today}, logger=_logger),
        _safe_mcp(fmp_client, "revenue-product-segmentation", {"symbol": ticker}, logger=_logger),
    )

    # Normalize list-wrapped single results
    quote = quote[0] if isinstance(quote, list) and quote else quote
    profile = profile[0] if isinstance(profile, list) and profile else profile

    # ── FRED REST calls (unchanged) ───────────────────────────────────────
    async with aiohttp.ClientSession() as session:
        fred_base = "https://api.stlouisfed.org/fred"
        fred_params = {
            "api_key": fred_key,
            "file_type": "json",
            "limit": 1,
            "sort_order": "desc"
        }

        fed_funds, yield_spread, vix = await asyncio.gather(
            fetch_with_retry(session, f"{fred_base}/series/observations",
                             {**fred_params, "series_id": "DFF"}),
            fetch_with_retry(session, f"{fred_base}/series/observations",
                             {**fred_params, "series_id": "T10Y2Y"}),
            fetch_with_retry(session, f"{fred_base}/series/observations",
                             {**fred_params, "series_id": "VIXCLS"}),
            return_exceptions=True,
        )

        _logger.log("FRED", "Fed Funds Rate", f"{fred_base}/series/observations?series_id=DFF")
        _logger.log("FRED", "Yield Spread", f"{fred_base}/series/observations?series_id=T10Y2Y")
        _logger.log("FRED", "VIX", f"{fred_base}/series/observations?series_id=VIXCLS")

    def _fred_val(resp) -> float:
        if isinstance(resp, Exception):
            return 0
        try:
            return float(resp.get("observations", [{}])[0].get("value", 0))
        except (IndexError, TypeError, ValueError):
            return 0

    return {
        "ticker": ticker,

        # Core financial data
        "quote": quote if not isinstance(quote, Exception) else {},
        "income_statements": income if not isinstance(income, Exception) else [],
        "balance_sheet": balance_sheet if not isinstance(balance_sheet, Exception) else [],
        "cash_flow": cash_flow if not isinstance(cash_flow, Exception) else [],

        # Valuation and ratios
        "ratios": ratios if not isinstance(ratios, Exception) else [],
        "key_metrics": key_metrics if not isinstance(key_metrics, Exception) else [],
        "enterprise_values": enterprise_values if not isinstance(enterprise_values, Exception) else [],
        "growth": growth if not isinstance(growth, Exception) else [],

        # Company and analyst data
        "profile": profile if not isinstance(profile, Exception) else {},
        "analyst_estimates": analyst_estimates if not isinstance(analyst_estimates, Exception) else {},
        "price_targets": price_targets if not isinstance(price_targets, Exception) else {},

        # Valuation models
        "dcf_valuation": dcf if not isinstance(dcf, Exception) else {},
        "advanced_dcf": advanced_dcf if not isinstance(advanced_dcf, Exception) else {},

        # Financial health scores
        "financial_scores": financial_scores if not isinstance(financial_scores, Exception) else {},

        # TTM data
        "ttm_income": ttm_income if not isinstance(ttm_income, Exception) else [],
        "ttm_metrics": ttm_metrics if not isinstance(ttm_metrics, Exception) else {},

        # Derived data for backward compatibility
        "price_changes": growth[0] if isinstance(growth, list) and growth else {},

        # New enriched data sources (MCP)
        "sector_pe": sector_pe if not isinstance(sector_pe, Exception) else {},
        "industry_pe": industry_pe if not isinstance(industry_pe, Exception) else {},
        "revenue_product_segmentation": rev_seg if not isinstance(rev_seg, Exception) else {},

        # Macro economic data (FRED)
        "macro": {
            "fed_funds_rate": _fred_val(fed_funds),
            "yield_spread": _fred_val(yield_spread),
            "vix": _fred_val(vix),
        }
    }


async def fetch_sentiment_data(ticker: str, fmp_client: Client | None = None, logger: "SourceLogger | None" = None) -> Dict[str, Any]:
    """Fetch sentiment data from FMP (MCP) and Scraping Dog (REST)."""
    _logger = logger or source_logger
    scraping_key = os.environ.get("SCRAPINGDOG_API_KEY")
    if not scraping_key:
        raise ValueError("SCRAPINGDOG_API_KEY not set")

    if fmp_client is None:
        raise ValueError("fmp_client is required — MCP client must be provided")

    # ── MCP calls (FMP sentiment data) ────────────────────────────────────
    (
        profile, stock_news, press_releases,
        grades_summary, price_target_consensus, insider_stats,
    ) = await asyncio.gather(
        _safe_mcp(fmp_client, "profile-symbol", {"symbol": ticker}, logger=_logger),
        _safe_mcp(fmp_client, "search-stock-news", {"symbols": [ticker], "limit": 10}, default=[], logger=_logger),
        _safe_mcp(fmp_client, "search-press-releases", {"symbols": [ticker], "limit": 5}, default=[], logger=_logger),
        _safe_mcp(fmp_client, "grades-summary", {"symbol": ticker}, logger=_logger),
        _safe_mcp(fmp_client, "price-target-consensus", {"symbol": ticker}, logger=_logger),
        _safe_mcp(fmp_client, "insider-trade-statistics", {"symbol": ticker}, logger=_logger),
    )

    profile = profile[0] if isinstance(profile, list) and profile else profile

    # ── Scraping Dog REST calls (unchanged) ───────────────────────────────
    search_queries = [
        f"{ticker} stock analyst rating 2025",
        f"{ticker} stock news sentiment",
        f"{ticker} stock risks headwinds"
    ]

    async with aiohttp.ClientSession() as session:
        search_tasks = []
        for query in search_queries:
            params = {
                "api_key": scraping_key,
                "query": query,
                "results": 10,
                "country": "us",
                "page": 0
            }
            search_tasks.append(
                fetch_with_retry(session, "https://api.scrapingdog.com/google", params)
            )

        search_results = await asyncio.gather(*search_tasks, return_exceptions=True)

    # Parse search results
    analyst_ratings = []
    news_sentiment = []
    risks = []

    for i, result in enumerate(search_results):
        if not isinstance(result, Exception) and isinstance(result, dict) and "organic_results" in result:
            items = result["organic_results"]
            for item in items:
                entry = {
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "snippet": item.get("snippet", "")
                }
                _logger.log("Scraping Dog", f"Search: {search_queries[i]}", item.get("link", ""))

                if i == 0:
                    analyst_ratings.append(entry)
                elif i == 1:
                    news_sentiment.append(entry)
                else:
                    risks.append(entry)

    # Build estimates from profile data
    estimates = {}
    if not isinstance(profile, Exception) and isinstance(profile, dict):
        estimates = {
            "marketCap": profile.get("marketCap", 0),
            "beta": profile.get("beta", 0),
            "price": profile.get("price", 0)
        }

    return {
        "ticker": ticker,
        "analyst_ratings": analyst_ratings,
        "news_sentiment": news_sentiment,
        "risks": risks,
        "analyst_estimates": estimates,

        # New enriched data sources (MCP)
        "stock_news": stock_news if not isinstance(stock_news, Exception) else [],
        "press_releases": press_releases if not isinstance(press_releases, Exception) else [],
        "grades_summary": grades_summary if not isinstance(grades_summary, Exception) else {},
        "price_target_consensus": price_target_consensus if not isinstance(price_target_consensus, Exception) else {},
        "insider_trade_statistics": insider_stats if not isinstance(insider_stats, Exception) else {},
    }


async def fetch_technical_data(ticker: str, fmp_client: Client | None = None, logger: "SourceLogger | None" = None) -> Dict[str, Any]:
    """Fetch technical indicators and price data from FMP (MCP)."""
    _logger = logger or source_logger
    if fmp_client is None:
        raise ValueError("fmp_client is required — MCP client must be provided")

    from_date = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d")
    to_date = datetime.now().strftime("%Y-%m-%d")

    # ── MCP calls ─────────────────────────────────────────────────────────
    (
        historical_raw, quote, profile,
        rsi_data, sma50_data, sma200_data, ema20_data,
        quote_change,
    ) = await asyncio.gather(
        _safe_mcp(fmp_client, "historical-price-eod-full", {"symbol": ticker, "from": from_date, "to": to_date}, default=[], logger=_logger),
        _safe_mcp(fmp_client, "quote", {"symbol": ticker}, logger=_logger),
        _safe_mcp(fmp_client, "profile-symbol", {"symbol": ticker}, logger=_logger),
        _safe_mcp(fmp_client, "relative-strength-index", {"symbol": ticker, "periodLength": 14, "timeframe": "1day"}, logger=_logger),
        _safe_mcp(fmp_client, "simple-moving-average", {"symbol": ticker, "periodLength": 50, "timeframe": "1day"}, logger=_logger),
        _safe_mcp(fmp_client, "simple-moving-average", {"symbol": ticker, "periodLength": 200, "timeframe": "1day"}, logger=_logger),
        _safe_mcp(fmp_client, "exponential-moving-average", {"symbol": ticker, "periodLength": 20, "timeframe": "1day"}, logger=_logger),
        _safe_mcp(fmp_client, "quote-change", {"symbol": ticker}, logger=_logger),
    )

    # Normalize list-wrapped results
    quote = quote[0] if isinstance(quote, list) and quote else quote
    profile = profile[0] if isinstance(profile, list) and profile else profile

    # Parse historical prices
    historical = []
    if isinstance(historical_raw, dict) and "historical" in historical_raw:
        historical = historical_raw["historical"]
    elif isinstance(historical_raw, list):
        historical = historical_raw

    # Extract closing prices (most recent first) for fallback calculations
    closes = []
    volumes = []
    for day in historical:
        if isinstance(day, dict) and "close" in day:
            closes.append(day["close"])
            volumes.append(day.get("volume", 0))

    # ── Extract native indicators from MCP, fall back to manual calc ──────

    # RSI
    rsi = None
    if isinstance(rsi_data, list) and rsi_data:
        rsi = rsi_data[0].get("rsi")
    elif isinstance(rsi_data, dict):
        rsi = rsi_data.get("rsi")
    if rsi is not None:
        try:
            rsi = round(float(rsi), 2)
        except (TypeError, ValueError):
            rsi = None
    if rsi is None:
        rsi = _calculate_rsi(closes, period=14)

    # SMA 50
    sma50 = None
    if isinstance(sma50_data, list) and sma50_data:
        sma50 = sma50_data[0].get("sma")
    elif isinstance(sma50_data, dict):
        sma50 = sma50_data.get("sma")
    if sma50 is not None:
        try:
            sma50 = round(float(sma50), 2)
        except (TypeError, ValueError):
            sma50 = None
    if sma50 is None:
        sma50 = _calculate_sma(closes, period=50)

    # SMA 200
    sma200 = None
    if isinstance(sma200_data, list) and sma200_data:
        sma200 = sma200_data[0].get("sma")
    elif isinstance(sma200_data, dict):
        sma200 = sma200_data.get("sma")
    if sma200 is not None:
        try:
            sma200 = round(float(sma200), 2)
        except (TypeError, ValueError):
            sma200 = None
    if sma200 is None:
        sma200 = _calculate_sma(closes, period=200)

    # EMA 20 (new — no manual fallback)
    ema20 = None
    if isinstance(ema20_data, list) and ema20_data:
        ema20 = ema20_data[0].get("ema")
    elif isinstance(ema20_data, dict):
        ema20 = ema20_data.get("ema")
    if ema20 is not None:
        try:
            ema20 = round(float(ema20), 2)
        except (TypeError, ValueError):
            ema20 = None

    # Price changes — prefer MCP quote-change, fall back to manual calc
    price_changes = {}
    if isinstance(quote_change, list) and quote_change:
        qc = quote_change[0]
    elif isinstance(quote_change, dict):
        qc = quote_change
    else:
        qc = {}

    if qc:
        mapping = {
            "1D": "1D",
            "5D": "5D",
            "1M": "1M",
            "3M": "3M",
            "6M": "6M",
            "ytd": "YTD",
            "1Y": "1Y",
            "5Y": "5Y",
        }
        for api_key, label in mapping.items():
            val = qc.get(api_key)
            if val is not None:
                try:
                    price_changes[label] = round(float(val), 2)
                except (TypeError, ValueError):
                    pass

    # Fall back to manual calculation if quote-change returned nothing useful
    if not price_changes:
        price_changes = _calculate_price_changes(closes, quote)

    # Build recent price action summary (last 10 trading days)
    recent_prices = []
    for day in historical[:10]:
        if isinstance(day, dict):
            recent_prices.append({
                "date": day.get("date", ""),
                "open": day.get("open", 0),
                "high": day.get("high", 0),
                "low": day.get("low", 0),
                "close": day.get("close", 0),
                "volume": day.get("volume", 0),
            })

    # Calculate average volume (20-day)
    avg_volume_20 = sum(volumes[:20]) / min(len(volumes), 20) if volumes else 0

    # Identify support/resistance from recent highs/lows
    support_resistance = _calculate_support_resistance(historical[:90])

    return {
        "ticker": ticker,
        "current_price": quote.get("price", 0) if isinstance(quote, dict) else 0,
        "rsi_14": rsi,
        "sma_50": sma50,
        "sma_200": sma200,
        "ema_20": ema20,
        "sma_50_vs_200": "bullish (golden cross)" if sma50 and sma200 and sma50 > sma200 else "bearish (death cross)" if sma50 and sma200 else "insufficient data",
        "price_changes": price_changes,
        "recent_prices": recent_prices,
        "avg_volume_20d": round(avg_volume_20),
        "latest_volume": volumes[0] if volumes else 0,
        "volume_trend": "above average" if volumes and volumes[0] > avg_volume_20 else "below average" if volumes else "unknown",
        "support_resistance": support_resistance,
        "year_high": profile.get("yearHigh", 0) if isinstance(profile, dict) else 0,
        "year_low": profile.get("yearLow", 0) if isinstance(profile, dict) else 0,
        "historical_prices_available": len(closes),
    }
