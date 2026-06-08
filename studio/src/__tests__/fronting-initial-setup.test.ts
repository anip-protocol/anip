import { describe, expect, it } from 'vitest'
import { buildFrontingInitialSetupPlan } from '../design/fronting-initial-setup'
import {
  expandStarterTemplate,
  getStarterTemplate,
  starterTemplatesForProjectType,
  validateStarterTemplate,
} from '../design/starter-templates'

describe('fronting initial setup', () => {
  it('only seeds user-provided fronting intent and does not invent backend operations', () => {
    const plan = buildFrontingInitialSetupPlan({
      projectId: 'proj-notion',
      projectName: 'Notion Governed Fronting',
      domain: 'notion',
      brief: 'Govern selected Notion access behind ANIP capabilities.',
    })

    expect(plan.documents).toHaveLength(1)
    expect(plan.documents[0].kind).toBe('business_intent')
    expect(plan.documents[0].content).toContain('Govern selected Notion access behind ANIP capabilities.')
    expect(plan.documents[0].content).toContain('Studio must not invent backend operations')
    expect(plan.documents[0].content).not.toContain('POST /search')
    expect(plan.documents[0].content).not.toContain('MCP tool')
  })

  it('exposes Notion starter data only through an explicit starter template', () => {
    const template = getStarterTemplate('notion-fronting-starter')
    expect(template?.title).toBe('Notion Fronting Starter')
    expect(template?.anipSpecVersion).toBe('anip/0.24')
    expect(starterTemplatesForProjectType('governed_service_project').map((item) => item.id)).toContain('notion-fronting-starter')

    const expanded = expandStarterTemplate('proj-notion', template!)
    expect(expanded.documents).toHaveLength(2)
    expect(expanded.connections.map((connection) => connection.id)).toEqual([
      'proj-notion-notion-api',
      'proj-notion-notion-mcp',
    ])
    expect(expanded.discoveryRecords).toHaveLength(10)
    expect(expanded.capabilityMappings.map((mapping) => mapping.data.capability_id)).toEqual([
      'notion.workspace.search_context',
      'notion.database.query_context',
      'notion.page.create.prepare',
      'notion.page.update.prepare',
      'notion.comment.prepare',
    ])
    expect(expanded.capabilityMappings[0].data.template_suggested).toBe(true)
    expect(expanded.capabilityMappings[0].data.connection_ref).toBe('proj-notion-notion-api')
    expect(expanded.capabilityMappings[0].data.backend_bindings[0].matched_discovery_record_ids).toEqual([
      'proj-notion-native-api-workspace-search-context',
    ])
    expect(expanded.documents[1].content).toContain('Imported from starter template')
    expect(expanded.documents[1].content).toContain('POST /search')
  })

  it('loads the Jira starter from the shared fronting starter schema', () => {
    const template = getStarterTemplate('jira-fronting-starter')
    expect(template?.title).toBe('Jira Fronting Starter')
    expect(template?.anipSpecVersion).toBe('anip/0.24')

    const expanded = expandStarterTemplate('proj-jira', template!)
    expect(expanded.documents).toHaveLength(3)
    expect(expanded.connections.map((connection) => connection.id)).toEqual([
      'proj-jira-jira-api',
      'proj-jira-atlassian-mcp',
    ])
    expect(expanded.discoveryRecords).toHaveLength(23)
    expect(expanded.capabilityMappings.map((mapping) => mapping.data.capability_id)).toEqual([
      'jira.backlog.search_context',
      'jira.issue.get_context',
      'jira.incident_bug.prepare',
      'jira.story.prepare',
      'jira.subtask.prepare',
      'jira.customer_escalation.comment.prepare',
      'jira.workflow_transition.request',
      'jira.sprint_move.request',
      'jira.assignee_change.request',
      'jira.issue_link.request',
      'jira.release_notes.prepare',
    ])
    const backlogMapping = expanded.capabilityMappings[0].data
    expect(backlogMapping.service_id).toBe('jira-fronting')
    expect(expanded.capabilityMappings.find((mapping) =>
      mapping.data.capability_id === 'jira.workflow_transition.request'
    )?.data.service_id).toBe('jira-governance')
    expect(backlogMapping.inputs[0]).toMatchObject({
      input_name: 'project_key',
      semantic_type: 'project_scope',
      entity_reference: true,
      catalog_ref: 'jira.project_catalog',
      resolution: {
        mode: 'backend_resolved',
        resolver_ref: 'jira.project_catalog',
      },
    })
    const storySummaryInput = expanded.capabilityMappings
      .find((mapping) => mapping.data.capability_id === 'jira.story.prepare')
      ?.data.inputs.find((input) => input.input_name === 'summary')
    const transitionReasonInput = expanded.capabilityMappings
      .find((mapping) => mapping.data.capability_id === 'jira.workflow_transition.request')
      ?.data.inputs.find((input) => input.input_name === 'reason')
    expect(storySummaryInput?.semantic_type).toBe('work_item_summary')
    expect(transitionReasonInput?.semantic_type).toBe('business_reason')
    expect(backlogMapping.backend_bindings[0].matched_discovery_record_ids[0]).toContain(
      'jira-backlog-search-context-jira-rest-search-issues',
    )
    expect(expanded.documents[2].filename).toBe('jira-developer-evidence.template.md')
    expect(expanded.documents[2].content).toContain('## Reviewed Developer Evidence')
    expect(expanded.documents[2].content).toContain('first-class `integration_fronting_capability_mapping` records')
    expect(expanded.documents[2].content).toContain('| jira.backlog.search_context | jira-fronting | read | read |')
    expect(expanded.documents[2].content).toContain('| jira.adapter.execute.workflow_transition | jira-adapter | write | approval_required |')
    expect(expanded.documents[2].content).toContain('| jira.story.prepare | summary | string | yes | work_item_summary |')
    expect(expanded.documents[2].content).toContain('| jira.story.prepare | acceptance_criteria | array<string> | yes | acceptance_criteria |')
    expect(expanded.documents[2].content).toContain('| jira.customer_escalation.comment.prepare | context | string | yes | comment_context |')
    expect(expanded.documents[2].content).toContain('| jira.workflow_transition.request | reason | string | yes | business_reason |')

    const bugPrepareMapping = expanded.capabilityMappings.find((mapping) =>
      mapping.data.capability_id === 'jira.incident_bug.prepare'
    )?.data
    const workflowMapping = expanded.capabilityMappings.find((mapping) =>
      mapping.data.capability_id === 'jira.workflow_transition.request'
    )?.data
    expect(bugPrepareMapping?.side_effect_level).toBe('write_adjacent')
    expect(bugPrepareMapping?.execution_posture).toBe('prepare_only')
    expect(workflowMapping?.side_effect_level).toBe('approval_required')
    expect(workflowMapping?.execution_posture).toBe('prepare_only')
  })

  it('lets registry/import callers select which template source docs are seeded', () => {
    const template = getStarterTemplate('notion-fronting-starter')!
    const plan = buildFrontingInitialSetupPlan({
      projectId: 'proj-notion',
      projectName: 'Notion Governed Fronting',
      domain: 'notion',
      brief: 'Only import the business intent.',
      starterTemplate: template,
      selectedDocumentIdSuffixes: ['template-fronting-intent'],
    })

    expect(plan.documents).toHaveLength(1)
    expect(plan.documents[0].id).toBe('proj-notion-template-fronting-intent')
    expect(plan.documents[0].content).toContain('Only import the business intent.')
    expect(plan.documents[0].content).not.toContain('POST /databases/{database_id}/query')
  })

  it('rejects malformed starter template data before it can seed a project', () => {
    const template = JSON.parse(JSON.stringify(getStarterTemplate('notion-fronting-starter')))
    template.documents[0].filename = '../notion.md'
    template.documents[1].filename = 'integration-evidence.pdf'
    template.connections[0].secret_ref = 'secret-token-value'
    template.discoveryRecords[0].connectionIdSuffix = 'missing-connection'
    template.capabilityMappings[0].data.backend_bindings[0].matched_discovery_record_ids = ['missing-record']

    const errors = validateStarterTemplate(template)
    expect(errors).toContain('documents[0].filename must be a safe filename, not a path.')
    expect(errors).toContain('documents[1].filename must use the .md extension.')
    expect(errors).toContain('connections[0].secret_ref must be an environment-style reference, not a token value.')
    expect(errors).toContain('discoveryRecords[0].connectionIdSuffix must reference a template connection.')
    expect(errors).toContain(
      'capabilityMappings[0].data.backend_bindings[0].matched_discovery_record_ids must reference template discovery records.',
    )
  })

  it('rejects starter templates that do not match Studio ANIP spec exactly', () => {
    const template = JSON.parse(JSON.stringify(getStarterTemplate('notion-fronting-starter')))
    template.anipSpecVersion = 'anip/0.25'

    expect(validateStarterTemplate(template)).toContain(
      'anipSpecVersion must be anip/0.24.',
    )
  })
})
