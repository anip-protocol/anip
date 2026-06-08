import {
  buildProductDesignSufficiencyCards,
  findPermissionIntentArtifact,
  type PermissionIntentData,
} from './product-design'
import {
  buildDeveloperDefinitionSufficiencyCards,
  findInferredCompositionAmbiguities,
  findDeveloperDefinitionArtifact,
  shapeDeclaresSourceCapabilityInventory,
} from './developer-definition'
import {
  findDeveloperBaselineArtifact,
  findTraceabilityArtifact,
} from './traceability'
import type {
  ArtifactRecord,
  DeveloperBaselineData,
  DeveloperDefinitionData,
  HighRiskConfirmationItem,
  HighRiskConfirmationReport,
  HighRiskConfirmationReview,
  ProjectDetail,
  ProjectDocumentRecord,
  RequirementsRecord,
  ShapeRecord,
} from './project-types'

export const HIGH_RISK_CONFIRMATIONS_ARTIFACT_TYPE = 'high_risk_confirmations'

export function findHighRiskConfirmationArtifact(
  artifacts: ArtifactRecord[],
): ArtifactRecord | null {
  return artifacts.find((artifact) => artifact.data?.artifact_type === HIGH_RISK_CONFIRMATIONS_ARTIFACT_TYPE) ?? null
}

export function highRiskConfirmationReportFromArtifacts(
  artifacts: ArtifactRecord[],
): HighRiskConfirmationReport | null {
  const traceability = findTraceabilityArtifact(artifacts)
  const traceabilityReport = traceability?.data?.high_risk_confirmations as HighRiskConfirmationReport | undefined
  if (traceabilityReport?.artifact_type === HIGH_RISK_CONFIRMATIONS_ARTIFACT_TYPE) return traceabilityReport
  const artifactReport = findHighRiskConfirmationArtifact(artifacts)?.data as HighRiskConfirmationReport | undefined
  return artifactReport?.artifact_type === HIGH_RISK_CONFIRMATIONS_ARTIFACT_TYPE ? artifactReport : null
}

export function normalizeHighRiskConfirmationReviews(
  value: unknown,
): Record<string, HighRiskConfirmationReview> {
  if (!value || typeof value !== 'object') return {}
  const entries = Object.entries(value as Record<string, unknown>).filter(([, item]) =>
    item
    && typeof item === 'object'
    && typeof (item as Record<string, unknown>).id === 'string'
    && (
      (item as Record<string, unknown>).status === 'confirmed'
      || (item as Record<string, unknown>).status === 'deferred'
    )
    && typeof (item as Record<string, unknown>).note === 'string'
    && typeof (item as Record<string, unknown>).reviewed_at === 'string',
  ) as Array<[string, HighRiskConfirmationReview]>
  return Object.fromEntries(entries)
}

export function buildHighRiskConfirmationReport(params: {
  project: ProjectDetail
  pmArtifacts: ArtifactRecord[]
  documents: ProjectDocumentRecord[]
  requirements: RequirementsRecord[]
  scenarios: ArtifactRecord[]
  shapes: ShapeRecord[]
  existing?: HighRiskConfirmationReport | null
  sourceInputContractEvidenceReady?: boolean
}): HighRiskConfirmationReport {
  const items = dedupeItems([
    ...productClarificationItems(params),
    ...developerClarificationItems(params),
    ...capabilityIdentityItems(params),
    ...serviceCapabilityCoverageItems(params),
    ...compositionAmbiguityItems(params),
    ...permissionMappingItems(params),
    ...readinessReviewItems(params),
  ])
  const activeItemIds = new Set(items.map((item) => item.id))
  const reviews = Object.fromEntries(
    Object.entries(normalizeHighRiskConfirmationReviews(params.existing?.reviews))
      .filter(([id]) => activeItemIds.has(id)),
  )
  const confirmed = Object.values(reviews).filter((review) => review.status === 'confirmed').length
  const deferred = Object.values(reviews).filter((review) => review.status === 'deferred').length
  const unresolved = items.filter((item) => !reviews[item.id]).length
  return {
    artifact_type: HIGH_RISK_CONFIRMATIONS_ARTIFACT_TYPE,
    generated_at: new Date().toISOString(),
    summary: {
      total: items.length,
      unresolved,
      confirmed,
      deferred,
      blockers: items.filter((item) => item.severity === 'blocker' && !reviews[item.id]).length,
      warnings: items.filter((item) => item.severity === 'warning' && !reviews[item.id]).length,
    },
    items,
    reviews,
  }
}

