#!/usr/bin/env python3
"""Poll GitHub for issues labeled 'claude' and implement them via Claude CLI.

Runs as a standalone background process on the Dell server. Uses the Claude
Code CLI (subscription-based, no API key needed) to automatically implement
features and fix bugs described in GitHub issues.

Supports multi-turn conversations: when Claude needs clarification, it posts
a comment on the issue and waits for the user to reply via GitHub mobile.

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
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── Configuration ──────────────────────────────────────────────────────────

REPO = os.environ.get("GITHUB_REPO", "McKenna-0/HealthApp")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL_MINUTES", "5")) * 60
REPO_DIR = Path(__file__).resolve().parent.parent  # health-app root
CLAUDE_TIMEOUT = 1800  # 30 minutes max per issue
STALL_TIMEOUT = 180    # kill if 0 bytes output after 3 minutes

LABEL_TRIGGER = "claude"
LABEL_WIP = "claude-wip"
LABEL_DONE = "claude-done"
LABEL_FAILED = "claude-failed"
LABEL_WAITING = "claude-waiting"
LABEL_REVIEW = "claude-review"

MAX_CONVERSATION_TURNS = 10
RETRY_COOLDOWN_HOURS = 2

CLAUDE_BIN = os.environ.get("CLAUDE_BIN", str(Path.home() / ".local" / "bin" / "claude"))
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "opus")

RATE_LIMIT_HINTS = ["rate limit", "usage limit", "capacity", "try again later",
                    "too many requests", "throttl"]

STATE_FILE = REPO_DIR / "logs" / "conversation_state.json"

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


# ── State persistence ─────────────────────────────────────────────────────

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            log.warning("Corrupt state file, starting fresh")
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def cleanup_issue_state(issue_key: str) -> None:
    state = load_state()
    state.pop(issue_key, None)
    save_state(state)


def session_id_for_issue(issue_number: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{REPO}#{issue_number}"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def set_retry_cooldown(state: dict, issue_key: str) -> None:
    """Set a cooldown so the poller skips this issue until usage refreshes."""
    retry_at = datetime.now(timezone.utc) + timedelta(hours=RETRY_COOLDOWN_HOURS)
    if issue_key not in state:
        state[issue_key] = {"session_id": session_id_for_issue(int(issue_key)), "turn_count": 0}
    state[issue_key]["retry_after"] = retry_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    save_state(state)


def is_on_cooldown(state: dict, issue_key: str) -> bool:
    """Check if an issue is still in its retry cooldown period."""
    issue_state = state.get(issue_key, {})
    retry_after = issue_state.get("retry_after")
    if not retry_after:
        return False
    if retry_after > _now_iso():
        return True
    # Cooldown expired — clear it
    issue_state.pop("retry_after", None)
    save_state(state)
    return False


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


def _get_bot_login() -> str:
    if not hasattr(_get_bot_login, "_cached"):
        result = gh("api", "/user", "--jq", ".login")
        _get_bot_login._cached = result.stdout.strip() if result.returncode == 0 else ""
    return _get_bot_login._cached


def get_user_replies(issue_number: int, after_timestamp: str) -> list[str]:
    """Get user comment bodies posted after the given ISO timestamp."""
    result = gh(
        "issue", "view", str(issue_number),
        "--repo", REPO,
        "--json", "comments",
    )
    if result.returncode != 0:
        return []
    try:
        comments = json.loads(result.stdout).get("comments", [])
    except (json.JSONDecodeError, KeyError):
        return []

    bot_login = _get_bot_login()
    replies = []
    for c in comments:
        author = c.get("author", {}).get("login", "")
        created = c.get("createdAt", "")
        if author != bot_login and created > after_timestamp:
            replies.append(c.get("body", ""))
    return replies


# ── Work detection ─────────────────────────────────────────────────────────

def detect_pr_created(issue_number: int) -> str | None:
    """Check if an open PR exists for this issue's branch. Returns URL or None."""
    result = gh(
        "pr", "list",
        "--repo", REPO,
        "--head", f"claude/issue-{issue_number}",
        "--json", "url",
        "--state", "open",
    )
    if result.returncode != 0:
        return None
    try:
        prs = json.loads(result.stdout)
        return prs[0]["url"] if prs else None
    except (json.JSONDecodeError, IndexError, KeyError):
        return None


