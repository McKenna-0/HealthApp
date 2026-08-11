"""Measure whether a model is actually good enough to be the health agent, and
what it costs to be.

Deliberately NOT a pytest file: every run spends money and hits the network, so
it has to be something you choose to do, not something CI does behind your back.

The expectations are derived from the database at runtime rather than hardcoded.
Hardcoding "your average is 8,412 steps" would make the harness rot the moment
you sync again; instead each case computes its own ground truth from the same
services the tools use, and checks the answer agrees.

Usage:
    uv run python scripts/eval_agent.py
    uv run python scripts/eval_agent.py --model deepseek/deepseek-v4-pro
    uv run python scripts/eval_agent.py --model X --base-url https://... --json out.json
    uv run python scripts/eval_agent.py --only inventory,literature
"""

import argparse
import json
import re
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

from app import models  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.services import ai_agent, ai_client, ai_tools  # noqa: E402
from app.timeutil import today_local  # noqa: E402

# Questions per day used to turn a per-question cost into something comparable.
ASSUMED_DAILY_QUESTIONS = 10


# ---- ground truth ----------------------------------------------------------------


@dataclass
class Facts:
    """Everything the checks need, computed once from the DB."""

    inventory: dict
    today: str
    first_date: str | None
    last_date: str | None
    latest_weight: float | None
    latest_weight_date: str | None
    mean_steps_30d: float | None
    workouts_last_30d: int
    top_exercise: str | None
    out_of_range_markers: list[str]
    n_blood_panels: int
    n_alcohol_logs: int


def gather_facts(db) -> Facts:
    inv = ai_tools.get_data_inventory(db)
    today = today_local()
    start_30 = (today - timedelta(days=29)).isoformat()

    w = db.scalars(
        select(models.WeightLog).order_by(models.WeightLog.date.desc()).limit(1)
    ).first()

    steps = [
        r.steps
        for r in db.scalars(
            select(models.DailyMetrics).where(models.DailyMetrics.date >= start_30)
        ).all()
        if r.steps is not None
    ]

    workouts = db.scalars(
        select(models.Activity).where(models.Activity.date >= start_30)
    ).all()

    busiest = db.execute(
        select(models.Exercise.name, func.count(models.WorkoutSet.id))
        .join(models.WorkoutSet, models.WorkoutSet.exercise_id == models.Exercise.id)
        .group_by(models.Exercise.name)
        .order_by(func.count(models.WorkoutSet.id).desc())
        .limit(1)
    ).first()
    top = busiest[0] if busiest else None

    try:
        blood = ai_tools.get_bloodwork(db)
        markers = [x["marker"] for x in blood.get("out_of_range", [])]
    except Exception:  # noqa: BLE001
        markers = []

    return Facts(
        inventory=inv,
        today=today.isoformat(),
        first_date=inv["overall_first_date"],
        last_date=inv["overall_last_date"],
        latest_weight=w.weight_kg if w else None,
        latest_weight_date=w.date if w else None,
        mean_steps_30d=(sum(steps) / len(steps)) if steps else None,
        workouts_last_30d=len(workouts),
        top_exercise=top,
        out_of_range_markers=markers,
        n_blood_panels=next(
            (d["n_rows"] for d in inv["domains"] if d["domain"] == "blood_panels"), 0
        ),
        n_alcohol_logs=inv["context_types"].get("alcohol", 0),
    )


# ---- answer inspection -----------------------------------------------------------

_NUMBER = re.compile(r"-?\d[\d,]*\.?\d*")


def numbers_in(text: str) -> list[float]:
    out = []
    for m in _NUMBER.finditer(text):
        try:
            out.append(float(m.group().replace(",", "")))
        except ValueError:
            pass
    return out


def mentions_number(text: str, expected: float | None, tolerance: float = 0.05) -> bool:
    """True if some number in the answer is within tolerance of the expected one.
    Loose on purpose - the model may round, or express steps in thousands."""
    if expected is None:
        return False
    span = abs(expected) * tolerance
    return any(abs(n - expected) <= span for n in numbers_in(text))


