import { readFile } from 'node:fs/promises'
import { basename, resolve } from 'node:path'
import { createHash, webcrypto } from 'node:crypto'

import {
  createIntegrationDiscoveryRecord,
  createPmArtifact,
  createProject,
  createProjectDocument,
  createRequirements,
  createScenario,
  createWorkspace,
  createWorkspaceConnection,
  getWorkspace,
  getProject,
  listPmArtifacts,
  listProjectDocuments,
  listRequirements,
  listScenarios,
  listShapes,
  updatePmArtifact,
  updateRequirements,
  updateScenario,
} from '../src/design/project-api'
import {
  buildDeveloperDefinitionContract,
  buildDeveloperDefinitionData,
  developerDefinitionArtifactId,
  developerDefinitionRevisionArtifactId,
  stableStringify,
  validateDeveloperDefinitionRequiredFields,
  INTEGRATION_FRONTING_MAPPING_ARTIFACT_TYPE,
} from '../src/design/developer-definition'
import {
  buildDeveloperBaseline,
  developerBaselineArtifactId,
  buildTraceabilityRecord,
  traceabilityArtifactId,
} from '../src/design/traceability'
import {
  ACTOR_MODEL_ARTIFACT_TYPE,
  BUSINESS_AREAS_ARTIFACT_TYPE,
  PERMISSION_INTENT_ARTIFACT_TYPE,
  PRODUCT_DESIGN_REVISION_ARTIFACT_TYPE,
  PRODUCT_SUMMARY_ARTIFACT_TYPE,
  buildProductDesignRevision,
  productDesignArtifactId,
  productDesignRevisionArtifactId,
} from '../src/design/product-design'
import {
  buildHighRiskConfirmationReport,
} from '../src/design/high-risk-confirmations'
import {
  analyzeAgentConsumptionReadiness,
  applyReadinessFindingReviews,
  type AgentConsumptionReadinessFinding,
  type AgentConsumptionReadinessFindingReview,
} from '../src/design/agent-consumption-readiness'
import type {
  AgentConsumabilityCapabilityReview,
} from '../src/design/agent-consumability'
import type {
  ArtifactRecord,
  DeveloperCapabilityFormalization,
  DeveloperCompiledContractIdentity,
  DeveloperDefinitionData,
  DeveloperDefinitionRevisionData,
  IntegrationBackendKind,
  ProjectDetail,
  RequirementsRecord,
  ShapeRecord,
  TraceabilityRecordData,
} from '../src/design/project-types'

const repoRoot = resolve(new URL('../..', import.meta.url).pathname)
const apiBase = process.env.STUDIO_API_BASE || 'http://127.0.0.1:8100'
const webBase = (process.env.STUDIO_WEB_BASE || 'http://localhost:5173').replace(/\/+$/, '')
const nowStamp = new Date().toISOString().replace(/[-:.TZ]/g, '').slice(0, 14)
const stableIds = process.env.FRONTING_BATCH_STABLE_IDS === '1'
const projectIdToken = stableIds ? 'showcase' : nowStamp
const workspaceId = process.env.FRONTING_BATCH_WORKSPACE_ID || (stableIds ? 'ws-anip-showcases' : `ws-fronting-showcase-${nowStamp}`)
const selectedExampleKeys = new Set(
  (process.env.FRONTING_BATCH_EXAMPLES ?? '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean),
)

if (!globalThis.crypto) {
  Object.defineProperty(globalThis, 'crypto', { value: webcrypto })
}

const nativeFetch = globalThis.fetch.bind(globalThis)
globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) => {
  if (typeof input === 'string' && input.startsWith('/')) {
    return nativeFetch(`${apiBase}${input}`, init)
  }
  return nativeFetch(input, init)
}) as typeof globalThis.fetch

type ExampleConfig = {
  key: 'jira' | 'github' | 'slack' | 'gitlab' | 'notion' | 'linear' | 'superset'
  name: string
  domain: string
  summary: string
  sourceDoc: string
  serviceDefinition: string
  projectId: string
  connections: Array<{
    id: string
    display_name: string
    backend_kind: IntegrationBackendKind
    system_kind: string
    endpoint_ref: string
    auth_mode: 'user_delegated' | 'service_delegated' | 'external'
    identity_provider_ref: string
    secret_ref: string
  }>
}

type ProjectState = {
  project: ProjectDetail
  pmArtifacts: ArtifactRecord[]
  documents: Awaited<ReturnType<typeof listProjectDocuments>>
  requirements: RequirementsRecord[]
  scenarios: ArtifactRecord[]
  shapes: ShapeRecord[]
}

