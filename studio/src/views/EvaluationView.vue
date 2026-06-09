<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  designStore,
  composeDraftProposal,
  clearPendingRuntimeObservation,
  recordRuntimeObservation,
  setSelectedObservedServiceMetadataId,
} from '../design/store'
import { loadProject, projectStore, refreshArtifacts } from '../design/project-store'
import { createEvaluation, explainEvaluationWithAssistant, generateDriftAnalysis } from '../design/project-api'
import type {
  AssistantExplanation,
  DeveloperDefinitionData,
  DeveloperGenerationRunData,
  DriftAnalysis,
} from '../design/project-types'
import type { ObservedServiceMetadata } from '../design/types'
import { runShapeValidation, runValidation } from '../design/api'
import { fetchAudit } from '../api'
import { store } from '../store'
import { normalizeAuditEntryToObservation } from '../design/runtime-observations'
import {
  findDeveloperDefinitionArtifact,
  findLatestDeveloperGenerationRunArtifact,
  resolveEvaluationCompiledContractIdentity,
  resolveEvaluationObservedServiceEvidence,
  resolveEvaluationServiceMetadataSnapshot,
  resolveObservedServiceEvidence,
  resolveCompiledContractAlignment,
  resolveGenerationContractAlignment,
} from '../design/developer-definition'
import { formatStudioTimestamp } from '../design/time'
import { developerLabel } from '../design/developer-vocabulary'
import {
  compareIntendedToObservedMetadata,
  findObservedServiceMetadataArtifact,
  selectObservedServiceMetadata,
} from '../design/service-metadata'
import { approvalReviewRoute } from '../design/approval-surface'
import StudioAssistantPanel from '../design/components/StudioAssistantPanel.vue'

const route = useRoute()
const router = useRouter()

const projectId = computed(() => route.params.projectId as string)
const readOnlyMode = computed(() => projectStore.runtimeStatus?.read_only_mode !== false)
const readOnlyReason = computed(() =>
  projectStore.runtimeStatus?.read_only_reason
  || 'Studio is running in read-only mode. Explore the design, then download and run Studio locally to make changes.',
)

onMounted(() => {
  if (projectId.value && projectStore.activeProject?.id !== projectId.value) {
    loadProject(projectId.value)
  }
})

watch(projectId, (id) => {
  if (id && projectStore.activeProject?.id !== id) {
    loadProject(id)
  }
})

const projectRecord = computed(() => {
  const id = route.params.id as string
  return projectStore.artifacts.evaluations.find(e => e.id === id) ?? null
})

const projectScenario = computed(() => {
  const id = route.params.id as string
  return projectStore.artifacts.scenarios.find(s => s.id === id) ?? null
})

const hasData = computed(() => !!projectRecord.value || !!projectScenario.value || designStore.liveEvaluation !== null)

// Display name for the title
const artifactName = computed(() => {
  return projectRecord.value?.scenario_id ?? projectScenario.value?.title ?? 'Evaluation'
})

const isLive = computed(() => designStore.liveEvaluation !== null)

const evaluation = computed(() => {
  if (designStore.liveEvaluation) {
    return designStore.liveEvaluation.evaluation
  }
  return projectRecord.value?.data?.evaluation ?? null
})

const hasEvaluationResult = computed(() => evaluation.value !== null)

// --- Save to Project ---
const saving = ref(false)
const saveError = ref<string | null>(null)
const savedEvalId = ref<string | null>(null)
const selectedObservedMetadataArtifactId = computed({
  get: () => designStore.selectedObservedServiceMetadataId,
  set: (value: string | null) => setSelectedObservedServiceMetadataId(value),
})
const attachPendingRuntimeObservation = ref(true)
const selectedRuntimeObservationId = ref<string | null>(null)
const auditImportInvocationId = ref('')
const auditImportLoading = ref(false)
const auditImportError = ref<string | null>(null)
const auditImportSuccess = ref<string | null>(null)
const auditBrowseLoading = ref(false)
const auditBrowseError = ref<string | null>(null)
const auditBrowseResults = ref<Record<string, any>[]>([])
const routeImportedInvocationId = ref<string | null>(null)
const activeProposalRecord = computed(() =>
  projectStore.artifacts.proposals.find((item) => item.id === projectStore.activeProposalId) ??
  projectStore.artifacts.proposals[0] ??
  null,
)
const activeShapeRecord = computed(() =>
  projectStore.artifacts.shapes.find((item) => item.id === projectStore.activeShapeId) ??
  projectStore.artifacts.shapes[0] ??
  null,
)
const developerDefinitionArtifact = computed(() => findDeveloperDefinitionArtifact(projectStore.artifacts.pmArtifacts))
const developerDefinition = computed(() =>
  (developerDefinitionArtifact.value?.data as DeveloperDefinitionData | undefined) ?? null,
)
const compiledContractIdentity = computed(() =>
  ((developerDefinitionArtifact.value?.data as { compiled_contract_identity?: Record<string, any> } | undefined)?.compiled_contract_identity) ?? null,
)
const currentSavedRevision = computed(() => developerDefinition.value?.saved_revision ?? null)
const latestGenerationRunArtifact = computed(() => findLatestDeveloperGenerationRunArtifact(projectStore.artifacts.pmArtifacts))
const latestGenerationRun = computed(() =>
  (latestGenerationRunArtifact.value?.data as DeveloperGenerationRunData | undefined) ?? null,
)
const evaluationContractIdentity = computed(() => {
  return resolveEvaluationCompiledContractIdentity(projectRecord.value as any)
})
const contractAlignment = computed(() =>
  resolveCompiledContractAlignment(compiledContractIdentity.value as any, evaluationContractIdentity.value as any),
)
const generationAlignment = computed(() =>
  resolveGenerationContractAlignment(compiledContractIdentity.value as any, latestGenerationRun.value?.compiled_contract_identity as any),
)
const approvalReviewLink = computed(() =>
  approvalReviewRoute(activeProposalRecord.value, activeShapeRecord.value, { status: 'pending' }),
)

const canSave = computed(() =>
  !readOnlyMode.value &&
  isLive.value &&
  projectStore.activeProject !== null,
)
const canPersistAgainstContract = computed(() => Boolean(compiledContractIdentity.value?.signature))

const canImportAuditObservation = computed(() =>
  !readOnlyMode.value &&
  store.connected &&
  !!store.baseUrl &&
  !!store.bearer &&
  auditImportInvocationId.value.trim().length > 0,
)

function formatGenerationField(value: string | undefined | null) {
  return developerLabel(value || 'not_recorded')
}

function buildSelectedObservationHistory() {
  const items = [...availableRuntimeObservations.value]
  if (
    selectedRuntimeObservation.value &&
    !items.some((item) => item.observation_id === selectedRuntimeObservation.value?.observation_id)
  ) {
    items.unshift(selectedRuntimeObservation.value)
  }
  return items.slice(0, 12)
}

const missingContext = computed(() => {
  if (!canSave.value) return null
  const missing: string[] = []
  if (!projectStore.activeRequirementsId) missing.push('requirements set')
  if (!projectStore.activeShapeId && !projectStore.activeProposalId) missing.push('shape or approach')
  if (!canPersistAgainstContract.value) missing.push('saved developer definition')
  return missing.length > 0 ? missing : null
})

const availableObservedMetadataArtifacts = computed(() => projectStore.artifacts.serviceMetadata)

watch(
  () => availableObservedMetadataArtifacts.value.map((item) => item.id).join(','),
  () => {
    if (!availableObservedMetadataArtifacts.value.length) {
      setSelectedObservedServiceMetadataId(null)
      return
    }
    if (
      designStore.selectedObservedServiceMetadataId &&
      availableObservedMetadataArtifacts.value.some(
        (item) => item.id === designStore.selectedObservedServiceMetadataId,
      )
    ) {
      return
    }
    setSelectedObservedServiceMetadataId(null)
  },
  { immediate: true },
)

