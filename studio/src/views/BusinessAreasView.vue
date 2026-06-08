<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { createPmArtifact, deletePmArtifact, updatePmArtifact } from '../design/project-api'
import { requestConfirmation } from '../design/confirm'
import {
  BUSINESS_AREAS_ARTIFACT_TYPE,
  cloneProductDesignData,
  defaultBusinessAreasData,
  findBusinessAreasArtifact,
  isBusinessAreasComplete,
  makeBlankBusinessArea,
  normalizeBusinessAreaId,
  productDesignArtifactId,
  type BusinessAreasData,
} from '../design/product-design'
import { loadProject, projectStore } from '../design/project-store'
import ProjectIssueBanner from '../components/ProjectIssueBanner.vue'
import { useProjectIssue } from '../design/use-project-issue'

const route = useRoute()
const router = useRouter()

const projectId = computed(() => route.params.projectId as string)
const project = computed(() => projectStore.activeProject)
const artifact = computed(() => findBusinessAreasArtifact(projectStore.artifacts.pmArtifacts))
const baseData = ref<BusinessAreasData>(defaultBusinessAreasData())
const draft = ref<BusinessAreasData>(defaultBusinessAreasData())
const saving = ref(false)
const deleting = ref(false)
const saveError = ref<string | null>(null)
const editing = ref(false)
const pageIssue = useProjectIssue('project-business-areas')
const readOnlyMode = computed(() => projectStore.runtimeStatus?.read_only_mode !== false)
const readOnlyReason = computed(() =>
  projectStore.runtimeStatus?.read_only_reason
  || 'Studio is running in read-only mode. Explore the design, then run Studio locally to make changes.',
)

async function ensureLoaded() {
  if (!projectId.value) return
  if (projectStore.activeProject?.id === projectId.value) return
  await loadProject(projectId.value)
}

function syncDraft() {
  const next = artifact.value?.data
    ? cloneProductDesignData(artifact.value.data as BusinessAreasData)
    : defaultBusinessAreasData()
  if (!next.entries.length) {
    next.entries = [makeBlankBusinessArea()]
  }
  next.entries = next.entries.map((entry) => ({
    ...makeBlankBusinessArea(),
    ...entry,
  }))
  baseData.value = cloneProductDesignData(next)
  draft.value = cloneProductDesignData(next)
}

onMounted(async () => {
  await ensureLoaded()
  syncDraft()
})

watch(
  () => [projectId.value, artifact.value?.updated_at] as const,
  async () => {
    await ensureLoaded()
    syncDraft()
  },
)

const hasChanges = computed(() => JSON.stringify(draft.value) !== JSON.stringify(baseData.value))
const isComplete = computed(() => isBusinessAreasComplete(draft.value))
const pageHasIssue = computed(() => Boolean(pageIssue.value?.count) && !isComplete.value)

function entryHasIssue(index: number): boolean {
  const entry = draft.value.entries[index]
  return pageHasIssue.value && Boolean(entry) && (
    !entry.business_area_id.trim()
    || !entry.label.trim()
  )
}

function missingEntryField(index: number, field: 'business_area_id' | 'label'): boolean {
  return pageHasIssue.value && !draft.value.entries[index]?.[field]?.trim()
}

function addEntry() {
  if (readOnlyMode.value) return
  draft.value.entries.push(makeBlankBusinessArea())
}

function removeEntry(index: number) {
  if (readOnlyMode.value) return
  draft.value.entries.splice(index, 1)
  if (!draft.value.entries.length) {
    draft.value.entries.push(makeBlankBusinessArea())
  }
}

function setBusinessAreaId(index: number, value: string) {
  if (readOnlyMode.value) return
  draft.value.entries[index].business_area_id = normalizeBusinessAreaId(value)
}

function setBusinessAreaLabel(index: number, value: string) {
  if (readOnlyMode.value) return
  draft.value.entries[index].label = value
  if (!draft.value.entries[index].business_area_id.trim()) {
    draft.value.entries[index].business_area_id = normalizeBusinessAreaId(value)
  }
}

