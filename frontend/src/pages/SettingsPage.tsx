import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { useEffect, useState } from 'react'
import { apiDelete, apiGet, apiPost, apiPut } from '../api/client'
import type { AIModelOption, AIProvider, HealthStatus, MfpStatus, SyncLogRow } from '../api/types'
import {
  getNotificationConfig,
  saveNotificationConfig,
  requestNotificationPermission,
  NOTIFICATION_LABELS,
  type NotificationType,
} from '../notifications'

interface Targets {
  calorie_target: number | null
  protein_target_g: number | null
  carbs_target_g: number | null
  fat_target_g: number | null
  weight_goal_kg: number | null
  macro_mode: string | null
  protein_target_pct: number | null
  carbs_target_pct: number | null
  fat_target_pct: number | null
  daily_balance_target: number | null
}

function TargetsCard() {
  const qc = useQueryClient()
  const { data } = useQuery({
    queryKey: ['settings'],
    queryFn: () => apiGet<Targets>('/api/settings'),
  })
  const [mode, setMode] = useState<'grams' | 'percent'>('grams')
  const [form, setForm] = useState({
    calorie_target: '',
    protein_target_g: '',
    carbs_target_g: '',
    fat_target_g: '',
    weight_goal_kg: '',
    protein_target_pct: '',
    carbs_target_pct: '',
    fat_target_pct: '',
    daily_balance_target: '',
  })

  useEffect(() => {
    if (data) {
      setMode((data.macro_mode as 'grams' | 'percent') || 'grams')
      setForm({
        calorie_target: data.calorie_target?.toString() ?? '',
        protein_target_g: data.protein_target_g?.toString() ?? '',
        carbs_target_g: data.carbs_target_g?.toString() ?? '',
        fat_target_g: data.fat_target_g?.toString() ?? '',
        weight_goal_kg: data.weight_goal_kg?.toString() ?? '',
        protein_target_pct: data.protein_target_pct?.toString() ?? '',
        carbs_target_pct: data.carbs_target_pct?.toString() ?? '',
        fat_target_pct: data.fat_target_pct?.toString() ?? '',
        daily_balance_target: data.daily_balance_target?.toString() ?? '',
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
        weight_goal_kg: form.weight_goal_kg ? parseFloat(form.weight_goal_kg) : null,
        macro_mode: mode,
        protein_target_pct: form.protein_target_pct ? parseFloat(form.protein_target_pct) : null,
        carbs_target_pct: form.carbs_target_pct ? parseFloat(form.carbs_target_pct) : null,
        fat_target_pct: form.fat_target_pct ? parseFloat(form.fat_target_pct) : null,
        daily_balance_target: form.daily_balance_target ? parseFloat(form.daily_balance_target) : null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['settings'] })
      qc.invalidateQueries({ queryKey: ['targets'] })
    },
  })

  const field = (key: keyof typeof form, label: string) => (
    <div style={{ flex: 1, minWidth: 0 }}>
      <div className="text-caption" style={{ marginBottom: 4 }}>{label}</div>
      <input
        type="number"
        inputMode="decimal"
        value={form[key]}
        onChange={(e) => setForm({ ...form, [key]: e.target.value })}
        style={{ width: '100%' }}
      />
    </div>
  )

  const pctTotal =
    (parseFloat(form.protein_target_pct) || 0) +
    (parseFloat(form.carbs_target_pct) || 0) +
    (parseFloat(form.fat_target_pct) || 0)

  const calTarget = parseFloat(form.calorie_target) || 0
  const computedGrams = mode === 'percent' && calTarget > 0 ? {
    protein: Math.round(calTarget * (parseFloat(form.protein_target_pct) || 0) / 100 / 4),
    carbs: Math.round(calTarget * (parseFloat(form.carbs_target_pct) || 0) / 100 / 4),
    fat: Math.round(calTarget * (parseFloat(form.fat_target_pct) || 0) / 100 / 9),
  } : null

  return (
    <div className="card">
      <p className="text-title" style={{ marginBottom: 12 }}>Daily targets</p>
      <div className="row" style={{ marginBottom: 4 }}>
        {field('calorie_target', 'Calories')}
        {field('weight_goal_kg', 'Weight goal (kg)')}
      </div>
      <div className="text-caption" style={{ marginBottom: 12, color: 'var(--muted)' }}>
        Active calories burned each day are added on top of this allowance
      </div>

      <div className="row" style={{ marginBottom: 4 }}>
        {field('daily_balance_target', 'Balance target (kcal)')}
      </div>
      <div className="text-caption" style={{ marginBottom: 12, color: 'var(--muted)' }}>
        e.g. +200 for surplus, -500 for deficit
      </div>

      <div className="text-caption" style={{ marginBottom: 6 }}>Macro targets</div>
      <div className="tabs" style={{ marginBottom: 10 }}>
        <button className={`chip ${mode === 'grams' ? 'active' : ''}`} onClick={() => setMode('grams')}>
          Grams
        </button>
        <button className={`chip ${mode === 'percent' ? 'active' : ''}`} onClick={() => setMode('percent')}>
          % of Calories
        </button>
      </div>

      {mode === 'grams' ? (
        <div className="row" style={{ marginBottom: 10 }}>
          {field('protein_target_g', 'Protein (g)')}
          {field('carbs_target_g', 'Carbs (g)')}
          {field('fat_target_g', 'Fat (g)')}
        </div>
      ) : (
        <>
          <div className="row" style={{ marginBottom: 6 }}>
            {field('protein_target_pct', 'Protein %')}
            {field('carbs_target_pct', 'Carbs %')}
            {field('fat_target_pct', 'Fat %')}
          </div>
          <div className="text-caption" style={{ marginBottom: 10 }}>
            Total: {Math.round(pctTotal)}%{' '}
            {pctTotal > 0 && Math.abs(pctTotal - 100) > 1 && (
              <span style={{ color: 'var(--red)' }}>(should be 100%)</span>
            )}
            {computedGrams && (
              <span>
                {' '}= {computedGrams.protein}g P / {computedGrams.carbs}g C / {computedGrams.fat}g F
                {' '}at {Math.round(calTarget)} kcal — grows with active calories
              </span>
            )}
          </div>
        </>
      )}

      <button onClick={() => save.mutate()} disabled={save.isPending} style={{ width: '100%' }}>
        {save.isPending ? 'Saving...' : 'Save targets'}
      </button>
    </div>
  )
}