async function saveToProject() {
  if (readOnlyMode.value) {
    saveError.value = readOnlyReason.value
    return
  }
  if (!canSave.value || !projectStore.activeProject) return
  if (missingContext.value) return

  saving.value = true
  saveError.value = null
  try {
    const requirementsRecord = projectStore.artifacts.requirements.find(
      r => r.id === projectStore.activeRequirementsId,
    )
    const proposalRecord = projectStore.artifacts.proposals.find(
      p => p.id === projectStore.activeProposalId,
    )
    const shapeRecord = projectStore.activeShapeId
      ? projectStore.artifacts.shapes.find(s => s.id === projectStore.activeShapeId)
      : null

    const inputSnapshot: Record<string, any> = {}
    const requirements = designStore.draftRequirements ?? requirementsRecord?.data
    const scenario = designStore.draftScenario ?? projectScenario.value?.data
    const proposal = shapeRecord ? null : (composeDraftProposal() ?? proposalRecord?.data)
    const shape = shapeRecord?.data

    if (requirements) inputSnapshot.requirements = JSON.parse(JSON.stringify(requirements))
    if (scenario) inputSnapshot.scenario = JSON.parse(JSON.stringify(scenario))
    if (proposal) inputSnapshot.proposal = JSON.parse(JSON.stringify(proposal))
    if (shape) inputSnapshot.shape = JSON.parse(JSON.stringify(shape))
    const scenarioId = route.params.id as string
    const evalId = crypto.randomUUID()
    const evaluationData = JSON.parse(JSON.stringify(designStore.liveEvaluation))
    const evidenceEnvelope = buildEvaluationEvidenceEnvelope()
    evaluationData.evidence = evidenceEnvelope
    if (
      attachPendingRuntimeObservation.value &&
      selectedRuntimeObservation.value
    ) {
      evaluationData.evaluation = evaluationData.evaluation || {}
      evaluationData.evaluation.runtime_observations = JSON.parse(
        JSON.stringify(selectedRuntimeObservation.value),
      )
      evaluationData.evaluation.runtime_observation_history = JSON.parse(
        JSON.stringify(buildSelectedObservationHistory()),
      )
    }

    // Shape-first: use shape_id when available, fall back to proposal_id
    const useShape = !!shapeRecord

    await createEvaluation(projectStore.activeProject.id, {
      id: evalId,
      proposal_id: useShape ? null : projectStore.activeProposalId!,
      scenario_id: scenarioId,
      requirements_id: projectStore.activeRequirementsId!,
      shape_id: useShape ? projectStore.activeShapeId : null,
      source: 'live_validation',
      data: evaluationData,
      input_snapshot: inputSnapshot,
    })

    savedEvalId.value = evalId
    if (attachPendingRuntimeObservation.value) {
      clearPendingRuntimeObservation()
    }
    await refreshArtifacts()
  } catch (err) {
    saveError.value = err instanceof Error ? err.message : String(err)
  } finally {
    saving.value = false
  }
}

async function importRuntimeObservationFromAudit() {
  if (readOnlyMode.value) {
    auditImportError.value = readOnlyReason.value
    return
  }
  if (!canImportAuditObservation.value) return
  auditImportLoading.value = true
  auditImportError.value = null
  auditImportSuccess.value = null
  try {
    const response = await fetchAudit(store.baseUrl, store.bearer, {
      invocationId: auditImportInvocationId.value.trim(),
      limit: '5',
    })
    const entries: Record<string, any>[] = Array.isArray(response?.entries) ? response.entries : []
    const exactMatch = entries.find((entry: Record<string, any>) => entry?.invocation_id === auditImportInvocationId.value.trim())
    const entry = exactMatch || entries[0]
    if (!entry) {
      throw new Error('No audit entry found for that invocation id.')
    }
    const observation = normalizeAuditEntryToObservation(entry)
    recordRuntimeObservation(observation)
    selectedRuntimeObservationId.value = observation.observation_id
    auditImportSuccess.value = `Imported ${observation.invoked_capability}${observation.invocation_id ? ` (${observation.invocation_id})` : ''}`
  } catch (err) {
    auditImportError.value = err instanceof Error ? err.message : String(err)
  } finally {
    auditImportLoading.value = false
  }
}

async function importRuntimeObservationFromRoute() {
  if (readOnlyMode.value) return
  const invocationId =
    typeof route.query.auditInvocationId === 'string' ? route.query.auditInvocationId.trim() : ''
  if (!invocationId || invocationId === routeImportedInvocationId.value) return
  if (!store.connected || !store.baseUrl || !store.bearer) return
  routeImportedInvocationId.value = invocationId
  auditImportInvocationId.value = invocationId
  await importRuntimeObservationFromAudit()
}

function useAuditEntryAsObservation(entry: Record<string, any>) {
  if (readOnlyMode.value) return
  const observation = normalizeAuditEntryToObservation(entry)
  recordRuntimeObservation(observation)
  selectedRuntimeObservationId.value = observation.observation_id
  auditImportSuccess.value = `Imported ${observation.invoked_capability}${observation.invocation_id ? ` (${observation.invocation_id})` : ''}`
  auditImportError.value = null
}

async function loadRecentAuditEntries() {
  if (readOnlyMode.value) {
    auditBrowseError.value = readOnlyReason.value
    return
  }
  if (!store.connected || !store.baseUrl || !store.bearer) return
  auditBrowseLoading.value = true
  auditBrowseError.value = null
  try {
    const response = await fetchAudit(store.baseUrl, store.bearer, {
      limit: '10',
    })
    auditBrowseResults.value = Array.isArray(response?.entries) ? response.entries : []
  } catch (err) {
    auditBrowseResults.value = []
    auditBrowseError.value = err instanceof Error ? err.message : String(err)
  } finally {
    auditBrowseLoading.value = false
  }
}

async function handleRunValidation() {
  if (readOnlyMode.value) {
    designStore.validationError = readOnlyReason.value
    return
  }
  if (!projectStore.activeRequirementsId || (!projectStore.activeProposalId && !projectStore.activeShapeId) || !projectScenario.value) {
    designStore.validationError = 'Choose a requirements set, scenario, and shape or approach before evaluating.'
    return
  }

  const requirementsRecord = projectStore.artifacts.requirements.find(
    r => r.id === projectStore.activeRequirementsId,
  )
  const proposalRecord = projectStore.activeProposalId
    ? projectStore.artifacts.proposals.find(p => p.id === projectStore.activeProposalId)
    : null
  const shapeRecord = projectStore.activeShapeId
    ? projectStore.artifacts.shapes.find(s => s.id === projectStore.activeShapeId)
    : null
  const scenarioRecord = projectScenario.value

  if (!requirementsRecord || (projectStore.activeShapeId && !shapeRecord)) {
    designStore.validationError = 'Active design context is incomplete.'
    return
  }

  designStore.validating = true
  designStore.validationError = null
  try {
    const requirements = designStore.draftRequirements ?? requirementsRecord.data
    const scenario = designStore.draftScenario ?? scenarioRecord.data
    const result = shapeRecord
      ? await runShapeValidation(requirements, shapeRecord.data, scenario)
      : await runValidation(requirements, composeDraftProposal() ?? proposalRecord?.data ?? {}, scenario)
    designStore.liveEvaluation = result
  } catch (err: any) {
    designStore.validationError = err.message ?? 'Unknown error'
  } finally {
    designStore.validating = false
  }
}

function clearLive() {
  if (readOnlyMode.value) return
  designStore.liveEvaluation = null
  designStore.validationError = null
  savedEvalId.value = null
}

// --- Re-evaluate stale stored evaluations ---
const reEvaluating = ref(false)
const reEvaluateError = ref<string | null>(null)
const assistantLoading = ref(false)
const assistantError = ref<string | null>(null)
const assistantExplanation = ref<AssistantExplanation | null>(null)
const driftAnalysisLoading = ref(false)
const driftAnalysisError = ref<string | null>(null)
const driftAnalysis = ref<DriftAnalysis | null>(null)

const isStoredStale = computed(() =>
  !isLive.value &&
  projectRecord.value?.is_stale === true,
)

const availableRuntimeObservations = computed(() => {
  const observations = [...designStore.runtimeObservationHistory]
  if (
    designStore.pendingRuntimeObservation &&
    !observations.some((item) => item.observation_id === designStore.pendingRuntimeObservation?.observation_id)
  ) {
    observations.unshift(designStore.pendingRuntimeObservation)
  }
  return observations
})

const selectedRuntimeObservation = computed(() => {
  if (!selectedRuntimeObservationId.value) return designStore.pendingRuntimeObservation
  return (
    availableRuntimeObservations.value.find(
      (item) => item.observation_id === selectedRuntimeObservationId.value,
    ) ?? designStore.pendingRuntimeObservation
  )
})

