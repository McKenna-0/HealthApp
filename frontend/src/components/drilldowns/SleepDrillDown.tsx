import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
} from 'recharts'
import { apiGet } from '../../api/client'
import type { SleepRow } from '../../api/types'
import RangePicker from '../RangePicker'
import SkeletonLoader from '../SkeletonLoader'

const tooltipStyle = {
  contentStyle: {
    background: 'var(--card-elevated)',
    border: '1px solid var(--border)',
    borderRadius: 8,
    color: 'var(--text)',
  },
}

function isoDaysAgo(n: number) {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return d.toISOString().slice(0, 10)
}

export default function SleepDrillDown() {
  const [days, setDays] = useState(30)

  const { data: rows, isLoading } = useQuery<SleepRow[]>({
    queryKey: ['sleep', days],
    queryFn: () => apiGet(`/api/sleep?start=${isoDaysAgo(days - 1)}`),
  })

  const data = (rows ?? []).map(r => ({
    date: r.date.slice(5),
    deep: r.deep_min != null ? +(r.deep_min / 60).toFixed(1) : null,
    light: r.light_min != null ? +(r.light_min / 60).toFixed(1) : null,
    rem: r.rem_min != null ? +(r.rem_min / 60).toFixed(1) : null,
    awake: r.awake_min != null ? +(r.awake_min / 60).toFixed(1) : null,
    score: r.sleep_score,
    hrv: r.avg_overnight_hrv,
    duration: r.duration_min != null ? +(r.duration_min / 60).toFixed(1) : null,
  }))

  const latest = data[data.length - 1]

  const scoredRows = data.filter(d => d.score != null)
  const avgScore = scoredRows.length
    ? Math.round(scoredRows.reduce((s, d) => s + (d.score ?? 0), 0) / scoredRows.length)
    : null

  const durationRows = data.filter(d => d.duration != null)
  const avgDuration = durationRows.length
    ? (durationRows.reduce((s, d) => s + (d.duration ?? 0), 0) / durationRows.length).toFixed(1)
    : null

  const hasHrv = data.some(d => d.hrv != null)

  return (
    <div>
      {/* Summary row */}
      <div style={{ display: 'flex', gap: 20, marginBottom: 16, flexWrap: 'wrap' }}>
        <div>
          <div className="text-caption">Last Night</div>
          <div className="text-body" style={{ fontWeight: 600 }}>
            {latest?.duration != null ? `${latest.duration}h` : '–'}
          </div>
        </div>
        <div>
          <div className="text-caption">Score</div>
          <div className="text-body" style={{ fontWeight: 600 }}>{latest?.score ?? '–'}</div>
        </div>
        <div>
          <div className="text-caption">Avg Score</div>
          <div className="text-body" style={{ fontWeight: 600 }}>{avgScore ?? '–'}</div>
        </div>
        <div>
          <div className="text-caption">Avg Duration</div>
          <div className="text-body" style={{ fontWeight: 600 }}>
            {avgDuration != null ? `${avgDuration}h` : '–'}
          </div>
        </div>
        <div>
          <div className="text-caption">Deep</div>
          <div className="text-body" style={{ fontWeight: 600 }}>
            {latest?.deep != null ? `${Math.round(latest.deep * 60)}m` : '–'}
          </div>
        </div>
        <div>
          <div className="text-caption">REM</div>
          <div className="text-body" style={{ fontWeight: 600 }}>
            {latest?.rem != null ? `${Math.round(latest.rem * 60)}m` : '–'}
          </div>
        </div>
      </div>

      <RangePicker value={days} onChange={setDays} />

      {isLoading ? (
        <SkeletonLoader height="400px" borderRadius="14px" />
      ) : (
        <>
          {/* Sleep stages stacked bar */}
          <div className="text-title" style={{ margin: '16px 0 8px' }}>Sleep Stages</div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={data}>
              <XAxis
                dataKey="date"
                tick={{ fill: 'var(--muted)', fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                minTickGap={20}
              />
              <YAxis
                tick={{ fill: 'var(--muted)', fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                width={30}
              />
              <Tooltip {...tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: 11, color: 'var(--muted)' }} />
              <Bar dataKey="deep" stackId="a" fill="#6366f1" name="Deep" />
              <Bar dataKey="light" stackId="a" fill="#38bdf8" name="Light" />
              <Bar dataKey="rem" stackId="a" fill="#a78bfa" name="REM" />
              <Bar dataKey="awake" stackId="a" fill="#f87171" name="Awake" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>

          {/* Sleep score line */}
          <div className="text-title" style={{ margin: '16px 0 8px' }}>Sleep Score</div>
          <ResponsiveContainer width="100%" height={150}>
            <LineChart data={data}>
              <XAxis
                dataKey="date"
                tick={{ fill: 'var(--muted)', fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                minTickGap={20}
              />
              <YAxis
                domain={[0, 100]}
                tick={{ fill: 'var(--muted)', fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                width={30}
              />
              <Tooltip {...tooltipStyle} />
              <Line
                type="monotone"
                dataKey="score"
                stroke="var(--accent)"
                strokeWidth={2}
                dot={false}
                name="Score"
              />
            </LineChart>
          </ResponsiveContainer>

          {/* Overnight HRV */}
          {hasHrv && (
            <>
              <div className="text-title" style={{ margin: '16px 0 8px' }}>Overnight HRV</div>
              <ResponsiveContainer width="100%" height={150}>
                <LineChart data={data.filter(d => d.hrv != null)}>
                  <XAxis
                    dataKey="date"
                    tick={{ fill: 'var(--muted)', fontSize: 11 }}
                    tickLine={false}
                    axisLine={false}
                    minTickGap={20}
                  />
                  <YAxis
                    tick={{ fill: 'var(--muted)', fontSize: 11 }}
                    tickLine={false}
                    axisLine={false}
                    width={30}
                  />
                  <Tooltip {...tooltipStyle} />
                  <Line
                    type="monotone"
                    dataKey="hrv"
                    stroke="var(--green)"
                    strokeWidth={2}
                    dot={false}
                    name="HRV (ms)"
                  />
                </LineChart>
              </ResponsiveContainer>
            </>
          )}
        </>
      )}
    </div>
  )
}
