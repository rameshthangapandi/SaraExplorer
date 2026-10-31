from datetime import date, timedelta

from app.planner.solver import TripRequest, solve
from app.planner.verify import COMMONSENSE, HARD, check, plan_total

D = date.today() + timedelta(days=30)


def _plan(res):
    return {"out": res.out, "back": res.back, "stay": res.stay}


def test_solver_plan_satisfies_every_constraint():
    req = TripRequest("Delhi", "goa", D, nights=4, adults=2, budget_total=60000, hotel_min_stars=4)
    res = solve(req)
    assert res.status == "ok"
    checks = check(req, _plan(res))
    assert all(checks[c] for c in COMMONSENSE + HARD), checks
    assert plan_total(_plan(res)) == res.total <= 60000


def test_train_only_mode():
    res = solve(TripRequest("Mumbai", "jaipur", D, nights=2, adults=1, mode="train"))
    assert res.status == "ok" and "train_no" in res.out and "train_no" in res.back


def test_infeasible_budget_is_detected_with_reason():
    res = solve(TripRequest("Delhi", "goa", D, nights=5, adults=4, budget_total=3000))
    assert res.status == "infeasible" and res.min_possible_total > 3000 and "over the" in res.reasons[0]


def test_cheapest_objective_is_minimal():
    req = TripRequest("Delhi", "jaipur", D, nights=2, adults=2, objective="cheapest")
    assert solve(req).total == solve(req).min_possible_total


async def test_auto_plan_api(client):
    from tests.conftest import register
    data = await register(client, "planner-api@example.com")
    auth = {"Authorization": f"Bearer {data['access_token']}"}
    r = await client.post("/api/plan/auto", headers=auth, json={"origin": "Delhi", "destination": "goa",
                          "depart": D.isoformat(), "nights": 3, "adults": 2, "budget_total": 80000})
    body = r.json()
    assert r.status_code == 200 and body["status"] == "ok" and body["plan"]["stay"]["id"].startswith("HT-")
    ids = [body["plan"]["out"]["id"], body["plan"]["back"]["id"], body["plan"]["stay"]["id"]]
    c = await client.post("/api/consents", headers=auth, json={"option_ids": ids, "title": "Auto plan"})
    assert c.status_code == 201 and c.json()["total_inr"] == body["total"]
