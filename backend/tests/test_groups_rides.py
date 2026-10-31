from datetime import date, timedelta

from app.planner.groups import GROUPS, hotel_bonus
from app.planner.solver import TripRequest, solve
from app.planner.verify import COMMONSENSE, HARD, check
from app.providers.local_transport import compare
from app.strategist.runner import where_to_go
from tests.conftest import register

D = date.today() + timedelta(days=40)
JAIPUR_AIRPORT, HAWA_MAHAL = (26.8242, 75.8122), (26.9239, 75.8267)


def test_family_and_seniors_never_get_high_altitude_destinations():
    for kind in ("family", "seniors"):
        assert all(p["slug"] not in ("leh", "tawang") for p in where_to_go(7, traveller_type=kind, limit=26))


def test_couples_get_honeymoon_destinations_first():
    top = where_to_go(12, traveller_type="couple", limit=5)
    assert all("honeymoon" in p["tags"] or "beach" in p["tags"] or "lakes" in p["tags"] for p in top[:3])


def test_group_preferences_keep_hard_constraints():
    for kind in GROUPS:
        req = TripRequest("Delhi", "goa", D, nights=3, adults=2, budget_total=90000, traveller_type=kind)
        res = solve(req)
        assert res.status == "ok"
        assert all(check(req, {"out": res.out, "back": res.back, "stay": res.stay}).values())


def test_family_plan_prefers_family_friendly_stay():
    generic = solve(TripRequest("Mumbai", "goa", D, nights=3, adults=4, budget_total=200000))
    family = solve(TripRequest("Mumbai", "goa", D, nights=3, adults=4, budget_total=200000, traveller_type="family"))
    assert hotel_bonus(family.stay, "family")[0] >= hotel_bonus(generic.stay, "family")[0]
    assert family.why


def test_rides_family_with_luggage_gets_a_car():
    r = compare(JAIPUR_AIRPORT, HAWA_MAHAL, hour=18, people=4, bags=2, traveller_type="family")
    assert r["recommended"]["mode"] in ("cab", "sedan", "suv")
    assert all(o["mode"] != "bike" for o in r["options"])


def test_rides_large_group_gets_suv_and_solo_budget_gets_public_transport():
    assert compare(JAIPUR_AIRPORT, HAWA_MAHAL, hour=14, people=5, bags=3, traveller_type="friends")["recommended"]["mode"] == "suv"
    solo = compare(JAIPUR_AIRPORT, HAWA_MAHAL, hour=11, people=1, priority="cheapest", traveller_type="solo")
    assert solo["recommended"]["mode"] in ("bus", "metro", "bike")


def test_rides_cheapest_badge_and_night_rules():
    r = compare(JAIPUR_AIRPORT, HAWA_MAHAL, hour=23, people=1)
    assert all(o["mode"] not in ("bus", "metro", "bike") for o in r["options"])
    cheapest = min(r["options"], key=lambda o: o["per_person"])
    assert "Cheapest" in cheapest["badges"]


async def test_local_compare_api(client):
    data = await register(client, "rides-api@example.com")
    auth = {"Authorization": f"Bearer {data['access_token']}"}
    r = await client.post("/api/local/compare", headers=auth, json={
        "from_lat": JAIPUR_AIRPORT[0], "from_lon": JAIPUR_AIRPORT[1], "to_lat": HAWA_MAHAL[0], "to_lon": HAWA_MAHAL[1],
        "hour": 10, "people": 2, "traveller_type": "couple"})
    assert r.status_code == 200 and r.json()["recommended"] and len(r.json()["options"]) >= 5


def test_family_strategy_never_recommends_pre_dawn_flight():
    from app.data.destinations import DESTINATIONS
    from app.strategist.base import TripContext
    from app.strategist.runner import advise
    import re
    for days in range(20, 40):
        ctx = TripContext(destination=DESTINATIONS["goa"], month=1, origin="Mumbai", travel_date=date.today() + timedelta(days=days),
                          traveller_type="family")
        for s in advise(ctx, limit=10):
            m = re.match(r"Take the (\d+):\d+ (AM|PM) flight", s.title)
            if m:
                hour = int(m.group(1)) % 12 + (12 if m.group(2) == "PM" else 0)
                assert 6 <= hour < 22


def test_couple_evening_ride_is_a_car():
    r = compare(JAIPUR_AIRPORT, HAWA_MAHAL, hour=20, people=2, bags=1, traveller_type="couple")
    assert r["recommended"]["mode"] in ("cab", "sedan")
