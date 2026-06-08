<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  APPLICATION_INTEGRATION_BACKEND_OPTIONS,
  type ApplicationIntegrationSeedProfile,
  createDraftApplicationIntegrationProjectState,
} from '../application-integration/defaults'
import { APPLICATION_INTEGRATION_DEFINITION_SECTIONS, developerDefinitionMatchesCurrentContext, findDeveloperDefinitionArtifact, implementationLanguageForAdapter, resolveDeveloperDefinitionLinks } from '../design/developer-definition'
import type {
  ApplicationIntegrationBackendType,
  ApplicationIntegrationImplementationLanguage,
  ApplicationIntegrationGeneratedOutput,
  ApplicationIntegrationProjectState,
} from '../application-integration/types'
import {
  createSavedApplicationIntegrationProject,
  getSavedApplicationIntegrationProject,
  updateSavedApplicationIntegrationProject,
} from '../design/project-api'
import { loadProject, projectStore } from '../design/project-store'
import type { DerivationReport, DeveloperBaselineData, DeveloperDefinitionData, TraceabilityCoverageItem, TraceabilityRecordData } from '../design/project-types'
import {
  normalizeApplicationIntegrationApproverType,
  normalizeApplicationIntegrationAuthType,
  normalizeApplicationIntegrationBackendType,
  normalizeApplicationIntegrationClarificationTriggerType,
  normalizeApplicationIntegrationDenialType,
  normalizeApplicationIntegrationEnvironment,
  normalizeApplicationIntegrationPermissionScopeType,
  normalizeApplicationIntegrationRestrictionType,
} from '../design/use-developer-definition-editor'
import { developerBaselineMatchesCurrentContext, findDeveloperBaselineArtifact, findTraceabilityArtifact, pmReviewStatusLabel, summarizeCoverage } from '../design/traceability'
import { developerLabel } from '../design/developer-vocabulary'

const route = useRoute()
const router = useRouter()
const studioProjectId = computed(() => route.params.projectId as string | undefined)
const studioProject = computed(() => projectStore.activeProject)

const SEED_DEFAULTS: Record<ApplicationIntegrationSeedProfile, { title: string; summary: string }> = {
  salesforce_crm_basic: {
    title: 'Salesforce CRM Basic',
    summary: 'Governed interaction model for bounded CRM account, contact, and follow-up task flows.',
  },
  zendesk_support_basic: {
    title: 'Zendesk Support Basic',
    summary: 'Governed interaction model for bounded Zendesk ticket, requester, and internal-note workflows.',
  },
  hubspot_crm_basic: {
    title: 'HubSpot CRM Basic',
    summary: 'Governed interaction model for bounded HubSpot company, contact, and follow-up workflows.',
  },
  github_issues_basic: {
    title: 'GitHub Issues Basic',
    summary: 'Governed interaction model for bounded GitHub repository issue lookup, issue summary, and approval-gated issue comment workflows.',
  },
  mcp_knowledge_basic: {
    title: 'MCP Knowledge Basic',
    summary: 'Governed interaction model for bounded MCP-backed knowledge search, note retrieval, and approval-gated note creation.',
  },
}

const BACKEND_DEFAULT_SEEDS: Partial<Record<ApplicationIntegrationBackendType, ApplicationIntegrationSeedProfile>> = {
  rest_api: 'salesforce_crm_basic',
  graphql_api: 'github_issues_basic',
  mcp_server: 'mcp_knowledge_basic',
}

const title = ref(SEED_DEFAULTS.salesforce_crm_basic.title)
const summary = ref(SEED_DEFAULTS.salesforce_crm_basic.summary)
const backendType = ref<ApplicationIntegrationBackendType>('rest_api')
const seedProfile = ref<ApplicationIntegrationSeedProfile>('salesforce_crm_basic')
const loading = ref(false)
const error = ref<string | null>(null)
const project = ref<ApplicationIntegrationProjectState | null>(
  createDraftApplicationIntegrationProjectState(title.value, summary.value, backendType.value, seedProfile.value),
)
const designPacket = ref<ApplicationIntegrationGeneratedOutput | null>(null)
const capabilityScaffold = ref<ApplicationIntegrationGeneratedOutput | null>(null)
const backendScaffold = ref<ApplicationIntegrationGeneratedOutput | null>(null)
const scenarioPack = ref<ApplicationIntegrationGeneratedOutput | null>(null)
const scenarioManifest = ref<ApplicationIntegrationGeneratedOutput | null>(null)
const policyStub = ref<ApplicationIntegrationGeneratedOutput | null>(null)
const currentSavedId = ref<string | null>(null)
const derivationReport = ref<DerivationReport | null>(null)
const autoSeeded = ref(false)

const hasOutputs = computed(() =>
  Boolean(designPacket.value || capabilityScaffold.value || backendScaffold.value || scenarioPack.value || scenarioManifest.value || policyStub.value),
)

function slugify(value: string): string {
  return value.toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')
}

function syncControlsFromProject() {
  if (!project.value) return
  title.value = project.value.title
  summary.value = project.value.summary
  backendType.value = project.value.backend.backendType
  project.value.backend.implementationLanguage = (project.value.backend.implementationLanguage || 'typescript') as ApplicationIntegrationImplementationLanguage
  seedProfile.value = (project.value.backend.seedProfile as ApplicationIntegrationSeedProfile) || 'salesforce_crm_basic'
}

