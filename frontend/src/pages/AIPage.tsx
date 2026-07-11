import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { apiDelete, apiGet, apiPost } from '../api/client'

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
          <strong>Not configured</strong>
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
      <p className="muted" style={{ margin: '0 4px 12px' }}>
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
      <button style={{ width: '100%', marginBottom: 12 }} onClick={() => generate.mutate()} disabled={generate.isPending}>
        {generate.isPending ? 'Analysing your data… (up to a minute)' : 'Generate report now'}
      </button>
      {generate.isError && (
        <p className="error-text">{String(generate.error).replace(/^\d+: /, '').slice(0, 200)}</p>
      )}

      {openId != null && report.data && (
        <div className="card">
          <div className="row" style={{ justifyContent: 'space-between', marginBottom: 4 }}>
            <strong>
              {report.data.period_start} → {report.data.period_end}
            </strong>
            <button className="secondary fixed" onClick={() => setOpenId(null)}>
              Close
            </button>
          </div>
          <div className="report-md">
            <ReactMarkdown>{report.data.report_md}</ReactMarkdown>
          </div>
        </div>
      )}

      <div className="card">
        <strong>History</strong>
        {(reports.data ?? []).length === 0 && <p className="muted">No reports yet.</p>}
        {(reports.data ?? []).map((r) => (
          <div key={r.id} className="list-item">
            <div className="main" onClick={() => setOpenId(r.id)} style={{ cursor: 'pointer' }}>
              <div className="name">
                {r.kind === 'weekly' ? '🗓 Weekly' : '⚡ On demand'} · {r.created_at.slice(0, 10)}
              </div>
              <div className="detail">
                {r.period_start} → {r.period_end} · {r.model.split('/').pop()}
                {r.status === 'error' ? ' · failed' : ''}
              </div>
            </div>
            <button className="del" onClick={() => remove.mutate(r.id)}>
              ✕
            </button>
          </div>
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
      <div className="card">
        {messages.length === 0 && (
          <p className="muted">
            Ask about your data — e.g. "How did alcohol affect my sleep this month?" or "Am I eating enough
            protein for my training?"
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} style={{ marginBottom: 10 }}>
            <div className="muted" style={{ fontSize: '0.72rem' }}>
              {m.role === 'user' ? 'You' : 'Analyst'}
            </div>
            {m.role === 'assistant' ? (
              <div className="report-md">
                <ReactMarkdown>{m.content}</ReactMarkdown>
              </div>
            ) : (
              <div>{m.content}</div>
            )}
          </div>
        ))}
        {ask.isPending && <p className="muted">Thinking…</p>}
        {ask.isError && <p className="error-text">{String(ask.error).replace(/^\d+: /, '').slice(0, 200)}</p>}
      </div>
      <div className="row">
        <input
          placeholder="Ask about your health data…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
        />
        <button className="fixed" onClick={send} disabled={ask.isPending || !input.trim()}>
          Send
        </button>
      </div>
    </>
  )
}
