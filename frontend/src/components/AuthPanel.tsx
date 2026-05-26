import { useState } from 'react'
import { ArrowRight, Eye, EyeOff, GraduationCap, LoaderCircle, Lock, Mail } from 'lucide-react'

import backgroundUrl from '../assets/canvex-paper-bg.png'
import { login, register } from '../lib/api'
import type { AuthSession } from '../types'

type AuthPanelProps = {
  onAuthenticated: (session: AuthSession) => void
}

const defaultState = { email: '', displayName: '', password: '' }

const AuthPanel = ({ onAuthenticated }: AuthPanelProps) => {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [form, setForm] = useState(defaultState)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [showPassword, setShowPassword] = useState(false)

  const showComingSoon = (feature: string) => {
    setError('')
    setNotice(`${feature} is coming soon.`)
  }

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    setError('')
    setNotice('')
    setIsSubmitting(true)
    try {
      const session =
        mode === 'login'
          ? await login(form.email, form.password)
          : await register(form.email, form.displayName, form.password)
      onAuthenticated(session)
    } catch {
      setError(
        mode === 'register'
          ? 'Check your details. Password must be at least 8 characters.'
          : 'Authentication failed. Please check your details and try again.',
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="auth-notebook min-h-screen text-slate-950">
      <img src={backgroundUrl} alt="" className="auth-notebook-art" aria-hidden="true" />
      <div className="auth-notebook-lines" />
      <div className="paper-margin-line" />

      <main className="auth-ink-login">
        <h1 className="stamped-logo text-center font-reading-serif text-5xl font-normal uppercase leading-none tracking-[0.16em] text-indigo-950/20 sm:text-6xl">
          Canvex
        </h1>
        <p className="mt-2 font-handwriting text-xl text-indigo-800/45">
          collaborative research canvas
        </p>

        <div className="auth-tab-shell mt-9 w-full">
          <div className="grid grid-cols-2">
            <button
              type="button"
              onClick={() => {
                setMode('login')
                setError('')
                setNotice('')
              }}
              className={`auth-tab ${mode === 'login' ? 'active' : ''}`}
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => {
                setMode('register')
                setError('')
                setNotice('')
              }}
              className={`auth-tab ${mode === 'register' ? 'active' : ''}`}
            >
              Create Account
            </button>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="mt-6 w-full space-y-5">
          <div className="ink-field">
            <label className="auth-label" htmlFor="email">
              Email Address
            </label>
            <div className="relative">
              <Mail className="auth-input-icon" size={22} />
              <input
                id="email"
                className="auth-input"
                type="email"
                required
                value={form.email}
                onChange={(event) => setForm((prev) => ({ ...prev, email: event.target.value }))}
                placeholder="researcher@institution.edu"
              />
            </div>
          </div>

          <div className={`auth-register-field ${mode === 'register' ? 'open' : ''}`} aria-hidden={mode !== 'register'}>
            <div className="ink-field">
              <label className="auth-label" htmlFor="display-name">
                Display Name
              </label>
              <div className="relative">
                <GraduationCap className="auth-input-icon" size={22} />
                <input
                  id="display-name"
                  className="auth-input"
                  type="text"
                  required={mode === 'register'}
                  tabIndex={mode === 'register' ? 0 : -1}
                  value={form.displayName}
                  onChange={(event) => setForm((prev) => ({ ...prev, displayName: event.target.value }))}
                  placeholder="Canvas Captain"
                />
              </div>
            </div>
          </div>

          <div className="ink-field">
            <label className="auth-label" htmlFor="password">
              Password
            </label>
            <div className="relative">
              <Lock className="auth-input-icon" size={22} />
              <input
                id="password"
                className="auth-input pr-12"
                type={showPassword ? 'text' : 'password'}
                required
                value={form.password}
                onChange={(event) => setForm((prev) => ({ ...prev, password: event.target.value }))}
                placeholder="••••••••"
              />
              <button
                type="button"
                aria-label={showPassword ? 'Hide password' : 'Show password'}
                className="absolute right-1 top-1/2 -translate-y-1/2 text-slate-500 hover:text-indigo-700"
                onClick={() => setShowPassword((prev) => !prev)}
              >
                {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
              </button>
            </div>
            {mode === 'login' && (
              <div className="pt-2 text-right">
                <button
                  type="button"
                  className="font-handwriting text-lg text-indigo-700 underline decoration-wavy decoration-indigo-400/50"
                  onClick={() => showComingSoon('Password recovery')}
                >
                  Forgot Password?
                </button>
              </div>
            )}
          </div>

          {error && <p key={error} className="auth-feedback-error rounded-lg bg-rose-50/80 px-4 py-2 text-sm font-semibold text-rose-700 backdrop-blur-sm">{error}</p>}
          {notice && <p className="rounded-lg bg-indigo-50/80 px-4 py-2 text-sm font-semibold text-indigo-700 backdrop-blur-sm">{notice}</p>}

          <button type="submit" disabled={isSubmitting} className="auth-submit">
            {isSubmitting ? 'Working...' : mode === 'login' ? 'Continue to Workspace' : 'Create Workspace'}
            {isSubmitting ? <LoaderCircle className="animate-spin" size={18} /> : <ArrowRight size={18} />}
          </button>
        </form>

        <div className="my-5 flex w-full items-center gap-4">
          <div className="h-px flex-1 bg-slate-300/60" />
          <span className="font-reading-serif text-sm italic text-slate-700">or</span>
          <div className="h-px flex-1 bg-slate-300/60" />
        </div>

        <div className="w-full space-y-3">
          <button type="button" className="auth-secondary-action" onClick={() => showComingSoon('Google login')}>
            <span className="text-xl font-bold text-blue-600">G</span>
            Continue with Google
          </button>
          <button type="button" className="auth-secondary-action" onClick={() => showComingSoon('Institutional SSO')}>
            <GraduationCap size={18} />
            Institutional Login (SSO)
          </button>
        </div>
      </main>
    </div>
  )
}

export default AuthPanel
