<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  useDeveloperDefinitionEditor,
  ARCHITECTURE_SHAPE_OPTIONS,
  DELIVERY_MODEL_OPTIONS,
  DATA_ACCESS_BACKEND_BINDING_OPTIONS,
  APPLICATION_INTEGRATION_BACKEND_BINDING_OPTIONS,
} from '../design/use-developer-definition-editor'
import { projectStore } from '../design/project-store'
import { useDeveloperIssueTargets } from '../design/use-developer-issue-targets'
import { formatStudioTimestamp } from '../design/time'
import ProjectIssueBanner from '../components/ProjectIssueBanner.vue'
import { useProjectIssue } from '../design/use-project-issue'
import { developerLabel, developerTechnicalLabel, optionLabel } from '../design/developer-vocabulary'
import { showTechnicalIdentifiers, technicalHoverLabel } from '../design/technical-display'
import { buildRbacModel } from '../design/rbac-model'

const route = useRoute()
const router = useRouter()
const editing = ref(false)
const activeServiceAnchor = ref('')
const pageIssue = useProjectIssue('project-developer-service-formalization')
const readOnly = computed(() => projectStore.runtimeStatus?.read_only_mode !== false)
const {
  project,
  baseline,
  baselineAligned,
  definition,
  saveDraft,
  resetDefinition,
  saving,
  saveError,
} = useDeveloperDefinitionEditor()

const {
  messagesForPath,
  messagesForPrefix,
  hasIssueForPath,
  hasIssueForPrefix,
  serviceValidationMessages,
  serviceNeedsCapabilityConfirmation,
  serviceHasIssue,
} = useDeveloperIssueTargets({ definition, project })
const rbacModel = computed(() => buildRbacModel(definition.value))

const TRUST_MODE_OPTIONS = [
  {
    value: 'unsigned',
    label: 'No signature required',
    description: 'Use only when this package does not rely on signed caller or package evidence.',
  },
  {
    value: 'signed',
    label: 'Signed evidence required',
    description: 'Requests or package evidence should be signed and verifiable.',
  },
  {
    value: 'anchored',
    label: 'Signed and anchored to a trust root',
    description: 'Trust should chain back to a known authority, registry, or organization root.',
  },
  {
    value: 'attested',
    label: 'Strong attestation required',
    description: 'Use for the strongest identity posture, such as hardware-backed or platform-backed attestation.',
  },
]

const APPROVAL_EXPECTATION_OPTIONS = [
  {
    value: 'not_specified',
    label: 'No special approval expectation recorded',
    description: 'Approval may still exist per capability, but there is no package-wide expectation here.',
  },
  {
    value: 'no_approval_expected',
    label: 'Approval is not expected',
    description: 'The package is expected to stay within non-governed or read-only behavior.',
  },
  {
    value: 'approval_required_for_high_risk',
    label: 'Approval for high-risk work',
    description: 'High-risk actions should stop for explicit approval before progressing.',
  },
  {
    value: 'approval_required_for_write',
    label: 'Approval for write actions',
    description: 'Any write or write-adjacent behavior should require approval.',
  },
  {
    value: 'approval_required_for_governed_work',
    label: 'Approval for governed work',
    description: 'Governed actions should use explicit approval even when they are previews or preparations.',
  },
]

const FAILURE_POSTURE_OPTIONS = [
  {
    value: '',
    label: 'No special failure posture recorded',
    description: 'Use normal service/runtime behavior unless a capability declares something stricter.',
  },
  {
    value: 'structured_blocked',
    label: 'Return a clear blocked response',
    description: 'Stop safely and return a structured reason the consuming app can show to the user.',
  },
  {
    value: 'retry_with_backoff',
    label: 'Retry with backoff',
    description: 'Retry transient failures using controlled backoff instead of failing immediately.',
  },
  {
    value: 'escalate_to_human',
    label: 'Escalate to a human',
    description: 'Stop and hand the situation to a person when authority, policy, or recovery is unclear.',
  },
  {
    value: 'fail_safe',
    label: 'Fail safe',
    description: 'Halt execution and leave the system in a safe known state.',
  },
]

function yesNoLabel(value: boolean | undefined): string {
  return value ? 'Enabled' : 'Not enabled'
}

function booleanPostureLabel(value: boolean | undefined, enabledLabel: string, disabledLabel: string): string {
  return value ? enabledLabel : disabledLabel
}

function backendLabel(value: string | undefined | null, emptyLabel = 'Not set'): string {
  return developerLabel(value, emptyLabel)
}

function serviceBackendBindingsForService(serviceId: string) {
  const binding = definition.value?.service_backend_bindings.find((candidate) => candidate.service_id === serviceId)
  return binding ? [binding] : []
}

function serviceBackendBindingPath(serviceId: string, field: string): string {
  return `service_backend_bindings.${serviceId}.${field}`
}

function serviceBackendBindingHasIssue(serviceId: string): boolean {
  return hasIssueForPrefix(`service_backend_bindings.${serviceId}`)
}

function normalizeRuntimeBackendFlags(runtime: {
  uses_data_access_backend: boolean
  data_access_backend_type: string
  data_access_target_label: string
  uses_application_integration_backend: boolean
  application_integration_backend_type: string
  application_integration_system_name: string
  application_integration_environment: string
  application_integration_auth_type: string
  application_integration_adapter_target: string
}): void {
  if (!runtime.uses_data_access_backend) {
    runtime.data_access_backend_type = ''
    runtime.data_access_target_label = ''
  }
  if (!runtime.uses_application_integration_backend) {
    runtime.application_integration_backend_type = ''
    runtime.application_integration_system_name = ''
    runtime.application_integration_environment = ''
    runtime.application_integration_auth_type = ''
    runtime.application_integration_adapter_target = ''
    return
  }
  runtime.application_integration_environment = ''
  if (runtime.application_integration_backend_type !== 'custom_adapter') {
    runtime.application_integration_adapter_target = ''
  }
}

