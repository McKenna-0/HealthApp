import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, ArrowLeft, Check, PenLine, Send, Square, Wrench, X } from 'lucide-react'
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import { apiGet, apiPost } from '../api/client'
import { streamChatTurn } from '../api/aiStream'
import type { ChatMessage, ChatSessionDetail, PendingAction } from '../api/types'

interface TraceStep {
  call_id: string
  name: string
  summary: string | null
  error: string | null
  done: boolean
}

interface LiveTurn {
  question: string
  steps: TraceStep[]
  answer: string
  pending: PendingAction[]
  error: string | null
  streaming: boolean
}

/** A rendered bubble, with the tool work that produced it folded in above. */
interface Bubble {
  key: string
  role: 'user' | 'assistant'
  content: string
  trace: TraceStep[]
}

/**
 * iOS does not resize the layout viewport when the keyboard opens, so a fixed
 * bottom bar ends up underneath it. visualViewport is the only way to find out
 * how much of the screen the keyboard actually took.
 *
 * The gap between the two viewports is not always a keyboard, though - a
 * horizontal scrollbar or a collapsing Safari toolbar produces a small one too,
 * and reacting to those would jerk the bar around for no reason. Nothing that
 * shallow is a keyboard, so treat it as zero.
 */
const MIN_KEYBOARD_PX = 120

function useKeyboardOffset(): number {
  const [offset, setOffset] = useState(0)

  useEffect(() => {
    const vv = window.visualViewport
    if (!vv) return
    const update = () => {
      const gap = Math.round(window.innerHeight - vv.height - vv.offsetTop)
      setOffset(gap >= MIN_KEYBOARD_PX ? gap : 0)
    }
    vv.addEventListener('resize', update)
    vv.addEventListener('scroll', update)
    update()
    return () => {
      vv.removeEventListener('resize', update)
      vv.removeEventListener('scroll', update)
    }
  }, [])

  return offset
}

/**
 * A failed tool stores its error payload as the message content and has no
 * trace summary. Showing "something went wrong" would hide the one useful part,
 * which is usually specific enough to act on ("unknown field(s) ['weight_kg']").
 */
function toolError(content: string | null): string {
  if (!content) return 'no result recorded'
  try {
    const parsed = JSON.parse(content)
    return String(parsed.message ?? parsed.error ?? 'no result recorded')
  } catch {
    return 'no result recorded'
  }
}

/**
 * Flatten the stored transcript into bubbles. Tool messages aren't shown on
 * their own - they're collected and attached to the assistant reply they led to,
 * which is also why an interrupted turn (tool results, no reply) still renders
 * its trace instead of vanishing.
 */
function toBubbles(messages: ChatMessage[]): Bubble[] {
  const out: Bubble[] = []
  const namesById = new Map<string, string>()
  let trace: TraceStep[] = []

  for (const m of messages) {
    if (m.role === 'user') {
      out.push({ key: `m${m.id}`, role: 'user', content: m.content ?? '', trace: [] })
      trace = []
    } else if (m.role === 'assistant') {
      for (const c of m.tool_calls ?? []) {
        if (c.id) namesById.set(c.id, c.name ?? 'tool')
      }
      if (m.content) {
        out.push({ key: `m${m.id}`, role: 'assistant', content: m.content, trace })
        trace = []
      }
    } else if (m.role === 'tool') {
      trace.push({
        call_id: m.tool_call_id ?? `t${m.id}`,
        name: m.tool_name ?? namesById.get(m.tool_call_id ?? '') ?? 'tool',
        summary: m.trace_summary,
        error: m.trace_summary ? null : toolError(m.content),
        done: true,
      })
    }
  }

  if (trace.length) {
    out.push({ key: 'interrupted', role: 'assistant', content: '', trace })
  }
  return out
}

const SUGGESTIONS = [
  'How has my resting heart rate changed over the past year?',
  'Is my bench press actually progressing, or have I stalled?',
  'Does alcohol show up in my HRV the next morning?',
]