const runtimeObservations = computed<Record<string, any> | null>(() => {
  const livePending =
    isLive.value &&
    attachPendingRuntimeObservation.value &&
    selectedRuntimeObservation.value
      ? selectedRuntimeObservation.value
      : null
  const value = evaluation.value?.runtime_observations || livePending
  return value && typeof value === 'object' ? value : null
})

const runtimeObservationHistory = computed<Record<string, any>[]>(() => {
  const history = evaluation.value?.runtime_observation_history
  if (Array.isArray(history)) {
    return history.filter((item): item is Record<string, any> => !!item && typeof item === 'object')
  }
  return []
})

watch(
  () => availableRuntimeObservations.value.map((item) => item.observation_id).join(','),
  () => {
    if (!availableRuntimeObservations.value.length) {
      selectedRuntimeObservationId.value = null
      return
    }
    if (
      !selectedRuntimeObservationId.value ||
      !availableRuntimeObservations.value.some(
        (item) => item.observation_id === selectedRuntimeObservationId.value,
      )
    ) {
      selectedRuntimeObservationId.value = availableRuntimeObservations.value[0].observation_id
    }
  },
  { immediate: true },
)

const runtimeObservationAuditQuery = computed(() => {
  if (!runtimeObservations.value?.invocation_id) return null
  return {
    name: 'audit',
    query: {
      invocationId: String(runtimeObservations.value.invocation_id),
      capability: runtimeObservations.value.invoked_capability
        ? String(runtimeObservations.value.invoked_capability)
        : undefined,
    },
  }
})

const intendedScenarioMetadata = computed<Record<string, any> | null>(() => {
  if (projectRecord.value?.input_snapshot?.scenario) return projectRecord.value.input_snapshot.scenario
  return designStore.draftScenario ?? projectScenario.value?.data ?? null
})

const intendedProposalMetadata = computed<Record<string, any> | null>(() => {
  if (projectRecord.value?.input_snapshot?.proposal) return projectRecord.value.input_snapshot.proposal
  if (projectRecord.value?.input_snapshot?.shape) return null
  if (projectStore.activeShapeId) return null
  const activeProposal = projectStore.activeProposalId
    ? projectStore.artifacts.proposals.find((item) => item.id === projectStore.activeProposalId)
    : null
  return composeDraftProposal() ?? activeProposal?.data ?? null
})

const intendedShapeMetadata = computed<Record<string, any> | null>(() => {
  if (projectRecord.value?.input_snapshot?.shape) return projectRecord.value.input_snapshot.shape
  const activeShape = projectStore.activeShapeId
    ? projectStore.artifacts.shapes.find((item) => item.id === projectStore.activeShapeId)
    : null
  return activeShape?.data ?? null
})

const observedServiceMetadata = computed<ObservedServiceMetadata | null>(() => {
  if (designStore.selectedObservedServiceMetadataId) {
    const selectedArtifact = projectStore.artifacts.serviceMetadata.find(
      (item) => item.id === designStore.selectedObservedServiceMetadataId,
    )
    if (selectedArtifact?.data) {
      return selectedArtifact.data as ObservedServiceMetadata
    }
  }
  const projectObserved = selectObservedServiceMetadata(projectStore.artifacts.serviceMetadata, {
    serviceId: store.serviceId,
    baseUrl: store.baseUrl,
  })
  if (projectObserved) return projectObserved
  const savedSnapshot = resolveEvaluationServiceMetadataSnapshot(projectRecord.value as any)
  if (savedSnapshot) return savedSnapshot
  return designStore.observedServiceMetadata ?? null
})

const observedServiceMetadataSource = computed(() => {
  if (designStore.selectedObservedServiceMetadataId) {
    return {
      label: 'selected project artifact',
      detail: designStore.selectedObservedServiceMetadataId,
    }
  }
  const projectArtifact = findObservedServiceMetadataArtifact(projectStore.artifacts.serviceMetadata, {
    serviceId: store.serviceId,
    baseUrl: store.baseUrl,
  })
  if (projectArtifact) {
    return {
      label: 'project artifact',
      detail: projectArtifact.id,
    }
  }
  if (resolveEvaluationServiceMetadataSnapshot(projectRecord.value as any)) {
    return {
      label: 'saved evaluation snapshot',
      detail: projectRecord.value?.id ?? null,
    }
  }
  if (designStore.observedServiceMetadata) {
    return {
      label: 'live inspect session',
      detail: designStore.observedServiceMetadata.service_id || designStore.observedServiceMetadata.base_url || null,
    }
  }
  return null
})

const currentObservedMetadataArtifact = computed(() => {
  if (designStore.selectedObservedServiceMetadataId) {
    return projectStore.artifacts.serviceMetadata.find(
      (item) => item.id === designStore.selectedObservedServiceMetadataId,
    ) ?? null
  }
  return findObservedServiceMetadataArtifact(projectStore.artifacts.serviceMetadata, {
    serviceId: store.serviceId,
    baseUrl: store.baseUrl,
  }) ?? null
})

const serviceMetadataComparison = computed(() => {
  if (!observedServiceMetadata.value) return null
  return compareIntendedToObservedMetadata({
    scenario: intendedScenarioMetadata.value,
    proposal: intendedProposalMetadata.value,
    shape: intendedShapeMetadata.value,
    observed: observedServiceMetadata.value,
  })
})

const currentObservedServiceEvidence = computed(() => {
  const definition = (developerDefinitionArtifact.value?.data as any) ?? null
  return resolveObservedServiceEvidence({
    definition,
    currentContractIdentity: compiledContractIdentity.value as any,
    generationRun: latestGenerationRun.value as any,
    generationRunArtifactId: latestGenerationRunArtifact.value?.id ?? null,
    observedArtifacts: currentObservedMetadataArtifact.value ? [currentObservedMetadataArtifact.value] : [],
    evaluationSnapshot: observedServiceMetadata.value as any,
  })
})

const currentObservedServiceSetEvidence = computed(() => {
  const definition = (developerDefinitionArtifact.value?.data as any) ?? null
  return resolveObservedServiceEvidence({
    definition,
    currentContractIdentity: compiledContractIdentity.value as any,
    generationRun: latestGenerationRun.value as any,
    generationRunArtifactId: latestGenerationRunArtifact.value?.id ?? null,
    observedArtifacts: projectStore.artifacts.serviceMetadata,
    evaluationSnapshot: null,
  })
})

const savedObservedServiceEvidence = computed(() =>
  resolveEvaluationObservedServiceEvidence(projectRecord.value as any),
)

const normalizedObservedServiceEvidence = computed(() => {
  if (!isLive.value && savedObservedServiceEvidence.value) {
    return savedObservedServiceEvidence.value
  }
  return currentObservedServiceEvidence.value
})

function buildEvaluationEvidenceEnvelope() {
  const run = latestGenerationRun.value
  const savedRevision = currentSavedRevision.value
  return {
    compiled_contract_identity: compiledContractIdentity.value
      ? JSON.parse(JSON.stringify(compiledContractIdentity.value))
      : null,
    generation_run_artifact_id: latestGenerationRunArtifact.value?.id ?? null,
    generation_dependency_source: run?.generator_inputs?.dependency_source ?? null,
    definition_revision_artifact_id: run?.definition_revision_artifact_id ?? savedRevision?.revision_artifact_id ?? null,
    definition_revision_number: run?.definition_revision_number ?? savedRevision?.revision_number ?? null,
    product_revision_artifact_id:
      run?.source_inputs?.product_revision_artifact_id
      ?? developerDefinition.value?.source_inputs?.product_revision_artifact_id
      ?? null,
    product_revision_number:
      run?.source_inputs?.product_revision_number
      ?? developerDefinition.value?.source_inputs?.product_revision_number
      ?? null,
    service_metadata_snapshot: observedServiceMetadata.value
      ? JSON.parse(JSON.stringify(observedServiceMetadata.value))
      : null,
    observed_service_evidence: currentObservedServiceSetEvidence.value
      ? JSON.parse(JSON.stringify(currentObservedServiceSetEvidence.value))
      : null,
    metadata_comparison: serviceMetadataComparison.value
      ? JSON.parse(JSON.stringify(serviceMetadataComparison.value))
      : null,
  }
}

