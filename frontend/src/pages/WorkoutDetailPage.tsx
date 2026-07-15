import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { apiDelete, apiGet, apiPost } from '../api/client'
import type { Exercise, HrZone, Lap, SessionPayload, WorkoutDetail } from '../api/types'

function fmtDuration(min: number | null) {
  if (min == null) return '–'
  const h = Math.floor(min / 60)
  return h > 0 ? `${h}h ${Math.round(min % 60)}m` : `${Math.round(min)}m`
}

function fmtLapTime(s: number | null) {
  if (s == null) return '–'
  const m = Math.floor(s / 60)
  return `${m}:${String(Math.round(s % 60)).padStart(2, '0')}`
}

function pace(mps: number | null) {
  if (!mps) return '–'
  const minPerKm = 1000 / mps / 60
  const m = Math.floor(minPerKm)
  return `${m}:${String(Math.round((minPerKm - m) * 60)).padStart(2, '0')}`
}

const STRENGTH_TYPES = new Set(['strength_training', 'indoor_cardio', 'yoga', 'pilates'])

export default function WorkoutDetailPage() {
  const { id } = useParams()
  const { data, isLoading, error } = useQuery({
    queryKey: ['workout', id],
    queryFn: () => apiGet<WorkoutDetail>(`/api/workouts/${id}`),
  })

  if (isLoading) return <p className="muted">Loading…</p>
  if (error || !data) return <p className="error-text">Failed to load: {String(error)}</p>

  const a = data.activity
  const isStrength = STRENGTH_TYPES.has(a.type ?? '') || data.sets.length > 0

  return (
    <>
      <p style={{ margin: '8px 4px 0' }}>
        <Link to="/workouts" className="muted" style={{ textDecoration: 'none' }}>
          ‹ Workouts
        </Link>
      </p>
      <h1>{a.name ?? a.type}</h1>
      {isStrength && <WorkoutActions detail={data} workoutId={id!} />}
      <div className="metric-grid">
        <div className="metric-card">
          <div className="label">Duration</div>
          <div className="value">{fmtDuration(a.duration_min)}</div>
        </div>
        {a.distance_km != null && (
          <div className="metric-card">
            <div className="label">Distance</div>
            <div className="value">{a.distance_km.toFixed(1)} km</div>
          </div>
        )}
        {a.avg_speed_mps != null && a.type !== 'cycling' && (
          <div className="metric-card">
            <div className="label">Pace</div>
            <div className="value">{pace(a.avg_speed_mps)}</div>
            <div className="sub">min/km</div>
          </div>
        )}
        {a.avg_speed_mps != null && a.type === 'cycling' && (
          <div className="metric-card">
            <div className="label">Speed</div>
            <div className="value">{(a.avg_speed_mps * 3.6).toFixed(1)}</div>
            <div className="sub">km/h avg</div>
          </div>
        )}
        <div className="metric-card">
          <div className="label">Calories</div>
          <div className="value">{a.calories ?? '–'}</div>
        </div>
        <div className="metric-card">
          <div className="label">Heart rate</div>
          <div className="value">{a.avg_hr ?? '–'}</div>
          <div className="sub">{a.max_hr ? `max ${a.max_hr}` : ''}</div>
        </div>
        {a.elevation_gain_m != null && (
          <div className="metric-card">
            <div className="label">Elevation</div>
            <div className="value">{Math.round(a.elevation_gain_m)} m</div>
          </div>
        )}
        {a.training_load != null && (
          <div className="metric-card">
            <div className="label">Load</div>
            <div className="value">{Math.round(a.training_load)}</div>
            <div className="sub">{a.training_effect_label?.toLowerCase().replace(/_/g, ' ') ?? ''}</div>
          </div>
        )}
        {a.aerobic_te != null && (
          <div className="metric-card">
            <div className="label">Aerobic TE</div>
            <div className="value">{a.aerobic_te.toFixed(1)}</div>
          </div>
        )}
      </div>

      {a.avg_hr != null && <HrZonesSection workoutId={id!} />}
      {isStrength ? <SetsSection detail={data} workoutId={id!} /> : <LapsSection workoutId={id!} type={a.type} />}
    </>
  )
}

