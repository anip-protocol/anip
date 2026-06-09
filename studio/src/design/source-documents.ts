import type { ProjectDetail, ProjectDocumentRecord } from './project-types'

export type SourceDocumentKind =
  | 'business_spec'
  | 'business_intent'
  | 'requirements_source'
  | 'developer_interface'
  | 'semantic_model'
  | 'integration_contract'
  | 'api_docs'
  | 'mcp_schema'
  | 'auth_docs'
  | 'permission_matrix'
  | 'workflow_docs'
  | 'policy_source'
  | 'runtime_evidence'
  | 'reference'

export interface SourceDocumentKindOption {
  value: SourceDocumentKind
  label: string
  description: string
}

const STANDARD_SOURCE_KIND_OPTIONS: SourceDocumentKindOption[] = [
  {
    value: 'business_spec',
    label: 'Business spec',
    description: 'PM-readable business goals, actors, scenarios, rules, and expected outcomes.',
  },
  {
    value: 'requirements_source',
    label: 'Requirements source',
    description: 'Existing requirements, PRDs, or stakeholder notes that should inform Product Design.',
  },
  {
    value: 'policy_source',
    label: 'Org policy',
    description: 'Security, privacy, approval, audit, or data-handling policy that constrains behavior.',
  },
  {
    value: 'reference',
    label: 'Supporting reference',
    description: 'Any supporting document that helps review or explain the intended product.',
  },
]

const FRONTING_EXTRA_SOURCE_KIND_OPTIONS: SourceDocumentKindOption[] = [
  {
    value: 'business_intent',
    label: 'Fronting intent',
    description: 'What agents or people should be allowed to accomplish through the governed ANIP layer.',
  },
  {
    value: 'integration_contract',
    label: 'API/OpenAPI contract',
    description: 'OpenAPI, Swagger, GraphQL, protobuf, SDK contract, or endpoint schema.',
  },
  {
    value: 'mcp_schema',
    label: 'MCP schema',
    description: 'MCP tool, resource, prompt, or server discovery schema.',
  },
  {
    value: 'api_docs',
    label: 'API docs',
    description: 'Technical API documentation, examples, lifecycle behavior, errors, and rate limits.',
  },
  {
    value: 'auth_docs',
    label: 'Auth and scopes',
    description: 'OAuth scopes, service-account behavior, user delegation, SSO, and credential posture.',
  },
  {
    value: 'permission_matrix',
    label: 'Permission matrix',
    description: 'Roles, scopes, allowed actions, approval boundaries, and denial behavior.',
  },
  {
    value: 'workflow_docs',
    label: 'Workflow/status docs',
    description: 'State transitions, required fields, lifecycle rules, webhooks, and operational runbooks.',
  },
  {
    value: 'runtime_evidence',
    label: 'Runtime evidence',
    description: 'Observed metadata, examples, existing skills, prompts, logs, or migration evidence.',
  },
]

const DEVELOPER_SOURCE_KIND_OPTIONS: SourceDocumentKindOption[] = [
  {
    value: 'developer_interface',
    label: 'Developer interface',
    description: 'Developer-owned service notes, runtime input contracts, handler boundaries, or implementation surface decisions.',
  },
  {
    value: 'integration_contract',
    label: 'API/OpenAPI contract',
    description: 'OpenAPI, Swagger, GraphQL, protobuf, SDK contract, or endpoint schema.',
  },
  {
    value: 'mcp_schema',
    label: 'MCP schema',
    description: 'MCP tool, resource, prompt, or server discovery schema.',
  },
  {
    value: 'semantic_model',
    label: 'Semantic model',
    description: 'dbt, Cube, Superset, BI, metrics, dataset, dimension, or governed query surface documentation.',
  },
  {
    value: 'api_docs',
    label: 'API docs',
    description: 'Technical API documentation, examples, lifecycle behavior, errors, and rate limits.',
  },
  {
    value: 'auth_docs',
    label: 'Auth and scopes',
    description: 'OAuth scopes, service-account behavior, user delegation, SSO, and credential posture.',
  },
  {
    value: 'permission_matrix',
    label: 'Permission matrix',
    description: 'Roles, scopes, allowed actions, approval boundaries, and denial behavior.',
  },
  {
    value: 'workflow_docs',
    label: 'Workflow/status docs',
    description: 'State transitions, required fields, lifecycle rules, webhooks, and operational runbooks.',
  },
  {
    value: 'runtime_evidence',
    label: 'Runtime evidence',
    description: 'Observed metadata, examples, logs, generated package metadata, or migration evidence.',
  },
  {
    value: 'reference',
    label: 'Supporting reference',
    description: 'Any supporting document that helps review or explain the developer design.',
  },
]

