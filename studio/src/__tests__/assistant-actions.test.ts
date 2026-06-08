import { describe, expect, it, beforeEach, vi } from 'vitest'
import {
  devActionForSection,
  isDeveloperSectionNavigationOnly,
  pmActionForSection,
  runDevAssistantAction,
  runPmAssistantAction,
} from '../design/assistant-actions'
import type {
  AssistantProposalEnvelope,
} from '../design/project-types'

const api = vi.hoisted(() => ({
  proposeActorModelWithAssistant: vi.fn(),
  proposeBackendBindingsWithAssistant: vi.fn(),
  proposeBusinessAreasWithAssistant: vi.fn(),
  proposeBusinessSummaryWithAssistant: vi.fn(),
  proposeCapabilityFormalizationWithAssistant: vi.fn(),
  identifyMissingBusinessInfoWithAssistant: vi.fn(),
  proposeInputContractsWithAssistant: vi.fn(),
  proposeNonGoalsWithAssistant: vi.fn(),
  proposePermissionIntentWithAssistant: vi.fn(),
  proposeRequirementsWithAssistant: vi.fn(),
  proposeRuntimePolicyBindingsWithAssistant: vi.fn(),
  proposeScenariosWithAssistant: vi.fn(),
  proposeServiceDesignWithAssistant: vi.fn(),
  proposeSuccessCriteriaWithAssistant: vi.fn(),
  proposeVerificationExpectationsWithAssistant: vi.fn(),
}))

vi.mock('../design/project-api', () => api)

function makeEnvelope(capability: string): AssistantProposalEnvelope {
  return {
    title: `Envelope for ${capability}`,
    summary: 'Test envelope.',
    mode: capability.startsWith('propose_') || capability === 'identify_missing_business_info' ? 'pm' : 'dev',
    capability,
    questions_for_user: [],
    watchouts: [],
    next_steps: [],
    proposal: {
      proposal_kind: 'candidate_blocks',
      artifact_type: 'assistant_requirement_candidates',
      items: [
        {
          client_id: `${capability}-1`,
          title: capability,
          body: 'Body',
          confidence: 'high',
          rationale: 'Rationale',
        },
      ],
    },
  }
}

