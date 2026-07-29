<script setup lang="ts">
import { ref, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { useWebSocket } from '../composables/useWebSocket'
import { fetchSessions, fetchSessionMessages, fetchSessionJobs, deleteSession, type SessionItem } from '../api/sessions'
import { uploadResume, fetchResumes, deleteResume, type ResumeItem } from '../api/resumes'
import { fetchPreferences, savePreferences, type UserPreferences } from '../api/preferences'
import { uploadJobsJson } from '../api/jobs'
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

// --- 简历 ---
const resumes = ref<ResumeItem[]>([])
const uploadingResume = ref(false)
const processingSeconds = ref(0)
const fileInput = ref<HTMLInputElement>()
let pollTimer: ReturnType<typeof setInterval> | null = null

const hasReadyResume = ref(false)

async function loadResumes() {
  try {
    const data = await fetchResumes()
    resumes.value = data.resumes
    hasReadyResume.value = data.resumes.some(r => r.status === 'ready')
  } catch { /* silent */ }
}

async function handleUpload(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file || hasReadyResume.value) return

  uploadingResume.value = true
  processingSeconds.value = 0

  try {
    const result = await uploadResume(file)
    if (result.status === 'processing') {
      // 后台解析中：不立即刷新列表，开始轮询状态
      pollTimer = setInterval(async () => {
        processingSeconds.value++
        try {
          const data = await fetchResumes()
          const uploaded = data.resumes.find(r => r.id === result.id)
          if (!uploaded || uploaded.status === 'error') {
            clearInterval(pollTimer!)
            pollTimer = null
            uploadingResume.value = false
            messages.value.push({
              role: 'system',
              content: '简历解析失败：' + (uploaded?.error_message || '未知错误'),
            })
          } else if (uploaded.status === 'ready') {
            clearInterval(pollTimer!)
            pollTimer = null
            uploadingResume.value = false
            resumes.value = data.resumes
            hasReadyResume.value = true
          }
          // status === 'processing' → 继续轮询
        } catch {
          // 网络异常，继续轮询
        }
      }, 1000)
    } else {
      // 直接 ready（文字型 PDF 瞬间完成），直接刷新列表
      await loadResumes()
      hasReadyResume.value = true
      uploadingResume.value = false
    }
  } catch {
    messages.value.push({ role: 'system', content: '简历上传失败，请重试。' })
    uploadingResume.value = false
  } finally {
    input.value = ''
  }
}

async function handleDeleteResume(id: number) {
  await deleteResume(id)
  await loadResumes()
  hasReadyResume.value = resumes.value.some(r => r.status === 'ready')
}

// --- 求职偏好 ---
const showPrefForm = ref(false)
const prefLoading = ref(false)
const preferences = ref<UserPreferences>({
  city: null, salary_min: null, salary_max: null,
  job_keywords: null, experience_years: null, company_age: null,
})

async function loadPreferences() {
  try {
    const data = await fetchPreferences()
    if (data) preferences.value = data
  } catch { /* silent */ }
}

async function handleSavePreferences() {
  prefLoading.value = true
  try {
    await savePreferences(preferences.value)
    showPrefForm.value = false
  } catch {
    messages.value.push({ role: 'system', content: '保存偏好失败，请重试。' })
  } finally {
    prefLoading.value = false
  }
}

// --- 上传岗位 JSON ---
const uploadingJobs = ref(false)
const jobsFileInput = ref<HTMLInputElement>()

async function handleUploadJobs(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  uploadingJobs.value = true
  try {
    const result = await uploadJobsJson(file)
    messages.value.push({
      role: 'system',
      content: `岗位上传完成：新增 ${result.new} 条，更新 ${result.update} 条，共 ${result.total} 条`,
    })
  } catch (err: any) {
    messages.value.push({ role: 'system', content: '岗位上传失败：' + (err?.message || '未知错误') })
  } finally {
    uploadingJobs.value = false
    input.value = ''
  }
}

