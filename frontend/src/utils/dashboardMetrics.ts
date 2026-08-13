/**
 * Which metric tiles appear along the top of the home page, and in what order.
 *
 * Stored in localStorage, which means an existing install already has a saved
 * list that predates any metric added later. Bumping STORAGE_KEY and migrating
 * the old value appends new metrics once, without discarding the user's
 * enable/disable and ordering choices.
 */

export const ALL_METRICS = [
  'hrv',
  'sleep_score',
  'calories_out',
  'steps',
  'resting_hr',
  'body_battery',
  'weight',
] as const

export type MetricKey = (typeof ALL_METRICS)[number]

export const DEFAULT_METRICS: string[] = [...ALL_METRICS]

const STORAGE_KEY = 'dashboard-metrics-config-v2'
const LEGACY_KEY = 'dashboard-metrics-config'

/** Metrics introduced after the legacy key was written, appended on migration. */
const ADDED_SINCE_LEGACY = ['weight']

function parse(raw: string | null): string[] | null {
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.filter((k) => typeof k === 'string') : null
  } catch {
    return null
  }
}

export function loadMetricsConfig(): string[] {
  const current = parse(localStorage.getItem(STORAGE_KEY))
  if (current) return current

  const legacy = parse(localStorage.getItem(LEGACY_KEY))
  if (legacy) {
    const migrated = [...legacy, ...ADDED_SINCE_LEGACY.filter((k) => !legacy.includes(k))]
    saveMetricsConfig(migrated)
    return migrated
  }
  return DEFAULT_METRICS
}

export function saveMetricsConfig(keys: string[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(keys))
}
