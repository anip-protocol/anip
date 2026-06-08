<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  findDeveloperDefinitionArtifact,
  resolveCompiledContractAlignment,
  resolveEvaluationCompiledContractIdentity,
} from '../design/developer-definition'
import { firstProductDesignGateMessage, productDesignGate } from '../design/project-workflow'
import { loadProject, projectStore } from '../design/project-store'
import { formatStudioTimestamp } from '../design/time'

const route = useRoute()
const router = useRouter()

const projectId = computed(() => route.params.projectId as string)
const project = computed(() => projectStore.activeProject)
const workspace = computed(() => projectStore.activeWorkspace)
const loading = computed(() => projectStore.loading)
const error = computed(() => projectStore.error)
const runtimeStatus = computed(() => projectStore.runtimeStatus)
const readOnlyMode = computed(() => !!runtimeStatus.value?.read_only_mode)
const assistantReady = computed(() =>
  !readOnlyMode.value
  && !!runtimeStatus.value?.studio_api_reachable
  && !!runtimeStatus.value?.llm_ready
  && !!runtimeStatus.value?.api_key_configured,
)
const latestEvaluation = computed(() => {
  const evaluations = [...projectStore.artifacts.evaluations]
  evaluations.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
  return evaluations[0] ?? null
})
const developerDefinitionArtifact = computed(() => findDeveloperDefinitionArtifact(projectStore.artifacts.pmArtifacts))
const compiledContractIdentity = computed(() =>
  ((developerDefinitionArtifact.value?.data as { compiled_contract_identity?: Record<string, string | null> } | undefined)?.compiled_contract_identity) ?? null,
)
const latestEvaluationContractIdentity = computed(() =>
  resolveEvaluationCompiledContractIdentity(latestEvaluation.value as any),
)
const contractAlignment = computed(() =>
  resolveCompiledContractAlignment(compiledContractIdentity.value as any, latestEvaluationContractIdentity.value as any),
)
const dashboardMode = computed<'overview' | 'product' | 'developer'>(() => {
  if (route.query.view === 'product') return 'product'
  if (route.query.view === 'developer') return 'developer'
  return 'overview'
})
const isGovernedFrontingProject = computed(() => project.value?.project_type === 'governed_service_project')
const sourceDocumentCount = computed(() =>
  project.value?.documents_count ?? projectStore.artifacts.documents.length,
)
const productGate = computed(() =>
  productDesignGate({
    project: project.value,
    pmArtifacts: projectStore.artifacts.pmArtifacts,
    requirements: projectStore.artifacts.requirements,
    scenarios: projectStore.artifacts.scenarios,
    documents: projectStore.artifacts.documents,
    shapes: projectStore.artifacts.shapes,
  }),
)

async function ensureLoaded() {
  if (!projectId.value) return
  if (projectStore.activeProject?.id === projectId.value && projectStore.artifacts.documents.length > 0) return
  await loadProject(projectId.value)
}

onMounted(ensureLoaded)
watch(projectId, ensureLoaded)

function openPath(path: string) {
  router.push(path)
}

function openDeveloperPath(path: string) {
  if (!productGate.value.ready && project.value) {
    router.push(`/design/projects/${project.value.id}/pm`)
    return
  }
  router.push(path)
}

