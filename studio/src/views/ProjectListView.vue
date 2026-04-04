<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { projectStore, checkDbAvailable, loadProjects, seedDb } from '../design/project-store'
import { createProject, deleteProject } from '../design/project-api'
import { PACKS } from '../design/data/packs.generated'

const router = useRouter()

const showCreateForm = ref(false)
const newName = ref('')
const newDomain = ref('')
const newSummary = ref('')
const creating = ref(false)
const deletingProjectId = ref<string | null>(null)
const cleaningJunk = ref(false)

const dbAvailable = computed(() => projectStore.dbAvailable)
const projects = computed(() => projectStore.projects)
const loading = computed(() => projectStore.loading)
const error = computed(() => projectStore.error)
const junkProjects = computed(() =>
  projects.value.filter(project =>
    project.id.startsWith('proj-') &&
    !project.domain &&
    !project.summary &&
    (!project.labels || project.labels.length === 0),
  ),
)

onMounted(async () => {
  await checkDbAvailable()
  if (projectStore.dbAvailable) {
    await loadProjects()
  }
})

function openProject(id: string) {
  router.push(`/design/projects/${id}`)
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
    await createProject({
      id,
      name,
      domain: newDomain.value.trim() || undefined,
      summary: newSummary.value.trim() || undefined,
    })
    newName.value = ''
    newDomain.value = ''
    newSummary.value = ''
    showCreateForm.value = false
    await loadProjects()
    router.push(`/design/projects/${id}`)
  } catch {
    // error is surfaced via projectStore.error
  } finally {
    creating.value = false
  }
}

async function handleSeed() {
  await seedDb()
}

async function handleDeleteProject(projectId: string, projectName: string, event: Event) {
  event.stopPropagation()
  if (!window.confirm(`Delete project "${projectName}"? This will remove its requirements, scenarios, shapes, and evaluations.`)) {
    return
  }

  deletingProjectId.value = projectId
  try {
    await deleteProject(projectId)
    await loadProjects()
  } finally {
    deletingProjectId.value = null
  }
}

async function handleCleanJunkProjects() {
  if (junkProjects.value.length === 0) return
  if (!window.confirm(`Delete ${junkProjects.value.length} test projects from the local Studio database?`)) {
    return
  }

  cleaningJunk.value = true
  try {
    for (const project of junkProjects.value) {
      await deleteProject(project.id)
    }
    await loadProjects()
  } finally {
    cleaningJunk.value = false
  }
}
</script>

<template>
  <div class="project-list">
    <h1 class="page-title">Projects</h1>
    <p class="page-desc">Manage your ANIP design projects, clean out test clutter, or load showcase examples people can explore.</p>

    <!-- Sidecar unavailable banner + read-only pack cards -->
    <template v-if="!dbAvailable">
      <div class="banner banner-warning">
        Sidecar unavailable — read-only mode
      </div>
      <div class="pack-grid">
        <div
          v-for="pack in PACKS"
          :key="pack.meta.id"
          class="pack-card"
          @click="openPack(pack.meta.id)"
        >
          <div class="pack-header">
            <span class="domain-badge">{{ pack.meta.domain }}</span>
            <span
              v-if="pack.meta.result"
              class="result-badge"
              :class="'result-' + pack.meta.result.toLowerCase().replace('_', '-')"
            >{{ pack.meta.result }}</span>
          </div>
          <h3 class="card-name">{{ pack.meta.name }}</h3>
          <p class="card-summary">{{ pack.meta.narrative }}</p>
        </div>
      </div>
    </template>

    <!-- DB available: project list -->
    <template v-else>
      <div class="toolbar">
        <button class="btn btn-primary" @click="showCreateForm = !showCreateForm">
          {{ showCreateForm ? 'Cancel' : 'Create Project' }}
        </button>
        <button
          v-if="junkProjects.length > 0"
          class="btn btn-secondary"
          @click="handleCleanJunkProjects"
          :disabled="cleaningJunk"
        >
          {{ cleaningJunk ? 'Cleaning...' : `Clean Test Projects (${junkProjects.length})` }}
        </button>
        <button
          v-if="projects.length === 0 && !loading"
          class="btn btn-secondary"
          @click="handleSeed"
          :disabled="loading"
        >
          Seed from Examples
        </button>
      </div>

      <!-- Inline create form -->
      <div v-if="showCreateForm" class="create-form">
        <div class="form-row">
          <input
            v-model="newName"
            class="form-input"
            placeholder="Project name"
            @keyup.enter="handleCreate"
          />
          <input
            v-model="newDomain"
            class="form-input form-input-sm"
            placeholder="Domain (e.g. travel)"
          />
        </div>
        <input
          v-model="newSummary"
          class="form-input"
          placeholder="Summary (optional)"
        />
        <button
          class="btn btn-primary"
          @click="handleCreate"
          :disabled="!newName.trim() || creating"
        >
          {{ creating ? 'Creating...' : 'Create' }}
        </button>
      </div>

      <div v-if="loading && projects.length === 0" class="empty-state">
        Loading projects...
      </div>

      <div v-if="error" class="banner banner-error">{{ error }}</div>

      <div v-if="!loading && projects.length === 0 && !error" class="empty-state">
        No projects yet. Create one or seed from example packs.
      </div>

      <div class="pack-grid">
        <div
          v-for="project in projects"
          :key="project.id"
          class="pack-card"
          @click="openProject(project.id)"
        >
          <div class="pack-header">
            <span class="domain-badge">{{ project.domain || 'general' }}</span>
          </div>
          <h3 class="card-name">{{ project.name }}</h3>
          <p class="card-summary">{{ project.summary || 'No summary' }}</p>
          <div class="card-meta">
            <span v-if="project.labels?.length" class="card-labels">
              <span v-for="label in project.labels" :key="label" class="label-chip">{{ label }}</span>
            </span>
            <button
              class="delete-link"
              :disabled="deletingProjectId !== null || cleaningJunk"
              @click="handleDeleteProject(project.id, project.name, $event)"
            >
              {{ deletingProjectId === project.id ? 'Deleting...' : 'Delete' }}
            </button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.project-list {
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

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
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

.create-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 1rem;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin-bottom: 1rem;
  max-width: 480px;
}

.form-row {
  display: flex;
  gap: 8px;
}

.form-input {
  flex: 1;
  height: 36px;
  padding: 0 12px;
  background: var(--bg-app);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 13px;
  outline: none;
  transition: border-color var(--transition);
}

.form-input::placeholder {
  color: var(--text-muted);
}

.form-input:focus {
  border-color: var(--border-focus);
}

.form-input-sm {
  max-width: 140px;
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

.result-partial {
  background: rgba(251, 191, 36, 0.15);
  color: var(--design-partial, #fbbf24);
}

.result-requires-glue {
  background: rgba(248, 113, 113, 0.15);
  color: var(--design-glue, #f87171);
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
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.card-labels {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.label-chip {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 8px;
  background: var(--bg-hover);
  color: var(--text-muted);
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
