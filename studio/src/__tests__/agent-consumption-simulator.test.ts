import { describe, expect, it } from 'vitest'
import {
  buildAgentConsumptionSimulationRequest,
  scoreAgentConsumptionSimulation,
  summarizeAgentConsumptionSimulationPublicationGate,
} from '../design/agent-consumption-simulator'
import type { AgentConsumptionReadinessReport } from '../design/agent-consumption-readiness'
import type { AgentConsumabilityMetadata } from '../design/agent-consumability'

function readiness(): AgentConsumptionReadinessReport {
  return {
    artifact_type: 'agent_consumption_readiness',
    status: 'needs_review',
    score: 80,
    summary: {
      blockers: 0,
      warnings: 1,
      info: 0,
      probes: 2,
      required_app_glue: 1,
    },
    findings: [],
    required_app_glue: [],
    probes: [
      {
        id: 'missing-context',
        label: 'Missing context',
        prompt: 'Ask for enrichment without account names.',
        expected_outcome: 'clarification_required',
        target_capability_id: 'gtm.account_enrichment_summary',
        rationale: 'The app should not guess account names.',
      },
      {
        id: 'unsupported-send',
        label: 'Unsupported send',
        prompt: 'Ask the package to send the outreach now.',
        expected_outcome: 'unsupported',
        target_capability_id: 'gtm.draft_outreach_message',
        rationale: 'Drafting does not dispatch externally.',
      },
    ],
  }
}

function consumability(): AgentConsumabilityMetadata {
  return {
    artifact_type: 'agent_consumability_metadata',
    schema_version: 'anip-agent-consumability/v0',
    capabilities: {
      'gtm.account_enrichment_summary': {
        intent: {
          category: 'account.enrichment.summary',
          summary: 'Summarize enrichment for explicit account cohorts.',
        },
        required_context: [
          {
            input: 'account_names',
            missing_behavior: 'clarify_or_app_select',
          },
        ],
        app_glue: {
          required: true,
          reason: 'The app selects or asks for the account cohort.',
        },
      },
    },
  }
}

