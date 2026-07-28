import apiClient from './client'

export interface KnowledgeDocItem {
  id: number
  document_name: string
  version: string
  source_file: string
  chunk_count: number
  status: string
  error_message: string | null
  created_at: string
}

export async function uploadKnowledge(file: File): Promise<KnowledgeDocItem> {
  const form = new FormData()
  form.append('file', file)
  return apiClient.post('/knowledge/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }) as Promise<KnowledgeDocItem>
}

export async function fetchKnowledgeDocs(): Promise<{ documents: KnowledgeDocItem[] }> {
  return apiClient.get('/knowledge') as Promise<{ documents: KnowledgeDocItem[] }>
}

export async function deleteKnowledgeDoc(id: number): Promise<void> {
  return apiClient.delete(`/knowledge/${id}`)
}
