import apiClient from './client'

interface ChatData {
  reply: string
}

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export function sendMessage(input: string, history: ChatMessage[] = []) {
  return apiClient.post<ChatData>('/chat', { input, messages: history })
}
