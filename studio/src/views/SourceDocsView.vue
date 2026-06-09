<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  createProjectDocument,
  deleteProjectDocument,
  getProjectDocumentDownloadUrl,
  getProjectDocumentPreview,
} from '../design/project-api'
import { loadProject, projectStore, refreshArtifacts } from '../design/project-store'
import { requestConfirmation } from '../design/confirm'
import { formatStudioTimestamp } from '../design/time'
import {
  defaultDeveloperSourceDocumentKind,
  defaultSourceDocumentKind,
  developerSourceDocumentKindOptions,
  hasDeveloperSourceDocument,
  hasFrontingIntegrationSource,
  hasFrontingIntentSource,
  isDeveloperSourceDocument,
  isFrontingIntegrationSource,
  isProductSourceDocument,
  isGovernedFrontingProject,
  sourceDocumentKindLabel,
  sourceDocumentKindOptions,
} from '../design/source-documents'
import ProjectIssueBanner from '../components/ProjectIssueBanner.vue'
import { useProjectIssue } from '../design/use-project-issue'
import { developerBaselineMatchesCurrentContext, findDeveloperBaselineArtifact } from '../design/traceability'
import type { DeveloperBaselineData } from '../design/project-types'
import {
  buildDeveloperEvidenceScaffoldFiles,
  downloadDeveloperEvidenceScaffoldFile,
  type DeveloperEvidenceScaffoldFile,
} from '../design/developer-evidence-scaffold'

const route = useRoute()
const router = useRouter()

