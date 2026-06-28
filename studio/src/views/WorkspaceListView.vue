<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { checkDbAvailable, loadWorkspaces, projectStore } from '../design/project-store'
import { cloneWorkspace, createWorkspace, deleteWorkspace } from '../design/project-api'
import { requestConfirmation } from '../design/confirm'
import { studioApiUnavailableMessage } from '../design/desktop-mode'

const router = useRouter()

const showCreateForm = ref(false)
const newName = ref('')
const newSummary = ref('')
const creating = ref(false)
const deletingWorkspaceId = ref<string | null>(null)
const cleaningWorkspaces = ref(false)

const dbAvailable = computed(() => projectStore.dbAvailable)
const dbChecking = computed(() => projectStore.dbChecking)
const workspaces = computed(() => projectStore.workspaces)
const loading = computed(() => projectStore.loading)
const error = computed(() => projectStore.error)
const readOnlyMode = computed(() => projectStore.runtimeStatus?.read_only_mode !== false)
const readOnlyReason = computed(
  () =>
    projectStore.runtimeStatus?.read_only_reason ||
    'Studio is running in read-only mode. Explore the design here, then run Studio locally to make changes.',
)
const startupMessage = 'Starting local Studio API...'
const startupDetail = 'Studio is launching the bundled API, opening the local database, applying migrations, and loading showcase projects.'
const pageTitle = computed(() => dbAvailable.value || dbChecking.value ? 'Workspaces' : 'Showcase Examples')
const pageDescription = computed(() =>
  dbAvailable.value
    ? 'Organize multiple design projects under a shared workspace, then move into service shaping and evaluation inside each project.'
    : dbChecking.value
      ? 'Preparing the local Studio workspace. This usually takes a few seconds on first launch.'
    : 'Studio cannot reach its API right now, so you are looking at read-only example packs instead of real workspaces and projects.',
)
const apiUnavailableMessage = computed(() => studioApiUnavailableMessage())
const junkWorkspaces = computed(() =>
  workspaces.value.filter(workspace =>
    workspace.id.startsWith('ws-') &&
    workspace.projects_count === 0,
  ),
)

function resetCreateForm() {
  newName.value = ''
  newSummary.value = ''
}

function cancelCreateWorkspace() {
  if (creating.value) return
  resetCreateForm()
  showCreateForm.value = false
}

onMounted(async () => {
  await checkDbAvailable()
  if (projectStore.dbAvailable) {
    await loadWorkspaces()
  }
})

function openWorkspace(id: string) {
  router.push(`/design/workspaces/${id}`)
}

async function handleCreate() {
  if (readOnlyMode.value) return
  const name = newName.value.trim()
  if (!name) return
  creating.value = true
  try {
    const id = crypto.randomUUID()
    await createWorkspace({
      id,
      name,
      summary: newSummary.value.trim() || undefined,
    })
    resetCreateForm()
    showCreateForm.value = false
    await loadWorkspaces()
    router.push(`/design/workspaces/${id}`)
  } finally {
    creating.value = false
  }
}

async function handleDeleteWorkspace(workspaceId: string, workspaceName: string, event: Event) {
  if (readOnlyMode.value) return
  event.stopPropagation()
  const confirmed = await requestConfirmation({
    title: 'Delete workspace?',
    message: `Delete workspace "${workspaceName}"?`,
    confirmLabel: 'Delete Workspace',
    cancelLabel: 'Cancel',
    tone: 'danger',
  })
  if (!confirmed) return
  deletingWorkspaceId.value = workspaceId
  try {
    await deleteWorkspace(workspaceId)
    await loadWorkspaces()
  } finally {
    deletingWorkspaceId.value = null
  }
}

async function handleCloneWorkspace(workspaceId: string, workspaceName: string, workspaceSummary: string, event: Event) {
  if (readOnlyMode.value) return
  event.stopPropagation()
  const cloneName = `${workspaceName} Copy`
  const confirmed = await requestConfirmation({
    title: 'Clone workspace?',
    message: `Create a full copy of "${workspaceName}" and all of its projects as "${cloneName}"?`,
    confirmLabel: 'Clone Workspace',
    cancelLabel: 'Cancel',
    tone: 'neutral',
  })
  if (!confirmed) return
  const clone = await cloneWorkspace(workspaceId, {
    name: cloneName,
    summary: workspaceSummary ? `${workspaceSummary} (copy)` : '',
  })
  await loadWorkspaces()
  router.push(`/design/workspaces/${clone.id}`)
}

