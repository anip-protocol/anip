<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type {
  DeveloperCapabilityFormalization,
  DeveloperCapabilityInputFormalization,
  DeveloperCapabilityInputResolutionBehavior,
  DeveloperCapabilityInputResolutionMode,
  DeveloperCapabilityKind,
  DeveloperComposition,
  DeveloperCompositionStep,
  DeveloperGrantPolicy,
  DeveloperGrantType,
} from '../design/project-types'
import { useDeveloperDefinitionEditor } from '../design/use-developer-definition-editor'
import { useDeveloperIssueTargets } from '../design/use-developer-issue-targets'
import ProjectIssueBanner from '../components/ProjectIssueBanner.vue'
import { useProjectIssue } from '../design/use-project-issue'
import { developerLabel } from '../design/developer-vocabulary'
import { formatEffectList, technicalEffectLabel } from '../design/effect-vocabulary'
import { showTechnicalIdentifiers, technicalHoverLabel } from '../design/technical-display'
import { loadProject, projectStore } from '../design/project-store'
import { createPmArtifact } from '../design/project-api'
import {
  applyInputContractEvidence,
  inputContractEvidenceArtifactItems,
  parseInputContractEvidence,
} from '../design/input-contract-evidence'

const route = useRoute()
const router = useRouter()
const editing = ref(false)
const activeCapabilityAnchor = ref('')
const activeServiceAnchor = ref('')
const activeBehaviorAnchor = ref('')
const expandedHelpCards = ref<Record<string, boolean>>({})
const activeHelpCard = ref<string | null>(null)
const evidencePanelOpen = ref(false)
const inputContractEvidenceText = ref('')
const inputContractEvidenceError = ref('')
const inputContractEvidenceStatus = ref('')
const importingInputContractEvidence = ref(false)
const pageIssue = useProjectIssue('project-developer-capability-formalization')
const readOnly = computed(() => projectStore.runtimeStatus?.read_only_mode !== false)
const {
  project,
  baseline,
  baselineAligned,
  definition,
  serviceOptions,
  setCapabilityField,
  saveDraft,
  resetDefinition,
  saving,
  saveError,
} = useDeveloperDefinitionEditor()

const {
  messagesForPath,
  messagesForPrefix,
  hasIssueForPath,
  hasIssueForPrefix,
} = useDeveloperIssueTargets({ definition, project })

const CAPABILITY_FIELD_HELP: Record<string, {
  title: string
  summary: string
  inlineDetails: string[]
  bullets: string[]
  example?: string
  decisionOwner?: string
}> = {
  stableCapabilityId: {
    title: 'Stable Capability ID',
    summary: 'This is the durable contract identity for the capability, not just a display label.',
    inlineDetails: [
      'Registry packages, generated services, verifier checks, and consuming apps use this ID to refer to the same capability over time.',
      'Changing it after publication should be treated as a contract identity change, not a cosmetic rename.',
    ],
    bullets: [
      'Keep this stable when the business capability is still the same.',
      'Use predictable names that are unique inside the package.',
      'Do not use this field for prose or version notes.',
      'If the capability meaning changes materially, create a new revision and review whether the ID should change.',
    ],
    example: '`gtm.pipeline_summary` is acceptable as a stable ID. “Pipeline summary for Q2 review” belongs in the display name or summary, not the ID.',
    decisionOwner: 'Usually developer design or architecture.',
  },
  displayName: {
    title: 'Display Name',
    summary: 'This is the human-facing name reviewers see in Studio diagrams, summaries, and review screens.',
    inlineDetails: [
      'Unlike the stable capability ID, this can be improved for readability without changing contract identity.',
      'Use a short business name, not a backend method name.',
    ],
    bullets: [
      'Prefer words users and reviewers understand.',
      'Avoid prefixes that only repeat the domain unless they add clarity.',
      'Keep it short enough to work in diagrams and cards.',
    ],
    example: 'Use “Pipeline Summary” rather than “Gtm.Pipeline Summary” if the domain is already clear elsewhere.',
    decisionOwner: 'Usually developer design, with PM review for business wording.',
  },
  owningService: {
    title: 'Owning Service',
    summary: 'This decides which generated service exposes and owns this capability.',
    inlineDetails: [
      'A capability should have one service owner in the generated ANIP surface.',
      'If ownership is ambiguous, resolve that explicitly before generation instead of relying on fallback behavior.',
    ],
    bullets: [
      'The owner controls generated service placement.',
      'Service-level permissions, runtime posture, and verification expectations follow this binding.',
      'Do not assign a capability to a service just because that service participates indirectly.',
    ],
    example: 'An enrichment summary should be owned by the enrichment service, even if a pipeline scenario may call it later.',
    decisionOwner: 'Usually developer design or architecture.',
  },
  capabilityPurpose: {
    title: 'Capability Purpose',
    summary: 'This describes why the capability exists from the consuming app perspective.',
    inlineDetails: [
      'Use this to distinguish business-facing capabilities from internal plumbing.',
      'This feeds generated metadata, readiness checks, and simulator probes.',
    ],
    bullets: [
      'Business action means the capability is something an app or agent can intentionally ask for.',
      'Read-only information is appropriate when the capability only answers or summarizes.',
      'Approval-gated work is appropriate when the capability may stop for human approval.',
    ],
    example: '“Draft outreach message” is a business action. “Get raw adapter payload” usually is not.',
    decisionOwner: 'Usually developer design, with PM review for product semantics.',
  },
  serviceAction: {
    title: 'Service Action',
    summary: 'This describes what the service does when the capability is invoked.',
    inlineDetails: [
      'Use this to separate returning information, ranking, drafting, previewing governed work, and changing systems.',
      'This is more precise than a prose summary and is used by validation and generation.',
    ],
    bullets: [
      'Return information for summaries and bounded reads.',
      'Compute or rank for scoring, prioritization, and recommendations.',
      'Draft content for generated content that is not sent.',
      'Preview governed work when the service prepares a safe preview before approval.',
      'Change a system only when downstream state is actually mutated.',
    ],
    example: 'A forecast summary returns information. A routing recommendation may compute/rank or preview governed work depending on its boundary.',
    decisionOwner: 'Usually developer design.',
  },
  safetySideEffect: {
    title: 'Safety / Side Effect',
    summary: 'This tells Studio how risky the capability is to invoke.',
    inlineDetails: [
      'Read-only means no downstream state changes are expected.',
      'Draft-only means content is created but not sent, published, or written externally.',
      'Requires approval means the capability may stop and resume only with a bounded approval grant.',
      'Writes data means invocation can mutate downstream state.',
    ],
    bullets: [
      'This value drives readiness checks and simulator probes.',
      'Do not mark a capability read-only if its wording implies approval, send, export, or mutation behavior.',
      'If the capability prepares a mutation but does not execute it, prefer preview or approval-required semantics.',
    ],
    example: '“Draft email” is draft-only. “Send email” is a downstream mutation and should not be hidden as read-only.',
    decisionOwner: 'Usually developer design, with PM validation for governed boundaries.',
  },
  businessSummary: {
    title: 'Business Summary',
    summary: 'This is the plain-language contract for what the capability does and does not do.',
    inlineDetails: [
      'Write this so a PM, architect, or consuming-app developer can understand the boundary without reading code.',
      'Call out important exclusions like no raw export, no sending, no mutation, or explicit scope required.',
    ],
    bullets: [
      'Prefer product language over backend language.',
      'Include safety boundaries when they matter.',
      'Avoid simply repeating the capability ID.',
    ],
    example: '“Summarizes pipeline health for a bounded quarter and visible scope. Does not export raw opportunity rows.”',
    decisionOwner: 'PM and developer design together.',
  },
  capabilityShape: {
    title: 'Capability Shape',
    summary: 'This decides whether the capability is one direct behavior or a same-service composed behavior.',
    inlineDetails: [
      'Single capability is one atomic service behavior.',
      'Composed capability is still one agent-facing capability, but the same service owns ordered internal child calls.',
    ],
    bullets: [
      'Use single capability unless the service truly owns multiple ordered internal steps.',
      'Do not use composed capability for arbitrary cross-service workflows.',
      'Composed capabilities are validated before generation and publication.',
    ],
    example: 'A same-service “prepare follow-up preview” can compose internal selection and preview steps. Cross-service app routing should remain outside this field.',
    decisionOwner: 'Developer design or architecture.',
  },
  namedBusinessTarget: {
    title: 'Needs Named Business Target',
    summary: 'This tells Studio whether the caller must name a specific business target before invocation.',
    inlineDetails: [
      'Use Yes when the service cannot safely infer the target from generic language like “top accounts” or “selected region.”',
      'This helps Studio identify clarification needs and app-glue boundaries earlier.',
    ],
    bullets: [
      'Examples include account, team, opportunity, cohort, region, owner, product, or customer segment.',
      'If the consuming app must select the target first, mark that explicitly instead of treating vague language as a literal name.',
      'Use No only when the capability can safely operate without a named target.',
    ],
    example: 'An account enrichment summary needs a named account or account set. A portfolio-level pipeline summary may not.',
    decisionOwner: 'PM and developer design together.',
  },
  businessSubject: {
    title: 'Business Subject',
    summary: 'This names the main business thing the capability is about.',
    inlineDetails: [
      'Use a simple domain noun or noun phrase.',
      'This improves diagrams, readiness reports, and consuming-app hints without changing the stable capability ID.',
    ],
    bullets: [
      'Good examples: account, team, opportunity cohort, pipeline, product line.',
      'Avoid backend resource names unless those are also business terms.',
    ],
    example: 'For account enrichment, the subject is “account” or “account cohort.”',
    decisionOwner: 'Usually PM or developer design.',
  },
  businessContext: {
    title: 'Business Context',
    summary: 'This describes the operating context where the capability is useful.',
    inlineDetails: [
      'Context is broader than the subject. It explains the business situation or lens.',
      'Use it to help reviewers and consuming apps understand when the capability applies.',
    ],
    bullets: [
      'Good examples: pipeline review, entity enrichment, operational performance, routing preparation.',
      'Avoid implementation contexts like REST endpoint or SQL query.',
    ],
    example: 'A team performance summary subject may be “sales team,” while its context is “operational performance.”',
    decisionOwner: 'Usually PM and developer design together.',
  },
  resultMeaning: {
    title: 'Result Meaning',
    summary: 'This describes what the output represents in business terms.',
    inlineDetails: [
      'Use this to explain the result shape without exposing schema internals first.',
      'It helps consuming apps render and reason about results without hardcoded domain guesses.',
    ],
    bullets: [
      'Good examples: bounded summary, ranked targets, draft content, approval preview.',
      'If the result is restricted, masked, or approval-gated, say that here or in the business summary.',
    ],
    example: 'For prioritization, result meaning might be “ranked target cohort with explainable priority evidence.”',
    decisionOwner: 'Developer design, with PM validation for user-facing meaning.',
  },
}

const RUNTIME_FIELD_HELP: Record<string, {
  title: string
  summary: string
  inlineDetails: string[]
}> = {
  composedCapability: {
    title: 'Composed Capability',
    summary: 'A composed capability is one caller-facing ANIP capability backed by ordered child capability calls inside the same service.',
    inlineDetails: [
      'Use this when the service can own the full business behavior without pushing orchestration into the consuming app.',
      'The caller invokes only the parent capability. Runtime executes the child steps, maps inputs and outputs, and preserves audit lineage.',
      'Studio currently supports same-service composition only. Cross-service workflow remains app glue or future contract work.',
    ],
  },
  authorityBoundary: {
    title: 'Authority Boundary',
    summary: 'This defines where child capability calls are allowed to run.',
    inlineDetails: [
      'Same service only means every child step must be owned by this service.',
      'This avoids hidden cross-service orchestration and keeps token scope, audit, and failure behavior reviewable.',
    ],
  },
  emptyResultPolicy: {
    title: 'Empty Result Behavior',
    summary: 'This tells runtime what to do when an earlier selection step returns no business records.',
    inlineDetails: [
      'Return no-results when no downstream work should happen and the request can still complete safely.',
      'Clarify when the service needs a different target or more context.',
      'Deny when an empty result means the requested behavior is not allowed or cannot be proven safe.',
    ],
  },
  compositionStep: {
    title: 'Composition Step',
    summary: 'Each step calls one existing single capability owned by this same service.',
    inlineDetails: [
      'Step order matters. Later steps can use caller-provided inputs or the result from an earlier step.',
      'The step ID is a stable internal key used by generated code. Most users should not need to edit it unless there is a naming conflict.',
    ],
  },
  compositionChildCapability: {
    title: 'Child Capability',
    summary: 'Choose which existing same-service capability should run at this point in the composed behavior.',
    inlineDetails: [
      'Only single capabilities from this same service are valid because the current runtime boundary is same-service composition.',
      'Choose the child behavior in the order the service must execute it.',
      'If the behavior needs another service, that is not this field. It should be app glue, orchestration outside this service, or future cross-service composition work.',
    ],
  },
  inputMapping: {
    title: 'Input Mapping',
    summary: 'Input mapping tells the composed capability where each child step gets each required value.',
    inlineDetails: [
      'A value can come from the caller of the parent capability, such as the target group supplied to the composed capability.',
      'A value can also come from an earlier step, such as using step 1 results as the target for step 2.',
      'Studio lists mappings from the selected child capability input contract. Do not add arbitrary rows here; change the child capability inputs or selected child step instead.',
    ],
  },
  jsonPathMapping: {
    title: 'Technical Mapping Path',
    summary: 'This is a machine-readable pointer used by the generated runtime to copy data between parent input, child steps, and parent output.',
    inlineDetails: [
      '$.input.target_group means “use the value the caller passed to the parent capability.”',
      '$.steps.prioritize_cohort.output.result means “use the result produced by the prioritize_cohort step.”',
      'Most users should rely on the plain-language Data handoff summary and Auto-fill data handoff. Edit the technical path only when reviewing a specific generated-runtime mapping.',
    ],
  },
  emptyResultSource: {
    title: 'Can Produce Empty Source',
    summary: 'This marks a step whose result may legitimately contain no business records.',
    inlineDetails: [
      'Use Yes for selection, ranking, filtering, or lookup steps where “no matching records” is a safe outcome.',
      'When this is Yes, Empty Result Path optionally tells runtime which output field proves the result is empty.',
      'Use No for action, preparation, or rendering steps where empty output is not the expected safe-stop condition.',
    ],
  },
  outputMapping: {
    title: 'Output Mapping',
    summary: 'Output mapping defines what the parent capability returns to the caller.',
    inlineDetails: [
      'Usually the parent result points at the last child step result.',
      'Expose only the stable business response shape the consuming app should depend on.',
    ],
  },
  noResultsResponse: {
    title: 'No-Results Response',
    summary: 'This is the response returned when the configured empty-result step produces no business records.',
    inlineDetails: [
      'Use it to make safe-stop behavior explicit and testable.',
      'Keep this response simple and stable so consuming apps can render it without guessing.',
    ],
  },
  failureHandling: {
    title: 'Failure Handling',
    summary: 'This controls how child clarification, denial, approval, and unexpected errors affect the parent capability.',
    inlineDetails: [
      'Pass through to caller keeps the child outcome visible as the parent outcome.',
      'Fail composed capability turns the child outcome into a parent failure.',
      'Approval-required usually should pass through so the caller can complete the approval grant flow.',
    ],
  },
  auditLineage: {
    title: 'Audit Lineage',
    summary: 'Audit lineage controls whether the parent invocation and child invocations remain connected.',
    inlineDetails: [
      'Record child invocations when reviewers need to inspect each internal step.',
      'Keep parent task lineage when the composed behavior should appear as one business task with traceable children.',
    ],
  },
  approvalGrantPolicy: {
    title: 'Approval Grant Policy',
    summary: 'Approval grants let an approval-required capability resume only within bounded, reviewed limits.',
    inlineDetails: [
      'Enable this for capabilities that can stop for approval and later continue after an approver grants authority.',
      'One-time grants are safest for single actions. Session-bound grants can reduce friction but require tighter expiry and scope review.',
      'Expiry and maximum uses limit how long and how often the approved continuation can be used.',
    ],
  },
  capabilityInputs: {
    title: 'Capability Inputs',
    summary: 'Capability inputs are the runtime contract the consuming app must satisfy before invoking this capability.',
    inlineDetails: [
      'Use inputs to make required context, supported formats, allowed values, and clarification behavior explicit.',
      'Generator and verifier preserve these fields; consuming apps can use them to ask better questions before invocation.',
      'Do not hide required inputs in service code or prompt-only instructions when they are part of the capability contract.',
    ],
  },
  inputName: {
    title: 'Input Name',
    summary: 'The stable field name used in invocation parameters and composition mappings.',
    inlineDetails: [
      'Keep this stable once published because callers and generated code use it directly.',
      'Use concise names like quarter, account_names, cohort, or routing_target.',
    ],
  },
  inputType: {
    title: 'Input Type',
    summary: 'The expected value shape for this input.',
    inlineDetails: [
      'Common examples are string, integer, boolean, object, array<string>, or array<object>.',
      'This should describe the contract shape, not the backend storage type.',
    ],
  },
  inputRequired: {
    title: 'Required Input',
    summary: 'Required inputs must be supplied or mapped before runtime can invoke the capability.',
    inlineDetails: [
      'If missing, the service or consuming app should clarify rather than guess.',
      'Composition validation also requires every required child input to map from parent input or earlier step output.',
    ],
  },
  inputEntityReference: {
    title: 'Entity Reference',
    summary: 'Marks whether the value identifies a business thing such as account, lead, cohort, region, owner, or opportunity.',
    inlineDetails: [
      'Entity references often need explicit user context or app-level selection before invocation.',
      'Use this to help readiness checks and consuming apps avoid treating vague language as a literal identifier.',
    ],
  },
  inputSemanticType: {
    title: 'Semantic Type',
    summary: 'A human-readable category for what the input means.',
    inlineDetails: [
      'Examples: time_scope, entity_scope, view_control, decision_input, business_category.',
      'This helps assistants and consuming apps reason about inputs without hardcoded domain code.',
    ],
  },
  inputDefaultValue: {
    title: 'Default Value',
    summary: 'Optional fallback value used only when the product contract says a default is safe.',
    inlineDetails: [
      'Avoid defaults for business scope, authority, entity selection, or approval-sensitive inputs.',
      'If a missing value should trigger a question, leave this blank and use a clarification hint.',
    ],
  },
  inputSummary: {
    title: 'Input Summary',
    summary: 'Plain-language explanation of what the input represents and how it should be used.',
    inlineDetails: [
      'Write this for consuming-app developers and reviewers.',
      'Include safety constraints such as bounded cohort, visible scope, approved source window, or draft-only context.',
    ],
  },
  inputAllowedValues: {
    title: 'Allowed Values',
    summary: 'A closed set of accepted values for this input.',
    inlineDetails: [
      'Use this for real enums such as forecast modes, ranking schemes, or supported categories.',
      'Do not turn this into a giant alias list; use normalization hints for meaning and let the app clarify when uncertain.',
    ],
  },
  inputNormalizationHint: {
    title: 'Normalization Hint',
    summary: 'Guidance for converting natural user language into the declared input shape.',
    inlineDetails: [
      'Examples: normalize Q2 2017 to 2017-Q2, require explicit bounded set, or reject unsupported modes.',
      'This is reviewed contract guidance, not hidden runtime magic.',
    ],
  },
  inputNormalizationContext: {
    title: 'Normalization Context',
    summary: 'Additional bounded context needed to normalize safely.',
    inlineDetails: [
      'Examples include default fiscal year, supported fiscal calendar, or known project-specific catalog source.',
      'Use this sparingly; do not encode broad prompt behavior here.',
    ],
  },
  inputFormat: {
    title: 'Input Format',
    summary: 'Named format convention for this input.',
    inlineDetails: [
      'Examples: business_quarter, iso_date, email, slug, currency_code.',
      'Use format names when regex alone would be hard for users to understand.',
    ],
  },
  inputValidationPattern: {
    title: 'Validation Pattern',
    summary: 'Optional regex pattern for deterministic validation.',
    inlineDetails: [
      'Use only for stable syntactic checks such as quarters, email-like values, or IDs.',
      'Do not use regex as a substitute for business authorization or semantic validation.',
    ],
  },
  inputClarificationHint: {
    title: 'Clarification Hint',
    summary: 'The question or instruction to return when the input is missing, ambiguous, or malformed.',
    inlineDetails: [
      'Good hints tell the caller exactly what is missing and give examples of acceptable values.',
      'This is important for low-cost agents because it avoids guessing and reduces retry loops.',
    ],
  },
}

