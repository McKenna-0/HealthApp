import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.db import Base, get_db
from app.main import app
from app.services import targets

DAY = "2026-07-20"


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


def _settings(db, **kwargs):
    for key, value in kwargs.items():
        db.add(models.UserSetting(key=key, value=str(value)))
    db.commit()


def _metrics(db, day, calories_active):
    db.add(
        models.DailyMetrics(
            date=day,
            calories_active=calories_active,
            source="garmin",
            synced_at="2026-07-20T21:30:00",
        )
    )
    db.commit()


def test_active_calories_added_to_calorie_goal(db):
    _settings(db, calorie_target=2200)
    _metrics(db, DAY, 430)

    out = targets.resolve(db, DAY)

    assert out["active_calories"] == 430
    assert out["calories"] == {"base": 2200, "bonus": 430, "target": 2630}


def test_no_metrics_falls_back_to_base_goal(db):
    _settings(db, calorie_target=2200)

    out = targets.resolve(db, DAY)

    assert out["active_calories"] == 0
    assert out["calories"] == {"base": 2200, "bonus": 0, "target": 2200}


def test_bonus_ignored_without_a_calorie_goal(db):
    _metrics(db, DAY, 430)

    out = targets.resolve(db, DAY)

    assert out["active_calories"] == 430
    assert out["calories"] == {"base": None, "bonus": 0.0, "target": None}


def test_percent_macros_scale_with_active_calories(db):
    _settings(
        db,
        calorie_target=2200,
        macro_mode="percent",
        protein_target_pct=30,
        carbs_target_pct=40,
        fat_target_pct=30,
    )
    _metrics(db, DAY, 400)

    out = targets.resolve(db, DAY)

    # 30% of 2200 / 4 = 165g base, 30% of 400 / 4 = 30g bonus
    assert out["protein"] == {"base": 165, "bonus": 30, "target": 195}
    # 40% of 2200 / 4 = 220g base, 40% of 400 / 4 = 40g bonus
    assert out["carbs"] == {"base": 220, "bonus": 40, "target": 260}
    # 30% of 2200 / 9 = 73g base, 30% of 400 / 9 = 13g bonus
    assert out["fat"] == {"base": 73, "bonus": 13, "target": 86}


def test_gram_macros_are_absolute(db):
    _settings(
        db,
        calorie_target=2200,
        macro_mode="grams",
        protein_target_g=180,
        carbs_target_g=200,
        fat_target_g=70,
    )
    _metrics(db, DAY, 500)

    out = targets.resolve(db, DAY)

    assert out["calories"]["target"] == 2700
    assert out["protein"] == {"base": 180, "bonus": 0, "target": 180}
    assert out["carbs"]["bonus"] == 0
    assert out["fat"]["target"] == 70


def test_percent_mode_without_percentages_uses_gram_targets(db):
    _settings(db, calorie_target=2200, macro_mode="percent", protein_target_g=180)
    _metrics(db, DAY, 400)

    out = targets.resolve(db, DAY)

    assert out["protein"] == {"base": 180, "bonus": 0, "target": 180}
    assert out["carbs"]["target"] is None


def test_targets_endpoint(db):
    _settings(db, calorie_target=2000, macro_mode="percent", protein_target_pct=25)
    _metrics(db, DAY, 300)

    app.dependency_overrides[get_db] = lambda: db
    try:
        r = TestClient(app).get(f"/api/settings/targets?date={DAY}")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    body = r.json()
    assert body["date"] == DAY
    assert body["calories"]["target"] == 2300
    assert body["protein"]["target"] == 144  # (2000*.25/4) + (300*.25/4) = 125 + 19
