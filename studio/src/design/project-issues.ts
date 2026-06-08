import {
  ACTOR_MODEL_ARTIFACT_TYPE,
  BUSINESS_AREAS_ARTIFACT_TYPE,
  NON_GOALS_ARTIFACT_TYPE,
  PERMISSION_INTENT_ARTIFACT_TYPE,
  PRODUCT_SUMMARY_ARTIFACT_TYPE,
  SUCCESS_CRITERIA_ARTIFACT_TYPE,
  buildProductDesignSufficiencyCards,
  findActorModelArtifact,
  findBusinessAreasArtifact,
  findPermissionIntentArtifact,
  type ActorModelData,
  type BusinessAreasData,
  type PermissionIntentData,
} from './product-design'
import type { ArtifactRecord, ProjectDetail, ProjectDocumentRecord, RequirementsRecord, ShapeRecord } from './project-types'
import {
  canonicalScenarioSetHash,
  findDeveloperBaselineArtifact,
  findTraceabilityArtifact,
  hasReviewedCoverageResolution,
  summarizeCoverage,
} from './traceability'
import {
  buildHighRiskConfirmationReport,
  highRiskConfirmationReportFromArtifacts,
  unresolvedHighRiskConfirmationItems,
} from './high-risk-confirmations'
import {
  buildDeveloperDefinitionData,
  developerDefinitionTargetStatus,
  findDeveloperDefinitionArtifact,
  findIntegrationFrontingMappingArtifacts,
  validateDeveloperDefinitionRequiredFields,
} from './developer-definition'
import {
  analyzeAgentConsumptionReadiness,
  applyReadinessFindingReviews,
  normalizeReadinessFindingReviews,
} from './agent-consumption-readiness'
import { validateRequirements, validateScenario } from './schemas'
import {
  hasFrontingIntegrationSource,
  hasFrontingIntentSource,
  isGovernedFrontingProject,
} from './source-documents'

export type ProjectIssueSeverity = 'warning' | 'error'

export interface ProjectIssueSummary {
  severity: ProjectIssueSeverity
  count: number
  messages: string[]
}

type IssueMap = Record<string, ProjectIssueSummary>
type AggregateEntry = { key: string; label: string }

function addIssue(map: IssueMap, key: string, severity: ProjectIssueSeverity, message: string): void {
  const existing = map[key]
  if (!existing) {
    map[key] = { severity, count: 1, messages: [message] }
    return
  }
  if (existing.messages.includes(message)) {
    if (severity === 'error') existing.severity = 'error'
    return
  }
  existing.count += 1
  existing.messages.push(message)
  if (severity === 'error') existing.severity = 'error'
}

function setAggregateIssue(
  map: IssueMap,
  targetKey: string,
  entries: AggregateEntry[],
): void {
  const affectedEntries = entries
    .map((entry) => ({ entry, issue: map[entry.key] }))
    .filter((item): item is { entry: AggregateEntry; issue: ProjectIssueSummary } => Boolean(item.issue))

  if (affectedEntries.length === 0) {
    delete map[targetKey]
    return
  }

  map[targetKey] = {
    severity: affectedEntries.some((item) => item.issue.severity === 'error') ? 'error' : 'warning',
    count: affectedEntries.reduce((total, item) => total + item.issue.count, 0),
    messages: affectedEntries.map(({ entry, issue }) => {
      const firstMessage = issue.messages[0] || `${entry.label} needs attention.`
      const remainingCount = Math.max(0, issue.messages.length - 1)
      return remainingCount > 0
        ? `${entry.label}: ${firstMessage} (+${remainingCount} more)`
        : `${entry.label}: ${firstMessage}`
    }),
  }
}

function uniqueTrimmed(values: Array<string | undefined | null>): Set<string> {
  return new Set(values.map((value) => safeText(value)).filter(Boolean))
}

