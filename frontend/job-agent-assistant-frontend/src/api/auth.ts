import apiClient from './client'

interface AuthData {
  token: string
}

export interface UserInfo {
  id: number
  username: string
  role: string
}

export function loginApi(username: string, password: string) {
  return apiClient.post<AuthData & { role: string }>('/auth/login', { username, password })
}

export function registerApi(username: string, password: string) {
  return apiClient.post<AuthData & { role: string }>('/auth/register', { username, password })
}

export function fetchUserInfo() {
  return apiClient.get<UserInfo>('/auth/me')
}
