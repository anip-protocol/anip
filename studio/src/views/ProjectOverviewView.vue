<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  projectStore,
  loadProject,
  loadVocabulary,
  setActiveRequirements,
  setActiveScenario,
  setActiveProposal,
  setActiveShape,
  setPendingIntentDraft,
  refreshArtifacts,
} from '../design/project-store'
import {
  createProposal,
  createRequirements,
  createScenario,
  createShape,
  exportProject,
  interpretProjectIntentWithAssistant,
  importArtifacts,
  setRequirementsRole,
} from '../design/project-api'
import type { IntentInterpretation } from '../design/project-types'
import StudioIntentPanel from '../design/components/StudioIntentPanel.vue'
import {
  slugify,
  normalizedWords,
  cleanSentence,
  scenarioTitleFromStarter,
  inferScenarioCategory,
  makeRequirementsTemplateFromIntent,
  makeScenarioTemplatesFromIntent,
  makeShapeTemplateFromIntent,
} from '../design/intent-drafts'
import {
  buildBusinessBrief,
  buildEngineeringContract,
  downloadTextDocument,
} from '../design/shared-artifacts'

const route = useRoute()
const router = useRouter()

const projectId = computed(() => route.params.projectId as string)
const project = computed(() => projectStore.activeProject)
const loading = computed(() => projectStore.loading)
const error = computed(() => projectStore.error)

const requirements = computed(() => projectStore.artifacts.requirements)
const scenarios = computed(() => projectStore.artifacts.scenarios)
const proposals = computed(() => projectStore.artifacts.proposals)
const shapes = computed(() => projectStore.artifacts.shapes)
const evaluations = computed(() => projectStore.artifacts.evaluations)

const activeRequirementsId = computed(() => projectStore.activeRequirementsId)
const activeScenarioId = computed(() => projectStore.activeScenarioId)
const activeProposalId = computed(() => projectStore.activeProposalId)
const activeShapeId = computed(() => projectStore.activeShapeId)

/** Shape-first: project has shapes */
const hasShapes = computed(() => shapes.value.length > 0)
/** Legacy: project has proposals but no shapes */
const isLegacyProposalProject = computed(() => proposals.value.length > 0 && !hasShapes.value)
const isShapeFirstProject = computed(() => !isLegacyProposalProject.value)

const importing = ref(false)
const exporting = ref(false)
const creating = ref<'requirements' | 'scenario' | 'proposal' | 'shape' | null>(null)
const promotingId = ref<string | null>(null)
const showAlternatives = ref(false)
const intentLoading = ref(false)
const intentError = ref<string | null>(null)
const intentInterpretation = computed(() => projectStore.pendingIntentDraft?.interpretation ?? null)
const lastInterpretedIntent = computed(() => projectStore.pendingIntentDraft?.source_intent ?? '')
const draftStatus = ref<string | null>(null)
const loopView = ref<LoopView>('current')
const businessBriefCopied = ref(false)
const engineeringContractCopied = ref(false)

const primaryRequirements = computed(() =>
  requirements.value.filter(r => r.role === 'primary'),
)

const alternativeRequirements = computed(() =>
  requirements.value.filter(r => r.role === 'alternative'),
)

const hasRequirements = computed(() => requirements.value.length > 0)
const hasScenarios = computed(() => scenarios.value.length > 0)
const hasServiceShape = computed(() => isLegacyProposalProject.value ? proposals.value.length > 0 : shapes.value.length > 0)
const canEvaluate = computed(() =>
  !!activeRequirementsId.value &&
  !!activeScenarioId.value &&
  (!!activeShapeId.value || !!activeProposalId.value),
)

const latestEvaluationRecord = computed(() => {
  const items = [...evaluations.value]
  items.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
  return items[0] ?? null
})

const latestEvaluation = computed<Record<string, any> | null>(() => {
  return latestEvaluationRecord.value?.data?.evaluation ?? null
})

const latestHandled = computed<string[]>(() => {
  const handled = latestEvaluation.value?.handled_by_anip
  return Array.isArray(handled) ? handled.slice(0, 4) : []
})

const latestChangesNeeded = computed<string[]>(() => {
  const improve = latestEvaluation.value?.what_would_improve
  if (Array.isArray(improve) && improve.length > 0) return improve.slice(0, 5)
  const glue = latestEvaluation.value?.glue_you_will_still_write
  return Array.isArray(glue) ? glue.slice(0, 5) : []
})

const latestWhy = computed<string[]>(() => {
  const why = latestEvaluation.value?.why
  return Array.isArray(why) ? why.slice(0, 3) : []
})

const latestEvaluationSummary = computed(() => {
  const result = latestEvaluation.value?.result
  if (!result) return null
  if (result === 'HANDLED') return 'The current design is covering the scenario pressure well.'
  if (result === 'PARTIAL') return 'The current design is promising, but there are still important gaps to close.'
  return 'The current design still needs meaningful changes before it can support this scenario cleanly.'
})

const businessBriefContent = computed(() => buildBusinessBrief({
  project: project.value,
  sourceIntent: lastInterpretedIntent.value,
  requirements: activeRequirementsRecord.value,
  scenario: activeScenarioRecord.value,
  shape: activeShapeRecord.value,
  evaluation: latestEvaluationRecord.value,
}))

const engineeringContractContent = computed(() => buildEngineeringContract({
  project: project.value,
  requirements: activeRequirementsRecord.value,
  scenario: activeScenarioRecord.value,
  shape: activeShapeRecord.value,
  evaluation: latestEvaluationRecord.value,
}))

const activeRequirementsRecord = computed(() =>
  requirements.value.find(item => item.id === activeRequirementsId.value) ??
  primaryRequirements.value[0] ??
  requirements.value[0] ??
  null,
)

const activeScenarioRecord = computed(() =>
  scenarios.value.find(item => item.id === activeScenarioId.value) ??
  scenarios.value[0] ??
  null,
)

const activeShapeRecord = computed(() =>
  shapes.value.find(item => item.id === activeShapeId.value) ??
  shapes.value[0] ??
  null,
)

const activeServiceDesignTitle = computed(() => {
  if (isLegacyProposalProject.value) {
    return proposals.value.find(item => item.id === activeProposalId.value)?.title ??
      proposals.value[0]?.title ??
      'Nothing selected yet'
  }
  return activeShapeRecord.value?.title ?? shapes.value[0]?.title ?? 'Nothing selected yet'
})

const currentDesignCards = computed(() => [
  {
    label: 'What Matters',
    title: activeRequirementsRecord.value?.title ?? 'Nothing selected yet',
    description: activeRequirementsRecord.value
      ? 'These are the active constraints and pressures shaping the design.'
      : 'Define what must be true before the design hardens.',
    actionLabel: activeRequirementsRecord.value ? 'Open What Matters' : 'Create What Matters',
    onClick: () => {
      if (activeRequirementsRecord.value) {
        navigateRequirements(activeRequirementsRecord.value.id)
      } else {
        void handleCreateRequirementsManual()
      }
    },
  },
  {
    label: 'Real Situation',
    title: activeScenarioRecord.value?.title ?? 'Nothing selected yet',
    description: activeScenarioRecord.value
      ? 'This is the active situation currently pressuring the design.'
      : 'Add the first real situation the design should handle.',
    actionLabel: activeScenarioRecord.value ? 'Open Real Situation' : 'Add Real Situation',
    onClick: () => {
      if (activeScenarioRecord.value) {
        navigateScenario(activeScenarioRecord.value.id)
      } else {
        void handleCreateScenarioManual()
      }
    },
  },
  {
    label: isLegacyProposalProject.value ? 'Legacy Approach' : 'Service Design',
    title: activeServiceDesignTitle.value,
    description: isLegacyProposalProject.value
      ? 'This project is still using the legacy approach model.'
      : activeShapeRecord.value
        ? 'This is the active service design Studio will use in the next test.'
        : 'Turn the current pressures and situations into a service design.',
    actionLabel: (isLegacyProposalProject.value
      ? activeProposalId.value
      : activeShapeRecord.value)
      ? 'Open Service Design'
      : 'Create Service Design',
    onClick: () => {
      if (isLegacyProposalProject.value) {
        if (activeProposalId.value) {
          navigateProposal(activeProposalId.value)
        }
        return
      }
      if (activeShapeRecord.value) {
        navigateShape(activeShapeRecord.value.id)
      } else {
        void handleCreateShapeManual()
      }
    },
  },
])