const examples: ExampleConfig[] = [
  {
    key: 'jira',
    name: 'Jira Governed Fronting Showcase',
    domain: 'jira',
    summary: 'ANIP governed service in front of native Jira REST APIs with an Atlassian MCP alternate backend path.',
    sourceDoc: 'docs/examples/jira-fronting-showcase/source-spec.md',
    serviceDefinition: 'docs/examples/jira-fronting-showcase/anip-fronting-starter.json',
    projectId: `jira-fronting-studio-${projectIdToken}`,
    connections: [
      {
        id: 'jira_rest_api',
        display_name: 'Jira REST API',
        backend_kind: 'native_api',
        system_kind: 'jira',
        endpoint_ref: 'JIRA_BASE_URL',
        auth_mode: 'service_delegated',
        identity_provider_ref: 'enterprise-sso',
        secret_ref: 'JIRA_API_TOKEN',
      },
      {
        id: 'atlassian_mcp',
        display_name: 'Atlassian MCP',
        backend_kind: 'mcp',
        system_kind: 'atlassian',
        endpoint_ref: 'ATLASSIAN_MCP_ENDPOINT',
        auth_mode: 'external',
        identity_provider_ref: 'atlassian-oauth',
        secret_ref: 'ATLASSIAN_MCP_TOKEN',
      },
    ],
  },
  {
    key: 'github',
    name: 'GitHub Governed Fronting Showcase',
    domain: 'github',
    summary: 'ANIP governed service in front of native GitHub REST/GraphQL APIs with a GitHub MCP alternate backend path.',
    sourceDoc: 'docs/examples/github-fronting-showcase/source-spec.md',
    serviceDefinition: 'docs/examples/github-fronting-showcase/anip-fronting-starter.json',
    projectId: `github-fronting-studio-${projectIdToken}`,
    connections: [
      {
        id: 'github_rest_graphql_api',
        display_name: 'GitHub REST/GraphQL API',
        backend_kind: 'native_api',
        system_kind: 'github',
        endpoint_ref: 'https://api.github.com',
        auth_mode: 'service_delegated',
        identity_provider_ref: 'enterprise-sso',
        secret_ref: 'GITHUB_TOKEN',
      },
      {
        id: 'github_mcp',
        display_name: 'GitHub MCP',
        backend_kind: 'mcp',
        system_kind: 'github',
        endpoint_ref: 'GITHUB_MCP_ENDPOINT',
        auth_mode: 'external',
        identity_provider_ref: 'github-oauth',
        secret_ref: 'GITHUB_MCP_TOKEN',
      },
    ],
  },
  {
    key: 'slack',
    name: 'Slack Governed Fronting Showcase',
    domain: 'slack',
    summary: 'ANIP governed service in front of native Slack Web APIs with a Slack MCP alternate backend path.',
    sourceDoc: 'docs/examples/slack-fronting-showcase/source-spec.md',
    serviceDefinition: 'examples/showcase/slack_fronting/registry-packages/slack-fronting-showcase-0.2.0-service-definition.json',
    projectId: `slack-fronting-studio-${projectIdToken}`,
    connections: [
      {
        id: 'slack_web_api',
        display_name: 'Slack Web API',
        backend_kind: 'native_api',
        system_kind: 'slack',
        endpoint_ref: 'https://slack.com/api',
        auth_mode: 'service_delegated',
        identity_provider_ref: 'enterprise-sso',
        secret_ref: 'SLACK_BOT_TOKEN',
      },
      {
        id: 'slack_mcp',
        display_name: 'Slack MCP',
        backend_kind: 'mcp',
        system_kind: 'slack',
        endpoint_ref: 'SLACK_MCP_ENDPOINT',
        auth_mode: 'external',
        identity_provider_ref: 'slack-oauth',
        secret_ref: 'SLACK_MCP_TOKEN',
      },
    ],
  },
  {
    key: 'gitlab',
    name: 'GitLab Governed Fronting Showcase',
    domain: 'gitlab',
    summary: 'ANIP governed service in front of native GitLab REST APIs with a GitLab MCP alternate backend path.',
    sourceDoc: 'docs/examples/gitlab-fronting-showcase/source-spec.md',
    serviceDefinition: 'docs/examples/gitlab-fronting-showcase/anip-fronting-starter.json',
    projectId: `gitlab-fronting-studio-${projectIdToken}`,
    connections: [
      {
        id: 'gitlab_rest_api',
        display_name: 'GitLab REST API',
        backend_kind: 'native_api',
        system_kind: 'gitlab',
        endpoint_ref: 'https://gitlab.com/api/v4',
        auth_mode: 'service_delegated',
        identity_provider_ref: 'enterprise-sso',
        secret_ref: 'GITLAB_TOKEN',
      },
      {
        id: 'gitlab_mcp',
        display_name: 'GitLab MCP',
        backend_kind: 'mcp',
        system_kind: 'gitlab',
        endpoint_ref: 'GITLAB_MCP_ENDPOINT',
        auth_mode: 'external',
        identity_provider_ref: 'gitlab-oauth',
        secret_ref: 'GITLAB_MCP_TOKEN',
      },
    ],
  },
  {
    key: 'notion',
    name: 'Notion Governed Fronting Showcase',
    domain: 'notion',
    summary: 'ANIP governed service in front of native Notion APIs with a Notion MCP alternate backend path.',
    sourceDoc: 'docs/examples/notion-fronting-showcase/source-spec.md',
    serviceDefinition: 'docs/examples/notion-fronting-showcase/anip-fronting-starter.json',
    projectId: `notion-fronting-studio-${projectIdToken}`,
    connections: [
      {
        id: 'notion_api',
        display_name: 'Notion API',
        backend_kind: 'native_api',
        system_kind: 'notion',
        endpoint_ref: 'https://api.notion.com/v1',
        auth_mode: 'service_delegated',
        identity_provider_ref: 'enterprise-sso',
        secret_ref: 'NOTION_TOKEN',
      },
      {
        id: 'notion_mcp',
        display_name: 'Notion MCP',
        backend_kind: 'mcp',
        system_kind: 'notion',
        endpoint_ref: 'NOTION_MCP_ENDPOINT',
        auth_mode: 'external',
        identity_provider_ref: 'notion-oauth',
        secret_ref: 'NOTION_MCP_TOKEN',
      },
    ],
  },
  {
    key: 'linear',
    name: 'Linear Governed Fronting Showcase',
    domain: 'linear',
    summary: 'ANIP governed service in front of native Linear GraphQL APIs with a Linear MCP alternate backend path.',
    sourceDoc: 'docs/examples/linear-fronting-showcase/source-spec.md',
    serviceDefinition: 'docs/examples/linear-fronting-showcase/anip-fronting-starter.json',
    projectId: `linear-fronting-studio-${projectIdToken}`,
    connections: [
      {
        id: 'linear_graphql_api',
        display_name: 'Linear GraphQL API',
        backend_kind: 'native_api',
        system_kind: 'linear',
        endpoint_ref: 'https://api.linear.app/graphql',
        auth_mode: 'service_delegated',
        identity_provider_ref: 'enterprise-sso',
        secret_ref: 'LINEAR_API_KEY',
      },
      {
        id: 'linear_mcp',
        display_name: 'Linear MCP',
        backend_kind: 'mcp',
        system_kind: 'linear',
        endpoint_ref: 'LINEAR_MCP_ENDPOINT',
        auth_mode: 'external',
        identity_provider_ref: 'linear-oauth',
        secret_ref: 'LINEAR_MCP_TOKEN',
      },
    ],
  },
  {
    key: 'superset',
    name: 'Superset Governed Fronting Showcase',
    domain: 'superset',
    summary: 'ANIP governed service in front of native Superset REST APIs with a Superset MCP alternate backend path.',
    sourceDoc: 'docs/examples/superset-fronting-showcase/source-spec.md',
    serviceDefinition: 'docs/examples/superset-fronting-showcase/anip-fronting-starter.json',
    projectId: `superset-fronting-studio-${projectIdToken}`,
    connections: [
      {
        id: 'superset_rest_api',
        display_name: 'Superset REST API',
        backend_kind: 'native_api',
        system_kind: 'superset',
        endpoint_ref: 'SUPERSET_API_URL',
        auth_mode: 'service_delegated',
        identity_provider_ref: 'enterprise-sso',
        secret_ref: 'SUPERSET_SERVICE_TOKEN',
      },
      {
        id: 'superset_mcp',
        display_name: 'Superset MCP',
        backend_kind: 'mcp',
        system_kind: 'superset',
        endpoint_ref: 'SUPERSET_MCP_ENDPOINT',
        auth_mode: 'external',
        identity_provider_ref: 'superset-jwt',
        secret_ref: 'SUPERSET_MCP_TOKEN',
      },
    ],
  },
]

