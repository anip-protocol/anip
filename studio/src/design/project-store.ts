import { reactive } from 'vue'
import type {
  ProjectSummary,
  ProjectDetail,
  ArtifactRecord,
  RequirementsRecord,
  ProposalRecord,
  EvaluationRecord,
  VocabularyEntry,
} from './project-types'
import {
  listProjects,
  listRequirements,
  listScenarios,
  listProposals,
  listEvaluations,
  listVocabulary,
  seedDatabase,
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
  projects: ProjectSummary[]
  activeProject: ProjectDetail | null
  artifacts: {
    requirements: RequirementsRecord[]
    scenarios: ArtifactRecord[]
    proposals: ProposalRecord[]
    evaluations: EvaluationRecord[]
  }
  vocabulary: VocabularyEntry[]
  activeRequirementsId: string | null
  activeProposalId: string | null
  loading: boolean
  error: string | null
  dbAvailable: boolean
}

export const projectStore = reactive<ProjectState>({
  projects: [],
  activeProject: null,
  artifacts: {
    requirements: [],
    scenarios: [],
    proposals: [],
    evaluations: [],
  },
  vocabulary: [],
  activeRequirementsId: null,
  activeProposalId: null,
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
    projectStore.activeProposalId !== null &&
    !projectStore.artifacts.proposals.some(p => p.id === projectStore.activeProposalId)
  ) {
    projectStore.activeProposalId = null
  }
}

/**
 * Auto-select active IDs when exactly one record of each type exists.
 * Called after loadProject() finishes populating artifact lists.
 */
function autoSelectActiveIds(): void {
  if (projectStore.artifacts.requirements.length === 1) {
    projectStore.activeRequirementsId = projectStore.artifacts.requirements[0].id
  }
  if (projectStore.artifacts.proposals.length === 1) {
    projectStore.activeProposalId = projectStore.artifacts.proposals[0].id
  }
}

// ---------------------------------------------------------------------------
// Public functions
// ---------------------------------------------------------------------------

/** Check if the sidecar/DB is reachable. Sets dbAvailable. Never throws. */
export async function checkDbAvailable(): Promise<void> {
  try {
    await listProjects()
    projectStore.dbAvailable = true
  } catch {
    projectStore.dbAvailable = false
  }
}

/** Fetch all projects and populate the projects list. */
export async function loadProjects(): Promise<void> {
  setLoading(true)
  clearError()
  try {
    projectStore.projects = await listProjects()
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
  projectStore.activeProposalId = null

  setLoading(true)
  clearError()
  try {
    const [detail, requirements, scenarios, proposals, evaluations] = await Promise.all([
      // getProject returns ProjectDetail with counts — import lazily to avoid circular dep
      fetch(`/api/projects/${id}`).then(r => {
        if (!r.ok) throw new Error(`Failed to load project ${id}: ${r.status}`)
        return r.json() as Promise<ProjectDetail>
      }),
      listRequirements(id),
      listScenarios(id),
      listProposals(id),
      listEvaluations(id),
    ])

    projectStore.activeProject = detail
    projectStore.artifacts.requirements = requirements
    projectStore.artifacts.scenarios = scenarios
    projectStore.artifacts.proposals = proposals
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

/** Set the active proposal for evaluation context. */
export function setActiveProposal(id: string | null): void {
  projectStore.activeProposalId = id
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
  } else if (artifactType === 'proposal') {
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

/** Seed the database from example packs, then reload the project list. */
export async function seedDb(): Promise<void> {
  setLoading(true)
  clearError()
  try {
    await seedDatabase()
    await loadProjects()
  } catch (err) {
    setError(err)
  } finally {
    setLoading(false)
  }
}

/**
 * Reset all project-scoped state.
 *
 * Active Context Reset Rules: clearProject() clears both active IDs to null.
 */
export function clearProject(): void {
  projectStore.activeProject = null
  projectStore.artifacts.requirements = []
  projectStore.artifacts.scenarios = []
  projectStore.artifacts.proposals = []
  projectStore.artifacts.evaluations = []
  projectStore.vocabulary = []
  projectStore.activeRequirementsId = null
  projectStore.activeProposalId = null
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
 * Call after deleting a scenario record.
 */
export function onScenarioDeleted(id: string): void {
  projectStore.artifacts.scenarios = projectStore.artifacts.scenarios.filter(s => s.id !== id)
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
    const [requirements, scenarios, proposals, evaluations] = await Promise.all([
      listRequirements(project.id),
      listScenarios(project.id),
      listProposals(project.id),
      listEvaluations(project.id),
    ])
    projectStore.artifacts.requirements = requirements
    projectStore.artifacts.scenarios = scenarios
    projectStore.artifacts.proposals = proposals
    projectStore.artifacts.evaluations = evaluations
    // Revalidate per Active Context Reset Rules
    revalidateActiveIds()
  } catch (err) {
    setError(err)
  }
}
