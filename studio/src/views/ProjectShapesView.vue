<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { createShape } from '../design/project-api'
import { slugify } from '../design/intent-drafts'
import { loadProject, projectStore, refreshArtifacts, setActiveShape } from '../design/project-store'

const route = useRoute()
const router = useRouter()

const projectId = computed(() => route.params.projectId as string)
const project = computed(() => projectStore.activeProject)
const shapes = computed(() => projectStore.artifacts.shapes)
const requirements = computed(() => projectStore.artifacts.requirements)
const loading = computed(() => projectStore.loading)
const error = computed(() => projectStore.error)
const readOnlyMode = computed(() => projectStore.runtimeStatus?.read_only_mode !== false)
const readOnlyReason = computed(() =>
  projectStore.runtimeStatus?.read_only_reason
  || 'Studio is running in read-only mode. Explore the design, then download and run Studio locally to make changes.',
)
const creating = ref(false)
const activeRequirements = computed(() =>
  requirements.value.find((item) => item.id === projectStore.activeRequirementsId)
  ?? requirements.value.find((item) => item.role === 'primary')
  ?? requirements.value[0]
  ?? null,
)

async function ensureLoaded() {
  if (!projectId.value) return
  if (projectStore.activeProject?.id === projectId.value) return
  await loadProject(projectId.value)
}

onMounted(ensureLoaded)
watch(projectId, ensureLoaded)

function makeDefaultShape() {
  const root = project.value?.name || 'Primary Service'
  const serviceId = slugify(root) || 'primary-service'
  return {
    shape: {
      id: `shape-${crypto.randomUUID()}`,
      name: root,
      type: 'single_service',
      notes: ['Start with one bounded service shape, then expand only when the behavior pressure justifies it.'],
      services: [
        {
          id: serviceId,
          name: root,
          role: 'primary service',
          responsibilities: ['Own the main bounded workflow and the critical control checks around it.'],
          capabilities: ['handle_primary_action'],
          owns_concepts: [],
        },
      ],
      coordination: [],
      domain_concepts: [],
    },
  }
}

async function handleCreate() {
  if (readOnlyMode.value || !projectId.value || !project.value) return
  const requirementsId =
    projectStore.activeRequirementsId
    || requirements.value.find((item) => item.role === 'primary')?.id
    || requirements.value[0]?.id
    || null
  if (!requirementsId) return
  creating.value = true
  try {
    const created = await createShape(projectId.value, {
      id: `shape-${crypto.randomUUID()}`,
      title: shapes.value.length === 0 ? 'Service Shape' : `Service Shape ${shapes.value.length + 1}`,
      requirements_id: requirementsId,
      data: makeDefaultShape(),
    })
    await refreshArtifacts()
    setActiveShape(created.id)
    router.push(`/design/projects/${projectId.value}/shapes/${created.id}`)
  } finally {
    creating.value = false
  }
}

function openShape(id: string) {
  setActiveShape(id)
  router.push(`/design/projects/${projectId.value}/shapes/${id}`)
}

function shapeRoot(record: Record<string, any>) {
  return (record?.shape ?? record) as Record<string, any>
}

function serviceCount(record: Record<string, any>): number {
  const root = shapeRoot(record)
  return Array.isArray(root.services) ? root.services.length : 0
}

function coordinationCount(record: Record<string, any>): number {
  const root = shapeRoot(record)
  return Array.isArray(root.coordination) ? root.coordination.length : 0
}
</script>

