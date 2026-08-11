#!/usr/bin/env bash
# Deploy the health app to the Dell host over SSH.
# Builds frontend locally, pushes code, copies static files, and restarts.
# Usage: bash scripts/deploy.sh
set -euo pipefail

DELL_HOST="conor@100.95.44.32"
APP_DIR="health-app"
APP_URL="https://conor-latitude-3540.tail6b532d.ts.net"

echo "==> Building frontend locally..."
bash scripts/build_frontend.sh

echo "==> Pushing to origin..."
# A failed push used to only warn, and the deploy carried on to pull a commit
# that was never sent - so the Dell happily redeployed the previous release
# while the new one sat on this laptop. There is nothing worth deploying past
# this point, so fail here.
git push origin main

echo "==> Copying frontend build to Dell..."
scp -r backend/app/static "$DELL_HOST:~/$APP_DIR/backend/app/"

echo "==> Connecting to Dell ($DELL_HOST)..."

ssh "$DELL_HOST" bash --login -s << REMOTE
set -euo pipefail
cd ~/$APP_DIR
mkdir -p ~/$APP_DIR/logs
POLLER_LOG=~/$APP_DIR/logs/poller.log
touch \$POLLER_LOG

# The poller is restarted FIRST, deliberately. On startup it redeploys every
# branch labelled claude-review - checking the branch out, rebuilding the
# frontend and restarting uvicorn. Restarting it last, as this script used to,
# meant it overwrote the deploy seconds after the script reported success.
echo "==> Restarting GitHub poller..."
LOG_MARK=\$(wc -l < \$POLLER_LOG)
pkill -f "github_poller[.]py" 2>/dev/null || true
sleep 1
nohup python3 ~/$APP_DIR/scripts/github_poller.py >> \$POLLER_LOG 2>&1 &
disown

# Only lines written after the restart count - the marker from a previous run
# is still sitting in the log.
echo "==> Waiting for poller startup redeploys to finish..."
SETTLED=no
for _ in \$(seq 1 72); do
  if tail -n +\$((LOG_MARK + 1)) \$POLLER_LOG | grep -q "entering poll loop"; then
    SETTLED=yes
    break
  fi
  sleep 5
done
if [ "\$SETTLED" = yes ]; then
  echo "    poller settled"
else
  echo "    WARNING: poller still busy after 6 min; it may overwrite this deploy" >&2
fi

echo "==> Pulling latest code..."
git stash --include-untracked 2>/dev/null || true
git checkout main
git pull --ff-only

echo "==> Installing backend dependencies..."
cd backend
uv sync

# Bound to localhost because 'tailscale serve' fronts it with HTTPS. The
# poller starts it the same way; binding 0.0.0.0 here made the app's exposure
# depend on which of the two deployed last.
echo "==> Restarting uvicorn..."
pkill -f "uvicorn app[.]main" 2>/dev/null || true
sleep 2
nohup uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 \
  >> ~/$APP_DIR/logs/uvicorn.log 2>&1 &
disown

echo "==> Verifying backend..."
sleep 6
curl -fsS --max-time 10 http://127.0.0.1:8000/api/health > /dev/null
echo "    health OK, serving \$(git rev-parse --short HEAD)"
REMOTE

# The symptom that started all this was the server quietly serving a different
# bundle than the one just built, so check rather than assume.
echo "==> Verifying the deployed frontend is the one we just built..."
LOCAL_ASSET=$(grep -o 'assets/index-[^"]*\.js' backend/app/static/index.html | head -1)
REMOTE_ASSET=$(curl -fsS --max-time 20 "$APP_URL/" | grep -o 'assets/index-[^"]*\.js' | head -1)
if [ "$LOCAL_ASSET" != "$REMOTE_ASSET" ]; then
  echo "    MISMATCH: built $LOCAL_ASSET but the server is serving $REMOTE_ASSET" >&2
  echo "    Something redeployed over this. Check logs/poller.log on the Dell." >&2
  exit 1
fi
echo "    OK: serving $LOCAL_ASSET"

echo ""
echo "==> Deploy complete! Live at $APP_URL"
echo "    On the phone, force-quit the PWA from the app switcher to pick it up."