function normalizeAllRuntimeBackendFlags(): void {
  for (const runtime of definition.value?.service_backend_bindings ?? []) {
    normalizeRuntimeBackendFlags(runtime)
  }
}

function startEditing(): void {
  if (readOnly.value) return
  editing.value = true
}

function cancelEditing(): void {
  resetDefinition()
  editing.value = false
}

async function saveAndReview(): Promise<void> {
  if (readOnly.value) return
  normalizeAllRuntimeBackendFlags()
  await saveDraft()
  if (!saveError.value) {
    editing.value = false
  }
}

function friendlyIdentifier(value: string): string {
  const raw = String(value || '').split('.').pop() || value
  return raw
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

function capabilityDisplayName(capabilityId: string, fallbackTitle?: string): string {
  const raw = String(capabilityId || '').trim()
  if (!raw) return fallbackTitle || 'Capability'
  const [namespace, ...rest] = raw.split('.')
  if (!namespace || rest.length === 0) return fallbackTitle || friendlyIdentifier(raw)
  return `${friendlyIdentifier(namespace)}.${friendlyIdentifier(rest.join('.'))}`
}

function confirmedCapabilityCount(service: { formalized_capability_ids: string[] }): number {
  return service.formalized_capability_ids.length
}

function missingFormalizedCapabilities(service: { source_capabilities: string[], formalized_capability_ids: string[] }): string[] {
  const confirmed = new Set(service.formalized_capability_ids)
  return service.source_capabilities.filter((capabilityId) => !confirmed.has(capabilityId))
}

function restoreProposedCapabilities(service: { source_capabilities: string[], formalized_capability_ids: string[] }): void {
  service.formalized_capability_ids = [...service.source_capabilities]
}

function capabilitySummary(service: { source_capabilities: string[], formalized_capability_ids: string[] }): string {
  if (!service.source_capabilities.length) return 'No canonical capabilities were proposed for this service.'
  const confirmed = confirmedCapabilityCount(service)
  const total = service.source_capabilities.length
  if (confirmed === total) return `${confirmed} of ${total} proposed capabilities are confirmed for this service.`
  return `${confirmed} of ${total} proposed capabilities are confirmed. Restore the proposed set here, or change ownership in Service Design / Agent & App Glue before generation.`
}

function servicePermissionRequirements(serviceId: string) {
  const permissionsById = new Map(rbacModel.value.permissions.map((permission) => [permission.id, permission]))
  return rbacModel.value.capabilityRequirements
    .filter((requirement) => requirement.capability.service_id === serviceId)
    .map((requirement) => ({
      capability: requirement.capability,
      permissions: requirement.permissionIds
        .map((permissionId) => permissionsById.get(permissionId))
        .filter((permission): permission is NonNullable<typeof permission> => Boolean(permission)),
    }))
    .filter((requirement) => requirement.permissions.length)
}

function routeHashTarget(): string {
  if (!route.hash) return ''
  try {
    return decodeURIComponent(route.hash.slice(1))
  } catch {
    return route.hash.slice(1)
  }
}

async function scrollToServiceHash() {
  const target = routeHashTarget()
  activeServiceAnchor.value = target
  if (!target) return
  await nextTick()
  document.getElementById(target)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

onMounted(scrollToServiceHash)
watch(
  () => [route.hash, definition.value?.service_topology_bindings.length ?? 0],
  () => {
    void scrollToServiceHash()
  },
)
</script>

<template>
  <div class="developer-definition">
    <template v-if="project">
      <section class="page-header">
        <button class="back-link" type="button" @click="router.push(`/design/projects/${project.id}/developer`)">
          &larr; Back to Developer Design
        </button>
        <div class="page-kicker">Developer Design</div>
        <h1>Service Formalization</h1>
        <p>
          Formalize service architecture, service boundaries, runtime backends, and authority posture here. Cross-cutting audit, actor expectations, and PM-rule bindings live on their own page.
        </p>
      </section>
      <ProjectIssueBanner :issue="pageIssue" title="Service Formalization diagnostics" />
      <section v-if="!baseline" class="panel empty-panel">
        <h2>Developer baseline is not locked</h2>
        <p>Return to Developer Overview and lock Product Design before formalizing service structure.</p>
      </section>

      <section v-else-if="!baselineAligned" class="panel empty-panel">
        <h2>Locked baseline is out of sync</h2>
        <p>Product Design changed after the current developer baseline was locked. Re-lock the baseline before continuing.</p>
      </section>

      <section v-else-if="definition" class="grid" :class="{ 'review-mode': !editing, 'edit-mode': editing }">
        <article class="panel panel-full">
          <div class="panel-header">
            <h2>Locked Baseline</h2>
            <div class="header-actions">
              <span class="status-chip">{{ formatStudioTimestamp(baseline!.locked_at) }}</span>
              <button v-if="!editing" class="btn btn-secondary" type="button" :disabled="readOnly" @click="startEditing">
                Edit Service Design
              </button>
              <button v-if="editing" class="btn btn-secondary" type="button" :disabled="saving" @click="cancelEditing">
                Cancel
              </button>
              <button v-if="editing" class="btn btn-primary" :disabled="readOnly || saving" @click="saveAndReview">
                {{ saving ? 'Saving…' : 'Save Formalization' }}
              </button>
            </div>
          </div>
          <p v-if="saveError" class="error">{{ saveError }}</p>
          <p class="panel-copy">
            These values define the service architecture surface of the Developer Definition. Keep service boundaries, capability ownership, required permissions, per-service runtime backends, and authority here. Use Roles & Access for role assignments and Audit & Lineage for evidence requirements.
          </p>
        </article>

        <article id="product-intent-formalization" class="panel panel-full">
          <div class="panel-header">
            <h2>Product Intent Formalization</h2>
          </div>
          <p class="panel-copy intent-intro">
            These fields make the PM-level governed behavior and approval posture explicit in the developer contract instead of leaving them as summary prose.
          </p>
          <div class="review-summary-grid review-only">
            <div class="review-summary-card field-wide"><strong>Governed Behavior</strong><p>{{ definition.product_alignment.governed_behavior_formalization || 'Not formalized yet.' }}</p></div>
            <div class="review-summary-card field-wide"><strong>Approval Posture</strong><p>{{ definition.product_alignment.approval_posture_formalization || 'Not formalized yet.' }}</p></div>
          </div>
          <div class="settings-grid edit-only">
            <label id="product-intent-governed-behavior" class="field">
              <span class="summary-label required-label">Governed Behavior Summary</span>
              <textarea
                v-model="definition.product_alignment.governed_behavior_formalization"
                class="textarea"
                rows="3"
                placeholder="State how the generated and implemented services should preserve the governed behavior PM described."
              />
            </label>
            <label id="product-intent-approval-posture" class="field">
              <span class="summary-label required-label">Approval Posture Summary</span>
              <textarea
                v-model="definition.product_alignment.approval_posture_formalization"
                class="textarea"
                rows="3"
                placeholder="State how approval-required work should be represented across capabilities, stop conditions, and runtime outcomes."
              />
            </label>
          </div>
        </article>

        <article id="identity-delivery" class="panel panel-full">
          <div class="panel-header">
            <h2>Identity & Delivery</h2>
          </div>
          <div class="review-summary-grid review-only">
            <div class="review-summary-card"><strong>System Name</strong><span>{{ definition.identity.system_name || 'Not set' }}</span></div>
            <div class="review-summary-card"><strong>Domain</strong><span>{{ definition.identity.domain_name || 'Not set' }}</span></div>
            <div class="review-summary-card">
              <strong>Delivery Model</strong>
              <span :title="technicalHoverLabel(definition.identity.delivery_model)">{{ optionLabel(DELIVERY_MODEL_OPTIONS, definition.identity.delivery_model) }}</span>
              <small v-if="showTechnicalIdentifiers">{{ developerTechnicalLabel(definition.identity.delivery_model) }}</small>
            </div>
            <div class="review-summary-card">
              <strong>Architecture Shape</strong>
              <span :title="technicalHoverLabel(definition.identity.architecture_shape)">{{ optionLabel(ARCHITECTURE_SHAPE_OPTIONS, definition.identity.architecture_shape) }}</span>
              <small v-if="showTechnicalIdentifiers">{{ developerTechnicalLabel(definition.identity.architecture_shape) }}</small>
            </div>
            <div class="review-summary-card"><strong>High Availability</strong><span>{{ definition.identity.high_availability_required ? 'Required' : 'Not required' }}</span></div>
          </div>
          <div class="settings-grid edit-only">
            <label id="identity-system-name" class="field">
              <span class="required-label">System Name</span>
              <input v-model="definition.identity.system_name" class="input" placeholder="e.g. Revenue Operations Service" />
            </label>
            <label id="identity-domain" class="field">
              <span class="required-label">Domain</span>
              <input v-model="definition.identity.domain_name" class="input" placeholder="e.g. revenue_operations" />
            </label>
            <label id="identity-delivery-model" class="field">
              <span class="required-label">Delivery Model</span>
              <select v-model="definition.identity.delivery_model" class="select">
                <option v-for="option in DELIVERY_MODEL_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
              </select>
              <small class="hint">{{ DELIVERY_MODEL_OPTIONS.find((option) => option.value === definition.identity.delivery_model)?.description }}</small>
            </label>
            <label id="identity-architecture-shape" class="field">
              <span class="required-label">Architecture Shape</span>
              <select v-model="definition.identity.architecture_shape" class="select">
                <option v-for="option in ARCHITECTURE_SHAPE_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
              </select>
              <small class="hint">{{ ARCHITECTURE_SHAPE_OPTIONS.find((option) => option.value === definition.identity.architecture_shape)?.description }}</small>
            </label>
            <label id="identity-high-availability" class="field">
              <span class="required-label">High Availability Required</span>
              <select v-model="definition.identity.high_availability_required" class="select">
                <option :value="true">Yes</option>
                <option :value="false">No</option>
              </select>
            </label>
          </div>
        </article>

        <article id="service-topology-bindings" class="panel panel-full">
          <div class="panel-header">
            <h2>Service Topology Bindings</h2>
          </div>
          <p class="panel-copy topology-intro">
            Formalize each Service Design boundary here so Coverage can point to an exact technical target instead of a broad topology section.
          </p>
          <div v-if="definition.service_topology_bindings.length" class="binding-list">
            <div
              v-for="service in definition.service_topology_bindings"
              :id="service.service_id"
              :key="service.id"
              class="binding-card"
              :class="{
                'field-error-card': serviceHasIssue(service) || serviceBackendBindingHasIssue(service.service_id),
                'anchored-card': activeServiceAnchor === service.service_id,
              }"
            >
              <div class="section-head">
                <div>
                  <h3>{{ service.service_name }}</h3>
                  <p v-if="serviceNeedsCapabilityConfirmation(service)" class="inline-field-error">
                    This service has responsibilities but no canonical capability IDs. Add capability IDs, merge this boundary away, or intentionally defer it on Agent & App Glue.
                  </p>
                  <p
                    v-for="message in serviceValidationMessages(service)"
                    :key="message"
                    class="inline-field-error"
                  >
                    {{ message }}
                  </p>
                </div>
              </div>
              <p class="panel-copy binding-description">
                {{ service.source_role || 'No source role recorded.' }}
              </p>
              <div class="source-confirmation-card">
                <strong>Service Design proposed ownership</strong>
                <p>{{ capabilitySummary(service) }}</p>
              </div>
              <div class="source-confirmation-card policy-enforcement-card">
                <div class="section-head compact-head">
                  <div>
                    <strong>Required Permissions</strong>
                    <p class="section-hint">
                      Capabilities owned by this service list the permissions callers must have. Roles receive those permissions on Roles & Access.
                    </p>
                  </div>
                </div>
                <div v-if="servicePermissionRequirements(service.service_id).length" class="policy-enforcement-list">
                  <div
                    v-for="requirement in servicePermissionRequirements(service.service_id)"
                    :key="requirement.capability.capability_id"
                    class="policy-enforcement-row"
                  >
                    <strong class="policy-capability-title">{{ capabilityDisplayName(requirement.capability.capability_id, requirement.capability.title) }}</strong>
                    <div class="policy-permission-count">
                      {{ requirement.permissions.length }} required permission{{ requirement.permissions.length === 1 ? '' : 's' }}
                    </div>
                    <div class="policy-permission-list">
                      {{ requirement.permissions.map((permission) => permission.label).join(', ') }}
                    </div>
                    <p>
                      Generated runtime policy checks whether the caller's role has one of the required permissions before this capability runs.
                    </p>
                  </div>
                </div>
                <p v-else class="empty-state">No required permissions are mapped to this service's capabilities yet.</p>
              </div>
              <div class="review-summary-grid review-only">
                <div class="review-summary-card"><strong>Formalized Capabilities</strong><span>{{ service.formalized_capability_ids.length }} / {{ service.source_capabilities.length }}</span></div>
                <div v-if="service.source_concepts.length" class="review-summary-card"><strong>Owned Concepts</strong><span>{{ service.owned_concept_ids.length }} / {{ service.source_concepts.length }}</span></div>
                <div class="review-summary-card field-wide"><strong>Implementation Notes</strong><p>{{ service.implementation_notes || 'No notes recorded.' }}</p></div>
              </div>
              <div
                v-for="runtime in serviceBackendBindingsForService(service.service_id)"
                :id="`service-backend-bindings-${service.service_id}`"
                :key="runtime.service_id"
                class="service-runtime-backends"
                :class="{ 'field-error-card': serviceBackendBindingHasIssue(runtime.service_id) }"
              >
                <div class="section-head compact-head">
                  <div>
                    <h4>External Runtime Dependencies</h4>
                    <p class="section-hint">
                      Declare only external systems this service calls. Native generated/custom service implementation does not need a backend here.
                    </p>
                    <p
                      v-for="message in messagesForPrefix(`service_backend_bindings.${runtime.service_id}`)"
                      :key="message"
                      class="inline-field-error"
                    >
                      {{ message }}
                    </p>
                  </div>
                </div>
                <div class="review-summary-grid review-only">
                  <div class="review-summary-card">
                    <strong>Data Backend</strong>
                    <span :title="technicalHoverLabel(runtime.data_access_backend_type)">{{ runtime.uses_data_access_backend ? backendLabel(runtime.data_access_backend_type, 'Enabled') : 'Not used' }}</span>
                    <small v-if="showTechnicalIdentifiers && runtime.uses_data_access_backend">{{ developerTechnicalLabel(runtime.data_access_backend_type) }}</small>
                  </div>
                  <div v-if="runtime.uses_data_access_backend" class="review-summary-card"><strong>Data Target</strong><span>{{ runtime.data_access_target_label || 'Not set' }}</span></div>
                  <div class="review-summary-card">
                    <strong>Integration Backend</strong>
                    <span :title="technicalHoverLabel(runtime.application_integration_backend_type)">{{ runtime.uses_application_integration_backend ? backendLabel(runtime.application_integration_backend_type, 'Enabled') : 'Not used' }}</span>
                    <small v-if="showTechnicalIdentifiers && runtime.uses_application_integration_backend">{{ developerTechnicalLabel(runtime.application_integration_backend_type) }}</small>
                  </div>
                  <template v-if="runtime.uses_application_integration_backend">
                    <div v-if="runtime.application_integration_backend_type === 'custom_adapter'" class="review-summary-card"><strong>Backend Template</strong><span>{{ runtime.application_integration_adapter_target || 'Not set' }}</span></div>
                    <div v-else class="review-summary-card"><strong>Integration System</strong><span>{{ runtime.application_integration_system_name || 'Not set' }}</span></div>
                  </template>
                </div>
                <div class="settings-grid edit-only">
                  <label class="field">
                    <span>Calls External Data Backend</span>
                    <select v-model="runtime.uses_data_access_backend" class="select" @change="normalizeRuntimeBackendFlags(runtime)">
                      <option :value="true">Yes</option>
                      <option :value="false">No</option>
                    </select>
                  </label>
                  <label v-if="runtime.uses_data_access_backend" class="field" :class="{ 'field-error': hasIssueForPath(serviceBackendBindingPath(runtime.service_id, 'data_access_backend_type')) }">
                    <span>Data Access Backend Type</span>
                    <select v-model="runtime.data_access_backend_type" class="select">
                      <option value="">Select a data backend</option>
                      <option v-for="option in DATA_ACCESS_BACKEND_BINDING_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
                    </select>
                    <small v-for="message in messagesForPath(serviceBackendBindingPath(runtime.service_id, 'data_access_backend_type'))" :key="message" class="field-error-copy">{{ message }}</small>
                  </label>
                  <label v-if="runtime.uses_data_access_backend" class="field field-wide" :class="{ 'field-error': hasIssueForPath(serviceBackendBindingPath(runtime.service_id, 'data_access_target_label')) }">
                    <span>Data Access Target Label</span>
                    <input v-model="runtime.data_access_target_label" class="input" placeholder="e.g. Revenue Analytics Warehouse" />
                    <small v-for="message in messagesForPath(serviceBackendBindingPath(runtime.service_id, 'data_access_target_label'))" :key="message" class="field-error-copy">{{ message }}</small>
                  </label>

                  <label class="field">
                    <span>Calls External Application Backend</span>
                    <select v-model="runtime.uses_application_integration_backend" class="select" @change="normalizeRuntimeBackendFlags(runtime)">
                      <option :value="true">Yes</option>
                      <option :value="false">No</option>
                    </select>
                  </label>
                  <label v-if="runtime.uses_application_integration_backend" class="field" :class="{ 'field-error': hasIssueForPath(serviceBackendBindingPath(runtime.service_id, 'application_integration_backend_type')) }">
                    <span>Integration Backend Type</span>
                    <select v-model="runtime.application_integration_backend_type" class="select" @change="normalizeRuntimeBackendFlags(runtime)">
                      <option value="">Select an integration backend</option>
                      <option v-for="option in APPLICATION_INTEGRATION_BACKEND_BINDING_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
                    </select>
                    <small v-for="message in messagesForPath(serviceBackendBindingPath(runtime.service_id, 'application_integration_backend_type'))" :key="message" class="field-error-copy">{{ message }}</small>
                  </label>
                  <label v-if="runtime.uses_application_integration_backend && runtime.application_integration_backend_type !== 'custom_adapter'" class="field field-wide" :class="{ 'field-error': hasIssueForPath(serviceBackendBindingPath(runtime.service_id, 'application_integration_system_name')) }">
                    <span>Integration System Name</span>
                    <input v-model="runtime.application_integration_system_name" class="input" placeholder="e.g. Salesforce CRM" />
                    <small v-for="message in messagesForPath(serviceBackendBindingPath(runtime.service_id, 'application_integration_system_name'))" :key="message" class="field-error-copy">{{ message }}</small>
                  </label>
                  <label v-if="runtime.uses_application_integration_backend && runtime.application_integration_backend_type === 'custom_adapter'" class="field field-wide" :class="{ 'field-error': hasIssueForPath(serviceBackendBindingPath(runtime.service_id, 'application_integration_adapter_target')) }">
                    <span>Backend Template or Implementation Target</span>
                    <input v-model="runtime.application_integration_adapter_target" class="input" placeholder="e.g. generated-backend-template:mcp or internal-notification-client" />
                    <small class="hint">Only needed for custom backend implementation. REST, GraphQL, MCP, and internal HTTP services should usually use Integration System Name instead.</small>
                    <small v-for="message in messagesForPath(serviceBackendBindingPath(runtime.service_id, 'application_integration_adapter_target'))" :key="message" class="field-error-copy">{{ message }}</small>
                  </label>
                </div>
              </div>
              <div class="settings-grid edit-only">
                <div
                  class="field field-wide formalized-capabilities-field"
                  :class="{
                    'field-error': hasIssueForPath(`service_topology_bindings.${service.id}.formalized_capability_ids`) || serviceNeedsCapabilityConfirmation(service) || missingFormalizedCapabilities(service).length > 0,
                  }"
                >
                  <span class="summary-label required-label">Formalized Capabilities</span>
                  <div class="chip-grid">
                    <span
                      v-for="capabilityId in service.source_capabilities"
                      :key="capabilityId"
                      class="chip readonly-chip"
                      :class="{ active: service.formalized_capability_ids.includes(capabilityId) }"
                      :title="capabilityId"
                    >
                      {{ friendlyIdentifier(capabilityId) }}
                    </span>
                  </div>
                  <small class="hint">This page confirms ownership proposed by Service Design. To move or remove a capability, update Service Design or record an explicit defer/app-glue decision on Agent & App Glue.</small>
                  <div v-if="missingFormalizedCapabilities(service).length" class="inline-actions">
                    <button type="button" class="btn btn-secondary" @click="restoreProposedCapabilities(service)">
                      Restore proposed ownership
                    </button>
                    <button type="button" class="btn btn-secondary" @click="router.push(`/design/projects/${project.id}/shapes`)">
                      Open Service Design
                    </button>
                    <button type="button" class="btn btn-secondary" @click="router.push(`/design/projects/${project.id}/developer/app-glue`)">
                      Open Agent & App Glue
                    </button>
                  </div>
                  <small
                    v-if="serviceNeedsCapabilityConfirmation(service)"
                    class="field-error-copy"
                  >
                    No canonical capabilities were declared for this service boundary.
                  </small>
                  <small
                    v-for="capabilityId in missingFormalizedCapabilities(service)"
                    :key="capabilityId"
                    class="field-error-copy"
                  >
                    {{ friendlyIdentifier(capabilityId) }} is currently unassigned.
                  </small>
                  <small
                    v-for="message in messagesForPath(`service_topology_bindings.${service.id}.formalized_capability_ids`)"
                    :key="message"
                    class="field-error-copy"
                  >
                    {{ message }}
                  </small>
                </div>
                <div v-if="service.source_concepts.length" class="field field-wide owned-concepts-field">
                  <span class="summary-label">Owned Concepts</span>
                  <div class="chip-grid">
                    <button
                      v-for="conceptId in service.source_concepts"
                      :key="conceptId"
                      type="button"
                      class="chip"
                      :class="{ active: service.owned_concept_ids.includes(conceptId) }"
                      @click="
                        service.owned_concept_ids = service.owned_concept_ids.includes(conceptId)
                          ? service.owned_concept_ids.filter((value) => value !== conceptId)
                          : [...service.owned_concept_ids, conceptId]
                      "
                    >
                      {{ conceptId }}
                    </button>
                  </div>
                  <small class="hint">Use the seeded concept list to confirm which domain concepts this service boundary owns.</small>
                </div>
                <label class="field field-wide">
                  <span class="summary-label">Implementation Notes</span>
                  <textarea
                    v-model="service.implementation_notes"
                    class="textarea"
                    rows="3"
                    placeholder="Optional notes only when the structured ownership fields are not enough."
                  />
                </label>
              </div>
            </div>
          </div>
          <p v-else class="panel-copy">No services are defined on the locked Service Design.</p>
        </article>

        <article id="authority-approval" class="panel panel-full">
          <div class="panel-header">
            <h2>Authority & Approval</h2>
          </div>
          <p class="panel-copy">
            Define the package-level authority posture in business language. Studio saves canonical values behind these choices for contract generation.
          </p>
          <div class="review-summary-grid review-only">
            <div class="review-summary-card">
              <strong>Caller Trust Evidence</strong>
              <span :title="technicalHoverLabel(definition.authority.trust_mode)">{{ optionLabel(TRUST_MODE_OPTIONS, definition.authority.trust_mode) }}</span>
              <small v-if="showTechnicalIdentifiers">{{ developerTechnicalLabel(definition.authority.trust_mode) }}</small>
            </div>
            <div class="review-summary-card"><strong>Re-check Authority During Work</strong><span>{{ booleanPostureLabel(definition.authority.trust_checkpoints_required, 'Required', 'Not required') }}</span></div>
            <div class="review-summary-card"><strong>Spending or Budget Risk</strong><span>{{ booleanPostureLabel(definition.authority.spending_actions_present, 'Present', 'Not present') }}</span></div>
            <div class="review-summary-card"><strong>Irreversible Action Risk</strong><span>{{ booleanPostureLabel(definition.authority.irreversible_actions_present, 'Present', 'Not present') }}</span></div>
            <div class="review-summary-card"><strong>Show Cost Before Work</strong><span>{{ booleanPostureLabel(definition.authority.cost_visibility_required, 'Required', 'Not required') }}</span></div>
            <div class="review-summary-card"><strong>Discover Authority Before Acting</strong><span>{{ booleanPostureLabel(definition.authority.preflight_authority_discovery, 'Required', 'Not required') }}</span></div>
            <div class="review-summary-card"><strong>Restricted Actions Can Be Granted</strong><span>{{ yesNoLabel(definition.authority.grantable_restrictions) }}</span></div>
            <div class="review-summary-card"><strong>Separate Restricted From Denied</strong><span>{{ yesNoLabel(definition.authority.restricted_vs_denied) }}</span></div>
            <div class="review-summary-card"><strong>Use Delegated Authority Tokens</strong><span>{{ yesNoLabel(definition.authority.delegation_tokens) }}</span></div>
            <div class="review-summary-card"><strong>Limit Authority by Scope</strong><span>{{ yesNoLabel(definition.authority.scoped_authority) }}</span></div>
            <div class="review-summary-card"><strong>Bind Authority to Purpose</strong><span>{{ yesNoLabel(definition.authority.purpose_binding) }}</span></div>
            <div class="review-summary-card">
              <strong>Approval Expectation</strong>
              <span :title="technicalHoverLabel(definition.authority.approval_expectation)">{{ optionLabel(APPROVAL_EXPECTATION_OPTIONS, definition.authority.approval_expectation) }}</span>
              <small v-if="showTechnicalIdentifiers">{{ developerTechnicalLabel(definition.authority.approval_expectation) }}</small>
            </div>
            <div class="review-summary-card"><strong>Needs Explicit Recovery Guidance</strong><span>{{ yesNoLabel(definition.authority.recovery_sensitive) }}</span></div>
            <div class="review-summary-card">
              <strong>When Work Is Blocked or Fails</strong>
              <span :title="technicalHoverLabel(definition.authority.blocked_failure_posture)">{{ optionLabel(FAILURE_POSTURE_OPTIONS, definition.authority.blocked_failure_posture) }}</span>
              <small v-if="showTechnicalIdentifiers">{{ developerTechnicalLabel(definition.authority.blocked_failure_posture) }}</small>
            </div>
          </div>
          <div class="settings-grid edit-only">
            <label id="authority-trust-mode" class="field">
              <span>Caller Trust Evidence</span>
              <select v-model="definition.authority.trust_mode" class="select">
                <option v-for="option in TRUST_MODE_OPTIONS" :key="option.value" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
              <small class="hint">{{ TRUST_MODE_OPTIONS.find((option) => option.value === definition.authority.trust_mode)?.description }}</small>
            </label>
            <label id="authority-trust-checkpoints" class="field">
              <span>Re-check authority during work</span>
              <select v-model="definition.authority.trust_checkpoints_required" class="select">
                <option :value="true">Required before important steps</option>
                <option :value="false">Initial authority check is enough</option>
              </select>
            </label>
            <label id="authority-spending-actions" class="field">
              <span>Spending or budget risk</span>
              <select v-model="definition.authority.spending_actions_present" class="select">
                <option :value="true">Present</option>
                <option :value="false">Not present</option>
              </select>
            </label>
            <label id="authority-irreversible-actions" class="field">
              <span>Irreversible action risk</span>
              <select v-model="definition.authority.irreversible_actions_present" class="select">
                <option :value="true">Present</option>
                <option :value="false">Not present</option>
              </select>
            </label>
            <label id="authority-cost-visibility" class="field">
              <span>Show cost before work</span>
              <select v-model="definition.authority.cost_visibility_required" class="select">
                <option :value="true">Required</option>
                <option :value="false">Not required</option>
              </select>
            </label>
            <label id="authority-preflight-discovery" class="field">
              <span>Discover authority before acting</span>
              <select v-model="definition.authority.preflight_authority_discovery" class="select">
                <option :value="true">Required</option>
                <option :value="false">Not required</option>
              </select>
            </label>
            <label id="authority-grantable-restrictions" class="field">
              <span>Restricted actions can be granted</span>
              <select v-model="definition.authority.grantable_restrictions" class="select">
                <option :value="true">Yes, additional authority can unlock them</option>
                <option :value="false">No, blocked actions stay blocked</option>
              </select>
            </label>
            <label id="authority-restricted-vs-denied" class="field">
              <span>Separate restricted from denied</span>
              <select v-model="definition.authority.restricted_vs_denied" class="select">
                <option :value="true">Yes, distinguish temporary restriction from hard denial</option>
                <option :value="false">No, one blocked outcome is enough</option>
              </select>
            </label>
            <label id="authority-delegation-tokens" class="field">
              <span>Use delegated authority tokens</span>
              <select v-model="definition.authority.delegation_tokens" class="select">
                <option :value="true">Yes, carry scoped delegated authority</option>
                <option :value="false">No delegated authority tokens</option>
              </select>
            </label>
            <label id="authority-scoped-authority" class="field">
              <span>Limit authority by scope</span>
              <select v-model="definition.authority.scoped_authority" class="select">
                <option :value="true">Yes, authority is bounded by scope</option>
                <option :value="false">No explicit scope boundary</option>
              </select>
            </label>
            <label id="authority-purpose-binding" class="field">
              <span>Bind authority to purpose</span>
              <select v-model="definition.authority.purpose_binding" class="select">
                <option :value="true">Yes, authority is tied to intended purpose</option>
                <option :value="false">No explicit purpose binding</option>
              </select>
            </label>
            <label id="authority-approval-expectation" class="field">
              <span>Approval expectation</span>
              <select v-model="definition.authority.approval_expectation" class="select">
                <option v-for="option in APPROVAL_EXPECTATION_OPTIONS" :key="option.value" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
              <small class="hint">{{ APPROVAL_EXPECTATION_OPTIONS.find((option) => option.value === definition.authority.approval_expectation)?.description }}</small>
            </label>
            <label id="authority-recovery-sensitive" class="field">
              <span>Needs explicit recovery guidance</span>
              <select v-model="definition.authority.recovery_sensitive" class="select">
                <option :value="true">Yes, recovery behavior should be designed explicitly</option>
                <option :value="false">No special recovery posture</option>
              </select>
            </label>
            <label id="authority-blocked-failure-posture" class="field">
              <span>When work is blocked or fails</span>
              <select v-model="definition.authority.blocked_failure_posture" class="select">
                <option v-for="option in FAILURE_POSTURE_OPTIONS" :key="option.value || 'none'" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
              <small class="hint">{{ FAILURE_POSTURE_OPTIONS.find((option) => option.value === definition.authority.blocked_failure_posture)?.description }}</small>
            </label>
          </div>
        </article>
      </section>
    </template>
  </div>
