export const studioDesktopMode = !!import.meta.env.VITE_STUDIO_DESKTOP

export let studioApiBase = String(import.meta.env.VITE_STUDIO_API_BASE ?? '').replace(/\/+$/, '')

let runtimeApiBaseResolved = false
let runtimeApiBasePromise: Promise<string> | null = null

export function configureStudioApiBase(base: string | null | undefined): string {
  studioApiBase = String(base ?? '').trim().replace(/\/+$/, '')
  runtimeApiBaseResolved = true
  runtimeApiBasePromise = null
  return studioApiBase
}

export async function ensureStudioApiBase(): Promise<string> {
  if (!studioDesktopMode || runtimeApiBaseResolved) return studioApiBase
  if (runtimeApiBasePromise) return runtimeApiBasePromise

  runtimeApiBasePromise = import('@tauri-apps/api/core')
    .then(({ invoke }) => invoke<string>('studio_api_base_url'))
    .then((base) => configureStudioApiBase(base))
    .catch(() => {
      runtimeApiBaseResolved = true
      return studioApiBase
    })

  return runtimeApiBasePromise
}

export function studioApiUnavailableMessage(): string {
  if (!studioDesktopMode) return 'Studio API unavailable'
  return `Studio API unavailable. Start the local Studio API${studioApiBase ? ` at ${studioApiBase}` : ''} to use Design mode.`
}
