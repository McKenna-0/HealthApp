import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { apiDelete, apiGet, apiPost, apiPut } from '../api/client'
import type { ContextRow, FoodItem, FoodLogRow, WeightRow } from '../api/types'

function todayIso() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

const MEALS = ['breakfast', 'lunch', 'dinner', 'snack'] as const
const CONTEXT_TYPES = ['alcohol', 'caffeine', 'mood', 'illness', 'supplement', 'note'] as const

export default function LogPage() {
  const [tab, setTab] = useState<'food' | 'weight' | 'context'>('food')
  const [date, setDate] = useState(todayIso())

  return (
    <>
      <h1>Log</h1>
      <div className="row" style={{ marginBottom: 12 }}>
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
      </div>
      <div className="tabs">
        {(['food', 'weight', 'context'] as const).map((t) => (
          <button key={t} className={`chip ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>
            {t[0].toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>
      {tab === 'food' && <FoodTab date={date} />}
      {tab === 'weight' && <WeightTab date={date} />}
      {tab === 'context' && <ContextTab date={date} />}
    </>
  )
}

// ---------------- food ----------------

function FoodTab({ date }: { date: string }) {
  const qc = useQueryClient()
  const [query, setQuery] = useState('')
  const [debounced, setDebounced] = useState('')
  const [selected, setSelected] = useState<FoodItem | null>(null)
  const [grams, setGrams] = useState('100')
  const [meal, setMeal] = useState<(typeof MEALS)[number]>('snack')
  const [freeText, setFreeText] = useState('')
  const [freeKcal, setFreeKcal] = useState('')

  useEffect(() => {
    const t = setTimeout(() => setDebounced(query.trim()), 500)
    return () => clearTimeout(t)
  }, [query])

  const search = useQuery({
    queryKey: ['food-search', debounced],
    queryFn: () => apiGet<FoodItem[]>(`/api/food/search?q=${encodeURIComponent(debounced)}`),
    enabled: debounced.length >= 2,
  })

  const log = useQuery({
    queryKey: ['food-log', date],
    queryFn: () => apiGet<FoodLogRow[]>(`/api/food/log?date=${date}`),
  })

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['food-log', date] })
    qc.invalidateQueries({ queryKey: ['dashboard'] })
    qc.invalidateQueries({ queryKey: ['energy-balance'] })
    qc.invalidateQueries({ queryKey: ['tdee'] })
  }

  const addItem = useMutation({
    mutationFn: () =>
      apiPost('/api/food/log', {
        date,
        meal,
        food_cache_id: selected!.id,
        quantity_g: parseFloat(grams),
      }),
    onSuccess: () => {
      setSelected(null)
      setQuery('')
      invalidate()
    },
  })

  const addFree = useMutation({
    mutationFn: () =>
      apiPost('/api/food/log', {
        date,
        meal,
        description: freeText,
        calories: parseFloat(freeKcal),
      }),
    onSuccess: () => {
      setFreeText('')
      setFreeKcal('')
      invalidate()
    },
  })

  const remove = useMutation({
    mutationFn: (id: number) => apiDelete(`/api/food/log/${id}`),
    onSuccess: invalidate,
  })

  const toggleComplete = useMutation({
    mutationFn: (row: FoodLogRow) =>
      apiPut(`/api/food/log/${row.id}`, { logging_complete_day: row.logging_complete_day ? 0 : 1 }),
    onSuccess: invalidate,
  })

  const entries = log.data ?? []
  const total = entries.reduce((a, e) => a + e.calories, 0)
  const previewKcal =
    selected?.kcal_per_100g != null && grams
      ? ((selected.kcal_per_100g * parseFloat(grams || '0')) / 100).toFixed(0)
      : null

  return (
    <>
      <div className="card">
        <div className="tabs">
          {MEALS.map((m) => (
            <button key={m} className={`chip ${meal === m ? 'active' : ''}`} onClick={() => setMeal(m)}>
              {m}
            </button>
          ))}
        </div>
        <input
          placeholder="Search food (Open Food Facts)…"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setSelected(null)
          }}
          style={{ width: '100%' }}
        />
        {search.isFetching && <p className="muted">Searching…</p>}
        {!selected &&
          (search.data ?? []).map((f) => (
            <div key={f.id} className="list-item" onClick={() => setSelected(f)} style={{ cursor: 'pointer' }}>
              <div className="main">
                <div className="name">{f.name}</div>
                <div className="detail">
                  {f.brand ?? ''} · {f.kcal_per_100g} kcal/100g
                </div>
              </div>
            </div>
          ))}
        {selected && (
          <div style={{ marginTop: 8 }}>
            <div className="muted">{selected.name}</div>
            <div className="row" style={{ marginTop: 8 }}>
              <input
                type="number"
                inputMode="decimal"
                value={grams}
                onChange={(e) => setGrams(e.target.value)}
                placeholder="grams"
              />
              <span className="fixed muted">g = {previewKcal ?? '–'} kcal</span>
              <button className="fixed" onClick={() => addItem.mutate()} disabled={addItem.isPending || !grams}>
                Add
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="card">
        <div className="muted" style={{ marginBottom: 8 }}>
          Quick add (free text)
        </div>
        <div className="row">
          <input placeholder="e.g. flat white" value={freeText} onChange={(e) => setFreeText(e.target.value)} />
          <input
            type="number"
            inputMode="numeric"
            placeholder="kcal"
            value={freeKcal}
            onChange={(e) => setFreeKcal(e.target.value)}
            style={{ maxWidth: 90 }}
          />
          <button className="fixed" onClick={() => addFree.mutate()} disabled={addFree.isPending || !freeText || !freeKcal}>
            Add
          </button>
        </div>
      </div>

      <div className="card">
        <div className="row" style={{ justifyContent: 'space-between', marginBottom: 4 }}>
          <strong>
            {date} · {total.toFixed(0)} kcal
          </strong>
          {entries.length > 0 && (
            <button className="secondary fixed" onClick={() => toggleComplete.mutate(entries[0])}>
              {entries[0].logging_complete_day ? '✓ Day complete' : 'Day incomplete'}
            </button>
          )}
        </div>
        {entries.length === 0 && <p className="muted">Nothing logged yet.</p>}
        {entries.map((e) => (
          <div key={e.id} className="list-item">
            <div className="main">
              <div className="name">{e.description ?? 'Food'}</div>
              <div className="detail">
                {e.meal}
                {e.quantity_g ? ` · ${e.quantity_g}g` : ''} · {e.calories.toFixed(0)} kcal
              </div>
            </div>
            <button className="del" onClick={() => remove.mutate(e.id)}>
              ✕
            </button>
          </div>
        ))}
      </div>
    </>
  )
}

// ---------------- weight ----------------

function WeightTab({ date }: { date: string }) {
  const qc = useQueryClient()
  const [kg, setKg] = useState('')
  const [note, setNote] = useState('')

  const recent = useQuery({
    queryKey: ['weight-recent'],
    queryFn: () => apiGet<WeightRow[]>('/api/weight'),
  })

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['weight-recent'] })
    qc.invalidateQueries({ queryKey: ['weight-trend'] })
    qc.invalidateQueries({ queryKey: ['dashboard'] })
    qc.invalidateQueries({ queryKey: ['tdee'] })
  }

  const add = useMutation({
    mutationFn: () => apiPost('/api/weight', { date, weight_kg: parseFloat(kg), note: note || null }),
    onSuccess: () => {
      setKg('')
      setNote('')
      invalidate()
    },
  })

  const remove = useMutation({
    mutationFn: (id: number) => apiDelete(`/api/weight/${id}`),
    onSuccess: invalidate,
  })

  const rows = [...(recent.data ?? [])].reverse().slice(0, 14)

  return (
    <>
      <div className="card">
        <div className="row">
          <input
            type="number"
            inputMode="decimal"
            step="0.1"
            placeholder="Weight (kg)"
            value={kg}
            onChange={(e) => setKg(e.target.value)}
          />
          <input placeholder="note (optional)" value={note} onChange={(e) => setNote(e.target.value)} />
          <button className="fixed" onClick={() => add.mutate()} disabled={add.isPending || !kg}>
            Save
          </button>
        </div>
      </div>
      <div className="card">
        <strong>Recent</strong>
        {rows.map((w) => (
          <div key={w.id} className="list-item">
            <div className="main">
              <div className="name">{w.weight_kg.toFixed(1)} kg</div>
              <div className="detail">
                {w.date} · {w.source}
                {w.note ? ` · ${w.note}` : ''}
              </div>
            </div>
            {w.source === 'manual' && (
              <button className="del" onClick={() => remove.mutate(w.id)}>
                ✕
              </button>
            )}
          </div>
        ))}
      </div>
    </>
  )
}

// ---------------- context ----------------

function ContextTab({ date }: { date: string }) {
  const qc = useQueryClient()
  const [type, setType] = useState<(typeof CONTEXT_TYPES)[number]>('caffeine')
  const [value, setValue] = useState('')
  const [note, setNote] = useState('')

  const list = useQuery({
    queryKey: ['context', date],
    queryFn: () => apiGet<ContextRow[]>(`/api/context?start=${date}&end=${date}`),
  })

  const add = useMutation({
    mutationFn: () =>
      apiPost('/api/context', {
        date,
        type,
        value: value ? parseFloat(value) : null,
        note: note || null,
      }),
    onSuccess: () => {
      setValue('')
      setNote('')
      qc.invalidateQueries({ queryKey: ['context', date] })
    },
  })

  const remove = useMutation({
    mutationFn: (id: number) => apiDelete(`/api/context/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['context', date] }),
  })

  const hint: Record<string, string> = {
    alcohol: 'units',
    caffeine: 'mg',
    mood: '1–5',
    illness: '1 = yes',
    supplement: 'dose',
    note: '',
  }

  return (
    <>
      <div className="card">
        <div className="tabs">
          {CONTEXT_TYPES.map((t) => (
            <button key={t} className={`chip ${type === t ? 'active' : ''}`} onClick={() => setType(t)}>
              {t}
            </button>
          ))}
        </div>
        <div className="row">
          <input
            type="number"
            inputMode="decimal"
            placeholder={hint[type] || 'value'}
            value={value}
            onChange={(e) => setValue(e.target.value)}
          />
          <input placeholder="note (optional)" value={note} onChange={(e) => setNote(e.target.value)} />
          <button className="fixed" onClick={() => add.mutate()} disabled={add.isPending}>
            Save
          </button>
        </div>
      </div>
      <div className="card">
        <strong>{date}</strong>
        {(list.data ?? []).length === 0 && <p className="muted">Nothing logged.</p>}
        {(list.data ?? []).map((c) => (
          <div key={c.id} className="list-item">
            <div className="main">
              <div className="name">
                {c.type}
                {c.value != null ? ` · ${c.value}` : ''}
              </div>
              <div className="detail">{c.note ?? ''}</div>
            </div>
            <button className="del" onClick={() => remove.mutate(c.id)}>
              ✕
            </button>
          </div>
        ))}
      </div>
    </>
  )
}
