<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  findDeveloperDefinitionArtifact,
  findDeveloperGenerationRunArtifacts,
  findLatestDeveloperGenerationRunArtifact,
  resolveEvaluationCompiledContractIdentity,
  resolveEvaluationObservedServiceEvidence,
  resolveEvaluationServiceMetadataSnapshot,
  resolveObservedServiceEvidence,
  resolveCompiledContractAlignment,
  resolveGenerationContractAlignment,
} from '../design/developer-definition'
import { createPmArtifact, updatePmArtifact } from '../design/project-api'
import { loadProject, projectStore } from '../design/project-store'
import type { DeveloperDefinitionData, DeveloperGenerationRunData, EvaluationEvidenceEnvelope, PmReviewState, TraceabilityRecordData } from '../design/project-types'
import { formatStudioTimestamp } from '../design/time'
import {
  DESIGN_TRACEABILITY_ARTIFACT_TYPE,
  buildTraceabilityRecord,
  coverageStatusLabel,
  developerStatusLabel,
  findTraceabilityArtifact,
  pmReviewStatusLabel,
  summarizeCoverage,
  traceabilityArtifactId,
} from '../design/traceability'

const route = useRoute()
const router = useRouter()

const projectId = computed(() => route.params.projectId as string)
const project = computed(() => projectStore.activeProject)
const requirements = computed(() => projectStore.artifacts.requirements)
const scenarios = computed(() => projectStore.artifacts.scenarios)
const shapes = computed(() => projectStore.artifacts.shapes)
const traceabilityArtifact = computed(() => findTraceabilityArtifact(projectStore.artifacts.pmArtifacts))

const reviewDraft = ref<TraceabilityRecordData | null>(null)
const saving = ref(false)
const saveError = ref<string | null>(null)
const readOnlyMode = computed(() => projectStore.runtimeStatus?.read_only_mode !== false)
const readOnlyReason = computed(() =>
  projectStore.runtimeStatus?.read_only_reason
  || 'Studio is running in read-only mode. Explore the design, then download and run Studio locally to make changes.',
)

const activeRequirements = computed(() =>
  requirements.value.find((item) => item.id === projectStore.activeRequirementsId)
  ?? requirements.value.find((item) => item.role === 'primary')
  ?? requirements.value[0]
  ?? null,
)

const activeScenario = computed(() =>
  scenarios.value.find((item) => item.id === projectStore.activeScenarioId)
  ?? scenarios.value[0]
  ?? null,
)

const activeShape = computed(() =>
  shapes.value.find((item) => item.id === projectStore.activeShapeId)
  ?? shapes.value[0]
  ?? null,
)

const requiresShapeForPmReview = computed(() => project.value?.project_type !== 'governed_service_project')
const developerReady = computed(() =>
  !!activeRequirements.value && !!activeScenario.value && (!requiresShapeForPmReview.value || !!activeShape.value),
)
const shapeCoverageTitle = computed(() =>
  project.value?.project_type === 'governed_service_project'
    ? 'Backend Supply Coverage'
    : 'Service Design Coverage',
)

const groupedCoverage = computed(() => {
  const coverage = reviewDraft.value?.coverage ?? []
  return [
    { key: 'requirements', title: 'Requirements Coverage', items: coverage.filter((item) => item.source === 'requirements') },
    { key: 'scenario', title: 'Scenario Coverage', items: coverage.filter((item) => item.source === 'scenario') },
    { key: 'shape', title: shapeCoverageTitle.value, items: coverage.filter((item) => item.source === 'shape') },
  ].filter((group) => group.items.length > 0)
})

