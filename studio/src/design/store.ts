import { reactive, watch } from 'vue'
import type { Evaluation, DeclaredSurfaces, EditState, ValidationError } from './types'
import type { RequirementsMode } from './types'
import type { ScenarioMode } from './types'
import type { CompletenessHint } from './guided/types'
import { hydrateAnswersFromArtifact, applyAnswerToArtifact } from './guided/mappings'
import { evaluateCompleteness } from './guided/hints'
import { hydrateScenarioAnswers, applyScenarioAnswer } from './guided/scenario-mappings'
import { evaluateScenarioCompleteness } from './guided/scenario-hints'
import { checkHealth } from './api'
import { validateProposal, validateRequirements, validateScenario } from './schemas'

interface DesignState {
  liveEvaluation: Evaluation | null
  validating: boolean
  validationError: string | null
  apiAvailable: boolean
  draftRequirements: Record<string, any> | null
  draftScenario: Record<string, any> | null
  draftDeclaredSurfaces: DeclaredSurfaces | null
  originalRequirements: Record<string, any> | null
  originalScenario: Record<string, any> | null
  originalProposal: Record<string, any> | null
  editState: EditState
  validationErrors: ValidationError[]
  requirementsMode: RequirementsMode
  guidedAnswers: Record<string, any>
  completenessHints: CompletenessHint[]
  showFieldMappings: boolean
  scenarioMode: ScenarioMode
  guidedScenarioAnswers: Record<string, any>
  scenarioHints: CompletenessHint[]
  activeArtifact: 'requirements' | 'scenario' | 'proposal' | null
}

export const designStore = reactive<DesignState>({
  liveEvaluation: null,
  validating: false,
  validationError: null,
  apiAvailable: false,
  draftRequirements: null,
  draftScenario: null,
  draftDeclaredSurfaces: null,
  originalRequirements: null,
  originalScenario: null,
  originalProposal: null,
  editState: 'read',
  validationErrors: [],
  requirementsMode: 'guided',
  guidedAnswers: {},
  completenessHints: [],
  showFieldMappings: false,
  scenarioMode: 'guided',
  guidedScenarioAnswers: {},
  scenarioHints: [],
  activeArtifact: null,
})

export async function checkApiAvailability(): Promise<void> {
  designStore.apiAvailable = await checkHealth()
}

// ---------------------------------------------------------------------------
// Draft editing helpers
// ---------------------------------------------------------------------------

const DEFAULT_SURFACES: DeclaredSurfaces = {
  budget_enforcement: false,
  binding_requirements: false,
  authority_posture: false,
  recovery_class: false,
  refresh_via: false,
  verify_via: false,
  followup_via: false,
  cross_service_handoff: false,
  cross_service_continuity: false,
  cross_service_reconstruction: false,
}

function deepClone<T>(obj: T): T {
  return JSON.parse(JSON.stringify(obj))
}

export function startEditing(): void {
  if (designStore.activeArtifact === 'requirements' && designStore.originalRequirements) {
    designStore.draftRequirements = deepClone(designStore.originalRequirements)
    designStore.guidedAnswers = hydrateAnswersFromArtifact(designStore.draftRequirements)
    designStore.completenessHints = evaluateCompleteness(designStore.draftRequirements)
  } else if (designStore.activeArtifact === 'scenario' && designStore.originalScenario) {
    designStore.draftScenario = deepClone(designStore.originalScenario)
    designStore.guidedScenarioAnswers = hydrateScenarioAnswers(designStore.draftScenario)
    designStore.scenarioHints = evaluateScenarioCompleteness(designStore.draftScenario)
  } else if (designStore.activeArtifact === 'proposal' && designStore.originalProposal) {
    const surfaces = designStore.originalProposal?.proposal?.declared_surfaces
    designStore.draftDeclaredSurfaces = surfaces
      ? deepClone({ ...DEFAULT_SURFACES, ...surfaces })
      : deepClone(DEFAULT_SURFACES)
  } else {
    return
  }

  designStore.editState = 'draft'
  designStore.validationErrors = []
}

/** Discard all draft edits and return to read mode. */
export function discardEdits(): void {
  designStore.draftRequirements = null
  designStore.draftScenario = null
  designStore.draftDeclaredSurfaces = null
  designStore.editState = 'read'
  designStore.validationErrors = []
  designStore.guidedAnswers = {}
  designStore.completenessHints = []
  designStore.guidedScenarioAnswers = {}
  designStore.scenarioHints = []
}

/** Check whether draft differs from the original snapshot. */
export function isDirty(): boolean {
  if (designStore.editState !== 'draft') return false
  return (
    JSON.stringify(designStore.draftRequirements) !== JSON.stringify(designStore.originalRequirements) ||
    JSON.stringify(designStore.draftScenario) !== JSON.stringify(designStore.originalScenario) ||
    JSON.stringify(designStore.draftDeclaredSurfaces) !== JSON.stringify(
      designStore.originalProposal?.proposal?.declared_surfaces ?? null
    )
  )
}

