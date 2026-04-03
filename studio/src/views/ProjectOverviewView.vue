<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  projectStore,
  loadProject,
  loadVocabulary,
  setActiveRequirements,
  setActiveProposal,
} from '../design/project-store'
import { exportProject, importArtifacts } from '../design/project-api'

const route = useRoute()
const router = useRouter()

const projectId = computed(() => route.params.projectId as string)
const project = computed(() => projectStore.activeProject)
const loading = computed(() => projectStore.loading)
const error = computed(() => projectStore.error)

const requirements = computed(() => projectStore.artifacts.requirements)
const scenarios = computed(() => projectStore.artifacts.scenarios)
const proposals = computed(() => projectStore.artifacts.proposals)
const evaluations = computed(() => projectStore.artifacts.evaluations)

const activeRequirementsId = computed(() => projectStore.activeRequirementsId)
const activeProposalId = computed(() => projectStore.activeProposalId)

const importing = ref(false)
const exporting = ref(false)

onMounted(() => {
  if (projectId.value) {
    loadProject(projectId.value)
    loadVocabulary(projectId.value)
  }
})

watch(projectId, (id) => {
  if (id) {
    loadProject(id)
    loadVocabulary(id)
  }
})

function onRequirementsChange(event: Event) {
  const value = (event.target as HTMLSelectElement).value
  setActiveRequirements(value || null)
}

function onProposalChange(event: Event) {
  const value = (event.target as HTMLSelectElement).value
  setActiveProposal(value || null)
}

function navigateRequirements(id: string) {
  router.push(`/design/projects/${projectId.value}/requirements/${id}`)
}

function navigateScenario(id: string) {
  router.push(`/design/projects/${projectId.value}/scenarios/${id}`)
}

function navigateProposal(id: string) {
  router.push(`/design/projects/${projectId.value}/proposals/${id}`)
}

function navigateEvaluation(id: string) {
  router.push(`/design/projects/${projectId.value}/evaluations/${id}`)
}

