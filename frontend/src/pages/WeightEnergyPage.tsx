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

  if (trend.isLoading || balance.isLoading) return <p className="muted">Loading…</p>
  if (trend.error || !trend.data) return <p className="error-text">Failed to load: {String(trend.error)}</p>

  const latest = [...trend.data].reverse().find((p) => p.trend != null)
  const t = tdee.data

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

      <h2>History</h2>
      <RangePicker value={days} onChange={setDays} />

      <ChartCard title="Weight (kg)" height={220}>
        <LineChart data={trend.data}>
          <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
          <XAxis dataKey="date" tickFormatter={(d: string) => d.slice(5)} tick={axisStyle} minTickGap={30} />
          <YAxis tick={axisStyle} width={40} domain={['auto', 'auto']} />
          <Tooltip {...tooltipStyle} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
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
