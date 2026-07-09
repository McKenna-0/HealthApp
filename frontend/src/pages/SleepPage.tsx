import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { apiGet } from '../api/client'
import type { SleepRow } from '../api/types'
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

export default function SleepPage() {
  const [days, setDays] = useState(30)
  const { data, isLoading, error } = useQuery({
    queryKey: ['sleep', days],
    queryFn: () => apiGet<SleepRow[]>(`/api/sleep?start=${isoDaysAgo(days - 1)}`),
  })

  if (isLoading) return <p className="muted">Loading…</p>
  if (error || !data) return <p className="error-text">Failed to load: {String(error)}</p>

  const rows = data.map((r) => ({
    ...r,
    deep_h: r.deep_min != null ? +(r.deep_min / 60).toFixed(2) : null,
    light_h: r.light_min != null ? +(r.light_min / 60).toFixed(2) : null,
    rem_h: r.rem_min != null ? +(r.rem_min / 60).toFixed(2) : null,
    awake_h: r.awake_min != null ? +(r.awake_min / 60).toFixed(2) : null,
  }))
  const last = rows[rows.length - 1]
  const avgScore =
    rows.filter((r) => r.sleep_score != null).reduce((a, r) => a + (r.sleep_score ?? 0), 0) /
    Math.max(1, rows.filter((r) => r.sleep_score != null).length)

  return (
    <>
      <h1>Sleep</h1>
      <div className="metric-grid">
        <MetricCard
          label="Last night"
          value={last?.duration_min != null ? `${Math.floor(last.duration_min / 60)}h ${last.duration_min % 60}m` : '–'}
        />
        <MetricCard label="Score" value={last?.sleep_score} sub={`avg ${avgScore.toFixed(0)}`} />
        <MetricCard label="Deep" value={last?.deep_min != null ? `${last.deep_min}m` : '–'} />
        <MetricCard label="REM" value={last?.rem_min != null ? `${last.rem_min}m` : '–'} />
      </div>

      <h2>History</h2>
      <RangePicker value={days} onChange={setDays} />

      <ChartCard title="Sleep stages (hours)" height={220}>
        <BarChart data={rows}>
          <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
          <XAxis dataKey="date" tickFormatter={(d: string) => d.slice(5)} tick={axisStyle} minTickGap={30} />
          <YAxis tick={axisStyle} width={30} />
          <Tooltip {...tooltipStyle} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Bar dataKey="deep_h" stackId="s" fill="#1d4ed8" name="Deep" />
          <Bar dataKey="light_h" stackId="s" fill="#38bdf8" name="Light" />
          <Bar dataKey="rem_h" stackId="s" fill="#a78bfa" name="REM" />
          <Bar dataKey="awake_h" stackId="s" fill="#f87171" name="Awake" />
        </BarChart>
      </ChartCard>

      <ChartCard title="Sleep score">
        <LineChart data={rows}>
          <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
          <XAxis dataKey="date" tickFormatter={(d: string) => d.slice(5)} tick={axisStyle} minTickGap={30} />
          <YAxis tick={axisStyle} width={30} domain={[0, 100]} />
          <Tooltip {...tooltipStyle} />
          <Line dataKey="sleep_score" stroke="#a78bfa" dot={false} strokeWidth={2} />
        </LineChart>
      </ChartCard>

      <ChartCard title="Overnight HRV">
        <LineChart data={rows}>
          <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
          <XAxis dataKey="date" tickFormatter={(d: string) => d.slice(5)} tick={axisStyle} minTickGap={30} />
          <YAxis tick={axisStyle} width={30} domain={['auto', 'auto']} />
          <Tooltip {...tooltipStyle} />
          <Line dataKey="avg_overnight_hrv" stroke="#38bdf8" dot={false} strokeWidth={2} name="HRV" />
        </LineChart>
      </ChartCard>
    </>
  )
}