function WorkoutActions({ detail, workoutId }: { detail: WorkoutDetail; workoutId: string }) {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const a = detail.activity

  const repeat = useMutation({
    mutationFn: () =>
      apiPost<SessionPayload>('/api/workouts/sessions', { repeat_workout_id: Number(workoutId) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['active-session'] })
      navigate('/workouts/active')
    },
  })

  const saveRoutine = useMutation({
    mutationFn: (name: string) => apiPost(`/api/routines/from-workout/${workoutId}`, { name }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['routines'] }),
  })

  return (
    <div className="row" style={{ marginBottom: 12 }}>
      {a.source === 'app' && a.status === 'finished' && (
        <Link to={`/workouts/${workoutId}/summary`} style={{ display: 'flex' }}>
          <button className="secondary" style={{ width: '100%' }}>Summary</button>
        </Link>
      )}
      {detail.sets.length > 0 && (
        <>
          <button onClick={() => repeat.mutate()} disabled={repeat.isPending}>
            ↻ Repeat
          </button>
          <button
            className="secondary"
            disabled={saveRoutine.isPending || saveRoutine.isSuccess}
            onClick={() => {
              const name = window.prompt('Routine name:', a.name ?? '')
              if (name && name.trim().length >= 2) saveRoutine.mutate(name.trim())
            }}
          >
            {saveRoutine.isSuccess ? '✓ Saved' : 'Save as routine'}
          </button>
        </>
      )}
      {(repeat.isError || saveRoutine.isError) && (
        <p className="error-text">
          {String(repeat.error ?? saveRoutine.error).replace(/^\d+: /, '').slice(0, 120)}
        </p>
      )}
    </div>
  )
}

const ZONE_COLORS = ['#64748b', '#38bdf8', '#4ade80', '#fbbf24', '#f87171']

function HrZonesSection({ workoutId }: { workoutId: string }) {
  const { data } = useQuery({
    queryKey: ['hr-zones', workoutId],
    queryFn: () => apiGet<HrZone[]>(`/api/workouts/${workoutId}/hr-zones`),
  })
  if (!data?.length) return null
  const total = data.reduce((a, z) => a + (z.secs_in_zone ?? 0), 0)
  if (total === 0) return null
  return (
    <div className="card">
      <h2 style={{ marginTop: 0 }}>Heart rate zones</h2>
      {data.map((z) => {
        const secs = z.secs_in_zone ?? 0
        const pct = (secs / total) * 100
        const m = Math.floor(secs / 60)
        const s = Math.round(secs % 60)
        return (
          <div key={z.zone_number} className="row" style={{ marginBottom: 6, gap: 8 }}>
            <span className="muted fixed" style={{ width: 24 }}>
              Z{z.zone_number}
            </span>
            <div style={{ flex: 1, background: '#334155', borderRadius: 4, height: 14 }}>
              <div
                style={{
                  width: `${Math.max(pct, secs > 0 ? 2 : 0)}%`,
                  background: ZONE_COLORS[z.zone_number - 1] ?? '#64748b',
                  height: 14,
                  borderRadius: 4,
                }}
              />
            </div>
            <span className="muted fixed" style={{ width: 52, textAlign: 'right', fontSize: '0.75rem' }}>
              {m}:{String(s).padStart(2, '0')}
            </span>
          </div>
        )
      })}
    </div>
  )
}

