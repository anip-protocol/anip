import {
  createPmArtifact,
  createRequirements,
  createScenario,
  createShape,
  setRequirementsRole,
  updatePmArtifact,
} from './project-api'
import type {
  ArtifactRecord,
  AssistantCandidateBlocksProposal,
  AssistantPatchCandidatesProposal,
  AssistantProposalEnvelope,
  AssistantServiceTopologyPreference,
  ProjectDetail,
  RequirementsRecord,
} from './project-types'
import {
  ACTOR_MODEL_ARTIFACT_TYPE,
  BUSINESS_AREAS_ARTIFACT_TYPE,
  cloneProductDesignData,
  defaultProductSummaryData,
  NON_GOALS_ARTIFACT_TYPE,
  PERMISSION_INTENT_ARTIFACT_TYPE,
  PERMISSION_INTENT_FALLBACK_REVIEW_NOTE,
  PERMISSION_INTENT_FALLBACK_REVIEW_SOURCE,
  PRODUCT_SUMMARY_ARTIFACT_TYPE,
  productDesignArtifactId,
  SUCCESS_CRITERIA_ARTIFACT_TYPE,
  type ActorModelData,
  type BusinessAreasData,
  type NonGoalsData,
  type PermissionIntentData,
  type PermissionIntentRule,
  type ProductDesignArtifactData,
  type ProductDesignArtifactType,
  type ProductSummaryData,
  type SuccessCriteriaData,
} from './product-design'
import { runPmAssistantAction, type PmAssistantActionKey } from './assistant-actions'
import { inferScenarioCategory, makeRequirementsTemplate, slugify } from './intent-drafts'
import { isGovernedFrontingProject } from './source-documents'

export type ProductDesignDraftSectionId =
  | 'business_summary'
  | 'actor_model'
  | 'business_areas'
  | 'permission_intent'
  | 'requirements'
  | 'scenarios'
  | 'service_design'
  | 'non_goals'
  | 'success_criteria'

export interface ProductDesignDraftSection {
  id: ProductDesignDraftSectionId
  title: string
  action: PmAssistantActionKey
  envelope: AssistantProposalEnvelope | null
  selectedIds: string[]
  clarificationAnswers?: Record<string, string>
  usedClarificationAnswers?: AssistantClarificationAnswerContext[]
  status: 'proposed' | 'needs_clarification' | 'failed' | 'saved'
  error?: string
}

export interface AssistantClarificationAnswerContext {
  questionId: string
  prompt: string
  targetArtifact: string
  answer: string
  answeredAt: string
}

export interface ProductDesignDraftBundle {
  title: string
  summary: string
  sourceText: string
  sections: ProductDesignDraftSection[]
  createdAt: string
}

const SECTION_DEFS: Array<{ id: ProductDesignDraftSectionId; title: string; action: PmAssistantActionKey }> = [
  { id: 'business_summary', title: 'Business Summary', action: 'business_summary' },
  { id: 'actor_model', title: 'Actor Model', action: 'actor_model' },
  { id: 'business_areas', title: 'Business Areas', action: 'business_areas' },
  { id: 'permission_intent', title: 'Permission Intent', action: 'permission_intent' },
  { id: 'requirements', title: 'Requirements', action: 'requirements' },
  { id: 'scenarios', title: 'Scenarios', action: 'scenarios' },
  { id: 'service_design', title: 'Service Design', action: 'service_design' },
  { id: 'non_goals', title: 'Non-Goals', action: 'non_goals' },
  { id: 'success_criteria', title: 'Success Criteria', action: 'success_criteria' },
]

const ASSISTANT_SECTION_DRAFT_DELAY_MS = 600
const ASSISTANT_SECTION_RETRY_DELAY_MS = 1200
const ASSISTANT_SECTION_MAX_ATTEMPTS = 2

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => globalThis.setTimeout(resolve, ms))
}

function isAbortError(err: unknown, signal?: AbortSignal): boolean {
  return !!signal?.aborted || (err instanceof DOMException && err.name === 'AbortError')
}

async function runProductAssistantActionWithRetries(args: {
  section: { title: string; action: PmAssistantActionKey }
  projectId: string
  sourceText: string
  sourceRequirementsId?: string | null
  useDeterministic?: boolean
  serviceTopologyPreference?: AssistantServiceTopologyPreference | null
  signal?: AbortSignal
  onProgress?: (message: string) => void
}): Promise<AssistantProposalEnvelope> {
  const maxAttempts = args.useDeterministic ? 1 : ASSISTANT_SECTION_MAX_ATTEMPTS
  let lastError: unknown = null
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      return await runPmAssistantAction(args.section.action, {
        projectId: args.projectId,
        sourceText: args.sourceText,
        sourceRequirementsId: args.sourceRequirementsId,
        useDeterministic: args.useDeterministic,
        serviceTopologyPreference: args.serviceTopologyPreference,
        signal: args.signal,
      })
    } catch (err) {
      if (isAbortError(err, args.signal)) throw err
      lastError = err
      if (attempt < maxAttempts) {
        args.onProgress?.(`Retrying ${args.section.title} after assistant response validation failed (${attempt + 1}/${maxAttempts})`)
        await wait(ASSISTANT_SECTION_RETRY_DELAY_MS)
      }
    }
  }
  throw lastError instanceof Error ? lastError : new Error(String(lastError))
}

const PRODUCT_ARTIFACT_BY_SECTION: Partial<Record<ProductDesignDraftSectionId, ProductDesignArtifactType>> = {
  business_summary: PRODUCT_SUMMARY_ARTIFACT_TYPE,
  actor_model: ACTOR_MODEL_ARTIFACT_TYPE,
  business_areas: BUSINESS_AREAS_ARTIFACT_TYPE,
  permission_intent: PERMISSION_INTENT_ARTIFACT_TYPE,
  non_goals: NON_GOALS_ARTIFACT_TYPE,
  success_criteria: SUCCESS_CRITERIA_ARTIFACT_TYPE,
}

export function productArtifactTypeForDraftSection(sectionId: ProductDesignDraftSectionId): ProductDesignArtifactType | undefined {
  return PRODUCT_ARTIFACT_BY_SECTION[sectionId]
}

const PRODUCT_ARTIFACT_TITLE: Record<ProductDesignArtifactType, string> = {
  [PRODUCT_SUMMARY_ARTIFACT_TYPE]: 'Business Summary',
  [ACTOR_MODEL_ARTIFACT_TYPE]: 'Actor Model',
  [BUSINESS_AREAS_ARTIFACT_TYPE]: 'Business Areas',
  [PERMISSION_INTENT_ARTIFACT_TYPE]: 'Permission Intent',
  [NON_GOALS_ARTIFACT_TYPE]: 'Non-Goals',
  [SUCCESS_CRITERIA_ARTIFACT_TYPE]: 'Success Criteria',
}

