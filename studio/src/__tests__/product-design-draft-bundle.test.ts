import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  bundleOpenQuestions,
  draftProductDesignBundle,
  redraftProductDesignSection,
  saveAcceptedProductDesignSection,
  type ProductDesignDraftBundle,
  type ProductDesignDraftSection,
} from '../design/product-design-draft-bundle'
import {
  isPermissionIntentComplete,
  PERMISSION_INTENT_FALLBACK_REVIEW_NOTE,
} from '../design/product-design'
import type { ArtifactRecord, AssistantProposalEnvelope } from '../design/project-types'

const api = vi.hoisted(() => ({
  createPmArtifact: vi.fn(),
  createRequirements: vi.fn(),
  createScenario: vi.fn(),
  createShape: vi.fn(),
  setRequirementsRole: vi.fn(),
  updatePmArtifact: vi.fn(),
}))

const assistant = vi.hoisted(() => ({
  runPmAssistantAction: vi.fn(),
}))

vi.mock('../design/project-api', async () => {
  const actual = await vi.importActual<typeof import('../design/project-api')>('../design/project-api')
  return {
    ...actual,
    ...api,
  }
})

vi.mock('../design/assistant-actions', async () => {
  const actual = await vi.importActual<typeof import('../design/assistant-actions')>('../design/assistant-actions')
  return {
    ...actual,
    runPmAssistantAction: (...args: any[]) => assistant.runPmAssistantAction(...args),
  }
})

function project() {
  return {
    id: 'proj-1',
    workspace_id: 'workspace-1',
    name: 'Revenue Assistant',
    domain: 'revenue',
    summary: '',
    labels: [],
    created_at: '2026-04-20T00:00:00Z',
    updated_at: '2026-04-20T00:00:00Z',
    requirements_count: 0,
    scenarios_count: 0,
    proposals_count: 0,
    shapes_count: 0,
    evaluations_count: 0,
    documents_count: 0,
  }
}

function patchEnvelope(): AssistantProposalEnvelope {
  return {
    title: 'Business Summary Proposal',
    summary: 'Draft summary.',
    mode: 'pm',
    capability: 'propose_business_summary',
    questions_for_user: ['Which actions require approval?'],
    watchouts: [],
    next_steps: [],
    proposal: {
      proposal_kind: 'patch_candidates',
      artifact_type: 'product_summary',
      patches: [
        {
          path: '/product_purpose',
          op: 'replace',
          value: 'Help revenue teams answer governed questions.',
          rationale: 'Purpose comes from source.',
        },
        {
          path: '/business_goals/-',
          op: 'add',
          value: 'Answer governed revenue questions faster.',
          rationale: 'Goal comes from source.',
        },
      ],
    },
  }
}

function candidateEnvelope(artifactType: 'requirements' | 'scenarios'): AssistantProposalEnvelope {
  return {
    title: `${artifactType} proposal`,
    summary: 'Candidate blocks.',
    mode: 'pm',
    capability: artifactType === 'requirements' ? 'propose_requirements' : 'propose_scenarios',
    questions_for_user: [],
    watchouts: [],
    next_steps: [],
    proposal: {
      proposal_kind: 'candidate_blocks',
      artifact_type: artifactType,
      items: [
        {
          client_id: 'item-1',
          title: 'Preserve governed approval stops',
          body: 'The system must stop for approval before high-impact actions.',
          confidence: 'high',
          rationale: 'Approval appears in the source.',
        },
      ],
    },
  }
}

function serviceDesignEnvelope(): AssistantProposalEnvelope {
  return {
    title: 'Service Design proposal',
    summary: 'Candidate service shape.',
    mode: 'pm',
    capability: 'propose_service_design',
    questions_for_user: [],
    watchouts: [],
    next_steps: [],
    proposal: {
      proposal_kind: 'candidate_blocks',
      artifact_type: 'service_design',
      items: [
        {
          client_id: 'shape-1',
          title: 'Revenue service shape',
          body: 'Pipeline coordinates with outreach and enrichment.',
          confidence: 'high',
          rationale: 'Source names the service handoffs.',
          structured_data: {
            shape: {
              id: 'revenue-shape',
              name: 'Revenue Shape',
              services: [
                { id: 'pipeline', name: 'Pipeline Service', role: 'Pipeline review.', capabilities: ['demo.pipeline_summary'] },
                { id: 'outreach', name: 'Outreach Service', role: 'Outreach drafts.', capabilities: ['demo.outreach_draft'] },
                { id: 'enrichment', name: 'Enrichment Service', role: 'Enrichment.', capabilities: ['demo.enrichment_summary'] },
              ],
              coordination: [
                { from: 'pipeline', to: 'outreach', relationship: 'handoff' },
                { from: 'pipeline', to: 'enrichment', relationship: 'handoff' },
              ],
            },
          },
        },
      ],
    },
  }
}

