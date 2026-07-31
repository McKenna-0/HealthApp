import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle } from 'lucide-react'
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
    <div
      className="card"
      style={{ borderLeft: '3px solid var(--amber)', marginBottom: 12 }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
        <AlertTriangle size={18} color="var(--amber)" style={{ flexShrink: 0, marginTop: 2 }} />
        <div style={{ flex: 1 }}>
          <div className="text-body" style={{ fontWeight: 600, color: 'var(--amber)' }}>
            Garmin data may be outdated
          </div>
          <div className="text-caption" style={{ marginTop: 2 }}>
            Last sync: {ageLabel(data.last_success_at)}
            {data.last_status === 'error' && data.last_error
              ? ` · ${data.last_error.slice(0, 120)}`
              : ''}
          </div>
          {syncNow.isError && (
            <div className="text-caption" style={{ color: 'var(--red)', marginTop: 4 }}>
              {String(syncNow.error).replace(/^\d+: /, '').slice(0, 120)}
            </div>
          )}
        </div>
        <button
          onClick={() => syncNow.mutate()}
          disabled={syncNow.isPending}
          style={{
            background: 'var(--amber)',
            color: '#1a1000',
            border: 'none',
            borderRadius: 8,
            padding: '8px 14px',
            fontWeight: 600,
            fontSize: '0.8rem',
            minHeight: 44,
            minWidth: 80,
            flexShrink: 0,
            opacity: syncNow.isPending ? 0.7 : 1,
          }}
        >
          {syncNow.isPending ? 'Syncing…' : 'Sync now'}
        </button>
      </div>
    </div>
  )
}