export function unresolvedHighRiskConfirmationItems(
  report: HighRiskConfirmationReport | null | undefined,
): HighRiskConfirmationItem[] {
  if (!report) return []
  const reviews = normalizeHighRiskConfirmationReviews(report.reviews)
  return report.items.filter((item) => !reviews[item.id])
}

function productClarificationItems(params: {
  project: ProjectDetail
  pmArtifacts: ArtifactRecord[]
  documents: ProjectDocumentRecord[]
  requirements: RequirementsRecord[]
  scenarios: ArtifactRecord[]
}): HighRiskConfirmationItem[] {
  return buildProductDesignSufficiencyCards(params.project.id, params.pmArtifacts, {
    documents_count: params.documents.length,
    requirements_count: params.requirements.length,
    scenarios_count: params.scenarios.length,
  })
    .filter((card) => card.status === 'needs_clarification' && card.questions.length > 0)
    .map((card) => ({
      id: `product-clarification:${card.key}`,
      category: 'clarification',
      severity: 'blocker',
      title: `${card.title} needs confirmation`,
      detail: card.questions[0] ?? `${card.title} has unresolved PM ambiguity.`,
      recommendation: 'Answer or intentionally defer this before locking Product Design or generating from it.',
      source: 'product_design',
      target_route: card.path,
      related_ids: [card.key],
    }))
}

function developerClarificationItems(params: {
  project: ProjectDetail
  pmArtifacts: ArtifactRecord[]
  requirements: RequirementsRecord[]
  scenarios: ArtifactRecord[]
  shapes: ShapeRecord[]
  sourceInputContractEvidenceReady?: boolean
}): HighRiskConfirmationItem[] {
  const baseline = findDeveloperBaselineArtifact(params.pmArtifacts)?.data as DeveloperBaselineData | undefined
  const definition = findDeveloperDefinitionArtifact(params.pmArtifacts)?.data as DeveloperDefinitionData | undefined
  const requirements =
    params.requirements.find((item) => item.id === baseline?.source_inputs.requirements_id)
    ?? params.requirements.find((item) => item.role === 'primary')
    ?? params.requirements[0]
    ?? null
  const scenarios = (baseline?.source_inputs.scenario_ids ?? [])
    .map((id) => params.scenarios.find((item) => item.id === id) ?? null)
    .filter((item): item is ArtifactRecord => item != null)
  const shape = params.shapes.find((item) => item.id === baseline?.source_inputs.shape_id) ?? null
  return buildDeveloperDefinitionSufficiencyCards({
    projectId: params.project.id,
    baseline: baseline ?? null,
    definition: definition ?? null,
    definitionAligned: Boolean(definition),
    requirements,
    scenarios: scenarios.length ? scenarios : params.scenarios,
    shape,
    pmArtifacts: params.pmArtifacts,
    reducedFrontingProject: params.project.project_type === 'governed_service_project',
    sourceInputContractEvidenceReady: params.sourceInputContractEvidenceReady,
  })
    .filter((card) => card.status === 'needs_clarification' && card.questions.length > 0)
    .map((card) => ({
      id: `developer-clarification:${card.key}`,
      category: 'clarification',
      severity: 'blocker',
      title: `${card.title} needs confirmation`,
      detail: card.questions[0] ?? `${card.title} has unresolved Developer Design ambiguity.`,
      recommendation: 'Answer or intentionally defer this before saving, publishing, or generating from Developer Definition.',
      source: 'developer_design',
      target_route: card.path,
      related_ids: [card.key],
    }))
}

