import type { AgentConsumabilityMetadata } from './agent-consumability'
import type {
  AgentConsumptionReadinessProbe,
  AgentConsumptionReadinessReport,
} from './agent-consumption-readiness'
import type { DeveloperDefinitionData } from './project-types'

export type AgentConsumptionSimulationOutcome =
  | 'success'
  | 'clarification_required'
  | 'denied'
  | 'approval_required'
  | 'unsupported'

export interface AgentConsumptionSimulationRequest {
  project?: {
    id: string
    name: string
    domain?: string
  } | null
  developer_definition: DeveloperDefinitionData | Record<string, unknown>
  readiness: AgentConsumptionReadinessReport
  agent_consumability: AgentConsumabilityMetadata
  probes: AgentConsumptionReadinessProbe[]
}

export interface AgentConsumptionSimulationModelCase {
  probe_id: string
  selected_capability_id: string | null
  actual_outcome: AgentConsumptionSimulationOutcome
  parameter_plan: Record<string, unknown>
  used_consumability_hints: string[]
  rationale: string
  confidence: number
}

export interface AgentConsumptionSimulationModelOutput {
  artifact_type: 'agent_consumption_simulation_model_output'
  schema_version: 'anip-agent-consumption-simulator/v0'
  simulator_runtime: {
    provider: string
    model?: string | null
    provider_source?: string
    model_source?: string
  }
  cases: AgentConsumptionSimulationModelCase[]
  summary?: Record<string, unknown>
}

export interface AgentConsumptionSimulationScoredCase extends AgentConsumptionSimulationModelCase {
  expected_outcome: AgentConsumptionSimulationOutcome
  expected_capability_id: string | null
  status: 'pass' | 'fail'
  failures: string[]
}

export interface AgentConsumptionSimulationReport {
  artifact_type: 'agent_consumption_simulation_report'
  schema_version: 'anip-agent-consumption-simulator/v0'
  generated_at: string
  status: 'pass' | 'fail'
  summary: {
    total: number
    passed: number
    failed: number
  }
  simulator_runtime: AgentConsumptionSimulationModelOutput['simulator_runtime']
  cases: AgentConsumptionSimulationScoredCase[]
  raw_model_summary?: Record<string, unknown>
}

export type AgentConsumptionSimulationPublicationGateStatus =
  | 'pass'
  | 'missing'
  | 'failed'
  | 'overridden'

export interface AgentConsumptionSimulationPublicationGate {
  status: AgentConsumptionSimulationPublicationGateStatus
  label: string
  detail: string
  blocksPublication: boolean
  requiresOverride: boolean
}

export function buildAgentConsumptionSimulationRequest(params: {
  project?: { id: string; name: string; domain?: string } | null
  definition: DeveloperDefinitionData | null | undefined
  readiness: AgentConsumptionReadinessReport
  agentConsumability: AgentConsumabilityMetadata
  maxProbes?: number
}): AgentConsumptionSimulationRequest {
  const probes = params.readiness.probes.slice(0, params.maxProbes ?? 12)
  return {
    project: params.project ?? null,
    developer_definition: compactDefinitionForSimulation(params.definition),
    readiness: {
      ...params.readiness,
      summary: {
        ...params.readiness.summary,
        probes: probes.length,
      },
      probes,
    },
    agent_consumability: params.agentConsumability,
    probes,
  }
}

