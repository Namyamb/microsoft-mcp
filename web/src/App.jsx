import { useState, useEffect } from 'react'
import AuthFlow from './components/AuthFlow'
import ChatView from './components/ChatView'

export default function App() {
  const [authStatus, setAuthStatus] = useState('checking') // checking | authenticated | unauthenticated

  useEffect(() => {
    checkAuth()
  }, [])

  const checkAuth = async () => {
    try {
      const res = await fetch('/api/auth/status')
      const data = await res.json()
      setAuthStatus(data.authenticated ? 'authenticated' : 'unauthenticated')
    } catch {
      setAuthStatus('unauthenticated')
    }
  }

  if (authStatus === 'checking') {
    return (
      <div className="loading-screen">
        <div className="loading-spinner" />
        <p>Connecting to Outlook Assistant…</p>
      </div>
    )
  }

  if (authStatus === 'unauthenticated') {
    return <AuthFlow onAuthenticated={() => setAuthStatus('authenticated')} />
  }

  return <ChatView />
}
