<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { createPmArtifact, verifyLocalRegistryPackageWithGo, verifyRegistryPackageWithGo } from '../design/project-api'
import { loadProject, projectStore } from '../design/project-store'
import {
  parseExternalCliResult,
  summarizeExternalCliResult,
  type ExternalCliPublicationContext,
  type ExternalCliProvenanceSummary,
} from '../design/external-cli-provenance'
import {
  findDeveloperDefinitionArtifact,
  findDeveloperGenerationRunArtifacts,
  findLatestDeveloperGenerationRunArtifact,
  resolveEvaluationCompiledContractIdentity,
  resolveEvaluationObservedServiceEvidence,
  resolveEvaluationEvidenceEnvelope,
  resolveEvaluationServiceMetadataSnapshot,
  resolveObservedServiceEvidence,
  resolveCompiledContractAlignment,
  resolveGenerationContractAlignment,
} from '../design/developer-definition'
import {
  analyzeAgentConsumptionReadiness,
  readinessStatusLabel,
  type AgentConsumptionReadinessReport,
} from '../design/agent-consumption-readiness'
import type { DeveloperDefinitionData, DeveloperGenerationRunData, EvaluationEvidenceEnvelope, EvaluationRecord, TraceabilityRecordData } from '../design/project-types'
import { classifyPublicationLineage, findRegistryPublicationArtifacts } from '../design/publication-lineage'
import { findReleaseRecordArtifacts, summarizeApprovalLineage } from '../design/release-lineage'
import { formatStudioTimestamp } from '../design/time'
import { developerStatusLabel, findTraceabilityArtifact, pmReviewStatusLabel, summarizeCoverage } from '../design/traceability'
import { developerLabel } from '../design/developer-vocabulary'

const route = useRoute()
const router = useRouter()

const projectId = computed(() => route.params.projectId as string)
const project = computed(() => projectStore.activeProject)
const readOnlyMode = computed(() => projectStore.runtimeStatus?.read_only_mode !== false)
const readOnlyReason = computed(() =>
  projectStore.runtimeStatus?.read_only_reason
  || 'Studio is running in read-only mode. Explore the design, then download and run Studio locally to make changes.',
)
const developerDefinitionArtifact = computed(() => findDeveloperDefinitionArtifact(projectStore.artifacts.pmArtifacts))
const developerDefinition = computed(() =>
  (developerDefinitionArtifact.value?.data as DeveloperDefinitionData | undefined) ?? null,
)
const compiledContractIdentity = computed(() =>
  developerDefinition.value?.compiled_contract_identity ?? null,
)
const currentSavedRevision = computed(() => developerDefinition.value?.saved_revision ?? null)
const currentProductRevisionArtifactId = computed(() => developerDefinition.value?.source_inputs?.product_revision_artifact_id ?? null)
const currentProductRevisionNumber = computed(() => developerDefinition.value?.source_inputs?.product_revision_number ?? null)
const registryPublicationArtifacts = computed(() => findRegistryPublicationArtifacts(projectStore.artifacts.pmArtifacts))
const latestRegistryPublicationArtifact = computed(() => registryPublicationArtifacts.value[0] ?? null)
const publicationLineage = computed(() =>
  classifyPublicationLineage(latestRegistryPublicationArtifact.value, {
    productRevisionArtifactId: currentProductRevisionArtifactId.value,
    productRevisionNumber: currentProductRevisionNumber.value,
    developerRevisionArtifactId: currentSavedRevision.value?.revision_artifact_id ?? null,
    developerRevisionNumber: currentSavedRevision.value?.revision_number ?? null,
    contractSignature: compiledContractIdentity.value?.signature ?? null,
  }),
)
const approvalLineage = computed(() =>
  summarizeApprovalLineage(projectStore.artifacts.pmArtifacts, {
    productRevisionArtifactId: currentProductRevisionArtifactId.value,
    productRevisionNumber: currentProductRevisionNumber.value,
    developerRevisionArtifactId: currentSavedRevision.value?.revision_artifact_id ?? null,
    developerRevisionNumber: currentSavedRevision.value?.revision_number ?? null,
    contractSignature: compiledContractIdentity.value?.signature ?? null,
  }),
)
const releaseArtifacts = computed(() => findReleaseRecordArtifacts(projectStore.artifacts.pmArtifacts))
const latestReleaseArtifact = computed(() => releaseArtifacts.value[0] ?? null)
const latestRelease = computed(() => latestReleaseArtifact.value?.data as Record<string, any> | undefined)
const externalCliPublicationContext = computed<ExternalCliPublicationContext | null>(() => {
  const artifact = latestRegistryPublicationArtifact.value
  const data = artifact?.data as Record<string, any> | undefined
  const packageRecord = (data?.package ?? {}) as Record<string, any>
  const lineage = data?.lineage ?? packageRecord.lineage ?? packageRecord.manifest?.lineage ?? packageRecord.recommended_lock?.lineage ?? {}
  const receipt = (data?.receipt ?? {}) as Record<string, any>
  if (!packageRecord.package_id || !packageRecord.package_version) return null
  return {
    publicationArtifactId: artifact?.id ?? null,
    packageId: String(packageRecord.package_id),
    packageVersion: String(packageRecord.package_version),
    productRevision: lineage.product_revision ?? null,
    developerRevision: lineage.developer_revision ?? null,
    receiptSignature: typeof receipt.registry_signature === 'string' ? receipt.registry_signature : null,
  }
})
type ExternalCliProvenanceArtifactData = {
  artifact_type: 'external_cli_provenance_result'
  imported_at: string
  source_tool: string
  raw_result: Record<string, any>
  summary: ExternalCliProvenanceSummary
  reconciled_against_publication_artifact_id: string | null
}
const externalCliProvenanceArtifacts = computed(() => {
  const artifacts = [...projectStore.artifacts.pmArtifacts].filter((artifact) =>
    artifact.data?.artifact_type === 'external_cli_provenance_result',
  )
  artifacts.sort((a, b) => new Date(b.updated_at || b.created_at).getTime() - new Date(a.updated_at || a.created_at).getTime())
  return artifacts
})
const externalCliProvenanceRows = computed(() =>
  externalCliProvenanceArtifacts.value.map((artifact) => {
    const data = artifact.data as ExternalCliProvenanceArtifactData
    return {
      artifactId: artifact.id,
      importedAt: data.imported_at || artifact.created_at,
      summary: data.summary,
    }
  }),
)
const generationRunArtifacts = computed(() => {
  const artifacts = [...findDeveloperGenerationRunArtifacts(projectStore.artifacts.pmArtifacts)]
  artifacts.sort((a, b) => new Date(b.updated_at || b.created_at).getTime() - new Date(a.updated_at || a.created_at).getTime())
  return artifacts
})
const latestGenerationRunArtifact = computed(() => findLatestDeveloperGenerationRunArtifact(projectStore.artifacts.pmArtifacts))
const selectedGenerationRunArtifactId = computed(() => {
  const queryValue = typeof route.query.generationRun === 'string' ? route.query.generationRun.trim() : ''
  if (queryValue && generationRunArtifacts.value.some((artifact) => artifact.id === queryValue)) return queryValue
  return latestGenerationRunArtifact.value?.id ?? null
})
const selectedGenerationRunArtifact = computed(() =>
  generationRunArtifacts.value.find((artifact) => artifact.id === selectedGenerationRunArtifactId.value)
  ?? latestGenerationRunArtifact.value
  ?? null,
)
const latestGenerationRun = computed(() =>
  (selectedGenerationRunArtifact.value?.data as DeveloperGenerationRunData | undefined) ?? null,
)
const latestEvaluation = computed(() => {
  const targetRunId = selectedGenerationRunArtifactId.value
  const evaluations = [...projectStore.artifacts.evaluations]
    .filter((record) => {
      const envelope = resolveEvaluationEvidenceEnvelope(record as any)
      const runId = envelope?.generation_run_artifact_id ?? null
      return targetRunId ? runId === targetRunId : true
    })
  evaluations.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
  return evaluations[0] ?? null
})
const observedServiceArtifacts = computed(() => {
  const targetRunId = selectedGenerationRunArtifactId.value
  const artifacts = [...projectStore.artifacts.serviceMetadata]
    .filter((artifact) => {
      const runId = typeof artifact.data?.generation_run_artifact_id === 'string'
        ? artifact.data.generation_run_artifact_id
        : null
      return targetRunId ? runId === targetRunId : true
    })
  artifacts.sort((a, b) => new Date(b.updated_at || b.created_at).getTime() - new Date(a.updated_at || a.created_at).getTime())
  return artifacts
})
const latestEvaluationEvidenceEnvelope = computed(() => resolveEvaluationEvidenceEnvelope(latestEvaluation.value as any))
const latestEvaluationContractIdentity = computed(() => resolveEvaluationCompiledContractIdentity(latestEvaluation.value as any))
const latestEvaluationObservedServiceEvidence = computed(() => resolveEvaluationObservedServiceEvidence(latestEvaluation.value as any))
const latestEvaluationServiceMetadata = computed(() => resolveEvaluationServiceMetadataSnapshot(latestEvaluation.value as any))
const latestEvaluationGenerationRunArtifactId = computed(() => latestEvaluationEvidenceEnvelope.value?.generation_run_artifact_id ?? null)
const latestEvaluationGenerationDependencySource = computed(() => latestEvaluationEvidenceEnvelope.value?.generation_dependency_source ?? null)
const latestEvaluationPayload = computed(() =>
  (latestEvaluation.value?.data?.evaluation as Record<string, any> | undefined) ?? null,
)
const generationAlignment = computed(() =>
  resolveGenerationContractAlignment(compiledContractIdentity.value as any, latestGenerationRun.value?.compiled_contract_identity as any),
)
const traceabilityArtifact = computed(() => findTraceabilityArtifact(projectStore.artifacts.pmArtifacts))
const traceabilityData = computed(() => (traceabilityArtifact.value?.data as TraceabilityRecordData | undefined) ?? null)
function isAgentReadinessReport(value: unknown): value is AgentConsumptionReadinessReport {
  if (!value || typeof value !== 'object') return false
  const report = value as Partial<AgentConsumptionReadinessReport>
  const summary = report.summary as Partial<AgentConsumptionReadinessReport['summary']> | undefined
  return Boolean(
    report.artifact_type === 'agent_consumption_readiness'
    && typeof report.status === 'string'
    && typeof report.score === 'number'
    && summary
    && typeof summary.blockers === 'number'
    && typeof summary.warnings === 'number'
    && typeof summary.info === 'number'
    && typeof summary.probes === 'number'
    && typeof summary.required_app_glue === 'number',
  )
}
const agentReadinessReport = computed(() =>
  isAgentReadinessReport(traceabilityData.value?.agent_consumption_readiness)
    ? traceabilityData.value.agent_consumption_readiness
    : analyzeAgentConsumptionReadiness(developerDefinition.value),
)
const coverageSummary = computed(() =>
  summarizeCoverage((traceabilityArtifact.value?.data as { coverage?: any[] } | undefined)?.coverage ?? []),
)
const externalCliImportText = ref('')
const externalCliImportError = ref<string | null>(null)
const externalCliImportRunning = ref(false)
const externalCliImportSummary = ref<ExternalCliProvenanceSummary | null>(null)
const goVerifierRunning = ref(false)
const goVerifierError = ref<string | null>(null)
const goVerifierSummary = ref<ExternalCliProvenanceSummary | null>(null)
const registryGoVerifierRunning = ref(false)
const registryGoVerifierError = ref<string | null>(null)
const registryGoVerifierSummary = ref<ExternalCliProvenanceSummary | null>(null)