export default function AIChatPage() {
  const { sessionId } = useParams()
  const id = Number(sessionId)
  const navigate = useNavigate()
  const qc = useQueryClient()

  const [input, setInput] = useState('')
  const [live, setLive] = useState<LiveTurn | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const endRef = useRef<HTMLDivElement | null>(null)
  const kbOffset = useKeyboardOffset()

  const session = useQuery({
    queryKey: ['ai-session', id],
    queryFn: () => apiGet<ChatSessionDetail>(`/api/ai/sessions/${id}`),
    enabled: Number.isFinite(id),
  })

  // Only follow the stream if the user is already at the bottom; yanking the
  // view down while they're reading something further up is worse than not
  // following at all.
  const scrollToEnd = useCallback(() => {
    const nearBottom =
      window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 160
    if (nearBottom) endRef.current?.scrollIntoView({ block: 'end' })
  }, [])

  useLayoutEffect(scrollToEnd, [live?.answer, live?.steps.length, session.data?.messages.length, scrollToEnd])

  useEffect(() => () => abortRef.current?.abort(), [])

  const send = async () => {
    const question = input.trim()
    if (!question || live?.streaming) return

    setInput('')
    setLive({ question, steps: [], answer: '', pending: [], error: null, streaming: true })

    const controller = new AbortController()
    abortRef.current = controller

    try {
      await streamChatTurn(
        id,
        question,
        {
          onToken: (text) => setLive((l) => (l ? { ...l, answer: l.answer + text } : l)),
          onToolCall: (e) =>
            setLive((l) =>
              l
                ? {
                    ...l,
                    steps: [
                      ...l.steps,
                      { call_id: e.call_id, name: e.name, summary: null, error: null, done: false },
                    ],
                  }
                : l,
            ),
          onToolResult: (e) =>
            setLive((l) =>
              l
                ? {
                    ...l,
                    steps: l.steps.map((s) =>
                      s.call_id === e.call_id
                        ? { ...s, summary: e.summary, error: e.error, done: true }
                        : s,
                    ),
                  }
                : l,
            ),
          // Held in live state rather than refetched. Refetching mid-turn pulls
          // in the half-written transcript, which then renders alongside the
          // live copy and shows the user their own question twice.
          onPendingAction: (e) =>
            setLive((l) =>
              l
                ? {
                    ...l,
                    pending: [
                      ...l.pending,
                      {
                        id: e.id,
                        session_id: id,
                        kind: 'log_weight',
                        summary_text: e.summary_text,
                        status: 'pending',
                        payload: {},
                        created_at: '',
                        resolved_at: null,
                        result: null,
                      },
                    ],
                  }
                : l,
            ),
          onError: (message) => setLive((l) => (l ? { ...l, error: message } : l)),
        },
        controller.signal,
      )
      await qc.invalidateQueries({ queryKey: ['ai-session', id] })
      qc.invalidateQueries({ queryKey: ['ai-sessions'] })
      // cleared only once the saved transcript is in place, so the answer never
      // blinks out and back in
      setLive((l) => (l?.error ? { ...l, streaming: false } : null))
    } catch (err) {
      if (controller.signal.aborted) {
        await qc.invalidateQueries({ queryKey: ['ai-session', id] })
        setLive(null)
        return
      }
      setInput(question) // don't make them retype it
      setLive({
        question,
        steps: [],
        answer: '',
        pending: [],
        error: String(err).replace(/^Error: /, '').replace(/^\d+: /, '').slice(0, 300),
        streaming: false,
      })
    } finally {
      abortRef.current = null
    }
  }

  if (session.isLoading) return <p className="muted" style={{ padding: 16 }}>Loading…</p>
  if (session.error || !session.data) {
    return (
      <div style={{ padding: 16 }}>
        <p className="error-text">Chat not found.</p>
        <button className="secondary" onClick={() => navigate('/ai')}>Back to chats</button>
      </div>
    )
  }

  const bubbles = toBubbles(session.data.messages)
  const busy = live?.streaming ?? false

  return (
    <>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '8px 0 4px' }}>
        <button
          onClick={() => navigate('/ai')}
          style={{
            background: 'none', border: 'none', color: 'var(--muted)',
            padding: 8, minWidth: 44, minHeight: 44,
            display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer',
          }}
          aria-label="Back to chats"
        >
          <ArrowLeft size={20} />
        </button>
        <h1
          className="text-title"
          style={{ margin: 0, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
        >
          {session.data.title ?? 'New chat'}
        </h1>
      </div>

      <div className="chat-messages">
        {bubbles.length === 0 && !live && (
          <div className="card">
            <p className="text-body" style={{ marginTop: 0 }}>
              Ask anything about your data. I can look across your whole history, not just the last
              month, and I'll say when the data isn't there rather than guess.
            </p>
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                className="secondary"
                onClick={() => setInput(s)}
                style={{ width: '100%', textAlign: 'left', marginTop: 8, minHeight: 44 }}
              >
                {s}
              </button>
            ))}
          </div>
        )}

        {bubbles.map((b) => (
          <div key={b.key}>
            {b.trace.length > 0 && <ToolTrace steps={b.trace} />}
            {b.content && (
              <div className={`chat-msg ${b.role}`}>
                {b.role === 'assistant' ? (
                  <div className="report-md">
                    <ReactMarkdown>{b.content}</ReactMarkdown>
                  </div>
                ) : (
                  b.content
                )}
              </div>
            )}
          </div>
        ))}

        {live && (
          <>
            <div className="chat-msg user">{live.question}</div>
            {live.steps.length > 0 && <ToolTrace steps={live.steps} open />}
            {live.answer && (
              <div className="chat-msg assistant">
                <div className="report-md">
                  <ReactMarkdown>{live.answer}</ReactMarkdown>
                </div>
              </div>
            )}
            {live.streaming && !live.answer && live.steps.length === 0 && (
              <div className="chat-msg assistant">
                <span className="muted">Thinking…</span>
              </div>
            )}
            {live.error && <p className="error-text">{live.error}</p>}
          </>
        )}

        {/* Deduped by id: a draft lives in live state during the turn and in the
            saved session afterwards, and for one render both can be true. */}
        {[
          ...(session.data.pending_actions ?? []),
          ...(live?.pending ?? []).filter(
            (p) => !(session.data.pending_actions ?? []).some((s) => s.id === p.id),
          ),
        ].map((a) => (
          <PendingActionCard key={a.id} action={a} sessionId={id} />
        ))}
        <div ref={endRef} />
      </div>

      <div
        className={`chat-input-bar${kbOffset > 0 ? ' kb-open' : ''}`}
        style={{ transform: `translateY(-${kbOffset}px)` }}
      >
        <input
          placeholder="Ask about your health data…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
          enterKeyHint="send"
        />
        {busy ? (
          <button
            className="secondary fixed"
            onClick={() => abortRef.current?.abort()}
            style={{ minWidth: 44, minHeight: 44, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
            aria-label="Stop"
          >
            <Square size={16} />
          </button>
        ) : (
          <button
            className="fixed"
            onClick={send}
            disabled={!input.trim()}
            style={{ minWidth: 44, minHeight: 44, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
            aria-label="Send"
          >
            <Send size={16} />
          </button>
        )}
      </div>
    </>
  )
}

const RESOLVED_LABEL: Record<string, { text: string; colour: string }> = {
  confirmed: { text: 'Saved', colour: 'var(--green)' },
  rejected: { text: 'Discarded', colour: 'var(--muted)' },
  failed: { text: "Couldn't save", colour: 'var(--red)' },
}

/**
 * The agent drafts, the user decides. Nothing reaches the health tables until
 * Confirm is tapped, so this card is the only path from a suggested entry to a
 * real one - which is also why it shows the exact values rather than a vague
 * "log this?".
 */
function PendingActionCard({ action, sessionId }: { action: PendingAction; sessionId: number }) {
  const qc = useQueryClient()

  const resolve = useMutation({
    mutationFn: (decision: 'confirm' | 'reject') =>
      apiPost<PendingAction>(`/api/ai/pending-actions/${action.id}/${decision}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['ai-session', sessionId] })
      // a confirmed entry changes the day's totals everywhere else
      qc.invalidateQueries({ queryKey: ['dashboard'] })
      qc.invalidateQueries({ queryKey: ['weight'] })
    },
  })

  if (action.status !== 'pending') {
    const label = RESOLVED_LABEL[action.status] ?? { text: action.status, colour: 'var(--muted)' }
    return (
      <p className="text-caption" style={{ margin: '0 0 8px', color: label.colour }}>
        {label.text}: {action.summary_text}
      </p>
    )
  }

  return (
    <div className="card-elevated" style={{ marginBottom: 8 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
        <PenLine size={15} style={{ color: 'var(--amber)', flexShrink: 0, marginTop: 3 }} />
        <div style={{ minWidth: 0 }}>
          <p className="text-body" style={{ margin: 0, fontWeight: 600 }}>{action.summary_text}</p>
          <p className="text-caption" style={{ margin: '2px 0 0' }}>
            Nothing is saved until you confirm.
          </p>
        </div>
      </div>
      <div className="row" style={{ gap: 8, marginTop: 12 }}>
        <button
          onClick={() => resolve.mutate('confirm')}
          disabled={resolve.isPending}
          style={{ flex: 1, minHeight: 44, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}
        >
          <Check size={16} />
          {resolve.isPending ? 'Saving…' : 'Confirm'}
        </button>
        <button
          className="secondary"
          onClick={() => resolve.mutate('reject')}
          disabled={resolve.isPending}
          style={{ flex: 1, minHeight: 44, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}
        >
          <X size={16} />
          Discard
        </button>
      </div>
      {resolve.isError && (
        <p className="error-text" style={{ marginBottom: 0 }}>
          {String(resolve.error).replace(/^\d+: /, '').slice(0, 200)}
        </p>
      )}
    </div>
  )
}

function ToolTrace({ steps, open = false }: { steps: TraceStep[]; open?: boolean }) {
  const running = steps.some((s) => !s.done)
  const label = running
    ? `Checking your data… (${steps.filter((s) => s.done).length}/${steps.length})`
    : `Looked at ${steps.length} ${steps.length === 1 ? 'source' : 'sources'}`

  return (
    <details className="tool-trace" open={open}>
      <summary>
        <Wrench size={13} />
        <span>{label}</span>
      </summary>
      <ul>
        {steps.map((s) => (
          <li key={s.call_id} className={s.error ? 'failed' : ''}>
            {!s.done ? (
              <span className="spinner-dot" aria-hidden />
            ) : s.error ? (
              <AlertTriangle size={12} />
            ) : (
              <Check size={12} />
            )}
            <span>{s.summary ?? s.error ?? s.name}</span>
          </li>
        ))}
      </ul>
    </details>
  )
}
