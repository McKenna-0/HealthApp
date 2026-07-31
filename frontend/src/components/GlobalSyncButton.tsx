import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { RefreshCw } from 'lucide-react'
import { apiGet, apiPost } from '../api/client'
import type { SyncStatus } from '../api/types'

export default function GlobalSyncButton({ hide = false }: { hide?: boolean }) {
  const qc = useQueryClient()
  const { data: st } = useQuery<SyncStatus>({
    queryKey: ['sync-status'],
    queryFn: () => apiGet('/api/sync/status'),
    refetchInterval: 300_000,
  })
  const sync = useMutation({
    mutationFn: () => apiPost('/api/sync'),
    onSuccess: () => {
      qc.invalidateQueries()
    },
  })

  if (hide) return null

  const stale = st && st.last_success_at &&
    (Date.now() - new Date(st.last_success_at).getTime()) > 6 * 3600_000
  const error = st?.last_error

  const color = sync.isPending ? 'var(--accent)' :
    error ? 'var(--red)' :
    stale ? 'var(--amber)' : 'var(--muted)'

  return (
    <button
      className="header-btn"
      onClick={() => sync.mutate()}
      disabled={sync.isPending}
      aria-label="Sync data"
    >
      <RefreshCw
        size={20}
        color={color}
        style={sync.isPending ? { animation: 'spin 1s linear infinite' } : undefined}
      />
    </button>
  )
}
