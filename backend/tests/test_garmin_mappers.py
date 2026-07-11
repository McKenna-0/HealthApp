"""Unit tests for GarminSource JSON -> DTO mappers, using recorded sample
shapes from the python-garminconnect README/examples. These run without a
Garmin account; live fetching is exercised once an account exists."""

from datetime import date

from app.datasources.garmin_source import (
    map_activity,
    map_daily_metrics,
    map_exercise_sets,
    map_laps,
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


def test_map_activity_enriched_cardio():
    a = {
        "activityId": 111,
        "activityName": "Long Ride",
        "startTimeLocal": "2026-07-11 09:00:00",
        "activityType": {"typeKey": "cycling"},
        "duration": 12594.0,
        "movingDuration": 12000.0,
        "distance": 59040.0,
        "calories": 1041.0,
        "averageHR": 104,
        "maxHR": 163,
        "elevationGain": 420.5,
        "averageSpeed": 4.69,
        "maxSpeed": 14.2,
        "aerobicTrainingEffect": 3.2,
        "anaerobicTrainingEffect": 0.4,
        "trainingEffectLabel": "AEROBIC_BASE",
        "activityTrainingLoad": 185.3,
        "vO2MaxValue": 52.0,
        "lapCount": 12,
    }
    dto = map_activity(a)
    assert dto.moving_duration_min == 200.0
    assert dto.elevation_gain_m == 420.5
    assert dto.avg_speed_mps == 4.69
    assert dto.training_load == 185.3
    assert dto.vo2max == 52.0
    assert dto.lap_count == 12


def test_map_activity_enriched_strength():
    a = {
        "activityId": 222,
        "activityName": "Strength",
        "startTimeLocal": "2026-07-10 18:00:00",
        "activityType": {"typeKey": "strength_training"},
        "duration": 3600.0,
        "calories": 300.0,
        "totalSets": 18,
        "totalReps": 160,
        "totalVolume": 5240.0,
    }
    dto = map_activity(a)
    assert dto.total_sets == 18
    assert dto.total_reps == 160
    assert dto.total_volume_kg == 5240.0


def test_map_laps():
    data = {
        "lapDTOs": [
            {"lapIndex": 1, "duration": 300.0, "distance": 1000.0, "averageHR": 150,
             "averageSpeed": 3.33, "elevationGain": 5.0},
            {"lapIndex": 2, "duration": 310.0, "distance": 1000.0, "averageHR": 155,
             "averageSpeed": 3.22, "elevationGain": 8.0},
        ]
    }
    laps = map_laps(data)
    assert len(laps) == 2
    assert laps[0].distance_km == 1.0
    assert laps[1].avg_hr == 155


def test_map_exercise_sets_grams_to_kg_and_rest_filtered():
    data = {
        "exerciseSets": [
            {"setType": "ACTIVE", "repetitionCount": 8,
             "weight": 80000.0, "exercises": [{"category": "BENCH_PRESS", "name": None}]},
            {"setType": "REST", "repetitionCount": None, "weight": None, "exercises": []},
            {"setType": "ACTIVE", "repetitionCount": 10,
             "weight": None, "exercises": [{"category": "PUSH_UP", "name": "PUSH_UP"}]},
        ]
    }
    sets = map_exercise_sets(data)
    assert len(sets) == 2  # REST filtered
    assert sets[0].weight_kg == 80.0  # grams -> kg
    assert sets[0].exercise_name == "Bench Press"
    assert sets[0].set_number == 1
    assert sets[1].set_number == 2
    assert sets[1].weight_kg is None
