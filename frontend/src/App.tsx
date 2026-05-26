import { useCallback, useEffect, useMemo, useState } from 'react'

import AuthPanel from './components/AuthPanel'
import CanvasBoard from './components/CanvasBoard'
import Sidebar from './components/Sidebar'
import { createChannel, createPage, getChannel, getMe, listChannels, logout } from './lib/api'
import { clearSession, loadSession, saveSession } from './lib/storage'
import type { AuthSession, ChannelDetail, ChannelListItem, PageSummary } from './types'

const App = () => {
  const [session, setSession] = useState<AuthSession | null>(loadSession())
  const [channels, setChannels] = useState<ChannelListItem[]>([])
  const [selectedChannel, setSelectedChannel] = useState<ChannelDetail | null>(null)
  const [selectedPage, setSelectedPage] = useState<PageSummary | null>(null)
  const [isBooting, setIsBooting] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const handleSelectChannel = useCallback(async (channelId: string) => {
    const detail = await getChannel(channelId)
    setSelectedChannel(detail)
    if (detail.pages.length) {
      setSelectedPage(detail.pages[0])
    } else {
      setSelectedPage(null)
    }
  }, [])

  const refreshChannels = useCallback(async () => {
    const data = await listChannels()
    setChannels(data)
    if (data.length && !selectedChannel) {
      await handleSelectChannel(data[0].id)
    }
  }, [handleSelectChannel, selectedChannel])

  useEffect(() => {
    const boot = async () => {
      if (!session) {
        setIsBooting(false)
        return
      }
      try {
        const user = await getMe()
        const updatedSession = { ...session, user }
        saveSession(updatedSession)
        setSession(updatedSession)
        await refreshChannels()
      } catch {
        clearSession()
        setSession(null)
      } finally {
        setIsBooting(false)
      }
    }
    boot()
  }, [refreshChannels, session])

  useEffect(() => {
    if (!session) return
    refreshChannels().catch(() => setError('Failed to load channels.'))
  }, [refreshChannels, session])

  const handleCreateChannel = async (payload: { name: string; description?: string }) => {
    try {
      const channel = await createChannel(payload)
      setChannels((prev) => [channel, ...prev])
      await handleSelectChannel(channel.id)
    } catch {
      setError('Unable to create channel.')
    }
  }

  const handleCreatePage = async (title: string) => {
    if (!selectedChannel) return
    try {
      const page = await createPage(selectedChannel.id, title)
      const updated = await getChannel(selectedChannel.id)
      setSelectedChannel(updated)
      setSelectedPage(page)
    } catch {
      setError('Unable to create page.')
    }
  }

  const handleLogout = async () => {
    if (!session) return
    await logout(session.refreshToken)
    setSession(null)
    setChannels([])
    setSelectedChannel(null)
    setSelectedPage(null)
  }

  const pageList = useMemo(() => selectedChannel?.pages ?? [], [selectedChannel])

  if (isBooting) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-slate-500">
        Booting Canvex…
      </div>
    )
  }

  if (!session) {
    return <AuthPanel onAuthenticated={(next) => setSession(next)} />
  }

  return (
    <div className="flex h-screen overflow-hidden bg-slate-950 text-slate-100">
      <Sidebar
        user={session.user}
        channels={channels}
        selectedChannel={selectedChannel}
        selectedPage={selectedPage}
        onSelectChannel={handleSelectChannel}
        onCreateChannel={handleCreateChannel}
        onSelectPage={(pageId) => {
          const page = pageList.find((item) => item.id === pageId) ?? null
          setSelectedPage(page)
        }}
        onCreatePage={handleCreatePage}
      />
      <main className="flex flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-slate-800/70 px-6 py-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">
              Channel
            </p>
            <h2 className="text-lg font-semibold text-white">
              {selectedChannel?.name ?? 'No channel selected'}
            </h2>
          </div>
          <div className="flex items-center gap-3">
            {error && <span className="text-sm text-rose-400">{error}</span>}
            <button
              type="button"
              onClick={handleLogout}
              className="rounded-xl border border-slate-800 bg-slate-900/80 px-4 py-2 text-sm text-slate-200 hover:border-slate-600"
            >
              Sign out
            </button>
          </div>
        </header>
        <div className="flex-1">
          <CanvasBoard page={selectedPage} user={session.user} accessToken={session.accessToken} />
        </div>
      </main>
    </div>
  )
}

export default App
