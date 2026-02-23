"""Curation layer: converts raw data dicts into concise analyst-readable text summaries."""

from typing import Any


# ── Shared helpers ────────────────────────────────────────────────────────────


def _safe_get(d: dict | list | None, *keys, default=None) -> Any:
    """Safely traverse nested dicts/lists."""
    current = d
    for key in keys:
        if current is None:
            return default
        if isinstance(current, dict):
            current = current.get(key)
        elif isinstance(current, list):
            try:
                current = current[key]
            except (IndexError, TypeError):
                return default
        else:
            return default
    return current if current is not None else default


def _fmt_big(val, prefix: str = "$") -> str:
    """Format large numbers with abbreviated suffix."""
    if val is None:
        return "N/A"
    try:
        v = float(val)
    except (TypeError, ValueError):
        return str(val)
    if v == 0:
        return f"{prefix}0"
    sign = "-" if v < 0 else ""
    abs_v = abs(v)
    if abs_v >= 1e12:
        return f"{sign}{prefix}{abs_v / 1e12:.2f}T"
    if abs_v >= 1e9:
        return f"{sign}{prefix}{abs_v / 1e9:.2f}B"
    if abs_v >= 1e6:
        return f"{sign}{prefix}{abs_v / 1e6:.1f}M"
    if abs_v >= 1e3:
        return f"{sign}{prefix}{abs_v / 1e3:.1f}K"
    return f"{sign}{prefix}{abs_v:.0f}"


def _fmt_pct(val) -> str:
    """Format a value as percentage. Handles both ratio (0.25) and already-percent (25) forms."""
    if val is None:
        return "N/A"
    try:
        v = float(val)
    except (TypeError, ValueError):
        return str(val)
    # If it looks like a ratio (between -1 and 1 exclusive, but not 0), convert to pct
    if -1 < v < 1 and v != 0:
        return f"{v * 100:+.1f}%"
    return f"{v:+.1f}%"


def _fmt_num(val, decimals: int = 2) -> str:
    """Format a numeric value."""
    if val is None:
        return "N/A"
    try:
        v = float(val)
        return f"{v:,.{decimals}f}"
    except (TypeError, ValueError):
        return str(val)


def _fmt_price(val) -> str:
    """Format a price value."""
    if val is None:
        return "N/A"
    try:
        return f"${float(val):,.2f}"
    except (TypeError, ValueError):
        return str(val)


def _first(data, default=None):
    """Extract first element if data is a list, otherwise return as-is."""
    if isinstance(data, list):
        return data[0] if data else (default or {})
    return data if data is not None else (default or {})


# ── Quant Summary ─────────────────────────────────────────────────────────────


