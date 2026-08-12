// InputBar.tsx — the text input and send button at the bottom of the chat
//
// WHY disable during streaming?
// ------------------------------
// The backend processes one message at a time and the conversation store
// is updated only after the stream completes. Allowing a second message
// mid-stream would send it without the previous assistant response in
// the history, breaking multi-turn context.

import { useState, type KeyboardEvent } from 'react'

interface Props {
  onSend: (message: string) => void
  isStreaming: boolean
}

export function InputBar({ onSend, isStreaming }: Props) {
  const [value, setValue] = useState('')

  const handleSend = () => {
    const trimmed = value.trim()
    if (!trimmed || isStreaming) return
    onSend(trimmed)
    setValue('')     // clear input after sending
  }

  // Allow submitting with Enter key (Shift+Enter adds a newline instead)
  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()   // prevent newline in textarea
      handleSend()
    }
  }

  return (
    <div
      style={{
        display: 'flex',
        gap: '8px',
        padding: '12px 16px',
        borderTop: '1px solid #e5e7eb',
        background: '#fff',
        alignItems: 'flex-end',
      }}
    >
      <textarea
        value={value}
        onChange={e => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={isStreaming}
        placeholder={
          isStreaming
            ? 'kubefriend is investigating...'
            : 'Ask about your cluster... (Enter to send, Shift+Enter for newline)'
        }
        rows={1}
        style={{
          flex: 1,
          padding: '10px 12px',
          border: '1px solid #e5e7eb',
          borderRadius: '12px',
          fontSize: '14px',
          lineHeight: '1.5',
          resize: 'none',         // no manual resize handle — it auto-grows
          outline: 'none',
          fontFamily: 'inherit',
          background: isStreaming ? '#f7f8fa' : '#fff',
          color: '#1f2328',
          // Auto-grow: we use a fixed rows=1 + overflow:hidden so the browser
          // doesn't show a scrollbar — the content just clips. For a true
          // auto-grow textarea we'd use a JS resize observer, but rows=1
          // is clean enough for v1.
          overflowY: 'hidden',
        }}
      />

      <button
        onClick={handleSend}
        disabled={isStreaming || !value.trim()}
        style={{
          padding: '10px 18px',
          background:
            isStreaming || !value.trim() ? '#e5e7eb' : '#3b82d4',
          color: isStreaming || !value.trim() ? '#8c959f' : '#fff',
          border: 'none',
          borderRadius: '12px',
          fontSize: '14px',
          fontWeight: 500,
          cursor: isStreaming || !value.trim() ? 'not-allowed' : 'pointer',
          transition: 'background 0.15s ease',
          whiteSpace: 'nowrap',
        }}
      >
        {isStreaming ? '...' : 'Send'}
      </button>
    </div>
  )
}
