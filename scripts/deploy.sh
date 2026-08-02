#!/usr/bin/env bash
# Deploy the health app to the Dell host over SSH.
# Usage: bash scripts/deploy.sh
set -euo pipefail

DELL_HOST="conor@100.95.44.32"
APP_DIR="/home/conor/health-app"   # path on the Dell

echo "==> Connecting to Dell ($DELL_HOST)..."

ssh "$DELL_HOST" bash -s << REMOTE
set -euo pipefail
cd "$APP_DIR"

echo "==> Pulling latest code..."
git stash --include-untracked 2>/dev/null || true
git pull --ff-only

echo "==> Installing backend dependencies..."
cd backend
uv sync
cd ..

echo "==> Building frontend..."
cd frontend
npm ci --prefer-offline
npm run build
cd ..

echo "==> Copying frontend build to backend static dir..."
rm -rf backend/app/static
mkdir -p backend/app/static
cp -r frontend/dist/* backend/app/static/

echo "==> Restarting uvicorn..."
# Kill existing uvicorn process, then relaunch detached
taskkill //F //IM uvicorn.exe 2>/dev/null || true
# Small delay for port release
sleep 2
cd backend
nohup uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 \
  >> "\$LOCALAPPDATA/health-app/uvicorn.log" 2>&1 &
disown

echo ""
echo "==> Deploy complete! App should be live at http://100.95.44.32:8000"
REMOTE
