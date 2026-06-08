<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { createPmArtifact, deletePmArtifact, updatePmArtifact } from '../design/project-api'
import { requestConfirmation } from '../design/confirm'
import {
  ACTOR_MODEL_ARTIFACT_TYPE,
  cloneProductDesignData,
  defaultActorModelData,
  findActorModelArtifact,
  isActorModelComplete,
  makeBlankActor,
  persistedPmArtifactStatus,
  productDesignArtifactId,
  type ActorModelData,
} from '../design/product-design'
import { loadProject, projectStore } from '../design/project-store'
import ProjectIssueBanner from '../components/ProjectIssueBanner.vue'
import { useProjectIssue } from '../design/use-project-issue'

const route = useRoute()
const router = useRouter()

const projectId = computed(() => route.params.projectId as string)
const project = computed(() => projectStore.activeProject)
const artifact = computed(() => findActorModelArtifact(projectStore.artifacts.pmArtifacts))
const baseData = ref<ActorModelData>(defaultActorModelData())
const draft = ref<ActorModelData>(defaultActorModelData())
const saving = ref(false)
const deleting = ref(false)
const saveError = ref<string | null>(null)
const editing = ref(false)
const pageIssue = useProjectIssue('project-actor-model')
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
    ? cloneProductDesignData(artifact.value.data as ActorModelData)
    : defaultActorModelData()
  if (!next.actors.length) {
    next.actors = [makeBlankActor()]
  }
  next.actors = next.actors.map((actor) => ({
    ...makeBlankActor(),
    ...actor,
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
const isComplete = computed(() => isActorModelComplete(draft.value))
const pageHasIssue = computed(() => Boolean(pageIssue.value?.count) && !isComplete.value)

function actorHasIssue(index: number): boolean {
  const actor = draft.value.actors[index]
  return pageHasIssue.value && Boolean(actor) && (
    !actor.actor_id.trim()
    || !actor.title.trim()
    || !actor.summary.trim()
  )
}

function missingActorField(index: number, field: 'actor_id' | 'title' | 'summary'): boolean {
  return pageHasIssue.value && !draft.value.actors[index]?.[field]?.trim()
}

function addActor() {
  if (readOnlyMode.value) return
  draft.value.actors.push(makeBlankActor())
}

function removeActor(index: number) {
  if (readOnlyMode.value) return
  draft.value.actors.splice(index, 1)
  if (!draft.value.actors.length) {
    draft.value.actors.push(makeBlankActor())
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
    const payload: ActorModelData = {
      ...cloneProductDesignData(draft.value),
      artifact_type: ACTOR_MODEL_ARTIFACT_TYPE,
      actors: draft.value.actors.filter((actor) =>
        actor.actor_id.trim().length > 0
        || actor.title.trim().length > 0
        || actor.summary.trim().length > 0
        || actor.visibility_expectations.trim().length > 0
        || actor.action_expectations.trim().length > 0
        || actor.approval_expectations.trim().length > 0
        || actor.notes.trim().length > 0,
      ),
    }
    if (!payload.actors.length) {
      payload.actors = [makeBlankActor()]
    }
    if (artifact.value) {
      await updatePmArtifact(project.value.id, artifact.value.id, {
        title: 'Actor Model',
        status: persistedPmArtifactStatus(isActorModelComplete(payload)),
        data: payload,
      })
    } else {
      await createPmArtifact(project.value.id, {
        id: productDesignArtifactId(project.value.id, ACTOR_MODEL_ARTIFACT_TYPE),
        title: 'Actor Model',
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
    title: 'Delete Actor Model?',
    message: 'This removes the saved Product Design actor model from the project.',
    confirmLabel: 'Delete Actor Model',
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
        <h1>Actor Model</h1>
        <p>
          Define the business actors Studio should preserve through the rest of the flow. This is where PM records who
          uses the system, what each actor is allowed to see, and what kinds of action the product is expected to support.
        </p>
      </section>

      <ProjectIssueBanner :issue="pageIssue" title="Actor Model diagnostics" />

      <div v-if="saveError" class="banner banner-error">{{ saveError }}</div>
      <div v-if="readOnlyMode" class="banner banner-warning readonly-banner">{{ readOnlyReason }}</div>

      <section class="panel" :class="{ 'field-error-card': pageHasIssue }">
        <div class="panel-header">
          <div>
            <h2>Actors</h2>
            <p class="panel-copy">
              Each actor entry should stay in business language. Developer Design will formalize this later into policy,
              permissions, and capability contracts.
            </p>
          </div>
          <div class="actions">
            <button v-if="!editing" class="btn btn-secondary" type="button" :disabled="readOnlyMode" @click="startEditing">
              {{ artifact ? 'Edit Actors' : 'Add Actors' }}
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
          <article v-for="(actor, index) in baseData.actors" :key="`summary-${index}`" class="entry-card summary-entry-card">
            <div class="entry-header">
              <h3>{{ actor.title || `Actor ${index + 1}` }}</h3>
              <span class="summary-chip">{{ actor.actor_id || 'no id' }}</span>
            </div>
            <p>{{ actor.summary || 'No summary captured.' }}</p>
            <small>Visibility: {{ actor.visibility_expectations || 'Not captured' }}</small>
            <details class="view-details">
              <summary>View all saved values</summary>
              <div class="detail-grid">
                <div><span>Actor ID</span><strong>{{ actor.actor_id || 'Not captured' }}</strong></div>
                <div><span>Title</span><strong>{{ actor.title || 'Not captured' }}</strong></div>
                <div class="detail-wide"><span>Summary</span><p>{{ actor.summary || 'Not captured' }}</p></div>
                <div><span>Visibility Expectations</span><p>{{ actor.visibility_expectations || 'Not captured' }}</p></div>
                <div><span>Action Expectations</span><p>{{ actor.action_expectations || 'Not captured' }}</p></div>
                <div><span>Approval Expectations</span><p>{{ actor.approval_expectations || 'Not captured' }}</p></div>
                <div><span>Notes</span><p>{{ actor.notes || 'Not captured' }}</p></div>
              </div>
            </details>
          </article>
        </div>

        <div v-else-if="!editing" class="empty-editor-state">
          <strong>No actor model saved yet.</strong>
          <p>Add actors when you are ready to capture PM-owned visibility, action, and approval expectations.</p>
        </div>

        <div v-else class="card-stack">
          <article v-for="(actor, index) in draft.actors" :key="index" class="entry-card" :class="{ 'field-error-card': actorHasIssue(index) }">
            <div class="entry-header">
              <h3>Actor {{ index + 1 }}</h3>
              <button class="btn btn-tertiary" type="button" :disabled="readOnlyMode" @click="removeActor(index)">Remove</button>
            </div>
            <div class="field-grid">
              <label class="field" :class="{ 'field-error': missingActorField(index, 'actor_id') }">
                <span class="field-label">Actor ID</span>
                <span class="field-help">Use a stable business-facing identifier such as <code>rev_ops_manager</code>.</span>
                <input v-model="actor.actor_id" class="field-input" type="text" />
                <small v-if="missingActorField(index, 'actor_id')" class="field-error-copy">Actor ID is required.</small>
              </label>
              <label class="field" :class="{ 'field-error': missingActorField(index, 'title') }">
                <span class="field-label">Title</span>
                <span class="field-help">The role name business stakeholders would recognize.</span>
                <input v-model="actor.title" class="field-input" type="text" />
                <small v-if="missingActorField(index, 'title')" class="field-error-copy">Title is required.</small>
              </label>
              <label class="field field-full" :class="{ 'field-error': missingActorField(index, 'summary') }">
                <span class="field-label">Summary</span>
                <span class="field-help">Describe what this actor is trying to get done with the product.</span>
                <textarea v-model="actor.summary" class="field-input textarea" rows="3" />
                <small v-if="missingActorField(index, 'summary')" class="field-error-copy">Summary is required.</small>
              </label>
              <label class="field">
                <span class="field-label">Visibility Expectations</span>
                <span class="field-help">What should this actor be able to inspect, but not necessarily act on?</span>
                <textarea v-model="actor.visibility_expectations" class="field-input textarea" rows="3" />
              </label>
              <label class="field">
                <span class="field-label">Action Expectations</span>
                <span class="field-help">What kinds of actions or requests should the product support for this actor?</span>
                <textarea v-model="actor.action_expectations" class="field-input textarea" rows="3" />
              </label>
              <label class="field">
                <span class="field-label">Approval Expectations</span>
                <span class="field-help">When should this actor be allowed to proceed directly, and when should the product stop for approval or human confirmation?</span>
                <textarea v-model="actor.approval_expectations" class="field-input textarea" rows="3" />
              </label>
              <label class="field field-full">
                <span class="field-label">Notes</span>
                <span class="field-help">Capture any business nuances the rest of the design flow should preserve.</span>
                <textarea v-model="actor.notes" class="field-input textarea" rows="3" />
              </label>
            </div>
          </article>
        </div>

        <div class="footer-row">
          <button class="btn btn-secondary" type="button" :disabled="readOnlyMode" @click="addActor">Add Actor</button>
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

.footer-row {
  margin-top: 1.25rem;
  flex-wrap: wrap;
}

.panel-header h2 {
  margin: 0;
  font-size: 20px;
  line-height: 1.25;
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

.actions .btn,
.footer-row .btn,
.entry-header .btn {
  width: auto;
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
  min-width: 0;
  max-width: 100%;
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