export function proposalSelectionIds(envelope: AssistantProposalEnvelope): string[] {
  const proposal = envelope.proposal
  if (proposal.proposal_kind === 'candidate_blocks') {
    return (proposal.items ?? []).map((item) => item.client_id)
  }
  if (proposal.proposal_kind === 'clarification_questions') {
    return (proposal.questions ?? []).map((question) => question.question_id)
  }
  return (proposal.patches ?? []).map((_, index) => String(index))
}

function envelopeRequiresClarification(envelope: AssistantProposalEnvelope): boolean {
  return envelope.proposal.proposal_kind === 'clarification_questions'
}

function sectionFromEnvelope(
  section: { id: ProductDesignDraftSectionId; title: string; action: PmAssistantActionKey },
  envelope: AssistantProposalEnvelope,
  clarificationAnswers: Record<string, string> = {},
): ProductDesignDraftSection {
  return {
    ...section,
    envelope,
    selectedIds: proposalSelectionIds(envelope),
    clarificationAnswers,
    status: envelopeRequiresClarification(envelope) ? 'needs_clarification' : 'proposed',
  }
}

export async function draftProductDesignBundle(args: {
  projectId: string
  projectName: string
  sourceText: string
  pmArtifacts?: ArtifactRecord[]
  sourceRequirementsId?: string | null
  useDeterministic?: boolean
  serviceTopologyPreference?: AssistantServiceTopologyPreference | null
  signal?: AbortSignal
  onProgress?: (message: string) => void
}): Promise<ProductDesignDraftBundle> {
  const sections: ProductDesignDraftSection[] = []
  let inFlightPmArtifacts = [...(args.pmArtifacts ?? [])]
  for (let index = 0; index < SECTION_DEFS.length; index += 1) {
    const section = SECTION_DEFS[index]
    args.signal?.throwIfAborted()
    args.onProgress?.(`Drafting ${section.title} (${index + 1}/${SECTION_DEFS.length})`)
    try {
      const sourceText = sourceTextWithInFlightProductContext(args.sourceText, inFlightPmArtifacts)
      const envelope = await runProductAssistantActionWithRetries({
        section,
        projectId: args.projectId,
        sourceText,
        sourceRequirementsId: args.sourceRequirementsId,
        useDeterministic: args.useDeterministic,
        serviceTopologyPreference: args.serviceTopologyPreference,
        signal: args.signal,
        onProgress: args.onProgress,
      })
      const draftedSection = sectionFromEnvelope(section, envelope)
      sections.push(draftedSection)
      inFlightPmArtifacts = updateInFlightProductArtifacts(args.projectId, draftedSection, inFlightPmArtifacts)
      args.onProgress?.(`Completed ${section.title}`)
    } catch (err) {
      if (isAbortError(err, args.signal)) {
        throw err
      }
      sections.push({
        ...section,
        envelope: null,
        selectedIds: [],
        clarificationAnswers: {},
        status: 'failed',
        error: err instanceof Error ? err.message : String(err),
      })
      args.onProgress?.(`Could not draft ${section.title}; continuing with the next section`)
    }
    if (!args.useDeterministic && index < SECTION_DEFS.length - 1) {
      await wait(ASSISTANT_SECTION_DRAFT_DELAY_MS)
    }
  }

  return {
    title: `Product Design Draft: ${args.projectName}`,
    summary: 'Review this source-derived Product Design bundle, answer only blocking clarifications, and save accepted sections into deterministic Studio artifacts.',
    sourceText: args.sourceText,
    sections,
    createdAt: new Date().toISOString(),
  }
}

function sourceTextWithInFlightProductContext(sourceText: string, pmArtifacts: ArtifactRecord[]): string {
  const actorModel = pmArtifacts.find((artifact) => artifact.data?.artifact_type === ACTOR_MODEL_ARTIFACT_TYPE)?.data as ActorModelData | undefined
  const businessAreas = pmArtifacts.find((artifact) => artifact.data?.artifact_type === BUSINESS_AREAS_ARTIFACT_TYPE)?.data as BusinessAreasData | undefined
  const permissions = pmArtifacts.find((artifact) => artifact.data?.artifact_type === PERMISSION_INTENT_ARTIFACT_TYPE)?.data as PermissionIntentData | undefined

  const actorIds = (actorModel?.actors ?? []).map((actor) => String(actor.actor_id ?? '').trim()).filter(Boolean)
  const businessAreaIds = (businessAreas?.entries ?? []).map((entry) => String(entry.business_area_id ?? '').trim()).filter(Boolean)
  const permissionRules = (permissions?.rules ?? [])
    .map((rule) => `${rule.actor_id} | ${rule.business_area} | ${rule.access_posture} | ${rule.governed_outcome_type}`)
    .filter((line) => line.replace(/\|/g, '').trim())

  if (!actorIds.length && !businessAreaIds.length && !permissionRules.length) return sourceText

  const contextLines = [
    '---',
    'In-flight Product Design Context',
    '',
    'Studio generated this context earlier in the same Product Autopilot run. Treat it as already accepted draft context for subsequent Product sections. It is not additional business source material.',
  ]
  if (actorIds.length) {
    contextLines.push('', '## Actor IDs', ...actorIds.map((id) => `- \`${id}\``))
  }
  if (businessAreaIds.length) {
    contextLines.push('', '## Business Area IDs', ...businessAreaIds.map((id) => `- \`${id}\``))
  }
  if (permissionRules.length) {
    contextLines.push('', '## Permission Rule Drafts', ...permissionRules.map((line) => `- ${line}`))
  }
  return `${sourceText.trim()}\n\n${contextLines.join('\n')}`.trim()
}

function updateInFlightProductArtifacts(
  projectId: string,
  section: ProductDesignDraftSection,
  pmArtifacts: ArtifactRecord[],
): ArtifactRecord[] {
  const artifactType = PRODUCT_ARTIFACT_BY_SECTION[section.id]
  const proposal = section.envelope?.proposal
  if (!artifactType || !proposal || proposal.proposal_kind !== 'patch_candidates' || section.selectedIds.length === 0) {
    return pmArtifacts
  }
  const existing = pmArtifacts.find((artifact) => artifact.data?.artifact_type === artifactType)
  const base = existing?.data
    ? cloneProductDesignData(existing.data as ProductDesignArtifactData)
    : emptyProductArtifactData(artifactType)
  const data = normalizeProductArtifactData(artifactType, applySelectedPatches(base, proposal, section.selectedIds), pmArtifacts)
  const now = new Date().toISOString()
  const next: ArtifactRecord = {
    id: existing?.id ?? productDesignArtifactId(projectId, artifactType),
    project_id: projectId,
    title: existing?.title ?? PRODUCT_ARTIFACT_TITLE[artifactType],
    status: existing?.status ?? 'draft',
    data: data as Record<string, any>,
    content_hash: existing?.content_hash ?? '',
    created_at: existing?.created_at ?? now,
    updated_at: now,
  }
  return [
    ...pmArtifacts.filter((artifact) => artifact.id !== next.id && artifact.data?.artifact_type !== artifactType),
    next,
  ]
}

