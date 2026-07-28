import json

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- read models -------------------------------------------------------------


class DailyMetricsOut(ORMModel):
    date: str
    steps: int | None
    resting_hr: int | None
    hrv_last_night_avg: float | None
    hrv_status: str | None
    stress_avg: int | None
    body_battery_high: int | None
    body_battery_low: int | None
    calories_total_out: int | None
    calories_bmr: int | None
    calories_active: int | None
    source: str


class SleepOut(ORMModel):
    date: str
    start_ts: str | None
    end_ts: str | None
    duration_min: int | None
    deep_min: int | None
    light_min: int | None
    rem_min: int | None
    awake_min: int | None
    sleep_score: int | None
    avg_overnight_hrv: float | None


class ActivityOut(ORMModel):
    id: int
    external_id: str
    date: str
    start_ts: str | None
    type: str | None
    name: str | None
    duration_min: float | None
    distance_km: float | None
    calories: int | None
    avg_hr: int | None
    max_hr: int | None
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
    source: str | None = None
    status: str | None = None
    ended_ts: str | None = None
    linked_activity_id: int | None = None


class ExerciseOut(ORMModel):
    id: int
    name: str
    category: str
    equipment: str | None
    is_custom: int
    primary_muscles: list[str] = []
    secondary_muscles: list[str] = []

    @field_validator("primary_muscles", "secondary_muscles", mode="before")
    @classmethod
    def _parse_muscles(cls, v: object) -> object:
        if v is None:
            return []
        if isinstance(v, str):
            return json.loads(v) if v else []
        return v


class ExerciseIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    category: str = Field(pattern="^(push|pull|legs|core|other)$")
    equipment: str | None = None
    primary_muscles: list[str] = []
    secondary_muscles: list[str] = []


class WorkoutSetOut(ORMModel):
    id: int
    activity_id: int
    exercise_id: int
    set_number: int
    reps: int
    weight_kg: float | None
    rpe: float | None
    note: str | None
    source: str
    is_warmup: int = 0


class WorkoutSetIn(BaseModel):
    exercise_id: int
    reps: int = Field(gt=0, le=200)
    weight_kg: float | None = Field(default=None, ge=0, le=600)
    rpe: float | None = Field(default=None, ge=1, le=10)
    note: str | None = None
    is_warmup: int = Field(default=0, ge=0, le=1)


class WorkoutSetUpdate(BaseModel):
    exercise_id: int | None = None
    reps: int | None = Field(default=None, gt=0, le=200)
    weight_kg: float | None = Field(default=None, ge=0, le=600)
    rpe: float | None = Field(default=None, ge=1, le=10)
    note: str | None = None
    is_warmup: int | None = Field(default=None, ge=0, le=1)


class SetLogResult(BaseModel):
    set: WorkoutSetOut
    e1rm: float | None = None
    is_pr: bool = False
    delta_weight_kg: float | None = None
    delta_reps: int | None = None


