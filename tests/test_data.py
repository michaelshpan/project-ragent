"""Tests for data fetching module."""

import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from aioresponses import aioresponses

from data import fetch_quant_data, fetch_sentiment_data, fetch_technical_data


def _make_mcp_client(tool_responses: dict) -> MagicMock:
    """Create a mock MCP client that returns predefined responses per tool name.

    tool_responses: {tool_name: return_value, ...}
    """
    client = MagicMock()

    async def _call_tool(tool_name, args):
        data = tool_responses.get(tool_name, {})
        result = MagicMock()
        result.structured_content = None
        block = MagicMock()
        block.text = json.dumps(data)
        result.content = [block]
        return result

    client.call_tool = AsyncMock(side_effect=_call_tool)
    return client


@pytest.mark.asyncio
async def test_fetch_quant_data():
    """Test fetching quantitative data from MCP + FRED."""
    ticker = "AAPL"

    # Define MCP tool responses
    tool_responses = {
        "quote": [{"symbol": "AAPL", "price": 175.50, "marketCap": 2750000000000, "pe": 28.5, "eps": 6.15}],
        "income-statement": [{"date": "2023-09-30", "revenue": 383285000000, "netIncome": 96995000000}],
        "balance-sheet-statement": [{"date": "2023-09-30", "totalAssets": 352000000000}],
        "cashflow-statement": [{"date": "2023-09-30", "freeCashFlow": 110000000000}],
        "metrics-ratios": [{"peRatio": 28.5, "priceToBookRatio": 47.2, "debtEquityRatio": 1.95}],
        "key-metrics": [{"revenuePerShare": 24.5}],
        "enterprise-values": [{"enterpriseValue": 2800000000000, "marketCapitalization": 2750000000000}],
        "financial-statement-growth": [{"revenueGrowth": 0.05}],
        "profile-symbol": [{"companyName": "Apple Inc.", "sector": "Technology"}],
        "financial-estimates": [{"estimatedRevenueAvg": 400000000000, "estimatedEpsAvg": 6.50}],
        "price-target-summary": {"priceTargetAverage": 200},
        "dcf-advanced": {"dcf": 190.0},
        "dcf-levered": {"leveredDCF": 185.0},
        "financial-scores": {"altmanZScore": 8.5, "piotroskiScore": 7},
        "income-statements-ttm": [{"revenue": 400000000000}],
        "key-metrics-ttm": {"peRatioTTM": 29.0},
        "sector-PE-snapshot": [{"sector": "Technology", "pe": 30.0}],
        "industry-PE-snapshot": [{"industry": "Consumer Electronics", "pe": 25.0}],
        "revenue-product-segmentation": [{"iPhone": 200000000000, "Services": 80000000000}],
    }

    fmp_client = _make_mcp_client(tool_responses)

    with aioresponses() as mocked:
        # Mock FRED API responses
        mocked.get(
            "https://api.stlouisfed.org/fred/series/observations",
            payload={"observations": [{"date": "2024-01-01", "value": "5.50"}]},
            repeat=True,
        )

        with patch.dict("os.environ", {"FRED_API_KEY": "test_key"}):
            result = await fetch_quant_data(ticker, fmp_client=fmp_client)

    assert result["ticker"] == ticker
    assert result["quote"]["price"] == 175.50
    assert result["quote"]["pe"] == 28.5
    assert result["income_statements"][0]["revenue"] == 383285000000
    assert result["enterprise_values"][0]["enterpriseValue"] == 2800000000000
    # New enriched fields
    assert "sector_pe" in result
    assert "industry_pe" in result
    assert "revenue_product_segmentation" in result
    assert "macro" in result


@pytest.mark.asyncio
async def test_fetch_sentiment_data():
    """Test fetching sentiment data from MCP + Scraping Dog."""
    ticker = "AAPL"

    # MCP tool responses for sentiment
    tool_responses = {
        "profile-symbol": [{"companyName": "Apple Inc.", "marketCap": 2750000000000, "beta": 1.2, "price": 175.50}],
        "search-stock-news": [{"title": "Apple Q4 earnings beat", "publishedDate": "2024-01-15"}],
        "search-press-releases": [{"title": "Apple Announces New Product", "date": "2024-01-10"}],
        "grades-summary": [{"strongBuy": 20, "buy": 10, "hold": 5, "sell": 1, "strongSell": 0}],
        "price-target-consensus": [{"targetConsensus": 200, "targetHigh": 250, "targetLow": 160}],
        "insider-trade-statistics": [{"totalBought": 5, "totalSold": 3}],
    }

    fmp_client = _make_mcp_client(tool_responses)

    # Mock Scraping Dog at the function level
    with patch("data.fetch_with_retry", new_callable=AsyncMock) as mock_fetch:
        search_results = {
            "organic_results": [
                {
                    "title": "Apple Stock Analysis 2025",
                    "link": "https://example.com/apple-analysis",
                    "snippet": "Apple remains a strong buy with analysts targeting $200"
                },
                {
                    "title": "AAPL Price Target Raised",
                    "link": "https://example.com/aapl-target",
                    "snippet": "Morgan Stanley raises Apple price target to $210"
                }
            ]
        }

        mock_fetch.side_effect = [
            search_results,  # First search query
            search_results,  # Second search query
            search_results,  # Third search query
        ]

        with patch.dict("os.environ", {"SCRAPINGDOG_API_KEY": "test_key"}):
            result = await fetch_sentiment_data(ticker, fmp_client=fmp_client)

    assert result["ticker"] == ticker
    assert len(result["analyst_ratings"]) == 2
    assert result["analyst_ratings"][0]["title"] == "Apple Stock Analysis 2025"
    assert len(result["news_sentiment"]) == 2
    assert len(result["risks"]) == 2
    # New enriched fields
    assert "stock_news" in result
    assert "press_releases" in result
    assert "grades_summary" in result
    assert "price_target_consensus" in result
    assert "insider_trade_statistics" in result
    assert result["analyst_estimates"]["price"] == 175.50


@pytest.mark.asyncio
async def test_fetch_technical_data():
    """Test fetching technical data from MCP."""
    ticker = "AAPL"

    historical = [
        {"date": f"2024-01-{30-i:02d}", "open": 174.0 + i, "high": 176.0 + i,
         "low": 173.5 + i, "close": 175.5 + i, "volume": 50000000}
        for i in range(250)
    ]

    tool_responses = {
        "historical-price-eod-full": {"historical": historical},
        "quote": [{"symbol": "AAPL", "price": 175.50, "changePercentage": 0.5}],
        "profile-symbol": [{"yearHigh": 200.0, "yearLow": 150.0}],
        "relative-strength-index": [{"rsi": 65.5}],
        "simple-moving-average": [{"sma": 170.5}],  # used for both SMA50 and SMA200
        "exponential-moving-average": [{"ema": 172.3}],
        "quote-change": [{"1D": 0.5, "5D": 1.2, "1M": 3.5, "3M": 8.2, "6M": 15.3, "1Y": 22.5}],
    }

    fmp_client = _make_mcp_client(tool_responses)

    result = await fetch_technical_data(ticker, fmp_client=fmp_client)

    assert result["ticker"] == ticker
    assert result["rsi_14"] == 65.5
    assert result["sma_50"] == 170.5
    assert result["sma_200"] == 170.5  # same mock for both SMA calls
    assert result["ema_20"] == 172.3
    assert result["current_price"] == 175.50
    assert result["price_changes"]["1M"] == 3.5
    assert result["year_high"] == 200.0
    assert result["year_low"] == 150.0
    assert len(result["recent_prices"]) == 10
