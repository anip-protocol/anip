// studio/src/design/guided/hints.ts

import type { CompletenessHint } from './types'
import { collectRiskLeaves } from './mappings'

/**
 * Evaluate the current requirements artifact and return advisory hints
 * about completeness and potential ambiguity.
 *
 * These are NOT schema validation errors — they are design-quality warnings.
 * They never modify the artifact.
 *
 * Uses the recursive risk_profile walker so nested multi-service risk trees
 * are fully traversed, not just top-level entries.
 */
export function evaluateCompleteness(req: Record<string, any>): CompletenessHint[] {
  const hints: CompletenessHint[] = []
  const bc = req.business_constraints ?? {}
  const riskLeaves = req.risk_profile ? collectRiskLeaves(req.risk_profile) : []

  // Derive intent from risk_profile leaves
  const hasIrreversibleLeaf = riskLeaves.some(l => l.side_effect === 'irreversible')
  const hasHighRiskLeaf = riskLeaves.some(l => l.high_risk === true)
  const hasCostVisibilityLeaf = riskLeaves.some(l => l.cost_visibility_required === true)

  // 1. Spending or irreversible actions without approval expectations
  if (
    (bc.spending_possible || bc.irreversible_actions_present || hasIrreversibleLeaf) &&
    !bc.approval_expected_for_high_risk && !hasHighRiskLeaf
  ) {
    hints.push({
      id: 'spending-no-approval',
      severity: 'warning',
      message: 'Spending or irreversible actions are indicated, but no approval expectation is captured.',
      explanation:
        'Consider whether high-risk actions should have stronger control or approval expectations. ' +
        'You can set this in the Authority and Approval section.',
      relatedFields: [
        'business_constraints.spending_possible',
        'business_constraints.irreversible_actions_present',
        'business_constraints.approval_expected_for_high_risk',
      ],
    })
  }

  // 2. Multi-service shape without cross-service reconstruction
  if (
    req.scale?.shape_preference === 'multi_service_estate' &&
    !req.audit?.cross_service_reconstruction_required
  ) {
    hints.push({
      id: 'multi-service-no-reconstruction',
      severity: 'warning',
      message: 'Multi-service shape is selected, but cross-service reconstruction is not required.',
      explanation:
        'In multi-service estates, operators typically need to reconstruct what happened across services. ' +
        'Consider enabling cross-service reconstruction in the Audit and Traceability section.',
      relatedFields: [
        'scale.shape_preference',
        'audit.cross_service_reconstruction_required',
      ],
    })
  }

  // 3. Multi-service shape without cross-service continuity
  if (
    req.scale?.shape_preference === 'multi_service_estate' &&
    !req.lineage?.cross_service_continuity_required
  ) {
    hints.push({
      id: 'multi-service-no-continuity',
      severity: 'info',
      message: 'Multi-service shape is selected, but cross-service lineage continuity is not required.',
      explanation:
        'Cross-service continuity preserves invocation chains across service boundaries. ' +
        'This is usually important for debugging in multi-service architectures.',
      relatedFields: [
        'scale.shape_preference',
        'lineage.cross_service_continuity_required',
      ],
    })
  }

  // 4. Durable audit without searchable audit
  if (req.audit?.durable && !req.audit?.searchable) {
    hints.push({
      id: 'durable-not-searchable',
      severity: 'info',
      message: 'Durable audit is required, but searchable audit is not specified.',
      explanation:
        'Durable records are useful for compliance, but without searchability ' +
        'operators may struggle to find specific events. Consider whether search is needed.',
      relatedFields: ['audit.durable', 'audit.searchable'],
    })
  }

  // 5. Recovery-sensitive system without blocked/failure posture
  if (
    bc.recovery_sensitive &&
    (!bc.blocked_failure_posture || bc.blocked_failure_posture === 'not_specified')
  ) {
    hints.push({
      id: 'recovery-no-posture',
      severity: 'warning',
      message: 'System is marked recovery-sensitive, but no blocked/failure posture is specified.',
      explanation:
        'If recovery is important, specify what should happen when work is blocked or fails. ' +
        'Options include retry with backoff, escalation to human, or fail-safe behavior.',
      relatedFields: [
        'business_constraints.recovery_sensitive',
        'business_constraints.blocked_failure_posture',
      ],
    })
  }

  // 6. Service-to-service handoffs without multi-service shape
  if (
    req.auth?.service_to_service_handoffs &&
    req.scale?.shape_preference !== 'multi_service_estate' &&
    req.scale?.shape_preference !== 'control_plane_worker_split'
  ) {
    hints.push({
      id: 'handoffs-not-multi-service',
      severity: 'info',
      message: 'Service-to-service handoffs are enabled, but the deployment shape is not multi-service.',
      explanation:
        'Service handoffs typically apply to multi-service or control-plane architectures. ' +
        'Verify that the deployment shape matches the handoff expectations.',
      relatedFields: [
        'auth.service_to_service_handoffs',
        'scale.shape_preference',
      ],
    })
  }

  // 7. High-risk capabilities in risk_profile without cost visibility (recursive)
  if (riskLeaves.length > 0) {
    if (hasHighRiskLeaf && !bc.cost_visibility_required && !hasCostVisibilityLeaf) {
      hints.push({
        id: 'high-risk-no-cost-visibility',
        severity: 'info',
        message: 'High-risk capabilities are defined, but cost visibility is not required.',
        explanation:
          'High-risk capabilities often involve cost. Consider whether operators should see ' +
          'cost information before high-risk actions are executed.',
        relatedFields: [
          'risk_profile',
          'business_constraints.cost_visibility_required',
        ],
      })
    }
  }

  return hints
}
