import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import {
  buildDeveloperDefinitionContract,
  buildDeveloperDefinitionData,
  developerDefinitionTargetStatus,
  findInferredCompositionAmbiguities,
  resolveIntegrationFrontingBackendBindingHealth,
  resolveIntegrationFrontingBackendBindingsHealth,
  sourceTextHasConcreteCapabilityInputEvidence,
  validateDeveloperDefinitionRequiredFields,
} from '../design/developer-definition'
import {
  applyInputContractEvidence,
  expectedCapabilityIdsFromShape,
  inputContractEvidenceCoverage,
  inputContractReviewedEvidenceCoverage,
  parseInputContractEvidence,
  parseInputContractEvidenceFromSourceText,
} from '../design/input-contract-evidence'
import type { DeveloperCapabilityFormalization, DeveloperDefinitionData } from '../design/project-types'

describe('developer definition validation', () => {
  function definitionWithCapabilities(capabilities: DeveloperCapabilityFormalization[]): DeveloperDefinitionData {
    return {
      product_alignment: {
        governed_behavior_formalization: 'Formalized.',
        approval_posture_formalization: 'Formalized.',
      },
      identity: {
        system_name: 'Composition Test',
        domain_name: 'demo',
        delivery_model: 'standalone_service',
        architecture_shape: 'single_service',
      },
      service_topology_bindings: [],
      service_backend_bindings: [],
      actor_expectations: [],
      permission_intent_bindings: [],
      data_domain: { domain_name: 'demo' },
      domain_concept_bindings: [],
      application_object_model: [],
      capability_formalizations: capabilities,
      scenario_formalizations: [],
      composition_rules: [],
      verification: {
        supported_question_family_bindings: [],
        business_goal_bindings: [],
        non_goal_guards: [],
        success_criteria_checks: [],
      },
      generation: {
        scalability_profile: 'single_service',
        codegen_adapter: 'generic',
        layout_strategy: 'service_topology',
        protocols: ['anip_http'],
        selected_service_ids: ['demo-service'],
      },
      naming: {
        namespace: 'demo',
        package_prefix: 'demo',
        service_name_prefix: 'demo',
      },
    } as unknown as DeveloperDefinitionData
  }

  it('imports reviewed input-contract evidence into capability formalizations', () => {
    const capabilities: DeveloperCapabilityFormalization[] = [
      {
        id: 'contract_native:gtm.pipeline_summary',
        source_kind: 'contract_native',
        service_id: 'gtm-pipeline-service',
        capability_id: 'gtm.pipeline_summary',
        title: 'Pipeline Summary',
        summary: 'Summarize pipeline health.',
        intent_type: 'business_action',
        operation_type: 'read',
        side_effect_level: 'read',
        backend_operation: 'gtm.pipeline_summary',
        path_template: '',
        output_shape: 'governed_result',
        inputs: [],
      },
    ]
    const evidence = parseInputContractEvidence(JSON.stringify({
      capabilities: [
        {
          capability_id: 'gtm.pipeline_summary',
          inputs: [
            {
              input_name: 'quarter',
              input_type: 'string',
              required: true,
              semantic_type: 'time_scope',
              resolution: {
                mode: 'clarify',
                on_missing: 'clarify',
              },
            },
          ],
        },
      ],
    }))

    const applied = applyInputContractEvidence(capabilities, evidence)

    expect(applied.matchedCapabilityIds).toEqual(['gtm.pipeline_summary'])
    expect(capabilities[0].inputs).toEqual([
      expect.objectContaining({
        input_name: 'quarter',
        input_type: 'string',
        required: true,
        semantic_type: 'time_scope',
        resolution: expect.objectContaining({
          mode: 'clarify',
          on_missing: 'clarify',
        }),
      }),
    ])
  })

  it('parses capability-id keyed input-contract evidence', () => {
    const evidence = parseInputContractEvidence(JSON.stringify({
      'gtm.pipeline_summary': {
        inputs: [
          {
            name: 'owner_scope',
            type: 'string',
            required: false,
            description: 'Optional visible owner scope.',
            resolution: {
              mode: 'actor_policy_or_explicit',
              on_missing: 'use_actor_scope',
            },
          },
        ],
      },
    }))

    expect(evidence.capabilities).toEqual([
      expect.objectContaining({
        capability_id: 'gtm.pipeline_summary',
        inputs: [
          expect.objectContaining({
            input_name: 'owner_scope',
            input_type: 'string',
            required: false,
            summary: 'Optional visible owner scope.',
            resolution: expect.objectContaining({
              mode: 'actor_policy_or_explicit',
              on_missing: 'use_actor_scope',
            }),
          }),
        ],
      }),
    ])
  })

  it('detects developer-owned canonical input contracts in source text', () => {
    const sourceText = [
      'Developer-owned implementation evidence.',
      '```json',
      JSON.stringify({
        canonical_capability_inventory: [
          {
            capability_id: 'gtm.pipeline_summary',
            inputs: [
              {
                input_name: 'quarter',
                input_type: 'string',
                required: true,
              },
            ],
          },
        ],
      }),
      '```',
    ].join('\n')

    expect(sourceTextHasConcreteCapabilityInputEvidence(sourceText)).toBe(true)
    expect(sourceTextHasConcreteCapabilityInputEvidence([
      '# Source 1: Runtime interface',
      'Kind: Developer interface',
      '',
      JSON.stringify({
        capability_formalizations: [
          {
            capability_id: 'gtm.pipeline_summary',
            inputs: [
              {
                input_name: 'quarter',
                input_type: 'string',
                required: true,
              },
            ],
          },
        ],
      }),
    ].join('\n'))).toBe(true)
    expect(sourceTextHasConcreteCapabilityInputEvidence('canonical_capability_inventory without parseable JSON')).toBe(false)
  })

  it('reports partial input-contract evidence against the locked service shape', () => {
    const shape = {
      id: 'shape-coverage',
      content_hash: 'shape-coverage-hash',
      requirements_id: 'requirements-coverage',
      project_id: 'project-coverage',
      title: 'Shape',
      status: 'active',
      created_at: '2026-05-26T00:00:00.000Z',
      updated_at: '2026-05-26T00:00:00.000Z',
      data: {
        shape: {
          services: [
            {
              id: 'pipeline',
              capabilities: ['gtm.pipeline_summary', 'gtm.account_risk_summary'],
            },
            {
              id: 'outreach',
              capabilities: ['gtm.draft_outreach_message'],
            },
          ],
        },
      },
    }
    const expectedCapabilityIds = expectedCapabilityIdsFromShape(shape)
    const coverage = inputContractEvidenceCoverage({
      expectedCapabilityIds,
      sourceText: [
        'Developer source evidence.',
        '```json',
        JSON.stringify({
          capabilities: [
            {
              capability_id: 'gtm.pipeline_summary',
              inputs: [{ input_name: 'quarter', input_type: 'string', required: true }],
            },
            {
              capability_id: 'gtm.account_risk_summary',
              inputs: [],
            },
            {
              capability_id: 'gtm.unknown',
              inputs: [{ input_name: 'account_ref', input_type: 'string' }],
            },
          ],
        }),
        '```',
      ].join('\n'),
    })

    expect(expectedCapabilityIds).toEqual([
      'gtm.account_risk_summary',
      'gtm.draft_outreach_message',
      'gtm.pipeline_summary',
    ])
    expect(coverage.coveredCapabilityIds).toEqual(['gtm.pipeline_summary'])
    expect(coverage.incompleteCapabilityIds).toEqual(['gtm.account_risk_summary'])
    expect(coverage.missingCapabilityIds).toEqual(['gtm.draft_outreach_message'])
    expect(coverage.unknownCapabilityIds).toEqual(['gtm.unknown'])
    expect(coverage.weakInputClassifications).toEqual([
      {
        capability_id: 'gtm.pipeline_summary',
        input_name: 'quarter',
        reason: 'Required input is missing semantic_type, entity_reference, allowed_values, input_format, validation_pattern, or clarification_hint.',
      },
    ])
  })

  it('flags source evidence that has inputs but lacks agent-safe required input classification', () => {
    const coverage = inputContractEvidenceCoverage({
      expectedCapabilityIds: ['jira.story.prepare', 'jira.workflow_transition.request'],
      sourceText: [
        'Developer source evidence.',
        '```json',
        JSON.stringify({
          capabilities: [
            {
              capability_id: 'jira.story.prepare',
              inputs: [
                { input_name: 'project_key', input_type: 'string', required: true, semantic_type: 'project_scope' },
                { input_name: 'summary', input_type: 'string', required: true },
              ],
            },
            {
              capability_id: 'jira.workflow_transition.request',
              inputs: [
                { input_name: 'issue_key', input_type: 'string', required: true, entity_reference: true },
                { input_name: 'reason', input_type: 'string', required: true },
              ],
            },
          ],
        }),
        '```',
      ].join('\n'),
    })

    expect(coverage.missingCapabilityIds).toEqual([])
    expect(coverage.incompleteCapabilityIds).toEqual([])
    expect(coverage.coveredCapabilityIds).toEqual(['jira.story.prepare', 'jira.workflow_transition.request'])
    expect(coverage.weakInputClassifications).toEqual([
      {
        capability_id: 'jira.story.prepare',
        input_name: 'summary',
        reason: 'Required input is missing semantic_type, entity_reference, allowed_values, input_format, validation_pattern, or clarification_hint.',
      },
      {
        capability_id: 'jira.workflow_transition.request',
        input_name: 'reason',
        reason: 'Required input is missing semantic_type, entity_reference, allowed_values, input_format, validation_pattern, or clarification_hint.',
      },
    ])
  })

  it('treats accepted Guided input-contract artifacts as reviewed evidence', () => {
    const expectedCapabilityIds = [
      'gtm.account_risk_summary',
      'gtm.draft_outreach_message',
      'gtm.pipeline_summary',
    ]
    const coverage = inputContractReviewedEvidenceCoverage({
      expectedCapabilityIds,
      sourceText: [
        'Developer source evidence.',
        '```json',
        JSON.stringify({
          capabilities: [
            {
              capability_id: 'gtm.pipeline_summary',
              inputs: [{ input_name: 'quarter', input_type: 'string', required: true }],
            },
          ],
        }),
        '```',
      ].join('\n'),
      pmArtifacts: [
        {
          id: 'artifact-input-contracts',
          project_id: 'project-guided',
          title: 'Accepted Input Contracts',
          created_at: '2026-05-26T00:00:00.000Z',
          updated_at: '2026-05-26T00:00:00.000Z',
          data: {
            artifact_type: 'assistant_input_contract_candidates',
            accepted_payload: [
              {
                client_id: 'input-contract-gtm-account-risk-summary',
                structured_data: {
                  capabilities: [
                    {
                      capability_id: 'gtm.account_risk_summary',
                      inputs: [{ input_name: 'account_ref', input_type: 'string', required: true }],
                    },
                  ],
                },
              },
              {
                client_id: 'input-contract-gtm-draft-outreach-message',
                structured_data: {
                  capabilities: [
                    {
                      capability_id: 'gtm.draft_outreach_message',
                      inputs: [{ input_name: 'target_ref', input_type: 'string', required: true }],
                    },
                  ],
                },
              },
            ],
          },
        } as any,
      ],
    })

    expect(coverage.coveredCapabilityIds).toEqual([...expectedCapabilityIds].sort())
    expect(coverage.missingCapabilityIds).toEqual([])
    expect(coverage.incompleteCapabilityIds).toEqual([])
    expect(coverage.weakInputClassifications.map((item) => `${item.capability_id}.${item.input_name}`)).toEqual([
      'gtm.account_risk_summary.account_ref',
      'gtm.draft_outreach_message.target_ref',
      'gtm.pipeline_summary.quarter',
    ])
  })

  it('treats imported fronting mapping input metadata as reviewed developer evidence', () => {
    const coverage = inputContractReviewedEvidenceCoverage({
      expectedCapabilityIds: ['jira.backlog.search_context', 'jira.story.prepare'],
      sourceText: '',
      pmArtifacts: [
        {
          id: 'mapping-search',
          project_id: 'jira-template-roundtrip',
          title: 'Search Backlog mapping',
          created_at: '2026-06-04T00:00:00.000Z',
          updated_at: '2026-06-04T00:00:00.000Z',
          data: {
            artifact_type: 'integration_fronting_capability_mapping',
            capability_id: 'jira.backlog.search_context',
            input_metadata: [
              {
                input_name: 'project_key',
                input_type: 'string',
                required: true,
                semantic_type: 'project_scope',
                resolution: { mode: 'backend_resolved', on_missing: 'clarify' },
              },
              {
                input_name: 'query',
                input_type: 'string',
                required: false,
                semantic_type: 'search_query',
                resolution: { mode: 'explicit_only', on_missing: 'omit' },
              },
            ],
          },
        },
        {
          id: 'mapping-story',
          project_id: 'jira-template-roundtrip',
          title: 'Prepare Story mapping',
          created_at: '2026-06-04T00:00:00.000Z',
          updated_at: '2026-06-04T00:00:00.000Z',
          data: {
            artifact_type: 'integration_fronting_capability_mapping',
            capability_id: 'jira.story.prepare',
            input_metadata: [
              {
                input_name: 'summary',
                input_type: 'string',
                required: true,
                clarification_hint: 'Ask for the story summary before preparing a preview.',
                resolution: { mode: 'clarify', on_missing: 'clarify' },
              },
            ],
          },
        },
      ] as any,
    })

    expect(coverage.coveredCapabilityIds).toEqual(['jira.backlog.search_context', 'jira.story.prepare'])
    expect(coverage.missingCapabilityIds).toEqual([])
    expect(coverage.incompleteCapabilityIds).toEqual([])
    expect(coverage.weakInputClassifications).toEqual([])
  })

  it('parses developer-owned Markdown input contract tables', () => {
    const evidence = parseInputContractEvidenceFromSourceText(`
## Capability: gtm.pipeline_summary

| input_name | input_type | required | semantic_type | resolution_mode | on_missing | summary |
| --- | --- | --- | --- | --- | --- | --- |
| quarter | string | yes | time_scope | clarify | clarify | Quarter label such as 2017-Q2. |
| owner_scope | string | no | scope_reference | actor_policy_or_explicit | use_actor_scope | Optional actor-visible owner scope. |

## Capability: gtm.draft_outreach_message

| name | type | required | entity_reference | resolution_mode | on_missing | clarification_hint |
| --- | --- | --- | --- | --- | --- | --- |
| account_ref | string | true | true | backend_resolved | clarify | Ask which account should receive outreach. |

## Capability: gtm.account_enrichment_summary

| input_name | input_type | required | semantic_type | entity_reference | resolution_mode | on_missing | on_ambiguous | on_unresolved | default_value | allowed_values | catalog_ref | summary | clarification_hint |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| account_names | string | yes | entity_reference | yes | backend_resolved | clarify | clarify | clarify |  |  | gtm.account_catalog | Comma-separated account names |  |
`)

    expect(evidence.capabilities).toEqual([
      expect.objectContaining({
        capability_id: 'gtm.pipeline_summary',
        inputs: [
          expect.objectContaining({
            input_name: 'quarter',
            input_type: 'string',
            required: true,
            semantic_type: 'time_scope',
            resolution: expect.objectContaining({
              mode: 'clarify',
              on_missing: 'clarify',
            }),
          }),
          expect.objectContaining({
            input_name: 'owner_scope',
            required: false,
            resolution: expect.objectContaining({
              mode: 'actor_policy_or_explicit',
              on_missing: 'use_actor_scope',
            }),
          }),
        ],
      }),
      expect.objectContaining({
        capability_id: 'gtm.draft_outreach_message',
        inputs: [
          expect.objectContaining({
            input_name: 'account_ref',
            entity_reference: true,
            clarification_hint: 'Ask which account should receive outreach.',
          }),
        ],
      }),
      expect.objectContaining({
        capability_id: 'gtm.account_enrichment_summary',
        inputs: [
          expect.objectContaining({
            input_name: 'account_names',
            default_value: '',
            allowed_values: [],
            catalog_ref: 'gtm.account_catalog',
            summary: 'Comma-separated account names',
          }),
        ],
      }),
    ])
  })

  it('parses the committed GTM runtime input-contract source with service-owned bottleneck target selection', () => {
    const source = readFileSync(
      resolve(process.cwd(), '../docs/examples/gtm-showcase/gtm-runtime-input-contracts.md'),
      'utf8',
    )

    const evidence = parseInputContractEvidenceFromSourceText(source)
    const capability = evidence.capabilities.find((item) =>
      item.capability_id === 'gtm.bottleneck_account_outreach_draft',
    )
    const targetRef = capability?.inputs.find((input) => input.input_name === 'target_ref')

    expect(evidence.capabilities).toHaveLength(23)
    expect(targetRef).toEqual(expect.objectContaining({
      required: false,
      catalog_ref: 'gtm.account_catalog',
      resolution: expect.objectContaining({
        mode: 'backend_resolved',
        resolver_ref: 'gtm.account_catalog',
        on_missing: 'omit',
      }),
    }))
  })

  it('parses developer-owned CSV input contract evidence', () => {
    const source = readFileSync(
      resolve(process.cwd(), '../docs/examples/gtm-showcase/anip-capability-input-contracts.csv'),
      'utf8',
    )

    const evidence = parseInputContractEvidenceFromSourceText(source)
    const expectedCapabilityIds = [
      'gtm.pipeline_summary',
      'gtm.account_risk_summary',
      'gtm.bottleneck_account_outreach_draft',
    ]
    const coverage = inputContractEvidenceCoverage({
      expectedCapabilityIds,
      sourceText: source,
    })
    const bottleneckDraft = evidence.capabilities.find((item) =>
      item.capability_id === 'gtm.bottleneck_account_outreach_draft',
    )
    const targetRef = bottleneckDraft?.inputs.find((input) => input.input_name === 'target_ref')

    expect(evidence.capabilities).toHaveLength(23)
    expect(coverage.coveredCapabilityIds).toEqual([...expectedCapabilityIds].sort())
    expect(targetRef).toEqual(expect.objectContaining({
      required: false,
      catalog_ref: 'gtm.account_catalog',
      resolution: expect.objectContaining({
        mode: 'backend_resolved',
        resolver_ref: 'gtm.account_catalog',
        on_missing: 'omit',
      }),
    }))
  })

  it('keeps CSV input evidence bounded to the input-contract worksheet', () => {
    const inputContracts = readFileSync(
      resolve(process.cwd(), '../docs/examples/gtm-showcase/anip-capability-input-contracts.csv'),
      'utf8',
    )
    const runtimeGovernance = readFileSync(
      resolve(process.cwd(), '../docs/examples/gtm-showcase/anip-capability-runtime-governance.csv'),
      'utf8',
    )
    const source = [
      '# Locked Product Design Baseline',
      '{"source":"locked_product_design_baseline"}',
      '# Source Evidence Available To Developer Design',
      inputContracts,
      '# Next Developer Evidence Worksheet',
      runtimeGovernance,
    ].join('\n\n')

    const evidence = parseInputContractEvidenceFromSourceText(source)

    expect(evidence.capabilities).toHaveLength(23)
    expect(evidence.capabilities.map((item) => item.capability_id)).not.toContain('capability_id')
    expect(evidence.capabilities.find((item) => item.capability_id === 'gtm.pipeline_summary')?.inputs)
      .not.toEqual(expect.arrayContaining([
        expect.objectContaining({ input_name: 'gtm-pipeline-service' }),
      ]))
  })

  it('infers v0.24 input resolution from source-owned semantic types', () => {
    const definition = buildDeveloperDefinitionData({
      project: {
        id: 'project-resolution',
        name: 'Resolution Project',
        domain: 'gtm',
        project_type: 'standard',
      },
      baseline: null,
      requirements: null,
      scenarios: [],
      shape: {
        id: 'shape-resolution',
        content_hash: 'shape-resolution-hash',
        data: {
          shape: {
            services: [
              {
                id: 'gtm-pipeline-service',
                name: 'GTM Pipeline Service',
                capabilities: ['gtm.pipeline_summary'],
              },
            ],
            capability_contracts: [
              {
                id: 'gtm.pipeline_summary',
                capability_id: 'gtm.pipeline_summary',
                purpose: 'Return a bounded pipeline summary.',
                source_kind: 'custom_code_bundle',
                inputs: [
                  {
                    input_name: 'owner_scope',
                    input_type: 'string',
                    required: false,
                    semantic_type: 'scope_reference',
                    summary: 'Actor-safe ownership scope.',
                  },
                  {
                    input_name: 'target_ref',
                    input_type: 'string',
                    required: true,
                    semantic_type: 'entity_reference',
                    entity_reference: true,
                    catalog_ref: 'gtm.account_catalog',
                    summary: 'Account reference.',
                  },
                ],
              },
            ],
          },
        },
      },
      pmArtifacts: [],
    } as any)

    const capability = definition.capability_formalizations.find((item) => item.capability_id === 'gtm.pipeline_summary')
    expect(capability?.inputs.find((input) => input.input_name === 'owner_scope')?.resolution).toEqual({
      mode: 'actor_policy_or_explicit',
      on_missing: 'use_actor_scope',
      on_ambiguous: 'clarify',
      on_unresolved: 'clarify',
    })
    expect(capability?.inputs.find((input) => input.input_name === 'target_ref')?.resolution).toEqual({
      mode: 'backend_resolved',
      resolver_ref: 'gtm.account_catalog',
      on_missing: 'clarify',
      on_ambiguous: 'clarify',
      on_unresolved: 'clarify',
    })
    const contract = buildDeveloperDefinitionContract({
      project: {
        id: 'project-resolution',
        name: 'Resolution Project',
        domain: 'gtm',
        project_type: 'standard',
      } as any,
      baseline: null,
      requirements: null,
      scenarios: [],
      shape: null,
      traceability: null,
      developerDefinition: definition,
    })
    const contractJson = JSON.stringify(contract)
    expect(contractJson).toContain('"catalog_ref":"gtm.account_catalog"')
    expect(contractJson).not.toContain('reference_catalog')
  })

  it('rejects invalid v0.24 input resolution metadata', () => {
    const issues = validateDeveloperDefinitionRequiredFields({
      product_alignment: {
        governed_behavior_formalization: 'Formalized.',
        approval_posture_formalization: 'Formalized.',
      },
      identity: {
        system_name: 'Resolution Project',
        domain_name: 'gtm',
        delivery_model: 'standalone_service',
        architecture_shape: 'single_service',
      },
      service_topology_bindings: [],
      service_backend_bindings: [],
      actor_expectations: [],
      permission_intent_bindings: [],
      data_domain: { domain_name: 'gtm' },
      domain_concept_bindings: [],
      application_object_model: [],
      capability_formalizations: [
        {
          id: 'cap-risk',
          service_id: 'gtm-service',
          capability_id: 'gtm.risk',
          title: 'Risk',
          summary: 'Risk summary.',
          intent_type: 'read_only',
          operation_type: 'query',
          side_effect_level: 'none',
          backend_operation: 'risk',
          path_template: '/risk',
          output_shape: 'risk_result',
          kind: 'atomic',
          inputs: [
            {
              input_name: 'status',
              input_type: 'string',
              required: true,
              summary: 'Status',
              default_value: '',
              allowed_values: [],
              resolution: { mode: 'closed_values' },
            },
            {
              input_name: 'scope',
              input_type: 'string',
              required: true,
              summary: 'Scope',
              default_value: '',
              allowed_values: [],
              semantic_type: 'bad type',
              catalog_ref: '../bad',
              resolution: { mode: 'guess' },
            },
          ],
        },
      ],
      scenario_formalizations: [],
      composition_rules: [],
      verification: {
        supported_question_family_bindings: [],
        business_goal_bindings: [],
        non_goal_guards: [],
        success_criteria_checks: [],
      },
      generation: {
        scalability_profile: 'single_service',
        codegen_adapter: 'generic',
        layout_strategy: 'service_topology',
        protocols: ['anip_http'],
        selected_service_ids: ['gtm-service'],
      },
      naming: {
        namespace: 'gtm',
        package_prefix: 'gtm',
        service_name_prefix: 'gtm',
      },
    } as unknown as DeveloperDefinitionData)

    expect(issues.map((issue) => issue.message)).toEqual(expect.arrayContaining([
      'closed_values resolution requires non-empty allowed values.',
      'Input semantic type must be a safe v0.24 identifier.',
      'Input catalog_ref must be a safe v0.24 resolver/catalog identifier.',
      'Input resolution.mode must be a supported v0.24 value.',
    ]))
  })

  it('normalizes manual enum separators and preserves catalog resolver references', () => {
    const definition = definitionWithCapabilities([
      {
        id: 'contract_native:gtm.prioritize_accounts',
        source_kind: 'contract_native',
        service_id: 'gtm-prioritization-service',
        capability_id: 'gtm.prioritize_accounts',
        title: 'Prioritize Accounts',
        summary: 'Prioritize accounts.',
        intent_type: 'business_action',
        operation_type: 'read',
        side_effect_level: 'read',
        business_effects: { produces: ['content.recommendation'], does_not_produce: ['system.mutation'] },
        backend_operation: 'gtm.prioritize_accounts',
        path_template: '/gtm/prioritize-accounts',
        output_shape: 'gtm_prioritize_accounts_result',
        kind: 'atomic',
        inputs: [
          {
            input_name: 'cohort_ref',
            input_type: 'string',
            required: true,
            summary: 'Closed cohort reference.',
            default_value: '',
            allowed_values: ['expansion_candidates_q2;at_risk_q2'],
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
    ])

    const contract = buildDeveloperDefinitionContract({
      project: { id: 'project-enums', name: 'Enum Project', domain: 'gtm', project_type: 'standard' } as any,
      baseline: null,
      requirements: null,
      scenarios: [],
      shape: null,
      traceability: null,
      developerDefinition: definition,
    })
    const input = contract.capability_formalizations[0]?.inputs[0]

    expect(input.allowed_values).toEqual(['expansion_candidates_q2', 'at_risk_q2'])
    expect(input.resolution).toEqual(expect.objectContaining({
      mode: 'closed_values',
      resolver_ref: 'gtm.cohort_catalog',
    }))
  })

  it('rejects public-required inputs that are resolved or omitted when missing', () => {
    const definition = definitionWithCapabilities([
      {
        id: 'contract_native:demo.summary',
        source_kind: 'contract_native',
        service_id: 'demo-service',
        capability_id: 'demo.summary',
        title: 'Summary',
        summary: 'Summarize bounded context.',
        intent_type: 'read_only',
        operation_type: 'read',
        side_effect_level: 'read',
        business_effects: { produces: ['content.summary'], does_not_produce: ['raw_data_export'] },
        backend_operation: 'demo.summary',
        path_template: '/demo/summary',
        output_shape: 'summary_result',
        kind: 'atomic',
        inputs: [
          {
            input_name: 'owner_scope',
            input_type: 'string',
            required: true,
            summary: 'Actor scope.',
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
          {
            input_name: 'target_ref',
            input_type: 'string',
            required: true,
            summary: 'Optional provider-owned target.',
            default_value: '',
            allowed_values: [],
            semantic_type: 'entity_reference',
            entity_reference: true,
            resolution: {
              mode: 'backend_resolved',
              on_missing: 'omit',
              on_ambiguous: 'clarify',
              on_unresolved: 'clarify',
            },
          },
        ],
      },
    ])

    const messages = validateDeveloperDefinitionRequiredFields(definition).map((issue) => issue.message)

    expect(messages).toEqual(expect.arrayContaining([
      'Inputs resolved from actor scope when missing must be optional in the public contract.',
      'Inputs omitted when missing must be optional in the public contract.',
    ]))
  })

  it('requires explicit capability runtime governance before saving', () => {
    const definition = {
      product_alignment: {
        governed_behavior_formalization: 'Formalized.',
        approval_posture_formalization: 'Formalized.',
      },
      identity: {
        system_name: 'Governance Project',
        domain_name: 'gtm',
        delivery_model: 'standalone_service',
        architecture_shape: 'single_service',
      },
      service_topology_bindings: [],
      service_backend_bindings: [],
      actor_expectations: [],
      permission_intent_bindings: [],
      data_domain: { domain_name: 'gtm' },
      domain_concept_bindings: [],
      application_object_model: [],
      capability_formalizations: [
        {
          id: 'contract_native:gtm.route_leads',
          source_kind: 'contract_native',
          service_id: 'gtm-prioritization-service',
          capability_id: 'gtm.route_leads',
          title: 'Route Leads',
          summary: 'Prepare governed routing preview.',
          intent_type: 'business_action',
          operation_type: 'approval_gated',
          side_effect_level: 'approval_required',
          backend_operation: 'gtm.route_leads',
          path_template: '/gtm/route-leads',
          output_shape: 'gtm_route_leads_result',
          kind: 'atomic',
          inputs: [
            {
              input_name: 'cohort_ref',
              input_type: 'string',
              required: true,
              summary: 'Lead cohort.',
              allowed_values: [],
              default_value: '',
            },
          ],
        },
      ],
      scenario_formalizations: [],
      composition_rules: [],
      verification: {
        supported_question_family_bindings: [],
        business_goal_bindings: [],
        non_goal_guards: [],
        success_criteria_checks: [],
      },
      generation: {
        scalability_profile: 'single_service',
        codegen_adapter: 'generic',
        layout_strategy: 'service_topology',
        protocols: ['anip_http'],
        selected_service_ids: ['gtm-prioritization-service'],
      },
      naming: {
        namespace: 'gtm',
        package_prefix: 'gtm',
        service_name_prefix: 'gtm',
      },
    } as unknown as DeveloperDefinitionData

    const issues = validateDeveloperDefinitionRequiredFields(definition)

    expect(issues.map((issue) => issue.message)).toEqual(expect.arrayContaining([
      'Route Leads Produced Effects must have at least one selection.',
      'Route Leads Forbidden Effects must have at least one selection.',
      'Route Leads is approval/write-capable and must define an approval grant policy before saving.',
    ]))
  })

  it('rejects composed mappings from cohort references into concrete entity child inputs', () => {
    const child: DeveloperCapabilityFormalization = {
      id: 'contract_native:demo.draft_message',
      source_kind: 'contract_native',
      service_id: 'demo-service',
      capability_id: 'demo.draft_message',
      title: 'Draft Message',
      summary: 'Draft a message for a concrete account.',
      intent_type: 'business_action',
      operation_type: 'read',
      side_effect_level: 'read',
      business_effects: { produces: ['content.draft'], does_not_produce: ['external_dispatch'] },
      backend_operation: 'demo.draft_message',
      path_template: '/demo/draft-message',
      output_shape: 'draft_result',
      kind: 'atomic',
      inputs: [
        {
          input_name: 'target_ref',
          input_type: 'string',
          required: true,
          summary: 'Concrete account target.',
          default_value: '',
          allowed_values: [],
          semantic_type: 'entity_reference',
          entity_reference: true,
        },
      ],
    }
    const parent: DeveloperCapabilityFormalization = {
      id: 'contract_native:demo.prioritized_draft',
      source_kind: 'contract_native',
      service_id: 'demo-service',
      capability_id: 'demo.prioritized_draft',
      title: 'Prioritized Draft',
      summary: 'Prioritize a cohort and draft for the selected target.',
      intent_type: 'business_action',
      operation_type: 'read',
      side_effect_level: 'read',
      business_effects: { produces: ['content.draft'], does_not_produce: ['external_dispatch'] },
      backend_operation: 'demo.prioritized_draft',
      path_template: '/demo/prioritized-draft',
      output_shape: 'draft_result',
      kind: 'composed',
      inputs: [
        {
          input_name: 'cohort_ref',
          input_type: 'string',
          required: true,
          summary: 'Account cohort.',
          default_value: '',
          allowed_values: [],
          semantic_type: 'cohort_reference',
        },
      ],
      composition: {
        authority_boundary: 'same_service',
        steps: [{ id: 'draft', capability: 'demo.draft_message' }],
        input_mapping: { draft: { target_ref: '$.input.cohort_ref' } },
        output_mapping: { result: '$.steps.draft.output.result' },
        failure_policy: {
          child_clarification: 'propagate',
          child_denial: 'propagate',
          child_approval_required: 'propagate',
          child_error: 'fail_parent',
        },
        audit_policy: { record_child_invocations: true, parent_task_lineage: true },
      },
    }

    const issues = validateDeveloperDefinitionRequiredFields(definitionWithCapabilities([child, parent]))

    expect(issues.map((issue) => issue.message)).toContain(
      'Input mapping cannot feed cohort parent input cohort_ref into concrete_entity child input target_ref. Add a provider-owned composition step and map from its output if this value is derived.',
    )
  })

  it('rejects optional parent inputs that are the only source for required child inputs', () => {
    const child: DeveloperCapabilityFormalization = {
      id: 'contract_native:demo.draft_message',
      source_kind: 'contract_native',
      service_id: 'demo-service',
      capability_id: 'demo.draft_message',
      title: 'Draft Message',
      summary: 'Draft a message for a concrete account.',
      intent_type: 'business_action',
      operation_type: 'read',
      side_effect_level: 'read',
      business_effects: { produces: ['content.draft'], does_not_produce: ['external_dispatch'] },
      backend_operation: 'demo.draft_message',
      path_template: '/demo/draft-message',
      output_shape: 'draft_result',
      kind: 'atomic',
      inputs: [
        {
          input_name: 'target_ref',
          input_type: 'string',
          required: true,
          summary: 'Concrete account target.',
          default_value: '',
          allowed_values: [],
          semantic_type: 'entity_reference',
          entity_reference: true,
        },
      ],
    }
    const parent: DeveloperCapabilityFormalization = {
      id: 'contract_native:demo.bottleneck_draft',
      source_kind: 'contract_native',
      service_id: 'demo-service',
      capability_id: 'demo.bottleneck_draft',
      title: 'Bottleneck Draft',
      summary: 'Draft for a provider-selected bottleneck account.',
      intent_type: 'business_action',
      operation_type: 'read',
      side_effect_level: 'read',
      business_effects: { produces: ['content.draft'], does_not_produce: ['external_dispatch'] },
      backend_operation: 'demo.bottleneck_draft',
      path_template: '/demo/bottleneck-draft',
      output_shape: 'draft_result',
      kind: 'composed',
      inputs: [
        {
          input_name: 'target_ref',
          input_type: 'string',
          required: false,
          summary: 'Optional caller-selected account.',
          default_value: '',
          allowed_values: [],
          semantic_type: 'entity_reference',
          entity_reference: true,
          resolution: { mode: 'backend_resolved', on_missing: 'omit', on_ambiguous: 'clarify', on_unresolved: 'clarify' },
        },
      ],
      composition: {
        authority_boundary: 'same_service',
        steps: [{ id: 'draft', capability: 'demo.draft_message' }],
        input_mapping: { draft: { target_ref: '$.input.target_ref' } },
        output_mapping: { result: '$.steps.draft.output.result' },
        failure_policy: {
          child_clarification: 'propagate',
          child_denial: 'propagate',
          child_approval_required: 'propagate',
          child_error: 'fail_parent',
        },
        audit_policy: { record_child_invocations: true, parent_task_lineage: true },
      },
    }

    const issues = validateDeveloperDefinitionRequiredFields(definitionWithCapabilities([child, parent]))

    expect(issues.map((issue) => issue.message)).toContain(
      'Required child input target_ref cannot be satisfied by optional parent input target_ref. Map it from a required/defaulted parent input or a prior provider-owned composition step output.',
    )
  })

  it('allows optional child composition inputs to remain unmapped', () => {
    const child: DeveloperCapabilityFormalization = {
      id: 'contract_native:demo.prepare_preview',
      source_kind: 'contract_native',
      service_id: 'demo-service',
      capability_id: 'demo.prepare_preview',
      title: 'Prepare Preview',
      summary: 'Prepare a governed preview.',
      intent_type: 'business_action',
      operation_type: 'preview',
      side_effect_level: 'approval_required',
      business_effects: { produces: ['system.preview_mutation'], does_not_produce: ['approval.execute'] },
      backend_operation: 'demo.prepare_preview',
      path_template: '/demo/prepare-preview',
      output_shape: 'preview_result',
      kind: 'atomic',
      grant_policy: {
        allowed_grant_types: ['one_time'],
        default_grant_type: 'one_time',
        expires_in_seconds: 900,
        max_uses: 1,
      },
      inputs: [
        {
          input_name: 'quarter',
          input_type: 'string',
          required: true,
          summary: 'Quarter label.',
          default_value: '',
          allowed_values: [],
          semantic_type: 'time_scope',
        },
        {
          input_name: 'selection_basis',
          input_type: 'string',
          required: false,
          summary: 'Optional provider default for the selection basis.',
          default_value: 'risk',
          allowed_values: [],
          semantic_type: 'business_category',
        },
      ],
    }
    const parent: DeveloperCapabilityFormalization = {
      ...child,
      id: 'contract_native:demo.composed_preview',
      capability_id: 'demo.composed_preview',
      title: 'Composed Preview',
      kind: 'composed',
      inputs: [
        {
          input_name: 'quarter',
          input_type: 'string',
          required: true,
          summary: 'Quarter label.',
          default_value: '',
          allowed_values: [],
          semantic_type: 'time_scope',
        },
      ],
      composition: {
        authority_boundary: 'same_service',
        steps: [{ id: 'prepare', capability: 'demo.prepare_preview' }],
        input_mapping: { prepare: { quarter: '$.input.quarter', selection_basis: '' } },
        output_mapping: { result: '$.steps.prepare.output.result' },
        failure_policy: {
          child_clarification: 'propagate',
          child_denial: 'propagate',
          child_approval_required: 'propagate',
          child_error: 'fail_parent',
        },
        audit_policy: { record_child_invocations: true, parent_task_lineage: true },
      },
    }

    const messages = validateDeveloperDefinitionRequiredFields(definitionWithCapabilities([child, parent])).map((issue) => issue.message)

    expect(messages).not.toContain('Composed Preview prepare selection_basis Mapping must be a JSONPath from parent input or a previous step output.')
    expect(messages).toEqual([])
  })

  it('reports incomplete grant policy metadata without throwing', () => {
    const capability: DeveloperCapabilityFormalization = {
      id: 'contract_native:demo.approval_preview',
      source_kind: 'contract_native',
      service_id: 'demo-service',
      capability_id: 'demo.approval_preview',
      title: 'Approval Preview',
      summary: 'Prepare a governed approval preview.',
      intent_type: 'business_action',
      operation_type: 'preview',
      side_effect_level: 'approval_required',
      business_effects: { produces: ['system.preview_mutation'], does_not_produce: ['approval.execute'] },
      backend_operation: 'demo.approval_preview',
      path_template: '/demo/approval-preview',
      output_shape: 'preview_result',
      kind: 'atomic',
      grant_policy: {} as DeveloperCapabilityFormalization['grant_policy'],
      inputs: [],
    }

    const messages = validateDeveloperDefinitionRequiredFields(definitionWithCapabilities([capability]))
      .map((issue) => issue.message)

    expect(messages).toContain('Approval grant policy must allow at least one grant type.')
    expect(messages).toContain('Default approval grant type must be one of the allowed grant types.')
    expect(messages).toContain('Approval grants must expire after a positive number of seconds.')
    expect(messages).toContain('Approval grants must allow at least one use.')
  })

  it('treats backend binding discovery matches as order-independent and mapping-level ready', () => {
    const discoveryRecords = [
      {
        id: 'record-a',
        connection_id: 'jira-api',
        backend_kind: 'native_api',
        operation_id: 'jira.rest.get_versions',
        input_schema_summary: {
          required: ['project_key'],
          optional: ['limit'],
        },
      },
      {
        id: 'record-b',
        connection_id: 'jira-api',
        backend_kind: 'native_api',
        operation_id: 'jira.rest.search_issues',
        input_schema_summary: {
          required: ['issue_query'],
          optional: ['backend_options'],
        },
      },
      {
        id: 'record-c-other-capability',
        connection_id: 'jira-api',
        backend_kind: 'native_api',
        operation_id: 'jira.rest.search_issues',
        input_schema_summary: {
          required: ['different_context'],
          optional: ['different_optional'],
        },
      },
    ] as any
    const nativeBinding = {
      backend_kind: 'native_api',
      connection_ref: 'jira-api',
      raw_operation_refs: ['jira.rest.search_issues', 'jira.rest.get_versions'],
      backend_input_mode: 'explicit',
      derived_required_backend_inputs: ['issue_query', 'project_key'],
      derived_optional_backend_inputs: ['backend_options', 'limit'],
      matched_discovery_record_ids: ['record-b', 'record-a'],
    } as any
    const mcpBinding = {
      backend_kind: 'mcp',
      connection_ref: 'atlassian-mcp',
      raw_operation_refs: [],
      backend_input_mode: 'explicit',
    } as any

    expect(resolveIntegrationFrontingBackendBindingHealth(nativeBinding, discoveryRecords).status).toBe('ready')
    expect(resolveIntegrationFrontingBackendBindingsHealth([nativeBinding, mcpBinding], discoveryRecords).status).toBe('ready')
  })

  it('rejects no-result composition policy without an explicit empty-result source step', () => {
    const child: DeveloperCapabilityFormalization = {
      id: 'contract_native:demo.prepare_preview',
      source_kind: 'contract_native',
      service_id: 'demo-service',
      capability_id: 'demo.prepare_preview',
      title: 'Prepare Preview',
      summary: 'Prepare a governed preview.',
      intent_type: 'business_action',
      operation_type: 'read',
      side_effect_level: 'read',
      business_effects: { produces: ['content.summary'], does_not_produce: ['raw_data_export'] },
      backend_operation: 'demo.prepare_preview',
      path_template: '/demo/prepare-preview',
      output_shape: 'preview_result',
      kind: 'atomic',
      inputs: [],
    }
    const parent: DeveloperCapabilityFormalization = {
      ...child,
      id: 'contract_native:demo.composed_preview',
      capability_id: 'demo.composed_preview',
      title: 'Composed Preview',
      kind: 'composed',
      composition: {
        authority_boundary: 'same_service',
        steps: [{ id: 'prepare', capability: 'demo.prepare_preview' }],
        input_mapping: { prepare: {} },
        output_mapping: { result: '$.steps.prepare.output.result' },
        empty_result_policy: 'return_success_no_results',
        empty_result_output: { result: null, empty: true },
        failure_policy: {
          child_clarification: 'propagate',
          child_denial: 'propagate',
          child_approval_required: 'propagate',
          child_error: 'fail_parent',
        },
        audit_policy: { record_child_invocations: true, parent_task_lineage: true },
      },
    }

    const messages = validateDeveloperDefinitionRequiredFields(definitionWithCapabilities([child, parent])).map((issue) => issue.message)

    expect(messages).toContain(
      'return_success_no_results requires exactly one composition step marked as the empty-result source.',
    )
  })

  it('accepts provider-owned prior step outputs as concrete child input sources', () => {
    const selectTarget: DeveloperCapabilityFormalization = {
      id: 'contract_native:demo.select_target',
      source_kind: 'contract_native',
      service_id: 'demo-service',
      capability_id: 'demo.select_target',
      title: 'Select Target',
      summary: 'Select a concrete target from a reviewed cohort.',
      intent_type: 'business_action',
      operation_type: 'read',
      side_effect_level: 'read',
      business_effects: { produces: ['content.summary'], does_not_produce: ['raw_data_export'] },
      backend_operation: 'demo.select_target',
      path_template: '/demo/select-target',
      output_shape: 'selected_target_result',
      kind: 'atomic',
      inputs: [
        {
          input_name: 'cohort_ref',
          input_type: 'string',
          required: true,
          summary: 'Account cohort.',
          default_value: '',
          allowed_values: [],
          semantic_type: 'cohort_reference',
        },
      ],
    }
    const draft: DeveloperCapabilityFormalization = {
      id: 'contract_native:demo.draft_message',
      source_kind: 'contract_native',
      service_id: 'demo-service',
      capability_id: 'demo.draft_message',
      title: 'Draft Message',
      summary: 'Draft a message for a concrete account.',
      intent_type: 'business_action',
      operation_type: 'read',
      side_effect_level: 'read',
      business_effects: { produces: ['content.draft'], does_not_produce: ['external_dispatch'] },
      backend_operation: 'demo.draft_message',
      path_template: '/demo/draft-message',
      output_shape: 'draft_result',
      kind: 'atomic',
      inputs: [
        {
          input_name: 'target_ref',
          input_type: 'string',
          required: true,
          summary: 'Concrete account target.',
          default_value: '',
          allowed_values: [],
          semantic_type: 'entity_reference',
          entity_reference: true,
        },
      ],
    }
    const parent: DeveloperCapabilityFormalization = {
      id: 'contract_native:demo.prioritized_draft',
      source_kind: 'contract_native',
      service_id: 'demo-service',
      capability_id: 'demo.prioritized_draft',
      title: 'Prioritized Draft',
      summary: 'Prioritize a cohort and draft for the provider-selected target.',
      intent_type: 'business_action',
      operation_type: 'read',
      side_effect_level: 'read',
      business_effects: { produces: ['content.draft'], does_not_produce: ['external_dispatch'] },
      backend_operation: 'demo.prioritized_draft',
      path_template: '/demo/prioritized-draft',
      output_shape: 'draft_result',
      kind: 'composed',
      inputs: [
        {
          input_name: 'cohort_ref',
          input_type: 'string',
          required: true,
          summary: 'Account cohort.',
          default_value: '',
          allowed_values: [],
          semantic_type: 'cohort_reference',
        },
      ],
      composition: {
        authority_boundary: 'same_service',
        steps: [
          { id: 'select_target', capability: 'demo.select_target' },
          { id: 'draft', capability: 'demo.draft_message' },
        ],
        input_mapping: {
          select_target: { cohort_ref: '$.input.cohort_ref' },
          draft: { target_ref: '$.steps.select_target.output.selected_target_ref' },
        },
        output_mapping: { result: '$.steps.draft.output.result' },
        failure_policy: {
          child_clarification: 'propagate',
          child_denial: 'propagate',
          child_approval_required: 'propagate',
          child_error: 'fail_parent',
        },
        audit_policy: { record_child_invocations: true, parent_task_lineage: true },
      },
    }

    const messages = validateDeveloperDefinitionRequiredFields(definitionWithCapabilities([selectTarget, draft, parent])).map((issue) => issue.message)

    expect(messages).not.toContain(
      'Input mapping cannot feed cohort parent input cohort_ref into concrete_entity child input target_ref. Add a provider-owned composition step and map from its output if this value is derived.',
    )
    expect(messages).not.toContain(
      'Required child input target_ref cannot be satisfied by optional parent input target_ref. Map it from a required/defaulted parent input or a prior provider-owned composition step output.',
    )
  })

  it('narrows unconditional high-risk policy bindings to matching capability surfaces', () => {
    const definition = buildDeveloperDefinitionData({
      project: {
        id: 'project-policy-narrowing',
        name: 'Policy Narrowing Project',
        domain: 'gtm',
        project_type: 'standard',
      },
      baseline: null,
      requirements: null,
      scenarios: [],
      shape: {
        id: 'shape-policy-narrowing',
        content_hash: 'shape-policy-narrowing-hash',
        data: {
          shape: {
            services: [
              {
                id: 'gtm-pipeline-service',
                name: 'GTM Pipeline Service',
                capabilities: ['gtm.pipeline_summary', 'gtm.account_enrichment_summary'],
              },
            ],
            capability_contracts: [
              {
                id: 'gtm.pipeline_summary',
                capability_id: 'gtm.pipeline_summary',
                purpose: 'Return bounded pipeline intelligence.',
                source_kind: 'custom_code_bundle',
                inputs: [],
              },
              {
                id: 'gtm.account_enrichment_summary',
                capability_id: 'gtm.account_enrichment_summary',
                purpose: 'Return bounded account enrichment context.',
                source_kind: 'custom_code_bundle',
                inputs: [],
              },
            ],
          },
        },
      },
      pmArtifacts: [
        {
          id: 'business-areas',
          project_id: 'project-policy-narrowing',
          title: 'Business Areas',
          kind: 'product',
          role: 'supporting',
          content_hash: 'business-areas-hash',
          created_at: '',
          updated_at: '',
          data: {
            artifact_type: 'business_areas',
            entries: [{ business_area_id: 'account_enrichment', label: 'Account Enrichment', description: 'Account enrichment context.' }],
          },
        },
        {
          id: 'permission-intent',
          project_id: 'project-policy-narrowing',
          title: 'Permission Intent',
          kind: 'product',
          role: 'supporting',
          content_hash: 'permission-intent-hash',
          created_at: '',
          updated_at: '',
          data: {
            artifact_type: 'permission_intent',
            policy_summary: 'Account enrichment denial should not blanket every pipeline capability.',
            rules: [
              {
                actor_id: 'rev_ops_manager',
                business_area: 'account_enrichment',
                access_posture: 'denied',
                governed_outcome_type: 'deny_request',
                governed_outcome: 'Deny raw export, direct-send, unsupported analysis, or out-of-scope mutation requests.',
                notes: '',
              },
            ],
          },
        },
      ],
    } as any)

    expect(definition.permission_intent_bindings[0]?.target_capability_ids).toEqual(['gtm.account_enrichment_summary'])
  })

  it('rejects empty required composition-rule formalization strategy', () => {
    const issues = validateDeveloperDefinitionRequiredFields({
      product_alignment: {
        governed_behavior_formalization: 'Preserve governed behavior.',
        approval_posture_formalization: 'Stop before approval-gated work.',
      },
      identity: {
        system_name: 'Revenue Operations',
        domain_name: 'revenue_operations',
        delivery_model: 'local_service',
        architecture_shape: 'multi_service_estate',
        high_availability_required: true,
      },
      backend_bindings: {
        data_access_backend_type: 'warehouse',
        data_access_target_label: 'Pipeline warehouse',
        application_integration_backend_type: 'crm',
        application_integration_system_name: 'CRM',
        application_integration_environment: 'production',
        application_integration_auth_type: 'oauth2',
        application_integration_adapter_target: 'crm_adapter',
      },
      data_domain: {
        domain_name: 'revenue_operations',
      },
      generation: {
        scalability_profile: 'team',
        codegen_adapter: 'typescript',
        layout_strategy: 'package',
        protocols: ['http'],
        selected_service_ids: ['pipeline'],
      },
      naming: {
        namespace: 'revenue.operations',
        package_prefix: 'revenue',
        service_name_prefix: 'revenue',
      },
      verification: {
        data_access_scenario_pack: {
          target_count: 1,
          categories: ['allowed'],
        },
      },
      service_topology_bindings: [],
      actor_expectations: [],
      permission_intent_bindings: [],
      domain_concept_bindings: [],
      application_object_model: [],
      capability_formalizations: [],
      scenario_formalizations: [],
      composition_rules: [
        {
          id: 'composition_rule_0',
          rule: 'Do not compose gated work without approval.',
          affected_scenario_ids: ['scenario-1'],
          formalization_strategy: '',
        },
      ],
    } as unknown as DeveloperDefinitionData)

    expect(issues.some((issue) =>
      issue.path === 'composition_rules.composition_rule_0.formalization_strategy'
      && issue.message === 'Do not compose gated work without approval. Formalization Strategy is required.',
    )).toBe(true)
  })

  it('allows governed fronting projects to save with the reduced fronting contract sections', () => {
    const issues = validateDeveloperDefinitionRequiredFields({
      product_alignment: {
        governed_behavior_formalization: 'Govern outbound behavior explicitly.',
        approval_posture_formalization: 'Stop before approval-gated writes.',
      },
      identity: {
        system_name: 'Issue Tracker Fronting',
        domain_name: 'issue_tracker',
        delivery_model: 'embedded_existing_product',
        architecture_shape: 'single_service',
        high_availability_required: false,
      },
      backend_bindings: {
        data_access_backend_type: '',
        data_access_target_label: '',
        application_integration_backend_type: 'mcp_server',
        application_integration_system_name: 'Issue Tracker MCP',
        application_integration_environment: 'production',
        application_integration_auth_type: 'oauth2',
        application_integration_adapter_target: 'issue_tracker_adapter',
      },
      integration_fronting: {
        project_type: 'governed_service_project',
        integration_profile: {
          kind: 'mcp_fronting',
          systems: [],
        },
        capability_mappings: [],
      },
      capability_formalizations: [
        {
          id: 'cap-1',
          capability_id: 'issue_tracker.prepare_ticket',
          title: 'Prepare Ticket',
          source_kind: 'question_family',
          service_id: 'svc_issue_fronting',
          intent_type: 'prepare',
          operation_type: 'prepare_only',
          side_effect_level: 'write_adjacent',
          summary: 'Prepare a ticket payload without executing the write.',
          output_shape: 'ticket_payload',
          backend_operation: 'issue_mcp.create_issue',
          business_effects: {
            produces: ['system.preview_mutation'],
            does_not_produce: ['system.mutation', 'external_dispatch'],
          },
          path_template: '',
        },
      ],
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
      generation: {
        scalability_profile: 'single_instance',
        codegen_adapter: 'typescript_node',
        layout_strategy: 'monorepo',
        protocols: ['anip_http'],
        selected_service_ids: ['svc_issue_fronting'],
      },
      naming: {
        namespace: 'issue.tracker',
        package_prefix: 'issue',
        service_name_prefix: 'issue',
      },
      service_topology_bindings: [],
      actor_expectations: [],
      permission_intent_bindings: [],
      data_domain: {
        domain_name: '',
      },
      domain_concept_bindings: [],
      application_object_model: [],
      scenario_formalizations: [],
      composition_rules: [],
    } as unknown as DeveloperDefinitionData)

    expect(issues).toEqual([])
  })

  it('rejects invalid service ids before package generation', () => {
    const issues = validateDeveloperDefinitionRequiredFields({
      product_alignment: {
        governed_behavior_formalization: 'Formalized.',
        approval_posture_formalization: 'Formalized.',
      },
      identity: {
        system_name: 'Issue Tracker Fronting',
        domain_name: 'issue_tracker',
        delivery_model: 'embedded_existing_product',
        architecture_shape: 'single_service',
      },
      integration_fronting: {
        project_type: 'governed_service_project',
        integration_profile: { kind: 'mcp_fronting', systems: [] },
        capability_mappings: [],
      },
      service_topology_bindings: [
        {
          id: 'service_topology_issue.context',
          service_id: 'issue.context',
          service_name: 'Issue Context',
          source_role: 'Conceptual context slice.',
          source_capabilities: [],
          source_concepts: [],
          formalized_capability_ids: [],
          owned_concept_ids: [],
          implementation_notes: '',
        },
      ],
      capability_formalizations: [],
      verification: {
        supported_question_family_bindings: [],
        business_goal_bindings: [],
        non_goal_guards: [],
        success_criteria_checks: [],
      },
      generation: {
        scalability_profile: 'single_instance',
        codegen_adapter: 'typescript_node',
        layout_strategy: 'monorepo',
        protocols: ['anip_http'],
        selected_service_ids: ['issue.context'],
      },
      naming: {
        namespace: 'issue_tracker',
        package_prefix: 'issue',
        service_name_prefix: 'issue',
      },
      service_backend_bindings: [],
      actor_expectations: [],
      permission_intent_bindings: [],
      data_domain: { domain_name: '' },
      domain_concept_bindings: [],
      application_object_model: [],
      scenario_formalizations: [],
      composition_rules: [],
    } as unknown as DeveloperDefinitionData)

    expect(issues.some((issue) =>
      issue.path === 'service_topology_bindings.service_topology_issue.context.service_id'
      && issue.message.includes('must not contain dots'),
    )).toBe(true)
    expect(issues.some((issue) =>
      issue.path === 'generation.selected_service_ids'
      && issue.message.includes('issue.context is invalid'),
    )).toBe(true)
  })

  it('uses fronting integration services instead of conceptual product-shape services for governed fronting topology', () => {
    const definition = buildDeveloperDefinitionData({
      project: {
        id: 'jira-fronting-test',
        workspace_id: 'workspace',
        name: 'Jira Fronting',
        summary: '',
        domain: 'jira',
        labels: [],
        project_type: 'governed_service_project',
        integration_profile: { kind: 'native_api_fronting', systems: [] },
        created_at: '',
        updated_at: '',
        requirements_count: 0,
        scenarios_count: 0,
        proposals_count: 0,
        evaluations_count: 0,
        shapes_count: 0,
        documents_count: 0,
        pm_artifacts_count: 0,
      } as any,
      baseline: null,
      requirements: null,
      scenarios: [],
      shape: {
        id: 'shape-1',
        project_id: 'jira-fronting-test',
        status: 'active',
        content_hash: 'shape-hash',
        created_at: '',
        updated_at: '',
        data: {
          shape: {
            services: [
              {
                id: 'jira.context',
                name: 'Jira Context Service',
                role: 'Conceptual read slice.',
                capabilities: ['jira.backlog.search_context'],
              },
            ],
          },
        },
      } as any,
      pmArtifacts: [
        {
          id: 'mapping-1',
          project_id: 'jira-fronting-test',
          artifact_type: 'integration_fronting_capability_mapping',
          created_at: '',
          updated_at: '',
          data: {
            artifact_type: 'integration_fronting_capability_mapping',
            id: 'mapping-1',
            capability_id: 'jira.backlog.search_context',
            title: 'Search Backlog',
            service_id: 'jira-governance-service',
            service_name: 'Jira Governance Service',
            business_effects: {
              produces: ['content.summary', 'data.read'],
              does_not_produce: ['raw_data_export', 'system.mutation'],
            },
            backend_bindings: [
              {
                backend_kind: 'native_api',
                connection_ref: '2e042241-7389-403f-9002-6bcab2589697-jira-api',
                raw_operation_refs: ['jira.rest.search_issues'],
              },
              {
                backend_kind: 'mcp',
                connection_ref: '2e042241-7389-403f-9002-6bcab2589697-atlassian-mcp',
                raw_operation_refs: [],
                status: 'missing',
              },
            ],
          },
        } as any,
      ],
    })

    expect(definition.generation.selected_service_ids).toEqual(['jira-governance-service'])
    expect(definition.service_topology_bindings.map((binding) => binding.service_id)).toEqual(['jira-governance-service'])
    expect(definition.capability_formalizations.find((capability) =>
      capability.capability_id === 'jira.backlog.search_context',
    )?.service_id).toBe('jira-governance-service')
    expect(definition.capability_formalizations.find((capability) =>
      capability.capability_id === 'jira.backlog.search_context',
    )?.business_effects).toEqual({
      produces: ['content.summary', 'data.read'],
      does_not_produce: ['raw_data_export', 'system.mutation'],
    })
    expect(definition.integration_fronting?.capability_mappings[0]?.backend_bindings).toEqual([
      expect.objectContaining({
        backend_kind: 'native_api',
        connection_ref: 'conn_2e042241-7389-403f-9002-6bcab2589697-jira-api',
        raw_operation_refs: ['jira.rest.search_issues'],
      }),
    ])
  })

  it('materializes approval grant policy from approval-capable fronting mappings', () => {
    const definition = buildDeveloperDefinitionData({
      project: {
        id: 'jira-fronting-test',
        workspace_id: 'workspace',
        name: 'Jira Fronting',
        summary: '',
        domain: 'jira',
        labels: [],
        project_type: 'governed_service_project',
        integration_profile: { kind: 'native_api_fronting', systems: [] },
        created_at: '',
        updated_at: '',
        requirements_count: 0,
        scenarios_count: 0,
        proposals_count: 0,
        evaluations_count: 0,
        shapes_count: 0,
        documents_count: 0,
        pm_artifacts_count: 0,
      } as any,
      baseline: null,
      requirements: null,
      scenarios: [],
      shape: {
        id: 'shape-1',
        project_id: 'jira-fronting-test',
        status: 'active',
        content_hash: 'shape-hash',
        created_at: '',
        updated_at: '',
        data: {
          shape: {
            services: [
              {
                id: 'jira.fronting',
                name: 'Jira Fronting Service',
                role: 'Governed Jira fronting service.',
                capabilities: ['jira.workflow_transition.request'],
              },
            ],
          },
        },
      } as any,
      pmArtifacts: [
        {
          id: 'mapping-approval',
          project_id: 'jira-fronting-test',
          artifact_type: 'integration_fronting_capability_mapping',
          created_at: '',
          updated_at: '',
          data: {
            artifact_type: 'integration_fronting_capability_mapping',
            capability_id: 'jira.workflow_transition.request',
            title: 'Request Workflow Transition',
            service_id: 'jira-governance-service',
            service_name: 'Jira Governance Service',
            execution_posture: 'approval_gated',
            side_effect_level: 'approval_required',
            approval_rule_refs: ['approval.workflow_transition'],
            business_effects: {
              produces: ['approval.request', 'system.preview_mutation'],
              does_not_produce: ['approval.execute', 'system.mutation'],
            },
            backend_bindings: [
              {
                backend_kind: 'native_api',
                connection_ref: 'jira-api',
                raw_operation_refs: ['jira.rest.transition_issue'],
              },
            ],
          },
        } as any,
      ],
    })

    const capability = definition.capability_formalizations.find((item) =>
      item.capability_id === 'jira.workflow_transition.request',
    )

    expect(capability?.grant_policy).toEqual({
      allowed_grant_types: ['one_time', 'session_bound'],
      default_grant_type: 'one_time',
      expires_in_seconds: 900,
      max_uses: 1,
    })
    expect(validateDeveloperDefinitionRequiredFields(definition).some((issue) =>
      issue.path === 'capability_formalizations.contract_native:jira.workflow_transition.request.grant_policy',
    )).toBe(false)
  })

  it('treats conceptual product-shape service coverage as addressed by the selected governed fronting service', () => {
    const status = developerDefinitionTargetStatus('developer_definition.service_topology:jira.context', {
      developerDefinition: {
        integration_fronting: {
          project_type: 'governed_service_project',
          integration_profile: { kind: 'native_api_fronting', systems: [] },
          capability_mappings: [],
        },
        service_topology_bindings: [
          {
            id: 'service_topology_jira-governance-service',
            service_id: 'jira-governance-service',
            service_name: 'Jira Governance Service',
            source_role: 'Governed fronting boundary.',
            source_capabilities: [],
            source_concepts: [],
            formalized_capability_ids: [],
            owned_concept_ids: [],
            implementation_notes: '',
          },
        ],
        generation: {
          service_generation_mode: 'from_service_design',
          selected_service_ids: ['jira-governance-service'],
        },
      } as unknown as DeveloperDefinitionData,
    })

    expect(status).toBe('addressed')
  })

  it('treats governed fronting service splits as coordination coverage when mappings span service boundaries', () => {
    const status = developerDefinitionTargetStatus('developer_definition.service_coordination:shape:coordination:Jira.Fronting:Jira.Governance:handoff', {
      developerDefinition: {
        integration_fronting: {
          project_type: 'governed_service_project',
          integration_profile: { kind: 'native_api_fronting', systems: [] },
          capability_mappings: [
            { capability_id: 'jira.backlog.search_context', service_id: 'jira.fronting' },
            { capability_id: 'jira.workflow_transition.request', service_id: 'jira.governance' },
          ],
        },
        service_topology_bindings: [
          { service_id: 'jira.fronting' },
          { service_id: 'jira.governance' },
        ],
        audit: {
          service_handoffs_required: true,
          cross_service_reconstruction_required: false,
          cross_service_continuity_required: false,
        },
        scenario_formalizations: [],
      } as unknown as DeveloperDefinitionData,
    })

    expect(status).toBe('addressed')
  })

  it('rejects unknown business effect ids before saving a developer definition', () => {
    const issues = validateDeveloperDefinitionRequiredFields({
      product_alignment: {
        governed_behavior_formalization: 'Govern outbound behavior explicitly.',
        approval_posture_formalization: 'Stop before approval-gated writes.',
      },
      identity: {
        system_name: 'Issue Tracker Fronting',
        domain_name: 'issue_tracker',
        delivery_model: 'embedded_existing_product',
        architecture_shape: 'single_service',
        high_availability_required: false,
      },
      backend_bindings: {
        data_access_backend_type: '',
        data_access_target_label: '',
        application_integration_backend_type: 'mcp_server',
        application_integration_system_name: 'Issue Tracker MCP',
        application_integration_environment: 'production',
        application_integration_auth_type: 'oauth2',
        application_integration_adapter_target: 'issue_tracker_adapter',
      },
      integration_fronting: {
        project_type: 'governed_service_project',
        integration_profile: {
          kind: 'mcp_fronting',
          systems: [],
        },
        capability_mappings: [],
      },
      capability_formalizations: [
        {
          id: 'cap-1',
          capability_id: 'issue_tracker.prepare_ticket',
          title: 'Prepare Ticket',
          source_kind: 'question_family',
          service_id: 'svc_issue_fronting',
          intent_type: 'prepare',
          operation_type: 'prepare_only',
          side_effect_level: 'write_adjacent',
          summary: 'Prepare a ticket payload without executing the write.',
          output_shape: 'ticket_payload',
          backend_operation: 'issue_mcp.create_issue',
          business_effects: {
            produces: ['system.preview_mutation'],
            does_not_produce: ['external_send'],
          },
          path_template: '',
        },
      ],
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
      generation: {
        scalability_profile: 'single_instance',
        codegen_adapter: 'typescript_node',
        layout_strategy: 'monorepo',
        protocols: ['anip_http'],
        selected_service_ids: ['svc_issue_fronting'],
      },
      naming: {
        namespace: 'issue.tracker',
        package_prefix: 'issue',
        service_name_prefix: 'issue',
      },
      service_topology_bindings: [],
      actor_expectations: [],
      permission_intent_bindings: [],
      data_domain: {
        domain_name: '',
      },
      domain_concept_bindings: [],
      application_object_model: [],
      scenario_formalizations: [],
      composition_rules: [],
    } as unknown as DeveloperDefinitionData)

    expect(issues.some((issue) =>
      issue.path === 'capability_formalizations.cap-1.business_effects.does_not_produce'
      && issue.message.includes('unknown effect "external_send"'),
    )).toBe(true)
  })

  it('uses assistant capability candidates and infers same-service governed preparation composition', () => {
    const definition = buildDeveloperDefinitionData({
      project: {
        id: 'project-1',
        name: 'Revenue Review',
        domain: 'demo',
        project_type: 'standard',
      },
      baseline: null,
      requirements: null,
      scenarios: [],
      shape: {
        id: 'shape-1',
        content_hash: 'shape-hash',
        data: {
          shape: {
            services: [
              {
                id: 'demo-pipeline-service',
                name: 'Pipeline Service',
                capabilities: [
                  'demo.account_risk_summary',
                  'demo.prepare_followup_tasks',
                ],
              },
            ],
          },
        },
      },
      pmArtifacts: [
        {
          id: 'product-summary',
          data: {
            artifact_type: 'product_summary',
            multi_step_composition_rules: [],
            supported_question_families: [],
            business_goals: [
              'Review account risk and prepare follow-up task previews without executing downstream mutations.',
            ],
            product_purpose: '',
            business_problem: '',
            approval_posture_summary: '',
            governed_behavior_summary: '',
            success_outcome_summary: '',
            why_now: '',
            lock_status: 'lockable',
          },
        },
        {
          id: 'business-goals',
          data: {
            artifact_type: 'success_criteria',
            criteria: [],
            entries: [],
          },
        },
        {
          id: 'non-goals',
          data: {
            artifact_type: 'non_goals',
            entries: [],
          },
        },
        {
          id: 'product-summary-evidence',
          data: {
            artifact_type: 'composition_evidence',
            business_goals: [
              'Review account risk and prepare follow-up task previews without executing downstream mutations.',
            ],
          },
        },
        {
          id: 'assistant-capabilities',
          data: {
            artifact_type: 'assistant_capability_formalization_candidates',
            source_proposal: {
              items: [
                {
                  structured_data: {
                    capabilities: [
                      {
                        capability_id: 'demo.account_risk_summary',
                        title: 'Account Risk Summary',
                        summary: 'Return ranked risky accounts for the requested business scope.',
                        service_id: 'demo-pipeline-service',
                        intent_type: 'analysis',
                        operation_type: 'read',
                        side_effect_level: 'read_only',
                        output_shape: 'risk_summary',
                      },
                      {
                        capability_id: 'demo.prepare_followup_tasks',
                        title: 'Prepare Follow-up Tasks',
                        summary: 'Prepare follow-up task previews for selected risky accounts without executing the mutation.',
                        service_id: 'demo-pipeline-service',
                        intent_type: 'business_action',
                        operation_type: 'prepare',
                        side_effect_level: 'approval_required',
                        output_shape: 'followup_task_preview',
                        inputs: [
                          {
                            input_name: 'context',
                            input_type: 'object',
                            required: true,
                            summary: 'Derived account-risk context.',
                          },
                        ],
                      },
                    ],
                  },
                },
              ],
            },
          },
        },
      ],
    } as any)

    const followup = definition.capability_formalizations.find((capability) =>
      capability.capability_id === 'demo.prepare_followup_tasks',
    )
    expect(followup?.side_effect_level).toBe('approval_required')
    expect(followup?.inputs.map((input) => input.input_name)).toContain('context')

    const composed = definition.capability_formalizations.find((capability) =>
      capability.capability_id === 'demo.at_risk_followup_preparation',
    )
    expect(composed?.kind).toBe('composed')
    expect(composed?.service_id).toBe('demo-pipeline-service')
    expect(composed?.composition?.steps.map((step) => step.capability)).toEqual([
      'demo.account_risk_summary',
      'demo.prepare_followup_tasks',
    ])
  })

  it('does not invent composed capabilities when the service shape declares canonical source capabilities', () => {
    const definition = buildDeveloperDefinitionData({
      project: {
        id: 'project-canonical',
        name: 'Canonical Revenue Review',
        domain: 'gtm',
        project_type: 'standard',
      },
      baseline: null,
      requirements: null,
      scenarios: [],
      shape: {
        id: 'shape-canonical',
        content_hash: 'shape-canonical-hash',
        data: {
          shape: {
            notes: [
              'Preserves source-declared service IDs and capability ownership instead of inventing new boundaries.',
            ],
            services: [
              {
                id: 'gtm-pipeline-service',
                name: 'Pipeline Service',
                capabilities: [
                  'gtm.account_risk_summary',
                  'gtm.prepare_followup_tasks',
                ],
              },
            ],
          },
        },
      },
      pmArtifacts: [
        {
          id: 'product-summary',
          data: {
            artifact_type: 'product_summary',
            business_goals: [
              'Review account risk and prepare follow-up task previews without executing downstream mutations.',
            ],
            multi_step_composition_rules: [],
            supported_question_families: [],
            product_purpose: '',
            business_problem: '',
            approval_posture_summary: '',
            governed_behavior_summary: '',
            success_outcome_summary: '',
            why_now: '',
            lock_status: 'lockable',
          },
        },
        {
          id: 'assistant-capabilities',
          data: {
            artifact_type: 'assistant_capability_formalization_candidates',
            source_proposal: {
              items: [
                {
                  structured_data: {
                    capabilities: [
                      {
                        capability_id: 'gtm.account_risk_summary',
                        title: 'Account Risk Summary',
                        summary: 'Return ranked risky accounts for the requested business scope.',
                        service_id: 'gtm-pipeline-service',
                        operation_type: 'read',
                        side_effect_level: 'read_only',
                        output_shape: 'risk_summary',
                      },
                      {
                        capability_id: 'gtm.prepare_followup_tasks',
                        title: 'Prepare Follow-up Tasks',
                        summary: 'Prepare follow-up task previews for selected risky accounts without executing the mutation.',
                        service_id: 'gtm-pipeline-service',
                        operation_type: 'prepare',
                        side_effect_level: 'approval_required',
                        output_shape: 'followup_task_preview',
                        inputs: [
                          {
                            input_name: 'context',
                            input_type: 'object',
                            required: true,
                            summary: 'Derived account-risk context.',
                          },
                        ],
                      },
                    ],
                  },
                },
              ],
            },
          },
        },
      ],
    } as any)

    expect(definition.capability_formalizations.map((capability) => capability.capability_id)).toEqual([
      'gtm.account_risk_summary',
      'gtm.prepare_followup_tasks',
    ])
    expect(definition.capability_formalizations.some((capability) => capability.kind === 'composed')).toBe(false)
  })

  it('ignores placeholder assistant capability contracts when compiling canonical source capabilities', () => {
    const definition = buildDeveloperDefinitionData({
      project: {
        id: 'project-placeholder-candidate',
        name: 'Canonical Revenue Review',
        domain: 'gtm',
        project_type: 'standard',
      },
      baseline: null,
      requirements: null,
      scenarios: [],
      shape: {
        id: 'shape-placeholder-candidate',
        content_hash: 'shape-placeholder-candidate-hash',
        data: {
          shape: {
            notes: 'The source declares a canonical capability inventory and Studio must preserve it exactly.',
            services: [
              {
                id: 'gtm-outreach-service',
                name: 'Outreach Service',
                role: 'Draft bounded outreach for explicit selected targets without sending messages.',
                capabilities: ['gtm.bottleneck_account_outreach_draft'],
              },
            ],
          },
        },
      },
      pmArtifacts: [
        {
          id: 'assistant-placeholder-capabilities',
          data: {
            artifact_type: 'assistant_capability_formalization_candidates',
            source_proposal: {
              items: [
                {
                  structured_data: {
                    capabilities: [
                      {
                        capability_id: 'gtm.bottleneck_account_outreach_draft',
                        title: 'Bottleneck account outreach draft',
                        summary: 'Placeholder: outreach-owned cross-service draft contract needs explicit source context.',
                        service_id: 'gtm-outreach-service',
                        backend_operation: 'review_needed',
                        output_shape: 'review_needed',
                      },
                    ],
                  },
                },
              ],
            },
          },
        },
      ],
    } as any)

    const capability = definition.capability_formalizations.find((item) =>
      item.capability_id === 'gtm.bottleneck_account_outreach_draft',
    )
    expect(capability?.summary).toContain('Draft bounded outreach')
    expect(capability?.summary).not.toContain('Placeholder')
    expect(capability?.backend_operation).toBe('gtm.bottleneck_account_outreach_draft')
    expect(capability?.output_shape).toBe('governed_result')
  })

  it('does not preserve placeholder values from a prior saved developer definition', () => {
    const project = {
      id: 'project-prior-placeholder',
      name: 'Canonical Revenue Review',
      domain: 'gtm',
      project_type: 'standard',
    }
    const shape = {
      id: 'shape-prior-placeholder',
      content_hash: 'shape-prior-placeholder-hash',
      data: {
        shape: {
          services: [
            {
              id: 'gtm-pipeline-service',
              name: 'Pipeline Service',
              role: 'Return governed pipeline summaries for quarter and actor scope.',
              capabilities: ['gtm.pipeline_summary'],
            },
          ],
        },
      },
    }
    const existing = buildDeveloperDefinitionData({
      project,
      baseline: null,
      requirements: null,
      scenarios: [],
      shape,
      pmArtifacts: [],
    } as any)
    existing.capability_formalizations[0] = {
      ...existing.capability_formalizations[0],
      summary: 'Placeholder: quarter-scoped pipeline analytics contract needs fuller input and output detail.',
      backend_operation: 'review_needed',
      output_shape: 'review_needed',
    }

    const definition = buildDeveloperDefinitionData({
      project,
      baseline: null,
      requirements: null,
      scenarios: [],
      shape,
      pmArtifacts: [],
      existing,
    } as any)

    const capability = definition.capability_formalizations.find((item) => item.capability_id === 'gtm.pipeline_summary')
    expect(capability?.summary).toContain('Return governed pipeline summaries')
    expect(capability?.summary).not.toContain('Placeholder')
    expect(capability?.backend_operation).toBe('gtm.pipeline_summary')
    expect(capability?.output_shape).toBe('governed_result')
  })

  it('uses source-declared capability purpose when existing summary is generated review filler', () => {
    const project = {
      id: 'project-source-purpose',
      name: 'Canonical Revenue Review',
      domain: 'gtm',
      project_type: 'standard',
    }
    const shape = {
      id: 'shape-source-purpose',
      content_hash: 'shape-source-purpose-hash',
      data: {
        shape: {
          services: [
            {
              id: 'gtm-outreach-service',
              name: 'Outreach Service',
              capabilities: ['gtm.prioritized_outreach_draft'],
            },
          ],
          capability_contracts: [
            {
              id: 'gtm.prioritized_outreach_draft',
              service_id: 'gtm-outreach-service',
              purpose: 'Prioritize a bounded account cohort, include bounded enrichment context for the top accounts, and draft one outreach message.',
              side_effect_type: 'read',
              inputs: [
                {
                  input_name: 'cohort_ref',
                  input_type: 'string',
                  required: true,
                  allowed_values: ['expansion_candidates_q2'],
                },
              ],
            },
          ],
        },
      },
    }
    const existing = buildDeveloperDefinitionData({
      project,
      baseline: null,
      requirements: null,
      scenarios: [],
      shape,
      pmArtifacts: [],
    } as any)
    existing.capability_formalizations[0] = {
      ...existing.capability_formalizations[0],
      summary: 'Reviewed contract for Prioritized Outreach Draft.',
    }

    const definition = buildDeveloperDefinitionData({
      project,
      baseline: null,
      requirements: null,
      scenarios: [],
      shape,
      pmArtifacts: [],
      existing,
    } as any)

    const capability = definition.capability_formalizations.find((item) => item.capability_id === 'gtm.prioritized_outreach_draft')
    expect(capability?.summary).toContain('include bounded enrichment context')
    expect(capability?.summary).not.toContain('Reviewed contract')
    expect(capability?.business_effects).toBeUndefined()
  })

  it('rejects source-declared capability shells before saving a developer definition', () => {
    const definition = buildDeveloperDefinitionData({
      project: {
        id: 'project-contract-shell',
        name: 'Canonical Revenue Review',
        domain: 'gtm',
        project_type: 'standard',
      },
      baseline: null,
      requirements: null,
      scenarios: [],
      shape: {
        id: 'shape-contract-shell',
        content_hash: 'shape-contract-shell-hash',
        data: {
          shape: {
            services: [
              {
                id: 'gtm-pipeline-service',
                name: 'Pipeline Service',
                capabilities: ['gtm.pipeline_summary'],
              },
            ],
          },
        },
      },
      pmArtifacts: [],
    } as any)

    const issues = validateDeveloperDefinitionRequiredFields(definition)
    expect(issues.map((issue) => issue.message)).toEqual(expect.arrayContaining([
      'Gtm.Pipeline Summary is a source-declared capability and must define concrete input contract details before saving.',
    ]))
  })

  it('uses pending developer assistant capability drafts as editable review state', () => {
    const definition = buildDeveloperDefinitionData({
      project: {
        id: 'project-pending-dev-draft',
        name: 'Canonical Revenue Review',
        domain: 'gtm',
        project_type: 'standard',
      },
      baseline: null,
      requirements: null,
      scenarios: [],
      shape: {
        id: 'shape-pending-dev-draft',
        content_hash: 'shape-pending-dev-draft-hash',
        data: {
          shape: {
            services: [
              {
                id: 'gtm-pipeline-service',
                name: 'Pipeline Service',
                capabilities: ['gtm.pipeline_summary'],
              },
            ],
          },
        },
      },
      pmArtifacts: [
        {
          id: 'assistant-draft-bundle-dev-test',
          project_id: 'project-pending-dev-draft',
          title: 'Developer Draft Bundle',
          data: {
            artifact_type: 'assistant_developer_design_draft_bundle',
            bundle: {
              sections: [
                {
                  id: 'capability_formalization',
                  status: 'proposed',
                  envelope: {
                    proposal: {
                      artifact_type: 'capability_formalization',
                      items: [
                        {
                          client_id: 'canonical-capability-inventory',
                          structured_data: {
                            capabilities: [
                              {
                                service_id: 'gtm-pipeline-service',
                                capability_id: 'gtm.pipeline_summary',
                                title: 'Pipeline Summary',
                                summary: 'Return governed pipeline summaries.',
                                intent_type: 'business_action',
                                operation_type: 'read',
                                side_effect_level: 'read',
                                backend_operation: 'gtm.pipeline_summary',
                                output_shape: 'governed_result',
                                inputs: [
                                  {
                                    input_name: 'quarter',
                                    input_type: 'string',
                                    required: true,
                                    summary: 'Reviewed quarter input.',
                                    semantic_type: 'time_scope',
                                  },
                                ],
                              },
                            ],
                          },
                        },
                      ],
                    },
                  },
                },
              ],
            },
          },
          created_at: '2026-05-26T00:00:00Z',
          updated_at: '2026-05-26T00:00:00Z',
        },
      ],
    } as any)

    const capability = definition.capability_formalizations.find((item) => item.capability_id === 'gtm.pipeline_summary')
    expect(capability?.inputs.map((input) => input.input_name)).toEqual(['quarter'])
    expect(validateDeveloperDefinitionRequiredFields(definition).map((issue) => issue.message)).not.toContain(
      'Gtm.Pipeline Summary is a source-declared capability and must define concrete input contract details before saving.',
    )
  })

  it('uses pending developer assistant input-contract sections as editable review state', () => {
    const definition = buildDeveloperDefinitionData({
      project: {
        id: 'project-pending-dev-input-section',
        name: 'Canonical Revenue Review',
        domain: 'gtm',
        project_type: 'standard',
      },
      baseline: null,
      requirements: null,
      scenarios: [],
      shape: {
        id: 'shape-pending-dev-input-section',
        content_hash: 'shape-pending-dev-input-section-hash',
        data: {
          shape: {
            services: [
              {
                id: 'gtm-pipeline-service',
                name: 'Pipeline Service',
                capabilities: ['gtm.pipeline_summary'],
              },
            ],
          },
        },
      },
      pmArtifacts: [
        {
          id: 'assistant-draft-bundle-dev-input-section',
          project_id: 'project-pending-dev-input-section',
          title: 'Developer Draft Bundle',
          data: {
            artifact_type: 'assistant_developer_design_draft_bundle',
            bundle: {
              sections: [
                {
                  id: 'input_contracts',
                  status: 'proposed',
                  envelope: {
                    proposal: {
                      artifact_type: 'input_contracts',
                      items: [
                        {
                          client_id: 'canonical-input-contracts',
                          structured_data: {
                            capabilities: [
                              {
                                capability_id: 'gtm.pipeline_summary',
                                inputs: [
                                  {
                                    input_name: 'quarter',
                                    input_type: 'string',
                                    required: true,
                                    summary: 'Reviewed quarter input.',
                                    semantic_type: 'time_scope',
                                  },
                                ],
                              },
                            ],
                          },
                        },
                      ],
                    },
                  },
                },
              ],
            },
          },
          created_at: '2026-05-26T00:00:00Z',
          updated_at: '2026-05-26T00:00:00Z',
        },
      ],
    } as any)

    const capability = definition.capability_formalizations.find((item) => item.capability_id === 'gtm.pipeline_summary')
    expect(capability?.inputs.map((input) => input.input_name)).toEqual(['quarter'])
    expect(validateDeveloperDefinitionRequiredFields(definition).map((issue) => issue.message)).not.toContain(
      'Gtm.Pipeline Summary is a source-declared capability and must define concrete input contract details before saving.',
    )
  })

  it('uses accepted assistant input-contract proposals as compiled capability inputs', () => {
    const definition = buildDeveloperDefinitionData({
      project: {
        id: 'project-accepted-input-contracts',
        name: 'Canonical Revenue Review',
        domain: 'gtm',
        project_type: 'standard',
      },
      baseline: null,
      requirements: null,
      scenarios: [],
      shape: {
        id: 'shape-accepted-input-contracts',
        content_hash: 'shape-accepted-input-contracts-hash',
        data: {
          shape: {
            services: [
              {
                id: 'gtm-pipeline-service',
                name: 'Pipeline Service',
                capabilities: ['gtm.pipeline_summary'],
              },
            ],
          },
        },
      },
      pmArtifacts: [
        {
          id: 'accepted-input-contracts',
          project_id: 'project-accepted-input-contracts',
          title: 'Accepted Input Contract Candidates',
          data: {
            artifact_type: 'assistant_input_contract_candidates',
            accepted_payload: [
              {
                client_id: 'pipeline-input-contract',
                structured_data: {
                  capabilities: [
                    {
                      capability_id: 'gtm.pipeline_summary',
                      inputs: [
                        {
                          input_name: 'quarter',
                          input_type: 'string',
                          required: true,
                          summary: 'Reviewed quarter input.',
                          semantic_type: 'time_scope',
                        },
                      ],
                    },
                  ],
                },
              },
            ],
            source_proposal: {
              items: [
                {
                  client_id: 'rejected-input-contract',
                  structured_data: {
                    capabilities: [
                      {
                        capability_id: 'gtm.pipeline_summary',
                        inputs: [
                          {
                            input_name: 'wrong_field',
                            input_type: 'string',
                            required: true,
                            summary: 'Rejected input that must not be compiled.',
                          },
                        ],
                      },
                    ],
                  },
                },
              ],
            },
          },
          created_at: '2026-05-26T00:00:00Z',
          updated_at: '2026-05-26T00:00:00Z',
        },
      ],
    } as any)

    const capability = definition.capability_formalizations.find((item) => item.capability_id === 'gtm.pipeline_summary')
    expect(capability?.inputs.map((input) => input.input_name)).toEqual(['quarter'])
    expect(validateDeveloperDefinitionRequiredFields(definition).map((issue) => issue.message)).not.toContain(
      'Gtm.Pipeline Summary is a source-declared capability and must define concrete input contract details before saving.',
    )
  })

  it('uses the newest accepted assistant input-contract artifact and preserves v0.24 input metadata', () => {
    const definition = buildDeveloperDefinitionData({
      project: {
        id: 'project-newest-input-contracts',
        name: 'Canonical Revenue Review',
        domain: 'gtm',
        project_type: 'standard',
      },
      baseline: null,
      requirements: null,
      scenarios: [],
      shape: {
        id: 'shape-newest-input-contracts',
        content_hash: 'shape-newest-input-contracts-hash',
        data: {
          shape: {
            services: [
              {
                id: 'gtm-enrichment-service',
                name: 'Enrichment Service',
                capabilities: ['gtm.account_enrichment_summary'],
              },
            ],
          },
        },
      },
      pmArtifacts: [
        {
          id: 'newest-input-contracts',
          project_id: 'project-newest-input-contracts',
          title: 'Newest Accepted Input Contracts',
          data: {
            artifact_type: 'assistant_input_contract_candidates',
            accepted_payload: [
              {
                structured_data: {
                  capabilities: [
                    {
                      capability_id: 'gtm.account_enrichment_summary',
                      inputs: [
                        {
                          input_name: 'account_names',
                          input_type: 'string',
                          required: true,
                          summary: 'Comma-separated account names.',
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
                },
              },
            ],
          },
          created_at: '2026-05-26T00:02:00Z',
          updated_at: '2026-05-26T00:02:00Z',
        },
        {
          id: 'older-input-contracts',
          project_id: 'project-newest-input-contracts',
          title: 'Older Accepted Input Contracts',
          data: {
            artifact_type: 'assistant_input_contract_candidates',
            accepted_payload: [
              {
                structured_data: {
                  capabilities: [
                    {
                      capability_id: 'gtm.account_enrichment_summary',
                      inputs: [
                        {
                          input_name: 'account_names',
                          input_type: 'string',
                          required: true,
                          summary: 'Older weaker account reference.',
                          semantic_type: 'entity_reference',
                          entity_reference: true,
                        },
                      ],
                    },
                  ],
                },
              },
            ],
          },
          created_at: '2026-05-26T00:01:00Z',
          updated_at: '2026-05-26T00:01:00Z',
        },
      ],
    } as any)

    const capability = definition.capability_formalizations.find((item) => item.capability_id === 'gtm.account_enrichment_summary')
    const accountNames = capability?.inputs.find((input) => input.input_name === 'account_names')

    expect(accountNames).toEqual(expect.objectContaining({
      summary: 'Comma-separated account names.',
      entity_reference: true,
      catalog_ref: 'gtm.account_catalog',
      resolution: expect.objectContaining({
        mode: 'backend_resolved',
        resolver_ref: 'gtm.account_catalog',
        on_missing: 'clarify',
        on_ambiguous: 'clarify',
        on_unresolved: 'clarify',
      }),
    }))
  })

  it('does not let accepted input-contract proposals overwrite capability metadata', () => {
    const definition = buildDeveloperDefinitionData({
      project: {
        id: 'project-input-contract-overlay',
        name: 'Canonical Revenue Review',
        domain: 'gtm',
        project_type: 'standard',
      },
      baseline: null,
      requirements: null,
      scenarios: [],
      shape: {
        id: 'shape-input-contract-overlay',
        content_hash: 'shape-input-contract-overlay-hash',
        data: {
          shape: {
            services: [
              {
                id: 'gtm-pipeline-service',
                name: 'Pipeline Service',
                capabilities: ['gtm.pipeline_summary'],
              },
            ],
          },
        },
      },
      pmArtifacts: [
        {
          id: 'accepted-capability-formalization',
          project_id: 'project-input-contract-overlay',
          title: 'Accepted Capability Formalization',
          data: {
            artifact_type: 'assistant_capability_formalization_candidates',
            accepted_payload: [
              {
                structured_data: {
                  capabilities: [
                    {
                      capability_id: 'gtm.pipeline_summary',
                      title: 'pipeline_summary',
                      summary: 'Return a bounded pipeline health summary for a quarter and optional scope.',
                      intent_type: 'read',
                      operation_type: 'summary',
                      side_effect_level: 'read_only',
                      output_intent: 'pipeline health visibility',
                      output_shape: 'gtm_pipeline_summary_result',
                      backend_operation: 'gtm.pipeline_summary',
                      path_template: '/gtm/pipeline-summary',
                      inputs: [
                        {
                          input_name: 'quarter',
                          input_type: 'string',
                          required: true,
                          summary: 'Quarter label like 2017-Q2',
                          semantic_type: 'time_scope',
                        },
                      ],
                    },
                  ],
                },
              },
            ],
          },
          created_at: '2026-05-26T00:00:00Z',
          updated_at: '2026-05-26T00:00:00Z',
        },
        {
          id: 'accepted-weak-capability-formalization',
          project_id: 'project-input-contract-overlay',
          title: 'Accepted Weak Capability Formalization',
          data: {
            artifact_type: 'assistant_capability_formalization_candidates',
            accepted_payload: [
              {
                structured_data: {
                  capabilities: [
                    {
                      capability_id: 'gtm.pipeline_summary',
                      title: 'Pipeline Summary',
                      summary: 'Reviewed contract for Pipeline Summary.',
                      intent_type: 'business_action',
                      operation_type: 'read',
                      side_effect_level: 'read',
                      output_intent: 'governed_result',
                      output_shape: 'governed_result',
                      inputs: [
                        {
                          input_name: 'owner_scope',
                          input_type: 'string',
                          required: false,
                          summary: 'Reviewed owner scope input.',
                          semantic_type: 'scope_reference',
                        },
                      ],
                    },
                  ],
                },
              },
            ],
          },
          created_at: '2026-05-26T00:00:30Z',
          updated_at: '2026-05-26T00:00:30Z',
        },
        {
          id: 'accepted-input-contracts',
          project_id: 'project-input-contract-overlay',
          title: 'Accepted Input Contract Candidates',
          data: {
            artifact_type: 'assistant_input_contract_candidates',
            accepted_payload: [
              {
                structured_data: {
                  capabilities: [
                    {
                      capability_id: 'gtm.pipeline_summary',
                      title: 'Pipeline Summary',
                      summary: 'Reviewed contract for Pipeline Summary.',
                      intent_type: 'business_action',
                      operation_type: 'read',
                      side_effect_level: 'read',
                      output_intent: 'governed_result',
                      output_shape: 'governed_result',
                      inputs: [
                        {
                          input_name: 'quarter',
                          input_type: 'string',
                          required: true,
                          summary: 'Reviewed quarter input.',
                          semantic_type: 'time_scope',
                        },
                        {
                          input_name: 'owner_scope',
                          input_type: 'string',
                          required: false,
                          summary: 'Reviewed owner scope input.',
                          semantic_type: 'scope_reference',
                        },
                      ],
                    },
                  ],
                },
              },
            ],
          },
          created_at: '2026-05-26T00:01:00Z',
          updated_at: '2026-05-26T00:01:00Z',
        },
      ],
    } as any)

    const capability = definition.capability_formalizations.find((item) => item.capability_id === 'gtm.pipeline_summary')
    expect(capability?.summary).toBe('Return a bounded pipeline health summary for a quarter and optional scope.')
    expect(capability?.operation_type).toBe('summary')
    expect(capability?.output_shape).toBe('gtm_pipeline_summary_result')
    expect(capability?.path_template).toBe('/gtm/pipeline-summary')
    expect(capability?.inputs.map((input) => input.input_name)).toEqual(['quarter', 'owner_scope'])
    expect(capability?.inputs.find((input) => input.input_name === 'quarter')?.summary).toBe('Reviewed quarter input.')
  })

  it('defaults cross-service audit posture from explicit service coordination', () => {
    const definition = buildDeveloperDefinitionData({
      project: {
        id: 'project-coordination',
        name: 'Coordination Project',
        domain: 'gtm',
        project_type: 'standard',
      },
      baseline: null,
      requirements: null,
      scenarios: [],
      shape: {
        id: 'shape-coordination',
        content_hash: 'shape-coordination-hash',
        data: {
          shape: {
            services: [
              {
                id: 'gtm-pipeline-service',
                name: 'Pipeline Service',
                capabilities: ['gtm.pipeline_summary'],
              },
              {
                id: 'gtm-outreach-service',
                name: 'Outreach Service',
                capabilities: ['gtm.draft_outreach_message'],
              },
            ],
            coordination: [
              {
                from: 'gtm-pipeline-service',
                to: 'gtm-outreach-service',
                relationship: 'handoff',
                description: 'Pipeline-selected accounts can flow into outreach drafting.',
              },
            ],
          },
        },
      },
      pmArtifacts: [],
    } as any)

    expect(definition.audit.service_handoffs_required).toBe(true)
    expect(definition.audit.cross_service_reconstruction_required).toBe(true)
    expect(definition.audit.cross_service_continuity_required).toBe(true)
  })

  it('does not silently infer composition when multiple source capabilities are plausible', () => {
    const pmArtifacts = [
      {
        id: 'product-summary',
        data: {
          artifact_type: 'product_summary',
          business_goals: [
            'Review account risk, pipeline risk, and prepare follow-up task previews without executing downstream mutations.',
          ],
          multi_step_composition_rules: [],
          supported_question_families: [],
          product_purpose: '',
          business_problem: '',
          approval_posture_summary: '',
          governed_behavior_summary: '',
          success_outcome_summary: '',
          why_now: '',
          lock_status: 'lockable',
        },
      },
      {
        id: 'assistant-capabilities',
        data: {
          artifact_type: 'assistant_capability_formalization_candidates',
          source_proposal: {
            items: [
              {
                structured_data: {
                  capabilities: [
                    {
                      capability_id: 'demo.account_risk_summary',
                      title: 'Account Risk Summary',
                      summary: 'Return ranked risky accounts for the requested business scope.',
                      service_id: 'demo-pipeline-service',
                      operation_type: 'read',
                      side_effect_level: 'read_only',
                      output_shape: 'risk_summary',
                    },
                    {
                      capability_id: 'demo.pipeline_risk_summary',
                      title: 'Pipeline Risk Summary',
                      summary: 'Return ranked risky pipeline items for the requested business scope.',
                      service_id: 'demo-pipeline-service',
                      operation_type: 'read',
                      side_effect_level: 'read_only',
                      output_shape: 'risk_summary',
                    },
                    {
                      capability_id: 'demo.prepare_followup_tasks',
                      title: 'Prepare Follow-up Tasks',
                      summary: 'Prepare follow-up task previews for selected risky accounts without executing the mutation.',
                      service_id: 'demo-pipeline-service',
                      intent_type: 'business_action',
                      operation_type: 'prepare',
                      side_effect_level: 'approval_required',
                      output_shape: 'followup_task_preview',
                      inputs: [
                        {
                          input_name: 'context',
                          input_type: 'object',
                          required: true,
                          summary: 'Derived account-risk context.',
                        },
                      ],
                    },
                  ],
                },
              },
            ],
          },
        },
      },
    ] as any

    const definition = buildDeveloperDefinitionData({
      project: {
        id: 'project-1',
        name: 'Revenue Review',
        domain: 'demo',
        project_type: 'standard',
      },
      baseline: null,
      requirements: null,
      scenarios: [],
      shape: {
        id: 'shape-1',
        content_hash: 'shape-hash',
        data: {
          shape: {
            services: [
              {
                id: 'demo-pipeline-service',
                name: 'Pipeline Service',
                capabilities: [
                  'demo.account_risk_summary',
                  'demo.pipeline_risk_summary',
                  'demo.prepare_followup_tasks',
                ],
              },
            ],
          },
        },
      },
      pmArtifacts,
    } as any)

    expect(definition.capability_formalizations.some((capability) => capability.kind === 'composed')).toBe(false)

    const ambiguities = findInferredCompositionAmbiguities({
      definition,
      pmArtifacts,
    })
    expect(ambiguities).toEqual([
      expect.objectContaining({
        sink_capability_id: 'demo.prepare_followup_tasks',
        top_candidates: expect.arrayContaining([
          expect.objectContaining({ capability_id: 'demo.account_risk_summary' }),
          expect.objectContaining({ capability_id: 'demo.pipeline_risk_summary' }),
        ]),
      }),
    ])
  })

  it('does not infer derived-target composition from content draft capabilities', () => {
    const definition = buildDeveloperDefinitionData({
      project: {
        id: 'project-1',
        name: 'Revenue Review',
        domain: 'demo',
        project_type: 'standard',
      },
      baseline: null,
      requirements: null,
      scenarios: [],
      shape: {
        id: 'shape-1',
        content_hash: 'shape-hash',
        data: {
          shape: {
            services: [
              {
                id: 'demo-pipeline-service',
                name: 'Pipeline Service',
                capabilities: [
                  'demo.bottleneck_outreach_draft',
                  'demo.prepare_followup_tasks',
                ],
              },
            ],
          },
        },
      },
      pmArtifacts: [
        {
          id: 'product-summary',
          data: {
            artifact_type: 'product_summary',
            business_goals: [
              'Review bottlenecks and prepare follow-up task previews without executing downstream mutations.',
            ],
            multi_step_composition_rules: [],
            supported_question_families: [],
            product_purpose: '',
            business_problem: '',
            approval_posture_summary: '',
            governed_behavior_summary: '',
            success_outcome_summary: '',
            why_now: '',
            lock_status: 'lockable',
          },
        },
        {
          id: 'assistant-capabilities',
          data: {
            artifact_type: 'assistant_capability_formalization_candidates',
            source_proposal: {
              items: [
                {
                  structured_data: {
                    capabilities: [
                      {
                        capability_id: 'demo.bottleneck_outreach_draft',
                        title: 'Bottleneck Outreach Draft',
                        summary: 'Draft outreach for a specific account already selected from bottleneck analysis.',
                        service_id: 'demo-pipeline-service',
                        operation_type: 'read',
                        side_effect_level: 'read',
                        output_intent: 'outreach_draft',
                        output_shape: 'bottleneck_outreach_draft',
                        business_effects: {
                          produces: ['content.draft'],
                          does_not_produce: ['external_dispatch'],
                        },
                        inputs: [
                          {
                            input_name: 'target_ref',
                            input_type: 'string',
                            required: true,
                            summary: 'Specific selected account.',
                          },
                        ],
                      },
                      {
                        capability_id: 'demo.prepare_followup_tasks',
                        title: 'Prepare Follow-up Tasks',
                        summary: 'Prepare follow-up task previews for derived bottleneck accounts without executing the mutation.',
                        service_id: 'demo-pipeline-service',
                        intent_type: 'business_action',
                        operation_type: 'prepare',
                        side_effect_level: 'approval_required',
                        output_shape: 'followup_task_preview',
                        inputs: [
                          {
                            input_name: 'context',
                            input_type: 'object',
                            required: true,
                            summary: 'Derived bottleneck account context.',
                          },
                        ],
                      },
                    ],
                  },
                },
              ],
            },
          },
        },
      ],
    } as any)

    expect(definition.capability_formalizations.some((capability) => capability.kind === 'composed')).toBe(false)
  })

  it('normalizes assistant-authored backend operation prose to a generator-safe capability id', () => {
    const definition = buildDeveloperDefinitionData({
      project: {
        id: 'project-1',
        name: 'Revenue Review',
        domain: 'demo',
        project_type: 'standard',
      },
      baseline: null,
      requirements: null,
      scenarios: [],
      shape: {
        id: 'shape-1',
        content_hash: 'shape-hash',
        data: {
          shape: {
            services: [
              {
                id: 'demo-pipeline-service',
                name: 'Pipeline Service',
                capabilities: ['demo.cross_service_preview'],
              },
            ],
          },
        },
      },
      pmArtifacts: [
        {
          id: 'assistant-capabilities',
          data: {
            artifact_type: 'assistant_capability_formalization_candidates',
            source_proposal: {
              items: [
                {
                  structured_data: {
                    capabilities: [
                      {
                        capability_id: 'demo.cross_service_preview',
                        title: 'Cross Service Preview',
                        summary: 'Preview a governed handoff without executing it.',
                        service_id: 'demo-pipeline-service',
                        operation_type: 'read',
                        side_effect_level: 'read',
                        backend_operation: 'cross-service composition',
                        output_shape: 'preview_result',
                      },
                    ],
                  },
                },
              ],
            },
          },
        },
      ],
    } as any)

    expect(
      definition.capability_formalizations.find((capability) =>
        capability.capability_id === 'demo.cross_service_preview',
      )?.backend_operation,
    ).toBe('demo.cross_service_preview')
  })
})