function deepClone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value))
}

type ChangeAction =
  | 'open_requirements'
  | 'open_shape'
  | 'open_scenarios'
  | 'open_evaluation'
  | 'evaluate'

function classifyChangeAction(text: string): { label: string; action: ChangeAction } {
  const words = normalizedWords(text)

  if (
    words.has('requirement') ||
    words.has('requirements') ||
    words.has('budget') ||
    words.has('approval') ||
    words.has('audit') ||
    words.has('lineage') ||
    words.has('constraint') ||
    words.has('authority')
  ) {
    return { label: hasRequirements.value ? 'Open Requirements' : 'Create Requirements', action: 'open_requirements' }
  }

  if (
    words.has('shape') ||
    words.has('service') ||
    words.has('boundary') ||
    words.has('coordination') ||
    words.has('capability') ||
    words.has('concept')
  ) {
    return { label: hasServiceShape.value ? 'Open Service Shape' : 'Create Service Shape', action: 'open_shape' }
  }

  if (
    words.has('scenario') ||
    words.has('followup') ||
    words.has('follow') ||
    words.has('handoff') ||
    words.has('verification') ||
    words.has('refresh') ||
    words.has('revalidate')
  ) {
    return { label: hasScenarios.value ? 'Open Scenarios' : 'Add Scenario', action: 'open_scenarios' }
  }

  if (canEvaluate.value) {
    return { label: 'Re-evaluate', action: 'evaluate' }
  }

  return { label: 'Open Evaluation', action: 'open_evaluation' }
}

function makeRequirementsFixTemplate(change: string) {
  const base = activeRequirementsRecord.value
    ? deepClone(baseData(activeRequirementsRecord.value.data))
    : makeRequirementsTemplate()
  const words = normalizedWords(change)
  const constraints = (base.business_constraints ??= {}) as Record<string, any>
  const audit = (base.audit ??= {}) as Record<string, any>
  const lineage = (base.lineage ??= {}) as Record<string, any>

  if (words.has('budget') || words.has('cost') || words.has('spend')) {
    constraints.spending_possible = true
    constraints.cost_visibility_required = true
    constraints.blocked_failure_posture = 'structured_blocked'
  }
  if (words.has('approval') || words.has('authority') || words.has('escalate')) {
    constraints.approval_expected_for_high_risk = true
    constraints.blocked_failure_posture = 'structured_blocked'
  }
  if (words.has('recovery') || words.has('refresh') || words.has('revalidate') || words.has('stale')) {
    constraints.recovery_sensitive = true
    constraints.blocked_failure_posture = 'structured_blocked'
  }
  if (words.has('audit') || words.has('trace')) {
    audit.durable = true
    audit.searchable = true
  }
  if (words.has('lineage') || words.has('continuity') || words.has('cross')) {
    lineage.task_id = true
    lineage.parent_invocation_id = true
    lineage.cross_service_continuity_required = true
    audit.cross_service_reconstruction_required = true
  }

  return base
}

function baseData(data: Record<string, any>) {
  return (data?.requirements ?? data?.shape ?? data) as Record<string, any>
}

function makeScenarioFixTemplate(change: string) {
  const category = inferScenarioCategory(change)
  const baseScenario = activeScenarioRecord.value?.data?.scenario
  const title = scenarioTitleFromStarter(change, scenarios.value.length + 1)
  return {
    scenario: {
      name: title,
      category,
      narrative: cleanSentence(change),
      context: {
        capability: baseScenario?.context?.capability || 'handle_the_primary_action',
      },
      expected_behavior: [
        cleanSentence(change),
        category === 'cross_service'
          ? 'The cross-service responsibility should stay explicit instead of hiding inside glue.'
          : 'The system should make the intended decision and next step explicit.',
      ],
      expected_anip_support: [
        category === 'cross_service'
          ? 'The contract should preserve cross-service continuity and handoff meaning.'
          : category === 'recovery'
            ? 'The contract should make refresh or recovery guidance explicit.'
            : 'The contract should make purpose, blocked-action meaning, and next steps explicit.',
      ],
    },
  }
}

function makeShapeFixTemplate(change: string) {
  const base = activeShapeRecord.value
    ? deepClone(baseData(activeShapeRecord.value.data))
    : baseData(makeShapeTemplate())
  const shape = base as Record<string, any>
  const words = normalizedWords(change)

  shape.notes = [...(Array.isArray(shape.notes) ? shape.notes : []), cleanSentence(change)]
  shape.services = Array.isArray(shape.services) ? shape.services : []
  shape.coordination = Array.isArray(shape.coordination) ? shape.coordination : []
  shape.domain_concepts = Array.isArray(shape.domain_concepts) ? shape.domain_concepts : []

  const primaryService = shape.services[0]

  if (primaryService) {
    primaryService.responsibilities = Array.isArray(primaryService.responsibilities) ? primaryService.responsibilities : []
    primaryService.capabilities = Array.isArray(primaryService.capabilities) ? primaryService.capabilities : []
  }

  if (primaryService && (words.has('budget') || words.has('approval') || words.has('authority'))) {
    primaryService.responsibilities.push('Make high-risk control checks explicit before the main action proceeds.')
    primaryService.capabilities.push('enforce_control_decision')
  }

  if (primaryService && (words.has('refresh') || words.has('revalidate') || words.has('stale'))) {
    primaryService.capabilities.push('refresh_or_revalidate_input')
  }

  if (words.has('verification') || words.has('verify')) {
    const existing = shape.services.find((item: Record<string, any>) => item.id === 'verification-service')
    if (!existing) {
      shape.services.push({
        id: 'verification-service',
        name: 'Verification Service',
        role: 'verification boundary',
        responsibilities: ['Verify the outcome after the main action completes.'],
        capabilities: ['verify_outcome'],
        owns_concepts: [],
      })
    }
    if (!shape.coordination.some((edge: Record<string, any>) => edge.to === 'verification-service')) {
      shape.coordination.push({
        from: primaryService?.id || 'primary-service',
        to: 'verification-service',
        relationship: 'verification',
        description: cleanSentence(change),
      })
    }
  }

  if (words.has('handoff') || words.has('cross') || words.has('coordination') || words.has('followup')) {
    const existing = shape.services.find((item: Record<string, any>) => item.id === 'followup-service')
    if (!existing) {
      shape.services.push({
        id: 'followup-service',
        name: 'Follow-up Service',
        role: 'handoff boundary',
        responsibilities: ['Handle the follow-up or secondary service responsibility explicitly.'],
        capabilities: ['handle_followup'],
        owns_concepts: [],
      })
    }
    if (!shape.coordination.some((edge: Record<string, any>) => edge.to === 'followup-service')) {
      shape.coordination.push({
        from: primaryService?.id || 'primary-service',
        to: 'followup-service',
        relationship: 'handoff',
        description: cleanSentence(change),
      })
    }
  }

  if (words.has('concept') || words.has('entity') || words.has('domain')) {
    shape.domain_concepts.push({
      id: `concept-${crypto.randomUUID()}`,
      name: 'New Domain Concept',
      meaning: cleanSentence(change),
      owner: primaryService?.id || 'shared',
      sensitivity: 'none',
    })
  }

  return { shape }
}

const nextStepTitle = computed(() => {
  if (!hasRequirements.value) return 'Start with requirements'
  if (!hasScenarios.value) return 'Add the key scenarios'
  if (!hasServiceShape.value) return isLegacyProposalProject.value ? 'Define the legacy approach' : 'Define the service shape'
  if (!canEvaluate.value) return 'Choose the active evaluation context'
  return 'Run an evaluation'
})

