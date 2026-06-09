<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import StudioFlowDiagram, {
  type StudioFlowDiagramNode,
  type StudioFlowDiagramStatus,
} from '../design/components/StudioFlowDiagram.vue'
import StudioNodeDiagram, {
  type StudioDiagramEdge,
  type StudioDiagramNode,
  type StudioDiagramStatus,
} from '../design/components/StudioNodeDiagram.vue'
import { Position } from '@vue-flow/core'
import {
  findDeveloperDefinitionArtifact,
} from '../design/developer-definition'
import { effectLabel } from '../design/effect-vocabulary'
import {
  findLatestProductDesignRevisionArtifact,
  type ProductDesignRevisionData,
} from '../design/product-design'
import { loadProject, projectStore } from '../design/project-store'
import type {
  DeveloperCapabilityFormalization,
  DeveloperDefinitionData,
  DeveloperServiceBackendBinding,
  DeveloperServiceTopologyBinding,
  TraceabilityRecordData,
} from '../design/project-types'
import { findDeveloperBaselineArtifact, findTraceabilityArtifact } from '../design/traceability'
import { formatStudioTimestamp } from '../design/time'

const route = useRoute()
const router = useRouter()

const projectId = computed(() => route.params.projectId as string)
const project = computed(() => projectStore.activeProject)
const requirements = computed(() => projectStore.artifacts.requirements)
type DeveloperDiagramTab = 'architecture' | 'glue' | 'artifacts'
const activeDiagramTab = ref<DeveloperDiagramTab>('architecture')
const diagramFitVersion = ref(0)

interface AppGlueDiagramItem {
  id: string
  title: string
  detail: string
  recommendation?: string
  capability_id?: string
  category?: string
  reviewed: boolean
  count?: number
}

async function ensureLoaded() {
  if (!projectId.value) return
  if (projectStore.activeProject?.id === projectId.value) return
  await loadProject(projectId.value)
}

onMounted(ensureLoaded)
watch(projectId, ensureLoaded)
watch(
  () => route.query.diagram,
  (value) => {
    if (value === 'artifacts' || value === 'architecture' || value === 'glue') {
      activeDiagramTab.value = value
    }
  },
  { immediate: true },
)

const developerDefinitionArtifact = computed(() => findDeveloperDefinitionArtifact(projectStore.artifacts.pmArtifacts))
const developerDefinition = computed(() =>
  (developerDefinitionArtifact.value?.data as DeveloperDefinitionData | undefined) ?? null,
)
const baselineArtifact = computed(() => findDeveloperBaselineArtifact(projectStore.artifacts.pmArtifacts))
const traceabilityArtifact = computed(() => findTraceabilityArtifact(projectStore.artifacts.pmArtifacts))
const traceability = computed(() =>
  (traceabilityArtifact.value?.data as TraceabilityRecordData | undefined) ?? null,
)
const productRevisionArtifact = computed(() => findLatestProductDesignRevisionArtifact(projectStore.artifacts.pmArtifacts))
const productRevision = computed(() =>
  (productRevisionArtifact.value?.data as ProductDesignRevisionData | undefined) ?? null,
)
function path(suffix: string): string {
  return `/design/projects/${projectId.value}${suffix}`
}

function servicePath(serviceId: string): string {
  return `${path('/developer/service-formalization')}#${encodeURIComponent(serviceId)}`
}

function capabilityPath(capabilityId: string): string {
  return `${path('/developer/capability-formalization')}#${encodeURIComponent(capabilityId)}`
}

function capabilityServicePath(serviceId: string): string {
  return `${path('/developer/capability-formalization')}#${encodeURIComponent(`service:${serviceId}`)}`
}

function capabilityBehaviorPath(serviceId: string): string {
  return `${path('/developer/capability-formalization')}#${encodeURIComponent(`behavior:${serviceId}`)}`
}

function governancePath(): string {
  return path('/developer/governance-bindings')
}

function actorModelPath(): string {
  return path('/actor-model')
}

function permissionIntentPath(): string {
  return path('/permission-intent')
}

function verificationPath(): string {
  return path('/developer/verification-expectations')
}

function appGluePath(): string {
  return path('/developer/app-glue')
}

function setDiagramTab(tab: DeveloperDiagramTab) {
  diagramFitVersion.value += 1
  activeDiagramTab.value = tab
  const query = { ...route.query }
  if (tab === 'architecture') {
    delete query.diagram
  } else {
    query.diagram = tab
  }
  void router.replace({ path: route.path, query })
}

