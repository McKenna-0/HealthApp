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
git clone <your-repo-url> health-app
cd health-app

# Copy .env from laptop (run from laptop, not Dell)
# scp "C:/Users/conor/Health app/.env" conor@100.95.44.32:~/health-app/.env

# Snapshot the database (WAL-safe) — run on whichever machine has the live DB
cd backend
uv run python -c "import sqlite3; sqlite3.connect('data/health.db').backup(sqlite3.connect('health-snap.db')); print('snapshot ok')"

# From laptop: copy the snapshot to the Dell
# scp "C:/Users/conor/Health app/backend/health-snap.db" conor@100.95.44.32:~/health-app/backend/data/health.db

# On the Dell: install deps and build
cd ~/health-app
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
cd health-app/backend
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

## 5.5. Windows laptop

1. Ensure Tailscale is running on both the Dell and the laptop.
2. Open `https://<dell>.<tailnet>.ts.net` in any browser on the laptop.

## 6. GitHub Issue Poller (auto-implement from phone)

A background script (`scripts/github_poller.py`) on the Dell polls GitHub every
5 minutes for issues labeled `claude`. When it finds one, it runs the Claude
Code CLI (using your subscription — no API costs) to implement the feature or
fix, then opens a PR for you to review on your phone.

### How it works

```
You (phone)                     Dell server
───────────                     ───────────
Create GitHub issue      →
Add 'claude' label       →      Poller detects issue (≤5 min)
                                 Label → claude-wip
                                 Claude CLI (Opus) implements, tests
                         ←      If Claude needs info: label → claude-waiting
                                 Comment posted with Claude's question
Reply to the comment     →      Poller detects reply (≤5 min)
                                 Label → claude-wip, session resumed
                                 Pushes branch, opens PR
                                 Auto-deploys branch to your phone
                                 Label → claude-review
Test on your phone       ←      Changes are live on the PWA
Post feedback comment    →      Poller resumes Claude with feedback
                                 Claude iterates, redeploys branch
                                 (repeat up to 10 turns)
Comment 'lgtm'           →      PR merged, main deployed
                                 Label → claude-done
```

**Label state machine:** `claude` → `claude-wip` → `claude-review` (test on phone) → `claude-done` / back to `claude-wip` (feedback)

- On success: branch auto-deployed to your phone, label set to `claude-review`
- On `claude-review`: test on phone, comment feedback to iterate, or comment
  **lgtm** to merge the PR and deploy main
- On failure: error posted as comment, label set to `claude-failed`
- On needs clarification: Claude's question posted as comment, label set to
  `claude-waiting` — reply to the issue and the poller resumes automatically
- On rate limit: label reverts to `claude` (or `claude-waiting` if mid-conversation), retries next cycle
- On crash recovery (poller restart): stuck `claude-wip` issues are
  re-queued, `claude-review` issues re-deploy their branch, `claude-waiting` issues continue waiting
- Max 10 conversation turns per issue (includes review feedback rounds)

### Tips for writing good issues

- Be specific: "Add a rest timer to the workout page that counts down from
  the configured rest period" works better than "add timer"
- Describe what you see in text — Claude cannot view attached images
- Mention relevant files if you know them
- One feature/fix per issue — Claude works on them sequentially

### Prerequisites on the Dell (one-time)

- **`gh` CLI** installed and authenticated: `gh auth login` + `gh auth setup-git`
- **`claude` CLI** at `~/.local/bin/claude`, logged in: `claude login`
- **SSH key** from laptop in `~/.ssh/authorized_keys` (for deploy script)
- **Trust dialog accepted**: Run `claude` interactively once in the repo to accept the workspace trust dialog
- GitHub labels created:
  ```bash
  gh label create claude-wip --color c5def5 --repo McKenna-0/HealthApp
  gh label create claude-done --color 0e8a16 --repo McKenna-0/HealthApp
  gh label create claude-failed --color d93f0b --repo McKenna-0/HealthApp
  gh label create claude-waiting --color fbca04 --repo McKenna-0/HealthApp
  gh label create claude-review --color 1d76db --repo McKenna-0/HealthApp
  ```

### Start the poller

Auto-start at logon: `~/.config/autostart/github-poller.desktop` is already
configured. Or start manually:

```bash
cd ~/health-app
mkdir -p logs
nohup python3 scripts/github_poller.py >> logs/poller.log 2>&1 &
disown
```

The deploy script (`scripts/deploy.sh`) automatically restarts the poller on
each deploy.

### Usage from phone

1. Open GitHub mobile app → create an issue describing the feature/bug
2. Add the `claude` label
3. Within 5 minutes, the poller picks it up and Claude starts working
4. Watch label changes: `claude` → `claude-wip` → `claude-done` or `claude-failed`
5. Review the PR on your phone, merge if good
6. If `claude-failed`, check the comment on the issue for the error

### Monitoring

```bash
# Poller status
tail -f ~/health-app/logs/poller.log

# Live Claude output for a specific issue
tail -f ~/health-app/logs/claude-issue-1.log

# Check process is running
ps aux | grep github_poller
```

### Re-triggering a failed issue

Remove the `claude-failed` label and re-add `claude` on the GitHub issue.

### Conversation state

Per-issue state (session ID, turn count, timestamps) is stored in
`logs/conversation_state.json`. This file is preserved across deploys and
poller restarts. If deleted, any `claude-waiting` issues will be re-queued
for a fresh attempt.

## 7. Deploying updates

From the **laptop**, run the one-command deploy script:

```bash
bash scripts/deploy.sh
```

This SSHs into the Dell, pulls the latest code, rebuilds the frontend, syncs
backend deps, and restarts uvicorn. See `scripts/deploy.sh` for details.

Or manually:

```bash
ssh conor@100.95.44.32
cd ~/health-app
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
- **MFP Sync button missing**: The MFP cookie is stored per-database. After deploying
  to the Dell, visit Settings on the Dell version and configure your MFP cookie there.
- **Stale PWA on phone**: Kill and reopen the PWA after deploys for service worker refresh.
- **Build fails on Dell**: Ensure Node.js and uv are installed and on PATH in the SSH session.