function log(message: string) {
  process.stdout.write(`[fronting-batch] ${message}\n`)
}

async function ensureWorkspace(payload: { id: string; name: string; summary?: string }) {
  try {
    await getWorkspace(payload.id)
    log(`Workspace ${payload.id} already exists`)
    return
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    if (!message.includes('404')) {
      throw error
    }
  }
  await createWorkspace(payload)
}

function sha256Hex(value: string): string {
  return createHash('sha256').update(value).digest('hex')
}

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function contractIdentityPayload(baseContract: Record<string, any>) {
  const payload = clone(baseContract)
  delete payload.generated_at
  delete payload.compiled_contract_identity
  if (payload.source?.developer_definition_revision) {
    payload.source.developer_definition_revision = null
  }
  return payload
}

function serviceDefinitionPath(example: ExampleConfig): string {
  return resolve(repoRoot, example.serviceDefinition)
}

function sourceDocPath(example: ExampleConfig): string {
  return resolve(repoRoot, example.sourceDoc)
}

async function readJson(path: string): Promise<Record<string, any>> {
  return JSON.parse(await readFile(path, 'utf8')) as Record<string, any>
}

function backendBindingForStarterOperation(
  example: ExampleConfig,
  operation: Record<string, any>,
  rawOperationRefs: string[],
  kind: IntegrationBackendKind,
): Record<string, any> | null {
  const refs = rawOperationRefs.filter((ref) =>
    kind === 'mcp'
      ? ref.includes('.mcp.') || ref.includes('mcp.')
      : !(ref.includes('.mcp.') || ref.includes('mcp.')),
  )
  if (refs.length === 0) return null
  const connection = kind === 'mcp'
    ? example.connections.find((item) => item.backend_kind === 'mcp')
    : example.connections.find((item) => item.backend_kind === 'native_api')
  return {
    backend_kind: kind,
    connection_ref: connection?.id ?? String(operation.connection_ref ?? ''),
    raw_operation_refs: refs,
    matched_discovery_record_ids: refs.map((ref) => `${operation.capability_id}-${kind}-${ref}`.replace(/[^a-z0-9_-]+/gi, '-')),
    explicit_required_backend_inputs: inputNames(operation, 'required'),
    explicit_optional_backend_inputs: inputNames(operation, 'optional'),
    backend_input_mode: operation.backend_input_mode ?? 'hybrid',
    status: 'candidate',
    status_detail: `${kind === 'mcp' ? 'MCP alternate' : 'Native API'} backend supply for the governed capability.`,
  }
}

function normalizeFrontingStarterDefinition(example: ExampleConfig, source: Record<string, any>): Record<string, any> {
  if (source.schema_version !== 'anip-fronting-starter/v0') return source
  const operations = Array.isArray(source.operations) ? source.operations as Record<string, any>[] : []
  const capabilityFormalizations = operations.map((operation) => ({
    capability_id: String(operation.capability_id ?? ''),
    title: String(operation.title ?? operation.capability_id ?? ''),
    summary: String(operation.summary ?? ''),
    subject_kind: String(operation.subject_kind ?? 'fronting_subject'),
    context_type: String(operation.context_type ?? 'fronting_context'),
    output_intent: String(operation.output_intent ?? 'governed_fronting_result'),
    side_effect_level: String(operation.side_effect_level ?? 'read'),
    inputs: Array.isArray(operation.inputs) ? operation.inputs : [],
  }))
  const capabilityMappings = operations.map((operation) => {
    const rawOperationRefs = Array.isArray(operation.raw_operation_refs)
      ? operation.raw_operation_refs.map((item: unknown) => String(item)).filter(Boolean)
      : []
    return {
      capability_id: String(operation.capability_id ?? ''),
      title: String(operation.title ?? operation.capability_id ?? ''),
      summary: String(operation.summary ?? ''),
      service_id: String(source.service_id ?? `${example.key}_fronting_service`),
      service_name: String(source.service_name ?? example.name),
      subject_kind: String(operation.subject_kind ?? 'fronting_subject'),
      context_type: String(operation.context_type ?? 'fronting_context'),
      output_intent: String(operation.output_intent ?? 'governed_fronting_result'),
      side_effect_level: String(operation.side_effect_level ?? 'read'),
      execution_posture: String(operation.side_effect_level ?? 'read') === 'read' ? 'read_only' : 'prepare_only',
      path_template: String(operation.path ?? `/${example.domain}/${String(operation.capability_id ?? 'capability').split('.').pop()}`),
      backend_input_mode: operation.backend_input_mode ?? 'hybrid',
      required_inputs: inputNames(operation, 'required'),
      optional_inputs: inputNames(operation, 'optional'),
      input_metadata: Array.isArray(operation.inputs) ? operation.inputs : [],
      raw_operation_refs: rawOperationRefs,
      backend_bindings: [
        backendBindingForStarterOperation(example, operation, rawOperationRefs, 'native_api'),
        backendBindingForStarterOperation(example, operation, rawOperationRefs, 'mcp'),
      ].filter(Boolean),
    }
  })
  return {
    identity: {
      system_name: source.system_name ?? example.name,
      domain_name: source.domain_name ?? example.domain,
    },
    service_topology_bindings: [
      {
        service_id: source.service_id ?? `${example.key}_fronting_service`,
        service_name: source.service_name ?? example.name,
      },
    ],
    permission_intent_bindings: [
      {
        actor_id: `${example.key}_fronting_consumer`,
      },
    ],
    capability_formalizations: capabilityFormalizations,
    integration_fronting: {
      capability_mappings: capabilityMappings,
    },
  }
}

