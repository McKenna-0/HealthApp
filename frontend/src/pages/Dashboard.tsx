import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { apiGet } from '../api/client'
import type { Dashboard as DashboardData } from '../api/types'
import ChartCard from '../components/ChartCard'
import MetricCard from '../components/MetricCard'
import RangePicker from '../components/RangePicker'

const axisStyle = { fontSize: 10, fill: '#94a3b8' }
const tooltipStyle = {
  contentStyle: { background: '#1e293b', border: '1px solid #334155', borderRadius: 8 },
  labelStyle: { color: '#94a3b8' },
}

function shortDate(d: string) {
  return d.slice(5)
}

export default function Dashboard() {
  const [days, setDays] = useState(30)
  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard', days],
    queryFn: () => apiGet<DashboardData>(`/api/analytics/dashboard?days=${days}`),
  })

  if (isLoading) return <p className="muted">Loading…</p>
  if (error || !data) return <p className="error-text">Failed to load: {String(error)}</p>

  const today = data.series[data.series.length - 1]
  const avg = data.averages_7d

  return (
    <>
      <h1>Today</h1>
      <div className="metric-grid">
        <MetricCard label="Steps" value={today?.steps?.toLocaleString()} sub={avg.steps ? `7d ${Math.round(avg.steps).toLocaleString()}` : undefined} />
        <MetricCard label="Resting HR" value={today?.resting_hr} sub={avg.resting_hr ? `7d ${avg.resting_hr}` : undefined} />
        <MetricCard label="HRV" value={today?.hrv} sub={avg.hrv ? `7d ${avg.hrv}` : undefined} />
        <MetricCard label="Sleep score" value={today?.sleep_score} sub={avg.sleep_score ? `7d ${avg.sleep_score}` : undefined} />
        <MetricCard label="Body battery" value={today?.body_battery_high} sub="high" />
        <MetricCard
          label="Kcal in / out"
          value={today?.calories_in != null ? `${today.calories_in}` : '–'}
          sub={today?.calories_out != null ? `out ${today.calories_out}` : undefined}
        />
      </div>

      <h2>Trends</h2>
      <RangePicker value={days} onChange={setDays} />

      <ChartCard title="HRV">
        <LineChart data={data.series}>
          <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
          <XAxis dataKey="date" tickFormatter={shortDate} tick={axisStyle} minTickGap={30} />
          <YAxis tick={axisStyle} width={30} domain={['auto', 'auto']} />
          <Tooltip {...tooltipStyle} />
          <Line dataKey="hrv" stroke="#38bdf8" dot={false} strokeWidth={2} />
        </LineChart>
      </ChartCard>

      <ChartCard title="Resting HR">
        <LineChart data={data.series}>
          <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
          <XAxis dataKey="date" tickFormatter={shortDate} tick={axisStyle} minTickGap={30} />
          <YAxis tick={axisStyle} width={30} domain={['auto', 'auto']} />
          <Tooltip {...tooltipStyle} />
          <Line dataKey="resting_hr" stroke="#f87171" dot={false} strokeWidth={2} />
        </LineChart>
      </ChartCard>

      <ChartCard title="Sleep score">
        <LineChart data={data.series}>
          <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
          <XAxis dataKey="date" tickFormatter={shortDate} tick={axisStyle} minTickGap={30} />
          <YAxis tick={axisStyle} width={30} domain={[0, 100]} />
          <Tooltip {...tooltipStyle} />
          <Line dataKey="sleep_score" stroke="#a78bfa" dot={false} strokeWidth={2} />
        </LineChart>
      </ChartCard>

      <ChartCard title="Steps">
        <BarChart data={data.series}>
          <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
          <XAxis dataKey="date" tickFormatter={shortDate} tick={axisStyle} minTickGap={30} />
          <YAxis tick={axisStyle} width={40} />
          <Tooltip {...tooltipStyle} />
          <Bar dataKey="steps" fill="#38bdf8" />
        </BarChart>
      </ChartCard>

      <ChartCard title="Weight trend">
        <LineChart data={data.series.filter((d) => d.weight_trend != null)}>
          <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
          <XAxis dataKey="date" tickFormatter={shortDate} tick={axisStyle} minTickGap={30} />
          <YAxis tick={axisStyle} width={40} domain={['auto', 'auto']} />
          <Tooltip {...tooltipStyle} />
          <Line dataKey="weight" stroke="#64748b" dot={{ r: 2 }} strokeWidth={0} name="daily" />
          <Line dataKey="weight_trend" stroke="#4ade80" dot={false} strokeWidth={2} name="trend" />
        </LineChart>
      </ChartCard>

      <ChartCard title="Energy balance (kcal)">
        <BarChart data={data.series}>
          <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
          <XAxis dataKey="date" tickFormatter={shortDate} tick={axisStyle} minTickGap={30} />
          <YAxis tick={axisStyle} width={40} />
          <Tooltip {...tooltipStyle} />
          <Bar dataKey="balance">
            {data.series.map((d) => (
              <Cell key={d.date} fill={(d.balance ?? 0) > 0 ? '#f87171' : '#4ade80'} />
            ))}
          </Bar>
        </BarChart>
      </ChartCard>
    </>
  )
}
