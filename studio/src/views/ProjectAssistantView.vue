<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AssistantDraftSectionCard from '../design/components/AssistantDraftSectionCard.vue'
import AssistantWorkingOverlay from '../design/components/AssistantWorkingOverlay.vue'
import {
  createPmArtifact,
  getProjectDocumentPreview,
  updatePmArtifact,
} from '../design/project-api'
import {
  assistantRuntimeContext,
  bundleFromArtifact,
  deleteAssistantDraftBundle,
  findLatestAssistantDraftBundleArtifact,
  persistAssistantDraftBundle,
} from '../design/assistant-draft-bundles'
import {
  appendAssistantAuditEvent,
  type AssistantAuditEvent,
} from '../design/assistant-audit-log'
import {
  buildDeveloperBaselineSourceText,
  clearDeveloperSectionSelection,
  developerBundleOpenQuestions,
  developerSectionItemCount,
  draftDeveloperDesignBundle,
  redraftDeveloperDesignSection,
  saveAcceptedDeveloperDesignSection,
  selectAllDeveloperSectionItems,
  selectedDeveloperSectionItemCount,
  toggleDeveloperSectionSelection,
  type DeveloperDesignDraftBundle,
  type DeveloperDesignDraftSection,
} from '../design/developer-design-draft-bundle'
import {
  bundleOpenQuestions,
  clearSectionSelection,
  draftProductDesignBundle,
  productArtifactTypeForDraftSection,
  redraftProductDesignSection,
  saveAcceptedProductDesignSection,
  sectionItemCount,
  selectAllSectionItems,
  selectedSectionItemCount,
  toggleSectionSelection,
  type AssistantClarificationAnswerContext,
  type ProductDesignDraftBundle,
  type ProductDesignDraftSection,
} from '../design/product-design-draft-bundle'
import { findProductDesignArtifact } from '../design/product-design'
import { buildProjectIssueIndex } from '../design/project-issues'
import { loadProject, projectStore, refreshArtifacts } from '../design/project-store'
import {
  findDeveloperDefinitionArtifact,
} from '../design/developer-definition'
import {
  expectedCapabilityIdsFromShape,
  inputContractReviewedEvidenceCoverage,
} from '../design/input-contract-evidence'
import {
  hasFrontingIntegrationSource,
  hasFrontingIntentSource,
  isFrontingIntegrationSource,
  isDeveloperSourceDocument,
  isGovernedFrontingProject,
  isProductSourceDocument,
  sourceDocumentKindLabel,
} from '../design/source-documents'
import type {
  AssistantClarificationQuestion,
  AssistantServiceGranularity,
  AssistantServiceTopologyPreference,
  DeveloperBaselineData,
  DeveloperDefinitionData,
  HighRiskConfirmationReport,
  ShapeRecord,
  TraceabilityCoverageItem,
  TraceabilityRecordData,
} from '../design/project-types'
import { formatStudioTimestamp } from '../design/time'
import { findDeveloperBaselineArtifact, findTraceabilityArtifact, summarizeCoverage } from '../design/traceability'
import {
  buildStudioOperatorHandoffSummary,
  buildStudioOperatorDecisionQueue,
  buildStudioOperatorTasks,
  coordinationResolutionChoices,
  createStudioOperatorActivity,
  findStudioOperatorActivityLogArtifact,
  findStudioOperatorHandoffSummaryArtifact,
  nextStudioOperatorTask,
  persistStudioOperatorActivity,
  persistStudioOperatorHandoffSummary,
  studioOperatorActivityLogFromArtifact,
  studioOperatorHandoffSummaryFromArtifact,
  type StudioOperatorTask,
  type StudioOperatorDecisionQueueAction,
  type StudioOperatorDecisionQueueItem,
} from '../design/studio-operator'
import {
  buildHighRiskConfirmationReport,
  findHighRiskConfirmationArtifact,
  HIGH_RISK_CONFIRMATIONS_ARTIFACT_TYPE,
  highRiskConfirmationReportFromArtifacts,
  unresolvedHighRiskConfirmationItems,
} from '../design/high-risk-confirmations'
import type { AgentConsumptionReadinessReport } from '../design/agent-consumption-readiness'
import type { AgentConsumabilityCapabilityReview } from '../design/agent-consumability'
import {
  mergeSelectionHint,
  mergeSemanticInterpretationRule,
  selectionHintForSemanticRule,
  semanticInterpretationRuleForFinding,
} from '../design/semantic-interpretation-rules'
import { projectPath, projectPathFromParts } from '../design/project-routes'

type AssistantLane = 'pm' | 'dev'
type AssistantWorkMode = 'manual' | 'guided' | 'autopilot'

const route = useRoute()
const router = useRouter()

const projectId = computed(() => route.params.projectId as string)
const project = computed(() => projectStore.activeProject)
const projectRoute = (suffix = '') => project.value
  ? projectPath(project.value, suffix)
  : projectPathFromParts(projectId.value, null, suffix)
const documents = computed(() => projectStore.artifacts.documents)
const governedFrontingProject = computed(() => isGovernedFrontingProject(project.value))
const assistantDocuments = computed(() =>
  lane.value === 'dev'
    ? documents.value.filter(isDeveloperSourceDocument)
    : documents.value.filter((document) =>
        isProductSourceDocument(document)
        || (governedFrontingProject.value && isFrontingIntegrationSource(document)),
      ),
)
const pmArtifacts = computed(() => projectStore.artifacts.pmArtifacts)
const requirements = computed(() => projectStore.artifacts.requirements)
const scenarios = computed(() => projectStore.artifacts.scenarios)
const shapes = computed(() => projectStore.artifacts.shapes)
const loading = computed(() => projectStore.loading)
const error = computed(() => projectStore.error)
const runtimeStatus = computed(() => projectStore.runtimeStatus)
const readOnlyMode = computed(() => projectStore.runtimeStatus?.read_only_mode !== false)
const readOnlyReason = computed(() =>
  projectStore.runtimeStatus?.read_only_reason
  || 'Studio is running in read-only mode. Explore the design, then download and run Studio locally to make changes.',
)
const frontingIntentReady = computed(() => hasFrontingIntentSource(documents.value))
const frontingIntegrationReady = computed(() => hasFrontingIntegrationSource(documents.value))
const assistantCanDraft = computed(() =>
  !!runtimeStatus.value?.studio_api_reachable
  && !!runtimeStatus.value?.llm_ready
  && !readOnlyMode.value,
)
const canRunDeterministicDraft = computed(() =>
  !!runtimeStatus.value?.studio_api_reachable
  && !readOnlyMode.value,
)
const assistantStatus = computed(() => {
  const runtime = runtimeStatus.value
  if (!runtime) {
    return {
      label: 'Unknown',
      ready: false,
      detail: 'Studio has not loaded assistant runtime status yet.',
    }
  }
  if (readOnlyMode.value) {
    return {
      label: 'Read-only',
      ready: false,
      detail: readOnlyReason.value,
    }
  }
  if (!runtime.studio_api_reachable) {
    return {
      label: 'Studio API unavailable',
      ready: false,
      detail: 'The assistant cannot draft until Studio API is reachable.',
    }
  }
  if (runtime.llm_ready) {
    return {
      label: 'Ready',
      ready: true,
      detail: 'AI drafting is available. Studio will still save only reviewed deterministic artifacts.',
    }
  }
  if (!runtime.llm_enabled) {
    return {
      label: 'AI not enabled',
      ready: false,
      detail: 'Configure an assistant provider and API key before using AI drafting.',
    }
  }
  if (!runtime.api_key_configured) {
    return {
      label: 'LLM key missing',
      ready: false,
      detail: 'Configure an API key in Studio or through the startup environment.',
    }
  }
  if (!runtime.assistant_model) {
    return {
      label: 'Model not set',
      ready: false,
      detail: 'Set a model or use the provider default where supported.',
    }
  }
  return {
    label: 'Needs attention',
    ready: false,
    detail: 'Assistant runtime configuration is incomplete.',
  }
})
const assistantReadinessItems = computed(() => [
  {
    label: 'Studio API',
    value: runtimeStatus.value?.studio_api_reachable ? 'reachable' : 'unavailable',
    ready: !!runtimeStatus.value?.studio_api_reachable,
  },
  {
    label: 'Provider',
    value: runtimeStatus.value?.assistant_provider || 'not set',
    ready: !!runtimeStatus.value?.assistant_provider,
  },
  {
    label: 'Model',
    value: runtimeStatus.value?.assistant_model || 'provider default / not set',
    ready: !!runtimeStatus.value?.assistant_model || !!runtimeStatus.value?.llm_ready,
  },
  {
    label: 'LLM key',
    value: runtimeStatus.value?.api_key_configured ? `configured (${runtimeStatus.value.api_key_source})` : 'missing',
    ready: !!runtimeStatus.value?.api_key_configured,
  },
  {
    label: 'Base URL',
    value: runtimeStatus.value?.assistant_base_url || 'provider default',
    ready: true,
  },
])

const requestedWorkMode = computed<AssistantWorkMode>(() => {
  const mode = typeof route.query.mode === 'string' ? route.query.mode.toLowerCase() : ''
  if (mode === 'autopilot' || mode === 'operator') return 'autopilot'
  if (mode === 'guided') return 'guided'
  if (mode === 'manual') return 'manual'
  return 'autopilot'
})
const workMode = computed<AssistantWorkMode>(() =>
  assistantCanDraft.value ? requestedWorkMode.value : 'manual',
)
const workModeNotice = computed(() =>
  assistantCanDraft.value
    ? 'Autopilot and Guided modes are available. Studio still saves only reviewed deterministic artifacts.'
    : 'Manual mode is active because the assistant is not configured or Studio is read-only.',
)

const lane = computed<AssistantLane>(() => {
  if (route.meta.assistantLane === 'dev') return 'dev'
  if (route.meta.assistantLane === 'pm') return 'pm'
  const queryLane = typeof route.query.lane === 'string' ? route.query.lane.toLowerCase() : ''
  return queryLane === 'dev' || queryLane === 'developer' ? 'dev' : 'pm'
})
const sourceSelectionMode = ref<'all' | 'selected'>('all')
const selectedDocumentIds = ref<string[]>([])
const previewContent = ref('')
const previewError = ref<string | null>(null)
const previewLoading = ref(false)
const previewContentKey = ref('')
const draftBundle = ref<ProductDesignDraftBundle | null>(null)
const draftLoading = ref(false)
const productDraftOperation = ref<'ai' | 'deterministic' | null>(null)
const draftError = ref<string | null>(null)
const assistantProgressItems = ref<string[]>([])
const assistantAbortController = ref<AbortController | null>(null)
const assistantCancelRequested = ref(false)
const savingSectionId = ref<string | null>(null)
const regeneratingSectionId = ref<string | null>(null)
const productBundleArtifactId = ref<string | null>(null)
const developerDraftBundle = ref<DeveloperDesignDraftBundle | null>(null)
const developerDraftLoading = ref(false)
const developerDraftOperation = ref<'ai' | 'deterministic' | null>(null)
const developerDraftError = ref<string | null>(null)
const savingDeveloperSectionId = ref<string | null>(null)
const regeneratingDeveloperSectionId = ref<string | null>(null)
const developerBundleArtifactId = ref<string | null>(null)
const discardingBundle = ref(false)
const productServiceGranularity = ref<AssistantServiceGranularity>('balanced')
const productTargetServiceCount = ref<number | null>(null)
const operatorSummarySaving = ref(false)
const operatorSummaryMessage = ref<string | null>(null)
const operatorSummaryError = ref<string | null>(null)
const operatorDecisionApplyingId = ref<string | null>(null)
const operatorDecisionMessage = ref<string | null>(null)
const operatorDecisionError = ref<string | null>(null)
const operatorActivityArtifact = computed(() =>
  findStudioOperatorActivityLogArtifact(projectStore.artifacts.pmArtifacts),
)
const operatorActivities = computed(() =>
  studioOperatorActivityLogFromArtifact(operatorActivityArtifact.value)?.events ?? [],
)
const operatorHandoffArtifact = computed(() =>
  findStudioOperatorHandoffSummaryArtifact(projectStore.artifacts.pmArtifacts),
)
const savedOperatorHandoffSummary = computed(() =>
  studioOperatorHandoffSummaryFromArtifact(operatorHandoffArtifact.value),
)

async function ensureLoaded() {
  if (!projectId.value) return
  if (projectStore.activeProject?.id === projectId.value) return
  await loadProject(projectId.value)
}

onMounted(ensureLoaded)
watch(projectId, ensureLoaded)

function setLane(nextLane: AssistantLane) {
  router.replace({
    path: nextLane === 'dev'
      ? projectRoute('/developer/assistant')
      : projectRoute('/pm/assistant'),
    query: { ...route.query, lane: undefined, mode: workMode.value },
  })
}

function setWorkMode(nextMode: AssistantWorkMode) {
  router.replace({
    path: route.path,
    query: { ...route.query, mode: nextMode },
  })
}

const selectableDocumentIds = computed(() => assistantDocuments.value.map((item) => item.id))
const activeSourceDocumentIds = computed(() => {
  const available = new Set(selectableDocumentIds.value)
  if (sourceSelectionMode.value === 'all') return selectableDocumentIds.value
  return selectedDocumentIds.value.filter((id) => available.has(id))
})
const selectedSourceDocuments = computed(() => {
  const active = new Set(activeSourceDocumentIds.value)
  return assistantDocuments.value.filter((item) => active.has(item.id))
})
const activeSourcePreviewKey = computed(() => `${projectId.value || 'no-project'}:${activeSourceDocumentIds.value.join(',')}`)
const selectedDocument = computed(() => selectedSourceDocuments.value[0] ?? null)
const selectedSourceCount = computed(() => selectedSourceDocuments.value.length)
const sourceSelectionSummary = computed(() => {
  if (!assistantDocuments.value.length) return lane.value === 'dev' ? 'No developer source documents' : 'No source documents'
  if (sourceSelectionMode.value === 'all') {
    return `Using all ${assistantDocuments.value.length} ${lane.value === 'dev' ? 'developer ' : ''}source document${assistantDocuments.value.length === 1 ? '' : 's'}`
  }
  return `Using ${selectedSourceCount.value} of ${assistantDocuments.value.length} ${lane.value === 'dev' ? 'developer ' : ''}source document${assistantDocuments.value.length === 1 ? '' : 's'}`
})

watch(
  () => [assistantDocuments.value.map((item) => `${item.id}:${item.updated_at}`).join(','), route.query.sourceDoc] as const,
  async ([, querySourceDoc]) => {
    if (!assistantDocuments.value.length) {
      selectedDocumentIds.value = []
      previewContent.value = ''
      previewError.value = null
      return
    }
    if (lane.value === 'dev') {
      sourceSelectionMode.value = 'all'
      selectedDocumentIds.value = []
      clearSourceDocumentQuery()
      await loadPreview()
      return
    }
    const requestedId = typeof querySourceDoc === 'string' ? querySourceDoc : null
    if (requestedId && assistantDocuments.value.some((item) => item.id === requestedId)) {
      sourceSelectionMode.value = 'selected'
      selectedDocumentIds.value = [requestedId]
    } else {
      const available = new Set(selectableDocumentIds.value)
      selectedDocumentIds.value = selectedDocumentIds.value.filter((id) => available.has(id))
      if (sourceSelectionMode.value === 'selected' && selectedDocumentIds.value.length === 0) {
        selectedDocumentIds.value = selectableDocumentIds.value
      }
    }
    await loadPreview()
  },
  { immediate: true },
)

watch([sourceSelectionMode, () => selectedDocumentIds.value.join(',')], async () => {
  await loadPreview()
})

function useAllSourceDocuments() {
  sourceSelectionMode.value = 'all'
  clearSourceDocumentQuery()
}

function useSelectedSourceDocuments() {
  sourceSelectionMode.value = 'selected'
  if (!selectedDocumentIds.value.length) {
    selectedDocumentIds.value = selectableDocumentIds.value
  }
}

function selectAllSourceDocuments() {
  sourceSelectionMode.value = 'selected'
  selectedDocumentIds.value = selectableDocumentIds.value
  clearSourceDocumentQuery()
}

function clearSelectedSourceDocuments() {
  sourceSelectionMode.value = 'selected'
  selectedDocumentIds.value = []
  clearSourceDocumentQuery()
}

function clearSourceDocumentQuery() {
  if (route.query.sourceDoc === undefined) return
  router.replace({
    path: route.path,
    query: { ...route.query, sourceDoc: undefined },
  })
}

watch(
  () => [projectStore.artifacts.pmArtifacts.map((item) => `${item.id}:${item.updated_at}`).join(','), project.value?.id] as const,
  () => {
    if (!project.value) return
    if (!draftBundle.value) {
      const artifact = findLatestAssistantDraftBundleArtifact(projectStore.artifacts.pmArtifacts, 'pm')
      const bundle = bundleFromArtifact<ProductDesignDraftBundle>(artifact)
      if (artifact && bundle) {
        productBundleArtifactId.value = artifact.id
        draftBundle.value = bundle
      }
    }
    if (!developerDraftBundle.value) {
      const artifact = findLatestAssistantDraftBundleArtifact(projectStore.artifacts.pmArtifacts, 'dev')
      const bundle = bundleFromArtifact<DeveloperDesignDraftBundle>(artifact)
      if (artifact && bundle) {
        developerBundleArtifactId.value = artifact.id
        developerDraftBundle.value = bundle
      }
    }
  },
  { immediate: true },
)

async function loadPreview() {
  const previewKey = activeSourcePreviewKey.value
  previewContentKey.value = ''
  if (!projectId.value || activeSourceDocumentIds.value.length === 0) {
    previewContent.value = ''
    previewError.value = null
    return
  }
  previewLoading.value = true
  previewError.value = null
  previewContent.value = ''
  try {
    const previews = await Promise.all(
      selectedSourceDocuments.value.map(async (document) => {
        const preview = await getProjectDocumentPreview(projectId.value, document.id)
        return { document, content: preview.content.trim() }
      }),
    )
    const nextPreviewContent = previews
      .map(({ document, content }, index) => [
        `# Source ${index + 1}: ${document.title}`,
        `Kind: ${sourceDocumentKindLabel(document.kind)}`,
        `Filename: ${document.filename}`,
        '',
        content || 'No readable preview for this source document.',
      ].join('\n'))
      .join('\n\n---\n\n')
    if (activeSourcePreviewKey.value === previewKey) {
      previewContent.value = nextPreviewContent
      previewContentKey.value = previewKey
    }
  } catch (err) {
    previewError.value = err instanceof Error ? err.message : String(err)
  } finally {
    previewLoading.value = false
  }
}

