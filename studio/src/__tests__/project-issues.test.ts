import { describe, expect, it } from 'vitest'
import { buildProjectIssueIndex } from '../design/project-issues'
import { productDesignGate } from '../design/project-workflow'
import type { ArtifactRecord, ProjectDetail, ShapeRecord } from '../design/project-types'

function project(): ProjectDetail {
  return {
    id: 'project-1',
    workspace_id: 'workspace-1',
    name: 'Demo',
    summary: '',
    domain: 'demo',
    labels: [],
    project_type: 'standard',
    created_at: '2026-05-29T00:00:00.000Z',
    updated_at: '2026-05-29T00:00:00.000Z',
    requirements_count: 0,
    scenarios_count: 0,
    proposals_count: 0,
    evaluations_count: 0,
    shapes_count: 1,
  }
}

function artifact(id: string, data: Record<string, any>): ArtifactRecord {
  return {
    id,
    project_id: 'project-1',
    title: id,
    status: 'active',
    data,
    content_hash: `${id}-hash`,
    created_at: '2026-05-29T00:00:00.000Z',
    updated_at: '2026-05-29T00:00:00.000Z',
  }
}

function scenario(id: string, participatingServices: string[]): ArtifactRecord {
  return artifact(id, {
    scenario: {
      name: id,
      category: 'cross_service',
      narrative: 'A bounded execution scenario.',
      context: { quarter: '2026-Q2' },
      expected_behavior: ['Preserve declared service boundaries.'],
      expected_anip_support: ['Expose service ownership and coordination.'],
      participating_services: participatingServices,
    },
  })
}

const shape = artifact('shape-1', {
  shape: {
    id: 'shape-1',
    name: 'Multi-service shape',
    type: 'multi_service',
    services: [
      { id: 'pipeline', name: 'Pipeline Service', role: 'Pipeline summaries.' },
      { id: 'outreach', name: 'Outreach Service', role: 'Outreach drafts.' },
      { id: 'enrichment', name: 'Enrichment Service', role: 'Account enrichment.' },
    ],
    coordination: [
      { from: 'pipeline', to: 'outreach', relationship: 'handoff' },
      { from: 'pipeline', to: 'enrichment', relationship: 'verification' },
    ],
  },
}) as ShapeRecord

