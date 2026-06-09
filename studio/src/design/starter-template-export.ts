import type {
  ArtifactRecord,
  DeveloperDefinitionData,
  DeveloperDefinitionRevisionData,
  IntegrationDiscoveryRecord,
  ProjectDetail,
  ProjectDocumentRecord,
  WorkspaceConnection,
} from './project-types'
import { INTEGRATION_FRONTING_MAPPING_ARTIFACT_TYPE } from './developer-definition'
import type {
  StarterTemplate,
  StarterTemplateCapabilityMapping,
  StarterTemplateConnection,
  StarterTemplateDiscoveryRecord,
  StarterTemplateDocument,
} from './starter-templates'
import { validateStarterTemplate } from './starter-templates'
import {
  buildStarterTemplatePackageEnvelope,
  type StarterTemplatePackage,
} from './starter-template-package'
import { STUDIO_PROTOCOL_VERSION } from '../version'

export interface StarterTemplateExportSelection {
  documentIds: string[]
  connectionIds: string[]
  discoveryRecordIds: string[]
  mappingArtifactIds: string[]
}

export interface StarterTemplateDocumentInput {
  record: ProjectDocumentRecord
  content: string
}

function slugify(value: string, fallback: string): string {
  const slug = value
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 80)
  return slug || fallback
}

function safeFilename(value: string, fallback: string): string {
  const basename = value.split(/[\\/]/).pop() || fallback
  const cleaned = basename
    .replace(/\.\.+/g, '.')
    .replace(/[^A-Za-z0-9_.-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 120)
  return cleaned && /^[A-Za-z0-9]/.test(cleaned) ? cleaned : fallback
}

function titleizeRef(value: string, fallback: string): string {
  const words = value
    .replace(/^conn[_-]/, '')
    .split(/[^A-Za-z0-9]+/)
    .filter(Boolean)
  return words.length > 0
    ? words.map((word) => `${word.charAt(0).toUpperCase()}${word.slice(1)}`).join(' ')
    : fallback
}

function templateRefBase(ref: string, project: ProjectDetail): string {
  let value = ref.trim().replace(/^conn[_-]/, '')
  if (project.id && value.startsWith(project.id)) {
    value = value.slice(project.id.length).replace(/^[-_]+/, '')
  }
  return value || ref.trim()
}

function envRef(value: string, suffix: string): string {
  const prefix = value
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 80) || 'INTEGRATION'
  return `${prefix}_${suffix}`
}

function mappingBackendKind(data: Record<string, any>, binding?: Record<string, any>): WorkspaceConnection['backend_kind'] {
  const candidate = String(binding?.backend_kind ?? data.backend_kind ?? '').trim()
  return ['native_api', 'mcp', 'database', 'hybrid'].includes(candidate)
    ? candidate as WorkspaceConnection['backend_kind']
    : 'native_api'
}

function collectMappingConnectionRefs(mappings: ArtifactRecord[]): Array<{
  ref: string
  backendKind: WorkspaceConnection['backend_kind']
}> {
  const refs = new Map<string, WorkspaceConnection['backend_kind']>()
  for (const artifact of mappings) {
    const data = artifact.data ?? {}
    const addRef = (ref: unknown, binding?: Record<string, any>) => {
      if (typeof ref !== 'string' || !ref.trim()) return
      const value = ref.trim()
      if (!refs.has(value)) refs.set(value, mappingBackendKind(data, binding))
    }
    addRef(data.connection_ref)
    for (const binding of Array.isArray(data.backend_bindings) ? data.backend_bindings : []) {
      if (binding && typeof binding === 'object' && !Array.isArray(binding)) {
        addRef(binding.connection_ref, binding as Record<string, any>)
      }
    }
  }
  return [...refs.entries()].map(([ref, backendKind]) => ({ ref, backendKind }))
}

type MappingOperationRef = {
  operationId: string
  connectionRef: string
  backendKind: IntegrationDiscoveryRecord['backend_kind']
  sideEffectLevel: string
  requiredInputs: string[]
  optionalInputs: string[]
  capabilityId: string
}

function templateConnectionFromMappingRef(
  ref: string,
  backendKind: WorkspaceConnection['backend_kind'],
  suffix: string,
  project: ProjectDetail,
): StarterTemplateConnection {
  const refBase = templateRefBase(ref, project)
  const systemKind = project.domain || slugify(refBase, 'integration')
  const systemEnv = systemKind || 'integration'
  return {
    idSuffix: suffix,
    display_name: titleizeRef(refBase, `${systemKind} backend`),
    backend_kind: backendKind,
    system_kind: systemKind,
    endpoint_ref: backendKind === 'mcp'
      ? envRef(systemEnv, 'MCP_ENDPOINT')
      : envRef(systemEnv, 'BASE_URL'),
    auth_mode: backendKind === 'mcp' ? 'external' : 'service_delegated',
    identity_provider_ref: 'workspace-identity',
    secret_ref: backendKind === 'mcp'
      ? envRef(systemEnv, 'MCP_TOKEN')
      : envRef(systemEnv, 'API_TOKEN'),
    metadata: {
      exported_from_mapping_connection_ref: ref,
      synthesized_from_fronting_mapping: true,
      template_suggested: true,
    },
  }
}

