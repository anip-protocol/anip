import type {
  DeveloperCapabilityFormalization,
  DeveloperCapabilityInputFormalization,
  DeveloperCapabilityInputResolution,
  DeveloperDefinitionData,
} from './project-types'
import type {
  AgentConsumptionReadinessFindingReview,
  AgentConsumptionReadinessReport,
} from './agent-consumption-readiness'
import { normalizeReadinessFindingReviews } from './agent-consumption-readiness'
import { isKnownEffect } from './effect-vocabulary'

export interface AgentConsumabilityMetadata {
  artifact_type: 'agent_consumability_metadata'
  schema_version: 'anip-agent-consumability/v0'
  capabilities: Record<string, AgentConsumabilityCapability>
  selection_hints?: AgentConsumabilitySelectionHint[]
}

export interface AgentConsumabilityCapability {
  intent: {
    category: string
    summary: string
  }
  business_effects?: {
    produces: string[]
    does_not_produce: string[]
  }
  input_semantics?: AgentConsumabilityInputSemantics[]
  required_context?: Array<{
    input: string
    missing_behavior: 'clarify' | 'clarify_or_app_select' | 'use_default' | 'optional'
  }>
  output_semantics?: {
    primary_field: string
    result_type: string
    display_fields: string[]
  }
  result_display?: {
    primary_fields: string[]
    style?: string
  }
  input_meanings?: Record<string, Record<string, string>>
  reference_catalogs?: Record<string, string[]>
  app_boundaries?: {
    guidance?: string
    unsupported_effects?: string[]
    unsupported_terms?: Record<string, string[]>
    conditional_approval_boundary?: {
      when_missing: string[]
      produces: string[]
    }
  }
  approval?: {
    required: boolean
    grant_types: string[]
    approval_effect?: string
  }
  composition?: {
    kind: string
    business_capability: boolean
    steps_visible_to_agent: boolean
  }
  app_glue?: {
    required: boolean
    reason: string
  }
  derived_target_owner?: {
    owner: 'service' | 'app' | 'contract_composition' | 'unresolved'
    reason: string
  }
  intent_rules?: AgentConsumabilityIntentRule[]
  business_language_rules?: AgentConsumabilityBusinessLanguageRule[]
  review?: {
    source: 'manual_review'
    reviewed_at: string
  }
}

export interface AgentConsumabilitySelectionHint {
  capability: string
  all_terms?: string[]
  any_terms?: string[]
  exclude_terms?: string[]
  lock_capability?: boolean
}

export interface AgentConsumabilityInputSemantics {
  input_name: string
  semantic_type: string
  required: boolean
  summary?: string
  resolution?: DeveloperCapabilityInputResolution
  entity_reference?: boolean
  catalog_ref?: string
  allowed_values?: Array<{
    value: string
    meaning: string
  }>
}

export interface AgentConsumabilityIntentRule {
  id: string
  meaning: string
  owner: 'product_contract' | 'developer_contract' | 'service' | 'agent_app_glue'
  applies_when?: string
  agent_action?: string
  service_behavior?: string
}

export interface AgentConsumabilityBusinessLanguageRule {
  id: string
  meaning: string
  owner: 'product_contract' | 'developer_contract' | 'service' | 'agent_app_glue'
  applies_when: {
    all_terms?: string[]
    any_terms?: string[]
    exclude_terms?: string[]
  }
  interpretation: string
  agent_action?: 'treat_as_supported' | 'treat_as_purpose' | 'prefer_capability' | 'clarify'
  target_capability?: string
  suppress_unsupported_effects?: string[]
}

export interface AgentConsumabilityCapabilityReview {
  capability_id: string
  reviewed_at: string
  intent_category?: string
  intent_summary?: string
  app_glue_required?: boolean
  app_glue_reason?: string
  intent_rules?: AgentConsumabilityIntentRule[]
  business_language_rules?: AgentConsumabilityBusinessLanguageRule[]
  input_meanings?: Record<string, Record<string, string>>
  reference_catalogs?: Record<string, string[]>
  app_boundaries?: AgentConsumabilityCapability['app_boundaries']
  selection_hints?: AgentConsumabilitySelectionHint[]
}

