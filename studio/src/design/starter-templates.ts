import type {
  IntegrationDiscoveryRecord,
  ProjectType,
  WorkspaceConnection,
} from './project-types'
import { STUDIO_PROTOCOL_VERSION } from '../version'
import builtInNotionFrontingStarter from './starter-templates/notion-fronting-starter.json'
import builtInJiraFrontingStarter from './starter-templates/jira-fronting-starter.raw.json'

export type StarterTemplateKind = 'fronting_starter' | 'project_starter'

export type StarterTemplateDocument = {
  idSuffix: string
  title: string
  kind: string
  filename: string
  content: string
}

export type StarterTemplateConnection = Omit<WorkspaceConnection, 'id' | 'workspace_id' | 'created_at' | 'updated_at' | 'allowed_project_refs'>
  & { idSuffix: string }

export type StarterTemplateDiscoveryRecord = Omit<IntegrationDiscoveryRecord, 'id' | 'project_id' | 'content_hash' | 'created_at' | 'updated_at' | 'connection_id'>
  & { idSuffix: string; connectionIdSuffix: string }

export type StarterTemplateCapabilityMapping = {
  idSuffix: string
  title: string
  data: Record<string, any>
}

export interface StarterTemplate {
  schema: 'anip-starter-template/v0'
  anipSpecVersion: string
  id: string
  kind: StarterTemplateKind
  projectType: ProjectType
  title: string
  summary: string
  description: string
  domain?: string
  recommendedBrief?: string
  documents: StarterTemplateDocument[]
  connections: StarterTemplateConnection[]
  discoveryRecords: StarterTemplateDiscoveryRecord[]
  capabilityMappings: StarterTemplateCapabilityMapping[]
}

type FrontingStarterInput = {
  name?: string
  type?: string
  required?: boolean
  summary?: string
  default_value?: string
  allowed_values?: string[]
  semantic_type?: string
  validation_pattern?: string
  clarification_hint?: string
  entity_reference?: boolean
  catalog_ref?: string
  resolution?: Record<string, unknown>
}

type FrontingStarterOperation = {
  capability_id?: string
  title?: string
  summary?: string
  service_id?: string
  subject_kind?: string
  context_type?: string
  output_intent?: string
  backend_kind?: string
  connection_ref?: string
  method?: string
  path?: string
  raw_operation_refs?: string[]
  side_effect_level?: string
  backend_input_mode?: string
  inputs?: FrontingStarterInput[]
}

type FrontingStarter = {
  schema_version?: string
  system_name?: string
  domain_name?: string
  service_id?: string
  service_name?: string
  backend_kind?: string
  connection_ref?: string
  operations?: FrontingStarterOperation[]
  supporting_capabilities?: FrontingStarterOperation[]
}

export interface ExpandedStarterTemplate {
  template: StarterTemplate
  documents: Array<StarterTemplateDocument & { id: string }>
  connections: Array<Omit<WorkspaceConnection, 'workspace_id' | 'created_at' | 'updated_at'>>
  discoveryRecords: Array<Omit<IntegrationDiscoveryRecord, 'project_id' | 'content_hash' | 'created_at' | 'updated_at'>>
  capabilityMappings: StarterTemplateCapabilityMapping[]
}

const SAFE_ID_RE = /^[A-Za-z0-9][A-Za-z0-9_-]{0,95}$/
const SAFE_TEMPLATE_ID_RE = /^[a-z0-9][a-z0-9_-]{0,95}$/
const SAFE_CAPABILITY_ID_RE = /^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$/
const SAFE_OPERATION_ID_RE = /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$/
const SAFE_FILENAME_RE = /^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/
const ANIP_SPEC_VERSION_RE = /^anip\/(\d+)\.(\d+)$/
const ENV_REF_RE = /^[A-Z][A-Z0-9_]{1,127}$/
const MAX_TEMPLATE_TEXT = 50000
const MAX_TEMPLATE_DOCUMENTS = 20
const MAX_TEMPLATE_CONNECTIONS = 20
const MAX_TEMPLATE_DISCOVERY_RECORDS = 200
const MAX_TEMPLATE_MAPPINGS = 100

const BUILT_IN_STARTER_TEMPLATE_DATA = [
  builtInNotionFrontingStarter,
  builtInJiraFrontingStarter,
] as unknown[]

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function stringField(record: Record<string, unknown>, field: string): string {
  const value = record[field]
  return typeof value === 'string' ? value : ''
}

function parseAnipSpecVersion(value: string): [number, number] | null {
  const match = ANIP_SPEC_VERSION_RE.exec(value)
  if (!match) return null
  return [Number(match[1]), Number(match[2])]
}

function isValidEndpointRef(value: string): boolean {
  if (ENV_REF_RE.test(value)) return true
  try {
    const parsed = new URL(value)
    return parsed.protocol === 'https:' || parsed.protocol === 'http:'
  } catch {
    return false
  }
}

function pushDuplicateErrors(values: string[], label: string, errors: string[]): void {
  const seen = new Set<string>()
  for (const value of values) {
    if (seen.has(value)) {
      errors.push(`${label} '${value}' is duplicated.`)
    }
    seen.add(value)
  }
}

