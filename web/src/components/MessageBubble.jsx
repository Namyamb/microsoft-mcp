import { useRef, useCallback } from 'react'
import ToolCallBadge from './ToolCallBadge'
import EmailCard from './EmailCard'

function extractEmailsFromResult(result) {
  if (!result) return null
  if (result.success === false) return null
  const data = result.data
  if (!data) return null
  // List of emails
  if (Array.isArray(data)) {
    return data.filter(e => e && e.subject !== undefined)
  }
  // Paged result {emails: [...]}
  if (data.emails && Array.isArray(data.emails)) {
    return data.emails
  }
  // Single email object
  if (data.subject !== undefined || data.id !== undefined) {
    return [data]
  }
  return null
}

// Graph message IDs: base64url, 40+ chars, no spaces
const ID_RE = /([A-Za-z0-9+/=_\-]{40,})/g

function wrapIds(html) {
  // Only replace outside of HTML tags by splitting on < > boundaries.
  return html.replace(/>([^<]+)</g, (_, text) => {
    const replaced = text.replace(ID_RE, id =>
      `<span class="msg-id-chip" data-copy="${escapeHtml(id)}">`
      + `<span class="msg-id-text">${escapeHtml(id)}</span>`
      + `<button class="msg-id-copy" data-copy="${escapeHtml(id)}" title="Copy ID">`
      + `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" width="12" height="12"><rect x="5" y="5" width="8" height="9" rx="1.5"/><path d="M3 11V3a1.5 1.5 0 0 1 1.5-1.5H11"/></svg>`
      + `</button></span>`
    )
    return `>${replaced}<`
  })
}

function renderMarkdown(text) {
  const base = text
    .replace(/```[\s\S]*?```/g, m => `<pre><code>${escapeHtml(m.slice(3, -3))}</code></pre>`)
    .replace(/`([^`]+)`/g, (_, c) => `<code>${escapeHtml(c)}</code>`)
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/^[-*] (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br/>')
  return wrapIds(base)
}

function escapeHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

export default function MessageBubble({ message }) {
  const { role, content, toolCalls, streaming, stopped } = message
  const bubbleRef = useRef(null)

  const handleBubbleClick = useCallback((e) => {
    const btn = e.target.closest('.msg-id-copy')
    if (!btn) return
    const id = btn.dataset.copy
    if (!id) return
    navigator.clipboard.writeText(id).then(() => {
      btn.classList.add('copied')
      setTimeout(() => btn.classList.remove('copied'), 1800)
    })
  }, [])

  if (role === 'user') {
    return (
      <div className="msg-row user">
        <div className="msg-bubble user">
          <p>{content}</p>
        </div>
      </div>
    )
  }

  // Assistant message
  return (
    <div className="msg-row assistant">
      <div className="msg-avatar">
        <svg viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect width="32" height="32" rx="8" fill="#0078d4" />
          <path d="M7 12l9 6 9-6" stroke="white" strokeWidth="2" strokeLinecap="round" />
          <rect x="7" y="10" width="18" height="14" rx="2" stroke="white" strokeWidth="2" fill="none" />
        </svg>
      </div>

      <div className="msg-content">
        {/* Tool calls */}
        {toolCalls && toolCalls.length > 0 && (
          <div className="tool-calls">
            {toolCalls.map((tc) => (
              <ToolCallBadge
                key={tc.id}
                name={tc.name}
                status={tc.status}
                result={tc.result}
              />
            ))}
          </div>
        )}

        {/* Email cards from tool results */}
        {toolCalls && toolCalls.map((tc) => {
          if (tc.status !== 'done') return null
          const emails = extractEmailsFromResult(tc.result)
          if (!emails || emails.length === 0) return null
          return (
            <div key={`emails-${tc.id}`} className="email-cards">
              {emails.map((email, i) => (
                <EmailCard key={email.id || i} email={email} index={i} />
              ))}
            </div>
          )
        })}

        {/* Text content */}
        {content && (
          <div
            ref={bubbleRef}
            className="msg-bubble assistant"
            onClick={handleBubbleClick}
            dangerouslySetInnerHTML={{ __html: '<p>' + renderMarkdown(content) + '</p>' }}
          />
        )}

        {/* Streaming cursor */}
        {streaming && !content && (
          <div className="msg-bubble assistant typing">
            <span className="typing-dot" />
            <span className="typing-dot" />
            <span className="typing-dot" />
          </div>
        )}

        {/* User stopped generation — ChatGPT-style muted notice (not inline markdown) */}
        {stopped && (
          <div className="msg-stopped" role="status">
            <span className="msg-stopped-icon" aria-hidden>⏹</span>
            <span className="msg-stopped-text">
              {content?.trim()
                ? 'Generation stopped. The reply above is partial.'
                : 'Generation stopped before any reply was produced.'}
            </span>
          </div>
        )}
      </div>
    </div>
  )
}
