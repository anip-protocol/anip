<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { createPmArtifact, deletePmArtifact, updatePmArtifact } from '../design/project-api'
import { requestConfirmation } from '../design/confirm'
import {
  cloneProductDesignData,
  defaultSuccessCriteriaData,
  findSuccessCriteriaArtifact,
  isSuccessCriteriaComplete,
  makeBlankSuccessCriteria,
  persistedPmArtifactStatus,
  productDesignArtifactId,
  SUCCESS_CRITERIA_ARTIFACT_TYPE,
  type SuccessCriteriaData,
  type SuccessCriteriaPriority,
} from '../design/product-design'
import { loadProject, projectStore } from '../design/project-store'
import ProjectIssueBanner from '../components/ProjectIssueBanner.vue'
import { useProjectIssue } from '../design/use-project-issue'

const route = useRoute()
const router = useRouter()

const projectId = computed(() => route.params.projectId as string)
const project = computed(() => projectStore.activeProject)
const artifact = computed(() => findSuccessCriteriaArtifact(projectStore.artifacts.pmArtifacts))
const baseData = ref<SuccessCriteriaData>(defaultSuccessCriteriaData())
const draft = ref<SuccessCriteriaData>(defaultSuccessCriteriaData())
const saving = ref(false)
const deleting = ref(false)
const saveError = ref<string | null>(null)
const editing = ref(false)
const pageIssue = useProjectIssue('project-success-criteria')
const readOnlyMode = computed(() => projectStore.runtimeStatus?.read_only_mode !== false)
const readOnlyReason = computed(() =>
  projectStore.runtimeStatus?.read_only_reason
  || 'Studio is running in read-only mode. Explore the design, then run Studio locally to make changes.',
)

const priorityOptions: Array<{ value: SuccessCriteriaPriority; label: string }> = [
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
]

async function ensureLoaded() {
  if (!projectId.value) return
  if (projectStore.activeProject?.id === projectId.value) return
  await loadProject(projectId.value)
}

