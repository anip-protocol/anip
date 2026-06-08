import { describe, expect, it } from 'vitest'
import {
  analyzeAgentConsumptionReadiness,
  applyReadinessFindingReviews,
} from '../design/agent-consumption-readiness'
import type { DeveloperDefinitionData } from '../design/project-types'

function baseDefinition(overrides: Partial<DeveloperDefinitionData> = {}): DeveloperDefinitionData {
  return {
    capability_formalizations: [],
    scenario_formalizations: [],
    verification: {
      supported_question_family_bindings: [],
      business_goal_bindings: [],
      non_goal_guards: [],
      success_criteria_checks: [],
      data_access_scenario_pack: {
        target_count: 0,
        categories: [],
      },
    },
    ...overrides,
  } as DeveloperDefinitionData
}

describe('agent consumption readiness', () => {
  it('blocks required inputs without agent-consumable classification and emits a probe', () => {
    const report = analyzeAgentConsumptionReadiness(baseDefinition({
      capability_formalizations: [
        {
          id: 'cap-risk',
          source_kind: 'application_integration',
          service_id: 'gtm-prioritization-service',
          capability_id: 'gtm.account_risk_ranking',
          title: 'Account Risk Ranking',
          summary: 'Rank account risk for a quarter.',
          intent_type: 'rank',
          operation_type: 'read',
          side_effect_level: 'read',
          backend_operation: 'rank_accounts',
          path_template: '',
          output_shape: 'risk_ranking',
          inputs: [
            {
              input_name: 'quarter',
              input_type: 'string',
              required: true,
              summary: 'Quarter label.',
              default_value: '',
              allowed_values: [],
            },
          ],
        },
      ],
    }))

    expect(report.status).toBe('blocked')
    const classificationFinding = report.findings.find((finding) =>
      finding.category === 'clarification_behavior'
      && finding.input_name === 'quarter',
    )
    expect(classificationFinding?.severity).toBe('blocker')
    expect(report.probes.some((probe) =>
      probe.expected_outcome === 'clarification_required'
      && probe.target_capability_id === 'gtm.account_risk_ranking',
    )).toBe(true)
  })

  it('requires composition or app glue for derived target capabilities', () => {
    const report = analyzeAgentConsumptionReadiness(baseDefinition({
      capability_formalizations: [
        {
          id: 'cap-top',
          source_kind: 'application_integration',
          service_id: 'gtm-enrichment-service',
          capability_id: 'gtm.top_account_enrichment_summary',
          title: 'Top Account Enrichment Summary',
          summary: 'Summarize enrichment for top accounts.',
          intent_type: 'summarize',
          operation_type: 'read',
          side_effect_level: 'read',
          backend_operation: 'summarize_top_accounts',
          path_template: '',
          output_shape: 'enrichment_summary',
          inputs: [],
        },
      ],
    }))

    expect(report.findings.some((finding) =>
      finding.category === 'derived_target'
      && finding.capability_id === 'gtm.top_account_enrichment_summary',
    )).toBe(true)
  })

  it('treats v0.24 catalog-backed references as explicit target binding', () => {
    const report = analyzeAgentConsumptionReadiness(baseDefinition({
      capability_formalizations: [
        {
          id: 'cap-enrichment',
          source_kind: 'application_integration',
          service_id: 'gtm-enrichment-service',
          capability_id: 'gtm.account_enrichment_summary',
          title: 'Account Enrichment Summary',
          summary: 'Return bounded firmographic context and fit signals for selected accounts.',
          intent_type: 'summarize',
          operation_type: 'read',
          side_effect_level: 'read',
          backend_operation: 'account_enrichment_summary',
          path_template: '',
          output_shape: 'account_enrichment_summary',
          inputs: [
            {
              input_name: 'account_names',
              input_type: 'string',
              required: true,
              summary: 'Comma-separated account names.',
              default_value: '',
              allowed_values: [],
              semantic_type: 'entity_reference',
              entity_reference: true,
              catalog_ref: 'gtm.account_catalog',
              resolution: {
                mode: 'backend_resolved',
                resolver_ref: 'gtm.account_catalog',
                on_missing: 'clarify',
                on_ambiguous: 'clarify',
                on_unresolved: 'clarify',
              },
            },
          ],
        },
      ],
    }))

    expect(report.findings.some((finding) =>
      finding.category === 'derived_target'
      && finding.capability_id === 'gtm.account_enrichment_summary',
    )).toBe(false)
  })

  it('treats optional backend-resolved target references as service-owned derived target binding', () => {
    const report = analyzeAgentConsumptionReadiness(baseDefinition({
      capability_formalizations: [
        {
          id: 'cap-bottleneck-outreach',
          source_kind: 'application_integration',
          service_id: 'gtm-outreach-service',
          capability_id: 'gtm.bottleneck_account_outreach_draft',
          title: 'Bottleneck Account Outreach Draft',
          summary: 'Select or accept a bounded bottleneck target, draft outreach, and stop at approval.',
          intent_type: 'approval_gated',
          operation_type: 'approval_gated',
          side_effect_level: 'approval_gated',
          backend_operation: 'bottleneck_account_outreach_draft',
          path_template: '',
          output_shape: 'outreach_draft_preview',
          inputs: [
            {
              input_name: 'target_ref',
              input_type: 'string',
              required: false,
              summary: 'Optional explicit account selected from the bottleneck review.',
              default_value: '',
              allowed_values: [],
              semantic_type: 'entity_reference',
              entity_reference: true,
              catalog_ref: 'gtm.account_catalog',
              resolution: {
                mode: 'backend_resolved',
                resolver_ref: 'gtm.account_catalog',
                on_missing: 'omit',
                on_ambiguous: 'clarify',
                on_unresolved: 'clarify',
              },
            },
          ],
        },
      ],
    }))

    expect(report.findings.some((finding) =>
      finding.category === 'derived_target'
      && finding.capability_id === 'gtm.bottleneck_account_outreach_draft',
    )).toBe(false)
  })

  it('treats closed-value reference catalogs as explicit target binding', () => {
    const report = analyzeAgentConsumptionReadiness(baseDefinition({
      capability_formalizations: [
        {
          id: 'cap-score',
          source_kind: 'application_integration',
          service_id: 'gtm-prioritization-service',
          capability_id: 'gtm.score_leads',
          title: 'Score Leads',
          summary: 'Return bounded lead scores and explainable priority bands for a named cohort.',
          intent_type: 'rank',
          operation_type: 'read',
          side_effect_level: 'read',
          backend_operation: 'score_leads',
          path_template: '',
          output_shape: 'lead_scores',
          inputs: [
            {
              input_name: 'cohort_ref',
              input_type: 'string',
              required: true,
              summary: 'Cohort reference.',
              default_value: '',
              allowed_values: ['inbound_last_week', 'webinar_q2'],
              semantic_type: 'cohort_reference',
              catalog_ref: 'gtm.cohort_catalog',
              resolution: {
                mode: 'closed_values',
                on_missing: 'clarify',
                on_ambiguous: 'clarify',
                on_unresolved: 'clarify',
              },
            },
          ],
        },
      ],
    }))

    expect(report.findings.some((finding) =>
      finding.category === 'derived_target'
      && finding.capability_id === 'gtm.score_leads',
    )).toBe(false)
  })

  it('does not treat risk or bottleneck summary wording alone as derived target selection', () => {
    const report = analyzeAgentConsumptionReadiness(baseDefinition({
      capability_formalizations: [
        {
          id: 'cap-forecast',
          source_kind: 'application_integration',
          service_id: 'gtm-pipeline-service',
          capability_id: 'gtm.pipeline_forecast_summary',
          title: 'Pipeline Forecast Summary',
          summary: 'Return risk-adjusted and best-case forecast summaries for a quarter.',
          intent_type: 'summarize',
          operation_type: 'read',
          side_effect_level: 'read',
          backend_operation: 'forecast',
          path_template: '',
          output_shape: 'forecast_summary',
          inputs: [],
        },
      ],
    }))

    expect(report.findings.some((finding) =>
      finding.category === 'derived_target'
      && finding.capability_id === 'gtm.pipeline_forecast_summary',
    )).toBe(false)
  })

  it('counts v0.24 input resolution as an optional omission rule', () => {
    const report = analyzeAgentConsumptionReadiness(baseDefinition({
      capability_formalizations: [
        {
          id: 'cap-pipeline',
          source_kind: 'application_integration',
          service_id: 'gtm-pipeline-service',
          capability_id: 'gtm.pipeline_summary',
          title: 'Pipeline Summary',
          summary: 'Return a bounded pipeline summary.',
          intent_type: 'summarize',
          operation_type: 'read',
          side_effect_level: 'read',
          backend_operation: 'pipeline_summary',
          path_template: '',
          output_shape: 'pipeline_summary',
          inputs: [
            {
              input_name: 'owner_scope',
              input_type: 'string',
              required: false,
              summary: 'Optional region, team, owner, or company-wide scope.',
              default_value: '',
              allowed_values: [],
              semantic_type: 'scope_reference',
              resolution: {
                mode: 'actor_policy_or_explicit',
                on_missing: 'use_actor_scope',
                on_ambiguous: 'clarify',
                on_unresolved: 'clarify',
              },
            },
          ],
        },
      ],
    }))

    expect(report.findings.some((finding) =>
      finding.category === 'declared_defaults'
      && finding.input_name === 'owner_scope',
    )).toBe(false)
  })

  it('counts v0.24 closed-values resolution as enough enum grounding for readiness', () => {
    const report = analyzeAgentConsumptionReadiness(baseDefinition({
      capability_formalizations: [
        {
          id: 'cap-summary',
          source_kind: 'application_integration',
          service_id: 'gtm-pipeline-service',
          capability_id: 'gtm.pipeline_summary',
          title: 'Pipeline Summary',
          summary: 'Return a bounded pipeline summary.',
          intent_type: 'summarize',
          operation_type: 'read',
          side_effect_level: 'read',
          backend_operation: 'pipeline_summary',
          path_template: '',
          output_shape: 'pipeline_summary',
          inputs: [
            {
              input_name: 'detail_level',
              input_type: 'string',
              required: false,
              summary: 'Response detail level.',
              default_value: 'summary',
              allowed_values: ['summary', 'stage_breakdown'],
              semantic_type: 'business_category',
              resolution: {
                mode: 'closed_values',
                on_missing: 'use_default',
                on_ambiguous: 'clarify',
                on_unresolved: 'clarify',
              },
            },
          ],
        },
      ],
    }))

    expect(report.findings.some((finding) =>
      finding.category === 'app_glue'
      && finding.input_name === 'detail_level',
    )).toBe(false)
  })

  it('treats ranking plus bounded limit inputs as service-owned derived target selection', () => {
    const report = analyzeAgentConsumptionReadiness(baseDefinition({
      capability_formalizations: [
        {
          id: 'cap-risk',
          source_kind: 'application_integration',
          service_id: 'gtm-pipeline-service',
          capability_id: 'gtm.account_risk_summary',
          title: 'Account Risk Summary',
          summary: 'Return at-risk account ranking for a quarter.',
          intent_type: 'rank',
          operation_type: 'read',
          side_effect_level: 'read',
          backend_operation: 'account_risk_summary',
          path_template: '',
          output_shape: 'account_risk_summary',
          inputs: [
            {
              input_name: 'ranking_basis',
              input_type: 'string',
              required: true,
              summary: 'Risk ranking basis.',
              default_value: 'risk_score',
              allowed_values: ['risk_score'],
              semantic_type: 'business_category',
              resolution: {
                mode: 'closed_values',
                on_missing: 'use_default',
                on_ambiguous: 'clarify',
                on_unresolved: 'clarify',
              },
            },
            {
              input_name: 'limit',
              input_type: 'integer',
              required: false,
              summary: 'Maximum number of accounts to include.',
              default_value: '',
              allowed_values: [],
              semantic_type: 'quantity_limit',
              resolution: {
                mode: 'explicit_only',
                on_missing: 'omit',
              },
            },
          ],
        },
      ],
    }))

    expect(report.findings.some((finding) =>
      finding.category === 'derived_target'
      && finding.capability_id === 'gtm.account_risk_summary',
    )).toBe(false)
  })

  it('turns explicit implementation-fit glue into required app-glue guidance', () => {
    const report = analyzeAgentConsumptionReadiness(baseDefinition({
      capability_formalizations: [
        {
          id: 'cap-draft',
          source_kind: 'application_integration',
          service_id: 'gtm-outreach-service',
          capability_id: 'gtm.draft_outreach_message',
          title: 'Draft Outreach Message',
          summary: 'Draft bounded outreach content.',
          intent_type: 'business_action',
          operation_type: 'read',
          side_effect_level: 'read',
          implementation_fit: {
            category: 'agent_app_glue',
            rationale: 'Needs product-specific presentation and tone framing.',
          },
          backend_operation: 'draft_outreach',
          path_template: '',
          output_shape: 'outreach_draft',
          inputs: [],
        },
      ],
    }))

    expect(report.required_app_glue.some((glue) =>
      glue.category === 'app_glue'
      && glue.capability_id === 'gtm.draft_outreach_message',
    )).toBe(true)
  })

  it('flags mutating capabilities without approval grant policy as blocked', () => {
    const report = analyzeAgentConsumptionReadiness(baseDefinition({
      capability_formalizations: [
        {
          id: 'cap-send',
          source_kind: 'application_integration',
          service_id: 'messaging-service',
          capability_id: 'message.send',
          title: 'Send Message',
          summary: 'Send a message to a customer.',
          intent_type: 'send',
          operation_type: 'write',
          side_effect_level: 'write',
          business_effects: {
            produces: ['external_dispatch'],
            does_not_produce: [],
          },
          backend_operation: 'send_message',
          path_template: '',
          output_shape: 'send_result',
          inputs: [],
        },
      ],
    }))

    expect(report.status).toBe('blocked')
    expect(report.findings.some((finding) =>
      finding.category === 'approval_boundary'
      && finding.severity === 'blocker',
    )).toBe(true)
  })

  it('does not block approval-required capabilities that receive compiler-default grants', () => {
    const report = analyzeAgentConsumptionReadiness(baseDefinition({
      capability_formalizations: [
        {
          id: 'cap-preview',
          source_kind: 'application_integration',
          service_id: 'routing-service',
          capability_id: 'gtm.route_leads',
          title: 'Route Leads',
          summary: 'Prepare bounded routing recommendations without executing downstream assignment mutations.',
          intent_type: 'approval_gated',
          operation_type: 'approval_gated',
          side_effect_level: 'approval_required',
          business_effects: {
            produces: ['approval.request', 'system.preview_mutation'],
            does_not_produce: ['approval.execute'],
          },
          backend_operation: 'route_leads',
          path_template: '',
          output_shape: 'routing_preview',
          inputs: [],
        },
      ],
    }))

    expect(report.status).not.toBe('blocked')
    expect(report.findings.some((finding) =>
      finding.category === 'approval_boundary'
      && finding.severity === 'blocker',
    )).toBe(false)
  })

  it('blocks approval-preview wording that is still declared as read-only data access', () => {
    const report = analyzeAgentConsumptionReadiness(baseDefinition({
      capability_formalizations: [
        {
          id: 'cap-followup',
          source_kind: 'application_integration',
          service_id: 'gtm-pipeline-service',
          capability_id: 'gtm.prepare_followup_tasks',
          title: 'Prepare Follow-up Tasks',
          summary: 'Prepare follow-up task previews for high-risk accounts.',
          intent_type: 'business_action',
          operation_type: 'read',
          side_effect_level: 'read',
          business_effects: {
            produces: ['data.read'],
            does_not_produce: ['raw_data_export'],
          },
          backend_operation: 'prepare_followup_tasks',
          path_template: '',
          output_shape: 'task_preview',
          inputs: [],
        },
      ],
    }))

    expect(report.status).toBe('blocked')
    expect(report.findings.some((finding) =>
      finding.id === 'gtm.prepare_followup_tasks:approval-effect-drift'
      && finding.category === 'approval_boundary'
    )).toBe(true)
    const finding = report.findings.find((item) => item.id === 'gtm.prepare_followup_tasks:approval-effect-drift')
    expect(finding?.title).toBe('Approval boundary is unclear')
    expect(finding?.detail).toContain('marked as read-only')
  })

  it('does not treat read-only follow-up content as approval-preview drift', () => {
    const report = analyzeAgentConsumptionReadiness(baseDefinition({
      capability_formalizations: [
        {
          id: 'cap-followup-content',
          source_kind: 'application_integration',
          service_id: 'gtm-outreach-service',
          capability_id: 'gtm.suggest_followup_content',
          title: 'Suggest Follow-up Content',
          summary: 'Suggest read-only follow-up messaging content for an account.',
          intent_type: 'draft',
          operation_type: 'read',
          side_effect_level: 'read',
          business_effects: {
            produces: ['content.draft'],
            does_not_produce: ['external_dispatch'],
          },
          backend_operation: 'suggest_followup_content',
          path_template: '',
          output_shape: 'draft_content',
          inputs: [],
        },
      ],
    }))

    expect(report.findings.some((finding) =>
      finding.id === 'gtm.suggest_followup_content:approval-effect-drift'
    )).toBe(false)
  })

  it('does not treat non-mutating routing recommendations as approval-preview drift', () => {
    const report = analyzeAgentConsumptionReadiness(baseDefinition({
      capability_formalizations: [
        {
          id: 'cap-score-leads',
          source_kind: 'application_integration',
          service_id: 'gtm-prioritization-service',
          capability_id: 'gtm.score_leads',
          title: 'Score leads',
          summary: 'Score and rank a bounded lead cohort with explainable rationale and non-mutating routing posture recommendations.',
          intent_type: 'read',
          operation_type: 'rank',
          side_effect_level: 'read_only',
          business_effects: {
            produces: ['content.summary'],
            does_not_produce: ['system.mutation'],
          },
          backend_operation: 'score_leads',
          path_template: '',
          output_shape: 'governed.ranked_entities',
          inputs: [],
        },
      ],
    }))

    expect(report.findings.some((finding) =>
      finding.id === 'gtm.score_leads:approval-effect-drift'
    )).toBe(false)
  })

  it('does not treat explanation as planning approval-preview drift', () => {
    const report = analyzeAgentConsumptionReadiness(baseDefinition({
      capability_formalizations: [
        {
          id: 'cap-account-fit',
          source_kind: 'application_integration',
          service_id: 'gtm-enrichment-service',
          capability_id: 'gtm.account_fit_explanation',
          title: 'Account Fit Explanation',
          summary: 'Explain why a named account fits the ideal customer profile using bounded evidence.',
          intent_type: 'business_action',
          operation_type: 'read',
          side_effect_level: 'read',
          business_effects: {
            produces: ['content.summary'],
            does_not_produce: ['raw_data_export'],
          },
          backend_operation: 'account_fit_explanation',
          path_template: '',
          output_shape: 'account_fit_explanation',
          inputs: [],
        },
      ],
    }))

    expect(report.findings.some((finding) =>
      finding.id === 'gtm.account_fit_explanation:approval-effect-drift'
    )).toBe(false)
  })

  it('emits approval-preview boundary probes for governed preview capabilities', () => {
    const report = analyzeAgentConsumptionReadiness(baseDefinition({
      capability_formalizations: [
        {
          id: 'cap-followup',
          source_kind: 'application_integration',
          service_id: 'gtm-pipeline-service',
          capability_id: 'gtm.prepare_followup_tasks',
          title: 'Prepare Follow-up Tasks',
          summary: 'Prepare follow-up task previews for high-risk accounts.',
          intent_type: 'approval_gated',
          operation_type: 'approval_gated',
          side_effect_level: 'approval_required',
          business_effects: {
            produces: ['approval.request', 'system.preview_mutation'],
            does_not_produce: ['approval.execute'],
          },
          grant_policy: {
            allowed_grant_types: ['one_time'],
            default_grant_type: 'one_time',
            expires_in_seconds: 900,
            max_uses: 1,
          },
          backend_operation: 'prepare_followup_tasks',
          path_template: '',
          output_shape: 'task_preview',
          inputs: [],
        },
      ],
    }))

    expect(report.probes.some((probe) =>
      probe.id === 'gtm.prepare_followup_tasks:approval-boundary-probe'
      && probe.expected_outcome === 'approval_required'
      && probe.target_capability_id === 'gtm.prepare_followup_tasks'
    )).toBe(true)
  })

  it('emits ungrounded temporal scope probes for required quarter inputs', () => {
    const report = analyzeAgentConsumptionReadiness(baseDefinition({
      capability_formalizations: [
        {
          id: 'cap-forecast',
          source_kind: 'application_integration',
          service_id: 'gtm-pipeline-service',
          capability_id: 'gtm.pipeline_forecast_summary',
          title: 'Pipeline Forecast Summary',
          summary: 'Summarize forecast for a quarter.',
          intent_type: 'summarize',
          operation_type: 'read',
          side_effect_level: 'read',
          backend_operation: 'forecast',
          path_template: '',
          output_shape: 'forecast_summary',
          inputs: [
            {
              input_name: 'quarter',
              input_type: 'string',
              required: true,
              summary: 'Quarter label like 2017-Q2.',
              default_value: '',
              input_format: 'business_quarter',
              allowed_values: [],
            },
          ],
        },
      ],
    }))

    expect(report.probes.some((probe) =>
      probe.id === 'gtm.pipeline_forecast_summary:quarter:ungrounded-scope-probe'
      && probe.expected_outcome === 'clarification_required'
    )).toBe(true)
  })

  it('emits ungrounded reference probes for required cohort inputs', () => {
    const report = analyzeAgentConsumptionReadiness(baseDefinition({
      capability_formalizations: [
        {
          id: 'cap-prioritize',
          source_kind: 'application_integration',
          service_id: 'gtm-prioritization-service',
          capability_id: 'gtm.prioritize_accounts',
          title: 'Prioritize Accounts',
          summary: 'Rank bounded accounts by priority.',
          intent_type: 'rank',
          operation_type: 'read',
          side_effect_level: 'read',
          backend_operation: 'prioritize_accounts',
          path_template: '',
          output_shape: 'priority_ranking',
          inputs: [
            {
              input_name: 'cohort_ref',
              input_type: 'string',
              required: true,
              summary: 'Explicit bounded lead or account cohort to score.',
              default_value: '',
              allowed_values: [],
              semantic_type: 'cohort_reference',
            },
          ],
        },
      ],
    }))

    expect(report.probes.some((probe) =>
      probe.id === 'gtm.prioritize_accounts:cohort_ref:ungrounded-reference-probe'
      && probe.expected_outcome === 'clarification_required'
      && probe.target_capability_id === 'gtm.prioritize_accounts'
    )).toBe(true)
  })

  it('does not treat fronting adapter raw-operation steps as unresolved ANIP composition', () => {
    const report = analyzeAgentConsumptionReadiness(baseDefinition({
      integration_fronting: {
        project_type: 'fronting_service',
        integration_profile: {} as NonNullable<DeveloperDefinitionData['integration_fronting']>['integration_profile'],
        capability_mappings: [
          {
            id: 'jira-story-prepare',
            capability_id: 'jira.story.prepare',
            title: 'Prepare Story',
            intent: 'Prepare a Jira story preview.',
            service_id: 'jira-fronting-service',
            service_name: 'Jira Fronting Service',
            backend_kind: 'native_api',
            connection_ref: 'jira_fronting',
            raw_operation_refs: ['jira.rest.get_create_metadata', 'jira.rest.create_issue'],
            backend_bindings: [],
            execution_posture: 'approval_preview',
            side_effect_level: 'write_adjacent',
            subject_kind: 'jira_issue',
            context_type: 'story_preparation',
            output_intent: 'issue_creation_preview',
            required_inputs: ['project_key', 'summary'],
            optional_inputs: [],
            backend_input_mode: 'explicit',
            derived_required_backend_inputs: [],
            derived_optional_backend_inputs: [],
            explicit_required_backend_inputs: ['project_key', 'summary'],
            explicit_optional_backend_inputs: [],
            approval_rule_refs: [],
            denial_rule_refs: [],
            clarification_rule_refs: [],
            audit_required: true,
          },
        ],
      },
      capability_formalizations: [
        {
          id: 'jira-story-prepare',
          source_kind: 'application_integration',
          service_id: 'jira-fronting-service',
          capability_id: 'jira.story.prepare',
          title: 'Prepare Story',
          summary: 'Prepare a Jira story preview before any issue is created.',
          intent_type: 'approval_gated',
          operation_type: 'approval_gated',
          side_effect_level: 'write_adjacent',
          business_effects: {
            produces: ['approval.request', 'system.preview_mutation'],
            does_not_produce: ['system.mutation'],
          },
          backend_operation: 'prepare_story',
          path_template: '',
          output_shape: 'issue_creation_preview',
          inputs: [
            {
              input_name: 'project_key',
              input_type: 'string',
              required: true,
              summary: 'Allowed Jira project key.',
              default_value: '',
              allowed_values: [],
              semantic_type: 'project_scope',
              entity_reference: true,
            },
            {
              input_name: 'summary',
              input_type: 'string',
              required: true,
              summary: 'Story summary.',
              default_value: '',
              allowed_values: [],
              semantic_type: 'work_item_summary',
            },
          ],
        },
      ],
      scenario_formalizations: [
        {
          scenario_id: 'prepare-story',
          scenario_key: 'prepare-story',
          scenario_title: 'Prepare a governed Jira story preview',
          primary_capability: 'jira.story.prepare',
          actor_context: 'Product manager.',
          business_scope: 'Allowed Jira project.',
          time_scope: 'Current request.',
          side_effect_formalization: 'Preview only; do not create the issue.',
          expected_cost_formalization: 'Low.',
          budget_guard_formalization: 'Single preview.',
          permission_formalization: 'Allowed project only.',
          task_tracking_formalization: 'Record preview request.',
          participating_service_ids: ['jira-fronting-service'],
          orchestration_steps: [
            {
              id: 'metadata',
              service_id: 'jira-fronting-service',
              step_kind: 'capability_execution',
              capability_id: 'jira.story.prepare',
              outcome_type: 'intermediate_result',
              outcome_notes: 'Load create metadata.',
              stop_condition: 'continue',
            },
            {
              id: 'preview',
              service_id: 'jira-fronting-service',
              step_kind: 'capability_execution',
              capability_id: 'jira.story.prepare',
              outcome_type: 'approval_required',
              outcome_notes: 'Return preview and stop before mutation.',
              stop_condition: 'approval_required',
            },
          ],
          required_behaviors: ['Return preview and stop before mutation.'],
          required_anip_support: ['approval_required'],
          implementation_notes: 'The fronting service owns native Jira metadata and preview adapter calls.',
        },
      ],
    }))

    expect(report.findings.some((finding) =>
      finding.category === 'composition_candidate'
      && finding.id === 'prepare-story:composition-candidate',
    )).toBe(false)
  })

  it('turns explicit finding review decisions into app-glue handoff entries', () => {
    const report = analyzeAgentConsumptionReadiness(baseDefinition({
      capability_formalizations: [
        {
          id: 'cap-top',
          source_kind: 'application_integration',
          service_id: 'gtm-enrichment-service',
          capability_id: 'gtm.top_account_enrichment_summary',
          title: 'Top Account Enrichment Summary',
          summary: 'Summarize enrichment for top accounts.',
          intent_type: 'summarize',
          operation_type: 'read',
          side_effect_level: 'read',
          backend_operation: 'summarize_top_accounts',
          path_template: '',
          output_shape: 'enrichment_summary',
          inputs: [],
        },
      ],
    }))
    const finding = report.findings.find((item) => item.category === 'derived_target')
    expect(finding).toBeTruthy()

    const reviewed = applyReadinessFindingReviews(report, {
      [finding!.id]: {
        id: finding!.id,
        decision: 'explicit_app_glue',
        note: 'The app selects the target cohort before invoking enrichment.',
        reviewed_at: '2026-04-28T00:00:00Z',
      },
    })

    expect(reviewed.summary.required_app_glue).toBe(1)
    expect(reviewed.summary.warnings).toBe(report.summary.warnings - 1)
    expect(reviewed.required_app_glue[0].capability_id).toBe('gtm.top_account_enrichment_summary')
    expect(reviewed.finding_reviews?.[finding!.id]?.decision).toBe('explicit_app_glue')
  })
})
