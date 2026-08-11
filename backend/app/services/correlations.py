"""Curated correlation insights over the user's own data.

Not a data-dredging exercise: a fixed list of physiologically plausible
hypotheses, each tested with simple transparent stats and gated on minimum
sample sizes. Every payload carries a correlation-not-causation note.

Lag convention: sleep and HRV rows are keyed to WAKE date, so an evening
exposure on date D pairs with outcomes keyed to D+1. Day-level exposures
(illness) pair at lag 0.
"""

import math
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..timeutil import today_local

MIN_CONTINUOUS_N = 10
MIN_GROUP_N = 4

NOTE = "These are correlations in your own data, not proof of causation."


# ---- stats (plain python) ------------------------------------------------------


def pearson_r(pairs: list[tuple[float, float]]) -> float | None:
    n = len(pairs)
    if n < 2:
        return None
    mx = sum(p[0] for p in pairs) / n
    my = sum(p[1] for p in pairs) / n
    sxx = sum((p[0] - mx) ** 2 for p in pairs)
    syy = sum((p[1] - my) ** 2 for p in pairs)
    if sxx == 0 or syy == 0:
        return None
    sxy = sum((p[0] - mx) * (p[1] - my) for p in pairs)
    return sxy / math.sqrt(sxx * syy)


def cohens_d(group_a: list[float], group_b: list[float]) -> tuple[float | None, float]:
    """(d, mean_diff) for exposed group A vs unexposed B."""
    na, nb = len(group_a), len(group_b)
    ma = sum(group_a) / na
    mb = sum(group_b) / nb
    mean_diff = ma - mb
    if na < 2 or nb < 2:
        return None, mean_diff
    va = sum((x - ma) ** 2 for x in group_a) / (na - 1)
    vb = sum((x - mb) ** 2 for x in group_b) / (nb - 1)
    sp = math.sqrt(((na - 1) * va + (nb - 1) * vb) / (na + nb - 2))
    if sp == 0:
        return None, mean_diff
    return mean_diff / sp, mean_diff


def _strength_continuous(r: float, n: int) -> str:
    a = abs(r)
    if a >= 0.5 and n >= 15:
        return "strong"
    if a >= 0.3 and n >= 15:
        return "moderate"
    if a >= 0.3:
        return "tentative"
    return "none"


def _strength_binary(d: float) -> str:
    a = abs(d)
    if a >= 0.8:
        return "strong"
    if a >= 0.5:
        return "moderate"
    if a >= 0.2:
        return "weak"
    return "none"


# ---- data frame ------------------------------------------------------------------


def _build_frame(db: Session, days: int, end: str | None = None) -> dict[str, dict]:
    end_s = (date.fromisoformat(end) if end else today_local()).isoformat()
    start = (date.fromisoformat(end_s) - timedelta(days=days - 1)).isoformat()

    frame: dict[str, dict] = {}

    def row(d: str) -> dict:
        return frame.setdefault(d, {})

    for m in db.scalars(
        select(models.DailyMetrics).where(
            models.DailyMetrics.date >= start, models.DailyMetrics.date <= end_s
        )
    ):
        r = row(m.date)
        r["hrv"] = m.hrv_last_night_avg
        r["rhr"] = m.resting_hr
        r["steps"] = m.steps

    for s in db.scalars(
        select(models.Sleep).where(models.Sleep.date >= start, models.Sleep.date <= end_s)
    ):
        r = row(s.date)
        r["sleep_score"] = s.sleep_score
        r["sleep_duration"] = s.duration_min

    for a in db.scalars(
        select(models.Activity).where(
            models.Activity.date >= start, models.Activity.date <= end_s
        )
    ):
        r = row(a.date)
        r["load"] = (r.get("load") or 0) + (a.training_load or 0)

    for c in db.scalars(
        select(models.ContextLog).where(
            models.ContextLog.date >= start, models.ContextLog.date <= end_s
        )
    ):
        r = row(c.date)
        if c.type == "alcohol":
            r["alcohol"] = True
            if c.value is not None:
                r["alcohol_units"] = (r.get("alcohol_units") or 0) + c.value
        elif c.type == "caffeine" and c.value is not None:
            r["caffeine_mg"] = (r.get("caffeine_mg") or 0) + c.value
        elif c.type == "illness":
            r["ill"] = True

    return frame


# ---- hypotheses --------------------------------------------------------------------

