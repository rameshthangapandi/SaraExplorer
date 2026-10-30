# Sara Explorer

**An Indian trip planner agentic AI.** Plan trips across India with simple dropdowns or by chatting with Sara, explore destinations with photos and maps, get Strategist advice on when to book and travel, and book flights, trains and stays — only after you approve and your payment is confirmed.

> Demo build: flights, trains and hotels come from a built-in sandbox, so **no real tickets are issued**. Payments are real UPI payments to the operator's UPI ID. Everything runs at **₹0 cost**.

## Features

| Area | What's included |
|---|---|
| **Plan & Book** (home) | Dropdown-based planner: from, to, dates, nights, travellers, travel mode, hotel budget. Compare onward/return flights and trains (filter + sort) and stays, pick options, see Sara's strategy, then approve |
| **Explore** | Destinations ranked for your travel month and interest, with photos; destination pages with summary, best-time calendar, live 7-day forecast, festivals, tips, and an interactive map of nearby sights (with photos), restaurants, cafes and stays — around the destination or **near me** |
| **Travel Guide** | Searchable permits, train rules, pilgrimage, safety and app help, with sources |
| **Ask Sara** | Streaming chat agent (LangGraph + Groq `openai/gpt-oss-120b`) with 10 tools, rich cards, chat history, voice input (Groq `whisper-large-v3`) |
| **Strategist** | Plug-in strategies: booking timing, departure time, nearby airport, closed days, weather, shoulder season, festivals, fog/monsoon buffers, permits. Best-time calendar and "where to go in month X" for 26 destinations |
| **Consent-first booking** | Sara or the planner only *propose*. An approval card shows items, terms, total and a 15-minute price hold. **Approve & Pay** shows a UPI QR / "Open UPI app" for the exact amount; the traveller submits the 12-digit UTR; the trip is **booked only after an admin confirms the money was received** |
| **Admin: Verify payments** | Admins (ADMIN_EMAILS) match the UTR and amount in their UPI/bank app, then confirm (books the trip) or reject (nothing is booked) |
| **Travel knowledge** | Permits (ILP/PAP), IRCTC Tatkal & waitlist rules, Char Dham, Taj closed days, scams, app help — each with source and verified date |
| **Sandbox inventory** | Deterministic flights / trains / hotels with realistic pricing (lead time, weekday, departure hour, festival peaks) and waitlist confirmation chances |
| **Accounts** | Register, login, stay signed in until the session ends, device list, sign out one or all devices, spending limit |

## Security

**Authentication & sessions**
- Argon2id password hashing, password strength rules, timing-safe login (no user enumeration by timing)
- Account lockout after 5 failed attempts; rate limits on login, register, chat, voice and payments (Redis-backed)
- 15-minute JWT access tokens kept **in memory only** (never localStorage)
- Refresh token in an `httpOnly`, `SameSite=Strict`, path-scoped cookie with **rotation** and **reuse detection** (a replayed token revokes the whole session family)
- "Keep me signed in" = 7 days; otherwise the session ends when the browser closes. Logout and "sign out everywhere" take effect immediately (every request checks the session is live)
- CSRF protection on cookie endpoints (custom header + Origin check)

**Payments**
- Booked only after money is confirmed: UPI payments wait for admin verification; Razorpay (optional) is confirmed by signed callbacks
- UTR format checked and each UTR usable only once; a request can't be cancelled while its payment is being verified
- The LLM can never set prices: bookable options are stored server-side and referenced by ID; totals are computed on the server
- Amount locked at approval; spending cap enforced; ownership checked on every consent/order
- Payment accepted only with a valid **HMAC-SHA256 signature** (constant-time comparison); webhooks verified the same way
- **Idempotent settlement**: an atomic `created → paid` transition guarantees bookings are created exactly once, even on replay
- Card / UPI details never touch the server; the app never asks for a UPI PIN
- The instant "mock" gateway exists only for automated tests and is disabled otherwise
- Every approval, payment, booking and security event is written to an **audit log**

**Platform**
- Strict security headers (CSP, X-Frame-Options, nosniff, Referrer-Policy, Permissions-Policy, HSTS when on HTTPS)
- Validation errors never echo submitted values; internal errors are never exposed
- API docs disabled in production; containers run as non-root; Postgres and Redis are not exposed outside Docker
- Prompt-injection guard: tool results are treated as data; Sara never asks for passwords, OTPs or PINs
- Secrets only in `.env` (git-ignored)

## Tech stack

React 19 + Vite + TypeScript + Tailwind CSS 4 · Leaflet + OpenStreetMap · FastAPI · LangGraph · Groq · PostgreSQL (pgvector image) · Redis · Docker Compose

Free data sources: Open-Meteo (weather), Wikipedia / Wikimedia (photos, sights), OpenStreetMap Nominatim (restaurants, cafes, stays). Restaurant photos and star ratings are not available from free sources, so restaurants link to Google Maps for photos and reviews.

## Quick start (Docker)

```bash
cp .env.example .env        # fill in GROQ_API_KEY, MERCHANT_UPI_ID, ADMIN_EMAILS and generate the secrets
docker compose up -d --build
```

Open **http://localhost:8080**, create an account and ask Sara something.

## Local development

```bash
# Backend (uses SQLite by default)
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt     # Windows (use .venv/bin on macOS/Linux)
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000

# Frontend (proxies /api to :8000)
cd frontend
npm install
npm run dev                  # http://localhost:5173
```

Run backend tests: `cd backend && .venv/Scripts/python -m pytest`

## Project structure

```
backend/app/
  agents/        Ask Sara: LangGraph graph (sara.py) and tools (tools.py)
  api/           auth, chat (SSE), trips (consent/payments/bookings), misc (voice, strategist, account)
  strategist/    plug-in framework + strategies/ (money, timing, experience, risk)
  providers/     sandbox inventory, Open-Meteo weather, places (Wikipedia + OpenStreetMap)
  knowledge/     travel knowledge base + search
  payments/      gateway (test gateway + Razorpay) with signature verification
  security/      passwords, tokens, rate limiting, headers, auth dependencies
  data/          destinations, airports, stations, aliases
frontend/src/
  pages/         Landing, Auth, Plan, Explore, Strategist, Guide, AskSara, Trips, Account, Admin
  components/    SaraAvatar, PaymentModal, cards/ (flights, trains, hotels, consent, ...)
  lib/           API client (in-memory token, refresh, SSE), auth context
docs/            Project plan
```

## Switching to real services later

| Today (free) | Later |
|---|---|
| Sandbox flights / hotels | Duffel / LiteAPI (same tool interface) |
| Mock railway | Authorised IRCTC partner API |
| UPI QR + manual verification | `PAYMENT_PROVIDER=razorpay` for automatic confirmation (Razorpay charges a fee per transaction) |
| Restaurant links to Google Maps | Google Places / Foursquare for photos and ratings (paid) |
| Keyword knowledge search | Hybrid search (Postgres FTS + pgvector BGE-M3) + re-ranking |

See [docs/Sara_Explorer_Project_Plan.docx](docs/Sara_Explorer_Project_Plan.docx) for the full roadmap.
