import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  ChevronLeft, ChevronRight, Plus, Scale,
  StickyNote, RefreshCw,
} from 'lucide-react'
import { apiDelete, apiGet, apiPost, apiPut } from '../api/client'
import type { CheckinResponse, FoodLogRow, Meal, MfpStatus, StreakInfo } from '../api/types'
import BottomSheet from '../components/BottomSheet'
import CalorieDonut from '../components/CalorieDonut'
import ProgressBar from '../components/ProgressBar'
import StreakWeekRow from '../components/StreakWeekRow'
import MealCard from '../components/MealCard'
import Stepper from '../components/Stepper'

const MEALS: Meal[] = ['breakfast', 'lunch', 'dinner', 'snack']
const MOODS = ['😞', '😕', '😐', '🙂', '😄']

interface Settings {
  calorie_target: number | null
  protein_target_g: number | null
  carbs_target_g: number | null
  fat_target_g: number | null
}

function todayIso() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function shiftDate(date: string, days: number) {
  const d = new Date(date + 'T00:00:00')
  d.setDate(d.getDate() + days)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function dateLabel(date: string) {
  const today = todayIso()
  if (date === today) return 'Today'
  if (date === shiftDate(today, -1)) return 'Yesterday'
  return new Date(date + 'T00:00:00').toLocaleDateString(undefined, {
    weekday: 'short', day: 'numeric', month: 'short',
  })
}

// ────────── Check-in sheet ──────────

function CheckinSheet({
  open,
  onClose,
  date,
  data,
}: {
  open: boolean
  onClose: () => void
  date: string
  data: CheckinResponse | undefined
}) {
  const qc = useQueryClient()

  const [mood, setMood] = useState<number | null>(null)
  const [alcohol, setAlcohol] = useState(0)
  const [caffeine, setCaffeine] = useState(0)
  const [caffeineTime, setCaffeineTime] = useState('')
  const [ill, setIll] = useState(false)
  const [weight, setWeight] = useState('')
  const [eatStart, setEatStart] = useState('')
  const [eatEnd, setEatEnd] = useState('')
  const [note, setNote] = useState('')
  const [loaded, setLoaded] = useState(false)

  // Populate from existing data whenever sheet opens (or data arrives)
  useEffect(() => {
    if (!open || !data) return
    if (loaded) return
    setLoaded(true)
    const c = data.checkin
    if (c) {
      setMood(c.mood)
      setAlcohol(c.alcohol_units)
      setCaffeine(c.caffeine_cups)
      setCaffeineTime(c.caffeine_last_time ?? '')
      setIll(c.illness === 1)
      setEatStart(c.eating_start ?? '')
      setEatEnd(c.eating_end ?? '')
      setNote(c.note ?? '')
    }
    if (data.weight_kg != null) setWeight(String(data.weight_kg))
  }, [open, data, loaded])

  // Reset loaded flag when sheet closes so next open re-populates
  useEffect(() => {
    if (!open) setLoaded(false)
  }, [open])

  const save = useMutation({
    mutationFn: () =>
      apiPut<CheckinResponse>(`/api/checkin/${date}`, {
        mood,
        alcohol_units: alcohol,
        caffeine_cups: caffeine,
        caffeine_last_time: caffeine > 0 && caffeineTime ? caffeineTime : null,
        illness: ill ? 1 : 0,
        eating_start: eatStart || null,
        eating_end: eatEnd || null,
        weight_kg: weight ? parseFloat(weight) : null,
        note: note.trim() || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['checkin', date] })
      qc.invalidateQueries({ queryKey: ['streak'] })
      qc.invalidateQueries({ queryKey: ['weight-recent'] })
      qc.invalidateQueries({ queryKey: ['dashboard'] })
      qc.invalidateQueries({ queryKey: ['tdee'] })
      onClose()
    },
  })

  return (
    <BottomSheet open={open} onClose={onClose} title="Daily Check-in">
      <div style={{ padding: '0 16px 32px', display: 'flex', flexDirection: 'column', gap: 20 }}>
        {/* Mood */}
        <div>
          <div className="text-caption" style={{ color: 'var(--muted)', marginBottom: 10 }}>How was your mood?</div>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
            {MOODS.map((m, i) => (
              <button
                key={i}
                onClick={() => setMood(mood === i + 1 ? null : i + 1)}
                style={{
                  flex: 1,
                  minHeight: 48,
                  fontSize: '1.5rem',
                  borderRadius: 12,
                  border: `2px solid ${mood === i + 1 ? 'var(--accent)' : 'var(--border)'}`,
                  background: mood === i + 1 ? 'color-mix(in srgb, var(--accent) 15%, transparent)' : 'var(--surface)',
                  cursor: 'pointer',
                }}
              >
                {m}
              </button>
            ))}
          </div>
        </div>

        {/* Alcohol */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div className="text-body" style={{ fontWeight: 600 }}>Alcohol</div>
            <div className="text-caption" style={{ color: 'var(--muted)' }}>units</div>
          </div>
          <Stepper value={alcohol} onChange={setAlcohol} step={0.5} max={30} />
        </div>

        {/* Caffeine */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div className="text-body" style={{ fontWeight: 600 }}>Caffeine</div>
              <div className="text-caption" style={{ color: 'var(--muted)' }}>cups (~80 mg each)</div>
            </div>
            <Stepper value={caffeine} onChange={setCaffeine} step={1} max={15} />
          </div>
          {caffeine > 0 && (
            <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 10 }}>
              <label className="text-caption" style={{ color: 'var(--muted)', whiteSpace: 'nowrap' }}>Last cup at</label>
              <input
                type="time"
                value={caffeineTime}
                onChange={(e) => setCaffeineTime(e.target.value)}
                style={{ flex: 1, minHeight: 40 }}
              />
            </div>
          )}
        </div>

        {/* Illness */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div className="text-body" style={{ fontWeight: 600 }}>Feeling ill?</div>
          <button
            onClick={() => setIll((v) => !v)}
            style={{
              minHeight: 44,
              padding: '0 20px',
              borderRadius: 99,
              border: `2px solid ${ill ? 'var(--red)' : 'var(--border)'}`,
              background: ill ? 'color-mix(in srgb, var(--red) 15%, transparent)' : 'var(--surface)',
              color: ill ? 'var(--red)' : 'var(--muted)',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            {ill ? '🤒 Yes' : 'No'}
          </button>
        </div>

        {/* Weight */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div className="text-body" style={{ fontWeight: 600 }}>Weight</div>
            <div className="text-caption" style={{ color: 'var(--muted)' }}>optional, kg</div>
          </div>
          <input
            type="number"
            inputMode="decimal"
            step="0.1"
            placeholder="—"
            value={weight}
            onChange={(e) => setWeight(e.target.value)}
            style={{ maxWidth: 110, textAlign: 'center', minHeight: 44 }}
          />
        </div>

        {/* Eating window */}
        <div>
          <div className="text-body" style={{ fontWeight: 600, marginBottom: 4 }}>Eating window</div>
          {data?.derived_eating_start ? (
            <div className="text-caption" style={{ color: 'var(--muted)', marginBottom: 8 }}>
              Estimated from logs: {data.derived_eating_start}–{data.derived_eating_end}
              {data.fasting_hours != null ? ` · ${data.fasting_hours}h fast` : ''}
            </div>
          ) : (
            <div className="text-caption" style={{ color: 'var(--muted)', marginBottom: 8 }}>
              Log food to see an estimate, or set manually
            </div>
          )}
          <div style={{ display: 'flex', gap: 12 }}>
            <div style={{ flex: 1 }}>
              <div className="text-caption" style={{ color: 'var(--muted)', marginBottom: 4 }}>First meal</div>
              <input type="time" value={eatStart} onChange={(e) => setEatStart(e.target.value)} style={{ width: '100%', minHeight: 44 }} />
            </div>
            <div style={{ flex: 1 }}>
              <div className="text-caption" style={{ color: 'var(--muted)', marginBottom: 4 }}>Last meal</div>
              <input type="time" value={eatEnd} onChange={(e) => setEatEnd(e.target.value)} style={{ width: '100%', minHeight: 44 }} />
            </div>
          </div>
        </div>

        {/* Note */}
        <div>
          <div className="text-body" style={{ fontWeight: 600, marginBottom: 6 }}>Note</div>
          <textarea
            placeholder="Optional note…"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={3}
            style={{ width: '100%', resize: 'none', minHeight: 72 }}
          />
        </div>

        {/* Save */}
        <button
          onClick={() => save.mutate()}
          disabled={save.isPending}
          style={{
            width: '100%',
            minHeight: 52,
            borderRadius: 14,
            background: 'var(--accent)',
            color: 'white',
            border: 'none',
            fontWeight: 700,
            fontSize: '1rem',
            cursor: save.isPending ? 'not-allowed' : 'pointer',
          }}
        >
          {save.isPending ? 'Saving…' : data?.exists ? 'Update check-in' : '✓ Complete check-in'}
        </button>
        {save.isError && (
          <p style={{ color: 'var(--red)', fontSize: '0.8rem', margin: 0 }}>
            {String(save.error).replace(/^\d+: /, '').slice(0, 120)}
          </p>
        )}
      </div>
    </BottomSheet>
  )
}

// ────────── Quick Add sheet ──────────

function QuickAddSheet({
  open,
  onClose,
  date,
}: {
  open: boolean
  onClose: () => void
  date: string
}) {
  const qc = useQueryClient()
  const [name, setName] = useState('')
  const [kcal, setKcal] = useState('')
  const [meal, setMeal] = useState<Meal>('snack')

  const add = useMutation({
    mutationFn: () =>
      apiPost('/api/food/log', {
        date,
        meal,
        description: name.trim(),
        calories: parseFloat(kcal),
      }),
    onSuccess: () => {
      setName('')
      setKcal('')
      qc.invalidateQueries({ queryKey: ['food-log', date] })
      qc.invalidateQueries({ queryKey: ['dashboard'] })
      onClose()
    },
  })

  return (
    <BottomSheet open={open} onClose={onClose} title="Quick Add Food">
      <div style={{ padding: '0 16px 32px', display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div>
          <div className="text-caption" style={{ color: 'var(--muted)', marginBottom: 6 }}>Food name</div>
          <input
            placeholder="e.g. Banana, Chicken breast…"
            value={name}
            onChange={(e) => setName(e.target.value)}
            style={{ width: '100%', minHeight: 44 }}
            autoFocus
          />
        </div>
        <div>
          <div className="text-caption" style={{ color: 'var(--muted)', marginBottom: 6 }}>Calories (kcal)</div>
          <input
            type="number"
            inputMode="numeric"
            placeholder="0"
            value={kcal}
            onChange={(e) => setKcal(e.target.value)}
            style={{ width: '100%', minHeight: 44 }}
          />
        </div>
        <div>
          <div className="text-caption" style={{ color: 'var(--muted)', marginBottom: 8 }}>Meal</div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {MEALS.map((m) => (
              <button
                key={m}
                onClick={() => setMeal(m)}
                style={{
                  minHeight: 44,
                  padding: '0 16px',
                  borderRadius: 99,
                  border: `2px solid ${meal === m ? 'var(--accent)' : 'var(--border)'}`,
                  background: meal === m ? 'color-mix(in srgb, var(--accent) 15%, transparent)' : 'var(--surface)',
                  color: meal === m ? 'var(--accent)' : 'var(--text)',
                  fontWeight: 600,
                  cursor: 'pointer',
                  textTransform: 'capitalize',
                }}
              >
                {m}
              </button>
            ))}
          </div>
        </div>
        <button
          onClick={() => add.mutate()}
          disabled={add.isPending || !name.trim() || !kcal}
          style={{
            width: '100%',
            minHeight: 52,
            borderRadius: 14,
            background: 'var(--accent)',
            color: 'white',
            border: 'none',
            fontWeight: 700,
            fontSize: '1rem',
            cursor: add.isPending || !name.trim() || !kcal ? 'not-allowed' : 'pointer',
            opacity: !name.trim() || !kcal ? 0.5 : 1,
          }}
        >
          {add.isPending ? 'Adding…' : '+ Add food'}
        </button>
        {add.isError && (
          <p style={{ color: 'var(--red)', fontSize: '0.8rem', margin: 0 }}>
            {String(add.error).replace(/^\d+: /, '').slice(0, 120)}
          </p>
        )}
      </div>
    </BottomSheet>
  )
}

// ────────── Weight Log sheet ──────────

function WeightLogSheet({
  open,
  onClose,
  date,
}: {
  open: boolean
  onClose: () => void
  date: string
}) {
  const qc = useQueryClient()
  const [kg, setKg] = useState('')
  const [note, setNote] = useState('')

  const add = useMutation({
    mutationFn: () =>
      apiPost('/api/weight', { date, weight_kg: parseFloat(kg), note: note.trim() || null }),
    onSuccess: () => {
      setKg('')
      setNote('')
      qc.invalidateQueries({ queryKey: ['weight-recent'] })
      qc.invalidateQueries({ queryKey: ['weight-trend'] })
      qc.invalidateQueries({ queryKey: ['dashboard'] })
      qc.invalidateQueries({ queryKey: ['tdee'] })
      onClose()
    },
  })

  return (
    <BottomSheet open={open} onClose={onClose} title="Log Weight">
      <div style={{ padding: '0 16px 32px', display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div>
          <div className="text-caption" style={{ color: 'var(--muted)', marginBottom: 6 }}>Weight (kg)</div>
          <input
            type="number"
            inputMode="decimal"
            step="0.1"
            placeholder="e.g. 75.4"
            value={kg}
            onChange={(e) => setKg(e.target.value)}
            style={{ width: '100%', minHeight: 44 }}
            autoFocus
          />
        </div>
        <div>
          <div className="text-caption" style={{ color: 'var(--muted)', marginBottom: 6 }}>Note (optional)</div>
          <input
            placeholder="e.g. morning, post-workout…"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            style={{ width: '100%', minHeight: 44 }}
          />
        </div>
        <button
          onClick={() => add.mutate()}
          disabled={add.isPending || !kg}
          style={{
            width: '100%',
            minHeight: 52,
            borderRadius: 14,
            background: 'var(--accent)',
            color: 'white',
            border: 'none',
            fontWeight: 700,
            fontSize: '1rem',
            cursor: add.isPending || !kg ? 'not-allowed' : 'pointer',
            opacity: !kg ? 0.5 : 1,
          }}
        >
          {add.isPending ? 'Saving…' : 'Save weight'}
        </button>
        {add.isError && (
          <p style={{ color: 'var(--red)', fontSize: '0.8rem', margin: 0 }}>
            {String(add.error).replace(/^\d+: /, '').slice(0, 120)}
          </p>
        )}
      </div>
    </BottomSheet>
  )
}

// ────────── Note sheet ──────────

function NoteSheet({
  open,
  onClose,
  date,
}: {
  open: boolean
  onClose: () => void
  date: string
}) {
  const qc = useQueryClient()
  const [note, setNote] = useState('')

  const add = useMutation({
    mutationFn: () =>
      apiPost('/api/context', { date, type: 'note', note: note.trim() || null }),
    onSuccess: () => {
      setNote('')
      qc.invalidateQueries({ queryKey: ['context', date] })
      onClose()
    },
  })

  return (
    <BottomSheet open={open} onClose={onClose} title="Add Note">
      <div style={{ padding: '0 16px 32px', display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div>
          <div className="text-caption" style={{ color: 'var(--muted)', marginBottom: 6 }}>Note</div>
          <textarea
            placeholder="Write a note…"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={5}
            autoFocus
            style={{ width: '100%', resize: 'none', minHeight: 100 }}
          />
        </div>
        <button
          onClick={() => add.mutate()}
          disabled={add.isPending || !note.trim()}
          style={{
            width: '100%',
            minHeight: 52,
            borderRadius: 14,
            background: 'var(--accent)',
            color: 'white',
            border: 'none',
            fontWeight: 700,
            fontSize: '1rem',
            cursor: add.isPending || !note.trim() ? 'not-allowed' : 'pointer',
            opacity: !note.trim() ? 0.5 : 1,
          }}
        >
          {add.isPending ? 'Saving…' : 'Save note'}
        </button>
        {add.isError && (
          <p style={{ color: 'var(--red)', fontSize: '0.8rem', margin: 0 }}>
            {String(add.error).replace(/^\d+: /, '').slice(0, 120)}
          </p>
        )}
      </div>
    </BottomSheet>
  )
}

// ────────── Main LogPage ──────────

export default function LogPage() {
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const today = todayIso()
  const date = params.get('date') ?? today
  const setDate = (d: string) => setParams(d === today ? {} : { date: d })
  const isDateToday = date === today

  const [showCheckin, setShowCheckin] = useState(false)
  const [showQuickAdd, setShowQuickAdd] = useState(false)
  const [showWeightLog, setShowWeightLog] = useState(false)
  const [showNote, setShowNote] = useState(false)

  // Queries
  const { data: foodLog } = useQuery<FoodLogRow[]>({
    queryKey: ['food-log', date],
    queryFn: () => apiGet(`/api/food/log?date=${date}`),
  })
  const { data: checkinResp } = useQuery<CheckinResponse>({
    queryKey: ['checkin', date],
    queryFn: () => apiGet(`/api/checkin?date=${date}`),
  })
  const { data: streak } = useQuery<StreakInfo>({
    queryKey: ['streak'],
    queryFn: () => apiGet('/api/checkin/streak'),
  })
  const { data: settings } = useQuery<Settings>({
    queryKey: ['settings'],
    queryFn: () => apiGet('/api/settings'),
  })
  const { data: mfpStatus } = useQuery<MfpStatus>({
    queryKey: ['mfp-status'],
    queryFn: () => apiGet('/api/mfp/status'),
  })

  // Mutations
  const deleteFoodMut = useMutation({
    mutationFn: (id: number) => apiDelete(`/api/food/log/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['food-log', date] })
      qc.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })

  const mfpSyncMut = useMutation({
    mutationFn: () => apiPost('/api/mfp/sync'),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['food-log'] }),
  })

  // Computed
  const entries = foodLog ?? []
  const totalCal = entries.reduce((s, f) => s + f.calories, 0)
  const totalP = entries.reduce((s, f) => s + (f.protein_g ?? 0), 0)
  const totalC = entries.reduce((s, f) => s + (f.carbs_g ?? 0), 0)
  const totalF = entries.reduce((s, f) => s + (f.fat_g ?? 0), 0)
  const checkin = checkinResp?.checkin

  const calTarget = settings?.calorie_target ?? null
  const protTarget = settings?.protein_target_g ?? null
  const carbTarget = settings?.carbs_target_g ?? null
  const fatTarget = settings?.fat_target_g ?? null

  // Chip button style
  const chipStyle = (active = false): React.CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    minHeight: 44,
    padding: '0 16px',
    borderRadius: 99,
    border: `1.5px solid ${active ? 'var(--accent)' : 'var(--border)'}`,
    background: active ? 'color-mix(in srgb, var(--accent) 12%, transparent)' : 'var(--surface)',
    color: active ? 'var(--accent)' : 'var(--text)',
    fontWeight: 600,
    fontSize: '0.85rem',
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  })

  return (
    <div style={{ padding: '16px 16px 100px' }}>
      {/* Date bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 16, marginBottom: 16 }}>
        <button
          onClick={() => setDate(shiftDate(date, -1))}
          style={{ minWidth: 44, minHeight: 44, borderRadius: 10, background: 'var(--surface)', border: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}
        >
          <ChevronLeft size={20} />
        </button>
        <span className="text-title" style={{ minWidth: 100, textAlign: 'center' }}>{dateLabel(date)}</span>
        <button
          onClick={() => !isDateToday && setDate(shiftDate(date, 1))}
          disabled={isDateToday}
          style={{ minWidth: 44, minHeight: 44, borderRadius: 10, background: 'var(--surface)', border: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: isDateToday ? 'default' : 'pointer', opacity: isDateToday ? 0.4 : 1 }}
        >
          <ChevronRight size={20} />
        </button>
      </div>

      {/* Streak */}
      {streak && <StreakWeekRow streak={streak} />}

      {/* Check-in card */}
      <div className="card" style={{ marginTop: 12 }}>
        {checkin ? (
          <div onClick={() => setShowCheckin(true)} style={{ cursor: 'pointer' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <span className="text-title">Check-in</span>
              <span className="text-caption" style={{ color: 'var(--accent)', fontWeight: 600 }}>Edit</span>
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {checkin.mood && (
                <span style={{ fontSize: '1.3rem' }}>{MOODS[checkin.mood - 1]}</span>
              )}
              {checkin.alcohol_units > 0 && (
                <span className="text-caption" style={{ background: 'var(--surface)', padding: '4px 10px', borderRadius: 99, border: '1px solid var(--border)' }}>
                  🍺 {checkin.alcohol_units}
                </span>
              )}
              {checkin.caffeine_cups > 0 && (
                <span className="text-caption" style={{ background: 'var(--surface)', padding: '4px 10px', borderRadius: 99, border: '1px solid var(--border)' }}>
                  ☕ {checkin.caffeine_cups}
                </span>
              )}
              {checkin.illness === 1 && (
                <span className="text-caption" style={{ background: 'color-mix(in srgb, var(--red) 12%, transparent)', padding: '4px 10px', borderRadius: 99, border: '1px solid var(--red)', color: 'var(--red)' }}>
                  🤒 Ill
                </span>
              )}
              {checkinResp?.fasting_hours != null && (
                <span className="text-caption" style={{ background: 'var(--surface)', padding: '4px 10px', borderRadius: 99, border: '1px solid var(--border)' }}>
                  🍽️ {checkinResp.fasting_hours}h fast
                </span>
              )}
            </div>
          </div>
        ) : (
          <div>
            <div className="text-title" style={{ marginBottom: 6 }}>How's your day?</div>
            <div className="text-caption" style={{ color: 'var(--muted)', marginBottom: 12 }}>
              Mood, alcohol, caffeine &amp; more — keeps your streak alive
            </div>
            <button
              onClick={() => setShowCheckin(true)}
              style={{ width: '100%', minHeight: 48, borderRadius: 12, background: 'var(--accent)', color: 'white', border: 'none', fontWeight: 700, fontSize: '0.95rem', cursor: 'pointer' }}
            >
              Check in
            </button>
          </div>
        )}
      </div>

      {/* Nutrition summary */}
      <div className="card" style={{ marginTop: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <span className="text-title">Nutrition</span>
          {mfpStatus?.cookie_set && (
            <span className="text-caption" style={{ color: 'var(--green)' }}>via MFP</span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <CalorieDonut calories={totalCal} protein_g={totalP} carbs_g={totalC} fat_g={totalF} size={90} />
          <div style={{ flex: 1 }}>
            <div style={{ marginBottom: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span className="text-caption">Calories</span>
                <span className="text-caption">{Math.round(totalCal)}{calTarget ? ` / ${Math.round(calTarget)}` : ''}</span>
              </div>
              <ProgressBar value={totalCal} target={calTarget} color="var(--accent)" />
            </div>
            <div style={{ marginBottom: 6 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span className="text-caption">Protein</span>
                <span className="text-caption">{Math.round(totalP)}g{protTarget ? ` / ${Math.round(protTarget)}g` : ''}</span>
              </div>
              <ProgressBar value={totalP} target={protTarget} color="var(--green)" />
            </div>
            <div style={{ marginBottom: 6 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span className="text-caption">Carbs</span>
                <span className="text-caption">{Math.round(totalC)}g{carbTarget ? ` / ${Math.round(carbTarget)}g` : ''}</span>
              </div>
              <ProgressBar value={totalC} target={carbTarget} color="var(--amber)" />
            </div>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span className="text-caption">Fat</span>
                <span className="text-caption">{Math.round(totalF)}g{fatTarget ? ` / ${Math.round(fatTarget)}g` : ''}</span>
              </div>
              <ProgressBar value={totalF} target={fatTarget} color="#a78bfa" />
            </div>
          </div>
        </div>
      </div>

      {/* Quick actions */}
      <div style={{ display: 'flex', gap: 8, marginTop: 12, overflowX: 'auto', paddingBottom: 4 }}>
        {mfpStatus?.cookie_set && (
          <button style={chipStyle(mfpSyncMut.isPending)} onClick={() => mfpSyncMut.mutate()} disabled={mfpSyncMut.isPending}>
            <RefreshCw size={14} /> {mfpSyncMut.isPending ? 'Syncing…' : 'Sync MFP'}
          </button>
        )}
        <button style={chipStyle()} onClick={() => setShowQuickAdd(true)}>
          <Plus size={14} /> Quick add
        </button>
        <button style={chipStyle()} onClick={() => setShowWeightLog(true)}>
          <Scale size={14} /> Weight
        </button>
        <button style={chipStyle()} onClick={() => setShowNote(true)}>
          <StickyNote size={14} /> Note
        </button>
      </div>

      {/* Meal cards */}
      {MEALS.map((m) => (
        <MealCard
          key={m}
          meal={m}
          entries={entries.filter((e) => e.meal === m)}
          onLog={() => navigate(`/log/food/${m}?date=${date}`)}
          onDelete={(id) => deleteFoodMut.mutate(id)}
          onEdit={(e) =>
            navigate(`/log/food/${m}/detail?date=${date}&logId=${e.id}&cacheId=${e.food_cache_id}`)
          }
        />
      ))}

      {/* Bottom sheets */}
      <CheckinSheet
        open={showCheckin}
        onClose={() => setShowCheckin(false)}
        date={date}
        data={checkinResp}
      />
      <QuickAddSheet
        open={showQuickAdd}
        onClose={() => setShowQuickAdd(false)}
        date={date}
      />
      <WeightLogSheet
        open={showWeightLog}
        onClose={() => setShowWeightLog(false)}
        date={date}
      />
      <NoteSheet
        open={showNote}
        onClose={() => setShowNote(false)}
        date={date}
      />
    </div>
  )
}
