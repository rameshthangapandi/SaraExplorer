import logging
from datetime import date

from app.data.destinations import DESTINATIONS, MONTHS
from app.providers.sandbox import PEAK_WINDOWS
from app.strategist.base import REGISTRY, Suggestion, TripContext

# Importing the modules registers the strategies.
from app.strategist.strategies import experience, group, money, risk, timing  # noqa: F401

log = logging.getLogger(__name__)


def advise(ctx: TripContext, limit: int = 5) -> list[Suggestion]:
    suggestions: list[Suggestion] = []
    for strategy in REGISTRY:
        try:
            if strategy.applies_to(ctx):
                suggestions.extend(strategy.suggest(ctx))
        except Exception:
            log.exception("strategy %s failed", strategy.name)
    suggestions.sort(key=lambda s: s.score * s.confidence, reverse=True)
    return suggestions[:limit]


def best_time(dest: dict) -> dict:
    months = []
    for i, rating in enumerate(dest["ratings"], 1):
        months.append({
            "month": i, "name": MONTHS[i - 1], "rating": rating, "peak": i in dest["peak"],
            "festivals": [f for f, ms, _ in dest["festivals"] if i in ms],
        })
    value = [m for m in months if m["rating"] >= 4 and not m["peak"]]
    return {
        "destination": dest["name"], "slug": dest["slug"], "state": dest["state"], "months": months,
        "best_value_months": [m["name"] for m in value],
        "tips": dest["tips"], "permit": dest["permit"],
    }


def where_to_go(month: int, interest: str | None = None, limit: int = 6, traveller_type: str | None = None) -> list[dict]:
    from app.planner.groups import destination_fit
    ranked = []
    for d in DESTINATIONS.values():
        if interest and interest.lower() not in " ".join(d["tags"] + [d["terrain"]]):
            continue
        rating = d["ratings"][month - 1]
        fit = destination_fit(d, traveller_type)
        if rating < 4 or fit < 0:
            continue
        crowd_penalty = 0.5 if month in d["peak"] else 0
        ranked.append({"slug": d["slug"], "name": d["name"], "state": d["state"], "rating": rating,
                       "peak": month in d["peak"], "tags": d["tags"], "fit": fit,
                       "score": rating - crowd_penalty + 0.3 * fit})
    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked[:limit]


def avoid_in(month: int) -> list[str]:
    return [d["name"] for d in DESTINATIONS.values() if d["ratings"][month - 1] <= 2]


def upcoming_peaks(today: date | None = None) -> list[dict]:
    today = today or date.today()
    return [{"name": n, "start": s.isoformat(), "end": e.isoformat(), "fare_increase_pct": int((m - 1) * 100)}
            for s, e, m, n in PEAK_WINDOWS if e >= today][:4]