def says_no_data(text: str) -> bool:
    """Deliberately narrow. A loose match like a bare "no" would let almost any
    answer through, and this is the check that catches the worst failure mode -
    inventing months of sleep data that never existed."""
    lowered = text.lower()
    return any(
        phrase in lowered
        for phrase in (
            "no data", "no sleep data", "don't have", "do not have",
            "isn't any", "is not any", "nothing recorded", "no records",
            "not available", "can't tell", "cannot tell", "doesn't go back",
            "does not go back", "only goes back", "no coverage", "nothing for",
        )
    )


def hedges(text: str) -> bool:
    lowered = text.lower()
    return any(
        phrase in lowered
        for phrase in (
            "correlation", "not causation", "n=1", "single person", "weak",
            "suggests", "may ", "might ", "directional", "estimate",
        )
    )


# ---- cases -----------------------------------------------------------------------

CheckFn = Callable[[str, Facts], list[str]]


@dataclass
class Case:
    id: str
    question: str
    expect_tools: set[str] = field(default_factory=set)
    # False: every tool in expect_tools must be called. True: at least one must
    # be - for questions where more than one route to the data is legitimate.
    expect_any: bool = False
    forbid_tools: set[str] = field(default_factory=set)
    check: CheckFn = lambda answer, facts: []
    skip_if: Callable[[Facts], bool] = lambda facts: False


NO_WRITES = {"propose_log_weight", "propose_log_food", "propose_log_context"}


def _contains_all(text: str, *needles: str) -> list[str]:
    lowered = text.lower()
    return [f"answer never mentions {n!r}" for n in needles if n.lower() not in lowered]


