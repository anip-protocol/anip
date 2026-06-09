import { reactive } from 'vue'

export type StudioTimeDisplayMode = 'local' | 'utc'
export type StudioTimeFormatStyle = 'datetime' | 'date'

const STORAGE_KEY = 'studio.time-display-mode'

function readStoredMode(): StudioTimeDisplayMode | null {
  if (typeof window === 'undefined') return null
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    return stored === 'utc' ? 'utc' : stored === 'local' ? 'local' : null
  } catch {
    return null
  }
}

function initialMode(): StudioTimeDisplayMode {
  return readStoredMode() ?? 'local'
}

export const studioTimePreferences = reactive<{
  mode: StudioTimeDisplayMode
}>({
  mode: initialMode(),
})

export function setStudioTimeDisplayMode(mode: StudioTimeDisplayMode) {
  studioTimePreferences.mode = mode
  if (typeof window !== 'undefined') {
    try {
      window.localStorage.setItem(STORAGE_KEY, mode)
    } catch {
      // Ignore storage failures; the in-memory preference still applies for this session.
    }
  }
}

export function formatStudioTimestamp(
  value: string | Date | null | undefined,
  style: StudioTimeFormatStyle = 'datetime',
): string {
  if (!value) return 'Not recorded'
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)

  const mode = studioTimePreferences.mode
  const locale = undefined
  const baseOptions: Intl.DateTimeFormatOptions =
    style === 'date'
      ? {
          year: 'numeric',
          month: 'short',
          day: 'numeric',
        }
      : {
          year: 'numeric',
          month: 'short',
          day: 'numeric',
          hour: 'numeric',
          minute: '2-digit',
          second: '2-digit',
          timeZoneName: 'short',
        }

  if (mode === 'utc') {
    return new Intl.DateTimeFormat(locale, {
      ...baseOptions,
      timeZone: 'UTC',
    }).format(date)
  }

  return new Intl.DateTimeFormat(locale, baseOptions).format(date)
}
