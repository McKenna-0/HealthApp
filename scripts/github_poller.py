#!/usr/bin/env python3
"""Poll GitHub for issues labeled 'claude' and implement them via Claude CLI.

Runs as a standalone background process on the Dell server. Uses the Claude
Code CLI (subscription-based, no API key needed) to automatically implement
features and fix bugs described in GitHub issues.

Usage:
    python scripts/github_poller.py          # run in foreground
    nohup python scripts/github_poller.py >> logs/poller.log 2>&1 &  # background
"""

import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

# ── Configuration ──────────────────────────────────────────────────────────

REPO = os.environ.get("GITHUB_REPO", "McKenna-0/HealthApp")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL_MINUTES", "5")) * 60
REPO_DIR = Path(__file__).resolve().parent.parent  # health-app root
CLAUDE_TIMEOUT = 1800  # 30 minutes max per issue

LABEL_TRIGGER = "claude"
LABEL_WIP = "claude-wip"
LABEL_DONE = "claude-done"
LABEL_FAILED = "claude-failed"

RATE_LIMIT_HINTS = ["rate limit", "usage limit", "capacity", "try again later",
                    "too many requests", "throttl"]

# ── Logging ────────────────────────────────────────────────────────────────

log_dir = REPO_DIR / "logs"
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(log_dir / "poller.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("github-poller")


# ── GitHub helpers (via gh CLI) ────────────────────────────────────────────

def gh(*args: str, input_text: str | None = None) -> subprocess.CompletedProcess:
    """Run a gh CLI command and return the result."""
    cmd = ["gh", *args]
    return subprocess.run(
        cmd, capture_output=True, text=True, input=input_text, cwd=REPO_DIR,
    )


def get_issues_with_label(label: str) -> list[dict]:
    """Fetch open issues with the given label."""
    result = gh(
        "issue", "list",
        "--repo", REPO,
        "--label", label,
        "--json", "number,title,body",
        "--state", "open",
    )
    if result.returncode != 0:
        log.error("Failed to list issues: %s", result.stderr.strip())
        return []
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        log.error("Bad JSON from gh: %s", result.stdout[:200])
        return []


def set_labels(issue: int, *, add: list[str] | None = None,
               remove: list[str] | None = None) -> None:
    """Add/remove labels on an issue."""
    args = ["issue", "edit", str(issue), "--repo", REPO]
    for label in (add or []):
        args += ["--add-label", label]
    for label in (remove or []):
        args += ["--remove-label", label]
    result = gh(*args)
    if result.returncode != 0:
        log.warning("Label update failed on #%d: %s", issue, result.stderr.strip())


def comment(issue: int, body: str) -> None:
    """Post a comment on an issue."""
    result = gh("issue", "comment", str(issue), "--repo", REPO, "--body", body)
    if result.returncode != 0:
        log.warning("Comment failed on #%d: %s", issue, result.stderr.strip())


# ── Git helpers ────────────────────────────────────────────────────────────

def git(*args: str) -> subprocess.CompletedProcess:
    """Run a git command in the repo directory."""
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, cwd=REPO_DIR,
    )


def reset_to_main() -> bool:
    """Ensure we're on a clean main branch, ready for the next issue."""
    git("checkout", "main")
    git("clean", "-fd")
    git("checkout", ".")
    result = git("pull", "--ff-only")
    if result.returncode != 0:
        log.warning("git pull --ff-only failed: %s", result.stderr.strip())
        return False
    return True


# ── Core logic ─────────────────────────────────────────────────────────────

def build_prompt(issue: dict) -> str:
    """Build the prompt for Claude CLI from an issue."""
    number = issue["number"]
    title = issue["title"]
    body = issue.get("body") or "(no description)"
    return f"""Read the CLAUDE.md file for project context and coding conventions.

ISSUE #{number}: {title}

{body}

Implement this issue:
1. Create a new git branch named 'claude/issue-{number}' from main
2. Read the relevant code to understand the current state
3. Implement the feature or fix described in the issue
4. Run backend tests with `cd backend && uv run pytest` to verify nothing is broken
5. Run frontend lint with `cd frontend && npm run lint`
6. Commit your changes with a descriptive message referencing issue #{number}
7. Push the branch and create a pull request linking to issue #{number}

Tech stack: FastAPI + SQLAlchemy/SQLite backend, React 19 + TypeScript + Vite frontend.
Python managed with uv. Frontend uses React Query, Recharts, date-fns.
"""


