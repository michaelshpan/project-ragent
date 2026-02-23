# CLAUDE.md — Investment Committee Agent Framework

## Project Overview

Build a CLI-based mini-investment committee that generates a Buy/Sell decision for a given stock ticker. The system runs multiple LLM agents in a structured 4-stage pipeline: parallel research → portfolio manager decision → devil's advocate challenge → final decision. All outputs are saved as a markdown report.

**Invocation:** `python run.py AAPL`
**Output:** Markdown report saved to `./reports/AAPL_YYYYMMDD_HHMMSS.md`

---

## Architecture

### Pipeline Stages

```
Stage 1: Parallel Research (asyncio.gather)
┌─────────────────┬─────────────────┬─────────────────┐
│ Quant Valuation  │ Sentiment Search│ Technical Signals│
│ (Grok 4.1 Think) │ (GLM-5)        │ (Qwen-3.5)      │
└────────┬─────────┴────────┬────────┴────────┬─────────┘
         └─────────────────┼──────────────────┘
                           ▼
Stage 2: Portfolio Manager Decision (Opus 4.6)
         Reads all 3 research reports → issues Buy/Sell + rationale
                           │
                           ▼
Stage 3: Devil's Advocate (Sonnet 4.6)
         Reads Stage 2 decision → conducts independent research
         → generates contrarian recommendation (opposite of Stage 2)
                           │
                           ▼
Stage 4: Final Decision (Opus 4.6)
         Compares Stage 2 decision vs DA recommendation
         → issues final Buy/Sell decision
```

### Agent Anonymity Requirement
Agents must NOT know which model powers any other agent. In system prompts, refer to other agents only by role name (e.g., "Quantitative Valuation Researcher", "Portfolio Manager"). Never include model names, provider names, or API details in any prompt sent to agents.

---

## Model Registry & API Configuration

All models use the OpenAI-compatible chat completions interface except Anthropic models. Reference the attached `beacon_planner.py` for proven patterns.

| Role | Model | Provider | model_id | base_url | API Key Env |
|------|-------|----------|----------|----------|-------------|
| Portfolio Manager (Stages 2 & 4) | Claude Opus 4.6 | Anthropic | `claude-opus-4-6` | — (native SDK) | `ANTHROPIC_API_KEY` |
| Devil's Advocate (Stage 3) | Claude Sonnet 4.6 | Anthropic | `claude-sonnet-4-6` | — (native SDK) | `ANTHROPIC_API_KEY` |
| Quant Valuation Researcher | Grok 4.1 Thinking | xAI (OpenAI-compat) | `grok-4-1-fast-reasoning` | `https://api.x.ai/v1` | `XAI_API_KEY` |
| Sentiment Researcher | GLM-5 | Zhipu (OpenAI-compat) | `glm-5` | `https://api.z.ai/api/paas/v4/` | `ZAI_API_KEY` |
| Technical Signals Researcher | Qwen-3.5 | Together AI (OpenAI-compat) | `Qwen/Qwen3-235B-A22B-Thinking-2507` | `https://api.together.xyz/v1` | `TOGETHER_API_KEY` |

### LLM Call Patterns

**Anthropic (non-streaming, for pipeline use):**
```python
import anthropic
client = anthropic.Anthropic(api_key=api_key)
response = client.messages.create(
    model=model_id, max_tokens=2000,
    system=system_prompt,
    messages=[{"role": "user", "content": user_prompt}]
)
text = response.content[0].text
```

**OpenAI-compatible (non-streaming):**
```python
import openai
client = openai.OpenAI(api_key=api_key, base_url=base_url)
response = client.chat.completions.create(
    model=model_id, max_tokens=2000,
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
)
text = response.choices[0].message.content
```

**Important:** Some thinking/reasoning models (Grok 4.1 Thinking, Qwen-3.5) may return reasoning tokens mixed into the response. Strip any `<think>...</think>` or similar tags from the final output before passing to downstream agents. Check the response for these patterns and extract only the final answer content.

---

## Data APIs

### 1. Financial Modeling Prep (FMP)
**Docs:** https://site.financialmodelingprep.com/developer/docs
**Key env:** `FMP_API_KEY`
**Base URL:** `https://financialmodelingprep.com/api/v3`

