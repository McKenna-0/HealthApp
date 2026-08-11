from sqlalchemy import Float, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class DailyMetrics(Base):
    __tablename__ = "daily_metrics"

    date: Mapped[str] = mapped_column(Text, primary_key=True)  # YYYY-MM-DD
    steps: Mapped[int | None] = mapped_column(Integer)
    resting_hr: Mapped[int | None] = mapped_column(Integer)
    hrv_last_night_avg: Mapped[float | None] = mapped_column(Float)
    hrv_status: Mapped[str | None] = mapped_column(Text)
    stress_avg: Mapped[int | None] = mapped_column(Integer)
    body_battery_high: Mapped[int | None] = mapped_column(Integer)
    body_battery_low: Mapped[int | None] = mapped_column(Integer)
    calories_total_out: Mapped[int | None] = mapped_column(Integer)
    calories_bmr: Mapped[int | None] = mapped_column(Integer)
    calories_active: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(Text)
    synced_at: Mapped[str] = mapped_column(Text)


class Sleep(Base):
    __tablename__ = "sleep"

    date: Mapped[str] = mapped_column(Text, primary_key=True)  # wake date
    start_ts: Mapped[str | None] = mapped_column(Text)
    end_ts: Mapped[str | None] = mapped_column(Text)
    duration_min: Mapped[int | None] = mapped_column(Integer)
    deep_min: Mapped[int | None] = mapped_column(Integer)
    light_min: Mapped[int | None] = mapped_column(Integer)
    rem_min: Mapped[int | None] = mapped_column(Integer)
    awake_min: Mapped[int | None] = mapped_column(Integer)
    sleep_score: Mapped[int | None] = mapped_column(Integer)
    avg_overnight_hrv: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(Text)
    synced_at: Mapped[str] = mapped_column(Text)


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_id: Mapped[str] = mapped_column(Text, unique=True)
    date: Mapped[str] = mapped_column(Text, index=True)
    start_ts: Mapped[str | None] = mapped_column(Text)
    type: Mapped[str | None] = mapped_column(Text)
    name: Mapped[str | None] = mapped_column(Text)
    duration_min: Mapped[float | None] = mapped_column(Float)
    distance_km: Mapped[float | None] = mapped_column(Float)
    calories: Mapped[int | None] = mapped_column(Integer)
    avg_hr: Mapped[int | None] = mapped_column(Integer)
    max_hr: Mapped[int | None] = mapped_column(Integer)
    # v3 enrichment (all nullable; populated by Garmin re-sync)
    moving_duration_min: Mapped[float | None] = mapped_column(Float)
    elevation_gain_m: Mapped[float | None] = mapped_column(Float)
    avg_speed_mps: Mapped[float | None] = mapped_column(Float)
    max_speed_mps: Mapped[float | None] = mapped_column(Float)
    aerobic_te: Mapped[float | None] = mapped_column(Float)
    anaerobic_te: Mapped[float | None] = mapped_column(Float)
    training_effect_label: Mapped[str | None] = mapped_column(Text)
    training_load: Mapped[float | None] = mapped_column(Float)
    vo2max: Mapped[float | None] = mapped_column(Float)
    avg_power: Mapped[float | None] = mapped_column(Float)
    norm_power: Mapped[float | None] = mapped_column(Float)
    avg_run_cadence: Mapped[float | None] = mapped_column(Float)
    total_sets: Mapped[int | None] = mapped_column(Integer)
    total_reps: Mapped[int | None] = mapped_column(Integer)
    total_volume_kg: Mapped[float | None] = mapped_column(Float)
    lap_count: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(Text)
    synced_at: Mapped[str] = mapped_column(Text)
    # in-app workout sessions (NULL for synced/watch activities)
    status: Mapped[str | None] = mapped_column(Text)  # active | finished
    ended_ts: Mapped[str | None] = mapped_column(Text)
    planned_json: Mapped[str | None] = mapped_column(Text)  # [{exercise_id, target_sets}]
    linked_activity_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("activities.id")
    )