</template>

<style scoped src="./developer-definition-shared.css"></style>
<style scoped>
.panel > .panel-copy {
  max-width: 92rem;
  margin: 0 0 1.25rem;
}

.panel-header {
  margin-bottom: 1.15rem;
}

.panel-header h2,
.section-head h3 {
  margin: 0;
}

.section-head h4 {
  margin: 0;
  font-size: 14px;
}

.settings-grid {
  gap: 1rem;
}

.field {
  gap: 0.5rem;
}

.field > span,
.summary-label {
  margin: 0;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.input,
.select,
.textarea {
  background: var(--surface-depth-control);
}

.textarea {
  min-height: 8.5rem;
}

.hint {
  display: block;
  margin-top: 0.1rem;
}

.intent-intro {
  margin-bottom: 1.3rem;
}

.topology-intro {
  margin-bottom: 1.3rem;
}

.binding-description {
  margin: 0 0 1.15rem;
  color: var(--text-secondary);
  line-height: 1.55;
}

.source-confirmation-card,
.source-confirmation-card strong {
  display: block;
  margin-bottom: 0.35rem;
  color: #e2e8f0;
  font-size: 13px;
  font-weight: 800;
}

.source-confirmation-card p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.5;
}

.source-confirmation-card small {
  display: block;
  margin-top: 0.5rem;
  color: rgba(148, 163, 184, 0.86);
  font-size: 12px;
  line-height: 1.45;
}

