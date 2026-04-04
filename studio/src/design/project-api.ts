import type {
  ProjectSummary,
  ProjectDetail,
  ArtifactRecord,
  RequirementsRecord,
  ProposalRecord,
  ShapeRecord,
  EvaluationRecord,
  VocabularyEntry,
  CreateProject,
  ImportResult,
} from './project-types'
import type { DerivedExpectation } from './shape-types'

// ---------------------------------------------------------------------------
// Core fetch wrapper
// ---------------------------------------------------------------------------

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options?.headers ?? {}),
    },
  })

  if (resp.status === 204) {
    return undefined as T
  }

  if (!resp.ok) {
    const text = await resp.text().catch(() => resp.statusText)
    throw new Error(`API ${options?.method ?? 'GET'} ${path} failed (${resp.status}): ${text}`)
  }

  return resp.json() as Promise<T>
}

// ---------------------------------------------------------------------------
// Projects
// ---------------------------------------------------------------------------

export function listProjects(): Promise<ProjectSummary[]> {
  return api<ProjectSummary[]>('/api/projects')
}

export function getProject(id: string): Promise<ProjectDetail> {
  return api<ProjectDetail>(`/api/projects/${id}`)
}

export function createProject(payload: CreateProject): Promise<ProjectSummary> {
  return api<ProjectSummary>('/api/projects', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateProject(
  id: string,
  payload: Partial<Pick<ProjectSummary, 'name' | 'summary' | 'domain' | 'labels'>>,
): Promise<ProjectSummary> {
  return api<ProjectSummary>(`/api/projects/${id}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function deleteProject(id: string): Promise<void> {
  return api<void>(`/api/projects/${id}`, { method: 'DELETE' })
}

// ---------------------------------------------------------------------------
// Requirements
// ---------------------------------------------------------------------------

export function listRequirements(projectId: string): Promise<RequirementsRecord[]> {
  return api<RequirementsRecord[]>(`/api/projects/${projectId}/requirements`)
}

export function getRequirements(projectId: string, id: string): Promise<RequirementsRecord> {
  return api<RequirementsRecord>(`/api/projects/${projectId}/requirements/${id}`)
}

export function createRequirements(
  projectId: string,
  payload: { id: string; title: string; data: Record<string, any> },
): Promise<RequirementsRecord> {
  return api<RequirementsRecord>(`/api/projects/${projectId}/requirements`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateRequirements(
  projectId: string,
  id: string,
  payload: Partial<{ title: string; status: string; data: Record<string, any> }>,
): Promise<RequirementsRecord> {
  return api<RequirementsRecord>(`/api/projects/${projectId}/requirements/${id}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function deleteRequirements(projectId: string, id: string): Promise<void> {
  return api<void>(`/api/projects/${projectId}/requirements/${id}`, { method: 'DELETE' })
}

export function setRequirementsRole(
  pid: string,
  rid: string,
  role: 'primary' | 'alternative',
): Promise<RequirementsRecord> {
  return api<RequirementsRecord>(`/api/projects/${pid}/requirements/${rid}/role`, {
    method: 'PUT',
    body: JSON.stringify({ role }),
  })
}

// ---------------------------------------------------------------------------
// Scenarios
// ---------------------------------------------------------------------------

export function listScenarios(projectId: string): Promise<ArtifactRecord[]> {
  return api<ArtifactRecord[]>(`/api/projects/${projectId}/scenarios`)
}

export function getScenario(projectId: string, id: string): Promise<ArtifactRecord> {
  return api<ArtifactRecord>(`/api/projects/${projectId}/scenarios/${id}`)
}

export function createScenario(
  projectId: string,
  payload: { id: string; title: string; data: Record<string, any> },
): Promise<ArtifactRecord> {
  return api<ArtifactRecord>(`/api/projects/${projectId}/scenarios`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateScenario(
  projectId: string,
  id: string,
  payload: Partial<{ title: string; status: string; data: Record<string, any> }>,
): Promise<ArtifactRecord> {
  return api<ArtifactRecord>(`/api/projects/${projectId}/scenarios/${id}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function deleteScenario(projectId: string, id: string): Promise<void> {
  return api<void>(`/api/projects/${projectId}/scenarios/${id}`, { method: 'DELETE' })
}

// ---------------------------------------------------------------------------
// Proposals
// ---------------------------------------------------------------------------

export function listProposals(projectId: string): Promise<ProposalRecord[]> {
  return api<ProposalRecord[]>(`/api/projects/${projectId}/proposals`)
}

export function getProposal(projectId: string, id: string): Promise<ProposalRecord> {
  return api<ProposalRecord>(`/api/projects/${projectId}/proposals/${id}`)
}

export function createProposal(
  projectId: string,
  payload: { id: string; title: string; requirements_id: string; data: Record<string, any> },
): Promise<ProposalRecord> {
  return api<ProposalRecord>(`/api/projects/${projectId}/proposals`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateProposal(
  projectId: string,
  id: string,
  payload: Partial<{ title: string; status: string; data: Record<string, any> }>,
): Promise<ProposalRecord> {
  return api<ProposalRecord>(`/api/projects/${projectId}/proposals/${id}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

// ---------------------------------------------------------------------------
// Evaluations
// ---------------------------------------------------------------------------

export interface ListEvaluationsFilter {
  scenario_id?: string
  proposal_id?: string
}

export function listEvaluations(
  projectId: string,
  filter?: ListEvaluationsFilter,
): Promise<EvaluationRecord[]> {
  const params = new URLSearchParams()
  if (filter?.scenario_id) params.set('scenario_id', filter.scenario_id)
  if (filter?.proposal_id) params.set('proposal_id', filter.proposal_id)
  const qs = params.toString()
  return api<EvaluationRecord[]>(
    `/api/projects/${projectId}/evaluations${qs ? `?${qs}` : ''}`,
  )
}

export function createEvaluation(
  projectId: string,
  payload: {
    id: string
    proposal_id?: string | null
    scenario_id: string
    requirements_id: string
    shape_id?: string | null
    source?: string
    data: Record<string, any>
    input_snapshot: Record<string, any>
  },
): Promise<EvaluationRecord> {
  return api<EvaluationRecord>(`/api/projects/${projectId}/evaluations`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function deleteEvaluation(projectId: string, id: string): Promise<void> {
  return api<void>(`/api/projects/${projectId}/evaluations/${id}`, { method: 'DELETE' })
}

// ---------------------------------------------------------------------------
// Shapes
// ---------------------------------------------------------------------------

export function listShapes(projectId: string): Promise<ShapeRecord[]> {
  return api<ShapeRecord[]>(`/api/projects/${projectId}/shapes`)
}

export function getShape(projectId: string, id: string): Promise<ShapeRecord> {
  return api<ShapeRecord>(`/api/projects/${projectId}/shapes/${id}`)
}

export function createShape(
  projectId: string,
  payload: { id: string; title: string; requirements_id: string; data: Record<string, any> },
): Promise<ShapeRecord> {
  return api<ShapeRecord>(`/api/projects/${projectId}/shapes`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateShape(
  projectId: string,
  id: string,
  payload: Partial<{ title: string; status: string; data: Record<string, any> }>,
): Promise<ShapeRecord> {
  return api<ShapeRecord>(`/api/projects/${projectId}/shapes/${id}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function deleteShape(projectId: string, id: string): Promise<void> {
  return api<void>(`/api/projects/${projectId}/shapes/${id}`, { method: 'DELETE' })
}

export async function getShapeExpectations(
  projectId: string,
  id: string,
): Promise<DerivedExpectation[]> {
  const resp = await api<{ expectations: DerivedExpectation[] }>(`/api/projects/${projectId}/shapes/${id}/expectations`)
  return resp.expectations
}

// ---------------------------------------------------------------------------
// Vocabulary
// ---------------------------------------------------------------------------

export interface ListVocabularyFilter {
  category?: string
  project_id?: string
}

export function listVocabulary(filter?: ListVocabularyFilter): Promise<VocabularyEntry[]> {
  const params = new URLSearchParams()
  if (filter?.category) params.set('category', filter.category)
  if (filter?.project_id) params.set('project_id', filter.project_id)
  const qs = params.toString()
  return api<VocabularyEntry[]>(`/api/vocabulary${qs ? `?${qs}` : ''}`)
}

export function createVocabularyEntry(payload: {
  project_id?: string | null
  category: string
  value: string
  origin?: string
  description?: string
}): Promise<VocabularyEntry> {
  return api<VocabularyEntry>('/api/vocabulary', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function deleteVocabularyEntry(id: number): Promise<void> {
  return api<void>(`/api/vocabulary/${id}`, { method: 'DELETE' })
}

// ---------------------------------------------------------------------------
// Import / Export / Seed
// ---------------------------------------------------------------------------

export function importArtifacts(
  projectId: string,
  artifacts: Array<{ type: string; data: Record<string, any> }>,
): Promise<ImportResult> {
  return api<ImportResult>(`/api/projects/${projectId}/import`, {
    method: 'POST',
    body: JSON.stringify({ artifacts }),
  })
}

export function exportProject(projectId: string): Promise<Record<string, any>> {
  return api<Record<string, any>>(`/api/projects/${projectId}/export`)
}

export function seedDatabase(): Promise<{ created_projects: number; skipped: number }> {
  return api<{ created_projects: number; skipped: number }>('/api/seed', { method: 'POST' })
}
