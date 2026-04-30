import { useState, useEffect } from 'react'
import AuthFlow from './components/AuthFlow'
import ChatView from './components/ChatView'
import Sidebar from './components/Sidebar'
import NotificationBanner from './components/NotificationBanner'

export default function App() {
  const [authStatus, setAuthStatus] = useState('checking')
  const [activeSessionId, setActiveSessionId] = useState(null)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'dark')

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('theme', theme)
  }, [theme])

  useEffect(() => {
    checkAuth()
  }, [])

  const checkAuth = async () => {
    try {
      const res = await fetch('/api/auth/status')
      const data = await res.json()
      if (data.authenticated) {
        setAuthStatus('authenticated')
        await ensureSession()
      } else {
        setAuthStatus('unauthenticated')
      }
    } catch {
      setAuthStatus('unauthenticated')
    }
  }

  const ensureSession = async () => {
    const saved = localStorage.getItem('active_session_id')
    if (saved) {
      // Verify it still exists
      try {
        const res = await fetch(`/api/sessions/${saved}`)
        if (res.ok) { setActiveSessionId(saved); return }
      } catch { /* fall through */ }
    }
    // Create a new session
    const res = await fetch('/api/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: 'New Chat' }),
    })
    const s = await res.json()
    setActiveSessionId(s.id)
    localStorage.setItem('active_session_id', s.id)
  }

  const handleSelectSession = (id) => {
    setActiveSessionId(id)
    localStorage.setItem('active_session_id', id)
  }

  const handleNewChat = async () => {
    const res = await fetch('/api/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: 'New Chat' }),
    })
    const s = await res.json()
    setActiveSessionId(s.id)
    localStorage.setItem('active_session_id', s.id)
    Sidebar.refresh?.()
  }

  const toggleTheme = () => setTheme(t => t === 'dark' ? 'light' : 'dark')

  if (authStatus === 'checking') {
    return (
      <div className="loading-screen">
        <div className="loading-spinner" />
        <p>Connecting…</p>
      </div>
    )
  }

  if (authStatus === 'unauthenticated') {
    return <AuthFlow onAuthenticated={() => { setAuthStatus('authenticated'); ensureSession() }} />
  }

  return (
    <div className="app-layout">
      <NotificationBanner />
      <Sidebar
        activeId={activeSessionId}
        onSelect={handleSelectSession}
        onNew={handleNewChat}
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(c => !c)}
      />
      <div className="main-area">
        {activeSessionId && (
          <ChatView
            key={activeSessionId}
            sessionId={activeSessionId}
            onSessionTitleUpdate={() => Sidebar.refresh?.()}
            theme={theme}
            onToggleTheme={toggleTheme}
          />
        )}
      </div>
    </div>
  )
}
