import type { RateStatus } from '../api/types'

/**
 * How each rate-of-change verdict is named and coloured.
 *
 * Colour is never the only signal: every place these are drawn also shows the
 * label, so the chart is readable in greyscale and to a colourblind reader.
 */
export const STATUS_META: Record<RateStatus, { label: string; color: string }> = {
  on_track: { label: 'On track', color: 'var(--green)' },
  too_slow: { label: 'Behind plan', color: 'var(--amber)' },
  too_fast: { label: 'Too fast', color: 'var(--red)' },
  wrong_way: { label: 'Wrong way', color: 'var(--red)' },
}

export const STATUS_ORDER: RateStatus[] = ['on_track', 'too_slow', 'too_fast', 'wrong_way']

export function statusColor(status: RateStatus | null | undefined): string {
  return status ? STATUS_META[status].color : 'var(--muted)'
}

/** Signed weekly rate, e.g. "+0.28 kg/wk". */
export function formatRate(kgPerWeek: number | null | undefined): string {
  if (kgPerWeek == null) return '–'
  return `${kgPerWeek > 0 ? '+' : ''}${kgPerWeek.toFixed(2)} kg/wk`
}

/**
 * A sentence explaining the verdict, using the user's own numbers.
 * Every figure here comes from the API response — nothing is estimated here.
 */
export function statusExplanation(
  status: RateStatus,
  rate: number,
  goalRate: number | null,
  maxGain: number,
  maxLoss: number,
  tolerance: number,
): string {
  const r = formatRate(rate)
  if (goalRate == null || goalRate === 0) {
    return status === 'on_track'
      ? `Holding steady at ${r}, inside the ±${tolerance.toFixed(2)} kg/wk you'd expect from normal fluctuation.`
      : `Drifting at ${r}, more than the ±${tolerance.toFixed(2)} kg/wk that counts as holding steady.`
  }
  const goal = formatRate(goalRate)
  switch (status) {
    case 'on_track':
      return `${r} against a plan of ${goal} — moving the right way, at a rate that mostly changes the tissue you want.`
    case 'too_slow':
      return `${r} against a plan of ${goal} — right direction, under half the intended pace.`
    case 'too_fast':
      return goalRate > 0
        ? `${r} is past ${maxGain.toFixed(2)} kg/wk (0.5% of body weight). Above that, most of the extra is fat rather than muscle.`
        : `${r} is past ${maxLoss.toFixed(2)} kg/wk (1% of body weight). Cutting faster than that costs lean mass.`
    case 'wrong_way':
      return goalRate > 0
        ? `${r} — you're losing while the plan is to gain.`
        : `${r} — you're gaining while the plan is to lose.`
  }
}
