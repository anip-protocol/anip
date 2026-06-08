import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  buildDeveloperBaselineSourceText,
  draftDeveloperDesignBundle,
  redraftDeveloperDesignSection,
  saveAcceptedDeveloperDesignSection,
  type DeveloperDesignDraftSection,
} from '../design/developer-design-draft-bundle'
import type { AssistantProposalEnvelope } from '../design/project-types'

const mocks = vi.hoisted(() => ({
  applyAssistantProposal: vi.fn(),
  runDevAssistantAction: vi.fn(),
}))

vi.mock('../design/project-api', async () => {
  const actual = await vi.importActual<typeof import('../design/project-api')>('../design/project-api')
  return {
    ...actual,
    applyAssistantProposal: (...args: any[]) => mocks.applyAssistantProposal(...args),
  }
})

vi.mock('../design/assistant-actions', async () => {
  const actual = await vi.importActual<typeof import('../design/assistant-actions')>('../design/assistant-actions')
  return {
    ...actual,
    runDevAssistantAction: (...args: any[]) => mocks.runDevAssistantAction(...args),
  }
})

function envelope(capability: string, options?: { clarification?: boolean }): AssistantProposalEnvelope {
  if (options?.clarification) {
    return {
      title: 'Clarify Runtime Policy',
      summary: 'A developer clarification is needed.',
      mode: 'dev',
      capability,
      questions_for_user: ['Where should the runtime stop for approval?'],
      watchouts: [],
      next_steps: [],
      proposal: {
        proposal_kind: 'clarification_questions',
        mode: 'dev',
        section_key: 'authority_and_approval',
        questions: [
          {
            question_id: 'q-1',
            prompt: 'Where should the runtime stop for approval?',
            why_it_matters: 'Approval boundaries affect runtime policy.',
            target_artifact: 'authority_and_approval',
          },
        ],
      },
    }
  }

  return {
    title: `${capability} proposal`,
    summary: 'Drafted from locked baseline.',
    mode: 'dev',
    capability,
    questions_for_user: [],
    watchouts: [],
    next_steps: [],
    proposal: {
      proposal_kind: 'candidate_blocks',
      artifact_type: capability,
      items: [
        {
          client_id: `${capability}-1`,
          title: 'Draft candidate',
          body: 'Candidate text derived from the locked baseline.',
          confidence: 'high',
          rationale: 'The locked baseline contains enough signal.',
        },
      ],
    },
  }
}

function section(): DeveloperDesignDraftSection {
  const env = envelope('propose_service_design')
  return {
    id: 'service_design',
    title: 'Service Design',
    action: 'service_design',
    envelope: env,
    selectedIds: ['propose_service_design-1'],
    status: 'proposed',
  }
}

