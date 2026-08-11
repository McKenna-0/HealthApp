"""The agent's tool layer.

The bar these tests defend: a tool must never blow the context window on a long
range, never silently truncate, and never guess when the request is ambiguous."""

import json
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.db import Base
from app.services import ai_tools
from app.services.ai_tools import ToolError
from app.timeutil import today_local


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _seed_days(db, n: int, end: date | None = None):
    end = end or today_local()
    for i in range(n):
        d = end - timedelta(days=i)
        db.add(
            models.DailyMetrics(
                date=d.isoformat(),
                steps=8000 + i,
                resting_hr=55,
                hrv_last_night_avg=60.0,
                source="mock",
                synced_at="x",
            )
        )
        db.add(
            models.Sleep(
                date=d.isoformat(),
                sleep_score=80,
                duration_min=440,
                source="mock",
                synced_at="x",
            )
        )
    db.commit()


# ---- inventory -------------------------------------------------------------------


def test_inventory_reports_real_bounds(db):
    end = today_local()
    _seed_days(db, 30, end)

    inv = ai_tools.get_data_inventory(db)
    by_domain = {d["domain"]: d for d in inv["domains"]}

    assert by_domain["daily_metrics"]["n_rows"] == 30
    assert by_domain["daily_metrics"]["last_date"] == end.isoformat()
    assert by_domain["daily_metrics"]["first_date"] == (end - timedelta(days=29)).isoformat()
    # domains with nothing in them report zero rather than vanishing
    assert by_domain["blood_panels"]["n_rows"] == 0
    assert by_domain["blood_panels"]["first_date"] is None
    assert inv["overall_last_date"] == end.isoformat()


def test_inventory_on_empty_db(db):
    inv = ai_tools.get_data_inventory(db)
    assert inv["overall_first_date"] is None
    assert all(d["n_rows"] == 0 for d in inv["domains"])
    assert "none found" in inv["trace_summary"]


# ---- granularity escalation ------------------------------------------------------


def test_short_range_returns_daily_rows(db):
    end = today_local()
    _seed_days(db, 20, end)

    r = ai_tools.get_daily_series(
        db, (end - timedelta(days=9)).isoformat(), end.isoformat(), ["steps"]
    )
    assert r["granularity"] == "day"
    assert r["raw"] is not None
    assert len(r["raw"]) == 10


def test_medium_range_buckets_by_week_and_drops_raw(db):
    end = today_local()
    _seed_days(db, 100, end)

    r = ai_tools.get_daily_series(
        db, (end - timedelta(days=59)).isoformat(), end.isoformat(), ["steps"]
    )
    assert r["granularity"] == "week"
    assert r["raw"] is None
    assert all("period" in b for b in r["series"])


def test_long_range_buckets_by_month(db):
    end = today_local()
    _seed_days(db, 200, end)

    r = ai_tools.get_daily_series(
        db, (end - timedelta(days=179)).isoformat(), end.isoformat(), ["steps"]
    )
    assert r["granularity"] == "month"
    assert r["raw"] is None


@pytest.mark.parametrize(
    "n_days,expected", [(14, "day"), (15, "week"), (90, "week"), (91, "month")]
)
def test_granularity_boundaries(n_days, expected):
    gran, _ = ai_tools._choose_granularity(n_days, "auto")
    assert gran == expected


def test_explicit_day_over_long_range_escalates_with_notice(db):
    end = today_local()
    _seed_days(db, 200, end)

    r = ai_tools.get_daily_series(
        db,
        (end - timedelta(days=179)).isoformat(),
        end.isoformat(),
        ["steps"],
        granularity="day",
    )
    # escalated rather than erroring, and it says so
    assert r["granularity"] == "month"
    assert any("too large" in n for n in r["notices"])


def test_bucket_cap_keeps_most_recent_and_says_what_it_dropped():
    # only reachable with many years of history (monthly buckets), so drive the
    # bucketing directly rather than seeding a decade
    start = date(2016, 1, 1)
    rows = [
        {"date": (start + timedelta(days=i)).isoformat(), "steps": 8000 + i}
        for i in range(0, 80 * 31, 31)  # ~80 distinct months
    ]
    series, notices = ai_tools._bucketize(rows, ["steps"], "month")

    assert len(series) == ai_tools.MAX_BUCKETS
    assert any("dropped" in n for n in notices)
    # the recent end is what survives, not the ancient end
    assert series[-1]["period"] > series[0]["period"]
    assert series[-1]["period"] == ai_tools._bucket_key(rows[-1]["date"], "month")