export function buildAgentConsumabilityMetadata(params: {
  definition: DeveloperDefinitionData | null | undefined
  readiness?: AgentConsumptionReadinessReport | null
  manualReviews?: Record<string, AgentConsumabilityCapabilityReview> | null
}): AgentConsumabilityMetadata {
  const capabilities = params.definition?.capability_formalizations ?? []
  const reviews = normalizeReadinessFindingReviews(params.readiness?.finding_reviews)
  const manualReviews = normalizeAgentConsumabilityReviews(params.manualReviews)
  const selectionHints = Object.values(manualReviews)
    .flatMap((review) => review.selection_hints ?? [])
    .filter((hint) => hint.capability.trim())
  return withoutEmptyValues({
    artifact_type: 'agent_consumability_metadata',
    schema_version: 'anip-agent-consumability/v0',
    capabilities: Object.fromEntries(capabilities
      .filter((capability) => capability.capability_id)
      .map((capability) => [
        capability.capability_id,
        buildCapabilityConsumability(capability, reviews, manualReviews[capability.capability_id]),
      ])),
    selection_hints: selectionHints,
  })
}

function buildCapabilityConsumability(
  capability: DeveloperCapabilityFormalization,
  reviews: Record<string, AgentConsumptionReadinessFindingReview>,
  manualReview?: AgentConsumabilityCapabilityReview,
): AgentConsumabilityCapability {
  const appGlueReviews = Object.values(reviews).filter((review) =>
    review.id.startsWith(`${capability.capability_id}:`) && review.decision === 'explicit_app_glue',
  )
  const derivedTargetReview = Object.values(reviews).find((review) =>
    review.id === `${capability.capability_id}:derived-target`,
  )
  const inputSemantics = capability.inputs
    .map((input) => buildInputSemantics(input))
    .filter((input): input is AgentConsumabilityInputSemantics => input != null)
  const requiredContext = capability.inputs
    .filter((input) => input.required || input.entity_reference || Boolean(input.semantic_type))
    .map((input) => ({
      input: input.input_name,
      missing_behavior: missingBehaviorForInput(input, appGlueReviews.length > 0),
    }))
  if (requiredContext.length === 0 && appGlueReviews.length > 0) {
    requiredContext.push({
      input: 'derived_target',
      missing_behavior: 'clarify_or_app_select',
    })
  }

  const businessEffects = effectiveBusinessEffects(capability)
  const generated = withoutEmptyValues({
    intent: {
      category: capabilityCategory(capability),
      summary: capabilityIntentSummary(capability),
    },
    business_effects: businessEffects,
    input_semantics: inputSemantics,
    required_context: requiredContext,
    output_semantics: {
      primary_field: 'result',
      result_type: capability.output_shape || capability.output_intent || 'result',
      display_fields: ['result'],
    },
    result_display: {
      primary_fields: ['result'],
      style: resultDisplayStyle(capability),
    },
    input_meanings: buildInputMeanings(capability.inputs),
    reference_catalogs: buildReferenceCatalogs(capability.inputs),
    app_boundaries: buildAppBoundaries(capability, businessEffects),
    approval: capability.grant_policy
      ? {
          required: true,
          grant_types: capability.grant_policy.allowed_grant_types,
          approval_effect: approvalEffect(capability),
        }
      : undefined,
    composition: capability.kind === 'composed' && capability.composition
      ? {
          kind: capability.composition.authority_boundary,
          business_capability: true,
          steps_visible_to_agent: false,
        }
      : undefined,
    app_glue: appGlueReviews.length > 0
      ? {
          required: true,
          reason: appGlueReviews.map((review) => review.note).filter(Boolean).join(' '),
        }
      : undefined,
    derived_target_owner: derivedTargetReview
      ? {
          owner: derivedTargetOwner(derivedTargetReview.decision),
          reason: derivedTargetReview.note,
        }
      : undefined,
  })
  return applyManualReview(generated, manualReview)
}

function capabilityIntentSummary(capability: DeveloperCapabilityFormalization): string {
  const summary = capability.summary?.trim()
  if (summary && !isOwnershipPlaceholder(summary)) return summary
  const title = capability.title?.trim()
  if (title && !isNamespaceTitlePlaceholder(title, capability.capability_id)) return title
  return titleFromCapabilityId(capability.capability_id)
}

function isOwnershipPlaceholder(value: string): boolean {
  return /^capability owned by .+\.$/i.test(value.trim())
}

function isNamespaceTitlePlaceholder(value: string, capabilityId: string): boolean {
  const namespace = capabilityId.includes('.') ? capabilityId.split('.')[0] : ''
  return Boolean(namespace) && value.trim().toLowerCase().startsWith(`${namespace.toLowerCase()}.`)
}

