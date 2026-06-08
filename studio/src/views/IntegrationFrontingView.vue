<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  createIntegrationDiscoveryRecord,
  createPmArtifact,
  createWorkspaceConnection,
  deleteIntegrationDiscoveryRecord,
  deletePmArtifact,
  deleteWorkspaceConnection,
  listIntegrationDiscoveryRecords,
  listWorkspaceConnections,
  proposeGovernedFrontingCapabilitiesWithAssistant,
  updateIntegrationDiscoveryRecord,
  updatePmArtifact,
  updateWorkspaceConnection,
} from '../design/project-api'
import { requestConfirmation } from '../design/confirm'
import { loadProject, projectStore } from '../design/project-store'
import {
  INTEGRATION_FRONTING_MAPPING_ARTIFACT_TYPE,
  resolveIntegrationFrontingBackendBindingHealth,
  resolveIntegrationFrontingBackendBindingsHealth,
} from '../design/developer-definition'
import { developerLabel } from '../design/developer-vocabulary'
import type { ArtifactRecord, AssistantProposalEnvelope, AssistantProposalItem, BackendInputMode, DeveloperIntegrationFrontingBackendBinding, IntegrationAuthMode, IntegrationBackendKind, IntegrationDiscoveryRecord, IntegrationProfile, WorkspaceConnection } from '../design/project-types'

const route = useRoute()
const router = useRouter()
const projectId = computed(() => String(route.params.projectId || ''))
const project = computed(() => projectStore.activeProject?.id === projectId.value ? projectStore.activeProject : null)
const readOnly = computed(() => projectStore.runtimeStatus?.read_only_mode !== false)

const connections = ref<WorkspaceConnection[]>([])
const workspaceConnectionCount = ref(0)
const discoveryRecords = ref<IntegrationDiscoveryRecord[]>([])
const loading = ref(false)
const savingConnection = ref(false)
const savingDiscovery = ref(false)
const savingMapping = ref(false)
const deletingConnectionId = ref<string | null>(null)
const deletingDiscoveryId = ref<string | null>(null)
const deletingMappingId = ref<string | null>(null)
const frontingAssistantBusy = ref(false)
const frontingAssistantError = ref<string | null>(null)
const frontingAssistantProposal = ref<AssistantProposalEnvelope | null>(null)
const error = ref<string | null>(null)
const connectionEditorOpen = ref(false)
const discoveryEditorOpen = ref(false)
const mappingEditorOpen = ref(false)
const editingConnectionId = ref<string | null>(null)
const editingDiscoveryId = ref<string | null>(null)
const editingMappingArtifactId = ref<string | null>(null)
const expandedConnectionIds = ref<Set<string>>(new Set())
const expandedDiscoveryRecordIds = ref<Set<string>>(new Set())
const expandedMappingArtifactIds = ref<Set<string>>(new Set())
const discoveryEditorRef = ref<HTMLElement | null>(null)
const mappingEditorRef = ref<HTMLElement | null>(null)

const connectionForm = reactive({
  id: '',
  display_name: '',
  backend_kind: 'native_api' as IntegrationBackendKind,
  system_kind: '',
  endpoint_ref: '',
  auth_mode: 'service_delegated' as IntegrationAuthMode,
  identity_provider_ref: '',
  secret_ref: '',
})

const discoveryForm = reactive({
  id: '',
  connection_id: '',
  operation_id: '',
  backend_kind: 'native_api' as IntegrationBackendKind,
  method: '',
  path_template: '',
  side_effect_level: '',
  required_inputs: '',
  optional_inputs: '',
  risk_notes: '',
})

const mappingForm = reactive({
  capability_id: '',
  title: '',
  intent: '',
  service_id: '',
  service_name: '',
  execution_posture: '',
  side_effect_level: '',
  subject_kind: '',
  context_type: '',
  output_intent: '',
  required_inputs: '',
  optional_inputs: '',
  approval_rule_refs: '',
  denial_rule_refs: '',
  clarification_rule_refs: '',
  audit_required: true,
})

type MappingBackendBindingEditor = {
  client_id: string
  backend_kind: IntegrationBackendKind
  connection_ref: string
  raw_operation_refs: string
  backend_input_mode: BackendInputMode
  explicit_required_backend_inputs: string
  explicit_optional_backend_inputs: string
}

const mappingBackendBindings = ref<MappingBackendBindingEditor[]>([])

function connectionAllowedForProject(connection: WorkspaceConnection, activeProjectId: string): boolean {
  if (!activeProjectId) return false
  return connection.allowed_project_refs.length === 0 || connection.allowed_project_refs.includes(activeProjectId)
}

const activeIntegrationProfile = computed<IntegrationProfile>(() => {
  return project.value?.integration_profile ?? { kind: 'none', systems: [] }
})
const isGovernedServiceProject = computed(() => project.value?.project_type === 'governed_service_project')
const projectUnavailable = computed(() => !loading.value && !project.value && !!projectId.value)
const profileSystems = computed(() => activeIntegrationProfile.value.systems ?? [])
const projectConnectionIds = computed(() => new Set(connections.value.map((connection) => connection.id)))
const hiddenWorkspaceConnectionCount = computed(() => Math.max(0, workspaceConnectionCount.value - connections.value.length))
const profileSystemsOutsideProjectConnections = computed(() =>
  profileSystems.value.filter((system) => system.connection_ref && !projectConnectionIds.value.has(system.connection_ref)),
)

const firstConnection = computed(() => connections.value[0] ?? null)
const savedMappings = computed(() =>
  projectStore.artifacts.pmArtifacts.filter((artifact) => artifact.data?.artifact_type === INTEGRATION_FRONTING_MAPPING_ARTIFACT_TYPE),
)
const acceptedMappingCount = computed(() => savedMappings.value.length)
const savedBindingHealth = computed(() =>
  savedMappings.value.map((artifact) => {
    const data = artifact.data as Record<string, unknown>
    const bindings = Array.isArray(data.backend_bindings) && data.backend_bindings.length > 0
      ? data.backend_bindings as DeveloperIntegrationFrontingBackendBinding[]
      : [legacySavedMappingBinding(data)]
    return {
      artifactId: artifact.id,
      capabilityId: String(data.capability_id ?? artifact.title ?? ''),
      health: resolveIntegrationFrontingBackendBindingsHealth(bindings, discoveryRecords.value),
    }
  }),
)
const staleSavedBindingCount = computed(() => savedBindingHealth.value.filter((entry) => entry.health.status === 'stale').length)
const missingSavedBindingCount = computed(() => savedBindingHealth.value.filter((entry) => entry.health.status === 'missing').length)
const workflowSteps = computed(() => [
  {
    id: 'connection',
    label: '1. Reference workspace connection',
    ready: connections.value.length > 0,
    detail: 'Keep endpoint, identity-provider, and secret references at workspace scope, then allow only the relevant project refs here.',
  },
  {
    id: 'discovery',
    label: '2. Record raw backend supply',
    ready: discoveryRecords.value.length > 0,
    detail: 'Capture selected tools, endpoints, or operations as backend supply. This is not the agent-facing surface.',
  },
  {
    id: 'mapping',
    label: '3. Curate governed capabilities',
    ready: acceptedMappingCount.value > 0 && staleSavedBindingCount.value === 0 && missingSavedBindingCount.value === 0,
    detail: staleSavedBindingCount.value || missingSavedBindingCount.value
      ? `Accepted mappings exist, but ${staleSavedBindingCount.value} stale and ${missingSavedBindingCount.value} missing backend bindings need review.`
      : 'Accept the small governed ANIP capability surface that agents can actually use.',
  },
])
const readyStepCount = computed(() => workflowSteps.value.filter((step) => step.ready).length)
const canAcceptMapping = computed(() =>
  !!project.value
  && !!mappingForm.capability_id.trim()
  && !!mappingForm.service_id.trim()
  && mappingBackendBindings.value.some((binding) => binding.connection_ref.trim() && splitCsv(binding.raw_operation_refs).length > 0),
)

const frontingAssistantItems = computed<AssistantProposalItem[]>(() => {
  const proposal = frontingAssistantProposal.value?.proposal
  if (!proposal || proposal.proposal_kind !== 'candidate_blocks') return []
  return proposal.items
})

function splitCsv(value: string): string[] {
  return value.split(',').map((item) => item.trim()).filter(Boolean)
}

function createBackendBindingEditor(
  seed: Partial<MappingBackendBindingEditor> = {},
): MappingBackendBindingEditor {
  return {
    client_id: seed.client_id || crypto.randomUUID(),
    backend_kind: seed.backend_kind || firstConnection.value?.backend_kind || 'native_api',
    connection_ref: seed.connection_ref || firstConnection.value?.id || '',
    raw_operation_refs: seed.raw_operation_refs || '',
    backend_input_mode: seed.backend_input_mode || 'implicit',
    explicit_required_backend_inputs: seed.explicit_required_backend_inputs || '',
    explicit_optional_backend_inputs: seed.explicit_optional_backend_inputs || '',
  }
}

function formatList(items: unknown, emptyLabel = 'none'): string {
  if (!Array.isArray(items)) return emptyLabel
  const values = items.map((item) => String(item)).filter(Boolean)
  return values.length ? values.join(', ') : emptyLabel
}

function displayValue(value: unknown, emptyLabel = 'not set'): string {
  if (value === null || value === undefined || value === '') return emptyLabel
  if (Array.isArray(value)) return formatList(value, emptyLabel)
  return String(value)
}

function structuredList(value: unknown): string {
  return Array.isArray(value) ? value.map((item) => String(item)).filter(Boolean).join(', ') || 'none' : 'none'
}

function structuredObject(value: unknown): Record<string, any> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, any> : {}
}

function csvFromUnknown(value: unknown): string {
  return Array.isArray(value) ? value.map((item) => String(item)).filter(Boolean).join(', ') : ''
}

function normalizeBackendKind(value: unknown): IntegrationBackendKind {
  return value === 'mcp' || value === 'database' || value === 'hybrid' ? value : 'native_api'
}

function normalizeBackendInputMode(value: unknown): BackendInputMode {
  return value === 'explicit' || value === 'hybrid' ? value : 'implicit'
}

function assistantItemData(item: AssistantProposalItem): Record<string, any> {
  return structuredObject(item.structured_data)
}

