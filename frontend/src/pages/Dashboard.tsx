import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  Heart, Moon, Footprints, Flame, Activity, Battery,
  ChevronRight,
} from 'lucide-react'
import { ResponsiveContainer, LineChart, Line, YAxis } from 'recharts'
import { apiGet } from '../api/client'
import type { Dashboard as DashboardData, CorrelationsResponse, Workout } from '../api/types'
import MetricCard from '../components/MetricCard'
import MetricDrillDown from '../components/MetricDrillDown'
import SyncStatusCard from '../components/SyncStatusCard'
import SkeletonLoader from '../components/SkeletonLoader'
import SleepDrillDown from '../components/drilldowns/SleepDrillDown'
import WeightDrillDown from '../components/drilldowns/WeightDrillDown'
import HrvDrillDown from '../components/drilldowns/HrvDrillDown'
import GenericDrillDown from '../components/drilldowns/GenericDrillDown'

const DEFAULT_METRICS = ['hrv', 'sleep_score', 'calories_out', 'steps', 'resting_hr', 'body_battery']

const METRIC_DEFS: Record<string, { label: string; icon: typeof Heart; unit?: string }> = {
  hrv:          { label: 'HRV',        icon: Activity,   unit: 'ms' },
  sleep_score:  { label: 'Sleep',      icon: Moon },
  calories_out: { label: 'Cal Burned', icon: Flame,      unit: 'kcal' },
  steps:        { label: 'Steps',      icon: Footprints },
  resting_hr:   { label: 'Rest HR',    icon: Heart,      unit: 'bpm' },
  body_battery: { label: 'Battery',    icon: Battery },
}

// Maps metric key -> field on DashboardDay
function getMetricValue(day: DashboardData['series'][0] | undefined, key: string): number | null {
  if (!day) return null
  const map: Record<string, number | null | undefined> = {
    hrv:          day.hrv,
    sleep_score:  day.sleep_score,
    calories_out: day.calories_out,
    steps:        day.steps,
    resting_hr:   day.resting_hr,
    // DashboardDay uses body_battery_high
    body_battery: day.body_battery_high,
  }
  return map[key] ?? null
}

// Maps metric key -> field on averages_7d
function getAvgValue(avg: DashboardData['averages_7d'] | undefined, key: string): number | null {
  if (!avg) return null
  const map: Record<string, number | null | undefined> = {
    hrv:          avg.hrv,
    sleep_score:  avg.sleep_score,
    steps:        avg.steps,
    resting_hr:   avg.resting_hr,
    // calories_out and body_battery not in averages_7d
    calories_out: null,
    body_battery: null,
  }
  return map[key] ?? null
}

const READINESS_COLORS: Record<string, string> = {
  green:              'var(--green)',
  amber:              'var(--amber)',
  red:                'var(--red)',
  building_baseline:  'var(--accent)',
  no_data:            'var(--muted)',
}

