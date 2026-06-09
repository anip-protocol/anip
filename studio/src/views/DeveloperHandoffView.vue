<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  findDeveloperDefinitionArtifact,
  findLatestDeveloperGenerationRunArtifact,
  resolveCompiledContractAlignment,
  resolveEvaluationCompiledContractIdentity,
  resolveGenerationContractAlignment,
} from '../design/developer-definition'
import { generateBusinessPacket } from '../design/project-api'
import type {
  BusinessPacket,
  DeveloperBaselineData,
  DeveloperGenerationRunData,
  TraceabilityRecordData,
} from '../design/project-types'
import { formatStudioTimestamp } from '../design/time'
import { loadProject, projectStore } from '../design/project-store'
import { developerBaselineMatchesCurrentContext, findDeveloperBaselineArtifact, findTraceabilityArtifact, pmReviewStatusLabel } from '../design/traceability'
import { developerLabel } from '../design/developer-vocabulary'

const route = useRoute()
const router = useRouter()

const projectId = computed(() => route.params.projectId as string)
const project = computed(() => projectStore.activeProject)
const requirements = computed(() => projectStore.artifacts.requirements)
const scenarios = computed(() => projectStore.artifacts.scenarios)
const shapes = computed(() => projectStore.artifacts.shapes)
const evaluations = computed(() => projectStore.artifacts.evaluations)

const loading = ref(false)
const error = ref<string | null>(null)
const packet = ref<BusinessPacket | null>(null)
const readOnlyMode = computed(() => projectStore.runtimeStatus?.read_only_mode !== false)
const readOnlyReason = computed(() =>
  projectStore.runtimeStatus?.read_only_reason
  || 'Studio is running in read-only mode. Explore the design, then download and run Studio locally to make changes.',
)

async function ensureLoaded() {
  if (!projectId.value) return
  if (projectStore.activeProject?.id === projectId.value) return
  await loadProject(projectId.value)
}

const baselineArtifact = computed(() => findDeveloperBaselineArtifact(projectStore.artifacts.pmArtifacts))
const baseline = computed(() =>
  (baselineArtifact.value?.data as DeveloperBaselineData | undefined) ?? null,
)

const currentRequirements = computed(() =>
  requirements.value.find((item) => item.role === 'primary')
  ?? requirements.value[0]
  ?? null,
)

const currentShape = computed(() =>
  shapes.value.find((item) => item.id === projectStore.activeShapeId)
  ?? (shapes.value.length === 1 ? shapes.value[0] : null)
  ?? shapes.value[0]
  ?? null,
)

const currentScenarios = computed(() => scenarios.value)

const baselineAligned = computed(() =>
  developerBaselineMatchesCurrentContext({
    baseline: baseline.value,
    requirements: currentRequirements.value,
    scenarios: currentScenarios.value,
    shape: currentShape.value,
    pmArtifacts: projectStore.artifacts.pmArtifacts,
  }),
)

const lockedRequirements = computed(() =>
  requirements.value.find((item) => item.id === baseline.value?.source_inputs.requirements_id)
  ?? null,
)

const lockedScenarios = computed(() =>
  (baseline.value?.source_inputs.scenario_ids ?? [])
    .map((id) => scenarios.value.find((item) => item.id === id) ?? null)
    .filter((item): item is NonNullable<typeof item> => item != null),
)

const lockedPrimaryScenario = computed(() =>
  scenarios.value.find((item) => item.id === baseline.value?.source_inputs.primary_scenario_id)
  ?? lockedScenarios.value[0]
  ?? null,
)

const lockedShape = computed(() =>
  shapes.value.find((item) => item.id === baseline.value?.source_inputs.shape_id)
  ?? null,
)

const latestEvaluation = computed(() => {
  const records = [...evaluations.value]
  records.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
  return records[0] ?? null
})
const developerDefinitionArtifact = computed(() => findDeveloperDefinitionArtifact(projectStore.artifacts.pmArtifacts))
const compiledContractIdentity = computed(() =>
  ((developerDefinitionArtifact.value?.data as { compiled_contract_identity?: Record<string, string | null> } | undefined)?.compiled_contract_identity) ?? null,
)
const latestGenerationRunArtifact = computed(() => findLatestDeveloperGenerationRunArtifact(projectStore.artifacts.pmArtifacts))
const latestGenerationRun = computed(() =>
  (latestGenerationRunArtifact.value?.data as DeveloperGenerationRunData | undefined) ?? null,
)
const latestEvaluationContractIdentity = computed(() =>
  resolveEvaluationCompiledContractIdentity(latestEvaluation.value as any),
)
const contractAlignment = computed(() =>
  resolveCompiledContractAlignment(compiledContractIdentity.value as any, latestEvaluationContractIdentity.value as any),
)
const generationAlignment = computed(() =>
  resolveGenerationContractAlignment(compiledContractIdentity.value as any, latestGenerationRun.value?.compiled_contract_identity as any),
)

