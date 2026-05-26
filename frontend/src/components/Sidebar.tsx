import { Plus, SquarePen } from 'lucide-react'
import { useMemo, useState } from 'react'

import type { ChannelDetail, ChannelListItem, PageSummary, User } from '../types'

type SidebarProps = {
  user: User
  channels: ChannelListItem[]
  selectedChannel?: ChannelDetail | null
  selectedPage?: PageSummary | null
  onSelectChannel: (channelId: string) => void
  onCreateChannel: (payload: { name: string; description?: string }) => void
  onSelectPage: (pageId: string) => void
  onCreatePage: (title: string) => void
}

const Sidebar = ({
  user,
  channels,
  selectedChannel,
  selectedPage,
  onSelectChannel,
  onCreateChannel,
  onSelectPage,
  onCreatePage,
}: SidebarProps) => {
  const [newChannelName, setNewChannelName] = useState('')
  const [newChannelDescription, setNewChannelDescription] = useState('')
  const [newPageTitle, setNewPageTitle] = useState('')

  const channelRole = selectedChannel?.role?.toUpperCase() ?? 'VIEWER'
  const membersCount = selectedChannel?.members.length ?? 0

  const sortedPages = useMemo(() => {
    if (!selectedChannel) return []
    return [...selectedChannel.pages].sort((a, b) => a.order_index - b.order_index)
  }, [selectedChannel])

  return (
    <aside className="glass-panel flex h-full w-80 flex-col gap-6 border-r border-slate-800/80 p-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">Workspace</p>
        <h1 className="mt-2 text-2xl font-semibold text-white">Canvex</h1>
        <p className="mt-1 text-sm text-slate-400">Realtime SQL whiteboard</p>
      </div>

      <div className="rounded-2xl border border-slate-800/70 bg-slate-900/70 p-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-semibold text-white">{user.display_name}</p>
            <p className="text-xs text-slate-400">{user.email}</p>
          </div>
          <span className="chip">{channelRole}</span>
        </div>
        {selectedChannel && (
          <div className="mt-3 flex items-center gap-2 text-xs text-slate-400">
            <span>{membersCount} members</span>
            <span>•</span>
            <span>{selectedChannel.pages.length} pages</span>
          </div>
        )}
      </div>

      <section>
        <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">
          Channels
        </div>
        <div className="mt-3 space-y-2">
          {channels.map((channel) => (
            <button
              key={channel.id}
              type="button"
              onClick={() => onSelectChannel(channel.id)}
              className={`flex w-full items-center justify-between rounded-xl border px-3 py-2 text-left text-sm ${
                selectedChannel?.id === channel.id
                  ? 'border-indigo-400/60 bg-indigo-500/10 text-white'
                  : 'border-slate-800/70 bg-slate-900/60 text-slate-300 hover:border-slate-700'
              }`}
            >
              <span className="font-medium">{channel.name}</span>
              <span className="text-xs text-slate-400">{channel.role}</span>
            </button>
          ))}
        </div>

        <div className="mt-4 space-y-2">
          <input
            className="form-input"
            placeholder="New channel"
            value={newChannelName}
            onChange={(event) => setNewChannelName(event.target.value)}
          />
          <input
            className="form-input"
            placeholder="Description (optional)"
            value={newChannelDescription}
            onChange={(event) => setNewChannelDescription(event.target.value)}
          />
          <button
            type="button"
            onClick={() => {
              if (!newChannelName.trim()) return
              const description = newChannelDescription.trim()
              onCreateChannel({ name: newChannelName.trim(), description: description || undefined })
              setNewChannelName('')
              setNewChannelDescription('')
            }}
            className="toolbar-button w-full justify-center"
          >
            <Plus size={16} />
            Create channel
          </button>
        </div>
      </section>

      <section className="flex-1">
        <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">
          Pages
        </div>
        <div className="mt-3 space-y-2">
          {sortedPages.length === 0 && (
            <p className="text-sm text-slate-500">Select a channel to see pages.</p>
          )}
          {sortedPages.map((page) => (
            <button
              key={page.id}
              type="button"
              onClick={() => onSelectPage(page.id)}
              className={`flex w-full items-center justify-between rounded-xl border px-3 py-2 text-left text-sm ${
                selectedPage?.id === page.id
                  ? 'border-indigo-400/60 bg-indigo-500/10 text-white'
                  : 'border-slate-800/70 bg-slate-900/60 text-slate-300 hover:border-slate-700'
              }`}
            >
              <span className="font-medium">{page.title}</span>
              <SquarePen size={14} className="text-slate-500" />
            </button>
          ))}
        </div>

        {selectedChannel && (
          <div className="mt-4 space-y-2">
            <input
              className="form-input"
              placeholder="New page title"
              value={newPageTitle}
              onChange={(event) => setNewPageTitle(event.target.value)}
            />
            <button
              type="button"
              onClick={() => {
                if (!newPageTitle.trim()) return
                onCreatePage(newPageTitle.trim())
                setNewPageTitle('')
              }}
              className="toolbar-button w-full justify-center"
            >
              <Plus size={16} />
              Create page
            </button>
          </div>
        )}
      </section>
    </aside>
  )
}

export default Sidebar