describe('developer-design-draft-bundle', () => {
  beforeEach(() => {
    vi.stubGlobal('crypto', { randomUUID: () => 'uuid-1' })
    mocks.applyAssistantProposal.mockReset()
    mocks.runDevAssistantAction.mockReset()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('builds grounded source text from the locked PM baseline', () => {
    const text = buildDeveloperBaselineSourceText({
      projectName: 'Revenue Ops Assistant',
      baselineLockedAt: '2026-04-20T00:00:00Z',
      requirements: {
        id: 'req-1',
        project_id: 'proj-1',
        title: 'Requirements',
        status: 'active',
        role: 'primary',
        data: { system: { name: 'Revenue Ops Assistant' } },
        content_hash: 'req-hash',
        created_at: '2026-04-20T00:00:00Z',
        updated_at: '2026-04-20T00:00:00Z',
      },
      scenarios: [
        {
          id: 'scn-1',
          project_id: 'proj-1',
          title: 'Pipeline risk review',
          status: 'active',
          data: { scenario: { name: 'pipeline_risk_review' } },
          content_hash: 'scn-hash',
          created_at: '2026-04-20T00:00:00Z',
          updated_at: '2026-04-20T00:00:00Z',
        },
      ],
      shape: {
        id: 'shape-1',
        project_id: 'proj-1',
        title: 'Service Shape',
        status: 'active',
        requirements_id: 'req-1',
        data: { shape: { services: [{ id: 'pipeline' }] } },
        content_hash: 'shape-hash',
        created_at: '2026-04-20T00:00:00Z',
        updated_at: '2026-04-20T00:00:00Z',
      },
    })

    expect(JSON.parse(text)).toMatchObject({
      source: 'locked_product_design_baseline',
      project_name: 'Revenue Ops Assistant',
      requirements: { id: 'req-1' },
      scenarios: [{ id: 'scn-1' }],
      service_design: { id: 'shape-1' },
    })
  })

  it('stops developer drafting at the first clarification boundary', async () => {
    mocks.runDevAssistantAction.mockImplementation(async (action: string) =>
      envelope(action, { clarification: action === 'runtime_policy_bindings' }),
    )

    const bundle = await draftDeveloperDesignBundle({
      projectId: 'proj-1',
      projectName: 'Revenue Ops Assistant',
      baselineText: 'locked baseline json',
      sourceRequirementsId: 'req-1',
      sourceShapeId: 'shape-1',
    })

    expect(bundle.sections.map((item) => item.id)).toEqual([
      'service_design',
      'input_contracts',
      'capability_formalization',
      'runtime_policy_bindings',
    ])
    expect(bundle.sections.find((item) => item.id === 'runtime_policy_bindings')?.status).toBe('needs_clarification')
    expect(mocks.runDevAssistantAction).toHaveBeenCalledWith('service_design', {
      projectId: 'proj-1',
      sourceText: 'locked baseline json',
      sourceRequirementsId: 'req-1',
      sourceShapeId: 'shape-1',
      serviceTopologyPreference: undefined,
    })
  })

  it('stops developer drafting when a contract section fails validation', async () => {
    mocks.runDevAssistantAction.mockImplementation(async (action: string) => {
      if (action === 'capability_formalization') {
        throw new Error('assistant response failed source-grounding validation')
      }
      return envelope(action)
    })

    await expect(draftDeveloperDesignBundle({
      projectId: 'proj-1',
      projectName: 'Revenue Ops Assistant',
      baselineText: 'locked baseline json',
      sourceRequirementsId: 'req-1',
      sourceShapeId: 'shape-1',
    })).rejects.toThrow('Could not draft Capability Formalization')

    expect(mocks.runDevAssistantAction).toHaveBeenCalledTimes(4)
    expect(mocks.runDevAssistantAction).toHaveBeenNthCalledWith(1, 'service_design', expect.any(Object))
    expect(mocks.runDevAssistantAction).toHaveBeenNthCalledWith(2, 'input_contracts', expect.any(Object))
    expect(mocks.runDevAssistantAction).toHaveBeenNthCalledWith(3, 'capability_formalization', expect.any(Object))
    expect(mocks.runDevAssistantAction).toHaveBeenNthCalledWith(4, 'capability_formalization', expect.any(Object))
  })

  it('saves accepted developer proposal sections as assistant review artifacts', async () => {
    mocks.applyAssistantProposal.mockResolvedValue({ id: 'pm-artifact-1' })

    await saveAcceptedDeveloperDesignSection({
      projectId: 'proj-1',
      section: section(),
      notes: 'locked baseline json',
    })

    expect(mocks.applyAssistantProposal).toHaveBeenCalledWith('proj-1', expect.objectContaining({
      artifact_id: 'pm-artifact-uuid-1',
      capability: 'propose_service_design',
      accepted_item_ids: ['propose_service_design-1'],
      rejected_item_ids: [],
      notes: 'locked baseline json',
    }))
  })

  it('redrafts one developer section with answered clarification context', async () => {
    mocks.runDevAssistantAction.mockResolvedValue(envelope('propose_runtime_policy_bindings'))

    const result = await redraftDeveloperDesignSection({
      projectId: 'proj-1',
      baselineText: 'locked baseline plus answers',
      sourceRequirementsId: 'req-1',
      sourceShapeId: 'shape-1',
      section: {
        id: 'runtime_policy_bindings',
        title: 'Runtime Policy Bindings',
        action: 'runtime_policy_bindings',
        envelope: envelope('propose_runtime_policy_bindings', { clarification: true }),
        selectedIds: ['q-1'],
        clarificationAnswers: { 'q-1': 'Stop before dispatch and require manager approval.' },
        status: 'needs_clarification',
      },
    })

    expect(mocks.runDevAssistantAction).toHaveBeenCalledWith('runtime_policy_bindings', {
      projectId: 'proj-1',
      sourceText: 'locked baseline plus answers',
      sourceRequirementsId: 'req-1',
      sourceShapeId: 'shape-1',
      serviceTopologyPreference: undefined,
    })
    expect(result.status).toBe('proposed')
    expect(result.selectedIds).toEqual(['propose_runtime_policy_bindings-1'])
    expect(result.clarificationAnswers).toEqual({ 'q-1': 'Stop before dispatch and require manager approval.' })
  })
})
