import type {
  ArtifactRecord,
  CoverageStatus,
  DeveloperBaselineData,
  DeveloperCoverageState,
  PmReviewState,
  RequirementsRecord,
  ShapeRecord,
  TraceabilityCoverageItem,
  TraceabilityRecordData,
} from './project-types'
import {
  inferAutomaticCoverageMapping,
  resolveDeveloperDefinitionLinks,
} from './developer-definition'
import { GUIDED_SECTIONS } from './guided/questions'
import { hydrateAnswersFromArtifact } from './guided/mappings'
import { SCENARIO_GUIDED_SECTIONS } from './guided/scenario-questions'
import { hydrateScenarioAnswers } from './guided/scenario-mappings'
import {
  BUSINESS_AREAS_ARTIFACT_TYPE,
  findActorModelArtifact,
  findNonGoalsArtifact,
  findPermissionIntentArtifact,
  findProductSummaryArtifact,
  findProductDesignArtifact,
  findLatestProductDesignRevisionArtifact,
  productDesignSourceHash,
  resolveBusinessAreaLabel,
  findSuccessCriteriaArtifact,
  type ActorModelData,
  type NonGoalsData,
  type PermissionIntentData,
  type ProductDesignRevisionData,
  type ProductSummaryData,
  type SuccessCriteriaData,
} from './product-design'

export const DESIGN_TRACEABILITY_ARTIFACT_TYPE = 'design_traceability'
export const DEVELOPER_BASELINE_ARTIFACT_TYPE = 'developer_baseline'
const INTEGRATION_FRONTING_MAPPING_ARTIFACT_TYPE = 'integration_fronting_capability_mapping'

export function traceabilityArtifactId(projectId: string): string {
  return `${projectId}-design-traceability`
}

export function developerBaselineArtifactId(projectId: string): string {
  return `${projectId}-developer-baseline`
}

export function coverageStatusLabel(status: CoverageStatus): string {
  const labels: Record<CoverageStatus, string> = {
    not_addressed: 'Not Addressed',
    partially_addressed: 'Partially Addressed',
    addressed: 'Addressed',
    deferred: 'Intentionally Deferred',
    not_applicable: 'Not Applicable',
  }
  return labels[status]
}

export function developerStatusLabel(status: DeveloperCoverageState): string {
  const labels: Record<DeveloperCoverageState, string> = {
    not_started: 'Not Started',
    in_progress: 'In Progress',
    ready_for_pm_review: 'Ready for PM Review',
  }
  return labels[status]
}

export function pmReviewStatusLabel(status: PmReviewState): string {
  const labels: Record<PmReviewState, string> = {
    pending: 'Pending Review',
    approved: 'Approved',
    changes_requested: 'Changes Requested',
  }
  return labels[status]
}

function hasMeaningfulValue(value: unknown): boolean {
  if (value == null) return false
  if (typeof value === 'boolean') return value
  if (typeof value === 'string') {
    const normalized = value.trim()
    return normalized.length > 0 && normalized !== 'not_specified'
  }
  if (Array.isArray(value)) return value.length > 0
  if (typeof value === 'object') return Object.keys(value as Record<string, unknown>).length > 0
  return true
}

