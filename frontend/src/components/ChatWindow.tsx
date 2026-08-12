// ChatWindow.tsx — the scrollable list of messages
//
// WHY auto-scroll?
// ----------------
// As new tokens arrive, the message list grows. Without auto-scroll,
// the user would have to manually scroll to see new content.
// We scroll to a hidden div at the bottom of the list after every render.

import { useEffect, useRef } from 'react'
import type { Message } from '../types'
import { MessageBubble } from './MessageBubble'

interface Props {
  messages: Message[]
}

export function ChatWindow({ messages }: Props) {
  // bottomRef is attached to an invisible div at the end of the message list.
  // Calling scrollIntoView() on it scrolls the container to the bottom.
  const bottomRef = useRef<HTMLDivElement>(null)

  // useEffect runs after every render — including when messages changes
  // (new token appended, new message added, tool call updated).
  // This keeps the view scrolled to the latest content automatically.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div
      style={{
        flex: 1,             // takes all available vertical space
        overflowY: 'auto',   // scrollable when content exceeds height
        padding: '20px',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {messages.length === 0 && (
        // Empty state — shown before any messages are sent
        <div
          style={{
            margin: 'auto',
            textAlign: 'center',
            color: '#57606a',
          }}
        >
          <div style={{ fontSize: '32px', marginBottom: '12px' }}>⎈</div>
          <div style={{ fontSize: '18px', fontWeight: 600, marginBottom: '8px' }}>
            kubefriend
          </div>
          <div style={{ fontSize: '14px' }}>
            Ask me anything about your Kubernetes cluster.
          </div>
          <div style={{ fontSize: '13px', marginTop: '8px', color: '#8c959f' }}>
            e.g. "Why is my openrag-backend pod failing?"
          </div>
        </div>
      )}

      {messages.map(message => (
        <MessageBubble key={message.id} message={message} />
      ))}

      {/* Invisible anchor at the bottom — scrollIntoView targets this */}
      <div ref={bottomRef} />
    </div>
  )
}
