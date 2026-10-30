"""Live forecast from Open-Meteo (free, no key). Falls back to curated climate ratings."""

import logging
from datetime import date

import httpx

log = logging.getLogger(__name__)

WMO = {0: "Clear", 1: "Mostly clear", 2: "Partly cloudy", 3: "Overcast", 45: "Fog", 48: "Fog", 51: "Drizzle",
       53: "Drizzle", 55: "Drizzle", 61: "Light rain", 63: "Rain", 65: "Heavy rain", 71: "Snow", 73: "Snow",
       75: "Heavy snow", 80: "Showers", 81: "Showers", 82: "Heavy showers", 95: "Thunderstorm", 96: "Thunderstorm",
       99: "Thunderstorm"}


async def forecast(lat: float, lon: float, start: date | None = None, days: int = 7) -> list[dict] | None:
    params = {
        "latitude": lat, "longitude": lon, "timezone": "Asia/Kolkata",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "forecast_days": 16,
    }
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get("https://api.open-meteo.com/v1/forecast", params=params)
            r.raise_for_status()
            daily = r.json()["daily"]
    except Exception as exc:
        log.info("Open-Meteo unavailable: %s", exc)
        return None
    out = []
    for i, day in enumerate(daily["time"]):
        if start and day < start.isoformat():
            continue
        out.append({
            "date": day,
            "summary": WMO.get(daily["weather_code"][i], "Mixed"),
            "max_c": daily["temperature_2m_max"][i],
            "min_c": daily["temperature_2m_min"][i],
            "rain_chance": daily["precipitation_probability_max"][i],
        })
        if len(out) >= days:
            break
    return out