const coverageSummary = computed(() => summarizeCoverage(reviewDraft.value?.coverage ?? []))
const observedServiceArtifacts = computed(() => {
  const targetRunId = selectedGenerationRunArtifactId.value
  const artifacts = [...projectStore.artifacts.serviceMetadata].filter((artifact) => {
    const runId = typeof artifact.data?.generation_run_artifact_id === 'string'
      ? artifact.data.generation_run_artifact_id
      : null
    return targetRunId ? runId === targetRunId : true
  })
  artifacts.sort((a, b) => new Date(b.updated_at || b.created_at).getTime() - new Date(a.updated_at || a.created_at).getTime())
  return artifacts
})
const developerDefinitionArtifact = computed(() => findDeveloperDefinitionArtifact(projectStore.artifacts.pmArtifacts))
const developerDefinition = computed(() =>
  (developerDefinitionArtifact.value?.data as DeveloperDefinitionData | undefined) ?? null,
)
const compiledContractIdentity = computed(() =>
  developerDefinition.value?.compiled_contract_identity ?? null,
)
const currentSavedRevision = computed(() => developerDefinition.value?.saved_revision ?? null)
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
  const records = [...projectStore.artifacts.evaluations].filter((record) => {
    const envelope = (record.data?.evidence as { generation_run_artifact_id?: string | null } | undefined) ?? null
    return targetRunId ? envelope?.generation_run_artifact_id === targetRunId : true
  })
  records.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
  return records[0] ?? null
})
const latestEvaluationContractIdentity = computed(() => resolveEvaluationCompiledContractIdentity(latestEvaluation.value as any))
const latestEvaluationObservedServiceEvidence = computed(() => resolveEvaluationObservedServiceEvidence(latestEvaluation.value as any))
const latestEvaluationServiceMetadata = computed(() => resolveEvaluationServiceMetadataSnapshot(latestEvaluation.value as any))
const evaluationAlignment = computed(() =>
  resolveCompiledContractAlignment(compiledContractIdentity.value as any, latestEvaluationContractIdentity.value as any),
)
const generationAlignment = computed(() =>
  resolveGenerationContractAlignment(compiledContractIdentity.value as any, latestGenerationRun.value?.compiled_contract_identity as any),
)

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
  const envelope = (latestEvaluation.value.data?.evidence as EvaluationEvidenceEnvelope | undefined) ?? null
  if (envelope?.definition_revision_artifact_id || envelope?.definition_revision_number != null) {
    return revisionSummaryForTarget(envelope, 'evaluation evidence')
  }
  if (!envelope?.generation_run_artifact_id) {
    return { status: 'unversioned' as const, label: revisionEvidenceLabel('unversioned'), detail: 'This evaluation does not record a generation run id.' }
  }
  return revisionSummaryForRun(latestGenerationRun.value)
})
const savedReviewRevisionEvidence = computed(() => {
  if (!reviewDraft.value?.pm_reviewed_at || reviewDraft.value.pm_review_status === 'pending') {
    return { status: 'missing' as const, label: revisionEvidenceLabel('missing'), detail: 'No PM review evidence is selected.' }
  }
  if (
    reviewDraft.value.pm_review_definition_revision_artifact_id
    || reviewDraft.value.pm_review_definition_revision_number != null
  ) {
    return revisionSummaryForTarget({
      definition_revision_artifact_id: reviewDraft.value.pm_review_definition_revision_artifact_id,
      definition_revision_number: reviewDraft.value.pm_review_definition_revision_number,
    }, 'PM review')
  }
  return revisionSummaryForRun(latestGenerationRun.value)
})

const contractEvidence = computed(() => {
  if (!compiledContractIdentity.value?.signature) {
    return {
      status: 'missing' as EvidenceStatus,
      label: statusLabel('missing'),
      detail: 'No saved revision exists yet. PM signoff must be anchored to a saved Developer Definition first.',
    }
  }
  return {
    status: 'ready' as EvidenceStatus,
    label: statusLabel('ready'),
    detail: 'PM review can target a specific saved revision signature.',
  }
})

const generationEvidence = computed(() =>
  evidenceStatusFromAlignment(
    generationAlignment.value,
    Boolean(latestGenerationRun.value),
    'No aligned generation run is saved yet for the current compiled contract.',
  ),
)

const evaluationEvidence = computed(() =>
  evidenceStatusFromAlignment(
    evaluationAlignment.value,
    Boolean(latestEvaluation.value),
    'No aligned evaluation evidence is saved yet for the current compiled contract.',
  ),
)

const observedServiceEvidence = computed(() => {
  const definition = (developerDefinitionArtifact.value?.data as any) ?? null
  const result = resolveObservedServiceEvidence({
    definition,
    currentContractIdentity: compiledContractIdentity.value as any,
    generationRun: latestGenerationRun.value as any,
    generationRunArtifactId: selectedGenerationRunArtifact.value?.id ?? null,
    observedArtifacts: observedServiceArtifacts.value,
    evaluationObservedEvidence: latestEvaluationObservedServiceEvidence.value as any,
    evaluationSnapshot: latestEvaluationServiceMetadata.value as any,
  })
  return {
    ...result,
    secondary: result.artifactId
      ? `${result.service} · ${result.protocol} · ${result.artifactId}`
      : `${result.service} · ${result.protocol} · ${result.profile}`,
  }
})

