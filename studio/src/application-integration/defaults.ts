import type {
  ApplicationIntegrationBackendType,
  ApplicationIntegrationGeneratedOutput,
  ApplicationIntegrationImplementationLanguage,
  ApplicationIntegrationProjectState,
} from './types'

export type ApplicationIntegrationSeedProfile =
  | 'salesforce_crm_basic'
  | 'zendesk_support_basic'
  | 'hubspot_crm_basic'
  | 'github_issues_basic'
  | 'mcp_knowledge_basic'

export const APPLICATION_INTEGRATION_BACKEND_OPTIONS: Array<{
  value: ApplicationIntegrationBackendType
  label: string
  description: string
}> = [
  {
    value: 'rest_api',
    label: 'REST API',
    description: 'Front an existing REST API with a governed ANIP interaction model.',
  },
  {
    value: 'graphql_api',
    label: 'GraphQL API',
    description: 'Front a GraphQL API with bounded capabilities and governed outcomes.',
  },
  {
    value: 'mcp_server',
    label: 'MCP Server',
    description: 'Front an MCP-backed tool server with bounded capabilities and governed outcomes.',
  },
  {
    value: 'internal_http_service',
    label: 'Internal HTTP Service',
    description: 'Front an internal service API without forcing a service rewrite.',
  },
  {
    value: 'custom_adapter',
    label: 'Custom Adapter',
    description: 'Generate a starter scaffold for a custom backend adapter.',
  },
]

export const APPLICATION_INTEGRATION_IMPLEMENTATION_LANGUAGE_OPTIONS: Array<{
  value: ApplicationIntegrationImplementationLanguage
  label: string
  description: string
}> = [
  {
    value: 'typescript',
    label: 'TypeScript',
    description: 'Generate TypeScript-first ANIP service and adapter starter files.',
  },
  {
    value: 'python',
    label: 'Python',
    description: 'Generate Python-first ANIP service and adapter starter files.',
  },
]

export const APPLICATION_INTEGRATION_SEED_OPTIONS: Array<{
  value: ApplicationIntegrationSeedProfile
  label: string
  description: string
}> = [
  {
    value: 'salesforce_crm_basic',
    label: 'Salesforce CRM Basic',
    description: 'Bounded account, contact, and follow-up task workflow with approval-gated writes.',
  },
  {
    value: 'zendesk_support_basic',
    label: 'Zendesk Support Basic',
    description: 'Bounded ticket, requester, and internal-note workflow with approval-gated support writes.',
  },
  {
    value: 'hubspot_crm_basic',
    label: 'HubSpot CRM Basic',
    description: 'Bounded company, contact, and follow-up workflow with approval-gated CRM writes.',
  },
  {
    value: 'github_issues_basic',
    label: 'GitHub Issues Basic',
    description: 'Bounded repository issue lookup, issue summary, and approval-gated issue comment workflow over GitHub GraphQL.',
  },
  {
    value: 'mcp_knowledge_basic',
    label: 'MCP Knowledge Basic',
    description: 'Bounded MCP-backed knowledge search, note retrieval, and approval-gated note creation.',
  },
]

function nowIso(): string {
  return new Date().toISOString()
}

function defaultAdapterTarget(
  backendType: ApplicationIntegrationBackendType,
  seedProfile: ApplicationIntegrationSeedProfile,
): string {
  if (seedProfile === 'github_issues_basic') return 'generated-backend-template:graphql'

  if (backendType === 'graphql_api') return 'generated-backend-template:graphql'
  if (backendType === 'mcp_server') return 'generated-backend-template:mcp'
  if (backendType === 'internal_http_service') return 'generated-backend-template:native-api'
  if (backendType === 'custom_adapter') return 'generated-backend-template:custom'

  if (seedProfile === 'salesforce_crm_basic') return 'generated-backend-template:native-api'
  if (seedProfile === 'zendesk_support_basic') return 'generated-backend-template:native-api'
  if (seedProfile === 'hubspot_crm_basic') return 'generated-backend-template:native-api'
  if (seedProfile === 'mcp_knowledge_basic') return 'generated-backend-template:mcp'

  switch (backendType) {
    case 'rest_api':
    default:
      return 'generated-backend-template:native-api'
  }
}

