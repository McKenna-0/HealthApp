export interface DashboardDay {
  date: string
  steps: number | null
  steps_7d: number | null
  resting_hr: number | null
  hrv: number | null
  stress_avg: number | null
  body_battery_high: number | null
  sleep_score: number | null
  sleep_duration_min: number | null
  weight: number | null
  weight_trend: number | null
  calories_in: number | null
  calories_out: number | null
  balance: number | null
}

export interface TdeeResult {
  tdee: number | null
  reason: string | null
  window_days: number
  valid_logged_days: number
  weight_points: number
  mean_intake?: number
  weight_slope_kg_per_week?: number
  garmin_mean_calories_out?: number | null
}

export interface Dashboard {
  start: string
  end: string
  series: DashboardDay[]
  averages_7d: {
    steps: number | null
    resting_hr: number | null
    hrv: number | null
    sleep_score: number | null
  }
  tdee: TdeeResult
}

export interface SleepRow {
  date: string
  start_ts: string | null
  end_ts: string | null
  duration_min: number | null
  deep_min: number | null
  light_min: number | null
  rem_min: number | null
  awake_min: number | null
  sleep_score: number | null
  avg_overnight_hrv: number | null
}

export interface WeightTrendPoint {
  date: string
  weight: number | null
  trend: number | null
}

export interface EnergyBalanceDay {
  date: string
  calories_in: number | null
  calories_out: number | null
  balance: number | null
  valid: boolean
  balance_7d_avg: number | null
}

export interface WeightRow {
  id: number
  date: string
  ts: string
  weight_kg: number
  source: string
  note: string | null
}

export interface FoodItem {
  id: number
  api_source: string
  external_id: string
  name: string
  brand: string | null
  kcal_per_100g: number | null
  protein_g: number | null
  carbs_g: number | null
  fat_g: number | null
  serving_size_g: number | null
}

export interface FoodLogRow {
  id: number
  date: string
  ts: string
  meal: string
  food_cache_id: number | null
  description: string | null
  quantity_g: number | null
  calories: number
  protein_g: number | null
  carbs_g: number | null
  fat_g: number | null
  logging_complete_day: number
}

export interface ContextRow {
  id: number
  date: string
  ts: string
  type: string
  value: number | null
  label: string | null
  note: string | null
}

export interface SyncLogRow {
  id: number
  started_at: string
  finished_at: string | null
  source: string
  days_requested: number
  status: string
  error: string | null
}

export interface HealthStatus {
  status: string
  data_source: string
  tz: string
}
