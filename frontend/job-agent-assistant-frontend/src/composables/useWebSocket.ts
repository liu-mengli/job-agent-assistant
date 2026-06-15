import { ref } from 'vue'

type MessageHandler = (payload: any) => void

const WS_BASE = import.meta.env.VITE_WS_BASE_URL

export function useWebSocket() {
  const connected = ref(false)
  const error = ref<string | null>(null)
  let ws: WebSocket | null = null
  let pingTimer: ReturnType<typeof setInterval> | null = null
  const handlers = new Map<string, MessageHandler[]>()

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
      // 非主动登出则 5 秒后自动重连
      if (event.code !== 1000 && sessionStorage.getItem('token')) {
        setTimeout(connect, 5000)
      }
    }
  }

  function send(type: string, payload: any = null) {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type, payload }))
    }
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

  return { connected, error, connect, send, on, off, disconnect }
}
