import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, BarChart2, Check, ChevronRight } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useNavigate } from 'react-router-dom'
import { apiDelete, apiGet, apiPost, apiPut } from '../api/client'
import type {
  Exercise,
  ExerciseGhost,
  ExerciseStatsDetail,
  PlannedExercise,
  SessionPayload,
  SetLogResult,
  WorkoutSetBase,
  WorkoutSummary,
} from '../api/types'
import BottomSheet from '../components/BottomSheet'
import ExercisePicker from '../components/ExercisePicker'
import RestTimerBar, { clearRestTimer, startRestTimer } from '../components/RestTimerBar'
import SwipeToDelete from '../components/SwipeToDelete'

function useElapsed(startTs: string | null) {
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [])
  if (!startTs) return '0:00'
  const secs = Math.max(0, Math.floor((now - new Date(startTs).getTime()) / 1000))
  const h = Math.floor(secs / 3600)
  const m = Math.floor((secs % 3600) / 60)
  const s = secs % 60
  return h > 0 ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}` : `${m}:${String(s).padStart(2, '0')}`
}

export default function ActiveWorkoutPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: ['active-session'],
    queryFn: () => apiGet<{ active: SessionPayload | null }>('/api/workouts/sessions/active'),
  })

  const [extraExercises, setExtraExercises] = useState<PlannedExercise[]>([])
  const [extraGhosts, setExtraGhosts] = useState<Record<string, ExerciseGhost>>({})
  const [results, setResults] = useState<Record<number, SetLogResult>>({})
  const [showPicker, setShowPicker] = useState(false)
  const [removedExerciseIds, setRemovedExerciseIds] = useState<Set<number>>(new Set())

  const session = data?.active ?? null
  const workoutId = session?.activity.id

  const exercises = useMemo(() => {
    if (!session) return []
    const seen = new Set(session.planned_exercises.map((p) => p.exercise_id))
    const all = [...session.planned_exercises, ...extraExercises.filter((e) => !seen.has(e.exercise_id))]
    return all.filter((e) => !removedExerciseIds.has(e.exercise_id))
  }, [session, extraExercises, removedExerciseIds])

  const ghosts: Record<string, ExerciseGhost> = { ...(session?.ghosts ?? {}), ...extraGhosts }
  const sets: WorkoutSetBase[] = session?.sets ?? []
  const elapsed = useElapsed(session?.activity.start_ts ?? null)

  const finish = useMutation({
    mutationFn: () => apiPost<WorkoutSummary>(`/api/workouts/sessions/${workoutId}/finish`),
    onSuccess: (s) => {
      clearRestTimer()
      qc.invalidateQueries({ queryKey: ['active-session'] })
      qc.invalidateQueries({ queryKey: ['workouts'] })
      navigate(`/workouts/${s.workout_id}/summary`)
    },
  })

  const discard = useMutation({
    mutationFn: () => apiDelete(`/api/workouts/sessions/${workoutId}`),
    onSuccess: () => {
      clearRestTimer()
      qc.invalidateQueries({ queryKey: ['active-session'] })
      qc.invalidateQueries({ queryKey: ['workouts'] })
      navigate('/workouts')
    },
  })

  const addExercise = async (ex: Exercise) => {
    setShowPicker(false)
    setRemovedExerciseIds((s) => { const n = new Set(s); n.delete(ex.id); return n })
    if (exercises.some((e) => e.exercise_id === ex.id)) return
    setExtraExercises((p) => [...p, { exercise_id: ex.id, name: ex.name, target_sets: 3 }])
    try {
      const g = await apiGet<Record<string, ExerciseGhost>>(
        `/api/exercises/last-session?ids=${ex.id}&exclude=${workoutId}`,
      )
      setExtraGhosts((p) => ({ ...p, ...g }))
    } catch {
      // ghost data is optional
    }
  }

  if (isLoading) return <p className="muted">Loading…</p>
  if (!session) {
    return (
      <>
        <h1>Workout</h1>
        <p className="muted">No workout in progress.</p>
        <button onClick={() => navigate('/workouts')}>Back to workouts</button>
      </>
    )
  }

  const totalWorking = sets.filter((s) => !s.is_warmup).length
  const tonnage = sets.filter((s) => !s.is_warmup).reduce((a, s) => a + (s.weight_kg ?? 0) * s.reps, 0)

  return (
    <>
      {/* Workout-specific header */}
      <div className="workout-header" style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 8,
        marginBottom: 12,
      }}>
        <button
          className="secondary"
          style={{ minWidth: 44, minHeight: 44, padding: 8, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          onClick={() => {
            if (window.confirm('Discard this workout and all its sets?')) discard.mutate()
          }}
          title="Discard workout"
        >
          <ArrowLeft size={20} />
        </button>
        <div style={{ flex: 1, textAlign: 'center' }}>
          <div className="text-title" style={{ fontWeight: 600, lineHeight: 1.2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {session.activity.name}
          </div>
          <div className="text-caption" style={{ color: 'var(--muted)' }}>
            {elapsed} · {totalWorking} sets · {Math.round(tonnage)} kg
          </div>
        </div>
        <button
          className="finish-btn"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '10px 16px',
            minHeight: 44,
            background: 'var(--accent)',
            borderRadius: 10,
            fontWeight: 600,
          }}
          onClick={() => finish.mutate()}
          disabled={finish.isPending}
        >
          <Check size={16} /> Finish
        </button>
      </div>

      {exercises.map((ex) => (
        <ExerciseCard
          key={ex.exercise_id}
          exercise={ex}
          workoutId={workoutId!}
          sets={sets.filter((s) => s.exercise_id === ex.exercise_id)}
          ghost={ghosts[String(ex.exercise_id)]}
          results={results}
          onLogged={(res) => {
            setResults((r) => ({ ...r, [res.set.id]: res }))
            startRestTimer()
            qc.invalidateQueries({ queryKey: ['active-session'] })
          }}
          onDeleted={() => qc.invalidateQueries({ queryKey: ['active-session'] })}
          onExerciseRemoved={() => {
            setRemovedExerciseIds((s) => new Set(s).add(ex.exercise_id))
            qc.invalidateQueries({ queryKey: ['active-session'] })
          }}
        />
      ))}

      <button
        className="secondary add-exercise-btn"
        style={{ width: '100%', marginBottom: 100 }}
        onClick={() => setShowPicker(true)}
      >
        + Add exercise
      </button>

      {showPicker && <ExercisePicker onPick={addExercise} onClose={() => setShowPicker(false)} />}
      <RestTimerBar />
    </>
  )
}

function DeltaChips({ result }: { result: SetLogResult }) {
  const chips = []
  if (result.is_pr) chips.push(<span key="pr" className="badge pr">PR</span>)
  if (result.delta_weight_kg != null && result.delta_weight_kg !== 0) {
    const up = result.delta_weight_kg > 0
    chips.push(
      <span key="w" className={`delta ${up ? 'up' : 'down'}`}>
        {up ? '▲' : '▼'} {Math.abs(result.delta_weight_kg)} kg
      </span>,
    )
  }
  if (result.delta_reps != null && result.delta_reps !== 0) {
    const up = result.delta_reps > 0
    chips.push(
      <span key="r" className={`delta ${up ? 'up' : 'down'}`}>
        {up ? '▲' : '▼'} {Math.abs(result.delta_reps)} rep{Math.abs(result.delta_reps) > 1 ? 's' : ''}
      </span>,
    )
  }
  if (
    chips.length === 0 &&
    (result.delta_weight_kg === 0 || result.delta_reps === 0) &&
    (result.delta_weight_kg != null || result.delta_reps != null)
  ) {
    chips.push(<span key="m" className="delta same">= last</span>)
  }
  return <span className="delta-chips">{chips}</span>
}

const axisStyle = { fontSize: 10, fill: '#94a3b8' }
const tooltipStyle = {
  contentStyle: { background: '#1e293b', border: '1px solid #334155', borderRadius: 8 },
  labelStyle: { color: '#94a3b8' },
}

function ExerciseStatsSheet({ exerciseId, onClose }: { exerciseId: number; onClose: () => void }) {
  const { data, isLoading } = useQuery({
    queryKey: ['exercise-stats-quick', exerciseId],
    queryFn: () => apiGet<ExerciseStatsDetail>(`/api/workouts/analytics/exercises/${exerciseId}?range=6m`),
  })

  const sessions = data ? [...data.sessions].sort((a, b) => (a.date < b.date ? -1 : 1)) : []
  const recent = [...sessions].reverse().slice(0, 3)
  const chartData = sessions.map((s) => ({ date: s.date, e1rm: s.best_e1rm }))

  return (
    <BottomSheet open onClose={onClose} title={data?.exercise.name ?? 'Stats'}>
      <div style={{ padding: '0 16px 16px' }}>
        {isLoading && <p className="muted">Loading…</p>}

        {data?.prs.best_e1rm && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '12px 0',
            borderBottom: '1px solid var(--border)',
          }}>
            <span className="badge pr" style={{ fontSize: '0.7rem' }}>PR</span>
            <span className="text-body">
              Best e1RM: <strong>{data.prs.best_e1rm.e1rm} kg</strong>
            </span>
            <span className="text-caption" style={{ color: 'var(--muted)' }}>
              ({data.prs.best_e1rm.weight_kg}×{data.prs.best_e1rm.reps} on {data.prs.best_e1rm.date})
            </span>
          </div>
        )}

        {recent.length > 0 && (
          <div style={{ paddingTop: 12, paddingBottom: 12, borderBottom: '1px solid var(--border)' }}>
            <div className="text-caption" style={{ color: 'var(--muted)', marginBottom: 8 }}>Recent sessions</div>
            {recent.map((s) => (
              <div key={s.activity_id} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <span className="text-caption">{s.date}</span>
                <span className="text-body">{s.sets.filter(x => !x.is_top).map(x => `${x.weight_kg ?? 'BW'}×${x.reps}`).join(', ') || `${s.num_sets} sets`}</span>
              </div>
            ))}
          </div>
        )}

        {chartData.some(d => d.e1rm != null) && (
          <div style={{ paddingTop: 12 }}>
            <div className="text-caption" style={{ color: 'var(--muted)', marginBottom: 8 }}>e1RM trend</div>
            <LineChart width={320} height={120} data={chartData}>
              <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
              <XAxis dataKey="date" tickFormatter={(d: string) => d.slice(5)} tick={axisStyle} minTickGap={30} />
              <YAxis tick={axisStyle} width={35} domain={['auto', 'auto']} />
              <Tooltip {...tooltipStyle} />
              <Line dataKey="e1rm" stroke="#4ade80" strokeWidth={2} dot={false} name="e1RM" />
            </LineChart>
          </div>
        )}
      </div>
    </BottomSheet>
  )
}

function ExerciseCard({
  exercise,
  workoutId,
  sets,
  ghost,
  results,
  onLogged,
  onDeleted,
  onExerciseRemoved,
}: {
  exercise: PlannedExercise
  workoutId: number
  sets: WorkoutSetBase[]
  ghost: ExerciseGhost | undefined
  results: Record<number, SetLogResult>
  onLogged: (res: SetLogResult) => void
  onDeleted: () => void
  onExerciseRemoved: () => void
}) {
  const [weight, setWeight] = useState('')
  const [reps, setReps] = useState('')
  const [warmup, setWarmup] = useState(false)
  const [showNote, setShowNote] = useState(false)
  const [note, setNote] = useState('')
  const [editingSetId, setEditingSetId] = useState<number | null>(null)
  const [editWeight, setEditWeight] = useState('')
  const [editReps, setEditReps] = useState('')
  const [showStats, setShowStats] = useState(false)
  const qc = useQueryClient()

  const workingLogged = sets.filter((s) => !s.is_warmup).length
  const nextGhost = warmup ? undefined : ghost?.sets[workingLogged]
  const ghostWeight = nextGhost?.weight_kg != null ? String(nextGhost.weight_kg) : ''
  const ghostReps = nextGhost != null ? String(nextGhost.reps) : ''

  const lastBest = ghost?.sets.length
    ? ghost.sets.reduce((a, b) => ((b.weight_kg ?? 0) > (a.weight_kg ?? 0) ? b : a))
    : null

  const log = useMutation({
    mutationFn: () => {
      const w = weight !== '' ? parseFloat(weight) : ghostWeight !== '' ? parseFloat(ghostWeight) : null
      const r = reps !== '' ? parseInt(reps) : ghostReps !== '' ? parseInt(ghostReps) : NaN
      return apiPost<SetLogResult>(`/api/workouts/${workoutId}/sets`, {
        exercise_id: exercise.exercise_id,
        reps: r,
        weight_kg: w,
        is_warmup: warmup ? 1 : 0,
        note: note.trim() || null,
      })
    },
    onSuccess: (res) => {
      setWeight('')
      setReps('')
      setNote('')
      setShowNote(false)
      setWarmup(false)
      onLogged(res)
    },
  })

  const del = useMutation({
    mutationFn: (setId: number) => apiDelete(`/api/workouts/sets/${setId}`),
    onSuccess: onDeleted,
  })

  const updateSet = useMutation({
    mutationFn: ({ setId, weight_kg, reps }: { setId: number; weight_kg: number | null; reps: number }) =>
      apiPut(`/api/workouts/sets/${setId}`, { weight_kg, reps }),
    onSuccess: () => {
      setEditingSetId(null)
      qc.invalidateQueries({ queryKey: ['active-session'] })
    },
  })

  const removeExercise = useMutation({
    mutationFn: () => apiDelete(`/api/workouts/${workoutId}/exercises/${exercise.exercise_id}/sets`),
    onSuccess: onExerciseRemoved,
  })

  const canLog = (reps !== '' && parseInt(reps) > 0) || ghostReps !== ''

  const startEdit = (s: WorkoutSetBase) => {
    setEditingSetId(s.id)
    setEditWeight(s.weight_kg != null ? String(s.weight_kg) : '')
    setEditReps(String(s.reps))
  }

  const saveEdit = (s: WorkoutSetBase) => {
    const w = editWeight !== '' ? parseFloat(editWeight) : null
    const r = parseInt(editReps)
    if (!isNaN(r) && r > 0) {
      updateSet.mutate({ setId: s.id, weight_kg: w, reps: r })
    } else {
      setEditingSetId(null)
    }
  }

  return (
    <>
      <SwipeToDelete
        onDelete={() => {
          if (window.confirm(`Remove ${exercise.name} and all its sets?`)) removeExercise.mutate()
        }}
      >
        <div className="card exercise-card">
          {/* Exercise header */}
          <div className="row" style={{ justifyContent: 'space-between', marginBottom: 4 }}>
            <button
              onClick={() => setShowStats(true)}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--text)',
                padding: 0,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                flex: 1,
                minHeight: 44,
                textAlign: 'left',
              }}
            >
              <strong style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {exercise.name}
              </strong>
              <BarChart2 size={14} color="var(--muted)" />
            </button>
            {ghost && lastBest && (
              <span className="muted" style={{ fontSize: '0.75rem', flexShrink: 0 }}>
                Last: {lastBest.weight_kg != null ? `${lastBest.weight_kg} kg × ` : ''}
                {lastBest.reps} ({ghost.date.slice(5)})
              </span>
            )}
          </div>

          {/* Logged sets */}
          {sets.map((s) => {
            const num = sets.filter((x) => x.is_warmup === s.is_warmup && x.id <= s.id).length
            let res = results[s.id]
            if (!res && !s.is_warmup && ghost) {
              const prev = ghost.sets.find((g) => g.set_number === num)
              if (prev) {
                res = {
                  set: s,
                  e1rm: null,
                  is_pr: false,
                  delta_weight_kg:
                    s.weight_kg != null && prev.weight_kg != null
                      ? Math.round((s.weight_kg - prev.weight_kg) * 100) / 100
                      : null,
                  delta_reps: s.reps - prev.reps,
                }
              }
            }

            const isEditing = editingSetId === s.id

            return (
              <SwipeToDelete key={s.id} onDelete={() => del.mutate(s.id)}>
                {isEditing ? (
                  <div className="set-row logged" style={{ gap: 6, flexWrap: 'wrap' }}>
                    <span className={`set-num ${s.is_warmup ? 'warm' : ''}`}>{s.is_warmup ? 'W' : num}</span>
                    <input
                      type="number"
                      inputMode="decimal"
                      className="set-input"
                      value={editWeight}
                      onChange={(e) => setEditWeight(e.target.value)}
                      placeholder="kg"
                      autoFocus
                      style={{ width: 60 }}
                    />
                    <span className="muted">×</span>
                    <input
                      type="number"
                      inputMode="numeric"
                      className="set-input"
                      value={editReps}
                      onChange={(e) => setEditReps(e.target.value)}
                      placeholder="reps"
                      style={{ width: 52 }}
                    />
                    <button
                      className="log-btn"
                      onClick={() => saveEdit(s)}
                      style={{ padding: '6px 12px', minHeight: 36 }}
                    >
                      <Check size={14} />
                    </button>
                    <button
                      className="secondary"
                      onClick={() => setEditingSetId(null)}
                      style={{ padding: '6px 10px', minHeight: 36, fontSize: '0.8rem' }}
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <div
                    className={`set-row logged ${s.is_warmup ? 'warmup' : ''}`}
                    onClick={() => startEdit(s)}
                    style={{ cursor: 'pointer' }}
                    title="Tap to edit"
                  >
                    <span className={`set-num ${s.is_warmup ? 'warm' : ''}`}>{s.is_warmup ? 'W' : num}</span>
                    <span className="set-values">
                      {s.weight_kg != null ? `${s.weight_kg} kg` : 'BW'} × {s.reps}
                    </span>
                    {res && <DeltaChips result={res} />}
                    {s.note && <span className="muted set-note-text">{s.note}</span>}
                    <ChevronRight size={12} color="var(--muted)" style={{ marginLeft: 'auto', flexShrink: 0 }} />
                  </div>
                )}
              </SwipeToDelete>
            )
          })}

          {/* Log new set row */}
          <div className="set-row input-row">
            <button
              className={`set-num toggle ${warmup ? 'warm active' : ''}`}
              title="Toggle warm-up set"
              onClick={() => setWarmup((v) => !v)}
            >
              {warmup ? 'W' : sets.filter((s) => !s.is_warmup).length + 1}
            </button>
            <input
              type="number"
              inputMode="decimal"
              className="set-input"
              placeholder={ghostWeight || 'kg'}
              value={weight}
              onChange={(e) => setWeight(e.target.value)}
            />
            <span className="muted">×</span>
            <input
              type="number"
              inputMode="numeric"
              className="set-input"
              placeholder={ghostReps || 'reps'}
              value={reps}
              onChange={(e) => setReps(e.target.value)}
            />
            <button className="secondary note-btn" onClick={() => setShowNote((v) => !v)} title="Add note">
              ✎
            </button>
            <button className="log-btn" onClick={() => log.mutate()} disabled={!canLog || log.isPending}>
              ✓
            </button>
          </div>
          {showNote && (
            <input
              placeholder="Set note (e.g. felt heavy, paused reps)"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              style={{ width: '100%', marginTop: 6 }}
            />
          )}
          {log.isError && (
            <p className="error-text">{String(log.error).replace(/^\d+: /, '').slice(0, 120)}</p>
          )}
        </div>
      </SwipeToDelete>

      {showStats && (
        <ExerciseStatsSheet
          exerciseId={exercise.exercise_id}
          onClose={() => setShowStats(false)}
        />
      )}
    </>
  )
}