export async function redraftProductDesignSection(args: {
  projectId: string
  section: ProductDesignDraftSection
  sourceText: string
  sourceRequirementsId?: string | null
  useDeterministic?: boolean
  serviceTopologyPreference?: AssistantServiceTopologyPreference | null
  signal?: AbortSignal
}): Promise<ProductDesignDraftSection> {
  const envelope = await runProductAssistantActionWithRetries({
    section: args.section,
    projectId: args.projectId,
    sourceText: args.sourceText,
    sourceRequirementsId: args.sourceRequirementsId,
    useDeterministic: args.useDeterministic,
    serviceTopologyPreference: args.serviceTopologyPreference,
    signal: args.signal,
  })
  return sectionFromEnvelope(args.section, envelope, args.section.clarificationAnswers ?? {})
}

export function sectionItemCount(section: ProductDesignDraftSection): number {
  const proposal = section.envelope?.proposal
  if (!proposal) return 0
  if (proposal.proposal_kind === 'candidate_blocks') return proposal.items.length
  if (proposal.proposal_kind === 'clarification_questions') return proposal.questions.length
  return proposal.patches.length
}

export function selectedSectionItemCount(section: ProductDesignDraftSection): number {
  return section.selectedIds.length
}

export function toggleSectionSelection(section: ProductDesignDraftSection, id: string): ProductDesignDraftSection {
  const exists = section.selectedIds.includes(id)
  return {
    ...section,
    selectedIds: exists
      ? section.selectedIds.filter((item) => item !== id)
      : [...section.selectedIds, id],
  }
}

export function selectAllSectionItems(section: ProductDesignDraftSection): ProductDesignDraftSection {
  return section.envelope
    ? { ...section, selectedIds: proposalSelectionIds(section.envelope) }
    : section
}

export function clearSectionSelection(section: ProductDesignDraftSection): ProductDesignDraftSection {
  return { ...section, selectedIds: [] }
}

export function bundleOpenQuestions(bundle: ProductDesignDraftBundle | null): string[] {
  if (!bundle) return []
  const questions: string[] = []
  for (const section of bundle.sections) {
    if (!section.envelope) continue
    for (const question of section.envelope.questions_for_user) {
      questions.push(`${section.title}: ${question}`)
    }
    if (section.envelope.proposal.proposal_kind === 'clarification_questions') {
      for (const question of section.envelope.proposal.questions) {
        questions.push(`${section.title}: ${question.prompt}`)
      }
    }
  }
  return [...new Set(questions)].slice(0, 8)
}

export async function saveAcceptedProductDesignSection(args: {
  project: ProjectDetail
  section: ProductDesignDraftSection
  pmArtifacts: ArtifactRecord[]
  requirements?: RequirementsRecord[]
  scenarios?: ArtifactRecord[]
  sourceText?: string | null
}): Promise<void> {
  if (!args.section.envelope) {
    throw new Error('This section has no assistant proposal to save.')
  }
  if (args.section.selectedIds.length === 0) {
    throw new Error('Select at least one proposal item before saving this section.')
  }
  if (args.section.id === 'requirements') {
    await saveRequirementCandidates(args.project, args.section.envelope, args.section.selectedIds)
    return
  }
  if (args.section.id === 'scenarios') {
    await saveScenarioCandidates(args.project, args.section.envelope, args.section.selectedIds, args.pmArtifacts, args.scenarios ?? [])
    return
  }
  if (args.section.id === 'service_design') {
    await saveServiceDesignCandidate(args.project, args.section.envelope, args.section.selectedIds, args.requirements ?? [], args.scenarios ?? [], args.sourceText)
    return
  }
  await saveProductArtifactPatchSection(args.project.id, args.section, args.pmArtifacts)
}

async function saveRequirementCandidates(project: ProjectDetail, envelope: AssistantProposalEnvelope, acceptedIds: string[]) {
  const proposal = envelope.proposal
  if (proposal.proposal_kind !== 'candidate_blocks') {
    throw new Error('Requirements draft must contain candidate requirement blocks.')
  }
  const accepted = acceptedCandidateBlocks(proposal, acceptedIds)
  const data = makeRequirementsTemplate(project.name, project.domain)
  data.business_constraints = {
    ...data.business_constraints,
    assistant_drafted_requirements_count: accepted.length,
    assistant_drafted_requirements_summary: accepted
      .map((item) => `${item.title}: ${item.body}`)
      .join('\n'),
  }
  const created = await createRequirements(project.id, {
    id: `req-${crypto.randomUUID()}`,
    title: accepted.length === 1 ? accepted[0].title : 'Drafted Product Requirements',
    data,
  })
  await setRequirementsRole(project.id, created.id, 'primary')
}

async function saveScenarioCandidates(
  project: ProjectDetail,
  envelope: AssistantProposalEnvelope,
  acceptedIds: string[],
  pmArtifacts: ArtifactRecord[],
  scenarios: ArtifactRecord[],
) {
  const proposal = envelope.proposal
  if (proposal.proposal_kind !== 'candidate_blocks') {
    throw new Error('Scenario draft must contain candidate scenario blocks.')
  }
  const accepted = acceptedCandidateBlocks(proposal, acceptedIds)
  const normalized = accepted.map((item) => normalizeScenarioCandidate(item))
  await Promise.all(
    accepted.map((item, index) =>
      createScenario(project.id, {
        id: `scn-${crypto.randomUUID()}`,
        title: item.title,
        data: { scenario: normalized[index] },
      }),
    ),
  )
  await ensureFrontingCapabilityScenarioCoverage(project, pmArtifacts, scenarios, normalized)
}

