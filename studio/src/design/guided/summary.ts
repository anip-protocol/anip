// studio/src/design/guided/summary.ts

import { collectRiskLeaves } from './mappings'

function humanizeLabel(value: unknown): string {
  if (value == null) return ''
  const text = String(value).trim()
  if (!text) return ''
  return text
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .replace(/\b\w/g, (match) => match.toUpperCase())
}

function describeDeploymentIntent(value: unknown): string {
  const key = String(value ?? '').trim().toLowerCase()
  const descriptions: Record<string, string> = {
    business_source_document: 'a source business document that drives downstream PM and engineering work',
    embedded_single_process: 'an embedded single-process component',
    production_single_service: 'a single production service',
    public_http_service: 'a public HTTP service',
    control_plane_worker_split: 'a control plane with separate worker processes',
    multi_service_estate: 'a coordinated multi-service production system',
    horizontally_scaled: 'a horizontally scaled production service',
    testing: 'a system primarily used for testing and evaluation',
    production: 'a system intended for production use',
    prod: 'a system intended for production use',
  }
  return descriptions[key] ?? String(value ?? '').trim().replace(/[.]+$/, '')
}

function describeDeliveryShape(value: unknown): string {
  const key = String(value ?? '').trim().toLowerCase()
  const labels: Record<string, string> = {
    embedded_single_process: 'an embedded product experience',
    production_single_service: 'one standalone service',
    horizontally_scaled: 'a horizontally scaled service deployment',
    control_plane_worker_split: 'a coordinator and worker split',
    multi_service_estate: 'multiple coordinated services',
  }
  return labels[key] ?? humanizeLabel(value).toLowerCase()
}

function formatCapabilityLabel(name: string): string {
  const trimmed = String(name ?? '').trim()
  if (!trimmed) return ''
  const lastSegment = trimmed.split('.').pop() ?? trimmed
  return humanizeLabel(lastSegment)
}

/**
 * Generate a plain-language requirements summary from the artifact.
 * Each paragraph covers one aspect. Returns an array of summary paragraphs.
 *
 * Uses the recursive risk_profile walker to derive risk/recovery/cost intent
 * from existing packs that express these in capabilityConfig leaf nodes rather
 * than (or in addition to) business_constraints.* keys.
 */
export function generateRequirementsSummary(
  req: Record<string, any>,
): string[] {
  const parts: string[] = []

  // System identity
  if (req.system) {
    const systemSentence = `${req.system.name} is a ${humanizeLabel(req.system.domain).toLowerCase()} system.`
    const intent = describeDeploymentIntent(req.system.deployment_intent)
    if (intent) {
      parts.push(`${systemSentence} It is intended to be delivered as ${intent}.`)
    } else {
      parts.push(systemSentence)
    }
  }

  // Scale
  if (req.scale) {
    const shape = describeDeliveryShape(req.scale.shape_preference)
    const ha = req.scale.high_availability ? ' with high availability' : ''
    parts.push(`It is expected to run as ${shape}${ha}.`)
  }

  // Collect risk_profile leaves (recursive walk)
  const riskLeaves = req.risk_profile ? collectRiskLeaves(req.risk_profile) : []
  const hasIrreversibleLeaf = riskLeaves.some(l => l.side_effect === 'irreversible')
  const hasCostVisibilityLeaf = riskLeaves.some(l => l.cost_visibility_required === true)
  const hasRecoveryLeaf = riskLeaves.some(l => l.recovery_guidance_required === true)

  // Risk and side effects — merge business_constraints and risk_profile sources
  const bc = req.business_constraints ?? {}
  const riskParts: string[] = []
  if (bc.spending_possible) riskParts.push('actions that can spend money')
  if (bc.irreversible_actions_present || hasIrreversibleLeaf) riskParts.push('irreversible actions')
  if (riskParts.length > 0) {
    const hasCostVis = bc.cost_visibility_required || hasCostVisibilityLeaf
    const costNote = hasCostVis ? ' Cost visibility is required before acting.' : ''
    parts.push(`The system involves ${riskParts.join(' and ')}.${costNote}`)
  }

  // Risk profile capabilities — recursive walk for high_risk
  if (riskLeaves.length > 0) {
    const highRiskLeaves = riskLeaves.filter(l => l.high_risk === true)
    if (highRiskLeaves.length > 0) {
      parts.push(`High-risk actions include: ${highRiskLeaves.map(l => formatCapabilityLabel(l.name)).join(', ')}.`)
    }
  }

  // Authority and control
  const authParts: string[] = []
  if (req.permissions?.preflight_discovery) authParts.push('preflight authority discovery')
  if (req.permissions?.grantable_requirements) authParts.push('grantable restrictions')
  if (req.permissions?.restricted_vs_denied) authParts.push('restricted vs denied distinction')
  if (req.auth?.delegation_tokens) authParts.push('delegation tokens')
  if (req.auth?.scoped_authority) authParts.push('scoped authority')
  if (req.auth?.purpose_binding) authParts.push('purpose binding')
  if (authParts.length > 0) {
    parts.push(`Authority posture includes: ${authParts.join(', ')}.`)
  }
  if (bc.approval_expected_for_high_risk) {
    parts.push('Stronger control or approval expectations are expected for high-risk actions.')
  }

  // Recovery — merge business_constraints and risk_profile sources
  const isRecoverySensitive = bc.recovery_sensitive || hasRecoveryLeaf
  if (isRecoverySensitive) {
    const posture = bc.blocked_failure_posture
    if (posture && posture !== 'not_specified') {
      const postureLabels: Record<string, string> = {
        retry_with_backoff: 'automatic retry with backoff',
        escalate_to_human: 'escalation to a human operator',
        fail_safe: 'fail-safe shutdown',
      }
      parts.push(`Recovery is important — the expected posture for blocked or failed work is ${postureLabels[posture] ?? posture}.`)
    } else if (hasRecoveryLeaf && !bc.recovery_sensitive) {
      const recoveryCaps = riskLeaves
        .filter(l => l.recovery_guidance_required === true)
        .map(l => formatCapabilityLabel(l.name))
      parts.push(`Recovery guidance is required for: ${recoveryCaps.join(', ')}.`)
    } else {
      parts.push('Recovery expectations are flagged as important but no specific posture is defined.')
    }
  }

  // Audit and traceability
  const auditParts: string[] = []
  if (req.audit?.durable) auditParts.push('durable records')
  if (req.audit?.searchable) auditParts.push('searchable history')
  if (req.audit?.cross_service_reconstruction_required) auditParts.push('cross-service reconstruction')
  if (auditParts.length > 0) {
    parts.push(`Traceability requirements: ${auditParts.join(', ')}.`)
  }

  const lineageParts: string[] = []
  if (req.lineage?.invocation_id) lineageParts.push('invocation tracking')
  if (req.lineage?.task_id) lineageParts.push('task grouping')
  if (req.lineage?.parent_invocation_id) lineageParts.push('parent chain tracking')
  if (req.lineage?.client_reference_id) lineageParts.push('client reference IDs')
  if (req.lineage?.cross_service_continuity_required) lineageParts.push('cross-service continuity')
  if (lineageParts.length > 0) {
    parts.push(`Lineage features: ${lineageParts.join(', ')}.`)
  }

  // Multi-service
  if (req.auth?.service_to_service_handoffs) {
    parts.push('Work crosses service boundaries with explicit handoff expectations.')
  }

  // Services inventory
  if (req.services && req.services.length > 0) {
    const names = req.services.map((s: any) => s.name)
    parts.push(`Service inventory: ${names.join(', ')}.`)
  }

  return parts
}
