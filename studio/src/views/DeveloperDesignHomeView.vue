<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  createPmArtifact,
  deletePmArtifact,
  deleteSavedApplicationIntegrationProject,
  deleteSavedDataAccessProject,
  getSavedApplicationIntegrationProject,
  getSavedDataAccessProject,
  listIntegrationDiscoveryRecords,
  listSavedApplicationIntegrationProjects,
  listSavedDataAccessProjects,
  updatePmArtifact,
} from '../design/project-api'
import { requestConfirmation } from '../design/confirm'
import { buildProjectIssueIndex } from '../design/project-issues'
import {
  buildDeveloperDefinitionSufficiencyCards,
  buildDeveloperDefinitionData,
  developerDefinitionMatchesCurrentContext,
  developerDefinitionTargetStatus,
  findDeveloperDefinitionArtifact,
  findLatestDeveloperGenerationRunArtifact,
  resolveCompiledContractAlignment,
  resolveEvaluationCompiledContractIdentity,
  resolveEvaluationEvidenceEnvelope,
  resolveEvaluationObservedServiceEvidence,
  resolveEvaluationServiceMetadataSnapshot,
  resolveGenerationContractAlignment,
  resolveIntegrationFrontingBackendBindingsHealth,
  resolveObservedServiceEvidence,
} from '../design/developer-definition'
import {
  buildProductDesignRevision,
  findLatestProductDesignRevisionArtifact,
  productDesignSourceHash,
  type ProductDesignRevisionData,
} from '../design/product-design'
import {
  analyzeAgentConsumptionReadiness,
  applyReadinessFindingReviews,
  normalizeReadinessFindingReviews,
} from '../design/agent-consumption-readiness'
import { loadProject, projectStore } from '../design/project-store'
import type {
  DesignSectionSufficiencyCard,
  DeveloperBaselineData,
  DeveloperDefinitionData,
  DeveloperGenerationRunData,
  IntegrationDiscoveryRecord,
  TraceabilityRecordData,
} from '../design/project-types'
import { formatStudioTimestamp } from '../design/time'
import {
  buildDeveloperBaseline,
  developerBaselineArtifactId,
  developerBaselineMatchesCurrentContext,
  developerStatusLabel,
  findDeveloperBaselineArtifact,
  findTraceabilityArtifact,
  pmReviewStatusLabel,
  summarizeCoverage,
} from '../design/traceability'
import DeveloperDesignMap, {
  type DeveloperDesignMapGroup,
  type DeveloperDesignMapStatus,
} from '../design/components/DeveloperDesignMap.vue'
import {
  summarizeDeveloperDesignBlocks,
  type DeveloperDesignContextBlock,
} from '../design/developer-design-context'
import { developerLabel } from '../design/developer-vocabulary'
import { showTechnicalIdentifiers } from '../design/technical-display'

const route = useRoute()
const router = useRouter()

const projectId = computed(() => route.params.projectId as string)
const project = computed(() => projectStore.activeProject)
const requirements = computed(() => projectStore.artifacts.requirements)
const scenarios = computed(() => projectStore.artifacts.scenarios)
const shapes = computed(() => projectStore.artifacts.shapes)
const evaluations = computed(() => projectStore.artifacts.evaluations)
const isGovernedFrontingProject = computed(() => project.value?.project_type === 'governed_service_project')
const frontingContractSeedReady = computed(() => isGovernedFrontingProject.value)
const developerSufficiencyKeysForGovernedFronting = new Set([
  'service_identity_topology',
  'capability_contracts',
  'authority_and_approval',
  'backend_bindings',
  'audit_and_lineage',
  'generation_and_extensions',
])

const savingBaseline = ref(false)
const resettingDeveloperDesign = ref(false)
const baselineError = ref<string | null>(null)
const discoveryRecords = ref<IntegrationDiscoveryRecord[]>([])

async function ensureLoaded() {
  if (!projectId.value) return
  if (projectStore.activeProject?.id !== projectId.value) {
    await loadProject(projectId.value)
  }
  if (projectStore.activeProject?.project_type === 'governed_service_project') {
    discoveryRecords.value = await listIntegrationDiscoveryRecords(projectId.value)
  } else {
    discoveryRecords.value = []
  }
}

onMounted(ensureLoaded)
watch(projectId, ensureLoaded)

const currentRequirements = computed(() =>
  requirements.value.find((item) => item.role === 'primary')
  ?? requirements.value[0]
  ?? null,
)

const currentScenarios = computed(() => scenarios.value)

const currentShape = computed(() =>
  shapes.value.find((item) => item.id === projectStore.activeShapeId)
  ?? (shapes.value.length === 1 ? shapes.value[0] : null)
  ?? shapes.value[0]
  ?? null,
)

const primaryScenario = computed(() =>
  scenarios.value.find((item) => item.id === projectStore.activeScenarioId)
  ?? scenarios.value[0]
  ?? null,
)

const latestEvaluation = computed(() => {
  const records = [...evaluations.value]
  records.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
  return records[0] ?? null
})

const baselineArtifact = computed(() => findDeveloperBaselineArtifact(projectStore.artifacts.pmArtifacts))
const baseline = computed(() =>
  (baselineArtifact.value?.data as DeveloperBaselineData | undefined) ?? null,
)
const baselineAligned = computed(() =>
  developerBaselineMatchesCurrentContext({
    baseline: baseline.value,
    requirements: currentRequirements.value,
    scenarios: currentScenarios.value,
    shape: currentShape.value,
    pmArtifacts: projectStore.artifacts.pmArtifacts,
  }),
)

const lockedRequirements = computed(() =>
  requirements.value.find((item) => item.id === baseline.value?.source_inputs.requirements_id)
  ?? null,
)

const lockedScenarios = computed(() =>
  (baseline.value?.source_inputs.scenario_ids ?? [])
    .map((id) => scenarios.value.find((item) => item.id === id) ?? null)
    .filter((item): item is NonNullable<typeof item> => item != null),
)

const lockedPrimaryScenario = computed(() =>
  scenarios.value.find((item) => item.id === baseline.value?.source_inputs.primary_scenario_id)
  ?? lockedScenarios.value[0]
  ?? null,
)

const lockedShape = computed(() =>
  shapes.value.find((item) => item.id === baseline.value?.source_inputs.shape_id)
  ?? null,
)