def detect_commits_on_branch(issue_number: int) -> bool:
    """Check if the claude branch has commits beyond main."""
    branch = f"claude/issue-{issue_number}"
    result = git("rev-list", "--count", f"main..{branch}")
    if result.returncode != 0:
        return False
    try:
        return int(result.stdout.strip()) > 0
    except ValueError:
        return False


def detect_pr_merged(issue_number: int) -> bool:
    """Check if the PR for this issue has been merged."""
    result = gh(
        "pr", "list",
        "--repo", REPO,
        "--head", f"claude/issue-{issue_number}",
        "--json", "url,mergedAt",
        "--state", "merged",
    )
    if result.returncode != 0:
        return False
    try:
        return len(json.loads(result.stdout)) > 0
    except (json.JSONDecodeError, IndexError):
        return False


# ── Git helpers ────────────────────────────────────────────────────────────

def git(*args: str) -> subprocess.CompletedProcess:
    """Run a git command in the repo directory."""
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, cwd=REPO_DIR,
    )


def reset_to_main() -> bool:
    """Ensure we're on a clean main branch, ready for the next issue."""
    git("checkout", "main")
    git("clean", "-fd", "--exclude=logs")
    git("checkout", ".")
    result = git("pull", "--ff-only")
    if result.returncode != 0:
        log.warning("git pull --ff-only failed: %s", result.stderr.strip())
        return False
    return True


def _deploy_env() -> dict:
    """Build an env dict with ~/.local/bin and nvm node on PATH."""
    env = os.environ.copy()
    extra = [str(Path.home() / ".local" / "bin")]
    nvm_node = Path.home() / ".nvm" / "versions" / "node"
    node_dirs = sorted(nvm_node.iterdir()) if nvm_node.is_dir() else []
    if node_dirs:
        extra.append(str(node_dirs[-1] / "bin"))
    env["PATH"] = ":".join(extra) + ":" + env.get("PATH", "")
    return env


def _build_and_restart() -> bool:
    """Build frontend and restart uvicorn on whatever branch is checked out."""
    env = _deploy_env()
    build = subprocess.run(
        ["bash", str(REPO_DIR / "scripts" / "build_frontend.sh")],
        capture_output=True, text=True, cwd=str(REPO_DIR), env=env,
    )
    if build.returncode != 0:
        log.error("Frontend build failed: %s", build.stderr[-500:])
        return False
    log.info("Frontend built successfully")

    subprocess.run(["pkill", "-f", "uvicorn app.main:app"],
                   capture_output=True, cwd=str(REPO_DIR))
    time.sleep(2)

    uvicorn_log = REPO_DIR / "logs" / "uvicorn.log"
    uf = open(uvicorn_log, "a")
    subprocess.Popen(
        ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
        cwd=str(REPO_DIR / "backend"),
        stdout=uf, stderr=subprocess.STDOUT,
        env=env,
    )
    log.info("Uvicorn restarted")
    return True


def deploy_branch(branch: str) -> bool:
    """Checkout a feature branch, build frontend, restart uvicorn."""
    result = git("checkout", branch)
    if result.returncode != 0:
        log.error("Failed to checkout %s: %s", branch, result.stderr.strip())
        return False
    return _build_and_restart()


def deploy_main() -> bool:
    """Checkout main, pull latest, build frontend, restart uvicorn."""
    git("checkout", "main")
    git("pull", "--ff-only")
    return _build_and_restart()


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

Do not ask clarifying questions. Make your best judgment and proceed.
If you need to document an assumption, do so in the PR description.

