import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { CorrelationsResponse, Readiness } from '../api/types'
import { InsightCard } from './InsightsPage'
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
import SyncStatusCard from '../components/SyncStatusCard'
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

const READINESS_COLORS: Record<string, string> = {
  green: '#4ade80',
  amber: '#fbbf24',
  red: '#f87171',
  building_baseline: '#38bdf8',
  no_data: '#64748b',
}

function ReadinessCard({ readiness }: { readiness: Readiness | undefined }) {
  const [expanded, setExpanded] = useState(false)
  if (!readiness) return null
  const color = READINESS_COLORS[readiness.status] ?? '#64748b'
  return (
    <div className="card" onClick={() => setExpanded((e) => !e)} style={{ cursor: 'pointer' }}>
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <div className="row" style={{ flex: 1, gap: 10 }}>
          <span
            className="fixed"
            style={{ width: 12, height: 12, borderRadius: '50%', background: color, display: 'inline-block' }}
          />
          <strong>{readiness.label}</strong>
        </div>
        {readiness.score_pct != null && (
          <span className="muted fixed">{readiness.score_pct}%</span>
        )}
      </div>
      {expanded && readiness.components.length > 0 && (
        <table style={{ marginTop: 8 }}>
          <tbody>
            {readiness.components.map((c) => (
              <tr key={c.key}>
                <td className="muted">{c.label}</td>
                <td>
                  {c.value}
                  {c.baseline != null ? ` (base ${c.baseline})` : ''}
                </td>
                <td style={{ textAlign: 'right' }}>
                  {'●'.repeat(c.points)}
                  <span style={{ opacity: 0.25 }}>{'●'.repeat(c.max_points - c.points)}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

function InsightsTeaser() {
  const { data } = useQuery({
    queryKey: ['correlations'],
    queryFn: () => apiGet<CorrelationsResponse>('/api/analytics/correlations?days=90'),
  })
  const established = (data?.insights ?? [])
    .filter((i) => i.status === 'ok' && i.strength && i.strength !== 'none')
    .slice(0, 2)
  if (established.length === 0) return null
  return (
    <>
      <h2>Insights</h2>
      {established.map((i) => (
        <InsightCard key={i.id} insight={i} />
      ))}
      <p style={{ margin: '0 4px 4px', textAlign: 'right' }}>
        <Link to="/insights" className="muted" style={{ fontSize: '0.85rem' }}>
          More insights ›
        </Link>
      </p>
    </>
  )
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
      <SyncStatusCard />
      <ReadinessCard readiness={data.readiness} />
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

      <InsightsTeaser />

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