export function scoreAgentConsumptionSimulation(params: {
  modelOutput: AgentConsumptionSimulationModelOutput
  readiness: AgentConsumptionReadinessReport
  probes?: AgentConsumptionReadinessProbe[]
}): AgentConsumptionSimulationReport {
  const expectedProbes = params.probes ?? params.readiness.probes
  const probesById = new Map(expectedProbes.map((probe) => [probe.id, probe]))
  const cases = params.modelOutput.cases.map((modelCase) => {
    const probe = probesById.get(modelCase.probe_id)
    const failures: string[] = []
    const expectedOutcome = normalizeOutcome(probe?.expected_outcome)
    const actualOutcome = normalizeOutcome(modelCase.actual_outcome)
    const expectedCapabilityId = probe?.target_capability_id ?? null
    if (!probe) {
      failures.push('Model returned a case for an unknown probe.')
    } else {
      if (actualOutcome !== expectedOutcome) {
        failures.push(`Expected outcome ${expectedOutcome}, got ${actualOutcome}.`)
      }
      if (
        expectedCapabilityId
        && actualOutcome !== 'unsupported'
        && modelCase.selected_capability_id !== expectedCapabilityId
      ) {
        failures.push(`Expected capability ${expectedCapabilityId}, got ${modelCase.selected_capability_id || 'none'}.`)
      }
    }
    return {
      ...modelCase,
      actual_outcome: actualOutcome,
      expected_outcome: expectedOutcome,
      expected_capability_id: expectedCapabilityId,
      status: failures.length === 0 ? 'pass' as const : 'fail' as const,
      failures,
    }
  })

  const returnedProbeIds = new Set(params.modelOutput.cases.map((item) => item.probe_id))
  for (const probe of expectedProbes) {
    if (returnedProbeIds.has(probe.id)) continue
    cases.push({
      probe_id: probe.id,
      selected_capability_id: null,
      actual_outcome: 'unsupported',
      parameter_plan: {},
      used_consumability_hints: [],
      rationale: 'Simulator model did not return a case for this probe.',
      confidence: 0,
      expected_outcome: normalizeOutcome(probe.expected_outcome),
      expected_capability_id: probe.target_capability_id ?? null,
      status: 'fail',
      failures: ['Missing simulator case.'],
    })
  }

  const passed = cases.filter((item) => item.status === 'pass').length
  const failed = cases.length - passed
  return {
    artifact_type: 'agent_consumption_simulation_report',
    schema_version: 'anip-agent-consumption-simulator/v0',
    generated_at: new Date().toISOString(),
    status: failed === 0 ? 'pass' : 'fail',
    summary: {
      total: cases.length,
      passed,
      failed,
    },
    simulator_runtime: params.modelOutput.simulator_runtime,
    cases,
    raw_model_summary: params.modelOutput.summary,
  }
}

export function summarizeAgentConsumptionSimulationPublicationGate(params: {
  report: AgentConsumptionSimulationReport | null | undefined
  overrideAccepted: boolean
}): AgentConsumptionSimulationPublicationGate {
  if (!params.report) {
    return params.overrideAccepted
      ? {
          status: 'overridden',
          label: 'No simulator report, overridden',
          detail: 'No saved agent-consumption simulation report exists. PM/dev accepted the publication risk explicitly.',
          blocksPublication: false,
          requiresOverride: true,
        }
      : {
          status: 'missing',
          label: 'Simulator report missing',
          detail: 'Run the AI Simulator from Agent & App Glue before publishing, or explicitly accept the risk.',
          blocksPublication: true,
          requiresOverride: true,
        }
  }
  if (params.report.status === 'fail') {
    const failed = params.report.summary.failed
    return params.overrideAccepted
      ? {
          status: 'overridden',
          label: 'Simulation failed, overridden',
          detail: `${failed} simulator probe${failed === 1 ? '' : 's'} failed. PM/dev accepted the publication risk explicitly.`,
          blocksPublication: false,
          requiresOverride: true,
        }
      : {
          status: 'failed',
          label: 'Simulation failed',
          detail: `${failed} simulator probe${failed === 1 ? '' : 's'} failed. Review the report or explicitly accept the risk before publishing.`,
          blocksPublication: true,
          requiresOverride: true,
        }
  }
  return {
    status: 'pass',
    label: 'Simulation passed',
    detail: `Latest simulator report passed ${params.report.summary.passed}/${params.report.summary.total} probes.`,
    blocksPublication: false,
    requiresOverride: false,
  }
}

function compactDefinitionForSimulation(
  definition: DeveloperDefinitionData | null | undefined,
): Record<string, unknown> {
  return {
    capability_formalizations: (definition?.capability_formalizations ?? []).map((capability) => ({
      capability_id: capability.capability_id,
      title: capability.title,
      summary: capability.summary,
      intent_type: capability.intent_type,
      operation_type: capability.operation_type,
      side_effect_level: capability.side_effect_level,
      output_shape: capability.output_shape,
      business_effects: capability.business_effects,
      grant_policy: capability.grant_policy,
      implementation_fit: capability.implementation_fit,
      composition: capability.composition,
      inputs: capability.inputs,
    })),
    scenario_formalizations: (definition?.scenario_formalizations ?? []).map((scenario) => ({
      scenario_id: scenario.scenario_id,
      scenario_title: scenario.scenario_title,
      business_scope: scenario.business_scope,
      required_behaviors: scenario.required_behaviors,
      orchestration_steps: scenario.orchestration_steps,
    })),
    verification: definition?.verification ?? null,
  }
}

function normalizeOutcome(value: unknown): AgentConsumptionSimulationOutcome {
  if (
    value === 'success'
    || value === 'clarification_required'
    || value === 'denied'
    || value === 'approval_required'
    || value === 'unsupported'
  ) {
    return value
  }
  return 'unsupported'
}
