<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { designStore, discardEdits, updateDraftField, setScenarioMode, updateGuidedScenarioAnswer } from '../design/store'
import { loadProject, projectStore, openArtifactForEditing, refreshArtifacts } from '../design/project-store'
import { createScenario, deleteScenario, updateScenario } from '../design/project-api'
import EditorToolbar from '../design/components/EditorToolbar.vue'
import KeyValueEditor from '../design/components/KeyValueEditor.vue'
import StringListEditor from '../design/components/StringListEditor.vue'
import AdditionalContextEditor from '../design/components/AdditionalContextEditor.vue'
import { SCENARIO_GUIDED_SECTIONS, BEHAVIOR_SUGGESTIONS, SUPPORT_SUGGESTIONS } from '../design/guided/scenario-questions'
import { hydrateScenarioAnswers } from '../design/guided/scenario-mappings'
import { evaluateScenarioCompleteness } from '../design/guided/scenario-hints'
import GuidedSection from '../design/components/GuidedSection.vue'
import ScenarioSummary from '../design/components/ScenarioSummary.vue'
import CompletenessHints from '../design/components/CompletenessHints.vue'
import SuggestionChips from '../design/components/SuggestionChips.vue'
import { requestConfirmation } from '../design/confirm'
import type { DeveloperBaselineData } from '../design/project-types'
import type { ScenarioAdditionalContextEntry, ScenarioAdditionalContextSemanticType } from '../design/types'
import { findDeveloperBaselineArtifact } from '../design/traceability'

const route = useRoute()
const router = useRouter()

const projectId = computed(() => route.params.projectId as string)
const scenariosListPath = computed(() => `/design/projects/${projectId.value}/scenarios`)
const shapes = computed(() => projectStore.artifacts.shapes)
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
  return projectStore.artifacts.scenarios.find(s => s.id === id) ?? null
})

// Hydrate design store when project record changes
watch(projectRecord, (record) => {
  if (record) {
    openArtifactForEditing('scenario', record)
  }
}, { immediate: true })

const isEditing = computed(() => designStore.editState === 'draft' && !readOnlyMode.value)

const hasData = computed(() => !!projectRecord.value)
const artifactTitle = ref('')
const artifactName = computed(() => artifactTitle.value || projectRecord.value?.title || 'Scenario')

watch(
  projectRecord,
  (record) => {
    artifactTitle.value = record?.title ?? ''
  },
  { immediate: true },
)

// Source data: draft when editing, stored project record otherwise
const scenario = computed(() => {
  if (isEditing.value && designStore.draftScenario) {
    return (designStore.draftScenario as Record<string, any>).scenario ?? {}
  }
  return projectRecord.value?.data?.scenario ?? {}
})

const context = computed(() => scenario.value?.context ?? {})
const contextKeys = computed(() => Object.keys(context.value))
const currentShape = computed(() =>
  shapes.value.find((item) => item.id === projectStore.activeShapeId)
  ?? shapes.value[0]
  ?? null,
)
const serviceOptions = computed(() => {
  const shapeData = ((currentShape.value?.data?.shape ?? currentShape.value?.data) as Record<string, any> | undefined) ?? {}
  const services = Array.isArray(shapeData.services) ? shapeData.services : []
  return services
    .map((service: Record<string, any>) => ({
      id: String(service.id ?? '').trim(),
      label: String(service.name ?? service.id ?? 'Service'),
    }))
    .filter((service) => service.id)
})

function humanizeLabel(value: unknown) {
  if (value == null) return ''
  const text = String(value).trim()
  if (!text) return ''
  return text
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .replace(/\b\w/g, (match) => match.toUpperCase())
}

function renderValue(value: unknown): string {
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (Array.isArray(value)) return value.map((item) => renderValue(item)).join(', ')
  if (typeof value === 'string') return humanizeLabel(value)
  if (typeof value === 'object') return JSON.stringify(value)
  return value == null ? '' : String(value)
}

// --- Draft helpers ---
function setField(path: string, value: any) {
  if (readOnlyMode.value) return
  updateDraftField('scenario', `scenario.${path}`, value)
}

function handleGuidedScenarioAnswer(questionId: string, value: any) {
  if (readOnlyMode.value) return
  updateGuidedScenarioAnswer(questionId, value)
}

const CATEGORY_OPTIONS = ['safety', 'recovery', 'orchestration', 'cross_service', 'observability']
const NAME_PATTERN = /^[a-z0-9_\-]+$/

// Full scenario wrapper object (includes .scenario sub-key)
const scenarioWrapper = computed(() => {
  return projectRecord.value?.data ?? {}
})

const guidedScenarioAnswers = computed(() => {
  if (isEditing.value) return designStore.guidedScenarioAnswers
  return hydrateScenarioAnswers(scenarioWrapper.value)
})

const scenarioHints = computed(() => {
  if (isEditing.value) return designStore.scenarioHints
  return evaluateScenarioCompleteness(scenarioWrapper.value)
})

const currentCategory = computed(() => {
  return scenario.value?.category ?? 'safety'
})

const behaviorSuggestions = computed(() => {
  return BEHAVIOR_SUGGESTIONS[currentCategory.value] ?? []
})

const supportSuggestions = computed(() => {
  return SUPPORT_SUGGESTIONS[currentCategory.value] ?? []
})

/** Context keys managed by guided questions — excluded from the fallback editor */
const GUIDED_CONTEXT_KEYS = new Set([
  'capability', 'side_effect', 'expected_cost', 'budget_limit', 'permissions_state', 'task_id',
])

/** Context entries NOT managed by guided questions — shown in the fallback editor */
const extraContext = computed(() => {
  const ctx = scenario.value?.context ?? {}
  const filtered: Record<string, any> = {}
  for (const [key, value] of Object.entries(ctx)) {
    if (!GUIDED_CONTEXT_KEYS.has(key)) {
      filtered[key] = value
    }
  }
  return filtered
})

type AdditionalContextEntry = {
  key: string
  value: string
  semantic_type: ScenarioAdditionalContextSemanticType
  description: string
}

function normalizeSemanticType(entry: Record<string, any>): ScenarioAdditionalContextSemanticType {
  const semanticType = String(entry.semantic_type ?? '').trim()
  if (
    semanticType === 'actor_context'
    || semanticType === 'business_scope'
    || semanticType === 'time_scope'
    || semanticType === 'participating_services'
    || semanticType === 'orchestration_step'
    || semanticType === 'descriptive_only'
  ) {
    return semanticType
  }
  return 'descriptive_only'
}

function semanticTypeLabel(semanticType: ScenarioAdditionalContextSemanticType): string {
  const labels: Record<ScenarioAdditionalContextSemanticType, string> = {
    descriptive_only: 'Descriptive Only',
    actor_context: 'Actor Context',
    business_scope: 'Business Scope',
    time_scope: 'Time Scope',
    participating_services: 'Participating Services',
    orchestration_step: 'Orchestration Step',
  }
  return labels[semanticType]
}

