"""SaraBench-IN: TravelPlanner-style evaluation of Sara Explorer on Indian trips.

Systems
  solver    Sara Explorer constraint solver (no LLM)                         -> all queries
  agent     Ask Sara: LLM agent (gpt-oss-120b on Groq) with tools + solver   -> sampled queries
  llm_only  same LLM, given the candidate options, plans without the solver  -> sampled queries

Metrics (as in TravelPlanner, Xie et al. 2024): delivery rate, commonsense / hard constraint pass rate
(micro = share of checks passed, macro = share of plans passing all), final pass rate. Extra: detection of
unsatisfiable requests, exactness of the stated total price, latency.

Usage:  python -m benchmarks.sarabench --systems solver,llm_only,agent --n 300 --llm-n 30 --agent-n 15
"""

import argparse
import asyncio
import json
import os
import random
import re
import sys
import tempfile
import time
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{tempfile.mkdtemp()}/bench.db")
os.environ.setdefault("JWT_SECRET", "benchmark-secret-" + "x" * 32)
os.environ.setdefault("REDIS_URL", "")
sys.path.insert(0, str(ROOT.parent))

from app.planner.solver import TripRequest, solve  # noqa: E402
from app.planner.verify import COMMONSENSE, HARD, check, plan_total  # noqa: E402

ORIGINS = ["Delhi", "Mumbai", "Bengaluru", "Chennai", "Kolkata", "Hyderabad", "Pune", "Ahmedabad", "Jaipur",
           "Lucknow", "Kochi", "Guwahati"]
DESTS = ["goa", "jaipur", "agra", "delhi", "varanasi", "rishikesh", "manali", "shimla", "leh", "srinagar", "munnar",
         "alleppey", "kochi", "udaipur", "jaisalmer", "darjeeling", "gangtok", "shillong", "andaman", "hampi", "mumbai",
         "kolkata", "rann-of-kutch", "amritsar", "puducherry", "tawang"]
TODAY = date.today()


# ------------------------------------------------------------------ queries

def make_queries(n: int, seed: int = 2026) -> list[dict]:
    rng = random.Random(seed)
    out, attempts = [], 0
    while len(out) < n and attempts < n * 20:
        attempts += 1
        level = rng.choices(["easy", "medium", "hard"], weights=[1, 1, 1])[0]
        origin, dest = rng.choice(ORIGINS), rng.choice(DESTS)
        if dest.replace("-", " ") in origin.lower():
            continue
        req = TripRequest(origin=origin, destination=dest, depart=TODAY + timedelta(days=rng.randint(10, 120)),
                          nights=rng.randint(1, 6), adults=rng.randint(1, 5))
        if level in ("medium", "hard"):
            if rng.random() < 0.5:
                req.mode = rng.choice(["flight", "train"])
            else:
                req.hotel_min_stars = rng.choice([3, 4])
        if level == "hard":
            req.mode = req.mode if req.mode != "any" else rng.choice(["flight", "train"])
            req.hotel_min_stars = req.hotel_min_stars or rng.choice([3, 4])
            req.hotel_max_per_night = rng.choice([6000, 9000, 14000])
        oracle = solve(TripRequest(**{**asdict(req), "objective": "cheapest"}), TODAY)
        if oracle.status != "ok":
            continue  # route not served under these filters: not a meaningful query
        infeasible = rng.random() < 0.12
        factor = rng.uniform(0.6, 0.92) if infeasible else rng.choice([1.03, 1.15, 1.35, 1.8])
        req.budget_total = int(round(oracle.total * factor, -2))
        if infeasible and req.budget_total >= oracle.total:
            req.budget_total = oracle.total - 100
        out.append({"id": f"Q{len(out) + 1:03d}", "level": level, "feasible": not infeasible,
                    "oracle_min_total": oracle.total, "request": {**asdict(req), "depart": req.depart.isoformat()}})
    return out


def to_req(q: dict) -> TripRequest:
    r = dict(q["request"])
    r["depart"] = date.fromisoformat(r["depart"])
    return TripRequest(**r)


def describe(q: dict) -> str:
    r = q["request"]
    parts = [f"Plan a round trip from {r['origin']} to {r['destination'].replace('-', ' ').title()} departing {r['depart']} "
             f"for {r['nights']} night(s), {r['adults']} adult(s)."]
    parts.append(f"Total budget for everything (all travellers): ₹{r['budget_total']:,}.")
    if r["mode"] != "any":
        parts.append(f"Travel by {r['mode']} only, both ways.")
    if r["hotel_min_stars"]:
        parts.append(f"Hotel must be at least {r['hotel_min_stars']} stars.")
    if r["hotel_max_per_night"]:
        parts.append(f"Hotel must cost at most ₹{r['hotel_max_per_night']:,} per night.")
    return " ".join(parts)


