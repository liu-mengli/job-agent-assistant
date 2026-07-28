<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const authStore = useAuthStore()

const allItems = [
  { path: '/', label: '仪表盘', icon: '⌂' },
  { path: '/weather', label: '天气助手', icon: '☀' },
  { path: '/job-assistant', label: '求职助手', icon: '💼' },
  { path: '/hr-assistant', label: 'HR 助手', icon: '👥' },
  { path: '/knowledge-assistant', label: '知识库', icon: '📚' },
  { path: '/resume', label: '我的简历', icon: '📋' },
  { path: '/admin/users', label: '人员管理', icon: '👤' },
]

const items = computed(() => {
  if (authStore.isAdmin) return allItems
  return allItems.filter(item =>
    item.path === '/' || item.path === '/hr-assistant' || item.path === '/resume'
  )
})
</script>

<template>
  <nav class="sidenav">
    <router-link
      v-for="item in items"
      :key="item.path"
      :to="item.path"
      :class="['nav-item', { active: route.path === item.path }]"
    >
      <span class="nav-icon">{{ item.icon }}</span>
      <span class="nav-label">{{ item.label }}</span>
    </router-link>
  </nav>
</template>

<style scoped>
.sidenav {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 20px 12px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
  color: #1d1d1f;
  text-decoration: none;
  transition: background 0.15s;
}

.nav-item:hover {
  background: rgba(0, 0, 0, 0.04);
}

.nav-item.active {
  background: rgba(37, 99, 235, 0.1);
  color: #2563eb;
}

.nav-icon {
  font-size: 18px;
  width: 24px;
  text-align: center;
}
</style>