function capabilityIdentityItems(params: {
  project: ProjectDetail
  pmArtifacts: ArtifactRecord[]
  shapes: ShapeRecord[]
}): HighRiskConfirmationItem[] {
  const definition = findDeveloperDefinitionArtifact(params.pmArtifacts)?.data as DeveloperDefinitionData | undefined
  const frontingMappings = definition?.integration_fronting?.project_type === 'governed_service_project'
    ? definition.integration_fronting.capability_mappings ?? []
    : []
  const definitionCapabilities = definition?.capability_formalizations ?? []
  const capabilityOwnership = frontingMappings.length > 0 || definitionCapabilities.length > 0
    ? []
    : shapeCapabilityOwnership(params.shapes)
  for (const capability of definitionCapabilities) {
    const capabilityId = text(capability.capability_id)
    if (!capabilityId) continue
    capabilityOwnership.push({
      capability_id: capabilityId,
      service_id: text(capability.service_id),
    })
  }
  const uniqueOwnership = uniqueCapabilityOwnership(capabilityOwnership)
  const capabilityIds = uniqueOwnership.map((item) => item.capability_id).filter(Boolean)
  if (capabilityIds.length === 0) return []
  const duplicateIds = capabilitiesWithConflictingOwners(uniqueOwnership)
  const weakIds = capabilityIds.filter((id) => !id.includes('.') || id.startsWith('answer_') || id.startsWith('prepare_') || id.startsWith('explain_'))
  const sourceDeclaredInventory = params.shapes.some((shape) => shapeDeclaresSourceCapabilityInventory(shape))
  if (sourceDeclaredInventory && weakIds.length === 0 && duplicateIds.length === 0 && uniqueOwnership.every((item) => item.service_id)) {
    return []
  }
  const items: HighRiskConfirmationItem[] = [
    {
      id: 'capability-identity:canonical-ids',
      category: 'capability_identity',
      severity: weakIds.length || duplicateIds.length ? 'blocker' : 'warning',
      title: 'Confirm canonical capability IDs',
      detail: `${capabilityIds.length} capability id${capabilityIds.length === 1 ? '' : 's'} will become durable contract identity.`
        + (weakIds.length ? ` Review weak or paraphrased ids: ${weakIds.slice(0, 8).join(', ')}.` : '')
        + (duplicateIds.length ? ` Duplicate ids detected: ${duplicateIds.slice(0, 8).join(', ')}.` : ''),
      recommendation: 'Confirm these IDs are canonical, or edit Developer Capability Formalization before lock/publish/generate.',
      source: 'developer_design',
      target_route: `/design/projects/${params.project.id}/developer/capabilities`,
      related_ids: capabilityIds.slice(0, 20),
    },
    {
      id: 'capability-identity:service-ownership',
      category: 'service_ownership',
      severity: uniqueOwnership.some((item) => !item.service_id) ? 'blocker' : 'warning',
      title: 'Confirm service ownership for capabilities',
      detail: `${uniqueOwnership.length} capability ownership binding${uniqueOwnership.length === 1 ? '' : 's'} will drive generated service boundaries.`
        + (uniqueOwnership.some((item) => !item.service_id) ? ' One or more capabilities does not have a service owner.' : ''),
      recommendation: 'Confirm the service owner for each canonical capability, or intentionally defer if the app layer owns the ambiguity.',
      source: 'developer_design',
      target_route: `/design/projects/${params.project.id}/developer/services`,
      related_ids: uniqueOwnership.map((item) => `${item.service_id || 'unassigned'}:${item.capability_id}`).slice(0, 20),
    },
  ]
  return items
}

function permissionMappingItems(params: { project: ProjectDetail; pmArtifacts: ArtifactRecord[] }): HighRiskConfirmationItem[] {
  const permissions = findPermissionIntentArtifact(params.pmArtifacts)?.data as PermissionIntentData | undefined
  const mappedRules = (permissions?.rules ?? []).filter((rule) =>
    text(rule.notes).includes('Studio mapped assistant'),
  )
  if (mappedRules.length === 0) return []
  return [{
    id: 'permission-mapping:assistant-reference-map',
    category: 'permission_mapping',
    severity: 'blocker',
    title: 'Confirm mapped permission references',
    detail: `${mappedRules.length} Permission Intent rule${mappedRules.length === 1 ? '' : 's'} were mapped from assistant wording to existing actor or business-area IDs.`,
    recommendation: 'Confirm these mappings are correct, or edit Permission Intent so policy does not rely on a guessed reference.',
    source: 'assistant',
    target_route: `/design/projects/${params.project.id}/permission-intent`,
    related_ids: mappedRules.map((rule) => `${rule.actor_id}:${rule.business_area}`).slice(0, 12),
}]
}

