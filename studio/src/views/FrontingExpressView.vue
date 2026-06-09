<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  findIntegrationFrontingMappingArtifacts,
  resolveIntegrationFrontingBackendBindingsHealth,
} from '../design/developer-definition'
import { listIntegrationDiscoveryRecords, listWorkspaceConnections } from '../design/project-api'
import { loadProject, projectStore } from '../design/project-store'
import { firstProductDesignGateMessage, productDesignGate } from '../design/project-workflow'
import {
  hasFrontingIntegrationSource,
  hasFrontingIntentSource,
} from '../design/source-documents'
import type {
  BackendInputMode,
  DeveloperIntegrationFrontingBackendBinding,
  IntegrationBackendKind,
  IntegrationDiscoveryRecord,
  WorkspaceConnection,
} from '../design/project-types'

type StepState = 'done' | 'active' | 'blocked'

const route = useRoute()
const router = useRouter()

const projectId = computed(() => route.params.projectId as string)
const project = computed(() => projectStore.activeProject)
const workspace = computed(() => projectStore.activeWorkspace)
const loading = computed(() => projectStore.loading)
const error = computed(() => projectStore.error)
const readOnlyMode = computed(() => projectStore.runtimeStatus?.read_only_mode !== false)
const isGovernedFrontingProject = computed(() => project.value?.project_type === 'governed_service_project')

const connections = ref<WorkspaceConnection[]>([])
const discoveryRecords = ref<IntegrationDiscoveryRecord[]>([])
const refreshError = ref<string | null>(null)

function routeTo(path: string) {
  router.push(path)
}

function connectionAllowedForProject(connection: WorkspaceConnection, activeProjectId: string): boolean {
  if (!activeProjectId) return false
  return connection.allowed_project_refs.length === 0 || connection.allowed_project_refs.includes(activeProjectId)
}

async function refresh() {
  if (!projectId.value) return
  refreshError.value = null
  try {
    await loadProject(projectId.value)
    if (project.value?.workspace_id) {
      const workspaceConnections = await listWorkspaceConnections(project.value.workspace_id)
      connections.value = workspaceConnections.filter((connection) =>
        connectionAllowedForProject(connection, project.value?.id ?? ''),
      )
    } else {
      connections.value = []
    }
    discoveryRecords.value = await listIntegrationDiscoveryRecords(projectId.value)
  } catch (err) {
    refreshError.value = err instanceof Error ? err.message : String(err)
  }
}

onMounted(refresh)
watch(projectId, refresh)

const sourceDocumentCount = computed(() => projectStore.artifacts.documents.length || project.value?.documents_count || 0)
const frontingIntentReady = computed(() => hasFrontingIntentSource(projectStore.artifacts.documents))
const frontingIntegrationReady = computed(() => hasFrontingIntegrationSource(projectStore.artifacts.documents))
const sourceEvidenceReady = computed(() => frontingIntentReady.value && frontingIntegrationReady.value)
const mappingArtifacts = computed(() => findIntegrationFrontingMappingArtifacts(projectStore.artifacts.pmArtifacts))
const productGate = computed(() =>
  productDesignGate({
    project: project.value,
    pmArtifacts: projectStore.artifacts.pmArtifacts,
    requirements: projectStore.artifacts.requirements,
    scenarios: projectStore.artifacts.scenarios,
    documents: projectStore.artifacts.documents,
    shapes: projectStore.artifacts.shapes,
  }),
)

function text(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.map(item => String(item).trim()).filter(Boolean)
}

function normalizeBackendKind(value: unknown): IntegrationBackendKind {
  const normalized = text(value)
  if (normalized === 'mcp' || normalized === 'database' || normalized === 'hybrid') return normalized
  return 'native_api'
}

function normalizeBackendInputMode(value: unknown): BackendInputMode {
  if (value === 'explicit' || value === 'hybrid') return value
  return 'implicit'
}

