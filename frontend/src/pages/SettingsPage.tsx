import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost } from '../api/client'
import type { HealthStatus, SyncLogRow } from '../api/types'

export default function SettingsPage() {
  const qc = useQueryClient()

  const health = useQuery({
    queryKey: ['health'],
    queryFn: () => apiGet<HealthStatus>('/api/health'),
  })

  const log = useQuery({
    queryKey: ['sync-log'],
    queryFn: () => apiGet<SyncLogRow[]>('/api/sync/log'),
  })

  const sync = useMutation({
    mutationFn: () => apiPost<SyncLogRow>('/api/sync?days=7'),
    onSuccess: () => qc.invalidateQueries(),
  })

  return (
    <>
      <h1>Settings</h1>

      <div className="card">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <div>Data source</div>
            <div className="muted">timezone: {health.data?.tz ?? '…'}</div>
          </div>
          <span className={`badge fixed ${health.data?.data_source ?? ''}`}>
            {health.data?.data_source === 'mock' ? 'Mock data' : health.data?.data_source ?? '…'}
          </span>
        </div>
        {health.data?.data_source === 'mock' && (
          <p className="muted" style={{ marginBottom: 0 }}>
            Generated sample data. To use real Garmin data, set DATA_SOURCE=garmin and your
            credentials in .env, then restart the backend.
          </p>
        )}
      </div>

      <div className="card">
        <button onClick={() => sync.mutate()} disabled={sync.isPending} style={{ width: '100%' }}>
          {sync.isPending ? 'Syncing…' : 'Sync now (last 7 days)'}
        </button>
        {sync.data && (
          <p className="muted">
            Last run: {sync.data.status}
            {sync.data.error ? ` — ${sync.data.error}` : ''}
          </p>
        )}
      </div>

      <div className="card">
        <strong>Sync history</strong>
        <table style={{ marginTop: 8 }}>
          <thead>
            <tr>
              <th>Started</th>
              <th>Source</th>
              <th>Days</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {(log.data ?? []).map((r) => (
              <tr key={r.id}>
                <td>{r.started_at.slice(0, 16).replace('T', ' ')}</td>
                <td>{r.source}</td>
                <td>{r.days_requested}</td>
                <td>
                  <span className={`badge ${r.status}`}>{r.status}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
