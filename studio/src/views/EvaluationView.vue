<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { designStore, composeDraftProposal } from '../design/store'
import { loadProject, projectStore, refreshArtifacts } from '../design/project-store'
import { createEvaluation, explainEvaluationWithAssistant } from '../design/project-api'
import type { AssistantExplanation } from '../design/project-types'
import { runShapeValidation, runValidation } from '../design/api'
import StudioAssistantPanel from '../design/components/StudioAssistantPanel.vue'

const route = useRoute()
const router = useRouter()

const projectId = computed(() => route.params.projectId as string)

onMounted(() => {
  if (projectId.value && projectStore.activeProject?.id !== projectId.value) {
    loadProject(projectId.value)
  }
})

watch(projectId, (id) => {
  if (id && projectStore.activeProject?.id !== id) {
    loadProject(id)
  }
})

const projectRecord = computed(() => {
  const id = route.params.id as string
  return projectStore.artifacts.evaluations.find(e => e.id === id) ?? null
})

const projectScenario = computed(() => {
  const id = route.params.id as string
  return projectStore.artifacts.scenarios.find(s => s.id === id) ?? null
})

const hasData = computed(() => !!projectRecord.value || !!projectScenario.value || designStore.liveEvaluation !== null)

// Display name for the title
const artifactName = computed(() => {
  return projectRecord.value?.scenario_id ?? projectScenario.value?.title ?? 'Evaluation'
})

const isLive = computed(() => designStore.liveEvaluation !== null)

const evaluation = computed(() => {
  if (designStore.liveEvaluation) {
    return designStore.liveEvaluation.evaluation
  }
  return projectRecord.value?.data?.evaluation ?? null
})

const hasEvaluationResult = computed(() => evaluation.value !== null)

// --- Save to Project ---
const saving = ref(false)
const saveError = ref<string | null>(null)
const savedEvalId = ref<string | null>(null)

const canSave = computed(() =>
  isLive.value &&
  projectStore.activeProject !== null,
)

const missingContext = computed(() => {
  if (!canSave.value) return null
  const missing: string[] = []
  if (!projectStore.activeRequirementsId) missing.push('requirements set')
  if (!projectStore.activeShapeId && !projectStore.activeProposalId) missing.push('shape or approach')
  return missing.length > 0 ? missing : null
})

async function saveToProject() {
  if (!canSave.value || !projectStore.activeProject) return
  if (missingContext.value) return

  saving.value = true
  saveError.value = null
  try {
    const requirementsRecord = projectStore.artifacts.requirements.find(
      r => r.id === projectStore.activeRequirementsId,
    )
    const proposalRecord = projectStore.artifacts.proposals.find(
      p => p.id === projectStore.activeProposalId,
    )
    const shapeRecord = projectStore.activeShapeId
      ? projectStore.artifacts.shapes.find(s => s.id === projectStore.activeShapeId)
      : null

    const inputSnapshot: Record<string, any> = {}
    const requirements = designStore.draftRequirements ?? requirementsRecord?.data
    const scenario = designStore.draftScenario ?? projectScenario.value?.data
    const proposal = shapeRecord ? null : (composeDraftProposal() ?? proposalRecord?.data)
    const shape = shapeRecord?.data

    if (requirements) inputSnapshot.requirements = JSON.parse(JSON.stringify(requirements))
    if (scenario) inputSnapshot.scenario = JSON.parse(JSON.stringify(scenario))
    if (proposal) inputSnapshot.proposal = JSON.parse(JSON.stringify(proposal))
    if (shape) inputSnapshot.shape = JSON.parse(JSON.stringify(shape))

    const scenarioId = route.params.id as string
    const evalId = crypto.randomUUID()

    // Shape-first: use shape_id when available, fall back to proposal_id
    const useShape = !!shapeRecord

    await createEvaluation(projectStore.activeProject.id, {
      id: evalId,
      proposal_id: useShape ? null : projectStore.activeProposalId!,
      scenario_id: scenarioId,
      requirements_id: projectStore.activeRequirementsId!,
      shape_id: useShape ? projectStore.activeShapeId : null,
      source: 'live_validation',
      data: JSON.parse(JSON.stringify(designStore.liveEvaluation)),
      input_snapshot: inputSnapshot,
    })

    savedEvalId.value = evalId
    await refreshArtifacts()
  } catch (err) {
    saveError.value = err instanceof Error ? err.message : String(err)
  } finally {
    saving.value = false
  }
}

