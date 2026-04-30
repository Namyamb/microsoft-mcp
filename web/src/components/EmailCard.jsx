function formatDate(dateStr) {
  if (!dateStr) return ''
  try {
    const d = new Date(dateStr)
    const now = new Date()
    const diffMs = now - d
    const diffDays = Math.floor(diffMs / 86400000)
    if (diffDays === 0) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    if (diffDays === 1) return 'Yesterday'
    if (diffDays < 7) return d.toLocaleDateString([], { weekday: 'short' })
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' })
  } catch {
    return dateStr
  }
}

function getSenderName(from) {
  if (!from) return 'Unknown'
  if (from.emailAddress) {
    return from.emailAddress.name || from.emailAddress.address || 'Unknown'
  }
  if (typeof from === 'string') return from
  return 'Unknown'
}

function getSenderEmail(from) {
  if (!from) return ''
  if (from.emailAddress) return from.emailAddress.address || ''
  return ''
}

export default function EmailCard({ email, index }) {
  if (!email || typeof email !== 'object') return null

  const isRead = email.isRead !== false
  const isFlagged = email.flag?.flagStatus === 'flagged'
  const hasAttachments = email.hasAttachments
  const importance = email.importance

  return (
    <div className={`email-card ${!isRead ? 'unread' : ''}`}>
      {index !== undefined && (
        <span className="email-index">{index + 1}</span>
      )}
      <div className="email-card-header">
        <div className="email-sender-row">
          <span className="email-sender">{getSenderName(email.from)}</span>
          {isFlagged && <span className="email-flag" title="Flagged">🚩</span>}
          {importance === 'high' && <span className="email-important" title="High importance">!</span>}
          {hasAttachments && <span className="email-attach" title="Has attachments">📎</span>}
          <span className="email-date">{formatDate(email.receivedDateTime)}</span>
        </div>
        <div className="email-subject">
          {!isRead && <span className="unread-dot" />}
          {email.subject || '(No subject)'}
        </div>
        {getSenderEmail(email.from) && (
          <div className="email-address">{getSenderEmail(email.from)}</div>
        )}
      </div>
      {email.bodyPreview && (
        <div className="email-preview">{email.bodyPreview.slice(0, 160)}{email.bodyPreview.length > 160 ? '…' : ''}</div>
      )}
      {email.body?.content && !email.bodyPreview && (
        <div className="email-preview">{email.body.content.replace(/<[^>]+>/g, '').slice(0, 160)}…</div>
      )}
    </div>
  )
}
