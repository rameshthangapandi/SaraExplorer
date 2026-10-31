"""Local transport comparison: city bus, metro, Rapido, Ola and Uber (bike, auto, cab, sedan, SUV).

Distances come from real geocoding (OpenStreetMap Nominatim) and coordinates; fares are estimated from each
service's typical fare structure (base fare, per-km and per-minute rates, peak and night multipliers), because
these companies do not offer free public fare APIs. Booking opens the operator's app or website."""

import math
from dataclasses import dataclass
from urllib.parse import quote

from app.planner.groups import profile

ROAD_FACTOR = 1.35          # road distance vs straight line
METRO_CITIES = {            # city: (lat, lon)
    "Delhi": (28.61, 77.21), "Mumbai": (19.08, 72.88), "Bengaluru": (12.97, 77.59), "Chennai": (13.08, 80.27),
    "Kolkata": (22.57, 88.36), "Hyderabad": (17.39, 78.49), "Jaipur": (26.91, 75.79), "Kochi": (9.97, 76.28),
    "Lucknow": (26.85, 80.95), "Pune": (18.52, 73.86), "Ahmedabad": (23.02, 72.57),
}


@dataclass(frozen=True)
class Service:
    provider: str
    product: str
    mode: str            # bus | metro | bike | auto | cab | sedan | suv
    base: float
    per_km: float
    per_min: float
    capacity: int
    speed_kmh: float     # typical city speed off-peak
    pickup_min: int
    max_bags: int
    peak_surge: float = 1.0
    night_mult: float = 1.0


SERVICES = [
    Service("City bus", "Ordinary / AC bus", "bus", 0, 0, 0, 40, 17, 12, 1),
    Service("Metro", "Metro rail", "metro", 0, 0, 0, 200, 33, 8, 2),
    Service("Rapido", "Bike", "bike", 15, 6.0, 0.5, 1, 26, 4, 0, 1.15, 1.0),
    Service("Uber", "Moto", "bike", 20, 6.5, 0.5, 1, 26, 5, 0, 1.25, 1.0),
    Service("Ola", "Bike", "bike", 15, 6.2, 0.5, 1, 26, 5, 0, 1.2, 1.0),
    Service("Rapido", "Auto", "auto", 25, 13.0, 1.0, 3, 22, 4, 2, 1.1, 1.5),
    Service("Ola", "Auto", "auto", 30, 14.0, 1.0, 3, 22, 5, 2, 1.2, 1.5),
    Service("Uber", "Auto", "auto", 28, 13.5, 1.0, 3, 22, 5, 2, 1.25, 1.5),
    Service("Rapido", "Cab Economy", "cab", 45, 13.0, 1.5, 4, 25, 6, 3, 1.2, 1.1),
    Service("Ola", "Mini", "cab", 50, 14.0, 1.5, 4, 25, 6, 3, 1.3, 1.1),
    Service("Uber", "Go", "cab", 55, 14.5, 1.5, 4, 25, 5, 3, 1.35, 1.1),
    Service("Ola", "Prime Sedan", "sedan", 70, 17.0, 2.0, 4, 26, 7, 4, 1.3, 1.1),
    Service("Uber", "Premier", "sedan", 75, 18.0, 2.0, 4, 26, 6, 4, 1.35, 1.1),
    Service("Ola", "Prime SUV", "suv", 90, 21.0, 2.5, 6, 25, 9, 6, 1.3, 1.1),
    Service("Uber", "XL", "suv", 95, 22.0, 2.5, 6, 25, 8, 6, 1.35, 1.1),
]

MODE_LABEL = {"bus": "Bus", "metro": "Metro", "bike": "Bike taxi", "auto": "Auto", "cab": "Cab", "sedan": "Sedan", "suv": "SUV"}


def haversine_km(a, b) -> float:
    r = 6371
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(b[1] - a[1]) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _metro_city(a, b) -> str | None:
    for city, c in METRO_CITIES.items():
        if haversine_km(a, c) < 15 and haversine_km(b, c) < 15:  # core network only
            return city
    return None


def _metro_fare(km: float) -> int:
    for limit, fare in ((2, 10), (5, 20), (12, 30), (21, 40), (32, 50)):
        if km <= limit:
            return fare
    return 60


def _bus_fare(km: float, hour: int) -> int:
    return int(max(10, round(km * 1.4)))


def _traffic(hour: int) -> float:
    if 8 <= hour < 11 or 17 <= hour < 21:
        return 0.65
    if 23 <= hour or hour < 6:
        return 1.25
    return 1.0


def _links(svc: Service, a, b) -> str:
    if svc.provider == "Uber":
        return ("https://m.uber.com/ul/?action=setPickup"
                f"&pickup[latitude]={a[0]}&pickup[longitude]={a[1]}&dropoff[latitude]={b[0]}&dropoff[longitude]={b[1]}")
    if svc.provider == "Ola":
        return "https://www.olacabs.com/"
    if svc.provider == "Rapido":
        return "https://www.rapido.bike/"
    return f"https://www.google.com/maps/dir/?api=1&origin={a[0]},{a[1]}&destination={b[0]},{b[1]}&travelmode=transit"


