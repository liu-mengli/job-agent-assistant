import apiClient from './client'
import axios from 'axios'

export interface ResumeItem {
  id: number
  filename: string
  chunk_count: number
  status: string
  error_message: string | null
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

export async function downloadResume(id: number, filename: string): Promise<void> {
  const token = localStorage.getItem('token')
  const baseURL = import.meta.env.VITE_API_BASE_URL
  const resp = await axios.get(`${baseURL}/resumes/${id}/download`, {
    responseType: 'blob',
    headers: { Authorization: `Bearer ${token}` },
  })
  const url = URL.createObjectURL(resp.data)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
