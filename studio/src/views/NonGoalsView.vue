<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { createPmArtifact, deletePmArtifact, updatePmArtifact } from '../design/project-api'
import { requestConfirmation } from '../design/confirm'
import {
  cloneProductDesignData,
  defaultNonGoalsData,
  findNonGoalsArtifact,
  isNonGoalsComplete,
  makeBlankNonGoal,
  NON_GOALS_ARTIFACT_TYPE,
  persistedPmArtifactStatus,
  productDesignArtifactId,
  type NonGoalsData,
} from '../design/product-design'
import { loadProject, projectStore } from '../design/project-store'
import ProjectIssueBanner from '../components/ProjectIssueBanner.vue'
import { useProjectIssue } from '../design/use-project-issue'

const route = useRoute()
const router = useRouter()

const projectId = computed(() => route.params.projectId as string)
const project = computed(() => projectStore.activeProject)
const artifact = computed(() => findNonGoalsArtifact(projectStore.artifacts.pmArtifacts))
const baseData = ref<NonGoalsData>(defaultNonGoalsData())
const draft = ref<NonGoalsData>(defaultNonGoalsData())
const saving = ref(false)
const deleting = ref(false)
const saveError = ref<string | null>(null)
const editing = ref(false)
const pageIssue = useProjectIssue('project-non-goals')
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
    ? cloneProductDesignData(artifact.value.data as NonGoalsData)
    : defaultNonGoalsData()
  if (!next.entries.length) {
    next.entries = [makeBlankNonGoal()]
  }
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
const isComplete = computed(() => isNonGoalsComplete(draft.value))
const pageHasIssue = computed(() => Boolean(pageIssue.value?.count) && !isComplete.value)

function entryHasIssue(index: number): boolean {
  return pageHasIssue.value && !draft.value.entries[index]?.statement?.trim()
}

function addEntry() {
  if (readOnlyMode.value) return
  draft.value.entries.push(makeBlankNonGoal())
}