function selectedMappingOperationRefs(mappings: ArtifactRecord[]): MappingOperationRef[] {
  const operations = new Map<string, MappingOperationRef>()
  for (const artifact of mappings) {
    const data = artifact.data ?? {}
    const capabilityId = String(data.capability_id ?? '').trim()
    const defaultConnectionRef = String(data.connection_ref ?? '').trim()
    const sideEffectLevel = String(data.side_effect_level ?? 'read').trim() || 'read'
    for (const binding of Array.isArray(data.backend_bindings) ? data.backend_bindings : []) {
      if (!binding || typeof binding !== 'object' || Array.isArray(binding)) continue
      const bindingRecord = binding as Record<string, any>
      const connectionRef = String(bindingRecord.connection_ref ?? defaultConnectionRef).trim()
      if (!connectionRef) continue
      const backendKind = mappingBackendKind(data, bindingRecord)
      const requiredInputs = [
        ...(Array.isArray(bindingRecord.explicit_required_backend_inputs) ? bindingRecord.explicit_required_backend_inputs : []),
        ...(Array.isArray(bindingRecord.derived_required_backend_inputs) ? bindingRecord.derived_required_backend_inputs : []),
      ].map(String).filter(Boolean)
      const optionalInputs = [
        ...(Array.isArray(bindingRecord.explicit_optional_backend_inputs) ? bindingRecord.explicit_optional_backend_inputs : []),
        ...(Array.isArray(bindingRecord.derived_optional_backend_inputs) ? bindingRecord.derived_optional_backend_inputs : []),
      ].map(String).filter(Boolean)
      for (const operationId of Array.isArray(bindingRecord.raw_operation_refs) ? bindingRecord.raw_operation_refs : []) {
        const operation = String(operationId ?? '').trim()
        if (!operation || operations.has(operation)) continue
        operations.set(operation, {
          operationId: operation,
          connectionRef,
          backendKind,
          sideEffectLevel,
          requiredInputs: [...new Set(requiredInputs)],
          optionalInputs: [...new Set(optionalInputs)],
          capabilityId,
        })
      }
    }
  }
  return [...operations.values()]
}

function validateExportDocument(document: StarterTemplateDocumentInput, index: number): void {
  const filename = document.record.filename.trim()
  if (document.record.media_type !== 'text/markdown' || !filename.toLowerCase().endsWith('.md')) {
    throw new Error(`Template source document '${document.record.title || `document-${index + 1}`}' must be a Markdown .md file.`)
  }
}

function uniqueSuffix(base: string, used: Set<string>): string {
  let candidate = base
  let index = 2
  while (used.has(candidate)) {
    candidate = `${base}-${index}`
    index += 1
  }
  used.add(candidate)
  return candidate
}

function cloneRecord<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function templateConnectionFromRecord(connection: WorkspaceConnection, suffix: string): StarterTemplateConnection {
  return {
    idSuffix: suffix,
    display_name: connection.display_name,
    backend_kind: connection.backend_kind,
    system_kind: connection.system_kind,
    endpoint_ref: connection.endpoint_ref,
    auth_mode: connection.auth_mode,
    identity_provider_ref: connection.identity_provider_ref,
    secret_ref: connection.secret_ref,
    metadata: {
      ...(connection.metadata ?? {}),
      exported_from_connection_id: connection.id,
      template_suggested: true,
    },
  }
}

function templateDiscoveryFromRecord(
  record: IntegrationDiscoveryRecord,
  suffix: string,
  connectionRefById: Map<string, string>,
): StarterTemplateDiscoveryRecord {
  return {
    idSuffix: suffix,
    connectionIdSuffix: record.connection_id ? (connectionRefById.get(record.connection_id) ?? '') : '',
    operation_id: record.operation_id,
    backend_kind: record.backend_kind,
    method: record.method,
    path_template: record.path_template,
    side_effect_level: record.side_effect_level,
    input_schema_summary: cloneRecord(record.input_schema_summary ?? {}),
    risk_notes: [...(record.risk_notes ?? [])],
    data: {
      ...(cloneRecord(record.data ?? {})),
      exported_from_discovery_record_id: record.id,
      template_suggested: true,
    },
  }
}

