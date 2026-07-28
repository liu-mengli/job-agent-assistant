<script setup lang="ts">
import { ref, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { useWebSocket } from '../composables/useWebSocket'
import { fetchSessions, fetchSessionMessages, deleteSession, type SessionItem } from '../api/sessions'
import type { StructuredContent } from '../types/structured'
import StructuredMessage from '../components/StructuredMessage.vue'
import { renderMarkdown } from '../utils/markdown'

interface Message {
  role: 'user' | 'assistant' | 'system'
  content: string
  structured?: StructuredContent
}

const ws = useWebSocket()
const messages = ref<Message[]>([])
const input = ref('')
const sending = ref(false)
const chatRef = ref<HTMLElement>()

// --- 会话列表 ---
const sessions = ref<SessionItem[]>([])
const activeSessionId = ref<string | null>(null)
const loadingSessions = ref(false)

async function loadSessions() {
  loadingSessions.value = true
  try {
    const data = await fetchSessions('hr')
    sessions.value = data.sessions

    if (sessions.value.length === 0) {
      activeSessionId.value = ws.sessionId.value || null
      messages.value = []
      return
    }

    const inList = activeSessionId.value
      && sessions.value.some(s => s.session_id === activeSessionId.value)

    if (!inList) {
      await switchToSession(sessions.value[0].session_id)
    }
  } catch {
    /* silent */
  } finally {
    loadingSessions.value = false
  }
}

async function switchToSession(sessionId: string) {
  if (activeSessionId.value === sessionId) return

  activeSessionId.value = sessionId
  sessionStorage.setItem('sessionId', sessionId)

  try {
    const detail = await fetchSessionMessages(sessionId)
    messages.value = detail.messages.map(m => ({
      role: m.role as Message['role'],
      content: m.content,
    }))
    await scrollToBottom()
  } catch {
    messages.value = []
  }

  ws.disconnect()
  ws.connect()
}

async function handleNewSession() {
  ws.newSession()
  activeSessionId.value = null
  messages.value = []
}

async function handleDeleteSession(sessionId: string, e: Event) {
  e.stopPropagation()
  try {
    await deleteSession(sessionId)
    if (activeSessionId.value === sessionId) {
      activeSessionId.value = null
      messages.value = []
      const remaining = sessions.value.filter(s => s.session_id !== sessionId)
      if (remaining.length > 0) {
        await switchToSession(remaining[0].session_id)
      }
    }
    sessions.value = sessions.value.filter(s => s.session_id !== sessionId)
  } catch {
    messages.value.push({ role: 'system', content: '删除会话失败，请重试。' })
  }
}

// --- WS 事件处理 ---

function onStream(payload: any) {
  for (let i = messages.value.length - 1; i >= 0; i--) {
    if (messages.value[i].role === 'assistant') {
      messages.value[i].content += payload.content
      break
    }
  }
  scrollToBottom()
}

function onDone() {
  sending.value = false
  loadSessions()
}

function onError(payload: any) {
  if (sending.value) {
    sending.value = false
    messages.value.push({ role: 'system', content: '抱歉，请求失败：' + (payload?.detail || '未知错误') })
  }
}

function onBusy(payload: any) {
  if (sending.value) {
    const last = messages.value[messages.value.length - 1]
    if (last && last.role === 'assistant' && last.content === '') {
      messages.value.pop()
      messages.value.pop()
    }
    messages.value.push({ role: 'system', content: payload?.detail || '请稍后再试。' })
    sending.value = false
  }
}

function onStructured(payload: StructuredContent) {
  // StructuredMessage 组件仅渲染 match_analysis 类型，其余类型不触发样式回退
  if (payload.response_type !== 'match_analysis') return
  for (let i = messages.value.length - 1; i >= 0; i--) {
    if (messages.value[i].role === 'assistant') {
      messages.value[i].structured = payload
      break
    }
  }
}

function onWsClose(event: CloseEvent) {
  if (sending.value) {
    const len = messages.value.length
    if (len >= 2) {
      const lastTwo = messages.value.slice(-2)
      if (lastTwo[0].role === 'user' && lastTwo[1].role === 'assistant') {
        lastTwo[1].content += ' [连接中断]'
        messages.value.splice(-2, 2)
      }
    }
    messages.value.push({ role: 'system', content: '连接中断，请重新发送您的问题。' })
    sending.value = false
    return
  }

  if (event.code === 1001) {
    messages.value.push({ role: 'system', content: '连接已被其他页面顶替，刷新可重新连接。' })
  }
}

onMounted(() => {
  ws.on('chat.stream', onStream)
  ws.on('chat.done', onDone)
  ws.on('chat.busy', onBusy)
  ws.on('chat.structured', onStructured)
  ws.on('error', onError)
  ws.onClose(onWsClose)

  const stopWatch = watch(() => ws.error.value, (val) => {
    if (val) messages.value.push({ role: 'system', content: val })
  })

  loadSessions()

  onUnmounted(() => {
    stopWatch()
    ws.off('chat.stream', onStream)
    ws.off('chat.done', onDone)
    ws.off('chat.busy', onBusy)
    ws.off('chat.structured', onStructured)
    ws.off('error', onError)
    ws.offClose(onWsClose)
  })
})

// --- 发送消息 ---

async function handleSend() {
  const text = input.value.trim()
  if (!text || sending.value) return

  if (!activeSessionId.value && ws.sessionId.value) {
    activeSessionId.value = ws.sessionId.value
  }

  messages.value.push({ role: 'user', content: text })
  input.value = ''
  sending.value = true
  await scrollToBottom()

  messages.value.push({ role: 'assistant', content: '' })

  const ok = ws.send('chat.request', { content: text, session_id: ws.sessionId.value, agent_type: 'hr' })
  if (!ok) {
    messages.value.pop()
    messages.value.pop()
    messages.value.push({ role: 'system', content: '连接已断开，请稍后重试。' })
    sending.value = false
  }
}

async function scrollToBottom() {
  await nextTick()
  if (chatRef.value) {
    chatRef.value.scrollTop = chatRef.value.scrollHeight
  }
}
</script>

<template>
  <div class="hr-page">
    <h2 class="page-title">HR 面试助手</h2>
    <p class="page-desc">我是你的 HR 专属助手，可以帮你快速了解候选人的技能、项目经验和技术背景。</p>

    <div class="hr-layout">
      <!-- 聊天区 -->
      <div class="chat-card">
        <div class="chat-body" ref="chatRef">
          <div v-if="messages.length === 0" class="chat-empty">
            <span class="empty-icon">&#128101;</span>
            <p>试试问我：这个候选人擅长什么技术？做过哪些项目？</p>
          </div>
          <div
            v-for="(msg, i) in messages"
            :key="i"
            :class="['chat-bubble', msg.role]"
          >
            <StructuredMessage
              v-if="msg.role === 'assistant' && msg.structured"
              :data="msg.structured"
            />
            <div
              :class="msg.structured ? 'msg-text-fallback' : 'msg-text'"
              v-html="renderMarkdown(msg.content)"></div>
          </div>
          <div v-if="sending" class="chat-bubble assistant typing">正在思考...</div>
        </div>
        <div class="chat-footer">
          <div class="input-row">
            <el-input
              v-model="input"
              placeholder="比如：帮我看看候选人 Agent开发 能力怎么样？"
              :disabled="sending"
              @keyup.enter="handleSend"
            />
            <button
              class="send-btn"
              :disabled="!input.trim() || sending"
              @click="handleSend"
            >
              <span v-if="!sending">&#8593;</span>
              <span v-else class="spinner" />
            </button>
          </div>
        </div>
      </div>

      <!-- 会话侧边栏 -->
      <div class="session-sidebar">
        <button class="new-chat-btn" @click="handleNewSession">+ 新对话</button>

        <div class="session-list">
          <div v-if="loadingSessions && sessions.length === 0" class="session-empty">
            加载中...
          </div>
          <div v-else-if="sessions.length === 0" class="session-empty">
            暂无历史会话
          </div>
          <div
            v-for="s in sessions"
            :key="s.session_id"
            :class="['session-card', { active: s.session_id === activeSessionId }]"
            @click="switchToSession(s.session_id)"
          >
            <div class="session-title">{{ s.title }}</div>
            <div class="session-time">{{ s.updated_at.slice(0, 16).replace('T', ' ') }}</div>
            <div class="session-actions">
              <button class="session-more" title="更多操作">&#8943;</button>
              <button
                class="session-delete"
                title="删除会话"
                @click="handleDeleteSession(s.session_id, $event)"
              >删除</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.hr-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 24px;
}