const projectId = computed(() => route.params.projectId as string)
const project = computed(() => projectStore.activeProject)
const documents = computed(() => projectStore.artifacts.documents)
const developerSourceMode = computed(() => route.meta.sourceDocsLane === 'dev')
const visibleDocuments = computed(() =>
  developerSourceMode.value
    ? documents.value.filter(isDeveloperSourceDocument)
    : governedFrontingProject.value
    ? documents.value.filter((document) =>
        isProductSourceDocument(document) || isFrontingIntegrationSource(document),
      )
    : documents.value.filter(isProductSourceDocument),
)
const loading = computed(() => projectStore.loading)
const error = computed(() => projectStore.error)
const readOnlyMode = computed(() => projectStore.runtimeStatus?.read_only_mode !== false)
const readOnlyReason = computed(() =>
  projectStore.runtimeStatus?.read_only_reason
  || 'Studio is running in read-only mode. Explore the design, then download and run Studio locally to make changes.',
)
const developerBaseline = computed(() =>
  (findDeveloperBaselineArtifact(projectStore.artifacts.pmArtifacts)?.data as DeveloperBaselineData | undefined) ?? null,
)
const developerBaselineLocked = computed(() =>
  developerBaselineMatchesCurrentContext({
    baseline: developerBaseline.value,
    requirements:
      projectStore.artifacts.requirements.find((item) => item.role === 'primary')
      ?? projectStore.artifacts.requirements[0]
      ?? null,
    scenarios: projectStore.artifacts.scenarios,
    shape:
      projectStore.artifacts.shapes.find((item) => item.id === projectStore.activeShapeId)
      ?? (projectStore.artifacts.shapes.length === 1 ? projectStore.artifacts.shapes[0] : null)
      ?? projectStore.artifacts.shapes[0]
      ?? null,
    pmArtifacts: projectStore.artifacts.pmArtifacts,
  }),
)
const productHandoffReady = computed(() =>
  (project.value?.requirements_count ?? projectStore.artifacts.requirements.length) > 0
  && (project.value?.scenarios_count ?? projectStore.artifacts.scenarios.length) > 0
  && (project.value?.shapes_count ?? projectStore.artifacts.shapes.length) > 0
)
const developerSourceLocked = computed(() =>
  developerSourceMode.value && (!developerBaselineLocked.value || !productHandoffReady.value),
)
const mutationDisabled = computed(() => readOnlyMode.value || developerSourceLocked.value)
const governedFrontingProject = computed(() => isGovernedFrontingProject(project.value))
const sourceKindOptions = computed(() =>
  developerSourceMode.value ? developerSourceDocumentKindOptions() : sourceDocumentKindOptions(project.value),
)
const frontingIntentReady = computed(() => hasFrontingIntentSource(documents.value))
const frontingIntegrationReady = computed(() => hasFrontingIntegrationSource(documents.value))
const developerSourceReady = computed(() => hasDeveloperSourceDocument(documents.value))
const currentShape = computed(() =>
  projectStore.artifacts.shapes.find((item) => item.id === projectStore.activeShapeId)
  ?? (projectStore.artifacts.shapes.length === 1 ? projectStore.artifacts.shapes[0] : null)
  ?? projectStore.artifacts.shapes[0]
  ?? null,
)
const developerEvidenceScaffoldFiles = computed(() =>
  developerSourceMode.value && project.value && developerBaselineLocked.value
    ? buildDeveloperEvidenceScaffoldFiles({
        projectId: project.value.id,
        shape: currentShape.value,
        pmArtifacts: projectStore.artifacts.pmArtifacts,
      })
    : [],
)
const scaffoldCapabilityCount = computed(() => {
  const manifestFile = developerEvidenceScaffoldFiles.value.find((file) => file.filename.endsWith('-developer-evidence-manifest.json'))
  if (!manifestFile) return 0
  try {
    const manifest = JSON.parse(manifestFile.content) as { capability_count?: number }
    return Number(manifest.capability_count ?? 0)
  } catch {
    return 0
  }
})
const pageKicker = computed(() => developerSourceMode.value ? 'Developer Source Docs' : 'Project Source Docs')
const visibleDocumentLabel = computed(() =>
  developerSourceMode.value
    ? 'developer source doc'
    : governedFrontingProject.value
    ? 'fronting source doc'
    : 'product source doc',
)
const sourceDocsHeaderCopy = computed(() =>
  developerSourceMode.value
    ? 'Attach developer-owned implementation evidence: service interfaces, OpenAPI/MCP/GraphQL schemas, semantic models, auth docs, permission matrices, runtime notes, and reviewed input-contract evidence. Product intent stays on Project Source Docs.'
    : governedFrontingProject.value
    ? 'Attach fronting intent, integration contracts, API/MCP documentation, permission matrices, and org policy evidence. Technical integration docs stay here as Developer/Integration sources, not PM business specs.'
    : 'Upload canonical business specs and supporting documents into Studio so the project carries its own sources.',
)
const assistantPanelCopy = computed(() =>
  developerSourceMode.value
    ? 'Developer Autopilot drafts from the locked Product Design baseline plus these developer source docs. If implementation evidence is missing or incomplete, Studio must ask developer-facing questions and block revision save until input contracts are reviewed.'
    : governedFrontingProject.value
    ? 'For fronting projects, the assistant can draft from business intent plus integration evidence. Add API/OpenAPI contracts, MCP schemas, auth docs, permission matrices, workflow docs, or org policy sources as separate source artifacts.'
    : 'Source Docs now only manages project references. Use the dedicated AI Assistant page to draft from the selected business spec, review the proposal bundle, answer targeted clarifications, and save accepted sections.',
)
const emptyDocumentCopy = computed(() =>
  developerSourceMode.value
    ? 'No developer source documents yet. Add service interface notes, implementation-surface contracts, semantic model docs, auth/scopes, or reviewed runtime input evidence before locking Developer Design.'
    : governedFrontingProject.value
    ? 'No source documents yet. Add fronting intent and at least one integration source such as an API contract, MCP schema, permission matrix, or API docs.'
    : 'No source documents yet. Upload the canonical business spec first.',
)
const pageIssue = useProjectIssue('project-source-docs')

const uploadTitle = ref('')
const uploadKind = ref('business_spec')
const uploadSourcePath = ref('')
const selectedFile = ref<File | null>(null)
const selectedDocumentId = ref<string | null>(null)
const previewContent = ref('')
const previewError = ref<string | null>(null)
const previewRequestId = ref(0)
const uploading = ref(false)
const deletingId = ref<string | null>(null)

async function ensureLoaded() {
  if (!projectId.value) return
  if (projectStore.activeProject?.id === projectId.value) return
  await loadProject(projectId.value)
}

onMounted(ensureLoaded)
watch(projectId, ensureLoaded)

watch(
  () => [project.value?.id, developerSourceMode.value] as const,
  () => {
    uploadKind.value = developerSourceMode.value ? defaultDeveloperSourceDocumentKind() : defaultSourceDocumentKind(project.value)
  },
  { immediate: true },
)

