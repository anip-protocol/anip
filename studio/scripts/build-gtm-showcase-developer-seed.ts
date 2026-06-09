import { mkdir, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { createHash, webcrypto } from 'node:crypto'

import {
  getProject,
  listPmArtifacts,
  listProjectDocuments,
  listRequirements,
  listScenarios,
  listShapes,
} from '../src/design/project-api'
import type {
  ArtifactRecord,
  DeveloperCompiledContractIdentity,
  DeveloperDefinitionData,
  DeveloperDefinitionRevisionData,
  ProjectDetail,
  RequirementsRecord,
  ShapeRecord,
  TraceabilityCoverageItem,
  TraceabilityRecordData,
} from '../src/design/project-types'
import {
  buildProductDesignRevision,
  productDesignRevisionArtifactId,
  type ProductDesignRevisionData,
} from '../src/design/product-design'
import {
  buildDeveloperBaseline,
  developerBaselineArtifactId,
  traceabilityArtifactId,
  buildTraceabilityRecord,
} from '../src/design/traceability'
import {
  analyzeAgentConsumptionReadiness,
  applyReadinessFindingReviews,
  type AgentConsumptionReadinessFinding,
  type AgentConsumptionReadinessFindingReview,
} from '../src/design/agent-consumption-readiness'
import {
  buildDeveloperDefinitionContract,
  buildDeveloperDefinitionData,
  developerDefinitionArtifactId,
  developerDefinitionRevisionArtifactId,
  developerDefinitionTargetStatus,
  stableStringify,
  validateDeveloperDefinitionRequiredFields,
} from '../src/design/developer-definition'
import { buildHighRiskConfirmationReport } from '../src/design/high-risk-confirmations'
import {
  mergeSemanticInterpretationRule,
  semanticInterpretationRuleForFinding,
} from '../src/design/semantic-interpretation-rules'
import {
  buildAgentConsumabilityMetadata,
  type AgentConsumabilityCapabilityReview,
} from '../src/design/agent-consumability'

const repoRoot = resolve(new URL('../..', import.meta.url).pathname)
const apiBase = process.env.STUDIO_API_BASE || 'http://127.0.0.1:8100'
const projectId = process.env.GTM_SHOWCASE_PROJECT_ID || 'gtm-pipeline-q2-review'
const outputFile = process.env.GTM_SHOWCASE_DEVELOPER_SEED_OUTPUT
  || resolve(repoRoot, 'studio/server/seed_data/gtm_developer_artifacts.json')

if (!globalThis.crypto) {
  Object.defineProperty(globalThis, 'crypto', { value: webcrypto })
}

const nativeFetch = globalThis.fetch.bind(globalThis)
globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) => {
  if (typeof input === 'string' && input.startsWith('/')) {
    return nativeFetch(`${apiBase}${input}`, init)
  }
  return nativeFetch(input, init)
}) as typeof globalThis.fetch

interface ProjectState {
  project: ProjectDetail
  pmArtifacts: ArtifactRecord[]
  documents: Awaited<ReturnType<typeof listProjectDocuments>>
  requirements: RequirementsRecord[]
  scenarios: ArtifactRecord[]
  shapes: ShapeRecord[]
}

interface SeedArtifact {
  id: string
  title: string
  data: Record<string, any>
}

function log(message: string) {
  process.stdout.write(`[gtm-seed] ${message}\n`)
}

async function loadState(projectRef: string): Promise<ProjectState> {
  const [project, pmArtifacts, documents, requirements, scenarios, shapes] = await Promise.all([
    getProject(projectRef),
    listPmArtifacts(projectRef),
    listProjectDocuments(projectRef),
    listRequirements(projectRef),
    listScenarios(projectRef),
    listShapes(projectRef),
  ])
  return { project, pmArtifacts, documents, requirements, scenarios, shapes }
}

function contractIdentityPayload(baseContract: Record<string, any>) {
  const payload = JSON.parse(JSON.stringify(baseContract))
  delete payload.generated_at
  delete payload.compiled_contract_identity
  if (payload.source?.developer_definition_revision) {
    payload.source.developer_definition_revision = null
  }
  return payload
}

