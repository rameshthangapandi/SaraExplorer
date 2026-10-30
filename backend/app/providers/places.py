"""Free place data (no API keys, no cost):

- Wikipedia REST / geosearch: destination photos + summaries, nearby attractions with photos.
- OpenStreetMap Nominatim: nearby restaurants, cafes and stays (real names, cuisine, hours).
  Nominatim's usage policy allows ~1 request/second with caching and an identifying User-Agent,
  so calls are serialised, spaced out and cached.

Restaurant photos and star ratings are not available from free sources (they need paid APIs such as
Google Places), so restaurants link to Google Maps for photos and reviews.
"""

import asyncio
import logging
import math
import re
import time
from urllib.parse import quote

import httpx

log = logging.getLogger(__name__)

UA = "SaraExplorer/0.1 (+https://github.com/rameshthangapandi/SaraExplorer)"
TTL = 24 * 3600
_cache: dict[str, tuple[float, object]] = {}
_nominatim_lock = asyncio.Lock()
_last_nominatim = 0.0

# Wikipedia article used for each destination's photo and summary.
WIKI_TITLES = {
    "goa": "Goa", "jaipur": "Hawa Mahal", "agra": "Taj Mahal", "delhi": "India Gate", "varanasi": "Ghats in Varanasi",
    "rishikesh": "Rishikesh", "manali": "Manali, Himachal Pradesh", "shimla": "Shimla", "leh": "Pangong Tso",
    "srinagar": "Dal Lake", "munnar": "Munnar", "alleppey": "Alappuzha", "kochi": "Fort Kochi",
    "udaipur": "Lake Pichola", "jaisalmer": "Jaisalmer Fort", "darjeeling": "Darjeeling", "gangtok": "Gangtok",
    "tawang": "Tawang Monastery", "shillong": "Shillong", "andaman": "Radhanagar Beach", "hampi": "Hampi",
    "mumbai": "Gateway of India", "kolkata": "Victoria Memorial, Kolkata", "rann-of-kutch": "Great Rann of Kutch",
    "amritsar": "Golden Temple", "puducherry": "Promenade Beach",
}

_NOT_PLACES = ("district", "bombing", "attack", "constituency", "election", "riot", "division", "tehsil",
               "lok sabha", "assembly", "massacre", "earthquake", "flood", "list of", "metropolitan region",
               "school", "college", "university", "institute", "hospital", "company", "bank", "neighbourhood",
               "neighborhood", "suburb", "village", "census town", "ward", "railway station", "metro station",
               "bus station", "airport", "office", "headquarters", "court", "police", "high-rise", "apartment",
               "residential", "locality", "area of", "town in", "city in", "municipal", "newspaper", "radio")
# Sights travellers actually visit.
_SIGHTS = ("fort", "palace", "mahal", "temple", "mandir", "mosque", "masjid", "church", "cathedral", "gurdwara",
           "monastery", "gompa", "museum", "gallery", "lake", "garden", "bagh", "park", "monument", "memorial",
           "tomb", "mausoleum", "gate", "ghat", "beach", "waterfall", "falls", "sanctuary", "national park", "zoo",
           "cave", "stepwell", "baori", "haveli", "observatory", "market", "bazaar", "viewpoint", "hill", "peak",
           "dam", "bridge", "heritage", "landmark", "tourist", "attraction", "stadium", "shrine", "dargah",
           "pilgrimage", "island", "valley", "pass", "glacier", "backwater", "lighthouse", "square", "chowk")


def is_sight(title: str, description: str) -> bool:
    text = f"{title} {description}".lower()
    return not any(w in text for w in _NOT_PLACES) and any(w in text for w in _SIGHTS)


def _get_cached(key: str):
    hit = _cache.get(key)
    if hit and hit[0] > time.time():
        return hit[1]
    return None


def _put(key: str, value) -> None:
    if len(_cache) > 2000:
        _cache.clear()
    _cache[key] = (time.time() + TTL, value)


def distance_m(lat1, lon1, lat2, lon2) -> int:
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return int(2 * r * math.asin(math.sqrt(a)))


