<script setup lang="ts">
import { ref, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { useWebSocket } from '../composables/useWebSocket'
import { fetchSessions, fetchSessionMessages, type SessionItem } from '../api/sessions'
import { uploadResume, fetchResumes, deleteResume, type ResumeItem } from '../api/resumes'

interface Message {
  role: 'user' | 'assistant' | 'system'
  content: string
}

const ws = useWebSocket()
const messages = ref<Message[]>([])
const input = ref('')
const sending = ref(false)
const chatRef = ref<HTMLElement>()

// --- 简历 ---
const resumes = ref<ResumeItem[]>([])
const uploadingResume = ref(false)
const fileInput = ref<HTMLInputElement>()

async function loadResumes() {
  try {
    const data = await fetchResumes()
    resumes.value = data.resumes
  } catch { /* silent */ }
}

async function handleUpload(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  uploadingResume.value = true
  const start = Date.now()
  const timer = setInterval(() => {
    const elapsed = Math.round((Date.now() - start) / 1000)
    // 更新侧边栏状态文字
    const card = document.querySelector('.upload-status')
    if (card) card.textContent = `解析中... ${elapsed}s`
  }, 1000)
  try {
    await uploadResume(file)
    await loadResumes()
  } catch {
    messages.value.push({ role: 'system', content: '简历上传失败，请重试。' })
  } finally {
    clearInterval(timer)
    uploadingResume.value = false
    input.value = ''
  }
}

async function handleDeleteResume(id: number) {
  await deleteResume(id)
  await loadResumes()
}

// --- 会话列表 ---
const sessions = ref<SessionItem[]>([])
const activeSessionId = ref<string | null>(null)
const loadingSessions = ref(false)

async function loadSessions() {
  loadingSessions.value = true
  try {
    const data = await fetchSessions()
    sessions.value = data.sessions

    if (sessions.value.length === 0) {
      // 无历史会话：使用当前 WS 的 sessionId 作为新会话
      activeSessionId.value = ws.sessionId.value || null
      messages.value = []
      return
    }

    // 检查当前 activeSessionId 是否在列表中
    const inList = activeSessionId.value
      && sessions.value.some(s => s.session_id === activeSessionId.value)

    if (!inList) {
      // 不在列表中（首次进入 / 清库后 / sessionStorage 里的 ID 已过时）
      // → 默认加载最新的会话
      await switchToSession(sessions.value[0].session_id)
    }
  } catch {
    // 网络异常时静默
  } finally {
    loadingSessions.value = false
  }
}

async function switchToSession(sessionId: string) {
  if (activeSessionId.value === sessionId) return

  activeSessionId.value = sessionId
  sessionStorage.setItem('sessionId', sessionId)

  // 加载该会话的历史消息
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

  // 重连 WS 以切换后端 session/thread
  ws.disconnect()
  ws.connect()
}

async function handleNewSession() {
  ws.newSession()
  activeSessionId.value = null
  messages.value = []
  // newSession 内部调用 disconnect+connect，connect 生成新 UUID 并写入 sessionStorage
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
  // LLM 回复完成后刷新会话列表
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
  ws.on('error', onError)
  ws.onClose(onWsClose)

  const stopWatch = watch(() => ws.error.value, (val) => {
    if (val) messages.value.push({ role: 'system', content: val })
  })

  // 初始加载会话列表 + 简历列表
  loadSessions()
  loadResumes()

  onUnmounted(() => {
    stopWatch()
    ws.off('chat.stream', onStream)
    ws.off('chat.done', onDone)
    ws.off('chat.busy', onBusy)
    ws.off('error', onError)
    ws.offClose(onWsClose)
  })
})

// --- 发送消息 ---

