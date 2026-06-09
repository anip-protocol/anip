<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { createScenario, deleteScenario, updateScenario } from '../design/project-api'
import { loadProject, projectStore, refreshArtifacts, setActiveScenario } from '../design/project-store'
import { slugify } from '../design/intent-drafts'
import { requestConfirmation } from '../design/confirm'
import type { DeveloperBaselineData } from '../design/project-types'
import { findDeveloperBaselineArtifact } from '../design/traceability'
import ProjectIssueBanner from '../components/ProjectIssueBanner.vue'
import { useProjectIssue } from '../design/use-project-issue'
import { validateScenario } from '../design/schemas'

const route = useRoute()
const router = useRouter()

const projectId = computed(() => route.params.projectId as string)
const project = computed(() => projectStore.activeProject)
const scenarios = computed(() => projectStore.artifacts.scenarios)
const shapes = computed(() => projectStore.artifacts.shapes)
const loading = computed(() => projectStore.loading)
const error = computed(() => projectStore.error)
const readOnlyMode = computed(() => projectStore.runtimeStatus?.read_only_mode !== false)
const readOnlyReason = computed(() =>
  projectStore.runtimeStatus?.read_only_reason
  || 'Studio is running in read-only mode. Explore the design, then download and run Studio locally to make changes.',
)
const creating = ref(false)
const deletingId = ref<string | null>(null)
const editingId = ref<string | null>(null)
const editingTitle = ref('')
const serviceFilter = ref<'all' | 'unassigned' | string>('all')
const baselineArtifact = computed(() => findDeveloperBaselineArtifact(projectStore.artifacts.pmArtifacts))
const baseline = computed(() =>
  (baselineArtifact.value?.data as DeveloperBaselineData | undefined) ?? null,
)
const pageIssue = useProjectIssue('project-scenarios-list')

const currentShape = computed(() =>
  shapes.value.find((item) => item.id === projectStore.activeShapeId)
  ?? shapes.value[0]
  ?? null,
)

const serviceOptions = computed(() => {
  const shapeData = ((currentShape.value?.data?.shape ?? currentShape.value?.data) as Record<string, any> | undefined) ?? {}
  const services = Array.isArray(shapeData.services) ? shapeData.services : []
  return services
    .map((service: Record<string, any>) => ({
      id: String(service.id ?? ''),
      label: String(service.name ?? service.id ?? 'Service'),
    }))
    .filter((service) => service.id)
})

async function ensureLoaded() {
  if (!projectId.value) return
  if (projectStore.activeProject?.id === projectId.value) return
  await loadProject(projectId.value)
}

onMounted(ensureLoaded)
watch(projectId, ensureLoaded)

function recordIsLocked(record: { id: string }) {
  return !!baseline.value && (baseline.value.source_inputs.scenario_ids ?? []).includes(record.id)
}

function nextRevisionTitle(title: string) {
  const trimmed = title.trim() || 'Scenario'
  const match = trimmed.match(/^(.*?)(?:\s+Revision\s+(\d+))?$/i)
  if (!match) return `${trimmed} Revision 2`
  const base = (match[1] || trimmed).trim()
  const current = match[2] ? Number(match[2]) : 1
  return `${base} Revision ${current + 1}`
}

function legacyParticipatingServices(record: { data: Record<string, any> }) {
  const scenarioData = (record.data?.scenario ?? {}) as Record<string, any>
  const additional = Array.isArray(scenarioData.additional_context) ? scenarioData.additional_context : []
  return additional
    .filter((entry: Record<string, any>) => String(entry.semantic_type ?? '') === 'participating_services')
    .flatMap((entry: Record<string, any>) =>
      String(entry.value ?? '')
        .split(/\n|,|;/)
        .map((value) => value.trim())
        .filter(Boolean),
    )
}

function participatingServiceIds(record: { data: Record<string, any> }) {
  const scenarioData = (record.data?.scenario ?? {}) as Record<string, any>
  const explicit = Array.isArray(scenarioData.participating_services) ? scenarioData.participating_services : []
  const fallback = legacyParticipatingServices(record)
  return [...new Set([...explicit, ...fallback].map((value) => String(value).trim()).filter(Boolean))]
}

function participatingServiceLabels(record: { data: Record<string, any> }) {
  const lookup = new Map(serviceOptions.value.map((service) => [service.id, service.label] as const))
  return participatingServiceIds(record).map((serviceId) => lookup.get(serviceId) ?? serviceId)
}