function contractSignature(baseContract: Record<string, any>): string {
  return createHash('sha256').update(stableStringify(contractIdentityPayload(baseContract))).digest('hex')
}

function generatedArtifactRecord(projectId: string, artifact: SeedArtifact, timestamp: string): ArtifactRecord {
  return {
    id: artifact.id,
    project_id: projectId,
    title: artifact.title,
    status: 'active',
    data: artifact.data,
    content_hash: contractSignature(artifact.data),
    created_at: timestamp,
    updated_at: timestamp,
  }
}

function baseProductArtifacts(pmArtifacts: ArtifactRecord[]): ArtifactRecord[] {
  return pmArtifacts.filter((artifact) => {
    const artifactType = String(artifact.data?.artifact_type ?? '').trim()
    return artifactType !== 'developer_baseline'
      && artifactType !== 'design_traceability'
      && artifactType !== 'developer_definition'
      && artifactType !== 'developer_definition_revision'
      && artifactType !== 'product_design_revision'
      && artifactType !== 'developer_generation_run'
  })
}

function readinessReviewForFinding(finding: AgentConsumptionReadinessFinding, reviewedAt: string): AgentConsumptionReadinessFindingReview {
  if (finding.category === 'derived_target' || finding.category === 'app_glue' || finding.owner === 'agent_app_glue') {
    return {
      id: finding.id,
      decision: 'explicit_app_glue',
      note: 'Showcase seed review classified this as consuming-app guidance. The contract remains valid; the app profile owns selection, framing, or clarification behavior without changing generic ANIP invocation.',
      reviewed_at: reviewedAt,
      review_method: 'manual',
    }
  }
  if (finding.severity === 'blocker') {
    return {
      id: finding.id,
      decision: 'follow_up',
      note: 'Showcase seed review left this as follow-up because blocker-level contract behavior should not be auto-accepted.',
      reviewed_at: reviewedAt,
      review_method: 'manual',
    }
  }
  return {
    id: finding.id,
    decision: 'acceptable_warning',
    note: 'Showcase seed review accepted this as a reviewed limitation for the public GTM contract.',
    reviewed_at: reviewedAt,
    review_method: 'manual',
  }
}

function capabilityById(definition: DeveloperDefinitionData, capabilityId: string | undefined) {
  if (!capabilityId) return null
  return definition.capability_formalizations.find((capability) => capability.capability_id === capabilityId) ?? null
}

function buildConsumabilityReviews(
  definition: DeveloperDefinitionData,
  findings: AgentConsumptionReadinessFinding[],
  findingReviews: Record<string, AgentConsumptionReadinessFindingReview>,
): Record<string, AgentConsumabilityCapabilityReview> {
  const reviews: Record<string, AgentConsumabilityCapabilityReview> = {}
  for (const finding of findings) {
    const review = findingReviews[finding.id]
    if (review?.decision !== 'explicit_app_glue' || !finding.capability_id) continue
    const capability = capabilityById(definition, finding.capability_id)
    const current = reviews[finding.capability_id]
    const semanticRule = semanticInterpretationRuleForFinding(finding, review.note)
    reviews[finding.capability_id] = {
      capability_id: finding.capability_id,
      reviewed_at: review.reviewed_at,
      intent_category: current?.intent_category ?? finding.capability_id.replace(/[_-]+/g, '.'),
      intent_summary: current?.intent_summary ?? capability?.summary ?? capability?.title ?? finding.title,
      app_glue_required: true,
      app_glue_reason: current?.app_glue_reason ?? review.note,
      intent_rules: current?.intent_rules ?? [{
        id: finding.category,
        meaning: finding.detail,
        owner: 'agent_app_glue',
        agent_action: 'Select, clarify, or frame the request before invoking the ANIP capability.',
      }],
      business_language_rules: mergeSemanticInterpretationRule(current?.business_language_rules, semanticRule),
      input_meanings: current?.input_meanings,
      reference_catalogs: current?.reference_catalogs,
      app_boundaries: current?.app_boundaries,
      selection_hints: current?.selection_hints,
    }
  }

  const metadata = buildAgentConsumabilityMetadata({
    definition,
    manualReviews: reviews,
  })
  for (const capability of definition.capability_formalizations) {
    if (!capability.capability_id || reviews[capability.capability_id]) continue
    const capabilityMetadata = metadata.capabilities[capability.capability_id]
    const requiresAppGlue =
      capability.implementation_fit?.category === 'agent_app_glue'
      || capabilityMetadata?.app_glue?.required === true
    if (!requiresAppGlue) continue
    const reason = capabilityMetadata?.app_glue?.reason?.trim()
      || 'Showcase seed review classified this as consuming-app guidance. The contract remains valid; the app profile owns presentation, selection, framing, or clarification behavior without changing generic ANIP invocation.'
    reviews[capability.capability_id] = {
      capability_id: capability.capability_id,
      reviewed_at: new Date().toISOString(),
      intent_category: capabilityMetadata?.intent.category ?? capability.capability_id.replace(/[_-]+/g, '.'),
      intent_summary: capabilityMetadata?.intent.summary ?? capability.summary ?? capability.title ?? capability.capability_id,
      app_glue_required: true,
      app_glue_reason: reason,
      intent_rules: capabilityMetadata?.intent_rules ?? [],
      business_language_rules: capabilityMetadata?.business_language_rules ?? [],
      input_meanings: capabilityMetadata?.input_meanings,
      reference_catalogs: capabilityMetadata?.reference_catalogs,
      app_boundaries: capabilityMetadata?.app_boundaries,
    }
  }
  return reviews
}

