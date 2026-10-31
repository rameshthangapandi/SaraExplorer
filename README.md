# Sara Explorer

**An Indian trip planner agentic AI.** Plan trips across India with simple dropdowns or by chatting with Sara, let a constraint solver build the best trip within your budget, explore destinations with photos and maps, and book only after you approve and each vendor confirms your UPI payment.

![Sara Explorer system workflow](docs/figures/block_diagram.png)

## Highlights

- **Two ways to plan** – dropdown-based *Plan & Book* screens, or *Ask Sara*, a streaming chat agent (LangGraph + Groq `openai/gpt-oss-120b`) with 12 tools and voice input (`whisper-large-v3`).
- **Guaranteed plans** – a constraint solver checks every combination of onward travel, stay and return travel and returns only plans that meet the budget, nights, travel mode and hotel rules, or explains exactly why none exists and what each change would cost.
- **No invented prices** – a price-grounding guard checks every ₹ amount in Sara's reply against tool results and rewrites anything it cannot verify.
- **Plans for who is travelling** – honeymoon couples, families with children, friends, senior citizens, solo and business travellers get different destinations, stays, journey times and advice, without ever breaking the budget or other rules.
- **Local rides compared** – city bus, metro, Rapido, Ola and Uber (bike, auto, cab, sedan, SUV): estimated fare, fare per person, time and vehicles needed, with the cheapest, fastest and recommended option and a link to book in the operator's app.
- **Strategist** – ten strategies, including traveller-group advice: booking time, cheapest departure hour, nearby airports, monument closing days, seasons, shoulder months, festivals, fog / monsoon buffers and permits.
- **Consent-gated booking** – approve an exact total with a 15-minute price hold, pay **each vendor directly** with a UPI QR code, and each part is booked only after that vendor confirms the money arrived. The platform never holds customer funds.
- **Explore India** – 26 destinations ranked by month, Wikipedia photos, live Open-Meteo forecasts and an OpenStreetMap map of nearby sights, restaurants, cafes and stays (around the destination or *near me*).
- **Security first** – Argon2id, rotating refresh tokens with reuse detection, lockout, rate limits, CSRF guard, strict CSP and an audit log.

## Screens

| | |
|---|---|
| ![Landing](docs/screenshots/01_landing.png) **1. Landing page** – what Sara does and how booking stays under your control. | ![Sign in](docs/screenshots/02_login.png) **2. Sign in** – "keep me signed in" for 7 days, otherwise the session ends when the browser closes. |
| ![Plan & Book](docs/screenshots/03_plan_home.png) **3. Plan & Book** – origin, destination, dates, nights, travellers, travel mode, hotel budget, total budget and priority, all from dropdowns. | ![Auto-plan](docs/screenshots/04_autoplan.png) **4. Auto-plan** – the solver checked 594 combinations and picked the best trip within ₹40,000; flights and trains can be filtered and sorted. |
| ![Approval](docs/screenshots/05_approval.png) **5. Approval card** – each item, its cancellation rule, who will be paid, the exact total and a price-hold timer. | ![Vendor QR](docs/screenshots/06_vendor_qr.png) **6. Pay each vendor** – one UPI QR per vendor with the exact amount; works with any UPI app. |
| ![UTR](docs/screenshots/07_enter_utr.png) **7. Submit the UTR** – the 12-digit UPI reference; each UTR can be used only once. | ![Waiting](docs/screenshots/08_waiting_vendor.png) **8. Waiting for vendors** – each part is booked only after its vendor confirms the payment. |
| ![Vendor portal](docs/screenshots/09_vendor_portal.png) **9. Vendor portal** – vendors match the UTR and amount with their bank app and press *Money received*. | ![Vendors](docs/screenshots/10_vendors_admin.png) **10. Vendor onboarding** – admins add a vendor's verified UPI ID and login email and switch it live. |
| ![My Trips](docs/screenshots/11_my_trips.png) **11. My Trips** – confirmed bookings with references and cancellation. | ![Explore](docs/screenshots/12_explore.png) **12. Explore** – destinations ranked for your travel month with photos. |
| ![Destination](docs/screenshots/13_destination.png) **13. Destination page** – summary, best-time chart, how to get there and a live forecast. | ![Sights](docs/screenshots/14_nearby_sights.png) **14. Nearby sights** – sights with photos on an interactive map. |
| ![Restaurants](docs/screenshots/15_nearby_restaurants.png) **15. Nearby restaurants** – cuisine, veg tag, hours and distance, with a link to Google Maps for photos and reviews. | ![Strategist](docs/screenshots/16_strategist.png) **16. Strategist** – ranked advice for a trip and month-by-month ratings. |
| ![Guide](docs/screenshots/17_travel_guide.png) **17. Travel Guide** – permits, train rules, pilgrimages and safety with sources. | ![Account](docs/screenshots/18_account_security.png) **18. Account & Security** – spending limit and every signed-in device, with *sign out everywhere*. |
| ![Mobile plan](docs/screenshots/19_mobile_plan.png) **19. Phone layout** – the full planner on a phone. | ![Mobile destination](docs/screenshots/20_mobile_destination.png) **20. Phone destination page** – photos and details on a small screen. |
| ![Local rides](docs/screenshots/21_local_rides.png) **21. Local Rides** – bus, metro, Rapido, Ola and Uber compared by fare per person and time for a family of four. | ![Family plan](docs/screenshots/22_plan_family.png) **22. Plan for a family** – the auto-plan explains why the trip suits a family with children. |
| ![Couples](docs/screenshots/23_explore_couples.png) **23. Explore for couples** – honeymoon-friendly destinations ranked first. | ![Strategist family](docs/screenshots/24_strategist_family.png) **24. Group advice** – the strategist warns a family that Leh is high altitude. |

