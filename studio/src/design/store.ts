import { reactive, watch } from 'vue'
import type { DesignPack, PackMeta, Evaluation, DeclaredSurfaces, EditState, ValidationError } from './types'
import { PACKS } from './data/packs.generated'
import { runValidation, checkHealth } from './api'
import { validateRequirements, validateScenario } from './schemas'

interface DesignState {
  packs: DesignPack[]
  activePackId: string | null
  liveEvaluation: Evaluation | null
  validating: boolean
  validationError: string | null
  apiAvailable: boolean
  draftRequirements: Record<string, any> | null
  draftScenario: Record<string, any> | null
  draftDeclaredSurfaces: DeclaredSurfaces | null
  originalRequirements: Record<string, any> | null
  originalScenario: Record<string, any> | null
  editState: EditState
  validationErrors: ValidationError[]
}

export const designStore = reactive<DesignState>({
  packs: PACKS,
  activePackId: null,
  liveEvaluation: null,
  validating: false,
  validationError: null,
  apiAvailable: false,
  draftRequirements: null,
  draftScenario: null,
  draftDeclaredSurfaces: null,
  originalRequirements: null,
  originalScenario: null,
  editState: 'read',
  validationErrors: [],
})

export function getActivePack(): DesignPack | null {
  if (!designStore.activePackId) return null
  return designStore.packs.find(p => p.meta.id === designStore.activePackId) ?? null
}

export function setActivePack(id: string) {
  designStore.activePackId = id
  // Clear live evaluation when switching packs
  designStore.liveEvaluation = null
  designStore.validationError = null
}

export function getPackMetas(): PackMeta[] {
  return designStore.packs.map(p => p.meta)
}

export async function runLiveValidation(): Promise<void> {
  const pack = getActivePack()
  if (!pack) return

  designStore.validating = true
  designStore.validationError = null
  try {
    // Use draft state when editing, otherwise use original pack data
    const requirements = designStore.draftRequirements ?? pack.requirements
    const scenario = designStore.draftScenario ?? pack.scenario
    const proposal = composeDraftProposal() ?? pack.proposal
    if (!proposal) return

    const result = await runValidation(requirements, proposal, scenario)
    designStore.liveEvaluation = result
  } catch (err: any) {
    designStore.validationError = err.message ?? 'Unknown error'
  } finally {
    designStore.validating = false
  }
}

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

/** Enter draft mode — snapshot current pack data for editing. */
export function startEditing(): void {
  const pack = getActivePack()
  if (!pack) return

  designStore.draftRequirements = deepClone(pack.requirements)
  designStore.originalRequirements = deepClone(pack.requirements)
  designStore.draftScenario = deepClone(pack.scenario)
  designStore.originalScenario = deepClone(pack.scenario)

  // Extract declared_surfaces from proposal if present
  const surfaces = pack.proposal?.proposal?.declared_surfaces
  designStore.draftDeclaredSurfaces = surfaces
    ? deepClone({ ...DEFAULT_SURFACES, ...surfaces })
    : deepClone(DEFAULT_SURFACES)

  designStore.editState = 'draft'
  designStore.validationErrors = []
}

/** Discard all draft edits and return to read mode. */
export function discardEdits(): void {
  designStore.draftRequirements = null
  designStore.draftScenario = null
  designStore.draftDeclaredSurfaces = null
  designStore.originalRequirements = null
  designStore.originalScenario = null
  designStore.editState = 'read'
  designStore.validationErrors = []
}

/** Check whether draft differs from the original snapshot. */
export function isDirty(): boolean {
  if (designStore.editState !== 'draft') return false
  return (
    JSON.stringify(designStore.draftRequirements) !== JSON.stringify(designStore.originalRequirements) ||
    JSON.stringify(designStore.draftScenario) !== JSON.stringify(designStore.originalScenario) ||
    JSON.stringify(designStore.draftDeclaredSurfaces) !== JSON.stringify(
      getActivePack()?.proposal?.proposal?.declared_surfaces ?? null
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
 * Merge draftDeclaredSurfaces into the pack proposal, returning a complete proposal object.
 * Used by live validation and export.
 */
export function composeDraftProposal(): Record<string, any> | null {
  const pack = getActivePack()
  if (!pack?.proposal) return null

  const proposal = deepClone(pack.proposal)
  if (designStore.draftDeclaredSurfaces) {
    proposal.proposal.declared_surfaces = deepClone(designStore.draftDeclaredSurfaces)
  }
  return proposal
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
    validateTimer = setTimeout(() => validateDraft(), 300)
  },
  { deep: true },
)