interface CapabilityChoice {
  value: string
  label: string
  description: string
}

const CAPABILITY_PURPOSE_OPTIONS: CapabilityChoice[] = [
  {
    value: 'business_action',
    label: 'Business action',
    description: 'A named business capability the consuming app can ask this service to perform.',
  },
  {
    value: 'read_only',
    label: 'Read-only information',
    description: 'Returns information without preparing governed work or changing downstream systems.',
  },
  {
    value: 'approval_gated',
    label: 'Approval-gated work',
    description: 'Can stop for human approval before a bounded continuation grant is used.',
  },
]

const SERVICE_ACTION_OPTIONS: CapabilityChoice[] = [
  {
    value: 'read',
    label: 'Return information',
    description: 'Read, summarize, or inspect existing business state.',
  },
  {
    value: 'retrieve',
    label: 'Retrieve records',
    description: 'Look up an existing entity, record, or bounded cohort.',
  },
  {
    value: 'compute',
    label: 'Compute or rank',
    description: 'Calculate a score, ranking, prioritization, or recommendation.',
  },
  {
    value: 'draft',
    label: 'Draft content',
    description: 'Produce draft-only content without sending, publishing, or mutating systems.',
  },
  {
    value: 'preview',
    label: 'Preview governed work',
    description: 'Prepare a safe preview of a governed action before approval or execution.',
  },
  {
    value: 'approval_gated',
    label: 'Approval-gated operation',
    description: 'Prepare governed work that may stop at an approval boundary before continuation.',
  },
  {
    value: 'write',
    label: 'Change a system',
    description: 'Perform a downstream mutation. Use sparingly and pair with explicit governance.',
  },
]

const SIDE_EFFECT_OPTIONS: CapabilityChoice[] = [
  {
    value: 'read',
    label: 'Read-only',
    description: 'No downstream state changes are expected.',
  },
  {
    value: 'draft',
    label: 'Draft-only',
    description: 'Creates draft content but does not dispatch, publish, or mutate external systems.',
  },
  {
    value: 'approval_required',
    label: 'Requires approval',
    description: 'The capability can resume only after a bounded approval grant is issued.',
  },
  {
    value: 'write',
    label: 'Writes data',
    description: 'Changes downstream state directly.',
  },
]

const CAPABILITY_SHAPE_OPTIONS: CapabilityChoice[] = [
  {
    value: 'atomic',
    label: 'Single capability',
    description: 'Use when this capability is one direct service-owned behavior.',
  },
  {
    value: 'composed',
    label: 'Composed capability',
    description: 'Use when this is still one agent-facing capability, but the same service owns ordered internal child calls.',
  },
]

const NAMED_BUSINESS_TARGET_OPTIONS: CapabilityChoice[] = [
  {
    value: 'false',
    label: 'No',
    description: 'Use when the capability can safely operate without the caller naming a specific business target.',
  },
  {
    value: 'true',
    label: 'Yes',
    description: 'Use when the caller must name a specific account, team, opportunity, cohort, region, owner, or similar target before invocation.',
  },
]

const INPUT_RESOLUTION_MODE_OPTIONS: CapabilityChoice[] = [
  {
    value: 'clarify',
    label: 'Clarify',
    description: 'Ask for a concrete value when the input is missing or unclear.',
  },
  {
    value: 'closed_values',
    label: 'Closed values',
    description: 'Accept only one of the declared allowed values.',
  },
  {
    value: 'backend_resolved',
    label: 'Backend resolved',
    description: 'Resolve the supplied reference through a provider-owned catalog or resolver.',
  },
  {
    value: 'app_selected',
    label: 'App selected',
    description: 'The consuming app must select or bind the value before invocation.',
  },
  {
    value: 'actor_policy',
    label: 'Actor policy',
    description: 'Derive the value from the actor policy, not from free text.',
  },
  {
    value: 'actor_policy_or_explicit',
    label: 'Actor policy or explicit',
    description: 'Use actor policy by default, but allow an explicit bounded value.',
  },
  {
    value: 'explicit_only',
    label: 'Explicit only',
    description: 'Use the value only when explicitly supplied; otherwise omit it.',
  },
]

const INPUT_RESOLUTION_BEHAVIOR_OPTIONS: CapabilityChoice[] = [
  {
    value: '',
    label: 'Not specified',
    description: 'Leave this behavior unset.',
  },
  {
    value: 'clarify',
    label: 'Clarify',
    description: 'Ask the caller for a concrete value.',
  },
  {
    value: 'use_default',
    label: 'Use default',
    description: 'Use the declared default value.',
  },
  {
    value: 'use_actor_scope',
    label: 'Use actor scope',
    description: 'Use the actor policy scope.',
  },
  {
    value: 'app_select_or_clarify',
    label: 'App select or clarify',
    description: 'Let the app select a value or ask the user when it cannot.',
  },
  {
    value: 'deny',
    label: 'Deny',
    description: 'Deny instead of guessing.',
  },
  {
    value: 'deny_or_clarify',
    label: 'Deny or clarify',
    description: 'Deny unsafe cases and clarify recoverable cases.',
  },
  {
    value: 'omit',
    label: 'Omit',
    description: 'Leave the optional input out.',
  },
]

function choiceOptions(options: CapabilityChoice[], current: string | undefined | null): CapabilityChoice[] {
  const normalized = String(current ?? '').trim()
  if (!normalized || options.some((option) => option.value === normalized)) return options
  const fallback = developerLabel(normalized)
  const label = options.some((option) => option.label === fallback) ? `${fallback} (saved value)` : fallback
  return [
    ...options,
    {
      value: normalized,
      label,
      description: 'Existing saved value from this project. Review before changing.',
    },
  ]
}

function choiceDescription(options: CapabilityChoice[], current: string | undefined | null): string {
  const normalized = String(current ?? '').trim()
  return choiceOptions(options, normalized).find((option) => option.value === normalized)?.description ?? ''
}

