import apiClient from './client'

export interface SessionItem {
  session_id: string
  title: string
  created_at: string
  updated_at: string
}

export interface SessionDetail {
  session_id: string
  title: string
  messages: Array<{ role: string; content: string }>
}

export async function fetchSessions(): Promise<{ sessions: SessionItem[] }> {
  return apiClient.get('/sessions') as Promise<{ sessions: SessionItem[] }>
}

export async function fetchSessionMessages(sessionId: string): Promise<SessionDetail> {
  return apiClient.get(`/sessions/${sessionId}`) as Promise<SessionDetail>
}

export async function deleteSession(sessionId: string): Promise<void> {
  return apiClient.delete(`/sessions/${sessionId}`)
}
