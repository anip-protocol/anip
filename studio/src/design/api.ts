import type { Evaluation } from './types'

export async function runValidation(
  requirements: Record<string, any>,
  proposal: Record<string, any>,
  scenario: Record<string, any>,
): Promise<Evaluation> {
  const resp = await fetch('/api/validate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ requirements, proposal, scenario }),
  })
  if (!resp.ok) {
    const err = await resp.text()
    throw new Error(`Validation failed: ${err}`)
  }
  return resp.json()
}

export async function checkHealth(): Promise<boolean> {
  try {
    const resp = await fetch('/api/health')
    return resp.ok
  } catch {
    return false
  }
}
