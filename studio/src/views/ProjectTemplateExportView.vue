<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  findLatestDeveloperDefinitionRevisionArtifact,
  INTEGRATION_FRONTING_MAPPING_ARTIFACT_TYPE,
} from '../design/developer-definition'
import { loadProject, projectStore } from '../design/project-store'
import {
  getProjectDocumentPreview,
  listIntegrationDiscoveryRecords,
  listWorkspaceConnections,
  publishRegistryTemplate,
} from '../design/project-api'
import type {
  DeveloperDefinitionRevisionData,
  IntegrationDiscoveryRecord,
  WorkspaceConnection,
} from '../design/project-types'
import { buildStarterTemplatePackageFromProject } from '../design/starter-template-export'
import type { StarterTemplatePackage } from '../design/starter-template-package'
import { downloadJson } from '../design/download'

const route = useRoute()
const router = useRouter()

const projectId = computed(() => route.params.projectId as string)
const project = computed(() => projectStore.activeProject)
const workspace = computed(() => projectStore.activeWorkspace)
const loading = computed(() => projectStore.loading || templateExportLoading.value)
const error = computed(() => projectStore.error)

const templateExportLoading = ref(false)
const templateExportError = ref<string | null>(null)
const templateExportConnections = ref<WorkspaceConnection[]>([])
const templateExportDiscoveryRecords = ref<IntegrationDiscoveryRecord[]>([])
const selectedTemplateDocumentIds = ref<string[]>([])
const selectedTemplateConnectionIds = ref<string[]>([])
const selectedTemplateDiscoveryRecordIds = ref<string[]>([])
const selectedTemplateMappingArtifactIds = ref<string[]>([])
const templatePublishResult = ref<string | null>(null)
const readOnlyMode = computed(() => projectStore.runtimeStatus?.read_only_mode !== false)
const readOnlyReason = computed(() =>
  projectStore.runtimeStatus?.read_only_reason
  || 'Studio is running in read-only mode. Explore the design, then download and run Studio locally to make changes.',
)

const frontingMappingArtifacts = computed(() =>
  projectStore.artifacts.pmArtifacts.filter((artifact) => artifact.data?.artifact_type === INTEGRATION_FRONTING_MAPPING_ARTIFACT_TYPE),
)

const latestDeveloperDefinitionRevision = computed<DeveloperDefinitionRevisionData | null>(() =>
  (findLatestDeveloperDefinitionRevisionArtifact(projectStore.artifacts.pmArtifacts)?.data as DeveloperDefinitionRevisionData | undefined) ?? null,
)

const selectedCounts = computed(() => ({
  documents: selectedTemplateDocumentIds.value.length,
  connections: selectedTemplateConnectionIds.value.length,
  operations: selectedTemplateDiscoveryRecordIds.value.length,
  mappings: selectedTemplateMappingArtifactIds.value.length,
}))

function connectionAllowedForProject(connection: WorkspaceConnection, activeProjectId: string): boolean {
  return connection.allowed_project_refs.length === 0 || connection.allowed_project_refs.includes(activeProjectId)
}

async function ensureLoaded() {
  if (!projectId.value) return
  if (projectStore.activeProject?.id !== projectId.value || projectStore.artifacts.documents.length === 0) {
    await loadProject(projectId.value)
  }
  await loadTemplateExportInputs()
}

async function loadTemplateExportInputs() {
  if (!project.value) return
  templateExportLoading.value = true
  templateExportError.value = null
  templatePublishResult.value = null
  try {
    const [workspaceConnections, discoveryRecords] = await Promise.all([
      listWorkspaceConnections(project.value.workspace_id),
      listIntegrationDiscoveryRecords(project.value.id),
    ])
    templateExportConnections.value = workspaceConnections.filter((connection) =>
      connectionAllowedForProject(connection, project.value?.id ?? ''),
    )
    templateExportDiscoveryRecords.value = discoveryRecords
    selectedTemplateDocumentIds.value = []
    selectedTemplateConnectionIds.value = templateExportConnections.value.map((connection) => connection.id)
    selectedTemplateDiscoveryRecordIds.value = discoveryRecords.map((record) => record.id)
    selectedTemplateMappingArtifactIds.value = frontingMappingArtifacts.value.map((artifact) => artifact.id)
  } catch (err) {
    templateExportError.value = err instanceof Error ? err.message : String(err)
  } finally {
    templateExportLoading.value = false
  }
}

