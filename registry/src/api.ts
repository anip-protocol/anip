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

export interface PublicationSummary {
  package_id: string
  package_version: string
  project_ref: string
  product_revision_ref: string
  developer_revision_ref: string
  contract_signature: string
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

async function api<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`)
  if (!response.ok) {
    const detail = await response.text().catch(() => response.statusText)
    throw new Error(`Registry request failed (${response.status}): ${detail || response.statusText}`)
  }
  return response.json() as Promise<T>
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
