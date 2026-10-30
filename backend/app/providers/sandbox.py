"""Sandbox travel inventory: flights, trains and hotels.

Results are deterministic for the same query (seeded), and prices follow realistic patterns
(booking lead time, weekday, departure hour, festival peaks), so the Strategist has real signal.
Replace these functions with Duffel / LiteAPI / an IRCTC partner without changing the agent.
"""

import hashlib
import math
import random
from datetime import date, datetime, timedelta

from app.data.destinations import find_destination
from app.data.geo import AIRPORTS, STATIONS, normalise

AIRLINES = [("IndiGo", "6E"), ("Air India", "AI"), ("Akasa Air", "QP"), ("SpiceJet", "SG"), ("Air India Express", "IX")]

# Approximate high-demand windows (festivals, holidays). Extend yearly.
PEAK_WINDOWS = [
    (date(2026, 10, 16), date(2026, 10, 22), 1.30, "Durga Puja / Dussehra"),
    (date(2026, 11, 4), date(2026, 11, 12), 1.45, "Diwali"),
    (date(2026, 12, 20), date(2027, 1, 3), 1.60, "Christmas & New Year"),
    (date(2027, 3, 19), date(2027, 3, 23), 1.20, "Holi"),
    (date(2027, 5, 15), date(2027, 6, 15), 1.25, "Summer holidays"),
    (date(2027, 10, 6), date(2027, 10, 12), 1.30, "Durga Puja / Dussehra"),
    (date(2027, 10, 25), date(2027, 11, 2), 1.45, "Diwali"),
    (date(2027, 12, 20), date(2028, 1, 3), 1.60, "Christmas & New Year"),
]


def _rng(*parts) -> random.Random:
    seed = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()
    return random.Random(int(seed[:16], 16))


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def peak_for(d: date) -> tuple[float, str | None]:
    for start, end, mult, name in PEAK_WINDOWS:
        if start <= d <= end:
            return mult, name
    return 1.0, None


def lead_time_multiplier(days_ahead: int) -> float:
    if days_ahead < 3:
        return 1.90
    if days_ahead < 7:
        return 1.55
    if days_ahead < 14:
        return 1.25
    if days_ahead < 21:
        return 1.08
    if days_ahead <= 45:
        return 0.92
    if days_ahead <= 90:
        return 0.98
    return 1.05


WEEKDAY_MULT = [1.05, 0.92, 0.93, 1.00, 1.12, 0.97, 1.15]  # Mon..Sun


def hour_multiplier(hour: int) -> float:
    if hour < 7:
        return 0.88
    if hour < 10:
        return 1.12
    if hour < 17:
        return 0.98
    if hour < 21:
        return 1.10
    return 0.90


# ---------------------------------------------------------------- resolving places

def resolve_airports(place: str) -> list[str]:
    """City / destination / IATA code -> list of airport codes (closest first)."""
    text = place.strip()
    if text.upper() in AIRPORTS:
        return [text.upper()]
    key = normalise(text)
    codes = [c for c, a in AIRPORTS.items() if a["city"].lower() == key]
    if codes:
        return codes
    dest = find_destination(text)
    if dest:
        return [c for c in dest["airports"] if c in AIRPORTS]
    return []


def resolve_stations(place: str) -> list[str]:
    text = place.strip()
    if text.upper() in STATIONS:
        return [text.upper()]
    key = normalise(text)
    codes = [c for c, s in STATIONS.items() if s["city"].lower() == key]
    if codes:
        return codes
    dest = find_destination(text)
    if dest:
        return [c for c in dest["stations"] if c in STATIONS]
    return []


# ---------------------------------------------------------------- flights

def flight_price(base: float, travel: date, hour: int, booked_on: date, rng: random.Random | None = None) -> int:
    days_ahead = max((travel - booked_on).days, 0)
    mult = lead_time_multiplier(days_ahead) * WEEKDAY_MULT[travel.weekday()] * hour_multiplier(hour)
    mult *= peak_for(travel)[0]
    if rng:
        mult *= rng.uniform(0.94, 1.06)
    return int(round(base * mult / 10) * 10)