.formalized-capabilities-field {
  margin-bottom: 0.8rem;
}

.owned-concepts-field {
  margin-bottom: 0.8rem;
}

.binding-list {
  display: flex;
  flex-direction: column;
  gap: 1.1rem;
}

.binding-card {
  scroll-margin-top: 6rem;
  border: 1px solid var(--surface-border-card);
  border-radius: 18px;
  padding: 1.1rem;
  background: var(--surface-depth-card);
  box-shadow: var(--surface-shadow-card);
}

.binding-card.anchored-card {
  border-color: rgba(125, 211, 252, 0.72);
  background:
    radial-gradient(circle at top left, rgba(14, 165, 233, 0.2), transparent 34%),
    rgba(15, 23, 42, 0.34);
  box-shadow: 0 0 0 1px rgba(125, 211, 252, 0.26), 0 20px 54px rgba(14, 165, 233, 0.16);
}

.binding-card.field-error-card {
  border-color: rgba(248, 113, 113, 0.66);
  background:
    linear-gradient(135deg, rgba(127, 29, 29, 0.26), rgba(15, 23, 42, 0.28)),
    rgba(15, 23, 42, 0.24);
  box-shadow: 0 0 0 1px rgba(248, 113, 113, 0.18), 0 18px 40px rgba(127, 29, 29, 0.12);
}