CASES: list[Case] = [
    Case(
        id="inventory",
        question="What health data do you actually have, and over what date range?",
        # No expect_tools on purpose: `system_messages` already injects the
        # inventory into every turn, so calling get_data_inventory to learn what
        # the model was just told is waste. Whether it calls it is sampling
        # noise - what matters is that the range it reports is the real one,
        # which the check below enforces.
        forbid_tools=NO_WRITES,
        check=lambda a, f: _contains_all(a, (f.first_date or "")[:4], (f.last_date or "")[:4]),
    ),
    Case(
        id="latest_weight",
        question="What is the most recent weight I logged, and when?",
        forbid_tools=NO_WRITES,
        skip_if=lambda f: f.latest_weight is None,
        check=lambda a, f: (
            [] if mentions_number(a, f.latest_weight, 0.02) else ["did not quote the real latest weight"]
        ),
    ),
    Case(
        id="steps_trend",
        question="How have my daily steps trended over the last 30 days? Give me the average.",
        expect_tools={"get_daily_series"},
        forbid_tools=NO_WRITES,
        skip_if=lambda f: f.mean_steps_30d is None,
        check=lambda a, f: (
            [] if mentions_number(a, f.mean_steps_30d, 0.15) else ["average steps not close to the real value"]
        ),
    ),
    Case(
        id="long_range",
        question="How has my weight changed across my entire history?",
        expect_tools={"get_daily_series"},
        forbid_tools=NO_WRITES,
        check=lambda a, f: _contains_all(a, (f.first_date or "")[:4]),
    ),
    Case(
        id="period_with_no_data",
        question="How did I sleep during 2018? Give me the monthly averages.",
        forbid_tools=NO_WRITES,
        check=lambda a, f: [] if says_no_data(a) else ["invented an answer for a period with no data"],
    ),
    Case(
        id="sleep_recent",
        question="What has my sleep been like over the last two weeks?",
        expect_tools={"get_daily_series"},
        forbid_tools=NO_WRITES,
    ),
    Case(
        id="resting_hr_direction",
        question="Is my resting heart rate going up or down? Be specific about the numbers.",
        expect_tools={"get_daily_series"},
        forbid_tools=NO_WRITES,
        check=lambda a, f: [] if numbers_in(a) else ["answered without a single number"],
    ),
    Case(
        id="workout_count",
        question="How many workouts did I do in the last 30 days?",
        expect_tools={"get_workouts"},
        forbid_tools=NO_WRITES,
        skip_if=lambda f: f.workouts_last_30d == 0,
        check=lambda a, f: (
            [] if mentions_number(a, float(f.workouts_last_30d), 0.001)
            else [f"did not report the real count ({f.workouts_last_30d})"]
        ),
    ),
    Case(
        id="strength_progress",
        question="Am I actually getting stronger, or have I stalled?",
        expect_tools={"get_strength_progress"},
        forbid_tools=NO_WRITES,
        skip_if=lambda f: f.top_exercise is None,
    ),
    Case(
        id="ambiguous_exercise",
        question="How is my press going?",
        forbid_tools=NO_WRITES,
        skip_if=lambda f: f.top_exercise is None,
    ),
    Case(
        id="bloodwork",
        question="Are any of my blood markers outside their reference range?",
        expect_tools={"get_bloodwork"},
        forbid_tools=NO_WRITES,
        # With no panels logged the inventory injected at the top of the turn
        # already answers this, and calling the tool to confirm zero rows would
        # be waste, not rigour - so don't score it as a miss.
        skip_if=lambda f: f.n_blood_panels == 0,
    ),
    Case(
        id="correlation_hedging",
        question="Does drinking alcohol affect my HRV the next morning?",
        # Hedging alone is too easy to pass: a model that answers from general
        # knowledge and never opens the data hedges beautifully and tells the
        # user nothing about themselves. It has to look first - but only when
        # there is something to look at. With no alcohol logged, refusing to
        # correlate is the right answer and there is no n=1 claim to hedge.
        expect_tools={"get_correlation_insights", "get_context_and_checkins"},
        expect_any=True,
        skip_if=lambda f: f.n_alcohol_logs == 0,
        forbid_tools=NO_WRITES,
        check=lambda a, f: [] if hedges(a) else ["stated a correlation without hedging it"],
    ),
    Case(
        id="literature_cites_pmid",
        question="What does the published evidence say about creatine and strength gains?",
        expect_tools={"search_literature"},
        forbid_tools=NO_WRITES,
        check=lambda a, f: (
            [] if re.search(r"\b\d{7,8}\b", a) or "pmid" in a.lower()
            else ["cited research without a PMID"]
        ),
    ),
    Case(
        id="literature_vs_my_data",
        question="Research says 7-9 hours of sleep is optimal. How does my own sleep compare?",
        expect_tools={"get_daily_series"},
        forbid_tools=NO_WRITES,
    ),
    Case(
        id="no_unsolicited_write",
        question="What did I weigh yesterday?",
        forbid_tools=NO_WRITES,
    ),
    Case(
        id="write_proposal",
        question="Log my weight as 78.4 kg for today.",
        expect_tools={"propose_log_weight"},
        check=lambda a, f: (
            ["claimed the entry was saved when it is only drafted"]
            if re.search(r"\b(logged|saved|recorded|added) (it|your|the)\b", a.lower())
            else []
        ),
    ),
]


# ---- runner ----------------------------------------------------------------------


@dataclass
class Result:
    case_id: str
    ok: bool
    reasons: list[str]
    tools: list[str]
    latency_s: float
    prompt_tokens: int
    completion_tokens: int
    answer: str
    skipped: bool = False
    estimated_tokens: bool = False


class UsageRecorder:
    """Wraps chat_stream to capture real token usage and wall time per model call.

    Estimated tokens would be good enough to compare models against each other,
    but not to predict a bill, so ask the provider for the real numbers and only
    fall back to an estimate if it doesn't supply them."""

    def __init__(self, inner, is_openrouter: bool):
        self.inner = inner
        self.is_openrouter = is_openrouter
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.calls = 0
        self.estimated = False

    def __call__(self, messages, provider, tools=None, extra_body=None, **kw):
        self.calls += 1
        body = dict(extra_body or {})
        if self.is_openrouter:
            body["usage"] = {"include": True}

        got_usage = False
        for chunk in self.inner(messages, provider, tools=tools, extra_body=body, **kw):
            usage = chunk.get("usage")
            if usage:
                got_usage = True
                self.prompt_tokens += usage.get("prompt_tokens", 0)
                self.completion_tokens += usage.get("completion_tokens", 0)
            yield chunk

        if not got_usage:
            self.estimated = True
            self.prompt_tokens += len(json.dumps(messages)) // 4
            if tools:
                self.prompt_tokens += len(json.dumps(tools)) // 4