function buildSalesforceProfile(
  title: string,
  summary: string,
  backendType: ApplicationIntegrationBackendType,
  timestamp: string,
): ApplicationIntegrationProjectState {
  return {
    kind: 'application_integration',
    version: 1,
    title,
    summary: summary || 'Governed interaction model for bounded CRM account, contact, and follow-up task flows.',
    backend: {
      backendType,
      systemName: 'Salesforce CRM',
      environment: 'production',
      baseUrl: 'https://example.my.salesforce.com',
      authType: 'oauth2',
      authNotes: 'Use delegated OAuth plus approval gating for write capabilities.',
      adapterTarget: defaultAdapterTarget(backendType, 'salesforce_crm_basic'),
      seedProfile: 'salesforce_crm_basic',
      implementationLanguage: 'typescript',
    },
    objects: [
      {
        objectId: 'account',
        name: 'Account',
        summary: 'Customer organization record used as the main lookup object.',
        keyField: 'Id',
        fields: [
          { fieldName: 'Id', fieldType: 'string', required: true, filterable: true, writable: false, sensitive: false, summary: 'Account identifier.' },
          { fieldName: 'Name', fieldType: 'string', required: true, filterable: true, writable: false, sensitive: false, summary: 'Account display name.' },
          { fieldName: 'BillingState', fieldType: 'string', required: false, filterable: true, writable: false, sensitive: false, summary: 'Billing state or province.' },
        ],
        relationships: [{ relationshipName: 'contacts', targetObjectName: 'Contact', cardinality: 'one_to_many', summary: 'Contacts under an account.' }],
        sensitiveFieldNames: ['AnnualRevenue'],
      },
      {
        objectId: 'contact',
        name: 'Contact',
        summary: 'Person record linked to an account.',
        keyField: 'Id',
        fields: [
          { fieldName: 'Id', fieldType: 'string', required: true, filterable: true, writable: false, sensitive: false, summary: 'Contact identifier.' },
          { fieldName: 'LastName', fieldType: 'string', required: true, filterable: true, writable: false, sensitive: false, summary: 'Last name.' },
          { fieldName: 'Title', fieldType: 'string', required: false, filterable: true, writable: false, sensitive: false, summary: 'Job title.' },
        ],
        relationships: [{ relationshipName: 'account', targetObjectName: 'Account', cardinality: 'many_to_one', summary: 'Parent account.' }],
        sensitiveFieldNames: ['Email'],
      },
      {
        objectId: 'task',
        name: 'Task',
        summary: 'Follow-up task or note action tied to an account.',
        keyField: 'Id',
        fields: [
          { fieldName: 'Id', fieldType: 'string', required: true, filterable: true, writable: false, sensitive: false, summary: 'Task identifier.' },
          { fieldName: 'Subject', fieldType: 'string', required: true, filterable: false, writable: true, sensitive: false, summary: 'Task subject.' },
          { fieldName: 'ActivityDate', fieldType: 'date', required: false, filterable: false, writable: true, sensitive: false, summary: 'Due date.' },
        ],
        relationships: [{ relationshipName: 'account', targetObjectName: 'Account', cardinality: 'many_to_one', summary: 'Target account.' }],
        sensitiveFieldNames: [],
      },
    ],
    capabilities: [
      {
        capabilityId: 'salesforce.search_accounts',
        title: 'Search Accounts',
        summary: 'Find accounts by name with optional narrowing.',
        objectScope: ['Account'],
        intentType: 'search',
        operationType: 'read',
        sideEffectLevel: 'read_only',
        requiredInputs: [{ inputName: 'account_name', inputType: 'string', required: true, summary: 'Account name or partial name.' }],
        optionalInputs: [{ inputName: 'billing_state', inputType: 'string', required: false, summary: 'Optional state narrowing.' }],
        supportedFilters: ['Name', 'BillingState'],
        outputShape: 'record_list',
        backendMapping: {
          backendOperation: 'account_search',
          httpMethod: 'GET',
          pathTemplate: '/services/data/vXX.X/query',
          requestMappingSummary: 'Translate account search inputs into a bounded search request.',
          responseMappingSummary: 'Normalize into bounded account records.',
          errorMappingSummary: 'Map auth and permission failures into governed outcomes.',
        },
      },
      {
        capabilityId: 'salesforce.get_account_summary',
        title: 'Get Account Summary',
        summary: 'Retrieve a bounded account summary for a resolved record.',
        objectScope: ['Account', 'Contact', 'Task'],
        intentType: 'retrieve',
        operationType: 'read',
        sideEffectLevel: 'read_only',
        requiredInputs: [{ inputName: 'account_ref', inputType: 'object_ref', required: true, summary: 'Resolved account identifier.' }],
        optionalInputs: [],
        supportedFilters: [],
        outputShape: 'summary',
        backendMapping: {
          backendOperation: 'account_summary',
          httpMethod: 'GET',
          pathTemplate: '/services/data/vXX.X/sobjects/Account/{id}',
          requestMappingSummary: 'Fetch the bounded account summary and related counts.',
          responseMappingSummary: 'Normalize into a compact account summary.',
          errorMappingSummary: 'Map not found and permission failures into governed outcomes.',
        },
      },
      {
        capabilityId: 'salesforce.search_account_contacts',
        title: 'Search Account Contacts',
        summary: 'List key contacts for a resolved account.',
        objectScope: ['Account', 'Contact'],
        intentType: 'search',
        operationType: 'read',
        sideEffectLevel: 'read_only',
        requiredInputs: [{ inputName: 'account_ref', inputType: 'object_ref', required: true, summary: 'Resolved account identifier.' }],
        optionalInputs: [{ inputName: 'title', inputType: 'string', required: false, summary: 'Optional title narrowing.' }],
        supportedFilters: ['LastName', 'Title'],
        outputShape: 'record_list',
        backendMapping: {
          backendOperation: 'account_contact_search',
          httpMethod: 'GET',
          pathTemplate: '/services/data/vXX.X/query',
          requestMappingSummary: 'Search Contact records scoped to the resolved account.',
          responseMappingSummary: 'Normalize to bounded contact records.',
          errorMappingSummary: 'Map unresolved account and permission failures into governed outcomes.',
        },
      },
      {
        capabilityId: 'salesforce.create_followup_task',
        title: 'Create Follow-Up Task',
        summary: 'Create an approval-gated follow-up task for a resolved account or contact.',
        objectScope: ['Account', 'Contact', 'Task'],
        intentType: 'create',
        operationType: 'write',
        sideEffectLevel: 'approval_required_write',
        requiredInputs: [
          { inputName: 'target_ref', inputType: 'object_ref', required: true, summary: 'Resolved account or contact target.' },
          { inputName: 'subject', inputType: 'string', required: true, summary: 'Task subject.' },
        ],
        optionalInputs: [{ inputName: 'due_date', inputType: 'date', required: false, summary: 'Optional due date.' }],
        supportedFilters: [],
        outputShape: 'action_receipt',
        backendMapping: {
          backendOperation: 'task_create',
          httpMethod: 'POST',
          pathTemplate: '/services/data/vXX.X/sobjects/Task',
          requestMappingSummary: 'Build a task payload from resolved target and approved inputs.',
          responseMappingSummary: 'Normalize to an action receipt with created id and target id.',
          errorMappingSummary: 'Map validation and permission failures into governed outcomes.',
        },
      },
      {
        capabilityId: 'salesforce.add_account_note',
        title: 'Add Account Note',
        summary: 'Add an approval-gated note-like entry to a resolved account.',
        objectScope: ['Account', 'Task'],
        intentType: 'create',
        operationType: 'write',
        sideEffectLevel: 'approval_required_write',
        requiredInputs: [
          { inputName: 'account_ref', inputType: 'object_ref', required: true, summary: 'Resolved account identifier.' },
          { inputName: 'note_body', inputType: 'text', required: true, summary: 'Note content.' },
        ],
        optionalInputs: [],
        supportedFilters: [],
        outputShape: 'action_receipt',
        backendMapping: {
          backendOperation: 'account_note_create',
          httpMethod: 'POST',
          pathTemplate: '/services/data/vXX.X/sobjects/Task',
          requestMappingSummary: 'Build a bounded note-like payload linked to the account.',
          responseMappingSummary: 'Normalize to an action receipt with created id and account id.',
          errorMappingSummary: 'Map content policy and permission failures into governed outcomes.',
        },
      },
    ],
    governance: {
      permissionRules: [
        {
          ruleId: 'accounts_read_basic',
          scopeType: 'object',
          scopeName: 'Account',
          actorConstraint: 'delegated_sales_or_success_user',
          purposeConstraint: 'customer_support_or_followup',
          allowed: true,
          summary: 'Allow bounded Account reads for sales and success users.',
        },
      ],
      clarificationRules: [
        {
          ruleId: 'ambiguous_account_name',
          triggerType: 'ambiguous_record',
          capabilityId: 'salesforce.search_accounts',
          summary: 'Clarify when multiple account matches are plausible.',
          promptHint: 'I found several likely accounts. Which one do you mean?',
          enabled: true,
        },
        {
          ruleId: 'ambiguous_task_target',
          triggerType: 'ambiguous_record',
          capabilityId: 'salesforce.create_followup_task',
          summary: 'Clarify before task creation when the target is not uniquely resolved.',
          promptHint: 'Which account or contact should I create the task for?',
          enabled: true,
        },
      ],
      restrictionRules: [
        {
          ruleId: 'default_account_result_limit',
          restrictionType: 'result_limit',
          capabilityId: 'salesforce.search_accounts',
          summary: 'Restrict account search results to a small bounded list.',
          value: '10',
          enabled: true,
        },
      ],
      denialRules: [
        {
          ruleId: 'deny_forbidden_sensitive_fields',
          denialType: 'forbidden_field',
          capabilityId: null,
          summary: 'Sensitive fields should be denied in the first slice.',
          enabled: true,
        },
        {
          ruleId: 'deny_unsupported_mutation',
          denialType: 'unsupported_object',
          capabilityId: null,
          summary: 'Unsupported mutations should be denied rather than improvised.',
          enabled: true,
        },
      ],
      approvalRules: [
        {
          ruleId: 'approve_followup_task',
          capabilityId: 'salesforce.create_followup_task',
          required: true,
          approverType: 'user',
          summary: 'User approval is required before task creation.',
        },
        {
          ruleId: 'approve_account_note',
          capabilityId: 'salesforce.add_account_note',
          required: true,
          approverType: 'user',
          summary: 'User approval is required before account note creation.',
        },
      ],
      safeDefaults: {
        defaultResultLimit: 10,
        requireApprovalForWrites: true,
        requireClarificationOnAmbiguousRecord: true,
        dryRunBeforeWrite: true,
      },
    },
    scenarios: [
      {
        scenarioId: 'sf01',
        title: 'Find an account',
        request: 'Find the Acme account in California.',
        capabilityHint: 'salesforce.search_accounts',
        expectedOutcome: 'available',
        expectedBackendOperation: 'account_search',
        notes: 'Straightforward bounded account search.',
      },
      {
        scenarioId: 'sf02',
        title: 'Ambiguous account search',
        request: 'Find Acme.',
        capabilityHint: 'salesforce.search_accounts',
        expectedOutcome: 'clarification_required',
        expectedBackendOperation: 'account_search',
        notes: 'Requires disambiguation before mutation or summary retrieval.',
      },
      {
        scenarioId: 'sf03',
        title: 'Create follow-up task',
        request: 'Create a follow-up task for Acme next week to review procurement.',
        capabilityHint: 'salesforce.create_followup_task',
        expectedOutcome: 'approval_required',
        expectedBackendOperation: 'task_create',
        notes: 'Requires resolution, possible clarification, and approval.',
      },
      {
        scenarioId: 'sf04',
        title: 'Unsupported mutation',
        request: 'Update the opportunity stage for Acme to Closed Won.',
        capabilityHint: null,
        expectedOutcome: 'denied',
        expectedBackendOperation: null,
        notes: 'Opportunity mutation is not in the first bounded slice.',
      },
    ],
    metadata: {
      createdAt: timestamp,
      updatedAt: timestamp,
      sourcePacketId: null,
      derivationSummary: 'Seeded from the Salesforce CRM Basic application integration profile.',
    },
  }
}

