import { BookOpen, Folder, Plus, SquarePen, UserRound } from 'lucide-react'
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
    <aside className="workspace-sidebar flex h-full w-80 flex-col gap-6 p-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">Notebook Index</p>
        <h1 className="mt-2 font-reading-serif text-3xl uppercase tracking-[0.16em] text-indigo-950/20">Canvex</h1>
        <p className="mt-1 text-sm text-slate-500">Realtime research pages</p>
      </div>

      <div className="workspace-user-strip">
        <div className="flex items-center justify-between">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-indigo-700">
              <UserRound size={17} />
            </div>
            <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-slate-900">{user.display_name}</p>
            <p className="truncate text-xs text-slate-400">{user.email}</p>
            </div>
          </div>
          <span className="workspace-chip">{channelRole}</span>
        </div>
        {selectedChannel && (
          <div className="mt-3 flex items-center gap-2 text-xs text-slate-500">
            <span>{membersCount} members</span>
            <span>•</span>
            <span>{selectedChannel.pages.length} pages</span>
          </div>
        )}
      </div>

      <section>
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
          <Folder size={14} />
          Channels
        </div>
        <div className="mt-3 space-y-2">
          {channels.map((channel) => (
            <button
              key={channel.id}
              type="button"
              onClick={() => onSelectChannel(channel.id)}
              className={`workspace-list-item ${
                selectedChannel?.id === channel.id
                  ? 'active'
                  : ''
              }`}
            >
              <span className="font-medium">{channel.name}</span>
              <span className="text-xs text-slate-400">{channel.role}</span>
            </button>
          ))}
        </div>

        <div className="mt-4 space-y-2">
          <input
            className="workspace-input"
            placeholder="New channel"
            value={newChannelName}
            onChange={(event) => setNewChannelName(event.target.value)}
          />
          <input
            className="workspace-input"
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
            className="workspace-action-button w-full justify-center"
          >
            <Plus size={16} />
            Create channel
          </button>
        </div>
      </section>

      <section className="flex-1">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
          <BookOpen size={14} />
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
              className={`workspace-list-item ${
                selectedPage?.id === page.id
                  ? 'active'
                  : ''
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
              className="workspace-input"
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
              className="workspace-action-button w-full justify-center"
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
