import { createHash } from 'node:crypto'
import { mkdir, writeFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import {
  buildDeveloperBaseline,
  buildTraceabilityRecord,
  developerBaselineArtifactId,
  findDeveloperBaselineArtifact,
  findTraceabilityArtifact,
  traceabilityArtifactId,
} from '../studio/src/design/traceability.ts'
import {
  buildProductDesignRevision,
  findLatestProductDesignRevisionArtifact,
  productDesignSourceHash,
  type ProductDesignRevisionData,
} from '../studio/src/design/product-design.ts'
import {
  buildDeveloperDefinitionContract,
  buildDeveloperDefinitionData,
  developerDefinitionArtifactId,
  developerDefinitionRevisionArtifactId,
  findDeveloperDefinitionArtifact,
  findLatestDeveloperDefinitionRevisionArtifact,
  stableStringify,
  validateDeveloperDefinitionRequiredFields,
  type DeveloperDefinitionData,
  type DeveloperDefinitionRevisionData,
} from '../studio/src/design/developer-definition.ts'
import type {
  ArtifactRecord,
  DeveloperBaselineData,
  DeveloperCompiledContractIdentity,
  DeveloperDefinitionSavedRevision,
  ProjectDetail,
  RequirementsRecord,
  ShapeRecord,
  TraceabilityRecordData,
} from '../studio/src/design/project-types.ts'

const API_BASE = process.env.STUDIO_API_URL ?? 'http://127.0.0.1:8100'
const PROJECT_ID = process.env.STUDIO_PROJECT_ID ?? 'gtm-pipeline-q2-review'
const GENERATED_TS_DIR = process.env.GTM_GENERATED_TS_DIR
  ?? 'examples/showcase/gtm/generated/studio_gtm_pipeline_typescript_registry'

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init.headers ?? {}),
    },
  })
  const text = await response.text()
  const body = text ? JSON.parse(text) : null
  if (!response.ok) {
    throw new Error(`${init.method ?? 'GET'} ${path} failed (${response.status}): ${text}`)
  }
  return body as T
}

function sha256Hex(input: string): string {
  return createHash('sha256').update(input).digest('hex')
}

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function contractIdentityPayload(baseContract: Record<string, any>): Record<string, any> {
  const payload = clone(baseContract)
  delete payload.generated_at
  if (payload.source?.developer_definition) {
    payload.source.developer_definition.saved_at = null
    delete payload.source.developer_definition.saved_revision
  }
  return payload
}

function materializeDefinitionContract(
  projectId: string,
  baseContract: Record<string, any>,
  definition: DeveloperDefinitionData,
): { contract: Record<string, any>; identity: DeveloperCompiledContractIdentity } {
  const canonicalJson = stableStringify(contractIdentityPayload(baseContract))
  const identity: DeveloperCompiledContractIdentity = {
    artifact_name: `${projectId}-developer-definition.json`,
    canonical_format: 'stable-json-v1',
    signature_algorithm: 'sha256',
    signature: sha256Hex(canonicalJson),
    generated_at: new Date().toISOString(),
  }
  return {
    identity,
    contract: {
      ...baseContract,
      identity: {
        artifact_name: identity.artifact_name,
        canonical_format: identity.canonical_format,
        signature_algorithm: identity.signature_algorithm,
        signature: identity.signature,
        generated_at: identity.generated_at,
        revision_number: definition.saved_revision?.revision_number ?? null,
        revision_artifact_id: definition.saved_revision?.revision_artifact_id ?? null,
        previous_revision_artifact_id: definition.saved_revision?.previous_revision_artifact_id ?? null,
        requirements_hash: definition.source_inputs.requirements_hash ?? null,
        scenario_set_hash: definition.source_inputs.scenario_set_hash ?? null,
        service_design_hash: definition.source_inputs.shape_hash ?? null,
        baseline_locked_at: definition.source_inputs.baseline_locked_at ?? null,
        developer_definition_saved_at: definition.saved_at ?? null,
      },
    },
  }
}

function serviceIds(definition: DeveloperDefinitionData): string[] {
  const selected = definition.generation?.selected_service_ids ?? []
  const topology = (definition.service_topology_bindings ?? []).map((service) => service.service_id || service.id)
  return Array.from(new Set([...selected, ...topology].filter(Boolean)))
}

