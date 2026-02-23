"""Integration tests for the complete pipeline."""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

from run import run_pipeline, validate_environment


def _mock_fmp_client_cm():
    """Create a mock for ``async with Client(url) as fmp_client:``."""
    mock_client = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    return mock_cm


@pytest.mark.asyncio
async def test_pipeline_with_mocked_apis():
    """Test the complete pipeline with mocked API calls."""

    mock_quant_data = {
        "ticker": "AAPL",
        "quote": {"price": 175.50, "pe": 28.5},
        "income_statements": [{"revenue": 383285000000}],
        "macro": {"fed_funds_rate": 5.50, "vix": 14.5}
    }

    mock_sentiment_data = {
        "ticker": "AAPL",
        "analyst_ratings": [{"title": "Apple Buy Rating", "snippet": "Strong buy"}],
        "news_sentiment": [{"title": "Positive news", "snippet": "Good earnings"}]
    }

    mock_technical_data = {
        "ticker": "AAPL",
        "rsi_14": 65.5,
        "sma_50": 170.5,
        "sma_200": 165.2,
        "price_changes": {"1M": 3.5}
    }

    mock_quant_report = "## Quantitative Valuation Report: AAPL\nStrong fundamentals with P/E of 28.5.\n**Opinion: Buy**"
    mock_sentiment_report = "## Sentiment Report: AAPL\nPositive analyst sentiment.\n**Opinion: Buy**"
    mock_technical_report = "## Technical Signals Report: AAPL\nBullish RSI at 65.5.\n**Opinion: Buy**"
    mock_pm_decision = "## Portfolio Manager Decision: AAPL\n**Decision: BUY | Conviction: High**\nUnanimous buy signals."
    mock_da_report = "## Devil's Advocate Report: AAPL\n**Contrarian Recommendation: SELL**\nValuation concerns."
    mock_final_decision = "## Final Investment Decision: AAPL\n**Decision: BUY | Conviction: High | Maintained**\nMaintaining buy."

    with patch("run.Client", return_value=_mock_fmp_client_cm()), \
         patch("run.fetch_quant_data", new_callable=AsyncMock, return_value=mock_quant_data), \
         patch("run.fetch_sentiment_data", new_callable=AsyncMock, return_value=mock_sentiment_data), \
         patch("run.fetch_technical_data", new_callable=AsyncMock, return_value=mock_technical_data), \
         patch("run.call_agent", new_callable=AsyncMock) as mock_call_agent, \
         patch("run.call_research_agents_parallel", new_callable=AsyncMock,
               return_value=(mock_quant_report, mock_sentiment_report, mock_technical_report)), \
         patch("run.save_report") as mock_save_report, \
         patch("run.save_research_report") as mock_save_research, \
         patch("run.source_logger") as mock_logger, \
         patch.dict("os.environ", {"FMP_API_KEY": "test_key"}):

        mock_call_agent.side_effect = [
            mock_pm_decision,
            mock_da_report,
            mock_final_decision
        ]

        mock_logger.get_log.return_value = []
        mock_save_report.return_value = Path("reports/AAPL_test.md")
        mock_save_research.return_value = Path("reports/agent-research/AAPL_test.md")

        result = await run_pipeline("AAPL", verbose=False)

        assert result is not None
        assert "AAPL" in str(result)
        assert mock_call_agent.call_count == 3
        mock_save_report.assert_called_once()
        assert mock_save_research.call_count == 6


def test_validate_environment():
    """Test environment validation."""

    with patch.dict("os.environ", {
        "ANTHROPIC_API_KEY": "test",
        "XAI_API_KEY": "test",
        "ZAI_API_KEY": "test",
        "MOONSHOT_API_KEY": "test",
        "FMP_API_KEY": "test",
        "FRED_API_KEY": "test",
        "SCRAPINGDOG_API_KEY": "test"
    }):
        assert validate_environment() is True

    with patch.dict("os.environ", {
        "XAI_API_KEY": "test",
        "ZAI_API_KEY": "test",
        "MOONSHOT_API_KEY": "test",
        "FMP_API_KEY": "test",
        "FRED_API_KEY": "test",
        "SCRAPINGDOG_API_KEY": "test"
    }, clear=True):
        assert validate_environment() is False

    with patch.dict("os.environ", {
        "ANTHROPIC_API_KEY": "test",
        "XAI_API_KEY": "test",
        "ZAI_API_KEY": "test",
        "MOONSHOT_API_KEY": "test",
        "FRED_API_KEY": "test",
        "SCRAPINGDOG_API_KEY": "test"
    }, clear=True):
        assert validate_environment() is False


@pytest.mark.asyncio
async def test_pipeline_error_handling():
    """Test pipeline handles errors gracefully."""

    with patch("run.Client", return_value=_mock_fmp_client_cm()), \
         patch("run.fetch_quant_data", new_callable=AsyncMock,
               side_effect=Exception("API Error")), \
         patch("run.fetch_sentiment_data", new_callable=AsyncMock,
               return_value={"ticker": "AAPL"}), \
         patch("run.fetch_technical_data", new_callable=AsyncMock,
               return_value={"ticker": "AAPL"}), \
         patch.dict("os.environ", {"FMP_API_KEY": "test_key"}):

        result = await run_pipeline("AAPL", verbose=False)
        assert result is None


@pytest.mark.asyncio
async def test_pipeline_with_agent_timeout():
    """Test pipeline handles agent timeouts."""

    mock_data = {"ticker": "AAPL", "quote": {"price": 175.50}}

    with patch("run.Client", return_value=_mock_fmp_client_cm()), \
         patch("run.fetch_quant_data", new_callable=AsyncMock, return_value=mock_data), \
         patch("run.fetch_sentiment_data", new_callable=AsyncMock, return_value=mock_data), \
         patch("run.fetch_technical_data", new_callable=AsyncMock, return_value=mock_data), \
         patch("run.call_research_agents_parallel", new_callable=AsyncMock) as mock_parallel, \
         patch.dict("os.environ", {"FMP_API_KEY": "test_key"}):

        mock_parallel.return_value = (
            "Quant report",
            "## Sentiment Report: ERROR\n\nThis research agent encountered an error and could not complete analysis.\n\n**Opinion: Neutral**",
            "Technical report"
        )

        with patch("run.call_agent", new_callable=AsyncMock, return_value="Decision"), \
             patch("run.save_report", return_value=Path("test.md")), \
             patch("run.save_research_report", return_value=Path("test.md")), \
             patch("run.source_logger.get_log", return_value=[]):

            result = await run_pipeline("AAPL", verbose=False)
            assert result is not None
            mock_parallel.assert_called_once()
