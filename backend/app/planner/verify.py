"""Independent plan verifier (used by the solver's tests and the SaraBench evaluation).

Checks follow the TravelPlanner split into commonsense constraints (is the plan sensible and complete?)
and hard constraints (does it satisfy what the traveller asked for?)."""

from datetime import timedelta

from app.data.destinations import find_destination
from app.data.geo import AIRPORTS, STATIONS
from app.planner.solver import MIN_CONFIRM_CHANCE, TripRequest

COMMONSENSE = ["complete_plan", "valid_route_onward", "valid_route_return", "dates_consistent",
               "stay_in_destination", "travellers_consistent", "transport_bookable"]
HARD = ["within_budget", "nights_match", "mode_respected", "hotel_price_cap", "hotel_min_stars"]


def _city(code: str) -> str:
    return (AIRPORTS.get(code) or STATIONS.get(code) or {}).get("city", "").lower()


def _serves(code: str, place: str) -> bool:
    dest = find_destination(place)
    if dest and (code in dest["airports"] or code in dest["stations"]):
        return True
    return _city(code) == place.lower() or (dest is not None and _city(code) == dest["name"].lower())


def check(req: TripRequest, plan: dict | None) -> dict[str, bool]:
    """plan = {"out": option, "back": option|None, "stay": option}. Returns constraint -> passed."""
    r = {c: False for c in COMMONSENSE + HARD}
    if not plan or not plan.get("out") or not plan.get("stay") or (req.round_trip and not plan.get("back")):
        return r
    out, back, stay = plan["out"], plan.get("back"), plan["stay"]
    ret_day = (req.depart + timedelta(days=req.nights)).isoformat()
    dest = find_destination(req.destination)
    dest_name = dest["name"] if dest else req.destination
    legs = [out] + ([back] if back else [])

    r["complete_plan"] = True
    r["valid_route_onward"] = _serves(out["from"], req.origin) and _serves(out["to"], dest_name)
    r["valid_route_return"] = (back is None) or (_serves(back["from"], dest_name) and _serves(back["to"], req.origin))
    r["dates_consistent"] = (out["depart"][:10] == req.depart.isoformat()
                             and (back is None or back["depart"][:10] == ret_day)
                             and stay["check_in"] == req.depart.isoformat() and stay["check_out"] == ret_day)
    r["stay_in_destination"] = stay["city"].lower() == dest_name.lower()
    r["travellers_consistent"] = all(l["adults"] == req.adults for l in legs) and stay["guests"] == req.adults
    r["transport_bookable"] = all(l.get("confirm_chance", 1.0) >= MIN_CONFIRM_CHANCE for l in legs)

    total = sum(l["price_total"] for l in legs) + stay["price_total"]
    r["within_budget"] = req.budget_total is None or total <= req.budget_total
    r["nights_match"] = stay["nights"] == req.nights
    r["mode_respected"] = req.mode == "any" or all(("train_no" in l) == (req.mode == "train") for l in legs)
    r["hotel_price_cap"] = req.hotel_max_per_night is None or stay["price_per_night"] <= req.hotel_max_per_night
    r["hotel_min_stars"] = req.hotel_min_stars is None or stay["stars"] >= req.hotel_min_stars
    return r


def plan_total(plan: dict) -> int:
    legs = [plan["out"]] + ([plan["back"]] if plan.get("back") else [])
    return sum(l["price_total"] for l in legs) + plan["stay"]["price_total"]
