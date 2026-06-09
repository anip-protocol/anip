<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ACTOR_MODEL_ARTIFACT_TYPE,
  BUSINESS_AREAS_ARTIFACT_TYPE,
  PERMISSION_INTENT_ARTIFACT_TYPE,
  PRODUCT_SUMMARY_ARTIFACT_TYPE,
  buildProductDesignStatusCards,
  buildProductDesignSufficiencyCards,
} from '../design/product-design'
import { loadProject, projectStore } from '../design/project-store'
import type { DesignSectionSufficiencyCard, DeveloperBaselineData } from '../design/project-types'
import { formatStudioTimestamp } from '../design/time'
import { DESIGN_TRACEABILITY_ARTIFACT_TYPE, developerBaselineMatchesCurrentContext, findDeveloperBaselineArtifact, findTraceabilityArtifact, pmReviewStatusLabel } from '../design/traceability'
import { buildProjectIssueIndex } from '../design/project-issues'
import { showTechnicalIdentifiers } from '../design/technical-display'

const route = useRoute()
const router = useRouter()

const projectId = computed(() => route.params.projectId as string)
const project = computed(() => projectStore.activeProject)
const requirements = computed(() => projectStore.artifacts.requirements)
const scenarios = computed(() => projectStore.artifacts.scenarios)
const shapes = computed(() => projectStore.artifacts.shapes)
const evaluations = computed(() => projectStore.artifacts.evaluations)
const documents = computed(() => projectStore.artifacts.documents)
const loading = computed(() => projectStore.loading)
const error = computed(() => projectStore.error)
const isGovernedFrontingProject = computed(() => project.value?.project_type === 'governed_service_project')
const governedFrontingProductArtifactKeys = new Set([
  PRODUCT_SUMMARY_ARTIFACT_TYPE,
  ACTOR_MODEL_ARTIFACT_TYPE,
  BUSINESS_AREAS_ARTIFACT_TYPE,
  PERMISSION_INTENT_ARTIFACT_TYPE,
])

async function ensureLoaded() {
  if (!projectId.value) return
  if (projectStore.activeProject?.id === projectId.value) return
  await loadProject(projectId.value)
}

onMounted(ensureLoaded)
watch(projectId, ensureLoaded)

const activeRequirements = computed(() =>
  requirements.value.find((item) => item.id === projectStore.activeRequirementsId)
  ?? requirements.value.find((item) => item.role === 'primary')
  ?? requirements.value[0]
  ?? null,
)

const activeScenario = computed(() =>
  scenarios.value.find((item) => item.id === projectStore.activeScenarioId)
  ?? scenarios.value[0]
  ?? null,
)
const activeShape = computed(() =>
  shapes.value.find((item) => item.id === projectStore.activeShapeId)
  ?? shapes.value[0]
  ?? null,
)

const latestEvaluation = computed(() => {
  const records = [...evaluations.value]
  records.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
  return records[0] ?? null
})
const productStatusCards = computed(() =>
  project.value
    ? buildProductDesignStatusCards(project.value.id, projectStore.artifacts.pmArtifacts)
      .filter((card) => !isGovernedFrontingProject.value || governedFrontingProductArtifactKeys.has(card.key))
    : [],
)
const productSufficiencyCards = computed<DesignSectionSufficiencyCard[]>(() =>
  project.value
    ? buildProductDesignSufficiencyCards(project.value.id, projectStore.artifacts.pmArtifacts, {
        documents_count: documents.value.length,
        requirements_count: requirements.value.length,
        scenarios_count: scenarios.value.length,
      }).filter((card) => !isGovernedFrontingProject.value || governedFrontingProductArtifactKeys.has(card.key))
    : [],
)
const productReadyCount = computed(() => productStatusCards.value.filter((card) => card.complete).length)
const clarificationCandidates = computed(() =>
  productSufficiencyCards.value.filter((card) => card.status === 'needs_clarification'),
)
const nextPmStep = computed(() =>
  productSufficiencyCards.value.find((card) => card.status === 'needs_clarification')
  ?? productSufficiencyCards.value.find((card) => card.status === 'blocked')
  ?? productSufficiencyCards.value.find((card) => card.status === 'draftable')
  ?? null,
)
const productIssueIndex = computed(() => buildProjectIssueIndex({
  project: project.value,
  pmArtifacts: projectStore.artifacts.pmArtifacts,
  requirements: requirements.value,
  scenarios: scenarios.value,
  documents: documents.value,
  shapes: shapes.value,
}))
const productOverviewIssues = computed(() =>
  productIssueIndex.value['project-product-design']?.messages ?? [],
)

