import type { FoodLogRow, Meal } from '../api/types'

const MEAL_ICONS: Record<Meal, string> = {
  breakfast: '☕',
  lunch: '🥪',
  dinner: '🍽️',
  snack: '🍪',
}

const MEAL_LABELS: Record<Meal, string> = {
  breakfast: 'Breakfast',
  lunch: 'Lunch',
  dinner: 'Dinner',
  snack: 'Snacks',
}

export default function MealCard({
  meal,
  entries,
  onLog,
  onDelete,
  onEdit,
}: {
  meal: Meal
  entries: FoodLogRow[]
  onLog: () => void
  onDelete: (id: number) => void
  onEdit?: (entry: FoodLogRow) => void
}) {
  const kcal = entries.reduce((a, e) => a + e.calories, 0)
  const first = entries[0]?.description ?? null
  return (
    <div className="card meal-card">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <div className="row" style={{ gap: 10, flex: 1 }}>
          <span style={{ fontSize: '1.2rem' }} className="fixed">
            {MEAL_ICONS[meal]}
          </span>
          <div>
            <strong>{MEAL_LABELS[meal]}</strong>
            {entries.length > 0 && (
              <div className="muted" style={{ fontSize: '0.78rem' }}>
                {first}
                {entries.length > 1 ? ` and ${entries.length - 1} more` : ''} · {Math.round(kcal)} cal
              </div>
            )}
          </div>
        </div>
        <button className="log-meal-btn fixed" onClick={onLog}>
          Log
        </button>
      </div>
      {entries.length > 0 && (
        <div className="meal-entries">
          {entries.map((e) => (
            <div key={e.id} className="list-item" style={{ padding: '6px 0' }}>
              <div
                className="main"
                style={onEdit && e.food_cache_id ? { cursor: 'pointer' } : undefined}
                onClick={onEdit && e.food_cache_id ? () => onEdit(e) : undefined}
              >
                <div className="detail" style={{ color: 'var(--text)' }}>
                  {e.description ?? 'Food'}
                </div>
                <div className="detail">
                  {e.quantity_g ? `${e.quantity_g}g · ` : ''}
                  {Math.round(e.calories)} cal
                </div>
              </div>
              <button className="del" onClick={() => onDelete(e.id)}>
                ✕
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
