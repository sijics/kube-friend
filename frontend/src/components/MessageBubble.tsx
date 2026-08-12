// MessageBubble.tsx — renders a single chat message
//
// WHY two distinct visual styles?
// --------------------------------
// User messages (right-aligned, accent colour) vs assistant messages
// (left-aligned, neutral) is the universal chat UI pattern. It instantly
// communicates who said what without needing labels.

import ReactMarkdown from 'react-markdown'
import type { Message } from '../types'

interface Props {
  message: Message
}

export function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user'

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: isUser ? 'flex-end' : 'flex-start',
        marginBottom: '12px',
      }}
    >
      <div
        style={{
          maxWidth: '75%',
          padding: '10px 14px',
          borderRadius: isUser ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
          background: isUser ? '#3b82d4' : '#f1f3f5',
          color: isUser ? '#fff' : '#1f2328',
          fontSize: '14px',
          lineHeight: '1.6',
          // Preserve whitespace in assistant messages — markdown needs this
          whiteSpace: isUser ? 'pre-wrap' : undefined,
        }}
      >
        {isUser ? (
          // User messages are plain text — no markdown rendering needed
          message.content
        ) : (
          // Assistant messages are rendered as markdown.
          // WHY markdown? GPT-4o naturally formats answers with **bold**,
          // bullet lists, and code blocks. ReactMarkdown turns that into
          // proper HTML so it's readable rather than showing raw asterisks.
          <ReactMarkdown
            components={{
              // Override default styles for code blocks
              code: ({ children, ...props }) => (
                <code
                  {...props}
                  style={{
                    background: '#e8eaed',
                    padding: '2px 6px',
                    borderRadius: '4px',
                    fontFamily: 'monospace',
                    fontSize: '13px',
                  }}
                >
                  {children}
                </code>
              ),
              pre: ({ children, ...props }) => (
                <pre
                  {...props}
                  style={{
                    background: '#e8eaed',
                    padding: '12px',
                    borderRadius: '8px',
                    overflowX: 'auto',
                    fontSize: '13px',
                  }}
                >
                  {children}
                </pre>
              ),
            }}
          >
            {message.content || '▋'}
            {/* ▋ is a blinking cursor substitute — shows while content is empty during streaming */}
          </ReactMarkdown>
        )}
      </div>
    </div>
  )
}
