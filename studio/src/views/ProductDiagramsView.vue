<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Position } from '@vue-flow/core'
import StudioNodeDiagram, {
  type StudioDiagramEdge,
  type StudioDiagramGroupItem,
  type StudioDiagramNode,
  type StudioDiagramStatus,
} from '../design/components/StudioNodeDiagram.vue'
import {
  findDeveloperDefinitionArtifact,
} from '../design/developer-definition'
import {
  ACTOR_MODEL_ARTIFACT_TYPE,
  BUSINESS_AREAS_ARTIFACT_TYPE,
  PERMISSION_INTENT_ARTIFACT_TYPE,
  PRODUCT_SUMMARY_ARTIFACT_TYPE,
  buildProductDesignSufficiencyCards,
  findActorModelArtifact,
  findBusinessAreasArtifact,
  findNonGoalsArtifact,
  findPermissionIntentArtifact,
  findProductSummaryArtifact,
  findSuccessCriteriaArtifact,
  type ActorModelData,
  type ActorModelEntry,
  type BusinessAreaEntry,
  type BusinessAreasData,
  type NonGoalEntry,
  type NonGoalsData,
  type PermissionIntentData,
  type PermissionIntentRule,
  type ProductSummaryData,
  type SuccessCriteriaData,
  type SuccessCriteriaEntry,
} from '../design/product-design'
import { loadProject, projectStore } from '../design/project-store'
import type {
  ArtifactRecord,
  DesignSectionSufficiencyCard,
  DeveloperBaselineData,
  DeveloperDefinitionData,
} from '../design/project-types'
import { findDeveloperBaselineArtifact } from '../design/traceability'

const route = useRoute()
const router = useRouter()

const projectId = computed(() => route.params.projectId as string)
const project = computed(() => projectStore.activeProject)
const documents = computed(() => projectStore.artifacts.documents)
const requirements = computed(() => projectStore.artifacts.requirements)
const scenarios = computed(() => projectStore.artifacts.scenarios)
const shapes = computed(() => projectStore.artifacts.shapes)
type ProductDiagramTab = 'capabilities' | 'actors' | 'outcomes' | 'scenarios' | 'handoff' | 'components'
const activeDiagramTab = ref<ProductDiagramTab>('capabilities')
const diagramFitVersion = ref(0)
const isGovernedFrontingProject = computed(() => project.value?.project_type === 'governed_service_project')
const governedFrontingProductArtifactKeys = new Set([
  PRODUCT_SUMMARY_ARTIFACT_TYPE,
  ACTOR_MODEL_ARTIFACT_TYPE,
  BUSINESS_AREAS_ARTIFACT_TYPE,
  PERMISSION_INTENT_ARTIFACT_TYPE,
])

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
    if (value === 'components' || value === 'capabilities' || value === 'actors' || value === 'outcomes' || value === 'scenarios' || value === 'handoff') {
      activeDiagramTab.value = value
    }
  },
  { immediate: true },
)

const sufficiencyCards = computed<DesignSectionSufficiencyCard[]>(() =>
  project.value
    ? buildProductDesignSufficiencyCards(project.value.id, projectStore.artifacts.pmArtifacts, {
        documents_count: documents.value.length,
        requirements_count: requirements.value.length,
        scenarios_count: scenarios.value.length,
      }).filter((card) => !isGovernedFrontingProject.value || governedFrontingProductArtifactKeys.has(card.key))
    : [],
)

function cardStatus(key: string, fallback: StudioDiagramStatus): StudioDiagramStatus {
  return (sufficiencyCards.value.find((card) => card.key === key)?.status ?? fallback) as StudioDiagramStatus
}

function cardDetail(key: string, fallback: string): string {
  return sufficiencyCards.value.find((card) => card.key === key)?.detail ?? fallback
}

function path(suffix: string): string {
  return `/design/projects/${projectId.value}${suffix}`
}

function setDiagramTab(tab: ProductDiagramTab) {
  diagramFitVersion.value += 1
  activeDiagramTab.value = tab
  const query = { ...route.query }
  if (tab === 'capabilities') {
    delete query.diagram
  } else {
    query.diagram = tab
  }
  void router.replace({ path: route.path, query })
}

watch(activeDiagramTab, () => {
  diagramFitVersion.value += 1
})

function cleanText(value: unknown): string {
  return String(value ?? '').replace(/\s+/g, ' ').trim()
}

function shortText(value: string, max = 170): string {
  const cleaned = cleanText(value)
  if (cleaned.length <= max) return cleaned
  return `${cleaned.slice(0, max - 1).trim()}…`
}