function MfpCard() {
  const qc = useQueryClient()
  const { data: status } = useQuery({
    queryKey: ['mfp-status'],
    queryFn: () => apiGet<MfpStatus>('/api/mfp/status'),
  })
  const [cookie, setCookie] = useState('')
  const [showInstructions, setShowInstructions] = useState(false)

  const saveCookie = useMutation({
    mutationFn: () => apiPut<{ saved: boolean; valid: boolean }>('/api/mfp/cookie', { cookie }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['mfp-status'] })
      setCookie('')
    },
  })

  const syncNow = useMutation({
    mutationFn: () => apiPost<{ entries_synced: number; errors: string[] }>('/api/mfp/sync?days=3'),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['mfp-status'] })
      qc.invalidateQueries({ queryKey: ['food-log'] })
      qc.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })

  const disconnect = useMutation({
    mutationFn: () => apiDelete('/api/mfp/cookie'),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['mfp-status'] }),
  })

  const statusColor =
    status?.last_sync_status === 'ok'
      ? 'var(--green)'
      : status?.last_sync_status === 'cookie_expired'
        ? 'var(--amber)'
        : status?.cookie_set
          ? 'var(--muted)'
          : 'var(--border)'

  const statusLabel = !status?.cookie_set
    ? 'Not configured'
    : status.last_sync_status === 'ok'
      ? 'Connected'
      : status.last_sync_status === 'cookie_expired'
        ? 'Cookie expired'
        : status.last_sync_status === 'error'
          ? 'Sync error'
          : 'Pending first sync'

  return (
    <div className="card">
      <div className="row" style={{ justifyContent: 'space-between', marginBottom: 10 }}>
        <p className="text-title" style={{ margin: 0 }}>MyFitnessPal sync</p>
        <span className="row" style={{ gap: 6, alignItems: 'center' }}>
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: statusColor,
              display: 'inline-block',
              flexShrink: 0,
            }}
          />
          <span className="text-caption">{statusLabel}</span>
        </span>
      </div>

      {status?.last_sync_at && (
        <div className="text-caption" style={{ marginBottom: 10 }}>
          Last sync: {status.last_sync_at.slice(0, 16).replace('T', ' ')}
          {status.last_sync_error ? ` — ${status.last_sync_error}` : ''}
        </div>
      )}

      {!status?.cookie_set ? (
        <>
          <button
            className="secondary"
            onClick={() => setShowInstructions(!showInstructions)}
            style={{ width: '100%', marginBottom: 8 }}
          >
            {showInstructions ? 'Hide setup' : 'Set up MFP sync'}
          </button>
          {showInstructions && (
            <div className="text-caption" style={{ marginBottom: 10, lineHeight: 1.6 }}>
              1. Log into <b>myfitnesspal.com</b> in a browser<br />
              2. Open DevTools (F12) &gt; <b>Network</b> tab<br />
              3. Refresh the page, click any request to myfitnesspal.com<br />
              4. In Request Headers, find <b>Cookie</b> &gt; right-click &gt; Copy value<br />
              5. Paste below
            </div>
          )}
          <textarea
            placeholder="Paste MFP cookie string..."
            value={cookie}
            onChange={(e) => setCookie(e.target.value)}
            rows={3}
            style={{ width: '100%', fontSize: '16px', marginBottom: 8, fontFamily: 'monospace' }}
          />
          <button onClick={() => saveCookie.mutate()} disabled={saveCookie.isPending || cookie.length < 10} style={{ width: '100%' }}>
            {saveCookie.isPending ? 'Saving...' : 'Save & test'}
          </button>
          {saveCookie.data && (
            <p className="text-caption" style={{ marginTop: 6 }}>
              {saveCookie.data.valid ? 'Cookie is valid!' : 'Saved, but cookie appears expired — paste a fresh one.'}
            </p>
          )}
          {saveCookie.isError && (
            <p className="text-caption" style={{ marginTop: 6, color: 'var(--red)' }}>
              {String(saveCookie.error).replace(/^\d+: /, '').slice(0, 200)}
            </p>
          )}
        </>
      ) : (
        <div className="row" style={{ gap: 8 }}>
          <button onClick={() => syncNow.mutate()} disabled={syncNow.isPending} style={{ flex: 1 }}>
            {syncNow.isPending ? 'Syncing...' : 'Sync now'}
          </button>
          <button
            onClick={() => { if (confirm('Disconnect MFP?')) disconnect.mutate() }}
            disabled={disconnect.isPending}
            className="secondary fixed"
          >
            Disconnect
          </button>
        </div>
      )}

      {syncNow.data && (
        <p className="text-caption" style={{ marginTop: 6 }}>
          Synced {syncNow.data.entries_synced} entries
          {syncNow.data.errors.length > 0 ? ` (${syncNow.data.errors.length} errors)` : ''}
        </p>
      )}

      {status?.cookie_set && status.last_sync_status === 'cookie_expired' && (
        <>
          <div className="text-caption" style={{ marginTop: 10, marginBottom: 6 }}>
            Paste a fresh cookie to reconnect:
          </div>
          <textarea
            placeholder="Paste MFP cookie string..."
            value={cookie}
            onChange={(e) => setCookie(e.target.value)}
            rows={3}
            style={{ width: '100%', fontSize: '16px', marginBottom: 8, fontFamily: 'monospace' }}
          />
          <button onClick={() => saveCookie.mutate()} disabled={saveCookie.isPending || cookie.length < 10} style={{ width: '100%' }}>
            {saveCookie.isPending ? 'Saving...' : 'Update cookie'}
          </button>
          {saveCookie.isError && (
            <p className="text-caption" style={{ marginTop: 6, color: 'var(--red)' }}>
              {String(saveCookie.error).replace(/^\d+: /, '').slice(0, 200)}
            </p>
          )}
        </>
      )}
    </div>
  )
}