function helpChoicesFor(id: string | null): CapabilityChoice[] {
  switch (id) {
    case 'capabilityPurpose':
      return CAPABILITY_PURPOSE_OPTIONS
    case 'serviceAction':
      return SERVICE_ACTION_OPTIONS
    case 'safetySideEffect':
      return SIDE_EFFECT_OPTIONS
    case 'capabilityShape':
      return CAPABILITY_SHAPE_OPTIONS
    case 'namedBusinessTarget':
      return NAMED_BUSINESS_TARGET_OPTIONS
    default:
      return []
  }
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

function fieldHelpTitle(id: string): string {
  return expandedHelpCards.value[id] ? 'Hide help' : 'What does this mean?'
}

function capabilityFieldHelpKey(capability: DeveloperCapabilityFormalization, id: string): string {
  return `${capability.id}:${id}`
}

function capabilityFieldHelpTitle(capability: DeveloperCapabilityFormalization, id: string): string {
  return fieldHelpTitle(capabilityFieldHelpKey(capability, id))
}

function toggleCapabilityFieldHelp(capability: DeveloperCapabilityFormalization, id: string) {
  toggleHelpCard(capabilityFieldHelpKey(capability, id))
}

function capabilityFieldHelpExpanded(capability: DeveloperCapabilityFormalization, id: string): boolean {
  return Boolean(expandedHelpCards.value[capabilityFieldHelpKey(capability, id)])
}

function capabilityPath(capability: DeveloperCapabilityFormalization, field: string): string {
  return `capability_formalizations.${capability.id}.${field}`
}

function capabilityAnchorId(capability: DeveloperCapabilityFormalization): string {
  return capability.capability_id || capability.id
}

function routeHashTarget(): string {
  if (!route.hash) return ''
  try {
    return decodeURIComponent(route.hash.slice(1))
  } catch {
    return route.hash.slice(1)
  }
}

function capabilityForHash(target: string): DeveloperCapabilityFormalization | undefined {
  if (!definition.value) return undefined
  if (target.startsWith('service:')) {
    const serviceId = target.slice('service:'.length)
    return definition.value.capability_formalizations.find((capability) => capability.service_id === serviceId)
  }
  if (target.startsWith('behavior:')) {
    const serviceId = target.slice('behavior:'.length)
    return definition.value.capability_formalizations.find((capability) => capability.service_id === serviceId)
  }
  return definition.value.capability_formalizations.find((capability) => capabilityAnchorId(capability) === target)
}

async function scrollToCapabilityHash() {
  const target = routeHashTarget()
  activeCapabilityAnchor.value = target && !target.startsWith('service:') && !target.startsWith('behavior:') ? target : ''
  activeServiceAnchor.value = target.startsWith('service:') ? target.slice('service:'.length) : ''
  activeBehaviorAnchor.value = target.startsWith('behavior:') ? target.slice('behavior:'.length) : ''
  if (!target) return
  await nextTick()
  const capability = capabilityForHash(target)
  const elementId = capability ? capabilityAnchorId(capability) : target
  document.getElementById(elementId)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

onMounted(scrollToCapabilityHash)
watch(
  () => [route.hash, definition.value?.capability_formalizations.length ?? 0],
  () => {
    void scrollToCapabilityHash()
  },
)

watch(readOnly, (isReadOnly) => {
  if (isReadOnly) editing.value = false
})

function capabilityHasIssue(capability: DeveloperCapabilityFormalization): boolean {
  return hasIssueForPrefix(`capability_formalizations.${capability.id}`)
}

function addCapabilityInput(capability: DeveloperCapabilityFormalization, required: boolean) {
  capability.inputs.push({
    input_name: '',
    input_type: 'string',
    required,
    summary: '',
    default_value: '',
    allowed_values: [],
    entity_reference: false,
    semantic_type: '',
    normalization_hint: '',
    normalization_context: '',
    input_format: '',
    validation_pattern: '',
    clarification_hint: '',
    resolution: {
      mode: required ? 'clarify' : 'explicit_only',
      on_missing: required ? 'clarify' : 'omit',
    },
  })
}

function openInputContractEvidencePanel() {
  inputContractEvidenceError.value = ''
  inputContractEvidenceStatus.value = ''
  evidencePanelOpen.value = true
  if (!inputContractEvidenceText.value.trim()) {
    inputContractEvidenceText.value = JSON.stringify({
      capabilities: (definition.value?.capability_formalizations ?? []).map((capability) => ({
        capability_id: capability.capability_id,
        inputs: [
          {
            input_name: '',
            input_type: 'string',
            required: true,
            summary: '',
            semantic_type: '',
            allowed_values: [],
            resolution: {
              mode: 'clarify',
              on_missing: 'clarify',
            },
          },
        ],
      })),
    }, null, 2)
  }
}

async function importInputContractEvidence() {
  if (!project.value || !definition.value) return
  inputContractEvidenceError.value = ''
  inputContractEvidenceStatus.value = ''
  importingInputContractEvidence.value = true
  try {
    const evidence = parseInputContractEvidence(inputContractEvidenceText.value)
    const applied = applyInputContractEvidence(definition.value.capability_formalizations, evidence)
    const details = [
      applied.unknownCapabilityIds.length ? `Unknown capabilities ignored: ${applied.unknownCapabilityIds.join(', ')}` : '',
      applied.missingInputCapabilityIds.length ? `Capabilities without inputs ignored: ${applied.missingInputCapabilityIds.join(', ')}` : '',
      evidence.warnings.length ? evidence.warnings.join(' ') : '',
    ].filter(Boolean)
    if (applied.matchedCapabilityIds.length === 0) {
      throw new Error(details.join(' ') || 'No pasted input contracts matched current project capabilities.')
    }

    const items = inputContractEvidenceArtifactItems({
      capabilities: evidence.capabilities.filter((capability) =>
        applied.matchedCapabilityIds.includes(capability.capability_id),
      ),
      warnings: evidence.warnings,
    })
    await createPmArtifact(project.value.id, {
      id: `assistant-input-contracts-${crypto.randomUUID()}`,
      title: 'Reviewed Input Contract Evidence',
      data: {
        artifact_type: 'assistant_input_contract_candidates',
        source_capability: 'manual_input_contract_import',
        proposal_kind: 'candidate_blocks',
        accepted_item_ids: items.map((item) => String(item.client_id ?? '')),
        rejected_item_ids: [],
        accepted_payload: items,
        source_proposal: {
          proposal_kind: 'candidate_blocks',
          artifact_type: 'input_contracts',
          items,
        },
        notes: 'Imported reviewed input-contract evidence from Capability Formalization.',
        imported_at: new Date().toISOString(),
      },
    })
    await loadProject(project.value.id)
    resetDefinition()
    inputContractEvidenceStatus.value = `Imported ${applied.matchedCapabilityIds.length} capability input contract${applied.matchedCapabilityIds.length === 1 ? '' : 's'}. Review the fields, then save formalization.`
    if (details.length) inputContractEvidenceStatus.value += ` ${details.join(' ')}`
    evidencePanelOpen.value = false
  } catch (error) {
    inputContractEvidenceError.value = (error as Error).message
  } finally {
    importingInputContractEvidence.value = false
  }
}

function booleanString(value: boolean | undefined): string {
  return value ? 'true' : 'false'
}

function setEntityTargeted(capability: DeveloperCapabilityFormalization, value: string) {
  capability.entity_targeted = value === 'true'
}

function allowedValuesText(capability: DeveloperCapabilityFormalization, inputIndex: number): string {
  return capability.inputs[inputIndex]?.allowed_values.join(', ') ?? ''
}

function setAllowedValues(capability: DeveloperCapabilityFormalization, inputIndex: number, value: string) {
  const input = capability.inputs[inputIndex]
  if (!input) return
  input.allowed_values = value
    .split(/[;,]/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function defaultResolutionMode(input: DeveloperCapabilityInputFormalization): DeveloperCapabilityInputResolutionMode {
  return input.required ? 'clarify' : 'explicit_only'
}

function defaultMissingBehavior(input: DeveloperCapabilityInputFormalization): DeveloperCapabilityInputResolutionBehavior {
  return input.required ? 'clarify' : 'omit'
}

function ensureInputResolution(input: DeveloperCapabilityInputFormalization) {
  if (!input.resolution) {
    input.resolution = {
      mode: defaultResolutionMode(input),
      on_missing: defaultMissingBehavior(input),
    }
  }
  return input.resolution
}

function setInputResolutionMode(input: DeveloperCapabilityInputFormalization, value: string) {
  ensureInputResolution(input).mode = (value || defaultResolutionMode(input)) as DeveloperCapabilityInputResolutionMode
}

function inputResolutionBehavior(input: DeveloperCapabilityInputFormalization, field: 'on_missing' | 'on_ambiguous' | 'on_unresolved'): string {
  return input.resolution?.[field] ?? ''
}

function setInputResolutionBehavior(
  input: DeveloperCapabilityInputFormalization,
  field: 'on_missing' | 'on_ambiguous' | 'on_unresolved',
  value: string,
) {
  const resolution = ensureInputResolution(input)
  if (!value) {
    delete resolution[field]
    return
  }
  resolution[field] = value as DeveloperCapabilityInputResolutionBehavior
}

function inputResolverRef(input: DeveloperCapabilityInputFormalization): string {
  return input.resolution?.resolver_ref ?? ''
}

function setInputResolverRef(input: DeveloperCapabilityInputFormalization, value: string) {
  const resolution = ensureInputResolution(input)
  const nextValue = value.trim()
  if (nextValue) resolution.resolver_ref = nextValue
  else delete resolution.resolver_ref
}

function capabilityKind(capability: DeveloperCapabilityFormalization): DeveloperCapabilityKind {
  return capability.kind === 'composed' ? 'composed' : 'atomic'
}

function capabilityProduces(capability: DeveloperCapabilityFormalization): string {
  return formatEffectList(capability.business_effects?.produces)
}

function capabilityDoesNotProduce(capability: DeveloperCapabilityFormalization): string {
  return formatEffectList(capability.business_effects?.does_not_produce)
}

function capabilityTechnicalEffects(capability: DeveloperCapabilityFormalization): string {
  return technicalEffectLabel([
    ...(capability.business_effects?.produces ?? []),
    ...(capability.business_effects?.does_not_produce ?? []),
  ])
}

function effectListText(values: string[] | undefined): string {
  return (values ?? []).join(', ')
}

function parseEffectList(value: string): string[] {
  return value
    .split(/[;,]/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function setCapabilityEffectList(
  capability: DeveloperCapabilityFormalization,
  field: 'produces' | 'does_not_produce',
  value: string,
) {
  const current = capability.business_effects ?? { produces: [], does_not_produce: [] }
  capability.business_effects = {
    produces: field === 'produces' ? parseEffectList(value) : [...current.produces],
    does_not_produce: field === 'does_not_produce' ? parseEffectList(value) : [...current.does_not_produce],
  }
}

function inputBehaviorRuleCount(capability: DeveloperCapabilityFormalization): number {
  return capability.inputs.filter((input) =>
    input.input_format || input.validation_pattern || input.clarification_hint,
  ).length
}

function inputClarificationCount(capability: DeveloperCapabilityFormalization): number {
  return capability.inputs.filter((input) => input.clarification_hint).length
}

const INPUT_DISPLAY_LABELS: Record<string, string> = {
  account_names: 'Account names',
  cohort: 'Target group',
  quarter: 'Quarter',
  ranking_scheme: 'Ranking scheme',
  routing_target: 'Routing target',
  source_window: 'Source window',
  target_entities: 'Target entities',
}

function inputDisplayLabel(inputName: string | undefined | null): string {
  const normalized = String(inputName || '').trim()
  if (!normalized) return 'Unnamed input'
  return INPUT_DISPLAY_LABELS[normalized.toLowerCase()] ?? normalized
}

function startEditing(): void {
  if (readOnly.value) return
  editing.value = true
}

function cancelEditing(): void {
  resetDefinition()
  editing.value = false
}

async function saveAndReview(): Promise<void> {
  if (readOnly.value) return
  await saveDraft()
  if (!saveError.value) {
    editing.value = false
  }
}

function setCapabilityKind(capability: DeveloperCapabilityFormalization, value: string) {
  capability.kind = value === 'composed' ? 'composed' : 'atomic'
  if (capability.kind === 'atomic') {
    capability.composition = null
  } else {
    ensureComposition(capability)
  }
}

function defaultComposition(): DeveloperComposition {
  return {
    authority_boundary: 'same_service',
    steps: [],
    input_mapping: {},
    output_mapping: {
      result: '$.steps.step_1.output.result',
    },
    empty_result_policy: null,
    empty_result_output: null,
    failure_policy: {
      child_clarification: 'propagate',
      child_denial: 'propagate',
      child_approval_required: 'propagate',
      child_error: 'propagate',
    },
    audit_policy: {
      record_child_invocations: true,
      parent_task_lineage: true,
    },
  }
}

function ensureComposition(capability: DeveloperCapabilityFormalization): DeveloperComposition {
  if (!capability.composition) {
    capability.composition = defaultComposition()
  }
  capability.composition.authority_boundary = 'same_service'
  capability.composition.steps ??= []
  capability.composition.input_mapping ??= {}
  capability.composition.output_mapping ??= {}
  capability.composition.failure_policy ??= defaultComposition().failure_policy
  capability.composition.audit_policy ??= defaultComposition().audit_policy
  return capability.composition
}

function sameServiceAtomicOptions(capability: DeveloperCapabilityFormalization): DeveloperCapabilityFormalization[] {
  if (!definition.value) return []
  return definition.value.capability_formalizations.filter((candidate) =>
    candidate.id !== capability.id
    && candidate.service_id === capability.service_id
    && capabilityKind(candidate) === 'atomic'
    && Boolean(candidate.capability_id),
  )
}

function nextStepId(composition: DeveloperComposition): string {
  let index = composition.steps.length + 1
  const existing = new Set(composition.steps.map((step) => step.id))
  while (existing.has(`step_${index}`)) index += 1
  return `step_${index}`
}

function addCompositionStep(capability: DeveloperCapabilityFormalization) {
  const composition = ensureComposition(capability)
  const stepId = nextStepId(composition)
  const firstCapability = sameServiceAtomicOptions(capability).find((candidate) =>
    !composition.steps.some((step) => step.capability === candidate.capability_id),
  )
  composition.steps.push({
    id: stepId,
    capability: firstCapability?.capability_id ?? '',
    empty_result_source: false,
    empty_result_path: '',
  })
  composition.input_mapping[stepId] = {}
  if (!composition.output_mapping.result) {
    composition.output_mapping.result = `$.steps.${stepId}.output.result`
  }
}

function removeCompositionStep(capability: DeveloperCapabilityFormalization, stepIndex: number) {
  const composition = ensureComposition(capability)
  const [removed] = composition.steps.splice(stepIndex, 1)
  if (removed) {
    delete composition.input_mapping[removed.id]
  }
}

function setCompositionStepId(capability: DeveloperCapabilityFormalization, step: DeveloperCompositionStep, value: string) {
  const composition = ensureComposition(capability)
  const nextId = value.trim()
  if (!nextId || nextId === step.id) return
  const previousId = step.id
  step.id = nextId
  composition.input_mapping[nextId] = composition.input_mapping[previousId] ?? {}
  delete composition.input_mapping[previousId]
  for (const [field, path] of Object.entries(composition.output_mapping)) {
    composition.output_mapping[field] = path.replace(`$.steps.${previousId}.`, `$.steps.${nextId}.`)
  }
}

function childCapabilityForStep(step: DeveloperCompositionStep): DeveloperCapabilityFormalization | undefined {
  return definition.value?.capability_formalizations.find((capability) => capability.capability_id === step.capability)
}

function capabilityDisplayName(capabilityId: string): string {
  const capability = definition.value?.capability_formalizations.find((candidate) => candidate.capability_id === capabilityId)
  return capability?.title || capability?.capability_id || capabilityId || 'Select capability'
}

function stepLabel(step: DeveloperCompositionStep, index: number): string {
  return step.capability ? capabilityDisplayName(step.capability) : `Choose step ${index + 1}`
}

function pathDescription(path: string): string {
  if (!path) return 'Not mapped yet'
  const parentMatch = path.match(/^\$\.input\.([A-Za-z0-9_.-]+)$/)
  if (parentMatch) return `caller provides “${inputDisplayLabel(parentMatch[1])}”`
  const stepMatch = path.match(/^\$\.steps\.([A-Za-z0-9_.-]+)\.output(?:\.result)?(?:\.([A-Za-z0-9_.-]+))?$/)
  if (stepMatch) {
    const sourceStep = stepMatch[1]
    const sourceField = stepMatch[2] || 'result'
    return `use ${sourceField} from step “${sourceStep}”`
  }
  return path
}

function inputMappingDescription(capability: DeveloperCapabilityFormalization, step: DeveloperCompositionStep, input: DeveloperCapabilityInputFormalization): string {
  return `${inputDisplayLabel(input.input_name)}: ${pathDescription(inputMappingValue(capability, step, input))}`
}

function outputMappingDescription(field: string, path: string): string {
  return `${field}: ${pathDescription(path)}`
}

function isInputLikelyProducedByPriorStep(input: DeveloperCapabilityInputFormalization): boolean {
  const semanticType = String(input.semantic_type || '').toLowerCase()
  const inputName = String(input.input_name || '').toLowerCase()
  return Boolean(input.entity_reference)
    || semanticType.includes('entity')
    || semanticType.includes('reference')
    || semanticType.includes('target')
    || semanticType.includes('scope')
    || inputName.includes('target')
}

function suggestedMappingForInput(stepIndex: number, previousStep: DeveloperCompositionStep | undefined, input: DeveloperCapabilityInputFormalization): string {
  if (stepIndex > 0 && previousStep && isInputLikelyProducedByPriorStep(input)) {
    return `$.steps.${previousStep.id}.output.result`
  }
  return `$.input.${input.input_name}`
}

function autoFillCompositionMappings(capability: DeveloperCapabilityFormalization): void {
  const composition = ensureComposition(capability)
  composition.steps.forEach((step, stepIndex) => {
    const childCapability = childCapabilityForStep(step)
    composition.input_mapping[step.id] ??= {}
    childCapability?.inputs.forEach((input) => {
      if (!composition.input_mapping[step.id]?.[input.input_name]) {
        composition.input_mapping[step.id][input.input_name] = suggestedMappingForInput(stepIndex, composition.steps[stepIndex - 1], input)
      }
    })
  })
  const lastStep = composition.steps[composition.steps.length - 1]
  if (lastStep && !composition.output_mapping.result) {
    composition.output_mapping.result = `$.steps.${lastStep.id}.output.result`
  }
}

function inputMappingValue(capability: DeveloperCapabilityFormalization, step: DeveloperCompositionStep, input: DeveloperCapabilityInputFormalization): string {
  const mapping = ensureComposition(capability).input_mapping[step.id] ?? {}
  if (Object.prototype.hasOwnProperty.call(mapping, input.input_name)) {
    return mapping[input.input_name] ?? ''
  }
  return input.required ? `$.input.${input.input_name}` : ''
}

function setInputMappingValue(capability: DeveloperCapabilityFormalization, step: DeveloperCompositionStep, inputName: string, value: string) {
  const composition = ensureComposition(capability)
  composition.input_mapping[step.id] ??= {}
  const nextValue = value.trim()
  if (!nextValue) {
    delete composition.input_mapping[step.id][inputName]
    return
  }
  composition.input_mapping[step.id][inputName] = nextValue
}

function outputMappingEntries(capability: DeveloperCapabilityFormalization): Array<[string, string]> {
  return Object.entries(ensureComposition(capability).output_mapping)
}

function addOutputMapping(capability: DeveloperCapabilityFormalization) {
  const composition = ensureComposition(capability)
  let index = Object.keys(composition.output_mapping).length + 1
  while (`field_${index}` in composition.output_mapping) index += 1
  const firstStep = composition.steps[composition.steps.length - 1]?.id ?? 'step_1'
  composition.output_mapping[`field_${index}`] = `$.steps.${firstStep}.output.result`
}

function setOutputMappingKey(capability: DeveloperCapabilityFormalization, previousKey: string, value: string) {
  const composition = ensureComposition(capability)
  const nextKey = value.trim()
  if (!nextKey || nextKey === previousKey) return
  const currentValue = composition.output_mapping[previousKey]
  delete composition.output_mapping[previousKey]
  composition.output_mapping[nextKey] = currentValue
}

function setOutputMappingValue(capability: DeveloperCapabilityFormalization, key: string, value: string) {
  ensureComposition(capability).output_mapping[key] = value.trim()
}

function removeOutputMapping(capability: DeveloperCapabilityFormalization, key: string) {
  delete ensureComposition(capability).output_mapping[key]
}

function emptyResultOutputEntries(capability: DeveloperCapabilityFormalization): Array<[string, string]> {
  const output = ensureComposition(capability).empty_result_output ?? {}
  return Object.entries(output).map(([key, value]) => [key, String(value)])
}

function addEmptyResultOutput(capability: DeveloperCapabilityFormalization) {
  const composition = ensureComposition(capability)
  composition.empty_result_output ??= {}
  let index = Object.keys(composition.empty_result_output).length + 1
  while (`field_${index}` in composition.empty_result_output) index += 1
  composition.empty_result_output[`field_${index}`] = ''
}

function setEmptyResultOutputKey(capability: DeveloperCapabilityFormalization, previousKey: string, value: string) {
  const composition = ensureComposition(capability)
  composition.empty_result_output ??= {}
  const nextKey = value.trim()
  if (!nextKey || nextKey === previousKey) return
  const currentValue = composition.empty_result_output[previousKey]
  delete composition.empty_result_output[previousKey]
  composition.empty_result_output[nextKey] = currentValue
}

function setEmptyResultOutputValue(capability: DeveloperCapabilityFormalization, key: string, value: string) {
  const composition = ensureComposition(capability)
  composition.empty_result_output ??= {}
  composition.empty_result_output[key] = value
}

function removeEmptyResultOutput(capability: DeveloperCapabilityFormalization, key: string) {
  const composition = ensureComposition(capability)
  if (!composition.empty_result_output) return
  delete composition.empty_result_output[key]
}

function defaultGrantPolicy(): DeveloperGrantPolicy {
  return {
    allowed_grant_types: ['one_time'],
    default_grant_type: 'one_time',
    expires_in_seconds: 900,
    max_uses: 1,
  }
}

function setGrantPolicyEnabled(capability: DeveloperCapabilityFormalization, value: string) {
  capability.grant_policy = value === 'true' ? (capability.grant_policy ?? defaultGrantPolicy()) : null
}

function grantTypeAllowed(capability: DeveloperCapabilityFormalization, grantType: DeveloperGrantType): boolean {
  return Boolean(capability.grant_policy?.allowed_grant_types.includes(grantType))
}

function setGrantTypeAllowed(capability: DeveloperCapabilityFormalization, grantType: DeveloperGrantType, checked: boolean) {
  const policy = capability.grant_policy ?? defaultGrantPolicy()
  const set = new Set(policy.allowed_grant_types)
  if (checked) set.add(grantType)
  else set.delete(grantType)
  policy.allowed_grant_types = [...set] as DeveloperGrantType[]
  if (!policy.allowed_grant_types.includes(policy.default_grant_type)) {
    policy.default_grant_type = policy.allowed_grant_types[0] ?? 'one_time'
  }
  capability.grant_policy = policy
}

function setGrantPolicyNumber(capability: DeveloperCapabilityFormalization, field: 'expires_in_seconds' | 'max_uses', value: string) {
  const policy = capability.grant_policy ?? defaultGrantPolicy()
  policy[field] = Math.max(1, Number(value) || 1)
  capability.grant_policy = policy
}

function setDefaultGrantType(capability: DeveloperCapabilityFormalization, value: string) {
  const policy = capability.grant_policy ?? defaultGrantPolicy()
  const grantType = value === 'session_bound' ? 'session_bound' : 'one_time'
  if (!policy.allowed_grant_types.includes(grantType)) {
    policy.allowed_grant_types = [...policy.allowed_grant_types, grantType]
  }
  policy.default_grant_type = grantType
  capability.grant_policy = policy
}
</script>

<template>
  <div class="developer-definition">
    <template v-if="project">
      <section class="page-header">
        <button class="back-link" type="button" @click="router.push(`/design/projects/${project.id}/developer`)">
          &larr; Back to Developer Design
        </button>
        <div class="page-kicker">Developer Design</div>
        <h1>Capability Formalization</h1>
        <p>
          Formalize the ANIP-facing capability contracts here. This page exists to answer one concrete question: which explicit ANIP capability surface should generation, verification, and observed-service metadata recognize for each bounded action?
        </p>
      </section>
      <ProjectIssueBanner :issue="pageIssue" title="Capability Contract diagnostics" />
      <section v-if="!baseline" class="panel empty-panel">
        <h2>Developer baseline is not locked</h2>
        <p>Return to Developer Overview and lock Product Design before formalizing capabilities.</p>
      </section>

      <section v-else-if="!baselineAligned" class="panel empty-panel">
        <h2>Locked baseline is out of sync</h2>
        <p>Product Design changed after the current developer baseline was locked. Re-lock the baseline before continuing.</p>
      </section>

      <section v-else-if="definition" class="grid" :class="{ 'review-mode': !editing, 'edit-mode': editing }">
        <article id="capability-contracts" class="panel panel-full">
          <div class="panel-header">
            <h2>Capability Contracts</h2>
            <div class="header-actions">
              <button class="btn btn-secondary" type="button" :disabled="readOnly || importingInputContractEvidence" @click="openInputContractEvidencePanel">
                Import Input Contracts
              </button>
              <button v-if="!editing" class="btn btn-secondary" type="button" :disabled="readOnly" @click="startEditing">
                Edit Contracts
              </button>
              <button v-if="editing" class="btn btn-secondary" type="button" :disabled="saving" @click="cancelEditing">
                Cancel
              </button>
              <button v-if="editing" class="btn btn-primary" :disabled="readOnly || saving" @click="saveAndReview">
                {{ saving ? 'Saving…' : 'Save Formalization' }}
              </button>
            </div>
          </div>
          <p v-if="saveError" class="error">{{ saveError }}</p>
          <p v-if="inputContractEvidenceStatus" class="success">{{ inputContractEvidenceStatus }}</p>
          <section v-if="evidencePanelOpen" class="evidence-import-panel">
            <div class="evidence-import-header">
              <div>
                <h3>Import Reviewed Input Contract Evidence</h3>
                <p>
                  Paste developer-reviewed JSON that maps each capability id to its runtime inputs. Studio stores it as accepted input-contract evidence, then rebuilds this page from that evidence.
                </p>
              </div>
              <button class="btn btn-secondary" type="button" :disabled="importingInputContractEvidence" @click="evidencePanelOpen = false">
                Close
              </button>
            </div>
            <textarea
              v-model="inputContractEvidenceText"
              class="textarea mono-textarea evidence-textarea"
              rows="14"
              spellcheck="false"
              placeholder='{"capabilities":[{"capability_id":"gtm.pipeline_summary","inputs":[{"input_name":"quarter","input_type":"string","required":true,"semantic_type":"time_scope","resolution":{"mode":"clarify","on_missing":"clarify"}}]}]}'
            />
            <p v-if="inputContractEvidenceError" class="error">{{ inputContractEvidenceError }}</p>
            <div class="evidence-import-actions">
              <button class="btn btn-primary" type="button" :disabled="readOnly || importingInputContractEvidence" @click="importInputContractEvidence">
                {{ importingInputContractEvidence ? 'Importing…' : 'Import Evidence' }}
              </button>
              <span class="helper-text">Accepted shapes: `capabilities`, `capability_formalizations`, `input_contracts`, or a capability-id keyed object.</span>
            </div>
          </section>
          <p class="panel-copy">
            Use this page for capability-level contract data only. A capability contract tells Studio which service owns an action, what the stable capability id is, what kind of side effect it has, and which backend operation it binds to. The old Integration Pattern page should follow these definitions, not invent them.
          </p>
          <p class="panel-copy why-copy">
            Why this matters: reviewers should reason about human behavior first, while Studio keeps the technical identifiers available for generator, verifier, and Registry traceability.
          </p>
          <div v-if="definition.capability_formalizations.length" class="capability-list">
            <article
              v-for="capability in definition.capability_formalizations"
              :id="capabilityAnchorId(capability)"
              :key="capability.id"
              class="capability-card"
              :class="{
                'field-error-card': capabilityHasIssue(capability),
                'anchored-card': activeCapabilityAnchor === capabilityAnchorId(capability),
                'service-anchored-card': activeServiceAnchor === capability.service_id,
                'behavior-anchored-card': activeBehaviorAnchor === capability.service_id,
              }"
            >
              <details class="review-collapse review-only">
                <summary>
                  <div class="review-collapse-summary">
                    <div class="review-collapse-title">
                      <h3>{{ capability.title || capability.capability_id || 'Capability' }}</h3>
                      <p class="review-collapse-meta">
                        {{ capability.capability_id || 'Capability ID not set' }}
                        <template v-if="serviceOptions.find((service) => service.id === capability.service_id)?.label || capability.service_id">
                          · {{ serviceOptions.find((service) => service.id === capability.service_id)?.label || capability.service_id }}
                        </template>
                      </p>
                    </div>
                    <div class="review-collapse-badges">
                      <span class="review-collapse-badge" :class="capabilityKind(capability)">{{ developerLabel(capabilityKind(capability)) }}</span>
                      <span class="review-collapse-badge">{{ developerLabel(capability.intent_type, 'Intent not set') }}</span>
                      <span class="review-collapse-badge">{{ developerLabel(capability.side_effect_level, 'Side effect not set') }}</span>
                      <span class="review-collapse-badge">{{ capability.inputs.length }} inputs</span>
                      <span class="review-collapse-toggle">View all saved values</span>
                    </div>
                  </div>
                </summary>
                <div class="review-collapse-body">
                  <div class="review-summary-grid">
                    <div class="review-summary-card"><strong>Capability ID</strong><span>{{ capability.capability_id || 'Not set' }}</span></div>
                    <div class="review-summary-card"><strong>Owning Service</strong><span>{{ serviceOptions.find((service) => service.id === capability.service_id)?.label || capability.service_id || 'Not specified' }}</span></div>
                    <div class="review-summary-card"><strong>Intent</strong><span>{{ developerLabel(capability.intent_type) }} / {{ developerLabel(capability.operation_type) }}</span></div>
                    <div class="review-summary-card"><strong>Capability Kind</strong><span>{{ developerLabel(capabilityKind(capability)) }}</span></div>
                    <div class="review-summary-card"><strong>Side Effect</strong><span>{{ developerLabel(capability.side_effect_level) }}</span></div>
                    <div class="review-summary-card">
                      <strong>Produces</strong>
                      <span :title="technicalHoverLabel([...(capability.business_effects?.produces ?? []), ...(capability.business_effects?.does_not_produce ?? [])].join(', '))">{{ capabilityProduces(capability) }}</span>
                      <small v-if="showTechnicalIdentifiers">{{ capabilityTechnicalEffects(capability) }}</small>
                    </div>
                    <div class="review-summary-card">
                      <strong>Does Not Produce</strong>
                      <span>{{ capabilityDoesNotProduce(capability) }}</span>
                    </div>
                    <div class="review-summary-card"><strong>Backend Operation</strong><span>{{ capability.backend_operation || 'Not set' }}</span></div>
                    <div class="review-summary-card"><strong>Output</strong><span>{{ capability.output_shape || capability.output_intent || 'Not specified' }}</span></div>
                    <div class="review-summary-card" v-if="capabilityKind(capability) === 'composed'"><strong>Composition Steps</strong><span>{{ capability.composition?.steps?.map((step) => step.capability).join(' -> ') || 'Not defined' }}</span></div>
                    <div class="review-summary-card" v-if="capability.grant_policy"><strong>Approval Grants</strong><span>{{ capability.grant_policy.default_grant_type }} · {{ capability.grant_policy.max_uses }} use{{ capability.grant_policy.max_uses === 1 ? '' : 's' }}</span></div>
                    <div class="review-summary-card field-wide"><strong>Summary</strong><p>{{ capability.summary || 'No summary recorded.' }}</p></div>
                    <div class="review-summary-card"><strong>Inputs</strong><span>{{ capability.inputs.length }} total, {{ capability.inputs.filter((input) => input.required).length }} required</span></div>
                    <div class="review-summary-card" v-if="inputBehaviorRuleCount(capability)">
                      <strong>Input Behavior</strong>
                      <span>{{ inputBehaviorRuleCount(capability) }} input behavior rule{{ inputBehaviorRuleCount(capability) === 1 ? '' : 's' }}</span>
                    </div>
                    <div class="review-summary-card service-contract-card" v-if="inputClarificationCount(capability)">
                      <strong>Runtime Clarification</strong>
                      <span>{{ inputClarificationCount(capability) }} service-contract prompt{{ inputClarificationCount(capability) === 1 ? '' : 's' }} configured</span>
                    </div>
                    <div class="review-summary-card"><strong>Subject</strong><span>{{ capability.subject_kind || 'Not specified' }}</span></div>
                  </div>
                </div>
              </details>

              <details class="review-collapse edit-collapse edit-only">
                <summary>
                  <div class="review-collapse-summary">
                    <div class="review-collapse-title">
                      <h3>{{ capability.title || capability.capability_id || 'Capability' }}</h3>
                      <p class="review-collapse-meta">
                        {{ capability.capability_id || 'Capability ID not set' }}
                        <template v-if="serviceOptions.find((service) => service.id === capability.service_id)?.label || capability.service_id">
                          · {{ serviceOptions.find((service) => service.id === capability.service_id)?.label || capability.service_id }}
                        </template>
                      </p>
                      <p class="meta">
                        Source:
                        <span class="source-badge" :class="capability.source_kind">
                          {{ capability.source_kind === 'application_integration' ? 'Integration Pattern' : 'Data Access Pattern' }}
                        </span>
                      </p>
                      <p
                        v-for="message in messagesForPrefix(`capability_formalizations.${capability.id}`)"
                        :key="message"
                        class="inline-field-error"
                      >
                        {{ message }}
                      </p>
                    </div>
                    <div class="review-collapse-badges">
                      <span class="review-collapse-badge" :class="capabilityKind(capability)">{{ developerLabel(capabilityKind(capability)) }}</span>
                      <span class="review-collapse-badge">{{ developerLabel(capability.intent_type, 'Intent not set') }}</span>
                      <span class="review-collapse-badge">{{ developerLabel(capability.side_effect_level, 'Side effect not set') }}</span>
                      <span class="review-collapse-badge">{{ capability.inputs.length }} inputs</span>
                      <span class="review-collapse-toggle">Edit this capability</span>
                    </div>
                  </div>
                </summary>
                <div class="edit-collapse-body">
              <div class="settings-grid">
                <label class="field" :class="{ 'field-error': hasIssueForPath(capabilityPath(capability, 'capability_id')) }">
                  <div class="field-label-row">
                    <span class="required-label">Stable Capability ID</span>
                    <span class="field-help-actions">
                      <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'stableCapabilityId')">{{ capabilityFieldHelpTitle(capability, 'stableCapabilityId') }}</button>
                    </span>
                  </div>
                  <input
                    :value="capability.capability_id"
                    class="input"
                    placeholder="e.g. domain.capability_name"
                    @input="setCapabilityField(capability, 'capability_id', ($event.target as HTMLInputElement).value)"
                  />
                  <small>Durable contract identity used by Registry, verifier, generator, and consuming apps.</small>
                  <div v-if="capabilityFieldHelpExpanded(capability, 'stableCapabilityId')" class="inline-help field-inline-help">
                    <p class="inline-help-summary">{{ CAPABILITY_FIELD_HELP.stableCapabilityId.summary }}</p>
                    <ul class="inline-help-list">
                      <li v-for="detail in CAPABILITY_FIELD_HELP.stableCapabilityId.inlineDetails" :key="detail">{{ detail }}</li>
                    </ul>
                  </div>
                  <small v-for="message in messagesForPath(capabilityPath(capability, 'capability_id'))" :key="message" class="field-error-copy">{{ message }}</small>
                </label>
                <label class="field" :class="{ 'field-error': hasIssueForPath(capabilityPath(capability, 'title')) }">
                  <div class="field-label-row">
                    <span class="required-label">Display Name</span>
                    <span class="field-help-actions">
                      <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'displayName')">{{ capabilityFieldHelpTitle(capability, 'displayName') }}</button>
                    </span>
                  </div>
                  <input
                    :value="capability.title"
                    class="input"
                    placeholder="Capability title"
                    @input="setCapabilityField(capability, 'title', ($event.target as HTMLInputElement).value)"
                  />
                  <div v-if="capabilityFieldHelpExpanded(capability, 'displayName')" class="inline-help field-inline-help">
                    <p class="inline-help-summary">{{ CAPABILITY_FIELD_HELP.displayName.summary }}</p>
                    <ul class="inline-help-list">
                      <li v-for="detail in CAPABILITY_FIELD_HELP.displayName.inlineDetails" :key="detail">{{ detail }}</li>
                    </ul>
                  </div>
                  <small v-for="message in messagesForPath(capabilityPath(capability, 'title'))" :key="message" class="field-error-copy">{{ message }}</small>
                </label>
                <label class="field">
                  <div class="field-label-row">
                    <span>Owning Service</span>
                    <span class="field-help-actions">
                      <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'owningService')">{{ capabilityFieldHelpTitle(capability, 'owningService') }}</button>
                    </span>
                  </div>
                  <select
                    :value="capability.service_id"
                    class="select"
                    @change="setCapabilityField(capability, 'service_id', ($event.target as HTMLSelectElement).value)"
                  >
                    <option value="">Not specified</option>
                    <option v-for="service in serviceOptions" :key="service.id" :value="service.id">{{ service.label }}</option>
                  </select>
                  <div v-if="capabilityFieldHelpExpanded(capability, 'owningService')" class="inline-help field-inline-help">
                    <p class="inline-help-summary">{{ CAPABILITY_FIELD_HELP.owningService.summary }}</p>
                    <ul class="inline-help-list">
                      <li v-for="detail in CAPABILITY_FIELD_HELP.owningService.inlineDetails" :key="detail">{{ detail }}</li>
                    </ul>
                  </div>
                </label>
                <label class="field" :class="{ 'field-error': hasIssueForPath(capabilityPath(capability, 'intent_type')) }">
                  <div class="field-label-row">
                    <span class="required-label">Capability Purpose</span>
                    <span class="field-help-actions">
                      <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'capabilityPurpose')">{{ capabilityFieldHelpTitle(capability, 'capabilityPurpose') }}</button>
                      <button class="help-link secondary" type="button" @click.stop.prevent="openHelpCard('capabilityPurpose')">More detail</button>
                    </span>
                  </div>
                  <select
                    :value="capability.intent_type"
                    class="select"
                    :title="technicalHoverLabel(capability.intent_type)"
                    @change="setCapabilityField(capability, 'intent_type', ($event.target as HTMLSelectElement).value)"
                  >
                    <option v-for="option in choiceOptions(CAPABILITY_PURPOSE_OPTIONS, capability.intent_type)" :key="option.value" :value="option.value">
                      {{ option.label }}
                    </option>
                  </select>
                  <small>{{ choiceDescription(CAPABILITY_PURPOSE_OPTIONS, capability.intent_type) }}</small>
                  <div v-if="capabilityFieldHelpExpanded(capability, 'capabilityPurpose')" class="inline-help field-inline-help">
                    <p class="inline-help-summary">{{ CAPABILITY_FIELD_HELP.capabilityPurpose.summary }}</p>
                    <ul class="inline-help-list">
                      <li v-for="detail in CAPABILITY_FIELD_HELP.capabilityPurpose.inlineDetails" :key="detail">{{ detail }}</li>
                    </ul>
                  </div>
                  <small v-for="message in messagesForPath(capabilityPath(capability, 'intent_type'))" :key="message" class="field-error-copy">{{ message }}</small>
                </label>
                <label class="field" :class="{ 'field-error': hasIssueForPath(capabilityPath(capability, 'operation_type')) }">
                  <div class="field-label-row">
                    <span class="required-label">Service Action</span>
                    <span class="field-help-actions">
                      <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'serviceAction')">{{ capabilityFieldHelpTitle(capability, 'serviceAction') }}</button>
                      <button class="help-link secondary" type="button" @click.stop.prevent="openHelpCard('serviceAction')">More detail</button>
                    </span>
                  </div>
                  <select
                    :value="capability.operation_type"
                    class="select"
                    :title="technicalHoverLabel(capability.operation_type)"
                    @change="setCapabilityField(capability, 'operation_type', ($event.target as HTMLSelectElement).value)"
                  >
                    <option v-for="option in choiceOptions(SERVICE_ACTION_OPTIONS, capability.operation_type)" :key="option.value" :value="option.value">
                      {{ option.label }}
                    </option>
                  </select>
                  <small>{{ choiceDescription(SERVICE_ACTION_OPTIONS, capability.operation_type) }}</small>
                  <div v-if="capabilityFieldHelpExpanded(capability, 'serviceAction')" class="inline-help field-inline-help">
                    <p class="inline-help-summary">{{ CAPABILITY_FIELD_HELP.serviceAction.summary }}</p>
                    <ul class="inline-help-list">
                      <li v-for="detail in CAPABILITY_FIELD_HELP.serviceAction.inlineDetails" :key="detail">{{ detail }}</li>
                    </ul>
                  </div>
                  <small v-for="message in messagesForPath(capabilityPath(capability, 'operation_type'))" :key="message" class="field-error-copy">{{ message }}</small>
                </label>
                <label class="field" :class="{ 'field-error': hasIssueForPath(capabilityPath(capability, 'side_effect_level')) }">
                  <div class="field-label-row">
                    <span class="required-label">Safety / Side Effect</span>
                    <span class="field-help-actions">
                      <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'safetySideEffect')">{{ capabilityFieldHelpTitle(capability, 'safetySideEffect') }}</button>
                      <button class="help-link secondary" type="button" @click.stop.prevent="openHelpCard('safetySideEffect')">More detail</button>
                    </span>
                  </div>
                  <select
                    :value="capability.side_effect_level"
                    class="select"
                    :title="technicalHoverLabel(capability.side_effect_level)"
                    @change="setCapabilityField(capability, 'side_effect_level', ($event.target as HTMLSelectElement).value)"
                  >
                    <option v-for="option in choiceOptions(SIDE_EFFECT_OPTIONS, capability.side_effect_level)" :key="option.value" :value="option.value">
                      {{ option.label }}
                    </option>
                  </select>
                  <small>{{ choiceDescription(SIDE_EFFECT_OPTIONS, capability.side_effect_level) }}</small>
                  <div v-if="capabilityFieldHelpExpanded(capability, 'safetySideEffect')" class="inline-help field-inline-help">
                    <p class="inline-help-summary">{{ CAPABILITY_FIELD_HELP.safetySideEffect.summary }}</p>
                    <ul class="inline-help-list">
                      <li v-for="detail in CAPABILITY_FIELD_HELP.safetySideEffect.inlineDetails" :key="detail">{{ detail }}</li>
                    </ul>
                  </div>
                  <small v-for="message in messagesForPath(capabilityPath(capability, 'side_effect_level'))" :key="message" class="field-error-copy">{{ message }}</small>
                </label>
                <label class="field" :class="{ 'field-error': hasIssueForPath(capabilityPath(capability, 'business_effects.produces')) }">
                  <div class="field-label-row">
                    <span class="required-label">Produces</span>
                  </div>
                  <input
                    :value="effectListText(capability.business_effects?.produces)"
                    class="input"
                    placeholder="content.summary, approval.request"
                    @input="setCapabilityEffectList(capability, 'produces', ($event.target as HTMLInputElement).value)"
                  />
                  <small>Comma-separated contract effects this capability may produce.</small>
                  <small v-for="message in messagesForPath(capabilityPath(capability, 'business_effects.produces'))" :key="message" class="field-error-copy">{{ message }}</small>
                </label>
                <label class="field" :class="{ 'field-error': hasIssueForPath(capabilityPath(capability, 'business_effects.does_not_produce')) }">
                  <div class="field-label-row">
                    <span class="required-label">Does Not Produce</span>
                  </div>
                  <input
                    :value="effectListText(capability.business_effects?.does_not_produce)"
                    class="input"
                    placeholder="raw_data_export, external_dispatch"
                    @input="setCapabilityEffectList(capability, 'does_not_produce', ($event.target as HTMLInputElement).value)"
                  />
                  <small>Comma-separated forbidden effects that define the capability boundary.</small>
                  <small v-for="message in messagesForPath(capabilityPath(capability, 'business_effects.does_not_produce'))" :key="message" class="field-error-copy">{{ message }}</small>
                </label>
                <label class="field field-wide" :class="{ 'field-error': hasIssueForPath(capabilityPath(capability, 'summary')) }">
                  <div class="field-label-row">
                    <span class="required-label">Business Summary</span>
                    <span class="field-help-actions">
                      <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'businessSummary')">{{ capabilityFieldHelpTitle(capability, 'businessSummary') }}</button>
                    </span>
                  </div>
                  <textarea
                    :value="capability.summary"
                    class="textarea"
                    rows="3"
                    placeholder="Describe what the capability does, when it is safe to use, and what it will not do."
                    @input="setCapabilityField(capability, 'summary', ($event.target as HTMLTextAreaElement).value)"
                  />
                  <div v-if="capabilityFieldHelpExpanded(capability, 'businessSummary')" class="inline-help field-inline-help">
                    <p class="inline-help-summary">{{ CAPABILITY_FIELD_HELP.businessSummary.summary }}</p>
                    <ul class="inline-help-list">
                      <li v-for="detail in CAPABILITY_FIELD_HELP.businessSummary.inlineDetails" :key="detail">{{ detail }}</li>
                    </ul>
                  </div>
                  <small v-for="message in messagesForPath(capabilityPath(capability, 'summary'))" :key="message" class="field-error-copy">{{ message }}</small>
                </label>
                <label class="field">
                  <div class="field-label-row">
                    <span class="required-label">Capability Shape</span>
                    <span class="field-help-actions">
                      <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'capabilityShape')">{{ capabilityFieldHelpTitle(capability, 'capabilityShape') }}</button>
                      <button class="help-link secondary" type="button" @click.stop.prevent="openHelpCard('capabilityShape')">More detail</button>
                    </span>
                  </div>
                  <select
                    :value="capabilityKind(capability)"
                    class="select"
                    @change="setCapabilityKind(capability, ($event.target as HTMLSelectElement).value)"
                  >
                    <option value="atomic">Single capability</option>
                    <option value="composed">Composed capability</option>
                  </select>
                  <div v-if="capabilityFieldHelpExpanded(capability, 'capabilityShape')" class="inline-help field-inline-help">
                    <p class="inline-help-summary">{{ CAPABILITY_FIELD_HELP.capabilityShape.summary }}</p>
                    <ul class="inline-help-list">
                      <li v-for="detail in CAPABILITY_FIELD_HELP.capabilityShape.inlineDetails" :key="detail">{{ detail }}</li>
                    </ul>
                  </div>
                </label>
                <label class="field">
                  <div class="field-label-row">
                    <span>Needs Named Business Target</span>
                    <span class="field-help-actions">
                      <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'namedBusinessTarget')">{{ capabilityFieldHelpTitle(capability, 'namedBusinessTarget') }}</button>
                      <button class="help-link secondary" type="button" @click.stop.prevent="openHelpCard('namedBusinessTarget')">More detail</button>
                    </span>
                  </div>
                  <select
                    :value="booleanString(capability.entity_targeted)"
                    class="select"
                    @change="setEntityTargeted(capability, ($event.target as HTMLSelectElement).value)"
                  >
                    <option value="false">No</option>
                    <option value="true">Yes</option>
                  </select>
                  <small>Use Yes when the caller must name a specific account, team, opportunity, cohort, or similar target.</small>
                  <div v-if="capabilityFieldHelpExpanded(capability, 'namedBusinessTarget')" class="inline-help field-inline-help">
                    <p class="inline-help-summary">{{ CAPABILITY_FIELD_HELP.namedBusinessTarget.summary }}</p>
                    <ul class="inline-help-list">
                      <li v-for="detail in CAPABILITY_FIELD_HELP.namedBusinessTarget.inlineDetails" :key="detail">{{ detail }}</li>
                    </ul>
                  </div>
                </label>
                <label class="field">
                  <div class="field-label-row">
                    <span>Business Subject</span>
                    <span class="field-help-actions">
                      <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'businessSubject')">{{ capabilityFieldHelpTitle(capability, 'businessSubject') }}</button>
                    </span>
                  </div>
                  <input
                    :value="capability.subject_kind"
                    class="input"
                    placeholder="e.g. account, team, opportunity cohort"
                    @input="setCapabilityField(capability, 'subject_kind', ($event.target as HTMLInputElement).value)"
                  />
                  <div v-if="capabilityFieldHelpExpanded(capability, 'businessSubject')" class="inline-help field-inline-help">
                    <p class="inline-help-summary">{{ CAPABILITY_FIELD_HELP.businessSubject.summary }}</p>
                    <ul class="inline-help-list">
                      <li v-for="detail in CAPABILITY_FIELD_HELP.businessSubject.inlineDetails" :key="detail">{{ detail }}</li>
                    </ul>
                  </div>
                </label>
                <label class="field">
                  <div class="field-label-row">
                    <span>Business Context</span>
                    <span class="field-help-actions">
                      <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'businessContext')">{{ capabilityFieldHelpTitle(capability, 'businessContext') }}</button>
                    </span>
                  </div>
                  <input
                    :value="capability.context_type"
                    class="input"
                    placeholder="e.g. entity enrichment, operational performance"
                    @input="setCapabilityField(capability, 'context_type', ($event.target as HTMLInputElement).value)"
                  />
                  <div v-if="capabilityFieldHelpExpanded(capability, 'businessContext')" class="inline-help field-inline-help">
                    <p class="inline-help-summary">{{ CAPABILITY_FIELD_HELP.businessContext.summary }}</p>
                    <ul class="inline-help-list">
                      <li v-for="detail in CAPABILITY_FIELD_HELP.businessContext.inlineDetails" :key="detail">{{ detail }}</li>
                    </ul>
                  </div>
                </label>
                <label class="field">
                  <div class="field-label-row">
                    <span>Result Meaning</span>
                    <span class="field-help-actions">
                      <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'resultMeaning')">{{ capabilityFieldHelpTitle(capability, 'resultMeaning') }}</button>
                    </span>
                  </div>
                  <input
                    :value="capability.output_intent"
                    class="input"
                    placeholder="e.g. entity context summary, ranked targets"
                    @input="setCapabilityField(capability, 'output_intent', ($event.target as HTMLInputElement).value)"
                  />
                  <div v-if="capabilityFieldHelpExpanded(capability, 'resultMeaning')" class="inline-help field-inline-help">
                    <p class="inline-help-summary">{{ CAPABILITY_FIELD_HELP.resultMeaning.summary }}</p>
                    <ul class="inline-help-list">
                      <li v-for="detail in CAPABILITY_FIELD_HELP.resultMeaning.inlineDetails" :key="detail">{{ detail }}</li>
                    </ul>
                  </div>
                </label>
                <details class="technical-contract-section">
                  <summary>
                    <span>Technical Contract Identifiers</span>
                    <small>Generator-facing operation, path, and result shape.</small>
                  </summary>
                  <div class="settings-grid technical-contract-grid">
                    <label class="field" :class="{ 'field-error': hasIssueForPath(capabilityPath(capability, 'backend_operation')) }">
                      <span class="required-label">Backend Operation</span>
                      <input
                        :value="capability.backend_operation"
                        class="input mono-input"
                        placeholder="e.g. list_accounts"
                        @input="setCapabilityField(capability, 'backend_operation', ($event.target as HTMLInputElement).value)"
                      />
                      <small>Stable operation key preserved in generated metadata.</small>
                      <small v-for="message in messagesForPath(capabilityPath(capability, 'backend_operation'))" :key="message" class="field-error-copy">{{ message }}</small>
                    </label>
                    <label class="field">
                      <span>Path Template</span>
                      <input
                        :value="capability.path_template"
                        class="input mono-input"
                        placeholder="e.g. /accounts/{id}"
                        @input="setCapabilityField(capability, 'path_template', ($event.target as HTMLInputElement).value)"
                      />
                    </label>
                    <label class="field">
                      <span>Output Shape</span>
                      <input
                        :value="capability.output_shape"
                        class="input mono-input"
                        placeholder="e.g. summary"
                        @input="setCapabilityField(capability, 'output_shape', ($event.target as HTMLInputElement).value)"
                      />
                    </label>
                  </div>
                </details>
              </div>

              <div class="composition-section">
                <div class="section-head capability-head">
                  <div>
                    <h3>Runtime Metadata</h3>
                    <p class="meta">Composition and approval grant policy are generated contract metadata. Studio validates them before generation or publication.</p>
                  </div>
                </div>
                <div
                  v-if="capabilityKind(capability) === 'composed'"
                  class="runtime-editor"
                  :class="{ 'field-error-card': hasIssueForPrefix(capabilityPath(capability, 'composition')) }"
                >
                  <div class="runtime-editor-head">
                    <div>
                      <h4>Composed Capability</h4>
                      <p class="meta">A composed capability is still one agent-facing capability. The service owns the internal ordered steps.</p>
                    </div>
                    <div class="runtime-actions">
                      <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'composedCapability')">{{ capabilityFieldHelpTitle(capability, 'composedCapability') }}</button>
                    </div>
                  </div>
                  <small v-for="message in messagesForPrefix(capabilityPath(capability, 'composition'))" :key="message" class="field-error-copy">{{ message }}</small>
                  <div v-if="capabilityFieldHelpExpanded(capability, 'composedCapability')" class="inline-help field-inline-help">
                    <p class="inline-help-summary">{{ RUNTIME_FIELD_HELP.composedCapability.summary }}</p>
                    <ul class="inline-help-list">
                      <li v-for="detail in RUNTIME_FIELD_HELP.composedCapability.inlineDetails" :key="detail">{{ detail }}</li>
                    </ul>
                  </div>

                  <div class="composition-builder">
                    <div class="composition-outcome-card">
                      <span class="composition-eyebrow">Caller sees one capability</span>
                      <strong>{{ capability.title || capability.capability_id }}</strong>
                      <p>{{ capability.summary || 'Define the business outcome this composed capability owns.' }}</p>
                    </div>
                    <div class="composition-builder-actions">
                      <button class="btn btn-secondary" type="button" @click="autoFillCompositionMappings(capability)">Auto-fill data handoff</button>
                      <button class="btn btn-secondary" type="button" @click="addCompositionStep(capability)">Add Step</button>
                    </div>
                    <div v-if="ensureComposition(capability).steps.length" class="composition-step-list guided">
                      <article v-for="(step, stepIndex) in ensureComposition(capability).steps" :key="`${capability.id}-guided-step-${stepIndex}`" class="composition-step-card guided-step-card">
                        <div class="guided-step-number">{{ stepIndex + 1 }}</div>
                        <div class="guided-step-content">
                          <label class="field">
                            <div class="field-label-row">
                              <span>{{ stepIndex === 0 ? 'First, this service should' : 'Then, this service should' }}</span>
                              <span class="field-help-actions">
                                <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'compositionChildCapability')">{{ capabilityFieldHelpTitle(capability, 'compositionChildCapability') }}</button>
                              </span>
                            </div>
                            <select v-model="step.capability" class="select">
                              <option value="">Choose a same-service capability</option>
                              <option
                                v-for="candidate in sameServiceAtomicOptions(capability)"
                                :key="candidate.id"
                                :value="candidate.capability_id"
                              >
                                {{ candidate.title || candidate.capability_id }}
                              </option>
                            </select>
                            <small>Only atomic capabilities owned by this same service are valid child steps.</small>
                            <div v-if="capabilityFieldHelpExpanded(capability, 'compositionChildCapability')" class="inline-help field-inline-help">
                              <p class="inline-help-summary">{{ RUNTIME_FIELD_HELP.compositionChildCapability.summary }}</p>
                              <ul class="inline-help-list">
                                <li v-for="detail in RUNTIME_FIELD_HELP.compositionChildCapability.inlineDetails" :key="detail">{{ detail }}</li>
                              </ul>
                            </div>
                          </label>
                          <div class="guided-step-summary">
                            <strong>{{ stepLabel(step, stepIndex) }}</strong>
                            <p v-if="childCapabilityForStep(step)?.inputs.length">
                              Data handoff:
                              <span
                                v-for="input in childCapabilityForStep(step)?.inputs ?? []"
                                :key="`${step.id}-plain-${input.input_name}`"
                                class="mapping-pill"
                              >
                                {{ inputMappingDescription(capability, step, input) }}
                              </span>
                            </p>
                            <p v-else>Select a child capability to see what data it needs.</p>
                          </div>
                          <details class="technical-contract-section composition-technical">
                            <summary>
                              <span>Technical mapping</span>
                              <small>Advanced runtime data handoff. Most users should not need to edit this.</small>
                            </summary>
                            <div class="settings-grid technical-contract-grid">
                              <div class="technical-help-callout">
                                <strong>What are these paths?</strong>
                                <p>
                                  These are generated-runtime pointers. <code>$.input</code> means “use a value the caller supplied to the parent capability.”
                                  <code>$.steps</code> means “use a value produced by an earlier step.” Use the Data handoff summary above for the human review.
                                </p>
                                <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'jsonPathMapping')">{{ capabilityFieldHelpTitle(capability, 'jsonPathMapping') }}</button>
                                <div v-if="capabilityFieldHelpExpanded(capability, 'jsonPathMapping')" class="inline-help field-inline-help">
                                  <p class="inline-help-summary">{{ RUNTIME_FIELD_HELP.jsonPathMapping.summary }}</p>
                                  <ul class="inline-help-list">
                                    <li v-for="detail in RUNTIME_FIELD_HELP.jsonPathMapping.inlineDetails" :key="detail">{{ detail }}</li>
                                  </ul>
                                </div>
                              </div>
                              <label class="field">
                                <div class="field-label-row">
                                  <span>Step ID</span>
                                  <span class="field-help-actions">
                                    <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'compositionStep')">{{ capabilityFieldHelpTitle(capability, 'compositionStep') }}</button>
                                  </span>
                                </div>
                                <input
                                  :value="step.id"
                                  class="input"
                                  placeholder="step_1"
                                  @change="setCompositionStepId(capability, step, ($event.target as HTMLInputElement).value)"
                                />
                                <small>Stable step key used by input and output mapping JSONPaths.</small>
                                <div v-if="capabilityFieldHelpExpanded(capability, 'compositionStep')" class="inline-help field-inline-help">
                                  <p class="inline-help-summary">{{ RUNTIME_FIELD_HELP.compositionStep.summary }}</p>
                                  <ul class="inline-help-list">
                                    <li v-for="detail in RUNTIME_FIELD_HELP.compositionStep.inlineDetails" :key="detail">{{ detail }}</li>
                                  </ul>
                                </div>
                              </label>
                              <label class="field">
                                <div class="field-label-row">
                                  <span>Can Produce Empty Source</span>
                                  <span class="field-help-actions">
                                    <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'emptyResultSource')">{{ capabilityFieldHelpTitle(capability, 'emptyResultSource') }}</button>
                                  </span>
                                </div>
                                <select v-model="step.empty_result_source" class="select">
                                  <option :value="false">No</option>
                                  <option :value="true">Yes</option>
                                </select>
                                <small>Use Yes for a selection step that may return no business records.</small>
                                <div v-if="capabilityFieldHelpExpanded(capability, 'emptyResultSource')" class="inline-help field-inline-help">
                                  <p class="inline-help-summary">{{ RUNTIME_FIELD_HELP.emptyResultSource.summary }}</p>
                                  <ul class="inline-help-list">
                                    <li v-for="detail in RUNTIME_FIELD_HELP.emptyResultSource.inlineDetails" :key="detail">{{ detail }}</li>
                                  </ul>
                                </div>
                              </label>
                              <label v-if="step.empty_result_source" class="field">
                                <div class="field-label-row">
                                  <span>Empty Result Path</span>
                                  <span class="field-help-actions">
                                    <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'jsonPathMapping')">{{ capabilityFieldHelpTitle(capability, 'jsonPathMapping') }}</button>
                                  </span>
                                </div>
                                <input v-model="step.empty_result_path" class="input mono-input" placeholder="e.g. $.accounts" />
                                <small>Optional JSONPath to the list or field that determines whether this step is empty.</small>
                              </label>
                              <div class="field field-wide">
                                <div class="field-label-row">
                                  <span>Input Mapping</span>
                                  <span class="field-help-actions">
                                    <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'inputMapping')">{{ capabilityFieldHelpTitle(capability, 'inputMapping') }}</button>
                                  </span>
                                </div>
                                <small>Map every child input from parent inputs or earlier step outputs.</small>
                                <p class="meta">Rows come from the selected child capability inputs. To add or remove a row, change the child capability input contract or choose a different child step.</p>
                                <div v-if="capabilityFieldHelpExpanded(capability, 'inputMapping')" class="inline-help field-inline-help">
                                  <p class="inline-help-summary">{{ RUNTIME_FIELD_HELP.inputMapping.summary }}</p>
                                  <ul class="inline-help-list">
                                    <li v-for="detail in RUNTIME_FIELD_HELP.inputMapping.inlineDetails" :key="detail">{{ detail }}</li>
                                  </ul>
                                </div>
                                <div v-if="childCapabilityForStep(step)?.inputs.length" class="mapping-list">
                                  <label
                                    v-for="input in childCapabilityForStep(step)?.inputs ?? []"
                                    :key="`${step.id}-${input.input_name}`"
                                    class="mapping-row"
                                  >
                                    <span :title="technicalHoverLabel(input.input_name)">{{ inputDisplayLabel(input.input_name) }}</span>
                                    <input
                                      :value="inputMappingValue(capability, step, input)"
                                      class="input mono-input"
                                      placeholder="$.input.field or $.steps.previous.output.field"
                                      @input="setInputMappingValue(capability, step, input.input_name, ($event.target as HTMLInputElement).value)"
                                    />
                                  </label>
                                </div>
                                <p v-else class="meta">Select a child capability to map its inputs.</p>
                              </div>
                            </div>
                          </details>
                        </div>
                        <button class="btn btn-danger btn-icon" type="button" @click="removeCompositionStep(capability, stepIndex)">Remove</button>
                      </article>
                    </div>
                    <p v-else class="panel-copy">No composition steps yet. Add a same-service child capability to start building the flow.</p>
                    <div class="composition-output-summary">
                      <strong>Caller receives</strong>
                      <span
                        v-for="[field, path] in outputMappingEntries(capability)"
                        :key="`${capability.id}-output-plain-${field}`"
                        class="mapping-pill"
                      >
                        {{ outputMappingDescription(field, path) }}
                      </span>
                    </div>
                  </div>

                  <details class="technical-contract-section composition-advanced">
                    <summary>
                      <span>Advanced runtime controls</span>
                      <small>Authority boundary, empty-result behavior, output JSONPath, no-results response, failure, and audit.</small>
                    </summary>
                    <div class="technical-contract-grid">
                      <div class="settings-grid runtime-grid">
                        <label class="field">
                          <div class="field-label-row">
                            <span>Authority Boundary</span>
                            <span class="field-help-actions">
                              <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'authorityBoundary')">{{ capabilityFieldHelpTitle(capability, 'authorityBoundary') }}</button>
                            </span>
                          </div>
                          <select :value="ensureComposition(capability).authority_boundary" class="select" disabled>
                            <option value="same_service">Same service only</option>
                          </select>
                          <small>Current runtime support keeps all child steps inside this service boundary.</small>
                        </label>
                        <label class="field">
                          <div class="field-label-row">
                            <span>Empty Result Behavior</span>
                            <span class="field-help-actions">
                              <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'emptyResultPolicy')">{{ capabilityFieldHelpTitle(capability, 'emptyResultPolicy') }}</button>
                            </span>
                          </div>
                          <select v-model="ensureComposition(capability).empty_result_policy" class="select">
                            <option :value="null">No special behavior</option>
                            <option value="return_success_no_results">Return a successful no-results response</option>
                            <option value="clarify">Ask for clarification</option>
                            <option value="deny">Deny the request</option>
                          </select>
                          <small>Decides whether an empty upstream selection should safely stop, clarify, or deny.</small>
                        </label>
                      </div>

                      <div class="runtime-subsection">
                        <div class="runtime-editor-head compact">
                          <div>
                            <h4>Output Mapping</h4>
                            <p class="meta">Map the composed response fields from parent inputs or previous child step outputs.</p>
                          </div>
                          <div class="runtime-actions">
                            <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'outputMapping')">{{ capabilityFieldHelpTitle(capability, 'outputMapping') }}</button>
                            <button class="btn btn-secondary" type="button" @click="addOutputMapping(capability)">Add Output Field</button>
                          </div>
                        </div>
                        <div v-if="capabilityFieldHelpExpanded(capability, 'outputMapping')" class="inline-help field-inline-help">
                          <p class="inline-help-summary">{{ RUNTIME_FIELD_HELP.outputMapping.summary }}</p>
                          <ul class="inline-help-list">
                            <li v-for="detail in RUNTIME_FIELD_HELP.outputMapping.inlineDetails" :key="detail">{{ detail }}</li>
                          </ul>
                        </div>
                        <div class="mapping-list">
                          <label v-for="[field, path] in outputMappingEntries(capability)" :key="field" class="mapping-row mapping-row-removable">
                            <input
                              :value="field"
                              class="input"
                              placeholder="field"
                              @change="setOutputMappingKey(capability, field, ($event.target as HTMLInputElement).value)"
                            />
                            <input
                              :value="path"
                              class="input mono-input"
                              placeholder="$.steps.step_1.output.result"
                              @input="setOutputMappingValue(capability, field, ($event.target as HTMLInputElement).value)"
                            />
                            <button class="btn btn-danger btn-icon" type="button" @click="removeOutputMapping(capability, field)">Remove</button>
                          </label>
                        </div>
                      </div>

                      <div v-if="ensureComposition(capability).empty_result_policy === 'return_success_no_results'" class="runtime-subsection">
                        <div class="runtime-editor-head compact">
                          <div>
                            <h4>No-Results Response</h4>
                            <p class="meta">Define simple response fields when the empty-result source produces no business records.</p>
                          </div>
                          <div class="runtime-actions">
                            <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'noResultsResponse')">{{ capabilityFieldHelpTitle(capability, 'noResultsResponse') }}</button>
                            <button class="btn btn-secondary" type="button" @click="addEmptyResultOutput(capability)">Add Field</button>
                          </div>
                        </div>
                        <div v-if="capabilityFieldHelpExpanded(capability, 'noResultsResponse')" class="inline-help field-inline-help">
                          <p class="inline-help-summary">{{ RUNTIME_FIELD_HELP.noResultsResponse.summary }}</p>
                          <ul class="inline-help-list">
                            <li v-for="detail in RUNTIME_FIELD_HELP.noResultsResponse.inlineDetails" :key="detail">{{ detail }}</li>
                          </ul>
                        </div>
                        <div class="mapping-list">
                          <label v-for="[field, value] in emptyResultOutputEntries(capability)" :key="field" class="mapping-row mapping-row-removable">
                            <input
                              :value="field"
                              class="input"
                              placeholder="field"
                              @change="setEmptyResultOutputKey(capability, field, ($event.target as HTMLInputElement).value)"
                            />
                            <input
                              :value="value"
                              class="input"
                              placeholder="value"
                              @input="setEmptyResultOutputValue(capability, field, ($event.target as HTMLInputElement).value)"
                            />
                            <button class="btn btn-danger btn-icon" type="button" @click="removeEmptyResultOutput(capability, field)">Remove</button>
                          </label>
                        </div>
                      </div>

                  <div class="runtime-subsection">
                    <div class="runtime-editor-head compact">
                      <div>
                        <h4>Failure Handling</h4>
                        <p class="meta">Choose whether child outcomes pass through or fail the parent capability.</p>
                      </div>
                      <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'failureHandling')">{{ capabilityFieldHelpTitle(capability, 'failureHandling') }}</button>
                    </div>
                    <div v-if="capabilityFieldHelpExpanded(capability, 'failureHandling')" class="inline-help field-inline-help">
                      <p class="inline-help-summary">{{ RUNTIME_FIELD_HELP.failureHandling.summary }}</p>
                      <ul class="inline-help-list">
                        <li v-for="detail in RUNTIME_FIELD_HELP.failureHandling.inlineDetails" :key="detail">{{ detail }}</li>
                      </ul>
                    </div>
                    <div class="settings-grid runtime-grid">
                      <label class="field">
                        <span>Clarification From Child</span>
                        <select v-model="ensureComposition(capability).failure_policy.child_clarification" class="select">
                          <option value="propagate">Pass through to caller</option>
                          <option value="fail_parent">Fail composed capability</option>
                        </select>
                      </label>
                      <label class="field">
                        <span>Denial From Child</span>
                        <select v-model="ensureComposition(capability).failure_policy.child_denial" class="select">
                          <option value="propagate">Pass through to caller</option>
                          <option value="fail_parent">Fail composed capability</option>
                        </select>
                      </label>
                      <label class="field">
                        <span>Approval Required From Child</span>
                        <select v-model="ensureComposition(capability).failure_policy.child_approval_required" class="select">
                          <option value="propagate">Pass through to caller</option>
                          <option value="fail_parent">Fail composed capability</option>
                        </select>
                      </label>
                      <label class="field">
                        <span>Unexpected Child Error</span>
                        <select v-model="ensureComposition(capability).failure_policy.child_error" class="select">
                          <option value="propagate">Pass through to caller</option>
                          <option value="fail_parent">Fail composed capability</option>
                        </select>
                      </label>
                    </div>
                  </div>

                  <div class="runtime-subsection">
                    <div class="runtime-editor-head compact">
                      <div>
                        <h4>Audit Lineage</h4>
                        <p class="meta">Keep the parent business action linked to internal child calls.</p>
                      </div>
                      <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'auditLineage')">{{ capabilityFieldHelpTitle(capability, 'auditLineage') }}</button>
                    </div>
                    <div v-if="capabilityFieldHelpExpanded(capability, 'auditLineage')" class="inline-help field-inline-help">
                      <p class="inline-help-summary">{{ RUNTIME_FIELD_HELP.auditLineage.summary }}</p>
                      <ul class="inline-help-list">
                        <li v-for="detail in RUNTIME_FIELD_HELP.auditLineage.inlineDetails" :key="detail">{{ detail }}</li>
                      </ul>
                    </div>
                    <div class="settings-grid runtime-grid">
                      <label class="field">
                        <span>Record Child Invocations</span>
                        <select v-model="ensureComposition(capability).audit_policy.record_child_invocations" class="select">
                          <option :value="true">Yes</option>
                          <option :value="false">No</option>
                        </select>
                      </label>
                      <label class="field">
                        <span>Keep Parent Task Lineage</span>
                        <select v-model="ensureComposition(capability).audit_policy.parent_task_lineage" class="select">
                          <option :value="true">Yes</option>
                          <option :value="false">No</option>
                        </select>
                      </label>
                    </div>
                  </div>
                    </div>
                  </details>
                </div>

                <div class="runtime-editor" :class="{ 'field-error-card': hasIssueForPrefix(capabilityPath(capability, 'grant_policy')) }">
                  <div class="runtime-editor-head">
                    <div>
                      <h4>Approval Grant Policy</h4>
                      <p class="meta">Use this when an approval-required capability can resume after an approver issues a bounded grant.</p>
                    </div>
                    <div class="runtime-actions">
                      <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'approvalGrantPolicy')">{{ capabilityFieldHelpTitle(capability, 'approvalGrantPolicy') }}</button>
                      <label class="inline-toggle">
                        <span>Enabled</span>
                        <select
                          :value="capability.grant_policy ? 'true' : 'false'"
                          class="select"
                          @change="setGrantPolicyEnabled(capability, ($event.target as HTMLSelectElement).value)"
                        >
                          <option value="false">No</option>
                          <option value="true">Yes</option>
                        </select>
                      </label>
                    </div>
                  </div>
                  <small v-for="message in messagesForPrefix(capabilityPath(capability, 'grant_policy'))" :key="message" class="field-error-copy">{{ message }}</small>
                  <div v-if="capabilityFieldHelpExpanded(capability, 'approvalGrantPolicy')" class="inline-help field-inline-help">
                    <p class="inline-help-summary">{{ RUNTIME_FIELD_HELP.approvalGrantPolicy.summary }}</p>
                    <ul class="inline-help-list">
                      <li v-for="detail in RUNTIME_FIELD_HELP.approvalGrantPolicy.inlineDetails" :key="detail">{{ detail }}</li>
                    </ul>
                  </div>

                  <div v-if="capability.grant_policy" class="settings-grid runtime-grid">
                    <label class="field">
                      <span>Allowed Grant Types</span>
                      <span class="checkbox-row">
                        <input
                          type="checkbox"
                          :checked="grantTypeAllowed(capability, 'one_time')"
                          @change="setGrantTypeAllowed(capability, 'one_time', ($event.target as HTMLInputElement).checked)"
                        />
                        One-time approval
                      </span>
                      <span class="checkbox-row">
                        <input
                          type="checkbox"
                          :checked="grantTypeAllowed(capability, 'session_bound')"
                          @change="setGrantTypeAllowed(capability, 'session_bound', ($event.target as HTMLInputElement).checked)"
                        />
                        Session-bound approval
                      </span>
                      <small>One-time is safest. Session-bound allows repeated approved work during a bounded session.</small>
                    </label>
                    <label class="field">
                      <span>Default Grant Type</span>
                      <select
                        :value="capability.grant_policy.default_grant_type"
                        class="select"
                        @change="setDefaultGrantType(capability, ($event.target as HTMLSelectElement).value)"
                      >
                        <option value="one_time">One-time approval</option>
                        <option value="session_bound">Session-bound approval</option>
                      </select>
                      <small>The grant type Studio uses when the approver does not choose a more specific option.</small>
                    </label>
                    <label class="field">
                      <span>Expires After</span>
                      <input
                        :value="capability.grant_policy.expires_in_seconds"
                        class="input"
                        type="number"
                        min="1"
                        @input="setGrantPolicyNumber(capability, 'expires_in_seconds', ($event.target as HTMLInputElement).value)"
                      />
                      <small>Seconds after approval issuance.</small>
                    </label>
                    <label class="field">
                      <span>Maximum Uses</span>
                      <input
                        :value="capability.grant_policy.max_uses"
                        class="input"
                        type="number"
                        min="1"
                        @input="setGrantPolicyNumber(capability, 'max_uses', ($event.target as HTMLInputElement).value)"
                      />
                      <small>Maximum number of invocations allowed by one issued approval grant.</small>
                    </label>
                  </div>
                  <p v-else class="panel-copy">No approval continuation grant will be generated for this capability.</p>
                </div>
              </div>

              <div class="input-contract-section">
                <div class="section-head capability-head">
                  <div>
                    <h3>Capability Inputs</h3>
                    <p class="meta">These are part of the runtime contract and should come from Studio, not generator templates.</p>
                  </div>
                  <div class="input-actions">
                    <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'capabilityInputs')">{{ capabilityFieldHelpTitle(capability, 'capabilityInputs') }}</button>
                    <button class="btn btn-secondary" type="button" @click="addCapabilityInput(capability, true)">Add Required Input</button>
                    <button class="btn btn-secondary" type="button" @click="addCapabilityInput(capability, false)">Add Optional Input</button>
                  </div>
                </div>
                <div v-if="capabilityFieldHelpExpanded(capability, 'capabilityInputs')" class="inline-help field-inline-help">
                  <p class="inline-help-summary">{{ RUNTIME_FIELD_HELP.capabilityInputs.summary }}</p>
                  <ul class="inline-help-list">
                    <li v-for="detail in RUNTIME_FIELD_HELP.capabilityInputs.inlineDetails" :key="detail">{{ detail }}</li>
                  </ul>
                </div>
                <div v-if="capability.inputs.length" class="capability-input-list">
                  <article v-for="(input, inputIndex) in capability.inputs" :key="`${capability.id}-input-${inputIndex}`" class="capability-input-card">
                    <div v-if="input.clarification_hint" class="service-contract-indicator">
                      <strong>Runtime clarification configured</strong>
                      <span>Service-contract behavior: the runtime has a reviewed question for missing or malformed {{ inputDisplayLabel(input.input_name).toLowerCase() }}.</span>
                    </div>
                    <div class="settings-grid">
                      <label class="field">
                        <div class="field-label-row">
                          <span>Name</span>
                          <span class="field-help-actions">
                            <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'inputName')">{{ capabilityFieldHelpTitle(capability, 'inputName') }}</button>
                          </span>
                        </div>
                        <small v-if="input.input_name" class="display-label-hint">
                          Displayed as {{ inputDisplayLabel(input.input_name) }}<template v-if="showTechnicalIdentifiers"> · Technical name: {{ input.input_name }}</template>
                        </small>
                        <input v-model="input.input_name" class="input" placeholder="e.g. quarter" />
                        <small>Stable parameter key used by callers, composition, and generated metadata.</small>
                        <div v-if="capabilityFieldHelpExpanded(capability, 'inputName')" class="inline-help field-inline-help">
                          <p class="inline-help-summary">{{ RUNTIME_FIELD_HELP.inputName.summary }}</p>
                          <ul class="inline-help-list">
                            <li v-for="detail in RUNTIME_FIELD_HELP.inputName.inlineDetails" :key="detail">{{ detail }}</li>
                          </ul>
                        </div>
                      </label>
                      <label class="field">
                        <div class="field-label-row">
                          <span>Type</span>
                          <span class="field-help-actions">
                            <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'inputType')">{{ capabilityFieldHelpTitle(capability, 'inputType') }}</button>
                          </span>
                        </div>
                        <input v-model="input.input_type" class="input" placeholder="e.g. string" />
                        <small>Contract value shape, such as string, object, or array&lt;string&gt;.</small>
                        <div v-if="capabilityFieldHelpExpanded(capability, 'inputType')" class="inline-help field-inline-help">
                          <p class="inline-help-summary">{{ RUNTIME_FIELD_HELP.inputType.summary }}</p>
                          <ul class="inline-help-list">
                            <li v-for="detail in RUNTIME_FIELD_HELP.inputType.inlineDetails" :key="detail">{{ detail }}</li>
                          </ul>
                        </div>
                      </label>
                      <label class="field">
                        <div class="field-label-row">
                          <span>Required</span>
                          <span class="field-help-actions">
                            <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'inputRequired')">{{ capabilityFieldHelpTitle(capability, 'inputRequired') }}</button>
                          </span>
                        </div>
                        <select v-model="input.required" class="select">
                          <option :value="true">Yes</option>
                          <option :value="false">No</option>
                        </select>
                        <small>Required inputs must be provided or clarified before invocation.</small>
                        <div v-if="capabilityFieldHelpExpanded(capability, 'inputRequired')" class="inline-help field-inline-help">
                          <p class="inline-help-summary">{{ RUNTIME_FIELD_HELP.inputRequired.summary }}</p>
                          <ul class="inline-help-list">
                            <li v-for="detail in RUNTIME_FIELD_HELP.inputRequired.inlineDetails" :key="detail">{{ detail }}</li>
                          </ul>
                        </div>
                      </label>
                      <label class="field">
                        <div class="field-label-row">
                          <span>Entity Reference</span>
                          <span class="field-help-actions">
                            <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'inputEntityReference')">{{ capabilityFieldHelpTitle(capability, 'inputEntityReference') }}</button>
                          </span>
                        </div>
                        <select v-model="input.entity_reference" class="select">
                          <option :value="true">Yes</option>
                          <option :value="false">No</option>
                        </select>
                        <small>Use Yes when this identifies a business entity, cohort, scope, or target.</small>
                        <div v-if="capabilityFieldHelpExpanded(capability, 'inputEntityReference')" class="inline-help field-inline-help">
                          <p class="inline-help-summary">{{ RUNTIME_FIELD_HELP.inputEntityReference.summary }}</p>
                          <ul class="inline-help-list">
                            <li v-for="detail in RUNTIME_FIELD_HELP.inputEntityReference.inlineDetails" :key="detail">{{ detail }}</li>
                          </ul>
                        </div>
                      </label>
                      <label class="field">
                        <div class="field-label-row">
                          <span>Semantic Type</span>
                          <span class="field-help-actions">
                            <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'inputSemanticType')">{{ capabilityFieldHelpTitle(capability, 'inputSemanticType') }}</button>
                          </span>
                        </div>
                        <input v-model="input.semantic_type" class="input" placeholder="e.g. time_scope, entity_reference, business_category" />
                        <small>Meaning category used by readiness checks and consuming apps.</small>
                        <div v-if="capabilityFieldHelpExpanded(capability, 'inputSemanticType')" class="inline-help field-inline-help">
                          <p class="inline-help-summary">{{ RUNTIME_FIELD_HELP.inputSemanticType.summary }}</p>
                          <ul class="inline-help-list">
                            <li v-for="detail in RUNTIME_FIELD_HELP.inputSemanticType.inlineDetails" :key="detail">{{ detail }}</li>
                          </ul>
                        </div>
                      </label>
                      <label class="field">
                        <div class="field-label-row">
                          <span>Catalog Ref</span>
                          <span class="field-help-actions">
                            <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'inputResolution')">{{ capabilityFieldHelpTitle(capability, 'inputResolution') }}</button>
                          </span>
                        </div>
                        <input v-model="input.catalog_ref" class="input mono-input" placeholder="e.g. gtm.account_catalog" />
                        <small>Provider-owned catalog used to resolve or constrain this input.</small>
                      </label>
                      <label class="field">
                        <div class="field-label-row">
                          <span>Default Value</span>
                          <span class="field-help-actions">
                            <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'inputDefaultValue')">{{ capabilityFieldHelpTitle(capability, 'inputDefaultValue') }}</button>
                          </span>
                        </div>
                        <input v-model="input.default_value" class="input" placeholder="optional default" />
                        <small>Use only when a missing value can be safely defaulted.</small>
                        <div v-if="capabilityFieldHelpExpanded(capability, 'inputDefaultValue')" class="inline-help field-inline-help">
                          <p class="inline-help-summary">{{ RUNTIME_FIELD_HELP.inputDefaultValue.summary }}</p>
                          <ul class="inline-help-list">
                            <li v-for="detail in RUNTIME_FIELD_HELP.inputDefaultValue.inlineDetails" :key="detail">{{ detail }}</li>
                          </ul>
                        </div>
                      </label>
                      <label class="field field-wide">
                        <div class="field-label-row">
                          <span>Summary</span>
                          <span class="field-help-actions">
                            <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'inputSummary')">{{ capabilityFieldHelpTitle(capability, 'inputSummary') }}</button>
                          </span>
                        </div>
                        <textarea v-model="input.summary" class="textarea" rows="2" placeholder="Explain the input contract and meaning." />
                        <div v-if="capabilityFieldHelpExpanded(capability, 'inputSummary')" class="inline-help field-inline-help">
                          <p class="inline-help-summary">{{ RUNTIME_FIELD_HELP.inputSummary.summary }}</p>
                          <ul class="inline-help-list">
                            <li v-for="detail in RUNTIME_FIELD_HELP.inputSummary.inlineDetails" :key="detail">{{ detail }}</li>
                          </ul>
                        </div>
                      </label>
                      <label class="field field-wide">
                        <div class="field-label-row">
                          <span>Allowed Values</span>
                          <span class="field-help-actions">
                            <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'inputAllowedValues')">{{ capabilityFieldHelpTitle(capability, 'inputAllowedValues') }}</button>
                          </span>
                        </div>
                        <input
                          :value="allowedValuesText(capability, inputIndex)"
                          class="input"
                          placeholder="comma-separated allowed values"
                          @input="setAllowedValues(capability, inputIndex, ($event.target as HTMLInputElement).value)"
                        />
                        <small>Use for closed enum choices, not open-ended phrase aliases.</small>
                        <div v-if="capabilityFieldHelpExpanded(capability, 'inputAllowedValues')" class="inline-help field-inline-help">
                          <p class="inline-help-summary">{{ RUNTIME_FIELD_HELP.inputAllowedValues.summary }}</p>
                          <ul class="inline-help-list">
                            <li v-for="detail in RUNTIME_FIELD_HELP.inputAllowedValues.inlineDetails" :key="detail">{{ detail }}</li>
                          </ul>
                        </div>
                      </label>
                      <label class="field">
                        <div class="field-label-row">
                          <span>Resolution Mode</span>
                          <span class="field-help-actions">
                            <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'inputResolution')">{{ capabilityFieldHelpTitle(capability, 'inputResolution') }}</button>
                          </span>
                        </div>
                        <select
                          :value="input.resolution?.mode ?? defaultResolutionMode(input)"
                          class="select"
                          @change="setInputResolutionMode(input, ($event.target as HTMLSelectElement).value)"
                        >
                          <option v-for="option in INPUT_RESOLUTION_MODE_OPTIONS" :key="option.value" :value="option.value">
                            {{ option.label }}
                          </option>
                        </select>
                        <small>{{ choiceDescription(INPUT_RESOLUTION_MODE_OPTIONS, input.resolution?.mode ?? defaultResolutionMode(input)) }}</small>
                      </label>
                      <label class="field">
                        <div class="field-label-row">
                          <span>Resolver Ref</span>
                          <span class="field-help-actions">
                            <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'inputResolution')">{{ capabilityFieldHelpTitle(capability, 'inputResolution') }}</button>
                          </span>
                        </div>
                        <input
                          :value="inputResolverRef(input)"
                          class="input mono-input"
                          placeholder="e.g. gtm.account_catalog"
                          @input="setInputResolverRef(input, ($event.target as HTMLInputElement).value)"
                        />
                        <small>Resolver used by backend-resolved or catalog-backed inputs.</small>
                      </label>
                      <label class="field">
                        <span>On Missing</span>
                        <select
                          :value="inputResolutionBehavior(input, 'on_missing')"
                          class="select"
                          @change="setInputResolutionBehavior(input, 'on_missing', ($event.target as HTMLSelectElement).value)"
                        >
                          <option v-for="option in INPUT_RESOLUTION_BEHAVIOR_OPTIONS" :key="option.value" :value="option.value">
                            {{ option.label }}
                          </option>
                        </select>
                      </label>
                      <label class="field">
                        <span>On Ambiguous</span>
                        <select
                          :value="inputResolutionBehavior(input, 'on_ambiguous')"
                          class="select"
                          @change="setInputResolutionBehavior(input, 'on_ambiguous', ($event.target as HTMLSelectElement).value)"
                        >
                          <option v-for="option in INPUT_RESOLUTION_BEHAVIOR_OPTIONS" :key="option.value" :value="option.value">
                            {{ option.label }}
                          </option>
                        </select>
                      </label>
                      <label class="field">
                        <span>On Unresolved</span>
                        <select
                          :value="inputResolutionBehavior(input, 'on_unresolved')"
                          class="select"
                          @change="setInputResolutionBehavior(input, 'on_unresolved', ($event.target as HTMLSelectElement).value)"
                        >
                          <option v-for="option in INPUT_RESOLUTION_BEHAVIOR_OPTIONS" :key="option.value" :value="option.value">
                            {{ option.label }}
                          </option>
                        </select>
                      </label>
                      <label class="field">
                        <div class="field-label-row">
                          <span>Normalization Hint</span>
                          <span class="field-help-actions">
                            <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'inputNormalizationHint')">{{ capabilityFieldHelpTitle(capability, 'inputNormalizationHint') }}</button>
                          </span>
                        </div>
                        <input v-model="input.normalization_hint" class="input" placeholder="e.g. quarter, scope, top_n" />
                        <small>Guides safe conversion from user language into this input.</small>
                        <div v-if="capabilityFieldHelpExpanded(capability, 'inputNormalizationHint')" class="inline-help field-inline-help">
                          <p class="inline-help-summary">{{ RUNTIME_FIELD_HELP.inputNormalizationHint.summary }}</p>
                          <ul class="inline-help-list">
                            <li v-for="detail in RUNTIME_FIELD_HELP.inputNormalizationHint.inlineDetails" :key="detail">{{ detail }}</li>
                          </ul>
                        </div>
                      </label>
                      <label class="field">
                        <div class="field-label-row">
                          <span>Normalization Context</span>
                          <span class="field-help-actions">
                            <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'inputNormalizationContext')">{{ capabilityFieldHelpTitle(capability, 'inputNormalizationContext') }}</button>
                          </span>
                        </div>
                        <input v-model="input.normalization_context" class="input" placeholder="e.g. default_year=2026" />
                        <small>Optional bounded context used when normalizing safely.</small>
                        <div v-if="capabilityFieldHelpExpanded(capability, 'inputNormalizationContext')" class="inline-help field-inline-help">
                          <p class="inline-help-summary">{{ RUNTIME_FIELD_HELP.inputNormalizationContext.summary }}</p>
                          <ul class="inline-help-list">
                            <li v-for="detail in RUNTIME_FIELD_HELP.inputNormalizationContext.inlineDetails" :key="detail">{{ detail }}</li>
                          </ul>
                        </div>
                      </label>
                      <label class="field">
                        <div class="field-label-row">
                          <span>Input Format</span>
                          <span class="field-help-actions">
                            <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'inputFormat')">{{ capabilityFieldHelpTitle(capability, 'inputFormat') }}</button>
                          </span>
                        </div>
                        <input v-model="input.input_format" class="input" placeholder="e.g. business_quarter, date, email" />
                        <small>Named format convention reviewers and consuming apps can understand.</small>
                        <div v-if="capabilityFieldHelpExpanded(capability, 'inputFormat')" class="inline-help field-inline-help">
                          <p class="inline-help-summary">{{ RUNTIME_FIELD_HELP.inputFormat.summary }}</p>
                          <ul class="inline-help-list">
                            <li v-for="detail in RUNTIME_FIELD_HELP.inputFormat.inlineDetails" :key="detail">{{ detail }}</li>
                          </ul>
                        </div>
                      </label>
                      <label class="field">
                        <div class="field-label-row">
                          <span>Validation Pattern</span>
                          <span class="field-help-actions">
                            <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'inputValidationPattern')">{{ capabilityFieldHelpTitle(capability, 'inputValidationPattern') }}</button>
                          </span>
                        </div>
                        <input v-model="input.validation_pattern" class="input" placeholder="e.g. ^\\d{4}-Q[1-4]$" />
                        <small>Optional regex for deterministic syntax validation.</small>
                        <div v-if="capabilityFieldHelpExpanded(capability, 'inputValidationPattern')" class="inline-help field-inline-help">
                          <p class="inline-help-summary">{{ RUNTIME_FIELD_HELP.inputValidationPattern.summary }}</p>
                          <ul class="inline-help-list">
                            <li v-for="detail in RUNTIME_FIELD_HELP.inputValidationPattern.inlineDetails" :key="detail">{{ detail }}</li>
                          </ul>
                        </div>
                      </label>
                      <label class="field field-wide">
                        <div class="field-label-row">
                          <span>Clarification Hint</span>
                          <span class="field-help-actions">
                            <button class="help-link" type="button" @click.stop.prevent="toggleCapabilityFieldHelp(capability, 'inputClarificationHint')">{{ capabilityFieldHelpTitle(capability, 'inputClarificationHint') }}</button>
                          </span>
                        </div>
                        <textarea v-model="input.clarification_hint" class="textarea" rows="2" placeholder="Question or instruction to return when this input is missing or malformed." />
                        <div v-if="capabilityFieldHelpExpanded(capability, 'inputClarificationHint')" class="inline-help field-inline-help">
                          <p class="inline-help-summary">{{ RUNTIME_FIELD_HELP.inputClarificationHint.summary }}</p>
                          <ul class="inline-help-list">
                            <li v-for="detail in RUNTIME_FIELD_HELP.inputClarificationHint.inlineDetails" :key="detail">{{ detail }}</li>
                          </ul>
                        </div>
                      </label>
                    </div>
                    <button class="btn btn-danger" type="button" @click="capability.inputs.splice(inputIndex, 1)">Remove Input</button>
                  </article>
                </div>
                <p v-else class="panel-copy">No explicit input contract yet.</p>
              </div>
                </div>
              </details>
            </article>
          </div>
          <p v-else class="panel-copy">No capability candidates are available yet from the linked developer drafts.</p>
          <div v-if="activeHelpCard && CAPABILITY_FIELD_HELP[activeHelpCard]" class="help-dialog-backdrop" @click.self="closeHelpCard">
            <div class="help-dialog">
              <div class="help-dialog-header">
                <h2>{{ CAPABILITY_FIELD_HELP[activeHelpCard].title }}</h2>
                <button class="help-dialog-close" type="button" @click="closeHelpCard">Close</button>
              </div>
              <p class="inline-help-summary">{{ CAPABILITY_FIELD_HELP[activeHelpCard].summary }}</p>
              <div v-if="helpChoicesFor(activeHelpCard).length" class="help-choice-section">
                <strong>Available choices</strong>
                <div class="help-choice-list">
                  <article v-for="choice in helpChoicesFor(activeHelpCard)" :key="choice.value" class="help-choice-card">
                    <div>
                      <span class="help-choice-label">{{ choice.label }}</span>
                      <p>{{ choice.description }}</p>
                    </div>
                  </article>
                </div>
              </div>
              <ul class="inline-help-list">
                <li v-for="item in CAPABILITY_FIELD_HELP[activeHelpCard].bullets" :key="item">{{ item }}</li>
              </ul>
              <div v-if="CAPABILITY_FIELD_HELP[activeHelpCard].example" class="help-dialog-example">
                <strong>Example</strong>
                <p>{{ CAPABILITY_FIELD_HELP[activeHelpCard].example }}</p>
              </div>
              <div v-if="CAPABILITY_FIELD_HELP[activeHelpCard].decisionOwner" class="help-dialog-example">
                <strong>Who usually decides this?</strong>
                <p>{{ CAPABILITY_FIELD_HELP[activeHelpCard].decisionOwner }}</p>
              </div>
            </div>
          </div>
        </article>
      </section>
    </template>
  </div>
