<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { healthCheck } from '../api/health'
import { useAuthStore } from '../stores/auth'

interface HealthData {
  status: string
}

const status = ref<string>('')
const authStore = useAuthStore()

onMounted(async () => {
  try {
    const data = await healthCheck() as HealthData
    status.value = data.status
  } catch {
    status.value = '后端未连接'
  }
})
</script>

<template>
  <div class="home">
    <div class="home-header">
      <h1>AI 找工作助手</h1>
      <div class="home-user">
        <span v-if="authStore.user">欢迎，{{ authStore.user.username }}</span>
        <el-button text @click="authStore.logout">退出登录</el-button>
      </div>
    </div>
    <p>后端状态：{{ status || '检测中...' }}</p>
  </div>
</template>

<style scoped>
.home {
  text-align: center;
  margin-top: 80px;
  padding: 0 24px;
}

.home-header {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 24px;
  margin-bottom: 20px;
}

.home-user {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 14px;
  color: #86868b;
}
</style>
