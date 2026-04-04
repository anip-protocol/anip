import type { Evaluation } from './types'

function extractValidationError(body: string): string {
  let detail = body

  try {
    const parsed = JSON.parse(body)
    if (parsed && typeof parsed.detail === 'string') {
      detail = parsed.detail
    }
  } catch {
    // keep original body
  }

  return detail
    .replace('requirements.schema.json validation failed:', 'Requirements are incomplete:')
    .replace('proposal.schema.json validation failed:', 'The approach is incomplete:')
    .replace('shape.schema.json validation failed:', 'The service shape is incomplete:')
    .replace('scenario.schema.json validation failed:', 'The scenario is incomplete:')
    .replace(/- <root>:/g, '-')
    .replace(/- system:/g, '- system')
    .trim()
}

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
    throw new Error(extractValidationError(err))
  }
  return resp.json()
}

export async function runShapeValidation(
  requirements: Record<string, any>,
  shape: Record<string, any>,
  scenario: Record<string, any>,
): Promise<Evaluation> {
  const resp = await fetch('/api/validate-shape', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ requirements, shape, scenario }),
  })
  if (!resp.ok) {
    const err = await resp.text()
    throw new Error(extractValidationError(err))
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
