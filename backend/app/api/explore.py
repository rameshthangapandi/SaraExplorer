"""Click-based features (no chat needed): Plan & Book searches, Explore with photos and maps, Travel Guide."""

import asyncio
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.agents import tools
from app.agents.tools import ToolContext
from app.data.destinations import DESTINATIONS, MONTHS
from app.data.geo import AIRPORTS, STATIONS
from app.knowledge.docs import DOCS, VERIFIED
from app.knowledge.search import search as kb_search
from app.models import User
from app.planner.solver import TripRequest
from app.providers import places, weather
from app.security.deps import get_current_user
from app.security.rate_limit import enforce
from app.strategist.runner import best_time

router = APIRouter(prefix="/api", tags=["explore"])


# ---------------------------------------------------------------- reference data

@router.get("/meta/places")
async def meta_places(user: User = Depends(get_current_user)):
    cities = sorted({a["city"] for a in AIRPORTS.values()} | {s["city"] for s in STATIONS.values()})
    dests = [{"slug": d["slug"], "name": d["name"], "state": d["state"]}
             for d in sorted(DESTINATIONS.values(), key=lambda d: d["name"])]
    return {"origins": cities, "destinations": dests}


# ---------------------------------------------------------------- Plan & Book (same tools Sara uses)

class FlightQ(BaseModel):
    origin: str = Field(max_length=60)
    destination: str = Field(max_length=60)
    date: date
    adults: int = Field(default=1, ge=1, le=9)


class HotelQ(BaseModel):
    city: str = Field(max_length=60)
    check_in: date
    check_out: date
    guests: int = Field(default=2, ge=1, le=9)
    max_price_per_night: int | None = Field(default=None, ge=500, le=200000)


def _card_or_error(result: tools.ToolResult) -> dict:
    if result.card is None:
        import json
        raise HTTPException(422, json.loads(result.summary).get("error", "No results"))
    return result.card


@router.post("/search/flights")
async def search_flights(q: FlightQ, user: User = Depends(get_current_user)):
    await enforce(f"search:{user.id}", 40, 60)
    return _card_or_error(await tools.search_flights(ToolContext(user.id), q.origin, q.destination, q.date.isoformat(), q.adults))


@router.post("/search/trains")
async def search_trains(q: FlightQ, user: User = Depends(get_current_user)):
    await enforce(f"search:{user.id}", 40, 60)
    return _card_or_error(await tools.search_trains(ToolContext(user.id), q.origin, q.destination, q.date.isoformat(), q.adults))


@router.post("/search/hotels")
async def search_hotels(q: HotelQ, user: User = Depends(get_current_user)):
    await enforce(f"search:{user.id}", 40, 60)
    return _card_or_error(await tools.search_hotels(ToolContext(user.id), q.city, q.check_in.isoformat(),
                                                    q.check_out.isoformat(), q.guests, q.max_price_per_night))


class AutoPlanQ(BaseModel):
    origin: str = Field(max_length=60)
    destination: str = Field(max_length=60)
    depart: date
    nights: int = Field(default=3, ge=1, le=14)
    adults: int = Field(default=2, ge=1, le=9)
    mode: str = Field(default="any", pattern="^(any|flight|train)$")
    budget_total: int | None = Field(default=None, ge=500, le=2_000_000)
    hotel_max_per_night: int | None = Field(default=None, ge=500, le=200_000)
    hotel_min_stars: int | None = Field(default=None, ge=1, le=5)
    round_trip: bool = True
    objective: str = Field(default="balanced", pattern="^(cheapest|balanced|comfort)$")


@router.post("/plan/auto")
async def auto_plan(q: AutoPlanQ, user: User = Depends(get_current_user)):
    """Constraint solver: best complete trip satisfying every constraint, or an explanation why none exists."""
    await enforce(f"autoplan:{user.id}", 30, 60)
    if q.depart < date.today():
        raise HTTPException(422, "Departure date is in the past")
    return await tools.run_auto_plan(user.id, TripRequest(**q.model_dump()))


# ---------------------------------------------------------------- Explore

@router.get("/explore/destinations")
async def explore_destinations(month: int | None = Query(default=None, ge=1, le=12), interest: str | None = None,
                               user: User = Depends(get_current_user)):
    m = month or date.today().month
    picks = [d for d in DESTINATIONS.values()
             if not interest or interest.lower() in " ".join(d["tags"] + [d["terrain"]])]
    sem = asyncio.Semaphore(6)

    async def photo(d):
        async with sem:
            s = await places.wiki_summary(places.WIKI_TITLES.get(d["slug"], d["name"]))
        return (s or {}).get("thumb") or (s or {}).get("image")

    images = await asyncio.gather(*(photo(d) for d in picks))
    out = [{"slug": d["slug"], "name": d["name"], "state": d["state"], "tags": d["tags"], "image": img,
            "rating": d["ratings"][m - 1], "peak": m in d["peak"], "permit": bool(d["permit"])}
           for d, img in zip(picks, images)]
    out.sort(key=lambda x: (-x["rating"], x["peak"], x["name"]))
    return {"month": MONTHS[m - 1], "destinations": out}


@router.get("/explore/destinations/{slug}")
async def explore_destination(slug: str, user: User = Depends(get_current_user)):
    d = DESTINATIONS.get(slug)
    if not d:
        raise HTTPException(404, "Unknown destination")
    summary, forecast = await asyncio.gather(
        places.wiki_summary(places.WIKI_TITLES.get(slug, d["name"])),
        weather.forecast(d["lat"], d["lon"], days=7),
    )
    return {
        "slug": slug, "name": d["name"], "state": d["state"], "lat": d["lat"], "lon": d["lon"], "tags": d["tags"],
        "summary": summary, "forecast": forecast, "best_time": best_time(d),
        "festivals": [{"name": n, "months": [MONTHS[m - 1] for m in ms], "note": note} for n, ms, note in d["festivals"]],
        "closed": [{"place": p, "day": day} for p, day in d["closed"]],
        "airports": [{"code": c, "name": AIRPORTS[c]["name"]} for c in d["airports"] if c in AIRPORTS],
        "stations": [{"code": c, "name": STATIONS[c]["name"]} for c in d["stations"] if c in STATIONS],
    }


@router.get("/explore/nearby")
async def explore_nearby(lat: float = Query(ge=6, le=37.5), lon: float = Query(ge=68, le=98),
                         kind: str = Query(pattern="^(attractions|restaurants|cafes|stays)$"),
                         user: User = Depends(get_current_user)):
    """Nearby places for a destination or the traveller's own location (India only)."""
    await enforce(f"nearby:{user.id}", 30, 60)
    if kind == "attractions":
        items = await places.wiki_nearby(lat, lon)
    else:
        items = await places.osm_nearby(lat, lon, kind)
    return {"kind": kind, "items": items[:24],
            "source": "Wikipedia" if kind == "attractions" else "OpenStreetMap contributors"}


# ---------------------------------------------------------------- Travel guide

@router.get("/guide")
async def guide(q: str | None = Query(default=None, max_length=200), user: User = Depends(get_current_user)):
    if q:
        return {"results": kb_search(q, k=8)}
    return {"results": [{"id": d["id"], "title": d["title"], "text": d["text"], "source": d["source"],
                         "verified": VERIFIED, "tags": d["tags"]} for d in DOCS]}