type EvidenceStatus = 'ready' | 'stale' | 'missing'
type RevisionEvidenceStatus = 'current' | 'superseded' | 'unversioned' | 'mismatch' | 'missing'
type RevisionEvidenceTarget = {
  definition_revision_artifact_id?: string | null
  definition_revision_number?: number | null
}

function statusLabel(status: EvidenceStatus): string {
  if (status === 'ready') return 'Ready'
  if (status === 'stale') return 'Stale'
  return 'Missing'
}

function evidenceStatusFromAlignment(
  alignment: { status: 'aligned' | 'stale' | 'unknown'; detail: string },
  hasObserved: boolean,
  missingDetail: string,
): { status: EvidenceStatus; label: string; detail: string } {
  if (!hasObserved || alignment.status === 'unknown') {
    return { status: 'missing', label: statusLabel('missing'), detail: missingDetail }
  }
  if (alignment.status === 'aligned') {
    return { status: 'ready', label: statusLabel('ready'), detail: alignment.detail }
  }
  return { status: 'stale', label: statusLabel('stale'), detail: alignment.detail }
}

function revisionEvidenceLabel(status: RevisionEvidenceStatus): string {
  switch (status) {
    case 'current':
      return 'valid for current revision'
    case 'superseded':
      return 'valid but superseded'
    case 'unversioned':
      return 'unversioned evidence'
    case 'mismatch':
      return 'revision mismatch'
    default:
      return 'no revision evidence'
  }
}

function revisionSummaryForTarget(target: RevisionEvidenceTarget | null | undefined, sourceLabel: string): {
  status: RevisionEvidenceStatus
  label: string
  detail: string
} {
  if (!target) {
    return { status: 'missing', label: revisionEvidenceLabel('missing'), detail: `No ${sourceLabel} is selected.` }
  }
  const current = currentSavedRevision.value
  const targetRevisionArtifactId = target.definition_revision_artifact_id ?? null
  const targetRevisionNumber = target.definition_revision_number ?? null
  if (!current) {
    return { status: 'unversioned', label: revisionEvidenceLabel('unversioned'), detail: 'No current Developer Revision is saved yet.' }
  }
  if (!targetRevisionArtifactId && targetRevisionNumber == null) {
    return { status: 'unversioned', label: revisionEvidenceLabel('unversioned'), detail: `This ${sourceLabel} does not record a Developer Revision id or number.` }
  }
  if (
    targetRevisionArtifactId === current.revision_artifact_id
    || targetRevisionNumber === current.revision_number
  ) {
    return { status: 'current', label: revisionEvidenceLabel('current'), detail: `Targets Developer Revision ${current.revision_number}.` }
  }
  if (generationAlignment.value.status === 'stale') {
    return {
      status: 'mismatch',
      label: revisionEvidenceLabel('mismatch'),
      detail: `Targets Developer Revision ${targetRevisionNumber ?? 'unknown'}, while current is ${current.revision_number}. Contract signatures differ.`,
    }
  }
  return {
    status: 'superseded',
    label: revisionEvidenceLabel('superseded'),
    detail: `Targets Developer Revision ${targetRevisionNumber ?? 'unknown'}, while current is ${current.revision_number}.`,
  }
}

function revisionSummaryForRun(run: DeveloperGenerationRunData | null | undefined) {
  return revisionSummaryForTarget(run, 'generation run')
}

const generationRevisionEvidence = computed(() => revisionSummaryForRun(latestGenerationRun.value))
const evaluationRevisionEvidence = computed(() => {
  if (!latestEvaluation.value) {
    return { status: 'missing' as const, label: revisionEvidenceLabel('missing'), detail: 'No evaluation evidence is selected.' }
  }
  const envelope = latestEvaluationEvidenceEnvelope.value as EvaluationEvidenceEnvelope | null
  if (envelope?.definition_revision_artifact_id || envelope?.definition_revision_number != null) {
    return revisionSummaryForTarget(envelope, 'evaluation evidence')
  }
  if (!latestEvaluationGenerationRunArtifactId.value) {
    return { status: 'unversioned' as const, label: revisionEvidenceLabel('unversioned'), detail: 'This evaluation does not record a generation run id.' }
  }
  return revisionSummaryForRun(latestGenerationRun.value)
})
const pmReviewRevisionEvidence = computed(() => {
  if (!traceabilityData.value?.pm_reviewed_at || traceabilityData.value.pm_review_status === 'pending') {
    return { status: 'missing' as const, label: revisionEvidenceLabel('missing'), detail: 'No PM review evidence is selected.' }
  }
  if (
    traceabilityData.value.pm_review_definition_revision_artifact_id
    || traceabilityData.value.pm_review_definition_revision_number != null
  ) {
    return revisionSummaryForTarget({
      definition_revision_artifact_id: traceabilityData.value.pm_review_definition_revision_artifact_id,
      definition_revision_number: traceabilityData.value.pm_review_definition_revision_number,
    }, 'PM review')
  }
  return revisionSummaryForRun(latestGenerationRun.value)
})

