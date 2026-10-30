from datetime import date, timedelta

from app.data.destinations import DESTINATIONS
from app.knowledge.search import search
from app.providers import sandbox
from app.strategist.base import TripContext
from app.strategist.runner import advise, where_to_go


def test_sandbox_is_deterministic():
    d = date.today() + timedelta(days=25)
    assert sandbox.search_flights("Delhi", "Goa", d) == sandbox.search_flights("Delhi", "Goa", d)


def test_prices_rise_close_to_departure():
    assert sandbox.lead_time_multiplier(2) > sandbox.lead_time_multiplier(30)


def test_aliases_resolve():
    assert sandbox.resolve_airports("Bombay") == ["BOM"]
    assert sandbox.resolve_stations("Banaras") == ["BSB"]


def test_closed_day_strategy_flags_taj_friday():
    today = date.today()
    friday = today + timedelta(days=(4 - today.weekday()) % 7 + 7)
    ctx = TripContext(destination=DESTINATIONS["agra"], month=friday.month, travel_date=friday, nights=1)
    titles = [s.title for s in advise(ctx, limit=10)]
    assert any("Taj Mahal is closed" in t for t in titles)


def test_permit_strategy_for_tawang():
    ctx = TripContext(destination=DESTINATIONS["tawang"], month=10)
    assert any(s.strategy == "permits" for s in advise(ctx, limit=10))


def test_where_to_go_in_july_prefers_ladakh():
    names = [p["slug"] for p in where_to_go(7)]
    assert "leh" in names and "goa" not in names


def test_knowledge_search_finds_ilp():
    assert search("do I need a permit for Tawang?")[0]["id"] == "ilp-arunachal"