async function handleCleanWorkspaces() {
  if (readOnlyMode.value) return
  if (junkWorkspaces.value.length === 0) return
  const confirmed = await requestConfirmation({
    title: 'Delete empty test workspaces?',
    message: `Delete ${junkWorkspaces.value.length} empty test workspaces from the local Studio database?`,
    confirmLabel: 'Delete Workspaces',
    cancelLabel: 'Cancel',
    tone: 'danger',
  })
  if (!confirmed) return
  cleaningWorkspaces.value = true
  try {
    for (const workspace of junkWorkspaces.value) {
      await deleteWorkspace(workspace.id)
    }
    await loadWorkspaces()
  } finally {
    cleaningWorkspaces.value = false
  }
}
</script>

<template>
  <div class="workspace-list">
    <h1 class="page-title">{{ pageTitle }}</h1>
    <p class="page-desc">{{ pageDescription }}</p>

    <template v-if="dbChecking">
      <div class="banner banner-warning">{{ startupMessage }}</div>
      <p class="fallback-note">{{ startupDetail }}</p>
    </template>

    <template v-else-if="!dbAvailable">
      <div class="banner banner-warning">{{ apiUnavailableMessage }}</div>
      <p class="fallback-note">
        Workspaces, projects, service shaping, and evaluation require the Studio API. Bring the backend back up to keep working in Studio.
      </p>
    </template>

    <template v-else>
      <div v-if="readOnlyMode" class="banner banner-warning">
        {{ readOnlyReason }}
      </div>
      <div v-if="!readOnlyMode" class="toolbar">
        <button
          class="btn btn-primary"
          :disabled="readOnlyMode"
          @click="showCreateForm ? cancelCreateWorkspace() : showCreateForm = true"
        >
          {{ showCreateForm ? 'Cancel' : 'Create Workspace' }}
        </button>
        <button
          v-if="junkWorkspaces.length > 0"
          class="btn btn-secondary"
          @click="handleCleanWorkspaces"
          :disabled="cleaningWorkspaces || readOnlyMode"
        >
          {{ cleaningWorkspaces ? 'Cleaning...' : `Clean Empty Test Workspaces (${junkWorkspaces.length})` }}
        </button>
      </div>

      <div v-if="showCreateForm && !readOnlyMode" class="create-form">
        <div class="field-group">
          <label class="field-label">Workspace Name</label>
          <input
            v-model="newName"
            class="form-input form-input-lg"
            placeholder="Workspace name"
            @keyup.enter="handleCreate"
          />
        </div>
        <div class="field-group">
          <label class="field-label">Summary</label>
          <textarea
            v-model="newSummary"
            class="form-textarea"
            placeholder="What kind of projects should live in this workspace?"
          ></textarea>
        </div>
        <div class="form-actions">
          <button
            class="btn btn-primary btn-create"
            @click="handleCreate"
            :disabled="!newName.trim() || creating"
          >
            {{ creating ? 'Creating...' : 'Create Workspace' }}
          </button>
          <button
            class="btn btn-secondary btn-create"
            type="button"
            :disabled="creating"
            @click="cancelCreateWorkspace"
          >
            Cancel
          </button>
        </div>
      </div>

      <div v-if="!showCreateForm && loading && workspaces.length === 0" class="empty-state">Loading workspaces...</div>
      <div v-if="error" class="banner banner-error">{{ error }}</div>
      <div v-if="!showCreateForm && !loading && workspaces.length === 0 && !error" class="empty-state">
        No workspaces yet. Create one to group related design projects together.
      </div>

      <div v-if="!showCreateForm" class="pack-grid">
        <div
          v-for="workspace in workspaces"
          :key="workspace.id"
          class="pack-card"
          @click="openWorkspace(workspace.id)"
        >
          <div class="pack-header">
            <span class="domain-badge">workspace</span>
            <span class="result-badge result-handled">{{ workspace.projects_count }} project{{ workspace.projects_count === 1 ? '' : 's' }}</span>
          </div>
          <h3 class="card-name">{{ workspace.name }}</h3>
          <p class="card-summary">{{ workspace.summary || 'No summary' }}</p>
          <div v-if="!readOnlyMode" class="card-meta">
            <button
              class="action-link"
              :disabled="deletingWorkspaceId !== null || cleaningWorkspaces || readOnlyMode"
              @click="handleCloneWorkspace(workspace.id, workspace.name, workspace.summary, $event)"
            >
              Clone
            </button>
            <button
              v-if="workspace.id !== 'default'"
              class="delete-link"
              :disabled="deletingWorkspaceId !== null || cleaningWorkspaces || readOnlyMode"
              @click="handleDeleteWorkspace(workspace.id, workspace.name, $event)"
            >
              {{ deletingWorkspaceId === workspace.id ? 'Deleting...' : 'Delete' }}
            </button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.workspace-list {
  padding: 2rem;
}