async function loadState(projectId: string): Promise<ProjectState> {
  const [project, pmArtifacts, documents, requirements, scenarios, shapes] = await Promise.all([
    getProject(projectId),
    listPmArtifacts(projectId),
    listProjectDocuments(projectId),
    listRequirements(projectId),
    listScenarios(projectId),
    listShapes(projectId),
  ])
  return { project, pmArtifacts, documents, requirements, scenarios, shapes }
}

async function createSourceDoc(example: ExampleConfig) {
  const content = await readFile(sourceDocPath(example), 'utf8')
  const baseId = `${example.projectId}-doc-${basename(example.sourceDoc).replace(/[^a-z0-9]+/gi, '-').replace(/^-+|-+$/g, '').toLowerCase()}`
  await createProjectDocument(example.projectId, {
    id: `${baseId}-intent`,
    title: basename(example.sourceDoc),
    kind: 'business_intent',
    filename: basename(example.sourceDoc),
    media_type: 'text/markdown',
    source_path: example.sourceDoc,
    content_base64: Buffer.from(content, 'utf8').toString('base64'),
  })
  await createProjectDocument(example.projectId, {
    id: `${baseId}-api`,
    title: `${example.name} Native API Contract`,
    kind: 'api_docs',
    filename: `${example.key}-native-api.md`,
    media_type: 'text/markdown',
    source_path: `${example.sourceDoc}#native-api`,
    content_base64: Buffer.from([
      `# ${example.name} Native API Evidence`,
      '',
      `Studio models a native API backend for ${example.domain} as the primary implementation seam.`,
      'The generated ANIP service exposes only curated capabilities; raw endpoints remain adapter implementation details.',
    ].join('\n'), 'utf8').toString('base64'),
  })
  await createProjectDocument(example.projectId, {
    id: `${baseId}-mcp`,
    title: `${example.name} MCP Coverage Evidence`,
    kind: 'mcp_schema',
    filename: `${example.key}-mcp.md`,
    media_type: 'text/markdown',
    source_path: `${example.sourceDoc}#mcp`,
    content_base64: Buffer.from([
      `# ${example.name} MCP Evidence`,
      '',
      `Studio models MCP as an alternate backend for teams that already standardize on ${example.domain} MCP.`,
      'MCP coverage does not define the agent-facing ANIP surface; the reviewed governed capabilities do.',
    ].join('\n'), 'utf8').toString('base64'),
  })
}

function inputNames(mapping: Record<string, any>, kind: 'required' | 'optional'): string[] {
  const key = kind === 'required' ? 'required_inputs' : 'optional_inputs'
  if (Array.isArray(mapping[key])) return mapping[key].map((item: unknown) => String(item)).filter(Boolean)
  const inputs = Array.isArray(mapping.inputs) ? mapping.inputs as Record<string, any>[] : []
  return inputs
    .filter((input) => Boolean(input?.name) && Boolean(input?.required) === (kind === 'required'))
    .map((input) => String(input.name))
}

function requirementData(example: ExampleConfig, serviceDefinition: Record<string, any>) {
  const capabilities = Array.isArray(serviceDefinition.capability_formalizations)
    ? serviceDefinition.capability_formalizations
    : []
  return {
    system: {
      name: example.name,
      domain: example.domain,
      deployment_intent: 'centralized_anip_fronting_service',
    },
    services: [
      {
        name: String(serviceDefinition.service_topology_bindings?.[0]?.service_name ?? `${example.name} Service`),
        role: `Governed ANIP facade in front of ${example.domain} native API and MCP backend supply.`,
        public_http: true,
        internal_only: false,
      },
    ],
    transports: {
      http: true,
      mcp: true,
      stdio: false,
      grpc: false,
    },
    trust: {
      mode: 'actor_aware_governed_access',
      checkpoints: true,
    },
    permissions: {
      preflight_discovery: true,
      grantable_requirements: true,
      restricted_vs_denied: true,
    },
    auth: {
      delegation_tokens: true,
      scoped_authority: true,
      purpose_binding: true,
      service_to_service_handoffs: false,
    },
    audit: {
      durable: true,
      searchable: true,
      cross_service_reconstruction_required: false,
    },
    lineage: {
      invocation_id: true,
      task_id: true,
      parent_invocation_id: true,
      client_reference_id: true,
      cross_service_continuity_required: false,
    },
    business_constraints: {
      approval_expected_for_high_risk: true,
      recovery_sensitive: false,
      blocked_failure_posture: 'clarify_or_deny_before_downstream_call',
    },
    scale: {
      shape_preference: 'production_single_service',
      high_availability: true,
    },
    risk_profile: Object.fromEntries(capabilities.map((capability: Record<string, any>) => [
      String(capability.capability_id ?? '').replace(/[^a-z0-9_]+/gi, '_'),
      {
        side_effect: String(capability.side_effect_level ?? '') === 'write_adjacent' ? 'reversible' : 'none',
        high_risk: String(capability.side_effect_level ?? '') === 'write_adjacent',
        approval_required: String(capability.side_effect_level ?? '') === 'write_adjacent',
        recovery_guidance_required: String(capability.side_effect_level ?? '') === 'write_adjacent',
      },
    ])),
    source_documents: [
      {
        kind: 'business_intent',
        path: example.sourceDoc,
        title: basename(example.sourceDoc),
      },
      {
        kind: 'api_docs',
        path: `${example.sourceDoc}#native-api`,
        title: `${example.name} Native API Contract`,
      },
      {
        kind: 'mcp_schema',
        path: `${example.sourceDoc}#mcp`,
        title: `${example.name} MCP Coverage Evidence`,
      },
    ],
  }
}