watch(
  () => visibleDocuments.value.map((item) => `${item.id}:${item.content_hash}:${item.updated_at}`).join(','),
  async () => {
    if (!visibleDocuments.value.length) {
      selectedDocumentId.value = null
      previewContent.value = ''
      previewError.value = null
      return
    }
    if (!selectedDocumentId.value || !visibleDocuments.value.some((item) => item.id === selectedDocumentId.value)) {
      selectedDocumentId.value = visibleDocuments.value[0].id
      return
    }
    await loadPreview()
  },
  { immediate: true },
)

watch(selectedDocumentId, loadPreview, { immediate: true })

function onFileSelected(event: Event) {
  const input = event.target as HTMLInputElement
  if (mutationDisabled.value) {
    input.value = ''
    selectedFile.value = null
    return
  }
  const file = input.files?.[0] ?? null
  selectedFile.value = file
  if (file && !uploadTitle.value.trim()) {
    uploadTitle.value = file.name.replace(/\.[^.]+$/, '')
  }
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(reader.error ?? new Error('Failed to read file'))
    reader.onload = () => {
      const result = String(reader.result || '')
      const encoded = result.includes(',') ? result.split(',')[1] : result
      resolve(encoded)
    }
    reader.readAsDataURL(file)
  })
}

async function handleUpload() {
  if (mutationDisabled.value || !projectId.value || !selectedFile.value) return
  uploading.value = true
  try {
    const file = selectedFile.value
    await createProjectDocument(projectId.value, {
      id: crypto.randomUUID(),
      title: uploadTitle.value.trim() || file.name,
      kind: uploadKind.value,
      filename: file.name,
      media_type: file.type || 'application/octet-stream',
      source_path: uploadSourcePath.value.trim(),
      content_base64: await fileToBase64(file),
    })
    uploadTitle.value = ''
    uploadKind.value = developerSourceMode.value ? defaultDeveloperSourceDocumentKind() : defaultSourceDocumentKind(project.value)
    uploadSourcePath.value = ''
    selectedFile.value = null
    const input = document.getElementById('source-doc-file') as HTMLInputElement | null
    if (input) input.value = ''
    await refreshArtifacts()
  } finally {
    uploading.value = false
  }
}

async function loadPreview() {
  const documentId = selectedDocumentId.value
  if (!projectId.value || !documentId) {
    previewContent.value = ''
    previewError.value = null
    return
  }
  const requestId = previewRequestId.value + 1
  previewRequestId.value = requestId
  previewError.value = null
  previewContent.value = ''
  try {
    const preview = await getProjectDocumentPreview(projectId.value, documentId)
    if (previewRequestId.value !== requestId || selectedDocumentId.value !== documentId) return
    previewContent.value = preview.content
  } catch (err) {
    if (previewRequestId.value !== requestId || selectedDocumentId.value !== documentId) return
    previewError.value = err instanceof Error ? err.message : String(err)
  }
}

async function handleDelete(documentId: string) {
  if (mutationDisabled.value || !projectId.value) return
  const record = visibleDocuments.value.find((item) => item.id === documentId)
  if (!record) return
  const confirmed = await requestConfirmation({
    title: 'Delete source document?',
    message: `Delete source document "${record.title}"?`,
    confirmLabel: 'Delete Document',
    cancelLabel: 'Cancel',
    tone: 'danger',
  })
  if (!confirmed) return
  deletingId.value = documentId
  try {
    await deleteProjectDocument(projectId.value, documentId)
    await refreshArtifacts()
  } finally {
    deletingId.value = null
  }
}

const selectedDocument = computed(() =>
  visibleDocuments.value.find((item) => item.id === selectedDocumentId.value) ?? null,
)

function openAssistant() {
  if (!project.value) return
  router.push({
    path: developerSourceMode.value
      ? `/design/projects/${project.value.id}/developer/assistant`
      : `/design/projects/${project.value.id}/pm/assistant`,
    query: {},
  })
}

function openAssistantLabel() {
  if (developerSourceMode.value) {
    return visibleDocuments.value.length
      ? 'Open Developer Autopilot With All Developer Docs'
      : 'Open Developer Autopilot'
  }
  return visibleDocuments.value.length ? 'Open AI Assistant With All Product Docs' : 'Open AI Assistant'
}