def search_flights(origin: str, dest: str, travel: date, adults: int = 1, today: date | None = None) -> list[dict]:
    today = today or date.today()
    results = []
    for o in resolve_airports(origin)[:1]:
        for d in resolve_airports(dest)[:2]:
            if o == d:
                continue
            a, b = AIRPORTS[o], AIRPORTS[d]
            km = haversine_km(a["lat"], a["lon"], b["lat"], b["lon"])
            nonstop = a["hub"] or b["hub"] or km < 900
            rng = _rng("flight", o, d, travel.isoformat())
            count = 6 if (a["hub"] and b["hub"]) else 4
            hours = sorted(rng.sample([5, 6, 7, 8, 9, 10, 12, 13, 15, 17, 18, 19, 20, 21, 22], count))
            base = 1800 + km * 2.4
            for h in hours:
                airline, code = rng.choice(AIRLINES)
                minute = rng.choice([0, 5, 15, 20, 30, 40, 45, 55])
                dep = datetime.combine(travel, datetime.min.time()).replace(hour=h, minute=minute)
                dur = int(km / 9.5 + 35) if nonstop else int(km / 9.5 + 35 + rng.choice([75, 95, 120, 150]))
                arr = dep + timedelta(minutes=dur)
                price = flight_price(base if nonstop else base * 0.9, travel, h, today, rng)
                results.append({
                    "airline": airline,
                    "flight_no": f"{code}-{rng.randint(100, 999)}",
                    "from": o, "from_city": a["city"], "to": d, "to_city": b["city"],
                    "depart": dep.isoformat(timespec="minutes"), "arrive": arr.isoformat(timespec="minutes"),
                    "duration_min": dur, "stops": 0 if nonstop else 1,
                    "via": None if nonstop else rng.choice(["DEL", "BOM", "BLR", "HYD"]),
                    "price_per_person": price, "price_total": price * adults, "adults": adults,
                    "refundable": rng.random() < 0.3, "date": travel.isoformat(),
                })
    return sorted(results, key=lambda f: f["price_total"])


# ---------------------------------------------------------------- trains

TRAIN_TYPES = [("Rajdhani Express", 1.25, 68), ("Superfast Express", 1.0, 58), ("Vande Bharat Express", 1.35, 80),
               ("Mail Express", 0.9, 50), ("Duronto Express", 1.2, 66)]
CLASS_RATE = {"SL": 0.55, "3A": 1.40, "2A": 2.05, "1A": 3.40, "CC": 1.25}


def waitlist_confirm_chance(wl: int, days_ahead: int, peak: float) -> float:
    chance = 0.97 - wl * 0.028 + min(days_ahead, 60) * 0.004 - (peak - 1) * 0.5
    return round(max(0.05, min(0.97, chance)), 2)


