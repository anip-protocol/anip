<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  applyReadinessFindingReviews,
  analyzeAgentConsumptionReadiness,
  normalizeReadinessFindingReviews,
} from '../design/agent-consumption-readiness'
import {
  buildAgentConsumabilityMetadata,
  normalizeAgentConsumabilityReviews,
  type AgentConsumabilityBusinessLanguageRule,
  type AgentConsumabilityCapabilityReview,
  type AgentConsumabilityIntentRule,
  type AgentConsumabilitySelectionHint,
} from '../design/agent-consumability'
import {
  buildDeveloperDefinitionData,
  findDeveloperDefinitionArtifact,
} from '../design/developer-definition'
import { developerLabel } from '../design/developer-vocabulary'
import { formatEffectList } from '../design/effect-vocabulary'
import { createPmArtifact, updatePmArtifact } from '../design/project-api'
import { loadProject, projectStore } from '../design/project-store'
import type {
  DeveloperBaselineData,
  DeveloperDefinitionData,
  TraceabilityRecordData,
} from '../design/project-types'
import {
  DESIGN_TRACEABILITY_ARTIFACT_TYPE,
  buildTraceabilityRecord,
  developerBaselineMatchesCurrentContext,
  findDeveloperBaselineArtifact,
  findTraceabilityArtifact,
  traceabilityArtifactId,
} from '../design/traceability'

const route = useRoute()
const router = useRouter()

const projectId = computed(() => route.params.projectId as string)
const project = computed(() => projectStore.activeProject)
const isGovernedFrontingProject = computed(() => project.value?.project_type === 'governed_service_project')
const requirements = computed(() => projectStore.artifacts.requirements)
const scenarios = computed(() => projectStore.artifacts.scenarios)
const shapes = computed(() => projectStore.artifacts.shapes)
const saving = ref(false)
const saveError = ref<string | null>(null)
const savedMessage = ref<string | null>(null)
const expandedEditorId = ref<string | null>(null)
const reviewDrafts = ref<Record<string, AgentConsumabilityCapabilityReview>>({})
const businessRuleDrafts = ref<Record<string, {
  meaning: string
  anyTerms: string
  allTerms: string
  excludeTerms: string
  interpretation: string
  action: NonNullable<AgentConsumabilityBusinessLanguageRule['agent_action']>
}>>({})
const selectionHintDrafts = ref<Record<string, {
  anyTerms: string
  allTerms: string
  excludeTerms: string
}>>({})

async function ensureLoaded() {
  if (!projectId.value) return
  if (projectStore.activeProject?.id === projectId.value) return
  await loadProject(projectId.value)
}

const baselineArtifact = computed(() => findDeveloperBaselineArtifact(projectStore.artifacts.pmArtifacts))
const baseline = computed(() =>
  (baselineArtifact.value?.data as DeveloperBaselineData | undefined) ?? null,
)

const traceabilityArtifact = computed(() => findTraceabilityArtifact(projectStore.artifacts.pmArtifacts))
const traceabilityRecord = computed(() =>
  (traceabilityArtifact.value?.data as TraceabilityRecordData | undefined) ?? null,
)

const developerDefinitionArtifact = computed(() => findDeveloperDefinitionArtifact(projectStore.artifacts.pmArtifacts))
const savedDeveloperDefinition = computed(() =>
  (developerDefinitionArtifact.value?.data as DeveloperDefinitionData | undefined) ?? null,
)

const lockedRequirements = computed(() =>
  requirements.value.find((item) => item.id === baseline.value?.source_inputs.requirements_id)
  ?? null,
)

const lockedScenarios = computed(() =>
  scenarios.value.filter((item) => baseline.value?.source_inputs.scenario_ids.includes(item.id)),
)

const lockedShape = computed(() =>
  shapes.value.find((item) => item.id === baseline.value?.source_inputs.shape_id)
  ?? null,
)

const baselineAligned = computed(() =>
  developerBaselineMatchesCurrentContext({
    baseline: baseline.value,
    requirements: lockedRequirements.value,
    scenarios: lockedScenarios.value,
    shape: lockedShape.value,
    pmArtifacts: projectStore.artifacts.pmArtifacts,
  }),
)

const developerDefinition = computed<DeveloperDefinitionData | null>(() => {
  if (
    project.value
    && baseline.value
    && baselineAligned.value
    && lockedRequirements.value
    && lockedScenarios.value.length > 0
    && (isGovernedFrontingProject.value || lockedShape.value)
  ) {
    return buildDeveloperDefinitionData({
      project: project.value,
      baseline: baseline.value,
      requirements: lockedRequirements.value,
      scenarios: lockedScenarios.value,
      shape: lockedShape.value,
      pmArtifacts: projectStore.artifacts.pmArtifacts,
      existing: savedDeveloperDefinition.value,
    })
  }
  return savedDeveloperDefinition.value
})

const readinessReport = computed(() =>
  analyzeAgentConsumptionReadiness(developerDefinition.value),
)

const reviewedReadinessReport = computed(() =>
  applyReadinessFindingReviews(
    readinessReport.value,
    normalizeReadinessFindingReviews(traceabilityRecord.value?.agent_consumption_readiness?.finding_reviews),
  ),
)

const agentConsumabilityMetadata = computed(() =>
  buildAgentConsumabilityMetadata({
    definition: developerDefinition.value,
    readiness: reviewedReadinessReport.value,
    manualReviews: normalizeAgentConsumabilityReviews(traceabilityRecord.value?.agent_consumability_reviews),
  }),
)

const capabilityTitleById = computed(() =>
  new Map((developerDefinition.value?.capability_formalizations ?? []).map((capability) => [
    capability.capability_id,
    capability.title || developerLabel(capability.capability_id),
  ])),
)