function validateTemplateDocument(document: unknown, index: number, errors: string[]): string | null {
  if (!isRecord(document)) {
    errors.push(`documents[${index}] must be an object.`)
    return null
  }
  const idSuffix = stringField(document, 'idSuffix')
  if (!SAFE_ID_RE.test(idSuffix)) {
    errors.push(`documents[${index}].idSuffix must be a safe id suffix.`)
  }
  for (const field of ['title', 'kind', 'filename', 'content']) {
    if (typeof document[field] !== 'string' || !String(document[field]).trim()) {
      errors.push(`documents[${index}].${field} is required.`)
    }
  }
  const filename = stringField(document, 'filename')
  if (filename.includes('..') || filename.includes('/') || filename.includes('\\') || !SAFE_FILENAME_RE.test(filename)) {
    errors.push(`documents[${index}].filename must be a safe filename, not a path.`)
  }
  if (!filename.toLowerCase().endsWith('.md')) {
    errors.push(`documents[${index}].filename must use the .md extension.`)
  }
  if (stringField(document, 'content').length > MAX_TEMPLATE_TEXT) {
    errors.push(`documents[${index}].content exceeds ${MAX_TEMPLATE_TEXT} characters.`)
  }
  return idSuffix || null
}

function templateInputHasVerifierClassification(input: Record<string, unknown>): boolean {
  return Boolean(
    stringField(input, 'semantic_type').trim()
    || stringField(input, 'input_format').trim()
    || stringField(input, 'validation_pattern').trim()
    || stringField(input, 'clarification_hint').trim()
    || input.entity_reference === true
    || (Array.isArray(input.allowed_values) && input.allowed_values.length > 0),
  )
}

function validateTemplateConnection(connection: unknown, index: number, errors: string[]): string | null {
  if (!isRecord(connection)) {
    errors.push(`connections[${index}] must be an object.`)
    return null
  }
  const idSuffix = stringField(connection, 'idSuffix')
  if (!SAFE_ID_RE.test(idSuffix)) {
    errors.push(`connections[${index}].idSuffix must be a safe id suffix.`)
  }
  if (!['native_api', 'mcp', 'database', 'hybrid'].includes(stringField(connection, 'backend_kind'))) {
    errors.push(`connections[${index}].backend_kind is not supported.`)
  }
  if (!['user_delegated', 'service_delegated', 'external'].includes(stringField(connection, 'auth_mode'))) {
    errors.push(`connections[${index}].auth_mode is not supported.`)
  }
  for (const field of ['display_name', 'system_kind', 'endpoint_ref', 'identity_provider_ref', 'secret_ref']) {
    if (typeof connection[field] !== 'string' || !String(connection[field]).trim()) {
      errors.push(`connections[${index}].${field} is required.`)
    }
  }
  if (!isValidEndpointRef(stringField(connection, 'endpoint_ref'))) {
    errors.push(`connections[${index}].endpoint_ref must be an HTTP(S) URL or environment-style reference.`)
  }
  if (stringField(connection, 'secret_ref') && !ENV_REF_RE.test(stringField(connection, 'secret_ref'))) {
    errors.push(`connections[${index}].secret_ref must be an environment-style reference, not a token value.`)
  }
  if (!isRecord(connection.metadata)) {
    errors.push(`connections[${index}].metadata must be an object.`)
  }
  return idSuffix || null
}

function validateTemplateDiscoveryRecord(
  record: unknown,
  index: number,
  connectionIds: Set<string>,
  errors: string[],
): string | null {
  if (!isRecord(record)) {
    errors.push(`discoveryRecords[${index}] must be an object.`)
    return null
  }
  const idSuffix = stringField(record, 'idSuffix')
  if (!SAFE_ID_RE.test(idSuffix)) {
    errors.push(`discoveryRecords[${index}].idSuffix must be a safe id suffix.`)
  }
  const connectionIdSuffix = stringField(record, 'connectionIdSuffix')
  if (!connectionIds.has(connectionIdSuffix)) {
    errors.push(`discoveryRecords[${index}].connectionIdSuffix must reference a template connection.`)
  }
  if (!SAFE_OPERATION_ID_RE.test(stringField(record, 'operation_id'))) {
    errors.push(`discoveryRecords[${index}].operation_id must be a safe operation id.`)
  }
  if (!['native_api', 'mcp', 'database', 'hybrid'].includes(stringField(record, 'backend_kind'))) {
    errors.push(`discoveryRecords[${index}].backend_kind is not supported.`)
  }
  for (const field of ['method', 'path_template', 'side_effect_level']) {
    if (typeof record[field] !== 'string' || !String(record[field]).trim()) {
      errors.push(`discoveryRecords[${index}].${field} is required.`)
    }
  }
  if (!isRecord(record.input_schema_summary)) {
    errors.push(`discoveryRecords[${index}].input_schema_summary must be an object.`)
  }
  if (!Array.isArray(record.risk_notes)) {
    errors.push(`discoveryRecords[${index}].risk_notes must be an array.`)
  }
  if (!isRecord(record.data)) {
    errors.push(`discoveryRecords[${index}].data must be an object.`)
  }
  return idSuffix || null
}

