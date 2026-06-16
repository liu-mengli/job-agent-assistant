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
    status.value = '未连接'
  }
})
</script>

<template>
  <div class="dashboard">
    <h2 class="page-title">仪表盘</h2>
    <p class="page-desc">系统运行状态一览</p>

    <div class="cards">
      <div class="card">
        <div class="card-icon">&#9881;</div>
        <div class="card-body">
          <div class="card-label">后端状态</div>
          <div class="card-value">
            <span :class="['dot', status === 'OK' ? 'ok' : 'fail']" />
            {{ status === 'OK' ? '运行中' : '未连接' }}
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-icon">&#9733;</div>
        <div class="card-body">
          <div class="card-label">已登录</div>
          <div class="card-value">{{ authStore.user?.username || '-' }}</div>
        </div>
      </div>

      <div class="card">
        <div class="card-icon">&#9789;</div>
        <div class="card-body">
          <div class="card-label">功能模块</div>
          <div class="card-value">天气助手 Demo</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-title {
  font-size: 22px;
  font-weight: 600;
  color: #1d1d1f;
  margin: 0 0 4px;
  letter-spacing: -0.3px;
}

.page-desc {
  font-size: 14px;
  color: #86868b;
  margin: 0 0 28px;
}

.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px;
}

.card {
  background: #fff;
  border-radius: 14px;
  padding: 22px 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  display: flex;
  align-items: flex-start;
  gap: 16px;
}

.card-icon {
  font-size: 26px;
  opacity: 0.6;
  width: 36px;
  text-align: center;
}

.card-label {
  font-size: 12px;
  color: #86868b;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 4px;
}

.card-value {
  font-size: 16px;
  font-weight: 600;
  color: #1d1d1f;
  display: flex;
  align-items: center;
  gap: 6px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}
.dot.ok { background: #34c759; }
.dot.fail { background: #ff3b30; }
</style>
