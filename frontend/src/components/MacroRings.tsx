interface Targets {
  calorie_target: number | null
  protein_target_g: number | null
  carbs_target_g: number | null
  fat_target_g: number | null
}

interface Totals {
  calories: number
  protein_g: number
  carbs_g: number
  fat_g: number
}

function Bar({ label, value, target, color, unit }: { label: string; value: number; target: number | null; color: string; unit: string }) {
  const pct = target ? Math.min(100, (value / target) * 100) : 0
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem' }}>
        <span className="muted">{label}</span>
        <span>
          {Math.round(value)}
          {target ? ` / ${Math.round(target)}` : ''} {unit}
        </span>
      </div>
      <div style={{ background: '#334155', borderRadius: 4, height: 6, marginTop: 3 }}>
        <div
          style={{
            width: `${target ? pct : 0}%`,
            background: pct >= 100 ? '#f87171' : color,
            height: 6,
            borderRadius: 4,
            transition: 'width 0.3s',
          }}
        />
      </div>
    </div>
  )
}

export default function MacroRings({ totals, targets }: { totals: Totals; targets: Targets | undefined }) {
  return (
    <div className="card">
      <Bar label="Calories" value={totals.calories} target={targets?.calorie_target ?? null} color="#38bdf8" unit="kcal" />
      <Bar label="Protein" value={totals.protein_g} target={targets?.protein_target_g ?? null} color="#4ade80" unit="g" />
      <Bar label="Carbs" value={totals.carbs_g} target={targets?.carbs_target_g ?? null} color="#fbbf24" unit="g" />
      <Bar label="Fat" value={totals.fat_g} target={targets?.fat_target_g ?? null} color="#a78bfa" unit="g" />
      {!targets?.calorie_target && (
        <p className="muted" style={{ margin: 0 }}>
          Set targets in Settings to track progress.
        </p>
      )}
    </div>
  )
}