</template>

<style scoped src="./developer-definition-shared.css"></style>
<style scoped>
.panel > .panel-copy {
  margin: 0 0 1.25rem;
  max-width: 92rem;
}

.why-copy {
  color: var(--text-primary);
  background: rgba(14, 165, 233, 0.08);
  border: 1px solid rgba(125, 211, 252, 0.16);
  border-radius: 14px;
  padding: 0.75rem 0.9rem;
}

.success {
  color: #86efac;
}

.evidence-import-panel {
  margin: 0 0 1.25rem;
  border: 1px solid rgba(125, 211, 252, 0.2);
  border-radius: 18px;
  padding: 1rem;
  background:
    linear-gradient(135deg, rgba(14, 165, 233, 0.12), rgba(15, 23, 42, 0.12)),
    rgba(15, 23, 42, 0.36);
}

.evidence-import-header,
.evidence-import-actions {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.evidence-import-header h3 {
  margin: 0 0 0.4rem;
}

.evidence-import-header p,
.helper-text {
  margin: 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.5;
}

.evidence-textarea {
  margin: 0.9rem 0;
  min-height: 22rem;
}

.panel-header {
  margin-bottom: 1.1rem;
}

.review-summary-card small {
  display: block;
  margin-top: 0.35rem;
  color: var(--text-secondary);
  font-size: 0.75rem;
  line-height: 1.35;
  word-break: break-word;
}

.service-contract-card {
  border-color: rgba(34, 197, 94, 0.34);
  background:
    linear-gradient(135deg, rgba(22, 101, 52, 0.2), rgba(15, 23, 42, 0.16)),
    rgba(20, 83, 45, 0.12);
}

.field-label-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
}

