"""Tools the AI agent can call to query the user's health data.

Pure Python + SQLAlchemy, no FastAPI import, so the whole layer is drivable from
tests without a server.

Two rules shape every tool here:

1. **Aggregate first.** A question like "how was my sleep in 2025" must never
   return 365 rows. Ranges are bucketed by day/week/month depending on their
   length, and whole-range `stats` are always present so the model can answer
   without walking the series.
2. **Never silently truncate.** When a request is downgraded or clipped, say so
   in `notices` so the model can tell the user what it actually looked at.
"""

import json
import re
from collections import defaultdict
from datetime import date, timedelta

import httpx
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models
from ..timeutil import iso_now, today_local
from . import analytics, bloodwork, cardio, checkin, context, correlations, muscles, sessions, strength

# ---- budgeting knobs -------------------------------------------------------------

MAX_RAW_ROWS = 120          # ~4 months of daily rows
MAX_BUCKETS = 60            # 5 years of months, or ~14 months of weeks
DAY_MAX_DAYS = 14           # beyond this, bucket by week
WEEK_MAX_DAYS = 90          # beyond this, bucket by month

DAILY_FIELDS = (
    "steps", "resting_hr", "hrv", "stress_avg", "body_battery_high",
    "body_battery_current", "sleep_score", "sleep_duration_min", "weight",
    "weight_trend", "calories_in", "calories_out", "balance",
)


class ToolError(Exception):
    """Raised for bad arguments the model can fix by retrying differently."""


# ---- shared helpers --------------------------------------------------------------


def _parse_date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        raise ToolError(f"{field} must be a YYYY-MM-DD date, got {value!r}")


def _resolve_range(start: str, end: str) -> tuple[date, date]:
    s, e = _parse_date(start, "start"), _parse_date(end, "end")
    if s > e:
        raise ToolError(f"start ({start}) is after end ({end})")
    return s, e


def _choose_granularity(n_days: int, requested: str) -> tuple[str, list[str]]:
    """Escalate rather than error: an over-broad request still returns something
    useful, with a note explaining the downgrade."""
    notices: list[str] = []
    natural = "day" if n_days <= DAY_MAX_DAYS else "week" if n_days <= WEEK_MAX_DAYS else "month"
    if requested in ("auto", None):
        return natural, notices
    order = {"day": 0, "week": 1, "month": 2}
    if order.get(requested, 0) < order[natural]:
        notices.append(
            f"requested granularity '{requested}' over {n_days} days would be too "
            f"large; returned '{natural}' buckets instead"
        )
        return natural, notices
    return requested, notices


def _bucket_key(d: str, granularity: str) -> str:
    if granularity == "day":
        return d
    dt = date.fromisoformat(d)
    if granularity == "month":
        return dt.strftime("%Y-%m")
    iso = dt.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _agg(values: list[float]) -> dict:
    vals = [v for v in values if v is not None]
    if not vals:
        return {"n": 0, "mean": None, "min": None, "max": None}
    return {
        "n": len(vals),
        "mean": round(sum(vals) / len(vals), 1),
        "min": round(min(vals), 1),
        "max": round(max(vals), 1),
    }


def _stats(rows: list[dict], fields: list[str]) -> dict:
    """Whole-range aggregate per field, plus a per-week trend so the model can
    talk about direction without being handed every point."""
    out: dict[str, dict] = {}
    for f in fields:
        series = [(i, r[f]) for i, r in enumerate(rows) if r.get(f) is not None]
        stat = _agg([r.get(f) for r in rows])
        if len(series) >= 3:
            slope = analytics.ols_slope(series)
            stat["trend_per_week"] = round(slope * 7, 2) if slope is not None else None
        else:
            stat["trend_per_week"] = None
        out[f] = stat
    return out


def _bucketize(rows: list[dict], fields: list[str], granularity: str) -> tuple[list[dict], list[str]]:
    notices: list[str] = []
    if granularity == "day":
        series = [{"period": r["date"], **{f: r.get(f) for f in fields}} for r in rows]
    else:
        grouped: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            grouped[_bucket_key(r["date"], granularity)].append(r)
        series = []
        for key in sorted(grouped):
            chunk = grouped[key]
            entry: dict = {"period": key, "n_days_with_data": 0}
            days_with_data = 0
            for f in fields:
                a = _agg([c.get(f) for c in chunk])
                entry[f] = a["mean"]
                entry[f"{f}_min"] = a["min"]
                entry[f"{f}_max"] = a["max"]
                days_with_data = max(days_with_data, a["n"])
            entry["n_days_with_data"] = days_with_data
            series.append(entry)

    if len(series) > MAX_BUCKETS:
        dropped = len(series) - MAX_BUCKETS
        series = series[-MAX_BUCKETS:]
        notices.append(f"dropped {dropped} older buckets to stay within the size cap")
    return series, notices


