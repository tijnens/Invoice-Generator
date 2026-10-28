from datetime import datetime, timedelta, timezone
import pytest
from conftest import find_client
from calendar_processor import match_event_title_to_client_names
from util import GoogleCalendarEvent, load_client_database


def event(title, event_id="e1", duration_minutes=60):
    start = datetime(2026, 10, 5, 9, tzinfo=timezone.utc)
    return GoogleCalendarEvent(
        title=title, id=event_id, link="", start_date=start,
        end_date=start + timedelta(minutes=duration_minutes),
    )


@pytest.mark.parametrize("title", ["Emma de Vries", "Emma de Vries vervolgafspraak", "  EMMA   de Vries  "])
def test_full_name_match(clients, title):
    matches = match_event_title_to_client_names(event(title), clients)
    assert [c.full_name for c in matches] == ["Emma de Vries"]
    assert matches[0].matched_calendar_events["e1"]["match_type"] == "exact_match"


def test_unique_first_name_match(clients):
    matches = match_event_title_to_client_names(event("Emma consult"), clients)
    assert [c.full_name for c in matches] == ["Emma de Vries"]


def test_intro_call_excluded(clients):
    assert match_event_title_to_client_names(event("Emma bellen"), clients) == []


def test_bellen_last_name_is_included_with_warning(clients):
    matches = match_event_title_to_client_names(event("Milan Bellen"), clients)
    assert len(matches) == 1
    assert matches[0].matched_calendar_events["e1"]["match_type"] == "bellen_match"


def test_unrelated_event_excluded(clients):
    assert match_event_title_to_client_names(event("Team meeting"), clients) == []


def test_ambiguous_first_name_fuzzy(client_csv, sample_rows):
    sample_rows.append({**sample_rows[0], "last name": "Jansen", "id": "CL004"})
    data = load_client_database(str(client_csv(sample_rows)))
    matches = match_event_title_to_client_names(event("Emma"), data)
    assert {c.full_name for c in matches} == {"Emma de Vries", "Emma Jansen"}
    assert all(c.matched_calendar_events["e1"]["match_type"] == "fuzzy_match" for c in matches)


def test_full_name_disambiguates_duplicate_first_name(client_csv, sample_rows):
    sample_rows.append({**sample_rows[0], "last name": "Jansen", "id": "CL004"})
    data = load_client_database(str(client_csv(sample_rows)))
    matches = match_event_title_to_client_names(event("Emma Jansen"), data)
    assert [c.full_name for c in matches] == ["Emma Jansen"]
    assert matches[0].matched_calendar_events["e1"]["match_type"] == "exact_match"
