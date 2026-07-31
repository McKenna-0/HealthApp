import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../api/client'
import type { CorrelationInsight, CorrelationsResponse } from '../api/types'
import SkeletonLoader from '../components/SkeletonLoader'

function strengthClass(strength: string | null | undefined): string {
  if (!strength || strength === 'none') return ''
  return strength // 'strong' | 'moderate' | 'weak' | 'tentative'
}

export function InsightCard({ insight }: { insight: CorrelationInsight }) {
  if (insight.status === 'insufficient_data') {
    return (
      <div className="insight-card" style={{ opacity: 0.7 }}>
        <div className="row" style={{ justifyContent: 'space-between', marginBottom: 4 }}>
          <span className="text-body" style={{ fontWeight: 600 }}>{insight.title}</span>
          <span className="badge" style={{ background: 'var(--card-elevated)', color: 'var(--muted)' }}>
            collecting
          </span>
        </div>
        <p className="text-caption" style={{ margin: 0 }}>
          {insight.summary_line}
        </p>
      </div>
    )
  }
  const cls = strengthClass(insight.strength)
  return (
    <div className={`insight-card ${cls}`}>
      <div className="row" style={{ justifyContent: 'space-between', marginBottom: 4 }}>
        <span className="text-body" style={{ fontWeight: 600 }}>{insight.title}</span>
        {insight.strength && insight.strength !== 'none' && (
          <span className="badge" style={{ background: 'var(--card-elevated)', color: 'var(--muted)' }}>
            {insight.strength}
          </span>
        )}
      </div>
      <p className="text-caption" style={{ margin: 0 }}>{insight.summary_line}</p>
    </div>
  )
}

export default function InsightsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['correlations'],
    queryFn: () => apiGet<CorrelationsResponse>('/api/analytics/correlations?days=90'),
  })

  if (isLoading) {
    return (
      <>
        <h1>Insights</h1>
        {[1, 2, 3].map((i) => (
          <div key={i} style={{ marginBottom: 12 }}>
            <SkeletonLoader height="80px" borderRadius="14px" />
          </div>
        ))}
      </>
    )
  }

  const established = (data?.insights ?? []).filter((i) => i.status === 'ok')
  const collecting = (data?.insights ?? []).filter((i) => i.status !== 'ok')

  return (
    <>
      <h1>Insights</h1>
      <p className="text-caption" style={{ margin: '0 4px 16px' }}>
        {data?.note} Based on your last {data?.days} days.
      </p>

      {established.length > 0 && (
        <>
          <p className="settings-section-header" style={{ marginTop: 0 }}>What your data shows</p>
          {established.map((i) => (
            <InsightCard key={i.id} insight={i} />
          ))}
        </>
      )}

      {collecting.length > 0 && (
        <>
          <p className="settings-section-header">Still collecting data</p>
          <p className="text-caption" style={{ margin: '0 4px 8px' }}>
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
