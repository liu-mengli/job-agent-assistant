import apiClient from './client'

export interface UserPreferences {
  city: string | null
  salary_min: number | null
  salary_max: number | null
  job_keywords: string | null
  experience_years: string | null
  company_age: number | null
}

export async function fetchPreferences(): Promise<UserPreferences | null> {
  return apiClient.get('/preferences') as Promise<UserPreferences | null>
}

export async function savePreferences(data: UserPreferences): Promise<void> {
  return apiClient.put('/preferences', data)
}
