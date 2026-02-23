# Product Requirements Document: RAgent — Investment Committee Agent Framework

## 1. Purpose & Problem Statement

**Problem**: Individual investors and small advisory teams lack access to institutional-grade investment committee processes. Professional fund managers benefit from multi-perspective analysis — quantitative valuation, sentiment research, and technical signals — followed by structured debate. Replicating this workflow manually is time-consuming, inconsistent, and subject to individual cognitive biases.

**Solution**: RAgent automates a multi-agent investment committee using specialized LLM agents in a structured 4-stage pipeline. Each agent analyzes the same stock from a different angle, a portfolio manager synthesizes the research into a decision, a devil's advocate stress-tests the thesis, and a final decision is rendered — all within ~60 seconds.

**Target Output**: A markdown report containing research from three independent analysts, an initial portfolio manager decision, a contrarian challenge, and a final Buy/Sell recommendation with conviction level.

**Live Instance**: [https://ragent.spacetimelogics.com](https://ragent.spacetimelogics.com)

## 2. High-Level Architecture

**Pipeline Flow**:
1. **Data Collection** — Concurrent fetching from FMP (MCP), FRED (REST), Scraping Dog (REST)
2. **Data Curation** — Raw API responses converted to concise analyst-readable summaries
3. **Parallel Research** — Three specialized LLM agents analyze quant, sentiment, and technical data simultaneously
4. **Portfolio Manager Decision** — Synthesizes three research reports into a Buy/Sell decision
5. **Devil's Advocate Challenge** — Builds the strongest case for the opposite position
6. **Final Decision** — Portfolio Manager issues a final ruling after considering the contrarian arguments

```
Stage 1: Parallel Research (asyncio.gather)
┌─────────────────┬─────────────────┬─────────────────┐
│ Quant Valuation  │ Sentiment Search│ Technical Signals│
│ (Grok 4.1)       │ (GLM-5)        │ (Kimi K2.5)     │
└────────┬─────────┴────────┬────────┴────────┬────────┘
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

**Key Components**:
- **Data Layer** (`data.py`): Async data fetching via MCP and REST with source logging
- **Curation Layer** (`curation.py`): Converts raw API responses to role-specific text summaries
- **Agent Layer** (`agents.py`): Unified interface for Anthropic and OpenAI-compatible LLM calls
- **Prompt Layer** (`prompts.py`): Structured prompt templates for each pipeline stage
- **Report Layer** (`report.py`): Markdown report generation with source audit trail
- **Web Layer** (`api_server.py`, `pipeline_web.py`): FastAPI server with SSE streaming
- **Frontend** (`frontend/`): React SPA with real-time step-by-step display

## 3. Data Sources

**Financial Modeling Prep (FMP) — via MCP Protocol**:
- **Core Statements**: Quote, income statement, balance sheet, cash flow (annual, 5 periods)
- **Valuation & Ratios**: Metrics-ratios, key-metrics, enterprise values (annual)
- **Growth**: Financial statement growth metrics
- **Analyst Data**: Financial estimates, price target summary, grades summary, price target consensus
- **Valuation Models**: DCF advanced, DCF levered
- **Health Scores**: Altman Z-Score, Piotroski Score
- **TTM Data**: Income statements TTM, key metrics TTM
- **Sector Comparison**: Sector PE snapshot, industry PE snapshot
- **Segmentation**: Revenue product segmentation
- **Sentiment**: Stock news (10 articles), press releases (5), insider trade statistics
- **Technical**: Historical price EOD (400 days), RSI(14), SMA(50), SMA(200), EMA(20), quote change

**FRED (Federal Reserve Economic Data) — REST API**:
- Federal Funds Rate (DFF)
- 10Y-2Y Treasury Yield Spread (T10Y2Y)
- VIX Volatility Index (VIXCLS)

**Scraping Dog (Google Search) — REST API**:
- `"{ticker} stock analyst rating 2025"` — analyst consensus signals
- `"{ticker} stock news sentiment"` — recent news themes
- `"{ticker} stock risks headwinds"` — risk narratives

**Data Quality Features**:
- MCP calls wrapped in `_safe_mcp()` with graceful failure (returns defaults on error)
- REST calls with retry logic and exponential backoff on 429 responses
- Field name normalization layer (`_normalize_quant_data()`) mapping MCP field names to pipeline-expected names
- Per-request `SourceLogger` instances for concurrent web request isolation
- Manual fallback calculations for RSI, SMA, support/resistance when MCP indicators fail

## 4. Technical Requirements

**System Requirements**:
- Python 3.12.7
- Node.js 22 LTS (frontend build)
- AWS EC2 `t3.medium` (2 vCPU, 4GB RAM, 20GB gp3) for production
- Single async worker (MCP client is not multi-process safe)

**Core Libraries — Backend**:
- **LLM SDKs**: anthropic (Claude), openai (Grok, GLM-5, Kimi K2.5 via OpenAI-compat)
- **MCP Client**: fastmcp (FMP data via Model Context Protocol)
- **Async HTTP**: aiohttp (FRED, Scraping Dog REST calls)
- **Web Framework**: FastAPI, uvicorn (SSE streaming)
- **Configuration**: python-dotenv (.env file management)
- **Testing**: pytest, pytest-asyncio, pytest-mock, aioresponses

**Core Libraries — Frontend**:
- **UI**: React 19, TypeScript
- **Build**: Vite 6
- **Markdown**: marked (rendering agent reports)

**Development Tools**:
- Version control: Git + GitHub
- AI coding assistant: Claude Code
- Environment: Virtual environments (.venv)

**Infrastructure**:
- Development: Local Python + Vite dev server with proxy
- Production: AWS EC2, nginx reverse proxy, systemd service
- SSE streaming: `proxy_buffering off` in nginx for real-time event delivery
- Rate limiting: File-based daily counter (`./data/usage.json`), 50 analyses/day

## 5. Agent Specifications

**Model Registry**:

| Role | Model | Provider | Interface | Max Tokens |
|------|-------|----------|-----------|------------|
| Portfolio Manager (Stages 2 & 4) | Claude Opus 4.6 | Anthropic | Native SDK | 2,000 |
| Devil's Advocate (Stage 3) | Claude Sonnet 4.6 | Anthropic | Native SDK | 2,000 |
| Quant Valuation Researcher | Grok 4.1 Thinking | xAI | OpenAI-compat | 8,192 |
| Sentiment Researcher | GLM-5 | Zhipu | OpenAI-compat | 2,000 |
| Technical Signals Researcher | Kimi K2.5 | Moonshot | OpenAI-compat | 8,192 |

**Agent Anonymity**: Agents refer to each other only by role name. No model names, provider names, or API details appear in any prompt.

**Thinking Model Handling**: Grok 4.1 and Kimi K2.5 may return `<think>...</think>` blocks. These are stripped via regex before downstream consumption.

**Output Constraints**: Each agent targets a 200-word limit. Responses exceeding 250 words trigger a warning but are not truncated.

**Research Agent Output Format**:
- Key findings from analysis
- Investment opinion: Strong Buy / Buy / Neutral / Sell / Strong Sell
- 2-3 supporting bullet points
- 1-2 risk bullets

**Portfolio Manager Output Format**:
- Decision: BUY or SELL
- Conviction level: High / Medium / Low
- Summary rationale
- Key risk to monitor
- Position sizing guidance

**Devil's Advocate Output Format**:
- Specific weaknesses in PM's reasoning
- Counter-evidence from data
- Contrarian recommendation with supporting arguments
- Conditions under which PM's original thesis would be correct

## 6. Web Interface Specifications

**API Endpoints**:
- `POST /api/analyze` — Accepts `{"ticker": "AAPL"}`, returns SSE event stream
- `GET /api/usage` — Returns `{count, limit, remaining}`
- `GET /` — Serves React SPA from `frontend/dist/`

**SSE Event Flow**:
```
status(data_fetch) → data_ready → status(research) → agent_done×3
→ status(pm_decision) → stage_done(pm) → status(da_challenge)
→ stage_done(da) → status(final_decision) → stage_done(final) → complete
```

**Concurrency Guards**:
- Duplicate ticker analysis blocked via `_active_tickers` set
- Per-request `SourceLogger` prevents source log pollution between concurrent analyses
- 1-second per-provider rate limiting on LLM API calls

**Frontend State Machine**:
- `idle` → `data_fetch` → `research` → `pm_decision` → `da_challenge` → `final_decision` → `complete`
- Error state reachable from any stage
- SSE connection via `fetch()` + `ReadableStream` (not `EventSource`, which only supports GET)

**UI Design**:
- Dark theme (`#0a0a0f` background), monospace system font
- Green/red accent for BUY/SELL decisions
- Sequential step display: each stage replaces the previous with a fade transition
- Final view: hero BUY/SELL card with expandable `<details>` for all reports and data sources

## 7. Success Metrics

**Pipeline Reliability**:
- All 3 research agents complete successfully (graceful degradation if one fails)
- End-to-end pipeline execution under 120 seconds
- 26 unit tests passing across all modules

**Data Completeness**:
- Zero N/A values for core financial fields (P/E, EPS, margins, ratios, estimates, price targets)
- Source log captures every external API call with timestamp
- Field name normalization handles all known MCP-to-legacy field mappings

**Web Interface**:
- SSE events stream without buffering (nginx `proxy_buffering off`)
- Daily usage cap enforced atomically via file lock
- Concurrent analyses of different tickers isolated correctly

## 8. Monitoring & Observability

**Source Logging**:
Every external API call is logged with source name, data type, URL, and timestamp. The complete source log is:
- Rendered as a table in the final markdown report
- Returned in the `complete` SSE event for the web interface
- Scoped per-request (web) or per-pipeline-run (CLI)

**Progress Output (CLI)**:
```
[00:00] Starting Investment Committee analysis for AAPL...
[00:01] Connecting to FMP MCP server & fetching market data...
[00:08] Data fetched successfully
[00:08] Stage 1: Running parallel research agents...
[00:14]   → Quantitative Valuation Researcher... done (6.2s)
[00:14]   → Sentiment Researcher... done (5.8s)
[00:14]   → Technical Signals Researcher... done (6.1s)
[00:14] Stage 2: Portfolio Manager decision...
[00:20] Stage 3: Devil's Advocate challenge...
[00:28] Stage 4: Final decision...
[00:34] Report saved: ./reports/AAPL_20260223_143022.md
```

**Error Handling**:
- Individual agent timeouts (120s) do not crash the pipeline
- Failed research agents produce an error placeholder; PM notes missing research
- MCP call failures return safe defaults (empty dict/list)
- Rate limit errors (429) trigger exponential backoff (up to 3 retries)

**Data Quality Checks**:
- Word count warnings for agent responses exceeding 250 words
- Data archive saved for every pipeline run (`reports/agent-research/`)
- Individual agent reports saved separately for audit

## 9. Scope & Deliverables

**Version 1.0 (Current)**:
- Coverage: Any US-listed stock ticker (1-5 characters)
- Interfaces: CLI (`python run.py AAPL`) and web (SSE streaming)
- Output: Markdown report with 4-stage pipeline results and source log
- Deployment: AWS EC2 with nginx, systemd, Let's Encrypt SSL
- Rate limiting: 50 analyses per day (web interface)

**Future Enhancements**:
- Historical analysis comparison (track decisions over time)
- Portfolio-level analysis (multiple tickers, correlation)
- Custom agent configuration (swap models, adjust prompts)