const runtimePanelTitle = computed(() => readOnlyMode.value ? 'Hosted Showcase Mode' : 'Runtime Readiness')
const runtimePanelLabel = computed(() => {
  if (readOnlyMode.value) return 'Browse-only'
  return runtimeStatus.value?.llm_ready ? 'Ready' : 'Needs attention'
})
const runtimePanelReady = computed(() =>
  readOnlyMode.value ? !!runtimeStatus.value?.studio_api_reachable : !!runtimeStatus.value?.llm_ready,
)
const readinessItems = computed(() => {
  if (readOnlyMode.value) {
    return [
      {
        label: 'Studio API',
        value: runtimeStatus.value?.studio_api_reachable ? 'reachable' : 'unavailable',
        ready: !!runtimeStatus.value?.studio_api_reachable,
      },
      {
        label: 'Mutation guard',
        value: 'enabled',
        ready: true,
      },
      {
        label: 'Assistant authoring',
        value: 'disabled for public preview',
        ready: true,
      },
      {
        label: 'Project data',
        value: sourceDocumentCount.value > 0 ? 'seeded showcase' : 'not seeded',
        ready: sourceDocumentCount.value > 0,
      },
    ]
  }

  return [
    {
      label: 'Studio API',
      value: runtimeStatus.value?.studio_api_reachable ? 'reachable' : 'unavailable',
      ready: !!runtimeStatus.value?.studio_api_reachable,
    },
    {
      label: 'Assistant provider',
      value: runtimeStatus.value?.assistant_provider || 'unknown',
      ready: !!runtimeStatus.value?.assistant_provider,
    },
    {
      label: 'Model',
      value: runtimeStatus.value?.assistant_model || 'not configured',
      ready: !!runtimeStatus.value?.assistant_model,
    },
    {
      label: 'LLM key',
      value: runtimeStatus.value?.api_key_configured ? 'configured' : 'missing',
      ready: !!runtimeStatus.value?.api_key_configured,
    },
  ]
})
const latestEvidenceLabel = computed(() => {
  if (!latestEvaluation.value) return 'None yet'
  if (contractAlignment.value.status === 'unknown' && readOnlyMode.value) return 'Captured'
  return contractAlignment.value.label
})
const latestEvidenceReady = computed(() =>
  contractAlignment.value.status === 'aligned'
  || (!!latestEvaluation.value && readOnlyMode.value),
)
const latestEvidenceDetail = computed(() => {
  if (contractAlignment.value.status === 'unknown' && latestEvaluation.value && readOnlyMode.value) {
    return 'This hosted showcase includes seeded evaluation evidence. Full saved-revision signatures appear after an authoring workspace publishes a package revision.'
  }
  return contractAlignment.value.detail
})
</script>