.page-title {
  font-size: 22px;
  font-weight: 600;
  color: #1d1d1f;
  margin: 0 0 6px;
  letter-spacing: -0.3px;
}

.page-desc {
  font-size: 14px;
  color: #86868b;
  margin: 0 0 24px;
}

.hr-layout {
  display: flex;
  gap: 16px;
  flex: 1;
  min-height: 0;
}

/* --- 聊天区 --- */
.chat-card {
  flex: 3;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.chat-empty {
  text-align: center;
  color: #86868b;
  margin-top: 100px;
}

.empty-icon {
  font-size: 40px;
  display: block;
  margin-bottom: 12px;
  opacity: 0.4;
}

.chat-bubble {
  max-width: 92%;
  padding: 8px 14px;
  border-radius: 14px;
  font-size: 14px;
  line-height: 1.45;
  word-break: break-word;
}

.chat-bubble.user {
  align-self: flex-end;
  background: #7c3aed;
  color: #fff;
  border-bottom-right-radius: 4px;
  padding: 6px 16px;
  line-height: 1.4;
}
.chat-bubble.user .msg-text {
  line-height: 1.4;
  display: flex;
  align-items: center;
}
.chat-bubble.user .msg-text :deep(p) { margin: 0; }

.chat-bubble.assistant {
  align-self: flex-start;
  background: #f2f2f7;
  color: #1d1d1f;
  border-bottom-left-radius: 4px;
}

.chat-bubble.system {
  align-self: center;
  background: #fef3c7;
  color: #92400e;
  font-size: 12px;
  border-radius: 8px;
  padding: 6px 14px;
  max-width: 90%;
}

.chat-bubble.typing {
  opacity: 0.5;
  font-style: italic;
}

.msg-text {
  white-space: pre-wrap;
  line-height: 1.5;
}
.msg-text :deep(h1), .msg-text :deep(h2), .msg-text :deep(h3) {
  font-size: 16px;
  font-weight: 600;
  margin: 8px 0 2px;
  color: #1d1d1f;
}
.msg-text :deep(h3) { font-size: 15px; }
.msg-text :deep(p) { margin: 2px 0; }
.msg-text :deep(strong) { font-weight: 600; color: #1d1d1f; }
.msg-text :deep(hr) { border: none; border-top: 1px solid #e5e7eb; margin: 8px 0; }
.msg-text :deep(ul), .msg-text :deep(ol) { margin: 2px 0; padding-left: 20px; }
.msg-text :deep(li) { margin: 1px 0; }
.msg-text :deep(code) {
  background: #f3f4f6;
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 13px;
  font-family: 'SF Mono', 'Fira Code', monospace;
}
.msg-text :deep(blockquote) {
  border-left: 3px solid #7c3aed;
  padding: 4px 12px;
  margin: 8px 0;
  color: #6b7280;
  background: #fafafa;
}
/* markdown 表格 */
.msg-text :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 10px 0;
  font-size: 13px;
}
.msg-text :deep(th) {
  background: #f5f5f7;
  color: #6b7280;
  font-weight: 600;
  text-align: left;
  padding: 8px 12px;
  border-bottom: 2px solid #e5e7eb;
  white-space: nowrap;
}
.msg-text :deep(td) {
  padding: 8px 12px;
  border-bottom: 1px solid #f0f0f0;
  vertical-align: top;
  line-height: 1.5;
}
.msg-text :deep(tr:last-child td) {
  border-bottom: none;
}
.msg-text :deep(tr:hover td) {
  background: #fafafa;
}

.msg-text-fallback {
  font-size: 12px;
  color: #86868b;
  white-space: pre-wrap;
  border-top: 1px solid #f0f0f0;
  padding-top: 8px;
  margin-top: 4px;
}

.chat-footer {
  padding: 14px 20px;
  border-top: 1px solid #f0f0f0;
}

.input-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.input-row :deep(.el-input) {
  flex: 1;
}

.input-row :deep(.el-input__wrapper) {
  border-radius: 22px;
  box-shadow: 0 0 0 1px #d2d2d7 inset;
  padding: 4px 16px;
}

.send-btn {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: none;
  background: #7c3aed;
  color: #fff;
  font-size: 20px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: background 0.15s, transform 0.15s;
}

.send-btn:hover:not(:disabled) {
  background: #6d28d9;
  transform: scale(1.05);
}

.send-btn:disabled {
  background: #d2d2d7;
  cursor: not-allowed;
}

.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
  flex-shrink: 0;
  box-sizing: border-box;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* --- 会话侧边栏 --- */
.session-sidebar {
  flex: 1;
  min-width: 180px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.new-chat-btn {
  width: 100%;
  padding: 10px 0;
  border: 1px dashed #d2d2d7;
  border-radius: 10px;
  background: #fff;
  color: #7c3aed;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s;
}

.new-chat-btn:hover {
  background: #f5f3ff;
}

.session-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.session-empty {
  text-align: center;
  color: #86868b;
  font-size: 12px;
  padding: 20px 0;
}

.session-card {
  padding: 10px 12px;
  border-radius: 10px;
  background: #fff;
  cursor: pointer;
  transition: background 0.15s;
  border: 1px solid transparent;
  position: relative;
}

.session-card:hover {
  background: #f5f5f7;
}

.session-card:hover .session-more {
  display: none;
}

.session-card:hover .session-delete {
  display: inline-block;
}

.session-card.active {
  background: #f5f3ff;
  border-color: #7c3aed;
}

.session-actions {
  position: absolute;
  top: 4px;
  right: 6px;
}

.session-more {
  background: none;
  border: none;
  color: #86868b;
  font-size: 16px;
  cursor: pointer;
  padding: 0 2px;
  line-height: 1;
}

.session-delete {
  display: none;
  background: none;
  border: none;
  color: #ef4444;
  font-size: 12px;
  cursor: pointer;
  padding: 1px 4px;
  border-radius: 4px;
}

.session-delete:hover {
  background: #fef2f2;
}

.session-title {
  font-size: 13px;
  font-weight: 500;
  color: #1d1d1f;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-time {
  font-size: 11px;
  color: #86868b;
  margin-top: 4px;
}
</style>
