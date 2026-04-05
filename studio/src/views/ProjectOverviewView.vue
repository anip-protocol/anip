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
const intentInterpretation = ref<IntentInterpretation | null>(null)
const lastInterpretedIntent = ref('')
const draftStatus = ref<string | null>(null)

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
    intentInterpretation.value = null
    intentError.value = null
    draftStatus.value = null
    lastInterpretedIntent.value = ''
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

function slugify(input: string): string {
  return input
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

function normalizedWords(...parts: string[]): Set<string> {
  return new Set(
    parts
      .join(' ')
      .toLowerCase()
      .split(/[^a-z0-9]+/)
      .map(item => item.trim())
      .filter(Boolean),
  )
}

function titleize(input: string): string {
  return input
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (match) => match.toUpperCase())
}

function cleanSentence(input: string): string {
  return input.replace(/\s+/g, ' ').trim()
}

function scenarioTitleFromStarter(text: string, index: number): string {
  const cleaned = cleanSentence(text).replace(/^add a scenario where\s+/i, '').replace(/^describe\s+/i, '')
  const compact = cleaned.replace(/\.$/, '')
  if (!compact) return `Scenario ${index}`
  const shortened = compact.length > 72 ? `${compact.slice(0, 69).trim()}...` : compact
  return titleize(shortened)
}

function inferScenarioCategory(text: string): 'safety' | 'recovery' | 'orchestration' | 'cross_service' | 'observability' {
  const words = normalizedWords(text)
  if (
    words.has('handoff') ||
    words.has('handoffs') ||
    words.has('cross') ||
    words.has('services') ||
    words.has('service')
  ) {
    return 'cross_service'
  }
  if (words.has('verify') || words.has('verification') || words.has('confirm') || words.has('reconcile')) {
    return 'observability'
  }
  if (words.has('refresh') || words.has('stale') || words.has('expired') || words.has('revalidate')) {
    return 'recovery'
  }
  if (words.has('follow') || words.has('followup') || words.has('async') || words.has('approval')) {
    return 'orchestration'
  }
  return 'safety'
}

function makeRequirementsTemplateFromIntent(result: IntentInterpretation, intent: string) {
  const data = makeRequirementsTemplate()
  const words = normalizedWords(
    intent,
    result.summary,
    result.recommended_shape_reason,
    ...result.requirements_focus,
    ...result.scenario_starters,
    ...result.next_steps,
  )

  data.system.name = slugify(project.value?.name || result.title || 'new-service') || 'new-service'
  data.scale.shape_preference =
    result.recommended_shape_type === 'multi_service'
      ? 'multi_service_estate'
      : 'production_single_service'

  const constraints = data.business_constraints as Record<string, any>
  const mentionsBudget =
    words.has('budget') || words.has('cost') || words.has('spend') || words.has('price') || words.has('pricing')
  const mentionsApproval =
    words.has('approval') || words.has('approve') || words.has('approver') || words.has('escalate') || words.has('escalation')
  const mentionsRecovery =
    words.has('refresh') || words.has('stale') || words.has('expired') || words.has('revalidate') || words.has('recovery')
  const mentionsRisk =
    words.has('risk') || words.has('danger') || words.has('dangerous') || words.has('destructive') || words.has('delete')

  constraints.spending_possible = mentionsBudget
  constraints.cost_visibility_required = mentionsBudget
  constraints.approval_expected_for_high_risk = mentionsApproval || mentionsRisk
  constraints.recovery_sensitive = mentionsRecovery
  constraints.blocked_failure_posture = mentionsBudget || mentionsApproval || mentionsRecovery || mentionsRisk
    ? 'structured_blocked'
    : 'basic_failure_surface'

  return data
}

