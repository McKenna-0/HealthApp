"""Deterministic mock data source.

Generates physiologically plausible, correlated time series so the whole
pipeline (ingest -> DB -> API -> analytics -> UI) can be exercised without a
Garmin account. Deterministic per (seed, date): the same date always yields
the same data.

Ground truth built into the data (used by tests and to sanity-check TDEE):
  - weight trend: -0.045 kg/day (~ -350 kcal/day deficit vs intake seeding)
  - alcohol nights (mostly Fri/Sat): HRV down ~25%, RHR +5-8, sleep score -20
  - one 4-day illness stretch per ~97 days: RHR +10, HRV down, steps way down
"""

import math
import random
from datetime import date, datetime, time, timedelta

from ..timeutil import tzinfo
from .base import (
    ActivityDTO,
    ActivityTimeSeriesDTO,
    DailyMetricsDTO,
    DataSource,
    IntradayBodyBatteryDTO,
    IntradayStressDTO,
    SleepDTO,
    WeightDTO,
)

ANCHOR = date(2026, 1, 1)
BASE_WEIGHT_KG = 82.0
WEIGHT_SLOPE_KG_PER_DAY = -0.045
BASE_BMR = 1750
BASE_HRV = 55.0
BASE_RHR = 52


def _clip(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


class MockSource(DataSource):
    name = "mock"

    def __init__(self, seed: int = 42):
        self.seed = seed

    # ---- latent daily state -------------------------------------------------

    def _rng(self, day: date, salt: str = "") -> random.Random:
        return random.Random(f"{self.seed}:{day.isoformat()}:{salt}")

    def is_alcohol_night(self, day: date) -> bool:
        """Did drinking happen on the evening of `day`? (affects next morning)"""
        r = self._rng(day, "alcohol")
        p = {4: 0.6, 5: 0.5}.get(day.weekday(), 0.05)  # Fri, Sat
        return r.random() < p

    def is_ill(self, day: date) -> bool:
        return day.toordinal() % 97 in (10, 11, 12, 13)

    def is_training_day(self, day: date) -> bool:
        return day.weekday() in (0, 1, 3, 5) and not self.is_ill(day)

    # ---- generators ----------------------------------------------------------

    def _steps(self, day: date) -> int:
        r = self._rng(day, "steps")
        if self.is_ill(day):
            return int(r.gauss(3000, 800))
        base = 10000 if day.weekday() >= 5 else 8000
        if self.is_training_day(day):
            base += 3000
        return max(1000, int(r.gauss(base, 1500)))

    def _activities_for(self, day: date) -> list[ActivityDTO]:
        if not self.is_training_day(day):
            return []
        r = self._rng(day, "activity")
        is_run = day.isocalendar().week % 2 == day.weekday() % 2
        start = datetime.combine(day, time(18, 0), tzinfo()) + timedelta(
            minutes=r.randint(-60, 60)
        )
        if is_run:
            dur = r.gauss(45, 8)
            return [
                ActivityDTO(
                    external_id=f"mock-{day.isoformat()}-run",
                    date=day,
                    start_ts=start.isoformat(timespec="seconds"),
                    type="running",
                    name="Evening Run",
                    duration_min=round(dur, 1),
                    distance_km=round(dur / 5.6, 2),
                    calories=int(dur * 10.7),
                    avg_hr=int(r.gauss(152, 6)),
                    max_hr=int(r.gauss(178, 5)),
                )
            ]
        dur = r.gauss(50, 10)
        return [
            ActivityDTO(
                external_id=f"mock-{day.isoformat()}-strength",
                date=day,
                start_ts=start.isoformat(timespec="seconds"),
                type="strength_training",
                name="Strength",
                duration_min=round(dur, 1),
                distance_km=None,
                calories=int(dur * 6.0),
                avg_hr=int(r.gauss(118, 8)),
                max_hr=int(r.gauss(150, 8)),
            )
        ]

    def fetch_daily_metrics(self, day: date) -> DailyMetricsDTO | None:
        r = self._rng(day, "daily")
        drank_last_night = self.is_alcohol_night(day - timedelta(days=1))
        ill = self.is_ill(day)

        hrv = r.gauss(BASE_HRV, 4)
        rhr = r.gauss(BASE_RHR, 1.5)
        stress = r.gauss(30, 6)
        if drank_last_night:
            hrv *= 0.75
            rhr += r.uniform(5, 8)
            stress += 15
        if ill:
            hrv *= 0.8
            rhr += 10
            stress += 20

        steps = self._steps(day)
        activity_cal = sum(a.calories or 0 for a in self._activities_for(day))
        active = int(steps * 0.04 + activity_cal)
        bmr = int(r.gauss(BASE_BMR, 15))

        bb_high = max(20, min(100, int(r.gauss(85, 8) - (25 if drank_last_night else 0) - (20 if ill else 0))))
        bb_low = max(5, bb_high - int(r.gauss(60, 10)))

        return DailyMetricsDTO(
            date=day,
            steps=steps,
            resting_hr=int(rhr),
            hrv_last_night_avg=round(hrv, 1),
            hrv_status="unbalanced" if (drank_last_night or ill) else "balanced",
            stress_avg=max(5, min(95, int(stress))),
            body_battery_high=bb_high,
            body_battery_low=bb_low,
            calories_total_out=bmr + active,
            calories_bmr=bmr,
            calories_active=active,
        )

    def fetch_sleep(self, day: date) -> SleepDTO | None:
        r = self._rng(day, "sleep")
        drank = self.is_alcohol_night(day - timedelta(days=1))
        ill = self.is_ill(day)

        duration = r.gauss(450, 35)
        score = r.gauss(80, 7)
        deep_frac = r.gauss(0.20, 0.03)
        if drank:
            duration -= 40
            score -= 20
            deep_frac *= 0.7
        if ill:
            duration += 30
            score -= 10

        duration = max(240, duration)
        score = max(20, min(100, int(score)))
        deep = duration * max(0.05, deep_frac)
        rem = duration * r.gauss(0.22, 0.03)
        awake = duration * r.gauss(0.05, 0.015)
        light = duration - deep - rem - awake

        bedtime = datetime.combine(
            day - timedelta(days=1), time(23, 0), tzinfo()
        ) + timedelta(minutes=r.randint(-40, 60) + (45 if drank else 0))
        wake = bedtime + timedelta(minutes=duration)

        metrics = self.fetch_daily_metrics(day)
        return SleepDTO(
            date=day,
            start_ts=bedtime.isoformat(timespec="seconds"),
            end_ts=wake.isoformat(timespec="seconds"),
            duration_min=int(duration),
            deep_min=int(deep),
            light_min=int(light),
            rem_min=int(rem),
            awake_min=int(awake),
            sleep_score=score,
            avg_overnight_hrv=metrics.hrv_last_night_avg if metrics else None,
        )

    def fetch_activities(self, start: date, end: date) -> list[ActivityDTO]:
        out: list[ActivityDTO] = []
        d = start
        while d <= end:
            out.extend(self._activities_for(d))
            d += timedelta(days=1)
        return out

    def _minute_of_day(self, iso_ts: str, day: date) -> float:
        dt = datetime.fromisoformat(iso_ts)
        delta = dt - datetime.combine(day, time(0, 0), dt.tzinfo)
        return delta.total_seconds() / 60

    def _day_windows(self, day: date) -> tuple[float, float, list[tuple[float, float]]]:
        """Returns (wake_minute, bedtime_minute, activity_windows) for `day`,
        in minutes since local midnight, used to shape the intraday curves."""
        sleep_today = self.fetch_sleep(day)  # wake this morning
        sleep_tonight = self.fetch_sleep(day + timedelta(days=1))  # bedtime tonight
        wake_min = (
            _clip(self._minute_of_day(sleep_today.end_ts, day), 0, 1439)
            if sleep_today and sleep_today.end_ts
            else 420
        )
        bedtime_min = (
            _clip(self._minute_of_day(sleep_tonight.start_ts, day), 0, 1439)
            if sleep_tonight and sleep_tonight.start_ts
            else 1380
        )
        if bedtime_min <= wake_min:
            bedtime_min = min(1439, wake_min + 600)
        act_windows = []
        for a in self._activities_for(day):
            if not a.start_ts or not a.duration_min:
                continue
            start_min = self._minute_of_day(a.start_ts, day)
            act_windows.append((start_min, start_min + a.duration_min))
        return wake_min, bedtime_min, act_windows

    def fetch_intraday_body_battery(self, day: date) -> list[IntradayBodyBatteryDTO]:
        metrics = self.fetch_daily_metrics(day)
        wake_min, bedtime_min, act_windows = self._day_windows(day)
        bb_high = (metrics.body_battery_high if metrics else None) or 80
        bb_low = (metrics.body_battery_low if metrics else None) or 25
        r = self._rng(day, "bb_curve")

        out = []
        for i in range(144):  # every 10 minutes
            minute = i * 10
            ts_str = (datetime.combine(day, time(0, 0), tzinfo()) + timedelta(minutes=minute)).strftime("%H:%M")

            if minute < wake_min:
                # overnight recharge, ramping up to bb_high by wake time
                frac = minute / wake_min if wake_min else 1
                level = bb_low + frac * (bb_high - bb_low)
            elif minute < bedtime_min:
                # daytime drain from bb_high down to bb_low by bedtime
                frac = (minute - wake_min) / (bedtime_min - wake_min)
                level = bb_high - frac * (bb_high - bb_low)
                for a_start, a_end in act_windows:
                    if a_start <= minute <= a_end + 30:
                        dip = 15 if minute <= a_end else 15 * max(0, 1 - (minute - a_end) / 30)
                        level -= dip
            else:
                # partial evening recharge after bedtime
                frac = (minute - bedtime_min) / max(1, 1440 - bedtime_min)
                level = bb_low + frac * 0.4 * (bb_high - bb_low)

            level += r.gauss(0, 2)
            if r.random() < 0.03:
                continue  # simulate real-world unmeasurable gaps
            out.append(
                IntradayBodyBatteryDTO(date=day, timestamp=ts_str, body_battery=int(round(_clip(level, 0, 100))))
            )
        return out

    def fetch_intraday_stress(self, day: date) -> list[IntradayStressDTO]:
        metrics = self.fetch_daily_metrics(day)
        wake_min, bedtime_min, act_windows = self._day_windows(day)
        stress_avg = (metrics.stress_avg if metrics else None) or 30
        r = self._rng(day, "stress_curve")

        out = []
        for i in range(144):
            minute = i * 10
            ts_str = (datetime.combine(day, time(0, 0), tzinfo()) + timedelta(minutes=minute)).strftime("%H:%M")

            if minute < wake_min or minute >= bedtime_min:
                level = r.gauss(15, 6)
            elif any(a_start <= minute <= a_end for a_start, a_end in act_windows):
                level = r.gauss(72, 10)
            else:
                level = r.gauss(stress_avg, 12)

            out.append(
                IntradayStressDTO(date=day, timestamp=ts_str, stress_level=int(round(_clip(level, 0, 100))))
            )
        return out

    def true_weight(self, day: date) -> float:
        """Underlying trend without measurement noise (used by tests)."""
        return BASE_WEIGHT_KG + WEIGHT_SLOPE_KG_PER_DAY * (day - ANCHOR).days

    def fetch_activity_timeseries(self, external_id: str) -> ActivityTimeSeriesDTO | None:
        if "run" not in external_id and "cycling" not in external_id:
            return None
        # Parse date from external_id pattern "mock-YYYY-MM-DD-run"
        parts = external_id.split("-")
        try:
            day = date(int(parts[1]), int(parts[2]), int(parts[3]))
        except (IndexError, ValueError):
            return None
        r = self._rng(day, "timeseries")
        n_points = 180  # 15s intervals for ~45 min
        points = []
        for i in range(n_points):
            elapsed_s = i * 15
            hr = int(r.gauss(152, 8))
            speed_mps = max(0.5, r.gauss(2.8, 0.3))
            elevation_m = 45 + 10 * math.sin(elapsed_s / 300)
            cadence = int(r.gauss(170, 5))
            points.append({
                "elapsed_s": elapsed_s,
                "hr": hr,
                "speed_mps": round(speed_mps, 3),
                "elevation_m": round(elevation_m, 1),
                "cadence": cadence,
            })
        return ActivityTimeSeriesDTO(points=points)

    def fetch_weight(self, start: date, end: date) -> list[WeightDTO]:
        out: list[WeightDTO] = []
        d = start
        while d <= end:
            r = self._rng(d, "weight")
            w = self.true_weight(d) + r.gauss(0, 0.4)
            if self.is_alcohol_night(d - timedelta(days=1)):
                w += 0.3  # water retention
            ts = datetime.combine(d, time(7, 15), tzinfo())
            out.append(
                WeightDTO(date=d, ts=ts.isoformat(timespec="seconds"), weight_kg=round(w, 2))
            )
            d += timedelta(days=1)
        return out