function downloadScaffold(file: DeveloperEvidenceScaffoldFile) {
  downloadDeveloperEvidenceScaffoldFile(file)
}
</script>

<template>
  <div class="source-docs-view">
    <div v-if="loading && !project" class="empty-state">Loading project...</div>
    <div v-else-if="error" class="banner banner-error">{{ error }}</div>
    <template v-else-if="project">
      <section class="page-header">
        <div>
          <div class="page-kicker">{{ pageKicker }}</div>
          <h1>{{ project.name }}</h1>
          <p>{{ sourceDocsHeaderCopy }}</p>
        </div>
      </section>

      <ProjectIssueBanner :issue="pageIssue" title="Source Docs diagnostics" />

      <div v-if="readOnlyMode" class="banner banner-warning readonly-banner">
        {{ readOnlyReason }}
      </div>
      <div v-if="developerSourceLocked" class="banner banner-warning readonly-banner">
        Lock the Product Design baseline before adding Developer Source Docs. Developer evidence must attach to a stable PM baseline, not a moving draft.
      </div>

      <section v-if="developerSourceMode" class="panel developer-scaffold-panel">
        <div class="panel-header">
          <div>
            <div class="assistant-kicker">Developer Evidence Scaffold</div>
            <h2>Download worksheets from the locked Product Design baseline</h2>
            <p class="panel-copy">
              Studio can generate a README, manifest, and strict CSV worksheets for capability governance, input contracts, and composition metadata from the locked service shape.
              Developers fill the implementation-owned fields, upload the completed files here, and Autopilot uses them as structured evidence.
            </p>
          </div>
          <span class="count-badge">{{ scaffoldCapabilityCount }} capabilities</span>
        </div>
        <div v-if="!developerBaselineLocked" class="banner banner-warning">
          Lock Product Design first. The scaffold must be tied to a stable baseline so evidence does not drift from PM intent.
        </div>
        <div v-else class="scaffold-actions">
          <button
            v-for="file in developerEvidenceScaffoldFiles"
            :key="file.filename"
            class="btn btn-secondary"
            type="button"
            @click="downloadScaffold(file)"
          >
            Download {{ file.filename }}
          </button>
        </div>
      </section>

      <section class="panel assistant-link-panel">
        <div class="panel-header">
          <div>
            <div class="assistant-kicker">AI Assistant</div>
            <h2>{{ developerSourceMode ? 'Draft Developer Design on the AI Assistant page' : 'Draft Product Design on the AI Assistant page' }}</h2>
            <p class="panel-copy">
              {{ assistantPanelCopy }}
            </p>
          </div>
        </div>
        <div v-if="governedFrontingProject && !developerSourceMode" class="fronting-readiness">
          <div class="fronting-readiness-item" :class="{ ready: frontingIntentReady }">
            <span class="status-dot" :class="{ ready: frontingIntentReady }"></span>
            <strong>Fronting intent</strong>
            <span>{{ frontingIntentReady ? 'available' : 'needed' }}</span>
          </div>
          <div class="fronting-readiness-item" :class="{ ready: frontingIntegrationReady }">
            <span class="status-dot" :class="{ ready: frontingIntegrationReady }"></span>
            <strong>Integration evidence</strong>
            <span>{{ frontingIntegrationReady ? 'available' : 'needed' }}</span>
          </div>
        </div>
        <div v-if="developerSourceMode" class="fronting-readiness">
          <div class="fronting-readiness-item" :class="{ ready: developerSourceReady }">
            <span class="status-dot" :class="{ ready: developerSourceReady }"></span>
            <strong>Developer evidence</strong>
            <span>{{ developerSourceReady ? 'available' : 'needed' }}</span>
          </div>
          <div class="fronting-readiness-item">
            <span class="status-dot"></span>
            <strong>Revision save gate</strong>
            <span>blocks incomplete input contracts</span>
          </div>
        </div>
        <div class="assistant-context">
          <span class="status-chip" :class="{ ready: !!selectedDocument }">
            {{
              developerSourceMode
                ? (visibleDocuments.length ? 'All developer docs will be passed to Developer Autopilot' : 'Add developer source docs first')
                : governedFrontingProject
                ? (visibleDocuments.length ? 'All fronting source docs will be passed to AI Assistant' : 'Add fronting source docs first')
                : (visibleDocuments.length ? 'All product source docs will be passed to AI Assistant' : 'Add product source docs first')
            }}
          </span>
          <span class="assistant-selected-doc">
            {{ `${visibleDocuments.length} ${visibleDocumentLabel}${visibleDocuments.length === 1 ? '' : 's'}` }}
          </span>
        </div>
        <div class="assistant-actions">
          <button class="btn btn-primary" :disabled="developerSourceLocked" @click="openAssistant">
            {{ openAssistantLabel() }}
          </button>
        </div>
      </section>

      <section class="content-grid">
        <article class="panel upload-panel">
          <div class="panel-header"><h2>Add Document</h2></div>
          <div class="form-grid">
            <label class="field field-wide">
              <span>Title</span>
              <textarea
                v-model="uploadTitle"
                class="form-input form-textarea"
                rows="3"
                :disabled="mutationDisabled"
                :placeholder="developerSourceMode ? 'Runtime interface notes, OpenAPI/MCP schema, semantic model, or input contract evidence' : governedFrontingProject ? 'Fronting intent, API contract, MCP schema, or policy source' : 'Canonical business spec'"
              ></textarea>
            </label>
            <label class="field">
              <span>Kind</span>
              <select v-model="uploadKind" class="form-input" :disabled="mutationDisabled">
                <option v-for="option in sourceKindOptions" :key="option.value" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
              <small class="field-help">
                {{ sourceKindOptions.find(option => option.value === uploadKind)?.description }}
              </small>
            </label>
            <label class="field field-wide">
              <span>Source path</span>
              <input
                v-model="uploadSourcePath"
                class="form-input"
                :placeholder="developerSourceMode ? 'docs/examples/my-project/runtime-interface.md' : 'docs/examples/my-project/business-spec.md'"
                :disabled="mutationDisabled"
              />
            </label>
            <div class="field field-wide">
              <span>File</span>
              <label class="file-drop-zone" :class="{ disabled: mutationDisabled }" for="source-doc-file">
                <input
                  id="source-doc-file"
                  type="file"
                  class="file-input-hidden"
                  :disabled="mutationDisabled"
                  @change="onFileSelected"
                />
                <span class="file-drop-action">Choose file</span>
                <span class="selected-file" :class="{ empty: !selectedFile }">
                  {{ selectedFile ? selectedFile.name : 'No file selected' }}
                </span>
              </label>
            </div>
          </div>
          <button class="btn btn-primary" :disabled="mutationDisabled || !selectedFile || uploading" @click="handleUpload">
            {{ uploading ? 'Uploading...' : 'Upload document' }}
          </button>
        </article>

        <article class="panel list-panel">
          <div class="panel-header">
            <div class="panel-title-row">
              <h2>Stored Documents</h2>
              <span class="count-badge">{{ visibleDocuments.length }}</span>
            </div>
          </div>
          <div v-if="visibleDocuments.length === 0" class="empty-state">
            {{ emptyDocumentCopy }}
          </div>
          <div v-else class="doc-list">
            <button
              v-for="document in visibleDocuments"
              :key="document.id"
              class="doc-card"
              :class="{ selected: document.id === selectedDocumentId }"
              @click="selectedDocumentId = document.id"
            >
              <div class="doc-card-top">
                <span class="doc-kind">{{ sourceDocumentKindLabel(document.kind) }}</span>
                <span class="doc-date">{{ formatStudioTimestamp(document.updated_at, 'date') }}</span>
              </div>
              <div class="doc-title">{{ document.title }}</div>
              <div class="doc-meta">{{ document.filename }}</div>
            </button>
          </div>
        </article>

        <article class="panel preview-panel">
          <div class="panel-header">
            <h2>Preview</h2>
            <div v-if="selectedDocument" class="preview-actions">
              <a
                class="btn btn-secondary btn-link"
                :href="getProjectDocumentDownloadUrl(project.id, selectedDocument.id)"
              >
                Download
              </a>
              <button
                class="btn btn-secondary"
                :disabled="mutationDisabled || deletingId === selectedDocument.id"
                @click="handleDelete(selectedDocument.id)"
              >
                {{ deletingId === selectedDocument.id ? 'Deleting...' : 'Delete' }}
              </button>
            </div>
          </div>
          <template v-if="selectedDocument">
            <div class="preview-meta">
              <div><strong>Kind:</strong> {{ sourceDocumentKindLabel(selectedDocument.kind) }}</div>
              <div><strong>Filename:</strong> {{ selectedDocument.filename }}</div>
              <div v-if="selectedDocument.source_path"><strong>Source path:</strong> {{ selectedDocument.source_path }}</div>
            </div>
            <div v-if="previewError" class="banner banner-warning">{{ previewError }}</div>
            <pre v-else class="preview-content">{{ previewContent }}</pre>
          </template>
          <div v-else class="empty-state">Select a source document to preview it.</div>
        </article>
      </section>
    </template>
  </div>
