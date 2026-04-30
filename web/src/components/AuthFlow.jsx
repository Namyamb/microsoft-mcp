import { useState, useEffect, useRef } from 'react'

export default function AuthFlow({ onAuthenticated }) {
  const [step, setStep] = useState('idle')   // idle | loading | waiting | success | error
  const [flow, setFlow] = useState(null)
  const [error, setError] = useState('')
  const [countdown, setCountdown] = useState(0)
  const [copied, setCopied] = useState(false)
  const pollRef = useRef(null)
  const timerRef = useRef(null)

  const startAuth = async () => {
    setStep('loading')
    setError('')
    try {
      const res = await fetch('/api/auth/start', { method: 'POST' })
      const data = await res.json()

      if (data.already_authenticated) {
        setStep('success')
        setTimeout(onAuthenticated, 1000)
        return
      }

      setFlow(data)
      setCountdown(data.expires_in || 900)
      setStep('waiting')
      startPolling()
      startCountdown()
    } catch (e) {
      setStep('error')
      setError('Failed to connect to the server. Is it running?')
    }
  }

  const startPolling = () => {
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch('/api/auth/poll')
        const data = await res.json()
        if (data.status === 'completed') {
          clearInterval(pollRef.current)
          clearInterval(timerRef.current)
          setStep('success')
          setTimeout(onAuthenticated, 1200)
        } else if (data.status === 'error') {
          clearInterval(pollRef.current)
          clearInterval(timerRef.current)
          setStep('error')
          setError(data.error || 'Authentication failed.')
        }
      } catch { /* ignore */ }
    }, 2500)
  }

  const startCountdown = () => {
    timerRef.current = setInterval(() => {
      setCountdown(c => {
        if (c <= 1) {
          clearInterval(timerRef.current)
          clearInterval(pollRef.current)
          setStep('error')
          setError('The sign-in code expired. Please try again.')
          return 0
        }
        return c - 1
      })
    }, 1000)
  }

  useEffect(() => {
    return () => {
      clearInterval(pollRef.current)
      clearInterval(timerRef.current)
    }
  }, [])

  const copyCode = () => {
    if (flow?.user_code) {
      navigator.clipboard.writeText(flow.user_code)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const fmtCountdown = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`

  return (
    <div className="auth-screen">
      <div className="auth-card">
        <div className="auth-logo">
          <svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect width="48" height="48" rx="10" fill="#0078d4" />
            <path d="M8 16l16 11 16-11" stroke="white" strokeWidth="2.5" strokeLinecap="round" />
            <rect x="8" y="14" width="32" height="22" rx="3" stroke="white" strokeWidth="2.5" fill="none" />
          </svg>
        </div>
        <h1>Outlook Assistant</h1>
        <p className="auth-subtitle">Your AI-powered email agent</p>

        {step === 'idle' && (
          <>
            <p className="auth-desc">
              Sign in with your Microsoft account to get started. You'll see a device code to enter on Microsoft's website.
            </p>
            <button className="btn-primary btn-large" onClick={startAuth}>
              Sign in to Outlook
            </button>
          </>
        )}

        {step === 'loading' && (
          <div className="auth-loading">
            <div className="loading-spinner" />
            <p>Starting sign-in flow…</p>
          </div>
        )}

        {step === 'waiting' && flow && (
          <div className="auth-waiting">
            <p className="auth-instruction">
              1. Open the link below (or go to <strong>microsoft.com/devicelogin</strong>)
            </p>
            <a
              href={flow.verification_uri}
              target="_blank"
              rel="noreferrer"
              className="btn-secondary"
            >
              Open Microsoft Sign-In ↗
            </a>

            <p className="auth-instruction" style={{ marginTop: '1.5rem' }}>
              2. Enter this code when prompted:
            </p>
            <div className="device-code-box">
              <span className="device-code">{flow.user_code}</span>
              <button className="copy-btn" onClick={copyCode} title="Copy code">
                {copied ? '✓ Copied' : 'Copy'}
              </button>
            </div>

            <div className="auth-status-row">
              <div className="auth-pulse" />
              <span>Waiting for you to sign in…</span>
              <span className="countdown">{fmtCountdown(countdown)}</span>
            </div>
          </div>
        )}

        {step === 'success' && (
          <div className="auth-success">
            <div className="success-icon">✓</div>
            <p>Signed in successfully!</p>
          </div>
        )}

        {step === 'error' && (
          <div className="auth-error">
            <p className="error-msg">{error}</p>
            <button className="btn-primary" onClick={() => { setStep('idle'); setError('') }}>
              Try Again
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