function serviceCapabilityCoverageItems(params: {
  project: ProjectDetail
  shapes: ShapeRecord[]
  pmArtifacts: ArtifactRecord[]
}): HighRiskConfirmationItem[] {
  const definition = findDeveloperDefinitionArtifact(params.pmArtifacts)?.data as DeveloperDefinitionData | undefined
  if (
    definition?.integration_fronting?.project_type === 'governed_service_project'
    && (definition.integration_fronting.capability_mappings ?? []).length > 0
  ) {
    return []
  }
  const knownDefinitionServices = new Map(
    (definition?.service_topology_bindings ?? []).map((service) => [service.service_id, service] as const),
  )
  const uncovered = shapeServices(params.shapes).filter((service) => {
    const definitionService = knownDefinitionServices.get(service.service_id)
    const formalizedCapabilities = definitionService?.formalized_capability_ids ?? []
    return service.has_declared_responsibility && service.source_capabilities.length === 0 && formalizedCapabilities.length === 0
  })
  if (uncovered.length === 0) return []
  return [{
    id: 'service-ownership:services-without-capabilities',
    category: 'service_ownership',
    severity: 'blocker',
    title: 'Confirm services without canonical capabilities',
    detail: `${uncovered.length} service ${uncovered.length === 1 ? 'boundary has' : 'boundaries have'} responsibilities but no canonical capability IDs: ${uncovered.map((service) => service.service_id).slice(0, 8).join(', ')}.`,
    recommendation: 'Add canonical capability IDs for these services, merge the service boundary away, or intentionally defer the boundary as app/service glue before generation or publication.',
    source: 'developer_design',
    target_route: `/design/projects/${params.project.id}/developer/services`,
    related_ids: uncovered.map((service) => service.service_id),
  }]
}

function compositionAmbiguityItems(params: {
  project: ProjectDetail
  pmArtifacts: ArtifactRecord[]
  shapes: ShapeRecord[]
}): HighRiskConfirmationItem[] {
  if (params.shapes.some((shape) => shapeDeclaresSourceCapabilityInventory(shape))) {
    return []
  }
  const definition = findDeveloperDefinitionArtifact(params.pmArtifacts)?.data as DeveloperDefinitionData | undefined
  const ambiguities = findInferredCompositionAmbiguities({
    definition,
    pmArtifacts: params.pmArtifacts,
  })
  return ambiguities.map((ambiguity) => ({
    id: ambiguity.id,
    category: 'composition_ambiguity',
    severity: 'blocker',
    title: 'Resolve ambiguous composed capability inference',
    detail: `Studio found multiple plausible source capabilities for ${ambiguity.sink_capability_id}: ${ambiguity.top_candidates.map((candidate) => `${candidate.capability_id} (${candidate.score})`).join(', ')}.`,
    recommendation: 'Choose the source capability explicitly, define scenario orchestration steps, mark the behavior as app-owned glue, or defer it. Studio will not silently generate this composed capability.',
    source: 'developer_design',
    target_route: `/design/projects/${params.project.id}/developer/capability-formalization#${encodeURIComponent(ambiguity.sink_capability_id)}`,
    related_ids: [ambiguity.sink_capability_id, ...ambiguity.top_candidates.map((candidate) => candidate.capability_id)].slice(0, 12),
  }))
}

