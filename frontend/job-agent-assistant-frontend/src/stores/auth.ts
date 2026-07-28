import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { loginApi, registerApi, fetchUserInfo, type UserInfo } from '../api/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const user = ref<UserInfo | null>(null)
  const router = useRouter()

  const isAdmin = computed(() => user.value?.role === 'admin')

  async function init() {
    if (token.value && !user.value) {
      try {
        user.value = await fetchUserInfo()
      } catch {
        token.value = ''
        localStorage.removeItem('token')
      }
    }
  }

  async function login(username: string, password: string): Promise<boolean> {
    try {
      const data = await loginApi(username, password)
      token.value = data.token
      localStorage.setItem('token', token.value)
      user.value = await fetchUserInfo()
      return true
    } catch {
      return false
    }
  }

  async function register(username: string, password: string): Promise<boolean> {
    try {
      const data = await registerApi(username, password)
      token.value = data.token
      localStorage.setItem('token', token.value)
      user.value = { id: (data as any).id, username: (data as any).username, role: (data as any).role || 'user' }
      return true
    } catch {
      return false
    }
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('sessionId')
    router.push('/login')
  }

  return { token, user, isAdmin, init, login, register, logout }
})