const capabilityRows = computed(() =>
  Object.entries(agentConsumabilityMetadata.value.capabilities)
    .map(([id, metadata]) => ({
      id,
      title: capabilityTitleById.value.get(id) ?? developerLabel(id),
      metadata,
    }))
    .sort((a, b) => a.title.localeCompare(b.title)),
)

const appOwnedCapabilities = computed(() =>
  capabilityRows.value.filter(({ metadata }) =>
    metadata.app_glue?.required
    || metadata.derived_target_owner?.owner === 'app'
    || (metadata.intent_rules ?? []).some((rule) => rule.owner === 'agent_app_glue')
    || (metadata.business_language_rules ?? []).some((rule) => rule.owner === 'agent_app_glue'),
  ),
)

const businessLanguageRules = computed(() =>
  capabilityRows.value.flatMap(({ id, title, metadata }) =>
    (metadata.business_language_rules ?? []).map((rule) => ({ capabilityId: id, capabilityTitle: title, rule })),
  ),
)

const intentRules = computed(() =>
  capabilityRows.value.flatMap(({ id, title, metadata }) =>
    (metadata.intent_rules ?? []).map((rule) => ({ capabilityId: id, capabilityTitle: title, rule })),
  ),
)

const groundingRows = computed(() =>
  capabilityRows.value.flatMap(({ id, title, metadata }) => {
    const meaningRows = Object.entries(metadata.input_meanings ?? {}).map(([inputName, meanings]) => ({
      capabilityId: id,
      capabilityTitle: title,
      label: developerLabel(inputName),
      type: 'Value meanings',
      detail: Object.entries(meanings).map(([value, meaning]) => `${developerLabel(value)} means ${meaning}`).join('; '),
    }))
    const catalogRows = Object.entries(metadata.reference_catalogs ?? {}).map(([inputName, values]) => ({
      capabilityId: id,
      capabilityTitle: title,
      label: developerLabel(inputName),
      type: 'Reference catalog',
      detail: values.map((value) => developerLabel(value)).join(', '),
    }))
    return [...meaningRows, ...catalogRows]
  }),
)

const boundaryRows = computed(() =>
  capabilityRows.value.flatMap(({ id, title, metadata }) => {
    const boundaries = metadata.app_boundaries
    if (!boundaries) return []
    const rows: Array<{ capabilityId: string; capabilityTitle: string; title: string; detail: string }> = []
    if (boundaries.unsupported_effects?.length) {
      rows.push({
        capabilityId: id,
        capabilityTitle: title,
        title: 'Unsupported outcomes',
        detail: `The app should refuse or explain requests for ${formatEffectList(boundaries.unsupported_effects)}.`,
      })
    }
    if (boundaries.conditional_approval_boundary?.when_missing?.length) {
      rows.push({
        capabilityId: id,
        capabilityTitle: title,
        title: 'Conditional approval boundary',
        detail: `If ${boundaries.conditional_approval_boundary.when_missing.map((value) => developerLabel(value)).join(', ')} is missing, the app should treat the request as ${formatEffectList(boundaries.conditional_approval_boundary.produces)}.`,
      })
    }
    if (boundaries.guidance) {
      rows.push({
        capabilityId: id,
        capabilityTitle: title,
        title: 'Boundary guidance',
        detail: boundaries.guidance,
      })
    }
    return rows
  }),
)

const selectionHints = computed(() => agentConsumabilityMetadata.value.selection_hints ?? [])

const knownEffectOptions = [
  'content.draft',
  'content.summary',
  'content.recommendation',
  'data.read',
  'data.aggregate',
  'data.export',
  'raw_data_export',
  'system.preview_mutation',
  'system.mutation',
  'external_dispatch',
  'approval.request',
  'approval.execute',
]

const customizationStats = computed(() => [
  {
    label: 'Capabilities in app profile',
    value: capabilityRows.value.length,
    detail: 'Generated from the reviewed Developer Definition.',
  },
  {
    label: 'App-owned capabilities',
    value: appOwnedCapabilities.value.length,
    detail: 'Package-specific choices the consuming app must own.',
  },
  {
    label: 'Business-language rules',
    value: businessLanguageRules.value.length,
    detail: 'Reviewed interpretations for ambiguous phrases.',
  },
  {
    label: 'Selection hints',
    value: selectionHints.value.length,
    detail: 'Compact routing hints for the generated app profile.',
  },
])

function ownerLabel(owner: AgentConsumabilityIntentRule['owner'] | AgentConsumabilityBusinessLanguageRule['owner']): string {
  if (owner === 'agent_app_glue') return 'Agent app'
  if (owner === 'developer_contract') return 'Developer contract'
  if (owner === 'product_contract') return 'Product design'
  return 'Service'
}

function actionLabel(action?: AgentConsumabilityBusinessLanguageRule['agent_action']): string {
  if (action === 'treat_as_purpose') return 'Treat as purpose or framing'
  if (action === 'prefer_capability') return 'Prefer this capability'
  if (action === 'clarify') return 'Ask for clarification'
  return 'Treat as supported wording'
}

function cloneReviews(value: unknown): Record<string, AgentConsumabilityCapabilityReview> {
  return JSON.parse(JSON.stringify(normalizeAgentConsumabilityReviews(value)))
}

watch(
  () => traceabilityRecord.value?.agent_consumability_reviews,
  (value) => {
    reviewDrafts.value = cloneReviews(value)
  },
  { immediate: true },
)

function reviewForCapability(
  capabilityId: string,
  metadata: AgentConsumabilityMetadataCapability,
): AgentConsumabilityCapabilityReview {
  return reviewDrafts.value[capabilityId] ?? defaultReviewForCapability(capabilityId, metadata)
}

type AgentConsumabilityMetadataCapability = ReturnType<typeof buildAgentConsumabilityMetadata>['capabilities'][string]