const contractEvidence = computed(() => {
  if (!compiledContractIdentity.value?.signature) {
    return {
      status: 'missing' as EvidenceStatus,
      label: statusLabel('missing'),
      detail: 'No saved revision identity exists yet. Save Developer Definition before treating verification as evidence.',
    }
  }
  return {
    status: 'ready' as EvidenceStatus,
    label: statusLabel('ready'),
    detail: 'Verification is anchored to a saved revision identity and can be compared against saved generation and evaluation evidence.',
  }
})

const generationEvidence = computed(() =>
  evidenceStatusFromAlignment(
    generationAlignment.value,
    Boolean(latestGenerationRun.value),
    'No saved generation run is recorded against the current project yet.',
  ),
)

const evaluationEvidence = computed(() =>
  evidenceStatusFromAlignment(
    resolveCompiledContractAlignment(compiledContractIdentity.value as any, latestEvaluationContractIdentity.value as any),
    Boolean(latestEvaluation.value),
    'No saved evaluation evidence is recorded against the current project yet.',
  ),
)

const pmReviewEvidence = computed(() => {
  const review = traceabilityData.value
  if (!review?.pm_reviewed_at || review.pm_review_status === 'pending') {
    return {
      status: 'missing' as EvidenceStatus,
      label: statusLabel('missing'),
      detail: 'No saved PM review is recorded against the current evidence set yet.',
    }
  }
  const contractSignature = compiledContractIdentity.value?.signature ?? null
  const generationSignature = latestGenerationRun.value?.compiled_contract_identity?.signature ?? null
  const evaluationSignature = latestEvaluationContractIdentity.value?.signature ?? null
  const observedSignature = observedServiceEvidence.value.signature || null
  if (!contractSignature || !generationSignature || !evaluationSignature || !observedSignature) {
    return {
      status: 'missing' as EvidenceStatus,
      label: statusLabel('missing'),
      detail: 'PM review exists, but the current contract, generation, evaluation, or observed-service evidence signature is missing, so evidence cannot be confirmed.',
    }
  }
  const aligned =
    review.pm_review_contract_signature === contractSignature
    && review.pm_review_generation_signature === generationSignature
    && review.pm_review_evaluation_signature === evaluationSignature
    && review.pm_review_observed_service_signature === observedSignature
  if (aligned) {
    return {
      status: 'ready' as EvidenceStatus,
      label: statusLabel('ready'),
      detail: `Saved PM review is ${pmReviewStatusLabel(review.pm_review_status)} against the current contract, generation run, evaluation evidence, and observed service evidence.`,
    }
  }
  return {
    status: 'stale' as EvidenceStatus,
    label: statusLabel('stale'),
    detail: 'A PM review exists, but it was recorded against a different contract or evidence set than the current one.',
  }
})

const evaluationEvidenceSummary = computed(() => {
  const evaluation = latestEvaluationPayload.value
  const record = latestEvaluation.value as EvaluationRecord | null
  if (!record || !evaluation) {
    return {
      status: 'missing' as EvidenceStatus,
      label: statusLabel('missing'),
      detail: 'No saved evaluation result is available yet for normalization.',
      result: 'No saved evaluation',
      glueCategories: [] as string[],
      handledByAnip: [] as string[],
      additionalWork: [] as string[],
      runtimeObservationAttached: false,
    }
  }
  const alignment = resolveCompiledContractAlignment(compiledContractIdentity.value as any, latestEvaluationContractIdentity.value as any)
  const status = alignment.status === 'aligned' ? 'ready' : alignment.status === 'stale' ? 'stale' : 'missing'
  return {
    status,
    label: statusLabel(status),
    detail: alignment.status === 'aligned'
      ? 'Saved evaluation evidence is aligned to the current compiled contract and can be reviewed by normalized category.'
      : alignment.status === 'stale'
        ? 'Saved evaluation evidence exists, but it targets an older compiled contract signature.'
        : 'Saved evaluation evidence does not record enough compiled contract identity to normalize against the current contract.',
    result: String(evaluation.result || record.result || 'Unknown'),
    glueCategories: Array.isArray(evaluation.glue_category) ? evaluation.glue_category : [],
    handledByAnip: Array.isArray(evaluation.handled_by_anip) ? evaluation.handled_by_anip : [],
    additionalWork: Array.isArray(evaluation.glue_you_will_still_write) ? evaluation.glue_you_will_still_write : [],
    runtimeObservationAttached: Boolean(evaluation.runtime_observations),
  }
})

const observedServiceEvidence = computed(() => {
  const definition = (developerDefinitionArtifact.value?.data as any) ?? null
  return resolveObservedServiceEvidence({
    definition,
    currentContractIdentity: compiledContractIdentity.value as any,
    generationRun: latestGenerationRun.value as any,
    generationRunArtifactId: selectedGenerationRunArtifact.value?.id ?? null,
    observedArtifacts: observedServiceArtifacts.value,
    evaluationObservedEvidence: latestEvaluationObservedServiceEvidence.value as any,
    evaluationSnapshot: latestEvaluationServiceMetadata.value as any,
  })
})

const evidenceCards = computed(() => [
  {
    key: 'contract',
    title: 'Compiled Contract',
    status: contractEvidence.value.status,
    label: contractEvidence.value.label,
    detail: contractEvidence.value.detail,
    signature: compiledContractIdentity.value?.signature ?? 'Not saved yet',
    secondary: compiledContractIdentity.value?.artifact_name ?? null,
    revisionLabel: currentSavedRevision.value
      ? `current Dev r${currentSavedRevision.value.revision_number}`
      : revisionEvidenceLabel('unversioned'),
    revisionStatus: currentSavedRevision.value ? 'current' : 'unversioned',
    revisionDetail: currentSavedRevision.value?.revision_artifact_id ?? 'No saved Developer Revision metadata recorded.',
  },
  {
    key: 'generation',
    title: 'Generation Evidence',
    status: generationEvidence.value.status,
    label: generationEvidence.value.label,
    detail: generationEvidence.value.detail,
    signature: latestGenerationRun.value?.compiled_contract_identity?.signature ?? 'No generation signature',
    secondary: latestGenerationRun.value
      ? `${formatStudioTimestamp(latestGenerationRun.value.generated_at)} · ${selectedGenerationRunArtifact.value?.id || 'No artifact id'} · ${formatGenerationDependencySource(latestGenerationRun.value.generator_inputs.dependency_source)}`
      : null,
    revisionLabel: generationRevisionEvidence.value.label,
    revisionStatus: generationRevisionEvidence.value.status,
    revisionDetail: generationRevisionEvidence.value.detail,
  },
  {
    key: 'evaluation',
    title: 'Evaluation Evidence',
    status: evaluationEvidence.value.status,
    label: evaluationEvidence.value.label,
    detail: evaluationEvidence.value.detail,
    signature: latestEvaluationContractIdentity.value?.signature ?? 'No evaluation signature',
    secondary: latestEvaluation.value
      ? `${formatStudioTimestamp(latestEvaluation.value.created_at)} · ${latestEvaluation.value.id}${latestEvaluationGenerationRunArtifactId.value ? ` · ${latestEvaluationGenerationRunArtifactId.value}` : ''}${latestEvaluationGenerationDependencySource.value ? ` · ${formatGenerationDependencySource(latestEvaluationGenerationDependencySource.value)}` : ''}`
      : null,
    revisionLabel: evaluationRevisionEvidence.value.label,
    revisionStatus: evaluationRevisionEvidence.value.status,
    revisionDetail: evaluationRevisionEvidence.value.detail,
  },
  {
    key: 'observed-services',
    title: 'Observed Service Evidence',
    status: observedServiceEvidence.value.status,
    label: observedServiceEvidence.value.label,
    detail: observedServiceEvidence.value.detail,
    signature: observedServiceEvidence.value.service,
    secondary: observedServiceEvidence.value.capabilityCount > 0
      ? `${observedServiceEvidence.value.protocol} · ${observedServiceEvidence.value.profile} · ${observedServiceEvidence.value.capabilityCount} capabilities`
      : null,
    revisionLabel: observedServiceEvidence.value.status === 'ready'
      ? generationRevisionEvidence.value.label
      : observedServiceEvidence.value.status === 'stale'
        ? revisionEvidenceLabel('mismatch')
        : revisionEvidenceLabel('missing'),
    revisionStatus: observedServiceEvidence.value.status === 'ready'
      ? generationRevisionEvidence.value.status
      : observedServiceEvidence.value.status === 'stale'
        ? 'mismatch'
        : 'missing',
    revisionDetail: observedServiceEvidence.value.generationRunArtifactId
      ? generationRevisionEvidence.value.detail
      : 'Observed service evidence is not tied to a selected generation run.',
  },
  {
    key: 'pm-review',
    title: 'PM Review Evidence',
    status: pmReviewEvidence.value.status,
    label: pmReviewEvidence.value.label,
    detail: pmReviewEvidence.value.detail,
    signature: traceabilityData.value?.pm_review_contract_signature ?? 'No PM review signature',
    secondary: traceabilityData.value?.pm_reviewed_at
      ? `${formatStudioTimestamp(traceabilityData.value.pm_reviewed_at)} · ${pmReviewStatusLabel(traceabilityData.value.pm_review_status)}`
      : 'No saved PM review',
    revisionLabel: pmReviewRevisionEvidence.value.label,
    revisionStatus: pmReviewRevisionEvidence.value.status,
    revisionDetail: pmReviewRevisionEvidence.value.detail,
  },
])

