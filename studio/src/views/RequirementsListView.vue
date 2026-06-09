<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { createRequirements, deleteRequirements, setRequirementsRole, updateRequirements } from '../design/project-api'
import { makeRequirementsTemplate } from '../design/intent-drafts'
import { loadProject, projectStore, refreshArtifacts, setActiveRequirements } from '../design/project-store'
import { requestConfirmation } from '../design/confirm'
import type { DeveloperBaselineData } from '../design/project-types'
import { findDeveloperBaselineArtifact } from '../design/traceability'
import ProjectIssueBanner from '../components/ProjectIssueBanner.vue'
import { useProjectIssue } from '../design/use-project-issue'

const route = useRoute()
const router = useRouter()

const projectId = computed(() => route.params.projectId as string)
const project = computed(() => projectStore.activeProject)
const requirements = computed(() => projectStore.artifacts.requirements)
const loading = computed(() => projectStore.loading)
const error = computed(() => projectStore.error)
const creating = ref(false)
const promotingId = ref<string | null>(null)
const deletingId = ref<string | null>(null)
const editingId = ref<string | null>(null)
const editingTitle = ref('')
const baselineArtifact = computed(() => findDeveloperBaselineArtifact(projectStore.artifacts.pmArtifacts))
const baseline = computed(() =>
  (baselineArtifact.value?.data as DeveloperBaselineData | undefined) ?? null,
)
const pageIssue = useProjectIssue('project-requirements-list')
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

onMounted(ensureLoaded)
watch(projectId, ensureLoaded)

const primaryRequirements = computed(() => requirements.value.filter((item) => item.role === 'primary'))
const alternativeRequirements = computed(() => requirements.value.filter((item) => item.role === 'alternative'))
function recordIsLocked(record: { id: string }) {
  return !!baseline.value && baseline.value.source_inputs.requirements_id === record.id
}

function nextRevisionTitle(title: string) {
  const trimmed = title.trim() || 'Requirements'
  const match = trimmed.match(/^(.*?)(?:\s+Revision\s+(\d+))?$/i)
  if (!match) return `${trimmed} Revision 2`
  const base = (match[1] || trimmed).trim()
  const current = match[2] ? Number(match[2]) : 1
  return `${base} Revision ${current + 1}`
}

async function handleCreate() {
  if (readOnlyMode.value || !projectId.value || !project.value) return
  creating.value = true
  try {
    const created = await createRequirements(projectId.value, {
      id: `req-${crypto.randomUUID()}`,
      title: requirements.value.length === 0 ? 'Requirements' : `Requirements ${requirements.value.length + 1}`,
      data: makeRequirementsTemplate(project.value.name, project.value.domain),
    })
    await refreshArtifacts()
    setActiveRequirements(created.id)
    router.push(`/design/projects/${projectId.value}/requirements/${created.id}`)
  } finally {
    creating.value = false
  }
}

async function handlePromote(id: string) {
  if (readOnlyMode.value || !projectId.value) return
  promotingId.value = id
  try {
    await setRequirementsRole(projectId.value, id, 'primary')
    await refreshArtifacts()
    setActiveRequirements(id)
  } finally {
    promotingId.value = null
  }
}

function beginRename(record: { id: string; title?: string | null }) {
  if (readOnlyMode.value) return
  editingId.value = record.id
  editingTitle.value = record.title ?? ''
}

function cancelRename() {
  editingId.value = null
  editingTitle.value = ''
}

async function saveRename(record: { id: string; title?: string | null; status: string; data: Record<string, any> }) {
  if (readOnlyMode.value || !projectId.value) return
  if (recordIsLocked(record)) {
    const created = await createRequirements(projectId.value, {
      id: `req-${crypto.randomUUID()}`,
      title: nextRevisionTitle(editingTitle.value.trim() || record.title || 'Requirements'),
      data: record.data,
    })
    await setRequirementsRole(projectId.value, created.id, 'primary')
    await refreshArtifacts()
    cancelRename()
    router.push(`/design/projects/${projectId.value}/requirements/${created.id}`)
    return
  }
  await updateRequirements(projectId.value, record.id, {
    title: editingTitle.value.trim() || record.title || 'Requirements',
    status: record.status,
    data: record.data,
  })
  await refreshArtifacts()
  cancelRename()
}