function titleFromCapabilityId(capabilityId: string): string {
  const localName = capabilityId.includes('.') ? capabilityId.split('.').slice(1).join('.') : capabilityId
  const text = localName.replace(/[._-]+/g, ' ').trim()
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : capabilityId
}

function applyManualReview(
  generated: AgentConsumabilityCapability,
  manualReview?: AgentConsumabilityCapabilityReview,
): AgentConsumabilityCapability {
  if (!manualReview) return generated
  const intentCategory = manualReview.intent_category?.trim()
  const intentSummary = manualReview.intent_summary?.trim()
  const appGlueReason = manualReview.app_glue_reason?.trim()
  const intentRules = (manualReview.intent_rules ?? []).filter((rule) =>
    rule.id.trim() && rule.meaning.trim(),
  )
  const businessLanguageRules = (manualReview.business_language_rules ?? []).filter((rule) =>
    rule.id.trim() && rule.meaning.trim() && rule.interpretation.trim(),
  )
  return withoutEmptyValues({
    ...generated,
    intent: {
      category: intentCategory || generated.intent.category,
      summary: intentSummary || generated.intent.summary,
    },
    app_glue: manualReview.app_glue_required || appGlueReason
      ? {
          required: true,
          reason: appGlueReason || generated.app_glue?.reason || 'The consuming app must provide package-specific presentation, target selection, or boundary guidance for this capability.',
        }
      : generated.app_glue,
    intent_rules: intentRules.length > 0 ? intentRules : generated.intent_rules,
    business_language_rules: businessLanguageRules.length > 0
      ? businessLanguageRules
      : generated.business_language_rules,
    input_meanings: manualReview.input_meanings ?? generated.input_meanings,
    reference_catalogs: manualReview.reference_catalogs ?? generated.reference_catalogs,
    app_boundaries: mergeAppBoundaries(generated.app_boundaries, manualReview.app_boundaries),
    review: {
      source: 'manual_review',
      reviewed_at: manualReview.reviewed_at,
    },
  })
}

function mergeAppBoundaries(
  generated: AgentConsumabilityCapability['app_boundaries'] | undefined,
  manual: AgentConsumabilityCapability['app_boundaries'] | undefined,
): AgentConsumabilityCapability['app_boundaries'] | undefined {
  if (!generated) return manual
  if (!manual) return generated
  return withoutEmptyValues({
    ...generated,
    ...manual,
    unsupported_effects: Array.from(new Set([
      ...(generated.unsupported_effects ?? []),
      ...(manual.unsupported_effects ?? []),
    ])),
    unsupported_terms: {
      ...(generated.unsupported_terms ?? {}),
      ...(manual.unsupported_terms ?? {}),
    },
    conditional_approval_boundary: manual.conditional_approval_boundary ?? generated.conditional_approval_boundary,
  })
}

export function normalizeAgentConsumabilityReviews(
  value: unknown,
): Record<string, AgentConsumabilityCapabilityReview> {
  if (!value || typeof value !== 'object') return {}
  const result: Record<string, AgentConsumabilityCapabilityReview> = {}
  for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
    if (!item || typeof item !== 'object') continue
    const raw = item as Record<string, unknown>
    const capabilityId = typeof raw.capability_id === 'string' && raw.capability_id.trim()
      ? raw.capability_id.trim()
      : key
    if (!capabilityId) continue
    result[capabilityId] = withoutEmptyValues({
      capability_id: capabilityId,
      reviewed_at: typeof raw.reviewed_at === 'string' && raw.reviewed_at.trim()
        ? raw.reviewed_at
        : new Date(0).toISOString(),
      intent_category: typeof raw.intent_category === 'string' ? raw.intent_category : undefined,
      intent_summary: typeof raw.intent_summary === 'string' ? raw.intent_summary : undefined,
      app_glue_required: raw.app_glue_required === true,
      app_glue_reason: typeof raw.app_glue_reason === 'string' ? raw.app_glue_reason : undefined,
      intent_rules: normalizeIntentRules(raw.intent_rules),
      business_language_rules: normalizeBusinessLanguageRules(raw.business_language_rules),
      input_meanings: normalizeNestedStringMap(raw.input_meanings),
      reference_catalogs: normalizeStringListMap(raw.reference_catalogs),
      app_boundaries: normalizeAppBoundaries(raw.app_boundaries),
      selection_hints: normalizeSelectionHints(raw.selection_hints),
    })
  }
  return result
}

