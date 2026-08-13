import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, RotateCcw } from 'lucide-react'
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { apiDelete, apiGet, apiPost } from '../api/client'
import type { Exercise, HrZone, Lap, SessionPayload, TimeSeriesPoint, WorkoutDetail } from '../api/types'
import ChartCard from '../components/ChartCard'
import EditableWorkoutName from '../components/EditableWorkoutName'
import SwipeToDelete from '../components/SwipeToDelete'
import { AreaChart, Area, BarChart, Bar, CartesianGrid, Cell, LineChart, Line, Tooltip, XAxis, YAxis } from 'recharts'

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

function paceFromDistTime(distKm: number, durS: number) {
  if (!distKm || !durS) return '–'
  const mps = (distKm * 1000) / durS
  return pace(mps)
}

const STRENGTH_TYPES = new Set(['strength_training', 'indoor_cardio', 'yoga', 'pilates'])

export default function WorkoutDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { data, isLoading, error } = useQuery({
    queryKey: ['workout', id],
    queryFn: () => apiGet<WorkoutDetail>(`/api/workouts/${id}`),
  })

  const [tab, setTab] = useState<'overview' | 'stats' | 'laps' | 'charts'>('overview')

  if (isLoading) return <p className="muted">Loading…</p>
  if (error || !data) return <p className="error-text">Failed to load: {String(error)}</p>

  const a = data.activity
  const isStrength = STRENGTH_TYPES.has(a.type ?? '') || data.sets.length > 0
  const isCardio = !isStrength

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
        <h1 className="text-display" style={{ margin: 0, flex: 1, minWidth: 0 }}>
          <EditableWorkoutName
            workoutId={a.id}
            name={a.name ?? a.type}
            editable={a.source !== 'garmin'}
          />
        </h1>
      </div>

      {isStrength && <WorkoutActions detail={data} workoutId={id!} />}

      {isCardio && (
        <div className="tabs" style={{ marginBottom: 12 }}>
          {(['overview', 'stats', 'laps', 'charts'] as const).map((t) => (
            <button key={t} className={`chip ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>
              {t[0].toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>
      )}

      {isStrength ? (
        <>
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
          <SetsSection detail={data} workoutId={id!} />
        </>
      ) : (
        <>
          {tab === 'overview' && <OverviewTab workoutId={id!} activity={a} />}
          {tab === 'stats' && <StatsTab activity={a} />}
          {tab === 'laps' && <LapsTabContent workoutId={id!} type={a.type} />}
          {tab === 'charts' && <ChartsTab workoutId={id!} type={a.type} />}
        </>
      )}
    </>
  )
}

// ---- Charts Tab ----

const axisStyle = { fontSize: 10, fill: '#94a3b8' }
const tooltipStyle = {
  contentStyle: { background: '#1e293b', border: '1px solid #334155', borderRadius: 8 },
  labelStyle: { color: '#94a3b8' },
}
const ZONE_BAR_COLORS = ['#64748b', '#38bdf8', '#4ade80', '#fbbf24', '#f87171']

function ChartsTab({ workoutId, type }: { workoutId: string; type: string | null }) {
  const { data: timeseries, isLoading } = useQuery({
    queryKey: ['timeseries', workoutId],
    queryFn: () => apiGet<TimeSeriesPoint[]>(`/api/workouts/${workoutId}/timeseries`),
  })
  const { data: zones } = useQuery({
    queryKey: ['hr-zones', workoutId],
    queryFn: () => apiGet<HrZone[]>(`/api/workouts/${workoutId}/hr-zones`),
  })

  if (isLoading) return <p className="muted">Loading charts…</p>
  if (!timeseries || timeseries.length === 0) {
    return (
      <p className="muted" style={{ textAlign: 'center', padding: 32 }}>
        Chart data not available for this activity.
      </p>
    )
  }

  function fmtElapsed(s: number) {
    const totalSecs = Math.round(s)
    const h = Math.floor(totalSecs / 3600)
    const m = Math.floor((totalSecs % 3600) / 60)
    const sec = totalSecs % 60
    if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
    return `${m}:${String(sec).padStart(2, '0')}`
  }

  const pts = timeseries.filter((p) => p.elapsed_s != null)
  const isRunning = type === 'running'

  const hasHr = pts.some((p) => p.hr != null)
  const hasSpeed = pts.some((p) => p.speed_mps != null)
  const hasElevation = pts.some((p) => p.elevation_m != null)
  const hasCadence = pts.some((p) => p.cadence != null)

  // Compute derived pace/speed data
  const paceData = pts.map((p) => ({
    ...p,
    pace: p.speed_mps ? 1000 / p.speed_mps / 60 : null,
    speed_kmh: p.speed_mps ? p.speed_mps * 3.6 : null,
  }))

  const hasZones = zones && zones.length > 0

  return (
    <div>
      {hasHr && (
        <ChartCard title="Heart Rate" height={200}>
          <LineChart data={pts} >
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis
              dataKey="elapsed_s"
              tickFormatter={fmtElapsed}
              tick={axisStyle}
              minTickGap={40}
            />
            <YAxis tick={axisStyle} label={{ value: 'bpm', angle: -90, position: 'insideLeft', style: axisStyle }} />
            <Tooltip
              {...tooltipStyle}
              labelFormatter={(v) => fmtElapsed(v as number)}
              formatter={(v) => [`${v} bpm`, 'HR']}
            />
            <Line
              type="monotone"
              dataKey="hr"
              stroke="#f87171"
              strokeWidth={1.5}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ChartCard>
      )}

      {hasSpeed && (
        <ChartCard title={isRunning ? 'Pace' : 'Speed'} height={200}>
          <LineChart data={paceData} >
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis
              dataKey="elapsed_s"
              tickFormatter={fmtElapsed}
              tick={axisStyle}
              minTickGap={40}
            />
            {isRunning ? (
              <YAxis
                tick={axisStyle}
                reversed
                label={{ value: 'min/km', angle: -90, position: 'insideLeft', style: axisStyle }}
                tickFormatter={(v: number) => {
                  const m = Math.floor(v)
                  const s = Math.round((v - m) * 60)
                  return `${m}:${String(s).padStart(2, '0')}`
                }}
              />
            ) : (
              <YAxis
                tick={axisStyle}
                label={{ value: 'km/h', angle: -90, position: 'insideLeft', style: axisStyle }}
              />
            )}
            <Tooltip
              {...tooltipStyle}
              labelFormatter={(v) => fmtElapsed(v as number)}
              formatter={(v: any) => {
                if (isRunning) {
                  const m = Math.floor(v)
                  const s = Math.round((v - m) * 60)
                  return [`${m}:${String(s).padStart(2, '0')} /km`, 'Pace']
                }
                return [`${v.toFixed(1)} km/h`, 'Speed']
              }}
            />
            <Line
              type="monotone"
              dataKey={isRunning ? 'pace' : 'speed_kmh'}
              stroke="#4ade80"
              strokeWidth={1.5}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ChartCard>
      )}

      {hasElevation && (
        <ChartCard title="Elevation" height={160}>
          <AreaChart data={pts} >
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis
              dataKey="elapsed_s"
              tickFormatter={fmtElapsed}
              tick={axisStyle}
              minTickGap={40}
            />
            <YAxis tick={axisStyle} label={{ value: 'm', angle: -90, position: 'insideLeft', style: axisStyle }} />
            <Tooltip
              {...tooltipStyle}
              labelFormatter={(v) => fmtElapsed(v as number)}
              formatter={(v) => [`${v} m`, 'Elevation']}
            />
            <Area
              type="monotone"
              dataKey="elevation_m"
              stroke="#38bdf8"
              fill="#38bdf8"
              fillOpacity={0.15}
              dot={false}
              isAnimationActive={false}
            />
          </AreaChart>
        </ChartCard>
      )}

      {hasCadence && (
        <ChartCard title="Cadence" height={160}>
          <LineChart data={pts} >
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis
              dataKey="elapsed_s"
              tickFormatter={fmtElapsed}
              tick={axisStyle}
              minTickGap={40}
            />
            <YAxis tick={axisStyle} label={{ value: 'spm', angle: -90, position: 'insideLeft', style: axisStyle }} />
            <Tooltip
              {...tooltipStyle}
              labelFormatter={(v) => fmtElapsed(v as number)}
              formatter={(v) => [`${v} spm`, 'Cadence']}
            />
            <Line
              type="monotone"
              dataKey="cadence"
              stroke="#a78bfa"
              strokeWidth={1.5}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ChartCard>
      )}

      {hasZones && (
        <ChartCard title="Time in Zones" height={180}>
          <BarChart
            data={zones}
            layout="vertical"
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis
              type="number"
              tick={axisStyle}
              tickFormatter={(v: number) => {
                const m = Math.floor(v / 60)
                const s = Math.round(v % 60)
                return `${m}:${String(s).padStart(2, '0')}`
              }}
            />
            <YAxis
              type="category"
              dataKey="zone_number"
              tick={axisStyle}
              tickFormatter={(v) => `Z${v}`}
              width={28}
            />
            <Tooltip
              {...tooltipStyle}
              formatter={(v: any) => {
                const m = Math.floor(v / 60)
                const s = Math.round(v % 60)
                return [`${m}:${String(s).padStart(2, '0')}`, 'Time']
              }}
              labelFormatter={(v) => `Zone ${v}`}
            />
            <Bar dataKey="secs_in_zone" isAnimationActive={false}>
              {zones.map((z) => (
                <Cell
                  key={z.zone_number}
                  fill={ZONE_BAR_COLORS[(z.zone_number - 1)] ?? '#64748b'}
                />
              ))}
            </Bar>
          </BarChart>
        </ChartCard>
      )}
    </div>
  )
}

// ---- Overview Tab ----

function OverviewTab({ workoutId, activity: a }: { workoutId: string; activity: import('../api/types').Workout }) {
  const isCycling = a.type === 'cycling'

  // Determine 4th banner metric: elevation if available, else calories
  const fourthMetric = a.elevation_gain_m != null
    ? { label: 'Elevation', value: `${Math.round(a.elevation_gain_m)} m` }
    : { label: 'Calories', value: String(a.calories ?? '–') }

  const speedOrPace = isCycling
    ? { label: 'Speed', value: a.avg_speed_mps != null ? `${(a.avg_speed_mps * 3.6).toFixed(1)}` : '–', sub: 'km/h' }
    : { label: 'Pace', value: pace(a.avg_speed_mps), sub: 'min/km' }

  return (
    <>
      {/* Banner: 4 headline metrics */}
      <div className="workout-banner">
        <div className="metric-card">
          <div className="label">Distance</div>
          <div className="value">{a.distance_km != null ? `${a.distance_km.toFixed(2)} km` : '–'}</div>
        </div>
        <div className="metric-card">
          <div className="label">Time</div>
          <div className="value">{fmtDuration(a.duration_min)}</div>
        </div>
        <div className="metric-card">
          <div className="label">{speedOrPace.label}</div>
          <div className="value">{speedOrPace.value}</div>
          <div className="sub">{speedOrPace.sub}</div>
        </div>
        <div className="metric-card">
          <div className="label">{fourthMetric.label}</div>
          <div className="value">{fourthMetric.value}</div>
        </div>
      </div>

      {/* HR summary */}
      {(a.avg_hr != null || a.max_hr != null) && (
        <div className="card" style={{ marginBottom: 12 }}>
          <div style={{ display: 'flex', gap: 16, justifyContent: 'space-around' }}>
            {a.avg_hr != null && (
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--text)' }}>{a.avg_hr}</div>
                <div className="label">Avg HR</div>
              </div>
            )}
            {a.max_hr != null && (
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--red)' }}>{a.max_hr}</div>
                <div className="label">Max HR</div>
              </div>
            )}
          </div>
          {a.calories != null && a.elevation_gain_m != null && (
            <p className="muted" style={{ textAlign: 'center', margin: '8px 0 0', fontSize: '0.85rem' }}>
              {a.calories} kcal
            </p>
          )}
        </div>
      )}

      {/* Training effect row */}
      {(a.aerobic_te != null || a.anaerobic_te != null || a.training_load != null) && (
        <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
          {a.aerobic_te != null && (
            <div className="metric-card" style={{ flex: 1, textAlign: 'center' }}>
              <div className="label">Aerobic TE</div>
              <div className="value">{a.aerobic_te.toFixed(1)}</div>
            </div>
          )}
          {a.anaerobic_te != null && (
            <div className="metric-card" style={{ flex: 1, textAlign: 'center' }}>
              <div className="label">Anaerobic TE</div>
              <div className="value">{a.anaerobic_te.toFixed(1)}</div>
            </div>
          )}
          {a.training_load != null && (
            <div className="metric-card" style={{ flex: 1, textAlign: 'center' }}>
              <div className="label">Training Load</div>
              <div className="value">{Math.round(a.training_load)}</div>
            </div>
          )}
        </div>
      )}

      {/* HR Zones */}
      {a.avg_hr != null && <HrZonesSection workoutId={workoutId} />}
    </>
  )
}

// ---- Stats Tab ----

function StatsRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="stats-row">
      <span className="label">{label}</span>
      <span className="value">{value}</span>
    </div>
  )
}

function StatsTab({ activity: a }: { activity: import('../api/types').Workout }) {
  const isCycling = a.type === 'cycling'

  const movingDurationMin = a.moving_duration_min
  const movingDurationS = movingDurationMin != null ? movingDurationMin * 60 : null

  const movingPace = (a.distance_km != null && movingDurationS != null)
    ? paceFromDistTime(a.distance_km, movingDurationS)
    : null

  const hasElevation = a.elevation_gain_m != null
  const hasCadencePower = a.avg_run_cadence != null || (a as unknown as Record<string, unknown>).avg_power != null || (a as unknown as Record<string, unknown>).norm_power != null
  const hasTraining = a.training_load != null || a.vo2max != null || a.training_effect_label != null

  return (
    <div>
      {/* Time */}
      <details className="stats-section card" open>
        <summary>Time</summary>
        <StatsRow label="Duration" value={fmtDuration(a.duration_min)} />
        {movingDurationMin != null && (
          <StatsRow label="Moving time" value={fmtDuration(movingDurationMin)} />
        )}
        {a.avg_speed_mps != null && (
          <StatsRow
            label={isCycling ? 'Avg speed' : 'Avg pace'}
            value={isCycling ? `${(a.avg_speed_mps * 3.6).toFixed(1)} km/h` : `${pace(a.avg_speed_mps)} min/km`}
          />
        )}
        {movingPace != null && !isCycling && (
          <StatsRow label="Moving pace" value={`${movingPace} min/km`} />
        )}
        {movingPace != null && isCycling && a.distance_km != null && movingDurationS != null && (
          <StatsRow
            label="Moving speed"
            value={`${((a.distance_km * 1000) / movingDurationS * 3.6).toFixed(1)} km/h`}
          />
        )}
      </details>

      {/* Heart Rate */}
      {(a.avg_hr != null || a.max_hr != null || a.aerobic_te != null || a.anaerobic_te != null) && (
        <details className="stats-section card" open>
          <summary>Heart Rate</summary>
          {a.avg_hr != null && <StatsRow label="Avg HR" value={`${a.avg_hr} bpm`} />}
          {a.max_hr != null && <StatsRow label="Max HR" value={`${a.max_hr} bpm`} />}
          {a.aerobic_te != null && <StatsRow label="Aerobic TE" value={a.aerobic_te.toFixed(1)} />}
          {a.anaerobic_te != null && <StatsRow label="Anaerobic TE" value={a.anaerobic_te.toFixed(1)} />}
        </details>
      )}

      {/* Elevation */}
      {hasElevation && (
        <details className="stats-section card" open>
          <summary>Elevation</summary>
          <StatsRow label="Elevation gain" value={`${Math.round(a.elevation_gain_m!)} m`} />
        </details>
      )}

      {/* Cadence & Power */}
      {hasCadencePower && (
        <details className="stats-section card" open>
          <summary>Cadence &amp; Power</summary>
          {a.avg_run_cadence != null && (
            <StatsRow label="Avg cadence" value={`${Math.round(a.avg_run_cadence)} spm`} />
          )}
        </details>
      )}

      {/* Training */}
      {hasTraining && (
        <details className="stats-section card" open>
          <summary>Training</summary>
          {a.training_load != null && (
            <StatsRow label="Training load" value={`${Math.round(a.training_load)}`} />
          )}
          {a.vo2max != null && (
            <StatsRow label="VO2 Max" value={a.vo2max.toFixed(1)} />
          )}
          {a.training_effect_label != null && (
            <StatsRow
              label="Training effect"
              value={a.training_effect_label.replace(/_/g, ' ').toLowerCase()}
            />
          )}
        </details>
      )}
    </div>
  )
}

// ---- Laps Tab (with summary row) ----

function LapsTabContent({ workoutId, type }: { workoutId: string; type: string | null }) {
  const { data, isLoading } = useQuery({
    queryKey: ['laps', workoutId],
    queryFn: () => apiGet<Lap[]>(`/api/workouts/${workoutId}/laps`),
  })
  if (isLoading) return <p className="muted">Loading laps…</p>
  if (!data?.length) return <p className="muted" style={{ textAlign: 'center', padding: 24 }}>No lap data available.</p>

  // Compute summary from laps
  const totalDurS = data.reduce((s, l) => s + (l.duration_s ?? 0), 0)
  const totalDistKm = data.reduce((s, l) => s + (l.distance_km ?? 0), 0)
  const hrReadings = data.map((l) => l.avg_hr).filter((v): v is number => v != null)
  const avgHr = hrReadings.length > 0 ? Math.round(hrReadings.reduce((a, b) => a + b, 0) / hrReadings.length) : null
  const avgPace = type === 'cycling'
    ? totalDistKm > 0 && totalDurS > 0 ? `${((totalDistKm * 1000) / totalDurS * 3.6).toFixed(1)} km/h` : '–'
    : paceFromDistTime(totalDistKm, totalDurS)

  return (
    <div className="card">
      {/* Summary row */}
      <div className="lap-summary">
        <div>
          <div className="value">{fmtLapTime(totalDurS)}</div>
          <div className="label">Total time</div>
        </div>
        <div>
          <div className="value">{totalDistKm.toFixed(2)} km</div>
          <div className="label">Total dist</div>
        </div>
        <div>
          <div className="value">{avgPace}</div>
          <div className="label">{type === 'cycling' ? 'Avg speed' : 'Avg pace'}</div>
        </div>
        <div>
          <div className="value">{avgHr ?? '–'}</div>
          <div className="label">Avg HR</div>
        </div>
      </div>

      <h2 className="text-title" style={{ margin: '12px 0 8px' }}>Laps</h2>
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

  const deleteWorkout = useMutation({
    mutationFn: () => apiDelete(`/api/workouts/${workoutId}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['workouts'] })
      navigate('/workouts')
    },
  })

  return (
    <div className="row" style={{ marginBottom: 12, flexWrap: 'wrap' }}>
      {a.source === 'app' && a.status === 'finished' && (
        <button className="secondary" onClick={() => navigate(`/workouts/${workoutId}/summary`)}>
          Summary
        </button>
      )}
      {detail.sets.length > 0 && (
        <>
          <button onClick={() => repeat.mutate()} disabled={repeat.isPending} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <RotateCcw size={14} /> Repeat
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
      {a.source !== 'garmin' && (
        <button
          className="secondary"
          style={{ color: 'var(--red)' }}
          disabled={deleteWorkout.isPending}
          onClick={() => {
            if (window.confirm('Delete this workout and all its data? This cannot be undone.'))
              deleteWorkout.mutate()
          }}
        >
          Delete
        </button>
      )}
      {(repeat.isError || saveRoutine.isError || deleteWorkout.isError) && (
        <p className="error-text">
          {String(repeat.error ?? saveRoutine.error ?? deleteWorkout.error).replace(/^\d+: /, '').slice(0, 120)}
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
      <h2 className="text-title" style={{ marginTop: 0 }}>Heart rate zones</h2>
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
        <h2 className="text-title" style={{ marginTop: 0 }}>Sets · {detail.tonnage_kg.toFixed(0)} kg total</h2>
        {detail.sets.length === 0 && <p className="muted">No sets logged yet.</p>}
        {detail.sets.map((s) => (
          <SwipeToDelete key={s.id} onDelete={() => removeSet.mutate(s.id)}>
            <div className="list-item" style={s.is_warmup ? { opacity: 0.6 } : undefined}>
              <div className="main">
                <div className="text-body name">
                  {s.exercise_name}{' '}
                  {s.is_warmup ? <span className="badge warm-badge">warm-up</span> : null}{' '}
                  {s.is_pr && <span className="badge pr">PR</span>}
                </div>
                <div className="text-caption detail">
                  {s.weight_kg != null ? `${s.weight_kg}kg × ` : ''}
                  {s.reps} reps
                  {s.e1rm != null && !s.is_warmup ? ` · e1RM ${s.e1rm}kg` : ''}
                  {s.note ? ` · ${s.note}` : ''}
                </div>
              </div>
            </div>
          </SwipeToDelete>
        ))}
      </div>

      <div className="card">
        <h2 className="text-title" style={{ marginTop: 0 }}>Add set</h2>
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
                    <div className="text-body name">{e.name}</div>
                    <div className="text-caption detail">
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
