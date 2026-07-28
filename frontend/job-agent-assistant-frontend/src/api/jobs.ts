import apiClient from './client'

export async function uploadJobsJson(file: File): Promise<{ new: number; update: number; total: number }> {
  const form = new FormData()
  form.append('file', file)
  return apiClient.post('/jobs/upload-json', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }) as Promise<{ new: number; update: number; total: number }>
}