async function handleRunValidation() {
  if (!projectStore.activeRequirementsId || (!projectStore.activeProposalId && !projectStore.activeShapeId) || !projectScenario.value) {
    designStore.validationError = 'Choose a requirements set, scenario, and shape or approach before evaluating.'
    return
  }

  const requirementsRecord = projectStore.artifacts.requirements.find(
    r => r.id === projectStore.activeRequirementsId,
  )
  const proposalRecord = projectStore.activeProposalId
    ? projectStore.artifacts.proposals.find(p => p.id === projectStore.activeProposalId)
    : null
  const shapeRecord = projectStore.activeShapeId
    ? projectStore.artifacts.shapes.find(s => s.id === projectStore.activeShapeId)
    : null
  const scenarioRecord = projectScenario.value

  if (!requirementsRecord || (projectStore.activeShapeId && !shapeRecord)) {
    designStore.validationError = 'Active design context is incomplete.'
    return
  }

  designStore.validating = true
  designStore.validationError = null
  try {
    const requirements = designStore.draftRequirements ?? requirementsRecord.data
    const scenario = designStore.draftScenario ?? scenarioRecord.data
    const result = shapeRecord
      ? await runShapeValidation(requirements, shapeRecord.data, scenario)
      : await runValidation(requirements, composeDraftProposal() ?? proposalRecord?.data ?? {}, scenario)
    designStore.liveEvaluation = result
  } catch (err: any) {
    designStore.validationError = err.message ?? 'Unknown error'
  } finally {
    designStore.validating = false
  }
}

function clearLive() {
  designStore.liveEvaluation = null
  designStore.validationError = null
  savedEvalId.value = null
}

// --- Re-evaluate stale stored evaluations ---
const reEvaluating = ref(false)
const reEvaluateError = ref<string | null>(null)
const assistantLoading = ref(false)
const assistantError = ref<string | null>(null)
const assistantExplanation = ref<AssistantExplanation | null>(null)

const isStoredStale = computed(() =>
  !isLive.value &&
  projectRecord.value?.is_stale === true,
)

const staleArtifactLabels = computed<string[]>(() => {
  const stale = projectRecord.value?.stale_artifacts ?? []
  return stale.map(a => {
    if (a === 'requirements') return 'Requirements changed'
    if (a === 'scenario') return 'Scenario changed'
    if (a === 'proposal') return 'Approach changed'
    if (a === 'shape') return 'Shape changed'
    return `${a} changed`
  })
})

async function handleReEvaluate() {
  if (!projectStore.activeProject || !projectRecord.value) return

  const pid = projectStore.activeProject.id
  const stored = projectRecord.value

  // Resolve the linked artifacts from the store
  const reqRecord = projectStore.artifacts.requirements.find(r => r.id === stored.requirements_id)
  const propRecord = stored.proposal_id
    ? projectStore.artifacts.proposals.find(p => p.id === stored.proposal_id)
    : null
  const shapeRecord = stored.shape_id
    ? projectStore.artifacts.shapes.find(s => s.id === stored.shape_id)
    : null
  const scnRecord = projectStore.artifacts.scenarios.find(s => s.id === stored.scenario_id)

  if (!reqRecord || !scnRecord) {
    reEvaluateError.value = 'Could not find linked artifacts for re-evaluation.'
    return
  }

  if (!propRecord && !shapeRecord) {
    reEvaluateError.value = 'Could not find linked approach or shape for re-evaluation.'
    return
  }

  reEvaluating.value = true
  reEvaluateError.value = null
  try {
    const requirements = reqRecord.data
    const scenario = scnRecord.data
    const result = shapeRecord
      ? await runShapeValidation(requirements, shapeRecord.data, scenario)
      : await runValidation(requirements, propRecord?.data ?? {}, scenario)

    const inputSnapshot: Record<string, any> = {
      requirements: JSON.parse(JSON.stringify(requirements)),
      scenario: JSON.parse(JSON.stringify(scenario)),
    }
    if (shapeRecord) {
      inputSnapshot.shape = JSON.parse(JSON.stringify(shapeRecord.data))
    } else if (propRecord) {
      inputSnapshot.proposal = JSON.parse(JSON.stringify(propRecord.data))
    }

    const evalId = crypto.randomUUID()
    await createEvaluation(pid, {
      id: evalId,
      proposal_id: stored.proposal_id,
      scenario_id: stored.scenario_id,
      requirements_id: stored.requirements_id,
      shape_id: stored.shape_id,
      source: 'live_validation',
      data: JSON.parse(JSON.stringify(result)),
      input_snapshot: inputSnapshot,
    })

    await refreshArtifacts()
    router.push(`/design/projects/${pid}/evaluations/${evalId}`)
  } catch (err) {
    reEvaluateError.value = err instanceof Error ? err.message : String(err)
  } finally {
    reEvaluating.value = false
  }
}