function validateTemplateMapping(
  mapping: unknown,
  index: number,
  connectionIds: Set<string>,
  discoveryIds: Set<string>,
  errors: string[],
): string | null {
  if (!isRecord(mapping)) {
    errors.push(`capabilityMappings[${index}] must be an object.`)
    return null
  }
  const idSuffix = stringField(mapping, 'idSuffix')
  if (!SAFE_ID_RE.test(idSuffix)) {
    errors.push(`capabilityMappings[${index}].idSuffix must be a safe id suffix.`)
  }
  if (typeof mapping.title !== 'string' || !mapping.title.trim()) {
    errors.push(`capabilityMappings[${index}].title is required.`)
  }
  if (!isRecord(mapping.data)) {
    errors.push(`capabilityMappings[${index}].data must be an object.`)
    return idSuffix || null
  }
  const capabilityId = stringField(mapping.data, 'capability_id')
  if (!SAFE_CAPABILITY_ID_RE.test(capabilityId)) {
    errors.push(`capabilityMappings[${index}].data.capability_id must be a safe dotted capability id.`)
  }
  const connectionRef = stringField(mapping.data, 'connection_ref')
  if (connectionRef && !connectionIds.has(connectionRef)) {
    errors.push(`capabilityMappings[${index}].data.connection_ref must reference a template connection.`)
  }
  const backendBindings = mapping.data.backend_bindings
  if (backendBindings !== undefined && !Array.isArray(backendBindings)) {
    errors.push(`capabilityMappings[${index}].data.backend_bindings must be an array when present.`)
  }
  if (Array.isArray(backendBindings)) {
    backendBindings.forEach((binding, bindingIndex) => {
      if (!isRecord(binding)) {
        errors.push(`capabilityMappings[${index}].data.backend_bindings[${bindingIndex}] must be an object.`)
        return
      }
      const bindingConnectionRef = stringField(binding, 'connection_ref')
      if (bindingConnectionRef && !connectionIds.has(bindingConnectionRef)) {
        errors.push(`capabilityMappings[${index}].data.backend_bindings[${bindingIndex}].connection_ref must reference a template connection.`)
      }
      const matchedIds = binding.matched_discovery_record_ids
      if (matchedIds !== undefined && !Array.isArray(matchedIds)) {
        errors.push(`capabilityMappings[${index}].data.backend_bindings[${bindingIndex}].matched_discovery_record_ids must be an array.`)
      }
      if (Array.isArray(matchedIds)) {
        matchedIds.forEach((matchedId) => {
          if (typeof matchedId !== 'string' || !discoveryIds.has(matchedId)) {
            errors.push(`capabilityMappings[${index}].data.backend_bindings[${bindingIndex}].matched_discovery_record_ids must reference template discovery records.`)
          }
        })
      }
    })
  }
  if (Array.isArray(mapping.data.inputs)) {
    mapping.data.inputs.forEach((input, inputIndex) => {
      if (!isRecord(input)) {
        errors.push(`capabilityMappings[${index}].data.inputs[${inputIndex}] must be an object.`)
        return
      }
      if (input.required === true && !templateInputHasVerifierClassification(input)) {
        const inputName = stringField(input, 'input_name') || `input-${inputIndex}`
        errors.push(`capabilityMappings[${index}].data.inputs[${inputIndex}] '${inputName}' is required but missing verifier-recognized classification.`)
      }
    })
  }
  return idSuffix || null
}

export function validateStarterTemplate(template: unknown): string[] {
  const errors: string[] = []
  if (!isRecord(template)) {
    return ['Starter template must be an object.']
  }
  if (template.schema !== 'anip-starter-template/v0') {
    errors.push('schema must be anip-starter-template/v0.')
  }
  const anipSpecVersion = stringField(template, 'anipSpecVersion')
  if (!parseAnipSpecVersion(anipSpecVersion)) {
    errors.push('anipSpecVersion must use the anip/<major>.<minor> format.')
  } else if (anipSpecVersion !== STUDIO_PROTOCOL_VERSION) {
    errors.push(`anipSpecVersion must be ${STUDIO_PROTOCOL_VERSION}.`)
  }
  if (!SAFE_TEMPLATE_ID_RE.test(stringField(template, 'id'))) {
    errors.push('id must be a safe starter-template id.')
  }
  if (!['fronting_starter', 'project_starter'].includes(stringField(template, 'kind'))) {
    errors.push('kind is not supported.')
  }
  if (!['standard', 'governed_service_project'].includes(stringField(template, 'projectType'))) {
    errors.push('projectType is not supported.')
  }
  for (const field of ['title', 'summary', 'description']) {
    const value = stringField(template, field)
    if (!value.trim()) {
      errors.push(`${field} is required.`)
    }
    if (value.length > 2000) {
      errors.push(`${field} exceeds 2000 characters.`)
    }
  }
  if (typeof template.recommendedBrief === 'string' && template.recommendedBrief.length > MAX_TEMPLATE_TEXT) {
    errors.push(`recommendedBrief exceeds ${MAX_TEMPLATE_TEXT} characters.`)
  }

  const documents = Array.isArray(template.documents) ? template.documents : []
  const connections = Array.isArray(template.connections) ? template.connections : []
  const discoveryRecords = Array.isArray(template.discoveryRecords) ? template.discoveryRecords : []
  const capabilityMappings = Array.isArray(template.capabilityMappings) ? template.capabilityMappings : []
  if (!Array.isArray(template.documents)) errors.push('documents must be an array.')
  if (!Array.isArray(template.connections)) errors.push('connections must be an array.')
  if (!Array.isArray(template.discoveryRecords)) errors.push('discoveryRecords must be an array.')
  if (!Array.isArray(template.capabilityMappings)) errors.push('capabilityMappings must be an array.')
  if (documents.length > MAX_TEMPLATE_DOCUMENTS) errors.push(`documents exceeds ${MAX_TEMPLATE_DOCUMENTS} entries.`)
  if (connections.length > MAX_TEMPLATE_CONNECTIONS) errors.push(`connections exceeds ${MAX_TEMPLATE_CONNECTIONS} entries.`)
  if (discoveryRecords.length > MAX_TEMPLATE_DISCOVERY_RECORDS) errors.push(`discoveryRecords exceeds ${MAX_TEMPLATE_DISCOVERY_RECORDS} entries.`)
  if (capabilityMappings.length > MAX_TEMPLATE_MAPPINGS) errors.push(`capabilityMappings exceeds ${MAX_TEMPLATE_MAPPINGS} entries.`)

  const documentIds = documents.map((document, index) => validateTemplateDocument(document, index, errors)).filter((id): id is string => Boolean(id))
  const connectionIds = connections.map((connection, index) => validateTemplateConnection(connection, index, errors)).filter((id): id is string => Boolean(id))
  const connectionIdSet = new Set(connectionIds)
  const discoveryIds = discoveryRecords.map((record, index) =>
    validateTemplateDiscoveryRecord(record, index, connectionIdSet, errors),
  ).filter((id): id is string => Boolean(id))
  const discoveryIdSet = new Set(discoveryIds)
  const mappingIds = capabilityMappings.map((mapping, index) =>
    validateTemplateMapping(mapping, index, connectionIdSet, discoveryIdSet, errors),
  ).filter((id): id is string => Boolean(id))
  pushDuplicateErrors(documentIds, 'document idSuffix', errors)
  pushDuplicateErrors(connectionIds, 'connection idSuffix', errors)
  pushDuplicateErrors(discoveryIds, 'discovery record idSuffix', errors)
  pushDuplicateErrors(mappingIds, 'capability mapping idSuffix', errors)

  return errors
}

