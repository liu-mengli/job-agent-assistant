import apiClient from './client'

export interface UserPreferences {
  city: string | null
  work_mode: string | null
  salary_min: number | null
  salary_max: number | null
  industry: string | null
  company_size: string | null
  tech_stack: string | null
  deal_breakers: string | null
  experience_years: number | null
  job_status: string | null
}

export async function fetchPreferences(): Promise<UserPreferences | null> {
  return apiClient.get('/preferences') as Promise<UserPreferences | null>
}

export async function savePreferences(data: UserPreferences): Promise<void> {
  return apiClient.put('/preferences', data)
}
