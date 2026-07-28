import apiClient from './client'

export interface SessionItem {
  session_id: string
  title: string
  agent_type: string
  created_at: string
  updated_at: string
}

export interface SessionDetail {
  session_id: string
  title: string
  messages: Array<{ role: string; content: string }>
}

export async function fetchSessions(agentType?: string): Promise<{ sessions: SessionItem[] }> {
  const query = agentType ? `?agent_type=${agentType}` : ''
  return apiClient.get(`/sessions${query}`) as Promise<{ sessions: SessionItem[] }>
}

export async function fetchSessionMessages(sessionId: string): Promise<SessionDetail> {
  return apiClient.get(`/sessions/${sessionId}`) as Promise<SessionDetail>
}

export async function deleteSession(sessionId: string): Promise<void> {
  return apiClient.delete(`/sessions/${sessionId}`)
}

export async function fetchSessionJobs(sessionId: string): Promise<{ jobs: any[] }> {
  return apiClient.get(`/sessions/${sessionId}/jobs`) as Promise<{ jobs: any[] }>
}
