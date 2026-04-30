import { useState, useRef, useEffect, useCallback } from 'react'
import MessageBubble from './MessageBubble'

const SUGGESTIONS = [
  "Show my latest emails",
  "What's on my calendar today?",
  "Show unread emails",
  "Search emails about 'meeting'",
]

function buildDisplayMessages(apiMessages) {
  return apiMessages.map(m => ({
    id: m.id,
    role: m.role,
    content: m.content,
    toolCalls: m.tool_calls || [],
    streaming: false,
  }))
}

export default function ChatView({ sessionId, onSessionTitleUpdate, theme, onToggleTheme }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [loading, setLoading] = useState(true)
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  // Load messages from DB when session changes
  useEffect(() => {
    loadMessages()
  }, [sessionId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const loadMessages = async () => {
    setLoading(true)
    try {
      const res = await fetch(`/api/sessions/${sessionId}`)
      const data = await res.json()
      setMessages(buildDisplayMessages(data.messages || []))
    } catch { /* ignore */ } finally {
      setLoading(false)
    }
  }

  const sendMessage = useCallback(async (text) => {
    const trimmed = (text || input).trim()
    if (!trimmed || isStreaming) return

    setInput('')
    setIsStreaming(true)

    const userMsgId = `user-${Date.now()}`
    const assistantId = `assistant-${Date.now() + 1}`

    setMessages(prev => [
      ...prev,
      { id: userMsgId, role: 'user', content: trimmed, toolCalls: [], streaming: false },
      { id: assistantId, role: 'assistant', content: '', toolCalls: [], streaming: true },
    ])

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, message: trimmed }),
      })

      if (!res.ok) throw new Error(`Server error ${res.status}`)

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
          const raw = line.slice(6).trim()
          if (!raw) continue
          let event
          try { event = JSON.parse(raw) } catch { continue }

          if (event.type === 'text_delta') {
            finalContent += event.content
            setMessages(prev => prev.map(m =>
              m.id === assistantId ? { ...m, content: finalContent } : m
            ))
          } else if (event.type === 'tool_start') {
            const tc = { id: event.id, name: event.name, args: event.args, status: 'running', result: null }
            finalToolCalls = [...finalToolCalls, tc]
            setMessages(prev => prev.map(m =>
              m.id === assistantId ? { ...m, toolCalls: [...finalToolCalls] } : m
            ))
          } else if (event.type === 'tool_end') {
            finalToolCalls = finalToolCalls.map(tc =>
              tc.id === event.id ? { ...tc, status: 'done', result: event.result } : tc
            )
            setMessages(prev => prev.map(m =>
              m.id === assistantId ? { ...m, toolCalls: [...finalToolCalls] } : m
            ))
          } else if (event.type === 'error') {
            const errText = (finalContent ? '\n\n' : '') + `⚠️ ${event.message}`
            finalContent += errText
            setMessages(prev => prev.map(m =>
              m.id === assistantId ? { ...m, content: finalContent, streaming: false } : m
            ))
          } else if (event.type === 'done') {
            break
          }
        }
      }

      setMessages(prev => prev.map(m =>
        m.id === assistantId ? { ...m, streaming: false } : m
      ))
      onSessionTitleUpdate?.()

    } catch (e) {
      if (e.name !== 'AbortError') {
        setMessages(prev => prev.map(m =>
          m.id === assistantId
            ? { ...m, content: `⚠️ Connection error: ${e.message}`, streaming: false }
            : m
        ))
      }
    } finally {
      setIsStreaming(false)
      inputRef.current?.focus()
    }
  }, [input, isStreaming, sessionId, onSessionTitleUpdate])

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() }
  }

  // Auto-resize textarea
  const handleInput = (e) => {
    setInput(e.target.value)
    e.target.style.height = 'auto'
    e.target.style.height = Math.min(e.target.scrollHeight, 140) + 'px'
  }

  const isEmpty = messages.length === 0 && !loading

  return (
    <div className="chat-layout">
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
            <p className="header-sub">AI-powered email + calendar agent</p>
          </div>
        </div>
        <div className="chat-header-right">
          <button className="btn-ghost theme-toggle" onClick={onToggleTheme} title="Toggle theme">
            {theme === 'dark' ? '☀️' : '🌙'}
          </button>
        </div>
      </header>

      <main className="chat-messages">
        {loading && (
          <div className="loading-messages">
            <div className="loading-spinner" />
          </div>
        )}

        {isEmpty && (
          <div className="welcome">
            <div className="welcome-icon">✉️</div>
            <h2>How can I help with your emails?</h2>
            <p>I can read, search, send, organize emails and manage your calendar.</p>
            <div className="suggestions">
              {SUGGESTIONS.map(s => (
                <button key={s} className="suggestion-chip" onClick={() => sendMessage(s)}>{s}</button>
              ))}
            </div>
          </div>
        )}

        {messages.map(msg => <MessageBubble key={msg.id} message={msg} />)}
        <div ref={bottomRef} />
      </main>

      <footer className="chat-footer">
        <div className="input-row">
          <textarea
            ref={inputRef}
            className="chat-input"
            placeholder="Ask about your emails or calendar…"
            value={input}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            rows={1}
            disabled={isStreaming}
          />
          <button
            className="send-btn"
            onClick={() => sendMessage()}
            disabled={!input.trim() || isStreaming}
          >
            {isStreaming ? <span className="send-spinner" /> : (
              <svg viewBox="0 0 20 20" fill="currentColor">
                <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" />
              </svg>
            )}
          </button>
        </div>
        <p className="input-hint">Enter to send · Shift+Enter for new line</p>
      </footer>
    </div>
  )
}