describe('project issue index', () => {
  it('blocks Product Design when multi-service scenarios do not cover all services and coordination edges', () => {
    const issues = buildProjectIssueIndex({
      project: project(),
      pmArtifacts: [],
      requirements: [],
      scenarios: [scenario('pipeline_review', ['pipeline'])],
      documents: [],
      shapes: [shape],
    })

    expect(issues['project-scenarios-list']?.severity).toBe('error')
    expect(issues['project-scenarios-list']?.messages).toContain(
      'Scenario pack does not cover service design service(s): Outreach Service, Enrichment Service.',
    )
    expect(issues['project-scenarios-list']?.messages).toContain(
      'Scenario pack does not cover service coordination edge(s): Pipeline Service -> Outreach Service (handoff), Pipeline Service -> Enrichment Service (verification).',
    )
    expect(issues['project-product-design']?.severity).toBe('error')
  })

  it('accepts Product Design service coverage when scenarios cover each service and coordination edge', () => {
    const issues = buildProjectIssueIndex({
      project: project(),
      pmArtifacts: [],
      requirements: [],
      scenarios: [
        scenario('pipeline_to_outreach', ['pipeline', 'outreach']),
        scenario('pipeline_to_enrichment', ['pipeline', 'enrichment']),
      ],
      documents: [],
      shapes: [shape],
    })

    expect(issues['project-scenarios-list']?.messages ?? []).not.toContain(
      'Scenario pack does not cover service design service(s): Outreach Service, Enrichment Service.',
    )
    expect(issues['project-scenarios-list']?.messages ?? []).not.toContain(
      'Scenario pack does not cover service coordination edge(s): Pipeline Service -> Outreach Service (handoff), Pipeline Service -> Enrichment Service (verification).',
    )
  })

  it('blocks Developer Design entry on any unresolved fronting Product Design issue', () => {
    const frontingProject = {
      ...project(),
      project_type: 'governed_service_project',
    } as ProjectDetail

    const gate = productDesignGate({
      project: frontingProject,
      pmArtifacts: [],
      requirements: [],
      scenarios: [],
      documents: [],
      shapes: [],
    })

    expect(gate.ready).toBe(false)
    expect(gate.count).toBeGreaterThan(0)
    expect(gate.issue?.severity).toBe('warning')
  })

  it('accepts fronting mappings when one backend alternative is complete', () => {
    const frontingProject = {
      ...project(),
      project_type: 'governed_service_project',
    } as ProjectDetail
    const baseline = artifact('baseline-1', {
      artifact_type: 'developer_baseline',
      locked_at: '2026-05-29T00:00:00.000Z',
      source_inputs: {},
    })
    const mapping = artifact('jira.prepare', {
      artifact_type: 'integration_fronting_capability_mapping',
      capability_id: 'jira.prepare_comment',
      backend_bindings: [
        {
          backend_kind: 'native_api',
          connection_ref: 'jira-api',
          raw_operation_refs: ['POST /rest/api/3/issue/{issueIdOrKey}/comment'],
          status: 'ready',
        },
        {
          backend_kind: 'mcp',
          connection_ref: 'atlassian-mcp',
          raw_operation_refs: [],
          status: 'missing',
        },
      ],
    })

    const issues = buildProjectIssueIndex({
      project: frontingProject,
      pmArtifacts: [baseline, mapping],
      requirements: [],
      scenarios: [],
      documents: [],
      shapes: [],
    })

    expect(issues['project-integration-fronting']?.messages ?? []).not.toContain(
      'jira.prepare has incomplete backend bindings.',
    )
  })

  it('does not reintroduce coverage warnings for reviewed automatic coverage resolutions', () => {
    const frontingProject = {
      ...project(),
      project_type: 'governed_service_project',
    } as ProjectDetail
    const lockedAt = '2026-05-29T00:00:00.000Z'
    const baseline = artifact('baseline-1', {
      artifact_type: 'developer_baseline',
      locked_at: lockedAt,
      source_inputs: {
        requirements_id: null,
        primary_scenario_id: null,
        scenario_ids: [],
        scenario_set_hash: null,
        shape_id: null,
      },
    })
    const traceability = artifact('traceability-1', {
      artifact_type: 'design_traceability',
      source_inputs: {
        requirements_id: null,
        scenario_id: null,
        scenario_ids: [],
        scenario_set_hash: null,
        shape_id: null,
        baseline_locked_at: lockedAt,
      },
      developer_status: 'ready_for_pm_review',
      coverage: [
        {
          id: 'shape:coordination:jira.fronting:jira.governance:handoff',
          source: 'shape',
          section: 'Coordination',
          label: 'Jira.Fronting -> Jira.Governance',
          detail: 'Preparation flows may hand off to governance-managed approval paths.',
          status: 'addressed',
          rationale: 'Reviewed as contract-owned capability behavior.',
          linked_surfaces: ['audit_and_lineage'],
          mapping_mode: 'automatic',
          mapping_target_key: 'developer_definition.integration_fronting:jira.workflow_transition.request',
          mapping_target_label: 'Developer Design > Govern API / MCP > Accepted Governed Mapping',
          operator_resolution: {
            choice_id: 'contract_owned',
            label: 'Service owns the behavior',
            applied_at: '2026-05-29T00:01:00.000Z',
          },
        },
      ],
    })

    const issues = buildProjectIssueIndex({
      project: frontingProject,
      pmArtifacts: [baseline, traceability],
      requirements: [],
      scenarios: [],
      documents: [],
      shapes: [],
    })

    expect(issues['project-developer-coverage']?.messages ?? []).not.toContain(
      '1 Product Design item are only partially addressed.',
    )
    expect(issues['project-developer-coverage']?.messages ?? []).not.toContain(
      '1 Product Design item is still not addressed.',
    )
  })
})