const nextStepDescription = computed(() => {
  if (!hasRequirements.value) return 'Describe what must be true before deciding how the service should be shaped.'
  if (!hasScenarios.value) return 'Capture the situations that should pressure and validate the design.'
  if (!hasServiceShape.value) return 'Describe the service or service estate that should satisfy the requirements across those scenarios.'
  if (!canEvaluate.value) return 'Pick the requirements, scenario, and service shape you want to test together.'
  return 'You have enough context to evaluate whether this design will work and what still needs to change.'
})

type HomePrimaryAction =
  | 'review_first_draft'
  | 'create_requirements'
  | 'create_scenario'
  | 'create_shape'
  | 'choose_context'
  | 'evaluate'
  | 'review_changes'

type LoopView = 'current' | 'test' | 'changes'

const currentStateTitle = computed(() => {
  if (projectStore.pendingIntentDraft) {
    return 'Studio has a suggested first design ready to review.'
  }
  if (!hasRequirements.value && !hasScenarios.value && !hasServiceShape.value) {
    return 'This project is still blank.'
  }
  if (!hasRequirements.value) return 'The project still needs what matters.'
  if (!hasScenarios.value) return 'The project still needs real situations.'
  if (!hasServiceShape.value) return 'The project still needs a service design.'
  if (!canEvaluate.value) return 'The design exists, but the test context is incomplete.'
  if (evaluations.value.length === 0) return 'The design is ready for its first test.'
  return 'The project has a current design loop in progress.'
})

const currentStateDescription = computed(() => {
  if (projectStore.pendingIntentDraft) {
    return 'Review the suggested first design, then decide what to turn into real project artifacts.'
  }
  if (!hasRequirements.value && !hasScenarios.value && !hasServiceShape.value) {
    return 'Start by describing the problem in plain language, then let Studio shape the first draft.'
  }
  if (!hasRequirements.value) return 'Define what must be true before the service design hardens around the wrong assumptions.'
  if (!hasScenarios.value) return 'Add the situations that should pressure and validate the design.'
  if (!hasServiceShape.value) return 'Turn the requirements and situations into a concrete service design.'
  if (!canEvaluate.value) return 'Choose the active requirements, scenario, and service shape you want to test together.'
  if (evaluations.value.length === 0) return 'You have enough structure to test whether the current design will really work.'
  return 'Review what changed, test the current design again, or turn the latest result into something you can share.'
})

const homePrimaryAction = computed<{ label: string; detail: string; action: HomePrimaryAction }>(() => {
  if (projectStore.pendingIntentDraft) {
    return {
      label: 'Review Suggested First Design',
      detail: 'See Studio’s proposed starting point before creating artifacts.',
      action: 'review_first_draft',
    }
  }
  if (!hasRequirements.value) {
    return {
      label: 'Create Requirements',
      detail: 'Start by capturing what must be true.',
      action: 'create_requirements',
    }
  }
  if (!hasScenarios.value) {
    return {
      label: 'Add Scenario',
      detail: 'Add the first real situation this design should handle.',
      action: 'create_scenario',
    }
  }
  if (!hasServiceShape.value) {
    return {
      label: 'Create Service Shape',
      detail: 'Turn the current inputs into a concrete service design.',
      action: 'create_shape',
    }
  }
  if (!canEvaluate.value) {
    return {
      label: 'Choose What To Test',
      detail: 'Pick the requirements, scenario, and service shape for the next test.',
      action: 'choose_context',
    }
  }
  if (evaluations.value.length === 0) {
    return {
      label: 'Test This Design',
      detail: 'Run the first evaluation on the current design.',
      action: 'evaluate',
    }
  }
  return {
    label: 'Review What Needs To Change',
    detail: 'Use the latest evaluation to decide the next design move.',
    action: 'review_changes',
  }
})

async function handlePromote(rid: string) {
  if (!projectId.value) return
  promotingId.value = rid
  try {
    await setRequirementsRole(projectId.value, rid, 'primary')
    await loadProject(projectId.value)
  } finally {
    promotingId.value = null
  }
}

onMounted(() => {
  if (projectId.value) {
    loadProject(projectId.value)
    loadVocabulary(projectId.value)
  }
})

watch(projectId, (id) => {
  if (id) {
    loadProject(id)
    loadVocabulary(id)
    setPendingIntentDraft(null)
    intentError.value = null
    draftStatus.value = null
  }
})

function onRequirementsChange(event: Event) {
  const value = (event.target as HTMLSelectElement).value
  setActiveRequirements(value || null)
}

function onScenarioChange(event: Event) {
  const value = (event.target as HTMLSelectElement).value
  setActiveScenario(value || null)
}

function onProposalChange(event: Event) {
  const value = (event.target as HTMLSelectElement).value
  setActiveProposal(value || null)
}

function onShapeChange(event: Event) {
  const value = (event.target as HTMLSelectElement).value
  setActiveShape(value || null)
}

function navigateRequirements(id: string) {
  router.push(`/design/projects/${projectId.value}/requirements/${id}`)
}

function navigateScenario(id: string) {
  router.push(`/design/projects/${projectId.value}/scenarios/${id}`)
}

function navigateProposal(id: string) {
  router.push(`/design/projects/${projectId.value}/proposals/${id}`)
}

function navigateEvaluation(id: string) {
  router.push(`/design/projects/${projectId.value}/evaluations/${id}`)
}

function goToEvaluation() {
  if (!activeScenarioId.value) return
  router.push(`/design/projects/${projectId.value}/evaluations/${activeScenarioId.value}`)
}