function bindingsFromMappingData(data: Record<string, unknown>): DeveloperIntegrationFrontingBackendBinding[] {
  const rawBindings = data.backend_bindings
  if (Array.isArray(rawBindings)) {
    return rawBindings
      .map((item) => {
        const source = item && typeof item === 'object' ? item as Record<string, unknown> : {}
        return {
          backend_kind: normalizeBackendKind(source.backend_kind),
          connection_ref: text(source.connection_ref),
          raw_operation_refs: stringList(source.raw_operation_refs),
          backend_input_mode: normalizeBackendInputMode(source.backend_input_mode),
          derived_required_backend_inputs: stringList(source.derived_required_backend_inputs),
          derived_optional_backend_inputs: stringList(source.derived_optional_backend_inputs),
          explicit_required_backend_inputs: stringList(source.explicit_required_backend_inputs),
          explicit_optional_backend_inputs: stringList(source.explicit_optional_backend_inputs),
        }
      })
      .filter(binding => binding.connection_ref || binding.raw_operation_refs.length > 0)
  }

  const connectionRef = text(data.connection_ref)
  const operationRefs = stringList(data.raw_operation_refs)
  if (!connectionRef && operationRefs.length === 0) return []
  return [{
    backend_kind: normalizeBackendKind(data.backend_kind),
    connection_ref: connectionRef,
    raw_operation_refs: operationRefs,
    backend_input_mode: normalizeBackendInputMode(data.backend_input_mode),
    derived_required_backend_inputs: stringList(data.derived_required_backend_inputs),
    derived_optional_backend_inputs: stringList(data.derived_optional_backend_inputs),
    explicit_required_backend_inputs: stringList(data.explicit_required_backend_inputs),
    explicit_optional_backend_inputs: stringList(data.explicit_optional_backend_inputs),
  }]
}

const mappingHealth = computed(() =>
  mappingArtifacts.value.map((artifact) => {
    const bindings = bindingsFromMappingData(artifact.data ?? {})
    return {
      artifactId: artifact.id,
      capabilityId: text(artifact.data?.capability_id) || artifact.title,
      health: resolveIntegrationFrontingBackendBindingsHealth(bindings, discoveryRecords.value),
    }
  }),
)
const staleBindingCount = computed(() => mappingHealth.value.filter(item => item.health.status === 'stale').length)
const missingBindingCount = computed(() => mappingHealth.value.filter(item => item.health.status === 'missing').length)
const readyBindingCount = computed(() => mappingHealth.value.filter(item => item.health.status === 'ready').length)

const frontingReady = computed(() =>
  isGovernedFrontingProject.value
  && productGate.value.ready
  && sourceEvidenceReady.value
  && connections.value.length > 0
  && discoveryRecords.value.length > 0
  && mappingArtifacts.value.length > 0
  && staleBindingCount.value === 0
  && missingBindingCount.value === 0,
)

const setupStatus = computed(() => {
  if (!isGovernedFrontingProject.value) return 'Not a fronting project'
  if (!productGate.value.ready) return 'Complete Product Design'
  if (!sourceEvidenceReady.value) return 'Add intent and backend evidence'
  if (connections.value.length === 0) return 'Add connection reference'
  if (discoveryRecords.value.length === 0) return 'Record backend operations'
  if (mappingArtifacts.value.length === 0) return 'Map governed capabilities'
  if (missingBindingCount.value > 0) return 'Complete backend bindings'
  if (staleBindingCount.value > 0) return 'Refresh stale mappings'
  return 'Ready for contract definition'
})

