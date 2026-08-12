// useChat.ts — manages all chat state and drives the SSE stream
//
// WHY a custom hook?
// ------------------
// A React hook is a function that holds state and logic that multiple
// components can share. Without it, you'd put all this logic directly
// in App.tsx — making it huge and hard to follow.
//
// useChat owns:
//   - the messages array (what's displayed in the chat window)
//   - the isStreaming flag (disables the input while the agent is working)
//   - the sendMessage function (triggered by InputBar)
//
// Components just call useChat() and read/use what it returns.
// They don't know anything about fetch, SSE, or state updates.

import { useState, useCallback } from 'react'
import { streamChat } from '../api'
import type { Message, ToolCall } from '../types'

// A tiny helper to generate unique IDs for messages and tool calls.
// We use crypto.randomUUID() — built into modern browsers, no library needed.
const uid = () => crypto.randomUUID()

export function useChat(conversationId: string) {
  // messages: the full conversation displayed in the chat window
  const [messages, setMessages] = useState<Message[]>([])

  // isStreaming: true while the agent is running (disables the input field)
  const [isStreaming, setIsStreaming] = useState(false)

  const sendMessage = useCallback(
    async (userText: string) => {
      if (!userText.trim() || isStreaming) return

      // 1. Add the user's message to the chat immediately — no waiting
      const userMessage: Message = {
        id: uid(),
        role: 'user',
        content: userText,
      }

      // 2. Add an empty assistant message placeholder.
      //    We'll append tokens to it as they stream in.
      //    This gives the "typing..." effect.
      const assistantMessageId = uid()
      const assistantMessage: Message = {
        id: assistantMessageId,
        role: 'assistant',
        content: '',        // starts empty — tokens fill it in
        toolCalls: [],      // tool calls populate as tools are invoked
      }

      // setMessages with a function (not a value) is the React pattern for
      // updates that depend on the previous state — avoids stale closures.
      setMessages(prev => [...prev, userMessage, assistantMessage])
      setIsStreaming(true)

      // Helper to update just the assistant message currently streaming.
      // We find it by ID so we don't accidentally update the wrong message
      // in a future multi-message scenario.
      const updateAssistant = (updater: (msg: Message) => Message) => {
        setMessages(prev =>
          prev.map(m => (m.id === assistantMessageId ? updater(m) : m)),
        )
      }

      // 3. Open the SSE stream and handle each event type
      await streamChat(userText, conversationId, {
        // onToken: a new word/token arrived — append it to the assistant message
        onToken: (token) => {
          updateAssistant(m => ({ ...m, content: m.content + token }))
        },

        // onToolCall: the LLM decided to call a tool — add it to the panel
        // status is "pending" because the tool hasn't returned yet
        onToolCall: (name, input) => {
          const toolCall: ToolCall = {
            id: uid(),
            name,
            input,
            status: 'pending',
          }
          updateAssistant(m => ({
            ...m,
            toolCalls: [...(m.toolCalls ?? []), toolCall],
          }))
        },

        // onToolResult: the tool finished — find it by name and update it
        // We match on name because that's what we have (no tool call ID from SSE)
        onToolResult: (name, result) => {
          updateAssistant(m => ({
            ...m,
            toolCalls: (m.toolCalls ?? []).map(tc =>
              tc.name === name && tc.status === 'pending'
                ? { ...tc, result, status: 'done' }
                : tc,
            ),
          }))
        },

        // onDone: the agent finished — re-enable the input
        onDone: () => {
          setIsStreaming(false)
        },

        // onError: something went wrong — show the error in the assistant message
        onError: (message) => {
          updateAssistant(m => ({
            ...m,
            content: m.content + `\n\n⚠️ Error: ${message}`,
          }))
          setIsStreaming(false)
        },
      })
    },
    [conversationId, isStreaming],
  )

  return { messages, isStreaming, sendMessage }
}
