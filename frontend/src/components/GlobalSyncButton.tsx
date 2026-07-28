import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost } from '../api/client'
import type { SyncLogRow, SyncStatus } from '../api/types'

export default function GlobalSyncButton() {
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

  if (!data) return null

  const cls = syncNow.isPending
    ? 'sync-btn syncing'
    : data.stale
      ? data.last_status === 'error'
        ? 'sync-btn error'
        : 'sync-btn stale'
      : 'sync-btn fresh'

  return (
    <button
      className={cls}
      onClick={() => syncNow.mutate()}
      disabled={syncNow.isPending}
      title={data.stale ? 'Sync stale — tap to sync' : 'Synced'}
    >
      ↻
    </button>
  )
}