function existingScenario(participatingServices: string[]): ArtifactRecord {
  return {
    id: 'scn-existing',
    project_id: 'proj-1',
    title: 'Existing scenario',
    status: 'draft',
    created_at: '2026-04-20T00:00:00Z',
    updated_at: '2026-04-20T00:00:00Z',
    content_hash: 'scn-existing-hash',
    data: {
      scenario: {
        name: 'existing',
        participating_services: participatingServices,
      },
    },
  }
}

function section(overrides: Partial<ProductDesignDraftSection>): ProductDesignDraftSection {
  return {
    id: 'business_summary',
    title: 'Business Summary',
    action: 'business_summary',
    envelope: patchEnvelope(),
    selectedIds: ['0', '1'],
    status: 'proposed',
    ...overrides,
  }
}

describe('product-design-draft-bundle', () => {
  beforeEach(() => {
    Object.values(api).forEach((mock) => mock.mockReset())
    assistant.runPmAssistantAction.mockReset()
    api.createRequirements.mockResolvedValue({ id: 'req-1' })
  })

  it('collects clarification questions across the bundle', () => {
    const bundle: ProductDesignDraftBundle = {
      title: 'Draft',
      summary: 'Summary',
      sourceText: 'Source',
      createdAt: '2026-04-20T00:00:00Z',
      sections: [section({})],
    }

    expect(bundleOpenQuestions(bundle)).toEqual(['Business Summary: Which actions require approval?'])
  })

  it('passes in-flight Product Design context to later Autopilot sections', async () => {
    assistant.runPmAssistantAction.mockImplementation(async (action: string, args: { sourceText: string }) => {
      if (action === 'actor_model') {
        return {
          title: 'Actor Model',
          summary: 'Actors.',
          mode: 'pm',
          capability: 'propose_actor_model',
          questions_for_user: [],
          watchouts: [],
          next_steps: [],
          proposal: {
            proposal_kind: 'patch_candidates',
            artifact_type: 'actor_model',
            patches: [
              {
                path: '/actors/-',
                op: 'add',
                value: {
                  actor_id: 'sales_leader',
                  title: 'Sales Leader',
                  summary: 'Reviews governed GTM work.',
                  visibility_expectations: '',
                  action_expectations: '',
                  approval_expectations: '',
                  notes: '',
                },
                rationale: 'Source names the actor.',
              },
            ],
          },
        }
      }
      if (action === 'business_areas') {
        return {
          title: 'Business Areas',
          summary: 'Areas.',
          mode: 'pm',
          capability: 'propose_business_areas',
          questions_for_user: [],
          watchouts: [],
          next_steps: [],
          proposal: {
            proposal_kind: 'patch_candidates',
            artifact_type: 'business_areas',
            patches: [
              {
                path: '/entries/-',
                op: 'add',
                value: {
                  business_area_id: 'pipeline_health',
                  label: 'Pipeline Health',
                  description: 'Bounded pipeline review.',
                },
                rationale: 'Source names the area.',
              },
            ],
          },
        }
      }
      if (action === 'permission_intent') {
        expect(args.sourceText).toContain('In-flight Product Design Context')
        expect(args.sourceText).toContain('## Actor IDs')
        expect(args.sourceText).toContain('- `sales_leader`')
        expect(args.sourceText).toContain('## Business Area IDs')
        expect(args.sourceText).toContain('- `pipeline_health`')
      }
      if (action === 'requirements' || action === 'scenarios') return candidateEnvelope(action)
      if (action === 'service_design') return serviceDesignEnvelope()
      return patchEnvelope()
    })

    await draftProductDesignBundle({
      projectId: 'proj-1',
      projectName: 'Revenue Assistant',
      sourceText: 'Source brief.',
      useDeterministic: true,
    })

    expect(assistant.runPmAssistantAction).toHaveBeenCalledWith(
      'permission_intent',
      expect.objectContaining({
        sourceText: expect.stringContaining('In-flight Product Design Context'),
      }),
    )
  })

  it('saves accepted patch candidates into canonical PM artifacts', async () => {
    await saveAcceptedProductDesignSection({
      project: project(),
      section: section({}),
      pmArtifacts: [],
    })

    expect(api.createPmArtifact).toHaveBeenCalledWith('proj-1', expect.objectContaining({
      id: 'proj-1-product_summary',
      title: 'Business Summary',
      data: expect.objectContaining({
        artifact_type: 'product_summary',
        product_purpose: 'Help revenue teams answer governed questions.',
        business_goals: ['Answer governed revenue questions faster.'],
      }),
    }))
  })

  it('saves accepted requirement candidates as a deterministic requirements artifact', async () => {
    await saveAcceptedProductDesignSection({
      project: project(),
      section: section({
        id: 'requirements',
        title: 'Requirements',
        action: 'requirements',
        envelope: candidateEnvelope('requirements'),
        selectedIds: ['item-1'],
      }),
      pmArtifacts: [],
    })

    expect(api.createRequirements).toHaveBeenCalledWith('proj-1', expect.objectContaining({
      title: 'Preserve governed approval stops',
      data: expect.objectContaining({
        business_constraints: expect.objectContaining({
          assistant_drafted_requirements_count: 1,
          assistant_drafted_requirements_summary: 'Preserve governed approval stops: The system must stop for approval before high-impact actions.',
        }),
      }),
    }))
    expect(api.setRequirementsRole).toHaveBeenCalledWith('proj-1', 'req-1', 'primary')
  })

  it('creates reviewable fallback permission rules from a policy-summary-only assistant draft', async () => {
    await saveAcceptedProductDesignSection({
      project: project(),
      section: section({
        id: 'permission_intent',
        title: 'Permission Intent',
        action: 'permission_intent',
        envelope: {
          title: 'Permission Intent Proposal',
          summary: 'Policy only.',
          mode: 'pm',
          capability: 'propose_permission_intent',
          questions_for_user: ['Which actors can approve operational previews?'],
          watchouts: [],
          next_steps: [],
          proposal: {
            proposal_kind: 'patch_candidates',
            artifact_type: 'permission_intent',
            patches: [
              {
                path: '/policy_summary',
                op: 'replace',
                value: 'The product should preserve bounded access and approval stops.',
                rationale: 'The assistant did not provide concrete actor-by-business-area rules.',
              },
            ],
          },
        },
        selectedIds: ['0'],
      }),
      pmArtifacts: [
        {
          id: 'actors',
          project_id: 'proj-1',
          title: 'Actor Model',
          status: 'draft',
          created_at: '2026-04-20T00:00:00Z',
          updated_at: '2026-04-20T00:00:00Z',
          content_hash: 'actors',
          data: {
            artifact_type: 'actor_model',
            actors: [{ actor_id: 'sales_leader', title: 'Sales Leader', summary: 'Reviews governed work.', visibility_expectations: '', action_expectations: '', approval_expectations: '', notes: '' }],
          },
        },
        {
          id: 'areas',
          project_id: 'proj-1',
          title: 'Business Areas',
          status: 'draft',
          created_at: '2026-04-20T00:00:00Z',
          updated_at: '2026-04-20T00:00:00Z',
          content_hash: 'areas',
          data: {
            artifact_type: 'business_areas',
            entries: [{ business_area_id: 'pipeline_health', label: 'Pipeline Health', description: 'Bounded pipeline review.' }],
          },
        },
      ],
    })

    expect(api.createPmArtifact).toHaveBeenCalledWith('proj-1', expect.objectContaining({
      data: expect.objectContaining({
        artifact_type: 'permission_intent',
        policy_summary: 'The product should preserve bounded access and approval stops.',
        rules: [
          expect.objectContaining({
            actor_id: 'sales_leader',
            business_area: 'pipeline_health',
            access_posture: 'bounded',
            governed_outcome_type: 'bounded_result',
            review_source: 'studio_fallback_needs_review',
            notes: expect.stringContaining(PERMISSION_INTENT_FALLBACK_REVIEW_NOTE),
          }),
        ],
      }),
    }))
  })

  it('does not count legacy fallback permission rules as complete', () => {
    expect(isPermissionIntentComplete({
      artifact_type: 'permission_intent',
      policy_summary: 'Bounded policy.',
      rules: [
        {
          actor_id: 'sales_leader',
          business_area: 'pipeline_health',
          access_posture: 'bounded',
          governed_outcome_type: 'bounded_result',
          governed_outcome: 'Allow bounded pipeline review.',
          notes: `${PERMISSION_INTENT_FALLBACK_REVIEW_NOTE} Confirm or edit before locking Product Design.`,
        },
      ],
    })).toBe(false)
  })

  it('saves accepted scenario candidates as deterministic scenario artifacts', async () => {
    await saveAcceptedProductDesignSection({
      project: project(),
      section: section({
        id: 'scenarios',
        title: 'Scenarios',
        action: 'scenarios',
        envelope: candidateEnvelope('scenarios'),
        selectedIds: ['item-1'],
      }),
      pmArtifacts: [],
    })

    expect(api.createScenario).toHaveBeenCalledWith('proj-1', expect.objectContaining({
      title: 'Preserve governed approval stops',
      data: expect.objectContaining({
        scenario: expect.objectContaining({
          narrative: 'The system must stop for approval before high-impact actions.',
        }),
      }),
    }))
  })

  it('fills missing governed fronting capability scenarios from mapping artifacts', async () => {
    const envelope = candidateEnvelope('scenarios')
    ;(envelope.proposal as any).items[0].structured_data = {
      scenario: {
        name: 'search-backlog-context',
        category: 'observability',
        narrative: 'Search bounded backlog context.',
        context: { capability: 'jira.backlog.search_context' },
        expected_behavior: ['Return bounded context.'],
        expected_anip_support: ['Preserve the governed capability boundary.'],
      },
    }

    await saveAcceptedProductDesignSection({
      project: { ...project(), project_type: 'governed_service_project' },
      section: section({
        id: 'scenarios',
        title: 'Scenarios',
        action: 'scenarios',
        envelope,
        selectedIds: ['item-1'],
      }),
      pmArtifacts: [
        {
          id: 'map-backlog',
          project_id: 'proj-1',
          title: 'Backlog Mapping',
          status: 'draft',
          created_at: '2026-04-20T00:00:00Z',
          updated_at: '2026-04-20T00:00:00Z',
          content_hash: 'map-backlog',
          data: {
            artifact_type: 'integration_fronting_capability_mapping',
            capability_id: 'jira.backlog.search_context',
            service_id: 'jira.fronting',
            side_effect_level: 'read',
          },
        },
        {
          id: 'map-link',
          project_id: 'proj-1',
          title: 'Issue Link Mapping',
          status: 'draft',
          created_at: '2026-04-20T00:00:00Z',
          updated_at: '2026-04-20T00:00:00Z',
          content_hash: 'map-link',
          data: {
            artifact_type: 'integration_fronting_capability_mapping',
            capability_id: 'jira.issue_link.request',
            service_id: 'jira.governance',
            side_effect_level: 'system.mutation',
            intent: 'Request linking two Jira issues with cross-project policy checks.',
          },
        },
      ],
      scenarios: [],
    })

    expect(api.createScenario).toHaveBeenCalledTimes(2)
    expect(api.createScenario).toHaveBeenLastCalledWith('proj-1', expect.objectContaining({
      title: 'Review Jira Issue Link Request capability behavior',
      data: expect.objectContaining({
        scenario: expect.objectContaining({
          category: 'safety',
          context: expect.objectContaining({
            capability: 'jira.issue_link.request',
            source: 'studio_fronting_template_coverage',
          }),
        }),
      }),
    }))
  })

  it('adds service-coordination coverage scenarios when Service Design declares uncovered edges', async () => {
    await saveAcceptedProductDesignSection({
      project: { ...project(), project_type: 'governed_service_project' },
      section: section({
        id: 'service_design',
        title: 'Service Design',
        action: 'service_design',
        envelope: serviceDesignEnvelope(),
        selectedIds: ['shape-1'],
      }),
      pmArtifacts: [],
      requirements: [{ id: 'req-1', project_id: 'proj-1', title: 'Requirements', role: 'primary', data: {}, content_hash: 'req-hash', created_at: '2026-04-20T00:00:00Z', updated_at: '2026-04-20T00:00:00Z' }],
      scenarios: [existingScenario(['pipeline', 'outreach'])],
    })

    expect(api.createShape).toHaveBeenCalledWith('proj-1', expect.objectContaining({
      title: 'Assistant-Drafted Service Shape',
    }))
    expect(api.createScenario).toHaveBeenCalledTimes(1)
    expect(api.createScenario).toHaveBeenCalledWith('proj-1', expect.objectContaining({
      title: 'Review Pipeline Service to Enrichment Service handoff',
      data: expect.objectContaining({
        scenario: expect.objectContaining({
          category: 'cross_service',
          participating_services: ['pipeline', 'enrichment'],
        }),
      }),
    }))
  })

  it('filters invented internal capabilities from assistant Service Design before saving', async () => {
    const envelope = serviceDesignEnvelope()
    const shape = ((envelope.proposal as any).items[0].structured_data.shape)
    shape.services[0].capabilities = [
      'jira.backlog.search_context',
      'jira.execution.transition_issue',
      'jira.adapter.execute.workflow_transition',
    ]

    await saveAcceptedProductDesignSection({
      project: { ...project(), project_type: 'governed_service_project' },
      section: section({
        id: 'service_design',
        title: 'Service Design',
        action: 'service_design',
        envelope,
        selectedIds: ['shape-1'],
      }),
      pmArtifacts: [],
      requirements: [{ id: 'req-1', project_id: 'proj-1', title: 'Requirements', role: 'primary', data: {}, content_hash: 'req-hash', created_at: '2026-04-20T00:00:00Z', updated_at: '2026-04-20T00:00:00Z' }],
      scenarios: [],
      sourceText: [
        '## Template-suggested capabilities',
        '- jira.backlog.search_context: Search bounded backlog context.',
        '- jira.workflow_transition.request: Request a workflow transition.',
      ].join('\n'),
    })

    expect(api.createShape).toHaveBeenCalledWith('proj-1', expect.objectContaining({
      data: expect.objectContaining({
        shape: expect.objectContaining({
          services: expect.arrayContaining([
            expect.objectContaining({
              id: 'pipeline',
              capabilities: ['jira.backlog.search_context'],
            }),
          ]),
          notes: expect.arrayContaining([
            expect.stringContaining('jira.execution.transition_issue'),
          ]),
        }),
      }),
    }))
  })

  it('does not apply fronting capability allow-list filtering to standard projects', async () => {
    const envelope = serviceDesignEnvelope()
    const shape = ((envelope.proposal as any).items[0].structured_data.shape)
    shape.services[0].capabilities = [
      'gtm.pipeline_summary',
      'gtm.pipeline_forecast_summary',
    ]

    await saveAcceptedProductDesignSection({
      project: { ...project(), project_type: 'standard' },
      section: section({
        id: 'service_design',
        title: 'Service Design',
        action: 'service_design',
        envelope,
        selectedIds: ['shape-1'],
      }),
      pmArtifacts: [],
      requirements: [{ id: 'req-1', project_id: 'proj-1', title: 'Requirements', role: 'primary', data: {}, content_hash: 'req-hash', created_at: '2026-04-20T00:00:00Z', updated_at: '2026-04-20T00:00:00Z' }],
      scenarios: [],
      sourceText: [
        '## Template-suggested capabilities',
        '- jira.backlog.search_context: Search bounded backlog context.',
      ].join('\n'),
    })

    expect(api.createShape).toHaveBeenCalledWith('proj-1', expect.objectContaining({
      data: expect.objectContaining({
        shape: expect.objectContaining({
          services: expect.arrayContaining([
            expect.objectContaining({
              id: 'pipeline',
              capabilities: ['gtm.pipeline_summary', 'gtm.pipeline_forecast_summary'],
            }),
          ]),
        }),
      }),
    }))
  })

  it('redrafts one PM section with answered clarification context', async () => {
    assistant.runPmAssistantAction.mockResolvedValue(candidateEnvelope('requirements'))

    const result = await redraftProductDesignSection({
      projectId: 'proj-1',
      sourceText: 'business spec plus answers',
      sourceRequirementsId: 'req-1',
      section: section({
        id: 'requirements',
        title: 'Requirements',
        action: 'requirements',
        clarificationAnswers: { 'q-1': 'Approval must stop before write actions.' },
      }),
    })

    expect(assistant.runPmAssistantAction).toHaveBeenCalledWith('requirements', {
      projectId: 'proj-1',
      sourceText: 'business spec plus answers',
      sourceRequirementsId: 'req-1',
      serviceTopologyPreference: undefined,
    })
    expect(result.status).toBe('proposed')
    expect(result.selectedIds).toEqual(['item-1'])
    expect(result.clarificationAnswers).toEqual({ 'q-1': 'Approval must stop before write actions.' })
  })
})
