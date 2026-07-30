<script setup lang="ts">
import { watch } from 'vue'
import { useAuthStore } from './stores/auth'
import { useWebSocket } from './composables/useWebSocket'

const authStore = useAuthStore()
const ws = useWebSocket()

// token 变化时自动管理 WS 连接生命周期
watch(
  () => authStore.token,
  async (val) => {
    if (val) {
      await ws.connect()
    } else {
      ws.disconnect()
    }
  },
  { immediate: true },
)

// 根据角色动态更新网页标题
watch(
  () => authStore.user,
  (u) => {
    if (!u) {
      document.title = 'AI HR助手'
    } else if (u.role === 'admin') {
      document.title = 'AI 找工作助手'
    } else {
      document.title = 'AI HR助手'
    }
  },
  { immediate: true },
)
</script>

<template>
  <router-view />
</template>