async def wiki_summary(title: str) -> dict | None:
    key = f"wiki:{title}"
    cached = _get_cached(key)
    if cached is not None:
        return cached or None
    try:
        async with httpx.AsyncClient(timeout=10, headers={"User-Agent": UA}) as c:
            r = await c.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title.replace(' ', '_'))}")
            r.raise_for_status()
            d = r.json()
    except Exception as exc:
        log.info("wikipedia summary failed for %s: %s", title, exc)
        return None
    original = d.get("originalimage") or {}
    thumb = (d.get("thumbnail") or {}).get("source")
    # Originals can be several MB: use a 1280px rendition for large images.
    image = original.get("source")
    if thumb and original.get("width", 0) > 1280:
        image = re.sub(r"/\d+px-", "/1280px-", thumb)
    out = {
        "title": d.get("title"), "extract": d.get("extract", ""),
        "image": image or thumb,
        "thumb": (d.get("thumbnail") or {}).get("source"),
        "url": (d.get("content_urls") or {}).get("desktop", {}).get("page"),
    }
    _put(key, out)
    return out


async def wiki_nearby(lat: float, lon: float, radius: int = 10000, limit: int = 100) -> list[dict]:
    key = f"wikinear:{lat:.3f}:{lon:.3f}:{radius}"
    cached = _get_cached(key)
    if cached is not None:
        return cached
    params = {
        "action": "query", "format": "json", "generator": "geosearch", "ggscoord": f"{lat}|{lon}",
        "ggsradius": min(radius, 10000), "ggslimit": limit, "prop": "pageimages|description|coordinates|info",
        "piprop": "thumbnail", "pithumbsize": 480, "pilimit": 50, "colimit": "max", "inprop": "url",
    }
    try:
        async with httpx.AsyncClient(timeout=10, headers={"User-Agent": UA}) as c:
            r = await c.get("https://en.wikipedia.org/w/api.php", params=params)
            r.raise_for_status()
            pages = (r.json().get("query") or {}).get("pages", {}).values()
    except Exception as exc:
        log.info("wikipedia geosearch failed: %s", exc)
        return []
    out = []
    for p in pages:
        title = p.get("title", "")
        desc = p.get("description", "")
        if not p.get("coordinates") or not is_sight(title, desc):
            continue
        co = p["coordinates"][0]
        out.append({
            "name": title, "description": desc, "image": (p.get("thumbnail") or {}).get("source"),
            "lat": co["lat"], "lon": co["lon"], "distance_m": distance_m(lat, lon, co["lat"], co["lon"]),
            "url": p.get("fullurl"),
        })
    out.sort(key=lambda x: (x["image"] is None, x["distance_m"]))
    _put(key, out)
    return out


NOMINATIM_QUERY = {"restaurants": "restaurant", "cafes": "cafe", "stays": "hotel"}


async def osm_nearby(lat: float, lon: float, kind: str, km: float = 3.0) -> list[dict]:
    global _last_nominatim
    q = NOMINATIM_QUERY[kind]
    key = f"osm:{kind}:{lat:.3f}:{lon:.3f}:{km}"
    cached = _get_cached(key)
    if cached is not None:
        return cached
    dlat = km / 111
    dlon = km / (111 * max(math.cos(math.radians(lat)), 0.2))
    params = {"q": q, "format": "jsonv2", "limit": 30, "bounded": 1, "extratags": 1,
              "viewbox": f"{lon - dlon},{lat + dlat},{lon + dlon},{lat - dlat}"}
    async with _nominatim_lock:
        wait = 1.1 - (time.time() - _last_nominatim)
        if wait > 0:
            await asyncio.sleep(wait)
        try:
            async with httpx.AsyncClient(timeout=15, headers={"User-Agent": UA}) as c:
                r = await c.get("https://nominatim.openstreetmap.org/search", params=params)
                r.raise_for_status()
                rows = r.json()
        except Exception as exc:
            log.info("nominatim failed: %s", exc)
            return []
        finally:
            _last_nominatim = time.time()
    out = []
    for x in rows:
        name = x.get("name")
        if not name:
            continue
        tags = x.get("extratags") or {}
        plat, plon = float(x["lat"]), float(x["lon"])
        cuisine = (tags.get("cuisine") or "").replace(";", ", ").replace("_", " ")
        out.append({
            "name": name, "type": x.get("type"), "cuisine": cuisine or None,
            "vegetarian": tags.get("diet:vegetarian") in ("only", "yes"),
            "opening_hours": tags.get("opening_hours"), "phone": tags.get("phone") or tags.get("contact:phone"),
            "website": tags.get("website") or tags.get("contact:website"),
            "stars": tags.get("stars"),
            "lat": plat, "lon": plon, "distance_m": distance_m(lat, lon, plat, plon),
            "maps_url": f"https://www.google.com/maps/search/?api=1&query={quote(name)}%20{plat},{plon}",
        })
    out.sort(key=lambda p: p["distance_m"])
    _put(key, out)
    return out
