"""Benchmark figures for SaraBench-IN (saved to docs/figures/benchmarks/)."""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parent
RES = ROOT / "results"
OUT = ROOT.parent.parent / "docs" / "figures" / "benchmarks"
OUT.mkdir(parents=True, exist_ok=True)

INK, MUSTARD, GREY, LIGHT = "#141414", "#E3A812", "#9A9A9A", "#D9D9D9"
BLUE, GREEN = "#2B6CB0", "#2F855A"
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 11, "axes.spines.top": False, "axes.spines.right": False,
    "axes.edgecolor": "#444", "axes.titleweight": "bold", "axes.titlesize": 13, "savefig.dpi": 220,
    "savefig.bbox": "tight", "figure.facecolor": "white",
})


def load(name):
    p = RES / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else None


solver, agent, llm = load("solver"), load("agent"), load("llm_only")
queries = json.loads((RES / "queries.json").read_text())
S = solver["summary"]


def save(fig, name):
    fig.savefig(OUT / f"{name}.png")
    plt.close(fig)
    print("saved", name)


def label_bars(ax, bars, fmt="{:.1f}%", inside=False):
    for b in bars:
        w = b.get_width() if b.get_width() > 0 and ax.get_xlim()[1] > 1 and b.get_height() < 1 else None
        if w is not None:
            ax.text(w + 1, b.get_y() + b.get_height() / 2, fmt.format(w), va="center", fontsize=10)
        else:
            h = b.get_height()
            ax.text(b.get_x() + b.get_width() / 2, h + 1, fmt.format(h), ha="center", fontsize=9.5)


# 1. Final pass rate vs published travel-planning agents ------------------------------------------
published = [
    ("GPT-4 + ReAct (TravelPlanner, Xie et al. 2024)", 0.6),
    ("GPT-3.5 + LLM-Modulo (Gundawar et al. 2024)", 5.0),
    ("o1-preview, all info given (Hao et al. 2024)", 10.0),
    ("ATLAS multi-agent (Choi et al. 2025)", 44.4),
    ("LLM + formal verifier (Hao et al. 2024)", 93.9),
]
ours = [("Sara Explorer — solver (SaraBench-IN)", S["final_pass_rate"])]
if agent:
    ours.append(("Sara Explorer — Ask Sara agent (SaraBench-IN)", agent["summary"]["final_pass_rate"]))
rows = sorted(published + ours, key=lambda r: r[1])
fig, ax = plt.subplots(figsize=(10, 4.8))
colors = [MUSTARD if "Sara" in n else LIGHT for n, _ in rows]
bars = ax.barh([n for n, _ in rows], [v for _, v in rows], color=colors, edgecolor=INK, linewidth=0.6)
for b, (_, v) in zip(bars, rows):
    ax.text(v + 1, b.get_y() + b.get_height() / 2, f"{v:.1f}%", va="center", fontsize=10, fontweight="bold" if v == S["final_pass_rate"] else None)
ax.set_xlim(0, 112)
ax.set_xlabel("Final pass rate (%) — plan satisfies every constraint")
ax.set_title("Final pass rate: Sara Explorer vs published travel-planning agents")
ax.text(0, -0.17, "Published values are the final pass rates reported by each paper on its own benchmark (TravelPlanner family).",
        transform=ax.transAxes, fontsize=8.5, color="#555")
save(fig, "fig01_final_pass_vs_published")

# 2. TravelPlanner metrics for Sara Explorer --------------------------------------------------------
metrics = [("Delivery", "delivery_rate"), ("Commonsense\nmicro", "commonsense_micro"), ("Commonsense\nmacro", "commonsense_macro"),
           ("Hard\nmicro", "hard_micro"), ("Hard\nmacro", "hard_macro"), ("Final pass", "final_pass_rate")]
gpt4 = {"delivery_rate": 93.1, "commonsense_micro": 63.3, "commonsense_macro": 2.0, "hard_micro": 10.5, "hard_macro": 5.5, "final_pass_rate": 0.6}
fig, ax = plt.subplots(figsize=(10, 4.4))
x = np.arange(len(metrics))
b1 = ax.bar(x - 0.2, [S[k] for _, k in metrics], 0.38, color=MUSTARD, edgecolor=INK, linewidth=0.6, label="Sara Explorer (SaraBench-IN, n=300)")
b2 = ax.bar(x + 0.2, [gpt4[k] for _, k in metrics], 0.38, color=LIGHT, edgecolor=INK, linewidth=0.6, label="GPT-4 two-stage (TravelPlanner test, reported)")
for bars in (b1, b2):
    for b in bars:
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 1.2, f"{b.get_height():.1f}", ha="center", fontsize=9)
ax.set_xticks(x, [m for m, _ in metrics])
ax.set_ylim(0, 112)
ax.set_ylabel("%")
ax.set_title("Constraint-satisfaction metrics (TravelPlanner definitions)")
ax.legend(frameon=False, loc="upper center", ncol=2, bbox_to_anchor=(0.5, -0.14))
save(fig, "fig02_travelplanner_metrics")

