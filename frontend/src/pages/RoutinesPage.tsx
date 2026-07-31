import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, ChevronDown, ChevronUp, Play, Plus } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiDelete, apiGet, apiPost, apiPut } from '../api/client'
import type { Exercise, Routine, SessionPayload } from '../api/types'
import ExercisePicker from '../components/ExercisePicker'
import SwipeToDelete from '../components/SwipeToDelete'

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
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '8px 0 4px' }}>
        <button
          onClick={() => navigate('/workouts')}
          style={{
            background: 'none', border: 'none', color: 'var(--muted)',
            padding: 8, minWidth: 44, minHeight: 44,
            display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer',
          }}
          aria-label="Back"
        >
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-display" style={{ margin: 0, flex: 1 }}>Routines</h1>
        <button
          onClick={() => setEditing('new')}
          style={{ display: 'flex', alignItems: 'center', gap: 6, minHeight: 44 }}
        >
          <Plus size={16} /> New
        </button>
      </div>

      {isLoading && <p className="muted">Loading…</p>}
      {data?.length === 0 && (
        <p className="muted">
          No routines yet. Create one here, or open a past workout and tap "Save as routine".
        </p>
      )}
      {(data ?? []).map((r) => (
        <div key={r.id} className="card" style={{ overflow: 'hidden', padding: 0 }}>
          <div style={{ padding: '14px 16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="text-body" style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {r.name}
                </div>
                <div className="text-caption" style={{ color: 'var(--muted)', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {r.exercises.map((e) => e.name).join(' · ') || 'No exercises'}
                </div>
                {r.last_used_at && (
                  <div className="text-caption" style={{ color: 'var(--muted)', marginTop: 2 }}>
                    Last used {r.last_used_at.slice(0, 10)}
                  </div>
                )}
              </div>
              <div className="row fixed" style={{ gap: 8, flexShrink: 0 }}>
                <button className="secondary fixed" onClick={() => setEditing(r)} style={{ minHeight: 44 }}>
                  Edit
                </button>
                <button
                  onClick={() => start.mutate(r.id)}
                  disabled={start.isPending}
                  style={{ display: 'flex', alignItems: 'center', gap: 6, minHeight: 44 }}
                >
                  <Play size={14} fill="currentColor" /> Start
                </button>
              </div>
            </div>
          </div>
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
      <h1 className="text-display">{routine ? 'Edit routine' : 'New routine'}</h1>
      <div className="card">
        <input
          placeholder="Routine name (e.g. Push, Pull, Legs)"
          value={name}
          onChange={(e) => setName(e.target.value)}
          style={{ width: '100%', marginBottom: 8 }}
        />
        {exercises.map((e, i) => (
          <SwipeToDelete
            key={e.exercise_id}
            onDelete={() => setExercises((p) => p.filter((_, xi) => xi !== i))}
          >
            <div className="list-item">
              <div className="main">
                <div className="text-body name">{e.name}</div>
                <div className="text-caption detail">{e.target_sets} sets</div>
              </div>
              <input
                type="number"
                inputMode="numeric"
                value={e.target_sets}
                min={1}
                max={20}
                style={{ width: 56, padding: 6, fontSize: '1rem' }}
                onChange={(ev) => {
                  const v = Math.max(1, Math.min(20, parseInt(ev.target.value) || 1))
                  setExercises((p) => p.map((x, xi) => (xi === i ? { ...x, target_sets: v } : x)))
                }}
              />
              <button
                className="secondary fixed"
                style={{ padding: '6px 10px', minWidth: 44, minHeight: 44 }}
                onClick={() => move(i, -1)}
                aria-label="Move up"
              >
                <ChevronUp size={16} />
              </button>
              <button
                className="secondary fixed"
                style={{ padding: '6px 10px', minWidth: 44, minHeight: 44 }}
                onClick={() => move(i, 1)}
                aria-label="Move down"
              >
                <ChevronDown size={16} />
              </button>
            </div>
          </SwipeToDelete>
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