</template>

<style scoped>
.source-docs-view {
  width: 100%;
  max-width: none;
  padding: 2rem;
}

.page-header {
  margin-bottom: 1.75rem;
}

.page-header h1 {
  margin: 0.2rem 0 0.5rem;
  color: var(--text-primary);
  font-size: 32px;
  line-height: 1.15;
  font-weight: 700;
}

.page-header p {
  max-width: 78ch;
  margin: 0;
  line-height: 1.6;
}

.page-header p,
.page-kicker,
.empty-state,
.doc-meta,
.preview-meta {
  color: var(--text-secondary);
}

.page-kicker {
  text-transform: uppercase;
  font-size: 12px;
  letter-spacing: 0.08em;
  color: var(--text-muted);
  margin-bottom: 0.4rem;
}

.content-grid {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 1.05rem;
  margin-bottom: 1rem;
}

.panel {
  background: var(--surface-depth-panel);
  border: 1px solid var(--surface-border-panel);
  border-radius: 22px;
  padding: 1.35rem;
}

.upload-panel {
  grid-column: span 5;
}

.list-panel {
  grid-column: span 7;
}

.preview-panel {
  grid-column: span 12;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: center;
  margin-bottom: 1.15rem;
}

.panel-header h2 {
  margin: 0;
  color: var(--text-primary);
  font-size: 20px;
  line-height: 1.25;
  font-weight: 700;
}

