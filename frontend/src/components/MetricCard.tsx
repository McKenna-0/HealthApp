import type { ReactNode } from 'react'

/**
 * Builds a polyline for a fixed 140x22 viewBox. Drawn as raw SVG rather than a
 * Recharts instance: there are up to seven of these on the dashboard, and
 * Recharts costs a ResponsiveContainer observer each.
 */
function sparkPoints(values: number[]): string | null {
  if (values.length < 3) return null
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  const step = 140 / (values.length - 1)
  return values
    .map((v, i) => `${(i * step).toFixed(1)},${(20 - ((v - min) / span) * 18).toFixed(1)}`)
    .join(' ')
}

export default function MetricCard({
  icon,
  label,
  value,
  unit,
  sub,
  delta,
  deltaColor,
  deltaText,
  spark,
  onClick,
}: {
  icon?: ReactNode
  label: string
  value: string | number | null
  unit?: string
  sub?: string
  delta?: { value: number; suffix?: string }
  /** Overrides "up is good": for weight, whether a rise is good depends on the goal. */
  deltaColor?: string
  /** Overrides the rendered delta text, e.g. to control decimal places. */
  deltaText?: string
  /** Recent history, oldest first. Nulls are dropped before plotting. */
  spark?: (number | null | undefined)[]
  onClick?: () => void
}) {
  const resolvedDeltaColor = delta
    ? deltaColor ?? (
      delta.value > 0 ? 'var(--green)'
      : delta.value < 0 ? 'var(--red)'
      : 'var(--muted)'
    )
    : undefined

  const points = spark ? sparkPoints(spark.filter((v): v is number => v != null)) : null

  const body = (
    <>
      <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
        {icon && <span style={{ color: 'var(--dim)', display: 'flex' }}>{icon}</span>}
        <span
          className="label"
          style={{ fontSize: '0.625rem', fontWeight: 700, letterSpacing: '0.1em' }}
        >
          {label}
        </span>
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 4, margin: '3px 0 2px' }}>
        <span
          className="value"
          style={{ fontSize: '1.5rem', letterSpacing: '-0.02em', margin: 0 }}
        >
          {value ?? '–'}
        </span>
        {unit && <span style={{ fontSize: '0.7rem', color: 'var(--muted)' }}>{unit}</span>}
        {delta && (
          <span style={{ marginLeft: 'auto', fontSize: '0.7rem', fontWeight: 600, color: resolvedDeltaColor }}>
            {deltaText ?? `${delta.value > 0 ? '+' : ''}${delta.value}${delta.suffix || ''}`}
          </span>
        )}
      </div>
      {points ? (
        <svg width="100%" height="22" viewBox="0 0 140 22" preserveAspectRatio="none" fill="none" aria-hidden="true">
          <polyline
            points={points}
            stroke={resolvedDeltaColor ?? 'var(--accent)'}
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            vectorEffect="non-scaling-stroke"
          />
        </svg>
      ) : (
        <div style={{ height: 22 }} />
      )}
      {sub && <div className="sub">{sub}</div>}
    </>
  )

  // A real <button> so the tile is reachable by keyboard and announced as a
  // control; a div with onClick is skipped by Tab entirely.
  return onClick ? (
    <button
      type="button"
      className="metric-card"
      onClick={onClick}
      style={{ width: '100%', textAlign: 'left', font: 'inherit', color: 'var(--text)' }}
    >
      {body}
    </button>
  ) : (
    <div className="metric-card">{body}</div>
  )
}
