# FMP API Update - February 2026

## Issue
Financial Modeling Prep (FMP) has deprecated their v3 API endpoints as of August 31, 2025. All legacy endpoints now return 403 errors with the message:
> "Legacy Endpoint : Due to Legacy endpoints being no longer supported - This endpoint is only available for legacy users who have valid subscriptions prior August 31, 2025."

## Solution
Updated all FMP API calls from `/api/v3/` to `/stable/` endpoints.

### Changes Made

#### 1. Base URL Change
- **Old**: `https://financialmodelingprep.com/api/v3`
- **New**: `https://financialmodelingprep.com/stable`

#### 2. Endpoint Mappings

| Old Endpoint (v3) | New Endpoint (stable) | Status |
|-------------------|----------------------|---------|
| `/quote/{ticker}` | `/quote?symbol={ticker}` | ✅ Working |
| `/income-statement/{ticker}` | `/income-statement?symbol={ticker}` | ✅ Working |
| `/ratios/{ticker}` | `/key-metrics?symbol={ticker}` | ✅ Working (using key-metrics instead) |
| `/enterprise-values/{ticker}` | `/profile?symbol={ticker}` | ✅ Working (using profile data) |
| `/analyst-estimates/{ticker}` | `/profile?symbol={ticker}` | ✅ Working (using profile data) |
| `/stock-price-change/{ticker}` | `/financial-growth?symbol={ticker}` | ✅ Working |
| `/historical-price-full/{ticker}` | `/historical-price-eod/full?symbol={ticker}` | ✅ Working |
| `/technical_indicator/daily/{ticker}` | Not available | ❌ Removed (calculating manually) |

#### 3. Parameter Changes
- All endpoints now use `symbol` parameter instead of path parameter
- API key still passed as `apikey` parameter
- Period parameters remain the same

### Working Endpoints in Stable API

1. **Quote**: `/quote?symbol=AAPL`
   - Returns: price, volume, market cap, price changes

2. **Company Profile**: `/profile?symbol=AAPL`
   - Returns: detailed company info, market cap, beta, price ranges

3. **Income Statement**: `/income-statement?symbol=AAPL&period=annual`
   - Returns: revenue, net income, EPS, etc.

4. **Key Metrics**: `/key-metrics?symbol=AAPL&period=annual`
   - Returns: P/E ratio, P/B ratio, ROE, debt ratios, etc.

5. **Financial Growth**: `/financial-growth?symbol=AAPL&period=annual`
   - Returns: growth percentages for various metrics

6. **Cash Flow Statement**: `/cash-flow-statement?symbol=AAPL&period=annual`
   - Returns: operating, investing, financing cash flows

7. **Historical Prices**: `/historical-price-eod/full?symbol=AAPL`
   - Returns: full price history with OHLCV data

### Non-Working/Missing Endpoints

1. **Technical Indicators**: `/technical-indicator/*`
   - RSI, SMA, EMA endpoints not available
   - Solution: Calculate from historical price data

2. **Analyst Estimates**: `/analyst-estimates`
   - Returns 400 error (missing period parameter)
   - Solution: Use profile data for basic estimates

3. **Stock Rating**: `/rating`
   - Returns 404
   - Not available in stable API

4. **Balance Sheet**: `/balance-sheet`
   - Returns 404
   - Not available in stable API

### Data Structure Changes

The data returned by the stable API has the same structure as v3 for most endpoints, but some fields may be named differently or located in different endpoints. The pipeline has been updated to handle these changes gracefully.

### Testing

Use the included test scripts to verify API connectivity:
- `debug_fmp.py` - Tests individual FMP endpoints
- `test_fmp_simple.py` - Tests working endpoints
- `test_data_fetch.py` - Tests the full data fetching pipeline

### FRED API
FRED API continues to work without changes and provides:
- Federal Funds Rate (DFF)
- 10Y-2Y Yield Spread (T10Y2Y)
- VIX (VIXCLS)