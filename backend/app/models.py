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
    source: Mapped[str] = mapped_column(Text)
    synced_at: Mapped[str] = mapped_column(Text)


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
    raw_json: Mapped[str | None] = mapped_column(Text)
    cached_at: Mapped[str] = mapped_column(Text)


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


class ContextLog(Base):
    __tablename__ = "context_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(Text, index=True)
    ts: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(Text)  # alcohol|caffeine|mood|illness|supplement|note
    value: Mapped[float | None] = mapped_column(Float)
    label: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)


class SyncLog(Base):
    __tablename__ = "sync_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[str] = mapped_column(Text)
    finished_at: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    days_requested: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text)  # ok | error
    error: Mapped[str | None] = mapped_column(Text)
