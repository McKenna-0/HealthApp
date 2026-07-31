const COLORS = { carbs: 'var(--amber)', fat: '#a78bfa', protein: 'var(--green)' }
const RADIUS = 54
const STROKE = 12
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

export default function CalorieDonut({
  calories,
  protein_g,
  carbs_g,
  fat_g,
  size = 120,
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
    { key: 'carbs', kcal: c, grams: carbs_g ?? 0, label: 'C', color: COLORS.carbs },
    { key: 'fat', kcal: f, grams: fat_g ?? 0, label: 'F', color: COLORS.fat },
    { key: 'protein', kcal: p, grams: protein_g ?? 0, label: 'P', color: COLORS.protein },
  ]

  let offset = 0
  const viewBox = `0 0 ${RADIUS * 2 + STROKE} ${RADIUS * 2 + STROKE}`
  const center = RADIUS + STROKE / 2

  return (
    <svg width={size} height={size} viewBox={viewBox}>
      {/* Track */}
      <circle cx={center} cy={center} r={RADIUS} fill="none" stroke="var(--border)" strokeWidth={STROKE} />
      {/* Segments */}
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
      {/* Center text */}
      <text x={center} y={center - 5} textAnchor="middle" fill="var(--text)" fontSize="18" fontWeight="700">
        {Math.round(calories)}
      </text>
      <text x={center} y={center + 12} textAnchor="middle" fill="var(--muted)" fontSize="9" fontWeight="500">
        kcal
      </text>
    </svg>
  )
}
