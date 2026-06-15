import apiClient from './client'

interface LoginData {
  token: string
}

export interface UserInfo {
  id: number
  username: string
}

export function loginApi(username: string, password: string) {
  return apiClient.post<LoginData>('/auth/login', { username, password })
}

export function fetchUserInfo() {
  return apiClient.get<UserInfo>('/auth/me')
}