async function saveServiceDesignCandidate(
  project: ProjectDetail,
  envelope: AssistantProposalEnvelope,
  acceptedIds: string[],
  requirements: RequirementsRecord[],
  scenarios: ArtifactRecord[],
  sourceText?: string | null,
) {
  const proposal = envelope.proposal
  if (proposal.proposal_kind !== 'candidate_blocks') {
    throw new Error('Service Design draft must contain candidate service design blocks.')
  }
  const accepted = acceptedCandidateBlocks(proposal, acceptedIds)
  const requirementsId =
    requirements.find((item) => item.role === 'primary')?.id
    ?? requirements[0]?.id
    ?? null
  if (!requirementsId) {
    throw new Error('Save requirements before saving an assistant-derived service design.')
  }
  const structuredShape = accepted
    .map((item) => item.structured_data?.shape ?? item.structured_data)
    .find((shape) => shape && typeof shape === 'object') as Record<string, unknown> | undefined
  const sourceCapabilityIds = isGovernedFrontingProject(project)
    ? sourceDeclaredProductCapabilityIds(sourceText ?? '')
    : []
  const shape = normalizeServiceShapeCandidate(structuredShape, accepted, project.name, sourceCapabilityIds)

  await createShape(project.id, {
    id: `shape-${crypto.randomUUID()}`,
    title: 'Assistant-Drafted Service Shape',
    requirements_id: requirementsId,
    data: {
      shape,
    },
  })
  await ensureScenarioCoordinationCoverage(project.id, shape, scenarios)
}

function normalizeScenarioCandidate(item: ReturnType<typeof acceptedCandidateBlocks>[number]) {
  const structured = item.structured_data?.scenario && typeof item.structured_data.scenario === 'object'
    ? item.structured_data.scenario as Record<string, any>
    : item.structured_data && typeof item.structured_data === 'object'
      ? item.structured_data as Record<string, any>
      : {}
  const structuredContext = structured.context && typeof structured.context === 'object'
    ? structured.context as Record<string, unknown>
    : {}
  const expectedBehavior = normalizeStringList(structured.expected_behavior)
  const expectedAnipSupport = normalizeStringList(structured.expected_anip_support)
  const scenarioName = slugify(String(structured.name ?? item.title ?? '').trim())
  const rawCategory = String(structured.category ?? '').trim()
  return {
    name: scenarioName || `scenario-${crypto.randomUUID()}`,
    category: normalizeScenarioCategory(rawCategory, [item.title, item.body, item.rationale].filter(Boolean).join(' ')),
    narrative: String(structured.narrative ?? item.body).trim(),
    context: {
      source: 'assistant_product_design_bundle',
      rationale: item.rationale,
      confidence: item.confidence,
      actor_context: String(structured.actor_context ?? structured.actor ?? '').trim(),
      business_scope: String(structured.business_scope ?? '').trim(),
      time_scope: String(structured.time_scope ?? '').trim(),
      capability: String(structured.primary_capability ?? structured.capability ?? structuredContext.capability ?? '').trim(),
    },
    participating_services: normalizeStringList(structured.participating_services),
    orchestration_steps: normalizeOrchestrationSteps(structured.orchestration_steps),
    expected_behavior: expectedBehavior.length ? expectedBehavior : [item.body],
    expected_anip_support: expectedAnipSupport.length
      ? expectedAnipSupport
      : ['The contract should make bounded behavior, required clarification, and stop conditions explicit.'],
  }
}

function normalizeServiceShapeCandidate(
  structured: Record<string, unknown> | undefined,
  accepted: ReturnType<typeof acceptedCandidateBlocks>,
  projectName: string,
  sourceCapabilityIds: string[] = [],
) {
  const services = Array.isArray(structured?.services)
    ? structured.services.map((service) => normalizeServiceCandidate(service as Record<string, unknown>))
    : []
  const fallbackServiceId = slugify(projectName) || 'primary-service'
  const normalizedServices = services.length
    ? services
    : [
        {
          id: fallbackServiceId,
          name: projectName,
          role: 'primary service',
          responsibilities: accepted.map((item) => item.body).filter(Boolean),
          capabilities: [
            'answer_governed_business_question',
            'prepare_governed_next_action',
            'explain_governed_outcome',
          ],
          owns_concepts: [],
        },
      ]
  const capabilityNormalization = normalizeServiceCapabilityOwnership(normalizedServices, sourceCapabilityIds)
  const domainConcepts = normalizeDomainConceptCandidates(structured?.domain_concepts, capabilityNormalization.services)
  const notes = normalizeStringList(structured?.notes).length
    ? normalizeStringList(structured?.notes)
    : accepted.map((item) => item.body).filter(Boolean)
  return {
    id: String(structured?.id ?? `shape-${crypto.randomUUID()}`),
    name: String(structured?.name ?? projectName),
    type: String(structured?.type ?? (capabilityNormalization.services.length > 1 ? 'multi_service' : 'single_service')),
    notes: [
      ...notes,
      ...capabilityNormalization.notes,
    ],
    services: capabilityNormalization.services.map((service) => ({
      ...service,
      owns_concepts: service.owns_concepts.filter((conceptId) =>
        domainConcepts.some((concept) => concept.id === conceptId),
      ),
    })),
    coordination: normalizeCoordinationCandidates(structured?.coordination, capabilityNormalization.services),
    domain_concepts: domainConcepts,
  }
}

async function ensureScenarioCoordinationCoverage(
  projectId: string,
  shape: ReturnType<typeof normalizeServiceShapeCandidate>,
  scenarios: ArtifactRecord[],
) {
  const serviceLabels = new Map(shape.services.map((service) => [service.id, service.name || service.id] as const))
  const existingServiceSets = scenarios.map((scenario) => {
    const scenarioData = scenario.data?.scenario && typeof scenario.data.scenario === 'object'
      ? scenario.data.scenario as Record<string, unknown>
      : {}
    return new Set(normalizeStringList(scenarioData.participating_services))
  })
  const missingEdges = shape.coordination.filter((edge) =>
    !existingServiceSets.some((serviceSet) => serviceSet.has(edge.from) && serviceSet.has(edge.to)),
  )

  await Promise.all(
    missingEdges.map((edge) => {
      const fromLabel = serviceLabels.get(edge.from) ?? edge.from
      const toLabel = serviceLabels.get(edge.to) ?? edge.to
      const relationship = edge.relationship || 'handoff'
      return createScenario(projectId, {
        id: `scn-${crypto.randomUUID()}`,
        title: `Review ${fromLabel} to ${toLabel} ${relationship}`,
        data: {
          scenario: {
            name: slugify(`${fromLabel}-${toLabel}-${relationship}`),
            category: 'cross_service',
            narrative: `A representative request requires ${fromLabel} and ${toLabel} to coordinate through a governed ${relationship} without hiding service ownership or stop conditions.`,
            context: {
              source: 'assistant_product_design_service_coverage',
              coordination_edge: { from: edge.from, to: edge.to, relationship },
            },
            participating_services: [edge.from, edge.to],
            orchestration_steps: [
              `${fromLabel} prepares only the bounded context it owns.`,
              `${toLabel} consumes the governed handoff context and preserves clarification, restriction, denial, or approval stops.`,
            ],
            expected_behavior: [
              'The product keeps service ownership visible across the coordination boundary.',
              'The product does not collapse a cross-service flow into hidden consumer-side glue.',
            ],
            expected_anip_support: [
              'ANIP metadata should expose the participating services, coordination boundary, and reviewable stop conditions.',
            ],
          },
        },
      })
    }),
  )
}

