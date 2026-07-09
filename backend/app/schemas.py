from pydantic import BaseModel, ConfigDict, Field


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


class SyncLogOut(ORMModel):
    id: int
    started_at: str
    finished_at: str | None
    source: str
    days_requested: int
    status: str
    error: str | None


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


class FoodLogUpdate(BaseModel):
    meal: str | None = Field(default=None, pattern="^(breakfast|lunch|dinner|snack)$")
    quantity_g: float | None = Field(default=None, gt=0)
    calories: float | None = Field(default=None, ge=0)
    description: str | None = None
    logging_complete_day: int | None = Field(default=None, ge=0, le=1)


class ContextIn(BaseModel):
    date: str
    type: str = Field(pattern="^(alcohol|caffeine|mood|illness|supplement|note)$")
    value: float | None = None
    label: str | None = None
    note: str | None = None