function perMillion(price: string | null): string | null {
  const n = Number(price)
  if (!price || Number.isNaN(n)) return null
  return `$${(n * 1e6).toFixed(2)}/M`
}

function AIProviderCard() {
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [baseUrl, setBaseUrl] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [filter, setFilter] = useState('')
  const [browsing, setBrowsing] = useState(false)

  const provider = useQuery({
    queryKey: ['ai-provider'],
    queryFn: () => apiGet<AIProvider>('/api/ai/provider'),
  })

  // Never hardcoded: the catalogue is provider- and host-specific, and models
  // without tool-calling support simply won't work as the agent.
  const models = useQuery({
    queryKey: ['ai-models'],
    queryFn: () => apiGet<{ models: AIModelOption[] }>('/api/ai/models'),
    enabled: browsing,
    staleTime: 60 * 60 * 1000,
  })

  const save = useMutation({
    mutationFn: (patch: Partial<Record<'base_url' | 'api_key' | 'model', string>>) =>
      apiPut<AIProvider>('/api/ai/provider', patch),
    onSuccess: () => {
      setApiKey('')
      qc.invalidateQueries({ queryKey: ['ai-provider'] })
      qc.invalidateQueries({ queryKey: ['ai-status'] })
      qc.invalidateQueries({ queryKey: ['ai-models'] })
    },
  })

  const reset = useMutation({
    mutationFn: () => apiDelete<AIProvider>('/api/ai/provider'),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['ai-provider'] })
      qc.invalidateQueries({ queryKey: ['ai-status'] })
    },
  })

  const p = provider.data
  const needle = filter.trim().toLowerCase()
  const matches = (models.data?.models ?? [])
    .filter((m) => !needle || m.id.toLowerCase().includes(needle) || m.name.toLowerCase().includes(needle))
    .slice(0, 25)

  return (
    <div className="card">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <div style={{ minWidth: 0 }}>
          <p className="text-body" style={{ margin: 0, fontWeight: 600 }}>AI assistant</p>
          <p className="text-caption" style={{ margin: '2px 0 0', wordBreak: 'break-all' }}>
            {p ? `${p.model || 'no model'} · ${p.base_url || 'no endpoint'}` : '…'}
          </p>
        </div>
        <span className={`badge fixed ${p?.configured ? 'garmin' : ''}`}>
          {p?.configured ? 'Ready' : 'Not set'}
        </span>
      </div>

      <p className="text-caption" style={{ margin: '8px 0 0' }}>
        {p?.privacy_routing
          ? 'Routing only to endpoints that do not retain or train on prompts.'
          : p?.is_openrouter
            ? 'Privacy routing is off — set AI_REQUIRE_ZDR=true to restrict which hosts see your data.'
            : 'Whoever hosts this endpoint can see every prompt, including your health data. Open weights alone do not make a request private.'}
      </p>

      <button
        className="secondary"
        onClick={() => setOpen(!open)}
        style={{ width: '100%', marginTop: 10, minHeight: 44 }}
      >
        {open ? 'Hide' : 'Change provider'}
      </button>

      {open && (
        <div style={{ marginTop: 10 }}>
          <label className="text-caption">Endpoint (OpenAI-compatible)</label>
          <input
            placeholder={p?.base_url || 'https://openrouter.ai/api/v1'}
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            autoCapitalize="off"
            autoCorrect="off"
            style={{ width: '100%', margin: '4px 0 10px' }}
          />

          <label className="text-caption">
            API key {p?.api_key_set ? '(one is already saved)' : ''}
          </label>
          <input
            type="password"
            placeholder="Paste a key to replace the saved one"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            autoComplete="off"
            style={{ width: '100%', margin: '4px 0 10px' }}
          />

          <button
            onClick={() =>
              save.mutate({
                ...(baseUrl.trim() ? { base_url: baseUrl.trim() } : {}),
                ...(apiKey.trim() ? { api_key: apiKey.trim() } : {}),
              })
            }
            disabled={save.isPending || (!baseUrl.trim() && !apiKey.trim())}
            style={{ width: '100%', minHeight: 44 }}
          >
            {save.isPending ? 'Saving…' : 'Save endpoint & key'}
          </button>

          <button
            className="secondary"
            onClick={() => setBrowsing(true)}
            style={{ width: '100%', marginTop: 8, minHeight: 44 }}
          >
            {browsing ? 'Models loaded below' : 'Choose model'}
          </button>

          {browsing && (
            <>
              {models.isLoading && <p className="text-caption" style={{ marginTop: 8 }}>Loading catalogue…</p>}
              {models.isError && (
                <p className="text-caption" style={{ marginTop: 8, color: 'var(--red)' }}>
                  {String(models.error).replace(/^\d+: /, '').slice(0, 200)}
                </p>
              )}
              {models.data && (
                <>
                  <input
                    placeholder="Filter models…"
                    value={filter}
                    onChange={(e) => setFilter(e.target.value)}
                    autoCapitalize="off"
                    style={{ width: '100%', margin: '8px 0' }}
                  />
                  <div style={{ maxHeight: 280, overflowY: 'auto' }}>
                    {matches.map((m) => (
                      <div
                        key={m.id}
                        className="list-item"
                        onClick={() => save.mutate({ model: m.id })}
                        style={{ cursor: 'pointer', minHeight: 44 }}
                      >
                        <div className="main">
                          <div className="name" style={{ wordBreak: 'break-all' }}>{m.id}</div>
                          <div className="detail">
                            {[
                              perMillion(m.prompt_price) && `${perMillion(m.prompt_price)} in`,
                              perMillion(m.completion_price) && `${perMillion(m.completion_price)} out`,
                            ]
                              .filter(Boolean)
                              .join(' · ') || 'price unknown'}
                            {m.context_length ? ` · ${Math.round(m.context_length / 1000)}k ctx` : ''}
                          </div>
                        </div>
                        {p?.model === m.id && <span className="badge fixed garmin">Active</span>}
                      </div>
                    ))}
                    {matches.length === 0 && <p className="text-caption">No matches.</p>}
                  </div>
                  <p className="text-caption" style={{ marginTop: 6 }}>
                    The agent needs a model that supports tool calling — most current chat models do,
                    but a base or completion-only model will fail on the first question.
                  </p>
                </>
              )}
            </>
          )}

          {save.isError && (
            <p className="text-caption" style={{ marginTop: 6, color: 'var(--red)' }}>
              {String(save.error).replace(/^\d+: /, '').slice(0, 200)}
            </p>
          )}

          <button
            className="secondary"
            onClick={() => { if (confirm('Reset AI provider to the .env defaults?')) reset.mutate() }}
            disabled={reset.isPending}
            style={{ width: '100%', marginTop: 8, minHeight: 44 }}
          >
            Reset to .env defaults
          </button>
        </div>
      )}
    </div>
  )
}