function assistantItemBindings(item: AssistantProposalItem): string {
  const data = assistantItemData(item)
  const bindings = Array.isArray(data.backend_bindings) ? data.backend_bindings : []
  return bindings
    .map((binding) => {
      const entry = structuredObject(binding)
      const operations = Array.isArray(entry.raw_operation_refs) ? entry.raw_operation_refs.join(', ') : 'none'
      return `${entry.backend_kind || 'backend'}:${entry.connection_ref || 'unbound'} -> ${operations}`
    })
    .join(' | ') || 'none'
}

function assistantItemScenarios(item: AssistantProposalItem): string {
  const data = assistantItemData(item)
  const scenarios = Array.isArray(data.verification_scenarios) ? data.verification_scenarios : []
  return scenarios
    .map((scenario) => {
      const entry = structuredObject(scenario)
      return `${entry.name || 'scenario'}: ${entry.expected || 'expected behavior'}`
    })
    .join(' | ') || 'none'
}

function discoveryRequiredInputs(record: IntegrationDiscoveryRecord): string {
  return formatList(record.input_schema_summary.required)
}

function discoveryOptionalInputs(record: IntegrationDiscoveryRecord): string {
  return formatList(record.input_schema_summary.optional)
}

function backendOperationKindLabel(backendKind: IntegrationBackendKind): string {
  if (backendKind === 'mcp') return 'MCP operation'
  if (backendKind === 'database') return 'Database operation'
  if (backendKind === 'hybrid') return 'Backend operation'
  return 'HTTP method'
}

function backendOperationValueLabel(record: IntegrationDiscoveryRecord): string {
  const method = displayValue(record.method, record.backend_kind === 'mcp' ? 'MCP tool' : 'operation n/a')
  const path = record.path_template ? ` ${record.path_template}` : ''
  if (record.backend_kind === 'mcp' && record.method === 'tool') {
    return `MCP tool${path}`
  }
  return `${method}${path}`
}

function deriveBackendInputSummary(
  rawOperationRefsValue: string,
  connectionRefValue: string,
  backendKind?: IntegrationBackendKind,
) {
  const rawOperationRefs = splitCsv(rawOperationRefsValue)
  const connectionRef = connectionRefValue.trim()
  const exactMatches = discoveryRecords.value.filter((record) =>
    rawOperationRefs.includes(record.operation_id)
    && (!backendKind || record.backend_kind === backendKind)
    && (!connectionRef || !record.connection_id || record.connection_id === connectionRef),
  )
  const matches = exactMatches.length > 0
    ? exactMatches
    : discoveryRecords.value.filter((record) =>
        rawOperationRefs.includes(record.operation_id)
        && (!backendKind || record.backend_kind === backendKind),
      )

  const required = new Set<string>()
  const optional = new Set<string>()
  for (const record of matches) {
    const requiredItems = Array.isArray(record.input_schema_summary.required)
      ? record.input_schema_summary.required
      : []
    const optionalItems = Array.isArray(record.input_schema_summary.optional)
      ? record.input_schema_summary.optional
      : []
    requiredItems.forEach((item) => required.add(String(item).trim()))
    optionalItems.forEach((item) => optional.add(String(item).trim()))
  }

  return {
    required: Array.from(required).filter(Boolean),
    optional: Array.from(optional).filter((item) => item && !required.has(item)),
    matchedRecordIds: matches.map((record) => record.id),
  }
}

function bindingEditorDerivedInputs(binding: MappingBackendBindingEditor) {
  return deriveBackendInputSummary(binding.raw_operation_refs, binding.connection_ref, binding.backend_kind)
}

function mappingRequiredInputs(data: Record<string, unknown>): string {
  return formatList(data.required_inputs)
}

function mappingOptionalInputs(data: Record<string, unknown>): string {
  return formatList(data.optional_inputs)
}

function mappingBackendInputMode(data: Record<string, unknown>): BackendInputMode {
  return data.backend_input_mode === 'explicit' || data.backend_input_mode === 'hybrid'
    ? data.backend_input_mode
    : 'implicit'
}

function mappingRuleRefs(data: Record<string, unknown>): string {
  const refs = [
    ...(Array.isArray(data.approval_rule_refs) ? data.approval_rule_refs : []),
    ...(Array.isArray(data.denial_rule_refs) ? data.denial_rule_refs : []),
    ...(Array.isArray(data.clarification_rule_refs) ? data.clarification_rule_refs : []),
  ].map((item) => String(item)).filter(Boolean)
  return refs.length ? refs.join(', ') : 'none'
}

function legacySavedMappingBinding(data: Record<string, unknown>): DeveloperIntegrationFrontingBackendBinding {
  return {
    backend_kind: data.backend_kind === 'mcp' || data.backend_kind === 'database' || data.backend_kind === 'hybrid' ? data.backend_kind : 'native_api',
    connection_ref: String(data.connection_ref ?? ''),
    raw_operation_refs: Array.isArray(data.raw_operation_refs) ? data.raw_operation_refs.map((item) => String(item)) : [],
    backend_input_mode: data.backend_input_mode === 'explicit' || data.backend_input_mode === 'hybrid' ? data.backend_input_mode : 'implicit',
    derived_required_backend_inputs: Array.isArray(data.derived_required_backend_inputs) ? data.derived_required_backend_inputs.map((item) => String(item)) : [],
    derived_optional_backend_inputs: Array.isArray(data.derived_optional_backend_inputs) ? data.derived_optional_backend_inputs.map((item) => String(item)) : [],
    explicit_required_backend_inputs: Array.isArray(data.explicit_required_backend_inputs) ? data.explicit_required_backend_inputs.map((item) => String(item)) : [],
    explicit_optional_backend_inputs: Array.isArray(data.explicit_optional_backend_inputs) ? data.explicit_optional_backend_inputs.map((item) => String(item)) : [],
    matched_discovery_record_ids: Array.isArray(data.matched_discovery_record_ids) ? data.matched_discovery_record_ids.map((item) => String(item)) : [],
  }
}

function savedMappingBindings(data: Record<string, unknown>): DeveloperIntegrationFrontingBackendBinding[] {
  if (Array.isArray(data.backend_bindings) && data.backend_bindings.length > 0) {
    return data.backend_bindings as DeveloperIntegrationFrontingBackendBinding[]
  }
  return [legacySavedMappingBinding(data)]
}

function mappingBindingHealthEntries(data: Record<string, unknown>) {
  return savedMappingBindings(data).map((binding) => ({
    binding,
    health: resolveIntegrationFrontingBackendBindingHealth(binding, discoveryRecords.value),
  }))
}

function mappingBindingStatusSummary(data: Record<string, unknown>): string {
  const entries = mappingBindingHealthEntries(data)
  const stale = entries.filter((entry) => entry.health.status === 'stale').length
  const missing = entries.filter((entry) => entry.health.status === 'missing').length
  if (!entries.length) return 'no bindings'
  if (!stale && !missing) return `${entries.length} ready`
  return `${entries.length} bindings · ${stale} stale · ${missing} missing`
}

function connectionDetailsOpen(connectionId: string): boolean {
  return expandedConnectionIds.value.has(connectionId)
}

function discoveryDetailsOpen(recordId: string): boolean {
  return expandedDiscoveryRecordIds.value.has(recordId)
}

function mappingDetailsOpen(artifactId: string): boolean {
  return expandedMappingArtifactIds.value.has(artifactId)
}

function toggleDiscoveryDetails(recordId: string): void {
  const next = new Set(expandedDiscoveryRecordIds.value)
  if (next.has(recordId)) {
    next.delete(recordId)
  } else {
    next.add(recordId)
  }
  expandedDiscoveryRecordIds.value = next
}

function toggleMappingDetails(artifactId: string): void {
  const next = new Set(expandedMappingArtifactIds.value)
  if (next.has(artifactId)) {
    next.delete(artifactId)
  } else {
    next.add(artifactId)
  }
  expandedMappingArtifactIds.value = next
}

function toggleConnectionDetails(connectionId: string): void {
  const next = new Set(expandedConnectionIds.value)
  if (next.has(connectionId)) {
    next.delete(connectionId)
  } else {
    next.add(connectionId)
  }
  expandedConnectionIds.value = next
}