class WeightLog(Base):
    __tablename__ = "weight_log"
    __table_args__ = (UniqueConstraint("date", "source", name="uq_weight_date_source"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(Text, index=True)
    ts: Mapped[str] = mapped_column(Text)
    weight_kg: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(Text)  # manual | garmin | mock
    note: Mapped[str | None] = mapped_column(Text)


class FoodCache(Base):
    __tablename__ = "food_cache"
    __table_args__ = (
        UniqueConstraint("api_source", "external_id", name="uq_food_source_ext"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    api_source: Mapped[str] = mapped_column(Text)  # off | usda | custom
    external_id: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    brand: Mapped[str | None] = mapped_column(Text)
    kcal_per_100g: Mapped[float | None] = mapped_column(Float)
    protein_g: Mapped[float | None] = mapped_column(Float)
    carbs_g: Mapped[float | None] = mapped_column(Float)
    fat_g: Mapped[float | None] = mapped_column(Float)
    serving_size_g: Mapped[float | None] = mapped_column(Float)
    serving_size_text: Mapped[str | None] = mapped_column(Text)
    micronutrients_json: Mapped[str | None] = mapped_column(Text)
    raw_json: Mapped[str | None] = mapped_column(Text)
    cached_at: Mapped[str] = mapped_column(Text)
    is_favorite: Mapped[int] = mapped_column(Integer, default=0)


class FoodLog(Base):
    __tablename__ = "food_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(Text, index=True)
    ts: Mapped[str] = mapped_column(Text)
    meal: Mapped[str] = mapped_column(Text)  # breakfast | lunch | dinner | snack
    food_cache_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("food_cache.id")
    )
    description: Mapped[str | None] = mapped_column(Text)
    quantity_g: Mapped[float | None] = mapped_column(Float)
    calories: Mapped[float] = mapped_column(Float)
    protein_g: Mapped[float | None] = mapped_column(Float)
    carbs_g: Mapped[float | None] = mapped_column(Float)
    fat_g: Mapped[float | None] = mapped_column(Float)
    logging_complete_day: Mapped[int] = mapped_column(Integer, default=1)
    source: Mapped[str] = mapped_column(Text, default="manual")  # manual | myfitnesspal


class DailyCheckin(Base):
    """One row per date; row presence = daily check-in completed."""

    __tablename__ = "daily_checkin"

    date: Mapped[str] = mapped_column(Text, primary_key=True)  # YYYY-MM-DD
    ts: Mapped[str] = mapped_column(Text)  # last-updated iso
    mood: Mapped[int | None] = mapped_column(Integer)  # 1-5
    alcohol_units: Mapped[float] = mapped_column(Float, default=0)
    caffeine_cups: Mapped[float] = mapped_column(Float, default=0)
    caffeine_last_time: Mapped[str | None] = mapped_column(Text)  # "HH:MM"
    illness: Mapped[int] = mapped_column(Integer, default=0)
    eating_start: Mapped[str | None] = mapped_column(Text)  # "HH:MM" override
    eating_end: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)


class ContextLog(Base):
    __tablename__ = "context_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(Text, index=True)
    ts: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(Text)  # alcohol|caffeine|mood|illness|supplement|note
    value: Mapped[float | None] = mapped_column(Float)
    label: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)


class Exercise(Base):
    __tablename__ = "exercises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, unique=True)
    category: Mapped[str] = mapped_column(Text)  # push | pull | legs | core | other
    equipment: Mapped[str | None] = mapped_column(Text)
    is_custom: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(Text)
    primary_muscles: Mapped[str | None] = mapped_column(Text)  # JSON array
    secondary_muscles: Mapped[str | None] = mapped_column(Text)  # JSON array


class WorkoutSet(Base):
    __tablename__ = "workout_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    activity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("activities.id"), index=True
    )
    exercise_id: Mapped[int] = mapped_column(Integer, ForeignKey("exercises.id"))
    set_number: Mapped[int] = mapped_column(Integer)
    reps: Mapped[int] = mapped_column(Integer)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    rpe: Mapped[float | None] = mapped_column(Float)
    note: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text, default="manual")  # manual | garmin
    is_warmup: Mapped[int] = mapped_column(Integer, default=0)


class Routine(Base):
    __tablename__ = "routines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, unique=True)
    created_at: Mapped[str] = mapped_column(Text)
    last_used_at: Mapped[str | None] = mapped_column(Text)


class RoutineExercise(Base):
    __tablename__ = "routine_exercises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    routine_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("routines.id", ondelete="CASCADE"), index=True
    )
    exercise_id: Mapped[int] = mapped_column(Integer, ForeignKey("exercises.id"))
    position: Mapped[int] = mapped_column(Integer)
    target_sets: Mapped[int] = mapped_column(Integer, default=3)


