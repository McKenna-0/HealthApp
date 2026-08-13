import { useMemo, useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronDown } from 'lucide-react'
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { apiGet } from '../../api/client'
import type { RateStatus, WeightProgress } from '../../api/types'
import {
  STATUS_META,
  STATUS_ORDER,
  formatRate,
  statusColor,
  statusExplanation,
} from '../../utils/weightStatus'
import WeightGoalEditor from '../WeightGoalEditor'
import SkeletonLoader from '../SkeletonLoader'

const RANGES = [30, 90, 180]
const HORIZON = 21

/** 'YYYY-MM-DD' -> '4 Jul', without pulling a formatter into the tick callback. */
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
function shortDate(iso: string) {
  const [, m, d] = iso.split('-')
  return `${Number(d)} ${MONTHS[Number(m) - 1]}`
}

type Row = {
  iso: string
  weight: number | null
  trend: number | null
  ci: [number, number] | null
  goal: number | null
  projected: number | null
  fband: [number, number] | null
  rate: number | null
  status: RateStatus | null
} & Partial<Record<`gap_${RateStatus}`, [number, number] | null>>

export default function WeightProgressPanel() {
  const [days, setDays] = useState(90)

  const { data, isLoading } = useQuery<WeightProgress>({
    queryKey: ['weight-progress', days, HORIZON],
    queryFn: () => apiGet(`/api/analytics/weight-progress?days=${days}&horizon=${HORIZON}`),
  })

  const rows = useMemo<Row[]>(() => {
    if (!data) return []
    const series = data.series
    const out: Row[] = series.map((p, i) => {
      const prev = i > 0 ? series[i - 1].status : null
      const row: Row = {
        iso: p.date,
        weight: p.weight,
        trend: p.trend,
        ci: p.trend_lo != null && p.trend_hi != null ? [p.trend_lo, p.trend_hi] : null,
        goal: p.goal,
        projected: null,
        fband: null,
        rate: p.rate_kg_per_week,
        status: p.status,
      }
      // One shaded band per verdict, masked to the days that earned it. A day
      // also carries the previous day's verdict so consecutive segments touch
      // instead of leaving a one-day hole between colours.
      for (const s of STATUS_ORDER) {
        const belongs = p.status === s || prev === s
        row[`gap_${s}`] =
          belongs && p.trend != null && p.goal != null ? [p.goal, p.trend] : null
      }
      return row
    })

    // Hand the dashed projection off from the last real trend point so the two
    // lines meet rather than floating apart.
    const last = out[out.length - 1]
    if (last?.trend != null) {
      last.projected = last.trend
      last.fband = [last.trend, last.trend]
    }
    for (const f of data.forecast) {
      out.push({
        iso: f.date,
        weight: null,
        trend: null,
        ci: null,
        goal: f.goal ?? null,
        projected: f.projected,
        fband: [f.lo, f.hi],
        rate: null,
        status: null,
      })
    }
    return out
  }, [data])

  const current = data?.current ?? null
  const goal = data?.goal ?? null
  const statusesShown = useMemo(
    () => STATUS_ORDER.filter((s) => data?.series.some((p) => p.status === s)),
    [data],
  )

  if (isLoading) return <SkeletonLoader height="420px" borderRadius="14px" />

  return (
    <div>
      {/* Headline: the trend weight and the rate it is moving at */}
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
          <div>
            <div className="text-caption">Trend weight</div>
            <div className="text-display">
              {current ? `${current.trend_kg.toFixed(1)} kg` : '–'}
            </div>
          </div>
          {current && (
            <div style={{ marginLeft: 'auto', textAlign: 'right' }}>
              <div className="text-caption">Rate of change</div>
              <div
                className="text-title"
                style={{ color: statusColor(current.status) }}
              >
                {formatRate(current.rate_kg_per_week)}
              </div>
              <div className="text-caption">
                95% CI {current.rate_lo_kg_per_week.toFixed(2)} to{' '}
                {current.rate_hi_kg_per_week.toFixed(2)}
              </div>
            </div>
          )}
        </div>

        {current?.status && (
          <div
            style={{
              display: 'flex',
              gap: 8,
              alignItems: 'flex-start',
              marginTop: 12,
              padding: 10,
              borderRadius: 10,
              background: 'var(--card-elevated)',
              borderLeft: `3px solid ${statusColor(current.status)}`,
            }}
          >
            <div>
              <div className="text-body" style={{ fontWeight: 600 }}>
                {STATUS_META[current.status].label}
              </div>
              <div className="text-caption">
                {statusExplanation(
                  current.status,
                  current.rate_kg_per_week,
                  goal?.rate_kg_per_week ?? null,
                  current.bands.max_gain_kg_per_week,
                  current.bands.max_loss_kg_per_week,
                  current.bands.maintain_tolerance_kg_per_week,
                )}
              </div>
            </div>
          </div>
        )}

        {current && (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: '10px 12px',
              marginTop: 12,
            }}
          >
            <Stat label="Last weigh-in" value={current.latest_scale_kg != null ? `${current.latest_scale_kg.toFixed(1)} kg` : '–'} />
            <Stat label="Weigh-ins in range" value={`${current.weigh_ins} of ${days}`} />
            {goal?.remaining_kg != null && (
              <Stat
                label="To target"
                value={`${goal.remaining_kg > 0 ? '+' : ''}${goal.remaining_kg.toFixed(1)} kg`}
              />
            )}
            {goal?.eta_actual && (
              <Stat label="At this rate, target on" value={shortDate(goal.eta_actual)} />
            )}
            {goal?.on_plan_delta_kg != null && (
              <Stat
                label="Vs plan"
                value={`${goal.on_plan_delta_kg > 0 ? '+' : ''}${goal.on_plan_delta_kg.toFixed(1)} kg`}
              />
            )}
            <Stat
              label="Implied balance"
              value={`${current.rate_kcal_per_day > 0 ? '+' : ''}${current.rate_kcal_per_day} kcal/d`}
            />
          </div>
        )}
      </div>

      {/* Chart */}
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10, gap: 8 }}>
          <span className="text-title">Progress</span>
          <div className="tabs">
            {RANGES.map((d) => (
              <button
                key={d}
                className={`chip ${days === d ? 'active' : ''}`}
                onClick={() => setDays(d)}
                style={{ minHeight: 44 }}
              >
                {d}d
              </button>
            ))}
          </div>
        </div>

        {data?.reason ? (
          <p className="text-caption">Not enough data yet — {data.reason}.</p>
        ) : (
          <>
            {/* pan-y so a vertical swipe over the chart still scrolls the page */}
            <div style={{ touchAction: 'pan-y', marginLeft: -8 }}>
              <ResponsiveContainer width="100%" height={260}>
                <ComposedChart data={rows} margin={{ top: 8, right: 6, bottom: 0, left: 0 }}>
                  <CartesianGrid stroke="var(--border)" strokeOpacity={0.5} vertical={false} />
                  <XAxis
                    dataKey="iso"
                    tickFormatter={shortDate}
                    tick={{ fill: 'var(--muted)', fontSize: 10 }}
                    tickLine={false}
                    axisLine={false}
                    minTickGap={44}
                  />
                  <YAxis
                    domain={['dataMin - 0.4', 'dataMax + 0.4']}
                    tick={{ fill: 'var(--muted)', fontSize: 10 }}
                    tickLine={false}
                    axisLine={false}
                    width={38}
                    tickFormatter={(v: number) => v.toFixed(1)}
                  />

                  {/* uncertainty in the smoothed trend itself */}
                  <Area
                    dataKey="ci"
                    stroke="none"
                    fill="var(--accent)"
                    fillOpacity={0.12}
                    isAnimationActive={false}
                    activeDot={false}
                  />

                  {/* the gap between plan and reality, coloured by verdict */}
                  {STATUS_ORDER.map((s) => (
                    <Area
                      key={s}
                      dataKey={`gap_${s}`}
                      stroke="none"
                      fill={STATUS_META[s].color}
                      fillOpacity={0.3}
                      connectNulls={false}
                      isAnimationActive={false}
                      activeDot={false}
                    />
                  ))}

                  {/* projection ahead of today */}
                  <Area
                    dataKey="fband"
                    stroke="none"
                    fill="var(--accent)"
                    fillOpacity={0.08}
                    isAnimationActive={false}
                    activeDot={false}
                  />

                  {goal?.target_kg != null && (
                    <ReferenceLine
                      y={goal.target_kg}
                      stroke="var(--green)"
                      strokeDasharray="2 5"
                      strokeOpacity={0.8}
                    />
                  )}

                  {/* raw scale readings: dots only, deliberately recessive */}
                  <Line
                    dataKey="weight"
                    stroke="none"
                    dot={{ r: 1.6, fill: 'var(--muted)', strokeWidth: 0 }}
                    activeDot={{ r: 3.5, fill: 'var(--muted)' }}
                    isAnimationActive={false}
                  />
                  <Line
                    dataKey="goal"
                    stroke="var(--text)"
                    strokeOpacity={0.55}
                    strokeWidth={1.5}
                    strokeDasharray="5 4"
                    dot={false}
                    isAnimationActive={false}
                  />
                  <Line
                    dataKey="trend"
                    stroke="var(--accent)"
                    strokeWidth={2.5}
                    dot={false}
                    isAnimationActive={false}
                  />
                  <Line
                    dataKey="projected"
                    stroke="var(--accent)"
                    strokeWidth={2}
                    strokeDasharray="2 3"
                    dot={false}
                    isAnimationActive={false}
                  />
                  <Tooltip
                    content={<ProgressTooltip goalRate={goal?.rate_kg_per_week ?? null} />}
                    cursor={{ stroke: 'var(--muted)', strokeOpacity: 0.4 }}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>

            <Legend statuses={statusesShown} hasGoal={goal?.rate_kg_per_week != null} />
          </>
        )}
      </div>

      <WeightGoalEditor
        goal={goal}
        trendKg={current?.trend_kg ?? null}
        today={data?.end ?? new Date().toISOString().slice(0, 10)}
      />

      {/* Why the line is not just the scale readings joined up */}
      {data?.method && (
        <details className="card">
          <summary
            className="text-body"
            style={{
              cursor: 'pointer',
              minHeight: 44,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 8,
            }}
          >
            How this is calculated
            <ChevronDown size={16} color="var(--muted)" />
          </summary>
          <p className="text-caption" style={{ marginTop: 8 }}>{data.method}</p>
          {current && (
            <p className="text-caption">
              For you that puts single-day noise at about ±{current.observation_sd_kg.toFixed(2)} kg,
              so the trend line moves on the weight of several readings, not one. Green holds up to{' '}
              {current.bands.max_gain_kg_per_week.toFixed(2)} kg/wk gaining and{' '}
              {current.bands.max_loss_kg_per_week.toFixed(2)} kg/wk losing.
            </p>
          )}
          <p className="text-caption">
            Rates over a few weeks of one person's data are directional, not precise — read the
            confidence interval alongside the number.
          </p>
        </details>
      )}
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-caption">{label}</div>
      <div className="text-body" style={{ fontWeight: 600 }}>{value}</div>
    </div>
  )
}