function defaultReviewForCapability(
  capabilityId: string,
  metadata: AgentConsumabilityMetadataCapability,
): AgentConsumabilityCapabilityReview {
  return {
    capability_id: capabilityId,
    reviewed_at: new Date().toISOString(),
    intent_category: metadata.intent.category,
    intent_summary: metadata.intent.summary,
    app_glue_required: Boolean(metadata.app_glue?.required),
    app_glue_reason: metadata.app_glue?.reason,
    intent_rules: metadata.intent_rules,
    business_language_rules: metadata.business_language_rules,
    input_meanings: metadata.input_meanings,
    reference_catalogs: metadata.reference_catalogs,
    app_boundaries: metadata.app_boundaries,
    selection_hints: selectionHints.value.filter((hint) => hint.capability === capabilityId),
  }
}

function updateReview(
  capabilityId: string,
  metadata: AgentConsumabilityMetadataCapability,
  patch: Partial<AgentConsumabilityCapabilityReview>,
) {
  const current = reviewForCapability(capabilityId, metadata)
  reviewDrafts.value = {
    ...reviewDrafts.value,
    [capabilityId]: {
      ...current,
      ...patch,
      capability_id: capabilityId,
      reviewed_at: new Date().toISOString(),
    },
  }
  savedMessage.value = null
  saveError.value = null
}

function textList(value: string): string[] | undefined {
  const values = value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
  return values.length ? values : undefined
}

function businessRuleDraft(capabilityId: string) {
  return businessRuleDrafts.value[capabilityId] ?? {
    meaning: '',
    anyTerms: '',
    allTerms: '',
    excludeTerms: '',
    interpretation: '',
    action: 'treat_as_supported' as const,
  }
}

function updateBusinessRuleDraft(
  capabilityId: string,
  field: keyof ReturnType<typeof businessRuleDraft>,
  value: string,
) {
  businessRuleDrafts.value = {
    ...businessRuleDrafts.value,
    [capabilityId]: {
      ...businessRuleDraft(capabilityId),
      [field]: value,
    },
  }
}

function addBusinessRule(capabilityId: string, metadata: AgentConsumabilityMetadataCapability) {
  const draft = businessRuleDraft(capabilityId)
  const appliesWhen = {
    all_terms: textList(draft.allTerms),
    any_terms: textList(draft.anyTerms),
    exclude_terms: textList(draft.excludeTerms),
  }
  if (!draft.meaning.trim() || !draft.interpretation.trim() || (!appliesWhen.all_terms?.length && !appliesWhen.any_terms?.length)) {
    saveError.value = 'Add a meaning, interpretation, and at least one trigger term before adding a business-language rule.'
    return
  }
  const current = reviewForCapability(capabilityId, metadata)
  const rules = current.business_language_rules ?? []
  updateReview(capabilityId, metadata, {
    app_glue_required: true,
    app_glue_reason: current.app_glue_reason || 'The consuming app has reviewed package-specific business-language interpretation.',
    business_language_rules: [
      ...rules,
      {
        id: `${capabilityId.replace(/[^a-z0-9]+/gi, '-')}-business-language-${rules.length + 1}`.toLowerCase(),
        meaning: draft.meaning.trim(),
        owner: 'agent_app_glue',
        applies_when: appliesWhen,
        interpretation: draft.interpretation.trim(),
        agent_action: draft.action,
      },
    ],
  })
  businessRuleDrafts.value = {
    ...businessRuleDrafts.value,
    [capabilityId]: businessRuleDraft(''),
  }
}

function removeBusinessRule(
  capabilityId: string,
  metadata: AgentConsumabilityMetadataCapability,
  index: number,
) {
  const current = reviewForCapability(capabilityId, metadata)
  const rules = [...(current.business_language_rules ?? [])]
  rules.splice(index, 1)
  updateReview(capabilityId, metadata, { business_language_rules: rules })
}

function selectionHintDraft(capabilityId: string) {
  return selectionHintDrafts.value[capabilityId] ?? {
    anyTerms: '',
    allTerms: '',
    excludeTerms: '',
  }
}

function updateSelectionHintDraft(
  capabilityId: string,
  field: keyof ReturnType<typeof selectionHintDraft>,
  value: string,
) {
  selectionHintDrafts.value = {
    ...selectionHintDrafts.value,
    [capabilityId]: {
      ...selectionHintDraft(capabilityId),
      [field]: value,
    },
  }
}

function addSelectionHint(capabilityId: string, metadata: AgentConsumabilityMetadataCapability) {
  const draft = selectionHintDraft(capabilityId)
  const hint: AgentConsumabilitySelectionHint = {
    capability: capabilityId,
    all_terms: textList(draft.allTerms),
    any_terms: textList(draft.anyTerms),
    exclude_terms: textList(draft.excludeTerms),
  }
  if (!hint.all_terms?.length && !hint.any_terms?.length) {
    saveError.value = 'Add at least one required or optional term before adding a selection hint.'
    return
  }
  const current = reviewForCapability(capabilityId, metadata)
  updateReview(capabilityId, metadata, {
    app_glue_required: true,
    app_glue_reason: current.app_glue_reason || 'The consuming app has reviewed package-specific routing and selection hints.',
    selection_hints: [...(current.selection_hints ?? []), hint],
  })
  selectionHintDrafts.value = {
    ...selectionHintDrafts.value,
    [capabilityId]: selectionHintDraft(''),
  }
}

function removeSelectionHint(
  capabilityId: string,
  metadata: AgentConsumabilityMetadataCapability,
  index: number,
) {
  const current = reviewForCapability(capabilityId, metadata)
  const hints = [...(current.selection_hints ?? [])]
  hints.splice(index, 1)
  updateReview(capabilityId, metadata, { selection_hints: hints })
}