function LapsSection({ workoutId, type }: { workoutId: string; type: string | null }) {
  const { data, isLoading } = useQuery({
    queryKey: ['laps', workoutId],
    queryFn: () => apiGet<Lap[]>(`/api/workouts/${workoutId}/laps`),
  })
  if (isLoading) return <p className="muted">Loading laps…</p>
  if (!data?.length) return null
  return (
    <div className="card">
      <h2 style={{ marginTop: 0 }}>Laps</h2>
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Time</th>
            <th>Dist</th>
            <th>{type === 'cycling' ? 'km/h' : 'Pace'}</th>
            <th>HR</th>
            <th>Elev</th>
          </tr>
        </thead>
        <tbody>
          {data.map((l) => (
            <tr key={l.lap_index}>
              <td>{l.lap_index}</td>
              <td>{fmtLapTime(l.duration_s)}</td>
              <td>{l.distance_km != null ? `${l.distance_km.toFixed(2)}` : '–'}</td>
              <td>
                {type === 'cycling'
                  ? l.avg_speed_mps != null
                    ? (l.avg_speed_mps * 3.6).toFixed(1)
                    : '–'
                  : pace(l.avg_speed_mps)}
              </td>
              <td>{l.avg_hr ?? '–'}</td>
              <td>{l.elevation_gain_m != null ? `${Math.round(l.elevation_gain_m)}m` : '–'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function SetsSection({ detail, workoutId }: { detail: WorkoutDetail; workoutId: string }) {
  const qc = useQueryClient()
  const [exerciseQuery, setExerciseQuery] = useState('')
  const [exerciseId, setExerciseId] = useState<number | null>(null)
  const [reps, setReps] = useState('')
  const [weight, setWeight] = useState('')

  const exercises = useQuery({
    queryKey: ['exercises'],
    queryFn: () => apiGet<Exercise[]>('/api/exercises'),
  })

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['workout', workoutId] })
    qc.invalidateQueries({ queryKey: ['strength-analytics'] })
  }

  const addSet = useMutation({
    mutationFn: () =>
      apiPost(`/api/workouts/${workoutId}/sets`, {
        exercise_id: exerciseId,
        reps: parseInt(reps),
        weight_kg: weight ? parseFloat(weight) : null,
      }),
    onSuccess: () => {
      setReps('')
      invalidate()
    },
  })

  const removeSet = useMutation({
    mutationFn: (setId: number) => apiDelete(`/api/workouts/sets/${setId}`),
    onSuccess: invalidate,
  })

  const filtered = (exercises.data ?? []).filter((e) =>
    e.name.toLowerCase().includes(exerciseQuery.toLowerCase()),
  )
  const selected = (exercises.data ?? []).find((e) => e.id === exerciseId)

  return (
    <>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Sets · {detail.tonnage_kg.toFixed(0)} kg total</h2>
        {detail.sets.length === 0 && <p className="muted">No sets logged yet.</p>}
        {detail.sets.map((s) => (
          <div key={s.id} className="list-item" style={s.is_warmup ? { opacity: 0.6 } : undefined}>
            <div className="main">
              <div className="name">
                {s.exercise_name} {s.is_warmup ? <span className="badge warm-badge">warm-up</span> : null}{' '}
                {s.is_pr && <span className="badge pr">PR</span>}
              </div>
              <div className="detail">
                {s.weight_kg != null ? `${s.weight_kg}kg × ` : ''}
                {s.reps} reps
                {s.e1rm != null && !s.is_warmup ? ` · e1RM ${s.e1rm}kg` : ''}
                {s.note ? ` · ${s.note}` : ''}
              </div>
            </div>
            <button className="del" onClick={() => removeSet.mutate(s.id)}>
              ✕
            </button>
          </div>
        ))}
      </div>

      <div className="card">
        <h2 style={{ marginTop: 0 }}>Add set</h2>
        {!selected ? (
          <>
            <input
              placeholder="Search exercise…"
              value={exerciseQuery}
              onChange={(e) => setExerciseQuery(e.target.value)}
              style={{ width: '100%' }}
            />
            {exerciseQuery.length >= 2 &&
              filtered.slice(0, 6).map((e) => (
                <div
                  key={e.id}
                  className="list-item"
                  style={{ cursor: 'pointer' }}
                  onClick={() => setExerciseId(e.id)}
                >
                  <div className="main">
                    <div className="name">{e.name}</div>
                    <div className="detail">
                      {e.category}
                      {e.equipment ? ` · ${e.equipment}` : ''}
                    </div>
                  </div>
                </div>
              ))}
          </>
        ) : (
          <>
            <div className="row" style={{ marginBottom: 8 }}>
              <strong>{selected.name}</strong>
              <button className="secondary fixed" onClick={() => setExerciseId(null)}>
                Change
              </button>
            </div>
            <div className="row">
              <input
                type="number"
                inputMode="decimal"
                placeholder="kg"
                value={weight}
                onChange={(e) => setWeight(e.target.value)}
              />
              <input
                type="number"
                inputMode="numeric"
                placeholder="reps"
                value={reps}
                onChange={(e) => setReps(e.target.value)}
              />
              <button className="fixed" onClick={() => addSet.mutate()} disabled={addSet.isPending || !reps}>
                Add
              </button>
            </div>
          </>
        )}
      </div>
    </>
  )
}
