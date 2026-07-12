"""DataSource contract. All external health-data providers (Garmin, mock)
implement this interface; the rest of the app only ever sees these DTOs."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date


@dataclass
class DailyMetricsDTO:
    date: date
    steps: int | None = None
    resting_hr: int | None = None
    hrv_last_night_avg: float | None = None
    hrv_status: str | None = None
    stress_avg: int | None = None
    body_battery_high: int | None = None
    body_battery_low: int | None = None
    calories_total_out: int | None = None
    calories_bmr: int | None = None
    calories_active: int | None = None


@dataclass
class SleepDTO:
    date: date  # wake date
    start_ts: str | None = None
    end_ts: str | None = None
    duration_min: int | None = None
    deep_min: int | None = None
    light_min: int | None = None
    rem_min: int | None = None
    awake_min: int | None = None
    sleep_score: int | None = None
    avg_overnight_hrv: float | None = None


@dataclass
class ActivityDTO:
    external_id: str
    date: date
    start_ts: str | None = None
    type: str | None = None
    name: str | None = None
    duration_min: float | None = None
    distance_km: float | None = None
    calories: int | None = None
    avg_hr: int | None = None
    max_hr: int | None = None
    moving_duration_min: float | None = None
    elevation_gain_m: float | None = None
    avg_speed_mps: float | None = None
    max_speed_mps: float | None = None
    aerobic_te: float | None = None
    anaerobic_te: float | None = None
    training_effect_label: str | None = None
    training_load: float | None = None
    vo2max: float | None = None
    avg_power: float | None = None
    norm_power: float | None = None
    avg_run_cadence: float | None = None
    total_sets: int | None = None
    total_reps: int | None = None
    total_volume_kg: float | None = None
    lap_count: int | None = None


@dataclass
class WeightDTO:
    date: date
    ts: str
    weight_kg: float


@dataclass
class LapDTO:
    lap_index: int
    duration_s: float | None = None
    distance_km: float | None = None
    avg_hr: int | None = None
    avg_speed_mps: float | None = None
    elevation_gain_m: float | None = None


@dataclass
class HrZoneDTO:
    zone_number: int
    secs_in_zone: float | None = None
    zone_low_boundary: int | None = None


@dataclass
class GarminSetDTO:
    """A strength set auto-detected by the watch (prefill for manual editing)."""

    set_number: int
    reps: int
    weight_kg: float | None = None
    exercise_name: str | None = None  # Garmin's category/name guess


class DataSource(ABC):
    name: str

    @abstractmethod
    def fetch_daily_metrics(self, day: date) -> DailyMetricsDTO | None: ...

    @abstractmethod
    def fetch_sleep(self, day: date) -> SleepDTO | None: ...

    @abstractmethod
    def fetch_activities(self, start: date, end: date) -> list[ActivityDTO]: ...

    @abstractmethod
    def fetch_weight(self, start: date, end: date) -> list[WeightDTO]: ...

    def fetch_activity_laps(self, external_id: str) -> list[LapDTO]:
        return []

    def fetch_exercise_sets(self, external_id: str) -> list[GarminSetDTO]:
        return []

    def fetch_activity_hr_zones(self, external_id: str) -> list[HrZoneDTO]:
        return []
