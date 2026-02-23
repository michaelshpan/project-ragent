"""Report generation module for Investment Committee Agent Framework."""

from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional


class ReportBuilder:
    """Build and format the investment committee report."""
    
    def __init__(self, ticker: str):
        self.ticker = ticker
        self.start_time = datetime.now()
        self.stages: Dict[str, Any] = {}
        self.source_log: List[Dict[str, str]] = []
    
    def add_stage(self, stage_name: str, content: Any):
        """Add content for a pipeline stage."""
        self.stages[stage_name] = content
    
    def set_source_log(self, sources: List[Dict[str, str]]):
        """Set the source log from data fetching."""
        self.source_log = sources
    
    def generate_markdown(self) -> str:
        """Generate the complete markdown report."""
        duration = (datetime.now() - self.start_time).total_seconds()
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        lines = [
            f"# Investment Committee Report: {self.ticker}",
            f"**Date:** {date_str}",
            f"**Pipeline Duration:** {duration:.1f}s",
            "",
            "---",
            "",
        ]
        
        # Stage 1: Research Reports
        if "research" in self.stages:
            lines.extend([
                "## Stage 1: Research Reports",
                ""
            ])
            
            research = self.stages["research"]
            if isinstance(research, dict):
                # Separate reports
                if "quant" in research:
                    lines.extend([
                        "### Quantitative Valuation Research",
                        research["quant"],
                        ""
                    ])
                if "sentiment" in research:
                    lines.extend([
                        "### Sentiment Research",
                        research["sentiment"],
                        ""
                    ])
                if "technical" in research:
                    lines.extend([
                        "### Technical Signals Research",
                        research["technical"],
                        ""
                    ])
            elif isinstance(research, (list, tuple)) and len(research) == 3:
                # Tuple of reports
                lines.extend([
                    "### Quantitative Valuation Research",
                    research[0],
                    "",
                    "### Sentiment Research",
                    research[1],
                    "",
                    "### Technical Signals Research",
                    research[2],
                    ""
                ])
            
            lines.append("---")
            lines.append("")
        
        # Stage 2: Portfolio Manager Initial Decision
        if "stage2" in self.stages:
            lines.extend([
                "## Stage 2: Portfolio Manager Initial Decision",
                self.stages["stage2"],
                "",
                "---",
                ""
            ])
        
        # Stage 3: Devil's Advocate
        if "devil_advocate" in self.stages:
            lines.extend([
                "## Stage 3: Devil's Advocate Challenge",
                self.stages["devil_advocate"],
                "",
                "---",
                ""
            ])
        
        # Stage 4: Final Decision
        if "final" in self.stages:
            lines.extend([
                "## Stage 4: Final Investment Decision",
                self.stages["final"],
                "",
                "---",
                ""
            ])
        
        # Source Log
        lines.extend([
            "## Source Log",
            "| Source | Type | URL |",
            "|--------|------|-----|"
        ])
        
        for source in self.source_log:
            source_name = source.get("source", "Unknown")
            data_type = source.get("type", "Unknown")
            url = source.get("url", "N/A")
            # Truncate long URLs for readability
            if len(url) > 60:
                url = url[:57] + "..."
            lines.append(f"| {source_name} | {data_type} | {url} |")
        
        return "\n".join(lines)


def save_research_report(ticker: str, agent_name: str, content: str, output_dir: str = "./reports/agent-research") -> Path:
    """
    Save an individual research agent report.
    
    Args:
        ticker: Stock ticker symbol
        agent_name: Name of the research agent (quant, sentiment, technical)
        content: The report content
        output_dir: Directory to save research reports
    
    Returns:
        Path to the saved report file
    """
    # Create output directory if it doesn't exist
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{ticker}_{agent_name}_{timestamp}.md"
    filepath = output_path / filename
    
    # Save report
    filepath.write_text(content)
    
    return filepath


