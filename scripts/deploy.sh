#!/usr/bin/env bash
# Deploy the health app to the Dell host over SSH.
# Builds frontend locally, pushes code, copies static files, and restarts.
# Usage: bash scripts/deploy.sh
set -euo pipefail

DELL_HOST="conor@100.95.44.32"
APP_DIR="health-app"

echo "==> Building frontend locally..."
bash scripts/build_frontend.sh

echo "==> Pushing to origin..."
git push origin main || echo "WARNING: git push failed — ensure code is pushed before deploying"

echo "==> Copying frontend build to Dell..."
scp -r backend/app/static "$DELL_HOST:~/$APP_DIR/backend/app/"

echo "==> Connecting to Dell ($DELL_HOST)..."

ssh "$DELL_HOST" bash --login -s << REMOTE
set -euo pipefail
cd ~/$APP_DIR

echo "==> Pulling latest code..."
git stash --include-untracked 2>/dev/null || true
git pull --ff-only

echo "==> Installing backend dependencies..."
cd backend
uv sync

echo "==> Restarting uvicorn..."
pkill -f "uvicorn app.main:app" 2>/dev/null || true
sleep 2
mkdir -p ~/$APP_DIR/logs
nohup uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 \
  >> ~/$APP_DIR/logs/uvicorn.log 2>&1 &
disown

echo "==> Restarting GitHub poller..."
pkill -f "github_poller.py" 2>/dev/null || true
sleep 1
nohup python3 ~/$APP_DIR/scripts/github_poller.py \
  >> ~/$APP_DIR/logs/poller.log 2>&1 &
disown

echo ""
echo "==> Deploy complete! App should be live at http://100.95.44.32:8000"
REMOTE