function normalizeMappingData(
  artifact: ArtifactRecord,
  connectionRefById: Map<string, string>,
  discoveryRefById: Map<string, string>,
  discoveryRefByOperationId: Map<string, string>,
  developerDefinition?: DeveloperDefinitionData | DeveloperDefinitionRevisionData | null,
): Record<string, any> {
  const data = cloneRecord(artifact.data ?? {})
  const capabilityId = typeof data.capability_id === 'string' ? data.capability_id : ''
  const reviewedCapability = capabilityId
    ? developerDefinition?.capability_formalizations?.find((capability) => capability.capability_id === capabilityId)
    : null
  delete data.id
  data.template_suggested = true
  data.review_status = 'template_suggested'
  data.exported_from_artifact_id = artifact.id
  if (reviewedCapability) {
    data.inputs = cloneRecord(reviewedCapability.inputs ?? [])
    data.operation_type = reviewedCapability.operation_type || data.operation_type
    data.side_effect_level = reviewedCapability.side_effect_level || data.side_effect_level
    data.intent_type = reviewedCapability.intent_type || data.intent_type
    data.grant_policy = reviewedCapability.grant_policy
      ? cloneRecord(reviewedCapability.grant_policy)
      : data.grant_policy
    data.business_effects = reviewedCapability.business_effects
      ? cloneRecord(reviewedCapability.business_effects)
      : data.business_effects
  }
  if (typeof data.connection_ref === 'string' && connectionRefById.has(data.connection_ref)) {
    data.connection_ref = connectionRefById.get(data.connection_ref)
  }
  if (Array.isArray(data.backend_bindings)) {
    data.backend_bindings = data.backend_bindings.map((binding: Record<string, any>) => {
      const next = { ...binding }
      if (typeof next.connection_ref === 'string' && connectionRefById.has(next.connection_ref)) {
        next.connection_ref = connectionRefById.get(next.connection_ref)
      }
      if (Array.isArray(next.matched_discovery_record_ids)) {
        next.matched_discovery_record_ids = next.matched_discovery_record_ids
          .map((id: unknown) => typeof id === 'string' ? discoveryRefById.get(id) : null)
          .filter((id: unknown): id is string => typeof id === 'string' && id.length > 0)
      }
      if (
        (!Array.isArray(next.matched_discovery_record_ids) || next.matched_discovery_record_ids.length === 0)
        && Array.isArray(next.raw_operation_refs)
      ) {
        next.matched_discovery_record_ids = next.raw_operation_refs
          .map((operationId: unknown) => typeof operationId === 'string' ? discoveryRefByOperationId.get(operationId) : null)
          .filter((id: unknown): id is string => typeof id === 'string' && id.length > 0)
      }
      return next
    })
  }
  return data
}