const METRIC_DEFS: Record<string, { label: string }> = {
  hrv: { label: 'HRV' },
  sleep_score: { label: 'Sleep Score' },
  calories_out: { label: 'Cal Burned' },
  steps: { label: 'Steps' },
  resting_hr: { label: 'Resting HR' },
  body_battery: { label: 'Body Battery' },
}

const DEFAULT_METRICS = ['hrv', 'sleep_score', 'calories_out', 'steps', 'resting_hr', 'body_battery']

function DashboardCard() {
  const [allMetrics, setAllMetrics] = useState<string[]>(() => {
    try {
      const saved = localStorage.getItem('dashboard-metrics-config')
      if (saved) return JSON.parse(saved)
    } catch {}
    return DEFAULT_METRICS
  })

  function toggleMetric(key: string) {
    setAllMetrics(prev => {
      const next = prev.includes(key)
        ? prev.filter(k => k !== key)
        : [...prev, key]
      localStorage.setItem('dashboard-metrics-config', JSON.stringify(next))
      return next
    })
  }

  function moveMetric(key: string, direction: -1 | 1) {
    setAllMetrics(prev => {
      const idx = prev.indexOf(key)
      if (idx < 0) return prev
      const next = [...prev]
      const target = idx + direction
      if (target < 0 || target >= next.length) return prev
      ;[next[idx], next[target]] = [next[target], next[idx]]
      localStorage.setItem('dashboard-metrics-config', JSON.stringify(next))
      return next
    })
  }

  // Show all known metrics; enabled ones are those in allMetrics
  const allKeys = DEFAULT_METRICS
  // Order: enabled first (in their saved order), then disabled ones appended
  const orderedKeys = [
    ...allMetrics.filter(k => allKeys.includes(k)),
    ...allKeys.filter(k => !allMetrics.includes(k)),
  ]

  return (
    <div className="card">
      <div className="text-title" style={{ marginBottom: 12 }}>Dashboard</div>
      <div className="text-caption" style={{ marginBottom: 12 }}>Choose which metrics appear on your home page</div>
      {orderedKeys.map((key, idx) => (
        <div key={key} style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '12px 0', borderBottom: '1px solid var(--border)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <button
                onClick={() => moveMetric(key, -1)}
                disabled={idx === 0}
                style={{ background: 'none', border: 'none', color: 'var(--muted)', padding: 4, cursor: idx === 0 ? 'default' : 'pointer' }}
              >
                <ChevronUp size={14} />
              </button>
              <button
                onClick={() => moveMetric(key, 1)}
                disabled={idx === orderedKeys.length - 1}
                style={{ background: 'none', border: 'none', color: 'var(--muted)', padding: 4, cursor: idx === orderedKeys.length - 1 ? 'default' : 'pointer' }}
              >
                <ChevronDown size={14} />
              </button>
            </div>
            <span className="text-body">{METRIC_DEFS[key]?.label || key}</span>
          </div>
          <button
            onClick={() => toggleMetric(key)}
            style={{
              width: 48, height: 28, borderRadius: 14, border: 'none',
              background: allMetrics.includes(key) ? 'var(--accent)' : 'var(--border)',
              position: 'relative', transition: 'background 0.2s', cursor: 'pointer',
            }}
          >
            <div style={{
              width: 22, height: 22, borderRadius: '50%', background: 'white',
              position: 'absolute', top: 3,
              left: allMetrics.includes(key) ? 23 : 3,
              transition: 'left 0.2s',
            }} />
          </button>
        </div>
      ))}
    </div>
  )
}

