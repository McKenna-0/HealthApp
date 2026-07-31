import { Coffee, Sun, Moon, Cookie } from 'lucide-react'
import type { FoodLogRow, Meal } from '../api/types'
import SwipeToDelete from './SwipeToDelete'

const MEAL_ICONS: Record<Meal, React.ReactNode> = {
  breakfast: <Coffee size={18} />,
  lunch: <Sun size={18} />,
  dinner: <Moon size={18} />,
  snack: <Cookie size={18} />,
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

  return (
    <div className="card meal-card" style={{ marginTop: 12, padding: 0, overflow: 'hidden' }}>
      {/* Header row */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '12px 16px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ color: 'var(--accent)', display: 'flex', alignItems: 'center' }}>
            {MEAL_ICONS[meal]}
          </span>
          <div>
            <div className="text-body" style={{ fontWeight: 600 }}>{MEAL_LABELS[meal]}</div>
            {entries.length > 0 && (
              <div className="text-caption" style={{ color: 'var(--muted)' }}>
                {Math.round(kcal)} cal · {entries.length} item{entries.length !== 1 ? 's' : ''}
              </div>
            )}
          </div>
        </div>
        <button
          onClick={onLog}
          style={{
            minWidth: 44,
            minHeight: 44,
            padding: '0 14px',
            borderRadius: 10,
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            color: 'var(--accent)',
            fontWeight: 600,
            fontSize: '0.85rem',
          }}
        >
          + Log
        </button>
      </div>

      {/* Entries */}
      {entries.length > 0 && (
        <div style={{ borderTop: '1px solid var(--border)' }}>
          {entries.map((e) => (
            <SwipeToDelete key={e.id} onDelete={() => onDelete(e.id)}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '10px 16px',
                  borderBottom: '1px solid var(--border)',
                  background: 'var(--card)',
                  cursor: onEdit && e.food_cache_id ? 'pointer' : 'default',
                }}
                onClick={onEdit && e.food_cache_id ? () => onEdit(e) : undefined}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="text-body" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {e.description ?? 'Food'}
                    {e.source === 'myfitnesspal' && (
                      <span style={{ fontSize: '0.65rem', color: 'var(--muted)', marginLeft: 6, fontWeight: 500 }}>MFP</span>
                    )}
                  </div>
                  {e.quantity_g != null && (
                    <div className="text-caption" style={{ color: 'var(--muted)' }}>{e.quantity_g}g</div>
                  )}
                </div>
                <div className="text-caption" style={{ color: 'var(--muted)', marginLeft: 12, whiteSpace: 'nowrap' }}>
                  {Math.round(e.calories)} cal
                </div>
              </div>
            </SwipeToDelete>
          ))}
        </div>
      )}
    </div>
  )
}
