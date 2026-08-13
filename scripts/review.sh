#!/usr/bin/env bash
# Put the newest issue awaiting review onto the phone.
#
# The Dell is one checkout serving one app, so there is a single slot and
# deploying and reviewing want different things in it. deploy.sh always ends on
# main - your code should be what runs after you deploy - and this is the
# explicit way to switch the other way for a while.
#
# Nothing here re-runs Claude. It is a deployment action: the branch is already
# committed, pushed and open as a PR. Approving the issue with `lgtm` hands the
# slot on by itself, so you rarely need this twice in a row.
#
# Usage: bash scripts/review.sh
set -euo pipefail

DELL_HOST="conor@100.95.44.32"
APP_DIR="health-app"
APP_URL="https://conor-latitude-3540.tail6b532d.ts.net"

echo "==> Asking the Dell what is awaiting review..."

# Runs the poller's own deploy_review_slot so there is one implementation of
# "which branch gets the phone" rather than a second copy that can drift.
ssh "$DELL_HOST" bash --login -s << REMOTE
set -euo pipefail
cd ~/$APP_DIR
export PATH=\$HOME/.local/bin:\$PATH
mkdir -p ~/$APP_DIR/logs

python3 - <<'PY'
import importlib.util
spec = importlib.util.spec_from_file_location("gp", "scripts/github_poller.py")
gp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gp)

live = gp.deploy_review_slot()
if live is None:
    print("NOTHING_IN_REVIEW")
else:
    print(f"DEPLOYED_ISSUE={live}")
PY
REMOTE

echo "==> Verifying..."
curl -fsS --max-time 15 "$APP_URL/api/health" > /dev/null
BRANCH=$(ssh "$DELL_HOST" "cd ~/$APP_DIR && git branch --show-current")
echo "    health OK, serving branch: $BRANCH"

if [ "$BRANCH" = "main" ]; then
  echo ""
  echo "==> Nothing was awaiting review - main is still what runs."
else
  echo ""
  echo "==> $BRANCH is now live at $APP_URL"
  echo "    Force-quit the PWA from the app switcher to pick it up."
  echo "    Comment 'lgtm' on the issue to merge, or reply with feedback to"
  echo "    change it - anything that is not 'lgtm' resumes Claude."
  echo "    Run scripts/deploy.sh to put main back."
fi
