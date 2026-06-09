<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { DATA_ACCESS_BACKEND_OPTIONS, createDraftDataAccessProjectState } from '../data-access/defaults'
import type {
  DataAccessBackendType,
  DataAccessClarificationRuleKey,
  DataAccessGeneratedBundle,
  DataAccessImplementationLanguage,
  DataAccessGeneratedOutput,
  DataAccessProjectState,
} from '../data-access/types'
import type { DerivationReport, DeveloperBaselineData, DeveloperDefinitionData, TraceabilityCoverageItem, TraceabilityRecordData } from '../design/project-types'
import { DATA_ACCESS_DEFINITION_SECTIONS, developerDefinitionMatchesCurrentContext, findDeveloperDefinitionArtifact, implementationLanguageForAdapter, resolveDeveloperDefinitionLinks } from '../design/developer-definition'
import {
  createSavedDataAccessProject,
  getSavedDataAccessProject,
  updateSavedDataAccessProject,
} from '../design/project-api'
import { loadProject, projectStore } from '../design/project-store'
import { developerBaselineMatchesCurrentContext, findDeveloperBaselineArtifact, findTraceabilityArtifact, pmReviewStatusLabel, summarizeCoverage } from '../design/traceability'
import { developerLabel } from '../design/developer-vocabulary'

const route = useRoute()
const router = useRouter()
const studioProjectId = computed(() => route.params.projectId as string | undefined)
const studioProject = computed(() => projectStore.activeProject)
const name = ref('Sales Analytics Access')
const description = ref('Governed ANIP surface for bounded analytics access.')
const backendType = ref<typeof DATA_ACCESS_BACKEND_OPTIONS[number]['value']>('internal_metrics_api')
const loading = ref(false)
const error = ref<string | null>(null)
const project = ref<DataAccessProjectState | null>(
  createDraftDataAccessProjectState(name.value, description.value, backendType.value),
)
const generatedBundle = ref<DataAccessGeneratedBundle | null>(null)
const designPacket = ref<DataAccessGeneratedOutput | null>(null)
const capabilityScaffold = ref<DataAccessGeneratedOutput | null>(null)
const backendScaffold = ref<DataAccessGeneratedOutput | null>(null)
const scenarioPack = ref<DataAccessGeneratedOutput | null>(null)
const scenarioManifest = ref<DataAccessGeneratedOutput | null>(null)
const currentSavedId = ref<string | null>(null)
const derivationReport = ref<DerivationReport | null>(null)
const autoSeeded = ref(false)
const CLARIFICATION_RULE_OPTIONS: Array<{ key: DataAccessClarificationRuleKey; label: string; description: string }> = [
  {
    key: 'ambiguous_ranking_metric',
    label: 'Ranking Metric',
    description: 'Ask before assuming what “top” or “best” means.',
  },
  {
    key: 'ambiguous_time_semantics',
    label: 'Time Semantics',
    description: 'Ask before assuming fiscal vs calendar or similar time boundaries.',
  },
  {
    key: 'ambiguous_entity_grain',
    label: 'Entity Grain',
    description: 'Ask before assuming aggregate vs entity-detail answers.',
  },
  {
    key: 'ambiguous_account_hierarchy',
    label: 'Account Hierarchy',
    description: 'Ask before assuming customer vs parent-account grouping.',
  },
]

const hasOutputs = computed(() =>
  Boolean(designPacket.value || capabilityScaffold.value || backendScaffold.value || scenarioPack.value || scenarioManifest.value),
)

function slugify(value: string): string {
  return value.toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')
}

async function ensureStudioProjectLoaded() {
  if (!studioProjectId.value) return
  if (projectStore.activeProject?.id === studioProjectId.value) return
  await loadProject(studioProjectId.value)
}

const currentRequirements = computed(() =>
  projectStore.artifacts.requirements.find((item) => item.role === 'primary')
  ?? projectStore.artifacts.requirements[0]
  ?? null,
)

const currentScenarios = computed(() => projectStore.artifacts.scenarios)

const currentShape = computed(() =>
  projectStore.artifacts.shapes.find((item) => item.id === projectStore.activeShapeId)
  ?? projectStore.artifacts.shapes[0]
  ?? null,
)

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
  projectStore.artifacts.requirements.find((item) => item.id === baseline.value?.source_inputs.requirements_id)
  ?? null,
)
const lockedScenarioPack = computed(() =>
  (baseline.value?.source_inputs.scenario_ids ?? [])
    .map((id) => projectStore.artifacts.scenarios.find((item) => item.id === id) ?? null)
    .filter((item): item is NonNullable<typeof item> => item != null),
)
const lockedPrimaryScenario = computed(() =>
  projectStore.artifacts.scenarios.find((item) => item.id === baseline.value?.source_inputs.primary_scenario_id)
  ?? lockedScenarioPack.value[0]
  ?? null,
)
const lockedShape = computed(() =>
  projectStore.artifacts.shapes.find((item) => item.id === baseline.value?.source_inputs.shape_id)
  ?? null,
)

const developerReady = computed(() =>
  !!baseline.value && baselineAligned.value && !!lockedRequirements.value && !!lockedPrimaryScenario.value && !!lockedShape.value,
)