describe('assistant-actions', () => {
  beforeEach(() => {
    Object.values(api).forEach((mock) => mock.mockReset())
  })

  it('maps PM and Dev sections onto the correct assistant actions', () => {
    expect(pmActionForSection('product_summary')).toBe('business_summary')
    expect(pmActionForSection('actor_model')).toBe('actor_model')
    expect(pmActionForSection('unknown_pm_section')).toBe('missing_info')

    expect(devActionForSection('service_identity_topology')).toBe('service_design')
    expect(devActionForSection('capability_contracts')).toBe('capability_formalization')
    expect(devActionForSection('authority_and_approval')).toBe('runtime_policy_bindings')
    expect(devActionForSection('backend_bindings')).toBe('backend_bindings')
    expect(devActionForSection('audit_and_lineage')).toBe('verification_expectations')
    expect(devActionForSection('unknown_dev_section')).toBe('service_design')
  })

  it('identifies navigation-only developer definition sections', () => {
    expect(isDeveloperSectionNavigationOnly('data_contracts')).toBe(true)
    expect(isDeveloperSectionNavigationOnly('scenario_context')).toBe(true)
    expect(isDeveloperSectionNavigationOnly('execution_semantics')).toBe(true)
    expect(isDeveloperSectionNavigationOnly('generation_and_extensions')).toBe(true)
    expect(isDeveloperSectionNavigationOnly('backend_bindings')).toBe(false)
  })

  it('dispatches PM assistant actions through the correct API helpers', async () => {
    const requirementsEnvelope = makeEnvelope('propose_requirements')
    const missingInfoEnvelope = makeEnvelope('identify_missing_business_info')
    api.proposeRequirementsWithAssistant.mockResolvedValue(requirementsEnvelope)
    api.identifyMissingBusinessInfoWithAssistant.mockResolvedValue(missingInfoEnvelope)

    await expect(runPmAssistantAction('requirements', {
      projectId: 'proj-1',
      sourceText: 'Source brief',
      sourceRequirementsId: 'req-1',
    })).resolves.toBe(requirementsEnvelope)
    expect(api.proposeRequirementsWithAssistant).toHaveBeenCalledWith('proj-1', 'Source brief', 'req-1', false, {
      signal: undefined,
    })

    await expect(runPmAssistantAction('missing_info', {
      projectId: 'proj-1',
      sourceText: 'Source brief',
      sourceRequirementsId: 'req-1',
    })).resolves.toBe(missingInfoEnvelope)
    expect(api.identifyMissingBusinessInfoWithAssistant).toHaveBeenCalledWith('proj-1', 'Source brief', 'req-1', false, {
      signal: undefined,
    })
  })

  it('dispatches Dev assistant actions through the correct API helpers', async () => {
    const serviceDesignEnvelope = makeEnvelope('propose_service_design')
    const backendBindingsEnvelope = makeEnvelope('propose_backend_bindings')
    api.proposeServiceDesignWithAssistant.mockResolvedValue(serviceDesignEnvelope)
    api.proposeBackendBindingsWithAssistant.mockResolvedValue(backendBindingsEnvelope)

    await expect(runDevAssistantAction('service_design', {
      projectId: 'proj-1',
      sourceText: 'Locked PM baseline',
      sourceRequirementsId: 'req-1',
      sourceShapeId: 'shape-1',
    })).resolves.toBe(serviceDesignEnvelope)
    expect(api.proposeServiceDesignWithAssistant).toHaveBeenCalledWith(
      'proj-1',
      'Locked PM baseline',
      'req-1',
      'shape-1',
      false,
      null,
      { signal: undefined },
    )

    await expect(runDevAssistantAction('backend_bindings', {
      projectId: 'proj-1',
      sourceText: 'Locked PM baseline',
      sourceRequirementsId: 'req-1',
      sourceShapeId: 'shape-1',
    })).resolves.toBe(backendBindingsEnvelope)
    expect(api.proposeBackendBindingsWithAssistant).toHaveBeenCalledWith(
      'proj-1',
      'Locked PM baseline',
      'req-1',
      'shape-1',
      false,
      { signal: undefined },
    )
  })

  it('extracts developer input contracts from structured source evidence without calling the assistant', async () => {
    const sourceText = [
      '# Locked Product Design Baseline',
      JSON.stringify({ source: 'locked_product_design_baseline', requirements: {} }),
      '',
      '# Source Evidence Available To Developer Design',
      '# Source 1: Runtime interface',
      'Kind: Developer interface',
      '',
      JSON.stringify({
        artifact_type: 'anip_service_definition',
        capability_formalizations: [
          {
            capability_id: 'gtm.pipeline_summary',
            inputs: [
              {
                input_name: 'quarter',
                input_type: 'string',
                required: true,
                semantic_type: 'time_scope',
                summary: 'Quarter label like 2017-Q2',
              },
            ],
          },
        ],
      }),
    ].join('\n')

    const result = await runDevAssistantAction('input_contracts', {
      projectId: 'proj-1',
      sourceText,
      sourceRequirementsId: 'req-1',
      sourceShapeId: 'shape-1',
    })

    expect(api.proposeInputContractsWithAssistant).not.toHaveBeenCalled()
    expect(result.proposal.proposal_kind).toBe('candidate_blocks')
    if (result.proposal.proposal_kind !== 'candidate_blocks') throw new Error('expected candidate blocks')
    expect(result.proposal.items).toEqual([
      expect.objectContaining({
        title: 'Reviewed input contract for gtm.pipeline_summary',
        structured_data: {
          capabilities: [
            expect.objectContaining({
              capability_id: 'gtm.pipeline_summary',
              inputs: [
                expect.objectContaining({
                  input_name: 'quarter',
                  input_type: 'string',
                  required: true,
                }),
              ],
            }),
          ],
        },
      }),
    ])
  })

  it('extracts full developer capability formalizations from structured source evidence without calling the assistant', async () => {
    const sourceText = [
      '# Locked Product Design Baseline',
      JSON.stringify({ source: 'locked_product_design_baseline', requirements: {} }),
      '',
      '# Source Evidence Available To Developer Design',
      '# Source 1: Runtime interface',
      'Kind: Developer interface',
      '',
      JSON.stringify({
        artifact_type: 'anip_service_definition',
        capability_formalizations: [
          {
            id: 'composition:gtm.at_risk_followup_preparation',
            kind: 'composed',
            service_id: 'gtm-pipeline-service',
            capability_id: 'gtm.at_risk_followup_preparation',
            title: 'At Risk Followup Preparation',
            summary: 'Compose risk review into follow-up preparation.',
            source_kind: 'application_integration',
            intent_type: 'business_action',
            operation_type: 'approval_gated',
            side_effect_level: 'approval_required',
            backend_operation: 'gtm.at_risk_followup_preparation',
            path_template: '/gtm/at-risk-followup-preparation',
            output_shape: 'gtm_at_risk_followup_preparation_result',
            composition: {
              authority_boundary: 'same_service',
              steps: [
                { id: 'account_risk_summary', capability: 'gtm.account_risk_summary' },
                { id: 'prepare_followup_tasks', capability: 'gtm.prepare_followup_tasks' },
              ],
            },
            inputs: [
              {
                input_name: 'quarter',
                input_type: 'string',
                required: true,
                semantic_type: 'time_scope',
                summary: 'Quarter label like 2017-Q2',
              },
            ],
          },
        ],
      }),
      '',
      '# Draft Developer Input Contract Evidence',
      '```json',
      JSON.stringify({ canonical_capability_inventory: [{ capability_id: 'gtm.pipeline_summary', inputs: [] }] }),
      '```',
    ].join('\n')

    const result = await runDevAssistantAction('capability_formalization', {
      projectId: 'proj-1',
      sourceText,
      sourceRequirementsId: 'req-1',
      sourceShapeId: 'shape-1',
    })

    expect(api.proposeCapabilityFormalizationWithAssistant).not.toHaveBeenCalled()
    expect(result.proposal.proposal_kind).toBe('candidate_blocks')
    if (result.proposal.proposal_kind !== 'candidate_blocks') throw new Error('expected candidate blocks')
    expect(result.proposal.items).toEqual([
      expect.objectContaining({
        title: 'Canonical capability formalizations',
        structured_data: {
          capabilities: [
            expect.objectContaining({
              capability_id: 'gtm.at_risk_followup_preparation',
              service_id: 'gtm-pipeline-service',
              kind: 'composed',
              composition: expect.objectContaining({
                authority_boundary: 'same_service',
              }),
            }),
          ],
        },
      }),
    ])
  })
})