function startEditing() {
  if (readOnlyMode.value) return
  editing.value = true
}

function discardChanges() {
  draft.value = cloneProductDesignData(baseData.value)
  editing.value = false
}

async function save() {
  if (readOnlyMode.value || !project.value) return
  saving.value = true
  saveError.value = null
  try {
    const payload: BusinessAreasData = {
      ...cloneProductDesignData(draft.value),
      artifact_type: BUSINESS_AREAS_ARTIFACT_TYPE,
      entries: draft.value.entries
        .map((entry) => ({
          business_area_id: normalizeBusinessAreaId(entry.business_area_id || entry.label),
          label: entry.label.trim(),
          description: entry.description.trim(),
        }))
        .filter((entry) =>
          entry.business_area_id.length > 0
          || entry.label.length > 0
          || entry.description.length > 0,
        ),
    }
    if (!payload.entries.length) {
      payload.entries = [makeBlankBusinessArea()]
    }
    if (artifact.value) {
      await updatePmArtifact(project.value.id, artifact.value.id, {
        title: 'Business Areas',
        data: payload,
      })
    } else {
      await createPmArtifact(project.value.id, {
        id: productDesignArtifactId(project.value.id, BUSINESS_AREAS_ARTIFACT_TYPE),
        title: 'Business Areas',
        data: payload,
      })
    }
    await loadProject(project.value.id)
    editing.value = false
  } catch (err) {
    saveError.value = err instanceof Error ? err.message : String(err)
  } finally {
    saving.value = false
  }
}

async function removeArtifact() {
  if (readOnlyMode.value || !project.value || !artifact.value) return
  const confirmed = await requestConfirmation({
    title: 'Delete Business Areas?',
    message: 'This removes the saved Product Design business-area catalog from the project.',
    confirmLabel: 'Delete Business Areas',
    cancelLabel: 'Cancel',
    tone: 'danger',
  })
  if (!confirmed) return
  deleting.value = true
  try {
    await deletePmArtifact(project.value.id, artifact.value.id)
    await loadProject(project.value.id)
    editing.value = false
  } finally {
    deleting.value = false
  }
}
</script>

