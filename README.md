# Personal Health App

Self-hosted health tracker: Garmin metrics (sleep, HRV, resting HR, steps, stress, Body Battery, calories), manual weight/food/context logging, and derived energy-balance + TDEE analytics. Runs on your laptop; open it from your iPhone over the same WiFi.

## Stack

- **Backend**: FastAPI + SQLite (Python 3.13 via `uv`), APScheduler for scheduled syncs
- **Frontend**: React + Vite + Recharts, served by the backend as a static SPA
- **Data**: `python-garminconnect` (unofficial Garmin API) or a built-in mock data source

## Quick start

```bash
# 1. Backend deps (uv manages Python 3.13 automatically)
cd backend && uv sync

# 2. Seed 90 days of realistic mock data
uv run python scripts/seed_mock.py

# 3. Build the frontend into the backend
cd .. && bash scripts/build_frontend.sh

# 4. Run
cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 — API docs at http://localhost:8000/docs.

## Development

Run the backend on 8000, then the frontend dev server with hot reload:

```bash
cd frontend && npm run dev
```

Vite proxies `/api` to the backend, so no CORS setup is needed. After UI changes, re-run `bash scripts/build_frontend.sh` to update what the backend serves.

## Using it from your iPhone (same WiFi)

1. Find your laptop's LAN IP: `ipconfig` → look for "IPv4 Address" under your WiFi adapter (e.g. `192.168.1.42`).
2. Allow inbound connections through Windows Firewall (run once in an **admin** terminal):
   ```
   netsh advfirewall firewall add rule name="Health app" dir=in action=allow protocol=TCP localport=8000
   ```
   Also make sure your WiFi network profile is set to **Private** (Settings → Network → WiFi → your network).
3. On the iPhone, open Safari → `http://<laptop-ip>:8000`.
4. Share button → **Add to Home Screen** for an app-like icon and fullscreen launch.

Tips: set a DHCP reservation on your router so the laptop IP doesn't change. Full PWA offline support requires HTTPS (e.g. via `mkcert`) — not set up by default; the app still works fine as a home-screen web app.

## Mock vs Garmin mode

The app defaults to **mock mode**: deterministic, physiologically-correlated sample data (alcohol nights depress HRV and sleep, an illness stretch raises resting HR, weight trends down ~0.3 kg/week) so everything works before you have a Garmin.

To switch to real Garmin data:

1. Copy `.env.example` to `.env` and set:
   ```
   DATA_SOURCE=garmin
   GARMIN_EMAIL=you@example.com
   GARMIN_PASSWORD=...
   ```
2. Restart the backend and hit **Sync now** on the Settings page (or `POST /api/sync?days=30`).
3. OAuth tokens are cached in `backend/.garmin_tokens/` — the password is only used for the first login.

**Caveat**: `python-garminconnect` is an unofficial, reverse-engineered API and breaks occasionally when Garmin changes their auth. All Garmin-specific code is isolated in `backend/app/datasources/garmin_source.py`; if it breaks, the rest of the app keeps working and you can flip back to `DATA_SOURCE=mock`.

## Sync schedule

While the backend is running, syncs fire at 07:30 and 21:30 (timezone from `TZ` in `.env`), plus a catch-up sync on startup whenever the last successful sync is older than 12 hours (covers laptop sleep). Manual sync any time from Settings.

## Analytics

- **Weight trend**: exponentially-weighted moving average (α = 0.1) over daily weights, smoothing out water-weight noise.
- **Energy balance**: logged calories in − Garmin calories out, per day. Days not marked "complete" are shown greyed and excluded from TDEE.
- **TDEE estimate**: `mean intake − weight-trend slope × 7700 kcal/kg` over a 28-day window; needs ≥10 fully-logged days and ≥5 weigh-ins. This back-calculates your true maintenance calories from what actually happened, independent of Garmin's estimate.

## Tests

```bash
cd backend && uv run pytest
```

Covers mock-data determinism and correlations, the EWMA/TDEE math, and the Garmin JSON→DTO mappers (against recorded sample payloads).