async function handleExport() {
  if (!projectId.value) return
  exporting.value = true
  try {
    const data = await exportProject(projectId.value)
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${project.value?.name ?? 'project'}-export.json`
    a.click()
    URL.revokeObjectURL(url)
  } catch {
    // error surfaced through projectStore.error
  } finally {
    exporting.value = false
  }
}

function handleImportClick() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.json'
  input.onchange = async (e) => {
    const file = (e.target as HTMLInputElement).files?.[0]
    if (!file || !projectId.value) return
    importing.value = true
    try {
      const text = await file.text()
      const parsed = JSON.parse(text)
      const artifacts = Array.isArray(parsed.artifacts) ? parsed.artifacts : []
      await importArtifacts(projectId.value, artifacts)
      await loadProject(projectId.value)
    } catch {
      // error surfaced through projectStore.error
    } finally {
      importing.value = false
    }
  }
  input.click()
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}
</script>

<template>
  <div class="project-overview">
    <div v-if="loading && !project" class="loading-state">Loading project...</div>
    <div v-else-if="error && !project" class="error-state">{{ error }}</div>

    <template v-if="project">
      <!-- Project header -->
      <div class="project-header">
        <div class="header-top">
          <button class="back-link" @click="router.push('/design')">&larr; Projects</button>
        </div>
        <h1 class="page-title">{{ project.name }}</h1>
        <div class="project-meta">
          <span class="domain-badge">{{ project.domain || 'general' }}</span>
          <span v-if="project.summary" class="project-summary">{{ project.summary }}</span>
        </div>
      </div>

      <!-- Active design context -->
      <section class="context-section">
        <h2 class="section-title">Active Design Context</h2>
        <p class="section-desc">Select the requirements set and proposal for evaluation.</p>
        <div class="context-selects">
          <div class="context-field">
            <label class="field-label">Requirements Set</label>
            <select
              class="field-select"
              :value="activeRequirementsId ?? ''"
              @change="onRequirementsChange"
            >
              <option value="">-- Select --</option>
              <option
                v-for="r in requirements"
                :key="r.id"
                :value="r.id"
              >{{ r.title || r.id }}</option>
            </select>
          </div>
          <div class="context-field">
            <label class="field-label">Proposal</label>
            <select
              class="field-select"
              :value="activeProposalId ?? ''"
              @change="onProposalChange"
            >
              <option value="">-- Select --</option>
              <option
                v-for="p in proposals"
                :key="p.id"
                :value="p.id"
              >{{ p.title || p.id }}</option>
            </select>
          </div>
        </div>
      </section>

      <!-- Import/Export toolbar -->
      <div class="io-toolbar">
        <button class="btn btn-secondary" @click="handleImportClick" :disabled="importing">
          {{ importing ? 'Importing...' : 'Import' }}
        </button>
        <button class="btn btn-secondary" @click="handleExport" :disabled="exporting">
          {{ exporting ? 'Exporting...' : 'Export' }}
        </button>
      </div>

      <div v-if="error" class="banner banner-error">{{ error }}</div>

      <!-- Artifact lists -->
      <section class="artifact-section">
        <h2 class="section-title">Requirements ({{ requirements.length }})</h2>
        <div v-if="requirements.length === 0" class="empty-row">No requirements sets yet.</div>
        <div
          v-for="r in requirements"
          :key="r.id"
          class="artifact-row"
          @click="navigateRequirements(r.id)"
        >
          <span class="artifact-title">{{ r.title || r.id }}</span>
          <span class="artifact-status" :class="'status-' + r.status">{{ r.status }}</span>
          <span class="artifact-date">{{ formatDate(r.updated_at) }}</span>
        </div>
      </section>

      <section class="artifact-section">
        <h2 class="section-title">Scenarios ({{ scenarios.length }})</h2>
        <div v-if="scenarios.length === 0" class="empty-row">No scenarios yet.</div>
        <div
          v-for="s in scenarios"
          :key="s.id"
          class="artifact-row"
          @click="navigateScenario(s.id)"
        >
          <span class="artifact-title">{{ s.title || s.id }}</span>
          <span class="artifact-status" :class="'status-' + s.status">{{ s.status }}</span>
          <span class="artifact-date">{{ formatDate(s.updated_at) }}</span>
        </div>
      </section>

      <section class="artifact-section">
        <h2 class="section-title">Proposals ({{ proposals.length }})</h2>
        <div v-if="proposals.length === 0" class="empty-row">No proposals yet.</div>
        <div
          v-for="p in proposals"
          :key="p.id"
          class="artifact-row"
          @click="navigateProposal(p.id)"
        >
          <span class="artifact-title">{{ p.title || p.id }}</span>
          <span class="artifact-status" :class="'status-' + p.status">{{ p.status }}</span>
          <span class="artifact-date">{{ formatDate(p.updated_at) }}</span>
        </div>
      </section>

      <section class="artifact-section">
        <h2 class="section-title">Evaluations ({{ evaluations.length }})</h2>
        <div v-if="evaluations.length === 0" class="empty-row">No evaluations yet.</div>
        <div
          v-for="e in evaluations"
          :key="e.id"
          class="artifact-row"
          @click="navigateEvaluation(e.id)"
        >
          <span class="artifact-title">{{ e.id }}</span>
          <span class="artifact-status" :class="'status-' + e.result.toLowerCase()">{{ e.result }}</span>
          <span class="artifact-date">{{ formatDate(e.created_at) }}</span>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.project-overview {
  padding: 2rem;
  max-width: 900px;
}

.loading-state,
.error-state {
  padding: 2rem;
  text-align: center;
  color: var(--text-muted);
  font-size: 14px;
}

.error-state {
  color: var(--error);
}

.project-header {
  margin-bottom: 1.5rem;
}

.header-top {
  margin-bottom: 0.5rem;
}

.back-link {
  background: none;
  border: none;
  color: var(--accent);
  font-size: 13px;
  cursor: pointer;
  padding: 0;
  transition: color var(--transition);
}

.back-link:hover {
  color: var(--accent-hover);
}

.page-title {
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 0.5rem;
}

.project-meta {
  display: flex;
  align-items: center;
  gap: 12px;
}

.domain-badge {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-muted);
  background: var(--bg-hover);
  padding: 2px 8px;
  border-radius: 8px;
}

.project-summary {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.5;
}

/* Active design context */
.context-section {
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.25rem;
  margin-bottom: 1.5rem;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 0.25rem;
}

.section-desc {
  font-size: 13px;
  color: var(--text-muted);
  margin: 0 0 0.75rem;
}

.context-selects {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.context-field {
  flex: 1;
  min-width: 200px;
}

.field-label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.field-select {
  width: 100%;
  height: 34px;
  padding: 0 10px;
  background: var(--bg-app);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 13px;
  outline: none;
  transition: border-color var(--transition);
}

.field-select:focus {
  border-color: var(--border-focus);
}

/* Import / Export */
.io-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 1.5rem;
}

.btn {
  height: 34px;
  padding: 0 16px;
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

.btn-secondary {
  background: var(--bg-input);
  color: var(--text-secondary);
  border: 1px solid var(--border);
}

.btn-secondary:hover:not(:disabled) {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.banner {
  padding: 10px 16px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 1rem;
}

.banner-error {
  background: rgba(248, 113, 113, 0.12);
  border: 1px solid rgba(248, 113, 113, 0.3);
  color: var(--error);
}

/* Artifact sections */
.artifact-section {
  margin-bottom: 1.5rem;
}

.artifact-section .section-title {
  margin-bottom: 0.5rem;
}

.empty-row {
  font-size: 13px;
  color: var(--text-muted);
  padding: 8px 0;
}

.artifact-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  margin-bottom: 4px;
  background: var(--bg-input);
  cursor: pointer;
  transition: all var(--transition);
}

.artifact-row:hover {
  border-color: var(--accent);
  background: var(--bg-hover);
}

.artifact-title {
  flex: 1;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.artifact-status {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 10px;
  text-transform: capitalize;
  background: var(--bg-hover);
  color: var(--text-muted);
}

.status-active,
.status-handled {
  background: rgba(52, 211, 153, 0.15);
  color: var(--design-handled, #34d399);
}

.status-draft {
  background: rgba(251, 191, 36, 0.15);
  color: var(--design-partial, #fbbf24);
}

.status-partial {
  background: rgba(251, 191, 36, 0.15);
  color: var(--design-partial, #fbbf24);
}

.status-requires_glue,
.status-requires-glue {
  background: rgba(248, 113, 113, 0.15);
  color: var(--design-glue, #f87171);
}

.artifact-date {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
}
</style>