def is_rate_limited(output: str) -> bool:
    """Check if Claude CLI output suggests a rate limit."""
    lower = output.lower()
    return any(hint in lower for hint in RATE_LIMIT_HINTS)


def process_issue(issue: dict) -> bool:
    """Process a single GitHub issue. Returns True on success."""
    number = issue["number"]
    title = issue["title"]
    log.info("Processing issue #%d: %s", number, title)

    # Mark as work-in-progress
    set_labels(number, add=[LABEL_WIP], remove=[LABEL_TRIGGER])

    # Clean working tree
    if not reset_to_main():
        set_labels(number, add=[LABEL_FAILED], remove=[LABEL_WIP])
        comment(number, "⚠️ Poller failed: could not reset to clean main branch.")
        return False

    # Run Claude CLI
    prompt = build_prompt(issue)
    try:
        result = subprocess.run(
            ["claude", "-p", "--dangerously-skip-permissions"],
            input=prompt,
            capture_output=True,
            text=True,
            cwd=str(REPO_DIR),
            timeout=CLAUDE_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        log.error("Claude timed out on issue #%d", number)
        set_labels(number, add=[LABEL_FAILED], remove=[LABEL_WIP])
        comment(number, "⚠️ Claude timed out after 30 minutes.")
        reset_to_main()
        return False

    combined_output = (result.stdout or "") + (result.stderr or "")

    if result.returncode == 0:
        log.info("Issue #%d completed successfully", number)
        set_labels(number, add=[LABEL_DONE], remove=[LABEL_WIP])
        # Extract PR URL from output if possible
        pr_line = ""
        for line in combined_output.splitlines():
            if "github.com" in line and "/pull/" in line:
                pr_line = line.strip()
                break
        msg = f"✅ Claude has finished implementing this issue."
        if pr_line:
            msg += f"\n\nPR: {pr_line}"
        comment(number, msg)
        return True
    else:
        # Check for rate limiting
        if is_rate_limited(combined_output):
            log.warning("Rate limited on issue #%d — will retry next cycle", number)
            set_labels(number, add=[LABEL_TRIGGER], remove=[LABEL_WIP])
            return False

        log.error("Claude failed on issue #%d (exit %d)", number, result.returncode)
        # Truncate output for the comment
        error_snippet = combined_output[-1500:] if len(combined_output) > 1500 else combined_output
        set_labels(number, add=[LABEL_FAILED], remove=[LABEL_WIP])
        comment(number,
                f"⚠️ Claude failed to implement this issue (exit code {result.returncode}).\n\n"
                f"```\n{error_snippet}\n```")
        return False
    finally:
        reset_to_main()


def recover_stuck_issues() -> None:
    """On startup, recover any issues stuck in 'claude-wip' state."""
    stuck = get_issues_with_label(LABEL_WIP)
    for issue in stuck:
        log.info("Recovering stuck issue #%d: %s", issue["number"], issue["title"])
        set_labels(issue["number"], add=[LABEL_TRIGGER], remove=[LABEL_WIP])


# ── Main loop ──────────────────────────────────────────────────────────────

def main() -> None:
    log.info("GitHub issue poller started (repo=%s, interval=%ds)", REPO, POLL_INTERVAL)
    log.info("Repo directory: %s", REPO_DIR)

    recover_stuck_issues()

    while True:
        try:
            issues = get_issues_with_label(LABEL_TRIGGER)
            if issues:
                log.info("Found %d issue(s) to process", len(issues))
                for issue in issues:
                    process_issue(issue)
            else:
                log.debug("No issues to process")
        except Exception:
            log.exception("Unexpected error in poll cycle")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Poller stopped by user")
        sys.exit(0)
