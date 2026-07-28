const COLORS = { carbs: '#fbbf24', fat: '#a78bfa', protein: '#4ade80' }
const RADIUS = 54
const STROKE = 12
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

export default function CalorieDonut({
  calories,
  protein_g,
  carbs_g,
  fat_g,
  size = 160,
}: {
  calories: number
  protein_g: number | null
  carbs_g: number | null
  fat_g: number | null
  size?: number
}) {
  const p = (protein_g ?? 0) * 4
  const c = (carbs_g ?? 0) * 4
  const f = (fat_g ?? 0) * 9
  const total = p + c + f || 1

  const segments = [
    { key: 'carbs', kcal: c, grams: carbs_g ?? 0, label: 'Carbs', color: COLORS.carbs },
    { key: 'fat', kcal: f, grams: fat_g ?? 0, label: 'Fat', color: COLORS.fat },
    { key: 'protein', kcal: p, grams: protein_g ?? 0, label: 'Protein', color: COLORS.protein },
  ]

  let offset = 0
  const viewBox = `0 0 ${RADIUS * 2 + STROKE} ${RADIUS * 2 + STROKE}`
  const center = RADIUS + STROKE / 2

  return (
    <div className="donut-container">
      <svg width={size} height={size} viewBox={viewBox}>
        <circle cx={center} cy={center} r={RADIUS} fill="none" stroke="var(--card)" strokeWidth={STROKE} />
        {segments.map((s) => {
          const pct = s.kcal / total
          const dash = CIRCUMFERENCE * pct
          const gap = CIRCUMFERENCE - dash
          const rot = offset * 360 - 90
          offset += pct
          if (pct < 0.005) return null
          return (
            <circle
              key={s.key}
              cx={center}
              cy={center}
              r={RADIUS}
              fill="none"
              stroke={s.color}
              strokeWidth={STROKE}
              strokeDasharray={`${dash} ${gap}`}
              transform={`rotate(${rot} ${center} ${center})`}
              strokeLinecap="round"
            />
          )
        })}
        <text x={center} y={center - 6} textAnchor="middle" fill="var(--text)" fontSize="20" fontWeight="700">
          {Math.round(calories)}
        </text>
        <text x={center} y={center + 12} textAnchor="middle" fill="var(--muted)" fontSize="10">
          cal
        </text>
      </svg>
      <div className="macro-legend">
        {segments.map((s) => (
          <div key={s.key} className="macro-legend-item">
            <span className="macro-dot" style={{ background: s.color }} />
            <span className="macro-legend-pct">{Math.round((s.kcal / total) * 100)}%</span>
            <span className="macro-legend-label">{s.label}</span>
            <span className="macro-legend-val">{s.grams.toFixed(1)}g</span>
          </div>
        ))}
      </div>
    </div>
  )
}
