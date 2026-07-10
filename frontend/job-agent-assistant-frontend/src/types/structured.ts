/** 岗位条目 */
export interface JobItem {
  rank: number
  title: string
  company: string
  salary: string
  experience: string
  match_score?: number | null
  reason: string
}

/** 技能逐项对比 */
export interface SkillComparison {
  requirement: string
  match_level: 'match' | 'partial' | 'missing'
  your_status: string
  note: string
}

/** 后端 format_response_node 输出的结构化数据 */
export interface StructuredContent {
  response_type: 'greeting' | 'browse' | 'full_recommendation' | 'match_analysis' | 'resume_optimization' | 'resume_analysis' | 'general'

  // 共用
  summary?: string | null
  content?: string | null

  // browse / full_recommendation
  jobs?: JobItem[] | null
  assessment?: string | null
  next_steps?: string | null

  // match_analysis
  overall_match?: number | null
  match_summary?: string | null
  skill_comparisons?: SkillComparison[] | null
  strengths?: string[] | null
  weaknesses?: string[] | null
  application_advice?: string | null

  // resume_optimization
  highlights?: Record<string, string>[] | null
  keywords_to_add?: Record<string, string>[] | null
  improvements?: Record<string, string>[] | null
  to_remove?: string[] | null
  example_revision?: Record<string, string> | null

  // greeting
  greeting_short?: string | null
  greeting_standard?: string | null
  self_intro?: string | null
  advantage_lines?: string[] | null

  // resume_analysis
  basic_info?: Record<string, string> | null
  skill_matrix?: Record<string, string>[] | null
  projects?: Record<string, string>[] | null
  positioning?: string | null

  // general
  suggestions?: string[] | null
  guidance_tip?: string | null
}