class SessionCreateIn(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    routine_id: int | None = None
    repeat_workout_id: int | None = None


class PlannedExercise(BaseModel):
    exercise_id: int
    name: str
    target_sets: int = 3


class GhostSet(BaseModel):
    set_number: int
    weight_kg: float | None
    reps: int


class ExerciseGhost(BaseModel):
    date: str
    sets: list[GhostSet]
    best_e1rm: float | None = None


class SessionOut(BaseModel):
    activity: ActivityOut
    planned_exercises: list[PlannedExercise] = []
    ghosts: dict[int, ExerciseGhost] = {}


class RoutineExerciseIn(BaseModel):
    exercise_id: int
    target_sets: int = Field(default=3, gt=0, le=20)


class RoutineIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    exercises: list[RoutineExerciseIn] = []


class RoutineExerciseOut(BaseModel):
    exercise_id: int
    name: str
    target_sets: int


class RoutineOut(BaseModel):
    id: int
    name: str
    created_at: str
    last_used_at: str | None
    exercises: list[RoutineExerciseOut] = []


class WorkoutPR(BaseModel):
    exercise_id: int
    exercise_name: str
    weight_kg: float | None
    reps: int
    e1rm: float | None


class WorkoutSummaryOut(BaseModel):
    workout_id: int
    name: str | None
    date: str
    start_ts: str | None
    ended_ts: str | None
    duration_min: float | None
    avg_hr: int | None
    max_hr: int | None
    calories: int | None
    tonnage_kg: float
    total_sets: int
    total_reps: int
    exercise_count: int
    prs: list[WorkoutPR] = []
    muscles: dict[str, float] = {}
    linked_activity_id: int | None = None


class LapOut(ORMModel):
    lap_index: int
    duration_s: float | None
    distance_km: float | None
    avg_hr: int | None
    avg_speed_mps: float | None
    elevation_gain_m: float | None


class HrZoneOut(ORMModel):
    zone_number: int
    secs_in_zone: float | None
    zone_low_boundary: int | None


class WeightOut(ORMModel):
    id: int
    date: str
    ts: str
    weight_kg: float
    source: str
    note: str | None


class FoodCacheOut(ORMModel):
    id: int
    api_source: str
    external_id: str
    name: str
    brand: str | None
    kcal_per_100g: float | None
    protein_g: float | None
    carbs_g: float | None
    fat_g: float | None
    serving_size_g: float | None
    serving_size_text: str | None = None
    is_favorite: int = 0


class ServingOption(BaseModel):
    label: str
    grams: float


class RecentFoodOut(FoodCacheOut):
    last_quantity_g: float | None = None
    last_meal: str | None = None


class CustomFoodIn(BaseModel):
    """Per-100g values, OR per-serving values + serving_size_g (normalized on save)."""

    name: str = Field(min_length=2, max_length=120)
    brand: str | None = None
    serving_size_g: float | None = Field(default=None, gt=0)
    per_serving: bool = False  # if true, macro values are per serving
    kcal: float = Field(ge=0)
    protein_g: float | None = Field(default=None, ge=0)
    carbs_g: float | None = Field(default=None, ge=0)
    fat_g: float | None = Field(default=None, ge=0)


class CopyDayIn(BaseModel):
    from_date: str
    to_date: str
    meal: str | None = Field(default=None, pattern="^(breakfast|lunch|dinner|snack)$")


class FoodLogOut(ORMModel):
    id: int
    date: str
    ts: str
    meal: str
    food_cache_id: int | None
    description: str | None
    quantity_g: float | None
    calories: float
    protein_g: float | None
    carbs_g: float | None
    fat_g: float | None
    logging_complete_day: int


class ContextOut(ORMModel):
    id: int
    date: str
    ts: str
    type: str
    value: float | None
    label: str | None
    note: str | None


_HHMM = r"^\d{2}:\d{2}$"


class CheckinIn(BaseModel):
    mood: int | None = Field(default=None, ge=1, le=5)
    alcohol_units: float = Field(default=0, ge=0, le=30)
    caffeine_cups: float = Field(default=0, ge=0, le=15)
    caffeine_last_time: str | None = Field(default=None, pattern=_HHMM)
    illness: int = Field(default=0, ge=0, le=1)
    eating_start: str | None = Field(default=None, pattern=_HHMM)
    eating_end: str | None = Field(default=None, pattern=_HHMM)
    weight_kg: float | None = Field(default=None, gt=20, lt=400)
    note: str | None = None


class CheckinOut(ORMModel):
    date: str
    ts: str
    mood: int | None
    alcohol_units: float
    caffeine_cups: float
    caffeine_last_time: str | None
    illness: int
    eating_start: str | None
    eating_end: str | None
    note: str | None


class CheckinResponse(BaseModel):
    exists: bool
    checkin: CheckinOut | None = None
    derived_eating_start: str | None = None
    derived_eating_end: str | None = None
    fasting_hours: float | None = None
    weight_kg: float | None = None  # today's manual weight, for prefill


class WeekDayStatus(BaseModel):
    date: str
    weekday: str
    food_logged: bool
    checkin_done: bool
    complete: bool


class StreakOut(BaseModel):
    current_streak: int
    longest_streak: int
    today_complete: bool
    week: list[WeekDayStatus]


class SyncLogOut(ORMModel):
    id: int
    started_at: str
    finished_at: str | None
    source: str
    days_requested: int
    status: str
    error: str | None


class SyncStatusOut(BaseModel):
    last_success_at: str | None
    last_attempt_at: str | None
    last_status: str | None
    last_error: str | None
    stale: bool


# ---- write models --------------------------------------------------------------


class WeightIn(BaseModel):
    date: str  # YYYY-MM-DD
    weight_kg: float = Field(gt=20, lt=400)
    note: str | None = None


class FoodLogIn(BaseModel):
    date: str
    meal: str = Field(pattern="^(breakfast|lunch|dinner|snack)$")
    food_cache_id: int | None = None
    description: str | None = None
    quantity_g: float | None = Field(default=None, gt=0)
    calories: float | None = Field(default=None, ge=0)  # required if no cache item
    ts: str | None = None  # optional ISO timestamp; server uses iso_now() if absent


class FoodLogUpdate(BaseModel):
    meal: str | None = Field(default=None, pattern="^(breakfast|lunch|dinner|snack)$")
    quantity_g: float | None = Field(default=None, gt=0)
    calories: float | None = Field(default=None, ge=0)
    description: str | None = None
    logging_complete_day: int | None = Field(default=None, ge=0, le=1)
    ts: str | None = None


class ContextIn(BaseModel):
    date: str
    type: str = Field(pattern="^(alcohol|caffeine|mood|illness|supplement|note)$")
    value: float | None = None
    label: str | None = None
    note: str | None = None