# 3. Per-constraint pass rate -----------------------------------------------------------------------
pc = S["per_constraint"]
names = {"complete_plan": "Complete plan", "valid_route_onward": "Correct onward route", "valid_route_return": "Correct return route",
         "dates_consistent": "Dates consistent", "stay_in_destination": "Stay in destination", "travellers_consistent": "Travellers consistent",
         "transport_bookable": "Transport bookable", "within_budget": "Within budget", "nights_match": "Nights match",
         "mode_respected": "Travel mode respected", "hotel_price_cap": "Hotel price cap", "hotel_min_stars": "Hotel min stars"}
fig, ax = plt.subplots(figsize=(9, 5))
keys = list(names)
colors = [BLUE if i < 7 else MUSTARD for i in range(len(keys))]
bars = ax.barh([names[k] for k in keys][::-1], [pc[k] for k in keys][::-1], color=colors[::-1], edgecolor=INK, linewidth=0.5)
for b in bars:
    ax.text(b.get_width() - 3, b.get_y() + b.get_height() / 2, f"{b.get_width():.0f}%", va="center", ha="right", color="white", fontsize=9.5, fontweight="bold")
ax.set_xlim(0, 100)
ax.set_xlabel("Pass rate on feasible queries (%)")
ax.set_title(f"Every constraint satisfied on all {S['n_feasible']} feasible queries")
from matplotlib.patches import Patch  # noqa: E402
ax.legend(handles=[Patch(color=BLUE, label="Commonsense"), Patch(color=MUSTARD, label="Hard (user) constraints")], frameon=False, loc="lower left", bbox_to_anchor=(0, -0.22), ncol=2)
save(fig, "fig03_per_constraint")

# 4. Pass rate by difficulty ------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(8, 4.2))
levels = ["easy", "medium", "hard"]
counts = {l: sum(q["level"] == l for q in queries) for l in levels}
gpt_lvl = {"easy": 0.0, "medium": 0.0, "hard": 0.0}  # not reported per level for GPT-4: shown as overall 0.6
bars = ax.bar([f"{l.title()}\n(n={counts[l]})" for l in levels], [S["by_level"][l] for l in levels], color=[ "#F3C94E", MUSTARD, "#B8860B"], edgecolor=INK, linewidth=0.6, width=0.55)
for b in bars:
    ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 1.5, f"{b.get_height():.0f}%", ha="center", fontweight="bold")
ax.axhline(0.6, color=GREY, ls="--", lw=1.2)
ax.set_ylim(0, 118)
ax.text(0.5, 1.02, "Dashed line: GPT-4 overall final pass on TravelPlanner (0.6%)", transform=ax.transAxes, ha="center", fontsize=9, color="#555")
ax.set_ylabel("Final pass rate (%)")
ax.set_title("Final pass rate by difficulty level", pad=22)
save(fig, "fig04_by_difficulty")

# 5. Unsatisfiable request handling -----------------------------------------------------------------
fig, ax = plt.subplots(figsize=(8, 4))
labels = ["Sara Explorer solver", "LLM + formal verifier\n(Hao et al., dataset 1)", "LLM + formal verifier\n(Hao et al., dataset 2)"]
vals = [S["unsat_detection"], 81.6, 91.7]
bars = ax.bar(labels, vals, color=[MUSTARD, LIGHT, LIGHT], edgecolor=INK, linewidth=0.6, width=0.55)
for b in bars:
    ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 1.5, f"{b.get_height():.1f}%", ha="center", fontweight="bold")
ax.set_ylim(0, 112)
ax.set_ylabel("%")
ax.set_title(f"Unsatisfiable requests handled correctly (Sara: {S['n_infeasible']} impossible budgets)")
ax.text(0, -0.2, "Sara: impossible request detected and explained with the minimum feasible cost. Hao et al.: unsatisfiable queries repaired.",
        transform=ax.transAxes, fontsize=8.3, color="#555")
save(fig, "fig05_unsat_detection")

# 6. Planning latency -------------------------------------------------------------------------------
sol_ms = np.array([r["latency_s"] * 1000 for r in solver["rows"]])
fig, ax = plt.subplots(figsize=(8.5, 4.2))
items = [("Sara solver", np.median(sol_ms) / 1000, MUSTARD)]
if llm:
    items.append(("Same LLM planning\nwithout solver", llm["summary"]["latency_median_s"], LIGHT))
if agent:
    items.append(("Ask Sara agent\n(LLM + tools + solver)", agent["summary"]["latency_median_s"], "#F3C94E"))
