import apiClient from './client'

export interface AdminUser {
  id: number
  username: string
  password: string
  role: string
}

export async function fetchUsers(): Promise<{ users: AdminUser[] }> {
  return apiClient.get('/admin/users') as Promise<{ users: AdminUser[] }>
}

export async function deleteUser(userId: number): Promise<void> {
  return apiClient.delete(`/admin/users/${userId}`)
}