function formatGenerationField(value: string | undefined | null) {
  return developerLabel(value || 'not_recorded')
}

function formatGenerationDependencySource(value: string | null | undefined) {
  if (value === 'local') return 'Local workspace proof'
  if (value === 'registry') return 'Portable registry export'
  return 'Not recorded'
}

async function selectGenerationRun(artifactId: string) {
  const nextQuery = { ...route.query }
  if (artifactId) nextQuery.generationRun = artifactId
  else delete nextQuery.generationRun
  await router.replace({ query: nextQuery })
}

async function importExternalCliResult() {
  if (readOnlyMode.value) {
    externalCliImportError.value = readOnlyReason.value
    return
  }
  if (!project.value) return
  externalCliImportRunning.value = true
  externalCliImportError.value = null
  externalCliImportSummary.value = null
  try {
    const rawResult = parseExternalCliResult(externalCliImportText.value)
    const summary = summarizeExternalCliResult(rawResult, externalCliPublicationContext.value)
    const importedAt = new Date().toISOString()
    await createPmArtifact(project.value.id, {
      id: `${project.value.id}-external-cli-provenance-${Date.now()}`,
      title: `External CLI Provenance ${summary.packageLabel}`,
      data: {
        artifact_type: 'external_cli_provenance_result',
        imported_at: importedAt,
        source_tool: summary.sourceTool,
        raw_result: rawResult,
        summary,
        reconciled_against_publication_artifact_id: summary.matchedPublicationArtifactId,
      } satisfies ExternalCliProvenanceArtifactData,
    })
    externalCliImportSummary.value = summary
    externalCliImportText.value = ''
    await loadProject(project.value.id)
  } catch (err) {
    externalCliImportError.value = err instanceof Error ? err.message : String(err)
  } finally {
    externalCliImportRunning.value = false
  }
}

async function runGoVerifierForLocalPublication() {
  if (readOnlyMode.value) {
    goVerifierError.value = readOnlyReason.value
    return
  }
  if (!project.value || !publicationLineage.value.localPublicationId) return
  goVerifierRunning.value = true
  goVerifierError.value = null
  goVerifierSummary.value = null
  try {
    const result = await verifyLocalRegistryPackageWithGo(project.value.id, publicationLineage.value.localPublicationId)
    goVerifierSummary.value = result.summary as ExternalCliProvenanceSummary
    await loadProject(project.value.id)
  } catch (err) {
    goVerifierError.value = err instanceof Error ? err.message : String(err)
  } finally {
    goVerifierRunning.value = false
  }
}

async function runGoVerifierForRegistryPublication() {
  if (readOnlyMode.value) {
    registryGoVerifierError.value = readOnlyReason.value
    return
  }
  const context = externalCliPublicationContext.value
  if (!project.value || !context?.packageId || !context.packageVersion) return
  registryGoVerifierRunning.value = true
  registryGoVerifierError.value = null
  registryGoVerifierSummary.value = null
  try {
    const result = await verifyRegistryPackageWithGo(project.value.id, {
      package_id: context.packageId,
      package_version: context.packageVersion,
      publication_artifact_id: latestRegistryPublicationArtifact.value?.id,
    })
    registryGoVerifierSummary.value = result.summary as ExternalCliProvenanceSummary
    await loadProject(project.value.id)
  } catch (err) {
    registryGoVerifierError.value = err instanceof Error ? err.message : String(err)
  } finally {
    registryGoVerifierRunning.value = false
  }
}

async function ensureLoaded() {
  if (!projectId.value) return
  if (projectStore.activeProject?.id === projectId.value) return
  await loadProject(projectId.value)
}

onMounted(ensureLoaded)
watch(projectId, ensureLoaded)

const readinessRows = computed(() => [
  { label: 'Requirements', value: projectStore.artifacts.requirements.length },
  { label: 'Scenarios', value: projectStore.artifacts.scenarios.length },
  { label: 'Service Design', value: projectStore.artifacts.shapes.length },
  { label: 'Observed Services', value: projectStore.artifacts.serviceMetadata.length },
  { label: 'Evaluations', value: projectStore.artifacts.evaluations.length },
])

function openEvaluation() {
  const pid = projectId.value
  if (latestEvaluation.value) {
    router.push(`/design/projects/${pid}/evaluations/${latestEvaluation.value.id}`)
    return
  }
  if (projectStore.artifacts.requirements.length === 0) {
    router.push(`/design/projects/${pid}/requirements`)
    return
  }
  if (projectStore.artifacts.scenarios.length === 0) {
    router.push(`/design/projects/${pid}/scenarios`)
    return
  }
  if (projectStore.artifacts.shapes.length === 0) {
    router.push(`/design/projects/${pid}/shapes`)
    return
  }
  if (projectStore.activeScenarioId) {
    router.push(`/design/projects/${pid}/scenarios/${projectStore.activeScenarioId}`)
    return
  }
  router.push(`/design/projects/${pid}/pm`)
}
</script>

