/**
 * Which metric tiles appear along the top of the home page, and in what order.
 *
 * Stored in localStorage, which means an existing install already has a saved
 * list that predates any metric added later. The previous scheme bumped
 * STORAGE_KEY and appended a hardcoded list of "metrics added since", which had
 * to be edited by hand for every new tile — miss that step and the tile is
 * simply invisible on every install that already has a saved config, while
 * looking fine on a fresh one. That is how the weight tile went missing.
 *
 * Instead of a version bump, the stored value records which metrics the user
 * has actually been *offered*. Anything in ALL_METRICS they have never been
 * offered is appended once, so a new tile shows up on its own; anything they
 * were offered and switched off stays off.
 */

// Order matters: the home row scroll-snaps horizontally and only about three
// tiles fit across 390px, so anything past the third is invisible until the
// user thinks to swipe. Weight leads because the goal-tracking tile is the one
// the user checks daily; the row is reorderable in Settings.
export const ALL_METRICS = [
  'weight',
  'hrv',
  'sleep_score',
  'calories_out',
  'steps',
  'resting_hr',
  'body_battery',
] as const

export type MetricKey = (typeof ALL_METRICS)[number]

export const DEFAULT_METRICS: string[] = [...ALL_METRICS]

const STORAGE_KEY = 'dashboard-metrics-config-v3'
/** Keys written by earlier builds, read once so ordering choices survive. */
const PRIOR_KEYS = ['dashboard-metrics-config-v2', 'dashboard-metrics-config']

interface StoredConfig {
  enabled: string[]
  /** Every metric this install has been offered, enabled or not. */
  seen: string[]
}

function parseStringArray(value: unknown): string[] | null {
  return Array.isArray(value) ? value.filter((k): k is string => typeof k === 'string') : null
}

function readKey(key: string): unknown {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

/** Reads whichever shape is on disk: the v3 object, or a bare array from before it. */
function readStored(): StoredConfig | null {
  const current = readKey(STORAGE_KEY)
  if (current && typeof current === 'object' && !Array.isArray(current)) {
    const enabled = parseStringArray((current as { enabled?: unknown }).enabled)
    if (enabled) {
      return { enabled, seen: parseStringArray((current as { seen?: unknown }).seen) ?? enabled }
    }
  }

  for (const key of [STORAGE_KEY, ...PRIOR_KEYS]) {
    const legacy = parseStringArray(readKey(key))
    // An older build only recorded what was enabled, so that list is also the
    // most we can claim the user was ever offered.
    if (legacy) return { enabled: legacy, seen: legacy }
  }
  return null
}

export function loadMetricsConfig(): string[] {
  const stored = readStored()
  if (!stored) return DEFAULT_METRICS

  const known = stored.enabled.filter((k) => (ALL_METRICS as readonly string[]).includes(k))
  const unoffered = (ALL_METRICS as readonly string[]).filter(
    (k) => !stored.seen.includes(k) && !known.includes(k),
  )
  // Newly offered metrics go first, not last: appending them to a row that
  // already overflows the screen is indistinguishable from not adding them.
  const enabled = [...unoffered, ...known]

  // Persist so the append happens once; without this a metric the user turns
  // off would reappear on the next load.
  if (unoffered.length > 0 || known.length !== stored.enabled.length) {
    saveMetricsConfig(enabled)
  }
  return enabled
}

export function saveMetricsConfig(keys: string[]) {
  const config: StoredConfig = { enabled: keys, seen: [...ALL_METRICS] }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(config))
}