const workflowSteps = computed<Array<{ title: string; copy: string; state: StepState; metric: string }>>(() => {
  const hasSourceEvidence = sourceEvidenceReady.value
  const hasConnections = connections.value.length > 0
  const hasDiscovery = discoveryRecords.value.length > 0
  const hasMappings = mappingArtifacts.value.length > 0 && missingBindingCount.value === 0 && staleBindingCount.value === 0
  return [
    {
      title: 'Product Design',
      copy: 'Finish and review business intent, actors, permission posture, requirements, and scenarios before backend mapping becomes contract truth.',
      state: productGate.value.ready ? 'done' : 'active',
      metric: productGate.value.ready ? 'ready' : `${productGate.value.count} issue${productGate.value.count === 1 ? '' : 's'}`,
    },
    {
      title: 'Fronting evidence',
      copy: 'Attach intent plus API/MCP/backend evidence. This replaces the generic “write a full business spec first” starting point.',
      state: hasSourceEvidence ? 'done' : productGate.value.ready ? 'active' : 'blocked',
      metric: `${frontingIntentReady.value ? 1 : 0}/1 intent · ${frontingIntegrationReady.value ? 1 : 0}/1 backend`,
    },
    {
      title: 'Connection refs',
      copy: 'Reference credentials and endpoints without storing secrets in the contract.',
      state: hasConnections ? 'done' : hasSourceEvidence ? 'active' : 'blocked',
      metric: `${connections.value.length} connection${connections.value.length === 1 ? '' : 's'}`,
    },
    {
      title: 'Raw backend supply',
      copy: 'Record available operations as implementation supply, not as agent-facing behavior.',
      state: hasDiscovery ? 'done' : hasConnections ? 'active' : 'blocked',
      metric: `${discoveryRecords.value.length} operation${discoveryRecords.value.length === 1 ? '' : 's'}`,
    },
    {
      title: 'Governed capabilities',
      copy: 'Curate selected backend operations into reviewed ANIP capabilities, approvals, denials, and audit posture.',
      state: hasMappings ? 'done' : hasDiscovery ? 'active' : 'blocked',
      metric: `${mappingArtifacts.value.length} mapping${mappingArtifacts.value.length === 1 ? '' : 's'}`,
    },
  ]
})

const advancedPages = computed(() => project.value ? [
  {
    title: 'Advanced Setup',
    copy: 'Edit connection refs, discovery records, and capability mappings.',
    path: `/design/projects/${project.value.id}/developer/integration-fronting`,
  },
  {
    title: 'Source Docs',
    copy: 'Attach API docs, MCP surfaces, permission matrices, and policy evidence.',
    path: `/design/projects/${project.value.id}/source-docs`,
  },
  {
    title: 'Developer Definition',
    copy: 'Inspect the contract evidence consumed by generation and verification.',
    path: `/design/projects/${project.value.id}/developer/definition`,
  },
  {
    title: 'Full Studio',
    copy: 'Open the complete PM and developer design workspace.',
    path: `/design/projects/${project.value.id}`,
  },
] : [])

const primaryAction = computed(() => {
  if (!project.value) return null
  if (!productGate.value.ready) {
    return {
      label: 'Complete Product Design',
      path: `/design/projects/${project.value.id}/pm`,
    }
  }
  if (!sourceEvidenceReady.value) {
    return {
      label: 'Add Fronting Evidence',
      path: `/design/projects/${project.value.id}/source-docs`,
    }
  }
  if (!frontingReady.value) {
    return {
      label: 'Continue Express Setup',
      path: `/design/projects/${project.value.id}/developer/integration-fronting`,
    }
  }
  return {
    label: 'Review Developer Definition',
    path: `/design/projects/${project.value.id}/developer/definition`,
  }
})
</script>