<template>
  <div class="project-verification">
    <template v-if="project">
      <section class="page-header">
        <div class="page-kicker">Verification</div>
        <h1>Verification Overview</h1>
        <p>
          Verification is the evidence lane for the project. Use it to inspect observed services, review runtime evidence,
          and see where current Product and Developer Design still show drift or missing proof.
        </p>
      </section>

      <div v-if="readOnlyMode" class="readonly-banner">
        <strong>Read-only showcase mode</strong>
        <span>{{ readOnlyReason }} Evidence imports and verifier runs are disabled in the hosted preview.</span>
      </div>

      <section class="verification-grid">
        <article class="panel panel-wide">
          <div class="panel-header">
            <h2>Verification Overview</h2>
            <span class="status-chip" :class="{ ready: !!latestEvaluation }">
              {{ latestEvaluation ? latestEvaluation.result : 'Incomplete' }}
            </span>
          </div>
          <p class="panel-copy">
            The design exists, but the test context is incomplete until requirements, scenarios, service shape, and
            observed implementation are checked together.
          </p>
          <div class="stats-grid">
            <div v-for="row in readinessRows" :key="row.label" class="stat-card">
              <div class="stat-label">{{ row.label }}</div>
              <div class="stat-value">{{ row.value }}</div>
            </div>
          </div>
        </article>

        <article class="panel panel-wide">
          <div class="panel-header">
            <h2>Evidence Target</h2>
            <span class="status-chip" :class="{ ready: !!selectedGenerationRunArtifact }">
              {{ selectedGenerationRunArtifact ? 'Generation run selected' : 'No run selected' }}
            </span>
          </div>
          <p class="panel-copy">
            Verification now targets one saved generation run at a time. Evaluation evidence and observed runtime proof are matched to the selected run instead of silently following the latest generation.
          </p>
          <template v-if="generationRunArtifacts.length">
            <div class="run-target-list">
              <button
                v-for="artifact in generationRunArtifacts"
                :key="artifact.id"
                class="run-target-card"
                :class="{ selected: artifact.id === selectedGenerationRunArtifactId }"
                type="button"
                @click="selectGenerationRun(artifact.id)"
              >
                <strong>{{ artifact.id }}</strong>
                <span>{{ formatStudioTimestamp(artifact.updated_at || artifact.created_at) }}</span>
                <span>
                  {{
                    formatGenerationDependencySource(
                      (artifact.data as DeveloperGenerationRunData | undefined)?.generator_inputs?.dependency_source ?? null,
                    )
                  }}
                </span>
              </button>
            </div>
            <div class="button-stack">
              <p class="panel-copy">
                Studio local runtime proof is retired. Use the external verifier against the published Registry package or package bundle, then import the verifier result here.
              </p>
            </div>
          </template>
          <p v-else class="panel-copy">No saved generation runs exist yet for this project.</p>
        </article>

        <article class="panel panel-wide">
          <div class="panel-header"><h2>Evidence Status</h2></div>
          <p class="panel-copy">
            Verification is only trustworthy when contract, generation, evaluation, and PM review all point at the same saved revision signature.
          </p>
          <p class="panel-copy why-copy">
            Why this matters: this page should answer whether the package is safe to trust, not force reviewers to compare hashes manually. Technical signatures stay visible as secondary evidence.
          </p>
          <div class="evidence-grid">
            <div v-for="item in evidenceCards" :key="item.key" class="evidence-card">
              <div class="evidence-card-header">
                <h3>{{ item.title }}</h3>
                <span class="status-chip" :class="`status-${item.status}`">{{ item.label }}</span>
              </div>
              <div class="evidence-signature">{{ item.signature }}</div>
              <div v-if="item.secondary" class="evidence-secondary">{{ item.secondary }}</div>
              <div class="revision-evidence-line">
                <span class="revision-evidence-chip" :class="`revision-evidence-${item.revisionStatus}`">
                  {{ item.revisionLabel }}
                </span>
                <span>{{ item.revisionDetail }}</span>
              </div>
              <p class="panel-copy">{{ item.detail }}</p>
            </div>
          </div>
        </article>

        <article class="panel panel-wide">
          <div class="panel-header">
            <h2>Agent Consumption Readiness</h2>
            <span class="status-chip" :class="`readiness-${agentReadinessReport.status}`">
              {{ readinessStatusLabel(agentReadinessReport.status) }}
            </span>
          </div>
          <p class="panel-copy">
            This is the saved deterministic report that should gate generation and Registry publication. It turns app-glue needs and semantic gaps into explicit implementation work instead of late benchmark surprises.
          </p>
          <p class="panel-copy why-copy">
            Why this matters: readiness findings tell reviewers where ANIP-native behavior ends and app-specific glue or contract clarification begins.
          </p>
          <div class="snapshot-grid">
            <div class="snapshot-row"><span>Score</span><strong>{{ agentReadinessReport.score }}</strong></div>
            <div class="snapshot-row"><span>Blockers</span><strong>{{ agentReadinessReport.summary.blockers }}</strong></div>
            <div class="snapshot-row"><span>Warnings</span><strong>{{ agentReadinessReport.summary.warnings }}</strong></div>
            <div class="snapshot-row"><span>Required App Glue</span><strong>{{ agentReadinessReport.summary.required_app_glue }}</strong></div>
            <div class="snapshot-row"><span>Simulator Probes</span><strong>{{ agentReadinessReport.summary.probes }}</strong></div>
          </div>
          <div v-if="agentReadinessReport.findings.length" class="readiness-finding-list">
            <article v-for="finding in agentReadinessReport.findings.slice(0, 4)" :key="String(finding.id)" class="readiness-finding-card">
              <strong>{{ finding.title }}</strong>
              <p>{{ finding.recommendation }}</p>
            </article>
          </div>
          <button class="btn btn-secondary" type="button" @click="router.push(`/design/projects/${projectId}/developer/app-glue`)">
            Open Readiness Details
          </button>
        </article>

        <article class="panel">
          <div class="panel-header"><h2>Next Evaluation</h2></div>
          <p class="panel-copy">
            Choose the next evaluation context from here so runtime evidence stays tied to the active design baseline.
          </p>
          <button class="btn btn-primary btn-full" @click="openEvaluation">Open Evaluation Flow</button>
        </article>

        <article class="panel">
          <div class="panel-header">
            <h2>Published Lineage</h2>
            <span class="status-chip" :class="`publication-${publicationLineage.status}`">
              {{ publicationLineage.label }}
            </span>
          </div>
          <p class="panel-copy panel-copy-spaced">{{ publicationLineage.detail }}</p>
          <div class="snapshot-grid">
            <div class="snapshot-row"><span>Package</span><strong class="wrap-value">{{ publicationLineage.packageLabel }}</strong></div>
            <div class="snapshot-row"><span>Authority</span><strong>{{ publicationLineage.authority }}</strong></div>
            <div class="snapshot-row"><span>Product</span><strong class="wrap-value">{{ publicationLineage.productLabel }}</strong></div>
            <div class="snapshot-row"><span>Developer</span><strong class="wrap-value">{{ publicationLineage.developerLabel }}</strong></div>
            <div class="snapshot-row"><span>Receipt Authority</span><strong>{{ publicationLineage.receiptAuthority }}</strong></div>
            <div class="snapshot-row"><span>Receipt Status</span><strong>{{ publicationLineage.receiptStatus }}</strong></div>
            <div class="snapshot-row"><span>Receipt</span><strong class="wrap-value">{{ publicationLineage.receiptSignature }}</strong></div>
            <div class="snapshot-row"><span>Published</span><strong>{{ publicationLineage.publishedAt ? formatStudioTimestamp(publicationLineage.publishedAt) : 'Not recorded' }}</strong></div>
            <div class="snapshot-row"><span>PM Approval</span><strong>{{ approvalLineage.label }}</strong></div>
            <div class="snapshot-row"><span>Approved Product</span><strong class="wrap-value">{{ approvalLineage.productLabel }}</strong></div>
            <div class="snapshot-row"><span>Approved Developer</span><strong class="wrap-value">{{ approvalLineage.developerLabel }}</strong></div>
            <div class="snapshot-row"><span>Release</span><strong class="wrap-value">{{ latestRelease ? `${latestRelease.package_id}@${latestRelease.package_version}` : 'Not released' }}</strong></div>
            <div v-if="latestRelease" class="snapshot-row"><span>Released</span><strong>{{ formatStudioTimestamp(String(latestRelease.released_at || latestReleaseArtifact?.created_at)) }}</strong></div>
            <div v-if="publicationLineage.localPublicationId" class="snapshot-row"><span>Local ID</span><strong class="wrap-value">{{ publicationLineage.localPublicationId }}</strong></div>
            <div v-if="publicationLineage.localVerificationStatus" class="snapshot-row"><span>Local Verification</span><strong>{{ publicationLineage.localVerificationStatus }}</strong></div>
          </div>
          <p class="panel-copy">{{ approvalLineage.detail }}</p>
          <button class="btn btn-secondary" @click="router.push(`/design/projects/${projectId}/developer/definition`)">Open Publication Flow</button>
        </article>

        <article class="panel panel-wide">
          <div class="panel-header">
            <h2>External CLI Provenance</h2>
            <span
              v-if="externalCliImportSummary"
              class="status-chip"
              :class="`cli-${externalCliImportSummary.status}`"
            >
              {{ externalCliImportSummary.label }}
            </span>
          </div>
          <p class="panel-copy">
            Paste JSON output from <code>anip-verify</code> or <code>anip-generate</code>. Studio will save it as evidence and reconcile package, receipt, and Product/Developer revision lineage against the latest publication.
          </p>
          <textarea
            v-model="externalCliImportText"
            class="cli-import-textarea"
            rows="8"
            spellcheck="false"
            :disabled="readOnlyMode"
            placeholder='{"status":"ok","package_id":"...","package_version":"...","receipt_status":"verified"}'
          />
          <div class="button-stack">
            <button
              v-if="publicationLineage.localPublicationId"
              class="btn btn-primary"
              type="button"
              :disabled="readOnlyMode || goVerifierRunning"
              @click="runGoVerifierForLocalPublication"
            >
              {{ goVerifierRunning ? 'Running verifier…' : 'Run Verifier For Local Publication' }}
            </button>
            <p v-if="goVerifierError" class="panel-copy error-copy">{{ goVerifierError }}</p>
            <p v-else-if="goVerifierSummary" class="panel-copy">
              {{ goVerifierSummary.detail }}
            </p>
            <button
              v-if="publicationLineage.authority === 'remote-registry'"
              class="btn btn-primary"
              type="button"
              :disabled="readOnlyMode || registryGoVerifierRunning"
              @click="runGoVerifierForRegistryPublication"
            >
              {{ registryGoVerifierRunning ? 'Running Registry verifier…' : 'Run Verifier For Registry Publication' }}
            </button>
            <p v-if="registryGoVerifierError" class="panel-copy error-copy">{{ registryGoVerifierError }}</p>
            <p v-else-if="registryGoVerifierSummary" class="panel-copy">
              {{ registryGoVerifierSummary.detail }}
            </p>
            <button
              class="btn btn-secondary"
              type="button"
              :disabled="readOnlyMode || externalCliImportRunning || !externalCliImportText.trim()"
              @click="importExternalCliResult"
            >
              {{ externalCliImportRunning ? 'Importing…' : 'Import CLI Result' }}
            </button>
            <p v-if="externalCliImportError" class="panel-copy error-copy">{{ externalCliImportError }}</p>
            <p v-else-if="externalCliImportSummary" class="panel-copy">
              {{ externalCliImportSummary.detail }}
            </p>
          </div>
          <div v-if="externalCliProvenanceRows.length" class="cli-history-list">
            <article v-for="row in externalCliProvenanceRows" :key="row.artifactId" class="cli-history-card">
              <div class="cli-history-header">
                <strong>{{ row.summary.packageLabel }}</strong>
                <span class="status-chip" :class="`cli-${row.summary.status}`">{{ row.summary.label }}</span>
              </div>
              <div class="snapshot-grid">
                <div class="snapshot-row"><span>Imported</span><strong>{{ formatStudioTimestamp(row.importedAt) }}</strong></div>
                <div class="snapshot-row"><span>Tool</span><strong>{{ row.summary.sourceTool }}</strong></div>
                <div class="snapshot-row"><span>Receipt Status</span><strong>{{ row.summary.receiptStatus }}</strong></div>
                <div v-if="row.summary.registryTrustPostureLabel" class="snapshot-row"><span>Registry Trust</span><strong>{{ row.summary.registryTrustPostureLabel }}</strong></div>
                <div v-if="row.summary.registrySigningMode" class="snapshot-row"><span>Registry Signing</span><strong>{{ row.summary.registrySigningMode }}</strong></div>
                <div v-if="row.summary.registryActiveKeyID" class="snapshot-row"><span>Active Key</span><strong class="wrap-value">{{ row.summary.registryActiveKeyID }}</strong></div>
                <div class="snapshot-row"><span>Product</span><strong class="wrap-value">{{ row.summary.productRevisionLabel }}</strong></div>
                <div class="snapshot-row"><span>Developer</span><strong class="wrap-value">{{ row.summary.developerRevisionLabel }}</strong></div>
                <div class="snapshot-row"><span>Receipt</span><strong class="wrap-value">{{ row.summary.receiptSignature }}</strong></div>
              </div>
              <p v-if="row.summary.registryTrustPostureDetail" class="panel-copy">{{ row.summary.registryTrustPostureDetail }}</p>
              <p class="panel-copy">{{ row.summary.detail }}</p>
            </article>
          </div>
        </article>

        <article class="panel">
          <div class="panel-header"><h2>Observed Services</h2></div>
          <p class="panel-copy panel-copy-spaced">{{ observedServiceEvidence.detail }}</p>
          <div class="snapshot-grid">
            <div class="snapshot-row"><span>Artifacts</span><strong>{{ projectStore.artifacts.serviceMetadata.length }}</strong></div>
            <div class="snapshot-row"><span>Service</span><strong>{{ observedServiceEvidence.service }}</strong></div>
            <div class="snapshot-row"><span>Protocol</span><strong>{{ observedServiceEvidence.protocol }}</strong></div>
            <div class="snapshot-row"><span>Profile</span><strong>{{ observedServiceEvidence.profile }}</strong></div>
            <div class="snapshot-row"><span>Capabilities</span><strong>{{ observedServiceEvidence.capabilityCount }}</strong></div>
            <div class="snapshot-row"><span>Source</span><strong class="wrap-value">{{ observedServiceEvidence.source }}</strong></div>
            <div class="snapshot-row"><span>Generation Run</span><strong class="wrap-value">{{ observedServiceEvidence.generationRunArtifactId || 'Not recorded' }}</strong></div>
            <div class="snapshot-row"><span>Dependency Mode</span><strong>{{ formatGenerationDependencySource(observedServiceEvidence.generationDependencySource) }}</strong></div>
            <div class="snapshot-row"><span>Expected Services</span><strong class="wrap-value">{{ observedServiceEvidence.expectedServices.length ? observedServiceEvidence.expectedServices.join(', ') : 'Not defined' }}</strong></div>
            <div class="snapshot-row"><span>Expected Protocols</span><strong class="wrap-value">{{ observedServiceEvidence.expectedProtocols.length ? observedServiceEvidence.expectedProtocols.join(', ') : 'Not defined' }}</strong></div>
          </div>
          <div v-if="observedServiceEvidence.alignedCapabilities.length || observedServiceEvidence.missingCapabilities.length || observedServiceEvidence.extraCapabilities.length" class="evidence-normalized">
            <div class="evidence-normalized-header">
              <h3>Observed Capability Alignment</h3>
              <span class="status-chip" :class="`status-${observedServiceEvidence.status}`">{{ observedServiceEvidence.label }}</span>
            </div>
            <div class="snapshot-grid">
              <div class="snapshot-row"><span>Aligned</span><strong class="wrap-value">{{ observedServiceEvidence.alignedCapabilities.length ? observedServiceEvidence.alignedCapabilities.join(', ') : 'None' }}</strong></div>
              <div class="snapshot-row"><span>Missing</span><strong class="wrap-value">{{ observedServiceEvidence.missingCapabilities.length ? observedServiceEvidence.missingCapabilities.join(', ') : 'None' }}</strong></div>
              <div class="snapshot-row"><span>Broader Than Intended</span><strong class="wrap-value">{{ observedServiceEvidence.extraCapabilities.length ? observedServiceEvidence.extraCapabilities.join(', ') : 'None' }}</strong></div>
            </div>
          </div>
          <div class="button-stack">
            <button class="btn btn-secondary" @click="router.push('/inspect/discovery')">Open Discovery</button>
            <button class="btn btn-secondary" @click="router.push('/inspect/audit')">Open Audit</button>
            <button class="btn btn-secondary" @click="router.push('/inspect/approvals')">Open Approvals</button>
          </div>
        </article>

        <article class="panel">
          <div class="panel-header"><h2>Drift &amp; Gaps</h2></div>
          <p class="panel-copy panel-copy-spaced">
            {{ traceabilityArtifact ? `${coverageSummary.addressed} of ${coverageSummary.total} active Product Design items are marked addressed. Use this to spot current drift before looking at deeper runtime evidence.` : 'No developer coverage record has been saved yet.' }}
          </p>
          <div v-if="traceabilityArtifact" class="button-stack">
            <div class="snapshot-row"><span>Developer</span><strong>{{ developerStatusLabel((traceabilityArtifact.data?.developer_status || 'not_started') as any) }}</strong></div>
            <div class="snapshot-row"><span>PM Review</span><strong>{{ pmReviewStatusLabel((traceabilityArtifact.data?.pm_review_status || 'pending') as any) }}</strong></div>
          </div>
          <button class="btn btn-secondary" @click="router.push(`/design/projects/${projectId}/developer/gaps`)">Open Consistency Gaps</button>
        </article>

        <article class="panel">
          <div class="panel-header">
            <h2>Contract Evidence</h2>
            <span class="status-chip" :class="`status-${contractEvidence.status}`">{{ contractEvidence.label }}</span>
          </div>
          <p class="panel-copy panel-copy-spaced">
            Verification should stay tied to the saved revision identity, not only to the current page state.
          </p>
          <div v-if="compiledContractIdentity" class="button-stack">
            <div class="snapshot-row"><span>Artifact</span><strong>{{ compiledContractIdentity.artifact_name }}</strong></div>
            <div class="snapshot-row"><span>Signature</span><strong class="wrap-value">{{ compiledContractIdentity.signature || 'Not available' }}</strong></div>
            <div class="snapshot-row"><span>Algorithm</span><strong>{{ compiledContractIdentity.signature_algorithm }}</strong></div>
            <div class="snapshot-row"><span>Generated</span><strong>{{ formatStudioTimestamp(compiledContractIdentity.generated_at) }}</strong></div>
          </div>
          <p v-else class="panel-copy panel-copy-spaced">No saved revision identity is available yet. Save Developer Definition first.</p>
          <button class="btn btn-secondary" @click="router.push(`/design/projects/${projectId}/developer/definition`)">Open Developer Definition</button>
        </article>

        <article class="panel panel-wide">
          <div class="panel-header">
            <h2>Evaluation Evidence</h2>
            <span class="status-chip" :class="`status-${evaluationEvidence.status}`">{{ evaluationEvidence.label }}</span>
          </div>
          <template v-if="latestEvaluation">
            <div class="snapshot-grid">
              <div class="snapshot-row"><span>Created</span><strong>{{ formatStudioTimestamp(latestEvaluation.created_at) }}</strong></div>
              <div class="snapshot-row"><span>Scenario</span><strong>{{ latestEvaluation.scenario_id }}</strong></div>
              <div class="snapshot-row"><span>Requirements</span><strong>{{ latestEvaluation.requirements_id }}</strong></div>
              <div class="snapshot-row"><span>Shape</span><strong>{{ latestEvaluation.shape_id || latestEvaluation.proposal_id || 'not selected' }}</strong></div>
              <div class="snapshot-row"><span>Contract Artifact</span><strong>{{ latestEvaluationContractIdentity?.artifact_name || 'Not recorded' }}</strong></div>
              <div class="snapshot-row"><span>Contract Signature</span><strong class="wrap-value">{{ latestEvaluationContractIdentity?.signature || 'Not recorded' }}</strong></div>
              <div class="snapshot-row"><span>Generation Run</span><strong class="wrap-value">{{ latestEvaluationGenerationRunArtifactId || 'Not recorded' }}</strong></div>
              <div class="snapshot-row"><span>Dependency Mode</span><strong>{{ formatGenerationDependencySource(latestEvaluationGenerationDependencySource) }}</strong></div>
              <div class="snapshot-row"><span>Evidence Envelope</span><strong>{{ latestEvaluationEvidenceEnvelope ? 'Present' : 'Not recorded' }}</strong></div>
            </div>
            <div class="evidence-normalized">
              <div class="evidence-normalized-header">
                <h3>Normalized Evaluation Evidence</h3>
                <span class="status-chip" :class="`status-${evaluationEvidenceSummary.status}`">{{ evaluationEvidenceSummary.label }}</span>
              </div>
              <p class="panel-copy">{{ evaluationEvidenceSummary.detail }}</p>
              <div class="snapshot-grid">
                <div class="snapshot-row"><span>Result</span><strong>{{ evaluationEvidenceSummary.result }}</strong></div>
                <div class="snapshot-row"><span>Handled by ANIP</span><strong>{{ evaluationEvidenceSummary.handledByAnip.length }}</strong></div>
                <div class="snapshot-row"><span>Additional Work</span><strong>{{ evaluationEvidenceSummary.additionalWork.length }}</strong></div>
                <div class="snapshot-row"><span>Runtime Observation</span><strong>{{ evaluationEvidenceSummary.runtimeObservationAttached ? 'Attached' : 'Not attached' }}</strong></div>
              </div>
              <div v-if="evaluationEvidenceSummary.glueCategories.length" class="pill-row">
                <span v-for="category in evaluationEvidenceSummary.glueCategories" :key="category" class="evidence-pill">
                  {{ category }}
                </span>
              </div>
            </div>
          </template>
          <p v-else class="panel-copy">No evaluation captured yet. Start from the evaluation flow once the active context is ready.</p>
        </article>

        <article class="panel">
          <div class="panel-header">
            <h2>PM Review Evidence</h2>
            <span class="status-chip" :class="`status-${pmReviewEvidence.status}`">{{ pmReviewEvidence.label }}</span>
          </div>
          <p class="panel-copy panel-copy-spaced">{{ pmReviewEvidence.detail }}</p>
          <div v-if="traceabilityData?.pm_reviewed_at" class="snapshot-grid">
            <div class="snapshot-row"><span>Reviewed</span><strong>{{ formatStudioTimestamp(traceabilityData.pm_reviewed_at) }}</strong></div>
            <div class="snapshot-row"><span>Review State</span><strong>{{ pmReviewStatusLabel(traceabilityData.pm_review_status) }}</strong></div>
            <div class="snapshot-row"><span>Contract Signature</span><strong class="wrap-value">{{ traceabilityData.pm_review_contract_signature || 'Not recorded' }}</strong></div>
            <div class="snapshot-row"><span>Generation Signature</span><strong class="wrap-value">{{ traceabilityData.pm_review_generation_signature || 'Not recorded' }}</strong></div>
            <div class="snapshot-row"><span>Evaluation Signature</span><strong class="wrap-value">{{ traceabilityData.pm_review_evaluation_signature || 'Not recorded' }}</strong></div>
            <div class="snapshot-row"><span>Observed Service Signature</span><strong class="wrap-value">{{ traceabilityData.pm_review_observed_service_signature || 'Not recorded' }}</strong></div>
            <div class="snapshot-row"><span>Observed Service Artifact</span><strong class="wrap-value">{{ traceabilityData.pm_review_observed_service_artifact_id || 'Not recorded' }}</strong></div>
          </div>
          <button class="btn btn-secondary" @click="router.push(`/design/projects/${projectId}/pm/review`)">Open PM Review</button>
        </article>

        <article class="panel panel-wide">
          <div class="panel-header">
            <h2>Generation Evidence</h2>
            <span class="status-chip" :class="`status-${generationEvidence.status}`">
              {{ generationEvidence.label }}
            </span>
          </div>
          <template v-if="latestGenerationRun">
            <div class="snapshot-grid">
              <div class="snapshot-row"><span>Generated</span><strong>{{ formatStudioTimestamp(latestGenerationRun.generated_at) }}</strong></div>
              <div class="snapshot-row"><span>Run Artifact</span><strong class="wrap-value">{{ selectedGenerationRunArtifact?.id || 'Not recorded' }}</strong></div>
              <div class="snapshot-row"><span>Contract Artifact</span><strong>{{ latestGenerationRun.compiled_contract_identity?.artifact_name || 'Not recorded' }}</strong></div>
              <div class="snapshot-row"><span>Contract Signature</span><strong class="wrap-value">{{ latestGenerationRun.compiled_contract_identity?.signature || 'Not recorded' }}</strong></div>
              <div class="snapshot-row"><span>Dependency Mode</span><strong>{{ formatGenerationDependencySource(latestGenerationRun.generator_inputs.dependency_source) }}</strong></div>
              <div class="snapshot-row"><span>Primary Output Mode</span><strong>{{ formatGenerationField(latestGenerationRun.generator_inputs.primary_output_mode) }}</strong></div>
              <div class="snapshot-row"><span>Runtime Target Mode</span><strong>{{ formatGenerationField(latestGenerationRun.generator_inputs.runtime_target_mode) }}</strong></div>
              <div class="snapshot-row"><span>Saved Outputs</span><strong>{{ latestGenerationRun.outputs.runtime_target.length }}</strong></div>
            </div>
            <p class="panel-copy">{{ generationEvidence.detail }}</p>
          </template>
          <p v-else class="panel-copy">No generation run has been recorded yet for the current project.</p>
        </article>
      </section>
    </template>
  </div>
