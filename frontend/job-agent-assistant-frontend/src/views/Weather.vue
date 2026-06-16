<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { sendMessage } from '../api/chat'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

const messages = ref<Message[]>([])
const input = ref('')
const sending = ref(false)
const chatRef = ref<HTMLElement>()

async function handleSend() {
  const text = input.value.trim()
  if (!text || sending.value) return

  messages.value.push({ role: 'user', content: text })
  input.value = ''
  sending.value = true
  await scrollToBottom()

  try {
    // 把历史消息（不含最后一条用户消息）传给后端，实现多轮对话
    const history = messages.value.slice(0, -1)
    const data = await sendMessage(text, history) as { reply: string }
    messages.value.push({ role: 'assistant', content: data.reply })
  } catch {
    messages.value.push({ role: 'assistant', content: '抱歉，请求失败，请稍后重试。' })
  } finally {
    sending.value = false
    await scrollToBottom()
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
  <div class="weather-page">
    <h2 class="page-title">天气助手</h2>
    <p class="page-desc">我是你的专属天气助手，基于模拟数据回答。支持查询：北京 · 深圳 · 上海 · 广州 · 成都</p>

    <div class="chat-card">
      <div class="chat-body" ref="chatRef">
        <div v-if="messages.length === 0" class="chat-empty">
          <span class="empty-icon">&#9728;</span>
          <p>试试问我今天某个城市的天气吧</p>
        </div>
        <div
          v-for="(msg, i) in messages"
          :key="i"
          :class="['chat-bubble', msg.role]"
        >
          {{ msg.content }}
        </div>
        <div v-if="sending" class="chat-bubble assistant typing">正在查询...</div>
      </div>
      <div class="chat-footer">
        <div class="input-row">
          <el-input
            v-model="input"
            placeholder="比如：深圳今天天气怎么样？"
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
.weather-page {
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