def curate_quant_summary(data: dict) -> str:
    """Curate quantitative data into a concise analyst-readable summary (~300-500 tokens)."""
    ticker = data.get("ticker", "???")
    quote = _first(data.get("quote", {}))
    profile = _first(data.get("profile", {}))
    ratios = data.get("ratios", [])
    latest_ratios = _first(ratios)
    key_metrics = data.get("key_metrics", [])
    latest_km = _first(key_metrics)
    income = data.get("income_statements", [])
    balance = data.get("balance_sheet", [])
    cash_flow = data.get("cash_flow", [])
    ev_data = data.get("enterprise_values", [])
    latest_ev = _first(ev_data)
    growth = _first(data.get("growth", {}))
    dcf = _first(data.get("dcf_valuation", {}))
    adcf = _first(data.get("advanced_dcf", {}))
    scores = _first(data.get("financial_scores", {}))
    estimates = data.get("analyst_estimates", [])
    latest_est = _first(estimates) if isinstance(estimates, list) else estimates
    pt = _first(data.get("price_targets", {}))
    macro = data.get("macro", {})
    sector_pe = data.get("sector_pe", {})
    industry_pe = data.get("industry_pe", {})
    rev_seg = data.get("revenue_product_segmentation", {})

    lines = []

    # Header
    price = quote.get("price") or profile.get("price")
    mcap = quote.get("marketCap") or profile.get("marketCap")
    pe = quote.get("pe") or latest_ratios.get("priceEarningsRatio")
    ev_ebitda = latest_ratios.get("enterpriseValueOverEBITDA")
    lines.append(f"### {ticker} — Quantitative Snapshot")
    lines.append(f"Price: {_fmt_price(price)} | MCap: {_fmt_big(mcap)} | P/E: {_fmt_num(pe)} | EV/EBITDA: {_fmt_num(ev_ebitda)}")
    lines.append(f"Sector: {profile.get('sector', 'N/A')} | Industry: {profile.get('industry', 'N/A')}")

    # Sector/Industry PE comparison
    if sector_pe or industry_pe:
        parts = []
        if isinstance(sector_pe, list) and sector_pe:
            sector_name = profile.get("sector", "")
            for s in sector_pe:
                if s.get("sector", "").lower() == sector_name.lower():
                    parts.append(f"Sector PE: {_fmt_num(s.get('pe'))}")
                    break
        elif isinstance(sector_pe, dict) and sector_pe.get("pe"):
            parts.append(f"Sector PE: {_fmt_num(sector_pe.get('pe'))}")
        if isinstance(industry_pe, list) and industry_pe:
            ind_name = profile.get("industry", "")
            for s in industry_pe:
                if s.get("industry", "").lower() == ind_name.lower():
                    parts.append(f"Industry PE: {_fmt_num(s.get('pe'))}")
                    break
        elif isinstance(industry_pe, dict) and industry_pe.get("pe"):
            parts.append(f"Industry PE: {_fmt_num(industry_pe.get('pe'))}")
        if parts:
            lines.append("Peer Comparison: " + " | ".join(parts))

    # Revenue trend (3Y)
    if income and len(income) >= 2:
        lines.append("")
        lines.append("Revenue Trend (Annual):")
        for stmt in income[:3]:
            yr = str(stmt.get("date", stmt.get("calendarYear", "?")))[:4]
            rev = stmt.get("revenue")
            ni = stmt.get("netIncome")
            gm = stmt.get("grossProfitRatio")
            nm = stmt.get("netIncomeRatio")
            lines.append(f"  {yr}: Rev {_fmt_big(rev)} | NI {_fmt_big(ni)} | GM {_fmt_pct(gm)} | NM {_fmt_pct(nm)}")

    # Balance sheet highlights
    latest_bs = _first(balance) if balance else {}
    latest_cf = _first(cash_flow) if cash_flow else {}
    if latest_bs or latest_cf:
        lines.append("")
        lines.append("Balance Sheet & Cash Flow:")
        fcf = latest_cf.get("freeCashFlow")
        de = latest_ratios.get("debtEquityRatio")
        cr = latest_ratios.get("currentRatio")
        nd = latest_bs.get("netDebt")
        lines.append(f"  FCF: {_fmt_big(fcf)} | D/E: {_fmt_num(de)} | Current Ratio: {_fmt_num(cr)} | Net Debt: {_fmt_big(nd)}")

    # DCF valuation
    dcf_val = dcf.get("dcf") if isinstance(dcf, dict) else None
    adcf_val = (adcf.get("dcf") or adcf.get("leveredDCF")) if isinstance(adcf, dict) else None
    if dcf_val or adcf_val:
        lines.append("")
        parts = []
        if dcf_val:
            parts.append(f"DCF: {_fmt_price(dcf_val)}")
        if adcf_val:
            parts.append(f"Levered DCF: {_fmt_price(adcf_val)}")
        if price:
            try:
                ref = float(dcf_val or adcf_val)
                p = float(price)
                upside = ((ref - p) / p) * 100
                parts.append(f"Implied upside: {upside:+.1f}%")
            except (TypeError, ValueError):
                pass
        lines.append("DCF Valuation: " + " | ".join(parts))

    # Financial scores
    if isinstance(scores, dict) and scores:
        az = scores.get("altmanZScore")
        pi = scores.get("piotroskiScore")
        if az is not None or pi is not None:
            lines.append(f"Scores: Altman-Z: {_fmt_num(az)} | Piotroski: {_fmt_num(pi, 0)}")

    # Analyst consensus
    if isinstance(latest_est, dict) and latest_est:
        avg_eps = latest_est.get("estimatedEpsAvg")
        avg_rev = latest_est.get("estimatedRevenueAvg")
        if avg_eps or avg_rev:
            lines.append("")
            lines.append(f"Analyst Consensus: EPS Est {_fmt_num(avg_eps)} | Rev Est {_fmt_big(avg_rev)}")
    if isinstance(pt, dict) and pt:
        avg_pt = pt.get("priceTargetAverage") or pt.get("averagePriceTarget") or pt.get("targetConsensus")
        high_pt = pt.get("priceTargetHigh") or pt.get("highPriceTarget") or pt.get("targetHigh")
        low_pt = pt.get("priceTargetLow") or pt.get("lowPriceTarget") or pt.get("targetLow")
        if avg_pt:
            parts = [f"Avg PT: {_fmt_price(avg_pt)}"]
            if high_pt:
                parts.append(f"High: {_fmt_price(high_pt)}")
            if low_pt:
                parts.append(f"Low: {_fmt_price(low_pt)}")
            if price:
                try:
                    upside = ((float(avg_pt) - float(price)) / float(price)) * 100
                    parts.append(f"Upside: {upside:+.1f}%")
                except (TypeError, ValueError):
                    pass
            lines.append("Price Targets: " + " | ".join(parts))

    # Revenue segmentation
    if rev_seg:
        seg_list = rev_seg if isinstance(rev_seg, list) else [rev_seg]
        if seg_list and isinstance(seg_list[0], dict):
            lines.append("")
            lines.append("Revenue Segmentation:")
            # Take the most recent period
            latest_seg = seg_list[0]
            # Some formats have nested segments
            for key, val in latest_seg.items():
                if isinstance(val, dict):
                    for prod, amount in val.items():
                        lines.append(f"  {prod}: {_fmt_big(amount)}")
                    break

    # Macro
    if macro:
        lines.append("")
        ffr = macro.get("fed_funds_rate", 0)
        ys = macro.get("yield_spread", 0)
        vix = macro.get("vix", 0)
        lines.append(f"Macro: FFR {ffr:.2f}% | 10Y-2Y Spread {ys:.2f}% | VIX {_fmt_num(vix, 1)}")

    return "\n".join(lines)


