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
