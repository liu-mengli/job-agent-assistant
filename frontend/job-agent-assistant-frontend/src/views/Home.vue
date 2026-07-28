<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { healthCheck } from '../api/health'
import { useAuthStore } from '../stores/auth'

interface HealthData {
  status: string
}

const status = ref<string>('')
const authStore = useAuthStore()
const router = useRouter()

onMounted(async () => {
  try {
    const data = await healthCheck() as HealthData
    status.value = data.status
  } catch {
    status.value = '未连接'
  }
})

interface ModuleItem {
  label: string
  icon: string
  path: string
  desc: string
}

const allModules: ModuleItem[] = [
  { label: '仪表盘', icon: '⌂', path: '/', desc: '系统运行状态一览' },
  { label: '天气助手', icon: '☀', path: '/weather', desc: '智能天气查询 Demo' },
  { label: '求职助手', icon: '💼', path: '/job-assistant', desc: '岗位匹配与简历优化' },
  { label: 'HR 助手', icon: '👥', path: '/hr-assistant', desc: '智能面试模拟' },
  { label: '知识库', icon: '📚', path: '/knowledge-assistant', desc: '企业 SOP 文档问答' },
  { label: '我的简历', icon: '📋', path: '/resume', desc: '简历查看与管理' },
  { label: '人员管理', icon: '👤', path: '/admin/users', desc: '用户账号管理' },
]

const userModules: ModuleItem[] = [
  { label: 'HR 助手', icon: '👥', path: '/hr-assistant', desc: '快速了解候选人信息' },
  { label: '我的简历', icon: '📋', path: '/resume', desc: '简历查看与下载' },
]

const modules = computed(() => authStore.isAdmin ? allModules : userModules)

function goModule(path: string) {
  if (path !== '/') router.push(path)
}
</script>

<template>
  <div class="dashboard">
    <h2 class="page-title">仪表盘</h2>
    <p class="page-desc">系统运行状态一览</p>

    <!-- 状态卡片 -->
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
        <div class="card-icon">&#9788;</div>
        <div class="card-body">
          <div class="card-label">角色</div>
          <div class="card-value">{{ authStore.isAdmin ? '管理员' : '普通用户' }}</div>
        </div>
      </div>
    </div>

    <!-- 功能模块 -->
    <h3 class="section-title">功能模块</h3>
    <div class="module-grid">
      <div
        v-for="m in modules"
        :key="m.path"
        class="module-card"
        :class="{ clickable: m.path !== '/' }"
        @click="goModule(m.path)"
      >
        <span class="module-icon">{{ m.icon }}</span>
        <div class="module-body">
          <div class="module-label">{{ m.label }}</div>
          <div class="module-desc">{{ m.desc }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard {
  padding: 24px;
}

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
  margin-bottom: 32px;
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

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #1d1d1f;
  margin: 0 0 16px;
}

.module-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 14px;
}

.module-card {
  background: #fff;
  border-radius: 14px;
  padding: 22px 18px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  display: flex;
  align-items: flex-start;
  gap: 14px;
  transition: box-shadow 0.15s, transform 0.15s;
}

.module-card.clickable {
  cursor: pointer;
}

.module-card.clickable:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
  transform: translateY(-2px);
}

.module-icon {
  font-size: 28px;
  width: 40px;
  text-align: center;
  flex-shrink: 0;
}

.module-label {
  font-size: 15px;
  font-weight: 600;
  color: #1d1d1f;
  margin-bottom: 4px;
}

.module-desc {
  font-size: 12px;
  color: #86868b;
}
</style>