async function buildSelectedStarterTemplatePackage(): Promise<StarterTemplatePackage> {
  if (!project.value) throw new Error('Project is not loaded.')
  const documentInputs = await Promise.all(
    projectStore.artifacts.documents
      .filter((document) => selectedTemplateDocumentIds.value.includes(document.id))
      .map(async (document) => ({
        record: document,
        content: (await getProjectDocumentPreview(project.value!.id, document.id)).content,
      })),
  )
  return buildStarterTemplatePackageFromProject({
    project: project.value,
    documents: documentInputs,
    connections: templateExportConnections.value,
    discoveryRecords: templateExportDiscoveryRecords.value,
    mappingArtifacts: frontingMappingArtifacts.value,
    developerDefinition: latestDeveloperDefinitionRevision.value,
    selection: {
      documentIds: selectedTemplateDocumentIds.value,
      connectionIds: selectedTemplateConnectionIds.value,
      discoveryRecordIds: selectedTemplateDiscoveryRecordIds.value,
      mappingArtifactIds: selectedTemplateMappingArtifactIds.value,
    },
  })
}

async function withTemplatePackage(action: (pkg: StarterTemplatePackage) => Promise<void> | void) {
  if (templateExportLoading.value) return
  templateExportLoading.value = true
  templateExportError.value = null
  templatePublishResult.value = null
  try {
    await action(await buildSelectedStarterTemplatePackage())
  } catch (err) {
    templateExportError.value = err instanceof Error ? err.message : String(err)
  } finally {
    templateExportLoading.value = false
  }
}

async function exportStarterTemplatePackage() {
  if (readOnlyMode.value) {
    templateExportError.value = readOnlyReason.value
    return
  }
  await withTemplatePackage((pkg) => {
    downloadJson(pkg as unknown as Record<string, any>, `${pkg.template.id}-${pkg.package_version}.anip-template.json`)
  })
}

async function publishStarterTemplatePackage() {
  if (readOnlyMode.value) {
    templateExportError.value = readOnlyReason.value
    return
  }
  await withTemplatePackage(async (pkg) => {
    const result = await publishRegistryTemplate({
      template_id: pkg.template.id,
      template_version: pkg.package_version,
      manifest: pkg.manifest as unknown as Record<string, any>,
      template: pkg.template as unknown as Record<string, any>,
      package: pkg as unknown as Record<string, any>,
    })
    templatePublishResult.value = `Published ${result.template.template_id}@${result.template.template_version} to the Registry template catalog.`
  })
}

function openProjectDashboard() {
  if (!projectId.value) return
  router.push(`/design/projects/${projectId.value}`)
}

onMounted(ensureLoaded)
watch(projectId, ensureLoaded)
</script>