function formatGenerationField(value: string | undefined | null) {
  return developerLabel(value || 'not_recorded')
}
const problemStatement = computed(() => packet.value?.payload.intent.problem_statement || 'No problem statement available yet.')
const packetGoals = computed(() => packet.value?.payload.intent.goals ?? [])
const operationalConstraints = computed(() => packet.value?.payload.constraints.operational ?? [])
const riskConstraints = computed(() => packet.value?.payload.constraints.risk ?? [])

const developerReady = computed(() =>
  !!baseline.value && baselineAligned.value && !!lockedRequirements.value && !!lockedPrimaryScenario.value && !!lockedShape.value,
)

const traceabilityArtifact = computed(() => findTraceabilityArtifact(projectStore.artifacts.pmArtifacts))
const traceabilityRecord = computed(() =>
  (traceabilityArtifact.value?.data as TraceabilityRecordData | undefined) ?? null,
)
const coverageMatchesLockedBaseline = computed(() => {
  if (!traceabilityRecord.value || !baseline.value) return false
  return (
    traceabilityRecord.value.source_inputs.requirements_id === baseline.value.source_inputs.requirements_id
    && traceabilityRecord.value.source_inputs.scenario_id === baseline.value.source_inputs.primary_scenario_id
    && traceabilityRecord.value.source_inputs.shape_id === baseline.value.source_inputs.shape_id
    && traceabilityRecord.value.source_inputs.baseline_locked_at === baseline.value.locked_at
  )
})

async function loadPacket() {
  if (readOnlyMode.value) {
    packet.value = null
    loading.value = false
    error.value = null
    return
  }
  if (!projectId.value || !developerReady.value) {
    packet.value = null
    return
  }
  loading.value = true
  error.value = null
  try {
    packet.value = await generateBusinessPacket({
      project_id: projectId.value,
      requirements_id: lockedRequirements.value!.id,
      scenario_id: lockedPrimaryScenario.value!.id,
      shape_id: lockedShape.value!.id,
      evaluation_id: latestEvaluation.value?.id,
    })
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await ensureLoaded()
  await loadPacket()
})

watch(
  () => [projectId.value, baseline.value?.locked_at, baselineAligned.value, latestEvaluation.value?.id] as const,
  async () => {
    await loadPacket()
  },
)
</script>

