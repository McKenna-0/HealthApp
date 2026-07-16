import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { CartesianGrid, Line, LineChart, Tooltip, XAxis, YAxis } from 'recharts'
import { apiGet } from '../api/client'
import type { ExerciseSessionPoint, ExerciseStatsDetail } from '../api/types'
import ChartCard from '../components/ChartCard'

const axisStyle = { fontSize: 10, fill: '#94a3b8' }
const tooltipStyle = {
  contentStyle: { background: '#1e293b', border: '1px solid #334155', borderRadius: 8 },
  labelStyle: { color: '#94a3b8' },
}

const RANGES = ['3m', '6m', '1y', 'all'] as const
type Range = (typeof RANGES)[number]

const METRICS = [
  { key: 'best_e1rm', label: 'e1RM', unit: 'kg' },
  { key: 'volume_kg', label: 'Volume', unit: 'kg' },
  { key: 'total_reps', label: 'Reps', unit: '' },
  { key: 'max_reps', label: 'Max reps', unit: '' },
  { key: 'num_sets', label: 'Sets', unit: '' },
  { key: 'workouts', label: 'Workouts', unit: '' },
] as const
type MetricKey = (typeof METRICS)[number]['key']

function setNotation(s: ExerciseSessionPoint): string {
  const parts: string[] = []
  let prevWeight: number | null | undefined
  for (const set of s.sets) {
    const w = set.weight_kg
    const txt = w != null && w !== 0 && w !== prevWeight ? `${w}x${set.reps}` : `${set.reps}`
    parts.push(set.is_top ? `(${txt})` : txt)
    prevWeight = w
  }
  return parts.join(', ')
}

export default function ExerciseStatsPage() {
  const { exerciseId } = useParams()
  const [range, setRange] = useState<Range>('all')
  const [metric, setMetric] = useState<MetricKey>('best_e1rm')

  const { data, isLoading } = useQuery({
    queryKey: ['exercise-stats', exerciseId, range],
    queryFn: () =>
      apiGet<ExerciseStatsDetail>(`/api/workouts/analytics/exercises/${exerciseId}?range=${range}`),
  })

  if (isLoading) return <p className="muted">Loading…</p>
  if (!data) return <p className="muted">Not found.</p>

  const sessions = [...data.sessions].sort((a, b) => (a.date < b.date ? -1 : 1))
  const chartData = sessions.map((s, i) => ({
    ...s,
    workouts: i + 1,
  }))
  const metricDef = METRICS.find((m) => m.key === metric)!

  return (
    <>
      <p style={{ margin: '8px 4px 0' }}>
        <Link to="/workouts" className="muted" style={{ textDecoration: 'none' }}>
          ‹ Workouts
        </Link>
      </p>
      <h1>{data.exercise.name}</h1>

      <div className="tabs">
        {METRICS.map((m) => (
          <button
            key={m.key}
            className={`chip ${metric === m.key ? 'active' : ''}`}
            onClick={() => setMetric(m.key)}
          >
            {m.label}
          </button>
        ))}
      </div>
      <div className="tabs">
        {RANGES.map((r) => (
          <button
            key={r}
            className={`chip ${range === r ? 'active' : ''}`}
            onClick={() => setRange(r)}
          >
            {r.toUpperCase()}
          </button>
        ))}
      </div>

      <ChartCard title={`${metricDef.label}${metricDef.unit ? ` (${metricDef.unit})` : ''}`}>
        <LineChart data={chartData}>
          <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
          <XAxis
            dataKey="date"
            tickFormatter={(d: string) => d.slice(range === 'all' ? 2 : 5)}
            tick={axisStyle}
            minTickGap={30}
          />
          <YAxis tick={axisStyle} width={40} domain={['auto', 'auto']} />
          <Tooltip {...tooltipStyle} />
          <Line
            dataKey={metric}
            stroke="#4ade80"
            strokeWidth={2}
            dot={chartData.length < 40}
            name={metricDef.label}
            connectNulls
          />
        </LineChart>
      </ChartCard>

      {data.prs.best_e1rm && (
        <div className="card">
          <h2 style={{ marginTop: 0 }}>Personal records</h2>
          <p style={{ margin: '0 0 6px' }}>
            Best e1RM: <strong>{data.prs.best_e1rm.e1rm} kg</strong> ({data.prs.best_e1rm.weight_kg}kg ×{' '}
            {data.prs.best_e1rm.reps} on {data.prs.best_e1rm.date})
          </p>
          {data.prs.rep_prs.length > 0 && (
            <div className="muted" style={{ fontSize: '0.8rem' }}>
              {data.prs.rep_prs.map((p) => `${p.reps}RM ${p.weight_kg}kg`).join(' · ')}
            </div>
          )}
        </div>
      )}

      <h2>History ({sessions.length} sessions)</h2>
      <div className="card">
        {[...sessions].reverse().map((s) => (
          <Link
            key={s.activity_id}
            to={`/workouts/${s.activity_id}`}
            style={{ textDecoration: 'none', color: 'inherit' }}
          >
            <div className="list-item">
              <div className="main">
                <div className="name">{setNotation(s)}</div>
                <div className="detail">
                  {s.date} · {s.num_sets} sets · {s.total_reps} reps · max {s.max_reps}
                  {s.best_e1rm != null ? ` · e1RM ${s.best_e1rm}kg` : ''}
                </div>
              </div>
              <span className="muted">›</span>
            </div>
          </Link>
        ))}
        {sessions.length === 0 && <p className="muted">No sessions in this range.</p>}
      </div>
    </>
  )
}