const savedReviewEvidence = computed(() => {
  const review = reviewDraft.value
  if (!review?.pm_reviewed_at || review.pm_review_status === 'pending') {
    return {
      status: 'missing' as EvidenceStatus,
      label: statusLabel('missing'),
      detail: 'No saved PM review is recorded against the current contract evidence yet.',
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
      detail: 'A PM review exists, but the current contract, generation, evaluation, or observed-service evidence signature is missing.',
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
      detail: `Saved PM review is ${review.pm_review_status === 'approved' ? 'approved' : 'recorded'} against the current contract evidence set.`,
    }
  }
  return {
    status: 'stale' as EvidenceStatus,
    label: statusLabel('stale'),
    detail: 'A PM review exists, but it was recorded against a different contract or evidence set than the current one.',
  }
})

const signoffTargetSummary = computed(() => ({
  contractSignature: compiledContractIdentity.value?.signature ?? null,
  generationSignature: latestGenerationRun.value?.compiled_contract_identity?.signature ?? null,
  generationArtifactId: selectedGenerationRunArtifact.value?.id ?? null,
  evaluationSignature: latestEvaluationContractIdentity.value?.signature ?? null,
  evaluationId: latestEvaluation.value?.id ?? null,
  observedServiceSignature: observedServiceEvidence.value.signature || null,
  observedServiceArtifactId: observedServiceEvidence.value.artifactId,
  observedServiceLabel: observedServiceEvidence.value.secondary,
}))

const evidencePlanGroups = computed(() => {
  const verification = developerDefinition.value?.verification
  if (!verification) return []
  return [
    {
      key: 'supported-questions',
      title: 'Supported Questions',
      items: verification.supported_question_family_bindings.map((item) => ({
        title: item.question_family,
        proof: item.verification_strategy || 'No verification strategy recorded.',
        evidence: item.evidence_signal || 'No evidence signal recorded.',
      })),
    },
    {
      key: 'business-goals',
      title: 'Business Goals',
      items: verification.business_goal_bindings.map((item) => ({
        title: item.business_goal,
        proof: item.verification_strategy || 'No verification strategy recorded.',
        evidence: item.evidence_signal || 'No evidence signal recorded.',
      })),
    },
    {
      key: 'non-goals',
      title: 'Non-Goal Guards',
      items: verification.non_goal_guards.map((item) => ({
        title: item.non_goal,
        proof: item.guard_strategy || 'No guard strategy recorded.',
        evidence: item.evidence_signal || 'No evidence signal recorded.',
      })),
    },
    {
      key: 'success-criteria',
      title: 'Success Criteria',
      items: verification.success_criteria_checks.map((item) => ({
        title: item.success_criterion,
        proof: item.verification_strategy || 'No technical verification strategy recorded.',
        evidence: item.evidence_expectation || item.review_method || 'No PM evidence expectation recorded.',
      })),
    },
  ].filter((group) => group.items.length > 0)
})

const evidencePlanSummary = computed(() => {
  const groups = evidencePlanGroups.value
  const planned = groups.reduce((sum, group) => sum + group.items.length, 0)
  const missing = groups.reduce(
    (sum, group) => sum + group.items.filter((item) => /^No .* recorded\.$/.test(item.proof)).length,
    0,
  )
  return {
    planned,
    missing,
    status: planned > 0 && missing === 0 ? 'ready' : planned > 0 ? 'stale' : 'missing',
    label: planned > 0 && missing === 0 ? 'Ready for PM review' : planned > 0 ? 'Needs developer evidence detail' : 'No evidence plan',
  }
})

const evidenceCards = computed(() => [
  {
    key: 'contract',
    title: 'Compiled Contract',
    status: contractEvidence.value.status,
    label: contractEvidence.value.label,
    detail: contractEvidence.value.detail,
    signature: compiledContractIdentity.value?.signature ?? 'Not saved yet',
    secondary: compiledContractIdentity.value?.artifact_name ?? 'Save Developer Definition first',
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
      : 'No saved generation run',
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
      ? `${formatStudioTimestamp(latestEvaluation.value.created_at)} · ${latestEvaluation.value.id}`
      : 'No saved evaluation evidence',
    revisionLabel: evaluationRevisionEvidence.value.label,
    revisionStatus: evaluationRevisionEvidence.value.status,
    revisionDetail: evaluationRevisionEvidence.value.detail,
  },
  {
    key: 'observed-service',
    title: 'Observed Service Evidence',
    status: observedServiceEvidence.value.status,
    label: observedServiceEvidence.value.label,
    detail: observedServiceEvidence.value.detail,
    signature: observedServiceEvidence.value.artifactId || 'No observed-service set',
    secondary: observedServiceEvidence.value.artifactId
      ? `${observedServiceEvidence.value.service} · ${observedServiceEvidence.value.artifactId}`
      : `${observedServiceEvidence.value.service} · ${observedServiceEvidence.value.secondary}`,
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
    key: 'review',
    title: 'Saved PM Review',
    status: savedReviewEvidence.value.status,
    label: savedReviewEvidence.value.label,
    detail: savedReviewEvidence.value.detail,
    signature: reviewDraft.value?.pm_review_contract_signature ?? 'No PM review signature',
    secondary: reviewDraft.value?.pm_reviewed_at
      ? `${formatStudioTimestamp(reviewDraft.value.pm_reviewed_at)} · ${pmReviewStatusLabel(reviewDraft.value.pm_review_status)}`
      : 'No saved PM review',
    revisionLabel: savedReviewRevisionEvidence.value.label,
    revisionStatus: savedReviewRevisionEvidence.value.status,
    revisionDetail: savedReviewRevisionEvidence.value.detail,
  },
])