const traceabilityArtifact = computed(() => findTraceabilityArtifact(projectStore.artifacts.pmArtifacts))
const traceabilityRecord = computed(() =>
  (traceabilityArtifact.value?.data as TraceabilityRecordData | undefined) ?? null,
)
const definitionArtifact = computed(() => findDeveloperDefinitionArtifact(projectStore.artifacts.pmArtifacts))
const developerDefinition = computed(() =>
  (definitionArtifact.value?.data as DeveloperDefinitionData | undefined) ?? null,
)
const developerDefinitionAligned = computed(() =>
  developerDefinitionMatchesCurrentContext({
    definition: developerDefinition.value,
    baseline: baseline.value,
    requirements: lockedRequirements.value,
    scenarios: lockedScenarioPack.value,
    shape: lockedShape.value,
  }),
)
const coverageMatchesCurrentHandoff = computed(() => {
  if (!traceabilityRecord.value || !baseline.value) return false
  return (
    traceabilityRecord.value.source_inputs.requirements_id === baseline.value.source_inputs.requirements_id
    && traceabilityRecord.value.source_inputs.scenario_id === baseline.value.source_inputs.primary_scenario_id
    && traceabilityRecord.value.source_inputs.shape_id === baseline.value.source_inputs.shape_id
    && traceabilityRecord.value.source_inputs.baseline_locked_at === baseline.value.locked_at
  )
})
const surfaceCoverage = computed<TraceabilityCoverageItem[]>(() =>
  (traceabilityRecord.value?.coverage ?? []).filter((item) =>
    resolveDeveloperDefinitionLinks(item.linked_surfaces).some((surface) => DATA_ACCESS_DEFINITION_SECTIONS.includes(surface as any)),
  ),
)
const surfaceCoverageSummary = computed(() => summarizeCoverage(surfaceCoverage.value))
const surfaceOpenItems = computed(() =>
  surfaceCoverage.value.filter((item) => item.status === 'not_addressed' || item.status === 'partially_addressed'),
)
const patternContractInputs = computed(() => {
  if (!developerDefinition.value) return []
  const serviceIds = new Set(developerDefinition.value.generation.selected_service_ids)
  const selectedServices = (((lockedShape.value?.data?.shape ?? lockedShape.value?.data) as Record<string, any> | undefined)?.services ?? [])
    .filter((service: Record<string, any>) => serviceIds.has(String(service.id ?? '')))
    .map((service: Record<string, any>) => String(service.name ?? service.id ?? 'Service'))
  return [
    {
      label: 'Selected Service Boundaries',
      value: selectedServices.length ? selectedServices.join(', ') : 'None selected yet',
    },
    {
      label: 'Protocols',
      value: developerDefinition.value.generation.protocols.join(', ') || 'None selected yet',
    },
    {
      label: 'Codegen Adapter',
      value: developerDefinition.value.generation.codegen_adapter || 'Not specified',
    },
    {
      label: 'Scalability Profile',
      value: developerDefinition.value.generation.scalability_profile || 'Not specified',
    },
    {
      label: 'Data Access Backend Type',
      value: developerDefinition.value.backend_bindings.data_access_backend_type || 'Not specified',
    },
    {
      label: 'Data Access Target Label',
      value: developerDefinition.value.backend_bindings.data_access_target_label || 'Not specified',
    },
    {
      label: 'Implementation Language',
      value: implementationLanguageForAdapter(developerDefinition.value.generation.codegen_adapter),
    },
  ]
})
const patternRoleBullets = [
  'This page is still a generator-specific pattern surface, not the canonical developer contract.',
  'Use it to refine backend-facing data-access inputs the current generator still expects.',
  'The source-of-truth posture now lives in Service Formalization, Capability Formalization, Scenario Coverage Intent, Generation Settings, and Evidence & Verification Plan.',
]
const canonicalBackendBindings = computed(() => {
  if (!developerDefinition.value) return null
  return {
    backendType: developerDefinition.value.backend_bindings.data_access_backend_type as DataAccessBackendType,
    targetLabel: developerDefinition.value.backend_bindings.data_access_target_label,
    implementationLanguage: implementationLanguageForAdapter(developerDefinition.value.generation.codegen_adapter) as DataAccessImplementationLanguage,
  }
})
const canonicalDataAccessGovernance = computed(() => developerDefinition.value?.data_access_governance ?? null)
const canonicalDataDomain = computed(() => developerDefinition.value?.data_domain ?? null)
const pageReady = computed(() =>
  developerReady.value && !!developerDefinition.value && developerDefinitionAligned.value && !!traceabilityRecord.value && coverageMatchesCurrentHandoff.value,
)
const pageLockReasons = computed(() => {
  const reasons: string[] = []
  if (!developerReady.value) {
    reasons.push('Lock a Product Design baseline in Developer Overview first.')
  }
  if (developerReady.value && !developerDefinition.value) {
    reasons.push('Save the Developer Definition first so service count, protocols, scalability, naming, and adapter targets are explicit.')
  }
  if (developerReady.value && developerDefinition.value && !developerDefinitionAligned.value) {
    reasons.push('The saved Developer Definition targets a different locked baseline. Open Developer Definition and save it again for the current baseline.')
  }
  if (developerReady.value && !traceabilityRecord.value) {
    reasons.push('Create and save a Coverage Mapping record before editing the implementation draft.')
  }
  if (developerReady.value && traceabilityRecord.value && !coverageMatchesCurrentHandoff.value) {
    reasons.push('The saved Coverage Mapping record targets a different locked baseline. Open Coverage Mapping and resave it for the current baseline.')
  }
  return reasons
})
const pageWarnings = computed(() => {
  const warnings: string[] = []
  if (traceabilityRecord.value?.pm_review_status === 'changes_requested') {
    warnings.push('PM review is currently requesting changes. Resolve the requested changes before treating this page as complete.')
  }
  if (traceabilityRecord.value && surfaceCoverage.value.length === 0) {
    warnings.push('No Product Design items are linked to the developer-definition sections owned here yet. Use Coverage Mapping to assign what Governed Data Access is responsible for.')
  }
  if (surfaceOpenItems.value.length > 0) {
    warnings.push(`${surfaceOpenItems.value.length} Product Design item${surfaceOpenItems.value.length === 1 ? '' : 's'} linked to this technical area are still open or only partially addressed.`)
  }
  return warnings
})

