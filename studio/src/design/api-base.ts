import { studioApiBase } from './desktop-mode'

const ABSOLUTE_URL_PATTERN = /^[a-z][a-z0-9+.-]*:\/\//i

export function resolveStudioApiUrl(path: string, configuredBase: string | undefined): string {
  if (ABSOLUTE_URL_PATTERN.test(path)) return path

  const base = String(configuredBase ?? '').trim().replace(/\/+$/, '')
  if (!base) return path

  return `${base}${path.startsWith('/') ? path : `/${path}`}`
}

export function studioApiUrl(path: string): string {
  return resolveStudioApiUrl(path, studioApiBase)
}
