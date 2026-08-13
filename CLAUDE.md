# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Backend setup & run
cd backend && uv sync
cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

# Frontend dev (Vite proxies /api to backend on port 8000)
cd frontend && npm run dev

# Build frontend into backend static dir for single-port serving
bash scripts/build_frontend.sh

# Seed mock data
cd backend && uv run python scripts/seed_mock.py [--days 90]

# Tests (backend only)
cd backend && uv run pytest
cd backend && uv run pytest tests/test_analytics.py        # single file
cd backend && uv run pytest tests/test_analytics.py -k test_name  # single test

# Lint (frontend only)
cd frontend && npm run lint   # oxlint
```

## Architecture

**Monorepo**: FastAPI backend + React/TypeScript frontend. In production, backend serves both the API and the built SPA from `backend/app/static/`.

### Backend (`backend/`)
- **FastAPI** with SQLAlchemy ORM over SQLite (WAL mode, foreign keys enabled)
- **Routers** (`app/routers/`): sync, metrics, weight, food, context, analytics — each domain gets its own router
- **DataSource abstraction** (`app/datasources/`): ABC interface with MockSource and GarminSource implementations, selected by `DATA_SOURCE` env var
- **Scheduler** (`app/scheduler.py`): APScheduler cron jobs at 07:30 & 21:30 plus catch-up sync on startup
- **Analytics** (`app/services/`): Stateless on-demand calculations — EWMA weight trend (α=0.1), OLS slope, TDEE back-estimation, energy balance
- **Config** (`app/config.py`): Pydantic Settings loaded from `.env` (see `.env.example`)

### Frontend (`frontend/`)
- **React 19 + TypeScript + Vite**, React Router for SPA navigation
- **React Query** (TanStack) for server state — queryKey patterns like `['dashboard', days]`, `['weight']`
- **Recharts** for charts, **date-fns** for dates
- **API client** (`src/api/client.ts`): apiGet/apiPost/apiPut/apiDelete helpers hitting `/api/*`
- **Dark theme** with slate color palette

### API Contract
All endpoints under `/api/*`. In dev, Vite proxies to `http://127.0.0.1:8000`. Key routes: `/api/analytics/dashboard`, `/api/sync`, `/api/weight`, `/api/food/*`, `/api/context/*`, `/api/health`.

## Key Patterns

- **Upsert ingestion**: `insert().on_conflict_do_update()` for idempotent data syncing
- **Pydantic schemas** (`app/schemas.py`): Input schemas inherit BaseModel; output schemas use `from_attributes=True` for ORM mapping
- **Dependency injection**: `Depends(get_db)` injects SQLAlchemy sessions into routes
- **Weight priority**: manual > garmin > mock (SOURCE_PRIORITY dict in analytics)
- **Date storage**: TEXT columns in YYYY-MM-DD format; timestamps as ISO 8601
- **Source tracking**: most tables have a `source` field (manual | garmin | mock)
- **Python 3.13+** managed via uv; TypeScript strict mode with noUnusedLocals/Parameters

## Constraints

These hold regardless of the task. They are recorded here rather than in any
one machine's memory because work happens both on the laptop and, via the
GitHub issue poller, on the Dell.

### Privacy — the user's health data must not be harvested

- This is real medical and body data about one identifiable person. It is never
  training material for anyone.
- **Open weights do not mean private.** Whoever hosts the model still sees every
  prompt. Choosing an open-weight model satisfies nothing on its own.
- What actually prevents harvesting: OpenRouter's ZDR enforcement plus
  `provider: {data_collection: "deny", require_parameters: true}` in the request
  body, or self-hosting. `AI_REQUIRE_ZDR` controls this; leave it on. The
  provider block is OpenRouter-specific — gate it on the resolved host, since
  other OpenAI-compatible servers reject unknown top-level fields.
- Do not send real health data to a provider the user has not chosen. That
  includes exploratory scripts and evals: `scripts/eval_agent.py` costs money
  and ships live data to whichever endpoint is configured, which is why it is
  not a pytest file and is never run unattended.
- Never hardcode a PrivateMind model id — its catalogue is dynamic. Resolve
  through `GET /v1/models`.

### The only client is an iPhone 14 PWA

Installed to the Home Screen, iOS Safari, 390x844. Desktop rendering is a
development convenience, not a target. **Invoke the `iphone-pwa` skill for any
frontend change**, including ones that look purely cosmetic — the rules there
are correctness constraints, and the failures they prevent are invisible on a
desktop browser. Verify with Playwright at the iPhone 14 viewport; the phone is
the acceptance test.

### The AI agent never writes to health tables

`propose_log_weight` / `_food` / `_context` stage a row in `ai_pending_action`
for the user to confirm. The agent must say a value is *drafted*, never that it
has been logged. Confirmation claims the row with a conditional UPDATE so a
double tap cannot write twice.

### Never invent a number, a date, or a citation

Quote what the tools returned. Literature is cited only from what
`search_literature` actually came back with, always with a PMID — the pre-agent
prompt banned citing studies at all precisely because the model fabricated them.
Correlations over weeks of n=1 data are weak evidence and must be hedged;
wearable calorie, HRV and sleep-stage figures are estimates, so describe them as
directional.

### Deployment

`bash scripts/deploy.sh` is the only supported path, and it must stay
self-verifying — a failed push aborts, and the bundle the server returns is
checked against the one just built. Never edit files directly on the Dell: it is
a git checkout that the poller resets to main, so local changes get stashed or
cleaned away. The poller also deploys, and its startup redeploys every branch
labelled `claude-review`; deploy.sh sequences around that deliberately.
