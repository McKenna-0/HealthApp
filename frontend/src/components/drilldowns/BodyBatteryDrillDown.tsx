import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ComposedChart,
  Area,
  Line,
  Scatter,
  ReferenceArea,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { ChevronLeft, ChevronRight, Moon, Sunrise, Dumbbell, Footprints, Activity as ActivityIcon } from 'lucide-react'
import { apiGet } from '../../api/client'
import type {
  IntradayBodyBatteryPoint,
  IntradayStressPoint,
  BodyBatteryFactor,
  SleepRow,
  Workout,
} from '../../api/types'
import SkeletonLoader from '../SkeletonLoader'

const tooltipStyle = {
  contentStyle: {
    background: 'var(--card-elevated)',
    border: '1px solid var(--border)',
    borderRadius: 8,
    color: 'var(--text)',
  },
}

const UNMEASURABLE_GAP_MIN = 25
const REST_STRESS_THRESHOLD = 25
const DAY_MIN = 1440
const AXIS_TICKS = [0, 240, 480, 720, 960, 1200]

function isoToday(): string {
  return new Date().toISOString().slice(0, 10)
}

function offsetDate(dateStr: string, days: number): string {
  const d = new Date(dateStr)
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

function toMinutes(hhmm: string): number {
  const [h, m] = hhmm.split(':').map(Number)
  return h * 60 + m
}

function minuteLabel(min: number): string {
  const h = Math.floor(min / 60) % 24
  return `${String(h).padStart(2, '0')}:00`
}

// Minutes since local midnight of `refDate`, for an ISO timestamp that may
// land on the previous/next calendar day (overnight sleep, late workouts).
function minuteOfDay(iso: string, refDate: string): number {
  const dt = new Date(iso)
  const ref = new Date(`${refDate}T00:00:00`)
  return (dt.getTime() - ref.getTime()) / 60000
}

function clipToDay(start: number, end: number): [number, number] | null {
  const s = Math.max(0, start)
  const e = Math.min(DAY_MIN, end)
  if (e <= s) return null
  return [s, e]
}

function activityIcon(type: string | null | undefined) {
  if (type === 'running') return Footprints
  if (type === 'strength_training') return Dumbbell
  return ActivityIcon
}

function EventIcon(props: { cx?: number; cy?: number; payload?: { icon: typeof Moon; color: string } }) {
  const { cx, cy, payload } = props
  if (cx == null || cy == null || !payload) return null
  const Icon = payload.icon
  return (
    <foreignObject x={cx - 9} y={cy - 9} width={18} height={18} style={{ overflow: 'visible' }}>
      <div
        style={{
          width: 18,
          height: 18,
          borderRadius: '50%',
          background: payload.color,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Icon size={11} color="#0B0F14" />
      </div>
    </foreignObject>
  )
}

function ToggleChip({ active, color, label, onClick }: { active: boolean; color: string; label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        minHeight: 44,
        padding: '6px 12px',
        borderRadius: 999,
        border: `1px solid ${active ? color : 'var(--border)'}`,
        background: active ? `${color}22` : 'transparent',
        color: active ? 'var(--text)' : 'var(--muted)',
        cursor: 'pointer',
      }}
      className="text-caption"
    >
      <span style={{ width: 8, height: 8, borderRadius: '50%', background: color, flexShrink: 0 }} />
      {label}
    </button>
  )
}

export default function BodyBatteryDrillDown() {
  const [date, setDate] = useState(isoToday)
  const [showBodyBattery, setShowBodyBattery] = useState(true)
  const [showRest, setShowRest] = useState(true)
  const [showStress, setShowStress] = useState(true)

  const { data: bbData, isLoading: bbLoading } = useQuery<IntradayBodyBatteryPoint[]>({
    queryKey: ['intraday-body-battery', date],
    queryFn: () => apiGet(`/api/metrics/body-battery/intraday?date=${date}`),
  })

  const { data: stressData, isLoading: stressLoading } = useQuery<IntradayStressPoint[]>({
    queryKey: ['intraday-stress', date],
    queryFn: () => apiGet(`/api/metrics/stress/intraday?date=${date}`),
  })

  const { data: sleepRows } = useQuery<SleepRow[]>({
    queryKey: ['sleep-range', date],
    queryFn: () => apiGet(`/api/sleep?start=${offsetDate(date, -1)}&end=${offsetDate(date, 1)}`),
  })

  const { data: activityRows } = useQuery<Workout[]>({
    queryKey: ['activities-for-day', date],
    queryFn: () => apiGet(`/api/activities?start=${date}&end=${date}`),
  })

  const { data: factors } = useQuery<BodyBatteryFactor[]>({
    queryKey: ['body-battery-factors', date],
    queryFn: () => apiGet(`/api/metrics/body-battery/factors?date=${date}`),
  })

  const isLoading = bbLoading || stressLoading

  // Merge into a single series keyed by minute-of-day
  const merged: Record<number, { minute: number; time: string; body_battery?: number; stress?: number; stress_rest?: number; stress_active?: number }> = {}
  for (const pt of bbData ?? []) {
    const min = toMinutes(pt.timestamp)
    merged[min] = { ...merged[min], minute: min, time: pt.timestamp, body_battery: pt.body_battery }
  }
  for (const pt of stressData ?? []) {
    const min = toMinutes(pt.timestamp)
    merged[min] = { ...merged[min], minute: min, time: pt.timestamp, stress: pt.stress_level }
  }
  const chartData = Object.values(merged).sort((a, b) => a.minute - b.minute)

  // Split stress into rest/active segments for Garmin-style colored fill
  for (let i = 0; i < chartData.length; i++) {
    const pt = chartData[i]
    if (pt.stress == null) continue
    const isRest = pt.stress < REST_STRESS_THRESHOLD
    pt.stress_rest = isRest ? pt.stress : undefined
    pt.stress_active = !isRest ? pt.stress : undefined
    // Bridge threshold crossings to avoid visual gaps
    if (i > 0) {
      const prev = chartData[i - 1]
      if (prev.stress != null) {
        const prevRest = prev.stress < REST_STRESS_THRESHOLD
        if (prevRest !== isRest) {
          pt.stress_rest = pt.stress
          pt.stress_active = pt.stress
        }
      }
    }
  }

  const bbValues = (bbData ?? []).map(p => p.body_battery)
  const latest = bbValues.length ? bbValues[bbValues.length - 1] : null
  const high = bbValues.length ? Math.max(...bbValues) : null
  const low = bbValues.length ? Math.min(...bbValues) : null

  // Rest bands: sleep windows overlapping this date's 00:00-24:00 span
  const restBands: [number, number][] = []
  const wakeEvents: { minute: number; icon: typeof Moon; color: string; key: string }[] = []
  for (const s of sleepRows ?? []) {
    if (!s.start_ts || !s.end_ts) continue
    const clipped = clipToDay(minuteOfDay(s.start_ts, date), minuteOfDay(s.end_ts, date))
    if (!clipped) continue
    restBands.push(clipped)
    if (s.date === date) {
      wakeEvents.push({ minute: clipped[1], icon: Sunrise, color: 'var(--amber)', key: `wake-${s.date}` })
    } else if (s.date === offsetDate(date, 1)) {
      wakeEvents.push({ minute: clipped[0], icon: Moon, color: 'var(--accent)', key: `sleep-${s.date}` })
    }
  }

  // Active bands: today's workouts
  const activeBands: [number, number][] = []
  const activityEvents: { minute: number; icon: typeof Moon; color: string; key: string }[] = []
  for (const a of activityRows ?? []) {
    if (!a.start_ts) continue
    const startMin = minuteOfDay(a.start_ts, date)
    const clipped = clipToDay(startMin, startMin + (a.duration_min ?? 0))
    if (!clipped) continue
    activeBands.push(clipped)
    activityEvents.push({ minute: clipped[0], icon: activityIcon(a.type), color: 'var(--green)', key: `act-${a.id}` })
  }

  // Unmeasurable bands: gaps between consecutive body-battery readings
  const unmeasurableBands: [number, number][] = []
  const bbMinutes = (bbData ?? []).map(p => toMinutes(p.timestamp)).sort((a, b) => a - b)
  for (let i = 1; i < bbMinutes.length; i++) {
    if (bbMinutes[i] - bbMinutes[i - 1] > UNMEASURABLE_GAP_MIN) {
      unmeasurableBands.push([bbMinutes[i - 1], bbMinutes[i]])
    }
  }

  const events = [...wakeEvents, ...activityEvents].map(e => ({ ...e, y: 3 }))

  const isToday = date === isoToday()

  return (
    <div>
      {/* Date navigation */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <button
          onClick={() => setDate(d => offsetDate(d, -1))}
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text)', padding: 4, minWidth: 44, minHeight: 44 }}
        >
          <ChevronLeft size={20} />
        </button>
        <span className="text-body" style={{ flex: 1, textAlign: 'center', fontWeight: 600 }}>
          {date}
        </span>
        <button
          onClick={() => setDate(d => offsetDate(d, 1))}
          disabled={isToday}
          style={{
            background: 'none',
            border: 'none',
            cursor: isToday ? 'default' : 'pointer',
            color: isToday ? 'var(--muted)' : 'var(--text)',
            padding: 4,
            minWidth: 44,
            minHeight: 44,
          }}
        >
          <ChevronRight size={20} />
        </button>
      </div>

      {/* Summary */}
      <div style={{ display: 'flex', gap: 24, marginBottom: 16, flexWrap: 'wrap' }}>
        <div>
          <div className="text-caption">{isToday ? 'Current' : 'Latest'}</div>
          <div className="text-body" style={{ fontWeight: 600 }}>{latest ?? '–'}</div>
        </div>
        <div>
          <div className="text-caption">High</div>
          <div className="text-body" style={{ fontWeight: 600 }}>{high ?? '–'}</div>
        </div>
        <div>
          <div className="text-caption">Low</div>
          <div className="text-body" style={{ fontWeight: 600 }}>{low ?? '–'}</div>
        </div>
      </div>

      {/* Toggles */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <ToggleChip active={showBodyBattery} color="var(--accent)" label="Body Battery" onClick={() => setShowBodyBattery(v => !v)} />
        <ToggleChip active={showRest} color="var(--accent)" label="Rest" onClick={() => setShowRest(v => !v)} />
        <ToggleChip active={showStress} color="var(--amber)" label="Stress" onClick={() => setShowStress(v => !v)} />
      </div>

      {/* Chart */}
      <div style={{ marginTop: 8, touchAction: 'pan-y' }}>
        {isLoading ? (
          <SkeletonLoader height="230px" borderRadius="14px" />
        ) : chartData.length === 0 ? (
          <div
            style={{
              height: 230,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--muted)',
            }}
            className="text-caption"
          >
            No intraday data available for this date
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={230}>
            <ComposedChart data={chartData} margin={{ top: 5, right: 8, bottom: 0, left: 0 }}>
              <XAxis
                dataKey="minute"
                type="number"
                domain={[0, DAY_MIN]}
                ticks={AXIS_TICKS}
                tickFormatter={minuteLabel}
                tick={{ fill: 'var(--muted)', fontSize: 11 }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                domain={[0, 100]}
                tick={{ fill: 'var(--muted)', fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                width={32}
              />
              <Tooltip
                {...tooltipStyle}
                labelFormatter={(min) => {
                  if (typeof min !== 'number') return min
                  const h = Math.floor(min / 60) % 24
                  const m = Math.round(min % 60)
                  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
                }}
                formatter={(value, name, entry) => {
                  if (name === 'stress_active' && (entry.payload as Record<string, unknown>)?.stress_rest != null) return null
                  const label = name === 'body_battery' ? 'Body Battery'
                    : (name === 'stress_rest' || name === 'stress_active') ? 'Stress'
                    : String(name)
                  return [Math.round(Number(value)), label]
                }}
              />

              {activeBands.map(([s, e], i) => (
                <ReferenceArea key={`active-${i}`} x1={s} x2={e} y1={0} y2={100} fill="var(--green)" fillOpacity={0.12} stroke="none" ifOverflow="visible" />
              ))}
              {unmeasurableBands.map(([s, e], i) => (
                <ReferenceArea key={`unmeasurable-${i}`} x1={s} x2={e} y1={0} y2={100} fill="var(--muted)" fillOpacity={0.14} stroke="none" ifOverflow="visible" />
              ))}

              {showStress && (
                <Area
                  type="monotone"
                  dataKey="stress_active"
                  stroke="var(--amber)"
                  strokeWidth={1}
                  strokeOpacity={0.7}
                  fill="var(--amber)"
                  fillOpacity={0.15}
                  dot={false}
                  connectNulls={false}
                  name="stress_active"
                  isAnimationActive={false}
                />
              )}
              {showRest && (
                <Area
                  type="monotone"
                  dataKey="stress_rest"
                  stroke="var(--accent)"
                  strokeWidth={1}
                  strokeOpacity={0.7}
                  fill="var(--accent)"
                  fillOpacity={0.25}
                  dot={false}
                  connectNulls={false}
                  name="stress_rest"
                  isAnimationActive={false}
                />
              )}

              {showBodyBattery && (
                <Line
                  type="monotone"
                  dataKey="body_battery"
                  stroke="var(--accent)"
                  strokeWidth={2}
                  dot={false}
                  name="body_battery"
                  connectNulls
                  isAnimationActive={false}
                />
              )}

              {events.length > 0 && (
                <Scatter data={events} dataKey="y" shape={EventIcon} isAnimationActive={false} />
              )}
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Factors */}
      {factors && factors.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <div className="text-caption" style={{ marginBottom: 8 }}>Factors</div>
          {factors.map((f, i) => {
            const Icon = f.type === 'sleep' ? Moon : activityIcon(undefined)
            const positive = f.impact >= 0
            return (
              <div
                key={`${f.type}-${f.start_ts}-${i}`}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '8px 0',
                  borderTop: i > 0 ? '1px solid var(--border)' : undefined,
                }}
              >
                <Icon size={16} color="var(--muted)" />
                <div style={{ flex: 1 }}>
                  <div className="text-body">{f.label}</div>
                  <div className="text-caption">
                    {f.start_ts.slice(11, 16)} – {f.end_ts.slice(11, 16)}
                  </div>
                </div>
                <div className="text-body" style={{ fontWeight: 600, color: positive ? 'var(--green)' : 'var(--red)' }}>
                  {positive ? '+' : ''}{f.impact}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