function toggleUnsupportedEffect(
  capabilityId: string,
  metadata: AgentConsumabilityMetadataCapability,
  effectId: string,
  checked: boolean,
) {
  const current = reviewForCapability(capabilityId, metadata)
  const boundaries = current.app_boundaries ?? metadata.app_boundaries ?? {}
  const unsupported = new Set(boundaries.unsupported_effects ?? [])
  if (checked) unsupported.add(effectId)
  else unsupported.delete(effectId)
  updateReview(capabilityId, metadata, {
    app_boundaries: {
      ...boundaries,
      unsupported_effects: Array.from(unsupported),
    },
  })
}

function updateInputMeaning(
  capabilityId: string,
  metadata: AgentConsumabilityMetadataCapability,
  inputName: string,
  value: string,
  meaning: string,
) {
  const current = reviewForCapability(capabilityId, metadata)
  const inputMeanings = JSON.parse(JSON.stringify(current.input_meanings ?? metadata.input_meanings ?? {})) as Record<string, Record<string, string>>
  inputMeanings[inputName] = {
    ...(inputMeanings[inputName] ?? {}),
    [value]: meaning,
  }
  updateReview(capabilityId, metadata, { input_meanings: inputMeanings })
}

function baseTraceabilityRecord(): TraceabilityRecordData | null {
  if (traceabilityRecord.value) return JSON.parse(JSON.stringify(traceabilityRecord.value))
  if (!baseline.value) return null
  return buildTraceabilityRecord({
    pmArtifacts: projectStore.artifacts.pmArtifacts,
    requirements: lockedRequirements.value,
    scenarios: lockedScenarios.value,
    primaryScenarioId: baseline.value.source_inputs.primary_scenario_id,
    shape: lockedShape.value,
    baselineLockedAt: baseline.value.locked_at,
    existing: null,
    reducedFrontingProductDesign: isGovernedFrontingProject.value,
  })
}

async function saveCustomizationReviews() {
  if (!project.value) return
  const record = baseTraceabilityRecord()
  if (!record) {
    saveError.value = 'Lock the Developer baseline before saving app customization.'
    return
  }
  saving.value = true
  saveError.value = null
  savedMessage.value = null
  try {
    const payload: TraceabilityRecordData = {
      ...record,
      artifact_type: DESIGN_TRACEABILITY_ARTIFACT_TYPE,
      agent_consumability_reviews: JSON.parse(JSON.stringify(reviewDrafts.value)),
      pm_review_status: 'pending',
      pm_review_note: '',
      pm_reviewed_at: null,
    }
    if (traceabilityArtifact.value) {
      await updatePmArtifact(project.value.id, traceabilityArtifact.value.id, {
        title: 'Developer Coverage & PM Review',
        status: 'draft',
        data: payload as unknown as Record<string, any>,
      })
    } else {
      await createPmArtifact(project.value.id, {
        id: traceabilityArtifactId(project.value.id),
        title: 'Developer Coverage & PM Review',
        data: payload as unknown as Record<string, any>,
      })
    }
    await loadProject(project.value.id)
    savedMessage.value = 'App customization reviews saved. Generation will export them into the agent-consumption package files.'
  } catch (err) {
    saveError.value = err instanceof Error ? err.message : String(err)
  } finally {
    saving.value = false
  }
}

function ruleTerms(rule: AgentConsumabilityBusinessLanguageRule): string {
  const parts = [
    rule.applies_when.all_terms?.length ? `must include ${rule.applies_when.all_terms.join(', ')}` : '',
    rule.applies_when.any_terms?.length ? `may include ${rule.applies_when.any_terms.join(', ')}` : '',
    rule.applies_when.exclude_terms?.length ? `exclude ${rule.applies_when.exclude_terms.join(', ')}` : '',
  ].filter(Boolean)
  return parts.join('; ') || 'No terms recorded'
}

function open(path: string) {
  router.push(path)
}

onMounted(ensureLoaded)

watch(projectId, ensureLoaded)
</script>

