"""Tests for report generation module."""

import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

from report import ReportBuilder, save_report, save_research_report


def test_report_builder_initialization():
    """Test ReportBuilder initialization."""
    builder = ReportBuilder("AAPL")
    assert builder.ticker == "AAPL"
    assert builder.start_time is not None
    assert builder.stages == {}
    assert builder.source_log == []


def test_add_stage():
    """Test adding stage outputs to report."""
    builder = ReportBuilder("AAPL")
    
    builder.add_stage("research", {
        "quant": "Quant analysis report",
        "sentiment": "Sentiment analysis report",
        "technical": "Technical analysis report"
    })
    
    assert "research" in builder.stages
    assert builder.stages["research"]["quant"] == "Quant analysis report"


def test_set_source_log():
    """Test setting source log."""
    builder = ReportBuilder("AAPL")
    
    sources = [
        {"source": "FMP", "type": "Quote", "url": "https://api.fmp.com/quote/AAPL"},
        {"source": "FRED", "type": "VIX", "url": "https://api.fred.com/vix"}
    ]
    
    builder.set_source_log(sources)
    assert len(builder.source_log) == 2
    assert builder.source_log[0]["source"] == "FMP"


def test_generate_markdown():
    """Test generating markdown report."""
    builder = ReportBuilder("AAPL")
    
    # Add all stages
    builder.add_stage("research", {
        "quant": "## Quantitative Valuation Report: AAPL\nStrong fundamentals.\n**Opinion: Buy**",
        "sentiment": "## Sentiment Report: AAPL\nPositive sentiment.\n**Opinion: Buy**",
        "technical": "## Technical Signals Report: AAPL\nBullish signals.\n**Opinion: Buy**"
    })
    
    builder.add_stage("stage2", "## Portfolio Manager Decision: AAPL\n**Decision: BUY | Conviction: High**\nBased on unanimous buy signals.")
    
    builder.add_stage("devil_advocate", "## Devil's Advocate Report: AAPL\n**Contrarian Recommendation: SELL**\nValuation concerns.")
    
    builder.add_stage("final", "## Final Investment Decision: AAPL\n**Decision: BUY | Conviction: High | Maintained**\nMaintaining buy decision.")
    
    # Set source log
    builder.set_source_log([
        {"source": "FMP", "type": "Quote", "url": "https://api.fmp.com/quote/AAPL", "timestamp": "2024-01-01T10:00:00"},
        {"source": "FRED", "type": "VIX", "url": "https://api.fred.com/vix", "timestamp": "2024-01-01T10:00:01"}
    ])
    
    markdown = builder.generate_markdown()
    
    # Check structure
    assert "# Investment Committee Report: AAPL" in markdown
    assert "## Stage 1: Research Reports" in markdown
    assert "### Quantitative Valuation Research" in markdown
    assert "### Sentiment Research" in markdown
    assert "### Technical Signals Research" in markdown
    assert "## Stage 2: Portfolio Manager Initial Decision" in markdown
    assert "## Stage 3: Devil's Advocate Challenge" in markdown
    assert "## Stage 4: Final Investment Decision" in markdown
    assert "## Source Log" in markdown
    assert "| Source | Type | URL |" in markdown
    assert "| FMP | Quote |" in markdown


def test_save_report_creates_directory():
    """Test that save_report creates the reports directory if it doesn't exist."""
    with patch("pathlib.Path.mkdir") as mock_mkdir, \
         patch("pathlib.Path.exists", return_value=False), \
         patch("pathlib.Path.write_text") as mock_write:
        
        builder = ReportBuilder("AAPL")
        builder.add_stage("final", "Test content")
        
        filepath = save_report(builder)
        
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_write.assert_called_once()
        assert "AAPL" in str(filepath)


def test_save_report_filename_format():
    """Test that save_report generates correct filename."""
    with patch("pathlib.Path.write_text"), \
         patch("pathlib.Path.exists", return_value=True):
        
        builder = ReportBuilder("TSLA")
        builder.add_stage("final", "Test content")
        
        # Mock both datetime.now() calls - one in generate_markdown, one in save_report
        with patch("report.datetime") as mock_datetime:
            mock_now = MagicMock()
            mock_now.strftime.return_value = "20240115_143022"
            mock_datetime.now.return_value = mock_now
            
            # Also need to mock the total_seconds calculation for duration
            mock_now.__sub__.return_value.total_seconds.return_value = 10.5
            
            filepath = save_report(builder)
        
        assert filepath.name == "TSLA_20240115_143022.md"
        assert filepath.parent.name == "reports"


def test_duration_calculation():
    """Test pipeline duration calculation."""
    builder = ReportBuilder("AAPL")
    
    # Mock time passage
    import time
    time.sleep(0.1)
    
    builder.add_stage("final", "Done")
    markdown = builder.generate_markdown()
    
    # Duration should be greater than 0
    assert "Pipeline Duration:" in markdown
    assert "0." in markdown or "1" in markdown  # Should show some duration


def test_save_research_report():
    """Test saving individual research agent reports."""
    with patch("pathlib.Path.write_text") as mock_write, \
         patch("pathlib.Path.mkdir") as mock_mkdir, \
         patch("report.datetime") as mock_datetime:
        
        mock_datetime.now.return_value.strftime.return_value = "20240115_143022"
        
        # Test saving quant report
        filepath = save_research_report("AAPL", "quant", "Test quant report content")
        
        mock_mkdir.assert_called_with(parents=True, exist_ok=True)
        mock_write.assert_called_once_with("Test quant report content")
        assert filepath.name == "AAPL_quant_20240115_143022.md"
        assert "agent-research" in str(filepath.parent)
        
        # Test saving sentiment report with custom directory
        mock_write.reset_mock()
        filepath = save_research_report("TSLA", "sentiment", "Test sentiment", "./custom/dir")
        
        assert filepath.name == "TSLA_sentiment_20240115_143022.md"
        assert "custom/dir" in str(filepath.parent)