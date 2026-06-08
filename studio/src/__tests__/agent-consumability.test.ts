import { describe, expect, it } from 'vitest'
import { buildAgentConsumabilityMetadata } from '../design/agent-consumability'
import type { DeveloperDefinitionData } from '../design/project-types'

function definition(): DeveloperDefinitionData {
  return {
    capability_formalizations: [
      {
        id: 'cap-enrich',
        source_kind: 'application_integration',
        service_id: 'gtm-enrichment-service',
        capability_id: 'gtm.account_enrichment_summary',
        title: 'Account Enrichment Summary',
        summary: 'Summarize enrichment for an explicit account cohort.',
        intent_type: 'summarize',
        operation_type: 'read',
        side_effect_level: 'read',
        business_effects: {
          produces: ['content.summary'],
          does_not_produce: ['raw_data_export', 'system.mutation'],
        },
        backend_operation: 'summarize_enrichment',
        path_template: '/capabilities/gtm.account_enrichment_summary',
        output_shape: 'account_enrichment_summary',
        inputs: [
          {
            input_name: 'account_names',
            input_type: 'string_list',
            required: true,
            summary: 'Explicit account cohort to enrich.',
            default_value: '',
            allowed_values: [],
            entity_reference: true,
          },
          {
            input_name: 'detail_level',
            input_type: 'string',
            required: false,
            summary: 'Summary depth.',
            default_value: '',
            allowed_values: ['summary', 'deep_dive'],
            entity_reference: false,
          },
        ],
      },
    ],
    scenario_formalizations: [],
    verification: null,
  } as unknown as DeveloperDefinitionData
}

