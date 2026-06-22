<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()

const items = [
  { path: '/', label: '仪表盘', icon: '⌂' },
  { path: '/weather', label: '天气助手', icon: '☀' },
  { path: '/job-assistant', label: '求职助手', icon: '💼' },
]
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