<template>
  <div class="project-dashboard">
    <div v-if="loading && !project" class="empty-state">Loading project...</div>
    <div v-else-if="error" class="banner banner-error">{{ error }}</div>
    <template v-else-if="project">
      <section class="hero">
        <div class="hero-copy">
          <div class="hero-kicker">{{ workspace?.name || 'Workspace' }}</div>
          <h1 class="hero-title">{{ project.name }}</h1>
          <p class="hero-summary">{{ project.summary || 'No project summary yet.' }}</p>
        </div>
        <div class="hero-actions">
          <button
            class="btn"
            :class="dashboardMode === 'product' ? 'btn-primary' : 'btn-secondary'"
            @click="openPath(`/design/projects/${project.id}/pm`)"
          >
            Product Design
          </button>
          <button
            class="btn"
            :class="dashboardMode === 'developer' ? 'btn-primary' : 'btn-secondary'"
            :disabled="!productGate.ready"
            :title="!productGate.ready ? firstProductDesignGateMessage(productGate) : 'Open Developer Design'"
            @click="openDeveloperPath(`/design/projects/${project.id}/developer`)"
          >
            Developer Design
          </button>
          <button class="btn btn-secondary" @click="openPath(`/design/projects/${project.id}/verification`)">
            Verification
          </button>
        </div>
      </section>

      <section class="dashboard-grid">
        <article class="panel panel-wide">
          <div class="panel-header">
            <h2>Project Overview</h2>
            <span class="status-chip" :class="{ ready: !!latestEvaluation }">
              {{ latestEvaluation ? 'Observed' : 'In progress' }}
            </span>
          </div>
          <p class="panel-copy">
            This dashboard is the handoff point between product intent and developer implementation. Pick the lane you want to work in, then use Verification to confirm that the implementation still matches the design.
          </p>
          <div class="artifact-grid">
            <div class="metric-card">
              <div class="metric-label">Source Docs</div>
              <div class="metric-value">{{ sourceDocumentCount }}</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">Requirements</div>
              <div class="metric-value">{{ project.requirements_count }}</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">Scenarios</div>
              <div class="metric-value">{{ project.scenarios_count }}</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">Service Design</div>
              <div class="metric-value">{{ project.shapes_count }}</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">Observed Services</div>
              <div class="metric-value">{{ projectStore.artifacts.serviceMetadata.length }}</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">Evaluations</div>
              <div class="metric-value">{{ project.evaluations_count }}</div>
            </div>
          </div>
        </article>

        <article class="panel">
          <div class="panel-header">
            <h2>{{ runtimePanelTitle }}</h2>
            <span class="status-chip" :class="{ ready: runtimePanelReady }">
              {{ runtimePanelLabel }}
            </span>
          </div>
          <div class="status-list">
            <div v-for="item in readinessItems" :key="item.label" class="status-row">
              <div class="status-row-label">
                <span class="status-dot" :class="{ ready: item.ready }"></span>
                {{ item.label }}
              </div>
              <div class="status-row-value">{{ item.value }}</div>
            </div>
          </div>
        </article>

        <article class="panel panel-full">
          <div class="panel-header">
            <h2>Choose How To Work</h2>
            <span class="status-chip" :class="{ ready: assistantReady }">
              {{ assistantReady ? 'Assistant available' : readOnlyMode ? 'Browse-only preview' : 'Manual mode default' }}
            </span>
          </div>
          <p class="panel-copy">
            Studio always saves deterministic project artifacts. The mode only changes how much of the workflow Studio drives for you.
          </p>
          <div class="work-mode-grid">
            <button class="work-mode-card" @click="openPath(`/design/projects/${project.id}/pm`)">
              <span class="work-mode-eyebrow">Default without LLM</span>
              <span class="work-mode-title">Manual / Deterministic</span>
              <span class="work-mode-copy">PMs and developers edit the canonical pages directly. Studio validates, highlights gaps, and blocks unsafe generation.</span>
              <span class="work-mode-action">Open Product Design</span>
            </button>
            <button
              class="work-mode-card"
              :class="{ disabled: !assistantReady }"
              :disabled="!assistantReady"
              @click="openPath(`/design/projects/${project.id}/pm/assistant?mode=guided`)"
            >
              <span class="work-mode-eyebrow">Controlled assistant path</span>
              <span class="work-mode-title">Guided Mode</span>
              <span class="work-mode-copy">Use Guided Mode when you want control over each section. The assistant drafts, asks targeted questions, and waits for reviewed saves.</span>
              <span class="work-mode-action">{{ assistantReady ? 'Open Guided Assistant' : readOnlyMode ? 'Disabled in hosted preview' : 'Configure LLM to enable' }}</span>
            </button>
            <button
              class="work-mode-card work-mode-card-primary"
              :class="{ disabled: !assistantReady }"
              :disabled="!assistantReady"
              @click="openPath(`/design/projects/${project.id}/assistant?mode=autopilot`)"
            >
              <span class="work-mode-eyebrow">Lowest complexity path</span>
              <span class="work-mode-title">Autopilot Mode</span>
              <span class="work-mode-copy">Use Autopilot Mode when you want ANIP Studio to complete the project draft for you, stopping only for decisions that become contract truth.</span>
              <span class="work-mode-action">{{ assistantReady ? 'Start Autopilot Mode' : readOnlyMode ? 'Disabled in hosted preview' : 'Configure LLM to enable' }}</span>
            </button>
          </div>
        </article>

        <article class="panel">
          <div class="panel-header">
            <h2>Latest Evidence</h2>
            <span class="status-chip" :class="{ ready: latestEvidenceReady }">
              {{ latestEvidenceLabel }}
            </span>
          </div>
          <template v-if="latestEvaluation">
            <div class="detail-list">
              <div class="detail-row">
                <span class="detail-label">Created</span>
                <span>{{ formatStudioTimestamp(latestEvaluation.created_at) }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">Scenario</span>
                <span>{{ latestEvaluation.scenario_id }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">Source</span>
                <span>{{ latestEvaluation.source }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">{{ readOnlyMode && contractAlignment.status === 'unknown' ? 'Evidence status' : 'Contract status' }}</span>
                <span>{{ readOnlyMode && contractAlignment.status === 'unknown' ? 'Captured showcase evidence' : contractAlignment.label }}</span>
              </div>
              <div v-if="compiledContractIdentity?.signature || !readOnlyMode" class="detail-row">
                <span class="detail-label">Current contract</span>
                <span class="wrap-value">{{ compiledContractIdentity?.signature || 'Not saved' }}</span>
              </div>
              <div v-if="latestEvaluationContractIdentity?.signature || !readOnlyMode" class="detail-row">
                <span class="detail-label">Evaluated contract</span>
                <span class="wrap-value">{{ latestEvaluationContractIdentity?.signature || 'Not recorded' }}</span>
              </div>
            </div>
            <p class="panel-copy contract-copy">{{ latestEvidenceDetail }}</p>
            <button
              class="btn btn-secondary btn-full"
              @click="openPath(`/design/projects/${project.id}/verification`)"
            >
              Open Verification
            </button>
          </template>
          <p v-else class="panel-copy">No evaluation has been captured for this project yet.</p>
        </article>

        <article class="panel panel-full">
          <div class="panel-header">
            <h2>Choose a Design Lane</h2>
          </div>
          <div v-if="!productGate.ready" class="banner banner-warning lane-gate">
            <strong>Developer Design is gated by Product Design.</strong>
            <span>{{ firstProductDesignGateMessage(productGate) }}</span>
          </div>
          <div class="lane-grid">
            <button class="lane-card lane-card-primary" @click="openPath(`/design/projects/${project.id}/pm`)">
              <span class="lane-title">Product Design</span>
              <span class="lane-copy">
                {{ isGovernedFrontingProject
                  ? 'Capture the business intent, actors, permission posture, requirements, and scenarios for the governed ANIP fronting layer.'
                  : 'Work from business specs into business summary, actor model, permission intent, requirements, scenarios, and service design.' }}
              </span>
              <span class="lane-meta">
                {{ isGovernedFrontingProject
                  ? 'Source Docs, Product Overview, Business Summary, Actor Model, Permission Intent, What Matters, Real Situations, PM Review'
                  : 'Source Docs, Product Overview, Business Summary, Actor Model, Permission Intent, What Matters, Real Situations, Service Design' }}
              </span>
            </button>
            <button
              class="lane-card"
              :class="{ disabled: !productGate.ready }"
              :disabled="!productGate.ready"
              :title="!productGate.ready ? firstProductDesignGateMessage(productGate) : 'Open Developer Design'"
              @click="openDeveloperPath(`/design/projects/${project.id}/developer`)"
            >
              <span class="lane-title">{{ isGovernedFrontingProject ? 'Govern API / MCP' : 'Developer Design' }}</span>
              <span class="lane-copy">
                {{ isGovernedFrontingProject
                  ? 'Turn existing tools, endpoints, or MCP operations into governed ANIP capabilities, policy, generation settings, evidence, and the final ANIP definition.'
                  : 'Formalize the approved product intent into service, capability, data, scenario, generation, and verification contract surfaces.' }}
              </span>
              <span class="lane-meta">
                {{ isGovernedFrontingProject
                  ? 'Developer Overview, Locked Product Handoff, Govern API / MCP, Generation Settings, Consistency Gaps, Developer Definition'
                  : 'Developer Overview, Locked Product Handoff, Service Formalization, Capability Formalization, Roles & Access, Audit & Lineage, Scenario Coverage Intent' }}
              </span>
            </button>
          </div>
        </article>

        <article class="panel panel-full">
          <div class="panel-header">
            <h2>Next Recommended Actions</h2>
          </div>
          <div class="action-grid">
            <button class="action-card" @click="openPath(`/design/projects/${project.id}/source-docs`)">
              <span class="action-title">{{ readOnlyMode || sourceDocumentCount > 0 ? 'Review source documents' : 'Attach source documents' }}</span>
              <span class="action-copy">
                {{ readOnlyMode
                  ? 'Browse the seeded source documents that ground this showcase project.'
                  : isGovernedFrontingProject
                  ? 'Upload fronting intent, integration contracts, API/MCP docs, permission matrices, and policy evidence.'
                  : 'Upload the canonical business specs and supporting references.' }}
              </span>
            </button>
            <button class="action-card" @click="openPath(`/design/projects/${project.id}/pm`)">
              <span class="action-title">{{ readOnlyMode ? 'Review product design' : 'Continue product design' }}</span>
              <span class="action-copy">
                {{ isGovernedFrontingProject
                  ? 'Review fronting intent, actor expectations, permission posture, requirements, and scenarios before developer mapping.'
                  : 'Review business framing, actor expectations, requirements, scenarios, and service design choices.' }}
              </span>
            </button>
            <button
              class="action-card"
              :class="{ disabled: !productGate.ready }"
              :disabled="!productGate.ready"
              :title="!productGate.ready ? firstProductDesignGateMessage(productGate) : 'Continue Developer Design'"
              @click="openDeveloperPath(isGovernedFrontingProject ? `/design/projects/${project.id}/fronting` : `/design/projects/${project.id}/developer`)"
            >
              <span class="action-title">{{ readOnlyMode ? (isGovernedFrontingProject ? 'Review governed API / MCP' : 'Review developer design') : (isGovernedFrontingProject ? 'Continue Govern API / MCP' : 'Continue developer design') }}</span>
              <span class="action-copy">
                {{ isGovernedFrontingProject
                  ? 'Use Express Mode to connect backend supply, curate governed capabilities, and keep advanced Studio pages available.'
                  : 'Bind the approved project intent to governed backends and generation templates.' }}
              </span>
            </button>
            <button
              v-if="project.project_type === 'governed_service_project'"
              class="action-card"
              :class="{ disabled: !productGate.ready }"
              :disabled="!productGate.ready"
              :title="!productGate.ready ? firstProductDesignGateMessage(productGate) : 'Open advanced fronting setup'"
              @click="openDeveloperPath(`/design/projects/${project.id}/developer/integration-fronting`)"
            >
              <span class="action-title">Advanced fronting setup</span>
              <span class="action-copy">Open the full editor for connection refs, raw backend operations, and detailed capability mappings.</span>
            </button>
            <button class="action-card" @click="openPath(`/design/projects/${project.id}/templates/export`)">
              <span class="action-title">{{ readOnlyMode ? 'Review template export flow' : 'Create starter template' }}</span>
              <span class="action-copy">{{ readOnlyMode ? 'Inspect the selection-based template export workflow. Saving/exporting is disabled in hosted preview.' : 'Export selected project material as a reusable template package. Source docs are opt-in to avoid leaking sensitive content.' }}</span>
            </button>
            <button class="action-card" @click="openPath(`/design/projects/${project.id}/verification`)">
              <span class="action-title">Verify implementation</span>
              <span class="action-copy">Inspect test context, observed services, and evaluation readiness.</span>
            </button>
          </div>
        </article>

      </section>
    </template>
  </div>
</template>

<style scoped>
.project-dashboard {
  width: 100%;
  max-width: none;
  padding: 2rem;
}

.hero {
  display: flex;
  justify-content: space-between;
  gap: 1.5rem;
  align-items: flex-start;
  margin-bottom: 1.75rem;
}

.hero-copy {
  flex: 1;
  min-width: 0;
}

.hero-kicker {
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-secondary);
  margin-bottom: 0.5rem;
}

.hero-title {
  margin: 0 0 0.5rem;
  font-size: 30px;
  line-height: 1.1;
  color: var(--text-primary);
}

.hero-summary {
  margin: 0;
  max-width: 72ch;
  color: var(--text-secondary);
  line-height: 1.6;
}

.hero-actions {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 1rem;
}

.panel {
  grid-column: span 4;
  background: var(--surface-depth-panel);
  border: 1px solid var(--surface-border-panel);
  border-radius: 18px;
  padding: 1.25rem;
}

.panel-wide {
  grid-column: span 8;
}

.panel-full {
  grid-column: 1 / -1;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: center;
  margin-bottom: 0.9rem;
}

.panel-header h2 {
  margin: 0;
  font-size: 16px;
  color: var(--text-primary);
}

.panel-copy {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.6;
}

.artifact-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.9rem;
  margin-top: 1rem;
}

.metric-card {
  padding: 0.9rem 1rem;
  border-radius: 14px;
  background: var(--surface-depth-card);
  border: 1px solid var(--surface-border-card);
}

.metric-label {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-secondary);
  margin-bottom: 0.35rem;
}