function loadStarterTemplates(templates: unknown[]): StarterTemplate[] {
  return templates.map((template, index) => {
    const normalized = normalizeStarterTemplate(template)
    const errors = validateStarterTemplate(normalized)
    if (errors.length > 0) {
      throw new Error(`Invalid starter template at index ${index}: ${errors.join(' ')}`)
    }
    return normalized as StarterTemplate
  })
}

export function normalizeStarterTemplate(template: unknown): unknown {
  if (!isRecord(template) || template.schema_version !== 'anip-fronting-starter/v0') {
    return template
  }
  return frontingStarterToStudioTemplate(template as FrontingStarter)
}

function markdownCell(value: unknown): string {
  return String(value ?? '')
    .replace(/\r?\n/g, ' ')
    .replace(/\|/g, '\\|')
    .trim()
}

function frontingOperationType(operation: FrontingStarterOperation): string {
  return sideEffectIsWriteLike(operation.side_effect_level) ? 'write' : 'read'
}

function frontingSideEffectLevel(operation: FrontingStarterOperation): string {
  return String(operation.side_effect_level ?? '').trim() || 'read'
}

function frontingExecutionPosture(operation: FrontingStarterOperation): string {
  const sideEffect = frontingSideEffectLevel(operation)
  if (sideEffect === 'read') return 'read_only'
  if (sideEffect === 'write') return 'approval_gated'
  return 'prepare_only'
}

function frontingIntentType(operation: FrontingStarterOperation): string {
  return sideEffectIsWriteLike(operation.side_effect_level) ? 'prepare_only' : 'read_only'
}

function frontingCapabilityServiceId(domain: string, operation: FrontingStarterOperation, fallback: string): string {
  if (operation.service_id) return safeIdentifier(operation.service_id, fallback)
  const capabilityId = String(operation.capability_id ?? '')
  if (capabilityId.includes('.adapter.')) return safeIdentifier(`${domain}.adapter`, fallback)
  if (sideEffectIsWriteLike(operation.side_effect_level) && capabilityId.endsWith('.request')) {
    return safeIdentifier(`${domain}.governance`, fallback)
  }
  return safeIdentifier(`${domain}.fronting`, fallback)
}

function frontingProduces(operation: FrontingStarterOperation): string {
  if (sideEffectIsWriteLike(operation.side_effect_level)) return 'approval.request, system.preview_mutation, content.draft'
  const outputIntent = String(operation.output_intent ?? '').toLowerCase()
  if (outputIntent.includes('draft') || outputIntent.includes('notes')) return 'content.draft, data.aggregate'
  return 'content.summary, data.read'
}

function frontingDoesNotProduce(operation: FrontingStarterOperation): string {
  if (sideEffectIsWriteLike(operation.side_effect_level)) return 'approval.execute, system.mutation, raw_data_export'
  const outputIntent = String(operation.output_intent ?? '').toLowerCase()
  if (outputIntent.includes('draft') || outputIntent.includes('notes')) return 'external_dispatch, system.mutation, raw_data_export'
  return 'raw_data_export, system.mutation'
}

function defaultOneTimeGrantPolicy(): Record<string, unknown> {
  return {
    allowed_grant_types: ['one_time', 'session_bound'],
    default_grant_type: 'one_time',
    expires_in_seconds: 900,
    max_uses: 1,
  }
}