function buildZendeskProfile(
  title: string,
  summary: string,
  backendType: ApplicationIntegrationBackendType,
  timestamp: string,
): ApplicationIntegrationProjectState {
  return {
    kind: 'application_integration',
    version: 1,
    title,
    summary: summary || 'Governed interaction model for bounded Zendesk ticket, requester, and internal-note workflows.',
    backend: {
      backendType,
      systemName: 'Zendesk Support',
      environment: 'production',
      baseUrl: 'https://example.zendesk.com',
      authType: 'oauth2',
      authNotes: 'Use Zendesk OAuth or API token auth with approval gating for state-changing operations.',
      adapterTarget: defaultAdapterTarget(backendType, 'zendesk_support_basic'),
      seedProfile: 'zendesk_support_basic',
      implementationLanguage: 'typescript',
    },
    objects: [
      {
        objectId: 'ticket',
        name: 'Ticket',
        summary: 'Support ticket used as the main lookup and action object.',
        keyField: 'id',
        fields: [
          { fieldName: 'id', fieldType: 'string', required: true, filterable: true, writable: false, sensitive: false, summary: 'Ticket identifier.' },
          { fieldName: 'subject', fieldType: 'string', required: true, filterable: true, writable: false, sensitive: false, summary: 'Ticket subject.' },
          { fieldName: 'status', fieldType: 'string', required: true, filterable: true, writable: true, sensitive: false, summary: 'Ticket workflow status.' },
        ],
        relationships: [
          { relationshipName: 'requester', targetObjectName: 'User', cardinality: 'many_to_one', summary: 'Requester tied to the ticket.' },
          { relationshipName: 'organization', targetObjectName: 'Organization', cardinality: 'many_to_one', summary: 'Organization tied to the ticket.' },
        ],
        sensitiveFieldNames: ['description'],
      },
      {
        objectId: 'user',
        name: 'User',
        summary: 'Requester or assignee record tied to tickets.',
        keyField: 'id',
        fields: [
          { fieldName: 'id', fieldType: 'string', required: true, filterable: true, writable: false, sensitive: false, summary: 'User identifier.' },
          { fieldName: 'name', fieldType: 'string', required: true, filterable: true, writable: false, sensitive: false, summary: 'Display name.' },
          { fieldName: 'email', fieldType: 'string', required: false, filterable: true, writable: false, sensitive: true, summary: 'Requester email.' },
        ],
        relationships: [{ relationshipName: 'organization', targetObjectName: 'Organization', cardinality: 'many_to_one', summary: 'Parent organization.' }],
        sensitiveFieldNames: ['email'],
      },
      {
        objectId: 'organization',
        name: 'Organization',
        summary: 'Customer organization record used to scope requester and ticket context.',
        keyField: 'id',
        fields: [
          { fieldName: 'id', fieldType: 'string', required: true, filterable: true, writable: false, sensitive: false, summary: 'Organization identifier.' },
          { fieldName: 'name', fieldType: 'string', required: true, filterable: true, writable: false, sensitive: false, summary: 'Organization name.' },
        ],
        relationships: [{ relationshipName: 'tickets', targetObjectName: 'Ticket', cardinality: 'one_to_many', summary: 'Tickets under the organization.' }],
        sensitiveFieldNames: [],
      },
    ],
    capabilities: [
      {
        capabilityId: 'zendesk.search_tickets',
        title: 'Search Tickets',
        summary: 'Find tickets by subject, status, or bounded requester context.',
        objectScope: ['Ticket'],
        intentType: 'search',
        operationType: 'read',
        sideEffectLevel: 'read_only',
        requiredInputs: [{ inputName: 'query_text', inputType: 'string', required: true, summary: 'Ticket subject, id, or support topic.' }],
        optionalInputs: [{ inputName: 'status', inputType: 'string', required: false, summary: 'Optional status narrowing.' }],
        supportedFilters: ['subject', 'status'],
        outputShape: 'record_list',
        backendMapping: {
          backendOperation: 'ticket_search',
          httpMethod: 'GET',
          pathTemplate: '/api/v2/search.json',
          requestMappingSummary: 'Translate bounded ticket search inputs into a Zendesk search request.',
          responseMappingSummary: 'Normalize search results into bounded ticket records.',
          errorMappingSummary: 'Map auth, scope, and unsupported query failures into governed outcomes.',
        },
      },
      {
        capabilityId: 'zendesk.get_ticket_summary',
        title: 'Get Ticket Summary',
        summary: 'Retrieve a compact summary for a resolved ticket.',
        objectScope: ['Ticket', 'User', 'Organization'],
        intentType: 'retrieve',
        operationType: 'read',
        sideEffectLevel: 'read_only',
        requiredInputs: [{ inputName: 'ticket_ref', inputType: 'object_ref', required: true, summary: 'Resolved ticket identifier.' }],
        optionalInputs: [],
        supportedFilters: [],
        outputShape: 'summary',
        backendMapping: {
          backendOperation: 'ticket_summary',
          httpMethod: 'GET',
          pathTemplate: '/api/v2/tickets/{id}.json',
          requestMappingSummary: 'Fetch a bounded ticket summary with requester and organization context.',
          responseMappingSummary: 'Normalize into a compact support summary.',
          errorMappingSummary: 'Map not found and scope failures into governed outcomes.',
        },
      },
      {
        capabilityId: 'zendesk.search_ticket_comments',
        title: 'Search Ticket Comments',
        summary: 'List bounded comments for a resolved ticket.',
        objectScope: ['Ticket'],
        intentType: 'search',
        operationType: 'read',
        sideEffectLevel: 'read_only',
        requiredInputs: [{ inputName: 'ticket_ref', inputType: 'object_ref', required: true, summary: 'Resolved ticket identifier.' }],
        optionalInputs: [],
        supportedFilters: [],
        outputShape: 'record_list',
        backendMapping: {
          backendOperation: 'ticket_comment_list',
          httpMethod: 'GET',
          pathTemplate: '/api/v2/tickets/{id}/comments.json',
          requestMappingSummary: 'Fetch bounded comments for the resolved ticket.',
          responseMappingSummary: 'Normalize comments into bounded timeline entries.',
          errorMappingSummary: 'Map not found and scope failures into governed outcomes.',
        },
      },
      {
        capabilityId: 'zendesk.add_internal_note',
        title: 'Add Internal Note',
        summary: 'Add an approval-gated internal note to a resolved ticket.',
        objectScope: ['Ticket'],
        intentType: 'create',
        operationType: 'write',
        sideEffectLevel: 'approval_required_write',
        requiredInputs: [
          { inputName: 'ticket_ref', inputType: 'object_ref', required: true, summary: 'Resolved ticket identifier.' },
          { inputName: 'note_body', inputType: 'text', required: true, summary: 'Internal note content.' },
        ],
        optionalInputs: [],
        supportedFilters: [],
        outputShape: 'action_receipt',
        backendMapping: {
          backendOperation: 'ticket_internal_note_create',
          httpMethod: 'PUT',
          pathTemplate: '/api/v2/tickets/{id}.json',
          requestMappingSummary: 'Build a bounded internal-note update request for the ticket.',
          responseMappingSummary: 'Normalize into an action receipt with ticket id and update id.',
          errorMappingSummary: 'Map validation and permission failures into governed outcomes.',
        },
      },
      {
        capabilityId: 'zendesk.update_ticket_status',
        title: 'Update Ticket Status',
        summary: 'Apply an approval-gated status update to a resolved ticket.',
        objectScope: ['Ticket'],
        intentType: 'update',
        operationType: 'write',
        sideEffectLevel: 'approval_required_write',
        requiredInputs: [
          { inputName: 'ticket_ref', inputType: 'object_ref', required: true, summary: 'Resolved ticket identifier.' },
          { inputName: 'status', inputType: 'string', required: true, summary: 'Approved target ticket status.' },
        ],
        optionalInputs: [],
        supportedFilters: [],
        outputShape: 'action_receipt',
        backendMapping: {
          backendOperation: 'ticket_status_update',
          httpMethod: 'PUT',
          pathTemplate: '/api/v2/tickets/{id}.json',
          requestMappingSummary: 'Build a bounded status update request for the resolved ticket.',
          responseMappingSummary: 'Normalize into an action receipt with ticket id and updated status.',
          errorMappingSummary: 'Map invalid status and permission failures into governed outcomes.',
        },
      },
    ],
    governance: {
      permissionRules: [
        {
          ruleId: 'ticket_read_basic',
          scopeType: 'object',
          scopeName: 'Ticket',
          actorConstraint: 'delegated_support_user',
          purposeConstraint: 'support_resolution',
          allowed: true,
          summary: 'Allow bounded ticket reads for delegated support users.',
        },
      ],
      clarificationRules: [
        {
          ruleId: 'ambiguous_ticket_lookup',
          triggerType: 'ambiguous_record',
          capabilityId: 'zendesk.search_tickets',
          summary: 'Clarify when the request could match multiple tickets.',
          promptHint: 'I found several likely tickets. Which one should I use?',
          enabled: true,
        },
        {
          ruleId: 'missing_status_target',
          triggerType: 'missing_required_input',
          capabilityId: 'zendesk.update_ticket_status',
          summary: 'Clarify if the target status is missing or ambiguous.',
          promptHint: 'Which ticket status should I set?',
          enabled: true,
        },
      ],
      restrictionRules: [
        {
          ruleId: 'default_ticket_result_limit',
          restrictionType: 'result_limit',
          capabilityId: 'zendesk.search_tickets',
          summary: 'Restrict ticket search results to a small bounded list.',
          value: '10',
          enabled: true,
        },
      ],
      denialRules: [
        {
          ruleId: 'deny_export_sensitive_comments',
          denialType: 'forbidden_field',
          capabilityId: 'zendesk.search_ticket_comments',
          summary: 'Sensitive comment exports should be denied in the first slice.',
          enabled: true,
        },
        {
          ruleId: 'deny_unsupported_ticket_delete',
          denialType: 'unsupported_object',
          capabilityId: null,
          summary: 'Unsupported ticket deletion should be denied rather than improvised.',
          enabled: true,
        },
      ],
      approvalRules: [
        {
          ruleId: 'approve_internal_note',
          capabilityId: 'zendesk.add_internal_note',
          required: true,
          approverType: 'user',
          summary: 'User approval is required before posting an internal note.',
        },
        {
          ruleId: 'approve_ticket_status_update',
          capabilityId: 'zendesk.update_ticket_status',
          required: true,
          approverType: 'user',
          summary: 'User approval is required before changing ticket status.',
        },
      ],
      safeDefaults: {
        defaultResultLimit: 10,
        requireApprovalForWrites: true,
        requireClarificationOnAmbiguousRecord: true,
        dryRunBeforeWrite: true,
      },
    },
    scenarios: [
      {
        scenarioId: 'zd01',
        title: 'Find a support ticket',
        request: 'Find the ticket about the broken SSO login flow.',
        capabilityHint: 'zendesk.search_tickets',
        expectedOutcome: 'available',
        expectedBackendOperation: 'ticket_search',
        notes: 'Straightforward bounded ticket search.',
      },
      {
        scenarioId: 'zd02',
        title: 'Ambiguous ticket lookup',
        request: 'Open the login issue ticket.',
        capabilityHint: 'zendesk.search_tickets',
        expectedOutcome: 'clarification_required',
        expectedBackendOperation: 'ticket_search',
        notes: 'Requires disambiguation before summary retrieval or mutation.',
      },
      {
        scenarioId: 'zd03',
        title: 'Add an internal note',
        request: 'Add an internal note telling support to coordinate with SRE.',
        capabilityHint: 'zendesk.add_internal_note',
        expectedOutcome: 'approval_required',
        expectedBackendOperation: 'ticket_internal_note_create',
        notes: 'Write action remains bounded and approval-gated.',
      },
      {
        scenarioId: 'zd04',
        title: 'Unsupported destructive action',
        request: 'Delete the ticket entirely.',
        capabilityHint: null,
        expectedOutcome: 'denied',
        expectedBackendOperation: null,
        notes: 'Destructive support actions are out of scope in the first slice.',
      },
    ],
    metadata: {
      createdAt: timestamp,
      updatedAt: timestamp,
      sourcePacketId: null,
      derivationSummary: 'Seeded from the Zendesk Support Basic application integration profile.',
    },
  }
}

