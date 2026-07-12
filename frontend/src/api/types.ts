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

export interface ReadinessComponent {
  key: string
  label: string
  value: number
  baseline: number | null
  points: number
  max_points: number
}

export interface Readiness {
  status: 'green' | 'amber' | 'red' | 'building_baseline' | 'no_data'
  label: string
  score_pct: number | null
  baseline_days: number
  components: ReadinessComponent[]
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
  readiness: Readiness
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
  is_favorite: number
  last_quantity_g?: number | null
  last_meal?: string | null
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

// ---- v3: workouts ----

export interface Workout {
  id: number
  external_id: string
  date: string
  start_ts: string | null
  type: string | null
  name: string | null
  duration_min: number | null
  distance_km: number | null
  calories: number | null
  avg_hr: number | null
  max_hr: number | null
  moving_duration_min: number | null
  elevation_gain_m: number | null
  avg_speed_mps: number | null
  max_speed_mps: number | null
  aerobic_te: number | null
  anaerobic_te: number | null
  training_effect_label: string | null
  training_load: number | null
  vo2max: number | null
  avg_run_cadence: number | null
  total_sets: number | null
  total_reps: number | null
  total_volume_kg: number | null
  lap_count: number | null
}

export interface Exercise {
  id: number
  name: string
  category: string
  equipment: string | null
  is_custom: number
}

export interface WorkoutSetRow {
  id: number
  activity_id: number
  exercise_id: number
  set_number: number
  reps: number
  weight_kg: number | null
  rpe: number | null
  note: string | null
  source: string
  exercise_name: string
  e1rm: number | null
  is_pr: boolean
}

export interface WorkoutDetail {
  activity: Workout
  sets: WorkoutSetRow[]
  tonnage_kg: number
}

export interface Lap {
  lap_index: number
  duration_s: number | null
  distance_km: number | null
  avg_hr: number | null
  avg_speed_mps: number | null
  elevation_gain_m: number | null
}

export interface HrZone {
  zone_number: number
  secs_in_zone: number | null
  zone_low_boundary: number | null
}

export interface WeeklyVolume {
  week: string
  sets: number
  tonnage_kg: number
  by_category: Record<string, { sets: number; tonnage_kg: number }>
}

export interface ExerciseHistoryPoint {
  date: string
  sets: number
  volume_kg: number
  best_e1rm: number | null
  best_weight: number | null
  top_set: string | null
}

export interface StrengthAnalytics {
  weekly_volume: WeeklyVolume[]
  history?: ExerciseHistoryPoint[]
  prs?: {
    best_e1rm: { e1rm: number; weight_kg: number; reps: number; date: string } | null
    rep_prs: { reps: number; weight_kg: number; date: string }[]
  }
}

export interface CardioWeekly {
  week: string
  count: number
  distance_km: number
  duration_min: number
  load: number
  elevation_m: number
}

export interface PacePoint {
  date: string
  id: number
  name: string | null
  distance_km: number
  pace_min_per_km: number
  speed_kmh: number
  avg_hr: number | null
}

export interface LoadDay {
  date: string
  load: number
  acute_7d: number
  chronic_28d: number
  acr: number | null
}

export interface CorrelationInsight {
  id: string
  title: string
  kind: 'binary' | 'continuous'
  n: number
  n_exposed: number | null
  effect: number | null
  effect_type: 'cohens_d' | 'pearson_r'
  mean_diff: number | null
  unit: string
  direction: 'lower' | 'higher' | 'none' | null
  strength: 'strong' | 'moderate' | 'weak' | 'tentative' | 'none' | null
  summary_line: string | null
  status: 'ok' | 'insufficient_data'
  needed: number | null
}

export interface CorrelationsResponse {
  days: number
  note: string
  insights: CorrelationInsight[]
}

export interface CardioAnalytics {
  weekly: CardioWeekly[]
  load: { series: LoadDay[]; sufficient_history: boolean; history_days: number }
  pace_trend?: PacePoint[]
}