# ── Sentiment Summary ─────────────────────────────────────────────────────────


def curate_sentiment_summary(data: dict) -> str:
    """Curate sentiment data into a concise analyst-readable summary (~400-600 tokens)."""
    ticker = data.get("ticker", "???")
    lines = []
    lines.append(f"### {ticker} — Sentiment & Analyst Overview")

    # Market overview from analyst_estimates or profile
    est = data.get("analyst_estimates", {})
    if isinstance(est, dict) and est:
        price = est.get("price")
        mcap = est.get("marketCap")
        beta = est.get("beta")
        parts = []
        if price:
            parts.append(f"Price: {_fmt_price(price)}")
        if mcap:
            parts.append(f"MCap: {_fmt_big(mcap)}")
        if beta:
            parts.append(f"Beta: {_fmt_num(beta)}")
        if parts:
            lines.append(" | ".join(parts))

    # Analyst grade distribution (new MCP data)
    grades = data.get("grades_summary", {})
    if isinstance(grades, list) and grades:
        grades = grades[0]
    if isinstance(grades, dict) and grades:
        lines.append("")
        lines.append("Analyst Grades:")
        buy = grades.get("strongBuy", 0) or 0
        sb = grades.get("buy", 0) or 0
        hold = grades.get("hold", 0) or 0
        sell = grades.get("sell", 0) or 0
        ss = grades.get("strongSell", 0) or 0
        total = buy + sb + hold + sell + ss
        lines.append(f"  Strong Buy: {buy} | Buy: {sb} | Hold: {hold} | Sell: {sell} | Strong Sell: {ss} (Total: {total})")
        if total > 0:
            bullish_pct = ((buy + sb) / total) * 100
            lines.append(f"  Bullish consensus: {bullish_pct:.0f}%")

    # Price target consensus (new MCP data)
    ptc = data.get("price_target_consensus", {})
    if isinstance(ptc, list) and ptc:
        ptc = ptc[0]
    if isinstance(ptc, dict) and ptc:
        avg_pt = ptc.get("targetConsensus") or ptc.get("priceTargetAverage")
        high = ptc.get("targetHigh") or ptc.get("priceTargetHigh")
        low = ptc.get("targetLow") or ptc.get("priceTargetLow")
        if avg_pt:
            lines.append(f"  PT Consensus: Avg {_fmt_price(avg_pt)} | High {_fmt_price(high)} | Low {_fmt_price(low)}")

    # Insider trading stats (new MCP data)
    insider = data.get("insider_trade_statistics", {})
    if isinstance(insider, list) and insider:
        insider = insider[0]
    if isinstance(insider, dict) and insider:
        lines.append("")
        lines.append("Insider Trading (Recent):")
        buys = insider.get("totalBought") or insider.get("buyCount") or insider.get("totalBuying", 0)
        sells = insider.get("totalSold") or insider.get("sellCount") or insider.get("totalSelling", 0)
        lines.append(f"  Buys: {buys} | Sells: {sells}")

    # Stock news headlines (new MCP data)
    news = data.get("stock_news", [])
    if news:
        lines.append("")
        lines.append("Recent Headlines:")
        for item in news[:5]:
            title = item.get("title") or item.get("text", "")
            date = item.get("publishedDate", item.get("date", ""))
            if date:
                date = str(date)[:10]
            if title:
                lines.append(f"  [{date}] {title}")

    # Press releases (new MCP data)
    pr = data.get("press_releases", [])
    if pr:
        lines.append("")
        lines.append("Recent Press Releases:")
        for item in pr[:3]:
            title = item.get("title", "")
            date = item.get("date", "")
            if date:
                date = str(date)[:10]
            if title:
                lines.append(f"  [{date}] {title}")

    # Scraping Dog search results (condensed)
    for section_key, section_title in [
        ("analyst_ratings", "Analyst Rating Signals"),
        ("news_sentiment", "News Sentiment Signals"),
        ("risks", "Risk/Headwind Signals"),
    ]:
        items = data.get(section_key, [])
        if items:
            lines.append("")
            lines.append(f"{section_title}:")
            for item in items[:5]:
                snippet = item.get("snippet", "")
                if snippet:
                    # Truncate long snippets
                    if len(snippet) > 120:
                        snippet = snippet[:117] + "..."
                    lines.append(f"  - {snippet}")

    return "\n".join(lines)