function syncDraft() {
  const next = artifact.value?.data
    ? cloneProductDesignData(artifact.value.data as SuccessCriteriaData)
    : defaultSuccessCriteriaData()
  if (!next.entries.length) {
    next.entries = [makeBlankSuccessCriteria()]
  }
  next.entries = next.entries.map((entry) => ({
    ...makeBlankSuccessCriteria(),
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
const isComplete = computed(() => isSuccessCriteriaComplete(draft.value))
const pageHasIssue = computed(() => Boolean(pageIssue.value?.count) && !isComplete.value)

function entryHasIssue(index: number): boolean {
  const entry = draft.value.entries[index]
  return pageHasIssue.value && Boolean(entry) && (
    !entry.statement.trim()
    || !entry.evidence.trim()
  )
}

function missingEntryField(index: number, field: 'statement' | 'evidence'): boolean {
  return pageHasIssue.value && !draft.value.entries[index]?.[field]?.trim()
}

function addEntry() {
  if (readOnlyMode.value) return
  draft.value.entries.push(makeBlankSuccessCriteria())
}

function removeEntry(index: number) {
  if (readOnlyMode.value) return
  draft.value.entries.splice(index, 1)
  if (!draft.value.entries.length) {
    draft.value.entries.push(makeBlankSuccessCriteria())
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
    const payload: SuccessCriteriaData = {
      ...cloneProductDesignData(draft.value),
      artifact_type: SUCCESS_CRITERIA_ARTIFACT_TYPE,
      entries: draft.value.entries.filter((entry) =>
        entry.statement.trim().length > 0 || entry.evidence.trim().length > 0 || entry.review_method.trim().length > 0,
      ),
    }
    if (!payload.entries.length) {
      payload.entries = [makeBlankSuccessCriteria()]
    }
    if (artifact.value) {
      await updatePmArtifact(project.value.id, artifact.value.id, {
        title: 'Success Criteria',
        status: persistedPmArtifactStatus(isSuccessCriteriaComplete(payload)),
        data: payload,
      })
    } else {
      await createPmArtifact(project.value.id, {
        id: productDesignArtifactId(project.value.id, SUCCESS_CRITERIA_ARTIFACT_TYPE),
        title: 'Success Criteria',
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
    title: 'Delete Success Criteria?',
    message: 'This removes the saved Product Design success criteria from the project.',
    confirmLabel: 'Delete Success Criteria',
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
        <h1>Success Criteria</h1>
        <p>
          Define how PM and business stakeholders will judge whether the product is actually delivering the intended
          value. These are the criteria developers and reviewers should be able to trace back to the shipped result.
        </p>
      </section>

      <ProjectIssueBanner :issue="pageIssue" title="Success Criteria diagnostics" />

      <div v-if="saveError" class="banner banner-error">{{ saveError }}</div>
      <div v-if="readOnlyMode" class="banner banner-warning readonly-banner">{{ readOnlyReason }}</div>

      <section class="panel" :class="{ 'field-error-card': pageHasIssue }">
        <div class="panel-header">
          <div>
            <h2>Success Measures</h2>
            <p class="panel-copy">
              Success criteria should be specific enough that PM review and delivery review can refer back to them later.
            </p>
          </div>
          <div class="actions">
            <button v-if="!editing" class="btn btn-secondary" type="button" :disabled="readOnlyMode" @click="startEditing">
              {{ artifact ? 'Edit Success Criteria' : 'Add Success Criteria' }}
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
              <h3>Success Criterion {{ index + 1 }}</h3>
              <span class="summary-chip">{{ entry.priority }}</span>
            </div>
            <p>{{ entry.statement || 'No statement captured.' }}</p>
            <small>Evidence: {{ entry.evidence || 'Not captured' }}</small>
            <details class="view-details">
              <summary>View all saved values</summary>
              <div class="detail-grid">
                <div class="detail-wide"><span>Statement</span><p>{{ entry.statement || 'Not captured' }}</p></div>
                <div><span>Priority</span><strong>{{ entry.priority || 'Not captured' }}</strong></div>
                <div class="detail-wide"><span>Evidence</span><p>{{ entry.evidence || 'Not captured' }}</p></div>
                <div class="detail-wide"><span>Review Method</span><p>{{ entry.review_method || 'Not captured' }}</p></div>
              </div>
            </details>
          </article>
        </div>

        <div v-else-if="!editing" class="empty-editor-state">
          <strong>No success criteria saved yet.</strong>
          <p>Add criteria when you are ready to define how PM and delivery review will judge success.</p>
        </div>

        <div v-else class="card-stack">
          <article v-for="(entry, index) in draft.entries" :key="index" class="entry-card" :class="{ 'field-error-card': entryHasIssue(index) }">
            <div class="entry-header">
              <h3>Success Criterion {{ index + 1 }}</h3>
              <button class="btn btn-tertiary" type="button" :disabled="readOnlyMode" @click="removeEntry(index)">Remove</button>
            </div>
            <div class="field-grid">
              <label class="field field-full" :class="{ 'field-error': missingEntryField(index, 'statement') }">
                <span class="field-label">Statement</span>
                <span class="field-help">Describe the business result the team should be able to point to.</span>
                <textarea v-model="entry.statement" class="field-input textarea" rows="3" />
                <small v-if="missingEntryField(index, 'statement')" class="field-error-copy">Statement is required.</small>
              </label>
              <label class="field" :class="{ 'field-error': missingEntryField(index, 'evidence') }">
                <span class="field-label">Evidence</span>
                <span class="field-help">Explain what evidence PM and reviewers should look for.</span>
                <textarea v-model="entry.evidence" class="field-input textarea" rows="3" />
                <small v-if="missingEntryField(index, 'evidence')" class="field-error-copy">Evidence is required.</small>
              </label>
              <label class="field">
                <span class="field-label">Review Method</span>
                <span class="field-help">Describe how the team should review or prove this criterion, such as PM signoff, runtime evidence, audit inspection, or regression review.</span>
                <textarea v-model="entry.review_method" class="field-input textarea" rows="3" />
              </label>
              <label class="field">
                <span class="field-label">Priority</span>
                <span class="field-help">Use priority to distinguish must-have success signals from supporting ones.</span>
                <select v-model="entry.priority" class="field-input">
                  <option v-for="option in priorityOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
                </select>
              </label>
            </div>
          </article>
        </div>

        <div class="footer-row">
          <button class="btn btn-secondary" type="button" :disabled="readOnlyMode" @click="addEntry">Add Success Criterion</button>
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
  text-transform: uppercase;
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

@media (max-width: 900px) {
  .field-grid,
  .detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>
<style scoped src="./product-inline-errors.css"></style>
