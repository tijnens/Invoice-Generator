from datetime import datetime, timedelta, timezone
import pytest
from conftest import find_client
from calendar_processor import match_event_title_to_client_names
from util import GoogleCalendarEvent


@pytest.mark.parametrize("minutes,expected", [(30, 50), (45, 75), (60, 100), (90, 150)])
def test_event_price(clients, minutes, expected):
    start = datetime(2026, 10, 5, 9, tzinfo=timezone.utc)
    appointment = GoogleCalendarEvent(
        title="Emma de Vries", id=f"appointment-{minutes}", link="",
        start_date=start, end_date=start + timedelta(minutes=minutes),
    )
    match_event_title_to_client_names(appointment, clients)
    emma = find_client(clients, "Emma de Vries")
    assert emma.calculate_price_for_event(appointment.id) == pytest.approx(expected)


def test_unknown_event_id_returns_none(clients):
    assert find_client(clients, "Emma de Vries").calculate_price_for_event("missing") is None
