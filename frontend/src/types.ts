// types.ts — shared TypeScript type definitions
//
// WHY a separate types file?
// --------------------------
// TypeScript's superpower is catching shape mismatches at compile time.
// If the backend sends {"type": "token", "data": "Why"} and the frontend
// tries to read .data.text — TypeScript catches that before the browser does.
//
// Defining types once here means every file that imports them stays in sync.
// If you change a type, TypeScript shows you every place that breaks.

// ── SSE Event types coming from the backend ──────────────────────────────────

export type SSEEventType = 'token' | 'tool_call' | 'tool_result' | 'done' | 'error'

export interface SSETokenEvent {
  type: 'token'
  data: string                   // a single LLM output token, e.g. "Why"
}

export interface SSEToolCallEvent {
  type: 'tool_call'
  data: {
    name: string                 // e.g. "get_pod_status"
    input: Record<string, unknown>  // e.g. { namespace: "prod", pod_name: "openrag" }
  }
}

export interface SSEToolResultEvent {
  type: 'tool_result'
  data: {
    name: string                 // same tool name as the matching tool_call
    result: string               // the string the tool returned
  }
}

export interface SSEDoneEvent {
  type: 'done'
  data: Record<string, never>   // empty object — just a signal
}

export interface SSEErrorEvent {
  type: 'error'
  data: {
    message: string
    detail: string
  }
}

// ── Dashboard types ───────────────────────────────────────────────────────────

export type PodSeverity = 'healthy' | 'warning' | 'critical'

export interface DashboardPod {
  name: string
  namespace: string
  status: string           // e.g. "CrashLoopBackOff", "Running", "Pending"
  phase: string            // Kubernetes phase: Running | Pending | Failed | ...
  severity: PodSeverity
  restarts: number
  age_hours: number | null
  node: string
  diagnosis: string | null  // AI-generated root cause
  suggestion: string | null // AI-generated fix
}

export interface DashboardSummary {
  total: number
  running: number
  warning: number
  critical: number
}

export interface DashboardResponse {
  pods: DashboardPod[]
  summary: DashboardSummary
  namespaces: string[]
  error?: string
}

export type SSEEvent =
  | SSETokenEvent
  | SSEToolCallEvent
  | SSEToolResultEvent
  | SSEDoneEvent
  | SSEErrorEvent

// ── Tool call state ───────────────────────────────────────────────────────────

export interface ToolCall {
  id: string                     // unique id for React key prop
  name: string                   // e.g. "get_pod_status"
  input: Record<string, unknown> // arguments GPT-4o passed
  result?: string                // filled in when tool_result arrives
  status: 'pending' | 'done'    // pending = running, done = result received
}

// ── Chat message ──────────────────────────────────────────────────────────────

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string                // the text of the message
  toolCalls?: ToolCall[]         // only present on assistant messages
}