.binding-card .section-head {
  margin-bottom: 1rem;
  padding-bottom: 0.9rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
}

.binding-card .section-head h3 {
  font-size: 18px;
  line-height: 1.35;
}

.binding-card .compact-head {
  margin-bottom: 0.85rem;
  padding-bottom: 0.7rem;
}

.section-hint {
  margin: 0.25rem 0 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.45;
}

.service-runtime-backends {
  margin-top: 1rem;
  border: 1px solid var(--surface-border-card);
  border-radius: 16px;
  padding: 1rem;
  background: var(--surface-depth-card-nested);
  box-shadow: var(--surface-shadow-card-nested);
}

.service-runtime-backends.field-error-card {
  border-color: rgba(248, 113, 113, 0.66);
  background:
    linear-gradient(135deg, rgba(127, 29, 29, 0.26), rgba(15, 23, 42, 0.28)),
    rgba(15, 23, 42, 0.24);
  box-shadow: 0 0 0 1px rgba(248, 113, 113, 0.18), 0 18px 40px rgba(127, 29, 29, 0.12);
}

.policy-enforcement-card {
  margin-top: 1rem;
}

.policy-enforcement-card .section-head {
  align-items: flex-start;
  margin-bottom: 0.8rem;
}

.policy-enforcement-card .section-head strong {
  display: block;
}