describe('agent consumption simulator', () => {
  it('builds a compact simulator payload from readiness and consumability metadata', () => {
    const payload = buildAgentConsumptionSimulationRequest({
      project: { id: 'gtm', name: 'GTM', domain: 'Revenue' },
      definition: {
        capability_formalizations: [
          {
            id: 'cap-enrichment',
            capability_id: 'gtm.account_enrichment_summary',
            title: 'Account Enrichment Summary',
            summary: 'Summarize enrichment.',
            intent_type: 'summarize',
            operation_type: 'read',
            side_effect_level: 'read',
            output_shape: 'account_enrichment_summary',
            inputs: [],
          },
        ],
        scenario_formalizations: [],
        verification: null,
      } as any,
      readiness: readiness(),
      agentConsumability: consumability(),
      maxProbes: 1,
    })

    expect(payload.project?.id).toBe('gtm')
    expect(payload.probes).toHaveLength(1)
    expect((payload.developer_definition as any).capability_formalizations[0].capability_id).toBe('gtm.account_enrichment_summary')
    expect(payload.agent_consumability.capabilities['gtm.account_enrichment_summary'].app_glue?.required).toBe(true)
  })

  it('keeps the embedded readiness probes aligned with the submitted simulator probe set', () => {
    const sourceReadiness = {
      ...readiness(),
      probes: [
        ...readiness().probes,
        {
          id: 'extra-probe',
          label: 'Extra probe',
          prompt: 'Ask for an extra unsupported action.',
          expected_outcome: 'unsupported' as const,
          target_capability_id: 'gtm.draft_outreach_message',
          rationale: 'Should not leak into a capped simulator request.',
        },
      ],
      summary: {
        ...readiness().summary,
        probes: 3,
      },
    }

    const payload = buildAgentConsumptionSimulationRequest({
      project: { id: 'gtm', name: 'GTM', domain: 'Revenue' },
      definition: null,
      readiness: sourceReadiness,
      agentConsumability: consumability(),
      maxProbes: 2,
    })

    expect(payload.probes.map((probe) => probe.id)).toEqual(['missing-context', 'unsupported-send'])
    expect(payload.readiness.probes.map((probe) => probe.id)).toEqual(['missing-context', 'unsupported-send'])
    expect(payload.readiness.summary.probes).toBe(2)
  })

  it('scores simulator output deterministically against expected probe behavior', () => {
    const report = scoreAgentConsumptionSimulation({
      readiness: readiness(),
      modelOutput: {
        artifact_type: 'agent_consumption_simulation_model_output',
        schema_version: 'anip-agent-consumption-simulator/v0',
        simulator_runtime: {
          provider: 'openai',
          model: 'gpt-5.4-mini',
        },
        cases: [
          {
            probe_id: 'missing-context',
            selected_capability_id: 'gtm.account_enrichment_summary',
            actual_outcome: 'clarification_required',
            parameter_plan: {},
            used_consumability_hints: ['required_context'],
            rationale: 'Required context is missing.',
            confidence: 0.9,
          },
          {
            probe_id: 'unsupported-send',
            selected_capability_id: 'gtm.draft_outreach_message',
            actual_outcome: 'success',
            parameter_plan: {},
            used_consumability_hints: [],
            rationale: 'Wrongly treated send as draft.',
            confidence: 0.4,
          },
        ],
      },
    })

    expect(report.status).toBe('fail')
    expect(report.summary).toEqual({ total: 2, passed: 1, failed: 1 })
    expect(report.cases[1].failures[0]).toContain('Expected outcome unsupported')
  })

  it('fails approval and clarification probes when the model selects a different capability', () => {
    const baseReadiness = readiness()
    const report = scoreAgentConsumptionSimulation({
      readiness: {
        ...baseReadiness,
        probes: [
          {
            id: 'approval-boundary',
            label: 'Approval boundary',
            prompt: 'Ask for a forecast and prepare follow-up task previews.',
            expected_outcome: 'approval_required',
            target_capability_id: 'gtm.prepare_followup_tasks',
            rationale: 'The governed preview capability must own approval-preview intent.',
          },
        ],
      },
      modelOutput: {
        artifact_type: 'agent_consumption_simulation_model_output',
        schema_version: 'anip-agent-consumption-simulator/v0',
        simulator_runtime: {
          provider: 'openai',
          model: 'gpt-5.4-mini',
        },
        cases: [
          {
            probe_id: 'approval-boundary',
            selected_capability_id: 'gtm.pipeline_forecast_summary',
            actual_outcome: 'approval_required',
            parameter_plan: {},
            used_consumability_hints: ['business_effects'],
            rationale: 'Wrong capability even though outcome matched.',
            confidence: 0.6,
          },
        ],
      },
    })

    expect(report.status).toBe('fail')
    expect(report.cases[0].failures[0]).toContain('Expected capability gtm.prepare_followup_tasks')
  })

  it('summarizes publication gate state from the latest simulator report', () => {
    expect(summarizeAgentConsumptionSimulationPublicationGate({
      report: null,
      overrideAccepted: false,
    })).toMatchObject({
      status: 'missing',
      blocksPublication: true,
      requiresOverride: true,
    })

    const failedReport = scoreAgentConsumptionSimulation({
      readiness: readiness(),
      modelOutput: {
        artifact_type: 'agent_consumption_simulation_model_output',
        schema_version: 'anip-agent-consumption-simulator/v0',
        simulator_runtime: {
          provider: 'openai',
          model: 'gpt-5.4-mini',
        },
        cases: [
          {
            probe_id: 'missing-context',
            selected_capability_id: 'gtm.account_enrichment_summary',
            actual_outcome: 'success',
            parameter_plan: {},
            used_consumability_hints: [],
            rationale: 'Wrongly guessed missing context.',
            confidence: 0.4,
          },
          {
            probe_id: 'unsupported-send',
            selected_capability_id: 'gtm.draft_outreach_message',
            actual_outcome: 'unsupported',
            parameter_plan: {},
            used_consumability_hints: ['business_effects'],
            rationale: 'Dispatch is unsupported.',
            confidence: 0.9,
          },
        ],
      },
    })

    expect(summarizeAgentConsumptionSimulationPublicationGate({
      report: failedReport,
      overrideAccepted: false,
    })).toMatchObject({
      status: 'failed',
      blocksPublication: true,
    })
    expect(summarizeAgentConsumptionSimulationPublicationGate({
      report: failedReport,
      overrideAccepted: true,
    })).toMatchObject({
      status: 'overridden',
      blocksPublication: false,
    })
  })
})
