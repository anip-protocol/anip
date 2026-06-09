import type { RuntimeObservation } from './types'

export function deriveObservedOutcomeFromAuditEntry(
  entry: Record<string, any>,
): RuntimeObservation['observed_outcome'] {
  if (entry.success === true) return 'available'
  const failureType = String(entry.failure_type || '').toLowerCase()
  const bindingRequires = String(entry.binding_context?.requires || '').toLowerCase()
  if (
    failureType.includes('approval') ||
    bindingRequires.includes('approval')
  ) {
    return 'approval_required'
  }
  if (
    failureType.includes('clarif') ||
    failureType.includes('ambiguous') ||
    failureType.includes('missing')
  ) {
    return 'clarification_required'
  }
  if (failureType.includes('restrict')) {
    return 'restricted'
  }
  if (entry.success === false) return 'denied'
  return null
}

export function normalizeAuditEntryToObservation(entry: Record<string, any>): RuntimeObservation {
  const bindingContext = entry.binding_context && typeof entry.binding_context === 'object'
    ? entry.binding_context
    : null
  const unresolvedInputs = Array.isArray(bindingContext?.unresolved_inputs)
    ? bindingContext.unresolved_inputs.filter((value: unknown): value is string => typeof value === 'string')
    : []
  return {
    observation_id: entry.invocation_id || `audit:${entry.capability || 'unknown'}:${entry.sequence_number || Date.now()}`,
    source: 'audit',
    observed_at: entry.timestamp || null,
    invocation_id: entry.invocation_id || null,
    task_id: entry.task_id || null,
    parent_invocation_id: entry.parent_invocation_id || null,
    invoked_capability: entry.capability || 'unknown',
    observed_outcome: deriveObservedOutcomeFromAuditEntry(entry),
    reason_code: entry.failure_type || null,
    unresolved_inputs: unresolvedInputs,
    retry_without_progress: false,
    agent_behavior: bindingContext?.requires || null,
    backend_context: entry.event_class || null,
  }
}
