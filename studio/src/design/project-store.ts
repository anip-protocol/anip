import { reactive } from 'vue'
import type {
  WorkspaceDetail,
  ProjectSummary,
  ProjectDetail,
  ArtifactRecord,
  RequirementsRecord,
  ProposalRecord,
  ShapeRecord,
  EvaluationRecord,
  VocabularyEntry,
  PendingIntentDraft,
} from './project-types'
import {
  listWorkspaces,
  getWorkspace,
  listProjects,
  listRequirements,
  listScenarios,
  listProposals,
  listShapes,
  listEvaluations,
  listVocabulary,
} from './project-api'
import { designStore } from './store'
import { hydrateAnswersFromArtifact } from './guided/mappings'
import { evaluateCompleteness } from './guided/hints'
import { hydrateScenarioAnswers } from './guided/scenario-mappings'
import { evaluateScenarioCompleteness } from './guided/scenario-hints'

// ---------------------------------------------------------------------------
// State shape
// ---------------------------------------------------------------------------

interface ProjectState {
  workspaces: WorkspaceDetail[]
  activeWorkspace: WorkspaceDetail | null
  projects: ProjectSummary[]
  activeProject: ProjectDetail | null
  artifacts: {
    requirements: RequirementsRecord[]
    scenarios: ArtifactRecord[]
    proposals: ProposalRecord[]
    shapes: ShapeRecord[]
    evaluations: EvaluationRecord[]
  }
  vocabulary: VocabularyEntry[]
  activeRequirementsId: string | null
  activeScenarioId: string | null
  activeProposalId: string | null
  activeShapeId: string | null
  pendingIntentDraft: PendingIntentDraft | null
  loading: boolean
  error: string | null
  dbAvailable: boolean
}

export const projectStore = reactive<ProjectState>({
  workspaces: [],
  activeWorkspace: null,
  projects: [],
  activeProject: null,
  artifacts: {
    requirements: [],
    scenarios: [],
    proposals: [],
    shapes: [],
    evaluations: [],
  },
  vocabulary: [],
  activeRequirementsId: null,
  activeScenarioId: null,
  activeProposalId: null,
  activeShapeId: null,
  pendingIntentDraft: null,
  loading: false,
  error: null,
  dbAvailable: false,
})

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function setLoading(loading: boolean): void {
  projectStore.loading = loading
}

function setError(err: unknown): void {
  projectStore.error = err instanceof Error ? err.message : String(err)
}

function clearError(): void {
  projectStore.error = null
}

/**
 * After any list refresh, revalidate that the active IDs still exist.
 * Per Active Context Reset Rules: if the active ID no longer exists in the list,
 * reset it to null.
 */
function revalidateActiveIds(): void {
  if (
    projectStore.activeRequirementsId !== null &&
    !projectStore.artifacts.requirements.some(r => r.id === projectStore.activeRequirementsId)
  ) {
    projectStore.activeRequirementsId = null
  }

  if (
    projectStore.activeScenarioId !== null &&
    !projectStore.artifacts.scenarios.some(s => s.id === projectStore.activeScenarioId)
  ) {
    projectStore.activeScenarioId = null
  }

  if (
    projectStore.activeProposalId !== null &&
    !projectStore.artifacts.proposals.some(p => p.id === projectStore.activeProposalId)
  ) {
    projectStore.activeProposalId = null
  }

  if (
    projectStore.activeShapeId !== null &&
    !projectStore.artifacts.shapes.some(s => s.id === projectStore.activeShapeId)
  ) {
    projectStore.activeShapeId = null
  }
}

/**
 * Auto-select active IDs when exactly one record of each type exists.
 * Called after loadProject() finishes populating artifact lists.
 */
/**
 * Auto-select active IDs when exactly one record of each type exists.
 * Shape-first: if shapes exist, auto-select shape; only auto-select
 * proposal if no shapes exist (legacy project).
 */
function autoSelectActiveIds(): void {
  if (projectStore.activeRequirementsId === null) {
    const primary = projectStore.artifacts.requirements.find(r => r.role === 'primary')
    if (primary) {
      projectStore.activeRequirementsId = primary.id
    } else if (projectStore.artifacts.requirements.length === 1) {
      projectStore.activeRequirementsId = projectStore.artifacts.requirements[0].id
    }
  }

  if (projectStore.activeScenarioId === null && projectStore.artifacts.scenarios.length === 1) {
    projectStore.activeScenarioId = projectStore.artifacts.scenarios[0].id
  }

  if (projectStore.artifacts.shapes.length > 0) {
    if (projectStore.activeShapeId === null && projectStore.artifacts.shapes.length === 1) {
      projectStore.activeShapeId = projectStore.artifacts.shapes[0].id
    }
  } else if (projectStore.activeProposalId === null && projectStore.artifacts.proposals.length === 1) {
    projectStore.activeProposalId = projectStore.artifacts.proposals[0].id
  }
}

// ---------------------------------------------------------------------------
// Public functions
// ---------------------------------------------------------------------------