function completeRequiredFields(definition: DeveloperDefinitionData, project: ProjectDetail): DeveloperDefinitionData {
  const completed = clone(definition)
  const ids = serviceIds(completed)
  const primaryServiceId = ids[0] ?? 'gtm-pipeline-service'

  completed.product_alignment.governed_behavior_formalization ||= 'Formalize bounded GTM pipeline reads, clarifications, denials, and approval-stop behavior from Product Design.'
  completed.product_alignment.approval_posture_formalization ||= 'Read-only summaries can execute when scoped; write-adjacent preparation must stop at approval.'
  completed.identity.system_name ||= project.name
  completed.identity.domain_name ||= project.domain || 'revenue_operations'
  completed.identity.delivery_model ||= 'generated_service'
  completed.identity.architecture_shape ||= 'production_single_service'

  completed.backend_bindings.data_access_backend_type ||= 'postgres_dbt_cube'
  completed.backend_bindings.data_access_target_label ||= 'GTM Postgres, dbt, and Cube semantic layer'
  completed.backend_bindings.application_integration_backend_type ||= 'local_http_services'
  completed.backend_bindings.application_integration_system_name ||= 'GTM showcase local services'
  completed.backend_bindings.application_integration_environment ||= 'local-development'
  completed.backend_bindings.application_integration_auth_type ||= 'purpose_bound_delegation'
  completed.backend_bindings.application_integration_adapter_target ||= 'examples/showcase/gtm'

  for (const service of completed.service_topology_bindings ?? []) {
    if (!service.formalized_capability_ids?.length) {
      service.formalized_capability_ids = [...(service.source_capabilities ?? completed.capability_formalizations.map((capability) => capability.capability_id).filter(Boolean))]
    }
  }
  for (const actor of completed.actor_expectations ?? []) {
    actor.summary_formalization ||= actor.actor_summary || actor.actor_title || actor.actor_id
    actor.visibility_formalization ||= 'Bounded visibility follows the Product Design actor model and permission intent.'
    actor.action_formalization ||= 'Actions are limited to governed summaries and approval-gated preparation.'
    actor.approval_formalization ||= 'High-risk or write-adjacent operations require explicit approval before mutation.'
  }
  for (const permission of completed.permission_intent_bindings ?? []) {
    if (!permission.target_service_ids?.length) permission.target_service_ids = [...ids]
    permission.formalization_strategy ||= 'Bind actor, business area, purpose, and service target into runtime policy checks.'
  }
  completed.data_domain.domain_name ||= project.domain || 'revenue_operations'
  for (const concept of completed.domain_concept_bindings ?? []) {
    concept.technical_representation ||= `${concept.concept_name || concept.concept_id} represented as bounded GTM semantic records and aggregate evidence.`
  }
  for (const object of completed.application_object_model ?? []) {
    object.object_id ||= (object.name || 'gtm_object').toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '')
    object.name ||= object.object_id
  }
  for (const capability of completed.capability_formalizations ?? []) {
    capability.capability_id ||= capability.id
    capability.title ||= capability.capability_id
    capability.intent_type ||= 'summarize'
    capability.operation_type ||= capability.side_effect_level === 'approval_required_write' ? 'write' : 'read'
    capability.side_effect_level ||= capability.operation_type === 'write' ? 'approval_required_write' : 'read_only'
    capability.summary ||= `Formalized GTM capability ${capability.capability_id}.`
    capability.backend_operation ||= capability.capability_id
  }
  for (const scenario of completed.scenario_formalizations ?? []) {
    if (!scenario.participating_service_ids?.length) scenario.participating_service_ids = [primaryServiceId]
    if (!scenario.required_behaviors?.length) scenario.required_behaviors = ['Preserve the Product Design expected behavior for this scenario.']
    if (!scenario.required_anip_support?.length) scenario.required_anip_support = ['Expose governed ANIP outcome, audit, and evidence semantics.']
    for (const step of scenario.orchestration_steps ?? []) {
      step.service_id ||= primaryServiceId
      step.step_kind ||= 'capability_execution'
      if (step.step_kind === 'capability_execution') {
        step.capability_id ||= completed.capability_formalizations[0]?.capability_id ?? 'gtm.pipeline_summary'
      }
      step.outcome_type ||= 'success'
      step.stop_condition ||= 'Stop on clarification, denial, approval-required, or capability failure.'
    }
  }
  for (const rule of completed.composition_rules ?? []) {
    if (!rule.affected_scenario_ids?.length) rule.affected_scenario_ids = [...completed.source_inputs.scenario_ids]
    rule.formalization_strategy ||= 'Keep service boundaries explicit and require recorded approval before execution steps.'
  }
  for (const binding of completed.verification.supported_question_family_bindings ?? []) {
    if (!binding.target_service_ids?.length) binding.target_service_ids = [...ids]
    binding.verification_strategy ||= 'Exercise representative question-bank prompts against the generated runtime and verify governed outcomes.'
  }
  for (const binding of completed.verification.business_goal_bindings ?? []) {
    if (!binding.target_service_ids?.length) binding.target_service_ids = [...ids]
    binding.verification_strategy ||= 'Verify generated services satisfy the business goal with bounded evidence and no hidden mutation.'
  }
  for (const guard of completed.verification.non_goal_guards ?? []) {
    guard.guard_strategy ||= 'Reject or stop behavior that violates the non-goal.'
    guard.evidence_signal ||= 'Runtime outcome shows denial, clarification, or approval-required posture.'
  }
  for (const check of completed.verification.success_criteria_checks ?? []) {
    check.verification_strategy ||= 'Run Studio/ANIP regression questions and inspect recorded runtime evidence.'
  }

  return completed
}