function safeText(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function safeObjectList<T>(value: unknown): T[] {
  return Array.isArray(value)
    ? value.filter((item): item is T => Boolean(item) && typeof item === 'object' && !Array.isArray(item))
    : []
}

function hasCompleteBackendBinding(value: unknown): boolean {
  const binding = value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {}
  return Boolean(
    safeText(binding.connection_ref)
    && Array.isArray(binding.raw_operation_refs)
    && binding.raw_operation_refs.length > 0,
  )
}

function shapePayload(record: ShapeRecord | null | undefined): Record<string, any> | null {
  const root = record?.data?.shape ?? record?.data
  return root && typeof root === 'object' && !Array.isArray(root) ? root as Record<string, any> : null
}

function activeShapePayload(shapes: ShapeRecord[]): Record<string, any> | null {
  const active = shapes.find((shape) => shape.status === 'active')
    ?? shapes.find((shape) => shape.status === 'draft')
    ?? shapes[0]
  return shapePayload(active)
}

function serviceId(value: unknown): string {
  return safeText(value)
}

function serviceLabel(service: Record<string, any>): string {
  return safeText(service.name) || safeText(service.id) || 'Unnamed service'
}

function shapeServices(shape: Record<string, any> | null): Array<{ id: string; label: string }> {
  return safeObjectList<Record<string, any>>(shape?.services)
    .map((service) => ({ id: serviceId(service.id), label: serviceLabel(service) }))
    .filter((service) => Boolean(service.id))
}

function shapeCoordinationEdges(shape: Record<string, any> | null): Array<{ from: string; to: string; label: string }> {
  const serviceLabels = new Map(shapeServices(shape).map((service) => [service.id, service.label] as const))
  return safeObjectList<Record<string, any>>(shape?.coordination)
    .map((edge) => {
      const from = serviceId(edge.from ?? edge.source ?? edge.source_service_id ?? edge.from_service_id)
      const to = serviceId(edge.to ?? edge.target ?? edge.target_service_id ?? edge.to_service_id)
      const relationship = safeText(edge.relationship)
      const fromLabel = serviceLabels.get(from) ?? (from || 'source')
      const toLabel = serviceLabels.get(to) ?? (to || 'target')
      const label = `${fromLabel} -> ${toLabel}${relationship ? ` (${relationship})` : ''}`
      return { from, to, label }
    })
    .filter((edge) => Boolean(edge.from && edge.to))
}

function legacyParticipatingServices(scenarioData: Record<string, any>): string[] {
  return safeObjectList<Record<string, any>>(scenarioData.additional_context)
    .filter((entry) => safeText(entry.semantic_type) === 'participating_services')
    .flatMap((entry) =>
      safeText(entry.value)
        .split(/\n|,|;/)
        .map((value) => value.trim())
        .filter(Boolean),
    )
}

function scenarioParticipatingServices(record: ArtifactRecord): Set<string> {
  const scenarioData = record.data?.scenario && typeof record.data.scenario === 'object'
    ? record.data.scenario as Record<string, any>
    : {}
  const explicit = Array.isArray(scenarioData.participating_services)
    ? scenarioData.participating_services.map((value) => safeText(value)).filter(Boolean)
    : []
  return new Set([...explicit, ...legacyParticipatingServices(scenarioData)])
}

function addProductServiceCoverageIssues(params: {
  map: IssueMap
  shapes: ShapeRecord[]
  scenarios: ArtifactRecord[]
  reducedFronting: boolean
}): void {
  if (params.reducedFronting || params.scenarios.length === 0) return
  const shape = activeShapePayload(params.shapes)
  const services = shapeServices(shape)
  if (services.length <= 1) return

  const scenarioServiceSets = params.scenarios.map(scenarioParticipatingServices)
  const serviceIds = new Set(services.map((service) => service.id))
  const uncoveredServices = services.filter((service) =>
    !scenarioServiceSets.some((set) => set.has(service.id)),
  )
  if (uncoveredServices.length > 0) {
    addIssue(
      params.map,
      'project-scenarios-list',
      'error',
      `Scenario pack does not cover service design service(s): ${uncoveredServices.map((service) => service.label).join(', ')}.`,
    )
  }

  const uncoveredEdges = shapeCoordinationEdges(shape)
    .filter((edge) => serviceIds.has(edge.from) && serviceIds.has(edge.to))
    .filter((edge) =>
      !scenarioServiceSets.some((set) => set.has(edge.from) && set.has(edge.to)),
    )
  if (uncoveredEdges.length > 0) {
    addIssue(
      params.map,
      'project-scenarios-list',
      'error',
      `Scenario pack does not cover service coordination edge(s): ${uncoveredEdges.map((edge) => edge.label).join(', ')}.`,
    )
  }
}

function formatSchemaIssueMessage(title: string, path: string, message: string, params?: Record<string, unknown>): string {
  const at = path ? ` at ${path.replace(/^\//, '').replace(/\//g, ' / ')}` : ''
  const additionalProperty = typeof params?.additionalProperty === 'string' ? params.additionalProperty : ''
  if (additionalProperty) {
    return `${title}: unsupported field "${additionalProperty}"${at || ' at root'}.`
  }
  const missingProperty = typeof params?.missingProperty === 'string' ? params.missingProperty : ''
  if (missingProperty) {
    return `${title}: missing required field "${missingProperty}"${at || ' at root'}.`
  }
  return `${title}: ${message}${at}.`
}

function addSchemaValidationIssues(
  map: IssueMap,
  targetKey: string,
  records: Array<{ id: string; title?: string; data?: Record<string, unknown> }>,
  validator: ((value: unknown) => boolean) & { errors?: Array<{ instancePath: string; message?: string; params?: Record<string, unknown> }> | null },
  label: string,
): void {
  records.forEach((record) => {
    const valid = validator(record.data ?? {})
    if (valid || !validator.errors?.length) return
    const title = safeText(record.title) || record.id || label
    validator.errors.forEach((error) => {
      addIssue(
        map,
        targetKey,
        'error',
        formatSchemaIssueMessage(title, error.instancePath, error.message ?? 'validation error', error.params),
      )
    })
  })
}

function coverageTargetIssueKey(targetKey: string): string | null {
  if (
    targetKey.startsWith('developer_definition.product_alignment.')
    || targetKey.startsWith('developer_definition.identity.')
    || targetKey.startsWith('developer_definition.authority.')
    || targetKey.startsWith('developer_definition.backend_bindings.')
    || targetKey.startsWith('developer_definition.service_backend_bindings.')
    || targetKey.startsWith('developer_definition.service_topology:')
    || targetKey === 'developer_definition.contracts.service_identity_topology'
    || targetKey === 'developer_definition.contracts.authority_and_approval'
    || targetKey === 'developer_definition.contracts.backend_bindings'
  ) {
    return 'project-developer-service-formalization'
  }
  if (
    targetKey.startsWith('developer_definition.actor_expectation:')
    || targetKey.startsWith('developer_definition.permission_rule:')
  ) {
    return 'project-developer-governance-bindings'
  }
  if (
    targetKey.startsWith('developer_definition.audit.')
    || targetKey === 'developer_definition.contracts.audit_and_lineage'
  ) {
    return 'project-developer-audit-lineage'
  }
  if (
    targetKey.startsWith('developer_definition.domain_concept:')
    || targetKey === 'developer_definition.contracts.data_contracts'
  ) {
    return 'project-developer-data-contract-formalization'
  }
  if (
    targetKey.startsWith('developer_definition.scenario_formalization:')
    || targetKey === 'developer_definition.contracts.scenario_context'
  ) {
    return 'project-developer-scenario-formalization'
  }
  if (
    targetKey.startsWith('developer_definition.composition_rule:')
    || targetKey === 'developer_definition.contracts.execution_semantics'
  ) {
    return 'project-developer-scenario-execution-semantics'
  }
  if (targetKey === 'developer_definition.contracts.capability_contracts') {
    return 'project-developer-capability-formalization'
  }
  if (
    targetKey.startsWith('developer_definition.generation.')
    || targetKey === 'developer_definition.contracts.generation_and_extensions'
  ) {
    return 'project-developer-generation-settings'
  }
  if (targetKey.startsWith('developer_definition.integration_fronting:')) {
    return 'project-integration-fronting'
  }
  return null
}

function developerDefinitionValidationIssueKey(path: string): string {
  if (
    path.startsWith('product_alignment.')
    || path.startsWith('identity.')
    || path.startsWith('authority.')
    || path.startsWith('backend_bindings.')
    || path.startsWith('service_backend_bindings.')
    || path.startsWith('service_topology_bindings.')
  ) {
    return 'project-developer-service-formalization'
  }
  if (path.startsWith('capability_formalizations.')) return 'project-developer-capability-formalization'
  if (path.startsWith('scenario_formalizations.')) return 'project-developer-scenario-formalization'
  if (path.startsWith('composition_rules.')) return 'project-developer-scenario-execution-semantics'
  if (
    path.startsWith('actor_expectations.')
    || path.startsWith('permission_intent_bindings.')
  ) {
    return 'project-developer-governance-bindings'
  }
  if (path.startsWith('audit.')) return 'project-developer-audit-lineage'
  if (
    path.startsWith('data_domain.')
    || path.startsWith('domain_concept_bindings.')
    || path.startsWith('application_object_model.')
  ) {
    return 'project-developer-data-contract-formalization'
  }
  if (path.startsWith('verification.')) return 'project-developer-verification-expectations'
  if (path.startsWith('generation.') || path.startsWith('naming.')) return 'project-developer-generation-settings'
  return 'project-developer-definition'
}

function addProductDesignIssues(params: {
  map: IssueMap
  project: ProjectDetail
  pmArtifacts: ArtifactRecord[]
  requirements: RequirementsRecord[]
  scenarios: ArtifactRecord[]
  documents: ProjectDocumentRecord[]
  shapes: ShapeRecord[]
}): void {
  const reducedFronting = isGovernedFrontingProject(params.project)
  const cards = buildProductDesignSufficiencyCards(params.project.id, params.pmArtifacts, {
    documents_count: params.documents.length,
    requirements_count: params.requirements.length,
    scenarios_count: params.scenarios.length,
  })
  const cardToNavKey: Record<string, string> = {
    [PRODUCT_SUMMARY_ARTIFACT_TYPE]: 'project-product-summary',
    [ACTOR_MODEL_ARTIFACT_TYPE]: 'project-actor-model',
    [BUSINESS_AREAS_ARTIFACT_TYPE]: 'project-business-areas',
    [PERMISSION_INTENT_ARTIFACT_TYPE]: 'project-permission-intent',
    [NON_GOALS_ARTIFACT_TYPE]: 'project-non-goals',
    [SUCCESS_CRITERIA_ARTIFACT_TYPE]: 'project-success-criteria',
  }
  cards
    .filter((card) => !reducedFronting || [
      PRODUCT_SUMMARY_ARTIFACT_TYPE,
      ACTOR_MODEL_ARTIFACT_TYPE,
      BUSINESS_AREAS_ARTIFACT_TYPE,
      PERMISSION_INTENT_ARTIFACT_TYPE,
    ].includes(card.key))
    .forEach((card) => {
      if (card.status === 'ready') return
      const severity = reducedFronting
        ? 'warning'
        : card.status === 'blocked' || card.status === 'needs_clarification'
          ? 'error'
          : 'warning'
      addIssue(
        params.map,
        cardToNavKey[card.key] ?? `project-${card.key}`,
        severity,
        card.questions[0] || `${card.title} is not complete.`,
      )
    })

  if (params.requirements.length === 0) {
    addIssue(
      params.map,
      'project-requirements-list',
      reducedFronting ? 'warning' : 'error',
      reducedFronting
        ? 'No governed fronting requirements have been created yet.'
        : 'No requirements set has been created.',
    )
  } else {
    addSchemaValidationIssues(
      params.map,
      'project-requirements-list',
      params.requirements,
      validateRequirements,
      'Requirements',
    )
  }
  if (params.scenarios.length === 0) {
    addIssue(
      params.map,
      'project-scenarios-list',
      reducedFronting ? 'warning' : 'error',
      reducedFronting
        ? 'No governed fronting situations have been created yet.'
        : 'No scenarios have been created.',
    )
  } else {
    addSchemaValidationIssues(
      params.map,
      'project-scenarios-list',
      params.scenarios,
      validateScenario,
      'Scenario',
    )
    addProductServiceCoverageIssues({
      map: params.map,
      shapes: params.shapes,
      scenarios: params.scenarios,
      reducedFronting,
    })
  }
  if (reducedFronting) {
    if (params.documents.length === 0) {
      addIssue(params.map, 'project-source-docs', 'warning', 'Add fronting intent plus API/MCP/backend evidence to start Express Mode.')
    } else {
      if (!hasFrontingIntentSource(params.documents)) {
        addIssue(params.map, 'project-source-docs', 'warning', 'Fronting intent source is missing.')
      }
      if (!hasFrontingIntegrationSource(params.documents)) {
        addIssue(params.map, 'project-source-docs', 'warning', 'Integration evidence source is missing.')
      }
    }
  } else if (params.documents.length === 0) {
    addIssue(params.map, 'project-source-docs', 'warning', 'No source documents are attached.')
  }

  const actorModel = findActorModelArtifact(params.pmArtifacts)?.data as ActorModelData | undefined
  const businessAreas = findBusinessAreasArtifact(params.pmArtifacts)?.data as BusinessAreasData | undefined
  const permissionIntent = findPermissionIntentArtifact(params.pmArtifacts)?.data as PermissionIntentData | undefined
  const actorIds = uniqueTrimmed(safeObjectList<ActorModelData['actors'][number]>(actorModel?.actors).map((actor) => actor.actor_id))
  const businessAreaIds = uniqueTrimmed(safeObjectList<BusinessAreasData['entries'][number]>(businessAreas?.entries).map((entry) => entry.business_area_id))
  const missingActorRefs = safeObjectList<PermissionIntentData['rules'][number]>(permissionIntent?.rules)
    .map((rule) => safeText(rule.actor_id))
    .filter((actorId) => actorId && !actorIds.has(actorId))
  const missingBusinessAreaRefs = safeObjectList<PermissionIntentData['rules'][number]>(permissionIntent?.rules)
    .map((rule) => safeText(rule.business_area))
    .filter((businessAreaId) => businessAreaId && !businessAreaIds.has(businessAreaId))

  if (missingActorRefs.length > 0) {
    addIssue(params.map, 'project-permission-intent', 'error', `Permission rules reference actor ids missing from Actor Model: ${[...new Set(missingActorRefs)].join(', ')}.`)
    addIssue(params.map, 'project-actor-model', 'error', 'Actor Model is missing ids referenced by Permission Intent.')
  }
  if (missingBusinessAreaRefs.length > 0) {
    addIssue(params.map, 'project-permission-intent', 'error', `Permission rules reference business-area ids missing from Business Areas: ${[...new Set(missingBusinessAreaRefs)].join(', ')}.`)
    addIssue(params.map, 'project-business-areas', 'error', 'Business Areas is missing ids referenced by Permission Intent.')
  }
}

function addDeveloperIssues(params: {
  map: IssueMap
  project: ProjectDetail
  pmArtifacts: ArtifactRecord[]
  documents: ProjectDocumentRecord[]
  requirements: RequirementsRecord[]
  scenarios: ArtifactRecord[]
  shapes: ShapeRecord[]
  sourceInputContractEvidenceReady?: boolean
}): void {
  const reducedFronting = isGovernedFrontingProject(params.project)
  const baseline = findDeveloperBaselineArtifact(params.pmArtifacts)
  const traceability = findTraceabilityArtifact(params.pmArtifacts)
  const definition = findDeveloperDefinitionArtifact(params.pmArtifacts)
  const mappings = findIntegrationFrontingMappingArtifacts(params.pmArtifacts)

  if (!baseline) {
    const baselineRequiredKeys = reducedFronting
      ? [
          'project-fronting-express',
          'project-developer-handoff',
          'project-integration-fronting',
          'project-developer-definition',
        ]
      : [
          'project-developer-handoff',
          'project-developer-service-formalization',
          'project-developer-governance-bindings',
          'project-integration-fronting',
          'project-developer-capability-formalization',
          'project-developer-data-contract-formalization',
          'project-developer-scenario-formalization',
          'project-developer-scenario-execution-semantics',
          'project-developer-generation-settings',
          'project-developer-verification-expectations',
          'project-developer-coverage',
          'project-developer-gaps',
          'project-developer-definition',
        ]
    baselineRequiredKeys.forEach((key) => {
      addIssue(
        params.map,
        key,
        reducedFronting ? 'warning' : 'error',
        reducedFronting
          ? 'Lock reviewed fronting intent before generating the Developer Definition.'
          : 'Developer baseline is not locked.',
      )
    })
    return
  }
  if (!traceability) {
    addIssue(params.map, 'project-developer-coverage', 'warning', 'Coverage Mapping has not been created.')
  }
  if (!definition) {
    addIssue(params.map, 'project-developer-definition', 'warning', 'Developer Definition has not been saved.')
  }

  const baselineData = baseline.data as {
    locked_at?: string
    source_inputs?: {
      requirements_id?: string
      primary_scenario_id?: string | null
      scenario_ids?: string[]
      scenario_set_hash?: string | null
      shape_id?: string
    }
  }
  const traceabilityData = traceability?.data as {
    coverage?: Array<Record<string, unknown>>
    source_inputs?: {
      requirements_id?: string | null
      scenario_id?: string | null
      scenario_ids?: string[] | null
      scenario_set_hash?: string | null
      shape_id?: string | null
      baseline_locked_at?: string | null
    }
  } | undefined
  const definitionData = definition?.data as Record<string, unknown> | undefined
  const lockedRequirements = params.requirements.find((item) => item.id === baselineData.source_inputs?.requirements_id) ?? null
  const lockedScenarioIds = Array.isArray(baselineData.source_inputs?.scenario_ids)
    ? baselineData.source_inputs?.scenario_ids ?? []
    : []
  const lockedScenarios = lockedScenarioIds
    .map((id) => params.scenarios.find((item) => item.id === id) ?? null)
    .filter((item): item is ArtifactRecord => item != null)
  const lockedShape = params.shapes.find((item) => item.id === baselineData.source_inputs?.shape_id) ?? null
  const effectiveDefinition = buildDeveloperDefinitionData({
    project: params.project,
    baseline: baselineData as any,
    requirements: lockedRequirements as any,
    scenarios: lockedScenarios,
    shape: lockedShape,
    pmArtifacts: params.pmArtifacts,
    existing: (definitionData as any) ?? null,
  })
  const traceabilityAligned = !traceabilityData?.source_inputs
    || (
      traceabilityData.source_inputs.requirements_id === (baselineData.source_inputs?.requirements_id ?? null)
      && traceabilityData.source_inputs.shape_id === (baselineData.source_inputs?.shape_id ?? null)
      && traceabilityData.source_inputs.baseline_locked_at === (baselineData.locked_at ?? null)
      && (
        !traceabilityData.source_inputs.scenario_set_hash
        || canonicalScenarioSetHash(traceabilityData.source_inputs.scenario_set_hash) === canonicalScenarioSetHash(baselineData.source_inputs?.scenario_set_hash)
      )
      && (
        Array.isArray(traceabilityData.source_inputs.scenario_ids)
          ? traceabilityData.source_inputs.scenario_ids.length === lockedScenarioIds.length
            && lockedScenarioIds.every((id) => traceabilityData.source_inputs?.scenario_ids?.includes(id))
          : traceabilityData.source_inputs.scenario_id === (baselineData.source_inputs?.primary_scenario_id ?? lockedScenarioIds[0] ?? null)
      )
    )
  if (traceability && !traceabilityAligned) {
    addIssue(
      params.map,
      'project-developer-coverage',
      'warning',
      'The saved Coverage Mapping record does not match the current locked baseline. Rebuild coverage before using it as current implementation evidence.',
    )
  }
  for (const issue of validateDeveloperDefinitionRequiredFields(effectiveDefinition)) {
    if (
      !definition
      && params.sourceInputContractEvidenceReady
      && issue.path.startsWith('capability_formalizations.')
      && issue.path.endsWith('.inputs')
      && issue.message.includes('must define concrete input contract details')
    ) {
      continue
    }
    addIssue(
      params.map,
      developerDefinitionValidationIssueKey(issue.path),
      'error',
      issue.message,
    )
  }
  const effectiveCoverage = traceabilityAligned ? (traceabilityData?.coverage ?? []).map((item) => {
    const mappingMode = String(item.mapping_mode ?? '')
    const mappingTargetKey = String(item.mapping_target_key ?? '')
    if (mappingMode !== 'automatic' || !mappingTargetKey) return item
    if (hasReviewedCoverageResolution(item as any)) return item
    return {
      ...item,
      status: developerDefinitionTargetStatus(mappingTargetKey, {
        developerDefinition: effectiveDefinition,
      }),
    }
  }) : []
  const coverageSummary = summarizeCoverage(effectiveCoverage as any)

  if (coverageSummary.missing > 0) {
    addIssue(
      params.map,
      'project-developer-coverage',
      'error',
      `${coverageSummary.missing} Product Design item${coverageSummary.missing === 1 ? '' : 's'} are still not addressed.`,
    )
  }
  if (coverageSummary.partial > 0) {
    addIssue(
      params.map,
      'project-developer-coverage',
      'warning',
      `${coverageSummary.partial} Product Design item${coverageSummary.partial === 1 ? '' : 's'} are only partially addressed.`,
    )
  }
  effectiveCoverage.forEach((item) => {
    const mappingMode = String(item.mapping_mode ?? '')
    const mappingTargetKey = String(item.mapping_target_key ?? '')
    const status = String(item.status ?? '')
    const label = String(item.label ?? 'Coverage item')
    if (mappingMode !== 'automatic' || !mappingTargetKey) return
    const issueKey = coverageTargetIssueKey(mappingTargetKey)
    if (!issueKey) return
    if (status === 'not_addressed') {
      addIssue(params.map, issueKey, 'error', `${label} is not addressed.`)
    } else if (status === 'partially_addressed') {
      addIssue(params.map, issueKey, 'warning', `${label} is only partially addressed.`)
    }
  })
  if (reducedFronting) {
    if (mappings.length === 0) {
      addIssue(params.map, 'project-integration-fronting', 'error', 'No governed integration-fronting mappings have been accepted.')
    }
    mappings.forEach((artifact) => {
      const data = artifact.data ?? {}
      const bindings = Array.isArray(data.backend_bindings) && data.backend_bindings.length > 0
        ? data.backend_bindings
        : [{ connection_ref: data.connection_ref, raw_operation_refs: data.raw_operation_refs }]
      const hasReadyBinding = bindings.some(hasCompleteBackendBinding)
      if (!hasReadyBinding) {
        addIssue(params.map, 'project-integration-fronting', 'error', `${artifact.title || artifact.id} has incomplete backend bindings.`)
      }
    })
  } else if (params.shapes.length === 0) {
    addIssue(params.map, 'project-shapes', 'warning', 'No service design shape has been created.')
  }

  const highRiskReport = buildHighRiskConfirmationReport({
    project: params.project,
    pmArtifacts: params.pmArtifacts,
    documents: params.documents,
    requirements: params.requirements,
    scenarios: params.scenarios,
    shapes: params.shapes,
    existing: highRiskConfirmationReportFromArtifacts(params.pmArtifacts),
    sourceInputContractEvidenceReady: params.sourceInputContractEvidenceReady,
  })
  const unresolvedHighRisk = unresolvedHighRiskConfirmationItems(highRiskReport)
  if (unresolvedHighRisk.length > 0) {
    addIssue(
      params.map,
      'project-developer-coverage',
      'error',
      `${unresolvedHighRisk.length} high-risk confirmation${unresolvedHighRisk.length === 1 ? '' : 's'} must be confirmed or intentionally deferred before generation/publication.`,
    )
    addIssue(
      params.map,
      'project-developer-app-glue',
      'error',
      `${unresolvedHighRisk.length} high-risk confirmation${unresolvedHighRisk.length === 1 ? '' : 's'} must be confirmed or intentionally deferred before generation/publication.`,
    )
  }

  const readinessReport = applyReadinessFindingReviews(
    analyzeAgentConsumptionReadiness(effectiveDefinition),
    normalizeReadinessFindingReviews((traceabilityData as any)?.agent_consumption_readiness?.finding_reviews),
  )
  if (readinessReport.summary.blockers > 0) {
    const message = `Agent Consumption Readiness is blocked (score ${readinessReport.score}/100): ${readinessReport.summary.blockers} blocker${readinessReport.summary.blockers === 1 ? '' : 's'}, ${readinessReport.summary.warnings} warning${readinessReport.summary.warnings === 1 ? '' : 's'}.`
    addIssue(
      params.map,
      'project-developer-coverage',
      'error',
      message,
    )
    addIssue(
      params.map,
      'project-developer-app-glue',
      'error',
      message,
    )
  } else if (readinessReport.summary.warnings > 0) {
    const message = `Agent Consumption Readiness needs review (score ${readinessReport.score}/100): ${readinessReport.summary.warnings} warning${readinessReport.summary.warnings === 1 ? '' : 's'}.`
    addIssue(
      params.map,
      'project-developer-coverage',
      'warning',
      message,
    )
    addIssue(
      params.map,
      'project-developer-app-glue',
      'warning',
      message,
    )
  }
}

export function buildProjectIssueIndex(params: {
  project: ProjectDetail | null | undefined
  pmArtifacts: ArtifactRecord[]
  requirements: RequirementsRecord[]
  scenarios: ArtifactRecord[]
  documents: ProjectDocumentRecord[]
  shapes: ShapeRecord[]
  sourceInputContractEvidenceReady?: boolean
}): IssueMap {
  const map: IssueMap = {}
  if (!params.project) return map
  addProductDesignIssues({
    map,
    project: params.project,
    pmArtifacts: params.pmArtifacts,
    requirements: params.requirements,
    scenarios: params.scenarios,
    documents: params.documents,
    shapes: params.shapes,
  })
  addDeveloperIssues({
    map,
    project: params.project,
    pmArtifacts: params.pmArtifacts,
    documents: params.documents,
    requirements: params.requirements,
    scenarios: params.scenarios,
    shapes: params.shapes,
    sourceInputContractEvidenceReady: params.sourceInputContractEvidenceReady,
  })

  const productEntries: AggregateEntry[] = [
    { key: 'project-source-docs', label: 'Source Docs' },
    { key: 'project-product-summary', label: 'Business Summary' },
    { key: 'project-actor-model', label: 'Actor Model' },
    { key: 'project-business-areas', label: 'Business Areas' },
    { key: 'project-permission-intent', label: 'Permission Intent' },
    { key: 'project-requirements-list', label: 'What Matters' },
    { key: 'project-scenarios-list', label: 'Real Situations' },
    { key: 'project-shapes', label: 'Service Design' },
    { key: 'project-non-goals', label: 'Non-Goals' },
    { key: 'project-success-criteria', label: 'Success Criteria' },
  ]
  const developerEntries: AggregateEntry[] = [
    { key: 'project-fronting-express', label: 'Govern API / MCP Express' },
    { key: 'project-developer-handoff', label: 'Locked Product Handoff' },
    { key: 'project-developer-service-formalization', label: 'Service Formalization' },
    { key: 'project-developer-governance-bindings', label: 'Roles & Access' },
    { key: 'project-developer-audit-lineage', label: 'Audit & Lineage' },
    { key: 'project-integration-fronting', label: 'Govern API / MCP' },
    { key: 'project-developer-capability-formalization', label: 'Capability Formalization' },
    { key: 'project-developer-data-contract-formalization', label: 'Data Contract Formalization' },
    { key: 'project-developer-scenario-formalization', label: 'Scenario Coverage Intent' },
    { key: 'project-developer-scenario-execution-semantics', label: 'Scenario Execution Semantics' },
    { key: 'project-developer-generation-settings', label: 'Generation Settings' },
    { key: 'project-developer-verification-expectations', label: 'Evidence & Verification Plan' },
    { key: 'project-developer-coverage', label: 'Coverage Mapping' },
    { key: 'project-developer-app-glue', label: 'Agent & App Glue' },
    { key: 'project-developer-definition', label: 'Developer Definition' },
  ]
  setAggregateIssue(map, 'project-product-design', productEntries)
  setAggregateIssue(map, 'project-developer-design', developerEntries)
  return map
}