Endpoints to use:
- `/quote/{ticker}` — current price, market cap, P/E, EPS, 52-week range
- `/income-statement/{ticker}?period=annual&limit=3` — revenue, net income, margins
- `/ratios/{ticker}?period=annual&limit=3` — P/E, EV/EBITDA, ROE, debt/equity
- `/enterprise-values/{ticker}?period=annual&limit=3` — EV, EV/EBITDA
- `/analyst-estimates/{ticker}?limit=1` — consensus estimates
- `/stock-price-change/{ticker}` — 1D, 5D, 1M, 3M, 6M, 1Y, 5Y returns
- `/technical_indicator/daily/{ticker}?type=rsi&period=14` — RSI
- `/technical_indicator/daily/{ticker}?type=sma&period=50` — SMA 50
- `/technical_indicator/daily/{ticker}?type=sma&period=200` — SMA 200
- `/historical-price-full/{ticker}?timeseries=90` — daily OHLCV for 90 days

All endpoints require `?apikey={FMP_API_KEY}` as query parameter.

### 2. FRED API
**Docs:** https://fred.stlouisfed.org/docs/api/fred/
**Key env:** `FRED_API_KEY`
**Base URL:** `https://api.stlouisfed.org/fred`

Endpoints to use:
- `/series/observations?series_id=DFF&limit=1&sort_order=desc&file_type=json` — Fed Funds Rate
- `/series/observations?series_id=T10Y2Y&limit=1&sort_order=desc&file_type=json` — 10Y-2Y spread
- `/series/observations?series_id=VIXCLS&limit=1&sort_order=desc&file_type=json` — VIX

All endpoints require `&api_key={FRED_API_KEY}`.

### 3. Scraping Dog (Google Search)
**Docs:** https://docs.scrapingdog.com/google-search-scraper-api
**Key env:** `SCRAPINGDOG_API_KEY`
**Base URL:** `https://api.scrapingdog.com/google`

```python
params = {
    "api_key": api_key,
    "query": f"{ticker} stock analysis 2025",
    "results": 10,
    "country": "us",
    "page": 0
}
response = requests.get("https://api.scrapingdog.com/google", params=params)
```

Returns JSON with `organic_results` array containing `title`, `link`, `snippet`. Store these as the source log.

---

## Data Layer Design

Create a `data.py` module with async functions that fetch and package data for each research angle. Each function returns a structured dict.

### `async fetch_quant_data(ticker: str) -> dict`
Fetches from FMP: quote, income statements, ratios, enterprise values, analyst estimates, price changes. Also fetches FRED macro data. Returns structured dict with all fields.

### `async fetch_sentiment_data(ticker: str) -> dict`
Fetches from Scraping Dog: 3 searches — `"{ticker} stock analyst rating 2025"`, `"{ticker} stock news sentiment"`, `"{ticker} stock risks headwinds"`. Returns search results (title, snippet, link). Also fetches FMP analyst estimates.

### `async fetch_technical_data(ticker: str) -> dict`
Fetches from FMP: RSI(14), SMA(50), SMA(200), 90-day historical prices, price change percentages. Returns structured dict.

Use `aiohttp` for all HTTP calls. All three fetch functions should be called concurrently via `asyncio.gather` at the start of the pipeline so data is ready before agents run.

---

## Agent System Prompts

### Research Agent System Prompt Template
```
You are the {role_name} on an investment research team analyzing {ticker}.

Your task: Produce a concise research report (200-word limit) based on the provided data.

Your report MUST include:
1. Key findings from your analysis
2. An investment opinion: one of [Strong Buy, Buy, Neutral, Sell, Strong Sell]
3. 2-3 bullet points supporting your opinion
4. Key risks to your thesis (1-2 bullets)

Format your report as:
## {role_name} Report: {ticker}
[Your analysis]
**Opinion: [Strong Buy / Buy / Neutral / Sell / Strong Sell]**

Be specific. Use numbers from the data. Do not pad with generic statements.
200-word limit — be concise and precise.
```

**Quant Valuation Researcher:** Focus on P/E, EV/EBITDA, revenue growth, margin trends, earnings estimates, and how current valuation compares to historical and sector averages. Incorporate macro context (rates, VIX).