async function upsertPmArtifact(projectId: string, id: string, title: string, data: Record<string, any>, status?: string): Promise<ArtifactRecord> {
  const artifacts = await api<ArtifactRecord[]>(`/api/projects/${projectId}/pm-artifacts`)
  const existing = artifacts.find((artifact) => artifact.id === id)
  if (existing) {
    return api<ArtifactRecord>(`/api/projects/${projectId}/pm-artifacts/${id}`, {
      method: 'PUT',
      body: JSON.stringify({ title, status, data }),
    })
  }
  return api<ArtifactRecord>(`/api/projects/${projectId}/pm-artifacts`, {
    method: 'POST',
    body: JSON.stringify({ id, title, data }),
  })
}

function resolveProductRevisionRef(baseline: DeveloperBaselineData): string {
  const artifactId = baseline.source_inputs.product_revision_artifact_id
  const revisionNumber = baseline.source_inputs.product_revision_number
  if (artifactId && revisionNumber) return `${artifactId}@r${revisionNumber}`
  if (artifactId) return artifactId
  return `baseline:${baseline.locked_at}`
}

function buildRegistryPayload(params: {
  project: ProjectDetail
  baseline: DeveloperBaselineData
  definition: DeveloperDefinitionData
  serviceDefinition: Record<string, any>
  signature: string
}) {
  const savedRevision = params.definition.saved_revision
  const packageVersion = savedRevision ? `0.1.${savedRevision.revision_number}` : '0.1.0'
  const generatedAt = new Date().toISOString()
  const productRevisionRef = resolveProductRevisionRef(params.baseline)
  const developerRevisionRef = savedRevision
    ? `${savedRevision.revision_artifact_id}@r${savedRevision.revision_number}`
    : 'working'
  const lineage = {
    project_id: params.project.id,
    product: {
      artifact_id: params.baseline.source_inputs.product_revision_artifact_id ?? null,
      revision_number: params.baseline.source_inputs.product_revision_number ?? null,
      baseline_locked_at: params.baseline.locked_at,
      product_design_hash: params.baseline.source_inputs.product_design_hash ?? null,
    },
    developer: {
      artifact_id: savedRevision?.revision_artifact_id ?? null,
      revision_number: savedRevision?.revision_number ?? null,
      previous_revision_artifact_id: savedRevision?.previous_revision_artifact_id ?? null,
      contract_signature: params.signature,
    },
  }
  const manifest = {
    package_kind: 'anip_service_blueprint',
    blueprint_id: params.project.id,
    name: `${params.project.name} Service Blueprint`,
    version: packageVersion,
    schema_version: params.serviceDefinition.contract_schema_version ?? 'developer_definition.v1',
    publisher: { id: 'local-studio', display_name: 'Local Studio Export' },
    service_definition: 'anip-service-definition.json',
    service_definition_digest: params.signature,
    service_definition_digest_algorithm: 'sha256',
    build_packs: { recommended: ['anip-build-pack-typescript@local'] },
    verifier_packs: { recommended: ['anip-verifier@local'] },
    generated_at: generatedAt,
    lineage,
  }
  const recommendedLock = {
    lock_kind: 'publisher_recommended_lock',
    blueprint_id: params.project.id,
    blueprint_version: packageVersion,
    service_definition_digest: params.signature,
    schema_version: manifest.schema_version,
    build_packs: manifest.build_packs,
    verifier_packs: manifest.verifier_packs,
    runtime_packages: [],
    extension_packs: [],
    regression_packs: [],
    generated_at: generatedAt,
    lineage,
  }
  return {
    package_id: params.project.id,
    package_version: packageVersion,
    project_ref: params.project.id,
    product_revision_ref: productRevisionRef,
    developer_revision_ref: developerRevisionRef,
    contract_signature: params.signature,
    lineage,
    schema_version: manifest.schema_version,
    manifest,
    service_definition: params.serviceDefinition,
    recommended_lock: recommendedLock,
  }
}

