<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  analyzeAgentConsumptionSimulationWithAssistant,
  createPmArtifact,
  runAgentConsumptionSimulator,
  updatePmArtifact,
} from '../design/project-api'
import {
  DEVELOPER_DEFINITION_SECTIONS,
  buildDeveloperDefinitionData,
  developerDefinitionArtifactId,
  developerDefinitionTargetRoute,
  developerDefinitionTargetStatus,
  findDeveloperDefinitionArtifact,
} from '../design/developer-definition'
import {
  applyReadinessFindingReviews,
  analyzeAgentConsumptionReadiness,
  normalizeReadinessFindingReviews,
  readinessFindingDecisionLabel,
  readinessOwnerLabel,
  readinessSeverityLabel,
  readinessStatusLabel,
  type AgentConsumptionReadinessFinding,
  type AgentConsumptionReadinessFindingDecision,
  type AgentConsumptionReadinessFindingReview,
  type AgentConsumptionReadinessReport,
} from '../design/agent-consumption-readiness'
import {
  buildAgentConsumabilityMetadata,
  normalizeAgentConsumabilityReviews,
  type AgentConsumabilityMetadata,
  type AgentConsumabilityBusinessLanguageRule,
  type AgentConsumabilityCapabilityReview,
  type AgentConsumabilityIntentRule,
} from '../design/agent-consumability'
import {
  effectLabel,
  formatEffectList,
  technicalEffectLabel,
} from '../design/effect-vocabulary'
import { showTechnicalIdentifiers, technicalHoverLabel } from '../design/technical-display'
import {
  buildAgentConsumptionSimulationRequest,
  scoreAgentConsumptionSimulation,
  type AgentConsumptionSimulationReport,
  type AgentConsumptionSimulationScoredCase,
} from '../design/agent-consumption-simulator'
import {
  buildHighRiskConfirmationReport,
  normalizeHighRiskConfirmationReviews,
  unresolvedHighRiskConfirmationItems,
} from '../design/high-risk-confirmations'
import { loadProject, projectStore } from '../design/project-store'
import type {
  CoverageStatus,
  AssistantExplanation,
  DeveloperBaselineData,
  DeveloperCapabilityFormalization,
  DeveloperCoverageState,
  DeveloperDefinitionData,
  HighRiskConfirmationItem,
  HighRiskConfirmationReview,
  TraceabilityCoverageItem,
  TraceabilityRecordData,
} from '../design/project-types'
import {
  DESIGN_TRACEABILITY_ARTIFACT_TYPE,
  buildTraceabilityRecord,
  developerBaselineMatchesCurrentContext,
  findDeveloperBaselineArtifact,
  findTraceabilityArtifact,
  hasReviewedCoverageResolution,
  summarizeCoverage,
  traceabilityArtifactId,
} from '../design/traceability'
import ProjectIssueBanner from '../components/ProjectIssueBanner.vue'
import AssistantWorkingOverlay from '../design/components/AssistantWorkingOverlay.vue'
import { useProjectIssue } from '../design/use-project-issue'
import {
  assistantStepActionsForText,
  type AssistantStepAction,
} from '../design/assistant-step-actions'
import { developerLabel } from '../design/developer-vocabulary'
import { coordinationResolutionChoices } from '../design/studio-operator'
import {
  mergeSemanticInterpretationRule,
  semanticInterpretationRuleForFinding,
} from '../design/semantic-interpretation-rules'

const route = useRoute()
const router = useRouter()

const projectId = computed(() => route.params.projectId as string)
const project = computed(() => projectStore.activeProject)
const isAppGluePage = computed(() => route.name === 'project-developer-app-glue')
const pageIssueKey = computed(() => isAppGluePage.value ? 'project-developer-app-glue' : 'project-developer-coverage')
const pageIssue = useProjectIssue(pageIssueKey)
const readOnlyMode = computed(() => projectStore.runtimeStatus?.read_only_mode !== false)
const readOnlyReason = computed(() =>
  projectStore.runtimeStatus?.read_only_reason
  || 'Studio is running in read-only mode. Explore the design, then download and run Studio locally to make changes.',
)
const documents = computed(() => projectStore.artifacts.documents)
const requirements = computed(() => projectStore.artifacts.requirements)
const scenarios = computed(() => projectStore.artifacts.scenarios)
const shapes = computed(() => projectStore.artifacts.shapes)
const baselineArtifact = computed(() => findDeveloperBaselineArtifact(projectStore.artifacts.pmArtifacts))
const traceabilityArtifact = computed(() => findTraceabilityArtifact(projectStore.artifacts.pmArtifacts))
const definitionArtifact = computed(() => findDeveloperDefinitionArtifact(projectStore.artifacts.pmArtifacts))

const draft = ref<TraceabilityRecordData | null>(null)
const saving = ref(false)
const saveError = ref<string | null>(null)
const handoffSaving = ref(false)
const handoffError = ref<string | null>(null)
const handoffSavedMessage = ref<string | null>(null)
const consumabilityRuleErrors = ref<Record<string, string>>({})
const simulatorRunning = ref(false)
const simulatorError = ref<string | null>(null)
const simulatorSavedMessage = ref<string | null>(null)
const simulatorReport = ref<AgentConsumptionSimulationReport | null>(null)
const simulatorAssistantLoading = ref(false)
const simulatorAssistantError = ref<string | null>(null)
const simulatorAssistantAnalysis = ref<AssistantExplanation | null>(null)
const focusedAssistantLoadingId = ref<string | null>(null)
const focusedAssistantErrors = ref<Record<string, string>>({})
const focusedAssistantAnalyses = ref<Record<string, AssistantExplanation>>({})
const remediationPrompts = ref<Record<string, string>>({})
const remediationApplyingId = ref<string | null>(null)
const remediationErrors = ref<Record<string, string>>({})
const remediationMessages = ref<Record<string, string>>({})
const coverageResolutionApplyingId = ref<string | null>(null)
const coverageResolutionMessages = ref<Record<string, string>>({})
const semanticRuleDrafts = ref<Record<string, {
  meaning: string
  all_terms: string
  any_terms: string
  exclude_terms: string
  interpretation: string
  agent_action: AgentConsumabilityBusinessLanguageRule['agent_action']
  target_capability: string
  suppress_unsupported_effects: string
}>>({})

const simulatorAssistantNextStepRows = computed(() =>
  (simulatorAssistantAnalysis.value?.next_steps ?? []).map((step) => ({
    step,
    actions: assistantStepActionsForText(step, projectId.value).filter((action) => {
      if (reviewedAgentReadinessReport.value.status !== 'blocked') return true
      return action.id !== 'open-publication'
        && action.id !== 'open-verification'
        && action.id !== 'open-generation'
    }),
  })),
)

const unreviewedReadinessFindings = computed(() =>
  reviewedAgentReadinessReport.value.findings.filter((finding) => finding.severity !== 'info' && !findingReview(finding.id)),
)

const informationalReadinessFindings = computed(() =>
  reviewedAgentReadinessReport.value.findings.filter((finding) => finding.severity === 'info' && !findingReview(finding.id)),
)

const appGlueCandidateFindings = computed(() =>
  reviewedAgentReadinessReport.value.findings.filter((finding) =>
    !findingReview(finding.id)
    && (
      finding.category === 'derived_target'
      || finding.category === 'composition_candidate'
      || finding.owner === 'agent_app_glue'
    ),
  ),
)

interface ReadinessFindingGroup {
  id: string
  findings: AgentConsumptionReadinessFinding[]
  representative: AgentConsumptionReadinessFinding
  affectedCapabilities: string[]
  affectedInputs: string[]
}

function readinessFindingGroupKey(finding: AgentConsumptionReadinessFinding): string {
  if (finding.category === 'clarification_behavior' && finding.input_name) {
    return `${finding.category}:${finding.input_name}:${finding.title}`
  }
  if (finding.category === 'declared_defaults' && finding.input_name) {
    return `${finding.category}:${finding.input_name}:${finding.title}`
  }
  if (finding.category === 'app_glue' && finding.input_name) {
    return `${finding.category}:${finding.input_name}:${finding.title}`
  }
  return finding.id
}

function actionableReadinessFindings(findings: AgentConsumptionReadinessFinding[]): AgentConsumptionReadinessFinding[] {
  return findings.filter((finding) => finding.severity !== 'info' || Boolean(findingReview(finding.id)))
}

const readinessFindingGroups = computed<ReadinessFindingGroup[]>(() => {
  const groups = new Map<string, AgentConsumptionReadinessFinding[]>()
  for (const finding of actionableReadinessFindings(agentReadinessReport.value.findings)) {
    const key = readinessFindingGroupKey(finding)
    const existing = groups.get(key) ?? []
    existing.push(finding)
    groups.set(key, existing)
  }
  return Array.from(groups.entries()).map(([id, findings]) => {
    const representative = findings[0]
    const affectedCapabilities = Array.from(new Set(
      findings.map((finding) => finding.capability_id).filter((value): value is string => Boolean(value)),
    ))
    const affectedInputs = Array.from(new Set(
      findings.map((finding) => finding.input_name).filter((value): value is string => Boolean(value)),
    ))
    return {
      id,
      findings,
      representative,
      affectedCapabilities,
      affectedInputs,
    }
  })
})

function simulatorCaseFocusKey(item: AgentConsumptionSimulationScoredCase): string {
  return `simulator:${item.probe_id}`
}

function readinessFindingGroupFocusKey(group: ReadinessFindingGroup): string {
  return `readiness-group:${group.id}`
}

function highRiskFocusKey(item: HighRiskConfirmationItem): string {
  return `high-risk:${item.id}`
}

function suggestedReadinessDecision(
  finding: AgentConsumptionReadinessFinding,
): AgentConsumptionReadinessFindingDecision {
  if (
    finding.owner === 'agent_app_glue'
    || finding.category === 'derived_target'
    || finding.category === 'composition_candidate'
    || finding.category === 'app_glue'
  ) {
    return 'explicit_app_glue'
  }
  if (
    finding.category === 'approval_boundary'
    || finding.category === 'clarification_behavior'
    || finding.category === 'declared_defaults'
    || finding.category === 'unsupported_effect'
  ) {
    return 'follow_up'
  }
  if (finding.severity === 'warning') return 'acceptable_warning'
  return 'follow_up'
}

function suggestedReadinessNote(
  finding: AgentConsumptionReadinessFinding,
  analysis?: AssistantExplanation | null,
): string {
  const assistantText = analysis?.focused_answer?.trim() || analysis?.summary?.trim()
  if (assistantText && !assistantText.toLowerCase().startsWith('fix or classify readiness finding')) {
    return assistantText
  }
  return readinessFindingPlainAction(finding)
}

function suggestedReadinessGroupNote(
  group: ReadinessFindingGroup,
  analysis?: AssistantExplanation | null,
): string {
  const note = suggestedReadinessNote(group.representative, analysis)
  if (group.findings.length <= 1) return note
  const capabilities = group.affectedCapabilities.join(', ')
  return `${note} Applies to ${group.findings.length} findings${capabilities ? `: ${capabilities}` : ''}.`
}

function readinessFindingQuestion(finding: AgentConsumptionReadinessFinding): string {
  if (finding.category === 'derived_target') return 'Decision needed: who picks the target group?'
  if (finding.category === 'composition_candidate') return 'Decision needed: who coordinates the steps?'
  if (finding.category === 'approval_boundary') return 'Decision needed: is this safe read-only work or approval-controlled work?'
  if (finding.category === 'clarification_behavior') return 'Decision needed: what should the runtime ask when the user leaves this unclear?'
  if (finding.category === 'declared_defaults') return 'Decision needed: what should happen when this optional value is omitted?'
  if (finding.category === 'unsupported_effect') return 'Decision needed: what should this package explicitly refuse to do?'
  if (finding.category === 'app_glue') return 'Decision needed: what does the consuming app own?'
  if (finding.category === 'output_semantics') return 'Decision needed: how should the app display the result?'
  return 'Decision needed'
}

function readinessFindingPlainAction(finding: AgentConsumptionReadinessFinding): string {
  if (finding.category === 'derived_target') {
    return 'Pick one: the service selects the target group, the app selects it before calling, or vague target requests ask the user to clarify.'
  }
  if (finding.category === 'composition_candidate') {
    return 'Pick one: one service owns the full sequence, or the consuming app coordinates the steps as explicit app glue.'
  }
  if (finding.category === 'approval_boundary') {
    return 'Make the approval boundary explicit, or make the capability wording clearly read-only or draft-only.'
  }
  if (finding.category === 'clarification_behavior') {
    return 'Add the business meaning and the clarification prompt the service or app should return when this input is missing or vague.'
  }
  if (finding.category === 'declared_defaults') {
    return 'Add a default, add a clarification question, or state that the service resolves the scope.'
  }
  if (finding.category === 'unsupported_effect') {
    return 'Declare whether send, export, publish, or mutation requests are refused or handled through approval.'
  }
  if (finding.category === 'app_glue') {
    return 'Record the app-owned behavior as a reviewed app profile, not as hidden generic runtime logic.'
  }
  if (finding.category === 'output_semantics') {
    return 'Add result-display guidance or a clearer output shape.'
  }
  return finding.recommendation
}

function readinessDecisionTaskTitle(finding: AgentConsumptionReadinessFinding): string {
  if (finding.category === 'derived_target') return 'Choose who picks the target group'
  if (finding.category === 'composition_candidate') return 'Choose who coordinates the steps'
  if (finding.category === 'approval_boundary') return 'Choose the approval boundary'
  if (finding.category === 'clarification_behavior') return 'Define the runtime clarification'
  if (finding.category === 'declared_defaults') return 'Define omitted-value behavior'
  if (finding.category === 'unsupported_effect') return 'Define unsupported outcomes'
  if (finding.category === 'app_glue') return 'Define app-owned behavior'
  if (finding.category === 'output_semantics') return 'Define result display'
  return 'Classify this decision'
}

function readinessDecisionTarget(group: ReadinessFindingGroup): string {
  const finding = group.representative
  const capabilityText = group.affectedCapabilities.length
    ? group.affectedCapabilities.slice(0, 3).join(', ')
    : finding.capability_id || 'affected capability'
  if (finding.category === 'derived_target' || finding.category === 'composition_candidate') {
    return `Decide whether ${capabilityText} is service-owned behavior or app-owned orchestration.`
  }
  if (finding.category === 'clarification_behavior') {
    const input = group.affectedInputs[0] ? plainInputName(group.affectedInputs[0]) : 'the missing input'
    return `Add a reviewed clarification prompt for ${input} on ${capabilityText}.`
  }
  if (finding.category === 'approval_boundary') {
    return `Make ${capabilityText} clearly read-only/draft-only, or define approval-preview behavior.`
  }
  if (finding.category === 'unsupported_effect') {
    return `Record what ${capabilityText} must refuse, such as export, send, publish, or mutation.`
  }
  if (finding.category === 'declared_defaults') {
    return `Record whether ${capabilityText} uses a default, asks a question, or lets the service resolve the scope.`
  }
  return readinessFindingPlainAction(finding)
}

function readinessDecisionDoneState(group: ReadinessFindingGroup): string {
  const review = findingGroupReview(group)
  if (review?.decision === 'explicit_app_glue') return 'Saved as app-owned guidance and included in package handoff metadata.'
  if (review?.decision === 'contract_composition') return 'Marked service-owned; update Capability Formalization if the contract still needs structural changes.'
  if (review?.decision === 'acceptable_warning') return 'Recorded as an accepted limitation for this package revision.'
  if (review?.decision === 'follow_up') return 'Tracked as follow-up; not safe to treat as fixed until the owning artifact changes.'
  if (canApplyClarificationRemediation(group)) return 'Done when the prompt is applied to the Developer Definition draft and saved as a new revision.'
  if (canResolveDerivedTargetOwnership(group)) return 'Done when one of the three resolution choices below is selected and saved.'
  return 'Done when a reviewed decision is saved or the owning contract/app profile is updated.'
}

function readinessReviewEffect(finding: AgentConsumptionReadinessFinding): string {
  const review = findingReview(finding.id)
  if (!review) return ''
  if (review.decision === 'contract_composition') {
    return 'Resolution effect: this is a service-contract fix. Edit Capability Formalization so one service owns the full flow; this review alone does not change generated behavior.'
  }
  if (review.decision === 'explicit_app_glue') {
    return 'Resolution effect: this becomes required app-glue guidance in the handoff/package metadata. Developers should implement it in the consuming app or app profile, not in generic ANIP calling code.'
  }
  if (review.decision === 'acceptable_warning') {
    return 'Resolution effect: this is recorded as an accepted limitation. It documents the decision but does not change the contract, generator, or runtime behavior.'
  }
  return 'Resolution effect: follow-up is still required. This stays visible as unresolved work until the contract, app glue, or service behavior is updated.'
}

function readinessFollowUpOwner(finding: AgentConsumptionReadinessFinding): string {
  if (finding.owner === 'developer_contract') return 'Developer edits the service contract.'
  if (finding.owner === 'agent_app_glue') return 'App developer updates the consuming app or app profile.'
  if (finding.owner === 'custom_service_logic') return 'Service developer updates custom service behavior.'
  return 'PM/dev reviewer decides the owning artifact.'
}

function readinessFollowUpTarget(finding: AgentConsumptionReadinessFinding): string {
  if (finding.category === 'clarification_behavior' || finding.category === 'declared_defaults' || finding.category === 'app_glue' || finding.category === 'output_semantics') {
    return 'Open Capability Formalization and update the affected capability input or app-consumability metadata.'
  }
  if (finding.category === 'approval_boundary' || finding.category === 'derived_target' || finding.category === 'composition_candidate') {
    return 'Open Capability Formalization and update capability shape, composition, approval policy, or implementation-fit decision.'
  }
  if (finding.category === 'unsupported_effect') {
    return 'Open Capability Formalization and update supported/unsupported business effects.'
  }
  return 'Open Developer Definition or the owning design page and update the saved contract.'
}

function readinessFollowUpDoneCondition(finding: AgentConsumptionReadinessFinding): string {
  if (finding.category === 'clarification_behavior') {
    return 'Done when the affected input has a reviewed clarification prompt, format, validation rule, or default behavior and this finding disappears on reload/save.'
  }
  if (finding.category === 'declared_defaults') {
    return 'Done when the optional input has a reviewed default, clarification prompt, or service-owned omission behavior.'
  }
  if (finding.category === 'approval_boundary') {
    return 'Done when the capability is clearly read-only/draft-only or has approval-preview effects and grant policy.'
  }
  if (finding.category === 'derived_target' || finding.category === 'composition_candidate') {
    return 'Done when Studio knows whether the service owns the flow or the consuming app owns the decision.'
  }
  if (finding.category === 'app_glue') {
    return 'Done when the app-owned behavior is saved as reviewed agent-consumability metadata or required app glue.'
  }
  return 'Done when the owning artifact is saved and the readiness check is clear.'
}

function readinessFollowUpRoute(): string {
  return `/design/projects/${project.value?.id}/developer/capability-formalization`
}

function plainInputName(inputName: string): string {
  return developerLabel(inputName || 'input').toLowerCase()
}

function canApplyClarificationRemediation(group: ReadinessFindingGroup): boolean {
  return group.representative.category === 'clarification_behavior'
    && group.affectedInputs.length === 1
    && group.affectedCapabilities.length > 0
}

function canResolveDerivedTargetOwnership(group: ReadinessFindingGroup): boolean {
  return group.representative.category === 'derived_target'
}

function derivedTargetAppGlueNote(group: ReadinessFindingGroup): string {
  const capabilities = group.affectedCapabilities.join(', ')
  return `App owns target selection before invoking ${capabilities || 'the affected capability'}. The consuming app must choose, retrieve, or ask for the target group, then call the service with an explicit bounded target.`
}

function derivedTargetServiceFollowUpNote(group: ReadinessFindingGroup): string {
  const capabilities = group.affectedCapabilities.join(', ')
  return `Service should own derived target selection for ${capabilities || 'the affected capability'}. Update Capability Formalization so the service contract defines the selection flow, composition, inputs, and empty-result behavior.`
}

function derivedTargetClarifyOnlyNote(group: ReadinessFindingGroup): string {
  const capabilities = group.affectedCapabilities.join(', ')
  return `Vague target requests for ${capabilities || 'the affected capability'} are intentionally not auto-selected. Runtime/app behavior should ask the user to name an explicit target group before invocation.`
}

async function applyReadinessGroupDecision(
  group: ReadinessFindingGroup,
  decision: AgentConsumptionReadinessFindingDecision,
  note: string,
) {
  if (readOnlyMode.value) return
  updateFindingGroupReview(group, { decision, note })
  if (decision === 'explicit_app_glue') {
    applySemanticRulesForReadinessGroup(group, note)
  }
  await saveCoverage()
}

function applySemanticRulesForReadinessGroup(group: ReadinessFindingGroup, note: string) {
  if (readOnlyMode.value) return
  for (const finding of group.findings) {
    if (!finding.capability_id) continue
    const capability = currentDefinitionDraft.value?.capability_formalizations.find((candidate) =>
      candidate.capability_id === finding.capability_id,
    )
    if (!capability) continue
    const currentReview = agentConsumabilityReviews.value[finding.capability_id] ?? defaultCapabilityReview(capability)
    const semanticRule = semanticInterpretationRuleForFinding(finding, note)
    const businessLanguageRules = mergeSemanticInterpretationRule(
      currentReview.business_language_rules,
      semanticRule,
    )
    if (!businessLanguageRules) continue
    updateCapabilityConsumabilityReview(capability, {
      app_glue_required: true,
      app_glue_reason: currentReview.app_glue_reason || note,
      business_language_rules: businessLanguageRules,
    })
  }
}

function defaultClarificationPromptForGroup(group: ReadinessFindingGroup): string {
  const inputName = group.affectedInputs[0] || group.representative.input_name || 'value'
  const label = plainInputName(inputName)
  if (inputName.includes('quarter')) {
    return 'Which quarter should I use? Please provide a value such as 2017-Q2.'
  }
  if (inputName.includes('region')) {
    return 'Which region should I use for this request?'
  }
  return `Which ${label} should I use for this request?`
}

function remediationPromptForGroup(group: ReadinessFindingGroup): string {
  return remediationPrompts.value[group.id] ?? ''
}

function onRemediationPromptInput(group: ReadinessFindingGroup, event: Event) {
  if (readOnlyMode.value) return
  remediationPrompts.value = {
    ...remediationPrompts.value,
    [group.id]: (event.target as HTMLTextAreaElement).value,
  }
}

function useSuggestedRemediationPrompt(group: ReadinessFindingGroup) {
  if (readOnlyMode.value) return
  remediationPrompts.value = {
    ...remediationPrompts.value,
    [group.id]: defaultClarificationPromptForGroup(group),
  }
}

function cloneDeveloperDefinition(definition: DeveloperDefinitionData): DeveloperDefinitionData {
  return JSON.parse(JSON.stringify(definition)) as DeveloperDefinitionData
}

async function saveDeveloperDefinitionDraft(definition: DeveloperDefinitionData) {
  if (readOnlyMode.value || !project.value) return
  const payload: DeveloperDefinitionData = {
    ...definition,
    artifact_type: 'developer_definition',
    compiled_contract_identity: null,
    saved_revision: null,
    saved_at: null,
  }
  if (definitionArtifact.value) {
    await updatePmArtifact(project.value.id, definitionArtifact.value.id, {
      title: 'Developer Definition',
      status: 'draft',
      data: payload,
    })
  } else {
    await createPmArtifact(project.value.id, {
      id: developerDefinitionArtifactId(project.value.id),
      title: 'Developer Definition',
      data: payload,
    })
  }
}