const conformanceFailures = computed(() =>
  serviceMetadataComparison.value?.conformance_checks.filter((item) => item.status === 'non_conformant') ?? [],
)

const conformanceGaps = computed(() =>
  serviceMetadataComparison.value?.conformance_checks.filter((item) => item.status === 'insufficient_metadata') ?? [],
)

const driftCategoryLabel = computed(() => developerLabel(driftAnalysis.value?.gap_category, ''))
const driftOwnerLabel = computed(() => developerLabel(driftAnalysis.value?.likely_owner, ''))
const driftPriorityLabel = computed(() => driftAnalysis.value?.fix_priority ? `${driftAnalysis.value.fix_priority} priority` : '')
const driftDecisionSummary = computed(() => {
  const gap = driftAnalysis.value?.gap_category
  if (!gap) return ''
  if (gap === 'service_metadata_insufficient') {
    return 'Decision: treat the current implementation as incomplete against the intended capability surface.'
  }
  if (gap === 'developer_binding_incomplete') {
    return 'Decision: update the developer design or narrow the implementation boundary before relying on this capability.'
  }
  if (gap === 'agent_planning_misaligned') {
    return 'Decision: keep the capability, but tighten consuming-agent guidance before broader rollout.'
  }
  if (gap === 'clarification_loop_detected') {
    return 'Decision: do not expand rollout until the clarification path stops looping.'
  }
  if (gap === 'approval_control_missing') {
    return 'Decision: keep write actions gated until approval controls are explicit and testable.'
  }
  if (gap === 'backend_semantics_mismatch') {
    return 'Decision: review backend or adapter semantics before treating this implementation as aligned.'
  }
  return 'Decision: close the identified drift before treating the implementation as aligned.'
})
const serviceMetadataDecisionSummary = computed(() => {
  const comparison = serviceMetadataComparison.value
  if (!comparison) return ''
  if (conformanceFailures.value.length) {
    return `Decision: do not treat this implementation as ANIP-conformant yet; fix ${conformanceFailures.value.map((item) => item.label.toLowerCase()).join(', ')} first.`
  }
  if (conformanceGaps.value.length) {
    return `Decision: service metadata is still incomplete for conformance review; inspect ${conformanceGaps.value.map((item) => item.label.toLowerCase()).join(', ')} before relying on this validation.`
  }
  if (!comparison.missing_capabilities.length && !comparison.extra_capabilities.length) {
    return 'Decision: the observed implementation matches the intended capability surface closely enough to validate behavior directly.'
  }
  if (comparison.missing_capabilities.length && !comparison.extra_capabilities.length) {
    return 'Decision: the implementation is still missing intended capabilities; do not treat it as fully aligned yet.'
  }
  if (!comparison.missing_capabilities.length && comparison.extra_capabilities.length) {
    return 'Decision: the implementation exposes a broader surface than intended; confirm whether to narrow it or update the design.'
  }
  return 'Decision: the implementation is both missing intended capabilities and exposing extras; tighten the boundary before broader use.'
})

const staleArtifactLabels = computed<string[]>(() => {
  const stale = projectRecord.value?.stale_artifacts ?? []
  return stale.map(a => {
    if (a === 'requirements') return 'Requirements changed'
    if (a === 'scenario') return 'Scenario changed'
    if (a === 'proposal') return 'Approach changed'
    if (a === 'shape') return 'Shape changed'
    return `${a} changed`
  })
})

async function handleReEvaluate() {
  if (readOnlyMode.value) {
    reEvaluateError.value = readOnlyReason.value
    return
  }
  if (!projectStore.activeProject || !projectRecord.value) return

  const pid = projectStore.activeProject.id
  const stored = projectRecord.value

  // Resolve the linked artifacts from the store
  const reqRecord = projectStore.artifacts.requirements.find(r => r.id === stored.requirements_id)
  const propRecord = stored.proposal_id
    ? projectStore.artifacts.proposals.find(p => p.id === stored.proposal_id)
    : null
  const shapeRecord = stored.shape_id
    ? projectStore.artifacts.shapes.find(s => s.id === stored.shape_id)
    : null
  const scnRecord = projectStore.artifacts.scenarios.find(s => s.id === stored.scenario_id)

  if (!reqRecord || !scnRecord) {
    reEvaluateError.value = 'Could not find linked artifacts for re-evaluation.'
    return
  }

  if (!propRecord && !shapeRecord) {
    reEvaluateError.value = 'Could not find linked approach or shape for re-evaluation.'
    return
  }

  reEvaluating.value = true
  reEvaluateError.value = null
  try {
    const requirements = reqRecord.data
    const scenario = scnRecord.data
    const result = shapeRecord
      ? await runShapeValidation(requirements, shapeRecord.data, scenario)
      : await runValidation(requirements, propRecord?.data ?? {}, scenario)

    const inputSnapshot: Record<string, any> = {
      requirements: JSON.parse(JSON.stringify(requirements)),
      scenario: JSON.parse(JSON.stringify(scenario)),
    }
    if (shapeRecord) {
      inputSnapshot.shape = JSON.parse(JSON.stringify(shapeRecord.data))
    } else if (propRecord) {
      inputSnapshot.proposal = JSON.parse(JSON.stringify(propRecord.data))
    }

    const evalId = crypto.randomUUID()
    const evaluationData = JSON.parse(JSON.stringify(result))
    const evidenceEnvelope = buildEvaluationEvidenceEnvelope()
    evaluationData.evidence = evidenceEnvelope
    await createEvaluation(pid, {
      id: evalId,
      proposal_id: stored.proposal_id,
      scenario_id: stored.scenario_id,
      requirements_id: stored.requirements_id,
      shape_id: stored.shape_id,
      source: 'live_validation',
      data: evaluationData,
      input_snapshot: inputSnapshot,
    })

    await refreshArtifacts()
    router.push(`/design/projects/${pid}/evaluations/${evalId}`)
  } catch (err) {
    reEvaluateError.value = err instanceof Error ? err.message : String(err)
  } finally {
    reEvaluating.value = false
  }
}

async function refreshDriftAnalysis() {
  if (readOnlyMode.value) {
    driftAnalysis.value = null
    driftAnalysisError.value = null
    driftAnalysisLoading.value = false
    return
  }
  if (!projectId.value || !projectRecord.value) {
    driftAnalysis.value = null
    driftAnalysisError.value = null
    return
  }
  driftAnalysisLoading.value = true
  driftAnalysisError.value = null
  try {
    driftAnalysis.value = await generateDriftAnalysis({
      project_id: projectId.value,
      requirements_id: projectRecord.value.requirements_id,
      scenario_id: projectRecord.value.scenario_id,
      shape_id: projectRecord.value.shape_id || undefined,
      evaluation_id: projectRecord.value.id,
      service_metadata_artifact_id: designStore.selectedObservedServiceMetadataId || undefined,
      metadata_comparison: serviceMetadataComparison.value || undefined,
    })
  } catch (err) {
    driftAnalysis.value = null
    driftAnalysisError.value = err instanceof Error ? err.message : String(err)
  } finally {
    driftAnalysisLoading.value = false
  }
}

watch(
  () => [
    projectId.value,
    projectRecord.value?.id ?? '',
    designStore.selectedObservedServiceMetadataId ?? '',
    observedServiceMetadata.value?.observed_at ?? '',
  ],
  () => {
    void refreshDriftAnalysis()
  },
  { immediate: true },
)

watch(
  () => route.query.auditInvocationId,
  () => {
    void importRuntimeObservationFromRoute()
  },
  { immediate: true },
)

function categoryColor(cat: string): string {
  const colors: Record<string, string> = {
    safety: 'var(--design-category-safety)',
    orchestration: 'var(--design-category-orchestration)',
    observability: 'var(--design-category-observability)',
    cross_service: 'var(--design-category-cross-service)',
  }
  return colors[cat] || 'var(--text-muted)'
}

async function handleExplainEvaluation(question: string) {
  if (readOnlyMode.value) {
    assistantError.value = readOnlyReason.value
    return
  }
  if (!projectRecord.value || !projectId.value) return
  assistantLoading.value = true
  assistantError.value = null
  try {
    assistantExplanation.value = await explainEvaluationWithAssistant(projectId.value, projectRecord.value.id, question)
  } catch (err) {
    assistantError.value = err instanceof Error ? err.message : String(err)
  } finally {
    assistantLoading.value = false
  }
}
</script>

