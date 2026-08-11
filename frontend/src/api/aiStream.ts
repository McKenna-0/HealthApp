/**
 * SSE reader for an agent turn.
 *
 * EventSource can't be used here - the turn is a POST with a JSON body - so this
 * reads the response stream by hand. Frames are separated by a blank line, and a
 * chunk boundary can land anywhere, so partial frames are buffered until the
 * separator actually arrives.
 */

export interface ToolCallEvent {
  call_id: string
  name: string
  arguments: string
}

export interface ToolResultEvent {
  call_id: string
  name: string
  ok: boolean
  summary: string | null
  error: string | null
}

export interface PendingActionEvent {
  id: number
  summary_text: string
  status: string
}

export interface StreamHandlers {
  onStart?: (data: { session_id: number; user_message_id: number }) => void
  onToken?: (text: string) => void
  onToolCall?: (event: ToolCallEvent) => void
  onToolResult?: (event: ToolResultEvent) => void
  onPendingAction?: (event: PendingActionEvent) => void
  onMessageDone?: (data: { content: string; finish_reason?: string; warning?: string }) => void
  onTitle?: (title: string) => void
  onError?: (message: string) => void
}

export async function streamChatTurn(
  sessionId: number,
  message: string,
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const resp = await fetch(`/api/ai/sessions/${sessionId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
    signal,
  })

  // Anything that fails before the first byte still has a real status code, so
  // it throws in the same shape as client.ts and the callers' existing
  // String(error).replace(/^\d+: /, '') handling keeps working.
  if (!resp.ok) {
    throw new Error(`${resp.status}: ${await resp.text()}`)
  }
  if (!resp.body) {
    throw new Error('500: streaming is not supported by this browser')
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let split = buffer.indexOf('\n\n')
    while (split !== -1) {
      dispatch(buffer.slice(0, split), handlers)
      buffer = buffer.slice(split + 2)
      split = buffer.indexOf('\n\n')
    }
  }
}

function dispatch(frame: string, h: StreamHandlers): void {
  let event = ''
  let raw = ''
  for (const line of frame.split('\n')) {
    if (line.startsWith('event: ')) event = line.slice(7)
    else if (line.startsWith('data: ')) raw += line.slice(6)
  }
  if (!event || !raw) return

  let data: Record<string, unknown>
  try {
    data = JSON.parse(raw)
  } catch {
    return // a truncated frame is not worth killing the turn over
  }

  switch (event) {
    case 'start':
      h.onStart?.(data as unknown as { session_id: number; user_message_id: number })
      break
    case 'token':
      h.onToken?.(String(data.text ?? ''))
      break
    case 'tool_call':
      h.onToolCall?.(data as unknown as ToolCallEvent)
      break
    case 'tool_result':
      h.onToolResult?.(data as unknown as ToolResultEvent)
      break
    case 'pending_action':
      h.onPendingAction?.(data as unknown as PendingActionEvent)
      break
    case 'message_done':
      h.onMessageDone?.(data as unknown as { content: string; finish_reason?: string; warning?: string })
      break
    case 'title':
      h.onTitle?.(String(data.title ?? ''))
      break
    case 'error':
      h.onError?.(String(data.message ?? 'Unknown error'))
      break
  }
}
