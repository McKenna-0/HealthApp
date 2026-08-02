# Deploying to the Dell (always-on host, reachable anywhere via Tailscale)

The app runs on a Dell machine (`100.95.44.32` on Tailscale) serving the FastAPI
backend + built frontend on port 8000. Tailscale provides HTTPS and remote access
from your iPhone and laptop. Nothing is exposed to the public internet.

## 1. Prerequisites on the Dell

- **Git**, **uv** (Python), **Node.js** (for frontend builds)
- **Tailscale** installed and logged in
- **OpenSSH Server** enabled (Settings → Optional Features → OpenSSH Server)
- `.env` file in the repo root with Garmin credentials, API keys, etc.

## 2. Initial setup (one-time)

From the **laptop**, clone and migrate the database to the Dell:

```bash
# SSH into the Dell
ssh conor@100.95.44.32

# Clone the repo (or copy it)
cd ~
git clone <your-repo-url> "Health app"
cd "Health app"

# Copy .env from laptop (run from laptop, not Dell)
# scp "C:/Users/conor/Health app/.env" conor@100.95.44.32:"~/Health app/.env"

# Snapshot the database (WAL-safe) — run on whichever machine has the live DB
cd backend
uv run python -c "import sqlite3; sqlite3.connect('data/health.db').backup(sqlite3.connect('health-snap.db')); print('snapshot ok')"

# From laptop: copy the snapshot to the Dell
# scp "C:/Users/conor/Health app/backend/health-snap.db" conor@100.95.44.32:"~/Health app/backend/data/health.db"

# On the Dell: install deps and build
cd "~/Health app"
cd backend && uv sync && cd ..
cd frontend && npm ci && cd ..
bash scripts/build_frontend.sh
```

## 3. Start the app

Using the startup bat (auto-starts at logon):

1. Press Win+R → `shell:startup` → Enter.
2. Create a shortcut to `deploy\start-app.bat`.

Or start manually:

```bash
cd "Health app/backend"
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 4. HTTPS via Tailscale

On the Dell (PowerShell):

```powershell
tailscale serve --bg --https=443 http://127.0.0.1:8000
tailscale serve status   # shows https://<dell>.<tailnet>.ts.net
```

## 5. iPhone

1. Tailscale app on and connected.
2. Safari → `https://<dell>.<tailnet>.ts.net`.
3. Share → **Add to Home Screen** — full PWA with camera/barcode support.

## 6. Deploying updates

From the **laptop**, run the one-command deploy script:

```bash
bash scripts/deploy.sh
```

This SSHs into the Dell, pulls the latest code, rebuilds the frontend, syncs
backend deps, and restarts uvicorn. See `scripts/deploy.sh` for details.

Or manually:

```bash
ssh conor@100.95.44.32
cd "Health app"
git pull --ff-only
bash scripts/build_frontend.sh
cd backend && uv sync
# restart uvicorn (kill existing, relaunch via start-app.bat or manually)
```

Schema changes apply automatically on restart (the app adds missing tables/columns).

## Troubleshooting

- **Can't SSH in**: Ensure OpenSSH Server is running on the Dell
  (`Get-Service sshd` in PowerShell). Check Tailscale is connected on both machines.
- **App unreachable from phone**: Check `tailscale status` on both Dell and iPhone.
  Both must be on the same tailnet.
- **Garmin auth broken**: Delete `backend/.garmin_tokens/` on the Dell and restart —
  it re-authenticates using `.env` credentials.
- **Stale PWA on phone**: Kill and reopen the PWA after deploys for service worker refresh.
- **Build fails on Dell**: Ensure Node.js and uv are installed and on PATH in the SSH session.