<template>
  <div class="fronting-express">
    <div v-if="loading && !project" class="empty-state">Loading fronting project...</div>
    <div v-else-if="error || refreshError" class="banner banner-error">{{ error || refreshError }}</div>
    <template v-else-if="project">
      <section class="hero">
        <div>
          <div class="hero-kicker">{{ workspace?.name || 'Workspace' }} · Express Mode</div>
          <h1>Govern an existing API or MCP service</h1>
          <p>
            Start from backend supply, expose only reviewed ANIP capabilities, and keep raw tools out of the agent-facing contract.
            Advanced Studio pages remain available when you need full control.
          </p>
        </div>
        <div class="hero-status" :class="{ ready: frontingReady }">
          <span>{{ setupStatus }}</span>
          <strong>{{ frontingReady ? 'Ready' : 'Needs setup' }}</strong>
        </div>
      </section>

      <section v-if="!isGovernedFrontingProject" class="panel">
        <h2>Express fronting is not enabled</h2>
        <p>This mode is for projects created as governed wrappers around existing API, MCP, database, or hybrid backends.</p>
        <button class="btn btn-primary" @click="routeTo(`/design/projects/${project.id}`)">Open Project Dashboard</button>
      </section>

      <template v-else>
        <section v-if="!productGate.ready" class="banner banner-warning workflow-gate">
          <strong>Product Design comes first.</strong>
          <span>{{ firstProductDesignGateMessage(productGate) }}</span>
        </section>

        <section class="summary-grid">
          <article class="summary-card">
            <span class="summary-label">Source docs</span>
            <strong>{{ sourceDocumentCount }}</strong>
            <p>
              Intent {{ frontingIntentReady ? 'ready' : 'needed' }} · backend evidence {{ frontingIntegrationReady ? 'ready' : 'needed' }}.
            </p>
          </article>
          <article class="summary-card">
            <span class="summary-label">Connections</span>
            <strong>{{ connections.length }}</strong>
            <p>Endpoint and credential references; no secrets are stored in the contract.</p>
          </article>
          <article class="summary-card">
            <span class="summary-label">Backend operations</span>
            <strong>{{ discoveryRecords.length }}</strong>
            <p>Raw operations discovered or entered as supply for wrapper implementation.</p>
          </article>
          <article class="summary-card">
            <span class="summary-label">Capability mappings</span>
            <strong>{{ mappingArtifacts.length }}</strong>
            <p>{{ readyBindingCount }} ready · {{ missingBindingCount }} missing · {{ staleBindingCount }} stale</p>
          </article>
        </section>

        <section class="panel">
          <div class="panel-header">
            <div>
              <h2>Express Checklist</h2>
              <p>
                Most fronting projects should start here: attach evidence, select backend supply, curate governed capabilities, then review the generated contract. Full Studio pages remain available, but they are not the primary path.
              </p>
            </div>
            <button class="btn btn-secondary" @click="refresh">Refresh</button>
          </div>
          <div class="step-list">
            <article v-for="step in workflowSteps" :key="step.title" class="step-card" :class="step.state">
              <div class="step-state">{{ step.state }}</div>
              <div>
                <h3>{{ step.title }}</h3>
                <p>{{ step.copy }}</p>
              </div>
              <strong>{{ step.metric }}</strong>
            </article>
          </div>
        </section>

        <section class="action-row">
          <button v-if="primaryAction" class="btn btn-primary" @click="routeTo(primaryAction.path)">
            {{ primaryAction.label }}
          </button>
          <button class="btn btn-secondary" @click="routeTo(`/design/projects/${project.id}/developer/assistant`)">
            Open Assistant
          </button>
          <button class="btn btn-secondary" @click="routeTo(`/design/projects/${project.id}/verification`)">
            Open Verification
          </button>
        </section>

        <details class="panel advanced-panel">
          <summary>
            <span>Show Advanced Studio Pages</span>
            <em v-if="readOnlyMode">Read only</em>
          </summary>
          <p>
            Express Mode intentionally hides most page navigation. Open these pages when you need deterministic editing, detailed mapping, or contract inspection.
          </p>
          <div class="advanced-grid">
            <button v-for="page in advancedPages" :key="page.title" class="advanced-card" @click="routeTo(page.path)">
              <span>{{ page.title }}</span>
              <p>{{ page.copy }}</p>
            </button>
          </div>
        </details>
      </template>
    </template>
  </div>
</template>

