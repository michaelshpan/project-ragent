from datetime import date

from morning_brief import EmailSummary, attention_items, parse_ical_events, render_brief


ICS = """BEGIN:VCALENDAR
BEGIN:VEVENT
SUMMARY:Team standup
DTSTART;TZID=America/New_York:20260618T090000
DTEND;TZID=America/New_York:20260618T093000
LOCATION:Zoom
END:VEVENT
BEGIN:VEVENT
SUMMARY:Please review launch plan
DTSTART;TZID=America/New_York:20260618T140000
DTEND;TZID=America/New_York:20260618T150000
END:VEVENT
END:VCALENDAR
"""


def test_parse_ical_events_for_target_date():
    events = parse_ical_events(ICS, date(2026, 6, 18), "America/New_York")

    assert [event.title for event in events] == ["Team standup", "Please review launch plan"]
    assert events[0].location == "Zoom"
    assert events[0].start.hour == 9


def test_attention_items_detects_calendar_and_email_actions():
    events = parse_ical_events(ICS, date(2026, 6, 18), "America/New_York")
    emails = [EmailSummary("boss@example.com", "Action required: approve budget", snippet="Please review by noon")]

    items = attention_items(events, emails)

    assert "Calendar: Please review launch plan" in items
    assert "Email: Action required: approve budget — boss@example.com" in items


def test_render_brief_includes_sections():
    events = parse_ical_events(ICS, date(2026, 6, 18), "America/New_York")
    brief = render_brief(events, [], date(2026, 6, 18), "America/New_York")

    assert "Morning brief for Thursday, June 18, 2026" in brief
    assert "Calendar" in brief
    assert "Important unread emails" in brief
    assert "Needs attention today" in brief