# ------------------------------------------------------------------ scoring

def score(q: dict, plan: dict | None, declared_infeasible: bool) -> dict:
    req = to_req(q)
    if not q["feasible"]:
        ok = declared_infeasible and plan is None
        return {"delivered": ok or plan is not None, "final": ok, "unsat_correct": ok, "checks": None}
    checks = check(req, plan) if plan else {c: False for c in COMMONSENSE + HARD}
    return {"delivered": plan is not None, "checks": checks, "unsat_correct": None,
            "final": plan is not None and all(checks.values())}


def summarize(name: str, rows: list[dict]) -> dict:
    feas = [r for r in rows if r["feasible"]]
    infe = [r for r in rows if not r["feasible"]]

    def micro(keys):
        tot = sum(len(keys) for _ in feas)
        return 100 * sum(sum(r["checks"][k] for k in keys) for r in feas) / tot if tot else 0

    def macro(keys):
        return 100 * sum(all(r["checks"][k] for k in keys) for r in feas) / len(feas) if feas else 0

    lat = sorted(r["latency_s"] for r in rows)
    by_level = {}
    for lvl in ("easy", "medium", "hard"):
        sub = [r for r in rows if r["level"] == lvl]
        by_level[lvl] = round(100 * sum(r["final"] for r in sub) / len(sub), 1) if sub else None
    per_constraint = {k: round(100 * sum(r["checks"][k] for r in feas) / len(feas), 1) for k in COMMONSENSE + HARD} if feas else {}
    price = [r["price_exact"] for r in rows if r.get("price_exact") is not None]
    ground = [r["grounded"] for r in rows if r.get("grounded") is not None]
    ground_pre = [r["grounded_before_guard"] for r in rows if r.get("grounded_before_guard") is not None]
    return {
        "system": name, "n": len(rows), "n_feasible": len(feas), "n_infeasible": len(infe),
        "delivery_rate": round(100 * sum(r["delivered"] for r in rows) / len(rows), 1),
        "commonsense_micro": round(micro(COMMONSENSE), 1), "commonsense_macro": round(macro(COMMONSENSE), 1),
        "hard_micro": round(micro(HARD), 1), "hard_macro": round(macro(HARD), 1),
        "final_pass_rate": round(100 * sum(r["final"] for r in rows) / len(rows), 1),
        "unsat_detection": round(100 * sum(r["unsat_correct"] for r in infe) / len(infe), 1) if infe else None,
        "price_exact": round(100 * sum(price) / len(price), 1) if price else None,
        "price_grounded": round(100 * sum(ground) / len(ground), 1) if ground else None,
        "price_grounded_before_guard": round(100 * sum(ground_pre) / len(ground_pre), 1) if ground_pre else None,
        "by_level": by_level, "per_constraint": per_constraint,
        "latency_median_s": round(lat[len(lat) // 2], 3), "latency_p90_s": round(lat[int(len(lat) * 0.9) - 1], 3),
        "latency_median_ms": round(lat[len(lat) // 2] * 1000, 3), "latency_p90_ms": round(lat[int(len(lat) * 0.9) - 1] * 1000, 3),
    }


# ------------------------------------------------------------------ systems

def run_solver(queries):
    rows = []
    for q in queries:
        t = time.perf_counter()
        res = solve(to_req(q), TODAY)
        dt = time.perf_counter() - t
        plan = {"out": res.out, "back": res.back, "stay": res.stay} if res.status == "ok" else None
        s = score(q, plan, res.status == "infeasible")
        rows.append({**s, "id": q["id"], "level": q["level"], "feasible": q["feasible"], "latency_s": dt,
                     "price_exact": None if plan is None else (res.total == plan_total(plan))})
    return rows


def candidates(q: dict) -> dict:
    """The same inventory the solver sees (top options per leg), for the LLM-only baseline."""
    from app.planner import solver as S
    req = to_req(q)
    dest = S.find_destination(req.destination)["name"]
    ret = req.depart + timedelta(days=req.nights)
    allmode = TripRequest(**{**asdict(req), "mode": "any", "hotel_min_stars": None, "hotel_max_per_night": None})
    return {"out": S._transport(allmode, req.origin, dest, req.depart, TODAY)[:10],
            "back": S._transport(allmode, dest, req.origin, ret, TODAY)[:10],
            "stay": S._hotels(TripRequest(**{**asdict(allmode)}), dest)[:8]}


def _opt_line(i: str, o: dict) -> str:
    if o["kind"] == "hotel":
        return (f"{i}: hotel {o['hotel']} | {o['stars']} stars | rating {o['rating']} | ₹{o['price_per_night']}/night | "
                f"check-in {o['check_in']} check-out {o['check_out']} | {o['nights']} nights | guests {o['guests']} | total ₹{o['price_total']}")
    name = o.get("airline", o.get("train_name"))
    extra = f"train {o['class']} {o['availability']} confirm-chance {o['confirm_chance']}" if o["kind"] == "train" else f"flight {o['flight_no']}"
    return (f"{i}: {o['kind']} {name} | {extra} | {o['from']}->{o['to']} | departs {o['depart']} | "
            f"{o['adults']} adults | total ₹{o['price_total']}")


async def _llm(messages, json_mode=True):
    from groq import RateLimitError
    from app.agents.sara import client
    from app.config import get_settings
    s = get_settings()
    for attempt in range(8):
        try:
            r = await client().chat.completions.create(
                model=s.groq_chat_model, messages=messages, temperature=0.2, max_completion_tokens=4096,
                extra_body={"reasoning_effort": s.groq_reasoning_effort},
                **({"response_format": {"type": "json_object"}} if json_mode else {}))
            return r.choices[0].message.content or ""
        except RateLimitError as exc:
            if "per day" in str(exc).lower():
                raise
            await asyncio.sleep(20 * (attempt + 1))
    raise RuntimeError("rate limited")


async def run_llm_only(queries):
    rows = []
    for q in queries:
        c = candidates(q)
        ids = {}
        lines = []
        for leg, opts in (("out", c["out"]), ("back", c["back"]), ("stay", c["stay"])):
            lines.append({"out": "ONWARD OPTIONS", "back": "RETURN OPTIONS", "stay": "HOTEL OPTIONS"}[leg])
            for k, o in enumerate(opts):
                key = f"{leg[0].upper()}{k + 1}"
                ids[key] = (leg, o)
                lines.append(_opt_line(key, o))
        prompt = (describe(q) + "\n\n" + "\n".join(lines) +
                  "\n\nChoose exactly one onward option, one return option and one hotel that satisfy ALL the "
                  "constraints. A train with confirm-chance below 0.6 is not bookable. Reply as JSON: "
                  '{"onward": "O?", "return": "R?", "hotel": "H?", "total_inr": <sum>} or {"infeasible": true, '
                  '"reason": "..."} if no combination satisfies every constraint.')
        t = time.perf_counter()
        try:
            raw = await _llm([{"role": "system", "content": "You are an expert travel planner. Be exact with constraints and arithmetic."},
                              {"role": "user", "content": prompt}])
        except Exception as exc:  # daily limit reached: stop and keep what we have
            print("llm_only stopped:", exc)
            break
        dt = time.perf_counter() - t
        try:
            ans = json.loads(raw)
        except json.JSONDecodeError:
            ans = {}
        plan, declared = None, bool(ans.get("infeasible"))
        if not declared and all(ans.get(k) in ids for k in ("onward", "return", "hotel")):
            plan = {"out": ids[ans["onward"]][1], "back": ids[ans["return"]][1], "stay": ids[ans["hotel"]][1]}
            if ids[ans["onward"]][0] != "out" or ids[ans["return"]][0] != "back" or ids[ans["hotel"]][0] != "stay":
                plan = None
        s = score(q, plan, declared)
        exact = None if plan is None else (str(ans.get("total_inr", "")).replace(",", "") == str(plan_total(plan)))
        rows.append({**s, "id": q["id"], "level": q["level"], "feasible": q["feasible"], "latency_s": dt, "price_exact": exact})
        print(f"llm_only {q['id']} final={s['final']} ({len(rows)}/{len(queries)})", flush=True)
    return rows


async def run_agent(queries):
    from app.agents.sara import graph
    from app.agents.tools import ToolContext
    from app.db import SessionLocal, init_db
    from app.models import SearchOption, User, uid
    from sqlalchemy import select

    await init_db()
    async with SessionLocal() as db:
        user = User(id=uid(), email=f"bench{uid()[:6]}@example.com", name="Bench", password_hash="x", spend_cap_inr=5_000_000)
        db.add(user)
        await db.commit()
    rows = []
    for q in queries:
        state = {"messages": [{"role": "user", "content": describe(q) + " Find the best plan; do not book yet."}],
                 "steps": 0, "cards": [], "notes": []}
        text, cards, numbers, guard = "", [], set(), None
        t = time.perf_counter()
        try:
            async for ev in graph.astream(state, {"configurable": {"ctx": ToolContext(user_id=user.id)}, "recursion_limit": 20},
                                          stream_mode="custom"):
                if ev["type"] == "token":
                    text += ev["text"]
                elif ev["type"] == "replace":
                    text = ev["text"]
                elif ev["type"] == "grounding":
                    guard = ev
                elif ev["type"] == "card":
                    cards.append(ev["card"])
        except Exception as exc:
            print("agent stopped:", exc)
            if "per day" in str(exc).lower():
                break
            continue
        dt = time.perf_counter() - t
        plan, declared = None, False
        for c in cards:
            numbers |= {int(x) for x in re.findall(r"\b\d{3,7}\b", json.dumps(c))}
            if c["type"] == "autoplan" and c["status"] == "ok":
                p = c["plan"]
                plan = {"out": p["out"], "back": p["back"], "stay": p["stay"]}
                numbers.add(c["total"])
            if c["type"] == "autoplan" and c["status"] == "infeasible":
                declared = True
        if plan is None:  # agent may have composed a plan from searches + propose_booking instead
            for c in cards:
                if c["type"] == "consent":
                    async with SessionLocal() as db:
                        ids = [i.get("option_id") for i in c.get("items", [])]
                        opts = (await db.scalars(select(SearchOption).where(SearchOption.id.in_([i for i in ids if i])))).all()
                    legs = {o.kind: o.data for o in opts}
                    if legs:
                        plan = {"out": legs.get("flight") or legs.get("train"), "back": None, "stay": legs.get("hotel")}
        from app.agents.grounding import ungrounded as _ung
        base = set(guard["base"]) if guard else numbers
        bad_after = _ung(text, base)
        grounded = not bad_after
        grounded_before = None if guard is None else not guard["bad_before"]
        ungrounded = bad_after
        s = score(q, plan, declared)
        rows.append({**s, "id": q["id"], "level": q["level"], "feasible": q["feasible"], "latency_s": dt,
                     "price_exact": None if plan is None else True, "grounded": grounded,
                     "ungrounded": ungrounded, "grounded_before_guard": grounded_before, "text": text[:4000]})
        print(f"agent {q['id']} final={s['final']} grounded={grounded} ({len(rows)}/{len(queries)})", flush=True)
    return rows


# ------------------------------------------------------------------ main

def sample(queries, k, seed):
    """Stratified sample keeping the share of levels and infeasible queries."""
    rng = random.Random(seed)
    infeasible = [q for q in queries if not q["feasible"]]
    feasible = [q for q in queries if q["feasible"]]
    n_inf = max(1, round(k * len(infeasible) / len(queries)))
    pick = rng.sample(infeasible, min(n_inf, len(infeasible)))
    for lvl in ("easy", "medium", "hard"):
        pool = [q for q in feasible if q["level"] == lvl]
        pick += rng.sample(pool, min(len(pool), (k - n_inf) // 3))
    return sorted(pick, key=lambda q: q["id"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--systems", default="solver")
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--llm-n", type=int, default=30)
    ap.add_argument("--agent-n", type=int, default=15)
    a = ap.parse_args()

    qfile = RESULTS / "queries.json"
    if qfile.exists():
        queries = json.loads(qfile.read_text())
    else:
        queries = make_queries(a.n)
        qfile.write_text(json.dumps(queries, indent=1))
    print(f"{len(queries)} queries ({sum(not q['feasible'] for q in queries)} unsatisfiable)")

    for name in a.systems.split(","):
        if name == "solver":
            rows = run_solver(queries)
        elif name == "llm_only":
            rows = asyncio.run(run_llm_only(sample(queries, a.llm_n, 7)))
        elif name == "agent":
            rows = asyncio.run(run_agent(sample(queries, a.agent_n, 11)))
        else:
            raise SystemExit(f"unknown system {name}")
        if not rows:
            continue
        summary = summarize(name, rows)
        (RESULTS / f"{name}.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=1, default=str))
        print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
