export interface DeveloperVocabularyEntry {
  value: string
  label: string
  description?: string
}

export interface DeveloperOption {
  value: string
  label: string
}

export const DEVELOPER_VOCABULARY: Record<string, DeveloperVocabularyEntry> = {
  atomic: { value: 'atomic', label: 'Single capability' },
  composed: { value: 'composed', label: 'Composed capability' },
  business_action: { value: 'business_action', label: 'Business action' },
  read: { value: 'read', label: 'Read operation' },
  read_only: { value: 'read_only', label: 'Read-only' },
  write: { value: 'write', label: 'Write operation' },
  draft: { value: 'draft', label: 'Draft content' },
  preview: { value: 'preview', label: 'Preview change' },
  retrieve: { value: 'retrieve', label: 'Retrieve information' },
  compute: { value: 'compute', label: 'Compute result' },
  mutate: { value: 'mutate', label: 'Change system state' },
  mutation: { value: 'mutation', label: 'Change system state' },
  forbidden_mutation: { value: 'forbidden_mutation', label: 'Forbidden system change' },
  approval_gated: { value: 'approval_gated', label: 'Requires approval' },
  approval_required: { value: 'approval_required', label: 'Approval required' },
  clarification_required: { value: 'clarification_required', label: 'Clarification required' },
  safe_stop: { value: 'safe_stop', label: 'Safe stop' },
  continue: { value: 'continue', label: 'Continue' },
  complete: { value: 'complete', label: 'Complete' },
  completed: { value: 'completed', label: 'Complete' },
  intermediate_result: { value: 'intermediate_result', label: 'Intermediate result' },
  handoff: { value: 'handoff', label: 'Handoff' },
  capability_execution: { value: 'capability_execution', label: 'Executable capability step' },
  handoff_only: { value: 'handoff_only', label: 'Handoff only' },
  allow: { value: 'allow', label: 'Allowed' },
  allowed: { value: 'allowed', label: 'Allowed' },
  bounded: { value: 'bounded', label: 'Bounded' },
  restrict: { value: 'restrict', label: 'Restricted' },
  restricted: { value: 'restricted', label: 'Restricted' },
  denied: { value: 'denied', label: 'Denied' },
  available: { value: 'available', label: 'Available' },
  direct_result: { value: 'direct_result', label: 'Direct result' },
  bounded_result: { value: 'bounded_result', label: 'Bounded result' },
  masked_or_restricted_result: { value: 'masked_or_restricted_result', label: 'Masked or restricted result' },
  deny_request: { value: 'deny_request', label: 'Deny request' },
  approval_stop: { value: 'approval_stop', label: 'Approval stop' },
  read_outcome: { value: 'read_outcome', label: 'Read outcome' },
  write_outcome: { value: 'write_outcome', label: 'Write outcome' },
  raw_data_export: { value: 'raw_data_export', label: 'Export raw data' },
  external_dispatch: { value: 'external_dispatch', label: 'Send outside the system' },
  unsupported: { value: 'unsupported', label: 'Unsupported' },
  native_anip: { value: 'native_anip', label: 'Native ANIP' },
  contract_gap: { value: 'contract_gap', label: 'Contract gap' },
  custom_service_logic: { value: 'custom_service_logic', label: 'Custom service logic' },
  agent_app_glue: { value: 'agent_app_glue', label: 'Agent app glue' },
  external_integration: { value: 'external_integration', label: 'External integration' },
  explicit_app_glue: { value: 'explicit_app_glue', label: 'Explicit app glue' },
  acceptable_warning: { value: 'acceptable_warning', label: 'Acceptable warning' },
  contract_owned: { value: 'contract_owned', label: 'Owned by contract' },
  not_started: { value: 'not_started', label: 'Not started' },
  in_progress: { value: 'in_progress', label: 'In progress' },
  ready_for_pm_review: { value: 'ready_for_pm_review', label: 'Ready for PM review' },
  pending: { value: 'pending', label: 'Pending review' },
  approved: { value: 'approved', label: 'Approved' },
  changes_requested: { value: 'changes_requested', label: 'Changes requested' },
  not_addressed: { value: 'not_addressed', label: 'Not addressed' },
  partially_addressed: { value: 'partially_addressed', label: 'Partially addressed' },
  addressed: { value: 'addressed', label: 'Addressed' },
  deferred: { value: 'deferred', label: 'Intentionally deferred' },
  not_applicable: { value: 'not_applicable', label: 'Not applicable' },
  service_metadata_insufficient: { value: 'service_metadata_insufficient', label: 'Service metadata is insufficient' },
  clarification_loop_detected: { value: 'clarification_loop_detected', label: 'Clarification loop detected' },
  backend_semantics_mismatch: { value: 'backend_semantics_mismatch', label: 'Backend behavior mismatch' },
  restriction_mapping_missing: { value: 'restriction_mapping_missing', label: 'Restriction mapping missing' },
  developer_binding_incomplete: { value: 'developer_binding_incomplete', label: 'Developer binding incomplete' },
  approval_policy_gap: { value: 'approval_policy_gap', label: 'Approval policy gap' },
  approval_orchestration_missing: { value: 'approval_orchestration_missing', label: 'Approval orchestration missing' },
  consuming_agent: { value: 'consuming_agent', label: 'Consuming app or agent' },
  service_implementation: { value: 'service_implementation', label: 'Service implementation' },
  developer_design: { value: 'developer_design', label: 'Developer design' },
  product_design: { value: 'product_design', label: 'Product design' },
  assistant: { value: 'assistant', label: 'AI assistant' },
  readiness: { value: 'readiness', label: 'Agent readiness' },
  backend: { value: 'backend', label: 'Backend system' },
  clarification: { value: 'clarification', label: 'Clarification decision' },
  capability_identity: { value: 'capability_identity', label: 'Capability identity' },
  service_ownership: { value: 'service_ownership', label: 'Service ownership' },
  permission_mapping: { value: 'permission_mapping', label: 'Permission mapping' },
  composition_ambiguity: { value: 'composition_ambiguity', label: 'Composition ambiguity' },
  unsafe_boundary: { value: 'unsafe_boundary', label: 'Unsafe boundary' },
  agent_readiness: { value: 'agent_readiness', label: 'Agent readiness' },
  unsupported_effect: { value: 'unsupported_effect', label: 'Unsupported effect' },
  app_glue: { value: 'app_glue', label: 'App glue' },
  derived_target: { value: 'derived_target', label: 'Derived target' },
  from_service_design: { value: 'from_service_design', label: 'Generate from service design' },
  single_service_scaffold: { value: 'single_service_scaffold', label: 'Collapse to one service' },
  selected_services: { value: 'selected_services', label: 'Generate selected services only' },
  single_instance: { value: 'single_instance', label: 'Single instance' },
  stateless_horizontal: { value: 'stateless_horizontal', label: 'Stateless horizontal scale' },
  control_plane_workers: { value: 'control_plane_workers', label: 'Control plane and workers' },
  mixed: { value: 'mixed', label: 'Mixed posture' },
  anip_http: { value: 'anip_http', label: 'ANIP over HTTP' },
  grpc: { value: 'grpc', label: 'gRPC' },
  async_events: { value: 'async_events', label: 'Async events' },
  python_fastapi: { value: 'python_fastapi', label: 'Python and FastAPI' },
  typescript_node: { value: 'typescript_node', label: 'TypeScript and Node' },
  monorepo: { value: 'monorepo', label: 'Monorepo layout' },
  multi_repo: { value: 'multi_repo', label: 'Multi-repo layout' },
  embedded_existing_product: { value: 'embedded_existing_product', label: 'Embedded in existing product' },
  standalone_service: { value: 'standalone_service', label: 'One standalone service' },
  multiple_coordinated_services: { value: 'multiple_coordinated_services', label: 'Multiple coordinated services' },
  single_service: { value: 'single_service', label: 'Single service' },
  multi_service_estate: { value: 'multi_service_estate', label: 'Multiple service boundaries' },
  service_owned: { value: 'service_owned', label: 'Owned by this service' },
  service_owner: { value: 'service_owner', label: 'Service owner' },
  service_facade: { value: 'service_facade', label: 'Service facade' },
  orchestration_owner: { value: 'orchestration_owner', label: 'Orchestration owner' },
  signed: { value: 'signed', label: 'Signed trust' },
  unsigned: { value: 'unsigned', label: 'Unsigned trust' },
  anchored: { value: 'anchored', label: 'Anchored trust' },
  attested: { value: 'attested', label: 'Attested trust' },
  not_specified: { value: 'not_specified', label: 'Not specified' },
  not_recorded: { value: 'not_recorded', label: 'Not recorded' },
  legacy_projection: { value: 'legacy_projection', label: 'Legacy projection' },
  compiled_contract: { value: 'compiled_contract', label: 'Compiled contract' },
  approval_required_for_high_risk: { value: 'approval_required_for_high_risk', label: 'Approval required for high-risk work' },
  approval_required_for_write: { value: 'approval_required_for_write', label: 'Approval required for write actions' },
  approval_required_for_governed_work: { value: 'approval_required_for_governed_work', label: 'Approval required for governed work' },
  no_approval_expected: { value: 'no_approval_expected', label: 'No approval expected' },
  structured_blocked: { value: 'structured_blocked', label: 'Return a structured blocked response' },
  retry_with_backoff: { value: 'retry_with_backoff', label: 'Retry with backoff' },
  escalate_to_human: { value: 'escalate_to_human', label: 'Escalate to a human' },
  fail_safe: { value: 'fail_safe', label: 'Fail safe' },
  curated_sql: { value: 'curated_sql', label: 'Curated SQL' },
  cube_rest: { value: 'cube_rest', label: 'Cube REST' },
  snowflake_sql: { value: 'snowflake_sql', label: 'Snowflake SQL' },
  snowflake_semantic: { value: 'snowflake_semantic', label: 'Snowflake semantic model' },
  databricks_sql: { value: 'databricks_sql', label: 'Databricks SQL' },
  databricks_genie: { value: 'databricks_genie', label: 'Databricks Genie' },
  dbt_semantic: { value: 'dbt_semantic', label: 'dbt semantic layer' },
  internal_metrics_api: { value: 'internal_metrics_api', label: 'Internal metrics API' },
  custom_adapter: { value: 'custom_adapter', label: 'Custom adapter' },
  rest_api: { value: 'rest_api', label: 'REST API' },
  graphql_api: { value: 'graphql_api', label: 'GraphQL API' },
  mcp_server: { value: 'mcp_server', label: 'MCP server' },
  internal_http_service: { value: 'internal_http_service', label: 'Internal HTTP service' },
  development: { value: 'development', label: 'Development' },
  staging: { value: 'staging', label: 'Staging' },
  production: { value: 'production', label: 'Production' },
  api_key: { value: 'api_key', label: 'API key' },
  bearer_token: { value: 'bearer_token', label: 'Bearer token' },
  oauth2: { value: 'oauth2', label: 'OAuth 2' },
  session_cookie: { value: 'session_cookie', label: 'Session cookie' },
  object: { value: 'object', label: 'Object' },
  field: { value: 'field', label: 'Field' },
  capability: { value: 'capability', label: 'Capability' },
  result_limit: { value: 'result_limit', label: 'Result limit' },
  field_projection: { value: 'field_projection', label: 'Field projection' },
  allowed_assignees: { value: 'allowed_assignees', label: 'Allowed assignees' },
  supported_object_subset: { value: 'supported_object_subset', label: 'Supported object subset' },
  ambiguous_record: { value: 'ambiguous_record', label: 'Ambiguous record' },
  ambiguous_object: { value: 'ambiguous_object', label: 'Ambiguous object' },
  missing_required_input: { value: 'missing_required_input', label: 'Missing required input' },
  ambiguous_assignee: { value: 'ambiguous_assignee', label: 'Ambiguous assignee' },
  ambiguous_due_date: { value: 'ambiguous_due_date', label: 'Ambiguous due date' },
  unsupported_object: { value: 'unsupported_object', label: 'Unsupported object' },
  forbidden_field: { value: 'forbidden_field', label: 'Forbidden field' },
  missing_purpose: { value: 'missing_purpose', label: 'Missing purpose' },
  authority_missing: { value: 'authority_missing', label: 'Missing authority' },
}