def test_stats_always_present_even_when_bucketed(db):
    end = today_local()
    _seed_days(db, 120, end)

    r = ai_tools.get_daily_series(
        db, (end - timedelta(days=99)).isoformat(), end.isoformat(), ["steps"]
    )
    assert r["stats"]["steps"]["n"] > 0
    assert r["stats"]["steps"]["mean"] is not None
    assert "trend_per_week" in r["stats"]["steps"]


# ---- argument errors are recoverable ---------------------------------------------


def test_unknown_field_lists_valid_ones(db):
    with pytest.raises(ToolError) as exc:
        ai_tools.get_daily_series(db, "2026-01-01", "2026-01-10", ["vo2max"])
    assert "vo2max" in str(exc.value)
    assert "steps" in str(exc.value)  # tells the model what it can use


def test_backwards_range_rejected(db):
    with pytest.raises(ToolError, match="after end"):
        ai_tools.get_daily_series(db, "2026-05-01", "2026-01-01")


def test_malformed_date_rejected(db):
    with pytest.raises(ToolError, match="YYYY-MM-DD"):
        ai_tools.get_daily_series(db, "last tuesday", "2026-01-01")


# ---- ambiguity is surfaced, not guessed ------------------------------------------


def _add_exercise(db, name, category="push"):
    ex = models.Exercise(name=name, category=category, created_at="x")
    db.add(ex)
    db.commit()
    return ex


def test_ambiguous_exercise_returns_candidates(db):
    _add_exercise(db, "Barbell Bench Press")
    _add_exercise(db, "Incline Bench Press")

    r = ai_tools.get_strength_progress(db, exercise_name="bench")
    assert r["ambiguous"] is True
    assert set(r["candidates"]) == {"Barbell Bench Press", "Incline Bench Press"}


def test_exact_name_wins_over_substring(db):
    _add_exercise(db, "Bench Press")
    _add_exercise(db, "Incline Bench Press")

    r = ai_tools.get_strength_progress(db, exercise_name="Bench Press")
    assert r.get("ambiguous") is None
    assert r["exercise"] == "Bench Press"


def test_unknown_exercise_raises_with_guidance(db):
    _add_exercise(db, "Squat")
    with pytest.raises(ToolError, match="no exercise matching"):
        ai_tools.get_strength_progress(db, exercise_name="kettlebell swing")


def test_unknown_marker_lists_recorded_ones(db):
    panel = models.BloodPanel(date="2026-01-01", created_at="x")
    db.add(panel)
    db.flush()
    db.add(models.BloodResult(panel_id=panel.id, marker="Ferritin", value=90.0, unit="µg/L"))
    db.commit()

    with pytest.raises(ToolError) as exc:
        ai_tools.get_bloodwork(db, marker="HbA1c")
    assert "Ferritin" in str(exc.value)


def test_bloodwork_flags_out_of_range(db):
    panel = models.BloodPanel(date="2026-01-01", created_at="x")
    db.add(panel)
    db.flush()
    db.add(
        models.BloodResult(
            panel_id=panel.id, marker="Ferritin", value=5.0, unit="µg/L",
            ref_low=30.0, ref_high=400.0,
        )
    )
    db.commit()

    r = ai_tools.get_bloodwork(db)
    assert len(r["out_of_range"]) == 1
    assert r["out_of_range"][0]["flag"] == "low"


# ---- context aggregation ---------------------------------------------------------


def test_context_totals_cover_full_range_even_when_rows_clipped(db):
    end = today_local()
    n = ai_tools.MAX_RAW_ROWS + 40
    for i in range(n):
        d = end - timedelta(days=i)
        db.add(
            models.ContextLog(date=d.isoformat(), ts="x", type="alcohol", value=2.0)
        )
    db.commit()

    r = ai_tools.get_context_and_checkins(
        db, (end - timedelta(days=n - 1)).isoformat(), end.isoformat()
    )
    # rows clipped...
    assert len(r["entries"]) == ai_tools.MAX_RAW_ROWS
    assert any("listing the" in x for x in r["notices"])
    # ...but the totals still describe every row
    assert r["totals_by_type"]["alcohol"]["n_entries"] == n
    assert r["totals_by_type"]["alcohol"]["total_value"] == pytest.approx(2.0 * n)


# ---- literature ------------------------------------------------------------------


