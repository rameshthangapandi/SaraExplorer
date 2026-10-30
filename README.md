# Sara Explorer

**An Indian trip planner agentic AI.** Chat with Sara to plan trips across India, get Strategist advice on when to book and when to travel, and book flights, trains and stays — only after you approve.

> Demo build: flights, trains and hotels come from a built-in sandbox and payments use a built-in test gateway. No real money is charged and no real tickets are issued. Everything runs at **₹0 cost**.

## Features

| Area | What's included |
|---|---|
| **Ask Sara** | Streaming chat agent (LangGraph + Groq `openai/gpt-oss-120b`) with 10 tools, rich cards, chat history, voice input (Groq `whisper-large-v3`) |
| **Strategist** | Plug-in strategies: booking timing, departure time, nearby airport, closed days, weather, shoulder season, festivals, fog/monsoon buffers, permits. Best-time calendar and "where to go in month X" for 26 destinations |
| **Consent-first booking** | Sara can only *propose*. A consent card shows items, terms, total and a 15-minute price hold. Nothing is booked until **Approve & Pay** and a verified payment |
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
- The LLM can never set prices: bookable options are stored server-side and referenced by ID; totals are computed on the server
- Amount locked at approval; spending cap enforced; ownership checked on every consent/order
- Payment accepted only with a valid **HMAC-SHA256 signature** (constant-time comparison); webhooks verified the same way
- **Idempotent settlement**: an atomic `created → paid` transition guarantees bookings are created exactly once, even on replay
- Card / UPI details never touch the server (Razorpay Checkout when enabled; built-in test gateway otherwise)
- Every approval, payment, booking and security event is written to an **audit log**

**Platform**
- Strict security headers (CSP, X-Frame-Options, nosniff, Referrer-Policy, Permissions-Policy, HSTS when on HTTPS)
- Validation errors never echo submitted values; internal errors are never exposed
- API docs disabled in production; containers run as non-root; Postgres and Redis are not exposed outside Docker
- Prompt-injection guard: tool results are treated as data; Sara never asks for passwords, OTPs or PINs
- Secrets only in `.env` (git-ignored)

## Tech stack

React 19 + Vite + TypeScript + Tailwind CSS 4 · FastAPI · LangGraph · Groq · PostgreSQL (pgvector image) · Redis · Docker Compose · Open-Meteo (live weather, free)

## Quick start (Docker)

```bash
cp .env.example .env        # then fill in GROQ_API_KEY and generate the secrets
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
  providers/     sandbox inventory, Open-Meteo weather
  knowledge/     travel knowledge base + search
  payments/      gateway (test gateway + Razorpay) with signature verification
  security/      passwords, tokens, rate limiting, headers, auth dependencies
  data/          destinations, airports, stations, aliases
frontend/src/
  pages/         Landing, Auth, AskSara, Strategist, Trips, Account
  components/    SaraAvatar, PaymentModal, cards/ (flights, trains, hotels, consent, ...)
  lib/           API client (in-memory token, refresh, SSE), auth context
docs/            Project plan
```

## Switching to real services later

| Today (free) | Later |
|---|---|
| Sandbox flights / hotels | Duffel / LiteAPI (same tool interface) |
| Mock railway | Authorised IRCTC partner API |
| Built-in test gateway | `PAYMENT_PROVIDER=razorpay` with Razorpay keys |
| Keyword knowledge search | Hybrid search (Postgres FTS + pgvector BGE-M3) + re-ranking |

See [docs/Sara_Explorer_Project_Plan.docx](docs/Sara_Explorer_Project_Plan.docx) for the full roadmap.