.policy-enforcement-list {
  display: grid;
  gap: 0.5rem;
}

.policy-enforcement-row {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
  align-items: stretch;
  padding: 0.75rem 0.85rem;
  border: 1px solid var(--surface-border-card);
  border-radius: 12px;
  background: var(--surface-depth-inset);
}

.policy-capability-title {
  color: var(--text-primary);
  font-size: 14px;
  line-height: 1.35;
}

.policy-permission-count {
  color: var(--text-secondary);
  font-weight: 700;
  font-size: 12px;
}

.policy-permission-list {
  margin: 0;
  color: #7891b7;
  font-family: "IBM Plex Sans", "Aptos", "Segoe UI", sans-serif;
  font-size: 12.5px;
  font-weight: 600;
  font-style: italic;
  line-height: 1.55;
  overflow-wrap: anywhere;
}

.policy-enforcement-row p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.45;
}

.inline-field-error {
  margin: 0.5rem 0 0;
  color: #fecaca;
  font-size: 13px;
  font-weight: 700;
  line-height: 1.45;
}

.binding-card > .panel-copy:not(.binding-description) {
  margin: 0 0 1.15rem;
  color: var(--text-secondary);
  line-height: 1.55;
}

.chip-grid {
  margin-top: 0.15rem;
}

.chip {
  max-width: 100%;
  overflow-wrap: anywhere;
  text-align: left;
}

