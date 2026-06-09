import { ref, watch } from 'vue'

const STORAGE_KEY = 'anip.studio.showTechnicalIdentifiers'

function loadPreference(): boolean {
  if (typeof window === 'undefined') return false
  return window.localStorage.getItem(STORAGE_KEY) === 'true'
}

export const showTechnicalIdentifiers = ref(loadPreference())

if (typeof window !== 'undefined') {
  watch(showTechnicalIdentifiers, (value) => {
    if (value) {
      window.localStorage.setItem(STORAGE_KEY, 'true')
    } else {
      window.localStorage.removeItem(STORAGE_KEY)
    }
  })
}

export function technicalHoverLabel(value: string | undefined | null): string {
  const normalized = String(value ?? '').trim()
  return normalized ? `Canonical value: ${normalized}` : ''
}