async function ensureFrontingCapabilityScenarioCoverage(
  project: ProjectDetail,
  pmArtifacts: ArtifactRecord[],
  existingScenarios: ArtifactRecord[],
  acceptedScenarios: Array<ReturnType<typeof normalizeScenarioCandidate>>,
) {
  if (!isGovernedFrontingProject(project)) return
  const mappings = pmArtifacts
    .filter((artifact) => artifact.data?.artifact_type === 'integration_fronting_capability_mapping')
    .map((artifact) => artifact.data as Record<string, any>)
    .filter((mapping) => String(mapping.capability_id ?? '').trim())
  if (!mappings.length) return

  const covered = new Set<string>()
  const addCovered = (scenario: Record<string, any> | null | undefined) => {
    const context = scenario?.context && typeof scenario.context === 'object'
      ? scenario.context as Record<string, unknown>
      : {}
    const capability = String(context.capability ?? context.primary_capability ?? '').trim()
    if (capability) covered.add(capability)
  }
  existingScenarios.forEach((scenario) => {
    const data = scenario.data?.scenario && typeof scenario.data.scenario === 'object'
      ? scenario.data.scenario as Record<string, any>
      : null
    addCovered(data)
  })
  acceptedScenarios.forEach((scenario) => addCovered(scenario))

  const missing = mappings.filter((mapping) => !covered.has(String(mapping.capability_id ?? '').trim()))
  await Promise.all(missing.map((mapping) => {
    const capabilityId = String(mapping.capability_id ?? '').trim()
    const serviceId = String(mapping.service_id ?? '').trim()
    const intent = String(mapping.intent ?? mapping.summary ?? mapping.description ?? '').trim()
    const operationType = String(mapping.operation_type ?? '').trim()
    const sideEffect = String(mapping.side_effect_level ?? '').trim()
    return createScenario(project.id, {
      id: `scn-${crypto.randomUUID()}`,
      title: `Review ${humanizeScenarioPart(capabilityId)} capability behavior`,
      data: {
        scenario: {
          name: slugify(`review-${capabilityId}-capability-behavior`),
          category: sideEffect === 'read' ? 'observability' : 'safety',
          narrative: intent || `A user invokes ${capabilityId}; the product preserves governed fronting behavior without exposing raw backend tools.`,
          context: {
            source: 'studio_fronting_template_coverage',
            capability: capabilityId,
            service_id: serviceId,
            operation_type: operationType,
            side_effect_level: sideEffect,
          },
          participating_services: serviceId ? [serviceId] : [],
          orchestration_steps: [
            'Resolve required business inputs or ask for clarification.',
            'Apply actor-visible scope and governed fronting policy before touching the backend.',
            sideEffect === 'read'
              ? 'Return bounded context without raw backend export.'
              : 'Prepare a preview or approval request before any downstream mutation.',
          ],
          expected_behavior: [
            sideEffect === 'read'
              ? 'The product returns bounded actor-visible context only.'
              : 'The product stops at preview or approval before executing backend mutation.',
            'The product does not expose raw backend tool semantics as the agent-facing contract.',
          ],
          expected_anip_support: [
            'The ANIP contract should preserve capability identity, required inputs, governed outcomes, and backend boundary evidence.',
          ],
        },
      },
    })
  }))
}

function humanizeScenarioPart(value: string): string {
  return value
    .replace(/[_-]+/g, ' ')
    .replace(/\./g, ' ')
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

function normalizeServiceCandidate(service: Record<string, unknown>) {
  const name = String(service.name ?? service.id ?? 'Service').trim()
  const id = String(service.id ?? slugify(name) ?? `service-${crypto.randomUUID()}`).trim()
  return {
    id,
    name,
    role: String(service.role ?? 'service').trim(),
    responsibilities: normalizeStringList(service.responsibilities),
    capabilities: normalizeStringList(service.capabilities),
    owns_concepts: normalizeStringList(service.owns_concepts),
  }
}

function normalizeStringList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.map((item) => String(item).trim()).filter(Boolean)
    : []
}

type NormalizedServiceCandidate = ReturnType<typeof normalizeServiceCandidate>

function sourceDeclaredProductCapabilityIds(sourceText: string): string[] {
  const result = new Set<string>()
  const addCapabilityId = (value: string) => {
    const normalized = value.trim()
    if (!isCanonicalCapabilityId(normalized)) return
    const lowered = normalized.toLowerCase()
    if (lowered.includes('.adapter.') || lowered.includes('.execution.') || lowered.includes('.backend.')) return
    result.add(normalized)
  }

  sourceText.split(/\r?\n/).forEach((line) => {
    const trimmed = line.trim()
    if (!trimmed) return
    const listMatch = /^[-*]\s+`?([a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+)`?\s*(?::|-|$)/i.exec(trimmed)
    if (listMatch) {
      addCapabilityId(listMatch[1])
      return
    }
    for (const match of trimmed.matchAll(/`([a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+)`/gi)) {
      addCapabilityId(match[1])
    }
  })

  return Array.from(result)
}

function isCanonicalCapabilityId(value: string): boolean {
  return /^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$/i.test(value.trim())
}

function capabilityTerms(capabilityId: string): string[] {
  const ignored = new Set(['gtm', 'service', 'summary', 'prepare', 'bounded', 'governed'])
  return Array.from(new Set(
    capabilityId
      .toLowerCase()
      .split(/[^a-z0-9]+/)
      .map((term) => term.trim())
      .filter((term) => term.length > 2 && !ignored.has(term)),
  ))
}

function serviceMatchText(service: NormalizedServiceCandidate): string {
  return [
    service.id,
    service.name,
    service.role,
    ...service.responsibilities,
    ...service.owns_concepts,
  ].join(' ').toLowerCase().replace(/[_-]+/g, ' ')
}

function scoreCapabilityServiceOwnership(capabilityId: string, service: NormalizedServiceCandidate): number {
  const text = serviceMatchText(service)
  return capabilityTerms(capabilityId).reduce((score, term) => score + (text.includes(term) ? 1 : 0), 0)
}