async function scrollToEditor(editorRef: { value: HTMLElement | null }): Promise<void> {
  await nextTick()
  editorRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function resetConnectionForm(): void {
  connectionForm.id = ''
  connectionForm.display_name = ''
  connectionForm.backend_kind = 'native_api'
  connectionForm.system_kind = ''
  connectionForm.endpoint_ref = ''
  connectionForm.auth_mode = 'service_delegated'
  connectionForm.identity_provider_ref = ''
  connectionForm.secret_ref = ''
}

function resetDiscoveryForm(): void {
  discoveryForm.id = ''
  discoveryForm.connection_id = firstConnection.value?.id ?? ''
  discoveryForm.operation_id = ''
  discoveryForm.backend_kind = firstConnection.value?.backend_kind ?? 'native_api'
  discoveryForm.method = ''
  discoveryForm.path_template = ''
  discoveryForm.side_effect_level = ''
  discoveryForm.required_inputs = ''
  discoveryForm.optional_inputs = ''
  discoveryForm.risk_notes = ''
}

function resetMappingForm(): void {
  mappingForm.capability_id = ''
  mappingForm.title = ''
  mappingForm.intent = ''
  mappingForm.service_id = ''
  mappingForm.service_name = ''
  mappingForm.execution_posture = ''
  mappingForm.side_effect_level = ''
  mappingForm.subject_kind = ''
  mappingForm.context_type = ''
  mappingForm.output_intent = ''
  mappingForm.required_inputs = ''
  mappingForm.optional_inputs = ''
  mappingForm.approval_rule_refs = ''
  mappingForm.denial_rule_refs = ''
  mappingForm.clarification_rule_refs = ''
  mappingForm.audit_required = true
  mappingBackendBindings.value = [createBackendBindingEditor()]
}

function openAdditionalBackendBinding(): void {
  mappingBackendBindings.value = [...mappingBackendBindings.value, createBackendBindingEditor()]
}

function removeBackendBinding(clientId: string): void {
  if (mappingBackendBindings.value.length <= 1) return
  mappingBackendBindings.value = mappingBackendBindings.value.filter((binding) => binding.client_id !== clientId)
}

function bindingSummaryLabel(binding: MappingBackendBindingEditor | DeveloperIntegrationFrontingBackendBinding): string {
  const operations = Array.isArray(binding.raw_operation_refs)
    ? binding.raw_operation_refs
    : splitCsv(binding.raw_operation_refs)
  return `${binding.backend_kind}:${binding.connection_ref || 'unbound'} -> ${operations.join(', ') || 'none'}`
}

function openNewConnectionForm(): void {
  resetConnectionForm()
  editingConnectionId.value = null
  connectionEditorOpen.value = true
}

function openEditConnectionForm(connection: WorkspaceConnection): void {
  useConnection(connection)
  editingConnectionId.value = connection.id
  connectionEditorOpen.value = true
}

function closeConnectionEditor(): void {
  connectionEditorOpen.value = false
  editingConnectionId.value = null
  resetConnectionForm()
}

function openNewDiscoveryForm(): void {
  resetDiscoveryForm()
  editingDiscoveryId.value = null
  discoveryEditorOpen.value = true
  void scrollToEditor(discoveryEditorRef)
}

function openEditDiscoveryForm(record: IntegrationDiscoveryRecord): void {
  discoveryForm.id = record.id
  discoveryForm.connection_id = record.connection_id ?? ''
  discoveryForm.operation_id = record.operation_id
  discoveryForm.backend_kind = record.backend_kind
  discoveryForm.method = record.method ?? ''
  discoveryForm.path_template = record.path_template ?? ''
  discoveryForm.side_effect_level = record.side_effect_level
  discoveryForm.required_inputs = Array.isArray(record.input_schema_summary.required)
    ? record.input_schema_summary.required.join(', ')
    : ''
  discoveryForm.optional_inputs = Array.isArray(record.input_schema_summary.optional)
    ? record.input_schema_summary.optional.join(', ')
    : ''
  discoveryForm.risk_notes = record.risk_notes.join('\n')
  editingDiscoveryId.value = record.id
  discoveryEditorOpen.value = true
  mappingEditorOpen.value = false
  void scrollToEditor(discoveryEditorRef)
}

function closeDiscoveryEditor(): void {
  discoveryEditorOpen.value = false
  editingDiscoveryId.value = null
  resetDiscoveryForm()
}

function openNewMappingForm(): void {
  resetMappingForm()
  editingMappingArtifactId.value = null
  mappingEditorOpen.value = true
  void scrollToEditor(mappingEditorRef)
}

function useAssistantCandidate(item: AssistantProposalItem): void {
  const data = assistantItemData(item)
  mappingForm.capability_id = String(data.capability_id || '')
  mappingForm.title = String(data.title || item.title || '')
  mappingForm.intent = String(data.intent || item.body || '')
  mappingForm.service_id = String(data.service_id || '')
  mappingForm.service_name = String(data.service_name || '')
  mappingForm.execution_posture = String(data.execution_posture || '')
  mappingForm.side_effect_level = String(data.side_effect_level || '')
  mappingForm.subject_kind = String(data.subject_kind || '')
  mappingForm.context_type = String(data.context_type || '')
  mappingForm.output_intent = String(data.output_intent || '')
  mappingForm.required_inputs = csvFromUnknown(data.required_inputs)
  mappingForm.optional_inputs = csvFromUnknown(data.optional_inputs)
  mappingForm.approval_rule_refs = csvFromUnknown(data.approval_rule_refs)
  mappingForm.denial_rule_refs = csvFromUnknown(data.denial_rule_refs)
  mappingForm.clarification_rule_refs = csvFromUnknown(data.clarification_rule_refs)
  mappingForm.audit_required = data.audit_required !== false
  const backendBindings = Array.isArray(data.backend_bindings) && data.backend_bindings.length > 0
    ? data.backend_bindings
    : []
  mappingBackendBindings.value = backendBindings.length
    ? backendBindings.map((binding) => {
        const entry = structuredObject(binding)
        return createBackendBindingEditor({
          backend_kind: normalizeBackendKind(entry.backend_kind),
          connection_ref: String(entry.connection_ref || ''),
          raw_operation_refs: csvFromUnknown(entry.raw_operation_refs),
          backend_input_mode: normalizeBackendInputMode(entry.backend_input_mode),
          explicit_required_backend_inputs: csvFromUnknown(entry.explicit_required_backend_inputs),
          explicit_optional_backend_inputs: csvFromUnknown(entry.explicit_optional_backend_inputs),
        })
      })
    : [createBackendBindingEditor()]
  editingMappingArtifactId.value = null
  discoveryEditorOpen.value = false
  mappingEditorOpen.value = true
  void scrollToEditor(mappingEditorRef)
}

function openEditMappingForm(artifact: ArtifactRecord): void {
  const data = artifact.data
  mappingForm.capability_id = String(data.capability_id ?? '')
  mappingForm.title = String(data.title ?? artifact.title ?? '')
  mappingForm.intent = String(data.intent ?? '')
  mappingForm.service_id = String(data.service_id ?? '')
  mappingForm.service_name = String(data.service_name ?? '')
  mappingForm.execution_posture = String(data.execution_posture ?? '')
  mappingForm.side_effect_level = String(data.side_effect_level ?? '')
  mappingForm.subject_kind = String(data.subject_kind ?? '')
  mappingForm.context_type = String(data.context_type ?? '')
  mappingForm.output_intent = String(data.output_intent ?? '')
  mappingForm.required_inputs = Array.isArray(data.required_inputs) ? data.required_inputs.join(', ') : ''
  mappingForm.optional_inputs = Array.isArray(data.optional_inputs) ? data.optional_inputs.join(', ') : ''
  mappingForm.approval_rule_refs = Array.isArray(data.approval_rule_refs) ? data.approval_rule_refs.join(', ') : ''
  mappingForm.denial_rule_refs = Array.isArray(data.denial_rule_refs) ? data.denial_rule_refs.join(', ') : ''
  mappingForm.clarification_rule_refs = Array.isArray(data.clarification_rule_refs) ? data.clarification_rule_refs.join(', ') : ''
  mappingForm.audit_required = data.audit_required !== false
  const backendBindings = Array.isArray(data.backend_bindings) && data.backend_bindings.length > 0
    ? data.backend_bindings as Array<Record<string, unknown>>
    : [{
        backend_kind: data.backend_kind,
        connection_ref: data.connection_ref,
        raw_operation_refs: data.raw_operation_refs,
        backend_input_mode: data.backend_input_mode,
        explicit_required_backend_inputs: data.explicit_required_backend_inputs,
        explicit_optional_backend_inputs: data.explicit_optional_backend_inputs,
      }]
  mappingBackendBindings.value = backendBindings.map((binding) => createBackendBindingEditor({
    backend_kind: normalizeBackendKind(binding.backend_kind),
    connection_ref: String(binding.connection_ref ?? ''),
    raw_operation_refs: Array.isArray(binding.raw_operation_refs) ? binding.raw_operation_refs.join(', ') : '',
    backend_input_mode: normalizeBackendInputMode(binding.backend_input_mode),
    explicit_required_backend_inputs: Array.isArray(binding.explicit_required_backend_inputs) ? binding.explicit_required_backend_inputs.join(', ') : '',
    explicit_optional_backend_inputs: Array.isArray(binding.explicit_optional_backend_inputs) ? binding.explicit_optional_backend_inputs.join(', ') : '',
  }))
  editingMappingArtifactId.value = artifact.id
  mappingEditorOpen.value = true
  void scrollToEditor(mappingEditorRef)
}

function closeMappingEditor(): void {
  mappingEditorOpen.value = false
  editingMappingArtifactId.value = null
  resetMappingForm()
}

function summarizeMappingBindings(data: Record<string, unknown>): string {
  const bindings = Array.isArray(data.backend_bindings) && data.backend_bindings.length > 0
    ? data.backend_bindings
    : [{
      backend_kind: data.backend_kind,
      connection_ref: data.connection_ref,
      raw_operation_refs: data.raw_operation_refs,
    }]
  return bindings
    .map((binding) => {
      const item = typeof binding === 'object' && binding ? binding as Record<string, unknown> : {}
      return bindingSummaryLabel({
        client_id: crypto.randomUUID(),
        backend_kind: item.backend_kind === 'mcp' || item.backend_kind === 'database' || item.backend_kind === 'hybrid' ? item.backend_kind : 'native_api',
        connection_ref: String(item.connection_ref || ''),
        raw_operation_refs: Array.isArray(item.raw_operation_refs) ? item.raw_operation_refs.join(', ') : '',
        backend_input_mode: item.backend_input_mode === 'explicit' || item.backend_input_mode === 'hybrid' ? item.backend_input_mode : 'implicit',
        explicit_required_backend_inputs: '',
        explicit_optional_backend_inputs: '',
      })
    })
    .join(' | ')
}

function useConnection(connection: WorkspaceConnection): void {
  connectionForm.id = connection.id
  connectionForm.display_name = connection.display_name
  connectionForm.backend_kind = connection.backend_kind
  connectionForm.system_kind = connection.system_kind
  connectionForm.endpoint_ref = connection.endpoint_ref
  connectionForm.auth_mode = connection.auth_mode
  connectionForm.identity_provider_ref = connection.identity_provider_ref ?? ''
  connectionForm.secret_ref = connection.secret_ref ?? ''
  discoveryForm.connection_id = connection.id
  if (mappingBackendBindings.value.length === 0) {
    mappingBackendBindings.value = [createBackendBindingEditor({ connection_ref: connection.id, backend_kind: connection.backend_kind })]
  } else {
    mappingBackendBindings.value[0].connection_ref = connection.id
    mappingBackendBindings.value[0].backend_kind = connection.backend_kind
  }
}

function useDiscoveryRecord(record: IntegrationDiscoveryRecord): void {
  discoveryForm.id = record.id
  discoveryForm.connection_id = record.connection_id ?? ''
  discoveryForm.operation_id = record.operation_id
  discoveryForm.backend_kind = record.backend_kind
  discoveryForm.method = record.method ?? ''
  discoveryForm.path_template = record.path_template ?? ''
  discoveryForm.side_effect_level = record.side_effect_level
  discoveryForm.required_inputs = Array.isArray(record.input_schema_summary.required)
    ? record.input_schema_summary.required.join(', ')
    : ''
  discoveryForm.optional_inputs = Array.isArray(record.input_schema_summary.optional)
    ? record.input_schema_summary.optional.join(', ')
    : ''
  discoveryForm.risk_notes = record.risk_notes.join('\n')
  mappingForm.side_effect_level = record.side_effect_level === 'write' ? 'write_adjacent' : record.side_effect_level
  if (mappingBackendBindings.value.length === 0) {
    mappingBackendBindings.value = [createBackendBindingEditor()]
  }
  mappingBackendBindings.value[0].connection_ref = record.connection_id ?? mappingBackendBindings.value[0].connection_ref
  mappingBackendBindings.value[0].raw_operation_refs = record.operation_id
  mappingBackendBindings.value[0].backend_kind = record.backend_kind
  if (!mappingBackendBindings.value[0].explicit_required_backend_inputs.trim() && !mappingBackendBindings.value[0].explicit_optional_backend_inputs.trim()) {
    mappingBackendBindings.value[0].backend_input_mode = 'implicit'
  }
  editingMappingArtifactId.value = null
  discoveryEditorOpen.value = false
  mappingEditorOpen.value = true
  void scrollToEditor(mappingEditorRef)
}

function frontingAssistantSourceText(): string {
  const projectSummary = [
    `Project: ${project.value?.name || project.value?.id || projectId.value}`,
    `Domain: ${project.value?.domain || 'not set'}`,
    `Summary: ${project.value?.summary || 'not set'}`,
    `Fronting model: backend supply is implementation evidence; governed ANIP capabilities are the contract surface.`,
  ].join('\n')
  const connectionSummary = connections.value.map((connection) =>
    `Connection ${connection.id}: ${connection.backend_kind}, system=${connection.system_kind || 'not set'}, auth=${connection.auth_mode}`,
  ).join('\n')
  const operationSummary = discoveryRecords.value.map((record) =>
    `Operation ${record.operation_id}: backend=${record.backend_kind}, method=${record.method || 'n/a'}, path=${record.path_template || 'n/a'}, side_effect=${record.side_effect_level}, required=${discoveryRequiredInputs(record)}, optional=${discoveryOptionalInputs(record)}`,
  ).join('\n')
  const mappingSummary = savedMappings.value.map((artifact) =>
    `Accepted mapping ${artifact.data.capability_id || artifact.title}: ${summarizeMappingBindings(artifact.data)}`,
  ).join('\n')
  return [
    projectSummary,
    'Connections:',
    connectionSummary || 'none',
    'Raw backend operations:',
    operationSummary || 'none',
    'Accepted governed mappings:',
    mappingSummary || 'none',
  ].join('\n\n')
}

async function askFrontingAssistant(): Promise<void> {
  if (!project.value || frontingAssistantBusy.value) return
  frontingAssistantBusy.value = true
  frontingAssistantError.value = null
  try {
    frontingAssistantProposal.value = await proposeGovernedFrontingCapabilitiesWithAssistant(
      project.value.id,
      frontingAssistantSourceText(),
    )
  } catch (err: any) {
    frontingAssistantError.value = err?.message || String(err)
  } finally {
    frontingAssistantBusy.value = false
  }
}

async function refresh(): Promise<void> {
  if (!projectId.value) return
  loading.value = true
  error.value = null
  try {
    await loadProject(projectId.value)
    if (project.value?.workspace_id) {
      const workspaceConnections = await listWorkspaceConnections(project.value.workspace_id)
      workspaceConnectionCount.value = workspaceConnections.length
      connections.value = workspaceConnections.filter((connection) =>
        connectionAllowedForProject(connection, project.value?.id ?? ''),
      )
    }
    discoveryRecords.value = await listIntegrationDiscoveryRecords(projectId.value)
  } catch (err: any) {
    error.value = err?.message || String(err)
  } finally {
    loading.value = false
  }
}

watch(
  () => [project.value?.id, project.value?.project_type] as const,
  ([activeProjectId, projectType]) => {
    if (!activeProjectId || projectType === 'governed_service_project') return
    router.replace(`/design/projects/${activeProjectId}/developer`)
  },
  { immediate: true },
)

async function saveConnection(): Promise<void> {
  if (!project.value || savingConnection.value) return
  savingConnection.value = true
  error.value = null
  try {
    const payload = {
      display_name: connectionForm.display_name.trim(),
      backend_kind: connectionForm.backend_kind,
      system_kind: connectionForm.system_kind.trim(),
      endpoint_ref: connectionForm.endpoint_ref.trim(),
      auth_mode: connectionForm.auth_mode,
      identity_provider_ref: connectionForm.identity_provider_ref.trim(),
      secret_ref: connectionForm.secret_ref.trim(),
      allowed_project_refs: [project.value.id],
      metadata: {},
    }
    if (editingConnectionId.value) {
      await updateWorkspaceConnection(project.value.workspace_id, editingConnectionId.value, payload)
    } else {
      await createWorkspaceConnection(project.value.workspace_id, {
        id: connectionForm.id.trim(),
        ...payload,
      })
    }
    discoveryForm.connection_id = connectionForm.id.trim()
    closeConnectionEditor()
    await refresh()
  } catch (err: any) {
    error.value = err?.message || String(err)
  } finally {
    savingConnection.value = false
  }
}

async function removeConnection(connection: WorkspaceConnection): Promise<void> {
  if (!project.value || deletingConnectionId.value) return
  const confirmed = await requestConfirmation({
    title: 'Delete workspace connection?',
    message: `Delete connection "${connection.display_name || connection.id}"? Existing project mappings may still reference this connection ID until you update them.`,
    confirmLabel: 'Delete Connection',
    tone: 'danger',
  })
  if (!confirmed) return
  deletingConnectionId.value = connection.id
  error.value = null
  try {
    await deleteWorkspaceConnection(project.value.workspace_id, connection.id)
    await refresh()
  } catch (err: any) {
    error.value = err?.message || String(err)
  } finally {
    deletingConnectionId.value = null
  }
}

async function saveDiscoveryRecord(): Promise<void> {
  if (!project.value || savingDiscovery.value) return
  savingDiscovery.value = true
  error.value = null
  try {
    const required = splitCsv(discoveryForm.required_inputs)
    const optional = splitCsv(discoveryForm.optional_inputs)
    const riskNotes = discoveryForm.risk_notes.split('\n').map((item) => item.trim()).filter(Boolean)
    const payload = {
      connection_id: discoveryForm.connection_id.trim() || null,
      operation_id: discoveryForm.operation_id.trim(),
      backend_kind: discoveryForm.backend_kind,
      method: discoveryForm.method.trim(),
      path_template: discoveryForm.path_template.trim(),
      side_effect_level: discoveryForm.side_effect_level.trim(),
      input_schema_summary: { required, optional },
      risk_notes: riskNotes,
      data: {},
    }
    if (editingDiscoveryId.value) {
      await updateIntegrationDiscoveryRecord(project.value.id, editingDiscoveryId.value, payload)
    } else {
      await createIntegrationDiscoveryRecord(project.value.id, {
        id: discoveryForm.id.trim(),
        ...payload,
      })
    }
    closeDiscoveryEditor()
    await refresh()
  } catch (err: any) {
    error.value = err?.message || String(err)
  } finally {
    savingDiscovery.value = false
  }
}

async function removeDiscoveryRecord(record: IntegrationDiscoveryRecord): Promise<void> {
  if (!project.value || deletingDiscoveryId.value) return
  const confirmed = await requestConfirmation({
    title: 'Delete raw operation metadata?',
    message: `Delete raw operation "${record.operation_id}"? Governed mappings may still reference this operation until you update them.`,
    confirmLabel: 'Delete Raw Operation',
    tone: 'danger',
  })
  if (!confirmed) return
  deletingDiscoveryId.value = record.id
  error.value = null
  try {
    await deleteIntegrationDiscoveryRecord(project.value.id, record.id)
    await refresh()
  } catch (err: any) {
    error.value = err?.message || String(err)
  } finally {
    deletingDiscoveryId.value = null
  }
}

async function saveGovernedMapping(): Promise<void> {
  if (!project.value || savingMapping.value) return
  savingMapping.value = true
  error.value = null
  try {
    const id = editingMappingArtifactId.value || `integration-fronting-mapping-${crypto.randomUUID()}`
    const existing = savedMappings.value.find((artifact) => artifact.id === editingMappingArtifactId.value)
    const nextBackendBindings = mappingBackendBindings.value
      .map((binding) => {
        const derived = bindingEditorDerivedInputs(binding)
        return {
          backend_kind: binding.backend_kind,
          connection_ref: binding.connection_ref.trim(),
          raw_operation_refs: splitCsv(binding.raw_operation_refs),
          backend_input_mode: binding.backend_input_mode,
          derived_required_backend_inputs: derived.required,
          derived_optional_backend_inputs: derived.optional,
          explicit_required_backend_inputs: splitCsv(binding.explicit_required_backend_inputs),
          explicit_optional_backend_inputs: splitCsv(binding.explicit_optional_backend_inputs),
          matched_discovery_record_ids: derived.matchedRecordIds,
        }
      })
      .filter((binding) => binding.connection_ref || binding.raw_operation_refs.length > 0)
    if (nextBackendBindings.length === 0) {
      error.value = 'Add at least one backend binding before accepting a mapping.'
      return
    }
    const primaryBinding = nextBackendBindings[0]
    const aggregateDerivedRequired = Array.from(new Set(nextBackendBindings.flatMap((binding) => binding.derived_required_backend_inputs)))
    const aggregateDerivedOptional = Array.from(new Set(nextBackendBindings.flatMap((binding) => binding.derived_optional_backend_inputs)))
      .filter((item) => !aggregateDerivedRequired.includes(item))
    const aggregateExplicitRequired = Array.from(new Set(nextBackendBindings.flatMap((binding) => binding.explicit_required_backend_inputs)))
    const aggregateExplicitOptional = Array.from(new Set(nextBackendBindings.flatMap((binding) => binding.explicit_optional_backend_inputs)))
      .filter((item) => !aggregateExplicitRequired.includes(item))
    const data = {
      ...(existing?.data ?? {}),
      artifact_type: INTEGRATION_FRONTING_MAPPING_ARTIFACT_TYPE,
      title: mappingForm.title.trim() || mappingForm.capability_id.trim(),
      id,
      capability_id: mappingForm.capability_id.trim(),
      intent: mappingForm.intent.trim(),
      service_id: mappingForm.service_id.trim(),
      service_name: mappingForm.service_name.trim(),
      backend_kind: primaryBinding.backend_kind,
      connection_ref: primaryBinding.connection_ref,
      raw_operation_refs: primaryBinding.raw_operation_refs,
      backend_bindings: nextBackendBindings,
      execution_posture: mappingForm.execution_posture.trim(),
      side_effect_level: mappingForm.side_effect_level.trim(),
      subject_kind: mappingForm.subject_kind.trim(),
      context_type: mappingForm.context_type.trim(),
      output_intent: mappingForm.output_intent.trim(),
      required_inputs: splitCsv(mappingForm.required_inputs),
      optional_inputs: splitCsv(mappingForm.optional_inputs),
      backend_input_mode: primaryBinding.backend_input_mode,
      derived_required_backend_inputs: aggregateDerivedRequired,
      derived_optional_backend_inputs: aggregateDerivedOptional,
      explicit_required_backend_inputs: aggregateExplicitRequired,
      explicit_optional_backend_inputs: aggregateExplicitOptional,
      approval_rule_refs: splitCsv(mappingForm.approval_rule_refs),
      denial_rule_refs: splitCsv(mappingForm.denial_rule_refs),
      clarification_rule_refs: splitCsv(mappingForm.clarification_rule_refs),
      audit_required: mappingForm.audit_required,
    }
    if (existing) {
      await updatePmArtifact(project.value.id, existing.id, {
        title: data.title,
        data,
      })
    } else {
      await createPmArtifact(project.value.id, {
        id,
        title: data.title,
        data,
      })
    }
    closeMappingEditor()
    await refresh()
  } catch (err: any) {
    error.value = err?.message || String(err)
  } finally {
    savingMapping.value = false
  }
}

async function removeGovernedMapping(artifact: ArtifactRecord): Promise<void> {
  if (!project.value || deletingMappingId.value) return
  const confirmed = await requestConfirmation({
    title: 'Delete governed mapping?',
    message: `Delete mapping "${artifact.data.capability_id || artifact.title}"? Developer Definition coverage will no longer have this integration-fronting target.`,
    confirmLabel: 'Delete Mapping',
    tone: 'danger',
  })
  if (!confirmed) return
  deletingMappingId.value = artifact.id
  error.value = null
  try {
    await deletePmArtifact(project.value.id, artifact.id)
    await refresh()
  } catch (err: any) {
    error.value = err?.message || String(err)
  } finally {
    deletingMappingId.value = null
  }
}

function openDeveloperDefinition(): void {
  if (!project.value) return
  router.push(`/design/projects/${project.value.id}/developer/definition`)
}

onMounted(refresh)
</script>

<template>
  <div class="integration-fronting">
    <header class="hero">
      <div>
        <div class="hero-kicker">Developer Design</div>
        <h1>Govern API / MCP</h1>
        <p>
          Put ANIP in front of an existing API, MCP server, database, or hybrid backend.
          Raw tools and endpoints are implementation supply; governed ANIP capabilities are the reviewed agent-facing contract.
        </p>
      </div>
      <button class="btn btn-secondary" @click="refresh" :disabled="loading">Refresh</button>
    </header>

    <section v-if="project && isGovernedServiceProject" class="principle-strip">
      <div>
        <strong>MCP gives access.</strong>
        <span>Useful when a tool server already exists, but not the governance boundary.</span>
      </div>
      <div>
        <strong>Native APIs expose endpoints.</strong>
        <span>Often simpler when ANIP can govern the backend directly.</span>
      </div>
      <div>
        <strong>ANIP defines allowed use.</strong>
        <span>Capabilities, approvals, denial, clarification, outbound controls, and audit live here.</span>
      </div>
    </section>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="readOnly" class="notice">Read-only mode is enabled. You can inspect this project, but cannot save governed fronting metadata.</p>

    <section v-if="projectUnavailable" class="panel not-applicable-panel">
      <h2>Project could not be loaded</h2>
      <p class="panel-copy">
        Studio could not load this project ID, so there is no integration profile, raw operation metadata, or governed mapping data to show.
        Return to the workspace list and open an existing project.
      </p>
      <button class="btn btn-secondary" type="button" @click="router.push('/design')">
        Open Workspaces
      </button>
    </section>

    <section v-if="project && !isGovernedServiceProject" class="panel not-applicable-panel">
      <h2>Govern API / MCP is not enabled for this project</h2>
      <p class="panel-copy">
        This is a standard Studio project. Use Govern API / MCP when the goal is to place ANIP in front of existing native APIs, MCP servers, databases, or hybrid backends and expose only curated governed capabilities.
      </p>
      <button class="btn btn-secondary" type="button" @click="router.push(`/design/projects/${project.id}/developer`)">
        Back to Developer Overview
      </button>
    </section>

    <section v-if="project && isGovernedServiceProject" class="grid">
      <article class="panel panel-wide workflow-panel">
        <div class="panel-header">
          <div>
            <h2>Governed Fronting Workflow</h2>
            <p class="panel-copy">
              Complete these steps before exporting a Service Definition or package. Studio keeps raw backend operations separate from the governed ANIP contract so backend shape can change without changing agent-facing behavior.
            </p>
          </div>
          <span>{{ readyStepCount }} / {{ workflowSteps.length }} ready</span>
        </div>
        <div class="workflow-steps">
          <div v-for="step in workflowSteps" :key="step.id" class="workflow-step" :class="{ ready: step.ready }">
            <div class="workflow-step-heading">
              <strong>{{ step.label }}</strong>
              <span>{{ step.ready ? 'Ready' : 'Open' }}</span>
            </div>
            <p>{{ step.detail }}</p>
          </div>
        </div>
        <div v-if="acceptedMappingCount" class="next-action-row">
          <div>
            <strong>{{ staleSavedBindingCount || missingSavedBindingCount ? 'Bindings need review' : 'Mapping accepted' }}</strong>
            <p>
              {{
                staleSavedBindingCount || missingSavedBindingCount
                  ? `Review ${staleSavedBindingCount} stale and ${missingSavedBindingCount} missing backend bindings before treating the saved mappings as generation-ready.`
                  : 'Save Developer Definition next, then generate from the saved contract to emit adapter bindings, adapter scaffold, and conformance report.'
              }}
            </p>
          </div>
          <button class="btn btn-secondary" @click="staleSavedBindingCount || missingSavedBindingCount ? router.push(`/design/projects/${project.id}/developer/integration-fronting#accepted-mappings`) : openDeveloperDefinition()">
            {{ staleSavedBindingCount || missingSavedBindingCount ? 'Review Bindings' : 'Open Developer Definition' }}
          </button>
        </div>
      </article>

      <article class="panel panel-wide assistant-panel">
        <div class="panel-header">
          <div>
            <h2>Assistant Proposal</h2>
            <p class="panel-copy">
              Ask Studio to draft governed ANIP capability candidates from the raw backend supply. This does not save mappings; it gives you reviewable candidates to copy into the governed contract form below.
            </p>
          </div>
          <button class="btn btn-secondary" type="button" :disabled="readOnly || frontingAssistantBusy" @click="askFrontingAssistant">
            {{ frontingAssistantBusy ? 'Drafting...' : 'Propose Governed Capabilities' }}
          </button>
        </div>
        <p v-if="frontingAssistantError" class="error">{{ frontingAssistantError }}</p>
        <div v-if="frontingAssistantProposal" class="assistant-result">
          <div class="assistant-result-heading">
            <div>
              <strong>{{ frontingAssistantProposal.title }}</strong>
              <p>{{ frontingAssistantProposal.summary }}</p>
            </div>
            <span>{{ frontingAssistantItems.length }} candidates</span>
          </div>
          <div v-if="frontingAssistantProposal.questions_for_user.length" class="assistant-note-grid">
            <div>
              <span>Decisions to review</span>
              <p v-for="question in frontingAssistantProposal.questions_for_user" :key="question">{{ question }}</p>
            </div>
            <div>
              <span>Guardrails</span>
              <p v-for="watchout in frontingAssistantProposal.watchouts" :key="watchout">{{ watchout }}</p>
            </div>
          </div>
          <div class="record-list assistant-candidate-list">
            <div v-for="item in frontingAssistantItems" :key="item.client_id" class="record-card assistant-candidate-card">
              <div class="record-card-heading">
                <div>
                  <strong>{{ assistantItemData(item).capability_id || item.title }}</strong>
                  <span>{{ item.title }} · {{ item.confidence }} confidence</span>
                </div>
              </div>
              <p class="detail-copy">{{ item.body }}</p>
              <div class="compact-meta-grid">
                <div>
                  <span>Backend bindings</span>
                  <strong>{{ assistantItemBindings(item) }}</strong>
                </div>
                <div>
                  <span>Required context</span>
                  <strong>{{ structuredList(assistantItemData(item).required_inputs) }}</strong>
                </div>
                <div>
                  <span>Optional context</span>
                  <strong>{{ structuredList(assistantItemData(item).optional_inputs) }}</strong>
                </div>
                <div>
                  <span>Posture</span>
                  <strong>{{ assistantItemData(item).execution_posture || 'not set' }} · {{ assistantItemData(item).side_effect_level || 'not set' }}</strong>
                </div>
                <div>
                  <span>Policy refs</span>
                  <strong>
                    {{ structuredList([...(assistantItemData(item).approval_rule_refs || []), ...(assistantItemData(item).denial_rule_refs || []), ...(assistantItemData(item).clarification_rule_refs || [])]) }}
                  </strong>
                </div>
                <div>
                  <span>Verification</span>
                  <strong>{{ assistantItemScenarios(item) }}</strong>
                </div>
              </div>
              <div class="candidate-actions">
                <button class="btn btn-primary" type="button" :disabled="readOnly" @click="useAssistantCandidate(item)">
                  Use Candidate
                </button>
                <p class="field-hint">Prefills the editor only. The mapping is not saved until you review and click Accept Mapping.</p>
              </div>
            </div>
          </div>
        </div>
        <p v-else class="empty-copy">
          No assistant proposal has been generated for this fronting project yet.
        </p>
      </article>

      <article class="panel">
        <div class="panel-header">
          <h2>Workspace Connection</h2>
          <button class="btn btn-secondary" type="button" :disabled="readOnly" @click="openNewConnectionForm">Add Connection</button>
        </div>
        <p class="panel-copy">
          Connections are workspace-scoped, but this page shows only connections allowed for this project. Store secret refs here, not tokens. Project exports and packages should only carry connection references and non-secret expectations.
        </p>
        <p v-if="hiddenWorkspaceConnectionCount" class="hint-copy">
          {{ hiddenWorkspaceConnectionCount }} other workspace connection{{ hiddenWorkspaceConnectionCount === 1 ? '' : 's' }} hidden because they are not allowed for this project.
        </p>
        <p v-if="profileSystemsOutsideProjectConnections.length" class="notice">
          {{ profileSystemsOutsideProjectConnections.length }} integration profile system{{ profileSystemsOutsideProjectConnections.length === 1 ? '' : 's' }} reference a connection that is not allowed for this project. Edit the profile or connection scope before generation.
        </p>

        <div v-if="connections.length" class="record-list compact-list">
          <div v-for="connection in connections" :key="connection.id" class="record-card">
            <div class="record-card-heading">
              <div>
                <strong>{{ connection.display_name || connection.id }}</strong>
                <span>{{ connection.backend_kind }} · {{ connection.system_kind || 'system n/a' }} · {{ connection.auth_mode }}</span>
              </div>
              <button class="details-toggle" type="button" @click="toggleConnectionDetails(connection.id)">
                {{ connectionDetailsOpen(connection.id) ? 'Hide details' : 'Show details' }}
              </button>
            </div>
            <div class="compact-meta-grid">
              <div>
                <span>Connection ref</span>
                <strong>{{ connection.id }}</strong>
              </div>
              <div>
                <span>Endpoint ref</span>
                <strong>{{ displayValue(connection.endpoint_ref) }}</strong>
              </div>
              <div>
                <span>Secret ref</span>
                <strong>{{ displayValue(connection.secret_ref) }}</strong>
              </div>
            </div>
            <div v-if="connectionDetailsOpen(connection.id)" class="details-panel">
              <div class="compact-meta-grid detail-meta-grid">
                <div>
                  <span>Name</span>
                  <strong>{{ displayValue(connection.display_name) }}</strong>
                </div>
                <div>
                  <span>Backend</span>
                  <strong>{{ connection.backend_kind }}</strong>
                </div>
                <div>
                  <span>System</span>
                  <strong>{{ displayValue(connection.system_kind) }}</strong>
                </div>
                <div>
                  <span>Auth mode</span>
                  <strong>{{ connection.auth_mode }}</strong>
                </div>
                <div>
                  <span>Identity provider</span>
                  <strong>{{ displayValue(connection.identity_provider_ref) }}</strong>
                </div>
                <div>
                  <span>Allowed projects</span>
                  <strong>{{ formatList(connection.allowed_project_refs) }}</strong>
                </div>
              </div>
              <pre v-if="Object.keys(connection.metadata || {}).length">{{ JSON.stringify(connection.metadata, null, 2) }}</pre>
            </div>
            <div class="record-actions">
              <button class="inline-action" type="button" :disabled="readOnly" @click="useConnection(connection)">Use</button>
              <button class="inline-action" type="button" :disabled="readOnly" @click="openEditConnectionForm(connection)">Edit</button>
              <button
                class="inline-action danger-link"
                type="button"
                :disabled="readOnly || deletingConnectionId === connection.id"
                @click="removeConnection(connection)"
              >
                {{ deletingConnectionId === connection.id ? 'Deleting...' : 'Delete' }}
              </button>
            </div>
          </div>
        </div>
        <p v-else class="empty-copy">No workspace connections have been saved yet.</p>

        <div v-if="connectionEditorOpen" class="editor-shell">
          <h3>{{ editingConnectionId ? 'Edit Workspace Connection' : 'Add Workspace Connection' }}</h3>
          <div class="form-grid">
            <label><span>ID</span><input v-model="connectionForm.id" :disabled="!!editingConnectionId" /></label>
            <label><span>Name</span><input v-model="connectionForm.display_name" /></label>
            <label><span>Backend</span><select v-model="connectionForm.backend_kind"><option>native_api</option><option>mcp</option><option>database</option><option>hybrid</option></select></label>
            <label><span>System</span><input v-model="connectionForm.system_kind" /></label>
            <label><span>Endpoint Ref</span><input v-model="connectionForm.endpoint_ref" /></label>
            <label><span>Auth Mode</span><select v-model="connectionForm.auth_mode"><option>service_delegated</option><option>user_delegated</option><option>external</option></select></label>
            <label><span>Identity Provider Ref</span><input v-model="connectionForm.identity_provider_ref" /></label>
            <label><span>Secret Ref</span><input v-model="connectionForm.secret_ref" /></label>
          </div>
          <div class="editor-actions">
            <button class="btn btn-primary" :disabled="readOnly || savingConnection" @click="saveConnection">
              {{ savingConnection ? 'Saving...' : editingConnectionId ? 'Save Connection' : 'Create Connection' }}
            </button>
            <button class="btn btn-secondary" type="button" :disabled="savingConnection" @click="closeConnectionEditor">Cancel</button>
          </div>
        </div>
      </article>

      <article id="accepted-mappings" class="panel panel-wide">
        <div class="panel-header">
          <h2>Raw Backend Supply</h2>
          <button class="btn btn-secondary" type="button" :disabled="readOnly" @click="openNewDiscoveryForm">Add Tool / Endpoint</button>
        </div>
        <p class="panel-copy">
          Add the raw tools, endpoints, or operations that ANIP may call underneath. These records stay operational metadata until you explicitly map them into governed capabilities.
        </p>

        <div v-if="discoveryEditorOpen" ref="discoveryEditorRef" class="editor-shell editor-shell-active">
          <h3>{{ editingDiscoveryId ? 'Edit Raw Backend Operation' : 'Add Raw Backend Operation' }}</h3>
          <div class="form-grid">
            <label><span>ID</span><input v-model="discoveryForm.id" :disabled="!!editingDiscoveryId" /></label>
            <label><span>Connection</span><input v-model="discoveryForm.connection_id" :placeholder="firstConnection?.id || 'connection id'" /></label>
            <label><span>Operation</span><input v-model="discoveryForm.operation_id" /></label>
            <label><span>Backend</span><select v-model="discoveryForm.backend_kind"><option>native_api</option><option>mcp</option><option>database</option><option>hybrid</option></select></label>
            <label><span>{{ backendOperationKindLabel(discoveryForm.backend_kind) }}</span><input v-model="discoveryForm.method" :placeholder="discoveryForm.backend_kind === 'mcp' ? 'tool' : 'GET, POST, ...'" /></label>
            <label><span>Path Template</span><input v-model="discoveryForm.path_template" /></label>
            <label><span>Side Effect</span><input v-model="discoveryForm.side_effect_level" /></label>
            <label><span>Required Inputs</span><input v-model="discoveryForm.required_inputs" /></label>
            <label><span>Optional Inputs</span><input v-model="discoveryForm.optional_inputs" /></label>
          </div>
          <label class="full-field"><span>Risk Notes</span><textarea v-model="discoveryForm.risk_notes" rows="3" /></label>
          <div class="editor-actions">
            <button class="btn btn-primary" :disabled="readOnly || savingDiscovery" @click="saveDiscoveryRecord">
              {{ savingDiscovery ? 'Saving...' : editingDiscoveryId ? 'Save Operation' : 'Create Operation' }}
            </button>
            <button class="btn btn-secondary" type="button" :disabled="savingDiscovery" @click="closeDiscoveryEditor">Cancel</button>
          </div>
        </div>
        <p v-else class="empty-copy">
          {{ discoveryRecords.length ? `${discoveryRecords.length} raw operation metadata record(s) saved below.` : 'No raw operations have been saved yet.' }}
        </p>
      </article>

      <article class="panel panel-wide">
        <div class="panel-header">
          <h2>Saved Raw Operations</h2>
          <span>Operational metadata</span>
        </div>
        <div v-if="discoveryRecords.length" class="record-list">
          <div v-for="record in discoveryRecords" :key="record.id" class="record-card">
            <div class="record-card-heading">
              <div>
                <strong>{{ record.operation_id }}</strong>
                <span>{{ record.backend_kind }} · {{ backendOperationValueLabel(record) }}</span>
              </div>
              <button class="details-toggle" type="button" @click="toggleDiscoveryDetails(record.id)">
                {{ discoveryDetailsOpen(record.id) ? 'Hide details' : 'Show details' }}
              </button>
            </div>
            <div class="compact-meta-grid">
              <div>
                <span>Required</span>
                <strong>{{ discoveryRequiredInputs(record) }}</strong>
              </div>
              <div>
                <span>Optional</span>
                <strong>{{ discoveryOptionalInputs(record) }}</strong>
              </div>
              <div>
                <span>Side effect</span>
                <strong>{{ developerLabel(record.side_effect_level, 'Not set') }}</strong>
              </div>
            </div>
            <div v-if="discoveryDetailsOpen(record.id)" class="details-panel">
              <div class="compact-meta-grid detail-meta-grid">
                <div>
                  <span>Record ID</span>
                  <strong>{{ record.id }}</strong>
                </div>
                <div>
                  <span>Connection</span>
                  <strong>{{ displayValue(record.connection_id) }}</strong>
                </div>
                <div>
                  <span>Operation</span>
                  <strong>{{ record.operation_id }}</strong>
                </div>
                <div>
                  <span>Backend</span>
                  <strong>{{ record.backend_kind }}</strong>
                </div>
                <div>
                  <span>{{ backendOperationKindLabel(record.backend_kind) }}</span>
                  <strong>{{ displayValue(record.method) }}</strong>
                </div>
                <div>
                  <span>Path template</span>
                  <strong>{{ displayValue(record.path_template) }}</strong>
                </div>
              </div>
              <small>Signature: {{ record.content_hash }}</small>
              <pre>{{ JSON.stringify(record.input_schema_summary, null, 2) }}</pre>
              <pre v-if="Object.keys(record.data || {}).length">{{ JSON.stringify(record.data, null, 2) }}</pre>
              <div v-if="record.risk_notes.length" class="detail-note-list">
                <span>Risk notes</span>
                <p v-for="note in record.risk_notes" :key="note">{{ note }}</p>
              </div>
            </div>
            <div class="record-actions">
              <button class="inline-action" type="button" :disabled="readOnly" @click="useDiscoveryRecord(record)">Map this operation</button>
              <button class="inline-action" type="button" :disabled="readOnly" @click="openEditDiscoveryForm(record)">Edit</button>
              <button
                class="inline-action danger-link"
                type="button"
                :disabled="readOnly || deletingDiscoveryId === record.id"
                @click="removeDiscoveryRecord(record)"
              >
                {{ deletingDiscoveryId === record.id ? 'Deleting...' : 'Delete' }}
              </button>
            </div>
          </div>
        </div>
        <p v-else class="panel-copy">No backend tools, endpoints, or operations have been entered yet.</p>
      </article>

      <article class="panel panel-wide">
        <div class="panel-header">
          <h2>Governed Capability Contract</h2>
          <button class="btn btn-secondary" type="button" :disabled="readOnly" @click="openNewMappingForm">Add Governed Mapping</button>
        </div>
        <p class="panel-copy">
          Accepted mappings become Developer Definition content. This is where you decide what agents may ask for, what requires approval, what must clarify or deny, and which backend operation ANIP may call after policy passes.
        </p>
        <div v-if="savedMappings.length" class="record-list mapping-list">
          <div v-for="artifact in savedMappings" :key="artifact.id" class="record-card">
            <div class="record-card-heading">
              <div>
                <strong>{{ artifact.data.capability_id }}</strong>
                <span>{{ artifact.data.service_id }} · {{ developerLabel(artifact.data.side_effect_level, 'Side effect n/a') }} · {{ developerLabel(artifact.data.execution_posture, 'Posture n/a') }}</span>
              </div>
              <button class="details-toggle" type="button" @click="toggleMappingDetails(artifact.id)">
                {{ mappingDetailsOpen(artifact.id) ? 'Hide details' : 'Show details' }}
              </button>
            </div>
            <div class="compact-meta-grid">
              <div>
                <span>Semantic Required</span>
                <strong>{{ mappingRequiredInputs(artifact.data) }}</strong>
              </div>
              <div>
                <span>Semantic Optional</span>
                <strong>{{ mappingOptionalInputs(artifact.data) }}</strong>
              </div>
              <div>
                <span>Backend Bindings</span>
                <strong>{{ mappingBindingStatusSummary(artifact.data) }}</strong>
              </div>
              <div>
                <span>Rules</span>
                <strong>{{ mappingRuleRefs(artifact.data) }}</strong>
              </div>
            </div>
            <div v-if="mappingDetailsOpen(artifact.id)" class="details-panel">
              <div class="compact-meta-grid detail-meta-grid">
                <div>
                  <span>Title</span>
                  <strong>{{ displayValue(artifact.data.title || artifact.title) }}</strong>
                </div>
                <div>
                  <span>Service name</span>
                  <strong>{{ displayValue(artifact.data.service_name) }}</strong>
                </div>
                <div>
                  <span>Backend bindings</span>
                  <strong>{{ summarizeMappingBindings(artifact.data) }}</strong>
                </div>
                <div>
                  <span>Overall backend mode</span>
                  <strong>{{ displayValue(artifact.data.backend_kind) }}</strong>
                </div>
                <div>
                  <span>Semantic required</span>
                  <strong>{{ mappingRequiredInputs(artifact.data) }}</strong>
                </div>
                <div>
                  <span>Semantic optional</span>
                  <strong>{{ mappingOptionalInputs(artifact.data) }}</strong>
                </div>
                <div>
                  <span>Subject</span>
                  <strong>{{ artifact.data.subject_kind || 'not set' }}</strong>
                </div>
                <div>
                  <span>Context</span>
                  <strong>{{ artifact.data.context_type || 'not set' }}</strong>
                </div>
                <div>
                  <span>Output</span>
                  <strong>{{ artifact.data.output_intent || 'not set' }}</strong>
                </div>
                <div>
                  <span>Audit</span>
                  <strong>{{ artifact.data.audit_required === false ? 'not required' : 'required' }}</strong>
                </div>
              </div>
              <div class="binding-card-list">
                <div v-for="entry in mappingBindingHealthEntries(artifact.data)" :key="`${artifact.id}-${entry.binding.backend_kind}-${entry.binding.connection_ref}`" class="binding-card">
                  <div class="binding-card-heading">
                    <strong>{{ bindingSummaryLabel(entry.binding) }}</strong>
                    <span class="status-chip" :class="`status-${entry.health.status}`">{{ entry.health.status }}</span>
                  </div>
                  <div class="compact-meta-grid detail-meta-grid">
                    <div>
                      <span>Input mode</span>
                      <strong>{{ entry.binding.backend_input_mode || mappingBackendInputMode(artifact.data) }}</strong>
                    </div>
                    <div>
                      <span>Derived required</span>
                      <strong>{{ entry.health.derived_required_backend_inputs.length ? entry.health.derived_required_backend_inputs.join(', ') : 'none' }}</strong>
                    </div>
                    <div>
                      <span>Derived optional</span>
                      <strong>{{ entry.health.derived_optional_backend_inputs.length ? entry.health.derived_optional_backend_inputs.join(', ') : 'none' }}</strong>
                    </div>
                    <div>
                      <span>Explicit required</span>
                      <strong>{{ formatList(entry.binding.explicit_required_backend_inputs) }}</strong>
                    </div>
                    <div>
                      <span>Explicit optional</span>
                      <strong>{{ formatList(entry.binding.explicit_optional_backend_inputs) }}</strong>
                    </div>
                  </div>
                  <p class="detail-copy">{{ entry.health.detail }}</p>
                </div>
              </div>
              <p v-if="artifact.data.intent" class="detail-copy">{{ artifact.data.intent }}</p>
            </div>
            <div class="record-actions">
              <button class="inline-action" type="button" :disabled="readOnly" @click="openEditMappingForm(artifact)">Edit</button>
              <button
                class="inline-action danger-link"
                type="button"
                :disabled="readOnly || deletingMappingId === artifact.id"
                @click="removeGovernedMapping(artifact)"
              >
                {{ deletingMappingId === artifact.id ? 'Deleting...' : 'Delete' }}
              </button>
            </div>
          </div>
        </div>
        <p v-else class="empty-copy">No governed mappings have been accepted yet.</p>

        <div v-if="mappingEditorOpen" ref="mappingEditorRef" class="editor-shell editor-shell-active">
          <h3>{{ editingMappingArtifactId ? 'Edit Governed Mapping' : 'Add Governed Mapping' }}</h3>
          <div class="form-grid">
            <label><span>Capability ID</span><input v-model="mappingForm.capability_id" /></label>
            <label><span>Title</span><input v-model="mappingForm.title" /></label>
            <label><span>Service ID</span><input v-model="mappingForm.service_id" /></label>
            <label><span>Service Name</span><input v-model="mappingForm.service_name" /></label>
            <label><span>Execution Posture</span><input v-model="mappingForm.execution_posture" /></label>
            <label><span>Side Effect</span><input v-model="mappingForm.side_effect_level" /></label>
            <label><span>Subject Kind</span><input v-model="mappingForm.subject_kind" /></label>
            <label><span>Context Type</span><input v-model="mappingForm.context_type" /></label>
            <label><span>Output Intent</span><input v-model="mappingForm.output_intent" /></label>
            <label><span>Semantic Required Inputs</span><input v-model="mappingForm.required_inputs" placeholder="project_key, summary, severity" /></label>
            <label><span>Semantic Optional Inputs</span><input v-model="mappingForm.optional_inputs" placeholder="labels, assignee, comment" /></label>
            <label><span>Approval Rules</span><input v-model="mappingForm.approval_rule_refs" /></label>
            <label><span>Denial Rules</span><input v-model="mappingForm.denial_rule_refs" /></label>
            <label><span>Clarification Rules</span><input v-model="mappingForm.clarification_rule_refs" /></label>
          </div>
          <div class="subsection-header">
            <h4>Backend Realizations</h4>
            <button class="btn btn-secondary" type="button" :disabled="readOnly" @click="openAdditionalBackendBinding">Add Backend Binding</button>
          </div>
          <p class="field-hint">
            Keep semantic ANIP inputs explicit above. Define one or more backend realizations below so native API and MCP bindings can drift independently without changing the governed capability contract.
          </p>
          <div class="binding-editor-list">
            <div v-for="binding in mappingBackendBindings" :key="binding.client_id" class="binding-card">
              <div class="binding-card-heading">
                <strong>{{ bindingSummaryLabel(binding) }}</strong>
                <button class="inline-action danger-link" type="button" :disabled="readOnly || mappingBackendBindings.length <= 1" @click="removeBackendBinding(binding.client_id)">Remove</button>
              </div>
              <div class="form-grid">
                <label><span>Backend</span><select v-model="binding.backend_kind"><option>native_api</option><option>mcp</option><option>database</option><option>hybrid</option></select></label>
                <label><span>Connection Ref</span><input v-model="binding.connection_ref" /></label>
                <label><span>Raw Operation Refs</span><input v-model="binding.raw_operation_refs" /></label>
                <label><span>Backend Input Mode</span><select v-model="binding.backend_input_mode"><option value="implicit">implicit</option><option value="hybrid">hybrid</option><option value="explicit">explicit</option></select></label>
              </div>
              <div class="derived-input-summary">
                <div class="summary-row">
                  <span>Derived backend required</span>
                  <strong>{{ bindingEditorDerivedInputs(binding).required.length ? bindingEditorDerivedInputs(binding).required.join(', ') : 'none' }}</strong>
                </div>
                <div class="summary-row">
                  <span>Derived backend optional</span>
                  <strong>{{ bindingEditorDerivedInputs(binding).optional.length ? bindingEditorDerivedInputs(binding).optional.join(', ') : 'none' }}</strong>
                </div>
              </div>
              <div v-if="binding.backend_input_mode !== 'implicit'" class="form-grid">
                <label><span>Explicit Backend Required Inputs</span><input v-model="binding.explicit_required_backend_inputs" placeholder="project, issuetype, summary" /></label>
                <label><span>Explicit Backend Optional Inputs</span><input v-model="binding.explicit_optional_backend_inputs" placeholder="labels, assignee" /></label>
              </div>
            </div>
          </div>
          <label class="full-field checkbox-field">
            <input v-model="mappingForm.audit_required" type="checkbox" />
            <span>Audit required</span>
          </label>
          <label class="full-field"><span>Intent</span><textarea v-model="mappingForm.intent" rows="3" /></label>
          <p v-if="!canAcceptMapping" class="field-hint">
            Capability ID, service ID, connection ref, and at least one raw operation ref are required before accepting a mapping.
          </p>
          <div class="editor-actions">
            <button class="btn btn-primary" :disabled="readOnly || savingMapping || !canAcceptMapping" @click="saveGovernedMapping">
              {{ savingMapping ? 'Saving...' : editingMappingArtifactId ? 'Save Mapping' : 'Accept Mapping' }}
            </button>
            <button class="btn btn-secondary" type="button" :disabled="savingMapping" @click="closeMappingEditor">Cancel</button>
          </div>
        </div>
      </article>
    </section>
  </div>
</template>

<style scoped>
.integration-fronting {
  width: 100%;
  max-width: none;
  padding: 2rem;
}

.hero {
  display: flex;
  justify-content: space-between;
  gap: 1.5rem;
  align-items: flex-start;
  margin-bottom: 1.5rem;
}

.hero-kicker {
  color: var(--text-secondary);
  font-size: 12px;
  letter-spacing: 0.08em;
  margin-bottom: 0.5rem;
  text-transform: uppercase;
}

h1,
h2,
p {
  margin-top: 0;
}

.hero p,
.panel-copy {
  color: var(--text-secondary);
  line-height: 1.6;
}

.principle-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1rem;
  margin: 0 0 1rem;
}

