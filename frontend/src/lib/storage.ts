import type { AuthSession } from '../types'

const SESSION_KEY = 'canvex.session'

export const loadSession = (): AuthSession | null => {
  const raw = localStorage.getItem(SESSION_KEY)
  if (!raw) {
    return null
  }
  try {
    return JSON.parse(raw) as AuthSession
  } catch {
    return null
  }
}

export const saveSession = (session: AuthSession) => {
  localStorage.setItem(SESSION_KEY, JSON.stringify(session))
}

export const clearSession = () => {
  localStorage.removeItem(SESSION_KEY)
}