Tech stack: FastAPI + SQLAlchemy/SQLite backend, React 19 + TypeScript + Vite frontend.
Python managed with uv. Frontend uses React Query, Recharts, date-fns.
"""


def is_rate_limited(output: str) -> bool:
    """Check if Claude CLI output suggests a rate limit."""
    lower = output.lower()
    return any(hint in lower for hint in RATE_LIMIT_HINTS)


def enter_waiting_state(issue_number: int, claude_output: str,
                        state: dict, issue_key: str) -> None:
    """Post Claude's question as a comment and park the issue."""
    set_labels(issue_number, add=[LABEL_WAITING], remove=[LABEL_WIP])

    output_tail = claude_output[-2000:] if len(claude_output) > 2000 else claude_output
    body = (
        "Claude needs more information before proceeding. "
        "Reply to this issue with your answer and the poller will resume automatically.\n\n"
        f"**Claude's response:**\n\n{output_tail}"
    )
    comment(issue_number, body)

    state[issue_key]["waiting_since"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    save_state(state)
    log.info("Issue #%d entered waiting state", issue_number)


def process_issue(issue: dict, *, resume_text: str | None = None,
                   resume_context: str = "waiting") -> bool:
    """Process a single GitHub issue. Returns True on success."""
    number = issue["number"]
    title = issue["title"]
    issue_key = str(number)
    log.info("Processing issue #%d: %s (resume=%s, context=%s)",
             number, title, resume_text is not None, resume_context)

    # Load/init conversation state
    state = load_state()
    sid = session_id_for_issue(number)
    if issue_key not in state:
        state[issue_key] = {"session_id": sid, "turn_count": 0}
    issue_state = state[issue_key]
    issue_state["turn_count"] += 1
    save_state(state)

    # Enforce max turns
    if issue_state["turn_count"] > MAX_CONVERSATION_TURNS:
        set_labels(number, add=[LABEL_FAILED], remove=[LABEL_WIP])
        comment(number, f"Gave up after {MAX_CONVERSATION_TURNS} conversation turns without a PR.")
        cleanup_issue_state(issue_key)
        return False

    # Mark as work-in-progress
    set_labels(number, add=[LABEL_WIP], remove=[LABEL_TRIGGER, LABEL_WAITING, LABEL_REVIEW])

    # Clean working tree
    if not reset_to_main():
        set_labels(number, add=[LABEL_FAILED], remove=[LABEL_WIP])
        comment(number, "Poller failed: could not reset to clean main branch.")
        cleanup_issue_state(issue_key)
        return False

    # Build command and prompt
    if issue_state.get("session_started"):
        claude_cmd = [CLAUDE_BIN, "-p", "--dangerously-skip-permissions",
                      "--model", CLAUDE_MODEL, "--resume", sid]
    else:
        claude_cmd = [CLAUDE_BIN, "-p", "--dangerously-skip-permissions",
                      "--model", CLAUDE_MODEL, "--session-id", sid]
        issue_state["session_started"] = True
        save_state(state)

    if resume_text is not None:
        if resume_context == "review":
            prompt = (f"The user tested your changes and has feedback:\n\n{resume_text}\n\n"
                      f"Address this feedback. Commit and push to the existing branch.")
        else:
            prompt = f"User reply:\n\n{resume_text}\n\nContinue implementing the issue."
        comment(number, f"Resuming with your reply (turn {issue_state['turn_count']})...")
    else:
        prompt = build_prompt(issue)
        comment(number, "Poller picked up this issue. Claude is working on it now...")

    # Run Claude CLI
    claude_log = REPO_DIR / "logs" / f"claude-issue-{number}.log"
    log.info("Claude output → %s", claude_log)
    stay_on_branch = False
    try:
        mode = "a" if resume_text else "w"
        clf = open(claude_log, mode)
        if resume_text:
            clf.write(f"\n\n{'='*60}\nRESUMED TURN {issue_state['turn_count']}\n{'='*60}\n\n")
            clf.flush()
        proc = subprocess.Popen(
            claude_cmd,
            stdin=subprocess.PIPE,
            stdout=clf,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(REPO_DIR),
        )
        proc.stdin.write(prompt)
        proc.stdin.close()

        # Poll for completion with stall detection
        # Claude -p writes stdout only at the end; check session JSONL for activity
        session_jsonl = Path.home() / ".claude" / "projects" / "-home-conor-health-app" / f"{sid}.jsonl"
        start = time.monotonic()
        last_activity = start
        last_session_size = session_jsonl.stat().st_size if session_jsonl.exists() else 0
        stalled = False
        while proc.poll() is None:
            elapsed = time.monotonic() - start
            if elapsed > CLAUDE_TIMEOUT:
                log.warning("Claude hit hard timeout on issue #%d", number)
                proc.kill()
                proc.wait()
                stalled = True
                break
            cur_size = session_jsonl.stat().st_size if session_jsonl.exists() else 0
            if cur_size > last_session_size:
                last_activity = time.monotonic()
                last_session_size = cur_size
            idle = time.monotonic() - last_activity
            if idle > STALL_TIMEOUT:
                log.warning("Claude stalled (no session activity for %ds) on issue #%d", int(idle), number)
                proc.kill()
                proc.wait()
                stalled = True
                break
            time.sleep(30)

        clf.close()

        if stalled:
            issue_state["turn_count"] -= 1
            if resume_text is not None:
                set_labels(number, add=[LABEL_WAITING], remove=[LABEL_WIP])
            else:
                set_labels(number, add=[LABEL_TRIGGER], remove=[LABEL_WIP])
            set_retry_cooldown(state, issue_key)
            comment(number,
                    f"Claude stalled (likely rate limited). "
                    f"Will auto-retry in ~{RETRY_COOLDOWN_HOURS} hours.")
            return False

        returncode = proc.returncode

        combined_output = claude_log.read_text(errors="replace")

        # Non-zero exit code
        if returncode != 0:
            if is_rate_limited(combined_output):
                log.warning("Rate limited on issue #%d — will retry after cooldown", number)
                issue_state["turn_count"] -= 1
                if resume_text is not None:
                    set_labels(number, add=[LABEL_WAITING], remove=[LABEL_WIP])
                else:
                    set_labels(number, add=[LABEL_TRIGGER], remove=[LABEL_WIP])
                set_retry_cooldown(state, issue_key)
                return False

            log.error("Claude failed on issue #%d (exit %d)", number, returncode)
            error_snippet = combined_output[-1500:] if len(combined_output) > 1500 else combined_output
            set_labels(number, add=[LABEL_FAILED], remove=[LABEL_WIP])
            comment(number,
                    f"Claude failed (exit code {returncode}).\n\n"
                    f"```\n{error_snippet}\n```")
            cleanup_issue_state(issue_key)
            return False

        # Exit code 0 — check if real work was done
        pr_url = detect_pr_created(number)
        if pr_url is None:
            for line in combined_output.splitlines():
                if "github.com" in line and "/pull/" in line:
                    pr_url = line.strip()
                    break

        if pr_url or detect_commits_on_branch(number):
            branch = f"claude/issue-{number}"
            log.info("Issue #%d: deploying branch %s for review", number, branch)
            deployed = deploy_branch(branch)
            set_labels(number, add=[LABEL_REVIEW], remove=[LABEL_WIP])
            msg = ("Claude has finished implementing this issue.\n\n"
                   "**Changes are live on your phone for testing.**\n"
                   "Reply with feedback to request changes, or comment **lgtm** to merge.")
            if pr_url:
                msg += f"\n\nPR: {pr_url}"
            if not deployed:
                msg += "\n\n⚠️ Auto-deploy failed — changes are on the branch but not yet live."
            comment(number, msg)
            state = load_state()
            if issue_key not in state:
                state[issue_key] = {"session_id": sid, "turn_count": issue_state["turn_count"]}
            state[issue_key]["review_since"] = _now_iso()
            state[issue_key]["pr_url"] = pr_url
            save_state(state)
            stay_on_branch = True
            return True
        else:
            log.info("Issue #%d: no work detected, entering waiting state", number)
            enter_waiting_state(number, combined_output, state, issue_key)
            return False
    finally:
        if not stay_on_branch:
            reset_to_main()


def check_waiting_issues() -> None:
    """Check for user replies on issues in claude-waiting state."""
    waiting = get_issues_with_label(LABEL_WAITING)
    if not waiting:
        return

    state = load_state()

    for issue in waiting:
        number = issue["number"]
        issue_key = str(number)
        issue_state = state.get(issue_key)

        if is_on_cooldown(state, issue_key):
            log.info("Skipping waiting issue #%d — on cooldown", number)
            continue

        if not issue_state or "waiting_since" not in issue_state:
            log.warning("Issue #%d is claude-waiting but has no state — re-queuing", number)
            set_labels(number, add=[LABEL_TRIGGER], remove=[LABEL_WAITING])
            continue

        replies = get_user_replies(number, issue_state["waiting_since"])
        if not replies:
            log.debug("Issue #%d still waiting for user reply", number)
            continue

        reply_body = "\n\n---\n\n".join(replies)
        log.info("Issue #%d got user reply (%d comment(s)), resuming", number, len(replies))

        process_issue(issue, resume_text=reply_body)


def check_review_issues() -> None:
    """Check for user feedback or PR merges on issues in claude-review state."""
    review_issues = get_issues_with_label(LABEL_REVIEW)
    if not review_issues:
        return

    state = load_state()

    for issue in review_issues:
        number = issue["number"]
        issue_key = str(number)
        issue_state = state.get(issue_key, {})

        if is_on_cooldown(state, issue_key):
            log.info("Skipping review issue #%d — on cooldown", number)
            continue

        if detect_pr_merged(number):
            log.info("Issue #%d: PR merged, deploying main", number)
            deploy_main()
            set_labels(number, add=[LABEL_DONE], remove=[LABEL_REVIEW])
            comment(number, "PR merged. Main branch deployed.")
            cleanup_issue_state(issue_key)
            continue

        review_since = issue_state.get("review_since")
        if not review_since:
            log.warning("Issue #%d is claude-review but has no review_since — skipping", number)
            continue

        replies = get_user_replies(number, review_since)
        if not replies:
            log.debug("Issue #%d still awaiting review", number)
            continue

        reply_body = "\n\n---\n\n".join(replies)

        if reply_body.strip().lower() == "lgtm":
            log.info("Issue #%d: user approved, merging PR", number)
            merge_result = gh("pr", "merge",
                              "--repo", REPO,
                              "--head", f"claude/issue-{number}",
                              "--merge")
            if merge_result.returncode != 0:
                pr_url = detect_pr_created(number)
                if pr_url:
                    pr_num = pr_url.rstrip("/").split("/")[-1]
                    merge_result = gh("pr", "merge", pr_num, "--repo", REPO, "--merge")
            deploy_main()
            set_labels(number, add=[LABEL_DONE], remove=[LABEL_REVIEW])
            comment(number, "PR merged and main branch deployed.")
            cleanup_issue_state(issue_key)
            continue

        log.info("Issue #%d got review feedback (%d comment(s)), resuming",
                 number, len(replies))
        process_issue(issue, resume_text=reply_body, resume_context="review")


def recover_stuck_issues() -> None:
    """On startup, recover issues stuck in transient states."""
    stuck = get_issues_with_label(LABEL_WIP)
    for issue in stuck:
        log.info("Recovering stuck WIP issue #%d: %s", issue["number"], issue["title"])
        set_labels(issue["number"], add=[LABEL_TRIGGER], remove=[LABEL_WIP])

    waiting = get_issues_with_label(LABEL_WAITING)
    for issue in waiting:
        log.info("Issue #%d is waiting for user reply", issue["number"])

    reviewing = get_issues_with_label(LABEL_REVIEW)
    for issue in reviewing:
        number = issue["number"]
        log.info("Issue #%d is awaiting user review — ensuring branch is deployed", number)
        branch = f"claude/issue-{number}"
        result = git("branch", "--list", branch)
        if result.stdout.strip():
            deploy_branch(branch)


# ── Main loop ──────────────────────────────────────────────────────────────

def main() -> None:
    log.info("GitHub issue poller started (repo=%s, interval=%ds, model=%s)",
             REPO, POLL_INTERVAL, CLAUDE_MODEL)
    log.info("Repo directory: %s", REPO_DIR)

    recover_stuck_issues()

    while True:
        try:
            issues = get_issues_with_label(LABEL_TRIGGER)
            if issues:
                state = load_state()
                for issue in issues:
                    issue_key = str(issue["number"])
                    if is_on_cooldown(state, issue_key):
                        log.info("Skipping issue #%s — on cooldown until %s",
                                 issue_key, state[issue_key].get("retry_after"))
                        continue
                    process_issue(issue)
            else:
                log.debug("No issues to process")

            check_waiting_issues()
            check_review_issues()

        except Exception:
            log.exception("Unexpected error in poll cycle")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Poller stopped by user")
        sys.exit(0)
