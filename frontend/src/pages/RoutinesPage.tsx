import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { apiDelete, apiGet, apiPost, apiPut } from '../api/client'
import type { Exercise, Routine, SessionPayload } from '../api/types'
import ExercisePicker from '../components/ExercisePicker'

export default function RoutinesPage() {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [editing, setEditing] = useState<Routine | 'new' | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['routines'],
    queryFn: () => apiGet<Routine[]>('/api/routines'),
  })

  const start = useMutation({
    mutationFn: (routineId: number) =>
      apiPost<SessionPayload>('/api/workouts/sessions', { routine_id: routineId }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['active-session'] })
      navigate('/workouts/active')
    },
  })

  if (editing) {
    return (
      <RoutineEditor
        routine={editing === 'new' ? null : editing}
        onDone={() => {
          setEditing(null)
          qc.invalidateQueries({ queryKey: ['routines'] })
        }}
      />
    )
  }

  return (
    <>
      <p style={{ margin: '8px 4px 0' }}>
        <Link to="/workouts" className="muted" style={{ textDecoration: 'none' }}>
          ‹ Workouts
        </Link>
      </p>
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <h1>Routines</h1>
        <button className="fixed" onClick={() => setEditing('new')}>+ New</button>
      </div>
      {isLoading && <p className="muted">Loading…</p>}
      {data?.length === 0 && (
        <p className="muted">
          No routines yet. Create one here, or open a past workout and tap "Save as routine".
        </p>
      )}
      {(data ?? []).map((r) => (
        <div key={r.id} className="card">
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <div>
              <strong>{r.name}</strong>
              <div className="muted" style={{ fontSize: '0.78rem' }}>
                {r.exercises.map((e) => e.name).join(' · ') || 'No exercises'}
              </div>
            </div>
            <div className="row fixed" style={{ gap: 6 }}>
              <button className="secondary fixed" onClick={() => setEditing(r)}>Edit</button>
              <button className="fixed" onClick={() => start.mutate(r.id)} disabled={start.isPending}>
                Start
              </button>
            </div>
          </div>
          {r.last_used_at && (
            <div className="muted" style={{ fontSize: '0.72rem', marginTop: 4 }}>
              Last used {r.last_used_at.slice(0, 10)}
            </div>
          )}
        </div>
      ))}
      {start.isError && (
        <p className="error-text">{String(start.error).replace(/^\d+: /, '').slice(0, 120)}</p>
      )}
    </>
  )
}

function RoutineEditor({ routine, onDone }: { routine: Routine | null; onDone: () => void }) {
  const [name, setName] = useState(routine?.name ?? '')
  const [exercises, setExercises] = useState(routine?.exercises ?? [])
  const [showPicker, setShowPicker] = useState(false)

  const save = useMutation({
    mutationFn: () => {
      const body = {
        name: name.trim(),
        exercises: exercises.map((e) => ({ exercise_id: e.exercise_id, target_sets: e.target_sets })),
      }
      return routine ? apiPut(`/api/routines/${routine.id}`, body) : apiPost('/api/routines', body)
    },
    onSuccess: onDone,
  })

  const del = useMutation({
    mutationFn: () => apiDelete(`/api/routines/${routine!.id}`),
    onSuccess: onDone,
  })

  const move = (i: number, dir: -1 | 1) => {
    const j = i + dir
    if (j < 0 || j >= exercises.length) return
    const next = [...exercises]
    ;[next[i], next[j]] = [next[j], next[i]]
    setExercises(next)
  }

  const addExercise = (ex: Exercise) => {
    setShowPicker(false)
    if (exercises.some((e) => e.exercise_id === ex.id)) return
    setExercises((p) => [...p, { exercise_id: ex.id, name: ex.name, target_sets: 3 }])
  }

  return (
    <>
      <h1>{routine ? 'Edit routine' : 'New routine'}</h1>
      <div className="card">
        <input
          placeholder="Routine name (e.g. Push, Pull, Legs)"
          value={name}
          onChange={(e) => setName(e.target.value)}
          style={{ width: '100%', marginBottom: 8 }}
        />
        {exercises.map((e, i) => (
          <div key={e.exercise_id} className="list-item">
            <div className="main">
              <div className="name">{e.name}</div>
              <div className="detail">{e.target_sets} sets</div>
            </div>
            <input
              type="number"
              inputMode="numeric"
              value={e.target_sets}
              min={1}
              max={20}
              style={{ width: 56, padding: 6 }}
              onChange={(ev) => {
                const v = Math.max(1, Math.min(20, parseInt(ev.target.value) || 1))
                setExercises((p) => p.map((x, xi) => (xi === i ? { ...x, target_sets: v } : x)))
              }}
            />
            <button className="secondary fixed" style={{ padding: '6px 10px' }} onClick={() => move(i, -1)}>↑</button>
            <button className="secondary fixed" style={{ padding: '6px 10px' }} onClick={() => move(i, 1)}>↓</button>
            <button className="del" onClick={() => setExercises((p) => p.filter((_, xi) => xi !== i))}>✕</button>
          </div>
        ))}
        <button className="secondary" style={{ width: '100%', marginTop: 8 }} onClick={() => setShowPicker(true)}>
          + Add exercise
        </button>
      </div>
      {save.isError && (
        <p className="error-text">{String(save.error).replace(/^\d+: /, '').slice(0, 120)}</p>
      )}
      <div className="row">
        <button className="secondary" onClick={onDone}>Cancel</button>
        {routine && (
          <button
            className="secondary"
            style={{ color: 'var(--red)' }}
            onClick={() => {
              if (window.confirm(`Delete routine "${routine.name}"?`)) del.mutate()
            }}
          >
            Delete
          </button>
        )}
        <button onClick={() => save.mutate()} disabled={name.trim().length < 2 || save.isPending}>
          Save
        </button>
      </div>
      {showPicker && <ExercisePicker onPick={addExercise} onClose={() => setShowPicker(false)} />}
    </>
  )
}