const SOURCE_KIND_LABELS = new Map(
  [...STANDARD_SOURCE_KIND_OPTIONS, ...FRONTING_EXTRA_SOURCE_KIND_OPTIONS, ...DEVELOPER_SOURCE_KIND_OPTIONS].map((option) => [option.value, option.label]),
)

const FRONTING_INTENT_KINDS = new Set<SourceDocumentKind>([
  'business_spec',
  'business_intent',
  'requirements_source',
])

const FRONTING_INTEGRATION_KINDS = new Set<SourceDocumentKind>([
  'developer_interface',
  'integration_contract',
  'api_docs',
  'mcp_schema',
  'semantic_model',
  'auth_docs',
  'permission_matrix',
  'workflow_docs',
  'runtime_evidence',
])

const DEVELOPER_SOURCE_KINDS = new Set<SourceDocumentKind>([
  'developer_interface',
  'integration_contract',
  'api_docs',
  'mcp_schema',
  'semantic_model',
  'auth_docs',
  'permission_matrix',
  'workflow_docs',
  'policy_source',
  'runtime_evidence',
])

export function isGovernedFrontingProject(project: ProjectDetail | null | undefined): boolean {
  return project?.project_type === 'governed_service_project'
}

export function sourceDocumentKindOptions(project: ProjectDetail | null | undefined): SourceDocumentKindOption[] {
  if (!isGovernedFrontingProject(project)) return STANDARD_SOURCE_KIND_OPTIONS
  return [
    FRONTING_EXTRA_SOURCE_KIND_OPTIONS[0],
    ...STANDARD_SOURCE_KIND_OPTIONS,
    ...FRONTING_EXTRA_SOURCE_KIND_OPTIONS.slice(1),
  ]
}

export function developerSourceDocumentKindOptions(): SourceDocumentKindOption[] {
  return DEVELOPER_SOURCE_KIND_OPTIONS
}

export function defaultSourceDocumentKind(project: ProjectDetail | null | undefined): SourceDocumentKind {
  return isGovernedFrontingProject(project) ? 'business_intent' : 'business_spec'
}

export function defaultDeveloperSourceDocumentKind(): SourceDocumentKind {
  return 'developer_interface'
}

export function sourceDocumentKindLabel(kind: string | null | undefined): string {
  return SOURCE_KIND_LABELS.get(kind as SourceDocumentKind) ?? humanizeSourceKind(kind)
}

export function humanizeSourceKind(kind: string | null | undefined): string {
  return String(kind || 'reference').replace(/_/g, ' ')
}

export function isFrontingIntentSource(document: ProjectDocumentRecord | null | undefined): boolean {
  return FRONTING_INTENT_KINDS.has(document?.kind as SourceDocumentKind)
}

export function isFrontingIntegrationSource(document: ProjectDocumentRecord | null | undefined): boolean {
  return FRONTING_INTEGRATION_KINDS.has(document?.kind as SourceDocumentKind)
}

export function isDeveloperSourceDocument(document: ProjectDocumentRecord | null | undefined): boolean {
  return DEVELOPER_SOURCE_KINDS.has(document?.kind as SourceDocumentKind)
}

export function isProductSourceDocument(document: ProjectDocumentRecord | null | undefined): boolean {
  return !isDeveloperSourceDocument(document)
}

export function hasFrontingIntentSource(documents: ProjectDocumentRecord[]): boolean {
  return documents.some(isFrontingIntentSource)
}

export function hasFrontingIntegrationSource(documents: ProjectDocumentRecord[]): boolean {
  return documents.some(isFrontingIntegrationSource)
}

export function hasDeveloperSourceDocument(documents: ProjectDocumentRecord[]): boolean {
  return documents.some(isDeveloperSourceDocument)
}