function legacyParticipatingServices() {
  const stored = Array.isArray(scenario.value?.additional_context) ? scenario.value.additional_context : []
  return stored
    .filter((entry: Record<string, any>) => normalizeSemanticType(entry) === 'participating_services')
    .flatMap((entry: Record<string, any>) =>
      String(entry.value ?? '')
        .split(/\n|,|;/)
        .map((value) => value.trim())
        .filter(Boolean),
    )
}

function legacyOrchestrationSteps() {
  const stored = Array.isArray(scenario.value?.additional_context) ? scenario.value.additional_context : []
  return stored
    .filter((entry: Record<string, any>) => normalizeSemanticType(entry) === 'orchestration_step')
    .flatMap((entry: Record<string, any>) =>
      String(entry.value ?? '')
        .split('\n')
        .map((value) => value.trim())
        .filter(Boolean),
    )
}

const participatingServices = computed<string[]>(() => {
  const explicit = Array.isArray(scenario.value?.participating_services) ? scenario.value.participating_services : []
  return [...new Set([...explicit, ...legacyParticipatingServices()].map((value) => String(value).trim()).filter(Boolean))]
})

const orchestrationSteps = computed<string[]>(() => {
  const explicit = Array.isArray(scenario.value?.orchestration_steps) ? scenario.value.orchestration_steps : []
  return [...new Set([...explicit, ...legacyOrchestrationSteps()].map((value) => String(value).trim()).filter(Boolean))]
})

function setParticipatingServices(serviceIds: string[]) {
  setField('participating_services', serviceIds)
}

function setOrchestrationSteps(value: string) {
  const steps = value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
  setField('orchestration_steps', steps)
}

function toggleParticipatingService(serviceId: string) {
  if (readOnlyMode.value) return
  const set = new Set(participatingServices.value)
  if (set.has(serviceId)) set.delete(serviceId)
  else set.add(serviceId)
  setParticipatingServices([...set])
}

const additionalContextEntries = computed<AdditionalContextEntry[]>(() => {
  const stored = Array.isArray(scenario.value?.additional_context) ? scenario.value.additional_context : []
  if (stored.length > 0) {
    return stored.map((entry: ScenarioAdditionalContextEntry | Record<string, any>) => ({
      key: String(entry.key ?? '').trim(),
      value: entry.value == null ? '' : String(entry.value),
      semantic_type: normalizeSemanticType(entry as Record<string, any>),
      description: String(entry.description ?? '').trim(),
    }))
  }

  return Object.entries(extraContext.value).map(([key, value]) => ({
    key,
    value: value == null ? '' : Array.isArray(value) ? value.join(',') : String(value),
    semantic_type: 'descriptive_only' as const,
    description: '',
  }))
})

/** Merge extra context changes back, preserving guided-managed keys */
function setExtraContext(newExtra: Record<string, any>) {
  const ctx = scenario.value?.context ?? {}
  const merged: Record<string, any> = {}
  // Keep guided-managed keys from the current context
  for (const key of GUIDED_CONTEXT_KEYS) {
    if (ctx[key] !== undefined) {
      merged[key] = ctx[key]
    }
  }
  // Add the user-edited extra keys
  Object.assign(merged, newExtra)
  setField('context', merged)
}

function setAdditionalContextEntries(entries: AdditionalContextEntry[]) {
  const normalizedEntries = entries
    .map((entry) => ({
      key: String(entry.key ?? '').trim(),
      value: String(entry.value ?? '').trim(),
      semantic_type: entry.semantic_type ?? 'descriptive_only',
      description: String(entry.description ?? '').trim(),
    }))

  const mergedExtra: Record<string, any> = {}
  for (const entry of normalizedEntries) {
    if (!entry.key) continue
    const value = entry.value.includes(',') ? entry.value.split(',').map((item) => item.trim()).filter(Boolean) : entry.value
    mergedExtra[entry.key] = value
  }

  setExtraContext(mergedExtra)
  setField(
    'additional_context',
    normalizedEntries.map((entry) => ({
      key: entry.key,
      value: entry.value,
      semantic_type: entry.semantic_type,
      role: entry.semantic_type === 'descriptive_only' ? 'descriptive' : 'design_driving',
      description: entry.description,
    })),
  )
}

const saving = ref(false)
const saveError = ref<string | null>(null)
const expandedHelpCards = ref<Record<string, boolean>>({})
const activeHelpCard = ref<string | null>(null)
const titleDirty = computed(() => (artifactTitle.value.trim() || '') !== (projectRecord.value?.title?.trim() || ''))
const baselineArtifact = computed(() => findDeveloperBaselineArtifact(projectStore.artifacts.pmArtifacts))
const baseline = computed(() =>
  (baselineArtifact.value?.data as DeveloperBaselineData | undefined) ?? null,
)
const artifactIsLockedForDevelopment = computed(() =>
  !!baseline.value && (baseline.value.source_inputs.scenario_ids ?? []).includes(projectRecord.value?.id ?? ''),
)
const artifactIsWorkingRevision = computed(() =>
  !!baseline.value && !artifactIsLockedForDevelopment.value,
)