async function applyClarificationRemediation(group: ReadinessFindingGroup) {
  if (readOnlyMode.value || !project.value || !currentDefinitionDraft.value) return
  const inputName = group.affectedInputs[0] || group.representative.input_name
  const prompt = remediationPromptForGroup(group).trim()
  const key = group.id
  remediationErrors.value = { ...remediationErrors.value, [key]: '' }
  remediationMessages.value = { ...remediationMessages.value, [key]: '' }
  if (!inputName) {
    remediationErrors.value = { ...remediationErrors.value, [key]: 'No affected input was found for this fix.' }
    return
  }
  if (!prompt) {
    remediationErrors.value = { ...remediationErrors.value, [key]: 'Add the clarification prompt before applying this fix.' }
    return
  }
  remediationApplyingId.value = key
  try {
    const definition = cloneDeveloperDefinition(currentDefinitionDraft.value)
    const capabilityIds = new Set(group.affectedCapabilities)
    let updated = 0
    for (const capability of definition.capability_formalizations ?? []) {
      if (!capabilityIds.has(capability.capability_id)) continue
      for (const input of capability.inputs ?? []) {
        if (input.input_name !== inputName) continue
        input.clarification_hint = prompt
        updated += 1
      }
    }
    if (updated === 0) {
      throw new Error(`No matching ${plainInputName(inputName)} inputs were found in the affected capabilities.`)
    }
    await saveDeveloperDefinitionDraft(definition)
    await loadProject(project.value.id)
    syncDraft()
    remediationMessages.value = {
      ...remediationMessages.value,
      [key]: `Service-contract update applied: ${updated} capability input${updated === 1 ? '' : 's'} now has a runtime clarification prompt. Save a new Developer Definition revision before generation or publication.`,
    }
    handoffSavedMessage.value = null
  } catch (err) {
    remediationErrors.value = {
      ...remediationErrors.value,
      [key]: err instanceof Error ? err.message : String(err),
    }
  } finally {
    remediationApplyingId.value = null
  }
}

function readinessGroupReviewStateClass(group: ReadinessFindingGroup): Record<string, boolean> {
  const review = findingGroupReview(group)
  return {
    'readiness-card-reviewed': Boolean(review && review.decision !== 'follow_up' && review.decision !== 'explicit_app_glue' && findingGroupFullyReviewed(group)),
    'readiness-card-app-glue': Boolean(review?.decision === 'explicit_app_glue' && findingGroupFullyReviewed(group)),
    'readiness-card-follow-up': review?.decision === 'follow_up',
  }
}

function suggestedHighRiskStatus(
  item: HighRiskConfirmationItem,
): HighRiskConfirmationReview['status'] {
  return item.severity === 'blocker' ? 'deferred' : 'confirmed'
}

function suggestedHighRiskNote(
  item: HighRiskConfirmationItem,
  analysis?: AssistantExplanation | null,
): string {
  const firstStep = analysis?.next_steps?.[0]
  return firstStep || item.recommendation || item.detail
}

async function ensureLoaded(options: { force?: boolean } = {}) {
  if (!projectId.value) return
  if (!options.force && projectStore.activeProject?.id === projectId.value) return
  await loadProject(projectId.value)
}

const baseline = computed(() =>
  (baselineArtifact.value?.data as DeveloperBaselineData | undefined) ?? null,
)

const currentRequirements = computed(() =>
  requirements.value.find((item) => item.role === 'primary')
  ?? requirements.value[0]
  ?? null,
)

const currentShape = computed(() =>
  shapes.value.find((item) => item.id === projectStore.activeShapeId)
  ?? (shapes.value.length === 1 ? shapes.value[0] : null)
  ?? shapes.value[0]
  ?? null,
)

const currentScenarios = computed(() => scenarios.value)

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
  requirements.value.find((item) => item.id === baseline.value?.source_inputs.requirements_id)
  ?? null,
)

const lockedScenarios = computed(() =>
  (baseline.value?.source_inputs.scenario_ids ?? [])
    .map((id) => scenarios.value.find((item) => item.id === id) ?? null)
    .filter((item): item is NonNullable<typeof item> => item != null),
)

const lockedPrimaryScenario = computed(() =>
  scenarios.value.find((item) => item.id === baseline.value?.source_inputs.primary_scenario_id)
  ?? lockedScenarios.value[0]
  ?? null,
)

const lockedShape = computed(() =>
  shapes.value.find((item) => item.id === baseline.value?.source_inputs.shape_id)
  ?? null,
)

const isGovernedFrontingProject = computed(() => project.value?.project_type === 'governed_service_project')
const lockedImplementationContextLabel = computed(() =>
  isGovernedFrontingProject.value ? 'Backend Supply' : 'Service Design',
)
const lockedImplementationContextValue = computed(() =>
  isGovernedFrontingProject.value
    ? 'Source evidence, connection refs, and raw operations'
    : (lockedShape.value?.title || 'Not recorded'),
)

const developerReady = computed(() =>
  !!baseline.value
  && baselineAligned.value
  && !!lockedRequirements.value
  && lockedScenarios.value.length > 0
  && (isGovernedFrontingProject.value || !!lockedShape.value),
)

const developerDefinition = computed(() =>
  (definitionArtifact.value?.data as DeveloperDefinitionData | undefined) ?? null,
)

const currentDefinitionDraft = computed<DeveloperDefinitionData | null>(() => {
  if (!project.value || !developerReady.value) return null
  return buildDeveloperDefinitionData({
    project: project.value,
    baseline: baseline.value,
    requirements: lockedRequirements.value,
    scenarios: lockedScenarios.value,
    shape: lockedShape.value,
    pmArtifacts: projectStore.artifacts.pmArtifacts,
    existing: developerDefinition.value,
  })
})

function effectiveCoverageItem(item: TraceabilityCoverageItem): TraceabilityCoverageItem {
  if (item.mapping_mode !== 'automatic') return item
  if (hasReviewedCoverageResolution(item)) return item
  const effectiveDefinition = currentDefinitionDraft.value
  const definitionSaved = !!developerDefinition.value
  const derivedStatus = item.mapping_target_key
    ? (
      developerDefinitionTargetStatus(item.mapping_target_key, {
        developerDefinition: effectiveDefinition,
      })
    )
    : 'not_addressed'
  return {
    ...item,
    status: derivedStatus,
    rationale: '',
    mapping_note: !definitionSaved && item.mapping_target_key?.startsWith('developer_definition.')
      ? 'Status is derived from the current Developer Definition draft. Save the definition to persist it.'
      : item.mapping_note,
  }
}

const effectiveCoverage = computed(() =>
  (draft.value?.coverage ?? []).map((item) => effectiveCoverageItem(item)),
)

const productFoundationSources = computed(() =>
  project.value?.project_type === 'governed_service_project'
    ? ['product_summary', 'actor_model', 'permission_intent']
    : ['product_summary', 'actor_model', 'permission_intent', 'non_goals', 'success_criteria'],
)
const shapeCoverageTitle = computed(() =>
  project.value?.project_type === 'governed_service_project'
    ? 'Backend Supply Coverage'
    : 'Service Design Coverage',
)

const productFoundationGroups = computed(() => {
  const items = effectiveCoverage.value.filter((item) =>
    productFoundationSources.value.includes(item.source),
  )
  const groups = [
    { key: 'product_summary', title: 'Business Summary' },
    { key: 'actor_model', title: 'Actor Model' },
    { key: 'permission_intent', title: 'Permission Intent' },
    ...(project.value?.project_type === 'governed_service_project'
      ? []
      : [
          { key: 'non_goals', title: 'Non-Goals' },
          { key: 'success_criteria', title: 'Success Criteria' },
        ]),
  ] as Array<{ key: string; title: string }>
  return groups
    .map((group) => ({
      ...group,
      items: items.filter((item) => item.source === group.key),
    }))
    .filter((group) => group.items.length > 0)
})

function foundationSummary(items: TraceabilityCoverageItem[]) {
  return summarizeCoverage(items)
}

function foundationOpenByDefault(items: TraceabilityCoverageItem[]): boolean {
  const summary = foundationSummary(items)
  return summary.missing > 0 || summary.partial > 0
}

function coverageGroupSummary(items: TraceabilityCoverageItem[]) {
  return summarizeCoverage(items)
}

function coverageGroupOpenByDefault(items: TraceabilityCoverageItem[]): boolean {
  const summary = coverageGroupSummary(items)
  return summary.missing > 0 || summary.partial > 0
}

function coverageAttentionPreview(items: TraceabilityCoverageItem[]): string | null {
  const prioritized = items.filter((item) => item.status === 'not_addressed')
  const fallback = items.filter((item) => item.status === 'partially_addressed')
  const selected = prioritized.length > 0 ? prioritized : fallback
  if (selected.length === 0) return null
  const labels = selected.slice(0, 2).map((item) => item.label)
  const suffix = selected.length > 2 ? ` +${selected.length - 2} more` : ''
  return `${prioritized.length > 0 ? 'Needs attention' : 'Partially addressed'}: ${labels.join(', ')}${suffix}`
}

const groupedCoverage = computed(() => {
  const coverage = effectiveCoverage.value
  return [
    {
      key: 'product-design',
      title: 'Product Design Foundations',
      items: coverage.filter((item) =>
        productFoundationSources.value.includes(item.source),
      ),
    },
    { key: 'requirements', title: 'Requirements Coverage', items: coverage.filter((item) => item.source === 'requirements') },
    { key: 'scenario', title: 'Scenario Pack Coverage', items: coverage.filter((item) => item.source === 'scenario') },
    { key: 'shape', title: shapeCoverageTitle.value, items: coverage.filter((item) => item.source === 'shape') },
    { key: 'integration-fronting', title: 'Govern API / MCP Coverage', items: coverage.filter((item) => item.source === 'integration_fronting') },
  ].filter((group) => group.items.length > 0)
})

const coverageSummary = computed(() => summarizeCoverage(effectiveCoverage.value))

const implementationFitLabels: Record<string, string> = {
  native_anip: 'Native ANIP',
  contract_gap: 'Contract Gap',
  custom_service_logic: 'Custom Service Logic',
  agent_app_glue: 'Agent App Glue',
  external_integration: 'External Integration',
  unsupported: 'Unsupported',
}

const implementationFitSummary = computed(() => {
  const capabilities = currentDefinitionDraft.value?.capability_formalizations ?? []
  const counts = new Map<string, number>()
  for (const capability of capabilities) {
    const category = capability.implementation_fit?.category || 'contract_gap'
    counts.set(category, (counts.get(category) ?? 0) + 1)
  }
  return Array.from(counts.entries())
    .map(([category, count]) => ({
      category,
      count,
      label: implementationFitLabels[category] || developerLabel(category),
      examples: capabilities
        .filter((capability) => (capability.implementation_fit?.category || 'contract_gap') === category)
        .slice(0, 3)
        .map((capability) => capability.capability_id),
    }))
    .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label))
})

const recommendedAppGlue = computed(() => {
  const capabilities = currentDefinitionDraft.value?.capability_formalizations ?? []
  const recommendations = new Map<string, {
    key: string
    title: string
    summary: string
    action: string
    why: string
    capabilityIds: Set<string>
  }>()

  function add(
    key: string,
    title: string,
    summary: string,
    action: string,
    why: string,
    capabilityId: string,
  ) {
    const existing = recommendations.get(key)
    if (existing) {
      existing.capabilityIds.add(capabilityId)
      return
    }
    recommendations.set(key, { key, title, summary, action, why, capabilityIds: new Set([capabilityId]) })
  }

  for (const capability of capabilities) {
    const produces = capability.business_effects?.produces ?? []
    const doesNotProduce = capability.business_effects?.does_not_produce ?? []
    if (capability.implementation_fit?.category === 'agent_app_glue') {
      add(
        'product-framing',
        'Product framing guidance',
        'The consuming app may need business wording or role-specific framing before it calls this capability.',
        'Add a small app profile that explains how to introduce the capability, how to phrase boundaries, and any app-level preference.',
        'This keeps product-specific wording out of generic ANIP invocation code.',
        capability.capability_id,
      )
    }
    if (produces.some((value) => value.startsWith('content.'))) {
      add(
        'result-display',
        'Result display guidance',
        'The app should know which result fields matter most when showing drafts, summaries, recommendations, rationale, or evidence.',
        'Add display guidance for primary fields, supporting evidence, and any fields that should be hidden or shown secondary.',
        'Without this, the service can return a valid result but the app may render it poorly or inconsistently.',
        capability.capability_id,
      )
    }
    if (doesNotProduce.includes('external_dispatch') || doesNotProduce.includes('raw_data_export')) {
      add(
        'boundary-guidance',
        'Clear “will do / will not do” boundaries',
        `The app should explain outcomes such as ${effectLabel('content.draft')} vs ${effectLabel('external_dispatch')} or ${effectLabel('content.summary')} vs ${effectLabel('raw_data_export')} without relying on endless phrase deny lists.`,
        'Add boundary guidance that states supported outcomes and unsupported outcomes in business terms.',
        'This helps the app refuse unsupported requests like sending, exporting, or mutating without guessing from user wording.',
        capability.capability_id,
      )
    }
    if (capability.inputs.some((input) => (input.allowed_values ?? []).length > 0)) {
      add(
        'enum-meanings',
        'Plain-language meaning for choices',
        'Some inputs have fixed choices. The app needs short business meanings for those choices so it can map user intent safely.',
        'Add compact meanings for the choices, not long synonym lists.',
        'This avoids hardcoded phrase matching while still giving the app enough context to choose the right value.',
        capability.capability_id,
      )
    }
  }

  return Array.from(recommendations.values()).map((item) => ({
    ...item,
    capabilityIds: Array.from(item.capabilityIds),
    capabilityCount: item.capabilityIds.size,
  }))
})

const agentReadinessReport = computed(() =>
  analyzeAgentConsumptionReadiness(currentDefinitionDraft.value),
)

const readinessReviewDecisionOptions: Array<{ value: AgentConsumptionReadinessFindingDecision; label: string }> = [
  { value: 'contract_composition', label: readinessFindingDecisionLabel('contract_composition') },
  { value: 'explicit_app_glue', label: readinessFindingDecisionLabel('explicit_app_glue') },
  { value: 'acceptable_warning', label: readinessFindingDecisionLabel('acceptable_warning') },
  { value: 'follow_up', label: readinessFindingDecisionLabel('follow_up') },
]

const readinessFindingReviews = computed<Record<string, AgentConsumptionReadinessFindingReview>>(() => {
  const existing = draft.value?.agent_consumption_readiness?.finding_reviews ?? {}
  return normalizeReadinessFindingReviews(existing)
})

const reviewedAgentReadinessReport = computed<AgentConsumptionReadinessReport>(() =>
  applyReadinessFindingReviews(agentReadinessReport.value, readinessFindingReviews.value),
)

const agentConsumabilityReviews = computed<Record<string, AgentConsumabilityCapabilityReview>>(() =>
  normalizeAgentConsumabilityReviews(draft.value?.agent_consumability_reviews),
)

const reviewedAgentConsumabilityMetadata = computed(() =>
  buildAgentConsumabilityMetadata({
    definition: currentDefinitionDraft.value,
    readiness: reviewedAgentReadinessReport.value,
    manualReviews: agentConsumabilityReviews.value,
  }),
)

const highRiskConfirmationReviews = computed<Record<string, HighRiskConfirmationReview>>(() =>
  normalizeHighRiskConfirmationReviews(draft.value?.high_risk_confirmations?.reviews),
)

const highRiskConfirmationReport = computed(() => {
  if (!project.value) return null
  return buildHighRiskConfirmationReport({
    project: project.value,
    pmArtifacts: projectStore.artifacts.pmArtifacts,
    documents: documents.value,
    requirements: requirements.value,
    scenarios: scenarios.value,
    shapes: shapes.value,
    existing: draft.value?.high_risk_confirmations ?? null,
  })
})

const unresolvedHighRiskConfirmations = computed<HighRiskConfirmationItem[]>(() =>
  unresolvedHighRiskConfirmationItems(highRiskConfirmationReport.value),
)

const highRiskConfirmationOptions: Array<{ value: HighRiskConfirmationReview['status']; label: string }> = [
  { value: 'confirmed', label: 'Confirmed' },
  { value: 'deferred', label: 'Intentionally Deferred' },
]

const consumabilityReviewCapabilities = computed(() => {
  const capabilities = currentDefinitionDraft.value?.capability_formalizations ?? []
  const findingsByCapability = new Map<string, number>()
  const findingSeverityByCapability = new Map<string, AgentConsumptionReadinessFinding['severity']>()
  for (const finding of reviewedAgentReadinessReport.value.findings) {
    if (!finding.capability_id) continue
    findingsByCapability.set(finding.capability_id, (findingsByCapability.get(finding.capability_id) ?? 0) + 1)
    const currentSeverity = findingSeverityByCapability.get(finding.capability_id)
    if (!currentSeverity || severityRank(finding.severity) < severityRank(currentSeverity)) {
      findingSeverityByCapability.set(finding.capability_id, finding.severity)
    }
  }
  return capabilities
    .map((capability) => ({
      capability,
      review: agentConsumabilityReviews.value[capability.capability_id] ?? null,
      metadata: reviewedAgentConsumabilityMetadata.value.capabilities[capability.capability_id],
      findingCount: findingsByCapability.get(capability.capability_id) ?? 0,
      findingSeverity: findingSeverityByCapability.get(capability.capability_id) ?? null,
      needsReview:
        findingsByCapability.has(capability.capability_id)
        || capability.implementation_fit?.category === 'agent_app_glue'
        || reviewedAgentConsumabilityMetadata.value.capabilities[capability.capability_id]?.app_glue?.required === true,
    }))
    .sort((left, right) =>
      Number(right.needsReview) - Number(left.needsReview)
      || right.findingCount - left.findingCount
      || left.capability.capability_id.localeCompare(right.capability.capability_id),
    )
})

const consumabilityActionItems = computed(() =>
  consumabilityReviewCapabilities.value.filter((item) =>
    item.review
    || item.findingSeverity === 'blocker'
    || item.findingSeverity === 'warning'
    || suggestedConsumabilityAppGlueRequired(item),
  ),
)

const consumabilityOtherItems = computed(() =>
  consumabilityReviewCapabilities.value.filter((item) => !consumabilityActionItems.value.includes(item)),
)

type CoverageReviewLane = 'high-risk' | 'readiness' | 'consumability' | 'coverage' | 'completion'

const activeCoverageLane = ref<CoverageReviewLane>('coverage')
const coverageLaneTouched = ref(false)
const coveragePageLanes: CoverageReviewLane[] = ['high-risk', 'coverage', 'completion']
const appGluePageLanes: CoverageReviewLane[] = ['readiness', 'consumability', 'completion']

const coverageMissingCount = computed(() => coverageSummary.value.missing + coverageSummary.value.partial)
const consumabilityNeedsReviewCount = computed(() =>
  consumabilityReviewCapabilities.value.filter((item) => item.needsReview && !item.review).length,
)

const recommendedCoverageLane = computed<CoverageReviewLane>(() => {
  if (isAppGluePage.value) {
    if (
      reviewedAgentReadinessReport.value.status === 'blocked'
      || unreviewedReadinessFindings.value.length > 0
      || (simulatorReport.value?.summary.failed ?? 0) > 0
    ) {
      return 'readiness'
    }
    if (consumabilityNeedsReviewCount.value > 0) return 'consumability'
    return 'completion'
  }
  if ((highRiskConfirmationReport.value?.summary.unresolved ?? 0) > 0) return 'high-risk'
  if (coverageMissingCount.value > 0) return 'coverage'
  return 'completion'
})

const allCoverageReviewLanes = computed(() => [
  {
    key: 'high-risk' as const,
    title: 'High-Risk Decisions',
    detail: 'Confirm assumptions that could become contract or generated behavior.',
    count: highRiskConfirmationReport.value?.summary.unresolved ?? 0,
    meta: 'unresolved',
    state: (highRiskConfirmationReport.value?.summary.unresolved ?? 0) > 0 ? 'blocked' : 'ready',
  },
  {
    key: 'readiness' as const,
    title: 'Agent Readiness',
    detail: 'Run simulator evidence and resolve consumption findings before release gates.',
    count:
      reviewedAgentReadinessReport.value.summary.blockers
      + reviewedAgentReadinessReport.value.summary.warnings
      + (simulatorReport.value?.summary.failed ?? 0),
    meta: reviewedAgentReadinessReport.value.status === 'blocked' ? 'findings' : 'open items',
    state: reviewedAgentReadinessReport.value.status === 'blocked' ? 'blocked' : reviewedAgentReadinessReport.value.status,
  },
  {
    key: 'consumability' as const,
    title: 'App-Glue Review',
    detail: 'Review package-specific hints separately from the generic ANIP runtime.',
    count: consumabilityNeedsReviewCount.value,
    meta: 'needs review',
    state: consumabilityNeedsReviewCount.value > 0 ? 'warning' : 'ready',
  },
  {
    key: 'coverage' as const,
    title: 'Baseline Coverage',
    detail: 'Inspect how locked Product Design items map into Developer Design surfaces.',
    count: coverageMissingCount.value,
    meta: 'missing or partial',
    state: coverageMissingCount.value > 0 ? 'warning' : 'ready',
  },
  {
    key: 'completion' as const,
    title: 'Completion & Save',
    detail: 'Set developer status, add review notes, and persist the coverage record.',
    count: draft.value?.developer_status === 'ready_for_pm_review' ? 0 : 1,
    meta: draft.value?.developer_status === 'ready_for_pm_review' ? 'ready' : 'not ready',
    state: draft.value?.developer_status === 'ready_for_pm_review' ? 'ready' : 'info',
  },
])

const coverageReviewLanes = computed(() => {
  const allowed = new Set(isAppGluePage.value ? appGluePageLanes : coveragePageLanes)
  return allCoverageReviewLanes.value.filter((lane) => allowed.has(lane.key))
})

watch(
  recommendedCoverageLane,
  (lane) => {
    if (!coverageLaneTouched.value) activeCoverageLane.value = lane
  },
  { immediate: true },
)

watch([projectId, isAppGluePage], async () => {
  coverageLaneTouched.value = false
  await ensureLoaded({ force: true })
  syncDraft()
  activeCoverageLane.value = recommendedCoverageLane.value
})

function selectCoverageLane(lane: CoverageReviewLane) {
  activeCoverageLane.value = lane
  coverageLaneTouched.value = true
}

function severityRank(severity: AgentConsumptionReadinessFinding['severity']): number {
  if (severity === 'blocker') return 0
  if (severity === 'warning') return 1
  return 2
}

function findingReview(findingId: string): AgentConsumptionReadinessFindingReview | null {
  return readinessFindingReviews.value[findingId] ?? null
}

function findingGroupReviews(group: ReadinessFindingGroup): AgentConsumptionReadinessFindingReview[] {
  return group.findings
    .map((finding) => findingReview(finding.id))
    .filter((review): review is AgentConsumptionReadinessFindingReview => Boolean(review))
}

function findingGroupReview(group: ReadinessFindingGroup): AgentConsumptionReadinessFindingReview | null {
  const reviews = findingGroupReviews(group)
  if (reviews.length === 0) return null
  return reviews[0]
}

function findingGroupFullyReviewed(group: ReadinessFindingGroup): boolean {
  return findingGroupReviews(group).length === group.findings.length
}

