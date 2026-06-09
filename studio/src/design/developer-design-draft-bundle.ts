import { applyAssistantProposal } from './project-api'
import type {
  AssistantProposalEnvelope,
  AssistantServiceTopologyPreference,
  ArtifactRecord,
  RequirementsRecord,
  ShapeRecord,
} from './project-types'
import { runDevAssistantAction, type DevAssistantActionKey } from './assistant-actions'
import {
  proposalSelectionIds,
  type AssistantClarificationAnswerContext,
} from './product-design-draft-bundle'

export type DeveloperDesignDraftSectionId =
  | 'service_design'
  | 'capability_formalization'
  | 'runtime_policy_bindings'
  | 'input_contracts'
  | 'backend_bindings'
  | 'verification_expectations'

export interface DeveloperDesignDraftSection {
  id: DeveloperDesignDraftSectionId
  title: string
  action: DevAssistantActionKey
  envelope: AssistantProposalEnvelope | null
  selectedIds: string[]
  clarificationAnswers?: Record<string, string>
  usedClarificationAnswers?: AssistantClarificationAnswerContext[]
  status: 'proposed' | 'needs_clarification' | 'failed' | 'saved'
  error?: string
}

export interface DeveloperDesignDraftBundle {
  title: string
  summary: string
  baselineText: string
  sourceText: string
  sections: DeveloperDesignDraftSection[]
  createdAt: string
}