function syncDraftFromControls() {
  project.value = createDraftApplicationIntegrationProjectState(
    title.value,
    summary.value,
    backendType.value,
    seedProfile.value,
    project.value?.backend.implementationLanguage || 'typescript',
  )
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
const serviceOptions = computed(() => {
  const shapeData = ((lockedShape.value?.data?.shape ?? lockedShape.value?.data) as Record<string, any> | undefined) ?? {}
  const services = Array.isArray(shapeData.services) ? shapeData.services : []
  return services.map((service: Record<string, any>) => ({
    id: String(service.id ?? ''),
    label: String(service.name ?? service.id ?? 'Service'),
  }))
})

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
    resolveDeveloperDefinitionLinks(item.linked_surfaces).some((surface) => APPLICATION_INTEGRATION_DEFINITION_SECTIONS.includes(surface as any)),
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
      label: 'Integration Backend Type',
      value: developerDefinition.value.backend_bindings.application_integration_backend_type || 'Not specified',
    },
    {
      label: 'Integration System',
      value: developerDefinition.value.backend_bindings.application_integration_system_name || 'Not specified',
    },
    {
      label: 'Integration Auth Type',
      value: developerDefinition.value.backend_bindings.application_integration_auth_type || 'Not specified',
    },
    {
      label: 'Implementation Language',
      value: implementationLanguageForAdapter(developerDefinition.value.generation.codegen_adapter),
    },
  ]
})
const patternRoleBullets = [
  'This page is still a generator-specific pattern surface, not the canonical developer contract.',
  'Use it to refine backend-facing integration inputs the current generator still expects.',
  'The source-of-truth posture now lives in Service Formalization, Capability Formalization, Scenario Coverage Intent, Generation Settings, and Evidence & Verification Plan.',
]
const canonicalCapabilityContracts = computed(() => developerDefinition.value?.capability_formalizations ?? [])
const canonicalIntegrationGovernance = computed(() => developerDefinition.value?.application_integration_governance ?? null)
const canonicalApplicationObjects = computed(() => developerDefinition.value?.application_object_model ?? [])
const canonicalScenarioContracts = computed(() => {
  if (!developerDefinition.value) return []
  const scenarioLookup = new Map(
    lockedScenarioPack.value.map((scenario) => [scenario.id, (scenario.data?.scenario ?? {}) as Record<string, any>] as const),
  )
  const capabilityLookup = new Map(
    developerDefinition.value.capability_formalizations.map((capability) => [capability.capability_id, capability] as const),
  )
  const outcomeLabel = (outcomeType: string, stopCondition: string) => {
    if (stopCondition === 'approval_required' || outcomeType === 'approval_required') return 'approval_required'
    if (stopCondition === 'clarification_required' || outcomeType === 'clarification_required') return 'clarification_required'
    if (stopCondition === 'safe_stop' || outcomeType === 'safe_stop') return 'restricted'
    return 'available'
  }

  return developerDefinition.value.scenario_formalizations.map((formalization) => {
    const sourceScenario = scenarioLookup.get(formalization.scenario_id) ?? {}
    const executableSteps = formalization.orchestration_steps.filter((step) => step.step_kind === 'capability_execution')
    const terminalStep = formalization.orchestration_steps[formalization.orchestration_steps.length - 1] ?? null
    const capabilityHint = formalization.primary_capability || executableSteps[0]?.capability_id || ''
    const backendOperation = executableSteps
      .map((step) => capabilityLookup.get(step.capability_id)?.backend_operation || '')
      .find(Boolean) || ''
    return {
      scenario_id: formalization.scenario_id,
      title: formalization.scenario_title,
      request: String(sourceScenario.description ?? sourceScenario.narrative ?? ''),
      capability_hint: capabilityHint,
      expected_outcome: outcomeLabel(terminalStep?.outcome_type || '', terminalStep?.stop_condition || ''),
      expected_backend_operation: backendOperation,
      notes: formalization.implementation_notes,
      participating_services: formalization.participating_service_ids.map((serviceId) =>
        serviceOptions.value.find((service) => service.id === serviceId)?.label || serviceId,
      ),
    }
  })
})
const canonicalBackendBindings = computed(() => {
  if (!developerDefinition.value) return null
  return {
    backendType: normalizeApplicationIntegrationBackendType(developerDefinition.value.backend_bindings.application_integration_backend_type),
    systemName: developerDefinition.value.backend_bindings.application_integration_system_name,
    environment: normalizeApplicationIntegrationEnvironment(developerDefinition.value.backend_bindings.application_integration_environment),
    authType: normalizeApplicationIntegrationAuthType(developerDefinition.value.backend_bindings.application_integration_auth_type),
    adapterTarget: developerDefinition.value.backend_bindings.application_integration_adapter_target,
    implementationLanguage: implementationLanguageForAdapter(developerDefinition.value.generation.codegen_adapter) as ApplicationIntegrationImplementationLanguage,
  }
})
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
    warnings.push('No Product Design items are linked to the developer-definition sections owned here yet. Use Coverage Mapping to assign what Application Integration is responsible for.')
  }
  if (surfaceOpenItems.value.length > 0) {
    warnings.push(`${surfaceOpenItems.value.length} Product Design item${surfaceOpenItems.value.length === 1 ? '' : 's'} linked to this technical area are still open or only partially addressed.`)
  }
  return warnings
})