// 偏好选项
const expOptions = [
  { label: '不限', value: '' },
  { label: '在校/应届', value: '在校/应届' },
  { label: '1年以内', value: '1年以内' },
  { label: '1-3年', value: '1-3年' },
  { label: '3-5年', value: '3-5年' },
  { label: '5-10年', value: '5-10年' },
  { label: '10年以上', value: '10年以上' },
]

// --- 会话列表 ---
const sessions = ref<SessionItem[]>([])
const activeSessionId = ref<string | null>(null)
const loadingSessions = ref(false)

async function loadSessions() {
  loadingSessions.value = true
  try {
    const data = await fetchSessions('job_advisor')
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

    // 正在发送消息时不要切换会话，避免覆盖流式回答
    if (!inList && !sending.value) {
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
    await loadJobResultsForSession(sessionId)
    await scrollToBottom()
  } catch {
    messages.value = []
  }

  // 重连 WS 以切换后端 session/thread
  ws.disconnect()
  ws.connect(sessionId)
}

async function handleNewSession() {
  ws.newSession()
  activeSessionId.value = null
  messages.value = []
  jobResults.value = []
  // newSession 内部调用 disconnect+connect，connect 生成新 UUID 并写入 sessionStorage
}

async function handleDeleteSession(sessionId: string, e: Event) {
  e.stopPropagation()  // 防止触发了卡片点击（切换会话）
  try {
    await deleteSession(sessionId)
    // 如果删除的是当前活跃会话，清空聊天区
    if (activeSessionId.value === sessionId) {
      activeSessionId.value = null
      messages.value = []
      // 切换到最新会话
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

async function loadJobResultsForSession(sessionId?: string) {
  const sid = sessionId || activeSessionId.value
  if (!sid) { jobResults.value = []; return }
  try {
    const data = await fetchSessionJobs(sid)
    jobResults.value = data.jobs || []
  } catch { /* 静默 */ }
}

function onDone() {
  loadSessions()
  loadJobResultsForSession()
  sending.value = false
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

// --- 岗位查询结果列表（右侧面板展示）---
const jobResults = ref<StructuredContent['jobs']>([])

function onStructured(payload: StructuredContent) {
  // 右侧面板：用 all_jobs（完整岗位列表，优先）或 jobs
  const all = payload.all_jobs || payload.jobs
  if (all && all.length > 0) {
    jobResults.value = all
  }
  // 聊天区：只有 full_recommendation 和 match_analysis 需要 StructuredMessage 渲染
  const useStructured = payload.response_type === 'full_recommendation' || payload.response_type === 'match_analysis'
  if (!useStructured) return
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

  // 初始加载会话列表 + 简历列表 + 偏好
  loadSessions()
  loadResumes()
  loadPreferences()

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
            <label
              class="upload-btn"
              :class="{ uploading: uploadingResume, disabled: hasReadyResume && !uploadingResume }"
              :title="hasReadyResume ? '已有简历，请先删除再上传' : '上传简历'"
            >
              <span v-if="uploadingResume" class="spinner" />
              <span v-else>&#128206;</span>
              <input
                ref="fileInput"
                type="file"
                accept=".pdf"
                style="display:none"
                :disabled="hasReadyResume"
                @change="handleUpload"
              />
            </label>
            <el-input
              v-model="input"
              placeholder="比如：帮我推荐上海的前端开发岗位"
              :disabled="sending || uploadingResume"
              @keyup.enter="handleSend"
            />
            <button
              class="send-btn"
              :disabled="!input.trim() || sending || uploadingResume"
              @click="handleSend"
            >
              <span v-show="!sending" class="arrow-icon">&#8593;</span>
              <span v-show="sending" class="spinner"></span>
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

        <!-- 求职偏好入口 -->
        <button class="pref-btn" @click="showPrefForm = true">&#9881; 求职偏好</button>
        <label class="pref-btn upload-jobs-btn" :class="{ uploading: uploadingJobs }">
          <span v-if="uploadingJobs" class="spinner" style="width:12px;height:12px;border-width:2px;margin-right:4px" />
          {{ uploadingJobs ? '上传中...' : '📤 上传岗位' }}
          <input
            ref="jobsFileInput"
            type="file"
            accept=".json"
            style="display:none"
            :disabled="uploadingJobs"
            @change="handleUploadJobs"
          />
        </label>

        <!-- 简历分区 -->
        <div class="resume-section">
          <div class="section-header">已上传简历</div>
          <div v-if="uploadingResume" class="resume-card processing">
            <span class="spinner" />
            解析中... {{ processingSeconds }}s
          </div>
          <div v-else-if="resumes.filter(r => r.status !== 'processing').length === 0" class="session-empty">暂无简历</div>
          <div
            v-for="r in resumes.filter(r => r.status !== 'processing')"
            :key="r.id"
            class="resume-card"
          >
            <span class="resume-name">{{ r.filename }}</span>
            <button class="resume-delete" @click="handleDeleteResume(r.id)">x</button>
          </div>
        </div>
      </div>

      <!-- 岗位查询结果面板 -->
      <div class="job-results-panel">
        <div class="panel-header">
          <span>查询结果（{{ jobResults.length }} 条）</span>
        </div>
        <div v-if="jobResults.length === 0" class="panel-empty">
          暂无查询结果，输入筛选条件后自动展示
        </div>
        <el-table
          v-else
          :data="jobResults"
          stripe
          max-height="480"
          size="small"
          class="job-table"
        >
          <el-table-column prop="rank" label="#" width="40" />
          <el-table-column prop="title" label="岗位名称" min-width="140" show-overflow-tooltip />
          <el-table-column prop="company" label="公司" min-width="100" show-overflow-tooltip />
          <el-table-column prop="salary" label="薪资" width="100" />
          <el-table-column prop="experience" label="经验" width="80" />
          <el-table-column prop="company_years" label="司龄" width="60" />
        </el-table>
      </div>
    </div>

    <!-- 求职偏好弹窗 -->
    <div v-if="showPrefForm" class="pref-overlay" @click.self="showPrefForm = false">
      <div class="pref-modal">
        <div class="pref-header">
          <span>求职偏好设置</span>
          <button class="pref-close" @click="showPrefForm = false">&times;</button>
        </div>
        <div class="pref-body">
          <div class="pref-row">
            <label>期望城市</label>
            <input v-model="preferences.city" placeholder="如：深圳、北京" maxlength="50" />
          </div>
          <div class="pref-row">
            <label>薪资范围（元/月）</label>
            <div class="pref-inline">
              <input v-model.number="preferences.salary_min" type="number" placeholder="如：20000" min="0" style="width:48%" />
              <span style="color:#86868b">—</span>
              <input v-model.number="preferences.salary_max" type="number" placeholder="如：35000" min="0" style="width:48%" />
            </div>
          </div>
          <div class="pref-row">
            <label>岗位关键字</label>
            <input v-model="preferences.job_keywords" placeholder="如：Python后端、AI Agent、前端开发" maxlength="50" />
          </div>
          <div class="pref-row">
            <label>经验年限</label>
            <select v-model="preferences.experience_years">
              <option v-for="o in expOptions" :key="o.value" :value="o.value || null">{{ o.label }}</option>
            </select>
          </div>
          <div class="pref-row">
            <label>公司成立时间（年）</label>
            <input v-model.number="preferences.company_age" type="number" placeholder="如：5（成立5年以上）" min="0" style="width:160px" />
          </div>
        </div>
        <div class="pref-footer">
          <button class="pref-cancel-btn" @click="showPrefForm = false">取消</button>
          <button class="pref-save-btn" :disabled="prefLoading" @click="handleSavePreferences">
            <span v-if="prefLoading" class="spinner" style="width:14px;height:14px;border-width:2px;border-color:rgba(255,255,255,0.3);border-top-color:#fff;margin-right:4px" />
            {{ prefLoading ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.job-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  max-width: 100%;
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

.job-layout {
  display: flex;
  gap: 16px;
  flex: 1;
  min-height: 0;
}

/* --- 聊天区 --- */
.chat-card {
  flex: 3;
  min-width: 300px;
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
  background: #2563eb;
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
  border-left: 3px solid #2563eb;
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

.upload-btn:hover:not(.disabled) {
  background: #e5e5ea;
}

.upload-btn.uploading {
  background: #2563eb;
  pointer-events: none;
}

.upload-btn.disabled {
  opacity: 0.4;
  cursor: not-allowed;
  pointer-events: none;
}

.send-btn {
  position: relative;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: none;
  background: #2563eb;
  color: #fff;
  font-size: 20px;
  cursor: pointer;
  flex-shrink: 0;
  transition: background 0.15s, transform 0.15s;
}

.send-btn .arrow-icon,
.send-btn .spinner {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%) rotate(0deg);
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
  display: inline-block;
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
  to { transform: translate(-50%, -50%) rotate(360deg); }
}

/* --- 岗位查询结果面板 --- */
.job-results-panel {
  flex: 3;
  min-width: 300px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-bottom: 1px solid #f0f0f0;
  font-size: 13px;
  font-weight: 600;
  color: #1d1d1f;
  flex-shrink: 0;
}

.panel-close {
  background: none;
  border: none;
  font-size: 20px;
  color: #86868b;
  cursor: pointer;
  padding: 0 2px;
  line-height: 1;
}

.panel-close:hover {
  color: #1d1d1f;
}

.panel-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #9ca3af;
  font-size: 13px;
  padding: 40px 20px;
  text-align: center;
}

.job-table {
  flex: 1;
}

/* --- 会话侧边栏 --- */
.session-sidebar {
  flex: 1;
  min-width: 160px;
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
  background: #eff6ff;
  border-color: #2563eb;
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
/* --- 求职偏好 --- */
.pref-btn {
  width: 100%;
  padding: 8px 0;
  border: none;
  border-radius: 8px;
  background: #f5f5f7;
  color: #1d1d1f;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s;
}

.pref-btn:hover {
  background: #e5e5ea;
}

.upload-jobs-btn {
  display: flex;
  align-items: center;
  justify-content: center;
}

.upload-jobs-btn.uploading {
  background: #2563eb;
  color: #fff;
  pointer-events: none;
}

.pref-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.pref-modal {
  background: #fff;
  border-radius: 16px;
  width: 420px;
  max-height: 80vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.15);
}

.pref-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #f0f0f0;
  font-size: 16px;
  font-weight: 600;
  color: #1d1d1f;
}

.pref-close {
  background: none;
  border: none;
  font-size: 24px;
  color: #86868b;
  cursor: pointer;
  padding: 0;
  line-height: 1;
}

.pref-close:hover {
  color: #1d1d1f;
}

.pref-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.pref-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.pref-row label {
  font-size: 12px;
  font-weight: 500;
  color: #86868b;
}

.pref-row input,
.pref-row select {
  padding: 8px 12px;
  border: 1px solid #d2d2d7;
  border-radius: 8px;
  font-size: 13px;
  color: #1d1d1f;
  background: #fff;
  outline: none;
  transition: border-color 0.15s;
  font-family: inherit;
}

.pref-row input:focus,
.pref-row select:focus {
  border-color: #2563eb;
}

.pref-inline {
  display: flex;
  align-items: center;
  gap: 16px;
}

.pref-footer {
  display: flex;
  justify-content: flex-end;
  gap: 16px;
  padding: 14px 20px;
  border-top: 1px solid #f0f0f0;
}

.pref-cancel-btn {
  padding: 8px 20px;
  border: 1px solid #d2d2d7;
  border-radius: 8px;
  background: #fff;
  color: #1d1d1f;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s;
}

.pref-cancel-btn:hover {
  background: #f5f5f7;
}

.pref-save-btn {
  padding: 8px 20px;
  border: none;
  border-radius: 8px;
  background: #2563eb;
  color: #fff;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  display: flex;
  align-items: center;
  transition: background 0.15s;
}

.pref-save-btn:hover:not(:disabled) {
  background: #1d4ed8;
}

.pref-save-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
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

.resume-card.processing {
  color: #2563eb;
  font-size: 12px;
  font-weight: 500;
  gap: 16px;
}

.resume-card.processing .spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(37, 99, 235, 0.2);
  border-top-color: #2563eb;
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