function scenarioData(example: ExampleConfig, serviceDefinition: Record<string, any>) {
  const mappings = serviceDefinition.integration_fronting?.capability_mappings
  const capabilityIds = Array.isArray(mappings)
    ? mappings.map((mapping: Record<string, any>) => String(mapping.capability_id ?? '')).filter(Boolean)
    : []
  const serviceIds = Array.isArray(serviceDefinition.service_topology_bindings)
    ? serviceDefinition.service_topology_bindings.map((service: Record<string, any>) => String(service.service_id ?? '')).filter(Boolean)
    : []
  return {
    scenario: {
      name: `${example.key}_governed_fronting_path`,
      category: 'orchestration',
      narrative: `A consuming agent uses curated ANIP capabilities for ${example.domain} instead of direct raw API/MCP tools.`,
      context: {
        capability_surface: capabilityIds,
        backend_supply: ['native_api', 'mcp'],
        authority_boundary: 'curated_anip_capabilities_only',
      },
      participating_services: serviceIds,
      orchestration_steps: [
        'Classify the user request into a reviewed governed capability.',
        'Clarify missing required inputs before any downstream call.',
        'Use the native API adapter by default or MCP adapter when explicitly configured.',
        'Stop at preview or approval for write-adjacent actions.',
      ],
      expected_behavior: [
        'bound_downstream_context',
        'clarify_missing_required_inputs',
        'preview_or_approval_gate_write_adjacent_actions',
        'audit_every_governed_call',
      ],
      expected_anip_support: [
        'capability_contracts',
        'approval_grants',
        'denial_restriction_rules',
        'audit_lineage',
      ],
    },
  }
}

async function saveOrUpdatePmArtifact(projectId: string, id: string, title: string, data: Record<string, any>) {
  try {
    return await createPmArtifact(projectId, { id, title, data })
  } catch {
    return updatePmArtifact(projectId, id, { title, data })
  }
}

async function saveProductDesignArtifacts(example: ExampleConfig, serviceDefinition: Record<string, any>) {
  const actorId = String(serviceDefinition.permission_intent_bindings?.[0]?.actor_id ?? 'fronting_operator')
  const businessArea = `${example.key}_workspace`
  const capabilityIds = (serviceDefinition.capability_formalizations ?? [])
    .map((capability: Record<string, any>) => String(capability.capability_id ?? '').trim())
    .filter(Boolean)
  const writeLikeCount = (serviceDefinition.capability_formalizations ?? [])
    .filter((capability: Record<string, any>) => String(capability.side_effect_level ?? '') === 'write_adjacent')
    .length

  await saveOrUpdatePmArtifact(example.projectId, productDesignArtifactId(example.projectId, PRODUCT_SUMMARY_ARTIFACT_TYPE), 'Business Summary', {
    artifact_type: PRODUCT_SUMMARY_ARTIFACT_TYPE,
    product_purpose: `Provide a governed ANIP fronting layer for ${example.domain} so agents use reviewed capabilities instead of raw API or MCP tools.`,
    business_problem: `Raw ${example.domain} tools expose broad backend power and force teams to encode safety behavior in prompts or skills.`,
    business_goals: [
      'Expose curated governed capabilities.',
      'Keep raw backend operations behind adapter seams.',
      'Require clarification, audit, and approval where needed.',
    ],
    supported_question_families: capabilityIds,
    governed_behavior_summary: 'The service accepts only reviewed capability calls, validates required inputs, denies unsupported effects, and records audit lineage.',
    approval_posture_summary: writeLikeCount
      ? 'Write-adjacent actions stop at preview or approval before downstream mutation.'
      : 'Read-only actions are bounded and audited.',
    multi_step_composition_rules: [
      'Prefer native API adapters by default.',
      'Use MCP adapters only as an alternate backend implementation seam.',
    ],
    why_now: 'MCP and native APIs expose useful integration supply, but the organization needs a centralized governed behavior layer.',
    success_outcome_summary: 'Generated packages verify with zero blockers and agents see only governed ANIP capabilities.',
  })
  await saveOrUpdatePmArtifact(example.projectId, productDesignArtifactId(example.projectId, ACTOR_MODEL_ARTIFACT_TYPE), 'Actor Model', {
    artifact_type: ACTOR_MODEL_ARTIFACT_TYPE,
    actors: [
      {
        actor_id: actorId,
        title: 'Fronting Service Consumer',
        summary: `Uses governed ${example.domain} capabilities through ANIP instead of raw backend tools.`,
        visibility_expectations: 'Can see bounded results, previews, approvals, and denial reasons within actor-visible scope.',
        action_expectations: 'Can request governed reads and prepare/request flows; cannot bypass approval or call raw backend tools directly.',
        approval_expectations: 'Write-adjacent operations require preview or approval before mutation.',
        notes: 'Seeded by the fronting showcase batch from reviewed capability mappings.',
      },
    ],
  })
  await saveOrUpdatePmArtifact(example.projectId, productDesignArtifactId(example.projectId, BUSINESS_AREAS_ARTIFACT_TYPE), 'Business Areas', {
    artifact_type: BUSINESS_AREAS_ARTIFACT_TYPE,
    entries: [
      {
        business_area_id: businessArea,
        label: `${example.domain} governed workspace`,
        description: `Governed ${example.domain} access through curated ANIP capabilities.`,
      },
    ],
  })
  await saveOrUpdatePmArtifact(example.projectId, productDesignArtifactId(example.projectId, PERMISSION_INTENT_ARTIFACT_TYPE), 'Permission Intent', {
    artifact_type: PERMISSION_INTENT_ARTIFACT_TYPE,
    policy_summary: `Allow ${actorId} to use bounded ${example.domain} fronting capabilities; deny raw export, backend bypass, and unapproved mutation.`,
    rules: [
      {
        actor_id: actorId,
        business_area: businessArea,
        access_posture: 'bounded',
        governed_outcome_type: 'bounded_result',
        governed_outcome: `Actor may invoke curated ${example.domain} ANIP capabilities with required input validation, audit, and approval boundaries.`,
        notes: 'No raw API or MCP tool access is granted by Product Design.',
      },
    ],
  })

  const state = await loadState(example.projectId)
  const revision = buildProductDesignRevision({ projectId: example.projectId, pmArtifacts: state.pmArtifacts })
  await saveOrUpdatePmArtifact(example.projectId, productDesignRevisionArtifactId(example.projectId, revision.revision_number), 'Product Design Revision 1', {
    ...revision,
    artifact_type: PRODUCT_DESIGN_REVISION_ARTIFACT_TYPE,
  })
}

function scopedConnectionId(example: ExampleConfig, connectionId: string): string {
  return `${example.projectId}-${connectionId}`.replace(/[^a-zA-Z0-9_-]+/g, '-')
}