function readinessReviewItems(params: { project: ProjectDetail; pmArtifacts: ArtifactRecord[] }): HighRiskConfirmationItem[] {
  const traceability = findTraceabilityArtifact(params.pmArtifacts)?.data as { agent_consumption_readiness?: Record<string, any> } | undefined
  const readiness = traceability?.agent_consumption_readiness
  const reviews = readiness?.finding_reviews && typeof readiness.finding_reviews === 'object'
    ? Object.values(readiness.finding_reviews as Record<string, Record<string, unknown>>)
    : []
  const automated = reviews.filter((review) => review.review_method === 'automation_harness')
  const findings = Array.isArray(readiness?.findings) ? readiness.findings as Array<Record<string, unknown>> : []
  const unreviewedImportant = findings.filter((finding) =>
    (finding.severity === 'blocker' || finding.category === 'unsupported_effect' || finding.category === 'app_glue' || finding.category === 'derived_target')
    && !reviews.some((review) => review.id === finding.id),
  )
  const items: HighRiskConfirmationItem[] = []
  if (automated.length > 0) {
    items.push({
      id: 'agent-readiness:automation-harness-reviews',
      category: 'agent_readiness',
      severity: 'blocker',
      title: 'Confirm automated readiness classifications',
      detail: `${automated.length} readiness finding${automated.length === 1 ? '' : 's'} were classified by an automation harness, not by PM/dev review.`,
      recommendation: 'Review and save these decisions manually before treating the package as ready.',
      source: 'readiness',
      target_route: `/design/projects/${params.project.id}/developer/coverage`,
      related_ids: automated.map((review) => text(review.id)).filter(Boolean).slice(0, 12),
    })
  }
  if (unreviewedImportant.length > 0) {
    items.push({
      id: 'agent-readiness:unreviewed-high-impact-findings',
      category: 'agent_readiness',
      severity: 'blocker',
      title: 'Review high-impact agent readiness findings',
      detail: `${unreviewedImportant.length} readiness finding${unreviewedImportant.length === 1 ? '' : 's'} still need an explicit decision.`,
      recommendation: 'Classify each as contract behavior, app glue, acceptable warning, or follow-up before publication/generation.',
      source: 'readiness',
      target_route: `/design/projects/${params.project.id}/developer/coverage`,
      related_ids: unreviewedImportant.map((finding) => text(finding.id)).filter(Boolean).slice(0, 12),
    })
  }
  return items
}

function shapeServices(shapes: ShapeRecord[]): Array<{
  service_id: string
  source_capabilities: string[]
  has_declared_responsibility: boolean
}> {
  const result: Array<{
    service_id: string
    source_capabilities: string[]
    has_declared_responsibility: boolean
  }> = []
  for (const shape of shapes) {
    const data = (shape.data?.shape ?? shape.data) as Record<string, any> | undefined
    const services = Array.isArray(data?.services) ? data.services : []
    for (const service of services) {
      const serviceId = text(service?.id ?? service?.name)
      if (!serviceId) continue
      const capabilities = Array.isArray(service?.capabilities)
        ? service.capabilities.map((capability: unknown) => text(capability)).filter(Boolean)
        : []
      const responsibilities = Array.isArray(service?.responsibilities)
        ? service.responsibilities.map((responsibility: unknown) => text(responsibility)).filter(Boolean)
        : []
      result.push({
        service_id: serviceId,
        source_capabilities: capabilities,
        has_declared_responsibility: Boolean(text(service?.role) || responsibilities.length > 0),
      })
    }
  }
  return result
}

function shapeCapabilityOwnership(shapes: ShapeRecord[]): Array<{ capability_id: string; service_id: string }> {
  const result: Array<{ capability_id: string; service_id: string }> = []
  for (const shape of shapes) {
    const data = (shape.data?.shape ?? shape.data) as Record<string, any> | undefined
    const services = Array.isArray(data?.services) ? data.services : []
    for (const service of services) {
      const serviceId = text(service?.id ?? service?.name)
      const capabilities = Array.isArray(service?.capabilities) ? service.capabilities : []
      for (const capability of capabilities) {
        const capabilityId = text(capability)
        if (capabilityId) result.push({ capability_id: capabilityId, service_id: serviceId })
      }
    }
  }
  return result
}

function uniqueCapabilityOwnership(
  values: Array<{ capability_id: string; service_id: string }>,
): Array<{ capability_id: string; service_id: string }> {
  const seen = new Set<string>()
  return values.filter((value) => {
    const key = `${value.capability_id}:${value.service_id}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function capabilitiesWithConflictingOwners(
  values: Array<{ capability_id: string; service_id: string }>,
): string[] {
  const ownersByCapability = new Map<string, Set<string>>()
  for (const value of values) {
    const owners = ownersByCapability.get(value.capability_id) ?? new Set<string>()
    owners.add(value.service_id || 'unassigned')
    ownersByCapability.set(value.capability_id, owners)
  }
  return [...ownersByCapability.entries()]
    .filter(([, owners]) => owners.size > 1)
    .map(([capabilityId]) => capabilityId)
}

function dedupeItems(items: HighRiskConfirmationItem[]): HighRiskConfirmationItem[] {
  const seen = new Set<string>()
  return items.filter((item) => {
    if (seen.has(item.id)) return false
    seen.add(item.id)
    return true
  })
}

function text(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}
