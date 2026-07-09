"""Garmin Connect source via the unofficial python-garminconnect library.

ALL Garmin-specific JSON parsing lives in this file so that when Garmin
changes their (unofficial) API, the blast radius is exactly this module.
Untested against a live account until one exists; mapper functions are
unit-tested against recorded sample JSON fixtures.
"""

import logging
from datetime import date

from ..config import settings
from .base import ActivityDTO, DailyMetricsDTO, DataSource, SleepDTO, WeightDTO

logger = logging.getLogger(__name__)


def _get(d: dict | None, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur if cur is not None else default


# ---- pure mappers (unit-testable without a Garmin account) -------------------


def map_daily_metrics(day: date, stats: dict, hrv: dict | None) -> DailyMetricsDTO:
    """stats: garmin.get_stats(date) / user summary. hrv: garmin.get_hrv_data(date)."""
    total = _get(stats, "totalKilocalories")
    bmr = _get(stats, "bmrKilocalories")
    active = _get(stats, "activeKilocalories")
    return DailyMetricsDTO(
        date=day,
        steps=_get(stats, "totalSteps"),
        resting_hr=_get(stats, "restingHeartRate"),
        hrv_last_night_avg=_get(hrv, "hrvSummary", "lastNightAvg"),
        hrv_status=_get(hrv, "hrvSummary", "status"),
        stress_avg=_get(stats, "averageStressLevel"),
        body_battery_high=_get(stats, "bodyBatteryHighestValue"),
        body_battery_low=_get(stats, "bodyBatteryLowestValue"),
        calories_total_out=int(total) if total is not None else None,
        calories_bmr=int(bmr) if bmr is not None else None,
        calories_active=int(active) if active is not None else None,
    )


def map_sleep(day: date, data: dict) -> SleepDTO | None:
    """data: garmin.get_sleep_data(date)."""
    daily = _get(data, "dailySleepDTO", default={})
    seconds = _get(daily, "sleepTimeSeconds")
    if not seconds:
        return None

    def _min(key):
        v = _get(daily, key)
        return int(v / 60) if v is not None else None

    return SleepDTO(
        date=day,
        start_ts=_get(daily, "sleepStartTimestampLocal"),
        end_ts=_get(daily, "sleepEndTimestampLocal"),
        duration_min=int(seconds / 60),
        deep_min=_min("deepSleepSeconds"),
        light_min=_min("lightSleepSeconds"),
        rem_min=_min("remSleepSeconds"),
        awake_min=_min("awakeSleepSeconds"),
        sleep_score=_get(daily, "sleepScores", "overall", "value"),
        avg_overnight_hrv=_get(data, "avgOvernightHrv"),
    )


def map_activity(a: dict) -> ActivityDTO | None:
    start_local = _get(a, "startTimeLocal")
    if not start_local or _get(a, "activityId") is None:
        return None
    dur_s = _get(a, "duration")
    dist_m = _get(a, "distance")
    return ActivityDTO(
        external_id=str(a["activityId"]),
        date=date.fromisoformat(start_local[:10]),
        start_ts=start_local,
        type=_get(a, "activityType", "typeKey"),
        name=_get(a, "activityName"),
        duration_min=round(dur_s / 60, 1) if dur_s else None,
        distance_km=round(dist_m / 1000, 2) if dist_m else None,
        calories=int(a["calories"]) if _get(a, "calories") is not None else None,
        avg_hr=_get(a, "averageHR"),
        max_hr=_get(a, "maxHR"),
    )


def map_weight(entry: dict) -> WeightDTO | None:
    grams = _get(entry, "weight")
    day_str = _get(entry, "calendarDate")
    if grams is None or not day_str:
        return None
    return WeightDTO(
        date=date.fromisoformat(day_str),
        ts=_get(entry, "date", default=day_str) if isinstance(_get(entry, "date"), str) else day_str,
        weight_kg=round(grams / 1000, 2),
    )


# ---- live source --------------------------------------------------------------


class GarminSource(DataSource):
    name = "garmin"

    def __init__(self):
        self._client = None

    def _garmin(self):
        if self._client is None:
            from garminconnect import Garmin

            settings.garmin_token_dir.mkdir(parents=True, exist_ok=True)
            tokenstore = str(settings.garmin_token_dir)
            client = Garmin(settings.garmin_email, settings.garmin_password)
            try:
                client.login(tokenstore)
            except Exception:
                logger.info("Token login failed; performing fresh credential login")
                client.login()
                client.garth.dump(tokenstore)
            self._client = client
        return self._client

    def fetch_daily_metrics(self, day: date) -> DailyMetricsDTO | None:
        g = self._garmin()
        iso = day.isoformat()
        stats = g.get_stats(iso)
        if not stats:
            return None
        try:
            hrv = g.get_hrv_data(iso)
        except Exception:
            logger.warning("HRV fetch failed for %s", iso, exc_info=True)
            hrv = None
        return map_daily_metrics(day, stats, hrv)

    def fetch_sleep(self, day: date) -> SleepDTO | None:
        data = self._garmin().get_sleep_data(day.isoformat())
        return map_sleep(day, data) if data else None

    def fetch_activities(self, start: date, end: date) -> list[ActivityDTO]:
        raw = self._garmin().get_activities_by_date(start.isoformat(), end.isoformat())
        return [dto for a in raw or [] if (dto := map_activity(a))]

    def fetch_weight(self, start: date, end: date) -> list[WeightDTO]:
        raw = self._garmin().get_weigh_ins(start.isoformat(), end.isoformat())
        entries = []
        for group in _get(raw, "dailyWeightSummaries", default=[]) or []:
            for m in group.get("allWeightMetrics", []) or []:
                if dto := map_weight(m):
                    entries.append(dto)
        return entries
