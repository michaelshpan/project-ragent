"""FastAPI server for the Investment Committee web interface."""

import json
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

from rate_limit import check_and_increment, get_usage
from pipeline_web import run_pipeline_web

app = FastAPI(title="Investment Committee")

# Track tickers with an analysis currently in-flight to prevent duplicates.
_active_tickers: set[str] = set()


# ── Request / response models ───────────────────────────────────────────────


class AnalyzeRequest(BaseModel):
    ticker: str

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        v = v.strip().upper()
        if not re.fullmatch(r"[A-Z]{1,5}", v):
            raise ValueError("Ticker must be 1-5 alphabetic characters")
        return v


# ── Endpoints ────────────────────────────────────────────────────────────────


@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest):
    ticker = req.ticker

    # Rate limit
    allowed, count, limit = check_and_increment()
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=(
                "Sorry, we've hit the daily limit! "
                "The analysts and PM have gone to enjoy a few drinks at the pub. "
                "Please come back tomorrow for more."
            ),
        )

    # Guard against concurrent analyses of the same ticker
    if ticker in _active_tickers:
        raise HTTPException(
            status_code=409,
            detail=f"Analysis for {ticker} is already in progress.",
        )

    async def event_stream():
        _active_tickers.add(ticker)
        try:
            async for event in run_pipeline_web(ticker):
                data = json.dumps(event, default=str)
                yield f"event: {event['event']}\ndata: {data}\n\n"
        finally:
            _active_tickers.discard(ticker)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/usage")
async def usage():
    count, limit = get_usage()
    return {"count": count, "limit": limit, "remaining": limit - count}


# ── Static file serving ─────────────────────────────────────────────────────

_frontend_dist = Path(__file__).parent / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="static")


# ── Dev entry-point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)
