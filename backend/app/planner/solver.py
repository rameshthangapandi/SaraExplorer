"""Constraint solver for whole trips (onward transport + stay + return transport).

The LLM never assembles a plan by itself: it hands the traveller's constraints to this solver, which
enumerates candidate combinations from the inventory, keeps only those that satisfy every hard constraint,
and returns the best one for the chosen objective. If nothing satisfies the constraints it says so and
explains which constraint is binding (e.g. "cheapest possible trip is ₹3,200 over budget").
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from itertools import product

from app.data.destinations import find_destination
from app.planner import groups
from app.providers import sandbox

# A waitlisted train is only treated as bookable when it is likely to confirm.
MIN_CONFIRM_CHANCE = 0.6
TOP_TRANSPORT = 12
TOP_HOTELS = 8


@dataclass
class TripRequest:
    origin: str
    destination: str
    depart: date
    nights: int = 3
    adults: int = 2
    mode: str = "any"                      # any | flight | train
    budget_total: int | None = None        # whole trip, all travellers
    hotel_max_per_night: int | None = None
    hotel_min_stars: int | None = None
    round_trip: bool = True
    objective: str = "balanced"            # cheapest | balanced | comfort
    traveller_type: str | None = None      # solo | couple | family | friends | seniors | business


@dataclass
class PlanResult:
    status: str                            # ok | infeasible | no_inventory
    out: dict | None = None
    back: dict | None = None
    stay: dict | None = None
    total: int | None = None
    reasons: list[str] = field(default_factory=list)
    min_possible_total: int | None = None
    candidates_checked: int = 0
    alternatives: list[dict] = field(default_factory=list)
    why: list[str] = field(default_factory=list)


def _transport(req: TripRequest, origin: str, dest: str, day: date, today: date) -> list[dict]:
    options: list[dict] = []
    if req.mode in ("any", "flight"):
        options += [{**f, "kind": "flight"} for f in sandbox.search_flights(origin, dest, day, req.adults, today)]
    if req.mode in ("any", "train"):
        for t in sandbox.search_trains(origin, dest, day, req.adults, today):
            if t["confirm_chance"] >= MIN_CONFIRM_CHANCE:
                options.append({**t, "kind": "train"})
    options.sort(key=lambda o: o["price_total"])
    return options[:TOP_TRANSPORT]


def _hotels(req: TripRequest, city: str) -> list[dict]:
    hotels = sandbox.search_hotels(city, req.depart, req.depart + timedelta(days=req.nights), req.adults,
                                   req.hotel_max_per_night)
    if req.hotel_min_stars:
        hotels = [h for h in hotels if h["stars"] >= req.hotel_min_stars]
    return [{**h, "kind": "hotel"} for h in hotels[:TOP_HOTELS]]


def _score(req: TripRequest, out: dict, back: dict | None, stay: dict) -> float:
    """Lower is better. Group preferences add rupee-equivalent bonuses/penalties; hard constraints are unaffected."""
    total = out["price_total"] + (back["price_total"] if back else 0) + stay["price_total"]
    if req.objective == "cheapest":
        return total
    hours = (out["duration_min"] + (back["duration_min"] if back else 0)) / 60
    quality = stay["stars"] * 900 + stay["rating"] * 1200
    group = 0
    if req.traveller_type:
        group -= groups.hotel_bonus(stay, req.traveller_type)[0]
        group += sum(groups.transport_penalty(l, req.traveller_type)[0] for l in (out, back) if l)
    if req.objective == "comfort":
        return total * 0.35 + hours * 120 - quality * 2 + group
    return total + hours * 180 - quality * 0.6 + group  # balanced: ₹180 per travel hour, small bonus for better stays


def explain_fit(req: TripRequest, out: dict, back: dict | None, stay: dict) -> list[str]:
    """Plain-language reasons why the chosen plan suits the traveller group."""
    g = groups.profile(req.traveller_type)
    if not g:
        return []
    why = []
    _, matched = groups.hotel_bonus(stay, req.traveller_type)
    if matched:
        why.append(f"Stay has {', '.join(m.lower() for m in matched)}")
    issues = [w for l in (out, back) if l for w in groups.transport_penalty(l, req.traveller_type)[1]]
    if not issues and (g["avoid_early"] or g["avoid_late"]):
        why.append("No very early or late-night travel")
    if g["min_train_class"] != "SL" and not any("class" in w for w in issues):
        legs = [l for l in (out, back) if l and "class" in l]
        if legs:
            why.append(f"Comfortable train class ({', '.join(sorted({l['class'] for l in legs}))})")
    return why


def relaxations(req: TripRequest, today: date) -> list[dict]:
    """Exact cheapest totals if one condition is relaxed (so the agent never has to estimate them)."""
    from dataclasses import replace
    options = []
    if req.mode != "any":
        options.append(("Allow both flights and trains", replace(req, mode="any")))
    if req.nights > 1:
        options.append((f"Stay {req.nights - 1} night{'s' if req.nights > 2 else ''} instead of {req.nights}", replace(req, nights=req.nights - 1)))
    if req.hotel_min_stars:
        options.append(("Remove the minimum hotel rating", replace(req, hotel_min_stars=None)))
    if req.hotel_max_per_night:
        options.append(("Remove the hotel price limit", replace(req, hotel_max_per_night=None)))
    if req.round_trip:
        options.append(("Book one way only", replace(req, round_trip=False)))
    out = []
    for label, r in options:
        res = solve(replace(r, budget_total=None, objective="cheapest"), today)
        if res.status == "ok":
            out.append({"change": label, "cheapest_total_inr": res.total,
                        "fits_budget": req.budget_total is None or res.total <= req.budget_total})
    return sorted(out, key=lambda a: a["cheapest_total_inr"])


def solve(req: TripRequest, today: date | None = None) -> PlanResult:
    today = today or date.today()
    dest = find_destination(req.destination)
    dest_name = dest["name"] if dest else req.destination
    ret_day = req.depart + timedelta(days=req.nights)

    outs = _transport(req, req.origin, dest_name, req.depart, today)
    backs = _transport(req, dest_name, req.origin, ret_day, today) if req.round_trip else [None]
    stays = _hotels(req, dest_name)

    missing = []
    if not outs:
        missing.append(f"no {req.mode if req.mode != 'any' else 'flight or train'} from {req.origin} to {dest_name} on {req.depart:%d %b}")
    if req.round_trip and not backs:
        missing.append(f"no return {req.mode if req.mode != 'any' else 'flight or train'} on {ret_day:%d %b}")
    if not stays:
        missing.append("no stay matching the hotel filters")
    if missing:
        return PlanResult(status="no_inventory", reasons=missing)

    best, best_score, cheapest, checked = None, None, None, 0
    for out, back, stay in product(outs, backs, stays):
        checked += 1
        total = out["price_total"] + (back["price_total"] if back else 0) + stay["price_total"]
        cheapest = total if cheapest is None else min(cheapest, total)
        if req.budget_total is not None and total > req.budget_total:
            continue
        s = _score(req, out, back, stay)
        if best_score is None or s < best_score:
            best, best_score = (out, back, stay, total), s

    if best is None:
        gap = cheapest - req.budget_total
        return PlanResult(status="infeasible", min_possible_total=cheapest, candidates_checked=checked,
                          alternatives=relaxations(req, today),
                          reasons=[f"The cheapest valid trip costs ₹{cheapest:,}, which is ₹{gap:,} over the "
                                   f"₹{req.budget_total:,} budget."])
    out, back, stay, total = best
    return PlanResult(status="ok", out=out, back=back, stay=stay, total=total, candidates_checked=checked,
                      min_possible_total=cheapest, why=explain_fit(req, out, back, stay))