function categoryColor(cat: string): string {
  const colors: Record<string, string> = {
    safety: 'var(--design-category-safety)',
    orchestration: 'var(--design-category-orchestration)',
    observability: 'var(--design-category-observability)',
    cross_service: 'var(--design-category-cross-service)',
  }
  return colors[cat] || 'var(--text-muted)'
}

async function handleExplainEvaluation(question: string) {
  if (!projectRecord.value || !projectId.value) return
  assistantLoading.value = true
  assistantError.value = null
  try {
    assistantExplanation.value = await explainEvaluationWithAssistant(projectId.value, projectRecord.value.id, question)
  } catch (err) {
    assistantError.value = err instanceof Error ? err.message : String(err)
  } finally {
    assistantLoading.value = false
  }
}
</script>

<template>
  <div class="evaluation-view" v-if="hasData">
    <div class="header-row">
      <h1 class="page-title">Evaluation: {{ artifactName }}</h1>
      <div class="header-actions">
        <span class="source-badge live" v-if="hasEvaluationResult && isLive && !savedEvalId">Live</span>
        <span class="source-badge stale" v-else-if="hasEvaluationResult && isStoredStale">Stale</span>
        <span class="source-badge stored" v-else-if="hasEvaluationResult && (savedEvalId || !isLive)">Stored</span>
        <button
          v-if="designStore.apiAvailable && !designStore.validating"
          class="run-btn"
          @click="handleRunValidation"
        >Evaluate This Design</button>
        <span v-if="designStore.validating" class="spinner"></span>
        <button
          v-if="isLive"
          class="reset-btn"
          @click="clearLive"
        >Reset</button>
      </div>
    </div>

    <!-- Save to Project -->
    <div class="save-section" v-if="canSave && !savedEvalId">
      <div class="save-warning" v-if="missingContext">
        Select a {{ missingContext.join(' and ') }} in the project overview before saving.
      </div>
      <template v-else>
        <button
          class="save-btn"
          :disabled="saving"
          @click="saveToProject"
        >
          <span v-if="saving" class="spinner small"></span>
          {{ saving ? 'Saving...' : 'Save to Project' }}
        </button>
        <div class="save-error" v-if="saveError">{{ saveError }}</div>
      </template>
    </div>
    <div class="save-section" v-else-if="savedEvalId">
      <span class="save-success">Evaluation saved to project.</span>
    </div>

    <!-- Stale evaluation notice + Re-evaluate -->
    <div class="stale-section" v-if="isStoredStale">
      <div class="stale-notice">
        <span class="stale-icon">&#9888;</span>
        This evaluation is out of date.
        <span v-if="staleArtifactLabels.length > 0" class="stale-details">
          {{ staleArtifactLabels.join(', ') }}.
        </span>
      </div>
      <button
        class="reevaluate-btn"
        :disabled="reEvaluating"
        @click="handleReEvaluate"
      >
        <span v-if="reEvaluating" class="spinner small"></span>
        {{ reEvaluating ? 'Re-evaluating...' : 'Re-evaluate' }}
      </button>
      <div class="save-error" v-if="reEvaluateError">{{ reEvaluateError }}</div>
    </div>

    <!-- Validation error -->
    <div class="validation-error" v-if="designStore.validationError">
      {{ designStore.validationError }}
    </div>

    <div v-if="!hasEvaluationResult" class="empty-evaluation">
      No evaluation yet. Use Evaluate This Design to see what this shape supports, what still needs custom work, and what should change next.
    </div>

    <template v-if="evaluation">
      <StudioAssistantPanel
        v-if="projectRecord"
        title="Explain This Evaluation"
        description="Ask Studio to explain the result in plain terms, highlight the main support gaps, and point to the next design moves."
        button-label="Explain This Evaluation"
        :explanation="assistantExplanation"
        :loading="assistantLoading"
        :error="assistantError"
        @run="handleExplainEvaluation"
      />

      <!-- Result badge -->
      <div class="result-badge" :class="'result-' + evaluation.result.toLowerCase().replace('_', '-')">
        {{ evaluation.result }}
      </div>

      <!-- Confidence -->
      <div class="confidence" v-if="evaluation.confidence">
        <span class="confidence-label">Confidence:</span>
        <span class="confidence-value">{{ evaluation.confidence }}</span>
      </div>

      <!-- Glue categories -->
      <div class="categories-section" v-if="evaluation.glue_category && evaluation.glue_category.length">
        <h2>Categories</h2>
        <div class="pill-row">
          <span
            class="cat-pill"
            v-for="(cat, i) in evaluation.glue_category"
            :key="i"
            :style="{ background: categoryColor(cat) + '1a', color: categoryColor(cat), borderColor: categoryColor(cat) + '4d' }"
          >{{ cat }}</span>
        </div>
      </div>

      <!-- Supported by Design -->
      <div class="section">
        <h2>Supported by Design</h2>
        <ul>
          <li v-for="(item, i) in evaluation.handled_by_anip" :key="i">{{ item }}</li>
        </ul>
      </div>

      <!-- Requires Custom Integration -->
      <div class="section" v-if="evaluation.glue_you_will_still_write && evaluation.glue_you_will_still_write.length">
        <h2>Requires Custom Integration</h2>
        <ul class="glue-list">
          <li v-for="(item, i) in evaluation.glue_you_will_still_write" :key="i">{{ item }}</li>
        </ul>
      </div>

      <!-- Why -->
      <div class="section">
        <h2>Why</h2>
        <ul>
          <li v-for="(item, i) in evaluation.why" :key="i">{{ item }}</li>
        </ul>
      </div>

      <!-- Design Changes Needed -->
      <div class="section" v-if="evaluation.what_would_improve && evaluation.what_would_improve.length">
        <h2>Design Changes Needed</h2>
        <ul>
          <li v-for="(item, i) in evaluation.what_would_improve" :key="i">{{ item }}</li>
        </ul>
      </div>

      <!-- Notes -->
      <div class="section" v-if="evaluation.notes && evaluation.notes.length">
        <h2>Notes</h2>
        <ul class="notes-list">
          <li v-for="(note, i) in evaluation.notes" :key="i">{{ note }}</li>
        </ul>
      </div>
    </template>
  </div>
  <div v-else class="not-found">Evaluation not found.</div>
