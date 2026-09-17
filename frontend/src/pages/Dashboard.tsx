import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  Heart, Moon, Footprints, Flame, Activity, Battery, Scale,
  ChevronRight, Check,
} from 'lucide-react'
import { apiGet } from '../api/client'
import type {
  Dashboard as DashboardData, CorrelationsResponse, Workout, WeightProgress,
  Readiness, StreakInfo,
} from '../api/types'
import { getBalanceColor } from '../utils/balanceColor'
import { loadMetricsConfig } from '../utils/dashboardMetrics'
import { formatRate, statusColor } from '../utils/weightStatus'
import MetricCard from '../components/MetricCard'
import MetricDrillDown from '../components/MetricDrillDown'
import SyncStatusCard from '../components/SyncStatusCard'
import SkeletonLoader from '../components/SkeletonLoader'
import SleepDrillDown from '../components/drilldowns/SleepDrillDown'
import WeightDrillDown from '../components/drilldowns/WeightDrillDown'
import HrvDrillDown from '../components/drilldowns/HrvDrillDown'
import GenericDrillDown from '../components/drilldowns/GenericDrillDown'
import BodyBatteryDrillDown from '../components/drilldowns/BodyBatteryDrillDown'

interface Settings {
  daily_balance_target: number | null
}

const METRIC_DEFS: Record<string, { label: string; icon: typeof Heart; unit?: string }> = {
  hrv:          { label: 'HRV',        icon: Activity,   unit: 'ms' },
  sleep_score:  { label: 'Sleep',      icon: Moon },
  calories_out: { label: 'Cal Burned', icon: Flame,      unit: 'kcal' },
  steps:        { label: 'Steps',      icon: Footprints },
  resting_hr:   { label: 'Rest HR',    icon: Heart,      unit: 'bpm' },
  body_battery: { label: 'Battery',    icon: Battery },
  weight:       { label: 'Weight',     icon: Scale,      unit: 'kg' },
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
    // live/most-recently-synced reading, not the day's historical peak
    body_battery: day.body_battery_current,
    // the sparkline wants the de-noised line, not the scale's daily wobble
    weight:       day.weight_trend ?? day.weight,
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
    // calories_out, body_battery and weight are not in averages_7d — weight
    // gets its delta from the trend model instead of a 7-day mean
    calories_out: null,
    body_battery: null,
    weight: null,
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

/* The API labels read as a list ("Resting HR vs baseline"); as a row of four
   chips at 390px they need names, not sentences. Falls back to the API label
   with its qualifiers stripped if the backend adds a component. */
const READINESS_SHORT: Record<string, string> = {
  hrv: 'HRV',
  rhr: 'Rest HR',
  sleep: 'Sleep',
  body_battery: 'Battery',
}

const RING_R = 44
const RING_C = 2 * Math.PI * RING_R

/**
 * Readiness is the only number on this page that is different every morning,
 * so it leads. It used to be the last card, rendered as a bullet list.
 */
function ReadinessHero({ readiness }: { readiness: Readiness }) {
  const color = READINESS_COLORS[readiness.status] ?? 'var(--muted)'
  const pct = readiness.score_pct
  const offset = pct != null ? RING_C * (1 - Math.max(0, Math.min(100, pct)) / 100) : RING_C

  return (
    <div className="card">
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <svg width="104" height="104" viewBox="0 0 104 104" style={{ flexShrink: 0 }} aria-hidden="true">
          <circle cx="52" cy="52" r={RING_R} fill="none" stroke="var(--track)" strokeWidth="9" />
          <circle
            cx="52" cy="52" r={RING_R} fill="none"
            stroke={color} strokeWidth="9" strokeLinecap="round"
            strokeDasharray={RING_C} strokeDashoffset={offset}
            transform="rotate(-90 52 52)"
            style={{ transition: 'stroke-dashoffset 400ms cubic-bezier(.22,1,.36,1)' }}
          />
          <text
            x="52" y="51" textAnchor="middle" fill="var(--text)"
            fontSize="30" fontWeight="700" fontFamily="inherit"
          >
            {pct ?? '–'}
          </text>
          <text
            x="52" y="68" textAnchor="middle" fill="var(--muted)"
            fontSize="10" fontWeight="600" letterSpacing="1.2" fontFamily="inherit"
          >
            READY
          </text>
        </svg>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: '0.625rem', fontWeight: 700, letterSpacing: '0.14em', color: 'var(--muted)' }}>
            READINESS
          </div>
          <div style={{ fontSize: '1.375rem', fontWeight: 700, color, margin: '4px 0 6px', textTransform: 'capitalize' }}>
            {readiness.label}
          </div>
          <div className="text-caption" style={{ lineHeight: 1.45 }}>
            {readiness.baseline_days} days of baseline
          </div>
        </div>
      </div>

      {readiness.components && readiness.components.length > 0 && (
        <div style={{ display: 'flex', gap: 6, marginTop: 14 }}>
          {readiness.components.map((c) => (
            <div
              key={c.key}
              style={{
                flex: 1,
                minWidth: 0,
                background: 'var(--inset)',
                borderRadius: 12,
                padding: '8px 4px',
                textAlign: 'center',
              }}
            >
              <div style={{
                fontSize: '0.5625rem',
                fontWeight: 700,
                letterSpacing: '0.08em',
                color: 'var(--muted)',
                textTransform: 'uppercase',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}>
                {READINESS_SHORT[c.key] ?? c.label.replace(/\s*vs baseline/i, '').replace(/\s*\([^)]*\)/, '')}
              </div>
              <div className="tabular" style={{ fontSize: '0.875rem', fontWeight: 700, marginTop: 2 }}>
                {c.value}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/**
 * The open loop, on the screen you land on. Today previously showed nothing
 * outstanding — you had to reach the Log tab before the app would admit
 * anything was missing, which is the wrong place for a daily prompt.
 */
function TodayLoop({ streak, weightLogged }: { streak: StreakInfo; weightLogged: boolean }) {
  const today = streak.week[streak.week.length - 1]
  const chips = [
    { label: weightLogged ? 'Weight' : 'Log weight', done: weightLogged },
    { label: today?.checkin_done ? 'Check-in' : 'Check in', done: !!today?.checkin_done },
    { label: today?.food_logged ? 'Food' : 'Log food', done: !!today?.food_logged },
  ]
  // The first thing still open is the primary action; everything else is quiet.
  const firstOpen = chips.findIndex((c) => !c.done)

  return (
    <div className="card" style={{ padding: '12px 14px 14px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <Flame size={19} color="var(--amber)" style={{ flexShrink: 0 }} />
        <span className="tabular" style={{ fontSize: '1.0625rem', fontWeight: 700 }}>
          {streak.current_streak}
        </span>
        <span className="text-caption">day streak · best {streak.longest_streak}</span>
        <span style={{ marginLeft: 'auto', display: 'flex', gap: 5, alignItems: 'center' }}>
          {streak.week.map((d, i) => (
            <span
              key={d.date}
              title={`${d.weekday}${d.complete ? ' · complete' : ''}`}
              style={{
                width: 17,
                height: 17,
                borderRadius: '50%',
                boxSizing: 'border-box',
                background: d.complete ? 'var(--green)' : 'transparent',
                border: d.complete
                  ? 'none'
                  : `1.5px solid ${d.food_logged || d.checkin_done ? 'var(--amber)' : 'var(--track)'}`,
                boxShadow: i === streak.week.length - 1 ? '0 0 0 2px rgba(34,211,238,0.5)' : undefined,
              }}
            />
          ))}
        </span>
      </div>
      <div style={{ display: 'flex', gap: 6 }}>
        {chips.map((c, i) => (
          <Link
            key={c.label}
            to="/log"
            style={{
              flex: 1,
              minHeight: 44,
              borderRadius: 'var(--r-control)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 5,
              fontSize: '0.75rem',
              fontWeight: c.done ? 600 : 700,
              textDecoration: 'none',
              background: c.done
                ? 'rgba(52,211,153,0.12)'
                : i === firstOpen ? 'var(--accent)' : 'rgba(255,255,255,0.05)',
              color: c.done
                ? 'var(--green)'
                : i === firstOpen ? 'var(--accent-ink)' : 'var(--muted)',
            }}
          >
            {c.done && <Check size={14} strokeWidth={3} />}
            {c.label}
          </Link>
        ))}
      </div>
    </div>
  )
}

export default function Dashboard() {
  const [drillDown, setDrillDown] = useState<string | null>(null)
  const [metricsConfig] = useState<string[]>(loadMetricsConfig)

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

  const { data: settings } = useQuery<Settings>({
    queryKey: ['settings'],
    queryFn: () => apiGet('/api/settings'),
  })

  // Same query key the Log page uses, so the two share one cache entry.
  const { data: streak } = useQuery<StreakInfo>({
    queryKey: ['streak'],
    queryFn: () => apiGet('/api/checkin/streak'),
  })

  // Only fetched when the tile is on: the trend model is a separate, heavier
  // query than the dashboard roll-up and nothing else on this page needs it.
  const showWeight = metricsConfig.includes('weight')
  const { data: weightProgress } = useQuery<WeightProgress>({
    queryKey: ['weight-progress', 90, 0],
    queryFn: () => apiGet('/api/analytics/weight-progress?days=90&horizon=0'),
    enabled: showWeight,
  })

  // series is sorted oldest-first; last entry = today
  const today = dash?.series?.[dash.series.length - 1]
  // Garmin's burn total only covers the day so far, so today's balance is
  // measured against the projected full-day burn instead.
  const projBalance = today?.balance_projected ?? today?.balance ?? null
  const avg7 = dash?.averages_7d
  const recentWorkouts = workouts?.slice(0, 3)
  // The sparkline in each tile replaces the separate Trends card, which drew
  // the same four metrics again lower down the page.
  const sparkWindow = dash?.series?.slice(-14) ?? []

  return (
    <div style={{ padding: 'var(--s4)' }}>
      <SyncStatusCard />

      {isLoading ? (
        <SkeletonLoader height="136px" borderRadius="22px" />
      ) : (
        dash?.readiness && <ReadinessHero readiness={dash.readiness} />
      )}

      {streak && <TodayLoop streak={streak} weightLogged={today?.weight != null} />}

      {/* Energy */}
      <Link to="/log" style={{ textDecoration: 'none', color: 'inherit' }}>
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <span className="text-title">Today's Log</span>
            <ChevronRight size={16} color="var(--muted)" />
          </div>
          {today ? (
            // 2x2 rather than a 4-wide row: four values do not fit across 390px
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px 16px' }}>
              <div>
                <div className="text-caption">Calories In</div>
                <div className="text-body tabular" style={{ fontWeight: 600 }}>{today.calories_in ?? '–'}</div>
              </div>
              <div>
                <div className="text-caption">Burned</div>
                <div className="text-body tabular" style={{ fontWeight: 600 }}>{today.calories_out ?? '–'}</div>
              </div>
              <div>
                <div className="text-caption">Projected Burn</div>
                <div className="text-body tabular" style={{ fontWeight: 600 }}>{today.calories_out_projected ?? '–'}</div>
              </div>
              <div>
                <div className="text-caption">Balance (proj)</div>
                <div className="text-body tabular" style={{
                  fontWeight: 600,
                  color: projBalance != null ? getBalanceColor(projBalance, settings?.daily_balance_target ?? null) : undefined,
                }}>
                  {projBalance != null ? `${projBalance > 0 ? '+' : ''}${projBalance}` : '–'}
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

      {/* Metrics. A 2-up grid rather than a horizontal strip: a side-scroll
          nobody discovers hid whichever tiles came after the third. */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 10, marginBottom: 12 }}>
        {isLoading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <SkeletonLoader key={i} height="104px" borderRadius="18px" />
          ))
        ) : (
          metricsConfig.map(key => {
            const def = METRIC_DEFS[key]
            if (!def) return null
            const Icon = def.icon
            const spark = sparkWindow.map(d => getMetricValue(d, key))

            // Weight reads from the trend model: the tile shows the smoothed
            // weight and its weekly rate, coloured by how that rate compares
            // with the goal, rather than a raw reading against a 7-day mean.
            if (key === 'weight') {
              const cur = weightProgress?.current
              return (
                <MetricCard
                  key={key}
                  icon={<Icon size={13} />}
                  label={def.label}
                  value={cur ? cur.trend_kg.toFixed(1) : null}
                  unit={def.unit}
                  delta={cur ? { value: cur.rate_kg_per_week, suffix: ' kg/wk' } : undefined}
                  deltaColor={cur?.status ? statusColor(cur.status) : undefined}
                  deltaText={cur ? formatRate(cur.rate_kg_per_week) : undefined}
                  spark={spark}
                  onClick={() => setDrillDown(key)}
                />
              )
            }

            const val = getMetricValue(today, key)
            const avgVal = getAvgValue(avg7, key)
            const delta = val != null && avgVal != null ? +(val - avgVal).toFixed(1) : undefined
            return (
              <MetricCard
                key={key}
                icon={<Icon size={13} />}
                label={def.label}
                value={val != null ? val.toLocaleString() : null}
                unit={def.unit}
                delta={delta != null ? { value: delta, suffix: def.unit ? ` ${def.unit}` : '' } : undefined}
                spark={spark}
                onClick={() => setDrillDown(key)}
              />
            )
          })
        )}
      </div>

      {/* Recent Activities */}
      {recentWorkouts && recentWorkouts.length > 0 && (
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <span className="text-title">Recent Activities</span>
            <Link
              to="/workouts"
              style={{ color: 'var(--accent)', fontSize: '0.8rem', fontWeight: 600, textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 4, minHeight: 44, paddingLeft: 12 }}
            >
              See all <ChevronRight size={14} />
            </Link>
          </div>
          {recentWorkouts.map(w => (
            <Link
              key={w.id}
              to={`/workouts/${w.id}`}
              style={{ display: 'flex', alignItems: 'center', gap: 12, minHeight: 44, padding: '10px 0', borderBottom: '1px solid var(--border)', textDecoration: 'none', color: 'var(--text)' }}
            >
              <Activity size={18} color="var(--muted)" />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="text-body">{w.name || w.type}</div>
                <div className="text-caption">{w.date}{w.duration_min ? ` · ${w.duration_min}min` : ''}</div>
              </div>
              <ChevronRight size={16} color="var(--muted)" />
            </Link>
          ))}
        </div>
      )}

      {/* Insights */}
      {correlations?.insights && correlations.insights.filter(i => i.status === 'ok').length > 0 && (
        <Link to="/insights" style={{ textDecoration: 'none', color: 'inherit' }}>
          <div className="card">
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

      {/* Metric Drill-Downs */}
      {drillDown && (
        <MetricDrillDown
          open={!!drillDown}
          onClose={() => setDrillDown(null)}
          title={METRIC_DEFS[drillDown]?.label || drillDown}
          value={
            drillDown === 'weight'
              // the raw trend carries 3 decimals; a body weight wants one
              ? weightProgress?.current
                ? `${weightProgress.current.trend_kg.toFixed(1)} kg`
                : undefined
              : today ? getMetricValue(today, drillDown)?.toString() : undefined
          }
        >
          {drillDown === 'sleep_score' && <SleepDrillDown />}
          {drillDown === 'hrv' && <HrvDrillDown />}
          {drillDown === 'weight' && <WeightDrillDown />}
          {drillDown === 'calories_out' && <GenericDrillDown metricKey="calories_out" unit="kcal" />}
          {drillDown === 'steps' && <GenericDrillDown metricKey="steps" />}
          {drillDown === 'resting_hr' && <GenericDrillDown metricKey="resting_hr" unit="bpm" />}
          {drillDown === 'body_battery' && <BodyBatteryDrillDown />}
        </MetricDrillDown>
      )}
    </div>
  )
}