.metric-value {
  font-size: 28px;
  line-height: 1;
  color: var(--text-primary);
}

.status-list,
.detail-list {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.contract-copy {
  margin-top: 1rem;
}

.status-row,
.detail-row {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: center;
}

.status-row-label,
.detail-label {
  color: var(--text-secondary);
}

.status-row-value {
  color: var(--text-primary);
  text-align: right;
}

.assistant-actions {
  display: flex;
  justify-content: flex-start;
  margin-top: 1rem;
}

.assistant-entry-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 1rem;
  margin-top: 1rem;
}

.assistant-guidance-copy {
  margin-top: 1rem;
}

.assistant-banner {
  margin-top: 1rem;
}

.assistant-next-step {
  margin-top: 1rem;
  display: grid;
  gap: 0.9rem;
}

.assistant-list {
  display: grid;
  gap: 0.4rem;
}

.assistant-list ul,
.assistant-list ol {
  margin: 0;
  padding-left: 1.25rem;
  color: var(--text-secondary);
}

.work-mode-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1rem;
  margin-top: 1rem;
}

.work-mode-card {
  display: grid;
  gap: 0.7rem;
  min-height: 210px;
  padding: 1.15rem;
  text-align: left;
  border: 1px solid var(--surface-border-card);
  border-radius: 18px;
  background:
    linear-gradient(180deg, rgba(15, 23, 42, 0.72), rgba(15, 23, 42, 0.48));
  color: inherit;
  cursor: pointer;
  transition: border-color 140ms ease, background 140ms ease, transform 140ms ease;
}

