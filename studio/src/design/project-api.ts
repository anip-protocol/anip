import type {
  WorkspaceSummary,
  WorkspaceDetail,
  ProjectSummary,
  ProjectDetail,
  ProjectDocumentRecord,
  ArtifactRecord,
  RequirementsRecord,
  ProposalRecord,
  ShapeRecord,
  EvaluationRecord,
  VocabularyEntry,
  CreateProject,
  ImportResult,
  AssistantExplanation,
  AssistantProposal,
  AssistantProposalEnvelope,
  IntentInterpretation,
  BusinessPacket,
  DriftAnalysis,
  GlueAnalysis,
  RuntimeStatus,
  AssistantRuntimeConfig,
  StudioSettings,
  AssistantServiceTopologyPreference,
  IntegrationDiscoveryRecord,
  WorkspaceConnection,
} from './project-types'
import type {
  AgentConsumptionSimulationModelOutput,
  AgentConsumptionSimulationRequest,
} from './agent-consumption-simulator'
import type { StarterTemplatePackage } from './starter-template-package'
import type { ServiceMetadataComparison } from './types'
import type { DerivedExpectation } from './shape-types'
import type {
  DataAccessProjectState,
  SavedDataAccessProjectRecord,
  SavedDataAccessProjectSummary,
} from '../data-access/types'
import type {
  ApplicationIntegrationProjectState,
  SavedApplicationIntegrationProjectRecord,
  SavedApplicationIntegrationProjectSummary,
} from '../application-integration/types'
import { issueCapabilityToken, invokeCapability } from '../api'

// ---------------------------------------------------------------------------
// Core fetch wrapper
// ---------------------------------------------------------------------------

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options?.headers ?? {}),
    },
  })

  if (resp.status === 204) {
    return undefined as T
  }

  if (!resp.ok) {
    const text = await resp.text().catch(() => resp.statusText)
    throw new Error(`API ${options?.method ?? 'GET'} ${path} failed (${resp.status}): ${text}`)
  }

  return resp.json() as Promise<T>
}

export interface RegistryRevisionLineage {
  project_ref: string
  product_revision: {
    ref: string
    artifact_id: string | null
    revision_number: number | null
    baseline_locked_at?: string | null
  }
  developer_revision: {
    ref: string
    artifact_id: string | null
    revision_number: number | null
    contract_signature: string
  }
}

export interface RegistryPublishRequest {
  package_id: string
  package_version: string
  project_ref: string
  product_revision_ref: string
  developer_revision_ref: string
  contract_signature: string
  lineage?: RegistryRevisionLineage
  schema_version?: string
  manifest: Record<string, any>
  service_definition: Record<string, any>
  recommended_lock: Record<string, any>
  readme?: string
  source_links?: Array<{ title: string; url: string }>
  implementation_materials?: Array<{ title?: string; ref: string; bundle_tree_sha256?: string }>
}

export interface RegistryPublicationSummary {
  package_id: string
  package_version: string
  project_ref: string
  product_revision_ref: string
  developer_revision_ref: string
  contract_signature: string
  publisher_id?: string
  publisher_type?: string
  lineage?: RegistryRevisionLineage
  published_at: string
}

export interface RegistryPackageRecord {
  package_id: string
  package_version: string
  project_ref: string
  product_revision_ref: string
  developer_revision_ref: string
  contract_signature: string
  publisher_id?: string
  publisher_type?: string
  lineage?: RegistryRevisionLineage
  schema_version: string
  manifest_digest: string
  definition_digest: string
  lock_digest?: string
  published_at: string
  manifest: Record<string, any>
  service_definition: Record<string, any>
  recommended_lock: Record<string, any>
  readme?: string
  source_links?: Array<{ title: string; url: string }>
  implementation_materials?: Array<{ title?: string; ref: string; bundle_tree_sha256?: string }>
}

export interface RegistryReceipt {
  receipt_id: string
  package_id: string
  package_version: string
  registry_signature: string
  signature_algorithm?: string
  key_id?: string
  publisher_id?: string
  publisher_type?: string
  issued_at: string
}

export interface RegistryPublishResult {
  publication: RegistryPublicationSummary
  package: RegistryPackageRecord
  receipt: RegistryReceipt
}