function frontingDeveloperEvidenceDocument(params: {
  domain: string
  templateId: string
  serviceId: string
  operations: FrontingStarterOperation[]
  supportingCapabilities: FrontingStarterOperation[]
}): string {
  const capabilities = [...params.operations, ...params.supportingCapabilities]
    .filter((operation) => String(operation.capability_id ?? '').trim())

  const normalizedCapabilities = capabilities
    .map((operation) => ({
      capability_id: String(operation.capability_id ?? '').trim(),
      title: operation.title || humanize(String(operation.capability_id ?? '')),
      summary: operation.summary || 'Governed fronting capability.',
      kind: 'atomic',
      source_kind: 'application_integration',
      service_id: frontingCapabilityServiceId(params.domain, operation, params.serviceId),
      operation_type: frontingOperationType(operation),
      side_effect_level: frontingSideEffectLevel(operation),
      execution_posture: frontingExecutionPosture(operation),
      grant_policy: sideEffectIsWriteLike(operation.side_effect_level) ? defaultOneTimeGrantPolicy() : null,
      business_effects: {
        produces: frontingProduces(operation).split(',').map((item) => item.trim()).filter(Boolean),
        does_not_produce: frontingDoesNotProduce(operation).split(',').map((item) => item.trim()).filter(Boolean),
      },
      minimum_scope: [String(operation.capability_id ?? '').trim()],
      backend_operation: operationRefs(operation).join('; '),
      output_shape: operation.output_intent ? `${operation.output_intent}_result` : `${params.domain}_fronting_result`,
      output_intent: operation.output_intent || 'governed_fronting_result',
      intent_type: frontingIntentType(operation),
      subject_kind: operation.subject_kind || 'fronted_resource',
      context_type: operation.context_type || 'fronting_context',
      inputs: normalizeStarterEvidenceInputs(operation.inputs),
    }))

  const summaryRows = normalizedCapabilities
    .filter((operation) => String(operation.capability_id ?? '').trim())
    .map((operation) => [
      operation.capability_id,
      operation.service_id,
      operation.operation_type,
      operation.side_effect_level,
      operation.inputs.length,
      operation.backend_operation,
    ].map(markdownCell))
  const inputRows = normalizedCapabilities.flatMap((operation) =>
    operation.inputs.map((input) => [
      operation.capability_id,
      input.input_name,
      input.input_type,
      input.required ? 'yes' : 'no',
      input.semantic_type || '',
      input.entity_reference ? 'yes' : 'no',
    ].map(markdownCell)),
  )
  const effectRows = normalizedCapabilities.map((operation) => [
    operation.capability_id,
    operation.execution_posture,
    operation.intent_type,
    operation.business_effects.produces.join(', '),
    operation.business_effects.does_not_produce.join(', '),
  ].map(markdownCell))

  return [
    `# ${humanize(params.domain)} Developer Evidence`,
    '',
    `Imported from starter template \`${params.templateId}\`. This is developer-owned evidence for Studio Autopilot and generated-service review.`,
    '',
    'This document turns starter operations into explicit ANIP runtime governance and input-contract evidence. Review it against the real integration before publishing.',
    '',
    '## Capability Evidence Summary',
    '',
    '| capability_id | service_id | operation_type | side_effect_level | inputs | backend_operation |',
    '| --- | --- | --- | --- | ---: | --- |',
    ...summaryRows.map((row) => `| ${row.join(' | ')} |`),
    '',
    '## Reviewed Developer Evidence',
    '',
    'The starter also carries first-class `integration_fronting_capability_mapping` records. Use this document as readable developer evidence, not as the only machine-readable source.',
    '',
    '### Runtime governance',
    '',
    '| capability_id | execution_posture | intent_type | produces | does_not_produce |',
    '| --- | --- | --- | --- | --- |',
    ...effectRows.map((row) => `| ${row.join(' | ')} |`),
    '',
    '### Input contracts',
    '',
    '| capability_id | input | type | required | semantic_type | entity_reference |',
    '| --- | --- | --- | --- | --- | --- |',
    ...inputRows.map((row) => `| ${row.join(' | ')} |`),
  ].join('\n')
}

