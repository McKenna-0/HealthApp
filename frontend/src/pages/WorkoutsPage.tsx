import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { apiGet } from '../api/client'
import type {
  CardioAnalytics,
  Exercise,
  StrengthAnalytics,
  Workout,
} from '../api/types'
import ChartCard from '../components/ChartCard'

const axisStyle = { fontSize: 10, fill: '#94a3b8' }
const tooltipStyle = {
  contentStyle: { background: '#1e293b', border: '1px solid #334155', borderRadius: 8 },
  labelStyle: { color: '#94a3b8' },
}

const TYPE_ICONS: Record<string, string> = {
  running: '🏃',
  cycling: '🚴',
  strength_training: '🏋️',
  swimming: '🏊',
  walking: '🚶',
  hiking: '🥾',
}

function fmtDuration(min: number | null) {
  if (min == null) return '–'
  const h = Math.floor(min / 60)
  return h > 0 ? `${h}h ${Math.round(min % 60)}m` : `${Math.round(min)}m`
}

export default function WorkoutsPage() {
  const [tab, setTab] = useState<'history' | 'strength' | 'cardio'>('history')
  return (
    <>
      <h1>Workouts</h1>
      <div className="tabs">
        {(['history', 'strength', 'cardio'] as const).map((t) => (
          <button key={t} className={`chip ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>
            {t[0].toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>
      {tab === 'history' && <HistoryTab />}
      {tab === 'strength' && <StrengthTab />}
      {tab === 'cardio' && <CardioTab />}
    </>
  )
}

function HistoryTab() {
  const { data, isLoading } = useQuery({
    queryKey: ['workouts'],
    queryFn: () => apiGet<Workout[]>('/api/workouts?limit=60'),
  })
  if (isLoading) return <p className="muted">Loading…</p>
  if (!data?.length) return <p className="muted">No workouts synced yet.</p>
  return (
    <div className="card">
      {data.map((w) => (
        <Link key={w.id} to={`/workouts/${w.id}`} style={{ textDecoration: 'none', color: 'inherit' }}>
          <div className="list-item">
            <span style={{ fontSize: '1.3rem' }}>{TYPE_ICONS[w.type ?? ''] ?? '💪'}</span>
            <div className="main">
              <div className="name">{w.name ?? w.type}</div>
              <div className="detail">
                {w.date} · {fmtDuration(w.duration_min)}
                {w.distance_km ? ` · ${w.distance_km.toFixed(1)} km` : ''}
                {w.total_sets ? ` · ${w.total_sets} sets` : ''}
                {w.avg_hr ? ` · ${w.avg_hr} bpm` : ''}
              </div>
            </div>
            <span className="muted">›</span>
          </div>
        </Link>
      ))}
    </div>
  )
}

function StrengthTab() {
  const [exerciseId, setExerciseId] = useState<number | ''>('')
  const exercises = useQuery({
    queryKey: ['exercises'],
    queryFn: () => apiGet<Exercise[]>('/api/exercises'),
  })
  const { data } = useQuery({
    queryKey: ['strength-analytics', exerciseId],
    queryFn: () =>
      apiGet<StrengthAnalytics>(
        `/api/workouts/analytics/strength${exerciseId !== '' ? `?exercise_id=${exerciseId}` : ''}`,
      ),
  })

  return (
    <>
      <ChartCard title="Weekly tonnage (kg)">
        <BarChart data={data?.weekly_volume ?? []}>
          <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
          <XAxis dataKey="week" tick={axisStyle} minTickGap={20} />
          <YAxis tick={axisStyle} width={45} />
          <Tooltip {...tooltipStyle} />
          <Bar dataKey="tonnage_kg" fill="#38bdf8" name="Tonnage" />
        </BarChart>
      </ChartCard>

      <ChartCard title="Weekly sets">
        <BarChart data={data?.weekly_volume ?? []}>
          <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
          <XAxis dataKey="week" tick={axisStyle} minTickGap={20} />
          <YAxis tick={axisStyle} width={30} />
          <Tooltip {...tooltipStyle} />
          <Bar dataKey="sets" fill="#a78bfa" name="Sets" />
        </BarChart>
      </ChartCard>

      <div className="card">
        <h2 style={{ marginTop: 0 }}>Exercise progression</h2>
        <select
          value={exerciseId}
          onChange={(e) => setExerciseId(e.target.value === '' ? '' : Number(e.target.value))}
          style={{ width: '100%' }}
        >
          <option value="">Pick an exercise…</option>
          {(exercises.data ?? []).map((e) => (
            <option key={e.id} value={e.id}>
              {e.name}
            </option>
          ))}
        </select>
        {data?.prs?.best_e1rm && (
          <p className="muted" style={{ marginBottom: 0 }}>
            Best e1RM: <strong>{data.prs.best_e1rm.e1rm} kg</strong> ({data.prs.best_e1rm.weight_kg}kg ×{' '}
            {data.prs.best_e1rm.reps} on {data.prs.best_e1rm.date})
          </p>
        )}
      </div>

      {data?.history && data.history.length > 0 && (
        <ChartCard title="Estimated 1RM (kg)">
          <LineChart data={data.history}>
            <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
            <XAxis dataKey="date" tickFormatter={(d: string) => d.slice(5)} tick={axisStyle} minTickGap={30} />
            <YAxis tick={axisStyle} width={40} domain={['auto', 'auto']} />
            <Tooltip {...tooltipStyle} />
            <Line dataKey="best_e1rm" stroke="#4ade80" strokeWidth={2} name="e1RM" />
          </LineChart>
        </ChartCard>
      )}
    </>
  )
}

function CardioTab() {
  const [type, setType] = useState('running')
  const types = useQuery({
    queryKey: ['workout-types'],
    queryFn: () => apiGet<{ type: string; count: number }[]>('/api/workouts/types'),
  })
  const { data } = useQuery({
    queryKey: ['cardio-analytics', type],
    queryFn: () => apiGet<CardioAnalytics>(`/api/workouts/analytics/cardio?type=${type}`),
  })

  return (
    <>
      <div className="tabs">
        {(types.data ?? [])
          .filter((t) => t.type !== 'strength_training')
          .map((t) => (
            <button key={t.type} className={`chip ${type === t.type ? 'active' : ''}`} onClick={() => setType(t.type)}>
              {TYPE_ICONS[t.type] ?? ''} {t.type.replace(/_/g, ' ')}
            </button>
          ))}
      </div>

      <ChartCard title="Weekly distance (km)">
        <BarChart data={data?.weekly ?? []}>
          <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
          <XAxis dataKey="week" tick={axisStyle} minTickGap={20} />
          <YAxis tick={axisStyle} width={35} />
          <Tooltip {...tooltipStyle} />
          <Bar dataKey="distance_km" fill="#38bdf8" name="km" />
        </BarChart>
      </ChartCard>

      <ChartCard title={type === 'cycling' ? 'Speed (km/h)' : 'Pace (min/km)'}>
        <LineChart data={data?.pace_trend ?? []}>
          <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
          <XAxis dataKey="date" tickFormatter={(d: string) => d.slice(5)} tick={axisStyle} minTickGap={30} />
          <YAxis
            tick={axisStyle}
            width={35}
            domain={['auto', 'auto']}
            reversed={type !== 'cycling'}
          />
          <Tooltip {...tooltipStyle} />
          <Line
            dataKey={type === 'cycling' ? 'speed_kmh' : 'pace_min_per_km'}
            stroke="#4ade80"
            strokeWidth={2}
            name={type === 'cycling' ? 'km/h' : 'min/km'}
          />
        </LineChart>
      </ChartCard>

      <ChartCard title="Training load (acute vs chronic)">
        <LineChart data={data?.load.series ?? []}>
          <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
          <XAxis dataKey="date" tickFormatter={(d: string) => d.slice(5)} tick={axisStyle} minTickGap={30} />
          <YAxis tick={axisStyle} width={35} />
          <Tooltip {...tooltipStyle} />
          <Line dataKey="acute_7d" stroke="#f87171" dot={false} strokeWidth={2} name="Acute 7d" />
          <Line dataKey="chronic_28d" stroke="#38bdf8" dot={false} strokeWidth={2} name="Chronic 28d" />
        </LineChart>
      </ChartCard>
      {data && !data.load.sufficient_history && (
        <p className="muted">
          Acute:chronic ratio needs ≥21 days of training history (you have {data.load.history_days}). It will
          appear automatically as data accumulates.
        </p>
      )}
    </>
  )
}
