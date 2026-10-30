"""Tools Ask Sara can call. Each returns a compact JSON summary for the model and an optional UI card.

Facts (prices, availability, weather, rules) come only from these tools, never from the model."""

import json
import logging
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select

from app.booking import BookingError, booking_dict, consent_card, create_consent, store_options
from app.data.destinations import DESTINATIONS, MONTHS, find_destination, parse_month
from app.db import SessionLocal
from app.knowledge.search import search as kb_search
from app.models import Booking, User
from app.providers import sandbox, weather
from app.strategist.base import TripContext
from app.strategist.runner import advise, avoid_in, best_time, where_to_go

log = logging.getLogger(__name__)


@dataclass
class ToolContext:
    user_id: str


@dataclass
class ToolResult:
    summary: str
    card: dict | None = None


def _err(msg: str) -> ToolResult:
    return ToolResult(json.dumps({"error": msg}))


def _date(value, field: str) -> date:
    try:
        d = date.fromisoformat(str(value)[:10])
    except ValueError:
        raise ValueError(f"{field} must be a date in YYYY-MM-DD format")
    today = date.today()
    if d < today:
        raise ValueError(f"{field} {d} is in the past (today is {today})")
    if d > today + timedelta(days=365):
        raise ValueError(f"{field} is more than a year away")
    return d


def _adults(v) -> int:
    try:
        return max(1, min(int(v or 1), 9))
    except (TypeError, ValueError):
        return 1


KNOWN_PLACES = ", ".join(sorted({d["name"] for d in DESTINATIONS.values()}))


# ------------------------------------------------------------------ tool implementations

async def search_flights(ctx: ToolContext, origin: str, destination: str, date: str, adults: int = 1) -> ToolResult:
    travel = _date(date, "date")
    n = _adults(adults)
    results = sandbox.search_flights(origin, destination, travel, n)[:6]
    if not results:
        return _err(f"No flights found between {origin} and {destination}. Try a nearby city with an airport.")
    async with SessionLocal() as db:
        options = await store_options(db, ctx.user_id, "flight", results)
    card = {"type": "flights", "title": f"Flights {results[0]['from_city']} → {results[0]['to_city']}",
            "date": travel.isoformat(), "adults": n, "options": options}
    brief = [{"id": o["id"], "airline": o["airline"], "flight": o["flight_no"], "route": f"{o['from']}-{o['to']}",
              "depart": o["depart"][11:], "arrive": o["arrive"][11:], "stops": o["stops"], "total_inr": o["price_total"]}
             for o in options]
    return ToolResult(json.dumps({"date": travel.isoformat(), "adults": n, "options": brief}), card)


async def search_trains(ctx: ToolContext, origin: str, destination: str, date: str, adults: int = 1) -> ToolResult:
    travel = _date(date, "date")
    n = _adults(adults)
    results = sandbox.search_trains(origin, destination, travel, n)
    if not results:
        return _err(f"No direct trains found between {origin} and {destination} in the sandbox.")
    async with SessionLocal() as db:
        options = await store_options(db, ctx.user_id, "train", results)
    card = {"type": "trains", "title": f"Trains {results[0]['from_name']} → {results[0]['to_name']}",
            "date": travel.isoformat(), "adults": n, "options": options}
    brief = [{"id": o["id"], "train": f"{o['train_name']} {o['train_no']}", "class": o["class"],
              "depart": o["depart"][11:], "duration_h": round(o["duration_min"] / 60, 1),
              "availability": o["availability"], "confirm_chance": o["confirm_chance"], "total_inr": o["price_total"]}
             for o in options]
    return ToolResult(json.dumps({"date": travel.isoformat(), "adults": n, "options": brief}), card)


async def search_hotels(ctx: ToolContext, city: str, check_in: str, check_out: str, guests: int = 2,
                        max_price_per_night: int | None = None) -> ToolResult:
    cin, cout = _date(check_in, "check_in"), _date(check_out, "check_out")
    if cout <= cin:
        return _err("check_out must be after check_in")
    results = sandbox.search_hotels(city, cin, cout, _adults(guests), max_price_per_night)
    if not results:
        return _err("No hotels match those filters. Try a higher budget.")
    async with SessionLocal() as db:
        options = await store_options(db, ctx.user_id, "hotel", results)
    card = {"type": "hotels", "title": f"Stays in {results[0]['city']}", "options": options}
    brief = [{"id": o["id"], "hotel": o["hotel"], "stars": o["stars"], "rating": o["rating"],
              "per_night_inr": o["price_per_night"], "total_inr": o["price_total"],
              "free_cancel_until": o["free_cancellation_until"]} for o in options]
    return ToolResult(json.dumps({"check_in": cin.isoformat(), "check_out": cout.isoformat(), "options": brief}), card)


