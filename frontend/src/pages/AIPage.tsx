import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { MessageSquarePlus, Trash2, Zap, CalendarDays } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Markdown from '../components/Markdown'
import { apiDelete, apiGet, apiPost } from '../api/client'
import type { AIStatus, ChatSession } from '../api/types'
import SwipeToDelete from '../components/SwipeToDelete'

interface ReportMeta {
  id: number
  created_at: string
  kind: string
  model: string
  period_start: string
  period_end: string
  status: string
  error: string | null
}

interface Report extends ReportMeta {
  report_md: string
}

export default function AIPage() {
  const [tab, setTab] = useState<'chat' | 'reports'>('chat')
  const status = useQuery({
    queryKey: ['ai-status'],
    queryFn: () => apiGet<AIStatus>('/api/ai/status'),
  })

  // The agent and the report writer are configured separately, so a missing key
  // for one shouldn't blank out the other.
  const model = tab === 'chat' ? status.data?.agent_model : status.data?.model
  const ready = tab === 'chat' ? status.data?.agent_configured : status.data?.configured

  return (
    <>
      <h1>AI Analyst</h1>
      <p className="text-caption" style={{ margin: '0 4px 12px' }}>
        Model: {model ?? '…'}
      </p>
      <div className="tabs">
        {(['chat', 'reports'] as const).map((t) => (
          <button key={t} className={`chip ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>
            {t[0].toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>
      {status.data && !ready ? (
        <NotConfigured which={tab} />
      ) : tab === 'chat' ? (
        <ChatTab />
      ) : (
        <ReportsTab />
      )}
    </>
  )
}

function NotConfigured({ which }: { which: 'chat' | 'reports' }) {
  return (
    <div className="card">
      <p className="text-title" style={{ marginBottom: 8 }}>Not configured</p>
      <p className="muted">
        {which === 'chat'
          ? 'Set a model and API key under Settings › AI assistant. The model must support tool calling.'
          : 'Set AI_API_KEY in your .env file and restart the backend.'}{' '}
        Open models cost pennies. Prefer providers that don't retain or train on your prompts — open
        weights alone don't make a request private.
      </p>
    </div>
  )
}

function ReportsTab() {
  const qc = useQueryClient()
  const [openId, setOpenId] = useState<number | null>(null)

  const reports = useQuery({
    queryKey: ['ai-reports'],
    queryFn: () => apiGet<ReportMeta[]>('/api/ai/reports'),
  })
  const report = useQuery({
    queryKey: ['ai-report', openId],
    queryFn: () => apiGet<Report>(`/api/ai/reports/${openId}`),
    enabled: openId != null,
  })

  const generate = useMutation({
    mutationFn: () => apiPost<Report>('/api/ai/reports/generate?days=30'),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['ai-reports'] })
      setOpenId(data.id)
    },
  })

  const remove = useMutation({
    mutationFn: (id: number) => apiDelete(`/api/ai/reports/${id}`),
    onSuccess: () => {
      setOpenId(null)
      qc.invalidateQueries({ queryKey: ['ai-reports'] })
    },
  })

  return (
    <>
      <button
        style={{ width: '100%', marginBottom: 12, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}
        onClick={() => generate.mutate()}
        disabled={generate.isPending}
      >
        <Zap size={16} />
        {generate.isPending ? 'Analysing your data… (up to a minute)' : 'Generate report now'}
      </button>
      {generate.isError && (
        <p className="error-text">{String(generate.error).replace(/^\d+: /, '').slice(0, 200)}</p>
      )}

      {openId != null && report.data && (
        <div className="card">
          <div className="row" style={{ justifyContent: 'space-between', marginBottom: 4 }}>
            <span className="text-body" style={{ fontWeight: 600 }}>
              {report.data.period_start} → {report.data.period_end}
            </span>
            <button className="secondary fixed" onClick={() => setOpenId(null)} style={{ padding: '8px 14px' }}>
              Close
            </button>
          </div>
          <div className="report-md">
            <Markdown>{report.data.report_md}</Markdown>
          </div>
        </div>
      )}

      <div className="card">
        <p className="text-title" style={{ marginBottom: 8 }}>History</p>
        {(reports.data ?? []).length === 0 && <p className="muted">No reports yet.</p>}
        {(reports.data ?? []).map((r) => (
          <SwipeToDelete key={r.id} onDelete={() => remove.mutate(r.id)}>
            <div className="list-item" onClick={() => setOpenId(r.id)} style={{ cursor: 'pointer' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1, minWidth: 0 }}>
                {r.kind === 'weekly'
                  ? <CalendarDays size={16} style={{ color: 'var(--accent)', flexShrink: 0 }} />
                  : <Zap size={16} style={{ color: 'var(--amber)', flexShrink: 0 }} />
                }
                <div className="main">
                  <div className="name">
                    {r.kind === 'weekly' ? 'Weekly' : 'On demand'} · {r.created_at.slice(0, 10)}
                  </div>
                  <div className="detail">
                    {r.period_start} → {r.period_end} · {r.model.split('/').pop()}
                    {r.status === 'error' ? ' · failed' : ''}
                  </div>
                </div>
              </div>
              <Trash2 size={16} style={{ color: 'var(--muted)', flexShrink: 0 }} />
            </div>
          </SwipeToDelete>
        ))}
      </div>
    </>
  )
}

function ChatTab() {
  const qc = useQueryClient()
  const navigate = useNavigate()

  const sessions = useQuery({
    queryKey: ['ai-sessions'],
    queryFn: () => apiGet<ChatSession[]>('/api/ai/sessions'),
  })

  const create = useMutation({
    mutationFn: () => apiPost<ChatSession>('/api/ai/sessions'),
    onSuccess: (s) => {
      qc.invalidateQueries({ queryKey: ['ai-sessions'] })
      navigate(`/ai/chat/${s.id}`)
    },
  })

  const remove = useMutation({
    mutationFn: (id: number) => apiDelete(`/api/ai/sessions/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ai-sessions'] }),
  })

  const rows = sessions.data ?? []

  return (
    <>
      <button
        style={{ width: '100%', marginBottom: 12, minHeight: 44, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}
        onClick={() => create.mutate()}
        disabled={create.isPending}
      >
        <MessageSquarePlus size={16} />
        New chat
      </button>
      {create.isError && (
        <p className="error-text">{String(create.error).replace(/^\d+: /, '').slice(0, 200)}</p>
      )}

      <div className="card">
        <p className="text-title" style={{ marginBottom: 8 }}>Conversations</p>
        {rows.length === 0 && (
          <p className="muted">
            No chats yet. The assistant can read your whole history — not just the last month — and
            will tell you when the data isn't there instead of guessing.
          </p>
        )}
        {rows.map((s) => (
          <SwipeToDelete key={s.id} onDelete={() => remove.mutate(s.id)}>
            <div
              className="list-item"
              onClick={() => navigate(`/ai/chat/${s.id}`)}
              style={{ cursor: 'pointer', minHeight: 44 }}
            >
              <div className="main">
                <div className="name">{s.title ?? 'New chat'}</div>
                <div className="detail">
                  {s.updated_at.slice(0, 10)} · {s.message_count} message
                  {s.message_count === 1 ? '' : 's'}
                </div>
              </div>
              <Trash2 size={16} style={{ color: 'var(--muted)', flexShrink: 0 }} />
            </div>
          </SwipeToDelete>
        ))}
      </div>
    </>
  )
}