function buildHubSpotProfile(
  title: string,
  summary: string,
  backendType: ApplicationIntegrationBackendType,
  timestamp: string,
): ApplicationIntegrationProjectState {
  return {
    kind: 'application_integration',
    version: 1,
    title,
    summary: summary || 'Governed interaction model for bounded HubSpot company, contact, and follow-up workflows.',
    backend: {
      backendType,
      systemName: 'HubSpot CRM',
      environment: 'production',
      baseUrl: 'https://api.hubapi.com',
      authType: 'oauth2',
      authNotes: 'Use HubSpot OAuth or private app tokens with approval gating for write capabilities.',
      adapterTarget: defaultAdapterTarget(backendType, 'hubspot_crm_basic'),
      seedProfile: 'hubspot_crm_basic',
      implementationLanguage: 'typescript',
    },
    objects: [
      {
        objectId: 'company',
        name: 'Company',
        summary: 'Company record used as the main CRM lookup object.',
        keyField: 'id',
        fields: [
          { fieldName: 'id', fieldType: 'string', required: true, filterable: true, writable: false, sensitive: false, summary: 'Company identifier.' },
          { fieldName: 'name', fieldType: 'string', required: true, filterable: true, writable: false, sensitive: false, summary: 'Company name.' },
          { fieldName: 'industry', fieldType: 'string', required: false, filterable: true, writable: false, sensitive: false, summary: 'Industry classification.' },
        ],
        relationships: [
          { relationshipName: 'contacts', targetObjectName: 'Contact', cardinality: 'one_to_many', summary: 'Contacts associated with the company.' },
          { relationshipName: 'deals', targetObjectName: 'Deal', cardinality: 'one_to_many', summary: 'Deals associated with the company.' },
        ],
        sensitiveFieldNames: ['annualrevenue'],
      },
      {
        objectId: 'contact',
        name: 'Contact',
        summary: 'Contact record linked to a company.',
        keyField: 'id',
        fields: [
          { fieldName: 'id', fieldType: 'string', required: true, filterable: true, writable: false, sensitive: false, summary: 'Contact identifier.' },
          { fieldName: 'firstname', fieldType: 'string', required: false, filterable: true, writable: false, sensitive: false, summary: 'First name.' },
          { fieldName: 'lastname', fieldType: 'string', required: false, filterable: true, writable: false, sensitive: false, summary: 'Last name.' },
        ],
        relationships: [{ relationshipName: 'company', targetObjectName: 'Company', cardinality: 'many_to_one', summary: 'Parent company.' }],
        sensitiveFieldNames: ['email'],
      },
      {
        objectId: 'deal',
        name: 'Deal',
        summary: 'Deal record used for bounded pipeline context.',
        keyField: 'id',
        fields: [
          { fieldName: 'id', fieldType: 'string', required: true, filterable: true, writable: false, sensitive: false, summary: 'Deal identifier.' },
          { fieldName: 'dealname', fieldType: 'string', required: true, filterable: true, writable: false, sensitive: false, summary: 'Deal name.' },
          { fieldName: 'dealstage', fieldType: 'string', required: false, filterable: true, writable: false, sensitive: false, summary: 'Deal stage.' },
        ],
        relationships: [{ relationshipName: 'company', targetObjectName: 'Company', cardinality: 'many_to_one', summary: 'Related company.' }],
        sensitiveFieldNames: [],
      },
      {
        objectId: 'task',
        name: 'Task',
        summary: 'Follow-up task or note action tied to a company or contact.',
        keyField: 'id',
        fields: [
          { fieldName: 'id', fieldType: 'string', required: true, filterable: true, writable: false, sensitive: false, summary: 'Task identifier.' },
          { fieldName: 'hs_task_subject', fieldType: 'string', required: true, filterable: false, writable: true, sensitive: false, summary: 'Task subject.' },
        ],
        relationships: [{ relationshipName: 'company', targetObjectName: 'Company', cardinality: 'many_to_one', summary: 'Related company.' }],
        sensitiveFieldNames: [],
      },
    ],
    capabilities: [
      {
        capabilityId: 'hubspot.search_companies',
        title: 'Search Companies',
        summary: 'Find companies by name with optional industry narrowing.',
        objectScope: ['Company'],
        intentType: 'search',
        operationType: 'read',
        sideEffectLevel: 'read_only',
        requiredInputs: [{ inputName: 'company_name', inputType: 'string', required: true, summary: 'Company name or partial match.' }],
        optionalInputs: [{ inputName: 'industry', inputType: 'string', required: false, summary: 'Optional industry narrowing.' }],
        supportedFilters: ['name', 'industry'],
        outputShape: 'record_list',
        backendMapping: {
          backendOperation: 'company_search',
          httpMethod: 'POST',
          pathTemplate: '/crm/v3/objects/companies/search',
          requestMappingSummary: 'Translate company search inputs into a bounded HubSpot search request.',
          responseMappingSummary: 'Normalize search results into bounded company records.',
          errorMappingSummary: 'Map auth and scope failures into governed outcomes.',
        },
      },
      {
        capabilityId: 'hubspot.get_company_summary',
        title: 'Get Company Summary',
        summary: 'Retrieve a bounded summary for a resolved company.',
        objectScope: ['Company', 'Contact', 'Deal', 'Task'],
        intentType: 'retrieve',
        operationType: 'read',
        sideEffectLevel: 'read_only',
        requiredInputs: [{ inputName: 'company_ref', inputType: 'object_ref', required: true, summary: 'Resolved company identifier.' }],
        optionalInputs: [],
        supportedFilters: [],
        outputShape: 'summary',
        backendMapping: {
          backendOperation: 'company_summary',
          httpMethod: 'GET',
          pathTemplate: '/crm/v3/objects/companies/{id}',
          requestMappingSummary: 'Fetch the bounded company summary and related counts.',
          responseMappingSummary: 'Normalize into a compact company summary.',
          errorMappingSummary: 'Map not found and permission failures into governed outcomes.',
        },
      },
      {
        capabilityId: 'hubspot.search_company_contacts',
        title: 'Search Company Contacts',
        summary: 'List key contacts for a resolved company.',
        objectScope: ['Company', 'Contact'],
        intentType: 'search',
        operationType: 'read',
        sideEffectLevel: 'read_only',
        requiredInputs: [{ inputName: 'company_ref', inputType: 'object_ref', required: true, summary: 'Resolved company identifier.' }],
        optionalInputs: [{ inputName: 'job_title', inputType: 'string', required: false, summary: 'Optional title narrowing.' }],
        supportedFilters: ['lastname', 'jobtitle'],
        outputShape: 'record_list',
        backendMapping: {
          backendOperation: 'company_contact_search',
          httpMethod: 'POST',
          pathTemplate: '/crm/v3/objects/contacts/search',
          requestMappingSummary: 'Search contact records scoped to the resolved company.',
          responseMappingSummary: 'Normalize to bounded contact records.',
          errorMappingSummary: 'Map unresolved company and permission failures into governed outcomes.',
        },
      },
      {
        capabilityId: 'hubspot.create_followup_task',
        title: 'Create Follow-Up Task',
        summary: 'Create an approval-gated follow-up task for a resolved company or contact.',
        objectScope: ['Company', 'Contact', 'Task'],
        intentType: 'create',
        operationType: 'write',
        sideEffectLevel: 'approval_required_write',
        requiredInputs: [
          { inputName: 'target_ref', inputType: 'object_ref', required: true, summary: 'Resolved company or contact target.' },
          { inputName: 'subject', inputType: 'string', required: true, summary: 'Task subject.' },
        ],
        optionalInputs: [{ inputName: 'due_date', inputType: 'date', required: false, summary: 'Optional due date.' }],
        supportedFilters: [],
        outputShape: 'action_receipt',
        backendMapping: {
          backendOperation: 'task_create',
          httpMethod: 'POST',
          pathTemplate: '/crm/v3/objects/tasks',
          requestMappingSummary: 'Build a task payload from resolved target and approved inputs.',
          responseMappingSummary: 'Normalize to an action receipt with created id and target id.',
          errorMappingSummary: 'Map validation and permission failures into governed outcomes.',
        },
      },
      {
        capabilityId: 'hubspot.add_company_note',
        title: 'Add Company Note',
        summary: 'Add an approval-gated note entry to a resolved company.',
        objectScope: ['Company', 'Task'],
        intentType: 'create',
        operationType: 'write',
        sideEffectLevel: 'approval_required_write',
        requiredInputs: [
          { inputName: 'company_ref', inputType: 'object_ref', required: true, summary: 'Resolved company identifier.' },
          { inputName: 'note_body', inputType: 'text', required: true, summary: 'Note content.' },
        ],
        optionalInputs: [],
        supportedFilters: [],
        outputShape: 'action_receipt',
        backendMapping: {
          backendOperation: 'company_note_create',
          httpMethod: 'POST',
          pathTemplate: '/crm/v3/objects/notes',
          requestMappingSummary: 'Build a bounded note payload linked to the company.',
          responseMappingSummary: 'Normalize to an action receipt with created id and company id.',
          errorMappingSummary: 'Map content policy and permission failures into governed outcomes.',
        },
      },
    ],
    governance: {
      permissionRules: [
        {
          ruleId: 'companies_read_basic',
          scopeType: 'object',
          scopeName: 'Company',
          actorConstraint: 'delegated_sales_or_success_user',
          purposeConstraint: 'customer_followup_or_pipeline_review',
          allowed: true,
          summary: 'Allow bounded Company reads for delegated sales and success users.',
        },
      ],
      clarificationRules: [
        {
          ruleId: 'ambiguous_company_name',
          triggerType: 'ambiguous_record',
          capabilityId: 'hubspot.search_companies',
          summary: 'Clarify when multiple company matches are plausible.',
          promptHint: 'I found several likely companies. Which one do you mean?',
          enabled: true,
        },
        {
          ruleId: 'ambiguous_task_target',
          triggerType: 'ambiguous_record',
          capabilityId: 'hubspot.create_followup_task',
          summary: 'Clarify before task creation when the target is not uniquely resolved.',
          promptHint: 'Which company or contact should I create the task for?',
          enabled: true,
        },
      ],
      restrictionRules: [
        {
          ruleId: 'default_company_result_limit',
          restrictionType: 'result_limit',
          capabilityId: 'hubspot.search_companies',
          summary: 'Restrict company search results to a small bounded list.',
          value: '10',
          enabled: true,
        },
      ],
      denialRules: [
        {
          ruleId: 'deny_forbidden_sensitive_fields',
          denialType: 'forbidden_field',
          capabilityId: null,
          summary: 'Sensitive HubSpot fields should be denied in the first slice.',
          enabled: true,
        },
        {
          ruleId: 'deny_unsupported_mutation',
          denialType: 'unsupported_object',
          capabilityId: null,
          summary: 'Unsupported CRM mutations should be denied rather than improvised.',
          enabled: true,
        },
      ],
      approvalRules: [
        {
          ruleId: 'approve_followup_task',
          capabilityId: 'hubspot.create_followup_task',
          required: true,
          approverType: 'user',
          summary: 'User approval is required before task creation.',
        },
        {
          ruleId: 'approve_company_note',
          capabilityId: 'hubspot.add_company_note',
          required: true,
          approverType: 'user',
          summary: 'User approval is required before company note creation.',
        },
      ],
      safeDefaults: {
        defaultResultLimit: 10,
        requireApprovalForWrites: true,
        requireClarificationOnAmbiguousRecord: true,
        dryRunBeforeWrite: true,
      },
    },
    scenarios: [
      {
        scenarioId: 'hs01',
        title: 'Find a company',
        request: 'Find the Acme company in manufacturing.',
        capabilityHint: 'hubspot.search_companies',
        expectedOutcome: 'available',
        expectedBackendOperation: 'company_search',
        notes: 'Straightforward bounded company search.',
      },
      {
        scenarioId: 'hs02',
        title: 'Ambiguous company search',
        request: 'Find Acme.',
        capabilityHint: 'hubspot.search_companies',
        expectedOutcome: 'clarification_required',
        expectedBackendOperation: 'company_search',
        notes: 'Requires disambiguation before summary retrieval or mutation.',
      },
      {
        scenarioId: 'hs03',
        title: 'Create follow-up task',
        request: 'Create a follow-up task for Acme to review the renewal plan.',
        capabilityHint: 'hubspot.create_followup_task',
        expectedOutcome: 'approval_required',
        expectedBackendOperation: 'task_create',
        notes: 'Requires resolution, possible clarification, and approval.',
      },
      {
        scenarioId: 'hs04',
        title: 'Unsupported mutation',
        request: 'Mark the deal as closed won right now.',
        capabilityHint: null,
        expectedOutcome: 'denied',
        expectedBackendOperation: null,
        notes: 'Deal mutation is not in the first bounded slice.',
      },
    ],
    metadata: {
      createdAt: timestamp,
      updatedAt: timestamp,
      sourcePacketId: null,
      derivationSummary: 'Seeded from the HubSpot CRM Basic application integration profile.',
    },
  }
}


