import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { apiGet, apiPut } from '../api/client'
import type { CheckinResponse } from '../api/types'
import Stepper from '../components/Stepper'

const MOODS = ['😞', '😕', '😐', '🙂', '😄']

function todayIso() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export default function CheckinPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const date = params.get('date') ?? todayIso()

  const { data, isLoading } = useQuery({
    queryKey: ['checkin', date],
    queryFn: () => apiGet<CheckinResponse>(`/api/checkin?date=${date}`),
  })

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

  useEffect(() => {
    if (!data || loaded) return
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
  }, [data, loaded])

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
      qc.invalidateQueries({ queryKey: ['context', date] })
      qc.invalidateQueries({ queryKey: ['weight-recent'] })
      qc.invalidateQueries({ queryKey: ['dashboard'] })
      qc.invalidateQueries({ queryKey: ['tdee'] })
      navigate(`/log?date=${date}`)
    },
  })

  if (isLoading) return <p className="muted">Loading…</p>

  return (
    <>
      <div className="row" style={{ marginBottom: 8, marginTop: 8 }}>
        <button className="secondary fixed" onClick={() => navigate(`/log?date=${date}`)}>
          ‹
        </button>
        <h1 style={{ margin: 0, flex: 1, textAlign: 'center' }}>Daily check-in</h1>
        <span className="fixed" style={{ width: 44 }} />
      </div>
      <p className="muted" style={{ margin: '0 4px 12px', textAlign: 'center', fontSize: '0.8rem' }}>
        {date}
      </p>

      <div className="card">
        <h2 style={{ marginTop: 0 }}>How was your mood?</h2>
        <div className="mood-row">
          {MOODS.map((m, i) => (
            <button
              key={i}
              className={`mood-btn ${mood === i + 1 ? 'active' : ''}`}
              onClick={() => setMood(mood === i + 1 ? null : i + 1)}
            >
              {m}
            </button>
          ))}
        </div>
      </div>

      <div className="card">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <strong>Alcohol</strong>
            <div className="muted" style={{ fontSize: '0.75rem' }}>units</div>
          </div>
          <Stepper value={alcohol} onChange={setAlcohol} step={0.5} max={30} />
        </div>
      </div>

      <div className="card">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <strong>Caffeine</strong>
            <div className="muted" style={{ fontSize: '0.75rem' }}>cups (~80mg each)</div>
          </div>
          <Stepper value={caffeine} onChange={setCaffeine} step={1} max={15} />
        </div>
        {caffeine > 0 && (
          <div className="row" style={{ marginTop: 10 }}>
            <span className="muted fixed">Last cup at</span>
            <input type="time" value={caffeineTime} onChange={(e) => setCaffeineTime(e.target.value)} />
          </div>
        )}
      </div>

      <div className="card">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <strong>Feeling ill?</strong>
          <button className={`toggle-chip ${ill ? 'active' : ''}`} onClick={() => setIll((v) => !v)}>
            {ill ? 'Yes' : 'No'}
          </button>
        </div>
      </div>

      <div className="card">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <strong>Weight</strong>
            <div className="muted" style={{ fontSize: '0.75rem' }}>optional, kg</div>
          </div>
          <input
            type="number"
            inputMode="decimal"
            step="0.1"
            placeholder="—"
            value={weight}
            onChange={(e) => setWeight(e.target.value)}
            style={{ maxWidth: 110, textAlign: 'center' }}
          />
        </div>
      </div>

      <div className="card">
        <strong>Eating window</strong>
        <div className="muted" style={{ fontSize: '0.75rem', marginBottom: 8 }}>
          {data?.derived_eating_start
            ? `Estimated from logs: ${data.derived_eating_start}–${data.derived_eating_end}` +
              (data.fasting_hours != null ? ` · ${data.fasting_hours}h fast` : '')
            : 'Log food to see an estimate, or set manually'}
        </div>
        <div className="row">
          <div style={{ flex: 1 }}>
            <div className="muted" style={{ fontSize: '0.7rem', marginBottom: 4 }}>First meal</div>
            <input type="time" value={eatStart} onChange={(e) => setEatStart(e.target.value)} style={{ width: '100%' }} />
          </div>
          <div style={{ flex: 1 }}>
            <div className="muted" style={{ fontSize: '0.7rem', marginBottom: 4 }}>Last meal</div>
            <input type="time" value={eatEnd} onChange={(e) => setEatEnd(e.target.value)} style={{ width: '100%' }} />
          </div>
        </div>
      </div>

      <div className="card">
        <input
          placeholder="Note (optional)"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          style={{ width: '100%' }}
        />
      </div>

      <button style={{ width: '100%' }} onClick={() => save.mutate()} disabled={save.isPending}>
        {save.isPending ? 'Saving…' : data?.exists ? 'Update check-in' : '✓ Complete check-in'}
      </button>
      {save.isError && (
        <p className="error-text">{String(save.error).replace(/^\d+: /, '').slice(0, 120)}</p>
      )}
    </>
  )
}
