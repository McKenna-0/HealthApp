import type { ReactNode } from 'react'

export default function MetricCard({
  icon,
  label,
  value,
  sub,
  delta,
  onClick,
}: {
  icon?: ReactNode
  label: string
  value: string | number | null
  sub?: string
  delta?: { value: number; suffix?: string }
  onClick?: () => void
}) {
  const deltaColor = delta
    ? delta.value > 0 ? 'var(--green)'
    : delta.value < 0 ? 'var(--red)'
    : 'var(--muted)'
    : undefined

  return (
    <div
      className="metric-card"
      onClick={onClick}
      style={onClick ? { cursor: 'pointer' } : undefined}
    >
      {icon && <div style={{ color: 'var(--muted)', marginBottom: 4 }}>{icon}</div>}
      <div className="text-caption" style={{ textTransform: 'uppercase', letterSpacing: '0.5px' }}>
        {label}
      </div>
      <div className="text-display" style={{ fontSize: '1.25rem', margin: '4px 0 2px' }}>
        {value ?? '–'}
      </div>
      {delta && (
        <div style={{ fontSize: '0.72rem', color: deltaColor }}>
          {delta.value > 0 ? '+' : ''}{delta.value}{delta.suffix || ''}
        </div>
      )}
      {sub && <div className="text-caption">{sub}</div>}
    </div>
  )
}
