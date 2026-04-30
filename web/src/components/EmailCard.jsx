import { useState } from 'react'

function formatDate(dateStr) {
  if (!dateStr) return ''
  try {
    const d = new Date(dateStr)
    const now = new Date()
    const diffDays = Math.floor((now - d) / 86400000)
    if (diffDays === 0) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    if (diffDays === 1) return 'Yesterday'
    if (diffDays < 7) return d.toLocaleDateString([], { weekday: 'short' })
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' })
  } catch { return dateStr }
}

function getSenderName(from) {
  if (!from) return 'Unknown'
  if (from.emailAddress) return from.emailAddress.name || from.emailAddress.address || 'Unknown'
  if (typeof from === 'string') return from
  return 'Unknown'
}

function getSenderEmail(from) {
  if (!from) return ''
  if (from.emailAddress) return from.emailAddress.address || ''
  return ''
}

async function doEmailAction(emailId, action) {
  const res = await fetch('/api/email/action', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email_id: emailId, action }),
  })
  if (!res.ok) throw new Error(`Action failed: ${res.status}`)
  return res.json()
}

export default function EmailCard({ email, index }) {
  const [state, setState] = useState({
    isRead: email?.isRead !== false,
    isFlagged: email?.flag?.flagStatus === 'flagged',
    isArchived: false,
    isDeleted: false,
    busy: null,
    error: null,
  })
  const [confirmDelete, setConfirmDelete] = useState(false)

  if (!email || typeof email !== 'object') return null
  if (state.isDeleted) return null

  const act = async (action, update) => {
    setState(s => ({ ...s, busy: action, error: null }))
    try {
      await doEmailAction(email.id, action)
      setState(s => ({ ...s, busy: null, ...update }))
    } catch (e) {
      setState(s => ({ ...s, busy: null, error: e.message }))
      setTimeout(() => setState(s => ({ ...s, error: null })), 3000)
    }
  }

  const handleArchive = () => act('archive', { isArchived: true })
  const handleFlag = () => act(state.isFlagged ? 'unflag' : 'flag', { isFlagged: !state.isFlagged })
  const handleRead = () => act(state.isRead ? 'mark_unread' : 'mark_read', { isRead: !state.isRead })
  const handleDelete = async () => {
    if (!confirmDelete) { setConfirmDelete(true); setTimeout(() => setConfirmDelete(false), 3000); return }
    await act('delete', { isDeleted: true })
    setConfirmDelete(false)
  }

  if (state.isArchived) {
    return (
      <div className="email-card archived-note">
        <span>📦 Email archived</span>
      </div>
    )
  }

  const { isRead, isFlagged } = state
  const importance = email.importance
  const hasAttachments = email.hasAttachments

  return (
    <div className={`email-card ${!isRead ? 'unread' : ''}`}>
      {index !== undefined && <span className="email-index">{index + 1}</span>}

      <div className="email-card-header">
        <div className="email-sender-row">
          <span className="email-sender">{getSenderName(email.from)}</span>
          {isFlagged && <span className="email-flag">🚩</span>}
          {importance === 'high' && <span className="email-important">!</span>}
          {hasAttachments && <span className="email-attach">📎</span>}
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
        <div className="email-preview">
          {email.bodyPreview.slice(0, 160)}{email.bodyPreview.length > 160 ? '…' : ''}
        </div>
      )}

      {state.error && <div className="email-action-error">{state.error}</div>}

      {/* Action buttons */}
      {email.id && (
        <div className="email-actions">
          <button
            className="email-action-btn"
            onClick={handleRead}
            disabled={!!state.busy}
            title={isRead ? 'Mark unread' : 'Mark read'}
          >
            {state.busy === 'mark_read' || state.busy === 'mark_unread' ? '…' : isRead ? '◯' : '●'}
            <span>{isRead ? 'Unread' : 'Read'}</span>
          </button>

          <button
            className={`email-action-btn ${isFlagged ? 'active-flag' : ''}`}
            onClick={handleFlag}
            disabled={!!state.busy}
            title={isFlagged ? 'Remove flag' : 'Flag'}
          >
            {state.busy === 'flag' || state.busy === 'unflag' ? '…' : '🚩'}
            <span>{isFlagged ? 'Unflag' : 'Flag'}</span>
          </button>

          <button
            className="email-action-btn"
            onClick={handleArchive}
            disabled={!!state.busy}
            title="Archive"
          >
            {state.busy === 'archive' ? '…' : '📦'}
            <span>Archive</span>
          </button>

          <button
            className={`email-action-btn danger ${confirmDelete ? 'confirm' : ''}`}
            onClick={handleDelete}
            disabled={!!state.busy}
            title={confirmDelete ? 'Click again to confirm delete' : 'Delete'}
          >
            {state.busy === 'delete' ? '…' : '🗑'}
            <span>{confirmDelete ? 'Confirm?' : 'Delete'}</span>
          </button>
        </div>
      )}
    </div>
  )
}