.panel-title-row {
  display: inline-flex;
  align-items: center;
  gap: 0.6rem;
}

.panel-copy {
  margin: 0.5rem 0 0;
  color: var(--text-secondary);
  line-height: 1.6;
  max-width: 88ch;
}

.assistant-link-panel {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  margin: 0 0 1.05rem;
}

.developer-scaffold-panel {
  margin: 0 0 1.05rem;
}

.scaffold-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.assistant-link-panel .panel-header {
  margin-bottom: 0;
}

.assistant-context {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  align-items: center;
  color: var(--text-secondary);
}

.fronting-readiness {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
}

.fronting-readiness-item {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  padding: 0.72rem 0.85rem;
  border: 1px solid rgba(251, 191, 36, 0.22);
  border-radius: 14px;
  background: rgba(120, 53, 15, 0.14);
  color: var(--text-secondary);
}

.fronting-readiness-item.ready {
  border-color: rgba(34, 197, 94, 0.25);
  background: rgba(20, 83, 45, 0.16);
}

.fronting-readiness-item strong {
  color: var(--text-primary);
}

.status-dot {
  width: 0.55rem;
  height: 0.55rem;
  border-radius: 999px;
  background: #f59e0b;
  box-shadow: 0 0 0 4px rgba(245, 158, 11, 0.12);
}

.status-dot.ready {
  background: #22c55e;
  box-shadow: 0 0 0 4px rgba(34, 197, 94, 0.14);
}

.assistant-selected-doc {
  color: var(--text-primary);
  font-weight: 600;
}

.assistant-actions {
  display: flex;
  justify-content: flex-start;
  padding-top: 0.35rem;
}

.assistant-kicker {
  margin-bottom: 0.35rem;
  color: #93c5fd;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.readonly-banner {
  margin-bottom: 1rem;
}

.draft-panel {
  margin-bottom: 1rem;
}

.draft-actions,
.section-actions,
.selection-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem;
  align-items: center;
  justify-content: flex-end;
}

.draft-context {
  display: flex;
  flex-wrap: wrap;
  gap: 0.7rem;
  align-items: center;
  margin: 0.8rem 0 0;
  color: var(--text-secondary);
}