</template>

<style scoped>
.project-verification {
  width: 100%;
  max-width: none;
  padding: 2rem;
}

.page-kicker {
  text-transform: uppercase;
  font-size: 12px;
  letter-spacing: 0.08em;
  color: var(--text-secondary);
}

.page-header h1 {
  margin: 0.2rem 0 0.5rem;
  font-size: 28px;
}

.page-header {
  margin-bottom: 1.35rem;
}

.page-header p,
.panel-copy {
  color: var(--text-secondary);
  line-height: 1.6;
}

.why-copy {
  color: var(--text-primary);
  background: rgba(14, 165, 233, 0.08);
  border: 1px solid rgba(125, 211, 252, 0.16);
  border-radius: 14px;
  padding: 0.75rem 0.9rem;
}

.panel-copy-spaced {
  margin-bottom: 1rem;
}

.readonly-banner {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem 0.7rem;
  align-items: center;
  margin: 0 0 1rem;
  padding: 0.85rem 1rem;
  border: 1px solid rgba(251, 191, 36, 0.34);
  border-radius: 16px;
  background: rgba(251, 191, 36, 0.1);
  color: #fde68a;
}

.readonly-banner span {
  color: var(--text-secondary);
}

.run-target-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 0.85rem;
}

.run-target-card {
  display: grid;
  gap: 0.35rem;
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  background: var(--surface-depth-card);
  color: inherit;
  padding: 0.95rem;
  text-align: left;
  cursor: pointer;
}