<template>
  <div class="app-customization-page">
    <template v-if="project">
      <section class="page-header">
        <button class="back-link" type="button" @click="open(`/design/projects/${project.id}/developer`)">
          &larr; Back to Developer Design
        </button>
        <div class="page-kicker">Developer Design</div>
        <h1>Agent App Customization</h1>
        <p>
          This page separates generic ANIP runtime behavior from package-specific app guidance. The generated service contract stays canonical; the generated app profile carries reviewed wording, selection, display, and boundary choices that the consuming app can customize.
        </p>
        <div class="header-actions">
          <button class="btn btn-primary" type="button" :disabled="saving" @click="saveCustomizationReviews">
            {{ saving ? 'Saving...' : 'Save Customization Reviews' }}
          </button>
          <button class="btn btn-primary" type="button" @click="open(`/design/projects/${project.id}/developer/app-glue`)">Review Agent & App Glue</button>
          <button class="btn btn-secondary" type="button" @click="open(`/design/projects/${project.id}/developer/capability-formalization`)">Open Capability Contracts</button>
          <button class="btn btn-secondary" type="button" @click="open(`/design/projects/${project.id}/developer/diagrams?diagram=app-glue`)">Open Glue Diagram</button>
        </div>
        <p v-if="savedMessage" class="success-copy">{{ savedMessage }}</p>
        <p v-if="saveError" class="error-copy">{{ saveError }}</p>
      </section>

      <section v-if="!developerDefinition" class="panel empty-panel">
        <h2>No Developer Definition yet</h2>
        <p>Create or save the Developer Definition before reviewing generated app customization.</p>
      </section>

      <template v-else>
        <section class="stat-grid">
          <article v-for="stat in customizationStats" :key="stat.label" class="stat-card">
            <span>{{ stat.label }}</span>
            <strong>{{ stat.value }}</strong>
            <small>{{ stat.detail }}</small>
          </article>
        </section>

        <section class="panel panel-full">
          <div class="panel-header">
            <div>
              <h2>What Gets Generated</h2>
              <p>The shared runtime should stay boring and generic. Package-specific behavior is generated as reviewable app-profile files, then customized in the app layer when needed.</p>
            </div>
          </div>
          <div class="generation-grid">
            <article class="generation-card">
              <span class="generation-kicker">Shared runtime</span>
              <h3>Generic ANIP mechanics</h3>
              <p>Service discovery, schema validation, approval continuation, and safe invocation should not contain GTM-style wording or package-specific routing.</p>
            </article>
            <article class="generation-card">
              <span class="generation-kicker">Generated profile</span>
              <h3>Package app guidance</h3>
              <p>Studio exports capability summaries, unsupported outcomes, required context, display guidance, input meanings, and selection hints.</p>
            </article>
            <article class="generation-card">
              <span class="generation-kicker">Editable extension</span>
              <h3>Runtime overrides</h3>
              <p>The generated app includes customization files for business-language interpretation that should evolve outside the shared runtime library.</p>
            </article>
          </div>
        </section>

        <section class="panel panel-full">
          <div class="panel-header">
            <div>
              <h2>App-Owned Decisions</h2>
              <p>These are not generic ANIP rules. They are package or consuming-app responsibilities such as target selection, business phrasing, display posture, or refusing unsupported outcomes.</p>
            </div>
            <button class="btn btn-secondary" type="button" @click="open(`/design/projects/${project.id}/developer/app-glue`)">
              Edit Reviews
            </button>
          </div>
          <div v-if="appOwnedCapabilities.length" class="capability-stack">
            <details v-for="item in appOwnedCapabilities" :key="item.id" class="capability-card" open>
              <summary>
                <span>
                  <strong>{{ item.title }}</strong>
                  <small>{{ item.metadata.intent.summary }}</small>
                </span>
                <em>{{ item.metadata.app_glue?.required ? 'App glue required' : ownerLabel(item.metadata.derived_target_owner?.owner === 'app' ? 'agent_app_glue' : 'service') }}</em>
              </summary>
              <div class="detail-grid">
                <div v-if="item.metadata.app_glue?.reason" class="detail-box">
                  <span>App-owned behavior</span>
                  <p>{{ item.metadata.app_glue.reason }}</p>
                </div>
                <div v-if="item.metadata.derived_target_owner?.reason" class="detail-box">
                  <span>Target selection</span>
                  <p>{{ item.metadata.derived_target_owner.reason }}</p>
                </div>
                <div v-if="item.metadata.required_context?.length" class="detail-box">
                  <span>Required context</span>
                  <p>{{ item.metadata.required_context.map((context) => developerLabel(context.input)).join(', ') }}</p>
                </div>
                <div v-if="item.metadata.result_display?.primary_fields?.length" class="detail-box">
                  <span>Result display</span>
                  <p>Show {{ item.metadata.result_display.primary_fields.map((field) => developerLabel(field).toLowerCase()).join(', ') }} as the primary result.</p>
                </div>
              </div>
              <section class="customization-editor">
                <div class="editor-header">
                  <div>
                    <h3>Reviewed Customization</h3>
                    <p>Save app-owned behavior here. Generation exports it as package app-profile and override guidance, not as hidden generic runtime logic.</p>
                  </div>
                  <button
                    class="btn btn-secondary"
                    type="button"
                    @click="expandedEditorId = expandedEditorId === item.id ? null : item.id"
                  >
                    {{ expandedEditorId === item.id ? 'Hide Editor' : 'Edit Customization' }}
                  </button>
                </div>
                <div v-if="expandedEditorId === item.id" class="editor-body">
                  <label class="toggle-row">
                    <input
                      type="checkbox"
                      :checked="reviewForCapability(item.id, item.metadata).app_glue_required === true"
                      @change="updateReview(item.id, item.metadata, { app_glue_required: ($event.target as HTMLInputElement).checked })"
                    />
                    <span>This capability needs app-owned guidance</span>
                  </label>

                  <label class="field-block">
                    <span>App-owned behavior note</span>
                    <textarea
                      :value="reviewForCapability(item.id, item.metadata).app_glue_reason ?? ''"
                      placeholder="Explain what the consuming app must decide, display, select, or refuse."
                      @input="updateReview(item.id, item.metadata, { app_glue_reason: ($event.target as HTMLTextAreaElement).value, app_glue_required: true })"
                    />
                  </label>

                  <div class="editor-subsection">
                    <h4>Unsupported Outcomes</h4>
                    <p>Select outcomes the app should refuse or explain before invoking this capability.</p>
                    <div class="chip-grid">
                      <label v-for="effect in knownEffectOptions" :key="`${item.id}:${effect}`" class="checkbox-chip">
                        <input
                          type="checkbox"
                          :checked="(reviewForCapability(item.id, item.metadata).app_boundaries?.unsupported_effects ?? []).includes(effect)"
                          @change="toggleUnsupportedEffect(item.id, item.metadata, effect, ($event.target as HTMLInputElement).checked)"
                        />
                        <span>{{ developerLabel(effect) }}</span>
                      </label>
                    </div>
                  </div>

                  <div v-if="Object.keys(reviewForCapability(item.id, item.metadata).input_meanings ?? item.metadata.input_meanings ?? {}).length" class="editor-subsection">
                    <h4>Input Meanings</h4>
                    <p>Use this when compact values need business meaning before app invocation.</p>
                    <div
                      v-for="[inputName, meanings] in Object.entries(reviewForCapability(item.id, item.metadata).input_meanings ?? item.metadata.input_meanings ?? {})"
                      :key="`${item.id}:${inputName}`"
                      class="meaning-group"
                    >
                      <strong>{{ developerLabel(inputName) }}</strong>
                      <label v-for="[value, meaning] in Object.entries(meanings)" :key="`${item.id}:${inputName}:${value}`" class="field-block inline-field">
                        <span>{{ developerLabel(value) }}</span>
                        <input
                          :value="meaning"
                          @input="updateInputMeaning(item.id, item.metadata, inputName, value, ($event.target as HTMLInputElement).value)"
                        />
                      </label>
                    </div>
                  </div>

                  <div class="editor-subsection">
                    <h4>Business-Language Rules</h4>
                    <div v-if="(reviewForCapability(item.id, item.metadata).business_language_rules ?? []).length" class="mini-list">
                      <div
                        v-for="(rule, ruleIndex) in reviewForCapability(item.id, item.metadata).business_language_rules"
                        :key="`${item.id}:rule:${rule.id}`"
                        class="mini-row"
                      >
                        <span>{{ rule.meaning }}</span>
                        <small>{{ actionLabel(rule.agent_action) }} · {{ ruleTerms(rule) }}</small>
                        <button class="link-button" type="button" @click="removeBusinessRule(item.id, item.metadata, ruleIndex)">Remove</button>
                      </div>
                    </div>
                    <div class="rule-form">
                      <label class="field-block">
                        <span>Meaning</span>
                        <input
                          :value="businessRuleDraft(item.id).meaning"
                          placeholder="e.g. User asks for concentration risk"
                          @input="updateBusinessRuleDraft(item.id, 'meaning', ($event.target as HTMLInputElement).value)"
                        />
                      </label>
                      <label class="field-block">
                        <span>Optional terms</span>
                        <input
                          :value="businessRuleDraft(item.id).anyTerms"
                          placeholder="comma-separated terms"
                          @input="updateBusinessRuleDraft(item.id, 'anyTerms', ($event.target as HTMLInputElement).value)"
                        />
                      </label>
                      <label class="field-block">
                        <span>Required terms</span>
                        <input
                          :value="businessRuleDraft(item.id).allTerms"
                          placeholder="comma-separated terms"
                          @input="updateBusinessRuleDraft(item.id, 'allTerms', ($event.target as HTMLInputElement).value)"
                        />
                      </label>
                      <label class="field-block">
                        <span>Exclude terms</span>
                        <input
                          :value="businessRuleDraft(item.id).excludeTerms"
                          placeholder="comma-separated terms"
                          @input="updateBusinessRuleDraft(item.id, 'excludeTerms', ($event.target as HTMLInputElement).value)"
                        />
                      </label>
                      <label class="field-block wide">
                        <span>Interpretation</span>
                        <textarea
                          :value="businessRuleDraft(item.id).interpretation"
                          placeholder="What the app should infer from this business wording."
                          @input="updateBusinessRuleDraft(item.id, 'interpretation', ($event.target as HTMLTextAreaElement).value)"
                        />
                      </label>
                      <label class="field-block">
                        <span>App action</span>
                        <select
                          :value="businessRuleDraft(item.id).action"
                          @change="updateBusinessRuleDraft(item.id, 'action', ($event.target as HTMLSelectElement).value)"
                        >
                          <option value="treat_as_supported">Treat as supported wording</option>
                          <option value="treat_as_purpose">Treat as purpose/framing</option>
                          <option value="prefer_capability">Prefer this capability</option>
                          <option value="clarify">Ask for clarification</option>
                        </select>
                      </label>
                      <button class="btn btn-secondary" type="button" @click="addBusinessRule(item.id, item.metadata)">Add Rule</button>
                    </div>
                  </div>

                  <div class="editor-subsection">
                    <h4>Selection Hints</h4>
                    <div v-if="(reviewForCapability(item.id, item.metadata).selection_hints ?? []).length" class="mini-list">
                      <div
                        v-for="(hint, hintIndex) in reviewForCapability(item.id, item.metadata).selection_hints"
                        :key="`${item.id}:hint:${hintIndex}`"
                        class="mini-row"
                      >
                        <span>{{ [
                          hint.all_terms?.length ? `must include ${hint.all_terms.join(', ')}` : '',
                          hint.any_terms?.length ? `may include ${hint.any_terms.join(', ')}` : '',
                          hint.exclude_terms?.length ? `exclude ${hint.exclude_terms.join(', ')}` : '',
                        ].filter(Boolean).join('; ') }}</span>
                        <button class="link-button" type="button" @click="removeSelectionHint(item.id, item.metadata, hintIndex)">Remove</button>
                      </div>
                    </div>
                    <div class="rule-form">
                      <label class="field-block">
                        <span>Optional terms</span>
                        <input
                          :value="selectionHintDraft(item.id).anyTerms"
                          placeholder="comma-separated terms"
                          @input="updateSelectionHintDraft(item.id, 'anyTerms', ($event.target as HTMLInputElement).value)"
                        />
                      </label>
                      <label class="field-block">
                        <span>Required terms</span>
                        <input
                          :value="selectionHintDraft(item.id).allTerms"
                          placeholder="comma-separated terms"
                          @input="updateSelectionHintDraft(item.id, 'allTerms', ($event.target as HTMLInputElement).value)"
                        />
                      </label>
                      <label class="field-block">
                        <span>Exclude terms</span>
                        <input
                          :value="selectionHintDraft(item.id).excludeTerms"
                          placeholder="comma-separated terms"
                          @input="updateSelectionHintDraft(item.id, 'excludeTerms', ($event.target as HTMLInputElement).value)"
                        />
                      </label>
                      <button class="btn btn-secondary" type="button" @click="addSelectionHint(item.id, item.metadata)">Add Hint</button>
                    </div>
                  </div>
                </div>
              </section>
            </details>
          </div>
          <p v-else class="empty-copy">No explicit app-owned decisions are recorded yet.</p>
        </section>

        <section class="two-column">
          <article class="panel">
            <div class="panel-header">
              <div>
                <h2>Business-Language Rules</h2>
                <p>Reviewed wording rules tell the app how to interpret ambiguous user phrasing without adding brittle rules to the generic runtime package.</p>
              </div>
            </div>
            <div v-if="businessLanguageRules.length" class="rule-stack">
              <div v-for="item in businessLanguageRules" :key="`${item.capabilityId}:${item.rule.id}`" class="rule-card">
                <span>{{ item.capabilityTitle }}</span>
                <strong>{{ item.rule.meaning }}</strong>
                <p>{{ item.rule.interpretation }}</p>
                <small>{{ actionLabel(item.rule.agent_action) }} · {{ ownerLabel(item.rule.owner) }} · {{ ruleTerms(item.rule) }}</small>
              </div>
            </div>
            <p v-else class="empty-copy">No reviewed business-language rules are recorded yet.</p>
          </article>

          <article class="panel">
            <div class="panel-header">
              <div>
                <h2>Intent Rules</h2>
                <p>Intent rules explain package-specific behavior that the app may need to select, clarify, or pass to a service.</p>
              </div>
            </div>
            <div v-if="intentRules.length" class="rule-stack">
              <div v-for="item in intentRules" :key="`${item.capabilityId}:${item.rule.id}`" class="rule-card">
                <span>{{ item.capabilityTitle }}</span>
                <strong>{{ item.rule.meaning }}</strong>
                <p>{{ item.rule.agent_action || item.rule.service_behavior || item.rule.applies_when || 'No runtime action recorded.' }}</p>
                <small>{{ ownerLabel(item.rule.owner) }}</small>
              </div>
            </div>
            <p v-else class="empty-copy">No explicit intent rules are recorded yet.</p>
          </article>
        </section>

        <section class="two-column">
          <article class="panel">
            <div class="panel-header">
              <div>
                <h2>Value and Target Grounding</h2>
                <p>These hints help a consuming app normalize compact business values or references before invocation.</p>
              </div>
            </div>
            <div v-if="groundingRows.length" class="rule-stack">
              <div v-for="item in groundingRows" :key="`${item.capabilityId}:${item.type}:${item.label}`" class="rule-card">
                <span>{{ item.capabilityTitle }} · {{ item.type }}</span>
                <strong>{{ item.label }}</strong>
                <p>{{ item.detail }}</p>
              </div>
            </div>
            <p v-else class="empty-copy">No input meanings or reference catalogs are recorded yet.</p>
          </article>

          <article class="panel">
            <div class="panel-header">
              <div>
                <h2>Boundaries and Selection</h2>
                <p>Boundaries describe what the app should refuse, explain, or route carefully. Selection hints should stay compact and reviewable.</p>
              </div>
            </div>
            <div v-if="boundaryRows.length || selectionHints.length" class="rule-stack">
              <div v-for="item in boundaryRows" :key="`${item.capabilityId}:${item.title}`" class="rule-card boundary">
                <span>{{ item.capabilityTitle }}</span>
                <strong>{{ item.title }}</strong>
                <p>{{ item.detail }}</p>
              </div>
              <div v-for="hint in selectionHints" :key="`${hint.capability}:${hint.all_terms?.join('-')}:${hint.any_terms?.join('-')}`" class="rule-card selection">
                <span>{{ capabilityTitleById.get(hint.capability) ?? developerLabel(hint.capability) }}</span>
                <strong>Selection hint</strong>
                <p>
                  {{ [
                    hint.all_terms?.length ? `must include ${hint.all_terms.join(', ')}` : '',
                    hint.any_terms?.length ? `may include ${hint.any_terms.join(', ')}` : '',
                    hint.exclude_terms?.length ? `exclude ${hint.exclude_terms.join(', ')}` : '',
                  ].filter(Boolean).join('; ') || 'No terms recorded' }}
                </p>
              </div>
            </div>
            <p v-else class="empty-copy">No app boundaries or selection hints are recorded yet.</p>
          </article>
        </section>

        <section class="panel panel-full export-panel">
          <div class="panel-header">
            <div>
              <h2>Generated Artifacts</h2>
              <p>Generation should include these files so app teams know where to customize semantics without changing the shared ANIP runtime.</p>
            </div>
            <button class="btn btn-secondary" type="button" @click="open(`/design/projects/${project.id}/developer/definition#generation-launch`)">
              Open Generation
            </button>
          </div>
          <div class="artifact-list">
            <code>agent-consumption/agent-consumability.json</code>
            <span>Reviewed app-consumption metadata exported from Studio.</span>
            <code>agent-consumption/runtime-customization.json</code>
            <span>Generated package defaults for runtime interpretation.</span>
            <code>agent-consumption/custom/runtime-overrides.json</code>
            <span>Editable app-owned override file for package semantics.</span>
            <code>agent-consumption/custom/README.md</code>
            <span>Human guide explaining what can be customized safely.</span>
          </div>
        </section>
      </template>
    </template>
  </div>
