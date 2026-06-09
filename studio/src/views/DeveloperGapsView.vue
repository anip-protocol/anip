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
import { generateDriftAnalysis } from '../design/project-api'
import type {
  DeveloperBaselineData,
  DeveloperGenerationRunData,
  DriftAnalysis,
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
const readOnlyMode = computed(() => projectStore.runtimeStatus?.read_only_mode !== false)
const readOnlyReason = computed(() =>
  projectStore.runtimeStatus?.read_only_reason
  || 'Studio is running in read-only mode. Explore the design, then download and run Studio locally to make changes.',
)
const requirements = computed(() => projectStore.artifacts.requirements)
const scenarios = computed(() => projectStore.artifacts.scenarios)
const shapes = computed(() => projectStore.artifacts.shapes)
const evaluations = computed(() => projectStore.artifacts.evaluations)

const loading = ref(false)
const error = ref<string | null>(null)
const analysis = ref<DriftAnalysis | null>(null)

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

const lockedPrimaryScenario = computed(() =>
  scenarios.value.find((item) => item.id === baseline.value?.source_inputs.primary_scenario_id)
  ?? scenarios.value[0]
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

async function loadAnalysis() {
  if (readOnlyMode.value) {
    analysis.value = null
    error.value = null
    loading.value = false
    return
  }
  if (!projectId.value || !developerReady.value || !latestEvaluation.value) {
    analysis.value = null
    return
  }
  loading.value = true
  error.value = null
  try {
    analysis.value = await generateDriftAnalysis({
      project_id: projectId.value,
      requirements_id: lockedRequirements.value!.id,
      scenario_id: lockedPrimaryScenario.value!.id,
      shape_id: lockedShape.value!.id,
      evaluation_id: latestEvaluation.value.id,
    })
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await ensureLoaded()
  await loadAnalysis()
})

watch(
  () => [projectId.value, baseline.value?.locked_at, baselineAligned.value, latestEvaluation.value?.id, readOnlyMode.value] as const,
  async () => {
    await loadAnalysis()
  },
)
</script>

<template>
  <div class="developer-gaps">
    <template v-if="project">
      <section class="page-header">
        <button class="back-link" type="button" @click="router.push(`/design/projects/${project.id}/developer`)">
          &larr; Back to Developer Design
        </button>
        <div class="page-kicker">Developer Design</div>
        <h1>Consistency Gaps</h1>
        <p>
          Use this page to compare the locked Product Design baseline against saved implementation evidence. It is a drift-analysis surface, not a design editor.
        </p>
      </section>

      <div v-if="readOnlyMode" class="readonly-banner">
        <strong>Read-only showcase mode</strong>
        <span>{{ readOnlyReason }} Drift analysis is disabled because it requires Studio workbench execution.</span>
      </div>

      <section v-if="!baseline" class="panel empty-panel">
        <h2>Developer baseline is not locked</h2>
        <p>Lock the Product Design baseline on Developer Overview before reviewing implementation gaps.</p>
      </section>

      <section v-else-if="!baselineAligned" class="panel empty-panel">
        <h2>Locked baseline is out of sync</h2>
        <p>Product Design changed after the baseline was locked. Re-lock the baseline before reviewing gaps.</p>
      </section>

      <section v-else-if="!traceabilityRecord || !coverageMatchesLockedBaseline" class="panel empty-panel">
        <h2>Coverage alignment is incomplete</h2>
        <p>
          Consistency review depends on the locked baseline having a saved Coverage Mapping record.
          Open Coverage Mapping and save it for the current locked baseline before reviewing gaps.
        </p>
      </section>

      <section v-else-if="!latestEvaluation" class="panel empty-panel">
        <h2>No evaluation evidence yet</h2>
        <p>
          This page only works after Studio has a saved evaluation artifact for the current locked baseline.
          Run verification and save the result first. Then this page can compare the locked baseline, the saved contract,
          generation evidence, and observed service evidence to show real drift instead of assumptions.
        </p>
      </section>

      <section v-else class="grid">
        <article class="panel">
          <div class="panel-header">
            <h2>Current Comparison Context</h2>
          </div>
          <div class="summary-stack">
            <div class="summary-row">
              <span class="summary-label">Requirements</span>
              <strong>{{ lockedRequirements?.title }}</strong>
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
              <span class="summary-label">Evaluation</span>
              <strong>{{ latestEvaluation.result }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Evaluation contract</span>
              <strong>{{ contractAlignment.label }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">Generation contract</span>
              <strong>{{ latestGenerationRun ? generationAlignment.label : 'Not recorded' }}</strong>
            </div>
            <div class="summary-row">
              <span class="summary-label">PM review</span>
              <strong>{{ pmReviewStatusLabel(traceabilityRecord.pm_review_status) }}</strong>
            </div>
          </div>
        </article>

        <article class="panel panel-wide">
          <div class="panel-header">
            <h2>Drift Analysis</h2>
            <button class="btn btn-secondary" @click="loadAnalysis" :disabled="readOnlyMode || loading">
              {{ loading ? 'Refreshing…' : 'Refresh Analysis' }}
            </button>
          </div>
          <p v-if="error" class="error">{{ error }}</p>
          <p v-else-if="readOnlyMode" class="panel-copy">
            Live drift analysis is not run in the public read-only showcase. The saved context above is still available for review.
          </p>
          <template v-else-if="analysis">
            <div class="analysis-grid">
              <div class="analysis-card">
                <span class="analysis-label">Gap Category</span>
                <strong>{{ developerLabel(analysis.gap_category) }}</strong>
              </div>
              <div class="analysis-card">
                <span class="analysis-label">Likely Owner</span>
                <strong>{{ developerLabel(analysis.likely_owner) }}</strong>
              </div>
              <div class="analysis-card">
                <span class="analysis-label">Priority</span>
                <strong>{{ analysis.fix_priority }}</strong>
              </div>
              <div class="analysis-card">
                <span class="analysis-label">Observed Outcome</span>
                <strong>{{ analysis.observed_outcome || 'Not recorded' }}</strong>
              </div>
              <div class="analysis-card">
                <span class="analysis-label">Contract Alignment</span>
                <strong>{{ contractAlignment.label }}</strong>
              </div>
              <div class="analysis-card">
                <span class="analysis-label">Generation Run</span>
                <strong>{{ latestGenerationRun ? formatStudioTimestamp(latestGenerationRun.generated_at) : 'Not recorded' }}</strong>
              </div>
            </div>
            <p class="panel-copy">{{ contractAlignment.detail }}</p>
            <p v-if="latestGenerationRun" class="panel-copy">{{ generationAlignment.detail }}</p>
            <div class="recommendation">
              <h3>Recommended Fix</h3>
              <p>{{ analysis.recommended_fix }}</p>
            </div>
            <div class="recommendation">
              <h3>Diagnostic Evidence</h3>
              <ul>
                <li v-if="analysis.diagnostic_evidence.capability_id"><strong>Capability:</strong> {{ analysis.diagnostic_evidence.capability_id }}</li>
                <li v-if="analysis.diagnostic_evidence.reason_code"><strong>Reason Code:</strong> {{ analysis.diagnostic_evidence.reason_code }}</li>
                <li v-if="analysis.diagnostic_evidence.agent_behavior"><strong>Agent Behavior:</strong> {{ analysis.diagnostic_evidence.agent_behavior }}</li>
                <li v-if="analysis.diagnostic_evidence.backend_context"><strong>Backend Context:</strong> {{ analysis.diagnostic_evidence.backend_context }}</li>
                <li v-if="analysis.diagnostic_evidence.service_metadata_mismatch"><strong>Metadata Mismatch:</strong> {{ analysis.diagnostic_evidence.service_metadata_mismatch }}</li>
              </ul>
            </div>
          </template>
          <p v-else class="panel-copy">No drift analysis available yet.</p>
        </article>
      </section>
    </template>
  </div>
</template>

<style scoped>
.developer-gaps {
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

.page-kicker,
.summary-label,
.analysis-label {
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
.empty-panel p,
.panel-copy,
.recommendation p {
  color: var(--text-secondary);
  line-height: 1.6;
}

.readonly-banner {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem 0.7rem;
  align-items: center;
  margin: 0 0 1rem;
  padding: 0.85rem 1rem;
  border: 1px solid rgba(251, 191, 36, 0.34);
  border-radius: 16px;
  background: rgba(251, 191, 36, 0.1);
  color: #fde68a;
}

.readonly-banner span {
  color: var(--text-secondary);
}

.developer-gaps button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
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
.empty-panel {
  grid-column: span 8;
}

.empty-panel {
  background: rgba(127, 29, 29, 0.12);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1rem;
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

.analysis-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 0.85rem;
}

.analysis-card,
.recommendation {
  border: 1px solid var(--surface-border-card);
  border-radius: 16px;
  padding: 1rem;
  background: var(--surface-depth-card);
}

.recommendation {
  margin-top: 0.9rem;
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

.error {
  color: #fecaca;
}

@media (max-width: 1100px) {
  .panel,
  .panel-wide,
  .empty-panel {
    grid-column: span 12;
  }
}
</style>
