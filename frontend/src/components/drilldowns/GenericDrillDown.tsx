import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip } from 'recharts'
import { apiGet } from '../../api/client'
import type { Dashboard } from '../../api/types'
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

export default function GenericDrillDown({ metricKey, unit }: { metricKey: string; unit?: string }) {
  const [days, setDays] = useState(30)
  const { data, isLoading } = useQuery<Dashboard>({
    queryKey: ['dashboard', days],
    queryFn: () => apiGet(`/api/analytics/dashboard?days=${days}`),
  })

  const chartData = (data?.series ?? [])
    .map(d => ({
      date: d.date.slice(5),
      value: (d as unknown as Record<string, number | null>)[metricKey] ?? null,
    }))
    .filter(d => d.value != null)

  const values = chartData.map(d => d.value as number)
  const latest = values[values.length - 1] ?? null
  const avg7 = values.slice(-7)
  const avg7val = avg7.length ? Math.round(avg7.reduce((a, b) => a + b, 0) / avg7.length) : null
  const avg30 = values.slice(-30)
  const avg30val = avg30.length ? Math.round(avg30.reduce((a, b) => a + b, 0) / avg30.length) : null

  const fmt = (v: number | null) => v != null ? `${v}${unit ? ` ${unit}` : ''}` : '–'

  return (
    <div>
      {/* Summary row */}
      <div style={{ display: 'flex', gap: 24, marginBottom: 16, flexWrap: 'wrap' }}>
        <div>
          <div className="text-caption">Latest</div>
          <div className="text-body" style={{ fontWeight: 600 }}>{fmt(latest)}</div>
        </div>
        <div>
          <div className="text-caption">7d avg</div>
          <div className="text-body" style={{ fontWeight: 600 }}>{fmt(avg7val)}</div>
        </div>
        <div>
          <div className="text-caption">30d avg</div>
          <div className="text-body" style={{ fontWeight: 600 }}>{fmt(avg30val)}</div>
        </div>
      </div>

      <RangePicker value={days} onChange={setDays} />

      {/* Chart */}
      <div style={{ marginTop: 16 }}>
        {isLoading ? (
          <SkeletonLoader height="200px" borderRadius="14px" />
        ) : (
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={chartData}>
              <XAxis
                dataKey="date"
                tick={{ fill: 'var(--muted)', fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                minTickGap={30}
              />
              <YAxis
                domain={['dataMin - 5', 'dataMax + 5']}
                tick={{ fill: 'var(--muted)', fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                width={40}
              />
              <Tooltip {...tooltipStyle} />
              <Line
                type="monotone"
                dataKey="value"
                stroke="var(--accent)"
                strokeWidth={2}
                dot={false}
                name={unit ? `(${unit})` : metricKey}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* History table */}
      {!isLoading && chartData.length > 0 && (
        <div style={{ marginTop: 20 }}>
          <div className="text-title" style={{ marginBottom: 8 }}>Recent</div>
          {chartData.slice(-14).reverse().map((d, i) => (
            <div
              key={i}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                padding: '8px 0',
                borderBottom: '1px solid var(--border)',
              }}
            >
              <span className="text-caption">{d.date}</span>
              <span className="text-body" style={{ fontWeight: 600 }}>
                {d.value}{unit ? ` ${unit}` : ''}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