function frontingStarterToStudioTemplate(starter: FrontingStarter): StarterTemplate {
  const domain = safeIdentifier(starter.domain_name || starter.system_name || 'fronting', 'fronting')
  const templateId = `${domain}-fronting-starter`
  const title = `${humanize(domain)} Fronting Starter`
  const serviceId = safeIdentifier(starter.service_id || `${domain}-governance-service`, `${domain}-service`)
  const serviceName = starter.service_name || `${humanize(domain)} Governance Service`
  const operations = Array.isArray(starter.operations) ? starter.operations : []
  const nativeConnectionSuffix = `${domain}-api`
  const mcpConnectionSuffix = domain === 'jira' ? 'atlassian-mcp' : `${domain}-mcp`
  const sourceTitle = `${humanize(domain)} governed fronting intent`
  const capabilityLines = operations.map((operation) =>
    `- ${operation.capability_id}: ${operation.summary || operation.title || 'Governed fronting capability.'}`,
  )
  const operationLines = operations.flatMap((operation) =>
    operationRefs(operation).map((ref) => {
      const backend = backendKindForRef(ref)
      const label = backend === 'mcp' ? 'MCP tool' : `${methodForOperation(operation, backend)} ${operation.path || '/'}`
      return `- ${ref}: ${label}`
    }),
  )
  const developerEvidence = frontingDeveloperEvidenceDocument({
    domain,
    templateId,
    serviceId,
    operations,
    supportingCapabilities: Array.isArray(starter.supporting_capabilities) ? starter.supporting_capabilities : [],
  })

  return {
    schema: 'anip-starter-template/v0',
    anipSpecVersion: STUDIO_PROTOCOL_VERSION,
    id: templateId,
    kind: 'fronting_starter',
    projectType: 'governed_service_project',
    title,
    summary: `Template-suggested ${humanize(domain)} API/MCP fronting structure with reviewed capability candidates.`,
    description: `Starts a governed ${humanize(domain)} fronting project from reviewed starter data. Verify backend operations, auth posture, and policy boundaries against the real integration before locking.`,
    domain,
    recommendedBrief: [
      `Create a governed ANIP fronting layer for ${humanize(domain)}.`,
      'Expose selected behavior-shaped capabilities instead of raw backend operations.',
      'Read operations must preserve actor-visible scope.',
      'Write-adjacent operations must prepare previews or require approval before downstream mutation.',
    ].join(' '),
    documents: [
      {
        idSuffix: 'template-fronting-intent',
        title: sourceTitle,
        kind: 'business_intent',
        filename: `${domain}-fronting-intent.md`,
        content: [
          `# ${humanize(domain)} Governed Fronting Intent`,
          '',
          `> Imported from starter template \`${templateId}\`. Treat this as draft guidance, not discovered truth.`,
          '',
          `Expose a governed ${humanize(domain)} capability surface in front of native API or MCP-backed operations.`,
          '',
          '## Template-suggested capabilities',
          ...capabilityLines,
          '',
          '## Governance posture',
          `- Raw ${humanize(domain)} tools are not exposed directly to agents.`,
          '- Reads return bounded actor-visible context.',
          '- Write-adjacent actions prepare previews or require explicit approval before execution.',
          '- Missing required inputs trigger clarification instead of guessing.',
        ].join('\n'),
      },
      {
        idSuffix: 'template-integration-evidence',
        title: `${humanize(domain)} integration evidence`,
        kind: 'api_docs',
        filename: `${domain}-integration-evidence.template.md`,
        content: [
          `# ${humanize(domain)} Integration Evidence Template`,
          '',
          `> Imported from starter template \`${templateId}\`. Verify every operation against your chosen native API/MCP source before locking.`,
          '',
          `Native API connection: ${endpointRefFor(domain, 'native_api')}`,
          `MCP connection: ${endpointRefFor(domain, 'mcp')}`,
          '',
          '## Template-suggested backend operations',
          ...operationLines,
          '',
          '## Secret posture',
          '- Studio stores secret references only; project exports must not contain tokens.',
          '- Teams can implement either native API or MCP backend seams behind the same governed ANIP contract.',
        ].join('\n'),
      },
      {
        idSuffix: 'template-developer-evidence',
        title: `${humanize(domain)} developer evidence`,
        kind: 'api_docs',
        filename: `${domain}-developer-evidence.template.md`,
        content: developerEvidence,
      },
    ],
    connections: [
      {
        idSuffix: nativeConnectionSuffix,
        display_name: `${humanize(domain)} API`,
        backend_kind: 'native_api',
        system_kind: domain,
        endpoint_ref: endpointRefFor(domain, 'native_api'),
        auth_mode: 'service_delegated',
        identity_provider_ref: 'workspace-identity',
        secret_ref: secretRefFor(domain, 'native_api'),
        metadata: {
          template_suggested: true,
          starter_template_id: templateId,
        },
      },
      {
        idSuffix: mcpConnectionSuffix,
        display_name: domain === 'jira' ? 'Atlassian MCP' : `${humanize(domain)} MCP`,
        backend_kind: 'mcp',
        system_kind: domain === 'jira' ? 'atlassian' : domain,
        endpoint_ref: endpointRefFor(domain, 'mcp'),
        auth_mode: 'external',
        identity_provider_ref: `${domain}-oauth`,
        secret_ref: secretRefFor(domain, 'mcp'),
        metadata: {
          template_suggested: true,
          starter_template_id: templateId,
        },
      },
    ],
    discoveryRecords: operations.flatMap((operation) =>
      operationRefs(operation).map((ref) => {
        const backend = backendKindForRef(ref)
        const suffix = discoverySuffix(ref, operation.capability_id)
        const required = inputNames(operation, true)
        const optional = inputNames(operation, false)
        return {
          idSuffix: suffix,
          connectionIdSuffix: backend === 'mcp' ? mcpConnectionSuffix : nativeConnectionSuffix,
          operation_id: ref,
          backend_kind: backend,
          method: methodForOperation(operation, backend),
          path_template: backend === 'mcp' ? toolNameForRef(ref) : (operation.path || `/${domain}/${toolNameForRef(ref)}`),
          side_effect_level: operation.side_effect_level || 'read',
          input_schema_summary: { required, optional },
          risk_notes: [
            backend === 'mcp'
              ? 'Template-suggested MCP operation; verify selected MCP server tool name before locking.'
              : 'Template-suggested native API operation; verify endpoint, auth, and actor-visible scope before locking.',
          ],
          data: {
            template_suggested: true,
            starter_template_id: templateId,
            capability_id: operation.capability_id,
          },
        }
      }),
    ),
    capabilityMappings: operations.map((operation) => {
      const capabilityId = String(operation.capability_id ?? '').trim()
      const required = inputNames(operation, true)
      const optional = inputNames(operation, false)
      const refs = operationRefs(operation)
      const capabilityServiceId = frontingCapabilityServiceId(domain, operation, serviceId)
      return {
        idSuffix: `mapping-${capabilityId.replace(/[^a-z0-9]+/gi, '-')}`,
        title: operation.title || humanize(capabilityId),
        data: {
          artifact_type: 'integration_fronting_capability_mapping',
          template_suggested: true,
          review_status: 'template_suggested',
          title: operation.title || humanize(capabilityId),
          capability_id: capabilityId,
          intent: operation.summary || `Governed fronting capability for ${capabilityId}.`,
          service_id: capabilityServiceId,
          service_name: humanize(capabilityServiceId) || serviceName,
          backend_kind: operation.backend_kind || starter.backend_kind || 'hybrid',
          connection_ref: nativeConnectionSuffix,
          raw_operation_refs: refs,
          backend_bindings: ['native_api', 'mcp'].map((backend) => {
            const backendRefs = refs.filter((ref) => backendKindForRef(ref) === backend)
            return {
              backend_kind: backend,
              connection_ref: backend === 'mcp' ? mcpConnectionSuffix : nativeConnectionSuffix,
              raw_operation_refs: backendRefs,
              backend_input_mode: operation.backend_input_mode || 'hybrid',
              derived_required_backend_inputs: required,
              derived_optional_backend_inputs: optional,
              explicit_required_backend_inputs: required,
              explicit_optional_backend_inputs: optional,
              matched_discovery_record_ids: backendRefs.map((ref) => discoverySuffix(ref, operation.capability_id)),
              status: backendRefs.length > 0 ? 'ready' : 'missing',
              status_detail: backendRefs.length > 0
                ? `Template-suggested ${backend === 'mcp' ? 'MCP' : 'native API'} implementation seam. Review before locking.`
                : `No ${backend === 'mcp' ? 'MCP' : 'native API'} operation was declared for this capability.`,
            }
          }),
          execution_posture: frontingExecutionPosture(operation),
          side_effect_level: operation.side_effect_level || 'read',
          subject_kind: operation.subject_kind || 'fronted_resource',
          context_type: operation.context_type || 'fronting_context',
          output_intent: operation.output_intent || 'governed_fronting_result',
          required_inputs: required,
          optional_inputs: optional,
          inputs: normalizeStarterInputs(operation.inputs),
          backend_input_mode: operation.backend_input_mode || 'hybrid',
          derived_required_backend_inputs: required,
          derived_optional_backend_inputs: optional,
          explicit_required_backend_inputs: required,
          explicit_optional_backend_inputs: optional,
          approval_rule_refs: sideEffectIsWriteLike(operation.side_effect_level) ? ['approval.write_adjacent'] : [],
          denial_rule_refs: ['deny.raw_backend_bypass'],
          clarification_rule_refs: required.map((input) => `clarify.${input}`),
          audit_required: true,
          outbound_controls: {
            redaction_required: true,
            raw_backend_not_agent_visible: true,
          },
          template_notes: [
            'Imported from an explicit starter template.',
            'Review backend operations, auth posture, and approval rules before locking or generation.',
          ],
        },
      }
    }),
  }
}