function updateFindingReview(
  finding: AgentConsumptionReadinessFinding,
  patch: Partial<Pick<AgentConsumptionReadinessFindingReview, 'decision' | 'note'>>,
) {
  if (readOnlyMode.value || !draft.value) return
  const existingReport = (draft.value.agent_consumption_readiness ?? agentReadinessReport.value) as AgentConsumptionReadinessReport
  const currentReviews = {
    ...(existingReport.finding_reviews ?? {}),
    ...readinessFindingReviews.value,
  }
  const current = currentReviews[finding.id]
  const nextDecision = patch.decision ?? current?.decision
  if (!nextDecision) {
    delete currentReviews[finding.id]
  } else {
    currentReviews[finding.id] = {
      id: finding.id,
      decision: nextDecision,
      note: patch.note ?? current?.note ?? '',
      reviewed_at: new Date().toISOString(),
      review_method: 'manual',
    }
  }
  draft.value.agent_consumption_readiness = JSON.parse(JSON.stringify({
    ...agentReadinessReport.value,
    finding_reviews: currentReviews,
  }))
  handoffSavedMessage.value = null
}

function updateFindingGroupReview(
  group: ReadinessFindingGroup,
  patch: Partial<Pick<AgentConsumptionReadinessFindingReview, 'decision' | 'note'>>,
) {
  for (const finding of group.findings) {
    updateFindingReview(finding, patch)
  }
}

function onFindingGroupDecisionChange(group: ReadinessFindingGroup, event: Event) {
  const value = (event.target as HTMLSelectElement).value as AgentConsumptionReadinessFindingDecision | ''
  updateFindingGroupReview(group, { decision: value || undefined })
}

function onFindingGroupNoteInput(group: ReadinessFindingGroup, event: Event) {
  updateFindingGroupReview(group, { note: (event.target as HTMLTextAreaElement).value })
}

function highRiskReview(itemId: string): HighRiskConfirmationReview | null {
  return highRiskConfirmationReviews.value[itemId] ?? null
}

function updateHighRiskConfirmation(
  item: HighRiskConfirmationItem,
  patch: Partial<Pick<HighRiskConfirmationReview, 'status' | 'note'>>,
) {
  if (readOnlyMode.value || !draft.value || !highRiskConfirmationReport.value) return
  const currentReviews = {
    ...(highRiskConfirmationReport.value.reviews ?? {}),
    ...highRiskConfirmationReviews.value,
  }
  const current = currentReviews[item.id]
  const nextStatus = patch.status ?? current?.status
  if (!nextStatus) {
    delete currentReviews[item.id]
  } else {
    currentReviews[item.id] = {
      id: item.id,
      status: nextStatus,
      note: patch.note ?? current?.note ?? '',
      reviewed_at: new Date().toISOString(),
    }
  }
  draft.value.high_risk_confirmations = JSON.parse(JSON.stringify({
    ...highRiskConfirmationReport.value,
    reviews: currentReviews,
  }))
}

function onHighRiskStatusChange(item: HighRiskConfirmationItem, event: Event) {
  const value = (event.target as HTMLSelectElement).value as HighRiskConfirmationReview['status'] | ''
  updateHighRiskConfirmation(item, { status: value || undefined })
}

function onHighRiskNoteInput(item: HighRiskConfirmationItem, event: Event) {
  updateHighRiskConfirmation(item, { note: (event.target as HTMLTextAreaElement).value })
}

function handleAssistantStepAction(action: AssistantStepAction) {
  if (action.path) {
    router.push(action.path)
    return
  }
  if (readOnlyMode.value) return
  if (action.event === 'run_simulator') {
    runConsumptionSimulation()
  } else if (action.event === 'save_readiness_handoff') {
    saveReadinessHandoffArtifact()
  } else if (action.event === 'download_readiness_handoff') {
    downloadReadinessHandoff()
  }
}

function defaultCapabilityReview(capability: DeveloperCapabilityFormalization): AgentConsumabilityCapabilityReview {
  const metadata = reviewedAgentConsumabilityMetadata.value.capabilities[capability.capability_id]
  return {
    capability_id: capability.capability_id,
    reviewed_at: new Date().toISOString(),
    intent_category: suggestedConsumabilityIntentCategory(capability, metadata),
    intent_summary: suggestedConsumabilityIntentSummary(capability, metadata),
    app_glue_required: metadata?.app_glue?.required ?? capability.implementation_fit?.category === 'agent_app_glue',
    app_glue_reason: metadata?.app_glue?.reason ?? '',
    intent_rules: metadata?.intent_rules ?? [],
    business_language_rules: metadata?.business_language_rules ?? [],
    input_meanings: metadata?.input_meanings,
    reference_catalogs: metadata?.reference_catalogs,
    app_boundaries: metadata?.app_boundaries,
  }
}

function suggestedConsumabilityIntentCategory(
  capability: DeveloperCapabilityFormalization,
  metadata?: AgentConsumabilityMetadata['capabilities'][string],
): string {
  return metadata?.intent.category ?? capability.capability_id.replace(/_/g, '.')
}

function suggestedConsumabilityIntentSummary(
  capability: DeveloperCapabilityFormalization,
  metadata?: AgentConsumabilityMetadata['capabilities'][string],
): string {
  const summary = metadata?.intent.summary?.trim() || capability.summary?.trim()
  if (summary && !isOwnershipPlaceholder(summary)) return summary
  const title = capability.title?.trim()
  if (title && !isNamespaceTitlePlaceholder(title, capability.capability_id)) return title
  return titleFromCapabilityId(capability.capability_id)
}

function displayConsumabilityCapabilitySummary(
  capability: DeveloperCapabilityFormalization,
  metadata?: AgentConsumabilityMetadata['capabilities'][string],
): string {
  const summary = capability.summary?.trim()
  if (summary && !isOwnershipPlaceholder(summary)) return summary
  return `Needs reviewed intent summary. Suggested: ${suggestedConsumabilityIntentSummary(capability, metadata)}.`
}

function displayEffectList(effects?: string[] | null): string {
  return formatEffectList(effects)
}

function displayTechnicalEffects(effects?: string[] | null): string {
  return technicalEffectLabel(effects)
}

function displayOutcome(value: string | undefined | null): string {
  return developerLabel(value || 'not_recorded')
}

function suggestedConsumabilityAppGlueRequired(item: { capability: DeveloperCapabilityFormalization; metadata?: AgentConsumabilityMetadata['capabilities'][string] }): boolean {
  return item.metadata?.app_glue?.required === true || item.capability.implementation_fit?.category === 'agent_app_glue'
}

function suggestedConsumabilityAppGlueReason(
  item: { capability: DeveloperCapabilityFormalization; metadata?: AgentConsumabilityMetadata['capabilities'][string] },
): string {
  return item.metadata?.app_glue?.reason?.trim() ?? ''
}

function appProfileDecisionSummary(
  item: { capability: DeveloperCapabilityFormalization; metadata?: AgentConsumabilityMetadata['capabilities'][string]; review?: AgentConsumabilityCapabilityReview | null },
): string {
  if (item.review?.app_glue_required || suggestedConsumabilityAppGlueRequired(item)) {
    return item.review?.app_glue_reason?.trim()
      || suggestedConsumabilityAppGlueReason(item)
      || 'The consuming app owns a package-specific decision before or after invoking this capability.'
  }
  if (item.metadata?.app_boundaries?.unsupported_effects?.length) {
    return `The app should communicate unsupported outcomes such as ${formatEffectList(item.metadata.app_boundaries.unsupported_effects)}.`
  }
  if (item.metadata?.result_display?.primary_fields?.length) {
    return `The app can render ${item.metadata.result_display.primary_fields.join(', ')} as the primary result.`
  }
  return 'No app-owned behavior is required unless PM/dev chooses to add package-specific presentation or routing guidance.'
}

function appProfileHumanGuidance(
  item: { capability: DeveloperCapabilityFormalization; metadata?: AgentConsumabilityMetadata['capabilities'][string]; review?: AgentConsumabilityCapabilityReview | null },
): Array<{ title: string; detail: string; tone: 'app' | 'boundary' | 'context' | 'display' }> {
  const guidance: Array<{ title: string; detail: string; tone: 'app' | 'boundary' | 'context' | 'display' }> = []
  const appGlueReason = item.review?.app_glue_reason?.trim() || suggestedConsumabilityAppGlueReason(item)
  if (item.review?.app_glue_required || suggestedConsumabilityAppGlueRequired(item)) {
    guidance.push({
      title: 'App-owned behavior',
      detail: appGlueReason || 'The consuming app must make a package-specific decision without duplicating ANIP invocation mechanics.',
      tone: 'app',
    })
  }
  const unsupported = item.review?.app_boundaries?.unsupported_effects ?? item.metadata?.app_boundaries?.unsupported_effects ?? []
  if (unsupported.length) {
    guidance.push({
      title: 'Unsupported outcomes',
      detail: `The app should refuse or explain requests for ${formatEffectList(unsupported)}.`,
      tone: 'boundary',
    })
  }
  const requiredContext = item.metadata?.required_context?.filter((context) => context.missing_behavior !== 'optional') ?? []
  if (requiredContext.length) {
    guidance.push({
      title: 'Required context',
      detail: `Before invocation, the app should have ${requiredContext.map((context) => developerLabel(context.input).toLowerCase()).join(', ')} or ask for clarification.`,
      tone: 'context',
    })
  }
  const primaryFields = item.metadata?.result_display?.primary_fields ?? []
  if (primaryFields.length) {
    guidance.push({
      title: 'Result display',
      detail: `Show ${primaryFields.map((field) => developerLabel(field).toLowerCase()).join(', ')} as the primary result.`,
      tone: 'display',
    })
  }
  return guidance
}

function businessLanguageRulesForItem(
  item: { metadata?: AgentConsumabilityMetadata['capabilities'][string]; review?: AgentConsumabilityCapabilityReview | null },
): AgentConsumabilityBusinessLanguageRule[] {
  return item.review?.business_language_rules ?? item.metadata?.business_language_rules ?? []
}

function semanticRuleDraft(capability: DeveloperCapabilityFormalization) {
  const existing = semanticRuleDrafts.value[capability.capability_id]
  if (existing) return existing
  return {
    meaning: '',
    all_terms: '',
    any_terms: '',
    exclude_terms: '',
    interpretation: '',
    agent_action: 'treat_as_supported' as AgentConsumabilityBusinessLanguageRule['agent_action'],
    target_capability: '',
    suppress_unsupported_effects: '',
  }
}

function updateSemanticRuleDraft(
  capability: DeveloperCapabilityFormalization,
  field: keyof ReturnType<typeof semanticRuleDraft>,
  value: string,
) {
  if (readOnlyMode.value) return
  const current = semanticRuleDraft(capability)
  semanticRuleDrafts.value = {
    ...semanticRuleDrafts.value,
    [capability.capability_id]: {
      ...current,
      [field]: value,
    },
  }
}

function commaTerms(value: string): string[] | undefined {
  const terms = value
    .split(',')
    .map((term) => term.trim())
    .filter(Boolean)
  return terms.length > 0 ? terms : undefined
}

function displayTerms(terms?: string[] | null): string {
  return (terms ?? []).join(', ')
}

function semanticActionLabel(action?: AgentConsumabilityBusinessLanguageRule['agent_action']): string {
  if (action === 'treat_as_purpose') return 'Treat as purpose/framing'
  if (action === 'prefer_capability') return 'Prefer this capability'
  if (action === 'clarify') return 'Ask for clarification'
  return 'Treat as supported intent'
}

function semanticRuleSummary(rule: AgentConsumabilityBusinessLanguageRule): string {
  const parts: string[] = []
  if (rule.applies_when.all_terms?.length) parts.push(`must include ${rule.applies_when.all_terms.join(', ')}`)
  if (rule.applies_when.any_terms?.length) parts.push(`may include ${rule.applies_when.any_terms.join(', ')}`)
  if (rule.applies_when.exclude_terms?.length) parts.push(`unless ${rule.applies_when.exclude_terms.join(', ')}`)
  return parts.join(' · ') || 'No trigger terms recorded.'
}

function saveSemanticRuleDraft(capability: DeveloperCapabilityFormalization) {
  if (readOnlyMode.value) return
  const draftRule = semanticRuleDraft(capability)
  const appliesWhen = {
    all_terms: commaTerms(draftRule.all_terms),
    any_terms: commaTerms(draftRule.any_terms),
    exclude_terms: commaTerms(draftRule.exclude_terms),
  }
  if (!draftRule.meaning.trim()) {
    setConsumabilityError(capability.capability_id, 'business_language_rules', 'Describe what this business wording means.')
    return
  }
  if (!draftRule.interpretation.trim()) {
    setConsumabilityError(capability.capability_id, 'business_language_rules', 'Describe how the app/runtime should interpret it.')
    return
  }
  if (!appliesWhen.all_terms?.length && !appliesWhen.any_terms?.length) {
    setConsumabilityError(capability.capability_id, 'business_language_rules', 'Add at least one required or optional trigger term.')
    return
  }
  const currentReview = agentConsumabilityReviews.value[capability.capability_id] ?? defaultCapabilityReview(capability)
  const currentRules = currentReview.business_language_rules ?? []
  const nextRule: AgentConsumabilityBusinessLanguageRule = {
    id: `${capability.capability_id.replace(/[^a-z0-9]+/gi, '-')}-semantic-${currentRules.length + 1}`.toLowerCase(),
    meaning: draftRule.meaning.trim(),
    owner: 'agent_app_glue',
    applies_when: appliesWhen,
    interpretation: draftRule.interpretation.trim(),
    agent_action: draftRule.agent_action,
    target_capability: draftRule.target_capability.trim() || undefined,
    suppress_unsupported_effects: commaTerms(draftRule.suppress_unsupported_effects),
  }
  updateCapabilityConsumabilityReview(capability, {
    business_language_rules: [...currentRules, nextRule],
    app_glue_required: true,
    app_glue_reason: currentReview.app_glue_reason
      || 'The consuming app has reviewed business-language interpretation guidance for this capability.',
  })
  semanticRuleDrafts.value = {
    ...semanticRuleDrafts.value,
    [capability.capability_id]: {
      meaning: '',
      all_terms: '',
      any_terms: '',
      exclude_terms: '',
      interpretation: '',
      agent_action: 'treat_as_supported',
      target_capability: '',
      suppress_unsupported_effects: '',
    },
  }
  setConsumabilityError(capability.capability_id, 'business_language_rules', '')
}

function updateSemanticRule(
  capability: DeveloperCapabilityFormalization,
  index: number,
  patch: Partial<AgentConsumabilityBusinessLanguageRule>,
) {
  if (readOnlyMode.value) return
  const currentReview = agentConsumabilityReviews.value[capability.capability_id] ?? defaultCapabilityReview(capability)
  const rules = [...(currentReview.business_language_rules ?? [])]
  const current = rules[index]
  if (!current) return
  rules[index] = {
    ...current,
    ...patch,
    applies_when: {
      ...current.applies_when,
      ...(patch.applies_when ?? {}),
    },
  }
  updateCapabilityConsumabilityReview(capability, {
    business_language_rules: rules,
  })
}

function removeSemanticRule(capability: DeveloperCapabilityFormalization, index: number) {
  if (readOnlyMode.value) return
  const currentReview = agentConsumabilityReviews.value[capability.capability_id] ?? defaultCapabilityReview(capability)
  const rules = [...(currentReview.business_language_rules ?? [])]
  rules.splice(index, 1)
  updateCapabilityConsumabilityReview(capability, {
    business_language_rules: rules,
  })
}

async function acceptSuggestedAppProfile(capability: DeveloperCapabilityFormalization) {
  if (readOnlyMode.value) return
  updateCapabilityConsumabilityReview(capability, defaultCapabilityReview(capability))
  await saveCoverage()
}

function isOwnershipPlaceholder(value: string): boolean {
  return /^capability owned by .+\.$/i.test(value.trim())
}

function isNamespaceTitlePlaceholder(value: string, capabilityId: string): boolean {
  const namespace = capabilityId.includes('.') ? capabilityId.split('.')[0] : ''
  return Boolean(namespace) && value.trim().toLowerCase().startsWith(`${namespace.toLowerCase()}.`)
}

function titleFromCapabilityId(capabilityId: string): string {
  const localName = capabilityId.includes('.') ? capabilityId.split('.').slice(1).join('.') : capabilityId
  const text = localName.replace(/[._-]+/g, ' ').trim()
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : capabilityId
}

function updateCapabilityConsumabilityReview(
  capability: DeveloperCapabilityFormalization,
  patch: Partial<AgentConsumabilityCapabilityReview>,
) {
  if (readOnlyMode.value || !draft.value) return
  const currentReviews = {
    ...agentConsumabilityReviews.value,
  }
  currentReviews[capability.capability_id] = {
    ...defaultCapabilityReview(capability),
    ...(currentReviews[capability.capability_id] ?? {}),
    ...patch,
    capability_id: capability.capability_id,
    reviewed_at: new Date().toISOString(),
  }
  draft.value.agent_consumability_reviews = JSON.parse(JSON.stringify(currentReviews))
  handoffSavedMessage.value = null
}

function onConsumabilityFieldInput(
  capability: DeveloperCapabilityFormalization,
  field: 'intent_category' | 'intent_summary' | 'app_glue_reason',
  event: Event,
) {
  if (readOnlyMode.value) return
  updateCapabilityConsumabilityReview(capability, {
    [field]: (event.target as HTMLInputElement | HTMLTextAreaElement).value,
  })
}

function onAppGlueRequiredChange(capability: DeveloperCapabilityFormalization, event: Event) {
  if (readOnlyMode.value) return
  updateCapabilityConsumabilityReview(capability, {
    app_glue_required: (event.target as HTMLInputElement).checked,
  })
}

function formatIntentRules(rules: AgentConsumabilityIntentRule[] | undefined): string {
  return JSON.stringify(rules ?? [], null, 2)
}

function formatConsumabilityJson(value: unknown, fallback: unknown): string {
  return JSON.stringify(value ?? fallback, null, 2)
}

function setConsumabilityError(capabilityId: string, field: string, message: string) {
  consumabilityRuleErrors.value = {
    ...consumabilityRuleErrors.value,
    [`${capabilityId}:${field}`]: message,
  }
}

function onIntentRulesInput(capability: DeveloperCapabilityFormalization, event: Event) {
  if (readOnlyMode.value) return
  const raw = (event.target as HTMLTextAreaElement).value
  try {
    const parsed = JSON.parse(raw || '[]')
    if (!Array.isArray(parsed)) throw new Error('Intent rules must be a JSON array.')
    updateCapabilityConsumabilityReview(capability, {
      intent_rules: parsed,
    })
    consumabilityRuleErrors.value = {
      ...consumabilityRuleErrors.value,
      [capability.capability_id]: '',
    }
  } catch (err) {
    consumabilityRuleErrors.value = {
      ...consumabilityRuleErrors.value,
      [capability.capability_id]: err instanceof Error ? err.message : String(err),
    }
  }
}

function onConsumabilityJsonInput(
  capability: DeveloperCapabilityFormalization,
  field: 'input_meanings' | 'reference_catalogs' | 'app_boundaries' | 'selection_hints',
  event: Event,
) {
  if (readOnlyMode.value) return
  const raw = (event.target as HTMLTextAreaElement).value
  try {
    const parsed = JSON.parse(raw || (field === 'selection_hints' ? '[]' : '{}'))
    if (field === 'selection_hints' && !Array.isArray(parsed)) throw new Error('Selection hints must be a JSON array.')
    if (field !== 'selection_hints' && (!parsed || typeof parsed !== 'object' || Array.isArray(parsed))) {
      throw new Error(`${field} must be a JSON object.`)
    }
    updateCapabilityConsumabilityReview(capability, {
      [field]: parsed,
    })
    consumabilityRuleErrors.value = {
      ...consumabilityRuleErrors.value,
      [`${capability.capability_id}:${field}`]: '',
    }
  } catch (err) {
    consumabilityRuleErrors.value = {
      ...consumabilityRuleErrors.value,
      [`${capability.capability_id}:${field}`]: err instanceof Error ? err.message : String(err),
    }
  }
}

function buildReadinessHandoffData() {
  const report = reviewedAgentReadinessReport.value
  const reviewedFindings = report.findings.map((finding) => ({
    ...finding,
    review: report.finding_reviews?.[finding.id] ?? null,
  }))
  return {
    artifact_type: 'agent_consumption_readiness_handoff',
    generated_at: new Date().toISOString(),
    project: project.value
      ? {
          id: project.value.id,
          name: project.value.name,
          workspace_id: project.value.workspace_id,
        }
      : null,
    readiness: {
      status: report.status,
      score: report.score,
      summary: report.summary,
    },
    findings: reviewedFindings,
    required_app_glue: report.required_app_glue,
    agent_consumability: reviewedAgentConsumabilityMetadata.value,
    simulator_probes: report.probes,
    simulation_report: simulatorReport.value,
    review_summary: {
      contract_composition: reviewedFindings.filter((finding) => finding.review?.decision === 'contract_composition').length,
      explicit_app_glue: reviewedFindings.filter((finding) => finding.review?.decision === 'explicit_app_glue').length,
      acceptable_warning: reviewedFindings.filter((finding) => finding.review?.decision === 'acceptable_warning').length,
      follow_up: reviewedFindings.filter((finding) => finding.review?.decision === 'follow_up').length,
      unreviewed: reviewedFindings.filter((finding) => !finding.review).length,
    },
  }
}

async function runConsumptionSimulation() {
  if (readOnlyMode.value || !project.value || !currentDefinitionDraft.value) return
  simulatorRunning.value = true
  simulatorError.value = null
  simulatorReport.value = null
  try {
    const payload = buildAgentConsumptionSimulationRequest({
      project: {
        id: project.value.id,
        name: project.value.name,
        domain: project.value.domain,
      },
      definition: currentDefinitionDraft.value,
      readiness: reviewedAgentReadinessReport.value,
      agentConsumability: reviewedAgentConsumabilityMetadata.value,
    })
    const output = await runAgentConsumptionSimulator(payload)
    simulatorReport.value = scoreAgentConsumptionSimulation({
      modelOutput: output,
      readiness: reviewedAgentReadinessReport.value,
      probes: payload.probes,
    })
    await saveSimulationReportArtifact(simulatorReport.value)
    handoffSavedMessage.value = null
  } catch (err) {
    simulatorError.value = err instanceof Error ? err.message : String(err)
  } finally {
    simulatorRunning.value = false
  }
}

async function saveSimulationReportArtifact(report: AgentConsumptionSimulationReport) {
  if (readOnlyMode.value || !project.value) return
  simulatorSavedMessage.value = null
  const existing = projectStore.artifacts.pmArtifacts.find((artifact) =>
    (artifact.data as Record<string, unknown> | undefined)?.artifact_type === 'agent_consumption_simulation_report',
  )
  if (existing) {
    await updatePmArtifact(project.value.id, existing.id, {
      title: 'Agent Consumption Simulation Report',
      status: report.status === 'pass' ? 'active' : 'draft',
      data: report,
    })
  } else {
    await createPmArtifact(project.value.id, {
      id: `${project.value.id}-agent-consumption-simulation-report`,
      title: 'Agent Consumption Simulation Report',
      data: report,
    })
  }
  await loadProject(project.value.id)
  simulatorSavedMessage.value = 'Simulation report artifact saved.'
}

async function analyzeSimulationWithAssistant() {
  if (readOnlyMode.value || !project.value) return
  simulatorAssistantLoading.value = true
  simulatorAssistantError.value = null
  simulatorAssistantAnalysis.value = null
  try {
    simulatorAssistantAnalysis.value = await analyzeAgentConsumptionSimulationWithAssistant(
      project.value.id,
      'Use the latest simulator report to identify the smallest reviewed contract, app-glue, or service behavior fixes before generation or publication.',
      {
        readinessReport: reviewedAgentReadinessReport.value,
        highRiskReport: highRiskConfirmationReport.value,
      },
    )
  } catch (err) {
    simulatorAssistantError.value = err instanceof Error ? err.message : String(err)
  } finally {
    simulatorAssistantLoading.value = false
  }
}