const traceabilityArtifact = computed(() => findTraceabilityArtifact(projectStore.artifacts.pmArtifacts))
const traceabilityRecord = computed(() =>
  (traceabilityArtifact.value?.data as TraceabilityRecordData | undefined) ?? null,
)
const definitionArtifact = computed(() => findDeveloperDefinitionArtifact(projectStore.artifacts.pmArtifacts))
const developerDefinition = computed(() =>
  (definitionArtifact.value?.data as DeveloperDefinitionData | undefined) ?? null,
)
const compiledContractIdentity = computed(() => developerDefinition.value?.compiled_contract_identity ?? null)
const latestGenerationRunArtifact = computed(() => findLatestDeveloperGenerationRunArtifact(projectStore.artifacts.pmArtifacts))
const latestGenerationRun = computed(() =>
  (latestGenerationRunArtifact.value?.data as DeveloperGenerationRunData | undefined) ?? null,
)
const latestGenerationRunEvaluation = computed(() => {
  const targetRunId = latestGenerationRunArtifact.value?.id ?? null
  if (!targetRunId) return null
  const records = [...evaluations.value].filter((record) => {
    const envelope = resolveEvaluationEvidenceEnvelope(record as any)
    return envelope?.generation_run_artifact_id === targetRunId
  })
  records.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
  return records[0] ?? null
})
const latestGenerationRunObservedArtifacts = computed(() => {
  const targetRunId = latestGenerationRunArtifact.value?.id ?? null
  if (!targetRunId) return []
  const artifacts = [...projectStore.artifacts.serviceMetadata].filter((artifact) =>
    artifact.data?.generation_run_artifact_id === targetRunId,
  )
  artifacts.sort((a, b) => new Date(b.updated_at || b.created_at).getTime() - new Date(a.updated_at || a.created_at).getTime())
  return artifacts
})
const latestEvaluationContractIdentity = computed(() =>
  resolveEvaluationCompiledContractIdentity(latestGenerationRunEvaluation.value as any),
)
const contractAlignment = computed(() =>
  resolveCompiledContractAlignment(compiledContractIdentity.value as any, latestEvaluationContractIdentity.value as any),
)
const generationAlignment = computed(() =>
  resolveGenerationContractAlignment(compiledContractIdentity.value as any, latestGenerationRun.value?.compiled_contract_identity as any),
)
const latestGenerationRunObservedServiceEvidence = computed(() =>
  resolveEvaluationObservedServiceEvidence(latestGenerationRunEvaluation.value as any),
)
const latestGenerationRunEvaluationServiceMetadata = computed(() =>
  resolveEvaluationServiceMetadataSnapshot(latestGenerationRunEvaluation.value as any),
)
const latestGenerationRunObservedSummary = computed(() =>
  resolveObservedServiceEvidence({
    definition: developerDefinition.value as any,
    currentContractIdentity: compiledContractIdentity.value as any,
    generationRun: latestGenerationRun.value as any,
    generationRunArtifactId: latestGenerationRunArtifact.value?.id ?? null,
    observedArtifacts: latestGenerationRunObservedArtifacts.value,
    evaluationObservedEvidence: latestGenerationRunObservedServiceEvidence.value as any,
    evaluationSnapshot: latestGenerationRunEvaluationServiceMetadata.value as any,
  }),
)
const latestGenerationRunEvidenceSummary = computed(() => [
  {
    key: 'generation',
    label: 'Generation evidence',
    value: latestGenerationRun.value ? generationAlignment.value.label : 'Not recorded',
    detail: latestGenerationRunArtifact.value?.id ?? 'No saved generation run',
    ready: Boolean(latestGenerationRun.value) && generationAlignment.value.status === 'aligned',
  },
  {
    key: 'local-proof',
    label: 'Local proof',
    value: latestGenerationRunEvaluation.value ? 'Recorded' : 'Missing',
    detail: latestGenerationRunEvaluation.value?.id ?? 'No evaluation saved for this generation run',
    ready: Boolean(latestGenerationRunEvaluation.value),
  },
  {
    key: 'observed-service',
    label: 'Observed service evidence',
    value: latestGenerationRunObservedSummary.value.label,
    detail: latestGenerationRunObservedSummary.value.artifactId || latestGenerationRunObservedSummary.value.detail,
    ready: latestGenerationRunObservedSummary.value.status === 'ready',
  },
  {
    key: 'evaluation',
    label: 'Evaluation evidence',
    value: latestGenerationRunEvaluation.value ? contractAlignment.value.label : 'Missing',
    detail: latestGenerationRunEvaluation.value
      ? latestGenerationRunEvaluation.value.id
      : 'No evaluation evidence tied to the latest generation run',
    ready: Boolean(latestGenerationRunEvaluation.value) && contractAlignment.value.status === 'aligned',
  },
])
const developerDefinitionAligned = computed(() =>
  developerDefinitionMatchesCurrentContext({
    definition: developerDefinition.value,
    baseline: baseline.value,
    requirements: currentRequirements.value,
    scenarios: currentScenarios.value,
    shape: currentShape.value,
  }),
)
const currentDeveloperDefinitionDraft = computed<DeveloperDefinitionData | null>(() => {
  if (!project.value || !baseline.value || !baselineAligned.value || !currentRequirements.value || currentScenarios.value.length === 0) {
    return null
  }
  if (!isGovernedFrontingProject.value && !currentShape.value) {
    return null
  }
  return buildDeveloperDefinitionData({
    project: project.value,
    baseline: baseline.value,
    requirements: currentRequirements.value,
    scenarios: currentScenarios.value,
    shape: currentShape.value,
    pmArtifacts: projectStore.artifacts.pmArtifacts,
    existing: developerDefinition.value,
  })
})
const coverageMatchesBaseline = computed(() => {
  if (!traceabilityRecord.value || !baseline.value) return false
  return (
    traceabilityRecord.value.source_inputs.requirements_id === baseline.value.source_inputs.requirements_id
    && traceabilityRecord.value.source_inputs.scenario_id === baseline.value.source_inputs.primary_scenario_id
    && traceabilityRecord.value.source_inputs.shape_id === baseline.value.source_inputs.shape_id
    && traceabilityRecord.value.source_inputs.baseline_locked_at === baseline.value.locked_at
  )
})
const effectiveCoverageItems = computed(() => {
  if (!coverageMatchesBaseline.value) return []
  const coverage = (traceabilityArtifact.value?.data as { coverage?: any[] } | undefined)?.coverage ?? []
  const effectiveDefinition = currentDeveloperDefinitionDraft.value ?? developerDefinition.value
  return coverage.map((item) => {
    const mappingMode = String(item.mapping_mode ?? '')
    const mappingTargetKey = String(item.mapping_target_key ?? '')
    if (mappingMode !== 'automatic' || !mappingTargetKey) return item
    return {
      ...item,
      status: developerDefinitionTargetStatus(mappingTargetKey, {
        developerDefinition: effectiveDefinition,
      }),
    }
  })
})
const coverageSummary = computed(() =>
  summarizeCoverage(effectiveCoverageItems.value),
)

const reviewedAgentReadinessReport = computed(() => {
  if (!developerDefinition.value) return null
  return applyReadinessFindingReviews(
    analyzeAgentConsumptionReadiness(developerDefinition.value),
    normalizeReadinessFindingReviews(traceabilityRecord.value?.agent_consumption_readiness?.finding_reviews),
  )
})

const productPrerequisites = computed(() => [
  {
    label: 'Requirements baseline exists',
    ready: !!currentRequirements.value,
    detail: currentRequirements.value ? currentRequirements.value.title : 'Create a requirements set in Product Design.',
  },
  {
    label: 'Scenario pack exists',
    ready: currentScenarios.value.length > 0,
    detail: currentScenarios.value.length > 0 ? `${currentScenarios.value.length} scenarios recorded` : 'Create at least one scenario in Product Design.',
  },
  {
    label: isGovernedFrontingProject.value ? 'Fronting evidence starts from source docs' : 'Implementation service design is chosen',
    ready: isGovernedFrontingProject.value ? frontingContractSeedReady.value : !!currentShape.value,
    detail: isGovernedFrontingProject.value
      ? 'Backend type is captured as connection and operation metadata, not as contract identity.'
      : currentShape.value
        ? currentShape.value.title
        : 'Choose the service design that should be implemented, then return here to lock it.',
  },
  {
    label: 'Developer baseline is locked',
    ready: !!baseline.value && baselineAligned.value,
    detail:
      baseline.value && baselineAligned.value
        ? baseline.value.source_inputs.product_revision_number
          ? `Product Revision ${baseline.value.source_inputs.product_revision_number} locked ${formatStudioTimestamp(baseline.value.locked_at)}`
          : `Locked ${formatStudioTimestamp(baseline.value.locked_at)}`
        : baseline.value
          ? 'Product Design changed after the baseline was locked. Re-lock it to create the next Product Revision before continuing.'
          : 'Lock the current Product Design baseline before developer work begins.',
  },
  {
    label: 'Developer definition is saved',
    ready: !!developerDefinition.value && developerDefinitionAligned.value,
    detail:
      developerDefinition.value && developerDefinitionAligned.value
        ? developerDefinition.value.saved_revision
          ? `Revision ${developerDefinition.value.saved_revision.revision_number} saved ${formatStudioTimestamp(developerDefinition.value.saved_revision.saved_at)}`
          : `Legacy saved state from ${formatStudioTimestamp(developerDefinition.value.saved_at || new Date().toISOString())}`
        : developerDefinition.value
          ? 'The saved developer definition no longer matches the locked baseline. Open Developer Definition and save it again.'
          : 'Save the generation-driving developer definition before implementation work begins.',
  },
])

const productReady = computed(() =>
  !!currentRequirements.value
  && currentScenarios.value.length > 0
  && (isGovernedFrontingProject.value ? frontingContractSeedReady.value : !!currentShape.value)
  && productBlockingIssueSummary.value.count === 0,
)

const developerReady = computed(() =>
  productReady.value && !!baseline.value && baselineAligned.value,
)

const frontingBindingHealth = computed(() =>
  (developerDefinition.value?.integration_fronting?.capability_mappings ?? []).map((mapping) => ({
    capabilityId: mapping.capability_id,
    serviceId: mapping.service_id,
    health: resolveIntegrationFrontingBackendBindingsHealth(mapping.backend_bindings ?? [], discoveryRecords.value),
  })),
)
const staleFrontingBindingCount = computed(() =>
  frontingBindingHealth.value.filter((entry) => entry.health.status === 'stale').length,
)
const missingFrontingBindingCount = computed(() =>
  frontingBindingHealth.value.filter((entry) => entry.health.status === 'missing').length,
)

