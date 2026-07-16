import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.db import Base, get_db
from app.main import app
from app.services import strength
from app.services.repcount_import import import_csv


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()


@pytest.fixture
def client(db):
    def override():
        yield db

    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


def _row(**kw):
    base = {
        "Workout Start": "2026-07-15 16:55",
        "Workout End": "2026-07-15 17:48",
        "Exercise": "Pull Up",
        "Weight": "17.5",
        "Reps": "10",
        "Notes": "",
        "Kcal": "",
        "Distance": "",
        "Duration": "",
        "Category": "Back",
        "Name": "Pull options ",
        "Bodyweight": "",
    }
    base.update(kw)
    return base


def test_import_groups_and_totals(db):
    rows = [
        _row(),
        _row(Reps="8", Notes="+1r"),
        _row(Exercise="Db rows", Weight="32", Reps="13", Category="Back"),
        _row(**{"Workout Start": "2026-07-13 08:54", "Workout End": "2026-07-13 09:48",
                "Exercise": "RDL", "Weight": "130", "Reps": "10", "Category": "Legs",
                "Name": "Legs 2"}),
    ]
    stats = import_csv(db, rows)
    assert stats.workouts_created == 2
    assert stats.sets_created == 4

    acts = db.scalars(select(models.Activity).order_by(models.Activity.date)).all()
    assert [a.external_id for a in acts] == [
        "repcount:2026-07-13T08:54",
        "repcount:2026-07-15T16:55",
    ]
    a15 = acts[1]
    assert a15.source == "repcount"
    assert a15.status == "finished"
    assert a15.date == "2026-07-15"
    assert a15.name == "Pull options"
    assert a15.duration_min == 53.0
    assert a15.total_sets == 3
    assert a15.total_reps == 31
    assert a15.total_volume_kg == pytest.approx(17.5 * 10 + 17.5 * 8 + 32 * 13)

    # per-exercise set ordinals
    sets = db.scalars(
        select(models.WorkoutSet)
        .where(models.WorkoutSet.activity_id == a15.id)
        .order_by(models.WorkoutSet.id)
    ).all()
    assert [s.set_number for s in sets] == [1, 2, 1]
    assert sets[1].note == "+1r"


def test_idempotent_rerun(db):
    rows = [_row(), _row(Reps="8")]
    import_csv(db, rows)
    stats = import_csv(db, rows)
    assert stats.workouts_created == 0
    assert stats.workouts_skipped_existing == 1
    assert db.scalar(select(models.Activity).where(
        models.Activity.external_id == "repcount:2026-07-15T16:55"
    )) is not None
    assert len(db.scalars(select(models.WorkoutSet)).all()) == 2


def test_exercise_matching_case_and_space_insensitive(db):
    db.add(models.Exercise(name="Pull Up", category="pull", is_custom=0, created_at="x"))
    db.commit()
    stats = import_csv(db, [_row(Exercise="  pull up ")])
    assert stats.exercises_created == []
    assert len(db.scalars(select(models.Exercise)).all()) == 1


def test_unknown_exercise_created_with_mapped_category(db):
    stats = import_csv(db, [_row(Exercise="EZ skull crushers ", Category="Triceps")])
    assert stats.exercises_created == ["EZ skull crushers"]
    ex = db.scalar(select(models.Exercise))
    assert ex.name == "EZ skull crushers"
    assert ex.category == "push"
    assert ex.is_custom == 1
    assert "triceps" in (ex.primary_muscles or "")


def test_skip_rules_and_weight_zero_kept(db):
    rows = [
        _row(Weight="0", Reps="8"),          # bodyweight set: kept
        _row(Weight="", Reps="10"),          # no weight: skipped
        _row(Weight="15", Reps=""),          # no reps: skipped
        _row(Exercise="", Kcal="141"),       # cardio row: skipped
    ]
    stats = import_csv(db, rows)
    assert stats.sets_created == 1
    ws = db.scalar(select(models.WorkoutSet))
    assert ws.weight_kg == 0.0
    assert stats.skipped_rows["missing weight"] == 1
    assert stats.skipped_rows["missing/invalid reps"] == 1
    assert stats.skipped_rows["cardio row"] == 1


def test_bodyweight_import(db):
    import_csv(db, [_row(Bodyweight="78.4")])
    bw = db.scalar(select(models.WeightLog))
    assert bw is not None
    assert bw.weight_kg == 78.4
    assert bw.source == "repcount"
    assert bw.date == "2026-07-15"


def test_dry_run_rolls_back(db):
    stats = import_csv(db, [_row()], dry_run=True)
    assert stats.workouts_created == 1
    assert db.scalars(select(models.Activity)).all() == []


def test_import_links_to_overlapping_garmin_activity(db):
    garmin = models.Activity(
        external_id="g1", date="2026-07-15", start_ts="2026-07-15 16:50:08",
        type="strength_training", source="garmin", synced_at="x",
        duration_min=43.0, avg_hr=90, max_hr=122, calories=165,
    )
    db.add(garmin)
    db.commit()

    stats = import_csv(db, [_row()])
    assert stats.workouts_linked_to_garmin == 1
    imported = db.scalar(
        select(models.Activity).where(models.Activity.source == "repcount")
    )
    assert imported.linked_activity_id == garmin.id
    assert imported.avg_hr == 90
    assert imported.calories == 165


def test_import_does_not_link_repcount_to_itself_or_each_other(db):
    rows = [
        _row(),
        _row(**{"Workout Start": "2026-07-15 06:00", "Workout End": ""}),
    ]
    stats = import_csv(db, rows)
    assert stats.workouts_linked_to_garmin == 0
    for a in db.scalars(select(models.Activity)):
        assert a.linked_activity_id is None


def test_imported_sets_feed_ghosts_and_prs(db):
    import_csv(db, [_row(Weight="80", Reps="10")])
    ex = db.scalar(select(models.Exercise))
    ghost = strength.last_session_data(db, [ex.id])
    assert ghost[ex.id]["date"] == "2026-07-15"
    assert ghost[ex.id]["sets"][0]["weight_kg"] == 80.0
    prs = strength.personal_records(db, ex.id)
    assert prs["best_e1rm"]["weight_kg"] == 80.0
