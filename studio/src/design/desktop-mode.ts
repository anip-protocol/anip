export const studioDesktopMode = !!import.meta.env.VITE_STUDIO_DESKTOP

export const studioApiBase = String(import.meta.env.VITE_STUDIO_API_BASE ?? '').replace(/\/+$/, '')

export function studioApiUnavailableMessage(): string {
  if (!studioDesktopMode) return 'Studio API unavailable'
  return `Studio API unavailable. Start the local Studio API${studioApiBase ? ` at ${studioApiBase}` : ''} to use Design mode.`
}