</template>

<style scoped>
.evaluation-view {
  padding: 2rem;
  max-width: 800px;
}

.header-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
}

.page-title {
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.empty-evaluation {
  margin: 1rem 0 1.5rem;
  padding: 0.9rem 1rem;
  border: 1px dashed var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  background: var(--bg-input);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.source-badge {
  display: inline-block;
  font-size: 11px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 10px;
}

.source-badge.live {
  background: rgba(59, 130, 246, 0.15);
  color: #3b82f6;
}

.source-badge.precomputed {
  background: rgba(156, 163, 175, 0.15);
  color: #9ca3af;
}

.source-badge.stored {
  background: rgba(52, 211, 153, 0.15);
  color: #34d399;
}

.source-badge.stale {
  background: rgba(251, 191, 36, 0.15);
  color: #fbbf24;
}

.run-btn {
  font-size: 12px;
  font-weight: 600;
  padding: 5px 14px;
  border-radius: 6px;
  border: 1px solid rgba(59, 130, 246, 0.4);
  background: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
  cursor: pointer;
  transition: background 0.15s;
}

.run-btn:hover {
  background: rgba(59, 130, 246, 0.2);
}

.reset-btn {
  font-size: 12px;
  font-weight: 500;
  padding: 5px 12px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: background 0.15s;
}

.reset-btn:hover {
  background: rgba(156, 163, 175, 0.1);
}

.spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(59, 130, 246, 0.3);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.validation-error {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #ef4444;
  font-size: 13px;
  padding: 8px 12px;
  border-radius: 6px;
  margin-bottom: 1rem;
}

.result-badge {
  display: inline-block;
  font-size: 13px;
  font-weight: 700;
  padding: 4px 14px;
  border-radius: 14px;
  margin-bottom: 0.75rem;
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

/* Confidence */
.confidence {
  margin-bottom: 1rem;
  font-size: 13px;
}

.confidence-label {
  color: var(--text-muted);
  font-weight: 500;
  margin-right: 6px;
}

.confidence-value {
  color: var(--text-secondary);
  font-weight: 600;
}

/* Categories */
.categories-section {
  margin-bottom: 1.5rem;
}

.categories-section h2 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 0.5rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border);
}

.pill-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.cat-pill {
  display: inline-block;
  font-size: 12px;
  font-weight: 600;
  padding: 3px 12px;
  border-radius: 12px;
  border: 1px solid;
}

.section {
  margin-bottom: 1.5rem;
}

.section h2 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 0.5rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border);
}

