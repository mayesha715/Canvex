import { Canvas, Ellipse, FabricObject, Line, Polyline, Rect, Textbox } from 'fabric'
import {
  Brush,
  Circle,
  Eraser,
  Highlighter,
  Image,
  Move,
  PenLine,
  RectangleHorizontal,
  Redo2,
  Sparkles,
  StickyNote,
  Text,
  Undo2,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { getPresenceCount, listElements } from '../lib/api'
import { colorFromId } from '../lib/colors'
import type { Element, ElementType, PageSummary, User } from '../types'

type Tool = 'select' | 'rect' | 'ellipse' | 'text' | 'sticky'

type CanvasObject = FabricObject & {
  elementId?: string
  canvexType?: ElementType
  isRemote?: boolean
  localCreateId?: string
  pendingSync?: boolean
}

type CursorState = {
  userId: string
  displayName: string
  color: string
  x: number
  y: number
}

type CanvasBoardProps = {
  page: PageSummary | null
  user: User
  accessToken: string
}

const TOOL_LABELS: Record<Tool, string> = {
  select: 'Select',
  rect: 'Rectangle',
  ellipse: 'Ellipse',
  text: 'Text',
  sticky: 'Sticky Note',
}

const DEFAULT_RECT = { width: 140, height: 90 }
const DEFAULT_ELLIPSE = { rx: 60, ry: 40 }

const CanvasBoard = ({ page, user, accessToken }: CanvasBoardProps) => {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const fabricRef = useRef<Canvas | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const objectsById = useRef<Map<string, CanvasObject>>(new Map())
  const pendingCreates = useRef<Map<string, CanvasObject>>(new Map())
  const textUpdateTimers = useRef<Map<string, number>>(new Map())
  const applyingRemote = useRef(false)
  const activeToolRef = useRef<Tool>('select')
  const pageRef = useRef<PageSummary | null>(null)
  const seqRef = useRef(0)
  const clientIdRef = useRef(crypto.randomUUID())
  const cursorThrottleRef = useRef<number | null>(null)
  const [tool, setTool] = useState<Tool>('select')
  const [connectionState, setConnectionState] = useState<'connecting' | 'connected' | 'disconnected'>(
    'disconnected',
  )
  const [cursors, setCursors] = useState<Record<string, CursorState>>({})
  const [presenceCount, setPresenceCount] = useState(0)
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const [strokeColor, setStrokeColor] = useState('#0f172a')
  const [isAiOpen, setIsAiOpen] = useState(false)
  const [isLoadingPage, setIsLoadingPage] = useState(false)
  const strokeColorRef = useRef(strokeColor)

  const cursorColor = useMemo(() => colorFromId(user.id), [user.id])

  useEffect(() => {
    pageRef.current = page
  }, [page])

  useEffect(() => {
    strokeColorRef.current = strokeColor
  }, [strokeColor])

  const sendMessage = useCallback((payload: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(payload))
    }
  }, [])

  const nextVectorClock = useCallback(() => {
    seqRef.current += 1
    return { [clientIdRef.current]: seqRef.current }
  }, [])

  const toTransform = useCallback((obj: CanvasObject) => ({
    x: obj.left ?? 0,
    y: obj.top ?? 0,
    scaleX: obj.scaleX ?? 1,
    scaleY: obj.scaleY ?? 1,
    rotation: obj.angle ?? 0,
  }), [])

  const toStyle = useCallback((obj: CanvasObject) => ({
    stroke: obj.stroke as string | undefined,
    fill: obj.fill as string | undefined,
    strokeWidth: obj.strokeWidth ?? 2,
  }), [])

  const toContent = useCallback((obj: CanvasObject) => {
    if (obj.type === 'textbox') {
      return { text: (obj as Textbox).text ?? '' }
    }
    if (obj.type === 'polyline') {
      return { points: (obj as Polyline).points ?? [] }
    }
    if (obj.type === 'line') {
      const line = obj as Line
      return { points: [line.x1 ?? 0, line.y1 ?? 0, line.x2 ?? 0, line.y2 ?? 0] }
    }
    return {}
  }, [])

  const resolveElementType = useCallback((obj: CanvasObject): ElementType => {
    if (obj.canvexType) return obj.canvexType
    switch (obj.type) {
      case 'rect':
        return 'rect'
      case 'ellipse':
        return 'ellipse'
      case 'textbox':
        return 'text'
      case 'polyline':
        return 'stroke'
      case 'line':
        return 'arrow'
      default:
        return 'rect'
    }
  }, [])

  const makeObject = useCallback((element: Element): CanvasObject | null => {
    const base = {
      left: element.transform.x,
      top: element.transform.y,
      scaleX: element.transform.scaleX,
      scaleY: element.transform.scaleY,
      angle: element.transform.rotation,
      stroke: element.style.stroke ?? '#111827',
      strokeWidth: element.style.strokeWidth ?? 2,
      fill: element.style.fill ?? 'transparent',
      selectable: true,
      hasControls: true,
      hasBorders: true,
    }

    switch (element.type) {
      case 'rect': {
        const width = Number(element.content.width ?? DEFAULT_RECT.width)
        const height = Number(element.content.height ?? DEFAULT_RECT.height)
        return new Rect({ ...base, width, height }) as CanvasObject
      }
      case 'ellipse': {
        const rx = Number(element.content.rx ?? DEFAULT_ELLIPSE.rx)
        const ry = Number(element.content.ry ?? DEFAULT_ELLIPSE.ry)
        return new Ellipse({ ...base, rx, ry }) as CanvasObject
      }
      case 'text':
      case 'math':
      case 'sticky': {
        const text = String(element.content.text ?? 'Text')
        const textbox = new Textbox(text, {
          ...base,
          width: Number(element.content.width ?? 240),
          fontSize: Number(element.content.fontSize ?? 20),
          fill: element.style.fill ?? '#e2e8f0',
          stroke: element.style.stroke ?? '#0f172a',
        })
        return textbox as CanvasObject
      }
      case 'stroke': {
        const rawPoints = (element.content.points as Array<{ x: number; y: number } | number[]>) ?? []
        const points = rawPoints.map((point) =>
          Array.isArray(point) ? { x: point[0] ?? 0, y: point[1] ?? 0 } : point,
        )
        return new Polyline(points, { ...base, fill: 'transparent' }) as CanvasObject
      }
      case 'arrow': {
        const points = (element.content.points as number[]) ?? [0, 0, 120, 0]
        const linePoints: [number, number, number, number] = [
          points[0] ?? 0,
          points[1] ?? 0,
          points[2] ?? 120,
          points[3] ?? 0,
        ]
        return new Line(linePoints, { ...base, fill: 'transparent' }) as CanvasObject
      }
      default:
        return null
    }
  }, [])

  const addElementToCanvas = useCallback((element: Element) => {
    if (!fabricRef.current) return
    const obj = makeObject(element)
    if (!obj) return
    obj.elementId = element.id
    obj.canvexType = element.type
    obj.isRemote = true
    applyingRemote.current = true
    fabricRef.current.add(obj)
    applyingRemote.current = false
    obj.isRemote = false
    objectsById.current.set(element.id, obj)
  }, [makeObject])

  const updateElementOnCanvas = useCallback((element: Element) => {
    const obj = objectsById.current.get(element.id)
    if (!obj) {
      addElementToCanvas(element)
      return
    }
    obj.set({
      left: element.transform.x,
      top: element.transform.y,
      scaleX: element.transform.scaleX,
      scaleY: element.transform.scaleY,
      angle: element.transform.rotation,
      stroke: element.style.stroke ?? obj.stroke,
      strokeWidth: element.style.strokeWidth ?? obj.strokeWidth,
      fill: element.style.fill ?? obj.fill,
    })
    if (obj.type === 'textbox') {
      ;(obj as Textbox).text = String(element.content.text ?? '')
    }
    obj.setCoords()
    fabricRef.current?.renderAll()
  }, [addElementToCanvas])

  const removeElementFromCanvas = useCallback((elementId: string) => {
    const obj = objectsById.current.get(elementId)
    if (!obj || !fabricRef.current) return
    applyingRemote.current = true
    fabricRef.current.remove(obj)
    applyingRemote.current = false
    objectsById.current.delete(elementId)
  }, [])

  const sendElementCreate = useCallback(
    (obj: CanvasObject) => {
      const clientOperationId = crypto.randomUUID()
      const elementPayload = {
        type: resolveElementType(obj),
        transform: toTransform(obj),
        style: toStyle(obj),
        content: toContent(obj),
      }
      obj.localCreateId = clientOperationId
      pendingCreates.current.set(clientOperationId, obj)
      sendMessage({
        type: 'element:op',
        payload: {
          operation: 'create',
          client_operation_id: clientOperationId,
          vector_clock: nextVectorClock(),
          element: elementPayload,
        },
      })
    },
    [nextVectorClock, resolveElementType, sendMessage, toContent, toStyle, toTransform],
  )

  const sendElementUpdate = useCallback(
    (obj: CanvasObject) => {
      if (!obj.elementId) return
      sendMessage({
        type: 'element:op',
        payload: {
          operation: 'update',
          element_id: obj.elementId,
          transform: toTransform(obj),
          style: toStyle(obj),
          content: toContent(obj),
          vector_clock: nextVectorClock(),
        },
      })
    },
    [nextVectorClock, sendMessage, toContent, toStyle, toTransform],
  )

  const sendElementDelete = useCallback(
    (obj: CanvasObject) => {
      if (!obj.elementId) return
      sendMessage({ type: 'element:op', payload: { operation: 'delete', element_id: obj.elementId } })
    },
    [sendMessage],
  )

  const sendLock = useCallback(
    (elementId: string) => {
      sendMessage({ type: 'element:lock', payload: { element_id: elementId } })
    },
    [sendMessage],
  )

  const showToolMessage = useCallback((message: string) => {
    setStatusMessage(message)
  }, [])

  const applyStrokeColor = useCallback(
    (color: string) => {
      setStrokeColor(color)
      const canvas = fabricRef.current
      if (!canvas) return
      const activeObjects = canvas.getActiveObjects() as CanvasObject[]
      if (activeObjects.length === 0) return
      activeObjects.forEach((obj) => {
        obj.set({ stroke: color })
        if (obj.type === 'textbox') {
          obj.set({ fill: color })
        }
        if (obj.elementId) {
          sendElementUpdate(obj)
        } else {
          obj.pendingSync = true
        }
      })
      canvas.requestRenderAll()
    },
    [sendElementUpdate],
  )

  const deleteActiveObjects = useCallback(() => {
    const canvas = fabricRef.current
    if (!canvas) return
    const activeObjects = canvas.getActiveObjects() as CanvasObject[]
    if (activeObjects.length === 0) {
      showToolMessage('Select an element first, then use the eraser.')
      return
    }
    activeObjects.forEach((obj) => canvas.remove(obj))
    canvas.discardActiveObject()
    canvas.requestRenderAll()
  }, [showToolMessage])

  useEffect(() => {
    activeToolRef.current = tool
    const canvas = fabricRef.current
    if (!canvas) return
    canvas.isDrawingMode = false
  }, [tool])

  useEffect(() => {
    if (!page?.id || !canvasRef.current || !containerRef.current) return
    const timers = textUpdateTimers.current
    const objectMap = objectsById.current
    const pendingCreateMap = pendingCreates.current

    const canvas = new Canvas(canvasRef.current, {
      preserveObjectStacking: true,
      selection: true,
    })
    canvas.backgroundColor = 'rgba(248, 249, 255, 0)'
    fabricRef.current = canvas

    const resize = () => {
      if (!containerRef.current) return
      const width = containerRef.current.clientWidth
      const height = containerRef.current.clientHeight
      canvas.setDimensions({ width, height })
      canvas.renderAll()
    }

    resize()
    window.addEventListener('resize', resize)

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Delete' && event.key !== 'Backspace') return
      const active = document.activeElement
      if (
        active instanceof HTMLInputElement ||
        active instanceof HTMLTextAreaElement ||
        active?.getAttribute('contenteditable') === 'true'
      ) {
        return
      }
      if (canvas.getActiveObjects().length === 0) return
      event.preventDefault()
      deleteActiveObjects()
    }

    window.addEventListener('keydown', handleKeyDown)

    canvas.on('mouse:down', (event) => {
      const pointer = canvas.getViewportPoint(event.e)
      if (activeToolRef.current === 'rect') {
        const rect = new Rect({
          left: pointer.x,
          top: pointer.y,
          width: DEFAULT_RECT.width,
          height: DEFAULT_RECT.height,
          fill: '#f8fafc',
          stroke: strokeColorRef.current,
          strokeWidth: 2,
        }) as CanvasObject
        rect.canvexType = 'rect'
        canvas.add(rect)
        canvas.setActiveObject(rect)
        setTool('select')
      }
      if (activeToolRef.current === 'ellipse') {
        const ellipse = new Ellipse({
          left: pointer.x,
          top: pointer.y,
          rx: DEFAULT_ELLIPSE.rx,
          ry: DEFAULT_ELLIPSE.ry,
          fill: '#fef9c3',
          stroke: strokeColorRef.current,
          strokeWidth: 2,
        }) as CanvasObject
        ellipse.canvexType = 'ellipse'
        canvas.add(ellipse)
        canvas.setActiveObject(ellipse)
        setTool('select')
      }
      if (activeToolRef.current === 'text' || activeToolRef.current === 'sticky') {
        const isSticky = activeToolRef.current === 'sticky'
        const textbox = new Textbox(isSticky ? 'Sticky note' : 'Text', {
          left: pointer.x,
          top: pointer.y,
          width: isSticky ? 180 : 220,
          fontSize: isSticky ? 18 : 20,
          fill: strokeColorRef.current,
          backgroundColor: isSticky ? '#fef3c7' : '',
          padding: isSticky ? 12 : 0,
        })
        const canvexTextbox = textbox as CanvasObject
        canvexTextbox.canvexType = isSticky ? 'sticky' : 'text'
        canvas.add(canvexTextbox)
        canvas.setActiveObject(canvexTextbox)
        textbox.enterEditing()
        setTool('select')
      }
    })

    canvas.on('mouse:move', (event) => {
      if (!pageRef.current || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return
      if (cursorThrottleRef.current) return
      cursorThrottleRef.current = window.setTimeout(() => {
        cursorThrottleRef.current = null
      }, 30)
      const pointer = canvas.getViewportPoint(event.e)
      sendMessage({ type: 'cursor:move', payload: { x: pointer.x, y: pointer.y, color: cursorColor } })
    })

    canvas.on('selection:created', (event) => {
      const obj = event.selected?.[0] as CanvasObject | undefined
      if (obj?.elementId) {
        sendLock(obj.elementId)
      }
    })

    canvas.on('selection:updated', (event) => {
      const obj = event.selected?.[0] as CanvasObject | undefined
      if (obj?.elementId) {
        sendLock(obj.elementId)
      }
    })

    canvas.on('object:added', (event) => {
      const obj = event.target as CanvasObject | undefined
      if (!obj || applyingRemote.current || obj.isRemote) return
      if (!obj.elementId) {
        sendElementCreate(obj)
      }
    })

    canvas.on('object:modified', (event) => {
      const obj = event.target as CanvasObject | undefined
      if (!obj || applyingRemote.current || obj.isRemote) return
      sendElementUpdate(obj)
    })

    canvas.on('object:removed', (event) => {
      const obj = event.target as CanvasObject | undefined
      if (!obj || applyingRemote.current || obj.isRemote) return
      sendElementDelete(obj)
    })

    canvas.on('text:changed', (event) => {
      const obj = event.target as CanvasObject | undefined
      if (!obj || applyingRemote.current || obj.isRemote || !obj.elementId) return
      const elementId = obj.elementId
      const existing = textUpdateTimers.current.get(elementId)
      if (existing) {
        window.clearTimeout(existing)
      }
      const timer = window.setTimeout(() => {
        sendElementUpdate(obj)
        textUpdateTimers.current.delete(elementId)
      }, 300)
      textUpdateTimers.current.set(elementId, timer)
    })

    canvas.on('text:editing:exited', (event) => {
      const obj = event.target as CanvasObject | undefined
      if (!obj || applyingRemote.current || obj.isRemote || !obj.elementId) return
      const elementId = obj.elementId
      const existing = textUpdateTimers.current.get(elementId)
      if (existing) {
        window.clearTimeout(existing)
        textUpdateTimers.current.delete(elementId)
      }
      sendElementUpdate(obj)
    })

    return () => {
      window.removeEventListener('resize', resize)
      window.removeEventListener('keydown', handleKeyDown)
      timers.forEach((timer) => window.clearTimeout(timer))
      timers.clear()
      if (cursorThrottleRef.current) {
        window.clearTimeout(cursorThrottleRef.current)
        cursorThrottleRef.current = null
      }
      objectMap.clear()
      pendingCreateMap.clear()
      fabricRef.current = null
      canvas.dispose()
    }
  }, [
    cursorColor,
    deleteActiveObjects,
    page?.id,
    sendElementCreate,
    sendElementDelete,
    sendElementUpdate,
    sendLock,
    sendMessage,
  ])

  useEffect(() => {
    const pageId = page?.id
    if (!pageId || !fabricRef.current) return
    let cancelled = false

    const load = async () => {
      setIsLoadingPage(true)
      try {
        const elements = await listElements(pageId)
        if (cancelled || pageRef.current?.id !== pageId || !fabricRef.current) return
        applyingRemote.current = true
        fabricRef.current.clear()
        fabricRef.current.backgroundColor = 'rgba(248, 249, 255, 0)'
        objectsById.current.clear()
        pendingCreates.current.clear()
        setCursors({})
        elements.filter((element) => !element.is_deleted).forEach(addElementToCanvas)
      } catch {
        if (!cancelled) {
          setStatusMessage('Failed to load elements for this page.')
        }
      } finally {
        if (!cancelled) {
          applyingRemote.current = false
          setIsLoadingPage(false)
        }
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [addElementToCanvas, page?.id])

  useEffect(() => {
    const pageId = page?.id
    if (!pageId) return
    const wsUrl = new URL(`/ws/${pageId}`, import.meta.env.VITE_API_URL ?? 'http://localhost:8000')
    wsUrl.protocol = wsUrl.protocol.replace('http', 'ws')
    wsUrl.searchParams.set('token', accessToken)
    const socket = new WebSocket(wsUrl.toString())
    wsRef.current = socket
    setConnectionState('connecting')

    socket.onopen = () => {
      setConnectionState('connected')
    }
    socket.onclose = () => {
      setConnectionState('disconnected')
    }
    socket.onerror = () => {
      setConnectionState('disconnected')
    }
    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data)
        switch (message.type) {
          case 'element:ack': {
            if (message.operation === 'create') {
              const created = message.payload as Element
              const clientOperationId =
                typeof message.client_operation_id === 'string' ? message.client_operation_id : null
              const obj = clientOperationId ? pendingCreates.current.get(clientOperationId) : undefined
              if (obj) {
                pendingCreates.current.delete(clientOperationId)
                delete obj.localCreateId
                obj.elementId = created.id
                obj.canvexType = created.type
                objectsById.current.set(created.id, obj)
                if (obj.pendingSync) {
                  delete obj.pendingSync
                  sendElementUpdate(obj)
                }
              }
            }
            if (message.operation === 'update') {
              updateElementOnCanvas(message.payload as Element)
            }
            if (message.operation === 'delete') {
              removeElementFromCanvas(message.payload.id)
            }
            return
          }
          case 'element:op': {
            const payload = message.payload as Element
            if (message.operation === 'create') {
              addElementToCanvas(payload)
            } else if (message.operation === 'update') {
              updateElementOnCanvas(payload)
            } else if (message.operation === 'delete') {
              removeElementFromCanvas(payload.id)
            }
            return
          }
          case 'element:lock': {
            const lockPayload = message.payload as { element_id: string; locked_by: string }
            const obj = objectsById.current.get(lockPayload.element_id)
            if (obj && lockPayload.locked_by !== user.id) {
              obj.selectable = false
              obj.opacity = 0.6
              fabricRef.current?.renderAll()
            }
            return
          }
          case 'element:unlock': {
            const lockPayload = message.payload as { element_id: string }
            const obj = objectsById.current.get(lockPayload.element_id)
            if (obj) {
              obj.selectable = true
              obj.opacity = 1
              fabricRef.current?.renderAll()
            }
            return
          }
          case 'cursor:move': {
            const cursorPayload = message.payload as {
              user_id: string
              display_name: string
              x: number
              y: number
              color?: string
            }
            if (cursorPayload.user_id === user.id) return
            setCursors((prev) => ({
              ...prev,
              [cursorPayload.user_id]: {
                userId: cursorPayload.user_id,
                displayName: cursorPayload.display_name,
                x: cursorPayload.x,
                y: cursorPayload.y,
                color: cursorPayload.color ?? colorFromId(cursorPayload.user_id),
              },
            }))
            return
          }
          case 'presence:leave': {
            const payload = message.payload as { user_id: string }
            setCursors((prev) => {
              const next = { ...prev }
              delete next[payload.user_id]
              return next
            })
            return
          }
          case 'element:error': {
            setStatusMessage(message.detail ?? 'Canvas update failed')
            return
          }
          default:
            return
        }
      } catch {
        setStatusMessage('WebSocket message failed to parse')
      }
    }

    return () => {
      socket.close()
      wsRef.current = null
    }
  }, [
    accessToken,
    addElementToCanvas,
    page?.id,
    removeElementFromCanvas,
    sendElementUpdate,
    updateElementOnCanvas,
    user.id,
  ])

  useEffect(() => {
    const pageId = page?.id
    if (!pageId) return
    const refreshPresence = async () => {
      try {
        const count = await getPresenceCount(pageId)
        setPresenceCount(count)
      } catch {
        setPresenceCount(0)
      }
    }
    refreshPresence()
    const interval = window.setInterval(refreshPresence, 10000)
    return () => window.clearInterval(interval)
  }, [page?.id])

  useEffect(() => {
    if (!statusMessage) return
    const timer = window.setTimeout(() => setStatusMessage(null), 4000)
    return () => window.clearTimeout(timer)
  }, [statusMessage])

  if (!page) {
    return (
      <div className="relative h-full overflow-hidden">
        <div className="workspace-page-label">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">Active page</p>
          <h2 className="font-handwriting text-3xl font-semibold text-slate-950">No page selected</h2>
        </div>
        <div className="workspace-presence">
          <div className="workspace-avatar">{user.display_name.slice(0, 2).toUpperCase()}</div>
          <button type="button" className="workspace-ai-button" onClick={() => setIsAiOpen((prev) => !prev)}>
            <Sparkles size={15} />
            <span className="workspace-ai-label">Ask Canvex</span>
          </button>
        </div>
        <div className="workspace-tool-capsule opacity-60">
          <span className="hidden font-reading-serif text-lg text-slate-700/80 md:inline">Canvex</span>
          <div className="workspace-tool-divider hidden md:block" />
          <Move size={16} />
          <PenLine size={16} />
          <Brush size={16} />
          <Highlighter size={16} />
          <Eraser size={16} />
          <div className="workspace-tool-divider" />
          <RectangleHorizontal size={16} />
          <Circle size={16} />
          <Text size={16} />
          <StickyNote size={16} />
        </div>
        <div className="canvas-surface absolute inset-0"></div>
        <div className="relative z-20 flex h-full items-center justify-center text-sm text-slate-500">
          <div className="max-w-sm rounded-lg border border-dashed border-slate-300 bg-white/65 px-6 py-5 text-center shadow-sm backdrop-blur-sm">
            <p className="font-reading-serif text-xl text-slate-900">Your notebook is ready.</p>
            <p className="mt-2 text-sm leading-6 text-slate-500">
              Create a channel, then add a page from the notebook index on the left to start drawing.
            </p>
          </div>
        </div>
        {isAiOpen && (
          <aside className="workspace-ai-panel">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-reading-serif text-lg text-indigo-700">Ask Canvex</h3>
                <p className="text-xs uppercase tracking-[0.18em] text-slate-400">AI notebook assistant</p>
              </div>
              <button type="button" className="workspace-ghost-button" onClick={() => setIsAiOpen(false)}>
                Close
              </button>
            </div>
            <p className="mt-5 rounded-lg border border-indigo-100 bg-indigo-50/60 p-3 text-sm leading-6 text-slate-600">
              Create a page first, then I can help summarize, explain, and organize your canvas.
            </p>
          </aside>
        )}
      </div>
    )
  }

  const isConnected = connectionState === 'connected'

  return (
    <div className="relative h-full overflow-hidden">
      <div className="workspace-page-label">
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">Active page</p>
        <h2 className="font-handwriting text-3xl font-semibold text-slate-950">{page.title}</h2>
      </div>

      <div className="workspace-presence">
        <div className="flex -space-x-2">
          <div className="workspace-avatar">{user.display_name.slice(0, 2).toUpperCase()}</div>
          {presenceCount > 1 && <div className="workspace-avatar muted">+{presenceCount - 1}</div>}
        </div>
        <span className={`workspace-live-chip ${isConnected ? 'online' : ''}`}>
          {isConnected ? 'Live' : connectionState === 'connecting' ? 'Connecting' : 'Offline'}
        </span>
        <button type="button" className="workspace-ai-button" onClick={() => setIsAiOpen((prev) => !prev)}>
          <Sparkles size={15} />
          <span className="workspace-ai-label">Ask Canvex</span>
        </button>
      </div>

      <div className="workspace-tool-capsule">
        <span className="hidden font-reading-serif text-lg text-slate-700/80 md:inline">Canvex</span>
        <div className="workspace-tool-divider hidden md:block" />
        <button
          type="button"
          className={`workspace-tool-button ${tool === 'select' ? 'active' : ''}`}
          onClick={() => setTool('select')}
          title={TOOL_LABELS.select}
        >
          <Move size={16} />
        </button>
        <div className="workspace-tool-divider" />
        <button
          type="button"
          className="workspace-tool-button ghost"
          title="Pen"
          onClick={() => showToolMessage('Freehand pen is planned for the drawing phase. Use shapes and text for now.')}
        >
          <PenLine size={16} />
        </button>
        <button
          type="button"
          className="workspace-tool-button ghost"
          title="Pencil"
          onClick={() => showToolMessage('Pencil mode is coming soon.')}
        >
          <Brush size={16} />
        </button>
        <button
          type="button"
          className="workspace-tool-button ghost"
          title="Highlighter"
          onClick={() => showToolMessage('Highlighter mode is coming soon.')}
        >
          <Highlighter size={16} />
        </button>
        <button type="button" className="workspace-tool-button ghost" title="Eraser" onClick={deleteActiveObjects}>
          <Eraser size={16} />
        </button>
        <div className="workspace-tool-divider" />
        <button
          type="button"
          className={`workspace-tool-button ${tool === 'rect' ? 'active' : ''}`}
          onClick={() => setTool('rect')}
          title={TOOL_LABELS.rect}
        >
          <RectangleHorizontal size={16} />
        </button>
        <button
          type="button"
          className={`workspace-tool-button ${tool === 'ellipse' ? 'active' : ''}`}
          onClick={() => setTool('ellipse')}
          title={TOOL_LABELS.ellipse}
        >
          <Circle size={16} />
        </button>
        <button
          type="button"
          className={`workspace-tool-button ${tool === 'text' ? 'active' : ''}`}
          onClick={() => setTool('text')}
          title={TOOL_LABELS.text}
        >
          <Text size={16} />
        </button>
        <button
          type="button"
          className={`workspace-tool-button ${tool === 'sticky' ? 'active' : 'ghost'}`}
          title="Sticky Note"
          onClick={() => {
            setTool('sticky')
            showToolMessage('Click the canvas to place a note.')
          }}
        >
          <StickyNote size={16} />
        </button>
        <button
          type="button"
          className="workspace-tool-button ghost"
          title="Image"
          onClick={() => showToolMessage('Image uploads are coming soon.')}
        >
          <Image size={16} />
        </button>
        <div className="workspace-tool-divider" />
        <div className="workspace-swatches">
          {['#0f172a', '#2563eb', '#ef4444', '#22c55e', '#facc15', '#818cf8'].map((color) => (
            <button
              key={color}
              type="button"
              className={`workspace-swatch ${strokeColor === color ? 'active' : ''}`}
              style={{ backgroundColor: color }}
              onClick={() => applyStrokeColor(color)}
              title={`Use ${color}`}
            />
          ))}
        </div>
        <div className="workspace-tool-divider hidden sm:block" />
        <button
          type="button"
          className="workspace-tool-button ghost hidden sm:flex"
          title="Undo"
          onClick={() => showToolMessage('Undo is coming soon.')}
        >
          <Undo2 size={16} />
        </button>
        <button
          type="button"
          className="workspace-tool-button ghost hidden sm:flex"
          title="Redo"
          onClick={() => showToolMessage('Redo is coming soon.')}
        >
          <Redo2 size={16} />
        </button>
      </div>

      {statusMessage && (
        <div className="workspace-status-message">{statusMessage}</div>
      )}
      {isLoadingPage && (
        <div className="workspace-status-message">Loading page...</div>
      )}

      <div ref={containerRef} className="relative h-full overflow-hidden">
        <div className="canvas-surface absolute inset-0"></div>
        <canvas ref={canvasRef} className="relative z-10 h-full w-full"></canvas>
        {Object.values(cursors).map((cursor) => (
          <div key={cursor.userId} className="pointer-events-none absolute left-0 top-0">
            <div
              className="cursor-dot"
              style={{ left: cursor.x, top: cursor.y, backgroundColor: cursor.color }}
            />
            <div className="cursor-label" style={{ left: cursor.x, top: cursor.y }}>
              {cursor.displayName}
            </div>
          </div>
        ))}
      </div>
      {isAiOpen && (
        <aside className="workspace-ai-panel">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-reading-serif text-lg text-indigo-700">Ask Canvex</h3>
              <p className="text-xs uppercase tracking-[0.18em] text-slate-400">AI notebook assistant</p>
            </div>
            <button type="button" className="workspace-ghost-button" onClick={() => setIsAiOpen(false)}>
              Close
            </button>
          </div>
          <div className="mt-5 space-y-3 text-sm leading-6 text-slate-600">
            <p className="rounded-lg border border-indigo-100 bg-indigo-50/60 p-3">
              I can help explain selected notes, summarize this page, or turn sketches into structured study points.
            </p>
            <input className="workspace-input" placeholder="Ask about this canvas..." />
            <button
              type="button"
              className="workspace-action-button w-full justify-center"
              onClick={() => showToolMessage('AI features are coming in Phase 9.')}
            >
              <Sparkles size={15} />
              Ask
            </button>
          </div>
        </aside>
      )}
    </div>
  )
}

export default CanvasBoard
