import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { loginApi, fetchUserInfo, type UserInfo } from '../api/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(sessionStorage.getItem('token') || '')
  const user = ref<UserInfo | null>(null)
  const router = useRouter()

  async function init() {
    if (token.value && !user.value) {
      try {
        user.value = await fetchUserInfo()
      } catch {
        token.value = ''
        sessionStorage.removeItem('token')
      }
    }
  }

  async function login(username: string, password: string): Promise<boolean> {
    try {
      const data = await loginApi(username, password)
      token.value = data.token
      sessionStorage.setItem('token', token.value)
      // 登录后拉取用户信息
      user.value = await fetchUserInfo()
      return true
    } catch {
      return false
    }
  }

  function logout() {
    token.value = ''
    user.value = null
    sessionStorage.removeItem('token')
    router.push('/login')
  }

  return { token, user, init, login, logout }
})