function Swatch({ color, dashed, opacity = 1 }: { color: string; dashed?: boolean; opacity?: number }) {
  return (
    <span
      style={{
        width: 14,
        height: dashed ? 0 : 10,
        borderRadius: dashed ? 0 : 3,
        borderTop: dashed ? `2px dashed ${color}` : undefined,
        background: dashed ? undefined : color,
        opacity,
        flexShrink: 0,
        display: 'inline-block',
      }}
    />
  )
}

function Legend({ statuses, hasGoal }: { statuses: RateStatus[]; hasGoal: boolean }) {
  const items: { key: string; node: ReactNode; label: string }[] = [
    { key: 'trend', node: <Swatch color="var(--accent)" />, label: 'Smoothed trend' },
    { key: 'scale', node: <Swatch color="var(--muted)" />, label: 'Scale readings' },
  ]
  if (hasGoal) items.push({ key: 'goal', node: <Swatch color="var(--text)" dashed />, label: 'Goal plan' })
  items.push({ key: 'proj', node: <Swatch color="var(--accent)" dashed />, label: 'Projection' })
  for (const s of statuses) {
    items.push({
      key: s,
      node: <Swatch color={STATUS_META[s].color} opacity={0.45} />,
      label: STATUS_META[s].label,
    })
  }

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px 12px', marginTop: 10 }}>
      {items.map((it) => (
        <span key={it.key} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          {it.node}
          <span className="text-caption">{it.label}</span>
        </span>
      ))}
    </div>
  )
}