## Benchmark: SaraBench-IN

300 trip requests (12 origins, 26 destinations, easy / medium / hard, 39 with impossible budgets) scored with the **TravelPlanner** metrics (Xie et al., ICML 2024).

| Metric | Sara Explorer solver | GPT-4 two-stage on TravelPlanner (reported) |
|---|---|---|
| Delivery rate | **100%** | 93.1% |
| Commonsense pass (micro / macro) | **100% / 100%** | 63.3% / 2.0% |
| Hard-constraint pass (micro / macro) | **100% / 100%** | 10.5% / 5.5% |
| Final pass rate | **100%** | 0.6% |
| Impossible requests detected | **100% (39/39)** | – |
| Median planning time | **0.38 ms** | – |

The end-to-end Ask Sara agent reached a 100% final pass rate on its 14-request sample.

| | |
|---|---|
| ![Final pass](docs/figures/benchmarks/fig01_final_pass_vs_published.png) | ![Metrics](docs/figures/benchmarks/fig02_travelplanner_metrics.png) |
| ![Latency](docs/figures/benchmarks/fig06_latency.png) | ![Grounding](docs/figures/benchmarks/fig13_grounding.png) |
| ![Groups](docs/figures/benchmarks/fig14_group_personalisation.png) | ![Local rides](docs/figures/benchmarks/fig15_local_rides.png) |

Published values come from each paper's own TravelPlanner evaluation; SaraBench-IN uses the same constraint definitions on Indian routes. Reproduce with:

```bash
cd backend
.venv/Scripts/python -m benchmarks.sarabench --systems solver,llm_only,agent
.venv/Scripts/python benchmarks/charts.py
```

## Tech stack

React 19 · TypeScript · Vite · Tailwind CSS 4 · Leaflet + OpenStreetMap · FastAPI · LangGraph · Groq (gpt-oss-120b, Whisper) · PostgreSQL 16 · Redis 7 · Docker Compose · nginx

Free data services: Open-Meteo (weather), Wikipedia / Wikimedia (photos, sights), OpenStreetMap Nominatim (restaurants, cafes, stays).

## Quick start (Docker)

```bash
cp .env.example .env        # fill in GROQ_API_KEY and ADMIN_EMAILS, generate the secrets
docker compose up -d --build
```

Open **http://localhost:8080**, create an account and plan a trip.

## Local development

```bash
# Backend (SQLite by default)
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt     # use .venv/bin on macOS/Linux
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000

# Frontend (proxies /api to :8000)
cd frontend
npm install
npm run dev                  # http://localhost:5173
```

Tests: `cd backend && .venv/Scripts/python -m pytest` (49 tests).

## Security

- **Accounts:** Argon2id hashing, password rules, timing-safe login, lockout after 5 failures, Redis rate limits.
- **Sessions:** 15-minute access tokens kept only in memory; httpOnly `SameSite=Strict` refresh cookie with rotation and reuse detection; logout takes effect immediately.
- **Payments:** prices come only from server-side options (the model passes IDs, never amounts); one payment per vendor; single-use UTRs; atomic settlement so bookings are created exactly once; only a live vendor can confirm its own payments.
- **Platform:** CSRF guard, strict Content Security Policy and security headers, ownership checks on every object, containers run as non-root, database and Redis not exposed outside Docker, audit log of approvals, payments and vendor changes.

## Project structure

```
backend/app/
  agents/        Ask Sara graph (sara.py), tools (tools.py), price-grounding guard (grounding.py)
  planner/       constraint solver (solver.py), plan verifier (verify.py) and traveller groups (groups.py)
  strategist/    plug-in framework and strategies (money, timing, experience, risk, group)
  api/           auth, chat (SSE), trips (approvals, payments, vendor portal), explore, misc
  providers/     inventory adapters, Open-Meteo weather, places (Wikipedia + OpenStreetMap), local rides (local_transport.py)
  knowledge/     travel knowledge base and search
  payments/      UPI links, optional Razorpay, signature checks
  security/      passwords, tokens, rate limits, headers, access checks
  data/          destinations, airports, stations, aliases
backend/benchmarks/  SaraBench-IN harness, results and charts
frontend/src/        pages, components (Sara mascot, map, payment, cards), API client
docs/                screenshots, block diagram, benchmark figures, project plan
```

## Extending

| Component | How to extend |
|---|---|
| Flight / hotel inventory | Add an adapter (e.g. Duffel, LiteAPI) behind the same provider functions |
| Train inventory | Connect an authorised IRCTC partner API |
| Vendors | Add each vendor's verified UPI ID in *Vendor portal → Vendors* |
| Automatic payment confirmation | `PAYMENT_PROVIDER=razorpay` with Razorpay keys |
| Knowledge search | Hybrid search (Postgres full-text + pgvector) with re-ranking |