def _envelope(
    requested: dict,
    trace_summary: str,
    *,
    stats: dict | None = None,
    series: list | None = None,
    raw: list | None = None,
    granularity: str | None = None,
    notices: list[str] | None = None,
    **extra,
) -> dict:
    env = {
        "requested": requested,
        "stats": stats,
        "series": series,
        "raw": raw,
        "granularity": granularity,
        "notices": notices or [],
        "trace_summary": trace_summary,
    }
    env.update(extra)
    return env


# ---- 1. inventory ----------------------------------------------------------------


def get_data_inventory(db: Session) -> dict:
    """What data actually exists, and over what range.

    The agent calls this before assuming a period is answerable - it is the
    difference between "you have no data for March 2024" and a confident answer
    invented from nothing."""

    def span(model, label: str, date_col=None) -> dict:
        col = date_col if date_col is not None else model.date
        first, last, n = db.execute(
            select(func.min(col), func.max(col), func.count())
        ).one()
        return {"domain": label, "first_date": first, "last_date": last, "n_rows": n or 0}

    domains = [
        span(models.DailyMetrics, "daily_metrics"),
        span(models.Sleep, "sleep"),
        span(models.Activity, "activities"),
        span(models.WeightLog, "weight"),
        span(models.FoodLog, "food_log"),
        span(models.ContextLog, "context_logs"),
        span(models.DailyCheckin, "checkins"),
        span(models.BloodPanel, "blood_panels"),
    ]

    sets_n = db.scalar(select(func.count()).select_from(models.WorkoutSet)) or 0
    by_type = db.execute(
        select(models.Activity.type, func.count())
        .group_by(models.Activity.type)
        .order_by(func.count().desc())
    ).all()
    ctx_types = db.execute(
        select(models.ContextLog.type, func.count()).group_by(models.ContextLog.type)
    ).all()

    populated = [d for d in domains if d["n_rows"]]
    overall_first = min((d["first_date"] for d in populated), default=None)
    overall_last = max((d["last_date"] for d in populated), default=None)

    return {
        "today": today_local().isoformat(),
        "domains": domains,
        "workout_sets": sets_n,
        "activity_types": {t: c for t, c in by_type if t},
        "context_types": {t: c for t, c in ctx_types if t},
        "overall_first_date": overall_first,
        "overall_last_date": overall_last,
        "trace_summary": (
            f"Checked what data exists ({overall_first} to {overall_last})"
            if overall_first
            else "Checked what data exists (none found)"
        ),
    }


# ---- 2. daily series -------------------------------------------------------------


def get_daily_series(
    db: Session,
    start: str,
    end: str,
    fields: list[str] | None = None,
    granularity: str = "auto",
) -> dict:
    """Wearable / weight / energy metrics over a range, bucketed to fit."""
    s, e = _resolve_range(start, end)
    fields = list(fields) if fields else ["steps", "resting_hr", "hrv", "sleep_score", "weight"]
    unknown = [f for f in fields if f not in DAILY_FIELDS]
    if unknown:
        raise ToolError(
            f"unknown field(s) {unknown}. Available: {', '.join(DAILY_FIELDS)}"
        )

    n_days = (e - s).days + 1
    gran, notices = _choose_granularity(n_days, granularity)

    dash = analytics.dashboard(db, e.isoformat(), n_days)
    rows = [r for r in dash["series"] if any(r.get(f) is not None for f in fields)]

    stats = _stats(rows, fields)
    series, cap_notices = _bucketize(rows, fields, gran)
    notices += cap_notices

    raw = None
    if gran == "day" and len(rows) <= MAX_RAW_ROWS:
        raw = [{"date": r["date"], **{f: r.get(f) for f in fields}} for r in rows]

    return _envelope(
        {"start": start, "end": end, "fields": fields},
        f"Checked {', '.join(fields)} over {n_days} days ({start} to {end}), "
        f"{len(rows)} days with data",
        stats=stats,
        series=series,
        raw=raw,
        granularity=gran,
        notices=notices,
        days_with_data=len(rows),
        averages_7d=dash["averages_7d"],
    )


# ---- 3. TDEE + readiness ---------------------------------------------------------