.principle-strip div {
  border: 1px solid rgba(96, 165, 250, 0.18);
  border-radius: 16px;
  background:
    linear-gradient(135deg, rgba(96, 165, 250, 0.08), rgba(34, 197, 94, 0.05)),
    var(--surface-depth-card);
  padding: 1rem;
}

.principle-strip strong {
  display: block;
  color: var(--text-primary);
  font-size: 14px;
  margin-bottom: 0.35rem;
}

.principle-strip span {
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.5;
}

.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
  align-items: start;
}

.panel {
  border: 1px solid var(--surface-border-panel);
  border-radius: 18px;
  background: var(--surface-depth-panel);
  padding: 1.25rem;
}

.panel-wide {
  grid-column: 1 / -1;
}

.workflow-panel {
  background:
    linear-gradient(135deg, rgba(96, 165, 250, 0.08), rgba(52, 211, 153, 0.06)),
    rgba(15, 23, 42, 0.52);
}

.assistant-panel {
  border-color: rgba(52, 211, 153, 0.2);
  background:
    radial-gradient(circle at top left, rgba(52, 211, 153, 0.12), transparent 34rem),
    var(--surface-depth-panel);
}

.assistant-result {
  display: grid;
  gap: 1rem;
}

.assistant-result-heading {
  align-items: flex-start;
  border: 1px solid rgba(52, 211, 153, 0.18);
  border-radius: 16px;
  display: flex;
  gap: 1rem;
  justify-content: space-between;
  padding: 1rem;
  background: rgba(15, 23, 42, 0.3);
}