</template>

<style scoped>
.app-customization-page {
  width: 100%;
  padding: 32px;
  color: #172033;
}

.page-header,
.panel,
.stat-card {
  border: 1px solid rgba(28, 45, 75, 0.1);
  border-radius: 24px;
  background: #fffdf8;
  box-shadow: 0 18px 40px rgba(37, 47, 74, 0.08);
}

.page-header {
  margin-bottom: 24px;
  padding: 28px;
}

.page-header h1,
.panel h2 {
  margin: 0;
}

.page-header p,
.panel p,
.rule-card p,
.detail-box p {
  color: #5c6578;
  line-height: 1.55;
}

.page-kicker,
.generation-kicker,
.summary-label,
.rule-card span,
.detail-box span,
.stat-card span {
  color: #7c5c26;
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.back-link {
  margin-bottom: 16px;
  border: 0;
  background: transparent;
  color: #596274;
  cursor: pointer;
  font-weight: 700;
}

.header-actions,
.panel-header {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  justify-content: space-between;
}

.header-actions {
  flex-wrap: wrap;
  margin-top: 20px;
}

.btn {
  border: 0;
  border-radius: 999px;
  cursor: pointer;
  font-weight: 800;
  padding: 10px 16px;
}

.btn-primary {
  background: #183a37;
  color: #fffdf8;
}

.btn-secondary {
  background: #efe7d8;
  color: #283244;
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 20px;
}

.stat-card {
  display: grid;
  gap: 8px;
  padding: 20px;
}

.stat-card strong {
  color: #172033;
  font-size: 2rem;
}

.stat-card small,
.rule-card small,
.capability-card small {
  color: #6b7280;
  line-height: 1.45;
}

.panel {
  margin-bottom: 20px;
  padding: 24px;
}

.panel-full {
  width: 100%;
}

.generation-grid,
.detail-grid,
.two-column {
  display: grid;
  gap: 16px;
}

.generation-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.generation-card,
.detail-box,
.rule-card {
  border: 1px solid rgba(31, 55, 82, 0.1);
  border-radius: 18px;
  background: #f8f3e9;
  padding: 18px;
}

.generation-card h3,
.rule-card strong {
  display: block;
  margin: 6px 0;
}

.capability-stack,
.rule-stack {
  display: grid;
  gap: 12px;
  margin-top: 18px;
}

.capability-card {
  border: 1px solid rgba(31, 55, 82, 0.12);
  border-radius: 18px;
  background: #fbf7ef;
  padding: 16px;
}

.capability-card summary {
  align-items: center;
  cursor: pointer;
  display: flex;
  gap: 16px;
  justify-content: space-between;
}

.capability-card summary span {
  display: grid;
  gap: 4px;
}

.capability-card em {
  border-radius: 999px;
  background: #e2f2e8;
  color: #1f5f3c;
  font-size: 0.75rem;
  font-style: normal;
  font-weight: 800;
  padding: 6px 10px;
  white-space: nowrap;
}

.detail-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin-top: 16px;
}

