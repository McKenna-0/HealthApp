import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { apiGet, apiPost, apiPut } from '../api/client'
import type { HealthStatus, SyncLogRow } from '../api/types'

interface Targets {
  calorie_target: number | null
  protein_target_g: number | null
  carbs_target_g: number | null
  fat_target_g: number | null
}

function TargetsCard() {
  const qc = useQueryClient()
  const { data } = useQuery({
    queryKey: ['settings'],
    queryFn: () => apiGet<Targets>('/api/settings'),
  })
  const [form, setForm] = useState({ calorie_target: '', protein_target_g: '', carbs_target_g: '', fat_target_g: '' })

  useEffect(() => {
    if (data) {
      setForm({
        calorie_target: data.calorie_target?.toString() ?? '',
        protein_target_g: data.protein_target_g?.toString() ?? '',
        carbs_target_g: data.carbs_target_g?.toString() ?? '',
        fat_target_g: data.fat_target_g?.toString() ?? '',
      })
    }
  }, [data])

  const save = useMutation({
    mutationFn: () =>
      apiPut('/api/settings', {
        calorie_target: form.calorie_target ? parseFloat(form.calorie_target) : null,
        protein_target_g: form.protein_target_g ? parseFloat(form.protein_target_g) : null,
        carbs_target_g: form.carbs_target_g ? parseFloat(form.carbs_target_g) : null,
        fat_target_g: form.fat_target_g ? parseFloat(form.fat_target_g) : null,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['settings'] }),
  })

  const field = (key: keyof typeof form, label: string) => (
    <div style={{ flex: 1 }}>
      <div className="muted" style={{ fontSize: '0.72rem', marginBottom: 2 }}>
        {label}
      </div>
      <input
        type="number"
        inputMode="decimal"
        value={form[key]}
        onChange={(e) => setForm({ ...form, [key]: e.target.value })}
        style={{ width: '100%' }}
      />
    </div>
  )

  return (
    <div className="card">
      <strong>Daily targets</strong>
      <div className="row" style={{ marginTop: 8, marginBottom: 8 }}>
        {field('calorie_target', 'Calories')}
        {field('protein_target_g', 'Protein g')}
        {field('carbs_target_g', 'Carbs g')}
        {field('fat_target_g', 'Fat g')}
      </div>
      <button onClick={() => save.mutate()} disabled={save.isPending}>
        {save.isPending ? 'Saving…' : 'Save targets'}
      </button>
    </div>
  )
}

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

      <TargetsCard />

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
