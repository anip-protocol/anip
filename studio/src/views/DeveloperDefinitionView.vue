<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { requestConfirmation } from '../design/confirm'
import {
  buildExtensionManifest,
  buildGeneratedRuntimeTarget,
  buildGeneratedStructureSummary,
  buildIntegrationAdapterBindings,
  buildLocalConformanceReport,
  findLatestDeveloperGenerationRunArtifact,
} from '../design/developer-definition'
import {
  createPmArtifact,
  getLocalRegistryPackage,
  getLocalRegistryPackageBundleUrl,
  publishLocalRegistryPackage,
  publishRegistryPackage,
  type LocalPublicationRecord,
  type LocalPublicationVerificationResult,
  type RegistryPublishRequest,
  type RegistryPublishResult,
  type RegistryRevisionLineage,
  updatePmArtifact,
  verifyLocalRegistryPackage,
} from '../design/project-api'
import {
  analyzeAgentConsumptionReadiness,
  readinessStatusLabel,
  type AgentConsumptionReadinessReport,
} from '../design/agent-consumption-readiness'
import { buildAgentConsumabilityMetadata } from '../design/agent-consumability'
import {
  summarizeAgentConsumptionSimulationPublicationGate,
  type AgentConsumptionSimulationReport,
} from '../design/agent-consumption-simulator'
import { projectStore, refreshArtifacts } from '../design/project-store'
import {
  findReleaseRecordArtifacts,
  summarizeApprovalLineage,
  type ReleaseRecordData,
} from '../design/release-lineage'
import type {
  DeveloperExtensionPoint,
  DeveloperDefinitionData,
  DeveloperGeneratedArtifactOutput,
  DeveloperGeneratedRuntimeTarget,
  DeveloperGeneratedStructureSummary,
  DeveloperGenerationRunData,
} from '../design/project-types'
import { useDeveloperDefinitionEditor } from '../design/use-developer-definition-editor'
import { formatStudioTimestamp } from '../design/time'
import { buildProjectIssueIndex } from '../design/project-issues'
import { developerLabel } from '../design/developer-vocabulary'
import { STUDIO_PROTOCOL_VERSION } from '../version'

const router = useRouter()
const {
  project,
  baseline,
  baselineAligned,
  lockedRequirements,
  lockedScenarios,
  lockedShape,
  traceabilityRecord,
  savedDefinition,
  definitionAligned,
  definitionContract,
  definitionContractIdentity,
  definition,
  definitionJson,
  sectionCards,
  definitionSaveBlockedReason: editorDefinitionSaveBlockedReason,
  clearAssistantSeededSection,
  saving,
  saveError,
  saveDefinition,
  exportDefinition,
} = useDeveloperDefinitionEditor()

const readOnlyMode = computed(() => projectStore.runtimeStatus?.read_only_mode !== false)
const readOnlyReason = computed(() =>
  projectStore.runtimeStatus?.read_only_reason
  || 'Studio is running in read-only mode. Explore the design, then download and run Studio locally to make changes.',
)
const generationLoading = ref(false)
const generationError = ref<string | null>(null)
const publishingRegistry = ref(false)
const publishingLocalRegistry = ref(false)
const promotingLocalPublication = ref(false)
const recordingRelease = ref(false)
const registryPublishError = ref<string | null>(null)
const releaseError = ref<string | null>(null)
const registryPublishResult = ref<RegistryPublishResult | null>(null)
const localRegistryPublishResult = ref<LocalPublicationRecord | null>(null)
const localPublicationVerificationRunning = ref(false)
const localPublicationVerificationError = ref<string | null>(null)
const localPublicationVerificationResult = ref<LocalPublicationVerificationResult | null>(null)
type ImplementationMaterialDraft = {
  title: string
  ref: string
  bundle_tree_sha256: string
}

const implementationMaterialDrafts = ref<ImplementationMaterialDraft[]>([])

const designIssueIndex = computed(() => buildProjectIssueIndex({
  project: project.value,
  pmArtifacts: projectStore.artifacts.pmArtifacts,
  requirements: projectStore.artifacts.requirements,
  scenarios: projectStore.artifacts.scenarios,
  documents: projectStore.artifacts.documents,
  shapes: projectStore.artifacts.shapes,
}))
const blockingDesignIssueSummary = computed(() => {
  const issues = ['project-product-design', 'project-developer-design', 'project-developer-coverage']
    .map((key) => designIssueIndex.value[key])
    .filter((issue) => issue?.severity === 'error')
  return {
    count: issues.reduce((total, issue) => total + (issue?.count ?? 0), 0),
    messages: issues.flatMap((issue) => issue?.messages ?? []),
  }
})
const designIssueBlockedReason = computed(() => {
  if (blockingDesignIssueSummary.value.count === 0) return null
  return `Resolve ${blockingDesignIssueSummary.value.count} blocking Product/Developer Design issue${blockingDesignIssueSummary.value.count === 1 ? '' : 's'} before generation or Registry publication. First issue: ${blockingDesignIssueSummary.value.messages[0]}`
})
const simulationGateOverrideAcknowledged = ref(false)
const latestGenerationRunArtifact = computed(() => findLatestDeveloperGenerationRunArtifact(projectStore.artifacts.pmArtifacts))
const latestGenerationRun = computed(() =>
  (latestGenerationRunArtifact.value?.data as DeveloperGenerationRunData | undefined) ?? null,
)
type DeveloperRegistryPublicationArtifactData = {
  artifact_type: 'developer_registry_publication'
  authority: 'local-studio' | 'remote-registry'
  publication: RegistryPublishResult['publication']
  package: RegistryPublishResult['package']
  receipt: RegistryPublishResult['receipt']
  local_publication_id?: string
  approved_from_pm_review?: {
    approval_artifact_id: string | null
    approved_at: string | null
    product_revision: string
    developer_revision: string
    contract_signature: string
  }
  promoted_from_local_publication?: {
    local_publication_id: string
    local_receipt_signature: string
    verification_status: string
    receipt_status?: string
    verified_at: string
  }
  local_verification?: {
    status: string
    receipt_status: string
    receipt_signature: string
    verified_at: string
    passed_checks: number
    failed_checks: number
    product_revision?: RegistryRevisionLineage['product_revision'] | null
    developer_revision?: RegistryRevisionLineage['developer_revision'] | null
  }
  published_from_saved_revision: {
    revision_number: number | null
    revision_artifact_id: string | null
    product_revision_artifact_id?: string | null
    product_revision_number?: number | null
    baseline_locked_at: string | null
  }
}

const registryPublicationArtifacts = computed(() => {
  const artifacts = [...projectStore.artifacts.pmArtifacts].filter((artifact) =>
    artifact.data?.artifact_type === 'developer_registry_publication',
  )
  artifacts.sort((a, b) => new Date(b.updated_at || b.created_at).getTime() - new Date(a.updated_at || a.created_at).getTime())
  return artifacts
})
const latestRegistryPublicationArtifact = computed(() => registryPublicationArtifacts.value[0] ?? null)
const latestRegistryPublication = computed(() =>
  (latestRegistryPublicationArtifact.value?.data as DeveloperRegistryPublicationArtifactData | undefined) ?? null,
)
const latestSavedRevision = computed(() => savedDefinition.value?.saved_revision ?? null)
const savedContractSignature = computed(() => savedDefinition.value?.compiled_contract_identity?.signature ?? '')
const currentContractSignature = computed(() => definitionContractIdentity.value?.signature ?? '')
const hasUnsavedContractChanges = computed(() => {
  if (!savedDefinition.value) return Boolean(currentContractSignature.value)
  if (!savedContractSignature.value || !currentContractSignature.value) return false
  return savedContractSignature.value !== currentContractSignature.value
})
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
const savedAgentReadinessReport = computed(() => {
  const reviewedReport = traceabilityRecord.value?.agent_consumption_readiness
  return isAgentReadinessReport(reviewedReport)
    ? reviewedReport
    : analyzeAgentConsumptionReadiness(savedDefinition.value)
})
const savedAgentConsumabilityMetadata = computed(() =>
  buildAgentConsumabilityMetadata({
    definition: savedDefinition.value,
    readiness: savedAgentReadinessReport.value,
    manualReviews: traceabilityRecord.value?.agent_consumability_reviews,
  }),
)
const latestSimulationReportArtifact = computed(() => {
  const artifacts = [...projectStore.artifacts.pmArtifacts].filter((artifact) =>
    artifact.data?.artifact_type === 'agent_consumption_simulation_report',
  )
  artifacts.sort((a, b) => new Date(b.updated_at || b.created_at).getTime() - new Date(a.updated_at || a.created_at).getTime())
  return artifacts[0] ?? null
})
const latestSimulationReport = computed<AgentConsumptionSimulationReport | null>(() =>
  (latestSimulationReportArtifact.value?.data as AgentConsumptionSimulationReport | undefined) ?? null,
)
const simulationPublicationGate = computed(() =>
  summarizeAgentConsumptionSimulationPublicationGate({
    report: latestSimulationReport.value,
    overrideAccepted: simulationGateOverrideAcknowledged.value,
  }),
)
const definitionSaveBlockedReason = computed(() =>
  editorDefinitionSaveBlockedReason.value,
)
const agentReadinessBlockedReason = computed(() => {
  if (!savedDefinition.value) return null
  const report = savedAgentReadinessReport.value
  if (report.summary.blockers > 0) {
    return `Agent Consumption Readiness is blocked: ${report.summary.blockers} blocker${report.summary.blockers === 1 ? '' : 's'} must be resolved in Agent & App Glue before generation or publication.`
  }
  if (report.summary.warnings > 0) {
    return `Agent Consumption Readiness has ${report.summary.warnings} unresolved warning${report.summary.warnings === 1 ? '' : 's'}. Resolve or classify them in Agent & App Glue before generation or publication.`
  }
  return null
})
const generationBlockedReason = computed(() => {
  if (!savedDefinition.value) {
    return 'Save Developer Definition first. Generation and verification run against a saved revision, not transient page state.'
  }
  if (!latestSavedRevision.value) {
    return 'Save Developer Definition again to create revision 1. Generation and verification must point at an immutable saved revision.'
  }
  if (!definitionAligned.value) {
    return 'The latest saved revision no longer matches the locked baseline. Save the current compiled contract as a new revision before launching generation.'
  }
  if (hasUnsavedContractChanges.value) {
    return `The working draft differs from saved revision ${latestSavedRevision.value.revision_number}. Save a new revision before launching generation if this draft should become delivery truth.`
  }
  if (designIssueBlockedReason.value) return designIssueBlockedReason.value
  if (agentReadinessBlockedReason.value) return agentReadinessBlockedReason.value
  if (simulationPublicationGate.value.blocksPublication) return simulationPublicationGate.value.detail
  return null
})
const publicationPrerequisiteBlockedReason = computed(() => {
  if (!project.value || !baseline.value || !definitionContract.value) {
    return 'Lock the baseline and materialize a saved compiled contract before publishing to the registry.'
  }
  if (!savedDefinition.value) {
    return 'Save Developer Definition first. Registry publication must point at an immutable saved revision.'
  }
  if (!latestSavedRevision.value) {
    return 'Save Developer Definition again to create revision 1 before publishing.'
  }
  if (!definitionAligned.value) {
    return `Saved revision ${latestSavedRevision.value.revision_number} is stale against the locked baseline. Save a new revision before publishing.`
  }
  if (hasUnsavedContractChanges.value) {
    return `The working draft differs from saved revision ${latestSavedRevision.value.revision_number}. Save the current draft as a new revision before publishing.`
  }
  if (designIssueBlockedReason.value) return designIssueBlockedReason.value
  if (agentReadinessBlockedReason.value) return agentReadinessBlockedReason.value
  return null
})
const approvalLineage = computed(() =>
  summarizeApprovalLineage(projectStore.artifacts.pmArtifacts, {
    productRevisionArtifactId: baseline.value?.source_inputs.product_revision_artifact_id ?? null,
    productRevisionNumber: baseline.value?.source_inputs.product_revision_number ?? null,
    developerRevisionArtifactId: latestSavedRevision.value?.revision_artifact_id ?? null,
    developerRevisionNumber: latestSavedRevision.value?.revision_number ?? null,
    contractSignature: savedContractSignature.value,
  }),
)
const registryPublishBlockedReason = computed(() => {
  if (publicationPrerequisiteBlockedReason.value) return publicationPrerequisiteBlockedReason.value
  if (implementationMaterialError.value) return implementationMaterialError.value
  if (approvalLineage.value.status !== 'current') return approvalLineage.value.detail
  return null
})
const localPublishBlockedReason = computed(() => publicationPrerequisiteBlockedReason.value || implementationMaterialError.value)
const canPublishRegistry = computed(() => !readOnlyMode.value && !registryPublishBlockedReason.value && !publishingRegistry.value)
const canPublishLocalRegistry = computed(() => !readOnlyMode.value && !localPublishBlockedReason.value && !publishingLocalRegistry.value)
const canLaunchGeneration = computed(() => !readOnlyMode.value && !generationBlockedReason.value && !generationLoading.value)
const canSaveDefinition = computed(() => !readOnlyMode.value && !saving.value && !definitionSaveBlockedReason.value)
const saveButtonLabel = computed(() => {
  if (saving.value) return 'Saving…'
  if (!latestSavedRevision.value) return 'Save Revision 1'
  if (hasUnsavedContractChanges.value || !definitionAligned.value) {
    return `Save Revision ${latestSavedRevision.value.revision_number + 1}`
  }
  return 'Save Developer Definition'
})
const definitionSaveStatus = computed(() => {
  if (!savedDefinition.value) {
    return {
      label: 'No saved revision yet',
      detail: 'The current compiled contract exists only in working draft state. Save it to create immutable delivery truth for generation and verification.',
      tone: 'warning',
    }
  }
  if (!latestSavedRevision.value) {
    return {
      label: 'Legacy saved state',
      detail: 'A mutable saved artifact exists, but no immutable revision has been recorded yet. Save again to create revision 1.',
      tone: 'warning',
    }
  }
  if (hasUnsavedContractChanges.value) {
    return {
      label: 'Draft ahead of latest revision',
      detail: `The working draft differs from saved revision ${latestSavedRevision.value.revision_number}. Existing evidence remains tied to that saved revision until you save a new one.`,
      tone: 'warning',
    }
  }
  if (!definitionAligned.value) {
    return {
      label: 'Latest revision is stale',
      detail: `Saved revision ${latestSavedRevision.value.revision_number} no longer matches the locked baseline. Save the current compiled contract as a new revision to realign delivery truth.`,
      tone: 'warning',
    }
  }
  return {
    label: `Saved revision ${latestSavedRevision.value.revision_number} is current`,
    detail: 'Generation and verification will align against the latest saved revision.',
    tone: 'ready',
  }
})