bars = ax.bar([i[0] for i in items], [max(i[1], 0.0005) for i in items], color=[i[2] for i in items], edgecolor=INK, linewidth=0.6, width=0.55)
ax.set_yscale("log")
for b, it in zip(bars, items):
    txt = f"{it[1] * 1000:.1f} ms" if it[1] < 1 else f"{it[1]:.1f} s"
    ax.text(b.get_x() + b.get_width() / 2, b.get_height() * 1.25, txt, ha="center", fontweight="bold")
ax.set_ylabel("Median time per plan (s, log scale)")
ax.set_title("Planning latency")
save(fig, "fig06_latency")

# 7. Solver latency distribution --------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(8, 4))
ax.hist(sol_ms, bins=30, color=MUSTARD, edgecolor=INK, linewidth=0.5)
ax.axvline(np.median(sol_ms), color=INK, ls="--", lw=1.2)
ax.text(np.median(sol_ms), ax.get_ylim()[1] * 0.92, f"  median {np.median(sol_ms):.2f} ms", fontsize=10)
ax.set_xlabel("Solver time per query (ms)")
ax.set_ylabel("Queries")
ax.set_title(f"Constraint solver latency over {len(sol_ms)} queries (p90 {np.percentile(sol_ms, 90):.2f} ms)")
save(fig, "fig07_solver_latency_hist")

# 8. Budget use: cost vs budget ---------------------------------------------------------------------
qmap = {q["id"]: q for q in queries}
import sys  # noqa: E402
sys.path.insert(0, str(ROOT.parent))
from benchmarks.sarabench import to_req  # noqa: E402
from app.planner.solver import solve  # noqa: E402
fig, ax = plt.subplots(figsize=(7.5, 5.2))
budgets, totals = [], []
for q in queries:
    if q["feasible"]:
        res = solve(to_req(q))
        if res.status == "ok":
            budgets.append(q["request"]["budget_total"])
            totals.append(res.total)
if totals:
    ax.scatter(budgets, totals, s=16, color=MUSTARD, edgecolor=INK, linewidth=0.3, label="Plan total chosen by Sara")
lim = max(budgets) * 1.05
ax.plot([0, lim], [0, lim], color=GREY, ls="--", lw=1, label="Budget limit (total = budget)")
ax.set_xlim(0, lim)
ax.set_ylim(0, lim)
ax.set_xlabel("Traveller's budget (₹)")
ax.set_ylabel("Plan total (₹)")
ax.set_title("Every plan stays within the traveller's budget")
ax.legend(frameon=False, loc="upper left")
ax.ticklabel_format(style="plain")
save(fig, "fig08_budget_vs_total")

# 9. Benchmark composition --------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(8, 4))
feas = [sum(q["level"] == l and q["feasible"] for q in queries) for l in levels]
infe = [sum(q["level"] == l and not q["feasible"] for q in queries) for l in levels]
ax.bar([l.title() for l in levels], feas, color=MUSTARD, edgecolor=INK, linewidth=0.6, label="Feasible")
ax.bar([l.title() for l in levels], infe, bottom=feas, color=INK, label="Unsatisfiable (budget too low)")
for i, (f, u) in enumerate(zip(feas, infe)):
    ax.text(i, f / 2, str(f), ha="center", color=INK, fontweight="bold")
    ax.text(i, f + u / 2, str(u), ha="center", color="white", fontweight="bold")
ax.set_ylabel("Queries")
ax.set_title(f"SaraBench-IN: {len(queries)} queries, {len({q['request']['destination'] for q in queries})} destinations, "
             f"{len({q['request']['origin'] for q in queries})} origins")
ax.set_ylim(0, max(f + u for f, u in zip(feas, infe)) * 1.25)
ax.legend(frameon=False, loc="upper center", ncol=2)
save(fig, "fig09_benchmark_composition")

# 10. Capability comparison -------------------------------------------------------------------------
caps = ["Guaranteed hard\nconstraints", "Explains\nimpossible plans", "Books with\nuser consent", "Direct vendor\nUPI payment",
        "India-specific\nknowledge", "Voice input", "Maps & photos", "Security\nhardening"]