.readonly-chip {
  cursor: default;
  user-select: text;
}

.readonly-chip:not(.active) {
  border-color: rgba(248, 113, 113, 0.52);
  background: rgba(127, 29, 29, 0.18);
  color: #fecaca;
}

.inline-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem;
  margin-top: 0.85rem;
}

.field.field-error {
  border: 1px solid rgba(248, 113, 113, 0.62);
  border-radius: 14px;
  padding: 0.8rem;
  background: rgba(127, 29, 29, 0.16);
}

.field.field-error .input,
.field.field-error .select,
.field.field-error .textarea {
  border-color: rgba(248, 113, 113, 0.72);
  box-shadow: 0 0 0 1px rgba(248, 113, 113, 0.18);
}

.field-error-copy {
  display: block;
  margin-top: 0.25rem;
  color: #fecaca;
  font-size: 12px;
  font-weight: 800;
  line-height: 1.4;
}

#authority-approval .settings-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

#authority-approval .field:nth-last-child(-n + 2) {
  grid-column: span 3;
}

@media (max-width: 1180px) {
  #authority-approval .settings-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  #authority-approval .field:nth-last-child(-n + 2) {
    grid-column: span 2;
  }
}

@media (max-width: 960px) {
  #authority-approval .settings-grid {
    grid-template-columns: 1fr;
  }

  #authority-approval .field:nth-last-child(-n + 2) {
    grid-column: span 1;
  }
}
</style>