<template>
  <div class="product-editor">
    <template v-if="project">
      <section class="page-header">
        <button class="back-link" type="button" @click="router.push(`/design/projects/${project.id}/pm`)">
          &larr; Back to Product Overview
        </button>
        <div class="page-kicker">Product Design</div>
        <h1>Business Areas</h1>
        <p>
          Define the stable business-area identifiers the PM lane should reuse across Permission Intent, supported
          question families, verification, and downstream developer formalization.
        </p>
      </section>

      <ProjectIssueBanner :issue="pageIssue" title="Business Areas diagnostics" />

      <div v-if="saveError" class="banner banner-error">{{ saveError }}</div>
      <div v-if="readOnlyMode" class="banner banner-warning readonly-banner">{{ readOnlyReason }}</div>

      <section class="panel" :class="{ 'field-error-card': pageHasIssue }">
        <div class="panel-header">
          <div>
            <h2>Business Area Catalog</h2>
            <p class="panel-copy">
              Use human labels for PM readability and keep the id stable for reuse. This prevents `reporting_analytics`
              or similar values from being retyped inconsistently across multiple pages.
            </p>
          </div>
          <div class="actions">
            <button v-if="!editing" class="btn btn-secondary" type="button" :disabled="readOnlyMode" @click="startEditing">
              {{ artifact ? 'Edit Business Areas' : 'Add Business Areas' }}
            </button>
            <button v-if="editing" class="btn btn-secondary" :disabled="!hasChanges" @click="discardChanges">Discard Changes</button>
            <button v-if="editing" class="btn btn-secondary" :disabled="readOnlyMode || !artifact || deleting" @click="removeArtifact">
              {{ deleting ? 'Deleting...' : 'Delete' }}
            </button>
            <button v-if="editing" class="btn btn-primary" :disabled="readOnlyMode || saving" @click="save">
              {{ saving ? 'Saving...' : 'Save to Project' }}
            </button>
          </div>
        </div>

        <div v-if="!editing && artifact" class="card-stack">
          <article v-for="(entry, index) in baseData.entries" :key="`summary-${index}`" class="entry-card summary-entry-card">
            <div class="entry-header">
              <h3>{{ entry.label || `Business Area ${index + 1}` }}</h3>
              <span class="summary-chip">{{ entry.business_area_id || 'no id' }}</span>
            </div>
            <p>{{ entry.description || 'No description captured.' }}</p>
            <details class="view-details">
              <summary>View all saved values</summary>
              <div class="detail-grid">
                <div><span>Stable ID</span><strong>{{ entry.business_area_id || 'Not captured' }}</strong></div>
                <div><span>Label</span><strong>{{ entry.label || 'Not captured' }}</strong></div>
                <div class="detail-wide"><span>Description</span><p>{{ entry.description || 'Not captured' }}</p></div>
              </div>
            </details>
          </article>
        </div>

        <div v-else-if="!editing" class="empty-editor-state">
          <strong>No business areas saved yet.</strong>
          <p>Add business areas when you are ready to create stable PM-facing domains for permissions and coverage.</p>
        </div>

        <div v-else class="card-stack">
          <article v-for="(entry, index) in draft.entries" :key="index" class="entry-card" :class="{ 'field-error-card': entryHasIssue(index) }">
            <div class="entry-header">
              <h3>Business Area {{ index + 1 }}</h3>
              <button class="btn btn-tertiary" type="button" :disabled="readOnlyMode" @click="removeEntry(index)">Remove</button>
            </div>
            <div class="field-grid">
              <label class="field" :class="{ 'field-error': missingEntryField(index, 'label') }">
                <span class="field-label">Label</span>
                <span class="field-help">Business-facing name shown to PMs and reviewers.</span>
                <input
                  :value="entry.label"
                  class="field-input"
                  type="text"
                  @input="setBusinessAreaLabel(index, ($event.target as HTMLInputElement).value)"
                />
                <small v-if="missingEntryField(index, 'label')" class="field-error-copy">Business area label is required.</small>
              </label>
              <label class="field" :class="{ 'field-error': missingEntryField(index, 'business_area_id') }">
                <span class="field-label">Stable ID</span>
                <span class="field-help">Reusable internal id referenced by Permission Intent and downstream contract bindings.</span>
                <input
                  :value="entry.business_area_id"
                  class="field-input"
                  type="text"
                  @input="setBusinessAreaId(index, ($event.target as HTMLInputElement).value)"
                />
                <small v-if="missingEntryField(index, 'business_area_id')" class="field-error-copy">Stable ID is required.</small>
              </label>
              <label class="field field-full">
                <span class="field-label">Description</span>
                <span class="field-help">Describe the scope of this area so PMs know when to reuse it versus create a new one.</span>
                <textarea v-model="entry.description" class="field-input textarea" rows="3" />
              </label>
            </div>
          </article>
        </div>

        <div class="footer-row">
          <button class="btn btn-secondary" type="button" :disabled="readOnlyMode" @click="addEntry">Add Business Area</button>
          <span class="status-pill" :class="{ ready: isComplete }">{{ isComplete ? 'Ready' : 'Needs PM input' }}</span>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.product-editor {
  width: 100%;
  max-width: none;
  padding: 2rem;
}

.page-header {
  margin-bottom: 1.75rem;
}

.page-kicker {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 0.4rem;
}

.page-header h1 {
  margin: 0 0 0.5rem;
  font-size: 32px;
  line-height: 1.15;
  font-weight: 700;
  color: var(--text-primary);
}

.page-header p {
  max-width: 78ch;
  color: var(--text-secondary);
  line-height: 1.6;
}

.back-link {
  margin-bottom: 0.9rem;
  border: none;
  background: transparent;
  color: var(--accent);
  padding: 0;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
}

.back-link:hover {
  color: var(--accent-hover);
}