.assistant-result-heading strong {
  display: block;
  color: var(--text-primary);
  margin-bottom: 0.35rem;
}

.assistant-result-heading p {
  color: var(--text-secondary);
  line-height: 1.5;
  margin: 0;
}

.assistant-result-heading span {
  border-radius: 999px;
  background: rgba(52, 211, 153, 0.14);
  color: var(--text-primary);
  flex: 0 0 auto;
  font-size: 12px;
  font-weight: 800;
  padding: 0.35rem 0.65rem;
}

.assistant-note-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}

.assistant-note-grid > div {
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  background: var(--surface-depth-card);
  padding: 0.9rem;
}

.assistant-note-grid span {
  color: var(--text-secondary);
  display: block;
  font-size: 12px;
  font-weight: 800;
  margin-bottom: 0.5rem;
  text-transform: uppercase;
}

.assistant-note-grid p {
  color: var(--text-primary);
  font-size: 13px;
  line-height: 1.45;
  margin: 0.4rem 0 0;
}

.assistant-candidate-card {
  border-color: rgba(52, 211, 153, 0.16);
}

.candidate-actions {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.candidate-actions .field-hint {
  margin: 0;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
  margin-bottom: 1rem;
}

.panel-header h2 {
  margin: 0;
  font-size: 18px;
}

.panel-header span {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 0.65rem;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.12);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
  margin: 1rem 0;
}