function NotificationsCard() {
  const [notifConfig, setNotifConfig] = useState(getNotificationConfig)

  async function toggleNotification(type: NotificationType) {
    const current = notifConfig[type]
    if (!current.enabled) {
      const granted = await requestNotificationPermission()
      if (!granted) return
    }
    const updated = {
      ...notifConfig,
      [type]: { ...current, enabled: !current.enabled },
    }
    setNotifConfig(updated)
    saveNotificationConfig(updated)
  }

  function setNotifTime(type: NotificationType, time: string) {
    const updated = {
      ...notifConfig,
      [type]: { ...notifConfig[type], time },
    }
    setNotifConfig(updated)
    saveNotificationConfig(updated)
  }

  return (
    <div className="card">
      <div className="text-title" style={{ marginBottom: 12 }}>Notifications</div>
      {(Object.keys(NOTIFICATION_LABELS) as NotificationType[]).map(type => {
        const { label, description } = NOTIFICATION_LABELS[type]
        const config = notifConfig[type]
        return (
          <div key={type} style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '12px 0', borderBottom: '1px solid var(--border)',
          }}>
            <div>
              <div className="text-body">{label}</div>
              <div className="text-caption">{description}</div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              {config.enabled && config.time !== undefined && (
                <input
                  type="time"
                  value={config.time}
                  onChange={e => setNotifTime(type, e.target.value)}
                  style={{
                    background: 'var(--card-elevated)', border: '1px solid var(--border)',
                    borderRadius: 8, color: 'var(--text)', padding: '4px 8px', fontSize: '0.8rem',
                  }}
                />
              )}
              <button
                onClick={() => toggleNotification(type)}
                style={{
                  width: 48, height: 28, borderRadius: 14, border: 'none',
                  background: config.enabled ? 'var(--accent)' : 'var(--border)',
                  position: 'relative', transition: 'background 0.2s', cursor: 'pointer',
                }}
              >
                <div style={{
                  width: 22, height: 22, borderRadius: '50%', background: 'white',
                  position: 'absolute', top: 3,
                  left: config.enabled ? 23 : 3,
                  transition: 'left 0.2s',
                }} />
              </button>
            </div>
          </div>
        )
      })}
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

      {/* Profile / Targets */}
      <p className="settings-section-header">Profile</p>
      <TargetsCard />

      {/* Dashboard */}
      <p className="settings-section-header">Dashboard</p>
      <DashboardCard />

      {/* Notifications */}
      <p className="settings-section-header">Notifications</p>
      <NotificationsCard />

      {/* Integrations */}
      <p className="settings-section-header">Integrations</p>

      <div className="card">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <p className="text-body" style={{ margin: 0, fontWeight: 600 }}>Garmin Connect</p>
            <p className="text-caption" style={{ margin: '2px 0 0' }}>
              Timezone: {health.data?.tz ?? '…'}
            </p>
          </div>
          <span className={`badge fixed ${health.data?.data_source ?? ''}`}>
            {health.data?.data_source === 'mock' ? 'Mock data' : health.data?.data_source ?? '…'}
          </span>
        </div>
        {health.data?.data_source === 'mock' && (
          <p className="text-caption" style={{ marginTop: 8, marginBottom: 0 }}>
            Using generated sample data. To use real Garmin data, set DATA_SOURCE=garmin and your
            credentials in .env, then restart the backend.
          </p>
        )}
      </div>

      <MfpCard />

      <AIProviderCard />

      {/* Data */}
      <p className="settings-section-header">Data</p>

      <div className="card">
        <button onClick={() => sync.mutate()} disabled={sync.isPending} style={{ width: '100%' }}>
          {sync.isPending ? 'Syncing…' : 'Sync now (last 7 days)'}
        </button>
        {sync.data && (
          <p className="text-caption" style={{ marginTop: 8, marginBottom: 0 }}>
            Last run: {sync.data.status}
            {sync.data.error ? ` — ${sync.data.error}` : ''}
            {sync.data.status === 'ok' && sync.data.metrics_synced != null && (
              sync.data.metrics_synced === 0 && sync.data.sleeps_synced === 0 && sync.data.activities_synced === 0 && sync.data.weights_synced === 0
                ? ' — no data received from Garmin'
                : ` — ${sync.data.metrics_synced} metrics, ${sync.data.sleeps_synced} sleeps, ${sync.data.activities_synced} activities, ${sync.data.weights_synced} weights`
            )}
          </p>
        )}
      </div>

      <div className="card">
        <p className="text-title" style={{ marginBottom: 10 }}>Sync history</p>
        <table>
          <thead>
            <tr>
              <th>Started</th>
              <th>Source</th>
              <th>Days</th>
              <th>Records</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {(log.data ?? []).map((r) => (
              <tr key={r.id}>
                <td>{r.started_at.slice(0, 16).replace('T', ' ')}</td>
                <td>{r.source}</td>
                <td>{r.days_requested}</td>
                <td>{r.metrics_synced != null ? `${r.metrics_synced}/${r.sleeps_synced}/${r.activities_synced}/${r.weights_synced}` : '–'}</td>
                <td>
                  <span className={`badge ${r.status}`}>{r.status}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {(log.data ?? []).length === 0 && (
          <p className="text-caption" style={{ marginTop: 8 }}>No sync history yet.</p>
        )}
      </div>

      {/* About */}
      <p className="settings-section-header">About</p>
      <div className="card">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <span className="text-body">Health App</span>
          <span className="text-caption">v1.0.0</span>
        </div>
      </div>
    </>
  )
}