function applyCanonicalContractBindings() {
  if (!project.value || !canonicalBackendBindings.value || !canonicalDataAccessGovernance.value) return
  project.value.backend.type = canonicalBackendBindings.value.backendType
  project.value.backend.targetLabel = canonicalBackendBindings.value.targetLabel
  project.value.backend.implementationLanguage = canonicalBackendBindings.value.implementationLanguage
  if (canonicalDataDomain.value) {
    project.value.domain = {
      name: canonicalDataDomain.value.domain_name,
      metrics: canonicalDataDomain.value.metrics.map((metric) => ({
        key: metric.key,
        label: metric.label,
        description: metric.description,
      })),
      dimensions: canonicalDataDomain.value.dimensions.map((dimension) => ({
        key: dimension.key,
        label: dimension.label,
        description: dimension.description,
      })),
      filters: canonicalDataDomain.value.filters.map((filterDef) => ({
        key: filterDef.key,
        label: filterDef.label,
        description: filterDef.description,
      })),
      grains: [...canonicalDataDomain.value.grains] as DataAccessProjectState['domain']['grains'],
      resultModes: [...canonicalDataDomain.value.result_modes] as DataAccessProjectState['domain']['resultModes'],
    }
  }
  project.value.governedOutcomes = {
    available: canonicalDataAccessGovernance.value.governed_outcomes.includes('available'),
    restricted: canonicalDataAccessGovernance.value.governed_outcomes.includes('restricted'),
    denied: canonicalDataAccessGovernance.value.governed_outcomes.includes('denied'),
    clarification_required: canonicalDataAccessGovernance.value.governed_outcomes.includes('clarification_required'),
  }
  project.value.permissions.metricRules = canonicalDataAccessGovernance.value.metric_rules.map((rule) => ({
    metricKey: rule.metric_key,
    restrictedToRoles: [...rule.restricted_to_roles],
    deniedRoles: [...rule.denied_roles],
    notes: rule.notes,
  }))
  project.value.permissions.dimensionRules = canonicalDataAccessGovernance.value.dimension_rules.map((rule) => ({
    dimensionKey: rule.dimension_key,
    restrictedToRoles: [...rule.restricted_to_roles],
    deniedRoles: [...rule.denied_roles],
    notes: rule.notes,
  }))
  project.value.permissions.limitRules = canonicalDataAccessGovernance.value.limit_rules.map((rule) => ({
    appliesToRoles: [...rule.applies_to_roles],
    grain: rule.grain as DataAccessProjectState['permissions']['limitRules'][number]['grain'],
    maxRows: rule.max_rows,
    notes: rule.notes,
  }))
  project.value.permissions.useRules = canonicalDataAccessGovernance.value.use_rules.map((rule) => ({
    appliesToRoles: [...rule.applies_to_roles],
    exportAllowed: rule.export_allowed,
    downstreamUse: rule.downstream_use as DataAccessProjectState['permissions']['useRules'][number]['downstreamUse'],
    downgradeDecisionGrade: rule.downgrade_decision_grade,
    notes: rule.notes,
  }))
  project.value.clarification.rules = canonicalDataAccessGovernance.value.clarification_rules.map((rule) => ({
    key: rule.key as DataAccessProjectState['clarification']['rules'][number]['key'],
    enabled: rule.enabled,
    promptHint: rule.prompt_hint,
  }))
}
const DATA_ACCESS_SECTIONS = [
  { id: 'overview', title: 'Overview', description: 'See locked-baseline alignment and what this area owns.' },
  { id: 'backend', title: 'Backend', description: 'Define the service boundary, implementation target, and backend identity.' },
  { id: 'domain', title: 'Domain & Outcomes', description: 'Shape the domain surface, metrics, dimensions, and governed outcomes.' },
  { id: 'policy', title: 'Permissions & Clarification', description: 'Formalize limits, role rules, clarification behavior, and scenario-pack posture.' },
  { id: 'outputs', title: 'Outputs', description: 'Open the compiled Definition launch surface, inspect transitional draft state, and review any current-session artifacts.' },
] as const
type DataAccessSectionId = typeof DATA_ACCESS_SECTIONS[number]['id']
const currentSection = computed<DataAccessSectionId>(() => {
  const raw = typeof route.params.section === 'string' ? route.params.section : 'overview'
  return (DATA_ACCESS_SECTIONS.find((section) => section.id === raw)?.id ?? 'overview') as DataAccessSectionId
})

function openSection(section: DataAccessSectionId) {
  const base = `/design/projects/${studioProjectId.value}/developer/data-access`
  router.push(section === 'overview' ? base : `${base}/${section}`)
}

