import { createRouter, createWebHistory } from 'vue-router'
import { ElMessage } from 'element-plus'
import MainLayout from '../layouts/MainLayout.vue'
import Home from '../views/Home.vue'
import Weather from '../views/Weather.vue'
import JobAssistant from '../views/JobAssistant.vue'
import HRAssistant from '../views/HRAssistant.vue'
import KnowledgeAssistant from '../views/KnowledgeAssistant.vue'
import ResumeViewer from '../views/ResumeViewer.vue'
import UserManagement from '../views/UserManagement.vue'
import Login from '../views/Login.vue'

const routes = [
  {
    path: '/',
    component: MainLayout,
    children: [
      { path: '', name: 'Home', component: Home },
      { path: 'weather', name: 'Weather', component: Weather },
      { path: 'job-assistant', name: 'JobAssistant', component: JobAssistant, meta: { requiresAuth: true } },
      { path: 'hr-assistant', name: 'HRAssistant', component: HRAssistant, meta: { requiresAuth: true } },
      { path: 'knowledge-assistant', name: 'KnowledgeAssistant', component: KnowledgeAssistant, meta: { requiresAuth: true } },
      { path: 'resume', name: 'ResumeViewer', component: ResumeViewer, meta: { requiresAuth: true } },
      { path: 'admin/users', name: 'UserManagement', component: UserManagement, meta: { requiresAuth: true, requiresAdmin: true } },
    ],
  },
  {
    path: '/login',
    name: 'Login',
    component: Login,
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

function getUserRole(): string | null {
  const token = localStorage.getItem('token')
  if (!token) return null
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    return payload.role || 'user'
  } catch {
    return null
  }
}

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')

  if (to.meta.requiresAuth && !token) {
    ElMessage.warning('请先登录后使用求职助手，3 秒后跳转登录页')
    next({ name: 'Home' })
    setTimeout(() => {
      router.push({ name: 'Login', query: { redirect: to.fullPath } })
    }, 3000)
  } else if (to.meta.requiresAdmin && getUserRole() !== 'admin') {
    ElMessage.warning('需要管理员权限')
    next({ name: 'Home' })
  } else if (to.name === 'Login' && token) {
    next({ name: 'Home' })
  } else {
    next()
  }
})

export default router
