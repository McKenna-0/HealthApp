import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { apiGet } from '../../api/client'
import type { IntradayBodyBatteryPoint, IntradayStressPoint } from '../../api/types'
import SkeletonLoader from '../SkeletonLoader'

const tooltipStyle = {
  contentStyle: {
    background: 'var(--card-elevated)',
    border: '1px solid var(--border)',
    borderRadius: 8,
    color: 'var(--text)',
  },
}

function isoToday(): string {
  return new Date().toISOString().slice(0, 10)
}

function offsetDate(dateStr: string, days: number): string {
  const d = new Date(dateStr)
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

export default function BodyBatteryDrillDown() {
  const [date, setDate] = useState(isoToday)

  const { data: bbData, isLoading: bbLoading } = useQuery<IntradayBodyBatteryPoint[]>({
    queryKey: ['intraday-body-battery', date],
    queryFn: () => apiGet(`/api/metrics/body-battery/intraday?date=${date}`),
  })

  const { data: stressData, isLoading: stressLoading } = useQuery<IntradayStressPoint[]>({
    queryKey: ['intraday-stress', date],
    queryFn: () => apiGet(`/api/metrics/stress/intraday?date=${date}`),
  })

  const isLoading = bbLoading || stressLoading

  // Merge into a single series keyed by timestamp
  const merged: Record<string, { time: string; body_battery?: number; stress?: number }> = {}
  for (const pt of bbData ?? []) {
    const key = pt.timestamp
    merged[key] = { ...merged[key], time: key, body_battery: pt.body_battery }
  }
  for (const pt of stressData ?? []) {
    const key = pt.timestamp
    merged[key] = { ...merged[key], time: key, stress: pt.stress_level }
  }
  const chartData = Object.values(merged).sort((a, b) => a.time.localeCompare(b.time))

  const bbValues = (bbData ?? []).map(p => p.body_battery)
  const latest = bbValues.length ? bbValues[bbValues.length - 1] : null
  const high = bbValues.length ? Math.max(...bbValues) : null
  const low = bbValues.length ? Math.min(...bbValues) : null

  const isToday = date === isoToday()
  const useDots = chartData.length < 100

  return (
    <div>
      {/* Date navigation */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <button
          onClick={() => setDate(d => offsetDate(d, -1))}
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text)', padding: 4 }}
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
          }}
        >
          <ChevronRight size={20} />
        </button>
      </div>

      {/* Summary */}
      <div style={{ display: 'flex', gap: 24, marginBottom: 16, flexWrap: 'wrap' }}>
        <div>
          <div className="text-caption">Latest</div>
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

      {/* Chart */}
      <div style={{ marginTop: 8 }}>
        {isLoading ? (
          <SkeletonLoader height="200px" borderRadius="14px" />
        ) : chartData.length === 0 ? (
          <div
            style={{
              height: 200,
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
          <ResponsiveContainer width="100%" height={200}>
            <ComposedChart data={chartData}>
              <XAxis
                dataKey="time"
                tick={{ fill: 'var(--muted)', fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                minTickGap={40}
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
                formatter={(value, name) => [
                  value,
                  name === 'body_battery' ? 'Body Battery' : 'Stress',
                ]}
              />
              <Line
                dataKey="body_battery"
                stroke="var(--accent)"
                strokeWidth={2}
                dot={useDots ? { r: 2.5, fill: 'var(--accent)' } : false}
                name="body_battery"
                connectNulls
              />
              <Line
                dataKey="stress"
                stroke="var(--red, #ef4444)"
                strokeWidth={1}
                strokeOpacity={0.6}
                dot={useDots ? { r: 2.5, fill: 'var(--red, #ef4444)' } : false}
                name="stress"
                connectNulls
              />
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}