<template>
  <div class="template-export-page">
    <div v-if="loading && !project" class="empty-state">Loading template export...</div>
    <div v-else-if="error" class="banner banner-error">{{ error }}</div>
    <template v-else-if="project">
      <section class="hero">
        <div class="hero-copy">
          <div class="hero-kicker">{{ workspace?.name || 'Workspace' }}</div>
          <h1 class="hero-title">Create Starter Template</h1>
          <p class="hero-summary">
            Export selected material from {{ project.name }} as a reusable template package. Source documents are opt-in, and secrets are never exported.
          </p>
        </div>
        <div class="hero-actions">
          <button class="btn btn-secondary" @click="openProjectDashboard">Back To Project</button>
          <button class="btn btn-secondary" :disabled="templateExportLoading" @click="loadTemplateExportInputs">
            Refresh Inputs
          </button>
        </div>
      </section>

      <div v-if="readOnlyMode" class="readonly-banner">
        <strong>Read-only showcase mode</strong>
        <span>{{ readOnlyReason }} Template selection, download, and Registry publication are disabled in the hosted preview.</span>
      </div>

      <section class="summary-grid">
        <article class="summary-card">
          <span>Source Docs</span>
          <strong>{{ selectedCounts.documents }}</strong>
          <small>Opt-in only</small>
        </article>
        <article class="summary-card">
          <span>Connection Refs</span>
          <strong>{{ selectedCounts.connections }}</strong>
          <small>No secret values</small>
        </article>
        <article class="summary-card">
          <span>Backend Operations</span>
          <strong>{{ selectedCounts.operations }}</strong>
          <small>Starter supply</small>
        </article>
        <article class="summary-card">
          <span>Capability Mappings</span>
          <strong>{{ selectedCounts.mappings }}</strong>
          <small>Suggested mappings</small>
        </article>
      </section>

      <section class="panel">
        <div class="panel-header">
          <div>
            <h2>Template Contents</h2>
            <p>
              Choose exactly what goes into the reusable template. Keep source docs narrow and intentional; exported markdown can contain customer or internal details.
            </p>
          </div>
          <span class="status-chip">Selective export</span>
        </div>

        <div v-if="templateExportError" class="banner banner-error template-export-error">{{ templateExportError }}</div>
        <div v-if="templatePublishResult" class="banner banner-success template-export-error">{{ templatePublishResult }}</div>

        <div class="template-export-grid">
          <section class="template-export-section">
            <h3>Source Docs</h3>
            <p>Opt in only docs that are safe to share as starter evidence. Markdown content is included for selected docs.</p>
            <label
              v-for="document in projectStore.artifacts.documents"
              :key="document.id"
              class="template-export-row"
            >
              <input v-model="selectedTemplateDocumentIds" type="checkbox" :value="document.id" :disabled="readOnlyMode" />
              <span>
                <strong>{{ document.title }}</strong>
                <small>{{ document.kind }} · {{ document.filename }}</small>
              </span>
            </label>
            <div v-if="projectStore.artifacts.documents.length === 0" class="empty-inline">No source docs available.</div>
          </section>

          <section class="template-export-section">
            <h3>Connection Refs</h3>
            <p>Exports endpoint/auth/secret references only, not token values.</p>
            <label
              v-for="connection in templateExportConnections"
              :key="connection.id"
              class="template-export-row"
            >
              <input v-model="selectedTemplateConnectionIds" type="checkbox" :value="connection.id" :disabled="readOnlyMode" />
              <span>
                <strong>{{ connection.display_name }}</strong>
                <small>{{ connection.backend_kind }} · {{ connection.secret_ref }}</small>
              </span>
            </label>
            <div v-if="templateExportConnections.length === 0" class="empty-inline">No project-scoped connections available.</div>
          </section>

          <section class="template-export-section">
            <h3>Backend Operations</h3>
            <p>Include only operations that should be starter supply for future projects.</p>
            <label
              v-for="record in templateExportDiscoveryRecords"
              :key="record.id"
              class="template-export-row"
            >
              <input v-model="selectedTemplateDiscoveryRecordIds" type="checkbox" :value="record.id" :disabled="readOnlyMode" />
              <span>
                <strong>{{ record.operation_id }}</strong>
                <small>{{ record.method }} {{ record.path_template }}</small>
              </span>
            </label>
            <div v-if="templateExportDiscoveryRecords.length === 0" class="empty-inline">No backend operations available.</div>
          </section>

          <section class="template-export-section">
            <h3>Capability Mappings</h3>
            <p>Exports template-suggested mappings, not locked contract truth.</p>
            <label
              v-for="artifact in frontingMappingArtifacts"
              :key="artifact.id"
              class="template-export-row"
            >
              <input v-model="selectedTemplateMappingArtifactIds" type="checkbox" :value="artifact.id" :disabled="readOnlyMode" />
              <span>
                <strong>{{ artifact.title }}</strong>
                <small>{{ artifact.data.capability_id || artifact.id }}</small>
              </span>
            </label>
            <div v-if="frontingMappingArtifacts.length === 0" class="empty-inline">No fronting capability mappings available.</div>
          </section>
        </div>

        <div class="template-export-actions">
          <button
            class="btn btn-primary"
            :disabled="readOnlyMode || templateExportLoading"
            @click="exportStarterTemplatePackage"
          >
            {{ templateExportLoading ? 'Preparing...' : 'Download Template Package' }}
          </button>
          <button
            class="btn btn-secondary"
            :disabled="readOnlyMode || templateExportLoading"
            @click="publishStarterTemplatePackage"
          >
            Publish To Registry
          </button>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.template-export-page {
  width: 100%;
  max-width: none;
  padding: 2rem;
}