const approvalBlockedReason = computed(() => {
  if (!reviewDraft.value || reviewDraft.value.pm_review_status !== 'approved') return null
  if (!compiledContractIdentity.value?.signature) {
    return 'Approval requires a saved Developer Definition with a compiled contract signature.'
  }
  if (!latestGenerationRun.value || generationAlignment.value.status !== 'aligned') {
    return 'Approval requires an aligned generation run against the latest saved revision.'
  }
  if (!latestEvaluation.value || evaluationAlignment.value.status !== 'aligned') {
    return 'Approval requires aligned evaluation evidence against the latest saved revision.'
  }
  if (observedServiceEvidence.value.status !== 'ready') {
    return 'Approval requires saved observed service metadata that is current and aligned with the latest saved evaluation evidence.'
  }
  return null
})

const reviewOptions: Array<{ value: PmReviewState; label: string }> = [
  { value: 'pending', label: 'Pending Review' },
  { value: 'approved', label: 'Approved' },
  { value: 'changes_requested', label: 'Changes Requested' },
]

async function ensureLoaded() {
  if (!projectId.value) return
  if (projectStore.activeProject?.id === projectId.value) return
  await loadProject(projectId.value)
}

function syncDraft() {
  if (!developerReady.value) {
    reviewDraft.value = null
    return
  }
  reviewDraft.value = buildTraceabilityRecord({
    pmArtifacts: projectStore.artifacts.pmArtifacts,
    requirements: activeRequirements.value,
    scenarios: scenarios.value,
    primaryScenarioId: activeScenario.value?.id ?? null,
    shape: activeShape.value,
    existing: (traceabilityArtifact.value?.data as TraceabilityRecordData | undefined) ?? null,
    reducedFrontingProductDesign: project.value?.project_type === 'governed_service_project',
  })
}

onMounted(async () => {
  await ensureLoaded()
  syncDraft()
})

watch(
  () => [
    projectId.value,
    activeRequirements.value?.id,
    activeScenario.value?.id,
    activeShape.value?.id,
    traceabilityArtifact.value?.updated_at,
  ] as const,
  async () => {
    await ensureLoaded()
    syncDraft()
  },
)