def save_data_archive(
    ticker: str,
    quant_data: Dict[str, Any],
    sentiment_data: Dict[str, Any],
    technical_data: Dict[str, Any],
    output_dir: str = "./reports/agent-research",
) -> Path:
    """
    Archive the raw data collected for each agent into a human-readable markdown file.

    Args:
        ticker: Stock ticker symbol
        quant_data: Data dict from fetch_quant_data
        sentiment_data: Data dict from fetch_sentiment_data
        technical_data: Data dict from fetch_technical_data
        output_dir: Directory to save the archive

    Returns:
        Path to the saved archive file
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = output_path / f"{ticker}_data_archive_{timestamp}.md"

    lines = [
        f"# Data Archive: {ticker}",
        f"**Collected:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "This file contains all raw data fetched from external APIs and fed to the",
        "research agents during the investment committee pipeline run.",
        "",
        "---",
        "",
    ]

    # ── Section 1: Quantitative Data ──────────────────────────────────────
    lines.append("# 1. Quantitative Valuation Data")
    lines.append("")

    # Company profile snapshot
    profile = quant_data.get("profile", {})
    quote = quant_data.get("quote", {})
    if profile or quote:
        lines.append("## Company Snapshot")
        lines.append("")
        _append_kv_table(lines, [
            ("Company", profile.get("companyName", "N/A")),
            ("Sector", profile.get("sector", "N/A")),
            ("Industry", profile.get("industry", "N/A")),
            ("Exchange", profile.get("exchangeShortName", "N/A")),
            ("Price", _fmt_currency(quote.get("price"))),
            ("Market Cap", _fmt_large_number(quote.get("marketCap"))),
            ("P/E (TTM)", _fmt_number(quote.get("pe"))),
            ("EPS (TTM)", _fmt_currency(quote.get("eps"))),
            ("52-Week High", _fmt_currency(profile.get("yearHigh") or quote.get("yearHigh"))),
            ("52-Week Low", _fmt_currency(profile.get("yearLow") or quote.get("yearLow"))),
            ("Beta", _fmt_number(profile.get("beta"))),
        ])

    # Income statements
    income = quant_data.get("income_statements", [])
    if income:
        lines.append("## Income Statements (Annual)")
        lines.append("")
        _append_financial_table(lines, income, [
            ("Period", "date"),
            ("Revenue", "revenue", _fmt_large_number),
            ("Gross Profit", "grossProfit", _fmt_large_number),
            ("Operating Income", "operatingIncome", _fmt_large_number),
            ("Net Income", "netIncome", _fmt_large_number),
            ("EPS", "eps", _fmt_number),
            ("Gross Margin", "grossProfitRatio", _fmt_pct),
            ("Net Margin", "netIncomeRatio", _fmt_pct),
        ])

    # Balance sheet
    balance = quant_data.get("balance_sheet", [])
    if balance:
        lines.append("## Balance Sheet (Annual)")
        lines.append("")
        _append_financial_table(lines, balance, [
            ("Period", "date"),
            ("Total Assets", "totalAssets", _fmt_large_number),
            ("Total Liabilities", "totalLiabilities", _fmt_large_number),
            ("Total Equity", "totalStockholdersEquity", _fmt_large_number),
            ("Cash & Equivalents", "cashAndCashEquivalents", _fmt_large_number),
            ("Total Debt", "totalDebt", _fmt_large_number),
            ("Net Debt", "netDebt", _fmt_large_number),
        ])

    # Cash flow
    cashflow = quant_data.get("cash_flow", [])
    if cashflow:
        lines.append("## Cash Flow Statement (Annual)")
        lines.append("")
        _append_financial_table(lines, cashflow, [
            ("Period", "date"),
            ("Operating CF", "operatingCashFlow", _fmt_large_number),
            ("Investing CF", "netCashUsedForInvestingActivites", _fmt_large_number),
            ("Financing CF", "netCashUsedProvidedByFinancingActivities", _fmt_large_number),
            ("Free Cash Flow", "freeCashFlow", _fmt_large_number),
            ("CapEx", "capitalExpenditure", _fmt_large_number),
            ("SBC", "stockBasedCompensation", _fmt_large_number),
        ])

    # Ratios
    ratios = quant_data.get("ratios", [])
    if ratios:
        lines.append("## Financial Ratios (Annual)")
        lines.append("")
        _append_financial_table(lines, ratios, [
            ("Period", "date"),
            ("P/E", "priceEarningsRatio", _fmt_number),
            ("EV/EBITDA", "enterpriseValueOverEBITDA", _fmt_number),
            ("P/B", "priceToBookRatio", _fmt_number),
            ("P/S", "priceToSalesRatio", _fmt_number),
            ("ROE", "returnOnEquity", _fmt_pct),
            ("ROA", "returnOnAssets", _fmt_pct),
            ("D/E", "debtEquityRatio", _fmt_number),
            ("Current Ratio", "currentRatio", _fmt_number),
        ])

    # Key metrics
    metrics = quant_data.get("key_metrics", [])
    if metrics:
        lines.append("## Key Metrics (Annual)")
        lines.append("")
        _append_financial_table(lines, metrics, [
            ("Period", "date"),
            ("Revenue/Share", "revenuePerShare", _fmt_number),
            ("FCF/Share", "freeCashFlowPerShare", _fmt_number),
            ("Book Value/Share", "bookValuePerShare", _fmt_number),
            ("EV", "enterpriseValue", _fmt_large_number),
            ("EV/EBITDA", "evToOperatingCashFlow", _fmt_number),
            ("Dividend Yield", "dividendYield", _fmt_pct),
        ])

    # Enterprise values
    ev = quant_data.get("enterprise_values", [])
    if ev:
        lines.append("## Enterprise Values (Annual)")
        lines.append("")
        _append_financial_table(lines, ev, [
            ("Period", "date"),
            ("Market Cap", "marketCapitalization", _fmt_large_number),
            ("Enterprise Value", "enterpriseValue", _fmt_large_number),
            ("Shares Outstanding", "numberOfShares", _fmt_volume),
        ])

    # DCF valuations
    dcf = quant_data.get("dcf_valuation", {})
    adcf = quant_data.get("advanced_dcf", {})
    if dcf or adcf:
        lines.append("## DCF Valuations")
        lines.append("")
        if isinstance(dcf, list) and dcf:
            dcf = dcf[0]
        if isinstance(dcf, dict) and dcf:
            _append_kv_table(lines, [
                ("DCF Value", _fmt_currency(dcf.get("dcf"))),
                ("Current Price", _fmt_currency(dcf.get("Stock Price") or dcf.get("price"))),
            ])
        if isinstance(adcf, list) and adcf:
            adcf = adcf[0]
        if isinstance(adcf, dict) and adcf:
            _append_kv_table(lines, [
                ("Advanced Levered DCF", _fmt_currency(adcf.get("dcf") or adcf.get("leveredDCF"))),
            ])

    # Financial health scores
    scores = quant_data.get("financial_scores", {})
    if isinstance(scores, list) and scores:
        scores = scores[0]
    if isinstance(scores, dict) and scores:
        lines.append("## Financial Health Scores")
        lines.append("")
        _append_kv_table(lines, [
            ("Altman Z-Score", _fmt_number(scores.get("altmanZScore"))),
            ("Piotroski Score", _fmt_number(scores.get("piotroskiScore"))),
        ])

    # Analyst estimates
    estimates = quant_data.get("analyst_estimates", [])
    if estimates:
        lines.append("## Analyst Estimates")
        lines.append("")
        data_list = estimates if isinstance(estimates, list) else [estimates]
        _append_financial_table(lines, data_list[:3], [
            ("Period", "date"),
            ("Est. Revenue (Avg)", "estimatedRevenueAvg", _fmt_large_number),
            ("Est. Revenue (Low)", "estimatedRevenueLow", _fmt_large_number),
            ("Est. Revenue (High)", "estimatedRevenueHigh", _fmt_large_number),
            ("Est. EPS (Avg)", "estimatedEpsAvg", _fmt_number),
            ("Est. EPS (Low)", "estimatedEpsLow", _fmt_number),
            ("Est. EPS (High)", "estimatedEpsHigh", _fmt_number),
        ])

    # Price targets
    pt = quant_data.get("price_targets", {})
    if isinstance(pt, list) and pt:
        pt = pt[0]
    if isinstance(pt, dict) and pt:
        lines.append("## Price Target Summary")
        lines.append("")
        _append_kv_table(lines, [
            ("Current", _fmt_currency(pt.get("lastPrice"))),
            ("Average Target", _fmt_currency(pt.get("priceTargetAverage") or pt.get("averagePriceTarget"))),
            ("High Target", _fmt_currency(pt.get("priceTargetHigh") or pt.get("highPriceTarget"))),
            ("Low Target", _fmt_currency(pt.get("priceTargetLow") or pt.get("lowPriceTarget"))),
        ])

    # Macro data
    macro = quant_data.get("macro", {})
    if macro:
        lines.append("## Macroeconomic Context")
        lines.append("")
        _append_kv_table(lines, [
            ("Fed Funds Rate", f"{macro.get('fed_funds_rate', 0):.2f}%"),
            ("10Y-2Y Yield Spread", f"{macro.get('yield_spread', 0):.2f}%"),
            ("VIX", _fmt_number(macro.get("vix"))),
        ])

    # Sector / Industry PE comparison (new MCP data)
    sector_pe = quant_data.get("sector_pe", {})
    industry_pe = quant_data.get("industry_pe", {})
    if sector_pe or industry_pe:
        lines.append("## Sector & Industry PE Comparison")
        lines.append("")
        if isinstance(sector_pe, list) and sector_pe:
            profile_sector = (quant_data.get("profile") or {}).get("sector", "")
            for s in sector_pe:
                if isinstance(s, dict) and s.get("sector", "").lower() == profile_sector.lower():
                    _append_kv_table(lines, [
                        ("Sector", s.get("sector", "N/A")),
                        ("Sector PE", _fmt_number(s.get("pe"))),
                        ("Date", s.get("date", "N/A")),
                    ])
                    break
        elif isinstance(sector_pe, dict) and sector_pe:
            _append_kv_table(lines, [(k, str(v)) for k, v in sector_pe.items()])
        if isinstance(industry_pe, list) and industry_pe:
            profile_industry = (quant_data.get("profile") or {}).get("industry", "")
            for s in industry_pe:
                if isinstance(s, dict) and s.get("industry", "").lower() == profile_industry.lower():
                    _append_kv_table(lines, [
                        ("Industry", s.get("industry", "N/A")),
                        ("Industry PE", _fmt_number(s.get("pe"))),
                        ("Date", s.get("date", "N/A")),
                    ])
                    break
        elif isinstance(industry_pe, dict) and industry_pe:
            _append_kv_table(lines, [(k, str(v)) for k, v in industry_pe.items()])

    # Revenue Product Segmentation (new MCP data)
    rev_seg = quant_data.get("revenue_product_segmentation", {})
    if rev_seg:
        lines.append("## Revenue Product Segmentation")
        lines.append("")
        seg_list = rev_seg if isinstance(rev_seg, list) else [rev_seg]
        for seg_entry in seg_list[:3]:
            if isinstance(seg_entry, dict):
                for key, val in seg_entry.items():
                    if isinstance(val, dict):
                        lines.append(f"**{key}:**")
                        lines.append("")
                        _append_kv_table(lines, [
                            (prod, _fmt_large_number(amount)) for prod, amount in val.items()
                        ])
                        break

    # ── Section 2: Sentiment Data ─────────────────────────────────────────
    lines.append("---")
    lines.append("")
    lines.append("# 2. Sentiment Data")
    lines.append("")

    est = sentiment_data.get("analyst_estimates", {})
    if est:
        lines.append("## Market Overview")
        lines.append("")
        _append_kv_table(lines, [
            ("Price", _fmt_currency(est.get("price"))),
            ("Market Cap", _fmt_large_number(est.get("marketCap"))),
            ("Beta", _fmt_number(est.get("beta"))),
        ])

    # Analyst Grades Summary (new MCP data)
    grades = sentiment_data.get("grades_summary", {})
    if isinstance(grades, list) and grades:
        grades = grades[0]
    if isinstance(grades, dict) and grades:
        lines.append("## Analyst Grades Summary")
        lines.append("")
        _append_kv_table(lines, [
            ("Strong Buy", str(grades.get("strongBuy", "N/A"))),
            ("Buy", str(grades.get("buy", "N/A"))),
            ("Hold", str(grades.get("hold", "N/A"))),
            ("Sell", str(grades.get("sell", "N/A"))),
            ("Strong Sell", str(grades.get("strongSell", "N/A"))),
        ])

    # Price Target Consensus (new MCP data)
    ptc = sentiment_data.get("price_target_consensus", {})
    if isinstance(ptc, list) and ptc:
        ptc = ptc[0]
    if isinstance(ptc, dict) and ptc:
        lines.append("## Price Target Consensus")
        lines.append("")
        _append_kv_table(lines, [
            ("Consensus", _fmt_currency(ptc.get("targetConsensus") or ptc.get("priceTargetAverage"))),
            ("High", _fmt_currency(ptc.get("targetHigh") or ptc.get("priceTargetHigh"))),
            ("Low", _fmt_currency(ptc.get("targetLow") or ptc.get("priceTargetLow"))),
            ("Median", _fmt_currency(ptc.get("targetMedian"))),
        ])

    # Insider Trade Statistics (new MCP data)
    insider = sentiment_data.get("insider_trade_statistics", {})
    if isinstance(insider, list) and insider:
        insider = insider[0]
    if isinstance(insider, dict) and insider:
        lines.append("## Insider Trade Statistics")
        lines.append("")
        pairs = [(k, str(v)) for k, v in insider.items() if v is not None]
        if pairs:
            _append_kv_table(lines, pairs)

    # Stock News (new MCP data)
    stock_news = sentiment_data.get("stock_news", [])
    if stock_news:
        lines.append("## Recent Stock News (FMP)")
        lines.append("")
        lines.append(f"**{len(stock_news)} articles**")
        lines.append("")
        for j, item in enumerate(stock_news[:10], 1):
            title = item.get("title") or item.get("text", "Untitled")
            url = item.get("url") or item.get("link", "")
            date = item.get("publishedDate", item.get("date", ""))
            if date:
                date = str(date)[:10]
            lines.append(f"**{j}. [{title}]({url})** ({date})")
            snippet = item.get("text", "")
            if snippet and snippet != title:
                if len(snippet) > 200:
                    snippet = snippet[:197] + "..."
                lines.append(f"> {snippet}")
            lines.append("")

    # Press Releases (new MCP data)
    press = sentiment_data.get("press_releases", [])
    if press:
        lines.append("## Press Releases (FMP)")
        lines.append("")
        for j, item in enumerate(press[:5], 1):
            title = item.get("title", "Untitled")
            date = item.get("date", "")
            if date:
                date = str(date)[:10]
            lines.append(f"**{j}. {title}** ({date})")
            text = item.get("text", "")
            if text:
                if len(text) > 300:
                    text = text[:297] + "..."
                lines.append(f"> {text}")
            lines.append("")

    for section_key, section_title in [
        ("analyst_ratings", "Analyst Ratings Search Results"),
        ("news_sentiment", "News Sentiment Search Results"),
        ("risks", "Risks & Headwinds Search Results"),
    ]:
        items = sentiment_data.get(section_key, [])
        lines.append(f"## {section_title}")
        lines.append("")
        if not items:
            lines.append("*No results returned.*")
            lines.append("")
        else:
            lines.append(f"**{len(items)} results**")
            lines.append("")
            for j, item in enumerate(items, 1):
                title = item.get("title", "Untitled")
                link = item.get("link", "")
                snippet = item.get("snippet", "")
                lines.append(f"**{j}. [{title}]({link})**")
                if snippet:
                    lines.append(f"> {snippet}")
                lines.append("")

    # ── Section 3: Technical Data ─────────────────────────────────────────
    lines.append("---")
    lines.append("")
    lines.append("# 3. Technical Signals Data")
    lines.append("")

    lines.append("## Indicators")
    lines.append("")
    _append_kv_table(lines, [
        ("Current Price", _fmt_currency(technical_data.get("current_price"))),
        ("RSI (14)", _fmt_number(technical_data.get("rsi_14"))),
        ("SMA 50", _fmt_currency(technical_data.get("sma_50"))),
        ("SMA 200", _fmt_currency(technical_data.get("sma_200"))),
        ("EMA 20", _fmt_currency(technical_data.get("ema_20"))),
        ("SMA 50 vs 200", technical_data.get("sma_50_vs_200", "N/A")),
        ("52-Week High", _fmt_currency(technical_data.get("year_high"))),
        ("52-Week Low", _fmt_currency(technical_data.get("year_low"))),
        ("Historical Days Available", str(technical_data.get("historical_prices_available", 0))),
    ])

    lines.append("## Price Changes")
    lines.append("")
    changes = technical_data.get("price_changes", {})
    if changes:
        _append_kv_table(lines, [
            (period, f"{val:+.2f}%") for period, val in changes.items()
        ])
    else:
        lines.append("*No price change data available.*")
        lines.append("")

    lines.append("## Volume")
    lines.append("")
    _append_kv_table(lines, [
        ("Latest Volume", _fmt_volume(technical_data.get("latest_volume"))),
        ("20-Day Avg Volume", _fmt_volume(technical_data.get("avg_volume_20d"))),
        ("Volume Trend", technical_data.get("volume_trend", "N/A")),
    ])

    sr = technical_data.get("support_resistance", {})
    if sr and sr.get("resistance_90d"):
        lines.append("## Support & Resistance")
        lines.append("")
        _append_kv_table(lines, [
            ("30-Day Resistance", _fmt_currency(sr.get("resistance_30d"))),
            ("30-Day Support", _fmt_currency(sr.get("support_30d"))),
            ("90-Day Resistance", _fmt_currency(sr.get("resistance_90d"))),
            ("90-Day Support", _fmt_currency(sr.get("support_90d"))),
        ])

    recent = technical_data.get("recent_prices", [])
    if recent:
        lines.append("## Recent Price Action (Last 10 Days)")
        lines.append("")
        lines.append("| Date | Open | High | Low | Close | Volume |")
        lines.append("|------|------|------|-----|-------|--------|")
        for day in recent:
            lines.append(
                f"| {day.get('date', '')} "
                f"| {_fmt_currency(day.get('open'))} "
                f"| {_fmt_currency(day.get('high'))} "
                f"| {_fmt_currency(day.get('low'))} "
                f"| {_fmt_currency(day.get('close'))} "
                f"| {_fmt_volume(day.get('volume'))} |"
            )
        lines.append("")

    filepath.write_text("\n".join(lines))
    return filepath


# ── Formatting helpers ────────────────────────────────────────────────────

def _fmt_currency(val) -> str:
    """Format a value as currency."""
    if val is None:
        return "N/A"
    try:
        v = float(val)
        return f"${v:,.2f}"
    except (TypeError, ValueError):
        return str(val)


def _fmt_number(val) -> str:
    """Format a numeric value with two decimal places."""
    if val is None:
        return "N/A"
    try:
        v = float(val)
        return f"{v:,.2f}"
    except (TypeError, ValueError):
        return str(val)


def _fmt_pct(val) -> str:
    """Format a decimal ratio as a percentage (0.25 → 25.00%)."""
    if val is None:
        return "N/A"
    try:
        v = float(val)
        return f"{v * 100:.2f}%"
    except (TypeError, ValueError):
        return str(val)


def _fmt_large_number(val, prefix: str = "$") -> str:
    """Format a large number with abbreviated suffix (B, M, K)."""
    if val is None or val == 0:
        return "N/A"
    try:
        v = float(val)
    except (TypeError, ValueError):
        return str(val)
    abs_v = abs(v)
    sign = "-" if v < 0 else ""
    if abs_v >= 1_000_000_000_000:
        return f"{sign}{prefix}{abs_v / 1_000_000_000_000:,.2f}T"
    if abs_v >= 1_000_000_000:
        return f"{sign}{prefix}{abs_v / 1_000_000_000:,.2f}B"
    if abs_v >= 1_000_000:
        return f"{sign}{prefix}{abs_v / 1_000_000:,.2f}M"
    if abs_v >= 1_000:
        return f"{sign}{prefix}{abs_v / 1_000:,.1f}K"
    return f"{sign}{prefix}{abs_v:,.0f}"


def _fmt_volume(val) -> str:
    """Format a volume number (no currency prefix)."""
    return _fmt_large_number(val, prefix="")


def _append_kv_table(lines: List[str], pairs: List[tuple]):
    """Append a two-column key-value table to lines."""
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    for label, value in pairs:
        lines.append(f"| {label} | {value} |")
    lines.append("")


def _append_financial_table(
    lines: List[str],
    rows: list,
    columns: list,
):
    """
    Append a multi-period financial table.

    columns is a list of tuples:
        (header, dict_key)  or  (header, dict_key, formatter_fn)
    """
    if not rows:
        lines.append("*No data available.*")
        lines.append("")
        return

    # Limit to latest 5 periods
    rows = rows[:5]

    headers = [c[0] for c in columns]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["------"] * len(headers)) + "|")

    for row in rows:
        if not isinstance(row, dict):
            continue
        cells = []
        for col in columns:
            key = col[1]
            fmt = col[2] if len(col) > 2 else str
            raw = row.get(key)
            if raw is None:
                cells.append("N/A")
            else:
                try:
                    cells.append(fmt(raw))
                except Exception:
                    cells.append(str(raw))
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")


def save_report(builder: ReportBuilder, output_dir: str = "./reports") -> Path:
    """
    Save the report to a markdown file.
    
    Args:
        builder: The ReportBuilder instance with all content
        output_dir: Directory to save reports (default: ./reports)
    
    Returns:
        Path to the saved report file
    """
    # Create output directory if it doesn't exist
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{builder.ticker}_{timestamp}.md"
    filepath = output_path / filename
    
    # Generate and save report
    markdown = builder.generate_markdown()
    filepath.write_text(markdown)
    
    return filepath


def format_progress_message(elapsed: float, stage: str, status: str = "running") -> str:
    """
    Format a progress message for terminal output.
    
    Args:
        elapsed: Elapsed time in seconds
        stage: Current stage description
        status: Status indicator (running, complete, error)
    
    Returns:
        Formatted progress message
    """
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)
    time_str = f"[{minutes:02d}:{seconds:02d}]"
    
    status_icon = {
        "running": "⏳",
        "complete": "✓",
        "error": "❌"
    }.get(status, "")
    
    return f"{time_str} {stage}... {status_icon}"


def print_stage_progress(start_time: datetime, message: str, indent: int = 0):
    """Print formatted progress message to terminal."""
    elapsed = (datetime.now() - start_time).total_seconds()
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)
    time_str = f"[{minutes:02d}:{seconds:02d}]"
    
    indent_str = "  " * indent
    print(f"{time_str} {indent_str}{message}")