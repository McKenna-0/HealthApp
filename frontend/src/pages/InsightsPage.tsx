import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../api/client'
import type { CorrelationInsight, CorrelationsResponse } from '../api/types'

const STRENGTH_COLORS: Record<string, string> = {
  strong: '#f87171',
  moderate: '#fbbf24',
  weak: '#38bdf8',
  tentative: '#38bdf8',
  none: '#64748b',
}

export function InsightCard({ insight }: { insight: CorrelationInsight }) {
  if (insight.status === 'insufficient_data') {
    return (
      <div className="card" style={{ opacity: 0.7 }}>
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <strong style={{ fontSize: '0.9rem' }}>{insight.title}</strong>
          <span className="badge fixed" style={{ background: '#334155', color: '#94a3b8' }}>
            collecting
          </span>
        </div>
        <p className="muted" style={{ margin: '4px 0 0' }}>
          {insight.summary_line}
        </p>
      </div>
    )
  }
  const color = STRENGTH_COLORS[insight.strength ?? 'none']
  return (
    <div className="card">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <strong style={{ fontSize: '0.9rem' }}>{insight.title}</strong>
        {insight.strength && insight.strength !== 'none' && (
          <span className="badge fixed" style={{ background: color, color: '#0f172a' }}>
            {insight.strength}
          </span>
        )}
      </div>
      <p style={{ margin: '4px 0 0', fontSize: '0.85rem' }}>{insight.summary_line}</p>
    </div>
  )
}

export default function InsightsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['correlations'],
    queryFn: () => apiGet<CorrelationsResponse>('/api/analytics/correlations?days=90'),
  })

  if (isLoading) return <p className="muted">Loading…</p>

  const established = (data?.insights ?? []).filter((i) => i.status === 'ok')
  const collecting = (data?.insights ?? []).filter((i) => i.status !== 'ok')

  return (
    <>
      <h1>Insights</h1>
      <p className="muted" style={{ margin: '0 4px 12px' }}>
        {data?.note} Based on your last {data?.days} days.
      </p>

      {established.length > 0 && (
        <>
          <h2>What your data shows</h2>
          {established.map((i) => (
            <InsightCard key={i.id} insight={i} />
          ))}
        </>
      )}

      {collecting.length > 0 && (
        <>
          <h2>Still collecting data</h2>
          <p className="muted" style={{ margin: '0 4px 8px' }}>
            Keep logging context (alcohol, caffeine, illness) — these unlock as data accumulates.
          </p>
          {collecting.map((i) => (
            <InsightCard key={i.id} insight={i} />
          ))}
        </>
      )}
    </>
  )
}
