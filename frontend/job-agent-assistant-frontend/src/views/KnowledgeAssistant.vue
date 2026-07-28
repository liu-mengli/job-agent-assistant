<script setup lang="ts">
import { ref, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { useWebSocket } from '../composables/useWebSocket'
import { fetchSessions, fetchSessionMessages, deleteSession, type SessionItem } from '../api/sessions'
import { uploadKnowledge, fetchKnowledgeDocs, deleteKnowledgeDoc, type KnowledgeDocItem } from '../api/knowledge'
import type { StructuredContent } from '../types/structured'
import StructuredMessage from '../components/StructuredMessage.vue'
import { renderMarkdown } from '../utils/markdown'

interface Message {
  role: 'user' | 'assistant' | 'system'
  content: string
  structured?: StructuredContent
}

const previewImage = ref<string | null>(null)

function onImageClick(e: MouseEvent) {
  const target = e.target as HTMLElement
  if (target.tagName === 'IMG') {
    previewImage.value = target.getAttribute('src')
  }
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
    const data = await fetchSessions('kb')
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

// --- 知识库文档 ---
const documents = ref<KnowledgeDocItem[]>([])
const uploadingDoc = ref(false)
const processingSeconds = ref(0)
const fileInput = ref<HTMLInputElement>()
let pollTimer: ReturnType<typeof setInterval> | null = null

async function loadDocuments() {
  try {
    const data = await fetchKnowledgeDocs()
    documents.value = data.documents
    // 有 processing 状态的文档时轮询
    const hasProcessing = data.documents.some(d => d.status === 'processing')
    if (hasProcessing && !pollTimer) {
      startPolling()
    } else if (!hasProcessing && pollTimer) {
      stopPolling()
    }
  } catch { /* silent */ }
}

function startPolling() {
  if (pollTimer) return
  processingSeconds.value = 0
  pollTimer = setInterval(async () => {
    processingSeconds.value++
    await loadDocuments()
  }, 2000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function handleUpload(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  uploadingDoc.value = true
  processingSeconds.value = 0

  try {
    await uploadKnowledge(file)
    startPolling()
    await loadDocuments()
  } catch {
    messages.value.push({ role: 'system', content: '文档上传失败，请重试。' })
  } finally {
    uploadingDoc.value = false
    if (fileInput.value) fileInput.value.value = ''
  }
}

async function handleDeleteDocument(docId: number) {
  try {
    await deleteKnowledgeDoc(docId)
    documents.value = documents.value.filter(d => d.id !== docId)
  } catch {
    messages.value.push({ role: 'system', content: '删除文档失败，请重试。' })
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
  loadDocuments()

  onUnmounted(() => {
    stopWatch()
    stopPolling()
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

  const ok = ws.send('chat.request', { content: text, session_id: ws.sessionId.value, agent_type: 'kb' })
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
  <div class="kb-page">
    <h2 class="page-title">企业知识库助手</h2>
    <p class="page-desc">我是企业知识库问答助手，可以帮你查询 SOP 操作手册、技术规范和流程说明。</p>

    <div class="kb-layout">
      <!-- 聊天区 -->
      <div class="chat-card">
        <div class="chat-body" ref="chatRef">
          <div v-if="messages.length === 0" class="chat-empty">
            <span class="empty-icon">📚</span>
            <p>试试问我：主画面有哪些操作按钮？Offset 参数怎么设置？</p>
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
              v-html="renderMarkdown(msg.content)"
              @click="onImageClick"
            ></div>
          </div>
          <div v-if="sending" class="chat-bubble assistant typing">正在检索知识库...</div>
        </div>
        <div class="chat-footer">
          <div class="input-row">
            <!-- 上传按钮 -->
            <label class="upload-btn" title="上传 SOP 文档 (.doc/.docx)">
              <input
                ref="fileInput"
                type="file"
                accept=".doc,.docx"
                hidden
                :disabled="uploadingDoc"
                @change="handleUpload"
              />
              <span v-if="uploadingDoc" class="spinner" />
              <span v-else>📎</span>
            </label>
            <el-input
              v-model="input"
              placeholder="比如：主画面如何操作？Offset 参数怎么设置？"
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

      <!-- 右侧面板 -->
      <div class="right-panel">
        <!-- 会话 -->
        <div class="panel-section session-section">
          <button class="new-chat-btn" @click="handleNewSession">+ 新对话</button>
          <div class="scroll-list">
            <div v-if="loadingSessions && sessions.length === 0" class="list-empty">加载中...</div>
            <div v-else-if="sessions.length === 0" class="list-empty">暂无历史会话</div>
            <div
              v-for="s in sessions"
              :key="s.session_id"
              :class="['list-card', { active: s.session_id === activeSessionId }]"
              @click="switchToSession(s.session_id)"
            >
              <div class="card-title">{{ s.title }}</div>
              <div class="card-time">{{ s.updated_at.slice(0, 16).replace('T', ' ') }}</div>
              <div class="card-actions">
                <button class="card-more">&#8943;</button>
                <button class="card-delete" @click="handleDeleteSession(s.session_id, $event)">删除</button>
              </div>
            </div>
          </div>
        </div>

        <!-- 文档列表 -->
        <div class="panel-section doc-section">
          <h4 class="section-title">📄 SOP 文档</h4>
          <div class="scroll-list">
            <div v-if="documents.length === 0 && !uploadingDoc" class="list-empty">
              暂无文档，点击输入框旁的 📎 上传
            </div>
            <div
              v-for="doc in documents"
              :key="doc.id"
              class="list-card doc-card"
            >
              <div class="card-title">{{ doc.document_name }}</div>
              <div class="card-sub">
                <template v-if="doc.status === 'processing'">
                  <span class="status-tag processing">解析中... {{ processingSeconds }}s</span>
                </template>
                <template v-else-if="doc.status === 'ready'">
                  <span class="status-tag ready">已就绪 · {{ doc.chunk_count }} 切片</span>
                </template>
                <template v-else>
                  <span class="status-tag error" :title="doc.error_message || ''">失败</span>
                </template>
              </div>
              <div class="card-actions">
                <button class="card-delete" @click="handleDeleteDocument(doc.id)">删除</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 图片灯箱 -->
    <div v-if="previewImage" class="img-lightbox" @click="previewImage = null">
      <img :src="previewImage" class="img-lightbox-content" @click.stop />
    </div>
  </div>
</template>

<style scoped>
.kb-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  max-width: 960px;
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

.kb-layout {
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
  background: #059669;
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
  border-left: 3px solid #059669;
  padding: 4px 12px;
  margin: 8px 0;
  color: #6b7280;
  background: #fafafa;
}
.msg-text :deep(img) {
  max-width: 100%;
  max-height: 360px;
  border-radius: 10px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  margin: 8px 0;
  cursor: pointer;
  transition: transform 0.2s;
}
.msg-text :deep(img:hover) {
  transform: scale(1.02);
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

.upload-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: 16px;
  background: #f3f4f6;
  transition: background 0.15s;
  flex-shrink: 0;
}

.upload-btn:hover {
  background: #d1fae5;
}

.upload-btn .spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(0,0,0,0.15);
  border-top-color: #059669;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
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
  background: #059669;
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
  background: #047857;
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

/* --- 右侧面板 --- */
.right-panel {
  flex: 1;
  min-width: 180px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.panel-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.session-section {
  flex: 1;
  min-height: 0;
}

.doc-section {
  flex: 0 0 auto;
  max-height: 180px;
}

.section-title {
  font-size: 12px;
  font-weight: 600;
  color: #86868b;
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.scroll-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.list-empty {
  text-align: center;
  color: #86868b;
  font-size: 12px;
  padding: 12px 0;
}

.new-chat-btn {
  width: 100%;
  padding: 10px 0;
  border: 1px dashed #d2d2d7;
  border-radius: 10px;
  background: #fff;
  color: #059669;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s;
  flex-shrink: 0;
}

.new-chat-btn:hover {
  background: #ecfdf5;
}

.list-card {
  padding: 8px 10px;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  transition: background 0.15s;
  border: 1px solid transparent;
  position: relative;
}

.list-card:hover {
  background: #f5f5f7;
}

.list-card:hover .card-more {
  display: none;
}

.list-card:hover .card-delete {
  display: inline-block;
}

.list-card.active {
  background: #ecfdf5;
  border-color: #059669;
}

.doc-card {
  cursor: default;
}

.card-title {
  font-size: 12px;
  font-weight: 500;
  color: #1d1d1f;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-time {
  font-size: 11px;
  color: #86868b;
  margin-top: 2px;
}

.card-sub {
  font-size: 11px;
  margin-top: 2px;
}

.status-tag {
  font-size: 11px;
}

.status-tag.processing {
  color: #d97706;
}

.status-tag.ready {
  color: #059669;
}

.status-tag.error {
  color: #ef4444;
}

.card-actions {
  position: absolute;
  top: 4px;
  right: 4px;
}

.card-more {
  background: none;
  border: none;
  color: #86868b;
  font-size: 14px;
  cursor: pointer;
  padding: 0 2px;
  line-height: 1;
}

.card-delete {
  display: none;
  background: none;
  border: none;
  color: #ef4444;
  font-size: 11px;
  cursor: pointer;
  padding: 1px 4px;
  border-radius: 4px;
}

.card-delete:hover {
  background: #fef2f2;
}

/* --- 消息图片 --- */
.msg-image {
  display: block;
  max-width: 100%;
  max-height: 360px;
  border-radius: 8px;
  margin: 8px 0;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
}

.msg-image:hover {
  transform: scale(1.02);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

/* --- 图片灯箱 --- */
.img-lightbox {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.85);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  cursor: pointer;
}

.img-lightbox-content {
  max-width: 92vw;
  max-height: 92vh;
  border-radius: 8px;
  cursor: default;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}
</style>
