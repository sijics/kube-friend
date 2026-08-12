// api.ts — the only file that knows how to talk to the backend
//
// WHY isolate fetch logic here?
// ------------------------------
// Every other file just calls streamChat(...). If the backend URL changes,
// if we add auth headers, or if we switch from SSE to WebSockets — we change
// this one file. Nothing else needs to touch.

import type { SSEEvent } from './types'

// The conversation ID is generated once per page load (in App.tsx) and
// passed into every streamChat call. This is how the backend ties multiple
// questions together into one conversation with shared history.

export interface StreamCallbacks {
  onToken: (token: string) => void
  onToolCall: (name: string, input: Record<string, unknown>) => void
  onToolResult: (name: string, result: string) => void
  onDone: () => void
  onError: (message: string) => void
}

export async function streamChat(
  message: string,
  conversationId: string,
  callbacks: StreamCallbacks,
): Promise<void> {
  // POST to /api/chat.
  // In dev: Vite proxy forwards this to http://localhost:8000/api/chat
  // In prod: nginx proxy forwards this to http://backend:8000/api/chat
  // The frontend never hardcodes the backend host — the proxy handles it.
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, conversation_id: conversationId }),
  })

  if (!response.ok) {
    callbacks.onError(`HTTP ${response.status}: ${response.statusText}`)
    return
  }

  if (!response.body) {
    callbacks.onError('Response body is null — SSE stream unavailable')
    return
  }

  // HOW we read the SSE stream:
  // ----------------------------
  // response.body is a ReadableStream<Uint8Array> — raw bytes arriving over
  // the open HTTP connection. We need to:
  // 1. Decode bytes → text (TextDecoder)
  // 2. Split text into lines (SSE events are newline-delimited)
  // 3. Parse the "data: ..." lines as JSON
  // 4. Call the appropriate callback

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  // WHY a buffer?
  // The stream arrives in arbitrary chunks. A single SSE event might be split
  // across two chunks, or two events might arrive in one chunk.
  // We accumulate text in a buffer and process complete lines only.

  while (true) {
    const { done, value } = await reader.read()

    if (done) break

    // Decode the binary chunk to a UTF-8 string and add to buffer
    buffer += decoder.decode(value, { stream: true })

    // Split on newlines — each SSE event ends with \n\n
    // We process all complete lines and keep any trailing partial line in buffer
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''   // last element may be incomplete — save for next chunk

    for (const line of lines) {
      // SSE lines look like:  data: {"type":"token","data":"Why"}
      // We only care about lines starting with "data: "
      if (!line.startsWith('data: ')) continue

      const jsonStr = line.slice('data: '.length).trim()
      if (!jsonStr) continue

      let event: SSEEvent
      try {
        event = JSON.parse(jsonStr) as SSEEvent
      } catch {
        // Malformed JSON — skip this line (ping/heartbeat lines can be empty)
        continue
      }

      // Dispatch to the right callback based on event type
      switch (event.type) {
        case 'token':
          callbacks.onToken(event.data)
          break
        case 'tool_call':
          callbacks.onToolCall(event.data.name, event.data.input)
          break
        case 'tool_result':
          callbacks.onToolResult(event.data.name, event.data.result)
          break
        case 'done':
          callbacks.onDone()
          return   // stream is finished — exit the while loop
        case 'error':
          callbacks.onError(event.data.message)
          return
      }
    }
  }
}