def run_case(db, case: Case, facts: Facts, provider) -> Result:
    if case.skip_if(facts):
        return Result(case.id, True, ["skipped - no data for this case"], [], 0, 0, 0, "", skipped=True)

    session = _new_session(db, provider)
    recorder = UsageRecorder(ai_client.chat_stream, provider.is_openrouter)
    original = ai_agent.ai_client.chat_stream
    ai_agent.ai_client.chat_stream = recorder

    tools_called: list[str] = []
    answer = ""
    started = time.monotonic()
    try:
        messages = ai_agent.system_messages(db, session.id) + [
            {"role": "user", "content": case.question}
        ]
        for event in ai_agent.run_agent_turn(db, messages, provider, session_id=session.id):
            if event.type == "tool_call":
                tools_called.append(event.data["name"])
            elif event.type == "message_done":
                answer = event.data.get("content") or ""
            elif event.type == "error":
                return Result(
                    case.id, False, [f"stream error: {event.data.get('message')}"],
                    tools_called, time.monotonic() - started, 0, 0, "",
                )
    finally:
        ai_agent.ai_client.chat_stream = original
        _cleanup(db, session.id)

    latency = time.monotonic() - started
    called = set(tools_called)
    reasons: list[str] = []
    if case.expect_any:
        if case.expect_tools and not (case.expect_tools & called):
            reasons.append("called none of " + ", ".join(sorted(case.expect_tools)))
    else:
        for name in sorted(case.expect_tools - called):
            reasons.append(f"never called {name}")
    for name in sorted(case.forbid_tools & called):
        reasons.append(f"called {name} when it should not have")
    if not answer.strip():
        reasons.append("produced no answer")
    else:
        reasons.extend(case.check(answer, facts))

    return Result(
        case.id, not reasons, reasons, tools_called, latency,
        recorder.prompt_tokens, recorder.completion_tokens, answer,
        estimated_tokens=recorder.estimated,
    )


def _new_session(db, provider):
    from app.services import ai_chat

    return ai_chat.create_session(db, provider)


def _cleanup(db, session_id: int) -> None:
    """Evaluation runs must not leave drafts or transcripts in the real DB - and
    must never leave a pending action that could later be confirmed by accident."""
    from app.services import ai_chat

    ai_chat.delete_session(db, session_id)


# ---- pricing ---------------------------------------------------------------------


def lookup_pricing(model: str) -> tuple[float | None, float | None]:
    """Per-million-token prices from OpenRouter's catalogue, if it knows the model."""
    try:
        resp = httpx.get("https://openrouter.ai/api/v1/models", timeout=20)
        resp.raise_for_status()
        for m in resp.json().get("data", []):
            if m.get("id") == model:
                p = m.get("pricing") or {}
                return float(p.get("prompt", 0)) * 1e6, float(p.get("completion", 0)) * 1e6
    except Exception:  # noqa: BLE001
        pass
    return None, None


# ---- reporting -------------------------------------------------------------------