function applyAutomaticCoverageStatuses(
  traceability: TraceabilityRecordData,
  definition: DeveloperDefinitionData,
): TraceabilityRecordData {
  const coverage = traceability.coverage.map((item): TraceabilityCoverageItem => {
    if (item.mapping_mode !== 'automatic') return item
    return {
      ...item,
      status: item.mapping_target_key
        ? developerDefinitionTargetStatus(item.mapping_target_key, { developerDefinition: definition })
        : 'not_addressed',
    }
  })
  return { ...traceability, coverage }
}

function applyShowcaseCoordinationCoverageDecisions(
  traceability: TraceabilityRecordData,
  definition: DeveloperDefinitionData,
  reviewedAt: string,
): TraceabilityRecordData {
  const serviceHandoffsContracted = Boolean(
    definition.audit.service_handoffs_required
    || definition.audit.cross_service_continuity_required
    || definition.audit.cross_service_reconstruction_required,
  )

  const coverage = traceability.coverage.map((item): TraceabilityCoverageItem => {
    if (!item.id.startsWith('shape:coordination:') || item.status !== 'not_addressed') return item
    if (serviceHandoffsContracted) {
      return {
        ...item,
        status: 'addressed',
        rationale: [
          `Showcase seed review mapped ${item.label || 'this service coordination edge'} to the Developer Definition audit and lineage controls.`,
          'The compiled definition requires service handoff tracking, parent invocation tracking, cross-service continuity, and reconstruction evidence.',
        ].join(' '),
        linked_surfaces: ['audit_and_lineage', 'scenario_execution_semantics'],
        operator_resolution: {
          choice_id: 'contracted_handoff_controls',
          applied_at: reviewedAt,
          target_artifact: 'Developer Definition / Audit and Lineage',
          summary: 'Cross-service coordination is covered by explicit handoff and reconstruction controls in the Developer Definition.',
          requires_review: true,
          changes: [
            `Marked "${item.label || item.id}" addressed by generated handoff controls.`,
            'Confirmed that the public showcase contract exposes the handoff evidence requirement instead of leaving it as an unmapped product-design item.',
            `Preserved source detail: ${item.detail || 'No source detail provided.'}`,
          ],
        },
      }
    }
    return {
      ...item,
      status: 'deferred',
      rationale: [
        `Showcase seed review classified ${item.label || 'this service coordination edge'} as consuming-app or implementation orchestration.`,
        'The generated ANIP service contract does not declare hidden cross-service execution for this package revision.',
        'Keep the relationship explicit as app glue or implementation material instead of implying generated service behavior.',
      ].join(' '),
      linked_surfaces: ['generation_and_extensions'],
      operator_resolution: {
        choice_id: 'app_owned',
        applied_at: reviewedAt,
        target_artifact: 'Developer Coverage / Agent & App Glue',
        summary: 'Cross-service coordination is reviewed as app/implementation-owned orchestration, not generated ANIP handoff behavior.',
        requires_review: true,
        changes: [
          `Marked "${item.label || item.id}" intentionally deferred from contract-owned service behavior.`,
          'Recorded that the consuming app or implementation material must coordinate this relationship explicitly if needed.',
          `Preserved source detail: ${item.detail || 'No source detail provided.'}`,
        ],
      },
    }
  })
  return { ...traceability, coverage }
}

