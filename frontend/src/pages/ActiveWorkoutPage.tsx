import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiDelete, apiGet, apiPost } from '../api/client'
import type {
  Exercise,
  ExerciseGhost,
  PlannedExercise,
  SessionPayload,
  SetLogResult,
  WorkoutSetBase,
  WorkoutSummary,
} from '../api/types'
import ExercisePicker from '../components/ExercisePicker'
import RestTimerBar, { clearRestTimer, startRestTimer } from '../components/RestTimerBar'

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

  const session = data?.active ?? null
  const workoutId = session?.activity.id

  const exercises = useMemo(() => {
    if (!session) return []
    const seen = new Set(session.planned_exercises.map((p) => p.exercise_id))
    return [...session.planned_exercises, ...extraExercises.filter((e) => !seen.has(e.exercise_id))]
  }, [session, extraExercises])

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
      <div className="workout-header">
        <div>
          <h1 style={{ margin: 0 }}>{session.activity.name}</h1>
          <div className="muted" style={{ fontSize: '0.8rem' }}>
            {elapsed} · {totalWorking} sets · {Math.round(tonnage)} kg
          </div>
        </div>
        <div className="row fixed" style={{ gap: 6 }}>
          <button
            className="secondary fixed"
            onClick={() => {
              if (window.confirm('Discard this workout and all its sets?')) discard.mutate()
            }}
          >
            Discard
          </button>
          <button
            className="fixed finish-btn"
            onClick={() => finish.mutate()}
            disabled={finish.isPending}
          >
            ✓ Finish
          </button>
        </div>
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
        />
      ))}

      <button className="secondary add-exercise-btn" onClick={() => setShowPicker(true)}>
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

function ExerciseCard({
  exercise,
  workoutId,
  sets,
  ghost,
  results,
  onLogged,
  onDeleted,
}: {
  exercise: PlannedExercise
  workoutId: number
  sets: WorkoutSetBase[]
  ghost: ExerciseGhost | undefined
  results: Record<number, SetLogResult>
  onLogged: (res: SetLogResult) => void
  onDeleted: () => void
}) {
  const [weight, setWeight] = useState('')
  const [reps, setReps] = useState('')
  const [warmup, setWarmup] = useState(false)
  const [showNote, setShowNote] = useState(false)
  const [note, setNote] = useState('')

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

  const canLog = (reps !== '' && parseInt(reps) > 0) || ghostReps !== ''

  return (
    <div className="card exercise-card">
      <div className="row" style={{ justifyContent: 'space-between', marginBottom: 4 }}>
        <strong>{exercise.name}</strong>
        {ghost && lastBest && (
          <span className="muted fixed" style={{ fontSize: '0.75rem' }}>
            Last: {lastBest.weight_kg != null ? `${lastBest.weight_kg} kg × ` : ''}
            {lastBest.reps} ({ghost.date.slice(5)})
          </span>
        )}
      </div>

      {sets.map((s) => {
        const res = results[s.id]
        const num = sets.filter((x) => x.is_warmup === s.is_warmup && x.id <= s.id).length
        return (
          <div key={s.id} className={`set-row logged ${s.is_warmup ? 'warmup' : ''}`}>
            <span className={`set-num ${s.is_warmup ? 'warm' : ''}`}>{s.is_warmup ? 'W' : num}</span>
            <span className="set-values">
              {s.weight_kg != null ? `${s.weight_kg} kg` : 'BW'} × {s.reps}
            </span>
            {res && <DeltaChips result={res} />}
            {s.note && <span className="muted set-note-text">{s.note}</span>}
            <button className="del" onClick={() => del.mutate(s.id)}>✕</button>
          </div>
        )
      })}

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
  )
}