function buildGitHubIssuesProfile(
  title: string,
  summary: string,
  backendType: ApplicationIntegrationBackendType,
  timestamp: string,
): ApplicationIntegrationProjectState {
  return {
    kind: 'application_integration',
    version: 1,
    title,
    summary: summary || 'Governed interaction model for bounded GitHub repository issue lookup, issue summary, and approval-gated issue comment workflows.',
    backend: {
      backendType,
      systemName: 'GitHub GraphQL',
      environment: 'production',
      baseUrl: 'https://api.github.com/graphql',
      authType: 'bearer_token',
      authNotes: 'Use a delegated GitHub token or GitHub App installation token with repository-scoped access.',
      adapterTarget: defaultAdapterTarget(backendType, 'github_issues_basic'),
      seedProfile: 'github_issues_basic',
      implementationLanguage: 'typescript',
    },
    objects: [
      {
        objectId: 'repository',
        name: 'Repository',
        summary: 'GitHub repository that scopes issue and comment workflows.',
        keyField: 'id',
        fields: [
          { fieldName: 'id', fieldType: 'string', required: true, filterable: true, writable: false, sensitive: false, summary: 'Repository node id.' },
          { fieldName: 'name', fieldType: 'string', required: true, filterable: true, writable: false, sensitive: false, summary: 'Repository name.' },
          { fieldName: 'owner', fieldType: 'string', required: true, filterable: true, writable: false, sensitive: false, summary: 'Repository owner login.' },
        ],
        relationships: [{ relationshipName: 'issues', targetObjectName: 'Issue', cardinality: 'one_to_many', summary: 'Issues under the repository.' }],
        sensitiveFieldNames: [],
      },
      {
        objectId: 'issue',
        name: 'Issue',
        summary: 'Issue record returned by GitHub GraphQL.',
        keyField: 'id',
        fields: [
          { fieldName: 'id', fieldType: 'string', required: true, filterable: true, writable: false, sensitive: false, summary: 'Issue node id.' },
          { fieldName: 'number', fieldType: 'number', required: true, filterable: true, writable: false, sensitive: false, summary: 'Issue number within the repository.' },
          { fieldName: 'title', fieldType: 'string', required: true, filterable: true, writable: false, sensitive: false, summary: 'Issue title.' },
          { fieldName: 'state', fieldType: 'string', required: true, filterable: true, writable: false, sensitive: false, summary: 'Issue state.' },
        ],
        relationships: [{ relationshipName: 'repository', targetObjectName: 'Repository', cardinality: 'many_to_one', summary: 'Parent repository.' }],
        sensitiveFieldNames: ['body'],
      },
      {
        objectId: 'issue_comment',
        name: 'Issue Comment',
        summary: 'Comment prepared for a target issue.',
        keyField: 'id',
        fields: [
          { fieldName: 'id', fieldType: 'string', required: true, filterable: false, writable: false, sensitive: false, summary: 'Comment node id.' },
          { fieldName: 'body', fieldType: 'text', required: true, filterable: false, writable: true, sensitive: false, summary: 'Comment body.' },
        ],
        relationships: [{ relationshipName: 'issue', targetObjectName: 'Issue', cardinality: 'many_to_one', summary: 'Target issue.' }],
        sensitiveFieldNames: [],
      },
    ],
    capabilities: [
      {
        capabilityId: 'github.list_repository_issues',
        title: 'List Repository Issues',
        summary: 'List bounded repository issues through GitHub GraphQL.',
        objectScope: ['Repository', 'Issue'],
        intentType: 'search',
        operationType: 'read',
        sideEffectLevel: 'read_only',
        requiredInputs: [
          { inputName: 'owner', inputType: 'string', required: true, summary: 'Repository owner login.' },
          { inputName: 'repository', inputType: 'string', required: true, summary: 'Repository name.' },
        ],
        optionalInputs: [
          { inputName: 'state', inputType: 'string', required: false, summary: 'Optional issue state filter.' },
          { inputName: 'label_name', inputType: 'string', required: false, summary: 'Optional label filter.' },
        ],
        supportedFilters: ['state', 'label_name'],
        outputShape: 'record_list',
        backendMapping: {
          backendOperation: 'repository_issues_list',
          httpMethod: 'POST',
          pathTemplate: '/graphql',
          requestMappingSummary: 'Build a bounded GraphQL issue listing query from the resolved repository context.',
          responseMappingSummary: 'Normalize repository issue nodes into bounded issue records.',
          errorMappingSummary: 'Map repository, auth, and policy failures into governed outcomes.',
        },
      },
      {
        capabilityId: 'github.get_issue_summary',
        title: 'Get Issue Summary',
        summary: 'Retrieve a compact issue summary for a resolved repository and issue number.',
        objectScope: ['Repository', 'Issue'],
        intentType: 'retrieve',
        operationType: 'read',
        sideEffectLevel: 'read_only',
        requiredInputs: [
          { inputName: 'owner', inputType: 'string', required: true, summary: 'Repository owner login.' },
          { inputName: 'repository', inputType: 'string', required: true, summary: 'Repository name.' },
          { inputName: 'issue_number', inputType: 'number', required: true, summary: 'Issue number.' },
        ],
        optionalInputs: [],
        supportedFilters: [],
        outputShape: 'summary',
        backendMapping: {
          backendOperation: 'issue_summary_get',
          httpMethod: 'POST',
          pathTemplate: '/graphql',
          requestMappingSummary: 'Build a bounded GraphQL issue summary query from the resolved repository and issue number.',
          responseMappingSummary: 'Normalize into a compact issue summary.',
          errorMappingSummary: 'Map repository, issue, and permission failures into governed outcomes.',
        },
      },
      {
        capabilityId: 'github.prepare_issue_comment',
        title: 'Prepare Issue Comment',
        summary: 'Prepare an approval-gated issue comment against a resolved repository issue.',
        objectScope: ['Repository', 'Issue', 'Issue Comment'],
        intentType: 'create',
        operationType: 'write',
        sideEffectLevel: 'approval_required_write',
        requiredInputs: [
          { inputName: 'owner', inputType: 'string', required: true, summary: 'Repository owner login.' },
          { inputName: 'repository', inputType: 'string', required: true, summary: 'Repository name.' },
          { inputName: 'issue_number', inputType: 'number', required: true, summary: 'Issue number.' },
          { inputName: 'comment_body', inputType: 'text', required: true, summary: 'Comment body.' },
        ],
        optionalInputs: [],
        supportedFilters: [],
        outputShape: 'action_receipt',
        backendMapping: {
          backendOperation: 'issue_comment_prepare',
          httpMethod: 'POST',
          pathTemplate: '/graphql',
          requestMappingSummary: 'Build a bounded GraphQL mutation request from approved issue comment inputs.',
          responseMappingSummary: 'Normalize into an action receipt with repository, issue, and prepared comment data.',
          errorMappingSummary: 'Map validation, auth, and policy failures into governed outcomes.',
        },
      },
    ],
    governance: {
      permissionRules: [
        {
          ruleId: 'repo_issue_read_basic',
          scopeType: 'object',
          scopeName: 'Issue',
          actorConstraint: 'delegated_repo_user',
          purposeConstraint: 'issue_lookup_or_triage',
          allowed: true,
          summary: 'Allow bounded issue reads for delegated repository users.',
        },
      ],
      clarificationRules: [
        {
          ruleId: 'missing_repository_context',
          triggerType: 'missing_required_input',
          capabilityId: 'github.list_repository_issues',
          summary: 'Clarify when repository owner or name is missing.',
          promptHint: 'Which repository should I use?',
          enabled: true,
        },
        {
          ruleId: 'missing_issue_context',
          triggerType: 'missing_required_input',
          capabilityId: 'github.prepare_issue_comment',
          summary: 'Clarify when the issue number is missing for comment preparation.',
          promptHint: 'Which issue should I comment on?',
          enabled: true,
        },
      ],
      restrictionRules: [
        {
          ruleId: 'default_issue_result_limit',
          restrictionType: 'result_limit',
          capabilityId: 'github.list_repository_issues',
          summary: 'Restrict issue listings to a small bounded set.',
          value: '20',
          enabled: true,
        },
      ],
      denialRules: [
        {
          ruleId: 'deny_cross_repo_broad_export',
          denialType: 'unsupported_object',
          capabilityId: null,
          summary: 'Cross-organization issue exports are denied in the first GraphQL slice.',
          enabled: true,
        },
        {
          ruleId: 'deny_issue_state_mutation',
          denialType: 'unsupported_object',
          capabilityId: null,
          summary: 'Issue state mutation remains out of scope in the first bounded slice.',
          enabled: true,
        },
      ],
      approvalRules: [
        {
          ruleId: 'approve_issue_comment',
          capabilityId: 'github.prepare_issue_comment',
          required: true,
          approverType: 'user',
          summary: 'User approval is required before posting an issue comment.',
        },
      ],
      safeDefaults: {
        defaultResultLimit: 20,
        requireApprovalForWrites: true,
        requireClarificationOnAmbiguousRecord: true,
        dryRunBeforeWrite: true,
      },
    },
    scenarios: [
      {
        scenarioId: 'gh01',
        title: 'List repository issues',
        request: 'Show me the open onboarding issues in acme/platform.',
        capabilityHint: 'github.list_repository_issues',
        expectedOutcome: 'available',
        expectedBackendOperation: 'repository_issues_list',
        notes: 'Straightforward bounded issue lookup for a resolved repository.',
      },
      {
        scenarioId: 'gh02',
        title: 'Missing repository context',
        request: 'Show me issue 241.',
        capabilityHint: 'github.get_issue_summary',
        expectedOutcome: 'clarification_required',
        expectedBackendOperation: 'issue_summary_get',
        notes: 'Needs repository context before issue summary lookup.',
      },
      {
        scenarioId: 'gh03',
        title: 'Prepare an issue comment',
        request: 'Comment on issue 241 that onboarding copy is ready for review.',
        capabilityHint: 'github.prepare_issue_comment',
        expectedOutcome: 'approval_required',
        expectedBackendOperation: 'issue_comment_prepare',
        notes: 'Issue comment creation remains approval-gated.',
      },
      {
        scenarioId: 'gh04',
        title: 'Broad issue export',
        request: 'Export every open issue across all repositories in the org.',
        capabilityHint: 'github.list_repository_issues',
        expectedOutcome: 'restricted',
        expectedBackendOperation: 'repository_issues_list',
        notes: 'Bound the request to a single repository or a capped list.',
      },
      {
        scenarioId: 'gh05',
        title: 'Unsupported mutation',
        request: 'Close issue 241 right now.',
        capabilityHint: null,
        expectedOutcome: 'denied',
        expectedBackendOperation: null,
        notes: 'Issue state mutation is out of scope in the first slice.',
      },
    ],
    metadata: {
      createdAt: timestamp,
      updatedAt: timestamp,
      sourcePacketId: null,
      derivationSummary: 'Seeded from the GitHub Issues Basic application integration profile.',
    },
  }
}