const inconsistencyItems = computed(() => {
  const issues: string[] = []
  if (!baseline.value && productReady.value) {
    issues.push('Developer Design has not been started from a locked Product Design baseline.')
  }
  if (baseline.value && !baselineAligned.value) {
    issues.push('Product Design changed after the current baseline was locked. Re-lock the baseline before continuing developer work.')
  }
  if (developerReady.value && !traceabilityRecord.value) {
    issues.push('Coverage Mapping has not been created for the locked baseline.')
  }
  if (developerReady.value && !developerDefinition.value) {
    issues.push('Developer Definition has not been saved yet. Generation settings, naming, protocols, and service strategy are still undefined.')
  }
  if (developerDefinition.value && !developerDefinitionAligned.value) {
    issues.push('The saved Developer Definition does not match the current locked baseline.')
  }
  if (traceabilityRecord.value && !coverageMatchesBaseline.value) {
    issues.push('The saved Coverage Mapping record does not match the current locked baseline.')
  }
  if (coverageMatchesBaseline.value && coverageSummary.value.missing > 0) {
    issues.push(`${coverageSummary.value.missing} Product Design item${coverageSummary.value.missing === 1 ? '' : 's'} are still not addressed.`)
  }
  if (coverageMatchesBaseline.value && coverageSummary.value.partial > 0) {
    issues.push(`${coverageSummary.value.partial} Product Design item${coverageSummary.value.partial === 1 ? '' : 's'} are only partially addressed.`)
  }
  if (traceabilityRecord.value?.pm_review_status === 'changes_requested') {
    issues.push('PM review is currently requesting changes.')
  }
  if (developerReady.value && latestGenerationRun.value && !latestGenerationRunEvaluation.value) {
    issues.push('No evaluation evidence exists yet for drift analysis.')
  } else if (developerReady.value && contractAlignment.value.status === 'stale') {
    issues.push('The latest evaluation evidence was captured against an older compiled contract. Re-run verification against the latest saved revision.')
  } else if (developerReady.value && latestGenerationRunEvaluation.value && contractAlignment.value.status === 'unknown') {
    issues.push('The latest evaluation does not record enough compiled contract identity to confirm alignment with the latest saved revision.')
  }
  if (developerReady.value && latestGenerationRun.value && generationAlignment.value.status === 'stale') {
    issues.push('The latest generation run was launched from an older compiled contract. Re-run generation from the latest saved revision.')
  } else if (developerReady.value && latestGenerationRun.value && generationAlignment.value.status === 'unknown') {
    issues.push('The latest generation run does not record enough compiled contract identity to confirm alignment with the latest saved revision.')
  }
  if (isGovernedFrontingProject.value && staleFrontingBindingCount.value > 0) {
    issues.push(`${staleFrontingBindingCount.value} backend binding${staleFrontingBindingCount.value === 1 ? '' : 's'} no longer match current discovery metadata.`)
  }
  if (isGovernedFrontingProject.value && missingFrontingBindingCount.value > 0) {
    issues.push(`${missingFrontingBindingCount.value} backend binding${missingFrontingBindingCount.value === 1 ? '' : 's'} are missing discovery coverage or connection metadata.`)
  }
  return issues
})

const developerIssueIndex = computed(() =>
  buildProjectIssueIndex({
    project: project.value,
    pmArtifacts: projectStore.artifacts.pmArtifacts,
    requirements: requirements.value,
    scenarios: scenarios.value,
    documents: projectStore.artifacts.documents,
    shapes: shapes.value,
  }),
)
const developerBlockSummaries = computed(() =>
  summarizeDeveloperDesignBlocks({
    projectId: project.value?.id ?? projectId.value,
    issueIndex: developerIssueIndex.value,
  }),
)
const blockingDesignIssueSummary = computed(() => {
  const issues = ['project-product-design', 'project-developer-design', 'project-developer-coverage']
    .map((key) => developerIssueIndex.value[key])
    .filter((issue) => issue?.severity === 'error')
  return {
    count: issues.reduce((total, issue) => total + (issue?.count ?? 0), 0),
    messages: issues.flatMap((issue) => issue?.messages ?? []),
  }
})
const productBlockingIssueSummary = computed(() => {
  const issue = developerIssueIndex.value['project-product-design']
  if (issue?.severity !== 'error') return { count: 0, messages: [] as string[] }
  return {
    count: issue.count,
    messages: issue.messages,
  }
})

function currentProductBlockingMessages(): string[] {
  const issue = buildProjectIssueIndex({
    project: project.value,
    pmArtifacts: projectStore.artifacts.pmArtifacts,
    requirements: requirements.value,
    scenarios: scenarios.value,
    documents: projectStore.artifacts.documents,
    shapes: shapes.value,
  })['project-product-design']
  return issue?.severity === 'error' ? issue.messages : []
}

function developerSufficiencyIssueKey(cardKey: DesignSectionSufficiencyCard['key']): string | null {
  switch (cardKey) {
    case 'service_identity_topology':
    case 'authority_and_approval':
    case 'backend_bindings':
      return 'project-developer-service-formalization'
    case 'capability_contracts':
      return 'project-developer-capability-formalization'
    case 'data_contracts':
      return 'project-developer-data-contract-formalization'
    case 'scenario_context':
      return 'project-developer-scenario-formalization'
    case 'execution_semantics':
      return 'project-developer-scenario-execution-semantics'
    case 'audit_and_lineage':
      return 'project-developer-governance-bindings'
    case 'generation_and_extensions':
      return 'project-developer-generation-settings'
    default:
      return null
  }
}

const developerSufficiencyCards = computed<DesignSectionSufficiencyCard[]>(() => {
  if (!project.value) return []
  return buildDeveloperDefinitionSufficiencyCards({
    projectId: project.value.id,
    baseline: baseline.value,
    definition: developerDefinition.value,
    definitionAligned: developerDefinitionAligned.value,
    requirements: currentRequirements.value,
    scenarios: currentScenarios.value,
    shape: currentShape.value,
    pmArtifacts: projectStore.artifacts.pmArtifacts,
    reducedFrontingProject: isGovernedFrontingProject.value,
  })
    .filter((card) => !isGovernedFrontingProject.value || developerSufficiencyKeysForGovernedFronting.has(card.key))
    .map((card) => {
      const issueKey = developerSufficiencyIssueKey(card.key)
      const pageIssue = issueKey ? developerIssueIndex.value[issueKey] : undefined
      if (!pageIssue) return card
      if (pageIssue.severity === 'error') {
        return {
          ...card,
          status: 'blocked',
          detail: pageIssue.messages[0] || card.detail,
          questions: pageIssue.messages.slice(0, 3),
        }
      }
      if (card.status === 'ready' || card.status === 'draftable') {
        return {
          ...card,
          status: 'needs_clarification',
          detail: pageIssue.messages[0] || card.detail,
          questions: pageIssue.messages.slice(0, 3),
        }
      }
      return card
    })
})
const developerClarificationCards = computed(() =>
  developerSufficiencyCards.value.filter((card) => card.status === 'needs_clarification'),
)

function statusRank(status: string): number {
  if (status === 'blocked') return 4
  if (status === 'needs_clarification') return 3
  if (status === 'draftable') return 2
  if (status === 'ready') return 1
  return 0
}

function mergedMapStatus(statuses: string[]): DeveloperDesignMapStatus {
  const worst = statuses.reduce((current, next) => (statusRank(next) > statusRank(current) ? next : current), 'ready')
  if (worst === 'blocked' || worst === 'needs_clarification' || worst === 'draftable' || worst === 'ready') return worst
  return 'blocked'
}

function sufficiencyCard(key: DesignSectionSufficiencyCard['key']): DesignSectionSufficiencyCard | null {
  return developerSufficiencyCards.value.find((card) => card.key === key) ?? null
}

function pageIssueMessages(issueKey: string): string[] {
  const issue = developerIssueIndex.value[issueKey]
  return issue?.messages?.slice(0, 2) ?? []
}

function readinessIssueMessages(): string[] {
  const report = reviewedAgentReadinessReport.value
  if (!report) return []
  if (report.status === 'blocked') {
    return [
      `Agent Consumption Readiness is blocked (score ${report.score}/100): ${report.summary.blockers} blocker${report.summary.blockers === 1 ? '' : 's'}, ${report.summary.warnings} warning${report.summary.warnings === 1 ? '' : 's'}.`,
    ]
  }
  if (report.status === 'needs_review') {
    return [
      `Agent Consumption Readiness needs review (score ${report.score}/100): ${report.summary.warnings} warning${report.summary.warnings === 1 ? '' : 's'}.`,
    ]
  }
  return []
}

function readinessMapStatus(): DeveloperDesignMapStatus {
  const report = reviewedAgentReadinessReport.value
  if (!report) return 'ready'
  if (report.status === 'blocked') return 'blocked'
  if (report.status === 'needs_review') return 'needs_clarification'
  return 'ready'
}

function mapBlockSummary(block: DeveloperDesignContextBlock) {
  return developerBlockSummaries.value[block]
}

function sourceSubPages(block: DeveloperDesignContextBlock) {
  return mapBlockSummary(block).sources.map((source) => ({
    key: source.key,
    label: source.label,
    path: source.path,
    status: source.status,
    issueCount: source.issueCount,
  }))
}

function issueAwareStatus(status: DeveloperDesignMapStatus, block: DeveloperDesignContextBlock): DeveloperDesignMapStatus {
  return mergedMapStatus([status, mapBlockSummary(block).status])
}

function issueAwareMessages(fallback: string[], block: DeveloperDesignContextBlock): string[] {
  const blockIssues = mapBlockSummary(block).issues
  return blockIssues.length ? blockIssues : fallback
}

function issueAwarePath(fallback: string, block: DeveloperDesignContextBlock): string {
  const summary = mapBlockSummary(block)
  return summary.issueCount ? summary.issuePath : fallback
}