.summary-stack {
  display: grid;
  gap: 0.65rem;
}

.summary-row {
  align-items: center;
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  display: flex;
  gap: 1rem;
  justify-content: space-between;
  padding: 0.75rem 0.85rem;
}

.summary-row span {
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 700;
}

.summary-row strong {
  color: var(--text-primary);
  font-size: 13px;
  text-align: right;
}

.editor-shell {
  border: 1px solid rgba(96, 165, 250, 0.18);
  border-radius: 16px;
  background: var(--surface-depth-card);
  margin-top: 1rem;
  padding: 1rem;
}

.editor-shell h3 {
  margin: 0 0 0.85rem;
  font-size: 15px;
}

.editor-shell-active {
  box-shadow: 0 0 0 1px rgba(96, 165, 250, 0.08), 0 18px 48px rgba(15, 23, 42, 0.25);
}

.derived-input-summary {
  display: grid;
  gap: 0.65rem;
  margin: 1rem 0 0;
  padding: 0.9rem;
  border: 1px solid rgba(96, 165, 250, 0.14);
  border-radius: 14px;
  background:
    linear-gradient(180deg, rgba(15, 23, 42, 0.54), rgba(15, 23, 42, 0.4));
}

.subsection-header,
.binding-card-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.85rem;
}

.subsection-header {
  margin-top: 1rem;
}

