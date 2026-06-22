import { ref } from 'vue'

type MessageHandler = (payload: any) => void

const WS_BASE = import.meta.env.VITE_WS_BASE_URL

// --- 模块级单例，所有组件共享同一个连接 ---
let ws: WebSocket | null = null
let pingTimer: ReturnType<typeof setInterval> | null = null
const handlers = new Map<string, MessageHandler[]>()
const closeCallbacks: Array<(event: CloseEvent) => void> = []

const connected = ref(false)
const error = ref<string | null>(null)

function connect() {
  const token = sessionStorage.getItem('token')
  if (!token || ws) return

  ws = new WebSocket(`${WS_BASE}/ws/chat?token=${token}`)

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
    } catch {
      // 忽略非 JSON 消息
    }
  }

  ws.onerror = () => {
    error.value = 'WebSocket 连接异常'
  }

  ws.onclose = (event) => {
    connected.value = false
    if (pingTimer) clearInterval(pingTimer)
    ws = null
    // 通知所有注册的断连回调（用于页面清理未完成的消息等）
    closeCallbacks.forEach((cb) => cb(event))
    // 1000: 主动断开  1001: 服务端踢出（新连接顶替），不应自动重连
    if (event.code !== 1000 && event.code !== 1001 && sessionStorage.getItem('token')) {
      setTimeout(connect, 5000)
    }
  }
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

function disconnect() {
  if (pingTimer) clearInterval(pingTimer)
  ws?.close(1000)
  ws = null
  connected.value = false
}

function onClose(cb: (event: CloseEvent) => void) {
  closeCallbacks.push(cb)
}

function offClose(cb: (event: CloseEvent) => void) {
  const idx = closeCallbacks.indexOf(cb)
  if (idx !== -1) closeCallbacks.splice(idx, 1)
}

// 注意：这里不创建新实例，每次返回同一个单例
export function useWebSocket() {
  return { connected, error, connect, send, on, off, onClose, offClose, disconnect }
}