.field-label-row > span:first-child {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.field-help-actions {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.45rem;
  flex-wrap: wrap;
}

.field-help-actions .help-link {
  font-size: 11px;
  line-height: 1.2;
}

.field-inline-help {
  margin-top: 0.25rem;
}

.help-choice-section {
  margin-top: 1rem;
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 14px;
  padding: 0.9rem;
  background: rgba(15, 23, 42, 0.32);
}

.help-choice-section > strong {
  display: block;
  margin-bottom: 0.7rem;
  color: var(--text-primary);
  font-size: 13px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.help-choice-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0.7rem;
}

.help-choice-card {
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 12px;
  padding: 0.75rem;
  background: rgba(2, 6, 23, 0.22);
}

.help-choice-label {
  display: block;
  margin-bottom: 0.35rem;
  color: var(--text-primary);
  font-weight: 800;
}

.help-choice-card p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.45;
}

.settings-grid {
  gap: 1rem;
}

.field {
  gap: 0.5rem;
}

.field > span {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.field small {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.4;
}

.display-label-hint {
  color: var(--text-primary);
  font-weight: 700;
}

.input,
.select,
.textarea {
  background: var(--surface-depth-control);
}

.capability-list {
  display: flex;
  flex-direction: column;
  gap: 1.15rem;
}

.capability-card {
  scroll-margin-top: 6rem;
  border: 1px solid var(--surface-border-card);
  border-radius: 18px;
  padding: 1rem;
  background: var(--surface-depth-card);
}

.capability-card.anchored-card,
.capability-card.service-anchored-card,
.capability-card.behavior-anchored-card {
  border-color: rgba(125, 211, 252, 0.72);
  background:
    radial-gradient(circle at top left, rgba(14, 165, 233, 0.18), transparent 34%),
    rgba(15, 23, 42, 0.34);
  box-shadow: 0 0 0 1px rgba(125, 211, 252, 0.26), 0 20px 54px rgba(14, 165, 233, 0.14);
}

.capability-card.behavior-anchored-card {
  border-color: rgba(45, 212, 191, 0.72);
  background:
    radial-gradient(circle at top left, rgba(20, 184, 166, 0.18), transparent 34%),
    rgba(15, 23, 42, 0.34);
}

.capability-head {
  align-items: flex-start;
  margin-bottom: 1rem;
  padding-bottom: 0.9rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
}

.capability-head h3 {
  margin: 0 0 0.35rem;
  font-size: 18px;
}

.meta {
  margin: 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.45;
}

.source-badge {
  display: inline-flex;
  align-items: center;
  padding: 0.14rem 0.45rem;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.03em;
}

.source-badge.application_integration {
  background: rgba(59, 130, 246, 0.18);
  color: #93c5fd;
}

.source-badge.data_access {
  background: rgba(16, 185, 129, 0.18);
  color: #6ee7b7;
}

.input-contract-section {
  margin-top: 1.2rem;
  padding-top: 1rem;
  border-top: 1px solid rgba(148, 163, 184, 0.14);
}

.composition-section {
  margin-top: 1.2rem;
  padding-top: 1rem;
  border-top: 1px solid rgba(148, 163, 184, 0.14);
}

.technical-contract-section {
  grid-column: 1 / -1;
  margin-top: 0.1rem;
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 16px;
  background: rgba(15, 23, 42, 0.22);
}

.technical-contract-section summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  cursor: pointer;
  padding: 0.85rem 1rem;
  color: var(--text-primary);
  font-weight: 800;
}

