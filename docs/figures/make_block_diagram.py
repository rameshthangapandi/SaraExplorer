"""Generate the Sara Explorer swimlane block diagram (block_diagram.html -> rendered to block_diagram.png)."""
from pathlib import Path

W, H = 1920, 1080
LANE_X, LANE_W = 24, 1872
LABEL_W = 190
COLS = [380, 722, 1064, 1406, 1748]           # column centres
BW, BH = 262, 92                               # box size
LANES = [  # (key, label, colour, top)
    ("trav", "TRAVELLER", "#B7860B", 118),
    ("web", "WEB &amp; SECURITY", "#1F5F5B", 300),
    ("ai", "AI CORE", "#1D4ED8", 482),
    ("adv", "ADVICE &amp; DISCOVERY", "#7C3AED", 664),
    ("data", "DATA &amp; SERVICES", "#15803D", 846),
]
LANE_H = 168
lane = {k: (lbl, col, top) for k, lbl, col, top in LANES}


def cy(key):
    return lane[key][2] + LANE_H / 2


def esc(t):
    return t.replace("&", "&amp;") if "&amp;" not in t else t


out = []
add = out.append


def box(key, c, title, sub, shape="rect"):
    colour = lane[key][1]
    x, y = COLS[c] - BW / 2, cy(key) - BH / 2
    if shape == "pill":
        add(f'<rect x="{x}" y="{y}" width="{BW}" height="{BH}" rx="46" fill="#fff" stroke="{colour}" stroke-width="3"/>')
    elif shape == "diamond":
        cx_, cyy = COLS[c], cy(key)
        add(f'<polygon points="{cx_},{cyy - 62} {cx_ + 136},{cyy} {cx_},{cyy + 62} {cx_ - 136},{cyy}" fill="#fff" stroke="{colour}" stroke-width="3"/>')
    elif shape == "cyl":
        rx, ry = BW / 2, 14
        add(f'<path d="M{x},{y + ry} A{rx},{ry} 0 0 1 {x + BW},{y + ry} V{y + BH - ry} A{rx},{ry} 0 0 1 {x},{y + BH - ry} Z" fill="#fff" stroke="{colour}" stroke-width="3"/>')
        add(f'<path d="M{x},{y + ry} A{rx},{ry} 0 0 0 {x + BW},{y + ry}" fill="none" stroke="{colour}" stroke-width="3"/>')
    else:
        add(f'<rect x="{x}" y="{y}" width="{BW}" height="{BH}" rx="12" fill="#fff" stroke="{colour}" stroke-width="3"/>')
    ty = cy(key) - (6 if sub else -8) + (6 if shape == "cyl" else 0)
    add(f'<text x="{COLS[c]}" y="{ty}" class="t">{esc(title)}</text>')
    if sub:
        add(f'<text x="{COLS[c]}" y="{ty + 27}" class="s">{esc(sub)}</text>')