def report(results: list[Result], model: str, price_in, price_out) -> dict:
    scored = [r for r in results if not r.skipped]
    passed = [r for r in scored if r.ok]

    print(f"\n{'=' * 72}\n  {model}\n{'=' * 72}")
    for r in results:
        mark = "SKIP" if r.skipped else ("PASS" if r.ok else "FAIL")
        print(f"  [{mark}] {r.case_id:24} {r.latency_s:5.1f}s  "
              f"{r.prompt_tokens:>6} in / {r.completion_tokens:>5} out  "
              f"[{', '.join(r.tools) or 'no tools'}]")
        for reason in r.reasons if not r.ok else []:
            print(f"         - {reason}")

    n = len(scored) or 1
    avg_in = sum(r.prompt_tokens for r in scored) / n
    avg_out = sum(r.completion_tokens for r in scored) / n
    avg_latency = sum(r.latency_s for r in scored) / n

    summary = {
        "model": model,
        "passed": len(passed),
        "scored": len(scored),
        "skipped": len(results) - len(scored),
        "pass_rate": len(passed) / n,
        "avg_prompt_tokens": round(avg_in),
        "avg_completion_tokens": round(avg_out),
        "avg_latency_s": round(avg_latency, 1),
    }

    print(f"\n  {len(passed)}/{len(scored)} passed ({summary['pass_rate']:.0%})"
          f"   avg {avg_in:,.0f} in / {avg_out:,.0f} out   {avg_latency:.1f}s per question")

    if any(r.estimated_tokens for r in scored):
        summary["tokens_partly_estimated"] = True
        print("  NOTE: this endpoint did not report usage for every call, so some "
              "token counts are estimated (~4 chars/token). Costs below are indicative.")

    if price_in is not None and price_out is not None:
        per_q = (avg_in * price_in + avg_out * price_out) / 1e6
        monthly = per_q * ASSUMED_DAILY_QUESTIONS * 30
        summary |= {
            "price_in_per_m": price_in,
            "price_out_per_m": price_out,
            "cost_per_question": round(per_q, 6),
            "cost_per_month": round(monthly, 2),
        }
        print(f"  ${per_q:.5f} per question  ->  ${monthly:.2f}/month at "
              f"{ASSUMED_DAILY_QUESTIONS} questions/day (before provider fees)")
        if summary["pass_rate"]:
            print(f"  ${monthly / summary['pass_rate']:.2f}/month per unit of pass rate "
                  "- the number to compare models on")
    else:
        print("  (no pricing found for this model - pass --price-in / --price-out)")

    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", help="Model id. Defaults to the configured agent model.")
    ap.add_argument("--base-url", help="Override the endpoint.")
    ap.add_argument("--api-key", help="Override the key.")
    ap.add_argument("--only", help="Comma-separated case ids to run.")
    ap.add_argument("--price-in", type=float, help="$ per million input tokens.")
    ap.add_argument("--price-out", type=float, help="$ per million output tokens.")
    ap.add_argument("--json", help="Write the summary to this file.")
    args = ap.parse_args()

    init_db()
    with SessionLocal() as db:
        base = ai_client.resolve_agent_provider(db)
        provider = ai_client.Provider(
            base_url=args.base_url or base.base_url,
            api_key=args.api_key or base.api_key,
            model=args.model or base.model,
        )
        if not provider.configured:
            print("Agent provider is not configured - set AI_AGENT_API_KEY or pass --api-key")
            return 2

        facts = gather_facts(db)
        if not facts.first_date:
            print("The database is empty - seed it first: uv run python scripts/seed_mock.py")
            return 2

        print(f"Data spans {facts.first_date} to {facts.last_date}. "
              f"Endpoint: {provider.base_url}")

        wanted = set(args.only.split(",")) if args.only else None
        cases = [c for c in CASES if not wanted or c.id in wanted]
        if not cases:
            print(f"No cases matched --only. Available: {', '.join(c.id for c in CASES)}")
            return 2

        results = [run_case(db, c, facts, provider) for c in cases]

    price_in, price_out = args.price_in, args.price_out
    if price_in is None or price_out is None:
        looked_up = lookup_pricing(provider.model)
        price_in = price_in if price_in is not None else looked_up[0]
        price_out = price_out if price_out is not None else looked_up[1]

    summary = report(results, provider.model, price_in, price_out)

    if args.json:
        Path(args.json).write_text(
            json.dumps(
                {
                    "summary": summary,
                    "cases": [
                        {
                            "id": r.case_id, "ok": r.ok, "skipped": r.skipped,
                            "reasons": r.reasons, "tools": r.tools,
                            "latency_s": round(r.latency_s, 2),
                            "prompt_tokens": r.prompt_tokens,
                            "completion_tokens": r.completion_tokens,
                            "answer": r.answer,
                        }
                        for r in results
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\n  Wrote {args.json}")

    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
