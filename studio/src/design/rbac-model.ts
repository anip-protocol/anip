import { developerLabel } from './developer-vocabulary'
import type {
  DeveloperCapabilityFormalization,
  DeveloperDefinitionData,
  DeveloperPermissionIntentRuleBinding,
} from './project-types'

export type RbacDecision = 'allow' | 'allow_with_limits' | 'approval_required' | 'clarify' | 'deny'

export interface RbacPermission {
  id: string
  label: string
  businessArea: string
  decision: RbacDecision
  decisionLabel: string
  sourceRuleIds: string[]
  actorIds: string[]
  serviceIds: string[]
  capabilityIds: string[]
  businessRules: string[]
}

export interface RbacRoleAssignment {
  actorId: string
  ruleId: string
  permissionId: string
  decision: RbacDecision
}

export interface RbacCapabilityRequirement {
  capability: DeveloperCapabilityFormalization
  permissionIds: string[]
}

export interface RbacModel {
  permissions: RbacPermission[]
  roleAssignments: RbacRoleAssignment[]
  capabilityRequirements: RbacCapabilityRequirement[]
}

export function rbacDecisionForRule(rule: DeveloperPermissionIntentRuleBinding): RbacDecision {
  const access = rule.access_posture
  const outcome = rule.governed_outcome_type
  if (access === 'denied' || outcome === 'deny_request') return 'deny'
  if (outcome === 'clarification_required') return 'clarify'
  if (access === 'approval_required' || outcome === 'approval_required' || outcome === 'approval_stop') return 'approval_required'
  if (access === 'bounded' || access === 'restricted' || outcome === 'bounded_result' || outcome === 'masked_or_restricted_result') return 'allow_with_limits'
  return 'allow'
}

export function rbacDecisionLabel(decision: RbacDecision): string {
  if (decision === 'deny') return 'Deny'
  if (decision === 'clarify') return 'Clarify'
  if (decision === 'approval_required') return 'Require approval'
  if (decision === 'allow_with_limits') return 'Allow with limits'
  return 'Allow'
}

export function rbacPermissionLabel(rule: DeveloperPermissionIntentRuleBinding): string {
  return rule.business_area_label || developerLabel(rule.business_area, 'Unnamed permission')
}

export function effectivePermissionCapabilityIds(
  definition: DeveloperDefinitionData,
  rule: DeveloperPermissionIntentRuleBinding,
): string[] {
  const serviceIds = new Set(rule.target_service_ids)
  const allowed = new Set(
    definition.capability_formalizations
      .filter((capability) => serviceIds.has(capability.service_id))
      .map((capability) => capability.capability_id),
  )
  if (rule.target_capability_ids?.length) {
    return unique(rule.target_capability_ids.filter((capabilityId) => allowed.has(capabilityId))).sort()
  }
  return unique([...allowed]).sort()
}

export function rbacPermissionIdForRule(
  definition: DeveloperDefinitionData,
  rule: DeveloperPermissionIntentRuleBinding,
): string {
  const label = rbacPermissionLabel(rule).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
  const decision = rbacDecisionForRule(rule)
  const capabilityPart = effectivePermissionCapabilityIds(definition, rule).join('-')
  const servicePart = unique(rule.target_service_ids).sort().join('-')
  return [label || 'permission', decision, capabilityPart, servicePart].filter(Boolean).join('__')
}

export function buildRbacModel(definition: DeveloperDefinitionData | null | undefined): RbacModel {
  if (!definition) {
    return {
      permissions: [],
      roleAssignments: [],
      capabilityRequirements: [],
    }
  }

  const permissions = new Map<string, RbacPermission>()
  const roleAssignments: RbacRoleAssignment[] = []

  for (const rule of definition.permission_intent_bindings) {
    const permissionId = rbacPermissionIdForRule(definition, rule)
    const decision = rbacDecisionForRule(rule)
    const capabilityIds = effectivePermissionCapabilityIds(definition, rule)
    const existing = permissions.get(permissionId)
    if (existing) {
      existing.sourceRuleIds = unique([...existing.sourceRuleIds, rule.id])
      existing.actorIds = unique([...existing.actorIds, rule.actor_id])
      existing.serviceIds = unique([...existing.serviceIds, ...rule.target_service_ids]).sort()
      existing.capabilityIds = unique([...existing.capabilityIds, ...capabilityIds]).sort()
      existing.businessRules = unique([...existing.businessRules, rule.governed_outcome].filter(Boolean))
    } else {
      permissions.set(permissionId, {
        id: permissionId,
        label: rbacPermissionLabel(rule),
        businessArea: rule.business_area,
        decision,
        decisionLabel: rbacDecisionLabel(decision),
        sourceRuleIds: [rule.id],
        actorIds: unique([rule.actor_id]),
        serviceIds: unique(rule.target_service_ids).sort(),
        capabilityIds,
        businessRules: unique([rule.governed_outcome].filter(Boolean)),
      })
    }

    roleAssignments.push({
      actorId: rule.actor_id,
      ruleId: rule.id,
      permissionId,
      decision,
    })
  }

  const capabilityRequirements = definition.capability_formalizations.map((capability) => ({
    capability,
    permissionIds: [...permissions.values()]
      .filter((permission) => permission.capabilityIds.includes(capability.capability_id))
      .map((permission) => permission.id),
  }))

  return {
    permissions: [...permissions.values()].sort((left, right) => left.label.localeCompare(right.label)),
    roleAssignments,
    capabilityRequirements,
  }
}

function unique(values: string[]): string[] {
  return [...new Set(values.map((value) => String(value || '').trim()).filter(Boolean))]
}