const SECTION_DEFS: Array<{ id: DeveloperDesignDraftSectionId; title: string; action: DevAssistantActionKey }> = [
  { id: 'service_design', title: 'Service Design', action: 'service_design' },
  { id: 'input_contracts', title: 'Input Contracts', action: 'input_contracts' },
  { id: 'capability_formalization', title: 'Capability Formalization', action: 'capability_formalization' },
  { id: 'runtime_policy_bindings', title: 'Runtime Policy Bindings', action: 'runtime_policy_bindings' },
  { id: 'backend_bindings', title: 'Runtime Backends', action: 'backend_bindings' },
  { id: 'verification_expectations', title: 'Evidence & Verification Plan', action: 'verification_expectations' },
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

async function runDeveloperAssistantActionWithRetries(args: {
  section: { title: string; action: DevAssistantActionKey }
  projectId: string
  baselineText: string
  sourceText: string
  sourceRequirementsId?: string | null
  sourceShapeId?: string | null
  useDeterministic?: boolean
  serviceTopologyPreference?: AssistantServiceTopologyPreference | null
  signal?: AbortSignal
  onProgress?: (message: string) => void
}): Promise<AssistantProposalEnvelope> {
  const maxAttempts = args.useDeterministic ? 1 : ASSISTANT_SECTION_MAX_ATTEMPTS
  let lastError: unknown = null
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      return await runDevAssistantAction(args.section.action, {
        projectId: args.projectId,
        sourceText: args.sourceText,
        sourceRequirementsId: args.sourceRequirementsId,
        sourceShapeId: args.sourceShapeId,
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

function envelopeRequiresClarification(envelope: AssistantProposalEnvelope): boolean {
  return envelope.proposal.proposal_kind === 'clarification_questions'
}

function sectionFromEnvelope(
  section: { id: DeveloperDesignDraftSectionId; title: string; action: DevAssistantActionKey },
  envelope: AssistantProposalEnvelope,
  clarificationAnswers: Record<string, string> = {},
): DeveloperDesignDraftSection {
  return {
    ...section,
    envelope,
    selectedIds: proposalSelectionIds(envelope),
    clarificationAnswers,
    status: envelopeRequiresClarification(envelope) ? 'needs_clarification' : 'proposed',
  }
}

function capabilityInventoryFromInputContracts(envelope: AssistantProposalEnvelope | null): unknown[] {
  const items = envelope?.proposal.proposal_kind === 'candidate_blocks' ? envelope.proposal.items : []
  const capabilities: unknown[] = []
  items.forEach((item) => {
    const structured = item.structured_data as Record<string, unknown> | null | undefined
    if (Array.isArray(structured?.capabilities)) {
      capabilities.push(...structured.capabilities)
    }
  })
  return capabilities
}

function candidateCapabilityEntries(envelope: AssistantProposalEnvelope | null): Record<string, any>[] {
  const items = envelope?.proposal.proposal_kind === 'candidate_blocks' ? envelope.proposal.items : []
  const capabilities: Record<string, any>[] = []
  items.forEach((item) => {
    const structured = item.structured_data as Record<string, unknown> | null | undefined
    for (const key of ['capabilities', 'capability_contracts']) {
      const value = structured?.[key]
      if (Array.isArray(value)) {
        capabilities.push(...value.filter((entry): entry is Record<string, any> =>
          !!entry && typeof entry === 'object',
        ))
      }
    }
  })
  return capabilities
}

function isCanonicalCapabilityId(value: string): boolean {
  return /^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$/i.test(value.trim())
}

export function validateDeveloperDraftSectionContract(section: DeveloperDesignDraftSection): string[] {
  if (section.id !== 'capability_formalization') return []
  const issues: string[] = []
  candidateCapabilityEntries(section.envelope).forEach((capability) => {
    const capabilityId = String(capability.capability_id ?? '').trim()
    if (!capabilityId) return
    if (!isCanonicalCapabilityId(capabilityId)) {
      issues.push(`Capability ${capabilityId} is not a valid dotted capability id.`)
      return
    }
    const inputs = Array.isArray(capability.inputs) ? capability.inputs : []
    const inputNames = new Set<string>()
    inputs.forEach((input: Record<string, unknown>) => {
      const inputName = String(input?.input_name ?? input?.name ?? '').trim()
      if (!inputName) return
      if (inputNames.has(inputName)) {
        issues.push(`${capabilityId} declares duplicate input ${inputName}.`)
      }
      inputNames.add(inputName)
    })
    const kind = String(capability.kind ?? '').trim().toLowerCase()
    if (kind !== 'composed') return
    const composition = capability.composition && typeof capability.composition === 'object'
      ? capability.composition as Record<string, any>
      : null
    const steps = Array.isArray(composition?.steps) ? composition.steps : []
    if (steps.length === 0) {
      issues.push(`${capabilityId} is composed but does not define composition steps.`)
    }
    if (!composition || String(composition.authority_boundary ?? '').trim() === '') {
      issues.push(`${capabilityId} is composed but does not define an authority boundary.`)
    }
    if (!composition || !composition.input_mapping || Object.keys(composition.input_mapping).length === 0) {
      issues.push(`${capabilityId} is composed but does not define input mapping.`)
    }
    if (!composition || !composition.output_mapping || Object.keys(composition.output_mapping).length === 0) {
      issues.push(`${capabilityId} is composed but does not define output mapping.`)
    }
    if (!composition || !composition.failure_policy || Object.keys(composition.failure_policy).length === 0) {
      issues.push(`${capabilityId} is composed but does not define failure policy.`)
    }
  })
  return [...new Set(issues)]
}

function sourceTextWithDeveloperDraftEvidence(sourceText: string, section: DeveloperDesignDraftSection): string {
  if (section.id !== 'input_contracts' || section.status === 'needs_clarification') return sourceText
  const capabilities = capabilityInventoryFromInputContracts(section.envelope)
  if (!capabilities.length) return sourceText
  return [
    sourceText,
    '',
    '# Draft Developer Input Contract Evidence',
    '',
    'The following input contracts were drafted by the prior Developer Design section in this same review bundle. They are candidates for human review, not saved contract truth until accepted.',
    '',
    '```json',
    JSON.stringify({ canonical_capability_inventory: capabilities }, null, 2),
    '```',
  ].join('\n')
}

export function buildDeveloperBaselineSourceText(args: {
  projectName: string
  requirements: RequirementsRecord | null
  scenarios: ArtifactRecord[]
  shape: ShapeRecord | null
  baselineLockedAt?: string | null
}): string {
  return JSON.stringify(
    {
      source: 'locked_product_design_baseline',
      project_name: args.projectName,
      baseline_locked_at: args.baselineLockedAt ?? null,
      requirements: args.requirements
        ? {
            id: args.requirements.id,
            title: args.requirements.title,
            data: args.requirements.data,
          }
        : null,
      scenarios: args.scenarios.map((scenario) => ({
        id: scenario.id,
        title: scenario.title,
        data: scenario.data,
      })),
      service_design: args.shape
        ? {
            id: args.shape.id,
            title: args.shape.title,
            data: args.shape.data,
          }
        : null,
    },
    null,
    2,
  )
}

export async function draftDeveloperDesignBundle(args: {
  projectId: string
  projectName: string
  baselineText: string
  sourceText?: string | null
  sourceRequirementsId?: string | null
  sourceShapeId?: string | null
  useDeterministic?: boolean
  serviceTopologyPreference?: AssistantServiceTopologyPreference | null
  signal?: AbortSignal
  onProgress?: (message: string) => void
}): Promise<DeveloperDesignDraftBundle> {
  const sections: DeveloperDesignDraftSection[] = []
  const originalSourceText = args.sourceText?.trim() || args.baselineText
  let rollingSourceText = originalSourceText
  for (let index = 0; index < SECTION_DEFS.length; index += 1) {
    const section = SECTION_DEFS[index]
    args.signal?.throwIfAborted()
    args.onProgress?.(`Drafting ${section.title} (${index + 1}/${SECTION_DEFS.length})`)
    try {
      const envelope = await runDeveloperAssistantActionWithRetries({
        section,
        projectId: args.projectId,
        baselineText: args.baselineText,
        sourceText: rollingSourceText,
        sourceRequirementsId: args.sourceRequirementsId,
        sourceShapeId: args.sourceShapeId,
        useDeterministic: args.useDeterministic,
        serviceTopologyPreference: args.serviceTopologyPreference,
        signal: args.signal,
        onProgress: args.onProgress,
      })
      const draftedSection = sectionFromEnvelope(section, envelope)
      const contractIssues = validateDeveloperDraftSectionContract(draftedSection)
      if (contractIssues.length > 0) {
        sections.push({
          ...draftedSection,
          status: 'failed',
          selectedIds: [],
          error: [
            'Autopilot stopped because the drafted Developer Design section is not contract-complete.',
            ...contractIssues.slice(0, 12),
          ].join(' '),
        })
        args.onProgress?.(`Stopped at ${section.title}; the draft is not contract-complete.`)
        break
      }
      sections.push(draftedSection)
      if (envelopeRequiresClarification(envelope)) {
        args.onProgress?.(`Stopped at ${section.title}; clarification is required before later Developer Design sections can be drafted safely.`)
        break
      }
      rollingSourceText = sourceTextWithDeveloperDraftEvidence(rollingSourceText, draftedSection)
      args.onProgress?.(`Completed ${section.title}`)
    } catch (err) {
      if (isAbortError(err, args.signal)) {
        throw err
      }
      const message = err instanceof Error ? err.message : String(err)
      args.onProgress?.(`Could not draft ${section.title}; stopping Developer Design draft`)
      throw new Error(`Could not draft ${section.title}: ${message}`)
    }
    if (!args.useDeterministic && index < SECTION_DEFS.length - 1) {
      await wait(ASSISTANT_SECTION_DRAFT_DELAY_MS)
    }
  }

  return {
    title: `Developer Design Draft: ${args.projectName}`,
    summary: 'Review this locked-baseline-derived Developer Design bundle and save accepted proposal sections into assistant review artifacts.',
    baselineText: args.baselineText,
    sourceText: originalSourceText,
    sections,
    createdAt: new Date().toISOString(),
  }
}

export async function redraftDeveloperDesignSection(args: {
  projectId: string
  section: DeveloperDesignDraftSection
  baselineText: string
  sourceText?: string | null
  sourceRequirementsId?: string | null
  sourceShapeId?: string | null
  useDeterministic?: boolean
  serviceTopologyPreference?: AssistantServiceTopologyPreference | null
  signal?: AbortSignal
}): Promise<DeveloperDesignDraftSection> {
  const envelope = await runDeveloperAssistantActionWithRetries({
    section: args.section,
    projectId: args.projectId,
    baselineText: args.baselineText,
    sourceText: args.sourceText?.trim() || args.baselineText,
    sourceRequirementsId: args.sourceRequirementsId,
    sourceShapeId: args.sourceShapeId,
    useDeterministic: args.useDeterministic,
    serviceTopologyPreference: args.serviceTopologyPreference,
    signal: args.signal,
  })
  return sectionFromEnvelope(args.section, envelope, args.section.clarificationAnswers ?? {})
}

export function developerBundleOpenQuestions(bundle: DeveloperDesignDraftBundle | null): string[] {
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

export function developerSectionItemCount(section: DeveloperDesignDraftSection): number {
  const proposal = section.envelope?.proposal
  if (!proposal) return 0
  if (proposal.proposal_kind === 'candidate_blocks') return proposal.items.length
  if (proposal.proposal_kind === 'clarification_questions') return proposal.questions.length
  return proposal.patches.length
}

export function selectedDeveloperSectionItemCount(section: DeveloperDesignDraftSection): number {
  return section.selectedIds.length
}

export function toggleDeveloperSectionSelection(
  section: DeveloperDesignDraftSection,
  id: string,
): DeveloperDesignDraftSection {
  const exists = section.selectedIds.includes(id)
  return {
    ...section,
    selectedIds: exists
      ? section.selectedIds.filter((item) => item !== id)
      : [...section.selectedIds, id],
  }
}

export function selectAllDeveloperSectionItems(section: DeveloperDesignDraftSection): DeveloperDesignDraftSection {
  return section.envelope
    ? { ...section, selectedIds: proposalSelectionIds(section.envelope) }
    : section
}

export function clearDeveloperSectionSelection(section: DeveloperDesignDraftSection): DeveloperDesignDraftSection {
  return { ...section, selectedIds: [] }
}

export async function saveAcceptedDeveloperDesignSection(args: {
  projectId: string
  section: DeveloperDesignDraftSection
  notes?: string
}): Promise<ArtifactRecord> {
  if (!args.section.envelope) {
    throw new Error('This section has no assistant proposal to save.')
  }
  if (args.section.selectedIds.length === 0) {
    throw new Error('Select at least one proposal item before saving this section.')
  }
  const allItemIds = proposalSelectionIds(args.section.envelope)
  const rejectedIds = allItemIds.filter((id) => !args.section.selectedIds.includes(id))
  return applyAssistantProposal(args.projectId, {
    artifact_id: `pm-artifact-${crypto.randomUUID()}`,
    title: args.section.envelope.title || args.section.title,
    capability: args.section.envelope.capability,
    proposal: args.section.envelope.proposal,
    accepted_item_ids: [...args.section.selectedIds],
    rejected_item_ids: rejectedIds,
    notes: args.notes,
  })
}