const SCENARIO_CARD_HELP: Record<string, {
  title: string
  summary: string
  inlineDetails: string[]
  bullets: string[]
  example?: string
  decisionOwner?: string
}> = {
  expectedBehavior: {
    title: 'Expected Behavior',
    summary: 'This section describes what the system should do in this scenario, not how the code happens to do it.',
    inlineDetails: [
      'Use outcome-oriented statements like clarify, deny, restrict, stop safely, preserve lineage, or require approval.',
      'Studio uses these expectations to compare PM intent with developer design, generated service behavior, and evaluation results.',
    ],
    bullets: [
      'These items define the scenario outcome you expect from ANIP-backed services and surrounding logic.',
      'They should stay business-legible and testable. Avoid describing internal implementation details here.',
      'The verification flow later checks whether observed behavior matches these declared expectations.',
    ],
    example: 'For a safe-stop scenario, expected behavior might include finishing the allowed upstream reads, returning clarification at the final step, and preserving auditability.',
    decisionOwner: 'Usually PM or product design, with engineering input when wording must stay measurable.',
  },
  expectedAnipSupport: {
    title: 'Expected ANIP Support',
    summary: 'This section describes what the protocol or service surface must make visible or explicit so the expected behavior can be delivered safely.',
    inlineDetails: [
      'Use this for protocol-visible support like clarification outcomes, approval boundaries, audit visibility, lineage fields, or permission discovery.',
      'This tells Studio and developers what ANIP needs to expose, not just what the business outcome should be.',
    ],
    bullets: [
      'These items describe what ANIP services or adapters must surface so the scenario is implementable and verifiable.',
      'Good entries here often map to capability metadata, explicit outcomes, approval surfaces, or audit/query support.',
      'This is one of the bridges from PM intent into developer design because it names what the service contract must visibly support.',
      'cost_visibility means the caller can see expected spend or resource cost before execution when that matters.',
      'side_effect_visibility means the caller can see what kind of change the action would make before it runs.',
      'structured_failure means blocked or failed work comes back in a machine-readable outcome, not only free-form text.',
      'permission_discovery means the system can make relevant permission or authority posture visible instead of silently failing.',
      'resolution_guidance means the contract helps the caller understand what to do next when work is blocked, denied, or incomplete.',
      'task_id_support means related work can be grouped under a durable task identifier.',
      'parent_invocation_id_support means downstream work can preserve lineage back to the prior invocation or step.',
      'audit_queryability means operators can query and reconstruct what happened from audit records.',
      'cross_service_verification_guidance means the system exposes enough continuity to verify multi-service handoffs and outcomes.',
    ],
    example: 'A compound governed scenario may require clarification-required outcomes, bounded cross-service execution, and audit-and-lineage visibility.',
    decisionOwner: 'Usually PM and architecture together, because this affects the contract and not just the user narrative.',
  },
  additionalContext: {
    title: 'Additional Context',
    summary: 'Use this for scenario facts that do not fit the guided fields, and explicitly mark which ones should become typed inputs for Developer Design.',
    inlineDetails: [
      'Keep descriptive-only facts here when they add useful PM context but should not drive code generation.',
      'Use typed meanings like Actor Context, Business Scope, Time Scope, Participating Services, or Orchestration Step when Developer Design should consume them deterministically.',
      'Participating Services now has its own dedicated field on this page. Use the typed Additional Context meaning only for legacy compatibility or when you need to preserve supporting notes.',
      'Orchestration Steps now also has its own dedicated field on this page. Use the typed Additional Context meaning only for legacy compatibility or supporting notes.',
      'This prevents Studio from guessing semantics later from raw key names or domain-specific conventions.',
    ],
    bullets: [
      'Additional Context supplements the generic guided scenario fields instead of replacing them.',
      'Use descriptive-only entries for reference material that helps explain the scenario but does not belong in the generation contract.',
      'Use typed entries when Product Design already knows the true semantic meaning and wants Developer Design to consume it deterministically.',
      'This is how PM can define actor, scope, time, service participation, and orchestration meaning without forcing developers to guess later.',
      'This is still scenario-level context. It does not define service contracts directly. Instead, it feeds the later developer formalization and generation contract.',
    ],
    example: 'A scenario can include `actor = approver` marked as Actor Context, `region = west` marked as Business Scope, and `validate -> request approval -> stop` marked as Orchestration Step.',
    decisionOwner: 'Usually PM or product design. Engineering should only refine the technical implementation of typed entries, not infer their meaning from scratch.',
  },
  participatingServices: {
    title: 'Participating Services',
    summary: 'This marks which services from the selected Service Design actually participate in the scenario.',
    inlineDetails: [
      'Scenarios stay system-level. They are not automatically one service each.',
      'Use this field to say which service boundaries are involved so later developer formalization and generation do not assume every service participates.',
      'This is the first-class PM-side place to mark service involvement. Do not bury it in Additional Context.',
    ],
    bullets: [
      'Participating Services narrows the scenario to the relevant services while keeping the scenario itself system-level.',
      'Cross-service scenarios can select multiple services. Single-service scenarios can select exactly one.',
      'Developer Design consumes this selection deterministically and uses it to prefill per-scenario participating services in the generation contract.',
      'Verification later uses the same selection to know which services should show relevant behavior or lineage for the scenario.',
    ],
    example: 'A scenario about approval before routing might involve the prioritization service and the downstream execution-facing service, but not every service in the estate.',
    decisionOwner: 'Usually PM or product design, because this is part of the intended service participation for the business scenario.',
  },
  orchestrationSteps: {
    title: 'Orchestration Steps',
    summary: 'This records the ordered steps or service handoffs the business scenario expects the implementation to preserve.',
    inlineDetails: [
      'Write one concrete step per line in the order the scenario should unfold.',
      'Use this when the scenario spans multiple services or needs an explicit bounded flow, approval stop, or safe-stop point.',
      'This is now the first-class PM-side place to define orchestration. Do not rely on Additional Context for the primary path.',
    ],
    bullets: [
      'Orchestration Steps help Developer Design formalize cross-service behavior without guessing from narrative text.',
      'A step can reference a service, a capability, or a boundary like approval required, clarification required, or stop safely.',
      'Generation uses this ordered list to understand where multi-step behavior belongs. Verification uses it to understand what sequence or handoff should be visible.',
      'Keep steps business-legible. They should describe intended handoffs or bounded actions, not low-level internal implementation details.',
    ],
    example: 'Review target cohort -> score and rank -> prepare assignment recommendation -> stop at approval required before execution.',
    decisionOwner: 'Usually PM or product design, because this is part of the intended business flow that development should preserve.',
  },
}

function toggleHelpCard(id: string) {
  expandedHelpCards.value = {
    ...expandedHelpCards.value,
    [id]: !expandedHelpCards.value[id],
  }
}

function openHelpCard(id: string) {
  activeHelpCard.value = id
}

function closeHelpCard() {
  activeHelpCard.value = null
}

function nextRevisionTitle(title: string): string {
  const trimmed = title.trim() || 'Scenario'
  const match = trimmed.match(/^(.*?)(?:\s+Revision\s+(\d+))?$/i)
  if (!match) return `${trimmed} Revision 2`
  const base = (match[1] || trimmed).trim()
  const current = match[2] ? Number(match[2]) : 1
  return `${base} Revision ${current + 1}`
}

function formatSectionValidationMessage(sectionTitle: string, questionPrompt: string | null, message: string) {
  if (questionPrompt) {
    return `Review "${sectionTitle}" -> "${questionPrompt}": ${message}`
  }
  return `Review "${sectionTitle}": ${message}`
}

