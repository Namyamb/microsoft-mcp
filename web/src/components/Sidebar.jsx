import { useState, useEffect } from 'react'

function relativeTime(iso) {
  try {
    const d = new Date(iso)
    const now = new Date()
    const diff = now - d
    if (diff < 60000) return 'just now'
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`
    if (diff < 604800000) return `${Math.floor(diff / 86400000)}d ago`
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' })
  } catch { return '' }
}

export default function Sidebar({ activeId, onSelect, onNew, collapsed, onToggle }) {
  const [sessions, setSessions] = useState([])
  const [hoverId, setHoverId] = useState(null)
  const [editId, setEditId] = useState(null)
  const [editTitle, setEditTitle] = useState('')

  useEffect(() => {
    loadSessions()
    const iv = setInterval(loadSessions, 10000)
    return () => clearInterval(iv)
  }, [])

  const loadSessions = async () => {
    try {
      const res = await fetch('/api/sessions')
      const data = await res.json()
      setSessions(data)
    } catch { /* ignore */ }
  }

  const deleteSession = async (e, id) => {
    e.stopPropagation()
    await fetch(`/api/sessions/${id}`, { method: 'DELETE' })
    setSessions(s => s.filter(x => x.id !== id))
    if (activeId === id) onNew()
  }

  const startEdit = (e, session) => {
    e.stopPropagation()
    setEditId(session.id)
    setEditTitle(session.title)
  }

  const saveEdit = async (id) => {
    if (!editTitle.trim()) return
    await fetch(`/api/sessions/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: editTitle.trim() }),
    })
    setSessions(s => s.map(x => x.id === id ? { ...x, title: editTitle.trim() } : x))
    setEditId(null)
  }

  const handleNew = async () => {
    const res = await fetch('/api/sessions', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title: 'New Chat' }) })
    const session = await res.json()
    setSessions(s => [session, ...s])
    onSelect(session.id)
    onNew && onNew()
  }

  // Expose refresh to parent
  Sidebar.refresh = loadSessions

  return (
    <aside className={`sidebar ${collapsed ? 'collapsed' : ''}`}>
      <div className="sidebar-header">
        {!collapsed && <span className="sidebar-title">Chats</span>}
        <button className="sidebar-toggle" onClick={onToggle} title={collapsed ? 'Expand' : 'Collapse'}>
          {collapsed ? '›' : '‹'}
        </button>
      </div>

      {!collapsed && (
        <button className="new-chat-btn" onClick={handleNew}>
          <span>+</span> New Chat
        </button>
      )}
      {collapsed && (
        <button className="new-chat-btn-icon" onClick={handleNew} title="New Chat">+</button>
      )}

      {!collapsed && (
        <div className="session-list">
          {sessions.length === 0 && (
            <p className="no-sessions">No chats yet</p>
          )}
          {sessions.map(s => (
            <div
              key={s.id}
              className={`session-item ${activeId === s.id ? 'active' : ''}`}
              onClick={() => onSelect(s.id)}
              onMouseEnter={() => setHoverId(s.id)}
              onMouseLeave={() => setHoverId(null)}
            >
              {editId === s.id ? (
                <input
                  className="session-edit-input"
                  value={editTitle}
                  autoFocus
                  onChange={e => setEditTitle(e.target.value)}
                  onBlur={() => saveEdit(s.id)}
                  onKeyDown={e => { if (e.key === 'Enter') saveEdit(s.id); if (e.key === 'Escape') setEditId(null) }}
                  onClick={e => e.stopPropagation()}
                />
              ) : (
                <>
                  <div className="session-info">
                    <span className="session-name">{s.title}</span>
                    <span className="session-time">{relativeTime(s.updated_at)}</span>
                  </div>
                  {hoverId === s.id && (
                    <div className="session-actions">
                      <button className="session-action-btn" onClick={e => startEdit(e, s)} title="Rename">✏️</button>
                      <button className="session-action-btn danger" onClick={e => deleteSession(e, s.id)} title="Delete">🗑</button>
                    </div>
                  )}
                </>
              )}
            </div>
          ))}
        </div>
      )}
    </aside>
  )
}
