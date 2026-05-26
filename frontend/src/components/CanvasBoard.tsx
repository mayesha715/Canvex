import { Canvas, Ellipse, FabricObject, Line, PencilBrush, Polyline, Rect, Textbox } from 'fabric'
import { Brush, Circle, Move, PenLine, RectangleHorizontal, Text } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { getPresenceCount, listElements } from '../lib/api'
import { colorFromId } from '../lib/colors'
import type { Element, ElementType, PageSummary, User } from '../types'

type Tool = 'select' | 'pen' | 'rect' | 'ellipse' | 'text'

type CanvasObject = FabricObject & {
  elementId?: string
  canvexType?: ElementType
  isRemote?: boolean
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
  pen: 'Pen',
  rect: 'Rectangle',
  ellipse: 'Ellipse',
  text: 'Text',
}

const DEFAULT_RECT = { width: 140, height: 90 }
const DEFAULT_ELLIPSE = { rx: 60, ry: 40 }

const CanvasBoard = ({ page, user, accessToken }: CanvasBoardProps) => {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const fabricRef = useRef<Canvas | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const objectsById = useRef<Map<string, CanvasObject>>(new Map())
  const pendingCreates = useRef<CanvasObject[]>([])
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

  const cursorColor = useMemo(() => colorFromId(user.id), [user.id])

  useEffect(() => {
    pageRef.current = page
  }, [page])

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
    const elementPayload = {
      type: resolveElementType(obj),
      transform: toTransform(obj),
      style: toStyle(obj),
      content: toContent(obj),
      vector_clock: nextVectorClock(),
    }
    sendMessage({ type: 'element:op', payload: { operation: 'create', element: elementPayload } })
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

  useEffect(() => {
    activeToolRef.current = tool
    const canvas = fabricRef.current
    if (!canvas) return
    canvas.isDrawingMode = tool === 'pen'
    canvas.freeDrawingBrush = canvas.freeDrawingBrush ?? new PencilBrush(canvas)
    if (canvas.freeDrawingBrush) {
      canvas.freeDrawingBrush.width = 2
      canvas.freeDrawingBrush.color = '#1f2937'
    }
  }, [tool])

  useEffect(() => {
    if (!canvasRef.current || !containerRef.current) return
    const timers = textUpdateTimers.current

    const canvas = new Canvas(canvasRef.current, {
      preserveObjectStacking: true,
      selection: true,
    })
    canvas.backgroundColor = '#f8fafc'
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

    canvas.on('mouse:down', (event) => {
      const pointer = canvas.getViewportPoint(event.e)
      if (activeToolRef.current === 'rect') {
        const rect = new Rect({
          left: pointer.x,
          top: pointer.y,
          width: DEFAULT_RECT.width,
          height: DEFAULT_RECT.height,
          fill: '#f8fafc',
          stroke: '#111827',
          strokeWidth: 2,
        }) as CanvasObject
        rect.canvexType = 'rect'
        canvas.add(rect)
        canvas.setActiveObject(rect)
      }
      if (activeToolRef.current === 'ellipse') {
        const ellipse = new Ellipse({
          left: pointer.x,
          top: pointer.y,
          rx: DEFAULT_ELLIPSE.rx,
          ry: DEFAULT_ELLIPSE.ry,
          fill: '#fef9c3',
          stroke: '#111827',
          strokeWidth: 2,
        }) as CanvasObject
        ellipse.canvexType = 'ellipse'
        canvas.add(ellipse)
        canvas.setActiveObject(ellipse)
      }
      if (activeToolRef.current === 'text') {
        const textbox = new Textbox('Text', {
          left: pointer.x,
          top: pointer.y,
          width: 220,
          fontSize: 20,
          fill: '#0f172a',
        })
        const canvexTextbox = textbox as CanvasObject
        canvexTextbox.canvexType = 'text'
        canvas.add(canvexTextbox)
        canvas.setActiveObject(canvexTextbox)
        textbox.enterEditing()
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
        pendingCreates.current.push(obj)
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
      timers.forEach((timer) => window.clearTimeout(timer))
      timers.clear()
      canvas.dispose()
    }
  }, [
    cursorColor,
    sendElementCreate,
    sendElementDelete,
    sendElementUpdate,
    sendLock,
    sendMessage,
  ])

  useEffect(() => {
    const pageId = page?.id
    if (!pageId || !fabricRef.current) return
    const load = async () => {
      try {
        const elements = await listElements(pageId)
        applyingRemote.current = true
        fabricRef.current?.clear()
        if (fabricRef.current) {
          fabricRef.current.backgroundColor = '#f8fafc'
        }
        objectsById.current.clear()
        pendingCreates.current = []
        setCursors({})
        elements.filter((element) => !element.is_deleted).forEach(addElementToCanvas)
        applyingRemote.current = false
      } catch {
        setStatusMessage('Failed to load elements for this page.')
      }
    }
    load()
  }, [addElementToCanvas, page?.id])

  useEffect(() => {
    if (!page) return
    const wsUrl = new URL(`/ws/${page.id}`, import.meta.env.VITE_API_URL ?? 'http://localhost:8000')
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
              const obj = pendingCreates.current.shift()
              if (obj) {
                obj.elementId = created.id
                obj.canvexType = created.type
                objectsById.current.set(created.id, obj)
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
  }, [accessToken, addElementToCanvas, page, removeElementFromCanvas, updateElementOnCanvas, user.id])

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
      <div className="flex h-full items-center justify-center text-sm text-slate-500">
        Select a page to start collaborating.
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800/60 px-6 py-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">Active page</p>
          <h2 className="text-xl font-semibold text-white">{page.title}</h2>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <span className="chip">{presenceCount} online</span>
          <span className="chip">
            {connectionState === 'connected' ? 'Live sync' : connectionState === 'connecting' ? 'Connecting…' : 'Offline'}
          </span>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 border-b border-slate-800/60 px-6 py-3">
        <button
          type="button"
          className={`toolbar-button ${tool === 'select' ? 'active' : ''}`}
          onClick={() => setTool('select')}
        >
          <Move size={16} />
          {TOOL_LABELS.select}
        </button>
        <button
          type="button"
          className={`toolbar-button ${tool === 'pen' ? 'active' : ''}`}
          onClick={() => setTool('pen')}
        >
          <PenLine size={16} />
          {TOOL_LABELS.pen}
        </button>
        <button
          type="button"
          className={`toolbar-button ${tool === 'rect' ? 'active' : ''}`}
          onClick={() => setTool('rect')}
        >
          <RectangleHorizontal size={16} />
          {TOOL_LABELS.rect}
        </button>
        <button
          type="button"
          className={`toolbar-button ${tool === 'ellipse' ? 'active' : ''}`}
          onClick={() => setTool('ellipse')}
        >
          <Circle size={16} />
          {TOOL_LABELS.ellipse}
        </button>
        <button
          type="button"
          className={`toolbar-button ${tool === 'text' ? 'active' : ''}`}
          onClick={() => setTool('text')}
        >
          <Text size={16} />
          {TOOL_LABELS.text}
        </button>
        <button type="button" className="toolbar-button">
          <Brush size={16} />
          Locks on edit
        </button>
      </div>

      {statusMessage && (
        <div className="bg-rose-500/20 px-6 py-2 text-sm text-rose-200">{statusMessage}</div>
      )}

      <div ref={containerRef} className="relative flex-1 overflow-hidden bg-slate-900/40">
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
    </div>
  )
}

export default CanvasBoard
