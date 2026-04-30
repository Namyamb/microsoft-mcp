import { useState, useEffect, useRef } from 'react'

function getSenderName(from) {
  if (!from) return 'Someone'
  if (from.emailAddress) return from.emailAddress.name || from.emailAddress.address || 'Someone'
  return 'Someone'
}

export default function NotificationBanner({ onNewEmails }) {
  const [toasts, setToasts] = useState([])
  const esRef = useRef(null)

  useEffect(() => {
    connect()
    return () => esRef.current?.close()
  }, [])

  const connect = () => {
    const es = new EventSource('/api/notifications/stream')
    esRef.current = es

    es.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data)
        if (event.type === 'new_emails') {
          showToast(event)
          onNewEmails && onNewEmails(event)
        }
      } catch { /* ignore */ }
    }

    es.onerror = () => {
      es.close()
      setTimeout(connect, 15000)
    }
  }

  const showToast = (event) => {
    const id = Date.now()
    const first = event.emails?.[0]
    const toast = {
      id,
      count: event.count,
      subject: first?.subject || 'New email',
      sender: getSenderName(first?.from),
    }
    setToasts(t => [...t, toast])
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 6000)
  }

  const dismiss = (id) => setToasts(t => t.filter(x => x.id !== id))

  return (
    <div className="toast-container">
      {toasts.map(toast => (
        <div key={toast.id} className="toast" onClick={() => dismiss(toast.id)}>
          <div className="toast-icon">📬</div>
          <div className="toast-body">
            <div className="toast-title">
              {toast.count > 1 ? `${toast.count} new emails` : 'New email'}
            </div>
            <div className="toast-sub">{toast.sender} — {toast.subject}</div>
          </div>
          <button className="toast-close" onClick={() => dismiss(toast.id)}>✕</button>
        </div>
      ))}
    </div>
  )
}
