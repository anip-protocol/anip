import { ref } from 'vue'

export type DateTimeDisplayMode = 'utc' | 'local' | 'iso'

export const dateTimeDisplayMode = ref<DateTimeDisplayMode>('utc')

export const dateTimeDisplayOptions: { value: DateTimeDisplayMode; label: string }[] = [
  { value: 'utc', label: 'UTC' },
  { value: 'local', label: 'Local time' },
  { value: 'iso', label: 'ISO 8601' },
]

function formatWithZone(date: Date, timeZone?: string): string {
  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    timeZone,
    timeZoneName: 'short',
  }).format(date)
}

export function formatRegistryTimestamp(value: string | undefined): string {
  if (!value) return 'Unknown'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  if (dateTimeDisplayMode.value === 'iso') return date.toISOString()
  if (dateTimeDisplayMode.value === 'local') return formatWithZone(date)
  return formatWithZone(date, 'UTC')
}

export function formatTimestampRef(value: string | undefined): string {
  if (!value) return 'Unknown'
  const match = /^([^:]+):(.+)$/.exec(value)
  if (!match) return value
  const [, prefix, rawTimestamp] = match
  const formatted = formatRegistryTimestamp(rawTimestamp)
  return formatted === rawTimestamp ? value : `${prefix}:${formatted}`
}