describe('agent consumability metadata', () => {
  it('turns reviewed readiness decisions into structural consumer hints', () => {
    const metadata = buildAgentConsumabilityMetadata({
      definition: definition(),
      readiness: {
        artifact_type: 'agent_consumption_readiness',
        status: 'needs_review',
        score: 80,
        summary: {
          blockers: 0,
          warnings: 1,
          info: 0,
          probes: 1,
          required_app_glue: 1,
        },
        findings: [],
        probes: [],
        required_app_glue: [],
        finding_reviews: {
          'gtm.account_enrichment_summary:derived-target': {
            id: 'gtm.account_enrichment_summary:derived-target',
            decision: 'explicit_app_glue',
            note: 'The consuming app must select or provide the account cohort before invocation.',
            reviewed_at: '2026-04-28T00:00:00Z',
          },
        },
      },
    })

    const capability = metadata.capabilities['gtm.account_enrichment_summary']
    expect(metadata.schema_version).toBe('anip-agent-consumability/v0')
    expect(capability.intent.category).toBe('account.enrichment.summary')
    expect(capability.business_effects?.does_not_produce).toContain('raw_data_export')
    expect(capability.input_meanings?.detail_level?.summary).toBe('summary')
    expect(capability.app_boundaries?.unsupported_effects).toContain('raw_data_export')
    expect(capability.result_display?.primary_fields).toContain('result')
    expect(capability.required_context).toEqual([
      {
        input: 'account_names',
        missing_behavior: 'clarify_or_app_select',
      },
    ])
    expect(capability.app_glue?.required).toBe(true)
    expect(capability.derived_target_owner?.owner).toBe('app')
  })

  it('adds a derived target context hint when app glue has no declared input anchor', () => {
    const source = definition()
    source.capability_formalizations[0].inputs = []

    const metadata = buildAgentConsumabilityMetadata({
      definition: source,
      readiness: {
        artifact_type: 'agent_consumption_readiness',
        status: 'needs_review',
        score: 80,
        summary: {
          blockers: 0,
          warnings: 1,
          info: 0,
          probes: 1,
          required_app_glue: 1,
        },
        findings: [],
        probes: [],
        required_app_glue: [],
        finding_reviews: {
          'gtm.account_enrichment_summary:derived-target': {
            id: 'gtm.account_enrichment_summary:derived-target',
            decision: 'explicit_app_glue',
            note: 'The consuming app must select or provide the account cohort before invocation.',
            reviewed_at: '2026-04-28T00:00:00Z',
          },
        },
      },
    })

    expect(metadata.capabilities['gtm.account_enrichment_summary'].required_context).toEqual([
      {
        input: 'derived_target',
        missing_behavior: 'clarify_or_app_select',
      },
    ])
  })

  it('does not turn optional or defaulted inputs into required app-glue context', () => {
    const source = definition()
    source.capability_formalizations[0].inputs = [
      {
        input_name: 'target',
        input_type: 'string',
        required: true,
        summary: 'Explicit target.',
        default_value: '',
        allowed_values: [],
        entity_reference: true,
      },
      {
        input_name: 'channel',
        input_type: 'string',
        required: false,
        summary: 'Optional channel; service defaults when omitted.',
        default_value: 'email',
        allowed_values: ['email', 'linkedin'],
        entity_reference: false,
        semantic_type: 'message_context',
      },
      {
        input_name: 'persona',
        input_type: 'string',
        required: false,
        summary: 'Optional audience context.',
        default_value: '',
        allowed_values: [],
        entity_reference: true,
        semantic_type: 'message_context',
      },
    ]

    const metadata = buildAgentConsumabilityMetadata({
      definition: source,
      readiness: {
        artifact_type: 'agent_consumption_readiness',
        status: 'needs_review',
        score: 80,
        summary: {
          blockers: 0,
          warnings: 1,
          info: 0,
          probes: 1,
          required_app_glue: 1,
        },
        findings: [],
        probes: [],
        required_app_glue: [],
        finding_reviews: {
          'gtm.account_enrichment_summary:derived-target': {
            id: 'gtm.account_enrichment_summary:derived-target',
            decision: 'explicit_app_glue',
            note: 'The consuming app supplies the target.',
            reviewed_at: '2026-04-28T00:00:00Z',
          },
        },
      },
    })

    expect(metadata.capabilities['gtm.account_enrichment_summary'].required_context).toEqual([
      {
        input: 'target',
        missing_behavior: 'clarify_or_app_select',
      },
      {
        input: 'channel',
        missing_behavior: 'use_default',
      },
      {
        input: 'persona',
        missing_behavior: 'optional',
      },
    ])
  })

  it('applies manually reviewed intent rules without requiring an assistant', () => {
    const metadata = buildAgentConsumabilityMetadata({
      definition: definition(),
      manualReviews: {
        'gtm.account_enrichment_summary': {
          capability_id: 'gtm.account_enrichment_summary',
          reviewed_at: '2026-04-28T12:00:00Z',
          intent_category: 'account.enrichment.summary.reviewed',
          intent_summary: 'Summarize enrichment only after an explicit cohort is supplied or selected by the app.',
          app_glue_required: true,
          app_glue_reason: 'The app must select or ask for the account cohort before invoking the service.',
          intent_rules: [
            {
              id: 'explicit-cohort-required',
              meaning: 'User intent requires a concrete account cohort.',
              owner: 'agent_app_glue',
              applies_when: 'The user asks for enrichment of a vague review set.',
              agent_action: 'Ask for account names or select a reviewed cohort before invocation.',
              service_behavior: 'Clarify if account_names is omitted.',
            },
          ],
          business_language_rules: [
            {
              id: 'follow-up-purpose',
              meaning: 'Follow-up may describe the business purpose instead of outreach content.',
              owner: 'agent_app_glue',
              applies_when: {
                all_terms: ['follow-up'],
                any_terms: ['sales', 'account executive'],
                exclude_terms: ['draft', 'message'],
              },
              interpretation: 'Treat this as routing purpose unless content drafting is requested.',
              agent_action: 'treat_as_purpose',
            },
          ],
          app_boundaries: {
            conditional_approval_boundary: {
              when_missing: ['account_names'],
              produces: ['approval.request', 'system.preview_mutation'],
            },
          },
          selection_hints: [
            {
              capability: 'gtm.account_enrichment_summary',
              all_terms: ['enrich'],
              any_terms: ['account'],
            },
          ],
        },
      },
    })

    const capability = metadata.capabilities['gtm.account_enrichment_summary']
    expect(capability.intent.category).toBe('account.enrichment.summary.reviewed')
    expect(capability.intent.summary).toContain('explicit cohort')
    expect(capability.app_glue?.reason).toContain('select or ask')
    expect(capability.app_boundaries?.conditional_approval_boundary?.when_missing).toEqual(['account_names'])
    expect(capability.intent_rules?.[0].id).toBe('explicit-cohort-required')
    expect(capability.business_language_rules?.[0].id).toBe('follow-up-purpose')
    expect(capability.review?.source).toBe('manual_review')
    expect(metadata.selection_hints?.[0].capability).toBe('gtm.account_enrichment_summary')
  })

  it('merges generated app boundaries with manual reviews and drops unknown effect ids', () => {
    const source = definition()
    source.capability_formalizations[0] = {
      ...source.capability_formalizations[0],
      business_effects: {
        produces: ['content.draft'],
        does_not_produce: ['external_dispatch', 'system.mutation', 'raw_data_export'],
      },
    }

    const metadata = buildAgentConsumabilityMetadata({
      definition: source,
      manualReviews: {
        'gtm.account_enrichment_summary': {
          capability_id: 'gtm.account_enrichment_summary',
          reviewed_at: '2026-04-28T12:00:00Z',
          app_boundaries: {
            guidance: 'Reviewed guidance.',
            unsupported_effects: ['external_send', 'approval.execute'],
          },
        },
      },
    })

    expect(metadata.capabilities['gtm.account_enrichment_summary'].app_boundaries).toEqual({
      guidance: 'Reviewed guidance.',
      unsupported_effects: ['external_dispatch', 'system.mutation', 'raw_data_export', 'approval.execute'],
    })
  })

  it('derives approval-consumption hints from grant-governed capabilities', () => {
    const source = definition()
    source.capability_formalizations[0] = {
      ...source.capability_formalizations[0],
      capability_id: 'gtm.prepare_followup_tasks',
      title: 'Prepare Follow-up Tasks',
      summary: 'Prepare follow-up tasks for high-risk accounts without executing downstream mutations.',
      operation_type: 'approval_gated',
      side_effect_level: 'approval_required',
      business_effects: {
        produces: ['data.read'],
        does_not_produce: ['raw_data_export'],
      },
      grant_policy: {
        allowed_grant_types: ['one_time', 'session_bound'],
        default_grant_type: 'one_time',
        expires_in_seconds: 900,
        max_uses: 1,
      },
    }

    const metadata = buildAgentConsumabilityMetadata({ definition: source })
    const capability = metadata.capabilities['gtm.prepare_followup_tasks']

    expect(capability.business_effects?.produces).toContain('approval.request')
    expect(capability.business_effects?.produces).toContain('system.preview_mutation')
    expect(capability.business_effects?.produces).not.toContain('data.read')
    expect(capability.business_effects?.does_not_produce).toContain('approval.execute')
    expect(capability.approval?.required).toBe(true)
    expect(capability.app_boundaries?.guidance).toContain('approval-governed')
    expect(capability.result_display?.style).toContain('approval requirement')
  })
})
