import type { ElementStyle, ElementTransform, ElementType } from '../types'

const CLIENT_ID_KEY = 'canvex.client_id'

export type VectorClock = Record<string, number>

export type OfflineOperationType = 'create' | 'update' | 'delete'

export type OfflineElementState = {
  local_id: string
  server_id?: string
  page_id: string
  type: ElementType
  transform: ElementTransform
  style: ElementStyle
  content: Record<string, unknown>
  is_deleted: boolean
  updated_at: string
}

export type OfflineQueueItem = {
  id: string
  client_operation_id: string
  operation: OfflineOperationType
  local_id: string
  element_id?: string
  vector_clock: VectorClock
  queued_at: string
}

const queueKey = (pageId: string) => `canvex.offline_queue.${pageId}`

export const getClientId = () => {
  const existing = localStorage.getItem(CLIENT_ID_KEY)
  if (existing) return existing
  const clientId = crypto.randomUUID()
  localStorage.setItem(CLIENT_ID_KEY, clientId)
  return clientId
}

export const loadOfflineQueue = (pageId: string): OfflineQueueItem[] => {
  const raw = localStorage.getItem(queueKey(pageId))
  if (!raw) return []
  try {
    return JSON.parse(raw) as OfflineQueueItem[]
  } catch {
    return []
  }
}

export const saveOfflineQueue = (pageId: string, queue: OfflineQueueItem[]) => {
  if (queue.length === 0) {
    localStorage.removeItem(queueKey(pageId))
    return
  }
  localStorage.setItem(queueKey(pageId), JSON.stringify(queue))
}

