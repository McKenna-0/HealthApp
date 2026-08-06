export default function ProgressBar({
  value,
  target,
  bonus = 0,
  color = 'var(--accent)',
  bonusColor = `color-mix(in srgb, ${color} 45%, transparent)`,
}: {
  value: number
  /** Base target — the configured allowance, before any active-calorie bonus. */
  target: number | null | undefined
  /** Extra allowance earned from active calories, drawn as a second segment. */
  bonus?: number
  color?: string
  /** Colour of the bonus segment; defaults to a lighter wash of `color`. */
  bonusColor?: string
}) {
  const total = target ? target + bonus : 0
  const over = total > 0 && value > total
  // Fill the base segment first, then spill into the earned bonus segment.
  const basePct = total ? (Math.min(value, target ?? 0) / total) * 100 : 0
  const bonusPct = total ? (Math.min(Math.max(value - (target ?? 0), 0), bonus) / total) * 100 : 0

  return (
    <div
      style={{
        display: 'flex',
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
          width: `${over ? 100 : basePct}%`,
          background: over ? 'var(--red)' : color,
          transition: 'width 0.3s ease',
        }}
      />
      {!over && bonusPct > 0 && (
        <div
          style={{
            height: '100%',
            width: `${bonusPct}%`,
            background: bonusColor,
            transition: 'width 0.3s ease',
          }}
        />
      )}
    </div>
  )
}