class ActivityLap(Base):
    __tablename__ = "activity_laps"
    __table_args__ = (
        UniqueConstraint("activity_id", "lap_index", name="uq_lap_activity_index"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    activity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("activities.id"), index=True
    )
    lap_index: Mapped[int] = mapped_column(Integer)
    duration_s: Mapped[float | None] = mapped_column(Float)
    distance_km: Mapped[float | None] = mapped_column(Float)
    avg_hr: Mapped[int | None] = mapped_column(Integer)
    avg_speed_mps: Mapped[float | None] = mapped_column(Float)
    elevation_gain_m: Mapped[float | None] = mapped_column(Float)


class ActivityHrZone(Base):
    __tablename__ = "activity_hr_zones"
    __table_args__ = (
        UniqueConstraint("activity_id", "zone_number", name="uq_hrzone_activity_zone"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    activity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("activities.id"), index=True
    )
    zone_number: Mapped[int] = mapped_column(Integer)
    secs_in_zone: Mapped[float | None] = mapped_column(Float)
    zone_low_boundary: Mapped[int | None] = mapped_column(Integer)


class ActivityTimeSeries(Base):
    __tablename__ = "activity_timeseries"

    activity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("activities.id"), primary_key=True
    )
    fetched_at: Mapped[str] = mapped_column(Text)
    data_json: Mapped[str] = mapped_column(Text)


class UserSetting(Base):
    __tablename__ = "user_settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text)


class BloodPanel(Base):
    __tablename__ = "blood_panels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(Text, index=True)
    lab_name: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text)


class BloodResult(Base):
    __tablename__ = "blood_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    panel_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("blood_panels.id", ondelete="CASCADE"), index=True
    )
    marker: Mapped[str] = mapped_column(Text)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(Text)
    ref_low: Mapped[float | None] = mapped_column(Float)
    ref_high: Mapped[float | None] = mapped_column(Float)


class AIReport(Base):
    __tablename__ = "ai_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)  # weekly | on_demand
    model: Mapped[str] = mapped_column(Text)
    period_start: Mapped[str] = mapped_column(Text)
    period_end: Mapped[str] = mapped_column(Text)
    report_md: Mapped[str] = mapped_column(Text)
    summary_json: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="ok")
    error: Mapped[str | None] = mapped_column(Text)


class SyncLog(Base):
    __tablename__ = "sync_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[str] = mapped_column(Text)
    finished_at: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    days_requested: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text)  # ok | error
    error: Mapped[str | None] = mapped_column(Text)
    metrics_synced: Mapped[int | None] = mapped_column(Integer)
    sleeps_synced: Mapped[int | None] = mapped_column(Integer)
    activities_synced: Mapped[int | None] = mapped_column(Integer)
    weights_synced: Mapped[int | None] = mapped_column(Integer)


class IntradayBodyBattery(Base):
    __tablename__ = "intraday_body_battery"
    __table_args__ = (UniqueConstraint("date", "timestamp", name="uq_ibb_date_ts"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(Text, index=True)
    timestamp: Mapped[str] = mapped_column(Text)
    body_battery: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(Text)


class IntradayStress(Base):
    __tablename__ = "intraday_stress"
    __table_args__ = (UniqueConstraint("date", "timestamp", name="uq_ist_date_ts"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(Text, index=True)
    timestamp: Mapped[str] = mapped_column(Text)
    stress_level: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(Text)


class AIChatSession(Base):
    """One saved agent conversation."""

    __tablename__ = "ai_chat_session"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[str] = mapped_column(Text, index=True)
    title: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str | None] = mapped_column(Text)  # base URL at creation
    message_count: Mapped[int] = mapped_column(Integer, default=0)


class AIChatMessage(Base):
    """A message in the provider's wire format, stored faithfully enough to
    replay: an assistant message's tool_calls[].id must still pair with the
    tool_call_id of the tool message that answers it."""

    __tablename__ = "ai_chat_message"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ai_chat_session.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(Text)  # user | assistant | tool
    content: Mapped[str | None] = mapped_column(Text)
    tool_calls_json: Mapped[str | None] = mapped_column(Text)
    tool_call_id: Mapped[str | None] = mapped_column(Text)
    tool_name: Mapped[str | None] = mapped_column(Text)
    trace_summary: Mapped[str | None] = mapped_column(Text)
    token_estimate: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[str] = mapped_column(Text)


class AIPendingAction(Base):
    """A write the agent has drafted but not performed.

    The agent never writes to weight_log / food_log / context_log itself; it puts
    a row here and the user confirms it. `status` is what makes a confirm
    idempotent - a second confirm has nothing left to act on."""

    __tablename__ = "ai_pending_action"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ai_chat_session.id", ondelete="CASCADE"), index=True
    )
    message_id: Mapped[int | None] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(Text)  # log_weight | log_food | log_context
    payload_json: Mapped[str] = mapped_column(Text)
    summary_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="pending")  # pending|confirmed|rejected
    created_at: Mapped[str] = mapped_column(Text)
    resolved_at: Mapped[str | None] = mapped_column(Text)
    resolved_result_json: Mapped[str | None] = mapped_column(Text)


class LiteratureCache(Base):
    """Europe PMC search results, cached so repeat questions cost no round-trip.

    Only the query string is ever sent to Europe PMC - never health data."""

    __tablename__ = "literature_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    query_norm: Mapped[str] = mapped_column(Text, unique=True, index=True)
    results_json: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[str] = mapped_column(Text)