const capabilityFormalizationBlocked = computed(() =>
  Boolean(
    definitionSaveBlockedReason.value?.includes('source-declared capability')
    || definitionSaveBlockedReason.value?.includes('Capability input contracts'),
  ),
)

const sourceCards = computed(() => {
  const cards = [
    {
      id: 'service',
      label: 'Service Formalization',
      description: 'System identity, delivery model, service topology, runtime backends, and authority posture.',
      route: project.value ? `/design/projects/${project.value.id}/developer/service-formalization` : '',
      ready: sectionCards.value
        .filter((section) => ['service_identity_topology', 'authority_and_approval', 'backend_bindings'].includes(section.id))
        .every((section) => section.coverage.summary.missing === 0 && section.coverage.summary.partial === 0),
    },
    {
      id: 'governance',
      label: 'Actors, Access & Audit',
      description: 'Roles, assigned permissions, capability requirements, and audit evidence expectations.',
      route: project.value ? `/design/projects/${project.value.id}/developer/governance-bindings` : '',
      ready: sectionCards.value
        .filter((section) => ['audit_and_lineage'].includes(section.id))
        .every((section) => section.coverage.summary.missing === 0 && section.coverage.summary.partial === 0),
    },
    {
      id: 'capability',
      label: 'Capability Formalization',
      description: 'Capability identity, bounded behavior, backend binding, and output contract intent.',
      route: project.value ? `/design/projects/${project.value.id}/developer/capability-formalization` : '',
      ready: sectionCards.value
        .filter((section) => section.id === 'capability_contracts')
        .every((section) => section.coverage.summary.missing === 0 && section.coverage.summary.partial === 0)
        && !capabilityFormalizationBlocked.value,
    },
    {
      id: 'data',
      label: 'Data Contract Formalization',
      description: 'Canonical data domain, domain concept bindings, metrics, dimensions, filters, and object model.',
      route: project.value ? `/design/projects/${project.value.id}/developer/data-contract-formalization` : '',
      ready: sectionCards.value
        .filter((section) => section.id === 'data_contracts')
        .every((section) => section.coverage.summary.missing === 0 && section.coverage.summary.partial === 0),
    },
    {
      id: 'scenario_contract',
      label: 'Scenario Coverage Intent',
      description: 'Scenario identity, scope, operational posture, and participating service coverage for readiness and verification.',
      route: project.value ? `/design/projects/${project.value.id}/developer/scenario-formalization` : '',
      ready: sectionCards.value
        .filter((section) => section.id === 'scenario_context')
        .every((section) => section.coverage.summary.missing === 0 && section.coverage.summary.partial === 0),
    },
    {
      id: 'scenario_execution',
      label: 'Scenario Execution Semantics',
      description: 'Structured orchestration, required behaviors, required ANIP support, and compound workflow rules.',
      route: project.value ? `/design/projects/${project.value.id}/developer/scenario-execution-semantics` : '',
      ready: sectionCards.value
        .filter((section) => section.id === 'execution_semantics')
        .every((section) => section.coverage.summary.missing === 0 && section.coverage.summary.partial === 0),
    },
    {
      id: 'generation',
      label: 'Generation Settings',
      description: 'Service count, protocol posture, adapter target, repository layout, and naming strategy.',
      route: project.value ? `/design/projects/${project.value.id}/developer/generation-settings` : '',
      ready: sectionCards.value
        .filter((section) => ['generation_and_extensions'].includes(section.id))
        .every((section) => section.coverage.summary.missing === 0 && section.coverage.summary.partial === 0),
    },
    {
      id: 'verification',
      label: 'Evidence & Verification Plan',
      description: 'Planned proof for verification bindings, non-goal guards, success evidence, and scenario-pack evaluation expectations.',
      route: project.value ? `/design/projects/${project.value.id}/developer/verification-expectations` : '',
      ready: sectionCards.value
        .filter((section) => section.id === 'audit_and_lineage')
        .every((section) => section.coverage.summary.missing === 0 && section.coverage.summary.partial === 0),
    },
  ]
  if (project.value?.project_type !== 'governed_service_project') return cards
  return [
    {
      id: 'integration-fronting',
      label: 'Govern API / MCP',
      description: 'Curated governed capability mappings in front of native API, MCP, database, or hybrid backend operations.',
      route: project.value ? `/design/projects/${project.value.id}/developer/integration-fronting` : '',
      ready: sectionCards.value
        .filter((section) => ['capability_contracts', 'authority_and_approval', 'backend_bindings'].includes(section.id))
        .every((section) => section.coverage.summary.missing === 0 && section.coverage.summary.partial === 0)
        && !capabilityFormalizationBlocked.value,
    },
    ...cards.filter((card) => ['generation', 'verification'].includes(card.id)),
  ]
})

const contractIdentity = computed(() => {
  if (!project.value || !baseline.value) return []
  return [
    {
      label: 'Contract Artifact',
      value: `${project.value.id}-developer-definition.json`,
    },
    {
      label: 'Requirements Baseline',
      value: baseline.value.source_inputs.requirements_hash || 'Not available',
    },
    {
      label: 'Scenario Pack Hash',
      value: baseline.value.source_inputs.scenario_set_hash || 'Not available',
    },
    {
      label: 'Service Design Hash',
      value: baseline.value.source_inputs.shape_hash || 'Not available',
    },
    {
      label: 'Contract Signature',
      value: currentContractSignature.value || 'Not available yet',
    },
    {
      label: 'Signature Algorithm',
      value: definitionContractIdentity.value?.signature_algorithm || 'Not available yet',
    },
    {
      label: 'Latest Saved Revision',
      value: latestSavedRevision.value ? `Revision ${latestSavedRevision.value.revision_number}` : 'Not saved yet',
    },
    {
      label: 'Latest Revision Saved At',
      value: latestSavedRevision.value ? formatStudioTimestamp(latestSavedRevision.value.saved_at) : 'Not saved yet',
    },
    {
      label: 'Latest Saved Revision Signature',
      value: savedContractSignature.value || 'Not saved yet',
    },
  ]
})

const generationReadiness = computed(() => [
  {
    id: 'runtime-target',
    label: 'Runtime Target',
    ready: !!latestSavedRevision.value && !!savedContractSignature.value && !designIssueBlockedReason.value,
    detail: designIssueBlockedReason.value
      ? designIssueBlockedReason.value
      : latestSavedRevision.value && savedContractSignature.value
        ? `Primary generation path is ready from saved revision ${latestSavedRevision.value.revision_number}. Studio emits deterministic runtime-estate artifacts directly from that revision.`
      : 'Save Developer Definition first so Studio can generate the runtime-estate scaffold from an immutable saved revision.',
  },
])

const registryReadiness = computed(() => {
  if (registryPublishBlockedReason.value) {
    return {
      ready: false,
      label: 'Blocked',
      detail: registryPublishBlockedReason.value,
    }
  }
  if (!latestSavedRevision.value) {
    return {
      ready: false,
      label: 'Needs saved revision',
      detail: 'Publish from an immutable saved revision, not from the working draft.',
    }
  }
  return {
    ready: true,
    label: `Ready from revision ${latestSavedRevision.value.revision_number}`,
    detail: 'Studio can publish the current saved compiled contract and publisher lock bundle either to Studio-local immutable storage or to the separate Registry service.',
  }
})

const registryPublicationRows = computed(() => {
  if (!latestRegistryPublication.value) return []
  const latest = latestRegistryPublication.value
  const isRemote = latest.authority === 'remote-registry'
  const registryKeyLabel = formatRegistryReceiptKey(latest.receipt)
  const productRevisionLabel = formatRegistryRevisionLabel('Product', latest.package.lineage?.product_revision, {
    artifactId: latest.published_from_saved_revision.product_revision_artifact_id ?? null,
    revisionNumber: latest.published_from_saved_revision.product_revision_number ?? null,
  })
  const developerRevisionLabel = formatRegistryRevisionLabel('Developer', latest.package.lineage?.developer_revision, {
    artifactId: latest.published_from_saved_revision.revision_artifact_id ?? null,
    revisionNumber: latest.published_from_saved_revision.revision_number ?? null,
  })
  const latestVerificationStatus = latest.local_verification?.receipt_status
    ?? latest.promoted_from_local_publication?.receipt_status
    ?? inferPublicationReceiptStatus(latest)
  return [
    {
      label: latest.authority === 'local-studio' ? 'Local Package' : 'Published Package',
      value: `${latest.package.package_id}@${latest.package.package_version}`,
    },
    {
      label: 'Authority',
      value: latest.authority === 'local-studio' ? 'Studio local registry' : 'Remote Registry service',
    },
    {
      label: 'Authority State',
      value: latest.promoted_from_local_publication
        ? `Promoted from ${latest.promoted_from_local_publication.local_publication_id}`
        : latest.authority === 'local-studio'
          ? 'Local immutable publication'
          : 'Direct remote publication',
    },
    {
      label: 'Product Revision',
      value: productRevisionLabel,
    },
    {
      label: 'Developer Revision',
      value: developerRevisionLabel,
    },
    {
      label: 'Contract Signature',
      value: latest.package.contract_signature,
    },
    {
      label: 'Receipt Status',
      value: formatReceiptStatus(latestVerificationStatus),
    },
    ...(latest.approved_from_pm_review
      ? [
          {
            label: 'PM Approval',
            value: `${latest.approved_from_pm_review.product_revision} -> ${latest.approved_from_pm_review.developer_revision}`,
          },
        ]
      : []),
    ...(isRemote
      ? [
          {
            label: 'Registry Trust State',
            value: latest.receipt.key_id ? `Signed by Registry key ${latest.receipt.key_id}` : 'Signed receipt metadata unavailable',
          },
        ]
      : []),
    {
      label: 'Published From Revision',
      value: latest.published_from_saved_revision.revision_number
        ? `Revision ${latest.published_from_saved_revision.revision_number}`
        : 'Unknown',
    },
    {
      label: 'Published At',
      value: formatStudioTimestamp(latest.publication.published_at),
    },
    {
      label: 'Manifest Digest',
      value: latest.package.manifest_digest,
    },
    {
      label: 'Definition Digest',
      value: latest.package.definition_digest,
    },
    ...(latest.package.lock_digest
      ? [
          {
            label: 'Lock Digest',
            value: latest.package.lock_digest,
          },
        ]
      : []),
    {
      label: 'Receipt ID',
      value: latest.receipt.receipt_id,
    },
    {
      label: 'Receipt Signature',
      value: latest.receipt.registry_signature,
    },
    ...(registryKeyLabel
      ? [
          {
            label: 'Registry Receipt Key',
            value: registryKeyLabel,
          },
        ]
      : []),
    ...(latest.promoted_from_local_publication
      ? [
          {
            label: 'Local Receipt Signature',
            value: latest.promoted_from_local_publication.local_receipt_signature,
          },
        ]
      : []),
  ]
})

const releaseArtifacts = computed(() => findReleaseRecordArtifacts(projectStore.artifacts.pmArtifacts))
const releaseRows = computed(() =>
  releaseArtifacts.value.map((artifact) => {
    const data = artifact.data as ReleaseRecordData
    return {
      artifactId: artifact.id,
      releaseId: data.release_id,
      packageLabel: `${data.package_id}@${data.package_version}`,
      releasedAt: formatStudioTimestamp(data.released_at || artifact.created_at),
      authority: data.authority,
      receiptSignature: data.receipt_signature,
      approvalArtifactId: data.approval_artifact_id,
    }
  }),
)
const latestRemotePublicationArtifact = computed(() =>
  registryPublicationArtifacts.value.find((artifact) => artifact.data?.authority === 'remote-registry') ?? null,
)
const latestRemotePublication = computed(() =>
  (latestRemotePublicationArtifact.value?.data as DeveloperRegistryPublicationArtifactData | undefined) ?? null,
)
const releaseBlockedReason = computed(() => {
  if (!latestRemotePublicationArtifact.value || !latestRemotePublication.value) {
    return 'Publish an approved package to the remote Registry before recording a release.'
  }
  if (approvalLineage.value.status !== 'current' || !approvalLineage.value.artifactId) {
    return approvalLineage.value.detail
  }
  const alreadyReleased = releaseArtifacts.value.some((artifact) => {
    const data = artifact.data as ReleaseRecordData
    return data.publication_artifact_id === latestRemotePublicationArtifact.value?.id
  })
  if (alreadyReleased) return 'The latest remote Registry publication already has a release record.'
  return null
})
const canRecordRelease = computed(() => !readOnlyMode.value && !releaseBlockedReason.value && !recordingRelease.value)

const latestLocalPublicationBundle = computed(() => {
  if (!project.value || latestRegistryPublication.value?.authority !== 'local-studio') return null
  const publicationId = latestRegistryPublication.value.local_publication_id || localRegistryPublishResult.value?.id
  if (!publicationId) return null
  return {
    publicationId,
    url: getLocalRegistryPackageBundleUrl(project.value.id, publicationId),
    filename: `${latestRegistryPublication.value.package.package_id}-${latestRegistryPublication.value.package.package_version}.anip-package.json`,
  }
})

const canPromoteLatestLocalPublication = computed(() =>
  !readOnlyMode.value
    && Boolean(latestLocalPublicationBundle.value)
    && !registryPublishBlockedReason.value
    && !promotingLocalPublication.value
    && !publishingRegistry.value
    && !localPublicationVerificationRunning.value,
)

const localPublicationVerificationSummary = computed(() => {
  if (!localPublicationVerificationResult.value) return null
  const failedCount = localPublicationVerificationResult.value.checks.filter((check) => check.status === 'fail').length
  return {
    status: localPublicationVerificationResult.value.status,
    receiptStatus: localPublicationVerificationResult.value.receipt_status,
    receiptSignature: localPublicationVerificationResult.value.receipt_signature,
    authority: localPublicationVerificationResult.value.authority,
    productRevisionLabel: formatRegistryRevisionLabel('Product', localPublicationVerificationResult.value.product_revision, null),
    developerRevisionLabel: formatRegistryRevisionLabel('Developer', localPublicationVerificationResult.value.developer_revision, null),
    failedCount,
    passedCount: localPublicationVerificationResult.value.checks.length - failedCount,
  }
})

function formatRegistryReceiptKey(receipt: RegistryPublishResult['receipt']) {
  if (!receipt.signature_algorithm || !receipt.key_id) return ''
  return `${receipt.signature_algorithm}:${receipt.key_id}`
}

function formatRegistryRevisionLabel(
  kind: 'Product' | 'Developer',
  revision: RegistryRevisionLineage['product_revision'] | RegistryRevisionLineage['developer_revision'] | null | undefined,
  fallback: { artifactId?: string | null, revisionNumber?: number | null } | null,
) {
  const revisionNumber = revision?.revision_number ?? fallback?.revisionNumber ?? null
  const artifactId = revision?.artifact_id ?? fallback?.artifactId ?? null
  const ref = revision?.ref ?? artifactId
  if (revisionNumber != null && ref) return `${kind} r${revisionNumber} (${ref})`
  if (revisionNumber != null) return `${kind} r${revisionNumber}`
  return ref || `${kind} revision not recorded`
}