async def get_weather(ctx: ToolContext, place: str, start_date: str | None = None) -> ToolResult:
    dest = find_destination(place)
    if not dest:
        return _err(f"Unknown place. Known destinations: {KNOWN_PLACES}")
    start = _date(start_date, "start_date") if start_date else date.today()
    if (start - date.today()).days <= 14:
        days = await weather.forecast(dest["lat"], dest["lon"], start)
        if days:
            card = {"type": "weather", "title": f"Weather in {dest['name']}", "days": days}
            return ToolResult(json.dumps({"forecast": days}), card)
    bt = best_time(dest)
    month = bt["months"][start.month - 1]
    return ToolResult(json.dumps({"note": "Beyond forecast range; typical conditions", "month": month["name"],
                                  "rating_out_of_5": month["rating"], "tips": dest["tips"]}),
                      {"type": "best_time", **bt})


async def best_time_to_visit(ctx: ToolContext, destination: str) -> ToolResult:
    dest = find_destination(destination)
    if not dest:
        return _err(f"Unknown destination. Known destinations: {KNOWN_PLACES}")
    bt = best_time(dest)
    brief = {"ratings": {m["name"][:3]: m["rating"] for m in bt["months"]}, "peak": [m["name"] for m in bt["months"] if m["peak"]],
             "best_value": bt["best_value_months"], "tips": bt["tips"], "permit": bt["permit"]}
    return ToolResult(json.dumps(brief), {"type": "best_time", **bt})


async def strategist_advice(ctx: ToolContext, destination: str, origin: str | None = None,
                            travel_date: str | None = None, month: str | None = None, nights: int = 3,
                            adults: int = 1) -> ToolResult:
    dest = find_destination(destination)
    if not dest:
        return _err(f"Unknown destination. Known destinations: {KNOWN_PLACES}")
    travel = _date(travel_date, "travel_date") if travel_date else None
    m = travel.month if travel else (parse_month(month) if month else date.today().month)
    if m is None:
        return _err("month must be a month name or number")
    tc = TripContext(destination=dest, month=m, origin=origin, travel_date=travel,
                     nights=max(1, min(int(nights or 3), 30)), adults=_adults(adults))
    suggestions = [s.to_dict() for s in advise(tc)]
    card = {"type": "strategy", "title": f"Sara's strategy for {dest['name']}", "suggestions": suggestions}
    return ToolResult(json.dumps({"suggestions": [{k: s[k] for k in ("title", "detail", "saving_inr")} for s in suggestions]}), card)


async def where_to_go_in(ctx: ToolContext, month: str, interest: str | None = None) -> ToolResult:
    m = parse_month(month)
    if m is None:
        return _err("month must be a month name or number")
    picks = where_to_go(m, interest)
    avoid = avoid_in(m)
    card = {"type": "where", "title": f"Where to go in {MONTHS[m - 1]}", "month": MONTHS[m - 1], "picks": picks, "avoid": avoid}
    return ToolResult(json.dumps({"picks": [{"name": p["name"], "rating": p["rating"], "peak": p["peak"]} for p in picks],
                                  "avoid": avoid}), card)


async def search_travel_knowledge(ctx: ToolContext, query: str) -> ToolResult:
    hits = kb_search(query[:300])
    if not hits:
        return ToolResult(json.dumps({"results": [], "note": "Nothing in the knowledge base. Say you are not sure."}))
    card = {"type": "knowledge", "title": "From Sara's travel guide", "results": hits}
    return ToolResult(json.dumps({"results": hits}), card)


async def propose_booking(ctx: ToolContext, option_ids: list[str], title: str = "Your trip") -> ToolResult:
    async with SessionLocal() as db:
        user = await db.get(User, ctx.user_id)
        try:
            consent = await create_consent(db, user, option_ids if isinstance(option_ids, list) else [option_ids], title)
        except BookingError as exc:
            return _err(str(exc))
    card = consent_card(consent)
    return ToolResult(json.dumps({"consent_id": consent.id, "total_inr": consent.total_inr,
                                  "status": "awaiting user approval in the consent card"}), card)


