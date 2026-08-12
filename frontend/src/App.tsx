// App.tsx — the root component that assembles the full layout
//
// Layout:
// ┌─────────────────────────────────────┬──────────────┐
// │  Header                             │              │
// ├─────────────────────────────────────┤  Tool Call   │
// │                                     │  Panel       │
// │  ChatWindow (scrollable messages)   │  (sidebar)   │
// │                                     │              │
// ├─────────────────────────────────────┤              │
// │  InputBar                           │              │
// └─────────────────────────────────────┴──────────────┘

import { useState, useMemo } from 'react'
import { useChat } from './hooks/useChat'
import { ChatWindow } from './components/ChatWindow'
import { ToolCallPanel } from './components/ToolCallPanel'
import { InputBar } from './components/InputBar'

function App() {
  // Generate a single conversation ID for this page session.
  // useMemo with [] means it's computed once and never changes.
  // This is what the backend uses to look up conversation history.
  const conversationId = useMemo(() => crypto.randomUUID(), [])

  const { messages, isStreaming, sendMessage } = useChat(conversationId)

  // panelOpen: controls whether the tool-call sidebar is visible
  const [panelOpen, setPanelOpen] = useState(true)

  // Collect all tool calls from all assistant messages for the panel.
  // The panel shows the complete tool call history across the conversation.
  const allToolCalls = messages.flatMap(m => m.toolCalls ?? [])

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',        // full viewport height
        fontFamily: '-apple-system, "Segoe UI", system-ui, sans-serif',
        background: '#ffffff',
        color: '#1f2328',
      }}
    >
      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div
        style={{
          padding: '12px 20px',
          borderBottom: '1px solid #e5e7eb',
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          background: '#fff',
          flexShrink: 0,     // header never shrinks
        }}
      >
        <span style={{ fontSize: '20px' }}>⎈</span>
        <span style={{ fontWeight: 600, fontSize: '16px' }}>kubefriend</span>
        <span style={{ fontSize: '13px', color: '#57606a', marginLeft: '4px' }}>
          AI DevOps Assistant
        </span>
        {isStreaming && (
          <span
            style={{
              marginLeft: 'auto',
              fontSize: '12px',
              color: '#3b82d4',
              animation: 'pulse 1s infinite',
            }}
          >
            ● Investigating...
          </span>
        )}
      </div>

      {/* ── Main area: chat + sidebar ───────────────────────────────────── */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>

        {/* ── Left: chat area ─────────────────────────────────────────── */}
        <div
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            minWidth: 0,   // prevents flex children from overflowing
          }}
        >
          <ChatWindow messages={messages} />
          <InputBar onSend={sendMessage} isStreaming={isStreaming} />
        </div>

        {/* ── Right: tool call panel ──────────────────────────────────── */}
        <ToolCallPanel
          toolCalls={allToolCalls}
          isOpen={panelOpen}
          onToggle={() => setPanelOpen(p => !p)}
        />
      </div>
    </div>
  )
}

export default App
