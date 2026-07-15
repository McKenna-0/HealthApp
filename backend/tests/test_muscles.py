import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.db import Base
from app.services.muscles import (
    EXERCISE_MUSCLES,
    MUSCLE_GROUPS,
    backfill_exercise_muscles,
    muscle_intensity,
    muscle_set_counts,
)
from app.services.strength import SEED_EXERCISES, seed_exercises


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def test_all_seed_exercises_have_muscle_mapping():
    seed_names = {name for name, _, _ in SEED_EXERCISES}
    assert seed_names == set(EXERCISE_MUSCLES.keys())


def test_all_mapped_muscles_are_valid():
    valid = set(MUSCLE_GROUPS)
    for name, (primary, secondary) in EXERCISE_MUSCLES.items():
        assert set(primary) <= valid, name
        assert set(secondary) <= valid, name
        assert not (set(primary) & set(secondary)), name
        assert primary, f"{name} has no primary muscles"


def test_backfill_sets_muscles_and_is_idempotent(db):
    seed_exercises(db)
    first = backfill_exercise_muscles(db)
    assert first == len(SEED_EXERCISES)
    assert backfill_exercise_muscles(db) == 0  # idempotent

    bench = db.query(models.Exercise).filter_by(name="Bench Press").one()
    assert json.loads(bench.primary_muscles) == ["chest"]
    assert json.loads(bench.secondary_muscles) == ["front_delts", "triceps"]


def _make_workout(db, date="2026-07-14"):
    act = models.Activity(
        external_id=f"app:test-{date}", date=date, source="app",
        type="strength_training", synced_at="x",
    )
    db.add(act)
    db.commit()
    return act


def _add_set(db, act, exercise_id, is_warmup=0, reps=8, weight=60.0):
    ws = models.WorkoutSet(
        activity_id=act.id, exercise_id=exercise_id, set_number=1,
        reps=reps, weight_kg=weight, source="manual", is_warmup=is_warmup,
    )
    db.add(ws)
    db.commit()
    return ws


def test_muscle_intensity_primary_and_secondary(db):
    seed_exercises(db)
    backfill_exercise_muscles(db)
    bench = db.query(models.Exercise).filter_by(name="Bench Press").one()
    act = _make_workout(db)
    _add_set(db, act, bench.id)
    _add_set(db, act, bench.id)

    result = muscle_intensity(db, activity_ids=[act.id])
    assert result["chest"] == 1.0  # 2 sets x 1.0, normalized peak
    assert result["triceps"] == 0.5  # 2 sets x 0.5 / 2.0
    assert "quads" not in result


def test_muscle_intensity_excludes_warmups(db):
    seed_exercises(db)
    backfill_exercise_muscles(db)
    bench = db.query(models.Exercise).filter_by(name="Bench Press").one()
    squat = db.query(models.Exercise).filter_by(name="Barbell Back Squat").one()
    act = _make_workout(db)
    _add_set(db, act, bench.id)
    _add_set(db, act, squat.id, is_warmup=1)  # warm-up only: should not appear

    result = muscle_intensity(db, activity_ids=[act.id])
    assert "chest" in result
    assert "quads" not in result


def test_muscle_set_counts_date_range(db):
    seed_exercises(db)
    backfill_exercise_muscles(db)
    bench = db.query(models.Exercise).filter_by(name="Bench Press").one()
    inside = _make_workout(db, "2026-07-14")
    outside = _make_workout(db, "2026-06-01")
    _add_set(db, inside, bench.id)
    _add_set(db, outside, bench.id)

    result = muscle_set_counts(db, "2026-07-10", "2026-07-16")
    assert result["chest"]["sets"] == 1
    assert result["chest"]["intensity"] == 1.0


def test_muscle_intensity_empty(db):
    seed_exercises(db)
    backfill_exercise_muscles(db)
    assert muscle_intensity(db, activity_ids=[999]) == {}