const draftSourceText = computed(() => previewContent.value.trim())
const draftSourceReady = computed(() =>
  previewContentKey.value === activeSourcePreviewKey.value
  && !!draftSourceText.value,
)
const sourceInputContractEvidenceReady = computed(() =>
  draftSourceReady.value
  && developerInputContractEvidenceCoverage.value.expectedCapabilityIds.length > 0
  && developerInputContractEvidenceCoverage.value.missingCapabilityIds.length === 0
  && developerInputContractEvidenceCoverage.value.incompleteCapabilityIds.length === 0,
)
const draftQuestions = computed(() => bundleOpenQuestions(draftBundle.value))
const draftableSourceLabel = computed(() =>
  selectedSourceDocuments.value.length
    ? selectedSourceDocuments.value.map((document) => `${document.title} (${sourceDocumentKindLabel(document.kind)})`).join(', ')
    : 'No selected source document',
)
const sourceContextCopy = computed(() =>
  governedFrontingProject.value
    ? 'Use all relevant fronting intent and integration evidence, or select the exact subset for this assistant run. Fronting projects can draft from business intent, OpenAPI/API docs, MCP schemas, auth docs, permission matrices, workflow docs, policy sources, and runtime evidence.'
    : 'Use all relevant business source documents, or select the exact subset for this assistant run. Upload and delete documents from Source Docs; this page focuses on drafting, clarifying, and accepting proposals.',
)
const sourceMissingTitle = computed(() =>
  governedFrontingProject.value
    ? 'Fronting intent or integration evidence required for AI drafting'
    : 'Business spec required for PM AI drafting',
)
const sourceMissingCopy = computed(() =>
  governedFrontingProject.value
    ? 'Add fronting intent and at least one integration source such as an API/OpenAPI contract, MCP schema, API docs, auth docs, permission matrix, workflow docs, org policy, or runtime evidence.'
    : 'Upload a source document first so the assistant can draft from grounded business context instead of asking broad form questions.',
)
const draftMissingTitle = computed(() =>
  governedFrontingProject.value
    ? 'PM AI mode needs readable fronting source context'
    : 'PM AI mode needs a readable business spec',
)
const draftMissingCopy = computed(() =>
  governedFrontingProject.value
    ? 'Select or upload fronting intent or integration evidence before drafting. Manual Studio authoring still works without AI.'
    : 'Select or upload a business source document before drafting. Manual Studio authoring still works without AI.',
)
const sourceQualityTitle = computed(() =>
  governedFrontingProject.value ? 'Fronting Source Quality' : 'Business Spec Quality',
)
const sourceQualityNote = computed(() =>
  governedFrontingProject.value
    ? 'Higher-quality fronting sources include both intent and technical evidence, so the assistant can draft governed ANIP behavior with fewer clarification questions.'
    : 'Higher-quality business specs produce more concrete drafts and fewer clarification questions. Weak specs can still be used, but expect more review and correction before generation.',
)
const productDraftFailedSections = computed(() =>
  draftBundle.value?.sections.filter((section) => section.status === 'failed') ?? [],
)
const developerDraftFailedSections = computed(() =>
  developerDraftBundle.value?.sections.filter((section) => section.status === 'failed') ?? [],
)
const productDraftSourceChanged = computed(() =>
  !!draftBundle.value && draftBundle.value.sourceText !== draftSourceText.value,
)
const productDraftActionLabel = computed(() => {
  if (draftLoading.value) return draftBundle.value ? 'AI rerunning...' : 'AI drafting...'
  if (!draftBundle.value) return 'AI Draft Product Design'
  return productDraftSourceChanged.value ? 'Rerun AI Draft from Current Sources' : 'Rerun AI Draft'
})
const canOfferDeterministicProductDraft = computed(() =>
  draftSourceReady.value
  && canRunDeterministicDraft.value
  && (!!draftError.value || productDraftFailedSections.value.length > 0),
)
type SourceQualityStatus = 'strong' | 'usable' | 'weak'

interface SourceQualityCriterion {
  id: string
  label: string
  met: boolean
  detail: string
  improvement: string
}

interface AutopilotSourceEvidenceGate {
  ready: boolean
  summary: string
  detail: string
  messages: string[]
  modeGuidance: string
}

function includesAny(text: string, terms: string[]): boolean {
  const normalized = text.toLowerCase()
  return terms.some((term) => normalized.includes(term))
}

function looksLikePlaceholderSource(text: string): boolean {
  const normalized = text.toLowerCase()
  const placeholderTerms = [
    'lorem ipsum',
    'todo',
    'tbd',
    'placeholder',
    'coming soon',
    'fill this in',
    'sample text',
  ]
  const placeholderHits = placeholderTerms.filter((term) => normalized.includes(term)).length
  const wordCount = normalized.trim() ? normalized.trim().split(/\s+/).filter(Boolean).length : 0
  return placeholderHits >= 2 || (placeholderHits >= 1 && wordCount < 180)
}