async function handleSend() {
  const text = input.value.trim()
  if (!text || sending.value) return

  // 新会话首次发消息时，记录当前 sessionId
  if (!activeSessionId.value && ws.sessionId.value) {
    activeSessionId.value = ws.sessionId.value
  }

  messages.value.push({ role: 'user', content: text })
  input.value = ''
  sending.value = true
  await scrollToBottom()

  messages.value.push({ role: 'assistant', content: '' })

  const ok = ws.send('chat.request', { content: text, session_id: ws.sessionId.value })
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
  <div class="job-page">
    <h2 class="page-title">AI 求职助手</h2>
    <p class="page-desc">我是你的专属求职助手，可以帮你搜索岗位、分析简历、推荐匹配职位。</p>

    <div class="job-layout">
      <!-- 聊天区 -->
      <div class="chat-card">
        <div class="chat-body" ref="chatRef">
          <div v-if="messages.length === 0" class="chat-empty">
            <span class="empty-icon">&#128188;</span>
            <p>试试问我：帮我找深圳的 Python 后端岗位</p>
          </div>
          <div
            v-for="(msg, i) in messages"
            :key="i"
            :class="['chat-bubble', msg.role]"
          >
            {{ msg.content }}
          </div>
          <div v-if="sending" class="chat-bubble assistant typing">正在思考...</div>
        </div>
        <div class="chat-footer">
          <div class="input-row">
            <label class="upload-btn" :class="{ uploading: uploadingResume }">
              <span v-if="uploadingResume" class="spinner" />
              <span v-else>&#128206;</span>
              <input
                ref="fileInput"
                type="file"
                accept=".pdf"
                style="display:none"
                @change="handleUpload"
              />
            </label>
            <el-input
              v-model="input"
              placeholder="比如：帮我推荐上海的前端开发岗位"
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
          </div>
        </div>

        <!-- 简历分区 -->
        <div class="resume-section">
          <div class="section-header">已上传简历</div>
          <div v-if="uploadingResume" class="resume-card upload-status">
            <span class="spinner" style="width:14px;height:14px;border-width:2px;margin-right:8px" />
            解析中... 0s
          </div>
          <div v-else-if="resumes.length === 0" class="session-empty">暂无简历</div>
          <div
            v-for="r in resumes"
            :key="r.id"
            class="resume-card"
          >
            <span class="resume-name">{{ r.filename }}</span>
            <button class="resume-delete" @click="handleDeleteResume(r.id)">x</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.job-page {
  max-width: 960px;
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

.job-layout {
  display: flex;
  gap: 16px;
  height: 520px;
}

/* --- 聊天区 --- */
.chat-card {
  flex: 1;
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
  gap: 14px;
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
  max-width: 82%;
  padding: 12px 16px;
  border-radius: 14px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}

.chat-bubble.user {
  align-self: flex-end;
  background: #2563eb;
  color: #fff;
  border-bottom-right-radius: 4px;
}

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

.upload-btn {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: none;
  background: #f2f2f7;
  color: #86868b;
  font-size: 18px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: background 0.15s;
}

.upload-btn:hover {
  background: #e5e5ea;
}

.upload-btn.uploading {
  background: #2563eb;
  pointer-events: none;
}

.send-btn {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: none;
  background: #2563eb;
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
  background: #1d4ed8;
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
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* --- 会话侧边栏 --- */
.session-sidebar {
  width: 200px;
  flex-shrink: 0;
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
  color: #2563eb;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s;
}

.new-chat-btn:hover {
  background: #eff6ff;
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
}

.session-card:hover {
  background: #f5f5f7;
}

.session-card.active {
  background: #eff6ff;
  border-color: #2563eb;
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
/* --- 简历分区 --- */
.resume-section {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #f0f0f0;
}

.section-header {
  font-size: 12px;
  font-weight: 600;
  color: #86868b;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}

.resume-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  border-radius: 8px;
  background: #fff;
  margin-bottom: 4px;
}

.resume-name {
  font-size: 12px;
  color: #1d1d1f;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.resume-delete {
  border: none;
  background: none;
  color: #86868b;
  cursor: pointer;
  font-size: 14px;
  padding: 2px 4px;
  flex-shrink: 0;
}

.resume-delete:hover {
  color: #ef4444;
}
</style>
