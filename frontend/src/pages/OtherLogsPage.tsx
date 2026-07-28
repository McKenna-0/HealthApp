import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { apiDelete, apiGet, apiPost } from '../api/client'
import type { ContextRow, WeightRow } from '../api/types'

const CONTEXT_TYPES = ['alcohol', 'caffeine', 'mood', 'illness', 'supplement', 'note'] as const

function todayIso() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export default function OtherLogsPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const date = params.get('date') ?? todayIso()
  const [tab, setTab] = useState<'weight' | 'context'>('weight')

  return (
    <>
      <div className="row" style={{ marginBottom: 8, marginTop: 8 }}>
        <button className="secondary fixed" onClick={() => navigate(`/log?date=${date}`)}>
          ‹
        </button>
        <h1 style={{ margin: 0, flex: 1, textAlign: 'center' }}>Other logs</h1>
        <span className="fixed" style={{ width: 44 }} />
      </div>
      <div className="tabs">
        {(['weight', 'context'] as const).map((t) => (
          <button key={t} className={`chip ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>
            {t[0].toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>
      {tab === 'weight' && <WeightTab date={date} />}
      {tab === 'context' && <ContextTab date={date} />}
    </>
  )
}

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
                {c.label === 'checkin' && <span className="badge app-badge">check-in</span>}
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