function evaluateProductSourceQuality(text: string) {
  const trimmed = text.trim()
  const wordCount = trimmed ? trimmed.split(/\s+/).filter(Boolean).length : 0
  const headingCount = (trimmed.match(/^#{1,4}\s+/gm) ?? []).length
  const bulletCount = (trimmed.match(/^\s*[-*]\s+/gm) ?? []).length
  const criteria: SourceQualityCriterion[] = [
    {
      id: 'scope',
      label: 'Business scope and goal',
      met: wordCount >= 250 && includesAny(trimmed, ['goal', 'purpose', 'objective', 'problem', 'outcome', 'success']),
      detail: 'The spec should say what business problem the product solves and what outcome matters.',
      improvement: 'Add a short purpose section with business goals, target users, and expected outcomes.',
    },
    {
      id: 'actors',
      label: 'Actors and authority',
      met: includesAny(trimmed, ['actor', 'role', 'user', 'manager', 'admin', 'owner', 'approver', 'permission']),
      detail: 'The assistant needs role and authority boundaries to avoid broad generic policy drafts.',
      improvement: 'List the actors, what each can see, what each can do, and who approves high-impact actions.',
    },
    {
      id: 'scenarios',
      label: 'Concrete scenarios',
      met: includesAny(trimmed, ['scenario', 'example', 'when ', 'given ', 'workflow', 'use case', 'question']),
      detail: 'Concrete scenarios let Studio draft behavior instead of asking field-by-field questions.',
      improvement: 'Add representative user asks, expected outcomes, stop conditions, and edge cases.',
    },
    {
      id: 'governance',
      label: 'Governance and stop conditions',
      met: includesAny(trimmed, ['approval', 'clarification', 'deny', 'restrict', 'audit', 'trace', 'lineage', 'safe', 'risk']),
      detail: 'Governed behavior must be explicit before it can become deterministic contract data.',
      improvement: 'Document when the system should allow, restrict, deny, clarify, require approval, or preserve audit evidence.',
    },
    {
      id: 'data',
      label: 'Data, systems, and outputs',
      met: includesAny(trimmed, ['data', 'system', 'backend', 'crm', 'warehouse', 'api', 'input', 'output', 'metric', 'record']),
      detail: 'Service and capability drafting needs the business objects, source systems, and output expectations.',
      improvement: 'Name the important data objects, source systems, required inputs, and expected result shape.',
    },
    {
      id: 'structure',
      label: 'Readable structure',
      met: headingCount >= 2 || bulletCount >= 6,
      detail: 'Structured specs reduce extraction ambiguity and make proposal review faster.',
      improvement: 'Use headings and bullet lists for actors, scenarios, permissions, non-goals, and success criteria.',
    },
  ]
  const metCount = criteria.filter((item) => item.met).length
  const status: SourceQualityStatus = metCount >= 5 ? 'strong' : metCount >= 3 ? 'usable' : 'weak'
  return {
    status,
    score: Math.round((metCount / criteria.length) * 100),
    wordCount,
    criteria,
    weakAreas: criteria.filter((item) => !item.met),
    summary:
      status === 'strong'
        ? 'This source looks strong enough for a useful first draft with limited clarification.'
        : status === 'usable'
          ? 'This source is usable, but weak areas will likely create more clarification and review work.'
          : 'This source is weak for AI-assisted drafting. Studio can still draft, but expect generic proposals and more manual correction.',
  }
}

function evaluateFrontingSourceQuality(text: string) {
  const trimmed = text.trim()
  const wordCount = trimmed ? trimmed.split(/\s+/).filter(Boolean).length : 0
  const headingCount = (trimmed.match(/^#{1,4}\s+/gm) ?? []).length
  const bulletCount = (trimmed.match(/^\s*[-*]\s+/gm) ?? []).length
  const selectedIsIntegration = selectedSourceDocuments.value.some((document) => isFrontingIntegrationSource(document))
  const criteria: SourceQualityCriterion[] = [
    {
      id: 'fronting-intent',
      label: 'Fronting intent',
      met: frontingIntentReady.value || includesAny(trimmed, ['intent', 'allowed', 'agent', 'tool', 'user', 'outcome', 'business']),
      detail: 'The assistant needs to know what the governed ANIP layer should allow users or agents to accomplish.',
      improvement: 'Add fronting intent: target consumers, allowed outcomes, sensitive actions, and expected stops.',
    },
    {
      id: 'integration-contract',
      label: 'Integration contract',
      met: frontingIntegrationReady.value || selectedIsIntegration || includesAny(trimmed, ['openapi', 'swagger', 'endpoint', 'schema', 'mcp', 'tool', 'resource', 'graphql']),
      detail: 'Fronting projects need raw backend operation evidence before Studio can map governed capabilities.',
      improvement: 'Add an OpenAPI/API contract, MCP schema, endpoint docs, GraphQL schema, or raw operation metadata.',
    },
    {
      id: 'auth-permissions',
      label: 'Auth, scopes, and permissions',
      met: includesAny(trimmed, ['oauth', 'scope', 'permission', 'role', 'token', 'sso', 'service account', 'delegated', 'approval']),
      detail: 'ANIP must know which identity and authorization posture should govern downstream calls.',
      improvement: 'Document OAuth scopes, user-delegated vs service-delegated access, permission matrices, and approval boundaries.',
    },
    {
      id: 'data-controls',
      label: 'Sensitive data controls',
      met: includesAny(trimmed, ['sensitive', 'pii', 'secret', 'redact', 'mask', 'classification', 'external', 'audit', 'lineage']),
      detail: 'Central ANIP fronting should control what agents can send to external systems.',
      improvement: 'Identify sensitive fields, redaction/masking expectations, external-sharing restrictions, and audit evidence.',
    },
    {
      id: 'workflow-errors',
      label: 'Workflow and failure behavior',
      met: includesAny(trimmed, ['transition', 'status', 'lifecycle', 'required field', 'rate limit', 'error', 'retry', 'webhook', 'runbook']),
      detail: 'Generated fronting services need status transitions, required fields, and failure semantics.',
      improvement: 'Add workflow/status docs, required-field rules, error behavior, rate limits, and retry or clarification stops.',
    },
    {
      id: 'structure',
      label: 'Readable structure',
      met: wordCount >= 150 && (headingCount >= 2 || bulletCount >= 6),
      detail: 'Structured source evidence reduces extraction ambiguity and review effort.',
      improvement: 'Use headings and bullets for intent, raw operations, auth, permissions, sensitive data, workflows, and examples.',
    },
  ]
  const metCount = criteria.filter((item) => item.met).length
  const status: SourceQualityStatus = metCount >= 5 ? 'strong' : metCount >= 3 ? 'usable' : 'weak'
  return {
    status,
    score: Math.round((metCount / criteria.length) * 100),
    wordCount,
    criteria,
    weakAreas: criteria.filter((item) => !item.met),
    summary:
      status === 'strong'
        ? 'This source set looks strong enough for useful fronting drafts with limited clarification.'
        : status === 'usable'
          ? 'This source set is usable, but the weak areas will likely create more clarification and review work.'
          : 'This source set is weak for fronting drafts. Add intent plus integration evidence before expecting high-quality proposals.',
  }
}

const sourceQuality = computed(() =>
  governedFrontingProject.value
    ? evaluateFrontingSourceQuality(draftSourceReady.value ? draftSourceText.value : '')
    : evaluateProductSourceQuality(draftSourceReady.value ? draftSourceText.value : ''),
)
const expectedDeveloperCapabilityIds = computed(() => expectedCapabilityIdsFromShape(lockedShape.value ?? currentShape.value ?? null))
const developerInputContractEvidenceCoverage = computed(() =>
  inputContractReviewedEvidenceCoverage({
    sourceText: draftSourceReady.value ? draftSourceText.value : '',
    expectedCapabilityIds: expectedDeveloperCapabilityIds.value,
    pmArtifacts: projectStore.artifacts.pmArtifacts,
    capabilityFormalizations: ((findDeveloperDefinitionArtifact(projectStore.artifacts.pmArtifacts)?.data as DeveloperDefinitionData | undefined)?.capability_formalizations ?? []),
  }),
)

const autopilotSourceEvidenceGate = computed<AutopilotSourceEvidenceGate>(() => {
  const modeGuidance = 'Autopilot stopped instead of inventing missing contract truth. Use Guided Mode for targeted questions, use Manual Mode for deterministic editing, or upload stronger source evidence and rerun Autopilot.'
  const laneLabel = lane.value === 'dev' ? 'Developer' : governedFrontingProject.value ? 'Fronting' : 'Product'
  if (assistantDocuments.value.length === 0) {
    return {
      ready: false,
      summary: `${laneLabel} source evidence is missing.`,
      detail: lane.value === 'dev'
        ? 'Attach developer-owned interface, semantic model, API, runtime, or input-contract evidence before running Developer Autopilot.'
        : 'Attach product/business source evidence before running Product Autopilot.',
      messages: [
        lane.value === 'dev'
          ? 'Developer Autopilot needs implementation-grade evidence for services, capabilities, inputs, permissions, and runtime behavior.'
          : 'Product Autopilot needs business intent, actors, outcomes, scenarios, boundaries, and governance cues.',
      ],
      modeGuidance,
    }
  }
  if (previewLoading.value) {
    return {
      ready: false,
      summary: `${laneLabel} source evidence is still loading.`,
      detail: 'Wait for source previews to finish loading before running Autopilot.',
      messages: ['Studio has documents, but Autopilot only runs after it can inspect readable source content.'],
      modeGuidance,
    }
  }
  if (!draftSourceReady.value) {
    return {
      ready: false,
      summary: `${laneLabel} source evidence is not readable yet.`,
      detail: 'Select readable source documents or upload docs with extractable text.',
      messages: ['Autopilot is blocked because it cannot inspect the selected source content.'],
      modeGuidance,
    }
  }
  if (looksLikePlaceholderSource(draftSourceText.value)) {
    return {
      ready: false,
      summary: `${laneLabel} source evidence looks placeholder-level.`,
      detail: 'Replace TODO/TBD/sample content with real source truth before running Autopilot.',
      messages: ['Autopilot should not convert placeholder material into contract truth.'],
      modeGuidance,
    }
  }
  if (lane.value === 'dev') {
    const coverage = developerInputContractEvidenceCoverage.value
    if (coverage.expectedCapabilityIds.length === 0) {
      return {
        ready: false,
        summary: 'Developer capability inventory is not available yet.',
        detail: 'Lock Product Design service shape before Developer Autopilot can measure input-contract coverage.',
        messages: [
          'Autopilot needs the expected capability list before it can ask focused questions for missing implementation contracts.',
          'Use Guided or Manual Mode if you need to repair the product service shape first.',
        ],
        modeGuidance,
      }
    }
    const missingCount = coverage.missingCapabilityIds.length + coverage.incompleteCapabilityIds.length
    if (missingCount > 0) {
      const examples = [...coverage.missingCapabilityIds, ...coverage.incompleteCapabilityIds].slice(0, 6)
      return {
        ready: false,
        summary: `Developer source evidence covers ${coverage.coveredCapabilityIds.length}/${coverage.expectedCapabilityIds.length} capability input contracts.`,
        detail: 'Developer Autopilot found partial input-contract evidence. It will stop here instead of inventing missing runtime inputs.',
        messages: [
          examples.length ? `Missing or incomplete examples: ${examples.join(', ')}${missingCount > examples.length ? `, and ${missingCount - examples.length} more` : ''}.` : 'Some expected capabilities are missing reviewed input contracts.',
          'Upload additional developer interface/runtime evidence, or switch to Guided Mode to answer targeted implementation questions for the missing capabilities.',
          coverage.unknownCapabilityIds.length ? `Evidence also contains capability ids not present in the locked service shape: ${coverage.unknownCapabilityIds.slice(0, 4).join(', ')}.` : '',
        ].filter(Boolean),
        modeGuidance,
      }
    }
    if (coverage.weakInputClassifications.length > 0) {
      const examples = coverage.weakInputClassifications
        .slice(0, 6)
        .map((item) => `${item.capability_id}.${item.input_name}`)
      return {
        ready: false,
        summary: 'Developer source evidence has weak input classification.',
        detail: 'Developer Autopilot found required inputs that are structurally present but not classified enough for safe agent consumption.',
        messages: [
          `Missing semantic classification examples: ${examples.join(', ')}${coverage.weakInputClassifications.length > examples.length ? `, and ${coverage.weakInputClassifications.length - examples.length} more` : ''}.`,
          'Add semantic_type, entity_reference, allowed_values, input_format, validation_pattern, or clarification_hint for each required input before rerunning Autopilot.',
          'This prevents late Agent Consumption Readiness warnings after the expensive draft path has already run.',
        ],
        modeGuidance,
      }
    }
    return {
      ready: true,
      summary: 'Developer source evidence is ready for Autopilot.',
      detail: `Readable developer evidence covers ${coverage.coveredCapabilityIds.length}/${coverage.expectedCapabilityIds.length} expected capability input contracts.`,
      messages: [],
      modeGuidance,
    }
  }
  if (governedFrontingProject.value && (!frontingIntentReady.value || !frontingIntegrationReady.value)) {
    return {
      ready: false,
      summary: 'Fronting source evidence is incomplete.',
      detail: 'Fronting Autopilot needs both business/fronting intent and backend integration evidence before it can produce a governed contract.',
      messages: [
        frontingIntentReady.value ? 'Fronting intent is present.' : 'Missing fronting intent: what users/agents should be allowed to accomplish.',
        frontingIntegrationReady.value ? 'Integration evidence is present.' : 'Missing integration evidence: API/OpenAPI, MCP schema, auth scopes, workflow docs, semantic model, or runtime evidence.',
      ],
      modeGuidance,
    }
  }
  if (sourceQuality.value.status === 'weak') {
    return {
      ready: false,
      summary: `${laneLabel} source evidence is too weak for Autopilot.`,
      detail: sourceQuality.value.summary,
      messages: sourceQuality.value.weakAreas.slice(0, 4).map((area) => area.improvement),
      modeGuidance,
    }
  }
  return {
    ready: true,
    summary: `${laneLabel} source evidence is ready for Autopilot.`,
    detail: sourceQuality.value.summary,
    messages: [],
    modeGuidance,
  }
})

function shapeServiceCount(shape: ShapeRecord | null): number {
  const shapeData = shape?.data?.shape && typeof shape.data.shape === 'object'
    ? shape.data.shape as Record<string, unknown>
    : shape?.data && typeof shape.data === 'object'
      ? shape.data as Record<string, unknown>
      : null
  const services = Array.isArray(shapeData?.services) ? shapeData.services : []
  return services.filter((service) => service && typeof service === 'object').length
}

const productServiceTopologyPreference = computed<AssistantServiceTopologyPreference>(() => ({
  granularity: productServiceGranularity.value,
  target_service_count: productTargetServiceCount.value && productTargetServiceCount.value > 0
    ? productTargetServiceCount.value
    : null,
  preserve_source_services: false,
  rationale: productTargetServiceCount.value
    ? 'User selected an explicit deployable service count for AI-assisted Product Design drafting.'
    : 'User selected service granularity for AI-assisted Product Design drafting.',
}))

type DraftSectionWithClarifications = ProductDesignDraftSection | DeveloperDesignDraftSection

function clarificationQuestions(section: DraftSectionWithClarifications): AssistantClarificationQuestion[] {
  const proposal = section.envelope?.proposal
  return proposal?.proposal_kind === 'clarification_questions' ? proposal.questions : []
}

function isClarificationSection(section: DraftSectionWithClarifications): boolean {
  return clarificationQuestions(section).length > 0
}

function clarificationAnswer(section: DraftSectionWithClarifications, questionId: string): string {
  return section.clarificationAnswers?.[questionId] ?? ''
}

function selectedClarificationAnswers(section: DraftSectionWithClarifications) {
  return clarificationQuestions(section)
    .filter((question) => section.selectedIds.includes(question.question_id))
    .map((question) => ({
      question_id: question.question_id,
      prompt: question.prompt,
      target_artifact: question.target_artifact,
      answer: clarificationAnswer(section, question.question_id).trim(),
    }))
}

async function safeRecordAssistantAuditEvent(
  event: Omit<AssistantAuditEvent, 'id' | 'project_id' | 'created_at'>,
) {
  if (!project.value || readOnlyMode.value) return
  try {
    await appendAssistantAuditEvent({
      projectId: project.value.id,
      event: {
        ...event,
        assistant_runtime: assistantRuntimeContext(projectStore.runtimeStatus),
      },
    })
    await refreshArtifacts()
  } catch {
    // Audit persistence must not convert reviewed assistant proposals into failed authoring actions.
  }
}

function answeredClarificationContext(section: DraftSectionWithClarifications): AssistantClarificationAnswerContext[] {
  const answeredAt = new Date().toISOString()
  return selectedClarificationAnswers(section)
    .filter((question) => question.answer.length > 0)
    .map((question) => ({
      questionId: question.question_id,
      prompt: question.prompt,
      targetArtifact: question.target_artifact,
      answer: question.answer,
      answeredAt,
    }))
}

function canRegenerateFromClarifications(section: DraftSectionWithClarifications): boolean {
  if (section.status === 'failed') return true
  const selected = selectedClarificationAnswers(section)
  return selected.length > 0 && selected.every((question) => question.answer.length > 0)
}

function sourceTextWithClarificationAnswers(sourceText: string, section: DraftSectionWithClarifications): string {
  const answers = selectedClarificationAnswers(section)
  if (!answers.length) return sourceText
  return `${sourceText.trim()}\n\n---\nAssistant clarification answers for ${section.title}:\n${JSON.stringify(answers, null, 2)}`
}

function replaceBundleSection(sectionId: string, update: (section: ProductDesignDraftSection) => ProductDesignDraftSection) {
  if (!draftBundle.value) return
  draftBundle.value = {
    ...draftBundle.value,
    sections: draftBundle.value.sections.map((section) =>
      section.id === sectionId ? update(section) : section,
    ),
  }
}

async function persistProductBundleState() {
  if (!project.value || !draftBundle.value || readOnlyMode.value) return
  const artifact = await persistAssistantDraftBundle({
    projectId: project.value.id,
    lane: 'pm',
    bundle: draftBundle.value,
    artifactId: productBundleArtifactId.value,
    context: {
      source_document_id: selectedDocument.value?.id ?? null,
      source_document_title: selectedDocument.value?.title ?? null,
      source_documents: selectedSourceDocuments.value.map((document) => ({
        id: document.id,
        title: document.title,
        kind: document.kind,
        filename: document.filename,
      })),
      assistant_runtime: assistantRuntimeContext(projectStore.runtimeStatus),
    },
  })
  productBundleArtifactId.value = artifact.id
  await refreshArtifacts()
}

function resetAssistantProgress(message: string) {
  assistantProgressItems.value = [message]
  assistantCancelRequested.value = false
}

function recordAssistantProgress(message: string) {
  assistantProgressItems.value = [...assistantProgressItems.value, message].slice(-8)
}

function createAssistantAbortController() {
  assistantAbortController.value?.abort()
  const controller = new AbortController()
  assistantAbortController.value = controller
  assistantCancelRequested.value = false
  return controller
}

function clearAssistantAbortController(controller: AbortController) {
  if (assistantAbortController.value === controller) {
    assistantAbortController.value = null
  }
}

function cancelAssistantDraft() {
  if (!assistantAbortController.value || assistantCancelRequested.value) return
  assistantCancelRequested.value = true
  recordAssistantProgress('Cancel requested. Studio is stopping the active assistant call.')
  assistantAbortController.value.abort()
}

function isAbortError(err: unknown) {
  return err instanceof DOMException && err.name === 'AbortError'
}

async function handleDraftProductDesign(useDeterministic = false, sourceTextOverride?: string | null) {
  if (!project.value) return
  if (useDeterministic) {
    if (!canRunDeterministicDraft.value) return
  } else if (!assistantCanDraft.value) {
    return
  }
  const sourceText = sourceTextOverride?.trim() || (draftSourceReady.value ? draftSourceText.value : '')
  if (!sourceText) {
    draftError.value = governedFrontingProject.value
      ? 'Select a readable fronting intent, integration evidence, or policy source before drafting Product Design.'
      : 'Select a source document with readable text before drafting Product Design.'
    return
  }
  draftLoading.value = true
  productDraftOperation.value = useDeterministic ? 'deterministic' : 'ai'
  draftError.value = null
  const controller = useDeterministic ? null : createAssistantAbortController()
  if (!useDeterministic) {
    resetAssistantProgress('Preparing Product Design draft request')
  }
  try {
    draftBundle.value = await draftProductDesignBundle({
      projectId: project.value.id,
      projectName: project.value.name,
      sourceText,
      pmArtifacts: pmArtifacts.value,
      sourceRequirementsId: projectStore.activeRequirementsId,
      useDeterministic,
      serviceTopologyPreference: productServiceTopologyPreference.value,
      signal: controller?.signal,
      onProgress: useDeterministic ? undefined : recordAssistantProgress,
    })
    if (!useDeterministic) {
      recordAssistantProgress('Draft complete. Preparing review bundle.')
    }
    await persistProductBundleState()
    await safeRecordAssistantAuditEvent({
      event_type: 'draft_created',
      lane: 'pm',
      bundle_artifact_id: productBundleArtifactId.value,
      source_document_id: selectedDocument.value?.id ?? null,
      source_document_title: selectedDocument.value?.title ?? null,
      section_count: draftBundle.value.sections.length,
      draft_mode: useDeterministic ? 'deterministic' : 'ai',
    })
  } catch (err) {
    draftError.value = isAbortError(err)
      ? 'Assistant draft canceled. No Product Design draft changes were saved.'
      : err instanceof Error ? err.message : String(err)
  } finally {
    if (controller) clearAssistantAbortController(controller)
    draftLoading.value = false
    productDraftOperation.value = null
  }
}

async function handleDeterministicProductDesignDraft() {
  await handleDraftProductDesign(true)
}

async function persistProductClarificationAnswers(section: ProductDesignDraftSection) {
  await persistProductBundleState()
  await safeRecordAssistantAuditEvent({
    event_type: 'clarification_answers_saved',
    lane: 'pm',
    bundle_artifact_id: productBundleArtifactId.value,
    section_id: section.id,
    section_title: section.title,
    selected_ids: [...section.selectedIds],
    clarification_question_ids: selectedClarificationAnswers(section)
      .filter((question) => question.answer.length > 0)
      .map((question) => question.question_id),
  })
}

function toggleBundleItem(sectionId: string, itemId: string) {
  replaceBundleSection(sectionId, (section) => toggleSectionSelection(section, itemId))
}

function selectAllBundleItems(sectionId: string) {
  replaceBundleSection(sectionId, selectAllSectionItems)
}

function clearBundleItems(sectionId: string) {
  replaceBundleSection(sectionId, clearSectionSelection)
}

function productPatchPreviewSource(section: ProductDesignDraftSection): Record<string, unknown> | null {
  const artifactType = productArtifactTypeForDraftSection(section.id)
  if (!artifactType) return null
  const artifact = findProductDesignArtifact(projectStore.artifacts.pmArtifacts, artifactType)
  return artifact?.data && typeof artifact.data === 'object'
    ? artifact.data as Record<string, unknown>
    : null
}

function setProductClarificationAnswer(sectionId: string, questionId: string, value: string) {
  replaceBundleSection(sectionId, (section) => ({
    ...section,
    clarificationAnswers: {
      ...(section.clarificationAnswers ?? {}),
      [questionId]: value,
    },
  }))
}

async function saveBundleSection(section: ProductDesignDraftSection) {
  if (!project.value || readOnlyMode.value || !draftBundle.value) return
  if (isClarificationSection(section)) {
    draftError.value = 'Answer the selected clarification questions and regenerate this section before saving it.'
    return
  }
  savingSectionId.value = section.id
  draftError.value = null
  try {
    await saveAcceptedProductDesignSection({
      project: project.value,
      section,
      pmArtifacts: projectStore.artifacts.pmArtifacts,
      requirements: projectStore.artifacts.requirements,
      scenarios: projectStore.artifacts.scenarios,
      sourceText: draftBundle.value.sourceText,
    })
    await refreshArtifacts()
    replaceBundleSection(section.id, (current) => ({ ...current, status: 'saved' }))
    await persistProductBundleState()
    await safeRecordAssistantAuditEvent({
      event_type: 'section_saved',
      lane: 'pm',
      bundle_artifact_id: productBundleArtifactId.value,
      section_id: section.id,
      section_title: section.title,
      selected_ids: [...section.selectedIds],
    })
  } catch (err) {
    draftError.value = err instanceof Error ? err.message : String(err)
  } finally {
    savingSectionId.value = null
  }
}

async function regenerateProductSection(section: ProductDesignDraftSection) {
  if (!project.value || !draftBundle.value || !canRegenerateFromClarifications(section)) return
  regeneratingSectionId.value = section.id
  draftError.value = null
  try {
    const usedAnswers = section.status === 'failed' ? [] : answeredClarificationContext(section)
    const redrafted = await redraftProductDesignSection({
      projectId: project.value.id,
      section,
      sourceText: sourceTextWithClarificationAnswers(draftBundle.value.sourceText, section),
      sourceRequirementsId: projectStore.activeRequirementsId,
      serviceTopologyPreference: productServiceTopologyPreference.value,
    })
    replaceBundleSection(section.id, () => ({
      ...redrafted,
      usedClarificationAnswers: usedAnswers,
      error: undefined,
    }))
    await persistProductBundleState()
    await safeRecordAssistantAuditEvent({
      event_type: 'section_regenerated',
      lane: 'pm',
      bundle_artifact_id: productBundleArtifactId.value,
      section_id: section.id,
      section_title: section.title,
      selected_ids: [...section.selectedIds],
      clarification_question_ids: usedAnswers.map((answer) => answer.questionId),
    })
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    draftError.value = message
    replaceBundleSection(section.id, (current) => ({
      ...current,
      status: 'failed',
      error: message,
    }))
    try {
      await persistProductBundleState()
    } catch {
      // Keep the assistant failure visible even if persisting the failed bundle state also fails.
    }
    await safeRecordAssistantAuditEvent({
      event_type: 'section_regeneration_failed',
      lane: 'pm',
      bundle_artifact_id: productBundleArtifactId.value,
      section_id: section.id,
      section_title: section.title,
      selected_ids: [...section.selectedIds],
      clarification_question_ids: selectedClarificationAnswers(section)
        .filter((question) => question.answer.length > 0)
        .map((question) => question.question_id),
      status: 'failed',
      error: message,
    })
  } finally {
    regeneratingSectionId.value = null
  }
}

async function saveAllSelectedSections() {
  if (!draftBundle.value) return
  for (const section of draftBundle.value.sections) {
    if (section.status === 'saved' || section.status === 'failed' || isClarificationSection(section) || section.selectedIds.length === 0) continue
    await saveBundleSection(section)
    if (draftError.value) return
  }
}

function productDraftHasBlockingReviewItems(): boolean {
  if (!draftBundle.value) return false
  return draftBundle.value.sections.some((section) =>
    section.status === 'failed'
    || isClarificationSection(section)
    || section.selectedIds.length === 0,
  )
}

function productDraftNeedsSaving(): boolean {
  if (!draftBundle.value) return false
  return draftBundle.value.sections.some((section) =>
    section.status !== 'saved'
    && section.status !== 'failed'
    && !isClarificationSection(section)
    && section.selectedIds.length > 0,
  )
}

async function discardCurrentBundle() {
  if (!project.value || discardingBundle.value || readOnlyMode.value) return
  const artifactId = lane.value === 'pm' ? productBundleArtifactId.value : developerBundleArtifactId.value
  const discardedLane = lane.value
  discardingBundle.value = true
  try {
    if (artifactId) {
      await deleteAssistantDraftBundle(project.value.id, artifactId)
      await refreshArtifacts()
      await safeRecordAssistantAuditEvent({
        event_type: 'draft_discarded',
        lane: discardedLane,
        bundle_artifact_id: artifactId,
      })
    }
    if (lane.value === 'pm') {
      productBundleArtifactId.value = null
      draftBundle.value = null
    } else {
      developerBundleArtifactId.value = null
      developerDraftBundle.value = null
    }
  } finally {
    discardingBundle.value = false
  }
}

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
const baselineArtifact = computed(() => findDeveloperBaselineArtifact(projectStore.artifacts.pmArtifacts))
const developerDefinitionArtifact = computed(() => findDeveloperDefinitionArtifact(projectStore.artifacts.pmArtifacts))
const traceabilityArtifact = computed(() => findTraceabilityArtifact(projectStore.artifacts.pmArtifacts))
const developerDesignReviewArtifactTypes = [
  'assistant_service_design_candidates',
  'assistant_capability_formalization_candidates',
  'assistant_runtime_policy_binding_candidates',
  'assistant_input_contract_candidates',
  'assistant_backend_binding_candidates',
  'assistant_verification_expectation_candidates',
] as const
const baseline = computed(() =>
  (baselineArtifact.value?.data as DeveloperBaselineData | undefined) ?? null,
)
const traceabilityData = computed(() =>
  (traceabilityArtifact.value?.data as Record<string, any> | undefined) ?? null,
)
const traceabilityRecord = computed(() =>
  (traceabilityArtifact.value?.data as TraceabilityRecordData | undefined) ?? null,
)
const traceabilityCoverage = computed(() =>
  (Array.isArray(traceabilityData.value?.coverage) ? traceabilityData.value.coverage : []) as TraceabilityCoverageItem[],
)
const agentReadinessReport = computed(() =>
  (traceabilityData.value?.agent_consumption_readiness ?? null) as AgentConsumptionReadinessReport | null,
)
const agentReadinessSummary = computed(() =>
  (traceabilityData.value?.agent_consumption_readiness?.summary ?? {}) as Record<string, unknown>,
)
const agentReadinessStatus = computed(() =>
  String(traceabilityData.value?.agent_consumption_readiness?.status ?? ''),
)
const existingHighRiskReport = computed(() =>
  highRiskConfirmationReportFromArtifacts(projectStore.artifacts.pmArtifacts),
)
const highRiskSummary = computed(() =>
  (existingHighRiskReport.value?.summary ?? {}) as Record<string, unknown>,
)
function numericSummaryValue(summary: Record<string, unknown>, key: string): number {
  const value = Number(summary[key] ?? 0)
  return Number.isFinite(value) ? value : 0
}
const developerDefinitionSaved = computed(() => !!developerDefinitionArtifact.value)
const developerCoverageSaved = computed(() => !!traceabilityArtifact.value)
const simulatorReportSaved = computed(() =>
  projectStore.artifacts.pmArtifacts.some((artifact) => artifact.data?.artifact_type === 'agent_consumption_simulation_report'),
)
const developerCoverageMappingBlocked = computed(() => {
  if (!traceabilityArtifact.value) return true
  const summary = summarizeCoverage(traceabilityCoverage.value)
  return summary.missing > 0 || summary.partial > 0
})
const developerDesignReviewSaved = computed(() => {
  const artifactTypes = new Set(projectStore.artifacts.pmArtifacts.map((artifact) => artifact.data?.artifact_type))
  return developerDesignReviewArtifactTypes.every((artifactType) => artifactTypes.has(artifactType))
})
const developerReadinessFindingCount = computed(() =>
  numericSummaryValue(agentReadinessSummary.value, 'blockers')
  + numericSummaryValue(agentReadinessSummary.value, 'warnings'),
)
const developerHighRiskUnresolvedCount = computed(() =>
  numericSummaryValue(highRiskSummary.value, 'unresolved'),
)
const developerReviewBlocked = computed(() =>
  agentReadinessStatus.value === 'blocked'
  || developerReadinessFindingCount.value > 0
  || developerHighRiskUnresolvedCount.value > 0,
)
const projectIssueIndex = computed(() => buildProjectIssueIndex({
  project: project.value,
  pmArtifacts: projectStore.artifacts.pmArtifacts,
  requirements: requirements.value,
  scenarios: scenarios.value,
  documents: documents.value,
  shapes: shapes.value,
  sourceInputContractEvidenceReady: lane.value === 'dev' ? sourceInputContractEvidenceReady.value : false,
}))
const productDesignIssue = computed(() => projectIssueIndex.value['project-product-design'] ?? null)
const developerDesignIssue = computed(() => projectIssueIndex.value['project-developer-design'] ?? null)
const appGlueIssue = computed(() => projectIssueIndex.value['project-developer-app-glue'] ?? null)
const operatorHighRiskReport = computed(() => {
  if (!project.value) return null
  return buildHighRiskConfirmationReport({
    project: project.value,
    pmArtifacts: projectStore.artifacts.pmArtifacts,
    documents: documents.value,
    requirements: requirements.value,
    scenarios: scenarios.value,
    shapes: shapes.value,
    existing: existingHighRiskReport.value,
    sourceInputContractEvidenceReady: lane.value === 'dev' ? sourceInputContractEvidenceReady.value : false,
  })
})
const operatorDecisionQueue = computed(() => {
  if (!project.value) return []
  return buildStudioOperatorDecisionQueue({
    projectId: project.value.id,
    workspaceId: project.value.workspace_id,
    coverage: traceabilityCoverage.value,
    highRiskItems: unresolvedHighRiskConfirmationItems(operatorHighRiskReport.value),
    readinessReport: agentReadinessReport.value,
  })
})
const developerContinuationState = computed(() => {
  if (developerCoverageSaved.value) {
    return {
      title: 'Continue Developer Review',
      copy: developerReviewBlocked.value
        ? 'Developer Design already exists. The next useful assistant action is resolving readiness findings and high-risk confirmations, not creating another first draft.'
        : 'Developer Design coverage already exists. Review coverage, readiness, and simulator evidence before rerunning AI drafting from the locked baseline.',
      label: 'Open Agent & App Glue',
      path: projectRoute('/developer/app-glue'),
    }
  }
  if (developerDefinitionSaved.value) {
    return {
      title: 'Continue Developer Definition',
      copy: 'A Developer Definition is already saved. Review or revise the saved contract before rerunning AI drafting from the locked baseline.',
      label: 'Open Developer Definition',
      path: projectRoute('/developer/definition'),
    }
  }
  if (developerDesignReviewSaved.value) {
    return {
      title: 'Continue Developer Review',
      copy: 'Developer Design review artifacts already exist. Continue with coverage, readiness, and definition gates before rerunning AI drafting from the locked baseline.',
      label: 'Open Developer Coverage',
      path: projectRoute('/developer/coverage'),
    }
  }
  return null
})

const operatorStatusCards = computed(() => [
  {
    label: lane.value === 'dev' ? 'Developer source docs' : 'Source documents',
    status: autopilotSourceEvidenceGate.value.ready ? 'Ready' : 'Blocked',
    ready: autopilotSourceEvidenceGate.value.ready,
    detail: autopilotSourceEvidenceGate.value.detail,
  },
  {
    label: 'Product Design',
    status: productDesignIssue.value ? 'Needs work' : 'Ready',
    ready: !productDesignIssue.value,
    detail: productDesignIssue.value?.messages[0] ?? 'Product intent is complete enough for developer handoff.',
  },
  {
    label: 'Developer baseline',
    status: baseline.value ? 'Locked' : 'Needed',
    ready: !!baseline.value,
    detail: baseline.value
      ? `Locked ${formatStudioTimestamp(baseline.value.locked_at)}.`
      : 'Lock Product Design before Studio drafts Developer Design from a stable baseline.',
  },
  {
    label: 'Developer Design',
    status: developerDesignIssue.value ? 'Needs work' : 'Ready',
    ready: !developerDesignIssue.value,
    detail: developerDesignIssue.value?.messages[0] ?? 'Developer Design is ready for definition, generation, or publication gates.',
  },
])
const operatorTasks = computed(() => buildStudioOperatorTasks({
  project: project.value,
  documents_count: assistantDocuments.value.length,
  source_docs_label: lane.value === 'dev' ? 'developer source documents' : 'source documents',
  source_docs_empty_detail: lane.value === 'dev'
    ? 'Attach service interfaces, semantic models, auth/scopes, or reviewed input-contract evidence before drafting Developer Design.'
    : 'Attach business source documents before drafting Product Design.',
  source_docs_path: lane.value === 'dev'
    ? projectRoute('/developer/source-docs')
    : projectRoute('/source-docs'),
  source_evidence_ready: autopilotSourceEvidenceGate.value.ready,
  source_evidence_detail: autopilotSourceEvidenceGate.value.detail,
  source_evidence_mode_guidance: autopilotSourceEvidenceGate.value.modeGuidance,
  product_blocked: !!productDesignIssue.value,
  baseline_locked: !!baseline.value,
  developer_draft_available: !!developerDraftBundle.value,
  developer_design_saved: developerDesignReviewSaved.value,
  developer_definition_saved: developerDefinitionSaved.value,
  coverage_blocked: developerCoverageMappingBlocked.value,
  simulator_report_saved: simulatorReportSaved.value,
  developer_blocked: !!developerDesignIssue.value,
  app_readiness_blocked: !!appGlueIssue.value || developerReviewBlocked.value,
  source_ready: draftSourceReady.value,
  developer_ready: developerReady.value,
}))

const baseOperatorTask = computed(() => nextStudioOperatorTask(operatorTasks.value))
const operatorHandoffSummary = computed(() => {
  if (!project.value) return null
  return buildStudioOperatorHandoffSummary({
    project: project.value,
    tasks: operatorTasks.value,
    activities: operatorActivities.value,
  })
})
const operatorSummaryStatusLabel = computed(() => {
  const status = operatorHandoffSummary.value?.overall_status
  if (status === 'ready_for_generation') return 'Ready for next gate'
  if (status === 'needs_review') return 'Needs review'
  if (status === 'blocked') return 'Blocked'
  return 'Not available'
})
const operatorSummaryStatusReady = computed(() => operatorHandoffSummary.value?.overall_status === 'ready_for_generation')

const operatorPrimaryStep = computed(() => {
  const task = baseOperatorTask.value
  if (!task) {
    return {
      title: 'Project workflow complete',
      detail: 'No next Autopilot step is available.',
      why_it_matters: 'Autopilot Mode only advances when Studio can identify a deterministic next step.',
      success_condition: 'All visible Autopilot tasks are complete or intentionally handled.',
      label: 'Open Project',
      canRun: true,
      run: null as null | (() => Promise<void | 'needs_review'>),
      path: projectRoute(),
      requires_human_decision: false,
    }
  }
  const label = operatorActionLabel(task)
  return {
    ...task,
    label,
    canRun: operatorTaskCanRun(task),
    path: task.target_path,
    run: operatorTaskRun(task),
  }
})

async function runOperatorPrimaryStep() {
  const step = operatorPrimaryStep.value
  const task = baseOperatorTask.value
  if (!step.canRun) return
  await recordOperatorActivity({
    title: `Started: ${step.title}`,
    detail: step.detail,
    task,
    outcome: 'started',
  })
  if (step.run) {
    const result = await step.run()
    const needsReview = result === 'needs_review' || step.requires_human_decision
    await recordOperatorActivity({
      title: `${needsReview ? 'Ready for review' : 'Completed'}: ${step.title}`,
      detail: needsReview
        ? 'Autopilot prepared the next artifact or opened the next decision point. Human review is still required before this becomes contract truth.'
        : step.success_condition,
      task,
      outcome: needsReview ? 'needs_review' : 'completed',
    })
    return
  }
  if (step.path) {
    await recordOperatorActivity({
      title: `Opened review page: ${step.title}`,
      detail: step.path,
      task,
      outcome: step.requires_human_decision ? 'needs_review' : 'completed',
    })
    router.push(step.path)
  }
}

async function recordOperatorActivity(args: Parameters<typeof createStudioOperatorActivity>[0]) {
  if (!project.value) return
  const event = createStudioOperatorActivity(args)
  try {
    await persistStudioOperatorActivity({
      projectId: project.value.id,
      pmArtifacts: projectStore.artifacts.pmArtifacts,
      event,
    })
    await refreshArtifacts()
  } catch {
    // Activity persistence must not make an otherwise valid operator action fail.
  }
}

async function saveOperatorHandoffSummary() {
  if (!project.value || !operatorHandoffSummary.value) return
  operatorSummarySaving.value = true
  operatorSummaryMessage.value = null
  operatorSummaryError.value = null
  try {
    await persistStudioOperatorHandoffSummary({
      projectId: project.value.id,
      pmArtifacts: projectStore.artifacts.pmArtifacts,
      summary: operatorHandoffSummary.value,
    })
    await refreshArtifacts()
    operatorSummaryMessage.value = 'Autopilot summary artifact saved.'
  } catch (err) {
    operatorSummaryError.value = err instanceof Error ? err.message : String(err)
  } finally {
    operatorSummarySaving.value = false
  }
}

async function applyOperatorDecision(
  item: StudioOperatorDecisionQueueItem,
  action: StudioOperatorDecisionQueueAction,
) {
  if (!traceabilityArtifact.value && item.source === 'high_risk') {
    await applyStandaloneHighRiskDecision(item, action)
    return
  }
  if (!project.value || !traceabilityArtifact.value || !traceabilityRecord.value) {
    operatorDecisionError.value = 'Save Developer Coverage before applying Autopilot decisions.'
    return
  }
  operatorDecisionApplyingId.value = `${item.id}:${action.id}`
  operatorDecisionMessage.value = null
  operatorDecisionError.value = null
  try {
    const next = JSON.parse(JSON.stringify(traceabilityRecord.value)) as TraceabilityRecordData
    const now = new Date().toISOString()
    if (item.source === 'coordination') {
      applyOperatorCoordinationDecision(next, item, action, now)
    } else if (item.source === 'high_risk') {
      applyOperatorHighRiskDecision(next, item, action, now)
    } else {
      applyOperatorReadinessDecision(next, item, action, now)
    }
    await updatePmArtifact(project.value.id, traceabilityArtifact.value.id, {
      title: traceabilityArtifact.value.title,
      status: traceabilityArtifact.value.status,
      data: next,
    })
    await refreshArtifacts()
    await recordOperatorActivity({
      title: `Reviewed: ${item.title}`,
      detail: `${action.label}: ${action.detail}`,
      task: baseOperatorTask.value,
      outcome: action.id === 'follow_up' || action.id === 'defer' ? 'needs_review' : 'completed',
    })
    operatorDecisionMessage.value = `${action.label} saved for ${item.title}.`
  } catch (err) {
    operatorDecisionError.value = err instanceof Error ? err.message : String(err)
  } finally {
    operatorDecisionApplyingId.value = null
  }
}

async function applyStandaloneHighRiskDecision(
  item: StudioOperatorDecisionQueueItem,
  action: StudioOperatorDecisionQueueAction,
) {
  if (!project.value) return
  operatorDecisionApplyingId.value = `${item.id}:${action.id}`
  operatorDecisionMessage.value = null
  operatorDecisionError.value = null
  try {
    const report = operatorHighRiskReport.value
    const highRiskItem = report?.items.find((candidate) => candidate.id === item.source_id)
    if (!report || !highRiskItem) throw new Error('High-risk decision is no longer available.')
    if (highRiskItem.source !== 'product_design') {
      throw new Error('Save Developer Coverage before applying Developer Design decisions.')
    }
    const now = new Date().toISOString()
    const next: HighRiskConfirmationReport = {
      ...report,
      artifact_type: HIGH_RISK_CONFIRMATIONS_ARTIFACT_TYPE,
      reviews: {
        ...(report.reviews ?? {}),
        [item.source_id]: {
          id: item.source_id,
          status: action.id === 'defer' ? 'deferred' : 'confirmed',
          note: `${action.label}: ${highRiskItem.recommendation || highRiskItem.detail}`,
          reviewed_at: now,
        },
      },
    }
    const reviewedReport = buildHighRiskConfirmationReport({
      project: project.value,
      pmArtifacts: projectStore.artifacts.pmArtifacts,
      documents: documents.value,
      requirements: requirements.value,
      scenarios: scenarios.value,
      shapes: shapes.value,
      existing: next,
      sourceInputContractEvidenceReady: false,
    })
    const existing = findHighRiskConfirmationArtifact(projectStore.artifacts.pmArtifacts)
    if (existing) {
      await updatePmArtifact(project.value.id, existing.id, {
        title: existing.title,
        status: 'draft',
        data: reviewedReport,
      })
    } else {
      await createPmArtifact(project.value.id, {
        id: `${project.value.id}-high-risk-confirmations`,
        title: 'High-Risk Confirmations',
        data: reviewedReport,
      })
    }
    await refreshArtifacts()
    await recordOperatorActivity({
      title: `Reviewed: ${item.title}`,
      detail: `${action.label}: ${action.detail}`,
      task: baseOperatorTask.value,
      outcome: action.id === 'defer' ? 'needs_review' : 'completed',
    })
    operatorDecisionMessage.value = `${action.label} saved for ${item.title}.`
  } catch (err) {
    operatorDecisionError.value = err instanceof Error ? err.message : String(err)
  } finally {
    operatorDecisionApplyingId.value = null
  }
}

function applyOperatorCoordinationDecision(
  record: TraceabilityRecordData,
  item: StudioOperatorDecisionQueueItem,
  action: StudioOperatorDecisionQueueAction,
  now: string,
) {
  const coverageItem = record.coverage.find((candidate) => candidate.id === item.source_id)
  if (!coverageItem || !project.value) throw new Error('Coordination item is no longer available.')
  const choice = coordinationResolutionChoices(coverageItem, project.value.id).find((candidate) => candidate.id === action.id)
  if (!choice) throw new Error('Unsupported coordination decision.')
  coverageItem.status = choice.status
  coverageItem.rationale = choice.rationale
  coverageItem.operator_resolution = {
    choice_id: choice.id,
    applied_at: now,
    target_artifact: choice.patch_preview.target_artifact,
    summary: choice.effect,
    requires_review: choice.patch_preview.requires_review,
    changes: [...choice.patch_preview.changes],
  }
}

function applyOperatorHighRiskDecision(
  record: TraceabilityRecordData,
  item: StudioOperatorDecisionQueueItem,
  action: StudioOperatorDecisionQueueAction,
  now: string,
) {
  const report = record.high_risk_confirmations ?? operatorHighRiskReport.value
  const highRiskItem = report?.items.find((candidate) => candidate.id === item.source_id)
  if (!report || !highRiskItem) throw new Error('High-risk decision is no longer available.')
  record.high_risk_confirmations = {
    ...report,
    reviews: {
      ...(report.reviews ?? {}),
      [item.source_id]: {
        id: item.source_id,
        status: action.id === 'defer' ? 'deferred' : 'confirmed',
        note: `${action.label}: ${highRiskItem.recommendation || highRiskItem.detail}`,
        reviewed_at: now,
      },
    },
  }
  if (item.source_id === 'agent-readiness:automation-harness-reviews' && action.id !== 'defer') {
    const readiness = record.agent_consumption_readiness as AgentConsumptionReadinessReport | undefined
    const reviews = readiness?.finding_reviews
    if (readiness && reviews) {
      record.agent_consumption_readiness = JSON.parse(JSON.stringify({
        ...readiness,
        finding_reviews: Object.fromEntries(
          Object.entries(reviews).map(([id, review]) => [
            id,
            {
              ...review,
              review_method: 'manual',
              reviewed_at: now,
              note: review.note || 'Autopilot confirmed this readiness classification for generation.',
            },
          ]),
        ),
      }))
    }
  }
}

function applyOperatorReadinessDecision(
  record: TraceabilityRecordData,
  item: StudioOperatorDecisionQueueItem,
  action: StudioOperatorDecisionQueueAction,
  now: string,
) {
  const report = record.agent_consumption_readiness as AgentConsumptionReadinessReport | undefined
  const finding = report?.findings.find((candidate) => candidate.id === item.source_id)
  if (!report || !finding) throw new Error('Readiness finding is no longer available.')
  if (
    action.id !== 'contract_composition'
    && action.id !== 'explicit_app_glue'
    && action.id !== 'acceptable_warning'
    && action.id !== 'follow_up'
  ) {
    throw new Error('Unsupported readiness decision.')
  }
  record.agent_consumption_readiness = JSON.parse(JSON.stringify({
    ...report,
    finding_reviews: {
      ...(report.finding_reviews ?? {}),
      [item.source_id]: {
        id: item.source_id,
        decision: action.id,
        note: `${action.label}: ${finding.recommendation || finding.detail}`,
        reviewed_at: now,
        review_method: 'manual',
      },
    },
  }))
  if (action.id === 'explicit_app_glue' && finding.capability_id) {
    const definition = (developerDefinitionArtifact.value?.data as DeveloperDefinitionData | undefined) ?? null
    const capability = definition?.capability_formalizations.find((candidate) =>
      candidate.capability_id === finding.capability_id,
    )
    const currentReviews = (record.agent_consumability_reviews ?? {}) as Record<string, AgentConsumabilityCapabilityReview>
    const semanticRule = semanticInterpretationRuleForFinding(finding, `${action.label}: ${finding.recommendation || finding.detail}`)
    const selectionHint = selectionHintForSemanticRule(finding.capability_id, semanticRule)
    record.agent_consumability_reviews = {
      ...currentReviews,
      [finding.capability_id]: {
        ...(currentReviews[finding.capability_id] ?? {}),
        capability_id: finding.capability_id,
        reviewed_at: now,
        intent_category: currentReviews[finding.capability_id]?.intent_category
          ?? finding.capability_id.replace(/_/g, '.'),
        intent_summary: currentReviews[finding.capability_id]?.intent_summary
          ?? capability?.summary
          ?? capability?.title
          ?? finding.title,
        app_glue_required: true,
        app_glue_reason: `${action.label}: ${finding.recommendation || finding.detail}`,
        intent_rules: currentReviews[finding.capability_id]?.intent_rules ?? [{
          id: item.source_id.split(':').pop() || 'operator-app-glue',
          meaning: finding.title,
          owner: 'agent_app_glue',
          agent_action: finding.recommendation || finding.detail,
        }],
        business_language_rules: mergeSemanticInterpretationRule(
          currentReviews[finding.capability_id]?.business_language_rules,
          semanticRule,
        ),
        selection_hints: mergeSelectionHint(currentReviews[finding.capability_id]?.selection_hints, selectionHint),
        input_meanings: currentReviews[finding.capability_id]?.input_meanings,
        reference_catalogs: currentReviews[finding.capability_id]?.reference_catalogs,
        app_boundaries: currentReviews[finding.capability_id]?.app_boundaries,
      },
    } as unknown as TraceabilityRecordData['agent_consumability_reviews']
  }
}

function operatorActionLabel(task: StudioOperatorTask): string {
  if (task.kind === 'draft_product_design' && draftBundle.value) return 'Review Product Draft'
  if (task.kind === 'draft_developer_design' && developerDraftBundle.value) return 'Review Developer Draft'
  return task.safe_action_label
}

function operatorTaskCanRun(task: StudioOperatorTask): boolean {
  if (task.kind === 'draft_product_design') {
    return !previewLoading.value
      && draftSourceReady.value
      && autopilotSourceEvidenceGate.value.ready
      && assistantCanDraft.value
  }
  if (task.kind === 'draft_developer_design') {
    return developerReady.value
      && draftSourceReady.value
      && autopilotSourceEvidenceGate.value.ready
      && assistantCanDraft.value
  }
  return task.state !== 'blocked'
}

function operatorTaskRun(task: StudioOperatorTask): null | (() => Promise<void | 'needs_review'>) {
  if (task.kind === 'draft_product_design') {
    const sourceTextForRun = draftSourceText.value
    return async () => {
      if (!draftBundle.value) {
        await handleDraftProductDesign(false, sourceTextForRun)
      }
      if (draftBundle.value) {
        if (productDraftHasBlockingReviewItems()) {
          setWorkMode('guided')
          return 'needs_review'
        }
        if (productDraftNeedsSaving()) {
          await saveAllSelectedSections()
          if (draftError.value) {
            setWorkMode('guided')
            return 'needs_review'
          }
        }
      }
    }
  }
  if (task.kind === 'draft_developer_design') {
    const sourceTextForRun = developerDraftSourceText.value
    return async () => {
      if (!developerDraftBundle.value) await handleDraftDeveloperDesign(false, sourceTextForRun)
      if (developerDraftBundle.value) {
        if (developerDraftHasBlockingReviewItems()) {
          setWorkMode('guided')
          return 'needs_review'
        }
        if (developerDraftNeedsSaving()) {
          await saveAllSelectedDeveloperSections()
          if (developerDraftError.value) {
            setWorkMode('guided')
            return 'needs_review'
          }
        }
      }
    }
  }
  return null
}
const lockedRequirements = computed(() =>
  requirements.value.find((item) => item.id === baseline.value?.source_inputs.requirements_id)
  ?? null,
)
const lockedShape = computed(() =>
  shapes.value.find((item) => item.id === baseline.value?.source_inputs.shape_id)
  ?? null,
)
const lockedShapeServiceCount = computed(() => shapeServiceCount(lockedShape.value))
const developerServiceTopologyPreference = computed<AssistantServiceTopologyPreference | null>(() => {
  if (!lockedShape.value) return null
  const count = lockedShapeServiceCount.value
  return {
    granularity: 'source_defined',
    target_service_count: count > 0 ? count : null,
    preserve_source_services: true,
    rationale: 'Developer Design must preserve the locked Product Design service topology unless the baseline is intentionally changed.',
  }
})
const developerReady = computed(() =>
  !!baseline.value && !!lockedRequirements.value && currentScenarios.value.length > 0 && !!lockedShape.value,
)
const developerLaneNeedsBaseline = computed(() => lane.value === 'dev' && !developerReady.value)
const canOfferDeterministicDeveloperDraft = computed(() =>
  developerReady.value
  && canRunDeterministicDraft.value
  && (!!developerDraftError.value || developerDraftFailedSections.value.length > 0),
)
const canSaveDeveloperDraftBundle = computed(() =>
  !!developerDraftBundle.value
  && !developerDraftError.value
  && developerDraftFailedSections.value.length === 0
  && !developerDraftBaselineChanged.value
  && savingDeveloperSectionId.value === null
  && !readOnlyMode.value,
)
const developerBaselineText = computed(() =>
  project.value
    ? buildDeveloperBaselineSourceText({
        projectName: project.value.name,
        requirements: lockedRequirements.value,
        scenarios: currentScenarios.value,
        shape: lockedShape.value,
        baselineLockedAt: baseline.value?.locked_at ?? null,
      })
    : '',
)
const developerDraftSourceText = computed(() => {
  const baselineText = developerBaselineText.value.trim()
  const additionalSourceText = draftSourceReady.value ? draftSourceText.value.trim() : ''
  if (!additionalSourceText) return baselineText
  return [
    '# Locked Product Design Baseline',
    baselineText,
    '',
    '# Source Evidence Available To Developer Design',
    additionalSourceText,
  ].join('\n')
})
const developerSourceContextReady = computed(() =>
  assistantDocuments.value.length === 0 || draftSourceReady.value,
)
const developerDraftQuestions = computed(() => developerBundleOpenQuestions(developerDraftBundle.value))
const developerDraftBaselineChanged = computed(() =>
  !!developerDraftBundle.value
  && (
    developerDraftBundle.value.baselineText !== developerBaselineText.value
    || (developerDraftBundle.value.sourceText ?? developerDraftBundle.value.baselineText) !== developerDraftSourceText.value
  ),
)
const developerDraftActionLabel = computed(() => {
  if (developerDraftLoading.value) return developerDraftBundle.value ? 'AI rerunning...' : 'AI drafting...'
  if (developerContinuationState.value && !developerDraftBundle.value) return 'Rerun AI Draft from Locked Baseline'
  if (!developerDraftBundle.value) return 'AI Draft Developer Design'
  return developerDraftBaselineChanged.value ? 'Rerun AI Draft from Current Baseline' : 'Rerun AI Draft'
})
const assistantOverlayActive = computed(() =>
  (draftLoading.value && productDraftOperation.value === 'ai')
  || (developerDraftLoading.value && developerDraftOperation.value === 'ai'),
)
const assistantOverlayTitle = computed(() => {
  if (draftLoading.value) return draftBundle.value ? 'Rerunning Product Design draft' : 'Drafting Product Design'
  if (developerDraftLoading.value) return developerDraftBundle.value ? 'Rerunning Developer Design draft' : 'Drafting Developer Design'
  return 'Assistant is working'
})
const assistantOverlayMessage = computed(() => {
  if (draftLoading.value) {
    return 'Studio is asking the assistant to turn selected source context into a reviewed Product Design bundle.'
  }
  if (developerDraftLoading.value) {
    return 'Studio is asking the assistant to turn the locked PM baseline into a reviewed Developer Design bundle.'
  }
  return 'Studio is waiting for the configured assistant model.'
})
const developerPatchPreviewSource = computed(() => {
  if (!developerBaselineText.value) return null
  try {
    return JSON.parse(developerBaselineText.value) as Record<string, unknown>
  } catch {
    return null
  }
})

function replaceDeveloperBundleSection(
  sectionId: string,
  update: (section: DeveloperDesignDraftSection) => DeveloperDesignDraftSection,
) {
  if (!developerDraftBundle.value) return
  developerDraftBundle.value = {
    ...developerDraftBundle.value,
    sections: developerDraftBundle.value.sections.map((section) =>
      section.id === sectionId ? update(section) : section,
    ),
  }
}

async function persistDeveloperBundleState() {
  if (!project.value || !developerDraftBundle.value || readOnlyMode.value) return
  const artifact = await persistAssistantDraftBundle({
    projectId: project.value.id,
    lane: 'dev',
    bundle: developerDraftBundle.value,
    artifactId: developerBundleArtifactId.value,
    context: {
      baseline_locked_at: baseline.value?.locked_at ?? null,
      assistant_runtime: assistantRuntimeContext(projectStore.runtimeStatus),
    },
  })
  developerBundleArtifactId.value = artifact.id
  await refreshArtifacts()
}

async function handleDraftDeveloperDesign(useDeterministic = false, sourceTextOverride?: string | null) {
  if (!project.value) return
  const capturedSourceText = sourceTextOverride?.trim() ?? ''
  if (useDeterministic) {
    if (!canRunDeterministicDraft.value) return
  } else if (!assistantCanDraft.value) {
    return
  }
  if (!developerReady.value) {
    developerDraftError.value = 'Lock Product Design baseline before drafting Developer Design.'
    return
  }
  if (!developerSourceContextReady.value && !capturedSourceText) {
    developerDraftError.value = 'Developer source docs are still loading. Wait for Studio to load all selected developer evidence before drafting Developer Design.'
    return
  }
  developerDraftLoading.value = true
  developerDraftOperation.value = useDeterministic ? 'deterministic' : 'ai'
  developerDraftError.value = null
  const controller = useDeterministic ? null : createAssistantAbortController()
  if (!useDeterministic) {
    resetAssistantProgress('Preparing Developer Design draft request')
  }
  try {
    developerDraftBundle.value = await draftDeveloperDesignBundle({
      projectId: project.value.id,
      projectName: project.value.name,
      baselineText: developerBaselineText.value,
      sourceText: capturedSourceText || developerDraftSourceText.value,
      sourceRequirementsId: lockedRequirements.value?.id,
      sourceShapeId: lockedShape.value?.id,
      useDeterministic,
      serviceTopologyPreference: developerServiceTopologyPreference.value,
      signal: controller?.signal,
      onProgress: useDeterministic ? undefined : recordAssistantProgress,
    })
    if (!useDeterministic) {
      recordAssistantProgress('Draft complete. Preparing review bundle.')
    }
    await persistDeveloperBundleState()
    await safeRecordAssistantAuditEvent({
      event_type: 'draft_created',
      lane: 'dev',
      bundle_artifact_id: developerBundleArtifactId.value,
      baseline_locked_at: baseline.value?.locked_at ?? null,
      section_count: developerDraftBundle.value.sections.length,
      draft_mode: useDeterministic ? 'deterministic' : 'ai',
    })
  } catch (err) {
    developerDraftError.value = isAbortError(err)
      ? 'Assistant draft canceled. No Developer Design draft changes were saved.'
      : err instanceof Error ? err.message : String(err)
  } finally {
    if (controller) clearAssistantAbortController(controller)
    developerDraftLoading.value = false
    developerDraftOperation.value = null
  }
}

async function handleDeterministicDeveloperDesignDraft() {
  await handleDraftDeveloperDesign(true)
}

async function persistDeveloperClarificationAnswers(section: DeveloperDesignDraftSection) {
  await persistDeveloperBundleState()
  await safeRecordAssistantAuditEvent({
    event_type: 'clarification_answers_saved',
    lane: 'dev',
    bundle_artifact_id: developerBundleArtifactId.value,
    section_id: section.id,
    section_title: section.title,
    selected_ids: [...section.selectedIds],
    clarification_question_ids: selectedClarificationAnswers(section)
      .filter((question) => question.answer.length > 0)
      .map((question) => question.question_id),
  })
}

function toggleDeveloperBundleItem(sectionId: string, itemId: string) {
  replaceDeveloperBundleSection(sectionId, (section) => toggleDeveloperSectionSelection(section, itemId))
}

function selectAllDeveloperBundleItems(sectionId: string) {
  replaceDeveloperBundleSection(sectionId, selectAllDeveloperSectionItems)
}

function clearDeveloperBundleItems(sectionId: string) {
  replaceDeveloperBundleSection(sectionId, clearDeveloperSectionSelection)
}

function setDeveloperClarificationAnswer(sectionId: string, questionId: string, value: string) {
  replaceDeveloperBundleSection(sectionId, (section) => ({
    ...section,
    clarificationAnswers: {
      ...(section.clarificationAnswers ?? {}),
      [questionId]: value,
    },
  }))
}

async function saveDeveloperBundleSection(section: DeveloperDesignDraftSection) {
  if (!project.value || readOnlyMode.value || !developerDraftBundle.value) return
  if (isClarificationSection(section)) {
    developerDraftError.value = 'Answer the selected clarification questions and regenerate this section before saving it.'
    return
  }
  savingDeveloperSectionId.value = section.id
  developerDraftError.value = null
  try {
    await saveAcceptedDeveloperDesignSection({
      projectId: project.value.id,
      section,
      notes: developerBaselineText.value,
    })
    await refreshArtifacts()
    replaceDeveloperBundleSection(section.id, (current) => ({ ...current, status: 'saved' }))
    await persistDeveloperBundleState()
    await safeRecordAssistantAuditEvent({
      event_type: 'section_saved',
      lane: 'dev',
      bundle_artifact_id: developerBundleArtifactId.value,
      section_id: section.id,
      section_title: section.title,
      selected_ids: [...section.selectedIds],
    })
  } catch (err) {
    developerDraftError.value = err instanceof Error ? err.message : String(err)
  } finally {
    savingDeveloperSectionId.value = null
  }
}

async function regenerateDeveloperSection(section: DeveloperDesignDraftSection) {
  if (!project.value || !developerDraftBundle.value || !canRegenerateFromClarifications(section)) return
  regeneratingDeveloperSectionId.value = section.id
  developerDraftError.value = null
  try {
    const usedAnswers = section.status === 'failed' ? [] : answeredClarificationContext(section)
    const redrafted = await redraftDeveloperDesignSection({
      projectId: project.value.id,
      section,
      baselineText: sourceTextWithClarificationAnswers(developerDraftBundle.value.baselineText, section),
      sourceText: sourceTextWithClarificationAnswers(developerDraftBundle.value.sourceText ?? developerDraftBundle.value.baselineText, section),
      sourceRequirementsId: lockedRequirements.value?.id,
      sourceShapeId: lockedShape.value?.id,
      serviceTopologyPreference: developerServiceTopologyPreference.value,
    })
    replaceDeveloperBundleSection(section.id, () => ({
      ...redrafted,
      usedClarificationAnswers: usedAnswers,
      error: undefined,
    }))
    await persistDeveloperBundleState()
    await safeRecordAssistantAuditEvent({
      event_type: 'section_regenerated',
      lane: 'dev',
      bundle_artifact_id: developerBundleArtifactId.value,
      section_id: section.id,
      section_title: section.title,
      selected_ids: [...section.selectedIds],
      clarification_question_ids: usedAnswers.map((answer) => answer.questionId),
    })
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    developerDraftError.value = message
    replaceDeveloperBundleSection(section.id, (current) => ({
      ...current,
      status: 'failed',
      error: message,
    }))
    try {
      await persistDeveloperBundleState()
    } catch {
      // Keep the assistant failure visible even if persisting the failed bundle state also fails.
    }
    await safeRecordAssistantAuditEvent({
      event_type: 'section_regeneration_failed',
      lane: 'dev',
      bundle_artifact_id: developerBundleArtifactId.value,
      section_id: section.id,
      section_title: section.title,
      selected_ids: [...section.selectedIds],
      clarification_question_ids: selectedClarificationAnswers(section)
        .filter((question) => question.answer.length > 0)
        .map((question) => question.question_id),
      status: 'failed',
      error: message,
    })
  } finally {
    regeneratingDeveloperSectionId.value = null
  }
}

async function saveAllSelectedDeveloperSections() {
  if (!developerDraftBundle.value) return
  for (const section of developerDraftBundle.value.sections) {
    if (section.status === 'saved' || section.status === 'failed' || isClarificationSection(section) || section.selectedIds.length === 0) continue
    await saveDeveloperBundleSection(section)
    if (developerDraftError.value) return
  }
}

function developerDraftHasBlockingReviewItems(): boolean {
  if (!developerDraftBundle.value) return false
  return developerDraftBundle.value.sections.some((section) =>
    section.status === 'failed'
    || isClarificationSection(section)
    || section.selectedIds.length === 0,
  )
}

function developerDraftNeedsSaving(): boolean {
  if (!developerDraftBundle.value) return false
  return developerDraftBundle.value.sections.some((section) =>
    section.status !== 'saved'
    && section.status !== 'failed'
    && !isClarificationSection(section)
    && section.selectedIds.length > 0,
  )
}
</script>

<template>
  <div class="project-assistant-view">
    <AssistantWorkingOverlay
      :active="assistantOverlayActive"
      :title="assistantOverlayTitle"
      :message="assistantOverlayMessage"
      :progress-items="assistantProgressItems"
      :cancel-disabled="assistantCancelRequested"
      :cancel-label="assistantCancelRequested ? 'Canceling...' : 'Cancel request'"
      detail="This call can take a little while. Studio blocks the assistant page to prevent duplicate drafts while the model response is in flight."
      @cancel="cancelAssistantDraft"
    />

    <div v-if="loading && !project" class="empty-state">Loading project assistant...</div>
    <div v-else-if="error" class="banner banner-error">{{ error }}</div>
    <template v-else-if="project">
      <section class="page-header">
        <div>
          <div class="page-kicker">Project AI Assistant</div>
          <h1>{{ project.name }}</h1>
          <p>
            Use one dedicated assistant surface for this project. Choose the lane explicitly; Studio passes that lane to bounded assistant operations and still saves only reviewed, deterministic project artifacts.
          </p>
        </div>
      </section>

      <div v-if="readOnlyMode" class="banner banner-warning readonly-banner">
        {{ readOnlyReason }}
      </div>
      <div v-if="developerLaneNeedsBaseline" class="banner banner-warning readonly-banner">
        Lock the Product Design baseline before using Developer Guided Mode or Autopilot. Developer Design must draft from approved PM intent, not from a moving product draft.
      </div>

      <section class="assistant-status-panel" :class="{ ready: assistantStatus.ready }">
        <div>
          <div class="page-kicker">Assistant Runtime</div>
          <h2>{{ assistantStatus.label }}</h2>
          <p>{{ assistantStatus.detail }}</p>
        </div>
        <div class="assistant-status-list">
          <div v-for="item in assistantReadinessItems" :key="item.label" class="assistant-status-row">
            <span class="status-dot" :class="{ ready: item.ready }"></span>
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>
      </section>

      <section class="work-mode-switcher">
        <button
          class="work-mode-button"
          :class="{ active: workMode === 'manual' }"
          type="button"
          @click="setWorkMode('manual')"
        >
          <span>Manual</span>
          <strong>Direct deterministic editing</strong>
        </button>
        <button
          class="work-mode-button"
          :class="{ active: workMode === 'guided' }"
          :disabled="!assistantCanDraft || developerLaneNeedsBaseline"
          type="button"
          @click="setWorkMode('guided')"
        >
          <span>Guided Mode</span>
          <strong>Control each section</strong>
        </button>
        <button
          class="work-mode-button operator"
          :class="{ active: workMode === 'autopilot' }"
          :disabled="!assistantCanDraft || developerLaneNeedsBaseline"
          type="button"
          @click="setWorkMode('autopilot')"
        >
          <span>Autopilot Mode</span>
          <strong>Studio completes the draft</strong>
        </button>
      </section>
      <p class="mode-notice">{{ workModeNotice }}</p>

      <section v-if="developerLaneNeedsBaseline" class="panel blocking-state">
        <strong>Developer AI mode needs a locked Product Design baseline</strong>
        <p>Open Developer Overview and lock the Product Design baseline first. After that, add Developer Source Docs and run Developer Autopilot or Guided Mode.</p>
        <button class="btn btn-secondary" type="button" @click="router.push(projectRoute('/developer'))">
          Open Developer Overview
        </button>
      </section>

      <section v-else-if="workMode === 'manual'" class="manual-mode-panel">
        <div>
          <div class="page-kicker">Manual / Deterministic Mode</div>
          <h2>Edit the canonical design directly</h2>
          <p>
            Use this mode when you want full control or when no LLM is configured. Studio still validates every page and blocks generation when required decisions are missing.
          </p>
        </div>
        <div class="manual-action-grid">
          <button
            class="mode-action-card"
            type="button"
            :disabled="draftLoading || !draftSourceReady || !canRunDeterministicDraft"
            @click="handleDeterministicProductDesignDraft"
          >
            <strong>Draft Product Design Deterministically</strong>
            <span>Create a source-derived review bundle without calling an LLM.</span>
          </button>
          <button
            v-if="draftBundle"
            class="mode-action-card"
            type="button"
            :disabled="savingSectionId !== null || readOnlyMode"
            @click="saveAllSelectedSections"
          >
            <strong>Save Deterministic Product Draft</strong>
            <span>Save selected deterministic Product Design sections into canonical artifacts.</span>
          </button>
          <button
            class="mode-action-card"
            type="button"
            :disabled="developerDraftLoading || !developerReady || !canRunDeterministicDraft"
            @click="handleDeterministicDeveloperDesignDraft"
          >
            <strong>Draft Developer Design Deterministically</strong>
            <span>Create a locked-baseline Developer Design bundle without calling an LLM.</span>
          </button>
          <button
            v-if="developerDraftBundle"
            class="mode-action-card"
            type="button"
            :disabled="!canSaveDeveloperDraftBundle"
            @click="saveAllSelectedDeveloperSections"
          >
            <strong>Save Deterministic Developer Draft</strong>
            <span>Save selected deterministic Developer Design sections into reviewed artifacts.</span>
          </button>
          <button class="mode-action-card" type="button" @click="router.push(projectRoute('/pm'))">
            <strong>Open Product Design</strong>
            <span>Work through business intent, actors, requirements, situations, and PM review.</span>
          </button>
          <button class="mode-action-card" type="button" @click="router.push(projectRoute('/developer'))">
            <strong>Open Developer Design</strong>
            <span>Formalize services, capabilities, access, audit, app glue, and generation settings.</span>
          </button>
          <button class="mode-action-card" type="button" @click="router.push(projectRoute('/verification'))">
            <strong>Open Verification</strong>
            <span>Review evidence, simulator output, generated service alignment, and publication readiness.</span>
          </button>
        </div>
      </section>

      <section v-else-if="workMode === 'autopilot'" class="operator-mode-panel">
        <div class="operator-hero">
          <div>
            <div class="page-kicker">Autopilot Mode</div>
            <h2>Let Studio drive the workflow</h2>
            <p>
              Use Autopilot Mode when you want ANIP Studio to complete the project draft for you. Studio inspects project state, picks the next useful step, applies safe deterministic actions, and stops for human decisions that would become contract truth.
            </p>
          </div>
          <div class="operator-hero-actions">
            <button
              class="btn btn-primary"
              type="button"
              :disabled="!operatorPrimaryStep.canRun || draftLoading || developerDraftLoading"
              @click="runOperatorPrimaryStep"
            >
              {{ operatorPrimaryStep.label }}
            </button>
            <button
              v-if="project"
              class="btn btn-secondary"
              type="button"
              @click="router.push(projectRoute('/developer/app-customization'))"
            >
              View App Customization
            </button>
          </div>
        </div>

        <div class="operator-step-card">
          <span class="status-chip ready">Current step</span>
          <h3>{{ operatorPrimaryStep.title }}</h3>
          <p>{{ operatorPrimaryStep.detail }}</p>
          <div v-if="operatorPrimaryStep.why_it_matters" class="operator-task-detail">
            <strong>Why this matters</strong>
            <span>{{ operatorPrimaryStep.why_it_matters }}</span>
          </div>
          <div v-if="operatorPrimaryStep.success_condition" class="operator-task-detail">
            <strong>Done when</strong>
            <span>{{ operatorPrimaryStep.success_condition }}</span>
          </div>
          <p v-if="!operatorPrimaryStep.canRun" class="operator-blocked-copy">
            {{ autopilotSourceEvidenceGate.ready ? 'This step needs assistant runtime and a valid project state before Studio can proceed automatically.' : autopilotSourceEvidenceGate.modeGuidance }}
          </p>
        </div>

        <div v-if="!autopilotSourceEvidenceGate.ready" class="operator-guardrail-card">
          <div>
            <strong>Source evidence guardrail</strong>
            <p>{{ autopilotSourceEvidenceGate.summary }}</p>
            <p>{{ autopilotSourceEvidenceGate.detail }}</p>
          </div>
          <ul v-if="autopilotSourceEvidenceGate.messages.length">
            <li v-for="message in autopilotSourceEvidenceGate.messages" :key="message">{{ message }}</li>
          </ul>
          <div class="draft-actions draft-actions-bottom">
            <button
              v-if="project"
              class="btn btn-secondary"
              type="button"
              @click="router.push(lane === 'dev' ? projectRoute('/developer/source-docs') : projectRoute('/source-docs'))"
            >
              Open Source Docs
            </button>
            <button class="btn btn-secondary" type="button" @click="setWorkMode('guided')">
              Switch to Guided Mode
            </button>
            <button class="btn btn-secondary" type="button" @click="setWorkMode('manual')">
              Switch to Manual Mode
            </button>
          </div>
        </div>

        <section v-if="operatorHandoffSummary" class="operator-summary-card">
          <div class="panel-header">
            <div>
              <h3>Autopilot Handoff Summary</h3>
              <p>
                A compact project snapshot for review: current status, blockers, next action, and recent Autopilot activity.
              </p>
            </div>
            <span class="status-chip" :class="{ ready: operatorSummaryStatusReady }">
              {{ operatorSummaryStatusLabel }}
            </span>
          </div>
          <div class="operator-summary-grid">
            <div>
              <strong>{{ operatorHandoffSummary.counts.complete }}</strong>
              <span>complete</span>
            </div>
            <div>
              <strong>{{ operatorHandoffSummary.counts.ready }}</strong>
              <span>ready</span>
            </div>
            <div>
              <strong>{{ operatorHandoffSummary.counts.blocked }}</strong>
              <span>blocked</span>
            </div>
            <div>
              <strong>{{ operatorHandoffSummary.counts.needs_human_decision }}</strong>
              <span>human decisions</span>
            </div>
          </div>
          <div v-if="operatorHandoffSummary.next_action" class="operator-summary-next">
            <strong>Next action</strong>
            <p>{{ operatorHandoffSummary.next_action.title }}: {{ operatorHandoffSummary.next_action.detail }}</p>
          </div>
          <div v-if="operatorHandoffSummary.blockers.length" class="operator-summary-blockers">
            <strong>Open items</strong>
            <ul>
              <li v-for="item in operatorHandoffSummary.blockers.slice(0, 4)" :key="item.title">
                {{ item.title }}<span v-if="item.requires_human_decision"> · needs review</span>
              </li>
            </ul>
          </div>
          <div class="draft-actions">
            <button class="btn btn-secondary" type="button" :disabled="operatorSummarySaving" @click="saveOperatorHandoffSummary">
              {{ operatorSummarySaving ? 'Saving summary...' : 'Save Summary Artifact' }}
            </button>
            <span v-if="savedOperatorHandoffSummary" class="operator-summary-saved">
              Saved {{ formatStudioTimestamp(savedOperatorHandoffSummary.generated_at) }}
            </span>
          </div>
          <p v-if="operatorSummaryMessage" class="success-copy">{{ operatorSummaryMessage }}</p>
          <p v-if="operatorSummaryError" class="error">{{ operatorSummaryError }}</p>
        </section>

        <section class="operator-decision-queue">
          <div class="panel-header">
            <div>
              <h3>Decision Queue</h3>
              <p>
                Autopilot Mode pulls the next risky design decisions into one list. Use the target page when the decision needs contract or app-glue editing.
              </p>
            </div>
            <span class="status-chip" :class="{ ready: operatorDecisionQueue.length === 0 }">
              {{ operatorDecisionQueue.length ? `${operatorDecisionQueue.length} open` : 'Clear' }}
            </span>
          </div>
          <div v-if="operatorDecisionQueue.length === 0" class="operator-empty-decision">
            No coordination, high-risk, or readiness decisions are currently blocking the Autopilot path.
          </div>
          <div v-else class="operator-decision-list">
            <article
              v-for="item in operatorDecisionQueue"
              :key="item.id"
              class="operator-decision-card"
              :class="`severity-${item.severity}`"
            >
              <div class="operator-decision-header">
                <span>{{ item.source.replace(/_/g, ' ') }}</span>
                <strong>{{ item.severity }}</strong>
              </div>
              <h4>{{ item.title }}</h4>
              <p>{{ item.detail }}</p>
              <div class="operator-decision-guidance">
                <div>
                  <strong>Review target</strong>
                  <span>{{ item.review_target }}</span>
                </div>
                <div>
                  <strong>Why Studio stopped</strong>
                  <span>{{ item.why_human }}</span>
                </div>
                <div>
                  <strong>Done when</strong>
                  <span>{{ item.done_when }}</span>
                </div>
              </div>
              <p class="operator-decision-recommendation">{{ item.recommendation }}</p>
              <small v-if="item.affected_label">{{ item.affected_label }}</small>
              <div v-if="item.actions.length" class="operator-decision-actions">
                <button
                  v-for="action in item.actions"
                  :key="action.id"
                  class="btn btn-secondary"
                  type="button"
                  :disabled="operatorDecisionApplyingId === `${item.id}:${action.id}`"
                  :title="action.detail"
                  @click="applyOperatorDecision(item, action)"
                >
                  {{ operatorDecisionApplyingId === `${item.id}:${action.id}` ? 'Saving...' : action.label }}
                </button>
              </div>
              <button
                v-if="item.route"
                class="btn btn-secondary"
                type="button"
                @click="router.push(item.route)"
              >
                {{ item.action_label }}
              </button>
            </article>
          </div>
          <p v-if="operatorDecisionMessage" class="success-copy">{{ operatorDecisionMessage }}</p>
          <p v-if="operatorDecisionError" class="error">{{ operatorDecisionError }}</p>
        </section>

        <details class="operator-task-list">
          <summary>Show workflow plan</summary>
          <div class="operator-task-list-body">
            <article
              v-for="task in operatorTasks"
              :key="task.id"
              class="operator-task-row"
              :class="`state-${task.state}`"
            >
              <strong>{{ task.title }}</strong>
              <span>{{ task.state }}</span>
              <p>{{ task.success_condition }}</p>
            </article>
          </div>
        </details>

        <section class="operator-activity-log">
          <div class="panel-header">
            <h3>Autopilot Activity</h3>
            <span class="status-chip" :class="{ ready: operatorActivities.length > 0 }">
              {{ operatorActivities.length ? `${operatorActivities.length} event${operatorActivities.length === 1 ? '' : 's'}` : 'No activity yet' }}
            </span>
          </div>
          <p v-if="operatorActivities.length === 0">
            Actions taken in Autopilot Mode will appear here so users can inspect what Studio did and why.
          </p>
          <div v-else class="operator-activity-list">
            <article
              v-for="activity in operatorActivities"
              :key="activity.id"
              class="operator-activity-row"
              :class="`outcome-${activity.outcome}`"
            >
              <strong>{{ activity.title }}</strong>
              <span>{{ formatStudioTimestamp(activity.created_at) }}</span>
              <p>{{ activity.detail }}</p>
            </article>
          </div>
        </section>

        <div class="operator-status-grid">
          <article
            v-for="item in operatorStatusCards"
            :key="item.label"
            class="operator-status-card"
            :class="{ ready: item.ready }"
          >
            <span class="status-dot" :class="{ ready: item.ready }"></span>
            <strong>{{ item.label }}</strong>
            <em>{{ item.status }}</em>
            <p>{{ item.detail }}</p>
          </article>
        </div>

        <div
          v-if="(lane === 'pm' && draftBundle) || (lane === 'dev' && developerDraftBundle)"
          class="operator-review-card"
        >
          <strong>Review still required</strong>
          <p>
            Studio has a {{ lane === 'dev' ? 'Developer Design' : 'Product Design' }} draft ready. Autopilot Mode keeps the detailed cards hidden by default, but saved artifacts still require review.
          </p>
          <div class="draft-actions draft-actions-bottom">
            <button v-if="lane === 'pm' && draftBundle" class="btn btn-primary" type="button" @click="setWorkMode('guided')">
              Review Product Draft
            </button>
            <button v-if="lane === 'dev' && developerDraftBundle" class="btn btn-primary" type="button" @click="setWorkMode('guided')">
              Review Developer Draft
            </button>
          </div>
        </div>
      </section>

      <section v-else class="lane-switcher">
        <button class="lane-button" :class="{ active: lane === 'pm' }" @click="setLane('pm')">
          <span>PM Lane</span>
          <strong>Draft Product Design from source docs</strong>
        </button>
        <button class="lane-button" :class="{ active: lane === 'dev' }" @click="setLane('dev')">
          <span>Developer Lane</span>
          <strong>Draft Developer Design from locked baseline</strong>
        </button>
      </section>

      <section v-if="workMode === 'guided' && lane === 'pm'" class="assistant-grid">
        <article class="panel source-panel">
          <div class="panel-header">
            <h2>Source Context</h2>
            <span class="status-chip" :class="{ ready: draftSourceReady }">
              {{ draftSourceReady ? 'Source ready' : 'Select source' }}
            </span>
          </div>
          <p class="panel-copy">
            {{ sourceContextCopy }}
          </p>
          <div v-if="assistantDocuments.length === 0" class="blocking-state">
            <strong>{{ sourceMissingTitle }}</strong>
            <p>{{ sourceMissingCopy }}</p>
            <button class="btn btn-secondary" @click="router.push(projectRoute('/source-docs'))">
              Open Source Docs
            </button>
          </div>
          <div v-else class="source-selector">
            <div class="source-mode-row">
              <button
                class="btn"
                :class="sourceSelectionMode === 'all' ? 'btn-primary' : 'btn-secondary'"
                type="button"
                @click="useAllSourceDocuments"
              >
                Use All Sources
              </button>
              <button
                class="btn"
                :class="sourceSelectionMode === 'selected' ? 'btn-primary' : 'btn-secondary'"
                type="button"
                @click="useSelectedSourceDocuments"
              >
                Select Sources
              </button>
              <span class="source-selection-summary">{{ sourceSelectionSummary }}</span>
            </div>
            <div v-if="sourceSelectionMode === 'selected'" class="source-checkbox-list">
              <div class="source-list-actions">
                <button class="source-action-btn" type="button" @click="selectAllSourceDocuments">Select all</button>
                <button class="source-action-btn" type="button" @click="clearSelectedSourceDocuments">Clear</button>
              </div>
            </div>
          </div>
          <div v-if="assistantDocuments.length" class="source-document-table" :class="{ selectable: sourceSelectionMode === 'selected' }">
            <div class="source-document-table-header">
              <span v-if="sourceSelectionMode === 'selected'">Use</span>
              <span>Source</span>
              <span>Kind</span>
              <span>Updated</span>
            </div>
            <label
              v-for="document in assistantDocuments"
              :key="document.id"
              class="source-document-row"
              :class="{ active: activeSourceDocumentIds.includes(document.id), muted: sourceSelectionMode === 'selected' && !activeSourceDocumentIds.includes(document.id) }"
            >
              <span v-if="sourceSelectionMode === 'selected'" class="source-document-check">
                <input v-model="selectedDocumentIds" type="checkbox" :value="document.id" />
              </span>
              <span class="source-document-title">
                <strong>{{ document.title }}</strong>
                <small>{{ document.filename }}</small>
              </span>
              <span>{{ sourceDocumentKindLabel(document.kind) }}</span>
              <span>{{ formatStudioTimestamp(document.updated_at) }}</span>
            </label>
            <div v-if="sourceSelectionMode === 'selected' && selectedSourceCount === 0" class="source-empty-selection">
              Select at least one document before drafting, or switch back to Use All Sources.
            </div>
          </div>
          <div v-if="governedFrontingProject" class="fronting-readiness">
            <div class="fronting-readiness-item" :class="{ ready: frontingIntentReady }">
              <span class="status-dot" :class="{ ready: frontingIntentReady }"></span>
              <strong>Fronting intent</strong>
              <span>{{ frontingIntentReady ? 'available' : 'needed' }}</span>
            </div>
            <div class="fronting-readiness-item" :class="{ ready: frontingIntegrationReady }">
              <span class="status-dot" :class="{ ready: frontingIntegrationReady }"></span>
              <strong>Integration evidence</strong>
              <span>{{ frontingIntegrationReady ? 'available' : 'needed' }}</span>
            </div>
          </div>
          <div class="topology-controls">
            <div>
              <strong>Service topology for AI draft</strong>
              <p>Optional generic constraint. Use it when the desired deployable service count is a design decision, not something the assistant should infer freely.</p>
            </div>
            <label class="field compact-field">
              <span>Granularity</span>
              <select v-model="productServiceGranularity" class="form-input">
                <option value="coarse">Coarse</option>
                <option value="balanced">Balanced</option>
                <option value="fine">Fine</option>
                <option value="source_defined">Source-defined</option>
              </select>
            </label>
            <label class="field compact-field">
              <span>Target service count</span>
              <input
                v-model.number="productTargetServiceCount"
                class="form-input"
                type="number"
                min="1"
                max="20"
                placeholder="Not set"
              />
            </label>
          </div>
          <div v-if="draftSourceText" class="source-quality-card" :class="`quality-${sourceQuality.status}`">
            <div class="source-quality-header">
              <div>
                <strong>{{ sourceQualityTitle }}</strong>
                <p>{{ sourceQuality.summary }}</p>
              </div>
              <span>{{ sourceQuality.score }}%</span>
            </div>
            <p class="quality-note">
              {{ sourceQualityNote }}
            </p>
            <div class="quality-criteria">
              <div
                v-for="criterion in sourceQuality.criteria"
                :key="criterion.id"
                class="quality-row"
                :class="{ ready: criterion.met }"
              >
                <span class="status-dot" :class="{ ready: criterion.met }"></span>
                <span>{{ criterion.label }}</span>
              </div>
            </div>
            <div v-if="sourceQuality.weakAreas.length" class="quality-weak-areas">
              <strong>Improve these weak areas</strong>
              <ul>
                <li v-for="area in sourceQuality.weakAreas" :key="area.id">{{ area.improvement }}</li>
              </ul>
            </div>
          </div>
          <div v-if="previewError" class="banner banner-warning">{{ previewError }}</div>
          <div v-else-if="previewLoading" class="empty-state">Loading selected source previews...</div>
          <pre v-else-if="selectedSourceDocuments.length" class="preview-content">{{ previewContent || 'No readable preview for selected source documents.' }}</pre>
        </article>

        <article class="panel draft-panel">
          <div class="panel-header">
            <div>
              <h2>Draft Product Design</h2>
            </div>
            <span class="status-chip" :class="{ ready: draftSourceReady }">
              {{ draftSourceReady ? 'Source ready' : 'Select a readable source doc' }}
            </span>
          </div>
          <p class="panel-copy panel-copy-below-header">
            The assistant drafts a coherent bundle first, then asks only targeted questions for material missing decisions. Nothing is saved until you accept sections.
          </p>
          <div class="draft-context">
            <span>{{ draftableSourceLabel }}</span>
          </div>
          <div v-if="draftError" class="banner banner-error">{{ draftError }}</div>
          <div v-if="productDraftSourceChanged" class="banner banner-warning">
            Source context has changed since this draft was created. Rerun the draft to incorporate newly uploaded or newly selected documents.
          </div>
          <div v-if="productDraftFailedSections.length" class="banner banner-warning">
            AI drafting failed for {{ productDraftFailedSections.length }} section{{ productDraftFailedSections.length === 1 ? '' : 's' }}. Review the error, fix assistant configuration, or intentionally use deterministic drafting instead.
          </div>
          <div v-if="!draftSourceReady && !draftBundle" class="blocking-state">
            <strong>{{ draftMissingTitle }}</strong>
            <p>{{ draftMissingCopy }}</p>
          </div>

          <div v-if="draftBundle" class="draft-results">
            <div class="draft-summary">
              <h3>{{ draftBundle.title }}</h3>
              <p>{{ draftBundle.summary }}</p>
              <p class="draft-meta">
                Latest draft persisted{{ productBundleArtifactId ? ` as ${productBundleArtifactId}` : '' }}.
              </p>
            </div>

            <div v-if="draftQuestions.length" class="clarification-batch">
              <strong>Clarifications worth resolving</strong>
              <p>These are the shortest blocking questions found across the draft.</p>
              <ul>
                <li v-for="question in draftQuestions" :key="question">{{ question }}</li>
              </ul>
            </div>

            <div class="draft-section-grid">
              <AssistantDraftSectionCard
                v-for="section in draftBundle.sections"
                :key="section.id"
                :section="section"
                :item-count="sectionItemCount(section)"
                :selected-count="selectedSectionItemCount(section)"
                :patch-preview-source="productPatchPreviewSource(section)"
                :save-busy="savingSectionId !== null"
                :saving-current="savingSectionId === section.id"
                :regenerate-busy="regeneratingSectionId !== null"
                :regenerating-current="regeneratingSectionId === section.id"
                :read-only="readOnlyMode"
                :can-regenerate="canRegenerateFromClarifications(section)"
                clarification-placeholder="Type the business decision that answers this question."
                @select-all="selectAllBundleItems(section.id)"
                @clear-selection="clearBundleItems(section.id)"
                @toggle-item="toggleBundleItem(section.id, $event)"
                @update-clarification-answer="setProductClarificationAnswer(section.id, $event.questionId, $event.value)"
                @persist-answers="persistProductClarificationAnswers(section)"
                @regenerate="regenerateProductSection(section)"
                @save="saveBundleSection(section)"
              />
            </div>
          </div>
          <div class="draft-actions draft-actions-bottom">
            <button class="btn btn-primary" :disabled="draftLoading || !draftSourceReady || !assistantCanDraft" @click="handleDraftProductDesign(false)">
              {{ productDraftActionLabel }}
            </button>
            <button
              v-if="canOfferDeterministicProductDraft"
              class="btn btn-secondary"
              :disabled="draftLoading || !draftSourceReady || !canRunDeterministicDraft"
              @click="handleDeterministicProductDesignDraft"
            >
              Use Deterministic Draft Instead
            </button>
            <button
              v-if="draftBundle"
              class="btn btn-secondary"
              :disabled="savingSectionId !== null || readOnlyMode"
              @click="saveAllSelectedSections"
            >
              Save All Selected
            </button>
            <button
              v-if="draftBundle"
              class="btn btn-secondary"
              :disabled="discardingBundle || readOnlyMode"
              @click="discardCurrentBundle"
            >
              {{ discardingBundle ? 'Discarding...' : 'Discard Draft' }}
            </button>
          </div>
        </article>
      </section>

      <section v-else-if="workMode === 'guided'" class="assistant-grid developer-assistant-grid">
        <article class="panel source-panel">
          <div class="panel-header">
            <h2>Locked Baseline Context</h2>
            <span class="status-chip" :class="{ ready: developerReady }">
              {{ developerReady ? 'Ready' : 'Needs baseline' }}
            </span>
          </div>
          <p class="panel-copy">
            The developer lane uses the locked PM baseline. Studio does not ask developers to restate PM intent already captured in Product Design.
          </p>
          <div class="source-meta">
            <div><strong>Requirements:</strong> {{ lockedRequirements?.title || currentRequirements?.title || 'Missing' }}</div>
            <div><strong>Scenarios:</strong> {{ currentScenarios.length }}</div>
            <div><strong>Service design:</strong> {{ lockedShape?.title || currentShape?.title || 'Missing' }}</div>
            <div><strong>Locked services:</strong> {{ lockedShapeServiceCount || 'Missing' }}</div>
            <div><strong>Developer source docs:</strong> {{ assistantDocuments.length }}</div>
            <div><strong>Baseline:</strong> {{ baseline ? formatStudioTimestamp(baseline.locked_at) : 'Not locked' }}</div>
          </div>
          <div v-if="assistantDocuments.length === 0" class="blocking-state">
            <strong>Developer source docs are missing</strong>
            <p>
              Developer Autopilot can still ask targeted questions, but input contracts cannot be locked until implementation evidence or reviewed developer answers exist.
            </p>
            <button class="btn btn-secondary" @click="router.push(projectRoute('/developer/source-docs'))">
              Open Developer Source Docs
            </button>
          </div>
          <div v-else class="source-document-table developer-source-table">
            <div class="source-document-table-header">
              <span>Developer source</span>
              <span>Kind</span>
              <span>Updated</span>
            </div>
            <label
              v-for="document in assistantDocuments"
              :key="document.id"
              class="source-document-row active"
            >
              <span class="source-document-title">
                <strong>{{ document.title }}</strong>
                <small>{{ document.filename }}</small>
              </span>
              <span>{{ sourceDocumentKindLabel(document.kind) }}</span>
              <span>{{ formatStudioTimestamp(document.updated_at) }}</span>
            </label>
          </div>
          <div v-if="lockedShape" class="topology-controls topology-note">
            <strong>Developer topology is locked</strong>
            <p>AI Developer Design preserves the locked Product Design service count and boundaries unless the baseline is intentionally changed.</p>
          </div>
          <button class="btn btn-secondary" @click="router.push(projectRoute('/developer'))">
            Open Developer Overview
          </button>
        </article>

        <article class="panel draft-panel">
          <div class="panel-header">
            <div>
              <h2>{{ developerContinuationState?.title ?? 'Draft Developer Design' }}</h2>
              <p class="panel-copy">
                {{ developerContinuationState?.copy ?? 'Draft a coherent Developer Design bundle from the locked PM baseline. Accepted outputs are saved as assistant review artifacts until deterministic Developer Definition save/generation consumes them.' }}
              </p>
            </div>
          </div>
          <div class="draft-context">
            <span class="status-chip" :class="{ ready: developerReady }">
              {{ developerReady ? 'Locked baseline ready' : 'Lock Product Design baseline first' }}
            </span>
            <span v-if="developerDesignReviewSaved" class="status-chip ready">Developer Design saved</span>
            <span v-if="developerDefinitionSaved" class="status-chip ready">Developer Definition saved</span>
            <span v-if="developerCoverageSaved" class="status-chip ready">Coverage saved</span>
            <span>{{ lockedRequirements?.title || 'No locked requirements' }}</span>
          </div>
          <div v-if="developerContinuationState" class="continuation-state">
            <strong>{{ developerContinuationState.title }}</strong>
            <p>{{ developerContinuationState.copy }}</p>
            <div class="continuation-metrics">
              <span v-if="developerReadinessFindingCount">Readiness findings: {{ developerReadinessFindingCount }}</span>
              <span v-if="developerHighRiskUnresolvedCount">High-risk unresolved: {{ developerHighRiskUnresolvedCount }}</span>
            </div>
          </div>
          <div v-if="developerDraftError" class="banner banner-error">{{ developerDraftError }}</div>
          <div v-if="developerDraftBaselineChanged" class="banner banner-warning">
            Locked baseline context has changed since this developer draft was created. Rerun the draft before saving or generating downstream definitions.
          </div>
          <div v-if="developerDraftFailedSections.length" class="banner banner-warning">
            AI drafting failed for {{ developerDraftFailedSections.length }} section{{ developerDraftFailedSections.length === 1 ? '' : 's' }}. Review the error, fix assistant configuration, or intentionally use deterministic drafting instead.
          </div>
          <div v-if="!developerReady && !developerDraftBundle" class="blocking-state">
            <strong>Developer AI mode needs a locked PM baseline</strong>
            <p>Lock Product Design first so the assistant drafts from approved PM intent instead of asking developers to reconstruct it.</p>
            <button class="btn btn-secondary" @click="router.push(projectRoute('/developer'))">
              Open Developer Overview
            </button>
          </div>

          <div v-if="developerDraftBundle" class="draft-results">
            <div class="draft-summary">
              <h3>{{ developerDraftBundle.title }}</h3>
              <p>{{ developerDraftBundle.summary }}</p>
              <p class="draft-meta">
                Latest draft persisted{{ developerBundleArtifactId ? ` as ${developerBundleArtifactId}` : '' }}.
              </p>
            </div>

            <div v-if="developerDraftQuestions.length" class="clarification-batch">
              <strong>Clarifications worth resolving</strong>
              <p>These are the shortest implementation-grade questions found across the developer draft.</p>
              <ul>
                <li v-for="question in developerDraftQuestions" :key="question">{{ question }}</li>
              </ul>
            </div>

            <div class="draft-section-grid">
              <AssistantDraftSectionCard
                v-for="section in developerDraftBundle.sections"
                :key="section.id"
                :section="section"
                :item-count="developerSectionItemCount(section)"
                :selected-count="selectedDeveloperSectionItemCount(section)"
                :patch-preview-source="developerPatchPreviewSource"
                :save-busy="savingDeveloperSectionId !== null"
                :saving-current="savingDeveloperSectionId === section.id"
                :regenerate-busy="regeneratingDeveloperSectionId !== null"
                :regenerating-current="regeneratingDeveloperSectionId === section.id"
                :read-only="readOnlyMode"
                :can-regenerate="canRegenerateFromClarifications(section)"
                clarification-placeholder="Type the implementation decision that answers this question."
                @select-all="selectAllDeveloperBundleItems(section.id)"
                @clear-selection="clearDeveloperBundleItems(section.id)"
                @toggle-item="toggleDeveloperBundleItem(section.id, $event)"
                @update-clarification-answer="setDeveloperClarificationAnswer(section.id, $event.questionId, $event.value)"
                @persist-answers="persistDeveloperClarificationAnswers(section)"
                @regenerate="regenerateDeveloperSection(section)"
                @save="saveDeveloperBundleSection(section)"
              />
            </div>
          </div>
          <div class="draft-actions draft-actions-bottom">
            <button
              v-if="developerContinuationState"
              class="btn btn-primary"
              type="button"
              @click="router.push(developerContinuationState.path)"
            >
              {{ developerContinuationState.label }}
            </button>
            <button
              class="btn"
              :class="developerContinuationState ? 'btn-secondary' : 'btn-primary'"
              :disabled="developerDraftLoading || !developerReady || !assistantCanDraft || !developerSourceContextReady"
              @click="handleDraftDeveloperDesign(false)"
            >
              {{ developerDraftActionLabel }}
            </button>
            <button
              v-if="canOfferDeterministicDeveloperDraft"
              class="btn btn-secondary"
              :disabled="developerDraftLoading || !developerReady || !canRunDeterministicDraft"
              @click="handleDeterministicDeveloperDesignDraft"
            >
              Use Deterministic Draft Instead
            </button>
            <button
              v-if="developerDraftBundle"
              class="btn btn-secondary"
              :disabled="!canSaveDeveloperDraftBundle"
              @click="saveAllSelectedDeveloperSections"
            >
              Save All Selected
            </button>
            <button
              v-if="developerDraftBundle"
              class="btn btn-secondary"
              :disabled="discardingBundle || readOnlyMode"
              @click="discardCurrentBundle"
            >
              {{ discardingBundle ? 'Discarding...' : 'Discard Draft' }}
            </button>
            <button
              v-if="developerDraftBundle"
              class="btn btn-secondary"
              type="button"
              @click="router.push(projectRoute('/developer/app-glue'))"
            >
              Run Simulator / Readiness Loop
            </button>
          </div>
        </article>
      </section>
    </template>
  </div>
</template>

<style scoped>
.project-assistant-view {
  width: 100%;
  max-width: none;
  padding: 2rem;
}

.page-header {
  margin-bottom: 1.75rem;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.page-header h1 {
  margin: 0.2rem 0 0.5rem;
  color: var(--text-primary);
  font-size: 32px;
  line-height: 1.15;
  font-weight: 700;
}

.page-header p {
  max-width: 88ch;
  margin: 0;
  line-height: 1.6;
}

.header-config-btn {
  flex-shrink: 0;
}

.page-header p,
.page-kicker,
.empty-state,
.panel-copy,
.source-meta,
.proposal-body,
.proposal-item small,
.error-copy {
  color: var(--text-secondary);
}

.panel-copy {
  margin: 0.85rem 0 0;
  line-height: 1.6;
}

.panel-copy-below-header {
  margin-top: -0.35rem;
  margin-bottom: 1rem;
  max-width: 78ch;
}

.page-kicker {
  text-transform: uppercase;
  font-size: 12px;
  letter-spacing: 0.08em;
  color: var(--text-muted);
  margin-bottom: 0.4rem;
}

.readonly-banner {
  margin-bottom: 1rem;
}

.assistant-status-panel {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(280px, 0.9fr);
  gap: 1.05rem;
  align-items: start;
  margin-bottom: 1.05rem;
  padding: 1.35rem;
  border: 1px solid rgba(251, 191, 36, 0.24);
  border-radius: 22px;
  background:
    linear-gradient(135deg, rgba(251, 191, 36, 0.12), rgba(15, 23, 42, 0.46));
}

.assistant-status-panel.ready {
  border-color: rgba(34, 197, 94, 0.24);
  background: linear-gradient(135deg, rgba(34, 197, 94, 0.09), rgba(15, 23, 42, 0.42));
}

.assistant-status-panel h2 {
  margin: 0.25rem 0 0.45rem;
  color: var(--text-primary);
  font-size: 24px;
  line-height: 1.2;
  font-weight: 800;
}

.assistant-status-panel p {
  margin: 0;
  color: var(--text-secondary);
}

.assistant-status-list {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.assistant-status-row {
  display: grid;
  grid-template-columns: auto minmax(90px, 0.7fr) minmax(120px, 1fr);
  gap: 0.5rem;
  align-items: center;
  color: var(--text-secondary);
  font-size: 13px;
}

.assistant-status-row strong {
  color: var(--text-primary);
  font-weight: 800;
  text-align: right;
}

.status-dot {
  width: 0.55rem;
  height: 0.55rem;
  border-radius: 999px;
  background: rgba(248, 113, 113, 0.95);
}

.status-dot.ready {
  background: rgba(34, 197, 94, 0.95);
}

.work-mode-switcher {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1.05rem;
  margin-bottom: 0.65rem;
}

.work-mode-button {
  display: grid;
  gap: 0.42rem;
  text-align: left;
  padding: 1rem;
  border: 1px solid var(--surface-border-card);
  border-radius: 18px;
  color: var(--text-primary);
  background:
    linear-gradient(180deg, rgba(15, 23, 42, 0.64), rgba(15, 23, 42, 0.44));
  cursor: pointer;
  font: inherit;
}

.work-mode-button:disabled {
  cursor: not-allowed;
  opacity: 0.52;
}

.work-mode-button:not(:disabled):hover {
  border-color: rgba(147, 197, 253, 0.36);
  background:
    linear-gradient(180deg, rgba(30, 64, 175, 0.22), rgba(15, 23, 42, 0.52));
}

.work-mode-button span {
  color: var(--text-secondary);
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.work-mode-button.active {
  border-color: rgba(96, 165, 250, 0.5);
  background:
    linear-gradient(135deg, rgba(30, 64, 175, 0.3), rgba(15, 23, 42, 0.56));
}

.work-mode-button.operator.active {
  border-color: rgba(56, 189, 248, 0.52);
  background:
    radial-gradient(circle at top left, rgba(56, 189, 248, 0.2), transparent 46%),
    linear-gradient(135deg, rgba(12, 74, 110, 0.28), rgba(15, 23, 42, 0.56));
}

.mode-notice {
  margin: 0 0 1.05rem;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 700;
}

.manual-mode-panel,
.operator-mode-panel {
  display: grid;
  gap: 1.05rem;
  border: 1px solid var(--surface-border-panel);
  border-radius: 22px;
  padding: 1.35rem;
  background:
    radial-gradient(circle at top left, rgba(96, 165, 250, 0.1), transparent 38%),
    var(--surface-depth-panel);
}

.manual-mode-panel h2,
.operator-mode-panel h2 {
  margin: 0.2rem 0 0.5rem;
  color: var(--text-primary);
  font-size: 26px;
}

.manual-mode-panel p,
.operator-mode-panel p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.6;
}

.manual-action-grid,
.operator-status-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.9rem;
}

.mode-action-card,
.operator-status-card {
  display: grid;
  gap: 0.55rem;
  text-align: left;
  border: 1px solid var(--surface-border-card);
  border-radius: 16px;
  padding: 1rem;
  background: var(--surface-depth-card);
  color: inherit;
}

.mode-action-card {
  cursor: pointer;
}

.mode-action-card:hover {
  border-color: rgba(96, 165, 250, 0.38);
  background: rgba(30, 64, 175, 0.18);
}

.mode-action-card span,
.operator-status-card p {
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.5;
}

.operator-hero {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
}

.operator-hero .btn {
  flex-shrink: 0;
}

.operator-hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem;
  justify-content: flex-end;
}

.operator-step-card,
.operator-review-card {
  display: grid;
  gap: 0.6rem;
  border: 1px solid rgba(56, 189, 248, 0.24);
  border-radius: 18px;
  padding: 1rem;
  background:
    linear-gradient(135deg, rgba(12, 74, 110, 0.16), rgba(15, 23, 42, 0.32));
}

.operator-step-card h3 {
  margin: 0;
  color: var(--text-primary);
  font-size: 21px;
}

.operator-guardrail-card {
  display: grid;
  gap: 0.75rem;
  border: 1px solid rgba(251, 191, 36, 0.3);
  border-radius: 18px;
  padding: 1rem;
  background:
    radial-gradient(circle at top left, rgba(251, 191, 36, 0.14), transparent 42%),
    rgba(69, 26, 3, 0.18);
}

.operator-guardrail-card strong {
  color: #fde68a;
}

.operator-guardrail-card p {
  margin: 0.2rem 0 0;
  color: var(--text-secondary);
}

.operator-guardrail-card ul {
  margin: 0;
  padding-left: 1.15rem;
  color: var(--text-secondary);
}

.operator-summary-card {
  display: grid;
  gap: 0.85rem;
  border: 1px solid rgba(125, 211, 252, 0.2);
  border-radius: 18px;
  padding: 1rem;
  background:
    radial-gradient(circle at top right, rgba(56, 189, 248, 0.11), transparent 42%),
    rgba(15, 23, 42, 0.2);
}

.operator-summary-card .panel-header {
  margin-bottom: 0;
}

.operator-summary-card h3 {
  margin: 0 0 0.25rem;
  color: var(--text-primary);
}

.operator-summary-card .panel-header p {
  font-size: 13px;
}

.operator-summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.65rem;
}

.operator-summary-grid div {
  display: grid;
  gap: 0.2rem;
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  padding: 0.75rem;
  background: var(--surface-depth-card);
}

.operator-summary-grid strong {
  color: var(--text-primary);
  font-size: 22px;
}

.operator-summary-grid span,
.operator-summary-saved {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.operator-summary-next,
.operator-summary-blockers {
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 14px;
  padding: 0.75rem;
  background: rgba(15, 23, 42, 0.22);
}

.operator-summary-next strong,
.operator-summary-blockers strong {
  display: block;
  margin-bottom: 0.3rem;
  color: #bfdbfe;
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.operator-summary-blockers ul {
  margin: 0;
  padding-left: 1.15rem;
  color: var(--text-secondary);
}

.operator-summary-blockers li + li {
  margin-top: 0.25rem;
}

.operator-summary-blockers span {
  color: #fde68a;
  font-weight: 800;
}

.operator-decision-queue {
  display: grid;
  gap: 0.85rem;
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 18px;
  padding: 1rem;
  background: rgba(15, 23, 42, 0.18);
}

.operator-decision-queue .panel-header {
  margin-bottom: 0;
}

.operator-decision-queue h3 {
  margin: 0 0 0.25rem;
  color: var(--text-primary);
}

.operator-decision-queue .panel-header p {
  font-size: 13px;
}

.operator-empty-decision {
  border: 1px solid rgba(34, 197, 94, 0.22);
  border-radius: 14px;
  padding: 0.8rem;
  color: #bbf7d0;
  background: rgba(22, 101, 52, 0.12);
  font-weight: 800;
}

.operator-decision-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 0.75rem;
}

.operator-decision-card {
  display: grid;
  gap: 0.58rem;
  border: 1px solid var(--surface-border-card);
  border-left: 4px solid rgba(148, 163, 184, 0.72);
  border-radius: 14px;
  padding: 0.85rem;
  background: var(--surface-depth-card);
}

.operator-decision-card.severity-blocker {
  border-left-color: #ef4444;
}

.operator-decision-card.severity-warning {
  border-left-color: #f59e0b;
}

.operator-decision-card.severity-info {
  border-left-color: #60a5fa;
}

.operator-decision-header {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  align-items: center;
}

.operator-decision-header span,
.operator-decision-header strong,
.operator-decision-card small {
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.operator-decision-card h4 {
  margin: 0;
  color: var(--text-primary);
  font-size: 16px;
}

.operator-decision-card p {
  font-size: 13px;
}

.operator-decision-guidance {
  display: grid;
  gap: 0.42rem;
  padding: 0.65rem;
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.24);
}

.operator-decision-guidance div {
  display: grid;
  gap: 0.14rem;
}

.operator-decision-guidance strong {
  color: var(--text-primary);
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.operator-decision-guidance span {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.45;
}

.operator-decision-recommendation {
  color: #bfdbfe !important;
  font-weight: 700;
}

.operator-decision-card .btn {
  justify-self: start;
}

.operator-decision-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}

.operator-decision-actions .btn {
  padding: 0.42rem 0.65rem;
  font-size: 12px;
}

.operator-blocked-copy {
  color: #fde68a !important;
  font-weight: 800;
}

.operator-task-detail {
  display: grid;
  gap: 0.24rem;
  border: 1px solid rgba(125, 211, 252, 0.16);
  border-radius: 12px;
  padding: 0.65rem;
  background: rgba(15, 23, 42, 0.22);
}

.operator-task-detail strong {
  color: #bfdbfe;
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.operator-task-detail span {
  color: var(--text-secondary);
  line-height: 1.5;
}

.operator-task-list {
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 16px;
  padding: 0.85rem;
  background: rgba(15, 23, 42, 0.18);
}

.operator-task-list > summary {
  cursor: pointer;
  color: #bfdbfe;
  font-weight: 900;
}

.operator-task-list-body {
  display: grid;
  gap: 0.65rem;
  margin-top: 0.85rem;
}

.operator-task-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 0.45rem 0.75rem;
  border: 1px solid var(--surface-border-card);
  border-radius: 12px;
  padding: 0.75rem;
  background: var(--surface-depth-card);
}

.operator-task-row p {
  grid-column: 1 / -1;
  font-size: 13px;
}

.operator-task-row span {
  border-radius: 999px;
  padding: 0.2rem 0.52rem;
  background: rgba(148, 163, 184, 0.14);
  color: var(--text-secondary);
  font-size: 11px;
  font-weight: 900;
  text-transform: uppercase;
}

.operator-task-row.state-ready span {
  background: rgba(59, 130, 246, 0.18);
  color: #bfdbfe;
}

.operator-task-row.state-complete span {
  background: rgba(34, 197, 94, 0.16);
  color: #bbf7d0;
}

.operator-task-row.state-blocked span {
  background: rgba(251, 191, 36, 0.16);
  color: #fde68a;
}

.operator-activity-log {
  display: grid;
  gap: 0.8rem;
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 18px;
  padding: 1rem;
  background: rgba(15, 23, 42, 0.18);
}

.operator-activity-log .panel-header {
  margin-bottom: 0;
}

.operator-activity-log h3 {
  margin: 0;
  color: var(--text-primary);
}

.operator-activity-list {
  display: grid;
  gap: 0.62rem;
}

.operator-activity-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 0.3rem 0.75rem;
  border: 1px solid var(--surface-border-card);
  border-left: 4px solid rgba(96, 165, 250, 0.64);
  border-radius: 12px;
  padding: 0.72rem;
  background: var(--surface-depth-card);
}

.operator-activity-row.outcome-needs_review {
  border-left-color: #f59e0b;
}

.operator-activity-row.outcome-blocked {
  border-left-color: #ef4444;
}

.operator-activity-row.outcome-completed {
  border-left-color: #22c55e;
}

.operator-activity-row span {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 800;
}

.operator-activity-row p {
  grid-column: 1 / -1;
  font-size: 13px;
}

.operator-status-card {
  position: relative;
  border-color: rgba(251, 191, 36, 0.26);
}

.operator-status-card.ready {
  border-color: rgba(34, 197, 94, 0.24);
  background: rgba(20, 83, 45, 0.12);
}

.operator-status-card em {
  color: var(--text-primary);
  font-style: normal;
  font-weight: 900;
}

.lane-switcher {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1.05rem;
  margin-bottom: 1.05rem;
}

.lane-button {
  display: grid;
  gap: 0.45rem;
  text-align: left;
  padding: 1.1rem;
  border: 1px solid var(--surface-border-card);
  border-radius: 18px;
  color: var(--text-primary);
  background:
    linear-gradient(180deg, rgba(15, 23, 42, 0.66), rgba(15, 23, 42, 0.46));
  cursor: pointer;
  font: inherit;
  transition:
    border-color 0.16s ease,
    background 0.16s ease,
    transform 0.16s ease;
}

.lane-button:hover {
  border-color: rgba(147, 197, 253, 0.36);
  background:
    linear-gradient(180deg, rgba(30, 64, 175, 0.22), rgba(15, 23, 42, 0.52));
  transform: translateY(-1px);
}

.lane-button span {
  color: var(--text-secondary);
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.lane-button.active {
  border-color: rgba(96, 165, 250, 0.5);
  background:
    linear-gradient(135deg, rgba(30, 64, 175, 0.3), rgba(15, 23, 42, 0.56));
}

.assistant-grid {
  display: grid;
  grid-template-columns: minmax(320px, 0.8fr) minmax(420px, 1.4fr);
  gap: 1.05rem;
  align-items: start;
}

.developer-assistant-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.panel {
  background: var(--surface-depth-panel);
  border: 1px solid var(--surface-border-panel);
  border-radius: 22px;
  padding: 1.35rem;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
  margin-bottom: 1.15rem;
}

.panel-header h2 {
  margin: 0;
  color: var(--text-primary);
  font-size: 20px;
  line-height: 1.25;
  font-weight: 700;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin: 1rem 0;
  color: var(--text-primary);
  font-size: 0.92rem;
  font-weight: 700;
}

.form-input {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--surface-border-card);
  border-radius: 12px;
  padding: 0.78rem 0.9rem;
  background: var(--surface-depth-card);
  color: var(--text-primary);
  font: inherit;
  line-height: 1.45;
}

.source-selector {
  display: grid;
  gap: 0.85rem;
  margin: 1rem 0;
}

.source-mode-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.65rem;
}

.source-selection-summary {
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 700;
}

.source-checkbox-list {
  display: grid;
  gap: 0.55rem;
  padding: 0.85rem;
  border: 1px solid var(--surface-border-card);
  border-radius: 16px;
  background: var(--surface-depth-card);
}

.source-list-actions {
  display: flex;
  gap: 0.9rem;
  align-items: center;
}

.source-action-btn {
  border: 1px solid rgba(125, 211, 252, 0.28);
  border-radius: 999px;
  padding: 0.34rem 0.72rem;
  background: rgba(14, 116, 144, 0.16);
  color: #bae6fd;
  font: inherit;
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
}

.source-action-btn:hover {
  border-color: rgba(125, 211, 252, 0.46);
  background: rgba(14, 116, 144, 0.28);
  color: #f0f9ff;
}

.source-document-table {
  display: grid;
  margin: 0.9rem 0;
  overflow: hidden;
  border: 1px solid var(--surface-border-card);
  border-radius: 16px;
  background: var(--surface-depth-card);
}

.source-document-table-header,
.source-document-row {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(92px, 0.45fr) minmax(126px, 0.55fr);
  gap: 0.75rem;
  align-items: center;
}

.source-document-table.selectable .source-document-table-header,
.source-document-table.selectable .source-document-row {
  grid-template-columns: 42px minmax(0, 1.35fr) minmax(92px, 0.45fr) minmax(126px, 0.55fr);
}

.source-document-table-header {
  padding: 0.62rem 0.78rem;
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  background: var(--surface-depth-card);
}

.source-document-row {
  padding: 0.78rem;
  color: var(--text-secondary);
  font-size: 12px;
  border-top: 1px solid rgba(148, 163, 184, 0.12);
}

.source-document-row.active {
  background: rgba(14, 116, 144, 0.1);
  color: var(--text-primary);
}

.source-document-row.muted {
  opacity: 0.58;
}

.source-document-check {
  display: flex;
  align-items: center;
  justify-content: center;
}

.source-document-title {
  display: grid;
  gap: 0.18rem;
  min-width: 0;
}

.source-document-title strong,
.source-document-title small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-document-title strong {
  color: var(--text-primary);
  font-weight: 800;
}

.source-document-title small {
  color: var(--text-secondary);
}

.source-empty-selection {
  padding: 0.75rem 0.85rem;
  border-top: 1px solid rgba(251, 191, 36, 0.2);
  background: rgba(120, 53, 15, 0.14);
  color: #fde68a;
  font-size: 13px;
  font-weight: 700;
}

.fronting-readiness {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.7rem;
  margin: 0.9rem 0 0;
}

.fronting-readiness-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.68rem 0.78rem;
  border: 1px solid rgba(251, 191, 36, 0.22);
  border-radius: 14px;
  background: rgba(120, 53, 15, 0.14);
  color: var(--text-secondary);
  font-size: 13px;
}

.fronting-readiness-item.ready {
  border-color: rgba(34, 197, 94, 0.25);
  background: rgba(20, 83, 45, 0.16);
}

.fronting-readiness-item strong {
  color: var(--text-primary);
}

.topology-controls {
  display: grid;
  gap: 0.85rem;
  margin: 1rem 0;
  padding: 1.05rem;
  border: 1px solid rgba(96, 165, 250, 0.22);
  border-radius: 18px;
  background:
    linear-gradient(180deg, rgba(30, 64, 175, 0.14), rgba(15, 23, 42, 0.42));
}

.topology-controls p {
  margin: 0.3rem 0 0;
  color: var(--text-secondary);
  line-height: 1.45;
}

.topology-note {
  border-color: rgba(34, 197, 94, 0.2);
  background: rgba(34, 197, 94, 0.08);
}

.compact-field {
  margin: 0;
}

.source-quality-card {
  display: grid;
  gap: 0.85rem;
  margin: 1rem 0;
  padding: 1.05rem;
  border-radius: 18px;
  border: 1px solid rgba(251, 191, 36, 0.24);
  background:
    linear-gradient(180deg, rgba(251, 191, 36, 0.11), rgba(15, 23, 42, 0.42));
}

.source-quality-card.quality-strong {
  border-color: rgba(34, 197, 94, 0.25);
  background: rgba(34, 197, 94, 0.08);
}

.source-quality-card.quality-weak {
  border-color: rgba(248, 113, 113, 0.25);
  background: rgba(248, 113, 113, 0.08);
}

.source-quality-header {
  display: flex;
  gap: 0.75rem;
  justify-content: space-between;
  align-items: flex-start;
}

.source-quality-header p,
.quality-note {
  margin: 0.3rem 0 0;
  color: var(--text-secondary);
  line-height: 1.45;
}

.source-quality-header span {
  font-size: 24px;
  font-weight: 800;
  color: var(--text-primary);
}

.quality-criteria {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 0.45rem;
}

.quality-row {
  display: flex;
  gap: 0.45rem;
  align-items: center;
  color: var(--text-secondary);
  font-size: 13px;
}

.quality-row.ready {
  color: var(--text-primary);
}

.quality-weak-areas {
  display: grid;
  gap: 0.35rem;
  color: var(--text-secondary);
}

.quality-weak-areas strong {
  color: var(--text-primary);
}

.quality-weak-areas ul {
  margin: 0;
  padding-left: 1.1rem;
}

.blocking-state {
  display: grid;
  gap: 0.65rem;
  margin: 1rem 0;
  padding: 1.05rem;
  border: 1px solid rgba(251, 191, 36, 0.24);
  border-radius: 18px;
  background:
    linear-gradient(180deg, rgba(251, 191, 36, 0.11), rgba(15, 23, 42, 0.42));
}

.blocking-state p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.5;
}

