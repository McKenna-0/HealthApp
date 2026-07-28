import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { apiDelete, apiGet, apiPost, apiPut } from '../api/client'
import type { CheckinResponse, FoodLogRow, Meal, StreakInfo } from '../api/types'
import MealCard from '../components/MealCard'
import ProgressBar from '../components/ProgressBar'
import StreakWeekRow from '../components/StreakWeekRow'

const MEALS: Meal[] = ['breakfast', 'lunch', 'dinner', 'snack']
const MOODS = ['😞', '😕', '😐', '🙂', '😄']

interface Targets {
  calorie_target: number | null
  protein_target_g: number | null
  carbs_target_g: number | null
  fat_target_g: number | null
}

function toIso(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function shiftDate(date: string, days: number) {
  const d = new Date(date)
  d.setDate(d.getDate() + days)
  return toIso(d)
}

function dateLabel(date: string) {
  const today = toIso(new Date())
  if (date === today) return 'Today'
  if (date === shiftDate(today, -1)) return 'Yesterday'
  return new Date(date).toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' })
}

export default function LogPage() {
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const today = toIso(new Date())
  const date = params.get('date') ?? today
  const setDate = (d: string) => setParams(d === today ? {} : { date: d })

  const streak = useQuery({
    queryKey: ['streak'],
    queryFn: () => apiGet<StreakInfo>('/api/checkin/streak'),
  })
  const log = useQuery({
    queryKey: ['food-log', date],
    queryFn: () => apiGet<FoodLogRow[]>(`/api/food/log?date=${date}`),
  })
  const targets = useQuery({
    queryKey: ['settings'],
    queryFn: () => apiGet<Targets>('/api/settings'),
  })
  const checkin = useQuery({
    queryKey: ['checkin', date],
    queryFn: () => apiGet<CheckinResponse>(`/api/checkin?date=${date}`),
  })

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['food-log', date] })
    qc.invalidateQueries({ queryKey: ['streak'] })
    qc.invalidateQueries({ queryKey: ['dashboard'] })
    qc.invalidateQueries({ queryKey: ['energy-balance'] })
    qc.invalidateQueries({ queryKey: ['tdee'] })
  }

  const remove = useMutation({
    mutationFn: (id: number) => apiDelete(`/api/food/log/${id}`),
    onSuccess: invalidate,
  })

  const copyYesterday = useMutation({
    mutationFn: () =>
      apiPost('/api/food/copy-day', { from_date: shiftDate(date, -1), to_date: date }),
    onSuccess: invalidate,
  })

  const toggleComplete = useMutation({
    mutationFn: (row: FoodLogRow) =>
      apiPut(`/api/food/log/${row.id}`, { logging_complete_day: row.logging_complete_day ? 0 : 1 }),
    onSuccess: invalidate,
  })

  const entries = log.data ?? []
  const totals = {
    calories: entries.reduce((a, e) => a + e.calories, 0),
    protein_g: entries.reduce((a, e) => a + (e.protein_g ?? 0), 0),
    carbs_g: entries.reduce((a, e) => a + (e.carbs_g ?? 0), 0),
    fat_g: entries.reduce((a, e) => a + (e.fat_g ?? 0), 0),
  }
  const t = targets.data
  const kcalLeft = t?.calorie_target != null ? Math.round(t.calorie_target - totals.calories) : null
  const ci = checkin.data

  return (
    <>
      <div className="diary-date-bar">
        <button className="secondary fixed" onClick={() => setDate(shiftDate(date, -1))}>
          ‹
        </button>
        <label className="diary-date-label">
          {dateLabel(date)}
          <input
            type="date"
            value={date}
            max={today}
            onChange={(e) => e.target.value && setDate(e.target.value)}
          />
        </label>
        <button
          className="secondary fixed"
          onClick={() => setDate(shiftDate(date, 1))}
          disabled={date >= today}
        >
          ›
        </button>
      </div>

      <StreakWeekRow streak={streak.data} />

      <div className="card">
        <div className="row" style={{ justifyContent: 'space-between', marginBottom: 6 }}>
          <strong>Calories</strong>
          {kcalLeft != null ? (
            <span className="muted">
              <strong style={{ color: kcalLeft < 0 ? 'var(--red)' : 'var(--text)' }}>
                {Math.abs(kcalLeft)}
              </strong>{' '}
              {kcalLeft < 0 ? 'over' : 'left'}
            </span>
          ) : (
            <Link to="/settings" className="muted" style={{ fontSize: '0.78rem' }}>
              Set target ›
            </Link>
          )}
        </div>
        <div style={{ marginBottom: 6 }}>
          <span style={{ fontSize: '1.3rem', fontWeight: 700 }}>{Math.round(totals.calories)}</span>
          <span className="muted"> / {t?.calorie_target != null ? Math.round(t.calorie_target) : '—'} kcal</span>
        </div>
        <ProgressBar value={totals.calories} target={t?.calorie_target} />
      </div>

      <div className="card">
        <div className="macro-cols">
          {(
            [
              ['Carbs', totals.carbs_g, t?.carbs_target_g, '#fbbf24'],
              ['Fat', totals.fat_g, t?.fat_target_g, '#a78bfa'],
              ['Protein', totals.protein_g, t?.protein_target_g, '#4ade80'],
            ] as const
          ).map(([label, val, target, color]) => (
            <div key={label} className="macro-col">
              <div className="muted" style={{ fontSize: '0.75rem' }}>{label}</div>
              <div style={{ fontSize: '0.95rem', fontWeight: 600 }}>
                {Math.round(val)}g
                {target != null && <span className="muted" style={{ fontWeight: 400 }}> / {Math.round(target)}</span>}
              </div>
              <ProgressBar value={val} target={target} color={color} />
            </div>
          ))}
        </div>
      </div>

      {ci && (
        <div className="card">
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <strong>Daily check-in</strong>
            {ci.exists ? (
              <button className="secondary fixed" onClick={() => navigate(`/log/checkin?date=${date}`)}>
                Edit
              </button>
            ) : (
              <button className="fixed" onClick={() => navigate(`/log/checkin?date=${date}`)}>
                Check in
              </button>
            )}
          </div>
          {ci.exists && ci.checkin ? (
            <div className="checkin-summary">
              {ci.checkin.mood != null && <span className="chip-sm">{MOODS[ci.checkin.mood - 1]}</span>}
              <span className="chip-sm">🍺 {ci.checkin.alcohol_units}</span>
              <span className="chip-sm">
                ☕ {ci.checkin.caffeine_cups}
                {ci.checkin.caffeine_last_time ? ` · last ${ci.checkin.caffeine_last_time}` : ''}
              </span>
              {ci.checkin.illness === 1 && <span className="chip-sm ill">🤒 ill</span>}
              {(ci.checkin.eating_start ?? ci.derived_eating_start) && (
                <span className="chip-sm">
                  🍽 {ci.checkin.eating_start ?? ci.derived_eating_start}–
                  {ci.checkin.eating_end ?? ci.derived_eating_end}
                  {ci.fasting_hours != null ? ` · ${ci.fasting_hours}h fast` : ''}
                </span>
              )}
            </div>
          ) : (
            <p className="muted" style={{ margin: '6px 0 0', fontSize: '0.8rem' }}>
              Mood, alcohol, caffeine & more — keeps your streak alive
            </p>
          )}
        </div>
      )}

      {MEALS.map((m) => (
        <MealCard
          key={m}
          meal={m}
          entries={entries.filter((e) => e.meal === m)}
          onLog={() => navigate(`/log/food/${m}?date=${date}`)}
          onDelete={(id) => remove.mutate(id)}
          onEdit={(e) =>
            navigate(`/log/food/${m}/detail?date=${date}&logId=${e.id}&cacheId=${e.food_cache_id}`)
          }
        />
      ))}

      <div className="row" style={{ marginTop: 4 }}>
        {entries.length === 0 ? (
          <button className="secondary" onClick={() => copyYesterday.mutate()} disabled={copyYesterday.isPending}>
            Copy yesterday
          </button>
        ) : (
          <button className="secondary" onClick={() => toggleComplete.mutate(entries[0])}>
            {entries[0].logging_complete_day ? '✓ Day complete' : 'Mark day complete'}
          </button>
        )}
        <Link to={`/log/other?date=${date}`} style={{ display: 'flex' }}>
          <button className="secondary" style={{ width: '100%' }}>
            Other logs
          </button>
        </Link>
      </div>
      {copyYesterday.isError && (
        <p className="error-text">{String(copyYesterday.error).replace(/^\d+: /, '').slice(0, 100)}</p>
      )}
    </>
  )
}