.work-mode-card:hover:not(:disabled) {
  border-color: rgba(96, 165, 250, 0.42);
  background:
    linear-gradient(180deg, rgba(30, 64, 175, 0.24), rgba(15, 23, 42, 0.56));
  transform: translateY(-1px);
}

.work-mode-card-primary {
  border-color: rgba(56, 189, 248, 0.38);
  background:
    radial-gradient(circle at top left, rgba(56, 189, 248, 0.18), transparent 42%),
    linear-gradient(180deg, rgba(15, 23, 42, 0.72), rgba(15, 23, 42, 0.5));
}

.work-mode-card.disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.work-mode-eyebrow {
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.work-mode-title {
  color: var(--text-primary);
  font-size: 20px;
  font-weight: 900;
}

.work-mode-copy {
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.55;
}

.work-mode-action {
  align-self: end;
  width: fit-content;
  margin-top: auto;
  border: 1px solid rgba(96, 165, 250, 0.28);
  border-radius: 999px;
  padding: 0.42rem 0.72rem;
  color: #bfdbfe;
  font-size: 12px;
  font-weight: 900;
}

.wrap-value {
  word-break: break-all;
  text-align: right;
}

.status-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 999px;
  margin-right: 0.45rem;
  background: rgba(248, 113, 113, 0.9);
}