.run-target-card.selected {
  border-color: rgba(96, 165, 250, 0.38);
  background:
    radial-gradient(circle at top right, rgba(96, 165, 250, 0.14), transparent 38%),
    rgba(15, 23, 42, 0.4);
}

.verification-grid {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 1rem;
}

.panel {
  grid-column: span 4;
  background: var(--surface-depth-panel);
  border: 1px solid var(--surface-border-panel);
  border-radius: 18px;
  padding: 1.25rem;
}

.panel-wide {
  grid-column: span 8;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: center;
  margin-bottom: 1rem;
}

.panel-header h2 {
  margin: 0;
  font-size: 16px;
}

.status-chip {
  padding: 0.28rem 0.6rem;
  border-radius: 999px;
  font-size: 12px;
  background: rgba(148, 163, 184, 0.16);
  color: var(--text-secondary);
}

.status-chip.ready {
  background: rgba(34, 197, 94, 0.16);
}

.status-chip.status-ready {
  background: rgba(34, 197, 94, 0.16);
  color: #bbf7d0;
}

.status-chip.status-stale {
  background: rgba(251, 191, 36, 0.18);
  color: #fde68a;
}

.status-chip.status-missing {
  background: rgba(148, 163, 184, 0.18);
  color: #e2e8f0;
}