**Sentiment Researcher:** Focus on analyst sentiment, recent news themes, institutional positioning signals, and risk narratives from search results. Assess whether market sentiment is bullish, bearish, or mixed.

**Technical Signals Researcher:** Focus on RSI, SMA crossovers (50 vs 200), price momentum (1M/3M/6M returns), volume trends, and support/resistance levels from recent price action.

### Portfolio Manager System Prompt (Stage 2)
```
You are the Portfolio Manager making an investment decision on {ticker}.

You have received research reports from three independent analysts:
1. Quantitative Valuation Researcher
2. Sentiment Researcher
3. Technical Signals Researcher

{research_reports}

Based on these reports, make a BUY or SELL decision.

Your decision summary MUST include:
1. Decision: BUY or SELL
2. Conviction level: High / Medium / Low
3. Summary rationale (how you weighed the three research inputs)
4. Key risk to monitor
5. Suggested position sizing guidance (e.g., full position, half position)

Format:
## Portfolio Manager Decision: {ticker}
**Decision: [BUY/SELL] | Conviction: [High/Medium/Low]**
[Your rationale]

200-word limit.
```

### Devil's Advocate System Prompt (Stage 3)
```
You are the Devil's Advocate on an investment committee reviewing {ticker}.

The Portfolio Manager has made the following decision:
{stage2_decision}

Your job: Build the strongest possible case for the OPPOSITE position.
If the PM said BUY, argue SELL. If the PM said SELL, argue BUY.

You have access to independent research data:
{da_research_data}

Your contrarian report MUST include:
1. The specific weaknesses in the PM's reasoning
2. Counter-evidence from the data
3. Your contrarian recommendation with supporting arguments
4. What conditions would need to change for the PM's original thesis to be correct

Format:
## Devil's Advocate Report: {ticker}
**Contrarian Recommendation: [BUY/SELL] (opposite of PM)**
[Your contrarian argument]

200-word limit. Be rigorous and specific, not contrarian for its own sake.
```

### Portfolio Manager Final Decision System Prompt (Stage 4)
```
You are the Portfolio Manager making the FINAL investment decision on {ticker}.

Your original decision (Stage 2):
{stage2_decision}

The Devil's Advocate challenge:
{da_report}

Review the contrarian arguments. You may either:
A) MAINTAIN your original decision (explain why the DA arguments don't change your view)
B) REVERSE your decision (explain what the DA raised that changed your mind)

Your final decision MUST include:
1. Final Decision: BUY or SELL
2. Whether you maintained or reversed (and why)
3. Final conviction level: High / Medium / Low
4. Top 3 factors driving the decision
5. Key risk and monitoring trigger

Format:
## Final Investment Decision: {ticker}
**Decision: [BUY/SELL] | Conviction: [High/Medium/Low] | [Maintained/Reversed]**
[Your final rationale]

200-word limit.
```

---

## Pipeline Orchestration (`run.py`)

```
async def run_pipeline(ticker: str):
    # Phase 0: Fetch all data concurrently
    quant_data, sentiment_data, technical_data = await asyncio.gather(
        fetch_quant_data(ticker),
        fetch_sentiment_data(ticker),
        fetch_technical_data(ticker)
    )

    # Phase 1: Run 3 research agents in parallel
    quant_report, sentiment_report, technical_report = await asyncio.gather(
        call_agent("grok-4.1-thinking", quant_system_prompt, quant_data),
        call_agent("glm-5", sentiment_system_prompt, sentiment_data),
        call_agent("qwen-3.5", technical_system_prompt, technical_data)
    )

    # Phase 2: Portfolio Manager decision (sequential)
    pm_decision = await call_agent("opus-4.6", pm_stage2_prompt, combined_reports)

    # Phase 3: Devil's Advocate (sequential, needs Stage 2 output)
    # DA also gets fresh data to conduct independent research
    da_report = await call_agent("sonnet-4.6", da_prompt, pm_decision + da_data)

    # Phase 4: Final decision (sequential, needs Stages 2+3)
    final_decision = await call_agent("opus-4.6", pm_stage4_prompt, pm_decision + da_report)

    # Compile and save report
    save_report(ticker, all_outputs, source_log)
```