function inferPublicationReceiptStatus(publication: DeveloperRegistryPublicationArtifactData) {
  if (!publication.receipt.registry_signature) return 'none'
  if (publication.authority === 'remote-registry' && publication.receipt.key_id) return 'signed'
  return 'present'
}

function formatReceiptStatus(status: string | null | undefined) {
  if (!status) return 'Not recorded'
  if (status === 'ok') return 'Verified'
  return developerLabel(status)
}

const registryPublicationHistoryRows = computed(() =>
  registryPublicationArtifacts.value.map((artifact) => {
    const data = artifact.data as DeveloperRegistryPublicationArtifactData
    const isLatestVerifiedLocal = data.authority === 'local-studio'
      && localPublicationVerificationResult.value?.package_id === data.package.package_id
      && localPublicationVerificationResult.value?.package_version === data.package.package_version
    const receiptKeyLabel = formatRegistryReceiptKey(data.receipt)
    const receiptStatus = data.local_verification?.receipt_status
      ?? data.promoted_from_local_publication?.receipt_status
      ?? inferPublicationReceiptStatus(data)
    const remoteTrustLabel = data.authority === 'remote-registry'
      ? (data.receipt.key_id ? `Verified by Registry key ${data.receipt.key_id}` : 'Remote receipt key metadata unavailable')
      : ''
    const productRevisionLabel = formatRegistryRevisionLabel('Product', data.package.lineage?.product_revision, {
      artifactId: data.published_from_saved_revision.product_revision_artifact_id ?? null,
      revisionNumber: data.published_from_saved_revision.product_revision_number ?? null,
    })
    const developerRevisionLabel = formatRegistryRevisionLabel('Developer', data.package.lineage?.developer_revision, {
      artifactId: data.published_from_saved_revision.revision_artifact_id ?? null,
      revisionNumber: data.published_from_saved_revision.revision_number ?? null,
    })
    return {
      artifactId: artifact.id,
      packageLabel: `${data.package.package_id}@${data.package.package_version}`,
      authorityLabel: data.authority === 'local-studio' ? 'Local Studio' : 'Remote Registry',
      authorityClass: data.authority === 'local-studio' ? 'local' : 'remote',
      stateLabel: data.promoted_from_local_publication
        ? (data.receipt.key_id ? 'Promoted + signed' : 'Promoted')
        : data.authority === 'local-studio'
          ? (data.local_verification?.status
              ? `Local ${data.local_verification.status === 'ok' ? 'verified' : 'failed'}`
              : (isLatestVerifiedLocal ? `Local ${localPublicationVerificationResult.value?.status === 'ok' ? 'verified' : 'failed'}` : 'Local'))
          : (data.receipt.key_id ? 'Signed remote' : 'Remote'),
      revisionLabel: data.published_from_saved_revision.revision_number
        ? `Revision ${data.published_from_saved_revision.revision_number}`
        : 'Revision unknown',
      productRevisionLabel,
      developerRevisionLabel,
      publishedAt: formatStudioTimestamp(data.publication.published_at || artifact.created_at),
      definitionDigest: data.package.definition_digest,
      lockDigest: data.package.lock_digest || '',
      receiptSignature: data.receipt.registry_signature,
      receiptStatus: formatReceiptStatus(receiptStatus),
      receiptKeyLabel,
      remoteTrustLabel,
      localPublicationId: data.local_publication_id || data.promoted_from_local_publication?.local_publication_id || '',
      promotedFrom: data.promoted_from_local_publication,
      metaItems: [
        { label: 'Revision', value: data.published_from_saved_revision.revision_number ? `r${data.published_from_saved_revision.revision_number}` : 'unknown' },
        { label: 'Product', value: productRevisionLabel },
        { label: 'Developer', value: developerRevisionLabel },
        { label: 'Published', value: formatStudioTimestamp(data.publication.published_at || artifact.created_at) },
        ...(data.local_publication_id || data.promoted_from_local_publication?.local_publication_id
          ? [{ label: 'Local ID', value: data.local_publication_id || data.promoted_from_local_publication?.local_publication_id || '' }]
          : []),
      ],
      digestItems: [
        { label: 'Definition', value: data.package.definition_digest },
        ...(data.package.lock_digest ? [{ label: 'Lock', value: data.package.lock_digest }] : []),
        { label: 'Receipt Status', value: formatReceiptStatus(receiptStatus) },
        ...(receiptKeyLabel ? [{ label: 'Registry Key', value: receiptKeyLabel }] : []),
        ...(remoteTrustLabel ? [{ label: 'Trust', value: remoteTrustLabel }] : []),
        { label: 'Receipt', value: data.receipt.registry_signature },
        ...(data.promoted_from_local_publication
          ? [{
              label: 'Promoted',
              value: `after ${data.promoted_from_local_publication.verification_status} verification at ${formatStudioTimestamp(data.promoted_from_local_publication.verified_at)}`,
            }]
          : []),
      ],
    }
  }),
)

function formatGenerationDependencySource(value: string | null | undefined) {
  if (value === 'local') return 'retired local workspace bundle'
  if (value === 'registry') return 'registry package / external CLI'
  return 'not recorded'
}

const latestGenerationRunRows = computed(() => {
  if (!latestGenerationRun.value) return []
  return [
    {
      label: 'Generated At',
      value: formatStudioTimestamp(latestGenerationRun.value.generated_at),
    },
    {
      label: 'Primary Output Mode',
      value: developerLabel(latestGenerationRun.value.generator_inputs.primary_output_mode || 'legacy_projection'),
    },
    {
      label: 'Dependency Mode',
      value: formatGenerationDependencySource(latestGenerationRun.value.generator_inputs.dependency_source),
    },
    {
      label: 'Runtime Target Mode',
      value: developerLabel(latestGenerationRun.value.generator_inputs.runtime_target_mode || 'compiled_contract'),
    },
    {
      label: 'Contract Signature',
      value: latestGenerationRun.value.compiled_contract_identity?.signature || 'Not recorded',
    },
    {
      label: 'Saved Revision',
      value: latestGenerationRun.value.definition_revision_number
        ? `Revision ${latestGenerationRun.value.definition_revision_number}`
        : 'Not recorded',
    },
    {
      label: 'Runtime Target Outputs',
      value: String(latestGenerationRun.value.outputs.runtime_target?.length ?? 0),
    },
  ]
})

const latestGeneratedStructure = computed<DeveloperGeneratedStructureSummary | null>(
  () => latestGenerationRun.value?.generated_structure ?? null,
)
const latestRuntimeTarget = computed<DeveloperGeneratedRuntimeTarget | null>(
  () => latestGenerationRun.value?.runtime_target ?? null,
)
const latestExtensionManifest = computed<DeveloperExtensionPoint[]>(
  () => latestGenerationRun.value?.extension_manifest ?? [],
)

async function clearAssistantSeededForSection(sectionId: string) {
  if (readOnlyMode.value) return
  const confirmed = await requestConfirmation({
    title: 'Clear assistant-seeded guidance?',
    message: 'This removes only exact-match assistant-seeded text from the current draft section. Manual edits are left intact. Save Developer Definition afterward if you want to persist the cleared state.',
    confirmLabel: 'Clear Guidance',
    cancelLabel: 'Cancel',
    tone: 'neutral',
  })
  if (!confirmed) return
  clearAssistantSeededSection(sectionId as any)
}

function openAssistantArtifacts(artifactType: string) {
  if (!project.value) return
  router.push(`/design/projects/${project.value.id}/pm-artifacts?assistantType=${encodeURIComponent(artifactType)}`)
}

function buildRuntimeTargetManifestOutput(runtimeTarget: DeveloperGeneratedRuntimeTarget) {
  const generatedAt = new Date().toISOString()
  const content = JSON.stringify(runtimeTarget, null, 2)
  return {
    kind: 'runtime_target_manifest',
    title: 'Runtime Target Manifest',
    filename: 'runtime-target-manifest.json',
    content_type: 'json',
    generated_at: generatedAt,
    content,
    content_length: content.length,
  }
}