def compare(a: tuple[float, float], b: tuple[float, float], hour: int = 10, people: int = 1, bags: int = 0,
            priority: str = "value", traveller_type: str | None = None) -> dict:
    """Estimate every service for the ride and recommend one. a, b = (lat, lon)."""
    km = round(haversine_km(a, b) * ROAD_FACTOR, 1)
    traffic = _traffic(hour)
    peak = 8 <= hour < 11 or 17 <= hour < 21
    night = hour >= 23 or hour < 6
    metro_city = _metro_city(a, b)
    g = profile(traveller_type)
    options = []
    for svc in SERVICES:
        if svc.mode == "metro" and (not metro_city or km < 2 or night):
            continue
        if svc.mode == "bus" and (night or km > 60):
            continue
        if svc.mode == "bike" and (people > 2 or bags > svc.max_bags or night or km > 30):
            continue
        vehicles = 1 if svc.mode in ("bus", "metro") else math.ceil(people / svc.capacity)
        if svc.mode not in ("bus", "metro") and bags > svc.max_bags * vehicles:
            continue
        minutes = round(km / (svc.speed_kmh * traffic) * 60)
        if svc.mode == "metro":
            fare_each = _metro_fare(km)
            total = fare_each * people
        elif svc.mode == "bus":
            fare_each = _bus_fare(km, hour)
            total = fare_each * people
        else:
            mult = (svc.peak_surge if peak else 1.0) * (svc.night_mult if night else 1.0)
            per_vehicle = (svc.base + svc.per_km * km + svc.per_min * minutes) * mult
            total = per_vehicle * vehicles
        total = int(round(total / 5) * 5)
        wait = svc.pickup_min + (12 if svc.mode in ("bus", "metro") else 0)  # walk to and from the stop
        options.append({
            "provider": svc.provider, "product": svc.product, "mode": svc.mode, "mode_label": MODE_LABEL[svc.mode],
            "vehicles": vehicles, "fare_min": int(total * 0.92), "fare_max": int(total * 1.08), "fare": total,
            "per_person": round(total / people), "pickup_min": wait, "ride_min": minutes, "total_min": wait + minutes,
            "booking_url": _links(svc, a, b), "surge": peak and svc.peak_surge > 1 and svc.mode not in ("bus", "metro"),
            "night_fare": night and svc.night_mult > 1,
        })
    if not options:
        return {"distance_km": km, "options": [], "recommended": None}

    def value_score(o):
        score = o["per_person"] + 3.0 * o["total_min"]
        if priority == "cheapest":
            score = o["per_person"] + 0.2 * o["total_min"]
        elif priority == "fastest":
            score = o["total_min"] * 10 + o["per_person"] * 0.05
        elif priority == "comfort":
            score = {"suv": 0, "sedan": 10, "cab": 40, "auto": 200, "metro": 220, "bike": 300, "bus": 400}[o["mode"]] + o["per_person"] * 0.1
        if bags >= 2 and o["mode"] in ("bus", "metro", "auto"):
            score += 60 * bags  # carrying luggage on public transport or in an auto is uncomfortable
        if g:
            weight = 1.0 if priority in ("value", "comfort") else 0.3
            score += weight * g["ride_modes"].get(o["mode"], 0)
            if traveller_type in ("family", "seniors") and o["mode"] in ("bus", "metro"):
                score += 60 * weight
        return score

    options.sort(key=lambda o: o["per_person"])
    cheapest = options[0]
    fastest = min(options, key=lambda o: o["total_min"])
    best = min(options, key=value_score)
    for o in options:
        o["badges"] = [b for b, x in (("Cheapest", cheapest), ("Fastest", fastest), ("Recommended", best)) if o is x]
    reason = (f"{best['provider']} {best['product']}: about ₹{best['per_person']} per person and {best['total_min']} min door to door"
              + (f" for {people} people in {best['vehicles']} vehicle{'s' if best['vehicles'] > 1 else ''}" if people > 1 and best['mode'] not in ('bus', 'metro') else ""))
    if g:
        reason += f"; suits {g['label'].lower()}"
    if best is not cheapest:
        reason += f". Cheapest is {cheapest['provider']} {cheapest['product']} at ₹{cheapest['per_person']} per person"
    return {"distance_km": km, "hour": hour, "people": people, "bags": bags, "metro_city": metro_city,
            "peak": peak, "night": night, "options": options, "recommended": best, "reason": reason + "."}


def maps_link(name: str) -> str:
    return f"https://www.google.com/maps/search/?api=1&query={quote(name)}"
