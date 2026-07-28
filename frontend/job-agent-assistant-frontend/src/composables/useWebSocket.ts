import { ref } from 'vue'
import apiClient from '../api/client'

type MessageHandler = (payload: any) => void

const WS_BASE = import.meta.env.VITE_WS_BASE_URL

function generateUUID(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID()
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16)
  })
}

// --- 模块级单例 ---
let ws: WebSocket | null = null
let pingTimer: ReturnType<typeof setInterval> | null = null
let reconnectTimer: ReturnType<typeof setTimeout> | null = null
const handlers = new Map<string, MessageHandler[]>()
const closeCallbacks: Array<(event: CloseEvent) => void> = []

const connected = ref(false)
const error = ref<string | null>(null)
const sessionId = ref<string | null>(null)

let connecting = false
let connectVersion = 0

function scheduleReconnect() {
  if (reconnectTimer) clearTimeout(reconnectTimer)
  if (!localStorage.getItem('token')) return
  reconnectTimer = setTimeout(() => { connect().catch(() => {}) }, 1000)
}

async function connect(targetSessionId?: string) {
  const jwt = localStorage.getItem('token')
  if (!jwt) return
  if (ws || connecting) return

  connecting = true
  const myVersion = ++connectVersion

  // 初始连接始终生成新 ID，避免新旧 WS 冲突；切换会话时传 targetSessionId 复用
  sessionId.value = targetSessionId || generateUUID()
  sessionStorage.setItem('sessionId', sessionId.value!)

  try {
    const data = await apiClient.post('/ws/ticket') as { ticket: string }
    if (myVersion !== connectVersion) { connecting = false; return }
    ws = new WebSocket(`${WS_BASE}/ws/chat?ticket=${data.ticket}&session_id=${sessionId.value}`)
  } catch (err: any) {
    if (myVersion !== connectVersion) { connecting = false; return }
    connecting = false
    if (err?.response?.status !== 401) scheduleReconnect()
    return
  }

  ws.onopen = () => {
    connected.value = true
    error.value = null
    pingTimer = setInterval(() => send('ping'), 30000)
  }

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data)
      const callbacks = handlers.get(msg.type) || []
      callbacks.forEach((fn) => fn(msg.payload))
    } catch { /* ignore */ }
  }

  ws.onerror = () => {
    if (myVersion !== connectVersion) return
    // WS 构造函数阶段失败（非 1000/1001），立即重试
    if (!connected.value) scheduleReconnect()
  }

  ws.onclose = (event) => {
    connected.value = false
    if (pingTimer) clearInterval(pingTimer)
    ws = null
    closeCallbacks.forEach((cb) => cb(event))
    if (myVersion !== connectVersion) return
    // 异常断开（非主动关闭、非被踢）才重连
    if (event.code !== 1000 && event.code !== 1001 && localStorage.getItem('token')) {
      scheduleReconnect()
    }
  }

  connecting = false
}

function send(type: string, payload: any = null): boolean {
  if (ws?.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type, payload }))
    return true
  }
  return false
}

function on(type: string, handler: MessageHandler) {
  if (!handlers.has(type)) handlers.set(type, [])
  handlers.get(type)!.push(handler)
}

function off(type: string, handler: MessageHandler) {
  const list = handlers.get(type)
  if (list) handlers.set(type, list.filter((h) => h !== handler))
}

function newSession() {
  sessionStorage.removeItem('sessionId')
  sessionId.value = null
  disconnect()
  connect()
}

function disconnect() {
  connecting = false
  if (reconnectTimer) clearTimeout(reconnectTimer)
  if (pingTimer) clearInterval(pingTimer)
  ws?.close(1000)
  ws = null
  connected.value = false
}

function onClose(cb: (event: CloseEvent) => void) { closeCallbacks.push(cb) }
function offClose(cb: (event: CloseEvent) => void) {
  const idx = closeCallbacks.indexOf(cb)
  if (idx !== -1) closeCallbacks.splice(idx, 1)
}

export function useWebSocket() {
  return { connected, error, sessionId, connect, newSession, send, on, off, onClose, offClose, disconnect }
}
