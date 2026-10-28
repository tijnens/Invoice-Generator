import json
from datetime import datetime
import calendar_processor
from util import transform_user_dates_to_google_calendar_api_dates


def write_mock(tmp_path, events):
    folder = tmp_path / "demo"
    folder.mkdir()
    (folder / "events.json").write_text(json.dumps({"items": events}), encoding="utf-8")
    return folder


def make_event(event_id, summary, timestamp):
    start = datetime.fromisoformat(timestamp)
    end = start.replace(hour=start.hour + 1)
    return {
        "id": event_id,
        "summary": summary,
        "htmlLink": "",
        "start": {"dateTime": start.isoformat()},
        "end": {"dateTime": end.isoformat()},
    }


def test_demo_date_filtering(clients, tmp_path, monkeypatch):
    write_mock(tmp_path, [
        make_event("sep", "Emma de Vries", "2026-09-30T10:00:00+02:00"),
        make_event("oct", "Emma de Vries", "2026-10-01T10:00:00+02:00"),
        make_event("nov", "Emma de Vries", "2026-11-01T10:00:00+01:00"),
    ])
    monkeypatch.setattr(calendar_processor, "base_path", str(tmp_path))
    monkeypatch.setattr(calendar_processor, "MOCK_CALENDAR_LOC", "demo/events.json")
    start, end = transform_user_dates_to_google_calendar_api_dates("01-10-2026", "31-10-2026")
    matches = calendar_processor.pull_calendar_data(start, end, clients, None, demo=True)
    assert len(matches) == 1
    assert set(matches[0].matched_calendar_events) == {"oct"}


def test_empty_demo_calendar_returns_list(clients, tmp_path, monkeypatch):
    write_mock(tmp_path, [])
    monkeypatch.setattr(calendar_processor, "base_path", str(tmp_path))
    monkeypatch.setattr(calendar_processor, "MOCK_CALENDAR_LOC", "demo/events.json")
    start, end = transform_user_dates_to_google_calendar_api_dates("01-10-2026", "31-10-2026")
    assert calendar_processor.pull_calendar_data(start, end, clients, None, demo=True) == []


def test_demo_skips_events_without_summary(clients, tmp_path, monkeypatch):
    write_mock(tmp_path, [make_event("empty", "", "2026-10-05T09:00:00+02:00")])
    monkeypatch.setattr(calendar_processor, "base_path", str(tmp_path))
    monkeypatch.setattr(calendar_processor, "MOCK_CALENDAR_LOC", "demo/events.json")
    start, end = transform_user_dates_to_google_calendar_api_dates("01-10-2026", "31-10-2026")
    assert calendar_processor.pull_calendar_data(start, end, clients, None, demo=True) == []


def test_october_date_bounds_account_for_dst():
    start, end = transform_user_dates_to_google_calendar_api_dates("01-10-2026", "31-10-2026")
    assert start == "2026-09-30T22:00:00Z"
    assert end == "2026-10-31T23:00:00Z"