/** Run ajv validators against draft requirements and scenario, populating validationErrors. */
export function validateDraft(): boolean {
  const errors: ValidationError[] = []

  if (designStore.draftRequirements) {
    const valid = validateRequirements(designStore.draftRequirements)
    if (!valid && validateRequirements.errors) {
      for (const err of validateRequirements.errors) {
        errors.push({
          path: `requirements${err.instancePath}`,
          message: err.message ?? 'validation error',
        })
      }
    }
  }

  if (designStore.draftScenario) {
    const valid = validateScenario(designStore.draftScenario)
    if (!valid && validateScenario.errors) {
      for (const err of validateScenario.errors) {
        errors.push({
          path: `scenario${err.instancePath}`,
          message: err.message ?? 'validation error',
        })
      }
    }
  }

  const draftProposal = composeDraftProposal()
  if (draftProposal) {
    const valid = validateProposal(draftProposal)
    if (!valid && validateProposal.errors) {
      for (const err of validateProposal.errors) {
        errors.push({
          path: `proposal${err.instancePath}`,
          message: err.message ?? 'validation error',
        })
      }
    }
  }

  designStore.validationErrors = errors
  return errors.length === 0
}

/** Set a nested field in a draft artifact using a dot-separated path. */
export function updateDraftField(
  artifact: 'requirements' | 'scenario',
  path: string,
  value: any,
): void {
  const draft = artifact === 'requirements'
    ? designStore.draftRequirements
    : designStore.draftScenario
  if (!draft) return

  const keys = path.split('.')
  let target: Record<string, any> = draft
  for (let i = 0; i < keys.length - 1; i++) {
    const key = keys[i]
    if (target[key] === undefined || target[key] === null) {
      target[key] = {}
    }
    target = target[key]
  }
  target[keys[keys.length - 1]] = value
}

/** Toggle a declared surface boolean. */
export function updateDeclaredSurface(key: string, value: boolean): void {
  if (!designStore.draftDeclaredSurfaces) return
  if (key in designStore.draftDeclaredSurfaces) {
    ;(designStore.draftDeclaredSurfaces as Record<string, boolean>)[key] = value
  }
}

/**
 * Merge draftDeclaredSurfaces into the current proposal snapshot, returning a complete proposal object.
 * Used by live validation and export.
 */
export function composeDraftProposal(): Record<string, any> | null {
  const baseProposal = designStore.originalProposal ?? null
  if (!baseProposal) return null

  const proposal = deepClone(baseProposal)
  if (designStore.draftDeclaredSurfaces) {
    proposal.proposal.declared_surfaces = deepClone(designStore.draftDeclaredSurfaces)
  }
  return proposal
}

/** Toggle between guided and advanced requirements mode.
 *  Re-hydrates guided answers from the current draft when switching to guided. */
export function setRequirementsMode(mode: RequirementsMode): void {
  designStore.requirementsMode = mode

  if (mode === 'guided' && designStore.draftRequirements) {
    designStore.guidedAnswers = hydrateAnswersFromArtifact(designStore.draftRequirements)
    designStore.completenessHints = evaluateCompleteness(designStore.draftRequirements)
  }
}

/** Toggle between guided and advanced scenario mode. */
export function setScenarioMode(mode: ScenarioMode): void {
  designStore.scenarioMode = mode

  if (mode === 'guided' && designStore.draftScenario) {
    designStore.guidedScenarioAnswers = hydrateScenarioAnswers(designStore.draftScenario)
    designStore.scenarioHints = evaluateScenarioCompleteness(designStore.draftScenario)
  }
}

/** Update a single guided scenario answer and apply it to the draft artifact. */
export function updateGuidedScenarioAnswer(questionId: string, value: any): void {
  designStore.guidedScenarioAnswers[questionId] = value

  if (designStore.draftScenario) {
    applyScenarioAnswer(questionId, value, designStore.draftScenario)
    designStore.scenarioHints = evaluateScenarioCompleteness(designStore.draftScenario)
  }
}

/** Toggle field mapping chip visibility */
export function toggleFieldMappings(): void {
  designStore.showFieldMappings = !designStore.showFieldMappings
}

/** Update a single guided answer and apply it to the draft artifact */
export function updateGuidedAnswer(questionId: string, value: any): void {
  designStore.guidedAnswers[questionId] = value

  if (designStore.draftRequirements) {
    applyAnswerToArtifact(questionId, value, designStore.draftRequirements)
  }

  // Re-evaluate completeness hints
  if (designStore.draftRequirements) {
    designStore.completenessHints = evaluateCompleteness(designStore.draftRequirements)
  }
}

// ---------------------------------------------------------------------------
// Auto-validate on draft changes (debounced)
// ---------------------------------------------------------------------------

let validateTimer: ReturnType<typeof setTimeout> | null = null

watch(
  () => [designStore.draftRequirements, designStore.draftScenario, designStore.draftDeclaredSurfaces],
  () => {
    if (designStore.editState !== 'draft') return
    if (validateTimer) clearTimeout(validateTimer)
    validateTimer = setTimeout(() => {
      validateDraft()
      if (designStore.draftRequirements) {
        designStore.completenessHints = evaluateCompleteness(designStore.draftRequirements)
      }
      if (designStore.draftScenario) {
        designStore.scenarioHints = evaluateScenarioCompleteness(designStore.draftScenario)
      }
    }, 300)
  },
  { deep: true },
)