def get_tdee_and_readiness(db: Session, end: str | None = None, window: int = 28) -> dict:
    end_s = (_parse_date(end, "end") if end else today_local()).isoformat()
    tdee = analytics.estimate_tdee(db, end_s, window)
    ready = analytics.readiness(db, end_s)
    return _envelope(
        {"end": end_s, "window": window},
        f"Estimated TDEE and readiness as of {end_s}"
        + (f" (TDEE {tdee['tdee']:.0f} kcal)" if tdee.get("tdee") else " (TDEE unavailable)"),
        tdee=tdee,
        readiness=ready,
    )


# ---- 4. body battery drill-down --------------------------------------------------


def get_body_battery_factors(db: Session, day: str) -> dict:
    d = _parse_date(day, "day").isoformat()
    factors = analytics.body_battery_factors(db, d)
    return _envelope(
        {"day": d},
        f"Checked what moved body battery on {d} ({len(factors)} events)",
        factors=factors,
    )


# ---- 5. workouts -----------------------------------------------------------------


def get_workouts(
    db: Session,
    start: str,
    end: str,
    type_: str | None = None,
    include_load: bool = True,
) -> dict:
    s, e = _resolve_range(start, end)
    n_days = (e - s).days + 1

    acts = cardio.list_activities(db, start=s.isoformat(), end=e.isoformat(), type_=type_)
    rows = [
        {
            "id": a.id,
            "date": a.date,
            "type": a.type,
            "name": a.name,
            "duration_min": a.duration_min,
            "distance_km": a.distance_km,
            "avg_hr": a.avg_hr,
            "calories": a.calories,
            "training_load": a.training_load or cardio._fallback_load(a),
        }
        for a in acts
    ]

    notices: list[str] = []
    listed = rows
    if len(rows) > MAX_RAW_ROWS:
        listed = rows[-MAX_RAW_ROWS:]
        notices.append(
            f"{len(rows)} workouts in range; listing the {MAX_RAW_ROWS} most recent. "
            "Weekly totals below cover the whole range."
        )

    weeks = max(1, (n_days // 7) + 1)
    weekly = cardio.weekly_summary(db, weeks=weeks, type_=type_, end=e.isoformat())

    load = None
    if include_load:
        load_full = cardio.training_load_series(db, days=min(n_days, 60), end=e.isoformat())
        load = {
            "sufficient_history_for_acr": load_full["sufficient_history"],
            "history_days": load_full["history_days"],
            "recent": load_full["series"][-14:],
        }

    by_type: dict[str, int] = defaultdict(int)
    for r in rows:
        by_type[r["type"] or "unknown"] += 1

    return _envelope(
        {"start": start, "end": end, "type": type_},
        f"Checked {len(rows)} workouts between {start} and {end}"
        + (f" (type={type_})" if type_ else ""),
        notices=notices,
        total_workouts=len(rows),
        by_type=dict(by_type),
        workouts=listed,
        weekly_summary=weekly,
        training_load=load,
    )


# ---- 6. single workout -----------------------------------------------------------


def get_workout_detail(db: Session, activity_id: int) -> dict:
    act = db.get(models.Activity, activity_id)
    if not act:
        raise ToolError(f"no workout with id {activity_id}")
    summary = sessions.session_summary(db, act)
    return _envelope(
        {"activity_id": activity_id},
        f"Opened workout {activity_id} ({act.name or act.type} on {act.date})",
        detail=summary,
    )


# ---- 7. strength -----------------------------------------------------------------


def _match_exercise(db: Session, name: str) -> models.Exercise | list[str]:
    """Exact match wins; otherwise substring. Ambiguity returns candidates rather
    than a guess - picking the wrong lift silently would be worse than asking."""
    all_ex = list(db.scalars(select(models.Exercise)).all())
    lowered = name.strip().lower()
    exact = [e for e in all_ex if e.name.lower() == lowered]
    if exact:
        return exact[0]
    partial = [e for e in all_ex if lowered in e.name.lower()]
    if len(partial) == 1:
        return partial[0]
    if not partial:
        return []
    return [e.name for e in partial]


def get_strength_progress(
    db: Session,
    exercise_name: str | None = None,
    start: str | None = None,
    end: str | None = None,
    weeks: int = 12,
) -> dict:
    if exercise_name:
        match = _match_exercise(db, exercise_name)
        if isinstance(match, list):
            if not match:
                raise ToolError(
                    f"no exercise matching {exercise_name!r}. Call this tool with no "
                    "exercise_name to see everything that has been logged."
                )
            return _envelope(
                {"exercise_name": exercise_name},
                f"Looked up '{exercise_name}' - {len(match)} possible matches",
                ambiguous=True,
                candidates=match,
                notices=[
                    f"{exercise_name!r} matches several exercises; ask which one is meant."
                ],
            )

        series = strength.exercise_session_series(db, match.id, start_date=start)
        if end:
            series = [s for s in series if s["date"] <= end]
        notices = []
        if len(series) > MAX_RAW_ROWS:
            notices.append(
                f"{len(series)} sessions found; showing the {MAX_RAW_ROWS} most recent"
            )
            series = series[-MAX_RAW_ROWS:]
        prs = strength.personal_records(db, match.id)
        return _envelope(
            {"exercise_name": match.name, "start": start, "end": end},
            f"Checked {match.name}: {len(series)} sessions"
            + (f", best e1RM {prs['best_e1rm']['e1rm']:.1f}kg" if prs.get("best_e1rm") else ""),
            exercise=match.name,
            sessions=series,
            personal_records=prs,
            notices=notices,
        )

    overview = strength.exercise_overview(db)
    volume = strength.weekly_volume(db, weeks=weeks)
    muscle = None
    if start and end:
        muscle = muscles.muscle_set_counts(db, start, end)
    return _envelope(
        {"weeks": weeks, "start": start, "end": end},
        f"Checked strength overview: {len(overview)} exercises, {len(volume)} weeks of volume",
        exercises=overview,
        weekly_volume=volume,
        muscle_set_counts=muscle,
    )


# ---- 8. bloodwork ----------------------------------------------------------------


def get_bloodwork(db: Session, marker: str | None = None) -> dict:
    if marker:
        history = bloodwork.marker_history(db, marker)
        if not history:
            known = sorted({
                r.marker for r in db.scalars(select(models.BloodResult)).all()
            })
            raise ToolError(
                f"no results recorded for marker {marker!r}. "
                + (f"Recorded markers: {', '.join(known)}" if known else "No bloodwork logged at all.")
            )
        ref = bloodwork.MARKER_REFERENCE.get(marker)
        return _envelope(
            {"marker": marker},
            f"Checked {marker}: {len(history)} results "
            f"({history[0]['date']} to {history[-1]['date']})",
            marker=marker,
            reference_range=ref,
            history=history,
        )

    panels = bloodwork.list_panels(db, limit=4)
    flagged = [
        {"date": p["date"], **r}
        for p in panels
        for r in p["results"]
        if r["flag"]
    ]
    return _envelope(
        {},
        f"Checked bloodwork: {len(panels)} recent panels, {len(flagged)} out-of-range results",
        panels=panels,
        out_of_range=flagged,
    )


# ---- 9. context + check-ins ------------------------------------------------------


def get_context_and_checkins(
    db: Session,
    start: str,
    end: str,
    types: list[str] | None = None,
) -> dict:
    s, e = _resolve_range(start, end)
    entries = context.list_entries(db, start=s.isoformat(), end=e.isoformat(), types=types)

    # Aggregate first: "how much have I been drinking this year" must not return
    # every row.
    per_type: dict[str, dict] = defaultdict(lambda: {"days": set(), "total": 0.0, "n": 0})
    for c in entries:
        t = per_type[c.type]
        t["days"].add(c.date)
        t["n"] += 1
        t["total"] += c.value or 0
    summary = {
        k: {
            "n_entries": v["n"],
            "n_days": len(v["days"]),
            "total_value": round(v["total"], 1),
        }
        for k, v in per_type.items()
    }

    notices: list[str] = []
    listed = [
        {"date": c.date, "type": c.type, "value": c.value, "label": c.label, "note": c.note}
        for c in entries
    ]
    if len(listed) > MAX_RAW_ROWS:
        notices.append(
            f"{len(listed)} entries in range; listing the {MAX_RAW_ROWS} most recent. "
            "Totals above cover the whole range."
        )
        listed = listed[-MAX_RAW_ROWS:]

    checkins = list(
        db.scalars(
            select(models.DailyCheckin).where(
                models.DailyCheckin.date >= s.isoformat(),
                models.DailyCheckin.date <= e.isoformat(),
            ).order_by(models.DailyCheckin.date)
        ).all()
    )
    checkin_rows = [
        {
            "date": c.date,
            "mood": c.mood,
            "alcohol_units": c.alcohol_units,
            "caffeine_cups": c.caffeine_cups,
            "illness": bool(c.illness),
            "note": c.note,
        }
        for c in checkins[-MAX_RAW_ROWS:]
    ]

    eating = None
    if checkins:
        first, last, fasting = checkin.derive_eating_window(db, checkins[-1].date)
        eating = {
            "date": checkins[-1].date,
            "first_meal": first,
            "last_meal": last,
            "fasting_hours": fasting,
        }

    return _envelope(
        {"start": start, "end": end, "types": types},
        f"Checked context logs {start} to {end}: "
        + (", ".join(f"{k} x{v['n_entries']}" for k, v in summary.items()) or "nothing logged"),
        notices=notices,
        totals_by_type=summary,
        entries=listed,
        checkins=checkin_rows,
        latest_eating_window=eating,
    )


# ---- 9b. correlations ------------------------------------------------------------


def get_correlation_insights(db: Session, days: int = 90, end: str | None = None) -> dict:
    end_s = (_parse_date(end, "end") if end else today_local()).isoformat()
    result = correlations.compute_insights(db, days=days, end=end_s)
    ok = [i for i in result["insights"] if i["status"] == "ok"]
    return _envelope(
        {"days": days, "end": end_s},
        f"Checked {len(result['insights'])} correlation hypotheses over {days} days "
        f"({len(ok)} had enough data)",
        note=result["note"],
        insights=result["insights"],
    )


# ---- 10. literature --------------------------------------------------------------

EUROPE_PMC_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
LITERATURE_CACHE_DAYS = 30
_USER_AGENT = "health-app/1.0 (personal self-tracking analyst)"

_REVIEW_TYPES = ("review", "meta-analysis", "systematic review")


def _normalize_query(q: str) -> str:
    return re.sub(r"\s+", " ", q.strip().lower())


def search_literature(
    db: Session,
    query: str,
    years_back: int = 5,
    max_results: int = 5,
) -> dict:
    """Search Europe PMC for peer-reviewed evidence.

    Keyless and free; only the query string leaves the machine, never health
    data. Results are cached so repeat questions cost nothing."""
    if not query or len(query.strip()) < 3:
        raise ToolError("query must be at least 3 characters")
    max_results = max(1, min(int(max_results), 10))
    norm = _normalize_query(query)
    cache_key = f"{norm}|{years_back}|{max_results}"

    cached = db.scalar(
        select(models.LiteratureCache).where(models.LiteratureCache.query_norm == cache_key)
    )
    if cached:
        age = date.today() - date.fromisoformat(cached.fetched_at[:10])
        if age.days <= LITERATURE_CACHE_DAYS:
            results = json.loads(cached.results_json)
            return _envelope(
                {"query": query, "years_back": years_back},
                f"Searched the literature for '{query}' ({len(results)} papers, cached)",
                results=results,
                source="Europe PMC (cached)",
            )

    this_year = today_local().year
    full_query = (
        f"({query}) AND (PUB_YEAR:[{this_year - years_back} TO {this_year}])"
        " AND (SRC:MED OR SRC:PMC)"
    )
    try:
        resp = httpx.get(
            EUROPE_PMC_URL,
            params={
                "query": full_query,
                "format": "json",
                "pageSize": max_results * 3,  # over-fetch so reviews can be promoted
                "resultType": "core",
                # Deliberately no `sort`: Europe PMC's default is relevance.
                # Sorting by CITED desc ranks the whole match set by fame, and a
                # broad question matches ~1300 papers - so "creatine strength
                # gains" returned the AHA's heart disease statistics report,
                # which is enormously cited and mentions all three words. Let
                # relevance pick the pool; rank for evidence quality below.
            },
            headers={"User-Agent": _USER_AGENT},
            timeout=20.0,
        )
        resp.raise_for_status()
        payload = resp.json()
    except Exception as exc:  # noqa: BLE001 - must degrade, never break the turn
        return _envelope(
            {"query": query, "years_back": years_back},
            f"Literature search for '{query}' failed - answering from your data alone",
            results=[],
            error=f"{type(exc).__name__}: {exc}",
            notices=["Europe PMC was unreachable; do not cite any studies in this answer."],
        )

    found = []
    for rank, r in enumerate(payload.get("resultList", {}).get("result", [])):
        abstract = (r.get("abstractText") or "").strip()
        pub_type = " ".join(r.get("pubTypeList", {}).get("pubType", []) or []).lower()
        found.append({
            "_rank": rank,
            "pmid": r.get("pmid"),
            "doi": r.get("doi"),
            "title": r.get("title"),
            "journal": r.get("journalTitle"),
            "year": r.get("pubYear"),
            "is_review": any(t in pub_type for t in _REVIEW_TYPES),
            "cited_by": r.get("citedByCount"),
            "abstract_snippet": abstract[:700] + ("..." if len(abstract) > 700 else ""),
        })

    # Reviews and meta-analyses first: better evidence for a general principle
    # than any single trial. Within each group keep Europe PMC's relevance
    # order - citation count as the tiebreak reintroduces the same fame bias
    # that made the `sort` parameter useless, just over a smaller pool.
    found.sort(key=lambda x: (not x["is_review"], x["_rank"]))
    found = [{k: v for k, v in f.items() if k != "_rank"} for f in found[:max_results]]

    row = cached or models.LiteratureCache(query_norm=cache_key)
    row.results_json = json.dumps(found)
    row.fetched_at = iso_now()
    if not cached:
        db.add(row)
    db.commit()

    n_reviews = sum(1 for f in found if f["is_review"])
    return _envelope(
        {"query": query, "years_back": years_back},
        f"Searched the literature for '{query}' - {len(found)} papers "
        f"({n_reviews} reviews/meta-analyses)",
        results=found,
        source="Europe PMC",
    )


# ---- write proposals -------------------------------------------------------------
#
# These are structurally different from every tool above: they do not write to
# weight_log, food_log or context_log at all. They stage a row in
# ai_pending_action and hand back an id. The write happens later, off the agent
# loop, when the user confirms it - so a hallucinated number is something the
# user declines, not something they have to find and delete afterwards.


def _proposal_date(value: str) -> str:
    d = _parse_date(value, "date")
    if d > today_local():
        raise ToolError(f"date {value} is in the future - you cannot log data that hasn't happened")
    return d.isoformat()


def _validated(schema, **payload) -> dict:
    """Enforce the same bounds the UI enforces by running the request through the
    router's own input schema, so the two can't drift apart."""
    from pydantic import ValidationError

    try:
        return schema(**payload).model_dump()
    except ValidationError as exc:
        detail = "; ".join(
            f"{'.'.join(str(x) for x in e['loc'])}: {e['msg']}" for e in exc.errors()
        )
        raise ToolError(detail)


def _stage(db: Session, session_id: int, kind: str, payload: dict, summary: str) -> dict:
    row = models.AIPendingAction(
        session_id=session_id,
        kind=kind,
        payload_json=json.dumps(payload),
        summary_text=summary,
        status="pending",
        created_at=iso_now(),
    )
    db.add(row)
    db.commit()
    return {
        "pending_action_id": row.id,
        "summary_text": summary,
        "status": "pending_user_confirmation",
        "trace_summary": f"Drafted: {summary} (awaiting confirmation)",
        "notices": [
            "Nothing has been saved. Tell the user what you drafted and that they "
            "need to confirm it - do not claim it has been logged."
        ],
    }


def propose_log_weight(
    db: Session, session_id: int, date: str, weight_kg: float, note: str | None = None
) -> dict:
    from .. import schemas

    payload = _validated(
        schemas.WeightIn, date=_proposal_date(date), weight_kg=weight_kg, note=note
    )
    return _stage(
        db, session_id, "log_weight", payload,
        f"Log {payload['weight_kg']:g} kg for {payload['date']}",
    )


def propose_log_food(
    db: Session,
    session_id: int,
    date: str,
    meal: str,
    description: str,
    calories: float,
    quantity_g: float | None = None,
) -> dict:
    from .. import schemas

    payload = _validated(
        schemas.FoodLogIn,
        date=_proposal_date(date),
        meal=meal,
        description=description,
        calories=calories,
        quantity_g=quantity_g,
    )
    grams = f", {payload['quantity_g']:g}g" if payload.get("quantity_g") else ""
    return _stage(
        db, session_id, "log_food", payload,
        f"Log '{payload['description']}' ({payload['calories']:g} kcal{grams}) "
        f"as {payload['meal']} on {payload['date']}",
    )


def propose_log_context(
    db: Session,
    session_id: int,
    date: str,
    type: str,
    value: float | None = None,
    label: str | None = None,
    note: str | None = None,
) -> dict:
    from .. import schemas

    payload = _validated(
        schemas.ContextIn,
        date=_proposal_date(date), type=type, value=value, label=label, note=note,
    )
    detail = " ".join(
        str(x) for x in (payload.get("value"), payload.get("label")) if x is not None
    )
    return _stage(
        db, session_id, "log_context", payload,
        f"Log {payload['type']}{' ' + detail if detail else ''} on {payload['date']}",
    )


# ---- argument schemas ------------------------------------------------------------


class _Inventory(BaseModel):
    pass


class _DailySeries(BaseModel):
    start: str
    end: str
    fields: list[str] | None = None
    granularity: str = "auto"


class _TdeeReadiness(BaseModel):
    end: str | None = None
    window: int = Field(default=28, ge=7, le=120)


class _BodyBattery(BaseModel):
    day: str


class _Workouts(BaseModel):
    start: str
    end: str
    type_: str | None = None
    include_load: bool = True


class _WorkoutDetail(BaseModel):
    activity_id: int


class _Strength(BaseModel):
    exercise_name: str | None = None
    start: str | None = None
    end: str | None = None
    weeks: int = Field(default=12, ge=1, le=104)


class _Bloodwork(BaseModel):
    marker: str | None = None


class _ContextCheckins(BaseModel):
    start: str
    end: str
    types: list[str] | None = None


class _Correlations(BaseModel):
    days: int = Field(default=90, ge=14, le=365)
    end: str | None = None


class _Literature(BaseModel):
    query: str
    years_back: int = Field(default=5, ge=1, le=30)
    max_results: int = Field(default=5, ge=1, le=10)


# Loose types only - the real bounds come from the router's own input schemas at
# call time, so there is exactly one definition of what a valid weight is.
class _ProposeWeight(BaseModel):
    date: str
    weight_kg: float
    note: str | None = None


class _ProposeFood(BaseModel):
    date: str
    meal: str
    description: str
    calories: float
    quantity_g: float | None = None


class _ProposeContext(BaseModel):
    date: str
    type: str
    value: float | None = None
    label: str | None = None
    note: str | None = None


TOOL_REGISTRY = {
    "get_data_inventory": (get_data_inventory, _Inventory),
    "get_daily_series": (get_daily_series, _DailySeries),
    "get_tdee_and_readiness": (get_tdee_and_readiness, _TdeeReadiness),
    "get_body_battery_factors": (get_body_battery_factors, _BodyBattery),
    "get_workouts": (get_workouts, _Workouts),
    "get_workout_detail": (get_workout_detail, _WorkoutDetail),
    "get_strength_progress": (get_strength_progress, _Strength),
    "get_bloodwork": (get_bloodwork, _Bloodwork),
    "get_context_and_checkins": (get_context_and_checkins, _ContextCheckins),
    "get_correlation_insights": (get_correlation_insights, _Correlations),
    "search_literature": (search_literature, _Literature),
    "propose_log_weight": (propose_log_weight, _ProposeWeight),
    "propose_log_food": (propose_log_food, _ProposeFood),
    "propose_log_context": (propose_log_context, _ProposeContext),
}

# Tools that stage a write. dispatch() injects the chat session they belong to,
# and refuses to run them without one - a proposal with no conversation attached
# is a proposal nobody can confirm.
WRITE_TOOLS = frozenset({"propose_log_weight", "propose_log_food", "propose_log_context"})


def _schema(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


_DATE = {"type": "string", "description": "YYYY-MM-DD"}

TOOL_SCHEMAS = [
    _schema(
        "get_data_inventory",
        "What health data exists and over what date range, per domain. Call this "
        "first if you are unsure whether a period is covered - never assume.",
        {}, [],
    ),
    _schema(
        "get_daily_series",
        "Daily wearable, weight and energy metrics over a date range, with "
        "whole-range statistics. Long ranges are automatically bucketed by week "
        "or month.",
        {
            "start": _DATE,
            "end": _DATE,
            "fields": {
                "type": "array",
                "items": {"type": "string", "enum": list(DAILY_FIELDS)},
                "description": "Metrics to return. Defaults to steps, resting_hr, hrv, sleep_score, weight.",
            },
            "granularity": {
                "type": "string",
                "enum": ["auto", "day", "week", "month"],
                "description": "Leave as 'auto' unless you specifically need daily rows over a short window.",
            },
        },
        ["start", "end"],
    ),
    _schema(
        "get_tdee_and_readiness",
        "Back-estimated total daily energy expenditure and the readiness score, "
        "as of a given date.",
        {"end": _DATE, "window": {"type": "integer", "description": "Days of history for the TDEE estimate (default 28)."}},
        [],
    ),
    _schema(
        "get_body_battery_factors",
        "What raised or drained body battery on one specific day.",
        {"day": _DATE}, ["day"],
    ),
    _schema(
        "get_workouts",
        "Workouts in a date range with weekly totals and training load / acute:chronic ratio.",
        {
            "start": _DATE,
            "end": _DATE,
            "type_": {"type": "string", "description": "Filter to one activity type, e.g. 'running'."},
            "include_load": {"type": "boolean"},
        },
        ["start", "end"],
    ),
    _schema(
        "get_workout_detail",
        "Full detail for one workout: sets, tonnage, PRs hit, muscles worked. Use "
        "an id returned by get_workouts.",
        {"activity_id": {"type": "integer"}}, ["activity_id"],
    ),
    _schema(
        "get_strength_progress",
        "Strength training progress. With exercise_name: per-session history and "
        "personal records for that lift. Without: an overview of every exercise "
        "plus weekly volume.",
        {
            "exercise_name": {"type": "string", "description": "e.g. 'bench press'. Omit for an overview."},
            "start": _DATE,
            "end": _DATE,
            "weeks": {"type": "integer", "description": "Weeks of volume history for the overview (default 12)."},
        },
        [],
    ),
    _schema(
        "get_bloodwork",
        "Blood panels. With marker: the full all-time history for that marker with "
        "its reference range. Without: recent panels and everything out of range.",
        {"marker": {"type": "string", "description": "e.g. 'Ferritin', 'HbA1c'. Exact marker name."}},
        [],
    ),
    _schema(
        "get_context_and_checkins",
        "Subjective logs over a range - alcohol, caffeine, mood, illness, "
        "supplements - with per-type totals, plus daily check-ins.",
        {
            "start": _DATE,
            "end": _DATE,
            "types": {
                "type": "array",
                "items": {"type": "string", "enum": list(context.CONTEXT_TYPES)},
            },
        },
        ["start", "end"],
    ),
    _schema(
        "get_correlation_insights",
        "Pre-computed correlation hypotheses over the user's own data (alcohol vs "
        "HRV, load vs recovery, etc). These are n=1 correlations, not causation.",
        {
            "days": {"type": "integer", "description": "Window length, default 90."},
            "end": _DATE,
        },
        [],
    ),
    _schema(
        "search_literature",
        "Search peer-reviewed literature via Europe PMC. Use when the user asks "
        "what the evidence says. Only cite papers this returns - never from memory.",
        {
            "query": {"type": "string", "description": "Search terms, e.g. 'creatine supplementation resistance training'."},
            "years_back": {"type": "integer", "description": "How far back to search, default 5."},
            "max_results": {"type": "integer", "description": "1-10, default 5."},
        },
        ["query"],
    ),
    _schema(
        "propose_log_weight",
        "Draft a manual weight entry for the user to confirm. This does NOT save "
        "anything. Only call it when the user has clearly asked to log a weight.",
        {
            "date": _DATE,
            "weight_kg": {"type": "number", "description": "Weight in kilograms."},
            "note": {"type": "string"},
        },
        ["date", "weight_kg"],
    ),
    _schema(
        "propose_log_food",
        "Draft a food log entry for the user to confirm. This does NOT save "
        "anything. Only call it when the user has clearly asked to log food, and "
        "never invent a calorie figure - ask if you don't know it.",
        {
            "date": _DATE,
            "meal": {"type": "string", "enum": ["breakfast", "lunch", "dinner", "snack"]},
            "description": {"type": "string", "description": "What was eaten."},
            "calories": {"type": "number"},
            "quantity_g": {"type": "number", "description": "Portion in grams, if known."},
        },
        ["date", "meal", "description", "calories"],
    ),
    _schema(
        "propose_log_context",
        "Draft a context log entry (alcohol, caffeine, mood, illness, supplement, "
        "note) for the user to confirm. This does NOT save anything.",
        {
            "date": _DATE,
            "type": {"type": "string", "enum": list(context.CONTEXT_TYPES)},
            "value": {"type": "number", "description": "e.g. units of alcohol, mg of caffeine, mood 1-5."},
            "label": {"type": "string"},
            "note": {"type": "string"},
        },
        ["date", "type"],
    ),
]


def dispatch(
    db: Session, name: str, arguments: dict, session_id: int | None = None
) -> dict:
    """Validate then run a tool. Raises ToolError / ValidationError for the agent
    loop to feed back to the model as a recoverable message."""
    entry = TOOL_REGISTRY.get(name)
    if entry is None:
        raise ToolError(
            f"unknown tool {name!r}. Available: {', '.join(sorted(TOOL_REGISTRY))}"
        )
    fn, schema = entry
    kwargs = schema(**(arguments or {})).model_dump(exclude_none=False)
    if name in WRITE_TOOLS:
        if session_id is None:
            raise ToolError(
                f"{name} needs a saved chat session and there isn't one here"
            )
        kwargs["session_id"] = session_id
    return fn(db, **kwargs)