async function saveReview() {
  if (readOnlyMode.value || !project.value || !reviewDraft.value) return
  saving.value = true
  saveError.value = null
  try {
    const revisionSource = latestGenerationRun.value
    const savedRevision = currentSavedRevision.value
    const payload = {
      ...reviewDraft.value,
      artifact_type: DESIGN_TRACEABILITY_ARTIFACT_TYPE,
      pm_reviewed_at: reviewDraft.value.pm_review_status !== 'pending'
        ? new Date().toISOString()
        : reviewDraft.value.pm_reviewed_at,
      pm_review_contract_signature: compiledContractIdentity.value?.signature ?? null,
      pm_review_generation_signature: latestGenerationRun.value?.compiled_contract_identity?.signature ?? null,
      pm_review_generation_artifact_id: selectedGenerationRunArtifact.value?.id ?? null,
      pm_review_definition_revision_artifact_id:
        revisionSource?.definition_revision_artifact_id
        ?? savedRevision?.revision_artifact_id
        ?? null,
      pm_review_definition_revision_number:
        revisionSource?.definition_revision_number
        ?? savedRevision?.revision_number
        ?? null,
      pm_review_product_revision_artifact_id:
        revisionSource?.source_inputs?.product_revision_artifact_id
        ?? developerDefinition.value?.source_inputs?.product_revision_artifact_id
        ?? null,
      pm_review_product_revision_number:
        revisionSource?.source_inputs?.product_revision_number
        ?? developerDefinition.value?.source_inputs?.product_revision_number
        ?? null,
      pm_review_evaluation_signature: latestEvaluationContractIdentity.value?.signature ?? null,
      pm_review_evaluation_id: latestEvaluation.value?.id ?? null,
      pm_review_observed_service_signature: observedServiceEvidence.value.signature || null,
      pm_review_observed_service_artifact_id: observedServiceEvidence.value.artifactId ?? null,
    }

    if (traceabilityArtifact.value) {
      await updatePmArtifact(project.value.id, traceabilityArtifact.value.id, {
        title: 'Developer Coverage & PM Review',
        status: 'draft',
        data: payload,
      })
    } else {
      await createPmArtifact(project.value.id, {
        id: traceabilityArtifactId(project.value.id),
        title: 'Developer Coverage & PM Review',
        data: payload,
      })
    }
    await loadProject(project.value.id)
  } catch (err) {
    saveError.value = err instanceof Error ? err.message : String(err)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="pm-review-view">
    <template v-if="project">
      <section class="page-header">
        <button class="back-link" type="button" @click="router.push(`/design/projects/${project.id}/pm`)">
          &larr; Back to Product Overview
        </button>
        <div class="page-kicker">Product Design</div>
        <h1>PM Review & Signoff</h1>
        <p>
          Review how Developer Design claims to cover the current Product Design context, then approve the implementation direction or request changes.
        </p>
      </section>
      <div v-if="readOnlyMode" class="banner banner-warning readonly-banner">
        {{ readOnlyReason }}
      </div>

      <section v-if="!developerReady" class="panel empty-panel">
        <h2>Product context is incomplete</h2>
        <p>
          {{
            requiresShapeForPmReview
              ? 'Create the active requirements, scenario, and service design before attempting PM review.'
              : 'Create the active requirements and scenario before attempting PM review.'
          }}
        </p>
      </section>

      <section v-else-if="!traceabilityArtifact" class="panel empty-panel">
        <h2>No developer coverage record yet</h2>
        <p>
          PM Review only shows saved developer coverage. This project has PM artifacts, requirements, scenarios, and service design,
          but no saved developer coverage mapping yet, so showing 0 addressed items here would be misleading.
        </p>
        <div class="empty-actions">
          <button class="btn btn-primary" type="button" @click="router.push(`/design/projects/${project.id}/developer/coverage`)">
            Open Developer Coverage
          </button>
          <button class="btn btn-secondary" type="button" @click="router.push(`/design/projects/${project.id}/developer`)">
            Open Developer Design
          </button>
        </div>
      </section>

      <section v-else-if="reviewDraft" class="grid">
        <article class="panel panel-full">
          <div class="panel-header">
            <h2>Evidence Target</h2>
            <span class="status-pill status-ready">
              {{ selectedGenerationRunArtifact ? 'Generation run selected' : 'No run selected' }}
            </span>
          </div>
          <p class="inline-copy">
            PM review targets one saved generation run at a time. Pick the run whose evaluation and runtime proof should anchor signoff.
          </p>
          <div v-if="generationRunArtifacts.length" class="run-target-list">
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
          <div v-if="generationRunArtifacts.length" class="button-stack">
            <p class="inline-copy">
              Studio local runtime proof is retired. Use the external verifier against the published Registry package or package bundle.
            </p>
          </div>
        </article>

        <article class="panel panel-full">
          <div class="panel-header">
            <h2>Current PM Context</h2>
          </div>
          <div class="summary-stack">
            <div class="summary-row">
              <span class="summary-label">Requirements</span>
              <strong>{{ activeRequirements?.title }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Scenario</span>
              <strong>{{ activeScenario?.title }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">{{ shapeCoverageTitle }}</span>
              <strong>
                {{
                  activeShape?.title
                    || (requiresShapeForPmReview ? 'Not selected' : 'Not required for this fronting flow')
                }}
              </strong>
            </div>
          </div>
        </article>

        <article class="panel panel-half">
          <div class="panel-header">
            <h2>Developer Status</h2>
          </div>
          <div class="summary-stack">
            <div class="summary-row">
              <span class="summary-label">Developer state</span>
              <strong>{{ developerStatusLabel(reviewDraft.developer_status) }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Developer note</span>
              <p class="inline-copy">{{ reviewDraft.developer_note || 'No developer note recorded yet.' }}</p>
            </div>
          </div>
        </article>

        <article class="panel panel-half">
          <div class="panel-header">
            <h2>Signoff Against Contract Evidence</h2>
          </div>
          <p class="inline-copy">
            PM review is not general readiness. It is a review against one exact compiled contract signature, the saved generation and evaluation evidence tied to that signature, and the developer-authored Evidence & Verification Plan below.
          </p>
          <div class="evidence-grid">
            <div v-for="item in evidenceCards" :key="item.key" class="evidence-card">
              <div class="evidence-card-header">
                <h3>{{ item.title }}</h3>
                <span class="status-pill" :class="`status-${item.status}`">{{ item.label }}</span>
              </div>
              <div class="evidence-signature">{{ item.signature }}</div>
              <div class="evidence-secondary">{{ item.secondary }}</div>
              <div class="revision-evidence-line">
                <span class="revision-evidence-chip" :class="`revision-evidence-${item.revisionStatus}`">
                  {{ item.revisionLabel }}
                </span>
                <span>{{ item.revisionDetail }}</span>
              </div>
              <p class="coverage-detail">{{ item.detail }}</p>
            </div>
          </div>
        </article>

        <article class="panel panel-wide">
          <div class="panel-header">
            <h2>Coverage Summary</h2>
          </div>
          <div class="metric-grid">
            <div class="metric-card">
              <div class="metric-label">Total Items</div>
              <div class="metric-value">{{ coverageSummary.total }}</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">Addressed</div>
              <div class="metric-value">{{ coverageSummary.addressed }}</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">Partial</div>
              <div class="metric-value">{{ coverageSummary.partial }}</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">Missing</div>
              <div class="metric-value">{{ coverageSummary.missing }}</div>
            </div>
          </div>
        </article>

        <article class="panel panel-full">
          <div class="panel-header">
            <div>
              <h2>Evidence & Verification Plan Review</h2>
              <p class="inline-copy">
                Developers author this plan in Developer Design. PMs review it here as part of signoff: each PM expectation should have a planned proof and a concrete evidence signal.
              </p>
            </div>
            <span class="status-pill" :class="`status-${evidencePlanSummary.status}`">{{ evidencePlanSummary.label }}</span>
          </div>
          <div class="metric-grid evidence-plan-metrics">
            <div class="metric-card">
              <div class="metric-label">Planned Proof Items</div>
              <div class="metric-value">{{ evidencePlanSummary.planned }}</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">Missing Detail</div>
              <div class="metric-value">{{ evidencePlanSummary.missing }}</div>
            </div>
          </div>
          <div v-if="evidencePlanGroups.length" class="evidence-plan-groups">
            <section v-for="group in evidencePlanGroups" :key="group.key" class="evidence-plan-group">
              <h3>{{ group.title }}</h3>
              <div class="evidence-plan-list">
                <div v-for="item in group.items" :key="`${group.key}-${item.title}`" class="evidence-plan-card">
                  <strong>{{ item.title }}</strong>
                  <p><span>Planned proof:</span> {{ item.proof }}</p>
                  <p><span>Evidence signal:</span> {{ item.evidence }}</p>
                </div>
              </div>
            </section>
          </div>
          <p v-else class="inline-copy">
            No developer-authored evidence plan exists yet. Ask developers to complete Evidence & Verification Plan before PM signoff.
          </p>
          <button class="btn btn-secondary" type="button" @click="router.push(`/design/projects/${project.id}/developer/verification-expectations`)">
            Open Developer Evidence Plan
          </button>
        </article>

        <article v-for="group in groupedCoverage" :key="group.key" class="panel panel-full">
          <div class="panel-header">
            <h2>{{ group.title }}</h2>
          </div>
          <div class="coverage-list">
            <div v-for="item in group.items" :key="item.id" class="coverage-card">
              <div class="coverage-card-header">
                <div>
                  <div class="coverage-section">{{ item.section }}</div>
                  <h3>{{ item.label }}</h3>
                  <p class="coverage-detail">{{ item.detail }}</p>
                </div>
                <span class="status-pill" :class="`status-${item.status}`">{{ coverageStatusLabel(item.status) }}</span>
              </div>
              <p class="coverage-rationale">
                <strong>Developer rationale:</strong> {{ item.rationale || 'No rationale recorded yet.' }}
              </p>
              <p class="coverage-rationale">
                <strong>Addressed in:</strong>
                {{ item.linked_surfaces.length ? item.linked_surfaces.join(', ').replaceAll('_', ' ') : 'No linked developer surfaces recorded.' }}
              </p>
            </div>
          </div>
        </article>

        <article class="panel panel-wide">
          <div class="panel-header">
            <h2>PM Signoff</h2>
          </div>
          <div class="signoff-target">
            <div class="summary-row">
              <span class="summary-label">Contract under review</span>
              <strong>{{ signoffTargetSummary.contractSignature || 'No saved revision signature yet' }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Generation evidence under review</span>
              <p class="inline-copy">
                {{ signoffTargetSummary.generationArtifactId ? `${signoffTargetSummary.generationArtifactId} · ${signoffTargetSummary.generationSignature || 'No signature recorded'}` : 'No saved generation run yet.' }}
              </p>
            </div>
            <div class="summary-row">
              <span class="summary-label">Evaluation evidence under review</span>
              <p class="inline-copy">
                {{ signoffTargetSummary.evaluationId ? `${signoffTargetSummary.evaluationId} · ${signoffTargetSummary.evaluationSignature || 'No signature recorded'}` : 'No saved evaluation evidence yet.' }}
              </p>
            </div>
            <div class="summary-row">
              <span class="summary-label">Observed service evidence under review</span>
              <p class="inline-copy">
                {{ signoffTargetSummary.observedServiceArtifactId ? `${signoffTargetSummary.observedServiceArtifactId} · ${signoffTargetSummary.observedServiceLabel || 'No observed service set recorded'}` : 'No saved observed service metadata yet.' }}
              </p>
            </div>
          </div>
          <div class="review-grid">
            <label class="field">
              <span>PM review state</span>
              <select
                v-model="reviewDraft.pm_review_status"
                class="select"
                :disabled="readOnlyMode || reviewDraft.developer_status !== 'ready_for_pm_review'"
              >
                <option v-for="option in reviewOptions" :key="option.value" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
            </label>
            <label class="field field-wide">
              <span>PM review note</span>
              <textarea
                v-model="reviewDraft.pm_review_note"
                class="textarea"
                rows="3"
                :disabled="readOnlyMode || reviewDraft.developer_status !== 'ready_for_pm_review'"
                placeholder="Record approval rationale or concrete changes requested."
              />
            </label>
          </div>
          <p v-if="readOnlyMode" class="inline-copy">
            PM signoff controls are disabled because this Studio instance is read-only.
          </p>
          <p v-if="reviewDraft.developer_status !== 'ready_for_pm_review'" class="inline-copy">
            Developers need to mark the coverage mapping as ready for PM review before signoff can be recorded.
          </p>
          <p v-else-if="approvalBlockedReason" class="inline-copy">
            {{ approvalBlockedReason }}
          </p>
          <p v-if="reviewDraft.pm_reviewed_at" class="inline-copy">
            Current saved review is against contract {{ reviewDraft.pm_review_contract_signature || 'unknown' }}, generation {{ reviewDraft.pm_review_generation_signature || 'unknown' }}, evaluation {{ reviewDraft.pm_review_evaluation_signature || 'unknown' }}, and observed service evidence {{ reviewDraft.pm_review_observed_service_signature || 'unknown' }}.
          </p>
          <p v-if="saveError" class="error">{{ saveError }}</p>
          <button
            class="btn btn-primary"
            :disabled="readOnlyMode || saving || reviewDraft.developer_status !== 'ready_for_pm_review' || !!approvalBlockedReason"
            @click="saveReview"
          >
            {{ saving ? 'Saving…' : 'Save PM Review' }}
          </button>
        </article>
      </section>
    </template>
  </div>
</template>

<style scoped>
.pm-review-view {
  width: 100%;
  max-width: none;
  padding: 2rem;
}

.page-header {
  margin-bottom: 1.5rem;
}

.back-link {
  border: none;
  background: transparent;
  color: var(--accent);
  font-size: 13px;
  cursor: pointer;
  padding: 0;
  margin-bottom: 0.6rem;
}

.banner {
  padding: 0.75rem 0.95rem;
  border-radius: 12px;
  margin-bottom: 1rem;
}

.banner-warning {
  background: rgba(245, 158, 11, 0.12);
  border: 1px solid rgba(245, 158, 11, 0.3);
  color: #fbbf24;
}

.readonly-banner {
  margin-bottom: 1.25rem;
}

.page-kicker,
.summary-label,
.metric-label,
.coverage-section,
.field span {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 12px;
  color: var(--text-secondary);
}

.page-header h1 {
  margin: 0 0 0.55rem;
  font-size: 30px;
}

.page-header p,
.empty-panel p,
.coverage-detail,
.inline-copy {
  color: var(--text-secondary);
  line-height: 1.6;
}

.grid {
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

.panel-wide,
.empty-panel {
  grid-column: span 8;
}

.panel-half {
  grid-column: span 6;
}

.panel-full {
  grid-column: 1 / -1;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1rem;
}

.panel-header h2 {
  margin: 0;
  font-size: 16px;
}

.summary-stack {
  display: grid;
  gap: 0.75rem;
}

.summary-row {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.75rem;
}

.metric-card,
.coverage-card,
.evidence-card {
  border-radius: 14px;
  border: 1px solid var(--surface-border-card);
  background: var(--surface-depth-card);
  padding: 1rem;
}

.metric-value {
  font-size: 24px;
  color: var(--text-primary);
}

.coverage-list {
  display: grid;
  gap: 0.85rem;
}

.evidence-plan-groups {
  display: grid;
  gap: 1rem;
  margin: 1rem 0;
}

.evidence-plan-group {
  display: grid;
  gap: 0.7rem;
}

.evidence-plan-group h3 {
  margin: 0;
  color: var(--text-primary);
  font-size: 16px;
}

.evidence-plan-list {
  display: grid;
  gap: 0.7rem;
}

.evidence-plan-card {
  border-radius: 14px;
  border: 1px solid var(--surface-border-card);
  background: var(--surface-depth-card);
  padding: 0.95rem;
}

.evidence-plan-card strong {
  display: block;
  margin-bottom: 0.45rem;
}

.evidence-plan-card p {
  margin: 0.3rem 0 0;
  color: var(--text-secondary);
  line-height: 1.55;
}

.evidence-plan-card span {
  color: var(--text-primary);
  font-weight: 700;
}

.evidence-plan-metrics {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.evidence-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.85rem;
  margin-top: 1rem;
}

.run-target-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 0.85rem;
  margin-top: 1rem;
}

.run-target-card {
  display: grid;
  gap: 0.35rem;
  border-radius: 14px;
  border: 1px solid var(--surface-border-card);
  background: var(--surface-depth-card);
  color: inherit;
  padding: 1rem;
  text-align: left;
  cursor: pointer;
}

.run-target-card.selected {
  border-color: rgba(96, 165, 250, 0.38);
  background:
    radial-gradient(circle at top right, rgba(96, 165, 250, 0.14), transparent 38%),
    rgba(15, 23, 42, 0.58);
}

.evidence-card-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: center;
}

.evidence-card h3 {
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

.coverage-card-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
}

.coverage-card h3 {
  margin: 0.2rem 0 0.4rem;
  font-size: 18px;
}

.status-pill {
  border-radius: 999px;
  padding: 0.35rem 0.7rem;
  font-size: 12px;
  white-space: nowrap;
}

.status-addressed {
  background: rgba(34, 197, 94, 0.18);
  color: #bbf7d0;
}

.status-partially_addressed {
  background: rgba(251, 191, 36, 0.18);
  color: #fde68a;
}

.status-not_addressed {
  background: rgba(248, 113, 113, 0.18);
  color: #fecaca;
}

.status-deferred,
.status-not_applicable,
.status-missing {
  background: rgba(148, 163, 184, 0.18);
  color: #e2e8f0;
}

.status-ready {
  background: rgba(34, 197, 94, 0.18);
  color: #bbf7d0;
}

.status-stale {
  background: rgba(251, 191, 36, 0.18);
  color: #fde68a;
}

.coverage-rationale {
  margin: 0.6rem 0 0;
  color: var(--text-secondary);
}

.signoff-target {
  display: grid;
  gap: 0.75rem;
  margin-bottom: 1rem;
  padding: 0.9rem 1rem;
  border-radius: 14px;
  border: 1px solid var(--surface-border-card);
  background: var(--surface-depth-card);
}

.review-grid {
  display: grid;
  grid-template-columns: minmax(260px, 320px) minmax(0, 1fr);
  gap: 1rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.field-wide {
  min-width: 0;
}

.select,
.textarea {
  width: 100%;
  border-radius: 12px;
  border: 1px solid var(--surface-border-card);
  background: var(--surface-depth-card);
  color: var(--text-primary);
  padding: 0.75rem 0.85rem;
  font: inherit;
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
  color: var(--text-secondary);
}

.btn:disabled,
.select:disabled,
.textarea:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.empty-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-top: 1rem;
}

.error {
  color: var(--error);
  margin-bottom: 0.75rem;
}

.error-copy {
  color: #fca5a5;
}

@media (max-width: 980px) {
  .panel,
  .panel-wide,
  .panel-half,
  .panel-full,
  .empty-panel {
    grid-column: 1 / -1;
  }

  .metric-grid,
  .review-grid,
  .evidence-grid {
    grid-template-columns: 1fr;
  }

  .coverage-card-header {
    flex-direction: column;
  }
}
</style>
