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
    <div
      style={{
        height: 5,
        borderRadius: 99,
        background: 'var(--border)',
        overflow: 'hidden',
        marginTop: 3,
      }}
    >
      <div
        style={{
          height: '100%',
          borderRadius: 99,
          width: `${target ? pct : 0}%`,
          background: over ? 'var(--red)' : color,
          transition: 'width 0.3s ease',
        }}
      />
    </div>
  )
}
