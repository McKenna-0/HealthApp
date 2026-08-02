import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  Legend,
} from 'recharts'
import { apiGet } from '../../api/client'
import type { WeightTrendPoint, EnergyBalanceDay, TdeeResult } from '../../api/types'
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

export default function WeightDrillDown() {
  const [days, setDays] = useState(90)
  const start = isoDaysAgo(days - 1)

  const { data: trend, isLoading: trendLoading } = useQuery<WeightTrendPoint[]>({
    queryKey: ['weight-trend', days],
    queryFn: () => apiGet(`/api/analytics/weight-trend?start=${start}`),
  })

  const { data: energy } = useQuery<EnergyBalanceDay[]>({
    queryKey: ['energy-balance', days],
    queryFn: () => apiGet(`/api/analytics/energy-balance?start=${start}`),
  })

  const { data: tdee } = useQuery<TdeeResult>({
    queryKey: ['tdee'],
    queryFn: () => apiGet('/api/analytics/tdee'),
  })

  const trendData = (trend ?? []).map(p => ({
    date: p.date.slice(5),
    weight: p.weight,
    trend: p.trend != null ? +p.trend.toFixed(1) : null,
  }))

  const latest = [...trendData].reverse().find(p => p.trend != null)
  const latestWeight = [...trendData].reverse().find(p => p.weight != null)

  // Compute weekly slope from first and last valid trend points
  const trendPoints = (trend ?? []).filter(p => p.trend != null)
  let slopePerWeek: number | null = null
  if (trendPoints.length >= 8) {
    const first = trendPoints[trendPoints.length - 8]
    const last = trendPoints[trendPoints.length - 1]
    const daysDiff =
      (new Date(last.date).getTime() - new Date(first.date).getTime()) / (1000 * 60 * 60 * 24)
    if (daysDiff > 0) {
      slopePerWeek = +((((last.trend ?? 0) - (first.trend ?? 0)) / daysDiff) * 7).toFixed(2)
    }
  }

  return (
    <div>
      {/* Summary */}
      <div style={{ display: 'flex', gap: 20, marginBottom: 16, flexWrap: 'wrap' }}>
        <div>
          <div className="text-caption">Weight</div>
          <div className="text-body" style={{ fontWeight: 600 }}>
            {latestWeight?.weight != null ? `${latestWeight.weight} kg` : '–'}
          </div>
        </div>
        <div>
          <div className="text-caption">Trend</div>
          <div className="text-body" style={{ fontWeight: 600 }}>
            {latest?.trend != null ? `${latest.trend} kg` : '–'}
          </div>
        </div>
        {tdee?.tdee != null && (
          <div>
            <div className="text-caption">TDEE</div>
            <div className="text-body" style={{ fontWeight: 600 }}>{Math.round(tdee.tdee)} kcal</div>
          </div>
        )}
        {slopePerWeek != null && (
          <div>
            <div className="text-caption">Trend/wk</div>
            <div
              className="text-body"
              style={{
                fontWeight: 600,
                color:
                  slopePerWeek < 0
                    ? 'var(--green)'
                    : slopePerWeek > 0
                      ? 'var(--red)'
                      : 'var(--muted)',
              }}
            >
              {slopePerWeek > 0 ? '+' : ''}{slopePerWeek} kg
            </div>
          </div>
        )}
      </div>

      <RangePicker value={days} onChange={setDays} />

      {trendLoading ? (
        <SkeletonLoader height="400px" borderRadius="14px" />
      ) : (
        <>
          {/* Weight trend chart */}
          <div className="text-title" style={{ margin: '16px 0 8px' }}>Weight Trend</div>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={trendData}>
              <XAxis
                dataKey="date"
                tick={{ fill: 'var(--muted)', fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                minTickGap={30}
              />
              <YAxis
                domain={['dataMin - 1', 'dataMax + 1']}
                tick={{ fill: 'var(--muted)', fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                width={40}
              />
              <Tooltip {...tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: 11, color: 'var(--muted)' }} />
              <Line
                dataKey="weight"
                stroke="var(--muted)"
                strokeWidth={1}
                dot={{ r: 2, fill: 'var(--muted)' }}
                name="Daily"
                connectNulls={false}
              />
              <Line
                dataKey="trend"
                stroke="var(--accent)"
                strokeWidth={2}
                dot={{ r: 2.5, fill: 'var(--accent)' }}
                name="Trend (EWMA)"
              />
            </LineChart>
          </ResponsiveContainer>

          {/* Energy balance */}
          {(energy ?? []).length > 0 && (
            <>
              <div className="text-title" style={{ margin: '16px 0 8px' }}>Energy Balance</div>
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={energy}>
                  <XAxis
                    dataKey="date"
                    tickFormatter={(d: string) => d.slice(5)}
                    tick={{ fill: 'var(--muted)', fontSize: 11 }}
                    tickLine={false}
                    axisLine={false}
                    minTickGap={30}
                  />
                  <YAxis
                    tick={{ fill: 'var(--muted)', fontSize: 11 }}
                    tickLine={false}
                    axisLine={false}
                    width={40}
                  />
                  <ReferenceLine y={0} stroke="var(--border)" />
                  <Tooltip {...tooltipStyle} />
                  <Bar dataKey="balance" name="Balance (kcal)">
                    {(energy ?? []).map(d => (
                      <Cell
                        key={d.date}
                        fill={!d.valid ? 'var(--border)' : (d.balance ?? 0) > 0 ? 'var(--red)' : 'var(--green)'}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>

              {/* Calories in vs out */}
              <div className="text-title" style={{ margin: '16px 0 8px' }}>Calories In vs Out</div>
              <ResponsiveContainer width="100%" height={160}>
                <LineChart data={energy}>
                  <XAxis
                    dataKey="date"
                    tickFormatter={(d: string) => d.slice(5)}
                    tick={{ fill: 'var(--muted)', fontSize: 11 }}
                    tickLine={false}
                    axisLine={false}
                    minTickGap={30}
                  />
                  <YAxis
                    tick={{ fill: 'var(--muted)', fontSize: 11 }}
                    tickLine={false}
                    axisLine={false}
                    width={40}
                  />
                  <Tooltip {...tooltipStyle} />
                  <Legend wrapperStyle={{ fontSize: 11, color: 'var(--muted)' }} />
                  <Line
                    dataKey="calories_in"
                    stroke="#38bdf8"
                    strokeWidth={2}
                    dot={{ r: 2.5, fill: '#38bdf8' }}
                    name="In"
                    connectNulls={false}
                  />
                  <Line
                    dataKey="calories_out"
                    stroke="#f87171"
                    strokeWidth={2}
                    dot={{ r: 2.5, fill: '#f87171' }}
                    name="Out"
                    connectNulls={false}
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