function fallbackLabel(value: string): string {
  return value
    .replace(/[._-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

export function developerVocabularyEntry(value: string | undefined | null): DeveloperVocabularyEntry {
  const normalized = String(value ?? '').trim()
  if (!normalized) {
    return { value: '', label: 'Not set' }
  }
  return DEVELOPER_VOCABULARY[normalized] ?? {
    value: normalized,
    label: fallbackLabel(normalized),
  }
}

export function isKnownDeveloperValue(value: string | undefined | null): boolean {
  const normalized = String(value ?? '').trim()
  return Boolean(normalized && DEVELOPER_VOCABULARY[normalized])
}

export function developerLabel(value: string | undefined | null, emptyLabel = 'Not set'): string {
  const normalized = String(value ?? '').trim()
  if (!normalized) return emptyLabel
  return developerVocabularyEntry(normalized).label
}

export function developerTechnicalLabel(value: string | undefined | null, emptyLabel = ''): string {
  const normalized = String(value ?? '').trim()
  return normalized ? `Canonical value: ${normalized}` : emptyLabel
}

export function developerLabelWithTechnical(value: string | undefined | null, emptyLabel = 'Not set'): string {
  const normalized = String(value ?? '').trim()
  if (!normalized) return emptyLabel
  return `${developerLabel(normalized)} (${normalized})`
}

export function formatDeveloperList(values: Array<string | undefined | null> | undefined | null, emptyLabel = 'None selected'): string {
  const labels = (values ?? [])
    .map((value) => String(value ?? '').trim())
    .filter(Boolean)
    .map((value) => developerLabel(value))
  return labels.length ? labels.join(', ') : emptyLabel
}

export function optionLabel(options: DeveloperOption[], value: string | undefined | null, emptyLabel = 'Not set'): string {
  const normalized = String(value ?? '').trim()
  if (!normalized) return emptyLabel
  return options.find((option) => option.value === normalized)?.label ?? developerLabel(normalized)
}
