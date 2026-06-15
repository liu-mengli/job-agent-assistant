import apiClient from './client'

export function healthCheck() {
  return apiClient.get('/health')
}