function firstIssuePath(options: Array<{ messages: string[]; path: string }>, fallback: string): string {
  return options.find((option) => option.messages.length > 0)?.path ?? fallback
}

const developerMapGroups = computed<DeveloperDesignMapGroup[]>(() => {
  const serviceCard = sufficiencyCard('service_identity_topology')
  const capabilityCard = sufficiencyCard('capability_contracts')
  const dataCard = sufficiencyCard('data_contracts')
  const scenarioCard = sufficiencyCard('scenario_context')
  const executionCard = sufficiencyCard('execution_semantics')
  const authorityCard = sufficiencyCard('authority_and_approval')
  const backendCard = sufficiencyCard('backend_bindings')
  const lineageCard = sufficiencyCard('audit_and_lineage')
  const generationCard = sufficiencyCard('generation_and_extensions')
  const servicePath = `/design/projects/${project.value?.id}/developer/service-formalization`
  const capabilityPath = `/design/projects/${project.value?.id}/developer/capability-formalization`
  const dataPath = `/design/projects/${project.value?.id}/developer/data-contract-formalization`
  const scenarioPath = `/design/projects/${project.value?.id}/developer/scenario-formalization`
  const executionPath = `/design/projects/${project.value?.id}/developer/scenario-execution-semantics`
  const auditPath = `/design/projects/${project.value?.id}/developer/audit-lineage`
  const coveragePath = `/design/projects/${project.value?.id}/developer/app-glue`
  const generationPath = `/design/projects/${project.value?.id}/developer/generation-settings`
  const definitionPath = `/design/projects/${project.value?.id}/developer/definition`
  const coverageIssueMessages = [...new Set([...pageIssueMessages('project-developer-coverage'), ...readinessIssueMessages()])].slice(0, 2)
  const definitionIssueMessages = pageIssueMessages('project-developer-definition')

  return [
    {
      key: 'business',
      title: 'Business Handoff',
      summary: 'Freeze the Product Design truth before implementation details become contract truth.',
      blocks: [
        {
          key: 'handoff',
          title: 'Locked product baseline',
          detail: baseline.value && baselineAligned.value ? 'Product intent is frozen for Developer Design.' : 'Lock or re-lock the Product Design baseline.',
          contribution: 'Pins the Product Revision that every Developer Definition, generated contract, and package must trace back to.',
          status: issueAwareStatus(baseline.value && baselineAligned.value ? 'ready' : productReady.value ? 'draftable' : 'blocked', 'business'),
          path: `/design/projects/${project.value?.id}/developer/handoff`,
          issuePath: issueAwarePath(`/design/projects/${project.value?.id}/developer`, 'business'),
          issues: issueAwareMessages(baseline.value && baselineAligned.value ? [] : visibleInconsistencyItems.value.slice(0, 2), 'business'),
          issueCount: Math.max(mapBlockSummary('business').issueCount, baseline.value && baselineAligned.value ? 0 : visibleInconsistencyItems.value.length),
          subPages: sourceSubPages('business'),
        },
      ],
    },
    {
      key: 'contract',
      title: 'Contract Shape',
      summary: 'Define the ANIP surface: services, capabilities, data, and scenario behavior.',
      blocks: [
        {
          key: 'services',
          title: 'Service boundaries',
          detail: serviceCard?.detail ?? 'Name the services and ownership boundaries.',
          contribution: 'Defines generated service ownership, package topology, and which capabilities belong in each deployable boundary.',
          status: issueAwareStatus(serviceCard?.status ?? 'blocked', 'services'),
          path: servicePath,
          issuePath: issueAwarePath(servicePath, 'services'),
          issues: issueAwareMessages(serviceCard?.questions ?? [], 'services'),
          issueCount: Math.max(mapBlockSummary('services').issueCount, serviceCard?.questions?.length ?? 0),
          subPages: sourceSubPages('services'),
        },
        {
          key: 'capabilities',
          title: 'Capabilities and data',
          detail: capabilityCard?.status === 'ready' && dataCard?.status === 'ready'
            ? 'Capability contracts and data surfaces are formalized.'
            : 'Review capability inputs, outputs, and data surfaces.',
          contribution: 'Produces capability IDs, inputs, outputs, side effects, data contracts, and behavior fields used by generators and verifiers.',
          status: issueAwareStatus(mergedMapStatus([capabilityCard?.status ?? 'blocked', dataCard?.status ?? 'blocked']), 'capabilities'),
          path: capabilityPath,
          issuePath: issueAwarePath(firstIssuePath([
            { messages: capabilityCard?.questions ?? [], path: capabilityPath },
            { messages: dataCard?.questions ?? [], path: dataPath },
          ], capabilityPath), 'capabilities'),
          issues: issueAwareMessages([...(capabilityCard?.questions ?? []), ...(dataCard?.questions ?? [])].slice(0, 2), 'capabilities'),
          issueCount: Math.max(mapBlockSummary('capabilities').issueCount, (capabilityCard?.questions?.length ?? 0) + (dataCard?.questions?.length ?? 0)),
          subPages: sourceSubPages('capabilities'),
        },
        {
          key: 'scenarios',
          title: 'Scenario behavior',
          detail: scenarioCard?.status === 'ready' && executionCard?.status === 'ready'
            ? 'Scenario context and execution semantics are ready.'
            : 'Review scenario coverage, orchestration evidence, and expected behavior.',
          contribution: 'Keeps PM real situations visible as readiness, simulator, and verification evidence; runtime behavior still belongs in capabilities, roles, approvals, or service implementation.',
          status: issueAwareStatus(mergedMapStatus([scenarioCard?.status ?? 'blocked', executionCard?.status ?? 'blocked']), 'scenarios'),
          path: scenarioPath,
          issuePath: issueAwarePath(firstIssuePath([
            { messages: scenarioCard?.questions ?? [], path: scenarioPath },
            { messages: executionCard?.questions ?? [], path: executionPath },
          ], scenarioPath), 'scenarios'),
          issues: issueAwareMessages([...(scenarioCard?.questions ?? []), ...(executionCard?.questions ?? [])].slice(0, 2), 'scenarios'),
          issueCount: Math.max(mapBlockSummary('scenarios').issueCount, (scenarioCard?.questions?.length ?? 0) + (executionCard?.questions?.length ?? 0)),
          subPages: sourceSubPages('scenarios'),
        },
      ],
    },
    {
      key: 'controls',
      title: 'Controls and Consumability',
      summary: 'Make boundaries, approval posture, app glue, and evidence explicit before generation.',
      blocks: [
        {
          key: 'governance',
          title: 'Authority and service backends',
          detail: authorityCard?.status === 'ready' && backendCard?.status === 'ready'
            ? 'Policy and service runtime connections are formalized.'
            : 'Review approval, restrictions, and service runtime backends.',
          contribution: 'Defines scopes, approval boundaries, and explicit runtime connections that services must enforce.',
          status: issueAwareStatus(mergedMapStatus([authorityCard?.status ?? 'blocked', backendCard?.status ?? 'blocked']), 'governance'),
          path: servicePath,
          issuePath: issueAwarePath(servicePath, 'governance'),
          issues: issueAwareMessages([...(authorityCard?.questions ?? []), ...(backendCard?.questions ?? [])].slice(0, 2), 'governance'),
          issueCount: Math.max(mapBlockSummary('governance').issueCount, (authorityCard?.questions?.length ?? 0) + (backendCard?.questions?.length ?? 0)),
          subPages: sourceSubPages('governance'),
        },
        {
          key: 'consumability',
          title: 'Agent readiness and app glue',
          detail: coverageIssueMessages.length ? coverageIssueMessages[0] : 'Coverage, readiness findings, and required app glue are reviewed here.',
          contribution: 'Records Product Design coverage, agent-consumption readiness, required app glue, and reviewed limitations before publication.',
          status: issueAwareStatus(readinessMapStatus(), 'consumability'),
          path: coveragePath,
          issuePath: issueAwarePath(coveragePath, 'consumability'),
          issues: issueAwareMessages(coverageIssueMessages, 'consumability'),
          issueCount: Math.max(mapBlockSummary('consumability').issueCount, coverageIssueMessages.length),
          subPages: sourceSubPages('consumability'),
        },
        {
          key: 'lineage',
          title: 'Audit and lineage',
          detail: lineageCard?.detail ?? 'Record the evidence generated services must preserve.',
          contribution: 'Specifies audit, lineage, and evidence expectations that connect generated behavior back to the locked contract.',
          status: issueAwareStatus(lineageCard?.status ?? 'blocked', 'governance'),
          path: auditPath,
          issuePath: issueAwarePath(auditPath, 'governance'),
          issues: issueAwareMessages(lineageCard?.questions ?? [], 'governance'),
          issueCount: Math.max(mapBlockSummary('governance').issueCount, lineageCard?.questions?.length ?? 0),
          subPages: sourceSubPages('governance'),
        },
      ],
    },
    {
      key: 'delivery',
      title: 'Delivery',
      summary: 'Generate from a saved revision and prove the result against the same contract identity.',
      blocks: [
        {
          key: 'generation',
          title: 'Generation settings',
          detail: generationCard?.detail ?? 'Choose protocol, runtime, extension points, and target output.',
          contribution: 'Controls generator adapter, protocol surface, repository layout, selected services, and extension points.',
          status: issueAwareStatus(generationCard?.status ?? 'blocked', 'delivery'),
          path: generationPath,
          issuePath: issueAwarePath(generationPath, 'delivery'),
          issues: issueAwareMessages(generationCard?.questions ?? [], 'delivery'),
          issueCount: Math.max(mapBlockSummary('delivery').issueCount, generationCard?.questions?.length ?? 0),
          subPages: sourceSubPages('delivery'),
        },
        {
          key: 'definition',
          title: 'Compiled definition',
          detail: generationReadiness.value.detail,
          contribution: 'Compiles the saved Developer Definition into the canonical contract identity used by Registry, generator, and verifier.',
          status: issueAwareStatus(generationReadiness.value.ready ? 'ready' : 'blocked', 'delivery'),
          path: definitionPath,
          issuePath: issueAwarePath(definitionIssueMessages.length ? definitionPath : firstIssuePath([
            { messages: generationReadiness.value.ready ? [] : [generationReadiness.value.detail], path: definitionPath },
          ], definitionPath), 'delivery'),
          issues: issueAwareMessages(definitionIssueMessages.length ? definitionIssueMessages : generationReadiness.value.ready ? [] : [generationReadiness.value.detail], 'delivery'),
          issueCount: Math.max(mapBlockSummary('delivery').issueCount, definitionIssueMessages.length ? definitionIssueMessages.length : generationReadiness.value.ready ? 0 : 1),
          subPages: sourceSubPages('delivery'),
        },
      ],
    },
  ]
})

