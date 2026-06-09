import type {
  ApplicationIntegrationProjectState,
} from '../application-integration/types'
import type {
  DataAccessProjectState,
} from '../data-access/types'
import { inputContractEvidenceJsonCandidates } from './input-contract-evidence'
import type { ScenarioAdditionalContextEntry, ScenarioAdditionalContextSemanticType } from './types'
import type {
  ArtifactRecord,
  DesignSectionSufficiencyCard,
  DeveloperActorExpectationBinding,
  DeveloperApplicationIntegrationApprovalRule,
  DeveloperApplicationIntegrationClarificationRule,
  DeveloperApplicationIntegrationDenialRule,
  DeveloperApplicationIntegrationGovernanceFormalization,
  DeveloperApplicationIntegrationPermissionRule,
  DeveloperApplicationIntegrationRestrictionRule,
  DeveloperApplicationIntegrationSafeDefaults,
  DeveloperApplicationObjectFormalization,
  DeveloperApplicationObjectFieldFormalization,
  DeveloperApplicationObjectRelationshipFormalization,
  DeveloperArchitectureShape,
  DeveloperBaselineData,
  DeveloperBusinessEffects,
  DeveloperBusinessGoalBinding,
  DeveloperCapabilityFormalization,
  DeveloperCapabilityInputFormalization,
  DeveloperCapabilityInputResolution,
  DeveloperCapabilityInputResolutionBehavior,
  DeveloperCapabilityInputResolutionMode,
  DeveloperCodegenAdapter,
  DeveloperCompiledContractIdentity,
  DeveloperComposition,
  DeveloperExtensionPoint,
  DeveloperCompositionStep,
  DeveloperGeneratedCapabilityOwnership,
  DeveloperGeneratedConformanceReport,
  DeveloperGeneratedIntegrationAdapterBinding,
  DeveloperGeneratedRuntimeService,
  DeveloperGeneratedRuntimeTarget,
  DeveloperGeneratedServiceTarget,
  DeveloperGeneratedStructureSummary,
  DeveloperGenerationRunData,
  DeveloperGrantType,
  DeveloperGrantPolicy,
  DeveloperImplementationFit,
  DeveloperIntegrationFrontingBackendBinding,
  DeveloperIntegrationFrontingCapabilityMapping,
  IntegrationDiscoveryRecord,
  DeveloperCompositionRuleBinding,
  DeveloperDataAccessScenarioPackExpectation,
  DeveloperDataAccessClarificationRule,
  DeveloperDataDomainFormalization,
  DeveloperDataDimensionDefinition,
  DeveloperDataFilterDefinition,
  DeveloperDataAccessDimensionRule,
  DeveloperDataAccessGovernanceFormalization,
  DeveloperDataAccessLimitRule,
  DeveloperDataMetricDefinition,
  DeveloperDataAccessMetricRule,
  DeveloperDataAccessUseRule,
  DeveloperDeliveryModel,
  DeveloperDefinitionData,
  DeveloperDomainConceptBinding,
  DeveloperNonGoalGuard,
  DeveloperScenarioOutcomeType,
  DeveloperScenarioOrchestrationStep,
  DeveloperScenarioFormalization,
  DeveloperServiceBackendBinding,
  DeveloperServiceTopologyBinding,
  DeveloperSuccessCriteriaCheck,
  DeveloperSupportedQuestionFamilyBinding,
  DeveloperScenarioStepKind,
  DeveloperPermissionIntentRuleBinding,
  ProjectDetail,
  RequirementsRecord,
  ShapeRecord,
  TraceabilityCoverageItem,
  TraceabilityRecordData,
  EvaluationObservedServiceEvidenceSummary,
} from './project-types'
import type { ObservedServiceMetadata } from './types'
import {
  ASSISTANT_SECTION_CLARIFICATIONS_ARTIFACT_TYPE,
  findActorModelArtifact,
  findNonGoalsArtifact,
  findPermissionIntentArtifact,
  findProductSummaryArtifact,
  resolveBusinessAreaLabel,
  findSuccessCriteriaArtifact,
  type ActorModelData,
  type BusinessAreasData,
  type NonGoalsData,
  type PermissionIntentData,
  type PermissionIntentRule,
  type ProductSummaryData,
  type SuccessCriteriaData,
  isActorModelComplete,
  isBusinessAreasComplete,
  isNonGoalsComplete,
  isPermissionIntentComplete,
  isProductSummaryComplete,
  isSuccessCriteriaComplete,
  findBusinessAreasArtifact,
} from './product-design'
import { KNOWN_EFFECT_IDS, isKnownEffect } from './effect-vocabulary'

export const DEVELOPER_DEFINITION_ARTIFACT_TYPE = 'developer_definition'
export const DEVELOPER_DEFINITION_REVISION_ARTIFACT_TYPE = 'developer_definition_revision'
export const DEVELOPER_GENERATION_RUN_ARTIFACT_TYPE = 'developer_generation_run'
export const INTEGRATION_FRONTING_MAPPING_ARTIFACT_TYPE = 'integration_fronting_capability_mapping'

export function developerDefinitionArtifactId(projectId: string): string {
  return `${projectId}-developer-definition`
}

export function developerDefinitionRevisionArtifactId(projectId: string, revisionNumber: number): string {
  return `${projectId}-developer-definition-revision-${revisionNumber}`
}

export interface DeveloperDefinitionValidationIssue {
  path: string
  label: string
  message: string
}

function hasText(value: unknown): boolean {
  return typeof value === 'string' && value.trim().length > 0
}

function hasItems(value: unknown): boolean {
  return Array.isArray(value) && value.length > 0
}

const COMPOSITION_INPUT_PATH_PATTERN = /^\$\.input(?:\.[A-Za-z_][A-Za-z0-9_]*)+$/
const COMPOSITION_STEP_PATH_PATTERN = /^\$\.steps\.([A-Za-z_][A-Za-z0-9_-]*)\.output(?:\.[A-Za-z_][A-Za-z0-9_]*)+$/
const INPUT_SEMANTIC_TYPE_PATTERN = /^[A-Za-z_][A-Za-z0-9_]*$/
const INPUT_CATALOG_REF_PATTERN = /^[A-Za-z_][A-Za-z0-9_.:-]{0,127}$/
const SERVICE_ID_PATTERN = /^[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*$/

function compositionParentInputName(pathValue: unknown): string | null {
  const text = String(pathValue ?? '').trim()
  if (!COMPOSITION_INPUT_PATH_PATTERN.test(text)) return null
  return text.slice('$.input.'.length).split('.')[0] || null
}

function compositionStepOutputId(pathValue: unknown): string | null {
  const text = String(pathValue ?? '').trim()
  const match = text.match(COMPOSITION_STEP_PATH_PATTERN)
  return match?.[1] ?? null
}

function compactCompositionInputMapping(mapping: DeveloperComposition['input_mapping'] | undefined): DeveloperComposition['input_mapping'] {
  const compacted: DeveloperComposition['input_mapping'] = {}
  for (const [stepId, stepMapping] of Object.entries(mapping ?? {})) {
    const entries = Object.entries(stepMapping ?? {})
      .map(([inputName, pathValue]) => [inputName, String(pathValue ?? '').trim()] as const)
      .filter(([, pathValue]) => pathValue.length > 0)
    if (entries.length) {
      compacted[stepId] = Object.fromEntries(entries)
    }
  }
  return compacted
}

function compactDeveloperComposition(composition: DeveloperComposition | null | undefined): DeveloperComposition | null {
  if (!composition) return null
  const steps = (composition.steps ?? []).map((step, index) => {
    const compacted: DeveloperCompositionStep = {
      id: step.id,
      capability: step.capability,
      step_order: Number.isFinite(step.step_order) ? step.step_order : index + 1,
    }
    if (step.empty_result_source) {
      compacted.empty_result_source = true
      if (String(step.empty_result_path ?? '').trim()) {
        compacted.empty_result_path = String(step.empty_result_path ?? '').trim()
      }
    }
    return compacted
  })
  const emptyResultPolicy = composition.empty_result_policy ?? null
  const emptyResultOutput = composition.empty_result_output ?? null
  return {
    ...composition,
    steps,
    input_mapping: compactCompositionInputMapping(composition.input_mapping),
    output_mapping: Object.fromEntries(
      Object.entries(composition.output_mapping ?? {})
        .map(([field, pathValue]) => [field.trim(), String(pathValue ?? '').trim()] as const)
        .filter(([field, pathValue]) => field.length > 0 && pathValue.length > 0),
    ),
    empty_result_policy: emptyResultPolicy,
    empty_result_output: emptyResultPolicy === 'return_success_no_results' ? emptyResultOutput : null,
  }
}

type CompositionInputSemanticClass =
  | 'actor_scope'
  | 'audience'
  | 'business_category'
  | 'cohort'
  | 'concrete_entity'
  | 'quantity'
  | 'text'
  | 'time'
  | 'unknown'

function inputSemanticClass(input: DeveloperCapabilityInputFormalization | undefined): CompositionInputSemanticClass {
  if (!input) return 'unknown'
  const semanticType = String(input.semantic_type ?? '').trim().toLowerCase()
  const name = String(input.input_name ?? '').trim().toLowerCase()
  const summary = String(input.summary ?? '').trim().toLowerCase()
  const combined = `${semanticType} ${name} ${summary}`
  if (input.entity_reference) return 'concrete_entity'
  if (/\b(cohort|segment|population|set)\b/.test(combined)) return 'cohort'
  if (/\b(scope|region|territory|owner|team|actor|policy)\b/.test(combined)) return 'actor_scope'
  if (/\b(time|date|quarter|month|week|year|window|period)\b/.test(combined)) return 'time'
  if (/\b(limit|count|number|quantity|max|min|size)\b/.test(combined)) return 'quantity'
  if (/\b(category|type|basis|status|stage|mode|channel|objective|theme)\b/.test(combined)) return 'business_category'
  if (/\b(audience|persona|role)\b/.test(combined)) return 'audience'
  if (
    /\b(entity|target|account|lead|opportunity|contact|customer|user|issue|ticket|repository|repo|channel|document|page|database|dataset|dashboard|chart)\b/.test(combined)
  ) {
    return 'concrete_entity'
  }
  if (String(input.input_type ?? '').trim().toLowerCase() === 'string') return 'text'
  return 'unknown'
}

function parentInputCanSatisfyRequiredChild(input: DeveloperCapabilityInputFormalization): boolean {
  if (input.required) return true
  if (String(input.default_value ?? '').trim()) return true
  const onMissing = input.resolution?.on_missing
  return onMissing === 'use_default' || onMissing === 'use_actor_scope' || onMissing === 'app_select_or_clarify'
}

function compositionInputClassesCompatible(
  parentInput: DeveloperCapabilityInputFormalization,
  childInput: DeveloperCapabilityInputFormalization,
): boolean {
  const parentClass = inputSemanticClass(parentInput)
  const childClass = inputSemanticClass(childInput)
  if (parentClass === 'unknown' || childClass === 'unknown' || parentClass === 'text' || childClass === 'text') return true
  if (parentClass === childClass) return true
  if (childClass === 'concrete_entity') return parentClass === 'concrete_entity'
  if (childClass === 'cohort') return parentClass === 'cohort'
  if (childClass === 'actor_scope') return parentClass === 'actor_scope'
  if (childClass === 'time') return parentClass === 'time'
  if (childClass === 'quantity') return parentClass === 'quantity'
  if (childClass === 'business_category') return parentClass === 'business_category'
  if (childClass === 'audience') return parentClass === 'audience'
  return true
}

export function validateDeveloperDefinitionRequiredFields(definition: DeveloperDefinitionData): DeveloperDefinitionValidationIssue[] {
  const issues: DeveloperDefinitionValidationIssue[] = []
  const isGovernedFrontingProject = definition.integration_fronting?.project_type === 'governed_service_project'

  function requireText(path: string, label: string, value: unknown): void {
    if (hasText(value)) return
    issues.push({ path, label, message: `${label} is required.` })
  }

  function requireItems(path: string, label: string, value: unknown): void {
    if (hasItems(value)) return
    issues.push({ path, label, message: `${label} must have at least one selection.` })
  }

  function normalizedText(value: unknown): string {
    return String(value ?? '').trim().toLowerCase().replace(/[_-]+/g, ' ')
  }

  function capabilityRequiresGrantPolicy(capability: DeveloperCapabilityFormalization): boolean {
    const intentType = normalizedText(capability.intent_type)
    const operationType = normalizedText(capability.operation_type)
    const sideEffectLevel = normalizedText(capability.side_effect_level)
    const producedEffects = (capability.business_effects?.produces ?? []).map(normalizedText)
    return intentType.includes('approval')
      || operationType.includes('approval')
      || sideEffectLevel.includes('approval')
      || sideEffectLevel === 'write'
      || sideEffectLevel.includes('mutation')
      || sideEffectLevel.includes('irreversible')
      || producedEffects.includes('approval.request')
      || producedEffects.includes('system.mutation')
  }

  function includesPlaceholderMarker(value: unknown): boolean {
    const text = String(value ?? '').trim().toLowerCase()
    if (!text) return false
    return PLACEHOLDER_CAPABILITY_TEXT_MARKERS.some((marker) => text.includes(marker))
  }

  function validateCompositionPath(path: string, label: string, value: unknown, declaredStepIds: Set<string>, currentStepIndex?: number, stepIndexById?: Map<string, number>): void {
    if (!hasText(value)) {
      issues.push({ path, label, message: `${label} must be a JSONPath from parent input or a previous step output.` })
      return
    }
    const text = String(value).trim()
    if (COMPOSITION_INPUT_PATH_PATTERN.test(text)) return
    const match = text.match(COMPOSITION_STEP_PATH_PATTERN)
    if (!match) {
      issues.push({ path, label, message: `${label} must use $.input.<field> or $.steps.<step>.output.<field>.` })
      return
    }
    const referencedStepId = match[1]
    if (!declaredStepIds.has(referencedStepId)) {
      issues.push({ path, label, message: `${label} references unknown composition step ${referencedStepId}.` })
      return
    }
    if (currentStepIndex !== undefined && stepIndexById) {
      const referencedIndex = stepIndexById.get(referencedStepId)
      if (referencedIndex !== undefined && referencedIndex >= currentStepIndex) {
        issues.push({ path, label, message: `${label} can only reference parent input or an earlier composition step.` })
      }
    }
  }

  function validateInputResolution(path: string, label: string, input: DeveloperCapabilityInputFormalization): void {
    const semanticType = String(input.semantic_type ?? '').trim()
    if (semanticType && !INPUT_SEMANTIC_TYPE_PATTERN.test(semanticType)) {
      issues.push({
        path: `${path}.semantic_type`,
        label: `${label} Semantic Type`,
        message: 'Input semantic type must be a safe v0.24 identifier.',
      })
    }
    const catalogRef = String(input.catalog_ref ?? '').trim()
    if (catalogRef && !INPUT_CATALOG_REF_PATTERN.test(catalogRef)) {
      issues.push({
        path: `${path}.catalog_ref`,
        label: `${label} Catalog Ref`,
        message: 'Input catalog_ref must be a safe v0.24 resolver/catalog identifier.',
      })
    }
    const resolution = input.resolution
    if (!resolution) return
    if (!INPUT_RESOLUTION_MODES.has(resolution.mode)) {
      issues.push({
        path: `${path}.resolution.mode`,
        label: `${label} Resolution Mode`,
        message: 'Input resolution.mode must be a supported v0.24 value.',
      })
    }
    for (const key of ['on_missing', 'on_ambiguous', 'on_unresolved'] as const) {
      const value = resolution[key]
      if (value && !INPUT_RESOLUTION_BEHAVIORS.has(value)) {
        issues.push({
          path: `${path}.resolution.${key}`,
          label: `${label} Resolution ${key}`,
          message: `Input resolution.${key} must be a supported v0.24 behavior.`,
        })
      }
    }
    if (resolution.mode === 'closed_values' && !(input.allowed_values ?? []).some((value) => value.trim())) {
      issues.push({
        path: `${path}.resolution.mode`,
        label: `${label} Resolution Mode`,
        message: 'closed_values resolution requires non-empty allowed values.',
      })
    }
    if (
      input.required === true
      && resolution.mode === 'actor_policy_or_explicit'
      && resolution.on_missing === 'use_actor_scope'
    ) {
      issues.push({
        path: `${path}.required`,
        label: `${label} Required Flag`,
        message: 'Inputs resolved from actor scope when missing must be optional in the public contract.',
      })
    }
    if (
      input.required === true
      && ['explicit_only', 'backend_resolved'].includes(resolution.mode)
      && resolution.on_missing === 'omit'
    ) {
      issues.push({
        path: `${path}.required`,
        label: `${label} Required Flag`,
        message: 'Inputs omitted when missing must be optional in the public contract.',
      })
    }
    if (resolution.on_missing === 'use_default' && input.default_value === undefined) {
      issues.push({
        path: `${path}.resolution.on_missing`,
        label: `${label} Missing Input Behavior`,
        message: 'on_missing=use_default requires a default value.',
      })
    }
  }

  requireText('product_alignment.governed_behavior_formalization', 'Governed Behavior Summary', definition.product_alignment?.governed_behavior_formalization)
  requireText('product_alignment.approval_posture_formalization', 'Approval Posture Summary', definition.product_alignment?.approval_posture_formalization)
  requireText('identity.system_name', 'System Name', definition.identity?.system_name)
  requireText('identity.domain_name', 'Domain', definition.identity?.domain_name)
  requireText('identity.delivery_model', 'Delivery Model', definition.identity?.delivery_model)
  requireText('identity.architecture_shape', 'Architecture Shape', definition.identity?.architecture_shape)

  for (const service of definition.service_topology_bindings ?? []) {
    const serviceId = String(service.service_id ?? '').trim()
    if (!SERVICE_ID_PATTERN.test(serviceId)) {
      issues.push({
        path: `service_topology_bindings.${service.id}.service_id`,
        label: `${service.service_name || serviceId || 'Service'} Service ID`,
        message: 'Service IDs must use lowercase letters, numbers, hyphens, or underscores, and must not contain dots.',
      })
    }
  }
  for (const serviceId of definition.generation?.selected_service_ids ?? []) {
    if (!SERVICE_ID_PATTERN.test(String(serviceId ?? '').trim())) {
      issues.push({
        path: 'generation.selected_service_ids',
        label: 'Service Boundaries Selected For Generation',
        message: `Selected service ID ${serviceId} is invalid. Use lowercase letters, numbers, hyphens, or underscores, and do not use dots.`,
      })
    }
  }

  if (!isGovernedFrontingProject) {
    for (const service of definition.service_topology_bindings ?? []) {
      const basePath = `service_topology_bindings.${service.id}`
      if ((service.source_capabilities ?? []).length > 0) {
        requireItems(`${basePath}.formalized_capability_ids`, `${service.service_name} Formalized Capabilities`, service.formalized_capability_ids)
        const confirmedCapabilities = new Set(service.formalized_capability_ids ?? [])
        const missingCapabilities = (service.source_capabilities ?? []).filter((capabilityId) => !confirmedCapabilities.has(capabilityId))
        if (missingCapabilities.length > 0) {
          issues.push({
            path: `${basePath}.formalized_capability_ids`,
            label: `${service.service_name} Formalized Capabilities`,
            message: `${service.service_name} has unassigned proposed capabilities: ${missingCapabilities.join(', ')}.`,
          })
        }
      }
    }

  }

  for (const binding of definition.service_backend_bindings ?? []) {
    const basePath = `service_backend_bindings.${binding.service_id}`
    const serviceLabel = binding.service_name || binding.service_id
    if (binding.uses_data_access_backend) {
      requireText(`${basePath}.data_access_backend_type`, `${serviceLabel} Data Backend Type`, binding.data_access_backend_type)
      requireText(`${basePath}.data_access_target_label`, `${serviceLabel} Data Target Label`, binding.data_access_target_label)
    }
    if (binding.uses_application_integration_backend) {
      requireText(`${basePath}.application_integration_backend_type`, `${serviceLabel} Integration Backend Type`, binding.application_integration_backend_type)
      if (binding.application_integration_backend_type === 'custom_adapter') {
        requireText(`${basePath}.application_integration_adapter_target`, `${serviceLabel} Backend Template`, binding.application_integration_adapter_target)
      } else if (!binding.application_integration_system_name.trim()) {
        issues.push({
          path: `${basePath}.application_integration_system_name`,
          label: `${serviceLabel} Integration System`,
          message: `${serviceLabel} must explicitly name the backend system this service integrates with.`,
        })
      }
    }
  }

  if (!isGovernedFrontingProject) {
    for (const actor of definition.actor_expectations ?? []) {
      const actorLabel = actor.actor_title || actor.actor_id
      requireText(`actor_expectations.${actor.id}.summary_formalization`, `${actorLabel} Role Description`, actor.summary_formalization)
      requireText(`actor_expectations.${actor.id}.visibility_formalization`, `${actorLabel} Visibility Expectations`, actor.visibility_formalization)
      requireText(`actor_expectations.${actor.id}.action_formalization`, `${actorLabel} Allowed Requests`, actor.action_formalization)
      requireText(`actor_expectations.${actor.id}.approval_formalization`, `${actorLabel} Approval Boundaries`, actor.approval_formalization)
    }

    for (const permission of definition.permission_intent_bindings ?? []) {
      const permissionLabel = `${permission.actor_id || 'Actor'} ${permission.business_area_label || permission.business_area || 'Permission'}`
      const protectedCapabilityIds = permission.target_capability_ids?.length
        ? permission.target_capability_ids
        : definition.capability_formalizations
            .filter((capability) => permission.target_service_ids.includes(capability.service_id))
            .map((capability) => capability.capability_id)
      requireText(`permission_intent_bindings.${permission.id}.business_area`, `${permissionLabel} Business Area`, permission.business_area_label || permission.business_area)
      requireText(`permission_intent_bindings.${permission.id}.access_posture`, `${permissionLabel} Role Access`, permission.access_posture)
      requireText(`permission_intent_bindings.${permission.id}.governed_outcome`, `${permissionLabel} Business Rule`, permission.governed_outcome)
      requireItems(`permission_intent_bindings.${permission.id}.target_service_ids`, `${permissionLabel} Target Services`, permission.target_service_ids)
      requireItems(`permission_intent_bindings.${permission.id}.target_capability_ids`, `${permissionLabel} Protected Capabilities`, protectedCapabilityIds)
      requireText(`permission_intent_bindings.${permission.id}.formalization_strategy`, `${permissionLabel} Formalization Strategy`, permission.formalization_strategy)
    }

    requireText('data_domain.domain_name', 'Domain Name', definition.data_domain?.domain_name)
    for (const concept of definition.domain_concept_bindings ?? []) {
      requireText(`domain_concept_bindings.${concept.id}.technical_representation`, `${concept.concept_name || concept.concept_id} Technical Representation`, concept.technical_representation)
    }
    for (const objectDef of definition.application_object_model ?? []) {
      const objectPath = objectDef.object_id || objectDef.name || 'application_object'
      requireText(`application_object_model.${objectPath}.object_id`, `${objectDef.name || objectDef.object_id || 'Application Object'} Object ID`, objectDef.object_id)
      requireText(`application_object_model.${objectPath}.name`, `${objectDef.object_id || objectDef.name || 'Application Object'} Name`, objectDef.name)
    }
  }

  const capabilityByCapabilityId = new Map(
    (definition.capability_formalizations ?? [])
      .filter((capability) => capability.capability_id)
      .map((capability) => [capability.capability_id, capability] as const),
  )
  for (const capability of definition.capability_formalizations ?? []) {
    const capabilityLabel = capability.title || capability.capability_id || capability.id
    requireText(`capability_formalizations.${capability.id}.capability_id`, `${capabilityLabel} Capability ID`, capability.capability_id)
    requireText(`capability_formalizations.${capability.id}.title`, `${capabilityLabel} Title`, capability.title)
    requireText(`capability_formalizations.${capability.id}.intent_type`, `${capabilityLabel} Intent Type`, capability.intent_type)
    requireText(`capability_formalizations.${capability.id}.operation_type`, `${capabilityLabel} Operation Type`, capability.operation_type)
    requireText(`capability_formalizations.${capability.id}.side_effect_level`, `${capabilityLabel} Side Effect Level`, capability.side_effect_level)
    requireText(`capability_formalizations.${capability.id}.summary`, `${capabilityLabel} Summary`, capability.summary)
    requireText(`capability_formalizations.${capability.id}.backend_operation`, `${capabilityLabel} Backend Operation`, capability.backend_operation)
    requireText(`capability_formalizations.${capability.id}.output_shape`, `${capabilityLabel} Output Shape`, capability.output_shape)
    requireItems(
      `capability_formalizations.${capability.id}.business_effects.produces`,
      `${capabilityLabel} Produced Effects`,
      capability.business_effects?.produces?.filter((effect) => effect.trim()),
    )
    requireItems(
      `capability_formalizations.${capability.id}.business_effects.does_not_produce`,
      `${capabilityLabel} Forbidden Effects`,
      capability.business_effects?.does_not_produce?.filter((effect) => effect.trim()),
    )
    for (const [field, values] of Object.entries({
      produces: capability.business_effects?.produces ?? [],
      does_not_produce: capability.business_effects?.does_not_produce ?? [],
    })) {
      for (const effect of values) {
        const effectId = effect.trim()
        if (!effectId || isKnownEffect(effectId)) continue
        issues.push({
          path: `capability_formalizations.${capability.id}.business_effects.${field}`,
          label: `${capabilityLabel} Business Effects`,
          message: `${capabilityLabel} declares unknown effect "${effectId}". Use canonical effect IDs: ${KNOWN_EFFECT_IDS.join(', ')}.`,
        })
      }
    }
    if (capabilityRequiresGrantPolicy(capability) && !capability.grant_policy) {
      issues.push({
        path: `capability_formalizations.${capability.id}.grant_policy`,
        label: `${capabilityLabel} Approval Grant Policy`,
        message: `${capabilityLabel} is approval/write-capable and must define an approval grant policy before saving.`,
      })
    }
    for (const [field, value] of Object.entries({
      summary: capability.summary,
      backend_operation: capability.backend_operation,
      output_shape: capability.output_shape,
    })) {
      if (!includesPlaceholderMarker(value)) continue
      issues.push({
        path: `capability_formalizations.${capability.id}.${field}`,
        label: `${capabilityLabel} ${humanize(field)}`,
        message: `${capabilityLabel} contains placeholder contract text in ${field}. Regenerate or fill in concrete source-derived contract detail before saving.`,
      })
    }
    if (!isGovernedFrontingProject && capability.source_kind === 'contract_native' && !hasItems(capability.inputs)) {
      issues.push({
        path: `capability_formalizations.${capability.id}.inputs`,
        label: `${capabilityLabel} Inputs`,
        message: `${capabilityLabel} is a source-declared capability and must define concrete input contract details before saving.`,
      })
    }
    for (const input of capability.inputs ?? []) {
      const inputLabel = `${capabilityLabel} ${input.input_name || 'Input'}`
      requireText(`capability_formalizations.${capability.id}.inputs.${input.input_name}.input_name`, `${inputLabel} Name`, input.input_name)
      requireText(`capability_formalizations.${capability.id}.inputs.${input.input_name}.input_type`, `${inputLabel} Type`, input.input_type)
      requireText(`capability_formalizations.${capability.id}.inputs.${input.input_name}.summary`, `${inputLabel} Summary`, input.summary)
      validateInputResolution(
        `capability_formalizations.${capability.id}.inputs.${input.input_name}`,
        `${capabilityLabel} ${input.input_name}`,
        input,
      )
    }
    const kind = normalizedCapabilityKind(capability)
    if (kind === 'composed') {
      requireItems(`capability_formalizations.${capability.id}.composition.steps`, `${capabilityLabel} Composition Steps`, capability.composition?.steps)
      if (!capability.composition) {
        issues.push({
          path: `capability_formalizations.${capability.id}.composition`,
          label: `${capabilityLabel} Composition`,
          message: 'Composed capabilities must define contract-level composition metadata.',
        })
      } else {
        const composition = compactDeveloperComposition(capability.composition) ?? capability.composition
        const compositionSteps = Array.isArray(composition.steps) ? composition.steps : []
        if (composition.authority_boundary !== 'same_service') {
          issues.push({
            path: `capability_formalizations.${capability.id}.composition.authority_boundary`,
            label: `${capabilityLabel} Composition Authority Boundary`,
            message: 'Studio currently supports same-service composition only.',
          })
        }
        const stepIds = new Set<string>()
        const stepIndexById = new Map<string, number>()
        const stepById = new Map<string, DeveloperCompositionStep>()
        let emptyResultSources = 0
        for (const [stepIndex, step] of compositionSteps.entries()) {
          if (!hasText(step.id)) {
            issues.push({
              path: `capability_formalizations.${capability.id}.composition.steps.${stepIndex}.id`,
              label: `${capabilityLabel} Composition Step`,
              message: 'Composition step ID is required.',
            })
          } else if (stepIds.has(step.id)) {
            issues.push({
              path: `capability_formalizations.${capability.id}.composition.steps.${stepIndex}.id`,
              label: `${capabilityLabel} Composition Step`,
              message: `Composition step ID ${step.id} is duplicated.`,
            })
          } else {
            stepIds.add(step.id)
            stepIndexById.set(step.id, stepIndex)
            stepById.set(step.id, step)
          }
          if (step.empty_result_source) emptyResultSources += 1
          const child = capabilityByCapabilityId.get(step.capability)
          if (!child) {
            issues.push({
              path: `capability_formalizations.${capability.id}.composition.steps.${stepIndex}.capability`,
              label: `${capabilityLabel} Composition Step`,
              message: `Composition step capability ${step.capability} is not defined.`,
            })
            continue
          }
          if (child.service_id !== capability.service_id) {
            issues.push({
              path: `capability_formalizations.${capability.id}.composition.steps.${stepIndex}.capability`,
              label: `${capabilityLabel} Composition Step`,
              message: `Same-service composition cannot call ${step.capability} from ${child.service_id}.`,
            })
          }
          if (normalizedCapabilityKind(child) !== 'atomic') {
            issues.push({
              path: `capability_formalizations.${capability.id}.composition.steps.${stepIndex}.capability`,
              label: `${capabilityLabel} Composition Step`,
              message: `Contract-level composition steps must target atomic capabilities.`,
            })
          }
          for (const input of child.inputs ?? []) {
            if (!input.required) continue
            const mappedValue = composition.input_mapping?.[step.id]?.[input.input_name]
            if (!hasText(mappedValue)) {
              issues.push({
                path: `capability_formalizations.${capability.id}.composition.input_mapping.${step.id}.${input.input_name}`,
                label: `${capabilityLabel} ${step.id} ${input.input_name} Mapping`,
                message: `Required child input ${input.input_name} must be mapped from parent input or an earlier step output.`,
              })
            }
          }
        }
        if (emptyResultSources > 1) {
          issues.push({
            path: `capability_formalizations.${capability.id}.composition.steps`,
            label: `${capabilityLabel} Empty Result Source`,
            message: 'A composed capability can declare at most one empty-result source step.',
          })
        }
        if (emptyResultSources === 1 && !composition.empty_result_policy) {
          issues.push({
            path: `capability_formalizations.${capability.id}.composition.empty_result_policy`,
            label: `${capabilityLabel} Empty Result Behavior`,
            message: 'Choose how the composed capability behaves when the empty-result source has no results.',
          })
        }
        if (composition.empty_result_policy === 'return_success_no_results' && emptyResultSources !== 1) {
          issues.push({
            path: `capability_formalizations.${capability.id}.composition.steps`,
            label: `${capabilityLabel} Empty Result Source`,
            message: 'return_success_no_results requires exactly one composition step marked as the empty-result source.',
          })
        }
        if (composition.empty_result_policy === 'return_success_no_results' && !composition.empty_result_output) {
          issues.push({
            path: `capability_formalizations.${capability.id}.composition.empty_result_output`,
            label: `${capabilityLabel} No-Results Response`,
            message: 'Define the response fields returned for a successful no-results outcome.',
          })
        }
        for (const [stepId, mapping] of Object.entries(composition.input_mapping ?? {})) {
          const currentStepIndex = stepIndexById.get(stepId)
          if (!stepIds.has(stepId) || currentStepIndex === undefined) {
            issues.push({
              path: `capability_formalizations.${capability.id}.composition.input_mapping.${stepId}`,
              label: `${capabilityLabel} Input Mapping`,
              message: `Input mapping references undeclared step ${stepId}.`,
            })
            continue
          }
          const childCapabilityId = stepById.get(stepId)?.capability
          const child = childCapabilityId ? capabilityByCapabilityId.get(childCapabilityId) : undefined
          const childInputByName = new Map((child?.inputs ?? []).map((input) => [input.input_name, input] as const))
          const parentInputByName = new Map((capability.inputs ?? []).map((input) => [input.input_name, input] as const))
          for (const [inputName, pathValue] of Object.entries(mapping ?? {})) {
            const childInput = childInputByName.get(inputName)
            if (!childInput) {
              issues.push({
                path: `capability_formalizations.${capability.id}.composition.input_mapping.${stepId}.${inputName}`,
                label: `${capabilityLabel} ${stepId} ${inputName} Mapping`,
                message: `Input mapping targets ${inputName}, but ${stepId} child capability does not declare that input.`,
              })
            }
            validateCompositionPath(
              `capability_formalizations.${capability.id}.composition.input_mapping.${stepId}.${inputName}`,
              `${capabilityLabel} ${stepId} ${inputName} Mapping`,
              pathValue,
              stepIds,
              currentStepIndex,
              stepIndexById,
            )
            const parentInputName = compositionParentInputName(pathValue)
            if (!parentInputName) continue
            const parentInput = parentInputByName.get(parentInputName)
            if (!parentInput) {
              issues.push({
                path: `capability_formalizations.${capability.id}.composition.input_mapping.${stepId}.${inputName}`,
                label: `${capabilityLabel} ${stepId} ${inputName} Mapping`,
                message: `Input mapping references parent input ${parentInputName}, but ${capabilityLabel} does not declare that input.`,
              })
              continue
            }
            if (childInput?.required && !parentInputCanSatisfyRequiredChild(parentInput)) {
              issues.push({
                path: `capability_formalizations.${capability.id}.composition.input_mapping.${stepId}.${inputName}`,
                label: `${capabilityLabel} ${stepId} ${inputName} Mapping`,
                message: `Required child input ${inputName} cannot be satisfied by optional parent input ${parentInputName}. Map it from a required/defaulted parent input or a prior provider-owned composition step output.`,
              })
            }
            if (childInput && !compositionInputClassesCompatible(parentInput, childInput)) {
              issues.push({
                path: `capability_formalizations.${capability.id}.composition.input_mapping.${stepId}.${inputName}`,
                label: `${capabilityLabel} ${stepId} ${inputName} Mapping`,
                message: `Input mapping cannot feed ${inputSemanticClass(parentInput)} parent input ${parentInputName} into ${inputSemanticClass(childInput)} child input ${inputName}. Add a provider-owned composition step and map from its output if this value is derived.`,
              })
            }
          }
        }
        if (Object.keys(composition.output_mapping ?? {}).length === 0) {
          issues.push({
            path: `capability_formalizations.${capability.id}.composition.output_mapping`,
            label: `${capabilityLabel} Output Mapping`,
            message: 'Composed capabilities must define at least one output mapping.',
          })
        }
        for (const [field, pathValue] of Object.entries(composition.output_mapping ?? {})) {
          if (!hasText(field)) {
            issues.push({
              path: `capability_formalizations.${capability.id}.composition.output_mapping`,
              label: `${capabilityLabel} Output Mapping`,
              message: 'Output mapping field names cannot be blank.',
            })
          }
          validateCompositionPath(
            `capability_formalizations.${capability.id}.composition.output_mapping.${field}`,
            `${capabilityLabel} Output Mapping ${field}`,
            pathValue,
            stepIds,
          )
          const referencedStepId = compositionStepOutputId(pathValue)
          if (referencedStepId && !stepIds.has(referencedStepId)) {
            issues.push({
              path: `capability_formalizations.${capability.id}.composition.output_mapping.${field}`,
              label: `${capabilityLabel} Output Mapping ${field}`,
              message: `Output mapping references undeclared step ${referencedStepId}.`,
            })
          }
        }
        for (const [field, value] of Object.entries(composition.failure_policy ?? {})) {
          if (value !== 'propagate' && value !== 'fail_parent') {
            issues.push({
              path: `capability_formalizations.${capability.id}.composition.failure_policy.${field}`,
              label: `${capabilityLabel} Failure Handling`,
              message: 'Failure handling must pass through to caller or fail the composed capability.',
            })
          }
        }
      }
    } else if (capability.composition) {
      issues.push({
        path: `capability_formalizations.${capability.id}.composition`,
        label: `${capabilityLabel} Composition`,
        message: 'Atomic capabilities cannot carry composition metadata.',
      })
    }
    if (capability.grant_policy) {
      const policy = capability.grant_policy
      const allowedGrantTypes = Array.isArray(policy.allowed_grant_types) ? policy.allowed_grant_types : []
      const defaultGrantType = typeof policy.default_grant_type === 'string' ? policy.default_grant_type : ''
      if (!allowedGrantTypes.length) {
        issues.push({
          path: `capability_formalizations.${capability.id}.grant_policy.allowed_grant_types`,
          label: `${capabilityLabel} Approval Grant Types`,
          message: 'Approval grant policy must allow at least one grant type.',
        })
      }
      if (!allowedGrantTypes.some((grantType) => grantType === defaultGrantType)) {
        issues.push({
          path: `capability_formalizations.${capability.id}.grant_policy.default_grant_type`,
          label: `${capabilityLabel} Default Approval Grant`,
          message: 'Default approval grant type must be one of the allowed grant types.',
        })
      }
      if (typeof policy.expires_in_seconds !== 'number' || policy.expires_in_seconds <= 0) {
        issues.push({
          path: `capability_formalizations.${capability.id}.grant_policy.expires_in_seconds`,
          label: `${capabilityLabel} Approval Grant Expiry`,
          message: 'Approval grants must expire after a positive number of seconds.',
        })
      }
      if (typeof policy.max_uses !== 'number' || policy.max_uses <= 0) {
        issues.push({
          path: `capability_formalizations.${capability.id}.grant_policy.max_uses`,
          label: `${capabilityLabel} Approval Grant Uses`,
          message: 'Approval grants must allow at least one use.',
        })
      }
    }
  }

  if (!isGovernedFrontingProject) {
    for (const scenario of definition.scenario_formalizations ?? []) {
      const scenarioLabel = scenario.scenario_title || scenario.scenario_id
      requireItems(`scenario_formalizations.${scenario.scenario_id}.participating_service_ids`, `${scenarioLabel} Participating Services`, scenario.participating_service_ids)
      requireItems(`scenario_formalizations.${scenario.scenario_id}.required_behaviors`, `${scenarioLabel} Required Behaviors`, scenario.required_behaviors)
      requireItems(`scenario_formalizations.${scenario.scenario_id}.required_anip_support`, `${scenarioLabel} Required ANIP Support`, scenario.required_anip_support)
      for (const [index, step] of (scenario.orchestration_steps ?? []).entries()) {
        const stepLabel = `${scenarioLabel} Step ${index + 1}`
        requireText(`scenario_formalizations.${scenario.scenario_id}.orchestration_steps.${step.id}.service_id`, `${stepLabel} Service`, step.service_id)
        requireText(`scenario_formalizations.${scenario.scenario_id}.orchestration_steps.${step.id}.step_kind`, `${stepLabel} Step Kind`, step.step_kind)
        if (step.step_kind === 'capability_execution') {
          requireText(`scenario_formalizations.${scenario.scenario_id}.orchestration_steps.${step.id}.capability_id`, `${stepLabel} Capability ID`, step.capability_id)
        }
        requireText(`scenario_formalizations.${scenario.scenario_id}.orchestration_steps.${step.id}.outcome_type`, `${stepLabel} Outcome Type`, step.outcome_type)
        requireText(`scenario_formalizations.${scenario.scenario_id}.orchestration_steps.${step.id}.stop_condition`, `${stepLabel} Stop Condition`, step.stop_condition)
      }
    }

    for (const rule of definition.composition_rules ?? []) {
      requireItems(`composition_rules.${rule.id}.affected_scenario_ids`, `${rule.rule} Affected Scenarios`, rule.affected_scenario_ids)
      requireText(`composition_rules.${rule.id}.formalization_strategy`, `${rule.rule} Formalization Strategy`, rule.formalization_strategy)
    }
  }

  for (const binding of definition.verification?.supported_question_family_bindings ?? []) {
    requireItems(`verification.supported_question_family_bindings.${binding.id}.target_service_ids`, `${binding.question_family} Target Services`, binding.target_service_ids)
    requireText(`verification.supported_question_family_bindings.${binding.id}.verification_strategy`, `${binding.question_family} Verification Strategy`, binding.verification_strategy)
  }
  for (const binding of definition.verification?.business_goal_bindings ?? []) {
    requireItems(`verification.business_goal_bindings.${binding.id}.target_service_ids`, `${binding.business_goal} Target Services`, binding.target_service_ids)
    requireText(`verification.business_goal_bindings.${binding.id}.verification_strategy`, `${binding.business_goal} Verification Strategy`, binding.verification_strategy)
  }
  for (const guard of definition.verification?.non_goal_guards ?? []) {
    requireText(`verification.non_goal_guards.${guard.id}.guard_strategy`, `${guard.non_goal} Guard Strategy`, guard.guard_strategy)
    requireText(`verification.non_goal_guards.${guard.id}.evidence_signal`, `${guard.non_goal} Evidence Signal`, guard.evidence_signal)
  }
  for (const check of definition.verification?.success_criteria_checks ?? []) {
    requireText(`verification.success_criteria_checks.${check.id}.technical_verification_strategy`, `${check.success_criterion} Technical Verification Strategy`, check.verification_strategy)
  }

  requireText('generation.scalability_profile', 'Scalability posture', definition.generation?.scalability_profile)
  requireText('generation.codegen_adapter', 'Primary code generation adapter', definition.generation?.codegen_adapter)
  requireText('generation.layout_strategy', 'Repository / package layout', definition.generation?.layout_strategy)
  requireText('naming.namespace', 'Package namespace', definition.naming?.namespace)
  requireText('naming.package_prefix', 'Package prefix', definition.naming?.package_prefix)
  requireText('naming.service_name_prefix', 'Service name prefix', definition.naming?.service_name_prefix)
  requireItems('generation.protocols', 'Protocols', definition.generation?.protocols)
  requireItems('generation.selected_service_ids', 'Service Boundaries Selected For Generation', definition.generation?.selected_service_ids)

  return issues
}

export const DEVELOPER_DEFINITION_SECTIONS = [
  {
    id: 'service_identity_topology',
    label: 'Service Identity & Topology',
    description: 'How the system is decomposed into services and how those services are named and bounded.',
    owners: ['Service Design', 'Application Integration'],
  },
  {
    id: 'capability_contracts',
    label: 'Capability Contracts',
    description: 'The ANIP-facing capabilities, inputs, outputs, and bounded actions the implementation must expose.',
    owners: ['Application Integration'],
  },
  {
    id: 'authority_and_approval',
    label: 'Authority & Approval',
    description: 'How restrictions, denials, approvals, and clarification posture become formal service behavior.',
    owners: ['Governed Data Access', 'Application Integration'],
  },
  {
    id: 'data_contracts',
    label: 'Data Contracts',
    description: 'The governed data surface, metrics, dimensions, filters, outcomes, and result-shaping rules.',
    owners: ['Governed Data Access'],
  },
  {
    id: 'scenario_context',
    label: 'Scenario Coverage Intent',
    description: 'Per-scenario actor context, business/time scope, service participation, and operational posture used as readiness and verification evidence.',
    owners: ['Application Integration', 'Governed Data Access'],
  },
  {
    id: 'execution_semantics',
    label: 'Execution Semantics',
    description: 'Per-scenario required behaviors, protocol-visible ANIP support, and implementation notes that generation and verification should preserve.',
    owners: ['Application Integration', 'Governed Data Access'],
  },
  {
    id: 'backend_bindings',
    label: 'Runtime Backends',
    description: 'How the ANIP surface maps to real backend systems, adapters, operations, and implementation targets.',
    owners: ['Governed Data Access', 'Application Integration'],
  },
  {
    id: 'audit_and_lineage',
    label: 'Audit & Lineage',
    description: 'What evidence, lineage, and traceability the generated implementation must preserve.',
    owners: ['Governed Data Access', 'Application Integration'],
  },
  {
    id: 'generation_and_extensions',
    label: 'Generation & Extension Points',
    description: 'Which technical choices directly affect generated scaffolds and where manual extension points remain.',
    owners: ['Governed Data Access', 'Application Integration'],
  },
] as const

export type DeveloperDefinitionSectionId = typeof DEVELOPER_DEFINITION_SECTIONS[number]['id']
export interface AssistantSeedSummary {
  count: number
  clearable: boolean
  details?: Array<{ label: string; count: number; artifact_type: string }>
}

function incrementAssistantSeedDetail(summary: AssistantSeedSummary, artifactType: string, label: string, amount: number) {
  if (amount <= 0) return
  summary.count += amount
  if (!summary.details) summary.details = []
  const existing = summary.details.find((entry) => entry.label === label && entry.artifact_type === artifactType)
  if (existing) {
    existing.count += amount
    return
  }
  summary.details.push({ label, count: amount, artifact_type: artifactType })
}

export type CompiledContractAlignmentStatus = 'aligned' | 'stale' | 'unknown'

export const DATA_ACCESS_DEFINITION_SECTIONS: DeveloperDefinitionSectionId[] = [
  'authority_and_approval',
  'data_contracts',
  'scenario_context',
  'execution_semantics',
  'backend_bindings',
  'audit_and_lineage',
  'generation_and_extensions',
]

export const APPLICATION_INTEGRATION_DEFINITION_SECTIONS: DeveloperDefinitionSectionId[] = [
  'service_identity_topology',
  'capability_contracts',
  'authority_and_approval',
  'scenario_context',
  'execution_semantics',
  'backend_bindings',
  'audit_and_lineage',
  'generation_and_extensions',
]

export function developerDefinitionSectionLabel(id: string): string {
  return DEVELOPER_DEFINITION_SECTIONS.find((section) => section.id === id)?.label ?? id
}

export function developerDefinitionSectionDescription(id: string): string {
  return DEVELOPER_DEFINITION_SECTIONS.find((section) => section.id === id)?.description ?? ''
}

export function stableStringify(value: unknown): string {
  return JSON.stringify(sortJsonValue(value))
}

function sortJsonValue(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => sortJsonValue(item))
  }
  if (value && typeof value === 'object') {
    return Object.keys(value as Record<string, unknown>)
      .sort()
      .reduce<Record<string, unknown>>((acc, key) => {
        const nextValue = (value as Record<string, unknown>)[key]
        if (nextValue !== undefined) {
          acc[key] = sortJsonValue(nextValue)
        }
        return acc
      }, {})
  }
  return value
}

function humanize(value: string): string {
  return value
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

function textValue(value: unknown): string {
  return String(value ?? '').trim()
}

function textOrFallback(value: unknown, fallback: unknown): string {
  const current = textValue(value)
  if (current) return current
  return textValue(fallback)
}

function normalizedStringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.map((item) => String(item).trim()).filter(Boolean)
    : []
}

function normalizedStringSetKey(value: unknown): string {
  return JSON.stringify([...new Set(normalizedStringArray(value))].sort())
}

function canonicalOperationIdentifier(value: unknown, fallbackPrefix: string): string {
  const normalized = String(value ?? '')
    .trim()
    .replace(/[^A-Za-z0-9_.:-]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 120)
  const candidate = normalized || fallbackPrefix
  return /^[A-Za-z_]/.test(candidate) ? candidate : `${fallbackPrefix}_${candidate}`.slice(0, 128)
}

function normalizeIntegrationFrontingBackendBindings(data: Record<string, unknown>): DeveloperIntegrationFrontingBackendBinding[] {
  const explicitBindings = Array.isArray(data.backend_bindings) ? data.backend_bindings : []
  const bindings: DeveloperIntegrationFrontingBackendBinding[] = explicitBindings
    .map((binding) => {
      const item = typeof binding === 'object' && binding ? binding as Record<string, unknown> : {}
      const backendKind: DeveloperIntegrationFrontingBackendBinding['backend_kind'] = item.backend_kind === 'mcp' || item.backend_kind === 'database' || item.backend_kind === 'hybrid' ? item.backend_kind : 'native_api'
      const backendInputMode: DeveloperIntegrationFrontingBackendBinding['backend_input_mode'] =
        item.backend_input_mode === 'explicit' || item.backend_input_mode === 'hybrid' ? item.backend_input_mode : 'implicit'
      const backendStatus: DeveloperIntegrationFrontingBackendBinding['status'] =
        item.status === 'ready' || item.status === 'stale' || item.status === 'missing' ? item.status : undefined
      const rawOperationRefs = normalizedStringArray(item.raw_operation_refs)
      const connectionRef = String(item.connection_ref ?? '').trim()
      return {
        backend_kind: backendKind,
        connection_ref: connectionRef ? canonicalOperationIdentifier(connectionRef, 'conn') : '',
        raw_operation_refs: rawOperationRefs,
        backend_input_mode: backendInputMode,
        derived_required_backend_inputs: normalizedStringArray(item.derived_required_backend_inputs),
        derived_optional_backend_inputs: normalizedStringArray(item.derived_optional_backend_inputs),
        explicit_required_backend_inputs: normalizedStringArray(item.explicit_required_backend_inputs),
        explicit_optional_backend_inputs: normalizedStringArray(item.explicit_optional_backend_inputs),
        matched_discovery_record_ids: normalizedStringArray(item.matched_discovery_record_ids),
        status: backendStatus,
        status_detail: textValue(item.status_detail) || undefined,
      }
    })
    .filter((binding) => binding.connection_ref && binding.raw_operation_refs.length > 0)

  if (bindings.length > 0) return bindings

  const legacyRawOperationRefs = Array.isArray(data.raw_operation_refs)
    ? data.raw_operation_refs.map((operation) => String(operation).trim()).filter(Boolean)
    : []
  const legacyConnectionRef = String(data.connection_ref ?? '').trim()
  if (!legacyConnectionRef || legacyRawOperationRefs.length === 0) return []
  const legacyBackendKind: DeveloperIntegrationFrontingBackendBinding['backend_kind'] = data.backend_kind === 'mcp' || data.backend_kind === 'database' || data.backend_kind === 'hybrid' ? data.backend_kind : 'native_api'
  const legacyBackendInputMode: DeveloperIntegrationFrontingBackendBinding['backend_input_mode'] =
    data.backend_input_mode === 'explicit' || data.backend_input_mode === 'hybrid' ? data.backend_input_mode : 'implicit'
  return [{
    backend_kind: legacyBackendKind,
    connection_ref: legacyConnectionRef ? canonicalOperationIdentifier(legacyConnectionRef, 'conn') : '',
    raw_operation_refs: legacyRawOperationRefs,
    backend_input_mode: legacyBackendInputMode,
    derived_required_backend_inputs: normalizedStringArray(data.derived_required_backend_inputs),
    derived_optional_backend_inputs: normalizedStringArray(data.derived_optional_backend_inputs),
    explicit_required_backend_inputs: normalizedStringArray(data.explicit_required_backend_inputs),
    explicit_optional_backend_inputs: normalizedStringArray(data.explicit_optional_backend_inputs),
  }]
}

export function resolveIntegrationFrontingBackendBindingHealth(
  binding: DeveloperIntegrationFrontingBackendBinding,
  discoveryRecords: IntegrationDiscoveryRecord[],
): {
  status: 'ready' | 'stale' | 'missing'
  detail: string
  derived_required_backend_inputs: string[]
  derived_optional_backend_inputs: string[]
  matched_discovery_record_ids: string[]
} {
  const rawOperationRefs = normalizedStringArray(binding.raw_operation_refs)
  const connectionRef = textValue(binding.connection_ref)
  const savedMatchedIds = normalizedStringArray(binding.matched_discovery_record_ids)
  if (!connectionRef || rawOperationRefs.length === 0) {
    return {
      status: 'missing',
      detail: 'Backend binding is incomplete. Add a connection ref and at least one raw operation.',
      derived_required_backend_inputs: [],
      derived_optional_backend_inputs: [],
      matched_discovery_record_ids: [],
    }
  }

  const savedIdMatches = savedMatchedIds.length > 0
    ? discoveryRecords.filter((record) => savedMatchedIds.includes(record.id))
    : []
  const exactMatches = discoveryRecords.filter((record) =>
    record.backend_kind === binding.backend_kind
    && rawOperationRefs.includes(record.operation_id)
    && (!record.connection_id || record.connection_id === connectionRef),
  )
  const matches = savedMatchedIds.length > 0 && savedIdMatches.length === savedMatchedIds.length
    ? savedIdMatches
    : exactMatches.length > 0
    ? exactMatches
    : discoveryRecords.filter((record) =>
        record.backend_kind === binding.backend_kind
        && rawOperationRefs.includes(record.operation_id),
      )

  if (matches.length === 0) {
    return {
      status: 'missing',
      detail: `No discovery metadata matches ${binding.backend_kind}:${connectionRef}. Refresh or re-enter backend metadata.`,
      derived_required_backend_inputs: [],
      derived_optional_backend_inputs: [],
      matched_discovery_record_ids: [],
    }
  }

  const required = Array.from(new Set(matches.flatMap((record) => normalizedStringArray(record.input_schema_summary.required))))
  const optional = Array.from(new Set(matches.flatMap((record) => normalizedStringArray(record.input_schema_summary.optional))))
    .filter((item) => !required.includes(item))
  const matchedIds = matches.map((record) => record.id)
  const savedRequired = normalizedStringArray(binding.derived_required_backend_inputs)
  const savedOptional = normalizedStringArray(binding.derived_optional_backend_inputs)
  const requiredChanged = normalizedStringSetKey(required) !== normalizedStringSetKey(savedRequired)
  const optionalChanged = normalizedStringSetKey(optional) !== normalizedStringSetKey(savedOptional)
  const matchedChanged = savedMatchedIds.length > 0 && normalizedStringSetKey(matchedIds) !== normalizedStringSetKey(savedMatchedIds)

  if (requiredChanged || optionalChanged || matchedChanged) {
    return {
      status: 'stale',
      detail: 'Discovery metadata changed for this backend binding. Review derived backend inputs and save the mapping again.',
      derived_required_backend_inputs: required,
      derived_optional_backend_inputs: optional,
      matched_discovery_record_ids: matchedIds,
    }
  }

  return {
    status: 'ready',
    detail: 'Backend binding matches current discovery metadata.',
    derived_required_backend_inputs: required,
    derived_optional_backend_inputs: optional,
    matched_discovery_record_ids: matchedIds,
  }
}

export function resolveIntegrationFrontingBackendBindingsHealth(
  bindings: DeveloperIntegrationFrontingBackendBinding[],
  discoveryRecords: IntegrationDiscoveryRecord[],
): {
  status: 'ready' | 'stale' | 'missing'
  binding_statuses: Array<ReturnType<typeof resolveIntegrationFrontingBackendBindingHealth>>
} {
  const bindingStatuses = bindings.map((binding) =>
    resolveIntegrationFrontingBackendBindingHealth(binding, discoveryRecords),
  )
  if (bindingStatuses.some((status) => status.status === 'ready')) {
    return { status: 'ready', binding_statuses: bindingStatuses }
  }
  if (bindingStatuses.some((status) => status.status === 'stale')) {
    return { status: 'stale', binding_statuses: bindingStatuses }
  }
  return { status: 'missing', binding_statuses: bindingStatuses }
}

function textOrGuidanceOrFallback(value: unknown, guidance: string, fallback: unknown): string {
  return textOrFallback(value, guidance || fallback)
}

export function findDeveloperDefinitionArtifact(
  pmArtifacts: ArtifactRecord[] | null | undefined,
): ArtifactRecord | null {
  return (
    (pmArtifacts ?? []).find((artifact) => artifact.data?.artifact_type === DEVELOPER_DEFINITION_ARTIFACT_TYPE)
    ?? null
  )
}

export function findDeveloperDefinitionRevisionArtifacts(
  pmArtifacts: ArtifactRecord[] | null | undefined,
): ArtifactRecord[] {
  return (pmArtifacts ?? []).filter((artifact) => artifact.data?.artifact_type === DEVELOPER_DEFINITION_REVISION_ARTIFACT_TYPE)
}

export function findLatestDeveloperDefinitionRevisionArtifact(
  pmArtifacts: ArtifactRecord[] | null | undefined,
): ArtifactRecord | null {
  const artifacts = [...findDeveloperDefinitionRevisionArtifacts(pmArtifacts)]
  artifacts.sort((a, b) => {
    const aRevision = Number((a.data as { saved_revision?: { revision_number?: number } } | undefined)?.saved_revision?.revision_number ?? 0)
    const bRevision = Number((b.data as { saved_revision?: { revision_number?: number } } | undefined)?.saved_revision?.revision_number ?? 0)
    if (aRevision !== bRevision) return bRevision - aRevision
    return new Date(b.updated_at || b.created_at).getTime() - new Date(a.updated_at || a.created_at).getTime()
  })
  return artifacts[0] ?? null
}

export function findDeveloperGenerationRunArtifacts(
  pmArtifacts: ArtifactRecord[] | null | undefined,
): ArtifactRecord[] {
  return (pmArtifacts ?? []).filter((artifact) => artifact.data?.artifact_type === DEVELOPER_GENERATION_RUN_ARTIFACT_TYPE)
}

function hasSavedSectionClarification(
  pmArtifacts: ArtifactRecord[],
  mode: 'pm' | 'dev',
  sectionKey: string,
): boolean {
  return pmArtifacts.some((artifact) => {
    const data = artifact.data ?? {}
    if (data.artifact_type !== ASSISTANT_SECTION_CLARIFICATIONS_ARTIFACT_TYPE) return false
    if (String(data.mode ?? '').trim() !== mode) return false
    if (String(data.section_key ?? '').trim() !== sectionKey) return false
    const payload = Array.isArray(data.accepted_payload) ? data.accepted_payload : []
    return payload.some((item) =>
      item && typeof item === 'object' && String((item as Record<string, unknown>).answer ?? '').trim().length > 0,
    )
  })
}

export function findLatestDeveloperGenerationRunArtifact(
  pmArtifacts: ArtifactRecord[] | null | undefined,
): ArtifactRecord | null {
  const artifacts = [...findDeveloperGenerationRunArtifacts(pmArtifacts)]
  artifacts.sort((a, b) => new Date(b.updated_at || b.created_at).getTime() - new Date(a.updated_at || a.created_at).getTime())
  return artifacts[0] ?? null
}

export function findIntegrationFrontingMappingArtifacts(
  pmArtifacts: ArtifactRecord[] | null | undefined,
): ArtifactRecord[] {
  return (pmArtifacts ?? []).filter((artifact) => artifact.data?.artifact_type === INTEGRATION_FRONTING_MAPPING_ARTIFACT_TYPE)
}

function normalizeDeveloperBusinessEffects(value: unknown): DeveloperBusinessEffects | undefined {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return undefined
  const data = value as Record<string, unknown>
  const produces = Array.isArray(data.produces)
    ? data.produces.map((item) => String(item).trim()).filter(Boolean)
    : []
  const doesNotProduce = Array.isArray(data.does_not_produce)
    ? data.does_not_produce.map((item) => String(item).trim()).filter(Boolean)
    : []
  if (produces.length === 0 && doesNotProduce.length === 0) return undefined
  return {
    produces: Array.from(new Set(produces)),
    does_not_produce: Array.from(new Set(doesNotProduce)),
  }
}

function defaultDeveloperApprovalGrantPolicy(): DeveloperGrantPolicy {
  return {
    allowed_grant_types: ['one_time', 'session_bound'],
    default_grant_type: 'one_time',
    expires_in_seconds: 900,
    max_uses: 1,
  }
}

function normalizeDeveloperGrantPolicy(value: unknown): DeveloperGrantPolicy | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  const data = value as Record<string, unknown>
  const allowed = Array.isArray(data.allowed_grant_types)
    ? data.allowed_grant_types
      .map((item) => String(item).trim())
      .filter((item): item is DeveloperGrantType => item === 'one_time' || item === 'session_bound')
    : []
  const defaultGrantType = String(data.default_grant_type ?? '').trim()
  const default_grant_type: DeveloperGrantType = defaultGrantType === 'session_bound' ? 'session_bound' : 'one_time'
  return {
    allowed_grant_types: Array.from(new Set(allowed.length ? allowed : [default_grant_type])),
    default_grant_type,
    expires_in_seconds: Math.max(1, Number(data.expires_in_seconds) || 900),
    max_uses: Math.max(1, Number(data.max_uses) || 1),
  }
}

function mappingRequiresApprovalGrantPolicy(mapping: DeveloperIntegrationFrontingCapabilityMapping): boolean {
  const sideEffectLevel = mapping.side_effect_level.trim().toLowerCase()
  const executionPosture = mapping.execution_posture.trim().toLowerCase()
  const producedEffects = mapping.business_effects?.produces.map((effect) => effect.trim().toLowerCase()) ?? []
  return mapping.approval_rule_refs.length > 0
    || sideEffectLevel.includes('approval')
    || sideEffectLevel === 'write'
    || sideEffectLevel.includes('mutation')
    || executionPosture.includes('approval')
    || producedEffects.includes('approval.request')
    || producedEffects.includes('system.preview_mutation')
    || producedEffects.includes('system.mutation')
}

function grantPolicyFromFrontingMapping(mapping?: DeveloperIntegrationFrontingCapabilityMapping | null): DeveloperGrantPolicy | null {
  if (!mapping) return null
  if (mapping.grant_policy) return { ...mapping.grant_policy, allowed_grant_types: [...mapping.grant_policy.allowed_grant_types] }
  return mappingRequiresApprovalGrantPolicy(mapping) ? defaultDeveloperApprovalGrantPolicy() : null
}

function normalizeIntegrationFrontingMapping(
  artifact: ArtifactRecord,
): DeveloperIntegrationFrontingCapabilityMapping | null {
  const data = artifact.data ?? {}
  if (data.artifact_type !== INTEGRATION_FRONTING_MAPPING_ARTIFACT_TYPE) return null
  const capabilityId = String(data.capability_id ?? '').trim()
  if (!capabilityId) return null
  const requiredInputs = Array.isArray(data.required_inputs) ? data.required_inputs.map((item) => String(item).trim()).filter(Boolean) : []
  const optionalInputs = Array.isArray(data.optional_inputs) ? data.optional_inputs.map((item) => String(item).trim()).filter(Boolean) : []
  const inputMetadata = normalizeIntegrationFrontingInputMetadata(data.inputs ?? data.input_metadata)
  const derivedRequiredBackendInputs = Array.isArray(data.derived_required_backend_inputs)
    ? data.derived_required_backend_inputs.map((item) => String(item).trim()).filter(Boolean)
    : []
  const derivedOptionalBackendInputs = Array.isArray(data.derived_optional_backend_inputs)
    ? data.derived_optional_backend_inputs.map((item) => String(item).trim()).filter(Boolean)
    : []
  const explicitRequiredBackendInputs = Array.isArray(data.explicit_required_backend_inputs)
    ? data.explicit_required_backend_inputs.map((item) => String(item).trim()).filter(Boolean)
    : []
  const explicitOptionalBackendInputs = Array.isArray(data.explicit_optional_backend_inputs)
    ? data.explicit_optional_backend_inputs.map((item) => String(item).trim()).filter(Boolean)
    : []
  const backendBindings = normalizeIntegrationFrontingBackendBindings(data)
  const primaryBinding = backendBindings[0]
  const backendInputMode = data.backend_input_mode === 'explicit' || data.backend_input_mode === 'hybrid'
    ? data.backend_input_mode
    : 'implicit'
  return {
    id: String(data.id ?? artifact.id),
    capability_id: capabilityId,
    title: String(data.title ?? humanize(capabilityId)).trim(),
    intent: String(data.intent ?? data.summary ?? '').trim(),
    service_id: String(data.service_id ?? '').trim(),
    service_name: String(data.service_name ?? '').trim(),
    backend_kind: primaryBinding?.backend_kind ?? (data.backend_kind === 'mcp' || data.backend_kind === 'database' || data.backend_kind === 'hybrid' ? data.backend_kind : 'native_api'),
    connection_ref: primaryBinding?.connection_ref ?? String(data.connection_ref ?? '').trim(),
    raw_operation_refs: primaryBinding?.raw_operation_refs ?? (Array.isArray(data.raw_operation_refs) ? data.raw_operation_refs.map((item) => String(item).trim()).filter(Boolean) : []),
    backend_bindings: backendBindings,
    execution_posture: String(data.execution_posture ?? 'prepare_only').trim(),
    side_effect_level: String(data.side_effect_level ?? 'write_adjacent').trim(),
    grant_policy: normalizeDeveloperGrantPolicy(data.grant_policy),
    subject_kind: String(data.subject_kind ?? '').trim(),
    context_type: String(data.context_type ?? '').trim(),
    output_intent: String(data.output_intent ?? '').trim(),
    business_effects: normalizeDeveloperBusinessEffects(data.business_effects),
    required_inputs: requiredInputs,
    optional_inputs: optionalInputs,
    input_metadata: inputMetadata.length > 0 ? inputMetadata : undefined,
    backend_input_mode: backendInputMode,
    derived_required_backend_inputs: derivedRequiredBackendInputs,
    derived_optional_backend_inputs: derivedOptionalBackendInputs,
    explicit_required_backend_inputs: explicitRequiredBackendInputs,
    explicit_optional_backend_inputs: explicitOptionalBackendInputs,
    approval_rule_refs: Array.isArray(data.approval_rule_refs) ? data.approval_rule_refs.map((item) => String(item).trim()).filter(Boolean) : [],
    denial_rule_refs: Array.isArray(data.denial_rule_refs) ? data.denial_rule_refs.map((item) => String(item).trim()).filter(Boolean) : [],
    clarification_rule_refs: Array.isArray(data.clarification_rule_refs) ? data.clarification_rule_refs.map((item) => String(item).trim()).filter(Boolean) : [],
    audit_required: data.audit_required !== false,
    outbound_controls: typeof data.outbound_controls === 'object' && data.outbound_controls ? data.outbound_controls as Record<string, unknown> : undefined,
  }
}

function normalizeIntegrationFrontingInputMetadata(value: unknown): DeveloperCapabilityInputFormalization[] {
  if (!Array.isArray(value)) return []
  return value
    .map((item) => {
      if (!item || typeof item !== 'object') return null
      const data = item as Record<string, any>
      const inputName = String(data.input_name ?? data.name ?? '').trim()
      if (!inputName) return null
      return withInputResolution({
        input_name: inputName,
        input_type: String(data.input_type ?? data.type ?? 'string').trim() || 'string',
        required: Boolean(data.required),
        summary: String(data.summary ?? data.description ?? inputName).trim(),
        default_value: data.default_value == null ? '' : String(data.default_value),
        allowed_values: Array.isArray(data.allowed_values) ? data.allowed_values.map((entry) => String(entry)) : [],
        semantic_type: String(data.semantic_type ?? '').trim(),
        input_format: String(data.input_format ?? data.format ?? '').trim(),
        validation_pattern: String(data.validation_pattern ?? data.pattern ?? '').trim(),
        clarification_hint: String(data.clarification_hint ?? '').trim(),
        entity_reference: Boolean(data.entity_reference),
        reference_catalog: Array.isArray(data.reference_catalog) ? data.reference_catalog.map((entry) => String(entry)) : [],
        semantic_aliases: Array.isArray(data.semantic_aliases) ? data.semantic_aliases.map((entry) => String(entry)) : [],
        normalization_hint: String(data.normalization_hint ?? '').trim(),
        normalization_context: String(data.normalization_context ?? '').trim(),
        allowed_value_semantics: Array.isArray(data.allowed_value_semantics)
          ? data.allowed_value_semantics.map((entry: Record<string, any>) => ({
              value: String(entry.value ?? ''),
              aliases: Array.isArray(entry.aliases) ? entry.aliases.map((alias: unknown) => String(alias)) : [],
            }))
          : [],
        resolution: normalizeInputResolution(data.resolution),
        catalog_ref: String(data.catalog_ref ?? '').trim(),
      })
    })
    .filter((item): item is DeveloperCapabilityInputFormalization => Boolean(item))
}

function buildIntegrationFrontingMappings(pmArtifacts: ArtifactRecord[]): DeveloperIntegrationFrontingCapabilityMapping[] {
  return findIntegrationFrontingMappingArtifacts(pmArtifacts)
    .map((artifact) => normalizeIntegrationFrontingMapping(artifact))
    .filter((mapping): mapping is DeveloperIntegrationFrontingCapabilityMapping => Boolean(mapping))
}

function frontingInputBaseMetadata(
  inputName: string,
  required: boolean,
  mapping: DeveloperIntegrationFrontingCapabilityMapping,
): DeveloperCapabilityInputFormalization {
  const normalizedName = normalizeText(inputName)
  const label = humanize(inputName)
  const subject = mapping.subject_kind || mapping.context_type || 'record'
  const requiredPrefix = required ? 'Required' : 'Optional'
  let semanticType = 'business_context'
  let inputFormat = ''
  let validationPattern = ''
  let entityReference = false
  let summary = `${requiredPrefix} governed fronting input for ${label}.`
  let clarificationHint = required ? `Ask for ${label} before invoking ${mapping.capability_id}.` : ''

  if (/\b(issue|ticket|case|incident|task|pull request|pr)\b/.test(normalizedName) && /\b(key|id|ref|reference)\b/.test(normalizedName)) {
    semanticType = 'entity_reference'
    validationPattern = '^[A-Za-z][A-Za-z0-9_.-]*-[0-9]+$'
    entityReference = true
    summary = `${requiredPrefix} downstream ${humanize(subject)} reference used to bind the governed request.`
    clarificationHint = `Ask for the ${humanize(subject)} reference, for example PROJECT-123.`
  } else if (/\b(project|workspace|repo|repository|channel|team|tenant|org|organization)\b/.test(normalizedName) && /\b(key|id|slug|name)\b/.test(normalizedName)) {
    semanticType = 'scope_reference'
    validationPattern = '^[A-Za-z][A-Za-z0-9_.-]*$'
    entityReference = true
    summary = `${requiredPrefix} downstream scope identifier that constrains the governed request.`
    clarificationHint = `Ask which ${label} should be used before invoking ${mapping.capability_id}.`
  } else if (['owner', 'repo', 'repository'].includes(normalizedName)) {
    semanticType = 'scope_reference'
    validationPattern = '^[A-Za-z][A-Za-z0-9_.-]*$'
    entityReference = true
    summary = `${requiredPrefix} downstream ${label} scope that constrains the governed request.`
    clarificationHint = `Ask which ${label} should be used before invoking ${mapping.capability_id}.`
  } else if (/\b(range|selection|selected|refs|references)\b/.test(normalizedName)) {
    semanticType = 'selection_scope'
    summary = `${requiredPrefix} explicit selected-record scope for the governed request.`
    clarificationHint = `Ask which ${label} should bound the selected records for ${mapping.capability_id}.`
  } else if (/\b(status|state|transition|stage)\b/.test(normalizedName)) {
    semanticType = 'workflow_state'
    summary = `${requiredPrefix} target workflow state for the governed request.`
    clarificationHint = `Ask which ${label} should be requested.`
  } else if (/\b(reason|rationale|justification|purpose)\b/.test(normalizedName)) {
    semanticType = 'business_justification'
    summary = `${requiredPrefix} business reason used for approval, audit, or downstream context.`
    clarificationHint = `Ask for the business reason for this governed request.`
  } else if (/\b(summary|title|subject)\b/.test(normalizedName)) {
    semanticType = 'content_summary'
    summary = `${requiredPrefix} concise user-reviewed summary for the downstream ${humanize(subject)}.`
    clarificationHint = `Ask for a short ${label}.`
  } else if (/\b(description|details|body|content|context|message|comment)\b/.test(normalizedName)) {
    semanticType = 'content_detail'
    summary = `${requiredPrefix} user-provided context or content for the governed request.`
    clarificationHint = `Ask for the relevant ${label}.`
  } else if (/\b(criteria|acceptance|expected|repro|steps)\b/.test(normalizedName)) {
    semanticType = 'acceptance_criteria'
    summary = `${requiredPrefix} expected behavior or validation detail for the downstream work item.`
    clarificationHint = `Ask for ${label} or expected behavior.`
  } else if (/\b(severity|priority|impact|risk|urgency)\b/.test(normalizedName)) {
    semanticType = 'risk_or_priority_level'
    summary = `${requiredPrefix} risk, impact, or priority signal used by governance and routing.`
    clarificationHint = `Ask for the ${label} level.`
  } else if (/\b(query|search|jql|filter)\b/.test(normalizedName)) {
    semanticType = 'bounded_search_query'
    summary = `${requiredPrefix} bounded search criteria for read-only discovery.`
    clarificationHint = `Ask for bounded ${label} criteria rather than running an unrestricted search.`
  } else if (/\b(limit|count|max|page size)\b/.test(normalizedName)) {
    semanticType = 'quantity_limit'
    validationPattern = '^[1-9][0-9]*$'
    summary = `${requiredPrefix} result bound for the governed request.`
    clarificationHint = required ? `Ask for a maximum result count.` : ''
  } else if (/\b(label|labels|tag|tags)\b/.test(normalizedName)) {
    semanticType = 'classification_tags'
    summary = `${requiredPrefix} classification labels for downstream filtering or creation.`
    clarificationHint = required ? `Ask which labels or tags should be used.` : ''
  }

  return withInputResolution({
    input_name: inputName,
    input_type: semanticType === 'quantity_limit' ? 'integer' : 'string',
    required,
    summary,
    default_value: '',
    allowed_values: [],
    semantic_type: semanticType,
    input_format: inputFormat,
    validation_pattern: validationPattern,
    clarification_hint: clarificationHint,
    entity_reference: entityReference,
    reference_catalog: [],
    semantic_aliases: [],
    normalization_hint: semanticType === 'bounded_search_query'
      ? 'Reject or clarify unbounded searches before invoking downstream systems.'
      : '',
    normalization_context: `Generated from governed fronting mapping ${mapping.capability_id}.`,
    allowed_value_semantics: [],
  })
}

function mergeFrontingInputMetadata(
  input: DeveloperCapabilityInputFormalization,
  mapping: DeveloperIntegrationFrontingCapabilityMapping,
): DeveloperCapabilityInputFormalization {
  const inferred = frontingInputBaseMetadata(input.input_name, input.required, mapping)
  return withInputResolution({
    ...input,
    input_type: input.input_type || inferred.input_type,
    summary: input.summary || inferred.summary,
    default_value: input.default_value ?? inferred.default_value,
    allowed_values: input.allowed_values?.length ? [...input.allowed_values] : [...inferred.allowed_values],
    semantic_type: input.semantic_type || inferred.semantic_type,
    input_format: isContractSafeInputFormat(input.input_format) ? input.input_format : inferred.input_format,
    validation_pattern: input.validation_pattern || inferred.validation_pattern,
    clarification_hint: input.clarification_hint || inferred.clarification_hint,
    entity_reference: Boolean(input.entity_reference || inferred.entity_reference),
    reference_catalog: input.reference_catalog?.length ? [...input.reference_catalog] : [...(inferred.reference_catalog ?? [])],
    semantic_aliases: input.semantic_aliases?.length ? [...input.semantic_aliases] : [...(inferred.semantic_aliases ?? [])],
    normalization_hint: input.normalization_hint || inferred.normalization_hint,
    normalization_context: input.normalization_context || inferred.normalization_context,
    allowed_value_semantics: input.allowed_value_semantics?.length
      ? input.allowed_value_semantics.map((entry) => ({ value: entry.value, aliases: [...(entry.aliases ?? [])] }))
      : [...(inferred.allowed_value_semantics ?? [])],
    resolution: normalizeInputResolution(input.resolution) ?? inferred.resolution,
    catalog_ref: input.catalog_ref || inferred.catalog_ref,
  })
}

function buildIntegrationFrontingInputs(mapping: DeveloperIntegrationFrontingCapabilityMapping): DeveloperCapabilityInputFormalization[] {
  if (mapping.input_metadata?.length) {
    const metadataByName = new Map(mapping.input_metadata.map((input) => [input.input_name, input]))
    return [
      ...mapping.required_inputs.map((inputName) =>
        metadataByName.has(inputName)
          ? mergeFrontingInputMetadata({ ...metadataByName.get(inputName)!, required: true }, mapping)
          : frontingInputBaseMetadata(inputName, true, mapping),
      ),
      ...mapping.optional_inputs.map((inputName) =>
        metadataByName.has(inputName)
          ? mergeFrontingInputMetadata({ ...metadataByName.get(inputName)!, required: false }, mapping)
          : frontingInputBaseMetadata(inputName, false, mapping),
      ),
    ]
  }
  return [
    ...mapping.required_inputs.map((input) => frontingInputBaseMetadata(input, true, mapping)),
    ...mapping.optional_inputs.map((input) => frontingInputBaseMetadata(input, false, mapping)),
  ]
}

function isContractSafeInputFormat(value: string | undefined | null): boolean {
  return ['business_quarter', 'date', 'date_time', 'email', 'url', 'uuid'].includes(String(value ?? '').trim())
}

const INPUT_RESOLUTION_MODES = new Set<DeveloperCapabilityInputResolutionMode>([
  'closed_values',
  'backend_resolved',
  'app_selected',
  'actor_policy',
  'actor_policy_or_explicit',
  'explicit_only',
  'clarify',
])

const INPUT_RESOLUTION_BEHAVIORS = new Set<DeveloperCapabilityInputResolutionBehavior>([
  'clarify',
  'use_default',
  'use_actor_scope',
  'app_select_or_clarify',
  'deny',
  'deny_or_clarify',
  'omit',
])

function normalizeInputResolution(value: unknown): DeveloperCapabilityInputResolution | undefined {
  if (!value || typeof value !== 'object') return undefined
  const raw = value as Record<string, unknown>
  const mode = typeof raw.mode === 'string' && INPUT_RESOLUTION_MODES.has(raw.mode as DeveloperCapabilityInputResolutionMode)
    ? raw.mode as DeveloperCapabilityInputResolutionMode
    : undefined
  if (!mode) return undefined
  const behavior = (key: 'on_missing' | 'on_ambiguous' | 'on_unresolved') =>
    typeof raw[key] === 'string' && INPUT_RESOLUTION_BEHAVIORS.has(raw[key] as DeveloperCapabilityInputResolutionBehavior)
      ? raw[key] as DeveloperCapabilityInputResolutionBehavior
      : undefined
  return omitUndefinedFields({
    mode,
    resolver_ref: typeof raw.resolver_ref === 'string' && raw.resolver_ref.trim() ? raw.resolver_ref.trim() : undefined,
    on_missing: behavior('on_missing'),
    on_ambiguous: behavior('on_ambiguous'),
    on_unresolved: behavior('on_unresolved'),
  })
}

function splitContractListValues(values: unknown[] | undefined): string[] {
  return (values ?? [])
    .flatMap((entry) => String(entry ?? '').split(/[;,]/))
    .map((entry) => entry.trim())
    .filter(Boolean)
}

function inferInputResolution(input: DeveloperCapabilityInputFormalization): DeveloperCapabilityInputResolution {
  const semanticType = String(input.semantic_type ?? '').trim().toLowerCase().replace(/[\s-]+/g, '_')
  const hasDefault = String(input.default_value ?? '').trim().length > 0
  const hasAllowedValues = (input.allowed_values ?? []).some((value) => value.trim())
  const missingBehavior: DeveloperCapabilityInputResolutionBehavior = hasDefault
    ? 'use_default'
    : input.required
      ? 'clarify'
      : 'omit'
  if (hasAllowedValues) {
    return { mode: 'closed_values', on_missing: missingBehavior, on_ambiguous: 'clarify', on_unresolved: 'clarify' }
  }
  if (semanticType === 'scope_reference' || semanticType === 'selection_scope') {
    return { mode: 'actor_policy_or_explicit', on_missing: input.required ? 'clarify' : 'use_actor_scope', on_ambiguous: 'clarify', on_unresolved: 'clarify' }
  }
  if (input.entity_reference || semanticType.endsWith('_reference') || semanticType === 'entity_reference') {
    const catalogRef = String(input.catalog_ref ?? '').trim() || (semanticType ? `${semanticType.replace(/_reference$/, '')}_catalog` : undefined)
    return omitUndefinedFields({
      mode: 'backend_resolved',
      resolver_ref: catalogRef,
      on_missing: input.required ? 'clarify' : 'omit',
      on_ambiguous: 'clarify',
      on_unresolved: 'clarify',
    })
  }
  if (input.clarification_hint || input.required) {
    return { mode: 'clarify', on_missing: input.required ? 'clarify' : 'omit', on_ambiguous: 'clarify', on_unresolved: 'clarify' }
  }
  return { mode: 'explicit_only', on_missing: missingBehavior }
}

function withInputResolution(input: DeveloperCapabilityInputFormalization): DeveloperCapabilityInputFormalization {
  const catalogRef = String(input.catalog_ref ?? '').trim()
    || ((input.reference_catalog ?? []).length > 0 ? `${input.input_name}_catalog` : '')
  const normalized = normalizeInputResolution(input.resolution)
  const allowedValues = splitContractListValues(input.allowed_values)
  const resolution = normalized
    && ['backend_resolved', 'closed_values'].includes(normalized.mode)
    && !normalized.resolver_ref
    && catalogRef
    ? { ...normalized, resolver_ref: catalogRef }
    : normalized
  return omitUndefinedFields({
    ...input,
    allowed_values: allowedValues,
    catalog_ref: catalogRef || undefined,
    resolution: resolution ?? inferInputResolution({
      ...input,
      allowed_values: allowedValues,
      catalog_ref: catalogRef || input.catalog_ref,
    }),
  })
}

function contractInputFormalization(input: DeveloperCapabilityInputFormalization): Record<string, any> {
  const normalized = withInputResolution(input)
  return omitUndefinedFields({
    input_name: normalized.input_name,
    input_type: normalized.input_type,
    required: normalized.required,
    summary: normalized.summary,
    default_value: normalized.default_value,
    allowed_values: normalized.allowed_values ?? [],
    semantic_type: normalized.semantic_type || undefined,
    input_format: normalized.input_format || undefined,
    validation_pattern: normalized.validation_pattern || undefined,
    clarification_hint: normalized.clarification_hint || undefined,
    entity_reference: normalized.entity_reference || undefined,
    semantic_aliases: normalized.semantic_aliases?.length ? normalized.semantic_aliases : undefined,
    normalization_hint: normalized.normalization_hint || undefined,
    normalization_context: normalized.normalization_context || undefined,
    allowed_value_semantics: normalized.allowed_value_semantics?.length ? normalized.allowed_value_semantics : undefined,
    catalog_ref: normalized.catalog_ref || undefined,
    resolution: normalized.resolution,
  })
}

function omitUndefinedFields<T extends Record<string, any>>(value: T): T {
  return Object.fromEntries(
    Object.entries(value).filter(([, entry]) => entry !== undefined),
  ) as T
}

export function resolveEvaluationEvidenceEnvelope(
  record: { data?: Record<string, any> } | null | undefined,
): import('./project-types').EvaluationEvidenceEnvelope | null {
  return (record?.data?.evidence as import('./project-types').EvaluationEvidenceEnvelope | undefined) ?? null
}

export function resolveEvaluationCompiledContractIdentity(
  record: { data?: Record<string, any> } | null | undefined,
): DeveloperCompiledContractIdentity | null {
  const envelope = resolveEvaluationEvidenceEnvelope(record)
  return envelope?.compiled_contract_identity ?? null
}

export function resolveEvaluationServiceMetadataSnapshot(
  record: { data?: Record<string, any> } | null | undefined,
): ObservedServiceMetadata | null {
  const envelope = resolveEvaluationEvidenceEnvelope(record)
  return envelope?.service_metadata_snapshot ?? null
}

export function resolveEvaluationObservedServiceEvidence(
  record: { data?: Record<string, any> } | null | undefined,
): EvaluationObservedServiceEvidenceSummary | null {
  const envelope = resolveEvaluationEvidenceEnvelope(record)
  return envelope?.observed_service_evidence ?? null
}

export function buildGeneratedStructureSummary(definition: DeveloperDefinitionData): DeveloperGeneratedStructureSummary {
  const selectedServiceIds = [...definition.generation.selected_service_ids]
  const serviceLabelById = new Map(
    definition.service_topology_bindings.map((binding) => [
      binding.service_id,
      binding.service_name || binding.source_role || humanize(binding.service_id),
    ] as const),
  )
  const capabilityOwnership: DeveloperGeneratedCapabilityOwnership[] = definition.capability_formalizations.map((capability) => ({
    capability_id: capability.capability_id,
    service_id: capability.service_id || null,
    source_kind: capability.source_kind,
  }))
  const services: DeveloperGeneratedServiceTarget[] = selectedServiceIds.map((serviceId) => ({
    service_id: serviceId,
    service_name: serviceLabelById.get(serviceId) || humanize(serviceId),
    owned_capability_ids: capabilityOwnership
      .filter((capability) => capability.service_id === serviceId)
      .map((capability) => capability.capability_id),
    participating_scenario_ids: definition.scenario_formalizations
      .filter((scenario) => scenario.participating_service_ids.includes(serviceId))
      .map((scenario) => scenario.scenario_id),
  }))
  return {
    service_ids: selectedServiceIds,
    protocols: [...definition.generation.protocols],
    services,
    capability_ownership: capabilityOwnership,
    scenario_ids: definition.scenario_formalizations.map((scenario) => scenario.scenario_id),
    data_access_backend_type:
      definition.service_backend_bindings.find((binding) => binding.uses_data_access_backend)?.data_access_backend_type
      || null,
    application_integration_backend_type:
      definition.service_backend_bindings.find((binding) => binding.uses_application_integration_backend)?.application_integration_backend_type
      || null,
    integration_fronting_mapping_count: (definition.integration_fronting?.capability_mappings ?? []).length,
    generated_output_kinds: [
      'runtime_target_manifest',
      'service_estate_manifest',
      'service_composition_manifest',
      'runtime_service_contract',
      'runtime_service_scaffold',
      'runtime_capability_registry',
      'runtime_estate_scaffold',
      'runtime_design_packet',
      'runtime_scenario_pack',
      'runtime_scenario_manifest',
      'runtime_backend_bindings',
      'runtime_policy_stub',
      'integration_adapter_bindings',
      'backend_selection_template',
      'integration_adapter_scaffold',
      'anip_local_conformance_report',
      'extension_playbook',
    ],
  }
}

function integrationFrontingBackendBindingsForService(definition: DeveloperDefinitionData, serviceId: string): string[] {
  return Array.from(new Set(
    (definition.integration_fronting?.capability_mappings ?? [])
      .filter((mapping) => mapping.service_id === serviceId)
      .flatMap((mapping) => (mapping.backend_bindings ?? []).length > 0
        ? (mapping.backend_bindings ?? [])
        : [{ backend_kind: mapping.backend_kind, connection_ref: mapping.connection_ref, raw_operation_refs: mapping.raw_operation_refs ?? [] }])
      .filter((binding) => String(binding.connection_ref ?? '').trim())
      .map((binding) => `${binding.backend_kind}:${binding.connection_ref}`),
  ))
}

export function buildIntegrationAdapterBindings(
  definition: DeveloperDefinitionData,
): DeveloperGeneratedIntegrationAdapterBinding[] {
  return (definition.integration_fronting?.capability_mappings ?? []).map((mapping) => ({
    binding_id: mapping.id,
    capability_id: mapping.capability_id,
    service_id: mapping.service_id,
    service_name: mapping.service_name,
    backend_kind: mapping.backend_kind,
    connection_ref: mapping.connection_ref,
    raw_operation_refs: [...mapping.raw_operation_refs],
    backend_bindings: mapping.backend_bindings.map((binding) => ({
      backend_kind: binding.backend_kind,
      connection_ref: binding.connection_ref,
      raw_operation_refs: [...binding.raw_operation_refs],
      backend_input_mode: binding.backend_input_mode ?? mapping.backend_input_mode,
      derived_required_backend_inputs: [...(binding.derived_required_backend_inputs ?? mapping.derived_required_backend_inputs)],
      derived_optional_backend_inputs: [...(binding.derived_optional_backend_inputs ?? mapping.derived_optional_backend_inputs)],
      explicit_required_backend_inputs: [...(binding.explicit_required_backend_inputs ?? mapping.explicit_required_backend_inputs)],
      explicit_optional_backend_inputs: [...(binding.explicit_optional_backend_inputs ?? mapping.explicit_optional_backend_inputs)],
      matched_discovery_record_ids: [...(binding.matched_discovery_record_ids ?? [])],
      status: binding.status,
      status_detail: binding.status_detail,
    })),
    execution_posture: mapping.execution_posture,
    side_effect_level: mapping.side_effect_level,
    subject_kind: mapping.subject_kind,
    context_type: mapping.context_type,
    output_intent: mapping.output_intent,
    required_inputs: [...mapping.required_inputs],
    optional_inputs: [...mapping.optional_inputs],
    backend_input_mode: mapping.backend_input_mode,
    derived_required_backend_inputs: [...mapping.derived_required_backend_inputs],
    derived_optional_backend_inputs: [...mapping.derived_optional_backend_inputs],
    explicit_required_backend_inputs: [...mapping.explicit_required_backend_inputs],
    explicit_optional_backend_inputs: [...mapping.explicit_optional_backend_inputs],
    governance: {
      approval_rule_refs: [...mapping.approval_rule_refs],
      denial_rule_refs: [...mapping.denial_rule_refs],
      clarification_rule_refs: [...mapping.clarification_rule_refs],
      audit_required: mapping.audit_required,
    },
    outbound_controls: mapping.outbound_controls,
  }))
}

function camelizeIdentifier(value: string): string {
  return value
    .replace(/(^|[-_.\s]+)([a-zA-Z0-9])/g, (_match, _separator, char: string) => char.toUpperCase())
    .replace(/[^a-zA-Z0-9]/g, '')
}

export function buildIntegrationAdapterScaffoldModuleContent(
  serviceId: string,
  bindings: DeveloperGeneratedIntegrationAdapterBinding[],
): string {
  const exportedName = `${camelizeIdentifier(serviceId)}IntegrationAdapter`
  return [
    `// Generic integration adapter scaffold for ${bindings[0]?.service_name || serviceId}.`,
    '// Generated from accepted integration-fronting mappings in the saved Service Definition.',
    '// Runtime secrets and provider-specific request/response logic must stay in the deployment extension layer.',
    '',
    `export const ${exportedName}Bindings = ${JSON.stringify(bindings, null, 2)} as const`,
    '',
    'export type BackendSelectionEntry = {',
    '  active_backend_kind?: string',
    '  active_connection_ref?: string',
    '}',
    '',
    'export type EffectiveBackendInputContract = {',
    "  mode: 'implicit' | 'hybrid' | 'explicit'",
    '  required: string[]',
    '  optional: string[]',
    '}',
    '',
    'export type BackendInvocationPlan = {',
    '  selected_binding: {',
    "    backend_kind: 'native_api' | 'mcp' | 'database' | 'hybrid'",
    '    connection_ref: string',
    '    raw_operation_refs: string[]',
    "    backend_input_mode?: 'implicit' | 'hybrid' | 'explicit'",
    '    derived_required_backend_inputs?: string[]',
    '    derived_optional_backend_inputs?: string[]',
    '    explicit_required_backend_inputs?: string[]',
    '    explicit_optional_backend_inputs?: string[]',
    '  }',
    '  semantic_input: Record<string, unknown>',
    '  backend_input_contract: EffectiveBackendInputContract',
    '  unresolved_required_backend_inputs: string[]',
    '}',
    '',
    'export type BackendSelection = Record<string, BackendSelectionEntry>',
    '',
    'function uniqueStrings(values: string[]) {',
    '  return Array.from(new Set(values.filter(Boolean)))',
    '}',
    '',
    `function effectiveBackendBindings(binding: (typeof ${exportedName}Bindings)[number]) {`,
    '  return binding.backend_bindings.length > 0',
    '    ? binding.backend_bindings',
    '    : [{',
    '        backend_kind: binding.backend_kind,',
    '        connection_ref: binding.connection_ref,',
    '        raw_operation_refs: binding.raw_operation_refs,',
    '        backend_input_mode: binding.backend_input_mode,',
    '        derived_required_backend_inputs: binding.derived_required_backend_inputs,',
    '        derived_optional_backend_inputs: binding.derived_optional_backend_inputs,',
    '        explicit_required_backend_inputs: binding.explicit_required_backend_inputs,',
    '        explicit_optional_backend_inputs: binding.explicit_optional_backend_inputs,',
    '      }]',
    '}',
    '',
    `function selectBackendBinding(binding: (typeof ${exportedName}Bindings)[number], selection?: BackendSelectionEntry) {`,
    '  const available = effectiveBackendBindings(binding)',
    '  if (available.length === 1) return available[0]',
    '  if (!selection?.active_backend_kind && !selection?.active_connection_ref) {',
    "    const availableLabels = available.map((item) => item.backend_kind + ':' + item.connection_ref).join(', ')",
    '    throw new Error(`Select active backend for ${binding.capability_id}; available: ${availableLabels}`)',
    '  }',
    '  const selected = available.find((item) =>',
    '    (!selection.active_backend_kind || item.backend_kind === selection.active_backend_kind)',
    '    && (!selection.active_connection_ref || item.connection_ref === selection.active_connection_ref),',
    '  )',
    '  if (!selected) throw new Error(`Configured backend selection does not match ${binding.capability_id}`)',
    '  return selected',
    '}',
    '',
    `function effectiveBackendInputContract(binding: (typeof ${exportedName}Bindings)[number], selectedBinding: ReturnType<typeof selectBackendBinding>): EffectiveBackendInputContract {`,
    "  const mode = selectedBinding.backend_input_mode || binding.backend_input_mode",
    '  const derivedRequired = selectedBinding.derived_required_backend_inputs?.length ? selectedBinding.derived_required_backend_inputs : binding.derived_required_backend_inputs',
    '  const derivedOptional = selectedBinding.derived_optional_backend_inputs?.length ? selectedBinding.derived_optional_backend_inputs : binding.derived_optional_backend_inputs',
    '  const explicitRequired = selectedBinding.explicit_required_backend_inputs?.length ? selectedBinding.explicit_required_backend_inputs : binding.explicit_required_backend_inputs',
    '  const explicitOptional = selectedBinding.explicit_optional_backend_inputs?.length ? selectedBinding.explicit_optional_backend_inputs : binding.explicit_optional_backend_inputs',
    "  if (mode === 'explicit') {",
    '    return {',
    "      mode: 'explicit',",
    '      required: uniqueStrings([...(explicitRequired || [])]),',
    '      optional: uniqueStrings(',
    '        (explicitOptional || []).filter((item) => !(explicitRequired || []).includes(item)),',
    '      ),',
    '    }',
    '  }',
    "  if (mode === 'hybrid') {",
    '    const required = uniqueStrings([',
    '      ...(derivedRequired || []),',
    '      ...(explicitRequired || []),',
    '    ])',
    '    const optional = uniqueStrings([',
    '      ...(derivedOptional || []),',
    '      ...(explicitOptional || []),',
    '    ]).filter((item) => !required.includes(item))',
    "    return { mode: 'hybrid', required, optional }",
    '  }',
    '  const required = uniqueStrings([...(derivedRequired || [])])',
    '  const optional = uniqueStrings([...(derivedOptional || [])]).filter((item) => !required.includes(item))',
    "  return { mode: 'implicit', required, optional }",
    '}',
    '',
    `function buildBackendInvocationPlan(binding: (typeof ${exportedName}Bindings)[number], input: Record<string, unknown>, selection?: BackendSelectionEntry): BackendInvocationPlan {`,
    '  const selected_binding = selectBackendBinding(binding, selection)',
    '  const backend_input_contract = effectiveBackendInputContract(binding, selected_binding)',
    '  const semanticInputKeys = new Set([',
    '    ...binding.required_inputs,',
    '    ...binding.optional_inputs,',
    '  ])',
    '  const semantic_input = Object.fromEntries(',
    '    Object.entries(input).filter(([key]) => semanticInputKeys.has(key)),',
    '  )',
    '  const adapterInputKeys = new Set([',
    '    ...semanticInputKeys,',
    '    ...backend_input_contract.required,',
    '    ...backend_input_contract.optional,',
    '  ])',
    '  const adapter_input = Object.fromEntries(',
    '    Object.entries(input).filter(([key]) => adapterInputKeys.has(key)),',
    '  )',
    '  const unresolved_required_backend_inputs = backend_input_contract.required.filter((key) => !(key in input))',
    '  return {',
    '    selected_binding,',
    '    semantic_input,',
    '    adapter_input,',
    '    backend_input_contract,',
    '    unresolved_required_backend_inputs,',
    '  }',
    '}',
    '',
    `export async function ${exportedName}(capabilityId: string, input: Record<string, unknown>, backendSelection: BackendSelection = {}) {`,
    `  const binding = ${exportedName}Bindings.find((item) => item.capability_id === capabilityId)`,
    "  if (!binding) throw new Error(`Unknown integration capability: ${capabilityId}`)",
    '  const plan = buildBackendInvocationPlan(binding, input, backendSelection[capabilityId])',
    '  if (plan.unresolved_required_backend_inputs.length > 0) {',
    "    throw new Error(`Backend adapter enrichment required for ${capabilityId}; unresolved backend inputs: ${plan.unresolved_required_backend_inputs.join(', ')}`)",
    '  }',
    "  throw new Error(`Implement provider adapter for ${plan.selected_binding.backend_kind}:${plan.selected_binding.raw_operation_refs.join(',')} using ${plan.backend_input_contract.mode} backend input mode`)",
    '}',
  ].join('\n')
}

export function buildLocalConformanceReport(params: {
  definition: DeveloperDefinitionData
  runtimeTarget: DeveloperGeneratedRuntimeTarget
  extensionManifest: DeveloperExtensionPoint[]
  generatedOutputKinds: string[]
  generatedAt?: string
}): DeveloperGeneratedConformanceReport {
  const generatedAt = params.generatedAt ?? new Date().toISOString()
  const serviceDefinitionDigest = params.definition.compiled_contract_identity?.signature ?? null
  const mappings = params.definition.integration_fronting?.capability_mappings ?? []
  const capabilityIds = new Set(params.definition.capability_formalizations.map((capability) => capability.capability_id))
  const generatedKinds = new Set(params.generatedOutputKinds)
  const runtimeCapabilities = new Set(
    params.runtimeTarget.services.flatMap((service) => service.capabilities.map((capability) => capability.capability_id)),
  )
  const extensionPointIds = new Set(params.extensionManifest.map((entry) => entry.id))
  const needsIntegrationAdapterScaffold = mappings.length > 0
  const mappingsRequiringBackendSelection = mappings.filter((mapping) => {
    const bindings = mapping.backend_bindings.length > 0
      ? mapping.backend_bindings
      : [{ backend_kind: mapping.backend_kind, connection_ref: mapping.connection_ref, raw_operation_refs: mapping.raw_operation_refs }]
    return bindings.length > 1
  })
  const missingMappedCapabilities = mappings
    .map((mapping) => mapping.capability_id)
    .filter((capabilityId) => !capabilityIds.has(capabilityId))
  const missingRuntimeMappedCapabilities = mappings
    .map((mapping) => mapping.capability_id)
    .filter((capabilityId) => !runtimeCapabilities.has(capabilityId))
  const mappingsMissingOperation = mappings.filter((mapping) => {
    const bindings = mapping.backend_bindings.length > 0
      ? mapping.backend_bindings
      : [{ connection_ref: mapping.connection_ref, raw_operation_refs: mapping.raw_operation_refs }]
    return !bindings.some((binding) => Boolean(binding.connection_ref) && binding.raw_operation_refs.length > 0)
  })
  const checks: DeveloperGeneratedConformanceReport['checks'] = [
    {
      id: 'schema_valid',
      label: 'Schema Valid',
      status: serviceDefinitionDigest ? 'passed' : 'failed',
      detail: serviceDefinitionDigest
        ? 'Service Definition has a compiled contract digest.'
        : 'Service Definition has not been saved with a compiled contract digest.',
    },
    {
      id: 'generated',
      label: 'Generated',
      status: generatedKinds.has('runtime_target_manifest') ? 'passed' : 'failed',
      detail: generatedKinds.has('runtime_target_manifest')
        ? 'Runtime target outputs were generated from the saved revision.'
        : 'Runtime target manifest output is missing.',
    },
    {
      id: 'integration_adapter_bindings',
      label: 'Integration Adapter Bindings',
      status: mappingsMissingOperation.length === 0 && (!needsIntegrationAdapterScaffold || generatedKinds.has('integration_adapter_scaffold'))
        ? 'passed'
        : 'failed',
      detail: mappingsMissingOperation.length === 0 && (!needsIntegrationAdapterScaffold || generatedKinds.has('integration_adapter_scaffold'))
        ? `${mappings.length} integration-fronting mapping(s) have connection and raw operation bindings.`
        : `${mappingsMissingOperation.length} integration-fronting mapping(s) are missing connection/raw operation bindings or the integration adapter scaffold is missing.`,
    },
    {
      id: 'backend_selection_template',
      label: 'Backend Selection Template',
      status: mappingsRequiringBackendSelection.length === 0 || generatedKinds.has('backend_selection_template')
        ? 'passed'
        : 'failed',
      detail: mappingsRequiringBackendSelection.length === 0 || generatedKinds.has('backend_selection_template')
        ? `${mappingsRequiringBackendSelection.length} capability mapping(s) require deployment-time backend selection.`
        : `${mappingsRequiringBackendSelection.length} capability mapping(s) have multiple backend bindings but no backend selection template was generated.`,
    },
    {
      id: 'runtime_surface_valid',
      label: 'Runtime Surface Valid',
      status: missingMappedCapabilities.length === 0 && missingRuntimeMappedCapabilities.length === 0 ? 'passed' : 'failed',
      detail: missingMappedCapabilities.length === 0 && missingRuntimeMappedCapabilities.length === 0
        ? 'Accepted integration-fronting mappings are present in the formalized capability and runtime surfaces.'
        : `Missing mapped capabilities: ${[...new Set([...missingMappedCapabilities, ...missingRuntimeMappedCapabilities])].join(', ') || 'unknown'}.`,
    },
    {
      id: 'extension_hooks_bound',
      label: 'Extension Hooks Bound',
      status: extensionPointIds.has('application-integration-backend-adapter') ? 'passed' : 'failed',
      detail: extensionPointIds.has('application-integration-backend-adapter')
        ? 'Application integration backend adapter extension surface is declared.'
        : 'Application integration backend adapter extension surface is missing.',
    },
    {
      id: 'contract_evidence_aligned',
      label: 'Contract Evidence Aligned',
      status: params.runtimeTarget.system_name === params.definition.identity.system_name ? 'passed' : 'failed',
      detail: params.runtimeTarget.system_name === params.definition.identity.system_name
        ? 'Generated runtime target identity aligns with the saved Service Definition identity.'
        : 'Generated runtime target identity does not align with the saved Service Definition identity.',
    },
  ]
  const passed = checks.filter((check) => check.status === 'passed').length
  const failed = checks.length - passed
  return {
    report_kind: 'anip_local_conformance_report',
    generated_at: generatedAt,
    service_definition_digest: serviceDefinitionDigest,
    service_definition_digest_algorithm: params.definition.compiled_contract_identity?.signature_algorithm ?? 'sha256',
    checks,
    summary: {
      status: failed === 0 ? 'passed' : 'failed',
      passed,
      failed,
    },
  }
}

function runtimeBackendBindingsForService(
  definition: DeveloperDefinitionData,
  serviceId: string,
  participatesInDataAccess: boolean,
  participatesInIntegration: boolean,
): string[] {
  const integrationFrontingBindings = integrationFrontingBackendBindingsForService(definition, serviceId)
  const serviceBinding = definition.service_backend_bindings.find((binding) => binding.service_id === serviceId)
  if (serviceBinding) {
    const bindings: string[] = []
    if (serviceBinding.uses_data_access_backend) {
      bindings.push([
        serviceBinding.data_access_backend_type || 'unspecified',
        serviceBinding.data_access_target_label || 'unspecified',
      ].join(':'))
    }
    if (serviceBinding.uses_application_integration_backend) {
      bindings.push([
        serviceBinding.application_integration_backend_type || 'unspecified',
        serviceBinding.application_integration_system_name
          || serviceBinding.application_integration_adapter_target
          || 'unspecified',
      ].join(':'))
    }
    return Array.from(new Set([...integrationFrontingBindings, ...bindings]))
  }

  const bindings: string[] = []
  void participatesInDataAccess
  void participatesInIntegration
  return Array.from(new Set([...integrationFrontingBindings, ...bindings]))
}

export function buildExtensionManifest(definition: DeveloperDefinitionData): DeveloperExtensionPoint[] {
  const manifest: DeveloperExtensionPoint[] = [
    {
      id: 'data-access-capability-surface',
      label: 'Data Access Capability Surface',
      ownership: 'generated',
      plugin_surface: 'anip_capability_scaffold',
      rationale: 'Capability contract shape, service contract, and scenario-pack artifacts are generated directly from the compiled contract.',
    },
    {
      id: 'data-access-backend-adapter',
      label: 'Data Access Backend Adapter',
      ownership: 'generated_with_extension',
      plugin_surface: 'backend_adapter_scaffold',
      rationale: 'Studio generates the adapter scaffold and binding posture, but backend-specific query semantics and credential wiring still need handwritten completion.',
    },
    {
      id: 'application-integration-capability-surface',
      label: 'Application Integration Capability Surface',
      ownership: 'generated',
      plugin_surface: 'anip_capability_scaffold',
      rationale: 'Capability structure, scenario-pack artifacts, and contract-level governed outcomes are generated directly from the compiled contract.',
    },
    {
      id: 'application-integration-backend-adapter',
      label: 'Application Integration Backend Adapter',
      ownership: 'generated_with_extension',
      plugin_surface: 'backend_adapter_scaffold',
      rationale: 'Studio generates adapter scaffolding and backend binding intent, but backend-specific request/response mapping and runtime secrets remain implementation work.',
    },
    {
      id: 'application-integration-policy-runtime',
      label: 'Application Integration Policy Runtime',
      ownership: 'generated_with_extension',
      plugin_surface: 'policy_stub',
      rationale: 'Studio generates a policy stub from governance rules, but runtime enforcement glue and handwritten decision logic may still be required.',
    },
  ]
  if ((definition.generation.selected_service_ids ?? []).length > 1) {
    manifest.push({
      id: 'cross-service-composition-runtime',
      label: 'Cross-Service Composition Runtime',
      ownership: 'extension_only',
      plugin_surface: 'runtime_composition',
      rationale: 'Multi-service delivery still needs explicit runtime composition and deployment wiring beyond the generated service scaffolds.',
    })
  }
  return manifest
}

export function buildGeneratedRuntimeTarget(definition: DeveloperDefinitionData): DeveloperGeneratedRuntimeTarget {
  const selectedServiceIds = [...definition.generation.selected_service_ids]
  const topologyByServiceId = new Map(
    definition.service_topology_bindings.map((binding) => [binding.service_id, binding] as const),
  )
  const capabilityByServiceId = new Map<string, DeveloperCapabilityFormalization[]>(
    selectedServiceIds.map((serviceId) => [serviceId, []] as const),
  )
  for (const capability of definition.capability_formalizations) {
    if (!capability.service_id) continue
    const bucket = capabilityByServiceId.get(capability.service_id)
    if (bucket) bucket.push(capability)
  }

  const orchestrationStepIdsByServiceId = new Map<string, string[]>(
    selectedServiceIds.map((serviceId) => [serviceId, []] as const),
  )
  for (const scenario of definition.scenario_formalizations) {
    scenario.orchestration_steps.forEach((step, index) => {
      const bucket = orchestrationStepIdsByServiceId.get(step.service_id)
      if (bucket) {
        bucket.push(`${scenario.scenario_id}:${step.id || `step-${index + 1}`}`)
      }
    })
  }

  const services: DeveloperGeneratedRuntimeService[] = selectedServiceIds.map((serviceId) => {
    const topology = topologyByServiceId.get(serviceId)
    const capabilities = capabilityByServiceId.get(serviceId) ?? []
    const participatesInDataAccess = capabilities.some((capability) => capability.source_kind === 'data_access')
    const participatesInIntegration = capabilities.some((capability) => capability.source_kind === 'application_integration')
    const backendBindings = runtimeBackendBindingsForService(
      definition,
      serviceId,
      participatesInDataAccess,
      participatesInIntegration,
    )
    return {
      service_id: serviceId,
      service_name: topology?.service_name || topology?.source_role || humanize(serviceId),
      source_role: topology?.source_role || '',
      protocols: [...definition.generation.protocols],
      owned_concept_ids: [...(topology?.owned_concept_ids ?? [])],
      participating_scenario_ids: definition.scenario_formalizations
        .filter((scenario) => scenario.participating_service_ids.includes(serviceId))
        .map((scenario) => scenario.scenario_id),
      orchestration_step_ids: [...(orchestrationStepIdsByServiceId.get(serviceId) ?? [])],
      backend_bindings: backendBindings,
      capabilities: capabilities.map((capability) => ({
        capability_id: capability.capability_id,
        title: capability.title,
        source_kind: capability.source_kind,
        operation_type: capability.operation_type,
        side_effect_level: capability.side_effect_level,
        implementation_fit: capability.implementation_fit,
        business_effects: capability.business_effects,
        backend_operation: capability.backend_operation,
        path_template: capability.path_template,
        output_shape: capability.output_shape,
      })),
    }
  })

  return {
    system_name: definition.identity.system_name,
    domain_name: definition.identity.domain_name,
    delivery_model: definition.identity.delivery_model,
    architecture_shape: definition.identity.architecture_shape,
    service_generation_mode: definition.generation.service_generation_mode,
    protocols: [...definition.generation.protocols],
    services,
    required_behavior_tokens: Array.from(new Set(
      definition.scenario_formalizations.flatMap((scenario) => scenario.required_behaviors),
    )).sort(),
    required_anip_support_tokens: Array.from(new Set(
      definition.scenario_formalizations.flatMap((scenario) => scenario.required_anip_support),
    )).sort(),
    extension_point_ids: buildExtensionManifest(definition).map((entry) => entry.id),
  }
}

export function resolveCompiledContractAlignment(
  current: DeveloperCompiledContractIdentity | null | undefined,
  observed: DeveloperCompiledContractIdentity | null | undefined,
): {
  status: CompiledContractAlignmentStatus
  label: string
  detail: string
} {
  if (!current?.signature || !observed?.signature) {
    return {
      status: 'unknown',
      label: 'Unknown',
      detail: 'A saved revision signature or evaluation contract signature is missing.',
    }
  }

  if (current.signature === observed.signature) {
    return {
      status: 'aligned',
      label: 'Aligned',
      detail: 'The latest evaluation was run against the latest saved revision.',
    }
  }

  return {
    status: 'stale',
    label: 'Stale',
    detail: 'The latest evaluation was run against a different compiled contract than the latest saved revision.',
  }
}

export function resolveGenerationContractAlignment(
  current: DeveloperCompiledContractIdentity | null | undefined,
  observed: DeveloperCompiledContractIdentity | null | undefined,
): {
  status: CompiledContractAlignmentStatus
  label: string
  detail: string
} {
  if (!current?.signature || !observed?.signature) {
    return {
      status: 'unknown',
      label: 'Unknown',
      detail: 'A saved revision signature or generation-run contract signature is missing.',
    }
  }

  if (current.signature === observed.signature) {
    return {
      status: 'aligned',
      label: 'Aligned',
      detail: 'The latest generation run was launched from the latest saved revision.',
    }
  }

  return {
    status: 'stale',
    label: 'Stale',
    detail: 'The latest generation run was launched from a different compiled contract than the latest saved revision.',
  }
}

export function normalizeObservedMetadataSignature(value: Record<string, any> | null | undefined): string {
  if (!value) return ''
  const capabilityIds = Array.isArray(value.capabilities)
    ? value.capabilities
      .map((item: Record<string, any>) => String(item?.id || '').trim())
      .filter(Boolean)
      .sort()
    : []
  const normalized = JSON.stringify({
    service_id: value.service_id || null,
    protocol: value.protocol || null,
    profile: value.profile || null,
    source: value.source || null,
    capability_ids: capabilityIds,
  })
  return `observed:${hashObservedEvidenceKey(normalized)}`
}

function normalizeObservedMetadataSetSignature(values: Array<Record<string, any> | null | undefined>): string {
  const signatures = values
    .map((value) => normalizeObservedMetadataSignature(value))
    .filter(Boolean)
    .sort()
  if (!signatures.length) return ''
  return `observed-set:${hashObservedEvidenceKey(signatures.join('|'))}`
}

function hashObservedEvidenceKey(value: string): string {
  let hash = 2166136261
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index)
    hash = Math.imul(hash, 16777619)
  }
  return (hash >>> 0).toString(16).padStart(8, '0')
}

function normalizeObservedProtocol(protocol: string | null | undefined): string {
  return String(protocol || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '')
}

function normalizeContractProtocol(protocol: string): string {
  if (protocol === 'anip_http') return 'anip022'
  if (protocol === 'grpc') return 'grpc'
  return normalizeObservedProtocol(protocol)
}

function buildObservedServiceLabel(value: Record<string, any> | null | undefined): string {
  return String(value?.service_id || value?.base_url || 'Unknown service')
}

function buildObservedProtocolLabel(value: Record<string, any> | null | undefined): string {
  return String(value?.protocol || 'Unknown')
}

function buildObservedProfileLabel(value: Record<string, any> | null | undefined): string {
  return String(value?.profile || 'Unknown')
}

export function resolveObservedServiceEvidence(params: {
  definition: DeveloperDefinitionData | null | undefined
  currentContractIdentity: DeveloperCompiledContractIdentity | null | undefined
  generationRun: DeveloperGenerationRunData | null | undefined
  generationRunArtifactId?: string | null | undefined
  observedArtifacts: ArtifactRecord[]
  evaluationObservedEvidence?: EvaluationObservedServiceEvidenceSummary | null | undefined
  evaluationSnapshot: ObservedServiceMetadata | Record<string, any> | null | undefined
}): EvaluationObservedServiceEvidenceSummary {
  const missing = (
    detail: string,
    extras?: Partial<EvaluationObservedServiceEvidenceSummary>,
  ): EvaluationObservedServiceEvidenceSummary => ({
    status: 'missing',
    label: 'Missing',
    detail,
    signature: '',
    artifactId: null,
    generationRunArtifactId: null,
    generationDependencySource: null,
    service: 'No observed service metadata',
    protocol: 'Unknown',
    profile: 'Unknown',
    capabilityCount: 0,
    source: 'No observed metadata source',
    expectedServices: [],
    expectedProtocols: [],
    alignedCapabilities: [],
    missingCapabilities: [],
    extraCapabilities: [],
    ...extras,
  })
  const stale = (
    detail: string,
    extras?: Partial<EvaluationObservedServiceEvidenceSummary>,
  ): EvaluationObservedServiceEvidenceSummary => ({
    status: 'stale',
    label: 'Stale',
    detail,
    signature: '',
    artifactId: null,
    generationRunArtifactId: null,
    generationDependencySource: null,
    service: 'Unknown service',
    protocol: 'Unknown',
    profile: 'Unknown',
    capabilityCount: 0,
    source: 'Observed service metadata artifact',
    expectedServices: [],
    expectedProtocols: [],
    alignedCapabilities: [],
    missingCapabilities: [],
    extraCapabilities: [],
    ...extras,
  })
  const ready = (
    detail: string,
    extras?: Partial<EvaluationObservedServiceEvidenceSummary>,
  ): EvaluationObservedServiceEvidenceSummary => ({
    status: 'ready',
    label: 'Ready',
    detail,
    signature: '',
    artifactId: null,
    generationRunArtifactId: null,
    generationDependencySource: null,
    service: 'Unknown service',
    protocol: 'Unknown',
    profile: 'Unknown',
    capabilityCount: 0,
    source: 'Observed service metadata artifact',
    expectedServices: [],
    expectedProtocols: [],
    alignedCapabilities: [],
    missingCapabilities: [],
    extraCapabilities: [],
    ...extras,
  })

  const observedArtifacts = [...(params.observedArtifacts ?? [])]
  observedArtifacts.sort((a, b) => new Date(b.updated_at || b.created_at).getTime() - new Date(a.updated_at || a.created_at).getTime())
  const latestArtifact = observedArtifacts[0] ?? null
  const observedRecords = observedArtifacts
    .map((artifact) => (artifact.data as Record<string, any> | undefined) ?? null)
    .filter((value): value is Record<string, any> => Boolean(value))
  const latestObserved = observedRecords[0] ?? null
  const evaluationSnapshot = (params.evaluationSnapshot as Record<string, any> | undefined) ?? null
  const evaluationObservedEvidence = params.evaluationObservedEvidence ?? null
  const observedSignature = normalizeObservedMetadataSetSignature(observedRecords)
  const snapshotSignature = evaluationObservedEvidence?.signature || normalizeObservedMetadataSignature(evaluationSnapshot)

  if (!latestObserved && !evaluationSnapshot) {
    return missing('No observed service metadata is currently saved or attached to evaluation evidence.')
  }

  const currentContract = params.currentContractIdentity ?? null
  const definition = params.definition ?? null
  const observedForFallback = latestObserved || evaluationSnapshot
  const observedServiceIds = [
    ...new Set(
      observedRecords
        .map((value) => String(value?.service_id || '').trim())
        .filter(Boolean),
    ),
  ]
  const observedProtocols = [
    ...new Set(
      observedRecords
        .map((value) => String(value?.protocol || '').trim())
        .filter(Boolean),
    ),
  ]
  const observedProfiles = [
    ...new Set(
      observedRecords
        .map((value) => String(value?.profile || '').trim())
        .filter(Boolean),
    ),
  ]
  const observedCapabilities = [
    ...new Set(
      observedRecords.flatMap((value) =>
        Array.isArray(value.capabilities)
          ? value.capabilities
            .map((item: Record<string, any>) => String(item?.id || '').trim())
            .filter(Boolean)
          : [],
      ),
    ),
  ]
  const observedGenerationRunIds = [
    ...new Set(
      observedRecords
        .map((value) => String(value?.generation_run_artifact_id || '').trim())
        .filter(Boolean),
    ),
  ]
  const observedDependencySources = [
    ...new Set(
      observedRecords
        .map((value) => {
          const source = String(value?.generation_dependency_source || '').trim()
          return source === 'local' || source === 'registry' ? source : ''
        })
        .filter(Boolean),
    ),
  ] as Array<'local' | 'registry'>
  const observedServiceLabel = observedServiceIds.length
    ? observedServiceIds.join(', ')
    : buildObservedServiceLabel(observedForFallback)
  const observedProtocolLabel = observedProtocols.length
    ? observedProtocols.join(', ')
    : buildObservedProtocolLabel(observedForFallback)
  const observedProfileLabel = observedProfiles.length
    ? observedProfiles.join(', ')
    : buildObservedProfileLabel(observedForFallback)
  const observedSourceLabel = observedArtifacts.length > 1
    ? `${observedArtifacts.length} observed service metadata artifacts`
    : latestArtifact?.title || (evaluationSnapshot ? 'Saved evaluation snapshot' : 'No observed metadata source')
  const observedArtifactId = observedArtifacts.length === 1
    ? latestArtifact?.id ?? null
    : observedArtifacts.length > 1
      ? `observed-service-set:${observedArtifacts.length}`
      : evaluationObservedEvidence?.artifactId ?? null
  const currentGenerationRunArtifactId = String(params.generationRunArtifactId || '').trim() || null
  const currentGenerationDependencySource = params.generationRun?.generator_inputs?.dependency_source ?? null
  const observedGenerationRunArtifactId = observedGenerationRunIds.length === 1
    ? observedGenerationRunIds[0]
    : observedGenerationRunIds.length > 1
      ? `generation-run-set:${observedGenerationRunIds.length}`
      : evaluationObservedEvidence?.generationRunArtifactId
        ?? (String(evaluationSnapshot?.generation_run_artifact_id || '').trim() || null)
  const observedGenerationDependencySource = observedDependencySources.length === 1
    ? observedDependencySources[0]
    : evaluationObservedEvidence?.generationDependencySource
      ?? (() => {
        const source = String(evaluationSnapshot?.generation_dependency_source || '').trim()
        return source === 'local' || source === 'registry' ? source as 'local' | 'registry' : null
      })()
  if (!currentContract?.signature || !definition) {
    return missing('No saved revision exists yet, so observed service evidence cannot be aligned to delivery truth.', {
      signature: observedSignature || snapshotSignature,
      artifactId: observedArtifactId,
      generationRunArtifactId: observedGenerationRunArtifactId,
      generationDependencySource: observedGenerationDependencySource,
      service: observedServiceLabel,
      protocol: observedProtocolLabel,
      profile: observedProfileLabel,
      capabilityCount: observedCapabilities.length,
      source: observedSourceLabel,
    })
  }

  const generationRun = params.generationRun ?? null
  const generationAlignment = resolveGenerationContractAlignment(currentContract, generationRun?.compiled_contract_identity)
  const generatedOutputCount = generationRun?.outputs.runtime_target.length ?? 0
  if (!generationRun || generationAlignment.status === 'unknown') {
    return missing('Observed service evidence cannot be validated against generated output yet because no aligned generation run exists for the latest saved revision.', {
      signature: observedSignature || snapshotSignature,
      artifactId: observedArtifacts.length === 1 ? latestArtifact?.id ?? null : null,
      generationRunArtifactId: observedGenerationRunArtifactId,
      generationDependencySource: observedGenerationDependencySource,
      service: observedServiceLabel,
      protocol: observedProtocolLabel,
      profile: observedProfileLabel,
      capabilityCount: observedCapabilities.length,
      source: observedSourceLabel,
    })
  }
  if (generationAlignment.status === 'stale' || generatedOutputCount === 0) {
    return stale(
      generationAlignment.status === 'stale'
        ? 'Observed service evidence is newer than the latest aligned generation output. Regenerate from the latest saved revision before treating runtime metadata as aligned.'
        : 'An aligned generation run exists, but it did not save any generated outputs. Observed service evidence cannot be normalized against generated delivery artifacts yet.',
      {
        signature: observedSignature || snapshotSignature,
        artifactId: observedArtifactId,
        generationRunArtifactId: observedGenerationRunArtifactId,
        generationDependencySource: observedGenerationDependencySource,
        service: observedServiceLabel,
        protocol: observedProtocolLabel,
        profile: observedProfileLabel,
        capabilityCount: observedCapabilities.length,
        source: observedSourceLabel,
      },
    )
  }

  const expectedServices = [
    ...new Set(
      (definition.generation.selected_service_ids.length
        ? definition.generation.selected_service_ids
        : definition.service_topology_bindings.map((item) => item.service_id))
        .filter(Boolean),
    ),
  ]
  const expectedProtocols = [
    ...new Set(
      (definition.generation.protocols ?? [])
        .map((item) => normalizeContractProtocol(item))
        .filter(Boolean),
    ),
  ]

  const intendedCapabilities = [
    ...new Set(
      definition.capability_formalizations
        .filter((item) => !expectedServices.length || expectedServices.includes(item.service_id))
        .map((item) => String(item.capability_id || '').trim())
        .filter(Boolean),
    ),
  ]
  const alignedCapabilities = observedCapabilities.filter((item) => intendedCapabilities.includes(item))
  const missingCapabilities = intendedCapabilities.filter((item) => !observedCapabilities.includes(item))
  const extraCapabilities = observedCapabilities.filter((item) => !intendedCapabilities.includes(item))

  const snapshotAligned = snapshotSignature ? observedSignature === snapshotSignature : true
  const generationRunAligned = !currentGenerationRunArtifactId
    || !observedGenerationRunIds.length
    || observedGenerationRunIds.includes(currentGenerationRunArtifactId)
  const dependencySourceAligned = !currentGenerationDependencySource
    || !observedDependencySources.length
    || observedDependencySources.includes(currentGenerationDependencySource)
  const normalizedObservedProtocols = observedProtocols
    .map((value) => normalizeObservedProtocol(value))
    .filter(Boolean)
  const missingServices = expectedServices.filter((item) => !observedServiceIds.includes(item))
  const extraServices = observedServiceIds.filter((item) => !expectedServices.includes(item))
  const protocolAligned = !normalizedObservedProtocols.length
    || !expectedProtocols.length
    || normalizedObservedProtocols.every((item) => expectedProtocols.includes(item))

  const detailParts: string[] = []
  if (!snapshotAligned) {
    detailParts.push('Current observed service evidence differs from the observed-service evidence attached to the latest saved evaluation.')
  }
  if (!generationRunAligned && currentGenerationRunArtifactId) {
    detailParts.push(`Current observed service evidence was captured against a different generation run (${observedGenerationRunArtifactId || 'unknown'}) than the latest saved run (${currentGenerationRunArtifactId}).`)
  }
  if (!dependencySourceAligned && currentGenerationDependencySource) {
    detailParts.push(`Current observed service evidence was captured against ${observedGenerationDependencySource || 'unknown'} dependency mode, not the latest saved generation mode (${currentGenerationDependencySource}).`)
  }
  if (missingServices.length) {
    detailParts.push(`Missing observed services for compiled contract: ${missingServices.join(', ')}.`)
  }
  if (extraServices.length) {
    detailParts.push(`Observed services outside the compiled contract service set: ${extraServices.join(', ')}.`)
  }
  if (!protocolAligned) {
    detailParts.push(`Observed protocols ${observedProtocolLabel} do not match the generated contract protocol set (${expectedProtocols.join(', ') || 'none defined'}).`)
  }
  if (missingCapabilities.length) {
    detailParts.push(`Missing intended capabilities: ${missingCapabilities.join(', ')}.`)
  }
  if (extraCapabilities.length) {
    detailParts.push(`Observed capabilities broader than intended: ${extraCapabilities.join(', ')}.`)
  }

  const summary = {
    signature: observedSignature || snapshotSignature,
    artifactId: observedArtifactId,
    generationRunArtifactId: observedGenerationRunArtifactId,
    generationDependencySource: observedGenerationDependencySource,
    service: observedServiceLabel,
    protocol: observedProtocolLabel,
    profile: observedProfileLabel,
    capabilityCount: observedCapabilities.length,
    source: observedSourceLabel,
    expectedServices,
    expectedProtocols,
    alignedCapabilities,
    missingCapabilities,
    extraCapabilities,
  }

  if (detailParts.length) {
    return stale(detailParts.join(' '), summary)
  }

  return ready(
    'Observed service metadata is aligned to the latest saved revision, the latest aligned generation outputs, and the latest saved evaluation evidence when present.',
    summary,
  )
}

export function resolveDeveloperDefinitionLinks(values: string[]): string[] {
  const migrated = new Set<string>()
  values.forEach((value) => {
    if (value === 'data_access_design') {
      DATA_ACCESS_DEFINITION_SECTIONS.forEach((section) => migrated.add(section))
      return
    }
    if (value === 'application_integration') {
      APPLICATION_INTEGRATION_DEFINITION_SECTIONS.forEach((section) => migrated.add(section))
      return
    }
    if (value === 'observed_services' || value === 'verification') {
      migrated.add('audit_and_lineage')
      return
    }
    if (value === 'product_handoff') {
      migrated.add('service_identity_topology')
      return
    }
    migrated.add(value)
  })
  return [...migrated]
}

export function inferAutomaticCoverageMapping(
  item: TraceabilityCoverageItem,
): { linked_surfaces: string[]; note: string; target_key: string; target_label: string } | null {
  if (item.source === 'integration_fronting') {
    return {
      linked_surfaces: item.linked_surfaces.length
        ? resolveDeveloperDefinitionLinks(item.linked_surfaces)
        : [
            'capability_contracts',
            'authority_and_approval',
            'backend_bindings',
            'audit_and_lineage',
            'generation_and_extensions',
          ],
      note: item.mapping_note || 'Accepted integration-fronting mappings are compiled into the Developer Definition as governed backend-facing capability mappings.',
      target_key: item.mapping_target_key ?? `developer_definition.integration_fronting:${item.label}`,
      target_label: item.mapping_target_label ?? 'Developer Design > Govern API / MCP > Accepted Governed Mapping',
    }
  }
  const requirementId = item.id.startsWith('requirements:')
    ? item.id.replace('requirements:', '')
    : null
  const businessGoalMatch = item.id.match(/^product_summary:business_goal:(\d+)$/)
  if (businessGoalMatch) {
    const [, index] = businessGoalMatch
    return {
      linked_surfaces: ['execution_semantics'],
      note: 'This business goal must be formalized explicitly in Evidence & Verification Plan so delivery and runtime evidence can prove the implementation stayed aligned to business intent.',
      target_key: `developer_definition.verification.business_goal:${index}`,
      target_label: 'Developer Design > Evidence & Verification Plan > Business Goal Coverage',
    }
  }
  const questionFamilyMatch = item.id.match(/^product_summary:supported_question_family:(\d+)$/)
  if (questionFamilyMatch) {
    const [, index] = questionFamilyMatch
    return {
      linked_surfaces: ['capability_contracts'],
      note: 'This supported question family must be formalized explicitly in Evidence & Verification Plan so the generated capability surface and evidence can prove the family is still supported.',
      target_key: `developer_definition.verification.supported_question_family:${index}`,
      target_label: 'Developer Design > Evidence & Verification Plan > Supported Question Families',
    }
  }
  const compositionRuleMatch = item.id.match(/^product_summary:multi_step_composition_rule:(\d+)$/)
  if (compositionRuleMatch) {
    const [, index] = compositionRuleMatch
    return {
      linked_surfaces: ['scenario_context'],
      note: 'This compound workflow rule must be formalized explicitly so scenario orchestration stays aligned to the PM-level composition boundary.',
      target_key: `developer_definition.composition_rule:${index}`,
      target_label: 'Developer Design > Scenario Execution Semantics > Compound Workflow Rules',
    }
  }
  if (item.id === 'product_summary:approval_posture_summary') {
    return {
      linked_surfaces: ['authority_and_approval'],
      note: 'This PM approval posture is formalized explicitly in Product Intent Formalization on the Service Formalization page.',
      target_key: 'developer_definition.product_alignment.approval_posture_formalization',
      target_label: 'Developer Design > Service Formalization > Product Intent Formalization > Approval Posture Summary',
    }
  }
  if (item.id === 'product_summary:governed_behavior_summary') {
    return {
      linked_surfaces: ['execution_semantics'],
      note: 'This PM governed behavior summary is formalized explicitly in Product Intent Formalization on the Service Formalization page.',
      target_key: 'developer_definition.product_alignment.governed_behavior_formalization',
      target_label: 'Developer Design > Service Formalization > Product Intent Formalization > Governed Behavior Summary',
    }
  }
  const actorSummaryMatch = item.id.match(/^actor_model:actor:([^:]+):summary$/)
  if (actorSummaryMatch) {
    const [, actorKey] = actorSummaryMatch
    return {
      linked_surfaces: ['service_identity_topology'],
      note: 'This actor summary is formalized explicitly in the Actor Expectations block on the Service Formalization page.',
      target_key: `developer_definition.actor_expectation:${actorKey}:summary_formalization`,
      target_label: 'Developer Design > Service Formalization > Actor Expectations > Actor Summary Formalization',
    }
  }
  if (item.id.startsWith('actor_model:') && item.id.endsWith(':approval_expectations')) {
    const actorApprovalMatch = item.id.match(/^actor_model:actor:([^:]+):approval_expectations$/)
    const actorKey = actorApprovalMatch?.[1]
    return {
      linked_surfaces: ['authority_and_approval'],
      note: 'Actor-specific approval expectations are formalized explicitly in the Actor Expectations block on the Service Formalization page.',
      target_key: `developer_definition.actor_expectation:${actorKey}:approval_formalization`,
      target_label: 'Developer Design > Service Formalization > Actor Expectations > Approval Formalization',
    }
  }
  const actorVisibilityMatch = item.id.match(/^actor_model:actor:([^:]+):visibility_expectations$/)
  if (actorVisibilityMatch) {
    const [, actorKey] = actorVisibilityMatch
    return {
      linked_surfaces: ['service_identity_topology'],
      note: 'This actor visibility expectation must be formalized explicitly on the Service Formalization page so service exposure and result shaping preserve the intended audience boundary.',
      target_key: `developer_definition.actor_expectation:${actorKey}:visibility_formalization`,
      target_label: 'Developer Design > Service Formalization > Actor Expectations > Visibility Formalization',
    }
  }
  const actorActionMatch = item.id.match(/^actor_model:actor:([^:]+):action_expectations$/)
  if (actorActionMatch) {
    const [, actorKey] = actorActionMatch
    return {
      linked_surfaces: ['capability_contracts'],
      note: 'This actor action expectation must be formalized explicitly on the Service Formalization page so capability boundaries and bounded actions preserve the intended actor posture.',
      target_key: `developer_definition.actor_expectation:${actorKey}:action_formalization`,
      target_label: 'Developer Design > Service Formalization > Actor Expectations > Action Formalization',
    }
  }
  if (item.id.startsWith('permission_intent:rule:')) {
    const permissionRuleMatch = item.id.match(/^permission_intent:rule:(\d+)$/)
    const ruleIndex = permissionRuleMatch?.[1]
    return {
      linked_surfaces: ['authority_and_approval'],
      note: 'Permission-intent rules are formalized explicitly in the Permission Intent Bindings block on the Service Formalization page.',
      target_key: `developer_definition.permission_rule:${ruleIndex}`,
      target_label: 'Developer Design > Service Formalization > Permission Intent Bindings > Rule Formalization',
    }
  }
  const nonGoalMatch = item.id.match(/^non_goals:entry:(\d+)$/)
  if (nonGoalMatch) {
    const [, index] = nonGoalMatch
    return {
      linked_surfaces: ['execution_semantics'],
      note: 'This non-goal needs an explicit verification guard so generated and implemented behavior can be checked against scope boundaries.',
      target_key: `developer_definition.verification.non_goal:${index}`,
      target_label: 'Developer Design > Evidence & Verification Plan > Non-Goal Guards',
    }
  }
  const successCriteriaMatch = item.id.match(/^success_criteria:entry:(\d+)$/)
  if (successCriteriaMatch) {
    const [, index] = successCriteriaMatch
    return {
      linked_surfaces: ['audit_and_lineage'],
      note: 'This success criterion needs an explicit evidence and verification strategy so PM signoff has a concrete delivery signal to review.',
      target_key: `developer_definition.verification.success_criteria:${index}`,
      target_label: 'Developer Design > Evidence & Verification Plan > Success Criteria Evidence',
    }
  }
  if (requirementId) {
    if (requirementId === 'system-name') {
      return {
        linked_surfaces: ['service_identity_topology'],
        note: 'This PM input is formalized by the explicit System Name field on the Service Formalization page.',
        target_key: 'developer_definition.identity.system_name',
        target_label: 'Developer Design > Service Formalization > Identity & Delivery > System Name',
      }
    }
    if (requirementId === 'system-domain') {
      return {
        linked_surfaces: ['service_identity_topology'],
        note: 'This PM input is formalized by the explicit Domain field on the Service Formalization page.',
        target_key: 'developer_definition.identity.domain_name',
        target_label: 'Developer Design > Service Formalization > Identity & Delivery > Domain',
      }
    }
    if (requirementId === 'deployment-intent') {
      return {
        linked_surfaces: ['service_identity_topology'],
        note: 'This PM input is formalized by the explicit Delivery Model field on the Service Formalization page.',
        target_key: 'developer_definition.identity.delivery_model',
        target_label: 'Developer Design > Service Formalization > Identity & Delivery > Delivery Model',
      }
    }
    if (requirementId === 'scale-shape') {
      return {
        linked_surfaces: ['service_identity_topology'],
        note: 'This PM input is formalized by the explicit Architecture Shape field on the Service Formalization page.',
        target_key: 'developer_definition.identity.architecture_shape',
        target_label: 'Developer Design > Service Formalization > Identity & Delivery > Architecture Shape',
      }
    }
    if (requirementId === 'high-availability') {
      return {
        linked_surfaces: ['service_identity_topology'],
        note: 'This PM input is formalized by the explicit High Availability field on the Service Formalization page.',
        target_key: 'developer_definition.identity.high_availability_required',
        target_label: 'Developer Design > Service Formalization > Identity & Delivery > High Availability',
      }
    }
    if ([
      'trust-mode',
      'trust-checkpoints',
      'has-spending',
      'has-irreversible',
      'cost-visibility',
      'preflight-discovery',
      'grantable-restrictions',
      'restricted-vs-denied',
      'delegation-tokens',
      'scoped-authority',
      'purpose-binding',
      'approval-expectation',
      'recovery-sensitive',
      'blocked-failure-expectation',
    ].includes(requirementId)) {
      const authorityTargets: Record<string, { key: string; label: string }> = {
        'trust-mode': {
          key: 'developer_definition.authority.trust_mode',
          label: 'Developer Design > Service Formalization > Authority & Approval > Trust Mode',
        },
        'trust-checkpoints': {
          key: 'developer_definition.authority.trust_checkpoints_required',
          label: 'Developer Design > Service Formalization > Authority & Approval > Trust Checkpoints Required',
        },
        'has-spending': {
          key: 'developer_definition.authority.spending_actions_present',
          label: 'Developer Design > Service Formalization > Authority & Approval > Spending Actions Present',
        },
        'has-irreversible': {
          key: 'developer_definition.authority.irreversible_actions_present',
          label: 'Developer Design > Service Formalization > Authority & Approval > Irreversible Actions Present',
        },
        'cost-visibility': {
          key: 'developer_definition.authority.cost_visibility_required',
          label: 'Developer Design > Service Formalization > Authority & Approval > Cost Visibility Required',
        },
        'preflight-discovery': {
          key: 'developer_definition.authority.preflight_authority_discovery',
          label: 'Developer Design > Service Formalization > Authority & Approval > Preflight Authority Discovery',
        },
        'grantable-restrictions': {
          key: 'developer_definition.authority.grantable_restrictions',
          label: 'Developer Design > Service Formalization > Authority & Approval > Grantable Restrictions',
        },
        'restricted-vs-denied': {
          key: 'developer_definition.authority.restricted_vs_denied',
          label: 'Developer Design > Service Formalization > Authority & Approval > Restricted vs Denied',
        },
        'delegation-tokens': {
          key: 'developer_definition.authority.delegation_tokens',
          label: 'Developer Design > Service Formalization > Authority & Approval > Delegation Tokens',
        },
        'scoped-authority': {
          key: 'developer_definition.authority.scoped_authority',
          label: 'Developer Design > Service Formalization > Authority & Approval > Scoped Authority',
        },
        'purpose-binding': {
          key: 'developer_definition.authority.purpose_binding',
          label: 'Developer Design > Service Formalization > Authority & Approval > Purpose Binding',
        },
        'approval-expectation': {
          key: 'developer_definition.authority.approval_expectation',
          label: 'Developer Design > Service Formalization > Authority & Approval > Approval Expectation',
        },
        'recovery-sensitive': {
          key: 'developer_definition.authority.recovery_sensitive',
          label: 'Developer Design > Service Formalization > Authority & Approval > Recovery Sensitive',
        },
        'blocked-failure-expectation': {
          key: 'developer_definition.authority.blocked_failure_posture',
          label: 'Developer Design > Service Formalization > Authority & Approval > Blocked or Failed Work Posture',
        },
      }
      const target = authorityTargets[requirementId]
      return {
        linked_surfaces: ['authority_and_approval'],
        note: 'This PM input is formalized by an explicit field in the Authority & Approval block on the Service Formalization page.',
        target_key: target.key,
        target_label: target.label,
      }
    }
    if ([
      'needs-audit',
      'needs-searchable',
      'invocation-tracking',
      'task-tracking',
      'parent-tracking',
      'client-reference',
    ].includes(requirementId)) {
      const auditTargets: Record<string, { key: string; label: string }> = {
        'needs-audit': {
          key: 'developer_definition.audit.durable_records_required',
          label: 'Developer Design > Service Formalization > Audit & Lineage > Durable Records Required',
        },
        'needs-searchable': {
          key: 'developer_definition.audit.searchable_history_required',
          label: 'Developer Design > Service Formalization > Audit & Lineage > Searchable History Required',
        },
        'invocation-tracking': {
          key: 'developer_definition.audit.invocation_tracking',
          label: 'Developer Design > Service Formalization > Audit & Lineage > Invocation Tracking',
        },
        'task-tracking': {
          key: 'developer_definition.audit.task_tracking',
          label: 'Developer Design > Service Formalization > Audit & Lineage > Task Tracking',
        },
        'parent-tracking': {
          key: 'developer_definition.audit.parent_invocation_tracking',
          label: 'Developer Design > Service Formalization > Audit & Lineage > Parent Invocation Tracking',
        },
        'client-reference': {
          key: 'developer_definition.audit.client_reference_ids',
          label: 'Developer Design > Service Formalization > Audit & Lineage > Client Reference IDs',
        },
      }
      const target = auditTargets[requirementId]
      return {
        linked_surfaces: ['audit_and_lineage'],
        note: 'This PM input is formalized by an explicit field in the Audit & Lineage block on the Service Formalization page.',
        target_key: target.key,
        target_label: target.label,
      }
    }
    if ([
      'service-handoffs',
      'cross-service-reconstruction',
      'cross-service-continuity',
    ].includes(requirementId)) {
      const topologyTargets: Record<string, { key: string; label: string }> = {
        'service-handoffs': {
          key: 'developer_definition.audit.service_handoffs_required',
          label: 'Developer Design > Service Formalization > Audit & Lineage > Service Handoffs Required',
        },
        'cross-service-reconstruction': {
          key: 'developer_definition.audit.cross_service_reconstruction_required',
          label: 'Developer Design > Service Formalization > Audit & Lineage > Cross-Service Reconstruction Required',
        },
        'cross-service-continuity': {
          key: 'developer_definition.audit.cross_service_continuity_required',
          label: 'Developer Design > Service Formalization > Audit & Lineage > Cross-Service Continuity Required',
        },
      }
      const target = topologyTargets[requirementId]
      return {
        linked_surfaces: ['audit_and_lineage'],
        note: 'This PM input is formalized by an explicit field in the Audit & Lineage block on the Service Formalization page.',
        target_key: target.key,
        target_label: target.label,
      }
    }
  }

  if (item.id.startsWith('shape:service:')) {
    const serviceId = item.id.replace('shape:service:', '')
    return {
      linked_surfaces: ['service_identity_topology'],
      note: 'This service boundary is formalized explicitly in the Service Topology Bindings block on the Service Formalization page.',
      target_key: `developer_definition.service_topology:${serviceId}`,
      target_label: 'Developer Design > Service Formalization > Service Topology Bindings',
    }
  }

  if (item.id.startsWith('shape:coordination:')) {
    return {
      linked_surfaces: ['service_identity_topology', 'execution_semantics', 'audit_and_lineage'],
      note: 'This service-to-service relationship is covered by explicit service topology plus service handoff, cross-service continuity, and scenario execution semantics. It must not silently become hidden app glue.',
      target_key: `developer_definition.service_coordination:${item.id}`,
      target_label: 'Developer Design > Service Formalization / Scenario Execution Semantics > Service Coordination Coverage',
    }
  }

  if (item.id.startsWith('shape:concept:')) {
    return {
      linked_surfaces: ['data_contracts'],
      note: 'This domain concept is formalized explicitly in the Domain Concept Bindings block on the Data Contract Formalization page.',
      target_key: `developer_definition.domain_concept:${item.id.replace('shape:concept:', '')}`,
      target_label: 'Developer Design > Data Contract Formalization > Domain Concept Bindings',
    }
  }

  const scenarioQuestionMatch = item.id.match(/^scenario:([^:]+):(context-[^:]+)$/)
  const scenarioId = scenarioQuestionMatch?.[1] ?? null
  const scenarioQuestionId = scenarioQuestionMatch?.[2] ?? null
  if (scenarioQuestionId) {
    if (scenarioQuestionId === 'context-capability' && scenarioId) {
      return {
        linked_surfaces: ['scenario_context', 'capability_contracts'],
        note: 'This scenario capability must be formalized explicitly in the per-scenario developer definition, not inferred from PM narrative.',
        target_key: `developer_definition.scenario_formalization:${scenarioId}:primary_capability`,
        target_label: 'Developer Design > Scenario Coverage Intent > Primary Capability',
      }
    }
    const scenarioFieldTargets: Record<string, { linked: string[]; field: string; label: string; note: string }> = {
      'context-side-effect': {
        linked: ['authority_and_approval'],
        field: 'side_effect_formalization',
        label: 'Developer Design > Scenario Coverage Intent > Side-Effect Formalization',
        note: 'This scenario side-effect posture is formalized explicitly on the scenario entry.',
      },
      'context-expected-cost': {
        linked: ['authority_and_approval'],
        field: 'expected_cost_formalization',
        label: 'Developer Design > Scenario Coverage Intent > Expected Cost Formalization',
        note: 'This scenario cost posture is formalized explicitly on the scenario entry.',
      },
      'context-budget-limit': {
        linked: ['authority_and_approval'],
        field: 'budget_guard_formalization',
        label: 'Developer Design > Scenario Coverage Intent > Budget Guard Formalization',
        note: 'This scenario budget limit is formalized explicitly on the scenario entry.',
      },
      'context-permissions': {
        linked: ['authority_and_approval'],
        field: 'permission_formalization',
        label: 'Developer Design > Scenario Coverage Intent > Permission Formalization',
        note: 'This scenario permission posture is formalized explicitly on the scenario entry.',
      },
      'context-task-id': {
        linked: ['audit_and_lineage'],
        field: 'task_tracking_formalization',
        label: 'Developer Design > Scenario Coverage Intent > Task Tracking Formalization',
        note: 'This scenario task-tracking expectation is formalized explicitly on the scenario entry.',
      },
    }
    const target = scenarioFieldTargets[scenarioQuestionId]
    if (target && scenarioId) {
      return {
        linked_surfaces: target.linked,
        note: target.note,
        target_key: `developer_definition.scenario_formalization:${scenarioId}:${target.field}`,
        target_label: target.label,
      }
    }
  }

  const expectedSupportMatch = item.id.match(/^scenario:([^:]+):expected_anip_support:(.+)$/)
  if (expectedSupportMatch) {
    const [, scenarioId, supportId] = expectedSupportMatch
    return {
      linked_surfaces: ['execution_semantics'],
      note: 'This expected ANIP support item must be formalized explicitly on the scenario entry that generation will use.',
      target_key: `developer_definition.scenario_formalization:${scenarioId}:required_anip_support:${supportId}`,
      target_label: `Developer Design > Scenario Execution Semantics > Required ANIP Support: ${humanize(supportId)}`,
    }
  }

  const expectedBehaviorMatch = item.id.match(/^scenario:([^:]+):expected_behavior:(.+)$/)
  if (expectedBehaviorMatch) {
    const [, scenarioId, behaviorId] = expectedBehaviorMatch
    return {
      linked_surfaces: ['execution_semantics'],
      note: 'This expected scenario behavior must be formalized explicitly on the scenario entry that generation will use.',
      target_key: `developer_definition.scenario_formalization:${scenarioId}:required_behaviors:${behaviorId}`,
      target_label: `Developer Design > Scenario Execution Semantics > Required Behavior: ${humanize(behaviorId)}`,
    }
  }

  return null
}

function inferDefaultDeliveryModel(shape: ShapeRecord | null): DeveloperDeliveryModel {
  const shapeData = ((shape?.data?.shape ?? shape?.data) as Record<string, any> | undefined) ?? {}
  const services = Array.isArray(shapeData.services) ? shapeData.services : []
  return services.length > 1 ? 'multiple_coordinated_services' : 'standalone_service'
}

function inferDefaultArchitectureShape(shape: ShapeRecord | null): DeveloperArchitectureShape {
  const shapeData = ((shape?.data?.shape ?? shape?.data) as Record<string, any> | undefined) ?? {}
  const services = Array.isArray(shapeData.services) ? shapeData.services : []
  return services.length > 1 ? 'multi_service_estate' : 'single_service'
}

function shapeHasCoordination(shape: ShapeRecord | null): boolean {
  const shapeData = ((shape?.data?.shape ?? shape?.data) as Record<string, any> | undefined) ?? {}
  return Array.isArray(shapeData.coordination) && shapeData.coordination.length > 0
}

export function shapeDeclaresSourceCapabilityInventory(shape: ShapeRecord | null): boolean {
  const shapeData = ((shape?.data?.shape ?? shape?.data) as Record<string, any> | undefined) ?? {}
  const services = Array.isArray(shapeData.services) ? shapeData.services : []
  if (services.length === 0) return false
  const capabilityIds = services.flatMap((service: Record<string, any>) =>
    Array.isArray(service.capabilities)
      ? service.capabilities.map((value: unknown) => String(value).trim()).filter(Boolean)
      : [],
  )
  if (capabilityIds.length === 0) return false
  const notes = Array.isArray(shapeData.notes)
    ? shapeData.notes.map((value: unknown) => String(value).toLowerCase()).join(' ')
    : ''
  return (
    /\bsource[- ]declared\b/.test(notes)
    || /\bcanonical\b/.test(notes)
    || (/\bpreserv/.test(notes) && /\bcapabilit/.test(notes))
    || (/\bpreserv/.test(notes) && /\bsource\b/.test(notes) && /\bservice boundaries\b/.test(notes))
  )
}

function findScenarioFormalization(
  definition: DeveloperDefinitionData | null,
  scenarioId: string,
): DeveloperScenarioFormalization | null {
  return definition?.scenario_formalizations.find((item) => item.scenario_id === scenarioId) ?? null
}

function scenarioFieldAnchor(scenarioId: string, field: string): string {
  return `scenario-formalization-${scenarioId}-${field}`.replace(/[^a-zA-Z0-9_-]+/g, '-')
}

function hasVerificationTargetServices(serviceIds: string[]): boolean {
  return serviceIds.some((value) => value.trim().length > 0)
}

export function developerDefinitionTargetRoute(projectId: string, targetKey: string): string {
  const definitionBase = `/design/projects/${projectId}/developer/definition`
  const serviceBase = `/design/projects/${projectId}/developer/service-formalization`
  const governanceBase = `/design/projects/${projectId}/developer/governance-bindings`
  const auditBase = `/design/projects/${projectId}/developer/audit-lineage`
  const scenarioBase = `/design/projects/${projectId}/developer/scenario-formalization`
  const scenarioExecutionBase = `/design/projects/${projectId}/developer/scenario-execution-semantics`
  const generationBase = `/design/projects/${projectId}/developer/generation-settings`
  const verificationBase = `/design/projects/${projectId}/developer/verification-expectations`
  const dataContractBase = `/design/projects/${projectId}/developer/data-contract-formalization`
  const exactAnchors: Record<string, string> = {
    'developer_definition.product_alignment.governed_behavior_formalization': `${serviceBase}#product-intent-governed-behavior`,
    'developer_definition.product_alignment.approval_posture_formalization': `${serviceBase}#product-intent-approval-posture`,
    'developer_definition.identity.system_name': `${serviceBase}#identity-system-name`,
    'developer_definition.identity.domain_name': `${serviceBase}#identity-domain`,
    'developer_definition.identity.delivery_model': `${serviceBase}#identity-delivery-model`,
    'developer_definition.identity.architecture_shape': `${serviceBase}#identity-architecture-shape`,
    'developer_definition.identity.high_availability_required': `${serviceBase}#identity-high-availability`,
    'developer_definition.authority.trust_mode': `${serviceBase}#authority-trust-mode`,
    'developer_definition.authority.trust_checkpoints_required': `${serviceBase}#authority-trust-checkpoints`,
    'developer_definition.authority.spending_actions_present': `${serviceBase}#authority-spending-actions`,
    'developer_definition.authority.irreversible_actions_present': `${serviceBase}#authority-irreversible-actions`,
    'developer_definition.authority.cost_visibility_required': `${serviceBase}#authority-cost-visibility`,
    'developer_definition.authority.preflight_authority_discovery': `${serviceBase}#authority-preflight-discovery`,
    'developer_definition.authority.grantable_restrictions': `${serviceBase}#authority-grantable-restrictions`,
    'developer_definition.authority.restricted_vs_denied': `${serviceBase}#authority-restricted-vs-denied`,
    'developer_definition.authority.delegation_tokens': `${serviceBase}#authority-delegation-tokens`,
    'developer_definition.authority.scoped_authority': `${serviceBase}#authority-scoped-authority`,
    'developer_definition.authority.purpose_binding': `${serviceBase}#authority-purpose-binding`,
    'developer_definition.authority.approval_expectation': `${serviceBase}#authority-approval-expectation`,
    'developer_definition.authority.recovery_sensitive': `${serviceBase}#authority-recovery-sensitive`,
    'developer_definition.authority.blocked_failure_posture': `${serviceBase}#authority-blocked-failure-posture`,
    'developer_definition.audit.durable_records_required': `${auditBase}#audit-durable-records`,
    'developer_definition.audit.searchable_history_required': `${auditBase}#audit-searchable-history`,
    'developer_definition.audit.invocation_tracking': `${auditBase}#audit-invocation-tracking`,
    'developer_definition.audit.task_tracking': `${auditBase}#audit-task-tracking`,
    'developer_definition.audit.parent_invocation_tracking': `${auditBase}#audit-parent-invocation-tracking`,
    'developer_definition.audit.client_reference_ids': `${auditBase}#audit-client-reference-ids`,
    'developer_definition.audit.service_handoffs_required': `${auditBase}#audit-service-handoffs`,
    'developer_definition.audit.cross_service_reconstruction_required': `${auditBase}#audit-cross-service-reconstruction`,
    'developer_definition.audit.cross_service_continuity_required': `${auditBase}#audit-cross-service-continuity`,
  }
  if (exactAnchors[targetKey]) return exactAnchors[targetKey]
  if (targetKey.startsWith('developer_definition.product_alignment.')) return `${serviceBase}#product-intent-formalization`
  if (targetKey.startsWith('developer_definition.service_topology:')) return `${serviceBase}#service-topology-bindings`
  if (targetKey.startsWith('developer_definition.domain_concept:')) return `${dataContractBase}#domain-concept-bindings`
  if (targetKey.startsWith('developer_definition.integration_fronting:')) return `/design/projects/${projectId}/developer/integration-fronting#accepted-mappings`
  const scenarioFormalizationMatch = targetKey.match(/^developer_definition\.scenario_formalization:([^:]+):([^:]+)(?::.+)?$/)
  if (scenarioFormalizationMatch) {
    const [, scenarioId, field] = scenarioFormalizationMatch
    const executionFields = new Set(['orchestration_steps', 'required_behaviors', 'required_anip_support', 'implementation_notes'])
    const base = executionFields.has(field) ? scenarioExecutionBase : scenarioBase
    return `${base}#${scenarioFieldAnchor(scenarioId, field)}`
  }
  if (targetKey.startsWith('developer_definition.identity.')) return `${serviceBase}#identity-delivery`
  if (targetKey.startsWith('developer_definition.authority.')) return `${serviceBase}#authority-approval`
  if (targetKey.startsWith('developer_definition.audit.')) return `${auditBase}#audit-lineage`
  if (targetKey.startsWith('developer_definition.backend_bindings.')) return `${serviceBase}#service-topology-bindings`
  if (targetKey.startsWith('developer_definition.service_backend_bindings.')) return `${serviceBase}#service-topology-bindings`
  if (targetKey.startsWith('developer_definition.scenario_formalization:')) return `${scenarioBase}#scenario-context`
  if (targetKey.startsWith('developer_definition.verification.business_goal:')) return `${verificationBase}#verification-business-goals`
  if (targetKey.startsWith('developer_definition.verification.supported_question_family:')) return `${verificationBase}#verification-question-families`
  if (targetKey.startsWith('developer_definition.verification.non_goal:')) return `${verificationBase}#verification-non-goals`
  if (targetKey.startsWith('developer_definition.verification.success_criteria:')) return `${verificationBase}#verification-success-criteria`
  if (targetKey.startsWith('developer_definition.actor_expectation:')) return `${governanceBase}#actor-expectations`
  if (targetKey.startsWith('developer_definition.permission_rule:')) return `${governanceBase}#permission-intent-bindings`
  if (targetKey.startsWith('developer_definition.composition_rule:')) return `${scenarioExecutionBase}#compound-workflow-rules`
  if (targetKey.startsWith('developer_definition.generation.')) return `${generationBase}#generation-settings`
  if (targetKey.startsWith('developer_definition.contracts.')) {
    const sectionId = targetKey.replace('developer_definition.contracts.', '')
    const contractAnchors: Record<string, string> = {
      service_identity_topology: `${serviceBase}#identity-delivery`,
      capability_contracts: `/design/projects/${projectId}/developer/capability-formalization#capability-contracts`,
      authority_and_approval: `${serviceBase}#authority-approval`,
      data_contracts: `/design/projects/${projectId}/developer/data-contract-formalization#data-domain`,
      scenario_context: `${scenarioBase}#scenario-context`,
      execution_semantics: `${scenarioExecutionBase}#scenario-execution-semantics`,
      backend_bindings: `${serviceBase}#service-topology-bindings`,
      audit_and_lineage: `${auditBase}#audit-lineage`,
      generation_and_extensions: `${generationBase}#generation-settings`,
    }
    return contractAnchors[sectionId] ?? verificationBase
  }
  return definitionBase
}

export function developerDefinitionTargetStatus(
  targetKey: string,
  params: {
    developerDefinition: DeveloperDefinitionData | null
  },
): TraceabilityCoverageItem['status'] {
  const definition = params.developerDefinition

  const serviceTopologyMatch = targetKey.match(/^developer_definition\.service_topology:(.+)$/)
  if (serviceTopologyMatch) {
    const [, serviceId] = serviceTopologyMatch
    const binding = definition?.service_topology_bindings.find((item) => item.service_id === serviceId)
    if (!binding && definition?.integration_fronting?.project_type === 'governed_service_project') {
      return definition.generation.selected_service_ids.length > 0 ? 'addressed' : 'not_addressed'
    }
    if (!binding) return 'not_addressed'
    const capabilityReady = binding.formalized_capability_ids.length > 0
    const conceptReady = binding.source_concepts.length === 0 || binding.owned_concept_ids.length > 0
    if (capabilityReady && conceptReady) return 'addressed'
    if (capabilityReady || conceptReady || binding.implementation_notes.trim().length > 0) return 'partially_addressed'
    return 'not_addressed'
  }
  const domainConceptMatch = targetKey.match(/^developer_definition\.domain_concept:(.+)$/)
  if (domainConceptMatch) {
    const [, conceptId] = domainConceptMatch
    const binding = definition?.domain_concept_bindings.find((item) => item.concept_id === conceptId)
    if (!binding) return 'not_addressed'
    return binding.technical_representation.trim() ? 'addressed' : 'not_addressed'
  }

  const actorExpectationMatch = targetKey.match(/^developer_definition\.actor_expectation:([^:]+):(summary_formalization|visibility_formalization|action_formalization|approval_formalization)$/)
  if (actorExpectationMatch) {
    const [, actorKey, field] = actorExpectationMatch
    const entry = definition?.actor_expectations.find((item) => item.id === `actor_${actorKey}`)
    if (!entry) return 'not_addressed'
    const value = field === 'summary_formalization'
      ? entry.summary_formalization
      : field === 'visibility_formalization'
        ? entry.visibility_formalization
        : field === 'action_formalization'
          ? entry.action_formalization
          : entry.approval_formalization
    return value.trim() ? 'addressed' : 'not_addressed'
  }
  const permissionRuleMatch = targetKey.match(/^developer_definition\.permission_rule:(\d+)$/)
  if (permissionRuleMatch) {
    const [, index] = permissionRuleMatch
    const rule = definition?.permission_intent_bindings.find((item) => item.id === `permission_rule_${index}`)
    if (!rule) return 'not_addressed'
    return rule.formalization_strategy.trim() && hasVerificationTargetServices(rule.target_service_ids)
      ? 'addressed'
      : (rule.formalization_strategy.trim() || hasVerificationTargetServices(rule.target_service_ids) ? 'partially_addressed' : 'not_addressed')
  }
  if (targetKey === 'developer_definition.product_alignment.governed_behavior_formalization') {
    return definition?.product_alignment.governed_behavior_formalization.trim() ? 'addressed' : 'not_addressed'
  }
  if (targetKey === 'developer_definition.product_alignment.approval_posture_formalization') {
    return definition?.product_alignment.approval_posture_formalization.trim() ? 'addressed' : 'not_addressed'
  }
  if (targetKey.startsWith('developer_definition.service_coordination:')) {
    if (!definition) return 'not_addressed'
    const hasServiceTopology = definition.service_topology_bindings.length > 1
    const hasHandoffPolicy = definition.audit.service_handoffs_required
      || definition.audit.cross_service_reconstruction_required
      || definition.audit.cross_service_continuity_required
    const frontingMappingServiceIds = new Set(
      (definition.integration_fronting?.capability_mappings ?? [])
        .map((mapping) => mapping.service_id.trim())
        .filter(Boolean),
    )
    const hasGovernedFrontingSplit = definition.integration_fronting?.project_type === 'governed_service_project'
      && frontingMappingServiceIds.size > 1
    const hasExecutionSemantics = definition.scenario_formalizations.some((scenario) =>
      scenario.participating_service_ids.length > 1
      || scenario.orchestration_steps.some((step) => step.service_id.trim().length > 0),
    )
    if (hasServiceTopology && hasHandoffPolicy && (hasExecutionSemantics || hasGovernedFrontingSplit)) return 'addressed'
    if (hasServiceTopology || hasHandoffPolicy || hasExecutionSemantics || hasGovernedFrontingSplit) return 'partially_addressed'
    return 'not_addressed'
  }
  const integrationFrontingMatch = targetKey.match(/^developer_definition\.integration_fronting:(.+)$/)
  if (integrationFrontingMatch) {
    const [, capabilityId] = integrationFrontingMatch
    const mapping = definition?.integration_fronting?.capability_mappings.find((item) => item.capability_id === capabilityId)
    if (!mapping) return 'not_addressed'
    const hasBackendBinding = mapping.connection_ref.trim().length > 0 && mapping.raw_operation_refs.length > 0
    const hasGovernanceBinding = mapping.audit_required
      || mapping.approval_rule_refs.length > 0
      || mapping.denial_rule_refs.length > 0
      || mapping.clarification_rule_refs.length > 0
    if (hasBackendBinding && hasGovernanceBinding) return 'addressed'
    if (hasBackendBinding || hasGovernanceBinding || mapping.intent.trim()) return 'partially_addressed'
    return 'not_addressed'
  }
  const compositionRuleMatch = targetKey.match(/^developer_definition\.composition_rule:(\d+)$/)
  if (compositionRuleMatch) {
    const [, index] = compositionRuleMatch
    const rule = definition?.composition_rules.find((item) => item.id === `composition_rule_${index}`)
    if (!rule) return 'not_addressed'
    return rule.formalization_strategy.trim() && rule.affected_scenario_ids.length > 0
      ? 'addressed'
      : (rule.formalization_strategy.trim() || rule.affected_scenario_ids.length > 0 ? 'partially_addressed' : 'not_addressed')
  }
  const businessGoalMatch = targetKey.match(/^developer_definition\.verification\.business_goal:(\d+)$/)
  if (businessGoalMatch) {
    const [, index] = businessGoalMatch
    const binding = definition?.verification.business_goal_bindings.find((item) => item.id === `business_goal_${index}`)
    if (!binding) return 'not_addressed'
    return binding.verification_strategy.trim() && hasVerificationTargetServices(binding.target_service_ids)
      ? 'addressed'
      : (binding.verification_strategy.trim() || hasVerificationTargetServices(binding.target_service_ids) ? 'partially_addressed' : 'not_addressed')
  }
  const questionFamilyMatch = targetKey.match(/^developer_definition\.verification\.supported_question_family:(\d+)$/)
  if (questionFamilyMatch) {
    const [, index] = questionFamilyMatch
    const binding = definition?.verification.supported_question_family_bindings.find((item) => item.id === `supported_question_family_${index}`)
    if (!binding) return 'not_addressed'
    return binding.verification_strategy.trim() && hasVerificationTargetServices(binding.target_service_ids)
      ? 'addressed'
      : (binding.verification_strategy.trim() || hasVerificationTargetServices(binding.target_service_ids) ? 'partially_addressed' : 'not_addressed')
  }
  const nonGoalMatch = targetKey.match(/^developer_definition\.verification\.non_goal:(\d+)$/)
  if (nonGoalMatch) {
    const [, index] = nonGoalMatch
    const guard = definition?.verification.non_goal_guards.find((item) => item.id === `non_goal_${index}`)
    if (!guard) return 'not_addressed'
    return guard.guard_strategy.trim() && guard.evidence_signal.trim()
      ? 'addressed'
      : (guard.guard_strategy.trim() || guard.evidence_signal.trim() ? 'partially_addressed' : 'not_addressed')
  }
  const successCriteriaMatch = targetKey.match(/^developer_definition\.verification\.success_criteria:(\d+)$/)
  if (successCriteriaMatch) {
    const [, index] = successCriteriaMatch
    const check = definition?.verification.success_criteria_checks.find((item) => item.id === `success_criteria_${index}`)
    if (!check) return 'not_addressed'
    return check.verification_strategy.trim()
      ? 'addressed'
      : 'not_addressed'
  }
  if (targetKey === 'developer_definition.identity.system_name') {
    return definition?.identity.system_name.trim() ? 'addressed' : 'not_addressed'
  }
  if (targetKey === 'developer_definition.identity.domain_name') {
    return definition?.identity.domain_name.trim() ? 'addressed' : 'not_addressed'
  }
  if (targetKey === 'developer_definition.identity.delivery_model') {
    return definition?.identity.delivery_model ? 'addressed' : 'not_addressed'
  }
  if (targetKey === 'developer_definition.identity.architecture_shape') {
    return definition?.identity.architecture_shape ? 'addressed' : 'not_addressed'
  }
  if (targetKey === 'developer_definition.identity.high_availability_required') {
    return definition ? 'addressed' : 'not_addressed'
  }
  if (targetKey === 'developer_definition.authority.trust_mode') {
    return definition?.authority.trust_mode.trim() ? 'addressed' : 'not_addressed'
  }
  if (targetKey === 'developer_definition.authority.approval_expectation') {
    return definition?.authority.approval_expectation.trim() ? 'addressed' : 'not_addressed'
  }
  if (targetKey === 'developer_definition.authority.blocked_failure_posture') {
    return definition?.authority.blocked_failure_posture.trim() ? 'addressed' : 'not_addressed'
  }
  if (
    [
      'developer_definition.authority.trust_checkpoints_required',
      'developer_definition.authority.spending_actions_present',
      'developer_definition.authority.irreversible_actions_present',
      'developer_definition.authority.cost_visibility_required',
      'developer_definition.authority.preflight_authority_discovery',
      'developer_definition.authority.grantable_restrictions',
      'developer_definition.authority.restricted_vs_denied',
      'developer_definition.authority.delegation_tokens',
      'developer_definition.authority.scoped_authority',
      'developer_definition.authority.purpose_binding',
      'developer_definition.authority.recovery_sensitive',
      'developer_definition.audit.durable_records_required',
      'developer_definition.audit.searchable_history_required',
      'developer_definition.audit.invocation_tracking',
      'developer_definition.audit.task_tracking',
      'developer_definition.audit.parent_invocation_tracking',
      'developer_definition.audit.client_reference_ids',
      'developer_definition.audit.service_handoffs_required',
      'developer_definition.audit.cross_service_reconstruction_required',
      'developer_definition.audit.cross_service_continuity_required',
    ].includes(targetKey)
  ) {
    return definition ? 'addressed' : 'not_addressed'
  }
  const scenarioFormalizationMatch = targetKey.match(/^developer_definition\.scenario_formalization:([^:]+):([^:]+)(?::(.+))?$/)
  if (scenarioFormalizationMatch) {
    const [, scenarioId, field, value] = scenarioFormalizationMatch
    const formalization = findScenarioFormalization(definition, scenarioId)
    if (!formalization) return 'not_addressed'
    if (field === 'primary_capability') return formalization.primary_capability.trim() ? 'addressed' : 'not_addressed'
    if (field === 'actor_context') return formalization.actor_context.trim() ? 'addressed' : 'not_addressed'
    if (field === 'business_scope') return formalization.business_scope.trim() ? 'addressed' : 'not_addressed'
    if (field === 'time_scope') return formalization.time_scope.trim() ? 'addressed' : 'not_addressed'
    if (field === 'side_effect_formalization') return formalization.side_effect_formalization.trim() ? 'addressed' : 'not_addressed'
    if (field === 'expected_cost_formalization') return formalization.expected_cost_formalization.trim() ? 'addressed' : 'not_addressed'
    if (field === 'budget_guard_formalization') return formalization.budget_guard_formalization.trim() ? 'addressed' : 'not_addressed'
    if (field === 'permission_formalization') return formalization.permission_formalization.trim() ? 'addressed' : 'not_addressed'
    if (field === 'task_tracking_formalization') return formalization.task_tracking_formalization.trim() ? 'addressed' : 'not_addressed'
    if (field === 'participating_service_ids') return formalization.participating_service_ids.length ? 'addressed' : 'not_addressed'
    if (field === 'orchestration_steps') {
      if (!formalization.orchestration_steps.length) return 'not_addressed'
      const completeSteps = formalization.orchestration_steps.filter((step) =>
        step.service_id.trim()
        && step.outcome_type
        && (step.step_kind === 'handoff_only' || step.capability_id.trim()),
      )
      if (completeSteps.length === formalization.orchestration_steps.length) return 'addressed'
      return 'partially_addressed'
    }
    if (field === 'required_behaviors') {
      return value && formalization.required_behaviors.includes(value) ? 'addressed' : 'not_addressed'
    }
    if (field === 'required_anip_support') {
      return value && formalization.required_anip_support.includes(value) ? 'addressed' : 'not_addressed'
    }
  }
  if (targetKey === 'developer_definition.generation.service_generation_mode') {
    return definition?.generation.service_generation_mode ? 'addressed' : 'not_addressed'
  }
  if (targetKey === 'developer_definition.generation.selected_service_ids') {
    if (!definition) return 'not_addressed'
    if (definition.generation.service_generation_mode === 'single_service_scaffold') return 'addressed'
    return definition.generation.selected_service_ids.length > 0 ? 'addressed' : 'not_addressed'
  }
  if (targetKey === 'developer_definition.contracts.service_identity_topology') {
    if (!definition) return 'not_addressed'
    const identityComplete = [
      definition.identity.system_name,
      definition.identity.domain_name,
      definition.naming.namespace,
      definition.naming.package_prefix,
      definition.naming.service_name_prefix,
    ].every((value) => value.trim().length > 0)
    const servicesComplete = definition.generation.service_generation_mode === 'single_service_scaffold'
      || definition.generation.selected_service_ids.length > 0
    if (identityComplete && servicesComplete) return 'addressed'
    if (identityComplete || servicesComplete) return 'partially_addressed'
    return 'not_addressed'
  }
  if (targetKey === 'developer_definition.contracts.capability_contracts') {
    if (!definition) return 'not_addressed'
    const complete = definition.capability_formalizations.filter((item) =>
      item.capability_id.trim()
      && item.title.trim()
      && item.summary.trim()
      && item.operation_type.trim()
      && item.side_effect_level.trim()
      && item.backend_operation.trim(),
    ).length
    if (complete === definition.capability_formalizations.length && complete > 0) return 'addressed'
    if (complete > 0 || definition.capability_formalizations.length > 0) return 'partially_addressed'
    return 'not_addressed'
  }
  if (targetKey === 'developer_definition.contracts.authority_and_approval') {
    if (!definition) return 'not_addressed'
    const authoritySignals = Number(Boolean(definition.authority.trust_mode.trim()))
      + Number(Boolean(definition.authority.approval_expectation.trim()))
      + Number(Boolean(definition.authority.blocked_failure_posture.trim()))
      + definition.application_integration_governance.permission_rules.length
      + definition.application_integration_governance.restriction_rules.filter((rule) => rule.enabled).length
      + definition.application_integration_governance.denial_rules.filter((rule) => rule.enabled).length
      + definition.application_integration_governance.approval_rules.filter((rule) => rule.required).length
      + definition.data_access_governance.metric_rules.length
      + definition.data_access_governance.dimension_rules.length
      + definition.data_access_governance.use_rules.length
    if (authoritySignals >= 4) return 'addressed'
    if (authoritySignals > 0) return 'partially_addressed'
    return 'not_addressed'
  }
  if (targetKey === 'developer_definition.contracts.data_contracts') {
    const dataSignals = Number(Boolean(definition?.data_domain.domain_name.trim()))
      + (definition?.data_domain.metrics.length ?? 0)
      + (definition?.data_domain.dimensions.length ?? 0)
      + (definition?.data_domain.filters.length ?? 0)
      + (definition?.application_object_model.length ?? 0)
      + (definition?.data_access_governance.governed_outcomes.length ?? 0)
    if (dataSignals >= 3) return 'addressed'
    if (dataSignals > 0) return 'partially_addressed'
    return 'not_addressed'
  }
  if (targetKey === 'developer_definition.contracts.audit_and_lineage') {
    const lineageSignals = (definition?.scenario_formalizations.length ?? 0)
      + (definition?.data_access_governance.clarification_rules.filter((rule) => rule.enabled).length ?? 0)
    if (lineageSignals >= 2) return 'addressed'
    if (lineageSignals > 0) return 'partially_addressed'
    return 'not_addressed'
  }
  if (targetKey === 'developer_definition.contracts.execution_semantics') {
    if (!definition) return 'not_addressed'
    const semanticsSignals = definition.scenario_formalizations.reduce((count, scenario) =>
      count
      + scenario.required_behaviors.length
      + scenario.required_anip_support.length
      + Number(Boolean(scenario.implementation_notes.trim())),
    0)
    if (semanticsSignals >= 2) return 'addressed'
    if (semanticsSignals > 0) return 'partially_addressed'
    return 'not_addressed'
  }
  if (targetKey === 'developer_definition.contracts.backend_bindings') {
    if (!definition) return 'not_addressed'
    const serviceBindings = definition.service_backend_bindings ?? []
    const serviceComplete = serviceBindings.length > 0 && serviceBindings.every((binding) => {
      const dataReady = !binding.uses_data_access_backend
        || Boolean(binding.data_access_backend_type && binding.data_access_target_label.trim())
      const integrationReady = !binding.uses_application_integration_backend
        || Boolean(
          binding.application_integration_backend_type
          && (binding.application_integration_backend_type === 'custom_adapter'
            ? binding.application_integration_adapter_target.trim()
            : binding.application_integration_system_name.trim()),
        )
      return dataReady && integrationReady
    })
    const servicePartial = serviceBindings.some((binding) =>
      binding.uses_data_access_backend
      || binding.uses_application_integration_backend
      || binding.data_access_target_label.trim()
      || binding.application_integration_system_name.trim()
      || binding.application_integration_adapter_target.trim(),
    )
    if (serviceComplete) return 'addressed'
    if (servicePartial) return 'partially_addressed'
    return 'not_addressed'
  }
  if (targetKey === 'developer_definition.contracts.generation_and_extensions') {
    if (!definition) return 'not_addressed'
    const generationComplete = Boolean(
      definition.generation.codegen_adapter
      && definition.generation.layout_strategy
      && definition.generation.scalability_profile
      && definition.generation.protocols.length > 0,
    )
    const rationaleComplete = definition.rationale.trim().length > 0
    if (generationComplete && rationaleComplete) return 'addressed'
    if (generationComplete) return 'partially_addressed'
    return 'not_addressed'
  }
  return 'not_addressed'
}

export function summarizeCoverageForDefinitionSection(
  coverage: TraceabilityCoverageItem[],
  sectionId: DeveloperDefinitionSectionId,
) {
  const linked = coverage.filter((item) => resolveDeveloperDefinitionLinks(item.linked_surfaces).includes(sectionId))
  const summary = {
    total: linked.length,
    addressed: 0,
    partial: 0,
    missing: 0,
    deferred: 0,
  }
  linked.forEach((item) => {
    if (item.status === 'addressed') summary.addressed += 1
    else if (item.status === 'partially_addressed') summary.partial += 1
    else if (item.status === 'deferred') summary.deferred += 1
    else if (item.status === 'not_addressed') summary.missing += 1
  })
  return { items: linked, summary }
}

function serviceDesignSummary(shape: ShapeRecord | null) {
  const shapeData = ((shape?.data?.shape ?? shape?.data) as Record<string, any> | undefined) ?? {}
  const services = Array.isArray(shapeData.services) ? shapeData.services : []
  const coordination = Array.isArray(shapeData.coordination) ? shapeData.coordination : []
  return {
    id: shape?.id ?? null,
    title: shape?.title ?? null,
    hash: shape?.content_hash ?? null,
    services: services.map((service: Record<string, any>) => ({
      id: String(service.id ?? ''),
      name: String(service.name ?? service.id ?? 'Service'),
      role: String(service.role ?? ''),
      capabilities: Array.isArray(service.capabilities) ? service.capabilities : [],
    })),
    coordination: coordination.map((edge: Record<string, any>) => ({
      from: String(edge.from ?? ''),
      to: String(edge.to ?? ''),
      relationship: String(edge.relationship ?? ''),
      description: String(edge.description ?? ''),
    })),
  }
}

function slugify(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
}

function scenarioSetHash(scenarios: ArtifactRecord[]): string | null {
  if (scenarios.length === 0) return null
  return scenarios
    .map((scenario) => `${scenario.id}:${scenario.content_hash}`)
    .sort()
    .join('|')
}

function canonicalScenarioSetHash(value: string | null | undefined): string | null {
  const trimmed = String(value ?? '').trim()
  if (!trimmed) return null
  if (!trimmed.includes('|')) return trimmed
  return trimmed.split('|').map((part) => part.trim()).filter(Boolean).sort().join('|')
}

function deriveServiceIds(shape: ShapeRecord | null): string[] {
  const shapeData = ((shape?.data?.shape ?? shape?.data) as Record<string, any> | undefined) ?? {}
  const services = Array.isArray(shapeData.services) ? shapeData.services : []
  return services
    .map((service: Record<string, any>) => String(service.id ?? ''))
    .filter(Boolean)
}

function serviceLookupForShape(shape: ShapeRecord | null): Map<string, string> {
  const shapeData = ((shape?.data?.shape ?? shape?.data) as Record<string, any> | undefined) ?? {}
  const services = Array.isArray(shapeData.services) ? shapeData.services : []
  const lookup = new Map<string, string>()
  services.forEach((service: Record<string, any>) => {
    const id = String(service.id ?? '').trim()
    const name = String(service.name ?? id).trim()
    if (!id) return
    lookup.set(normalizeText(id), id)
    lookup.set(normalizeText(name), id)
  })
  return lookup
}

function normalizeText(value: string): string {
  return value.trim().toLowerCase().replace(/[_-]+/g, ' ').replace(/\s+/g, ' ')
}

function scenarioSemanticType(entry: Record<string, any>): ScenarioAdditionalContextSemanticType {
  const semanticType = String(entry.semantic_type ?? '').trim()
  if (
    semanticType === 'actor_context'
    || semanticType === 'business_scope'
    || semanticType === 'time_scope'
    || semanticType === 'participating_services'
    || semanticType === 'orchestration_step'
    || semanticType === 'descriptive_only'
  ) {
    return semanticType
  }
  return 'descriptive_only'
}

function scenarioAdditionalContextEntries(scenario: ArtifactRecord): ScenarioAdditionalContextEntry[] {
  const scenarioData = (scenario.data?.scenario ?? {}) as Record<string, any>
  const additional = Array.isArray(scenarioData.additional_context) ? scenarioData.additional_context : []
  return additional.map((entry: Record<string, any>) => ({
    key: String(entry.key ?? '').trim(),
    value: String(entry.value ?? '').trim(),
    semantic_type: scenarioSemanticType(entry),
    role: entry.role === 'design_driving' ? 'design_driving' : 'descriptive',
    description: String(entry.description ?? '').trim(),
  }))
}

function splitSemanticValues(value: string): string[] {
  return value
    .split(/\n|,|;/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function orchestrationStepId(index: number, seed: string): string {
  const base = slugify(seed) || `step_${index + 1}`
  return `step_${index + 1}_${base}`
}

function inferOutcomeTypeFromText(value: string): DeveloperScenarioOutcomeType {
  const normalized = normalizeText(value)
  if (normalized.includes('approval required')) return 'approval_required'
  if (normalized.includes('clarification required') || normalized.includes('request clarification')) return 'clarification_required'
  if (normalized.includes('safe stop') || normalized.includes('stop safely')) return 'safe_stop'
  if (normalized.includes('complete') || normalized.includes('completed')) return 'completed'
  if (normalized.includes('handoff')) return 'handoff'
  return 'intermediate_result'
}

function isGenericOrchestrationPlaceholder(value: string): boolean {
  return /^(step|phase|stage)\s*\d+$/i.test(value.trim())
}

function buildStructuredOrchestrationSteps(
  values: string[],
  serviceLookup: Map<string, string>,
): DeveloperScenarioOrchestrationStep[] {
  const steps: DeveloperScenarioOrchestrationStep[] = []
  values.forEach((raw, index) => {
    const line = String(raw).trim()
    if (!line) return
    if (isGenericOrchestrationPlaceholder(line)) return
    const parts = line.split(/\s*->\s*/).map((part) => part.trim()).filter(Boolean)
    const firstPart = parts[0] ?? line
    const firstPartSegments = firstPart.split(':').map((part) => part.trim()).filter(Boolean)
    const serviceCandidate = firstPartSegments[0] ?? ''
    const explicitCapabilityCandidate = firstPartSegments.length > 1
      ? firstPartSegments.slice(1).join(':')
      : ''
    const embeddedCapabilityCandidate = line.match(/\b[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+\b/i)?.[0] ?? ''
    const capabilityCandidate = explicitCapabilityCandidate || embeddedCapabilityCandidate
    const outcomeCandidate = parts.length > 1
      ? parts.slice(1).join(' -> ')
      : line
    const stepKind: DeveloperScenarioStepKind = capabilityCandidate ? 'capability_execution' : 'handoff_only'
    steps.push({
        id: orchestrationStepId(index, line),
        service_id: serviceLookup.get(normalizeText(serviceCandidate)) ?? '',
        step_kind: stepKind,
        capability_id: capabilityCandidate,
        outcome_type: inferOutcomeTypeFromText(outcomeCandidate),
        outcome_notes: outcomeCandidate,
        stop_condition: 'continue',
    })
  })
  return steps
}

interface ShapeCapabilityCandidate {
  capability_id: string
  service_id: string
  title: string
  summary: string
  operation_type: string
  side_effect_level: string
}

function shapeCapabilityCandidates(shape: ShapeRecord | null): ShapeCapabilityCandidate[] {
  const shapeData = ((shape?.data?.shape ?? shape?.data) as Record<string, any> | undefined) ?? {}
  const services = Array.isArray(shapeData.services) ? shapeData.services : []
  const ownerByCapabilityId = new Map<string, string>()
  services.forEach((service: Record<string, any>) => {
    const serviceId = String(service.id ?? service.name ?? '').trim()
    if (!serviceId || !Array.isArray(service.capabilities)) return
    service.capabilities
      .map((value: unknown) => String(value).trim())
      .filter(Boolean)
      .forEach((capabilityId: string) => {
        if (!ownerByCapabilityId.has(capabilityId)) ownerByCapabilityId.set(capabilityId, serviceId)
      })
  })

  const contracts = Array.isArray(shapeData.capability_contracts) ? shapeData.capability_contracts : []
  const fromContracts = contracts
    .map((contract: Record<string, any>) => {
      const capabilityId = String(contract.id ?? contract.capability_id ?? '').trim()
      if (!capabilityId) return null
      const sideEffect = String(contract.side_effect_type ?? contract.side_effect_level ?? 'read').trim()
      return {
        capability_id: capabilityId,
        service_id: String(contract.service_id ?? ownerByCapabilityId.get(capabilityId) ?? '').trim(),
        title: humanize(capabilityId),
        summary: String(contract.purpose ?? contract.summary ?? contract.description ?? '').trim(),
        operation_type: sideEffect === 'read' ? 'read' : 'approval_gated',
        side_effect_level: Array.isArray(contract.approval_required_when) && contract.approval_required_when.length
          ? 'approval_required'
          : sideEffect,
      } satisfies ShapeCapabilityCandidate
    })
    .filter((candidate): candidate is ShapeCapabilityCandidate => candidate != null)

  const known = new Set(fromContracts.map((candidate) => candidate.capability_id))
  const fromServices = services.flatMap((service: Record<string, any>) => {
    const serviceId = String(service.id ?? service.name ?? '').trim()
    if (!serviceId || !Array.isArray(service.capabilities)) return []
    return service.capabilities
      .map((value: unknown) => String(value).trim())
      .filter(Boolean)
      .filter((capabilityId: string) => !known.has(capabilityId))
      .map((capabilityId: string): ShapeCapabilityCandidate => ({
        capability_id: capabilityId,
        service_id: serviceId,
        title: humanize(capabilityId),
        summary: String(service.role ?? service.description ?? '').trim(),
        operation_type: 'read',
        side_effect_level: 'read',
      }))
  })

  return [...fromContracts, ...fromServices]
}

function distinctiveCapabilityTerms(capabilityId: string, summary: string): string[] {
  const ignored = new Set([
    'service',
    'summary',
    'summaries',
    'prepare',
    'return',
    'bounded',
    'governed',
    'review',
    'reviews',
  ])
  const idTerms = [...new Set(capabilityId
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .map((term) => term.trim())
    .filter((term) => term.length > 2 && !ignored.has(term)))]
  void summary
  return idTerms
}

function scoreCapabilityAgainstText(candidate: ShapeCapabilityCandidate, text: string): { score: number; position: number } {
  const normalized = normalizeText(text)
  const terms = distinctiveCapabilityTerms(candidate.capability_id, candidate.summary)
  let score = 0
  let position = Number.MAX_SAFE_INTEGER
  terms.forEach((term) => {
    const variants = [term]
    if (term === 'prioritize') variants.push('prioritization', 'prioritized')
    if (term === 'score') variants.push('scoring', 'scored')
    if (term === 'route') variants.push('routing', 'routed')
    if (term === 'draft') variants.push('drafting', 'drafted')
    if (term === 'followup') variants.push('follow up', 'follow-up')
    const index = variants
      .map((variant) => normalized.indexOf(variant))
      .filter((candidateIndex) => candidateIndex >= 0)
      .sort((left, right) => left - right)[0] ?? -1
    if (index >= 0) {
      score += 1
      position = Math.min(position, index)
    }
  })
  if (normalized.includes(candidate.capability_id.toLowerCase())) {
    score += 10
    position = Math.min(position, normalized.indexOf(candidate.capability_id.toLowerCase()))
  }
  return { score, position }
}

function inferScenarioOrchestrationStepsFromText(
  scenario: ArtifactRecord,
  shape: ShapeRecord | null,
): DeveloperScenarioOrchestrationStep[] {
  const scenarioData = (scenario.data?.scenario ?? {}) as Record<string, any>
  if (String(scenarioData.category ?? '').trim() !== 'orchestration') return []
  const text = [
    scenario.title,
    scenarioData.name,
    scenarioData.category,
    scenarioData.narrative,
    ...(Array.isArray(scenarioData.expected_behavior) ? scenarioData.expected_behavior : []),
  ].map((value) => String(value ?? '')).join(' ')
  const ranked = shapeCapabilityCandidates(shape)
    .map((candidate) => ({ candidate, ...scoreCapabilityAgainstText(candidate, text) }))
    .filter((entry) => entry.score >= 2)
    .sort((left, right) => left.position - right.position || right.score - left.score || left.candidate.capability_id.localeCompare(right.candidate.capability_id))
    .slice(0, 4)

  if (ranked.length === 0) return []
  return ranked.map((entry, index): DeveloperScenarioOrchestrationStep => ({
    id: orchestrationStepId(index, entry.candidate.capability_id),
    service_id: entry.candidate.service_id,
    step_kind: 'capability_execution',
    capability_id: entry.candidate.capability_id,
    outcome_type: index === ranked.length - 1 ? 'completed' : 'intermediate_result',
    outcome_notes: entry.candidate.summary || `Execute ${entry.candidate.capability_id}.`,
    stop_condition: 'continue',
  }))
}

function normalizeExistingOrchestrationSteps(
  steps: unknown[],
  serviceLookup: Map<string, string>,
): DeveloperScenarioOrchestrationStep[] {
  return steps
    .map((step, index) => {
      if (typeof step === 'string') {
        return buildStructuredOrchestrationSteps([step], serviceLookup)[0] ?? null
      }
      if (!step || typeof step !== 'object') return null
      const record = step as Record<string, unknown>
      const serviceId = String(record.service_id ?? '').trim()
      const stepKind = String(record.step_kind ?? (String(record.capability_id ?? '').trim() ? 'capability_execution' : 'handoff_only')).trim()
      const capabilityId = String(record.capability_id ?? '').trim()
      const outcomeNotes = String(record.outcome_notes ?? record.expected_outcome ?? '').trim()
      const stepLabel = String(record.id ?? record.name ?? record.step ?? '').trim()
      if (!serviceId && !capabilityId && !outcomeNotes && isGenericOrchestrationPlaceholder(stepLabel)) return null
      const outcomeType = String(record.outcome_type ?? inferOutcomeTypeFromText(outcomeNotes)).trim()
      const stopCondition = String(record.stop_condition ?? 'continue').trim()
      return {
        id: String(record.id ?? orchestrationStepId(index, outcomeNotes || capabilityId || serviceId || 'step')).trim(),
        service_id: serviceLookup.get(normalizeText(serviceId)) ?? serviceId,
        step_kind:
          stepKind === 'capability_execution'
          || stepKind === 'handoff_only'
            ? stepKind
            : (capabilityId ? 'capability_execution' : 'handoff_only'),
        capability_id: capabilityId,
        outcome_type:
          outcomeType === 'handoff'
          || outcomeType === 'approval_required'
          || outcomeType === 'clarification_required'
          || outcomeType === 'safe_stop'
          || outcomeType === 'completed'
            ? outcomeType
            : 'intermediate_result',
        outcome_notes: outcomeNotes,
        stop_condition:
          stopCondition === 'approval_required'
          || stopCondition === 'clarification_required'
          || stopCondition === 'safe_stop'
          || stopCondition === 'complete'
            ? stopCondition
            : 'continue',
      } satisfies DeveloperScenarioOrchestrationStep
    })
    .filter((step): step is DeveloperScenarioOrchestrationStep => step != null)
}

function normalizeScenarioOrchestrationServices(
  steps: DeveloperScenarioOrchestrationStep[],
  participatingServiceIds: string[],
): DeveloperScenarioOrchestrationStep[] {
  const fallbackServiceId = participatingServiceIds.length === 1 ? participatingServiceIds[0] : ''
  return steps
    .map((step) => ({
      ...step,
      service_id: step.service_id || fallbackServiceId || inferParticipatingServiceForStep(step, participatingServiceIds),
    }))
    .filter((step) => (
      step.service_id
      || step.step_kind === 'capability_execution'
    ))
}

function inferParticipatingServiceForStep(
  step: DeveloperScenarioOrchestrationStep,
  participatingServiceIds: string[],
): string {
  if (participatingServiceIds.length === 0) return ''
  const ignoredServiceTokens = new Set(['service', 'services', 'system', 'anip', 'api', 'gtm'])
  const stepText = normalizeText([
    step.id,
    step.capability_id,
    step.outcome_notes,
    step.outcome_type,
  ].join(' '))
  let best: { id: string; score: number } | null = null
  for (const serviceId of participatingServiceIds) {
    const serviceTokens = normalizeText(serviceId)
      .split(' ')
      .filter((token) => token.length > 2 && !ignoredServiceTokens.has(token))
    const score = serviceTokens.reduce((sum, token) => sum + (stepText.includes(token) ? 1 : 0), 0)
    if (score > (best?.score ?? 0)) best = { id: serviceId, score }
  }
  if (best && best.score > 0) return best.id
  return ''
}

function deriveScenarioFormalizationFromProductDesign(
  scenario: ArtifactRecord,
  shape: ShapeRecord | null,
): Pick<
  DeveloperScenarioFormalization,
  'actor_context' | 'business_scope' | 'time_scope' | 'participating_service_ids' | 'orchestration_steps'
> {
  const entries = scenarioAdditionalContextEntries(scenario)
  const serviceLookup = serviceLookupForShape(shape)

  const actorContext = entries.find((entry) => entry.semantic_type === 'actor_context')?.value ?? ''
  const businessScope = entries.find((entry) => entry.semantic_type === 'business_scope')?.value ?? ''
  const timeScope = entries.find((entry) => entry.semantic_type === 'time_scope')?.value ?? ''
  const scenarioData = (scenario.data?.scenario ?? {}) as Record<string, any>
  const explicitParticipatingServices = Array.isArray(scenarioData.participating_services)
    ? scenarioData.participating_services.map((value: unknown) => String(value).trim()).filter(Boolean)
    : []
  const explicitOrchestrationSteps = Array.isArray(scenarioData.orchestration_steps)
    ? scenarioData.orchestration_steps.filter((value: unknown) =>
      typeof value === 'string' || (value && typeof value === 'object'),
    )
    : []

  const participatingServiceIds = (explicitParticipatingServices.length
    ? explicitParticipatingServices
    : entries
      .filter((entry) => entry.semantic_type === 'participating_services')
      .flatMap((entry) => splitSemanticValues(entry.value)))
    .map((value) => serviceLookup.get(normalizeText(value)) ?? value)
    .filter(Boolean)

  const orchestrationSteps = explicitOrchestrationSteps.length
    ? normalizeExistingOrchestrationSteps(explicitOrchestrationSteps, serviceLookup)
    : entries
      .filter((entry) => entry.semantic_type === 'orchestration_step')
      .flatMap((entry) => buildStructuredOrchestrationSteps(
        entry.value.split('\n').map((line: string) => line.trim()).filter(Boolean),
        serviceLookup,
      ))

  return {
    actor_context: actorContext,
    business_scope: businessScope,
    time_scope: timeScope,
    participating_service_ids: [...new Set(participatingServiceIds)],
    orchestration_steps: orchestrationSteps.length ? orchestrationSteps : inferScenarioOrchestrationStepsFromText(scenario, shape),
  }
}

function deriveDefaultCodegenAdapter(
  dataAccessProject: DataAccessProjectState | null,
  applicationIntegrationProject: ApplicationIntegrationProjectState | null,
): DeveloperCodegenAdapter {
  const languages = [
    dataAccessProject?.backend.implementationLanguage ?? null,
    applicationIntegrationProject?.backend.implementationLanguage ?? null,
  ].filter(Boolean)

  if (languages.includes('python')) return 'python_fastapi'
  return 'typescript_node'
}

function implementationLanguageForAdapter(adapter: DeveloperCodegenAdapter | null | undefined): 'typescript' | 'python' {
  return adapter === 'python_fastapi' ? 'python' : 'typescript'
}

function requirementsData(requirements: RequirementsRecord | null): Record<string, any> {
  return ((requirements?.data ?? {}) as Record<string, any>)
}

function buildBackendBindings(params: {
  project: ProjectDetail
  shape: ShapeRecord | null
  existing?: DeveloperDefinitionData | null
  pmArtifacts: ArtifactRecord[]
  dataAccessProject: DataAccessProjectState | null
  applicationIntegrationProject: ApplicationIntegrationProjectState | null
}) {
  const existing = params.existing ?? null
  const dataAccessGuidance = buildAssistantGuidanceBlock(
    params.pmArtifacts,
    'assistant_backend_binding_candidates',
    ['backend-data-access-target'],
  )
  const integrationGuidance = buildAssistantGuidanceBlock(
    params.pmArtifacts,
    'assistant_backend_binding_candidates',
    ['backend-integration-system', 'backend-auth-posture', 'backend-environment-target'],
  )
  const adapterGuidance = buildAssistantGuidanceBlock(
    params.pmArtifacts,
    'assistant_backend_binding_candidates',
    ['backend-integration-system', 'backend-service-overrides'],
  )
  return {
    data_access_backend_type:
      existing?.backend_bindings.data_access_backend_type
      ?? params.dataAccessProject?.backend.type
      ?? '',
    data_access_target_label:
      textOrGuidanceOrFallback(
        existing?.backend_bindings.data_access_target_label,
        dataAccessGuidance,
        params.dataAccessProject?.backend.targetLabel ?? '',
      ),
    application_integration_backend_type:
      existing?.backend_bindings.application_integration_backend_type
      ?? params.applicationIntegrationProject?.backend.backendType
      ?? '',
    application_integration_system_name:
      textOrGuidanceOrFallback(
        existing?.backend_bindings.application_integration_system_name,
        integrationGuidance,
        params.applicationIntegrationProject?.backend.systemName ?? '',
      ),
    application_integration_environment:
      existing?.backend_bindings.application_integration_environment
      ?? params.applicationIntegrationProject?.backend.environment
      ?? '',
    application_integration_auth_type:
      existing?.backend_bindings.application_integration_auth_type
      ?? params.applicationIntegrationProject?.backend.authType
      ?? '',
    application_integration_adapter_target:
      textOrGuidanceOrFallback(
        existing?.backend_bindings.application_integration_adapter_target,
        adapterGuidance,
        params.applicationIntegrationProject?.backend.adapterTarget ?? '',
      ),
  }
}

function buildServiceBackendBindings(params: {
  shape: ShapeRecord | null
  capabilities: DeveloperCapabilityFormalization[]
  pmArtifacts: ArtifactRecord[]
  existing?: DeveloperDefinitionData | null
}): DeveloperServiceBackendBinding[] {
  const serviceLookup = serviceLookupForShape(params.shape)
  const integrationFrontingMappings = buildIntegrationFrontingMappings(params.pmArtifacts)
  const integrationMappingByServiceId = new Map(
    integrationFrontingMappings.map((mapping) => [mapping.service_id, mapping] as const),
  )
  const serviceIds = Array.from(new Set([
    ...deriveServiceIds(params.shape),
    ...params.capabilities.map((capability) => capability.service_id).filter(Boolean),
  ]))
  const perServiceGuidance = buildAssistantGuidanceBlock(
    params.pmArtifacts,
    'assistant_backend_binding_candidates',
    ['backend-service-overrides'],
  )
  return serviceIds.map((serviceId) => {
    const existingBinding = params.existing?.service_backend_bindings.find((binding) => binding.service_id === serviceId)
    const serviceCapabilities = params.capabilities.filter((capability) => capability.service_id === serviceId)
    const integrationFrontingMapping = integrationMappingByServiceId.get(serviceId)
    const inferredUsesDataAccess = serviceCapabilities.some((capability) => capability.source_kind === 'data_access')
    const inferredUsesIntegration = Boolean(integrationFrontingMapping)
      || serviceCapabilities.some((capability) =>
        capability.id.startsWith('application_integration:')
        || capability.id.startsWith('integration_fronting:'),
      )
    return {
      service_id: serviceId,
      service_name: existingBinding?.service_name
        || integrationFrontingMapping?.service_name
        || serviceLookup.get(serviceId)
        || humanize(serviceId),
      uses_data_access_backend:
        existingBinding?.uses_data_access_backend
        ?? inferredUsesDataAccess,
      data_access_backend_type:
        existingBinding?.uses_data_access_backend
          ? existingBinding.data_access_backend_type
          : '',
      data_access_target_label:
        existingBinding?.uses_data_access_backend
          ? seedAssistantText(existingBinding.data_access_target_label, perServiceGuidance)
          : '',
      uses_application_integration_backend:
        existingBinding?.uses_application_integration_backend
        ?? inferredUsesIntegration,
      application_integration_backend_type:
        existingBinding?.uses_application_integration_backend
          ? existingBinding.application_integration_backend_type
          : integrationFrontingMapping?.backend_kind ?? '',
      application_integration_system_name:
        existingBinding?.uses_application_integration_backend
          ? seedAssistantText(existingBinding.application_integration_system_name, perServiceGuidance)
          : integrationFrontingMapping?.connection_ref ?? '',
      application_integration_environment:
        existingBinding?.uses_application_integration_backend
          ? existingBinding.application_integration_environment
          : '',
      application_integration_auth_type:
        '',
      application_integration_adapter_target:
        existingBinding?.uses_application_integration_backend
          ? seedAssistantText(existingBinding.application_integration_adapter_target, perServiceGuidance)
          : '',
    }
  })
}

function buildApplicationIntegrationGovernance(params: {
  existing?: DeveloperDefinitionData | null
  pmArtifacts: ArtifactRecord[]
  applicationIntegrationProject: ApplicationIntegrationProjectState | null
}): DeveloperApplicationIntegrationGovernanceFormalization {
  const existing = params.existing?.application_integration_governance
  const governance = params.applicationIntegrationProject?.governance
  const clarificationGuidance = buildAssistantGuidanceBlock(
    params.pmArtifacts,
    'assistant_runtime_policy_binding_candidates',
    ['policy-clarification-stops'],
  )
  const approvalGuidance = buildAssistantGuidanceBlock(
    params.pmArtifacts,
    'assistant_runtime_policy_binding_candidates',
    ['policy-approval-decision-point'],
  )
  const safeDefaults: DeveloperApplicationIntegrationSafeDefaults = {
    default_result_limit:
      existing?.safe_defaults.default_result_limit
      ?? governance?.safeDefaults.defaultResultLimit
      ?? 25,
    require_approval_for_writes:
      existing?.safe_defaults.require_approval_for_writes
      ?? governance?.safeDefaults.requireApprovalForWrites
      ?? Boolean(approvalGuidance),
    require_clarification_on_ambiguous_record:
      existing?.safe_defaults.require_clarification_on_ambiguous_record
      ?? governance?.safeDefaults.requireClarificationOnAmbiguousRecord
      ?? Boolean(clarificationGuidance),
    dry_run_before_write:
      existing?.safe_defaults.dry_run_before_write
      ?? governance?.safeDefaults.dryRunBeforeWrite
      ?? false,
  }

  const permissionRules: DeveloperApplicationIntegrationPermissionRule[] =
    existing?.permission_rules
    ?? (governance?.permissionRules ?? []).map((rule) => ({
      rule_id: rule.ruleId,
      scope_type: rule.scopeType,
      scope_name: rule.scopeName,
      actor_constraint: rule.actorConstraint,
      purpose_constraint: rule.purposeConstraint,
      allowed: rule.allowed,
      summary: rule.summary,
    }))

  const clarificationRules: DeveloperApplicationIntegrationClarificationRule[] =
    existing?.clarification_rules
    ?? (governance?.clarificationRules ?? []).map((rule) => ({
      rule_id: rule.ruleId,
      trigger_type: rule.triggerType,
      capability_id: rule.capabilityId ?? '',
      summary: rule.summary,
      prompt_hint: rule.promptHint,
      enabled: rule.enabled,
    }))
  if (!clarificationRules.length && clarificationGuidance) {
    clarificationRules.push({
      rule_id: 'assistant_clarification_boundary',
      trigger_type: 'assistant_proposal',
      capability_id: '',
      summary: 'Accepted assistant clarification guidance',
      prompt_hint: clarificationGuidance,
      enabled: true,
    })
  }

  const restrictionRules: DeveloperApplicationIntegrationRestrictionRule[] =
    existing?.restriction_rules
    ?? (governance?.restrictionRules ?? []).map((rule) => ({
      rule_id: rule.ruleId,
      restriction_type: rule.restrictionType,
      capability_id: rule.capabilityId ?? '',
      summary: rule.summary,
      value: rule.value,
      enabled: rule.enabled,
    }))

  const denialRules: DeveloperApplicationIntegrationDenialRule[] =
    existing?.denial_rules
    ?? (governance?.denialRules ?? []).map((rule) => ({
      rule_id: rule.ruleId,
      denial_type: rule.denialType,
      capability_id: rule.capabilityId ?? '',
      summary: rule.summary,
      enabled: rule.enabled,
    }))

  const approvalRules: DeveloperApplicationIntegrationApprovalRule[] =
    existing?.approval_rules
    ?? (governance?.approvalRules ?? []).map((rule) => ({
      rule_id: rule.ruleId,
      capability_id: rule.capabilityId,
      required: rule.required,
      approver_type: rule.approverType,
      summary: rule.summary,
    }))
  if (!approvalRules.length && approvalGuidance) {
    approvalRules.push({
      rule_id: 'assistant_approval_boundary',
      capability_id: '',
      required: true,
      approver_type: '',
      summary: approvalGuidance,
    })
  }

  return {
    safe_defaults: safeDefaults,
    permission_rules: permissionRules,
    clarification_rules: clarificationRules,
    restriction_rules: restrictionRules,
    denial_rules: denialRules,
    approval_rules: approvalRules,
  }
}

function buildDataAccessGovernance(params: {
  existing?: DeveloperDefinitionData | null
  dataAccessProject: DataAccessProjectState | null
}): DeveloperDataAccessGovernanceFormalization {
  const existing = params.existing?.data_access_governance
  const project = params.dataAccessProject
  const governedOutcomes =
    existing?.governed_outcomes
    ?? Object.entries(project?.governedOutcomes ?? {})
      .filter(([, enabled]) => Boolean(enabled))
      .map(([key]) => key)

  const metricRules: DeveloperDataAccessMetricRule[] =
    existing?.metric_rules
    ?? (project?.permissions.metricRules ?? []).map((rule) => ({
      metric_key: rule.metricKey,
      restricted_to_roles: [...rule.restrictedToRoles],
      denied_roles: [...(rule.deniedRoles ?? [])],
      notes: rule.notes ?? '',
    }))

  const dimensionRules: DeveloperDataAccessDimensionRule[] =
    existing?.dimension_rules
    ?? (project?.permissions.dimensionRules ?? []).map((rule) => ({
      dimension_key: rule.dimensionKey,
      restricted_to_roles: [...rule.restrictedToRoles],
      denied_roles: [...(rule.deniedRoles ?? [])],
      notes: rule.notes ?? '',
    }))

  const limitRules: DeveloperDataAccessLimitRule[] =
    existing?.limit_rules
    ?? (project?.permissions.limitRules ?? []).map((rule) => ({
      applies_to_roles: [...rule.appliesToRoles],
      grain: rule.grain,
      max_rows: rule.maxRows,
      notes: rule.notes ?? '',
    }))

  const useRules: DeveloperDataAccessUseRule[] =
    existing?.use_rules
    ?? (project?.permissions.useRules ?? []).map((rule) => ({
      applies_to_roles: [...rule.appliesToRoles],
      export_allowed: rule.exportAllowed,
      downstream_use: rule.downstreamUse,
      downgrade_decision_grade: Boolean(rule.downgradeDecisionGrade),
      notes: rule.notes ?? '',
    }))

  const clarificationRules: DeveloperDataAccessClarificationRule[] =
    existing?.clarification_rules
    ?? (project?.clarification.rules ?? []).map((rule) => ({
      key: rule.key,
      enabled: rule.enabled,
      prompt_hint: rule.promptHint ?? '',
    }))

  return {
    governed_outcomes: governedOutcomes,
    metric_rules: metricRules,
    dimension_rules: dimensionRules,
    limit_rules: limitRules,
    use_rules: useRules,
    clarification_rules: clarificationRules,
  }
}

function buildDataDomainFormalization(params: {
  project: ProjectDetail
  existing?: DeveloperDefinitionData | null
  dataAccessProject: DataAccessProjectState | null
  fallbackDomainName?: string
}): DeveloperDataDomainFormalization {
  const existing = params.existing?.data_domain
  const domain = params.dataAccessProject?.domain
  const mapMetric = (item: { key: string; label: string; description?: string }): DeveloperDataMetricDefinition => ({
    key: item.key,
    label: item.label,
    description: item.description ?? '',
  })
  const mapDimension = (item: { key: string; label: string; description?: string }): DeveloperDataDimensionDefinition => ({
    key: item.key,
    label: item.label,
    description: item.description ?? '',
  })
  const mapFilter = (item: { key: string; label: string; description?: string }): DeveloperDataFilterDefinition => ({
    key: item.key,
    label: item.label,
    description: item.description ?? '',
  })
  return {
    domain_name: textOrFallback(
      existing?.domain_name,
      domain?.name || params.project.domain || params.fallbackDomainName || slugify(params.project.name),
    ),
    metrics: existing?.metrics ?? (domain?.metrics ?? []).map(mapMetric),
    dimensions: existing?.dimensions ?? (domain?.dimensions ?? []).map(mapDimension),
    filters: existing?.filters ?? (domain?.filters ?? []).map(mapFilter),
    grains: existing?.grains ?? [...(domain?.grains ?? [])],
    result_modes: existing?.result_modes ?? [...(domain?.resultModes ?? [])],
  }
}

function buildApplicationObjectModel(params: {
  existing?: DeveloperDefinitionData | null
  applicationIntegrationProject: ApplicationIntegrationProjectState | null
}): DeveloperApplicationObjectFormalization[] {
  const existingById = new Map(
    (params.existing?.application_object_model ?? []).map((item) => [item.object_id, item] as const),
  )
  const mapField = (field: Record<string, any>): DeveloperApplicationObjectFieldFormalization => ({
    field_name: String(field.fieldName ?? ''),
    field_type: String(field.fieldType ?? ''),
    required: Boolean(field.required),
    filterable: Boolean(field.filterable),
    writable: Boolean(field.writable),
    sensitive: Boolean(field.sensitive),
    summary: String(field.summary ?? ''),
  })
  const mapRelationship = (relationship: Record<string, any>): DeveloperApplicationObjectRelationshipFormalization => ({
    relationship_name: String(relationship.relationshipName ?? ''),
    target_object_name: String(relationship.targetObjectName ?? ''),
    cardinality: String(relationship.cardinality ?? ''),
    summary: String(relationship.summary ?? ''),
  })

  return (params.applicationIntegrationProject?.objects ?? []).map((objectDef) => {
    const prior = existingById.get(objectDef.objectId)
    return {
      object_id: objectDef.objectId,
      name: prior?.name ?? objectDef.name,
      summary: prior?.summary ?? objectDef.summary,
      key_field: prior?.key_field ?? objectDef.keyField,
      fields: prior?.fields ?? objectDef.fields.map((field) => mapField(field as unknown as Record<string, any>)),
      relationships:
        prior?.relationships
        ?? objectDef.relationships.map((relationship) => mapRelationship(relationship as unknown as Record<string, any>)),
      sensitive_field_names: prior?.sensitive_field_names ?? [...objectDef.sensitiveFieldNames],
    }
  })
}

function buildDomainConceptBindings(params: {
  shape: ShapeRecord | null
  existing?: DeveloperDefinitionData | null
}): DeveloperDomainConceptBinding[] {
  const shapeData = ((params.shape?.data?.shape ?? params.shape?.data) as Record<string, any> | undefined) ?? {}
  const concepts = Array.isArray(shapeData.domain_concepts) ? shapeData.domain_concepts : []
  return concepts.map((concept: Record<string, any>) => {
    const conceptId = String(concept.id ?? concept.name ?? '')
    const prior = params.existing?.domain_concept_bindings.find((item) => item.concept_id === conceptId)
    return {
      id: `domain_concept_${conceptId}`,
      concept_id: conceptId,
      concept_name: String(concept.name ?? concept.id ?? 'Concept'),
      concept_detail: String(concept.meaning ?? concept.risk_note ?? ''),
      technical_representation: textOrFallback(
        prior?.technical_representation,
        `Represent ${String(concept.name ?? concept.id ?? 'this concept')} as an explicit domain concept in the generated contract and bind it to the owning service where the service design declares ownership.`,
      ),
    }
  })
}

function buildServiceTopologyBindings(params: {
  shape: ShapeRecord | null
  pmArtifacts: ArtifactRecord[]
  existing?: DeveloperDefinitionData | null
}): DeveloperServiceTopologyBinding[] {
  const shapeData = ((params.shape?.data?.shape ?? params.shape?.data) as Record<string, any> | undefined) ?? {}
  const integrationMappings = buildIntegrationFrontingMappings(params.pmArtifacts)
  const integrationServiceIds = new Set(integrationMappings.map((mapping) => mapping.service_id).filter(Boolean))
  const services = (Array.isArray(shapeData.services) ? shapeData.services : []).filter((service: Record<string, any>) => {
    if (integrationServiceIds.size === 0) return true
    const serviceId = String(service.id ?? service.name ?? '').trim()
    return integrationServiceIds.has(serviceId)
  })
  const serviceGuidance = buildAssistantGuidanceBlock(
    params.pmArtifacts,
    'assistant_service_design_candidates',
    ['svc-boundaries-explicit', 'svc-capability-surface', 'svc-coordination-edges', 'svc-approval-boundary', 'svc-observability-posture'],
  )
  const shapeTopology = services.map((service: Record<string, any>) => {
    const serviceId = String(service.id ?? service.name ?? '')
    const prior = params.existing?.service_topology_bindings.find((item) => item.service_id === serviceId)
    const sourceCapabilities = Array.isArray(service.capabilities)
      ? service.capabilities.map((value: unknown) => String(value).trim()).filter(Boolean)
      : []
    const sourceConcepts = Array.isArray(service.owns_concepts)
      ? service.owns_concepts.map((value: unknown) => String(value).trim()).filter(Boolean)
      : []
    return {
      id: `service_topology_${serviceId}`,
      service_id: serviceId,
      service_name: String(service.name ?? service.id ?? 'Service'),
      source_role: String(service.role ?? ''),
      source_capabilities: sourceCapabilities,
      source_concepts: sourceConcepts,
      formalized_capability_ids: prior?.formalized_capability_ids?.length
        ? prior.formalized_capability_ids.filter((value) => sourceCapabilities.includes(value))
        : [...sourceCapabilities],
      owned_concept_ids: prior?.owned_concept_ids?.length
        ? prior.owned_concept_ids.filter((value) => sourceConcepts.includes(value))
        : [...sourceConcepts],
      implementation_notes: seedAssistantText(prior?.implementation_notes, serviceGuidance),
    }
  })
  const existingServiceIds = new Set(shapeTopology.map((binding) => binding.service_id))
  const mappingsByService = new Map<string, DeveloperIntegrationFrontingCapabilityMapping[]>()
  for (const mapping of integrationMappings) {
    if (!mapping.service_id || existingServiceIds.has(mapping.service_id)) continue
    const bucket = mappingsByService.get(mapping.service_id) ?? []
    bucket.push(mapping)
    mappingsByService.set(mapping.service_id, bucket)
  }
  const integrationTopology = Array.from(mappingsByService.entries()).map(([serviceId, mappings]): DeveloperServiceTopologyBinding => {
    const firstMapping = mappings[0]
    const prior = params.existing?.service_topology_bindings.find((item) => item.service_id === serviceId)
    const capabilityIds = mappings.map((mapping) => mapping.capability_id)
    const conceptIds = Array.from(new Set(mappings.map((mapping) => mapping.subject_kind).filter(Boolean)))
    return {
      id: `service_topology_${serviceId}`,
      service_id: serviceId,
      service_name: prior?.service_name || firstMapping.service_name || humanize(serviceId),
      source_role: prior?.source_role || 'Governed integration-fronting service.',
      source_capabilities: capabilityIds,
      source_concepts: conceptIds,
      formalized_capability_ids: prior?.formalized_capability_ids?.length
        ? prior.formalized_capability_ids
        : capabilityIds,
      owned_concept_ids: prior?.owned_concept_ids?.length
        ? prior.owned_concept_ids
        : conceptIds,
      implementation_notes: seedAssistantText(prior?.implementation_notes, serviceGuidance),
    }
  })
  return [...shapeTopology, ...integrationTopology]
}

function buildScenarioFormalizations(params: {
  scenarios: ArtifactRecord[]
  shape: ShapeRecord | null
  existing?: DeveloperDefinitionData | null
}): DeveloperScenarioFormalization[] {
  const existingById = new Map(
    ((params.existing as { scenario_formalizations?: DeveloperScenarioFormalization[] } | null)?.scenario_formalizations ?? [])
      .map((item) => [item.scenario_id, item] as const),
  )

  return params.scenarios.map((scenario) => {
    const scenarioData = (scenario.data?.scenario ?? {}) as Record<string, any>
    const scenarioContext = (scenarioData.context ?? {}) as Record<string, any>
    const expectedBehaviors = Array.isArray(scenarioData.expected_behavior)
      ? scenarioData.expected_behavior.map((value: unknown) => String(value).trim()).filter(Boolean)
      : []
    const expectedAnipSupport = Array.isArray(scenarioData.expected_anip_support)
      ? scenarioData.expected_anip_support.map((value: unknown) => String(value).trim()).filter(Boolean)
      : []
    const prior = existingById.get(scenario.id)
    const productFormalization = deriveScenarioFormalizationFromProductDesign(scenario, params.shape)
    const defaultParticipatingServiceIds = productFormalization.participating_service_ids.length
      ? productFormalization.participating_service_ids
      : deriveServiceIds(params.shape)
    const orchestrationSteps = prior?.orchestration_steps?.length
      ? normalizeExistingOrchestrationSteps(prior.orchestration_steps as unknown[], serviceLookupForShape(params.shape))
      : productFormalization.orchestration_steps
    return {
      scenario_id: scenario.id,
      scenario_title: scenario.title,
      scenario_key: String(scenarioData.name ?? ''),
      primary_capability: prior?.primary_capability?.trim() || String(scenarioContext.capability ?? ''),
      actor_context: prior?.actor_context?.trim() || productFormalization.actor_context,
      business_scope: prior?.business_scope?.trim() || productFormalization.business_scope,
      time_scope: prior?.time_scope?.trim() || productFormalization.time_scope,
      side_effect_formalization: prior?.side_effect_formalization ?? '',
      expected_cost_formalization: prior?.expected_cost_formalization ?? '',
      budget_guard_formalization: prior?.budget_guard_formalization ?? '',
      permission_formalization: prior?.permission_formalization ?? '',
      task_tracking_formalization: prior?.task_tracking_formalization ?? '',
      participating_service_ids: prior?.participating_service_ids?.length
        ? prior.participating_service_ids
        : defaultParticipatingServiceIds,
      orchestration_steps: normalizeScenarioOrchestrationServices(orchestrationSteps, defaultParticipatingServiceIds),
      required_behaviors: prior?.required_behaviors ?? expectedBehaviors,
      required_anip_support: prior?.required_anip_support ?? expectedAnipSupport,
      implementation_notes: prior?.implementation_notes ?? '',
    }
  })
}

function hasAnySpendingRisk(requirements: RequirementsRecord | null): boolean {
  const riskProfile = requirementsData(requirements).risk_profile ?? {}
  return Object.values(riskProfile).some((entry) => Boolean((entry as Record<string, any>)?.cost_visibility_required))
}

function hasAnyIrreversibleRisk(requirements: RequirementsRecord | null): boolean {
  const riskProfile = requirementsData(requirements).risk_profile ?? {}
  return Object.values(riskProfile).some((entry) => ((entry as Record<string, any>)?.side_effect ?? 'none') === 'irreversible')
}

function normalizeServiceIds(values: string[], allowedServiceIds: string[]): string[] {
  const allowed = new Set(allowedServiceIds)
  return [...new Set(values.filter((value) => allowed.has(value)))]
}

function scoreTextMatch(source: string, target: string): number {
  const sourceTokens = normalizeText(source)
    .split(' ')
    .map((token) => token.trim())
    .filter((token) => token.length > 2)
  const targetText = normalizeText(target)
  return sourceTokens.reduce((score, token) => score + (targetText.includes(token) ? 1 : 0), 0)
}

function buildSupportedQuestionFamilyBindings(params: {
  pmArtifacts: ArtifactRecord[]
  existing?: DeveloperDefinitionData | null
  allowedServiceIds: string[]
}): DeveloperSupportedQuestionFamilyBinding[] {
  const summary = findProductSummaryArtifact(params.pmArtifacts)?.data as ProductSummaryData | undefined
  const verificationGuidance = buildAssistantGuidanceBlock(
    params.pmArtifacts,
    'assistant_verification_expectation_candidates',
    ['verification-question-family-evidence', 'verification-scenario-pack'],
  )
  const families = summary?.supported_question_families.filter((item) => item.trim().length > 0) ?? []
  if (families.length === 0) {
    const frontingMappingsByService = new Map<string, DeveloperIntegrationFrontingCapabilityMapping[]>()
    for (const mapping of buildIntegrationFrontingMappings(params.pmArtifacts)) {
      const serviceId = mapping.service_id || params.allowedServiceIds[0] || 'integration-fronting-service'
      const mappings = frontingMappingsByService.get(serviceId) ?? []
      mappings.push(mapping)
      frontingMappingsByService.set(serviceId, mappings)
    }
    return [...frontingMappingsByService.entries()].map(([serviceId, mappings], index) => {
      const id = `integration_fronting_question_family_${index}`
      const prior = params.existing?.verification.supported_question_family_bindings.find((item) => item.id === id)
      const targetServiceIds = normalizeServiceIds(
        prior?.target_service_ids?.length ? prior.target_service_ids : [serviceId],
        params.allowedServiceIds,
      )
      const capabilityLabels = mappings
        .slice(0, 4)
        .map((mapping) => mapping.capability_id)
        .join(', ')
      const serviceLabel = humanize(serviceId)
      return {
        id,
        question_family: prior?.question_family || `Governed ${serviceLabel} requests through curated integration-fronting capabilities.`,
        target_service_ids: targetServiceIds.length ? targetServiceIds : normalizeServiceIds(params.allowedServiceIds, params.allowedServiceIds),
        verification_strategy: textOrGuidanceOrFallback(
          prior?.verification_strategy,
          verificationGuidance,
          `Verify fronting capabilities such as ${capabilityLabels || serviceLabel} through generated service scenarios, backend binding checks, approval/clarification probes, and observed integration evidence.`,
        ),
        evidence_signal: textOrGuidanceOrFallback(
          prior?.evidence_signal,
          verificationGuidance,
          `Passing fronting conformance evidence for ${serviceLabel}, including bounded input handling and downstream adapter binding alignment.`,
        ),
      }
    })
  }
  return families.map((questionFamily, index) => {
    const prior = params.existing?.verification.supported_question_family_bindings.find((item) => item.id === `supported_question_family_${index}`)
    const targetServiceIds = normalizeServiceIds(
      prior?.target_service_ids?.length ? prior.target_service_ids : params.allowedServiceIds,
      params.allowedServiceIds,
    )
    return {
      id: `supported_question_family_${index}`,
      question_family: questionFamily,
      target_service_ids: targetServiceIds,
      verification_strategy: textOrGuidanceOrFallback(
        prior?.verification_strategy,
        verificationGuidance,
        `Verify "${questionFamily}" through generated service scenarios, runtime evidence, and observed service metadata for the selected service boundary.`,
      ),
      evidence_signal: textOrGuidanceOrFallback(
        prior?.evidence_signal,
        verificationGuidance,
        `Passing regression evidence and service metadata alignment for "${questionFamily}".`,
      ),
    }
  })
}

function buildBusinessGoalBindings(params: {
  pmArtifacts: ArtifactRecord[]
  existing?: DeveloperDefinitionData | null
  allowedServiceIds: string[]
}): DeveloperBusinessGoalBinding[] {
  const summary = findProductSummaryArtifact(params.pmArtifacts)?.data as ProductSummaryData | undefined
  const verificationGuidance = buildAssistantGuidanceBlock(
    params.pmArtifacts,
    'assistant_verification_expectation_candidates',
    ['verification-business-goal-checks', 'verification-success-evidence'],
  )
  const goals = summary?.business_goals.filter((item) => item.trim().length > 0) ?? []
  return goals.map((goal, index) => {
    const prior = params.existing?.verification.business_goal_bindings.find((item) => item.id === `business_goal_${index}`)
    const targetServiceIds = normalizeServiceIds(
      prior?.target_service_ids?.length ? prior.target_service_ids : params.allowedServiceIds,
      params.allowedServiceIds,
    )
    return {
      id: `business_goal_${index}`,
      business_goal: goal,
      target_service_ids: targetServiceIds,
      verification_strategy: textOrGuidanceOrFallback(
        prior?.verification_strategy,
        verificationGuidance,
        `Verify that the selected services preserve the business goal: ${goal}`,
      ),
      evidence_signal: textOrGuidanceOrFallback(
        prior?.evidence_signal,
        verificationGuidance,
        `Scenario and runtime evidence demonstrate: ${goal}`,
      ),
    }
  })
}

function buildNonGoalGuards(params: {
  pmArtifacts: ArtifactRecord[]
  existing?: DeveloperDefinitionData | null
}): DeveloperNonGoalGuard[] {
  const nonGoals = findNonGoalsArtifact(params.pmArtifacts)?.data as NonGoalsData | undefined
  const nonGoalGuidance = buildAssistantGuidanceBlock(
    params.pmArtifacts,
    'assistant_verification_expectation_candidates',
    ['verification-non-goal-guards'],
  )
  const entries = nonGoals?.entries.filter((item) => item.statement.trim().length > 0) ?? []
  return entries.map((entry, index) => {
    const prior = params.existing?.verification.non_goal_guards.find((item) => item.id === `non_goal_${index}`)
    return {
      id: `non_goal_${index}`,
      non_goal: entry.statement,
      guard_strategy: textOrGuidanceOrFallback(
        prior?.guard_strategy,
        nonGoalGuidance,
        `Preserve this non-goal as an explicit denial, restriction, clarification, or safe-stop rule where requests would otherwise cross the declared boundary.`,
      ),
      evidence_signal: textOrGuidanceOrFallback(
        prior?.evidence_signal,
        nonGoalGuidance,
        entry.rationale || `Regression evidence confirms the system does not perform: ${entry.statement}`,
      ),
    }
  })
}

function buildSuccessCriteriaChecks(params: {
  pmArtifacts: ArtifactRecord[]
  existing?: DeveloperDefinitionData | null
}): DeveloperSuccessCriteriaCheck[] {
  const successCriteria = findSuccessCriteriaArtifact(params.pmArtifacts)?.data as SuccessCriteriaData | undefined
  const successGuidance = buildAssistantGuidanceBlock(
    params.pmArtifacts,
    'assistant_verification_expectation_candidates',
    ['verification-success-evidence'],
  )
  const entries = successCriteria?.entries.filter((item) => item.statement.trim().length > 0) ?? []
  return entries.map((entry, index) => {
    const prior = params.existing?.verification.success_criteria_checks.find((item) => item.id === `success_criteria_${index}`)
    return {
      id: `success_criteria_${index}`,
      success_criterion: entry.statement,
      evidence_expectation: entry.evidence,
      review_method: entry.review_method,
      verification_strategy: textOrGuidanceOrFallback(
        prior?.verification_strategy,
        successGuidance,
        entry.review_method || entry.evidence || `Verify success criterion through saved regression and runtime evidence: ${entry.statement}`,
      ),
    }
  })
}

function buildDataAccessScenarioPackExpectation(params: {
  existing?: DeveloperDefinitionData | null
  dataAccessProject: DataAccessProjectState | null
}): DeveloperDataAccessScenarioPackExpectation {
  return {
    categories:
      params.existing?.verification.data_access_scenario_pack?.categories
      ?? params.dataAccessProject?.scenarioPack.categories
      ?? ['allowed', 'restricted', 'clarification_required'],
    target_count:
      params.existing?.verification.data_access_scenario_pack?.target_count
      ?? params.dataAccessProject?.scenarioPack.targetCount
      ?? 4,
  }
}

function buildProductAlignment(params: {
  pmArtifacts: ArtifactRecord[]
  existing?: DeveloperDefinitionData | null
}): DeveloperDefinitionData['product_alignment'] {
  const summary = findProductSummaryArtifact(params.pmArtifacts)?.data as ProductSummaryData | undefined
  return {
    governed_behavior_formalization:
      params.existing?.product_alignment.governed_behavior_formalization
      ?? summary?.governed_behavior_summary
      ?? '',
    approval_posture_formalization:
      params.existing?.product_alignment.approval_posture_formalization
      ?? summary?.approval_posture_summary
      ?? '',
  }
}

type AssistantAcceptedPayloadItem = {
  client_id: string
  title: string
  body: string
  rationale: string
  structured_data?: Record<string, any>
}

function listAcceptedAssistantItems(
  pmArtifacts: ArtifactRecord[],
  artifactType: string,
): AssistantAcceptedPayloadItem[] {
  return [...pmArtifacts]
    .filter((artifact) => String(artifact.data?.artifact_type ?? '') === artifactType)
    .sort((a, b) => new Date(a.updated_at || a.created_at).getTime() - new Date(b.updated_at || b.created_at).getTime())
    .flatMap((artifact) => {
      const payload = Array.isArray(artifact.data?.accepted_payload) ? artifact.data.accepted_payload : []
      return payload
        .filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null)
        .map((item) => ({
          client_id: String(item.client_id ?? '').trim(),
          title: String(item.title ?? '').trim(),
          body: String(item.body ?? '').trim(),
          rationale: String(item.rationale ?? '').trim(),
          structured_data: item.structured_data && typeof item.structured_data === 'object'
            ? item.structured_data as Record<string, any>
            : undefined,
        }))
        .filter((item) => item.client_id || item.title || item.body || item.rationale)
    })
}

function buildAssistantGuidanceBlock(
  pmArtifacts: ArtifactRecord[],
  artifactType: string,
  itemIds?: string[],
): string {
  const accepted = listAcceptedAssistantItems(pmArtifacts, artifactType)
    .filter((item) => !itemIds?.length || itemIds.includes(item.client_id))
  if (!accepted.length) return ''
  const lines = ['Accepted assistant guidance:']
  accepted.forEach((item) => {
    const label = item.title || item.client_id || 'Guidance'
    lines.push(item.body ? `- ${label}: ${item.body}` : `- ${label}`)
    if (item.rationale) lines.push(`  Why: ${item.rationale}`)
  })
  return lines.join('\n')
}

function seedAssistantText(existingValue: string | null | undefined, guidance: string): string {
  const current = String(existingValue ?? '').trim()
  if (current) return current
  return guidance
}

function isExactAssistantSeed(value: string | null | undefined, guidance: string): boolean {
  const current = String(value ?? '').trim()
  const expected = String(guidance ?? '').trim()
  return Boolean(current && expected && current === expected)
}

function countIfExactSeed(value: string | null | undefined, guidance: string): number {
  return isExactAssistantSeed(value, guidance) ? 1 : 0
}

export function summarizeAssistantSeededFields(
  definition: DeveloperDefinitionData | null | undefined,
  pmArtifacts: ArtifactRecord[],
): Record<DeveloperDefinitionSectionId, AssistantSeedSummary> {
  const empty = DEVELOPER_DEFINITION_SECTIONS.reduce<Record<DeveloperDefinitionSectionId, AssistantSeedSummary>>((acc, section) => {
    acc[section.id] = { count: 0, clearable: false }
    return acc
  }, {} as Record<DeveloperDefinitionSectionId, AssistantSeedSummary>)
  if (!definition) return empty

  const serviceGuidance = buildAssistantGuidanceBlock(pmArtifacts, 'assistant_service_design_candidates', [
    'svc-boundaries-explicit',
    'svc-capability-surface',
    'svc-coordination-edges',
    'svc-approval-boundary',
    'svc-observability-posture',
  ])
  incrementAssistantSeedDetail(
    empty.service_identity_topology,
    'assistant_service_design_candidates',
    'Service topology notes',
    definition.service_topology_bindings.reduce(
      (count, binding) => count + countIfExactSeed(binding.implementation_notes, serviceGuidance),
      0,
    ),
  )

  const capabilitySummaryGuidance = buildAssistantGuidanceBlock(pmArtifacts, 'assistant_capability_formalization_candidates', [
    'capability-stable-ids',
    'capability-side-effects',
    'capability-approval-rules',
    'capability-evidence-shape',
  ])
  const inputRequiredGuidance = buildAssistantGuidanceBlock(pmArtifacts, 'assistant_input_contract_candidates', ['input-required-fields'])
  const inputAllowedValueGuidance = buildAssistantGuidanceBlock(pmArtifacts, 'assistant_input_contract_candidates', ['input-allowed-values'])
  const inputContextGuidance = buildAssistantGuidanceBlock(pmArtifacts, 'assistant_input_contract_candidates', ['input-reference-shape', 'input-clarification-thresholds', 'input-approval-evidence'])
  definition.capability_formalizations.forEach((capability) => {
    incrementAssistantSeedDetail(
      empty.capability_contracts,
      'assistant_capability_formalization_candidates',
      'Capability summaries',
      countIfExactSeed(capability.summary, capabilitySummaryGuidance),
    )
    capability.inputs.forEach((input) => {
      incrementAssistantSeedDetail(empty.capability_contracts, 'assistant_input_contract_candidates', 'Input summaries', countIfExactSeed(input.summary, inputRequiredGuidance))
      incrementAssistantSeedDetail(empty.capability_contracts, 'assistant_input_contract_candidates', 'Normalization hints', countIfExactSeed(input.normalization_hint, inputAllowedValueGuidance))
      incrementAssistantSeedDetail(empty.capability_contracts, 'assistant_input_contract_candidates', 'Normalization context', countIfExactSeed(input.normalization_context, inputContextGuidance))
    })
  })

  const actorBoundaryGuidance = buildAssistantGuidanceBlock(pmArtifacts, 'assistant_runtime_policy_binding_candidates', ['policy-actor-boundaries'])
  const scopeConstraintGuidance = buildAssistantGuidanceBlock(pmArtifacts, 'assistant_runtime_policy_binding_candidates', ['policy-scope-constraints'])
  const clarificationGuidance = buildAssistantGuidanceBlock(pmArtifacts, 'assistant_runtime_policy_binding_candidates', ['policy-clarification-stops'])
  const approvalGuidance = buildAssistantGuidanceBlock(pmArtifacts, 'assistant_runtime_policy_binding_candidates', ['policy-approval-decision-point'])
  definition.actor_expectations.forEach((actor) => {
    incrementAssistantSeedDetail(empty.authority_and_approval, 'assistant_runtime_policy_binding_candidates', 'Actor boundaries', countIfExactSeed(actor.summary_formalization, actorBoundaryGuidance))
    incrementAssistantSeedDetail(empty.authority_and_approval, 'assistant_runtime_policy_binding_candidates', 'Scope constraints', countIfExactSeed(actor.visibility_formalization, scopeConstraintGuidance))
    incrementAssistantSeedDetail(empty.authority_and_approval, 'assistant_runtime_policy_binding_candidates', 'Clarification boundaries', countIfExactSeed(actor.action_formalization, clarificationGuidance))
    incrementAssistantSeedDetail(empty.authority_and_approval, 'assistant_runtime_policy_binding_candidates', 'Approval boundaries', countIfExactSeed(actor.approval_formalization, approvalGuidance))
  })
  const permissionGuidance = buildAssistantGuidanceBlock(pmArtifacts, 'assistant_runtime_policy_binding_candidates', [
    'policy-actor-boundaries',
    'policy-scope-constraints',
    'policy-clarification-stops',
    'policy-approval-decision-point',
  ])
  definition.permission_intent_bindings.forEach((binding) => {
    incrementAssistantSeedDetail(empty.authority_and_approval, 'assistant_runtime_policy_binding_candidates', 'Permission strategies', countIfExactSeed(binding.formalization_strategy, permissionGuidance))
  })
  definition.application_integration_governance.clarification_rules.forEach((rule) => {
    incrementAssistantSeedDetail(empty.authority_and_approval, 'assistant_runtime_policy_binding_candidates', 'Clarification rules', countIfExactSeed(rule.prompt_hint, clarificationGuidance))
  })
  definition.application_integration_governance.approval_rules.forEach((rule) => {
    incrementAssistantSeedDetail(empty.authority_and_approval, 'assistant_runtime_policy_binding_candidates', 'Approval rules', countIfExactSeed(rule.summary, approvalGuidance))
  })

  const dataAccessGuidance = buildAssistantGuidanceBlock(pmArtifacts, 'assistant_backend_binding_candidates', ['backend-data-access-target'])
  const integrationGuidance = buildAssistantGuidanceBlock(pmArtifacts, 'assistant_backend_binding_candidates', ['backend-integration-system', 'backend-auth-posture', 'backend-environment-target'])
  const adapterGuidance = buildAssistantGuidanceBlock(pmArtifacts, 'assistant_backend_binding_candidates', ['backend-integration-system', 'backend-service-overrides'])
  const perServiceGuidance = buildAssistantGuidanceBlock(pmArtifacts, 'assistant_backend_binding_candidates', ['backend-service-overrides'])
  incrementAssistantSeedDetail(empty.backend_bindings, 'assistant_backend_binding_candidates', 'Global data access targets', countIfExactSeed(definition.backend_bindings.data_access_target_label, dataAccessGuidance))
  incrementAssistantSeedDetail(empty.backend_bindings, 'assistant_backend_binding_candidates', 'Integration system targets', countIfExactSeed(definition.backend_bindings.application_integration_system_name, integrationGuidance))
  incrementAssistantSeedDetail(empty.backend_bindings, 'assistant_backend_binding_candidates', 'Backend templates', countIfExactSeed(definition.backend_bindings.application_integration_adapter_target, adapterGuidance))
  definition.service_backend_bindings.forEach((binding) => {
    incrementAssistantSeedDetail(empty.backend_bindings, 'assistant_backend_binding_candidates', 'Per-service backend overrides', countIfExactSeed(binding.data_access_target_label, perServiceGuidance))
    incrementAssistantSeedDetail(empty.backend_bindings, 'assistant_backend_binding_candidates', 'Per-service backend overrides', countIfExactSeed(binding.application_integration_system_name, perServiceGuidance))
    incrementAssistantSeedDetail(empty.backend_bindings, 'assistant_backend_binding_candidates', 'Per-service backend overrides', countIfExactSeed(binding.application_integration_adapter_target, perServiceGuidance))
  })

  const verificationGuidance = buildAssistantGuidanceBlock(pmArtifacts, 'assistant_verification_expectation_candidates', [
    'verification-question-family-evidence',
    'verification-scenario-pack',
  ])
  definition.verification.supported_question_family_bindings.forEach((binding) => {
    incrementAssistantSeedDetail(empty.audit_and_lineage, 'assistant_verification_expectation_candidates', 'Question family verification', countIfExactSeed(binding.verification_strategy, verificationGuidance))
    incrementAssistantSeedDetail(empty.audit_and_lineage, 'assistant_verification_expectation_candidates', 'Question family evidence', countIfExactSeed(binding.evidence_signal, verificationGuidance))
  })
  const businessGoalGuidance = buildAssistantGuidanceBlock(pmArtifacts, 'assistant_verification_expectation_candidates', [
    'verification-business-goal-checks',
    'verification-success-evidence',
  ])
  definition.verification.business_goal_bindings.forEach((binding) => {
    incrementAssistantSeedDetail(empty.audit_and_lineage, 'assistant_verification_expectation_candidates', 'Business goal verification', countIfExactSeed(binding.verification_strategy, businessGoalGuidance))
    incrementAssistantSeedDetail(empty.audit_and_lineage, 'assistant_verification_expectation_candidates', 'Business goal evidence', countIfExactSeed(binding.evidence_signal, businessGoalGuidance))
  })
  const nonGoalGuidance = buildAssistantGuidanceBlock(pmArtifacts, 'assistant_verification_expectation_candidates', ['verification-non-goal-guards'])
  definition.verification.non_goal_guards.forEach((guard) => {
    incrementAssistantSeedDetail(empty.audit_and_lineage, 'assistant_verification_expectation_candidates', 'Non-goal guardrails', countIfExactSeed(guard.guard_strategy, nonGoalGuidance))
    incrementAssistantSeedDetail(empty.audit_and_lineage, 'assistant_verification_expectation_candidates', 'Non-goal evidence', countIfExactSeed(guard.evidence_signal, nonGoalGuidance))
  })
  const successGuidance = buildAssistantGuidanceBlock(pmArtifacts, 'assistant_verification_expectation_candidates', ['verification-success-evidence'])
  definition.verification.success_criteria_checks.forEach((check) => {
    incrementAssistantSeedDetail(empty.audit_and_lineage, 'assistant_verification_expectation_candidates', 'Success criteria verification', countIfExactSeed(check.verification_strategy, successGuidance))
  })

  for (const section of DEVELOPER_DEFINITION_SECTIONS) {
    if (empty[section.id].details?.length) {
      empty[section.id].details = [...empty[section.id].details!].sort((left, right) => right.count - left.count)
    }
    empty[section.id].clearable = empty[section.id].count > 0
  }
  return empty
}

export function clearAssistantSeededFieldsForSection(
  definition: DeveloperDefinitionData,
  pmArtifacts: ArtifactRecord[],
  sectionId: DeveloperDefinitionSectionId,
): boolean {
  let changed = false
  const clearIfExact = (value: string, guidance: string): string => {
    if (isExactAssistantSeed(value, guidance)) {
      changed = true
      return ''
    }
    return value
  }

  if (sectionId === 'service_identity_topology') {
    const serviceGuidance = buildAssistantGuidanceBlock(pmArtifacts, 'assistant_service_design_candidates', [
      'svc-boundaries-explicit',
      'svc-capability-surface',
      'svc-coordination-edges',
      'svc-approval-boundary',
      'svc-observability-posture',
    ])
    definition.service_topology_bindings.forEach((binding) => {
      binding.implementation_notes = clearIfExact(binding.implementation_notes, serviceGuidance)
    })
    return changed
  }

  if (sectionId === 'capability_contracts') {
    const capabilitySummaryGuidance = buildAssistantGuidanceBlock(pmArtifacts, 'assistant_capability_formalization_candidates', [
      'capability-stable-ids',
      'capability-side-effects',
      'capability-approval-rules',
      'capability-evidence-shape',
    ])
    const inputRequiredGuidance = buildAssistantGuidanceBlock(pmArtifacts, 'assistant_input_contract_candidates', ['input-required-fields'])
    const inputAllowedValueGuidance = buildAssistantGuidanceBlock(pmArtifacts, 'assistant_input_contract_candidates', ['input-allowed-values'])
    const inputContextGuidance = buildAssistantGuidanceBlock(pmArtifacts, 'assistant_input_contract_candidates', ['input-reference-shape', 'input-clarification-thresholds', 'input-approval-evidence'])
    definition.capability_formalizations.forEach((capability) => {
      capability.summary = clearIfExact(capability.summary, capabilitySummaryGuidance)
      capability.inputs.forEach((input) => {
        input.summary = clearIfExact(input.summary, inputRequiredGuidance)
        input.normalization_hint = clearIfExact(input.normalization_hint ?? '', inputAllowedValueGuidance)
        input.normalization_context = clearIfExact(input.normalization_context ?? '', inputContextGuidance)
      })
    })
    return changed
  }

  if (sectionId === 'authority_and_approval') {
    const actorBoundaryGuidance = buildAssistantGuidanceBlock(pmArtifacts, 'assistant_runtime_policy_binding_candidates', ['policy-actor-boundaries'])
    const scopeConstraintGuidance = buildAssistantGuidanceBlock(pmArtifacts, 'assistant_runtime_policy_binding_candidates', ['policy-scope-constraints'])
    const clarificationGuidance = buildAssistantGuidanceBlock(pmArtifacts, 'assistant_runtime_policy_binding_candidates', ['policy-clarification-stops'])
    const approvalGuidance = buildAssistantGuidanceBlock(pmArtifacts, 'assistant_runtime_policy_binding_candidates', ['policy-approval-decision-point'])
    const permissionGuidance = buildAssistantGuidanceBlock(pmArtifacts, 'assistant_runtime_policy_binding_candidates', [
      'policy-actor-boundaries',
      'policy-scope-constraints',
      'policy-clarification-stops',
      'policy-approval-decision-point',
    ])
    definition.actor_expectations.forEach((actor) => {
      actor.summary_formalization = clearIfExact(actor.summary_formalization, actorBoundaryGuidance)
      actor.visibility_formalization = clearIfExact(actor.visibility_formalization, scopeConstraintGuidance)
      actor.action_formalization = clearIfExact(actor.action_formalization, clarificationGuidance)
      actor.approval_formalization = clearIfExact(actor.approval_formalization, approvalGuidance)
    })
    definition.permission_intent_bindings.forEach((binding) => {
      binding.formalization_strategy = clearIfExact(binding.formalization_strategy, permissionGuidance)
    })
    const nextClarificationRules =
      definition.application_integration_governance.clarification_rules.filter((rule) => !isExactAssistantSeed(rule.prompt_hint, clarificationGuidance))
    if (nextClarificationRules.length !== definition.application_integration_governance.clarification_rules.length) changed = true
    definition.application_integration_governance.clarification_rules = nextClarificationRules
    const nextApprovalRules =
      definition.application_integration_governance.approval_rules.filter((rule) => !isExactAssistantSeed(rule.summary, approvalGuidance))
    if (nextApprovalRules.length !== definition.application_integration_governance.approval_rules.length) changed = true
    definition.application_integration_governance.approval_rules = nextApprovalRules
    return changed
  }

  if (sectionId === 'backend_bindings') {
    const dataAccessGuidance = buildAssistantGuidanceBlock(pmArtifacts, 'assistant_backend_binding_candidates', ['backend-data-access-target'])
    const integrationGuidance = buildAssistantGuidanceBlock(pmArtifacts, 'assistant_backend_binding_candidates', ['backend-integration-system', 'backend-auth-posture', 'backend-environment-target'])
    const adapterGuidance = buildAssistantGuidanceBlock(pmArtifacts, 'assistant_backend_binding_candidates', ['backend-integration-system', 'backend-service-overrides'])
    const perServiceGuidance = buildAssistantGuidanceBlock(pmArtifacts, 'assistant_backend_binding_candidates', ['backend-service-overrides'])
    definition.backend_bindings.data_access_target_label = clearIfExact(definition.backend_bindings.data_access_target_label, dataAccessGuidance)
    definition.backend_bindings.application_integration_system_name = clearIfExact(definition.backend_bindings.application_integration_system_name, integrationGuidance)
    definition.backend_bindings.application_integration_adapter_target = clearIfExact(definition.backend_bindings.application_integration_adapter_target, adapterGuidance)
    definition.service_backend_bindings.forEach((binding) => {
      binding.data_access_target_label = clearIfExact(binding.data_access_target_label, perServiceGuidance)
      binding.application_integration_system_name = clearIfExact(binding.application_integration_system_name, perServiceGuidance)
      binding.application_integration_adapter_target = clearIfExact(binding.application_integration_adapter_target, perServiceGuidance)
    })
    return changed
  }

  if (sectionId === 'audit_and_lineage') {
    const verificationGuidance = buildAssistantGuidanceBlock(pmArtifacts, 'assistant_verification_expectation_candidates', [
      'verification-question-family-evidence',
      'verification-scenario-pack',
    ])
    const businessGoalGuidance = buildAssistantGuidanceBlock(pmArtifacts, 'assistant_verification_expectation_candidates', [
      'verification-business-goal-checks',
      'verification-success-evidence',
    ])
    const nonGoalGuidance = buildAssistantGuidanceBlock(pmArtifacts, 'assistant_verification_expectation_candidates', ['verification-non-goal-guards'])
    const successGuidance = buildAssistantGuidanceBlock(pmArtifacts, 'assistant_verification_expectation_candidates', ['verification-success-evidence'])
    definition.verification.supported_question_family_bindings.forEach((binding) => {
      binding.verification_strategy = clearIfExact(binding.verification_strategy, verificationGuidance)
      binding.evidence_signal = clearIfExact(binding.evidence_signal, verificationGuidance)
    })
    definition.verification.business_goal_bindings.forEach((binding) => {
      binding.verification_strategy = clearIfExact(binding.verification_strategy, businessGoalGuidance)
      binding.evidence_signal = clearIfExact(binding.evidence_signal, businessGoalGuidance)
    })
    definition.verification.non_goal_guards.forEach((guard) => {
      guard.guard_strategy = clearIfExact(guard.guard_strategy, nonGoalGuidance)
      guard.evidence_signal = clearIfExact(guard.evidence_signal, nonGoalGuidance)
    })
    definition.verification.success_criteria_checks.forEach((check) => {
      check.verification_strategy = clearIfExact(check.verification_strategy, successGuidance)
    })
    return changed
  }

  return false
}

function buildActorExpectationBindings(params: {
  pmArtifacts: ArtifactRecord[]
  existing?: DeveloperDefinitionData | null
}): DeveloperActorExpectationBinding[] {
  const actors = findActorModelArtifact(params.pmArtifacts)?.data as ActorModelData | undefined
  const actorBoundaryGuidance = buildAssistantGuidanceBlock(
    params.pmArtifacts,
    'assistant_runtime_policy_binding_candidates',
    ['policy-actor-boundaries'],
  )
  const scopeConstraintGuidance = buildAssistantGuidanceBlock(
    params.pmArtifacts,
    'assistant_runtime_policy_binding_candidates',
    ['policy-scope-constraints'],
  )
  const clarificationGuidance = buildAssistantGuidanceBlock(
    params.pmArtifacts,
    'assistant_runtime_policy_binding_candidates',
    ['policy-clarification-stops'],
  )
  const approvalGuidance = buildAssistantGuidanceBlock(
    params.pmArtifacts,
    'assistant_runtime_policy_binding_candidates',
    ['policy-approval-decision-point'],
  )
  const text = (value: unknown) => String(value ?? '').trim()
  const entries = actors?.actors.filter((actor) =>
    text(actor.actor_id).length > 0
    || text(actor.title).length > 0
    || text(actor.summary).length > 0
    || text(actor.visibility_expectations).length > 0
    || text(actor.action_expectations).length > 0
    || text(actor.approval_expectations).length > 0
  ) ?? []
  return entries.map((actor, index) => {
    const actorKey = text(actor.actor_id) || String(index)
    const prior = params.existing?.actor_expectations.find((item) => item.id === `actor_${actorKey}`)
    return {
      id: `actor_${actorKey}`,
      actor_id: text(actor.actor_id),
      actor_title: text(actor.title),
      summary_formalization: seedAssistantText(textOrFallback(prior?.summary_formalization, actor.summary), actorBoundaryGuidance),
      visibility_formalization: seedAssistantText(textOrFallback(prior?.visibility_formalization, actor.visibility_expectations), scopeConstraintGuidance),
      action_formalization: seedAssistantText(textOrFallback(prior?.action_formalization, actor.action_expectations), clarificationGuidance),
      approval_formalization: seedAssistantText(textOrFallback(prior?.approval_formalization, actor.approval_expectations), approvalGuidance),
    }
  })
}

function buildPermissionIntentBindings(params: {
  pmArtifacts: ArtifactRecord[]
  existing?: DeveloperDefinitionData | null
  allowedServiceIds: string[]
  capabilityFormalizations: DeveloperCapabilityFormalization[]
}): DeveloperPermissionIntentRuleBinding[] {
  const permissionIntent = findPermissionIntentArtifact(params.pmArtifacts)?.data as PermissionIntentData | undefined
  const formalizationGuidance = buildAssistantGuidanceBlock(
    params.pmArtifacts,
    'assistant_runtime_policy_binding_candidates',
    ['policy-actor-boundaries', 'policy-scope-constraints', 'policy-clarification-stops', 'policy-approval-decision-point'],
  )
  const text = (value: unknown) => String(value ?? '').trim()
  const rules = permissionIntent?.rules.filter((rule) =>
    text(rule.actor_id).length > 0
    && text(rule.business_area).length > 0,
  ) ?? []
  const capabilitiesByService = new Map<string, DeveloperCapabilityFormalization[]>()
  params.capabilityFormalizations.forEach((capability) => {
    if (!capabilitiesByService.has(capability.service_id)) capabilitiesByService.set(capability.service_id, [])
    capabilitiesByService.get(capability.service_id)?.push(capability)
  })
  function inferServiceIdsForBusinessArea(rule: PermissionIntentRule): string[] {
    const businessAreaText = [
      text(rule.business_area),
      resolveBusinessAreaLabel(text(rule.business_area), params.pmArtifacts),
      text(rule.governed_outcome),
      text(rule.notes),
    ].filter(Boolean).join(' ')
    const scored = params.allowedServiceIds
      .map((serviceId) => {
        const capabilityText = (capabilitiesByService.get(serviceId) ?? [])
          .map((capability) => [
            capability.capability_id,
            capability.title,
            capability.summary,
            capability.subject_kind,
            capability.context_type,
            capability.output_intent,
          ].join(' '))
          .join(' ')
        return {
          serviceId,
          score: scoreTextMatch(businessAreaText, `${serviceId} ${capabilityText}`),
        }
      })
      .filter((entry) => entry.score > 0)
      .sort((a, b) => b.score - a.score)
    return scored.length > 0 ? [scored[0].serviceId] : params.allowedServiceIds
  }
  function inferCapabilityIdsForPermission(
    rule: PermissionIntentRule,
    capabilities: DeveloperCapabilityFormalization[],
  ): string[] {
    const decision = permissionPolicyDecision({
      id: '',
      actor_id: text(rule.actor_id),
      business_area: text(rule.business_area),
      business_area_label: resolveBusinessAreaLabel(text(rule.business_area), params.pmArtifacts),
      access_posture: text(rule.access_posture),
      governed_outcome_type: text(rule.governed_outcome_type),
      governed_outcome: text(rule.governed_outcome),
      target_service_ids: [],
      target_capability_ids: [],
      formalization_strategy: '',
    })
    if (!['approval_required', 'clarify', 'deny'].includes(decision)) {
      return capabilities.map((capability) => capability.capability_id)
    }
    const businessAreaText = [
      text(rule.business_area),
      resolveBusinessAreaLabel(text(rule.business_area), params.pmArtifacts),
      text(rule.governed_outcome_type),
      text(rule.governed_outcome),
      text(rule.notes),
    ].filter(Boolean).join(' ')
    const scored = capabilities
      .map((capability) => ({
        capability,
        score: scoreTextMatch(businessAreaText, [
          capability.capability_id,
          capability.title,
          capability.summary,
          capability.subject_kind,
          capability.context_type,
          capability.output_intent,
          capability.intent_type,
          capability.operation_type,
          capability.side_effect_level,
        ].join(' ')),
      }))
      .filter((entry) => entry.score > 0)
      .sort((left, right) => right.score - left.score || left.capability.capability_id.localeCompare(right.capability.capability_id))
    if (scored.length === 0) return capabilities.map((capability) => capability.capability_id)
    const maxScore = scored[0]?.score ?? 0
    const threshold = Math.max(1, maxScore)
    return scored
      .filter((entry) => entry.score >= threshold)
      .map((entry) => entry.capability.capability_id)
  }
  return rules.map((rule, index) => {
    const prior = params.existing?.permission_intent_bindings.find((item) => item.id === `permission_rule_${index}`)
    const defaultTargets = inferServiceIdsForBusinessArea(rule)
    const normalizedTargets = normalizeServiceIds(
      prior?.target_service_ids?.length ? prior.target_service_ids : defaultTargets,
      params.allowedServiceIds,
    )
    const allowedCapabilityIds = params.capabilityFormalizations
      .filter((capability) => normalizedTargets.includes(capability.service_id))
      .map((capability) => capability.capability_id)
    const defaultCapabilityIds = inferCapabilityIdsForPermission(
      rule,
      params.capabilityFormalizations.filter((capability) => normalizedTargets.includes(capability.service_id)),
    ).filter((capabilityId) => allowedCapabilityIds.includes(capabilityId))
    const priorCapabilityIds = prior?.target_capability_ids?.filter((capabilityId) => allowedCapabilityIds.includes(capabilityId)) ?? []
    const priorLooksLikeBroadDefault = priorCapabilityIds.length > 0 && priorCapabilityIds.length === allowedCapabilityIds.length
    const defaultStrategy = [
      `${text(rule.actor_id) || 'Actor'} ${text(rule.access_posture) || 'governed'} access to ${resolveBusinessAreaLabel(text(rule.business_area), params.pmArtifacts) || text(rule.business_area)} should return ${text(rule.governed_outcome_type) || 'a governed outcome'}.`,
      text(rule.governed_outcome),
      text(rule.notes),
    ].filter(Boolean).join(' ')
    return {
      id: `permission_rule_${index}`,
      actor_id: text(rule.actor_id),
      business_area: text(rule.business_area),
      business_area_label: resolveBusinessAreaLabel(text(rule.business_area), params.pmArtifacts),
      access_posture: text(rule.access_posture),
      governed_outcome_type: text(rule.governed_outcome_type),
      governed_outcome: text(rule.governed_outcome),
      target_service_ids: normalizedTargets,
      target_capability_ids: Array.from(new Set(
        (priorCapabilityIds.length && !priorLooksLikeBroadDefault ? priorCapabilityIds : defaultCapabilityIds.length ? defaultCapabilityIds : allowedCapabilityIds)
          .filter((capabilityId) => allowedCapabilityIds.includes(capabilityId)),
      )),
      formalization_strategy: seedAssistantText(textOrFallback(prior?.formalization_strategy, defaultStrategy), formalizationGuidance),
    }
  })
}

function buildCompositionRuleBindings(params: {
  pmArtifacts: ArtifactRecord[]
  scenarios: ArtifactRecord[]
  existing?: DeveloperDefinitionData | null
}): DeveloperCompositionRuleBinding[] {
  const summary = findProductSummaryArtifact(params.pmArtifacts)?.data as ProductSummaryData | undefined
  const rules = summary?.multi_step_composition_rules.filter((item) => item.trim().length > 0) ?? []
  const allowedScenarioIds = new Set(params.scenarios.map((scenario) => scenario.id))
  const allScenarioIds = [...allowedScenarioIds]
  return rules.map((rule, index) => {
    const prior = params.existing?.composition_rules.find((item) => item.id === `composition_rule_${index}`)
    const priorScenarioIds = [...new Set((prior?.affected_scenario_ids ?? []).filter((id) => allowedScenarioIds.has(id)))]
    return {
      id: `composition_rule_${index}`,
      rule,
      affected_scenario_ids: priorScenarioIds.length ? priorScenarioIds : allScenarioIds,
      formalization_strategy: textOrFallback(
        prior?.formalization_strategy,
        `Preserve this product-wide composition rule by keeping each participating service boundary, intermediate result, and stop condition explicit in scenario orchestration: ${rule}`,
      ),
    }
  })
}

function assistantCapabilityInputToFormalization(input: Record<string, any>): DeveloperCapabilityInputFormalization {
  return withInputResolution({
    input_name: String(input.input_name ?? input.name ?? '').trim(),
    input_type: String(input.input_type ?? input.type ?? 'string').trim() || 'string',
    required: Boolean(input.required),
    summary: String(input.summary ?? input.description ?? '').trim(),
    default_value: input.default_value == null ? '' : String(input.default_value),
    allowed_values: Array.isArray(input.allowed_values) ? input.allowed_values.map((value: unknown) => String(value)) : [],
    semantic_type: String(input.semantic_type ?? input.context_type ?? '').trim(),
    input_format: String(input.input_format ?? input.format ?? '').trim(),
    validation_pattern: String(input.validation_pattern ?? input.pattern ?? '').trim(),
    clarification_hint: String(input.clarification_hint ?? '').trim(),
    entity_reference: Boolean(input.entity_reference),
    reference_catalog: Array.isArray(input.reference_catalog) ? input.reference_catalog.map((value: unknown) => String(value)) : [],
    semantic_aliases: Array.isArray(input.semantic_aliases) ? input.semantic_aliases.map((value: unknown) => String(value)) : [],
    normalization_hint: String(input.normalization_hint ?? '').trim(),
    normalization_context: String(input.normalization_context ?? '').trim(),
    allowed_value_semantics: Array.isArray(input.allowed_value_semantics)
      ? input.allowed_value_semantics.map((entry: Record<string, any>) => ({
          value: String(entry.value ?? ''),
          aliases: Array.isArray(entry.aliases) ? entry.aliases.map((value: unknown) => String(value)) : [],
        }))
      : [],
    resolution: normalizeInputResolution(input.resolution),
    catalog_ref: String(input.catalog_ref ?? '').trim(),
  })
}

const PLACEHOLDER_CAPABILITY_TEXT_MARKERS = [
  'placeholder:',
  'review_needed',
  'needs explicit',
  'needs source',
  'needs review',
  'tbd',
  'todo',
]

function assistantCapabilityLooksPlaceholder(capability: Record<string, any>): boolean {
  const text = [
    capability.title,
    capability.summary,
    capability.description,
    capability.backend_operation,
    capability.output_shape,
  ]
    .map((value) => String(value ?? '').toLowerCase())
    .join(' ')
  return PLACEHOLDER_CAPABILITY_TEXT_MARKERS.some((marker) => text.includes(marker))
}

function assistantCapabilityLooksInputOnly(capability: Record<string, any>): boolean {
  const inputs = Array.isArray(capability.inputs) ? capability.inputs : []
  if (inputs.length === 0) return false
  const summary = String(capability.summary ?? capability.description ?? '').trim().toLowerCase()
  const serviceId = String(capability.service_id ?? '').trim()
  const pathTemplate = String(capability.path_template ?? '').trim()
  const outputShape = String(capability.output_shape ?? '').trim().toLowerCase()
  const outputIntent = String(capability.output_intent ?? '').trim().toLowerCase()
  const subjectKind = String(capability.subject_kind ?? '').trim()
  const contextType = String(capability.context_type ?? '').trim()
  const weakSummary = !summary || summary.startsWith('reviewed contract for ')
  const weakOutput = !outputShape || outputShape === 'governed_result'
  const weakIntent = !outputIntent || outputIntent === 'governed_result'
  return weakSummary && !serviceId && !pathTemplate && weakOutput && weakIntent && !subjectKind && !contextType
}

function extractAssistantCapabilityCandidates(pmArtifacts: ArtifactRecord[]): Map<string, Partial<DeveloperCapabilityFormalization>> {
  const candidates = new Map<string, Partial<DeveloperCapabilityFormalization>>()
  const reviewedInputCandidates = new Map<string, DeveloperCapabilityInputFormalization[]>()
  const orderedArtifacts = [...pmArtifacts].sort((a, b) => {
    const aTime = Date.parse(String(a.updated_at ?? a.created_at ?? '')) || 0
    const bTime = Date.parse(String(b.updated_at ?? b.created_at ?? '')) || 0
    if (aTime !== bTime) return aTime - bTime
    return String(a.id ?? '').localeCompare(String(b.id ?? ''))
  })

  function structuredCapabilityEntries(item: Record<string, any>): Record<string, any>[] {
    const structured = item.structured_data && typeof item.structured_data === 'object'
      ? item.structured_data as Record<string, any>
      : item
    const result: Record<string, any>[] = []
    for (const key of ['capabilities', 'capability_contracts', 'input_contracts', 'capability_inputs']) {
      const value = structured[key]
      if (Array.isArray(value)) {
        result.push(...value.filter((entry): entry is Record<string, any> =>
          !!entry && typeof entry === 'object',
        ))
      }
    }
    if (String(structured.capability_id ?? '').trim() && Array.isArray(structured.inputs)) {
      result.push(structured)
    }
    return result
  }

  function ingestProposalItems(items: unknown, options: { inputContractsOnly?: boolean } = {}): void {
    if (!Array.isArray(items)) return
    items.forEach((item: Record<string, any>) => {
      const capabilities = structuredCapabilityEntries(item)
      capabilities.forEach((capability: Record<string, any>) => {
        const capabilityId = String(capability.capability_id ?? '').trim()
        if (!capabilityId) return
        const inputs = Array.isArray(capability.inputs)
          ? capability.inputs
              .map((input: Record<string, any>) => assistantCapabilityInputToFormalization(input))
              .filter((input: DeveloperCapabilityInputFormalization) => input.input_name.length > 0)
          : []
        if (assistantCapabilityLooksPlaceholder(capability)) return
        if (assistantCapabilityLooksInputOnly(capability)) {
          if (inputs.length > 0) reviewedInputCandidates.set(capabilityId, inputs)
          return
        }
        if (options.inputContractsOnly) {
          if (inputs.length > 0) reviewedInputCandidates.set(capabilityId, inputs)
          return
        }
        candidates.set(capabilityId, {
          capability_id: capabilityId,
          kind: capability.kind === 'composed' ? 'composed' : 'atomic',
          composition: capability.composition && typeof capability.composition === 'object'
            ? capability.composition as DeveloperComposition
            : null,
          grant_policy: capability.grant_policy && typeof capability.grant_policy === 'object'
            ? capability.grant_policy as DeveloperGrantPolicy
            : null,
          business_effects: capability.business_effects && typeof capability.business_effects === 'object'
            ? {
                produces: Array.isArray(capability.business_effects.produces)
                  ? capability.business_effects.produces.map((value: unknown) => String(value))
                  : [],
                does_not_produce: Array.isArray(capability.business_effects.does_not_produce)
                  ? capability.business_effects.does_not_produce.map((value: unknown) => String(value))
                  : [],
              }
            : undefined,
          implementation_fit: capability.implementation_fit && typeof capability.implementation_fit === 'object'
            ? capability.implementation_fit as DeveloperImplementationFit
            : undefined,
          minimum_scope: Array.isArray(capability.minimum_scope)
            ? capability.minimum_scope.map((value: unknown) => String(value).trim()).filter(Boolean)
            : [],
          title: String(capability.title ?? '').trim(),
          summary: String(capability.summary ?? '').trim(),
          service_id: String(capability.service_id ?? '').trim(),
          intent_type: String(capability.intent_type ?? '').trim(),
          operation_type: String(capability.operation_type ?? '').trim(),
          side_effect_level: String(capability.side_effect_level ?? '').trim(),
          subject_kind: String(capability.subject_kind ?? '').trim(),
          context_type: String(capability.context_type ?? '').trim(),
          output_intent: String(capability.output_intent ?? '').trim(),
          backend_operation: String(capability.backend_operation ?? '').trim(),
          path_template: String(capability.path_template ?? '').trim(),
          output_shape: String(capability.output_shape ?? '').trim(),
          entity_targeted: capability.entity_targeted === true || capability.entity_targeted === 'true',
          inputs,
        })
      })
    })
  }

  orderedArtifacts.forEach((artifact) => {
    const data = artifact.data as Record<string, any> | undefined
    if (data?.artifact_type === 'assistant_capability_formalization_candidates') {
      ingestProposalItems(Array.isArray(data.accepted_payload) ? data.accepted_payload : data.source_proposal?.items)
      return
    }
    if (data?.artifact_type === 'assistant_input_contract_candidates') {
      ingestProposalItems(Array.isArray(data.accepted_payload) ? data.accepted_payload : data.source_proposal?.items, { inputContractsOnly: true })
      return
    }
    if (data?.artifact_type !== 'assistant_developer_design_draft_bundle') return
    const sections = Array.isArray(data.bundle?.sections) ? data.bundle.sections : []
    sections
      .filter((section: Record<string, any>) =>
        ['capability_formalization', 'input_contracts'].includes(String(section.id ?? ''))
        && section.status !== 'failed'
        && ['capability_formalization', 'input_contracts'].includes(String(section.envelope?.proposal?.artifact_type ?? '')),
      )
      .forEach((section: Record<string, any>) =>
        ingestProposalItems(section.envelope?.proposal?.items, {
          inputContractsOnly: section.id === 'input_contracts',
        }),
      )
  })
  reviewedInputCandidates.forEach((inputs, capabilityId) => {
    const existing = candidates.get(capabilityId)
    candidates.set(capabilityId, {
      ...(existing ?? {}),
      capability_id: capabilityId,
      inputs,
    })
  })
  return candidates
}

function buildCapabilityFormalizations(params: {
  existing?: DeveloperDefinitionData | null
  shape: ShapeRecord | null
  pmArtifacts: ArtifactRecord[]
  scenarios: DeveloperScenarioFormalization[]
  defaultNamespace: string
  applicationIntegrationProject: ApplicationIntegrationProjectState | null
  dataAccessProject: DataAccessProjectState | null
}) {
  const existingById = new Map(
    (params.existing?.capability_formalizations ?? []).map((item) => [item.id, item] as const),
  )
  const capabilityOwnerById = new Map<string, string>()
  const shapeData = ((params.shape?.data?.shape ?? params.shape?.data) as Record<string, any> | undefined) ?? {}
  const shapeServices = Array.isArray(shapeData.services) ? shapeData.services : []
  const shapeCapabilityContractById = new Map<string, Record<string, any>>(
    (Array.isArray(shapeData.capability_contracts) ? shapeData.capability_contracts : [])
      .map((contract: Record<string, any>) => [String(contract.id ?? contract.capability_id ?? '').trim(), contract] as const)
      .filter(([capabilityId]) => capabilityId.length > 0),
  )
  shapeServices.forEach((service: Record<string, any>) => {
    const serviceId = String(service.id ?? service.name ?? '').trim()
    if (!serviceId || !Array.isArray(service.capabilities)) return
    service.capabilities
      .map((value: unknown) => String(value).trim())
      .filter(Boolean)
      .forEach((capabilityId: string) => {
        if (!capabilityOwnerById.has(capabilityId)) capabilityOwnerById.set(capabilityId, serviceId)
      })
  })
  ;(params.existing?.service_topology_bindings ?? []).forEach((binding) => {
    binding.formalized_capability_ids
      .map((value) => String(value).trim())
      .filter(Boolean)
      .forEach((capabilityId) => {
        capabilityOwnerById.set(capabilityId, binding.service_id)
      })
  })
  const capabilitySummaryGuidance = buildAssistantGuidanceBlock(
    params.pmArtifacts,
    'assistant_capability_formalization_candidates',
    ['capability-stable-ids', 'capability-side-effects', 'capability-approval-rules', 'capability-evidence-shape'],
  )
  const inputRequiredGuidance = buildAssistantGuidanceBlock(
    params.pmArtifacts,
    'assistant_input_contract_candidates',
    ['input-required-fields'],
  )
  const inputAllowedValueGuidance = buildAssistantGuidanceBlock(
    params.pmArtifacts,
    'assistant_input_contract_candidates',
    ['input-allowed-values'],
  )
  const inputContextGuidance = buildAssistantGuidanceBlock(
    params.pmArtifacts,
    'assistant_input_contract_candidates',
    ['input-reference-shape', 'input-clarification-thresholds', 'input-approval-evidence'],
  )

  function cloneInputs(inputs: DeveloperCapabilityInputFormalization[] | undefined | null): DeveloperCapabilityInputFormalization[] {
    return (inputs ?? []).map((input) => withInputResolution({
      input_name: input.input_name,
      input_type: input.input_type,
      required: Boolean(input.required),
      summary: seedAssistantText(input.summary, inputRequiredGuidance),
      default_value: input.default_value ?? '',
      allowed_values: [...(input.allowed_values ?? [])],
      semantic_type: input.semantic_type ?? '',
      input_format: input.input_format ?? '',
      validation_pattern: input.validation_pattern ?? '',
      clarification_hint: input.clarification_hint ?? '',
      entity_reference: Boolean(input.entity_reference),
      reference_catalog: [...(input.reference_catalog ?? [])],
      semantic_aliases: [...(input.semantic_aliases ?? [])],
      normalization_hint: seedAssistantText(input.normalization_hint, inputAllowedValueGuidance),
      normalization_context: seedAssistantText(input.normalization_context, inputContextGuidance),
      allowed_value_semantics: (input.allowed_value_semantics ?? []).map((entry) => ({
        value: entry.value,
        aliases: [...(entry.aliases ?? [])],
      })),
      resolution: normalizeInputResolution(input.resolution),
      catalog_ref: input.catalog_ref ?? '',
    }))
  }

  function mapApplicationIntegrationInputs(capability: ApplicationIntegrationProjectState['capabilities'][number]) {
    const fromRequired = capability.requiredInputs.map<DeveloperCapabilityInputFormalization>((input) => withInputResolution({
      input_name: input.inputName,
      input_type: input.inputType,
      required: true,
      summary: input.summary ?? '',
      default_value: '',
      allowed_values: [],
      semantic_type: '',
      input_format: '',
      validation_pattern: '',
      clarification_hint: '',
      entity_reference: false,
      reference_catalog: [],
      semantic_aliases: [],
      normalization_hint: '',
      normalization_context: '',
      allowed_value_semantics: [],
    }))
    const fromOptional = capability.optionalInputs.map<DeveloperCapabilityInputFormalization>((input) => withInputResolution({
      input_name: input.inputName,
      input_type: input.inputType,
      required: false,
      summary: input.summary ?? '',
      default_value: '',
      allowed_values: [],
      semantic_type: '',
      input_format: '',
      validation_pattern: '',
      clarification_hint: '',
      entity_reference: false,
      reference_catalog: [],
      semantic_aliases: [],
      normalization_hint: '',
      normalization_context: '',
      allowed_value_semantics: [],
    }))
    return [...fromRequired, ...fromOptional]
  }

  function mapDataAccessInputs(capability: NonNullable<DataAccessProjectState['serviceContract']>['capabilities'][number]) {
    const fromRequired = capability.requiredInputs.map<DeveloperCapabilityInputFormalization>((input) => withInputResolution({
      input_name: input.inputName,
      input_type: input.inputType,
      required: true,
      summary: input.summary ?? '',
      default_value: '',
      allowed_values: [],
      semantic_type: '',
      input_format: '',
      validation_pattern: '',
      clarification_hint: '',
      entity_reference: false,
      reference_catalog: [],
      semantic_aliases: [],
      normalization_hint: '',
      normalization_context: '',
      allowed_value_semantics: [],
    }))
    const fromOptional = capability.optionalInputs.map<DeveloperCapabilityInputFormalization>((input) => withInputResolution({
      input_name: input.inputName,
      input_type: input.inputType,
      required: false,
      summary: input.summary ?? '',
      default_value: '',
      allowed_values: [],
      semantic_type: '',
      input_format: '',
      validation_pattern: '',
      clarification_hint: '',
      entity_reference: false,
      reference_catalog: [],
      semantic_aliases: [],
      normalization_hint: '',
      normalization_context: '',
      allowed_value_semantics: [],
    }))
    return [...fromRequired, ...fromOptional]
  }

  function contractInputToFormalization(input: Record<string, any>, requiredFallback: boolean): DeveloperCapabilityInputFormalization {
    const inputName = String(input.input_name ?? input.name ?? '').trim()
    const summary = String(input.summary ?? input.description ?? '').trim()
    return withInputResolution({
      input_name: inputName,
      input_type: String(input.input_type ?? input.type ?? 'string').trim() || 'string',
      required: input.required == null ? requiredFallback : Boolean(input.required),
      summary,
      default_value: input.default_value == null ? '' : String(input.default_value),
      allowed_values: Array.isArray(input.allowed_values) ? input.allowed_values.map((value) => String(value)) : [],
      semantic_type: String(input.semantic_type ?? '').trim(),
      input_format: String(input.input_format ?? input.format ?? '').trim(),
      validation_pattern: String(input.validation_pattern ?? input.pattern ?? '').trim(),
      clarification_hint: String(input.clarification_hint ?? '').trim(),
      entity_reference: Boolean(input.entity_reference),
      reference_catalog: Array.isArray(input.reference_catalog) ? input.reference_catalog.map((value) => String(value)) : [],
      semantic_aliases: Array.isArray(input.semantic_aliases) ? input.semantic_aliases.map((value) => String(value)) : [],
      normalization_hint: String(input.normalization_hint ?? '').trim(),
      normalization_context: String(input.normalization_context ?? '').trim(),
      allowed_value_semantics: Array.isArray(input.allowed_value_semantics)
        ? input.allowed_value_semantics.map((entry: Record<string, any>) => ({
            value: String(entry.value ?? ''),
            aliases: Array.isArray(entry.aliases) ? entry.aliases.map((value) => String(value)) : [],
          }))
        : [],
      resolution: normalizeInputResolution(input.resolution),
      catalog_ref: String(input.catalog_ref ?? '').trim(),
    })
  }

  function mapShapeContractInputs(contract: Record<string, any> | undefined): DeveloperCapabilityInputFormalization[] {
    if (!contract) return []
    if (Array.isArray(contract.inputs) && contract.inputs.length > 0) {
      return contract.inputs
        .map((input: Record<string, any>) => contractInputToFormalization(input, false))
        .filter((input) => input.input_name.length > 0)
    }
    const requiredInputs = Array.isArray(contract.required_inputs) ? contract.required_inputs : []
    const optionalInputs = Array.isArray(contract.optional_inputs) ? contract.optional_inputs : []
    return [
      ...requiredInputs.map((input) => contractInputToFormalization({ input_name: input, required: true }, true)),
      ...optionalInputs.map((input) => contractInputToFormalization({ input_name: input, required: false }, false)),
    ].filter((input) => input.input_name.length > 0)
  }

  function reviewedInputsOrFallback(
    priorInputs: DeveloperCapabilityInputFormalization[] | undefined,
    assistantInputs: DeveloperCapabilityInputFormalization[] | undefined,
    fallbackInputs: DeveloperCapabilityInputFormalization[],
  ): DeveloperCapabilityInputFormalization[] {
    if (assistantInputs?.length) return cloneInputs(assistantInputs)
    if (priorInputs?.length) return cloneInputs(priorInputs)
    return fallbackInputs
  }

  function mapShapeBusinessEffects(contract: Record<string, any> | undefined): DeveloperBusinessEffects | undefined {
    const effects = contract?.business_effects && typeof contract.business_effects === 'object'
      ? contract.business_effects as Record<string, unknown>
      : null
    const produces = Array.isArray(effects?.produces)
      ? effects.produces.map((value: unknown) => String(value).trim()).filter(Boolean)
      : []
    const doesNotProduce = Array.isArray(effects?.does_not_produce)
      ? effects.does_not_produce.map((value: unknown) => String(value).trim()).filter(Boolean)
      : []
    if (produces.length === 0 && doesNotProduce.length === 0) return undefined
    return {
      produces: Array.from(new Set(produces)),
      does_not_produce: Array.from(new Set(doesNotProduce)),
    }
  }

  function mapShapeGrantPolicy(contract: Record<string, any> | undefined): DeveloperGrantPolicy | null {
    return contract?.grant_policy && typeof contract.grant_policy === 'object'
      ? contract.grant_policy as DeveloperGrantPolicy
      : null
  }

  function mapShapeMinimumScope(contract: Record<string, any> | undefined): string[] {
    if (!Array.isArray(contract?.minimum_scope)) return []
    return Array.from(new Set(contract.minimum_scope.map((value: unknown) => String(value).trim()).filter(Boolean)))
  }

  const assistantCapabilityById = extractAssistantCapabilityCandidates(params.pmArtifacts)
  const integrationFrontingMappings = buildIntegrationFrontingMappings(params.pmArtifacts)
  const integrationFrontingMappingByCapabilityId = new Map(
    integrationFrontingMappings.map((mapping) => [mapping.capability_id, mapping] as const),
  )

  function priorLooksGeneratedCapabilityValue(capabilityId: string, value: string | null | undefined): boolean {
    const text = String(value ?? '').trim()
    if (!text) return true
    return text === capabilityId || normalizeText(text) === normalizeText(capabilityId) || normalizeText(text) === normalizeText(humanize(capabilityId))
  }

function priorLooksPlaceholderCapabilityValue(value: string | null | undefined): boolean {
  const text = String(value ?? '').trim().toLowerCase()
  if (!text) return false
  if (/^reviewed contract for\b/.test(text)) return true
  return PLACEHOLDER_CAPABILITY_TEXT_MARKERS.some((marker) => text.includes(marker))
}

  function textOrAssistant(
    priorValue: string | null | undefined,
    assistantValue: string | null | undefined,
    capabilityId: string,
    fallback: string,
  ): string {
    const priorText = String(priorValue ?? '').trim()
    const assistantText = String(assistantValue ?? '').trim()
    if (!assistantText) return priorLooksPlaceholderCapabilityValue(priorText) ? fallback : priorText || fallback
    if (!priorLooksGeneratedCapabilityValue(capabilityId, priorText) && !priorLooksPlaceholderCapabilityValue(priorText)) return priorText
    return assistantText
  }

  function enumOrAssistant(
    priorValue: string | null | undefined,
    assistantValue: string | null | undefined,
    fallback: string,
  ): string {
    const priorText = String(priorValue ?? '').trim()
    const assistantText = String(assistantValue ?? '').trim()
    if (!assistantText) return priorText || fallback
    if (!priorText || priorText === 'read' || priorText === 'read_only' || priorText === fallback) return assistantText
    return priorText
  }

  function booleanOrAssistant(
    priorValue: boolean | undefined,
    assistantValue: boolean | string | undefined,
    fallback = false,
  ): boolean {
    if (priorValue !== undefined && priorValue !== fallback) return priorValue
    if (assistantValue === true || assistantValue === 'true') return true
    if (assistantValue === false || assistantValue === 'false') return false
    return priorValue ?? fallback
  }

  function capabilityTokens(capabilityId: string): string[] {
    const raw = normalizeText(capabilityId.split('.').pop() || capabilityId)
    return raw
      .split(' ')
      .map((token) => token.trim())
      .filter((token) => token.length > 2 && !['service', 'capability'].includes(token))
  }

  function serviceResponsibilitySummary(service: Record<string, any>, capabilityId: string): string {
    const stringList = (value: unknown): string[] =>
      Array.isArray(value) ? value.map((item) => String(item).trim()).filter(Boolean) : []
    const candidates = [
      ...stringList(service.responsibilities),
      String(service.role ?? '').trim(),
    ].filter(Boolean)
    if (candidates.length === 0) return ''
    const tokens = capabilityTokens(capabilityId)
    if (tokens.length === 0) return candidates[0] ?? ''
    const scored = candidates
      .map((candidate) => {
        const normalized = normalizeText(candidate)
        const score = tokens.reduce((count, token) => count + (normalized.includes(token) ? 1 : 0), 0)
        return { candidate, score }
      })
      .filter((entry) => entry.score > 0)
      .sort((a, b) => b.score - a.score)
    return scored[0]?.candidate ?? candidates[0] ?? ''
  }

  const applicationCapabilities: DeveloperCapabilityFormalization[] =
    (params.applicationIntegrationProject?.capabilities ?? []).map((capability) => {
      const id = `application_integration:${capability.capabilityId}`
      const prior = existingById.get(id)
      const assistant = assistantCapabilityById.get(capability.capabilityId)
      return {
        id,
        kind: prior?.kind ?? 'atomic',
        composition: prior?.composition ?? null,
        grant_policy: prior?.grant_policy ?? null,
        source_kind: 'application_integration',
        service_id: prior?.service_id || capabilityOwnerById.get(capability.capabilityId) || '',
        capability_id: prior?.capability_id || capability.capabilityId,
        title: textOrAssistant(prior?.title, assistant?.title, capability.capabilityId, capability.title),
        summary: textOrAssistant(prior?.summary, assistant?.summary, capability.capabilityId, capability.summary || capabilitySummaryGuidance),
        entity_targeted: booleanOrAssistant(prior?.entity_targeted, assistant?.entity_targeted, false),
        subject_kind: textOrAssistant(prior?.subject_kind, assistant?.subject_kind, capability.capabilityId, ''),
        context_type: textOrAssistant(prior?.context_type, assistant?.context_type, capability.capabilityId, ''),
        output_intent: textOrAssistant(prior?.output_intent, assistant?.output_intent, capability.capabilityId, ''),
        intent_type: enumOrAssistant(prior?.intent_type, assistant?.intent_type, capability.intentType),
        operation_type: enumOrAssistant(prior?.operation_type, assistant?.operation_type, capability.operationType),
        side_effect_level: enumOrAssistant(prior?.side_effect_level, assistant?.side_effect_level, capability.sideEffectLevel),
        backend_operation: textOrAssistant(prior?.backend_operation, assistant?.backend_operation, capability.capabilityId, capability.backendMapping.backendOperation),
        path_template: textOrAssistant(prior?.path_template, assistant?.path_template, capability.capabilityId, capability.backendMapping.pathTemplate),
        output_shape: textOrAssistant(prior?.output_shape, assistant?.output_shape, capability.capabilityId, capability.outputShape),
        inputs: reviewedInputsOrFallback(prior?.inputs, assistant?.inputs, mapApplicationIntegrationInputs(capability)),
      }
    })

  const dataAccessCapabilities: DeveloperCapabilityFormalization[] =
    (params.dataAccessProject?.serviceContract?.capabilities ?? []).map((capability) => {
      const id = `data_access:${capability.capabilityId}`
      const prior = existingById.get(id)
      const assistant = assistantCapabilityById.get(capability.capabilityId)
      return {
        id,
        kind: prior?.kind ?? 'atomic',
        composition: prior?.composition ?? null,
        grant_policy: prior?.grant_policy ?? null,
        source_kind: 'data_access',
        service_id: params.dataAccessProject?.serviceContract?.serviceId ?? '',
        capability_id: prior?.capability_id || capability.capabilityId,
        title: textOrAssistant(prior?.title, assistant?.title, capability.capabilityId, capability.title),
        summary: textOrAssistant(prior?.summary, assistant?.summary, capability.capabilityId, capability.summary || capabilitySummaryGuidance),
        entity_targeted: booleanOrAssistant(prior?.entity_targeted, assistant?.entity_targeted, false),
        subject_kind: textOrAssistant(prior?.subject_kind, assistant?.subject_kind, capability.capabilityId, ''),
        context_type: textOrAssistant(prior?.context_type, assistant?.context_type, capability.capabilityId, ''),
        output_intent: textOrAssistant(prior?.output_intent, assistant?.output_intent, capability.capabilityId, ''),
        intent_type: enumOrAssistant(prior?.intent_type, assistant?.intent_type, ''),
        operation_type: enumOrAssistant(prior?.operation_type, assistant?.operation_type, capability.operationType),
        side_effect_level: enumOrAssistant(prior?.side_effect_level, assistant?.side_effect_level, capability.sideEffectLevel),
        backend_operation: textOrAssistant(prior?.backend_operation, assistant?.backend_operation, capability.capabilityId, capability.backendOperation),
        path_template: textOrAssistant(prior?.path_template, assistant?.path_template, capability.capabilityId, ''),
        output_shape: textOrAssistant(prior?.output_shape, assistant?.output_shape, capability.capabilityId, ''),
        inputs: reviewedInputsOrFallback(prior?.inputs, assistant?.inputs, mapDataAccessInputs(capability)),
      }
    })

  const shapeCapabilities: DeveloperCapabilityFormalization[] = shapeServices.flatMap((service: Record<string, any>) => {
    const serviceId = String(service.id ?? service.name ?? '').trim()
    if (!serviceId || !Array.isArray(service.capabilities)) return []
    return service.capabilities
      .map((value: unknown) => String(value).trim())
      .filter(Boolean)
      .filter((capabilityId: string) =>
        !applicationCapabilities.some((capability) => capability.capability_id === capabilityId)
        && !dataAccessCapabilities.some((capability) => capability.capability_id === capabilityId),
      )
      .map((capabilityId: string): DeveloperCapabilityFormalization => {
        const id = `contract_native:${capabilityId}`
        const prior = existingById.get(id)
        const contract = shapeCapabilityContractById.get(capabilityId)
        const assistant = assistantCapabilityById.get(capabilityId)
        const frontingMapping = integrationFrontingMappingByCapabilityId.get(capabilityId)
        const assistantDeclaresComposition = assistant?.kind === 'composed' || Boolean(assistant?.composition?.steps?.length)
        const sideEffectType = String(contract?.side_effect_type ?? contract?.side_effect_level ?? '').trim()
        const approvalRequired = Array.isArray(contract?.approval_required_when) && contract.approval_required_when.length > 0
        const serviceSummary = serviceResponsibilitySummary(service, capabilityId)
        return {
          id,
          kind: assistantDeclaresComposition ? 'composed' : prior?.kind ?? assistant?.kind ?? 'atomic',
          composition: assistantDeclaresComposition ? assistant?.composition ?? null : prior?.composition ?? assistant?.composition ?? null,
          grant_policy: prior?.grant_policy ?? assistant?.grant_policy ?? grantPolicyFromFrontingMapping(frontingMapping) ?? mapShapeGrantPolicy(contract),
          source_kind: frontingMapping ? 'application_integration' : 'contract_native',
          service_id: frontingMapping?.service_id || serviceId,
          capability_id: capabilityId,
          title: textOrAssistant(prior?.title, assistant?.title, capabilityId, humanize(capabilityId)),
          summary: textOrAssistant(prior?.summary, assistant?.summary, capabilityId, frontingMapping?.intent || String(contract?.purpose ?? contract?.summary ?? '').trim() || serviceSummary || capabilitySummaryGuidance || humanize(capabilityId)),
          entity_targeted: booleanOrAssistant(prior?.entity_targeted, assistant?.entity_targeted, false),
          subject_kind: textOrAssistant(prior?.subject_kind, assistant?.subject_kind, capabilityId, frontingMapping?.subject_kind || ''),
          context_type: textOrAssistant(prior?.context_type, assistant?.context_type, capabilityId, frontingMapping?.context_type || ''),
          output_intent: textOrAssistant(prior?.output_intent, assistant?.output_intent, capabilityId, frontingMapping?.output_intent || ''),
          intent_type: enumOrAssistant(prior?.intent_type, assistant?.intent_type, frontingMapping?.execution_posture || 'business_action'),
          operation_type: enumOrAssistant(prior?.operation_type, assistant?.operation_type, frontingMapping
            ? frontingMapping.side_effect_level.includes('approval')
              ? 'approval_gated'
              : frontingMapping.side_effect_level.includes('write')
                ? 'write'
                : 'read'
            : sideEffectType && sideEffectType !== 'read' ? 'approval_gated' : 'read'),
          side_effect_level: enumOrAssistant(prior?.side_effect_level, assistant?.side_effect_level, frontingMapping?.side_effect_level || (approvalRequired ? 'approval_required' : sideEffectType || 'read')),
          minimum_scope: prior?.minimum_scope?.length
            ? [...prior.minimum_scope]
            : assistant?.minimum_scope?.length
              ? [...assistant.minimum_scope]
              : mapShapeMinimumScope(contract),
          implementation_fit: prior?.implementation_fit ?? assistant?.implementation_fit,
          business_effects: prior?.business_effects ?? assistant?.business_effects ?? frontingMapping?.business_effects ?? mapShapeBusinessEffects(contract),
          backend_operation: textOrAssistant(prior?.backend_operation, assistant?.backend_operation, capabilityId, frontingMapping?.raw_operation_refs[0] || capabilityId),
          path_template: textOrAssistant(prior?.path_template, assistant?.path_template, capabilityId, ''),
          output_shape: textOrAssistant(prior?.output_shape, assistant?.output_shape, capabilityId, frontingMapping?.output_intent || 'governed_result'),
          inputs: reviewedInputsOrFallback(
            prior?.inputs,
            assistant?.inputs,
            mapShapeContractInputs(contract).length
              ? mapShapeContractInputs(contract)
              : frontingMapping
                ? buildIntegrationFrontingInputs(frontingMapping)
                : [],
          ),
        }
      })
  })

  const generatedCapabilities = [...applicationCapabilities, ...dataAccessCapabilities, ...shapeCapabilities]
  const integrationFrontingCapabilities: DeveloperCapabilityFormalization[] = integrationFrontingMappings
    .filter((mapping) => !generatedCapabilities.some((capability) => capability.capability_id === mapping.capability_id))
    .map((mapping) => {
      const id = `integration_fronting:${mapping.capability_id}`
      const prior = existingById.get(id)
      return {
        id,
        kind: prior?.kind ?? 'atomic',
        composition: prior?.composition ?? null,
        grant_policy: prior?.grant_policy ?? grantPolicyFromFrontingMapping(mapping),
        source_kind: 'application_integration',
        service_id: prior?.service_id || mapping.service_id,
        capability_id: prior?.capability_id || mapping.capability_id,
        title: prior?.title || mapping.title,
        summary: prior?.summary || mapping.intent,
        entity_targeted: prior?.entity_targeted ?? true,
        subject_kind: prior?.subject_kind || mapping.subject_kind,
        context_type: prior?.context_type || mapping.context_type,
        output_intent: prior?.output_intent || mapping.output_intent,
        intent_type: prior?.intent_type || mapping.execution_posture,
        operation_type: prior?.operation_type || (
          mapping.side_effect_level.includes('approval')
            ? 'approval_gated'
            : mapping.side_effect_level.includes('write')
              ? 'write'
              : 'read'
        ),
        side_effect_level: prior?.side_effect_level || mapping.side_effect_level,
        business_effects: prior?.business_effects ?? mapping.business_effects,
        backend_operation: prior?.backend_operation || mapping.raw_operation_refs[0] || mapping.capability_id,
        path_template: prior?.path_template || '',
        output_shape: prior?.output_shape || mapping.output_intent || 'governed_result',
        inputs: prior?.inputs?.length
          ? cloneInputs(prior.inputs).map((input) => mergeFrontingInputMetadata(input, mapping))
          : buildIntegrationFrontingInputs(mapping),
      }
    })

  const atomicCapabilities = [...generatedCapabilities, ...integrationFrontingCapabilities]
  const composedCapabilities = buildComposedCapabilityFormalizations({
    baseCapabilities: atomicCapabilities,
    existing: params.existing,
    shape: params.shape,
    scenarios: params.scenarios,
    defaultNamespace: params.defaultNamespace,
    pmArtifacts: params.pmArtifacts,
    allowGeneratedCompositions: !shapeDeclaresSourceCapabilityInventory(params.shape),
  })

  return [...atomicCapabilities, ...composedCapabilities].map((capability) => ({
    ...finalizeCapabilityFormalization(capability),
    inputs: cloneInputs(capability.inputs),
  }))
}

function capabilityStepId(capabilityId: string, index: number): string {
  return slugify(capabilityId.split('.').pop() || capabilityId) || `step_${index + 1}`
}

function childInputLooksDerivedContext(input: DeveloperCapabilityInputFormalization): boolean {
  const inputName = normalizeText(input.input_name)
  const semanticType = normalizeText(input.semantic_type ?? '')
  if (/\b(quarter|period|date|time|fiscal|year|month|week)\b/.test(inputName) || /\b(time|temporal|date|quarter)\b/.test(semanticType)) {
    return false
  }
  const text = normalizeText([
    input.input_name,
    input.summary,
    input.semantic_type,
    input.normalization_hint,
  ].join(' '))
  return /\b(context|target|targets|selected|selection|candidate|candidates|cohort|account|accounts|opportunity|opportunities|entities|source)\b/.test(text)
}

function makeCompositionForCapabilities(capabilities: DeveloperCapabilityFormalization[]): DeveloperComposition {
  const steps = capabilities.map((capability, index) => ({
    id: capabilityStepId(capability.capability_id, index),
    capability: capability.capability_id,
    step_order: index + 1,
  }))
  const input_mapping: DeveloperComposition['input_mapping'] = {}
  const parentInputNames = new Set((capabilities[0]?.inputs ?? []).map((input) => input.input_name).filter(Boolean))
  steps.forEach((step, index) => {
    const capability = capabilities[index]
    if (index === 0) {
      input_mapping[step.id] = Object.fromEntries(
        (capability?.inputs ?? [])
          .filter((input) => input.required || parentInputNames.has(input.input_name))
          .map((input) => [input.input_name, `$.input.${input.input_name}`]),
      )
      return
    }
    const previousStep = steps[index - 1]
    input_mapping[step.id] = Object.fromEntries(
      (capability?.inputs ?? [])
        .filter((input) => input.required || parentInputNames.has(input.input_name))
        .map((input) => [
          input.input_name,
          parentInputNames.has(input.input_name)
            ? `$.input.${input.input_name}`
            : childInputLooksDerivedContext(input)
            ? `$.steps.${previousStep.id}.output.result`
            : `$.input.${input.input_name}`,
        ]),
    )
  })
  return {
    authority_boundary: 'same_service',
    steps,
    input_mapping,
    output_mapping: {
      result: `$.steps.${steps[steps.length - 1]?.id ?? 'step_1'}.output.result`,
    },
    empty_result_policy: null,
    empty_result_output: null,
    failure_policy: {
      child_clarification: 'propagate',
      child_denial: 'propagate',
      child_approval_required: 'propagate',
      child_error: 'fail_parent',
    },
    audit_policy: {
      record_child_invocations: true,
      parent_task_lineage: true,
    },
  }
}

function minimumScopeForCapabilities(capabilities: DeveloperCapabilityFormalization[]): string[] {
  return Array.from(new Set(capabilities.flatMap((capability) => capability.minimum_scope ?? []).map((value) => value.trim()).filter(Boolean)))
}

function declaredBusinessEffects(capability: DeveloperCapabilityFormalization): DeveloperBusinessEffects | undefined {
  const produces = (capability.business_effects?.produces ?? [])
    .map((effect) => effect.trim())
    .filter(Boolean)
  const doesNotProduce = (capability.business_effects?.does_not_produce ?? [])
    .map((effect) => effect.trim())
    .filter(Boolean)
  if (produces.length === 0 && doesNotProduce.length === 0) return undefined
  return {
    produces: Array.from(new Set(produces)),
    does_not_produce: Array.from(new Set(doesNotProduce)),
  }
}

function looksOperationalApprovalPreviewIntent(text: string): boolean {
  if (/\bapproval\b|\bpreview\b|\breassign(?:ment)?\b|\brout(?:e|ing)\b/.test(text)) return true
  if (/\bprepare\b/.test(text) && /\b(task|tasks|follow[- ]?up|route|routing|reassign(?:ment)?|mutation)\b/.test(text)) return true
  if (/\bfollow[- ]?up\b/.test(text) && /\b(create|prepare|task|tasks|mutation)\b/.test(text)) return true
  return false
}

function shouldKeepDeclaredApprovalBoundary(
  capability: DeveloperCapabilityFormalization,
  businessEffects: DeveloperBusinessEffects | undefined,
): boolean {
  if (!capability.side_effect_level.includes('approval')) return true
  const intentText = [
    capability.capability_id,
    capability.title,
    capability.summary,
    capability.output_intent,
    capability.output_shape,
  ].join(' ').toLowerCase().replace(/[_-]+/g, ' ')
  const produces = new Set(businessEffects?.produces ?? [])
  return capability.intent_type.includes('approval')
    || capability.operation_type.includes('write')
    || looksOperationalApprovalPreviewIntent(intentText)
    || produces.has('approval.request')
    || produces.has('system.preview_mutation')
    || produces.has('system.mutation')
}

function inferImplementationFit(capability: DeveloperCapabilityFormalization) {
  if (normalizedCapabilityKind(capability) === 'composed') {
    return {
      category: 'native_anip' as const,
      rationale: 'Represented as a declared contract-level composed business capability. Child handlers may still require service implementation.',
    }
  }
  if (!capability.capability_id || !capability.inputs) {
    return {
      category: 'contract_gap' as const,
      rationale: 'Capability contract is incomplete and needs formalization before generation or publication.',
    }
  }
  if (capability.backend_operation || capability.service_id) {
    return {
      category: 'custom_service_logic' as const,
      rationale: 'ANIP can expose and govern this capability, but the service still needs domain/backend implementation logic.',
    }
  }
  return {
    category: 'native_anip' as const,
    rationale: 'Capability is represented by declared ANIP metadata and does not currently declare a custom backend dependency.',
  }
}

function finalizeCapabilityFormalization(capability: DeveloperCapabilityFormalization): DeveloperCapabilityFormalization {
  const businessEffects = declaredBusinessEffects(capability)
  const produces = new Set(businessEffects?.produces ?? [])
  const sideEffectLevel = shouldKeepDeclaredApprovalBoundary(capability, businessEffects)
    ? capability.side_effect_level
    : 'read'
  const hasApprovalBoundary =
    capability.intent_type.includes('approval')
    || capability.operation_type.includes('write')
    || sideEffectLevel.includes('approval')
    || sideEffectLevel.includes('write')
    || produces.has('approval.request')
    || produces.has('system.preview_mutation')
    || produces.has('system.mutation')
  return {
    ...capability,
    grant_policy: capability.grant_policy ?? null,
    operation_type: hasApprovalBoundary && capability.operation_type === 'read'
      ? 'approval_gated'
      : !hasApprovalBoundary && capability.operation_type.includes('approval')
        ? 'read'
        : capability.operation_type,
    side_effect_level: hasApprovalBoundary && sideEffectLevel === 'read'
      ? 'approval_required'
      : sideEffectLevel,
    backend_operation: canonicalBackendOperation(capability.backend_operation, capability.capability_id),
    business_effects: businessEffects,
    implementation_fit: capability.implementation_fit ?? inferImplementationFit(capability),
  }
}

function composedCapabilityIdForPair(namespace: string, firstCapabilityId: string, lastCapabilityId: string, fallback: string): string {
  const firstNamespace = firstCapabilityId.split('.')[0]
  const lastNamespace = lastCapabilityId.split('.')[0]
  const capabilityNamespace = firstNamespace && firstNamespace === lastNamespace ? firstNamespace : namespace
  return `${capabilityNamespace}.${slugify(fallback) || 'composed_business_capability'}`
}

function composedCapabilityFromSteps(params: {
  id: string
  capabilityId: string
  title: string
  summary: string
  capabilities: DeveloperCapabilityFormalization[]
  prior?: DeveloperCapabilityFormalization
}): DeveloperCapabilityFormalization | null {
  const capabilities = params.capabilities.filter((capability, index, all) =>
    capability.capability_id && all.findIndex((item) => item.capability_id === capability.capability_id) === index,
  )
  if (capabilities.length < 2) return null
  const finalCapability = capabilities[capabilities.length - 1]
  const hasApprovalOrWrite = capabilities.some((capability) =>
    capability.operation_type.includes('write')
    || capability.operation_type.includes('approval')
    || capability.side_effect_level.includes('write')
    || capability.side_effect_level.includes('approval'),
  )
  return {
    id: params.id,
    kind: 'composed',
    composition: params.prior?.composition ?? makeCompositionForCapabilities(capabilities),
    grant_policy: params.prior?.grant_policy ?? null,
    source_kind: 'application_integration',
    service_id: params.prior?.service_id || capabilities[0]?.service_id || finalCapability.service_id,
    capability_id: params.prior?.capability_id || params.capabilityId,
    title: params.prior?.title || params.title,
    summary: params.prior?.summary || params.summary,
    entity_targeted: params.prior?.entity_targeted ?? capabilities.some((capability) => capability.entity_targeted),
    subject_kind: params.prior?.subject_kind || finalCapability.subject_kind || capabilities[0]?.subject_kind || '',
    context_type: params.prior?.context_type || finalCapability.context_type || capabilities[0]?.context_type || '',
    output_intent: params.prior?.output_intent || finalCapability.output_intent || finalCapability.output_shape || 'composed_result',
    intent_type: params.prior?.intent_type || 'business_action',
    operation_type: params.prior?.operation_type || (hasApprovalOrWrite ? 'approval_gated' : 'read'),
    side_effect_level: params.prior?.side_effect_level || (hasApprovalOrWrite ? 'approval_required' : 'read'),
    minimum_scope: params.prior?.minimum_scope?.length ? [...params.prior.minimum_scope] : minimumScopeForCapabilities(capabilities),
    backend_operation: params.prior?.backend_operation || params.capabilityId,
    path_template: params.prior?.path_template || canonicalCapabilityPathTemplate(params.capabilityId),
    output_shape: params.prior?.output_shape || canonicalCapabilityOutputShape(params.capabilityId),
    inputs: params.prior?.inputs?.length ? params.prior.inputs : capabilities[0]?.inputs ?? [],
  }
}

function capabilitiesShareService(capabilities: DeveloperCapabilityFormalization[]): boolean {
  if (capabilities.length === 0) return false
  const serviceId = capabilities[0]?.service_id
  return !!serviceId && capabilities.every((capability) => capability.service_id === serviceId)
}

const COMPOSITION_SOURCE_TOKENS = new Set([
  'risk',
  'rank',
  'ranked',
  'score',
  'scored',
  'priority',
  'prioritize',
  'prioritized',
  'selected',
  'selection',
  'candidate',
  'candidates',
  'target',
  'targets',
  'top',
  'stalled',
  'bottleneck',
  'lookalike',
  'cohort',
])

const COMPOSITION_SINK_TOKENS = new Set([
  'prepare',
  'preparation',
  'preview',
  'plan',
  'route',
  'routing',
  'reassign',
  'reassignment',
  'followup',
  'follow',
  'task',
  'tasks',
])

const COMPOSITION_TOKEN_STOPWORDS = new Set([
  'a',
  'an',
  'and',
  'for',
  'from',
  'gtm',
  'of',
  'or',
  'review',
  'service',
  'summary',
  'the',
  'to',
  'with',
])

const INFERRED_COMPOSITION_MIN_SCORE = 6
const INFERRED_COMPOSITION_MIN_MARGIN = 4

export interface InferredCompositionAmbiguity {
  id: string
  service_id: string
  sink_capability_id: string
  top_candidates: Array<{
    capability_id: string
    title: string
    score: number
  }>
}

function capabilityCompositionText(capability: DeveloperCapabilityFormalization): string {
  return normalizeText([
    capability.capability_id,
    capability.title,
    capability.summary,
    capability.intent_type,
    capability.operation_type,
    capability.side_effect_level,
    capability.subject_kind,
    capability.context_type,
    capability.output_intent,
    capability.output_shape,
    capability.inputs?.map((input) => [input.input_name, input.summary, input.semantic_type, input.normalization_hint].join(' ')).join(' '),
  ].join(' '))
}

function capabilityCompositionPrimaryText(capability: DeveloperCapabilityFormalization): string {
  return normalizeText([
    capability.capability_id,
    capability.title,
    capability.subject_kind,
    capability.context_type,
    capability.output_intent,
    capability.output_shape,
    capability.inputs?.map((input) => [input.input_name, input.semantic_type].join(' ')).join(' '),
  ].join(' '))
}

function tokenSet(value: string): Set<string> {
  return new Set(
    normalizeText(value)
      .split(/\s+/)
      .map((token) => token.trim())
      .filter((token) => token.length > 2 && !COMPOSITION_TOKEN_STOPWORDS.has(token)),
  )
}

function hasTokenOverlap(tokens: Set<string>, candidates: Set<string>): boolean {
  return [...tokens].some((token) => candidates.has(token))
}

function producesGeneratedContent(capability: DeveloperCapabilityFormalization): boolean {
  const text = normalizeText([
    capability.output_intent,
    capability.output_shape,
    capability.business_effects?.produces.join(' '),
  ].join(' '))
  return /\b(content draft|draft|message|outreach|email|linkedin)\b/.test(text)
}

function isReadSelectionCapability(capability: DeveloperCapabilityFormalization): boolean {
  const text = capabilityCompositionText(capability)
  const tokens = tokenSet(text)
  const sideEffect = normalizeText(capability.side_effect_level)
  const operation = normalizeText(capability.operation_type)
  const readLike = sideEffect.includes('read') || operation.includes('read') || !sideEffect
  return readLike && !producesGeneratedContent(capability) && hasTokenOverlap(tokens, COMPOSITION_SOURCE_TOKENS)
}

function hasDerivedContextInput(capability: DeveloperCapabilityFormalization): boolean {
  return (capability.inputs ?? []).some((input) => {
    const text = normalizeText([
      input.input_name,
      input.summary,
      input.semantic_type,
      input.normalization_hint,
    ].join(' '))
    return /\b(context|target|targets|selected|selection|candidate|candidates|cohort|account|accounts|opportunity|opportunities|entities|source)\b/.test(text)
  })
}

function isGovernedPreparationCapability(capability: DeveloperCapabilityFormalization): boolean {
  const text = capabilityCompositionText(capability)
  const tokens = tokenSet(text)
  const sideEffect = normalizeText(capability.side_effect_level)
  const operation = normalizeText(capability.operation_type)
  const governed = sideEffect.includes('approval')
    || sideEffect.includes('write')
    || operation.includes('approval')
    || operation.includes('prepare')
    || operation.includes('preview')
    || operation.includes('write')
    || looksOperationalApprovalPreviewIntent(text)
  return governed && hasDerivedContextInput(capability) && hasTokenOverlap(tokens, COMPOSITION_SINK_TOKENS)
}

function evidenceTextsForComposition(pmArtifacts: ArtifactRecord[]): string[] {
  const values: string[] = []
  const visit = (value: unknown) => {
    if (typeof value === 'string') {
      const text = normalizeText(value)
      if (text.length > 20) values.push(text)
      return
    }
    if (Array.isArray(value)) {
      value.forEach(visit)
      return
    }
    if (value && typeof value === 'object') {
      Object.values(value as Record<string, unknown>).forEach(visit)
    }
  }
  pmArtifacts.forEach((artifact) => visit(artifact.data))
  return values
}

function scenarioEvidenceTextsForComposition(scenarios: DeveloperScenarioFormalization[]): string[] {
  return scenarios.flatMap((scenario) => [
    scenario.scenario_title,
    scenario.scenario_key,
    scenario.primary_capability,
    scenario.actor_context,
    scenario.business_scope,
    scenario.time_scope,
    scenario.side_effect_formalization,
    ...scenario.required_behaviors,
    ...scenario.required_anip_support,
    scenario.implementation_notes,
  ].map((value) => normalizeText(value)).filter((value) => value.length > 20))
}

function compositionEvidenceTexts(params: {
  pmArtifacts: ArtifactRecord[]
  scenarios: DeveloperScenarioFormalization[]
}): string[] {
  return [...evidenceTextsForComposition(params.pmArtifacts), ...scenarioEvidenceTextsForComposition(params.scenarios)]
}

function compositionAffinityScore(source: DeveloperCapabilityFormalization, sink: DeveloperCapabilityFormalization): number {
  const sourceTokens = tokenSet(capabilityCompositionPrimaryText(source))
  const sinkTokens = tokenSet(capabilityCompositionPrimaryText(sink))
  let score = 0
  if ((sinkTokens.has('followup') || sinkTokens.has('follow')) && (sourceTokens.has('risk') || sourceTokens.has('ranked') || sourceTokens.has('priority') || sourceTokens.has('prioritize'))) score += 4
  if ((sinkTokens.has('routing') || sinkTokens.has('route')) && (sourceTokens.has('priority') || sourceTokens.has('prioritize') || sourceTokens.has('ranked') || sourceTokens.has('score') || sourceTokens.has('cohort'))) score += 4
  if ((sinkTokens.has('reassignment') || sinkTokens.has('reassign')) && (sourceTokens.has('capacity') || sourceTokens.has('load') || sourceTokens.has('team'))) score += 4
  return score
}

function compositionEvidenceScore(source: DeveloperCapabilityFormalization, sink: DeveloperCapabilityFormalization, evidenceTexts: string[]): number {
  const sourcePrimaryTokens = [...tokenSet(capabilityCompositionPrimaryText(source))].filter((token) => COMPOSITION_SOURCE_TOKENS.has(token))
  const sinkPrimaryTokens = [...tokenSet(capabilityCompositionPrimaryText(sink))].filter((token) => COMPOSITION_SINK_TOKENS.has(token))
  const sourceTokens = [...tokenSet(capabilityCompositionText(source))].filter((token) => COMPOSITION_SOURCE_TOKENS.has(token))
  const sinkTokens = [...tokenSet(capabilityCompositionText(sink))].filter((token) => COMPOSITION_SINK_TOKENS.has(token))
  if (sourcePrimaryTokens.length === 0 || sinkPrimaryTokens.length === 0) return 0
  const evidenceScore = evidenceTexts.reduce((score, text) => {
    const primaryMatch = sourcePrimaryTokens.some((token) => text.includes(token))
      && sinkPrimaryTokens.some((token) => text.includes(token))
    const broadMatch = sourceTokens.some((token) => text.includes(token))
      && sinkTokens.some((token) => text.includes(token))
    return score + (primaryMatch ? 3 : 0) + (broadMatch ? 1 : 0)
  }, 0)
  return evidenceScore + compositionAffinityScore(source, sink)
}

function scoredCompositionSources(
  sources: DeveloperCapabilityFormalization[],
  sink: DeveloperCapabilityFormalization,
  evidenceTexts: string[],
): Array<{ source: DeveloperCapabilityFormalization; score: number }> {
  return sources
    .filter((source) => source.capability_id !== sink.capability_id)
    .map((source) => ({ source, score: compositionEvidenceScore(source, sink, evidenceTexts) }))
    .filter((entry) => entry.score > 0)
    .sort((left, right) => right.score - left.score)
}

function hasConfidentInferredCompositionChoice(
  scored: Array<{ source: DeveloperCapabilityFormalization; score: number }>,
): boolean {
  if (scored.length === 0) return false
  const [first, second] = scored
  if (first.score < INFERRED_COMPOSITION_MIN_SCORE) return false
  if (!second) return true
  return first.score - second.score >= INFERRED_COMPOSITION_MIN_MARGIN
}

function needsInferredCompositionReview(
  scored: Array<{ source: DeveloperCapabilityFormalization; score: number }>,
): boolean {
  if (scored.length < 2) return false
  const [first, second] = scored
  if (first.score < INFERRED_COMPOSITION_MIN_SCORE) return false
  return first.score - second.score < INFERRED_COMPOSITION_MIN_MARGIN
}

function sourceDescriptorForComposition(source: DeveloperCapabilityFormalization): string {
  const text = capabilityCompositionPrimaryText(source)
  if (/\bat risk\b|\brisk\b/.test(text)) return 'at_risk'
  if (/\bprioriti[sz]e\b|\bprioriti[sz]ed\b|\bpriority\b/.test(text)) return 'prioritized'
  if (/\brank(?:ed)?\b|\bscore(?:d)?\b/.test(text)) return 'ranked'
  if (/\bstalled\b/.test(text)) return 'stalled'
  if (/\bbottleneck\b/.test(text)) return 'bottleneck'
  if (/\blookalike\b/.test(text)) return 'lookalike'
  if (/\bselected\b|\bselection\b/.test(text)) return 'selected'
  const fallback = source.capability_id.split('.').pop() || source.title || 'derived'
  return slugify(fallback.replace(/(?:^|_)summary$/g, '').replace(/(?:^|_)review$/g, '')) || 'derived'
}

function sinkDescriptorForComposition(sink: DeveloperCapabilityFormalization): string {
  const text = capabilityCompositionText(sink)
  if (/\bfollow ?up\b|\bfollowup\b/.test(text)) return 'followup_preparation'
  if (/\brout(?:e|ing)\b/.test(text)) return 'routing_preparation'
  if (/\breassign(?:ment)?\b/.test(text)) return 'reassignment_preparation'
  if (/\btask(?:s)?\b/.test(text)) return 'task_preparation'
  const fallback = sink.capability_id.split('.').pop() || sink.title || 'preparation'
  return slugify(fallback.replace(/^prepare_/, '').replace(/_tasks$/, '_preparation')) || 'preparation'
}

function inferredComposedCapabilityId(namespace: string, source: DeveloperCapabilityFormalization, sink: DeveloperCapabilityFormalization): string {
  const sourceNamespace = source.capability_id.split('.')[0]
  const sinkNamespace = sink.capability_id.split('.')[0]
  const capabilityNamespace = sourceNamespace && sourceNamespace === sinkNamespace ? sourceNamespace : namespace
  return `${capabilityNamespace}.${sourceDescriptorForComposition(source)}_${sinkDescriptorForComposition(sink)}`
}

function buildInferredComposedCapabilityFormalizations(params: {
  baseCapabilities: DeveloperCapabilityFormalization[]
  existing?: DeveloperDefinitionData | null
  defaultNamespace: string
  pmArtifacts: ArtifactRecord[]
  scenarios: DeveloperScenarioFormalization[]
  generatedIds: Set<string>
}): DeveloperCapabilityFormalization[] {
  const evidenceTexts = compositionEvidenceTexts({
    pmArtifacts: params.pmArtifacts,
    scenarios: params.scenarios,
  })
  const existingByChildPair = new Map<string, DeveloperCapabilityFormalization>()
  ;(params.existing?.capability_formalizations ?? []).forEach((capability) => {
    const steps = capability.composition?.steps?.map((step) => step.capability).filter(Boolean) ?? []
    if (steps.length >= 2) existingByChildPair.set(steps.join(' -> '), capability)
  })
  const capabilitiesByService = new Map<string, DeveloperCapabilityFormalization[]>()
  params.baseCapabilities
    .filter((capability) => normalizedCapabilityKind(capability) !== 'composed' && capability.service_id && capability.capability_id)
    .forEach((capability) => {
      const list = capabilitiesByService.get(capability.service_id) ?? []
      list.push(capability)
      capabilitiesByService.set(capability.service_id, list)
    })

  const generated: DeveloperCapabilityFormalization[] = []
  capabilitiesByService.forEach((capabilities) => {
    const sources = capabilities.filter(isReadSelectionCapability)
    const sinks = capabilities.filter(isGovernedPreparationCapability)
    sinks.forEach((sink) => {
      const scored = scoredCompositionSources(sources, sink, evidenceTexts)
      if (!hasConfidentInferredCompositionChoice(scored)) return
      const source = scored[0].source
      const capabilityId = inferredComposedCapabilityId(params.defaultNamespace, source, sink)
      if (params.generatedIds.has(capabilityId)) return
      const childPairKey = [source.capability_id, sink.capability_id].join(' -> ')
      const prior = existingByChildPair.get(childPairKey)
      const composed = composedCapabilityFromSteps({
        id: prior?.id || `composition:inferred:${slugify(source.capability_id)}:${slugify(sink.capability_id)}`,
        capabilityId,
        title: humanize(capabilityId),
        summary: `Compose ${source.capability_id} -> ${sink.capability_id} when the requested business action needs derived targets before governed preparation.`,
        capabilities: [source, sink],
        prior,
      })
      if (composed) {
        generated.push(composed)
        params.generatedIds.add(composed.capability_id)
      }
    })
  })
  return generated
}

export function findInferredCompositionAmbiguities(params: {
  definition?: DeveloperDefinitionData | null
  pmArtifacts: ArtifactRecord[]
}): InferredCompositionAmbiguity[] {
  const definition = params.definition ?? null
  if (!definition) return []
  const evidenceTexts = compositionEvidenceTexts({
    pmArtifacts: params.pmArtifacts,
    scenarios: definition.scenario_formalizations ?? [],
  })
  const capabilitiesByService = new Map<string, DeveloperCapabilityFormalization[]>()
  ;(definition.capability_formalizations ?? [])
    .filter((capability) => normalizedCapabilityKind(capability) !== 'composed' && capability.service_id && capability.capability_id)
    .forEach((capability) => {
      const list = capabilitiesByService.get(capability.service_id) ?? []
      list.push(capability)
      capabilitiesByService.set(capability.service_id, list)
    })

  const ambiguities: InferredCompositionAmbiguity[] = []
  capabilitiesByService.forEach((capabilities, serviceId) => {
    const sources = capabilities.filter(isReadSelectionCapability)
    const sinks = capabilities.filter(isGovernedPreparationCapability)
    sinks.forEach((sink) => {
      const scored = scoredCompositionSources(sources, sink, evidenceTexts)
      if (!needsInferredCompositionReview(scored)) return
      ambiguities.push({
        id: `composition-ambiguity:${serviceId}:${sink.capability_id}`,
        service_id: serviceId,
        sink_capability_id: sink.capability_id,
        top_candidates: scored.slice(0, 4).map((entry) => ({
          capability_id: entry.source.capability_id,
          title: entry.source.title || humanize(entry.source.capability_id),
          score: entry.score,
        })),
      })
    })
  })
  return ambiguities
}

function buildComposedCapabilityFormalizations(params: {
  baseCapabilities: DeveloperCapabilityFormalization[]
  existing?: DeveloperDefinitionData | null
  shape: ShapeRecord | null
  scenarios: DeveloperScenarioFormalization[]
  defaultNamespace: string
  pmArtifacts: ArtifactRecord[]
  allowGeneratedCompositions: boolean
}): DeveloperCapabilityFormalization[] {
  if (!params.allowGeneratedCompositions) return []
  const existingById = new Map(
    (params.existing?.capability_formalizations ?? []).map((item) => [item.id, item] as const),
  )
  const baseByCapabilityId = new Map(params.baseCapabilities.map((capability) => [capability.capability_id, capability] as const))
  const generated: DeveloperCapabilityFormalization[] = []
  const generatedIds = new Set(params.baseCapabilities.map((capability) => capability.capability_id))

  params.scenarios.forEach((scenario) => {
    const steps = scenario.orchestration_steps
      .filter((step) => step.step_kind === 'capability_execution' && step.capability_id)
      .map((step) => baseByCapabilityId.get(step.capability_id))
      .filter((capability): capability is DeveloperCapabilityFormalization => capability != null)
    if (steps.length < 2) return
    if (!capabilitiesShareService(steps)) return
    const capabilityId = composedCapabilityIdForPair(
      params.defaultNamespace,
      steps[0].capability_id,
      steps[steps.length - 1].capability_id,
      scenario.scenario_key || scenario.scenario_title,
    )
    if (generatedIds.has(capabilityId)) return
    const id = `composition:scenario:${scenario.scenario_id}`
    const composed = composedCapabilityFromSteps({
      id,
      capabilityId,
      title: humanize(capabilityId),
      summary: `Compose ${steps.map((capability) => capability.capability_id).join(' -> ')} for ${scenario.scenario_title}.`,
      capabilities: steps,
      prior: existingById.get(id),
    })
    if (composed) {
      generated.push(composed)
      generatedIds.add(composed.capability_id)
    }
  })

  generated.push(...buildInferredComposedCapabilityFormalizations({
    baseCapabilities: params.baseCapabilities,
    existing: params.existing,
    defaultNamespace: params.defaultNamespace,
    pmArtifacts: params.pmArtifacts,
    scenarios: params.scenarios,
    generatedIds,
  }))

  return generated
}

export function buildDeveloperDefinitionData(params: {
  project: ProjectDetail
  baseline: DeveloperBaselineData | null
  requirements: RequirementsRecord | null
  scenarios: ArtifactRecord[]
  shape: ShapeRecord | null
  pmArtifacts: ArtifactRecord[]
  existing?: DeveloperDefinitionData | null
}): DeveloperDefinitionData {
  const existing = params.existing ?? null
  const integrationFrontingMappings = buildIntegrationFrontingMappings(params.pmArtifacts)
  const frontingServiceIds = Array.from(new Set(
    integrationFrontingMappings.map((mapping) => mapping.service_id).filter(Boolean),
  ))
  const isGovernedFrontingProject = params.project.project_type === 'governed_service_project'
  const shapeServiceIds = Array.from(new Set([
    ...(isGovernedFrontingProject && frontingServiceIds.length > 0 ? [] : deriveServiceIds(params.shape)),
    ...frontingServiceIds,
  ]))
  const existingSelectedServiceIds = (existing?.generation.selected_service_ids ?? [])
    .map((id) => String(id).trim())
    .filter(Boolean)
  const selectedServiceIds = isGovernedFrontingProject && frontingServiceIds.length > 0
    ? (
        existingSelectedServiceIds.filter((id) => frontingServiceIds.includes(id)).length > 0
          ? existingSelectedServiceIds.filter((id) => frontingServiceIds.includes(id))
          : frontingServiceIds
      )
    : (
        existingSelectedServiceIds.length > 0
          ? existingSelectedServiceIds
          : shapeServiceIds
      )
  const defaultNamespace = params.project.domain ? slugify(params.project.domain) : slugify(params.project.name)
  const defaultPrefix = slugify(params.project.name)
  const requirements = requirementsData(params.requirements)
  const requirementDomain = String(requirements.system?.domain ?? '').trim()
  const projectDomain = String(params.project.domain ?? '').trim()
  const inferredDomain = projectDomain
    || (requirementDomain && requirementDomain !== 'general' ? requirementDomain : '')
    || slugify(params.project.name)
  const backendBindings = buildBackendBindings({
    project: params.project,
    shape: params.shape,
    existing,
    pmArtifacts: params.pmArtifacts,
    dataAccessProject: null,
    applicationIntegrationProject: null,
  })
  const scenarioFormalizations = buildScenarioFormalizations({
    scenarios: params.scenarios,
    shape: params.shape,
    existing,
  })
  const capabilityFormalizations = buildCapabilityFormalizations({
    existing,
    shape: params.shape,
    pmArtifacts: params.pmArtifacts,
    scenarios: scenarioFormalizations,
    defaultNamespace,
    applicationIntegrationProject: null,
    dataAccessProject: null,
  })
  const serviceBackendBindings = buildServiceBackendBindings({
    shape: params.shape,
    capabilities: capabilityFormalizations,
    pmArtifacts: params.pmArtifacts,
    existing,
  })
  return {
    artifact_type: DEVELOPER_DEFINITION_ARTIFACT_TYPE,
    source_inputs: {
      product_revision_artifact_id: params.baseline?.source_inputs.product_revision_artifact_id ?? null,
      product_revision_number: params.baseline?.source_inputs.product_revision_number ?? null,
      product_design_hash: params.baseline?.source_inputs.product_design_hash ?? null,
      requirements_id: params.requirements?.id ?? null,
      requirements_hash: params.requirements?.content_hash ?? null,
      scenario_ids: params.scenarios.map((scenario) => scenario.id),
      scenario_set_hash: scenarioSetHash(params.scenarios),
      shape_id: params.shape?.id ?? null,
      shape_hash: params.shape?.content_hash ?? null,
      baseline_locked_at: params.baseline?.locked_at ?? null,
    },
    product_alignment: buildProductAlignment({
      pmArtifacts: params.pmArtifacts,
      existing,
    }),
    identity: {
      system_name: existing?.identity.system_name ?? params.project.name,
      domain_name: existing?.identity.domain_name ?? inferredDomain,
      delivery_model: existing?.identity.delivery_model ?? inferDefaultDeliveryModel(params.shape),
      architecture_shape: existing?.identity.architecture_shape ?? inferDefaultArchitectureShape(params.shape),
      high_availability_required: existing?.identity.high_availability_required ?? false,
    },
    authority: {
      trust_mode: existing?.authority.trust_mode ?? String(requirements.trust?.mode ?? ''),
      trust_checkpoints_required: existing?.authority.trust_checkpoints_required ?? Boolean(requirements.trust?.checkpoints),
      spending_actions_present: existing?.authority.spending_actions_present ?? hasAnySpendingRisk(params.requirements),
      irreversible_actions_present: existing?.authority.irreversible_actions_present ?? hasAnyIrreversibleRisk(params.requirements),
      cost_visibility_required: existing?.authority.cost_visibility_required ?? Object.values(requirements.risk_profile ?? {}).some((entry) => Boolean((entry as Record<string, any>)?.cost_visibility_required)),
      preflight_authority_discovery: existing?.authority.preflight_authority_discovery ?? Boolean(requirements.permissions?.preflight_discovery),
      grantable_restrictions: existing?.authority.grantable_restrictions ?? Boolean(requirements.permissions?.grantable_requirements),
      restricted_vs_denied: existing?.authority.restricted_vs_denied ?? Boolean(requirements.permissions?.restricted_vs_denied),
      delegation_tokens: existing?.authority.delegation_tokens ?? Boolean(requirements.auth?.delegation_tokens),
      scoped_authority: existing?.authority.scoped_authority ?? Boolean(requirements.auth?.scoped_authority),
      purpose_binding: existing?.authority.purpose_binding ?? Boolean(requirements.auth?.purpose_binding),
      approval_expectation: existing?.authority.approval_expectation ?? (requirements.business_constraints?.approval_expected_for_high_risk ? 'approval_required_for_high_risk' : 'not_specified'),
      recovery_sensitive: existing?.authority.recovery_sensitive ?? Boolean(requirements.business_constraints?.recovery_sensitive),
      blocked_failure_posture: existing?.authority.blocked_failure_posture ?? String(requirements.business_constraints?.blocked_failure_posture ?? ''),
    },
    audit: {
      durable_records_required: existing?.audit.durable_records_required ?? Boolean(requirements.audit?.durable),
      searchable_history_required: existing?.audit.searchable_history_required ?? Boolean(requirements.audit?.searchable),
      invocation_tracking: existing?.audit.invocation_tracking ?? Boolean(requirements.lineage?.invocation_id),
      task_tracking: existing?.audit.task_tracking ?? Boolean(requirements.lineage?.task_id),
      parent_invocation_tracking: existing?.audit.parent_invocation_tracking ?? Boolean(requirements.lineage?.parent_invocation_id),
      client_reference_ids: existing?.audit.client_reference_ids ?? Boolean(requirements.lineage?.client_reference_id),
      service_handoffs_required: existing?.audit.service_handoffs_required ?? (Boolean(requirements.auth?.service_to_service_handoffs) || shapeHasCoordination(params.shape)),
      cross_service_reconstruction_required: existing?.audit.cross_service_reconstruction_required ?? (Boolean(requirements.audit?.cross_service_reconstruction_required) || shapeHasCoordination(params.shape)),
      cross_service_continuity_required: existing?.audit.cross_service_continuity_required ?? (Boolean(requirements.lineage?.cross_service_continuity_required) || shapeHasCoordination(params.shape)),
    },
    backend_bindings: backendBindings,
    integration_fronting: {
      project_type: params.project.project_type ?? 'standard',
      integration_profile: params.project.integration_profile ?? { kind: 'none', systems: [] },
      capability_mappings: integrationFrontingMappings,
    },
    service_backend_bindings: serviceBackendBindings,
    application_integration_governance: buildApplicationIntegrationGovernance({
      existing,
      pmArtifacts: params.pmArtifacts,
      applicationIntegrationProject: null,
    }),
    data_access_governance: buildDataAccessGovernance({
      existing,
      dataAccessProject: null,
    }),
    data_domain: buildDataDomainFormalization({
      project: params.project,
      existing,
      dataAccessProject: null,
      fallbackDomainName: inferredDomain,
    }),
    domain_concept_bindings: buildDomainConceptBindings({
      shape: params.shape,
      existing,
    }),
    application_object_model: buildApplicationObjectModel({
      existing,
      applicationIntegrationProject: null,
    }),
    capability_formalizations: capabilityFormalizations,
    service_topology_bindings: buildServiceTopologyBindings({
      shape: params.shape,
      pmArtifacts: params.pmArtifacts,
      existing,
    }),
    actor_expectations: buildActorExpectationBindings({
      pmArtifacts: params.pmArtifacts,
      existing,
    }),
    permission_intent_bindings: buildPermissionIntentBindings({
      pmArtifacts: params.pmArtifacts,
      existing,
      allowedServiceIds: shapeServiceIds,
      capabilityFormalizations,
    }),
    scenario_formalizations: scenarioFormalizations,
    composition_rules: buildCompositionRuleBindings({
      pmArtifacts: params.pmArtifacts,
      scenarios: params.scenarios,
      existing,
    }),
    verification: {
      supported_question_family_bindings: buildSupportedQuestionFamilyBindings({
        pmArtifacts: params.pmArtifacts,
        existing,
        allowedServiceIds: shapeServiceIds,
      }),
      business_goal_bindings: buildBusinessGoalBindings({
        pmArtifacts: params.pmArtifacts,
        existing,
        allowedServiceIds: shapeServiceIds,
      }),
      non_goal_guards: buildNonGoalGuards({
        pmArtifacts: params.pmArtifacts,
        existing,
      }),
      success_criteria_checks: buildSuccessCriteriaChecks({
        pmArtifacts: params.pmArtifacts,
        existing,
      }),
      data_access_scenario_pack: buildDataAccessScenarioPackExpectation({
        existing,
        dataAccessProject: null,
      }),
    },
    generation: {
      service_generation_mode: existing?.generation.service_generation_mode ?? 'from_service_design',
      selected_service_ids: selectedServiceIds,
      scalability_profile: existing?.generation.scalability_profile ?? 'stateless_horizontal',
      protocols: (existing?.generation.protocols ?? []).filter((item) =>
        ['anip_http', 'grpc', 'async_events'].includes(item),
      ).length
        ? (existing?.generation.protocols ?? []).filter((item) =>
            ['anip_http', 'grpc', 'async_events'].includes(item),
          )
        : ['anip_http'],
      codegen_adapter: existing?.generation.codegen_adapter ?? deriveDefaultCodegenAdapter(null, null),
      layout_strategy: existing?.generation.layout_strategy ?? 'monorepo',
    },
    naming: {
      namespace: existing?.naming.namespace ?? defaultNamespace,
      package_prefix: existing?.naming.package_prefix ?? defaultPrefix,
      service_name_prefix: existing?.naming.service_name_prefix ?? defaultPrefix,
    },
    rationale: existing?.rationale ?? '',
    compiled_contract_identity: existing?.compiled_contract_identity ?? null,
    saved_revision: existing?.saved_revision ?? null,
    saved_at: existing?.saved_at ?? null,
  }
}

function developerSufficiencyActionLabel(status: import('./project-types').DesignSectionSufficiencyStatus): string {
  switch (status) {
    case 'ready':
      return 'Review'
    case 'draftable':
      return 'Draft From Baseline'
    case 'needs_clarification':
      return 'Resolve Gaps'
    default:
      return 'Unblock'
  }
}

function capabilityInventoryHasConcreteInputEvidence(value: unknown): boolean {
  if (!value || typeof value !== 'object') return false
  const record = value as Record<string, unknown>
  const inventories = [
    record.canonical_capability_inventory,
    record.capability_inventory,
    record.capabilities,
    record.capability_formalizations,
  ].filter(Array.isArray) as unknown[][]
  return inventories.some((inventory) =>
    inventory.some((capability) => {
      if (!capability || typeof capability !== 'object') return false
      const inputs = (capability as Record<string, unknown>).inputs
      if (!Array.isArray(inputs)) return false
      return inputs.some((input) => {
        if (!input || typeof input !== 'object') return false
        const inputRecord = input as Record<string, unknown>
        return textValue(inputRecord.input_name ?? inputRecord.name).length > 0
          && textValue(inputRecord.input_type ?? inputRecord.type).length > 0
      })
    }),
  )
}

export function sourceTextHasConcreteCapabilityInputEvidence(sourceText: string): boolean {
  return inputContractEvidenceJsonCandidates(sourceText).some((candidate) => {
    try {
      return capabilityInventoryHasConcreteInputEvidence(JSON.parse(candidate))
    } catch {
      return false
    }
  })
}

function hasConcreteCapabilityInputEvidence(
  pmArtifacts: ArtifactRecord[],
  definition: DeveloperDefinitionData | null,
): boolean {
  if ((definition?.capability_formalizations ?? []).some((capability) =>
    capability.inputs.some((input) => input.input_name.trim().length > 0),
  )) {
    return true
  }
  return pmArtifacts.some((artifact) => {
    const data = artifact.data as Record<string, any> | undefined
    const artifactType = String(data?.artifact_type ?? '')
    const items: Record<string, any>[] = []
    if (['assistant_capability_formalization_candidates', 'assistant_input_contract_candidates'].includes(artifactType)) {
      items.push(...(Array.isArray(data?.source_proposal?.items) ? data.source_proposal.items : []))
    } else if (artifactType === 'assistant_developer_design_draft_bundle') {
      const sections = Array.isArray(data?.bundle?.sections) ? data.bundle.sections : []
      sections
        .filter((section: Record<string, any>) =>
          section.status !== 'failed'
          && ['capability_formalization', 'input_contracts'].includes(String(section.id ?? '')),
        )
        .forEach((section: Record<string, any>) => {
          const sectionItems = section.envelope?.proposal?.items
          if (Array.isArray(sectionItems)) items.push(...sectionItems)
        })
    } else {
      return false
    }
    return items.some((item: Record<string, any>) => {
      const structured = item.structured_data as Record<string, any> | undefined
      const capabilities = Array.isArray(structured?.capabilities) ? structured.capabilities : []
      if (capabilities.some((capability: Record<string, any>) =>
        Array.isArray(capability.inputs)
        && capability.inputs.some((input: Record<string, any>) => String(input.input_name ?? input.name ?? '').trim().length > 0),
      )) {
        return true
      }
      const inputs = Array.isArray(structured?.inputs) ? structured.inputs : []
      return inputs.some((input: Record<string, any>) => String(input.input_name ?? input.name ?? '').trim().length > 0)
        || capabilityInventoryHasConcreteInputEvidence(structured)
    })
  })
}

export function buildDeveloperDefinitionSufficiencyCards(params: {
  projectId: string
  baseline: DeveloperBaselineData | null
  definition: DeveloperDefinitionData | null
  definitionAligned: boolean
  requirements: RequirementsRecord | null
  scenarios: ArtifactRecord[]
  shape: ShapeRecord | null
  pmArtifacts: ArtifactRecord[]
  reducedFrontingProject?: boolean
  sourceInputContractEvidenceReady?: boolean
}): DesignSectionSufficiencyCard[] {
  const summary = findProductSummaryArtifact(params.pmArtifacts)?.data as ProductSummaryData | undefined
  const actors = findActorModelArtifact(params.pmArtifacts)?.data as ActorModelData | undefined
  const businessAreas = findBusinessAreasArtifact(params.pmArtifacts)?.data as BusinessAreasData | undefined
  const permissions = findPermissionIntentArtifact(params.pmArtifacts)?.data as PermissionIntentData | undefined
  const nonGoals = findNonGoalsArtifact(params.pmArtifacts)?.data as NonGoalsData | undefined
  const successCriteria = findSuccessCriteriaArtifact(params.pmArtifacts)?.data as SuccessCriteriaData | undefined

  const baselineReady = Boolean(params.baseline)
  const summaryReady = isProductSummaryComplete(summary)
  const actorReady = isActorModelComplete(actors)
  const areasReady = isBusinessAreasComplete(businessAreas)
  const permissionReady = isPermissionIntentComplete(permissions)
  const nonGoalsReady = isNonGoalsComplete(nonGoals)
  const successReady = isSuccessCriteriaComplete(successCriteria)
  const requirementsReady = Boolean(params.requirements)
  const scenariosReady = params.scenarios.length > 0
  const shapeReady = Boolean(params.shape)
  const frontingMappings = buildIntegrationFrontingMappings(params.pmArtifacts)
  const frontingMappingsReady = frontingMappings.length > 0
  const implementationShapeReady = params.reducedFrontingProject ? frontingMappingsReady : shapeReady
  const alignedDefinition = Boolean(params.definition && params.definitionAligned)
  const capabilityInputEvidenceReady = params.reducedFrontingProject
    ? true
    : Boolean(params.sourceInputContractEvidenceReady) || hasConcreteCapabilityInputEvidence(params.pmArtifacts, params.definition)

  const definitionPath = `/design/projects/${params.projectId}/developer/definition`
  const developerPath = `/design/projects/${params.projectId}/developer`
  const pmPath = `/design/projects/${params.projectId}/pm`
  const productHandoffReady = requirementsReady && scenariosReady && shapeReady

  const cards: Array<{
    key: DeveloperDefinitionSectionId
    title: string
    prerequisitesReady: boolean
    detail: string
    questions: string[]
  }> = [
    {
      key: 'service_identity_topology',
      title: developerDefinitionSectionLabel('service_identity_topology'),
      prerequisitesReady: params.reducedFrontingProject ? baselineReady : baselineReady && shapeReady,
      detail: params.reducedFrontingProject
        ? 'Service identity can be drafted from the locked fronting intent and integration profile without requiring a separate Product Design service shape.'
        : shapeReady
          ? 'Service identity and topology can be drafted from the locked service design without asking for every field by hand.'
          : 'Choose and lock a Product Design service shape before formalizing service topology.',
      questions: [
        !params.reducedFrontingProject && !shapeReady ? 'Which service design should Developer Design formalize?' : null,
      ].filter((item): item is string => Boolean(item)),
    },
    {
      key: 'capability_contracts',
      title: developerDefinitionSectionLabel('capability_contracts'),
      prerequisitesReady: baselineReady && requirementsReady && scenariosReady && implementationShapeReady && capabilityInputEvidenceReady,
      detail: params.reducedFrontingProject
        ? frontingMappingsReady
          ? 'Capability contracts can be drafted from accepted governed integration-fronting mappings.'
          : 'Capability contracts need at least one accepted governed mapping from Govern API / MCP.'
        : requirementsReady && scenariosReady && shapeReady && !capabilityInputEvidenceReady
          ? 'Capability IDs and service ownership are known, but implementation-grade input contracts still need reviewed names, types, required flags, defaults, and allowed values.'
          : requirementsReady && scenariosReady && shapeReady
          ? 'Capability contracts can be drafted from the locked requirements, scenario pack, and service shape.'
          : 'Capability formalization depends on a locked requirements set, scenario pack, and service design.',
      questions: [
        !requirementsReady ? 'Which requirements set should the developer contract preserve?' : null,
        !scenariosReady ? 'Which concrete scenarios should capability behavior reflect?' : null,
        params.reducedFrontingProject
          ? (!frontingMappingsReady ? 'Which backend operations should be exposed as governed ANIP capabilities?' : null)
          : (!shapeReady ? 'Which service design owns those capabilities?' : null),
        !params.reducedFrontingProject && shapeReady && !capabilityInputEvidenceReady
          ? 'What are the reviewed implementation input names, types, required flags, defaults, and allowed values for each source-owned capability?'
          : null,
      ].filter((item): item is string => Boolean(item)),
    },
    {
      key: 'authority_and_approval',
      title: developerDefinitionSectionLabel('authority_and_approval'),
      prerequisitesReady: baselineReady && actorReady && areasReady && permissionReady,
      detail: actorReady && areasReady && permissionReady
        ? 'Runtime policy can be drafted from the locked PM actor model and permission intent, then narrowed only where boundaries are still ambiguous.'
        : 'Authority and approval should come from PM-owned actor and permission artifacts instead of ad hoc developer guesses.',
      questions: [
        !actorReady ? 'Which actors need distinct authority or visibility handling?' : null,
        !areasReady ? 'Which business areas should runtime policy bind to?' : null,
        !permissionReady ? 'Where should the runtime allow, restrict, clarify, deny, or stop for approval?' : null,
      ].filter((item): item is string => Boolean(item)),
    },
    {
      key: 'data_contracts',
      title: developerDefinitionSectionLabel('data_contracts'),
      prerequisitesReady: baselineReady && requirementsReady && scenariosReady,
      detail: requirementsReady && scenariosReady
        ? 'Data contracts can be drafted from the locked scenarios and operating posture, then clarified only for backend-specific gaps.'
        : 'Data contracts need locked requirements and scenarios before backend details can be formalized.',
      questions: [
        !requirementsReady ? 'What governed data posture do the requirements establish?' : null,
        !scenariosReady ? 'Which scenario contexts drive the result-shaping and data-bounding rules?' : null,
      ].filter((item): item is string => Boolean(item)),
    },
    {
      key: 'scenario_context',
      title: developerDefinitionSectionLabel('scenario_context'),
      prerequisitesReady: baselineReady && scenariosReady,
      detail: scenariosReady
        ? 'Scenario contract basics can be drafted from the locked scenario pack instead of re-entered field by field.'
        : 'Lock at least one Product Design scenario before formalizing scenario context.',
      questions: [
        !scenariosReady ? 'Which concrete scenario pack should execution context be derived from?' : null,
      ].filter((item): item is string => Boolean(item)),
    },
    {
      key: 'execution_semantics',
      title: developerDefinitionSectionLabel('execution_semantics'),
      prerequisitesReady: baselineReady && scenariosReady && shapeReady,
      detail: scenariosReady && shapeReady
        ? 'Execution semantics can be drafted from the locked scenario pack and service shape, then clarified only where orchestration rules are still missing.'
        : 'Execution semantics depend on both the locked scenario pack and service design.',
      questions: [
        !scenariosReady ? 'Which scenarios define the required execution behavior?' : null,
        !shapeReady ? 'Which service design should those execution steps map onto?' : null,
      ].filter((item): item is string => Boolean(item)),
    },
    {
      key: 'backend_bindings',
      title: developerDefinitionSectionLabel('backend_bindings'),
      prerequisitesReady: baselineReady && implementationShapeReady,
      detail: params.reducedFrontingProject
        ? frontingMappingsReady
          ? 'Backend bindings can be drafted from accepted integration-fronting mappings and connection references.'
          : 'Add governed mappings on Govern API / MCP before compiling backend adapter bindings.'
        : shapeReady
          ? 'Backend bindings can be drafted from the locked service shape and then refined only for concrete integration targets.'
          : 'Choose and lock the Product Design service shape before mapping backend targets.',
      questions: [
        params.reducedFrontingProject
          ? (!frontingMappingsReady ? 'Which raw backend operations and connection refs should the ANIP wrapper use?' : null)
          : (!shapeReady ? 'Which services need backend targets or adapters?' : null),
      ].filter((item): item is string => Boolean(item)),
    },
    {
      key: 'audit_and_lineage',
      title: developerDefinitionSectionLabel('audit_and_lineage'),
      prerequisitesReady: params.reducedFrontingProject
        ? baselineReady && (summaryReady || requirementsReady)
        : baselineReady && (summaryReady || requirementsReady) && (successReady || nonGoalsReady),
      detail: params.reducedFrontingProject
        ? 'Audit and lineage expectations can be drafted from fronting intent, permission posture, and accepted governed mappings.'
        : (summaryReady || requirementsReady) && (successReady || nonGoalsReady)
          ? 'Audit and lineage expectations can be drafted from PM goals, non-goals, and success checks instead of manually restating every field.'
          : 'Verification, evidence, and guardrails should trace back to PM-owned goals, non-goals, and success criteria.',
      questions: [
        !(summaryReady || requirementsReady) ? 'What business outcomes and risk posture should verification preserve?' : null,
        !params.reducedFrontingProject && !nonGoalsReady ? 'Which non-goals need explicit guardrails in verification?' : null,
        !params.reducedFrontingProject && !successReady ? 'Which success criteria need evidence signals in the generated contract?' : null,
      ].filter((item): item is string => Boolean(item)),
    },
    {
      key: 'generation_and_extensions',
      title: developerDefinitionSectionLabel('generation_and_extensions'),
      prerequisitesReady: baselineReady && (params.reducedFrontingProject || shapeReady),
      detail: params.reducedFrontingProject
        ? 'Generation and extension settings can be drafted from the locked fronting intent and selected integration profile.'
        : shapeReady
          ? 'Generation and extension settings can be drafted from the locked baseline and then adjusted only where delivery choices genuinely differ.'
          : 'Generation settings should follow the locked service shape and delivery path, not free-form guesses.',
      questions: [
        !params.reducedFrontingProject && !shapeReady ? 'Which locked service shape should generation target?' : null,
      ].filter((item): item is string => Boolean(item)),
    },
  ]

  return cards.map((card) => {
    const clarificationResolved = hasSavedSectionClarification(params.pmArtifacts, 'dev', card.key)
    const status = alignedDefinition
      ? 'ready'
      : !baselineReady
        ? 'blocked'
        : clarificationResolved
          ? 'draftable'
        : card.prerequisitesReady
          ? 'draftable'
          : card.questions.length > 0
            ? 'needs_clarification'
            : 'blocked'

    return {
      key: card.key,
      title: card.title,
      status,
      detail: alignedDefinition
        ? 'The saved Developer Definition already matches the locked baseline for this section.'
        : !baselineReady
          ? productHandoffReady
            ? 'Product Design is ready. Lock the Product Design baseline so Developer Design can draft from a stable handoff.'
            : 'Complete requirements, scenarios, and service design before locking the Product Design baseline.'
          : clarificationResolved
            ? `${card.title} has saved clarification answers. Rerun the draft step so Developer Definition can absorb them deterministically.`
            : card.detail,
      path: status === 'blocked' && !baselineReady ? (productHandoffReady ? developerPath : pmPath) : definitionPath,
      action_label: !baselineReady && productHandoffReady ? 'Lock Baseline' : developerSufficiencyActionLabel(status),
      questions: (status === 'ready' || clarificationResolved ? [] : card.questions).slice(0, 3),
    }
  })
}

export function developerDefinitionMatchesCurrentContext(params: {
  definition: DeveloperDefinitionData | null
  baseline: DeveloperBaselineData | null
  requirements: RequirementsRecord | null
  scenarios: ArtifactRecord[]
  shape: ShapeRecord | null
}): boolean {
  const { definition, baseline, requirements, scenarios, shape } = params
  if (!definition || !baseline) return false
  return (
    (definition.source_inputs.product_revision_artifact_id ?? null) === (baseline.source_inputs.product_revision_artifact_id ?? null)
    && (definition.source_inputs.product_revision_number ?? null) === (baseline.source_inputs.product_revision_number ?? null)
    && (definition.source_inputs.product_design_hash ?? null) === (baseline.source_inputs.product_design_hash ?? null)
    && definition.source_inputs.requirements_id === (requirements?.id ?? null)
    && definition.source_inputs.requirements_hash === (requirements?.content_hash ?? null)
    && definition.source_inputs.shape_id === (shape?.id ?? null)
    && definition.source_inputs.shape_hash === (shape?.content_hash ?? null)
    && canonicalScenarioSetHash(definition.source_inputs.scenario_set_hash) === canonicalScenarioSetHash(scenarioSetHash(scenarios))
    && definition.source_inputs.scenario_ids.length === scenarios.length
    && definition.source_inputs.scenario_ids.every((id) => scenarios.some((scenario) => scenario.id === id))
    && definition.source_inputs.baseline_locked_at === baseline.locked_at
  )
}

function canonicalCapabilityPathTemplate(capabilityId: string): string {
  const segments = capabilityId
    .split('.')
    .map((segment) => segment.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, ''))
    .filter(Boolean)
  return segments.length ? `/${segments.join('/')}` : '/capability'
}

function canonicalCapabilityOutputShape(capabilityId: string): string {
  const normalized = capabilityId.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '')
  return normalized ? `${normalized}_result` : 'governed_result'
}

const SAFE_OUTPUT_SHAPE_PATTERN = /^[A-Za-z_][A-Za-z0-9_]{0,127}$/

function canonicalOutputShape(value: unknown, capabilityId: string): string {
  const trimmed = String(value ?? '').trim()
  if (SAFE_OUTPUT_SHAPE_PATTERN.test(trimmed)) return trimmed
  return canonicalCapabilityOutputShape(capabilityId)
}

const SAFE_BACKEND_OPERATION_PATTERN = /^[A-Za-z_][A-Za-z0-9_.:-]{0,127}$/

function canonicalBackendOperation(value: unknown, capabilityId: string): string {
  const trimmed = String(value ?? '').trim()
  if (SAFE_BACKEND_OPERATION_PATTERN.test(trimmed)) return trimmed
  return capabilityId
}

function normalizedCapabilityKind(capability: DeveloperCapabilityFormalization): 'atomic' | 'composed' {
  return capability.kind === 'composed' ? 'composed' : 'atomic'
}

function permissionPolicyDecision(permission: DeveloperPermissionIntentRuleBinding): string {
  const access = permission.access_posture.trim()
  const outcome = permission.governed_outcome_type.trim()
  if (access === 'denied' || outcome === 'deny_request') return 'deny'
  if (outcome === 'clarification_required') return 'clarify'
  if (access === 'approval_required' || outcome === 'approval_required' || outcome === 'approval_stop') return 'approval_required'
  if (access === 'bounded' || access === 'restricted' || outcome === 'bounded_result' || outcome === 'masked_or_restricted_result') return 'allow_with_limits'
  return 'allow'
}

function permissionPolicyBindings(definition: DeveloperDefinitionData | null | undefined) {
  const capabilities = definition?.capability_formalizations ?? []
  return (definition?.permission_intent_bindings ?? []).map((permission) => {
    const serviceIds = permission.target_service_ids ?? []
    const capabilityIds = (permission.target_capability_ids?.length
      ? permission.target_capability_ids
      : capabilities
          .filter((capability) => serviceIds.includes(capability.service_id))
          .map((capability) => capability.capability_id)
    ).filter(Boolean)
    const requiredScopes = capabilities
      .filter((capability) => capabilityIds.includes(capability.capability_id))
      .flatMap((capability) => capability.minimum_scope ?? [])
      .filter(Boolean)
    return {
      id: `policy_${permission.id}`,
      source_permission_id: permission.id,
      actor_id: permission.actor_id,
      principal_selector: {
        claim: 'actor_id',
        equals: permission.actor_id,
      },
      business_area: permission.business_area,
      business_area_label: permission.business_area_label,
      service_ids: serviceIds,
      capability_ids: Array.from(new Set(capabilityIds)),
      required_scopes: Array.from(new Set(requiredScopes)),
      decision: permissionPolicyDecision(permission),
      business_rule: permission.governed_outcome,
      enforcement_notes: permission.formalization_strategy,
    }
  })
}

export function buildDeveloperDefinitionContract(params: {
  project: ProjectDetail
  baseline: DeveloperBaselineData | null
  requirements: RequirementsRecord | null
  scenarios: ArtifactRecord[]
  shape: ShapeRecord | null
  traceability: TraceabilityRecordData | null
  developerDefinition: DeveloperDefinitionData | null
}) {
  const coverage = params.traceability?.coverage ?? []
  const definition = params.developerDefinition

  return {
    artifact_type: 'anip_service_definition',
    contract_schema_version: 'anip-service-definition/v1',
    generated_at: new Date().toISOString(),
    project: {
      id: params.project.id,
      name: params.project.name,
      summary: params.project.summary,
      domain: params.project.domain,
      labels: params.project.labels,
    },
    identity: definition?.identity ?? {
      system_name: params.project.name,
      domain_name: params.project.domain,
      delivery_model: 'standalone_service',
      architecture_shape: 'single_service',
    },
    authority: definition?.authority ?? null,
    audit: definition?.audit ?? null,
    generation: definition?.generation
      ? {
          protocols: definition.generation.protocols,
          layout_strategy: definition.generation.layout_strategy,
          selected_service_ids: definition.generation.selected_service_ids,
        }
      : null,
    naming: definition?.naming ?? null,
    backend_bindings: definition?.backend_bindings ?? [],
    application_integration_governance: definition?.application_integration_governance ?? null,
    data_access_governance: definition?.data_access_governance ?? null,
    data_domain: definition?.data_domain ?? null,
    domain_concept_bindings: definition?.domain_concept_bindings ?? [],
    application_object_model: definition?.application_object_model ?? [],
    service_topology_bindings: (definition?.service_topology_bindings ?? []).map((binding) => ({
      id: binding.id,
      service_id: binding.service_id,
      service_name: binding.service_name,
      source_role: binding.source_role,
      source_capabilities: binding.source_capabilities,
      source_concepts: binding.source_concepts,
      formalized_capability_ids: binding.formalized_capability_ids,
      owned_concept_ids: binding.owned_concept_ids,
      implementation_notes: binding.implementation_notes,
    })),
    capability_formalizations: (definition?.capability_formalizations ?? []).map((capability) => ({
      ...capability,
      inputs: (capability.inputs ?? []).map((input) => contractInputFormalization(input)),
      kind: normalizedCapabilityKind(capability),
      composition: normalizedCapabilityKind(capability) === 'composed' ? compactDeveloperComposition(capability.composition) : null,
      grant_policy: capability.grant_policy ?? null,
      backend_operation: canonicalBackendOperation(capability.backend_operation, capability.capability_id),
      path_template: capability.path_template?.trim() || canonicalCapabilityPathTemplate(capability.capability_id),
      output_shape: canonicalOutputShape(capability.output_shape, capability.capability_id),
    })),
    actor_expectations: definition?.actor_expectations ?? [],
    permission_intent_bindings: definition?.permission_intent_bindings ?? [],
    runtime_policy_bindings: permissionPolicyBindings(definition),
    scenario_formalizations: definition?.scenario_formalizations ?? [],
    composition_rules: definition?.composition_rules ?? [],
    verification: definition?.verification ?? null,
    integration_fronting: definition?.integration_fronting ?? null,
    rationale: definition?.rationale ?? [],
    source: {
      product_design_baseline: {
        locked_at: params.baseline?.locked_at ?? null,
        product_revision_artifact_id: params.baseline?.source_inputs.product_revision_artifact_id ?? null,
        product_revision_number: params.baseline?.source_inputs.product_revision_number ?? null,
        product_design_hash: params.baseline?.source_inputs.product_design_hash ?? null,
        requirements: params.requirements
          ? {
              id: params.requirements.id,
              title: params.requirements.title,
              content_hash: params.requirements.content_hash,
            }
          : null,
        scenario_pack: params.scenarios.map((scenario) => ({
          id: scenario.id,
          title: scenario.title,
          scenario_key: String((scenario.data?.scenario?.name ?? '') || ''),
          content_hash: scenario.content_hash,
        })),
        service_design: serviceDesignSummary(params.shape),
      },
      developer_definition_revision: definition?.saved_revision
        ? {
            revision_number: definition.saved_revision.revision_number,
            revision_artifact_id: definition.saved_revision.revision_artifact_id,
            previous_revision_artifact_id: definition.saved_revision.previous_revision_artifact_id,
            saved_at: definition.saved_revision.saved_at,
          }
        : null,
      product_alignment: definition?.product_alignment ?? null,
      traceability: params.traceability
        ? {
            developer_status: params.traceability.developer_status,
            pm_review_status: params.traceability.pm_review_status,
            developer_marked_at: params.traceability.developer_marked_at,
            pm_reviewed_at: params.traceability.pm_reviewed_at,
          }
        : null,
    },
    studio_traceability: {
      sections: DEVELOPER_DEFINITION_SECTIONS.map((section) => {
        const sectionCoverage = summarizeCoverageForDefinitionSection(coverage, section.id)
        return {
          id: section.id,
          label: section.label,
          description: section.description,
          owners: section.owners,
          coverage: sectionCoverage.summary,
          linked_product_design_items: sectionCoverage.items.map((item) => ({
            id: item.id,
            source: item.source,
            section: item.section,
            label: item.label,
            detail: item.detail,
            status: item.status,
            rationale: item.rationale,
          })),
        }
      }),
    },
    generator_launch: {
      source_of_truth: 'compiled_contract',
      primary_output_mode: 'runtime_target',
      transitional_pages_required: false,
      runtime_target_only: true,
    },
  }
}

export { implementationLanguageForAdapter }
