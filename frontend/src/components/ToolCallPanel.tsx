// ToolCallPanel.tsx — the right sidebar showing agent tool calls in real time
//
// WHY show tool calls?
// --------------------
// Transparency. The user can see exactly what the agent investigated
// to reach its answer — which tools ran, what arguments were used,
// and what data came back. This builds trust and helps debugging.

import { useState } from 'react'
import type { ToolCall } from '../types'

interface Props {
  toolCalls: ToolCall[]
  isOpen: boolean
  onToggle: () => void
}

export function ToolCallPanel({ toolCalls, isOpen, onToggle }: Props) {
  // expandedIds: tracks which individual tool calls are expanded
  // (showing their full result). Others are collapsed to just the name.
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set())

  const toggleExpanded = (id: string) => {
    setExpandedIds(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  return (
    <div
      style={{
        width: isOpen ? '320px' : '40px',
        minWidth: isOpen ? '320px' : '40px',
        borderLeft: '1px solid #e5e7eb',
        background: '#f7f8fa',
        display: 'flex',
        flexDirection: 'column',
        transition: 'width 0.2s ease',
        overflow: 'hidden',
        position: 'relative',
      }}
    >
      {/* Toggle button — always visible even when panel is collapsed */}
      <button
        onClick={onToggle}
        title={isOpen ? 'Hide tool calls' : 'Show tool calls'}
        style={{
          position: 'absolute',
          top: '12px',
          left: isOpen ? '8px' : '4px',
          background: 'none',
          border: '1px solid #e5e7eb',
          borderRadius: '6px',
          cursor: 'pointer',
          padding: '4px 8px',
          fontSize: '12px',
          color: '#57606a',
          whiteSpace: 'nowrap',
          zIndex: 1,
        }}
      >
        {isOpen ? '⚙ Hide tools' : '⚙'}
      </button>

      {isOpen && (
        <div style={{ marginTop: '44px', overflowY: 'auto', padding: '0 12px 12px' }}>
          <div
            style={{
              fontSize: '12px',
              fontWeight: 600,
              color: '#57606a',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              marginBottom: '12px',
            }}
          >
            Tool Calls
          </div>

          {toolCalls.length === 0 ? (
            <div style={{ fontSize: '13px', color: '#8c959f' }}>
              No tools called yet.
            </div>
          ) : (
            toolCalls.map(tc => (
              <ToolCallItem
                key={tc.id}
                toolCall={tc}
                isExpanded={expandedIds.has(tc.id)}
                onToggle={() => toggleExpanded(tc.id)}
              />
            ))
          )}
        </div>
      )}
    </div>
  )
}

// ── Individual tool call item ─────────────────────────────────────────────────

interface ItemProps {
  toolCall: ToolCall
  isExpanded: boolean
  onToggle: () => void
}

function ToolCallItem({ toolCall, isExpanded, onToggle }: ItemProps) {
  const isPending = toolCall.status === 'pending'

  return (
    <div
      style={{
        marginBottom: '8px',
        border: '1px solid #e5e7eb',
        borderRadius: '8px',
        background: '#fff',
        overflow: 'hidden',
      }}
    >
      {/* Header row — always visible, click to expand */}
      <button
        onClick={onToggle}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '8px 10px',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          textAlign: 'left',
        }}
      >
        {/* Status indicator: spinner while pending, checkmark when done */}
        <span style={{ fontSize: '14px' }}>
          {isPending ? '⏳' : '✅'}
        </span>

        <span
          style={{
            flex: 1,
            fontSize: '13px',
            fontWeight: 500,
            fontFamily: 'monospace',
            color: '#1f2328',
          }}
        >
          {toolCall.name}
        </span>

        <span style={{ fontSize: '11px', color: '#8c959f' }}>
          {isExpanded ? '▲' : '▼'}
        </span>
      </button>

      {/* Expanded content: inputs and result */}
      {isExpanded && (
        <div style={{ padding: '0 10px 10px', borderTop: '1px solid #f0f0f0' }}>
          {/* Input arguments */}
          <div style={{ fontSize: '11px', color: '#57606a', marginTop: '8px', marginBottom: '4px' }}>
            INPUT
          </div>
          <pre
            style={{
              margin: 0,
              fontSize: '12px',
              background: '#f7f8fa',
              padding: '6px 8px',
              borderRadius: '4px',
              overflowX: 'auto',
              color: '#1f2328',
            }}
          >
            {JSON.stringify(toolCall.input, null, 2)}
          </pre>

          {/* Result — only shown after tool completes */}
          {toolCall.result && (
            <>
              <div style={{ fontSize: '11px', color: '#57606a', marginTop: '8px', marginBottom: '4px' }}>
                RESULT
              </div>
              <pre
                style={{
                  margin: 0,
                  fontSize: '12px',
                  background: '#f7f8fa',
                  padding: '6px 8px',
                  borderRadius: '4px',
                  overflowX: 'auto',
                  color: '#1f2328',
                  maxHeight: '200px',
                  overflowY: 'auto',
                }}
              >
                {toolCall.result}
              </pre>
            </>
          )}
        </div>
      )}
    </div>
  )
}