.technical-contract-section summary span {
  color: var(--text-primary);
  font-size: 13px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.technical-contract-section summary small {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0;
  text-transform: none;
}

.technical-contract-grid {
  padding: 0 1rem 1rem;
}

.technical-help-callout {
  grid-column: 1 / -1;
  border: 1px solid rgba(125, 211, 252, 0.18);
  border-radius: 14px;
  padding: 0.85rem;
  background: rgba(14, 165, 233, 0.08);
}

.technical-help-callout strong {
  display: block;
  margin-bottom: 0.35rem;
  color: var(--text-primary);
}

.technical-help-callout p {
  margin: 0 0 0.6rem;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.55;
}

.technical-help-callout code {
  color: #bae6fd;
}

.mono-textarea,
.mono-input {
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
  font-size: 12px;
}

.runtime-editor {
  border: 1px solid var(--surface-border-card);
  border-radius: 16px;
  padding: 1rem;
  background: var(--surface-depth-inset);
}

.runtime-editor + .runtime-editor {
  margin-top: 1rem;
}

.runtime-editor-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}

.runtime-editor-head.compact {
  margin-bottom: 0.75rem;
}

.runtime-actions {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 0.6rem;
}

.runtime-editor h4 {
  margin: 0 0 0.35rem;
  color: var(--text-primary);
  font-size: 15px;
}

