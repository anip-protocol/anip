import { reactive } from 'vue'
import type { DesignPack, PackMeta, Evaluation } from './types'
import { PACKS } from './data/packs.generated'
import { runValidation, checkHealth } from './api'

interface DesignState {
  packs: DesignPack[]
  activePackId: string | null
  liveEvaluation: Evaluation | null
  validating: boolean
  validationError: string | null
  apiAvailable: boolean
}

export const designStore = reactive<DesignState>({
  packs: PACKS,
  activePackId: null,
  liveEvaluation: null,
  validating: false,
  validationError: null,
  apiAvailable: false,
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
  if (!pack || !pack.proposal) return

  designStore.validating = true
  designStore.validationError = null
  try {
    const result = await runValidation(
      pack.requirements,
      pack.proposal,
      pack.scenario,
    )
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