<template>
  <div class="evaluation-view" v-if="hasData">
    <nav class="breadcrumb-row" aria-label="Project evaluation navigation">
      <router-link :to="`/design/projects/${projectId}/verification`">Verification</router-link>
      <span>/</span>
      <span>Evaluation detail</span>
    </nav>

    <div class="header-row">
      <h1 class="page-title">Evaluation: {{ artifactName }}</h1>
      <div class="header-actions">
        <span class="source-badge live" v-if="hasEvaluationResult && isLive && !savedEvalId">Live</span>
        <span class="source-badge stale" v-else-if="hasEvaluationResult && isStoredStale">Stale</span>
        <span class="source-badge stored" v-else-if="hasEvaluationResult && (savedEvalId || !isLive)">Stored</span>
        <button
          v-if="designStore.apiAvailable && !designStore.validating"
          class="run-btn"
          :disabled="readOnlyMode"
          @click="handleRunValidation"
        >Test This Design</button>
        <span v-if="designStore.validating" class="spinner"></span>
        <button
          v-if="isLive"
          class="reset-btn"
          :disabled="readOnlyMode"
          @click="clearLive"
        >Reset</button>
      </div>
    </div>

    <div v-if="readOnlyMode" class="readonly-banner">
      <strong>Read-only showcase mode</strong>
      <span>{{ readOnlyReason }} Evaluation runs, saves, audit imports, assistant explanations, and drift analysis are disabled in the hosted preview.</span>
    </div>

    <div class="contract-context">
      <div class="contract-context-header">
        <h2>Compiled Contract Context</h2>
        <span class="source-badge" :class="contractAlignment.status === 'aligned' ? 'stored' : contractAlignment.status === 'stale' ? 'stale' : 'live'">
          {{ isLive ? 'Current contract' : contractAlignment.label }}
        </span>
      </div>
      <p class="contract-context-copy">
        {{ isLive
          ? 'This live evaluation will be saved against the current compiled contract identity.'
          : contractAlignment.detail }}
      </p>
      <div class="contract-context-grid">
        <div class="contract-context-row">
          <span>Current contract</span>
          <strong>{{ compiledContractIdentity?.signature || 'Not saved' }}</strong>
        </div>
        <div class="contract-context-row">
          <span>Evaluation contract</span>
          <strong>{{ evaluationContractIdentity?.signature || (isLive ? 'Will use current contract on save' : 'Not recorded') }}</strong>
        </div>
        <div class="contract-context-row">
          <span>Artifact</span>
          <strong>{{ compiledContractIdentity?.artifact_name || 'Not available' }}</strong>
        </div>
      </div>
      <div class="contract-context-divider"></div>
      <div class="contract-context-header nested">
        <h3>Latest Generation Run</h3>
        <span class="source-badge" :class="generationAlignment.status === 'aligned' ? 'stored' : generationAlignment.status === 'stale' ? 'stale' : 'live'">
          {{ latestGenerationRun ? generationAlignment.label : 'None yet' }}
        </span>
      </div>
      <p class="contract-context-copy">
        {{ latestGenerationRun ? generationAlignment.detail : 'No generation run has been recorded yet for the current project.' }}
      </p>
      <div v-if="latestGenerationRun" class="contract-context-grid">
        <div class="contract-context-row">
          <span>Generated</span>
          <strong>{{ formatStudioTimestamp(latestGenerationRun.generated_at) }}</strong>
        </div>
        <div class="contract-context-row">
          <span>Generation contract</span>
          <strong>{{ latestGenerationRun.compiled_contract_identity?.signature || 'Not recorded' }}</strong>
        </div>
        <div class="contract-context-row">
          <span>Primary output mode</span>
          <strong>{{ formatGenerationField(latestGenerationRun.generator_inputs.primary_output_mode) }}</strong>
        </div>
        <div class="contract-context-row">
          <span>Runtime target mode</span>
          <strong>{{ formatGenerationField(latestGenerationRun.generator_inputs.runtime_target_mode) }}</strong>
        </div>
      </div>
    </div>

    <!-- Save to Project -->
    <div class="save-section" v-if="canSave && !savedEvalId">
      <div class="save-warning" v-if="missingContext">
        Select a {{ missingContext.join(' and ') }} in the project overview before saving.
      </div>
      <template v-else>
        <label v-if="designStore.pendingRuntimeObservation" class="runtime-attach-toggle">
          <input v-model="attachPendingRuntimeObservation" type="checkbox" :disabled="readOnlyMode" />
          <span>
            Attach latest runtime observation from
            <strong>{{ selectedRuntimeObservation?.invoked_capability || designStore.pendingRuntimeObservation.invoked_capability }}</strong>
            <template v-if="selectedRuntimeObservation?.invocation_id || designStore.pendingRuntimeObservation.invocation_id">
              ({{ selectedRuntimeObservation?.invocation_id || designStore.pendingRuntimeObservation.invocation_id }})
            </template>
          </span>
        </label>
        <label
          v-if="attachPendingRuntimeObservation && availableRuntimeObservations.length > 1"
          class="runtime-attach-toggle"
        >
          <span>Observation</span>
          <select v-model="selectedRuntimeObservationId" class="runtime-select" :disabled="readOnlyMode">
            <option
              v-for="item in availableRuntimeObservations"
              :key="item.observation_id"
              :value="item.observation_id"
            >
              {{ item.source || 'runtime' }} · {{ item.invoked_capability }}{{ item.invocation_id ? ` (${item.invocation_id})` : '' }}
            </option>
          </select>
        </label>
        <label
          v-if="store.connected && store.bearer"
          class="runtime-attach-toggle runtime-import-row"
        >
          <span>Import from audit</span>
          <input
            v-model="auditImportInvocationId"
            class="runtime-select runtime-input"
            type="text"
            placeholder="invocation_id"
            :disabled="readOnlyMode"
          />
          <button
            class="save-btn import-btn"
            type="button"
            :disabled="readOnlyMode || auditImportLoading || !canImportAuditObservation"
            @click="importRuntimeObservationFromAudit"
          >
            <span v-if="auditImportLoading" class="spinner small"></span>
            {{ auditImportLoading ? 'Importing...' : 'Import' }}
          </button>
        </label>
        <div v-if="auditImportError" class="save-error">{{ auditImportError }}</div>
        <div v-else-if="auditImportSuccess" class="save-success">{{ auditImportSuccess }}</div>
        <div
          v-if="store.connected && store.bearer"
          class="runtime-audit-browser"
        >
          <div class="runtime-audit-actions">
            <button
              class="save-btn import-btn"
              type="button"
              :disabled="readOnlyMode || auditBrowseLoading"
              @click="loadRecentAuditEntries"
            >
              <span v-if="auditBrowseLoading" class="spinner small"></span>
              {{ auditBrowseLoading ? 'Loading traces...' : 'Load recent audit traces' }}
            </button>
            <button
              v-if="approvalReviewLink"
              class="save-btn import-btn approval-nav-btn"
              type="button"
              @click="router.push(approvalReviewLink)"
            >
              Open approval review
            </button>
          </div>
          <div v-if="auditBrowseError" class="save-error">{{ auditBrowseError }}</div>
          <ul v-else-if="auditBrowseResults.length" class="audit-trace-list">
            <li v-for="entry in auditBrowseResults" :key="entry.invocation_id || `${entry.capability}:${entry.sequence_number}`">
              <button
                type="button"
                class="audit-trace-item"
                :disabled="readOnlyMode"
                @click="useAuditEntryAsObservation(entry)"
              >
                <span class="audit-trace-capability">{{ entry.capability || 'unknown' }}</span>
                <span class="audit-trace-meta" v-if="entry.invocation_id">{{ entry.invocation_id }}</span>
                <span class="audit-trace-meta" v-if="entry.event_class">{{ entry.event_class }}</span>
              </button>
            </li>
          </ul>
        </div>
        <button
          class="save-btn"
          :disabled="readOnlyMode || saving || !canPersistAgainstContract"
          @click="saveToProject"
        >
          <span v-if="saving" class="spinner small"></span>
          {{ saving ? 'Saving...' : 'Save to Project' }}
        </button>
        <div class="save-error" v-if="saveError">{{ saveError }}</div>
      </template>
    </div>
    <div class="save-section" v-else-if="savedEvalId">
      <span class="save-success">Evaluation saved to project.</span>
    </div>

    <!-- Stale evaluation notice + Re-evaluate -->
    <div class="stale-section" v-if="isStoredStale">
      <div class="stale-notice">
        <span class="stale-icon">&#9888;</span>
        This evaluation is out of date.
        <span v-if="staleArtifactLabels.length > 0" class="stale-details">
          {{ staleArtifactLabels.join(', ') }}.
        </span>
      </div>
      <div v-if="contractAlignment.status !== 'aligned'" class="stale-contract-note">
        Contract status: <strong>{{ contractAlignment.label }}</strong>. {{ contractAlignment.detail }}
      </div>
      <button
        class="reevaluate-btn"
        :disabled="readOnlyMode || reEvaluating"
        @click="handleReEvaluate"
      >
        <span v-if="reEvaluating" class="spinner small"></span>
        {{ reEvaluating ? 'Re-evaluating...' : 'Re-evaluate' }}
      </button>
      <div class="save-error" v-if="reEvaluateError">{{ reEvaluateError }}</div>
    </div>

    <!-- Validation error -->
    <div class="validation-error" v-if="designStore.validationError">
      {{ designStore.validationError }}
    </div>

    <div v-if="!hasEvaluationResult" class="empty-evaluation">
      <template v-if="readOnlyMode">
        No evaluation has been recorded for this scenario in the hosted preview.
      </template>
      <template v-else>
      No evaluation yet. Use Test This Design to see what this design supports, what still needs additional implementation work, and what should change next.
      </template>
    </div>

    <template v-if="evaluation">
      <StudioAssistantPanel
        v-if="projectRecord"
        title="Explain This Evaluation"
        description="Ask Studio to explain the result in plain terms, highlight the main design and implementation gaps, and point to the next design moves."
        button-label="Explain This Evaluation"
        :explanation="assistantExplanation"
        :loading="assistantLoading"
        :error="assistantError"
        :read-only="readOnlyMode"
        :read-only-reason="readOnlyReason"
        @run="handleExplainEvaluation"
      />

      <!-- Result badge -->
      <div class="result-badge" :class="'result-' + evaluation.result.toLowerCase().replace('_', '-')">
        {{ evaluation.result }}
      </div>

      <!-- Confidence -->
      <div class="confidence" v-if="evaluation.confidence">
        <span class="confidence-label">Confidence:</span>
        <span class="confidence-value">{{ evaluation.confidence }}</span>
      </div>

      <!-- Glue categories -->
      <div class="categories-section" v-if="evaluation.glue_category && evaluation.glue_category.length">
        <h2>Categories</h2>
        <div class="pill-row">
          <span
            class="cat-pill"
            v-for="(cat, i) in evaluation.glue_category"
            :key="i"
            :style="{ background: categoryColor(cat) + '1a', color: categoryColor(cat), borderColor: categoryColor(cat) + '4d' }"
          >{{ cat }}</span>
        </div>
      </div>

      <!-- Supported by Design -->
      <div class="section">
        <h2>Supported by Design</h2>
        <ul>
          <li v-for="(item, i) in evaluation.handled_by_anip" :key="i">{{ item }}</li>
        </ul>
      </div>

      <!-- Additional Implementation Work -->
      <div class="section" v-if="evaluation.glue_you_will_still_write && evaluation.glue_you_will_still_write.length">
        <h2>Additional Implementation Work</h2>
        <ul class="glue-list">
          <li v-for="(item, i) in evaluation.glue_you_will_still_write" :key="i">{{ item }}</li>
        </ul>
      </div>

      <!-- Why -->
      <div class="section">
        <h2>Why</h2>
        <ul>
          <li v-for="(item, i) in evaluation.why" :key="i">{{ item }}</li>
        </ul>
      </div>

      <!-- Design Changes Needed -->
      <div class="section" v-if="evaluation.what_would_improve && evaluation.what_would_improve.length">
        <h2>What Needs to Change</h2>
        <ul>
          <li v-for="(item, i) in evaluation.what_would_improve" :key="i">{{ item }}</li>
        </ul>
      </div>

      <div class="section">
        <h2>Validation Decision Summary</h2>
        <p v-if="isLive" class="section-note">
          Save this live evaluation to the project to generate a trace-backed validation summary for business and developer review.
        </p>
        <p v-else-if="driftAnalysisLoading" class="section-note">
          Comparing intended behavior against the latest observed implementation evidence...
        </p>
        <p v-else-if="driftAnalysisError" class="section-note">{{ driftAnalysisError }}</p>
        <template v-else-if="driftAnalysis">
          <div class="pill-row">
            <span class="cat-pill glue-pill">{{ driftCategoryLabel }}</span>
            <span class="cat-pill glue-pill">{{ driftOwnerLabel }}</span>
            <span class="cat-pill glue-pill">{{ driftPriorityLabel }}</span>
          </div>
          <p class="section-note">{{ driftDecisionSummary }}</p>
          <ul>
            <li>Intended behavior: {{ driftAnalysis.expected_outcome || 'unspecified' }}</li>
            <li>Observed implementation behavior: {{ driftAnalysis.observed_outcome || 'unspecified' }}</li>
            <li>Next decision: {{ driftAnalysis.recommended_fix }}</li>
            <li v-if="driftAnalysis.diagnostic_evidence.capability_id">Capability: {{ driftAnalysis.diagnostic_evidence.capability_id }}</li>
            <li v-if="driftAnalysis.diagnostic_evidence.reason_code">Reason code: {{ driftAnalysis.diagnostic_evidence.reason_code }}</li>
            <li v-if="driftAnalysis.diagnostic_evidence.agent_behavior">Agent behavior: {{ driftAnalysis.diagnostic_evidence.agent_behavior }}</li>
            <li v-if="driftAnalysis.diagnostic_evidence.backend_context">Backend context: {{ driftAnalysis.diagnostic_evidence.backend_context }}</li>
            <li v-if="driftAnalysis.diagnostic_evidence.observation_source">Evidence source: {{ driftAnalysis.diagnostic_evidence.observation_source }}</li>
            <li v-if="driftAnalysis.diagnostic_evidence.observed_at">Observed at: {{ driftAnalysis.diagnostic_evidence.observed_at }}</li>
            <li v-if="driftAnalysis.diagnostic_evidence.service_metadata_artifact_id">Metadata artifact: {{ driftAnalysis.diagnostic_evidence.service_metadata_artifact_id }}</li>
            <li v-if="driftAnalysis.diagnostic_evidence.service_metadata_mismatch">Metadata mismatch: {{ driftAnalysis.diagnostic_evidence.service_metadata_mismatch }}</li>
          </ul>
        </template>
        <p v-else class="section-note">No validation decision summary is available for this evaluation yet.</p>
      </div>

      <div class="section" v-if="serviceMetadataComparison">
        <h2>Intended Design vs Observed Implementation</h2>
        <p class="section-note">{{ serviceMetadataDecisionSummary }}</p>
        <label
          v-if="availableObservedMetadataArtifacts.length > 1"
          class="runtime-attach-toggle"
        >
          <span>Observed metadata snapshot</span>
          <select v-model="selectedObservedMetadataArtifactId" class="runtime-select" :disabled="readOnlyMode">
            <option :value="null">Best current match</option>
            <option
              v-for="item in availableObservedMetadataArtifacts"
              :key="item.id"
              :value="item.id"
            >
              {{ item.title }}
            </option>
          </select>
        </label>
        <div class="metadata-compare-grid">
          <div class="metadata-compare-card">
            <h3>Intended Design</h3>
            <ul>
              <li>Shape: {{ serviceMetadataComparison.intended.shape_type || 'unspecified' }}</li>
              <li>
                Services:
                {{ serviceMetadataComparison.intended.services.length ? serviceMetadataComparison.intended.services.join(', ') : 'none listed' }}
              </li>
              <li>
                Capabilities:
                {{ serviceMetadataComparison.intended.capabilities.length ? serviceMetadataComparison.intended.capabilities.join(', ') : 'none listed' }}
              </li>
              <li>
                Declared surfaces:
                {{ serviceMetadataComparison.intended.declared_surfaces.length ? serviceMetadataComparison.intended.declared_surfaces.join(', ') : 'none declared' }}
              </li>
            </ul>
          </div>
          <div class="metadata-compare-card">
            <h3>Observed Implementation</h3>
            <ul>
              <li>Service: {{ serviceMetadataComparison.observed.service_id || serviceMetadataComparison.observed.base_url || 'unknown' }}</li>
              <li>Protocol: {{ serviceMetadataComparison.observed.protocol || 'unknown' }}</li>
              <li>Profile: {{ serviceMetadataComparison.observed.profile || 'unknown' }}</li>
              <li>Trust: {{ serviceMetadataComparison.observed.trust_level || 'unknown' }}</li>
              <li>Manifest version: {{ serviceMetadataComparison.observed.manifest_version || 'unknown' }}</li>
              <li>Signature: {{ serviceMetadataComparison.observed.signature_present === null ? 'not inspected' : serviceMetadataComparison.observed.signature_present ? 'present' : 'missing' }}</li>
              <li>JWKS URI: {{ serviceMetadataComparison.observed.jwks_uri_present === null ? 'not inspected' : serviceMetadataComparison.observed.jwks_uri_present ? 'present' : 'missing' }}</li>
              <li v-if="observedServiceMetadataSource">
                Source: {{ observedServiceMetadataSource.label }}<template v-if="observedServiceMetadataSource.detail"> ({{ observedServiceMetadataSource.detail }})</template>
              </li>
              <li>
                Capabilities:
                {{ serviceMetadataComparison.observed.capabilities.length ? serviceMetadataComparison.observed.capabilities.map((item) => item.id).join(', ') : 'none observed' }}
              </li>
            </ul>
          </div>
        </div>
        <ul>
          <li>
            Aligned capabilities:
            {{ serviceMetadataComparison.aligned_capabilities.length ? serviceMetadataComparison.aligned_capabilities.join(', ') : 'none yet' }}
          </li>
          <li>
            Missing from implementation:
            {{ serviceMetadataComparison.missing_capabilities.length ? serviceMetadataComparison.missing_capabilities.join(', ') : 'none' }}
          </li>
          <li>
            Broader than intended:
            {{ serviceMetadataComparison.extra_capabilities.length ? serviceMetadataComparison.extra_capabilities.join(', ') : 'none' }}
          </li>
        </ul>
        <div v-if="serviceMetadataComparison.conformance_checks.length" class="surface-evidence">
          <h3 class="runtime-history-title">ANIP Conformance Checks</h3>
          <ul class="runtime-history-list">
            <li v-for="item in serviceMetadataComparison.conformance_checks" :key="item.id">
              <span class="runtime-history-capability">{{ item.label }}</span>
              <span class="runtime-history-meta">{{ item.status }}</span>
              <span class="runtime-history-meta">{{ item.source }}</span>
              <span class="runtime-history-meta">{{ item.detail }}</span>
            </li>
          </ul>
        </div>
        <div v-if="serviceMetadataComparison.surface_evidence.length" class="surface-evidence">
          <h3 class="runtime-history-title">Declared Surface Evidence</h3>
          <ul class="runtime-history-list">
            <li v-for="item in serviceMetadataComparison.surface_evidence" :key="item.surface">
              <span class="runtime-history-capability">{{ item.surface }}</span>
              <span class="runtime-history-meta">{{ item.status }}</span>
              <span class="runtime-history-meta">{{ item.detail }}</span>
            </li>
          </ul>
        </div>
      </div>

      <div class="section" v-if="normalizedObservedServiceEvidence">
        <div class="contract-context-header">
          <h2>Normalized Observed Service Evidence</h2>
          <span
            class="source-badge"
            :class="normalizedObservedServiceEvidence.status === 'ready' ? 'stored' : normalizedObservedServiceEvidence.status === 'stale' ? 'stale' : 'live'"
          >
            {{ normalizedObservedServiceEvidence.label }}
          </span>
        </div>
        <p class="section-note">
          {{ normalizedObservedServiceEvidence.detail }}
        </p>
        <div class="contract-context-grid">
          <div class="contract-context-row">
            <span>Source</span>
            <strong>{{ isLive ? 'Current evaluation context' : 'Saved evaluation evidence' }}</strong>
          </div>
          <div class="contract-context-row">
            <span>Observed service</span>
            <strong>{{ normalizedObservedServiceEvidence.service }}</strong>
          </div>
          <div class="contract-context-row">
            <span>Observed protocol</span>
            <strong>{{ normalizedObservedServiceEvidence.protocol }}</strong>
          </div>
          <div class="contract-context-row">
            <span>Observed profile</span>
            <strong>{{ normalizedObservedServiceEvidence.profile }}</strong>
          </div>
          <div class="contract-context-row">
            <span>Expected services</span>
            <strong>{{ normalizedObservedServiceEvidence.expectedServices?.length ? normalizedObservedServiceEvidence.expectedServices.join(', ') : 'Not defined' }}</strong>
          </div>
          <div class="contract-context-row">
            <span>Expected protocols</span>
            <strong>{{ normalizedObservedServiceEvidence.expectedProtocols?.length ? normalizedObservedServiceEvidence.expectedProtocols.join(', ') : 'Not defined' }}</strong>
          </div>
        </div>
        <ul>
          <li>
            Aligned capabilities:
            {{ normalizedObservedServiceEvidence.alignedCapabilities?.length ? normalizedObservedServiceEvidence.alignedCapabilities.join(', ') : 'none yet' }}
          </li>
          <li>
            Missing from implementation:
            {{ normalizedObservedServiceEvidence.missingCapabilities?.length ? normalizedObservedServiceEvidence.missingCapabilities.join(', ') : 'none' }}
          </li>
          <li>
            Broader than intended:
            {{ normalizedObservedServiceEvidence.extraCapabilities?.length ? normalizedObservedServiceEvidence.extraCapabilities.join(', ') : 'none' }}
          </li>
        </ul>
      </div>

      <div v-if="runtimeObservations" class="section">
        <h2>Runtime Observations</h2>
        <ul>
          <li v-if="runtimeObservations.source">Source: {{ runtimeObservations.source }}</li>
          <li v-if="runtimeObservations.invoked_capability">Invoked capability: {{ runtimeObservations.invoked_capability }}</li>
          <li v-if="runtimeObservations.observed_at">Observed at: {{ runtimeObservations.observed_at }}</li>
          <li v-if="runtimeObservations.observed_outcome">Observed outcome: {{ runtimeObservations.observed_outcome }}</li>
          <li v-if="runtimeObservations.reason_code">Reason code: {{ runtimeObservations.reason_code }}</li>
          <li v-if="runtimeObservations.agent_behavior">Agent behavior: {{ runtimeObservations.agent_behavior }}</li>
          <li v-if="runtimeObservations.backend_context">Backend context: {{ runtimeObservations.backend_context }}</li>
          <li v-if="runtimeObservations.unresolved_inputs?.length">
            Unresolved inputs: {{ runtimeObservations.unresolved_inputs.join(', ') }}
          </li>
          <li v-if="runtimeObservations.invocation_id">
            Invocation ID:
            <router-link
              v-if="runtimeObservationAuditQuery"
              class="inline-link"
              :to="runtimeObservationAuditQuery"
            >
              {{ runtimeObservations.invocation_id }}
            </router-link>
            <template v-else>{{ runtimeObservations.invocation_id }}</template>
          </li>
        </ul>
        <div v-if="runtimeObservationHistory.length > 1" class="runtime-history">
          <h3 class="runtime-history-title">Observation History</h3>
          <ul class="runtime-history-list">
            <li
              v-for="item in runtimeObservationHistory"
              :key="item.observation_id || `${item.invoked_capability}:${item.invocation_id || item.observed_at || 'runtime'}`"
            >
              <span class="runtime-history-capability">{{ item.invoked_capability || 'unknown' }}</span>
              <span v-if="item.source" class="runtime-history-meta">{{ item.source }}</span>
              <span v-if="item.invocation_id" class="runtime-history-meta">{{ item.invocation_id }}</span>
              <span v-if="item.observed_outcome" class="runtime-history-meta">{{ item.observed_outcome }}</span>
            </li>
          </ul>
        </div>
      </div>

      <!-- Notes -->
      <div class="section" v-if="evaluation.notes && evaluation.notes.length">
        <h2>Notes</h2>
        <ul class="notes-list">
          <li v-for="(note, i) in evaluation.notes" :key="i">{{ note }}</li>
        </ul>
      </div>
    </template>
  </div>
  <div v-else class="not-found">Evaluation not found.</div>