const developerMapReady = computed(() =>
  developerMapGroups.value.every((group) =>
    group.blocks.every((block) => block.status === 'ready' && (block.issueCount ?? block.issues.length) === 0),
  ),
)

const developerMapBlockedLabel = computed(() =>
  visibleInconsistencyItems.value.length === 0 && generationReadiness.value.ready
    ? 'Evidence pending'
    : 'Map shows blockers',
)

const developerOverviewIssueItems = computed(() =>
  developerIssueIndex.value['project-developer-design']?.messages ?? [],
)

const visibleInconsistencyItems = computed(() =>
  [...new Set([...developerOverviewIssueItems.value, ...inconsistencyItems.value])],
)

const generationReadiness = computed(() => {
  if (!baseline.value || !baselineAligned.value) {
    return {
      ready: false,
      label: 'Blocked by baseline',
      detail: 'Lock or re-lock the Product Design baseline before treating generation as ready.',
    }
  }
  if (!developerDefinition.value) {
    return {
      ready: false,
      label: 'Save Developer Definition',
      detail: 'Generation launches from a saved revision, not from the nav issue count or transient page state.',
    }
  }
  if (!developerDefinition.value.saved_revision) {
    return {
      ready: false,
      label: 'Create revision 1',
      detail: 'Resave Developer Definition so generation can point at an immutable saved revision instead of a mutable legacy artifact.',
    }
  }
  if (!developerDefinitionAligned.value) {
    return {
      ready: false,
      label: 'Saved revision is stale',
      detail: 'The latest saved revision no longer matches the locked baseline. Open Developer Definition and save a new revision before launching generation.',
    }
  }
  if (blockingDesignIssueSummary.value.count > 0) {
    return {
      ready: false,
      label: 'Blocked by design errors',
      detail: `Resolve ${blockingDesignIssueSummary.value.count} blocking Product/Developer Design issue${blockingDesignIssueSummary.value.count === 1 ? '' : 's'} before launching generation.`,
    }
  }
  return {
    ready: true,
    label: `Ready from revision ${developerDefinition.value.saved_revision.revision_number}`,
    detail: 'Generation can launch from the latest saved revision because no blocking Product/Developer Design errors are present.',
  }
})

function sufficiencyStatusLabel(status: DesignSectionSufficiencyCard['status']) {
  switch (status) {
    case 'ready':
      return 'Ready'
    case 'draftable':
      return 'Draftable from baseline'
    case 'needs_clarification':
      return 'Needs clarification'
    default:
      return 'Blocked'
  }
}

function formatGenerationField(value: string | undefined | null) {
  return developerLabel(value || 'not_recorded')
}

async function lockBaseline() {
  if (!project.value) return
  savingBaseline.value = true
  baselineError.value = null
  try {
    await loadProject(project.value.id)
    const blockingMessages = currentProductBlockingMessages()
    if (blockingMessages.length > 0) {
      baselineError.value = `Product Design must be resolved before locking: ${blockingMessages.join(' ')}`
      return
    }

    const currentProductDesignHash = productDesignSourceHash(projectStore.artifacts.pmArtifacts)
    const latestProductRevisionArtifact = findLatestProductDesignRevisionArtifact(projectStore.artifacts.pmArtifacts)
    const latestProductRevision = latestProductRevisionArtifact?.data as ProductDesignRevisionData | undefined
    const productRevision = latestProductRevision?.product_design_hash === currentProductDesignHash
      ? latestProductRevision
      : buildProductDesignRevision({
          projectId: project.value.id,
          pmArtifacts: projectStore.artifacts.pmArtifacts,
        })

    if (productRevision.revision_artifact_id !== latestProductRevision?.revision_artifact_id) {
      await createPmArtifact(project.value.id, {
        id: productRevision.revision_artifact_id,
        title: `Product Design Revision ${productRevision.revision_number}`,
        data: productRevision,
      })
    }

    const payload = buildDeveloperBaseline({
      requirements: currentRequirements.value,
      scenarios: currentScenarios.value,
      primaryScenarioId: primaryScenario.value?.id ?? null,
      shape: currentShape.value,
      pmArtifacts: projectStore.artifacts.pmArtifacts,
      productRevision,
      existing: null,
    })

    if (baselineArtifact.value) {
      await updatePmArtifact(project.value.id, baselineArtifact.value.id, {
        title: 'Locked Product Design Baseline',
        status: 'locked',
        data: payload,
      })
    } else {
      await createPmArtifact(project.value.id, {
        id: developerBaselineArtifactId(project.value.id),
        title: 'Locked Product Design Baseline',
        data: payload,
      })
    }
    await loadProject(project.value.id)
  } catch (err) {
    baselineError.value = err instanceof Error ? err.message : String(err)
  } finally {
    savingBaseline.value = false
  }
}

async function findResettableDataAccessDraftIds() {
  if (!project.value) return [] as string[]
  const filteredSummaries = await listSavedDataAccessProjects({ studio_project_id: project.value.id })
  const linkedIds = filteredSummaries
    .filter((item) => item.studio_project_id === project.value!.id)
    .map((item) => item.id)
  if (linkedIds.length > 0) return linkedIds
  const summaries = await listSavedDataAccessProjects()
  const matching = await Promise.all(
    summaries.map(async (item) => {
      try {
        const record = await getSavedDataAccessProject(item.id)
        const state = record.state
        const serviceId = state.serviceContract?.serviceId ?? null
        const seededFromProjectName = typeof state.name === 'string' && state.name.startsWith(project.value!.name)
        if (serviceId === project.value!.id || seededFromProjectName) {
          return record.id
        }
      } catch {
        return null
      }
      return null
    }),
  )
  return matching.filter((item): item is string => Boolean(item))
}

async function findResettableApplicationIntegrationDraftIds() {
  if (!project.value) return [] as string[]
  const filteredSummaries = await listSavedApplicationIntegrationProjects({ studio_project_id: project.value.id })
  const linkedIds = filteredSummaries
    .filter((item) => item.studio_project_id === project.value!.id)
    .map((item) => item.id)
  if (linkedIds.length > 0) return linkedIds
  const summaries = await listSavedApplicationIntegrationProjects()
  const matching = await Promise.all(
    summaries.map(async (item) => {
      try {
        const record = await getSavedApplicationIntegrationProject(item.id)
        const state = record.state
        const sourcePacketId = state.metadata?.sourcePacketId ?? null
        const seededFromProjectName = typeof state.title === 'string' && state.title.startsWith(project.value!.name)
        if (sourcePacketId === project.value!.id || seededFromProjectName) {
          return record.id
        }
      } catch {
        return null
      }
      return null
    }),
  )
  return matching.filter((item): item is string => Boolean(item))
}