<template>
  <div class="developer-handoff">
    <template v-if="project">
      <section class="page-header">
        <button class="back-link" type="button" @click="router.push(`/design/projects/${project.id}/developer`)">
          &larr; Back to Developer Design
        </button>
        <div class="page-kicker">Developer Design</div>
        <h1>Locked Product Handoff</h1>
        <p>
          This page turns the locked Product Design baseline into the structured handoff developers should work from. It is the source bridge between approved PM intent and the technical formalization work that follows.
        </p>
      </section>

      <div v-if="readOnlyMode" class="banner banner-warning readonly-banner">
        {{ readOnlyReason }}
      </div>

      <section v-if="baseline && baselineAligned" class="panel note-panel">
        <h2>What this page is for</h2>
        <p>
          This is a source-baseline surface, not the final technical contract. Use it to inspect the locked Product Design handoff before moving into Developer Definition and the implementation-pattern formalization pages.
        </p>
      </section>

      <section v-if="!baseline" class="panel locked-panel">
        <h2>Developer baseline is not locked yet</h2>
        <p>Lock the Product Design baseline on Developer Overview before opening the handoff packet.</p>
      </section>

      <section v-else-if="!baselineAligned" class="panel locked-panel">
        <h2>Locked baseline is out of sync</h2>
        <p>Product Design changed after the baseline was locked. Re-lock the baseline before using this handoff packet.</p>
      </section>

      <section v-else class="grid">
        <article class="panel">
          <div class="panel-header">
            <h2>Locked Baseline</h2>
          </div>
          <div class="summary-stack">
            <div class="summary-row">
              <span class="summary-label">Requirements</span>
              <strong>{{ lockedRequirements?.title }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Scenario Pack</span>
              <strong>{{ lockedScenarios.length }} scenarios</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Primary Seed Scenario</span>
              <strong>{{ lockedPrimaryScenario?.title }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Service Design</span>
              <strong>{{ lockedShape?.title }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Latest evaluation</span>
              <strong>{{ latestEvaluation?.result || 'None yet' }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Evaluation contract</span>
              <strong>{{ latestEvaluation ? contractAlignment.label : 'Not recorded' }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Generation contract</span>
              <strong>{{ latestGenerationRun ? generationAlignment.label : 'Not recorded' }}</strong>
            </div>
          </div>
        </article>

        <article class="panel">
          <div class="panel-header">
            <h2>Coverage Status</h2>
          </div>
          <div class="summary-stack">
            <div class="summary-row">
              <span class="summary-label">Coverage record</span>
              <strong>{{ traceabilityRecord ? 'Present' : 'Not created' }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Baseline alignment</span>
              <strong>{{ traceabilityRecord ? (coverageMatchesLockedBaseline ? 'Aligned' : 'Out of date') : 'Not available' }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">PM review</span>
              <strong>{{ traceabilityRecord ? pmReviewStatusLabel(traceabilityRecord.pm_review_status) : 'Not started' }}</strong>
            </div>
          </div>
        </article>

        <article class="panel">
          <div class="panel-header">
            <h2>Latest Generation Run</h2>
          </div>
          <template v-if="latestGenerationRun">
            <div class="summary-stack">
              <div class="summary-row">
                <span class="summary-label">Generated At</span>
                <strong>{{ formatStudioTimestamp(latestGenerationRun.generated_at) }}</strong>
              </div>
              <div class="summary-row">
                <span class="summary-label">Contract Signature</span>
                <strong>{{ latestGenerationRun.compiled_contract_identity?.signature || 'Not recorded' }}</strong>
              </div>
              <div class="summary-row">
                <span class="summary-label">Primary Output Mode</span>
                <strong>{{ formatGenerationField(latestGenerationRun.generator_inputs.primary_output_mode) }}</strong>
              </div>
              <div class="summary-row">
                <span class="summary-label">Runtime Target Mode</span>
                <strong>{{ formatGenerationField(latestGenerationRun.generator_inputs.runtime_target_mode) }}</strong>
              </div>
            </div>
            <p class="panel-copy">{{ generationAlignment.detail }}</p>
          </template>
          <p v-else class="panel-copy">
            No generation run has been saved yet for this locked baseline.
          </p>
        </article>

        <article class="panel panel-full">
          <div class="panel-header">
            <h2>Business Packet Summary</h2>
            <button class="btn btn-secondary" @click="loadPacket" :disabled="readOnlyMode || loading">
              {{ loading ? 'Refreshing…' : 'Refresh Packet' }}
            </button>
          </div>
          <p class="panel-copy">
            The handoff packet is generated from the locked baseline. It covers the full scenario pack, but the current packet seed is anchored on the baseline’s primary scenario so implementation tooling has a stable starting point.
          </p>
          <p v-if="error" class="error">{{ error }}</p>
          <template v-else-if="packet">
            <div class="packet-grid">
              <div class="packet-card">
                <h3>Problem Statement</h3>
                <p>{{ problemStatement }}</p>
              </div>
              <div class="packet-card">
                <h3>Goals</h3>
                <ul v-if="packetGoals.length">
                  <li v-for="goal in packetGoals" :key="goal">{{ goal }}</li>
                </ul>
                <p v-else class="empty-copy">No explicit goals were derived into the current business packet.</p>
              </div>
              <div class="packet-card">
                <h3>Operational Constraints</h3>
                <ul v-if="operationalConstraints.length">
                  <li v-for="item in operationalConstraints" :key="item">{{ item }}</li>
                </ul>
                <p v-else class="empty-copy">No separate operational constraints were derived into the current business packet.</p>
              </div>
              <div class="packet-card">
                <h3>Risk Constraints</h3>
                <ul v-if="riskConstraints.length">
                  <li v-for="item in riskConstraints" :key="item">{{ item }}</li>
                </ul>
                <p v-else class="empty-copy">
                  No separate risk constraints were derived from the current Product Design. Risk posture is currently expressed through requirements, scenarios, service design, and coverage mapping rather than this packet field.
                </p>
              </div>
            </div>
          </template>
          <p v-else-if="readOnlyMode" class="panel-copy">
            Business packet generation is disabled in read-only mode because it invokes the Studio workbench. The locked baseline, coverage status, and generation evidence above remain available for review.
          </p>
          <p v-else class="panel-copy">No business packet available yet.</p>
        </article>

        <article class="panel panel-full">
          <div class="panel-header">
            <h2>Developer Actions</h2>
          </div>
          <div class="action-grid">
            <button class="action-card" @click="router.push(`/design/projects/${project.id}/developer/service-formalization`)">
              <span class="action-title">Open Service Formalization</span>
              <span class="action-copy">Start formalizing service architecture, runtime backends, and authority from the locked baseline.</span>
            </button>
            <button class="action-card" @click="router.push(`/design/projects/${project.id}/developer/governance-bindings`)">
              <span class="action-title">Open Roles & Access</span>
              <span class="action-copy">Formalize roles and the policy rules that protect capabilities.</span>
            </button>
            <button class="action-card" @click="router.push(`/design/projects/${project.id}/developer/audit-lineage`)">
              <span class="action-title">Open Audit & Lineage</span>
              <span class="action-copy">Formalize evidence, invocation, and lineage expectations separately from access policy.</span>
            </button>
            <button class="action-card" @click="router.push(`/design/projects/${project.id}/developer/capability-formalization`)">
              <span class="action-title">Open Capability Formalization</span>
              <span class="action-copy">Bind the locked baseline to explicit capability contracts before any generator-specific compatibility work.</span>
            </button>
            <button class="action-card" @click="router.push(`/design/projects/${project.id}/developer/scenario-formalization`)">
              <span class="action-title">Open Scenario Coverage Intent</span>
              <span class="action-copy">Turn the locked scenario pack into explicit scope, operational posture, and participating service boundaries.</span>
            </button>
            <button class="action-card" @click="router.push(`/design/projects/${project.id}/developer/scenario-execution-semantics`)">
              <span class="action-title">Open Scenario Execution Semantics</span>
              <span class="action-copy">Formalize orchestration, required behaviors, ANIP-visible support, and compound workflow rules.</span>
            </button>
          </div>
        </article>
      </section>
    </template>
  </div>
</template>

<style scoped>
.developer-handoff {
  width: 100%;
  max-width: none;
  padding: 2rem;
}

.page-header {
  margin-bottom: 1.5rem;
}

.back-link {
  border: none;
  background: transparent;
  color: var(--accent);
  font-size: 13px;
  cursor: pointer;
  padding: 0;
  margin-bottom: 0.6rem;
}

.banner {
  padding: 0.75rem 0.95rem;
  border-radius: 12px;
  margin-bottom: 1rem;
}

.banner-warning {
  background: rgba(245, 158, 11, 0.12);
  border: 1px solid rgba(245, 158, 11, 0.3);
  color: #fbbf24;
}

.readonly-banner {
  margin-bottom: 1.25rem;
}

.page-kicker,
.summary-label {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 12px;
  color: var(--text-secondary);
}

.page-header h1 {
  margin: 0 0 0.55rem;
  font-size: 30px;
}

.page-header p,
.panel-copy,
.packet-card p,
.action-copy,
.locked-panel p {
  color: var(--text-secondary);
  line-height: 1.6;
}

.grid {
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

.panel-wide,
.locked-panel {
  grid-column: span 8;
}

.panel-full {
  grid-column: span 12;
}

.locked-panel {
  background: rgba(127, 29, 29, 0.12);
}

.note-panel {
  margin-bottom: 1rem;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1rem;
}

.panel-header h2,
.packet-card h3 {
  margin: 0;
}

.summary-stack {
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
}

.summary-row {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.summary-row .summary-label {
  color: var(--text-muted);
  font-weight: 700;
}

.summary-row strong {
  color: var(--text-primary);
  font-size: 15px;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.packet-grid,
.action-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 0.85rem;
}

.packet-grid {
  margin-top: 1rem;
}

.action-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.5rem;
  color: var(--text-primary);
  text-align: left;
}

.action-title,
.action-copy {
  display: block;
  width: 100%;
}

.packet-card,
.action-card {
  border: 1px solid var(--surface-border-card);
  border-radius: 16px;
  padding: 1rem;
  background: var(--surface-depth-card);
  min-width: 0;
}

.packet-card {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.packet-card ul {
  margin: 0;
  padding-left: 1.1rem;
  color: var(--text-secondary);
}

.packet-card li {
  overflow-wrap: anywhere;
  margin-bottom: 0.4rem;
}

.empty-copy {
  margin: 0;
  color: var(--text-secondary);
}

.action-card {
  text-align: left;
  cursor: pointer;
}

.btn {
  border: none;
  border-radius: 12px;
  padding: 0.7rem 1rem;
  font-weight: 600;
  cursor: pointer;
}

.btn-secondary {
  background: rgba(148, 163, 184, 0.15);
  color: inherit;
}

.btn:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.error {
  color: #fecaca;
}

@media (max-width: 1100px) {
  .panel,
  .panel-wide,
  .locked-panel {
    grid-column: span 12;
  }
}
</style>