/** Check if the sidecar/DB is reachable. Sets dbAvailable. Never throws. */
export async function checkDbAvailable(): Promise<void> {
  try {
    await listWorkspaces()
    projectStore.dbAvailable = true
  } catch {
    projectStore.dbAvailable = false
  }
}

export async function loadWorkspaces(): Promise<void> {
  setLoading(true)
  clearError()
  try {
    projectStore.workspaces = await listWorkspaces()
  } catch (err) {
    setError(err)
  } finally {
    setLoading(false)
  }
}

export async function loadWorkspace(id: string): Promise<void> {
  clearError()
  try {
    projectStore.activeWorkspace = await getWorkspace(id)
  } catch (err) {
    setError(err)
    projectStore.activeWorkspace = null
  }
}

/** Fetch all projects and populate the projects list. */
export async function loadProjects(workspaceId?: string): Promise<void> {
  setLoading(true)
  clearError()
  try {
    projectStore.projects = await listProjects(workspaceId)
  } catch (err) {
    setError(err)
  } finally {
    setLoading(false)
  }
}

/**
 * Fetch a single project detail plus all its artifact lists in parallel.
 *
 * Active Context Reset Rules:
 * - Clears activeRequirementsId and activeProposalId to null first (switching projects)
 * - Then auto-selects if exactly one active record exists
 */
export async function loadProject(id: string): Promise<void> {
  // Clear context immediately before any async work (switching projects)
  projectStore.activeRequirementsId = null
  projectStore.activeScenarioId = null
  projectStore.activeProposalId = null
  projectStore.activeShapeId = null

  setLoading(true)
  clearError()
  try {
    const [detail, requirements, scenarios, proposals, shapes, evaluations] = await Promise.all([
      // getProject returns ProjectDetail with counts — import lazily to avoid circular dep
      fetch(`/api/projects/${id}`).then(r => {
        if (!r.ok) throw new Error(`Failed to load project ${id}: ${r.status}`)
        return r.json() as Promise<ProjectDetail>
      }),
      listRequirements(id),
      listScenarios(id),
      listProposals(id),
      listShapes(id),
      listEvaluations(id),
    ])

    projectStore.activeProject = detail
    if (detail.workspace_id) {
      if (projectStore.activeWorkspace?.id !== detail.workspace_id) {
        await loadWorkspace(detail.workspace_id)
      }
    }
    projectStore.artifacts.requirements = requirements
    projectStore.artifacts.scenarios = scenarios
    projectStore.artifacts.proposals = proposals
    projectStore.artifacts.shapes = shapes
    projectStore.artifacts.evaluations = evaluations

    // Auto-select if exactly one record of each type exists
    autoSelectActiveIds()
  } catch (err) {
    setError(err)
  } finally {
    setLoading(false)
  }
}

/** Fetch merged global + project vocabulary. */
export async function loadVocabulary(projectId?: string): Promise<void> {
  clearError()
  try {
    projectStore.vocabulary = await listVocabulary(
      projectId ? { project_id: projectId } : undefined,
    )
  } catch (err) {
    setError(err)
  }
}

/** Set the active requirements set for evaluation context. */
export function setActiveRequirements(id: string | null): void {
  projectStore.activeRequirementsId = id
}

/** Set the active scenario for evaluation context. */
export function setActiveScenario(id: string | null): void {
  projectStore.activeScenarioId = id
}

/** Set the active proposal for evaluation context. */
export function setActiveProposal(id: string | null): void {
  projectStore.activeProposalId = id
}

/** Set the active shape for evaluation context. */
export function setActiveShape(id: string | null): void {
  projectStore.activeShapeId = id
}

export function setPendingIntentDraft(draft: PendingIntentDraft | null): void {
  projectStore.pendingIntentDraft = draft
}

/**
 * Handoff: hydrate the design store's draft state from a project artifact record.
 *
 * The design store does NOT know about projects — it only sees artifact content.
 * This function bridges the two stores by writing record.data into draft state
 * so existing guided/edit/validation flows work unchanged.
 *
 * Also updates activeRequirementsId / activeProposalId as a side effect when
 * navigating to requirements or proposal artifacts.
 */