async function analyzeSimulatorCaseWithAssistant(item: AgentConsumptionSimulationScoredCase) {
  if (readOnlyMode.value || !project.value) return
  const key = simulatorCaseFocusKey(item)
  focusedAssistantLoadingId.value = key
  focusedAssistantErrors.value = { ...focusedAssistantErrors.value, [key]: '' }
  try {
    const analysis = await analyzeAgentConsumptionSimulationWithAssistant(
      project.value.id,
      `Provide a concrete fix proposal for simulator case ${item.probe_id}. Include likely owner, exact artifact to edit, and what should change. If this is a stale or unknown probe mismatch, say that no contract change should be made until the simulator/probes are refreshed.`,
      {
        readinessReport: reviewedAgentReadinessReport.value,
        highRiskReport: highRiskConfirmationReport.value,
        focus: { kind: 'simulator_case', id: item.probe_id },
      },
    )
    focusedAssistantAnalyses.value = { ...focusedAssistantAnalyses.value, [key]: analysis }
  } catch (err) {
    focusedAssistantErrors.value = {
      ...focusedAssistantErrors.value,
      [key]: err instanceof Error ? err.message : String(err),
    }
  } finally {
    focusedAssistantLoadingId.value = null
  }
}

async function analyzeReadinessFindingGroupWithAssistant(group: ReadinessFindingGroup) {
  if (readOnlyMode.value || !project.value) return
  const finding = group.representative
  const key = readinessFindingGroupFocusKey(group)
  focusedAssistantLoadingId.value = key
  focusedAssistantErrors.value = { ...focusedAssistantErrors.value, [key]: '' }
  try {
    const analysis = await analyzeAgentConsumptionSimulationWithAssistant(
      project.value.id,
      `Provide a concrete, plain-language fix proposal for grouped readiness finding ${group.id}. It affects ${group.findings.length} findings across these capabilities: ${group.affectedCapabilities.join(', ') || 'none listed'}. Explain the user-facing risk, exact Studio artifact to edit, and smallest safe decision. Avoid internal terms unless they are required field names.`,
      {
        readinessReport: reviewedAgentReadinessReport.value,
        highRiskReport: highRiskConfirmationReport.value,
        focus: { kind: 'readiness_finding', id: finding.id },
      },
    )
    focusedAssistantAnalyses.value = { ...focusedAssistantAnalyses.value, [key]: analysis }
  } catch (err) {
    focusedAssistantErrors.value = {
      ...focusedAssistantErrors.value,
      [key]: err instanceof Error ? err.message : String(err),
    }
  } finally {
    focusedAssistantLoadingId.value = null
  }
}

async function analyzeHighRiskWithAssistant(item: HighRiskConfirmationItem) {
  if (readOnlyMode.value || !project.value) return
  const key = highRiskFocusKey(item)
  focusedAssistantLoadingId.value = key
  focusedAssistantErrors.value = { ...focusedAssistantErrors.value, [key]: '' }
  try {
    const analysis = await analyzeAgentConsumptionSimulationWithAssistant(
      project.value.id,
      `Provide a concrete review proposal for high-risk confirmation ${item.id}. Include whether it is safe to confirm or should be intentionally deferred, the reason, and the exact page/artifact the user should inspect if contract truth needs editing.`,
      {
        readinessReport: reviewedAgentReadinessReport.value,
        highRiskReport: highRiskConfirmationReport.value,
        focus: { kind: 'high_risk_confirmation', id: item.id },
      },
    )
    focusedAssistantAnalyses.value = { ...focusedAssistantAnalyses.value, [key]: analysis }
  } catch (err) {
    focusedAssistantErrors.value = {
      ...focusedAssistantErrors.value,
      [key]: err instanceof Error ? err.message : String(err),
    }
  } finally {
    focusedAssistantLoadingId.value = null
  }
}

async function applySuggestedReadinessGroupReview(group: ReadinessFindingGroup) {
  if (readOnlyMode.value) return
  const analysis = focusedAssistantAnalyses.value[readinessFindingGroupFocusKey(group)]
  await applyReadinessGroupDecision(
    group,
    suggestedReadinessDecision(group.representative),
    suggestedReadinessGroupNote(group, analysis),
  )
}

function applySuggestedHighRiskReview(item: HighRiskConfirmationItem) {
  if (readOnlyMode.value) return
  const analysis = focusedAssistantAnalyses.value[highRiskFocusKey(item)]
  updateHighRiskConfirmation(item, {
    status: suggestedHighRiskStatus(item),
    note: suggestedHighRiskNote(item, analysis),
  })
}

