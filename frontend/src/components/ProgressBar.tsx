export default function ProgressBar({
  value,
  target,
  color = 'var(--accent)',
}: {
  value: number
  target: number | null | undefined
  color?: string
}) {
  const pct = target ? Math.min((value / target) * 100, 100) : 0
  const over = target != null && value > target
  return (
    <div className="progress-track">
      <div
        className={`progress-fill ${over ? 'over' : ''}`}
        style={{ width: `${target ? pct : 0}%`, background: over ? undefined : color }}
      />
    </div>
  )
}