function summarizeValue(value: unknown): string {
  if (value == null) return ''
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (Array.isArray(value)) return value.map((item) => summarizeValue(item)).filter(Boolean).join(', ')
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function trimmed(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function humanize(value: unknown): string {
  return String(value ?? '')
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

function mergeCoverage(
  current: TraceabilityCoverageItem[],
  existing: TraceabilityCoverageItem[],
): TraceabilityCoverageItem[] {
  const existingById = new Map(existing.map((item) => [item.id, item]))
  return current.map((item) => {
    const prior = existingById.get(item.id)
    const automatic = inferAutomaticCoverageMapping(item)
    if (!prior) {
      return automatic
        ? {
            ...item,
            linked_surfaces: automatic.linked_surfaces,
            mapping_mode: 'automatic',
            mapping_note: automatic.note,
            mapping_target_key: automatic.target_key,
            mapping_target_label: automatic.target_label,
          }
        : {
            ...item,
            mapping_mode: 'manual',
            mapping_note: '',
            mapping_target_key: undefined,
            mapping_target_label: undefined,
          }
    }
    if (automatic) {
      return {
        ...item,
        status: prior.status,
        rationale: prior.rationale,
        linked_surfaces: automatic.linked_surfaces,
        mapping_mode: 'automatic',
        mapping_note: automatic.note,
        mapping_target_key: automatic.target_key,
        mapping_target_label: automatic.target_label,
        operator_resolution: prior.operator_resolution,
      }
    }
    return {
      ...item,
      status: prior.status,
      rationale: prior.rationale,
      linked_surfaces: Array.isArray(prior.linked_surfaces) ? resolveDeveloperDefinitionLinks(prior.linked_surfaces) : [],
      mapping_mode: 'manual',
      mapping_note: '',
      mapping_target_key: undefined,
      mapping_target_label: undefined,
      operator_resolution: prior.operator_resolution,
    }
  })
}

export function hasReviewedCoverageResolution(item: TraceabilityCoverageItem): boolean {
  const resolution = item.operator_resolution
  return !!resolution?.choice_id && !!resolution.applied_at
}

export function findTraceabilityArtifact(pmArtifacts: ArtifactRecord[]): ArtifactRecord | null {
  return (
    pmArtifacts.find((artifact) => artifact.data?.artifact_type === DESIGN_TRACEABILITY_ARTIFACT_TYPE)
    ?? null
  )
}

export function findDeveloperBaselineArtifact(pmArtifacts: ArtifactRecord[]): ArtifactRecord | null {
  return (
    pmArtifacts.find((artifact) => artifact.data?.artifact_type === DEVELOPER_BASELINE_ARTIFACT_TYPE)
    ?? null
  )
}

function scenarioSetHash(scenarios: ArtifactRecord[]): string | null {
  if (scenarios.length === 0) return null
  return scenarios
    .map((scenario) => `${scenario.id}:${scenario.content_hash}`)
    .sort()
    .join('|')
}

export function canonicalScenarioSetHash(value: string | null | undefined): string | null {
  const trimmed = String(value ?? '').trim()
  if (!trimmed) return null
  if (!trimmed.includes('|')) return trimmed
  return trimmed.split('|').map((part) => part.trim()).filter(Boolean).sort().join('|')
}

export function buildDeveloperBaseline(params: {
  requirements: RequirementsRecord | null
  scenarios: ArtifactRecord[]
  primaryScenarioId?: string | null
  shape: ShapeRecord | null
  pmArtifacts?: ArtifactRecord[]
  productRevision?: ProductDesignRevisionData | null
  existing?: DeveloperBaselineData | null
}): DeveloperBaselineData {
  const primaryScenarioId = params.primaryScenarioId
    ?? params.scenarios.find((scenario) => scenario.id === params.existing?.source_inputs.primary_scenario_id)?.id
    ?? params.scenarios[0]?.id
    ?? null

  return {
    artifact_type: DEVELOPER_BASELINE_ARTIFACT_TYPE,
    source_inputs: {
      product_revision_artifact_id:
        params.productRevision?.revision_artifact_id
        ?? params.existing?.source_inputs.product_revision_artifact_id
        ?? null,
      product_revision_number:
        params.productRevision?.revision_number
        ?? params.existing?.source_inputs.product_revision_number
        ?? null,
      product_design_hash:
        params.productRevision?.product_design_hash
        ?? (params.pmArtifacts ? productDesignSourceHash(params.pmArtifacts) : params.existing?.source_inputs.product_design_hash)
        ?? null,
      requirements_id: params.requirements?.id ?? null,
      requirements_hash: params.requirements?.content_hash ?? null,
      scenario_ids: params.scenarios.map((scenario) => scenario.id),
      primary_scenario_id: primaryScenarioId,
      scenario_set_hash: scenarioSetHash(params.scenarios),
      shape_id: params.shape?.id ?? null,
      shape_hash: params.shape?.content_hash ?? null,
    },
    locked_at: params.existing?.locked_at ?? new Date().toISOString(),
    note: params.existing?.note ?? '',
  }
}

export function developerBaselineMatchesCurrentContext(params: {
  baseline: DeveloperBaselineData | null
  requirements: RequirementsRecord | null
  scenarios: ArtifactRecord[]
  shape: ShapeRecord | null
  pmArtifacts?: ArtifactRecord[]
}): boolean {
  const { baseline, requirements, scenarios, shape } = params
  if (!baseline) return false
  const currentProductDesignHash = params.pmArtifacts ? productDesignSourceHash(params.pmArtifacts) : null
  const latestProductRevision = params.pmArtifacts
    ? findLatestProductDesignRevisionArtifact(params.pmArtifacts)?.data as ProductDesignRevisionData | undefined
    : undefined
  const productDesignAligned = !params.pmArtifacts
    || !baseline.source_inputs.product_design_hash
    || (
      baseline.source_inputs.product_design_hash === currentProductDesignHash
      && (
        !baseline.source_inputs.product_revision_artifact_id
        || baseline.source_inputs.product_revision_artifact_id === latestProductRevision?.revision_artifact_id
      )
    )
  return (
    productDesignAligned
    && baseline.source_inputs.requirements_id === (requirements?.id ?? null)
    && baseline.source_inputs.requirements_hash === (requirements?.content_hash ?? null)
    && baseline.source_inputs.shape_id === (shape?.id ?? null)
    && baseline.source_inputs.shape_hash === (shape?.content_hash ?? null)
    && canonicalScenarioSetHash(baseline.source_inputs.scenario_set_hash) === canonicalScenarioSetHash(scenarioSetHash(scenarios))
    && baseline.source_inputs.scenario_ids.length === scenarios.length
    && baseline.source_inputs.scenario_ids.every((id) => scenarios.some((scenario) => scenario.id === id))
    && (baseline.source_inputs.primary_scenario_id == null
      || scenarios.some((scenario) => scenario.id === baseline.source_inputs.primary_scenario_id))
  )
}

export function deriveRequirementsCoverageItems(
  requirements: RequirementsRecord | null,
): TraceabilityCoverageItem[] {
  if (!requirements?.data) return []
  const answers = hydrateAnswersFromArtifact(requirements.data)
  const items: TraceabilityCoverageItem[] = []

  for (const section of GUIDED_SECTIONS) {
    for (const question of section.questions) {
      const value = answers[question.id]
      if (!hasMeaningfulValue(value)) continue
      items.push({
        id: `requirements:${question.id}`,
        source: 'requirements',
        section: section.title,
        label: question.prompt,
        detail: summarizeValue(value),
        status: 'not_addressed',
        rationale: '',
        linked_surfaces: [],
      })
    }
  }

  return items
}

export function deriveProductDesignCoverageItems(
  pmArtifacts: ArtifactRecord[],
  options: { reducedFrontingProductDesign?: boolean } = {},
): TraceabilityCoverageItem[] {
  const items: TraceabilityCoverageItem[] = []
  const summary = findProductSummaryArtifact(pmArtifacts)?.data as ProductSummaryData | undefined
  const actors = findActorModelArtifact(pmArtifacts)?.data as ActorModelData | undefined
  const permissions = findPermissionIntentArtifact(pmArtifacts)?.data as PermissionIntentData | undefined
  const nonGoals = findNonGoalsArtifact(pmArtifacts)?.data as NonGoalsData | undefined
  const successCriteria = findSuccessCriteriaArtifact(pmArtifacts)?.data as SuccessCriteriaData | undefined
  const businessAreasConfigured = !!findProductDesignArtifact(pmArtifacts, BUSINESS_AREAS_ARTIFACT_TYPE)

  if (summary) {
    summary.business_goals.forEach((goal, index) => {
      if (!goal.trim()) return
      items.push({
        id: `product_summary:business_goal:${index}`,
        source: 'product_summary',
        section: 'Business Summary · Business Goals',
        label: humanize(goal),
        detail: 'Business goal the implementation should help achieve.',
        status: 'not_addressed',
        rationale: '',
        linked_surfaces: [],
      })
    })
    summary.supported_question_families.forEach((questionFamily, index) => {
      if (!questionFamily.trim()) return
      items.push({
        id: `product_summary:supported_question_family:${index}`,
        source: 'product_summary',
        section: 'Business Summary · Supported Question Families',
        label: humanize(questionFamily),
        detail: 'Question family the product must support in a governed way.',
        status: 'not_addressed',
        rationale: '',
        linked_surfaces: [],
      })
    })
    if (summary.governed_behavior_summary.trim()) {
      items.push({
        id: 'product_summary:governed_behavior_summary',
        source: 'product_summary',
        section: 'Business Summary · Governed Behavior',
        label: 'Governed Behavior Summary',
        detail: summary.governed_behavior_summary.trim(),
        status: 'not_addressed',
        rationale: '',
        linked_surfaces: [],
      })
    }
    if (summary.approval_posture_summary.trim()) {
      items.push({
        id: 'product_summary:approval_posture_summary',
        source: 'product_summary',
        section: 'Business Summary · Approval Posture',
        label: 'Approval Posture Summary',
        detail: summary.approval_posture_summary.trim(),
        status: 'not_addressed',
        rationale: '',
        linked_surfaces: [],
      })
    }
    summary.multi_step_composition_rules.forEach((rule, index) => {
      if (!rule.trim()) return
      items.push({
        id: `product_summary:multi_step_composition_rule:${index}`,
        source: 'product_summary',
        section: 'Business Summary · Multi-Step Composition Rules',
        label: humanize(rule),
        detail: 'Business rule describing how compound workflows should remain governed.',
        status: 'not_addressed',
        rationale: '',
        linked_surfaces: [],
      })
    })
  }

  if (actors) {
    actors.actors.forEach((actor, index) => {
      const actorId = trimmed(actor.actor_id) || `actor-${index + 1}`
      const actorLabel = trimmed(actor.title) || actorId || `Actor ${index + 1}`
      const summary = trimmed(actor.summary)
      const visibilityExpectations = trimmed(actor.visibility_expectations)
      const actionExpectations = trimmed(actor.action_expectations)
      const approvalExpectations = trimmed(actor.approval_expectations)
      if (summary) {
        items.push({
          id: `actor_model:actor:${actorId || index}:summary`,
          source: 'actor_model',
          section: `${actorLabel} · Actor Summary`,
          label: actorLabel,
          detail: summary,
          status: 'not_addressed',
          rationale: '',
          linked_surfaces: [],
        })
      }
      if (visibilityExpectations) {
        items.push({
          id: `actor_model:actor:${actorId || index}:visibility_expectations`,
          source: 'actor_model',
          section: `${actorLabel} · Visibility Expectations`,
          label: `${actorLabel} visibility`,
          detail: visibilityExpectations,
          status: 'not_addressed',
          rationale: '',
          linked_surfaces: [],
        })
      }
      if (actionExpectations) {
        items.push({
          id: `actor_model:actor:${actorId || index}:action_expectations`,
          source: 'actor_model',
          section: `${actorLabel} · Action Expectations`,
          label: `${actorLabel} actions`,
          detail: actionExpectations,
          status: 'not_addressed',
          rationale: '',
          linked_surfaces: [],
        })
      }
      if (approvalExpectations) {
        items.push({
          id: `actor_model:actor:${actorId || index}:approval_expectations`,
          source: 'actor_model',
          section: `${actorLabel} · Approval Expectations`,
          label: `${actorLabel} approval expectations`,
          detail: approvalExpectations,
          status: 'not_addressed',
          rationale: '',
          linked_surfaces: [],
        })
      }
    })
  }

  if (permissions) {
    permissions.rules.forEach((rule, index) => {
      const actorId = trimmed(rule.actor_id) || trimmed((rule as any).actor_family)
      const businessArea = trimmed(rule.business_area)
      if (!actorId || !businessArea) return
      const businessAreaLabel = businessAreasConfigured
        ? resolveBusinessAreaLabel(businessArea, pmArtifacts)
        : businessArea
      const governedOutcome = trimmed(rule.governed_outcome) || summarizeValue((rule as any).governed_outcomes)
      const governedOutcomeType = trimmed(rule.governed_outcome_type) || 'governed outcome'
      items.push({
        id: `permission_intent:rule:${index}`,
        source: 'permission_intent',
        section: 'Permission Intent',
        label: `${humanize(actorId)} · ${businessAreaLabel}`,
        detail: `${humanize(rule.access_posture)} · ${humanize(governedOutcomeType)}${governedOutcome ? ` · ${governedOutcome}` : ''}`,
        status: 'not_addressed',
        rationale: '',
        linked_surfaces: [],
      })
    })
  }

  if (!options.reducedFrontingProductDesign && nonGoals) {
    nonGoals.entries.forEach((entry, index) => {
      if (!entry.statement.trim()) return
      items.push({
        id: `non_goals:entry:${index}`,
        source: 'non_goals',
        section: 'Non-Goals',
        label: entry.statement.trim(),
        detail: entry.rationale.trim() || 'Product behavior the implementation should not expand into.',
        status: 'not_addressed',
        rationale: '',
        linked_surfaces: [],
      })
    })
  }

  if (!options.reducedFrontingProductDesign && successCriteria) {
    successCriteria.entries.forEach((entry, index) => {
      if (!entry.statement.trim()) return
      items.push({
        id: `success_criteria:entry:${index}`,
        source: 'success_criteria',
        section: 'Success Criteria',
        label: entry.statement.trim(),
        detail: entry.evidence.trim() || entry.review_method.trim() || 'Business-facing success condition that delivery should satisfy.',
        status: 'not_addressed',
        rationale: '',
        linked_surfaces: [],
      })
    })
  }

  return items
}

export function deriveScenarioCoverageItems(
  scenarios: ArtifactRecord[],
): TraceabilityCoverageItem[] {
  const items: TraceabilityCoverageItem[] = []

  scenarios.forEach((scenario) => {
    if (!scenario?.data) return
    const answers = hydrateScenarioAnswers(scenario.data)
    const scenarioTitle = scenario.title || 'Scenario'

    for (const section of SCENARIO_GUIDED_SECTIONS) {
      for (const question of section.questions) {
        if (
          question.id === 'name' ||
          question.id === 'scenario-title' ||
          question.id === 'scenario-category' ||
          question.id === 'scenario-narrative-text' ||
          question.prompt === 'Name this scenario'
        ) continue
        const value = answers[question.id]
        if (!hasMeaningfulValue(value)) continue
        items.push({
          id: `scenario:${scenario.id}:${question.id}`,
          source: 'scenario',
          section: `${scenarioTitle} · ${section.title}`,
          label: question.prompt,
          detail: summarizeValue(value),
          status: 'not_addressed',
          rationale: '',
          linked_surfaces: [],
        })
      }
    }

    const rawScenario = scenario.data?.scenario ?? {}
    const expectedBehavior = Array.isArray(rawScenario.expected_behavior) ? rawScenario.expected_behavior : []
    expectedBehavior.forEach((value: string) => {
      items.push({
        id: `scenario:${scenario.id}:expected_behavior:${value}`,
        source: 'scenario',
        section: `${scenarioTitle} · Expected Behavior`,
        label: humanize(value),
        detail: 'Scenario outcome that the implementation must preserve.',
        status: 'not_addressed',
        rationale: '',
        linked_surfaces: [],
      })
    })

    const expectedSupport = Array.isArray(rawScenario.expected_anip_support) ? rawScenario.expected_anip_support : []
    expectedSupport.forEach((value: string) => {
      items.push({
        id: `scenario:${scenario.id}:expected_anip_support:${value}`,
        source: 'scenario',
        section: `${scenarioTitle} · Expected ANIP Support`,
        label: humanize(value),
        detail: 'Protocol-visible support the implementation is expected to expose.',
        status: 'not_addressed',
        rationale: '',
        linked_surfaces: [],
      })
    })
  })

  return items
}

export function deriveShapeCoverageItems(
  shape: ShapeRecord | null,
  options: { integrationFrontingServiceIds?: Set<string> } = {},
): TraceabilityCoverageItem[] {
  if (!shape?.data) return []
  const shapeData = (shape.data.shape ?? shape.data) as Record<string, any>
  const items: TraceabilityCoverageItem[] = []

  const services = Array.isArray(shapeData.services) ? shapeData.services : []
  services.forEach((service: Record<string, any>) => {
    const serviceId = String(service.id ?? service.name ?? '').trim()
    const sourceCapabilities = Array.isArray(service.capabilities)
      ? service.capabilities.map((value: unknown) => String(value).trim()).filter(Boolean)
      : []
    const sourceConcepts = Array.isArray(service.owns_concepts)
      ? service.owns_concepts.map((value: unknown) => String(value).trim()).filter(Boolean)
      : []
    if (
      options.integrationFrontingServiceIds?.size
      && !options.integrationFrontingServiceIds.has(serviceId)
      && sourceCapabilities.length === 0
      && sourceConcepts.length === 0
    ) {
      return
    }
    items.push({
      id: `shape:service:${serviceId}`,
      source: 'shape',
      section: 'Services',
      label: String(service.name ?? service.id ?? 'Service'),
      detail: sourceCapabilities.length > 0
        ? `Owns capabilities: ${sourceCapabilities.map((value: string) => humanize(value)).join(', ')}`
        : String(service.role ?? 'Service boundary in the design draft.'),
      status: 'not_addressed',
      rationale: '',
      linked_surfaces: [],
    })
  })

  const coordination = Array.isArray(shapeData.coordination) ? shapeData.coordination : []
  coordination.forEach((edge: Record<string, any>) => {
    items.push({
      id: `shape:coordination:${String(edge.from ?? '')}:${String(edge.to ?? '')}:${String(edge.relationship ?? '')}`,
      source: 'shape',
      section: 'Coordination',
      label: `${humanize(String(edge.from ?? 'Source'))} -> ${humanize(String(edge.to ?? 'Target'))}`,
      detail: edge.description
        ? String(edge.description)
        : `${humanize(String(edge.relationship ?? 'coordination'))} between service boundaries.`,
      status: 'not_addressed',
      rationale: '',
      linked_surfaces: [],
    })
  })

  const concepts = Array.isArray(shapeData.domain_concepts) ? shapeData.domain_concepts : []
  concepts.forEach((concept: Record<string, any>) => {
    items.push({
      id: `shape:concept:${String(concept.id ?? concept.name ?? '')}`,
      source: 'shape',
      section: 'Domain Concepts',
      label: String(concept.name ?? concept.id ?? 'Concept'),
      detail: String(concept.meaning ?? concept.risk_note ?? 'Business concept that the service design protects.'),
      status: 'not_addressed',
      rationale: '',
      linked_surfaces: [],
    })
  })

  return items
}

export function deriveIntegrationFrontingCoverageItems(pmArtifacts: ArtifactRecord[]): TraceabilityCoverageItem[] {
  return pmArtifacts
    .filter((artifact) => artifact.data?.artifact_type === INTEGRATION_FRONTING_MAPPING_ARTIFACT_TYPE)
    .map((artifact): TraceabilityCoverageItem => {
      const data = artifact.data ?? {}
      const capabilityId = String(data.capability_id ?? artifact.title ?? artifact.id)
      const backendBindings = Array.isArray(data.backend_bindings)
        ? data.backend_bindings.map((binding) => {
          const item = typeof binding === 'object' && binding ? binding as Record<string, unknown> : {}
          return {
            backend_kind: String(item.backend_kind ?? 'integration'),
            connection_ref: String(item.connection_ref ?? ''),
            raw_operation_refs: Array.isArray(item.raw_operation_refs)
              ? item.raw_operation_refs.map((value) => String(value)).filter(Boolean)
              : [],
          }
        }).filter((binding) => binding.connection_ref || binding.raw_operation_refs.length > 0)
        : []
      const legacyRawOperationRefs = Array.isArray(data.raw_operation_refs)
        ? data.raw_operation_refs.map((value) => String(value)).filter(Boolean)
        : []
      const legacyConnectionRef = String(data.connection_ref ?? '')
      const legacyBackendKind = String(data.backend_kind ?? 'integration')
      const bindings = backendBindings.length > 0
        ? backendBindings
        : [{ backend_kind: legacyBackendKind, connection_ref: legacyConnectionRef, raw_operation_refs: legacyRawOperationRefs }]
      const missingBinding = bindings.some((binding) => !binding.connection_ref || binding.raw_operation_refs.length === 0)
      return {
        id: `integration_fronting:${artifact.id}`,
        source: 'integration_fronting',
        section: 'Govern API / MCP',
        label: capabilityId,
        detail: bindings
          .map((binding) => `${binding.backend_kind}${binding.connection_ref ? ` via ${binding.connection_ref}` : ''}${binding.raw_operation_refs.length ? `; operations: ${binding.raw_operation_refs.join(', ')}` : ''}`)
          .join(' | '),
        status: !missingBinding ? 'addressed' : 'partially_addressed',
        rationale: 'Accepted governed integration-fronting mapping compiled into the Developer Definition.',
        linked_surfaces: [
          'capability_contracts',
          'authority_and_approval',
          'backend_bindings',
          'audit_and_lineage',
          'generation_and_extensions',
        ],
        mapping_mode: 'automatic',
        mapping_note: 'Accepted integration-fronting mappings are the curated governed surface in front of raw backend operations.',
        mapping_target_key: `developer_definition.integration_fronting:${capabilityId}`,
        mapping_target_label: 'Developer Design > Govern API / MCP > Accepted Governed Mapping',
      }
    })
}

export function buildTraceabilityRecord(params: {
  pmArtifacts?: ArtifactRecord[]
  requirements: RequirementsRecord | null
  scenarios: ArtifactRecord[]
  primaryScenarioId?: string | null
  shape: ShapeRecord | null
  baselineLockedAt?: string | null
  existing?: TraceabilityRecordData | null
  reducedFrontingProductDesign?: boolean
}): TraceabilityRecordData {
  const productItems = deriveProductDesignCoverageItems(params.pmArtifacts ?? [], {
    reducedFrontingProductDesign: params.reducedFrontingProductDesign,
  })
  const requirementsItems = deriveRequirementsCoverageItems(params.requirements)
  const scenarioItems = deriveScenarioCoverageItems(params.scenarios)
  const integrationFrontingItems = deriveIntegrationFrontingCoverageItems(params.pmArtifacts ?? [])
  const integrationFrontingServiceIds = new Set(
    (params.pmArtifacts ?? [])
      .filter((artifact) => artifact.data?.artifact_type === INTEGRATION_FRONTING_MAPPING_ARTIFACT_TYPE)
      .map((artifact) => String(artifact.data?.service_id ?? '').trim())
      .filter(Boolean),
  )
  const shapeItems = deriveShapeCoverageItems(params.shape, { integrationFrontingServiceIds })
  const currentCoverage = [...productItems, ...requirementsItems, ...scenarioItems, ...shapeItems, ...integrationFrontingItems]
  const existing = params.existing ?? null
  const primaryScenarioId = params.primaryScenarioId ?? params.scenarios[0]?.id ?? null

  return {
    artifact_type: DESIGN_TRACEABILITY_ARTIFACT_TYPE,
    source_inputs: {
      requirements_id: params.requirements?.id ?? null,
      scenario_id: primaryScenarioId,
      scenario_ids: params.scenarios.map((scenario) => scenario.id),
      shape_id: params.shape?.id ?? null,
      baseline_locked_at: params.baselineLockedAt ?? null,
    },
    developer_status: existing?.developer_status ?? 'not_started',
    developer_note: existing?.developer_note ?? '',
    developer_marked_at: existing?.developer_marked_at ?? null,
    pm_review_status: existing?.pm_review_status ?? 'pending',
    pm_review_note: existing?.pm_review_note ?? '',
    pm_reviewed_at: existing?.pm_reviewed_at ?? null,
    pm_review_contract_signature: existing?.pm_review_contract_signature ?? null,
    pm_review_generation_signature: existing?.pm_review_generation_signature ?? null,
    pm_review_generation_artifact_id: existing?.pm_review_generation_artifact_id ?? null,
    pm_review_definition_revision_artifact_id: existing?.pm_review_definition_revision_artifact_id ?? null,
    pm_review_definition_revision_number: existing?.pm_review_definition_revision_number ?? null,
    pm_review_product_revision_artifact_id: existing?.pm_review_product_revision_artifact_id ?? null,
    pm_review_product_revision_number: existing?.pm_review_product_revision_number ?? null,
    pm_review_evaluation_signature: existing?.pm_review_evaluation_signature ?? null,
    pm_review_evaluation_id: existing?.pm_review_evaluation_id ?? null,
    pm_review_observed_service_signature: existing?.pm_review_observed_service_signature ?? null,
    pm_review_observed_service_artifact_id: existing?.pm_review_observed_service_artifact_id ?? null,
    coverage: mergeCoverage(currentCoverage, existing?.coverage ?? []),
    high_risk_confirmations: existing?.high_risk_confirmations,
    agent_consumption_readiness: existing?.agent_consumption_readiness,
    agent_consumability_reviews: existing?.agent_consumability_reviews,
  }
}

export function summarizeCoverage(coverage: TraceabilityCoverageItem[]): {
  total: number
  addressed: number
  partial: number
  missing: number
  deferred: number
} {
  return coverage.reduce(
    (acc, item) => {
      acc.total += 1
      if (item.status === 'addressed') acc.addressed += 1
      else if (item.status === 'partially_addressed') acc.partial += 1
      else if (item.status === 'deferred') acc.deferred += 1
      else if (item.status === 'not_addressed') acc.missing += 1
      return acc
    },
    { total: 0, addressed: 0, partial: 0, missing: 0, deferred: 0 },
  )
}