async function resetDeveloperDesign() {
  if (!project.value || resettingDeveloperDesign.value) return

  const confirmed = await requestConfirmation({
    title: 'Reset Developer Design?',
    message: 'This will release the locked Product Design baseline, delete the saved Coverage Mapping record, and remove saved Governed Data Access and Application Integration drafts linked to this project. This cannot be undone.',
    confirmLabel: 'Reset Developer Design',
    cancelLabel: 'Cancel',
    tone: 'danger',
  })
  if (!confirmed) return

  resettingDeveloperDesign.value = true
  baselineError.value = null
  try {
    const [dataAccessDraftIds, applicationIntegrationDraftIds] = await Promise.all([
      findResettableDataAccessDraftIds(),
      findResettableApplicationIntegrationDraftIds(),
    ])

    await Promise.all([
      baselineArtifact.value ? deletePmArtifact(project.value.id, baselineArtifact.value.id) : Promise.resolve(),
      traceabilityArtifact.value ? deletePmArtifact(project.value.id, traceabilityArtifact.value.id) : Promise.resolve(),
      ...dataAccessDraftIds.map(async (id) => {
        await deleteSavedDataAccessProject(id)
        sessionStorage.removeItem(`data-access-seed:${id}`)
      }),
      ...applicationIntegrationDraftIds.map(async (id) => {
        await deleteSavedApplicationIntegrationProject(id)
        sessionStorage.removeItem(`application-integration-seed:${id}`)
      }),
    ])

    await loadProject(project.value.id)
  } catch (err) {
    baselineError.value = err instanceof Error ? err.message : String(err)
  } finally {
    resettingDeveloperDesign.value = false
  }
}

function open(path: string) {
  router.push(path)
}
</script>