function downloadText(filename: string, content: string, mediaType = 'application/json') {
  const blob = new Blob([content], { type: mediaType })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

function currentStudioProjectUrl(): string | null {
  if (!project.value || typeof window === 'undefined') return null
  try {
    return new URL(`/studio/design/projects/${project.value.id}`, window.location.origin).toString()
  } catch {
    return null
  }
}

function buildPackageReadme(packageVersion: string): string {
  if (!project.value) return ''
  const productRevision = baseline.value?.source_inputs.product_revision_number
  const developerRevision = latestSavedRevision.value?.revision_number
  const lines = [
    `# ${project.value.name} ANIP Package`,
    '',
    `Project: ${project.value.id}`,
    `Package version: ${packageVersion}`,
    productRevision ? `Product revision: r${productRevision}` : '',
    developerRevision ? `Developer revision: r${developerRevision}` : '',
    '',
    'This package contains the locked ANIP service definition, manifest, and publisher recommended lock exported by Studio.',
    'Business behavior is defined by the locked Product and Developer Design revisions; app-layer glue, if any, must stay outside the generic ANIP substrate.',
  ].filter(Boolean)
  return lines.join('\n')
}

function isPublicHttpUrl(value: string): boolean {
  try {
    const url = new URL(value)
    if (url.protocol !== 'http:' && url.protocol !== 'https:') return false
    const hostname = url.hostname.toLowerCase()
    return hostname !== 'localhost' && hostname !== '127.0.0.1' && hostname !== '0.0.0.0' && hostname !== '::1'
  } catch {
    return false
  }
}

function buildPackageSourceLinks(): Array<{ title: string; url: string }> {
  const studioUrl = currentStudioProjectUrl()
  return studioUrl && isPublicHttpUrl(studioUrl) ? [{ title: 'Studio Project', url: studioUrl }] : []
}

function emptyImplementationMaterialDraft(): ImplementationMaterialDraft {
  return {
    title: '',
    ref: '',
    bundle_tree_sha256: '',
  }
}

function addImplementationMaterialDraft() {
  if (readOnlyMode.value) return
  implementationMaterialDrafts.value.push(emptyImplementationMaterialDraft())
}

function removeImplementationMaterialDraft(index: number) {
  if (readOnlyMode.value) return
  implementationMaterialDrafts.value.splice(index, 1)
}

const sha256DigestPattern = /^sha256:[a-f0-9]{64}$/i
const customBundleRefPattern = /^(git\+https:\/\/[^#]+@[a-f0-9]{40,64}|registry:\/\/[A-Za-z0-9][A-Za-z0-9._/-]{0,255}@[A-Za-z0-9][A-Za-z0-9._+-]{0,127}|object\+https:\/\/[^#]+|object\+s3:\/\/[^#]+)#sha256:[a-f0-9]{64}$/i

function implementationMaterialRowError(row: ImplementationMaterialDraft): string | null {
  const title = row.title.trim()
  const ref = row.ref.trim()
  const bundleTreeDigest = row.bundle_tree_sha256.trim()
  if (!title && !ref && !bundleTreeDigest) return null
  if (!ref) return 'Implementation material ref is required when title or digest is provided.'
  if (title.length > 120) return 'Implementation material title must be 120 characters or less.'
  if (ref.length > 2048) return 'Implementation material ref must be 2048 characters or less.'
  if (/\s|[<>"'`{}|^\\]/.test(ref) || ref.includes('..')) {
    return 'Implementation material ref contains unsafe characters or path traversal.'
  }
  if (!customBundleRefPattern.test(ref)) {
    return 'Use an immutable ref with #sha256:<64 hex>. Supported schemes: git+https, registry, object+https, object+s3.'
  }
  if (bundleTreeDigest && !sha256DigestPattern.test(bundleTreeDigest)) {
    return 'Bundle tree digest must be sha256:<64 hex chars>.'
  }
  return null
}

const implementationMaterialErrors = computed(() =>
  implementationMaterialDrafts.value
    .map((row, index) => ({ index, error: implementationMaterialRowError(row) }))
    .filter((row): row is { index: number, error: string } => Boolean(row.error)),
)
const implementationMaterialError = computed(() => {
  const first = implementationMaterialErrors.value[0]
  return first ? `Implementation material ${first.index + 1}: ${first.error}` : null
})
const implementationMaterialsForPublish = computed(() =>
  implementationMaterialDrafts.value
    .map((row) => ({
      ...(row.title.trim() ? { title: row.title.trim() } : {}),
      ref: row.ref.trim(),
      ...(row.bundle_tree_sha256.trim() ? { bundle_tree_sha256: row.bundle_tree_sha256.trim().toLowerCase() } : {}),
    }))
    .filter((row) => row.ref),
)
const latestImplementationMaterials = computed(() => {
  const materials = latestRegistryPublication.value?.package.implementation_materials
    ?? latestRegistryPublication.value?.package.manifest?.implementation_material?.custom_code_bundles
    ?? []
  return Array.isArray(materials) ? materials : []
})

function buildBlueprintPackage() {
  if (!project.value || !definitionContract.value || !definition.value) return null
  const generatedAt = new Date().toISOString()
  const packageVersion = latestSavedRevision.value ? `0.1.${latestSavedRevision.value.revision_number}` : '0.1.0'
  const serviceDefinition = definitionContract.value
  const serviceDefinitionIdentity = definitionContractIdentity.value
  const runtimeTarget = buildGeneratedRuntimeTarget(definition.value)
  const extensionManifestEntries = buildExtensionManifest(definition.value)
  const adapterBindings = buildIntegrationAdapterBindings(definition.value)
  const conformanceReport = buildLocalConformanceReport({
    definition: definition.value,
    runtimeTarget,
    extensionManifest: extensionManifestEntries,
    generatedOutputKinds: buildGeneratedStructureSummary(definition.value).generated_output_kinds,
    generatedAt,
  })
  const manifest = {
    package_kind: 'anip_service_blueprint',
    blueprint_id: project.value.id,
    name: `${project.value.name} Service Blueprint`,
    version: packageVersion,
    schema_version: serviceDefinition.contract_schema_version ?? 'anip-service-definition/v1',
    anip_spec_version: STUDIO_PROTOCOL_VERSION,
    publisher: {
      id: 'local-studio',
      display_name: 'Local Studio Export',
    },
    service_definition: 'anip-service-definition.json',
    service_definition_digest: serviceDefinitionIdentity?.signature ?? null,
    service_definition_digest_algorithm: serviceDefinitionIdentity?.signature_algorithm ?? 'sha256',
    build_packs: {
      recommended: ['anip-build-pack@local'],
    },
    verifier_packs: {
      recommended: ['anip-verifier@local'],
    },
    readme: buildPackageReadme(packageVersion),
    source_links: buildPackageSourceLinks(),
    ...(implementationMaterialsForPublish.value.length
      ? {
          implementation_material: {
            custom_code_bundles: JSON.parse(JSON.stringify(implementationMaterialsForPublish.value)),
          },
        }
      : {}),
    agent_consumption_readiness: JSON.parse(JSON.stringify(savedAgentReadinessReport.value)),
    agent_consumability: JSON.parse(JSON.stringify(savedAgentConsumabilityMetadata.value)),
    agent_consumption_simulation: latestSimulationReport.value
      ? JSON.parse(JSON.stringify(latestSimulationReport.value))
      : null,
    agent_consumption_publication_gate: {
      status: simulationPublicationGate.value.status,
      label: simulationPublicationGate.value.label,
      detail: simulationPublicationGate.value.detail,
      overridden: simulationPublicationGate.value.status === 'overridden',
      latest_report_artifact_id: latestSimulationReportArtifact.value?.id ?? null,
    },
    generated_at: generatedAt,
  }
  const recommendedLock = {
    lock_kind: 'publisher_recommended_lock',
    blueprint_id: manifest.blueprint_id,
    blueprint_version: manifest.version,
    service_definition_digest: manifest.service_definition_digest,
    schema_version: manifest.schema_version,
    anip_spec_version: STUDIO_PROTOCOL_VERSION,
    build_packs: manifest.build_packs.recommended,
    verifier_packs: manifest.verifier_packs.recommended,
    runtime_packages: [],
    extension_packs: [],
    regression_packs: [],
    agent_consumption_readiness: {
      status: savedAgentReadinessReport.value.status,
      score: savedAgentReadinessReport.value.score,
      summary: JSON.parse(JSON.stringify(savedAgentReadinessReport.value.summary)),
    },
    agent_consumability: {
      schema_version: savedAgentConsumabilityMetadata.value.schema_version,
      capability_count: Object.keys(savedAgentConsumabilityMetadata.value.capabilities).length,
    },
    agent_consumption_simulation: latestSimulationReport.value
      ? {
          status: latestSimulationReport.value.status,
          summary: JSON.parse(JSON.stringify(latestSimulationReport.value.summary)),
          generated_at: latestSimulationReport.value.generated_at,
          simulator_runtime: JSON.parse(JSON.stringify(latestSimulationReport.value.simulator_runtime)),
        }
      : null,
    agent_consumption_publication_gate: JSON.parse(JSON.stringify(manifest.agent_consumption_publication_gate)),
    generated_at: generatedAt,
  }
  const extensionManifest = {
    manifest_kind: 'anip_extension_manifest',
    service_definition_digest: manifest.service_definition_digest,
    extension_points: extensionManifestEntries,
  }
  const conformancePlan = {
    plan_kind: 'anip_local_conformance_plan',
    service_definition_digest: manifest.service_definition_digest,
    required_checks: [
      'schema_valid',
      'dependencies_resolved',
      'generated',
      'extension_hooks_bound',
      'runtime_surface_valid',
      'contract_evidence_aligned',
    ],
  }
  return {
    package_kind: 'anip_blueprint_package_export',
    generated_at: generatedAt,
    files: {
      'manifest.json': manifest,
      'anip-service-definition.json': serviceDefinition,
      'anip.recommended.lock': recommendedLock,
      'metadata/agent-consumability.json': savedAgentConsumabilityMetadata.value,
      ...(latestSimulationReport.value
        ? { 'verification/agent-consumption-simulation-report.json': latestSimulationReport.value }
        : {}),
      'extensions/extension-manifest.json': extensionManifest,
      'bindings/integration-adapter-bindings.json': {
        binding_kind: 'anip_integration_adapter_bindings',
        service_definition_digest: manifest.service_definition_digest,
        bindings: adapterBindings,
      },
      'verification/conformance-plan.json': conformancePlan,
      'verification/anip-conformance-report.json': conformanceReport,
    },
  }
}

function exportBlueprintPackage() {
  if (!project.value) return
  const blueprintPackage = buildBlueprintPackage()
  if (!blueprintPackage) return
  downloadText(`${project.value.id}-anip-blueprint-package.json`, JSON.stringify(blueprintPackage, null, 2))
}

function resolveProductRevisionRef() {
  if (!baseline.value) return null
  const sourceInputs = (baseline.value.source_inputs as Record<string, unknown>) ?? {}
  const revisionArtifactId = typeof sourceInputs.product_revision_artifact_id === 'string'
    ? sourceInputs.product_revision_artifact_id.trim()
    : ''
  const revisionNumber = typeof sourceInputs.product_revision_number === 'number'
    ? sourceInputs.product_revision_number
    : null
  if (revisionArtifactId) {
    return revisionNumber ? `${revisionArtifactId}@r${revisionNumber}` : revisionArtifactId
  }
  return `baseline:${baseline.value.locked_at}`
}

function buildRegistryRevisionLineage(productRevisionRef: string, developerRevisionRef: string): RegistryRevisionLineage | null {
  if (!project.value || !baseline.value || !latestSavedRevision.value) return null
  return {
    project_ref: project.value.id,
    product_revision: {
      ref: productRevisionRef,
      artifact_id: baseline.value.source_inputs.product_revision_artifact_id ?? null,
      revision_number: baseline.value.source_inputs.product_revision_number ?? null,
      baseline_locked_at: baseline.value.locked_at,
    },
    developer_revision: {
      ref: developerRevisionRef,
      artifact_id: latestSavedRevision.value.revision_artifact_id,
      revision_number: latestSavedRevision.value.revision_number,
      contract_signature: savedContractSignature.value,
    },
  }
}

function buildRegistryPublishPayload() {
  if (!project.value || !baseline.value || !definitionContract.value || !latestSavedRevision.value) return null
  const blueprintPackage = buildBlueprintPackage()
  if (!blueprintPackage) return null
  const files = blueprintPackage.files as Record<string, Record<string, any> | undefined>
  const manifest = files['manifest.json']
  const serviceDefinition = files['anip-service-definition.json']
  const recommendedLock = files['anip.recommended.lock']
  if (!manifest || !serviceDefinition || !recommendedLock) return null
  const productRevisionRef = resolveProductRevisionRef() ?? `baseline:${baseline.value.locked_at}`
  const developerRevisionRef = latestSavedRevision.value.revision_artifact_id || `developer-revision:${latestSavedRevision.value.revision_number}`
  const lineage = buildRegistryRevisionLineage(productRevisionRef, developerRevisionRef)
  if (lineage) {
    manifest.lineage = JSON.parse(JSON.stringify(lineage))
    recommendedLock.lineage = JSON.parse(JSON.stringify(lineage))
  }
  const payload: RegistryPublishRequest = {
    package_id: String(manifest.blueprint_id ?? project.value.id),
    package_version: String(manifest.version ?? `0.1.${latestSavedRevision.value.revision_number}`),
    project_ref: project.value.id,
    product_revision_ref: productRevisionRef,
    developer_revision_ref: developerRevisionRef,
    contract_signature: savedContractSignature.value,
    ...(lineage ? { lineage } : {}),
    schema_version: String(serviceDefinition.contract_schema_version ?? manifest.schema_version ?? 'anip-service-definition/v1'),
    manifest,
    service_definition: serviceDefinition,
    recommended_lock: recommendedLock,
    readme: String(manifest.readme ?? ''),
    source_links: Array.isArray(manifest.source_links) ? manifest.source_links : [],
    implementation_materials: implementationMaterialsForPublish.value,
  }
  return payload
}

async function publishToRegistry() {
  if (readOnlyMode.value) {
    registryPublishError.value = readOnlyReason.value
    return
  }
  if (registryPublishBlockedReason.value) {
    registryPublishError.value = registryPublishBlockedReason.value
    return
  }
  const payload = buildRegistryPublishPayload()
  if (!project.value || !payload || !latestSavedRevision.value || !baseline.value) {
    registryPublishError.value = 'Studio could not assemble the publish payload from the current saved revision.'
    return
  }

  const confirmed = await requestConfirmation({
    title: 'Publish to Registry?',
    message: `Publish ${payload.package_id}@${payload.package_version} from saved revision ${latestSavedRevision.value.revision_number} to the separate Registry service?`,
    confirmLabel: 'Publish',
    cancelLabel: 'Cancel',
    tone: 'neutral',
  })
  if (!confirmed) return

  publishingRegistry.value = true
  registryPublishError.value = null
  try {
    const result = await publishRegistryPackage(payload)
    registryPublishResult.value = result
    await createPmArtifact(project.value.id, {
      id: `${project.value.id}-registry-publication-${Date.now()}`,
      title: `Registry Publication ${result.package.package_id}@${result.package.package_version}`,
      data: {
        artifact_type: 'developer_registry_publication',
        authority: 'remote-registry',
        publication: result.publication,
        package: result.package,
        receipt: result.receipt,
        approved_from_pm_review: {
          approval_artifact_id: approvalLineage.value.artifactId,
          approved_at: approvalLineage.value.reviewedAt,
          product_revision: approvalLineage.value.productLabel,
          developer_revision: approvalLineage.value.developerLabel,
          contract_signature: approvalLineage.value.contractSignature,
        },
        published_from_saved_revision: {
          revision_number: latestSavedRevision.value.revision_number,
          revision_artifact_id: latestSavedRevision.value.revision_artifact_id,
          product_revision_artifact_id: baseline.value.source_inputs.product_revision_artifact_id ?? null,
          product_revision_number: baseline.value.source_inputs.product_revision_number ?? null,
          baseline_locked_at: baseline.value.locked_at,
        },
      } satisfies DeveloperRegistryPublicationArtifactData,
    })
    await refreshArtifacts()
  } catch (err) {
    registryPublishError.value = err instanceof Error ? err.message : String(err)
  } finally {
    publishingRegistry.value = false
  }
}

async function publishToLocalRegistry() {
  if (readOnlyMode.value) {
    registryPublishError.value = readOnlyReason.value
    return
  }
  if (localPublishBlockedReason.value) {
    registryPublishError.value = localPublishBlockedReason.value
    return
  }
  const payload = buildRegistryPublishPayload()
  if (!project.value || !payload || !latestSavedRevision.value || !baseline.value) {
    registryPublishError.value = 'Studio could not assemble the local publish payload from the current saved revision.'
    return
  }

  const confirmed = await requestConfirmation({
    title: 'Publish Locally?',
    message: `Create immutable Studio-local package ${payload.package_id}@${payload.package_version} from saved revision ${latestSavedRevision.value.revision_number}?`,
    confirmLabel: 'Publish locally',
    cancelLabel: 'Cancel',
    tone: 'neutral',
  })
  if (!confirmed) return

  publishingLocalRegistry.value = true
  registryPublishError.value = null
  try {
    const result = await publishLocalRegistryPackage(project.value.id, payload)
    localRegistryPublishResult.value = result
    localPublicationVerificationResult.value = null
    localPublicationVerificationError.value = null
    await createPmArtifact(project.value.id, {
      id: `${project.value.id}-local-publication-${Date.now()}`,
      title: `Local Publication ${result.package.package_id}@${result.package.package_version}`,
      data: {
        artifact_type: 'developer_registry_publication',
        authority: 'local-studio',
        publication: result.publication,
        package: result.package,
        receipt: result.receipt,
        local_publication_id: result.id,
        published_from_saved_revision: {
          revision_number: latestSavedRevision.value.revision_number,
          revision_artifact_id: latestSavedRevision.value.revision_artifact_id,
          product_revision_artifact_id: baseline.value.source_inputs.product_revision_artifact_id ?? null,
          product_revision_number: baseline.value.source_inputs.product_revision_number ?? null,
          baseline_locked_at: baseline.value.locked_at,
        },
      } satisfies DeveloperRegistryPublicationArtifactData,
    })
    await refreshArtifacts()
  } catch (err) {
    registryPublishError.value = err instanceof Error ? err.message : String(err)
  } finally {
    publishingLocalRegistry.value = false
  }
}

async function verifyLatestLocalPublication() {
  if (readOnlyMode.value) {
    localPublicationVerificationError.value = readOnlyReason.value
    return
  }
  if (!project.value || !latestLocalPublicationBundle.value) return
  localPublicationVerificationRunning.value = true
  localPublicationVerificationError.value = null
  try {
    const verification = await verifyLocalRegistryPackage(
      project.value.id,
      latestLocalPublicationBundle.value.publicationId,
    )
    localPublicationVerificationResult.value = verification
    if (latestRegistryPublicationArtifact.value && latestRegistryPublication.value?.authority === 'local-studio') {
      const failedCount = verification.checks.filter((check) => check.status === 'fail').length
      await updatePmArtifact(project.value.id, latestRegistryPublicationArtifact.value.id, {
        data: {
          ...(latestRegistryPublicationArtifact.value.data ?? {}),
          local_verification: {
            status: verification.status,
            receipt_status: verification.receipt_status,
            receipt_signature: verification.receipt_signature,
            verified_at: new Date().toISOString(),
            passed_checks: verification.checks.length - failedCount,
            failed_checks: failedCount,
            product_revision: verification.product_revision ?? null,
            developer_revision: verification.developer_revision ?? null,
          },
        },
      })
      await refreshArtifacts()
    }
  } catch (err) {
    localPublicationVerificationError.value = err instanceof Error ? err.message : String(err)
  } finally {
    localPublicationVerificationRunning.value = false
  }
}

function buildRegistryPublishPayloadFromLocalPublication(record: LocalPublicationRecord): RegistryPublishRequest {
  return {
    package_id: record.package.package_id,
    package_version: record.package.package_version,
    project_ref: record.package.project_ref,
    product_revision_ref: record.package.product_revision_ref,
    developer_revision_ref: record.package.developer_revision_ref,
    contract_signature: record.package.contract_signature,
    ...(record.package.lineage ? { lineage: record.package.lineage } : {}),
    schema_version: record.package.schema_version,
    manifest: record.package.manifest ?? {},
    service_definition: record.package.service_definition ?? {},
    recommended_lock: record.package.recommended_lock ?? {},
    readme: record.package.readme ?? String(record.package.manifest?.readme ?? ''),
    source_links: Array.isArray(record.package.source_links)
      ? record.package.source_links
      : (Array.isArray(record.package.manifest?.source_links) ? record.package.manifest.source_links : []),
    implementation_materials: Array.isArray(record.package.implementation_materials)
      ? record.package.implementation_materials
      : (Array.isArray(record.package.manifest?.implementation_material?.custom_code_bundles)
          ? record.package.manifest.implementation_material.custom_code_bundles
          : []),
  }
}

async function promoteLatestLocalPublicationToRegistry() {
  if (readOnlyMode.value) {
    registryPublishError.value = readOnlyReason.value
    return
  }
  if (!project.value || !latestLocalPublicationBundle.value || !latestRegistryPublication.value) return
  if (registryPublishBlockedReason.value) {
    registryPublishError.value = registryPublishBlockedReason.value
    return
  }

  const confirmed = await requestConfirmation({
    title: 'Promote local publication?',
    message: `Verify and promote ${latestRegistryPublication.value.package.package_id}@${latestRegistryPublication.value.package.package_version} from Studio-local storage to the Registry service?`,
    confirmLabel: 'Promote',
    cancelLabel: 'Cancel',
    tone: 'neutral',
  })
  if (!confirmed) return

  promotingLocalPublication.value = true
  registryPublishError.value = null
  localPublicationVerificationError.value = null
  try {
    const publicationId = latestLocalPublicationBundle.value.publicationId
    const verification = await verifyLocalRegistryPackage(project.value.id, publicationId)
    localPublicationVerificationResult.value = verification
    if (verification.status !== 'ok') {
      registryPublishError.value = `Local publication verification failed. Fix or recreate the local publication before promoting it.`
      return
    }

    const localRecord = await getLocalRegistryPackage(project.value.id, publicationId)
    const payload = buildRegistryPublishPayloadFromLocalPublication(localRecord)
    const result = await publishRegistryPackage(payload)
    registryPublishResult.value = result
    await createPmArtifact(project.value.id, {
      id: `${project.value.id}-registry-promotion-${Date.now()}`,
      title: `Registry Promotion ${result.package.package_id}@${result.package.package_version}`,
      data: {
        artifact_type: 'developer_registry_publication',
        authority: 'remote-registry',
        publication: result.publication,
        package: result.package,
        receipt: result.receipt,
        local_publication_id: publicationId,
        approved_from_pm_review: {
          approval_artifact_id: approvalLineage.value.artifactId,
          approved_at: approvalLineage.value.reviewedAt,
          product_revision: approvalLineage.value.productLabel,
          developer_revision: approvalLineage.value.developerLabel,
          contract_signature: approvalLineage.value.contractSignature,
        },
        promoted_from_local_publication: {
          local_publication_id: publicationId,
          local_receipt_signature: localRecord.receipt.registry_signature,
          verification_status: verification.status,
          receipt_status: verification.receipt_status,
          verified_at: new Date().toISOString(),
        },
        published_from_saved_revision: latestRegistryPublication.value.published_from_saved_revision,
      } satisfies DeveloperRegistryPublicationArtifactData,
    })
    await refreshArtifacts()
  } catch (err) {
    registryPublishError.value = err instanceof Error ? err.message : String(err)
  } finally {
    promotingLocalPublication.value = false
  }
}

async function recordReleaseForLatestRemotePublication() {
  if (readOnlyMode.value) {
    releaseError.value = readOnlyReason.value
    return
  }
  if (!project.value || !latestRemotePublicationArtifact.value || !latestRemotePublication.value || !approvalLineage.value.artifactId) return
  if (releaseBlockedReason.value) {
    releaseError.value = releaseBlockedReason.value
    return
  }

  const confirmed = await requestConfirmation({
    title: 'Record release?',
    message: `Mark ${latestRemotePublication.value.package.package_id}@${latestRemotePublication.value.package.package_version} as the released package for the approved revision chain?`,
    confirmLabel: 'Record release',
    cancelLabel: 'Cancel',
    tone: 'neutral',
  })
  if (!confirmed) return

  recordingRelease.value = true
  releaseError.value = null
  try {
    const releasedAt = new Date().toISOString()
    const releaseId = `${project.value.id}-release-${Date.now()}`
    await createPmArtifact(project.value.id, {
      id: releaseId,
      title: `Release ${latestRemotePublication.value.package.package_id}@${latestRemotePublication.value.package.package_version}`,
      data: {
        artifact_type: 'anip_release_record',
        release_id: releaseId,
        released_at: releasedAt,
        release_status: 'released',
        publication_artifact_id: latestRemotePublicationArtifact.value.id,
        approval_artifact_id: approvalLineage.value.artifactId,
        package_id: latestRemotePublication.value.package.package_id,
        package_version: latestRemotePublication.value.package.package_version,
        authority: latestRemotePublication.value.authority,
        receipt_signature: latestRemotePublication.value.receipt.registry_signature,
        approved_revision_chain: {
          product_revision_artifact_id: baseline.value?.source_inputs.product_revision_artifact_id ?? null,
          product_revision_number: baseline.value?.source_inputs.product_revision_number ?? null,
          developer_revision_artifact_id: latestSavedRevision.value?.revision_artifact_id ?? null,
          developer_revision_number: latestSavedRevision.value?.revision_number ?? null,
          contract_signature: savedContractSignature.value || null,
        },
      } satisfies ReleaseRecordData,
    })
    await refreshArtifacts()
  } catch (err) {
    releaseError.value = err instanceof Error ? err.message : String(err)
  } finally {
    recordingRelease.value = false
  }
}

function buildServiceEstateManifestOutput(runtimeTarget: DeveloperGeneratedRuntimeTarget) {
  const generatedAt = new Date().toISOString()
  const manifest = {
    system_name: runtimeTarget.system_name,
    domain_name: runtimeTarget.domain_name,
    protocols: runtimeTarget.protocols,
    service_generation_mode: runtimeTarget.service_generation_mode,
    services: runtimeTarget.services.map((service) => ({
      service_id: service.service_id,
      service_name: service.service_name,
      source_role: service.source_role,
      capability_ids: service.capabilities.map((capability) => capability.capability_id),
      backend_bindings: service.backend_bindings,
      participating_scenario_ids: service.participating_scenario_ids,
    })),
  }
  const content = JSON.stringify(manifest, null, 2)
  return {
    kind: 'service_estate_manifest',
    title: 'Service Estate Manifest',
    filename: 'service-estate-manifest.json',
    content_type: 'json',
    generated_at: generatedAt,
    content,
    content_length: content.length,
  }
}

function buildServiceCompositionManifestOutput(runtimeTarget: DeveloperGeneratedRuntimeTarget) {
  const generatedAt = new Date().toISOString()
  const manifest = {
    system_name: runtimeTarget.system_name,
    required_behavior_tokens: runtimeTarget.required_behavior_tokens,
    required_anip_support_tokens: runtimeTarget.required_anip_support_tokens,
    extension_point_ids: runtimeTarget.extension_point_ids,
  }
  const content = JSON.stringify(manifest, null, 2)
  return {
    kind: 'service_composition_manifest',
    title: 'Service Composition Manifest',
    filename: 'service-composition-manifest.json',
    content_type: 'json',
    generated_at: generatedAt,
    content,
    content_length: content.length,
  }
}

function buildPerServiceRuntimeOutputs(runtimeTarget: DeveloperGeneratedRuntimeTarget) {
  const generatedAt = new Date().toISOString()
  return runtimeTarget.services.map((service) => {
    const content = JSON.stringify({
      service_id: service.service_id,
      service_name: service.service_name,
      source_role: service.source_role,
      protocols: service.protocols,
      owned_concept_ids: service.owned_concept_ids,
      backend_bindings: service.backend_bindings,
      participating_scenario_ids: service.participating_scenario_ids,
      orchestration_step_ids: service.orchestration_step_ids,
      capabilities: service.capabilities,
    }, null, 2)
    return {
      kind: 'runtime_service_contract',
      title: `${service.service_name} Runtime Service Contract`,
      filename: `runtime/${service.service_id}.service-contract.json`,
      content_type: 'json',
      generated_at: generatedAt,
      content,
      content_length: content.length,
    }
  })
}

function buildRuntimeDesignPacketOutput(
  runtimeTarget: DeveloperGeneratedRuntimeTarget,
  extensionManifest: DeveloperExtensionPoint[],
) {
  const generatedAt = new Date().toISOString()
  const lines = [
    '# Runtime Design Packet',
    '',
    `System: ${runtimeTarget.system_name}`,
    `Domain: ${runtimeTarget.domain_name || 'unspecified'}`,
    `Delivery Model: ${developerLabel(runtimeTarget.delivery_model)}`,
    `Architecture Shape: ${developerLabel(runtimeTarget.architecture_shape)}`,
    '',
    '## Services',
    '',
    ...runtimeTarget.services.flatMap((service) => [
      `### ${service.service_name}`,
      `- Service ID: \`${service.service_id}\``,
      `- Protocols: ${service.protocols.join(', ') || 'none'}`,
      `- Backend Bindings: ${service.backend_bindings.join(', ') || 'none'}`,
      `- Capabilities: ${service.capabilities.map((capability) => `\`${capability.capability_id}\``).join(', ') || 'none'}`,
      '',
    ]),
    '## Extension Layer',
    '',
    ...extensionManifest.map((entry) => `- ${entry.label}: ${developerLabel(entry.ownership)} via \`${entry.plugin_surface}\``),
  ]
  const content = lines.join('\n')
  return {
    kind: 'runtime_design_packet',
    title: 'Runtime Design Packet',
    filename: 'runtime-design-packet.md',
    content_type: 'markdown',
    generated_at: generatedAt,
    content,
    content_length: content.length,
  }
}

function buildRuntimeScenarioPackOutput() {
  const generatedAt = new Date().toISOString()
  const scenarios = definition.value.scenario_formalizations.map((scenario) => ({
    scenario_id: scenario.scenario_id,
    scenario_title: scenario.scenario_title,
    participating_service_ids: scenario.participating_service_ids,
    required_behaviors: scenario.required_behaviors,
    required_anip_support: scenario.required_anip_support,
    orchestration_steps: scenario.orchestration_steps.map((step, index) => ({
      id: step.id || `step-${index + 1}`,
      service_id: step.service_id,
      step_kind: step.step_kind,
      capability_id: step.capability_id || null,
      outcome_type: step.outcome_type,
      stop_condition: step.stop_condition,
      outcome_notes: step.outcome_notes,
    })),
  }))
  const content = JSON.stringify({ scenarios }, null, 2)
  return {
    kind: 'runtime_scenario_pack',
    title: 'Runtime Scenario Pack',
    filename: 'runtime-scenario-pack.json',
    content_type: 'json',
    generated_at: generatedAt,
    content,
    content_length: content.length,
  }
}

function buildRuntimeScenarioManifestOutput() {
  const generatedAt = new Date().toISOString()
  const manifest = definition.value.scenario_formalizations.map((scenario) => ({
    scenario_id: scenario.scenario_id,
    title: scenario.scenario_title,
    service_count: scenario.participating_service_ids.length,
    orchestration_step_count: scenario.orchestration_steps.length,
  }))
  const content = JSON.stringify({ scenarios: manifest }, null, 2)
  return {
    kind: 'runtime_scenario_manifest',
    title: 'Runtime Scenario Manifest',
    filename: 'runtime-scenario-manifest.json',
    content_type: 'json',
    generated_at: generatedAt,
    content,
    content_length: content.length,
  }
}

function buildRuntimeBackendBindingsOutput(runtimeTarget: DeveloperGeneratedRuntimeTarget) {
  const generatedAt = new Date().toISOString()
  const bindings = runtimeTarget.services.map((service) => ({
    service_id: service.service_id,
    service_name: service.service_name,
    backend_bindings: service.backend_bindings,
    capability_backend_operations: service.capabilities.map((capability) => ({
      capability_id: capability.capability_id,
      backend_operation: capability.backend_operation,
      path_template: capability.path_template,
    })),
  }))
  const content = JSON.stringify({ bindings }, null, 2)
  return {
    kind: 'runtime_backend_bindings',
    title: 'Runtime Backend Bindings',
    filename: 'runtime-backend-bindings.json',
    content_type: 'json',
    generated_at: generatedAt,
    content,
    content_length: content.length,
  }
}

function buildIntegrationAdapterBindingsOutput(definitionData: DeveloperDefinitionData) {
  const generatedAt = new Date().toISOString()
  const bindings = buildIntegrationAdapterBindings(definitionData)
  const content = JSON.stringify({
    binding_kind: 'anip_integration_adapter_bindings',
    service_definition_digest: definitionData.compiled_contract_identity?.signature ?? null,
    bindings,
  }, null, 2)
  return {
    kind: 'integration_adapter_bindings',
    title: 'Integration Adapter Bindings',
    filename: 'bindings/integration-adapter-bindings.json',
    content_type: 'json',
    generated_at: generatedAt,
    content,
    content_length: content.length,
  }
}

function buildBackendSelectionTemplateOutput(definitionData: DeveloperDefinitionData) {
  const generatedAt = new Date().toISOString()
  const capabilities = buildIntegrationAdapterBindings(definitionData).map((binding) => {
    const availableBindings = binding.backend_bindings.length > 0
      ? binding.backend_bindings
      : [{
          backend_kind: binding.backend_kind,
          connection_ref: binding.connection_ref,
          raw_operation_refs: binding.raw_operation_refs,
        }]
    return {
      capability_id: binding.capability_id,
      service_id: binding.service_id,
      selection_required: availableBindings.length > 1,
      active_backend_kind: availableBindings.length === 1 ? availableBindings[0].backend_kind : '',
      active_connection_ref: availableBindings.length === 1 ? availableBindings[0].connection_ref : '',
      available_backend_bindings: availableBindings.map((availableBinding) => ({
        backend_kind: availableBinding.backend_kind,
        connection_ref: availableBinding.connection_ref,
        raw_operation_refs: [...availableBinding.raw_operation_refs],
      })),
    }
  })
  const content = JSON.stringify({
    template_kind: 'anip_backend_selection_template',
    selection_scope: 'deployment',
    service_definition_digest: definitionData.compiled_contract_identity?.signature ?? null,
    capabilities,
  }, null, 2)
  return {
    kind: 'backend_selection_template',
    title: 'Backend Selection Template',
    filename: 'deployment/backend-selection.template.json',
    content_type: 'json',
    generated_at: generatedAt,
    content,
    content_length: content.length,
  }
}

function buildLocalConformanceReportOutput(
  definitionData: DeveloperDefinitionData,
  runtimeTarget: DeveloperGeneratedRuntimeTarget,
  extensionManifest: DeveloperExtensionPoint[],
  generatedOutputKinds: string[],
) {
  const generatedAt = new Date().toISOString()
  const report = buildLocalConformanceReport({
    definition: definitionData,
    runtimeTarget,
    extensionManifest,
    generatedOutputKinds,
    generatedAt,
  })
  const content = JSON.stringify(report, null, 2)
  return {
    kind: 'anip_local_conformance_report',
    title: 'ANIP Local Conformance Report',
    filename: 'verification/anip-conformance-report.json',
    content_type: 'json',
    generated_at: generatedAt,
    content,
    content_length: content.length,
  }
}

function buildExtensionPlaybookOutput(
  runtimeTarget: DeveloperGeneratedRuntimeTarget,
  extensionManifest: DeveloperExtensionPoint[],
) {
  const generatedAt = new Date().toISOString()
  const lines = [
    '# Extension Playbook',
    '',
    `System: ${runtimeTarget.system_name}`,
    `Domain: ${runtimeTarget.domain_name || 'unspecified'}`,
    '',
    '## Generated Service Estate',
    '',
    ...runtimeTarget.services.flatMap((service) => [
      `- ${service.service_name} (\`${service.service_id}\`)`,
      `  - Protocols: ${service.protocols.join(', ') || 'none'}`,
      `  - Backend bindings: ${service.backend_bindings.join(', ') || 'none'}`,
      `  - Capabilities: ${service.capabilities.map((capability) => `\`${capability.capability_id}\``).join(', ') || 'none'}`,
    ]),
    '',
    '## Extension Surfaces',
    '',
    ...extensionManifest.map((entry) => `- ${entry.label}: ${developerLabel(entry.ownership)} via \`${entry.plugin_surface}\` — ${entry.rationale}`),
  ]
  const content = lines.join('\n')
  return {
    kind: 'extension_playbook',
    title: 'Extension Playbook',
    filename: 'extension-playbook.md',
    content_type: 'markdown',
    generated_at: generatedAt,
    content,
    content_length: content.length,
  }
}

async function persistGenerationRun() {
  if (readOnlyMode.value) return
  if (!project.value || !definitionContract.value) return
  const runtimeTarget = buildGeneratedRuntimeTarget(definition.value)
  const extensionManifest = buildExtensionManifest(definition.value)
  const baseRuntimeOutputs: DeveloperGeneratedArtifactOutput[] = [
    buildRuntimeTargetManifestOutput(runtimeTarget),
    buildRuntimeDesignPacketOutput(runtimeTarget, extensionManifest),
    buildServiceEstateManifestOutput(runtimeTarget),
    buildServiceCompositionManifestOutput(runtimeTarget),
    buildRuntimeScenarioPackOutput(),
    buildRuntimeScenarioManifestOutput(),
    buildRuntimeBackendBindingsOutput(runtimeTarget),
    buildIntegrationAdapterBindingsOutput(definition.value),
    buildBackendSelectionTemplateOutput(definition.value),
    ...buildPerServiceRuntimeOutputs(runtimeTarget),
    buildExtensionPlaybookOutput(runtimeTarget, extensionManifest),
  ]
  const runtimeOutputs: DeveloperGeneratedArtifactOutput[] = [
    ...baseRuntimeOutputs,
    buildLocalConformanceReportOutput(
      definition.value,
      runtimeTarget,
      extensionManifest,
      [...baseRuntimeOutputs.map((output) => output.kind), 'anip_local_conformance_report'],
    ),
  ]
  await createPmArtifact(project.value.id, {
    id: `${project.value.id}-generation-${Date.now()}`,
    title: 'Developer Generation Run',
    data: {
      artifact_type: 'developer_generation_run',
      launch_surface: 'developer_definition',
      generated_at: new Date().toISOString(),
      compiled_contract_identity: savedDefinition.value?.compiled_contract_identity
        ? JSON.parse(JSON.stringify(savedDefinition.value.compiled_contract_identity))
        : null,
      definition_revision_artifact_id: savedDefinition.value?.saved_revision?.revision_artifact_id ?? null,
      definition_revision_number: savedDefinition.value?.saved_revision?.revision_number ?? null,
      source_inputs: {
        product_revision_artifact_id: baseline.value?.source_inputs.product_revision_artifact_id ?? null,
        product_revision_number: baseline.value?.source_inputs.product_revision_number ?? null,
        product_design_hash: baseline.value?.source_inputs.product_design_hash ?? null,
        requirements_id: baseline.value?.source_inputs.requirements_id ?? null,
        requirements_hash: baseline.value?.source_inputs.requirements_hash ?? null,
        scenario_ids: [...(baseline.value?.source_inputs.scenario_ids ?? [])],
        scenario_set_hash: baseline.value?.source_inputs.scenario_set_hash ?? null,
        shape_id: baseline.value?.source_inputs.shape_id ?? null,
        shape_hash: baseline.value?.source_inputs.shape_hash ?? null,
        baseline_locked_at: baseline.value?.locked_at ?? null,
      },
      generator_inputs: {
        runtime_target_mode: 'compiled_contract',
        primary_output_mode: 'runtime_target',
        dependency_source: 'registry',
        toolchain: 'go_external',
        studio_generation_mode: 'contract_projection_only',
        external_generator_required: true,
      },
      generated_structure: buildGeneratedStructureSummary(definition.value),
      runtime_target: runtimeTarget,
      extension_manifest: extensionManifest,
      agent_consumption_readiness: JSON.parse(JSON.stringify(savedAgentReadinessReport.value)),
      agent_consumability: JSON.parse(JSON.stringify(savedAgentConsumabilityMetadata.value)),
      outputs: {
        runtime_target: runtimeOutputs,
      },
    },
  })
  await refreshArtifacts()
}

async function generateFromDefinition() {
  if (readOnlyMode.value) {
    generationError.value = readOnlyReason.value
    return
  }
  if (generationBlockedReason.value) {
    generationError.value = generationBlockedReason.value
    return
  }
  generationLoading.value = true
  generationError.value = null
  try {
    await persistGenerationRun()
  } catch (err) {
    generationError.value = err instanceof Error ? err.message : String(err)
  } finally {
    generationLoading.value = false
  }
}

function downloadSavedGeneratedOutput(output: {
  kind: string
  title: string
  filename: string
  content_type: string
  content: string
  generated_at: string
}) {
  const mime =
    output.content_type === 'json'
      ? 'application/json;charset=utf-8'
      : output.content_type === 'markdown'
        ? 'text/markdown;charset=utf-8'
        : output.content_type === 'yaml'
          ? 'text/yaml;charset=utf-8'
          : 'text/plain;charset=utf-8'
  const blob = new Blob([output.content], { type: mime })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = output.filename
  link.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <div class="developer-definition">
    <template v-if="project">
      <section class="page-header">
        <button class="back-link" type="button" @click="router.push(`/design/projects/${project.id}/developer`)">
          &larr; Back to Developer Design
        </button>
        <div class="page-kicker">Developer Design</div>
        <h1>Developer Definition</h1>
        <p>
          This page is now the compiled contract surface. Use the formalization pages to define service structure, scenario execution, generation settings, and evidence planning. This page shows the current compiled contract and exportable output.
        </p>
        <div class="page-role-strip">
          <span class="page-role-chip tone-compile">Compiled Contract</span>
          <span class="page-role-chip tone-review">Review Surface</span>
          <span class="page-role-chip tone-evidence">Generation Launch</span>
        </div>
      </section>
      <section class="panel note-panel">
        <h2>Compiled Contract Surface</h2>
        <p class="panel-copy">
          The formalization work now lives on dedicated Developer Design pages. This page is the assembled technical contract that generation, verification, CLI export, and later CI/CD should consume.
        </p>
        <p class="panel-copy subtle-copy">
          Treat the other Developer Design pages as authoring surfaces. Treat this page as the working draft, saved revision, export surface, and launch point for generation.
        </p>
      </section>

      <div v-if="readOnlyMode" class="readonly-banner">
        <strong>Read-only showcase mode</strong>
        <span>{{ readOnlyReason }}</span>
      </div>

      <section v-if="!baseline" class="panel empty-panel">
        <h2>Developer baseline is not locked</h2>
        <p>Return to Developer Overview and lock Product Design before working on the compiled contract.</p>
      </section>

      <section v-else-if="!baselineAligned" class="panel empty-panel">
        <h2>Locked baseline is out of sync</h2>
        <p>Product Design changed after the current developer baseline was locked. Re-lock the baseline before treating this definition as current.</p>
      </section>

      <section v-else class="grid">
        <article id="generation-launch" class="panel definition-summary-panel">
          <div class="panel-header">
            <h2>Locked Baseline</h2>
          </div>
          <div class="summary-stack">
            <div class="summary-row">
              <span class="summary-label">Requirements Set</span>
              <strong>{{ lockedRequirements?.title }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Scenario Pack</span>
              <strong>{{ lockedScenarios.length }} scenarios</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Service Design</span>
              <strong>{{ lockedShape?.title }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Locked At</span>
              <strong>{{ formatStudioTimestamp(baseline.locked_at) }}</strong>
            </div>
          </div>
        </article>

        <article class="panel definition-summary-panel">
          <div class="panel-header">
            <h2>Definition Status</h2>
            <button class="btn btn-secondary" :disabled="!canSaveDefinition" @click="saveDefinition">
              {{ saveButtonLabel }}
            </button>
          </div>
          <p class="panel-copy definition-status-copy">
            Saving turns the working draft into an immutable saved revision. Generation and verification align against that revision, not unsaved page state.
          </p>
          <p v-if="definitionSaveBlockedReason && !readOnlyMode" class="hint compact">{{ definitionSaveBlockedReason }}</p>
          <p v-if="saveError" class="error">{{ saveError }}</p>
          <div class="summary-stack">
            <div class="summary-row">
              <span class="summary-label">Saved Revision Status</span>
              <strong :class="['status-text', definitionSaveStatus.tone]">{{ definitionSaveStatus.label }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Draft vs Saved Revision</span>
              <strong>{{ definitionSaveStatus.detail }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Latest Saved Revision</span>
              <strong>{{ latestSavedRevision ? `Revision ${latestSavedRevision.revision_number}` : 'Not saved yet' }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Latest Saved Revision Matches Locked Baseline</span>
              <strong>{{ savedDefinition ? (definitionAligned ? 'Yes' : 'No') : 'Not available' }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Coverage Record</span>
              <strong>{{ traceabilityRecord ? 'Present' : 'Not saved yet' }}</strong>
            </div>
          </div>
        </article>

        <article class="panel panel-full contract-source-readiness-panel">
          <div class="panel-header">
            <h2>Contract Source Readiness</h2>
          </div>
          <div class="source-card-grid">
            <button
              v-for="source in sourceCards"
              :key="source.id"
              class="source-card"
              type="button"
              @click="source.route && router.push(source.route)"
            >
              <div class="source-card-head">
                <h3>{{ source.label }}</h3>
                <span class="status-chip" :class="{ ready: source.ready }">
                  {{ source.ready ? 'Ready' : 'Needs work' }}
                </span>
              </div>
              <p class="section-copy">{{ source.description }}</p>
            </button>
          </div>
        </article>

        <article class="panel panel-full">
          <div class="panel-header">
            <h2>Contract Sections</h2>
            <div class="export-actions">
              <button class="btn btn-secondary" :disabled="!definitionContract" @click="exportDefinition">Export Service Definition</button>
              <button class="btn btn-secondary" :disabled="!definitionContract" @click="exportBlueprintPackage">Export Blueprint Package</button>
            </div>
          </div>
          <p class="panel-copy">
            Coverage Mapping should point to these contract sections and their exact formalization targets, not to vague Studio pages.
          </p>
          <div class="section-grid">
            <div v-for="section in sectionCards" :key="section.id" class="section-card">
              <div class="section-head">
                <h3>{{ section.label }}</h3>
                <span class="status-chip" :class="{ ready: section.coverage.summary.missing === 0 && section.coverage.summary.partial === 0 && section.coverage.summary.total > 0 }">
                  {{ section.coverage.summary.addressed }} / {{ section.coverage.summary.total || 0 }} addressed
                </span>
              </div>
              <p class="section-copy">{{ section.description }}</p>
              <p class="section-owners">
                <strong>Owned in:</strong> {{ section.owners.join(', ') }}
              </p>
              <div
                v-if="section.assistant_seeded?.count"
                class="assistant-seed-row"
              >
                <span class="assistant-seed-label">
                  Assistant-seeded fields: {{ section.assistant_seeded.count }}
                </span>
                <button
                  v-if="section.assistant_seeded.clearable"
                  class="assistant-seed-action"
                  type="button"
                  :disabled="readOnlyMode"
                  @click="clearAssistantSeededForSection(section.id)"
                >
                  Clear exact seeded fields
                </button>
              </div>
              <ul
                v-if="section.assistant_seeded?.details?.length"
                class="assistant-seed-detail-list"
              >
                <li
                  v-for="detail in section.assistant_seeded.details"
                  :key="`${section.id}-${detail.label}`"
                >
                  <button
                    class="assistant-seed-link"
                    type="button"
                    @click="openAssistantArtifacts(detail.artifact_type)"
                  >
                    {{ detail.label }}
                  </button>
                  <strong>{{ detail.count }}</strong>
                </li>
              </ul>
              <div class="section-metrics">
                <span>Partial: {{ section.coverage.summary.partial }}</span>
                <span>Missing: {{ section.coverage.summary.missing }}</span>
                <span>Deferred: {{ section.coverage.summary.deferred }}</span>
              </div>
            </div>
          </div>
        </article>

        <article class="panel definition-summary-panel">
          <div class="panel-header">
            <h2>Contract Identity</h2>
          </div>
          <div class="summary-stack">
            <div v-for="entry in contractIdentity" :key="entry.label" class="summary-row">
              <span class="summary-label">{{ entry.label }}</span>
              <strong class="identity-value">{{ entry.value }}</strong>
            </div>
          </div>
        </article>

        <article class="panel definition-summary-panel">
          <div class="panel-header">
            <h2>Agent Consumption Gate</h2>
            <span :class="['status-chip', `readiness-${simulationPublicationGate.status === 'pass' ? savedAgentReadinessReport.status : 'blocked'}`]">
              {{ simulationPublicationGate.status === 'pass' ? readinessStatusLabel(savedAgentReadinessReport.status) : simulationPublicationGate.label }}
            </span>
          </div>
          <p class="panel-copy">
            Generation and Registry publication use deterministic readiness plus the latest saved simulator report from Agent & App Glue. Blockers stop the flow; warnings and simulator risk require explicit acknowledgement.
          </p>
          <div class="summary-stack">
            <div class="summary-row">
              <span class="summary-label">Readiness Score</span>
              <strong>{{ savedAgentReadinessReport.score }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Blockers</span>
              <strong :class="['status-text', savedAgentReadinessReport.summary.blockers === 0 ? 'success' : 'warning']">
                {{ savedAgentReadinessReport.summary.blockers }}
              </strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Warnings</span>
              <strong :class="['status-text', savedAgentReadinessReport.summary.warnings === 0 ? 'success' : 'warning']">
                {{ savedAgentReadinessReport.summary.warnings }}
              </strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Required App Glue</span>
              <strong>{{ savedAgentReadinessReport.summary.required_app_glue }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Simulator Probes</span>
              <strong>{{ savedAgentReadinessReport.summary.probes }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Simulation Gate</span>
              <strong :class="['status-text', simulationPublicationGate.blocksPublication ? 'warning' : 'success']">
                {{ simulationPublicationGate.label }}
              </strong>
            </div>
            <div v-if="latestSimulationReport" class="summary-row">
              <span class="summary-label">Simulation Result</span>
              <strong>
                {{ latestSimulationReport.summary.passed }}/{{ latestSimulationReport.summary.total }} passed
              </strong>
            </div>
          </div>
          <p v-if="savedAgentReadinessReport.summary.warnings > 0 && savedAgentReadinessReport.summary.blockers === 0" class="panel-copy warning-copy">
            Readiness warnings must be resolved or classified in Agent & App Glue before this Developer Definition can be used for generation or publication.
          </p>
          <label v-if="simulationPublicationGate.requiresOverride && simulationPublicationGate.status !== 'pass'" class="readiness-acknowledgement">
            <input v-model="simulationGateOverrideAcknowledged" type="checkbox" :disabled="readOnlyMode" />
            <span>I reviewed the simulator publication risk and explicitly accept publishing with this simulator gate state.</span>
          </label>
          <p v-if="simulationPublicationGate.status !== 'pass'" class="panel-copy warning-copy">
            {{ simulationPublicationGate.detail }}
          </p>
          <p v-if="agentReadinessBlockedReason" class="panel-copy warning-copy">
            {{ agentReadinessBlockedReason }}
          </p>
          <button class="btn btn-secondary btn-full" type="button" @click="router.push(`/design/projects/${project?.id}/developer/app-glue`)">
            Open Agent & App Glue
          </button>
        </article>

        <article class="panel definition-summary-panel">
          <div class="panel-header">
            <h2>Transitional Generator Compatibility</h2>
          </div>
          <p class="panel-copy definition-status-copy">
            Transitional pattern pages still exist as compatibility and inspection surfaces, but generation no longer reads them as inputs. This page launches directly from the latest saved revision.
          </p>
          <div class="summary-stack">
            <div class="summary-row">
              <span class="summary-label">Data Access Pattern Route</span>
              <strong>Compatibility only</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Integration Pattern Route</span>
              <strong>Compatibility only</strong>
            </div>
          </div>
        </article>

        <article class="panel panel-full">
          <div class="panel-header">
            <h2>Registry Publication</h2>
            <div class="button-row">
              <button class="btn btn-secondary" :disabled="readOnlyMode || !canPublishLocalRegistry" @click="publishToLocalRegistry">
                {{ publishingLocalRegistry ? 'Publishing locally…' : 'Publish Locally' }}
              </button>
              <button
                class="btn btn-secondary"
                :disabled="readOnlyMode || (latestLocalPublicationBundle ? !canPromoteLatestLocalPublication : !canPublishRegistry)"
                @click="latestLocalPublicationBundle ? promoteLatestLocalPublicationToRegistry() : publishToRegistry()"
              >
                {{
                  latestLocalPublicationBundle
                    ? (promotingLocalPublication ? 'Promoting…' : 'Promote To Registry')
                    : (publishingRegistry ? 'Publishing…' : 'Publish To Registry')
                }}
              </button>
              <button class="btn btn-secondary" :disabled="readOnlyMode || !canRecordRelease" @click="recordReleaseForLatestRemotePublication">
                {{ recordingRelease ? 'Recording…' : 'Record Release' }}
              </button>
            </div>
          </div>
          <p class="panel-copy definition-status-copy">
            Publish the selected saved revision as an immutable package. Local publication stores the same package and receipt shape inside Studio; remote publication promotes it to the separate Registry service.
          </p>
          <div class="implementation-materials-panel">
            <div class="publication-history-header">
              <h3>Implementation Materials</h3>
              <button class="btn btn-secondary btn-compact" type="button" :disabled="readOnlyMode" @click="addImplementationMaterialDraft">
                Add Ref
              </button>
            </div>
            <p class="panel-copy subtle-copy">
              Optional custom code bundle refs are signed as package metadata. They are implementation aids only: they do not change the ANIP behavior contract, and the generator will not fetch remote bundles unless the user explicitly opts in.
            </p>
            <div v-if="implementationMaterialDrafts.length" class="implementation-material-list">
              <article
                v-for="(material, index) in implementationMaterialDrafts"
                :key="index"
                :class="['implementation-material-card', implementationMaterialRowError(material) ? 'field-error-card' : '']"
              >
                <label class="field">
                  <span class="summary-label">Title</span>
                  <input v-model="material.title" class="input" placeholder="Reviewed app glue" maxlength="120" :disabled="readOnlyMode" />
                </label>
                <label class="field field-wide">
                  <span class="summary-label">Immutable Bundle Ref</span>
                  <input
                    v-model="material.ref"
                    class="input"
                    placeholder="registry://team/bundle@1.2.3#sha256:..."
                    :disabled="readOnlyMode"
                  />
                </label>
                <label class="field field-wide">
                  <span class="summary-label">Expected Local Tree Digest</span>
                  <input
                    v-model="material.bundle_tree_sha256"
                    class="input"
                    placeholder="sha256:<64 hex chars>"
                    :disabled="readOnlyMode"
                  />
                </label>
                <button class="btn btn-secondary btn-compact" type="button" :disabled="readOnlyMode" @click="removeImplementationMaterialDraft(index)">
                  Remove
                </button>
                <p v-if="implementationMaterialRowError(material)" class="inline-field-error field-wide">
                  {{ implementationMaterialRowError(material) }}
                </p>
              </article>
            </div>
            <p v-else class="panel-copy subtle-copy">
              No implementation material refs will be attached.
            </p>
            <div v-if="latestImplementationMaterials.length" class="implementation-material-published">
              <strong>Latest package metadata</strong>
              <span v-for="(material, index) in latestImplementationMaterials" :key="`${material.ref}-${index}`">
                {{ material.title || `Implementation material ${index + 1}` }} · {{ material.ref }}
              </span>
            </div>
          </div>
          <p v-if="registryPublishError" class="error">{{ registryPublishError }}</p>
          <p v-else-if="localRegistryPublishResult" class="panel-copy subtle-copy">
            Created local package {{ localRegistryPublishResult.package.package_id }}@{{ localRegistryPublishResult.package.package_version }} with a Studio-local receipt.
          </p>
          <p v-else-if="registryPublishResult" class="panel-copy subtle-copy">
            Published {{ registryPublishResult.package.package_id }}@{{ registryPublishResult.package.package_version }} and recorded the receipt in Studio.
          </p>
          <p v-if="releaseError" class="error">{{ releaseError }}</p>
          <div class="summary-stack">
            <div class="summary-row">
              <span class="summary-label">Registry Publish Status</span>
              <strong :class="['status-text', registryReadiness.ready ? 'success' : 'warning']">{{ registryReadiness.label }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">PM Approval</span>
              <strong :class="['status-text', approvalLineage.status === 'current' ? 'success' : 'warning']">{{ approvalLineage.label }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Approval Detail</span>
              <strong>{{ approvalLineage.detail }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Current Selected Lineage</span>
              <strong>
                {{ latestSavedRevision
                  ? `${resolveProductRevisionRef() || `baseline:${baseline?.locked_at}` } -> ${latestSavedRevision.revision_artifact_id || `revision:${latestSavedRevision.revision_number}`}`
                  : 'No saved revision selected' }}
              </strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Readiness Detail</span>
              <strong>{{ registryReadiness.detail }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Release Status</span>
              <strong>{{ releaseBlockedReason || 'Latest remote publication can be recorded as released.' }}</strong>
            </div>
          </div>
          <div v-if="registryPublicationRows.length" class="summary-stack publication-summary">
            <div v-for="row in registryPublicationRows" :key="row.label" class="summary-row">
              <span class="summary-label">{{ row.label }}</span>
              <strong>{{ row.value }}</strong>
            </div>
          </div>
          <a
            v-if="latestLocalPublicationBundle"
            class="btn btn-secondary bundle-download-link"
            :href="latestLocalPublicationBundle.url"
            :download="latestLocalPublicationBundle.filename"
          >
            Download .anip-package.json
          </a>
          <button
            v-if="latestLocalPublicationBundle"
            class="btn btn-secondary"
            :disabled="readOnlyMode || localPublicationVerificationRunning"
            @click="verifyLatestLocalPublication"
          >
            {{ localPublicationVerificationRunning ? 'Verifying…' : 'Verify Local Publication' }}
          </button>
          <p v-if="localPublicationVerificationError" class="error">{{ localPublicationVerificationError }}</p>
          <div v-if="localPublicationVerificationSummary" class="summary-stack publication-summary">
            <div class="summary-row">
              <span class="summary-label">Local Verification</span>
              <strong :class="['status-text', localPublicationVerificationSummary.status === 'ok' ? 'success' : 'warning']">
                {{ localPublicationVerificationSummary.status === 'ok' ? 'Passed' : 'Failed' }}
              </strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Verification Checks</span>
              <strong>{{ localPublicationVerificationSummary.passedCount }} passed / {{ localPublicationVerificationSummary.failedCount }} failed</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Receipt Status</span>
              <strong>{{ formatReceiptStatus(localPublicationVerificationSummary.receiptStatus) }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Verified Lineage</span>
              <strong>{{ localPublicationVerificationSummary.productRevisionLabel }} -> {{ localPublicationVerificationSummary.developerRevisionLabel }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Receipt Signature</span>
              <strong>{{ localPublicationVerificationSummary.receiptSignature }}</strong>
            </div>
          </div>
          <div v-if="registryPublicationHistoryRows.length" class="publication-history">
            <div class="publication-history-header">
              <h3>Publication History</h3>
              <span>{{ registryPublicationHistoryRows.length }} immutable record{{ registryPublicationHistoryRows.length === 1 ? '' : 's' }}</span>
            </div>
            <div class="publication-history-list">
              <article v-for="row in registryPublicationHistoryRows" :key="row.artifactId" class="publication-history-card">
                <div class="publication-history-main">
                  <strong>{{ row.packageLabel }}</strong>
                  <span :class="['authority-pill', row.authorityClass]">{{ row.authorityLabel }}</span>
                  <span class="authority-pill neutral">{{ row.stateLabel }}</span>
                </div>
                <div class="publication-history-meta">
                  <span v-for="item in row.metaItems" :key="`${row.artifactId}:meta:${item.label}`" class="publication-kv">
                    <span class="publication-kv-label">{{ item.label }}</span>
                    <strong>{{ item.value }}</strong>
                  </span>
                </div>
                <div class="publication-history-digests">
                  <span v-for="item in row.digestItems" :key="`${row.artifactId}:digest:${item.label}`" class="publication-kv publication-kv-digest">
                    <span class="publication-kv-label">{{ item.label }}</span>
                    <strong>{{ item.value }}</strong>
                  </span>
                </div>
              </article>
            </div>
          </div>
          <div v-if="releaseRows.length" class="publication-history">
            <div class="publication-history-header">
              <h3>Release History</h3>
              <span>{{ releaseRows.length }} release record{{ releaseRows.length === 1 ? '' : 's' }}</span>
            </div>
            <div class="publication-history-list">
              <article v-for="row in releaseRows" :key="row.artifactId" class="publication-history-card">
                <div class="publication-history-main">
                  <strong>{{ row.packageLabel }}</strong>
                  <span class="authority-pill neutral">released</span>
                  <span class="authority-pill remote">{{ row.authority }}</span>
                </div>
                <div class="publication-history-meta">
                  <span>{{ row.releasedAt }}</span>
                  <span>Approval: {{ row.approvalArtifactId }}</span>
                  <span>Release: {{ row.releaseId }}</span>
                </div>
                <div class="publication-history-digests">
                  <span>Receipt: {{ row.receiptSignature }}</span>
                </div>
              </article>
            </div>
          </div>
        </article>

        <article class="panel panel-full">
          <div class="panel-header">
            <h2>Generation Handoff</h2>
            <button class="btn btn-secondary" :disabled="readOnlyMode || !canLaunchGeneration" @click="generateFromDefinition">
              {{ generationLoading ? 'Creating handoff…' : 'Create Generator Handoff' }}
            </button>
          </div>
          <p class="panel-copy generation-launch-copy">
            Studio records a deterministic handoff from the latest saved revision. Code generation and verification are now external CLI responsibilities using a Registry package or package bundle.
          </p>
          <div class="generation-mode-grid">
            <div class="generation-mode-card selected">
              <div class="generation-mode-head">
                <strong>External generator</strong>
                <span class="status-chip ready">Required</span>
              </div>
              <p class="section-copy">
                Publish the saved Developer Definition to Registry, then run the generator/verifier outside Studio. Studio no longer emits runnable TypeScript service projects.
              </p>
            </div>
          </div>
          <p v-if="generationBlockedReason && !generationError" class="panel-copy generation-blocked-note">
            {{ generationBlockedReason }}
          </p>
          <p v-if="generationError" class="error">{{ generationError }}</p>
          <div class="source-card-grid">
            <div
              v-for="item in generationReadiness"
              :key="item.id"
              class="source-card"
            >
              <div class="source-card-head">
                <h3>{{ item.label }}</h3>
                <span class="status-chip" :class="{ ready: item.ready }">
                  {{ item.ready ? 'Ready' : (designIssueBlockedReason ? 'Blocked' : 'Missing saved revision') }}
                </span>
              </div>
              <p class="section-copy">{{ item.detail }}</p>
            </div>
          </div>
          <div v-if="latestGenerationRun" class="summary-stack generation-run-summary">
            <div v-for="entry in latestGenerationRunRows" :key="entry.label" class="summary-row">
              <span class="summary-label">{{ entry.label }}</span>
              <strong class="identity-value">{{ entry.value }}</strong>
            </div>
          </div>
          <div v-if="latestGenerationRunArtifact" class="generation-proof-actions">
            <p class="section-copy">
              Studio local runtime proof has been retired. Verify the published package with the external verifier against Registry or a portable package bundle.
            </p>
          </div>
          <div v-if="latestGeneratedStructure" class="generation-output-grid">
            <div class="section-card">
              <div class="section-head">
                <h3>Generated Structure</h3>
              </div>
              <div class="summary-stack compact-stack">
                <div class="summary-row">
                  <span class="summary-label">Target Services</span>
                  <strong>{{ latestGeneratedStructure.service_ids.length }}</strong>
                </div>
                <div class="summary-row">
                  <span class="summary-label">Capabilities</span>
                  <strong>{{ latestGeneratedStructure.capability_ownership.length }}</strong>
                </div>
                <div class="summary-row">
                  <span class="summary-label">Scenarios</span>
                  <strong>{{ latestGeneratedStructure.scenario_ids.length }}</strong>
                </div>
                <div class="summary-row">
                  <span class="summary-label">Protocols</span>
                  <strong>{{ latestGeneratedStructure.protocols.join(', ') || 'None' }}</strong>
                </div>
              </div>
              <div class="generated-structure-list">
                <div v-for="service in latestGeneratedStructure.services" :key="service.service_id" class="generated-structure-card">
                  <strong>{{ service.service_name }}</strong>
                  <code>{{ service.service_id }}</code>
                  <span>{{ service.owned_capability_ids.length }} capability{{ service.owned_capability_ids.length === 1 ? '' : 'ies' }}</span>
                  <span>{{ service.participating_scenario_ids.length }} scenario{{ service.participating_scenario_ids.length === 1 ? '' : 's' }}</span>
                </div>
              </div>
            </div>
            <div v-if="latestRuntimeTarget" class="section-card">
              <div class="section-head">
                <h3>Runtime Target</h3>
              </div>
              <div class="summary-stack compact-stack">
                <div class="summary-row">
                  <span class="summary-label">Estate Mode</span>
                  <strong>{{ developerLabel(latestRuntimeTarget.service_generation_mode) }}</strong>
                </div>
                <div class="summary-row">
                  <span class="summary-label">Required Behaviors</span>
                  <strong>{{ latestRuntimeTarget.required_behavior_tokens.length }}</strong>
                </div>
                <div class="summary-row">
                  <span class="summary-label">ANIP Support Tokens</span>
                  <strong>{{ latestRuntimeTarget.required_anip_support_tokens.length }}</strong>
                </div>
              </div>
              <pre class="json-preview compact-json">{{ JSON.stringify(latestRuntimeTarget, null, 2) }}</pre>
            </div>
            <div class="section-card">
              <div class="section-head">
                <h3>Extension Manifest</h3>
              </div>
              <div class="generated-structure-list">
                <div v-for="entry in latestExtensionManifest" :key="entry.id" class="generated-structure-card">
                  <strong>{{ entry.label }}</strong>
                  <span class="extension-ownership">{{ developerLabel(entry.ownership) }}</span>
                  <code>{{ entry.plugin_surface }}</code>
                  <p class="section-copy">{{ entry.rationale }}</p>
                </div>
              </div>
            </div>
          </div>
          <div v-if="latestGenerationRun?.outputs.runtime_target?.length" class="generation-output-grid">
            <div v-if="latestGenerationRun?.outputs.runtime_target?.length" class="section-card">
              <div class="section-head">
                <h3>Runtime Target Outputs</h3>
              </div>
              <div class="generation-output-list">
                <button
                  v-for="output in latestGenerationRun.outputs.runtime_target"
                  :key="output.filename"
                  class="download-button"
                  type="button"
                  @click="downloadSavedGeneratedOutput(output)"
                >
                  Download {{ output.title }}
                </button>
              </div>
            </div>
          </div>
        </article>

        <article class="panel panel-full">
          <div class="panel-header">
            <h2>Exported Contract Preview</h2>
          </div>
          <pre v-if="definitionJson" class="json-preview">{{ definitionJson }}</pre>
          <p v-else class="panel-copy">The contract preview becomes available once the locked baseline is valid.</p>
        </article>
      </section>
    </template>
  </div>
</template>

<style scoped src="./developer-definition-shared.css"></style>
<style scoped>
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

.developer-definition button:disabled,
.developer-definition input:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.source-card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 0.85rem;
}

.definition-summary-panel .summary-stack {
  gap: 0.85rem;
}

.definition-summary-panel .summary-row {
  gap: 0.2rem;
}

.definition-summary-panel .summary-row .summary-label {
  margin: 0;
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 700;
}

.definition-summary-panel .summary-row strong {
  color: var(--text-primary);
  font-size: 15px;
  line-height: 1.35;
}

.definition-summary-panel .summary-row .status-text.ready {
  color: #6ee7b7;
}

.definition-summary-panel .summary-row .status-text.warning {
  color: #fbbf24;
}

.panel-full > .summary-stack .summary-row,
.panel-full > .publication-summary .summary-row {
  display: grid;
  grid-template-columns: minmax(180px, 0.32fr) minmax(0, 1fr);
  gap: 0.75rem;
  align-items: start;
  padding: 0.7rem 0;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
}

.panel-full > .summary-stack .summary-row:last-child,
.panel-full > .publication-summary .summary-row:last-child {
  border-bottom: 0;
}

.panel-full > .summary-stack .summary-label,
.panel-full > .publication-summary .summary-label {
  margin-top: 0.1rem;
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 850;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.panel-full > .summary-stack .summary-row strong,
.panel-full > .publication-summary .summary-row strong {
  min-width: 0;
  color: var(--text-primary);
  font-size: 15px;
  font-weight: 750;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.panel-full > .summary-stack .summary-row strong:not(.status-text),
.panel-full > .publication-summary .summary-row strong:not(.status-text) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
  font-size: 13px;
}

.status-chip.readiness-ready {
  background: rgba(16, 185, 129, 0.16);
  color: #86efac;
}

.status-chip.readiness-needs_review {
  background: rgba(245, 158, 11, 0.16);
  color: #fcd34d;
}

.status-chip.readiness-blocked {
  background: rgba(239, 68, 68, 0.16);
  color: #fca5a5;
}

.readiness-acknowledgement {
  display: flex;
  gap: 0.65rem;
  align-items: flex-start;
  margin: 1rem 0;
  border: 1px solid rgba(245, 158, 11, 0.24);
  border-radius: 14px;
  padding: 0.85rem;
  background: rgba(120, 53, 15, 0.16);
  color: var(--text-primary);
  line-height: 1.45;
}

.readiness-acknowledgement input {
  margin-top: 0.2rem;
}

.warning-copy {
  color: #fcd34d;
}

.definition-status-copy {
  margin-bottom: 1.15rem;
}

.publication-history {
  margin-top: 1rem;
}

.implementation-materials-panel {
  display: grid;
  gap: 0.75rem;
  margin: 1rem 0;
  border: 1px solid var(--surface-border-card);
  border-radius: 16px;
  background:
    linear-gradient(135deg, rgba(14, 165, 233, 0.08), rgba(15, 23, 42, 0.22)),
    var(--surface-depth-card);
  padding: 0.95rem;
}

.implementation-material-list {
  display: grid;
  gap: 0.75rem;
}

.implementation-material-card {
  display: grid;
  grid-template-columns: minmax(160px, 0.8fr) minmax(0, 1fr) auto;
  gap: 0.75rem;
  align-items: end;
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  background: rgba(15, 23, 42, 0.32);
  padding: 0.85rem;
}

.implementation-material-card .field-wide {
  grid-column: span 2;
}

.implementation-material-published {
  display: grid;
  gap: 0.35rem;
  border-top: 1px solid var(--surface-border-card);
  padding-top: 0.75rem;
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1.45;
}

.implementation-material-published strong {
  color: var(--text-primary);
}

.publication-history-header,
.publication-history-main,
.publication-history-meta,
.publication-history-digests {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
}

.publication-history-header {
  justify-content: space-between;
  margin-bottom: 0.65rem;
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 700;
}

.publication-history-header h3 {
  margin: 0;
  color: var(--text-primary);
  font-size: 15px;
}

.publication-history-list {
  display: grid;
  gap: 0.65rem;
}

.publication-history-card {
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  background: var(--surface-depth-card);
  padding: 0.85rem;
}

.publication-history-main {
  justify-content: space-between;
}

.publication-history-main strong {
  margin-right: auto;
}

.publication-history-meta,
.publication-history-digests {
  margin-top: 0.5rem;
  color: var(--text-muted);
  font-size: 12px;
}

.publication-kv {
  display: inline-flex;
  max-width: 100%;
  min-width: 0;
  align-items: baseline;
  gap: 0.35rem;
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.28);
  padding: 0.2rem 0.45rem;
  line-height: 1.35;
}

.publication-kv-label {
  flex: 0 0 auto;
  color: var(--text-muted);
  font-weight: 700;
}

.publication-kv-label::after {
  content: ':';
}

.publication-kv strong {
  min-width: 0;
  color: var(--text-primary);
  font-weight: 650;
  overflow-wrap: anywhere;
}

.publication-kv-digest {
  border-radius: 10px;
}

.publication-history-digests .publication-kv {
  max-width: 100%;
  overflow-wrap: anywhere;
}

@media (max-width: 920px) {
  .implementation-material-card {
    grid-template-columns: 1fr;
  }

  .implementation-material-card .field-wide {
    grid-column: auto;
  }
}

.authority-pill {
  border: 1px solid var(--surface-border-card);
  border-radius: 999px;
  padding: 0.18rem 0.55rem;
  color: rgba(248, 250, 252, 0.86);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}

.authority-pill.local {
  border-color: rgba(251, 191, 36, 0.38);
  background: rgba(251, 191, 36, 0.1);
  color: #fde68a;
}

.authority-pill.remote {
  border-color: rgba(110, 231, 183, 0.38);
  background: rgba(16, 185, 129, 0.1);
  color: #6ee7b7;
}

.authority-pill.neutral {
  border-color: rgba(148, 163, 184, 0.24);
  background: rgba(148, 163, 184, 0.08);
}

.generation-launch-copy {
  margin-bottom: 1.2rem;
}

.contract-source-readiness-panel {
  background:
    radial-gradient(circle at top left, rgba(59, 130, 246, 0.12), transparent 34%),
    rgba(15, 23, 42, 0.46);
}

.contract-source-readiness-panel .source-card-grid {
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
}

.source-card {
  width: 100%;
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  background: var(--surface-depth-card);
  padding: 1rem;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.source-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
}

.source-card-head h3 {
  margin: 0;
  font-size: 16px;
}

.identity-value {
  word-break: break-word;
}

.compact-json {
  flex: 1 1 32rem;
  min-height: 32rem;
  max-height: 48rem;
  overflow: auto;
}

.status-text.ready {
  color: #6ee7b7;
}

.status-text.warning {
  color: #fbbf24;
}

.generation-blocked-note {
  color: rgba(248, 250, 252, 0.84);
}

.generation-mode-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 0.85rem;
  margin-bottom: 1rem;
}

.generation-mode-card {
  width: 100%;
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  background: var(--surface-depth-card);
  padding: 1rem;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.generation-mode-card.selected {
  border-color: rgba(96, 165, 250, 0.42);
  background:
    radial-gradient(circle at top right, rgba(96, 165, 250, 0.16), transparent 38%),
    rgba(15, 23, 42, 0.34);
}

.generation-mode-card:disabled {
  cursor: default;
  opacity: 0.72;
}

.generation-mode-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.55rem;
}

.generation-output-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  align-items: stretch;
  gap: 0.85rem;
  margin-top: 1rem;
}

.generation-output-grid .section-card {
  display: flex;
  flex-direction: column;
  min-height: 100%;
}

.generation-proof-actions {
  display: grid;
  gap: 0.65rem;
  margin-top: 1rem;
}

.page-role-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.85rem;
}

.page-role-chip {
  display: inline-flex;
  align-items: center;
  padding: 3px 9px;
  border-radius: 999px;
  border: 1px solid transparent;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.page-role-chip.tone-compile {
  background: rgba(96, 165, 250, 0.12);
  border-color: rgba(96, 165, 250, 0.28);
  color: #bfdbfe;
}

.page-role-chip.tone-review {
  background: rgba(148, 163, 184, 0.12);
  border-color: rgba(148, 163, 184, 0.22);
  color: rgba(226, 232, 240, 0.82);
}

.page-role-chip.tone-evidence {
  background: rgba(251, 191, 36, 0.12);
  border-color: rgba(251, 191, 36, 0.28);
  color: #fde68a;
}

.subtle-copy {
  color: rgba(226, 232, 240, 0.72);
}

.generation-output-list {
  display: grid;
  gap: 0.6rem;
}

.compact-stack {
  margin-bottom: 1rem;
}

.compact-stack .summary-row {
  display: grid;
  grid-template-columns: minmax(150px, 0.42fr) minmax(0, 1fr);
  gap: 0.65rem;
  align-items: baseline;
  padding: 0.45rem 0;
  border-bottom: 1px solid rgba(148, 163, 184, 0.1);
}

.compact-stack .summary-row:last-child {
  border-bottom: 0;
}

.compact-stack .summary-label {
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 850;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.compact-stack .summary-row strong {
  min-width: 0;
  color: var(--text-primary);
  font-size: 15px;
  font-weight: 800;
  overflow-wrap: anywhere;
}

.generated-structure-list {
  display: grid;
  gap: 0.7rem;
}

.generated-structure-card {
  display: grid;
  gap: 0.3rem;
  padding: 0.85rem 0.95rem;
  border-radius: 12px;
  border: 1px solid var(--surface-border-card);
  background: var(--surface-depth-card);
}

.generated-structure-card code {
  width: fit-content;
}

.extension-ownership {
  text-transform: capitalize;
  color: #bfdbfe;
  font-size: 12px;
  font-weight: 600;
}

.download-button {
  border: 1px solid var(--surface-border-card);
  border-radius: 10px;
  background: var(--surface-depth-card);
  color: inherit;
  padding: 0.7rem 0.85rem;
  text-align: left;
  cursor: pointer;
}

.export-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.button-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.developer-definition .btn-secondary {
  border: 1px solid rgba(148, 163, 184, 0.24);
  background:
    linear-gradient(135deg, rgba(30, 41, 59, 0.72), rgba(15, 23, 42, 0.62));
  color: rgba(226, 232, 240, 0.96);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.developer-definition .btn-secondary:hover:not(:disabled) {
  border-color: rgba(147, 197, 253, 0.42);
  background:
    linear-gradient(135deg, rgba(30, 64, 175, 0.28), rgba(15, 23, 42, 0.76));
}

.developer-definition .source-card {
  border-color: rgba(148, 163, 184, 0.22);
  background:
    linear-gradient(135deg, rgba(30, 41, 59, 0.56), rgba(15, 23, 42, 0.64));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.035);
}

.developer-definition .source-card:hover {
  border-color: rgba(147, 197, 253, 0.34);
  background:
    linear-gradient(135deg, rgba(30, 64, 175, 0.22), rgba(15, 23, 42, 0.74));
}

.assistant-seed-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-top: 0.6rem;
}

.assistant-seed-label {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  color: rgba(226, 232, 240, 0.72);
  font-size: 0.84rem;
  font-weight: 600;
}

.assistant-seed-action,
.assistant-seed-link,
.assistant-seed-row .inline-link,
.assistant-seed-detail-list .inline-link {
  border: 0;
  background: transparent;
  color: #93c5fd;
  cursor: pointer;
  font: inherit;
  font-size: 0.82rem;
  font-weight: 750;
}

.assistant-seed-action,
.assistant-seed-row .inline-link {
  flex: 0 0 auto;
  padding: 0.25rem 0;
  text-align: right;
}

.assistant-seed-action:hover,
.assistant-seed-link:hover,
.assistant-seed-row .inline-link:hover,
.assistant-seed-detail-list .inline-link:hover {
  color: #bfdbfe;
  text-decoration: underline;
  text-underline-offset: 3px;
}

.assistant-seed-action:disabled,
.assistant-seed-row .inline-link:disabled {
  cursor: not-allowed;
  opacity: 0.45;
  text-decoration: none;
}

.assistant-seed-detail-list {
  list-style: none;
  padding: 0;
  margin: 0.5rem 0 0;
  display: grid;
  gap: 0.35rem;
}

.assistant-seed-detail-list li {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
  color: rgba(226, 232, 240, 0.78);
  font-size: 0.82rem;
}

.assistant-seed-link,
.assistant-seed-detail-list .inline-link {
  padding: 0;
  text-align: left;
}

.error-copy {
  color: #fca5a5;
}
</style>