function downloadReadinessHandoff() {
  if (!project.value) return
  const content = JSON.stringify(buildReadinessHandoffData(), null, 2)
  const blob = new Blob([content], { type: 'application/json;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${project.value.id}-agent-consumption-readiness-handoff.json`
  link.click()
  URL.revokeObjectURL(url)
}

async function saveReadinessHandoffArtifact() {
  if (readOnlyMode.value || !project.value) return
  handoffSaving.value = true
  handoffError.value = null
  handoffSavedMessage.value = null
  try {
    const data = buildReadinessHandoffData()
    const existing = projectStore.artifacts.pmArtifacts.find((artifact) =>
      (artifact.data as Record<string, unknown> | undefined)?.artifact_type === 'agent_consumption_readiness_handoff',
    )
    if (existing) {
      await updatePmArtifact(project.value.id, existing.id, {
        title: 'Agent Consumption Readiness Handoff',
        status: 'draft',
        data,
      })
    } else {
      await createPmArtifact(project.value.id, {
        id: `${project.value.id}-agent-consumption-readiness-handoff`,
        title: 'Agent Consumption Readiness Handoff',
        data,
      })
    }
    await loadProject(project.value.id)
    handoffSavedMessage.value = 'Readiness handoff artifact saved.'
  } catch (err) {
    handoffError.value = err instanceof Error ? err.message : String(err)
  } finally {
    handoffSaving.value = false
  }
}

const statusOptions: Array<{ value: CoverageStatus; label: string }> = [
  { value: 'not_addressed', label: 'Not Addressed' },
  { value: 'partially_addressed', label: 'Partially Addressed' },
  { value: 'addressed', label: 'Addressed' },
  { value: 'deferred', label: 'Intentionally Deferred' },
  { value: 'not_applicable', label: 'Not Applicable' },
]

const developerStateOptions: Array<{ value: DeveloperCoverageState; label: string }> = [
  { value: 'not_started', label: 'Not Started' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'ready_for_pm_review', label: 'Ready for PM Review' },
]

const linkableSurfaces = DEVELOPER_DEFINITION_SECTIONS.map((section) => ({
  value: section.id,
  label: section.label,
}))

function syncDraft() {
  if (!developerReady.value || !baseline.value) {
    draft.value = null
    return
  }
  draft.value = buildTraceabilityRecord({
    pmArtifacts: projectStore.artifacts.pmArtifacts,
    requirements: lockedRequirements.value,
    scenarios: lockedScenarios.value,
    primaryScenarioId: lockedPrimaryScenario.value?.id ?? null,
    shape: lockedShape.value,
    baselineLockedAt: baseline.value.locked_at,
    existing: (traceabilityArtifact.value?.data as TraceabilityRecordData | undefined) ?? null,
    reducedFrontingProductDesign: project.value?.project_type === 'governed_service_project',
  })
}

onMounted(async () => {
  await ensureLoaded({ force: true })
  syncDraft()
})

watch(
  () => [
    projectId.value,
    baseline.value?.locked_at,
    baselineAligned.value,
    traceabilityArtifact.value?.updated_at,
    definitionArtifact.value?.updated_at,
    lockedRequirements.value?.id,
    lockedScenarios.value.map((item) => item.id).join('|'),
    lockedShape.value?.id,
  ] as const,
  async () => {
    await ensureLoaded()
    syncDraft()
  },
)

function updateCoverageStatus(itemId: string, value: CoverageStatus) {
  if (readOnlyMode.value || !draft.value) return
  draft.value.coverage = draft.value.coverage.map((item) =>
    item.id === itemId ? { ...item, status: value } : item,
  )
}

async function applyCoordinationResolution(
  item: TraceabilityCoverageItem,
  choiceId: ReturnType<typeof coordinationResolutionChoices>[number]['id'],
) {
  if (readOnlyMode.value || !project.value) return
  const choice = coordinationResolutionChoices(item, project.value.id).find((candidate) => candidate.id === choiceId)
  if (!choice) return
  coverageResolutionApplyingId.value = `${item.id}:${choice.id}`
  try {
    if (!draft.value) return
    draft.value.coverage = draft.value.coverage.map((coverageItem) => {
      if (coverageItem.id !== item.id) return coverageItem
      const linkedSurfaces = choice.id === 'contract_owned'
        ? ['capability_contracts']
        : choice.id === 'app_owned'
          ? ['generation_and_extensions']
          : coverageItem.linked_surfaces
      return {
        ...coverageItem,
        status: choice.status,
        rationale: choice.rationale,
        linked_surfaces: linkedSurfaces,
        operator_resolution: {
          choice_id: choice.id,
          applied_at: new Date().toISOString(),
          target_artifact: choice.patch_preview.target_artifact,
          summary: choice.patch_preview.title,
          requires_review: choice.patch_preview.requires_review,
          changes: choice.patch_preview.changes,
        },
      }
    })
    await saveCoverage()
    coverageResolutionMessages.value = {
      ...coverageResolutionMessages.value,
      [item.id]: `${choice.label} draft applied. ${choice.patch_preview.requires_review ? 'Review the owning page before generation.' : 'The coverage decision is saved.'}`,
    }
  } finally {
    coverageResolutionApplyingId.value = null
  }
}

function updateCoverageRationale(itemId: string, value: string) {
  if (readOnlyMode.value || !draft.value) return
  draft.value.coverage = draft.value.coverage.map((item) =>
    item.mapping_mode === 'automatic'
      ? item
      : item.id === itemId ? { ...item, rationale: value } : item,
  )
}

function selectLinkedSurface(itemId: string, surface: string) {
  if (readOnlyMode.value || !draft.value) return
  draft.value.coverage = draft.value.coverage.map((item) => {
    if (item.id !== itemId) return item
    if (item.mapping_mode === 'automatic') return item
    return { ...item, linked_surfaces: [surface] }
  })
}

async function saveCoverage() {
  if (readOnlyMode.value || !project.value || !draft.value) return
  saving.value = true
  saveError.value = null
  try {
    const payload = {
      ...draft.value,
      coverage: effectiveCoverage.value,
      artifact_type: DESIGN_TRACEABILITY_ARTIFACT_TYPE,
      developer_marked_at: draft.value.developer_status === 'ready_for_pm_review'
        ? new Date().toISOString()
        : draft.value.developer_marked_at,
      pm_review_status: 'pending' as const,
      pm_review_note: '',
      pm_reviewed_at: null,
      high_risk_confirmations: highRiskConfirmationReport.value
        ? JSON.parse(JSON.stringify({
            ...highRiskConfirmationReport.value,
            reviews: highRiskConfirmationReviews.value,
          }))
        : undefined,
      agent_consumption_readiness: JSON.parse(JSON.stringify(reviewedAgentReadinessReport.value)),
      agent_consumability_reviews: JSON.parse(JSON.stringify(agentConsumabilityReviews.value)),
    }

    if (traceabilityArtifact.value) {
      await updatePmArtifact(project.value.id, traceabilityArtifact.value.id, {
        title: 'Developer Coverage & PM Review',
        status: 'draft',
        data: payload,
      })
    } else {
      await createPmArtifact(project.value.id, {
        id: traceabilityArtifactId(project.value.id),
        title: 'Developer Coverage & PM Review',
        data: payload,
      })
    }
    await loadProject(project.value.id)
  } catch (err) {
    saveError.value = err instanceof Error ? err.message : String(err)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="developer-coverage">
    <AssistantWorkingOverlay
      :active="simulatorAssistantLoading"
      title="Building simulator fix plan"
      message="Studio is asking the assistant to inspect the latest simulator report and map failures to contract, metadata, app-glue, or service behavior fixes."
      detail="This call uses the configured assistant model. The page is blocked so the review state does not change while the plan is being produced."
    />

    <template v-if="project">
      <section class="page-header">
        <button class="back-link" type="button" @click="router.push(`/design/projects/${project.id}/developer`)">
          &larr; Back to Developer Design
        </button>
        <div class="page-kicker">Developer Design</div>
        <h1>{{ isAppGluePage ? 'Agent & App Glue' : 'Coverage Mapping' }}</h1>
        <p v-if="isAppGluePage">
          Review what an ANIP-aware app can consume directly, what still needs explicit app glue, and which simulator evidence supports those decisions. This keeps app-specific behavior visible instead of hiding it in the generic runtime.
        </p>
        <div v-if="isAppGluePage" class="page-header-actions">
          <button class="btn btn-secondary" type="button" @click="router.push(`/design/projects/${project.id}/developer/app-customization`)">
            Open Agent App Customization
          </button>
        </div>
        <p v-else>
          Formalize how Developer Design addresses the locked Product Design baseline. Coverage on this page should point to explicit sections of the developer definition contract, because that contract is what generation and verification will actually consume.
        </p>
      </section>

      <div v-if="readOnlyMode" class="readonly-banner">
        <strong>Read-only showcase mode</strong>
        <span>{{ readOnlyReason }}</span>
      </div>

      <ProjectIssueBanner :issue="pageIssue" :title="isAppGluePage ? 'Agent & App Glue diagnostics' : 'Coverage Mapping diagnostics'" />
      <section v-if="!baseline" class="panel empty-panel">
        <h2>Developer baseline is not locked</h2>
        <p>Return to Developer Overview and lock the current Product Design baseline before recording coverage.</p>
      </section>

      <section v-else-if="!baselineAligned" class="panel empty-panel">
        <h2>Developer baseline is out of sync</h2>
        <p>Product Design changed after this baseline was locked. Re-lock the baseline in Developer Overview before recording coverage.</p>
      </section>

      <section v-else-if="draft" class="grid coverage-layout">
        <article class="panel baseline-panel">
          <div class="panel-header">
            <h2>Locked Baseline</h2>
          </div>
          <div class="summary-stack">
            <div class="summary-row">
              <span class="summary-label">Requirements</span>
              <strong>{{ lockedRequirements?.title }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Scenario Pack</span>
              <strong>{{ lockedScenarios.length }} scenarios</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Primary Seed Scenario</span>
              <strong>{{ lockedPrimaryScenario?.title || 'None recorded' }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">{{ lockedImplementationContextLabel }}</span>
              <strong>{{ lockedImplementationContextValue }}</strong>
            </div>
          </div>
        </article>

        <article v-if="!isAppGluePage" class="panel coverage-summary-panel">
          <div class="panel-header">
            <h2>Coverage Summary</h2>
          </div>
          <div class="metric-grid">
            <div class="metric-card">
              <div class="metric-label">Total Items</div>
              <div class="metric-value">{{ coverageSummary.total }}</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">Addressed</div>
              <div class="metric-value">{{ coverageSummary.addressed }}</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">Partial</div>
              <div class="metric-value">{{ coverageSummary.partial }}</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">Missing</div>
              <div class="metric-value">{{ coverageSummary.missing }}</div>
            </div>
          </div>
        </article>

        <article v-if="isAppGluePage" class="panel implementation-fit-panel">
          <div class="panel-header">
            <h2>Implementation Fit</h2>
          </div>
          <p class="fit-intro">
            Studio separates contract-backed ANIP coverage from custom service work and agent-app glue. This is an implementation planning signal, not a claim that every scenario is zero-glue.
          </p>
          <div class="fit-list">
            <div v-for="item in implementationFitSummary" :key="item.category" class="fit-row">
              <div>
                <strong>{{ item.label }}</strong>
                <p>{{ item.examples.join(', ') || 'No examples recorded' }}</p>
              </div>
              <span>{{ item.count }}</span>
            </div>
          </div>
        </article>

        <article v-if="isAppGluePage" class="panel recommended-glue-panel">
          <div class="panel-header">
            <h2>Recommended App Glue</h2>
          </div>
          <p class="fit-intro">
            These are suggested responsibilities for the consuming app, such as wording, result display, or target selection. Keep them separate from generic ANIP calling code unless the service itself should own the behavior.
          </p>
          <div v-if="recommendedAppGlue.length" class="glue-list">
            <div v-for="item in recommendedAppGlue" :key="item.title" class="glue-card">
              <div class="glue-card-header">
                <strong>{{ item.title }}</strong>
                <span>{{ item.capabilityCount }} capability{{ item.capabilityCount === 1 ? '' : 'ies' }}</span>
              </div>
              <p>{{ item.summary }}</p>
              <div class="glue-card-guidance">
                <span>What to add</span>
                <p>{{ item.action }}</p>
              </div>
              <div class="glue-card-guidance">
                <span>Why it helps</span>
                <p>{{ item.why }}</p>
              </div>
              <details class="glue-card-details">
                <summary>Affected capabilities</summary>
                <p>{{ item.capabilityIds.join(', ') }}</p>
              </details>
            </div>
          </div>
          <p v-else class="empty-note">
            No app-glue recommendations yet. Studio will surface suggestions here when the Developer Definition exposes content rendering, business boundaries, enum grounding, or explicit agent-app glue.
          </p>
        </article>

        <article class="panel panel-full coverage-lanes-panel">
          <div class="panel-header">
            <div>
              <h2>Review Lanes</h2>
              <p class="fit-intro">
                {{ isAppGluePage
                  ? 'Agent and app-glue review is split into focused lanes. Start with simulator/readiness evidence, then review package-specific app hints before saving.'
                  : 'Coverage is split into focused lanes. Start with the recommended lane, then move through the remaining review work without scrolling through every detail at once.' }}
              </p>
            </div>
            <span class="recommended-lane">
              Recommended: {{ coverageReviewLanes.find((lane) => lane.key === recommendedCoverageLane)?.title }}
            </span>
          </div>
          <div class="coverage-lane-grid">
            <button
              v-for="lane in coverageReviewLanes"
              :key="lane.key"
              type="button"
              :class="['coverage-lane-card', `state-${lane.state}`, { active: activeCoverageLane === lane.key }]"
              @click="selectCoverageLane(lane.key)"
            >
              <span class="lane-count">{{ lane.count }}</span>
              <strong>{{ lane.title }}</strong>
              <em>{{ lane.meta }}</em>
              <p>{{ lane.detail }}</p>
            </button>
          </div>
        </article>

        <article v-if="activeCoverageLane === 'high-risk'" class="panel panel-full high-risk-panel">
          <div class="panel-header">
            <div>
              <h2>High-Risk Confirmations</h2>
              <p class="fit-intro">
                Studio asks only for decisions that would otherwise become contract truth or generated behavior: canonical capability IDs, service ownership, mapped permissions, unresolved clarifications, and automated readiness classifications.
              </p>
            </div>
            <span
              v-if="highRiskConfirmationReport"
              :class="['reviewed-count', { unresolved: highRiskConfirmationReport.summary.unresolved > 0 }]"
            >
              {{ highRiskConfirmationReport.summary.unresolved }} unresolved
            </span>
          </div>
          <div v-if="highRiskConfirmationReport?.items.length" class="high-risk-list">
            <div
              v-for="item in highRiskConfirmationReport.items"
              :key="item.id"
              class="high-risk-card"
              :class="{
                unresolved: !highRiskReview(item.id),
                'severity-card-blocker': item.severity === 'blocker',
                'severity-card-warning': item.severity === 'warning',
              }"
            >
              <div class="high-risk-card-header">
                <div>
                  <strong>{{ item.title }}</strong>
                  <p>{{ item.detail }}</p>
                </div>
                <span :class="['high-risk-severity-badge', item.severity === 'blocker' ? 'severity-blocker' : 'severity-warning']">
                  {{ item.severity }}
                </span>
              </div>
              <p class="readiness-recommendation">{{ item.recommendation }}</p>
              <div class="readiness-meta">
                <span>{{ displayOutcome(item.category) }}</span>
                <span>{{ displayOutcome(item.source) }}</span>
                <button v-if="item.target_route" class="inline-link" type="button" @click="router.push(item.target_route)">
                  Open source
                </button>
              </div>
              <div class="focused-assistant-actions">
                <button
                  class="btn btn-compact btn-secondary"
                  type="button"
                  :disabled="readOnlyMode || focusedAssistantLoadingId !== null"
                  @click="analyzeHighRiskWithAssistant(item)"
                >
                  {{ focusedAssistantLoadingId === highRiskFocusKey(item) ? 'Asking…' : 'Ask Assistant for This Decision' }}
                </button>
              </div>
              <p v-if="focusedAssistantErrors[highRiskFocusKey(item)]" class="error">
                {{ focusedAssistantErrors[highRiskFocusKey(item)] }}
              </p>
              <div
                v-if="focusedAssistantAnalyses[highRiskFocusKey(item)]"
                class="focused-assistant-preview"
              >
                <strong>{{ focusedAssistantAnalyses[highRiskFocusKey(item)].title }}</strong>
                <p>{{ focusedAssistantAnalyses[highRiskFocusKey(item)].focused_answer || focusedAssistantAnalyses[highRiskFocusKey(item)].summary }}</p>
                <div class="review-suggestion-preview">
                  <span>Suggested confirmation decision</span>
                  <strong>{{ suggestedHighRiskStatus(item) === 'confirmed' ? 'Confirmed' : 'Intentionally Deferred' }}</strong>
                  <p>{{ suggestedHighRiskNote(item, focusedAssistantAnalyses[highRiskFocusKey(item)]) }}</p>
                </div>
                <ul>
                  <li
                    v-for="step in focusedAssistantAnalyses[highRiskFocusKey(item)].next_steps"
                    :key="step"
                  >
                    {{ step }}
                  </li>
                </ul>
                <div class="assistant-step-actions">
                  <button
                    class="btn btn-compact btn-primary"
                    type="button"
                    :disabled="readOnlyMode"
                    @click="applySuggestedHighRiskReview(item)"
                  >
                    Apply Confirmation Decision
                  </button>
                  <button
                    v-if="item.target_route"
                    class="btn btn-compact btn-secondary"
                    type="button"
                    @click="router.push(item.target_route)"
                  >
                    Open Source
                  </button>
                </div>
              </div>
              <div class="readiness-review">
                <label>
                  Confirmation
                  <select
                    :value="highRiskReview(item.id)?.status ?? ''"
                    :disabled="readOnlyMode"
                    @change="onHighRiskStatusChange(item, $event)"
                  >
                    <option value="">Unconfirmed</option>
                    <option v-for="option in highRiskConfirmationOptions" :key="option.value" :value="option.value">
                      {{ option.label }}
                    </option>
                  </select>
                </label>
                <label>
                  Decision note
                  <textarea
                    rows="3"
                    :value="highRiskReview(item.id)?.note ?? ''"
                    :disabled="readOnlyMode"
                    placeholder="Record why this is safe to confirm or why it is intentionally deferred."
                    @input="onHighRiskNoteInput(item, $event)"
                  />
                </label>
              </div>
            </div>
          </div>
          <p v-else class="empty-note">
            No high-risk confirmations are currently required. Studio will add them when it detects assumptions that could become contract or generation truth.
          </p>
          <p v-if="unresolvedHighRiskConfirmations.length" class="error">
            {{ unresolvedHighRiskConfirmations.length }} confirmation{{ unresolvedHighRiskConfirmations.length === 1 ? '' : 's' }} must be confirmed or intentionally deferred before generation/publication.
          </p>
        </article>

        <article v-if="activeCoverageLane === 'readiness'" class="panel panel-full agent-readiness-panel">
          <div class="panel-header readiness-header">
            <div>
              <h2>Agent Consumption Readiness</h2>
              <p class="fit-intro">
                Deterministic checks for whether an ANIP-aware app can consume this package without discovering semantic gaps after generation, registry publication, or paid benchmark runs.
              </p>
              <p class="fit-intro why-copy">
                Why this matters: this is where Studio separates native ANIP behavior from reviewed app glue before generation or publication.
              </p>
            </div>
            <div :class="['readiness-score', `status-${reviewedAgentReadinessReport.status}`]">
              <span>Score</span>
              <strong>{{ reviewedAgentReadinessReport.score }}/100</strong>
              <em>{{ readinessStatusLabel(reviewedAgentReadinessReport.status) }}</em>
            </div>
          </div>
          <div class="readiness-actions">
            <button
              class="btn btn-primary"
              type="button"
              :disabled="readOnlyMode || simulatorRunning || agentReadinessReport.probes.length === 0"
              @click="runConsumptionSimulation"
            >
              {{ simulatorRunning ? 'Running Simulator…' : 'Run AI Simulator' }}
            </button>
            <button
              class="btn btn-secondary"
              type="button"
              :disabled="readOnlyMode || simulatorAssistantLoading"
              @click="analyzeSimulationWithAssistant"
            >
              {{ simulatorAssistantLoading ? 'Asking Assistant…' : 'Ask Assistant for Fix Plan' }}
            </button>
            <button class="btn btn-secondary" type="button" :disabled="readOnlyMode || handoffSaving" @click="saveReadinessHandoffArtifact">
              {{ handoffSaving ? 'Saving handoff…' : 'Save Handoff Artifact' }}
            </button>
            <button class="btn btn-secondary" type="button" @click="downloadReadinessHandoff">
              Download Report JSON
            </button>
          </div>
          <p v-if="simulatorError" class="error">{{ simulatorError }}</p>
          <p v-if="simulatorAssistantError" class="error">{{ simulatorAssistantError }}</p>
          <p v-if="simulatorSavedMessage" class="success-copy">{{ simulatorSavedMessage }}</p>
          <p v-if="handoffError" class="error">{{ handoffError }}</p>
          <p v-if="handoffSavedMessage" class="success-copy">{{ handoffSavedMessage }}</p>

          <div class="readiness-metrics">
            <div class="readiness-metric">
              <span>Blockers</span>
              <strong>{{ reviewedAgentReadinessReport.summary.blockers }}</strong>
            </div>
            <div class="readiness-metric">
              <span>Warnings</span>
              <strong>{{ reviewedAgentReadinessReport.summary.warnings }}</strong>
            </div>
            <div class="readiness-metric">
              <span>Reviewed App Glue</span>
              <strong>{{ reviewedAgentReadinessReport.summary.required_app_glue }}</strong>
            </div>
            <div class="readiness-metric">
              <span>Potential App-Owned Decisions</span>
              <strong>{{ appGlueCandidateFindings.length }}</strong>
            </div>
            <div class="readiness-metric">
              <span>Simulator Probes</span>
              <strong>{{ agentReadinessReport.summary.probes }}</strong>
            </div>
            <div class="readiness-metric">
              <span>Last Simulation</span>
              <strong v-if="simulatorReport">{{ simulatorReport.summary.passed }}/{{ simulatorReport.summary.total }}</strong>
              <strong v-else>Not run</strong>
            </div>
          </div>

          <div class="readiness-sections">
            <section v-if="simulatorReport" class="readiness-section readiness-section-wide">
              <h3>AI Simulation Result</h3>
              <div class="simulation-summary" :class="`status-${simulatorReport.status}`">
                <strong>{{ simulatorReport.status === 'pass' ? 'Pass' : 'Fail' }}</strong>
                <span>
                  {{ simulatorReport.summary.passed }} passed, {{ simulatorReport.summary.failed }} failed using
                  {{ simulatorReport.simulator_runtime.provider }}/{{ simulatorReport.simulator_runtime.model || 'default model' }}.
                </span>
              </div>
              <div class="readiness-list">
                <div v-for="item in simulatorReport.cases.slice(0, 10)" :key="item.probe_id" class="readiness-card">
                  <div class="readiness-card-header">
                    <strong>{{ item.probe_id }}</strong>
                    <span :class="['readiness-badge', item.status === 'pass' ? 'severity-info' : 'severity-blocker']">
                      {{ item.status }}
                    </span>
                  </div>
                  <p>
                    Expected {{ displayOutcome(item.expected_outcome) }},
                    simulated {{ displayOutcome(item.actual_outcome) }}
                    <template v-if="item.selected_capability_id"> via {{ item.selected_capability_id }}</template>.
                  </p>
                  <p class="readiness-recommendation">{{ item.rationale }}</p>
                  <div v-if="item.failures.length" class="readiness-meta">
                    <span v-for="failure in item.failures" :key="failure">{{ failure }}</span>
                  </div>
                  <div v-if="item.status === 'fail'" class="focused-assistant-actions">
                    <button
                      class="btn btn-compact btn-secondary"
                      type="button"
                      :disabled="readOnlyMode || focusedAssistantLoadingId !== null"
                      @click="analyzeSimulatorCaseWithAssistant(item)"
                    >
                      {{ focusedAssistantLoadingId === simulatorCaseFocusKey(item) ? 'Asking…' : 'Ask Assistant for This Fix' }}
                    </button>
                  </div>
                  <p v-if="focusedAssistantErrors[simulatorCaseFocusKey(item)]" class="error">
                    {{ focusedAssistantErrors[simulatorCaseFocusKey(item)] }}
                  </p>
                  <div
                    v-if="focusedAssistantAnalyses[simulatorCaseFocusKey(item)]"
                    class="focused-assistant-preview"
                  >
                    <strong>{{ focusedAssistantAnalyses[simulatorCaseFocusKey(item)].title }}</strong>
                    <p>{{ focusedAssistantAnalyses[simulatorCaseFocusKey(item)].focused_answer || focusedAssistantAnalyses[simulatorCaseFocusKey(item)].summary }}</p>
                    <ul>
                      <li
                        v-for="step in focusedAssistantAnalyses[simulatorCaseFocusKey(item)].next_steps"
                        :key="step"
                      >
                        {{ step }}
                      </li>
                    </ul>
                    <div class="assistant-step-actions">
                      <button
                        class="btn btn-compact btn-secondary"
                        type="button"
                        @click="router.push(`/design/projects/${project.id}/developer/definition`)"
                      >
                        Open Developer Definition
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            <section v-if="simulatorAssistantAnalysis" class="readiness-section readiness-section-wide">
              <h3>Assistant Simulator Feedback</h3>
              <div class="assistant-feedback">
                <strong>{{ simulatorAssistantAnalysis.title }}</strong>
                <p>{{ simulatorAssistantAnalysis.focused_answer || simulatorAssistantAnalysis.summary }}</p>
                <div v-if="reviewedAgentReadinessReport.status === 'blocked'" class="readiness-gate-warning">
                  <strong>Readiness gate is still blocked.</strong>
                  <p>
                    The simulator pass is regression evidence only. Resolve or explicitly review
                    {{ unreviewedReadinessFindings.length }} readiness finding{{ unreviewedReadinessFindings.length === 1 ? '' : 's' }}
                    before treating verification, generation, or publication as unblocked.
                  </p>
                </div>
                <div v-if="simulatorAssistantAnalysis.highlights?.length" class="assistant-feedback-grid">
                  <div>
                    <span>Highlights</span>
                    <ul>
                      <li v-for="item in simulatorAssistantAnalysis.highlights" :key="item">{{ item }}</li>
                    </ul>
                  </div>
                  <div>
                    <span>Next Steps</span>
                    <ul class="assistant-action-list">
                      <li v-for="item in simulatorAssistantNextStepRows" :key="item.step">
                        <p>{{ item.step }}</p>
                        <div v-if="item.actions.length" class="assistant-step-actions">
                          <button
                            v-for="action in item.actions"
                            :key="action.id"
                            class="btn btn-compact"
                            :class="action.tone === 'primary' ? 'btn-primary' : 'btn-secondary'"
                            type="button"
                            :disabled="readOnlyMode && !action.path"
                            @click="handleAssistantStepAction(action)"
                          >
                            {{ action.label }}
                          </button>
                        </div>
                      </li>
                    </ul>
                  </div>
                </div>
                <div v-if="simulatorAssistantAnalysis.watchouts?.length" class="readiness-meta">
                  <span v-for="item in simulatorAssistantAnalysis.watchouts" :key="item">{{ item }}</span>
                </div>
              </div>
            </section>

            <section class="readiness-section">
              <h3>Decisions Needed</h3>
              <p class="section-context-copy">
                These are unresolved review questions. Classify each as service-owned, app-owned, accepted limitation, or follow-up before generation or publication.
              </p>
              <div v-if="readinessFindingGroups.length" class="readiness-list">
                <div
                  v-for="group in readinessFindingGroups"
                  :key="group.id"
                  :class="[
                    'readiness-card',
                    `severity-card-${group.representative.severity}`,
                    readinessGroupReviewStateClass(group),
                  ]"
                >
                  <div class="readiness-card-header">
                    <strong>{{ group.representative.title }}</strong>
                    <div class="readiness-card-badges">
                      <span
                        v-if="findingGroupReview(group)"
                        :class="[
                          'readiness-badge',
                          'reviewed-decision-badge',
                          `decision-${findingGroupReview(group)!.decision}`,
                        ]"
                      >
                        Classified: {{ readinessFindingDecisionLabel(findingGroupReview(group)!.decision) }}
                      </span>
                      <span v-if="group.findings.length > 1" class="readiness-badge severity-info">
                        {{ group.findings.length }} related findings
                      </span>
                      <span :class="['readiness-badge', `severity-${group.representative.severity}`]">
                        {{ readinessSeverityLabel(group.representative.severity) }}
                      </span>
                    </div>
                  </div>
                  <p v-if="findingGroupReview(group)" class="readiness-resolution-effect">
                    {{ readinessReviewEffect(group.representative) }}
                  </p>
                  <div class="readiness-meta">
                    <span>Owner: {{ readinessOwnerLabel(group.representative.owner) }}</span>
                    <span v-if="group.affectedInputs.length">Input: {{ group.affectedInputs.join(', ') }}</span>
                    <span v-if="group.affectedCapabilities.length">{{ group.affectedCapabilities.length }} affected capability{{ group.affectedCapabilities.length === 1 ? '' : 'ies' }}</span>
                    <span v-if="findingGroupReview(group)?.review_method === 'automation_harness'" class="automation-review-chip">
                      Automation suggestion, needs human confirmation
                    </span>
                  </div>
                  <div
                    v-if="findingGroupReview(group)?.decision === 'follow_up'"
                    class="follow-up-work-card"
                  >
                    <strong>Still open. This review recorded the need for work; it did not perform the work.</strong>
                    <p>{{ readinessFollowUpOwner(group.representative) }}</p>
                    <p>{{ readinessFollowUpTarget(group.representative) }}</p>
                    <p>{{ readinessFollowUpDoneCondition(group.representative) }}</p>
                    <button
                      class="btn btn-compact btn-secondary"
                      type="button"
                      @click="router.push(readinessFollowUpRoute())"
                    >
                      Open Owning Editor
                    </button>
                  </div>
                  <component
                    :is="findingGroupReview(group) ? 'details' : 'div'"
                    class="readiness-card-body"
                    :class="{ collapsed: Boolean(findingGroupReview(group)) }"
                  >
                    <summary v-if="findingGroupReview(group)">Show details and edit review</summary>
                    <div class="readiness-task-box">
                      <div>
                        <span>Decision task</span>
                        <strong>{{ readinessDecisionTaskTitle(group.representative) }}</strong>
                        <p>{{ readinessFindingQuestion(group.representative) }}</p>
                      </div>
                      <div>
                        <span>Suggested resolution</span>
                        <p>{{ readinessDecisionTarget(group) }}</p>
                      </div>
                      <div>
                        <span>Done state</span>
                        <p>{{ readinessDecisionDoneState(group) }}</p>
                      </div>
                    </div>
                    <p>{{ group.representative.detail }}</p>
                    <p class="readiness-recommendation">{{ readinessFindingPlainAction(group.representative) }}</p>
                    <details v-if="group.affectedCapabilities.length" class="readiness-card-details">
                      <summary>Affected capabilities</summary>
                      <p>{{ group.affectedCapabilities.join(', ') }}</p>
                    </details>
                    <div
                      v-if="canApplyClarificationRemediation(group)"
                      class="inline-remediation-card"
                    >
                      <div>
                        <span>Recommended contract fix</span>
                        <strong>Define the runtime clarification prompt here.</strong>
                        <p>
                          This is a <b>service-contract update</b>, not app glue.
                          This updates the affected capability input named
                          <b>{{ plainInputName(group.affectedInputs[0]) }}</b>
                          across {{ group.affectedCapabilities.length }} capability{{ group.affectedCapabilities.length === 1 ? '' : 'ies' }}.
                        </p>
                      </div>
                      <div class="remediation-suggestion">
                        <span>Suggestion only</span>
                        <p>{{ defaultClarificationPromptForGroup(group) }}</p>
                        <button
                          class="btn btn-compact btn-secondary"
                          type="button"
                          :disabled="readOnlyMode"
                          @click="useSuggestedRemediationPrompt(group)"
                        >
                          Use This Suggestion
                        </button>
                      </div>
                      <label>
                        Prompt the runtime should return
                        <textarea
                          rows="2"
                          :value="remediationPromptForGroup(group)"
                          :disabled="readOnlyMode"
                          placeholder="Type the reviewed clarification prompt here. Nothing is written to the contract until this field has your reviewed text."
                          @input="onRemediationPromptInput(group, $event)"
                        />
                      </label>
                      <div class="assistant-step-actions">
                        <button
                          class="btn btn-compact btn-primary"
                          type="button"
                          :disabled="readOnlyMode || remediationApplyingId !== null"
                          @click="applyClarificationRemediation(group)"
                        >
                          {{ remediationApplyingId === group.id ? 'Applying…' : 'Apply to Developer Definition Draft' }}
                        </button>
                        <button
                          class="btn btn-compact btn-secondary"
                          type="button"
                          @click="router.push(`/design/projects/${project.id}/developer/capability-formalization`)"
                        >
                          Open Capability Editor
                        </button>
                      </div>
                      <p v-if="remediationMessages[group.id]" class="success">
                        {{ remediationMessages[group.id] }}
                      </p>
                      <p v-if="remediationErrors[group.id]" class="error">
                        {{ remediationErrors[group.id] }}
                      </p>
                    </div>
                    <div
                      v-if="canResolveDerivedTargetOwnership(group)"
                      class="ownership-resolution-card"
                    >
                      <div>
                        <span>Choose the resolution</span>
                        <strong>Who chooses the target group?</strong>
                        <p>
                          This is about requests like “top accounts” or “at-risk records.”
                          Studio needs to know whether the consuming app chooses that group before calling,
                          the service owns the selection flow, or vague requests should ask the user to clarify.
                        </p>
                      </div>
                      <div class="resolution-choice-grid">
                        <button
                          class="resolution-choice-card app-owned"
                          type="button"
                          :disabled="readOnlyMode"
                          @click="applyReadinessGroupDecision(group, 'explicit_app_glue', derivedTargetAppGlueNote(group))"
                        >
                          <strong>App owns target selection</strong>
                          <span>Saves required app-glue metadata. Generated service stays generic; app passes an explicit target group.</span>
                        </button>
                        <button
                          class="resolution-choice-card service-owned"
                          type="button"
                          :disabled="readOnlyMode"
                          @click="applyReadinessGroupDecision(group, 'follow_up', derivedTargetServiceFollowUpNote(group))"
                        >
                          <strong>Service should own it</strong>
                          <span>Records contract follow-up. Update Capability Formalization before generation/publication.</span>
                        </button>
                        <button
                          class="resolution-choice-card clarify-owned"
                          type="button"
                          :disabled="readOnlyMode"
                          @click="applyReadinessGroupDecision(group, 'acceptable_warning', derivedTargetClarifyOnlyNote(group))"
                        >
                          <strong>Clarify instead of guessing</strong>
                          <span>Records an accepted boundary: vague target requests must ask for an explicit target group.</span>
                        </button>
                      </div>
                    </div>
                    <div v-if="group.representative.severity !== 'info'" class="focused-assistant-actions">
                      <button
                        class="btn btn-compact btn-secondary"
                        type="button"
                        :disabled="readOnlyMode || focusedAssistantLoadingId !== null"
                        @click="analyzeReadinessFindingGroupWithAssistant(group)"
                      >
                        {{ focusedAssistantLoadingId === readinessFindingGroupFocusKey(group) ? 'Asking…' : 'Ask Assistant for Help' }}
                      </button>
                    </div>
                    <p v-if="focusedAssistantErrors[readinessFindingGroupFocusKey(group)]" class="error">
                      {{ focusedAssistantErrors[readinessFindingGroupFocusKey(group)] }}
                    </p>
                    <div
                      v-if="focusedAssistantAnalyses[readinessFindingGroupFocusKey(group)]"
                      class="focused-assistant-preview"
                    >
                      <strong>{{ focusedAssistantAnalyses[readinessFindingGroupFocusKey(group)].title }}</strong>
                      <p>{{ focusedAssistantAnalyses[readinessFindingGroupFocusKey(group)].focused_answer || focusedAssistantAnalyses[readinessFindingGroupFocusKey(group)].summary }}</p>
                      <div class="review-suggestion-preview">
                        <span>Suggested review decision</span>
                        <strong>{{ readinessFindingDecisionLabel(suggestedReadinessDecision(group.representative)) }}</strong>
                        <p>{{ suggestedReadinessGroupNote(group, focusedAssistantAnalyses[readinessFindingGroupFocusKey(group)]) }}</p>
                      </div>
                      <ul>
                        <li
                          v-for="step in focusedAssistantAnalyses[readinessFindingGroupFocusKey(group)].next_steps"
                          :key="step"
                        >
                          {{ step }}
                        </li>
                      </ul>
                      <div class="assistant-step-actions">
                        <button
                          v-if="canApplyClarificationRemediation(group)"
                          class="btn btn-compact btn-primary"
                          type="button"
                          :disabled="readOnlyMode || remediationApplyingId !== null"
                          @click="applyClarificationRemediation(group)"
                        >
                          {{ remediationApplyingId === group.id ? 'Applying…' : 'Apply Contract Fix Now' }}
                        </button>
                        <button
                          class="btn btn-compact btn-secondary"
                          type="button"
                          :disabled="readOnlyMode"
                          @click="applySuggestedReadinessGroupReview(group)"
                        >
                          Save Review Only
                        </button>
                        <button
                          class="btn btn-compact btn-secondary"
                          type="button"
                          @click="router.push(`/design/projects/${project.id}/developer/capability-formalization`)"
                        >
                          Open Capability Editor
                        </button>
                      </div>
                    </div>
                    <div class="readiness-review">
                      <label>
                        Review decision
                        <select
                          :value="findingGroupReview(group)?.decision ?? ''"
                          :disabled="readOnlyMode"
                          @change="onFindingGroupDecisionChange(group, $event)"
                        >
                          <option value="">Unreviewed</option>
                          <option v-for="option in readinessReviewDecisionOptions" :key="option.value" :value="option.value">
                            {{ option.label }}
                          </option>
                        </select>
                      </label>
                      <label>
                        Review note
                        <textarea
                          rows="3"
                          :value="findingGroupReview(group)?.note ?? ''"
                          :disabled="readOnlyMode"
                          placeholder="Record the reviewed decision in plain language. Example: the service owns the flow, the app owns target selection, this is an accepted limitation, or follow-up is required."
                          @input="onFindingGroupNoteInput(group, $event)"
                        />
                      </label>
                    </div>
                  </component>
                </div>
              </div>
              <p v-else class="empty-note">
                No readiness findings. Keep simulator probes as regression coverage before publishing.
              </p>
              <details v-if="informationalReadinessFindings.length" class="informational-readiness-notes">
                <summary>{{ informationalReadinessFindings.length }} informational note{{ informationalReadinessFindings.length === 1 ? '' : 's' }}</summary>
                <div class="readiness-list">
                  <div
                    v-for="finding in informationalReadinessFindings"
                    :key="finding.id"
                    class="readiness-card readiness-card-info-only severity-card-info"
                  >
                    <div class="readiness-card-header">
                      <strong>{{ finding.title }}</strong>
                      <span class="readiness-badge severity-info">Info</span>
                    </div>
                    <p>{{ finding.detail }}</p>
                    <p class="readiness-recommendation">{{ readinessFindingPlainAction(finding) }}</p>
                    <div class="readiness-meta">
                      <span>Owner: {{ readinessOwnerLabel(finding.owner) }}</span>
                      <span v-if="finding.input_name">Input: {{ finding.input_name }}</span>
                      <span v-if="finding.capability_id">{{ finding.capability_id }}</span>
                    </div>
                  </div>
                </div>
              </details>
            </section>

            <section class="readiness-section">
              <h3>App-Owned Work</h3>
              <p class="section-context-copy">
                These are reviewed decisions where the consuming app owns behavior outside generic ANIP invocation. This is the handoff list developers should implement in the app or app profile.
              </p>
              <div v-if="reviewedAgentReadinessReport.required_app_glue.length" class="readiness-list">
                <div v-for="glue in reviewedAgentReadinessReport.required_app_glue" :key="glue.id" class="readiness-card">
                  <span class="review-state-chip">Reviewed app-owned work</span>
                  <strong>{{ glue.title }}</strong>
                  <p>{{ glue.detail }}</p>
                  <p class="readiness-recommendation">{{ glue.recommendation }}</p>
                  <div class="readiness-meta">
                    <span>{{ displayOutcome(glue.category) }}</span>
                    <span v-if="glue.capability_id">{{ glue.capability_id }}</span>
                  </div>
                </div>
              </div>
              <p v-else class="empty-note">
                No reviewed app-owned work yet. Potential app-owned decisions remain under Decisions Needed until PM/dev explicitly classifies them.
              </p>
            </section>

            <section class="readiness-section readiness-section-wide">
              <h3>Deterministic Simulator Probes</h3>
              <div v-if="agentReadinessReport.probes.length" class="probe-grid">
                <div v-for="probe in agentReadinessReport.probes.slice(0, 10)" :key="probe.id" class="probe-card">
                  <div class="probe-card-header">
                    <strong>{{ probe.label }}</strong>
                    <span>{{ displayOutcome(probe.expected_outcome) }}</span>
                  </div>
                  <p>{{ probe.prompt }}</p>
                  <small>{{ probe.rationale }}</small>
                </div>
              </div>
              <p v-else class="empty-note">
                No simulator probes generated yet. Add capabilities, question-family bindings, or business-effect boundaries to make early validation meaningful.
              </p>
            </section>
          </div>
        </article>

        <article v-if="activeCoverageLane === 'consumability'" class="panel panel-full consumability-review-panel">
          <div class="panel-header">
            <div>
              <h2>Reviewed Agent Consumability</h2>
              <p class="fit-intro">
                Manual, deterministic intent and app-glue metadata. AI assistant drafts can populate these fields later, but publishing uses only reviewed values saved here.
              </p>
              <p class="fit-intro why-copy">
                Why this matters: package-specific guidance belongs here as reviewed design intent, not as hidden rules in a generic agent runtime.
              </p>
            </div>
            <span class="reviewed-count" :class="{ empty: Object.keys(agentConsumabilityReviews).length === 0 }">
              {{ Object.keys(agentConsumabilityReviews).length }} reviewed
            </span>
          </div>
          <div v-if="consumabilityActionItems.length" class="consumability-grid">
            <div
              v-for="item in consumabilityActionItems"
              :key="item.capability.capability_id"
              class="consumability-card"
              :class="{
                'severity-card-blocker': item.findingSeverity === 'blocker',
                'severity-card-warning': item.findingSeverity === 'warning',
                needsReview: item.needsReview && item.findingCount === 0 && !item.review,
                reviewed: !!item.review,
              }"
            >
              <div class="consumability-card-header">
                <div>
                  <strong>{{ item.capability.capability_id }}</strong>
                  <p>{{ displayConsumabilityCapabilitySummary(item.capability, item.metadata) }}</p>
                  <p v-if="item.metadata?.business_effects" class="effect-summary">
                    <span :title="technicalHoverLabel([...(item.metadata.business_effects.produces ?? []), ...(item.metadata.business_effects.does_not_produce ?? [])].join(', '))">Produces: {{ displayEffectList(item.metadata.business_effects.produces) }}</span>
                    <span v-if="item.metadata.business_effects.does_not_produce?.length">
                      · Does not produce: {{ displayEffectList(item.metadata.business_effects.does_not_produce) }}
                    </span>
                    <small v-if="showTechnicalIdentifiers">{{ displayTechnicalEffects([...(item.metadata.business_effects.produces ?? []), ...(item.metadata.business_effects.does_not_produce ?? [])]) }}</small>
                  </p>
                </div>
                <span v-if="item.review" class="readiness-badge severity-info">Reviewed</span>
                <span v-else-if="item.findingSeverity" :class="['readiness-badge', `severity-${item.findingSeverity}`]">
                  {{ readinessSeverityLabel(item.findingSeverity) }}
                </span>
                <span v-else-if="item.needsReview" class="readiness-badge severity-warning">Needs review</span>
              </div>

              <div class="app-profile-review-body">
                <div class="app-profile-summary">
                  <span>{{ item.review ? 'Reviewed app profile' : 'Suggested app profile' }}</span>
                  <p>{{ appProfileDecisionSummary(item) }}</p>
                </div>
                <div v-if="appProfileHumanGuidance(item).length" class="app-profile-guidance-grid">
                  <div
                    v-for="guidance in appProfileHumanGuidance(item)"
                    :key="`${item.capability.capability_id}-${guidance.title}`"
                    :class="['app-profile-guidance-card', `tone-${guidance.tone}`]"
                  >
                    <strong>{{ guidance.title }}</strong>
                    <p>{{ guidance.detail }}</p>
                  </div>
                </div>
                <section class="semantic-rules-panel">
                  <div class="semantic-rules-header">
                    <div>
                      <h3>Semantic Interpretation Rules</h3>
                      <p>
                        Use these when business wording is valid but easy for an agent to misread. Studio packages the reviewed rule as app-consumption guidance; it does not change the ANIP service contract.
                      </p>
                    </div>
                    <span class="readiness-badge severity-info">
                      {{ businessLanguageRulesForItem(item).length }} rule{{ businessLanguageRulesForItem(item).length === 1 ? '' : 's' }}
                    </span>
                  </div>
                  <div v-if="businessLanguageRulesForItem(item).length" class="semantic-rule-list">
                    <details
                      v-for="(rule, ruleIndex) in businessLanguageRulesForItem(item)"
                      :key="`${item.capability.capability_id}:${rule.id}`"
                      class="semantic-rule-card"
                    >
                      <summary>
                        <span>{{ rule.meaning }}</span>
                        <small>{{ semanticActionLabel(rule.agent_action) }} · {{ semanticRuleSummary(rule) }}</small>
                      </summary>
                      <div class="semantic-rule-editor">
                        <label>
                          Business meaning
                          <textarea
                            rows="2"
                            :value="rule.meaning"
                            :disabled="readOnlyMode"
                            @input="updateSemanticRule(item.capability, ruleIndex, { meaning: ($event.target as HTMLTextAreaElement).value })"
                          />
                        </label>
                        <label>
                          Runtime interpretation
                          <textarea
                            rows="2"
                            :value="rule.interpretation"
                            :disabled="readOnlyMode"
                            @input="updateSemanticRule(item.capability, ruleIndex, { interpretation: ($event.target as HTMLTextAreaElement).value })"
                          />
                        </label>
                        <label>
                          Runtime should
                          <select
                            :value="rule.agent_action ?? 'treat_as_supported'"
                            :disabled="readOnlyMode"
                            @change="updateSemanticRule(item.capability, ruleIndex, { agent_action: ($event.target as HTMLSelectElement).value as AgentConsumabilityBusinessLanguageRule['agent_action'] })"
                          >
                            <option value="treat_as_supported">Treat as supported intent</option>
                            <option value="treat_as_purpose">Treat as purpose/framing</option>
                            <option value="prefer_capability">Prefer this capability</option>
                            <option value="clarify">Ask for clarification</option>
                          </select>
                        </label>
                        <div class="semantic-rule-grid">
                          <label>
                            Must include
                            <input
                              :value="displayTerms(rule.applies_when.all_terms)"
                              :disabled="readOnlyMode"
                              placeholder="risk, concentration"
                              @input="updateSemanticRule(item.capability, ruleIndex, { applies_when: { all_terms: commaTerms(($event.target as HTMLInputElement).value) } })"
                            />
                          </label>
                          <label>
                            May include
                            <input
                              :value="displayTerms(rule.applies_when.any_terms)"
                              :disabled="readOnlyMode"
                              placeholder="account executive, AE, sales"
                              @input="updateSemanticRule(item.capability, ruleIndex, { applies_when: { any_terms: commaTerms(($event.target as HTMLInputElement).value) } })"
                            />
                          </label>
                          <label>
                            But not when user says
                            <input
                              :value="displayTerms(rule.applies_when.exclude_terms)"
                              :disabled="readOnlyMode"
                              placeholder="draft, send, export"
                              @input="updateSemanticRule(item.capability, ruleIndex, { applies_when: { exclude_terms: commaTerms(($event.target as HTMLInputElement).value) } })"
                            />
                          </label>
                        </div>
                        <label>
                          Suppress unsupported outcomes
                          <input
                            :value="displayTerms(rule.suppress_unsupported_effects)"
                            :disabled="readOnlyMode"
                            placeholder="raw_data_export, external_dispatch"
                            @input="updateSemanticRule(item.capability, ruleIndex, { suppress_unsupported_effects: commaTerms(($event.target as HTMLInputElement).value) })"
                          />
                        </label>
                        <div class="assistant-step-actions">
                          <button class="btn btn-compact btn-danger" type="button" :disabled="readOnlyMode" @click="removeSemanticRule(item.capability, ruleIndex)">
                            Remove Rule
                          </button>
                        </div>
                      </div>
                    </details>
                  </div>
                  <details class="semantic-rule-card add-rule-card">
                    <summary>Add reviewed semantic rule</summary>
                    <div class="semantic-rule-editor">
                      <label>
                        Business meaning
                        <textarea
                          rows="2"
                          :value="semanticRuleDraft(item.capability).meaning"
                          :disabled="readOnlyMode"
                          placeholder="Example: account-executive follow-up means routing destination, not outreach drafting."
                          @input="updateSemanticRuleDraft(item.capability, 'meaning', ($event.target as HTMLTextAreaElement).value)"
                        />
                      </label>
                      <label>
                        Runtime interpretation
                        <textarea
                          rows="2"
                          :value="semanticRuleDraft(item.capability).interpretation"
                          :disabled="readOnlyMode"
                          placeholder="Example: keep this as routing/approval-preview intent unless the user asks to draft, write, send, or create content."
                          @input="updateSemanticRuleDraft(item.capability, 'interpretation', ($event.target as HTMLTextAreaElement).value)"
                        />
                      </label>
                      <label>
                        Runtime should
                        <select
                          :value="semanticRuleDraft(item.capability).agent_action"
                          :disabled="readOnlyMode"
                          @change="updateSemanticRuleDraft(item.capability, 'agent_action', ($event.target as HTMLSelectElement).value)"
                        >
                          <option value="treat_as_supported">Treat as supported intent</option>
                          <option value="treat_as_purpose">Treat as purpose/framing</option>
                          <option value="prefer_capability">Prefer this capability</option>
                          <option value="clarify">Ask for clarification</option>
                        </select>
                      </label>
                      <div class="semantic-rule-grid">
                        <label>
                          Must include
                          <input
                            :value="semanticRuleDraft(item.capability).all_terms"
                            :disabled="readOnlyMode"
                            placeholder="risk"
                            @input="updateSemanticRuleDraft(item.capability, 'all_terms', ($event.target as HTMLInputElement).value)"
                          />
                        </label>
                        <label>
                          May include
                          <input
                            :value="semanticRuleDraft(item.capability).any_terms"
                            :disabled="readOnlyMode"
                            placeholder="concentration, concentrated"
                            @input="updateSemanticRuleDraft(item.capability, 'any_terms', ($event.target as HTMLInputElement).value)"
                          />
                        </label>
                        <label>
                          But not when user says
                          <input
                            :value="semanticRuleDraft(item.capability).exclude_terms"
                            :disabled="readOnlyMode"
                            placeholder="raw, export, download"
                            @input="updateSemanticRuleDraft(item.capability, 'exclude_terms', ($event.target as HTMLInputElement).value)"
                          />
                        </label>
                      </div>
                      <label>
                        Suppress unsupported outcomes
                        <input
                          :value="semanticRuleDraft(item.capability).suppress_unsupported_effects"
                          :disabled="readOnlyMode"
                          placeholder="Optional: raw_data_export"
                          @input="updateSemanticRuleDraft(item.capability, 'suppress_unsupported_effects', ($event.target as HTMLInputElement).value)"
                        />
                      </label>
                      <p v-if="consumabilityRuleErrors[`${item.capability.capability_id}:business_language_rules`]" class="error">
                        {{ consumabilityRuleErrors[`${item.capability.capability_id}:business_language_rules`] }}
                      </p>
                      <div class="assistant-step-actions">
                        <button class="btn btn-compact btn-primary" type="button" :disabled="readOnlyMode" @click="saveSemanticRuleDraft(item.capability)">
                          Save Semantic Rule
                        </button>
                      </div>
                    </div>
                  </details>
                </section>
                <div class="assistant-step-actions">
                  <button
                    class="btn btn-compact btn-primary"
                    type="button"
                    :disabled="readOnlyMode"
                    @click="acceptSuggestedAppProfile(item.capability)"
                  >
                    {{ item.review ? 'Refresh Reviewed App Profile' : 'Accept Suggested App Profile' }}
                  </button>
                  <button
                    class="btn btn-compact btn-secondary"
                    type="button"
                    @click="router.push(`/design/projects/${project.id}/developer/app-glue`)"
                  >
                    Keep Reviewing
                  </button>
                </div>
                <details class="technical-metadata-details">
                  <summary>Advanced metadata editor</summary>
                  <div class="consumability-fields">
                    <label>
                      Intent category
                      <input
                        :value="item.review?.intent_category ?? ''"
                        :disabled="readOnlyMode"
                        :placeholder="suggestedConsumabilityIntentCategory(item.capability, item.metadata)"
                        @input="onConsumabilityFieldInput(item.capability, 'intent_category', $event)"
                      />
                      <span v-if="!item.review" class="field-suggestion">
                        Suggested: {{ suggestedConsumabilityIntentCategory(item.capability, item.metadata) }}
                      </span>
                    </label>
                    <label>
                      Intent summary
                      <textarea
                        rows="2"
                        :value="item.review?.intent_summary ?? ''"
                        :disabled="readOnlyMode"
                        :placeholder="suggestedConsumabilityIntentSummary(item.capability, item.metadata)"
                        @input="onConsumabilityFieldInput(item.capability, 'intent_summary', $event)"
                      />
                    </label>
                    <label class="checkbox-field">
                      <input
                        type="checkbox"
                        :checked="item.review?.app_glue_required ?? false"
                        :disabled="readOnlyMode"
                        @change="onAppGlueRequiredChange(item.capability, $event)"
                      />
                      <span>Requires explicit app-owned behavior</span>
                    </label>
                    <label>
                      App-owned reason
                      <textarea
                        rows="2"
                        :value="item.review?.app_glue_reason ?? ''"
                        :disabled="readOnlyMode"
                        placeholder="What the consuming app must decide or render, without duplicating ANIP invocation mechanics."
                        @input="onConsumabilityFieldInput(item.capability, 'app_glue_reason', $event)"
                      />
                    </label>
                    <label>
                      Intent rules JSON
                      <textarea
                        rows="6"
                        :value="item.review ? formatIntentRules(item.review.intent_rules) : ''"
                        :disabled="readOnlyMode"
                        @input="onIntentRulesInput(item.capability, $event)"
                      />
                    </label>
                    <label>
                      Input meanings JSON
                      <textarea
                        rows="5"
                        :value="item.review ? formatConsumabilityJson(item.review.input_meanings, {}) : ''"
                        :disabled="readOnlyMode"
                        @input="onConsumabilityJsonInput(item.capability, 'input_meanings', $event)"
                      />
                    </label>
                    <label>
                      App boundaries JSON
                      <textarea
                        rows="6"
                        :value="item.review ? formatConsumabilityJson(item.review.app_boundaries, {}) : ''"
                        :disabled="readOnlyMode"
                        @input="onConsumabilityJsonInput(item.capability, 'app_boundaries', $event)"
                      />
                      <span class="field-suggestion">
                        Advanced view saves canonical metadata for generator/verifier compatibility.
                      </span>
                    </label>
                    <label>
                      Selection hints JSON
                      <textarea
                        rows="5"
                        :value="item.review ? formatConsumabilityJson(item.review.selection_hints, []) : ''"
                        :disabled="readOnlyMode"
                        @input="onConsumabilityJsonInput(item.capability, 'selection_hints', $event)"
                      />
                      <span class="field-suggestion">
                        Optional app-layer routing hints. Keep this compact; do not use it as an endless alias list.
                      </span>
                    </label>
                    <p v-if="consumabilityRuleErrors[item.capability.capability_id]" class="error">
                      {{ consumabilityRuleErrors[item.capability.capability_id] }}
                    </p>
                    <p
                      v-for="field in ['input_meanings', 'app_boundaries', 'selection_hints']"
                      :key="field"
                      v-show="consumabilityRuleErrors[`${item.capability.capability_id}:${field}`]"
                      class="error"
                    >
                      {{ consumabilityRuleErrors[`${item.capability.capability_id}:${field}`] }}
                    </p>
                  </div>
                </details>
              </div>
            </div>
          </div>
          <p v-else class="empty-note">
            No app-profile reviews are required right now. Save Coverage Mapping when readiness decisions are complete.
          </p>
          <details v-if="consumabilityOtherItems.length" class="technical-metadata-details other-capabilities-details">
            <summary>{{ consumabilityOtherItems.length }} other capability profiles</summary>
            <p class="section-context-copy">
              These capabilities have generated consumability metadata but no current app-glue decision. Review them only if the app needs package-specific presentation or routing behavior.
            </p>
            <div class="readiness-meta">
              <span v-for="item in consumabilityOtherItems.slice(0, 12)" :key="item.capability.capability_id">
                {{ item.capability.capability_id }}
              </span>
            </div>
          </details>
          <p class="empty-note">
            Save Coverage Mapping to persist these reviewed hints. Package export will include them in metadata/agent-consumability.json.
          </p>
        </article>

        <template v-if="activeCoverageLane === 'coverage'">
        <article v-for="group in groupedCoverage" :key="group.key" class="panel panel-full coverage-group-panel">
          <div class="panel-header">
            <h2>{{ group.title }}</h2>
          </div>
          <div v-if="group.key === 'product-design'" class="foundation-group-list">
            <details
              v-for="foundation in productFoundationGroups"
              :key="`${foundation.key}:${foundationSummary(foundation.items).missing}:${foundationSummary(foundation.items).partial}:${foundation.items.length}`"
              class="foundation-group"
              :open="foundationOpenByDefault(foundation.items)"
            >
              <summary class="foundation-group-header">
                <div class="foundation-group-title">
                  <h3>{{ foundation.title }}</h3>
                  <span class="foundation-count">{{ foundation.items.length }} item{{ foundation.items.length === 1 ? '' : 's' }}</span>
                </div>
                <div class="foundation-summary-actions">
                  <div class="foundation-summary-badges">
                    <span class="foundation-summary-badge ok">Addressed {{ foundationSummary(foundation.items).addressed }}</span>
                    <span v-if="foundationSummary(foundation.items).partial" class="foundation-summary-badge warn">Partial {{ foundationSummary(foundation.items).partial }}</span>
                    <span v-if="foundationSummary(foundation.items).missing" class="foundation-summary-badge danger">Missing {{ foundationSummary(foundation.items).missing }}</span>
                  </div>
                  <span v-if="coverageAttentionPreview(foundation.items)" class="foundation-preview">
                    {{ coverageAttentionPreview(foundation.items) }}
                  </span>
                  <span class="foundation-toggle-hint">View coverage items</span>
                </div>
              </summary>
              <div class="coverage-list foundation-group-body">
                <div v-for="item in foundation.items" :key="item.id" class="coverage-card">
                  <div class="coverage-card-header">
                    <div>
                      <div class="coverage-section">{{ item.section }}</div>
                      <h3>{{ item.label }}</h3>
                      <p class="coverage-detail">{{ item.detail }}</p>
                    </div>
                    <label class="field compact-field">
                      <span>Status</span>
                      <select
                        :class="['select', 'coverage-status-select', `status-${item.status}`]"
                        :value="item.status"
                        :disabled="readOnlyMode || item.mapping_mode === 'automatic'"
                        @change="updateCoverageStatus(item.id, ($event.target as HTMLSelectElement).value as CoverageStatus)"
                      >
                        <option v-for="option in statusOptions" :key="option.value" :value="option.value">
                          {{ option.label }}
                        </option>
                      </select>
                    </label>
                  </div>

                  <div class="surface-section">
                    <span class="surface-label">Formalized In</span>
                    <div
                      v-if="item.id.startsWith('shape:coordination:')"
                      class="coverage-resolution-card"
                    >
                      <strong>Coordination decision needed</strong>
                      <p>
                        Decide how this service-to-service relationship is represented:
                        as contract-owned capability behavior, as consuming-app orchestration,
                        as follow-up work, or as out of scope for this package.
                      </p>
                      <div class="coordination-choice-grid">
                        <article
                          v-for="choice in coordinationResolutionChoices(item, project?.id)"
                          :key="choice.id"
                          class="coordination-choice-card"
                        >
                          <strong>{{ choice.label }}</strong>
                          <span>{{ choice.plain_language }}</span>
                          <details class="coordination-patch-preview">
                            <summary>Preview draft change</summary>
                            <div class="coordination-patch-body">
                              <span>{{ choice.patch_preview.target_artifact }}</span>
                              <strong>{{ choice.patch_preview.title }}</strong>
                              <ul>
                                <li v-for="change in choice.patch_preview.changes" :key="change">{{ change }}</li>
                              </ul>
                              <em>{{ choice.patch_preview.requires_review ? 'Requires review before generation.' : 'Safe traceability update.' }}</em>
                            </div>
                          </details>
                          <div class="coordination-choice-actions">
                            <button
                              class="btn btn-compact btn-primary"
                              type="button"
                              :disabled="readOnlyMode || coverageResolutionApplyingId === `${item.id}:${choice.id}`"
                              @click="applyCoordinationResolution(item, choice.id)"
                            >
                              Apply Draft
                            </button>
                            <button
                              v-if="choice.next_path"
                              class="btn btn-compact btn-secondary"
                              type="button"
                              @click="router.push(choice.next_path)"
                            >
                              Open Review Page
                            </button>
                          </div>
                        </article>
                      </div>
                      <p v-if="coverageResolutionMessages[item.id]" class="surface-note success-note">
                        {{ coverageResolutionMessages[item.id] }}
                      </p>
                    </div>
                    <p class="surface-note">
                      These sections are defined across the Developer Design
                      <button class="inline-link" type="button" @click="router.push(`/design/projects/${project.id}/developer/definition`)">
                        formalization pages
                      </button>
                      and compiled into the Developer Definition.
                    </p>
                    <p v-if="item.mapping_mode === 'automatic'" class="surface-note">
                      {{ item.mapping_note || 'Mapped automatically from the locked baseline and developer definition contract.' }}
                    </p>
                    <div v-if="item.mapping_mode !== 'automatic'" class="surface-chips">
                      <button
                        v-for="surface in linkableSurfaces"
                        :key="surface.value"
                        class="surface-chip"
                        :class="{ active: item.linked_surfaces.includes(surface.value) }"
                        type="button"
                        :disabled="readOnlyMode"
                        @click="selectLinkedSurface(item.id, surface.value)"
                      >
                        {{ surface.label }}
                      </button>
                    </div>
                    <p v-if="item.mapping_target_label" class="target-surface-line">
                      <span class="target-surface-label">Target Surface</span>
                      <strong>{{ item.mapping_target_label }}</strong>
                    </p>
                    <p v-if="item.mapping_mode === 'automatic' && item.mapping_target_key" class="surface-note">
                      <button class="inline-link" type="button" @click="router.push(developerDefinitionTargetRoute(project.id, item.mapping_target_key))">
                        Open defining field
                      </button>
                    </p>
                    <p v-else-if="item.linked_surfaces[0]" class="surface-note">
                      <button class="inline-link" type="button" @click="router.push(developerDefinitionTargetRoute(project.id, `developer_definition.contracts.${item.linked_surfaces[0]}`))">
                        Open selected contract section
                      </button>
                    </p>
                  </div>

                  <label v-if="item.mapping_mode !== 'automatic'" class="field">
                    <span>Developer rationale</span>
                    <textarea
                      class="textarea"
                      rows="2"
                      :value="item.rationale"
                      :disabled="readOnlyMode"
                      @input="updateCoverageRationale(item.id, ($event.target as HTMLTextAreaElement).value)"
                      placeholder="Explain how this Product Design item is covered in Developer Design or why it is deferred."
                    />
                  </label>
                </div>
              </div>
            </details>
          </div>
          <details
            v-else
            :key="`${group.key}:${coverageGroupSummary(group.items).missing}:${coverageGroupSummary(group.items).partial}:${group.items.length}`"
            class="coverage-subgroup"
            :open="coverageGroupOpenByDefault(group.items)"
          >
            <summary class="coverage-subgroup-header">
              <div class="coverage-subgroup-title">
                <h3>{{ group.title }}</h3>
                <span class="foundation-count">{{ group.items.length }} item{{ group.items.length === 1 ? '' : 's' }}</span>
              </div>
              <div class="foundation-summary-actions">
                <div class="foundation-summary-badges">
                  <span class="foundation-summary-badge ok">Addressed {{ coverageGroupSummary(group.items).addressed }}</span>
                  <span v-if="coverageGroupSummary(group.items).partial" class="foundation-summary-badge warn">Partial {{ coverageGroupSummary(group.items).partial }}</span>
                  <span v-if="coverageGroupSummary(group.items).missing" class="foundation-summary-badge danger">Missing {{ coverageGroupSummary(group.items).missing }}</span>
                </div>
                <span v-if="coverageAttentionPreview(group.items)" class="foundation-preview">
                  {{ coverageAttentionPreview(group.items) }}
                </span>
                <span class="foundation-toggle-hint">View coverage items</span>
              </div>
            </summary>
            <div class="coverage-list coverage-subgroup-body">
              <div v-for="item in group.items" :key="item.id" class="coverage-card">
                <div class="coverage-card-header">
                  <div>
                    <div class="coverage-section">{{ item.section }}</div>
                    <h3>{{ item.label }}</h3>
                    <p class="coverage-detail">{{ item.detail }}</p>
                  </div>
                  <label class="field compact-field">
                    <span>Status</span>
                    <select
                      :class="['select', 'coverage-status-select', `status-${item.status}`]"
                      :value="item.status"
                      :disabled="readOnlyMode || item.mapping_mode === 'automatic'"
                      @change="updateCoverageStatus(item.id, ($event.target as HTMLSelectElement).value as CoverageStatus)"
                    >
                      <option v-for="option in statusOptions" :key="option.value" :value="option.value">
                        {{ option.label }}
                      </option>
                    </select>
                  </label>
                </div>

                <div class="surface-section">
                  <span class="surface-label">Formalized In</span>
                  <div
                    v-if="item.id.startsWith('shape:coordination:')"
                    class="coverage-resolution-card"
                  >
                    <strong>Coordination decision needed</strong>
                    <p>
                      Decide how this service-to-service relationship is represented:
                      as contract-owned capability behavior, as consuming-app orchestration,
                      as follow-up work, or as out of scope for this package.
                    </p>
                    <div class="coordination-choice-grid">
                      <article
                        v-for="choice in coordinationResolutionChoices(item, project?.id)"
                        :key="choice.id"
                        class="coordination-choice-card"
                      >
                        <strong>{{ choice.label }}</strong>
                        <span>{{ choice.plain_language }}</span>
                        <details class="coordination-patch-preview">
                          <summary>Preview draft change</summary>
                          <div class="coordination-patch-body">
                            <span>{{ choice.patch_preview.target_artifact }}</span>
                            <strong>{{ choice.patch_preview.title }}</strong>
                            <ul>
                              <li v-for="change in choice.patch_preview.changes" :key="change">{{ change }}</li>
                            </ul>
                            <em>{{ choice.patch_preview.requires_review ? 'Requires review before generation.' : 'Safe traceability update.' }}</em>
                          </div>
                        </details>
                        <div class="coordination-choice-actions">
                          <button
                            class="btn btn-compact btn-primary"
                            type="button"
                            :disabled="readOnlyMode || coverageResolutionApplyingId === `${item.id}:${choice.id}`"
                            @click="applyCoordinationResolution(item, choice.id)"
                          >
                            Apply Draft
                          </button>
                          <button
                            v-if="choice.next_path"
                            class="btn btn-compact btn-secondary"
                            type="button"
                            @click="router.push(choice.next_path)"
                          >
                            Open Review Page
                          </button>
                        </div>
                      </article>
                    </div>
                    <p v-if="coverageResolutionMessages[item.id]" class="surface-note success-note">
                      {{ coverageResolutionMessages[item.id] }}
                    </p>
                  </div>
                  <p class="surface-note">
                    These sections are defined across the Developer Design
                    <button class="inline-link" type="button" @click="router.push(`/design/projects/${project.id}/developer/definition`)">
                      formalization pages
                    </button>
                    and compiled into the Developer Definition.
                  </p>
                  <p v-if="item.mapping_mode === 'automatic'" class="surface-note">
                    {{ item.mapping_note || 'Mapped automatically from the locked baseline and developer definition contract.' }}
                  </p>
                  <div v-if="item.mapping_mode !== 'automatic'" class="surface-chips">
                    <button
                      v-for="surface in linkableSurfaces"
                      :key="surface.value"
                      class="surface-chip"
                      :class="{ active: item.linked_surfaces.includes(surface.value) }"
                      type="button"
                      :disabled="readOnlyMode"
                      @click="selectLinkedSurface(item.id, surface.value)"
                    >
                      {{ surface.label }}
                    </button>
                  </div>
                  <p v-if="item.mapping_target_label" class="target-surface-line">
                    <span class="target-surface-label">Target Surface</span>
                    <strong>{{ item.mapping_target_label }}</strong>
                  </p>
                  <p v-if="item.mapping_mode === 'automatic' && item.mapping_target_key" class="surface-note">
                    <button class="inline-link" type="button" @click="router.push(developerDefinitionTargetRoute(project.id, item.mapping_target_key))">
                      Open defining field
                    </button>
                  </p>
                  <p v-else-if="item.linked_surfaces[0]" class="surface-note">
                    <button class="inline-link" type="button" @click="router.push(developerDefinitionTargetRoute(project.id, `developer_definition.contracts.${item.linked_surfaces[0]}`))">
                      Open selected contract section
                    </button>
                  </p>
                </div>

                <label v-if="item.mapping_mode !== 'automatic'" class="field">
                  <span>Developer rationale</span>
                  <textarea
                    class="textarea"
                    rows="2"
                    :value="item.rationale"
                    :disabled="readOnlyMode"
                    @input="updateCoverageRationale(item.id, ($event.target as HTMLTextAreaElement).value)"
                    placeholder="Explain how this Product Design item is covered in Developer Design or why it is deferred."
                  />
                </label>
              </div>
            </div>
          </details>
        </article>
        </template>

        <template v-if="activeCoverageLane === 'completion'">
          <article class="panel panel-full developer-completion-panel">
            <div class="panel-header">
              <h2>Developer Completion</h2>
            </div>
            <div class="completion-grid">
              <label class="field">
                <span>Developer status</span>
                <select v-model="draft.developer_status" class="select" :disabled="readOnlyMode">
                  <option v-for="option in developerStateOptions" :key="option.value" :value="option.value">
                    {{ option.label }}
                  </option>
                </select>
              </label>
              <label class="field field-wide">
                <span>Developer note</span>
                <textarea
                  v-model="draft.developer_note"
                  class="textarea"
                  rows="3"
                  :disabled="readOnlyMode"
                  placeholder="Explain how Developer Design covers the locked Product Design baseline and what still needs work."
                />
              </label>
            </div>
          </article>

          <article class="panel panel-full persisted-record-panel">
            <div class="panel-header">
              <h2>Persisted Record</h2>
            </div>
            <p class="panel-copy">
              Saving this page freezes a project-scoped traceability record for the current locked baseline. PM review and implementation verification read the same record.
            </p>
            <p v-if="saveError" class="error">{{ saveError }}</p>
            <div class="persisted-actions">
              <button class="btn btn-primary" :disabled="readOnlyMode || saving" @click="saveCoverage">
                {{ saving ? 'Saving…' : 'Save Coverage Mapping' }}
              </button>
            </div>
          </article>
        </template>
      </section>
    </template>
  </div>
</template>

<style scoped>
.developer-coverage {
  width: 100%;
  max-width: none;
  padding: 2rem;
}

.page-header {
  margin-bottom: 1.5rem;
  max-width: 1040px;
}

.back-link {
  border: none;
  background: transparent;
  color: var(--accent);
  font-size: 13px;
  cursor: pointer;
  padding: 0;
  margin-bottom: 0.6rem;
}

.page-kicker,
.summary-label,
.metric-label,
.coverage-section,
.surface-label {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 12px;
  color: var(--text-secondary);
}

.page-header h1 {
  margin: 0 0 0.55rem;
  font-size: 30px;
}

.page-header p,
.empty-panel p,
.panel-copy,
.coverage-detail,
.surface-note {
  color: var(--text-secondary);
  line-height: 1.6;
}

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

.developer-coverage button:disabled,
.developer-coverage input:disabled,
.developer-coverage select:disabled,
.developer-coverage textarea:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.why-copy {
  color: var(--text-primary);
  background: rgba(14, 165, 233, 0.08);
  border: 1px solid rgba(125, 211, 252, 0.16);
  border-radius: 14px;
  padding: 0.75rem 0.9rem;
  margin-top: 0.7rem;
}

.grid {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 1rem;
  align-items: start;
}

.panel {
  grid-column: span 4;
  background: var(--surface-depth-panel);
  border: 1px solid var(--surface-border-panel);
  border-radius: 18px;
  padding: 1.25rem;
  min-width: 0;
}

.panel-wide {
  grid-column: span 8;
}

.panel-full {
  grid-column: span 12;
}

.empty-panel {
  background: rgba(127, 29, 29, 0.12);
}

.panel-header,
.coverage-card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 1rem;
}

.panel-header h2,
.coverage-card h3,
.foundation-group-header h3 {
  margin: 0;
}

.baseline-panel,
.coverage-summary-panel,
.developer-completion-panel {
  min-height: 100%;
}

.baseline-panel {
  background:
    radial-gradient(circle at top left, rgba(59, 130, 246, 0.12), transparent 36%),
    rgba(15, 23, 42, 0.46);
}

.coverage-summary-panel {
  background:
    radial-gradient(circle at top right, rgba(16, 185, 129, 0.1), transparent 34%),
    rgba(15, 23, 42, 0.46);
}

.developer-completion-panel {
  background:
    radial-gradient(circle at top right, rgba(245, 158, 11, 0.1), transparent 34%),
    rgba(15, 23, 42, 0.46);
}

.summary-stack,
.coverage-list {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.foundation-group-list {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.foundation-group {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  border: 1px solid var(--surface-border-card);
  border-radius: 16px;
  background: var(--surface-depth-inset);
  overflow: hidden;
}

.foundation-group + .foundation-group {
  margin-top: 0.2rem;
}

.foundation-group-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
  cursor: pointer;
  list-style: none;
  padding: 1rem 1rem 0.95rem;
}

.foundation-group-header::-webkit-details-marker {
  display: none;
}

.foundation-group-title {
  display: flex;
  align-items: baseline;
  gap: 0.85rem;
  min-width: 0;
}

.foundation-group-header h3 {
  margin: 0;
  font-size: 18px;
}

.foundation-count {
  font-size: 12px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.foundation-summary-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  justify-content: flex-end;
}

.foundation-summary-actions {
  display: flex;
  align-items: flex-end;
  flex-direction: column;
  gap: 0.75rem;
}

.foundation-preview {
  color: #fde68a;
  font-size: 12px;
  line-height: 1.45;
  max-width: 32rem;
  text-align: right;
}

.foundation-summary-badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 0.3rem 0.6rem;
  font-size: 12px;
  font-weight: 700;
}

.foundation-summary-badge.ok {
  background: rgba(16, 185, 129, 0.14);
  color: #86efac;
}

.foundation-summary-badge.warn {
  background: rgba(245, 158, 11, 0.14);
  color: #fcd34d;
}

.foundation-summary-badge.danger {
  background: rgba(239, 68, 68, 0.14);
  color: #fca5a5;
}

.foundation-group-body {
  padding: 0 1rem 1rem;
}

.coverage-subgroup {
  border: 1px solid var(--surface-border-card);
  border-radius: 16px;
  background: var(--surface-depth-inset);
  overflow: hidden;
}

.coverage-subgroup-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
  cursor: pointer;
  list-style: none;
  padding: 1rem 1rem 0.95rem;
}

