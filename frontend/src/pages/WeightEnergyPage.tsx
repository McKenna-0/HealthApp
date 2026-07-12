import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { apiGet } from '../api/client'
import type { EnergyBalanceDay, TdeeResult, WeightTrendPoint } from '../api/types'
import ChartCard from '../components/ChartCard'
import MetricCard from '../components/MetricCard'
import RangePicker from '../components/RangePicker'

const axisStyle = { fontSize: 10, fill: '#94a3b8' }
const tooltipStyle = {
  contentStyle: { background: '#1e293b', border: '1px solid #334155', borderRadius: 8 },
  labelStyle: { color: '#94a3b8' },
}

function isoDaysAgo(n: number) {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return d.toISOString().slice(0, 10)
}

function computeGoalEta(
  trendWeight: number | null,
  goal: number | null,
  slopePerWeek: number | null,
): string | null {
  if (trendWeight == null || goal == null || slopePerWeek == null) return null
  const remaining = goal - trendWeight
  if (Math.abs(remaining) < 0.3) return 'You are at your goal.'
  if (Math.abs(slopePerWeek) < 0.05) return 'Trend is flat — no ETA at current rate.'
  if (Math.sign(remaining) !== Math.sign(slopePerWeek)) {
    return `Trend is moving away from your ${goal} kg goal.`
  }
  const weeks = remaining / slopePerWeek
  if (weeks > 104) return `More than 2 years to ${goal} kg at the current rate.`
  const eta = new Date()
  eta.setDate(eta.getDate() + Math.round(weeks * 7))
  const sign = slopePerWeek > 0 ? '+' : ''
  return `At ${sign}${slopePerWeek.toFixed(2)} kg/wk you reach ${goal} kg ~${eta.toISOString().slice(0, 10)}.`
}

export default function WeightEnergyPage() {
  const [days, setDays] = useState(90)
  const start = isoDaysAgo(days - 1)

  const trend = useQuery({
    queryKey: ['weight-trend', days],
    queryFn: () => apiGet<WeightTrendPoint[]>(`/api/analytics/weight-trend?start=${start}`),
  })
  const balance = useQuery({
    queryKey: ['energy-balance', days],
    queryFn: () => apiGet<EnergyBalanceDay[]>(`/api/analytics/energy-balance?start=${start}`),
  })
  const tdee = useQuery({
    queryKey: ['tdee'],
    queryFn: () => apiGet<TdeeResult>('/api/analytics/tdee'),
  })
  const settings = useQuery({
    queryKey: ['settings'],
    queryFn: () => apiGet<{ weight_goal_kg: number | null }>('/api/settings'),
  })

  if (trend.isLoading || balance.isLoading) return <p className="muted">Loading…</p>
  if (trend.error || !trend.data) return <p className="error-text">Failed to load: {String(trend.error)}</p>

  const latest = [...trend.data].reverse().find((p) => p.trend != null)
  const t = tdee.data
  const goal = settings.data?.weight_goal_kg ?? null
  const goalEta = computeGoalEta(latest?.trend ?? null, goal, t?.weight_slope_kg_per_week ?? null)

  return (
    <>
      <h1>Weight & Energy</h1>
      <div className="metric-grid">
        <MetricCard label="Trend weight" value={latest?.trend != null ? `${latest.trend.toFixed(1)} kg` : '–'} />
        <MetricCard
          label="TDEE est."
          value={t?.tdee != null ? `${t.tdee}` : '–'}
          sub={t?.tdee != null ? 'kcal/day' : t?.reason ?? undefined}
        />
        <MetricCard
          label="Trend / week"
          value={t?.weight_slope_kg_per_week != null ? `${t.weight_slope_kg_per_week > 0 ? '+' : ''}${t.weight_slope_kg_per_week.toFixed(2)} kg` : '–'}
        />
        <MetricCard label="Garmin out" value={t?.garmin_mean_calories_out ?? '–'} sub="kcal/day avg" />
      </div>

      {t && t.tdee == null && t.reason && (
        <div className="card">
          <span className="muted">TDEE unavailable: {t.reason}</span>
        </div>
      )}

      {goalEta && (
        <div className="card">
          <span className="muted">🎯 {goalEta}</span>
        </div>
      )}

      <h2>History</h2>
      <RangePicker value={days} onChange={setDays} />

      <ChartCard title="Weight (kg)" height={220}>
        <LineChart data={trend.data}>
          <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
          <XAxis dataKey="date" tickFormatter={(d: string) => d.slice(5)} tick={axisStyle} minTickGap={30} />
          <YAxis
            tick={axisStyle}
            width={40}
            domain={[
              (dataMin: number) => Math.floor(goal != null ? Math.min(dataMin, goal) - 1 : dataMin - 1),
              (dataMax: number) => Math.ceil(goal != null ? Math.max(dataMax, goal) + 1 : dataMax + 1),
            ]}
          />
          <Tooltip {...tooltipStyle} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          {goal != null && (
            <ReferenceLine
              y={goal}
              stroke="#fbbf24"
              strokeDasharray="5 5"
              label={{ value: 'goal', fontSize: 10, fill: '#fbbf24', position: 'insideTopRight' }}
            />
          )}
          <Line dataKey="weight" stroke="#64748b" strokeWidth={0} dot={{ r: 2 }} name="Daily" />
          <Line dataKey="trend" stroke="#4ade80" dot={false} strokeWidth={2} name="Trend (EWMA)" />
        </LineChart>
      </ChartCard>

      <ChartCard title="Energy balance (kcal/day)" height={220}>
        <BarChart data={balance.data ?? []}>
          <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
          <XAxis dataKey="date" tickFormatter={(d: string) => d.slice(5)} tick={axisStyle} minTickGap={30} />
          <YAxis tick={axisStyle} width={40} />
          <Tooltip {...tooltipStyle} />
          <Bar dataKey="balance" name="Balance">
            {(balance.data ?? []).map((d) => (
              <Cell
                key={d.date}
                fill={!d.valid ? '#475569' : (d.balance ?? 0) > 0 ? '#f87171' : '#4ade80'}
              />
            ))}
          </Bar>
          <Line dataKey="balance_7d_avg" stroke="#fbbf24" dot={false} name="7d avg" />
        </BarChart>
      </ChartCard>

      <ChartCard title="Calories in vs out">
        <LineChart data={balance.data ?? []}>
          <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
          <XAxis dataKey="date" tickFormatter={(d: string) => d.slice(5)} tick={axisStyle} minTickGap={30} />
          <YAxis tick={axisStyle} width={40} domain={['auto', 'auto']} />
          <Tooltip {...tooltipStyle} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Line dataKey="calories_in" stroke="#38bdf8" dot={false} name="In" />
          <Line dataKey="calories_out" stroke="#f87171" dot={false} name="Out" />
        </LineChart>
      </ChartCard>
    </>
  )
}
