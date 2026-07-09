#!/usr/bin/env bash
# Build the frontend and copy it into the backend's static dir so FastAPI
# serves the whole app on one port (no CORS, works over LAN).
set -euo pipefail
cd "$(dirname "$0")/.."

(cd frontend && npm run build)
rm -rf backend/app/static
mkdir -p backend/app/static
cp -r frontend/dist/* backend/app/static/
echo "Frontend built and copied to backend/app/static"