function safeIdentifier(value: string, fallback: string): string {
  const normalized = value.toLowerCase().replace(/[^a-z0-9_-]+/g, '-').replace(/^-+|-+$/g, '')
  return normalized || fallback
}

function humanize(value: string): string {
  return value
    .replace(/[_-]+/g, ' ')
    .replace(/\./g, ' ')
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

function inputNames(operation: FrontingStarterOperation, required: boolean): string[] {
  return (operation.inputs ?? [])
    .filter((input) => Boolean(input.required) === required)
    .map((input) => String(input.name ?? '').trim())
    .filter(Boolean)
}

function normalizeStarterInputs(inputs: FrontingStarterInput[] | undefined): Record<string, unknown>[] {
  return (inputs ?? [])
    .map((input) => ({
      input_name: input.name,
      input_type: input.type || 'string',
      required: Boolean(input.required),
      summary: input.summary || input.name,
      default_value: input.default_value,
      allowed_values: Array.isArray(input.allowed_values) ? input.allowed_values : [],
      semantic_type: input.semantic_type,
      validation_pattern: input.validation_pattern,
      clarification_hint: input.clarification_hint,
      entity_reference: input.entity_reference,
      catalog_ref: input.catalog_ref,
      resolution: input.resolution,
    }))
    .filter((input) => typeof input.input_name === 'string' && input.input_name.trim())
}

function normalizeStarterEvidenceInputs(inputs: FrontingStarterInput[] | undefined): Record<string, unknown>[] {
  return (inputs ?? [])
    .map((input) => {
      const resolution = isRecord(input.resolution) ? input.resolution : {}
      return {
        input_name: input.name,
        input_type: input.type || 'string',
        required: Boolean(input.required),
        semantic_type: input.semantic_type || '',
        entity_reference: Boolean(input.entity_reference),
        catalog_ref: input.catalog_ref || '',
        default_value: input.default_value || '',
        allowed_values: Array.isArray(input.allowed_values) ? input.allowed_values : [],
        resolution: {
          mode: String(resolution.mode ?? '').trim(),
          resolver_ref: String(resolution.resolver_ref ?? input.catalog_ref ?? '').trim(),
          on_missing: String(resolution.on_missing ?? '').trim(),
          on_ambiguous: String(resolution.on_ambiguous ?? '').trim(),
          on_unresolved: String(resolution.on_unresolved ?? '').trim(),
        },
      }
    })
    .filter((input) => typeof input.input_name === 'string' && input.input_name.trim())
}

function operationRefs(operation: FrontingStarterOperation): string[] {
  if (Array.isArray(operation.raw_operation_refs) && operation.raw_operation_refs.length > 0) {
    return operation.raw_operation_refs.map((ref) => String(ref).trim()).filter(Boolean)
  }
  const method = String(operation.method ?? '').trim()
  const path = String(operation.path ?? '').trim()
  return method && path ? [`${method.toLowerCase()}_${path.replace(/[^a-z0-9]+/gi, '_').replace(/^_+|_+$/g, '')}`] : []
}

function backendKindForRef(ref: string): 'native_api' | 'mcp' {
  return ref.toLowerCase().includes('.mcp.') || ref.toLowerCase().includes('mcp.') ? 'mcp' : 'native_api'
}

function discoverySuffix(ref: string, scope?: string): string {
  const scoped = scope ? `${scope}-${ref}` : ref
  return scoped.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')
}

function toolNameForRef(ref: string): string {
  return ref.split('.').pop() || discoverySuffix(ref)
}

function methodForOperation(operation: FrontingStarterOperation, backend: 'native_api' | 'mcp'): string {
  if (backend === 'mcp') return 'tool'
  const method = String(operation.method ?? '').trim().toUpperCase()
  if (method) return method
  return sideEffectIsWriteLike(operation.side_effect_level) ? 'POST' : 'GET'
}

function sideEffectIsWriteLike(sideEffect: string | undefined): boolean {
  return ['approval_required', 'write', 'write_adjacent'].includes(String(sideEffect ?? '').trim())
}

function endpointRefFor(domain: string, kind: 'native_api' | 'mcp'): string {
  if (kind === 'mcp') return domain === 'jira' ? 'ATLASSIAN_MCP_ENDPOINT' : `${domain.toUpperCase()}_MCP_ENDPOINT`
  if (domain === 'jira') return 'JIRA_BASE_URL'
  return `${domain.toUpperCase()}_API_URL`
}

function secretRefFor(domain: string, kind: 'native_api' | 'mcp'): string {
  if (kind === 'mcp') return domain === 'jira' ? 'ATLASSIAN_MCP_TOKEN' : `${domain.toUpperCase()}_MCP_TOKEN`
  if (domain === 'jira') return 'JIRA_API_TOKEN'
  return `${domain.toUpperCase()}_API_TOKEN`
}

export const STARTER_TEMPLATES: StarterTemplate[] = loadStarterTemplates(BUILT_IN_STARTER_TEMPLATE_DATA)

export function starterTemplatesForProjectType(projectType: ProjectType): StarterTemplate[] {
  return STARTER_TEMPLATES.filter((template) => template.projectType === projectType)
}

export function getStarterTemplate(templateId: string | null | undefined): StarterTemplate | null {
  if (!templateId) return null
  return STARTER_TEMPLATES.find((template) => template.id === templateId) ?? null
}

function scopedId(projectId: string, suffix: string): string {
  return `${projectId}-${suffix}`.replace(/[^A-Za-z0-9_-]/g, '-')
}

function scopedTemplateRef(
  value: unknown,
  scopedRefs: Map<string, string>,
): string {
  const ref = String(value ?? '').trim()
  return scopedRefs.get(ref) ?? ref
}

function scopeMappingData(
  projectId: string,
  template: StarterTemplate,
  mapping: StarterTemplateCapabilityMapping,
  connectionRefs: Map<string, string>,
  discoveryRefs: Map<string, string>,
): StarterTemplateCapabilityMapping {
  const data = JSON.parse(JSON.stringify(mapping.data)) as Record<string, any>
  data.id = scopedId(projectId, mapping.idSuffix)
  data.connection_ref = scopedTemplateRef(data.connection_ref, connectionRefs)
  data.starter_template_id = template.id
  data.starter_template_title = template.title

  if (Array.isArray(data.backend_bindings)) {
    data.backend_bindings = data.backend_bindings.map((binding: Record<string, any>) => ({
      ...binding,
      connection_ref: scopedTemplateRef(binding.connection_ref, connectionRefs),
      matched_discovery_record_ids: Array.isArray(binding.matched_discovery_record_ids)
        ? binding.matched_discovery_record_ids.map((id) => scopedTemplateRef(id, discoveryRefs))
        : [],
    }))
  }

  return {
    idSuffix: mapping.idSuffix,
    title: mapping.title,
    data,
  }
}

export function expandStarterTemplate(projectId: string, template: StarterTemplate): ExpandedStarterTemplate {
  const connectionRefs = new Map(template.connections.map((connection) => [
    connection.idSuffix,
    scopedId(projectId, connection.idSuffix),
  ]))
  const discoveryRefs = new Map(template.discoveryRecords.map((record) => [
    record.idSuffix,
    scopedId(projectId, record.idSuffix),
  ]))

  return {
    template,
    documents: template.documents.map((document) => ({
      ...document,
      id: scopedId(projectId, document.idSuffix),
    })),
    connections: template.connections.map((connection) => ({
      id: scopedId(projectId, connection.idSuffix),
      display_name: connection.display_name,
      backend_kind: connection.backend_kind,
      system_kind: connection.system_kind,
      endpoint_ref: connection.endpoint_ref,
      auth_mode: connection.auth_mode,
      identity_provider_ref: connection.identity_provider_ref,
      secret_ref: connection.secret_ref,
      allowed_project_refs: [projectId],
      metadata: connection.metadata,
    })),
    discoveryRecords: template.discoveryRecords.map((record) => ({
      id: scopedId(projectId, record.idSuffix),
      connection_id: scopedTemplateRef(record.connectionIdSuffix, connectionRefs),
      operation_id: record.operation_id,
      backend_kind: record.backend_kind,
      method: record.method,
      path_template: record.path_template,
      side_effect_level: record.side_effect_level,
      input_schema_summary: record.input_schema_summary,
      risk_notes: record.risk_notes,
      data: record.data,
    })),
    capabilityMappings: template.capabilityMappings.map((mapping) =>
      scopeMappingData(projectId, template, mapping, connectionRefs, discoveryRefs),
    ),
  }
}