function normalizeBusinessLanguageRules(value: unknown): AgentConsumabilityBusinessLanguageRule[] | undefined {
  if (!Array.isArray(value)) return undefined
  const rules = value.flatMap((item, index) => {
    if (!item || typeof item !== 'object') return []
    const raw = item as Record<string, unknown>
    const id = typeof raw.id === 'string' && raw.id.trim() ? raw.id.trim() : `business-language-rule-${index + 1}`
    const meaning = typeof raw.meaning === 'string' ? raw.meaning.trim() : ''
    const interpretation = typeof raw.interpretation === 'string' ? raw.interpretation.trim() : ''
    const owner = isIntentRuleOwner(raw.owner) ? raw.owner : 'agent_app_glue'
    const appliesWhen = normalizeBusinessLanguageCondition(raw.applies_when)
    if (!meaning || !interpretation || Object.keys(appliesWhen).length === 0) return []
    return [withoutEmptyValues({
      id,
      meaning,
      owner,
      applies_when: appliesWhen,
      interpretation,
      agent_action: isBusinessLanguageAction(raw.agent_action) ? raw.agent_action : undefined,
      target_capability: typeof raw.target_capability === 'string' && raw.target_capability.trim()
        ? raw.target_capability.trim()
        : undefined,
      suppress_unsupported_effects: normalizeStringList(raw.suppress_unsupported_effects),
    })]
  })
  return rules.length > 0 ? rules : undefined
}

function normalizeBusinessLanguageCondition(value: unknown): AgentConsumabilityBusinessLanguageRule['applies_when'] {
  if (!value || typeof value !== 'object') return {}
  const raw = value as Record<string, unknown>
  return withoutEmptyValues({
    all_terms: normalizeStringList(raw.all_terms),
    any_terms: normalizeStringList(raw.any_terms),
    exclude_terms: normalizeStringList(raw.exclude_terms),
  })
}

function buildInputMeanings(inputs: DeveloperCapabilityInputFormalization[]): Record<string, Record<string, string>> | undefined {
  const entries = inputs.flatMap((input) => {
    const values = (input.allowed_values ?? []).filter((value) => value.trim())
    if (values.length === 0) return []
    return [[input.input_name, Object.fromEntries(values.map((value) => [value, meaningForAllowedValue(input, value)]))] as const]
  })
  return entries.length > 0 ? Object.fromEntries(entries) : undefined
}

function buildReferenceCatalogs(inputs: DeveloperCapabilityInputFormalization[]): Record<string, string[]> | undefined {
  const entries = inputs.flatMap((input) => {
    const reviewedCatalog = (input.reference_catalog ?? []).filter((value) => value.trim())
    const values = reviewedCatalog.length > 0 ? reviewedCatalog : (input.allowed_values ?? []).filter((value) => value.trim())
    if (!input.entity_reference || values.length === 0) return []
    return [[input.input_name, values] as const]
  })
  return entries.length > 0 ? Object.fromEntries(entries) : undefined
}

function buildAppBoundaries(
  capability: DeveloperCapabilityFormalization,
  businessEffects = effectiveBusinessEffects(capability),
): AgentConsumabilityCapability['app_boundaries'] | undefined {
  const doesNotProduce = businessEffects?.does_not_produce ?? []
  if (doesNotProduce.length === 0) return undefined
  const boundaries: AgentConsumabilityCapability['app_boundaries'] = {
    unsupported_effects: doesNotProduce,
  }
  if (capability.grant_policy && (businessEffects?.produces ?? []).some((effect) => ['approval.request', 'system.preview_mutation'].includes(effect))) {
    boundaries.guidance = 'This capability is approval-governed. Invoke it to produce the service-owned preview/request; do not execute the governed action in app code.'
  }
  return boundaries
}

function resultDisplayStyle(capability: DeveloperCapabilityFormalization): string | undefined {
  const produces = effectiveBusinessEffects(capability)?.produces ?? []
  if (produces.includes('content.draft')) return 'Show generated draft content first, then rationale and evidence.'
  if (produces.includes('content.recommendation')) return 'Show recommendations or variants with concise rationale.'
  if (produces.includes('content.summary')) return 'Show the bounded summary and key supporting evidence.'
  if (produces.includes('approval.request') || produces.includes('system.preview_mutation')) return 'Show preview, approval requirement, and bounded impact before details.'
  return undefined
}