.status-chip {
  border: 1px solid var(--surface-border-card);
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.12);
  color: var(--text-secondary);
  padding: 0.32rem 0.68rem;
  font-size: 12px;
  font-weight: 700;
  text-transform: capitalize;
}

.status-chip.ready {
  border-color: rgba(34, 197, 94, 0.28);
  background: rgba(34, 197, 94, 0.12);
  color: #bbf7d0;
}

.draft-results {
  display: grid;
  gap: 1rem;
  margin-top: 1.1rem;
  padding-top: 1rem;
  border-top: 1px solid rgba(148, 163, 184, 0.14);
}

.draft-summary h3,
.draft-summary p {
  margin: 0;
}

.draft-summary p {
  margin-top: 0.35rem;
  color: var(--text-secondary);
}

.clarification-batch {
  padding: 1rem;
  border-radius: 14px;
  border: 1px solid rgba(251, 191, 36, 0.24);
  background: rgba(251, 191, 36, 0.1);
}

.clarification-batch p {
  margin: 0.35rem 0 0.6rem;
  color: var(--text-secondary);
}

.clarification-batch ul,
.section-note ul {
  margin: 0;
  padding-left: 1.1rem;
  color: var(--text-secondary);
}

.draft-section-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 1rem;
}

.draft-section-card {
  display: grid;
  gap: 0.85rem;
  align-content: start;
  padding: 1rem;
  border-radius: 16px;
  border: 1px solid var(--surface-border-card);
  background: var(--surface-depth-card);
}

.draft-section-card.status-saved {
  border-color: rgba(34, 197, 94, 0.28);
}

.draft-section-card.status-failed {
  border-color: rgba(248, 113, 113, 0.28);
}

.draft-section-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
}

.draft-section-header h3 {
  margin: 0 0 0.3rem;
}

.draft-section-header p,
.proposal-body,
.proposal-item small,
.error-copy {
  color: var(--text-secondary);
}

.section-note {
  display: grid;
  gap: 0.4rem;
  padding: 0.8rem;
  border-radius: 12px;
  background: var(--surface-depth-card);
}

.selection-toolbar {
  justify-content: flex-start;
  color: var(--text-secondary);
  font-size: 13px;
}

.mini-btn {
  border: 1px solid var(--surface-border-card);
  border-radius: 999px;
  background: var(--surface-depth-card);
  color: var(--text-primary);
  padding: 0.3rem 0.65rem;
  cursor: pointer;
}

.proposal-items {
  display: grid;
  gap: 0.7rem;
  max-height: 430px;
  overflow: auto;
}

.proposal-item {
  display: flex;
  gap: 0.7rem;
  align-items: flex-start;
  padding: 0.8rem;
  border-radius: 12px;
  border: 1px solid var(--surface-border-card);
  background: var(--surface-depth-card);
}

.proposal-copy {
  display: grid;
  gap: 0.35rem;
  min-width: 0;
  flex: 1;
}

.proposal-title-row {
  display: flex;
  justify-content: space-between;
  gap: 0.8rem;
  align-items: baseline;
}

