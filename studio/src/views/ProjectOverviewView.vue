<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  projectStore,
  loadProject,
  loadVocabulary,
  setActiveRequirements,
  setActiveProposal,
  refreshArtifacts,
} from '../design/project-store'
import {
  createProposal,
  createRequirements,
  createScenario,
  exportProject,
  importArtifacts,
} from '../design/project-api'

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
const creating = ref<'requirements' | 'scenario' | 'proposal' | null>(null)

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

function navigateScenarioValidation(id: string, event: Event) {
  event.stopPropagation()
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
      const artifacts = Array.isArray(parsed.artifacts)
        ? parsed.artifacts
        : [
            ...(Array.isArray(parsed.requirements) ? parsed.requirements.map((item: any) => ({ type: 'requirements', data: item })) : []),
            ...(Array.isArray(parsed.scenarios) ? parsed.scenarios.map((item: any) => ({ type: 'scenario', data: item })) : []),
            ...(Array.isArray(parsed.proposals) ? parsed.proposals.map((item: any) => ({ type: 'proposal', data: item })) : []),
            ...(Array.isArray(parsed.evaluations) ? parsed.evaluations.map((item: any) => ({ type: 'evaluation', data: item })) : []),
          ]
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

function slugify(input: string): string {
  return input
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

function makeRequirementsTemplate() {
  const name = project.value?.name || 'new-service'
  const domain = project.value?.domain || 'general'
  return {
    system: {
      name: slugify(name) || 'new-service',
      domain,
      deployment_intent: 'public_http_service',
    },
    transports: { http: true, stdio: false, grpc: false },
    trust: { mode: 'signed', checkpoints: false },
    auth: {
      delegation_tokens: true,
      purpose_binding: true,
      scoped_authority: true,
    },
    permissions: {
      preflight_discovery: true,
      restricted_vs_denied: true,
    },
    audit: { durable: true, searchable: true },
    lineage: {
      invocation_id: true,
      client_reference_id: true,
      task_id: true,
      parent_invocation_id: true,
    },
    risk_profile: {},
    business_constraints: {},
    scale: {
      shape_preference: 'production_single_service',
      high_availability: false,
    },
  }
}

function makeScenarioTemplate(nextIndex: number) {
  return {
    scenario: {
      name: `scenario_${nextIndex}`,
      category: 'safety',
      narrative: 'Describe the situation, constraints, and expected outcome for this scenario.',
      context: {
        capability: 'describe_the_action_under_review',
      },
      expected_behavior: ['describe_expected_system_behavior'],
      expected_anip_support: ['describe_expected_anip_support'],
    },
  }
}

function makeProposalTemplate() {
  return {
    proposal: {
      recommended_shape: 'production_single_service',
      rationale: ['Describe why this approach is appropriate for the project.'],
      required_components: ['describe_required_component'],
      optional_components: [],
      key_runtime_requirements: [],
      anti_pattern_warnings: [],
      expected_glue_reduction: {},
      declared_surfaces: {
        budget_enforcement: false,
        binding_requirements: false,
        authority_posture: false,
        recovery_class: false,
        refresh_via: false,
        verify_via: false,
        followup_via: false,
        cross_service_handoff: false,
        cross_service_continuity: false,
        cross_service_reconstruction: false,
      },
    },
  }
}

async function handleCreateRequirements() {
  if (!projectId.value) return
  creating.value = 'requirements'
  try {
    const nextIndex = requirements.value.length + 1
    const created = await createRequirements(projectId.value, {
      id: `req-${crypto.randomUUID()}`,
      title: nextIndex === 1 ? 'Requirements' : `Requirements ${nextIndex}`,
      data: makeRequirementsTemplate(),
    })
    await refreshArtifacts()
    setActiveRequirements(created.id)
    router.push(`/design/projects/${projectId.value}/requirements/${created.id}`)
  } finally {
    creating.value = null
  }
}

async function handleCreateScenario() {
  if (!projectId.value) return
  creating.value = 'scenario'
  try {
    const nextIndex = scenarios.value.length + 1
    const data = makeScenarioTemplate(nextIndex)
    const created = await createScenario(projectId.value, {
      id: `scn-${crypto.randomUUID()}`,
      title: data.scenario.name,
      data,
    })
    await refreshArtifacts()
    router.push(`/design/projects/${projectId.value}/scenarios/${created.id}`)
  } finally {
    creating.value = null
  }
}

async function handleCreateProposal() {
  if (!projectId.value) return
  const requirementsId = activeRequirementsId.value || requirements.value[0]?.id || null
  if (!requirementsId) return

  creating.value = 'proposal'
  try {
    const nextIndex = proposals.value.length + 1
    const created = await createProposal(projectId.value, {
      id: `prop-${crypto.randomUUID()}`,
      title: nextIndex === 1 ? 'Approach' : `Approach ${nextIndex}`,
      requirements_id: requirementsId,
      data: makeProposalTemplate(),
    })
    await refreshArtifacts()
    setActiveProposal(created.id)
    router.push(`/design/projects/${projectId.value}/proposals/${created.id}`)
  } finally {
    creating.value = null
  }
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
        <p class="section-desc">Select the requirements set and approach for evaluation.</p>
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
            <label class="field-label">Approach</label>
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

      <section class="creation-section">
        <h2 class="section-title">Create Artifacts</h2>
        <p class="section-desc">Build the project directly in Studio instead of relying on import or seed data.</p>
        <div class="creation-actions">
          <button class="btn btn-primary" @click="handleCreateRequirements" :disabled="creating !== null">
            {{ creating === 'requirements' ? 'Creating requirements...' : 'New Requirements' }}
          </button>
          <button class="btn btn-primary" @click="handleCreateScenario" :disabled="creating !== null">
            {{ creating === 'scenario' ? 'Creating scenario...' : 'New Scenario' }}
          </button>
          <button
            class="btn btn-primary"
            @click="handleCreateProposal"
            :disabled="creating !== null || requirements.length === 0"
            :title="requirements.length === 0 ? 'Create a requirements set first' : ''"
          >
            {{ creating === 'proposal' ? 'Creating approach...' : 'New Approach' }}
          </button>
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
          <button
            class="artifact-action"
            :disabled="!activeRequirementsId || !activeProposalId"
            :title="!activeRequirementsId || !activeProposalId ? 'Select requirements and approach first' : 'Run validation for this scenario'"
            @click="navigateScenarioValidation(s.id, $event)"
          >
            Validate
          </button>
          <span class="artifact-date">{{ formatDate(s.updated_at) }}</span>
        </div>
      </section>

      <section class="artifact-section">
        <h2 class="section-title">Approaches ({{ proposals.length }})</h2>
        <div v-if="proposals.length === 0" class="empty-row">No approaches yet.</div>
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

.creation-section {
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

.creation-actions {
  display: flex;
  gap: 8px;
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

.btn-primary {
  background: var(--accent);
  color: #fff;
}

.btn-primary:hover:not(:disabled) {
  background: var(--accent-hover);
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

.artifact-action {
  height: 28px;
  padding: 0 10px;
  border: 1px solid rgba(59, 130, 246, 0.35);
  border-radius: var(--radius-sm);
  background: rgba(59, 130, 246, 0.08);
  color: #3b82f6;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: background var(--transition);
}

.artifact-action:hover:not(:disabled) {
  background: rgba(59, 130, 246, 0.16);
}

.artifact-action:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
</style>
