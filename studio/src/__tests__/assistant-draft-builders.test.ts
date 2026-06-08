import { describe, expect, it } from 'vitest'
import type {
  ArtifactRecord,
  DeveloperBaselineData,
  DeveloperIntegrationFrontingBackendBinding,
  IntegrationDiscoveryRecord,
  ProjectDetail,
  ShapeRecord,
} from '../design/project-types'
import {
  buildProductDesignSufficiencyCards,
  PRODUCT_SUMMARY_ARTIFACT_TYPE,
} from '../design/product-design'
import {
  buildDeveloperDefinitionData,
  buildGeneratedRuntimeTarget,
  buildIntegrationAdapterBindings,
  buildIntegrationAdapterScaffoldModuleContent,
  buildLocalConformanceReport,
  clearAssistantSeededFieldsForSection,
  developerDefinitionTargetStatus,
  INTEGRATION_FRONTING_MAPPING_ARTIFACT_TYPE,
  resolveIntegrationFrontingBackendBindingHealth,
  shapeDeclaresSourceCapabilityInventory,
  summarizeAssistantSeededFields,
  validateDeveloperDefinitionRequiredFields,
} from '../design/developer-definition'
import {
  buildTraceabilityRecord,
} from '../design/traceability'
import {
  buildHighRiskConfirmationReport,
} from '../design/high-risk-confirmations'
import {
  validateDeveloperDraftSectionContract,
} from '../design/developer-design-draft-bundle'

function makeArtifact(overrides: Partial<ArtifactRecord> & { data: Record<string, any> }): ArtifactRecord {
  return {
    id: overrides.id ?? 'artifact-1',
    project_id: overrides.project_id ?? 'proj-1',
    title: overrides.title ?? 'Artifact',
    status: overrides.status ?? 'draft',
    data: overrides.data,
    content_hash: overrides.content_hash ?? 'hash-1',
    created_at: overrides.created_at ?? '2026-04-19T00:00:00Z',
    updated_at: overrides.updated_at ?? '2026-04-19T00:00:00Z',
  }
}

function makeProject(overrides: Partial<ProjectDetail> = {}): ProjectDetail {
  return {
    id: 'proj-1',
    workspace_id: 'ws-1',
    name: 'Revenue Ops Assistant',
    summary: 'Governed internal assistant for revenue operations.',
    domain: 'gtm',
    labels: [],
    created_at: '2026-04-19T00:00:00Z',
    updated_at: '2026-04-19T00:00:00Z',
    requirements_count: 1,
    scenarios_count: 1,
    proposals_count: 0,
    evaluations_count: 0,
    shapes_count: 1,
    service_metadata_count: 0,
    documents_count: 1,
    pm_artifacts_count: 0,
    ...overrides,
  }
}

function makeBaseline(): DeveloperBaselineData {
  return {
    artifact_type: 'developer_baseline',
    source_inputs: {
      requirements_id: 'req-1',
      requirements_hash: 'req-hash-1',
      scenario_ids: ['scn-1'],
      primary_scenario_id: 'scn-1',
      scenario_set_hash: 'scenario-hash-1',
      shape_id: 'shape-1',
      shape_hash: 'shape-hash-1',
    },
    locked_at: '2026-04-19T00:00:00Z',
    note: 'Locked PM baseline',
  }
}

function testApprovalGrantPolicy() {
  return {
    allowed_grant_types: ['one_time'],
    default_grant_type: 'one_time',
    expires_in_seconds: 900,
    max_uses: 1,
  }
}

function makeShape(): ShapeRecord {
  return {
    ...makeArtifact({
      id: 'shape-1',
      title: 'Service Shape',
      content_hash: 'shape-hash-1',
      data: {
        shape: {
          services: [
            {
              id: 'svc_pipeline',
              name: 'Pipeline',
              role: 'Review governed pipeline questions.',
              capabilities: ['gtm.pipeline_summary'],
              owns_concepts: ['pipeline'],
            },
          ],
          coordination: [],
          domain_concepts: [
            { id: 'pipeline', name: 'Pipeline', meaning: 'Pipeline overview', risk_note: '' },
          ],
          capability_contracts: [
            {
              id: 'gtm.pipeline_summary',
              purpose: 'Return a bounded pipeline summary.',
              source_kind: 'custom_code_bundle',
              contract_complete: true,
              side_effect_type: 'read',
              approval_required_when: [],
              business_effects: {
                produces: ['content.summary'],
                does_not_produce: ['raw_data_export'],
              },
              inputs: [
                { name: 'quarter', type: 'string', required: true, description: 'Quarter label.' },
              ],
            },
          ],
        },
      },
    }),
    requirements_id: 'req-1',
  }
}

describe('developer assistant draft contract gate', () => {
  it('blocks composed capability drafts that omit contract-level composition metadata', () => {
    const issues = validateDeveloperDraftSectionContract({
      id: 'capability_formalization',
      title: 'Capability Formalization',
      action: 'capability_formalization',
      selectedIds: ['canonical-capability-inventory'],
      status: 'proposed',
      envelope: {
        title: 'Capability Formalization',
        summary: 'Draft',
        mode: 'dev',
        capability: 'propose_capability_formalization',
        questions_for_user: [],
        watchouts: [],
        next_steps: [],
        proposal: {
          proposal_kind: 'candidate_blocks',
          artifact_type: 'capability_formalization',
          items: [
            {
              client_id: 'canonical-capability-inventory',
              title: 'Canonical capability contracts',
              body: 'Drafted contracts.',
              confidence: 'high',
              rationale: 'Source evidence.',
              structured_data: {
                capabilities: [
                  {
                    capability_id: 'demo.candidate_assignment_preparation',
                    kind: 'composed',
                    service_id: 'demo-issue-service',
                    composition: null,
                    inputs: [
                      { input_name: 'query', input_type: 'string', required: true },
                    ],
                  },
                ],
              },
            },
          ],
        },
      } as any,
    })

    expect(issues).toContain('demo.candidate_assignment_preparation is composed but does not define composition steps.')
    expect(issues).toContain('demo.candidate_assignment_preparation is composed but does not define input mapping.')
    expect(issues).toContain('demo.candidate_assignment_preparation is composed but does not define output mapping.')
    expect(issues).toContain('demo.candidate_assignment_preparation is composed but does not define failure policy.')
  })
})