.runtime-grid {
  margin-top: 0.75rem;
}

.runtime-subsection {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid rgba(148, 163, 184, 0.12);
}

.composition-step-list {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  margin-top: 1rem;
}

.composition-builder {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  margin-top: 1rem;
}

.composition-outcome-card {
  border: 1px solid rgba(45, 212, 191, 0.18);
  border-radius: 16px;
  padding: 1rem;
  background:
    radial-gradient(circle at top left, rgba(45, 212, 191, 0.16), transparent 34%),
    rgba(15, 23, 42, 0.3);
}

.composition-outcome-card strong {
  display: block;
  margin-top: 0.35rem;
  color: var(--text-primary);
  font-size: 17px;
}

.composition-outcome-card p {
  margin: 0.45rem 0 0;
  color: var(--text-secondary);
  line-height: 1.5;
}

.composition-eyebrow {
  color: #5eead4;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.composition-builder-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.7rem;
  flex-wrap: wrap;
}

.composition-step-list.guided {
  gap: 0.9rem;
}

.composition-step-card {
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 14px;
  padding: 0.9rem;
  background: rgba(15, 23, 42, 0.28);
}

.guided-step-card {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 0.85rem;
  align-items: flex-start;
}

.guided-step-number {
  display: inline-grid;
  place-items: center;
  width: 2rem;
  height: 2rem;
  border-radius: 999px;
  background: rgba(125, 211, 252, 0.16);
  color: #bae6fd;
  font-weight: 900;
}