function humanizeToken(value: string): string {
  return value
    .replace(/^gtm[._-]/i, '')
    .replace(/[._-]+/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function deniedEffectLabel(value: string): string {
  const label = effectLabel(value)
  if (label.startsWith('No ')) return label
  return `No ${label.charAt(0).toLowerCase()}${label.slice(1)}`
}

function capabilityBehaviorBadges(capability: DeveloperCapabilityFormalization): string[] {
  const badges = new Set<string>()
  if (capability.side_effect_level === 'read') badges.add('Read-only')
  if (capability.side_effect_level && capability.side_effect_level !== 'read') {
    badges.add(humanizeToken(capability.side_effect_level))
  }
  for (const effect of capability.business_effects?.produces ?? []) {
    badges.add(effectLabel(effect))
  }
  for (const effect of capability.business_effects?.does_not_produce ?? []) {
    badges.add(deniedEffectLabel(effect))
  }
  if (capability.grant_policy) badges.add('Needs approval')
  if (capability.composition) badges.add('Composed capability')
  return Array.from(badges)
}

function capabilityChip(capability: DeveloperCapabilityFormalization): string {
  return humanizeToken(capability.title || capability.capability_id)
}

function capabilityChoice(capability: DeveloperCapabilityFormalization) {
  return {
    label: capabilityChip(capability),
    path: capabilityPath(capability.capability_id),
  }
}

function authorityItemsForService(serviceId: string, capabilities: DeveloperCapabilityFormalization[]) {
  const definition = developerDefinition.value
  const items: Array<{ label: string; path: string }> = []
  const scopedCapabilityCount = capabilities.filter((capability) => (capability.minimum_scope ?? []).length > 0).length
  const approvalCapabilityCount = capabilities.filter((capability) => capability.grant_policy).length
  const actorBindingCount = definition?.permission_intent_bindings.filter((binding) =>
    binding.target_service_ids.includes(serviceId),
  ).length ?? 0
  const auditSignals = definition?.audit
  const audited = Boolean(
    auditSignals?.durable_records_required
    || auditSignals?.invocation_tracking
    || auditSignals?.task_tracking
    || auditSignals?.parent_invocation_tracking,
  )
  const authoritySignals = definition?.authority

  if (authoritySignals?.delegation_tokens || authoritySignals?.scoped_authority || scopedCapabilityCount > 0) {
    items.push({
      label: scopedCapabilityCount > 0 ? `Token scopes (${scopedCapabilityCount})` : 'Token scopes',
      path: governancePath(),
    })
  }
  if (approvalCapabilityCount > 0 || authoritySignals?.approval_expectation === 'required') {
    items.push({
      label: approvalCapabilityCount > 0 ? `Needs approval (${approvalCapabilityCount})` : 'Needs approval',
      path: capabilityBehaviorPath(serviceId),
    })
  }
  if (actorBindingCount > 0) {
    items.push({
      label: `Actor constrained (${actorBindingCount})`,
      path: permissionIntentPath(),
    })
  } else if ((definition?.actor_expectations.length ?? 0) > 0) {
    items.push({
      label: 'Actor model',
      path: actorModelPath(),
    })
  }
  if (audited) {
    items.push({
      label: 'Audited',
      path: verificationPath(),
    })
  }
  if (authoritySignals?.purpose_binding) {
    items.push({
      label: 'Purpose-bound',
      path: governancePath(),
    })
  }
  if (authoritySignals?.restricted_vs_denied) {
    items.push({
      label: 'Restricted vs denied',
      path: governancePath(),
    })
  }

  return Array.from(new Map(items.map((item) => [item.label, item])).values())
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function stringField(record: Record<string, unknown>, key: string): string {
  return typeof record[key] === 'string' ? record[key].trim() : ''
}

function appGlueCategoryLabel(value: string | undefined): string {
  if (!value) return 'App-owned behavior'
  const labels: Record<string, string> = {
    app_glue: 'App glue',
    derived_target: 'Target selection',
    output_semantics: 'Result rendering',
    unsupported_effect: 'Boundary handling',
    approval_boundary: 'Approval framing',
    clarification_behavior: 'Clarification',
    declared_defaults: 'Defaults',
    composition_candidate: 'Composition review',
  }
  return labels[value] ?? humanizeToken(value)
}

function consumingAppLabel(): string {
  const systemName = developerDefinition.value?.identity.system_name?.trim()
  if (systemName) return `${systemName} app`
  const projectName = project.value?.name?.trim()
  if (projectName) return `${projectName} app`
  return 'Consuming app'
}

function appGlueDetail(detail: string): string {
  const prefix = `${consumingAppLabel()}-specific logic.`
  return detail ? `${prefix} ${detail}` : `${prefix} This behavior is outside the ANIP-native service contract.`
}

const capabilityById = computed(() => {
  const entries = new Map<string, DeveloperCapabilityFormalization>()
  for (const capability of developerDefinition.value?.capability_formalizations ?? []) {
    entries.set(capability.capability_id, capability)
  }
  return entries
})

function pushAppGlueItem(target: Map<string, AppGlueDiagramItem>, item: AppGlueDiagramItem) {
  const key = item.id || `${item.capability_id ?? 'project'}:${item.category ?? item.title}`
  if (target.has(key)) return
  target.set(key, item)
}

const appGlueItems = computed<AppGlueDiagramItem[]>(() => {
  const items = new Map<string, AppGlueDiagramItem>()
  const readiness = traceability.value?.agent_consumption_readiness
  const reviews = readiness?.finding_reviews ?? {}

  for (const raw of readiness?.required_app_glue ?? []) {
    const record = asRecord(raw)
    const title = stringField(record, 'title')
    const id = stringField(record, 'id') || title
    pushAppGlueItem(items, {
      id: id || `required-glue-${items.size + 1}`,
      title: title || appGlueCategoryLabel(stringField(record, 'category')),
      detail: stringField(record, 'detail') || stringField(record, 'recommendation') || 'Consuming app behavior is required and should be reviewed explicitly.',
      recommendation: stringField(record, 'recommendation'),
      capability_id: stringField(record, 'capability_id') || undefined,
      category: stringField(record, 'category') || undefined,
      reviewed: true,
    })
  }

  for (const raw of readiness?.findings ?? []) {
    const record = asRecord(raw)
    const id = stringField(record, 'id')
    const review = id ? reviews[id] : undefined
    if (review?.decision !== 'explicit_app_glue') continue
    pushAppGlueItem(items, {
      id: id || `reviewed-glue-${items.size + 1}`,
      title: stringField(record, 'title') || appGlueCategoryLabel(stringField(record, 'category')),
      detail: review.note || stringField(record, 'detail') || stringField(record, 'recommendation') || 'Reviewed as explicit consuming-app glue.',
      recommendation: stringField(record, 'recommendation'),
      capability_id: stringField(record, 'capability_id') || undefined,
      category: stringField(record, 'category') || undefined,
      reviewed: review.review_method !== 'automation_harness',
    })
  }

  for (const review of Object.values(traceability.value?.agent_consumability_reviews ?? {})) {
    if (!review.app_glue_required && !review.app_glue_reason?.trim()) continue
    const capability = capabilityById.value.get(review.capability_id)
    pushAppGlueItem(items, {
      id: `consumability-${review.capability_id}`,
      title: capability ? `${capabilityChip(capability)} app boundary` : `${humanizeToken(review.capability_id)} app boundary`,
      detail: review.app_glue_reason?.trim() || 'Reviewed agent-consumability metadata says the consuming app owns part of this behavior.',
      capability_id: review.capability_id,
      category: 'app_glue',
      reviewed: true,
    })
  }

  for (const capability of developerDefinition.value?.capability_formalizations ?? []) {
    if (capability.implementation_fit?.category !== 'agent_app_glue') continue
    pushAppGlueItem(items, {
      id: `implementation-fit-${capability.capability_id}`,
      title: `${capabilityChip(capability)} app glue`,
      detail: capability.implementation_fit.rationale || 'Implementation fit marks this capability as requiring consuming-app glue.',
      capability_id: capability.capability_id,
      category: 'app_glue',
      reviewed: false,
    })
  }

  return Array.from(items.values()).sort((left, right) =>
    appGlueCategoryLabel(left.category).localeCompare(appGlueCategoryLabel(right.category))
    || left.title.localeCompare(right.title),
  )
})

const appGlueItemsByService = computed(() => {
  const entries = new Map<string, AppGlueDiagramItem[]>()
  for (const item of appGlueItems.value) {
    const serviceId = item.capability_id ? capabilityById.value.get(item.capability_id)?.service_id : undefined
    if (!serviceId) continue
    const list = entries.get(serviceId) ?? []
    list.push(item)
    entries.set(serviceId, list)
  }
  return entries
})

const groupedAppGlueItems = computed<AppGlueDiagramItem[]>(() => {
  const grouped = new Map<string, AppGlueDiagramItem>()
  for (const item of appGlueItems.value) {
    const key = item.capability_id
      ? `capability:${item.capability_id}`
      : `category:${item.category ?? 'app_glue'}:${item.title.toLowerCase()}`
    const existing = grouped.get(key)
    if (!existing) {
      grouped.set(key, {
        ...item,
        id: `group-${diagramId(key)}`,
        count: item.count ?? 1,
      })
      continue
    }
    grouped.set(key, {
      ...existing,
      reviewed: existing.reviewed && item.reviewed,
      count: (existing.count ?? 1) + (item.count ?? 1),
    })
  }
  return Array.from(grouped.values()).sort((left, right) =>
    appGlueCategoryLabel(left.category).localeCompare(appGlueCategoryLabel(right.category))
    || left.title.localeCompare(right.title),
  )
})

const visibleAppGlueItems = computed(() => {
  const maxVisible = 5
  if (groupedAppGlueItems.value.length <= maxVisible) return groupedAppGlueItems.value
  const visible = groupedAppGlueItems.value.slice(0, maxVisible)
  visible.push({
    id: 'app-glue-more',
    title: `+${groupedAppGlueItems.value.length - maxVisible} more app-glue areas`,
    detail: 'Open Agent & App Glue to review the remaining app-owned decisions.',
    category: 'app_glue',
    reviewed: false,
    count: appGlueItems.value.length - visible.reduce((total, item) => total + (item.count ?? 1), 0),
  })
  return visible
})

function diagramItemLabel(item: string | { label: string }): string {
  return typeof item === 'string' ? item : item.label
}

function diagramId(value: string): string {
  return value.replace(/[^a-zA-Z0-9_-]+/g, '-').replace(/^-+|-+$/g, '') || 'item'
}

function detailGroupHeight(items: Array<string | { label: string }>, visibleLimit: number): number {
  if (items.length <= 0) return 43
  const visibleItems = items.slice(0, visibleLimit)
  const rowUnits = visibleItems.reduce((total, item) => {
    const label = diagramItemLabel(item)
    return total + (label.length > 22 ? 2 : 1)
  }, 0)
  const rows = Math.max(1, Math.ceil(rowUnits / 2))
  return 48 + rows * 32
}

const capabilitiesByService = computed(() => {
  const entries = new Map<string, DeveloperCapabilityFormalization[]>()
  for (const capability of developerDefinition.value?.capability_formalizations ?? []) {
    const list = entries.get(capability.service_id) ?? []
    list.push(capability)
    entries.set(capability.service_id, list)
  }
  return entries
})

function serviceStatus(binding: DeveloperServiceTopologyBinding): StudioDiagramStatus {
  if (!binding.formalized_capability_ids.length && !binding.source_capabilities.length) return 'needs_clarification'
  return 'ready'
}

function backendSummary(binding: DeveloperServiceBackendBinding | undefined): string[] {
  if (!binding) return ['No backend binding recorded']
  const items: string[] = []
  if (binding.uses_data_access_backend) {
    items.push(`Data: ${binding.data_access_target_label || binding.data_access_backend_type || 'configured'}`)
  }
  if (binding.uses_application_integration_backend) {
    items.push(`App: ${binding.application_integration_system_name || binding.application_integration_backend_type || 'configured'}`)
  }
  return items.length ? items : ['No backend required']
}

function isNativeImplementationBackend(binding: DeveloperServiceBackendBinding): boolean {
  if (!binding.uses_application_integration_backend) return false
  const backendType = binding.application_integration_backend_type.trim().toLowerCase()
  const systemName = binding.application_integration_system_name.trim().toLowerCase()
  const adapterTarget = binding.application_integration_adapter_target.trim().toLowerCase()
  const serviceName = binding.service_name.trim().toLowerCase()
  const nativeTransport = backendType === 'rest_api' || backendType === 'internal_http_service'
  const genericSystemName = !systemName
    || systemName.includes('showcase')
    || systemName.includes('generated')
    || systemName.includes(serviceName)
  const genericAdapter = !adapterTarget
    || adapterTarget.includes('adapter')
    || adapterTarget.includes('template')
    || adapterTarget.includes(binding.service_id.toLowerCase())
  return nativeTransport && genericSystemName && genericAdapter
}

function backendDependencyNodes(
  binding: DeveloperServiceTopologyBinding,
  backendBinding: DeveloperServiceBackendBinding | undefined,
  x: number,
  y: number,
  mediumY: number,
  expandedY: number,
): StudioDiagramNode[] {
  if (!backendBinding) {
    return [{
      id: `backend-none-${binding.service_id}`,
      title: 'No backend required',
      subtitle: 'Dependency',
      detail: 'No data source or application integration dependency is recorded for this service.',
      status: 'draftable',
      path: servicePath(binding.service_id),
      x,
      y,
      mediumY,
      expandedY,
      width: 320,
      height: 124,
      compactHeight: 138,
      mediumHeight: 148,
      expandedHeight: 166,
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      meta: ['Review service binding'],
    }]
  }

  const nodes: StudioDiagramNode[] = []
  if (backendBinding.uses_data_access_backend) {
    nodes.push({
      id: `backend-data-${binding.service_id}`,
      title: backendBinding.data_access_target_label || backendBinding.data_access_backend_type || 'Data source',
      subtitle: 'Data source',
      detail: 'Read/query dependency used by this ANIP service boundary.',
      status: 'ready',
      path: servicePath(binding.service_id),
      x,
      y,
      mediumY,
      expandedY,
      width: 320,
      height: 132,
      compactHeight: 148,
      mediumHeight: 154,
      expandedHeight: 172,
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      meta: [backendBinding.data_access_backend_type || 'Data access'],
    })
  }
  if (backendBinding.uses_application_integration_backend) {
    const nativeImplementation = isNativeImplementationBackend(backendBinding)
    nodes.push({
      id: `backend-app-${binding.service_id}`,
      title: nativeImplementation
        ? `${binding.service_name || humanizeToken(binding.service_id)} implementation`
        : backendBinding.application_integration_system_name || backendBinding.application_integration_backend_type || 'Application integration',
      subtitle: nativeImplementation ? 'Native implementation' : 'Application integration',
      detail: nativeImplementation
        ? 'Generated or custom service code behind this ANIP boundary; not a separate external system.'
        : 'External application/API dependency or adapter target used behind this ANIP service boundary.',
      status: 'ready',
      path: servicePath(binding.service_id),
      x,
      y: nodes.length ? y + 172 : y,
      mediumY: nodes.length ? mediumY + 178 : mediumY,
      expandedY: nodes.length ? expandedY + 196 : expandedY,
      width: 320,
      height: 140,
      compactHeight: 158,
      mediumHeight: 168,
      expandedHeight: 188,
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      meta: [
        nativeImplementation
          ? 'Native ANIP runtime'
          : backendBinding.application_integration_backend_type || 'Integration',
        backendBinding.application_integration_environment || 'Environment not recorded',
      ],
    })
  }

  return nodes.length
    ? nodes
    : [{
      id: `backend-none-${binding.service_id}`,
      title: 'No backend required',
      subtitle: 'Dependency',
      detail: 'This service is currently modeled without a data source or application integration dependency.',
      status: 'ready',
      path: servicePath(binding.service_id),
      x,
      y,
      mediumY,
      expandedY,
      width: 320,
      height: 124,
      compactHeight: 138,
      mediumHeight: 148,
      expandedHeight: 166,
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      meta: ['Self-contained service'],
    }]
}

const serviceBindings = computed(() => developerDefinition.value?.service_topology_bindings ?? [])
const backendBindingsByService = computed(() => {
  const entries = new Map<string, DeveloperServiceBackendBinding>()
  for (const binding of developerDefinition.value?.service_backend_bindings ?? []) {
    entries.set(binding.service_id, binding)
  }
  return entries
})

const architectureNodes = computed<StudioDiagramNode[]>(() => {
  const serviceCount = Math.max(1, serviceBindings.value.length)
  const serviceSpacing = 350
  const serviceWidth = 300
  const agentY = 0
  const serviceY = 250
  const serviceToDependencyGap = 84
  const serviceRowWidth = (serviceCount - 1) * serviceSpacing + serviceWidth
  const diagramRowWidth = Math.max(serviceRowWidth, 300)
  const serviceOffsetX = (diagramRowWidth - serviceRowWidth) / 2
  const centerX = Math.max(0, diagramRowWidth / 2 - 150)
  const dependencyNodes: StudioDiagramNode[] = []
  const serviceNodes = serviceBindings.value.map((binding, index) => {
    const serviceX = serviceOffsetX + index * serviceSpacing
    const backendBinding = backendBindingsByService.value.get(binding.service_id)
    const capabilities = capabilitiesByService.value.get(binding.service_id) ?? []
    const capabilityCount = binding.formalized_capability_ids.length || binding.source_capabilities.length || capabilities.length
    const capabilityChips = capabilities.length
      ? Array.from(new Map(capabilities.map((capability) => [
        capabilityChip(capability),
        {
          label: capabilityChip(capability),
          path: capabilityPath(capability.capability_id),
        },
      ])).values())
      : binding.source_capabilities.map(humanizeToken)
    const hiddenCapabilityCount = Math.max(0, capabilityChips.length - 6)
    const behaviorBadges = Array.from(new Set(capabilities.flatMap(capabilityBehaviorBadges)))
    const behaviorItems = behaviorBadges.map((badge) => {
      const matchingCapabilities = capabilities.filter((capability) => capabilityBehaviorBadges(capability).includes(badge))
      return {
        label: badge,
        path: matchingCapabilities.length === 1 ? capabilityPath(matchingCapabilities[0].capability_id) : undefined,
        choices: matchingCapabilities.length > 1 ? matchingCapabilities.map(capabilityChoice) : undefined,
      }
    })
    const authorityItems = authorityItemsForService(binding.service_id, capabilities)
    const expandedCapabilityItems = hiddenCapabilityCount
      ? [...capabilityChips.slice(0, 6), `+${hiddenCapabilityCount} more`]
      : capabilityChips
    const mediumGroupsHeight = detailGroupHeight(capabilityChips, 4)
      + detailGroupHeight(behaviorItems, 4)
      + detailGroupHeight(authorityItems, 4)
    const expandedGroupsHeight = detailGroupHeight(expandedCapabilityItems, 8)
      + detailGroupHeight(behaviorItems, 8)
      + detailGroupHeight(authorityItems, 8)
    const serviceCompactHeight = 262
    const serviceMediumHeight = Math.max(470, 205 + mediumGroupsHeight)
    const serviceExpandedHeight = Math.max(660, 235 + expandedGroupsHeight)
    const dependencyY = serviceY + serviceCompactHeight + 78
    const dependencyMediumY = serviceY + serviceMediumHeight + serviceToDependencyGap
    const dependencyExpandedY = serviceY + serviceExpandedHeight + serviceToDependencyGap
    dependencyNodes.push(...backendDependencyNodes(binding, backendBinding, serviceX, dependencyY, dependencyMediumY, dependencyExpandedY))
    return {
      id: `service-${binding.service_id}`,
      title: binding.service_name || binding.service_id,
      subtitle: 'Service / component',
      detail: binding.implementation_notes || binding.source_role || 'Service boundary formalized from the locked product baseline.',
      status: serviceStatus(binding),
      path: servicePath(binding.service_id),
      x: serviceX,
      y: serviceY,
      width: 320,
      height: 250,
      compactHeight: serviceCompactHeight,
      mediumHeight: serviceMediumHeight,
      expandedHeight: serviceExpandedHeight,
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      meta: [
        `${capabilityCount} capabilities`,
        ...backendSummary(backendBinding),
      ],
      detailGroups: [
        {
          title: 'Capabilities',
          count: capabilityCount,
          path: capabilityServicePath(binding.service_id),
          items: hiddenCapabilityCount
            ? [...capabilityChips.slice(0, 6), `+${hiddenCapabilityCount} more`]
            : capabilityChips,
          tone: 'capability',
        },
        {
          title: 'Governed behavior',
          count: behaviorBadges.length,
          path: capabilityBehaviorPath(binding.service_id),
          items: behaviorItems,
          tone: 'behavior',
        },
        {
          title: 'Trust & authority',
          count: authorityItems.length,
          path: governancePath(),
          items: authorityItems,
          tone: 'authority',
        },
      ],
    } satisfies StudioDiagramNode
  })
  return [
    {
      id: 'agent-request',
      title: 'Agent Request',
      subtitle: 'Entry',
      detail: baselineArtifact.value ? 'Agent requests enter the solution and route to the service that owns the requested capability.' : 'Lock Product Design before treating routing as authoritative.',
      status: baselineArtifact.value ? 'ready' : 'blocked',
      path: appGluePath(),
      x: centerX,
      y: agentY,
      width: 300,
      height: 176,
      compactHeight: 190,
      mediumHeight: 210,
      expandedHeight: 230,
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      meta: [
        'Capability discovery',
        'Token issuance',
        'ANIP invoke',
        requirements.value[0]?.title ?? 'No requirements',
      ],
      detailGroups: [
        {
          title: 'Request handling',
          count: 3,
          items: ['Discovery', 'Authorize', 'Invoke'],
          tone: 'neutral',
        },
      ],
    },
    ...serviceNodes,
    ...dependencyNodes,
  ]
})

const architectureEdges = computed<StudioDiagramEdge[]>(() => {
  const requestEdges = serviceBindings.value
    .map((binding) => ({
      id: `baseline-${binding.service_id}`,
      source: 'agent-request',
      target: `service-${binding.service_id}`,
      label: 'agent request',
      status: serviceStatus(binding),
    } satisfies StudioDiagramEdge))
  const dependencyEdges = serviceBindings.value.flatMap((binding) => {
    const backendBinding = backendBindingsByService.value.get(binding.service_id)
    const targets: string[] = []
    if (!backendBinding) {
      targets.push(`backend-none-${binding.service_id}`)
    } else {
      if (backendBinding.uses_data_access_backend) targets.push(`backend-data-${binding.service_id}`)
      if (backendBinding.uses_application_integration_backend) targets.push(`backend-app-${binding.service_id}`)
      if (!targets.length) targets.push(`backend-none-${binding.service_id}`)
    }
    const nativeRuntime = backendBinding ? isNativeImplementationBackend(backendBinding) : false
    return targets.map((target) => ({
      id: `dependency-${binding.service_id}-${target}`,
      source: `service-${binding.service_id}`,
      target,
      label: target.startsWith('backend-app-') && nativeRuntime ? 'runtime' : 'backend',
      status: serviceStatus(binding),
    } satisfies StudioDiagramEdge))
  })
  return [...requestEdges, ...dependencyEdges]
})

const showAppGlueDiagram = computed(() => visibleAppGlueItems.value.length > 0)

const appGlueDiagramNodes = computed<StudioDiagramNode[]>(() => {
  const glueCount = visibleAppGlueItems.value.length
  const glueSpacing = 370
  const glueWidth = 330
  const serviceSpacing = 380
  const glueY = 0
  const agentY = 330
  const serviceY = 660
  const appGlueRowWidth = glueCount ? (glueCount - 1) * glueSpacing + glueWidth : 0
  const serviceCount = Math.max(1, serviceBindings.value.length)
  const serviceRowWidth = (serviceCount - 1) * serviceSpacing + 340
  const diagramRowWidth = Math.max(appGlueRowWidth, serviceRowWidth, 340)
  const centerX = Math.max(0, diagramRowWidth / 2 - 160)
  const glueOffsetX = appGlueRowWidth ? (diagramRowWidth - appGlueRowWidth) / 2 : 0
  const serviceOffsetX = (diagramRowWidth - serviceRowWidth) / 2
  const serviceIdsWithGlue = new Set(appGlueItemsByService.value.keys())
  const relatedServiceBindings = serviceBindings.value.filter((binding) => serviceIdsWithGlue.has(binding.service_id))
  const serviceNodes = relatedServiceBindings.map((binding, index) => {
    const capabilities = capabilitiesByService.value.get(binding.service_id) ?? []
    const glueCountForService = appGlueItemsByService.value.get(binding.service_id)?.length ?? 0
    return {
      id: `glue-service-${binding.service_id}`,
      title: binding.service_name || binding.service_id,
      subtitle: 'Affected ANIP service',
      detail: binding.implementation_notes || binding.source_role || 'Service reached by the agent after app-specific glue has resolved the consuming-app concern.',
      status: serviceStatus(binding),
      path: servicePath(binding.service_id),
      x: serviceOffsetX + index * serviceSpacing,
      y: serviceY,
      width: 340,
      height: 236,
      compactHeight: 236,
      mediumHeight: 292,
      expandedHeight: 342,
      compactDetailLines: 3,
      mediumDetailLines: 4,
      expandedDetailLines: 6,
      compactMetaLimit: 2,
      mediumMetaLimit: 3,
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      meta: [
        `${capabilities.length || binding.formalized_capability_ids.length || binding.source_capabilities.length} capabilities`,
        `${glueCountForService} app-glue references`,
      ],
      detailGroups: [
        {
          title: 'Glue references',
          count: glueCountForService,
          path: appGluePath(),
          items: (appGlueItemsByService.value.get(binding.service_id) ?? [])
            .slice(0, 6)
            .map((item) => item.title),
          tone: 'glue',
        },
      ],
    } satisfies StudioDiagramNode
  })

  return [
    ...visibleAppGlueItems.value.map((item, index) => {
      const capability = item.capability_id ? capabilityById.value.get(item.capability_id) : undefined
      return {
        id: `glue-${diagramId(item.id)}`,
        title: item.title,
        subtitle: 'Consuming app glue',
        detail: appGlueDetail(item.detail),
        status: item.reviewed ? 'ready' : 'needs_clarification',
        path: appGluePath(),
        x: glueOffsetX + index * glueSpacing,
        y: glueY,
        mediumY: glueY - 16,
        expandedY: glueY - 40,
        width: glueWidth,
        height: 236,
        compactHeight: 236,
        mediumHeight: 292,
        expandedHeight: 344,
        compactDetailLines: 3,
        mediumDetailLines: 4,
        expandedDetailLines: 6,
        compactMetaLimit: 2,
        mediumMetaLimit: 3,
        sourcePosition: Position.Bottom,
        targetPosition: Position.Top,
        meta: [
          appGlueCategoryLabel(item.category),
          `${consumingAppLabel()} specific`,
          item.count && item.count > 1 ? `${item.count} findings` : '',
          item.reviewed ? 'Reviewed boundary' : 'Needs review',
        ].filter(Boolean),
        detailGroups: [
          {
            title: 'App owns',
            count: capability ? 1 : undefined,
            path: appGluePath(),
            items: capability
              ? [{ label: capabilityChip(capability), path: capabilityPath(capability.capability_id) }]
              : ['Project-level consuming app decision'],
            tone: 'glue',
          },
        ],
      } satisfies StudioDiagramNode
    }),
    {
      id: 'glue-agent',
      title: consumingAppLabel(),
      subtitle: 'Agent / consuming app',
      detail: 'App-specific glue shapes the request before the agent invokes ANIP-native service capabilities.',
      status: 'ready',
      path: appGluePath(),
      x: centerX,
      y: agentY,
      width: 320,
      height: 218,
      compactHeight: 218,
      mediumHeight: 246,
      expandedHeight: 278,
      compactDetailLines: 3,
      mediumDetailLines: 4,
      expandedDetailLines: 5,
      compactMetaLimit: 2,
      mediumMetaLimit: 3,
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      meta: ['App framing', 'Capability selection', 'Result presentation'],
      detailGroups: [
        {
          title: 'Still generic ANIP',
          count: 3,
          items: ['Discover', 'Authorize', 'Invoke'],
          tone: 'neutral',
        },
      ],
    },
    ...serviceNodes,
  ]
})

const appGlueDiagramEdges = computed<StudioDiagramEdge[]>(() => {
  const glueToAgent = visibleAppGlueItems.value.map((item) => ({
    id: `glue-to-agent-${diagramId(item.id)}`,
    source: `glue-${diagramId(item.id)}`,
    target: 'glue-agent',
    status: item.reviewed ? 'ready' : 'needs_clarification',
    type: 'smoothstep',
  } satisfies StudioDiagramEdge))
  const agentToServices = visibleAppGlueItems.value.flatMap((item) => {
    const serviceId = item.capability_id ? capabilityById.value.get(item.capability_id)?.service_id : undefined
    if (!serviceId) return []
    return [{
      id: `glue-agent-to-service-${diagramId(item.id)}-${serviceId}`,
      source: 'glue-agent',
      target: `glue-service-${serviceId}`,
      status: item.reviewed ? 'ready' : 'needs_clarification',
      type: 'smoothstep',
    } satisfies StudioDiagramEdge]
  })
  return [...glueToAgent, ...agentToServices]
})

function publicationStatus(): StudioFlowDiagramStatus {
  return developerDefinition.value?.compiled_contract_identity?.signature ? 'draftable' : 'blocked'
}

const artifactFlowNodes = computed<StudioFlowDiagramNode[]>(() => [
  {
    key: 'product-baseline',
    kicker: 'Source truth',
    title: 'Product baseline',
    detail: baselineArtifact.value ? 'Locked Product Design baseline is available.' : 'Lock Product Design before implementation artifacts become authoritative.',
    status: baselineArtifact.value ? 'ready' : 'blocked',
    path: path('/developer/handoff'),
    meta: productRevision.value?.revision_number ? `Product r${productRevision.value.revision_number}` : 'No product revision',
    issues: baselineArtifact.value ? [] : ['No locked baseline'],
  },
  {
    key: 'developer-definition',
    kicker: 'Implementation truth',
    title: 'Developer definition',
    detail: developerDefinition.value ? 'Saved Developer Definition is available.' : 'Save Developer Definition before publication or generation.',
    status: developerDefinition.value ? 'ready' : 'blocked',
    path: path('/developer/definition'),
    meta: developerDefinition.value?.saved_revision?.revision_number ? `Dev r${developerDefinition.value.saved_revision.revision_number}` : 'No saved revision',
    issues: developerDefinition.value ? [] : ['No developer definition'],
  },
  {
    key: 'contract-identity',
    kicker: 'Canonical identity',
    title: 'Contract identity',
    detail: developerDefinition.value?.compiled_contract_identity?.signature ? 'Contract signature is recorded.' : 'Compile/save the contract identity before publication.',
    status: developerDefinition.value?.compiled_contract_identity?.signature ? 'ready' : 'blocked',
    path: path('/developer/definition'),
    meta: developerDefinition.value?.compiled_contract_identity?.signature?.slice(0, 24) ?? 'No signature',
    issues: developerDefinition.value?.compiled_contract_identity?.signature ? [] : ['No contract signature'],
  },
  {
    key: 'registry-package',
    kicker: 'Portable artifact',
    title: 'Package / Registry',
    detail: 'Publication makes the contract portable and externally verifiable.',
    status: publicationStatus(),
    path: path('/verification'),
    meta: developerDefinition.value?.compiled_contract_identity?.signature ? 'Ready to publish' : 'Missing contract identity',
    issues: developerDefinition.value?.compiled_contract_identity?.signature ? [] : ['No compiled contract identity'],
  },
  {
    key: 'generator',
    kicker: 'Code output',
    title: 'Generator',
    detail: 'Generator produces target service code from the saved package/contract identity.',
    status: developerDefinition.value ? 'draftable' : 'blocked',
    path: path('/developer/definition#generation-launch'),
    meta: developerDefinition.value?.saved_at ? formatStudioTimestamp(developerDefinition.value.saved_at) : 'Not generated',
  },
  {
    key: 'verifier',
    kicker: 'Evidence',
    title: 'Verifier',
    detail: 'Verifier evidence proves generated/runtime artifacts still match the contract.',
    status: 'blocked',
    path: path('/verification'),
    meta: 'No verifier evidence',
    issues: ['Run verification after generation'],
  },
])

function open(path: string) {
  router.push(path)
}

const diagramTabs = computed<Array<{ key: DeveloperDiagramTab; label: string; summary: string }>>(() => {
  const tabs: Array<{ key: DeveloperDiagramTab; label: string; summary: string }> = [
    {
      key: 'architecture',
      label: 'Solution Architecture',
      summary: 'Agent request routing and service ownership.',
    },
  ]
  if (showAppGlueDiagram.value) {
    tabs.push({
      key: 'glue',
      label: 'App Glue',
      summary: 'Consuming-app-specific logic separated from ANIP-native architecture.',
    })
  }
  tabs.push({
    key: 'artifacts',
    label: 'Artifact Flow',
    summary: 'Contract identity, publication, generation, and verification.',
  })
  return tabs
})

watch(showAppGlueDiagram, (enabled) => {
  if (!project.value || projectStore.loading) return
  if (!enabled && activeDiagramTab.value === 'glue') {
    setDiagramTab('architecture')
  }
}, { immediate: true })

watch(activeDiagramTab, () => {
  diagramFitVersion.value += 1
})
</script>

<template>
  <div class="diagram-page">
    <div v-if="projectStore.loading && !project" class="empty-state">Loading developer diagrams...</div>
    <template v-else-if="project">
      <section class="page-header">
        <button class="back-link" type="button" @click="open(`/design/projects/${project.id}/developer`)">
          ← Developer Overview
        </button>
        <div class="page-kicker">Developer Design Diagrams</div>
        <h1>{{ project.name }}</h1>
        <p>
          Developer diagrams separate the solution architecture from the behavioral delivery flow. Use them to see service ownership, capability boundaries, governance streams, generation, and verification without reading every form field first.
        </p>
      </section>

      <section class="diagram-tabs" aria-label="Developer diagram tabs">
        <button
          v-for="tab in diagramTabs"
          :key="tab.key"
          type="button"
          class="diagram-tab"
          :class="{ active: activeDiagramTab === tab.key }"
          @click="setDiagramTab(tab.key)"
        >
          <span>{{ tab.label }}</span>
          <small>{{ tab.summary }}</small>
        </button>
      </section>

      <section class="diagram-stack">
        <article v-if="activeDiagramTab === 'architecture'" class="panel panel-full">
          <StudioNodeDiagram
            headline="Solution Architecture"
            summary="Agent requests route into ANIP-native services/components. App-specific glue is intentionally kept out of this architecture view and shown separately."
            :nodes="architectureNodes"
            :edges="architectureEdges"
            :height="720"
            :fit-version="diagramFitVersion"
            @navigate="open"
          />
        </article>

        <article v-else-if="activeDiagramTab === 'glue'" class="panel panel-full">
          <StudioNodeDiagram
            headline="App Glue Boundary"
            summary="Consuming-app-specific logic that shapes requests before the agent invokes ANIP-native services. This is separated from the solution architecture so app glue does not look like service coupling."
            :nodes="appGlueDiagramNodes"
            :edges="appGlueDiagramEdges"
            :height="720"
            :fit-version="diagramFitVersion"
            @navigate="open"
          />
        </article>

        <article v-else class="panel panel-full">
          <StudioFlowDiagram
            headline="Technical Artifact Flow"
            summary="Where the saved design goes next: locked Product Design, Developer Definition, contract identity, package publication, generator output, and verifier evidence."
            :nodes="artifactFlowNodes"
            @navigate="open"
          />
        </article>
      </section>
    </template>
  </div>
</template>

<style scoped>
.diagram-page {
  width: 100%;
  max-width: none;
  padding: 2rem;
}

.page-header {
  margin-bottom: 1.75rem;
}

.page-header h1 {
  margin: 0.25rem 0 0;
  color: var(--text-primary);
}

.page-header p {
  max-width: 980px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.page-kicker {
  color: var(--accent);
  font-size: 0.78rem;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.back-link {
  margin-bottom: 1rem;
  border: 0;
  background: transparent;
  color: var(--accent);
  font-weight: 800;
  cursor: pointer;
}

.diagram-tabs {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.8rem;
  margin-bottom: 1rem;
}

.diagram-tab {
  display: grid;
  gap: 0.28rem;
  border: 1px solid var(--surface-border-card);
  border-radius: 18px;
  padding: 0.9rem 1rem;
  background:
    radial-gradient(circle at top left, rgba(14, 165, 233, 0.08), transparent 38%),
    rgba(15, 23, 42, 0.58);
  color: var(--text-secondary);
  text-align: left;
  cursor: pointer;
  transition: border-color 0.16s ease, background 0.16s ease, transform 0.16s ease;
}

.diagram-tab:hover,
.diagram-tab.active {
  transform: translateY(-1px);
  border-color: rgba(125, 211, 252, 0.54);
  background:
    radial-gradient(circle at top left, rgba(14, 165, 233, 0.18), transparent 40%),
    rgba(14, 116, 144, 0.18);
}

.diagram-tab span {
  color: var(--text-primary);
  font-size: 0.98rem;
  font-weight: 900;
}

.diagram-tab small {
  color: var(--text-secondary);
  font-size: 0.78rem;
  line-height: 1.4;
}

.diagram-stack {
  display: grid;
  gap: 1rem;
}

.panel {
  border: 1px solid var(--border);
  border-radius: 22px;
  padding: 1.25rem;
  background: rgba(15, 23, 42, 0.72);
  box-shadow: var(--shadow);
}

@media (max-width: 980px) {
  .diagram-tabs {
    grid-template-columns: 1fr;
  }
}
</style>
