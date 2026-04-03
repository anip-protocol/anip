// Types mirroring the backend Pydantic models for the workspace API.

export interface ProjectSummary {
  id: string
  name: string
  summary: string
  domain: string
  labels: string[]
  created_at: string
  updated_at: string
}

export interface ProjectDetail extends ProjectSummary {
  requirements_count: number
  scenarios_count: number
  proposals_count: number
  evaluations_count: number
}

export interface ArtifactRecord {
  id: string
  project_id: string
  title: string
  status: string
  data: Record<string, any>
  created_at: string
  updated_at: string
}

export interface ProposalRecord extends ArtifactRecord {
  requirements_id: string
}

export interface EvaluationRecord {
  id: string
  project_id: string
  proposal_id: string
  scenario_id: string
  requirements_id: string
  result: string
  source: string
  data: Record<string, any>
  input_snapshot: Record<string, any>
  created_at: string
}

export interface VocabularyEntry {
  id: number
  project_id: string | null
  category: string
  value: string
  origin: 'canonical' | 'project' | 'custom'
  description: string
}

export interface CreateProject {
  id: string
  name: string
  summary?: string
  domain?: string
  labels?: string[]
}

export interface ImportResult {
  imported: number
  errors: string[]
}