.panel {
  background: var(--surface-depth-panel);
  border: 1px solid var(--surface-border-panel);
  border-radius: 22px;
  padding: 1.35rem;
}

.panel-header {
  margin-bottom: 1.25rem;
}

.panel-copy {
  margin: 0.5rem 0 0;
  color: var(--text-secondary);
  line-height: 1.6;
  max-width: 72ch;
}

.panel-header,
.entry-header,
.footer-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}

.entry-header {
  margin-bottom: 1.15rem;
}

.actions {
  display: flex;
  flex-wrap: nowrap;
  gap: 0.75rem;
  align-items: center;
  justify-content: flex-end;
  white-space: nowrap;
}

.actions .btn,
.footer-row .btn,
.entry-header .btn {
  width: auto;
}

.footer-row {
  margin-top: 1.25rem;
}

.entry-header h3 {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  margin: 0;
  padding: 0 0.75rem;
  border: 1px solid rgba(96, 165, 250, 0.26);
  border-radius: 999px;
  background: rgba(96, 165, 250, 0.1);
  color: #bfdbfe;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.card-stack {
  display: flex;
  flex-direction: column;
  gap: 1.1rem;
}

.entry-card {
  border: 1px solid var(--surface-border-card);
  border-radius: 20px;
  padding: 1.1rem;
  background:
    linear-gradient(180deg, rgba(15, 23, 42, 0.66), rgba(15, 23, 42, 0.46));
}

.summary-entry-card p,
.empty-editor-state p {
  color: var(--text-secondary);
  line-height: 1.55;
  margin: 0;
}

.view-details {
  border-top: 1px solid rgba(148, 163, 184, 0.12);
  margin-top: 0.85rem;
  padding-top: 0.75rem;
}

.view-details summary {
  color: #bfdbfe;
  cursor: pointer;
  font-size: 13px;
  font-weight: 800;
}

.detail-grid {
  display: grid;
  gap: 0.75rem;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin-top: 0.85rem;
}

.detail-grid > div {
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  background: var(--surface-depth-inset);
  padding: 0.75rem;
}

.detail-wide {
  grid-column: 1 / -1;
}

.detail-grid span {
  color: var(--text-secondary);
  display: block;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.06em;
  margin-bottom: 0.35rem;
  text-transform: uppercase;
}

.detail-grid strong,
.detail-grid p {
  color: var(--text-primary);
  line-height: 1.5;
  margin: 0;
  overflow-wrap: anywhere;
}

.summary-chip {
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.12);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 800;
  padding: 0.35rem 0.7rem;
}

.empty-editor-state {
  border: 1px solid var(--surface-border-card);
  border-radius: 16px;
  background: var(--surface-depth-card);
  padding: 1rem;
}

.empty-editor-state strong {
  color: var(--text-primary);
}

.field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1.05rem;
}

.field,
.field-full {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.field-full {
  grid-column: 1 / -1;
}

.field-label {
  font-size: 0.92rem;
  font-weight: 700;
  color: var(--text-primary);
}

.field-help {
  color: var(--text-secondary);
  font-size: 0.84rem;
  line-height: 1.5;
}

.field-input {
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  border-radius: 12px;
  border: 1px solid var(--surface-border-card);
  background: var(--surface-depth-card);
  color: var(--text-primary);
  padding: 0.78rem 0.9rem;
  font: inherit;
  line-height: 1.45;
}

.textarea {
  resize: vertical;
}

.banner-error {
  margin-bottom: 1rem;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  padding: 0.35rem 0.7rem;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.15);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
}

.status-pill.ready {
  background: rgba(16, 185, 129, 0.16);
  color: #86efac;
}

.btn {
  min-height: 38px;
  border-radius: 12px;
  font-weight: 700;
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

.btn-tertiary {
  background: var(--surface-depth-card);
  border-color: rgba(148, 163, 184, 0.18);
  color: var(--text-secondary);
}

@media (max-width: 900px) {
  .field-grid,
  .detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>
<style scoped src="./product-inline-errors.css"></style>