function sufficiencyStatusLabel(status: DesignSectionSufficiencyCard['status']) {
  switch (status) {
    case 'ready':
      return 'Ready'
    case 'draftable':
      return 'Draftable from source'
    case 'needs_clarification':
      return 'Needs clarification'
    default:
      return 'Blocked'
  }
}

const traceabilityArtifact = computed(() => findTraceabilityArtifact(projectStore.artifacts.pmArtifacts))
const baselineArtifact = computed(() => findDeveloperBaselineArtifact(projectStore.artifacts.pmArtifacts))
const baseline = computed(() =>
  (baselineArtifact.value?.data as DeveloperBaselineData | undefined) ?? null,
)
const baselineAligned = computed(() =>
  developerBaselineMatchesCurrentContext({
    baseline: baseline.value,
    requirements: activeRequirements.value,
    scenarios: scenarios.value,
    shape: activeShape.value,
    pmArtifacts: projectStore.artifacts.pmArtifacts,
  }),
)
const lockedRequirementsTitle = computed(() =>
  baseline.value
    ? (requirements.value.find((item) => item.id === baseline.value?.source_inputs.requirements_id)?.title || 'Missing')
    : 'Missing',
)
const lockedShapeTitle = computed(() =>
  baseline.value
    ? (shapes.value.find((item) => item.id === baseline.value?.source_inputs.shape_id)?.title || 'Missing')
    : 'Missing',
)
const frozenPmArtifacts = computed(() =>
  projectStore.artifacts.pmArtifacts.filter((artifact) =>
    artifact.data?.artifact_type !== DESIGN_TRACEABILITY_ARTIFACT_TYPE,
  ),
)

function open(path: string) {
  router.push(path)
}
</script>