async function handleExport() {
  if (!projectId.value) return
  exporting.value = true
  try {
    const data = await exportProject(projectId.value)
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${project.value?.name ?? 'project'}-export.json`
    a.click()
    URL.revokeObjectURL(url)
  } catch {
    // error surfaced through projectStore.error
  } finally {
    exporting.value = false
  }
}

function handleImportClick() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.json'
  input.onchange = async (e) => {
    const file = (e.target as HTMLInputElement).files?.[0]
    if (!file || !projectId.value) return
    importing.value = true
    try {
      const text = await file.text()
      const parsed = JSON.parse(text)
      const artifacts = Array.isArray(parsed.artifacts)
        ? parsed.artifacts
        : [
            ...(Array.isArray(parsed.requirements) ? parsed.requirements.map((item: any) => ({ type: 'requirements', data: item })) : []),
            ...(Array.isArray(parsed.scenarios) ? parsed.scenarios.map((item: any) => ({ type: 'scenario', data: item })) : []),
            ...(Array.isArray(parsed.proposals) ? parsed.proposals.map((item: any) => ({ type: 'proposal', data: item })) : []),
            ...(Array.isArray(parsed.evaluations) ? parsed.evaluations.map((item: any) => ({ type: 'evaluation', data: item })) : []),
          ]
      await importArtifacts(projectId.value, artifacts)
      await loadProject(projectId.value)
    } catch {
      // error surfaced through projectStore.error
    } finally {
      importing.value = false
    }
  }
  input.click()
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

function scrollToSection(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function openLoopView(view: LoopView) {
  loopView.value = view
  scrollToSection('design-loop')
}

function openFirstDraftReview() {
  router.push(`/design/projects/${projectId.value}/first-draft`)
}

function discardPendingIntent() {
  setPendingIntentDraft(null)
  draftStatus.value = 'Discarded the pending suggested first design.'
}

async function copyShareableDocument(kind: 'business' | 'engineering') {
  const content = kind === 'business' ? businessBriefContent.value : engineeringContractContent.value
  try {
    await navigator.clipboard.writeText(content)
    if (kind === 'business') {
      businessBriefCopied.value = true
      setTimeout(() => { businessBriefCopied.value = false }, 1500)
    } else {
      engineeringContractCopied.value = true
      setTimeout(() => { engineeringContractCopied.value = false }, 1500)
    }
  } catch {
    // clipboard may be unavailable in some environments
  }
}

function downloadShareableDocument(kind: 'business' | 'engineering') {
  const slug = slugify(project.value?.name || 'project')
  if (kind === 'business') {
    downloadTextDocument(`${slug}-business-brief.md`, businessBriefContent.value)
    return
  }
  downloadTextDocument(`${slug}-engineering-contract.md`, engineeringContractContent.value)
}

async function runHomePrimaryAction() {
  switch (homePrimaryAction.value.action) {
    case 'review_first_draft':
      router.push(`/design/projects/${projectId.value}/first-draft`)
      break
    case 'create_requirements':
      await handleCreateRequirementsManual()
      break
    case 'create_scenario':
      await handleCreateScenarioManual()
      break
    case 'create_shape':
      await handleCreateShapeManual()
      break
    case 'choose_context':
      openLoopView('test')
      break
    case 'evaluate':
      openLoopView('test')
      break
    case 'review_changes':
      openLoopView('changes')
      break
  }
}

function makeRequirementsTemplate() {
  const name = project.value?.name || 'new-service'
  const domain = project.value?.domain || 'general'
  return {
    system: {
      name: slugify(name) || 'new-service',
      domain,
      deployment_intent: 'public_http_service',
    },
    transports: { http: true, stdio: false, grpc: false },
    trust: { mode: 'signed', checkpoints: false },
    auth: {
      delegation_tokens: true,
      purpose_binding: true,
      scoped_authority: true,
    },
    permissions: {
      preflight_discovery: true,
      restricted_vs_denied: true,
    },
    audit: { durable: true, searchable: true },
    lineage: {
      invocation_id: true,
      client_reference_id: true,
      task_id: true,
      parent_invocation_id: true,
    },
    risk_profile: {},
    business_constraints: {},
    scale: {
      shape_preference: 'production_single_service',
      high_availability: false,
    },
  }
}

function makeScenarioTemplate(nextIndex: number) {
  return {
    scenario: {
      name: `scenario_${nextIndex}`,
      category: 'safety',
      narrative: 'Describe the situation, constraints, and expected outcome for this scenario.',
      context: {
        capability: 'describe_the_action_under_review',
      },
      expected_behavior: ['describe_expected_system_behavior'],
      expected_anip_support: ['describe_expected_anip_support'],
    },
  }
}

function makeProposalTemplate() {
  return {
    proposal: {
      recommended_shape: 'production_single_service',
      rationale: ['Describe why this approach is appropriate for the project.'],
      required_components: ['describe_required_component'],
      optional_components: [],
      key_runtime_requirements: [],
      anti_pattern_warnings: [],
      expected_glue_reduction: {},
      declared_surfaces: {
        budget_enforcement: false,
        binding_requirements: false,
        authority_posture: false,
        recovery_class: false,
        refresh_via: false,
        verify_via: false,
        followup_via: false,
        cross_service_handoff: false,
        cross_service_continuity: false,
        cross_service_reconstruction: false,
      },
    },
  }
}

async function handleCreateRequirements(intentResult?: IntentInterpretation) {
  if (!projectId.value) return
  creating.value = 'requirements'
  draftStatus.value = null
  try {
    const nextIndex = requirements.value.length + 1
    const data = intentResult
      ? makeRequirementsTemplateFromIntent(
          intentResult,
          lastInterpretedIntent.value,
          project.value?.name || 'new-service',
          project.value?.domain || 'general',
        )
      : makeRequirementsTemplate()
    const created = await createRequirements(projectId.value, {
      id: `req-${crypto.randomUUID()}`,
      title: nextIndex === 1 ? 'Requirements' : `Requirements ${nextIndex}`,
      data,
    })
    await refreshArtifacts()
    setActiveRequirements(created.id)
    draftStatus.value = intentResult ? 'Created a first requirements draft from your plain-language brief.' : null
    router.push(`/design/projects/${projectId.value}/requirements/${created.id}`)
  } finally {
    creating.value = null
  }
}

async function handleCreateScenario(intentResult?: IntentInterpretation) {
  if (!projectId.value) return
  creating.value = 'scenario'
  draftStatus.value = null
  try {
    const nextIndex = scenarios.value.length + 1
    const created = intentResult
      ? await createScenario(projectId.value, {
          id: `scn-${crypto.randomUUID()}`,
          title: makeScenarioTemplatesFromIntent(intentResult)[0].title,
          data: makeScenarioTemplatesFromIntent(intentResult)[0].data,
        })
      : await createScenario(projectId.value, {
          id: `scn-${crypto.randomUUID()}`,
          title: makeScenarioTemplate(nextIndex).scenario.name,
          data: makeScenarioTemplate(nextIndex),
        })
    await refreshArtifacts()
    setActiveScenario(created.id)
    draftStatus.value = intentResult ? 'Created a starter scenario from your plain-language brief.' : null
    router.push(`/design/projects/${projectId.value}/scenarios/${created.id}`)
  } finally {
    creating.value = null
  }
}

async function handleCreateProposal() {
  if (!projectId.value) return
  const requirementsId = activeRequirementsId.value || requirements.value[0]?.id || null
  if (!requirementsId) return

  creating.value = 'proposal'
  try {
    const nextIndex = proposals.value.length + 1
    const created = await createProposal(projectId.value, {
      id: `prop-${crypto.randomUUID()}`,
      title: nextIndex === 1 ? 'Approach' : `Approach ${nextIndex}`,
      requirements_id: requirementsId,
      data: makeProposalTemplate(),
    })
    await refreshArtifacts()
    setActiveProposal(created.id)
    router.push(`/design/projects/${projectId.value}/proposals/${created.id}`)
  } finally {
    creating.value = null
  }
}

function navigateShape(id: string) {
  router.push(`/design/projects/${projectId.value}/shapes/${id}`)
}

function makeShapeTemplate() {
  const name = project.value?.name || 'new-service'
  return {
    shape: {
      id: 'shape-1',
      name: name,
      type: 'single_service',
      notes: [],
      services: [
        {
          id: 'svc-1',
          name: name,
          role: 'primary service',
          responsibilities: [],
          capabilities: [],
          owns_concepts: [],
        },
      ],
      coordination: [],
      domain_concepts: [],
    },
  }
}

async function handleCreateShape(intentResult?: IntentInterpretation) {
  if (!projectId.value) return
  const requirementsId = activeRequirementsId.value || requirements.value[0]?.id || null
  if (!requirementsId) return

  creating.value = 'shape'
  draftStatus.value = null
  try {
    const nextIndex = shapes.value.length + 1
    const data = intentResult ? makeShapeTemplateFromIntent(intentResult, project.value?.name || 'new-service') : makeShapeTemplate()
    const created = await createShape(projectId.value, {
      id: `shape-${crypto.randomUUID()}`,
      title: nextIndex === 1 ? 'Service Shape' : `Service Shape ${nextIndex}`,
      requirements_id: requirementsId,
      data,
    })
    await refreshArtifacts()
    setActiveShape(created.id)
    draftStatus.value = intentResult ? 'Created a first service-shape draft from your plain-language brief.' : null
    router.push(`/design/projects/${projectId.value}/shapes/${created.id}`)
  } finally {
    creating.value = null
  }
}

async function handleInterpretIntent(intent: string) {
  if (!projectId.value || !intent) return
  intentLoading.value = true
  intentError.value = null
  draftStatus.value = null
  try {
    const interpretation = await interpretProjectIntentWithAssistant(projectId.value, intent)
    setPendingIntentDraft({
      source_intent: intent,
      interpretation,
    })
    router.push(`/design/projects/${projectId.value}/first-draft`)
  } catch (err) {
    intentError.value = err instanceof Error ? err.message : String(err)
  } finally {
    intentLoading.value = false
  }
}

function handleCreateRequirementsManual() {
  return handleCreateRequirements()
}

function handleCreateScenarioManual() {
  return handleCreateScenario()
}

function handleCreateShapeManual() {
  return handleCreateShape()
}

async function handleFollowChange(item: string) {
  const target = classifyChangeAction(item)

  if (target.action === 'open_requirements') {
    if (activeRequirementsId.value) {
      navigateRequirements(activeRequirementsId.value)
      return
    }
    await handleCreateRequirementsManual()
    return
  }

  if (target.action === 'open_shape') {
    if (activeShapeId.value) {
      navigateShape(activeShapeId.value)
      return
    }
    await handleCreateShapeManual()
    return
  }

  if (target.action === 'open_scenarios') {
    if (activeScenarioId.value) {
      navigateScenario(activeScenarioId.value)
      return
    }
    await handleCreateScenarioManual()
    return
  }

  if (target.action === 'evaluate') {
    goToEvaluation()
    return
  }

  if (latestEvaluationRecord.value) {
    navigateEvaluation(latestEvaluationRecord.value.id)
  }
}

async function handleDraftChange(item: string) {
  if (!projectId.value) return
  const target = classifyChangeAction(item)
  draftStatus.value = null

  if (target.action === 'open_requirements') {
    creating.value = 'requirements'
    try {
      const created = await createRequirements(projectId.value, {
        id: `req-${crypto.randomUUID()}`,
        title: `Requirements Fix ${requirements.value.length + 1}`,
        data: makeRequirementsFixTemplate(item),
      })
      await refreshArtifacts()
      setActiveRequirements(created.id)
      draftStatus.value = 'Created a requirements draft fix from the latest evaluation guidance.'
      navigateRequirements(created.id)
    } finally {
      creating.value = null
    }
    return
  }

  if (target.action === 'open_scenarios') {
    creating.value = 'scenario'
    try {
      const created = await createScenario(projectId.value, {
        id: `scn-${crypto.randomUUID()}`,
        title: scenarioTitleFromStarter(item, scenarios.value.length + 1),
        data: makeScenarioFixTemplate(item),
      })
      await refreshArtifacts()
      setActiveScenario(created.id)
      draftStatus.value = 'Created a scenario draft from the latest evaluation guidance.'
      navigateScenario(created.id)
    } finally {
      creating.value = null
    }
    return
  }

  if (target.action === 'open_shape') {
    const requirementsId = activeRequirementsRecord.value?.id || null
    if (!requirementsId) {
      draftStatus.value = 'Create or select a requirements set before drafting a shape fix.'
      return
    }
    creating.value = 'shape'
    try {
      const created = await createShape(projectId.value, {
        id: `shape-${crypto.randomUUID()}`,
        title: `Service Shape Fix ${shapes.value.length + 1}`,
        requirements_id: requirementsId,
        data: makeShapeFixTemplate(item),
      })
      await refreshArtifacts()
      setActiveShape(created.id)
      draftStatus.value = 'Created a service-shape draft fix from the latest evaluation guidance.'
      navigateShape(created.id)
    } finally {
      creating.value = null
    }
    return
  }

  await handleFollowChange(item)
}
</script>

<template>
  <div class="project-overview">
    <div v-if="loading && !project" class="loading-state">Loading project...</div>
    <div v-else-if="error && !project" class="error-state">{{ error }}</div>

    <template v-if="project">
      <!-- Project header -->
      <div class="project-header">
        <div class="header-top">
          <button class="back-link" @click="router.push(project?.workspace_id ? `/design/workspaces/${project.workspace_id}` : '/design')">&larr; Projects</button>
        </div>
        <h1 class="page-title">{{ project.name }}</h1>
        <div class="project-meta">
          <span class="domain-badge">{{ project.domain || 'general' }}</span>
          <span v-if="project.summary" class="project-summary">{{ project.summary }}</span>
        </div>
      </div>

      <section class="flow-section" id="overview">
        <div class="home-summary-card">
          <div class="home-summary-copy">
            <div class="summary-kicker">Current State</div>
            <h2 class="home-summary-title">{{ currentStateTitle }}</h2>
            <p class="home-summary-description">{{ currentStateDescription }}</p>
          </div>
          <div class="home-summary-action">
            <button class="btn btn-primary home-primary-btn" @click="runHomePrimaryAction">
              {{ homePrimaryAction.label }}
            </button>
            <p class="home-primary-detail">{{ homePrimaryAction.detail }}</p>
          </div>
        </div>

        <div class="home-state-metrics" aria-label="Current design state">
          <div class="state-metric">
            <span class="state-metric-label">Requirements</span>
            <span class="state-metric-value">{{ requirements.length }}</span>
          </div>
          <div class="state-metric">
            <span class="state-metric-label">Scenarios</span>
            <span class="state-metric-value">{{ scenarios.length }}</span>
          </div>
          <div class="state-metric">
            <span class="state-metric-label">{{ isLegacyProposalProject ? 'Approaches' : 'Service Shapes' }}</span>
            <span class="state-metric-value">{{ isLegacyProposalProject ? proposals.length : shapes.length }}</span>
          </div>
          <div class="state-metric">
            <span class="state-metric-label">Evaluations</span>
            <span class="state-metric-value">{{ evaluations.length }}</span>
          </div>
        </div>

        <StudioIntentPanel
          title="What Are We Building?"
          description="Describe what you want to build in normal language. Studio will suggest the first requirements pressure, scenario starters, domain concepts, and service-shape direction."
          :result="intentInterpretation"
          :pending-intent="lastInterpretedIntent"
          :loading="intentLoading"
          :error="intentError"
          @run="handleInterpretIntent"
          @review-result="openFirstDraftReview"
          @discard-result="discardPendingIntent"
        />

        <div v-if="draftStatus" class="banner banner-success">{{ draftStatus }}</div>
      </section>

      <section class="flow-map-section">
        <div class="flow-intro">
          <h2 class="section-title">How This Design Comes Together</h2>
          <p class="section-desc">Use the working loop below to define what matters, capture real situations, shape the service, and test whether it will work.</p>
        </div>
        <div class="flow-cards">
          <div class="flow-card" :class="{ ready: hasRequirements }">
            <span class="flow-step">1</span>
            <div>
              <div class="flow-label">What Matters</div>
              <div class="flow-meta">{{ requirements.length }} set{{ requirements.length === 1 ? '' : 's' }}</div>
            </div>
          </div>
          <div class="flow-card" :class="{ ready: hasScenarios }">
            <span class="flow-step">2</span>
            <div>
              <div class="flow-label">Real Situations</div>
              <div class="flow-meta">{{ scenarios.length }} scenario{{ scenarios.length === 1 ? '' : 's' }}</div>
            </div>
          </div>
          <div class="flow-card" :class="{ ready: hasServiceShape }">
            <span class="flow-step">3</span>
            <div>
              <div class="flow-label">{{ isLegacyProposalProject ? 'Legacy Approach' : 'Service Design' }}</div>
              <div class="flow-meta">{{ isLegacyProposalProject ? proposals.length : shapes.length }} defined</div>
            </div>
          </div>
          <div class="flow-card" :class="{ ready: evaluations.length > 0 }">
            <span class="flow-step">4</span>
            <div>
              <div class="flow-label">Design Test</div>
              <div class="flow-meta">{{ evaluations.length }} run{{ evaluations.length === 1 ? '' : 's' }}</div>
            </div>
          </div>
        </div>
        <div class="next-step-callout">
          <strong>{{ nextStepTitle }}</strong>
          <p>{{ nextStepDescription }}</p>
        </div>
      </section>

      <section class="loop-section" id="design-loop">
        <div class="loop-header">
          <div>
            <h2 class="section-title">Design Loop</h2>
            <p class="section-desc">Keep the current design, the next test, and the resulting changes in one working loop instead of treating them as separate destinations.</p>
          </div>
        </div>

        <div class="loop-tabs" role="tablist" aria-label="Design loop">
          <button class="loop-tab" :class="{ active: loopView === 'current' }" @click="loopView = 'current'">Current Design</button>
          <button class="loop-tab" :class="{ active: loopView === 'test' }" @click="loopView = 'test'">Test This Design</button>
          <button class="loop-tab" :class="{ active: loopView === 'changes' }" @click="loopView = 'changes'">What Needs to Change</button>
        </div>

        <div v-if="loopView === 'current'" class="loop-panel">
          <div class="loop-panel-head">
            <h3 class="loop-panel-title">Current Design</h3>
            <p class="section-desc">This is the current design context Studio is working from right now.</p>
          </div>

          <div class="current-design-grid">
            <div v-for="card in currentDesignCards" :key="card.label" class="current-design-card">
              <div class="current-design-label">{{ card.label }}</div>
              <h4 class="current-design-title">{{ card.title }}</h4>
              <p class="current-design-description">{{ card.description }}</p>
              <button class="btn btn-secondary current-design-btn" @click="card.onClick()">
                {{ card.actionLabel }}
              </button>
            </div>
          </div>
        </div>

        <div v-else-if="loopView === 'test'" class="loop-panel">
          <div class="loop-panel-head">
            <h3 class="loop-panel-title">Test This Design</h3>
            <p class="section-desc">Choose what matters, the real situation, and the {{ isLegacyProposalProject ? 'legacy approach' : 'service design' }} you want to test together.</p>
          </div>

          <div class="context-selects">
            <div class="context-field">
              <label class="field-label">What Matters</label>
              <select
                class="field-select"
                :value="activeRequirementsId ?? ''"
                @change="onRequirementsChange"
              >
                <option value="">-- Select --</option>
                <option
                  v-for="r in requirements"
                  :key="r.id"
                  :value="r.id"
                >{{ r.title || r.id }}</option>
              </select>
            </div>
            <div class="context-field">
              <label class="field-label">Real Situation</label>
              <select
                class="field-select"
                :value="activeScenarioId ?? ''"
                @change="onScenarioChange"
              >
                <option value="">-- Select --</option>
                <option
                  v-for="s in scenarios"
                  :key="s.id"
                  :value="s.id"
                >{{ s.title || s.id }}</option>
              </select>
            </div>
            <div v-if="isShapeFirstProject" class="context-field">
              <label class="field-label">Service Design</label>
              <select
                class="field-select"
                :value="activeShapeId ?? ''"
                @change="onShapeChange"
              >
                <option value="">-- Select --</option>
                <option
                  v-for="s in shapes"
                  :key="s.id"
                  :value="s.id"
                >{{ s.title || s.id }}</option>
              </select>
            </div>
            <div v-else class="context-field">
              <label class="field-label">Approach</label>
              <select
                class="field-select"
                :value="activeProposalId ?? ''"
                @change="onProposalChange"
              >
                <option value="">-- Select --</option>
                <option
                  v-for="p in proposals"
                  :key="p.id"
                  :value="p.id"
                >{{ p.title || p.id }}</option>
              </select>
            </div>
          </div>
          <div class="context-actions">
            <button
              class="btn btn-primary"
              :disabled="!canEvaluate"
              :title="canEvaluate ? 'Test this design context' : 'Select what matters, a real situation, and a service design first'"
              @click="goToEvaluation"
            >
              Test This Design
            </button>
          </div>
        </div>

        <div v-else class="loop-panel">
          <div class="readout-head">
            <div>
              <h3 class="loop-panel-title">What Needs to Change</h3>
              <p class="section-desc">Use the latest evaluation as the current design readout. This should tell you what already works and what you should change next.</p>
            </div>
            <button
              v-if="latestEvaluationRecord"
              class="btn btn-secondary"
              @click="navigateEvaluation(latestEvaluationRecord.id)"
            >
              Open Full Evaluation
            </button>
          </div>

          <div v-if="!latestEvaluationRecord" class="changes-empty">
            No evaluation yet. Run the current design once, then Studio will turn the result into a clearer “what works” and “what should change” readout here.
          </div>

          <template v-else>
            <div class="readout-summary-card">
              <div class="readout-badges">
                <span class="artifact-status" :class="'status-' + latestEvaluationRecord.result.toLowerCase()">{{ latestEvaluationRecord.result }}</span>
                <span v-if="latestEvaluationRecord.is_stale" class="stale-badge">Stale</span>
              </div>
              <h4 class="readout-title">Latest Evaluation Readout</h4>
              <p class="readout-summary">{{ latestEvaluationSummary }}</p>
              <p v-if="latestWhy.length" class="readout-why">{{ latestWhy[0] }}</p>
            </div>

            <div class="changes-grid">
              <div class="changes-card">
                <div class="changes-card-title">Working Well</div>
                <ul v-if="latestHandled.length" class="changes-list">
                  <li v-for="(item, index) in latestHandled" :key="`handled-${index}`">{{ item }}</li>
                </ul>
                <p v-else class="changes-empty-note">No strong support areas are called out yet.</p>
              </div>

              <div class="changes-card changes-card-primary">
                <div class="changes-card-title">Change Next</div>
                <ul v-if="latestChangesNeeded.length" class="changes-list">
                  <li v-for="(item, index) in latestChangesNeeded" :key="`change-${index}`" class="changes-list-item">
                    <div class="change-copy">{{ item }}</div>
                    <div class="change-actions">
                      <button class="change-action-btn" @click="handleFollowChange(item)">
                        {{ classifyChangeAction(item).label }}
                      </button>
                      <button class="change-action-btn change-action-btn-primary" @click="handleDraftChange(item)">
                        Draft Fix
                      </button>
                    </div>
                  </li>
                </ul>
                <p v-else class="changes-empty-note">No concrete design changes are suggested from the latest evaluation.</p>
              </div>
            </div>
          </template>
        </div>
      </section>

      <section class="share-section">
        <div class="share-head">
          <div>
            <h2 class="section-title">Shareable Outputs</h2>
            <p class="section-desc">Generate one brief for product conversations and one contract for engineering follow-through from the current design loop.</p>
          </div>
        </div>

        <div class="share-grid">
          <section class="share-card">
            <div class="share-card-head">
              <div>
                <h3 class="loop-panel-title">Business Brief</h3>
                <p class="section-desc">PM-facing summary of the current design, the key situation under review, and what should change next.</p>
              </div>
              <div class="share-actions">
                <button class="btn btn-secondary" @click="copyShareableDocument('business')">
                  {{ businessBriefCopied ? 'Copied!' : 'Copy' }}
                </button>
                <button class="btn btn-secondary" @click="downloadShareableDocument('business')">
                  Download
                </button>
              </div>
            </div>
            <textarea class="share-preview" readonly :value="businessBriefContent"></textarea>
          </section>

          <section class="share-card">
            <div class="share-card-head">
              <div>
                <h3 class="loop-panel-title">Engineering Contract</h3>
                <p class="section-desc">Engineering-facing summary of the active context, design structure, expected behavior, and current gaps.</p>
              </div>
              <div class="share-actions">
                <button class="btn btn-secondary" @click="copyShareableDocument('engineering')">
                  {{ engineeringContractCopied ? 'Copied!' : 'Copy' }}
                </button>
                <button class="btn btn-secondary" @click="downloadShareableDocument('engineering')">
                  Download
                </button>
              </div>
            </div>
            <textarea class="share-preview" readonly :value="engineeringContractContent"></textarea>
          </section>
        </div>
      </section>

      <section class="creation-section">
        <h2 class="section-title">Build the Design</h2>
        <p class="section-desc">Build the project directly in Studio. Define what matters, capture the key scenarios, shape the service, then evaluate whether it will work.</p>
        <div class="creation-actions">
          <button class="btn btn-primary" @click="handleCreateRequirementsManual" :disabled="creating !== null">
            {{ creating === 'requirements' ? 'Creating requirements...' : 'New Requirements' }}
          </button>
          <button class="btn btn-primary" @click="handleCreateScenarioManual" :disabled="creating !== null">
            {{ creating === 'scenario' ? 'Creating scenario...' : 'New Scenario' }}
          </button>
          <button
            class="btn btn-primary"
            @click="handleCreateShapeManual"
            :disabled="creating !== null || requirements.length === 0"
            :title="requirements.length === 0 ? 'Create a requirements set first' : ''"
          >
            {{ creating === 'shape' ? 'Creating service shape...' : 'New Service Shape' }}
          </button>
          <button
            v-if="isLegacyProposalProject"
            class="btn btn-secondary"
            @click="handleCreateProposal"
            :disabled="creating !== null || requirements.length === 0"
            :title="requirements.length === 0 ? 'Create a requirements set first' : ''"
          >
            {{ creating === 'proposal' ? 'Creating approach...' : 'New Approach (Legacy)' }}
          </button>
        </div>
      </section>

      <!-- Import/Export toolbar -->
      <div class="io-toolbar">
        <button class="btn btn-secondary" @click="handleImportClick" :disabled="importing">
          {{ importing ? 'Importing...' : 'Import' }}
        </button>
        <button class="btn btn-secondary" @click="handleExport" :disabled="exporting">
          {{ exporting ? 'Exporting...' : 'Export' }}
        </button>
      </div>

      <div v-if="error" class="banner banner-error">{{ error }}</div>

      <section class="artifact-summary-section">
        <h2 class="section-title">Working Material</h2>
        <p class="section-desc">These are the project artifacts behind the current design. Use them when you need to inspect or refine the underlying details.</p>
      </section>

      <!-- Artifact lists -->
      <section class="artifact-section" id="requirements">
        <h2 class="section-title">Requirements ({{ requirements.length }})</h2>
        <div v-if="requirements.length === 0" class="empty-row">No requirements yet. Start here so the service shape and evaluation have something real to optimize for.</div>

        <!-- Primary requirements -->
        <div
          v-for="r in primaryRequirements"
          :key="r.id"
          class="artifact-row"
          @click="navigateRequirements(r.id)"
        >
          <span class="artifact-title">{{ r.title || r.id }}</span>
          <span class="role-badge primary-badge">Primary</span>
          <span class="artifact-status" :class="'status-' + r.status">{{ r.status }}</span>
          <span class="artifact-date">{{ formatDate(r.updated_at) }}</span>
        </div>

        <!-- Alternatives collapsible -->
        <template v-if="alternativeRequirements.length > 0">
          <button
            class="alternatives-toggle"
            type="button"
            @click="showAlternatives = !showAlternatives"
          >
            {{ showAlternatives ? '▾' : '▸' }} Alternatives ({{ alternativeRequirements.length }})
          </button>
          <template v-if="showAlternatives">
            <div
              v-for="r in alternativeRequirements"
              :key="r.id"
              class="artifact-row artifact-row-alt"
              @click="navigateRequirements(r.id)"
            >
              <span class="artifact-title">{{ r.title || r.id }}</span>
              <span class="role-badge alt-badge">Alternative</span>
              <span class="artifact-status" :class="'status-' + r.status">{{ r.status }}</span>
              <button
                class="artifact-action promote-btn"
                :disabled="promotingId !== null"
                @click.stop="handlePromote(r.id)"
              >
                {{ promotingId === r.id ? 'Promoting...' : 'Promote to Primary' }}
              </button>
              <span class="artifact-date">{{ formatDate(r.updated_at) }}</span>
            </div>
          </template>
        </template>
      </section>

      <section class="artifact-section" id="scenarios">
        <h2 class="section-title">Scenarios ({{ scenarios.length }})</h2>
        <div v-if="scenarios.length === 0" class="empty-row">No scenarios yet. Add the situations that should pressure the design and reveal whether it will work.</div>
        <div
          v-for="s in scenarios"
          :key="s.id"
          class="artifact-row"
          @click="navigateScenario(s.id)"
        >
          <span class="artifact-title">{{ s.title || s.id }}</span>
          <span class="artifact-status" :class="'status-' + s.status">{{ s.status }}</span>
          <span class="artifact-date">{{ formatDate(s.updated_at) }}</span>
        </div>
      </section>

      <!-- Shapes section (primary design artifact) -->
      <section class="artifact-section" id="shape" v-if="hasShapes || !isLegacyProposalProject">
        <h2 class="section-title">Service Shapes ({{ shapes.length }})</h2>
        <div v-if="shapes.length === 0" class="empty-row">No service shape yet. Define the services, the domain concepts they own, and how they coordinate.</div>
        <div
          v-for="s in shapes"
          :key="s.id"
          class="artifact-row"
          @click="navigateShape(s.id)"
        >
          <span class="artifact-title">{{ s.title || s.id }}</span>
          <span class="artifact-status" :class="'status-' + s.status">{{ s.status }}</span>
          <span class="artifact-date">{{ formatDate(s.updated_at) }}</span>
        </div>
      </section>

      <!-- Approaches section (legacy projects only) -->
      <section class="artifact-section" v-if="isLegacyProposalProject">
        <h2 class="section-title">Approaches (Legacy) ({{ proposals.length }})</h2>
        <p class="section-desc legacy-note">This project uses the legacy approach model. Create a Service Shape to move into the new design workflow.</p>
        <div
          v-for="p in proposals"
          :key="p.id"
          class="artifact-row"
          @click="navigateProposal(p.id)"
        >
          <span class="artifact-title">{{ p.title || p.id }}</span>
          <span class="artifact-status" :class="'status-' + p.status">{{ p.status }}</span>
          <span class="artifact-date">{{ formatDate(p.updated_at) }}</span>
        </div>
      </section>

      <section class="artifact-section">
        <h2 class="section-title">Evaluation History ({{ evaluations.length }})</h2>
        <div v-if="evaluations.length === 0" class="empty-row">No evaluations yet. Use the evaluation context above to test whether this design will work and what still needs to change.</div>
        <div
          v-for="e in evaluations"
          :key="e.id"
          class="artifact-row"
          @click="navigateEvaluation(e.id)"
        >
          <span class="artifact-title">{{ e.id }}</span>
          <span class="artifact-status" :class="'status-' + e.result.toLowerCase()">{{ e.result }}</span>
          <span v-if="e.is_stale" class="stale-badge">Stale</span>
          <span class="artifact-date">{{ formatDate(e.created_at) }}</span>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.project-overview {
  padding: 2rem;
  max-width: 900px;
}

.loading-state,
.error-state {
  padding: 2rem;
  text-align: center;
  color: var(--text-muted);
  font-size: 14px;
}

.error-state {
  color: var(--error);
}

.project-header {
  margin-bottom: 1.5rem;
}

.header-top {
  margin-bottom: 0.5rem;
}

.back-link {
  background: none;
  border: none;
  color: var(--accent);
  font-size: 13px;
  cursor: pointer;
  padding: 0;
  transition: color var(--transition);
}

.back-link:hover {
  color: var(--accent-hover);
}

.page-title {
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 0.5rem;
}

.project-meta {
  display: flex;
  align-items: center;
  gap: 12px;
}

.domain-badge {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-muted);
  background: var(--bg-hover);
  padding: 2px 8px;
  border-radius: 8px;
}

.project-summary {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.flow-section {
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.02), rgba(15, 23, 42, 0.04));
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.25rem;
  margin-bottom: 1.5rem;
}

.home-summary-card {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
  padding: 1rem 1.1rem;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.55);
  margin-bottom: 1rem;
}

.home-summary-copy {
  flex: 1;
  min-width: 0;
}

.summary-kicker {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: 0.45rem;
}

.home-summary-title {
  margin: 0 0 0.4rem;
  font-size: 20px;
  line-height: 1.2;
  color: var(--text-primary);
}

.home-summary-description {
  margin: 0;
  max-width: 58ch;
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-secondary);
}

.home-summary-action {
  width: 240px;
  max-width: 100%;
  flex-shrink: 0;
}

.home-primary-btn {
  width: 100%;
}

.home-primary-detail {
  margin: 0.55rem 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-muted);
}

.home-state-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 10px;
  margin-bottom: 1rem;
}

.state-metric {
  padding: 0.75rem 0.85rem;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.42);
}

.state-metric-label {
  display: block;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: 0.35rem;
}

.state-metric-value {
  display: block;
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
}

.flow-map-section {
  margin-bottom: 1.5rem;
}

.flow-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}

.flow-card {
  display: flex;
  align-items: center;
  gap: 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 12px;
  background: var(--bg-app);
}

.flow-card.ready {
  border-color: rgba(52, 211, 153, 0.35);
  background: rgba(52, 211, 153, 0.06);
}

.flow-step {
  width: 26px;
  height: 26px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  background: var(--bg-hover);
  color: var(--text-secondary);
}

.flow-card.ready .flow-step {
  background: rgba(52, 211, 153, 0.14);
  color: #34d399;
}

.flow-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.flow-meta {
  font-size: 12px;
  color: var(--text-muted);
}

.next-step-callout {
  border-left: 3px solid var(--accent);
  padding-left: 12px;
}

.next-step-callout strong {
  display: block;
  font-size: 13px;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.next-step-callout p {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
}

/* Design loop */
.loop-section,
.artifact-summary-section {
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.25rem;
  margin-bottom: 1.5rem;
}

.loop-header {
  margin-bottom: 0.9rem;
}

.loop-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  margin-bottom: 1rem;
}

.loop-tab {
  height: 34px;
  padding: 0 14px;
  border: 1px solid rgba(15, 23, 42, 0.1);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.7);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.loop-tab.active {
  border-color: rgba(59, 130, 246, 0.28);
  background: rgba(59, 130, 246, 0.08);
  color: #2563eb;
}

.loop-panel {
  padding: 1rem 1rem 0.95rem;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.55);
}

.loop-panel-head,
.readout-head {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
  margin-bottom: 0.9rem;
}

.loop-panel-title {
  margin: 0 0 0.35rem;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.current-design-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0.85rem;
}

.current-design-card {
  padding: 0.95rem 1rem;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: var(--radius-sm);
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.02), rgba(15, 23, 42, 0.04));
}

.current-design-label {
  margin-bottom: 0.45rem;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.current-design-title {
  margin: 0 0 0.4rem;
  font-size: 15px;
  line-height: 1.35;
  color: var(--text-primary);
}

.current-design-description {
  margin: 0 0 0.8rem;
  min-height: 3.3em;
  font-size: 13px;
  line-height: 1.55;
  color: var(--text-secondary);
}

.current-design-btn {
  width: 100%;
}

.creation-section {
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.25rem;
  margin-bottom: 1.5rem;
}

.share-section {
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.25rem;
  margin-bottom: 1.5rem;
}

.share-head {
  margin-bottom: 0.9rem;
}

.share-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 1rem;
}

.share-card {
  padding: 1rem;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.55);
}

.share-card-head {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
  margin-bottom: 0.8rem;
}

.share-actions {
  display: flex;
  gap: 0.45rem;
  flex-shrink: 0;
}

.share-preview {
  width: 100%;
  min-height: 280px;
  box-sizing: border-box;
  padding: 0.85rem 0.95rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-app);
  color: var(--text-primary);
  font: inherit;
  font-size: 12px;
  line-height: 1.55;
  resize: vertical;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 0.25rem;
}

.section-desc {
  font-size: 13px;
  color: var(--text-muted);
  margin: 0 0 0.75rem;
}

.context-selects {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.creation-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.context-field {
  flex: 1;
  min-width: 200px;
}

.field-label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.field-select {
  width: 100%;
  height: 34px;
  padding: 0 10px;
  background: var(--bg-app);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 13px;
  outline: none;
  transition: border-color var(--transition);
}

@media (max-width: 720px) {
  .home-summary-card {
    flex-direction: column;
  }

  .home-summary-action {
    width: 100%;
  }
}

.field-select:focus {
  border-color: var(--border-focus);
}

.context-actions {
  display: flex;
  justify-content: flex-end;
}

/* Import / Export */
.io-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 1.5rem;
}

.btn {
  height: 34px;
  padding: 0 16px;
  border: none;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background var(--transition);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-secondary {
  background: var(--bg-input);
  color: var(--text-secondary);
  border: 1px solid var(--border);
}

.btn-secondary:hover:not(:disabled) {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.btn-primary {
  background: var(--accent);
  color: #fff;
}

.btn-primary:hover:not(:disabled) {
  background: var(--accent-hover);
}

.banner {
  padding: 10px 16px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 1rem;
}

.banner-error {
  background: rgba(248, 113, 113, 0.12);
  border: 1px solid rgba(248, 113, 113, 0.3);
  color: var(--error);
}

/* Artifact sections */
.artifact-section {
  margin-bottom: 1.5rem;
  scroll-margin-top: 72px;
}

.artifact-section .section-title {
  margin-bottom: 0.5rem;
}

.empty-row {
  font-size: 13px;
  color: var(--text-muted);
  padding: 8px 0;
}

.artifact-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  margin-bottom: 4px;
  background: var(--bg-input);
  cursor: pointer;
  transition: all var(--transition);
}

.artifact-row:hover {
  border-color: var(--accent);
  background: var(--bg-hover);
}

.artifact-title {
  flex: 1;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.artifact-status {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 10px;
  text-transform: capitalize;
  background: var(--bg-hover);
  color: var(--text-muted);
}

.status-active,
.status-handled {
  background: rgba(52, 211, 153, 0.15);
  color: var(--design-handled, #34d399);
}

.status-draft {
  background: rgba(251, 191, 36, 0.15);
  color: var(--design-partial, #fbbf24);
}

.status-partial {
  background: rgba(251, 191, 36, 0.15);
  color: var(--design-partial, #fbbf24);
}

.status-requires_glue,
.status-requires-glue {
  background: rgba(248, 113, 113, 0.15);
  color: var(--design-glue, #f87171);
}

.artifact-date {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
}

.artifact-action {
  height: 28px;
  padding: 0 10px;
  border: 1px solid rgba(59, 130, 246, 0.35);
  border-radius: var(--radius-sm);
  background: rgba(59, 130, 246, 0.08);
  color: #3b82f6;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: background var(--transition);
}

.artifact-action:hover:not(:disabled) {
  background: rgba(59, 130, 246, 0.16);
}

.artifact-action:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

/* Role badges */
.role-badge {
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  padding: 2px 7px;
  border-radius: 8px;
}

.primary-badge {
  background: rgba(52, 211, 153, 0.12);
  color: #34d399;
}

.alt-badge {
  background: rgba(156, 163, 175, 0.12);
  color: var(--text-muted);
}

/* Alternatives toggle */
.alternatives-toggle {
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  padding: 4px 0;
  margin: 4px 0 2px;
  transition: color var(--transition);
}

.alternatives-toggle:hover {
  color: var(--text-primary);
}

.artifact-row-alt {
  margin-left: 12px;
  opacity: 0.85;
}

/* Promote button */
.promote-btn {
  border-color: rgba(96, 165, 250, 0.35);
  background: rgba(96, 165, 250, 0.08);
  color: #60a5fa;
}

.promote-btn:hover:not(:disabled) {
  background: rgba(96, 165, 250, 0.16);
}

/* Stale evaluation badge */
.stale-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 10px;
  background: rgba(251, 191, 36, 0.15);
  color: #fbbf24;
}

.legacy-note {
  font-style: italic;
  color: var(--text-muted);
}

.changes-empty,
.changes-empty-note,
.readout-summary,
.readout-why {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.55;
}

.readout-summary-card {
  padding: 1rem 1rem 0.95rem;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: var(--radius-sm);
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.02), rgba(15, 23, 42, 0.04));
}

.readout-badges {
  display: flex;
  gap: 0.45rem;
  align-items: center;
  margin-bottom: 0.65rem;
}

.readout-title {
  margin: 0 0 0.35rem;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.readout-why {
  margin-top: 0.45rem;
}

.changes-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 1rem;
  margin-top: 1rem;
}

.changes-card {
  padding: 0.95rem 1rem;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.55);
}

.changes-card-primary {
  border-color: rgba(59, 130, 246, 0.18);
  background: rgba(59, 130, 246, 0.05);
}

.changes-card-title {
  margin-bottom: 0.55rem;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.changes-list {
  margin: 0;
  padding-left: 1.1rem;
  color: var(--text-secondary);
}

.changes-list li + li {
  margin-top: 0.35rem;
}

.changes-list-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
}

.change-copy {
  flex: 1;
}

.change-actions {
  display: flex;
  flex-shrink: 0;
  gap: 0.45rem;
}

.change-action-btn {
  flex-shrink: 0;
  height: 30px;
  padding: 0 10px;
  border: 1px solid rgba(59, 130, 246, 0.35);
  border-radius: var(--radius-sm);
  background: rgba(59, 130, 246, 0.08);
  color: #2563eb;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: background var(--transition);
}

.change-action-btn:hover {
  background: rgba(59, 130, 246, 0.14);
}

.change-action-btn-primary {
  border-color: rgba(15, 23, 42, 0.12);
  background: rgba(15, 23, 42, 0.06);
  color: var(--text-primary);
}

.change-action-btn-primary:hover {
  background: rgba(15, 23, 42, 0.1);
}
</style>