_FAKE_PMC = {
    "resultList": {
        "result": [
            {
                "pmid": "111", "doi": "10.1/a", "title": "A single trial",
                "journalTitle": "J Test", "pubYear": "2024",
                "abstractText": "Some findings.", "citedByCount": 50,
                "pubTypeList": {"pubType": ["Journal Article"]},
            },
            {
                "pmid": "222", "doi": "10.1/b", "title": "A meta-analysis",
                "journalTitle": "J Meta", "pubYear": "2023",
                "abstractText": "Pooled findings.", "citedByCount": 10,
                "pubTypeList": {"pubType": ["Meta-Analysis"]},
            },
        ]
    }
}


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_literature_promotes_reviews_over_citations(db, monkeypatch):
    monkeypatch.setattr(ai_tools.httpx, "get", lambda *a, **k: _FakeResp(_FAKE_PMC))

    r = ai_tools.search_literature(db, "creatine resistance training")
    # the meta-analysis outranks the more-cited single trial
    assert r["results"][0]["pmid"] == "222"
    assert r["results"][0]["is_review"] is True


def test_literature_does_not_ask_the_api_to_sort(db, monkeypatch):
    """Europe PMC's default order is relevance. Asking it for `CITED desc`
    ranks the entire match set by fame instead, and a broad question matches
    over a thousand papers - which is how 'creatine strength gains' came back
    with a national heart-disease statistics report as the top hit."""
    seen = {}

    def _capture(*a, **k):
        seen.update(k.get("params") or {})
        return _FakeResp(_FAKE_PMC)

    monkeypatch.setattr(ai_tools.httpx, "get", _capture)
    ai_tools.search_literature(db, "creatine strength gains")

    assert "sort" not in seen


def test_literature_keeps_relevance_order_within_reviews(db, monkeypatch):
    """Two reviews: the API ranked the topical one first, the other is more
    cited. Falling back to citations here is the same fame bias in miniature."""
    payload = {"resultList": {"result": [
        {
            "pmid": "333", "doi": "10.1/c", "title": "Creatine and strength: a meta-analysis",
            "journalTitle": "J Sport", "pubYear": "2024",
            "abstractText": "On topic.", "citedByCount": 12,
            "pubTypeList": {"pubType": ["Meta-Analysis"]},
        },
        {
            "pmid": "444", "doi": "10.1/d", "title": "Everything about everything",
            "journalTitle": "J Big", "pubYear": "2025",
            "abstractText": "Mentions creatine once.", "citedByCount": 900,
            "pubTypeList": {"pubType": ["Review"]},
        },
    ]}}
    monkeypatch.setattr(ai_tools.httpx, "get", lambda *a, **k: _FakeResp(payload))

    r = ai_tools.search_literature(db, "creatine strength gains")

    assert [x["pmid"] for x in r["results"]] == ["333", "444"]
    # the internal ordering key must not leak to the model
    assert "_rank" not in r["results"][0]


def test_literature_caches_and_avoids_second_call(db, monkeypatch):
    calls = {"n": 0}

    def _once(*a, **k):
        calls["n"] += 1
        return _FakeResp(_FAKE_PMC)

    monkeypatch.setattr(ai_tools.httpx, "get", _once)

    ai_tools.search_literature(db, "vitamin D and sleep")
    second = ai_tools.search_literature(db, "  Vitamin D AND Sleep  ")  # normalised

    assert calls["n"] == 1
    assert "cached" in second["source"]


def test_literature_failure_degrades_instead_of_raising(db, monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(ai_tools.httpx, "get", _boom)

    r = ai_tools.search_literature(db, "magnesium and hrv")
    assert r["results"] == []
    assert "error" in r
    # explicitly tells the model not to cite anything
    assert any("do not cite" in n.lower() for n in r["notices"])


# ---- dispatch --------------------------------------------------------------------


def test_dispatch_validates_and_runs(db):
    _seed_days(db, 10)
    end = today_local()
    out = ai_tools.dispatch(
        db,
        "get_daily_series",
        {"start": (end - timedelta(days=5)).isoformat(), "end": end.isoformat()},
    )
    assert out["trace_summary"]


def test_dispatch_unknown_tool_lists_available(db):
    with pytest.raises(ToolError) as exc:
        ai_tools.dispatch(db, "get_horoscope", {})
    assert "get_daily_series" in str(exc.value)


def test_every_schema_has_a_registry_entry():
    names = {t["function"]["name"] for t in ai_tools.TOOL_SCHEMAS}
    assert names == set(ai_tools.TOOL_REGISTRY)


def test_schemas_stay_small_enough_to_resend_every_turn():
    # they ride along on every model call, so a bloated set is a per-turn tax
    assert len(json.dumps(ai_tools.TOOL_SCHEMAS)) < 12000
