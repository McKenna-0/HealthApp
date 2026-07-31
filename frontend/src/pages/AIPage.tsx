import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Send, Trash2, Zap, CalendarDays } from 'lucide-react'
import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { apiDelete, apiGet, apiPost } from '../api/client'
import SwipeToDelete from '../components/SwipeToDelete'

interface AIStatus {
  configured: boolean
  model: string | null
  base_url: string
}

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

interface ChatMsg {
  role: 'user' | 'assistant'
  content: string
}

export default function AIPage() {
  const [tab, setTab] = useState<'reports' | 'chat'>('reports')
  const status = useQuery({
    queryKey: ['ai-status'],
    queryFn: () => apiGet<AIStatus>('/api/ai/status'),
  })

  if (status.data && !status.data.configured) {
    return (
      <>
        <h1>AI Analyst</h1>
        <div className="card">
          <p className="text-title" style={{ marginBottom: 8 }}>Not configured</p>
          <p className="muted">
            Get a key at openrouter.ai/keys, then set <code>AI_API_KEY</code> in your <code>.env</code> file and
            restart the backend. Reports cost pennies with open models. Prefer paid models with no-logging
            policies for privacy.
          </p>
        </div>
      </>
    )
  }

  return (
    <>
      <h1>AI Analyst</h1>
      <p className="text-caption" style={{ margin: '0 4px 12px' }}>
        Model: {status.data?.model ?? '…'}
      </p>
      <div className="tabs">
        {(['reports', 'chat'] as const).map((t) => (
          <button key={t} className={`chip ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>
            {t[0].toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>
      {tab === 'reports' ? <ReportsTab /> : <ChatTab />}
    </>
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
            <ReactMarkdown>{report.data.report_md}</ReactMarkdown>
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
  const [messages, setMessages] = useState<ChatMsg[]>([])
  const [input, setInput] = useState('')

  const ask = useMutation({
    mutationFn: (question: string) =>
      apiPost<{ answer: string }>('/api/ai/chat', { question, history: messages }),
    onSuccess: (data, question) => {
      setMessages((m) => [...m, { role: 'user', content: question }, { role: 'assistant', content: data.answer }])
    },
  })

  const send = () => {
    const q = input.trim()
    if (!q) return
    setInput('')
    ask.mutate(q)
  }

  return (
    <>
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="card">
            <p className="muted">
              Ask about your data — e.g. "How did alcohol affect my sleep this month?" or "Am I eating enough
              protein for my training?"
            </p>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`chat-msg ${m.role}`}>
            {m.role === 'assistant' ? (
              <div className="report-md">
                <ReactMarkdown>{m.content}</ReactMarkdown>
              </div>
            ) : (
              m.content
            )}
          </div>
        ))}
        {ask.isPending && (
          <div className="chat-msg assistant">
            <span className="muted">Thinking…</span>
          </div>
        )}
        {ask.isError && <p className="error-text">{String(ask.error).replace(/^\d+: /, '').slice(0, 200)}</p>}
      </div>

      <div className="chat-input-bar">
        <input
          placeholder="Ask about your health data…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
        />
        <button
          className="fixed"
          onClick={send}
          disabled={ask.isPending || !input.trim()}
          style={{ padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 6 }}
        >
          <Send size={16} />
        </button>
      </div>
    </>
  )
}
