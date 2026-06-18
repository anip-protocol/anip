export interface RegistryRevisionLineage {
  project_ref?: string
  product_revision?: {
    ref?: string
    artifact_id?: string | null
    revision_number?: number | null
    baseline_locked_at?: string | null
  }
  developer_revision?: {
    ref?: string
    artifact_id?: string | null
    revision_number?: number | null
    contract_signature?: string
  }
}

export interface PublisherSummary {
  publisher_id: string
  publisher_type: string
  display_name: string
  website_url?: string
  status: string
  trust_level: string
}

export interface RegistryPublisher {
  publisher_id: string
  publisher_type: string
  display_name: string
  description: string
  website_url: string
  status: string
  trust_level: string
  created_by_user_id?: string
  created_at: string
  updated_at: string
}

export interface RegistryPublishTokenScopes {
  operations: string[]
  namespaces: string[]
  package_ids?: string[]
  template_ids?: string[]
}

export interface PublisherSelfServiceContext {
  publisher: RegistryPublisher
  scopes: RegistryPublishTokenScopes
}

export interface RegistryPublishTokenSummary {
  token_id: string
  publisher_id: string
  label: string
  scopes: RegistryPublishTokenScopes
  expires_at?: string
  last_used_at?: string
  revoked_at?: string
  created_at: string
  updated_at: string
}

export interface CreatePublishTokenRequest {
  label: string
  scopes: RegistryPublishTokenScopes
  expires_at?: string
}

export interface CreatePublishTokenResult {
  token: RegistryPublishTokenSummary
  bearer_token: string
}

export interface PublisherArtifactSummary {
  artifact_kind: 'package' | 'template'
  artifact_id: string
  namespace: string
  status: string
  created_at: string
  updated_at: string
}

export interface UpdatePublisherRequest {
  display_name: string
  description: string
  website_url: string
}

export interface RegistryNamespaceSummary {
  namespace: string
  publisher_id: string
  artifact_kinds: string[]
  status: string
  created_at: string
  updated_at: string
}

export interface CreateNamespaceRequest {
  namespace: string
  artifact_kinds: string[]
}

export interface UpdateNamespaceStatusRequest {
  status: string
  reason?: string
}

export interface UpdatePublisherStatusRequest {
  status: string
  trust_level?: string
  reason?: string
}

export interface UpdateArtifactOwnershipStatusRequest {
  status: string
  reason?: string
}

export interface TransferArtifactOwnershipRequest {
  target_publisher_id: string
  target_namespace: string
  reason?: string
}

export interface PublicationSummary {
  package_id: string
  package_version: string
  project_ref: string
  product_revision_ref: string
  developer_revision_ref: string
  contract_signature: string
  publisher_id?: string
  publisher_type?: string
  publisher?: PublisherSummary
  lineage?: RegistryRevisionLineage
  published_at: string
  download_count?: number
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
  publisher?: PublisherSummary
  lineage?: RegistryRevisionLineage
  schema_version: string
  manifest_digest: string
  definition_digest: string
  lock_digest?: string
  published_at: string
  download_count?: number
  manifest: Record<string, unknown>
  service_definition: Record<string, unknown>
  recommended_lock: Record<string, unknown>
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
  issued_at: string
}

export interface TemplateSummary {
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
  publisher?: PublisherSummary
  published_at: string
  download_count?: number
  manifest?: Record<string, unknown>
}

export interface RegistryTemplateRecord extends TemplateSummary {
  manifest_digest: string
  template_digest: string
  package_digest: string
  manifest: Record<string, unknown>
  template: Record<string, unknown>
  package: Record<string, unknown>
}

const API_BASE = `${(import.meta.env.VITE_REGISTRY_API_BASE || '/registry-api/v1').replace(/\/$/, '')}`

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init)
  if (!response.ok) {
    const detail = await response.text().catch(() => response.statusText)
    throw new Error(`Registry request failed (${response.status}): ${detail || response.statusText}`)
  }
  return response.json() as Promise<T>
}

function authHeaders(token: string, extra: HeadersInit = {}): HeadersInit {
  return {
    ...extra,
    Authorization: `Bearer ${token}`,
  }
}

export async function listPublications(): Promise<PublicationSummary[]> {
  const payload = await api<{ items: PublicationSummary[] }>('/publications')
  return payload.items
}

export function getPackage(packageId: string, version: string): Promise<RegistryPackageRecord> {
  return api<RegistryPackageRecord>(`/packages/${encodeURIComponent(packageId)}/${encodeURIComponent(version)}`)
}

export function getReceipt(packageId: string, version: string): Promise<RegistryReceipt> {
  return api<RegistryReceipt>(`/packages/${encodeURIComponent(packageId)}/${encodeURIComponent(version)}/receipt`)
}

export function packageLockURL(packageId: string, version: string): string {
  return `${API_BASE}/packages/${encodeURIComponent(packageId)}/${encodeURIComponent(version)}/lock`
}

export async function listTemplates(): Promise<TemplateSummary[]> {
  const payload = await api<{ items: TemplateSummary[] }>('/templates')
  return payload.items
}

export function getTemplate(templateId: string, version: string): Promise<RegistryTemplateRecord> {
  return api<RegistryTemplateRecord>(`/templates/${encodeURIComponent(templateId)}/${encodeURIComponent(version)}`)
}

export function templateDownloadURL(templateId: string, version: string): string {
  return `${API_BASE}/templates/${encodeURIComponent(templateId)}/${encodeURIComponent(version)}/download`
}