.subsection-header h4 {
  margin: 0;
  font-size: 14px;
  color: var(--text-primary);
}

.binding-editor-list,
.binding-card-list {
  display: grid;
  gap: 0.85rem;
  margin-top: 0.85rem;
}

.binding-card {
  display: grid;
  gap: 0.75rem;
  padding: 0.85rem;
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  background: var(--surface-depth-inset);
}

.editor-actions,
.record-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  align-items: center;
}

.editor-actions {
  margin-top: 0.85rem;
}

.empty-copy {
  color: var(--text-secondary);
  line-height: 1.5;
  margin: 0.65rem 0 0;
}

.workflow-steps {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 0.95rem;
  margin-top: 1.05rem;
}

.workflow-step {
  border: 1px solid var(--surface-border-card);
  border-radius: 18px;
  background:
    linear-gradient(180deg, rgba(15, 23, 42, 0.66), rgba(15, 23, 42, 0.46));
  padding: 1rem;
}

.workflow-step.ready {
  border-color: rgba(22, 163, 74, 0.45);
  background: rgba(22, 163, 74, 0.08);
}

.workflow-step-heading {
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
  justify-content: space-between;
}

.workflow-step-heading strong {
  color: var(--text-primary);
  font-size: 14px;
  line-height: 1.35;
  min-width: 0;
}