function schemaIssueMessages(record: { data: Record<string, any>; title?: string | null }): string[] {
  const valid = validateScenario(record.data ?? {})
  if (valid || !validateScenario.errors?.length) return []
  const title = record.title || 'Scenario'
  return validateScenario.errors.map((error) => {
    const path = error.instancePath ? ` at ${error.instancePath.replace(/^\//, '').replace(/\//g, ' / ')}` : ''
    const missing = typeof error.params?.missingProperty === 'string' ? error.params.missingProperty : ''
    if (missing) return `${title}: missing required field "${missing}"${path || ' at root'}.`
    return `${title}: ${error.message ?? 'validation error'}${path}.`
  })
}

function recordHasIssue(record: { data: Record<string, any>; title?: string | null }): boolean {
  return schemaIssueMessages(record).length > 0
}

const filteredScenarios = computed(() => {
  if (serviceFilter.value === 'all') return scenarios.value
  if (serviceFilter.value === 'unassigned') {
    return scenarios.value.filter((record) => participatingServiceIds(record).length === 0)
  }
  return scenarios.value.filter((record) => participatingServiceIds(record).includes(serviceFilter.value))
})

watch(serviceOptions, (options) => {
  if (serviceFilter.value === 'all' || serviceFilter.value === 'unassigned') return
  if (!options.some((option) => option.id === serviceFilter.value)) {
    serviceFilter.value = 'all'
  }
}, { immediate: true })

watch(readOnlyMode, (enabled) => {
  if (enabled) cancelRename()
}, { immediate: true })

async function handleCreate() {
  if (readOnlyMode.value || !projectId.value) return
  creating.value = true
  try {
    const title = scenarios.value.length === 0 ? 'Scenario 1' : `Scenario ${scenarios.value.length + 1}`
    const created = await createScenario(projectId.value, {
      id: `scn-${crypto.randomUUID()}`,
      title,
      data: {
        scenario: {
          name: slugify(title),
          category: 'safety',
          narrative: 'Describe the real business situation this design should handle.',
          context: {},
          participating_services: [],
          orchestration_steps: [],
          expected_behavior: [
            'The system should handle the intended bounded behavior without hidden manual glue.',
          ],
          expected_anip_support: [
            'The contract should make the intended bounded behavior explicit.',
          ],
        },
      },
    })
    await refreshArtifacts()
    setActiveScenario(created.id)
    router.push(`/design/projects/${projectId.value}/scenarios/${created.id}`)
  } finally {
    creating.value = false
  }
}

function openScenario(id: string) {
  setActiveScenario(id)
  router.push(`/design/projects/${projectId.value}/scenarios/${id}`)
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
    const created = await createScenario(projectId.value, {
      id: `scn-${crypto.randomUUID()}`,
      title: nextRevisionTitle(editingTitle.value.trim() || record.title || 'Scenario'),
      data: record.data,
    })
    await refreshArtifacts()
    cancelRename()
    router.push(`/design/projects/${projectId.value}/scenarios/${created.id}`)
    return
  }
  await updateScenario(projectId.value, record.id, {
    title: editingTitle.value.trim() || record.title || 'Scenario',
    status: record.status,
    data: record.data,
  })
  await refreshArtifacts()
  cancelRename()
}

async function handleDelete(record: { id: string; title?: string | null }) {
  if (readOnlyMode.value || !projectId.value) return
  const confirmed = await requestConfirmation({
    title: 'Delete this scenario?',
    message: `This will permanently remove "${record.title || 'this scenario'}" from the current project.`,
    confirmLabel: 'Delete Scenario',
    cancelLabel: 'Cancel',
    tone: 'danger',
  })
  if (!confirmed) return

  deletingId.value = record.id
  try {
    await deleteScenario(projectId.value, record.id)
    await refreshArtifacts()
    if (editingId.value === record.id) {
      cancelRename()
    }
  } finally {
    deletingId.value = null
  }
}
</script>