export function openArtifactForEditing(
  artifactType: 'requirements' | 'scenario' | 'proposal',
  record: ArtifactRecord | ProposalRecord,
): void {
  const data = record.data ?? {}

  if (artifactType === 'requirements') {
    designStore.activeArtifact = 'requirements'
    designStore.draftScenario = null
    designStore.originalScenario = null
    designStore.draftDeclaredSurfaces = null
    designStore.guidedScenarioAnswers = {}
    designStore.scenarioHints = []
    designStore.draftRequirements = JSON.parse(JSON.stringify(data))
    designStore.originalRequirements = JSON.parse(JSON.stringify(data))
    designStore.originalProposal = null
    designStore.guidedAnswers = hydrateAnswersFromArtifact(designStore.draftRequirements!)
    designStore.completenessHints = evaluateCompleteness(designStore.draftRequirements!)
    designStore.editState = 'draft'
    // Update active context
    projectStore.activeRequirementsId = record.id
  } else if (artifactType === 'scenario') {
    designStore.activeArtifact = 'scenario'
    designStore.draftRequirements = null
    designStore.originalRequirements = null
    designStore.draftDeclaredSurfaces = null
    designStore.guidedAnswers = {}
    designStore.completenessHints = []
    designStore.draftScenario = JSON.parse(JSON.stringify(data))
    designStore.originalScenario = JSON.parse(JSON.stringify(data))
    designStore.originalProposal = null
    designStore.guidedScenarioAnswers = hydrateScenarioAnswers(designStore.draftScenario!)
    designStore.scenarioHints = evaluateScenarioCompleteness(designStore.draftScenario!)
    designStore.editState = 'draft'
    projectStore.activeScenarioId = record.id
  } else if (artifactType === 'proposal') {
    designStore.activeArtifact = 'proposal'
    designStore.draftRequirements = null
    designStore.originalRequirements = null
    designStore.draftScenario = null
    designStore.originalScenario = null
    designStore.guidedAnswers = {}
    designStore.completenessHints = []
    designStore.guidedScenarioAnswers = {}
    designStore.scenarioHints = []
    // Proposal data is nested: record.data may contain the full proposal object
    // Merge declared_surfaces into draftDeclaredSurfaces if present
    designStore.originalProposal = JSON.parse(JSON.stringify(data))
    const surfaces = data?.proposal?.declared_surfaces
    designStore.draftDeclaredSurfaces = surfaces
      ? JSON.parse(JSON.stringify(surfaces))
      : null
    designStore.editState = 'draft'
    // Update active context
    projectStore.activeProposalId = record.id
  }

  designStore.validationErrors = []
  designStore.liveEvaluation = null
}

/**
 * Reset all project-scoped state.
 *
 * Active Context Reset Rules: clearProject() clears both active IDs to null.
 */
export function clearProject(): void {
  projectStore.activeWorkspace = null
  projectStore.activeProject = null
  projectStore.artifacts.requirements = []
  projectStore.artifacts.scenarios = []
  projectStore.artifacts.proposals = []
  projectStore.artifacts.shapes = []
  projectStore.artifacts.evaluations = []
  projectStore.vocabulary = []
  projectStore.activeRequirementsId = null
  projectStore.activeScenarioId = null
  projectStore.activeProposalId = null
  projectStore.activeShapeId = null
  projectStore.pendingIntentDraft = null
}

export function setActiveWorkspace(workspace: WorkspaceDetail | null): void {
  projectStore.activeWorkspace = workspace
}

// ---------------------------------------------------------------------------
// Post-delete helpers — call these after API deletes to revalidate active IDs
// ---------------------------------------------------------------------------

/**
 * Call after deleting a requirements record.
 * Resets activeRequirementsId if the deleted record was active.
 */
export function onRequirementsDeleted(id: string): void {
  projectStore.artifacts.requirements = projectStore.artifacts.requirements.filter(
    r => r.id !== id,
  )
  if (projectStore.activeRequirementsId === id) {
    projectStore.activeRequirementsId = null
  }
}

/**
 * Call after deleting a proposal record.
 * Resets activeProposalId if the deleted record was active.
 */
export function onProposalDeleted(id: string): void {
  projectStore.artifacts.proposals = projectStore.artifacts.proposals.filter(p => p.id !== id)
  if (projectStore.activeProposalId === id) {
    projectStore.activeProposalId = null
  }
}

/**
 * Call after deleting a shape record.
 * Resets activeShapeId if the deleted record was active.
 */
export function onShapeDeleted(id: string): void {
  projectStore.artifacts.shapes = projectStore.artifacts.shapes.filter(s => s.id !== id)
  if (projectStore.activeShapeId === id) {
    projectStore.activeShapeId = null
  }
}

/**
 * Call after deleting a scenario record.
 */
export function onScenarioDeleted(id: string): void {
  projectStore.artifacts.scenarios = projectStore.artifacts.scenarios.filter(s => s.id !== id)
  if (projectStore.activeScenarioId === id) {
    projectStore.activeScenarioId = null
  }
}

/**
 * Call after deleting an evaluation record.
 */
export function onEvaluationDeleted(id: string): void {
  projectStore.artifacts.evaluations = projectStore.artifacts.evaluations.filter(
    e => e.id !== id,
  )
}

/**
 * Refresh artifact lists for the active project and revalidate active IDs.
 * Use after any mutation (create/update/delete) that changes artifact counts.
 */
export async function refreshArtifacts(): Promise<void> {
  const project = projectStore.activeProject
  if (!project) return
  try {
    const [requirements, scenarios, proposals, shapes, evaluations] = await Promise.all([
      listRequirements(project.id),
      listScenarios(project.id),
      listProposals(project.id),
      listShapes(project.id),
      listEvaluations(project.id),
    ])
    projectStore.artifacts.requirements = requirements
    projectStore.artifacts.scenarios = scenarios
    projectStore.artifacts.proposals = proposals
    projectStore.artifacts.shapes = shapes
    projectStore.artifacts.evaluations = evaluations
    // Revalidate per Active Context Reset Rules
    revalidateActiveIds()
    autoSelectActiveIds()
  } catch (err) {
    setError(err)
  }
}
