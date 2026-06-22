<script setup lang="ts">
import { ref, nextTick, onMounted, onUnmounted } from 'vue'
import { useWebSocket } from '../composables/useWebSocket'

interface Message {
  role: 'user' | 'assistant' | 'system'
  content: string
}

const ws = useWebSocket()
const messages = ref<Message[]>([])
const input = ref('')
const sending = ref(false)
const chatRef = ref<HTMLElement>()

// --- WS 事件处理 ---

function onStream(payload: any) {
  // payload.content 是一个 token 片段，追加到最后一条 assistant 消息上
  // 从后往前找最近一条 assistant 消息（避免 system 通知干扰）
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
}

function onError(payload: any) {
  // 仅在流式回复过程中才弹错误提示
  if (sending.value) {
    sending.value = false
    messages.value.push({ role: 'system', content: '抱歉，请求失败：' + (payload?.detail || '未知错误') })
  }
}

function onBusy(payload: any) {
  // 后端 Agent 正忙，回滚 handleSend 预埋的消息对
  if (sending.value) {
    // pop 掉空的 assistant 和用户消息（handleSend 预埋的）
    const last = messages.value[messages.value.length - 1]
    if (last && last.role === 'assistant' && last.content === '') {
      messages.value.pop()  // 空的 assistant
      messages.value.pop()  // 用户消息
    }
    messages.value.push({ role: 'system', content: payload?.detail || '请稍后再试。' })
    sending.value = false
  }
}

function onWsClose(event: CloseEvent) {
  if (sending.value) {
    // 流式回复过程中断连：清理未完成的消息对
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

  // 非发送过程中被踢（如另一个标签页连接顶替）：即时告知用户
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
})

onUnmounted(() => {
  ws.off('chat.stream', onStream)
  ws.off('chat.done', onDone)
  ws.off('chat.busy', onBusy)
  ws.off('error', onError)
  ws.offClose(onWsClose)
})

// --- 发送消息 ---

async function handleSend() {
  const text = input.value.trim()
  if (!text || sending.value) return

  messages.value.push({ role: 'user', content: text })
  input.value = ''
  sending.value = true
  await scrollToBottom()

  // 初始化一条空的 assistant 消息，后续由 chat.stream 事件填充
  messages.value.push({ role: 'assistant', content: '' })

  // 构建历史：过滤掉系统通知，只保留用户和助手的对话
  const conversation = messages.value.filter(m => m.role !== 'system')
  const history = conversation.slice(0, -2) // 去掉刚加的 user + 空的 assistant
  const ok = ws.send('chat.request', { content: text, messages: history })
  if (!ok) {
    // 发送失败：回滚消息数组，解锁输入框
    messages.value.pop()  // 去掉空的 assistant
    messages.value.pop()  // 去掉本次用户消息
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
    <p class="page-desc">我是你的专属求职助手，可以帮你搜索岗位、分析简历、推荐匹配职位。告诉我你的需求吧。</p>

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
  </div>
</template>

<style scoped>
.job-page {
  max-width: 720px;
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

.chat-card {
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  height: 520px;
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
</style>
