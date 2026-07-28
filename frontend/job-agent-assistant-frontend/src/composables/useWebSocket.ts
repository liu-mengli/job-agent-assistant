import { ref } from 'vue'
import apiClient from '../api/client'

type MessageHandler = (payload: any) => void

const WS_BASE = import.meta.env.VITE_WS_BASE_URL

// --- 模块级单例，所有组件共享同一个连接 ---
let ws: WebSocket | null = null
let pingTimer: ReturnType<typeof setInterval> | null = null
const handlers = new Map<string, MessageHandler[]>()
const closeCallbacks: Array<(event: CloseEvent) => void> = []

const connected = ref(false)
const error = ref<string | null>(null)
const sessionId = ref<string | null>(null)

async function connect() {
  const jwt = localStorage.getItem('token')
  if (!jwt || ws) return

  // 优先复用 sessionStorage 中保存的会话 ID（断线重连不换会话），
  // 无则生成新 UUID（首次连接或主动新建会话后）
  sessionId.value = sessionStorage.getItem('sessionId') || crypto.randomUUID()
  sessionStorage.setItem('sessionId', sessionId.value!)

  try {
    // ① 通过安全 HTTP 请求换取一次性 WS 票据（JWT 在请求头里，不进 URL）
    const data = await apiClient.post('/ws/ticket') as { ticket: string }
    const ticket = data.ticket

    // ② 用票据 + session_id 建立 WebSocket 连接（URL 里只暴露短期一次性票据）
    ws = new WebSocket(`${WS_BASE}/ws/chat?ticket=${ticket}&session_id=${sessionId.value}`)
  } catch (err: any) {
    error.value = '获取连接票据失败'
    // 如果是 401（Token 过期），交给 client.ts 拦截器跳登录；
    // 其他错误（网络不通等）延迟重试
    if (err?.response?.status !== 401) {
      setTimeout(() => connect(), 5000)
    }
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
    // 通知所有注册的断连回调
    closeCallbacks.forEach((cb) => cb(event))
    // 1000: 主动断开  1001: 服务端踢出（新连接顶替），不应自动重连
    if (event.code !== 1000 && event.code !== 1001 && localStorage.getItem('token')) {
      setTimeout(() => { connect().catch(() => { }) }, 5000)
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

function newSession() {
  // 清除旧会话 ID，下次 connect 会生成新的
  sessionStorage.removeItem('sessionId')
  sessionId.value = null
  disconnect()
  connect()
}

function disconnect() {
  if (pingTimer) clearInterval(pingTimer)
  ws?.close(1000)
  ws = null
  connected.value = false
  // 不清除 sessionId —— 断线重连后复用同一会话
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
  return { connected, error, sessionId, connect, newSession, send, on, off, onClose, offClose, disconnect }
}
