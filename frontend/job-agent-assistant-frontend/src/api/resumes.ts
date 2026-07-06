import apiClient from './client'

export interface ResumeItem {
  id: number
  filename: string
  chunk_count: number
  created_at: string
}

export async function uploadResume(file: File): Promise<ResumeItem> {
  const form = new FormData()
  form.append('file', file)
  return apiClient.post('/resumes/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }) as Promise<ResumeItem>
}

export async function fetchResumes(): Promise<{ resumes: ResumeItem[] }> {
  return apiClient.get('/resumes') as Promise<{ resumes: ResumeItem[] }>
}

export async function deleteResume(id: number): Promise<void> {
  return apiClient.delete(`/resumes/${id}`)
}