<style scoped>
.fronting-express {
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

.hero h1 {
  margin: 0 0 0.5rem;
  color: var(--text-primary);
  font-size: 30px;
  line-height: 1.1;
}

.hero p {
  max-width: 72ch;
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.6;
}

.hero-kicker,
.summary-label,
.step-state {
  color: var(--text-secondary);
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.hero-status {
  min-width: 12rem;
  border: 1px solid var(--surface-border-panel);
  border-radius: 18px;
  padding: 0.9rem 1rem;
  background: var(--surface-depth-panel);
  color: var(--text-secondary);
}

.hero-status.ready {
  border-color: rgba(52, 211, 153, 0.35);
  background: linear-gradient(135deg, rgba(52, 211, 153, 0.08), transparent), var(--surface-depth-panel);
}

.hero-status span,
.hero-status strong {
  display: block;
}

.hero-status strong {
  margin-top: 0.25rem;
  color: var(--text-primary);
  font-size: 1.4rem;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1rem;
  margin-top: 1.25rem;
}

.summary-card,
.panel {
  border: 1px solid var(--surface-border-panel);
  border-radius: 18px;
  background: var(--surface-depth-panel);
}

.summary-card {
  padding: 1.25rem;
}

.summary-card strong {
  display: block;
  margin: 0.45rem 0;
  font-size: 2rem;
  color: var(--text-primary);
}

.summary-card p,
.panel p,
.step-card p,
.advanced-card p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.55;
}

.panel {
  margin-top: 1.25rem;
  padding: 1.5rem;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: start;
  margin-bottom: 1rem;
}

.panel-header h2,
.step-card h3 {
  margin: 0 0 0.3rem;
  color: var(--text-primary);
}

.step-list {
  display: grid;
  gap: 0.75rem;
}

.step-card {
  display: grid;
  grid-template-columns: 5.5rem minmax(0, 1fr) auto;
  gap: 1rem;
  align-items: center;
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  padding: 1rem;
  background: var(--surface-depth-card);
}

.step-card.done {
  border-color: rgba(52, 211, 153, 0.28);
  background: linear-gradient(135deg, rgba(52, 211, 153, 0.08), transparent), var(--surface-depth-card);
}

.step-card.active {
  border-color: rgba(96, 165, 250, 0.28);
  background: linear-gradient(135deg, rgba(96, 165, 250, 0.08), transparent), var(--surface-depth-card);
}

.step-card.blocked {
  opacity: 0.66;
}

.step-card strong {
  white-space: nowrap;
  color: var(--text-primary);
}

.action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-top: 1.25rem;
}

.advanced-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.75rem;
  margin-top: 1rem;
}

.advanced-panel > summary {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: center;
  color: var(--text-primary);
  cursor: pointer;
  font-weight: 800;
  list-style: none;
}

.advanced-panel > summary::-webkit-details-marker {
  display: none;
}

.advanced-panel > summary::after {
  content: '+';
  display: grid;
  place-items: center;
  width: 1.75rem;
  height: 1.75rem;
  border: 1px solid var(--surface-border-card);
  border-radius: 999px;
  color: var(--text-secondary);
}

.advanced-panel[open] > summary::after {
  content: '-';
}

.advanced-panel > summary em {
  margin-left: auto;
  color: var(--text-secondary);
  font-style: normal;
  font-size: 0.82rem;
}

.advanced-panel > p {
  margin: 0.75rem 0 0;
}

.advanced-card {
  text-align: left;
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  padding: 1rem;
  background: var(--surface-depth-card);
  color: inherit;
  cursor: pointer;
}

.advanced-card:hover {
  border-color: rgba(96, 165, 250, 0.34);
  transform: translateY(-1px);
}

.advanced-card span {
  display: block;
  margin-bottom: 0.4rem;
  color: var(--text-primary);
  font-weight: 800;
}

.status-chip {
  border-radius: 999px;
  padding: 0.35rem 0.7rem;
  background: var(--surface-depth-card);
  color: var(--text-secondary);
  font-size: 0.78rem;
  font-weight: 800;
}

.banner,
.empty-state {
  border-radius: 16px;
  padding: 1rem;
  background: var(--surface-depth-panel);
  color: var(--text-secondary);
}

.banner-error {
  border: 1px solid rgba(248, 113, 113, 0.24);
  background: rgba(248, 113, 113, 0.1);
  color: var(--text-primary);
}

.banner-warning {
  display: grid;
  gap: 0.25rem;
  border: 1px solid rgba(251, 191, 36, 0.28);
  background: rgba(251, 191, 36, 0.1);
  color: var(--text-primary);
}

.banner-warning span {
  color: var(--text-secondary);
}

.workflow-gate {
  margin-bottom: 1rem;
}

.btn {
  border: 0;
  border-radius: 999px;
  padding: 0.72rem 1rem;
  font-weight: 800;
  cursor: pointer;
}

.btn-primary {
  background: var(--accent-primary, #2563eb);
  color: #ffffff;
}

.btn-secondary {
  border: 1px solid var(--surface-border-card);
  background: var(--surface-depth-card);
  color: var(--text-primary);
}

@media (max-width: 1000px) {
  .hero,
  .summary-grid,
  .advanced-grid {
    grid-template-columns: 1fr;
  }

  .step-card {
    grid-template-columns: 1fr;
  }
}
</style>