describe('assistant draft builders', () => {
  it('uses saved PM clarification artifacts to keep Product Design source-driven instead of questionnaire-driven', () => {
    const artifacts: ArtifactRecord[] = [
      makeArtifact({
        id: 'summary-1',
        title: 'Business Summary',
        data: {
          artifact_type: PRODUCT_SUMMARY_ARTIFACT_TYPE,
          product_purpose: 'Help operators answer governed revenue questions.',
          business_problem: '',
          business_goals: [],
          supported_question_families: [],
          governed_behavior_summary: '',
          approval_posture_summary: '',
          multi_step_composition_rules: [],
          why_now: '',
          success_outcome_summary: '',
        },
      }),
      makeArtifact({
        id: 'summary-clarification-1',
        title: 'Saved Clarification',
        data: {
          artifact_type: 'assistant_section_clarifications',
          mode: 'pm',
          section_key: 'product_summary',
          accepted_payload: [
            {
              question_id: 'product-summary-purpose',
              prompt: 'What is the product trying to accomplish?',
              answer: 'Help operators answer governed revenue questions with explicit approval stops.',
            },
          ],
        },
      }),
    ]

    const cards = buildProductDesignSufficiencyCards('proj-1', artifacts, {
      documents_count: 1,
      requirements_count: 0,
      scenarios_count: 0,
    })
    const summary = cards.find((card) => card.key === 'product_summary')

    expect(summary?.status).toBe('draftable')
    expect(summary?.questions).toEqual([])
    expect(summary?.detail).toContain('saved clarification answers')
    expect(summary?.action_label).toBe('Draft From Source')
  })

  it('seeds Developer Definition deterministically from accepted assistant artifacts and tracks provenance', () => {
    const pmArtifacts: ArtifactRecord[] = [
      makeArtifact({
        id: 'summary-1',
        title: 'Business Summary',
        data: {
          artifact_type: 'product_summary',
          product_purpose: 'Help operators answer governed revenue questions.',
          business_problem: 'Operators rely on manual interpretation and hidden escalation paths.',
          business_goals: ['Answer recurring revenue questions with bounded results.'],
          supported_question_families: ['Risk and health review'],
          governed_behavior_summary: 'Return bounded answers, clarify missing inputs, and stop at approval boundaries.',
          approval_posture_summary: 'High-impact writes must stop for approval.',
          multi_step_composition_rules: ['Only compose steps when each stop condition remains explicit.'],
          why_now: 'Teams need a governed operating model now.',
          success_outcome_summary: 'Users can act faster without losing governed boundaries.',
        },
      }),
      makeArtifact({
        id: 'actors-1',
        title: 'Actor Model',
        data: {
          artifact_type: 'actor_model',
          actors: [
            {
              actor_id: 'ops_manager',
              title: 'Ops Manager',
              summary: 'Reviews governed revenue answers.',
              visibility_expectations: 'Can see bounded operational summaries.',
              action_expectations: 'Can request governed next steps.',
              approval_expectations: 'Approves high-impact writes.',
              notes: '',
            },
          ],
        },
      }),
      makeArtifact({
        id: 'areas-1',
        title: 'Business Areas',
        data: {
          artifact_type: 'business_areas',
          entries: [
            {
              business_area_id: 'pipeline',
              label: 'Pipeline',
              description: 'Governed pipeline review.',
            },
          ],
        },
      }),
      makeArtifact({
        id: 'permissions-1',
        title: 'Permission Intent',
        data: {
          artifact_type: 'permission_intent',
          policy_summary: 'Preserve actor-aware visibility and approval stops.',
          rules: [
            {
              actor_id: 'ops_manager',
              business_area: 'pipeline',
              access_posture: 'approval_required',
              governed_outcome_type: 'approval_stop',
              governed_outcome: 'Prepare the recommendation and stop for explicit approval.',
              notes: '',
            },
          ],
        },
      }),
      makeArtifact({
        id: 'non-goals-1',
        title: 'Non-Goals',
        data: {
          artifact_type: 'non_goals',
          entries: [
            {
              statement: 'Do not execute high-impact changes automatically.',
              rationale: 'Approval boundaries must remain explicit.',
            },
          ],
        },
      }),
      makeArtifact({
        id: 'success-1',
        title: 'Success Criteria',
        data: {
          artifact_type: 'success_criteria',
          entries: [
            {
              statement: 'Users get bounded answers quickly.',
              evidence: 'Scenario review confirms governed answers are usable.',
              priority: 'high',
              review_method: 'PM signoff',
            },
          ],
        },
      }),
      makeArtifact({
        id: 'service-design-1',
        title: 'Accepted Service Design',
        data: {
          artifact_type: 'assistant_service_design_candidates',
          accepted_payload: [
            {
              client_id: 'svc-boundaries-explicit',
              title: 'Make service ownership boundaries explicit',
              body: 'State which service owns each bounded responsibility and where coordination must stop.',
              rationale: 'Service ownership should be explicit before capability work deepens.',
            },
          ],
        },
      }),
      makeArtifact({
        id: 'runtime-policy-1',
        title: 'Accepted Runtime Policy',
        data: {
          artifact_type: 'assistant_runtime_policy_binding_candidates',
          accepted_payload: [
            {
              client_id: 'policy-actor-boundaries',
              title: 'Actor boundaries',
              body: 'Formalize actor-specific visibility and action posture explicitly.',
              rationale: 'Actor differences drive runtime policy.',
            },
            {
              client_id: 'policy-scope-constraints',
              title: 'Scope constraints',
              body: 'Bind runtime policy to stable business scopes and visibility boundaries.',
              rationale: 'Scope constraints should remain explicit.',
            },
            {
              client_id: 'policy-clarification-stops',
              title: 'Clarification stops',
              body: 'Clarify ambiguous records before returning an answer.',
              rationale: 'Ambiguous cases should not silently proceed.',
            },
            {
              client_id: 'policy-approval-decision-point',
              title: 'Approval boundary',
              body: 'Stop for approval before any high-impact write that changes operational state.',
              rationale: 'Approval boundaries must remain explicit.',
            },
          ],
        },
      }),
      makeArtifact({
        id: 'backend-bindings-1',
        title: 'Accepted Backend Bindings',
        data: {
          artifact_type: 'assistant_backend_binding_candidates',
          accepted_payload: [
            {
              client_id: 'backend-data-access-target',
              title: 'Data access target',
              body: 'Read governed pipeline data from the internal metrics API.',
              rationale: 'The contract should point to the bounded data source.',
            },
            {
              client_id: 'backend-integration-system',
              title: 'Integration system',
              body: 'Use the RevenueOps control-plane service for prepared next actions.',
              rationale: 'Integration ownership should be explicit.',
            },
          ],
        },
      }),
      makeArtifact({
        id: 'verification-1',
        title: 'Accepted Verification',
        data: {
          artifact_type: 'assistant_verification_expectation_candidates',
          accepted_payload: [
            {
              client_id: 'verification-question-family-evidence',
              title: 'Question family evidence',
              body: 'Use scenario review evidence for each supported question family.',
              rationale: 'Question-family verification should be explicit.',
            },
            {
              client_id: 'verification-business-goal-checks',
              title: 'Business goal checks',
              body: 'Tie business-goal verification to bounded-answer correctness and governance stops.',
              rationale: 'Business goals need explicit verification strategy.',
            },
            {
              client_id: 'verification-non-goal-guards',
              title: 'Non-goal guards',
              body: 'Verify that no high-impact change executes without approval.',
              rationale: 'Non-goal guardrails need evidence.',
            },
            {
              client_id: 'verification-success-evidence',
              title: 'Success evidence',
              body: 'Review PM-visible evidence that the bounded answer was usable and governed.',
              rationale: 'Success criteria need reviewable evidence.',
            },
          ],
        },
      }),
    ]

    const definition = buildDeveloperDefinitionData({
      project: makeProject(),
      baseline: makeBaseline(),
      requirements: {
        ...makeArtifact({
          id: 'req-1',
          title: 'Requirements',
          content_hash: 'req-hash-1',
          data: { system: { name: 'Revenue Ops Assistant' } },
        }),
        role: 'primary',
      },
      scenarios: [
        makeArtifact({
          id: 'scn-1',
          title: 'Primary Scenario',
          data: { scenario: { name: 'Review pipeline risk' } },
        }),
      ],
      shape: makeShape(),
      pmArtifacts,
      existing: null,
    })

    expect(definition.service_topology_bindings[0].implementation_notes).toContain('Accepted assistant guidance:')
    expect(definition.actor_expectations[0].summary_formalization).toBe('Reviews governed revenue answers.')
    expect(definition.actor_expectations[0].approval_formalization).toBe('Approves high-impact writes.')
    expect(definition.backend_bindings.data_access_target_label).toContain('Read governed pipeline data from the internal metrics API.')
    expect(definition.backend_bindings.application_integration_system_name).toContain('RevenueOps control-plane service')
    expect(definition.application_integration_governance.clarification_rules[0].prompt_hint).toContain('Clarify ambiguous records before returning an answer.')
    expect(definition.application_integration_governance.approval_rules[0].summary).toContain('Stop for approval before any high-impact write')
    expect(definition.verification.supported_question_family_bindings[0].verification_strategy).toContain('Use scenario review evidence for each supported question family.')
    expect(definition.verification.business_goal_bindings[0].verification_strategy).toContain('Tie business-goal verification to bounded-answer correctness')
    expect(definition.verification.non_goal_guards[0].guard_strategy).toContain('Verify that no high-impact change executes without approval.')
    expect(definition.verification.success_criteria_checks[0].verification_strategy).toContain('Review PM-visible evidence')

    const summary = summarizeAssistantSeededFields(definition, pmArtifacts)
    expect(summary.service_identity_topology.count).toBeGreaterThan(0)
    expect(summary.authority_and_approval.count).toBeGreaterThan(0)
    expect(summary.backend_bindings.count).toBeGreaterThan(0)
    expect(summary.audit_and_lineage.count).toBeGreaterThan(0)

    expect(clearAssistantSeededFieldsForSection(definition, pmArtifacts, 'service_identity_topology')).toBe(true)
    expect(definition.service_topology_bindings[0].implementation_notes).toBe('')
  })

  it('derives a complete Developer Definition from saved Product Design seed artifacts without assistant-only patches', () => {
    const pmArtifacts: ArtifactRecord[] = [
      makeArtifact({
        id: 'summary-1',
        title: 'Business Summary',
        data: {
          artifact_type: 'product_summary',
          product_purpose: 'Help operators answer governed revenue questions.',
          business_problem: 'Operators rely on manual interpretation and hidden escalation paths.',
          business_goals: ['Answer recurring revenue questions with bounded results.'],
          supported_question_families: ['Risk and health review'],
          governed_behavior_summary: 'Return bounded answers, clarify missing inputs, and stop at approval boundaries.',
          approval_posture_summary: 'High-impact writes must stop for approval.',
          multi_step_composition_rules: ['Only compose steps when each stop condition remains explicit.'],
          why_now: 'Teams need a governed operating model now.',
          success_outcome_summary: 'Users can act faster without losing governed boundaries.',
        },
      }),
      makeArtifact({
        id: 'actors-1',
        title: 'Actor Model',
        data: {
          artifact_type: 'actor_model',
          actors: [
            {
              actor_id: 'ops_manager',
              title: 'Ops Manager',
              summary: 'Reviews governed revenue answers.',
              visibility_expectations: 'Can see bounded operational summaries.',
              action_expectations: 'Can request governed next steps.',
              approval_expectations: 'Approves high-impact writes.',
            },
          ],
        },
      }),
      makeArtifact({
        id: 'areas-1',
        title: 'Business Areas',
        data: {
          artifact_type: 'business_areas',
          entries: [{ business_area_id: 'pipeline', label: 'Pipeline', description: 'Governed pipeline review.' }],
        },
      }),
      makeArtifact({
        id: 'permissions-1',
        title: 'Permission Intent',
        data: {
          artifact_type: 'permission_intent',
          policy_summary: 'Preserve actor-aware visibility and approval stops.',
          rules: [
            {
              actor_id: 'ops_manager',
              business_area: 'pipeline',
              access_posture: 'approval_required',
              governed_outcome_type: 'approval_stop',
              governed_outcome: 'Prepare the recommendation and stop for explicit approval.',
              notes: 'Approval state must remain auditable.',
            },
          ],
        },
      }),
      makeArtifact({
        id: 'non-goals-1',
        title: 'Non-Goals',
        data: {
          artifact_type: 'non_goals',
          entries: [{
            statement: 'Do not execute high-impact changes automatically.',
            rationale: 'Approval boundaries must remain explicit.',
          }],
        },
      }),
      makeArtifact({
        id: 'success-1',
        title: 'Success Criteria',
        data: {
          artifact_type: 'success_criteria',
          entries: [{
            statement: 'Users get bounded answers quickly.',
            evidence: 'Scenario review confirms governed answers are usable.',
            priority: 'high',
            review_method: 'PM signoff',
          }],
        },
      }),
    ]

    const definition = buildDeveloperDefinitionData({
      project: makeProject(),
      baseline: makeBaseline(),
      requirements: {
        ...makeArtifact({
          id: 'req-1',
          title: 'Requirements',
          content_hash: 'req-hash-1',
          data: { system: { name: 'Revenue Ops Assistant' } },
        }),
        role: 'primary',
      },
      scenarios: [
        makeArtifact({
          id: 'scn-1',
          title: 'Primary Scenario',
          data: {
            scenario: {
              name: 'Review pipeline risk',
              expected_behavior: ['Return a bounded answer.'],
              expected_anip_support: ['clarification', 'approval_stop'],
              orchestration_steps: ['Pipeline executes gtm.pipeline_summary and returns a bounded governed result.'],
            },
          },
        }),
      ],
      shape: makeShape(),
      pmArtifacts,
      existing: null,
    })

    expect(validateDeveloperDefinitionRequiredFields(definition)).toEqual([])
    expect(definition.actor_expectations[0].summary_formalization).toBe('Reviews governed revenue answers.')
    expect(definition.permission_intent_bindings[0].formalization_strategy).toContain('approval_stop')
    expect(definition.composition_rules[0].formalization_strategy).toContain('Preserve this product-wide composition rule')
  })

  it('does not promote unresolved multi-service orchestration prose into required service-owned steps', () => {
    const shape: ShapeRecord = {
      ...makeShape(),
      data: {
        shape: {
          services: [
            {
              id: 'gtm-pipeline-service',
              name: 'GTM Pipeline Service',
              role: 'Reviews pipeline risk.',
              capabilities: ['gtm.account_risk_summary'],
            },
            {
              id: 'gtm-enrichment-service',
              name: 'GTM Enrichment Service',
              role: 'Enriches explicit account cohorts.',
              capabilities: ['gtm.account_enrichment_summary'],
            },
          ],
          coordination: [],
          domain_concepts: [],
        },
      },
    }

    const definition = buildDeveloperDefinitionData({
      project: makeProject(),
      baseline: makeBaseline(),
      requirements: {
        ...makeArtifact({
          id: 'req-1',
          title: 'Requirements',
          content_hash: 'req-hash-1',
          data: { system: { name: 'Revenue Ops Assistant' } },
        }),
        role: 'primary',
      },
      scenarios: [
        makeArtifact({
          id: 'scn-1',
          title: 'Cross-service review',
          data: {
            scenario: {
              name: 'cross_service_review',
              category: 'cross_service',
              expected_behavior: ['Keep service boundaries explicit.'],
              expected_anip_support: ['service handoff lineage'],
              participating_services: ['gtm-pipeline-service', 'gtm-enrichment-service'],
              orchestration_steps: [
                'User requests a bounded review of at-risk accounts for a quarter.',
                'Relevant service checks the request against its declared allowed surface.',
              ],
            },
          },
        }),
      ],
      shape,
      pmArtifacts: [],
      existing: null,
    })

    expect(definition.scenario_formalizations[0].orchestration_steps).toEqual([])
    expect(validateDeveloperDefinitionRequiredFields(definition).map((issue) => issue.message)).not.toContain(
      'Cross-service review Step 1 Service is required.',
    )
  })

  it('requires review when a declared service boundary has responsibilities but no canonical capabilities', () => {
    const shape: ShapeRecord = {
      ...makeShape(),
      data: {
        shape: {
          services: [
            {
              id: 'gtm-enrichment-service',
              name: 'GTM Enrichment Service',
              role: 'Enriches explicit account cohorts.',
              capabilities: [],
              responsibilities: ['Summarize firmographic and fit context for selected accounts.'],
            },
          ],
          coordination: [],
          domain_concepts: [],
        },
      },
    }
    const report = buildHighRiskConfirmationReport({
      project: makeProject(),
      pmArtifacts: [],
      documents: [],
      requirements: [],
      scenarios: [],
      shapes: [shape],
      existing: null,
    })

    expect(report.items).toEqual(expect.arrayContaining([
      expect.objectContaining({
        id: 'service-ownership:services-without-capabilities',
        severity: 'blocker',
      }),
    ]))
  })

  it('does not require composed-capability review for source-declared capability inventories', () => {
    const shape: ShapeRecord = {
      ...makeShape(),
      data: {
        shape: {
          notes: ['Preserve source-declared canonical capability inventory.'],
          services: [
            {
              id: 'gtm-pipeline-service',
              name: 'GTM Pipeline Service',
              role: 'Owns bounded pipeline reads and approval-gated preparation.',
              capabilities: [
                'gtm.account_risk_summary',
                'gtm.prepare_followup_tasks',
                'gtm.at_risk_followup_preparation',
              ],
            },
          ],
          coordination: [],
          domain_concepts: [],
        },
      },
    }
    const definition = buildDeveloperDefinitionData({
      project: makeProject(),
      baseline: makeBaseline(),
      requirements: {
        ...makeArtifact({
          id: 'req-1',
          title: 'Requirements',
          content_hash: 'req-hash-1',
          data: { system: { name: 'Revenue Ops Assistant' } },
        }),
        role: 'primary',
      },
      scenarios: [],
      shape,
      pmArtifacts: [],
      existing: null,
    })
    const report = buildHighRiskConfirmationReport({
      project: makeProject(),
      pmArtifacts: [
        makeArtifact({
          id: 'dev-def',
          title: 'Developer Definition',
          data: definition,
        }),
      ],
      documents: [],
      requirements: [],
      scenarios: [],
      shapes: [shape],
      existing: null,
    })

    expect(report.items.find((item) => item.id.startsWith('composition-ambiguity:'))).toBeUndefined()
  })

  it('treats explicit service capability ids as authoritative source inventory', () => {
    const shape: ShapeRecord = {
      ...makeShape(),
      data: {
        shape: {
          notes: ['Service topology was constrained by explicit topology preference or preserved source service boundaries.'],
          services: [
            {
              id: 'gtm-pipeline-service',
              name: 'GTM Pipeline Service',
              capabilities: [
                'gtm.pipeline_summary',
                'gtm.prepare_reassignment_plan',
              ],
            },
          ],
        },
      },
    }

    expect(shapeDeclaresSourceCapabilityInventory(shape)).toBe(true)
  })

  it('uses reviewed Developer Definition capability IDs instead of weak shape candidates for high-risk identity review', () => {
    const shape: ShapeRecord = {
      ...makeShape(),
      data: {
        shape: {
          services: [
            {
              id: 'gtm-pipeline-service',
              name: 'GTM Pipeline Service',
              role: 'Reviews governed pipeline questions.',
              capabilities: [
                'handle_primary_action',
                'a-revenue-ops-user-uploads-source-documents-and-reviews-ranked-opportunities',
              ],
            },
          ],
        },
      },
    }
    const report = buildHighRiskConfirmationReport({
      project: makeProject(),
      pmArtifacts: [
        makeArtifact({
          id: 'dev-def',
          title: 'Developer Definition',
          data: {
            artifact_type: 'developer_definition',
            capability_formalizations: [
              {
                capability_id: 'gtm.pipeline_summary',
                title: 'Pipeline Summary',
                service_id: 'gtm-pipeline-service',
                kind: 'atomic',
                subject_kind: 'pipeline',
                context_type: 'quarter',
                output_intent: 'Return bounded pipeline summary.',
                output_shape: 'summary',
                operation_type: 'read',
                side_effect_level: 'read',
                business_effects: {
                  produces: ['content.summary'],
                  does_not_produce: ['raw_data_export'],
                },
                inputs: [],
              },
              {
                capability_id: 'gtm.account_risk_summary',
                title: 'Account Risk Summary',
                service_id: 'gtm-pipeline-service',
                kind: 'atomic',
                subject_kind: 'account',
                context_type: 'quarter',
                output_intent: 'Return bounded account risk summary.',
                output_shape: 'summary',
                operation_type: 'read',
                side_effect_level: 'read',
                business_effects: {
                  produces: ['content.summary'],
                  does_not_produce: ['raw_data_export'],
                },
                inputs: [],
              },
            ],
          },
        }),
      ],
      documents: [],
      requirements: [],
      scenarios: [],
      shapes: [shape],
      existing: null,
    })

    const identityItem = report.items.find((item) => item.id === 'capability-identity:canonical-ids')
    expect(identityItem?.detail).toContain('2 capability ids')
    expect(identityItem?.detail).not.toContain('handle_primary_action')
    expect(identityItem?.related_ids).toEqual([
      'gtm.pipeline_summary',
      'gtm.account_risk_summary',
    ])
  })

  it('materializes contract-level composed capabilities from scenario orchestration and service coordination', () => {
    const pmArtifacts: ArtifactRecord[] = [
      makeArtifact({
        id: 'summary-1',
        title: 'Business Summary',
        data: {
          artifact_type: 'product_summary',
          product_purpose: 'Help operators compose governed account risk and enrichment context.',
          business_problem: 'Cross-service behavior is currently hidden in glue code.',
          business_goals: ['Make account risk enrichment explicit.'],
          supported_question_families: ['At-risk account enrichment'],
          governed_behavior_summary: 'Compose bounded account risk and enrichment only through explicit service boundaries.',
          approval_posture_summary: 'Reads are allowed when scoped.',
          multi_step_composition_rules: ['Compose pipeline review and enrichment only through explicit service boundaries.'],
          why_now: 'The behavior should be protocol-visible.',
          success_outcome_summary: 'The generated definition exposes composed business capability metadata.',
        },
      }),
    ]
    const shape: ShapeRecord = {
      ...makeShape(),
      data: {
        shape: {
          services: [
            {
              id: 'gtm-pipeline-service',
              name: 'GTM Pipeline Service',
              role: 'Ranks at-risk accounts with evidence.',
              capabilities: ['gtm.account_risk_summary'],
            },
            {
              id: 'gtm-enrichment-service',
              name: 'GTM Enrichment Service',
              role: 'Returns bounded enrichment context for approved account scope.',
              capabilities: ['gtm.account_enrichment_summary'],
            },
          ],
          coordination: [
            {
              from: 'gtm-pipeline-service',
              to: 'gtm-enrichment-service',
              relationship: 'account_scope_handoff',
              description: 'Pipeline risk outputs pass bounded account identifiers into enrichment while preserving lineage.',
            },
          ],
          capability_contracts: [
            {
              id: 'gtm.account_risk_summary',
              purpose: 'Rank at-risk accounts with explicit evidence for why they need attention.',
              source_kind: 'custom_code_bundle',
              contract_complete: true,
              side_effect_type: 'read',
              approval_required_when: [],
              business_effects: {
                produces: ['content.summary'],
                does_not_produce: ['raw_data_export'],
              },
              inputs: [
                { name: 'quarter', type: 'string', required: true, description: 'Quarter label.' },
              ],
            },
            {
              id: 'gtm.account_enrichment_summary',
              purpose: 'Return bounded firmographic and account context for selected accounts.',
              source_kind: 'custom_code_bundle',
              contract_complete: true,
              side_effect_type: 'read',
              approval_required_when: [],
              business_effects: {
                produces: ['content.summary'],
                does_not_produce: ['raw_data_export'],
              },
              inputs: [
                { name: 'account_ref', type: 'string', required: true, description: 'Selected account reference.' },
              ],
            },
          ],
        },
      },
    }

    const definition = buildDeveloperDefinitionData({
      project: makeProject(),
      baseline: makeBaseline(),
      requirements: {
        ...makeArtifact({
          id: 'req-1',
          title: 'Requirements',
          content_hash: 'req-hash-1',
          data: { system: { name: 'Revenue Ops Assistant' } },
        }),
        role: 'primary',
      },
      scenarios: [
        makeArtifact({
          id: 'scn-risk-enrichment',
          title: 'At-risk account enrichment',
          data: {
            scenario: {
              name: 'at_risk_account_enrichment_summary',
              category: 'orchestration',
              narrative: 'Show enrichment context for the top at-risk accounts in the current pipeline review.',
              expected_behavior: ['risk evidence is bounded', 'enrichment context is bounded'],
              expected_anip_support: ['service handoff lineage'],
            },
          },
        }),
      ],
      shape,
      pmArtifacts,
      existing: null,
    })

    const composed = definition.capability_formalizations.find((capability) => capability.capability_id === 'gtm.at_risk_account_enrichment_summary')
    expect(composed).toBeUndefined()
    expect(validateDeveloperDefinitionRequiredFields(definition)).toEqual([])
  })

  it('uses explicit source-declared effects instead of inferring side effects from labels alone', () => {
    const shape: ShapeRecord = {
      ...makeShape(),
      data: {
        shape: {
          services: [
            {
              id: 'gtm-enrichment-service',
              name: 'GTM Enrichment Service',
              role: 'Explain account fit and enrichment evidence.',
              capabilities: ['gtm.account_fit_explanation'],
              owns_concepts: ['account'],
            },
            {
              id: 'gtm-prioritization-service',
              name: 'GTM Prioritization Service',
              role: 'Prepare governed routing recommendations.',
              capabilities: ['gtm.prepare_routing_recommendation'],
              owns_concepts: ['routing'],
            },
          ],
          coordination: [],
          domain_concepts: [],
          capability_contracts: [
            {
              id: 'gtm.account_fit_explanation',
              purpose: 'Explain why a named account fits the ideal customer profile using bounded evidence.',
              source_kind: 'custom_code_bundle',
              contract_complete: true,
              side_effect_type: 'read',
              approval_required_when: [],
              business_effects: {
                produces: ['content.summary'],
                does_not_produce: ['raw_data_export'],
              },
              inputs: [
                { name: 'account_ref', type: 'string', required: true, description: 'Named account reference.' },
              ],
            },
            {
              id: 'gtm.prepare_routing_recommendation',
              purpose: 'Prepare a preview-only routing recommendation that requires approval before any external assignment changes.',
              source_kind: 'custom_code_bundle',
              contract_complete: true,
              side_effect_type: 'approval_required',
              approval_required_when: ['Before any external assignment change is applied.'],
              grant_policy: testApprovalGrantPolicy(),
              business_effects: {
                produces: ['approval.request', 'system.preview_mutation'],
                does_not_produce: ['approval.execute'],
              },
              inputs: [
                { name: 'cohort_ref', type: 'string', required: true, description: 'Selected cohort reference.' },
              ],
            },
          ],
        },
      },
    }

    const definition = buildDeveloperDefinitionData({
      project: makeProject(),
      baseline: makeBaseline(),
      requirements: {
        ...makeArtifact({
          id: 'req-1',
          title: 'Requirements',
          content_hash: 'req-hash-1',
          data: { system: { name: 'GTM Assistant' } },
        }),
        role: 'primary',
      },
      scenarios: [],
      shape,
      pmArtifacts: [],
      existing: null,
    })

    const explanation = definition.capability_formalizations.find((capability) => capability.capability_id === 'gtm.account_fit_explanation')
    expect(explanation?.side_effect_level).toBe('read')
    expect(explanation?.operation_type).toBe('read')
    expect(explanation?.grant_policy).toBeNull()
    expect(explanation?.business_effects?.produces).toContain('content.summary')
    expect(explanation?.business_effects?.produces).not.toContain('approval.request')

    const routing = definition.capability_formalizations.find((capability) => capability.capability_id === 'gtm.prepare_routing_recommendation')
    expect(routing?.side_effect_level).toBe('approval_required')
    expect(routing?.operation_type).toBe('approval_gated')
    expect(routing?.grant_policy).not.toBeNull()
    expect(routing?.business_effects?.produces).toContain('approval.request')
    expect(routing?.business_effects?.produces).toContain('system.preview_mutation')
    expect(routing?.business_effects?.does_not_produce).toContain('approval.execute')
  })

  it('treats prepare-without-execution capabilities as approval-preview boundaries', () => {
    const shape: ShapeRecord = {
      ...makeShape(),
      data: {
        shape: {
          services: [
            {
              id: 'pipeline-service',
              name: 'Pipeline Service',
              role: 'pipeline',
              capabilities: ['gtm.prepare_followup_tasks'],
              owns_concepts: [],
            },
          ],
          coordination: [],
          domain_concepts: [],
          capability_contracts: [
            {
              id: 'gtm.prepare_followup_tasks',
              purpose: 'Prepare follow-up tasks for high-risk accounts without executing downstream mutations.',
              source_kind: 'custom_code_bundle',
              contract_complete: true,
              side_effect_type: 'approval_required',
              approval_required_when: ['Before tasks are created in a downstream system.'],
              grant_policy: testApprovalGrantPolicy(),
              business_effects: {
                produces: ['approval.request', 'system.preview_mutation'],
                does_not_produce: ['approval.execute'],
              },
              inputs: [
                { name: 'account_ref', type: 'string', required: true, description: 'Selected account reference.' },
              ],
            },
          ],
        },
      },
    }

    const definition = buildDeveloperDefinitionData({
      project: makeProject(),
      baseline: makeBaseline(),
      requirements: {
        ...makeArtifact({
          id: 'req-1',
          title: 'Requirements',
          content_hash: 'req-hash-1',
          data: { system: { name: 'GTM Assistant' } },
        }),
        role: 'primary',
      },
      scenarios: [],
      shape,
      pmArtifacts: [],
      existing: null,
    })

    const capability = definition.capability_formalizations.find((item) => item.capability_id === 'gtm.prepare_followup_tasks')
    expect(capability?.side_effect_level).toBe('approval_required')
    expect(capability?.operation_type).toBe('approval_gated')
    expect(capability?.grant_policy).toBeTruthy()
    expect(capability?.business_effects?.produces).toContain('approval.request')
    expect(capability?.business_effects?.produces).toContain('system.preview_mutation')
    expect(capability?.business_effects?.does_not_produce).toContain('approval.execute')
  })

  it('exports accepted integration-fronting mappings into generic Developer Definition capabilities', () => {
    const pmArtifacts: ArtifactRecord[] = [
      makeArtifact({
        id: 'issue-tracker-mapping-1',
        title: 'Prepare Issue Ticket',
        data: {
          artifact_type: INTEGRATION_FRONTING_MAPPING_ARTIFACT_TYPE,
          id: 'issue-tracker-mapping-1',
          capability_id: 'issue_tracker.prepare_ticket',
          title: 'Prepare Issue Ticket',
          intent: 'Draft a governed issue tracker ticket.',
          service_id: 'issue-tracker-governance-service',
          service_name: 'Issue Tracker Governance Service',
          backend_kind: 'hybrid',
          connection_ref: 'conn-issue-rest-prod',
          raw_operation_refs: ['issue_rest.create_issue'],
          backend_bindings: [
            {
              backend_kind: 'native_api',
              connection_ref: 'conn-issue-rest-prod',
              raw_operation_refs: ['issue_rest.create_issue'],
            },
            {
              backend_kind: 'mcp',
              connection_ref: 'conn-issue-mcp-prod',
              raw_operation_refs: ['issue_mcp.create_issue'],
            },
          ],
          execution_posture: 'prepare_only',
          side_effect_level: 'write_adjacent',
          subject_kind: 'issue',
          context_type: 'incident_or_defect_summary',
          output_intent: 'approval_ready_ticket_draft',
          required_inputs: ['project_key', 'summary', 'severity'],
          optional_inputs: ['labels'],
          inputs: [
            {
              input_name: 'severity',
              input_type: 'string',
              required: true,
              summary: 'Reviewed severity level from the starter template.',
              allowed_values: ['sev1', 'sev2', 'sev3'],
              semantic_type: 'incident_severity',
              resolution: {
                mode: 'closed_values',
                on_missing: 'clarify',
                on_unresolved: 'deny',
              },
            },
          ],
          backend_input_mode: 'hybrid',
          derived_required_backend_inputs: ['project', 'project_key', 'summary', 'description', 'issue_type', 'issuetype'],
          derived_optional_backend_inputs: ['labels', 'assignee'],
          explicit_required_backend_inputs: ['project_key', 'issue_type', 'summary'],
          explicit_optional_backend_inputs: ['labels'],
          approval_rule_refs: ['approval.sev2_or_customer_impact'],
          denial_rule_refs: ['deny.unsupported_project'],
          clarification_rule_refs: ['clarify.missing_reproduction'],
          audit_required: true,
        },
      }),
    ]

    const definition = buildDeveloperDefinitionData({
      project: makeProject({
        project_type: 'governed_service_project',
        integration_profile: {
          kind: 'hybrid',
          systems: [
            {
              system_id: 'issue-rest',
              backend_kind: 'native_api',
              auth_mode: 'service_delegated',
              connection_ref: 'conn-issue-rest-prod',
            },
            {
              system_id: 'issue-mcp',
              backend_kind: 'mcp',
              auth_mode: 'user_delegated',
              connection_ref: 'conn-issue-mcp-prod',
            },
          ],
        },
      }),
      baseline: makeBaseline(),
      requirements: {
        ...makeArtifact({
          id: 'req-1',
          title: 'Requirements',
          content_hash: 'req-hash-1',
          data: { system: { name: 'Issue Tracker Governance' } },
        }),
        role: 'primary',
      },
      scenarios: [],
      shape: null,
      pmArtifacts,
      existing: null,
    })

    expect(definition.integration_fronting?.project_type).toBe('governed_service_project')
    expect(definition.integration_fronting?.integration_profile.kind).toBe('hybrid')
    expect(definition.integration_fronting?.capability_mappings[0].connection_ref).toBe('conn-issue-rest-prod')
    expect(definition.integration_fronting?.capability_mappings[0].backend_input_mode).toBe('hybrid')
    expect(definition.integration_fronting?.capability_mappings[0].derived_required_backend_inputs).toEqual([
      'project',
      'project_key',
      'summary',
      'description',
      'issue_type',
      'issuetype',
    ])
    expect(definition.integration_fronting?.capability_mappings[0].explicit_required_backend_inputs).toEqual([
      'project_key',
      'issue_type',
      'summary',
    ])
    expect(definition.integration_fronting?.capability_mappings[0].backend_bindings).toEqual([
      expect.objectContaining({
        backend_kind: 'native_api',
        connection_ref: 'conn-issue-rest-prod',
        raw_operation_refs: ['issue_rest.create_issue'],
      }),
      expect.objectContaining({
        backend_kind: 'mcp',
        connection_ref: 'conn-issue-mcp-prod',
        raw_operation_refs: ['issue_mcp.create_issue'],
      }),
    ])
    expect(developerDefinitionTargetStatus('developer_definition.integration_fronting:issue_tracker.prepare_ticket', {
      developerDefinition: definition,
    })).toBe('addressed')

    const capability = definition.capability_formalizations.find((item) => item.capability_id === 'issue_tracker.prepare_ticket')
    expect(capability?.service_id).toBe('issue-tracker-governance-service')
    expect(capability?.backend_operation).toBe('issue_rest.create_issue')
    expect(capability?.subject_kind).toBe('issue')
    expect(capability?.output_intent).toBe('approval_ready_ticket_draft')
    expect(capability?.inputs.map((input) => [input.input_name, input.required])).toEqual([
      ['project_key', true],
      ['summary', true],
      ['severity', true],
      ['labels', false],
    ])
    expect(capability?.inputs.find((input) => input.input_name === 'project_key')).toEqual(expect.objectContaining({
      semantic_type: 'scope_reference',
      clarification_hint: expect.stringContaining('which Project Key'),
      entity_reference: true,
    }))
    expect(capability?.inputs.find((input) => input.input_name === 'severity')).toEqual(expect.objectContaining({
      semantic_type: 'incident_severity',
      summary: 'Reviewed severity level from the starter template.',
      allowed_values: ['sev1', 'sev2', 'sev3'],
      resolution: expect.objectContaining({
        mode: 'closed_values',
        on_missing: 'clarify',
        on_unresolved: 'deny',
      }),
    }))
    expect(definition.verification.supported_question_family_bindings[0]).toEqual(expect.objectContaining({
      question_family: expect.stringContaining('Governed Issue Tracker Governance Service requests'),
      target_service_ids: ['issue-tracker-governance-service'],
    }))

    const adapterBindings = buildIntegrationAdapterBindings(definition)
    expect(adapterBindings).toEqual([
      expect.objectContaining({
        capability_id: 'issue_tracker.prepare_ticket',
        backend_kind: 'native_api',
        connection_ref: 'conn-issue-rest-prod',
        raw_operation_refs: ['issue_rest.create_issue'],
        backend_input_mode: 'hybrid',
        derived_required_backend_inputs: ['project', 'project_key', 'summary', 'description', 'issue_type', 'issuetype'],
        derived_optional_backend_inputs: ['labels', 'assignee'],
        explicit_required_backend_inputs: ['project_key', 'issue_type', 'summary'],
        explicit_optional_backend_inputs: ['labels'],
        backend_bindings: [
          expect.objectContaining({
            backend_kind: 'native_api',
            connection_ref: 'conn-issue-rest-prod',
            raw_operation_refs: ['issue_rest.create_issue'],
          }),
          expect.objectContaining({
            backend_kind: 'mcp',
            connection_ref: 'conn-issue-mcp-prod',
            raw_operation_refs: ['issue_mcp.create_issue'],
          }),
        ],
        governance: expect.objectContaining({
          approval_rule_refs: ['approval.sev2_or_customer_impact'],
          denial_rule_refs: ['deny.unsupported_project'],
          clarification_rule_refs: ['clarify.missing_reproduction'],
          audit_required: true,
        }),
      }),
    ])
    const scaffoldModule = buildIntegrationAdapterScaffoldModuleContent('issue-tracker-governance-service', adapterBindings)
    expect(scaffoldModule).toContain("mode: 'implicit' | 'hybrid' | 'explicit'")
    expect(scaffoldModule).toContain('function effectiveBackendInputContract')
    expect(scaffoldModule).toContain('function buildBackendInvocationPlan')
    expect(scaffoldModule).toContain('const mode = selectedBinding.backend_input_mode || binding.backend_input_mode')
    expect(scaffoldModule).toContain('Backend adapter enrichment required for ${capabilityId}')
    expect(scaffoldModule).toContain('using ${plan.backend_input_contract.mode} backend input mode')

    definition.compiled_contract_identity = {
      artifact_name: 'anip-service-definition.json',
      canonical_format: 'stable-json-v1',
      signature_algorithm: 'sha256',
      signature: 'contract-signature',
      generated_at: '2026-04-21T00:00:00Z',
    }
    const runtimeTarget = buildGeneratedRuntimeTarget(definition)
    expect(runtimeTarget.services[0]?.service_id).toBe('issue-tracker-governance-service')
    expect(runtimeTarget.services[0]?.backend_bindings).toContain('native_api:conn-issue-rest-prod')
    expect(runtimeTarget.services[0]?.backend_bindings).toContain('mcp:conn-issue-mcp-prod')
    expect(runtimeTarget.services[0]?.capabilities.map((item) => item.capability_id)).toContain('issue_tracker.prepare_ticket')

    const traceability = buildTraceabilityRecord({
      pmArtifacts,
      requirements: null,
      scenarios: [],
      shape: null,
    })
    expect(traceability.coverage).toEqual(expect.arrayContaining([
      expect.objectContaining({
        source: 'integration_fronting',
        mapping_target_key: 'developer_definition.integration_fronting:issue_tracker.prepare_ticket',
        status: 'addressed',
      }),
    ]))

    const conformanceReport = buildLocalConformanceReport({
      definition,
      runtimeTarget,
      extensionManifest: [{
        id: 'application-integration-backend-adapter',
        label: 'Application Integration Backend Adapter',
        ownership: 'generated_with_extension',
        plugin_surface: 'backend_adapter_scaffold',
        rationale: 'Adapter scaffold.',
      }],
      generatedOutputKinds: ['runtime_target_manifest', 'integration_adapter_bindings', 'backend_selection_template', 'integration_adapter_scaffold'],
      generatedAt: '2026-04-21T00:00:00Z',
    })
    expect(conformanceReport.summary.status).toBe('passed')
    expect(conformanceReport.checks.map((check) => [check.id, check.status])).toContainEqual([
      'integration_adapter_bindings',
      'passed',
    ])
    expect(conformanceReport.checks.map((check) => [check.id, check.status])).toContainEqual([
      'backend_selection_template',
      'passed',
    ])

    const missingSelectionTemplateReport = buildLocalConformanceReport({
      definition,
      runtimeTarget,
      extensionManifest: [{
        id: 'application-integration-backend-adapter',
        label: 'Application Integration Backend Adapter',
        ownership: 'generated_with_extension',
        plugin_surface: 'backend_adapter_scaffold',
        rationale: 'Adapter scaffold.',
      }],
      generatedOutputKinds: ['runtime_target_manifest', 'integration_adapter_bindings', 'integration_adapter_scaffold'],
      generatedAt: '2026-04-21T00:00:00Z',
    })
    expect(missingSelectionTemplateReport.summary.status).toBe('failed')
    expect(missingSelectionTemplateReport.checks.map((check) => [check.id, check.status])).toContainEqual([
      'backend_selection_template',
      'failed',
    ])
  })

  it('marks fronting backend bindings stale when discovery metadata changes', () => {
    const binding: DeveloperIntegrationFrontingBackendBinding = {
      backend_kind: 'native_api',
      connection_ref: 'conn-issue-rest-prod',
      raw_operation_refs: ['issue_rest.create_issue'],
      backend_input_mode: 'implicit',
      derived_required_backend_inputs: ['project', 'summary'],
      derived_optional_backend_inputs: ['labels'],
      matched_discovery_record_ids: ['discovery-1'],
    }
    const discoveryRecords: IntegrationDiscoveryRecord[] = [
      {
        id: 'discovery-1',
        project_id: 'proj-1',
        connection_id: 'conn-issue-rest-prod',
        operation_id: 'issue_rest.create_issue',
        backend_kind: 'native_api',
        method: 'POST',
        path_template: '/issues',
        side_effect_level: 'write',
        input_schema_summary: {
          required: ['project', 'summary', 'issue_type'],
          optional: ['labels'],
        },
        risk_notes: [],
        data: {},
        content_hash: 'hash-1',
        created_at: '2026-04-23T00:00:00Z',
        updated_at: '2026-04-23T00:00:00Z',
      },
    ]

    const health = resolveIntegrationFrontingBackendBindingHealth(binding, discoveryRecords)
    expect(health.status).toBe('stale')
    expect(health.derived_required_backend_inputs).toEqual(['project', 'summary', 'issue_type'])
  })
})