function buildMcpKnowledgeProfile(
  title: string,
  summary: string,
  backendType: ApplicationIntegrationBackendType,
  timestamp: string,
): ApplicationIntegrationProjectState {
  return {
    kind: 'application_integration',
    version: 1,
    title,
    summary: summary || 'Governed interaction model for bounded MCP-backed knowledge search, note retrieval, and approval-gated note creation.',
    backend: {
      backendType,
      systemName: 'MCP Knowledge Server',
      environment: 'production',
      baseUrl: 'mcp://knowledge',
      authType: 'custom',
      authNotes: 'Use host-managed MCP session or tool authorization and keep tool-specific auth in the MCP host boundary.',
      adapterTarget: defaultAdapterTarget(backendType, 'mcp_knowledge_basic'),
      seedProfile: 'mcp_knowledge_basic',
      implementationLanguage: 'typescript',
    },
    objects: [
      {
        objectId: 'note',
        name: 'Note',
        summary: 'Knowledge note exposed through MCP tools.',
        keyField: 'id',
        fields: [
          { fieldName: 'id', fieldType: 'string', required: true, filterable: true, writable: false, sensitive: false, summary: 'Note identifier.' },
          { fieldName: 'title', fieldType: 'string', required: true, filterable: true, writable: false, sensitive: false, summary: 'Note title.' },
          { fieldName: 'updated_at', fieldType: 'datetime', required: false, filterable: true, writable: false, sensitive: false, summary: 'Last update time.' },
        ],
        relationships: [{ relationshipName: 'workspace', targetObjectName: 'Workspace', cardinality: 'many_to_one', summary: 'Workspace that owns the note.' }],
        sensitiveFieldNames: ['body'],
      },
      {
        objectId: 'workspace',
        name: 'Workspace',
        summary: 'Knowledge workspace or namespace available through MCP.',
        keyField: 'id',
        fields: [
          { fieldName: 'id', fieldType: 'string', required: true, filterable: true, writable: false, sensitive: false, summary: 'Workspace identifier.' },
          { fieldName: 'name', fieldType: 'string', required: true, filterable: true, writable: false, sensitive: false, summary: 'Workspace name.' },
        ],
        relationships: [{ relationshipName: 'notes', targetObjectName: 'Note', cardinality: 'one_to_many', summary: 'Notes under the workspace.' }],
        sensitiveFieldNames: [],
      },
    ],
    capabilities: [
      {
        capabilityId: 'mcp.search_notes',
        title: 'Search Notes',
        summary: 'Search notes through an MCP tool with bounded query inputs.',
        objectScope: ['Note'],
        intentType: 'search',
        operationType: 'read',
        sideEffectLevel: 'read_only',
        requiredInputs: [{ inputName: 'query_text', inputType: 'string', required: true, summary: 'Search text for notes.' }],
        optionalInputs: [{ inputName: 'workspace_name', inputType: 'string', required: false, summary: 'Optional workspace narrowing.' }],
        supportedFilters: ['title', 'workspace'],
        outputShape: 'record_list',
        backendMapping: {
          backendOperation: 'search_notes',
          httpMethod: 'CUSTOM',
          pathTemplate: 'tool://search_notes',
          requestMappingSummary: 'Translate bounded note search inputs into an MCP tool invocation.',
          responseMappingSummary: 'Normalize MCP note search results into bounded note records.',
          errorMappingSummary: 'Map tool, auth, and scope failures into governed outcomes.',
        },
      },
      {
        capabilityId: 'mcp.get_note_summary',
        title: 'Get Note Summary',
        summary: 'Retrieve a compact note summary through an MCP tool for a resolved note.',
        objectScope: ['Note', 'Workspace'],
        intentType: 'retrieve',
        operationType: 'read',
        sideEffectLevel: 'read_only',
        requiredInputs: [{ inputName: 'note_ref', inputType: 'object_ref', required: true, summary: 'Resolved note identifier.' }],
        optionalInputs: [],
        supportedFilters: [],
        outputShape: 'summary',
        backendMapping: {
          backendOperation: 'get_note_summary',
          httpMethod: 'CUSTOM',
          pathTemplate: 'tool://get_note',
          requestMappingSummary: 'Build a bounded MCP note retrieval request for the resolved note.',
          responseMappingSummary: 'Normalize into a compact note summary.',
          errorMappingSummary: 'Map not found and permission failures into governed outcomes.',
        },
      },
      {
        capabilityId: 'mcp.create_note',
        title: 'Create Note',
        summary: 'Create an approval-gated note through an MCP tool in a bounded workspace.',
        objectScope: ['Note', 'Workspace'],
        intentType: 'create',
        operationType: 'write',
        sideEffectLevel: 'approval_required_write',
        requiredInputs: [
          { inputName: 'workspace_ref', inputType: 'object_ref', required: true, summary: 'Resolved workspace identifier.' },
          { inputName: 'title', inputType: 'string', required: true, summary: 'Note title.' },
          { inputName: 'body', inputType: 'text', required: true, summary: 'Note content.' },
        ],
        optionalInputs: [],
        supportedFilters: [],
        outputShape: 'action_receipt',
        backendMapping: {
          backendOperation: 'create_note',
          httpMethod: 'CUSTOM',
          pathTemplate: 'tool://create_note',
          requestMappingSummary: 'Build a bounded MCP note creation request from approved inputs.',
          responseMappingSummary: 'Normalize to an action receipt with created note id and workspace id.',
          errorMappingSummary: 'Map validation and permission failures into governed outcomes.',
        },
      },
    ],
    governance: {
      permissionRules: [
        {
          ruleId: 'workspace_read_basic',
          scopeType: 'object',
          scopeName: 'Note',
          actorConstraint: 'delegated_knowledge_user',
          purposeConstraint: 'knowledge_lookup_or_preparation',
          allowed: true,
          summary: 'Allow bounded MCP note reads for delegated knowledge users.',
        },
      ],
      clarificationRules: [
        {
          ruleId: 'ambiguous_note_lookup',
          triggerType: 'ambiguous_record',
          capabilityId: 'mcp.search_notes',
          summary: 'Clarify when the request could match multiple notes.',
          promptHint: 'I found several likely notes. Which one should I use?',
          enabled: true,
        },
        {
          ruleId: 'missing_workspace_target',
          triggerType: 'missing_required_input',
          capabilityId: 'mcp.create_note',
          summary: 'Clarify when the target workspace is missing for note creation.',
          promptHint: 'Which workspace should I create the note in?',
          enabled: true,
        },
      ],
      restrictionRules: [
        {
          ruleId: 'default_note_result_limit',
          restrictionType: 'result_limit',
          capabilityId: 'mcp.search_notes',
          summary: 'Restrict note search results to a small bounded list.',
          value: '10',
          enabled: true,
        },
      ],
      denialRules: [
        {
          ruleId: 'deny_sensitive_note_body_export',
          denialType: 'forbidden_field',
          capabilityId: null,
          summary: 'Sensitive full-note exports should be denied in the first slice.',
          enabled: true,
        },
        {
          ruleId: 'deny_unsupported_tool_usage',
          denialType: 'unsupported_object',
          capabilityId: null,
          summary: 'Unsupported MCP tools should be denied rather than improvised.',
          enabled: true,
        },
      ],
      approvalRules: [
        {
          ruleId: 'approve_note_creation',
          capabilityId: 'mcp.create_note',
          required: true,
          approverType: 'user',
          summary: 'User approval is required before note creation.',
        },
      ],
      safeDefaults: {
        defaultResultLimit: 10,
        requireApprovalForWrites: true,
        requireClarificationOnAmbiguousRecord: true,
        dryRunBeforeWrite: true,
      },
    },
    scenarios: [
      {
        scenarioId: 'mcp01',
        title: 'Find a note',
        request: 'Find the onboarding note for Acme.',
        capabilityHint: 'mcp.search_notes',
        expectedOutcome: 'available',
        expectedBackendOperation: 'search_notes',
        notes: 'Straightforward bounded note search through MCP.',
      },
      {
        scenarioId: 'mcp02',
        title: 'Ambiguous note lookup',
        request: 'Open the onboarding note.',
        capabilityHint: 'mcp.search_notes',
        expectedOutcome: 'clarification_required',
        expectedBackendOperation: 'search_notes',
        notes: 'Requires disambiguation before summary retrieval.',
      },
      {
        scenarioId: 'mcp03',
        title: 'Create a note',
        request: 'Create a note in the GTM workspace summarizing Acme onboarding actions.',
        capabilityHint: 'mcp.create_note',
        expectedOutcome: 'approval_required',
        expectedBackendOperation: 'create_note',
        notes: 'MCP-backed write remains bounded and approval-gated.',
      },
      {
        scenarioId: 'mcp04',
        title: 'Unsupported destructive action',
        request: 'Delete the onboarding note permanently.',
        capabilityHint: null,
        expectedOutcome: 'denied',
        expectedBackendOperation: null,
        notes: 'Destructive tool use is out of scope in the first slice.',
      },
    ],
    metadata: {
      createdAt: timestamp,
      updatedAt: timestamp,
      sourcePacketId: null,
      derivationSummary: 'Seeded from the MCP Knowledge Basic application integration profile.',
    },
  }
}