async function handleDelete(record: { id: string; title?: string | null }) {
  if (readOnlyMode.value || !projectId.value) return
  const confirmed = await requestConfirmation({
    title: 'Delete these requirements?',
    message: `This will permanently remove "${record.title || 'this requirements artifact'}" from the current project.`,
    confirmLabel: 'Delete Requirements',
    cancelLabel: 'Cancel',
    tone: 'danger',
  })
  if (!confirmed) return

  deletingId.value = record.id
  try {
    await deleteRequirements(projectId.value, record.id)
    await refreshArtifacts()
    if (editingId.value === record.id) {
      cancelRename()
    }
  } finally {
    deletingId.value = null
  }
}

function openRequirement(id: string) {
  setActiveRequirements(id)
  router.push(`/design/projects/${projectId.value}/requirements/${id}`)
}
</script>

<template>
  <div class="requirements-list-view">
    <div v-if="loading && !project" class="empty-state">Loading requirements...</div>
    <div v-else-if="error" class="banner banner-error">{{ error }}</div>
    <template v-else-if="project">
      <section class="page-header">
        <div>
          <div class="page-kicker">What Matters</div>
          <h1>{{ project.name }}</h1>
          <p>Capture the business posture, delivery expectations, risk boundaries, and evidence expectations the rest of the design should preserve.</p>
        </div>
        <button class="btn btn-primary" :disabled="readOnlyMode || creating" @click="handleCreate">
          {{ creating ? 'Creating...' : 'New Requirements' }}
        </button>
      </section>

      <ProjectIssueBanner :issue="pageIssue" title="What Matters diagnostics" />
      <div v-if="readOnlyMode" class="banner banner-warning readonly-banner">{{ readOnlyReason }}</div>

      <section class="panel">
        <div class="panel-header">
          <div class="panel-title-row">
            <h2>Primary Requirements</h2>
            <span class="count-badge">{{ primaryRequirements.length }}</span>
          </div>
        </div>
        <div v-if="primaryRequirements.length === 0" class="empty-state">No primary requirements yet.</div>
        <div v-for="record in primaryRequirements" :key="record.id" class="artifact-entry">
          <button class="artifact-row artifact-row-inline" @click="openRequirement(record.id)">
            <span class="artifact-copy">
              <template v-if="editingId === record.id">
                <input
                  class="artifact-title-input"
                  type="text"
                  v-model="editingTitle"
                  @click.stop
                  @keydown.enter.prevent="saveRename(record)"
                />
              </template>
              <template v-else>
                <span class="artifact-title">{{ record.title || record.id }}</span>
              </template>
            </span>
            <span class="artifact-status" :class="'status-' + record.status">{{ record.status }}</span>
          </button>
          <div class="artifact-actions">
            <template v-if="editingId === record.id">
              <button class="btn btn-secondary btn-sm" @click="saveRename(record)">Save Title</button>
              <button class="btn btn-secondary btn-sm" @click="cancelRename">Cancel</button>
            </template>
            <template v-else>
              <button class="btn btn-secondary btn-sm" :disabled="readOnlyMode" @click="beginRename(record)">Rename</button>
            </template>
            <span v-if="recordIsLocked(record)" class="locked-badge">Locked</span>
            <button class="btn btn-danger btn-sm" :disabled="readOnlyMode || deletingId === record.id" @click="handleDelete(record)">
              {{ deletingId === record.id ? 'Deleting...' : 'Delete' }}
            </button>
          </div>
        </div>
      </section>

      <section class="panel">
        <div class="panel-header">
          <div class="panel-title-row">
            <h2>Alternative Requirements</h2>
            <span class="count-badge">{{ alternativeRequirements.length }}</span>
          </div>
        </div>
        <div v-if="alternativeRequirements.length === 0" class="empty-state">No alternatives yet.</div>
        <div v-for="record in alternativeRequirements" :key="record.id" class="artifact-entry">
          <button class="artifact-row artifact-row-inline" @click="openRequirement(record.id)">
            <span class="artifact-copy">
              <template v-if="editingId === record.id">
                <input
                  class="artifact-title-input"
                  type="text"
                  v-model="editingTitle"
                  @click.stop
                  @keydown.enter.prevent="saveRename(record)"
                />
              </template>
              <template v-else>
                <span class="artifact-title">{{ record.title || record.id }}</span>
              </template>
            </span>
            <span class="artifact-status" :class="'status-' + record.status">{{ record.status }}</span>
          </button>
          <div class="artifact-actions">
            <template v-if="editingId === record.id">
              <button class="btn btn-secondary btn-sm" @click="saveRename(record)">Save Title</button>
              <button class="btn btn-secondary btn-sm" @click="cancelRename">Cancel</button>
            </template>
            <template v-else>
              <button class="btn btn-secondary btn-sm" :disabled="readOnlyMode" @click="beginRename(record)">Rename</button>
            </template>
            <span v-if="recordIsLocked(record)" class="locked-badge">Locked</span>
            <button class="btn btn-secondary btn-sm" :disabled="readOnlyMode || promotingId !== null" @click="handlePromote(record.id)">
              {{ promotingId === record.id ? 'Promoting...' : 'Promote to primary' }}
            </button>
            <button class="btn btn-danger btn-sm" :disabled="readOnlyMode || deletingId === record.id" @click="handleDelete(record)">
              {{ deletingId === record.id ? 'Deleting...' : 'Delete' }}
            </button>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.requirements-list-view {
  width: 100%;
  max-width: none;
  padding: 2rem;
}