<template>
  <div class="project-pm-home">
    <div v-if="loading && !project" class="empty-state">Loading PM view...</div>
    <div v-else-if="error" class="banner banner-error">{{ error }}</div>
    <template v-else-if="project">
      <section class="page-header">
        <div class="page-kicker">Product Design</div>
        <h1>{{ project.name }}</h1>
        <p>
          Product Overview is the PM-facing home for this project. Use it to shape business intent, actor expectations,
          permission posture, requirements, scenarios, service design, and signoff without dragging PMs into technical
          contract language.
        </p>
      </section>

      <section class="grid">
        <article v-if="baseline" class="panel panel-wide">
          <div class="panel-header">
            <h2>Development Lock</h2>
          </div>
          <div class="summary-stack">
            <div class="summary-row">
              <span class="summary-label">Locked revision</span>
              <strong>{{ formatStudioTimestamp(baseline.locked_at) }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Developer status</span>
              <strong>{{ baselineAligned ? 'Current draft matches locked baseline' : 'Current draft is a newer revision' }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Locked requirements</span>
              <strong>{{ lockedRequirementsTitle }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Locked service design</span>
              <strong>{{ lockedShapeTitle }}</strong>
            </div>
          </div>
          <p class="panel-copy">
            Product Design is locked for development. Editing the locked artifacts should create new working revisions rather than modifying the implemented baseline in place.
          </p>
        </article>

        <article class="panel">
          <div class="panel-header">
            <h2>Current Translation</h2>
          </div>
          <div class="summary-stack">
            <div class="summary-row">
              <span class="summary-label">Active What Matters</span>
              <strong>{{ activeRequirements?.title || 'Not selected yet' }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Active Real Situation</span>
              <strong>{{ activeScenario?.title || 'Not selected yet' }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Latest evaluation</span>
              <strong>{{ latestEvaluation?.result || 'None yet' }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">PM review</span>
              <strong>{{ traceabilityArtifact ? pmReviewStatusLabel((traceabilityArtifact.data?.pm_review_status || 'pending') as any) : 'Not started' }}</strong>
            </div>
          </div>
        </article>

        <article class="panel">
          <div class="panel-header">
            <h2>Display Settings</h2>
          </div>
          <label class="display-toggle">
            <input v-model="showTechnicalIdentifiers" type="checkbox" />
            <span>
              <strong>Show canonical values</strong>
              <small>Keep this off for a cleaner design view. Hover over mapped labels when you need the stored contract value.</small>
            </span>
          </label>
        </article>

        <article class="panel panel-full">
          <div class="panel-header">
            <h2>Business Design Sufficiency</h2>
            <span class="status-chip" :class="{ ready: productReadyCount === productStatusCards.length && productStatusCards.length > 0 }">
              {{ productReadyCount }} / {{ productStatusCards.length }} ready
            </span>
          </div>
          <p class="panel-copy">
            <template v-if="isGovernedFrontingProject">
              For Govern API / MCP projects, Product Design stays focused on intent, actors, and permission posture. Backend shape and capability mapping happen in Developer Design.
            </template>
            <template v-else>
              Studio should draft from the business spec where it has enough signal and only ask for targeted clarifications where the source is ambiguous or incomplete.
            </template>
          </p>
          <div class="action-grid">
            <button
              v-for="card in productSufficiencyCards"
              :key="card.key"
              class="action-card"
              @click="open(card.path)"
            >
              <span class="action-title">{{ card.title }}</span>
              <span class="action-copy">{{ card.detail }}</span>
              <span class="status-chip" :class="`status-${card.status}`">
                {{ sufficiencyStatusLabel(card.status) }}
              </span>
              <span v-if="card.questions.length" class="action-questions">
                {{ card.questions[0] }}
              </span>
            </button>
          </div>
        </article>

        <article class="panel panel-full">
          <div class="panel-header">
            <h2>Design Translation Status</h2>
          </div>
          <div class="metric-grid">
            <div class="metric-card">
              <div class="metric-label">Source Docs</div>
              <div class="metric-value">{{ documents.length }}</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">Requirements</div>
              <div class="metric-value">{{ requirements.length }}</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">Scenarios</div>
              <div class="metric-value">{{ scenarios.length }}</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">{{ isGovernedFrontingProject ? 'Backend Supply' : 'Service Design' }}</div>
              <div class="metric-value">{{ shapes.length }}</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">Evaluations</div>
              <div class="metric-value">{{ evaluations.length }}</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">PM Artifacts</div>
              <div class="metric-value">{{ frozenPmArtifacts.length }}</div>
            </div>
          </div>
        </article>

        <article class="panel panel-wide">
          <div class="panel-header">
            <h2>Next PM Step</h2>
          </div>
          <div v-if="nextPmStep" class="summary-stack">
            <div class="summary-row">
              <span class="summary-label">Needs attention</span>
              <strong>{{ nextPmStep.title }}</strong>
            </div>
            <p class="panel-copy">{{ nextPmStep.detail }}</p>
            <div>
              <button class="action-card single-action" @click="open(nextPmStep.path)">
                <span class="action-title">Open {{ nextPmStep.title }}</span>
                <span class="action-copy">Complete this PM artifact before locking or re-locking the developer baseline.</span>
              </button>
            </div>
          </div>
          <p v-else class="panel-copy">
            Product Design artifacts are in a good enough state to review, lock for development, or start a new revision intentionally.
          </p>
        </article>

        <article class="panel panel-wide">
          <div class="panel-header">
            <h2>Affected Product Pages</h2>
            <span class="status-chip" :class="{ ready: productOverviewIssues.length === 0 }">
              {{ productOverviewIssues.length === 0 ? 'No affected pages' : `${productOverviewIssues.length} page${productOverviewIssues.length === 1 ? '' : 's'} affected` }}
            </span>
          </div>
          <p v-if="productOverviewIssues.length === 0" class="panel-copy">
            Product Design has no detected missing references or incomplete required sections.
          </p>
          <ul v-else class="issue-list">
            <li v-for="issue in productOverviewIssues" :key="issue">{{ issue }}</li>
          </ul>
        </article>

        <article class="panel panel-wide">
          <div class="panel-header">
            <h2>Clarifications Worth Asking</h2>
            <span class="status-chip" :class="{ ready: clarificationCandidates.length === 0 }">
              {{ clarificationCandidates.length === 0 ? 'No targeted questions' : `${clarificationCandidates.length} sections need clarification` }}
            </span>
          </div>
          <p v-if="clarificationCandidates.length === 0" class="panel-copy">
            The current source docs and PM artifacts are sufficient for Studio to keep drafting without interrogating the user field by field.
          </p>
          <div v-else class="clarification-grid">
            <button
              v-for="card in clarificationCandidates"
              :key="card.key"
              class="clarification-card"
              @click="open(card.path)"
            >
              <strong>{{ card.title }}</strong>
              <ul>
                <li v-for="question in card.questions" :key="question">{{ question }}</li>
              </ul>
            </button>
          </div>
        </article>

        <article class="panel panel-wide">
          <div class="panel-header">
            <h2>{{ isGovernedFrontingProject ? 'Fronting Intent Work Areas' : 'PM Work Areas' }}</h2>
          </div>
          <div class="action-grid">
            <button class="action-card" @click="open(`/design/projects/${project.id}/pm/diagrams`)">
              <span class="action-title">Product Diagrams</span>
              <span class="action-copy">See the business component map before drilling into the individual Product Design pages.</span>
            </button>
            <button class="action-card" @click="open(`/design/projects/${project.id}/source-docs`)">
              <span class="action-title">Source Docs</span>
              <span class="action-copy">Attach and review the business source documents that define the intended behavior.</span>
            </button>
            <button class="action-card" @click="open(`/design/projects/${project.id}/product-summary`)">
              <span class="action-title">Business Summary</span>
              <span class="action-copy">Capture the product purpose, business problem, and governed behavior summary.</span>
            </button>
            <button class="action-card" @click="open(`/design/projects/${project.id}/actor-model`)">
              <span class="action-title">Actor Model</span>
              <span class="action-copy">Define who the product serves and what each actor expects to see or do.</span>
            </button>
            <button class="action-card" @click="open(`/design/projects/${project.id}/business-areas`)">
              <span class="action-title">Business Areas</span>
              <span class="action-copy">Define the stable business-area ids and labels that PM intent and downstream formalization should reuse.</span>
            </button>
            <button class="action-card" @click="open(`/design/projects/${project.id}/permission-intent`)">
              <span class="action-title">Permission Intent</span>
              <span class="action-copy">Describe the PM-owned trust posture before developers formalize it.</span>
            </button>
            <button class="action-card" @click="open(`/design/projects/${project.id}/requirements`)">
              <span class="action-title">What Matters</span>
              <span class="action-copy">Define the PM-owned product posture, operating boundaries, and evidence expectations Studio should preserve.</span>
            </button>
            <button class="action-card" @click="open(`/design/projects/${project.id}/scenarios`)">
              <span class="action-title">Real Situations</span>
              <span class="action-copy">Capture the concrete business situations that should pressure the design.</span>
            </button>
            <button v-if="!isGovernedFrontingProject" class="action-card" @click="open(`/design/projects/${project.id}/shapes`)">
              <span class="action-title">Service Design</span>
              <span class="action-copy">Choose and refine the service architecture PM wants developers to implement.</span>
            </button>
            <button v-if="!isGovernedFrontingProject" class="action-card" @click="open(`/design/projects/${project.id}/non-goals`)">
              <span class="action-title">Non-Goals</span>
              <span class="action-copy">State what the product explicitly should not do.</span>
            </button>
            <button v-if="!isGovernedFrontingProject" class="action-card" @click="open(`/design/projects/${project.id}/success-criteria`)">
              <span class="action-title">Success Criteria</span>
              <span class="action-copy">Record how PM and business stakeholders will judge delivery success.</span>
            </button>
            <button v-if="!isGovernedFrontingProject" class="action-card" @click="open(`/design/projects/${project.id}/pm-artifacts`)">
              <span class="action-title">PM Artifacts</span>
              <span class="action-copy">Review the PM-facing exports Studio can produce from the current project state.</span>
            </button>
            <button class="action-card" @click="open(`/design/projects/${project.id}/pm-review`)">
              <span class="action-title">PM Review</span>
              <span class="action-copy">Review developer coverage against the active Product Design context and sign off on implementation direction.</span>
            </button>
            <button
              class="action-card"
              @click="open(isGovernedFrontingProject ? `/design/projects/${project.id}/fronting` : `/design/projects/${project.id}/developer`)"
            >
              <span class="action-title">{{ isGovernedFrontingProject ? 'Govern API / MCP' : 'Developer Design' }}</span>
              <span class="action-copy">
                {{ isGovernedFrontingProject
                  ? 'Use Express Mode to map existing backend tools and endpoints into governed ANIP capabilities, policy, generation, and verification.'
                  : 'Carry the approved product translation into governed backend design and generation.' }}
              </span>
            </button>
          </div>
        </article>

        <article class="panel panel-wide">
          <div class="panel-header">
            <h2>AI Assistant</h2>
          </div>
          <p class="panel-copy">
            Use the dedicated project AI Assistant page when you want Studio to draft Product Design from source docs, ask only targeted clarifications, and save only the sections you accept.
          </p>
          <div class="assistant-entry-grid">
            <button class="action-card" @click="open(`/design/projects/${project.id}/pm/assistant`)">
              <span class="action-title">Open Product Design AI Assistant</span>
              <span class="action-copy">
                {{ isGovernedFrontingProject
                  ? 'Draft a reviewable fronting Product Design bundle from business intent, integration evidence, or policy sources.'
                  : 'Draft a reviewable Product Design bundle from a selected business spec.' }}
              </span>
            </button>
          </div>
        </article>
      </section>
    </template>
  </div>
</template>

<style scoped>
.project-pm-home {
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
  margin-bottom: 0.45rem;
}

.page-header h1 {
  margin: 0 0 0.55rem;
  font-size: 32px;
  line-height: 1.15;
  font-weight: 700;
  color: var(--text-primary);
}

.page-header p,
.empty-state {
  color: var(--text-secondary);
  line-height: 1.6;
}

.grid {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 1.05rem;
}

.panel {
  grid-column: span 4;
  background: var(--surface-depth-panel);
  border: 1px solid var(--surface-border-panel);
  border-radius: 22px;
  padding: 1.35rem;
}

.panel-wide {
  grid-column: span 8;
}

.panel-full {
  grid-column: span 12;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1.15rem;
}

.panel-header h2 {
  margin: 0;
  color: var(--text-primary);
  font-size: 20px;
  line-height: 1.25;
  font-weight: 700;
}

.panel-copy {
  margin: 0.55rem 0 1rem;
  color: var(--text-secondary);
  line-height: 1.6;
  max-width: 88ch;
}

.metric-grid,
.action-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 0.95rem;
}

.metric-card,
.action-card {
  border-radius: 18px;
  border: 1px solid var(--surface-border-card);
  background:
    linear-gradient(180deg, rgba(15, 23, 42, 0.66), rgba(15, 23, 42, 0.46));
  padding: 1.05rem;
}

.metric-label {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-secondary);
  margin-bottom: 0.45rem;
}

.metric-value {
  font-size: 28px;
  line-height: 1;
  font-weight: 800;
  color: var(--text-primary);
}

.summary-stack {
  display: flex;
  flex-direction: column;
  gap: 0.82rem;
}

.summary-row {
  display: flex;
  flex-direction: column;
  gap: 0.28rem;
}

.summary-label {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.03em;
  text-transform: none;
  color: var(--text-secondary);
}

.summary-row strong {
  color: var(--text-primary);
  font-size: 14px;
  line-height: 1.35;
  font-weight: 800;
}

.action-card {
  text-align: left;
  cursor: pointer;
  color: inherit;
  width: 100%;
  font: inherit;
  transition:
    border-color 0.16s ease,
    background 0.16s ease,
    transform 0.16s ease;
}

.single-action {
  width: auto;
  min-width: min(100%, 280px);
}

.action-card:hover {
  border-color: rgba(147, 197, 253, 0.36);
  background:
    linear-gradient(180deg, rgba(30, 64, 175, 0.22), rgba(15, 23, 42, 0.52));
  transform: translateY(-1px);
}

.action-title {
  display: block;
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 800;
  margin-bottom: 0.42rem;
}

.action-copy {
  display: block;
  color: var(--text-secondary);
  line-height: 1.55;
}

.status-chip {
  display: inline-flex;
  align-items: center;
  margin-top: 0.8rem;
  padding: 0.3rem 0.65rem;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.16);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
}

.panel-header .status-chip {
  margin-top: 0;
}

.status-chip.ready {
  background: rgba(16, 185, 129, 0.16);
  color: #86efac;
}

.status-chip.status-ready {
  background: rgba(16, 185, 129, 0.16);
  color: #86efac;
}

.status-chip.status-draftable {
  background: rgba(59, 130, 246, 0.16);
  color: #93c5fd;
}

.status-chip.status-needs_clarification {
  background: rgba(245, 158, 11, 0.16);
  color: #fcd34d;
}

.status-chip.status-blocked {
  background: rgba(248, 113, 113, 0.16);
  color: #fca5a5;
}

.action-questions {
  display: block;
  margin-top: 0.75rem;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.clarification-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 0.95rem;
}

.clarification-card {
  text-align: left;
  cursor: pointer;
  border-radius: 18px;
  border: 1px solid rgba(245, 158, 11, 0.2);
  background:
    linear-gradient(180deg, rgba(15, 23, 42, 0.66), rgba(15, 23, 42, 0.46));
  padding: 1.05rem;
  color: inherit;
}

.clarification-card strong {
  display: block;
  margin-bottom: 0.6rem;
  color: var(--text-primary);
  font-weight: 800;
}

.clarification-card ul {
  margin: 0;
  padding-left: 1rem;
  color: var(--text-secondary);
}

.issue-list {
  display: grid;
  gap: 0.55rem;
  margin: 0;
  padding-left: 1.1rem;
  color: var(--text-secondary);
}

.issue-list li::marker {
  color: #fbbf24;
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

.assistant-actions {
  display: flex;
  justify-content: flex-start;
  margin-top: 0.5rem;
}

.assistant-entry-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 0.95rem;
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
  color: #475569;
}

.display-toggle {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  cursor: pointer;
  color: var(--text-primary);
}

.display-toggle input {
  margin-top: 0.2rem;
}

.display-toggle span {
  display: grid;
  gap: 0.25rem;
}

.display-toggle small {
  color: var(--text-secondary);
  line-height: 1.45;
}

@media (max-width: 1100px) {
  .panel,
  .panel-wide,
  .panel-full {
    grid-column: span 12;
  }
}

@media (max-width: 720px) {
  .project-pm-home {
    padding: 1.25rem;
  }
}
</style>