def search_trains(origin: str, dest: str, travel: date, adults: int = 1, today: date | None = None) -> list[dict]:
    today = today or date.today()
    os_, ds = resolve_stations(origin), resolve_stations(dest)
    if not os_ or not ds or os_[0] == ds[0]:
        return []
    o, d = os_[0], ds[0]
    a, b = STATIONS[o], STATIONS[d]
    km = haversine_km(a["lat"], a["lon"], b["lat"], b["lon"]) * 1.25  # rail distance > straight line
    if km > 3200:
        return []
    rng = _rng("train", o, d, travel.isoformat())
    days_ahead = max((travel - today).days, 0)
    peak, _ = peak_for(travel)
    results = []
    for kind, fare_mult, speed in rng.sample(TRAIN_TYPES, 3):
        if kind == "Vande Bharat Express" and km > 900:
            continue
        hour = rng.choice([6, 9, 14, 16, 17, 19, 20, 22])
        dep = datetime.combine(travel, datetime.min.time()).replace(hour=hour, minute=rng.choice([0, 10, 25, 40, 55]))
        dur = int(km / speed * 60)
        classes = ["CC"] if kind == "Vande Bharat Express" else (["3A", "2A", "1A"] if "Rajdhani" in kind or "Duronto" in kind else ["SL", "3A", "2A"])
        number = rng.randint(12001, 22999)
        for cls in classes:
            fare = int(round(max(180, km * CLASS_RATE[cls] * fare_mult) / 5) * 5)
            # Availability gets worse closer to departure and in peak periods.
            pressure = rng.random() + (1 - min(days_ahead, 60) / 60) * 0.6 + (peak - 1)
            if pressure < 0.7:
                status, wl = f"AVAILABLE {rng.randint(8, 120)}", 0
            elif pressure < 1.0:
                status, wl = f"RAC {rng.randint(1, 30)}", 0
            else:
                wl = rng.randint(2, 60)
                status = f"WL {wl}"
            results.append({
                "train_name": f"{a['city']}–{b['city']} {kind}", "train_no": str(number), "class": cls,
                "from": o, "from_name": a["name"], "to": d, "to_name": b["name"],
                "depart": dep.isoformat(timespec="minutes"),
                "arrive": (dep + timedelta(minutes=dur)).isoformat(timespec="minutes"),
                "duration_min": dur, "fare_per_person": fare, "price_total": fare * adults, "adults": adults,
                "availability": status,
                "confirm_chance": 1.0 if wl == 0 else waitlist_confirm_chance(wl, days_ahead, peak),
                "date": travel.isoformat(),
            })
    return sorted(results, key=lambda t: (t["depart"], t["price_total"]))


# ---------------------------------------------------------------- hotels

HOTEL_NAMES = ["Saffron Courtyard", "Banyan Retreat", "Peacock Residency", "Monsoon House", "Indigo Haveli",
               "Mustard Tree Inn", "Sandalwood Suites", "Lotus Bay Resort", "Neem Garden Stay", "Copper Lantern Hotel",
               "Riverstone Lodge", "Old Fort View Hotel"]
AMENITIES = ["Free Wi-Fi", "Breakfast included", "Pool", "Airport pickup", "Pure-veg restaurant", "Spa",
             "Family rooms", "Mountain view", "Lake view", "Free cancellation", "Parking", "Lift"]


def search_hotels(city: str, check_in: date, check_out: date, guests: int = 2,
                  max_per_night: int | None = None) -> list[dict]:
    dest = find_destination(city)
    name = dest["name"] if dest else city.strip().title()
    base = dest["hotel_base"] if dest else 3000
    rating_this_month = dest["ratings"][check_in.month - 1] if dest else 3
    nights = max((check_out - check_in).days, 1)
    rng = _rng("hotel", name, check_in.isoformat(), check_out.isoformat())
    rooms = max(1, math.ceil(guests / 2))
    season = 0.75 + rating_this_month * 0.1
    peak, _ = peak_for(check_in)
    results = []
    for hotel in rng.sample(HOTEL_NAMES, 6):
        stars = rng.choice([3, 3, 4, 4, 5])
        nightly = 0
        for i in range(nights):
            day = check_in + timedelta(days=i)
            weekend = 1.15 if day.weekday() in (4, 5) else 1.0
            nightly += base * (0.6 + stars * 0.25) * season * peak * weekend * rng.uniform(0.9, 1.1)
        per_night = int(round(nightly / nights / 10) * 10)
        if max_per_night and per_night > max_per_night:
            continue
        results.append({
            "hotel": f"{hotel}, {name}", "city": name, "stars": stars,
            "rating": round(rng.uniform(3.8, 4.8), 1), "reviews": rng.randint(120, 3400),
            "amenities": rng.sample(AMENITIES, 4), "check_in": check_in.isoformat(), "check_out": check_out.isoformat(),
            "nights": nights, "rooms": rooms, "guests": guests,
            "price_per_night": per_night, "price_total": per_night * nights * rooms,
            "free_cancellation_until": (check_in - timedelta(days=2)).isoformat() if rng.random() < 0.6 else None,
        })
    return sorted(results, key=lambda h: h["price_total"])
