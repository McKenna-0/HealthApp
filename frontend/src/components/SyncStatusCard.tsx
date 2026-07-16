import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost } from '../api/client'
import type { SyncLogRow, SyncStatus } from '../api/types'

function ageLabel(iso: string | null): string {
  if (!iso) return 'never'
  const ms = Date.now() - new Date(iso).getTime()
  const hours = Math.floor(ms / 3_600_000)
  if (hours < 1) return 'under an hour ago'
  if (hours < 48) return `${hours}h ago`
  return `${Math.floor(hours / 24)} days ago`
}

export default function SyncStatusCard() {
  const qc = useQueryClient()
  const { data } = useQuery({
    queryKey: ['sync-status'],
    queryFn: () => apiGet<SyncStatus>('/api/sync/status'),
    refetchInterval: 5 * 60_000,
  })

  const syncNow = useMutation({
    mutationFn: () => apiPost<SyncLogRow>('/api/sync?days=7'),
    onSuccess: () => qc.invalidateQueries(),
  })

  if (!data || !data.stale) return null

  return (
    <div className="card" style={{ borderColor: 'var(--amber)' }}>
      <div className="row" style={{ justifyContent: 'space-between', gap: 8 }}>
        <div style={{ flex: 1 }}>
          <strong style={{ color: 'var(--amber)' }}>Garmin data may be outdated</strong>
          <div className="muted" style={{ fontSize: '0.8rem' }}>
            Last successful sync: {ageLabel(data.last_success_at)}
            {data.last_status === 'error' && data.last_error
              ? ` · ${data.last_error.slice(0, 120)}`
              : ''}
          </div>
        </div>
        <button className="fixed" onClick={() => syncNow.mutate()} disabled={syncNow.isPending}>
          {syncNow.isPending ? 'Syncing…' : 'Sync now'}
        </button>
      </div>
      {syncNow.isError && (
        <p className="error-text">{String(syncNow.error).replace(/^\d+: /, '').slice(0, 120)}</p>
      )}
    </div>
  )
}