def arrow(points, dashed=False, colour="#1f1f1f"):
    d = "M" + " L".join(f"{x},{y}" for x, y in points)
    dash = 'stroke-dasharray="8 7"' if dashed else ""
    marker = "ahg" if dashed else ("ahb" if colour == "#1D4ED8" else "ah")
    add(f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="2.6" {dash} marker-end="url(#{marker})"/>')


def label(x, y, text, colour):
    w = len(text) * 9.2 + 26
    add(f'<rect x="{x - w / 2}" y="{y - 15}" width="{w}" height="30" rx="15" fill="#fff" stroke="{colour}" stroke-width="2"/>')
    add(f'<text x="{x}" y="{y + 6}" class="lab" fill="{colour}">{text}</text>')


right = lambda c: COLS[c] + BW / 2  # noqa: E731
left = lambda c: COLS[c] - BW / 2   # noqa: E731
top = lambda k: cy(k) - BH / 2      # noqa: E731
bot = lambda k: cy(k) + BH / 2      # noqa: E731

# lanes
for k, lbl, col, t in LANES:
    add(f'<line x1="{LANE_X}" y1="{t + LANE_H + 7}" x2="{LANE_X + LANE_W}" y2="{t + LANE_H + 7}" stroke="#e6e6e6" stroke-width="1.5"/>')
    add(f'<rect x="{LANE_X}" y="{t + 10}" width="6" height="{LANE_H - 20}" rx="3" fill="{col}"/>')
    parts = lbl.split(" &amp; ")
    if len(parts) == 2:
        add(f'<text x="{LANE_X + 22}" y="{t + LANE_H / 2 - 5}" class="lane" fill="{col}">{parts[0]} &amp;</text>')
        add(f'<text x="{LANE_X + 22}" y="{t + LANE_H / 2 + 20}" class="lane" fill="{col}">{parts[1]}</text>')
    else:
        add(f'<text x="{LANE_X + 22}" y="{t + LANE_H / 2 + 7}" class="lane" fill="{col}">{lbl}</text>')

# lane 1: traveller
box("trav", 0, "Choose or ask", "dropdowns · chat · voice", "pill")
box("trav", 1, "Who's travelling", "couple · family · friends", "pill")
box("trav", 2, "Review the plan", "solver pick · strategy · rides", "pill")
box("trav", 3, "Approve &amp; pay", "exact total · UPI per vendor", "pill")
box("trav", 4, "Booked", "references in My Trips", "pill")
for c in range(4):
    arrow([(right(c), cy("trav")), (left(c + 1) - 4, cy("trav"))])

# lane 2: web & security
box("web", 0, "Web app", "Plan · Explore · Rides · Chat")
box("web", 1, "Security gate", "Argon2id · sessions · limits")
box("web", 2, "Live results", "cards streamed to the screen")
box("web", 3, "Consent gate", "server prices · 15-min hold")
box("web", 4, "Vendor portal", "confirms money received")
arrow([(right(0), cy("web")), (left(1) - 4, cy("web"))])
arrow([(right(3), cy("web")), (left(4) - 4, cy("web"))])
arrow([(COLS[0], bot("trav")), (COLS[0], top("web") - 4)])
arrow([(COLS[2], top("web")), (COLS[2], bot("trav") + 4)])
arrow([(COLS[3], bot("trav")), (COLS[3], top("web") - 4)])
arrow([(COLS[4], top("web")), (COLS[4], bot("trav") + 4)])

# lane 3: AI core
box("ai", 0, "Router", "screens or Ask Sara", "diamond")
box("ai", 1, "Ask Sara agent", "gpt-oss-120b · LangGraph")
box("ai", 2, "Constraint solver", "checks every combination")
box("ai", 3, "Group personaliser", "hotels · transport · places")
box("ai", 4, "Grounding guard", "no invented prices")
g = (top("ai") + bot("web")) / 2
arrow([(COLS[1], bot("web")), (COLS[1], g), (COLS[0], g), (COLS[0], cy("ai") - 66)])
arrow([(COLS[0] + 136, cy("ai")), (left(1) - 4, cy("ai"))])
arrow([(right(1), cy("ai")), (left(2) - 4, cy("ai"))])
arrow([(right(2), cy("ai")), (left(3) - 4, cy("ai"))])
arrow([(right(3), cy("ai")), (left(4) - 4, cy("ai"))])
arrow([(COLS[4], top("ai")), (COLS[4], g + 10), (COLS[2] + 40, g + 10), (COLS[2] + 40, bot("web") + 4)], colour="#1D4ED8")
label((COLS[3] + COLS[4]) / 2 + 40, g + 10, "checked reply", "#1D4ED8")

# lane 4: advice & discovery
box("adv", 0, "Strategist", "timing · seasons · risks")
box("adv", 1, "Local rides", "bus · metro · Rapido · Ola · Uber")
box("adv", 2, "Plan verifier", "12 constraint checks")
box("adv", 3, "Explore &amp; maps", "photos · sights · restaurants")
box("adv", 4, "Travel guide", "permits · rules · sources")
bus4 = (top("adv") + bot("ai")) / 2
add(f'<path d="M{COLS[0]},{top("adv")} V{bus4} H{COLS[4]} V{top("adv")}" fill="none" stroke="#7C3AED" stroke-width="2.4" stroke-dasharray="8 7"/>')
for c in (1, 2, 3):
    add(f'<line x1="{COLS[c]}" y1="{bus4}" x2="{COLS[c]}" y2="{top("adv")}" stroke="#7C3AED" stroke-width="2.4" stroke-dasharray="8 7"/>')
arrow([(COLS[1] + 60, bus4), (COLS[1] + 60, bot("ai") + 4)], dashed=True)
label(COLS[1] + 60, bus4, "12 tools", "#7C3AED")

# lane 5: data & services
box("data", 0, "PostgreSQL", "users · trips · payments", "cyl")
box("data", 1, "Redis", "rate-limit counters", "cyl")
box("data", 2, "Travel inventory", "flights · trains · hotels", "cyl")
box("data", 3, "Knowledge base", "26 destinations · travel rules", "cyl")
box("data", 4, "Free web services", "Open-Meteo · Wikipedia · OSM", "cyl")
bus5 = (top("data") + bot("adv")) / 2
add(f'<path d="M{COLS[0]},{top("data")} V{bus5} H{COLS[4]} V{top("data")}" fill="none" stroke="#15803D" stroke-width="2.4" stroke-dasharray="8 7"/>')
for c in (1, 2, 3):
    add(f'<line x1="{COLS[c]}" y1="{bus5}" x2="{COLS[c]}" y2="{top("data")}" stroke="#15803D" stroke-width="2.4" stroke-dasharray="8 7"/>')
label((COLS[2] + COLS[3]) / 2, bus5, "read · write", "#15803D")

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs>
<marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#1f1f1f"/></marker>
<marker id="ahb" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#1D4ED8"/></marker>
<marker id="ahg" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#7C3AED"/></marker>
<style>
.t{{font:700 23px "Segoe UI",Inter,Arial,sans-serif;fill:#111;text-anchor:middle}}
.s{{font:400 17px "Segoe UI",Inter,Arial,sans-serif;fill:#4a4a4a;text-anchor:middle}}
.lane{{font:800 19px "Segoe UI",Inter,Arial,sans-serif;letter-spacing:1.5px}}
.lab{{font:700 15px "Segoe UI",Inter,Arial,sans-serif;text-anchor:middle}}
.h1{{font:800 40px "Segoe UI",Inter,Arial,sans-serif;fill:#111}}
.h2{{font:400 19px "Segoe UI",Inter,Arial,sans-serif;fill:#555;text-anchor:end}}
</style></defs>
<rect width="{W}" height="{H}" fill="#fff"/>
<text x="{LANE_X}" y="66" class="h1">Sara <tspan fill="#B7860B">Explorer</tspan> — how it works</text>
<text x="{LANE_X + LANE_W}" y="64" class="h2">plans are solved, checked and approved before any money moves</text>
<line x1="{LANE_X}" y1="92" x2="{LANE_X + LANE_W}" y2="92" stroke="#111" stroke-width="2"/>
{"".join(out)}
</svg>'''
here = Path(__file__).parent
(here / "block_diagram.html").write_text(
    f'<!doctype html><html><head><meta charset="utf-8"><title>Sara Explorer block diagram</title>'
    f'<style>html,body{{margin:0;background:#fff}}</style></head><body>{svg}</body></html>', encoding="utf-8")
(here / "block_diagram.svg").write_text(svg, encoding="utf-8")
print("written")
