"""Unit tests for GarminSource JSON -> DTO mappers, using recorded sample
shapes from the python-garminconnect README/examples. These run without a
Garmin account; live fetching is exercised once an account exists."""

from datetime import date

from app.datasources.garmin_source import (
    map_activity,
    map_daily_metrics,
    map_sleep,
    map_weight,
)

DAY = date(2026, 7, 1)


def test_map_daily_metrics():
    stats = {
        "totalSteps": 9876,
        "restingHeartRate": 51,
        "averageStressLevel": 28,
        "bodyBatteryHighestValue": 92,
        "bodyBatteryLowestValue": 21,
        "totalKilocalories": 2450.0,
        "bmrKilocalories": 1740.0,
        "activeKilocalories": 710.0,
    }
    hrv = {"hrvSummary": {"lastNightAvg": 58, "status": "BALANCED"}}
    dto = map_daily_metrics(DAY, stats, hrv)
    assert dto.steps == 9876
    assert dto.resting_hr == 51
    assert dto.hrv_last_night_avg == 58
    assert dto.hrv_status == "BALANCED"
    assert dto.calories_total_out == 2450
    assert dto.calories_bmr == 1740
    assert dto.calories_active == 710


def test_map_daily_metrics_missing_fields():
    dto = map_daily_metrics(DAY, {}, None)
    assert dto.steps is None
    assert dto.hrv_last_night_avg is None
    assert dto.calories_total_out is None


def test_map_sleep():
    data = {
        "dailySleepDTO": {
            "sleepTimeSeconds": 27000,
            "sleepStartTimestampLocal": "2026-06-30T23:15:00.0",
            "sleepEndTimestampLocal": "2026-07-01T07:00:00.0",
            "deepSleepSeconds": 5400,
            "lightSleepSeconds": 14400,
            "remSleepSeconds": 6000,
            "awakeSleepSeconds": 1200,
            "sleepScores": {"overall": {"value": 82}},
        },
        "avgOvernightHrv": 55.0,
    }
    dto = map_sleep(DAY, data)
    assert dto is not None
    assert dto.duration_min == 450
    assert dto.deep_min == 90
    assert dto.sleep_score == 82
    assert dto.avg_overnight_hrv == 55.0


def test_map_sleep_no_data():
    assert map_sleep(DAY, {}) is None
    assert map_sleep(DAY, {"dailySleepDTO": {"sleepTimeSeconds": 0}}) is None


def test_map_activity():
    a = {
        "activityId": 123456789,
        "activityName": "Morning Run",
        "startTimeLocal": "2026-07-01 07:30:00",
        "activityType": {"typeKey": "running"},
        "duration": 2700.0,
        "distance": 8000.0,
        "calories": 480.0,
        "averageHR": 152,
        "maxHR": 176,
    }
    dto = map_activity(a)
    assert dto is not None
    assert dto.external_id == "123456789"
    assert dto.date == date(2026, 7, 1)
    assert dto.duration_min == 45.0
    assert dto.distance_km == 8.0
    assert dto.calories == 480


def test_map_activity_invalid():
    assert map_activity({}) is None
    assert map_activity({"activityId": 1}) is None  # no start time


def test_map_weight():
    entry = {"weight": 74250.0, "calendarDate": "2026-07-01"}
    dto = map_weight(entry)
    assert dto is not None
    assert dto.weight_kg == 74.25
    assert dto.date == date(2026, 7, 1)


def test_map_weight_invalid():
    assert map_weight({}) is None
    assert map_weight({"calendarDate": "2026-07-01"}) is None