.page-title {
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 0.5rem;
}

.page-desc {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0 0 1.5rem;
  line-height: 1.6;
}

.banner {
  padding: 10px 16px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 1rem;
}

.banner-warning {
  background: rgba(251, 191, 36, 0.12);
  border: 1px solid rgba(251, 191, 36, 0.3);
  color: #fbbf24;
}

.banner-error {
  background: rgba(248, 113, 113, 0.12);
  border: 1px solid rgba(248, 113, 113, 0.3);
  color: var(--error);
}

.fallback-note {
  margin: 0 0 1.25rem;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 1rem;
}

.btn {
  height: 36px;
  padding: 0 20px;
  border: none;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background var(--transition);
}

.btn-primary {
  background: var(--accent);
  color: #fff;
}

.btn-primary:hover:not(:disabled) {
  background: var(--accent-hover);
}

.btn-secondary {
  background: var(--bg-input);
  color: var(--text-secondary);
  border: 1px solid var(--border);
}

.btn-secondary:hover:not(:disabled) {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.create-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 1.5rem;
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.03), rgba(15, 23, 42, 0.06));
  border: 1px solid rgba(59, 130, 246, 0.18);
  border-radius: var(--radius);
  margin: 0 0 1.25rem;
  width: 100%;
  max-width: 720px;
  box-sizing: border-box;
}

.form-input {
  display: block;
  width: 100%;
  min-height: 48px;
  padding: 12px 16px;
  background: var(--bg-app);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 15px;
  outline: none;
  box-sizing: border-box;
  line-height: 1.2;
  appearance: none;
  -webkit-appearance: none;
}

.form-input-lg {
  min-height: 56px;
  padding: 14px 18px;
  font-size: 17px;
  font-weight: 600;
  border-width: 2px;
  line-height: 1.2;
}

.form-textarea {
  width: 100%;
  min-height: 148px;
  padding: 14px 16px;
  background: var(--bg-app);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 14px;
  line-height: 1.5;
  outline: none;
  resize: vertical;
  font-family: inherit;
  box-sizing: border-box;
}

.field-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.field-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.form-actions {
  display: flex;
  justify-content: flex-start;
  gap: 12px;
  flex-wrap: wrap;
}

.btn-create {
  width: auto;
  min-width: 168px;
  height: 38px;
}

.empty-state {
  padding: 2rem;
  text-align: center;
  color: var(--text-muted);
  font-size: 14px;
}

.pack-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

.pack-card {
  padding: 1.25rem;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  cursor: pointer;
  transition: all var(--transition);
}

.pack-card:hover {
  border-color: var(--accent);
  background: var(--bg-hover);
}

.pack-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.domain-badge {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-muted);
}

.result-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 10px;
}

.result-handled {
  background: rgba(52, 211, 153, 0.15);
  color: var(--design-handled, #34d399);
}

.card-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 0.5rem;
}

.card-summary {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
  margin: 0 0 0.5rem;
}

.card-meta {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.action-link,
.delete-link {
  border: none;
  background: transparent;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  padding: 0;
}

.action-link {
  color: var(--accent);
}

.action-link:hover:not(:disabled) {
  color: var(--accent-hover);
}

.delete-link {
  color: #ef4444;
}

.delete-link:hover:not(:disabled) {
  color: #dc2626;
}

.delete-link:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