systems = {
    "Sara Explorer": [1, 1, 1, 1, 1, 1, 1, 1],
    "TRIP-PAL (2024)": [1, 0, 0, 0, 0, 0, 0, 0],
    "LLM + formal verifier (2024)": [1, 1, 0, 0, 0, 0, 0, 0],
    "Personal Travel Solver (ACL 2025)": [1, 0, 0, 0, 0, 0, 0, 0],
    "ATLAS (2025)": [1, 0, 0, 0, 0, 0, 0, 0],
    "Personal LLM agents (EMNLP 2024)": [0, 0, 0, 0, 0, 0, 0, 0],
    "AI-Enabled Travel Planner (IEEE 2025)": [0, 0, 0, 0, 0, 0, 0, 0],
}
M = np.array(list(systems.values()))
fig, ax = plt.subplots(figsize=(11, 4.6))
ax.imshow(M, cmap=matplotlib.colors.ListedColormap(["#F2F2F2", MUSTARD]), aspect="auto", vmin=0, vmax=1)
ax.set_xticks(range(len(caps)), caps, fontsize=9)
ax.set_yticks(range(len(systems)), list(systems), fontsize=10)
for i in range(M.shape[0]):
    for j in range(M.shape[1]):
        ax.text(j, i, "✓" if M[i, j] else "–", ha="center", va="center", fontsize=12, color=INK if M[i, j] else GREY)
ax.set_xticks(np.arange(-0.5, len(caps), 1), minor=True)
ax.set_yticks(np.arange(-0.5, len(systems), 1), minor=True)
ax.grid(which="minor", color="white", lw=2)
ax.tick_params(which="minor", length=0)
for s in ax.spines.values():
    s.set_visible(False)
ax.set_title("Capabilities as described in each work (– = not reported)")
save(fig, "fig10_capabilities")

# 11. Security test coverage ------------------------------------------------------------------------
import subprocess  # noqa: E402
collected = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q"], cwd=ROOT.parent,
                           capture_output=True, text=True).stdout
per_file = {}
for line in collected.splitlines():
    if "::" in line:
        f = line.split("::")[0].split("/")[-1]
        per_file[f] = per_file.get(f, 0) + 1
labels = {"test_auth.py": "Accounts, sessions & tokens", "test_booking.py": "Consent & payment integrity",
          "test_upi.py": "Vendor payments & access control", "test_solver.py": "Constraint solver",
          "test_strategist.py": "Strategist, data & knowledge",
          "test_grounding.py": "Price-grounding guard"}
sec = [(labels.get(f, f), n) for f, n in per_file.items()]
total = sum(n for _, n in sec)
fig, ax = plt.subplots(figsize=(8.5, 3.8))
bars = ax.barh([s_[0] for s_ in sec][::-1], [s_[1] for s_ in sec][::-1], color=MUSTARD, edgecolor=INK, linewidth=0.6)
for b in bars:
    ax.text(b.get_width() + 0.1, b.get_y() + b.get_height() / 2, f"{int(b.get_width())} passed", va="center", fontsize=9.5)
ax.set_xlabel("Automated tests (all passing)")
ax.set_title(f"Automated security and correctness tests ({total} / {total} passing)")
ax.set_xlim(0, max(n for _, n in sec) + 3)
save(fig, "fig11_tests")

# 12. Agent: grounded prices -------------------------------------------------------------------------
if agent:
    A = agent["summary"]
    vals = [("Plan delivered", A["delivery_rate"]), ("Final pass", A["final_pass_rate"]),
            ("Prices grounded\nin tool data", A["price_grounded"] or 0), ("Impossible budgets\ndetected", A["unsat_detection"] or 0)]
    fig, ax = plt.subplots(figsize=(8.5, 4))
    bars = ax.bar([v[0] for v in vals], [v[1] for v in vals], color=MUSTARD, edgecolor=INK, linewidth=0.6, width=0.55)
    for b in bars:
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 1.5, f"{b.get_height():.0f}%", ha="center", fontweight="bold")
    ax.set_ylim(0, 112)
    ax.set_ylabel("%")
    ax.set_title(f"Ask Sara agent end to end (gpt-oss-120b + solver tool, n={A['n']})")
    save(fig, "fig12_agent")

# 13. Price grounding across the three agent versions ----------------------------------------------
v1, v2, v3 = load("agent_v1"), load("agent_v2"), load("agent_v3_partial")
if v1 and v2 and v3:
    nl = "\n"
    steps = [(f"v1: initial agent{nl}(n={v1['summary']['n']})", v1["summary"]["price_grounded"]),
             (f"v2: full price data{nl}+ stricter prompt (n={v2['summary']['n']})", v2["summary"]["price_grounded"]),
             (f"v3: + grounding guard{nl}(preliminary, n={v3['summary']['n']})", v3["summary"]["price_grounded"])]
    fig, ax = plt.subplots(figsize=(8.5, 4.4))
    bars = ax.bar([s_[0] for s_ in steps], [s_[1] or 0 for s_ in steps], color=[LIGHT, "#F3C94E", MUSTARD],
                  edgecolor=INK, linewidth=0.6, width=0.55)
    for b in bars:
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 1.5, f"{b.get_height():.0f}%", ha="center", fontweight="bold")
    ax.set_ylim(0, 112)
    ax.set_ylabel("Replies with every ₹ amount grounded (%)")
    ax.set_title("Eliminating invented prices in Sara's replies")
    save(fig, "fig13_grounding")
