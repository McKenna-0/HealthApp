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
# while the new one sat on this laptop. Nothing past this point is worth
# doing if the code did not leave, so fail here.
git push origin main

echo "==> Connecting to Dell ($DELL_HOST)..."

# The whole dance below exists because the poller also deploys. On startup it
# redeploys every branch labelled claude-review: checks the branch out,
# rebuilds the frontend into backend/app/static, restarts uvicorn. It has to
# run in the middle - after the pull so it is the current build of the poller,
# and before we put main back so it cannot overwrite us afterwards.
ssh "$DELL_HOST" bash --login -s << REMOTE
set -euo pipefail
cd ~/$APP_DIR

echo "==> Pulling latest code..."
git stash --include-untracked 2>/dev/null || true
git checkout main
git pull --ff-only
mkdir -p ~/$APP_DIR/logs
POLLER_LOG=~/$APP_DIR/logs/poller.log
touch \$POLLER_LOG

# Restarted here, not at the end. Restarting it last meant its startup
# redeploys landed seconds after this script printed "Deploy complete", so the
# server ended up running whichever review branch it processed last.
echo "==> Restarting GitHub poller..."
LOG_MARK=\$(wc -l < \$POLLER_LOG)
pkill -f "github_poller[.]py" 2>/dev/null || true
sleep 1
nohup python3 ~/$APP_DIR/scripts/github_poller.py >> \$POLLER_LOG 2>&1 &
disown

# Only lines written after this restart count - the marker from the previous
# run is still in the log. A poller predating the marker never matches, so the
# timeout has to be survivable rather than fatal.
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
  echo "    WARNING: no settle marker after 6 min - continuing anyway." >&2
  echo "    If this persists the Dell is running a poller from before the" >&2
  echo "    marker was added; the next deploy will pick it up." >&2
fi

# The poller leaves the repo on whichever review branch it deployed last, so
# main has to be re-asserted now that it is done.
echo "==> Restoring main..."
git stash --include-untracked 2>/dev/null || true
git checkout main

echo "==> Installing backend dependencies..."
cd backend
uv sync

# Bound to localhost because 'tailscale serve' fronts it with HTTPS. The
# poller starts it the same way; binding 0.0.0.0 here made the app's exposure
# depend on which of the two had deployed last.
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

# Copied last, on purpose: the poller rebuilds the frontend into this exact
# directory during its startup redeploys, so anything sent earlier gets
# overwritten while we wait.
echo "==> Copying frontend build to Dell..."
scp -q -r backend/app/static "$DELL_HOST:~/$APP_DIR/backend/app/"

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