function makeScenarioTemplatesFromIntent(result: IntentInterpretation) {
  const starters = result.scenario_starters.length
    ? result.scenario_starters.slice(0, 3)
    : ['Describe the normal success path that the service should handle cleanly.']

  return starters.map((starter, index) => {
    const category = inferScenarioCategory(starter)
    const title = scenarioTitleFromStarter(starter, index + 1)
    const scenarioName = slugify(title) || `scenario-${index + 1}`
    const words = normalizedWords(starter)
    const actionCapability =
      words.has('book') || words.has('booking')
        ? 'book_the_primary_action'
        : words.has('verify') || words.has('verification')
          ? 'verify_the_outcome'
          : words.has('refresh') || words.has('stale')
            ? 'refresh_or_revalidate_before_acting'
            : words.has('approval') || words.has('approve')
              ? 'request_or_record_approval'
              : 'handle_the_primary_action'

    const expectedBehavior = [
      starter,
      category === 'cross_service'
        ? 'The service boundary should remain clear across the handoff.'
        : 'The system should make the intended control decision explicit.',
    ]

    const expectedSupport = [
      category === 'recovery'
        ? 'The contract should make refresh or recovery guidance explicit.'
        : category === 'observability'
          ? 'The contract should expose enough context to verify and explain the outcome.'
          : category === 'cross_service'
            ? 'The contract should preserve continuity and handoff meaning across services.'
            : 'The contract should make purpose, constraints, and blocked-action meaning explicit.',
    ]

    return {
      title,
      data: {
        scenario: {
          name: scenarioName,
          category,
          narrative: starter,
          context: {
            capability: actionCapability,
          },
          expected_behavior: expectedBehavior,
          expected_anip_support: expectedSupport,
        },
      },
    }
  })
}