.status-dot.ready,
.status-chip.ready {
  background: rgba(34, 197, 94, 0.16);
}

.status-chip {
  padding: 0.28rem 0.6rem;
  border-radius: 999px;
  font-size: 12px;
  background: rgba(148, 163, 184, 0.16);
  color: var(--text-secondary);
}

.btn {
  border: 1px solid var(--surface-border-card);
  border-radius: 12px;
  padding: 0.75rem 1rem;
  font-size: 14px;
  cursor: pointer;
}

.btn:disabled,
.lane-card:disabled,
.action-card:disabled {
  cursor: not-allowed;
  opacity: 0.58;
  transform: none;
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

.btn-full {
  width: 100%;
  margin-top: 1rem;
}

.action-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.9rem;
}

.lane-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.9rem;
}

.lane-card {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 1.1rem;
  text-align: left;
  border-radius: 14px;
  border: 1px solid var(--surface-border-card);
  background: var(--surface-depth-card);
  color: inherit;
  cursor: pointer;
  transition: border-color 140ms ease, background 140ms ease, transform 140ms ease;
}

.lane-card:hover:not(:disabled) {
  border-color: rgba(96, 165, 250, 0.42);
  background: rgba(15, 23, 42, 0.6);
  transform: translateY(-1px);
}

.lane-card-primary {
  border-color: rgba(96, 165, 250, 0.34);
  background: rgba(37, 99, 235, 0.12);
}

.lane-title {
  font-size: 17px;
  color: var(--text-primary);
}

.lane-copy {
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-secondary);
}

.lane-meta {
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-muted);
}

.action-card {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  text-align: left;
  padding: 1rem;
  border-radius: 14px;
  border: 1px solid var(--surface-border-card);
  background: var(--surface-depth-card);
  color: inherit;
  cursor: pointer;
}

.action-title {
  font-size: 15px;
  color: var(--text-primary);
}

.action-copy {
  font-size: 13px;
  line-height: 1.5;
  color: var(--text-secondary);
}

.banner {
  padding: 0.8rem 1rem;
  border-radius: 12px;
}

.banner-error {
  background: rgba(248, 113, 113, 0.12);
  border: 1px solid rgba(248, 113, 113, 0.28);
  color: var(--error);
}

.banner-warning {
  display: grid;
  gap: 0.25rem;
  margin-bottom: 1rem;
  background: rgba(251, 191, 36, 0.1);
  border: 1px solid rgba(251, 191, 36, 0.28);
  color: var(--text-primary);
}

.banner-warning span {
  color: var(--text-secondary);
}

.empty-state {
  color: var(--text-secondary);
}

@media (max-width: 1100px) {
  .panel,
  .panel-wide {
    grid-column: span 12;
  }

  .artifact-grid,
  .work-mode-grid,
  .lane-grid,
  .action-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .project-dashboard {
    padding: 1.25rem;
  }

  .hero {
    flex-direction: column;
  }

  .artifact-grid,
  .work-mode-grid,
  .lane-grid,
  .action-grid {
    grid-template-columns: 1fr;
  }
}
</style>