async def get_my_bookings(ctx: ToolContext) -> ToolResult:
    async with SessionLocal() as db:
        rows = (await db.scalars(select(Booking).where(Booking.user_id == ctx.user_id)
                                 .order_by(Booking.created_at.desc()).limit(10))).all()
    items = [booking_dict(b) for b in rows]
    if not items:
        return ToolResult(json.dumps({"bookings": []}))
    card = {"type": "bookings", "title": "Your bookings", "bookings": items}
    return ToolResult(json.dumps({"bookings": [{k: b[k] for k in ("title", "reference", "status", "amount_inr")} for b in items]}), card)


# ------------------------------------------------------------------ schemas

def _fn(name, description, properties, required):
    return {"type": "function", "function": {"name": name, "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required}}}


S = {"type": "string"}
I = {"type": "integer"}

TOOLS = [
    _fn("search_flights", "Search flights between Indian cities for a date. Returns option IDs with prices.",
        {"origin": S, "destination": S, "date": {**S, "description": "YYYY-MM-DD"}, "adults": I},
        ["origin", "destination", "date"]),
    _fn("search_trains", "Search trains between Indian cities for a date, with availability and waitlist confirmation chance.",
        {"origin": S, "destination": S, "date": {**S, "description": "YYYY-MM-DD"}, "adults": I},
        ["origin", "destination", "date"]),
    _fn("search_hotels", "Search hotels in a city for given dates.",
        {"city": S, "check_in": {**S, "description": "YYYY-MM-DD"}, "check_out": {**S, "description": "YYYY-MM-DD"},
         "guests": I, "max_price_per_night": I}, ["city", "check_in", "check_out"]),
    _fn("get_weather", "Weather forecast (next 14 days) or typical conditions for a destination.",
        {"place": S, "start_date": {**S, "description": "YYYY-MM-DD, optional"}}, ["place"]),
    _fn("best_time_to_visit", "Month-by-month rating, peak months, festivals, tips and permits for a destination.",
        {"destination": S}, ["destination"]),
    _fn("strategist_advice", "Run Sara's Strategist: booking timing, cheapest departure time, nearby airports, closed days, "
        "weather, shoulder season, festivals, fog/monsoon buffers and permits.",
        {"destination": S, "origin": S, "travel_date": {**S, "description": "YYYY-MM-DD, optional"},
         "month": {**S, "description": "month name if no exact date"}, "nights": I, "adults": I}, ["destination"]),
    _fn("where_to_go_in", "Recommend destinations for a month, optionally filtered by interest (beach, mountains, heritage, ...).",
        {"month": S, "interest": S}, ["month"]),
    _fn("search_travel_knowledge", "Search Sara's travel guide: permits, train rules, Tatkal, monument rules, safety, app help.",
        {"query": S}, ["query"]),
    _fn("propose_booking", "Create a consent request for the chosen option IDs. The user must approve and pay in the "
        "consent card; this does NOT book anything by itself.",
        {"option_ids": {"type": "array", "items": S}, "title": S}, ["option_ids"]),
    _fn("get_my_bookings", "List the user's recent bookings and their status.", {}, []),
]

IMPLS = {
    "search_flights": search_flights, "search_trains": search_trains, "search_hotels": search_hotels,
    "get_weather": get_weather, "best_time_to_visit": best_time_to_visit, "strategist_advice": strategist_advice,
    "where_to_go_in": where_to_go_in, "search_travel_knowledge": search_travel_knowledge,
    "propose_booking": propose_booking, "get_my_bookings": get_my_bookings,
}

STATUS = {
    "search_flights": "Checking flights…", "search_trains": "Checking trains and waitlists…",
    "search_hotels": "Comparing stays…", "get_weather": "Looking at the weather…",
    "best_time_to_visit": "Checking the best time to go…", "strategist_advice": "Running the Strategist…",
    "where_to_go_in": "Finding the best places for that month…", "search_travel_knowledge": "Checking my travel guide…",
    "propose_booking": "Preparing your booking for approval…", "get_my_bookings": "Fetching your bookings…",
}


async def run_tool(name: str, args: dict, ctx: ToolContext) -> ToolResult:
    impl = IMPLS.get(name)
    if impl is None:
        return _err(f"Unknown tool {name}")
    try:
        return await impl(ctx, **args)
    except (ValueError, TypeError) as exc:
        return _err(str(exc))
    except Exception:
        log.exception("tool %s failed", name)
        return _err("This tool failed unexpectedly. Tell the user and offer to try again.")
