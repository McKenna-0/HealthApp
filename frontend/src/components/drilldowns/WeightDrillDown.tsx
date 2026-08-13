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
import type { EnergyBalanceDay, TdeeResult } from '../../api/types'
import RangePicker from '../RangePicker'
import WeightProgressPanel from './WeightProgressPanel'
import { getBalanceColor } from '../../utils/balanceColor'

interface Settings {
  daily_balance_target: number | null
}

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

  const { data: energy } = useQuery<EnergyBalanceDay[]>({
    queryKey: ['energy-balance', days],
    queryFn: () => apiGet(`/api/analytics/energy-balance?start=${start}`),
  })

  const { data: tdee } = useQuery<TdeeResult>({
    queryKey: ['tdee'],
    queryFn: () => apiGet('/api/analytics/tdee'),
  })

  const { data: settings } = useQuery<Settings>({
    queryKey: ['settings'],
    queryFn: () => apiGet('/api/settings'),
  })

  return (
    <div>
      {/* Trend, goal and rate of change */}
      <WeightProgressPanel />

      {/* What is driving it */}
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <span className="text-title">Energy</span>
          <RangePicker value={days} onChange={setDays} />
        </div>

        {tdee?.tdee != null && (
          <div style={{ marginBottom: 12 }}>
            <div className="text-caption">
              Back-estimated TDEE over {tdee.window_days} days
            </div>
            <div className="text-body" style={{ fontWeight: 600 }}>
              {Math.round(tdee.tdee)} kcal/day
            </div>
          </div>
        )}

        {(energy ?? []).length > 0 && (
          <>
            <div className="text-caption" style={{ margin: '4px 0 8px' }}>Daily balance</div>
            <div style={{ touchAction: 'pan-y' }}>
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
                        fill={!d.valid ? 'var(--border)' : getBalanceColor(d.balance ?? 0, settings?.daily_balance_target ?? null)}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="text-caption" style={{ margin: '12px 0 8px' }}>Calories in vs out</div>
            <div style={{ touchAction: 'pan-y' }}>
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
            </div>
          </>
        )}
      </div>
    </div>
  )
}