# ── Technical Summary ─────────────────────────────────────────────────────────


def curate_technical_summary(data: dict) -> str:
    """Curate technical data into a concise analyst-readable summary (~200-400 tokens)."""
    ticker = data.get("ticker", "???")
    lines = []
    lines.append(f"### {ticker} — Technical Signals")

    # Core indicators
    price = data.get("current_price")
    rsi = data.get("rsi_14")
    sma50 = data.get("sma_50")
    sma200 = data.get("sma_200")
    ema20 = data.get("ema_20")
    crossover = data.get("sma_50_vs_200", "N/A")

    lines.append(f"Price: {_fmt_price(price)} | RSI(14): {_fmt_num(rsi)} | SMA50: {_fmt_price(sma50)} | SMA200: {_fmt_price(sma200)}")
    if ema20:
        lines.append(f"EMA(20): {_fmt_price(ema20)}")
    lines.append(f"Crossover Signal: {crossover}")

    # RSI interpretation
    if rsi is not None:
        try:
            rsi_val = float(rsi)
            if rsi_val > 70:
                lines.append("RSI Signal: OVERBOUGHT (>70)")
            elif rsi_val < 30:
                lines.append("RSI Signal: OVERSOLD (<30)")
            else:
                lines.append(f"RSI Signal: Neutral ({rsi_val:.0f})")
        except (TypeError, ValueError):
            pass

    # Momentum
    changes = data.get("price_changes", {})
    if changes:
        lines.append("")
        lines.append("Momentum:")
        parts = []
        for period in ["1D", "5D", "1M", "3M", "6M", "1Y"]:
            val = changes.get(period)
            if val is not None:
                parts.append(f"{period}: {val:+.1f}%")
        if parts:
            lines.append("  " + " | ".join(parts))

    # Volume
    latest_vol = data.get("latest_volume")
    avg_vol = data.get("avg_volume_20d")
    vol_trend = data.get("volume_trend", "N/A")
    if latest_vol or avg_vol:
        lines.append("")
        lines.append(f"Volume: Latest {_fmt_big(latest_vol, '')} | 20D Avg {_fmt_big(avg_vol, '')} | Trend: {vol_trend}")

    # Support/resistance
    sr = data.get("support_resistance", {})
    if sr and sr.get("resistance_30d"):
        lines.append("")
        lines.append(f"Support/Resistance (30D): S {_fmt_price(sr.get('support_30d'))} — R {_fmt_price(sr.get('resistance_30d'))}")
        lines.append(f"Support/Resistance (90D): S {_fmt_price(sr.get('support_90d'))} — R {_fmt_price(sr.get('resistance_90d'))}")

    # 52-week range
    yh = data.get("year_high")
    yl = data.get("year_low")
    if yh and yl:
        try:
            p = float(price) if price else 0
            h = float(yh)
            l = float(yl)
            pct_from_high = ((p - h) / h) * 100 if h else 0
            range_pos = ((p - l) / (h - l)) * 100 if (h - l) else 0
            lines.append(f"52W Range: {_fmt_price(yl)} — {_fmt_price(yh)} | From High: {pct_from_high:+.1f}% | Range Position: {range_pos:.0f}%")
        except (TypeError, ValueError):
            lines.append(f"52W Range: {_fmt_price(yl)} — {_fmt_price(yh)}")

    # Recent OHLCV (last 5 days)
    recent = data.get("recent_prices", [])
    if recent:
        lines.append("")
        lines.append("Last 5 Days:")
        lines.append("  Date       | Open    | High    | Low     | Close   | Volume")
        for day in recent[:5]:
            d = day.get("date", "")[:10]
            o = _fmt_price(day.get("open"))
            h = _fmt_price(day.get("high"))
            lo = _fmt_price(day.get("low"))
            c = _fmt_price(day.get("close"))
            v = _fmt_big(day.get("volume"), "")
            lines.append(f"  {d} | {o:>7} | {h:>7} | {lo:>7} | {c:>7} | {v}")

    return "\n".join(lines)


# ── Devil's Advocate Summary ──────────────────────────────────────────────────


def curate_da_summary(quant_data: dict, sentiment_data: dict, technical_data: dict) -> str:
    """Concatenate all three curated summaries for the Devil's Advocate."""
    sections = []
    sections.append("## Independent Research Data")
    sections.append("")
    sections.append(curate_quant_summary(quant_data))
    sections.append("")
    sections.append("---")
    sections.append("")
    sections.append(curate_sentiment_summary(sentiment_data))
    sections.append("")
    sections.append("---")
    sections.append("")
    sections.append(curate_technical_summary(technical_data))
    return "\n".join(sections)