function applyCanonicalContractBindings() {
  if (!project.value || !canonicalBackendBindings.value || !canonicalIntegrationGovernance.value) return
  project.value.backend.backendType = canonicalBackendBindings.value.backendType
  project.value.backend.systemName = canonicalBackendBindings.value.systemName
  project.value.backend.environment = canonicalBackendBindings.value.environment
  project.value.backend.authType = canonicalBackendBindings.value.authType
  project.value.backend.adapterTarget = canonicalBackendBindings.value.adapterTarget
  project.value.backend.implementationLanguage = canonicalBackendBindings.value.implementationLanguage
  project.value.objects = canonicalApplicationObjects.value.map((objectDef) => ({
    objectId: objectDef.object_id,
    name: objectDef.name,
    summary: objectDef.summary,
    keyField: objectDef.key_field,
    fields: objectDef.fields.map((field) => ({
      fieldName: field.field_name,
      fieldType: field.field_type as ApplicationIntegrationProjectState['objects'][number]['fields'][number]['fieldType'],
      required: field.required,
      filterable: field.filterable,
      writable: field.writable,
      sensitive: field.sensitive,
      summary: field.summary,
    })),
    relationships: objectDef.relationships.map((relationship) => ({
      relationshipName: relationship.relationship_name,
      targetObjectName: relationship.target_object_name,
      cardinality: relationship.cardinality as ApplicationIntegrationProjectState['objects'][number]['relationships'][number]['cardinality'],
      summary: relationship.summary,
    })),
    sensitiveFieldNames: [...objectDef.sensitive_field_names],
  }))
  project.value.governance.safeDefaults = {
    defaultResultLimit: canonicalIntegrationGovernance.value.safe_defaults.default_result_limit,
    requireApprovalForWrites: canonicalIntegrationGovernance.value.safe_defaults.require_approval_for_writes,
    requireClarificationOnAmbiguousRecord: canonicalIntegrationGovernance.value.safe_defaults.require_clarification_on_ambiguous_record,
    dryRunBeforeWrite: canonicalIntegrationGovernance.value.safe_defaults.dry_run_before_write,
  }
  project.value.governance.permissionRules = canonicalIntegrationGovernance.value.permission_rules.map((rule) => ({
    ruleId: rule.rule_id,
    scopeType: normalizeApplicationIntegrationPermissionScopeType(rule.scope_type),
    scopeName: rule.scope_name,
    actorConstraint: rule.actor_constraint,
    purposeConstraint: rule.purpose_constraint,
    allowed: rule.allowed,
    summary: rule.summary,
  }))
  project.value.governance.clarificationRules = canonicalIntegrationGovernance.value.clarification_rules.map((rule) => ({
    ruleId: rule.rule_id,
    triggerType: normalizeApplicationIntegrationClarificationTriggerType(rule.trigger_type),
    capabilityId: rule.capability_id || null,
    summary: rule.summary,
    promptHint: rule.prompt_hint,
    enabled: rule.enabled,
  }))
  project.value.governance.restrictionRules = canonicalIntegrationGovernance.value.restriction_rules.map((rule) => ({
    ruleId: rule.rule_id,
    restrictionType: normalizeApplicationIntegrationRestrictionType(rule.restriction_type),
    capabilityId: rule.capability_id || null,
    summary: rule.summary,
    value: rule.value,
    enabled: rule.enabled,
  }))
  project.value.governance.denialRules = canonicalIntegrationGovernance.value.denial_rules.map((rule) => ({
    ruleId: rule.rule_id,
    denialType: normalizeApplicationIntegrationDenialType(rule.denial_type),
    capabilityId: rule.capability_id || null,
    summary: rule.summary,
    enabled: rule.enabled,
  }))
  project.value.governance.approvalRules = canonicalIntegrationGovernance.value.approval_rules.map((rule) => ({
    ruleId: rule.rule_id,
    capabilityId: rule.capability_id,
    required: rule.required,
    approverType: normalizeApplicationIntegrationApproverType(rule.approver_type),
    summary: rule.summary,
  }))
  project.value.scenarios = canonicalScenarioContracts.value.map((scenario) => ({
    scenarioId: scenario.scenario_id,
    title: scenario.title,
    request: scenario.request,
    capabilityHint: scenario.capability_hint || null,
    expectedOutcome: scenario.expected_outcome as ApplicationIntegrationProjectState['scenarios'][number]['expectedOutcome'],
    expectedBackendOperation: scenario.expected_backend_operation || null,
    notes: scenario.notes,
  }))
}
const APPLICATION_INTEGRATION_SECTIONS = [
  { id: 'overview', title: 'Overview', description: 'See locked-baseline alignment and what this area owns.' },
  { id: 'backend', title: 'Backend', description: 'Define the system boundary, backend contract, and delivery target.' },
  { id: 'capabilities', title: 'Objects & Capabilities', description: 'Refine the bounded object model and capability ownership.' },
  { id: 'governance', title: 'Governance & Scenarios', description: 'Reflect canonical governance and scenario bindings used by the current generator path.' },
  { id: 'outputs', title: 'Outputs', description: 'Open the compiled Definition launch surface, inspect transitional draft state, and review any current-session artifacts.' },
] as const
type ApplicationIntegrationSectionId = typeof APPLICATION_INTEGRATION_SECTIONS[number]['id']
const currentSection = computed<ApplicationIntegrationSectionId>(() => {
  const raw = typeof route.params.section === 'string' ? route.params.section : 'overview'
  return (APPLICATION_INTEGRATION_SECTIONS.find((section) => section.id === raw)?.id ?? 'overview') as ApplicationIntegrationSectionId
})

function openSection(section: ApplicationIntegrationSectionId) {
  const base = `/design/projects/${studioProjectId.value}/developer/application-integration`
  router.push(section === 'overview' ? base : `${base}/${section}`)
}

