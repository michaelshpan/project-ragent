#!/usr/bin/env python3
"""Weekday morning brief automation.

Collects today's calendar events from one or more iCalendar feeds and unread
messages from IMAP, highlights items that need attention today, and delivers the
brief to stdout or SMTP email. Intended to be run by cron/systemd on weekdays.
"""

from __future__ import annotations

import argparse
import email
import imaplib
import os
import re
import smtplib
import ssl
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Iterable, Sequence
from urllib.request import urlopen
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

ATTENTION_KEYWORDS = (
    "action required",
    "asap",
    "blocked",
    "deadline",
    "due today",
    "needs approval",
    "please review",
    "respond today",
    "urgent",
)


@dataclass(frozen=True)
class CalendarEvent:
    title: str
    start: datetime
    end: datetime | None = None
    location: str | None = None


@dataclass(frozen=True)
class EmailSummary:
    sender: str
    subject: str
    received: datetime | None = None
    snippet: str = ""


def _unescape_ical(value: str) -> str:
    return value.replace("\\n", " ").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\").strip()


def _unfold_ical(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw.startswith((" ", "\t")) and lines:
            lines[-1] += raw[1:]
        elif raw:
            lines.append(raw)
    return lines


def _parse_ical_datetime(value: str, tzid: str | None, default_tz: ZoneInfo) -> datetime:
    tz = ZoneInfo(tzid) if tzid else default_tz
    if value.endswith("Z"):
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).astimezone(default_tz)
    if "T" in value:
        return datetime.strptime(value, "%Y%m%dT%H%M%S").replace(tzinfo=tz).astimezone(default_tz)
    return datetime.combine(datetime.strptime(value, "%Y%m%d").date(), time.min, tzinfo=default_tz)


def parse_ical_events(ical_text: str, target_date: date, tz_name: str) -> list[CalendarEvent]:
    """Parse VEVENT entries from iCalendar text for ``target_date``."""
    default_tz = ZoneInfo(tz_name)
    events: list[CalendarEvent] = []
    in_event = False
    fields: dict[str, tuple[str, str | None]] = {}

    for line in _unfold_ical(ical_text):
        if line == "BEGIN:VEVENT":
            in_event = True
            fields = {}
            continue
        if line == "END:VEVENT" and in_event:
            title = _unescape_ical(fields.get("SUMMARY", ("(No title)", None))[0])
            start_raw, start_tz = fields.get("DTSTART", ("", None))
            if start_raw:
                start = _parse_ical_datetime(start_raw, start_tz, default_tz)
                end_raw, end_tz = fields.get("DTEND", ("", None))
                end = _parse_ical_datetime(end_raw, end_tz, default_tz) if end_raw else None
                if start.date() == target_date:
                    location = fields.get("LOCATION", (None, None))[0]
                    events.append(CalendarEvent(title, start, end, _unescape_ical(location) if location else None))
            in_event = False
            continue
        if not in_event or ":" not in line:
            continue
        key_part, value = line.split(":", 1)
        key, *params = key_part.split(";")
        tzid = None
        for param in params:
            if param.startswith("TZID="):
                tzid = param.split("=", 1)[1]
        if key in {"SUMMARY", "DTSTART", "DTEND", "LOCATION"}:
            fields[key] = (value, tzid)

    return sorted(events, key=lambda event: event.start)


def load_calendar_events(urls: Sequence[str], target_date: date, tz_name: str) -> list[CalendarEvent]:
    events: list[CalendarEvent] = []
    for url in urls:
        with urlopen(url, timeout=20) as response:  # noqa: S310 - configured private calendar URLs are expected.
            events.extend(parse_ical_events(response.read().decode("utf-8"), target_date, tz_name))
    return sorted(events, key=lambda event: event.start)


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        return " ".join(part.strip() for part in self.parts if part.strip())


def _message_body(msg: email.message.Message) -> str:
    plain: str | None = None
    html: str | None = None
    parts = msg.walk() if msg.is_multipart() else [msg]
    for part in parts:
        content_type = part.get_content_type()
        if part.get_content_disposition() == "attachment":
            continue
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        if content_type == "text/plain" and plain is None:
            plain = text
        elif content_type == "text/html" and html is None:
            parser = _HTMLTextExtractor()
            parser.feed(text)
            html = parser.text()
    return plain or html or ""


def fetch_unread_emails(host: str, username: str, password: str, limit: int = 10, mailbox: str = "INBOX") -> list[EmailSummary]:
    """Fetch unread email summaries from an IMAP mailbox."""
    with imaplib.IMAP4_SSL(host) as client:
        client.login(username, password)
        client.select(mailbox, readonly=True)
        status, data = client.search(None, "UNSEEN")
        if status != "OK":
            return []
        ids = data[0].split()[-limit:]
        summaries: list[EmailSummary] = []
        for msg_id in reversed(ids):
            status, fetched = client.fetch(msg_id, "(RFC822)")
            if status != "OK" or not fetched or not isinstance(fetched[0], tuple):
                continue
            msg = email.message_from_bytes(fetched[0][1])
            received = None
            if msg.get("Date"):
                try:
                    received = parsedate_to_datetime(msg["Date"])
                except (TypeError, ValueError):
                    received = None
            body = re.sub(r"\s+", " ", _message_body(msg)).strip()
            summaries.append(EmailSummary(msg.get("From", "Unknown sender"), msg.get("Subject", "(No subject)"), received, body[:240]))
        return summaries