.guided-step-content {
  min-width: 0;
}

.guided-step-summary {
  margin-top: 0.75rem;
  border: 1px solid rgba(148, 163, 184, 0.12);
  border-radius: 12px;
  padding: 0.75rem;
  background: rgba(2, 6, 23, 0.18);
}

.guided-step-summary strong {
  color: var(--text-primary);
}

.guided-step-summary p,
.composition-output-summary {
  margin: 0.45rem 0 0;
  color: var(--text-secondary);
  line-height: 1.55;
}

.mapping-pill {
  display: inline-flex;
  align-items: center;
  margin: 0.25rem 0.35rem 0 0;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 999px;
  padding: 0.2rem 0.55rem;
  background: rgba(15, 23, 42, 0.38);
  color: var(--text-primary);
  font-size: 12px;
}

.composition-technical,
.composition-advanced {
  margin-top: 0.85rem;
}

.composition-output-summary {
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 14px;
  padding: 0.85rem;
  background: rgba(15, 23, 42, 0.22);
}

.composition-output-summary strong {
  display: block;
  margin-bottom: 0.35rem;
  color: var(--text-primary);
}

.composition-step-card .btn-danger {
  margin-top: 0.85rem;
}

.mapping-list {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.mapping-row {
  display: grid;
  grid-template-columns: minmax(10rem, 0.8fr) minmax(16rem, 1.4fr);
  gap: 0.65rem;
  align-items: center;
}

.mapping-row > span {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
}

.mapping-row-removable {
  grid-template-columns: minmax(10rem, 0.8fr) minmax(16rem, 1.4fr) auto;
}

.btn-icon {
  min-height: 38px;
  white-space: nowrap;
}

.inline-toggle {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.inline-toggle .select {
  min-width: 8rem;
}

.checkbox-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--text-primary);
  font-size: 0.9rem;
  font-weight: 600;
  letter-spacing: 0;
  text-transform: none;
}

.input-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  justify-content: flex-end;
}

.capability-input-list {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.capability-input-card {
  border: 1px solid var(--surface-border-card);
  border-radius: 16px;
  padding: 1rem;
  background: var(--surface-depth-inset);
}

.service-contract-indicator {
  display: grid;
  gap: 0.25rem;
  margin-bottom: 0.85rem;
  border: 1px solid rgba(34, 197, 94, 0.3);
  border-left: 5px solid #22c55e;
  border-radius: 12px;
  padding: 0.7rem;
  background: rgba(20, 83, 45, 0.14);
}

.service-contract-indicator strong {
  color: #bbf7d0;
}

.service-contract-indicator span {
  color: #dcfce7;
  font-size: 0.86rem;
}

.capability-input-card .btn-danger {
  margin-top: 0.85rem;
}

.btn-danger {
  color: #fca5a5;
  border: 1px solid rgba(248, 113, 113, 0.28);
  background: rgba(127, 29, 29, 0.16);
}

@media (max-width: 960px) {
  .settings-grid {
    grid-template-columns: 1fr;
  }

  .field-wide {
    grid-column: span 1;
  }

  .input-actions {
    justify-content: flex-start;
  }
}
</style>