function scopedDiscoveryId(example: ExampleConfig, discoveryId: string): string {
  const raw = discoveryId.replace(/[^a-zA-Z0-9_-]+/g, '-')
  return raw.startsWith(`${example.projectId}-`) ? raw : `${example.projectId}-${raw}`
}

function remapConnectionRef(example: ExampleConfig, value: unknown): unknown {
  const raw = String(value ?? '').trim()
  if (!raw) return value
  return example.connections.some((connection) => connection.id === raw)
    ? scopedConnectionId(example, raw)
    : value
}

function remapMappingConnectionRefs(example: ExampleConfig, mapping: Record<string, any>): Record<string, any> {
  const next = clone(mapping)
  next.connection_ref = remapConnectionRef(example, next.connection_ref)
  if (Array.isArray(next.backend_bindings)) {
    next.backend_bindings = next.backend_bindings.map((binding: Record<string, any>) => ({
      ...binding,
      connection_ref: remapConnectionRef(example, binding.connection_ref),
      matched_discovery_record_ids: Array.isArray(binding.matched_discovery_record_ids)
        ? binding.matched_discovery_record_ids.map((id: unknown) => scopedDiscoveryId(example, String(id)))
        : binding.matched_discovery_record_ids,
      derived_required_backend_inputs: Array.isArray(binding.derived_required_backend_inputs)
        ? binding.derived_required_backend_inputs
        : Array.isArray(binding.explicit_required_backend_inputs)
          ? binding.explicit_required_backend_inputs
          : inputNames(next, 'required'),
      derived_optional_backend_inputs: Array.isArray(binding.derived_optional_backend_inputs)
        ? binding.derived_optional_backend_inputs
        : Array.isArray(binding.explicit_optional_backend_inputs)
          ? binding.explicit_optional_backend_inputs
          : inputNames(next, 'optional'),
    }))
  }
  return next
}

function sideEffectForOperation(ref: string, mappings: Record<string, any>[]): string {
  const mapping = mappings.find((item) =>
    Array.isArray(item.raw_operation_refs) && item.raw_operation_refs.includes(ref),
  )
  return String(mapping?.side_effect_level ?? 'read')
}

async function seedConnections(example: ExampleConfig) {
  for (const connection of example.connections) {
    await createWorkspaceConnection(workspaceId, {
      ...connection,
      id: scopedConnectionId(example, connection.id),
      allowed_project_refs: [example.projectId],
      metadata: {
        showcase: true,
        credential_policy: 'Reference only. Credentials are not exported in packages.',
      },
    })
  }
}

async function seedDiscoveryRecords(example: ExampleConfig, serviceDefinition: Record<string, any>) {
  const mappings = serviceDefinition.integration_fronting?.capability_mappings
  if (!Array.isArray(mappings)) return

  for (const rawMapping of mappings as Record<string, any>[]) {
    const mapping = remapMappingConnectionRefs(example, rawMapping)
    const bindings = Array.isArray(mapping.backend_bindings) ? mapping.backend_bindings : []
    for (const binding of bindings as Record<string, any>[]) {
      const operationRefs = Array.isArray(binding.raw_operation_refs) ? binding.raw_operation_refs : []
      const matchedIds = Array.isArray(binding.matched_discovery_record_ids) ? binding.matched_discovery_record_ids : []
      for (let index = 0; index < operationRefs.length; index += 1) {
        const operationRef = String(operationRefs[index] ?? '').trim()
        if (!operationRef) continue
        const recordId = String(matchedIds[index] ?? matchedIds[0] ?? operationRef.replace(/[^a-z0-9]+/gi, '-')).trim()
        await createIntegrationDiscoveryRecord(example.projectId, {
          id: scopedDiscoveryId(example, recordId),
          connection_id: String(binding.connection_ref ?? ''),
          operation_id: operationRef,
          backend_kind: String(binding.backend_kind ?? 'native_api') as IntegrationBackendKind,
          method: operationRef.includes('.mcp.') || operationRef.includes('mcp.') ? 'tool' : 'POST',
          path_template: String(mapping.path_template ?? `/${example.domain}/${operationRef.split('.').pop() ?? 'operation'}`),
          side_effect_level: sideEffectForOperation(operationRef, mappings),
          input_schema_summary: {
            required: Array.isArray(binding.explicit_required_backend_inputs)
              ? binding.explicit_required_backend_inputs
              : inputNames(mapping, 'required'),
            optional: Array.isArray(binding.explicit_optional_backend_inputs)
              ? binding.explicit_optional_backend_inputs
              : inputNames(mapping, 'optional'),
          },
          risk_notes: [
            String(binding.status_detail ?? 'Backend supply for a governed ANIP fronting capability.'),
          ],
          data: {
            capability_id: mapping.capability_id,
            status: binding.status ?? 'candidate',
            backend_input_mode: binding.backend_input_mode ?? 'explicit',
          },
        })
      }
    }
  }
}

async function seedMappings(example: ExampleConfig, serviceDefinition: Record<string, any>) {
  const mappings = serviceDefinition.integration_fronting?.capability_mappings
  if (!Array.isArray(mappings)) return
  for (const rawMapping of mappings as Record<string, any>[]) {
    const mapping = remapMappingConnectionRefs(example, rawMapping)
    const capabilityId = String(mapping.capability_id ?? '').trim()
    if (!capabilityId) continue
    await createPmArtifact(example.projectId, {
      id: `${example.projectId}-fronting-${capabilityId.replace(/[^a-z0-9]+/gi, '-')}`,
      title: `${mapping.title ?? capabilityId} Fronting Mapping`,
      data: {
        artifact_type: INTEGRATION_FRONTING_MAPPING_ARTIFACT_TYPE,
        ...mapping,
      },
    })
  }
}