function ProgressTooltip({
  active,
  payload,
  goalRate,
}: {
  active?: boolean
  payload?: { payload: Row }[]
  goalRate?: number | null
}) {
  if (!active || !payload?.length) return null
  const row = payload[0].payload
  return (
    <div
      style={{
        background: 'var(--card-elevated)',
        border: '1px solid var(--border)',
        borderRadius: 8,
        padding: '8px 10px',
        maxWidth: 200,
      }}
    >
      <div className="text-caption" style={{ marginBottom: 4 }}>{shortDate(row.iso)}</div>
      {row.weight != null && <TipRow label="Scale" value={`${row.weight.toFixed(1)} kg`} />}
      {row.trend != null && (
        <TipRow
          label="Trend"
          value={`${row.trend.toFixed(2)} kg${row.ci ? ` ±${((row.ci[1] - row.ci[0]) / 2).toFixed(2)}` : ''}`}
        />
      )}
      {row.projected != null && row.trend == null && (
        <TipRow label="Projected" value={`${row.projected.toFixed(2)} kg`} />
      )}
      {row.goal != null && <TipRow label="Plan" value={`${row.goal.toFixed(2)} kg`} />}
      {row.rate != null && <TipRow label="Rate" value={formatRate(row.rate)} />}
      {row.status && (
        <div style={{ color: statusColor(row.status), fontSize: '0.75rem', marginTop: 2 }}>
          {STATUS_META[row.status].label}
          {goalRate != null && ` · plan ${formatRate(goalRate)}`}
        </div>
      )}
    </div>
  )
}

function TipRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, fontSize: '0.78rem' }}>
      <span style={{ color: 'var(--muted)' }}>{label}</span>
      <span style={{ color: 'var(--text)' }}>{value}</span>
    </div>
  )
}
