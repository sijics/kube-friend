// App.tsx — root component with Chat and Dashboard tabs
//
// Layout (Chat tab):
// ┌──────────────────────────────────────────────────────┐
// │  Header          [Chat] [Dashboard]                  │
// ├───────────────────────────────────┬──────────────────┤
// │  ChatWindow                       │  Tool Call Panel │
// ├───────────────────────────────────┤                  │
// │  InputBar                         │                  │
// └───────────────────────────────────┴──────────────────┘
//
// Layout (Dashboard tab):
// ┌──────────────────────────────────────────────────────┐
// │  Header          [Chat] [Dashboard]                  │
// ├──────────────────────────────────────────────────────┤
// │  SummaryBar                                          │
// │  NamespaceSelector                                   │
// │  PodTable (with AI diagnosis + Ask AI buttons)       │
// └──────────────────────────────────────────────────────┘

import { useState, useMemo, useCallback } from 'react'
import { useChat } from './hooks/useChat'
import { ChatWindow } from './components/ChatWindow'
import { ToolCallPanel } from './components/ToolCallPanel'
import { InputBar } from './components/InputBar'
import Dashboard from './components/Dashboard'

type Tab = 'chat' | 'dashboard'

function App() {
  const conversationId = useMemo(() => crypto.randomUUID(), [])
  const { messages, isStreaming, sendMessage } = useChat(conversationId)
  const [panelOpen, setPanelOpen] = useState(true)
  const [activeTab, setActiveTab] = useState<Tab>('chat')
  const [pendingQuestion, setPendingQuestion] = useState('')

  const allToolCalls = messages.flatMap(m => m.toolCalls ?? [])

  // Called from Dashboard "Ask AI" button:
  // pre-fills InputBar and switches to chat tab
  const handleAskAboutPod = useCallback((question: string) => {
    setPendingQuestion(question)
    setActiveTab('chat')
  }, [])

  // Called by InputBar when it consumes the pending question
  const handleSend = useCallback((msg: string) => {
    setPendingQuestion('')
    sendMessage(msg)
  }, [sendMessage])

  return (
    <div style={styles.root}>

      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div style={styles.header}>
        <span style={{ fontSize: 20 }}>⎈</span>
        <span style={styles.brandName}>kubefriend</span>
        <span style={styles.brandSub}>AI DevOps Assistant</span>

        {/* Tab switcher */}
        <div style={styles.tabs}>
          <TabBtn label="💬 Chat"      active={activeTab === 'chat'}      onClick={() => setActiveTab('chat')} />
          <TabBtn label="📊 Dashboard" active={activeTab === 'dashboard'} onClick={() => setActiveTab('dashboard')} />
        </div>

        {isStreaming && (
          <span style={styles.streamingBadge}>● Investigating...</span>
        )}
      </div>

      {/* ── Chat tab ───────────────────────────────────────────────────── */}
      {activeTab === 'chat' && (
        <div style={styles.chatLayout}>
          <div style={styles.chatMain}>
            <ChatWindow messages={messages} />
            <InputBar
              onSend={handleSend}
              isStreaming={isStreaming}
              prefill={pendingQuestion}
            />
          </div>
          <ToolCallPanel
            toolCalls={allToolCalls}
            isOpen={panelOpen}
            onToggle={() => setPanelOpen(p => !p)}
          />
        </div>
      )}

      {/* ── Dashboard tab ──────────────────────────────────────────────── */}
      {activeTab === 'dashboard' && (
        <div style={styles.dashboardLayout}>
          <Dashboard onAskAboutPod={handleAskAboutPod} />
        </div>
      )}

    </div>
  )
}

function TabBtn({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '5px 14px',
        borderRadius: 6,
        border: active ? '1px solid #3b82f6' : '1px solid #e5e7eb',
        background: active ? '#eff6ff' : 'transparent',
        color: active ? '#1d4ed8' : '#6b7280',
        fontWeight: active ? 600 : 400,
        fontSize: 13,
        cursor: 'pointer',
      }}
    >
      {label}
    </button>
  )
}

const styles: Record<string, React.CSSProperties> = {
  root: {
    display: 'flex',
    flexDirection: 'column',
    height: '100vh',
    fontFamily: '-apple-system, "Segoe UI", system-ui, sans-serif',
    background: '#ffffff',
    color: '#1f2328',
  },
  header: {
    padding: '10px 20px',
    borderBottom: '1px solid #e5e7eb',
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    background: '#fff',
    flexShrink: 0,
  },
  brandName: {
    fontWeight: 600,
    fontSize: 16,
  },
  brandSub: {
    fontSize: 13,
    color: '#57606a',
    marginRight: 'auto',
  },
  tabs: {
    display: 'flex',
    gap: 6,
  },
  streamingBadge: {
    marginLeft: 12,
    fontSize: 12,
    color: '#3b82d4',
  },
  chatLayout: {
    display: 'flex',
    flex: 1,
    overflow: 'hidden',
  },
  chatMain: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
    minWidth: 0,
  },
  dashboardLayout: {
    flex: 1,
    overflowY: 'auto',
  },
}

export default App