</template>

<style scoped>
.evaluation-view {
  padding: 2rem;
  max-width: 800px;
}

.breadcrumb-row {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  margin-bottom: 0.75rem;
  font-size: 12px;
  color: var(--text-muted);
}

.breadcrumb-row a {
  color: #93c5fd;
  text-decoration: none;
}

.breadcrumb-row a:hover {
  text-decoration: underline;
}

.header-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
}

.page-title {
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.empty-evaluation {
  margin: 1rem 0 1.5rem;
  padding: 0.9rem 1rem;
  border: 1px dashed var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  background: var(--bg-input);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.source-badge {
  display: inline-block;
  font-size: 11px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 10px;
}

.source-badge.live {
  background: rgba(59, 130, 246, 0.15);
  color: #3b82f6;
}

.source-badge.precomputed {
  background: rgba(156, 163, 175, 0.15);
  color: #9ca3af;
}

.source-badge.stored {
  background: rgba(52, 211, 153, 0.15);
  color: #34d399;
}

.source-badge.stale {
  background: rgba(251, 191, 36, 0.15);
  color: #fbbf24;
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

.run-btn {
  font-size: 12px;
  font-weight: 600;
  padding: 5px 14px;
  border-radius: 6px;
  border: 1px solid rgba(59, 130, 246, 0.4);
  background: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
  cursor: pointer;
  transition: background 0.15s;
}

.run-btn:hover {
  background: rgba(59, 130, 246, 0.2);
}

.reset-btn {
  font-size: 12px;
  font-weight: 500;
  padding: 5px 12px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: background 0.15s;
}

.reset-btn:hover {
  background: rgba(156, 163, 175, 0.1);
}

.spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(59, 130, 246, 0.3);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.validation-error {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #ef4444;
  font-size: 13px;
  padding: 8px 12px;
  border-radius: 6px;
  margin-bottom: 1rem;
}

.result-badge {
  display: inline-block;
  font-size: 13px;
  font-weight: 700;
  padding: 4px 14px;
  border-radius: 14px;
  margin-bottom: 0.75rem;
}

.result-handled {
  background: rgba(52, 211, 153, 0.15);
  color: var(--design-handled, #34d399);
}

.result-partial {
  background: rgba(251, 191, 36, 0.15);
  color: var(--design-partial, #fbbf24);
}

.result-requires-glue {
  background: rgba(248, 113, 113, 0.15);
  color: var(--design-glue, #f87171);
}

/* Confidence */
.confidence {
  margin-bottom: 1rem;
  font-size: 13px;
}

.confidence-label {
  color: var(--text-muted);
  font-weight: 500;
  margin-right: 6px;
}

.confidence-value {
  color: var(--text-secondary);
  font-weight: 600;
}

/* Categories */
.categories-section {
  margin-bottom: 1.5rem;
}

.categories-section h2 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 0.5rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border);
}

.pill-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.cat-pill {
  display: inline-block;
  font-size: 12px;
  font-weight: 600;
  padding: 3px 12px;
  border-radius: 12px;
  border: 1px solid;
}

.section {
  margin-bottom: 1.5rem;
}

.section h2 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 0.5rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border);
}

.section ul {
  list-style: disc;
  padding-left: 1.25rem;
  margin: 0;
}

.section li {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: 0.25rem;
}

.section-note {
  margin: 0 0 0.75rem;
  color: var(--text-secondary);
  line-height: 1.55;
}

.inline-link {
  color: var(--accent);
  text-decoration: none;
}

.inline-link:hover {
  text-decoration: underline;
}

.glue-pill {
  background: rgba(249, 115, 22, 0.08);
  border-color: rgba(249, 115, 22, 0.22);
  color: #c2410c;
  text-transform: capitalize;
}

.glue-list li {
  color: var(--design-glue, #f87171);
}

.notes-list li {
  color: var(--text-muted);
  font-style: italic;
}

.runtime-history {
  margin-top: 12px;
}

.metadata-compare-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}

.metadata-compare-card {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-input);
  padding: 0.9rem 1rem;
}

.metadata-compare-card h3 {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.surface-evidence {
  margin-top: 12px;
}

.runtime-history-title {
  font-size: 13px;
  font-weight: 600;
  margin: 0 0 8px;
  color: var(--text-primary);
}

.runtime-history-list {
  list-style: none;
  padding-left: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.runtime-history-list li {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 0;
}

.runtime-history-capability {
  font-weight: 600;
  color: var(--text-primary);
}

.runtime-history-meta {
  font-size: 11px;
  color: var(--text-muted);
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.contract-context {
  margin-bottom: 1rem;
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg-card);
}

.contract-context-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.contract-context-header h2 {
  margin: 0;
  font-size: 15px;
}

.contract-context-header.nested {
  margin-top: 12px;
}

.contract-context-header.nested h3 {
  margin: 0;
  font-size: 14px;
}

.contract-context-copy {
  margin: 0 0 10px;
  font-size: 13px;
  color: var(--text-secondary);
}

.contract-context-divider {
  height: 1px;
  margin: 12px 0;
  background: var(--border);
}

.contract-context-grid {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.contract-context-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
  font-size: 12px;
}

.contract-context-row span {
  color: var(--text-muted);
}

.contract-context-row strong {
  color: var(--text-primary);
  word-break: break-all;
  text-align: right;
}

/* Save to Project */
.save-section {
  margin-bottom: 1rem;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.runtime-attach-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text-secondary);
}

.runtime-select {
  height: 30px;
  padding: 0 8px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: var(--bg-input);
  color: var(--text-primary);
  font-size: 12px;
}

.runtime-input {
  min-width: 180px;
}

.runtime-import-row {
  flex-wrap: wrap;
}

.import-btn {
  padding-inline: 12px;
}

.runtime-audit-browser {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.runtime-audit-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.approval-nav-btn {
  background: rgba(59, 130, 246, 0.12);
  color: var(--accent);
}

.audit-trace-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.audit-trace-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  text-align: left;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--bg-input);
  color: var(--text-primary);
  cursor: pointer;
}

.audit-trace-item:hover {
  border-color: var(--border-focus);
  background: rgba(59, 130, 246, 0.06);
}

.audit-trace-capability {
  font-size: 12px;
  font-weight: 600;
}

.audit-trace-meta {
  font-size: 11px;
  color: var(--text-muted);
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.save-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  padding: 6px 16px;
  border-radius: 6px;
  border: 1px solid rgba(52, 211, 153, 0.4);
  background: rgba(52, 211, 153, 0.1);
  color: #34d399;
  cursor: pointer;
  transition: background 0.15s;
}

.save-btn:hover:not(:disabled) {
  background: rgba(52, 211, 153, 0.2);
}

.save-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.save-warning {
  font-size: 13px;
  color: #fbbf24;
  background: rgba(251, 191, 36, 0.1);
  border: 1px solid rgba(251, 191, 36, 0.3);
  padding: 8px 12px;
  border-radius: 6px;
}

.save-error {
  font-size: 13px;
  color: #ef4444;
}

.save-success {
  font-size: 13px;
  font-weight: 500;
  color: #34d399;
}

.spinner.small {
  width: 12px;
  height: 12px;
  border-width: 1.5px;
}

.not-found {
  padding: 2rem;
  color: var(--text-muted);
}

/* Stale notice */
.stale-section {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 1rem;
  padding: 10px 14px;
  background: rgba(251, 191, 36, 0.08);
  border: 1px solid rgba(251, 191, 36, 0.3);
  border-radius: 6px;
}

.stale-notice {
  flex: 1;
  font-size: 13px;
  color: #fbbf24;
}

.stale-icon {
  margin-right: 6px;
}

.stale-details {
  font-weight: 500;
  margin-left: 4px;
}

.stale-contract-note {
  width: 100%;
  font-size: 12px;
  color: var(--text-secondary);
}

.reevaluate-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  padding: 5px 14px;
  border-radius: 6px;
  border: 1px solid rgba(251, 191, 36, 0.4);
  background: rgba(251, 191, 36, 0.1);
  color: #fbbf24;
  cursor: pointer;
  transition: background 0.15s;
}

.reevaluate-btn:hover:not(:disabled) {
  background: rgba(251, 191, 36, 0.2);
}

.reevaluate-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
