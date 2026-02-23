"""File-based global daily usage counter for the web API."""

import json
import threading
from pathlib import Path
from datetime import date

DAILY_LIMIT = 50
_USAGE_FILE = Path("./data/usage.json")
_lock = threading.Lock()


def _read_usage() -> dict:
    """Read usage file, returning reset state if missing or stale."""
    today = date.today().isoformat()
    try:
        data = json.loads(_USAGE_FILE.read_text())
        if data.get("date") != today:
            return {"date": today, "count": 0}
        return data
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return {"date": today, "count": 0}


def _write_usage(data: dict) -> None:
    _USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _USAGE_FILE.write_text(json.dumps(data))


def check_and_increment() -> tuple[bool, int, int]:
    """Atomically check the daily limit and increment if allowed.

    Returns:
        (allowed, current_count_after, limit)
    """
    with _lock:
        data = _read_usage()
        if data["count"] >= DAILY_LIMIT:
            return False, data["count"], DAILY_LIMIT
        data["count"] += 1
        _write_usage(data)
        return True, data["count"], DAILY_LIMIT


def get_usage() -> tuple[int, int]:
    """Read-only usage check.

    Returns:
        (count, limit)
    """
    with _lock:
        data = _read_usage()
        return data["count"], DAILY_LIMIT