export async function buildStarterTemplatePackageFromProject(args: {
  project: ProjectDetail
  documents: StarterTemplateDocumentInput[]
  connections: WorkspaceConnection[]
  discoveryRecords: IntegrationDiscoveryRecord[]
  mappingArtifacts: ArtifactRecord[]
  developerDefinition?: DeveloperDefinitionData | DeveloperDefinitionRevisionData | null
  selection: StarterTemplateExportSelection
  packageVersion?: string
  exportedAt?: string
}): Promise<StarterTemplatePackage> {
  const selectedDocumentIds = new Set(args.selection.documentIds)
  const selectedConnectionIds = new Set(args.selection.connectionIds)
  const selectedDiscoveryIds = new Set(args.selection.discoveryRecordIds)
  const selectedMappingIds = new Set(args.selection.mappingArtifactIds)
  const selectedDocuments = args.documents.filter((document) => selectedDocumentIds.has(document.record.id))
  const selectedConnections = args.connections.filter((connection) => selectedConnectionIds.has(connection.id))
  const selectedDiscoveryRecords = args.discoveryRecords.filter((record) => selectedDiscoveryIds.has(record.id))
  const selectedMappings = args.mappingArtifacts.filter((artifact) =>
    selectedMappingIds.has(artifact.id)
    && artifact.data?.artifact_type === INTEGRATION_FRONTING_MAPPING_ARTIFACT_TYPE,
  )

  const usedDocumentSuffixes = new Set<string>()
  const documents: StarterTemplateDocument[] = selectedDocuments.map((document, index) => {
    validateExportDocument(document, index)
    return {
      idSuffix: uniqueSuffix(slugify(document.record.filename.replace(/\.[^.]+$/, ''), `document-${index + 1}`), usedDocumentSuffixes),
      title: document.record.title,
      kind: document.record.kind,
      filename: safeFilename(document.record.filename, `document-${index + 1}.md`),
      content: document.content,
    }
  })

  const usedConnectionSuffixes = new Set<string>()
  const connectionRefById = new Map<string, string>()
  const connections = selectedConnections.map((connection, index) => {
    const suffix = uniqueSuffix(slugify(connection.display_name || connection.id, `connection-${index + 1}`), usedConnectionSuffixes)
    connectionRefById.set(connection.id, suffix)
    return templateConnectionFromRecord(connection, suffix)
  })
  for (const { ref, backendKind } of collectMappingConnectionRefs(selectedMappings)) {
    if (connectionRefById.has(ref)) continue
    const suffix = uniqueSuffix(slugify(templateRefBase(ref, args.project), `connection-${connections.length + 1}`), usedConnectionSuffixes)
    connectionRefById.set(ref, suffix)
    connections.push(templateConnectionFromMappingRef(ref, backendKind, suffix, args.project))
  }

  const usedDiscoverySuffixes = new Set<string>()
  const discoveryRefById = new Map<string, string>()
  const discoveryRefByOperationId = new Map<string, string>()
  const discoveryRecords = selectedDiscoveryRecords
    .filter((record) => !!record.connection_id && connectionRefById.has(record.connection_id))
    .map((record, index) => {
      const suffix = uniqueSuffix(slugify(record.operation_id, `operation-${index + 1}`), usedDiscoverySuffixes)
      discoveryRefById.set(record.id, suffix)
      discoveryRefByOperationId.set(record.operation_id, suffix)
      return templateDiscoveryFromRecord(record, suffix, connectionRefById)
    })
  for (const operation of selectedMappingOperationRefs(selectedMappings)) {
    if (discoveryRefByOperationId.has(operation.operationId)) continue
    const connectionIdSuffix = connectionRefById.get(operation.connectionRef)
    if (!connectionIdSuffix) continue
    const suffix = uniqueSuffix(slugify(operation.operationId, `operation-${discoveryRecords.length + 1}`), usedDiscoverySuffixes)
    discoveryRefByOperationId.set(operation.operationId, suffix)
    discoveryRecords.push({
      idSuffix: suffix,
      connectionIdSuffix,
      operation_id: operation.operationId,
      backend_kind: operation.backendKind,
      method: 'CALL',
      path_template: `/backend-operations/${suffix}`,
      side_effect_level: operation.sideEffectLevel,
      input_schema_summary: {
        required: operation.requiredInputs,
        optional: operation.optionalInputs,
      },
      risk_notes: [
        'Synthesized from reviewed fronting mapping metadata; verify backend endpoint details before locking a derived project.',
      ],
      data: {
        capability_id: operation.capabilityId,
        synthesized_from_fronting_mapping: true,
        template_suggested: true,
      },
    })
  }

  const usedMappingSuffixes = new Set<string>()
  const capabilityMappings: StarterTemplateCapabilityMapping[] = selectedMappings.map((artifact, index) => {
    const capabilityId = String(artifact.data?.capability_id ?? artifact.title ?? `mapping-${index + 1}`)
    const suffix = uniqueSuffix(slugify(capabilityId, `mapping-${index + 1}`), usedMappingSuffixes)
    return {
      idSuffix: suffix,
      title: artifact.title,
      data: normalizeMappingData(artifact, connectionRefById, discoveryRefById, discoveryRefByOperationId, args.developerDefinition),
    }
  })

  const template: StarterTemplate = {
    schema: 'anip-starter-template/v0',
    anipSpecVersion: STUDIO_PROTOCOL_VERSION,
    id: `${slugify(args.project.name, 'project')}-starter`,
    kind: args.project.project_type === 'governed_service_project' ? 'fronting_starter' : 'project_starter',
    projectType: args.project.project_type ?? 'standard',
    title: `${args.project.name} Starter`,
    summary: args.project.summary || `Starter template exported from ${args.project.name}.`,
    description: 'Exported from a reviewed Studio project. Review selected source docs, connection refs, backend operations, and mappings before locking or generation.',
    domain: args.project.domain || undefined,
    recommendedBrief: args.project.summary || undefined,
    documents,
    connections,
    discoveryRecords,
    capabilityMappings,
  }
  const validationErrors = validateStarterTemplate(template)
  if (validationErrors.length > 0) {
    throw new Error(`Exported starter template is invalid: ${validationErrors.join(' ')}`)
  }

  return buildStarterTemplatePackageEnvelope({
    packageVersion: args.packageVersion,
    exportedAt: args.exportedAt,
    sourceProject: {
      id: args.project.id,
      name: args.project.name,
      project_type: args.project.project_type ?? 'standard',
      ...(args.project.domain ? { domain: args.project.domain } : {}),
    },
    template,
    warnings: [
      'Source documents are included only when explicitly selected.',
      'Secret values are not exported; only secret references are included.',
      'Template data is starter evidence, not locked contract truth.',
    ],
  })
}