.section ul {
  list-style: disc;
  padding-left: 1.25rem;
  margin: 0;
}

.section li {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: 0.25rem;
}

.glue-list li {
  color: var(--design-glue, #f87171);
}

.notes-list li {
  color: var(--text-muted);
  font-style: italic;
}

/* Save to Project */
.save-section {
  margin-bottom: 1rem;
  display: flex;
  align-items: center;
  gap: 10px;
}

.save-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  padding: 6px 16px;
  border-radius: 6px;
  border: 1px solid rgba(52, 211, 153, 0.4);
  background: rgba(52, 211, 153, 0.1);
  color: #34d399;
  cursor: pointer;
  transition: background 0.15s;
}

.save-btn:hover:not(:disabled) {
  background: rgba(52, 211, 153, 0.2);
}

.save-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.save-warning {
  font-size: 13px;
  color: #fbbf24;
  background: rgba(251, 191, 36, 0.1);
  border: 1px solid rgba(251, 191, 36, 0.3);
  padding: 8px 12px;
  border-radius: 6px;
}

.save-error {
  font-size: 13px;
  color: #ef4444;
}

.save-success {
  font-size: 13px;
  font-weight: 500;
  color: #34d399;
}

.spinner.small {
  width: 12px;
  height: 12px;
  border-width: 1.5px;
}

.not-found {
  padding: 2rem;
  color: var(--text-muted);
}

/* Stale notice */
.stale-section {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 1rem;
  padding: 10px 14px;
  background: rgba(251, 191, 36, 0.08);
  border: 1px solid rgba(251, 191, 36, 0.3);
  border-radius: 6px;
}

.stale-notice {
  flex: 1;
  font-size: 13px;
  color: #fbbf24;
}

.stale-icon {
  margin-right: 6px;
}

.stale-details {
  font-weight: 500;
  margin-left: 4px;
}

.reevaluate-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  padding: 5px 14px;
  border-radius: 6px;
  border: 1px solid rgba(251, 191, 36, 0.4);
  background: rgba(251, 191, 36, 0.1);
  color: #fbbf24;
  cursor: pointer;
  transition: background 0.15s;
}

.reevaluate-btn:hover:not(:disabled) {
  background: rgba(251, 191, 36, 0.2);
}

.reevaluate-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