<template>
  <div class="project-shapes-view">
    <div v-if="loading && !project" class="empty-state">Loading service shapes...</div>
    <div v-else-if="error" class="banner banner-error">{{ error }}</div>
    <template v-else-if="project">
      <section class="page-header">
        <div>
          <div class="page-kicker">Service Design</div>
          <h1>{{ project.name }}</h1>
          <p>Record the intended service architecture here: service boundaries, ownership, coordination, and the ANIP-visible semantics that should fall out of that design.</p>
        </div>
        <button class="btn btn-primary" :disabled="readOnlyMode || creating || requirements.length === 0" @click="handleCreate">
          {{ creating ? 'Creating...' : 'New Service Design Draft' }}
        </button>
      </section>

      <div v-if="readOnlyMode" class="banner banner-warning readonly-banner">
        {{ readOnlyReason }}
      </div>

      <section class="info-grid">
        <article class="info-card">
          <h2>What belongs here</h2>
          <ul>
            <li>Which business capabilities belong to which service boundary.</li>
            <li>Which concepts each service owns and protects.</li>
            <li>How services coordinate across approvals, handoffs, and bounded follow-up work.</li>
            <li>What ANIP behavior this design should imply, even before implementation exists.</li>
          </ul>
        </article>
        <article class="info-card">
          <h2>Current design context</h2>
          <div class="summary-row">
            <span class="summary-label">Active What Matters</span>
            <strong>{{ activeRequirements?.title || 'Not selected yet' }}</strong>
          </div>
          <div class="summary-row">
            <span class="summary-label">Service designs</span>
            <strong>{{ shapes.length }}</strong>
          </div>
          <div class="summary-row">
            <span class="summary-label">Why this matters</span>
            <strong>Service design should explain the intended decomposition before code or observed services are compared against it.</strong>
          </div>
        </article>
      </section>

      <section class="panel">
        <div class="panel-header">
          <div class="panel-title-row">
            <h2>Service Design Drafts</h2>
            <span class="count-badge">{{ shapes.length }}</span>
          </div>
        </div>
        <div v-if="requirements.length === 0" class="empty-state">Create What Matters first so a service design has a clear boundary to inherit.</div>
        <div v-else-if="shapes.length === 0" class="empty-state">No service design drafts yet.</div>
        <button
          v-for="record in shapes"
          :key="record.id"
          class="artifact-row"
          @click="openShape(record.id)"
        >
          <div class="artifact-copy">
            <span class="artifact-title">{{ record.title || record.id }}</span>
            <span class="artifact-subtitle">
              {{ serviceCount(record.data) }} service{{ serviceCount(record.data) === 1 ? '' : 's' }} ·
              {{ coordinationCount(record.data) }} coordination link{{ coordinationCount(record.data) === 1 ? '' : 's' }}
            </span>
          </div>
          <span class="artifact-status" :class="'status-' + record.status">{{ record.status }}</span>
        </button>
      </section>
    </template>
  </div>
</template>

<style scoped>
.project-shapes-view {
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
  line-height: 1.6;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.info-card {
  background: var(--surface-depth-card);
  border: 1px solid var(--surface-border-card);
  border-radius: 18px;
  padding: 1.25rem;
}

.info-card h2 {
  margin: 0 0 0.85rem;
  font-size: 16px;
}

.info-card ul {
  margin: 0;
  padding-left: 1.1rem;
  color: var(--text-secondary);
  line-height: 1.55;
}

.summary-row + .summary-row {
  margin-top: 0.85rem;
}

.summary-label {
  display: block;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 0.2rem;
}

.panel {
  background: var(--surface-depth-panel);
  border: 1px solid var(--surface-border-panel);
  border-radius: 18px;
  padding: 1.25rem;
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

.artifact-row + .artifact-row {
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

.artifact-title {
  color: var(--text-primary);
  font-weight: 600;
}

.artifact-copy {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.artifact-subtitle {
  font-size: 12px;
  color: var(--text-secondary);
}

.artifact-status {
  font-size: 12px;
  color: var(--text-secondary);
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
  background: rgba(251, 191, 36, 0.12);
  border: 1px solid rgba(251, 191, 36, 0.28);
  color: #fbbf24;
}

.readonly-banner {
  margin-bottom: 1rem;
}

@media (max-width: 720px) {
  .project-shapes-view {
    padding: 1.25rem;
  }

  .info-grid {
    grid-template-columns: 1fr;
  }

  .page-header {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