Use `asyncio.run(run_pipeline(ticker))` from CLI entry point.

---

## Project Structure

```
investment-committee/
├── CLAUDE.md              # This file
├── run.py                 # CLI entry point and pipeline orchestrator
├── agents.py              # Agent call functions (Anthropic + OpenAI-compat)
├── data.py                # Data fetching (FMP, FRED, Scraping Dog)
├── prompts.py             # All system prompts and prompt builders
├── models.py              # Model registry and config
├── report.py              # Report compilation and markdown output
├── requirements.txt       # Dependencies
├── .env                   # API keys (gitignored)
├── .env.example           # Template for required keys
├── .gitignore
└── reports/               # Output directory for generated reports
```

---

## Output Report Format

Save to `./reports/{TICKER}_{YYYYMMDD}_{HHMMSS}.md`:

```markdown
# Investment Committee Report: {TICKER}
**Date:** {date}
**Pipeline Duration:** {seconds}s

---

## Stage 1: Research Reports

### Quantitative Valuation Research
{quant_report}

### Sentiment Research
{sentiment_report}

### Technical Signals Research
{technical_report}

---

## Stage 2: Portfolio Manager Initial Decision
{pm_stage2_decision}

---

## Stage 3: Devil's Advocate Challenge
{da_report}

---

## Stage 4: Final Investment Decision
{final_decision}

---

## Source Log
| Source | Type | URL/Endpoint |
|--------|------|-------------|
{source_log_rows}
```

---

## Source Logging

Track every external API call and search result used. Each entry should have: source name, data type, URL/endpoint, and timestamp. Accumulate throughout the pipeline and render as a table in the final report. Include both API endpoints called (FMP, FRED) and web search results returned (Scraping Dog links).

---

## `.env` File Structure

```
ANTHROPIC_API_KEY=sk-ant-...
XAI_API_KEY=xai-...
ZAI_API_KEY=...
TOGETHER_API_KEY=...
FMP_API_KEY=...
FRED_API_KEY=...
SCRAPINGDOG_API_KEY=...
```

---

## `requirements.txt`

```
anthropic>=0.52.0
openai>=1.70.0
aiohttp>=3.11.0
python-dotenv>=1.0.0
```

---

## Implementation Notes

1. **Error handling:** If a research agent fails (timeout, API error), log the error and continue the pipeline with available reports. The Portfolio Manager should note which research was missing. Set a 120-second timeout per agent call.

2. **Thinking model output cleaning:** Grok 4.1 Thinking and Qwen-3.5 may return `<think>...</think>` blocks. Strip these before passing output downstream. Regex: `re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()`

3. **Rate limiting:** Add a 1-second delay between sequential API calls to the same provider to avoid rate limits.

4. **Word count enforcement:** After each agent response, count words. If over 250 words (some buffer above 200), log a warning but do NOT truncate — let downstream agents handle verbosity.

5. **CLI interface:** Use `argparse`. Required: ticker. Optional: `--output-dir` (default `./reports`), `--verbose` flag for printing intermediate outputs to terminal.

6. **Async wrapper for sync SDKs:** The Anthropic and OpenAI Python SDKs are synchronous. Wrap calls in `asyncio.to_thread()` for the parallel stage:
   ```python
   result = await asyncio.to_thread(call_llm_sync, model_key, system_prompt, user_prompt)
   ```

7. **Progress output:** Print stage progress to terminal:
   ```
   [00:00] Starting Investment Committee analysis for AAPL...
   [00:01] Fetching market data...
   [00:03] Stage 1: Running parallel research agents...
   [00:03]   → Quantitative Valuation Researcher... ✓ (5.2s)
   [00:03]   → Sentiment Researcher... ✓ (4.8s)
   [00:03]   → Technical Signals Researcher... ✓ (6.1s)
   [00:09] Stage 2: Portfolio Manager decision...
   [00:15] Stage 3: Devil's Advocate challenge...
   [00:22] Stage 4: Final decision...
   [00:28] Report saved: ./reports/AAPL_20250222_143022.md
   ```

8. **Python version:** 3.12.7. Use modern syntax (match statements OK, f-strings, type hints with `|` union syntax).