function readinessReviewForFinding(
  finding: AgentConsumptionReadinessFinding,
  reviewedAt: string,
): AgentConsumptionReadinessFindingReview {
  if (finding.category === 'app_glue' || finding.category === 'composition_candidate' || finding.owner === 'agent_app_glue') {
    return {
      id: finding.id,
      decision: 'explicit_app_glue',
      note: 'Fronting showcase review classified this as consuming-app orchestration or presentation guidance. The ANIP contract remains the governed service boundary; the app profile owns request framing, routing, or multi-step coordination.',
      reviewed_at: reviewedAt,
      review_method: 'manual',
    }
  }
  if (finding.severity === 'blocker') {
    return {
      id: finding.id,
      decision: 'follow_up',
      note: 'Fronting showcase batch left this blocker as follow-up because blocker-level behavior requires project-specific review.',
      reviewed_at: reviewedAt,
      review_method: 'manual',
    }
  }
  return {
    id: finding.id,
    decision: 'acceptable_warning',
    note: 'Fronting showcase review accepted this as covered by the generated governed fronting contract and app handoff guidance.',
    reviewed_at: reviewedAt,
    review_method: 'manual',
  }
}

function capabilityNeedsAppReview(
  capability: DeveloperCapabilityFormalization,
  readinessReviews: Record<string, AgentConsumptionReadinessFindingReview>,
): boolean {
  if (capability.implementation_fit?.category === 'agent_app_glue') return true
  return Object.values(readinessReviews).some((review) =>
    review.id.startsWith(`${capability.capability_id}:`),
  )
}

function buildConsumabilityReviews(
  definition: DeveloperDefinitionData,
  readinessReviews: Record<string, AgentConsumptionReadinessFindingReview>,
  reviewedAt: string,
): Record<string, AgentConsumabilityCapabilityReview> {
  const reviews: Record<string, AgentConsumabilityCapabilityReview> = {}
  for (const capability of definition.capability_formalizations ?? []) {
    if (!capability.capability_id || !capabilityNeedsAppReview(capability, readinessReviews)) continue
    const findingReviewsForCapability = Object.values(readinessReviews).filter((review) =>
      review.id.startsWith(`${capability.capability_id}:`),
    )
    const appGlueRequired = capability.implementation_fit?.category === 'agent_app_glue'
      || findingReviewsForCapability.some((review) => review.decision === 'explicit_app_glue')
    reviews[capability.capability_id] = {
      capability_id: capability.capability_id,
      reviewed_at: reviewedAt,
      intent_category: capability.capability_id.replace(/[_-]+/g, '.'),
      intent_summary: capability.summary || capability.title || capability.capability_id,
      app_glue_required: appGlueRequired,
      app_glue_reason: appGlueRequired
        ? 'The consuming app owns package-specific request framing, result display, and multi-step orchestration around this governed ANIP capability; raw backend invocation remains hidden behind the service boundary.'
        : undefined,
      intent_rules: [
        {
          id: 'fronting-app-boundary',
          meaning: appGlueRequired
            ? 'The app may coordinate UX flow, clarification copy, and multi-step request routing.'
            : 'Reviewed capability semantics are sufficient for agent consumption; no extra app-owned behavior is required by this finding.',
          owner: 'agent_app_glue',
          agent_action: appGlueRequired
            ? 'Use the reviewed ANIP capability surface and do not expose raw API/MCP operations directly.'
            : 'Invoke the reviewed ANIP capability surface normally.',
        },
      ],
      app_boundaries: {
        guidance: 'Show governed ANIP capabilities as the supported surface; refuse or explain raw backend bypass, direct mutation, export, or send requests that exceed declared effects.',
      },
    }
  }
  return reviews
}

