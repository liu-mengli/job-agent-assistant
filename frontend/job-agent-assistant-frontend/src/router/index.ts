import { createRouter, createWebHistory } from 'vue-router'
import MainLayout from '../layouts/MainLayout.vue'
import Home from '../views/Home.vue'
import Weather from '../views/Weather.vue'
import JobAssistant from '../views/JobAssistant.vue'
import Login from '../views/Login.vue'

const routes = [
  {
    path: '/',
    component: MainLayout,
    meta: { requiresAuth: true },
    children: [
      { path: '', name: 'Home', component: Home },
      { path: 'weather', name: 'Weather', component: Weather },
      { path: 'job-assistant', name: 'JobAssistant', component: JobAssistant },
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

// 路由守卫：未登录跳转到登录页
router.beforeEach((to) => {
  const token = sessionStorage.getItem('token')
  if (to.meta.requiresAuth && !token) {
    return '/login'
  }
})

export default router