function effectiveBusinessEffects(capability: DeveloperCapabilityFormalization): AgentConsumabilityCapability['business_effects'] | undefined {
  const declared = capability.business_effects
  if (!capability.grant_policy) return declared
  const produces = new Set(declared?.produces ?? [])
  const doesNotProduce = new Set(declared?.does_not_produce ?? [])
  produces.delete('data.read')
  produces.add('approval.request')
  produces.add('system.preview_mutation')
  doesNotProduce.add('approval.execute')
  return {
    produces: Array.from(produces),
    does_not_produce: Array.from(doesNotProduce),
  }
}

function normalizeIntentRules(value: unknown): AgentConsumabilityIntentRule[] {
  if (!Array.isArray(value)) return []
  return value.flatMap((item, index) => {
    if (!item || typeof item !== 'object') return []
    const raw = item as Record<string, unknown>
    const id = typeof raw.id === 'string' && raw.id.trim() ? raw.id.trim() : `intent-rule-${index + 1}`
    const meaning = typeof raw.meaning === 'string' ? raw.meaning.trim() : ''
    const owner = isIntentRuleOwner(raw.owner) ? raw.owner : 'agent_app_glue'
    if (!meaning) return []
    return [withoutEmptyValues({
      id,
      meaning,
      owner,
      applies_when: typeof raw.applies_when === 'string' ? raw.applies_when : undefined,
      agent_action: typeof raw.agent_action === 'string' ? raw.agent_action : undefined,
      service_behavior: typeof raw.service_behavior === 'string' ? raw.service_behavior : undefined,
    })]
  })
}

function normalizeNestedStringMap(value: unknown): Record<string, Record<string, string>> | undefined {
  if (!value || typeof value !== 'object') return undefined
  const result: Record<string, Record<string, string>> = {}
  for (const [outerKey, rawInner] of Object.entries(value as Record<string, unknown>)) {
    if (!outerKey.trim() || !rawInner || typeof rawInner !== 'object') continue
    const inner: Record<string, string> = {}
    for (const [innerKey, rawValue] of Object.entries(rawInner as Record<string, unknown>)) {
      if (innerKey.trim() && typeof rawValue === 'string' && rawValue.trim()) {
        inner[innerKey] = rawValue.trim()
      }
    }
    if (Object.keys(inner).length > 0) result[outerKey] = inner
  }
  return Object.keys(result).length > 0 ? result : undefined
}

function normalizeStringListMap(value: unknown): Record<string, string[]> | undefined {
  if (!value || typeof value !== 'object') return undefined
  const result: Record<string, string[]> = {}
  for (const [key, rawList] of Object.entries(value as Record<string, unknown>)) {
    if (!key.trim() || !Array.isArray(rawList)) continue
    const values = rawList.flatMap((item) => typeof item === 'string' && item.trim() ? [item.trim()] : [])
    if (values.length > 0) result[key] = values
  }
  return Object.keys(result).length > 0 ? result : undefined
}

function normalizeAppBoundaries(value: unknown): AgentConsumabilityCapability['app_boundaries'] | undefined {
  if (!value || typeof value !== 'object') return undefined
  const raw = value as Record<string, unknown>
  const conditional = raw.conditional_approval_boundary && typeof raw.conditional_approval_boundary === 'object'
    ? raw.conditional_approval_boundary as Record<string, unknown>
    : null
  const result = withoutEmptyValues({
    guidance: typeof raw.guidance === 'string' ? raw.guidance.trim() : undefined,
    unsupported_effects: Array.isArray(raw.unsupported_effects)
      ? raw.unsupported_effects.flatMap((item) => {
          const effect = typeof item === 'string' ? item.trim() : ''
          return effect && isKnownEffect(effect) ? [effect] : []
        })
      : undefined,
    unsupported_terms: normalizeStringListMap(raw.unsupported_terms),
    conditional_approval_boundary: conditional
      ? withoutEmptyValues({
          when_missing: Array.isArray(conditional.when_missing)
            ? conditional.when_missing.flatMap((item) => typeof item === 'string' && item.trim() ? [item.trim()] : [])
            : [],
          produces: Array.isArray(conditional.produces)
            ? conditional.produces.flatMap((item) => typeof item === 'string' && item.trim() ? [item.trim()] : [])
            : [],
        })
      : undefined,
  })
  return Object.keys(result).length > 0 ? result : undefined
}