async function loadSavedProject(id: string) {
  loading.value = true
  error.value = null
  try {
    const record = await getSavedApplicationIntegrationProject(id)
    currentSavedId.value = record.id
    project.value = record.state
    syncControlsFromProject()
    const raw = sessionStorage.getItem(`application-integration-seed:${record.id}`)
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
  currentSavedId.value = null
  autoSeeded.value = true
  clearOutputs()
}

async function saveProject() {
  if (!project.value) return
  applyCanonicalContractBindings()
  loading.value = true
  error.value = null
  try {
    const targetId = currentSavedId.value || slugify(project.value.title) || `application-integration-${Date.now()}`
    const record = currentSavedId.value
      ? await updateSavedApplicationIntegrationProject(targetId, project.value, studioProjectId.value ?? null)
      : await createSavedApplicationIntegrationProject(targetId, project.value, studioProjectId.value ?? null)
    currentSavedId.value = record.id
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

function clearOutputs() {
  designPacket.value = null
  capabilityScaffold.value = null
  backendScaffold.value = null
  scenarioPack.value = null
  scenarioManifest.value = null
  policyStub.value = null
}

function downloadOutput(output: ApplicationIntegrationGeneratedOutput | null) {
  if (!output) return
  const blob = new Blob([output.content], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = output.filename
  link.click()
  URL.revokeObjectURL(url)
}

watch(
  () => route.query.project,
  async (value) => {
    if (typeof value === 'string' && value && value !== currentSavedId.value) {
      await loadSavedProject(value)
      autoSeeded.value = true
    }
  },
  { immediate: true },
)

watch(
  () => route.query.backend,
  value => {
    if (typeof value === 'string' && APPLICATION_INTEGRATION_BACKEND_OPTIONS.some(option => option.value === value)) {
      backendType.value = value as ApplicationIntegrationBackendType
      if (route.query.new === '1') {
        const defaultSeed = BACKEND_DEFAULT_SEEDS[backendType.value]
        if (defaultSeed) {
          seedProfile.value = defaultSeed
        }
        syncDraftFromControls()
      }
    }
  },
  { immediate: true },
)

watch(seedProfile, (next, previous) => {
  if (route.query.new !== '1' || currentSavedId.value) return
  const nextDefaults = SEED_DEFAULTS[next]
  const previousDefaults = previous ? SEED_DEFAULTS[previous] : null
  if (!previousDefaults || title.value === previousDefaults.title) {
    title.value = nextDefaults.title
  }
  if (!previousDefaults || summary.value === previousDefaults.summary) {
    summary.value = nextDefaults.summary
  }
})

watch([title, summary, backendType, seedProfile], () => {
  if (route.query.new === '1' && !currentSavedId.value) {
    syncDraftFromControls()
    autoSeeded.value = false
  }
})

onMounted(async () => {
  await ensureStudioProjectLoaded()
  if (typeof route.query.project === 'string' && route.query.project) {
    await loadSavedProject(route.query.project)
    autoSeeded.value = true
  } else {
    syncDraftFromControls()
    initializeFromCanonicalContract(true)
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
  () => [studioProjectId.value, baseline.value?.locked_at, baselineAligned.value] as const,
  async () => {
    if (typeof route.query.project === 'string' && route.query.project) return
    if (!developerReady.value || autoSeeded.value) return
    initializeFromCanonicalContract()
  },
)
</script>

<template>
  <div class="application-integration-view">
    <header class="hero">
      <div>
        <button
          v-if="studioProjectId"
          class="back-link"
          type="button"
          @click="router.push(`/design/projects/${studioProjectId}/developer`)"
        >
          &larr; Back to Developer Design
        </button>
        <div class="hero-kicker">Implementation Pattern</div>
        <h1>{{ studioProject?.name || 'Integration Pattern' }}</h1>
      <p>
        Start from the locked Product Design baseline, not from a standalone seed library. This page refines the current generator-specific application-integration pattern from the approved requirements set, scenario pack, and service design. It is not the primary source-of-truth contract.
      </p>
      </div>
      <div class="panel transitional-panel">
        <h2>Current Generator Pattern Surface</h2>
        <p class="hint">
          Use this page only for the remaining generator-specific integration draft residue and output inspection workflow. Canonical contract truth now lives on the formalization pages and in the compiled Developer Definition.
        </p>
      </div>
      <div class="hero-actions">
        <button class="secondary-btn" @click="initializeFromCanonicalContract(true)" :disabled="loading || !developerReady">
          {{ loading ? 'Working…' : 'Reseed From Product Design' }}
        </button>
        <button class="secondary-btn" @click="saveProject" :disabled="loading || !project">
          {{ loading ? 'Saving…' : currentSavedId ? 'Save Pattern Changes' : 'Save Pattern Draft' }}
        </button>
        <button class="secondary-btn" @click="router.push(`/design/projects/${studioProjectId}/developer/definition#generation-launch`)">
          Open Definition Generation
        </button>
      </div>
    </header>

    <p v-if="error" class="error">{{ error }}</p>

    <section class="panel controls">
      <h2>Locked Product Handoff</h2>
      <div class="field-grid">
        <div class="status-tile">
          <span class="status-label">Requirements</span>
          <strong>{{ lockedRequirements?.title || 'Not locked' }}</strong>
        </div>
        <div class="status-tile">
          <span class="status-label">Scenario Pack</span>
          <strong>{{ lockedScenarioPack.length ? `${lockedScenarioPack.length} scenarios` : 'Not locked' }}</strong>
        </div>
        <div class="status-tile">
          <span class="status-label">Service Design</span>
          <strong>{{ lockedShape?.title || 'Not locked' }}</strong>
        </div>
        <div class="status-tile">
          <span class="status-label">Primary Seed Scenario</span>
          <strong>{{ lockedPrimaryScenario?.title || 'Not recorded' }}</strong>
        </div>
        <div class="status-tile">
          <span class="status-label">Pattern Draft Id</span>
          <strong>{{ currentSavedId || 'Product-seeded draft' }}</strong>
        </div>
      </div>
    </section>

    <section v-if="developerReady" class="panel controls">
      <div class="section-header">
        <div>
          <h2>Pattern Alignment</h2>
          <p>Use the saved coverage record to keep this page aligned to the locked Product Design baseline.</p>
        </div>
        <span class="mode-indicator" :class="{ active: pageReady }">
          {{ pageReady ? 'Aligned to locked baseline' : 'Needs baseline alignment' }}
        </span>
      </div>
      <div class="field-grid">
        <div class="status-tile">
          <span class="status-label">Developer Status</span>
          <strong>{{ traceabilityRecord ? developerLabel(traceabilityRecord.developer_status) : 'No record yet' }}</strong>
        </div>
        <div class="status-tile">
          <span class="status-label">PM Review</span>
          <strong>{{ traceabilityRecord ? pmReviewStatusLabel(traceabilityRecord.pm_review_status) : 'No record yet' }}</strong>
        </div>
        <div class="status-tile">
          <span class="status-label">Items Linked To This Page</span>
          <strong>{{ surfaceCoverageSummary.total }} linked · {{ surfaceCoverageSummary.addressed }} addressed</strong>
        </div>
      </div>
      <div class="hero-actions">
        <button class="secondary-btn" @click="router.push(`/design/projects/${studioProjectId}/developer/coverage`)">Open Coverage Mapping</button>
        <button class="secondary-btn" @click="router.push(`/design/projects/${studioProjectId}/pm-review`)">Open PM Review</button>
      </div>
      <div v-if="surfaceCoverage.length" class="rule-list">
        <article v-for="item in surfaceCoverage" :key="item.id" class="info-card">
          <div class="editor-card-header">
            <h3>{{ item.label }}</h3>
            <span class="status-label">{{ developerLabel(item.status) }}</span>
          </div>
          <p>{{ item.section }} · {{ item.detail }}</p>
          <p v-if="item.rationale" class="meta"><strong>Developer note:</strong> {{ item.rationale }}</p>
        </article>
      </div>
      <p v-else class="meta">This page does not yet have any explicitly linked locked-baseline items.</p>
      <ul v-if="pageWarnings.length">
        <li v-for="warning in pageWarnings" :key="warning">{{ warning }}</li>
      </ul>
    </section>

    <section v-if="developerReady" class="panel controls">
      <div class="section-header">
        <div>
          <h2>Pattern Sections</h2>
        </div>
      </div>
      <div class="field-grid">
        <button
          v-for="section in APPLICATION_INTEGRATION_SECTIONS"
          :key="section.id"
          class="section-nav-card"
          :class="{ active: currentSection === section.id }"
          @click="openSection(section.id)"
        >
          <strong>{{ section.title }}</strong>
          <span>{{ section.description }}</span>
        </button>
      </div>
    </section>

    <section v-if="!pageReady" class="panel controls">
      <h2>Pattern editing is locked</h2>
      <p class="hint">
        This page only becomes editable when the Product Design baseline is locked and the current baseline has a saved coverage record.
      </p>
      <ul>
        <li v-for="reason in pageLockReasons" :key="reason">{{ reason }}</li>
      </ul>
      <div class="hero-actions">
        <button class="secondary-btn" @click="router.push(`/design/projects/${studioProjectId}/developer`)">Open Developer Overview</button>
        <button v-if="developerReady" class="secondary-btn" @click="router.push(`/design/projects/${studioProjectId}/developer/coverage`)">Open Coverage Mapping</button>
      </div>
    </section>

    <section v-else-if="derivationReport" class="panel controls">
      <h2>Seeded From Product Design</h2>
      <p class="hint">This draft was seeded from current Product Design context. Review the inferred API surface and governance before treating it as implementation-ready.</p>
      <div class="card-grid">
        <article class="info-card">
          <h3>Mapped Fields</h3>
          <ul>
            <li v-for="field in derivationReport.mapped_fields" :key="field">{{ field }}</li>
          </ul>
        </article>
        <article class="info-card">
          <h3>Suggested Fields</h3>
          <ul>
            <li v-for="field in derivationReport.suggested_fields" :key="field">{{ field }}</li>
          </ul>
        </article>
        <article class="info-card">
          <h3>Needs Developer Confirmation</h3>
          <ul>
            <li v-for="field in derivationReport.unresolved_fields" :key="field">{{ field }}</li>
          </ul>
        </article>
      </div>
    </section>

    <section v-if="pageReady && currentSection === 'overview'" class="panel controls">
      <div class="section-header">
        <div>
          <h2>Section Overview</h2>
        </div>
      </div>
      <div class="field-grid">
        <div class="status-tile">
          <span class="status-label">Backend</span>
          <strong>System boundary, auth, and delivery target.</strong>
        </div>
        <div class="status-tile">
          <span class="status-label">Objects & Capabilities</span>
          <strong>Object reference plus canonical capability contracts.</strong>
        </div>
        <div class="status-tile">
          <span class="status-label">Governance & Scenarios</span>
          <strong>Safe defaults, approval posture, and scenario expectations.</strong>
        </div>
        <div class="status-tile">
          <span class="status-label">Outputs</span>
          <strong>Definition-launched outputs and current draft evidence.</strong>
        </div>
      </div>
    </section>

    <section v-if="pageReady && currentSection === 'overview'" class="panel controls">
      <div class="section-header">
        <div>
          <h2>Pattern Contract Inputs</h2>
          <p>These are the current canonical contract choices this page should follow while the generator still consumes pattern-specific integration inputs.</p>
        </div>
      </div>
      <div class="field-grid">
        <div v-for="item in patternContractInputs" :key="item.label" class="status-tile">
          <span class="status-label">{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </div>
      </div>
    </section>

    <section v-if="pageReady && currentSection === 'overview'" class="panel controls">
      <div class="section-header">
        <div>
          <h2>Pattern Role</h2>
        </div>
      </div>
      <ul class="warning-list">
        <li v-for="item in patternRoleBullets" :key="item">{{ item }}</li>
      </ul>
      <div class="hero-actions compact-actions">
        <button class="secondary-btn" @click="router.push(`/design/projects/${studioProjectId}/developer/service-formalization`)">Open Service Formalization</button>
        <button class="secondary-btn" @click="router.push(`/design/projects/${studioProjectId}/developer/capability-formalization`)">Open Capability Formalization</button>
        <button class="secondary-btn" @click="router.push(`/design/projects/${studioProjectId}/developer/data-contract-formalization`)">Open Data Contract Formalization</button>
        <button class="secondary-btn" @click="router.push(`/design/projects/${studioProjectId}/developer/scenario-formalization`)">Open Scenario Coverage Intent</button>
        <button class="secondary-btn" @click="router.push(`/design/projects/${studioProjectId}/developer/generation-settings`)">Open Generation Settings</button>
      </div>
    </section>

    <section v-if="pageReady && currentSection === 'backend'" class="panel controls">
      <h2>Auto-Managed Draft Metadata</h2>
      <p class="hint compact">
        This metadata is seeded and maintained by the current generator path. It affects the saved pattern draft and output packaging, but it is not a canonical design input.
      </p>
      <div class="field-grid">
        <div class="status-tile">
          <span class="status-label">Draft Title</span>
          <strong>{{ title || 'Not specified' }}</strong>
        </div>
        <div class="status-tile">
          <span class="status-label">Seed Profile</span>
          <strong>{{ seedProfile || 'Not specified' }}</strong>
        </div>
        <div class="status-tile">
          <span class="status-label">Draft Summary</span>
          <strong>{{ summary || 'Not specified' }}</strong>
        </div>
      </div>
    </section>

    <section v-if="project && pageReady && currentSection === 'backend'" class="panel">
      <h2>Runtime Connection Draft</h2>
      <p class="hint">
        Backend type, system identity, auth type, adapter target, and implementation language now come from Service Formalization and Generation Settings. Keep only runtime connection residue here.
      </p>
      <div class="field-grid">
        <div class="status-tile">
          <span class="status-label">Backend Type</span>
          <strong>{{ project.backend.backendType }}</strong>
        </div>
        <div class="status-tile">
          <span class="status-label">System</span>
          <strong>{{ project.backend.systemName || 'Not specified' }}</strong>
        </div>
        <div class="status-tile">
          <span class="status-label">Environment</span>
          <strong>{{ project.backend.environment }}</strong>
        </div>
        <div class="status-tile">
          <span class="status-label">Auth Type</span>
          <strong>{{ project.backend.authType }}</strong>
        </div>
        <div class="status-tile">
          <span class="status-label">Backend Template</span>
          <strong>{{ project.backend.adapterTarget || 'Not specified' }}</strong>
        </div>
        <div class="status-tile">
          <span class="status-label">Implementation Language</span>
          <strong>{{ project.backend.implementationLanguage }}</strong>
        </div>
      </div>
      <div class="two-col">
        <label><span>Base URL</span><input v-model="project.backend.baseUrl" type="text" /></label>
      </div>
      <label><span>Auth Notes</span><textarea v-model="project.backend.authNotes" rows="2" /></label>
    </section>

    <section v-if="project && pageReady && currentSection === 'capabilities'" class="panel">
      <div class="section-header">
        <div>
          <h2>Objects</h2>
          <p>Object model now comes from the canonical developer contract.</p>
        </div>
        <button class="secondary-btn" @click="router.push(`/design/projects/${studioProjectId}/developer/data-contract-formalization#application-object-model`)">Open Data Contract Formalization</button>
      </div>
      <div class="card-grid">
        <article v-for="objectDef in canonicalApplicationObjects" :key="objectDef.object_id" class="info-card">
          <h3>{{ objectDef.name || objectDef.object_id }}</h3>
          <p>{{ objectDef.summary || 'No summary yet.' }}</p>
          <div class="meta">Object ID: {{ objectDef.object_id || 'Not specified' }}</div>
          <div class="meta">Key field: {{ objectDef.key_field || 'Not specified' }}</div>
          <div class="meta">Fields: {{ objectDef.fields.length }} · Relationships: {{ objectDef.relationships.length }}</div>
          <div class="meta">Sensitive fields: {{ objectDef.sensitive_field_names.join(', ') || 'None' }}</div>
        </article>
      </div>
      <p v-if="!canonicalApplicationObjects.length" class="hint">No canonical application objects have been formalized yet.</p>
    </section>

    <section v-if="project && pageReady && currentSection === 'capabilities'" class="panel">
      <div class="section-header">
        <div>
          <h2>Capabilities</h2>
          <p>Capability identity and bounded behavior now live on the canonical Capability Formalization page. This section only reflects the current contract and any remaining pattern-specific draft residue.</p>
        </div>
        <button class="secondary-btn" @click="router.push(`/design/projects/${studioProjectId}/developer/capability-formalization`)">Open Capability Formalization</button>
      </div>
      <div class="card-grid" v-if="canonicalCapabilityContracts.length">
        <article v-for="capability in canonicalCapabilityContracts" :key="capability.id" class="info-card">
          <h3>{{ capability.title || capability.capability_id }}</h3>
          <p>{{ capability.summary || 'No summary yet.' }}</p>
          <div class="meta">Capability ID: {{ capability.capability_id || 'Not specified' }}</div>
          <div class="meta">Operation: {{ developerLabel(capability.operation_type, 'Not specified') }} · Side Effect: {{ developerLabel(capability.side_effect_level, 'Not specified') }}</div>
          <div class="meta">Backend Operation: {{ capability.backend_operation || 'Not specified' }}</div>
        </article>
      </div>
      <p v-else class="hint">No canonical capability contracts have been formalized yet.</p>
    </section>

    <section v-if="project && pageReady && currentSection === 'governance'" class="panel">
      <div class="section-header">
        <div>
          <h2>Governance</h2>
          <p>These governance rules now come from the canonical developer contract. This page reflects them for the current generator path but does not own them.</p>
        </div>
        <button class="secondary-btn" @click="router.push(`/design/projects/${studioProjectId}/developer/governance-bindings`)">Open Roles & Access</button>
      </div>
      <div class="card-grid" v-if="canonicalIntegrationGovernance">
        <article class="info-card">
          <h3>Safe Defaults</h3>
          <div class="meta">Default Result Limit: {{ canonicalIntegrationGovernance.safe_defaults.default_result_limit }}</div>
          <div class="meta">Require Approval For Writes: {{ canonicalIntegrationGovernance.safe_defaults.require_approval_for_writes ? 'Yes' : 'No' }}</div>
          <div class="meta">Clarify Ambiguous Record: {{ canonicalIntegrationGovernance.safe_defaults.require_clarification_on_ambiguous_record ? 'Yes' : 'No' }}</div>
          <div class="meta">Dry Run Before Write: {{ canonicalIntegrationGovernance.safe_defaults.dry_run_before_write ? 'Yes' : 'No' }}</div>
        </article>
        <article class="info-card">
          <div class="editor-card-header"><h3>Permission Rules</h3></div>
          <div v-if="!canonicalIntegrationGovernance.permission_rules.length" class="empty-state">No permission rules yet.</div>
          <div v-for="rule in canonicalIntegrationGovernance.permission_rules" :key="rule.rule_id" class="rule-row rule-row-readonly">
            <div class="meta"><strong>{{ rule.rule_id }}</strong> · {{ rule.scope_type }} · {{ rule.scope_name || 'No scope name' }}</div>
            <div class="meta">Actor: {{ rule.actor_constraint || 'Not specified' }} · Purpose: {{ rule.purpose_constraint || 'Not specified' }} · Allowed: {{ rule.allowed ? 'Yes' : 'No' }}</div>
            <p class="hint compact">{{ rule.summary || 'No summary yet.' }}</p>
          </div>
        </article>
        <article class="info-card">
          <div class="editor-card-header"><h3>Restriction Rules</h3></div>
          <div v-if="!canonicalIntegrationGovernance.restriction_rules.length" class="empty-state">No restriction rules yet.</div>
          <div v-for="rule in canonicalIntegrationGovernance.restriction_rules" :key="rule.rule_id" class="rule-row rule-row-readonly">
            <div class="meta"><strong>{{ rule.rule_id }}</strong> · {{ rule.restriction_type }} · {{ rule.enabled ? 'Enabled' : 'Disabled' }}</div>
            <div class="meta">Capability: {{ rule.capability_id || 'Not specified' }} · Value: {{ rule.value || 'Not specified' }}</div>
            <p class="hint compact">{{ rule.summary || 'No summary yet.' }}</p>
          </div>
        </article>
        <article class="info-card">
          <div class="editor-card-header"><h3>Clarification Rules</h3></div>
          <div v-if="!canonicalIntegrationGovernance.clarification_rules.length" class="empty-state">No clarification rules yet.</div>
          <div class="rule-list">
            <div v-for="rule in canonicalIntegrationGovernance.clarification_rules" :key="rule.rule_id" class="rule-row rule-row-readonly">
              <div class="meta"><strong>{{ rule.rule_id }}</strong> · {{ rule.trigger_type }} · {{ rule.enabled ? 'Enabled' : 'Disabled' }}</div>
              <div class="meta">Capability: {{ rule.capability_id || 'Not specified' }}</div>
              <p class="hint compact">{{ rule.summary || 'No summary yet.' }}</p>
              <p class="hint compact">{{ rule.prompt_hint || 'No prompt hint.' }}</p>
            </div>
          </div>
        </article>
        <article class="info-card">
          <div class="editor-card-header"><h3>Denial Rules</h3></div>
          <div v-if="!canonicalIntegrationGovernance.denial_rules.length" class="empty-state">No denial rules yet.</div>
          <div class="rule-list">
            <div v-for="rule in canonicalIntegrationGovernance.denial_rules" :key="rule.rule_id" class="rule-row rule-row-readonly">
              <div class="meta"><strong>{{ rule.rule_id }}</strong> · {{ rule.denial_type }} · {{ rule.enabled ? 'Enabled' : 'Disabled' }}</div>
              <div class="meta">Capability: {{ rule.capability_id || 'Not specified' }}</div>
              <p class="hint compact">{{ rule.summary || 'No summary yet.' }}</p>
            </div>
          </div>
        </article>
        <article class="info-card">
          <div class="editor-card-header"><h3>Approval Rules</h3></div>
          <div v-if="!canonicalIntegrationGovernance.approval_rules.length" class="empty-state">No approval rules yet.</div>
          <div class="rule-list">
            <div v-for="rule in canonicalIntegrationGovernance.approval_rules" :key="rule.rule_id" class="rule-row rule-row-readonly">
              <div class="meta"><strong>{{ rule.rule_id }}</strong> · {{ rule.required ? 'Required' : 'Optional' }} · {{ rule.approver_type || 'No approver type' }}</div>
              <div class="meta">Capability: {{ rule.capability_id || 'Not specified' }}</div>
              <p class="hint compact">{{ rule.summary || 'No summary yet.' }}</p>
            </div>
          </div>
        </article>
      </div>
      <p v-else class="hint">No canonical integration governance has been formalized yet.</p>
    </section>

    <section v-if="project && pageReady && currentSection === 'governance'" class="panel">
      <div class="section-header">
        <div>
          <h2>Scenarios</h2>
          <p>Scenario cards now come from the canonical scenario formalization contract. This page only reflects how the current generator path will consume them.</p>
        </div>
        <button class="secondary-btn" @click="router.push(`/design/projects/${studioProjectId}/developer/scenario-formalization#scenario-context`)">Open Scenario Coverage Intent</button>
      </div>
      <div class="editor-list">
        <article v-for="scenario in canonicalScenarioContracts" :key="scenario.scenario_id" class="editor-card">
          <div class="editor-card-header">
            <h3>{{ scenario.title }}</h3>
          </div>
          <div class="two-col">
            <div class="meta"><strong>Scenario ID:</strong> {{ scenario.scenario_id }}</div>
            <div class="meta"><strong>Expected Outcome:</strong> {{ scenario.expected_outcome }}</div>
            <div class="meta"><strong>Capability Hint:</strong> {{ scenario.capability_hint || 'Not specified' }}</div>
            <div class="meta"><strong>Backend Operation:</strong> {{ scenario.expected_backend_operation || 'Not specified' }}</div>
          </div>
          <div class="meta"><strong>Participating Services:</strong> {{ scenario.participating_services.join(', ') || 'None selected' }}</div>
          <label><span>Request Context</span><textarea :value="scenario.request || 'No Product Design scenario narrative recorded.'" rows="2" readonly /></label>
          <label><span>Implementation Notes</span><textarea :value="scenario.notes || 'No implementation notes yet.'" rows="2" readonly /></label>
        </article>
        <p v-if="!canonicalScenarioContracts.length" class="hint">No canonical scenario contracts have been formalized yet.</p>
      </div>
    </section>

    <section v-if="pageReady && currentSection === 'outputs'" class="panel">
      <div class="section-header">
        <div>
          <h2>Outputs</h2>
          <p v-if="!hasOutputs">Generation now launches from Developer Definition. This page only reflects transitional draft state and any outputs already present in the current session.</p>
        </div>
        <button class="secondary-btn" @click="router.push(`/design/projects/${studioProjectId}/developer/definition#generation-launch`)">
          Open Definition Generation
        </button>
      </div>
      <div class="outputs">
        <article
          v-for="output in [designPacket, capabilityScaffold, backendScaffold, scenarioPack, scenarioManifest, policyStub]"
          :key="output?.kind || output?.filename || 'empty'"
          class="output-card"
        >
          <template v-if="output">
            <div class="output-header">
              <div>
                <h3>{{ output.title }}</h3>
                <p>{{ output.filename }}</p>
              </div>
              <button class="secondary-btn" @click="downloadOutput(output)">Download</button>
            </div>
            <pre>{{ output.content }}</pre>
          </template>
        </article>
      </div>
    </section>
  </div>
</template>

<style scoped>
.application-integration-view {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 24px;
}
.hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
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

.hero h1,
.panel h2,
.info-card h3,
.output-card h3,
.editor-card h3 {
  margin: 0;
}
.hero p,
.info-card p,
.output-card p,
.section-header p {
  margin: 6px 0 0;
  color: var(--text-secondary);
  line-height: 1.5;
}
.hero-actions,
.section-header {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.compact-actions {
  margin-top: 12px;
  flex-wrap: wrap;
}
.panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-input);
}
.mode-indicator {
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
.mode-indicator.active {
  border-color: color-mix(in srgb, #45c08a 40%, var(--border));
  color: #45c08a;
}

.transitional-panel {
  margin-top: 1rem;
}

.field-grid,
.two-col {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
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
  background: var(--bg-content);
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
label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: var(--text-secondary);
}
input,
select,
textarea {
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-app);
  color: var(--text-primary);
  font: inherit;
}

textarea {
  resize: vertical;
  overflow-wrap: anywhere;
}
input:focus,
select:focus,
textarea:focus {
  outline: none;
  border-color: var(--border-focus);
  box-shadow: 0 0 0 3px var(--accent-glow);
}
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 12px;
}
.info-card,
.output-card,
.editor-card,
.status-tile {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-content);
}
.editor-list,
.outputs,
.rule-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.editor-card-header,
.output-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.rule-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 8px;
  align-items: start;
}
.rule-row textarea {
  min-height: 72px;
}
.rule-row-readonly {
  grid-template-columns: 1fr;
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, var(--bg-secondary) 88%, transparent);
}
.meta,
.status-label {
  color: var(--text-secondary);
  font-size: 13px;
}
.toggle-row {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 8px;
}
.toggle-row.compact {
  white-space: nowrap;
}
.toggle-row input {
  width: auto;
}
pre {
  margin: 0;
  max-height: 240px;
  overflow: auto;
  padding: 12px;
  border-radius: var(--radius-sm);
  background: var(--bg-app);
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
}
.primary-btn,
.secondary-btn,
.ghost-danger {
  height: 36px;
  padding: 0 14px;
  border-radius: var(--radius-sm);
  cursor: pointer;
}
.primary-btn {
  border: none;
  background: var(--accent);
  color: #fff;
}
.secondary-btn {
  border: 1px solid var(--border);
  background: var(--bg-content);
  color: var(--text-primary);
}
.ghost-danger {
  border: 1px solid rgba(248, 113, 113, 0.28);
  background: rgba(248, 113, 113, 0.08);
  color: var(--error);
}
.error {
  color: var(--error);
  margin: 0;
}
@media (max-width: 900px) {
  .hero,
  .section-header,
  .hero-actions,
  .editor-card-header,
  .output-header {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