.blocking-state .btn {
  justify-self: start;
}

.continuation-state {
  display: grid;
  gap: 0.65rem;
  margin: 1rem 0;
  padding: 1.05rem;
  border: 1px solid rgba(59, 130, 246, 0.28);
  border-radius: 18px;
  background:
    radial-gradient(circle at top left, rgba(59, 130, 246, 0.16), transparent 36%),
    rgba(15, 23, 42, 0.42);
}

.continuation-state p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.5;
}

.continuation-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
}

.continuation-metrics span {
  border: 1px solid rgba(251, 191, 36, 0.26);
  border-radius: 999px;
  padding: 0.28rem 0.58rem;
  color: #fde68a;
  font-size: 12px;
  font-weight: 800;
}

.preview-content {
  max-height: 520px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  background:
    linear-gradient(180deg, rgba(15, 23, 42, 0.66), rgba(15, 23, 42, 0.48));
  border: 1px solid var(--surface-border-card);
  border-radius: 18px;
  padding: 1.1rem;
  color: var(--text-secondary);
}

.draft-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem;
  align-items: center;
  justify-content: flex-end;
}

.draft-actions-bottom {
  justify-content: flex-start;
  margin-top: 1rem;
}

.draft-context {
  display: flex;
  flex-wrap: wrap;
  gap: 0.7rem;
  align-items: center;
  margin: 0.8rem 0 0;
  color: var(--text-secondary);
}

