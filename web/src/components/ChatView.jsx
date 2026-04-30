import { useState, useRef, useEffect, useCallback } from 'react'
import MessageBubble from './MessageBubble'

const STORAGE_KEY = 'outlook_chat_history'
const HISTORY_KEY = 'outlook_agent_history'

function loadMessages() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function loadHistory() {
  try {
    const raw = localStorage.getItem(HISTORY_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function saveMessages(msgs) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(msgs.slice(-200)))
  } catch { /* ignore quota errors */ }
}

function saveHistory(history) {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(history.slice(-40)))
  } catch { /* ignore */ }
}

const SUGGESTIONS = [
  'Show my latest emails',
  'How many unread emails do I have?',
  'Search for emails about "meeting"',
  'Show my flagged emails',
]

export default function ChatView() {
  const [messages, setMessages] = useState(loadMessages)
  const [agentHistory, setAgentHistory] = useState(loadHistory)
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const bottomRef = useRef(null)
  const inputRef = useRef(null)
  const abortRef = useRef(null)

  useEffect(() => {
    saveMessages(messages)
  }, [messages])

  useEffect(() => {
    saveHistory(agentHistory)
  }, [agentHistory])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const clearChat = () => {
    setMessages([])
    setAgentHistory([])
    localStorage.removeItem(STORAGE_KEY)
    localStorage.removeItem(HISTORY_KEY)
  }

  const sendMessage = useCallback(async (text) => {
    const trimmed = (text || input).trim()
    if (!trimmed || isStreaming) return

    setInput('')
    setIsStreaming(true)

    const userMsg = { id: Date.now(), role: 'user', content: trimmed }
    const assistantId = Date.now() + 1
    const assistantMsg = {
      id: assistantId,
      role: 'assistant',
      content: '',
      toolCalls: [],
      streaming: true,
    }

    setMessages(prev => [...prev, userMsg, assistantMsg])

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ history: agentHistory, message: trimmed }),
        signal: abortRef.current,
      })

      if (!res.ok) {
        throw new Error(`Server error ${res.status}`)
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let finalContent = ''
      let finalToolCalls = []

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop()

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const jsonStr = line.slice(6).trim()
          if (!jsonStr) continue

          let event
          try { event = JSON.parse(jsonStr) } catch { continue }

          if (event.type === 'text_delta') {
            finalContent += event.content
            setMessages(prev => prev.map(m =>
              m.id === assistantId ? { ...m, content: finalContent } : m
            ))
          }

          else if (event.type === 'tool_start') {
            const tc = { id: event.id, name: event.name, args: event.args, status: 'running', result: null }
            finalToolCalls = [...finalToolCalls, tc]
            setMessages(prev => prev.map(m =>
              m.id === assistantId ? { ...m, toolCalls: [...finalToolCalls] } : m
            ))
          }

          else if (event.type === 'tool_end') {
            finalToolCalls = finalToolCalls.map(tc =>
              tc.id === event.id ? { ...tc, status: 'done', result: event.result } : tc
            )
            setMessages(prev => prev.map(m =>
              m.id === assistantId ? { ...m, toolCalls: [...finalToolCalls] } : m
            ))
          }

          else if (event.type === 'error') {
            finalContent += (finalContent ? '\n\n' : '') + `⚠️ ${event.message}`
            setMessages(prev => prev.map(m =>
              m.id === assistantId ? { ...m, content: finalContent, streaming: false } : m
            ))
          }

          else if (event.type === 'done') {
            break
          }
        }
      }

      // Mark streaming complete
      setMessages(prev => prev.map(m =>
        m.id === assistantId ? { ...m, streaming: false } : m
      ))

      // Update agent conversation history (text only, for context in next turn)
      setAgentHistory(prev => [
        ...prev,
        { role: 'user', content: trimmed },
        { role: 'assistant', content: finalContent || '(performed actions)' },
      ])

    } catch (e) {
      if (e.name === 'AbortError') return
      const errContent = `⚠️ Failed to connect to the server. Make sure it's running.\n\n${e.message}`
      setMessages(prev => prev.map(m =>
        m.id === assistantId ? { ...m, content: errContent, streaming: false } : m
      ))
    } finally {
      setIsStreaming(false)
      inputRef.current?.focus()
    }
  }, [input, isStreaming, agentHistory])

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const isEmpty = messages.length === 0

  return (
    <div className="chat-layout">
      {/* Header */}
      <header className="chat-header">
        <div className="chat-header-left">
          <div className="header-icon">
            <svg viewBox="0 0 32 32" fill="none">
              <rect width="32" height="32" rx="8" fill="#0078d4" />
              <path d="M7 12l9 6 9-6" stroke="white" strokeWidth="2" strokeLinecap="round" />
              <rect x="7" y="10" width="18" height="14" rx="2" stroke="white" strokeWidth="2" fill="none" />
            </svg>
          </div>
          <div>
            <h1 className="header-title">Outlook Assistant</h1>
            <p className="header-sub">AI-powered email agent</p>
          </div>
        </div>
        <div className="chat-header-right">
          {messages.length > 0 && (
            <button className="btn-ghost" onClick={clearChat} title="Clear chat">
              Clear chat
            </button>
          )}
        </div>
      </header>

      {/* Messages area */}
      <main className="chat-messages">
        {isEmpty ? (
          <div className="welcome">
            <div className="welcome-icon">✉️</div>
            <h2>How can I help with your emails?</h2>
            <p>I can read, search, send, organize, and summarize your Outlook emails.</p>
            <div className="suggestions">
              {SUGGESTIONS.map(s => (
                <button key={s} className="suggestion-chip" onClick={() => sendMessage(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map(msg => <MessageBubble key={msg.id} message={msg} />)
        )}
        <div ref={bottomRef} />
      </main>

      {/* Input area */}
      <footer className="chat-footer">
        <div className="input-row">
          <textarea
            ref={inputRef}
            className="chat-input"
            placeholder="Ask me about your emails…"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            disabled={isStreaming}
          />
          <button
            className="send-btn"
            onClick={() => sendMessage()}
            disabled={!input.trim() || isStreaming}
            title="Send (Enter)"
          >
            {isStreaming ? (
              <span className="send-spinner" />
            ) : (
              <svg viewBox="0 0 20 20" fill="currentColor">
                <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" />
              </svg>
            )}
          </button>
        </div>
        <p className="input-hint">Press Enter to send · Shift+Enter for new line</p>
      </footer>
    </div>
  )
}