.hero {
  display: flex;
  justify-content: space-between;
  gap: 1.5rem;
  align-items: flex-start;
  margin-bottom: 1.75rem;
}

.hero-copy {
  flex: 1;
  min-width: 0;
}

.hero-kicker {
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-secondary);
  margin-bottom: 0.5rem;
}

.hero-title {
  margin: 0 0 0.5rem;
  font-size: 30px;
  line-height: 1.1;
  color: var(--text-primary);
}

.hero-summary {
  margin: 0;
  max-width: 78ch;
  color: var(--text-secondary);
  line-height: 1.6;
}

.readonly-banner {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem 0.7rem;
  align-items: center;
  margin: 0 0 1rem;
  padding: 0.85rem 1rem;
  border: 1px solid rgba(251, 191, 36, 0.34);
  border-radius: 16px;
  background: rgba(251, 191, 36, 0.1);
  color: #fde68a;
}

.readonly-banner span {
  color: var(--text-secondary);
}

.hero-actions {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1rem;
  margin-bottom: 1rem;
}

.summary-card {
  display: grid;
  gap: 0.35rem;
  padding: 1rem;
  border: 1px solid var(--surface-border-card);
  border-radius: 16px;
  background: var(--surface-depth-card);
}

.summary-card span,
.summary-card small {
  color: var(--text-secondary);
}

.summary-card strong {
  color: var(--text-primary);
  font-size: 28px;
  line-height: 1;
}

.panel {
  background: var(--surface-depth-panel);
  border: 1px solid var(--surface-border-panel);
  border-radius: 18px;
  padding: 1.25rem;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
  margin-bottom: 0.9rem;
}

.panel-header h2,
.panel-header p {
  margin: 0;
}

.panel-header h2 {
  font-size: 18px;
  color: var(--text-primary);
}

.panel-header p {
  margin-top: 0.4rem;
  max-width: 84ch;
  color: var(--text-secondary);
  line-height: 1.6;
}

.status-chip {
  padding: 0.28rem 0.6rem;
  border-radius: 999px;
  font-size: 12px;
  background: rgba(148, 163, 184, 0.16);
  color: var(--text-secondary);
  white-space: nowrap;
}

.btn {
  border: 1px solid var(--surface-border-card);
  border-radius: 12px;
  padding: 0.75rem 1rem;
  font-size: 14px;
  cursor: pointer;
}

.btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.btn-primary {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}

.btn-secondary {
  background: var(--surface-depth-card);
  color: var(--text-primary);
}

.template-export-error {
  margin: 1rem 0 0;
}

.template-export-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
  margin-top: 1rem;
}

.template-export-section {
  display: grid;
  align-content: start;
  gap: 0.65rem;
  min-width: 0;
  padding: 1rem;
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  background: var(--surface-depth-card);
}

.template-export-section h3 {
  margin: 0;
  color: var(--text-primary);
  font-size: 15px;
}

.template-export-section p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.template-export-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 0.65rem;
  align-items: start;
  padding: 0.65rem;
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.28);
}

.template-export-row input {
  margin-top: 0.2rem;
}

.template-export-row span {
  display: grid;
  gap: 0.2rem;
  min-width: 0;
}

.template-export-row strong,
.template-export-row small {
  overflow-wrap: anywhere;
}

.template-export-row strong {
  color: var(--text-primary);
  font-size: 13px;
}

.template-export-row small {
  color: var(--text-muted);
  font-size: 11px;
}

.template-export-actions {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
  margin-top: 1rem;
}

.empty-inline,
.empty-state {
  color: var(--text-muted);
  font-size: 12px;
}

.banner {
  padding: 0.8rem 1rem;
  border-radius: 12px;
}

.banner-error {
  background: rgba(248, 113, 113, 0.12);
  border: 1px solid rgba(248, 113, 113, 0.28);
  color: var(--error);
}

.banner-success {
  background: rgba(34, 197, 94, 0.12);
  border: 1px solid rgba(34, 197, 94, 0.28);
  color: #166534;
}

@media (max-width: 1100px) {
  .summary-grid,
  .template-export-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .template-export-page {
    padding: 1.25rem;
  }

  .hero,
  .panel-header {
    flex-direction: column;
  }

  .summary-grid,
  .template-export-grid {
    grid-template-columns: 1fr;
  }
}
</style>