function normalizeSelectionHints(value: unknown): AgentConsumabilitySelectionHint[] | undefined {
  if (!Array.isArray(value)) return undefined
  const hints = value.flatMap((item) => {
    if (!item || typeof item !== 'object') return []
    const raw = item as Record<string, unknown>
    const capability = typeof raw.capability === 'string' ? raw.capability.trim() : ''
    if (!capability) return []
    return [withoutEmptyValues({
      capability,
      all_terms: normalizeStringList(raw.all_terms),
      any_terms: normalizeStringList(raw.any_terms),
      exclude_terms: normalizeStringList(raw.exclude_terms),
      lock_capability: raw.lock_capability === true,
    })]
  })
  return hints.length > 0 ? hints : undefined
}

function normalizeStringList(value: unknown): string[] | undefined {
  if (!Array.isArray(value)) return undefined
  const values = value.flatMap((item) => typeof item === 'string' && item.trim() ? [item.trim()] : [])
  return values.length > 0 ? values : undefined
}

function isIntentRuleOwner(value: unknown): value is AgentConsumabilityIntentRule['owner'] {
  return value === 'product_contract'
    || value === 'developer_contract'
    || value === 'service'
    || value === 'agent_app_glue'
}

function isBusinessLanguageAction(value: unknown): value is NonNullable<AgentConsumabilityBusinessLanguageRule['agent_action']> {
  return value === 'treat_as_supported'
    || value === 'treat_as_purpose'
    || value === 'prefer_capability'
    || value === 'clarify'
}

function buildInputSemantics(input: DeveloperCapabilityInputFormalization): AgentConsumabilityInputSemantics | null {
  const allowedValues = (input.allowed_values ?? [])
    .filter((value) => value.trim())
    .map((value) => ({
      value,
      meaning: meaningForAllowedValue(input, value),
    }))
  if (!input.entity_reference && allowedValues.length === 0 && !input.summary) return null
  return withoutEmptyValues({
    input_name: input.input_name,
    semantic_type: input.semantic_type || (input.entity_reference ? `${input.input_name}_reference` : semanticTypeForInput(input)),
    required: input.required,
    summary: input.summary,
    resolution: input.resolution,
    entity_reference: input.entity_reference || undefined,
    catalog_ref: input.catalog_ref,
    allowed_values: allowedValues,
  })
}

function capabilityCategory(capability: DeveloperCapabilityFormalization): string {
  const withoutNamespace = capability.capability_id.includes('.')
    ? capability.capability_id.split('.').slice(1).join('.')
    : capability.capability_id
  return withoutNamespace.replace(/_/g, '.')
}

function semanticTypeForInput(input: DeveloperCapabilityInputFormalization): string {
  if (input.input_format || input.validation_pattern || input.clarification_hint) return 'business_context'
  if ((input.allowed_values ?? []).length > 0) return 'business_category'
  return input.input_type || 'value'
}

function missingBehaviorForInput(
  input: DeveloperCapabilityInputFormalization,
  appGlueRequired: boolean,
): 'clarify' | 'clarify_or_app_select' | 'use_default' | 'optional' {
  if (String(input.default_value ?? '').trim()) return 'use_default'
  if (appGlueRequired && input.required) {
    return 'clarify_or_app_select'
  }
  if (input.required || input.clarification_hint) return 'clarify'
  return 'optional'
}

function meaningForAllowedValue(input: DeveloperCapabilityInputFormalization, value: string): string {
  if (input.normalization_context) return `${value} within ${input.normalization_context}`
  if (input.normalization_hint) return `${value}; ${input.normalization_hint}`
  return value.replace(/[_-]/g, ' ')
}

function approvalEffect(capability: DeveloperCapabilityFormalization): string | undefined {
  const produces = capability.business_effects?.produces ?? []
  return produces.find((effect) => effect.startsWith('approval.'))
    ?? produces.find((effect) => effect.includes('mutation'))
}

function derivedTargetOwner(decision: AgentConsumptionReadinessFindingReview['decision']): 'service' | 'app' | 'contract_composition' | 'unresolved' {
  if (decision === 'acceptable_warning') return 'service'
  if (decision === 'explicit_app_glue') return 'app'
  if (decision === 'contract_composition') return 'contract_composition'
  return 'unresolved'
}

function withoutEmptyValues<T extends Record<string, any>>(value: T): T {
  return Object.fromEntries(Object.entries(value).filter(([, entry]) =>
    entry !== undefined
    && (!Array.isArray(entry) || entry.length > 0)
    && (!(entry && typeof entry === 'object') || Array.isArray(entry) || Object.keys(entry).length > 0),
  )) as T
}