async function loadSavedProject(id: string) {
  loading.value = true
  error.value = null
  try {
    const record = await getSavedDataAccessProject(id)
    currentSavedId.value = record.id
    project.value = record.state
    name.value = record.state.name
    description.value = record.state.description
    backendType.value = record.state.backend.type
    record.state.backend.implementationLanguage = (record.state.backend.implementationLanguage || 'typescript') as DataAccessImplementationLanguage
    const raw = sessionStorage.getItem(`data-access-seed:${record.id}`)
    derivationReport.value = raw ? (JSON.parse(raw) as DerivationReport) : null
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

function initializeFromCanonicalContract(force = false) {
  if (!developerReady.value) return
  if (autoSeeded.value && !force) return
  applyCanonicalContractBindings()
  derivationReport.value = null
  autoSeeded.value = true
  designPacket.value = null
  capabilityScaffold.value = null
  backendScaffold.value = null
  scenarioPack.value = null
  scenarioManifest.value = null
  generatedBundle.value = null
}

async function saveProject() {
  if (!project.value) return
  applyCanonicalContractBindings()
  loading.value = true
  error.value = null
  try {
    const targetId = currentSavedId.value || slugify(project.value.name) || `data-access-${Date.now()}`
    const record = currentSavedId.value
      ? await updateSavedDataAccessProject(targetId, project.value, studioProjectId.value ?? null)
      : await createSavedDataAccessProject(targetId, project.value, studioProjectId.value ?? null)
    currentSavedId.value = record.id
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

function rolesToText(value: string[]) {
  return value.join(', ')
}

function downloadOutput(output: DataAccessGeneratedOutput | null) {
  if (!output) return
  const mime =
    output.contentType === 'json'
      ? 'application/json;charset=utf-8'
      : output.contentType === 'markdown'
        ? 'text/markdown;charset=utf-8'
        : 'text/plain;charset=utf-8'
  const blob = new Blob([output.content], { type: mime })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = output.filename
  a.click()
  URL.revokeObjectURL(url)
}

function downloadBundle() {
  const outputs = [designPacket.value, capabilityScaffold.value, backendScaffold.value, scenarioPack.value, scenarioManifest.value].filter(
    (value): value is DataAccessGeneratedOutput => Boolean(value),
  )
  if (!outputs.length || !project.value) return
  const bundle = {
    project: {
      name: project.value.name,
      description: project.value.description,
      backend_type: project.value.backend.type,
      generated_at: new Date().toISOString(),
    },
    outputs: outputs.map(output => ({
      kind: output.kind,
      title: output.title,
      filename: output.filename,
      contentType: output.contentType,
      generatedAt: output.generatedAt,
      content: output.content,
    })),
  }
  const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${slugify(project.value.name || 'data-access')}-bundle.json`
  a.click()
  URL.revokeObjectURL(url)
}

function projectIdFromRoute(): string {
  return typeof route.query.project === 'string' ? route.query.project : ''
}

function backendFromRoute(): DataAccessBackendType | null {
  const value = typeof route.query.backend === 'string' ? route.query.backend : ''
  return DATA_ACCESS_BACKEND_OPTIONS.some(option => option.value === value)
    ? (value as DataAccessBackendType)
    : null
}

function wantsFreshDraft(): boolean {
  return route.query.new === '1'
}

function initializeFreshProject(backendOverride?: DataAccessBackendType | null) {
  const resolvedBackend = backendOverride ?? backendType.value
  const resolvedLanguage = project.value?.backend.implementationLanguage || 'typescript'
  backendType.value = resolvedBackend
  currentSavedId.value = null
  derivationReport.value = null
  autoSeeded.value = false
  project.value = createDraftDataAccessProjectState(name.value, description.value, resolvedBackend, resolvedLanguage)
  designPacket.value = null
  capabilityScaffold.value = null
  backendScaffold.value = null
  scenarioPack.value = null
  scenarioManifest.value = null
  generatedBundle.value = null
}

onMounted(async () => {
  try {
    await ensureStudioProjectLoaded()
    const requestedProjectId = projectIdFromRoute()
    const requestedBackend = backendFromRoute()
    if (requestedProjectId) {
      await loadSavedProject(requestedProjectId)
      autoSeeded.value = true
    } else if (wantsFreshDraft()) {
      initializeFreshProject(requestedBackend)
      initializeFromCanonicalContract(true)
    } else {
      initializeFreshProject(requestedBackend)
      initializeFromCanonicalContract(true)
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
})

watch(studioProjectId, async () => {
  await ensureStudioProjectLoaded()
})

watch(
  canonicalBackendBindings,
  () => {
    applyCanonicalContractBindings()
  },
  { immediate: true, deep: true },
)

watch(
  () => route.query.project,
  async (value) => {
    if (typeof value === 'string' && value && value !== currentSavedId.value) {
      await loadSavedProject(value)
      autoSeeded.value = true
    }
  },
)

watch(
  () => [route.query.new, route.query.backend, route.query.project] as const,
  async ([freshFlag, backendValue, projectValue], [previousFreshFlag, previousBackendValue, previousProjectValue]) => {
    const requestedProjectId = typeof projectValue === 'string' ? projectValue : ''
    if (requestedProjectId) return

    const becameFresh =
      freshFlag === '1' && (previousFreshFlag !== '1' || backendValue !== previousBackendValue || projectValue !== previousProjectValue)

    if (!becameFresh) return

    const requestedBackend =
      typeof backendValue === 'string' && DATA_ACCESS_BACKEND_OPTIONS.some(option => option.value === backendValue)
        ? (backendValue as DataAccessBackendType)
        : null

    initializeFreshProject(requestedBackend)
    initializeFromCanonicalContract(true)
  },
)

watch(
  () => [studioProjectId.value, baseline.value?.locked_at, baselineAligned.value] as const,
  async () => {
    if (projectIdFromRoute()) return
    if (!developerReady.value || autoSeeded.value) return
    initializeFromCanonicalContract()
  },
)
</script>

<template>
  <div class="data-access-view">
    <div class="hero">
      <button
        v-if="studioProjectId"
        class="back-link"
        type="button"
        @click="router.push(`/design/projects/${studioProjectId}/developer`)"
      >
        &larr; Back to Developer Design
      </button>
      <div class="hero-kicker">Implementation Pattern</div>
      <h1>{{ studioProject?.name || 'Data Access Pattern' }}</h1>
      <p>Start from the locked Product Design baseline, not from a blank generic template. This page refines the current generator-specific data-access pattern from the approved requirements set, scenario pack, and service design. It is not the primary source-of-truth contract.</p>
    </div>

    <div class="panel transitional-panel">
      <h2>Current Generator Pattern Surface</h2>
      <p class="hint">
        Use this page only for the remaining generator-specific data-access draft residue and output inspection workflow. Canonical contract truth now lives on the formalization pages and in the compiled Developer Definition.
      </p>
    </div>

    <div class="panel">
      <h2>Locked Product Handoff</h2>
      <p class="hint">
        Locked requirements: <strong>{{ lockedRequirements?.title || 'not locked' }}</strong><br>
        Locked scenario pack: <strong>{{ lockedScenarioPack.length ? `${lockedScenarioPack.length} scenarios` : 'not locked' }}</strong><br>
        Primary seed scenario: <strong>{{ lockedPrimaryScenario?.title || 'not recorded' }}</strong><br>
        Locked service design: <strong>{{ lockedShape?.title || 'not locked' }}</strong>
      </p>
      <div class="actions">
        <button @click="initializeFromCanonicalContract(true)" :disabled="loading || !developerReady">
          {{ loading ? 'Working...' : 'Reseed From Product Design' }}
        </button>
        <button class="secondary" @click="saveProject" :disabled="loading || !project">
          {{ loading ? 'Working...' : currentSavedId ? 'Save Pattern Changes' : 'Save Pattern Draft' }}
        </button>
        <button class="secondary" @click="router.push(`/design/projects/${studioProjectId}/developer/definition#generation-launch`)">
          Open Definition Generation
        </button>
      </div>
      <p v-if="currentSavedId" class="saved-id">Pattern draft id: <code>{{ currentSavedId }}</code></p>
      <p v-if="error" class="error">{{ error }}</p>
    </div>

    <div v-if="developerReady" class="panel">
      <div class="panel-header">
        <h2>Pattern Alignment</h2>
        <span class="status-chip" :class="{ ready: pageReady }">
          {{ pageReady ? 'Aligned to locked baseline' : 'Needs baseline alignment' }}
        </span>
      </div>
      <div class="seed-grid">
        <div>
          <h3>Developer Status</h3>
          <p class="hint compact">
            <strong>{{ traceabilityRecord ? developerLabel(traceabilityRecord.developer_status) : 'No record yet' }}</strong>
          </p>
        </div>
        <div>
          <h3>PM Review</h3>
          <p class="hint compact">
            <strong>{{ traceabilityRecord ? pmReviewStatusLabel(traceabilityRecord.pm_review_status) : 'No record yet' }}</strong>
          </p>
        </div>
        <div>
          <h3>Items Linked To This Page</h3>
          <p class="hint compact">
            <strong>{{ surfaceCoverageSummary.total }}</strong> linked ·
            <strong>{{ surfaceCoverageSummary.addressed }}</strong> addressed
          </p>
        </div>
      </div>
      <div class="actions">
        <button class="secondary" @click="router.push(`/design/projects/${studioProjectId}/developer/coverage`)">
          Open Coverage Mapping
        </button>
        <button class="secondary" @click="router.push(`/design/projects/${studioProjectId}/pm-review`)">
          Open PM Review
        </button>
      </div>
      <div v-if="surfaceCoverage.length" class="coverage-list">
        <div v-for="item in surfaceCoverage" :key="item.id" class="coverage-card">
          <div class="coverage-title-row">
            <strong>{{ item.label }}</strong>
            <span class="coverage-status">{{ developerLabel(item.status) }}</span>
          </div>
          <p class="hint compact">{{ item.section }} · {{ item.detail }}</p>
          <p v-if="item.rationale" class="hint compact"><strong>Developer note:</strong> {{ item.rationale }}</p>
        </div>
      </div>
      <p v-else class="hint">This page does not yet have any explicitly linked locked-baseline items.</p>
      <ul v-if="pageWarnings.length" class="notes-list">
        <li v-for="warning in pageWarnings" :key="warning">{{ warning }}</li>
      </ul>
    </div>

    <div v-if="developerReady" class="panel">
      <div class="panel-header">
      <h2>Pattern Sections</h2>
      </div>
      <div class="section-nav-grid">
        <button
          v-for="section in DATA_ACCESS_SECTIONS"
          :key="section.id"
          class="section-nav-card"
          :class="{ active: currentSection === section.id }"
          @click="openSection(section.id)"
        >
          <strong>{{ section.title }}</strong>
          <span>{{ section.description }}</span>
        </button>
      </div>
    </div>

    <div v-if="!pageReady" class="panel">
      <h2>Pattern editing is locked</h2>
      <p class="hint">
        This page only becomes editable when the Product Design baseline is locked and the current baseline has a saved coverage record.
      </p>
      <ul class="notes-list">
        <li v-for="reason in pageLockReasons" :key="reason">{{ reason }}</li>
      </ul>
      <div class="actions">
        <button class="secondary" @click="router.push(`/design/projects/${studioProjectId}/developer`)">Open Developer Overview</button>
        <button v-if="developerReady" class="secondary" @click="router.push(`/design/projects/${studioProjectId}/developer/coverage`)">Open Coverage Mapping</button>
      </div>
    </div>

    <div v-else-if="derivationReport" class="panel">
      <h2>Seeded From Product Design</h2>
      <p class="hint">This draft was seeded from current Product Design context. Review the inferred structure before treating it as implementation-ready.</p>
      <div class="seed-grid">
        <div>
          <h3>Mapped</h3>
          <ul>
            <li v-for="item in derivationReport.mapped_fields" :key="`mapped-${item}`">{{ item }}</li>
          </ul>
        </div>
        <div>
          <h3>Suggested</h3>
          <ul>
            <li v-for="item in derivationReport.suggested_fields" :key="`suggested-${item}`">{{ item }}</li>
          </ul>
        </div>
        <div>
          <h3>Needs Confirmation</h3>
          <ul>
            <li v-for="item in derivationReport.unresolved_fields" :key="`unresolved-${item}`">{{ item }}</li>
          </ul>
        </div>
      </div>
      <ul v-if="derivationReport.notes.length" class="notes-list">
        <li v-for="note in derivationReport.notes" :key="note">{{ note }}</li>
      </ul>
    </div>

    <div v-if="pageReady && currentSection === 'overview'" class="panel">
      <div class="panel-header">
        <h2>Section Overview</h2>
      </div>
      <div class="seed-grid">
        <div>
          <h3>Backend</h3>
          <p class="hint compact">Define the ANIP-facing service boundary and implementation target.</p>
        </div>
        <div>
          <h3>Domain & Outcomes</h3>
          <p class="hint compact">Refine the bounded data surface, supported dimensions, and governed outcomes.</p>
        </div>
        <div>
          <h3>Permissions & Clarification</h3>
          <p class="hint compact">Translate role limits, export posture, and clarification rules into formal service behavior.</p>
        </div>
        <div>
          <h3>Outputs</h3>
          <p class="hint compact">Generation now launches from Developer Definition after the earlier sections reflect the intended governed behavior.</p>
        </div>
      </div>
    </div>

    <div v-if="pageReady && currentSection === 'overview'" class="panel">
      <h2>Pattern Contract Inputs</h2>
      <p class="hint">
        These are the current canonical contract choices this page should follow while the generator still consumes pattern-specific data access inputs.
      </p>
      <div class="field-grid">
        <div v-for="item in patternContractInputs" :key="item.label" class="status-tile">
          <span class="status-label">{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </div>
      </div>
    </div>

    <div v-if="pageReady && currentSection === 'overview'" class="panel">
      <h2>Pattern Role</h2>
      <ul class="notes-list">
        <li v-for="item in patternRoleBullets" :key="item">{{ item }}</li>
      </ul>
      <div class="hero-actions compact-actions">
        <button class="secondary-btn" @click="router.push(`/design/projects/${studioProjectId}/developer/service-formalization`)">Open Service Formalization</button>
        <button class="secondary-btn" @click="router.push(`/design/projects/${studioProjectId}/developer/capability-formalization`)">Open Capability Formalization</button>
        <button class="secondary-btn" @click="router.push(`/design/projects/${studioProjectId}/developer/data-contract-formalization`)">Open Data Contract Formalization</button>
        <button class="secondary-btn" @click="router.push(`/design/projects/${studioProjectId}/developer/scenario-formalization`)">Open Scenario Coverage Intent</button>
        <button class="secondary-btn" @click="router.push(`/design/projects/${studioProjectId}/developer/generation-settings`)">Open Generation Settings</button>
      </div>
    </div>

    <div v-if="project && pageReady && currentSection === 'backend'" class="sections-grid">
      <section class="panel">
        <h2>Auto-Managed Draft Metadata</h2>
        <p class="hint">
          This metadata is seeded and maintained by the current generator path. It affects the saved pattern draft and output packaging, but it is not a canonical design input.
        </p>
        <div class="field-grid">
          <div class="status-tile">
            <span class="status-label">Draft Name</span>
            <strong>{{ project.name || 'Not specified' }}</strong>
          </div>
          <div class="status-tile">
            <span class="status-label">Draft Summary</span>
            <strong>{{ project.description || 'Not specified' }}</strong>
          </div>
          <div class="status-tile">
            <span class="status-label">Backend Type</span>
            <strong>{{ project.backend.type }}</strong>
          </div>
          <div class="status-tile">
            <span class="status-label">Implementation Language</span>
            <strong>{{ project.backend.implementationLanguage }}</strong>
          </div>
          <div class="status-tile">
            <span class="status-label">Target Label</span>
            <strong>{{ project.backend.targetLabel || 'Not specified' }}</strong>
          </div>
        </div>
      </section>
    </div>

    <div v-if="project && pageReady && currentSection === 'domain'" class="sections-grid">
      <section class="panel">
        <h2>Domain</h2>
        <p class="hint compact">Domain shape now comes from the canonical developer contract.</p>
        <button class="mini-btn" @click="router.push(`/design/projects/${studioProjectId}/developer/data-contract-formalization#data-domain`)">Open Data Contract Formalization</button>
        <div v-if="canonicalDataDomain" class="rule-group">
          <div class="meta"><strong>Domain Name:</strong> {{ canonicalDataDomain.domain_name || 'Not specified' }}</div>
          <div class="meta"><strong>Grains:</strong> {{ canonicalDataDomain.grains.join(', ') || 'None' }}</div>
          <div class="meta"><strong>Result Modes:</strong> {{ canonicalDataDomain.result_modes.join(', ') || 'None' }}</div>
          <div class="rule-group">
            <div class="rule-header"><h3>Metrics</h3></div>
            <div v-if="!canonicalDataDomain.metrics.length" class="empty-state">No metrics formalized yet.</div>
            <div v-for="(metric, index) in canonicalDataDomain.metrics" :key="`metric-domain-${index}`" class="rule-card">
              <div class="meta"><strong>{{ metric.label || metric.key || 'Metric' }}</strong> · {{ metric.key || 'No key' }}</div>
              <p class="hint compact">{{ metric.description || 'No description.' }}</p>
            </div>
          </div>
          <div class="rule-group">
            <div class="rule-header"><h3>Dimensions</h3></div>
            <div v-if="!canonicalDataDomain.dimensions.length" class="empty-state">No dimensions formalized yet.</div>
            <div v-for="(dimension, index) in canonicalDataDomain.dimensions" :key="`dimension-domain-${index}`" class="rule-card">
              <div class="meta"><strong>{{ dimension.label || dimension.key || 'Dimension' }}</strong> · {{ dimension.key || 'No key' }}</div>
              <p class="hint compact">{{ dimension.description || 'No description.' }}</p>
            </div>
          </div>
          <div class="rule-group">
            <div class="rule-header"><h3>Filters</h3></div>
            <div v-if="!canonicalDataDomain.filters.length" class="empty-state">No filters formalized yet.</div>
            <div v-for="(filterDef, index) in canonicalDataDomain.filters" :key="`filter-domain-${index}`" class="rule-card">
              <div class="meta"><strong>{{ filterDef.label || filterDef.key || 'Filter' }}</strong> · {{ filterDef.key || 'No key' }}</div>
              <p class="hint compact">{{ filterDef.description || 'No description.' }}</p>
            </div>
          </div>
        </div>
        <p v-else class="empty-state">No canonical data domain has been formalized yet.</p>
      </section>

      <section class="panel">
        <h2>Outcomes</h2>
        <p class="hint compact">Data-access outcomes are currently captured as design metadata only. Generated behavior is driven by Data Contract Formalization and capability contracts.</p>
        <div v-if="canonicalDataAccessGovernance" class="readonly-list">
          <div v-for="outcome in canonicalDataAccessGovernance.governed_outcomes" :key="outcome" class="meta-chip">{{ developerLabel(outcome) }}</div>
          <div v-if="!canonicalDataAccessGovernance.governed_outcomes.length" class="empty-state">No governed outcomes yet.</div>
        </div>
      </section>
    </div>

    <div v-if="project && pageReady && currentSection === 'policy'" class="sections-grid">
      <section class="panel">
        <h2>Permissions</h2>
        <p class="hint">Data-access permission and policy rules are not exposed as a formal edit surface until they are wired to generator/runtime enforcement.</p>
        <div class="rule-group">
          <div class="rule-header">
            <h3>Metric Rules</h3>
          </div>
          <div v-if="!canonicalDataAccessGovernance?.metric_rules.length" class="empty-state">No metric rules yet.</div>
          <div v-for="(rule, index) in canonicalDataAccessGovernance?.metric_rules ?? []" :key="`metric-${index}`" class="rule-card">
            <div class="meta"><strong>{{ rule.metric_key || 'Unnamed metric' }}</strong></div>
            <div class="meta">Restricted To Roles: {{ rolesToText(rule.restricted_to_roles) || 'None' }}</div>
            <div class="meta">Denied Roles: {{ rolesToText(rule.denied_roles) || 'None' }}</div>
            <p class="hint compact">{{ rule.notes || 'No notes.' }}</p>
          </div>
        </div>

        <div class="rule-group">
          <div class="rule-header">
            <h3>Dimension Rules</h3>
          </div>
          <div v-if="!canonicalDataAccessGovernance?.dimension_rules.length" class="empty-state">No dimension rules yet.</div>
          <div v-for="(rule, index) in canonicalDataAccessGovernance?.dimension_rules ?? []" :key="`dimension-${index}`" class="rule-card">
            <div class="meta"><strong>{{ rule.dimension_key || 'Unnamed dimension' }}</strong></div>
            <div class="meta">Restricted To Roles: {{ rolesToText(rule.restricted_to_roles) || 'None' }}</div>
            <div class="meta">Denied Roles: {{ rolesToText(rule.denied_roles) || 'None' }}</div>
            <p class="hint compact">{{ rule.notes || 'No notes.' }}</p>
          </div>
        </div>

        <div class="rule-group">
          <div class="rule-header">
            <h3>Limit Rules</h3>
          </div>
          <div v-if="!canonicalDataAccessGovernance?.limit_rules.length" class="empty-state">No limit rules yet.</div>
          <div v-for="(rule, index) in canonicalDataAccessGovernance?.limit_rules ?? []" :key="`limit-${index}`" class="rule-card">
            <div class="meta">Applies To Roles: {{ rolesToText(rule.applies_to_roles) || 'None' }}</div>
            <div class="meta">Grain: {{ rule.grain || 'Not specified' }} · Max Rows: {{ rule.max_rows }}</div>
            <p class="hint compact">{{ rule.notes || 'No notes.' }}</p>
          </div>
        </div>

        <div class="rule-group">
          <div class="rule-header">
            <h3>Use Rules</h3>
          </div>
          <div v-if="!canonicalDataAccessGovernance?.use_rules.length" class="empty-state">No use rules yet.</div>
          <div v-for="(rule, index) in canonicalDataAccessGovernance?.use_rules ?? []" :key="`use-${index}`" class="rule-card">
            <div class="meta">Applies To Roles: {{ rolesToText(rule.applies_to_roles) || 'None' }}</div>
            <div class="meta">Export Allowed: {{ rule.export_allowed ? 'Yes' : 'No' }} · Downstream Use: {{ rule.downstream_use || 'Not specified' }}</div>
            <div class="meta">Downgrade Decision Grade: {{ rule.downgrade_decision_grade ? 'Yes' : 'No' }}</div>
            <p class="hint compact">{{ rule.notes || 'No notes.' }}</p>
          </div>
        </div>
      </section>

      <section class="panel">
        <h2>Clarification</h2>
        <p class="hint compact">Clarification behavior now comes from the canonical developer contract.</p>
        <div v-for="(rule, index) in canonicalDataAccessGovernance?.clarification_rules ?? []" :key="rule.key || index" class="rule-card">
          <div class="meta"><strong>{{ CLARIFICATION_RULE_OPTIONS.find(option => option.key === rule.key)?.label ?? rule.key }}</strong> · {{ rule.enabled ? 'Enabled' : 'Disabled' }}</div>
          <p class="hint compact">{{ CLARIFICATION_RULE_OPTIONS.find(option => option.key === rule.key)?.description }}</p>
          <p class="hint compact">{{ rule.prompt_hint || 'No prompt hint.' }}</p>
        </div>
        <div v-if="!canonicalDataAccessGovernance?.clarification_rules.length" class="empty-state">No clarification rules yet.</div>
      </section>

    </div>

    <div v-if="project && pageReady && currentSection === 'outputs'" class="sections-grid">
      <section class="panel">
        <h2>Outputs</h2>
        <p class="hint compact">Generation now launches from Developer Definition. This page only reflects transitional draft state and any outputs already present in the current session.</p>
        <div class="actions">
          <button class="secondary" @click="router.push(`/design/projects/${studioProjectId}/developer/definition#generation-launch`)">
            Open Definition Generation
          </button>
          <button class="secondary" @click="downloadBundle" :disabled="!hasOutputs">Download All</button>
        </div>
        <div v-if="hasOutputs" class="download-list">
          <button v-if="designPacket" class="download-btn" @click="downloadOutput(designPacket)">Download Design Packet</button>
          <button v-if="capabilityScaffold" class="download-btn" @click="downloadOutput(capabilityScaffold)">Download ANIP Scaffold</button>
          <button v-if="backendScaffold" class="download-btn" @click="downloadOutput(backendScaffold)">Download Adapter Scaffold</button>
          <button v-if="scenarioPack" class="download-btn" @click="downloadOutput(scenarioPack)">Download Scenario Pack</button>
          <button v-if="scenarioManifest" class="download-btn" @click="downloadOutput(scenarioManifest)">Download Scenario Manifest</button>
        </div>
      </section>
    </div>

    <div v-if="project && pageReady && currentSection === 'outputs'" class="panel">
      <h2>Current Pattern Draft State</h2>
      <p class="hint compact">This JSON reflects the current generator-specific pattern draft after canonical contract bindings have been applied.</p>
      <label class="field">
        <pre>{{ JSON.stringify(project, null, 2) }}</pre>
      </label>
    </div>

    <div v-if="pageReady && currentSection === 'outputs' && hasOutputs" class="outputs-grid">
      <section v-if="designPacket" class="panel">
        <div class="output-header">
          <h2>{{ designPacket.title }}</h2>
          <button class="download-btn" @click="downloadOutput(designPacket)">Download</button>
        </div>
        <pre>{{ designPacket.content }}</pre>
      </section>
      <section v-if="capabilityScaffold" class="panel">
        <div class="output-header">
          <h2>{{ capabilityScaffold.title }}</h2>
          <button class="download-btn" @click="downloadOutput(capabilityScaffold)">Download</button>
        </div>
        <pre>{{ capabilityScaffold.content }}</pre>
      </section>
      <section v-if="backendScaffold" class="panel">
        <div class="output-header">
          <h2>{{ backendScaffold.title }}</h2>
          <button class="download-btn" @click="downloadOutput(backendScaffold)">Download</button>
        </div>
        <pre>{{ backendScaffold.content }}</pre>
      </section>
      <section v-if="scenarioPack" class="panel">
        <div class="output-header">
          <h2>{{ scenarioPack.title }}</h2>
          <button class="download-btn" @click="downloadOutput(scenarioPack)">Download</button>
        </div>
        <pre>{{ scenarioPack.content }}</pre>
      </section>
      <section v-if="scenarioManifest" class="panel">
        <div class="output-header">
          <h2>{{ scenarioManifest.title }}</h2>
          <button class="download-btn" @click="downloadOutput(scenarioManifest)">Download</button>
        </div>
        <pre>{{ scenarioManifest.content }}</pre>
      </section>
    </div>
  </div>
</template>

<style scoped>
.data-access-view {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 24px;
}

.back-link {
  align-self: flex-start;
  border: none;
  background: transparent;
  color: var(--accent);
  font-size: 13px;
  cursor: pointer;
  padding: 0;
  margin-bottom: 0.45rem;
}

.hero-kicker {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 0.45rem;
}

.hero h1 {
  margin: 0 0 8px;
}

.hero p {
  margin: 0;
  color: var(--text-secondary);
  max-width: 820px;
}

.panel {
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 18px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.status-chip {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid color-mix(in srgb, var(--border) 78%, transparent);
  color: var(--text-secondary);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.status-chip.ready {
  border-color: color-mix(in srgb, #45c08a 40%, var(--border));
  color: #45c08a;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 14px;
}

.field input,
.field textarea,
.field select {
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  padding: 10px 12px;
}

.field textarea {
  resize: vertical;
  overflow-wrap: anywhere;
}

.actions {
  display: flex;
  gap: 10px;
}

.hero-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.compact-actions {
  margin-top: 12px;
}

.actions button {
  height: 38px;
  padding: 0 16px;
  border: none;
  border-radius: var(--radius-sm);
  background: var(--accent);
  color: white;
  cursor: pointer;
}

.actions button.secondary {
  background: #305c8b;
}

.secondary-btn {
  height: 36px;
  padding: 0 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-secondary);
  color: var(--text-primary);
  cursor: pointer;
}

.sections-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
}

.outputs-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 16px;
}

.seed-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
}

.section-nav-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.section-nav-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  text-align: left;
  padding: 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-secondary);
  color: var(--text-primary);
  cursor: pointer;
}

.section-nav-card span {
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.5;
}

.section-nav-card.active {
  border-color: color-mix(in srgb, var(--accent) 45%, var(--border));
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 15%, transparent);
}

.coverage-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 10px;
}

.coverage-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, var(--bg-secondary) 88%, transparent);
}