function normalizeServiceCapabilityOwnership(
  services: NormalizedServiceCandidate[],
  sourceCapabilityIds: string[] = [],
): { services: NormalizedServiceCandidate[]; notes: string[] } {
  const notes: string[] = []
  const occurrences = new Map<string, string[]>()
  const invalidByService = new Map<string, string[]>()
  const allowedSourceCapabilityIds = new Set(sourceCapabilityIds)

  services.forEach((service) => {
    service.capabilities.forEach((capabilityId) => {
      if (!isCanonicalCapabilityId(capabilityId)) {
        const invalid = invalidByService.get(service.id) ?? []
        invalid.push(capabilityId)
        invalidByService.set(service.id, invalid)
        return
      }
      if (allowedSourceCapabilityIds.size > 0 && !allowedSourceCapabilityIds.has(capabilityId)) {
        const invalid = invalidByService.get(service.id) ?? []
        invalid.push(capabilityId)
        invalidByService.set(service.id, invalid)
        return
      }
      const owners = occurrences.get(capabilityId) ?? []
      owners.push(service.id)
      occurrences.set(capabilityId, owners)
    })
  })

  const ownerByCapabilityId = new Map<string, string>()
  occurrences.forEach((ownerIds, capabilityId) => {
    const uniqueOwnerIds = Array.from(new Set(ownerIds))
    if (uniqueOwnerIds.length === 1) {
      ownerByCapabilityId.set(capabilityId, uniqueOwnerIds[0])
      return
    }
    const ranked = uniqueOwnerIds
      .map((serviceId) => {
        const service = services.find((item) => item.id === serviceId)
        return { serviceId, score: service ? scoreCapabilityServiceOwnership(capabilityId, service) : 0 }
      })
      .sort((left, right) => right.score - left.score)
    const best = ranked[0]
    const second = ranked[1]
    if (best && best.score > 0 && best.score > (second?.score ?? 0)) {
      ownerByCapabilityId.set(capabilityId, best.serviceId)
      notes.push(`Studio resolved duplicate capability "${capabilityId}" to service "${best.serviceId}" by service/capability token match.`)
      return
    }
    notes.push(`Studio removed ambiguous duplicate capability "${capabilityId}" from service ownership; confirm the canonical owner before using it as contract identity.`)
  })

  invalidByService.forEach((capabilities, serviceId) => {
    if (capabilities.length > 0) {
      notes.push(`Studio removed non-canonical capability labels from "${serviceId}": ${capabilities.slice(0, 8).join(', ')}.`)
    }
  })

  return {
    notes,
    services: services.map((service) => ({
      ...service,
      capabilities: Array.from(new Set(service.capabilities))
        .filter((capabilityId) => ownerByCapabilityId.get(capabilityId) === service.id),
    })),
  }
}

function normalizeDomainConceptCandidates(value: unknown, services: Array<{ id: string }>) {
  if (!Array.isArray(value)) return []
  const serviceIds = new Set(services.map((service) => service.id))
  const concepts = value.map((item, index) => {
    const raw: Record<string, unknown> = item && typeof item === 'object'
      ? item as Record<string, unknown>
      : { name: item }
    const name = String(raw.name ?? raw.id ?? item ?? `Concept ${index + 1}`).trim()
    const id = String(raw.id ?? slugify(name) ?? `concept-${index + 1}`).trim()
    const owner = String(raw.owner ?? '').trim()
    return {
      id,
      name,
      meaning: String(raw.meaning ?? raw.description ?? `Business concept: ${name}`).trim(),
      owner: owner === 'shared' || serviceIds.has(owner) ? owner : undefined,
      sensitivity: normalizeSensitivity(raw.sensitivity),
      risk_note: String(raw.risk_note ?? '').trim() || undefined,
    }
  })
  const seen = new Set<string>()
  return concepts.filter((concept) => {
    if (!concept.id || seen.has(concept.id)) return false
    seen.add(concept.id)
    return true
  })
}

function normalizeSensitivity(value: unknown): 'none' | 'medium' | 'high' {
  const normalized = String(value ?? '').trim().toLowerCase()
  return normalized === 'medium' || normalized === 'high' ? normalized : 'none'
}

function normalizeCoordinationCandidates(value: unknown, services: Array<{ id: string }>) {
  if (!Array.isArray(value)) return []
  const serviceIds = new Set(services.map((service) => service.id))
  return value
    .map((item) => item && typeof item === 'object' ? item as Record<string, unknown> : null)
    .filter((item): item is Record<string, unknown> => item != null)
    .map((item) => ({
      from: String(item.from ?? '').trim(),
      to: String(item.to ?? '').trim(),
      relationship: normalizeCoordinationRelationship(item.relationship),
      description: String(item.description ?? item.summary ?? '').trim() || undefined,
    }))
    .filter((edge) => serviceIds.has(edge.from) && serviceIds.has(edge.to))
}

function normalizeCoordinationRelationship(value: unknown): 'handoff' | 'verification' | 'async_followup' {
  const normalized = String(value ?? '').trim().toLowerCase()
  if (normalized === 'verification' || normalized === 'async_followup') return normalized
  return 'handoff'
}

function normalizeScenarioCategory(
  value: unknown,
  fallbackText: string,
): 'safety' | 'recovery' | 'orchestration' | 'cross_service' | 'observability' {
  const normalized = String(value ?? '').trim().toLowerCase()
  if (
    normalized === 'safety' ||
    normalized === 'recovery' ||
    normalized === 'orchestration' ||
    normalized === 'cross_service' ||
    normalized === 'observability'
  ) {
    return normalized
  }
  return inferScenarioCategory(fallbackText)
}

function normalizeOrchestrationSteps(value: unknown): string[] {
  return Array.isArray(value)
    ? value
      .map((item) => {
        if (typeof item === 'string') return item.trim()
        if (item && typeof item === 'object') {
          const record = item as Record<string, unknown>
          return String(
            record.description
              ?? record.summary
              ?? record.step
              ?? record.capability
              ?? record.name
              ?? '',
          ).trim()
        }
        return ''
      })
      .filter((item) => item && !isGenericStepPlaceholder(item))
    : []
}

function isGenericStepPlaceholder(value: string): boolean {
  return /^(step|phase|stage)\s*\d+$/i.test(value.trim())
}

