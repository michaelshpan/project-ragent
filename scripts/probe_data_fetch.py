"""Smoke-test the FMP MCP integration: run all three fetchers and report
which tools succeeded vs. failed."""

import asyncio
import io
import os
import sys
from contextlib import redirect_stdout
from pathlib import Path

from dotenv import load_dotenv
from fastmcp import Client

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
load_dotenv()

from data import fetch_quant_data, fetch_sentiment_data, fetch_technical_data


async def main():
    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    api_key = os.environ.get("FMP_API_KEY")
    if not api_key:
        raise SystemExit("FMP_API_KEY not set")

    url = f"https://financialmodelingprep.com/mcp?apikey={api_key}"

    buf = io.StringIO()
    with redirect_stdout(buf):
        async with Client(url) as fmp_client:
            results = await asyncio.gather(
                fetch_quant_data(ticker, fmp_client=fmp_client),
                fetch_sentiment_data(ticker, fmp_client=fmp_client),
                fetch_technical_data(ticker, fmp_client=fmp_client),
                return_exceptions=True,
            )

    output = buf.getvalue()
    warnings = [line for line in output.splitlines() if "Warning: MCP" in line]

    print(f"=== Fetch results for {ticker} ===\n")
    for name, r in zip(["quant", "sentiment", "technical"], results):
        if isinstance(r, Exception):
            print(f"{name}: EXCEPTION {type(r).__name__}: {r}")
        else:
            n_keys = len(r) if isinstance(r, dict) else "n/a"
            print(f"{name}: ok ({n_keys} top-level keys)")

    print(f"\n=== MCP warnings ({len(warnings)}) ===")
    for w in warnings:
        print(w)


if __name__ == "__main__":
    asyncio.run(main())