export function createDraftApplicationIntegrationProjectState(
  title: string,
  summary = '',
  backendType: ApplicationIntegrationBackendType = 'rest_api',
  seedProfile: ApplicationIntegrationSeedProfile = 'salesforce_crm_basic',
  implementationLanguage: ApplicationIntegrationImplementationLanguage = 'typescript',
): ApplicationIntegrationProjectState {
  const timestamp = nowIso()

  let project: ApplicationIntegrationProjectState

  switch (seedProfile) {
    case 'zendesk_support_basic':
      project = buildZendeskProfile(title, summary, backendType, timestamp)
      break
    case 'hubspot_crm_basic':
      project = buildHubSpotProfile(title, summary, backendType, timestamp)
      break
    case 'github_issues_basic':
      project = buildGitHubIssuesProfile(title, summary, backendType, timestamp)
      break
    case 'mcp_knowledge_basic':
      project = buildMcpKnowledgeProfile(title, summary, backendType, timestamp)
      break
    case 'salesforce_crm_basic':
    default:
      project = buildSalesforceProfile(title, summary, backendType, timestamp)
      break
  }

  project.backend.implementationLanguage = implementationLanguage
  return project
}

export function emptyApplicationIntegrationGeneratedOutput(
  kind: ApplicationIntegrationGeneratedOutput['kind'],
  title: string,
  filename: string,
  contentType: ApplicationIntegrationGeneratedOutput['contentType'],
): ApplicationIntegrationGeneratedOutput {
  return {
    kind,
    title,
    filename,
    contentType,
    content: '',
    generatedAt: new Date(0).toISOString(),
  }
}
