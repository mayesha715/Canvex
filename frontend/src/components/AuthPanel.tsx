import { useState } from 'react'
import { LogIn, Sparkles } from 'lucide-react'

import { login, register } from '../lib/api'
import type { AuthSession } from '../types'

type AuthPanelProps = {
  onAuthenticated: (session: AuthSession) => void
}

const defaultState = { email: '', displayName: '', password: '' }

const features = [
  'Real-time multiuser whiteboards',
  'Append-only audit trail',
  'SQL-first JSONB canvas storage',
  'Presence + live cursor streaming',
]

const AuthPanel = ({ onAuthenticated }: AuthPanelProps) => {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [form, setForm] = useState(defaultState)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    setError('')
    setIsSubmitting(true)
    try {
      const session =
        mode === 'login'
          ? await login(form.email, form.password)
          : await register(form.email, form.displayName, form.password)
      onAuthenticated(session)
    } catch {
      setError('Authentication failed. Please check your details and try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-stretch bg-slate-950 text-slate-100">
      <aside className="hidden w-1/2 flex-col justify-between bg-gradient-to-br from-slate-900 via-slate-900 to-indigo-900/60 p-12 lg:flex">
        <div>
          <div className="flex items-center gap-3 text-sm font-semibold uppercase tracking-[0.3em] text-slate-400">
            <Sparkles size={18} />
            Canvex
          </div>
          <h1 className="mt-6 text-4xl font-semibold leading-tight text-white">
            Collaborative thinking in real time.
          </h1>
          <p className="mt-4 max-w-md text-slate-300">
            A fast, SQL-native whiteboard with auditability, live presence, and a
            modern canvas workflow built for DBMS demos.
          </p>
        </div>
        <div className="space-y-4">
          {features.map((feature) => (
            <div key={feature} className="flex items-center gap-3 text-sm text-slate-300">
              <span className="h-2 w-2 rounded-full bg-indigo-400"></span>
              {feature}
            </div>
          ))}
        </div>
      </aside>

      <main className="flex flex-1 items-center justify-center px-6 py-12">
        <div className="glass-panel w-full max-w-md rounded-3xl p-8">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">
                {mode === 'login' ? 'Welcome back' : 'New workspace'}
              </p>
              <h2 className="mt-3 text-2xl font-semibold text-white">
                {mode === 'login' ? 'Sign in to Canvex' : 'Create your account'}
              </h2>
            </div>
            <LogIn className="text-indigo-300" size={28} />
          </div>

          <form onSubmit={handleSubmit} className="mt-8 space-y-5">
            <div>
              <label className="form-label">Email</label>
              <input
                className="form-input mt-2"
                type="email"
                required
                value={form.email}
                onChange={(event) => setForm((prev) => ({ ...prev, email: event.target.value }))}
                placeholder="you@canvex.local"
              />
            </div>
            {mode === 'register' && (
              <div>
                <label className="form-label">Display name</label>
                <input
                  className="form-input mt-2"
                  type="text"
                  required
                  value={form.displayName}
                  onChange={(event) => setForm((prev) => ({ ...prev, displayName: event.target.value }))}
                  placeholder="Canvas Captain"
                />
              </div>
            )}
            <div>
              <label className="form-label">Password</label>
              <input
                className="form-input mt-2"
                type="password"
                required
                value={form.password}
                onChange={(event) => setForm((prev) => ({ ...prev, password: event.target.value }))}
                placeholder="••••••••"
              />
            </div>

            {error && <p className="text-sm text-rose-400">{error}</p>}

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full rounded-xl bg-indigo-500 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-500/30 hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-70"
            >
              {isSubmitting ? 'Working...' : mode === 'login' ? 'Sign in' : 'Create account'}
            </button>
          </form>

          <div className="mt-6 text-center text-sm text-slate-400">
            {mode === 'login' ? (
              <button type="button" onClick={() => setMode('register')} className="text-indigo-300">
                New here? Create an account
              </button>
            ) : (
              <button type="button" onClick={() => setMode('login')} className="text-indigo-300">
                Already have an account? Sign in
              </button>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}

export default AuthPanel