.page-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
  margin-bottom: 1.5rem;
}

.page-kicker {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 0.45rem;
}

.page-header h1 {
  margin: 0 0 0.45rem;
  font-size: 30px;
  color: var(--text-primary);
}

.page-header p,
.empty-state {
  color: var(--text-secondary);
}

.panel {
  background: var(--surface-depth-panel);
  border: 1px solid var(--surface-border-panel);
  border-radius: 18px;
  padding: 1.25rem;
}

.panel + .panel {
  margin-top: 1rem;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: center;
  margin-bottom: 1rem;
}

.panel-header h2 {
  margin: 0;
  font-size: 16px;
}

.panel-title-row {
  display: inline-flex;
  align-items: center;
  gap: 0.6rem;
}

.artifact-entry + .artifact-entry {
  margin-top: 0.75rem;
}

.artifact-row {
  width: 100%;
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: center;
  padding: 0.95rem 1rem;
  border-radius: 14px;
  border: 1px solid var(--surface-border-card);
  background: var(--surface-depth-card);
  color: inherit;
  cursor: pointer;
  text-align: left;
}

.artifact-entry {
  display: flex;
  gap: 0.75rem;
  align-items: stretch;
}

.artifact-row-inline {
  flex: 1;
}

.artifact-copy {
  flex: 1;
  min-width: 0;
}

.artifact-title {
  color: var(--text-primary);
  font-weight: 600;
}

.artifact-title-input {
  width: 100%;
  padding: 0.65rem 0.8rem;
  border-radius: 10px;
  border: 1px solid var(--surface-border-card);
  background: var(--surface-depth-card);
  color: var(--text-primary);
  font-size: 0.95rem;
  font-weight: 600;
}

.locked-badge {
  padding: 0.25rem 0.55rem;
  border-radius: 999px;
  background: rgba(251, 191, 36, 0.14);
  border: 1px solid rgba(251, 191, 36, 0.34);
  color: #fde68a;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.artifact-status {
  font-size: 12px;
  color: var(--text-secondary);
}

.artifact-actions {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  flex-wrap: wrap;
}

.btn {
  border: 1px solid var(--surface-border-card);
  border-radius: 12px;
  padding: 0.75rem 1rem;
  font-size: 14px;
  cursor: pointer;
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

.btn-danger {
  background: rgba(127, 29, 29, 0.22);
  border-color: rgba(248, 113, 113, 0.28);
  color: #fecaca;
}

.btn-sm {
  padding: 0.6rem 0.8rem;
  font-size: 12px;
}

.count-badge {
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.16);
  padding: 0.25rem 0.6rem;
  font-size: 12px;
}

.banner {
  padding: 0.75rem 0.95rem;
  border-radius: 12px;
}

.banner-error {
  background: rgba(248, 113, 113, 0.12);
  border: 1px solid rgba(248, 113, 113, 0.28);
  color: var(--error);
}

.banner-warning {
  margin-bottom: 1rem;
  background: rgba(251, 191, 36, 0.12);
  border: 1px solid rgba(251, 191, 36, 0.28);
  color: #fde68a;
}

@media (max-width: 720px) {
  .requirements-list-view {
    padding: 1.25rem;
  }

  .page-header,
  .artifact-entry {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