export async function getMyPublisher(token: string): Promise<RegistryPublisher> {
  const payload = await getMyPublisherContext(token)
  return payload.publisher
}

export function getMyPublisherContext(token: string): Promise<PublisherSelfServiceContext> {
  return api<PublisherSelfServiceContext>('/me/publisher', {
    headers: authHeaders(token),
  })
}

export async function updateMyPublisher(token: string, request: UpdatePublisherRequest): Promise<RegistryPublisher> {
  const payload = await api<{ publisher: RegistryPublisher }>('/me/publisher', {
    method: 'PATCH',
    headers: authHeaders(token, { 'Content-Type': 'application/json' }),
    body: JSON.stringify(request),
  })
  return payload.publisher
}

export async function listMyNamespaces(token: string): Promise<RegistryNamespaceSummary[]> {
  const payload = await api<{ items: RegistryNamespaceSummary[] }>('/me/namespaces', {
    headers: authHeaders(token),
  })
  return payload.items
}

export async function createMyNamespace(token: string, request: CreateNamespaceRequest): Promise<RegistryNamespaceSummary> {
  const payload = await api<{ namespace: RegistryNamespaceSummary }>('/me/namespaces', {
    method: 'POST',
    headers: authHeaders(token, { 'Content-Type': 'application/json' }),
    body: JSON.stringify(request),
  })
  return payload.namespace
}

export async function listMyArtifacts(token: string): Promise<PublisherArtifactSummary[]> {
  const payload = await api<{ items: PublisherArtifactSummary[] }>('/me/artifacts', {
    headers: authHeaders(token),
  })
  return payload.items
}

export async function listMyTokens(token: string): Promise<RegistryPublishTokenSummary[]> {
  const payload = await api<{ items: RegistryPublishTokenSummary[] }>('/me/tokens', {
    headers: authHeaders(token),
  })
  return payload.items
}

export function createMyToken(token: string, request: CreatePublishTokenRequest): Promise<CreatePublishTokenResult> {
  return api<CreatePublishTokenResult>('/me/tokens', {
    method: 'POST',
    headers: authHeaders(token, { 'Content-Type': 'application/json' }),
    body: JSON.stringify(request),
  })
}

export async function revokeMyToken(token: string, tokenId: string): Promise<RegistryPublishTokenSummary> {
  const payload = await api<{ token: RegistryPublishTokenSummary }>(`/me/tokens/${encodeURIComponent(tokenId)}`, {
    method: 'DELETE',
    headers: authHeaders(token),
  })
  return payload.token
}

export async function listAdminNamespaces(token: string): Promise<RegistryNamespaceSummary[]> {
  const payload = await api<{ items: RegistryNamespaceSummary[] }>('/admin/namespaces', {
    headers: authHeaders(token),
  })
  return payload.items
}

export async function listAdminPublishers(token: string): Promise<RegistryPublisher[]> {
  const payload = await api<{ items: RegistryPublisher[] }>('/admin/publishers', {
    headers: authHeaders(token),
  })
  return payload.items
}

export async function listAdminArtifacts(token: string): Promise<PublisherArtifactSummary[]> {
  const payload = await api<{ items: PublisherArtifactSummary[] }>('/admin/artifacts', {
    headers: authHeaders(token),
  })
  return payload.items
}

export async function updateAdminNamespaceStatus(
  token: string,
  namespace: string,
  request: UpdateNamespaceStatusRequest,
): Promise<RegistryNamespaceSummary> {
  const payload = await api<{ namespace: RegistryNamespaceSummary }>(`/admin/namespaces/${encodeURIComponent(namespace)}`, {
    method: 'PATCH',
    headers: authHeaders(token, { 'Content-Type': 'application/json' }),
    body: JSON.stringify(request),
  })
  return payload.namespace
}

export async function updateAdminPublisherStatus(
  token: string,
  publisherId: string,
  request: UpdatePublisherStatusRequest,
): Promise<RegistryPublisher> {
  const payload = await api<{ publisher: RegistryPublisher }>(`/admin/publishers/${encodeURIComponent(publisherId)}/status`, {
    method: 'PATCH',
    headers: authHeaders(token, { 'Content-Type': 'application/json' }),
    body: JSON.stringify(request),
  })
  return payload.publisher
}

export async function updateAdminArtifactStatus(
  token: string,
  artifactKind: string,
  artifactId: string,
  request: UpdateArtifactOwnershipStatusRequest,
): Promise<PublisherArtifactSummary> {
  const payload = await api<{ artifact: PublisherArtifactSummary }>(
    `/admin/artifact-status/${encodeURIComponent(artifactKind)}/${encodeURIComponent(artifactId)}`,
    {
      method: 'PATCH',
      headers: authHeaders(token, { 'Content-Type': 'application/json' }),
      body: JSON.stringify(request),
    },
  )
  return payload.artifact
}

export async function transferAdminArtifactOwnership(
  token: string,
  artifactKind: string,
  artifactId: string,
  request: TransferArtifactOwnershipRequest,
): Promise<PublisherArtifactSummary> {
  const payload = await api<{ artifact: PublisherArtifactSummary }>(
    `/admin/artifact-transfer/${encodeURIComponent(artifactKind)}/${encodeURIComponent(artifactId)}`,
    {
      method: 'POST',
      headers: authHeaders(token, { 'Content-Type': 'application/json' }),
      body: JSON.stringify(request),
    },
  )
  return payload.artifact
}