async function saveBaselineAndDefinition(example: ExampleConfig, serviceDefinition: Record<string, any>) {
  let state = await loadState(example.projectId)
  const requirements = state.requirements[0] ?? null
  const baseline = buildDeveloperBaseline({
    requirements,
    scenarios: state.scenarios,
    primaryScenarioId: state.scenarios[0]?.id,
    shape: null,
    pmArtifacts: state.pmArtifacts,
  })
  await createPmArtifact(example.projectId, {
    id: developerBaselineArtifactId(example.projectId),
    title: 'Developer Baseline',
    data: {
      ...baseline,
      note: 'Studio batch accepted the governed integration-fronting source docs, connection refs, and curated capability mappings.',
    },
  })

  state = await loadState(example.projectId)
  const baselineArtifact = state.pmArtifacts.find((artifact) => artifact.id === developerBaselineArtifactId(example.projectId))
  const definition = buildDeveloperDefinitionData({
    project: state.project,
    baseline: baselineArtifact?.data as any,
    requirements: state.requirements[0] ?? null,
    scenarios: state.scenarios,
    shape: null,
    pmArtifacts: state.pmArtifacts,
  })

  definition.identity.system_name = String(serviceDefinition.identity?.system_name ?? definition.identity.system_name)
  definition.identity.domain_name = String(serviceDefinition.identity?.domain_name ?? definition.identity.domain_name)
  definition.identity.delivery_model = 'governed_integration_fronting' as any
  definition.identity.architecture_shape = 'single_service' as any
  definition.product_alignment.governed_behavior_formalization = 'Curated ANIP capabilities sit in front of selected raw API/MCP operations; agents do not receive direct unbounded backend tool access.'
  definition.product_alignment.approval_posture_formalization = 'Read operations are bounded and audited. Write-adjacent operations stop at preview or require ANIP approval grants before downstream mutation.'
  definition.generation.codegen_adapter = 'python_fastapi'
  definition.generation.layout_strategy = 'monorepo'
  definition.generation.scalability_profile = 'stateless_horizontal'
  definition.generation.protocols = ['http_json']
  definition.generation.selected_service_ids = Array.from(new Set(
    (serviceDefinition.service_topology_bindings ?? [])
      .map((service: Record<string, any>) => String(service.service_id ?? '').trim())
      .filter(Boolean),
  ))
  definition.naming.namespace = example.domain
  definition.naming.package_prefix = example.key
  definition.naming.service_name_prefix = example.key
  definition.rationale = 'Studio batch generated this governed integration-fronting project from reviewed source docs and curated backend mappings.'

  const validationIssues = validateDeveloperDefinitionRequiredFields(definition)
  if (validationIssues.length > 0) {
    throw new Error(`${example.key} Developer Definition has ${validationIssues.length} missing fields: ${validationIssues.slice(0, 10).map((issue) => issue.message).join(' ')}`)
  }

  const reviewedAt = new Date().toISOString()
  const readiness = analyzeAgentConsumptionReadiness(definition)
  const readinessReviews = Object.fromEntries(
    readiness.findings.map((finding) => [finding.id, readinessReviewForFinding(finding, reviewedAt)]),
  )
  const blockerFollowUps = Object.values(readinessReviews).filter((review) => review.decision === 'follow_up')
  if (blockerFollowUps.length > 0) {
    throw new Error(`${example.key} has ${blockerFollowUps.length} blocker readiness finding(s) that require manual review: ${blockerFollowUps.map((review) => review.id).join(', ')}`)
  }
  const reviewedReadiness = applyReadinessFindingReviews(readiness, readinessReviews)
  const consumabilityReviews = buildConsumabilityReviews(definition, readinessReviews, reviewedAt)

  const baseContract = buildDeveloperDefinitionContract({
    project: state.project,
    baseline: baselineArtifact?.data as any,
    requirements: state.requirements[0] ?? null,
    scenarios: state.scenarios,
    shape: null,
    traceability: null,
    developerDefinition: definition,
  })
  const canonicalJson = stableStringify(contractIdentityPayload(baseContract))
  const savedAt = new Date().toISOString()
  const identity: DeveloperCompiledContractIdentity = {
    artifact_name: `${example.projectId}-developer-definition.json`,
    canonical_format: 'stable-json-v1',
    signature_algorithm: 'sha256',
    signature: sha256Hex(canonicalJson),
    generated_at: savedAt,
  }
  const savedRevision = {
    revision_number: 1,
    revision_artifact_id: developerDefinitionRevisionArtifactId(example.projectId, 1),
    previous_revision_artifact_id: null,
    saved_at: savedAt,
  }
  const payload: DeveloperDefinitionData = {
    ...definition,
    compiled_contract_identity: identity,
    saved_revision: savedRevision,
    saved_at: savedAt,
  }
  const revisionPayload: DeveloperDefinitionRevisionData = {
    ...payload,
    artifact_type: 'developer_definition_revision',
    saved_revision: savedRevision,
  }

  await createPmArtifact(example.projectId, {
    id: savedRevision.revision_artifact_id,
    title: 'Developer Definition Revision 1',
    data: revisionPayload,
  })
  await createPmArtifact(example.projectId, {
    id: developerDefinitionArtifactId(example.projectId),
    title: 'Developer Definition',
    data: payload,
  })

  state = await loadState(example.projectId)
  const traceability = buildTraceabilityRecord({
    pmArtifacts: state.pmArtifacts,
    requirements: state.requirements[0] ?? null,
    scenarios: state.scenarios,
    shape: null,
    baselineLockedAt: baseline.locked_at,
    existing: null,
  })
  const highRisk = buildHighRiskConfirmationReport({
    project: state.project,
    pmArtifacts: state.pmArtifacts,
    documents: state.documents,
    requirements: state.requirements,
    scenarios: state.scenarios,
    shapes: state.shapes,
    existing: null,
  })
  const reviewedHighRisk = {
    ...highRisk,
    summary: {
      ...highRisk.summary,
      unresolved: 0,
      blockers: 0,
      warnings: 0,
      confirmed: highRisk.items.length,
      deferred: 0,
    },
    reviews: Object.fromEntries(highRisk.items.map((item) => [
      item.id,
      {
        id: item.id,
        status: 'confirmed',
        note: 'Fronting showcase batch confirmed the reviewed canonical capability IDs and service ownership for this generated example.',
        reviewed_at: reviewedAt,
      },
    ])),
  }
  await createPmArtifact(example.projectId, {
    id: traceabilityArtifactId(example.projectId),
    title: 'Traceability Record',
    data: {
      ...traceability,
      high_risk_confirmations: reviewedHighRisk,
      developer_status: 'ready_for_pm_review',
      developer_note: 'Studio batch saved the governed-fronting mapping and Developer Definition revision.',
      developer_marked_at: savedAt,
      agent_consumption_readiness: JSON.parse(JSON.stringify(reviewedReadiness)),
      agent_consumability_reviews: consumabilityReviews,
    } satisfies TraceabilityRecordData as Record<string, any>,
  })
}

async function createProjectFromExample(example: ExampleConfig) {
  log(`Creating ${example.key} project ${example.projectId}`)
  const serviceDefinition = normalizeFrontingStarterDefinition(example, await readJson(serviceDefinitionPath(example)))
  await createProject({
    id: example.projectId,
    workspace_id: workspaceId,
    name: example.name,
    summary: example.summary,
    domain: example.domain,
    labels: ['fronting', 'showcase', example.key],
    project_type: 'governed_service_project',
    integration_profile: { kind: 'none', systems: [] },
  })
  await createSourceDoc(example)
  await seedConnections(example)
  await seedDiscoveryRecords(example, serviceDefinition)
  await saveProductDesignArtifacts(example, serviceDefinition)
  await createRequirements(example.projectId, {
    id: `${example.projectId}-requirements`,
    title: `${example.name} Requirements`,
    data: requirementData(example, serviceDefinition),
  })
  await createScenario(example.projectId, {
    id: `${example.projectId}-scenario-governed-fronting`,
    title: `${example.name} Governed Fronting Scenario`,
    data: scenarioData(example, serviceDefinition),
  })
  await seedMappings(example, serviceDefinition)
  await saveBaselineAndDefinition(example, serviceDefinition)
}

async function main() {
  log(`Creating workspace ${workspaceId}`)
  const selectedExamples = selectedExampleKeys.size
    ? examples.filter((example) => selectedExampleKeys.has(example.key))
    : examples
  if (selectedExamples.length === 0) {
    throw new Error(`No fronting examples matched FRONTING_BATCH_EXAMPLES=${[...selectedExampleKeys].join(',')}`)
  }
  await ensureWorkspace({
    id: workspaceId,
    name: stableIds ? 'ANIP Showcase Projects' : `Governed Fronting Showcase ${nowStamp}`,
    summary: stableIds
      ? `Public read-only showcase projects for the GTM Agent and ${selectedExamples.map((example) => example.name).join(', ')} governed-fronting examples.`
      : `Studio-created ${selectedExamples.map((example) => example.name).join(', ')} governed-fronting projects.`,
  })
  for (const example of selectedExamples) {
    await createProjectFromExample(example)
  }
  log('Created Studio projects:')
  for (const example of selectedExamples) {
    log(`- ${example.name}: ${webBase}/design/projects/${example.projectId}/developer/integration-fronting`)
  }
}

main().catch((err) => {
  console.error(err)
  process.exitCode = 1
})