.coverage-subgroup-header::-webkit-details-marker {
  display: none;
}

.coverage-subgroup-title {
  display: flex;
  align-items: baseline;
  gap: 0.85rem;
  min-width: 0;
}

.coverage-subgroup-title h3 {
  margin: 0;
  font-size: 18px;
}

.coverage-subgroup-body {
  padding: 0 1rem 1rem;
}

.foundation-toggle-hint {
  display: inline-flex;
  align-items: center;
  border: 1px solid var(--surface-border-card);
  border-radius: 999px;
  padding: 0.3rem 0.65rem;
  background: var(--surface-depth-card);
  color: var(--text-primary);
  font-size: 12px;
  font-weight: 700;
}

.foundation-group[open] .foundation-toggle-hint::before {
  content: 'Hide coverage items';
}

.foundation-group[open] .foundation-toggle-hint {
  color: var(--text-primary);
}

.foundation-group[open] .foundation-toggle-hint {
  font-size: 0;
}

.foundation-group[open] .foundation-toggle-hint::before {
  font-size: 12px;
}

.summary-row {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  padding: 0.75rem 0.85rem;
  background: var(--surface-depth-card);
}

.summary-row strong {
  color: var(--text-primary);
  line-height: 1.45;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
}

.metric-card,
.coverage-card {
  border: 1px solid var(--surface-border-card);
  border-radius: 16px;
  padding: 0.95rem;
  background: var(--surface-depth-card);
}