function formatPathLabel(path: string) {
  const stripped = path.replace(/^scenario\/?/, '').replace(/^\//, '')
  if (!stripped) return 'Scenario'
  return stripped
    .split('/')
    .filter(Boolean)
    .map((part) => /^\d+$/.test(part) ? `#${Number(part) + 1}` : humanizeLabel(part))
    .join(' / ')
}

function formatValidationMessage(path: string, message: string, params?: Record<string, unknown>) {
  const additionalProperty = typeof params?.additionalProperty === 'string' ? params.additionalProperty : ''
  if (additionalProperty) {
    return `${formatPathLabel(path)} has unsupported field "${additionalProperty}".`
  }
  return `${formatPathLabel(path)}: ${message}`
}

const errorsBySection = computed(() => {
  const errors = designStore.validationErrors
  const result: Record<string, { questionErrors: Record<string, string[]>; unmappedErrors: string[] }> = {}
  const globalUnmapped: string[] = []

  const fieldLookup: Record<string, { sectionId: string; questionId: string; sectionTitle: string; questionPrompt: string }> = {}
  const sectionPrefixes: { prefix: string; sectionId: string; sectionTitle: string; questionPrompts: string[] }[] = []

  for (const section of SCENARIO_GUIDED_SECTIONS) {
    result[section.id] = { questionErrors: {}, unmappedErrors: [] }
    for (const q of section.questions) {
      for (const mapping of q.fieldMappings) {
        fieldLookup[mapping.path] = {
          sectionId: section.id,
          questionId: q.id,
          sectionTitle: section.title,
          questionPrompt: q.prompt,
        }
      }
    }
  }

  for (const section of SCENARIO_GUIDED_SECTIONS) {
    const prefixes = new Map<string, string[]>()
    for (const q of section.questions) {
      for (const mapping of q.fieldMappings) {
        const topLevel = mapping.path.split('.')[1] ?? mapping.path.split('.')[0]
        const prompts = prefixes.get(topLevel) ?? []
        prompts.push(q.prompt)
        prefixes.set(topLevel, prompts)
      }
    }
    for (const [prefix, prompts] of prefixes.entries()) {
      sectionPrefixes.push({
        prefix,
        sectionId: section.id,
        sectionTitle: section.title,
        questionPrompts: Array.from(new Set(prompts)),
      })
    }
  }

  for (const err of errors) {
    const stripped = err.path.replace(/^scenario\/?/, '')
    const dotPath = stripped.replace(/\//g, '.')

    let resolvedPath = dotPath
    const requiredMatch = err.message.match(/must have required property '(\w+)'/)
    if (requiredMatch) {
      const prop = requiredMatch[1]
      resolvedPath = dotPath ? `${dotPath}.${prop}` : prop
    }

    const exact = fieldLookup[resolvedPath]
    if (exact) {
      const sec = result[exact.sectionId]
      if (!sec.questionErrors[exact.questionId]) sec.questionErrors[exact.questionId] = []
      sec.questionErrors[exact.questionId].push(err.message)
      continue
    }

    const parts = (resolvedPath || dotPath).split('.')
    const topLevel = parts[1] ?? parts[0]
    const sectionMatch = sectionPrefixes.find(sp => sp.prefix === topLevel)
    if (sectionMatch) {
      result[sectionMatch.sectionId].unmappedErrors.push(
        formatSectionValidationMessage(
          sectionMatch.sectionTitle,
          sectionMatch.questionPrompts.length === 1 ? sectionMatch.questionPrompts[0] : null,
          formatValidationMessage(err.path, err.message, err.params),
        ),
      )
      continue
    }

    globalUnmapped.push(formatValidationMessage(err.path, err.message, err.params))
  }

  return { sections: result, globalUnmapped: Array.from(new Set(globalUnmapped)) }
})

const sectionValidationIssueCount = computed(() =>
  Object.values(errorsBySection.value.sections).reduce((total, section) =>
    total
    + section.unmappedErrors.length
    + Object.values(section.questionErrors).reduce((innerTotal, messages) => innerTotal + messages.length, 0),
  0),
)

const validationIssueSummary = computed(() => {
  const count = designStore.validationErrors.length
  if (count === 0) return 'Scenario structure is valid.'
  const globalCount = errorsBySection.value.globalUnmapped.length
  const sectionCount = sectionValidationIssueCount.value
  if (globalCount > 0 && sectionCount > 0) {
    return `${count} validation issues: ${globalCount} structural and ${sectionCount} section-level.`
  }
  if (globalCount > 0) return `${count} structural validation issue${count === 1 ? '' : 's'} found.`
  return `${count} section-level validation issue${count === 1 ? '' : 's'} found.`
})

async function handleSave() {
  if (readOnlyMode.value || !projectRecord.value || !designStore.draftScenario) return

  saving.value = true
  saveError.value = null
  try {
    if (artifactIsLockedForDevelopment.value) {
      const created = await createScenario(projectRecord.value.project_id, {
        id: `scn-${crypto.randomUUID()}`,
        title: nextRevisionTitle(artifactTitle.value.trim() || projectRecord.value.title || 'Scenario'),
        data: designStore.draftScenario,
      })
      designStore.originalScenario = JSON.parse(JSON.stringify(designStore.draftScenario))
      await refreshArtifacts()
      router.push(`/design/projects/${projectRecord.value.project_id}/scenarios/${created.id}`)
      return
    }

    await updateScenario(projectRecord.value.project_id, projectRecord.value.id, {
      title: artifactTitle.value.trim() || projectRecord.value.title || 'Scenario',
      status: projectRecord.value.status,
      data: designStore.draftScenario,
    })
    designStore.originalScenario = JSON.parse(JSON.stringify(designStore.draftScenario))
    await refreshArtifacts()
  } catch (err) {
    saveError.value = err instanceof Error ? err.message : String(err)
  } finally {
    saving.value = false
  }
}

async function handleDelete() {
  if (readOnlyMode.value || !projectRecord.value) return
  const confirmed = await requestConfirmation({
    title: 'Delete this scenario?',
    message: 'This will permanently remove the scenario artifact from the current project.',
    confirmLabel: 'Delete Scenario',
    cancelLabel: 'Cancel',
    tone: 'danger',
  })
  if (!confirmed) return

  saving.value = true
  saveError.value = null
  try {
    await deleteScenario(projectRecord.value.project_id, projectRecord.value.id)
    await refreshArtifacts()
    router.push(scenariosListPath.value)
  } catch (err) {
    saveError.value = err instanceof Error ? err.message : String(err)
  } finally {
    saving.value = false
  }
}

function handleDiscardTitle() {
  artifactTitle.value = projectRecord.value?.title ?? ''
}

watch(readOnlyMode, (enabled) => {
  if (enabled && designStore.editState === 'draft') {
    discardEdits()
  }
}, { immediate: true })
</script>

<template>
  <div class="scenario-detail" v-if="hasData">
    <div class="layout">
      <!-- Main content -->
      <div class="main">
        <RouterLink class="back-link" :to="scenariosListPath">← Back to Scenarios</RouterLink>
        <div class="page-header">
          <div class="page-header-main">
            <label class="title-field">
              <span class="title-label">Scenario Title</span>
              <input
                v-if="isEditing"
                class="title-input"
                type="text"
                v-model="artifactTitle"
                placeholder="Name this scenario"
              />
              <h1 v-else class="page-title">Scenario: {{ artifactName }}</h1>
            </label>
            <p class="page-intro">
              This title is the human-facing Product Design artifact name. Keep it readable; the internal scenario slug and category are managed separately below.
            </p>
            <div v-if="artifactIsLockedForDevelopment" class="revision-banner locked">
              Locked for development. Saving changes will create a new working revision instead of modifying the locked baseline scenario.
            </div>
            <div v-else-if="artifactIsWorkingRevision" class="revision-banner working">
              Working revision. This scenario is newer than the current locked developer baseline.
            </div>
          </div>
          <button v-if="isEditing" class="delete-btn" type="button" @click="handleDelete">
            Delete Scenario
          </button>
        </div>

        <div v-if="readOnlyMode" class="readonly-banner">
          {{ readOnlyReason }}
        </div>

        <div class="mode-toggle">
          <button class="mode-btn" :class="{ active: designStore.scenarioMode === 'guided' }" @click="setScenarioMode('guided')" type="button">Guided</button>
          <button class="mode-btn" :class="{ active: designStore.scenarioMode === 'advanced' }" @click="setScenarioMode('advanced')" type="button">Advanced</button>
        </div>

        <EditorToolbar
          artifact="scenario"
          :canSave="true"
          :saving="saving"
          :saveError="saveError"
          :externalDirty="titleDirty"
          :readOnly="readOnlyMode"
          @save="handleSave"
          @discard="handleDiscardTitle"
        />

        <section
          class="validation-overview"
          :class="{ invalid: designStore.validationErrors.length > 0, valid: designStore.validationErrors.length === 0 }"
        >
          <div>
            <strong>{{ designStore.validationErrors.length > 0 ? 'Validation Needs Attention' : 'Validation Ready' }}</strong>
            <p>{{ validationIssueSummary }}</p>
          </div>
          <ul v-if="errorsBySection.globalUnmapped.length > 0" class="validation-overview-list">
            <li v-for="err in errorsBySection.globalUnmapped" :key="err">{{ err }}</li>
          </ul>
          <p v-else-if="sectionValidationIssueCount > 0" class="validation-overview-note">
            Section-specific issues are highlighted directly in the guided sections below.
          </p>
        </section>

        <template v-if="designStore.scenarioMode === 'guided'">
          <ScenarioSummary :scenario="designStore.draftScenario ?? scenarioWrapper" />
          <CompletenessHints :hints="scenarioHints" />

          <div class="mapping-toggle" v-if="isEditing">
            <label class="mapping-label">
              <input type="checkbox" :checked="designStore.showFieldMappings" @change="designStore.showFieldMappings = !designStore.showFieldMappings" />
              Show technical field mappings
            </label>
          </div>

          <GuidedSection
            v-for="section in SCENARIO_GUIDED_SECTIONS"
            :key="section.id"
            :section="section"
            :answers="guidedScenarioAnswers"
            :showMappings="designStore.showFieldMappings"
            :readonly="!isEditing"
            :questionErrors="errorsBySection.sections[section.id]?.questionErrors"
            :unmappedErrors="errorsBySection.sections[section.id]?.unmappedErrors"
            @update:answer="handleGuidedScenarioAnswer"
          />

          <div class="guided-section-card">
            <div class="guided-card-header">
              <div>
                <h2 class="guided-section-title">Execution Context</h2>
                <p class="guided-section-desc">Mark this as not applicable when the scenario does not need extra execution context beyond its narrative and typed scenario fields.</p>
              </div>
            </div>
            <label class="checkbox-row">
              <input
                type="checkbox"
                :checked="Boolean(scenario.context_not_applicable)"
                :disabled="!isEditing"
                @change="setField('context_not_applicable', ($event.target as HTMLInputElement).checked)"
              />
              <span>Execution context is not applicable for this scenario.</span>
            </label>
          </div>

          <!-- Expected Behavior with suggestions -->
          <div class="guided-section-card">
            <div class="guided-card-header">
              <div>
                <h2 class="guided-section-title">Expected Behavior</h2>
                <p class="guided-section-desc">What should the system do in this situation?</p>
              </div>
              <div class="question-help-actions">
                <button class="help-link" type="button" @click="toggleHelpCard('expectedBehavior')">
                  {{ expandedHelpCards.expectedBehavior ? 'Hide help' : 'What does this mean?' }}
                </button>
                <button class="help-link secondary" type="button" @click="openHelpCard('expectedBehavior')">
                  More detail
                </button>
              </div>
            </div>
            <div v-if="expandedHelpCards.expectedBehavior" class="inline-help">
              <p class="inline-help-summary">{{ SCENARIO_CARD_HELP.expectedBehavior.summary }}</p>
              <ul class="inline-help-list">
                <li v-for="detail in SCENARIO_CARD_HELP.expectedBehavior.inlineDetails" :key="detail">{{ detail }}</li>
              </ul>
            </div>
            <SuggestionChips
              :modelValue="scenario.expected_behavior ?? []"
              :suggestions="behaviorSuggestions"
              :readonly="!isEditing"
              placeholder="Add custom behavior..."
              @update:modelValue="setField('expected_behavior', $event)"
            />
          </div>

          <!-- Expected ANIP Support with suggestions -->
          <div class="guided-section-card">
            <div class="guided-card-header">
              <div>
                <h2 class="guided-section-title">Expected ANIP Support</h2>
                <p class="guided-section-desc">What should the protocol or service contract make visible or explicit?</p>
              </div>
              <div class="question-help-actions">
                <button class="help-link" type="button" @click="toggleHelpCard('expectedAnipSupport')">
                  {{ expandedHelpCards.expectedAnipSupport ? 'Hide help' : 'What does this mean?' }}
                </button>
                <button class="help-link secondary" type="button" @click="openHelpCard('expectedAnipSupport')">
                  More detail
                </button>
              </div>
            </div>
            <div v-if="expandedHelpCards.expectedAnipSupport" class="inline-help">
              <p class="inline-help-summary">{{ SCENARIO_CARD_HELP.expectedAnipSupport.summary }}</p>
              <ul class="inline-help-list">
                <li v-for="detail in SCENARIO_CARD_HELP.expectedAnipSupport.inlineDetails" :key="detail">{{ detail }}</li>
              </ul>
            </div>
            <SuggestionChips
              :modelValue="scenario.expected_anip_support ?? []"
              :suggestions="supportSuggestions"
              :readonly="!isEditing"
              :allowCustom="false"
              @update:modelValue="setField('expected_anip_support', $event)"
            />
          </div>

          <div class="guided-section-card">
            <div class="guided-card-header">
              <div>
                <h2 class="guided-section-title">Participating Services</h2>
                <p class="guided-section-desc">Which services from the selected Service Design participate in this scenario?</p>
              </div>
              <div class="question-help-actions">
                <button class="help-link" type="button" @click="toggleHelpCard('participatingServices')">
                  {{ expandedHelpCards.participatingServices ? 'Hide help' : 'What does this mean?' }}
                </button>
                <button class="help-link secondary" type="button" @click="openHelpCard('participatingServices')">
                  More detail
                </button>
              </div>
            </div>
            <div v-if="expandedHelpCards.participatingServices" class="inline-help">
              <p class="inline-help-summary">{{ SCENARIO_CARD_HELP.participatingServices.summary }}</p>
              <ul class="inline-help-list">
                <li v-for="detail in SCENARIO_CARD_HELP.participatingServices.inlineDetails" :key="detail">{{ detail }}</li>
              </ul>
            </div>
            <div v-if="serviceOptions.length === 0" class="empty-state subtle-empty-state">
              No services are available yet. Define a Service Design first if you want to mark participating services explicitly.
            </div>
            <div v-else class="service-chip-grid">
              <button
                v-for="service in serviceOptions"
                :key="service.id"
                class="service-chip"
                :class="{ active: participatingServices.includes(service.id) }"
                type="button"
                :disabled="!isEditing"
                @click="toggleParticipatingService(service.id)"
              >
                {{ service.label }}
              </button>
            </div>
          </div>

          <div class="guided-section-card">
            <div class="guided-card-header">
              <div>
                <h2 class="guided-section-title">Orchestration Steps</h2>
                <p class="guided-section-desc">What ordered steps or service handoffs should this scenario preserve?</p>
              </div>
              <div class="question-help-actions">
                <button class="help-link" type="button" @click="toggleHelpCard('orchestrationSteps')">
                  {{ expandedHelpCards.orchestrationSteps ? 'Hide help' : 'What does this mean?' }}
                </button>
                <button class="help-link secondary" type="button" @click="openHelpCard('orchestrationSteps')">
                  More detail
                </button>
              </div>
            </div>
            <div v-if="expandedHelpCards.orchestrationSteps" class="inline-help">
              <p class="inline-help-summary">{{ SCENARIO_CARD_HELP.orchestrationSteps.summary }}</p>
              <ul class="inline-help-list">
                <li v-for="detail in SCENARIO_CARD_HELP.orchestrationSteps.inlineDetails" :key="detail">{{ detail }}</li>
              </ul>
            </div>
            <label class="field field-wide">
              <textarea
                class="form-textarea"
                rows="4"
                :value="orchestrationSteps.join('\n')"
                placeholder="One step per line, in the intended execution order."
                :disabled="!isEditing"
                @input="setOrchestrationSteps(($event.target as HTMLTextAreaElement).value)"
              />
            </label>
          </div>

          <!-- Additional context editor/read-only panel -->
          <div class="guided-section-card" v-if="isEditing || additionalContextEntries.length > 0">
            <div class="guided-card-header">
              <div>
                <h2 class="guided-section-title">Additional Context</h2>
                <p class="guided-section-desc">Add domain-specific context here and mark which entries should become typed inputs for Developer Design.</p>
              </div>
              <div class="question-help-actions">
                <button class="help-link" type="button" @click="toggleHelpCard('additionalContext')">
                  {{ expandedHelpCards.additionalContext ? 'Hide help' : 'What does this mean?' }}
                </button>
                <button class="help-link secondary" type="button" @click="openHelpCard('additionalContext')">
                  More detail
                </button>
              </div>
            </div>
            <div v-if="expandedHelpCards.additionalContext" class="inline-help">
              <p class="inline-help-summary">{{ SCENARIO_CARD_HELP.additionalContext.summary }}</p>
              <ul class="inline-help-list">
                <li v-for="detail in SCENARIO_CARD_HELP.additionalContext.inlineDetails" :key="detail">{{ detail }}</li>
              </ul>
            </div>
            <AdditionalContextEditor
              v-if="isEditing"
              :modelValue="additionalContextEntries"
              @update:modelValue="setAdditionalContextEntries($event)"
            />
            <div v-else class="context-display-list">
              <div v-for="entry in additionalContextEntries" :key="entry.key" class="context-display-item">
                <div class="context-display-row">
                  <div class="context-display-main">
                    <div class="context-display-key">{{ humanizeLabel(entry.key) }}</div>
                    <div class="context-display-value">{{ renderValue(entry.value) }}</div>
                  </div>
                  <span class="context-role-badge" :class="entry.semantic_type === 'descriptive_only' ? 'descriptive' : 'design-driving'">
                    {{ semanticTypeLabel(entry.semantic_type) }}
                  </span>
                </div>
                <p v-if="entry.description" class="context-display-description">{{ entry.description }}</p>
              </div>
            </div>
          </div>

          <div v-if="activeHelpCard" class="help-dialog-backdrop" @click.self="closeHelpCard">
            <div class="help-dialog">
              <div class="help-dialog-header">
                <h3 class="help-dialog-title">{{ SCENARIO_CARD_HELP[activeHelpCard].title }}</h3>
                <button class="help-dialog-close" type="button" @click="closeHelpCard">Close</button>
              </div>
              <p class="help-dialog-summary">{{ SCENARIO_CARD_HELP[activeHelpCard].summary }}</p>
              <ul class="help-dialog-list">
                <li v-for="item in SCENARIO_CARD_HELP[activeHelpCard].bullets" :key="item">{{ item }}</li>
              </ul>
              <div v-if="SCENARIO_CARD_HELP[activeHelpCard].example" class="help-dialog-block">
                <span class="help-dialog-label">Example</span>
                <p class="help-dialog-text">{{ SCENARIO_CARD_HELP[activeHelpCard].example }}</p>
              </div>
              <div v-if="SCENARIO_CARD_HELP[activeHelpCard].decisionOwner" class="help-dialog-block">
                <span class="help-dialog-label">Who usually decides this?</span>
                <p class="help-dialog-text">{{ SCENARIO_CARD_HELP[activeHelpCard].decisionOwner }}</p>
              </div>
            </div>
          </div>
        </template>

        <template v-else>
        <!-- Editable fields when in draft mode -->
        <template v-if="isEditing">
          <div class="section">
            <h2>Scenario Details</h2>
            <div class="form-grid">
              <label class="form-label">Name</label>
              <div class="form-field">
                <input
                  class="form-input"
                  type="text"
                  :value="scenario.name"
                  @input="setField('name', ($event.target as HTMLInputElement).value)"
                  placeholder="e.g. budget_exhaustion"
                  :pattern="NAME_PATTERN.source"
                />
                <span
                  class="field-hint"
                  :class="{ error: scenario.name && !NAME_PATTERN.test(scenario.name) }"
                >
                  lowercase, digits, hyphens, underscores only
                </span>
              </div>
              <label class="form-label">Category</label>
              <select
                class="form-select"
                :value="scenario.category"
                @change="setField('category', ($event.target as HTMLSelectElement).value)"
              >
                <option v-for="cat in CATEGORY_OPTIONS" :key="cat" :value="cat">{{ cat }}</option>
              </select>
              <label class="form-label">Narrative</label>
              <textarea
                class="form-textarea"
                :value="scenario.narrative"
                @input="setField('narrative', ($event.target as HTMLTextAreaElement).value)"
                rows="4"
                placeholder="Describe the scenario..."
              ></textarea>
            </div>
          </div>

          <div class="section">
            <h2>Context</h2>
            <label class="checkbox-row">
              <input
                type="checkbox"
                :checked="Boolean(scenario.context_not_applicable)"
                @change="setField('context_not_applicable', ($event.target as HTMLInputElement).checked)"
              />
              <span>Execution context is not applicable for this scenario.</span>
            </label>
            <KeyValueEditor
              :modelValue="scenario.context ?? {}"
              @update:modelValue="setField('context', $event)"
            />
          </div>

          <div class="section">
            <h2>Participating Services</h2>
            <p class="section-copy">
              Keep the scenario system-level, but mark which services actually participate so later developer formalization and generation do not have to infer service involvement.
            </p>
            <div v-if="serviceOptions.length === 0" class="empty-state subtle-empty-state">
              No services are available yet. Define a Service Design first if you want to mark participating services explicitly.
            </div>
            <div v-else class="service-chip-grid">
              <button
                v-for="service in serviceOptions"
                :key="service.id"
                class="service-chip"
                :class="{ active: participatingServices.includes(service.id) }"
                type="button"
                @click="toggleParticipatingService(service.id)"
              >
                {{ service.label }}
              </button>
            </div>
          </div>

          <div class="section">
            <h2>Orchestration Steps</h2>
            <p class="section-copy">
              Write the intended ordered steps or service handoffs for this scenario, one per line. Developer Design and verification use this as the PM-owned flow instead of inferring orchestration from narrative text.
            </p>
            <textarea
              class="form-textarea"
              :value="orchestrationSteps.join('\n')"
              @input="setOrchestrationSteps(($event.target as HTMLTextAreaElement).value)"
              rows="5"
              placeholder="One step per line, in execution order."
            ></textarea>
          </div>

          <div class="section">
            <h2>Expected Behavior</h2>
            <StringListEditor
              :modelValue="scenario.expected_behavior ?? []"
              @update:modelValue="setField('expected_behavior', $event)"
            />
          </div>

          <div class="section">
            <h2>Expected ANIP Support</h2>
            <SuggestionChips
              :modelValue="scenario.expected_anip_support ?? []"
              :suggestions="supportSuggestions"
              :readonly="!isEditing"
              :allowCustom="false"
              @update:modelValue="setField('expected_anip_support', $event)"
            />
          </div>
        </template>

        <!-- Read-only display -->
        <template v-else>
          <span class="category-badge">{{ humanizeLabel(scenario.category) }}</span>

          <p class="narrative">{{ scenario.narrative }}</p>

          <!-- Scenario Context -->
          <div class="section" v-if="contextKeys.length">
            <h2>Scenario Context</h2>
            <dl class="info-grid">
              <template v-for="key in contextKeys" :key="key">
                <dt>{{ humanizeLabel(key) }}</dt>
                <dd>{{ renderValue(context[key]) }}</dd>
              </template>
            </dl>
          </div>
          <div class="section" v-else-if="scenario.context_not_applicable">
            <h2>Scenario Context</h2>
            <p class="section-copy">Marked not applicable for this scenario.</p>
          </div>

          <div class="section" v-if="participatingServices.length">
            <h2>Participating Services</h2>
            <div class="service-badge-row">
              <span
                v-for="service in serviceOptions.filter((option) => participatingServices.includes(option.id))"
                :key="service.id"
                class="service-badge"
              >
                {{ service.label }}
              </span>
            </div>
          </div>

          <div class="section" v-if="orchestrationSteps.length">
            <h2>Orchestration Steps</h2>
            <ol class="item-list ordered-list">
              <li v-for="(step, index) in orchestrationSteps" :key="`${step}-${index}`">{{ step }}</li>
            </ol>
          </div>

          <!-- Expected Behavior -->
          <div class="section">
            <h2>Expected Behavior</h2>
            <ul class="item-list">
              <li v-for="(item, i) in scenario.expected_behavior" :key="i">{{ humanizeLabel(item) }}</li>
            </ul>
          </div>

          <!-- Expected ANIP Support -->
          <div class="section">
            <h2>Expected ANIP Support</h2>
            <ul class="item-list">
              <li v-for="(item, i) in scenario.expected_anip_support" :key="i">{{ humanizeLabel(item) }}</li>
            </ul>
          </div>
        </template>
        </template>
      </div>
    </div>
  </div>
  <div v-else class="not-found">Scenario not found.</div>
</template>

<style scoped>
.scenario-detail {
  padding: 2rem;
  width: 100%;
  max-width: none;
}

.back-link {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  margin-bottom: 0.95rem;
  font-size: 13px;
  font-weight: 600;
  color: var(--accent);
  text-decoration: none;
}

.back-link:hover {
  color: var(--accent-hover);
}

.layout {
  display: block;
}

.main {
  min-width: 0;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1.25rem;
  margin-bottom: 1.15rem;
}

.page-header-main {
  flex: 1;
  min-width: 0;
}

.title-field {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.title-label {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.title-input {
  width: 100%;
  min-height: 3rem;
  padding: 0.9rem 1rem;
  border-radius: 18px;
  border: 1px solid var(--surface-border-card);
  background: var(--surface-depth-card);
  color: var(--text-primary);
  font-size: 1.45rem;
  font-weight: 700;
  line-height: 1.2;
}

.page-intro {
  margin: 0.65rem 0 0;
  color: var(--text-secondary);
  line-height: 1.55;
}

.revision-banner {
  margin-top: 1rem;
  padding: 0.9rem 1rem;
  border-radius: 14px;
  font-size: 14px;
  line-height: 1.5;
}

.revision-banner.locked {
  background: rgba(251, 191, 36, 0.12);
  border: 1px solid rgba(251, 191, 36, 0.32);
  color: #fde68a;
}

.revision-banner.working {
  background: rgba(59, 130, 246, 0.12);
  border: 1px solid rgba(96, 165, 250, 0.32);
  color: #bfdbfe;
}

.readonly-banner {
  margin-bottom: 1rem;
  padding: 0.9rem 1rem;
  border-radius: 14px;
  border: 1px solid rgba(251, 191, 36, 0.28);
  background: rgba(251, 191, 36, 0.12);
  color: #fbbf24;
  font-size: 14px;
  line-height: 1.5;
}

.page-title {
  font-size: 28px;
  line-height: 1.15;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 0.5rem;
}

.delete-btn {
  padding: 0.75rem 1rem;
  border-radius: 12px;
  border: 1px solid rgba(248, 113, 113, 0.28);
  background: rgba(127, 29, 29, 0.22);
  color: #fecaca;
  font-size: 0.92rem;
  font-weight: 600;
  cursor: pointer;
}

.category-badge {
  display: inline-flex;
  align-items: center;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 0.25rem 0.65rem;
  border-radius: 999px;
  background: rgba(99, 102, 241, 0.16);
  border: 1px solid rgba(99, 102, 241, 0.28);
  color: #c7d2fe;
  margin-bottom: 0.5rem;
}

.result-row {
  margin-bottom: 1rem;
}

.result-badge {
  display: inline-block;
  font-size: 12px;
  font-weight: 700;
  padding: 3px 12px;
  border-radius: 12px;
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

.result-none {
  background: rgba(128, 128, 128, 0.15);
  color: var(--text-muted);
}

.narrative {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 0 0 1.35rem;
}

.section {
  margin-bottom: 1.35rem;
  background: var(--surface-depth-card);
  border: 1px solid var(--surface-border-card);
  border-radius: 20px;
  padding: 1.3rem;
}

.section h2 {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 0.9rem;
}

.section-copy {
  margin: 0 0 12px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-secondary);
}

.item-list {
  list-style: disc;
  padding-left: 1.25rem;
  margin: 0;
}

.ordered-list {
  list-style: decimal;
}

.item-list li {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.65;
  margin-bottom: 0.25rem;
}

.info-grid {
  display: grid;
  grid-template-columns: 200px 1fr;
  gap: 0.5rem 1rem;
  margin: 0;
}

.info-grid dt {
  font-size: 12px;
  color: var(--text-muted);
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.info-grid dd {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0;
  word-break: break-word;
}

.not-found {
  padding: 2rem;
  color: var(--text-muted);
}

/* ---- Edit-mode form controls ---- */
.form-grid {
  display: grid;
  grid-template-columns: 200px 1fr;
  gap: 0.75rem 1rem;
  align-items: start;
}

.form-label {
  font-size: 13px;
  color: var(--text-muted);
  font-weight: 500;
  padding-top: 6px;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.field-hint {
  font-size: 11px;
  color: var(--text-muted);
}

.field-hint.error {
  color: var(--error);
}

.form-input {
  font-size: 13px;
  padding: 0.65rem 0.75rem;
  background: var(--surface-depth-card);
  border: 1px solid var(--surface-border-card);
  border-radius: 12px;
  color: var(--text-primary);
  outline: none;
  width: 100%;
  box-sizing: border-box;
}

.form-input:focus {
  border-color: var(--border-focus);
}

.form-select {
  font-size: 13px;
  padding: 0.65rem 0.75rem;
  background: var(--surface-depth-card);
  border: 1px solid var(--surface-border-card);
  border-radius: 12px;
  color: var(--text-primary);
  outline: none;
  cursor: pointer;
}

.form-select:focus {
  border-color: var(--border-focus);
}

.form-textarea {
  font-size: 13px;
  padding: 0.75rem 0.85rem;
  background: var(--surface-depth-card);
  border: 1px solid var(--surface-border-card);
  border-radius: 12px;
  color: var(--text-secondary);
  outline: none;
  resize: vertical;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  font-family: inherit;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.form-textarea:focus {
  border-color: var(--border-focus);
}

.mode-toggle {
  display: flex;
  gap: 0;
  margin-bottom: 1rem;
  border: 1px solid var(--surface-border-card);
  border-radius: 12px;
  overflow: hidden;
  width: fit-content;
  background: var(--surface-depth-card);
}

.mode-btn {
  padding: 0.62rem 1.35rem;
  font-size: 13px;
  font-weight: 700;
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition);
}

.mode-btn.active {
  background: var(--accent);
  color: #fff;
}

.mode-btn:hover:not(.active) {
  background: rgba(148, 163, 184, 0.12);
  color: var(--text-primary);
}

.mapping-toggle {
  margin-bottom: 1rem;
}

.mapping-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-muted);
  cursor: pointer;
}

.mapping-label input[type="checkbox"] {
  cursor: pointer;
}

.guided-section-card {
  background: var(--surface-depth-card);
  border: 1px solid var(--surface-border-card);
  border-radius: 20px;
  padding: 1.3rem;
  margin-bottom: 1.35rem;
}

.guided-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1.25rem;
  margin-bottom: 0.85rem;
}

.guided-section-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 0.35rem;
}

.guided-section-desc {
  font-size: 13px;
  color: var(--text-muted);
  margin: 0;
  line-height: 1.5;
}

.subtle-empty-state {
  border: 1px dashed rgba(148, 163, 184, 0.2);
  border-radius: 14px;
  padding: 0.85rem 0.95rem;
  background: var(--surface-depth-card);
  font-size: 13px;
}

.service-chip-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
}

.service-chip {
  border: 1px solid var(--surface-border-card);
  background: var(--surface-depth-card);
  color: var(--text-secondary);
  border-radius: 999px;
  padding: 0.5rem 0.9rem;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.service-chip.active {
  border-color: rgba(59, 130, 246, 0.4);
  background: rgba(59, 130, 246, 0.16);
  color: #bfdbfe;
}

.service-chip:disabled {
  cursor: default;
  opacity: 0.7;
}

.question-help-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.help-link {
  border: none;
  background: transparent;
  color: var(--accent, #8b8cff);
  font-size: 12px;
  font-weight: 700;
  padding: 0;
  cursor: pointer;
}

.help-link.secondary {
  color: var(--text-muted);
}

.inline-help {
  margin: 0 0 1rem;
  padding: 0.85rem 0.95rem;
  border-radius: 14px;
  background: rgba(96, 165, 250, 0.08);
  border: 1px solid rgba(96, 165, 250, 0.18);
}

.inline-help-summary {
  margin: 0 0 8px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-secondary);
}

.inline-help-list {
  margin: 0;
  padding-left: 18px;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.context-display-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.context-display-item {
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  padding: 0.85rem 0.95rem;
  background: var(--surface-depth-card);
}

.context-display-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.context-display-main {
  min-width: 0;
}

.context-display-key {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.context-display-value {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
  word-break: break-word;
}

.context-display-description {
  margin: 10px 0 0;
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.5;
}

.context-role-badge {
  flex-shrink: 0;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  border-radius: 999px;
  padding: 4px 8px;
}

.context-role-badge.design-driving {
  background: rgba(96, 165, 250, 0.14);
  color: rgb(147, 197, 253);
}

.context-role-badge.descriptive {
  background: rgba(148, 163, 184, 0.12);
  color: var(--text-muted);
}

.service-badge-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.service-badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 0.28rem 0.7rem;
  font-size: 12px;
  font-weight: 700;
  background: rgba(59, 130, 246, 0.14);
  color: #93c5fd;
  border: 1px solid rgba(59, 130, 246, 0.24);
}

.checkbox-row {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  margin-bottom: 0.95rem;
  color: var(--text-secondary);
}

.validation-overview {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin: 1.15rem 0 1.35rem;
  padding: 1rem 1.1rem;
  border-radius: 18px;
  border: 1px solid rgba(52, 211, 153, 0.24);
  background:
    radial-gradient(circle at top left, rgba(16, 185, 129, 0.12), transparent 34%),
    rgba(6, 78, 59, 0.14);
}

.validation-overview.invalid {
  border-color: rgba(248, 113, 113, 0.32);
  background:
    radial-gradient(circle at top left, rgba(248, 113, 113, 0.12), transparent 34%),
    rgba(127, 29, 29, 0.18);
}

.validation-overview strong {
  display: block;
  margin-bottom: 0.35rem;
  color: var(--text-primary);
}

.validation-overview p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.5;
}

.validation-overview-list {
  flex: 1;
  min-width: 280px;
  max-width: 620px;
  margin: 0;
  padding-left: 1.1rem;
  color: #fecaca;
  font-size: 13px;
  line-height: 1.55;
}

.validation-overview-note {
  max-width: 420px;
}

.help-dialog-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(10, 10, 15, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  z-index: 200;
}

.help-dialog {
  width: min(720px, 100%);
  max-height: min(80vh, 760px);
  overflow: auto;
  background: var(--bg-panel, #13131d);
  border: 1px solid var(--border);
  border-radius: 12px;
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.35);
  padding: 20px 22px;
}

.help-dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.help-dialog-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}

.help-dialog-close {
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-secondary);
  border-radius: 8px;
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.help-dialog-summary,
.help-dialog-text {
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-secondary);
  margin: 0;
}

.help-dialog-list {
  margin: 14px 0;
  padding-left: 18px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.help-dialog-block {
  margin-top: 14px;
}

.help-dialog-label {
  display: block;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: 4px;
}

@media (max-width: 1100px) {
  .layout {
    grid-template-columns: 1fr;
  }

  .quick-links {
    width: auto;
    position: static;
  }
}
</style>
