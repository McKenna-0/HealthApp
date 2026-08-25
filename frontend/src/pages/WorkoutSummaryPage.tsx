import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Trophy, Watch } from 'lucide-react'
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { apiDelete, apiGet, apiPost } from '../api/client'
import type { Workout, WorkoutSummary } from '../api/types'
import EditableWorkoutName from '../components/EditableWorkoutName'
import MuscleBodyMap from '../components/MuscleBodyMap'

function fmtDuration(min: number | null) {
  if (min == null) return '–'
  const h = Math.floor(min / 60)
  return h > 0 ? `${h}h ${Math.round(min % 60)}m` : `${Math.round(min)}m`
}

export default function WorkoutSummaryPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { data, isLoading, error } = useQuery({
    queryKey: ['workout-summary', id],
    queryFn: () => apiGet<WorkoutSummary>(`/api/workouts/${id}/summary`),
  })

  if (isLoading) return <p className="muted">Loading…</p>
  if (error || !data) return <p className="error-text">Failed to load: {String(error)}</p>

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['workout-summary', id] })
    qc.invalidateQueries({ queryKey: ['workout', id] })
    qc.invalidateQueries({ queryKey: ['workouts'] })
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
        <div style={{ flex: 1, minWidth: 0 }}>
          <h1 className="text-display" style={{ margin: 0 }}>
            <EditableWorkoutName
              workoutId={data.workout_id}
              name={data.name}
              editable={data.source !== 'garmin'}
            />
          </h1>
          <span className="text-caption" style={{ color: 'var(--muted)' }}>{data.date}</span>
        </div>
      </div>

      <div className="card" style={{ padding: '16px 8px 4px' }}>
        <MuscleBodyMap intensities={data.muscles} height={280} />
        <div className="body-map-legend">
          <span><i className="dot hot" /> Primary work</span>
          <span><i className="dot mid" /> Secondary</span>
          <span><i className="dot cold" /> Untrained</span>
        </div>
      </div>

      <div className="metric-grid">
        <div className="metric-card">
          <div className="label">Duration</div>
          <div className="value">{fmtDuration(data.duration_min)}</div>
        </div>
        <div className="metric-card">
          <div className="label">Avg HR</div>
          <div className="value">{data.avg_hr ?? '–'}</div>
          <div className="sub">{data.max_hr ? `max ${data.max_hr}` : ''}</div>
        </div>
        <div className="metric-card">
          <div className="label">Calories</div>
          <div className="value">{data.calories ?? '–'}</div>
        </div>
        <div className="metric-card">
          <div className="label">Tonnage</div>
          <div className="value">{Math.round(data.tonnage_kg)}</div>
          <div className="sub">kg lifted</div>
        </div>
        <div className="metric-card">
          <div className="label">Sets</div>
          <div className="value">{data.total_sets}</div>
          <div className="sub">{data.total_reps} reps</div>
        </div>
        <div className="metric-card">
          <div className="label">Exercises</div>
          <div className="value">{data.exercise_count}</div>
        </div>
      </div>

      {data.prs.length > 0 && (
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <Trophy size={18} color="var(--amber)" />
            <h2 className="text-title" style={{ margin: 0 }}>Personal records</h2>
          </div>
          {data.prs.map((p) => (
            <div key={p.exercise_id} className="list-item">
              <div className="main">
                <div className="text-body name">{p.exercise_name}</div>
                <div className="text-caption detail">
                  {p.weight_kg != null ? `${p.weight_kg} kg × ` : ''}
                  {p.reps}
                  {p.e1rm != null ? ` · e1RM ${p.e1rm} kg` : ''}
                </div>
              </div>
              <span className="badge pr">PR</span>
            </div>
          ))}
        </div>
      )}

      <WatchLinkCard summary={data} workoutId={id!} onChange={invalidate} />

      <button
        className="secondary"
        style={{ width: '100%' }}
        onClick={() => navigate(`/workouts/${id}`)}
      >
        View full workout detail
      </button>
    </>
  )
}

function WatchLinkCard({
  summary,
  workoutId,
  onChange,
}: {
  summary: WorkoutSummary
  workoutId: string
  onChange: () => void
}) {
  const [picking, setPicking] = useState(false)
  const candidates = useQuery({
    queryKey: ['link-candidates', summary.date],
    queryFn: () =>
      apiGet<Workout[]>(`/api/workouts?start=${summary.date}&end=${summary.date}&type=strength_training`),
    enabled: picking,
  })

  const link = useMutation({
    mutationFn: (activityId: number) => apiPost(`/api/workouts/${workoutId}/link/${activityId}`),
    onSuccess: () => {
      setPicking(false)
      onChange()
    },
  })
  const unlink = useMutation({
    mutationFn: () => apiDelete(`/api/workouts/${workoutId}/link`),
    onSuccess: onChange,
  })

  return (
    <div className="card">
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Watch size={16} color="var(--muted)" />
          <h2 className="text-title" style={{ margin: 0 }}>Watch data</h2>
        </div>
        {summary.linked_activity_id != null ? (
          <button className="secondary fixed" onClick={() => unlink.mutate()}>Unlink</button>
        ) : (
          <button className="secondary fixed" onClick={() => setPicking((v) => !v)}>Link activity</button>
        )}
      </div>
      {summary.linked_activity_id != null ? (
        <p className="text-caption" style={{ color: 'var(--muted)', marginBottom: 0 }}>
          Heart rate, calories and duration are from your watch.
        </p>
      ) : (
        <p className="text-caption" style={{ color: 'var(--muted)', marginBottom: 0 }}>
          No watch activity linked. It links automatically when a matching strength activity syncs.
        </p>
      )}
      {picking && (
        <div style={{ marginTop: 8 }}>
          {(candidates.data ?? [])
            .filter((w) => w.source !== 'app')
            .map((w) => (
              <div key={w.id} className="list-item" style={{ cursor: 'pointer' }} onClick={() => link.mutate(w.id)}>
                <div className="main">
                  <div className="text-body name">{w.name ?? w.type}</div>
                  <div className="text-caption detail">
                    {w.start_ts?.slice(11, 16)} · {fmtDuration(w.duration_min)}
                    {w.avg_hr ? ` · ${w.avg_hr} bpm` : ''}
                  </div>
                </div>
                <span className="muted">Link</span>
              </div>
            ))}
          {candidates.data && candidates.data.filter((w) => w.source !== 'app').length === 0 && (
            <p className="muted">No strength activities found on {summary.date}.</p>
          )}
          {link.isError && (
            <p className="error-text">{String(link.error).replace(/^\d+: /, '').slice(0, 120)}</p>
          )}
        </div>
      )}
    </div>
  )
}
