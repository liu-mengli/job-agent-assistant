<script setup lang="ts">
import { useAuthStore } from '../stores/auth'
import SideNav from '../components/SideNav.vue'

const authStore = useAuthStore()
</script>

<template>
  <div class="layout">
    <!-- Header -->
    <header class="header">
      <div class="header-brand">AI 找工作助手</div>
      <div class="header-right">
        <span v-if="authStore.user" class="header-user">{{ authStore.user.username }}</span>
        <button class="header-btn" @click="authStore.logout">退出登录</button>
      </div>
    </header>

    <!-- Body -->
    <div class="body">
      <aside class="sidebar">
        <SideNav />
      </aside>
      <main class="content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<style scoped>
.layout {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f5f5f7;
}

/* Header */
.header {
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  flex-shrink: 0;
}

.header-brand {
  font-size: 16px;
  font-weight: 600;
  color: #1d1d1f;
  letter-spacing: -0.3px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 14px;
}

.header-user {
  font-size: 13px;
  color: #86868b;
}

.header-btn {
  font-size: 13px;
  color: #2563eb;
  background: none;
  border: none;
  cursor: pointer;
}

.header-btn:hover {
  text-decoration: underline;
}

/* Body */
.body {
  flex: 1;
  display: flex;
  min-height: 0;
}

.sidebar {
  width: 200px;
  flex-shrink: 0;
  background: rgba(255, 255, 255, 0.56);
  border-right: 1px solid rgba(0, 0, 0, 0.05);
}

.content {
  flex: 1;
  overflow-y: auto;
  padding: 28px 32px;
}
</style>
