import { reactive } from 'vue'
import type { DesignPack, PackMeta } from './types'
import { PACKS } from './data/packs.generated'

interface DesignState {
  packs: DesignPack[]
  activePackId: string | null
}

export const designStore = reactive<DesignState>({
  packs: PACKS,
  activePackId: null,
})

export function getActivePack(): DesignPack | null {
  if (!designStore.activePackId) return null
  return designStore.packs.find(p => p.meta.id === designStore.activePackId) ?? null
}

export function setActivePack(id: string) {
  designStore.activePackId = id
}

export function getPackMetas(): PackMeta[] {
  return designStore.packs.map(p => p.meta)
}
