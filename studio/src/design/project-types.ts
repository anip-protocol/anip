// Types mirroring the backend Pydantic models for the workspace API.

export interface WorkspaceSummary {
  id: string
  name: string
  summary: string
  created_at: string
  updated_at: string
}

export interface WorkspaceDetail extends WorkspaceSummary {
  projects_count: number
}

export interface ProjectSummary {
  id: string
  workspace_id: string
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
  shapes_count: number
}

export interface ArtifactRecord {
  id: string
  project_id: string
  title: string
  status: string
  data: Record<string, any>
  content_hash: string
  created_at: string
  updated_at: string
}

export interface RequirementsRecord extends ArtifactRecord {
  role: 'primary' | 'alternative'
}

export interface ProposalRecord extends ArtifactRecord {
  requirements_id: string
}

export interface ShapeRecord extends ArtifactRecord {
  requirements_id: string
}

export interface EvaluationRecord {
  id: string
  project_id: string
  proposal_id: string | null
  scenario_id: string
  requirements_id: string
  shape_id: string | null
  result: string
  source: string
  data: Record<string, any>
  input_snapshot: Record<string, any>
  requirements_hash: string
  proposal_hash: string
  scenario_hash: string
  shape_hash: string
  derived_expectations: Record<string, any> | null
  is_stale: boolean
  stale_artifacts: string[]
  created_at: string
}

export interface VocabularyEntry {
  id: number
  project_id: string | null
  category: string
  value: string
  origin: 'canonical' | 'project' | 'custom'
  evaluator_recognized: boolean
  description: string
}

export interface CreateProject {
  id: string
  workspace_id?: string
  name: string
  summary?: string
  domain?: string
  labels?: string[]
}

export interface ImportResult {
  imported: number
  errors: string[]
}

export interface AssistantExplanation {
  title: string
  summary: string
  focused_answer?: string | null
  highlights: string[]
  watchouts: string[]
  next_steps: string[]
}

export interface IntentInterpretation {
  title: string
  summary: string
  recommended_shape_type: 'single_service' | 'multi_service' | string
  recommended_shape_reason: string
  requirements_focus: string[]
  scenario_starters: string[]
  domain_concepts: string[]
  service_suggestions: string[]
  next_steps: string[]
}

export interface PendingIntentDraft {
  source_intent: string
  interpretation: IntentInterpretation
}