.metric-card {
  min-height: 82px;
}

.metric-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.15;
}

.completion-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.85rem;
  min-width: 0;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  min-width: 0;
}

.field > span {
  color: var(--text-primary);
  font-weight: 700;
}

.field-wide {
  grid-column: span 1;
}

.compact-field {
  width: 220px;
  flex: 0 0 220px;
}

.completion-grid .field,
.coverage-card > .field {
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  padding: 0.85rem;
  background: var(--surface-depth-card);
}

.select,
.textarea {
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  border-radius: 12px;
  border: 1px solid var(--surface-border-card);
  background: rgba(15, 23, 42, 0.7);
  color: inherit;
  padding: 0.7rem 0.85rem;
}

.coverage-status-select.status-not_addressed {
  border-color: rgba(248, 113, 113, 0.58);
  background: rgba(127, 29, 29, 0.22);
  color: #fecaca;
}

.coverage-status-select.status-partially_addressed {
  border-color: rgba(251, 191, 36, 0.42);
  background: rgba(120, 53, 15, 0.2);
  color: #fde68a;
}

.coverage-status-select.status-addressed,
.coverage-status-select.status-not_applicable {
  border-color: rgba(16, 185, 129, 0.34);
}

.textarea {
  resize: vertical;
  overflow-wrap: anywhere;
}

.surface-section {
  margin: 0.9rem 0;
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  padding: 0.85rem;
  background: var(--surface-depth-card);
}

.surface-note {
  margin: 0.35rem 0 0;
  font-size: 13px;
}

.target-surface-line {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  margin: 0.75rem 0 0;
  padding-top: 0.75rem;
  border-top: 1px solid rgba(148, 163, 184, 0.12);
}

.target-surface-label {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 11px;
  color: var(--text-secondary);
}

.inline-link {
  border: none;
  background: transparent;
  color: var(--accent);
  padding: 0;
  font: inherit;
  cursor: pointer;
}

.surface-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.surface-chip {
  border: 1px solid var(--surface-border-card);
  background: var(--surface-depth-card);
  color: inherit;
  border-radius: 999px;
  padding: 0.35rem 0.7rem;
  cursor: pointer;
}

.surface-chip.active {
  background: rgba(59, 130, 246, 0.16);
  border-color: rgba(96, 165, 250, 0.36);
}

.surface-chip.locked {
  cursor: default;
}

.btn {
  border-radius: 12px;
  border: none;
  padding: 0.7rem 1rem;
  font-weight: 600;
  cursor: pointer;
}

.btn-primary {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.92), rgba(14, 165, 233, 0.92));
  color: white;
}

.coverage-group-panel {
  background:
    linear-gradient(180deg, rgba(15, 23, 42, 0.48), rgba(15, 23, 42, 0.36));
}

.coverage-group-panel > .panel-header {
  padding-bottom: 0.9rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.13);
}

.coverage-card {
  background:
    linear-gradient(180deg, rgba(15, 23, 42, 0.38), rgba(15, 23, 42, 0.24));
}

.coverage-resolution-card {
  display: grid;
  gap: 0.65rem;
  margin: 0.75rem 0;
  border: 1px solid rgba(56, 189, 248, 0.24);
  border-left: 5px solid #38bdf8;
  border-radius: 14px;
  padding: 0.85rem;
  background: rgba(14, 116, 144, 0.1);
}

.coverage-resolution-card strong {
  color: #bae6fd;
}

.coverage-resolution-card p {
  margin: 0;
  color: #dbeafe;
  line-height: 1.5;
}

.coordination-choice-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
  margin-top: 0.55rem;
}

.coordination-choice-card {
  display: grid;
  gap: 0.45rem;
  border: 1px solid rgba(125, 211, 252, 0.22);
  border-radius: 14px;
  padding: 0.8rem;
  background: rgba(15, 23, 42, 0.28);
  color: inherit;
  text-align: left;
}

.coordination-choice-card:hover {
  border-color: rgba(125, 211, 252, 0.44);
  background: rgba(14, 116, 144, 0.14);
}

.coordination-choice-card strong {
  color: var(--text-primary);
}

.coordination-choice-card span,
.coordination-choice-card em {
  color: var(--text-secondary);
  font-size: 12px;
  font-style: normal;
  line-height: 1.45;
}

.coordination-choice-card em {
  color: #bfdbfe;
  font-weight: 750;
}

.coordination-patch-preview {
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 12px;
  padding: 0.62rem;
  background: rgba(15, 23, 42, 0.24);
}

.coordination-patch-preview > summary {
  cursor: pointer;
  color: #bfdbfe;
  font-size: 12px;
  font-weight: 900;
}

.coordination-patch-body {
  display: grid;
  gap: 0.45rem;
  margin-top: 0.62rem;
}

.coordination-patch-body ul {
  display: grid;
  gap: 0.3rem;
  margin: 0;
  padding-left: 1.1rem;
  color: var(--text-secondary);
}

.coordination-choice-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.success-note {
  color: #bbf7d0 !important;
  font-weight: 800;
}

.coverage-card-header {
  padding-bottom: 0.85rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
}

.coverage-card-header > div:first-child {
  min-width: 0;
}

.coverage-card h3 {
  margin-top: 0.3rem;
  color: var(--text-primary);
  font-size: 18px;
  line-height: 1.35;
}

.coverage-detail {
  margin: 0.45rem 0 0;
}

.foundation-count {
  flex: 0 0 auto;
}

.persisted-record-panel {
  background:
    radial-gradient(circle at top left, rgba(59, 130, 246, 0.14), transparent 34%),
    rgba(15, 23, 42, 0.46);
}

.persisted-actions {
  margin-top: 1rem;
}

.persisted-actions .btn {
  width: auto;
}

.fit-intro {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.5;
}

.section-context-copy {
  margin: 0.25rem 0 0.85rem;
  color: var(--text-secondary);
  line-height: 1.5;
}

.fit-list {
  display: grid;
  gap: 0.65rem;
  margin-top: 1rem;
}

.fit-row {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  padding: 0.8rem;
  background: var(--surface-depth-card);
}

.fit-row p {
  margin: 0.25rem 0 0;
  color: var(--text-secondary);
  font-size: 12px;
  overflow-wrap: anywhere;
}

.fit-row span {
  font-weight: 700;
  color: var(--text-primary);
}

.glue-list {
  display: grid;
  gap: 0.75rem;
  margin-top: 1rem;
}

.glue-card {
  border: 1px solid rgba(125, 211, 252, 0.18);
  border-radius: 16px;
  padding: 0.9rem;
  background:
    radial-gradient(circle at top left, rgba(14, 165, 233, 0.12), transparent 42%),
    rgba(15, 23, 42, 0.24);
}

.glue-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
}

.glue-card-header strong {
  color: var(--text-primary);
  font-size: 15px;
}

.glue-card-header span {
  border: 1px solid rgba(125, 211, 252, 0.2);
  border-radius: 999px;
  padding: 0.2rem 0.5rem;
  background: rgba(14, 165, 233, 0.08);
  color: #bae6fd;
  font-weight: 800;
  white-space: nowrap;
}

.glue-card p {
  margin: 0.35rem 0;
  color: var(--text-secondary);
  line-height: 1.5;
}

.glue-card-guidance {
  margin-top: 0.75rem;
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 12px;
  padding: 0.65rem;
  background: rgba(15, 23, 42, 0.2);
}

.glue-card span,
.empty-note {
  color: var(--text-secondary);
  font-size: 12px;
}

.glue-card-guidance span {
  display: block;
  color: #bfdbfe;
  font-weight: 800;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.glue-card-details,
.readiness-card-details {
  margin-top: 0.75rem;
  color: var(--text-muted);
  font-size: 12px;
}

.glue-card-details summary,
.readiness-card-details summary {
  cursor: pointer;
  color: #bfdbfe;
  font-weight: 800;
}

.glue-card-details p,
.readiness-card-details p {
  overflow-wrap: anywhere;
}

.readiness-card-body.collapsed {
  display: block;
  margin-top: 0.8rem;
  border-top: 1px solid rgba(148, 163, 184, 0.14);
  padding-top: 0.75rem;
}

.readiness-card-body.collapsed > summary {
  cursor: pointer;
  color: #bfdbfe;
  font-weight: 800;
}

.coverage-lanes-panel {
  background:
    radial-gradient(circle at top right, rgba(125, 211, 252, 0.11), transparent 34%),
    linear-gradient(180deg, rgba(15, 23, 42, 0.5), rgba(15, 23, 42, 0.34));
}

.recommended-lane {
  display: inline-flex;
  align-items: center;
  align-self: flex-start;
  border: 1px solid rgba(125, 211, 252, 0.2);
  border-radius: 999px;
  padding: 0.35rem 0.7rem;
  background: rgba(14, 165, 233, 0.1);
  color: #bae6fd;
  font-size: 12px;
  font-weight: 800;
  white-space: nowrap;
}

.coverage-lane-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 0.85rem;
}

.coverage-lane-card {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0.25rem 0.75rem;
  min-height: 148px;
  border: 1px solid var(--surface-border-card);
  border-radius: 16px;
  padding: 0.95rem;
  background: var(--surface-depth-card);
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.16s ease, transform 0.16s ease, background 0.16s ease;
}

.coverage-lane-card:hover,
.coverage-lane-card.active {
  border-color: rgba(125, 211, 252, 0.42);
  background:
    radial-gradient(circle at top left, rgba(14, 165, 233, 0.12), transparent 42%),
    var(--surface-depth-card);
  transform: translateY(-1px);
}

.coverage-lane-card.active {
  box-shadow: 0 0 0 1px rgba(125, 211, 252, 0.22), 0 18px 42px rgba(2, 6, 23, 0.18);
}

.coverage-lane-card strong {
  align-self: center;
  color: var(--text-primary);
  font-size: 15px;
}

.coverage-lane-card em {
  grid-column: 2;
  align-self: start;
  color: var(--text-secondary);
  font-size: 12px;
  font-style: normal;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.coverage-lane-card p {
  grid-column: 1 / -1;
  margin: 0.45rem 0 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.45;
}

.lane-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2.25rem;
  height: 2.25rem;
  border-radius: 12px;
  background: rgba(148, 163, 184, 0.12);
  color: var(--text-primary);
  font-weight: 900;
}

.coverage-lane-card.state-blocked .lane-count {
  background: rgba(127, 29, 29, 0.28);
  color: #fecaca;
}

.coverage-lane-card.state-warning .lane-count {
  background: rgba(120, 53, 15, 0.28);
  color: #fde68a;
}

.coverage-lane-card.state-ready .lane-count {
  background: rgba(6, 78, 59, 0.28);
  color: #bbf7d0;
}

.agent-readiness-panel {
  background:
    radial-gradient(circle at top left, rgba(251, 191, 36, 0.11), transparent 32%),
    linear-gradient(180deg, rgba(15, 23, 42, 0.5), rgba(15, 23, 42, 0.36));
}

.consumability-review-panel {
  background:
    radial-gradient(circle at top right, rgba(20, 184, 166, 0.12), transparent 34%),
    linear-gradient(180deg, rgba(15, 23, 42, 0.5), rgba(15, 23, 42, 0.36));
}

.high-risk-panel {
  background:
    radial-gradient(circle at top left, rgba(248, 113, 113, 0.12), transparent 34%),
    linear-gradient(180deg, rgba(15, 23, 42, 0.5), rgba(15, 23, 42, 0.36));
}

.high-risk-list {
  display: grid;
  gap: 0.85rem;
  margin-top: 1rem;
}

.high-risk-card {
  border: 1px solid var(--surface-border-card);
  border-radius: 16px;
  padding: 0.95rem;
  background: var(--surface-depth-inset);
}

.high-risk-card-header {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
}

