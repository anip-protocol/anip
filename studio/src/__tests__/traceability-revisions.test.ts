import { describe, expect, it } from 'vitest'
import { buildTraceabilityRecord } from '../design/traceability'
import type { ShapeRecord } from '../design/project-types'

describe('traceability revision metadata', () => {
  it('preserves saved PM review revision metadata when rebuilding the draft record', () => {
    const record = buildTraceabilityRecord({
      pmArtifacts: [],
      requirements: null,
      scenarios: [],
      primaryScenarioId: null,
      shape: null,
      existing: {
        artifact_type: 'design_traceability',
        source_inputs: {
          requirements_id: null,
          scenario_id: null,
          scenario_ids: [],
          shape_id: null,
        },
        developer_status: 'ready_for_pm_review',
        developer_note: '',
        developer_marked_at: null,
        pm_review_status: 'approved',
        pm_review_note: '',
        pm_reviewed_at: '2026-04-24T12:00:00Z',
        pm_review_contract_signature: 'contract-sig',
        pm_review_generation_signature: 'generation-sig',
        pm_review_generation_artifact_id: 'generation-run-1',
        pm_review_definition_revision_artifact_id: 'developer-revision-4',
        pm_review_definition_revision_number: 4,
        pm_review_product_revision_artifact_id: 'product-revision-2',
        pm_review_product_revision_number: 2,
        pm_review_evaluation_signature: 'evaluation-sig',
        pm_review_evaluation_id: 'evaluation-1',
        pm_review_observed_service_signature: 'observed-sig',
        pm_review_observed_service_artifact_id: 'observed-1',
        coverage: [],
      },
    })

    expect(record.pm_review_definition_revision_artifact_id).toBe('developer-revision-4')
    expect(record.pm_review_definition_revision_number).toBe(4)
    expect(record.pm_review_product_revision_artifact_id).toBe('product-revision-2')
    expect(record.pm_review_product_revision_number).toBe(2)
  })

  it('preserves saved agent consumption readiness when rebuilding the draft record', () => {
    const record = buildTraceabilityRecord({
      pmArtifacts: [],
      requirements: null,
      scenarios: [],
      primaryScenarioId: null,
      shape: null,
      existing: {
        artifact_type: 'design_traceability',
        source_inputs: {
          requirements_id: null,
          scenario_id: null,
          scenario_ids: [],
          shape_id: null,
        },
        developer_status: 'in_progress',
        developer_note: '',
        developer_marked_at: null,
        pm_review_status: 'pending',
        pm_review_note: '',
        pm_reviewed_at: null,
        pm_review_contract_signature: null,
        pm_review_generation_signature: null,
        pm_review_generation_artifact_id: null,
        pm_review_evaluation_signature: null,
        pm_review_evaluation_id: null,
        pm_review_observed_service_signature: null,
        pm_review_observed_service_artifact_id: null,
        coverage: [],
        agent_consumption_readiness: {
          artifact_type: 'agent_consumption_readiness',
          status: 'needs_review',
          score: 82,
          summary: {
            blockers: 0,
            warnings: 2,
            info: 1,
            probes: 4,
            required_app_glue: 1,
          },
          findings: [],
          probes: [],
          required_app_glue: [],
        },
      },
    })

    expect(record.agent_consumption_readiness?.status).toBe('needs_review')
    expect(record.agent_consumption_readiness?.summary.warnings).toBe(2)
  })

  it('preserves reviewed automatic coordination decisions when rebuilding coverage', () => {
    const shape: ShapeRecord = {
      id: 'shape-1',
      project_id: 'project-1',
      title: 'Service Shape',
      status: 'accepted',
      requirements_id: 'requirements-1',
      content_hash: 'shape-hash',
      created_at: '2026-06-01T00:00:00Z',
      updated_at: '2026-06-01T00:00:00Z',
      data: {
        shape: {
          services: [
            { id: 'fronting', name: 'Fronting', capabilities: ['fronting.read'] },
            { id: 'governance', name: 'Governance', capabilities: ['governance.request'] },
          ],
          coordination: [
            {
              from: 'fronting',
              to: 'governance',
              relationship: 'handoff',
              description: 'Fronting hands off approval-governed requests to governance.',
            },
          ],
        },
      },
    }

    const record = buildTraceabilityRecord({
      pmArtifacts: [],
      requirements: null,
      scenarios: [],
      primaryScenarioId: null,
      shape,
      existing: {
        artifact_type: 'design_traceability',
        source_inputs: {
          requirements_id: null,
          scenario_id: null,
          scenario_ids: [],
          shape_id: shape.id,
        },
        developer_status: 'in_progress',
        developer_note: '',
        developer_marked_at: null,
        pm_review_status: 'pending',
        pm_review_note: '',
        pm_reviewed_at: null,
        pm_review_contract_signature: null,
        pm_review_generation_signature: null,
        pm_review_generation_artifact_id: null,
        pm_review_evaluation_signature: null,
        pm_review_evaluation_id: null,
        pm_review_observed_service_signature: null,
        pm_review_observed_service_artifact_id: null,
        coverage: [{
          id: 'shape:coordination:fronting:governance:handoff',
          source: 'shape',
          section: 'Coordination',
          label: 'Fronting -> Governance',
          detail: 'Fronting hands off approval-governed requests to governance.',
          status: 'addressed',
          rationale: 'Reviewed as contract-owned coordination.',
          linked_surfaces: ['capability_contracts'],
          mapping_mode: 'automatic',
          operator_resolution: {
            choice_id: 'contract_owned',
            applied_at: '2026-06-01T00:01:00Z',
            target_artifact: 'Developer Coverage / Capability Formalization',
            summary: 'Coverage decision plus composed-capability review handoff',
            requires_review: true,
            changes: ['Mark coordination addressed.'],
          },
        }],
      },
    })

    expect(record.coverage).toEqual(expect.arrayContaining([
      expect.objectContaining({
        id: 'shape:coordination:fronting:governance:handoff',
        status: 'addressed',
        rationale: 'Reviewed as contract-owned coordination.',
        operator_resolution: expect.objectContaining({ choice_id: 'contract_owned' }),
      }),
    ]))
  })
})
