// studio/src/design/guided/summary.ts

import { collectRiskLeaves } from './mappings'

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
    parts.push(
      `${req.system.name} is a ${req.system.domain} system intended for ${req.system.deployment_intent}.`,
    )
  }

  // Scale
  if (req.scale) {
    const shapeLabels: Record<string, string> = {
      embedded_single_process: 'an embedded single-process deployment',
      production_single_service: 'a single production service',
      horizontally_scaled: 'a horizontally scaled deployment',
      control_plane_worker_split: 'a control-plane and worker split',
      multi_service_estate: 'a multi-service estate',
    }
    const shape = shapeLabels[req.scale.shape_preference] ?? req.scale.shape_preference
    const ha = req.scale.high_availability ? ' with high availability' : ''
    parts.push(`It targets ${shape}${ha}.`)
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
      parts.push(`High-risk capabilities: ${highRiskLeaves.map(l => l.name).join(', ')}.`)
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
      const recoveryCaps = riskLeaves.filter(l => l.recovery_guidance_required === true).map(l => l.name)
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