<template>
  <div class="scenarios-list-view">
    <div v-if="loading && !project" class="empty-state">Loading scenarios...</div>
    <div v-else-if="error" class="banner banner-error">{{ error }}</div>
    <template v-else-if="project">
      <section class="page-header">
        <div>
          <div class="page-kicker">Real Situations</div>
          <h1>{{ project.name }}</h1>
          <p>Capture the concrete business situations that should pressure the design and reveal weak assumptions.</p>
        </div>
        <button class="btn btn-primary" :disabled="readOnlyMode || creating" @click="handleCreate">
          {{ creating ? 'Creating...' : 'New Scenario' }}
        </button>
      </section>

      <ProjectIssueBanner :issue="pageIssue" title="Real Situations diagnostics" />

      <div v-if="readOnlyMode" class="banner banner-warning readonly-banner">
        {{ readOnlyReason }}
      </div>

      <section class="panel" :class="{ 'field-error-card': Boolean(pageIssue?.count) && scenarios.length === 0 }">
        <div class="panel-header">
          <div class="panel-title-row">
            <h2>Scenario List</h2>
            <span class="count-badge">{{ filteredScenarios.length }}</span>
          </div>
        </div>
        <div v-if="serviceOptions.length > 0" class="filter-bar">
          <span class="filter-label">Filter by Participating Service</span>
          <button class="filter-chip" :class="{ active: serviceFilter === 'all' }" type="button" @click="serviceFilter = 'all'">
            All
          </button>
          <button
            v-for="service in serviceOptions"
            :key="service.id"
            class="filter-chip"
            :class="{ active: serviceFilter === service.id }"
            type="button"
            @click="serviceFilter = service.id"
          >
            {{ service.label }}
          </button>
          <button class="filter-chip" :class="{ active: serviceFilter === 'unassigned' }" type="button" @click="serviceFilter = 'unassigned'">
            No Service Selected
          </button>
        </div>
        <div v-if="filteredScenarios.length === 0" class="empty-state">
          {{ scenarios.length === 0 ? 'No scenarios yet.' : 'No scenarios match the current service filter.' }}
        </div>
        <div
          v-for="record in filteredScenarios"
          :key="record.id"
          class="artifact-entry"
          :class="{ 'field-error-card': recordHasIssue(record) }"
        >
          <button class="artifact-row artifact-row-inline" @click="openScenario(record.id)">
            <span class="artifact-copy">
              <template v-if="editingId === record.id">
                <input
                  class="artifact-title-input"
                  type="text"
                  v-model="editingTitle"
                  :disabled="readOnlyMode"
                  @click.stop
                  @keydown.enter.prevent="saveRename(record)"
                />
              </template>
              <template v-else>
                <span class="artifact-title">{{ record.title || record.id }}</span>
                <span v-if="participatingServiceLabels(record).length" class="service-badge-row">
                  <span v-for="service in participatingServiceLabels(record)" :key="`${record.id}-${service}`" class="service-badge">
                    {{ service }}
                  </span>
                </span>
              </template>
            </span>
            <span class="artifact-status" :class="'status-' + record.status">{{ record.status }}</span>
          </button>
          <p
            v-for="message in schemaIssueMessages(record)"
            :key="message"
            class="inline-field-error"
          >
            {{ message }}
          </p>
          <div class="artifact-actions">
            <template v-if="editingId === record.id">
              <button class="btn btn-secondary btn-sm" :disabled="readOnlyMode" @click="saveRename(record)">Save Title</button>
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
    </template>
  </div>
</template>

<style scoped>
.scenarios-list-view {
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

.artifact-row-inline {
  flex: 1;
}

.artifact-entry {
  display: flex;
  gap: 0.75rem;
  align-items: stretch;
}

.artifact-copy {
  flex: 1;
  min-width: 0;
}

.artifact-title {
  color: var(--text-primary);
  font-weight: 600;
}

.service-badge-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-top: 0.45rem;
}

.service-badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 0.2rem 0.55rem;
  font-size: 11px;
  font-weight: 600;
  background: rgba(59, 130, 246, 0.14);
  color: #93c5fd;
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

.count-badge {
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.16);
  padding: 0.25rem 0.6rem;
  font-size: 12px;
}

.filter-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.55rem;
  margin-bottom: 1rem;
}

.filter-label {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.filter-chip {
  border: 1px solid var(--surface-border-card);
  background: var(--surface-depth-card);
  color: var(--text-secondary);
  border-radius: 999px;
  padding: 0.35rem 0.75rem;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.filter-chip.active {
  border-color: rgba(59, 130, 246, 0.4);
  background: rgba(59, 130, 246, 0.16);
  color: #bfdbfe;
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
  .scenarios-list-view {
    padding: 1.25rem;
  }

  .page-header {
    flex-direction: column;
    align-items: stretch;
  }

  .artifact-entry {
    flex-direction: column;
  }
}
</style>
<style scoped src="./product-inline-errors.css"></style>