.high-risk-card-header p {
  margin: 0.35rem 0 0;
  color: var(--text-secondary);
  line-height: 1.5;
}

.high-risk-severity-badge {
  flex: 0 0 auto;
  align-self: flex-start;
  border-radius: 10px;
  padding: 0.3rem 0.55rem;
  border: 1px solid var(--surface-border-card);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.08em;
  line-height: 1;
  text-transform: uppercase;
}

.high-risk-severity-badge.severity-blocker {
  border-color: rgba(248, 113, 113, 0.3);
  background: rgba(127, 29, 29, 0.22);
  color: #fecaca;
}

.high-risk-severity-badge.severity-warning {
  border-color: rgba(251, 191, 36, 0.28);
  background: rgba(120, 53, 15, 0.22);
  color: #fde68a;
}

.automation-review-chip {
  border-color: rgba(251, 191, 36, 0.34) !important;
  color: #fde68a !important;
}

.reviewed-count {
  flex: 0 0 auto;
  border: 1px solid rgba(45, 212, 191, 0.24);
  border-radius: 999px;
  padding: 0.35rem 0.7rem;
  background: rgba(15, 118, 110, 0.16);
  color: #99f6e4;
  font-size: 12px;
  font-weight: 700;
}

.reviewed-count.empty {
  border-color: rgba(148, 163, 184, 0.18);
  background: var(--surface-depth-card);
  color: var(--text-secondary);
}

.reviewed-count.unresolved {
  border-color: rgba(251, 191, 36, 0.34);
  background: rgba(120, 53, 15, 0.22);
  color: #fde68a;
}

.consumability-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
  margin-top: 1rem;
}

.consumability-card {
  border: 1px solid var(--surface-border-card);
  border-radius: 16px;
  padding: 0.95rem;
  background: var(--surface-depth-inset);
}

.consumability-card.needsReview {
  border-color: rgba(251, 191, 36, 0.3);
  background: rgba(120, 53, 15, 0.12);
}

.consumability-card.reviewed {
  border-color: rgba(45, 212, 191, 0.26);
}

.consumability-card-header {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  align-items: flex-start;
  padding-bottom: 0.85rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
}

.consumability-card-header p {
  margin: 0.35rem 0 0;
  color: var(--text-secondary);
  line-height: 1.5;
}

.consumability-card-header .effect-summary {
  color: var(--text-primary);
  font-size: 12px;
}

.effect-summary small {
  display: block;
  margin-top: 0.2rem;
  color: var(--text-muted);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace;
}

.app-profile-review-body {
  display: grid;
  gap: 0.85rem;
  margin-top: 0.85rem;
}

.app-profile-summary {
  border: 1px solid rgba(45, 212, 191, 0.2);
  border-radius: 14px;
  padding: 0.8rem;
  background: rgba(13, 148, 136, 0.08);
}

.app-profile-summary span {
  color: #99f6e4;
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.app-profile-summary p {
  margin: 0.35rem 0 0;
  color: #ccfbf1;
  line-height: 1.5;
}

.readiness-task-box {
  display: grid;
  gap: 0.65rem;
  padding: 0.8rem;
  border: 1px solid rgba(96, 165, 250, 0.22);
  border-radius: 14px;
  background:
    linear-gradient(135deg, rgba(30, 64, 175, 0.14), rgba(15, 23, 42, 0.18)),
    rgba(15, 23, 42, 0.2);
}

.readiness-task-box div {
  display: grid;
  gap: 0.2rem;
}

.readiness-task-box span {
  color: #bfdbfe;
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.readiness-task-box strong {
  color: var(--text-primary);
}

.readiness-task-box p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.45;
}

.app-profile-guidance-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
}

.app-profile-guidance-card {
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  padding: 0.8rem;
  background: rgba(15, 23, 42, 0.24);
}

.app-profile-guidance-card strong {
  color: var(--text-primary);
}

.app-profile-guidance-card p {
  margin: 0.35rem 0 0;
  color: var(--text-secondary);
  line-height: 1.45;
}

.app-profile-guidance-card.tone-app {
  border-color: rgba(56, 189, 248, 0.28);
  background: rgba(14, 116, 144, 0.12);
}

.app-profile-guidance-card.tone-boundary {
  border-color: rgba(251, 191, 36, 0.28);
  background: rgba(120, 53, 15, 0.14);
}

.app-profile-guidance-card.tone-context {
  border-color: rgba(34, 197, 94, 0.24);
  background: rgba(20, 83, 45, 0.12);
}

.app-profile-guidance-card.tone-display {
  border-color: rgba(168, 85, 247, 0.24);
  background: rgba(88, 28, 135, 0.12);
}

.semantic-rules-panel {
  display: grid;
  gap: 0.75rem;
  border: 1px solid rgba(125, 211, 252, 0.18);
  border-radius: 16px;
  padding: 0.85rem;
  background:
    linear-gradient(135deg, rgba(8, 47, 73, 0.22), rgba(15, 23, 42, 0.1)),
    rgba(15, 23, 42, 0.18);
}

.semantic-rules-header {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  align-items: flex-start;
}

.semantic-rules-header h3 {
  margin: 0;
  color: #e0f2fe;
}

.semantic-rules-header p {
  margin: 0.35rem 0 0;
  color: #bae6fd;
  line-height: 1.45;
}

.semantic-rule-list {
  display: grid;
  gap: 0.6rem;
}

.semantic-rule-card {
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 14px;
  padding: 0.7rem;
  background: rgba(15, 23, 42, 0.22);
}

.semantic-rule-card > summary {
  cursor: pointer;
  color: var(--text-primary);
  font-weight: 900;
}

.semantic-rule-card > summary small {
  display: block;
  margin-top: 0.25rem;
  color: var(--text-secondary);
  font-weight: 600;
  line-height: 1.4;
}

.semantic-rule-editor {
  display: grid;
  gap: 0.7rem;
  margin-top: 0.75rem;
}

.semantic-rule-editor label {
  display: grid;
  gap: 0.35rem;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.semantic-rule-editor input,
.semantic-rule-editor select,
.semantic-rule-editor textarea {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--surface-border-card);
  border-radius: 12px;
  background: var(--surface-depth-inset);
  color: var(--text-primary);
  padding: 0.65rem 0.75rem;
  font: inherit;
  letter-spacing: normal;
  text-transform: none;
}

.semantic-rule-editor textarea {
  resize: vertical;
}

.semantic-rule-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.65rem;
}

.add-rule-card {
  border-style: dashed;
}

.technical-metadata-details {
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 14px;
  padding: 0.75rem;
  background: rgba(15, 23, 42, 0.16);
}

.technical-metadata-details > summary {
  cursor: pointer;
  color: #bfdbfe;
  font-weight: 900;
}

.other-capabilities-details {
  margin-top: 1rem;
}

.consumability-fields {
  display: grid;
  gap: 0.75rem;
  margin-top: 0.85rem;
}

.consumability-fields label {
  display: grid;
  gap: 0.4rem;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.consumability-fields input,
.consumability-fields textarea {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--surface-border-card);
  border-radius: 12px;
  background: var(--surface-depth-inset);
  color: var(--text-primary);
  padding: 0.65rem 0.75rem;
  font: inherit;
  letter-spacing: normal;
  text-transform: none;
}

.consumability-fields textarea {
  resize: vertical;
}

.field-suggestion {
  margin: -0.15rem 0 0;
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 500;
  letter-spacing: normal;
  line-height: 1.45;
  text-transform: none;
}

.checkbox-field {
  display: flex !important;
  grid-template-columns: auto 1fr;
  align-items: center;
  gap: 0.55rem !important;
  letter-spacing: normal !important;
  text-transform: none !important;
}

.checkbox-field input {
  width: auto;
}

.readiness-header {
  align-items: center;
}

.readiness-score {
  flex: 0 0 auto;
  min-width: 136px;
  border: 1px solid var(--surface-border-card);
  border-radius: 18px;
  padding: 0.8rem;
  text-align: center;
  background: var(--surface-depth-card);
}

.readiness-score strong {
  display: block;
  margin-top: 0.25rem;
  font-size: 25px;
  line-height: 1;
}

.readiness-score span,
.readiness-score em {
  display: block;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.readiness-score em {
  margin-top: 0.4rem;
  color: inherit;
  font-style: normal;
}

.readiness-score.status-ready {
  border-color: rgba(16, 185, 129, 0.34);
  color: #86efac;
}

.readiness-score.status-needs_review {
  border-color: rgba(245, 158, 11, 0.36);
  color: #fcd34d;
}

.readiness-score.status-blocked {
  border-color: rgba(248, 113, 113, 0.42);
  color: #fca5a5;
}

.readiness-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-top: 1rem;
}

.readiness-actions .btn {
  width: auto;
}

.readiness-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.75rem;
  margin: 1rem 0;
}

.readiness-metric {
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  padding: 0.8rem;
  background: var(--surface-depth-card);
}

.readiness-metric span {
  display: block;
  color: var(--text-secondary);
  font-size: 12px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.readiness-metric strong {
  display: block;
  margin-top: 0.3rem;
  font-size: 24px;
}

.readiness-sections {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}

.readiness-section {
  min-width: 0;
}

.readiness-section-wide {
  grid-column: span 2;
}

.readiness-section h3 {
  margin: 0 0 0.75rem;
}

.simulation-summary {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: center;
  border: 1px solid var(--surface-border-card);
  border-radius: 16px;
  padding: 0.85rem 1rem;
  margin-bottom: 0.85rem;
  background: var(--surface-depth-card);
}

.simulation-summary strong {
  font-size: 20px;
  text-transform: uppercase;
}

.simulation-summary span {
  color: var(--text-secondary);
}

.simulation-summary.status-pass {
  border-color: rgba(16, 185, 129, 0.34);
}

.simulation-summary.status-fail {
  border-color: rgba(248, 113, 113, 0.42);
}

.assistant-feedback {
  border: 1px solid rgba(45, 212, 191, 0.2);
  border-radius: 16px;
  padding: 1rem;
  background: rgba(13, 148, 136, 0.08);
}

.assistant-feedback p {
  color: var(--text-secondary);
  line-height: 1.55;
}

.focused-assistant-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
  margin-top: 0.75rem;
}

.focused-assistant-preview {
  display: grid;
  gap: 0.65rem;
  margin-top: 0.85rem;
  border: 1px solid rgba(45, 212, 191, 0.22);
  border-radius: 14px;
  padding: 0.85rem;
  background:
    radial-gradient(circle at top left, rgba(45, 212, 191, 0.12), transparent 34%),
    rgba(15, 23, 42, 0.34);
}

.focused-assistant-preview p,
.focused-assistant-preview li {
  color: var(--text-secondary);
  line-height: 1.5;
}

.focused-assistant-preview ul {
  margin: 0;
  padding-left: 1.1rem;
}

.review-suggestion-preview {
  display: grid;
  gap: 0.35rem;
  border: 1px solid rgba(251, 191, 36, 0.22);
  border-radius: 12px;
  padding: 0.75rem;
  background: rgba(120, 53, 15, 0.14);
}

.review-suggestion-preview span {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.review-suggestion-preview p {
  margin: 0;
}

.inline-remediation-card {
  display: grid;
  gap: 0.7rem;
  margin-top: 0.85rem;
  border: 1px solid rgba(34, 197, 94, 0.34);
  border-left: 5px solid #22c55e;
  border-radius: 14px;
  padding: 0.85rem;
  background:
    linear-gradient(135deg, rgba(22, 101, 52, 0.22), rgba(15, 23, 42, 0.22)),
    rgba(20, 83, 45, 0.14);
}

.inline-remediation-card span {
  color: #bbf7d0;
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.inline-remediation-card strong {
  display: block;
  margin-top: 0.25rem;
  color: #f8fafc;
}

.inline-remediation-card p {
  margin: 0.3rem 0 0;
  color: #dcfce7;
}

.inline-remediation-card label {
  display: grid;
  gap: 0.35rem;
  color: #bbf7d0;
  font-size: 13px;
  font-weight: 800;
}

.remediation-suggestion {
  display: grid;
  gap: 0.45rem;
  border: 1px solid rgba(125, 211, 252, 0.2);
  border-radius: 12px;
  padding: 0.7rem;
  background: rgba(15, 23, 42, 0.22);
}

.remediation-suggestion p {
  margin: 0;
  color: #bfdbfe;
  font-weight: 700;
}

.remediation-suggestion .btn {
  width: fit-content;
}

.inline-remediation-card textarea {
  min-height: 72px;
}

.ownership-resolution-card {
  display: grid;
  gap: 0.8rem;
  margin-top: 0.85rem;
  border: 1px solid rgba(56, 189, 248, 0.24);
  border-left: 5px solid #38bdf8;
  border-radius: 14px;
  padding: 0.85rem;
  background:
    linear-gradient(135deg, rgba(12, 74, 110, 0.18), rgba(15, 23, 42, 0.22)),
    rgba(14, 116, 144, 0.1);
}

.ownership-resolution-card span {
  color: #bae6fd;
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.ownership-resolution-card strong {
  display: block;
  margin-top: 0.25rem;
  color: #f8fafc;
}

.ownership-resolution-card p {
  margin: 0.3rem 0 0;
  color: #dbeafe;
}

.resolution-choice-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.75rem;
}

.resolution-choice-card {
  min-height: 120px;
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  padding: 0.8rem;
  background: rgba(15, 23, 42, 0.26);
  color: inherit;
  cursor: pointer;
  text-align: left;
}

.resolution-choice-card:hover {
  transform: translateY(-1px);
  border-color: rgba(125, 211, 252, 0.38);
}

.resolution-choice-card strong {
  margin: 0 0 0.45rem;
}

.resolution-choice-card span {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 650;
  letter-spacing: normal;
  line-height: 1.45;
  text-transform: none;
}

.resolution-choice-card.app-owned {
  border-color: rgba(56, 189, 248, 0.28);
  background: rgba(14, 116, 144, 0.12);
}

.resolution-choice-card.service-owned {
  border-color: rgba(245, 158, 11, 0.3);
  background: rgba(120, 53, 15, 0.16);
}

.resolution-choice-card.clarify-owned {
  border-color: rgba(34, 197, 94, 0.28);
  background: rgba(20, 83, 45, 0.12);
}

.readiness-gate-warning {
  margin-top: 0.85rem;
  border: 1px solid rgba(248, 113, 113, 0.28);
  border-radius: 14px;
  padding: 0.8rem;
  background: rgba(127, 29, 29, 0.2);
}

.readiness-gate-warning strong {
  color: #fecaca;
}

.readiness-gate-warning p {
  margin: 0.35rem 0 0;
}

.assistant-feedback-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
  margin-top: 0.85rem;
}

.assistant-feedback-grid span {
  color: #99f6e4;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.assistant-feedback-grid ul {
  margin: 0.5rem 0 0;
  padding-left: 1.1rem;
  color: var(--text-secondary);
}

.assistant-action-list {
  display: grid;
  gap: 0.8rem;
  padding-left: 0;
  list-style: none;
}

.assistant-action-list li {
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  padding: 0.75rem;
  background: var(--surface-depth-inset);
}

.assistant-action-list p {
  margin: 0;
}

.assistant-step-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.65rem;
}

.assistant-step-actions .btn {
  width: auto;
}

.btn-compact {
  min-height: 32px;
  padding: 0.4rem 0.7rem;
  font-size: 12px;
}

.readiness-list,
.probe-grid {
  display: grid;
  gap: 0.75rem;
}

.probe-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.readiness-card,
.probe-card {
  border: 1px solid var(--surface-border-card);
  border-radius: 16px;
  padding: 0.9rem;
  background: var(--surface-depth-inset);
}

.readiness-card.severity-card-blocker,
.high-risk-card.severity-card-blocker,
.consumability-card.severity-card-blocker {
  border-color: rgba(248, 113, 113, 0.42);
  background:
    linear-gradient(135deg, rgba(127, 29, 29, 0.22), rgba(15, 23, 42, 0.2)),
    rgba(127, 29, 29, 0.12);
  box-shadow: 0 0 0 1px rgba(248, 113, 113, 0.14);
}

.readiness-card.severity-card-warning,
.high-risk-card.severity-card-warning,
.consumability-card.severity-card-warning {
  border-color: rgba(251, 191, 36, 0.34);
  background:
    linear-gradient(135deg, rgba(120, 53, 15, 0.2), rgba(15, 23, 42, 0.18)),
    rgba(120, 53, 15, 0.12);
  box-shadow: 0 0 0 1px rgba(251, 191, 36, 0.12);
}

.consumability-card.reviewed,
.consumability-card.reviewed.severity-card-warning,
.consumability-card.reviewed.severity-card-blocker {
  border-color: rgba(45, 212, 191, 0.48);
  border-left: 6px solid #2dd4bf;
  background:
    linear-gradient(135deg, rgba(15, 118, 110, 0.22), rgba(15, 23, 42, 0.2)),
    rgba(19, 78, 74, 0.16);
  box-shadow: 0 0 0 1px rgba(45, 212, 191, 0.16);
}

.readiness-card.readiness-card-reviewed {
  border-color: rgba(34, 197, 94, 0.62);
  border-left: 6px solid #22c55e;
  background:
    linear-gradient(135deg, rgba(22, 101, 52, 0.28), rgba(15, 23, 42, 0.24)),
    rgba(20, 83, 45, 0.18);
  box-shadow: 0 0 0 1px rgba(34, 197, 94, 0.22);
}

.readiness-card.readiness-card-app-glue {
  border-color: rgba(56, 189, 248, 0.58);
  border-left: 6px solid #38bdf8;
  background:
    linear-gradient(135deg, rgba(12, 74, 110, 0.28), rgba(15, 23, 42, 0.24)),
    rgba(14, 116, 144, 0.16);
  box-shadow: 0 0 0 1px rgba(56, 189, 248, 0.2);
}

.readiness-card.readiness-card-follow-up {
  border-color: rgba(245, 158, 11, 0.62);
  border-left: 6px solid #f59e0b;
  background:
    linear-gradient(135deg, rgba(146, 64, 14, 0.32), rgba(15, 23, 42, 0.26)),
    rgba(120, 53, 15, 0.22);
  box-shadow: 0 0 0 1px rgba(245, 158, 11, 0.24);
}

.readiness-card.severity-card-info,
.readiness-card.readiness-card-info-only {
  border-color: rgba(96, 165, 250, 0.2);
  background:
    linear-gradient(135deg, rgba(30, 64, 175, 0.12), rgba(15, 23, 42, 0.16)),
    rgba(15, 23, 42, 0.16);
}

.informational-readiness-notes {
  margin-top: 1rem;
  border: 1px solid rgba(96, 165, 250, 0.18);
  border-radius: 16px;
  padding: 0.85rem;
  background: rgba(15, 23, 42, 0.14);
}

.informational-readiness-notes > summary {
  cursor: pointer;
  color: #bfdbfe;
  font-weight: 900;
}

.informational-readiness-notes .readiness-list {
  margin-top: 0.85rem;
}

.review-state-chip {
  display: inline-flex;
  width: fit-content;
  margin-bottom: 0.55rem;
  border: 1px solid rgba(45, 212, 191, 0.24);
  border-radius: 999px;
  padding: 0.24rem 0.5rem;
  color: #99f6e4;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.07em;
  text-transform: uppercase;
}

.review-state-chip-warning {
  border-color: rgba(251, 191, 36, 0.28);
  color: #fde68a;
}

.readiness-card-header,
.probe-card-header {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  align-items: flex-start;
}

.readiness-card-badges {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.4rem;
}

.readiness-card p,
.probe-card p {
  margin: 0.45rem 0 0;
  color: var(--text-secondary);
  line-height: 1.5;
}

.readiness-question {
  color: #f8fafc !important;
  font-weight: 800;
}

.readiness-recommendation {
  color: #dbeafe !important;
}

.readiness-resolution-effect {
  border: 1px solid rgba(125, 211, 252, 0.18);
  border-radius: 12px;
  padding: 0.65rem;
  background: rgba(15, 23, 42, 0.24);
  color: #bfdbfe !important;
  font-weight: 700;
}

.follow-up-work-card {
  display: grid;
  gap: 0.45rem;
  margin-top: 0.85rem;
  border: 1px solid rgba(245, 158, 11, 0.34);
  border-left: 5px solid #f59e0b;
  border-radius: 14px;
  padding: 0.75rem;
  background: rgba(120, 53, 15, 0.2);
}

.follow-up-work-card strong {
  color: #fde68a;
}

.follow-up-work-card p {
  margin: 0;
  color: #fed7aa;
}

.follow-up-work-card .btn {
  width: fit-content;
  margin-top: 0.25rem;
}

.readiness-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  margin-top: 0.75rem;
}

.readiness-meta span,
.probe-card small,
.probe-card-header span {
  color: var(--text-secondary);
  font-size: 12px;
}

.readiness-meta span,
.probe-card-header span {
  border: 1px solid var(--surface-border-card);
  border-radius: 999px;
  padding: 0.25rem 0.5rem;
  background: var(--surface-depth-card);
}

.readiness-review {
  display: grid;
  gap: 0.75rem;
  margin-top: 0.9rem;
  padding-top: 0.9rem;
  border-top: 1px solid rgba(148, 163, 184, 0.12);
}

.readiness-review label {
  display: grid;
  gap: 0.4rem;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.readiness-review select,
.readiness-review textarea {
  width: 100%;
  border: 1px solid var(--surface-border-card);
  border-radius: 12px;
  background: var(--surface-depth-inset);
  color: var(--text-primary);
  padding: 0.65rem 0.75rem;
  font: inherit;
  letter-spacing: normal;
  text-transform: none;
}

.readiness-review textarea {
  resize: vertical;
  min-height: 76px;
}

.readiness-badge {
  flex: 0 0 auto;
  border-radius: 999px;
  padding: 0.25rem 0.55rem;
  font-size: 12px;
  font-weight: 700;
}

.readiness-badge.severity-blocker {
  background: rgba(239, 68, 68, 0.16);
  color: #fca5a5;
}

.readiness-badge.severity-warning {
  background: rgba(245, 158, 11, 0.16);
  color: #fcd34d;
}

.readiness-badge.severity-info {
  background: rgba(96, 165, 250, 0.14);
  color: #bfdbfe;
}

.readiness-badge.reviewed-decision-badge {
  border: 1px solid rgba(34, 197, 94, 0.45);
  background: rgba(22, 163, 74, 0.24);
  color: #bbf7d0;
  font-weight: 900;
}

.readiness-badge.reviewed-decision-badge.decision-follow_up {
  border-color: rgba(245, 158, 11, 0.52);
  background: rgba(180, 83, 9, 0.26);
  color: #fde68a;
}

.readiness-badge.reviewed-decision-badge.decision-explicit_app_glue {
  border-color: rgba(56, 189, 248, 0.5);
  background: rgba(14, 165, 233, 0.22);
  color: #bae6fd;
}

.readiness-badge.reviewed-decision-badge.decision-acceptable_warning {
  border-color: rgba(34, 197, 94, 0.5);
  background: rgba(22, 163, 74, 0.24);
  color: #bbf7d0;
}

.error {
  color: #fecaca;
}

.success-copy {
  color: #86efac;
}

.page-header-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-top: 1rem;
}

@media (max-width: 1100px) {
  .panel,
  .panel-wide,
  .panel-full {
    grid-column: span 12;
  }

  .completion-grid {
    grid-template-columns: 1fr;
  }

  .readiness-metrics,
  .readiness-sections,
  .probe-grid,
  .consumability-grid,
  .app-profile-guidance-grid,
  .semantic-rule-grid,
  .resolution-choice-grid {
    grid-template-columns: 1fr;
  }

  .readiness-section-wide {
    grid-column: span 1;
  }
}
</style>
