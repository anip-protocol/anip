import type {
  WorkspaceSummary,
  WorkspaceDetail,
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
  AssistantExplanation,
  IntentInterpretation,
} from './project-types'
import type { DerivedExpectation } from './shape-types'
import { issueCapabilityToken, invokeCapability } from '../api'

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

const STUDIO_ASSISTANT_BASE_URL = '/studio-assistant'
const STUDIO_ASSISTANT_BOOTSTRAP = 'studio-assistant-bootstrap'
const STUDIO_ASSISTANT_SCOPE_BY_CAPABILITY: Record<string, string> = {
  explain_shape: 'studio.assistant.explain_shape',
  explain_evaluation: 'studio.assistant.explain_evaluation',
  interpret_project_intent: 'studio.assistant.interpret_project_intent',
}

const assistantTokens: Record<string, string | undefined> = {}

async function ensureAssistantToken(capability: string, forceRefresh = false): Promise<string> {
  if (assistantTokens[capability] && !forceRefresh) return assistantTokens[capability] as string
  const scope = STUDIO_ASSISTANT_SCOPE_BY_CAPABILITY[capability]
  if (!scope) {
    throw new Error(`Unsupported Studio assistant capability: ${capability}`)
  }
  const issued = await issueCapabilityToken(
    STUDIO_ASSISTANT_BASE_URL,
    STUDIO_ASSISTANT_BOOTSTRAP,
    'studio-ui',
    capability,
    [scope],
    { ttl_hours: 8 },
  )
  if (!issued?.issued || !issued?.token) {
    const detail = issued?.failure?.detail || 'Failed to issue Studio assistant token'
    throw new Error(detail)
  }
  const token = issued.token as string
  assistantTokens[capability] = token
  return token
}

async function invokeAssistant<T>(capability: string, parameters: Record<string, any>): Promise<T> {
  let token = await ensureAssistantToken(capability)
  let result = await invokeCapability(STUDIO_ASSISTANT_BASE_URL, token, capability, parameters)

  if (!result?.success && result?.failure?.type === 'invalid_token') {
    token = await ensureAssistantToken(capability, true)
    result = await invokeCapability(STUDIO_ASSISTANT_BASE_URL, token, capability, parameters)
  }

  if (!result?.success) {
    const detail = result?.failure?.detail || `Assistant capability ${capability} failed`
    throw new Error(detail)
  }

  return result.result as T
}

// ---------------------------------------------------------------------------
// Workspaces
// ---------------------------------------------------------------------------

export function listWorkspaces(): Promise<WorkspaceDetail[]> {
  return api<WorkspaceDetail[]>('/api/workspaces')
}

export function getWorkspace(id: string): Promise<WorkspaceDetail> {
  return api<WorkspaceDetail>(`/api/workspaces/${id}`)
}

export function createWorkspace(payload: { id: string; name: string; summary?: string }): Promise<WorkspaceSummary> {
  return api<WorkspaceSummary>('/api/workspaces', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function deleteWorkspace(id: string): Promise<void> {
  return api<void>(`/api/workspaces/${id}`, { method: 'DELETE' })
}

// ---------------------------------------------------------------------------
// Projects
// ---------------------------------------------------------------------------

export function listProjects(workspaceId?: string): Promise<ProjectSummary[]> {
  const qs = workspaceId ? `?workspace_id=${encodeURIComponent(workspaceId)}` : ''
  return api<ProjectSummary[]>(`/api/projects${qs}`)
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
// Import / Export
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

// ---------------------------------------------------------------------------
// Studio Assistant (ANIP-backed)
// ---------------------------------------------------------------------------

export function explainShapeWithAssistant(
  projectId: string,
  shapeId: string,
  question = '',
): Promise<AssistantExplanation> {
  return invokeAssistant<AssistantExplanation>('explain_shape', {
    project_id: projectId,
    shape_id: shapeId,
    question,
  })
}

export function explainEvaluationWithAssistant(
  projectId: string,
  evaluationId: string,
  question = '',
): Promise<AssistantExplanation> {
  return invokeAssistant<AssistantExplanation>('explain_evaluation', {
    project_id: projectId,
    evaluation_id: evaluationId,
    question,
  })
}

export function interpretProjectIntentWithAssistant(
  projectId: string,
  intent: string,
): Promise<IntentInterpretation> {
  return invokeAssistant<IntentInterpretation>('interpret_project_intent', {
    project_id: projectId,
    intent,
  })
}