export default function Dashboard() {
  const [drillDown, setDrillDown] = useState<string | null>(null)
  const [metricsConfig] = useState<string[]>(() => {
    try {
      const saved = localStorage.getItem('dashboard-metrics-config')
      return saved ? JSON.parse(saved) : DEFAULT_METRICS
    } catch {
      return DEFAULT_METRICS
    }
  })

  const { data: dash, isLoading } = useQuery<DashboardData>({
    queryKey: ['dashboard', 30],
    queryFn: () => apiGet('/api/analytics/dashboard?days=30'),
  })

  const { data: workouts } = useQuery<Workout[]>({
    queryKey: ['workouts'],
    queryFn: () => apiGet('/api/workouts/'),
  })

  const { data: correlations } = useQuery<CorrelationsResponse>({
    queryKey: ['correlations'],
    queryFn: () => apiGet('/api/analytics/correlations?days=90'),
  })

  // series is sorted oldest-first; last entry = today
  const today = dash?.series?.[dash.series.length - 1]
  const avg7 = dash?.averages_7d
  const recentWorkouts = workouts?.slice(0, 3)

  return (
    <div style={{ padding: '16px' }}>
      <SyncStatusCard />

      {/* Metrics Row */}
      <div style={{
        display: 'flex',
        gap: 8,
        overflowX: 'auto',
        paddingBottom: 8,
        WebkitOverflowScrolling: 'touch',
        scrollSnapType: 'x mandatory',
      }}>
        {isLoading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <div key={i} style={{ minWidth: 120, flex: '0 0 auto' }}>
              <SkeletonLoader height="90px" borderRadius="14px" />
            </div>
          ))
        ) : (
          metricsConfig.map(key => {
            const def = METRIC_DEFS[key]
            if (!def) return null
            const val = getMetricValue(today, key)
            const avgVal = getAvgValue(avg7, key)
            const delta = val != null && avgVal != null ? +(val - avgVal).toFixed(1) : undefined
            const Icon = def.icon
            return (
              <div key={key} style={{ minWidth: 120, flex: '0 0 auto', scrollSnapAlign: 'start' }}>
                <MetricCard
                  icon={<Icon size={18} />}
                  label={def.label}
                  value={val != null ? val : null}
                  delta={delta != null ? { value: delta, suffix: def.unit ? ` ${def.unit}` : '' } : undefined}
                  onClick={() => setDrillDown(key)}
                />
              </div>
            )
          })
        )}
      </div>

      {/* Recent Activities */}
      {recentWorkouts && recentWorkouts.length > 0 && (
        <div className="card" style={{ marginTop: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <span className="text-title">Recent Activities</span>
            <Link to="/workouts" style={{ color: 'var(--accent)', fontSize: '0.8rem', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 4 }}>
              See all <ChevronRight size={14} />
            </Link>
          </div>
          {recentWorkouts.map(w => (
            <Link
              key={w.id}
              to={`/workouts/${w.id}`}
              style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 0', borderBottom: '1px solid var(--border)', textDecoration: 'none', color: 'var(--text)' }}
            >
              <Activity size={18} color="var(--muted)" />
              <div style={{ flex: 1 }}>
                <div className="text-body">{w.name || w.type}</div>
                <div className="text-caption">{w.date}{w.duration_min ? ` · ${w.duration_min}min` : ''}</div>
              </div>
              <ChevronRight size={16} color="var(--muted)" />
            </Link>
          ))}
        </div>
      )}

      {/* Today's Log Summary */}
      <Link to="/log" style={{ textDecoration: 'none', color: 'inherit' }}>
        <div className="card" style={{ marginTop: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <span className="text-title">Today's Log</span>
            <ChevronRight size={16} color="var(--muted)" />
          </div>
          {today ? (
            <div style={{ display: 'flex', gap: 16 }}>
              <div>
                <div className="text-caption">Calories In</div>
                <div className="text-body" style={{ fontWeight: 600 }}>{today.calories_in ?? '–'}</div>
              </div>
              <div>
                <div className="text-caption">Burned</div>
                <div className="text-body" style={{ fontWeight: 600 }}>{today.calories_out ?? '–'}</div>
              </div>
              <div>
                <div className="text-caption">Balance</div>
                <div className="text-body" style={{
                  fontWeight: 600,
                  color: today.balance != null ? (today.balance > 0 ? 'var(--red)' : 'var(--green)') : undefined,
                }}>
                  {today.balance != null ? `${today.balance > 0 ? '+' : ''}${today.balance}` : '–'}
                </div>
              </div>
            </div>
          ) : (
            isLoading
              ? <SkeletonLoader height="32px" borderRadius="8px" />
              : <div className="text-caption">No data yet. Check in to start tracking.</div>
          )}
        </div>
      </Link>

      {/* Trends sparklines */}
      {dash && dash.series.length > 7 && (
        <div className="card" style={{ marginTop: 12 }}>
          <div className="text-title" style={{ marginBottom: 12 }}>Trends</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            {metricsConfig.slice(0, 4).map(key => {
              const def = METRIC_DEFS[key]
              if (!def) return null
              const chartData = dash.series
                .map(d => ({ v: getMetricValue(d, key) }))
                .filter(d => d.v != null)
              if (chartData.length < 3) return null
              return (
                <div key={key} onClick={() => setDrillDown(key)} style={{ cursor: 'pointer' }}>
                  <div className="text-caption" style={{ marginBottom: 4 }}>{def.label}</div>
                  <ResponsiveContainer width="100%" height={50}>
                    <LineChart data={chartData}>
                      <YAxis domain={['dataMin', 'dataMax']} hide />
                      <Line type="linear" dataKey="v" stroke="var(--accent)" strokeWidth={1.5} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Insights */}
      {correlations?.insights && correlations.insights.filter(i => i.status === 'ok').length > 0 && (
        <Link to="/insights" style={{ textDecoration: 'none', color: 'inherit' }}>
          <div className="card" style={{ marginTop: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <span className="text-title">Insights</span>
              <ChevronRight size={16} color="var(--muted)" />
            </div>
            {correlations.insights.filter(i => i.status === 'ok').slice(0, 2).map((ins, i) => (
              <div key={ins.id} style={{ padding: '8px 0', borderTop: i > 0 ? '1px solid var(--border)' : undefined }}>
                <div className="text-body">{ins.title}</div>
                <div className="text-caption">{ins.summary_line}</div>
              </div>
            ))}
          </div>
        </Link>
      )}

      {/* Readiness */}
      {dash?.readiness && (
        <div className="card" style={{ marginTop: 12 }}>
          <div className="text-title" style={{ marginBottom: 8 }}>Readiness</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <div style={{
              width: 10,
              height: 10,
              borderRadius: '50%',
              background: READINESS_COLORS[dash.readiness.status] ?? 'var(--muted)',
              flexShrink: 0,
            }} />
            <span className="text-body" style={{ fontWeight: 600, textTransform: 'capitalize' }}>
              {dash.readiness.label}
            </span>
            {dash.readiness.score_pct != null && (
              <span className="text-caption">({dash.readiness.score_pct}%)</span>
            )}
          </div>
          {dash.readiness.components?.map((c) => (
            <div key={c.key} className="text-caption" style={{ padding: '2px 0' }}>
              • {c.label}: {c.value} ({c.points}/{c.max_points} pts)
            </div>
          ))}
        </div>
      )}

      {/* Metric Drill-Downs */}
      {drillDown && (
        <MetricDrillDown
          open={!!drillDown}
          onClose={() => setDrillDown(null)}
          title={METRIC_DEFS[drillDown]?.label || drillDown}
          value={today ? getMetricValue(today, drillDown)?.toString() : undefined}
        >
          {drillDown === 'sleep_score' && <SleepDrillDown />}
          {drillDown === 'hrv' && <HrvDrillDown />}
          {drillDown === 'weight' && <WeightDrillDown />}
          {drillDown === 'calories_out' && <GenericDrillDown metricKey="calories_out" unit="kcal" />}
          {drillDown === 'steps' && <GenericDrillDown metricKey="steps" />}
          {drillDown === 'resting_hr' && <GenericDrillDown metricKey="resting_hr" unit="bpm" />}
          {drillDown === 'body_battery' && <GenericDrillDown metricKey="body_battery_high" />}
        </MetricDrillDown>
      )}
    </div>
  )
}