.coverage-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.coverage-status {
  color: var(--text-secondary);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.seed-grid h3 {
  margin: 0 0 8px;
  font-size: 14px;
}

.seed-grid ul,
.notes-list {
  margin: 0;
  padding-left: 18px;
}

.rule-group {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 18px;
}

.rule-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.rule-header h3 {
  margin: 0;
  font-size: 14px;
}

.rule-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, var(--bg-secondary) 88%, transparent);
}

.checkbox-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.readonly-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.meta-chip {
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: color-mix(in srgb, var(--bg-secondary) 88%, transparent);
  color: var(--text-primary);
  font-size: 12px;
}

.download-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 12px;
}

.download-btn {
  height: 32px;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-secondary);
  color: var(--text-primary);
  cursor: pointer;
}

.mini-btn {
  height: 30px;
  padding: 0 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-secondary);
  color: var(--text-primary);
  cursor: pointer;
}

.mini-btn.danger {
  border-color: color-mix(in srgb, #d96b6b 50%, var(--border));
  color: #d96b6b;
}

.output-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.hint,
.saved-id {
  color: var(--text-secondary);
  margin-top: 10px;
}

.transitional-panel {
  margin-bottom: 1rem;
}

.hint.compact {
  margin: 0;
}

.empty-state {
  color: var(--text-secondary);
  font-size: 13px;
}

pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  line-height: 1.5;
}

.error {
  color: #d96b6b;
  margin-top: 12px;
}
</style>