.status-chip {
  border: 1px solid var(--surface-border-card);
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.12);
  color: var(--text-secondary);
  padding: 0.32rem 0.68rem;
  font-size: 12px;
  font-weight: 700;
  text-transform: capitalize;
}

.status-chip.ready {
  border-color: rgba(34, 197, 94, 0.28);
  background: rgba(34, 197, 94, 0.12);
  color: #bbf7d0;
}

.draft-results {
  display: grid;
  gap: 1.05rem;
  margin-top: 1.2rem;
  padding-top: 1.1rem;
  border-top: 1px solid rgba(148, 163, 184, 0.14);
}

.draft-summary h3,
.draft-summary p {
  margin: 0;
}

.draft-summary p {
  margin-top: 0.35rem;
  color: var(--text-secondary);
  line-height: 1.6;
}

.draft-meta {
  font-size: 12px;
}

.clarification-batch {
  padding: 1.05rem;
  border-radius: 18px;
  border: 1px solid rgba(251, 191, 36, 0.24);
  background:
    linear-gradient(180deg, rgba(251, 191, 36, 0.11), rgba(15, 23, 42, 0.42));
}

.clarification-batch p {
  margin: 0.35rem 0 0.6rem;
  color: var(--text-secondary);
}

.clarification-batch ul {
  margin: 0;
  padding-left: 1.1rem;
  color: var(--text-secondary);
}

.draft-section-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 0.8rem;
}

.btn {
  min-height: 38px;
  border-radius: 12px;
  font-weight: 700;
}

.btn-secondary {
  background: var(--surface-depth-card);
  color: #dbeafe;
  border-color: rgba(96, 165, 250, 0.24);
}

.btn-secondary:hover:not(:disabled) {
  background: rgba(30, 64, 175, 0.22);
  border-color: rgba(147, 197, 253, 0.42);
}

@media (max-width: 980px) {
  .assistant-grid,
  .work-mode-switcher,
  .manual-action-grid,
  .operator-status-grid,
  .lane-switcher,
  .assistant-status-panel {
    grid-template-columns: 1fr;
  }

  .operator-hero {
    flex-direction: column;
  }

  .assistant-status-row strong {
    text-align: left;
  }
}
</style>