.customization-editor {
  border-top: 1px solid rgba(31, 55, 82, 0.12);
  display: grid;
  gap: 16px;
  margin-top: 18px;
  padding-top: 18px;
}

.editor-header {
  align-items: flex-start;
  display: flex;
  gap: 16px;
  justify-content: space-between;
}

.editor-header h3,
.editor-subsection h4 {
  margin: 0;
}

.editor-header p,
.editor-subsection p {
  margin: 6px 0 0;
}

.editor-body,
.editor-subsection,
.meaning-group,
.mini-list {
  display: grid;
  gap: 12px;
}

.editor-body {
  border: 1px solid rgba(31, 55, 82, 0.12);
  border-radius: 18px;
  background: #fffaf1;
  padding: 18px;
}

.editor-subsection {
  border-top: 1px solid rgba(31, 55, 82, 0.1);
  padding-top: 16px;
}

.toggle-row {
  align-items: center;
  display: flex;
  gap: 10px;
  color: #293244;
  font-weight: 800;
}

.field-block {
  display: grid;
  gap: 6px;
}

.field-block span {
  color: #7c5c26;
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.field-block input,
.field-block select,
.field-block textarea {
  border: 1px solid rgba(31, 55, 82, 0.16);
  border-radius: 14px;
  background: #fffdf8;
  color: #172033;
  font: inherit;
  padding: 10px 12px;
}

.field-block textarea {
  min-height: 84px;
  resize: vertical;
}

.inline-field {
  grid-template-columns: 190px minmax(0, 1fr);
  align-items: center;
}

.rule-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.rule-form .wide {
  grid-column: 1 / -1;
}

.rule-form .btn {
  align-self: end;
  justify-self: start;
}

.chip-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.checkbox-chip {
  align-items: center;
  border: 1px solid rgba(31, 55, 82, 0.13);
  border-radius: 999px;
  background: #f8f3e9;
  display: inline-flex;
  gap: 7px;
  padding: 8px 10px;
  color: #293244;
  font-size: 0.86rem;
  font-weight: 800;
}

.mini-row {
  align-items: center;
  border: 1px solid rgba(31, 55, 82, 0.1);
  border-radius: 14px;
  background: #f8f3e9;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(160px, 0.9fr) auto;
  gap: 10px;
  padding: 10px 12px;
}

.mini-row span {
  color: #293244;
  font-weight: 800;
}

.link-button {
  border: 0;
  background: transparent;
  color: #8f3f24;
  cursor: pointer;
  font-weight: 900;
}

.two-column {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.rule-card.boundary {
  background: #fff1e6;
}

.rule-card.selection {
  background: #eef6ee;
}

.empty-copy {
  border: 1px dashed rgba(31, 55, 82, 0.16);
  border-radius: 16px;
  padding: 18px;
}

.artifact-list {
  display: grid;
  grid-template-columns: minmax(260px, 0.8fr) 1fr;
  gap: 10px 16px;
  margin-top: 18px;
}

.artifact-list code {
  border-radius: 12px;
  background: #172033;
  color: #fffdf8;
  padding: 10px 12px;
}

.artifact-list span {
  align-self: center;
  color: #5c6578;
}

@media (max-width: 980px) {
  .app-customization-page {
    padding: 18px;
  }

  .stat-grid,
  .generation-grid,
  .detail-grid,
  .two-column,
  .artifact-list,
  .rule-form,
  .inline-field,
  .mini-row {
    grid-template-columns: 1fr;
  }

  .header-actions,
  .panel-header,
  .capability-card summary,
  .editor-header {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