def attention_items(events: Iterable[CalendarEvent], emails: Iterable[EmailSummary]) -> list[str]:
    """Return concise action items inferred from calendar and unread email content."""
    items: list[str] = []
    for event in events:
        haystack = f"{event.title} {event.location or ''}".lower()
        if any(keyword in haystack for keyword in ("deadline", "due", "review", "interview", "1:1")):
            items.append(f"Calendar: {event.title}")
    for item in emails:
        haystack = f"{item.subject} {item.snippet}".lower()
        if any(keyword in haystack for keyword in ATTENTION_KEYWORDS):
            items.append(f"Email: {item.subject} — {item.sender}")
    return items


def render_brief(events: Sequence[CalendarEvent], emails: Sequence[EmailSummary], target_date: date, tz_name: str) -> str:
    lines = [f"Morning brief for {target_date:%A, %B %-d, %Y} ({tz_name})", ""]
    lines.append("Calendar")
    if events:
        for event in events:
            start = event.start.strftime("%-I:%M %p")
            end = f"–{event.end.strftime('%-I:%M %p')}" if event.end else ""
            location = f" @ {event.location}" if event.location else ""
            lines.append(f"- {start}{end}: {event.title}{location}")
    else:
        lines.append("- No calendar events found for today.")
    lines.extend(["", "Important unread emails"])
    if emails:
        for item in emails:
            when = f" ({item.received.astimezone(ZoneInfo(tz_name)).strftime('%-I:%M %p')})" if item.received else ""
            lines.append(f"- {item.subject} — {item.sender}{when}")
    else:
        lines.append("- No unread emails found.")
    lines.extend(["", "Needs attention today"])
    items = attention_items(events, emails)
    lines.extend(f"- {item}" for item in items) if items else lines.append("- Nothing obvious flagged from calendar or unread email.")
    return "\n".join(lines) + "\n"


def send_smtp(subject: str, body: str, sender: str, recipient: str, host: str, port: int, username: str | None, password: str | None) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content(body)
    context = ssl.create_default_context()
    with smtplib.SMTP(host, port) as server:
        server.starttls(context=context)
        if username and password:
            server.login(username, password)
        server.send_message(msg)


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Generate and optionally email a weekday morning brief.")
    parser.add_argument("--date", help="Date to brief in YYYY-MM-DD format; defaults to today.")
    parser.add_argument("--force", action="store_true", help="Run even on weekends.")
    args = parser.parse_args()

    tz_name = os.getenv("MORNING_BRIEF_TZ", "America/New_York")
    today = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else datetime.now(ZoneInfo(tz_name)).date()
    if today.weekday() >= 5 and not args.force:
        print("Skipping morning brief because today is not a weekday. Use --force to override.")
        return 0

    calendar_urls = [url.strip() for url in os.getenv("MORNING_BRIEF_ICS_URLS", "").split(",") if url.strip()]
    events = load_calendar_events(calendar_urls, today, tz_name) if calendar_urls else []

    emails: list[EmailSummary] = []
    if os.getenv("MORNING_BRIEF_IMAP_HOST") and os.getenv("MORNING_BRIEF_IMAP_USERNAME") and os.getenv("MORNING_BRIEF_IMAP_PASSWORD"):
        emails = fetch_unread_emails(
            os.environ["MORNING_BRIEF_IMAP_HOST"],
            os.environ["MORNING_BRIEF_IMAP_USERNAME"],
            os.environ["MORNING_BRIEF_IMAP_PASSWORD"],
            int(os.getenv("MORNING_BRIEF_EMAIL_LIMIT", "10")),
        )

    brief = render_brief(events, emails, today, tz_name)
    print(brief)

    if os.getenv("MORNING_BRIEF_SMTP_HOST") and os.getenv("MORNING_BRIEF_TO") and os.getenv("MORNING_BRIEF_FROM"):
        send_smtp(
            f"Morning brief — {today:%b %-d}",
            brief,
            os.environ["MORNING_BRIEF_FROM"],
            os.environ["MORNING_BRIEF_TO"],
            os.environ["MORNING_BRIEF_SMTP_HOST"],
            int(os.getenv("MORNING_BRIEF_SMTP_PORT", "587")),
            os.getenv("MORNING_BRIEF_SMTP_USERNAME"),
            os.getenv("MORNING_BRIEF_SMTP_PASSWORD"),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