function makeShapeTemplateFromIntent(result: IntentInterpretation) {
  const rootName = project.value?.name || 'new-service'
  const shapeName = titleize(rootName)
  const primaryServiceId = slugify(rootName) || 'primary-service'
  const conceptIds = result.domain_concepts.map((concept) => ({
    id: slugify(concept) || `concept-${crypto.randomUUID()}`,
    name: concept,
  }))

  const primaryService = {
    id: primaryServiceId,
    name: shapeName,
    role: 'primary service',
    responsibilities: [
      'Own the main action and the core control checks around it.',
      ...result.requirements_focus.slice(0, 2),
    ],
    capabilities: [
      'handle_primary_action',
      ...result.scenario_starters.slice(0, 2).map((item) => slugify(item) || 'support_scenario'),
    ],
    owns_concepts: conceptIds.slice(0, Math.max(1, conceptIds.length - 1)).map((concept) => concept.id),
  }

  const services: Array<Record<string, any>> = [primaryService]
  const coordination: Array<Record<string, any>> = []

  if (result.recommended_shape_type === 'multi_service') {
    const lowerSuggestions = result.service_suggestions.map((item) => item.toLowerCase())

    if (lowerSuggestions.some((item) => item.includes('approval'))) {
      services.push({
        id: 'approval-service',
        name: 'Approval Service',
        role: 'approval boundary',
        responsibilities: ['Track approvals and decisions that should not be hidden inside the main action.'],
        capabilities: ['request_approval', 'record_approval_decision'],
        owns_concepts: conceptIds.filter((concept) => concept.name.toLowerCase().includes('approval')).map((concept) => concept.id),
      })
      coordination.push({
        from: primaryServiceId,
        to: 'approval-service',
        relationship: 'handoff',
        description: 'Send blocked or exceptional work for approval before the main action proceeds.',
      })
    }

    if (lowerSuggestions.some((item) => item.includes('verification'))) {
      services.push({
        id: 'verification-service',
        name: 'Verification Service',
        role: 'verification boundary',
        responsibilities: ['Verify the outcome after the initial action completes.'],
        capabilities: ['verify_outcome', 'record_verification_result'],
        owns_concepts: conceptIds.filter((concept) => concept.name.toLowerCase().includes('outcome')).map((concept) => concept.id),
      })
      coordination.push({
        from: primaryServiceId,
        to: 'verification-service',
        relationship: 'verification',
        description: 'Verify that the completed action actually reached the intended end state.',
      })
    }

    if (lowerSuggestions.some((item) => item.includes('refresh') || item.includes('revalidation'))) {
      services.push({
        id: 'revalidation-service',
        name: 'Revalidation Service',
        role: 'refresh boundary',
        responsibilities: ['Refresh stale or expired inputs before the main action continues.'],
        capabilities: ['refresh_input', 'revalidate_input'],
        owns_concepts: conceptIds.filter((concept) => concept.name.toLowerCase().includes('quote')).map((concept) => concept.id),
      })
      coordination.push({
        from: primaryServiceId,
        to: 'revalidation-service',
        relationship: 'verification',
        description: 'Refresh or revalidate inputs before the main action proceeds.',
      })
    }
  }

  if (result.recommended_shape_type === 'multi_service' && services.length === 1) {
    services.push({
      id: 'support-service',
      name: 'Support Service',
      role: 'supporting responsibility',
      responsibilities: ['Handle the secondary follow-up, coordination, or verification responsibility implied by the brief.'],
      capabilities: ['handle_followup_or_coordination'],
      owns_concepts: [],
    })
    coordination.push({
      from: primaryServiceId,
      to: 'support-service',
      relationship: 'handoff',
      description: 'Separate the secondary responsibility instead of hiding it inside one oversized service.',
    })
  }

  return {
    shape: {
      id: slugify(`${shapeName}-shape`) || 'service-shape',
      name: shapeName,
      type: result.recommended_shape_type === 'multi_service' ? 'multi_service' : 'single_service',
      notes: [result.recommended_shape_reason, ...result.service_suggestions.slice(0, 2)],
      services,
      coordination,
      domain_concepts: conceptIds.map((concept, index) => ({
        id: concept.id,
        name: concept.name,
        meaning: `Business concept: ${concept.name}`,
        owner: services.length > 1 && concept.name.toLowerCase().includes('approval')
          ? 'approval-service'
          : index === conceptIds.length - 1 && services.length > 1
            ? 'shared'
            : primaryServiceId,
        sensitivity: concept.name.toLowerCase().includes('approval') || concept.name.toLowerCase().includes('budget') ? 'medium' : 'none',
      })),
    },
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
      ? makeRequirementsTemplateFromIntent(intentResult, lastInterpretedIntent.value)
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
    const data = intentResult ? makeShapeTemplateFromIntent(intentResult) : makeShapeTemplate()
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
  lastInterpretedIntent.value = intent
  try {
    intentInterpretation.value = await interpretProjectIntentWithAssistant(projectId.value, intent)
  } catch (err) {
    intentError.value = err instanceof Error ? err.message : String(err)
  } finally {
    intentLoading.value = false
  }
}

async function handleCreateScenarioStarters(result: IntentInterpretation) {
  if (!projectId.value) return
  creating.value = 'scenario'
  draftStatus.value = null
  try {
    const templates = makeScenarioTemplatesFromIntent(result)
    const createdIds: string[] = []
    for (const template of templates) {
      const created = await createScenario(projectId.value, {
        id: `scn-${crypto.randomUUID()}`,
        title: template.title,
        data: template.data,
      })
      createdIds.push(created.id)
    }
    await refreshArtifacts()
    setActiveScenario(createdIds[0] || null)
    draftStatus.value = `Created ${createdIds.length} starter scenario${createdIds.length === 1 ? '' : 's'} from your plain-language brief.`
    if (createdIds[0]) {
      router.push(`/design/projects/${projectId.value}/scenarios/${createdIds[0]}`)
    }
  } finally {
    creating.value = null
  }
}

async function handleCreateDraftSet(result: IntentInterpretation) {
  if (!projectId.value) return
  creating.value = 'requirements'
  draftStatus.value = null
  try {
    const requirementsCreated = await createRequirements(projectId.value, {
      id: `req-${crypto.randomUUID()}`,
      title: requirements.value.length === 0 ? 'Requirements' : `Requirements ${requirements.value.length + 1}`,
      data: makeRequirementsTemplateFromIntent(result, lastInterpretedIntent.value),
    })

    const scenarioTemplates = makeScenarioTemplatesFromIntent(result)
    const createdScenarioIds: string[] = []
    for (const template of scenarioTemplates) {
      const createdScenario = await createScenario(projectId.value, {
        id: `scn-${crypto.randomUUID()}`,
        title: template.title,
        data: template.data,
      })
      createdScenarioIds.push(createdScenario.id)
    }

    creating.value = 'shape'
    const shapeCreated = await createShape(projectId.value, {
      id: `shape-${crypto.randomUUID()}`,
      title: shapes.value.length === 0 ? 'Service Shape' : `Service Shape ${shapes.value.length + 1}`,
      requirements_id: requirementsCreated.id,
      data: makeShapeTemplateFromIntent(result),
    })

    await refreshArtifacts()
    setActiveRequirements(requirementsCreated.id)
    setActiveScenario(createdScenarioIds[0] || null)
    setActiveShape(shapeCreated.id)
    draftStatus.value = `Created the first draft set: requirements, ${createdScenarioIds.length} scenario starter${createdScenarioIds.length === 1 ? '' : 's'}, and a service shape.`
    router.push(`/design/projects/${projectId.value}/shapes/${shapeCreated.id}`)
  } finally {
    creating.value = null
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
        <StudioIntentPanel
          title="Start from Plain Language"
          description="Describe what you want to build in normal language. Studio will suggest the first requirements pressure, scenario starters, domain concepts, and service-shape direction."
          :result="intentInterpretation"
          :loading="intentLoading"
          :error="intentError"
          @run="handleInterpretIntent"
          @create-draft-set="handleCreateDraftSet"
          @create-requirements="handleCreateRequirements"
          @create-scenarios="handleCreateScenarioStarters"
          @create-shape="handleCreateShape"
        />

        <div v-if="draftStatus" class="banner banner-success">{{ draftStatus }}</div>

        <div class="flow-intro">
          <h2 class="section-title">Design Flow</h2>
          <p class="section-desc">Shape the service in one clear loop: define what matters, model the service, then evaluate whether it will work.</p>
        </div>
        <div class="flow-cards">
          <div class="flow-card" :class="{ ready: hasRequirements }">
            <span class="flow-step">1</span>
            <div>
              <div class="flow-label">Requirements</div>
              <div class="flow-meta">{{ requirements.length }} set{{ requirements.length === 1 ? '' : 's' }}</div>
            </div>
          </div>
          <div class="flow-card" :class="{ ready: hasScenarios }">
            <span class="flow-step">2</span>
            <div>
              <div class="flow-label">Scenarios</div>
              <div class="flow-meta">{{ scenarios.length }} scenario{{ scenarios.length === 1 ? '' : 's' }}</div>
            </div>
          </div>
          <div class="flow-card" :class="{ ready: hasServiceShape }">
            <span class="flow-step">3</span>
            <div>
              <div class="flow-label">{{ isLegacyProposalProject ? 'Legacy Approach' : 'Service Shape' }}</div>
              <div class="flow-meta">{{ isLegacyProposalProject ? proposals.length : shapes.length }} defined</div>
            </div>
          </div>
          <div class="flow-card" :class="{ ready: evaluations.length > 0 }">
            <span class="flow-step">4</span>
            <div>
              <div class="flow-label">Evaluation</div>
              <div class="flow-meta">{{ evaluations.length }} run{{ evaluations.length === 1 ? '' : 's' }}</div>
            </div>
          </div>
        </div>
        <div class="next-step-callout">
          <strong>{{ nextStepTitle }}</strong>
          <p>{{ nextStepDescription }}</p>
        </div>
      </section>

      <!-- Active design context -->
      <section class="context-section" id="evaluate">
        <h2 class="section-title">Evaluate the Current Design</h2>
        <p class="section-desc">Choose the requirements, scenario, and {{ isLegacyProposalProject ? 'legacy approach' : 'service shape' }} you want to test together.</p>
        <div class="context-selects">
          <div class="context-field">
            <label class="field-label">Requirements</label>
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
            <label class="field-label">Scenario</label>
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
            <label class="field-label">Service Shape</label>
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
            :title="canEvaluate ? 'Evaluate this design context' : 'Select requirements, a scenario, and a service shape first'"
            @click="goToEvaluation"
          >
            Evaluate This Design
          </button>
        </div>
      </section>

      <section class="readout-section" id="changes">
        <div class="readout-head">
          <div>
            <h2 class="section-title">Changes Needed</h2>
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
            <h3 class="readout-title">Latest Evaluation Readout</h3>
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

/* Active design context */
.context-section {
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.25rem;
  margin-bottom: 1.5rem;
}

.creation-section {
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.25rem;
  margin-bottom: 1.5rem;
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

.readout-section,
.artifact-summary-section {
  margin-bottom: 1.5rem;
  padding: 1.1rem 1.15rem;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: var(--radius);
  background: rgba(255, 255, 255, 0.55);
}

.readout-head {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
  margin-bottom: 0.9rem;
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