export function publishRegistryPackage(payload: RegistryPublishRequest): Promise<RegistryPublishResult> {
  return api<RegistryPublishResult>('/api/registry/publications', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export interface RegistryTemplatePublishRequest {
  template_id: string
  template_version: string
  manifest: Record<string, any>
  template: Record<string, any>
  package?: Record<string, any>
}

export interface RegistryTemplateRecord {
  template_id: string
  template_version: string
  template_kind: string
  project_type: string
  anip_spec_version: string
  domain?: string
  industry?: string
  systems?: string[]
  published_at: string
  download_count?: number
  manifest_digest: string
  template_digest: string
  package_digest: string
  manifest: Record<string, any>
  template: Record<string, any>
  package: Record<string, any>
}

export interface RegistryTemplateSummary {
  template_id: string
  template_version: string
  template_kind: string
  project_type: string
  anip_spec_version: string
  domain?: string
  industry?: string
  systems?: string[]
  publisher_id?: string
  publisher_type?: string
  published_at: string
  download_count?: number
  manifest: Record<string, any>
}

export interface RegistryTemplatePublishResult {
  template: RegistryTemplateRecord
}

export interface RegistryTemplateListResult {
  items: RegistryTemplateSummary[]
  warning?: string
}

export function publishRegistryTemplate(payload: RegistryTemplatePublishRequest): Promise<RegistryTemplatePublishResult> {
  return api<RegistryTemplatePublishResult>('/api/registry/templates', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function listRegistryTemplates(): Promise<RegistryTemplateListResult> {
  return api<RegistryTemplateListResult>('/api/registry/templates')
}

export function getRegistryTemplate(templateId: string, templateVersion: string): Promise<RegistryTemplateRecord> {
  return api<RegistryTemplateRecord>(
    `/api/registry/templates/${encodeURIComponent(templateId)}/${encodeURIComponent(templateVersion)}`,
  )
}

export function downloadRegistryTemplatePackage(templateId: string, templateVersion: string): Promise<StarterTemplatePackage> {
  return api<StarterTemplatePackage>(
    `/api/registry/templates/${encodeURIComponent(templateId)}/${encodeURIComponent(templateVersion)}/download`,
  )
}

export interface LocalPublicationRecord extends RegistryPublishResult {
  id: string
  project_id: string
  authority: 'local-studio'
  created_at: string
}

export interface LocalPublicationVerificationCheck {
  name: string
  status: 'pass' | 'fail'
  detail: string
}

export interface LocalPublicationVerificationResult {
  status: 'ok' | 'failed'
  receipt_status: 'verified' | 'failed' | 'present' | 'none' | string
  authority: 'local-studio' | string
  package_id: string
  package_version: string
  lineage?: RegistryRevisionLineage | null
  product_revision?: RegistryRevisionLineage['product_revision'] | null
  developer_revision?: RegistryRevisionLineage['developer_revision'] | null
  definition_digest: string
  manifest_digest: string
  receipt_signature: string
  computed_receipt_signature: string
  checks: LocalPublicationVerificationCheck[]
}

export function publishLocalRegistryPackage(projectId: string, payload: RegistryPublishRequest): Promise<LocalPublicationRecord> {
  return api<LocalPublicationRecord>(`/api/projects/${projectId}/local-publications`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function getLocalRegistryPackage(projectId: string, publicationId: string): Promise<LocalPublicationRecord> {
  return api<LocalPublicationRecord>(`/api/projects/${projectId}/local-publications/${publicationId}`)
}

export function listLocalRegistryPackages(projectId: string): Promise<{ items: LocalPublicationRecord[] }> {
  return api<{ items: LocalPublicationRecord[] }>(`/api/projects/${projectId}/local-publications`)
}

export function getLocalRegistryPackageBundleUrl(projectId: string, publicationId: string): string {
  return `/api/projects/${projectId}/local-publications/${publicationId}/bundle`
}

export function verifyLocalRegistryPackage(projectId: string, publicationId: string): Promise<LocalPublicationVerificationResult> {
  return api<LocalPublicationVerificationResult>(`/api/projects/${projectId}/local-publications/${publicationId}/verify`, {
    method: 'POST',
  })
}

export interface GoLocalPublicationVerificationResult {
  artifact: ArtifactRecord
  raw_result: Record<string, any>
  summary: {
    status: 'aligned' | 'mismatch' | 'incomplete' | 'unpublished' | string
    label: string
    detail: string
    sourceTool: 'anip-verify' | string
    packageLabel: string
    receiptStatus: string
    receiptSignature: string
    registrySigningMode?: string | null
    registryActiveKeyID?: string | null
    registryTrustPostureLabel?: string | null
    registryTrustPostureDetail?: string | null
    productRevisionLabel: string
    developerRevisionLabel: string
    matchedPublicationArtifactId: string | null
  }
}

export function verifyLocalRegistryPackageWithGo(projectId: string, publicationId: string): Promise<GoLocalPublicationVerificationResult> {
  return api<GoLocalPublicationVerificationResult>(`/api/projects/${projectId}/local-publications/${publicationId}/verify/go`, {
    method: 'POST',
  })
}

export interface GoRegistryPublicationVerificationRequest {
  package_id: string
  package_version: string
  registry_url?: string
  publication_artifact_id?: string
}

export interface GoRegistryPublicationVerificationResult extends GoLocalPublicationVerificationResult {
  registry_url: string
}

export function verifyRegistryPackageWithGo(
  projectId: string,
  payload: GoRegistryPublicationVerificationRequest,
): Promise<GoRegistryPublicationVerificationResult> {
  return api<GoRegistryPublicationVerificationResult>(`/api/projects/${projectId}/registry-verification/verify/go`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function runAgentConsumptionSimulator(
  payload: AgentConsumptionSimulationRequest,
): Promise<AgentConsumptionSimulationModelOutput> {
  return api<AgentConsumptionSimulationModelOutput>('/api/agent-consumption-simulator/run', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

const STUDIO_ASSISTANT_BASE_URL = '/studio-assistant'
const STUDIO_ASSISTANT_BOOTSTRAP = 'studio-assistant-bootstrap'
const STUDIO_ASSISTANT_SCOPE_BY_CAPABILITY: Record<string, string> = {
  explain_shape: 'studio.assistant.explain_shape',
  explain_evaluation: 'studio.assistant.explain_evaluation',
  interpret_project_intent: 'studio.assistant.interpret_project_intent',
  propose_requirements: 'studio.assistant.propose_requirements',
  propose_scenarios: 'studio.assistant.propose_scenarios',
  propose_business_summary: 'studio.assistant.propose_business_summary',
  propose_actor_model: 'studio.assistant.propose_actor_model',
  propose_business_areas: 'studio.assistant.propose_business_areas',
  propose_permission_intent: 'studio.assistant.propose_permission_intent',
  propose_non_goals: 'studio.assistant.propose_non_goals',
  propose_success_criteria: 'studio.assistant.propose_success_criteria',
  propose_service_design: 'studio.assistant.propose_service_design',
  propose_capability_formalization: 'studio.assistant.propose_capability_formalization',
  propose_runtime_policy_bindings: 'studio.assistant.propose_runtime_policy_bindings',
  propose_input_contracts: 'studio.assistant.propose_input_contracts',
  propose_verification_expectations: 'studio.assistant.propose_verification_expectations',
  propose_backend_bindings: 'studio.assistant.propose_backend_bindings',
  propose_governed_fronting_capabilities: 'studio.assistant.propose_governed_fronting_capabilities',
  identify_missing_business_info: 'studio.assistant.identify_missing_business_info',
  clarify_design_section: 'studio.assistant.clarify_design_section',
  suggest_next_step: 'studio.assistant.suggest_next_step',
  analyze_agent_consumption_simulation: 'studio.assistant.analyze_agent_consumption_simulation',
}
const STUDIO_WORKBENCH_BASE_URL = '/studio-workbench'
const STUDIO_WORKBENCH_BOOTSTRAP = 'studio-workbench-bootstrap'
const STUDIO_WORKBENCH_SCOPE_BY_CAPABILITY: Record<string, string> = {
  accept_first_design: 'studio.workbench.accept_first_design',
  generate_business_brief: 'studio.workbench.generate_business_brief',
  generate_engineering_contract: 'studio.workbench.generate_engineering_contract',
  generate_business_packet: 'studio.workbench.generate_business_packet',
  generate_drift_analysis: 'studio.workbench.generate_drift_analysis',
  generate_glue_analysis: 'studio.workbench.generate_glue_analysis',
}

const assistantTokens: Record<string, string | undefined> = {}
const workbenchTokens: Record<string, string | undefined> = {}

async function ensureAssistantToken(capability: string, forceRefresh = false): Promise<string> {
  if (assistantTokens[capability] && !forceRefresh) return assistantTokens[capability] as string
  const scope = STUDIO_ASSISTANT_SCOPE_BY_CAPABILITY[capability]
  if (!scope) {
    throw new Error(`Unsupported Studio assistant capability: ${capability}`)
  }
  const issued = await issueCapabilityToken(
    STUDIO_ASSISTANT_BASE_URL,
    STUDIO_ASSISTANT_BOOTSTRAP,
    'studio-ui',
    capability,
    [scope],
    { ttl_hours: 8 },
  )
  if (!issued?.issued || !issued?.token) {
    const detail = issued?.failure?.detail || 'Failed to issue Studio assistant token'
    throw new Error(detail)
  }
  const token = issued.token as string
  assistantTokens[capability] = token
  return token
}

async function invokeAssistant<T>(
  capability: string,
  parameters: Record<string, any>,
  options?: { signal?: AbortSignal },
): Promise<T> {
  let token = await ensureAssistantToken(capability)
  let result = await invokeCapability(STUDIO_ASSISTANT_BASE_URL, token, capability, parameters, {
    signal: options?.signal,
  })

  if (!result?.success && result?.failure?.type === 'invalid_token') {
    token = await ensureAssistantToken(capability, true)
    result = await invokeCapability(STUDIO_ASSISTANT_BASE_URL, token, capability, parameters, {
      signal: options?.signal,
    })
  }

  if (!result?.success) {
    const detail = result?.failure?.detail || `Assistant capability ${capability} failed`
    throw new Error(detail)
  }

  return result.result as T
}

async function ensureWorkbenchToken(capability: string, forceRefresh = false): Promise<string> {
  if (workbenchTokens[capability] && !forceRefresh) return workbenchTokens[capability] as string
  const scope = STUDIO_WORKBENCH_SCOPE_BY_CAPABILITY[capability]
  if (!scope) {
    throw new Error(`Unsupported Studio workbench capability: ${capability}`)
  }
  const issued = await issueCapabilityToken(
    STUDIO_WORKBENCH_BASE_URL,
    STUDIO_WORKBENCH_BOOTSTRAP,
    'studio-ui',
    capability,
    [scope],
    { ttl_hours: 8 },
  )
  if (!issued?.issued || !issued?.token) {
    const detail = issued?.failure?.detail || 'Failed to issue Studio workbench token'
    throw new Error(detail)
  }
  const token = issued.token as string
  workbenchTokens[capability] = token
  return token
}

async function invokeWorkbench<T>(capability: string, parameters: Record<string, any>): Promise<T> {
  let token = await ensureWorkbenchToken(capability)
  let result = await invokeCapability(STUDIO_WORKBENCH_BASE_URL, token, capability, parameters)

  if (!result?.success && result?.failure?.type === 'invalid_token') {
    token = await ensureWorkbenchToken(capability, true)
    result = await invokeCapability(STUDIO_WORKBENCH_BASE_URL, token, capability, parameters)
  }

  if (!result?.success) {
    const detail = result?.failure?.detail || `Workbench capability ${capability} failed`
    throw new Error(detail)
  }

  return result.result as T
}

// ---------------------------------------------------------------------------
// Workspaces
// ---------------------------------------------------------------------------

export function listWorkspaces(): Promise<WorkspaceDetail[]> {
  return api<WorkspaceDetail[]>('/api/workspaces')
}

export function getWorkspace(id: string): Promise<WorkspaceDetail> {
  return api<WorkspaceDetail>(`/api/workspaces/${id}`)
}

export function createWorkspace(payload: { id: string; name: string; summary?: string }): Promise<WorkspaceSummary> {
  return api<WorkspaceSummary>('/api/workspaces', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function cloneWorkspace(
  id: string,
  payload: { id?: string; name: string; summary?: string },
): Promise<WorkspaceDetail> {
  return api<WorkspaceDetail>(`/api/workspaces/${id}/clone`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function deleteWorkspace(id: string): Promise<void> {
  return api<void>(`/api/workspaces/${id}`, { method: 'DELETE' })
}

export function listWorkspaceConnections(workspaceId: string): Promise<WorkspaceConnection[]> {
  return api<WorkspaceConnection[]>(`/api/workspaces/${workspaceId}/connections`)
}

export function createWorkspaceConnection(
  workspaceId: string,
  payload: Omit<WorkspaceConnection, 'workspace_id' | 'created_at' | 'updated_at'>,
): Promise<WorkspaceConnection> {
  return api<WorkspaceConnection>(`/api/workspaces/${workspaceId}/connections`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateWorkspaceConnection(
  workspaceId: string,
  connectionId: string,
  payload: Partial<Omit<WorkspaceConnection, 'id' | 'workspace_id' | 'created_at' | 'updated_at'>>,
): Promise<WorkspaceConnection> {
  return api<WorkspaceConnection>(`/api/workspaces/${workspaceId}/connections/${connectionId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function deleteWorkspaceConnection(workspaceId: string, connectionId: string): Promise<void> {
  return api<void>(`/api/workspaces/${workspaceId}/connections/${connectionId}`, { method: 'DELETE' })
}

// ---------------------------------------------------------------------------
// Projects
// ---------------------------------------------------------------------------

export function listProjects(workspaceId?: string): Promise<ProjectSummary[]> {
  const qs = workspaceId ? `?workspace_id=${encodeURIComponent(workspaceId)}` : ''
  return api<ProjectSummary[]>(`/api/projects${qs}`)
}

export function getProject(id: string): Promise<ProjectDetail> {
  return api<ProjectDetail>(`/api/projects/${id}`)
}

export function getRuntimeStatus(): Promise<RuntimeStatus> {
  return api<RuntimeStatus>('/api/runtime-status')
}

export function getRuntimeConfig(): Promise<AssistantRuntimeConfig> {
  return api<AssistantRuntimeConfig>('/api/runtime-config')
}

export async function getStudioSettings(): Promise<StudioSettings> {
  try {
    return await api<StudioSettings>('/api/settings')
  } catch (err) {
    if (err instanceof Error && err.message.includes('/api/settings failed (404)')) {
      return {
        assistant: await getRuntimeConfig(),
        simulator: compatibilitySimulatorRuntimeConfig(),
        registry: compatibilityRegistryTrustPolicy(),
      }
    }
    throw err
  }
}

export function updateStudioSettings(
  payload: Partial<{
    assistant: Parameters<typeof updateRuntimeConfig>[0]
    simulator: Partial<{
      simulator_provider: string | null
      simulator_model: string | null
      simulator_base_url: string | null
      simulator_api_key: string | null
      clear_simulator_api_key: boolean
      temperature: number
      timeout_seconds: number
    }>
    registry: Partial<{
      registry_url: string | null
      required_registry_mode: string | null
      trusted_registry_key_id: string | null
      registry_publish_token: string | null
      clear_registry_publish_token: boolean
    }>
  }>,
): Promise<StudioSettings> {
  return api<StudioSettings>('/api/settings', {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

function compatibilitySimulatorRuntimeConfig(): StudioSettings['simulator'] {
  return {
    simulator_provider: 'openai',
    simulator_model: 'gpt-5.4-mini',
    simulator_base_url: null,
    temperature: 0,
    timeout_seconds: 60,
    api_key_configured: false,
    stored_api_key_configured: false,
    provider_source: 'default',
    model_source: 'default',
    base_url_source: 'default',
    api_key_source: 'none',
    temperature_source: 'default',
    timeout_seconds_source: 'default',
    read_only_mode: false,
    read_only_reason: null,
  }
}

function compatibilityRegistryTrustPolicy(): StudioSettings['registry'] {
  return {
    registry_url: 'http://127.0.0.1:8200',
    registry_url_source: 'compatibility-default',
    required_registry_mode: null,
    required_registry_mode_source: 'compatibility-default',
    trusted_registry_key_id: null,
    trusted_registry_key_id_source: 'compatibility-default',
    publish_token_configured: false,
    publish_token_source: 'none',
    production_mode_detected: false,
    allows_development_registry: true,
    key_pinned: false,
    warning: 'The Studio backend does not expose /api/settings yet. Restart or update the backend to show the active Registry trust policy.',
  }
}

export function updateRuntimeConfig(
  payload: Partial<{
    assistant_provider: string | null
    assistant_model: string | null
    assistant_base_url: string | null
    assistant_api_key: string | null
    clear_assistant_api_key: boolean
    temperature: number
    timeout_seconds: number
    strict: boolean
  }>,
): Promise<AssistantRuntimeConfig> {
  return api<AssistantRuntimeConfig>('/api/runtime-config', {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function createProject(payload: CreateProject): Promise<ProjectSummary> {
  return api<ProjectSummary>('/api/projects', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function cloneProject(
  id: string,
  payload: { id?: string; workspace_id?: string; name: string; summary?: string },
): Promise<ProjectSummary> {
  return api<ProjectSummary>(`/api/projects/${id}/clone`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateProject(
  id: string,
  payload: Partial<Pick<ProjectSummary, 'name' | 'summary' | 'domain' | 'labels' | 'project_type' | 'integration_profile'>>,
): Promise<ProjectSummary> {
  return api<ProjectSummary>(`/api/projects/${id}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function deleteProject(id: string): Promise<void> {
  return api<void>(`/api/projects/${id}`, { method: 'DELETE' })
}

export function listIntegrationDiscoveryRecords(projectId: string): Promise<IntegrationDiscoveryRecord[]> {
  return api<IntegrationDiscoveryRecord[]>(`/api/projects/${projectId}/integration-discovery-records`)
}

export function createIntegrationDiscoveryRecord(
  projectId: string,
  payload: Omit<IntegrationDiscoveryRecord, 'project_id' | 'content_hash' | 'created_at' | 'updated_at'>,
): Promise<IntegrationDiscoveryRecord> {
  return api<IntegrationDiscoveryRecord>(`/api/projects/${projectId}/integration-discovery-records`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateIntegrationDiscoveryRecord(
  projectId: string,
  recordId: string,
  payload: Partial<Omit<IntegrationDiscoveryRecord, 'id' | 'project_id' | 'content_hash' | 'created_at' | 'updated_at'>>,
): Promise<IntegrationDiscoveryRecord> {
  return api<IntegrationDiscoveryRecord>(`/api/projects/${projectId}/integration-discovery-records/${recordId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function deleteIntegrationDiscoveryRecord(projectId: string, recordId: string): Promise<void> {
  return api<void>(`/api/projects/${projectId}/integration-discovery-records/${recordId}`, { method: 'DELETE' })
}

export function listProjectDocuments(projectId: string): Promise<ProjectDocumentRecord[]> {
  return api<ProjectDocumentRecord[]>(`/api/projects/${projectId}/documents`)
}

export function listPmArtifacts(projectId: string): Promise<ArtifactRecord[]> {
  return api<ArtifactRecord[]>(`/api/projects/${projectId}/pm-artifacts`)
}

export function createPmArtifact(
  projectId: string,
  payload: { id: string; title: string; data: Record<string, any> },
): Promise<ArtifactRecord> {
  return api<ArtifactRecord>(`/api/projects/${projectId}/pm-artifacts`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updatePmArtifact(
  projectId: string,
  artifactId: string,
  payload: Partial<{ title: string; status: string; data: Record<string, any> }>,
): Promise<ArtifactRecord> {
  return api<ArtifactRecord>(`/api/projects/${projectId}/pm-artifacts/${artifactId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function deletePmArtifact(projectId: string, artifactId: string): Promise<void> {
  return api<void>(`/api/projects/${projectId}/pm-artifacts/${artifactId}`, {
    method: 'DELETE',
  })
}

export function appendProjectAssistantAuditEvent(
  projectId: string,
  payload: Record<string, any>,
): Promise<ArtifactRecord> {
  return api<ArtifactRecord>(`/api/projects/${projectId}/assistant/audit-events`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function createProjectDocument(
  projectId: string,
  payload: {
    id: string
    title: string
    kind: string
    filename: string
    media_type: string
    source_path?: string
    content_base64: string
  },
): Promise<ProjectDocumentRecord> {
  return api<ProjectDocumentRecord>(`/api/projects/${projectId}/documents`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function deleteProjectDocument(projectId: string, documentId: string): Promise<void> {
  return api<void>(`/api/projects/${projectId}/documents/${documentId}`, {
    method: 'DELETE',
  })
}

export function getProjectDocumentPreview(
  projectId: string,
  documentId: string,
): Promise<{ content: string }> {
  return api<{ content: string }>(`/api/projects/${projectId}/documents/${documentId}/preview`)
}

export function getProjectDocumentDownloadUrl(projectId: string, documentId: string): string {
  return `/api/projects/${projectId}/documents/${documentId}/download`
}

// ---------------------------------------------------------------------------
// Requirements
// ---------------------------------------------------------------------------

export function listRequirements(projectId: string): Promise<RequirementsRecord[]> {
  return api<RequirementsRecord[]>(`/api/projects/${projectId}/requirements`)
}

export function getRequirements(projectId: string, id: string): Promise<RequirementsRecord> {
  return api<RequirementsRecord>(`/api/projects/${projectId}/requirements/${id}`)
}

export function createRequirements(
  projectId: string,
  payload: { id: string; title: string; data: Record<string, any> },
): Promise<RequirementsRecord> {
  return api<RequirementsRecord>(`/api/projects/${projectId}/requirements`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateRequirements(
  projectId: string,
  id: string,
  payload: Partial<{ title: string; status: string; data: Record<string, any> }>,
): Promise<RequirementsRecord> {
  return api<RequirementsRecord>(`/api/projects/${projectId}/requirements/${id}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function deleteRequirements(projectId: string, id: string): Promise<void> {
  return api<void>(`/api/projects/${projectId}/requirements/${id}`, { method: 'DELETE' })
}

export function setRequirementsRole(
  pid: string,
  rid: string,
  role: 'primary' | 'alternative',
): Promise<RequirementsRecord> {
  return api<RequirementsRecord>(`/api/projects/${pid}/requirements/${rid}/role`, {
    method: 'PUT',
    body: JSON.stringify({ role }),
  })
}

// ---------------------------------------------------------------------------
// Scenarios
// ---------------------------------------------------------------------------

export function listScenarios(projectId: string): Promise<ArtifactRecord[]> {
  return api<ArtifactRecord[]>(`/api/projects/${projectId}/scenarios`)
}

export function getScenario(projectId: string, id: string): Promise<ArtifactRecord> {
  return api<ArtifactRecord>(`/api/projects/${projectId}/scenarios/${id}`)
}

export function createScenario(
  projectId: string,
  payload: { id: string; title: string; data: Record<string, any> },
): Promise<ArtifactRecord> {
  return api<ArtifactRecord>(`/api/projects/${projectId}/scenarios`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateScenario(
  projectId: string,
  id: string,
  payload: Partial<{ title: string; status: string; data: Record<string, any> }>,
): Promise<ArtifactRecord> {
  return api<ArtifactRecord>(`/api/projects/${projectId}/scenarios/${id}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function deleteScenario(projectId: string, id: string): Promise<void> {
  return api<void>(`/api/projects/${projectId}/scenarios/${id}`, { method: 'DELETE' })
}

// ---------------------------------------------------------------------------
// Observed Service Metadata
// ---------------------------------------------------------------------------

export function listServiceMetadata(projectId: string): Promise<ArtifactRecord[]> {
  return api<ArtifactRecord[]>(`/api/projects/${projectId}/service-metadata`)
}

export function getServiceMetadata(projectId: string, id: string): Promise<ArtifactRecord> {
  return api<ArtifactRecord>(`/api/projects/${projectId}/service-metadata/${id}`)
}

export function createServiceMetadata(
  projectId: string,
  payload: { id: string; title: string; data: Record<string, any> },
): Promise<ArtifactRecord> {
  return api<ArtifactRecord>(`/api/projects/${projectId}/service-metadata`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateServiceMetadata(
  projectId: string,
  id: string,
  payload: Partial<{ title: string; status: string; data: Record<string, any> }>,
): Promise<ArtifactRecord> {
  return api<ArtifactRecord>(`/api/projects/${projectId}/service-metadata/${id}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function deleteServiceMetadata(projectId: string, id: string): Promise<void> {
  return api<void>(`/api/projects/${projectId}/service-metadata/${id}`, { method: 'DELETE' })
}

// ---------------------------------------------------------------------------
// Proposals
// ---------------------------------------------------------------------------

export function listProposals(projectId: string): Promise<ProposalRecord[]> {
  return api<ProposalRecord[]>(`/api/projects/${projectId}/proposals`)
}

export function getProposal(projectId: string, id: string): Promise<ProposalRecord> {
  return api<ProposalRecord>(`/api/projects/${projectId}/proposals/${id}`)
}

export function createProposal(
  projectId: string,
  payload: { id: string; title: string; requirements_id: string; data: Record<string, any> },
): Promise<ProposalRecord> {
  return api<ProposalRecord>(`/api/projects/${projectId}/proposals`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateProposal(
  projectId: string,
  id: string,
  payload: Partial<{ title: string; status: string; data: Record<string, any> }>,
): Promise<ProposalRecord> {
  return api<ProposalRecord>(`/api/projects/${projectId}/proposals/${id}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

// ---------------------------------------------------------------------------
// Evaluations
// ---------------------------------------------------------------------------

export interface ListEvaluationsFilter {
  scenario_id?: string
  proposal_id?: string
}

export function listEvaluations(
  projectId: string,
  filter?: ListEvaluationsFilter,
): Promise<EvaluationRecord[]> {
  const params = new URLSearchParams()
  if (filter?.scenario_id) params.set('scenario_id', filter.scenario_id)
  if (filter?.proposal_id) params.set('proposal_id', filter.proposal_id)
  const qs = params.toString()
  return api<EvaluationRecord[]>(
    `/api/projects/${projectId}/evaluations${qs ? `?${qs}` : ''}`,
  )
}

export function createEvaluation(
  projectId: string,
  payload: {
    id: string
    proposal_id?: string | null
    scenario_id: string
    requirements_id: string
    shape_id?: string | null
    source?: string
    data: Record<string, any>
    input_snapshot: Record<string, any>
  },
): Promise<EvaluationRecord> {
  return api<EvaluationRecord>(`/api/projects/${projectId}/evaluations`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function deleteEvaluation(projectId: string, id: string): Promise<void> {
  return api<void>(`/api/projects/${projectId}/evaluations/${id}`, { method: 'DELETE' })
}

// ---------------------------------------------------------------------------
// Shapes
// ---------------------------------------------------------------------------

export function listShapes(projectId: string): Promise<ShapeRecord[]> {
  return api<ShapeRecord[]>(`/api/projects/${projectId}/shapes`)
}

export function getShape(projectId: string, id: string): Promise<ShapeRecord> {
  return api<ShapeRecord>(`/api/projects/${projectId}/shapes/${id}`)
}

export function createShape(
  projectId: string,
  payload: { id: string; title: string; requirements_id: string; data: Record<string, any> },
): Promise<ShapeRecord> {
  return api<ShapeRecord>(`/api/projects/${projectId}/shapes`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateShape(
  projectId: string,
  id: string,
  payload: Partial<{ title: string; status: string; data: Record<string, any> }>,
): Promise<ShapeRecord> {
  return api<ShapeRecord>(`/api/projects/${projectId}/shapes/${id}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function deleteShape(projectId: string, id: string): Promise<void> {
  return api<void>(`/api/projects/${projectId}/shapes/${id}`, { method: 'DELETE' })
}

export async function getShapeExpectations(
  projectId: string,
  id: string,
): Promise<DerivedExpectation[]> {
  const resp = await api<{ expectations: DerivedExpectation[] }>(`/api/projects/${projectId}/shapes/${id}/expectations`)
  return resp.expectations
}

// ---------------------------------------------------------------------------
// Vocabulary
// ---------------------------------------------------------------------------

export interface ListVocabularyFilter {
  category?: string
  project_id?: string
}

export function listVocabulary(filter?: ListVocabularyFilter): Promise<VocabularyEntry[]> {
  const params = new URLSearchParams()
  if (filter?.category) params.set('category', filter.category)
  if (filter?.project_id) params.set('project_id', filter.project_id)
  const qs = params.toString()
  return api<VocabularyEntry[]>(`/api/vocabulary${qs ? `?${qs}` : ''}`)
}

export function createVocabularyEntry(payload: {
  project_id?: string | null
  category: string
  value: string
  origin?: string
  description?: string
}): Promise<VocabularyEntry> {
  return api<VocabularyEntry>('/api/vocabulary', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function deleteVocabularyEntry(id: number): Promise<void> {
  return api<void>(`/api/vocabulary/${id}`, { method: 'DELETE' })
}

// ---------------------------------------------------------------------------
// Import / Export
// ---------------------------------------------------------------------------

export function importArtifacts(
  projectId: string,
  artifacts: Array<{ type: string; data: Record<string, any> }>,
): Promise<ImportResult> {
  return api<ImportResult>(`/api/projects/${projectId}/import`, {
    method: 'POST',
    body: JSON.stringify({ artifacts }),
  })
}

export function exportProject(projectId: string): Promise<Record<string, any>> {
  return api<Record<string, any>>(`/api/projects/${projectId}/export`)
}

export function generateBusinessBriefDocument(payload: {
  project_id: string
  source_intent?: string
  requirements_id?: string
  scenario_id?: string
  shape_id?: string
  evaluation_id?: string
  llm_assisted?: boolean
}): Promise<{ document: string; assisted: boolean }> {
  return invokeWorkbench<{ document: string; assisted: boolean }>('generate_business_brief', payload)
}

export function generateEngineeringContractDocument(payload: {
  project_id: string
  requirements_id?: string
  scenario_id?: string
  shape_id?: string
  evaluation_id?: string
  llm_assisted?: boolean
}): Promise<{ document: string; assisted: boolean }> {
  return invokeWorkbench<{ document: string; assisted: boolean }>('generate_engineering_contract', payload)
}

export function generateBusinessPacket(payload: {
  project_id: string
  requirements_id?: string
  scenario_id?: string
  shape_id?: string
  evaluation_id?: string
}): Promise<BusinessPacket> {
  return invokeWorkbench<{ packet: BusinessPacket }>('generate_business_packet', payload)
    .then(result => result.packet)
}

export function generateDriftAnalysis(payload: {
  project_id: string
  requirements_id?: string
  scenario_id?: string
  shape_id?: string
  evaluation_id?: string
  service_metadata_artifact_id?: string
  metadata_comparison?: ServiceMetadataComparison
}): Promise<DriftAnalysis> {
  return invokeWorkbench<{ analysis: DriftAnalysis }>('generate_drift_analysis', payload)
    .then(result => result.analysis)
}

export function generateGlueAnalysis(payload: {
  project_id: string
  requirements_id?: string
  scenario_id?: string
  shape_id?: string
  evaluation_id?: string
  service_metadata_artifact_id?: string
  metadata_comparison?: ServiceMetadataComparison
}): Promise<GlueAnalysis> {
  return generateDriftAnalysis(payload)
}





export function listSavedApplicationIntegrationProjects(filter?: { studio_project_id?: string }): Promise<SavedApplicationIntegrationProjectSummary[]> {
  const params = new URLSearchParams()
  if (filter?.studio_project_id) params.set('studio_project_id', filter.studio_project_id)
  const qs = params.toString()
  return api<SavedApplicationIntegrationProjectSummary[]>(`/api/application-integration-projects${qs ? `?${qs}` : ''}`)
}

export function getSavedApplicationIntegrationProject(id: string): Promise<SavedApplicationIntegrationProjectRecord> {
  return api<SavedApplicationIntegrationProjectRecord>(`/api/application-integration-projects/${id}`)
}

export function createSavedApplicationIntegrationProject(
  id: string,
  state: ApplicationIntegrationProjectState,
  studioProjectId?: string | null,
): Promise<SavedApplicationIntegrationProjectRecord> {
  return api<SavedApplicationIntegrationProjectRecord>('/api/application-integration-projects', {
    method: 'POST',
    body: JSON.stringify({ id, studio_project_id: studioProjectId ?? null, state }),
  })
}

export function updateSavedApplicationIntegrationProject(
  id: string,
  state: ApplicationIntegrationProjectState,
  studioProjectId?: string | null,
): Promise<SavedApplicationIntegrationProjectRecord> {
  return api<SavedApplicationIntegrationProjectRecord>(`/api/application-integration-projects/${id}`, {
    method: 'PUT',
    body: JSON.stringify({ studio_project_id: studioProjectId ?? null, state }),
  })
}

export function deleteSavedApplicationIntegrationProject(id: string): Promise<void> {
  return api<void>(`/api/application-integration-projects/${id}`, {
    method: 'DELETE',
  })
}

export function listSavedDataAccessProjects(filter?: { studio_project_id?: string }): Promise<SavedDataAccessProjectSummary[]> {
  const params = new URLSearchParams()
  if (filter?.studio_project_id) params.set('studio_project_id', filter.studio_project_id)
  const qs = params.toString()
  return api<SavedDataAccessProjectSummary[]>(`/api/data-access-projects${qs ? `?${qs}` : ''}`)
}

export function getSavedDataAccessProject(id: string): Promise<SavedDataAccessProjectRecord> {
  return api<SavedDataAccessProjectRecord>(`/api/data-access-projects/${id}`)
}

export function createSavedDataAccessProject(
  id: string,
  state: DataAccessProjectState,
  studioProjectId?: string | null,
): Promise<SavedDataAccessProjectRecord> {
  return api<SavedDataAccessProjectRecord>('/api/data-access-projects', {
    method: 'POST',
    body: JSON.stringify({ id, studio_project_id: studioProjectId ?? null, state }),
  })
}

export function updateSavedDataAccessProject(
  id: string,
  state: DataAccessProjectState,
  studioProjectId?: string | null,
): Promise<SavedDataAccessProjectRecord> {
  return api<SavedDataAccessProjectRecord>(`/api/data-access-projects/${id}`, {
    method: 'PUT',
    body: JSON.stringify({ studio_project_id: studioProjectId ?? null, state }),
  })
}

export function deleteSavedDataAccessProject(id: string): Promise<void> {
  return api<void>(`/api/data-access-projects/${id}`, {
    method: 'DELETE',
  })
}

// ---------------------------------------------------------------------------
// Studio Assistant (ANIP-backed)
// ---------------------------------------------------------------------------

export function explainShapeWithAssistant(
  projectId: string,
  shapeId: string,
  question = '',
): Promise<AssistantExplanation> {
  return invokeAssistant<AssistantExplanation>('explain_shape', {
    project_id: projectId,
    shape_id: shapeId,
    question,
  })
}

export function explainEvaluationWithAssistant(
  projectId: string,
  evaluationId: string,
  question = '',
): Promise<AssistantExplanation> {
  return invokeAssistant<AssistantExplanation>('explain_evaluation', {
    project_id: projectId,
    evaluation_id: evaluationId,
    question,
  })
}

export function interpretProjectIntentWithAssistant(
  projectId: string,
  intent: string,
  sourceRequirementsId?: string | null,
): Promise<IntentInterpretation> {
  return invokeAssistant<IntentInterpretation>('interpret_project_intent', {
    project_id: projectId,
    intent,
    source_requirements_id: sourceRequirementsId || undefined,
  })
}

export function proposeRequirementsWithAssistant(
  projectId: string,
  sourceDocumentText: string,
  sourceRequirementsId?: string | null,
  useDeterministic = false,
  options?: { signal?: AbortSignal },
): Promise<AssistantProposalEnvelope> {
  return invokeAssistant<AssistantProposalEnvelope>('propose_requirements', {
    project_id: projectId,
    source_document_text: sourceDocumentText,
    source_requirements_id: sourceRequirementsId || undefined,
    use_deterministic: useDeterministic || undefined,
  }, options)
}

export function proposeScenariosWithAssistant(
  projectId: string,
  sourceDocumentText: string,
  sourceRequirementsId?: string | null,
  useDeterministic = false,
  options?: { signal?: AbortSignal },
): Promise<AssistantProposalEnvelope> {
  return invokeAssistant<AssistantProposalEnvelope>('propose_scenarios', {
    project_id: projectId,
    source_document_text: sourceDocumentText,
    source_requirements_id: sourceRequirementsId || undefined,
    use_deterministic: useDeterministic || undefined,
  }, options)
}

export function proposeBusinessSummaryWithAssistant(
  projectId: string,
  sourceDocumentText: string,
  sourceRequirementsId?: string | null,
  useDeterministic = false,
  options?: { signal?: AbortSignal },
): Promise<AssistantProposalEnvelope> {
  return invokeAssistant<AssistantProposalEnvelope>('propose_business_summary', {
    project_id: projectId,
    source_document_text: sourceDocumentText,
    source_requirements_id: sourceRequirementsId || undefined,
    use_deterministic: useDeterministic || undefined,
  }, options)
}

export function proposeActorModelWithAssistant(
  projectId: string,
  sourceDocumentText: string,
  sourceRequirementsId?: string | null,
  useDeterministic = false,
  options?: { signal?: AbortSignal },
): Promise<AssistantProposalEnvelope> {
  return invokeAssistant<AssistantProposalEnvelope>('propose_actor_model', {
    project_id: projectId,
    source_document_text: sourceDocumentText,
    source_requirements_id: sourceRequirementsId || undefined,
    use_deterministic: useDeterministic || undefined,
  }, options)
}

export function proposeBusinessAreasWithAssistant(
  projectId: string,
  sourceDocumentText: string,
  sourceRequirementsId?: string | null,
  useDeterministic = false,
  options?: { signal?: AbortSignal },
): Promise<AssistantProposalEnvelope> {
  return invokeAssistant<AssistantProposalEnvelope>('propose_business_areas', {
    project_id: projectId,
    source_document_text: sourceDocumentText,
    source_requirements_id: sourceRequirementsId || undefined,
    use_deterministic: useDeterministic || undefined,
  }, options)
}

export function proposePermissionIntentWithAssistant(
  projectId: string,
  sourceDocumentText: string,
  sourceRequirementsId?: string | null,
  useDeterministic = false,
  options?: { signal?: AbortSignal },
): Promise<AssistantProposalEnvelope> {
  return invokeAssistant<AssistantProposalEnvelope>('propose_permission_intent', {
    project_id: projectId,
    source_document_text: sourceDocumentText,
    source_requirements_id: sourceRequirementsId || undefined,
    use_deterministic: useDeterministic || undefined,
  }, options)
}

export function proposeNonGoalsWithAssistant(
  projectId: string,
  sourceDocumentText: string,
  sourceRequirementsId?: string | null,
  useDeterministic = false,
  options?: { signal?: AbortSignal },
): Promise<AssistantProposalEnvelope> {
  return invokeAssistant<AssistantProposalEnvelope>('propose_non_goals', {
    project_id: projectId,
    source_document_text: sourceDocumentText,
    source_requirements_id: sourceRequirementsId || undefined,
    use_deterministic: useDeterministic || undefined,
  }, options)
}

export function proposeSuccessCriteriaWithAssistant(
  projectId: string,
  sourceDocumentText: string,
  sourceRequirementsId?: string | null,
  useDeterministic = false,
  options?: { signal?: AbortSignal },
): Promise<AssistantProposalEnvelope> {
  return invokeAssistant<AssistantProposalEnvelope>('propose_success_criteria', {
    project_id: projectId,
    source_document_text: sourceDocumentText,
    source_requirements_id: sourceRequirementsId || undefined,
    use_deterministic: useDeterministic || undefined,
  }, options)
}

export function proposeServiceDesignWithAssistant(
  projectId: string,
  sourceDocumentText: string,
  sourceRequirementsId?: string | null,
  sourceShapeId?: string | null,
  useDeterministic = false,
  serviceTopologyPreference?: AssistantServiceTopologyPreference | null,
  options?: { signal?: AbortSignal },
): Promise<AssistantProposalEnvelope> {
  return invokeAssistant<AssistantProposalEnvelope>('propose_service_design', {
    project_id: projectId,
    source_document_text: sourceDocumentText,
    source_requirements_id: sourceRequirementsId || undefined,
    source_shape_id: sourceShapeId || undefined,
    use_deterministic: useDeterministic || undefined,
    service_topology_preference: serviceTopologyPreference || undefined,
  }, options)
}

export function proposeCapabilityFormalizationWithAssistant(
  projectId: string,
  sourceDocumentText: string,
  sourceRequirementsId?: string | null,
  sourceShapeId?: string | null,
  useDeterministic = false,
  options?: { signal?: AbortSignal },
): Promise<AssistantProposalEnvelope> {
  return invokeAssistant<AssistantProposalEnvelope>('propose_capability_formalization', {
    project_id: projectId,
    source_document_text: sourceDocumentText,
    source_requirements_id: sourceRequirementsId || undefined,
    source_shape_id: sourceShapeId || undefined,
    use_deterministic: useDeterministic || undefined,
  }, options)
}

export function proposeRuntimePolicyBindingsWithAssistant(
  projectId: string,
  sourceDocumentText: string,
  sourceRequirementsId?: string | null,
  sourceShapeId?: string | null,
  useDeterministic = false,
  options?: { signal?: AbortSignal },
): Promise<AssistantProposalEnvelope> {
  return invokeAssistant<AssistantProposalEnvelope>('propose_runtime_policy_bindings', {
    project_id: projectId,
    source_document_text: sourceDocumentText,
    source_requirements_id: sourceRequirementsId || undefined,
    source_shape_id: sourceShapeId || undefined,
    use_deterministic: useDeterministic || undefined,
  }, options)
}

export function proposeInputContractsWithAssistant(
  projectId: string,
  sourceDocumentText: string,
  sourceRequirementsId?: string | null,
  sourceShapeId?: string | null,
  useDeterministic = false,
  options?: { signal?: AbortSignal },
): Promise<AssistantProposalEnvelope> {
  return invokeAssistant<AssistantProposalEnvelope>('propose_input_contracts', {
    project_id: projectId,
    source_document_text: sourceDocumentText,
    source_requirements_id: sourceRequirementsId || undefined,
    source_shape_id: sourceShapeId || undefined,
    use_deterministic: useDeterministic || undefined,
  }, options)
}

export function proposeVerificationExpectationsWithAssistant(
  projectId: string,
  sourceDocumentText: string,
  sourceRequirementsId?: string | null,
  sourceShapeId?: string | null,
  useDeterministic = false,
  options?: { signal?: AbortSignal },
): Promise<AssistantProposalEnvelope> {
  return invokeAssistant<AssistantProposalEnvelope>('propose_verification_expectations', {
    project_id: projectId,
    source_document_text: sourceDocumentText,
    source_requirements_id: sourceRequirementsId || undefined,
    source_shape_id: sourceShapeId || undefined,
    use_deterministic: useDeterministic || undefined,
  }, options)
}

export function proposeBackendBindingsWithAssistant(
  projectId: string,
  sourceDocumentText: string,
  sourceRequirementsId?: string | null,
  sourceShapeId?: string | null,
  useDeterministic = false,
  options?: { signal?: AbortSignal },
): Promise<AssistantProposalEnvelope> {
  return invokeAssistant<AssistantProposalEnvelope>('propose_backend_bindings', {
    project_id: projectId,
    source_document_text: sourceDocumentText,
    source_requirements_id: sourceRequirementsId || undefined,
    source_shape_id: sourceShapeId || undefined,
    use_deterministic: useDeterministic || undefined,
  }, options)
}

export function proposeGovernedFrontingCapabilitiesWithAssistant(
  projectId: string,
  sourceDocumentText: string,
  sourceRequirementsId?: string | null,
  sourceShapeId?: string | null,
  useDeterministic = false,
  options?: { signal?: AbortSignal },
): Promise<AssistantProposalEnvelope> {
  return invokeAssistant<AssistantProposalEnvelope>('propose_governed_fronting_capabilities', {
    project_id: projectId,
    source_document_text: sourceDocumentText,
    source_requirements_id: sourceRequirementsId || undefined,
    source_shape_id: sourceShapeId || undefined,
    use_deterministic: useDeterministic || undefined,
  }, options)
}

export function identifyMissingBusinessInfoWithAssistant(
  projectId: string,
  sourceDocumentText: string,
  sourceRequirementsId?: string | null,
  useDeterministic = false,
  options?: { signal?: AbortSignal },
): Promise<AssistantProposalEnvelope> {
  return invokeAssistant<AssistantProposalEnvelope>('identify_missing_business_info', {
    project_id: projectId,
    source_document_text: sourceDocumentText,
    source_requirements_id: sourceRequirementsId || undefined,
    use_deterministic: useDeterministic || undefined,
  }, options)
}

export function clarifyDesignSectionWithAssistant(
  projectId: string,
  mode: 'pm' | 'dev',
  sectionKey: string,
  sourceDocumentText: string,
  sourceRequirementsId?: string | null,
  sourceShapeId?: string | null,
): Promise<AssistantProposalEnvelope> {
  return invokeAssistant<AssistantProposalEnvelope>('clarify_design_section', {
    project_id: projectId,
    mode,
    section_key: sectionKey,
    source_document_text: sourceDocumentText || undefined,
    source_requirements_id: sourceRequirementsId || undefined,
    source_shape_id: sourceShapeId || undefined,
  })
}

export function suggestNextStepWithAssistant(
  projectId: string,
  mode: 'pm' | 'dev',
  question = '',
): Promise<AssistantExplanation> {
  return invokeAssistant<AssistantExplanation>('suggest_next_step', {
    project_id: projectId,
    mode,
    question: question || undefined,
  })
}

export function analyzeAgentConsumptionSimulationWithAssistant(
  projectId: string,
  question = '',
  context?: {
    readinessReport?: unknown
    highRiskReport?: unknown
    focus?: unknown
  },
): Promise<AssistantExplanation> {
  return invokeAssistant<AssistantExplanation>('analyze_agent_consumption_simulation', {
    project_id: projectId,
    question: question || undefined,
    agent_consumption_readiness: context?.readinessReport,
    high_risk_confirmations: context?.highRiskReport,
    focus: context?.focus,
  })
}

export function applyAssistantProposal(
  projectId: string,
  payload: {
    artifact_id: string
    title: string
    capability: string
    proposal: AssistantProposal
    accepted_item_ids: string[]
    rejected_item_ids?: string[]
    accepted_answers?: Record<string, string>
    notes?: string
  },
): Promise<ArtifactRecord> {
  return api<ArtifactRecord>(`/api/projects/${projectId}/assistant/proposals/apply`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function acceptFirstDesign(
  projectId: string,
  sourceIntent: string,
  interpretation: IntentInterpretation,
): Promise<{
  requirements: RequirementsRecord
  scenarios: ArtifactRecord[]
  shape: ShapeRecord
}> {
  return invokeWorkbench('accept_first_design', {
    project_id: projectId,
    source_intent: sourceIntent,
    interpretation,
  })
}