async function writeGeneratedTypeScriptBundle(projectId: string, serviceDefinition: Record<string, any>) {
  const generated = await api<{
    generated_at: string
    system_name: string
    package_name: string | null
    file_count: number
    files: Array<{ path: string; content: string }>
  }>(`/api/projects/${projectId}/generator/typescript`, {
    method: 'POST',
    body: JSON.stringify({
      definition: serviceDefinition,
      package_name: '@anip-generated/gtm-pipeline-q2-review',
      dependency_source: 'registry',
    }),
  })
  for (const file of generated.files) {
    const target = join(GENERATED_TS_DIR, file.path)
    await mkdir(dirname(target), { recursive: true })
    await writeFile(target, file.content, 'utf8')
  }
  return generated
}

async function main() {
  const project = await api<ProjectDetail>(`/api/projects/${PROJECT_ID}`)
  const requirements = await api<RequirementsRecord[]>(`/api/projects/${PROJECT_ID}/requirements`)
  const scenarios = await api<ArtifactRecord[]>(`/api/projects/${PROJECT_ID}/scenarios`)
  const shapes = await api<ShapeRecord[]>(`/api/projects/${PROJECT_ID}/shapes`)
  let pmArtifacts = await api<ArtifactRecord[]>(`/api/projects/${PROJECT_ID}/pm-artifacts`)

  const primaryRequirements = requirements.find((item) => item.role === 'primary') ?? requirements[0] ?? null
  const primaryScenarioId = scenarios.find((item) => item.id === 'scn-gtm-pipeline-q2-review')?.id ?? scenarios[0]?.id ?? null
  const shape = shapes[0] ?? null
  if (!primaryRequirements || !shape || scenarios.length === 0) {
    throw new Error('Project is missing requirements, scenarios, or shape data required for a locked baseline.')
  }

  const currentProductDesignHash = productDesignSourceHash(pmArtifacts)
  const latestProductRevisionArtifact = findLatestProductDesignRevisionArtifact(pmArtifacts)
  const latestProductRevision = latestProductRevisionArtifact?.data as ProductDesignRevisionData | undefined
  const productRevision = latestProductRevision?.product_design_hash === currentProductDesignHash
    ? latestProductRevision
    : buildProductDesignRevision({ projectId: project.id, pmArtifacts })

  if (productRevision.revision_artifact_id !== latestProductRevision?.revision_artifact_id) {
    await upsertPmArtifact(project.id, productRevision.revision_artifact_id, `Product Design Revision ${productRevision.revision_number}`, productRevision)
    pmArtifacts = await api<ArtifactRecord[]>(`/api/projects/${PROJECT_ID}/pm-artifacts`)
  }

  const baseline = buildDeveloperBaseline({
    requirements: primaryRequirements,
    scenarios,
    primaryScenarioId,
    shape,
    pmArtifacts,
    productRevision,
    existing: null,
  })
  await upsertPmArtifact(project.id, developerBaselineArtifactId(project.id), 'Locked Product Design Baseline', baseline, 'locked')
  pmArtifacts = await api<ArtifactRecord[]>(`/api/projects/${PROJECT_ID}/pm-artifacts`)

  const traceabilityArtifact = findTraceabilityArtifact(pmArtifacts)
  const traceability = buildTraceabilityRecord({
    pmArtifacts,
    requirements: primaryRequirements,
    scenarios,
    primaryScenarioId,
    shape,
    baselineLockedAt: baseline.locked_at,
    existing: (traceabilityArtifact?.data as TraceabilityRecordData | undefined) ?? null,
  })
  await upsertPmArtifact(project.id, traceabilityArtifactId(project.id), 'Design Traceability', traceability)
  pmArtifacts = await api<ArtifactRecord[]>(`/api/projects/${PROJECT_ID}/pm-artifacts`)

  const savedDefinitionArtifact = findDeveloperDefinitionArtifact(pmArtifacts)
  const savedDefinition = (savedDefinitionArtifact?.data as DeveloperDefinitionData | undefined) ?? null
  const latestDefinitionRevisionArtifact = findLatestDeveloperDefinitionRevisionArtifact(pmArtifacts)
  const latestDefinitionRevision = (latestDefinitionRevisionArtifact?.data as DeveloperDefinitionRevisionData | undefined)?.saved_revision
    ?? savedDefinition?.saved_revision
    ?? null
  const latestSavedSignature = (latestDefinitionRevisionArtifact?.data as DeveloperDefinitionRevisionData | undefined)?.compiled_contract_identity?.signature
    ?? savedDefinition?.compiled_contract_identity?.signature
    ?? null

  const draft = completeRequiredFields(buildDeveloperDefinitionData({
    project,
    baseline,
    requirements: primaryRequirements,
    scenarios,
    shape,
    pmArtifacts,
    existing: savedDefinition,
  }), project)

  const validationIssues = validateDeveloperDefinitionRequiredFields(draft)
  if (validationIssues.length > 0) {
    throw new Error(`Developer Definition still has required-field gaps: ${validationIssues.map((issue) => `${issue.path}: ${issue.message}`).join('; ')}`)
  }

  const draftContract = buildDeveloperDefinitionContract({
    project,
    baseline,
    requirements: primaryRequirements,
    scenarios,
    shape,
    traceability,
    developerDefinition: draft,
  }) as Record<string, any>
  const draftMaterialized = materializeDefinitionContract(project.id, draftContract, draft)
  const shouldCreateRevision = Boolean(draftMaterialized.identity.signature)
    && (!latestDefinitionRevision || draftMaterialized.identity.signature !== latestSavedSignature)
  const nextRevisionNumber = (latestDefinitionRevision?.revision_number ?? 0) + (shouldCreateRevision ? 1 : 0)
  const savedAt = new Date().toISOString()
  const savedRevision: DeveloperDefinitionSavedRevision | null = shouldCreateRevision
    ? {
        revision_number: nextRevisionNumber,
        revision_artifact_id: developerDefinitionRevisionArtifactId(project.id, nextRevisionNumber),
        previous_revision_artifact_id: latestDefinitionRevision?.revision_artifact_id ?? null,
        saved_at: savedAt,
      }
    : latestDefinitionRevision

  const savedDefinitionPayload: DeveloperDefinitionData = {
    ...draft,
    artifact_type: 'developer_definition',
    compiled_contract_identity: draftMaterialized.identity,
    saved_revision: savedRevision,
    saved_at: savedRevision?.saved_at ?? savedAt,
  }

  const savedContract = buildDeveloperDefinitionContract({
    project,
    baseline,
    requirements: primaryRequirements,
    scenarios,
    shape,
    traceability,
    developerDefinition: savedDefinitionPayload,
  }) as Record<string, any>
  const savedMaterialized = materializeDefinitionContract(project.id, savedContract, savedDefinitionPayload)
  savedDefinitionPayload.compiled_contract_identity = savedMaterialized.identity

  if (shouldCreateRevision && savedRevision) {
    const revisionPayload: DeveloperDefinitionRevisionData = {
      ...savedDefinitionPayload,
      artifact_type: 'developer_definition_revision',
      saved_revision: savedRevision,
    }
    await upsertPmArtifact(project.id, savedRevision.revision_artifact_id, `Developer Definition Revision ${savedRevision.revision_number}`, revisionPayload)
  }
  await upsertPmArtifact(project.id, developerDefinitionArtifactId(project.id), 'Developer Definition', savedDefinitionPayload, 'draft')

  const registryPayload = buildRegistryPayload({
    project,
    baseline,
    definition: savedDefinitionPayload,
    serviceDefinition: savedMaterialized.contract,
    signature: savedMaterialized.identity.signature ?? '',
  })
  const registryResult = await api<any>('/api/registry/publications', {
    method: 'POST',
    body: JSON.stringify(registryPayload),
  })
  const generated = await writeGeneratedTypeScriptBundle(project.id, savedMaterialized.contract)

  console.log(JSON.stringify({
    project_id: project.id,
    product_revision: productRevision.revision_artifact_id,
    product_revision_number: productRevision.revision_number,
    baseline_locked_at: baseline.locked_at,
    developer_revision: savedRevision?.revision_artifact_id ?? null,
    developer_revision_number: savedRevision?.revision_number ?? null,
    contract_signature: savedMaterialized.identity.signature,
    registry_package: `${registryPayload.package_id}@${registryPayload.package_version}`,
    registry_receipt: registryResult.receipt?.receipt_id ?? null,
    generated_typescript_dir: GENERATED_TS_DIR,
    generated_typescript_files: generated.file_count,
  }, null, 2))
}

main().catch((error) => {
  console.error(error instanceof Error ? error.stack : error)
  process.exit(1)
})