async function saveProductArtifactPatchSection(
  projectId: string,
  section: ProductDesignDraftSection,
  pmArtifacts: ArtifactRecord[],
) {
  const artifactType = PRODUCT_ARTIFACT_BY_SECTION[section.id]
  if (!artifactType) {
    throw new Error(`Unsupported Product Design section: ${section.title}`)
  }
  const proposal = section.envelope?.proposal
  if (!proposal || proposal.proposal_kind !== 'patch_candidates') {
    throw new Error(`${section.title} draft must contain patch candidates.`)
  }
  const existing = pmArtifacts.find((artifact) => artifact.data?.artifact_type === artifactType)
  const base = existing?.data
    ? cloneProductDesignData(existing.data as ProductDesignArtifactData)
    : emptyProductArtifactData(artifactType)
  const data = normalizeProductArtifactData(artifactType, applySelectedPatches(base, proposal, section.selectedIds), pmArtifacts)
  if (existing) {
    await updatePmArtifact(projectId, existing.id, {
      title: PRODUCT_ARTIFACT_TITLE[artifactType],
      status: 'draft',
      data,
    })
  } else {
    await createPmArtifact(projectId, {
      id: productDesignArtifactId(projectId, artifactType),
      title: PRODUCT_ARTIFACT_TITLE[artifactType],
      data,
    })
  }
}

function acceptedCandidateBlocks(proposal: AssistantCandidateBlocksProposal, acceptedIds: string[]) {
  const accepted = proposal.items.filter((item) => acceptedIds.includes(item.client_id))
  if (!accepted.length) {
    throw new Error('Select at least one candidate block before saving.')
  }
  return accepted
}

function applySelectedPatches<T extends ProductDesignArtifactData>(
  base: T,
  proposal: AssistantPatchCandidatesProposal,
  acceptedIds: string[],
): T {
  const next = cloneProductDesignData(base)
  proposal.patches.forEach((patch, index) => {
    if (!acceptedIds.includes(String(index))) return
    applyJsonPointerPatch(next as Record<string, any>, patch.path, patch.op, patch.value)
  })
  return next
}

function applyJsonPointerPatch(target: Record<string, any>, path: string, op: string, value: unknown) {
  const parts = path.split('/').slice(1).map((part) => part.replace(/~1/g, '/').replace(/~0/g, '~'))
  if (!parts.length) return
  let cursor: any = target
  for (const part of parts.slice(0, -1)) {
    if (!(part in cursor) || cursor[part] == null) {
      cursor[part] = {}
    }
    cursor = cursor[part]
  }
  const last = parts[parts.length - 1]
  if (Array.isArray(cursor)) {
    if (last === '-') {
      cursor.push(value)
      return
    }
    const index = Number(last)
    if (op === 'remove') cursor.splice(index, 1)
    else if (op === 'add') cursor.splice(index, 0, value)
    else cursor[index] = value
    return
  }
  if (last === '-') return
  if (op === 'remove') {
    delete cursor[last]
  } else {
    cursor[last] = value
  }
}

function emptyProductArtifactData(type: ProductDesignArtifactType): ProductDesignArtifactData {
  switch (type) {
    case PRODUCT_SUMMARY_ARTIFACT_TYPE:
      return {
        ...defaultProductSummaryData(),
        business_goals: [],
        supported_question_families: [],
        multi_step_composition_rules: [],
      }
    case ACTOR_MODEL_ARTIFACT_TYPE:
      return { artifact_type: ACTOR_MODEL_ARTIFACT_TYPE, actors: [] } satisfies ActorModelData
    case BUSINESS_AREAS_ARTIFACT_TYPE:
      return { artifact_type: BUSINESS_AREAS_ARTIFACT_TYPE, entries: [] } satisfies BusinessAreasData
    case PERMISSION_INTENT_ARTIFACT_TYPE:
      return { artifact_type: PERMISSION_INTENT_ARTIFACT_TYPE, policy_summary: '', rules: [] } satisfies PermissionIntentData
    case NON_GOALS_ARTIFACT_TYPE:
      return { artifact_type: NON_GOALS_ARTIFACT_TYPE, entries: [] } satisfies NonGoalsData
    case SUCCESS_CRITERIA_ARTIFACT_TYPE:
      return { artifact_type: SUCCESS_CRITERIA_ARTIFACT_TYPE, entries: [] } satisfies SuccessCriteriaData
  }
}

function normalizeProductArtifactData(type: ProductDesignArtifactType, data: ProductDesignArtifactData, pmArtifacts: ArtifactRecord[] = []): ProductDesignArtifactData {
  if (type === PRODUCT_SUMMARY_ARTIFACT_TYPE) {
    const summary = data as ProductSummaryData
    return {
      ...summary,
      artifact_type: PRODUCT_SUMMARY_ARTIFACT_TYPE,
      business_goals: compactStringList(summary.business_goals),
      supported_question_families: compactStringList(summary.supported_question_families),
      multi_step_composition_rules: compactStringList(summary.multi_step_composition_rules),
    }
  }
  if (type === ACTOR_MODEL_ARTIFACT_TYPE) {
    const model = data as ActorModelData
    return {
      artifact_type: ACTOR_MODEL_ARTIFACT_TYPE,
      actors: (model.actors ?? []).filter((actor) =>
        [actor.actor_id, actor.title, actor.summary].some((value) => String(value ?? '').trim()),
      ),
    }
  }
  if (type === BUSINESS_AREAS_ARTIFACT_TYPE) {
    const model = data as BusinessAreasData
    return {
      artifact_type: BUSINESS_AREAS_ARTIFACT_TYPE,
      entries: (model.entries ?? []).filter((entry) =>
        [entry.business_area_id, entry.label, entry.description].some((value) => String(value ?? '').trim()),
      ),
    }
  }
  if (type === PERMISSION_INTENT_ARTIFACT_TYPE) {
    const model = data as PermissionIntentData
    return normalizePermissionIntentData(model, pmArtifacts)
  }
  if (type === NON_GOALS_ARTIFACT_TYPE) {
    const model = data as NonGoalsData
    return {
      artifact_type: NON_GOALS_ARTIFACT_TYPE,
      entries: (model.entries ?? []).filter((entry) =>
        [entry.statement, entry.rationale].some((value) => String(value ?? '').trim()),
      ),
    }
  }
  const model = data as SuccessCriteriaData
  return {
    artifact_type: SUCCESS_CRITERIA_ARTIFACT_TYPE,
    entries: (model.entries ?? []).filter((entry) =>
      [entry.statement, entry.evidence, entry.review_method].some((value) => String(value ?? '').trim()),
    ),
  }
}