.status-chip.publication-current {
  background: rgba(34, 197, 94, 0.16);
  color: #bbf7d0;
}

.status-chip.publication-superseded {
  background: rgba(251, 191, 36, 0.18);
  color: #fde68a;
}

.status-chip.publication-mismatch {
  background: rgba(248, 113, 113, 0.18);
  color: #fecaca;
}

.status-chip.publication-unpublished {
  background: rgba(148, 163, 184, 0.18);
  color: #e2e8f0;
}

.status-chip.cli-aligned {
  background: rgba(34, 197, 94, 0.16);
  color: #bbf7d0;
}

.status-chip.cli-incomplete,
.status-chip.cli-unpublished {
  background: rgba(251, 191, 36, 0.18);
  color: #fde68a;
}

.status-chip.cli-mismatch {
  background: rgba(248, 113, 113, 0.18);
  color: #fecaca;
}

.status-chip.readiness-ready {
  background: rgba(34, 197, 94, 0.16);
  color: #bbf7d0;
}

.status-chip.readiness-needs_review {
  background: rgba(251, 191, 36, 0.18);
  color: #fde68a;
}

.status-chip.readiness-blocked {
  background: rgba(248, 113, 113, 0.18);
  color: #fecaca;
}

.readiness-finding-list {
  display: grid;
  gap: 0.65rem;
  margin: 1rem 0;
}

.readiness-finding-card {
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  padding: 0.8rem;
  background: var(--surface-depth-card);
}

.readiness-finding-card p {
  margin: 0.35rem 0 0;
  color: var(--text-secondary);
  line-height: 1.5;
}

.cli-import-textarea {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  background: var(--surface-depth-inset);
  color: var(--text-primary);
  font: 12px/1.5 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace;
  padding: 0.9rem;
  resize: vertical;
}

.cli-history-list {
  display: grid;
  gap: 0.85rem;
  margin-top: 1rem;
}

.cli-history-card {
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  background: var(--surface-depth-card);
  padding: 1rem;
}

.cli-history-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: center;
  margin-bottom: 0.8rem;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 0.8rem;
  margin-top: 1rem;
}

.stat-card {
  border-radius: 14px;
  border: 1px solid var(--surface-border-card);
  background: var(--surface-depth-card);
  padding: 0.9rem;
}

.stat-label {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-secondary);
  margin-bottom: 0.3rem;
}

.stat-value {
  font-size: 24px;
  color: var(--text-primary);
}

.evidence-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.8rem;
  margin-top: 1rem;
}

.evidence-card {
  border-radius: 14px;
  border: 1px solid var(--surface-border-card);
  background: var(--surface-depth-card);
  padding: 1rem;
}

.evidence-card-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: center;
}

.evidence-card-header h3 {
  margin: 0;
  font-size: 14px;
}

.evidence-signature {
  margin-top: 0.65rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace;
  font-size: 12px;
  color: var(--text-primary);
  word-break: break-word;
}

.evidence-secondary {
  margin-top: 0.35rem;
  color: var(--text-secondary);
  font-size: 12px;
}

.revision-evidence-line {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  align-items: center;
  margin-top: 0.65rem;
  color: var(--text-secondary);
  font-size: 12px;
}

.revision-evidence-chip {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 0.18rem 0.55rem;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.14);
  color: #e2e8f0;
  font-size: 11px;
  font-weight: 800;
  text-transform: uppercase;
}

.revision-evidence-current {
  background: rgba(34, 197, 94, 0.16);
  color: #bbf7d0;
}

.revision-evidence-superseded {
  background: rgba(251, 191, 36, 0.16);
  color: #fde68a;
}

.revision-evidence-unversioned,
.revision-evidence-missing {
  background: rgba(148, 163, 184, 0.16);
  color: #e2e8f0;
}

.revision-evidence-mismatch {
  background: rgba(248, 113, 113, 0.16);
  color: #fecaca;
}

.evidence-normalized {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid rgba(148, 163, 184, 0.14);
}

.evidence-normalized-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: center;
  margin-bottom: 0.75rem;
}

.evidence-normalized-header h3 {
  margin: 0;
  font-size: 14px;
}

.pill-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.8rem;
}

.evidence-pill {
  border-radius: 999px;
  padding: 0.3rem 0.7rem;
  font-size: 12px;
  background: rgba(99, 102, 241, 0.16);
  color: #c7d2fe;
  border: 1px solid rgba(99, 102, 241, 0.28);
}

.button-stack {
  display: flex;
  flex-direction: column;
  gap: 0.7rem;
  margin-top: 1rem;
}

.error-copy {
  color: #fca5a5;
}

.btn {
  border: 1px solid var(--surface-border-card);
  border-radius: 12px;
  padding: 0.75rem 1rem;
  font-size: 14px;
  cursor: pointer;
}

.btn-primary {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}

.btn-secondary {
  background: var(--surface-depth-card);
  color: var(--text-primary);
}

.btn-full {
  width: 100%;
  margin-top: 1rem;
}

.snapshot-grid {
  display: grid;
  gap: 0.75rem;
}

.snapshot-row {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  color: var(--text-secondary);
}

.snapshot-row strong {
  color: var(--text-primary);
}

.wrap-value {
  word-break: break-word;
}

@media (max-width: 1100px) {
  .panel,
  .panel-wide {
    grid-column: span 12;
  }

  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .evidence-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .project-verification {
    padding: 1.25rem;
  }

  .stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>
