# Investment Committee Agent Framework

AI-powered multi-agent stock analysis pipeline that generates Buy/Sell decisions using a structured 4-stage investment committee process.

**Live:** [https://ragent.spacetimelogics.com](https://ragent.spacetimelogics.com)

## Overview

The system runs multiple specialized LLM agents through a decision pipeline:
1. **Parallel Research** - Three agents analyze different aspects (quantitative, sentiment, technical)
2. **Portfolio Manager Decision** - Initial Buy/Sell decision based on research
3. **Devil's Advocate Challenge** - Contrarian analysis to stress-test the decision
4. **Final Decision** - Portfolio Manager's final decision after considering challenges

Available as both a **CLI tool** and a **web interface** with real-time streaming.

## Web Interface

Visit [https://ragent.spacetimelogics.com](https://ragent.spacetimelogics.com) to use the app:

1. Enter a stock ticker (e.g. AAPL, NVDA, TSLA)
2. Watch the analysis unfold step-by-step in real time via SSE streaming
3. Review the final BUY/SELL decision with expandable details for all research stages

The web interface has a daily usage cap of 50 analyses to manage API costs.

## Quick Start (CLI)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Up API Keys
Copy `.env.example` to `.env` and add your API keys:
```bash
cp .env.example .env
# Edit .env with your API keys
```

Required API keys:
- **LLM APIs**: ANTHROPIC_API_KEY, XAI_API_KEY, ZAI_API_KEY, MOONSHOT_API_KEY
- **Data APIs**: FMP_API_KEY, FRED_API_KEY, SCRAPINGDOG_API_KEY

### 3. Run Analysis
```bash
python run.py AAPL
```

Reports will be saved to:
- Main report: `./reports/AAPL_YYYYMMDD_HHMMSS.md`
- Individual agent reports: `./reports/agent-research/AAPL_<agent>_YYYYMMDD_HHMMSS.md`

### 4. Run Web Server (Local)
```bash
# Build frontend
cd frontend && npm ci && npm run build && cd ..

# Start server
python api_server.py
# Open http://localhost:8000
```

## Usage Examples

```bash
# Basic usage
python run.py AAPL

# Custom output directory
python run.py TSLA --output-dir ./my-reports

# Quiet mode (no progress output)
python run.py MSFT --quiet
```

## Pipeline Architecture

```
Stage 1: Parallel Research (asyncio.gather)
┌─────────────────┬─────────────────┬─────────────────┐
│ Quant Valuation │ Sentiment Search│ Technical Signals│
│ (Grok 4.1)      │ (GLM-5)        │ (Kimi K2.5)     │
└────────┬────────┴────────┬────────┴────────┬────────┘
         └─────────────────┼──────────────────┘
                           ▼
Stage 2: Portfolio Manager Decision (Claude Opus 4.6)
                           │
                           ▼
Stage 3: Devil's Advocate (Claude Sonnet 4.6)
                           │
                           ▼
Stage 4: Final Decision (Claude Opus 4.6)
```

## Testing

Run tests with pytest:
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_models.py -v

# Run with coverage
pytest --cov=. --cov-report=html
```

### Data Testing Scripts
Test individual components:
```bash
# Test all data fetching functions
python test_data_fetch.py

# Test simple pipeline (data only)
python test_simple_pipeline.py

# Test enhanced data endpoints specifically
python test_enhanced_data.py

# Test individual FMP endpoints
python test_fmp_simple.py
```

## Project Structure

```
project-ragent/
├── run.py              # CLI entry point and pipeline orchestrator
├── api_server.py       # FastAPI web server (SSE streaming)
├── pipeline_web.py     # Web pipeline wrapper (async generator)
├── rate_limit.py       # Daily usage counter for web API
├── agents.py           # LLM agent call functions
├── data.py             # Data fetching from APIs (MCP + REST)
├── curation.py         # Data curation layer (raw → summaries)
├── models.py           # Model registry and configuration
├── prompts.py          # Agent prompt templates
├── report.py           # Report generation and markdown output
├── frontend/           # React + Vite + TypeScript SPA
│   ├── src/
│   │   ├── App.tsx
│   │   ├── hooks/useAnalysis.ts   # SSE connection + state machine
│   │   └── components/            # UI components
│   └── dist/           # Production build (gitignored)
├── deploy/             # EC2 deployment config
│   ├── setup.sh        # Ubuntu provisioning script
│   ├── nginx.conf      # Reverse proxy with SSE support
│   ├── ragent.service  # systemd unit file
│   └── .env.production # API key template
├── tests/              # Test suite (26 tests)
├── reports/            # Generated reports (gitignored)
├── requirements.txt    # Python dependencies
├── .env.example        # API key template
└── README.md           # This file
```

## Recent Enhancements (February 2026)

### 🚀 **Enhanced Data Pipeline**
Upgraded from basic FMP v3 endpoints to comprehensive FMP Stable API coverage:

- **19 total data fields** (up from 12)
- **16+ FMP endpoints** for complete financial analysis
- **Balance sheet data**: $359B assets, $112B debt analysis for AAPL
- **DCF valuations**: Intrinsic value calculations vs market price
- **Financial health scores**: Bankruptcy prediction, financial strength
- **TTM metrics**: Trailing twelve months performance data

### 🔄 **API Migration Completed**
Successfully migrated from deprecated FMP v3 API to stable endpoints after August 2025 deprecation.

### 📊 **Research Agent Improvements**
Enhanced prompts to leverage richer data:
- Quantitative agents now analyze balance sheet strength, financial scores, DCF models
- Sentiment agents incorporate analyst price targets and estimate trends
- Technical agents have access to comprehensive historical data

## API Documentation

### Data Sources

#### Financial Modeling Prep (FMP) - Enhanced API Coverage
Using FMP Stable API endpoints for comprehensive financial data:

**Core Financial Statements:**
- Quote data (price, volume, market cap, price changes)
- Income statements (annual periods)
- Balance sheet statements (assets, liabilities, equity)
- Cash flow statements (operating, investing, financing)

**Valuation & Ratios:**
- Financial ratios (P/E, P/B, debt/equity, ROE)
- Key metrics (annual periods)
- Enterprise values (EV, EV/EBITDA, EV/Sales)
- Financial growth metrics

**Analyst & Market Data:**
- Analyst estimates (revenue, earnings forecasts)
- Price target summary (high, low, average targets)
- Company profile data

**Advanced Valuation Models:**
- Discounted Cash Flow (DCF) valuations
- Advanced levered DCF models

**Financial Health Scores:**
- Altman Z-Score (bankruptcy prediction)
- Piotroski Score (financial strength)

**Trailing Twelve Months (TTM) Data:**
- TTM income statements (quarterly data)
- TTM key metrics for recent performance

#### FRED (Federal Reserve Economic Data)
- Federal Funds Rate (DFF)
- 10Y-2Y Treasury Yield Spread (T10Y2Y) 
- VIX Volatility Index (VIXCLS)

#### Scraping Dog (Google Search API)
- Analyst rating searches
- News sentiment analysis
- Risk and headwind identification

### LLM Models
- **Claude Opus 4.6**: Portfolio Manager decisions
- **Claude Sonnet 4.6**: Devil's Advocate analysis
- **Grok 4.1 Thinking**: Quantitative research
- **GLM-5**: Sentiment analysis
- **Kimi K2.5**: Technical analysis

## Output Format

### Main Report
The consolidated report (`./reports/TICKER_YYYYMMDD_HHMMSS.md`) contains:
- Timestamp and duration metrics
- Three research reports (Stage 1)
- Portfolio Manager initial decision (Stage 2)
- Devil's Advocate challenge (Stage 3)
- Final investment decision (Stage 4)
- Comprehensive source log of all API calls made

### Individual Agent Reports
Each agent's output is also saved separately in `./reports/agent-research/`:
- `TICKER_quant_YYYYMMDD_HHMMSS.md` - Quantitative Valuation Research
- `TICKER_sentiment_YYYYMMDD_HHMMSS.md` - Sentiment Research
- `TICKER_technical_YYYYMMDD_HHMMSS.md` - Technical Signals Research
- `TICKER_portfolio_manager_stage2_YYYYMMDD_HHMMSS.md` - PM Initial Decision
- `TICKER_devil_advocate_YYYYMMDD_HHMMSS.md` - Devil's Advocate Challenge
- `TICKER_final_decision_YYYYMMDD_HHMMSS.md` - PM Final Decision

### Enhanced Data Analysis
The quantitative research now leverages comprehensive financial data:
- **Balance sheet analysis**: Asset quality, debt levels, equity strength
- **Advanced valuation**: DCF models, enterprise value calculations
- **Financial health scoring**: Altman Z-Score, Piotroski Score
- **TTM performance**: Recent quarterly trends and metrics
- **Analyst consensus**: Price targets, earnings estimates
- **Macro integration**: Interest rates, yield curves, market volatility

## Rate Limiting

The system includes automatic rate limiting:
- 1-second delay between calls to the same API provider
- Exponential backoff for rate limit errors (429 responses)
- 120-second timeout per agent call

## Error Handling

- Continues pipeline if individual research agents fail
- Logs errors and includes error notices in reports
- Validates all API keys before starting
- Creates output directory if it doesn't exist
- Handles mixed API response formats (lists vs dictionaries)
- Comprehensive source logging for audit trails