function normalizePermissionIntentData(model: PermissionIntentData, pmArtifacts: ArtifactRecord[]): PermissionIntentData {
  const actorModel = pmArtifacts.find((artifact) => artifact.data?.artifact_type === ACTOR_MODEL_ARTIFACT_TYPE)?.data as ActorModelData | undefined
  const businessAreas = pmArtifacts.find((artifact) => artifact.data?.artifact_type === BUSINESS_AREAS_ARTIFACT_TYPE)?.data as BusinessAreasData | undefined
  const actorOptions = (actorModel?.actors ?? [])
    .map((actor) => ({ id: String(actor.actor_id ?? '').trim(), text: [actor.actor_id, actor.title, actor.summary, actor.notes].join(' ') }))
    .filter((actor) => actor.id)
  const areaOptions = (businessAreas?.entries ?? [])
    .map((entry) => ({ id: String(entry.business_area_id ?? '').trim(), text: [entry.business_area_id, entry.label, entry.description].join(' ') }))
    .filter((entry) => entry.id)
  const normalizedRules = (model.rules ?? [])
    .map((rule) => {
      const actor = resolveKnownReference(rule.actor_id, actorOptions, [rule.governed_outcome, rule.notes, rule.access_posture].join(' '))
      const area = resolveKnownReference(rule.business_area, areaOptions, [rule.governed_outcome, rule.notes, rule.access_posture].join(' '))
      const notes = [
        String(rule.notes ?? '').trim(),
        String(rule.actor_id ?? '').trim() && actor && actor !== String(rule.actor_id ?? '').trim() ? `Studio mapped assistant actor reference "${rule.actor_id}" to existing actor "${actor}".` : '',
        String(rule.business_area ?? '').trim() && area && area !== String(rule.business_area ?? '').trim() ? `Studio mapped assistant business-area reference "${rule.business_area}" to existing business area "${area}".` : '',
      ].filter(Boolean).join(' ')
      return {
        actor_id: actor ?? slugify(String(rule.actor_id ?? '').trim()),
        business_area: area ?? slugify(String(rule.business_area ?? '').trim()),
        access_posture: normalizePermissionAccessPosture(rule.access_posture),
        governed_outcome_type: normalizePermissionOutcomeType(rule.governed_outcome_type),
        governed_outcome: String(rule.governed_outcome ?? '').trim(),
        notes,
        review_source: String(rule.review_source ?? '').trim() || undefined,
      }
    })
    .filter((rule) =>
      [rule.actor_id, rule.business_area, rule.governed_outcome_type, rule.governed_outcome].some((value) => String(value ?? '').trim()),
    )
  const fallbackRules = normalizedRules.length === 0 && String(model.policy_summary ?? '').trim()
    ? fallbackPermissionRules(actorOptions.map((actor) => actor.id), areaOptions.map((area) => area.id))
    : []
  return {
    artifact_type: PERMISSION_INTENT_ARTIFACT_TYPE,
    policy_summary: model.policy_summary ?? '',
    rules: normalizedRules.length ? normalizedRules : fallbackRules,
  }
}

function fallbackPermissionRules(actorIds: string[], businessAreaIds: string[]): PermissionIntentRule[] {
  if (!actorIds.length || !businessAreaIds.length) return []
  return actorIds.flatMap((actorId) =>
    businessAreaIds.map((businessAreaId) => ({
      actor_id: actorId,
      business_area: businessAreaId,
      access_posture: 'bounded',
      governed_outcome_type: 'bounded_result',
      governed_outcome: `Allow bounded, reviewable ${humanizePermissionPart(businessAreaId)} behavior for ${humanizePermissionPart(actorId)} when the request stays within actor-visible scope; clarify missing critical context, deny raw export or unsupported mutation, and stop for approval before side effects.`,
      notes: `${PERMISSION_INTENT_FALLBACK_REVIEW_NOTE}. Confirm or edit before locking Product Design.`,
      review_source: PERMISSION_INTENT_FALLBACK_REVIEW_SOURCE,
    })),
  )
}

function humanizePermissionPart(value: string): string {
  return value.replace(/[_-]+/g, ' ').trim() || value
}

function resolveKnownReference(
  value: unknown,
  options: Array<{ id: string; text: string }>,
  context: string,
): string | null {
  const raw = String(value ?? '').trim()
  if (!options.length) return raw || null
  const exact = options.find((option) => option.id === raw)
  if (exact) return exact.id
  const rawSlug = slugify(raw)
  const slugMatch = options.find((option) => option.id === rawSlug || slugify(option.text) === rawSlug)
  if (slugMatch) return slugMatch.id
  const candidateTokens = new Set(normalizeReferenceTokens([raw, context].join(' ')))
  let best: { id: string; score: number } | null = null
  for (const option of options) {
    const tokens = normalizeReferenceTokens(option.text)
    const score = tokens.reduce((sum, token) => sum + (candidateTokens.has(token) ? 1 : 0), 0)
    if (score > (best?.score ?? 0)) {
      best = { id: option.id, score }
    }
  }
  if (best && best.score > 0) return best.id
  return null
}

function normalizeReferenceTokens(value: string): string[] {
  return Array.from(new Set(value
    .toLowerCase()
    .split(/[^a-z0-9]+/g)
    .map((token) => token.trim())
    .filter((token) => token.length > 2)))
}

function normalizePermissionAccessPosture(value: unknown): PermissionIntentData['rules'][number]['access_posture'] {
  const normalized = String(value ?? '').trim().toLowerCase()
  if (normalized === 'allowed' || normalized === 'bounded' || normalized === 'restricted' || normalized === 'denied' || normalized === 'approval_required') {
    return normalized
  }
  if (normalized.includes('approval')) return 'approval_required'
  if (normalized.includes('deny') || normalized.includes('forbid')) return 'denied'
  if (normalized.includes('restrict') || normalized.includes('mask') || normalized.includes('limited')) return 'restricted'
  if (normalized.includes('allow') || normalized.includes('direct')) return 'allowed'
  return 'bounded'
}

function normalizePermissionOutcomeType(value: unknown): PermissionIntentData['rules'][number]['governed_outcome_type'] {
  const normalized = String(value ?? '').trim().toLowerCase()
  if (
    normalized === 'direct_result' ||
    normalized === 'bounded_result' ||
    normalized === 'masked_or_restricted_result' ||
    normalized === 'deny_request' ||
    normalized === 'approval_stop' ||
    normalized === 'clarification_required'
  ) {
    return normalized
  }
  if (normalized.includes('approval')) return 'approval_stop'
  if (normalized.includes('clarif')) return 'clarification_required'
  if (normalized.includes('deny') || normalized.includes('forbid')) return 'deny_request'
  if (normalized.includes('mask') || normalized.includes('restrict')) return 'masked_or_restricted_result'
  if (normalized.includes('direct')) return 'direct_result'
  return 'bounded_result'
}

function compactStringList(values: string[] | undefined): string[] {
  return (values ?? []).map((item) => item.trim()).filter(Boolean)
}