<template>
  <div class="developer-home">
    <template v-if="project">
      <section class="page-header">
        <div class="page-kicker">{{ isGovernedFrontingProject ? 'Govern API / MCP' : 'Developer Design' }}</div>
        <h1>{{ project.name }}</h1>
        <p>
          <template v-if="isGovernedFrontingProject">
            Govern API / MCP starts from locked fronting intent. Developers turn existing tools, endpoints, and backend operations into governed ANIP capabilities, policy, generation settings, and verification evidence.
          </template>
          <template v-else>
            Developer Design starts from a locked Product Design baseline. Developers should not pick arbitrary PM inputs. They should formalize and implement against the approved requirements set, the full scenario pack, and the selected service design for this project.
          </template>
        </p>
      </section>

      <section class="grid">
        <article class="panel panel-wide">
          <div class="panel-header">
            <h2>Developer Baseline Readiness</h2>
            <span class="status-chip" :class="{ ready: developerReady }">
              {{ developerReady ? 'Ready for developer work' : 'Baseline not ready' }}
            </span>
          </div>
          <div class="readiness-grid">
            <div v-for="item in productPrerequisites" :key="item.label" class="readiness-card">
              <div class="readiness-title">
                <span class="status-dot" :class="{ ready: item.ready }"></span>
                {{ item.label }}
              </div>
              <p>{{ item.detail }}</p>
            </div>
          </div>
        </article>

        <article class="panel">
          <div class="panel-header">
            <h2>Current Product Design Candidate</h2>
          </div>
          <div class="summary-stack">
            <div class="summary-row">
              <span class="summary-label">Requirements Set</span>
              <strong>{{ currentRequirements?.title || 'Not available' }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Scenario Pack</span>
              <strong>{{ currentScenarios.length ? `${currentScenarios.length} scenarios` : 'Not available' }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Primary Seed Scenario</span>
              <strong>{{ primaryScenario?.title || 'None selected' }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">{{ isGovernedFrontingProject ? 'Backend Supply' : 'Service Design' }}</span>
              <strong>
                {{ isGovernedFrontingProject
                  ? 'Captured through source evidence, connections, and raw operations'
                  : (currentShape?.title || 'Not selected') }}
              </strong>
            </div>
          </div>
        </article>

        <article class="panel">
          <div class="panel-header">
            <h2>Display Settings</h2>
          </div>
          <label class="display-toggle">
            <input v-model="showTechnicalIdentifiers" type="checkbox" />
            <span>
              <strong>Show canonical values</strong>
              <small>Keep this off for normal review. Hover over mapped labels when you need the stored contract value.</small>
            </span>
          </label>
        </article>

        <article class="panel">
          <div class="panel-header">
            <h2>Coverage Record</h2>
          </div>
          <div class="summary-stack">
            <div class="summary-row">
              <span class="summary-label">Developer state</span>
              <strong>{{ traceabilityArtifact ? developerStatusLabel((traceabilityArtifact.data?.developer_status || 'not_started') as any) : 'Not started' }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Addressed items</span>
              <strong>{{ coverageSummary.addressed }} / {{ coverageSummary.total }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">PM review</span>
              <strong>{{ traceabilityRecord ? pmReviewStatusLabel(traceabilityRecord.pm_review_status) : 'Not started' }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Evaluation contract</span>
              <strong>{{ latestEvaluation ? contractAlignment.label : 'Not recorded' }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Latest generation</span>
              <strong>{{ latestGenerationRun ? generationAlignment.label : 'Not recorded' }}</strong>
            </div>
          </div>
        </article>

        <article class="panel panel-wide">
          <div class="panel-header">
            <h2>Locked Product Design Baseline</h2>
            <div class="header-actions">
              <button
                class="btn btn-danger"
                :disabled="resettingDeveloperDesign"
                @click="resetDeveloperDesign"
              >
                {{ resettingDeveloperDesign ? 'Resetting…' : 'Reset Developer Design' }}
              </button>
              <button class="btn btn-primary" :disabled="!productReady || savingBaseline || resettingDeveloperDesign" @click="lockBaseline">
              {{ savingBaseline ? 'Locking…' : baseline && baselineAligned ? 'Re-lock Baseline' : 'Lock Baseline' }}
              </button>
            </div>
          </div>
          <p class="panel-copy">
            <template v-if="isGovernedFrontingProject">
              Locking the baseline freezes the requirements set, the current scenario pack, and the selected integration profile for ANIP fronting. If Product Design changes later, Developer Design is marked out of sync until the baseline is re-locked.
            </template>
            <template v-else>
              Locking the baseline freezes the requirements set, the current scenario pack, and the selected service design for implementation. If Product Design changes later, Developer Design is marked out of sync until the baseline is re-locked.
            </template>
          </p>
          <div v-if="productBlockingIssueSummary.count > 0" class="issue-list danger-list">
            <strong>Product Design must be resolved before locking:</strong>
            <ul>
              <li v-for="message in productBlockingIssueSummary.messages" :key="message">{{ message }}</li>
            </ul>
          </div>
          <p class="panel-copy danger-copy">
            Reset Developer Design clears the current developer baseline and coverage state so the implementation journey can start again from a clean slate.
          </p>
          <p v-if="baselineError" class="error">{{ baselineError }}</p>
          <div v-if="baseline" class="summary-stack baseline-summary">
            <div class="summary-row">
              <span class="summary-label">Requirements Set</span>
              <strong>{{ lockedRequirements?.title || 'Missing from current project state' }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Scenario Pack</span>
              <strong>{{ lockedScenarios.length ? `${lockedScenarios.length} scenarios locked` : 'No scenarios locked' }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Primary Seed Scenario</span>
              <strong>{{ lockedPrimaryScenario?.title || 'None recorded' }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">{{ isGovernedFrontingProject ? 'Backend Supply' : 'Service Design' }}</span>
              <strong>
                {{ isGovernedFrontingProject
                  ? 'Captured through source evidence, connections, and raw operations'
                  : (lockedShape?.title || 'Missing from current project state') }}
              </strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Locked At</span>
              <strong>{{ formatStudioTimestamp(baseline.locked_at) }}</strong>
            </div>
          </div>
        </article>

        <article id="developer-design-map" class="panel panel-full developer-map-panel">
          <DeveloperDesignMap
            :groups="developerMapGroups"
            :ready="developerMapReady"
            :blocked-label="developerMapBlockedLabel"
            @navigate="open"
          />
        </article>

        <article class="panel panel-full">
          <div class="panel-header">
            <h2>Developer Definition Sufficiency</h2>
            <span class="status-chip" :class="{ ready: developerDefinitionAligned }">
              {{ developerDefinitionAligned ? 'Saved draft aligned' : 'Draft from baseline' }}
            </span>
          </div>
          <p class="panel-copy">
            <template v-if="isGovernedFrontingProject">
              Governed fronting should draft from locked intent and accepted backend mappings, then ask only for missing governance, adapter, generation, or verification decisions.
            </template>
            <template v-else>
              Developer Design should draft from the locked PM baseline and only ask for clarifications where the handoff still leaves meaningful ambiguity.
            </template>
          </p>
          <div class="action-grid">
            <button
              v-for="card in developerSufficiencyCards"
              :key="card.key"
              class="action-card"
              @click="open(card.path)"
            >
              <span class="action-title">{{ card.title }}</span>
              <span class="action-copy">{{ card.detail }}</span>
              <span class="status-chip" :class="`status-${card.status}`">
                {{ sufficiencyStatusLabel(card.status) }}
              </span>
              <span v-if="card.questions.length" class="action-questions">
                {{ card.questions[0] }}
              </span>
            </button>
          </div>
        </article>

        <article class="panel panel-wide">
          <div class="panel-header">
            <h2>Clarifications Worth Asking</h2>
            <span class="status-chip" :class="{ ready: developerClarificationCards.length === 0 }">
              {{ developerClarificationCards.length === 0 ? 'No targeted questions' : `${developerClarificationCards.length} sections need clarification` }}
            </span>
          </div>
          <p v-if="developerClarificationCards.length === 0" class="panel-copy">
            The locked PM handoff is sufficient for Studio to keep drafting the developer definition without turning the flow into a field-by-field interview.
          </p>
          <div v-else class="clarification-grid">
            <button
              v-for="card in developerClarificationCards"
              :key="card.key"
              class="clarification-card"
              @click="open(card.path)"
            >
              <strong>{{ card.title }}</strong>
              <ul>
                <li v-for="question in card.questions" :key="question">{{ question }}</li>
              </ul>
            </button>
          </div>
        </article>

        <article class="panel panel-wide">
          <div class="panel-header">
            <h2>AI Assistant</h2>
            <span class="status-chip" :class="{ ready: developerReady }">
              {{ developerReady ? 'Ready' : 'Needs locked baseline' }}
            </span>
          </div>
          <p class="panel-copy">
            Use the dedicated project AI Assistant page to draft Developer Design from the locked PM baseline. This keeps assistant authoring in one explicit surface instead of scattered page-level panels.
          </p>
          <button class="action-card single-action" @click="open(`/design/projects/${project.id}/developer/assistant`)">
            <span class="action-title">Open Developer AI Assistant</span>
            <span class="action-copy">Draft contract-ready developer proposals from the locked PM baseline and save reviewed outputs through deterministic Studio artifacts.</span>
          </button>
        </article>

        <article class="panel panel-wide">
          <div class="panel-header">
            <h2>Current Inconsistencies</h2>
            <span class="status-chip" :class="{ ready: visibleInconsistencyItems.length === 0 }">
              {{ visibleInconsistencyItems.length === 0 ? 'No open inconsistencies' : 'Needs attention' }}
            </span>
          </div>
          <p v-if="visibleInconsistencyItems.length === 0" class="panel-copy">
            The locked baseline, coverage record, and review state are aligned well enough for implementation work to proceed.
          </p>
          <ul v-else class="warning-list">
            <li v-for="item in visibleInconsistencyItems" :key="item">{{ item }}</li>
          </ul>
        </article>

        <article class="panel">
          <div class="panel-header">
            <h2>Generation Readiness</h2>
            <span class="status-chip" :class="{ ready: generationReadiness.ready }">
              {{ generationReadiness.label }}
            </span>
          </div>
          <p class="panel-copy">{{ generationReadiness.detail }}</p>
          <button class="action-card single-action" @click="open(`/design/projects/${project.id}/developer/definition`)">
            <span class="action-title">Open Developer Definition</span>
            <span class="action-copy">Review the working draft, latest saved revision, and generation state in one place.</span>
          </button>
        </article>

        <article class="panel panel-wide">
          <div class="panel-header">
            <h2>Latest Generation Run</h2>
            <span class="status-chip" :class="{ ready: generationAlignment.status === 'aligned' }">
              {{ latestGenerationRun ? generationAlignment.label : 'None yet' }}
            </span>
          </div>
          <template v-if="latestGenerationRun">
            <div class="summary-stack">
              <div class="summary-row">
                <span class="summary-label">Generated At</span>
                <strong>{{ formatStudioTimestamp(latestGenerationRun.generated_at) }}</strong>
              </div>
              <div class="summary-row">
                <span class="summary-label">Contract Signature</span>
                <strong>{{ latestGenerationRun.compiled_contract_identity?.signature || 'Not recorded' }}</strong>
              </div>
              <div class="summary-row">
                <span class="summary-label">Primary Output Mode</span>
                <strong>{{ formatGenerationField(latestGenerationRun.generator_inputs.primary_output_mode) }}</strong>
              </div>
              <div class="summary-row">
                <span class="summary-label">Runtime Target Mode</span>
                <strong>{{ formatGenerationField(latestGenerationRun.generator_inputs.runtime_target_mode) }}</strong>
              </div>
              <div class="summary-row">
                <span class="summary-label">Saved Outputs</span>
                <strong>{{ latestGenerationRun.outputs.runtime_target.length }} runtime-target</strong>
              </div>
            </div>
            <p class="panel-copy">{{ generationAlignment.detail }}</p>
          </template>
          <p v-else class="panel-copy">
            No saved generation run exists yet. Launch generation from Developer Definition once the compiled contract is ready.
          </p>
        </article>

        <article class="panel">
          <div class="panel-header">
            <h2>Latest Proof & Evidence</h2>
            <span class="status-chip" :class="{ ready: latestGenerationRunEvidenceSummary.every((item) => item.ready) }">
              {{ latestGenerationRunEvidenceSummary.every((item) => item.ready) ? 'Ready' : 'Needs attention' }}
            </span>
          </div>
          <p class="panel-copy">
            Latest saved generation run at a glance. This card only summarizes evidence tied to that run, so proof does not silently follow a different generation artifact.
          </p>
          <div class="summary-stack">
            <div v-for="item in latestGenerationRunEvidenceSummary" :key="item.key" class="summary-row">
              <span class="summary-label">{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
              <span class="summary-detail">{{ item.detail }}</span>
            </div>
          </div>
        </article>

        <article class="panel panel-wide">
          <div class="panel-header">
            <h2>{{ isGovernedFrontingProject ? 'Govern API / MCP Flow' : 'Developer Flow' }}</h2>
          </div>
          <div v-if="isGovernedFrontingProject" class="flow-group">
            <h3>Fronting and Contract</h3>
            <div class="action-grid">
              <button class="action-card" @click="open(`/design/projects/${project.id}/fronting`)">
                <span class="action-title">Express Fronting Setup</span>
                <span class="action-copy">Use the simplified fronting checklist and continue into advanced pages only when detailed editing is needed.</span>
              </button>
              <button class="action-card" @click="open(`/design/projects/${project.id}/developer/handoff`)">
                <span class="action-title">Locked Product Handoff</span>
                <span class="action-copy">Review the locked fronting intent, requirements, scenarios, actors, and permission posture.</span>
              </button>
              <button class="action-card" @click="open(`/design/projects/${project.id}/developer/integration-fronting`)">
                <span class="action-title">Advanced API / MCP Mapping</span>
                <span class="action-copy">Curate raw tools and endpoints into governed ANIP capabilities with adapter, policy, outbound control, and audit metadata.</span>
              </button>
              <button class="action-card" @click="open(`/design/projects/${project.id}/developer/generation-settings`)">
                <span class="action-title">Generation Settings</span>
                <span class="action-copy">Set protocol, naming, and adapter choices that affect generated fronting code.</span>
              </button>
              <button class="action-card" @click="open(`/design/projects/${project.id}/developer/gaps`)">
                <span class="action-title">Consistency Gaps</span>
                <span class="action-copy">Check whether the accepted mappings and generated definition still align to the locked fronting intent.</span>
              </button>
              <button class="action-card" @click="open(`/design/projects/${project.id}/developer/definition`)">
                <span class="action-title">Developer Definition</span>
                <span class="action-copy">Review the compiled ANIP Service Definition that generation and verification will consume.</span>
              </button>
            </div>
          </div>
          <div v-else class="flow-group">
            <h3>Baseline and Formalization</h3>
          <div class="action-grid">
            <button class="action-card" @click="open(`/design/projects/${project.id}/developer/diagrams`)">
              <span class="action-title">Developer Diagrams</span>
              <span class="action-copy">Open the service architecture, capability streams, and technical artifact flow diagrams.</span>
            </button>
            <button class="action-card" @click="open(`/design/projects/${project.id}/developer/handoff`)">
              <span class="action-title">Locked Product Handoff</span>
              <span class="action-copy">Review the locked Product Design baseline and the business packet it produces.</span>
            </button>
              <button class="action-card" @click="open(`/design/projects/${project.id}/developer/service-formalization`)">
                <span class="action-title">Service Formalization</span>
                <span class="action-copy">Define system identity, service boundaries, runtime backends, and authority posture.</span>
              </button>
              <button class="action-card" @click="open(`/design/projects/${project.id}/developer/governance-bindings`)">
                <span class="action-title">Roles & Access</span>
                <span class="action-copy">Review roles and the permissions assigned to each role.</span>
              </button>
              <button class="action-card" @click="open(`/design/projects/${project.id}/developer/audit-lineage`)">
                <span class="action-title">Audit & Lineage</span>
                <span class="action-copy">Define the evidence generated services retain for traceability.</span>
              </button>
              <button class="action-card" @click="open(`/design/projects/${project.id}/developer/scenario-formalization`)">
                <span class="action-title">Scenario Coverage Intent</span>
                <span class="action-copy">Define scenario identity, scope, operational posture, and participating service boundaries.</span>
              </button>
              <button class="action-card" @click="open(`/design/projects/${project.id}/developer/scenario-execution-semantics`)">
                <span class="action-title">Scenario Execution Semantics</span>
                <span class="action-copy">Define orchestration steps, required behaviors, ANIP support, and compound workflow rules.</span>
              </button>
              <button class="action-card" @click="open(`/design/projects/${project.id}/developer/coverage`)">
                <span class="action-title">Coverage Mapping</span>
                <span class="action-copy">Map Product Design items to exact formalization targets instead of vague Studio pages.</span>
              </button>
              <button class="action-card" @click="open(`/design/projects/${project.id}/developer/app-glue`)">
                <span class="action-title">Agent & App Glue</span>
                <span class="action-copy">Review what an ANIP-aware app can consume directly and what explicit app glue remains.</span>
              </button>
              <button class="action-card" @click="open(`/design/projects/${project.id}/developer/app-customization`)">
                <span class="action-title">Agent App Customization</span>
                <span class="action-copy">See generated app-profile guidance and the extension files meant for package-specific runtime customization.</span>
              </button>
              <button class="action-card" @click="open(`/design/projects/${project.id}/developer/generation-settings`)">
                <span class="action-title">Generation Settings</span>
                <span class="action-copy">Set service count, protocol posture, naming, and adapter targets that change generated code.</span>
              </button>
              <button class="action-card" @click="open(`/design/projects/${project.id}/developer/verification-expectations`)">
                <span class="action-title">Evidence & Verification Plan</span>
                <span class="action-copy">Define planned proof that PM goals, non-goals, supported questions, and success criteria will be verified.</span>
              </button>
            </div>
          </div>
          <div v-if="!isGovernedFrontingProject" class="flow-group">
            <h3>Compiled Contract and Evidence</h3>
            <div class="action-grid">
              <button class="action-card" @click="open(`/design/projects/${project.id}/developer/gaps`)">
                <span class="action-title">Consistency Gaps</span>
                <span class="action-copy">Compare implementation evidence against the locked baseline and its coverage record.</span>
              </button>
              <button class="action-card" @click="open(`/design/projects/${project.id}/developer/definition`)">
                <span class="action-title">Developer Definition</span>
                <span class="action-copy">Review the compiled exportable technical contract assembled from the formalization pages.</span>
              </button>
            </div>
          </div>
        </article>
      </section>
    </template>
  </div>
</template>

<style scoped>
.developer-home {
  width: 100%;
  max-width: none;
  padding: 2rem;
}

.page-header {
  margin-bottom: 1.5rem;
}

.page-kicker,
.summary-label {
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
.panel-copy,
.action-copy,
.readiness-card p {
  color: var(--text-secondary);
  line-height: 1.6;
}

.subdued-card {
  opacity: 0.82;
  border-color: rgba(148, 163, 184, 0.12);
}

.flow-group + .flow-group {
  margin-top: 1.35rem;
  padding-top: 1.1rem;
  border-top: 1px solid rgba(148, 163, 184, 0.14);
}

.flow-group h3 {
  margin: 0 0 0.85rem;
  color: var(--text-primary);
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

.panel-wide {
  grid-column: span 8;
}

.panel-full {
  grid-column: span 12;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1rem;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.panel-header h2,
.action-title {
  margin: 0;
}

.status-chip {
  padding: 0.3rem 0.7rem;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.16);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
}

.status-chip.ready {
  background: rgba(16, 185, 129, 0.14);
  color: #bbf7d0;
}

.status-chip.status-ready {
  background: rgba(16, 185, 129, 0.14);
  color: #bbf7d0;
}

.status-chip.status-draftable {
  background: rgba(59, 130, 246, 0.16);
  color: #93c5fd;
}

.status-chip.status-needs_clarification {
  background: rgba(245, 158, 11, 0.16);
  color: #fcd34d;
}

.status-chip.status-blocked {
  background: rgba(248, 113, 113, 0.16);
  color: #fca5a5;
}

.readiness-grid,
.action-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0.85rem;
}

.readiness-card,
.action-card {
  border: 1px solid var(--surface-border-card);
  border-radius: 16px;
  padding: 1rem;
  background: var(--surface-depth-card);
}

.action-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.5rem;
  text-align: left;
  cursor: pointer;
  transition: transform 0.16s ease, border-color 0.16s ease;
  color: var(--text-primary);
}

.action-card:hover {
  transform: translateY(-1px);
  border-color: rgba(96, 165, 250, 0.36);
}

.action-title,
.action-copy {
  display: block;
  width: 100%;
}

.action-questions {
  display: block;
  width: 100%;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.clarification-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 0.85rem;
}

.clarification-card {
  text-align: left;
  cursor: pointer;
  border-radius: 16px;
  border: 1px solid rgba(245, 158, 11, 0.2);
  background: var(--surface-depth-card);
  padding: 1rem;
  color: inherit;
}

.clarification-card strong {
  display: block;
  margin-bottom: 0.55rem;
}

.clarification-card ul {
  margin: 0;
  padding-left: 1rem;
  color: var(--text-secondary);
}

.assistant-source {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  margin-bottom: 1rem;
}

.assistant-recommendation {
  margin: 1rem 0;
  padding: 0.9rem 1rem;
  border-radius: 14px;
  border: 1px solid rgba(96, 165, 250, 0.24);
  background: var(--surface-depth-card);
}

.assistant-recommendation strong {
  display: block;
  margin-bottom: 0.35rem;
  color: var(--text-primary);
}

.assistant-recommendation p {
  margin: 0 0 0.45rem;
  color: var(--text-secondary);
  line-height: 1.5;
}

.assistant-recommendation ul {
  margin: 0;
  padding-left: 1rem;
  color: var(--text-secondary);
}

.inline-status {
  text-transform: lowercase;
}

.assistant-source span {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-secondary);
}

.assistant-source textarea {
  width: 100%;
  min-height: 8rem;
  padding: 0.85rem 1rem;
  border-radius: 14px;
  border: 1px solid var(--border);
  background: var(--bg-input);
  color: var(--text-primary);
  resize: vertical;
  box-sizing: border-box;
}

.assistant-results {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  margin-top: 1rem;
}

.assistant-meta-block strong {
  display: block;
  margin-bottom: 0.35rem;
  color: var(--text-primary);
  font-size: 13px;
}

.assistant-meta-block ul {
  margin: 0;
  padding-left: 1.25rem;
  color: var(--text-secondary);
}

.assistant-selection-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.assistant-selection-item {
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
  padding: 0.85rem 0.95rem;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--surface-depth-card);
}

.assistant-selection-copy {
  flex: 1;
  min-width: 0;
}

.assistant-selection-title-row {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.35rem;
}

.assistant-selection-copy p {
  margin: 0 0 0.35rem;
  color: var(--text-secondary);
  line-height: 1.45;
  white-space: pre-wrap;
}

.assistant-selection-copy small {
  color: var(--text-muted);
}

.assistant-confidence {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
}

.success-copy {
  color: #86efac;
}

.readiness-title {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  font-weight: 600;
  margin-bottom: 0.45rem;
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: rgba(244, 63, 94, 0.7);
}

.status-dot.ready {
  background: rgba(16, 185, 129, 0.9);
}

.summary-stack {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.baseline-summary {
  margin-top: 1.35rem;
}

.summary-row {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.summary-row .summary-label {
  color: var(--text-muted);
  font-weight: 700;
}

.summary-row strong {
  color: var(--text-primary);
  font-size: 15px;
  line-height: 1.35;
}

.summary-detail {
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.5;
  word-break: break-word;
}

.warning-list {
  margin: 0;
  padding-left: 1rem;
  color: #fecaca;
}

.btn {
  border-radius: 12px;
  border: none;
  padding: 0.7rem 1rem;
  font-weight: 600;
  cursor: pointer;
}

.btn-primary {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.92), rgba(14, 165, 233, 0.92));
  color: white;
}

.btn-danger {
  background: transparent;
  color: #fca5a5;
  border: 1px solid rgba(248, 113, 113, 0.3);
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.error {
  color: #fecaca;
  margin: 0 0 0.9rem;
}

.danger-copy {
  color: #fca5a5;
}

.danger-list {
  margin: 0.85rem 0;
  border: 1px solid rgba(248, 113, 113, 0.32);
  border-radius: 14px;
  padding: 0.85rem 1rem;
  background: rgba(127, 29, 29, 0.14);
  color: #fecaca;
}

.danger-list ul {
  margin: 0.45rem 0 0;
  padding-left: 1.15rem;
}

.display-toggle {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  cursor: pointer;
  color: var(--text-primary);
}

.display-toggle input {
  margin-top: 0.2rem;
}

.display-toggle span {
  display: grid;
  gap: 0.25rem;
}

.display-toggle small {
  color: var(--text-secondary);
  line-height: 1.45;
}

@media (max-width: 1100px) {
  .panel,
  .panel-wide,
  .panel-full {
    grid-column: span 12;
  }
}

@media (max-width: 720px) {
  .developer-home {
    padding: 1rem;
  }
}
</style>