HYPOTHESES = [
    # (id, title, kind, exposure_key, outcome_key, lag_days, outcome_unit, lower_is_better_for_outcome)
    ("alcohol_hrv", "Alcohol → next-day HRV", "binary", "alcohol", "hrv", 1, "ms"),
    ("alcohol_rhr", "Alcohol → next-day resting HR", "binary", "alcohol", "rhr", 1, "bpm"),
    ("alcohol_sleep", "Alcohol → sleep score", "binary", "alcohol", "sleep_score", 1, "pts"),
    ("caffeine_sleep", "Caffeine dose → sleep score", "continuous", "caffeine_mg", "sleep_score", 1, "pts"),
    ("load_hrv", "Training load → next-day HRV", "continuous", "load", "hrv", 1, "ms"),
    ("load_rhr", "Training load → next-day resting HR", "continuous", "load", "rhr", 1, "bpm"),
    ("steps_sleep", "Daily steps → sleep score", "continuous", "steps", "sleep_score", 1, "pts"),
    ("sleep_steps", "Sleep duration → same-day steps", "continuous", "sleep_duration", "steps", 0, "steps"),
    ("illness_rhr", "Illness → resting HR", "binary", "ill", "rhr", 0, "bpm"),
]


def compute_insights(db: Session, days: int = 90, end: str | None = None) -> dict:
    frame = _build_frame(db, days, end)
    dates = sorted(frame.keys())

    insights = []
    for hid, title, kind, x_key, y_key, lag, unit in HYPOTHESES:
        pairs: list[tuple] = []
        for d in dates:
            out_date = (date.fromisoformat(d) + timedelta(days=lag)).isoformat() if lag else d
            outcome = frame.get(out_date, {}).get(y_key)
            if outcome is None:
                continue
            if kind == "binary":
                exposed = bool(frame.get(d, {}).get(x_key))
                pairs.append((exposed, float(outcome)))
            else:
                x = frame.get(d, {}).get(x_key)
                # for dose exposures (caffeine/load), a day with data but no
                # logged exposure counts as 0
                if x is None and x_key in ("caffeine_mg", "load"):
                    x = 0.0
                if x is None:
                    continue
                pairs.append((float(x), float(outcome)))

        insight = {
            "id": hid,
            "title": title,
            "kind": kind,
            "n": len(pairs),
            "n_exposed": None,
            "effect": None,
            "effect_type": "cohens_d" if kind == "binary" else "pearson_r",
            "mean_diff": None,
            "unit": unit,
            "direction": None,
            "strength": None,
            "summary_line": None,
            "status": "insufficient_data",
            "needed": None,
        }

        if kind == "binary":
            exposed = [y for x, y in pairs if x]
            unexposed = [y for x, y in pairs if not x]
            insight["n_exposed"] = len(exposed)
            if len(exposed) < MIN_GROUP_N or len(unexposed) < MIN_GROUP_N:
                insight["needed"] = max(MIN_GROUP_N - len(exposed), MIN_GROUP_N - len(unexposed), 0)
                insight["summary_line"] = (
                    f"Collecting data: {len(exposed)} exposed / {len(unexposed)} normal days "
                    f"(need {MIN_GROUP_N} of each)."
                )
            else:
                d_val, mean_diff = cohens_d(exposed, unexposed)
                if d_val is None:
                    insight["summary_line"] = "Not enough variation to compare."
                else:
                    direction = "lower" if mean_diff < 0 else "higher" if mean_diff > 0 else "none"
                    insight.update(
                        status="ok",
                        effect=round(d_val, 2),
                        mean_diff=round(mean_diff, 1),
                        direction=direction,
                        strength=_strength_binary(d_val),
                        summary_line=(
                            f"On exposed days, {title.split('→')[1].strip()} averaged "
                            f"{abs(round(mean_diff, 1))} {unit} {direction} "
                            f"(d={round(d_val, 2)}, {len(exposed)} vs {len(unexposed)} days)."
                        ),
                    )
        else:
            if len(pairs) < MIN_CONTINUOUS_N:
                insight["needed"] = MIN_CONTINUOUS_N - len(pairs)
                insight["summary_line"] = (
                    f"Collecting data: {len(pairs)} of {MIN_CONTINUOUS_N} paired days."
                )
            else:
                r = pearson_r(pairs)
                if r is None:
                    insight["summary_line"] = "Not enough variation to correlate."
                else:
                    direction = "lower" if r < 0 else "higher" if r > 0 else "none"
                    insight.update(
                        status="ok",
                        effect=round(r, 2),
                        direction=direction,
                        strength=_strength_continuous(r, len(pairs)),
                        summary_line=(
                            f"Higher {title.split('→')[0].strip().lower()} is associated with "
                            f"{direction} {title.split('→')[1].strip().lower()} "
                            f"(r={round(r, 2)}, n={len(pairs)})."
                        ),
                    )

        insights.append(insight)

    return {
        "days": days,
        "end": (date.fromisoformat(end) if end else today_local()).isoformat(),
        "note": NOTE,
        "insights": insights,
    }