.workflow-step-heading span {
  flex: 0 0 auto;
  color: var(--text-secondary);
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  padding: 0 0.62rem;
  border: 1px solid var(--surface-border-card);
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.12);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.workflow-step.ready .workflow-step-heading span {
  border-color: rgba(34, 197, 94, 0.28);
  background: rgba(34, 197, 94, 0.12);
  color: #bbf7d0;
}

.workflow-step p,
.next-action-row p,
.field-hint {
  color: var(--text-secondary);
  line-height: 1.5;
  margin: 0.35rem 0 0;
}

.next-action-row {
  align-items: center;
  border: 1px solid rgba(37, 99, 235, 0.25);
  border-radius: 14px;
  display: flex;
  gap: 1rem;
  justify-content: space-between;
  margin-top: 1rem;
  padding: 0.85rem;
}

label,
.full-field {
  display: grid;
  gap: 0.35rem;
  color: var(--text-secondary);
  font-size: 13px;
}

label span,
.full-field span {
  font-weight: 600;
}

input,
select,
textarea {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--surface-border-card);
  border-radius: 12px;
  background: var(--surface-depth-card);
  color: var(--text-primary);
  padding: 0.75rem 0.9rem;
  font: inherit;
}

pre {
  overflow: auto;
  border-radius: 12px;
  border: 1px solid var(--surface-border-card);
  background: var(--surface-depth-inset);
  padding: 1rem;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.panel-save-action {
  margin-top: 0.85rem;
}

.record-list {
  display: grid;
  gap: 0.75rem;
}

.mapping-list {
  margin-top: 1rem;
}

.compact-list {
  margin-top: 1rem;
}

.record-card {
  display: grid;
  gap: 0.65rem;
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  background: var(--surface-depth-card);
  padding: 0.85rem;
}

.record-card-heading {
  align-items: flex-start;
  display: flex;
  gap: 1rem;
  justify-content: space-between;
}

.record-card-heading > div {
  display: grid;
  gap: 0.25rem;
  min-width: 0;
}

.record-card strong {
  color: var(--text-primary);
}

.record-card span,
.record-card small {
  color: var(--text-secondary);
}

.compact-meta-grid {
  display: grid;
  gap: 0.6rem;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.compact-meta-grid > div {
  border: 1px solid var(--surface-border-card);
  border-radius: 12px;
  background: var(--surface-depth-inset);
  display: grid;
  gap: 0.25rem;
  min-width: 0;
  padding: 0.6rem 0.7rem;
}

.compact-meta-grid span,
.detail-note-list span {
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.compact-meta-grid strong {
  color: var(--text-primary);
  font-size: 13px;
  line-height: 1.4;
  overflow-wrap: anywhere;
}

.details-panel {
  border: 1px solid rgba(96, 165, 250, 0.14);
  border-radius: 14px;
  background: var(--surface-depth-inset);
  display: grid;
  gap: 0.75rem;
  padding: 0.8rem;
}

.detail-meta-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.detail-note-list {
  display: grid;
  gap: 0.45rem;
}

.detail-note-list p,
.detail-copy {
  color: var(--text-secondary);
  line-height: 1.5;
  margin: 0;
}

.inline-action {
  justify-self: start;
  border: 1px solid rgba(96, 165, 250, 0.24);
  border-radius: 999px;
  background: rgba(30, 41, 59, 0.55);
  color: #bfdbfe;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  padding: 0.35rem 0.7rem;
}

.details-toggle {
  border: 1px solid var(--surface-border-card);
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.72);
  color: var(--text-secondary);
  cursor: pointer;
  flex: 0 0 auto;
  font: inherit;
  font-size: 12px;
  font-weight: 800;
  padding: 0.35rem 0.7rem;
  white-space: nowrap;
}

.details-toggle:hover {
  border-color: rgba(96, 165, 250, 0.35);
  color: #bfdbfe;
}

.inline-action:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.danger-link {
  border-color: rgba(248, 113, 113, 0.28);
  color: #fecaca;
}

.error,
.notice {
  border-radius: 12px;
  padding: 0.75rem 1rem;
}

.error {
  background: rgba(185, 28, 28, 0.12);
  border: 1px solid rgba(248, 113, 113, 0.28);
  color: var(--error);
}

.notice {
  background: rgba(96, 165, 250, 0.12);
  border: 1px solid rgba(96, 165, 250, 0.28);
  color: #bfdbfe;
}

.checkbox-field {
  align-items: center;
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.checkbox-field input {
  width: auto;
}

@media (max-width: 900px) {
  .hero,
  .panel-header {
    display: grid;
  }

  .panel,
  .panel-wide {
    grid-column: 1 / -1;
  }

  .form-grid,
  .principle-strip {
    grid-template-columns: 1fr;
  }

  .workflow-steps {
    grid-template-columns: 1fr;
  }

  .compact-meta-grid,
  .detail-meta-grid {
    grid-template-columns: 1fr;
  }

  .next-action-row {
    align-items: flex-start;
    display: grid;
  }
}
</style>