.proposal-title-row em {
  color: var(--text-secondary);
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.proposal-body {
  white-space: pre-wrap;
  word-break: break-word;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1.05rem;
  margin-bottom: 1.1rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.field span {
  color: var(--text-primary);
  font-size: 0.92rem;
  font-weight: 700;
}

.field-help {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.45;
}

.field-wide {
  grid-column: span 2;
}

.form-input {
  width: 100%;
  border-radius: 12px;
  border: 1px solid var(--surface-border-card);
  background: var(--surface-depth-card);
  padding: 0.78rem 0.9rem;
  color: var(--text-primary);
  font: inherit;
  line-height: 1.45;
}

.form-textarea {
  min-height: 92px;
  resize: vertical;
  max-width: 100%;
  min-width: 0;
  font: inherit;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.file-input-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.file-drop-zone {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  min-height: 58px;
  border: 1px dashed rgba(96, 165, 250, 0.3);
  border-radius: 16px;
  background:
    linear-gradient(180deg, rgba(15, 23, 42, 0.66), rgba(15, 23, 42, 0.46));
  padding: 0.68rem;
  cursor: pointer;
  transition:
    background var(--transition),
    border-color var(--transition);
}

.file-drop-zone:hover {
  border-color: var(--border-focus);
  background: rgba(37, 37, 69, 0.72);
}

.file-drop-zone.disabled {
  opacity: 0.62;
  cursor: not-allowed;
}

.file-drop-zone.disabled:hover {
  border-color: rgba(96, 165, 250, 0.3);
  background:
    linear-gradient(180deg, rgba(15, 23, 42, 0.66), rgba(15, 23, 42, 0.46));
}

.file-drop-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 36px;
  padding: 0 0.95rem;
  border: 1px solid var(--surface-border-card);
  border-radius: 12px;
  background: var(--surface-depth-card);
  color: #dbeafe;
  font-size: 13px;
  font-weight: 700;
  white-space: nowrap;
}

.selected-file {
  flex: 1;
  min-height: 36px;
  display: flex;
  align-items: center;
  color: var(--text-primary);
  word-break: break-word;
}

.selected-file.empty {
  color: var(--text-secondary);
}

.doc-list {
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
}

.doc-card {
  width: 100%;
  text-align: left;
  padding: 1rem;
  border-radius: 18px;
  border: 1px solid var(--surface-border-card);
  background:
    linear-gradient(180deg, rgba(15, 23, 42, 0.66), rgba(15, 23, 42, 0.46));
  color: inherit;
  cursor: pointer;
  transition:
    border-color 0.16s ease,
    background 0.16s ease,
    transform 0.16s ease;
}

.doc-card:hover {
  border-color: rgba(147, 197, 253, 0.34);
  background:
    linear-gradient(180deg, rgba(30, 64, 175, 0.2), rgba(15, 23, 42, 0.52));
  transform: translateY(-1px);
}

.doc-card.selected {
  border-color: rgba(96, 165, 250, 0.42);
  background:
    linear-gradient(180deg, rgba(30, 64, 175, 0.24), rgba(15, 23, 42, 0.58));
}

.doc-card-top {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 0.5rem;
}

.doc-title {
  color: var(--text-primary);
  font-weight: 800;
  margin-bottom: 0.25rem;
}

.preview-actions {
  display: flex;
  gap: 0.6rem;
}

.preview-content {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
  line-height: 1.55;
  color: var(--text-primary);
  background:
    linear-gradient(180deg, rgba(15, 23, 42, 0.66), rgba(15, 23, 42, 0.48));
  border-radius: 18px;
  border: 1px solid var(--surface-border-card);
  padding: 1.1rem;
  min-height: 320px;
  max-height: min(70vh, 960px);
  overflow: auto;
}

.preview-meta {
  display: grid;
  gap: 0.35rem;
  margin-bottom: 1rem;
}

.count-badge {
  border-radius: 999px;
  background: rgba(96, 165, 250, 0.14);
  color: #bfdbfe;
  padding: 0.3rem 0.68rem;
  font-size: 12px;
  font-weight: 800;
}

.btn {
  border: 1px solid var(--surface-border-card);
  border-radius: 12px;
  padding: 0.75rem 1rem;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  min-height: 38px;
}

.btn-primary {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}

.btn-secondary {
  background: var(--surface-depth-card);
  color: #dbeafe;
  border-color: rgba(96, 165, 250, 0.24);
}

.btn-secondary:hover:not(:disabled) {
  background: rgba(30, 64, 175, 0.22);
  border-color: rgba(147, 197, 253, 0.42);
}

.btn-link {
  text-decoration: none;
}

.banner {
  padding: 0.75rem 0.95rem;
  border-radius: 12px;
}

.banner-warning {
  background: rgba(251, 191, 36, 0.12);
  border: 1px solid rgba(251, 191, 36, 0.28);
  color: #fbbf24;
}

.banner-error {
  background: rgba(248, 113, 113, 0.12);
  border: 1px solid rgba(248, 113, 113, 0.28);
  color: var(--error);
}

@media (max-width: 1200px) {
  .upload-panel,
  .list-panel,
  .preview-panel {
    grid-column: span 12;
  }
}

@media (max-width: 720px) {
  .source-docs-view {
    padding: 1.25rem;
  }

  .form-grid {
    grid-template-columns: 1fr;
  }

  .field-wide {
    grid-column: span 1;
  }
}
</style>
