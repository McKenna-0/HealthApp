import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.db import Base
from app.services.strength import (
    exercise_history,
    is_new_pr,
    last_session_data,
    personal_records,
    weekly_volume,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _exercise(db, name="Bench Press"):
    ex = models.Exercise(name=name, category="push", equipment="barbell", is_custom=0, created_at="x")
    db.add(ex)
    db.commit()
    return ex


def _workout(db, date, ext=None):
    act = models.Activity(
        external_id=ext or f"app:{date}", date=date, source="app",
        type="strength_training", synced_at="x",
    )
    db.add(act)
    db.commit()
    return act


def _set(db, act, ex, weight, reps, set_number=1, is_warmup=0):
    ws = models.WorkoutSet(
        activity_id=act.id, exercise_id=ex.id, set_number=set_number,
        reps=reps, weight_kg=weight, source="manual", is_warmup=is_warmup,
    )
    db.add(ws)
    db.commit()
    return ws


def test_warmups_excluded_from_history_prs_volume(db):
    ex = _exercise(db)
    act = _workout(db, "2026-07-14")
    _set(db, act, ex, 100.0, 5, is_warmup=1)  # heavy "warm-up" should not count
    _set(db, act, ex, 80.0, 8, set_number=2)

    hist = exercise_history(db, ex.id)
    assert len(hist) == 1
    assert hist[0]["sets"] == 1
    assert hist[0]["best_weight"] == 80.0

    prs = personal_records(db, ex.id)
    assert prs["best_e1rm"]["weight_kg"] == 80.0

    wv = weekly_volume(db)
    assert wv[0]["sets"] == 1


def test_warmup_set_is_never_a_pr(db):
    ex = _exercise(db)
    act = _workout(db, "2026-07-14")
    working = _set(db, act, ex, 80.0, 8)
    assert is_new_pr(db, working, "2026-07-14") is True

    act2 = _workout(db, "2026-07-16")
    warm = _set(db, act2, ex, 120.0, 5, is_warmup=1)
    # a later working set is compared only against working sets
    working2 = _set(db, act2, ex, 85.0, 8, set_number=2)
    assert is_new_pr(db, working2, "2026-07-16") is True
    # warm-up itself shouldn't beat the record for future comparisons
    working3 = _set(db, _workout(db, "2026-07-18"), ex, 90.0, 8)
    assert is_new_pr(db, working3, "2026-07-18") is True
    assert warm  # silence unused


def test_last_session_data_returns_latest_prior_session(db):
    ex = _exercise(db)
    old = _workout(db, "2026-07-01")
    _set(db, old, ex, 70.0, 10)
    recent = _workout(db, "2026-07-10")
    _set(db, recent, ex, 80.0, 8)
    _set(db, recent, ex, 80.0, 7, set_number=2)
    current = _workout(db, "2026-07-14")

    data = last_session_data(db, [ex.id], before_activity_id=current.id)
    assert data[ex.id]["date"] == "2026-07-10"
    assert [s["weight_kg"] for s in data[ex.id]["sets"]] == [80.0, 80.0]
    assert [s["reps"] for s in data[ex.id]["sets"]] == [8, 7]
    assert data[ex.id]["best_e1rm"] == round(80.0 * (1 + 8 / 30), 1)


def test_last_session_data_excludes_current_session_and_warmups(db):
    ex = _exercise(db)
    prior = _workout(db, "2026-07-10")
    _set(db, prior, ex, 60.0, 12, is_warmup=1)
    _set(db, prior, ex, 80.0, 8, set_number=2)
    current = _workout(db, "2026-07-14")
    _set(db, current, ex, 85.0, 8)

    data = last_session_data(db, [ex.id], before_activity_id=current.id)
    assert data[ex.id]["date"] == "2026-07-10"
    assert len(data[ex.id]["sets"]) == 1  # warm-up excluded
    assert data[ex.id]["sets"][0]["set_number"] == 1


def test_last_session_data_empty_cases(db):
    ex = _exercise(db)
    assert last_session_data(db, []) == {}
    assert last_session_data(db, [ex.id]) == {}