function removeEntry(index: number) {
  if (readOnlyMode.value) return
  draft.value.entries.splice(index, 1)
  if (!draft.value.entries.length) {
    draft.value.entries.push(makeBlankNonGoal())
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
    const payload: NonGoalsData = {
      ...cloneProductDesignData(draft.value),
      artifact_type: NON_GOALS_ARTIFACT_TYPE,
      entries: draft.value.entries.filter((entry) =>
        entry.statement.trim().length > 0 || entry.rationale.trim().length > 0,
      ),
    }
    if (!payload.entries.length) {
      payload.entries = [makeBlankNonGoal()]
    }
    if (artifact.value) {
      await updatePmArtifact(project.value.id, artifact.value.id, {
        title: 'Non-Goals',
        status: persistedPmArtifactStatus(isNonGoalsComplete(payload)),
        data: payload,
      })
    } else {
      await createPmArtifact(project.value.id, {
        id: productDesignArtifactId(project.value.id, NON_GOALS_ARTIFACT_TYPE),
        title: 'Non-Goals',
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
    title: 'Delete Non-Goals?',
    message: 'This removes the saved Product Design non-goals from the project.',
    confirmLabel: 'Delete Non-Goals',
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
        <h1>Non-Goals</h1>
        <p>
          Make the intentional limits of the product explicit. This gives developers and reviewers a clear boundary for
          what should not be generated, implemented, or assumed later in the flow.
        </p>
      </section>

      <ProjectIssueBanner :issue="pageIssue" title="Non-Goals diagnostics" />

      <div v-if="saveError" class="banner banner-error">{{ saveError }}</div>
      <div v-if="readOnlyMode" class="banner banner-warning readonly-banner">{{ readOnlyReason }}</div>

      <section class="panel" :class="{ 'field-error-card': pageHasIssue }">
        <div class="panel-header">
          <div>
            <h2>Explicit Non-Goals</h2>
            <p class="panel-copy">
              Non-goals should be concrete. They help prevent Studio from drifting into extra functionality nobody
              actually approved.
            </p>
          </div>
          <div class="actions">
            <button v-if="!editing" class="btn btn-secondary" type="button" :disabled="readOnlyMode" @click="startEditing">
              {{ artifact ? 'Edit Non-Goals' : 'Add Non-Goals' }}
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
              <h3>Non-Goal {{ index + 1 }}</h3>
            </div>
            <p>{{ entry.statement || 'No statement captured.' }}</p>
            <small>{{ entry.rationale || 'No rationale captured.' }}</small>
            <details class="view-details">
              <summary>View all saved values</summary>
              <div class="detail-grid">
                <div class="detail-wide"><span>Statement</span><p>{{ entry.statement || 'Not captured' }}</p></div>
                <div class="detail-wide"><span>Rationale</span><p>{{ entry.rationale || 'Not captured' }}</p></div>
              </div>
            </details>
          </article>
        </div>

        <div v-else-if="!editing" class="empty-editor-state">
          <strong>No non-goals saved yet.</strong>
          <p>Add explicit non-goals when you are ready to define what this project should not do.</p>
        </div>

        <div v-else class="card-stack">
          <article v-for="(entry, index) in draft.entries" :key="index" class="entry-card" :class="{ 'field-error-card': entryHasIssue(index) }">
            <div class="entry-header">
              <h3>Non-Goal {{ index + 1 }}</h3>
              <button class="btn btn-tertiary" type="button" :disabled="readOnlyMode" @click="removeEntry(index)">Remove</button>
            </div>
            <div class="field-grid">
              <label class="field field-full" :class="{ 'field-error': entryHasIssue(index) }">
                <span class="field-label">Statement</span>
                <span class="field-help">State what the product should explicitly not attempt to do.</span>
                <textarea v-model="entry.statement" class="field-input textarea" rows="3" />
                <small v-if="entryHasIssue(index)" class="field-error-copy">Statement is required.</small>
              </label>
              <label class="field field-full">
                <span class="field-label">Rationale</span>
                <span class="field-help">Explain why this capability or behavior is intentionally out of scope.</span>
                <textarea v-model="entry.rationale" class="field-input textarea" rows="3" />
              </label>
            </div>
          </article>
        </div>

        <div class="footer-row">
          <button class="btn btn-secondary" type="button" :disabled="readOnlyMode" @click="addEntry">Add Non-Goal</button>
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
  margin-bottom: 1.5rem;
}

.page-kicker {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 0.4rem;
}

.page-header h1 {
  margin: 0 0 0.5rem;
  font-size: 30px;
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
  color: var(--text-secondary);
  padding: 0;
  cursor: pointer;
}

.panel {
  background: var(--surface-depth-panel);
  border: 1px solid var(--surface-border-panel);
  border-radius: 18px;
  padding: 1.25rem;
}

.panel-header,
.entry-header,
.footer-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}

.panel-header {
  margin-bottom: 1rem;
}

.entry-header {
  margin-bottom: 1rem;
}

.footer-row {
  margin-top: 1rem;
}

.panel-header h2,
.entry-header h3 {
  margin: 0;
}

.entry-header h3 {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
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

.panel-copy {
  margin: 0.35rem 0 0;
  color: var(--text-secondary);
  max-width: 72ch;
  line-height: 1.5;
}

.actions,
.footer-row {
  flex-wrap: wrap;
}

.actions {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  justify-content: flex-end;
}

.actions .btn,
.footer-row .btn,
.entry-header .btn {
  width: auto;
}

.card-stack {
  display: grid;
  gap: 1rem;
}

.entry-card {
  border: 1px solid var(--surface-border-card);
  border-radius: 16px;
  background: var(--surface-depth-card);
  padding: 1rem;
}

.summary-entry-card p,
.summary-entry-card small,
.empty-editor-state p {
  color: var(--text-secondary);
  line-height: 1.55;
  margin: 0;
}

.summary-entry-card small {
  display: block;
  margin-top: 0.55rem;
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
  margin-top: 0.85rem;
}

.detail-grid > div {
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  background: var(--surface-depth-inset);
  padding: 0.75rem;
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

.detail-grid p {
  color: var(--text-primary);
  line-height: 1.5;
  margin: 0;
  overflow-wrap: anywhere;
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
  gap: 1rem;
}

.field {
  display: grid;
  gap: 0.45rem;
  min-width: 0;
}

.field-full {
  grid-column: 1 / -1;
}

.field-label {
  font-weight: 600;
  color: var(--text-primary);
}

.field-help {
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.5;
}

.field-input {
  width: 100%;
  min-width: 0;
  max-width: 100%;
  box-sizing: border-box;
  border-radius: 12px;
  border: 1px solid var(--surface-border-card);
  background: var(--surface-depth-card);
  color: var(--text-primary);
  padding: 0.75rem 0.9rem;
}

.textarea {
  resize: vertical;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  padding: 0.35rem 0.7rem;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.15);
  color: var(--text-secondary);
}

.status-pill.ready {
  background: rgba(16, 185, 129, 0.16);
  color: #86efac;
}
</style>
<style scoped src="./product-inline-errors.css"></style>