function buildSeedArtifacts(state: ProjectState): SeedArtifact[] {
  const generatedAt = new Date().toISOString()
  const initialProductArtifacts = baseProductArtifacts(state.pmArtifacts)
  const productRevision = buildProductDesignRevision({
    projectId: state.project.id,
    pmArtifacts: initialProductArtifacts,
    savedAt: generatedAt,
  })
  const productRevisionArtifact: SeedArtifact = {
    id: productDesignRevisionArtifactId(state.project.id, productRevision.revision_number),
    title: `Product Design Revision ${productRevision.revision_number}`,
    data: productRevision as unknown as Record<string, any>,
  }
  const productRevisionRecord = generatedArtifactRecord(state.project.id, productRevisionArtifact, generatedAt)
  const requirements = state.requirements.find((item) => item.role === 'primary') ?? state.requirements[0] ?? null
  const shape = state.shapes[0] ?? null
  const productArtifacts = [...initialProductArtifacts, productRevisionRecord]
  const baseline = buildDeveloperBaseline({
    requirements,
    scenarios: state.scenarios,
    primaryScenarioId: state.scenarios[0]?.id,
    shape,
    pmArtifacts: productArtifacts,
    productRevision: productRevision as ProductDesignRevisionData,
  })
  const baselineArtifact: SeedArtifact = {
    id: developerBaselineArtifactId(state.project.id),
    title: 'Developer Baseline',
    data: baseline as unknown as Record<string, any>,
  }
  const baselineRecord = generatedArtifactRecord(state.project.id, baselineArtifact, generatedAt)
  const sourcePmArtifacts = [...productArtifacts, baselineRecord]
  const firstTraceability = buildTraceabilityRecord({
    pmArtifacts: sourcePmArtifacts,
    requirements,
    scenarios: state.scenarios,
    shape,
    baselineLockedAt: baseline.locked_at,
    existing: null,
  })
  const definition = buildDeveloperDefinitionData({
    project: state.project,
    baseline,
    requirements,
    scenarios: state.scenarios,
    shape,
    pmArtifacts: sourcePmArtifacts,
  })
  const validationIssues = validateDeveloperDefinitionRequiredFields(definition)
  if (validationIssues.length > 0) {
    throw new Error(`Developer Definition has ${validationIssues.length} missing fields: ${validationIssues.slice(0, 12).map((issue) => issue.message).join(' ')}`)
  }

  const readiness = analyzeAgentConsumptionReadiness(definition)
  const readinessReviews = Object.fromEntries(
    readiness.findings.map((finding) => [finding.id, readinessReviewForFinding(finding, generatedAt)]),
  )
  const blockerFollowUps = Object.values(readinessReviews).filter((review) => review.decision === 'follow_up')
  if (blockerFollowUps.length > 0) {
    throw new Error(`Showcase seed found ${blockerFollowUps.length} blocker readiness findings that require real review: ${blockerFollowUps.map((review) => review.id).join(', ')}`)
  }
  const reviewedReadiness = applyReadinessFindingReviews(readiness, readinessReviews)
  const reviewedTraceability = applyShowcaseCoordinationCoverageDecisions(
    applyAutomaticCoverageStatuses(firstTraceability, definition),
    definition,
    generatedAt,
  )
  const traceabilityWithReadiness: TraceabilityRecordData = {
    ...reviewedTraceability,
    developer_status: 'ready_for_pm_review',
    developer_note: 'Showcase seed generated and reviewed Developer Definition readiness artifacts.',
    developer_marked_at: generatedAt,
    agent_consumption_readiness: JSON.parse(JSON.stringify(reviewedReadiness)),
    agent_consumability_reviews: buildConsumabilityReviews(definition, readiness.findings, readinessReviews),
  }

  const traceabilityRecord = generatedArtifactRecord(state.project.id, {
    id: traceabilityArtifactId(state.project.id),
    title: 'Design Traceability',
    data: traceabilityWithReadiness as unknown as Record<string, any>,
  }, generatedAt)
  const definitionRecord = generatedArtifactRecord(state.project.id, {
    id: developerDefinitionArtifactId(state.project.id),
    title: 'Developer Definition',
    data: definition as unknown as Record<string, any>,
  }, generatedAt)
  const highRiskInitial = buildHighRiskConfirmationReport({
    project: state.project,
    pmArtifacts: [...sourcePmArtifacts, traceabilityRecord, definitionRecord],
    documents: state.documents,
    requirements: state.requirements,
    scenarios: state.scenarios,
    shapes: state.shapes,
  })
  const highRiskReport = buildHighRiskConfirmationReport({
    project: state.project,
    pmArtifacts: [...sourcePmArtifacts, traceabilityRecord, definitionRecord],
    documents: state.documents,
    requirements: state.requirements,
    scenarios: state.scenarios,
    shapes: state.shapes,
    existing: {
      ...highRiskInitial,
      reviews: Object.fromEntries(highRiskInitial.items.map((item) => [item.id, {
        id: item.id,
        status: 'confirmed',
        note: 'Showcase seed confirmed this item for public contract display; it remains visible as review evidence.',
        reviewed_at: generatedAt,
      }])),
    },
  })
  const traceabilityFinal: TraceabilityRecordData = {
    ...traceabilityWithReadiness,
    high_risk_confirmations: highRiskReport,
  }

  const baseContract = buildDeveloperDefinitionContract({
    project: state.project,
    baseline,
    requirements,
    scenarios: state.scenarios,
    shape,
    traceability: traceabilityFinal,
    developerDefinition: definition,
  }) as Record<string, any>
  const savedRevision = {
    revision_number: 1,
    revision_artifact_id: developerDefinitionRevisionArtifactId(state.project.id, 1),
    previous_revision_artifact_id: null,
    saved_at: generatedAt,
  }
  const identity: DeveloperCompiledContractIdentity = {
    artifact_name: `${state.project.id}-developer-definition.json`,
    canonical_format: 'stable-json-v1',
    signature_algorithm: 'sha256',
    signature: contractSignature(baseContract),
    generated_at: generatedAt,
  }
  const payload: DeveloperDefinitionData = {
    ...definition,
    compiled_contract_identity: identity,
    saved_revision: savedRevision,
    saved_at: generatedAt,
  }
  const revisionPayload: DeveloperDefinitionRevisionData = {
    ...payload,
    artifact_type: 'developer_definition_revision',
  }

  return [
    productRevisionArtifact,
    baselineArtifact,
    {
      id: traceabilityArtifactId(state.project.id),
      title: 'Design Traceability',
      data: traceabilityFinal as unknown as Record<string, any>,
    },
    {
      id: savedRevision.revision_artifact_id,
      title: `Developer Definition Revision ${savedRevision.revision_number}`,
      data: revisionPayload as unknown as Record<string, any>,
    },
    {
      id: developerDefinitionArtifactId(state.project.id),
      title: 'Developer Definition',
      data: payload as unknown as Record<string, any>,
    },
  ]
}

async function main() {
  log(`Loading ${projectId} from ${apiBase}`)
  const state = await loadState(projectId)
  const artifacts = buildSeedArtifacts(state)
  await mkdir(dirname(outputFile), { recursive: true })
  await writeFile(outputFile, `${JSON.stringify(artifacts, null, 2)}\n`)
  log(`Wrote ${artifacts.length} developer seed artifacts to ${outputFile}`)
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
