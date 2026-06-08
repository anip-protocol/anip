import { describe, expect, it } from 'vitest'
import {
  buildDeveloperDefinitionData,
  buildDeveloperDefinitionContract,
  findDeveloperDefinitionRevisionArtifacts,
  findLatestDeveloperDefinitionRevisionArtifact,
} from '../design/developer-definition'
import type { ArtifactRecord, DeveloperDefinitionData, ProjectDetail } from '../design/project-types'

function artifact(overrides: Partial<ArtifactRecord>): ArtifactRecord {
  return {
    id: 'artifact-1',
    project_id: 'project-1',
    title: 'Artifact',
    status: 'draft',
    data: {},
    content_hash: 'hash',
    created_at: '2026-04-24T00:00:00.000Z',
    updated_at: '2026-04-24T00:00:00.000Z',
    ...overrides,
  }
}

describe('developer definition revisions', () => {
  it('filters immutable revision artifacts from pm artifacts', () => {
    const artifacts = [
      artifact({
        id: 'latest-definition',
        data: { artifact_type: 'developer_definition' },
      }),
      artifact({
        id: 'revision-1',
        data: {
          artifact_type: 'developer_definition_revision',
          saved_revision: { revision_number: 1 },
        },
      }),
    ]

    expect(findDeveloperDefinitionRevisionArtifacts(artifacts).map((item) => item.id)).toEqual(['revision-1'])
  })

  it('returns the highest revision number as the latest saved revision', () => {
    const artifacts = [
      artifact({
        id: 'revision-1',
        updated_at: '2026-04-24T00:01:00.000Z',
        data: {
          artifact_type: 'developer_definition_revision',
          saved_revision: { revision_number: 1 },
        },
      }),
      artifact({
        id: 'revision-3',
        updated_at: '2026-04-24T00:00:00.000Z',
        data: {
          artifact_type: 'developer_definition_revision',
          saved_revision: { revision_number: 3 },
        },
      }),
      artifact({
        id: 'revision-2',
        updated_at: '2026-04-24T00:02:00.000Z',
        data: {
          artifact_type: 'developer_definition_revision',
          saved_revision: { revision_number: 2 },
        },
      }),
    ]

    expect(findLatestDeveloperDefinitionRevisionArtifact(artifacts)?.id).toBe('revision-3')
  })

  it('includes saved revision metadata in the exported contract envelope', () => {
    const contract = buildDeveloperDefinitionContract({
      project: {
        id: 'project-1',
        name: 'Project 1',
        summary: 'summary',
        domain: 'software_delivery',
        labels: [],
      } as unknown as ProjectDetail,
      baseline: null,
      requirements: null,
      scenarios: [],
      shape: null,
      traceability: null,
      developerDefinition: {
        artifact_type: 'developer_definition',
        source_inputs: {
          requirements_id: null,
          requirements_hash: null,
          scenario_ids: [],
          scenario_set_hash: null,
          shape_id: null,
          shape_hash: null,
          baseline_locked_at: null,
        },
        product_alignment: {
          governed_behavior_formalization: 'Preserve behavior',
          approval_posture_formalization: 'Require approval when needed',
        },
        identity: {
          system_name: 'Project 1',
          domain_name: 'software_delivery',
          delivery_model: 'standalone_service',
          architecture_shape: 'single_service',
          high_availability_required: false,
        },
        authority: {
          trust_mode: 'unsigned',
          trust_checkpoints_required: false,
          spending_actions_present: false,
          irreversible_actions_present: false,
          cost_visibility_required: false,
          preflight_authority_discovery: false,
          grantable_restrictions: false,
          restricted_vs_denied: false,
          delegation_tokens: false,
          scoped_authority: false,
          purpose_binding: false,
          approval_expectation: 'not_specified',
          recovery_sensitive: false,
          blocked_failure_posture: 'return_error',
        },
        audit: {
          durable_records_required: false,
          searchable_history_required: false,
          invocation_tracking: false,
          task_tracking: false,
          parent_invocation_tracking: false,
          client_reference_ids: false,
          service_handoffs_required: false,
          cross_service_reconstruction_required: false,
          cross_service_continuity_required: false,
        },
        backend_bindings: {
          data_access_backend_type: '',
          data_access_target_label: '',
          application_integration_backend_type: '',
          application_integration_system_name: '',
          application_integration_environment: '',
          application_integration_auth_type: '',
          application_integration_adapter_target: '',
        },
        service_backend_bindings: [],
        application_integration_governance: {
          safe_defaults: {
            default_result_limit: 25,
            require_approval_for_writes: false,
            require_clarification_on_ambiguous_record: false,
            dry_run_before_write: false,
          },
          permission_rules: [],
          clarification_rules: [],
          restriction_rules: [],
          denial_rules: [],
          approval_rules: [],
        },
        data_access_governance: {
          governed_outcomes: [],
          metric_rules: [],
          dimension_rules: [],
          limit_rules: [],
          use_rules: [],
          clarification_rules: [],
        },
        data_domain: {
          domain_name: 'software_delivery',
          metrics: [],
          dimensions: [],
          filters: [],
          grains: [],
          result_modes: [],
        },
        domain_concept_bindings: [],
        application_object_model: [],
        capability_formalizations: [],
        service_topology_bindings: [],
        actor_expectations: [],
        permission_intent_bindings: [],
        scenario_formalizations: [],
        composition_rules: [],
        verification: {
          supported_question_family_bindings: [],
          business_goal_bindings: [],
          non_goal_guards: [],
          success_criteria_checks: [],
          data_access_scenario_pack: {
            categories: [],
            target_count: 0,
          },
        },
        generation: {
          service_generation_mode: 'from_service_design',
          selected_service_ids: [],
          scalability_profile: 'stateless_horizontal',
          protocols: ['anip_http'],
          codegen_adapter: 'typescript_node',
          layout_strategy: 'monorepo',
        },
        naming: {
          namespace: 'software_delivery',
          package_prefix: 'project_1',
          service_name_prefix: 'project_1',
        },
        rationale: '',
        compiled_contract_identity: null,
        saved_revision: {
          revision_number: 7,
          revision_artifact_id: 'project-1-developer-definition-revision-7',
          previous_revision_artifact_id: 'project-1-developer-definition-revision-6',
          saved_at: '2026-04-24T08:00:00.000Z',
        },
        saved_at: '2026-04-24T08:00:00.000Z',
      } as DeveloperDefinitionData,
    })

    expect(contract.artifact_type).toBe('anip_service_definition')
    expect(contract.contract_schema_version).toBe('anip-service-definition/v1')
    expect(contract.source.developer_definition_revision).toEqual({
      revision_number: 7,
      revision_artifact_id: 'project-1-developer-definition-revision-7',
      previous_revision_artifact_id: 'project-1-developer-definition-revision-6',
      saved_at: '2026-04-24T08:00:00.000Z',
    })
  })

  it('preserves saved actor formalization when rebuilding a developer draft', () => {
    const project = {
      id: 'project-1',
      name: 'Project 1',
      summary: 'summary',
      domain: 'gtm',
      labels: [],
    } as unknown as ProjectDetail
    const existing = {
      artifact_type: 'developer_definition',
      source_inputs: {
        requirements_id: null,
        requirements_hash: null,
        scenario_ids: [],
        scenario_set_hash: null,
        shape_id: null,
        shape_hash: null,
        baseline_locked_at: null,
      },
      product_alignment: {
        governed_behavior_formalization: '',
        approval_posture_formalization: '',
      },
      identity: {
        system_name: 'Project 1',
        domain_name: 'gtm',
        delivery_model: 'multiple_coordinated_services',
        architecture_shape: 'multi_service_estate',
        high_availability_required: false,
      },
      authority: {
        trust_mode: 'signed',
        trust_checkpoints_required: false,
        spending_actions_present: false,
        irreversible_actions_present: false,
        cost_visibility_required: false,
        preflight_authority_discovery: true,
        grantable_restrictions: false,
        restricted_vs_denied: true,
        delegation_tokens: true,
        scoped_authority: true,
        purpose_binding: true,
        approval_expectation: 'not_specified',
        recovery_sensitive: false,
        blocked_failure_posture: '',
      },
      audit: {
        durable_records_required: true,
        searchable_history_required: true,
        invocation_tracking: true,
        task_tracking: true,
        parent_invocation_tracking: true,
        client_reference_ids: true,
        service_handoffs_required: true,
        cross_service_reconstruction_required: true,
        cross_service_continuity_required: true,
      },
      backend_bindings: {
        data_access_backend_type: '',
        data_access_target_label: '',
        application_integration_backend_type: '',
        application_integration_system_name: '',
        application_integration_environment: '',
        application_integration_auth_type: '',
        application_integration_adapter_target: '',
      },
      service_backend_bindings: [],
      application_integration_governance: {
        safe_defaults: {
          default_result_limit: 25,
          require_approval_for_writes: false,
          require_clarification_on_ambiguous_record: false,
          dry_run_before_write: false,
        },
        permission_rules: [],
        clarification_rules: [],
        restriction_rules: [],
        denial_rules: [],
        approval_rules: [],
      },
      data_access_governance: {
        governed_outcomes: [],
        metric_rules: [],
        dimension_rules: [],
        limit_rules: [],
        use_rules: [],
        clarification_rules: [],
      },
      data_domain: {
        domain_name: 'gtm',
        metrics: [],
        dimensions: [],
        filters: [],
        grains: [],
        result_modes: [],
      },
      domain_concept_bindings: [],
      application_object_model: [],
      capability_formalizations: [],
      service_topology_bindings: [],
      actor_expectations: [{
        id: 'actor_sales_leader',
        actor_id: 'sales_leader',
        actor_title: 'Sales Leader',
        summary_formalization: 'Saved reviewer-approved summary.',
        visibility_formalization: 'Saved reviewer-approved visibility.',
        action_formalization: 'Saved reviewer-approved actions.',
        approval_formalization: 'Saved reviewer-approved approvals.',
      }],
      permission_intent_bindings: [],
      scenario_formalizations: [],
      composition_rules: [],
      verification: {
        supported_question_family_bindings: [],
        business_goal_bindings: [],
        non_goal_guards: [],
        success_criteria_checks: [],
        data_access_scenario_pack: {
          categories: [],
          target_count: 0,
        },
      },
      generation: {
        service_generation_mode: 'from_service_design',
        selected_service_ids: [],
        scalability_profile: 'stateless_horizontal',
        protocols: ['anip_http'],
        codegen_adapter: 'typescript_node',
        layout_strategy: 'monorepo',
      },
      naming: {
        namespace: 'gtm',
        package_prefix: 'project_1',
        service_name_prefix: 'project_1',
      },
      rationale: '',
      compiled_contract_identity: null,
      saved_revision: null,
      saved_at: null,
    } as DeveloperDefinitionData
    const rebuilt = buildDeveloperDefinitionData({
      project,
      baseline: null,
      requirements: null,
      scenarios: [],
      shape: null,
      pmArtifacts: [
        artifact({
          id: 'project-1-actor_model',
          data: {
            artifact_type: 'actor_model',
            actors: [{
              actor_id: 'sales_leader',
              title: 'Sales Leader',
              summary: 'New generated summary.',
              visibility_expectations: 'New generated visibility.',
              action_expectations: 'New generated actions.',
              approval_expectations: 'New generated approvals.',
            }],
          },
        }),
      ],
      existing,
    })

    expect(rebuilt.actor_expectations[0]).toMatchObject({
      summary_formalization: 'Saved reviewer-approved summary.',
      visibility_formalization: 'Saved reviewer-approved visibility.',
      action_formalization: 'Saved reviewer-approved actions.',
      approval_formalization: 'Saved reviewer-approved approvals.',
    })
  })
})
