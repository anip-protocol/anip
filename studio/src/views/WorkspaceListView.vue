<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { checkDbAvailable, loadWorkspaces, projectStore } from '../design/project-store'
import { createWorkspace, deleteWorkspace } from '../design/project-api'
import { PACKS } from '../design/data/packs.generated'

const router = useRouter()

const showCreateForm = ref(false)
const newName = ref('')
const newSummary = ref('')
const creating = ref(false)
const deletingWorkspaceId = ref<string | null>(null)
const cleaningWorkspaces = ref(false)

const dbAvailable = computed(() => projectStore.dbAvailable)
const workspaces = computed(() => projectStore.workspaces)
const loading = computed(() => projectStore.loading)
const error = computed(() => projectStore.error)
const junkWorkspaces = computed(() =>
  workspaces.value.filter(workspace =>
    workspace.id.startsWith('ws-') &&
    workspace.projects_count === 0,
  ),
)

onMounted(async () => {
  await checkDbAvailable()
  if (projectStore.dbAvailable) {
    await loadWorkspaces()
  }
})

function openWorkspace(id: string) {
  router.push(`/design/workspaces/${id}`)
}

function openPack(packId: string) {
  router.push(`/design/packs/${packId}`)
}

async function handleCreate() {
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
    newName.value = ''
    newSummary.value = ''
    showCreateForm.value = false
    await loadWorkspaces()
    router.push(`/design/workspaces/${id}`)
  } finally {
    creating.value = false
  }
}

async function handleDeleteWorkspace(workspaceId: string, workspaceName: string, event: Event) {
  event.stopPropagation()
  if (!window.confirm(`Delete workspace "${workspaceName}"?`)) return
  deletingWorkspaceId.value = workspaceId
  try {
    await deleteWorkspace(workspaceId)
    await loadWorkspaces()
  } finally {
    deletingWorkspaceId.value = null
  }
}

async function handleCleanWorkspaces() {
  if (junkWorkspaces.value.length === 0) return
  if (!window.confirm(`Delete ${junkWorkspaces.value.length} empty test workspaces from the local Studio database?`)) return
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
    <h1 class="page-title">Workspaces</h1>
    <p class="page-desc">Organize multiple design projects under a shared workspace, then move into service shaping and evaluation inside each project.</p>

    <template v-if="!dbAvailable">
      <div class="banner banner-warning">Sidecar unavailable — read-only mode</div>
      <div class="pack-grid">
        <div
          v-for="pack in PACKS"
          :key="pack.meta.id"
          class="pack-card"
          @click="openPack(pack.meta.id)"
        >
          <div class="pack-header">
            <span class="domain-badge">{{ pack.meta.domain }}</span>
          </div>
          <h3 class="card-name">{{ pack.meta.name }}</h3>
          <p class="card-summary">{{ pack.meta.narrative }}</p>
        </div>
      </div>
    </template>

    <template v-else>
      <div class="toolbar">
        <button class="btn btn-primary" @click="showCreateForm = !showCreateForm">
          {{ showCreateForm ? 'Cancel' : 'Create Workspace' }}
        </button>
        <button
          v-if="junkWorkspaces.length > 0"
          class="btn btn-secondary"
          @click="handleCleanWorkspaces"
          :disabled="cleaningWorkspaces"
        >
          {{ cleaningWorkspaces ? 'Cleaning...' : `Clean Empty Test Workspaces (${junkWorkspaces.length})` }}
        </button>
      </div>

      <div v-if="showCreateForm" class="create-form">
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
        </div>
      </div>

      <div v-if="loading && workspaces.length === 0" class="empty-state">Loading workspaces...</div>
      <div v-if="error" class="banner banner-error">{{ error }}</div>
      <div v-if="!loading && workspaces.length === 0 && !error" class="empty-state">
        No workspaces yet. Create one to group related design projects together.
      </div>

      <div class="pack-grid">
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
          <div class="card-meta">
            <button
              v-if="workspace.id !== 'default'"
              class="delete-link"
              :disabled="deletingWorkspaceId !== null || cleaningWorkspaces"
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
  max-width: none;
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
}

.delete-link {
  border: none;
  background: transparent;
  color: #ef4444;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  padding: 0;
}

.delete-link:hover:not(:disabled) {
  color: #dc2626;
}

.delete-link:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
