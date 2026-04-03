export interface FieldChange {
  path: string
  before: any
  after: any
}

/**
 * Recursively compare two objects and return a list of changed field paths
 * with their before/after values.
 */
export function diffObjects(
  original: Record<string, any> | null | undefined,
  current: Record<string, any> | null | undefined,
  prefix = '',
): FieldChange[] {
  const changes: FieldChange[] = []

  const orig = original ?? {}
  const curr = current ?? {}

  const allKeys = new Set([...Object.keys(orig), ...Object.keys(curr)])

  for (const key of allKeys) {
    const path = prefix ? `${prefix}.${key}` : key
    const before = orig[key]
    const after = curr[key]

    // Both undefined — skip
    if (before === undefined && after === undefined) continue

    // One side missing
    if (before === undefined) {
      changes.push({ path, before: undefined, after })
      continue
    }
    if (after === undefined) {
      changes.push({ path, before, after: undefined })
      continue
    }

    // Both are plain objects — recurse
    if (isPlainObject(before) && isPlainObject(after)) {
      changes.push(...diffObjects(before, after, path))
      continue
    }

    // Compare via JSON.stringify for arrays and primitives
    if (JSON.stringify(before) !== JSON.stringify(after)) {
      changes.push({ path, before, after })
    }
  }

  return changes
}

function isPlainObject(val: unknown): val is Record<string, any> {
  return typeof val === 'object' && val !== null && !Array.isArray(val)
}