function humanizeToken(value: string): string {
  return cleanText(value)
    .replace(/[._-]+/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function textTokens(...parts: string[]): Set<string> {
  return new Set(
    parts
      .join(' ')
      .toLowerCase()
      .split(/[^a-z0-9]+/)
      .map((item) => item.trim())
      .filter((item) => item.length > 2),
  )
}

const projectStopTokens = computed(() =>
  textTokens(project.value?.name ?? '', project.value?.domain ?? ''),
)

function businessTokens(...parts: string[]): Set<string> {
  const stopTokens = projectStopTokens.value
  return new Set([...textTokens(...parts)].filter((token) => !stopTokens.has(token)))
}

function tokenScore(area: BusinessAreaEntry, ...parts: string[]): number {
  const areaTokens = businessTokens(area.business_area_id, area.label, area.description)
  const targetTokens = businessTokens(...parts)
  return [...areaTokens].filter((token) => targetTokens.has(token)).length
}

function areaIdentityScore(area: BusinessAreaEntry, ...parts: string[]): number {
  const areaTokens = businessTokens(area.business_area_id, area.label)
  const targetTokens = businessTokens(...parts)
  return [...areaTokens].filter((token) => targetTokens.has(token)).length
}

function requiredAreaScore(area: BusinessAreaEntry): number {
  const areaTokens = businessTokens(area.business_area_id, area.label)
  return areaTokens.size > 1 ? 2 : 1
}

function scenarioData(record: ArtifactRecord): Record<string, any> {
  return ((record.data?.scenario ?? record.data) as Record<string, any> | undefined) ?? {}
}

function scenarioTitle(record: ArtifactRecord): string {
  const data = scenarioData(record)
  return cleanText(record.title || data.name || 'Scenario')
}

function scenarioSearchText(record: ArtifactRecord): string {
  const data = scenarioData(record)
  const context = (data.context ?? {}) as Record<string, unknown>
  return [
    record.title,
    data.name,
    data.category,
    context.capability,
  ].map(cleanText).join(' ')
}

function scenarioCapabilityText(record: ArtifactRecord): string {
  const data = scenarioData(record)
  return cleanText(data.context?.capability)
}

function scenarioExpectedBehavior(record: ArtifactRecord): string[] {
  const data = scenarioData(record)
  return Array.isArray(data.expected_behavior) ? data.expected_behavior.map(cleanText).filter(Boolean) : []
}

function scenarioExpectedSupport(record: ArtifactRecord): string[] {
  const data = scenarioData(record)
  return Array.isArray(data.expected_anip_support) ? data.expected_anip_support.map(cleanText).filter(Boolean) : []
}

function scenarioCoverageSearchText(record: ArtifactRecord): string {
  const data = scenarioData(record)
  const context = (data.context ?? {}) as Record<string, unknown>
  return [
    record.title,
    data.name,
    data.category,
    data.narrative,
    context.capability,
    ...scenarioExpectedBehavior(record),
    ...scenarioExpectedSupport(record),
  ].map(cleanText).join(' ')
}

const productSummary = computed(() =>
  (findProductSummaryArtifact(projectStore.artifacts.pmArtifacts)?.data as ProductSummaryData | undefined) ?? null,
)

const businessGoals = computed<string[]>(() =>
  (productSummary.value?.business_goals ?? []).map(cleanText).filter(Boolean),
)

const successOutcomeSummary = computed(() => cleanText(productSummary.value?.success_outcome_summary))

const actorModel = computed(() =>
  (findActorModelArtifact(projectStore.artifacts.pmArtifacts)?.data as ActorModelData | undefined) ?? null,
)

const actors = computed<ActorModelEntry[]>(() =>
  (actorModel.value?.actors ?? [])
    .map((actor) => ({
      actor_id: cleanText(actor.actor_id),
      title: cleanText(actor.title),
      summary: cleanText(actor.summary),
      visibility_expectations: cleanText(actor.visibility_expectations),
      action_expectations: cleanText(actor.action_expectations),
      approval_expectations: cleanText(actor.approval_expectations),
      notes: cleanText(actor.notes),
    }))
    .filter((actor) =>
      actor.actor_id
      || actor.title
      || actor.summary
      || actor.visibility_expectations
      || actor.action_expectations
      || actor.approval_expectations
    ),
)

const businessAreas = computed<BusinessAreaEntry[]>(() => {
  const data = findBusinessAreasArtifact(projectStore.artifacts.pmArtifacts)?.data as BusinessAreasData | undefined
  return (data?.entries ?? [])
    .map((entry) => ({
      business_area_id: cleanText(entry.business_area_id),
      label: cleanText(entry.label),
      description: cleanText(entry.description),
    }))
    .filter((entry) => entry.business_area_id || entry.label || entry.description)
})

const permissionRules = computed<PermissionIntentRule[]>(() => {
  const data = findPermissionIntentArtifact(projectStore.artifacts.pmArtifacts)?.data as PermissionIntentData | undefined
  return (data?.rules ?? []).filter((rule) =>
    cleanText(rule.actor_id)
    || cleanText(rule.business_area)
    || cleanText(rule.access_posture)
    || cleanText(rule.governed_outcome)
  )
})

const nonGoals = computed<NonGoalEntry[]>(() => {
  const data = findNonGoalsArtifact(projectStore.artifacts.pmArtifacts)?.data as NonGoalsData | undefined
  return (data?.entries ?? [])
    .map((entry) => ({
      statement: cleanText(entry.statement),
      rationale: cleanText(entry.rationale),
    }))
    .filter((entry) => entry.statement || entry.rationale)
})

const successCriteria = computed<SuccessCriteriaEntry[]>(() => {
  const data = findSuccessCriteriaArtifact(projectStore.artifacts.pmArtifacts)?.data as SuccessCriteriaData | undefined
  return (data?.entries ?? [])
    .map((entry) => ({
      statement: cleanText(entry.statement),
      evidence: cleanText(entry.evidence),
      priority: entry.priority,
      review_method: cleanText(entry.review_method),
    }))
    .filter((entry) => entry.statement || entry.evidence || entry.review_method)
})

const developerBaselineArtifact = computed(() => findDeveloperBaselineArtifact(projectStore.artifacts.pmArtifacts))
const developerBaseline = computed(() =>
  (developerBaselineArtifact.value?.data as DeveloperBaselineData | undefined) ?? null,
)

const developerDefinitionArtifact = computed(() => findDeveloperDefinitionArtifact(projectStore.artifacts.pmArtifacts))
const developerDefinition = computed(() =>
  (developerDefinitionArtifact.value?.data as DeveloperDefinitionData | undefined) ?? null,
)

const businessCapabilityIntents = computed<string[]>(() => {
  const summaryFamilies = productSummary.value?.supported_question_families
    .map(cleanText)
    .filter(Boolean) ?? []
  if (summaryFamilies.length) return summaryFamilies
  return requirements.value
    .map((record) => cleanText(record.title))
    .filter(Boolean)
})

function capabilityIntentsForArea(area: BusinessAreaEntry): string[] {
  const exact = businessCapabilityIntents.value.filter((intent) => tokenScore(area, intent) >= 1)
  if (exact.length) return exact
  return businessAreas.value.length === 1 ? businessCapabilityIntents.value : []
}

function capabilityIntentMatchesScenario(intent: string, scenario: ArtifactRecord): boolean {
  const intentTokens = textTokens(intent)
  const capabilityTokens = textTokens(scenarioCapabilityText(scenario))
  if (capabilityTokens.size) {
    const capabilityOverlap = [...intentTokens].filter((token) => capabilityTokens.has(token)).length
    if (capabilityOverlap >= Math.min(2, Math.max(1, intentTokens.size))) return true
  }

  const searchableTokens = businessTokens(scenarioSearchText(scenario))
  const intentSignalTokens = [...businessTokens(intent)].filter((token) => !['summary', 'review', 'report'].includes(token))
  if (!intentSignalTokens.length) return false
  const overlap = intentSignalTokens.filter((token) => searchableTokens.has(token)).length
  return overlap >= Math.min(2, intentSignalTokens.length)
}

function permissionRulesForArea(area: BusinessAreaEntry): PermissionIntentRule[] {
  const areaId = area.business_area_id.toLowerCase()
  return permissionRules.value.filter((rule) => {
    const businessArea = cleanText(rule.business_area).toLowerCase()
    return businessArea === areaId || areaIdentityScore(area, rule.business_area, rule.governed_outcome, rule.notes) >= requiredAreaScore(area)
  })
}

function scenariosForArea(area: BusinessAreaEntry): ArtifactRecord[] {
  const exact = scenarios.value.filter((scenario) => areaIdentityScore(area, scenarioSearchText(scenario)) >= requiredAreaScore(area))
  const areaIntentMatches = capabilityIntentsForArea(area)
  const byIntent = scenarios.value.filter((scenario) =>
    areaIntentMatches.some((intent) => capabilityIntentMatchesScenario(intent, scenario)),
  )
  const merged = [...exact]
  byIntent.forEach((scenario) => {
    if (!merged.some((candidate) => candidate.id === scenario.id)) merged.push(scenario)
  })
  if (merged.length) return merged
  return businessAreas.value.length === 1 ? scenarios.value : []
}

function scenarioCoverageForArea(area: BusinessAreaEntry): ArtifactRecord[] {
  const exact = scenarios.value.filter((scenario) => areaIdentityScore(area, scenarioSearchText(scenario)) >= requiredAreaScore(area))
  if (exact.length) return exact
  const byCapability = scenarios.value.filter((scenario) =>
    capabilityIntentsForArea(area).some((intent) => capabilityIntentMatchesScenario(intent, scenario)),
  )
  if (byCapability.length) return byCapability
  const broad = scenarios.value.filter((scenario) => areaIdentityScore(area, scenarioCoverageSearchText(scenario)) >= Math.max(requiredAreaScore(area) + 1, 3))
  if (broad.length) return broad
  return scenariosForArea(area)
}

function requirementCoverageForArea(area: BusinessAreaEntry): ArtifactRecord[] {
  const exact = requirements.value.filter((requirement) =>
    areaIdentityScore(area, requirement.title, JSON.stringify(requirement.data ?? {})) >= requiredAreaScore(area),
  )
  if (exact.length) return exact
  return businessAreas.value.length === 1 ? requirements.value : []
}

function ruleLabel(rule: PermissionIntentRule): string {
  const actor = cleanText(rule.actor_id) || 'Actor'
  const posture = humanizeToken(cleanText(rule.access_posture) || 'governed')
  const outcome = cleanText(rule.governed_outcome_type) || cleanText(rule.governed_outcome)
  return outcome ? `${actor}: ${posture} → ${humanizeToken(outcome)}` : `${actor}: ${posture}`
}

function actorTitle(actor: ActorModelEntry, index = 0): string {
  return actor.title || humanizeToken(actor.actor_id) || `Actor ${index + 1}`
}

function actorSummary(actor: ActorModelEntry): string {
  return actor.summary
    || actor.action_expectations
    || actor.visibility_expectations
    || 'A PM-defined actor whose visibility, action, approval, and boundary expectations must remain explicit.'
}

function rulesForActor(actor: ActorModelEntry): PermissionIntentRule[] {
  const actorId = actor.actor_id.toLowerCase()
  const actorTitleValue = actor.title.toLowerCase()
  return permissionRules.value.filter((rule) => {
    const ruleActor = cleanText(rule.actor_id).toLowerCase()
    if (actorId && ruleActor === actorId) return true
    return !actorId && !!actorTitleValue && ruleActor === actorTitleValue
  })
}

function decisionRuleItems(rules: PermissionIntentRule[]): StudioDiagramGroupItem[] {
  return rules.map((rule) => {
    const area = cleanText(rule.business_area) || 'Business area'
    const outcome = cleanText(rule.governed_outcome) || humanizeToken(cleanText(rule.governed_outcome_type) || cleanText(rule.access_posture))
    return {
      label: `${humanizeToken(area)}: ${humanizeToken(cleanText(rule.access_posture))}${outcome ? ` → ${outcome}` : ''}`,
      path: path('/permission-intent'),
    }
  })
}

function actorMapStatus(actor: ActorModelEntry, rules: PermissionIntentRule[]): StudioDiagramStatus {
  if (!actor.actor_id || !actor.title) return 'blocked'
  if (!rules.length) return 'needs_clarification'
  return 'ready'
}

function capabilityMapStatus(area: BusinessAreaEntry, intents: string[], rules: PermissionIntentRule[], areaScenarios: ArtifactRecord[]): StudioDiagramStatus {
  if (!area.business_area_id || !area.label) return 'blocked'
  if (!intents.length && !rules.length && !areaScenarios.length) return 'needs_clarification'
  return 'ready'
}

function groupItems(items: string[], path: string): StudioDiagramGroupItem[] {
  return items.map((item) => ({ label: item, path }))
}

function visibleItemsForHeight<T extends string | StudioDiagramGroupItem>(items: T[], visibleLimit: number, moreLabel: string): T[] {
  if (items.length <= visibleLimit) return items
  const visible = items.slice(0, Math.max(0, visibleLimit - 1))
  return [...visible, `+${items.length - visible.length} ${moreLabel}` as T]
}

function diagramItemLabel(item: string | { label: string }): string {
  return typeof item === 'string' ? item : item.label
}

function detailGroupHeight(items: Array<string | { label: string }>, visibleLimit: number): number {
  if (items.length <= 0) return 44
  const visibleItems = items.slice(0, visibleLimit)
  const rowUnits = visibleItems.reduce((total, item) => {
    const label = diagramItemLabel(item)
    return total + (label.length > 24 ? 2 : 1)
  }, 0)
  const rows = Math.max(1, Math.ceil(rowUnits / 2))
  return 52 + rows * 34
}

const capabilityMapNodes = computed<StudioDiagramNode[]>(() => {
  const areas = businessAreas.value.length
    ? businessAreas.value
    : [{
        business_area_id: '',
        label: 'Business Areas Needed',
        description: 'Define stable business areas so PM reviewers can see capability ownership clearly.',
      }]
  const areaSpacing = 440
  const areaWidth = 390
  const topY = 0
  const topMediumY = 0
  const topExpandedY = 0
  const areaY = 300
  const areaMediumY = 430
  const areaExpandedY = 560
  const reviewY = 690
  const areaRowWidth = (areas.length - 1) * areaSpacing + areaWidth
  const diagramWidth = Math.max(areaRowWidth, 980)
  const areaOffsetX = (diagramWidth - areaRowWidth) / 2
  const centerX = diagramWidth / 2 - 195
  const reviewX = diagramWidth / 2 - 160
  const productDetail = productSummary.value?.product_purpose
    || productSummary.value?.business_problem
    || cardDetail('product_summary', 'Capture the product purpose, business problem, supported question families, and governed boundaries.')
  const productIntentItems = groupItems(businessCapabilityIntents.value, path('/product-summary'))
  const productIntentMediumHeight = Math.max(292, 210 + detailGroupHeight(productIntentItems, 4))
  const productIntentExpandedHeight = Math.max(420, 240 + detailGroupHeight(productIntentItems, 8))

  const areaNodes = areas.map((area, index) => {
    const intents = capabilityIntentsForArea(area)
    const rules = permissionRulesForArea(area)
    const areaScenarios = scenariosForArea(area)
    const status = capabilityMapStatus(area, intents, rules, areaScenarios)
    const intentItems = groupItems(intents, path('/product-summary'))
    const scenarioItems = areaScenarios.map((scenario) => ({
      label: scenarioTitle(scenario),
      path: path(`/scenarios/${scenario.id}`),
    }))
    const ruleItems = rules.map((rule) => ({
      label: ruleLabel(rule),
      path: path('/permission-intent'),
    }))
    const visibleIntentItems = {
      medium: visibleItemsForHeight(intentItems, 4, 'more capability intents'),
      expanded: visibleItemsForHeight(intentItems, 8, 'more capability intents'),
    }
    const visibleScenarioItems = {
      medium: visibleItemsForHeight(scenarioItems, 4, 'more real situations'),
      expanded: visibleItemsForHeight(scenarioItems, 8, 'more real situations'),
    }
    const visibleRuleItems = {
      medium: visibleItemsForHeight(ruleItems, 4, 'more decision boundaries'),
      expanded: visibleItemsForHeight(ruleItems, 8, 'more decision boundaries'),
    }
    const mediumGroupsHeight = detailGroupHeight(visibleIntentItems.medium, 4)
      + detailGroupHeight(visibleScenarioItems.medium, 4)
      + detailGroupHeight(visibleRuleItems.medium, 4)
    const expandedGroupsHeight = detailGroupHeight(visibleIntentItems.expanded, 8)
      + detailGroupHeight(visibleScenarioItems.expanded, 8)
      + detailGroupHeight(visibleRuleItems.expanded, 8)
    const detailLines = Math.min(10, Math.max(4, Math.ceil((area.description || '').length / 54)))
    const detailHeight = detailLines * 16
    const areaMediumHeight = Math.max(520, 230 + detailHeight + mediumGroupsHeight)
    const areaExpandedHeight = Math.max(760, 270 + detailHeight + expandedGroupsHeight)
    return {
      id: `business-area-${area.business_area_id || index}`,
      title: area.label || humanizeToken(area.business_area_id) || `Business Area ${index + 1}`,
      subtitle: 'Business capability area',
      detail: shortText(area.description || 'A PM-owned business domain that groups capability intent, real situations, and decision boundaries.'),
      status,
      path: path('/business-areas'),
      x: areaOffsetX + index * areaSpacing,
      y: areaY,
      mediumY: areaMediumY,
      expandedY: areaExpandedY,
      width: areaWidth,
      height: 252,
      compactHeight: 252,
      mediumHeight: areaMediumHeight,
      expandedHeight: areaExpandedHeight,
      compactDetailLines: 3,
      mediumDetailLines: 5,
      expandedDetailLines: detailLines,
      compactMetaLimit: 2,
      mediumMetaLimit: 3,
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      meta: [
        `${intents.length} capability intent${intents.length === 1 ? '' : 's'}`,
        `${areaScenarios.length} real situation${areaScenarios.length === 1 ? '' : 's'}`,
        `${rules.length} decision boundar${rules.length === 1 ? 'y' : 'ies'}`,
      ],
      detailGroups: [
        {
          title: 'Capability intents',
          count: intents.length,
          path: path('/product-summary'),
          items: intentItems,
          mediumItemLimit: 4,
          expandedItemLimit: 8,
          moreLabel: 'more capability intents',
          tone: 'capability',
        },
        {
          title: 'Real situations',
          count: areaScenarios.length,
          path: path('/scenarios'),
          items: scenarioItems,
          mediumItemLimit: 4,
          expandedItemLimit: 8,
          moreLabel: 'more real situations',
          tone: 'behavior',
        },
        {
          title: 'Decision boundaries',
          count: rules.length,
          path: path('/permission-intent'),
          items: ruleItems,
          mediumItemLimit: 4,
          expandedItemLimit: 8,
          moreLabel: 'more decision boundaries',
          tone: 'authority',
        },
      ],
    } satisfies StudioDiagramNode
  })
  const maxAreaMediumHeight = Math.max(...areaNodes.map((node) => node.mediumHeight ?? node.height ?? 0), 382)
  const maxAreaExpandedHeight = Math.max(...areaNodes.map((node) => node.expandedHeight ?? node.height ?? 0), 560)
  const reviewMediumY = areaMediumY + maxAreaMediumHeight + 110
  const reviewExpandedY = areaExpandedY + maxAreaExpandedHeight + 130

  return [
    {
      id: 'source-context',
      title: 'Source Context',
      subtitle: 'Business evidence',
      detail: documents.value.length
        ? `${documents.value.length} source document${documents.value.length === 1 ? '' : 's'} shape this business map.`
        : 'Attach source documents so capability areas are grounded in reviewed business evidence.',
      status: documents.value.length ? 'ready' : 'needs_clarification',
      path: path('/source-docs'),
      x: Math.max(0, centerX - 430),
      y: topY,
      mediumY: topMediumY,
      expandedY: topExpandedY,
      width: 320,
      height: 200,
      compactHeight: 200,
      mediumHeight: 230,
      expandedHeight: 260,
      compactDetailLines: 3,
      sourcePosition: Position.Right,
      targetPosition: Position.Top,
      meta: ['Documents', 'Notes', 'Evidence'],
    },
    {
      id: 'product-intent',
      title: 'Product Intent',
      subtitle: 'Business purpose',
      detail: shortText(productDetail, 210),
      status: cardStatus('product_summary', 'blocked'),
      path: path('/product-summary'),
      x: centerX,
      y: topY,
      mediumY: topMediumY,
      expandedY: topExpandedY,
      width: 390,
      height: 222,
      compactHeight: 222,
      mediumHeight: productIntentMediumHeight,
      expandedHeight: productIntentExpandedHeight,
      compactDetailLines: 4,
      mediumDetailLines: 6,
      expandedDetailLines: 10,
      compactMetaLimit: 2,
      mediumMetaLimit: 3,
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      meta: [
        `${businessCapabilityIntents.value.length} supported question famil${businessCapabilityIntents.value.length === 1 ? 'y' : 'ies'}`,
        `${businessAreas.value.length} business area${businessAreas.value.length === 1 ? '' : 's'}`,
      ],
      detailGroups: [
        {
          title: 'Supported questions',
          count: businessCapabilityIntents.value.length,
          path: path('/product-summary'),
          items: productIntentItems,
          mediumItemLimit: 4,
          expandedItemLimit: 8,
          moreLabel: 'more supported questions',
          tone: 'capability',
        },
      ],
    },
    {
      id: 'actors-and-permissions',
      title: 'Actors and Decisions',
      subtitle: 'PM-owned controls',
      detail: cardDetail('permission_intent', 'Connect actors, business areas, allowed behavior, restricted behavior, and approval expectations.'),
      status: cardStatus('permission_intent', cardStatus('actor_model', 'blocked')),
      path: path('/permission-intent'),
      x: Math.min(diagramWidth - 320, centerX + 470),
      y: topY,
      mediumY: topMediumY,
      expandedY: topExpandedY,
      width: 320,
      height: 200,
      compactHeight: 200,
      mediumHeight: 244,
      expandedHeight: 282,
      compactDetailLines: 3,
      sourcePosition: Position.Left,
      targetPosition: Position.Top,
      meta: [
        `${permissionRules.value.length} permission rule${permissionRules.value.length === 1 ? '' : 's'}`,
        'Approval posture',
      ],
    },
    ...areaNodes,
    {
      id: 'pm-baseline',
      title: 'PM Review Baseline',
      subtitle: 'Handoff decision',
      detail: 'Review this business capability shape before Developer Design turns it into services, scopes, approvals, and verifiable contract behavior.',
      status: sufficiencyCards.value.every((card) => card.status === 'ready') && sufficiencyCards.value.length ? 'ready' : 'needs_clarification',
      path: path('/pm-review'),
      x: reviewX,
      y: reviewY,
      mediumY: reviewMediumY,
      expandedY: reviewExpandedY,
      width: 320,
      height: 214,
      compactHeight: 214,
      mediumHeight: 248,
      expandedHeight: 280,
      compactDetailLines: 3,
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      meta: ['Review', 'Lock', 'Developer baseline'],
    },
  ]
})

const capabilityMapEdges = computed<StudioDiagramEdge[]>(() => {
  const areas = businessAreas.value.length
    ? businessAreas.value
    : [{ business_area_id: '', label: 'Business Areas Needed', description: '' }]
  const areaEdges = areas.flatMap((area, index) => {
    const areaNodeId = `business-area-${area.business_area_id || index}`
    return [
      {
        id: `intent-to-area-${index}`,
        source: 'product-intent',
        target: areaNodeId,
        label: 'defines',
        status: capabilityMapNodes.value.find((node) => node.id === areaNodeId)?.status,
      },
      {
        id: `area-to-review-${index}`,
        source: areaNodeId,
        target: 'pm-baseline',
        label: 'review',
        status: capabilityMapNodes.value.find((node) => node.id === areaNodeId)?.status,
      },
    ] satisfies StudioDiagramEdge[]
  })
  return [
    { id: 'source-to-intent', source: 'source-context', target: 'product-intent', label: 'grounds' },
    { id: 'decisions-to-intent', source: 'actors-and-permissions', target: 'product-intent', label: 'constrains' },
    ...areaEdges,
  ]
})

const actorDecisionMapNodes = computed<StudioDiagramNode[]>(() => {
  const actorEntries = actors.value.length
    ? actors.value
    : [{
        actor_id: '',
        title: 'Actors Needed',
        summary: 'Define the distinct people, teams, or roles that need separate treatment.',
        visibility_expectations: '',
        action_expectations: '',
        approval_expectations: '',
        notes: '',
      }]
  const actorSpacing = 430
  const actorWidth = 390
  const actorRowWidth = (actorEntries.length - 1) * actorSpacing + actorWidth
  const diagramWidth = Math.max(actorRowWidth, 1140)
  const actorOffsetX = (diagramWidth - actorRowWidth) / 2
  const sourceY = 0
  const actorY = 330
  const actorMediumY = 440
  const actorExpandedY = 560
  const baselineX = diagramWidth / 2 - 190
  const modelX = diagramWidth / 2 - 430
  const permissionX = diagramWidth / 2 + 70

  const actorNodes = actorEntries.map((actor, index) => {
    const rules = rulesForActor(actor)
    const allowedRules = rules.filter((rule) => rule.access_posture === 'allowed' || rule.access_posture === 'bounded')
    const restrictedRules = rules.filter((rule) => rule.access_posture === 'restricted' || rule.governed_outcome_type === 'clarification_required')
    const approvalRules = rules.filter((rule) => rule.access_posture === 'approval_required' || rule.governed_outcome_type === 'approval_stop')
    const deniedRules = rules.filter((rule) => rule.access_posture === 'denied' || rule.governed_outcome_type === 'deny_request')
    const groupInputs = [
      { items: decisionRuleItems(allowedRules), more: 'more allowed/bounded rules' },
      { items: decisionRuleItems(restrictedRules), more: 'more restricted rules' },
      { items: decisionRuleItems(approvalRules), more: 'more approval rules' },
      { items: decisionRuleItems(deniedRules), more: 'more denied rules' },
    ]
    const mediumGroupsHeight = groupInputs.reduce(
      (total, group) => total + detailGroupHeight(visibleItemsForHeight(group.items, 4, group.more), 4),
      0,
    )
    const expandedGroupsHeight = groupInputs.reduce(
      (total, group) => total + detailGroupHeight(visibleItemsForHeight(group.items, 8, group.more), 8),
      0,
    )
    const detailLines = Math.min(9, Math.max(4, Math.ceil(actorSummary(actor).length / 58)))
    const detailHeight = detailLines * 16
    return {
      id: `actor-decision-${actor.actor_id || index}`,
      title: actorTitle(actor, index),
      subtitle: 'Actor decision posture',
      detail: shortText(actorSummary(actor), 190),
      status: actorMapStatus(actor, rules),
      path: path('/actor-model'),
      x: actorOffsetX + index * actorSpacing,
      y: actorY,
      mediumY: actorMediumY,
      expandedY: actorExpandedY,
      width: actorWidth,
      height: 252,
      compactHeight: 252,
      mediumHeight: Math.max(570, 230 + detailHeight + mediumGroupsHeight),
      expandedHeight: Math.max(820, 270 + detailHeight + expandedGroupsHeight),
      compactDetailLines: 3,
      mediumDetailLines: 5,
      expandedDetailLines: detailLines,
      compactMetaLimit: 2,
      mediumMetaLimit: 4,
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      meta: [
        `${allowedRules.length} allowed/bounded`,
        `${restrictedRules.length} restricted/clarify`,
        `${approvalRules.length} approval stop${approvalRules.length === 1 ? '' : 's'}`,
        `${deniedRules.length} denied`,
      ],
      detailGroups: [
        {
          title: 'Allowed behavior',
          count: allowedRules.length,
          path: path('/permission-intent'),
          items: groupInputs[0].items,
          mediumItemLimit: 4,
          expandedItemLimit: 8,
          moreLabel: groupInputs[0].more,
          tone: 'capability',
        },
        {
          title: 'Restricted behavior',
          count: restrictedRules.length,
          path: path('/permission-intent'),
          items: groupInputs[1].items,
          mediumItemLimit: 4,
          expandedItemLimit: 8,
          moreLabel: groupInputs[1].more,
          tone: 'behavior',
        },
        {
          title: 'Approval expectations',
          count: approvalRules.length,
          path: path('/permission-intent'),
          items: groupInputs[2].items,
          mediumItemLimit: 4,
          expandedItemLimit: 8,
          moreLabel: groupInputs[2].more,
          tone: 'authority',
        },
        {
          title: 'Denied boundaries',
          count: deniedRules.length,
          path: path('/permission-intent'),
          items: groupInputs[3].items,
          mediumItemLimit: 4,
          expandedItemLimit: 8,
          moreLabel: groupInputs[3].more,
          tone: 'glue',
        },
      ],
    } satisfies StudioDiagramNode
  })
  const maxActorMediumHeight = Math.max(...actorNodes.map((node) => node.mediumHeight ?? node.height ?? 0), 570)
  const maxActorExpandedHeight = Math.max(...actorNodes.map((node) => node.expandedHeight ?? node.height ?? 0), 820)
  const baselineMediumY = actorMediumY + maxActorMediumHeight + 110
  const baselineExpandedY = actorExpandedY + maxActorExpandedHeight + 130

  return [
    {
      id: 'actor-model-source',
      title: 'Actor Model',
      subtitle: 'Who participates',
      detail: cardDetail('actor_model', 'Define the distinct actors and what each one should see, do, and approve.'),
      status: cardStatus('actor_model', 'blocked'),
      path: path('/actor-model'),
      x: Math.max(0, modelX),
      y: sourceY,
      mediumY: sourceY,
      expandedY: sourceY,
      width: 360,
      height: 220,
      compactHeight: 220,
      mediumHeight: 260,
      expandedHeight: 300,
      compactDetailLines: 3,
      mediumDetailLines: 5,
      expandedDetailLines: 7,
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      meta: [
        `${actors.value.length} actor${actors.value.length === 1 ? '' : 's'}`,
        'Visibility',
        'Actions',
        'Approvals',
      ],
    },
    {
      id: 'decision-policy-source',
      title: 'Decision Boundaries',
      subtitle: 'Permission intent',
      detail: cardDetail('permission_intent', 'Capture the PM-owned rules for allowed, restricted, approval-required, and denied behavior.'),
      status: cardStatus('permission_intent', 'blocked'),
      path: path('/permission-intent'),
      x: Math.min(diagramWidth - 360, permissionX),
      y: sourceY,
      mediumY: sourceY,
      expandedY: sourceY,
      width: 360,
      height: 220,
      compactHeight: 220,
      mediumHeight: 280,
      expandedHeight: 330,
      compactDetailLines: 3,
      mediumDetailLines: 5,
      expandedDetailLines: 8,
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      meta: [
        `${permissionRules.value.length} decision rule${permissionRules.value.length === 1 ? '' : 's'}`,
        `${permissionRules.value.filter((rule) => rule.access_posture === 'approval_required').length} approval`,
        `${permissionRules.value.filter((rule) => rule.access_posture === 'denied').length} denied`,
      ],
    },
    ...actorNodes,
    {
      id: 'actor-decision-baseline',
      title: 'PM Authority Baseline',
      subtitle: 'Review decision',
      detail: 'Review actor-by-actor behavior before Developer Design turns these decisions into scopes, grants, denials, clarification behavior, and approval gates.',
      status: cardStatus('permission_intent', cardStatus('actor_model', 'blocked')),
      path: path('/pm-review'),
      x: baselineX,
      y: 700,
      mediumY: baselineMediumY,
      expandedY: baselineExpandedY,
      width: 380,
      height: 230,
      compactHeight: 230,
      mediumHeight: 270,
      expandedHeight: 310,
      compactDetailLines: 3,
      mediumDetailLines: 5,
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      meta: ['Actor review', 'Decision review', 'Developer baseline'],
    },
  ]
})

const actorDecisionMapEdges = computed<StudioDiagramEdge[]>(() => {
  const actorEntries = actors.value.length
    ? actors.value
    : [{ actor_id: '', title: 'Actors Needed' } as ActorModelEntry]
  const actorEdges = actorEntries.flatMap((actor, index) => {
    const actorNodeId = `actor-decision-${actor.actor_id || index}`
    const status = actorDecisionMapNodes.value.find((node) => node.id === actorNodeId)?.status
    return [
      {
        id: `actor-model-to-actor-${index}`,
        source: 'actor-model-source',
        target: actorNodeId,
        label: 'defines',
        status,
      },
      {
        id: `decision-policy-to-actor-${index}`,
        source: 'decision-policy-source',
        target: actorNodeId,
        label: 'governs',
        status,
      },
      {
        id: `actor-to-authority-baseline-${index}`,
        source: actorNodeId,
        target: 'actor-decision-baseline',
        label: 'review',
        status,
      },
    ] satisfies StudioDiagramEdge[]
  })
  return actorEdges
})

const productFlowNodes = computed<StudioDiagramNode[]>(() => {
  const centerX = 420
  const nodeWidth = 430
  const compactHeight = 218
  const reviewReady = sufficiencyCards.value.every((card) => card.status === 'ready') && sufficiencyCards.value.length > 0
  const actorAreaStatus = cardStatus('actor_model', cardStatus('business_areas', 'blocked'))
  const requirementScenarioStatus: StudioDiagramStatus = requirements.value.length && scenarios.value.length ? 'ready' : 'blocked'

  return [
    {
      id: 'source-docs',
      title: 'Source Docs',
      subtitle: 'Business evidence',
      detail: documents.value.length
        ? `${documents.value.length} source document${documents.value.length === 1 ? '' : 's'} attached. These are the evidence base for Product Design.`
        : 'Attach the business source material that should shape Product Design before PM intent is locked.',
      status: documents.value.length ? 'ready' : 'needs_clarification',
      path: path('/source-docs'),
      x: centerX,
      y: 0,
      width: nodeWidth,
      height: compactHeight,
      compactHeight,
      mediumHeight: 262,
      expandedHeight: 320,
      compactDetailLines: 3,
      mediumDetailLines: 5,
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      meta: [`${documents.value.length} source document${documents.value.length === 1 ? '' : 's'}`, 'Evidence base'],
    },
    {
      id: 'product-intent',
      title: 'Product Intent',
      subtitle: 'What the product means',
      detail: cardDetail('product_summary', 'Capture product purpose, business problem, goals, supported questions, and boundaries.'),
      status: cardStatus('product_summary', 'blocked'),
      path: path('/product-summary'),
      x: centerX,
      y: 280,
      width: nodeWidth,
      height: compactHeight,
      compactHeight,
      mediumHeight: 292,
      expandedHeight: 360,
      compactDetailLines: 3,
      mediumDetailLines: 5,
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      meta: [
        `${businessCapabilityIntents.value.length} supported question famil${businessCapabilityIntents.value.length === 1 ? 'y' : 'ies'}`,
        'Purpose and boundaries',
      ],
    },
    {
      id: 'actors-business-areas',
      title: 'Actors and Business Areas',
      subtitle: 'Who and where',
      detail: 'Define who participates and which business domains become stable product language.',
      status: actorAreaStatus,
      path: path('/actor-model'),
      x: centerX,
      y: 560,
      width: nodeWidth,
      height: compactHeight,
      compactHeight,
      mediumHeight: 310,
      expandedHeight: 390,
      compactDetailLines: 3,
      mediumDetailLines: 5,
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      meta: [
        `${actors.value.length} actor${actors.value.length === 1 ? '' : 's'}`,
        `${businessAreas.value.length} business area${businessAreas.value.length === 1 ? '' : 's'}`,
      ],
      detailGroups: [
        {
          title: 'Actors',
          count: actors.value.length,
          path: path('/actor-model'),
          items: actors.value.map((actor, index) => ({ label: actorTitle(actor, index), path: path('/actor-model') })),
          mediumItemLimit: 4,
          expandedItemLimit: 8,
          moreLabel: 'more actors',
          tone: 'capability',
        },
        {
          title: 'Business areas',
          count: businessAreas.value.length,
          path: path('/business-areas'),
          items: businessAreas.value.map((area) => ({ label: area.label || humanizeToken(area.business_area_id), path: path('/business-areas') })),
          mediumItemLimit: 4,
          expandedItemLimit: 8,
          moreLabel: 'more business areas',
          tone: 'behavior',
        },
      ],
    },
    {
      id: 'permission-intent',
      title: 'Permission Intent',
      subtitle: 'Allowed, restricted, approved, denied',
      detail: cardDetail('permission_intent', 'Capture PM-owned access posture before developers formalize scopes, denials, and approvals.'),
      status: cardStatus('permission_intent', 'blocked'),
      path: path('/permission-intent'),
      x: centerX,
      y: 840,
      width: nodeWidth,
      height: compactHeight,
      compactHeight,
      mediumHeight: 318,
      expandedHeight: 420,
      compactDetailLines: 3,
      mediumDetailLines: 5,
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      meta: [
        `${permissionRules.value.length} decision rule${permissionRules.value.length === 1 ? '' : 's'}`,
        'Authority boundaries',
      ],
      detailGroups: [
        {
          title: 'Decision rules',
          count: permissionRules.value.length,
          path: path('/permission-intent'),
          items: permissionRules.value.map((rule) => ({ label: ruleLabel(rule), path: path('/permission-intent') })),
          mediumItemLimit: 5,
          expandedItemLimit: 10,
          moreLabel: 'more decision rules',
          tone: 'authority',
        },
      ],
    },
    {
      id: 'requirements-scenarios',
      title: 'Requirements and Scenarios',
      subtitle: 'What matters and real situations',
      detail: 'Turn product intent into reviewable requirements and concrete situations that pressure the design.',
      status: requirementScenarioStatus,
      path: path('/requirements'),
      x: centerX,
      y: 1120,
      width: nodeWidth,
      height: compactHeight,
      compactHeight,
      mediumHeight: 310,
      expandedHeight: 390,
      compactDetailLines: 3,
      mediumDetailLines: 5,
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      meta: [
        `${requirements.value.length} requirement set${requirements.value.length === 1 ? '' : 's'}`,
        `${scenarios.value.length} real situation${scenarios.value.length === 1 ? '' : 's'}`,
      ],
      detailGroups: [
        {
          title: 'Real situations',
          count: scenarios.value.length,
          path: path('/scenarios'),
          items: scenarios.value.map((scenario) => ({ label: scenarioTitle(scenario), path: path(`/scenarios/${scenario.id}`) })),
          mediumItemLimit: 4,
          expandedItemLimit: 8,
          moreLabel: 'more real situations',
          tone: 'behavior',
        },
      ],
    },
    {
      id: 'pm-review-baseline',
      title: 'PM Review Baseline',
      subtitle: baselineRevisionLabel(),
      detail: developerBaseline.value
        ? 'Product Design is locked into a baseline that Developer Design must preserve.'
        : 'Review and lock Product Design so Developer Design has a stable baseline to preserve.',
      status: developerBaseline.value ? baselineStatus() : reviewReady ? 'needs_clarification' : 'blocked',
      path: path('/pm-review'),
      x: centerX,
      y: 1400,
      width: nodeWidth,
      height: compactHeight,
      compactHeight,
      mediumHeight: 280,
      expandedHeight: 340,
      compactDetailLines: 3,
      mediumDetailLines: 5,
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      meta: [
        baselineLockLabel(),
        reviewReady ? 'Review inputs ready' : 'Review inputs incomplete',
      ],
    },
  ]
})

const productFlowEdges = computed<StudioDiagramEdge[]>(() => [
  { id: 'source-to-intent', source: 'source-docs', target: 'product-intent', label: 'grounds' },
  { id: 'intent-to-actors-areas', source: 'product-intent', target: 'actors-business-areas', label: 'names' },
  { id: 'actors-areas-to-permission', source: 'actors-business-areas', target: 'permission-intent', label: 'governs' },
  { id: 'permission-to-requirements', source: 'permission-intent', target: 'requirements-scenarios', label: 'constrains' },
  { id: 'requirements-to-baseline', source: 'requirements-scenarios', target: 'pm-review-baseline', label: 'locks' },
])

function nonGoalLabel(entry: NonGoalEntry): string {
  return entry.statement || entry.rationale || 'Non-goal'
}

function successCriteriaLabel(entry: SuccessCriteriaEntry): string {
  return entry.statement || entry.evidence || 'Success criterion'
}

function evidenceExpectationLabel(entry: SuccessCriteriaEntry): string {
  const method = entry.review_method ? ` via ${entry.review_method}` : ''
  return entry.evidence ? `${entry.evidence}${method}` : entry.review_method || entry.statement || 'Evidence expectation'
}

const businessOutcomeMapNodes = computed<StudioDiagramNode[]>(() => {
  const goalItems = businessGoals.value.map((goal) => ({ label: goal, path: path('/product-summary') }))
  const nonGoalItems = nonGoals.value.map((entry) => ({ label: nonGoalLabel(entry), path: path('/non-goals') }))
  const successItems = successCriteria.value.map((entry) => ({ label: successCriteriaLabel(entry), path: path('/success-criteria') }))
  const evidenceItems = successCriteria.value
    .filter((entry) => entry.evidence || entry.review_method)
    .map((entry) => ({ label: evidenceExpectationLabel(entry), path: path('/success-criteria') }))
  const centerX = 420
  const nodeWidth = 430
  const compactHeight = 224
  const outcomesReady = businessGoals.value.length > 0 && nonGoals.value.length > 0 && successCriteria.value.length > 0

  return [
    {
      id: 'outcome-goals',
      title: 'Business Goals',
      subtitle: 'Desired outcomes',
      detail: successOutcomeSummary.value
        || cardDetail('product_summary', 'Define the business goals and outcome posture the product must support.'),
      status: businessGoals.value.length ? 'ready' : 'blocked',
      path: path('/product-summary'),
      x: centerX,
      y: 0,
      width: nodeWidth,
      height: compactHeight,
      compactHeight,
      mediumHeight: 310,
      expandedHeight: 420,
      compactDetailLines: 3,
      mediumDetailLines: 5,
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      meta: [
        `${businessGoals.value.length} business goal${businessGoals.value.length === 1 ? '' : 's'}`,
        'Outcome intent',
      ],
      detailGroups: [
        {
          title: 'Goals',
          count: businessGoals.value.length,
          path: path('/product-summary'),
          items: goalItems,
          mediumItemLimit: 5,
          expandedItemLimit: 10,
          moreLabel: 'more goals',
          tone: 'capability',
        },
      ],
    },
    {
      id: 'outcome-non-goals',
      title: 'Non-Goals',
      subtitle: 'Explicit boundaries',
      detail: nonGoals.value.length
        ? 'These boundaries make the product safer by naming what it should not do.'
        : 'Define what this product intentionally does not support so downstream design does not imply extra behavior.',
      status: cardStatus('non_goals', nonGoals.value.length ? 'ready' : 'blocked'),
      path: path('/non-goals'),
      x: 60,
      y: 330,
      width: nodeWidth,
      height: compactHeight,
      compactHeight,
      mediumHeight: 318,
      expandedHeight: 430,
      compactDetailLines: 3,
      mediumDetailLines: 5,
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      meta: [
        `${nonGoals.value.length} non-goal${nonGoals.value.length === 1 ? '' : 's'}`,
        'Boundaries',
      ],
      detailGroups: [
        {
          title: 'Explicitly out of scope',
          count: nonGoals.value.length,
          path: path('/non-goals'),
          items: nonGoalItems,
          mediumItemLimit: 5,
          expandedItemLimit: 10,
          moreLabel: 'more non-goals',
          tone: 'glue',
        },
      ],
    },
    {
      id: 'outcome-success-criteria',
      title: 'Success Criteria',
      subtitle: 'How success is judged',
      detail: successCriteria.value.length
        ? 'Success criteria convert goals into reviewable expectations.'
        : 'Define success criteria so PM review can judge whether the product outcome is actually satisfied.',
      status: cardStatus('success_criteria', successCriteria.value.length ? 'ready' : 'blocked'),
      path: path('/success-criteria'),
      x: 780,
      y: 330,
      width: nodeWidth,
      height: compactHeight,
      compactHeight,
      mediumHeight: 318,
      expandedHeight: 430,
      compactDetailLines: 3,
      mediumDetailLines: 5,
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      meta: [
        `${successCriteria.value.length} success ${successCriteria.value.length === 1 ? 'criterion' : 'criteria'}`,
        `${successCriteria.value.filter((entry) => entry.priority === 'high').length} high priority`,
      ],
      detailGroups: [
        {
          title: 'Criteria',
          count: successCriteria.value.length,
          path: path('/success-criteria'),
          items: successItems,
          mediumItemLimit: 5,
          expandedItemLimit: 10,
          moreLabel: 'more criteria',
          tone: 'behavior',
        },
      ],
    },
    {
      id: 'outcome-evidence',
      title: 'Evidence Expectations',
      subtitle: 'How reviewers verify',
      detail: evidenceItems.length
        ? 'Evidence expectations explain what must be observable or reviewable before the outcome can be trusted.'
        : 'Add evidence expectations and review methods so success criteria are verifiable, not just aspirational.',
      status: evidenceItems.length ? 'ready' : 'needs_clarification',
      path: path('/success-criteria'),
      x: centerX,
      y: 660,
      width: nodeWidth,
      height: compactHeight,
      compactHeight,
      mediumHeight: 330,
      expandedHeight: 450,
      compactDetailLines: 3,
      mediumDetailLines: 5,
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      meta: [
        `${evidenceItems.length} evidence expectation${evidenceItems.length === 1 ? '' : 's'}`,
        'Review method',
      ],
      detailGroups: [
        {
          title: 'Evidence',
          count: evidenceItems.length,
          path: path('/success-criteria'),
          items: evidenceItems,
          mediumItemLimit: 5,
          expandedItemLimit: 10,
          moreLabel: 'more evidence expectations',
          tone: 'authority',
        },
      ],
    },
    {
      id: 'outcome-review-baseline',
      title: 'Outcome Baseline',
      subtitle: baselineRevisionLabel(),
      detail: developerBaseline.value
        ? 'The reviewed outcome posture is part of the Product Design baseline developers must preserve.'
        : 'Lock Product Design once goals, non-goals, success criteria, and evidence expectations are reviewable.',
      status: developerBaseline.value ? baselineStatus() : outcomesReady ? 'needs_clarification' : 'blocked',
      path: path('/pm-review'),
      x: centerX,
      y: 990,
      width: nodeWidth,
      height: compactHeight,
      compactHeight,
      mediumHeight: 292,
      expandedHeight: 360,
      compactDetailLines: 3,
      mediumDetailLines: 5,
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      meta: [
        baselineLockLabel(),
        outcomesReady ? 'Outcome review ready' : 'Outcome gaps remain',
      ],
    },
  ]
})

const businessOutcomeMapEdges = computed<StudioDiagramEdge[]>(() => [
  {
    id: 'goals-to-non-goals',
    source: 'outcome-goals',
    target: 'outcome-non-goals',
    label: 'bounded by',
    status: nonGoals.value.length ? 'ready' : 'blocked',
  },
  {
    id: 'goals-to-success',
    source: 'outcome-goals',
    target: 'outcome-success-criteria',
    label: 'measured by',
    status: successCriteria.value.length ? 'ready' : 'blocked',
  },
  {
    id: 'success-to-evidence',
    source: 'outcome-success-criteria',
    target: 'outcome-evidence',
    label: 'verified by',
    status: successCriteria.value.some((entry) => entry.evidence || entry.review_method) ? 'ready' : 'needs_clarification',
  },
  {
    id: 'non-goals-to-baseline',
    source: 'outcome-non-goals',
    target: 'outcome-review-baseline',
    label: 'locks boundaries',
    status: nonGoals.value.length ? 'ready' : 'blocked',
  },
  {
    id: 'evidence-to-baseline',
    source: 'outcome-evidence',
    target: 'outcome-review-baseline',
    label: 'locks evidence',
    status: successCriteria.value.some((entry) => entry.evidence || entry.review_method) ? 'ready' : 'needs_clarification',
  },
])

const scenarioCoverageMapNodes = computed<StudioDiagramNode[]>(() => {
  const areas = businessAreas.value.length
    ? businessAreas.value
    : [{
        business_area_id: '',
        label: 'Business Areas Needed',
        description: 'Define business areas so real situations can be grouped into meaningful coverage lanes.',
      }]
  const areaSpacing = 440
  const areaWidth = 390
  const areaRowWidth = (areas.length - 1) * areaSpacing + areaWidth
  const diagramWidth = Math.max(areaRowWidth, 980)
  const areaOffsetX = (diagramWidth - areaRowWidth) / 2
  const sourceY = 0
  const areaY = 320
  const areaMediumY = 440
  const areaExpandedY = 580
  const baselineX = diagramWidth / 2 - 190

  const areaNodes = areas.map((area, index) => {
    const areaScenarios = scenarioCoverageForArea(area)
    const areaRequirements = requirementCoverageForArea(area)
    const areaRules = permissionRulesForArea(area)
    const scenarioItems = areaScenarios.map((scenario) => ({
      label: scenarioTitle(scenario),
      path: path(`/scenarios/${scenario.id}`),
    }))
    const requirementItems = areaRequirements.map((requirement) => ({
      label: cleanText(requirement.title) || 'Requirement set',
      path: path(`/requirements/${requirement.id}`),
    }))
    const boundaryItems = areaRules.map((rule) => ({
      label: ruleLabel(rule),
      path: path('/permission-intent'),
    }))
    const mediumGroupsHeight = detailGroupHeight(visibleItemsForHeight(scenarioItems, 5, 'more scenarios'), 5)
      + detailGroupHeight(visibleItemsForHeight(requirementItems, 4, 'more requirement sets'), 4)
      + detailGroupHeight(visibleItemsForHeight(boundaryItems, 4, 'more boundaries'), 4)
    const expandedGroupsHeight = detailGroupHeight(visibleItemsForHeight(scenarioItems, 10, 'more scenarios'), 10)
      + detailGroupHeight(visibleItemsForHeight(requirementItems, 8, 'more requirement sets'), 8)
      + detailGroupHeight(visibleItemsForHeight(boundaryItems, 8, 'more boundaries'), 8)
    const detailLines = Math.min(8, Math.max(3, Math.ceil((area.description || '').length / 58)))
    const detailHeight = detailLines * 16

    return {
      id: `scenario-area-${area.business_area_id || index}`,
      title: area.label || humanizeToken(area.business_area_id) || `Business Area ${index + 1}`,
      subtitle: 'Scenario coverage lane',
      detail: shortText(area.description || 'Real situations grouped by business area, with the requirements and boundaries each one exercises.', 190),
      status: areaScenarios.length ? 'ready' : 'needs_clarification',
      path: path('/scenarios'),
      x: areaOffsetX + index * areaSpacing,
      y: areaY,
      mediumY: areaMediumY,
      expandedY: areaExpandedY,
      width: areaWidth,
      height: 258,
      compactHeight: 258,
      mediumHeight: Math.max(560, 230 + detailHeight + mediumGroupsHeight),
      expandedHeight: Math.max(820, 270 + detailHeight + expandedGroupsHeight),
      compactDetailLines: 3,
      mediumDetailLines: 5,
      expandedDetailLines: detailLines,
      compactMetaLimit: 3,
      mediumMetaLimit: 4,
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      meta: [
        `${areaScenarios.length} real situation${areaScenarios.length === 1 ? '' : 's'}`,
        `${areaRequirements.length} requirement set${areaRequirements.length === 1 ? '' : 's'}`,
        `${areaRules.length} decision boundar${areaRules.length === 1 ? 'y' : 'ies'}`,
      ],
      detailGroups: [
        {
          title: 'Real situations',
          count: areaScenarios.length,
          path: path('/scenarios'),
          items: scenarioItems,
          mediumItemLimit: 5,
          expandedItemLimit: 10,
          moreLabel: 'more scenarios',
          tone: 'behavior',
        },
        {
          title: 'Requirements exercised',
          count: areaRequirements.length,
          path: path('/requirements'),
          items: requirementItems,
          mediumItemLimit: 4,
          expandedItemLimit: 8,
          moreLabel: 'more requirement sets',
          tone: 'capability',
        },
        {
          title: 'Boundaries exercised',
          count: areaRules.length,
          path: path('/permission-intent'),
          items: boundaryItems,
          mediumItemLimit: 4,
          expandedItemLimit: 8,
          moreLabel: 'more boundaries',
          tone: 'authority',
        },
      ],
    } satisfies StudioDiagramNode
  })
  const maxAreaMediumHeight = Math.max(...areaNodes.map((node) => node.mediumHeight ?? node.height ?? 0), 560)
  const maxAreaExpandedHeight = Math.max(...areaNodes.map((node) => node.expandedHeight ?? node.height ?? 0), 820)

  return [
    {
      id: 'scenario-requirements-source',
      title: 'Requirements',
      subtitle: 'What matters',
      detail: requirements.value.length
        ? `${requirements.value.length} requirement set${requirements.value.length === 1 ? '' : 's'} should be exercised by real situations.`
        : 'Capture requirements before judging scenario coverage.',
      status: requirements.value.length ? 'ready' : 'blocked',
      path: path('/requirements'),
      x: Math.max(0, diagramWidth / 2 - 410),
      y: sourceY,
      width: 360,
      height: 220,
      compactHeight: 220,
      mediumHeight: 270,
      expandedHeight: 320,
      compactDetailLines: 3,
      mediumDetailLines: 5,
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      meta: [`${requirements.value.length} requirement set${requirements.value.length === 1 ? '' : 's'}`, 'Reviewable expectations'],
    },
    {
      id: 'scenario-boundaries-source',
      title: 'Permission Boundaries',
      subtitle: 'What each scenario pressures',
      detail: permissionRules.value.length
        ? `${permissionRules.value.length} PM decision rule${permissionRules.value.length === 1 ? '' : 's'} should be exercised by scenarios.`
        : 'Capture permission intent so scenarios can pressure allowed, restricted, approval, and denied behavior.',
      status: permissionRules.value.length ? 'ready' : 'blocked',
      path: path('/permission-intent'),
      x: Math.min(diagramWidth - 360, diagramWidth / 2 + 50),
      y: sourceY,
      width: 360,
      height: 220,
      compactHeight: 220,
      mediumHeight: 270,
      expandedHeight: 320,
      compactDetailLines: 3,
      mediumDetailLines: 5,
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      meta: [`${permissionRules.value.length} decision rule${permissionRules.value.length === 1 ? '' : 's'}`, 'Boundaries'],
    },
    ...areaNodes,
    {
      id: 'scenario-coverage-baseline',
      title: 'Scenario Coverage Baseline',
      subtitle: baselineRevisionLabel(),
      detail: developerBaseline.value
        ? 'Scenario coverage is part of the locked Product Design baseline developers must preserve and verify.'
        : 'Lock Product Design after scenarios cover requirements and PM boundaries well enough for developer handoff.',
      status: developerBaseline.value ? baselineStatus() : scenarios.value.length ? 'needs_clarification' : 'blocked',
      path: path('/pm-review'),
      x: baselineX,
      y: 720,
      mediumY: areaMediumY + maxAreaMediumHeight + 110,
      expandedY: areaExpandedY + maxAreaExpandedHeight + 130,
      width: 380,
      height: 230,
      compactHeight: 230,
      mediumHeight: 280,
      expandedHeight: 340,
      compactDetailLines: 3,
      mediumDetailLines: 5,
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      meta: [
        `${scenarios.value.length} total scenario${scenarios.value.length === 1 ? '' : 's'}`,
        baselineLockLabel(),
      ],
    },
  ]
})

const scenarioCoverageMapEdges = computed<StudioDiagramEdge[]>(() => {
  const areas = businessAreas.value.length
    ? businessAreas.value
    : [{ business_area_id: '', label: 'Business Areas Needed', description: '' }]
  const areaEdges = areas.flatMap((area, index) => {
    const areaNodeId = `scenario-area-${area.business_area_id || index}`
    const status = scenarioCoverageMapNodes.value.find((node) => node.id === areaNodeId)?.status
    return [
      {
        id: `requirements-to-scenario-area-${index}`,
        source: 'scenario-requirements-source',
        target: areaNodeId,
        label: 'exercised by',
        status,
      },
      {
        id: `boundaries-to-scenario-area-${index}`,
        source: 'scenario-boundaries-source',
        target: areaNodeId,
        label: 'pressured by',
        status,
      },
      {
        id: `scenario-area-to-baseline-${index}`,
        source: areaNodeId,
        target: 'scenario-coverage-baseline',
        label: 'coverage',
        status,
      },
    ] satisfies StudioDiagramEdge[]
  })
  return areaEdges
})

function baselineRevisionLabel(): string {
  const revisionNumber = developerBaseline.value?.source_inputs.product_revision_number
  return revisionNumber ? `Product revision ${revisionNumber}` : 'Product baseline'
}

function baselineLockLabel(): string {
  if (!developerBaseline.value?.locked_at) return 'Not locked'
  const date = new Date(developerBaseline.value.locked_at)
  if (Number.isNaN(date.getTime())) return 'Locked'
  return `Locked ${date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}`
}

function baselineStatus(): StudioDiagramStatus {
  if (!developerBaseline.value) return 'blocked'
  return 'ready'
}

function developerDefinitionStatus(hasContent: boolean): StudioDiagramStatus {
  if (!developerBaseline.value) return 'blocked'
  return hasContent ? 'ready' : 'needs_clarification'
}

const handoffServiceCount = computed(() => developerDefinition.value?.service_topology_bindings.length ?? 0)
const handoffCapabilityCount = computed(() => developerDefinition.value?.capability_formalizations.length ?? 0)
const handoffScopeCount = computed(() =>
  developerDefinition.value?.capability_formalizations.reduce(
    (total, capability) => total + (capability.minimum_scope?.length ?? 0),
    0,
  ) ?? 0,
)
const handoffPermissionBindingCount = computed(() => developerDefinition.value?.permission_intent_bindings.length ?? 0)
const handoffApprovalCount = computed(() => {
  const grantPolicies = developerDefinition.value?.capability_formalizations.filter((capability) => capability.grant_policy).length ?? 0
  const approvalRules = developerDefinition.value?.permission_intent_bindings.filter((rule) =>
    rule.access_posture === 'approval_required' || rule.governed_outcome_type === 'approval_stop',
  ).length ?? 0
  return Math.max(grantPolicies, approvalRules)
})
const handoffVerificationCount = computed(() => {
  const verification = developerDefinition.value?.verification
  if (!verification) return 0
  return verification.supported_question_family_bindings.length
    + verification.business_goal_bindings.length
    + verification.non_goal_guards.length
    + verification.success_criteria_checks.length
})

const handoffMapNodes = computed<StudioDiagramNode[]>(() => {
  const baseline = developerBaseline.value
  const devDefinition = developerDefinition.value
  const pmReady = sufficiencyCards.value.every((card) => card.status === 'ready') && sufficiencyCards.value.length > 0
  const sourceY = 0
  const baselineY = 345
  const devY = 690

  return [
    {
      id: 'handoff-product-intent',
      title: 'Product Intent',
      subtitle: 'PM locked meaning',
      detail: cardDetail('product_summary', 'Product purpose, supported questions, business problem, goals, and explicit boundaries.'),
      status: cardStatus('product_summary', 'blocked'),
      path: path('/product-summary'),
      x: 0,
      y: sourceY,
      width: 330,
      height: 228,
      compactHeight: 228,
      mediumHeight: 270,
      expandedHeight: 320,
      compactDetailLines: 3,
      mediumDetailLines: 5,
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      meta: [
        `${businessCapabilityIntents.value.length} supported question famil${businessCapabilityIntents.value.length === 1 ? 'y' : 'ies'}`,
        'Business boundaries',
      ],
    },
    {
      id: 'handoff-actors-decisions',
      title: 'Actors and Decisions',
      subtitle: 'PM locked authority',
      detail: 'Actors, allowed behavior, restricted behavior, approval expectations, and denied boundaries.',
      status: cardStatus('permission_intent', cardStatus('actor_model', 'blocked')),
      path: path('/permission-intent'),
      x: 380,
      y: sourceY,
      width: 330,
      height: 228,
      compactHeight: 228,
      mediumHeight: 300,
      expandedHeight: 360,
      compactDetailLines: 3,
      mediumDetailLines: 5,
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      meta: [
        `${actors.value.length} actor${actors.value.length === 1 ? '' : 's'}`,
        `${permissionRules.value.length} decision rule${permissionRules.value.length === 1 ? '' : 's'}`,
      ],
      detailGroups: [
        {
          title: 'Decision posture',
          count: permissionRules.value.length,
          path: path('/permission-intent'),
          items: permissionRules.value.map((rule) => ({ label: ruleLabel(rule), path: path('/permission-intent') })),
          mediumItemLimit: 5,
          expandedItemLimit: 10,
          moreLabel: 'more decision rules',
          tone: 'authority',
        },
      ],
    },
    {
      id: 'handoff-business-evidence',
      title: 'Business Evidence',
      subtitle: 'PM locked situations',
      detail: 'Requirements, real situations, and service-shape intent that developers must preserve as executable behavior and tests.',
      status: requirements.value.length && scenarios.value.length ? 'ready' : 'needs_clarification',
      path: path('/scenarios'),
      x: 760,
      y: sourceY,
      width: 330,
      height: 228,
      compactHeight: 228,
      mediumHeight: 292,
      expandedHeight: 350,
      compactDetailLines: 3,
      mediumDetailLines: 5,
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      meta: [
        `${requirements.value.length} requirement set${requirements.value.length === 1 ? '' : 's'}`,
        `${scenarios.value.length} real situation${scenarios.value.length === 1 ? '' : 's'}`,
        `${shapes.value.length} service shape${shapes.value.length === 1 ? '' : 's'}`,
      ],
    },
    {
      id: 'handoff-baseline',
      title: 'Locked PM Baseline',
      subtitle: baselineRevisionLabel(),
      detail: baseline
        ? 'Developer Design should preserve this Product Design baseline when formalizing services, scopes, approvals, and verification evidence.'
        : 'Lock Product Design before Developer Design becomes authoritative. Without a baseline, service and scope choices are still provisional.',
      status: baselineStatus(),
      path: path('/pm-review'),
      x: 360,
      y: baselineY,
      width: 370,
      height: 238,
      compactHeight: 238,
      mediumHeight: 292,
      expandedHeight: 336,
      compactDetailLines: 4,
      mediumDetailLines: 6,
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      meta: [
        baselineLockLabel(),
        pmReady ? 'PM review complete' : 'PM review incomplete',
      ],
    },
    {
      id: 'handoff-services',
      title: 'Services Must Preserve Intent',
      subtitle: 'Developer formalization',
      detail: devDefinition
        ? 'Developer services should own the same business capabilities and responsibilities PM reviewed, without silently changing the product boundary.'
        : 'Developer Design still needs service ownership that preserves PM-reviewed capability and responsibility boundaries.',
      status: developerDefinitionStatus(handoffServiceCount.value > 0),
      path: path('/developer/service-formalization'),
      x: 0,
      y: devY,
      width: 330,
      height: 238,
      compactHeight: 238,
      mediumHeight: 310,
      expandedHeight: 370,
      compactDetailLines: 3,
      mediumDetailLines: 5,
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      meta: [
        `${handoffServiceCount.value} service boundar${handoffServiceCount.value === 1 ? 'y' : 'ies'}`,
        `${handoffCapabilityCount.value} capability mapping${handoffCapabilityCount.value === 1 ? '' : 's'}`,
      ],
    },
    {
      id: 'handoff-scopes',
      title: 'Scopes Preserve Decisions',
      subtitle: 'Authority mapping',
      detail: 'Actor and permission intent must become named scopes, actor constraints, denials, and clarification behavior.',
      status: developerDefinitionStatus(handoffScopeCount.value > 0 || (developerDefinition.value?.permission_intent_bindings.length ?? 0) > 0),
      path: path('/developer/governance-bindings'),
      x: 380,
      y: devY,
      width: 330,
      height: 238,
      compactHeight: 238,
      mediumHeight: 310,
      expandedHeight: 370,
      compactDetailLines: 3,
      mediumDetailLines: 5,
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      meta: [
        `${handoffPermissionBindingCount.value} permission binding${handoffPermissionBindingCount.value === 1 ? '' : 's'}`,
        `${handoffScopeCount.value} declared scope${handoffScopeCount.value === 1 ? '' : 's'}`,
      ],
    },
    {
      id: 'handoff-approvals',
      title: 'Approvals Preserve Stops',
      subtitle: 'Governed behavior',
      detail: 'Approval expectations must remain explicit as governed capability behavior, grant policy, preview posture, or intentional app-glue decision.',
      status: developerDefinitionStatus(handoffApprovalCount.value > 0 || !permissionRules.value.some((rule) => rule.access_posture === 'approval_required')),
      path: path('/developer/capability-formalization'),
      x: 760,
      y: devY,
      width: 330,
      height: 238,
      compactHeight: 238,
      mediumHeight: 310,
      expandedHeight: 370,
      compactDetailLines: 3,
      mediumDetailLines: 5,
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      meta: [
        `${handoffApprovalCount.value} approval mapping${handoffApprovalCount.value === 1 ? '' : 's'}`,
        'Preview before mutation',
      ],
    },
    {
      id: 'handoff-verification',
      title: 'Verification Preserves Evidence',
      subtitle: 'Contract checks',
      detail: 'Supported questions, business goals, non-goals, success criteria, and scenario packs should become testable verification expectations.',
      status: developerDefinitionStatus(handoffVerificationCount.value > 0),
      path: path('/developer/verification-expectations'),
      x: 1140,
      y: devY,
      width: 330,
      height: 238,
      compactHeight: 238,
      mediumHeight: 310,
      expandedHeight: 370,
      compactDetailLines: 3,
      mediumDetailLines: 5,
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      meta: [
        `${handoffVerificationCount.value} verification check${handoffVerificationCount.value === 1 ? '' : 's'}`,
        'Evidence trail',
      ],
    },
  ]
})

const handoffMapEdges = computed<StudioDiagramEdge[]>(() => [
  {
    id: 'handoff-intent-baseline',
    source: 'handoff-product-intent',
    target: 'handoff-baseline',
    label: 'locks meaning',
    status: cardStatus('product_summary', 'blocked'),
  },
  {
    id: 'handoff-decisions-baseline',
    source: 'handoff-actors-decisions',
    target: 'handoff-baseline',
    label: 'locks authority',
    status: cardStatus('permission_intent', cardStatus('actor_model', 'blocked')),
  },
  {
    id: 'handoff-evidence-baseline',
    source: 'handoff-business-evidence',
    target: 'handoff-baseline',
    label: 'locks evidence',
    status: requirements.value.length && scenarios.value.length ? 'ready' : 'needs_clarification',
  },
  {
    id: 'handoff-baseline-services',
    source: 'handoff-baseline',
    target: 'handoff-services',
    label: 'preserve as services',
    status: developerDefinitionStatus(handoffServiceCount.value > 0),
  },
  {
    id: 'handoff-baseline-scopes',
    source: 'handoff-baseline',
    target: 'handoff-scopes',
    label: 'preserve as scopes',
    status: developerDefinitionStatus(handoffScopeCount.value > 0 || handoffPermissionBindingCount.value > 0),
  },
  {
    id: 'handoff-baseline-approvals',
    source: 'handoff-baseline',
    target: 'handoff-approvals',
    label: 'preserve stops',
    status: developerDefinitionStatus(handoffApprovalCount.value > 0 || !permissionRules.value.some((rule) => rule.access_posture === 'approval_required')),
  },
  {
    id: 'handoff-baseline-verification',
    source: 'handoff-baseline',
    target: 'handoff-verification',
    label: 'preserve evidence',
    status: developerDefinitionStatus(handoffVerificationCount.value > 0),
  },
])

const diagramTabs = computed<Array<{ key: ProductDiagramTab; label: string; summary: string }>>(() => [
  {
    key: 'capabilities',
    label: 'Business Capability Map',
    summary: 'Capability areas, supported intents, situations, and decision boundaries.',
  },
  {
    key: 'actors',
    label: 'Actor and Decision Map',
    summary: 'Actors, allowed behavior, restrictions, approvals, and denied boundaries.',
  },
  {
    key: 'outcomes',
    label: 'Business Outcome Map',
    summary: 'Goals, non-goals, success criteria, and evidence expectations.',
  },
  {
    key: 'scenarios',
    label: 'Scenario Coverage Map',
    summary: 'Real situations grouped by business area, requirements, and boundaries.',
  },
  {
    key: 'handoff',
    label: 'PM-to-Developer Handoff',
    summary: 'What Product Design has locked and what Developer Design must preserve.',
  },
  {
    key: 'components',
    label: 'Product Component Map',
    summary: 'Source docs through intent, actors, business areas, permissions, scenarios, and PM baseline.',
  },
])

function open(path: string) {
  router.push(path)
}
</script>

<template>
  <div class="diagram-page">
    <div v-if="projectStore.loading && !project" class="empty-state">Loading product diagrams...</div>
    <template v-else-if="project">
      <section class="page-header">
        <button class="back-link" type="button" @click="open(`/design/projects/${project.id}/pm`)">
          ← Product Overview
        </button>
        <div class="page-kicker">Product Design Diagrams</div>
        <h1>{{ project.name }}</h1>
        <p>
          PM diagrams show the business components Studio must preserve before Developer Design turns them into contract, services, controls, and evidence.
        </p>
      </section>

      <section class="diagram-tabs" aria-label="Product diagram tabs">
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
        <article v-if="activeDiagramTab === 'capabilities'" class="panel panel-full">
          <StudioNodeDiagram
            headline="Business Capability Map"
            summary="Business-facing capability areas, the user intents they support, real situations that exercise them, and PM-owned decision boundaries."
            :nodes="capabilityMapNodes"
            :edges="capabilityMapEdges"
            :height="760"
            :fit-version="diagramFitVersion"
            @navigate="open"
          />
        </article>

        <article v-else-if="activeDiagramTab === 'actors'" class="panel panel-full">
          <StudioNodeDiagram
            headline="Actor and Decision Map"
            summary="Actor-facing decision posture: allowed and bounded behavior, restricted behavior, approval expectations, and denied boundaries."
            :nodes="actorDecisionMapNodes"
            :edges="actorDecisionMapEdges"
            :height="760"
            :fit-version="diagramFitVersion"
            @navigate="open"
          />
        </article>

        <article v-else-if="activeDiagramTab === 'outcomes'" class="panel panel-full">
          <StudioNodeDiagram
            headline="Business Outcome Map"
            summary="A PM-readable outcome map showing business goals, explicit non-goals, success criteria, evidence expectations, and the reviewed outcome baseline."
            :nodes="businessOutcomeMapNodes"
            :edges="businessOutcomeMapEdges"
            :height="760"
            :fit-version="diagramFitVersion"
            @navigate="open"
          />
        </article>

        <article v-else-if="activeDiagramTab === 'scenarios'" class="panel panel-full">
          <StudioNodeDiagram
            headline="Scenario Coverage Map"
            summary="Real situations grouped by business area, showing which requirements and PM decision boundaries each scenario lane exercises."
            :nodes="scenarioCoverageMapNodes"
            :edges="scenarioCoverageMapEdges"
            :height="780"
            :fit-version="diagramFitVersion"
            @navigate="open"
          />
        </article>

        <article v-else-if="activeDiagramTab === 'handoff'" class="panel panel-full">
          <StudioNodeDiagram
            headline="PM-to-Developer Handoff Map"
            summary="A PM-readable map of what Product Design has locked and what Developer Design must preserve as services, scopes, approvals, and verification."
            :nodes="handoffMapNodes"
            :edges="handoffMapEdges"
            :height="780"
            :fit-version="diagramFitVersion"
            @navigate="open"
          />
        </article>

        <article v-else class="panel panel-full">
          <StudioNodeDiagram
            headline="Product Component Map"
            summary="A PM-readable sequence from source documents to product intent, actors and business areas, permission intent, requirements and scenarios, and the PM review baseline."
            :nodes="productFlowNodes"
            :edges="productFlowEdges"
            :height="820"
            :fit-version="diagramFitVersion"
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
  max-width: 920px;
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
  min-height: 96px;
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

@media (max-width: 900px) {
  .diagram-tabs {
    grid-template-columns: 1fr;
  }
}
</style>
