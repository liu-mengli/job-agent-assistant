<script setup lang="ts">
import { watch } from 'vue'
import { useAuthStore } from './stores/auth'
import { useWebSocket } from './composables/useWebSocket'

const authStore = useAuthStore()
const ws = useWebSocket()

// token 变化时自动管理 WS 连接生命周期
watch(
  () => authStore.token,
  (val) => {
    if (val) {
      ws.connect()
    } else {
      ws.disconnect()
    }
  },
  { immediate: true },
)
</script>

<template>
  <router-view />
</template>
