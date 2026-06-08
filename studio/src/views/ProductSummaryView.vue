<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { createPmArtifact, deletePmArtifact, updatePmArtifact } from '../design/project-api'
import { requestConfirmation } from '../design/confirm'
import {
  findBusinessAreasArtifact,
  cloneProductDesignData,
  defaultProductSummaryData,
  findProductSummaryArtifact,
  isProductSummaryComplete,
  persistedPmArtifactStatus,
  PRODUCT_SUMMARY_ARTIFACT_TYPE,
  productDesignArtifactId,
  type ProductSummaryData,
} from '../design/product-design'
import { loadProject, projectStore } from '../design/project-store'
import ProjectIssueBanner from '../components/ProjectIssueBanner.vue'
import { useProjectIssue } from '../design/use-project-issue'

const route = useRoute()
const router = useRouter()

const projectId = computed(() => route.params.projectId as string)
const project = computed(() => projectStore.activeProject)
const artifact = computed(() => findProductSummaryArtifact(projectStore.artifacts.pmArtifacts))
const baseData = ref<ProductSummaryData>(defaultProductSummaryData())
const draft = ref<ProductSummaryData>(defaultProductSummaryData())
const saving = ref(false)
const deleting = ref(false)
const saveError = ref<string | null>(null)
const editing = ref(false)
const pageIssue = useProjectIssue('project-product-summary')
const readOnlyMode = computed(() => projectStore.runtimeStatus?.read_only_mode !== false)
const readOnlyReason = computed(() =>
  projectStore.runtimeStatus?.read_only_reason
  || 'Studio is running in read-only mode. Explore the design, then run Studio locally to make changes.',
)

async function ensureLoaded() {
  if (!projectId.value) return
  if (projectStore.activeProject?.id === projectId.value) return
  await loadProject(projectId.value)
}

function syncDraft() {
  const next = artifact.value?.data
    ? cloneProductDesignData(artifact.value.data as ProductSummaryData)
    : defaultProductSummaryData()
  if (!next.business_goals.length) {
    next.business_goals = ['']
  }
  if (!Array.isArray(next.supported_question_families) || !next.supported_question_families.length) {
    next.supported_question_families = ['']
  }
  if (!Array.isArray(next.multi_step_composition_rules) || !next.multi_step_composition_rules.length) {
    next.multi_step_composition_rules = ['']
  }
  next.approval_posture_summary = next.approval_posture_summary ?? ''
  baseData.value = cloneProductDesignData(next)
  draft.value = cloneProductDesignData(next)
}

onMounted(async () => {
  await ensureLoaded()
  syncDraft()
})

watch(
  () => [projectId.value, artifact.value?.updated_at] as const,
  async () => {
    await ensureLoaded()
    syncDraft()
  },
)

const hasChanges = computed(() => JSON.stringify(draft.value) !== JSON.stringify(baseData.value))
const isComplete = computed(() => isProductSummaryComplete(draft.value))
const pageHasIssue = computed(() => Boolean(pageIssue.value?.count) && !isComplete.value)
const businessAreaSuggestions = computed(() => {
  const artifact = findBusinessAreasArtifact(projectStore.artifacts.pmArtifacts)
  const entries = ((artifact?.data as { entries?: Array<{ label?: string }> } | undefined)?.entries ?? [])
  return entries
    .map((entry) => entry.label?.trim() ?? '')
    .filter((label, index, source) => label.length > 0 && source.indexOf(label) === index)
})

function missingText(value: string): boolean {
  return pageHasIssue.value && !value.trim()
}

function missingList(values: string[]): boolean {
  return pageHasIssue.value && !values.some((value) => value.trim())
}

function setGoal(index: number, value: string) {
  if (readOnlyMode.value) return
  draft.value.business_goals[index] = value
}

function setQuestionFamily(index: number, value: string) {
  if (readOnlyMode.value) return
  draft.value.supported_question_families[index] = value
}

function setCompositionRule(index: number, value: string) {
  if (readOnlyMode.value) return
  draft.value.multi_step_composition_rules[index] = value
}

function addGoal() {
  if (readOnlyMode.value) return
  draft.value.business_goals.push('')
}

function addQuestionFamily() {
  if (readOnlyMode.value) return
  draft.value.supported_question_families.push('')
}

function addSuggestedQuestionFamily(value: string) {
  if (readOnlyMode.value) return
  if (!value.trim()) return
  if (draft.value.supported_question_families.some((item) => item.trim().toLowerCase() === value.trim().toLowerCase())) return
  if (draft.value.supported_question_families.length === 1 && !draft.value.supported_question_families[0].trim()) {
    draft.value.supported_question_families[0] = value
    return
  }
  draft.value.supported_question_families.push(value)
}

function addCompositionRule() {
  if (readOnlyMode.value) return
  draft.value.multi_step_composition_rules.push('')
}

function removeGoal(index: number) {
  if (readOnlyMode.value) return
  draft.value.business_goals.splice(index, 1)
  if (!draft.value.business_goals.length) {
    draft.value.business_goals.push('')
  }
}

function removeQuestionFamily(index: number) {
  if (readOnlyMode.value) return
  draft.value.supported_question_families.splice(index, 1)
  if (!draft.value.supported_question_families.length) {
    draft.value.supported_question_families.push('')
  }
}

function removeCompositionRule(index: number) {
  if (readOnlyMode.value) return
  draft.value.multi_step_composition_rules.splice(index, 1)
  if (!draft.value.multi_step_composition_rules.length) {
    draft.value.multi_step_composition_rules.push('')
  }
}

function startEditing() {
  if (readOnlyMode.value) return
  editing.value = true
}

function discardChanges() {
  draft.value = cloneProductDesignData(baseData.value)
  editing.value = false
}

async function save() {
  if (readOnlyMode.value || !project.value) return
  saving.value = true
  saveError.value = null
  try {
    const payload: ProductSummaryData = {
      ...cloneProductDesignData(draft.value),
      artifact_type: PRODUCT_SUMMARY_ARTIFACT_TYPE,
      business_goals: draft.value.business_goals.map((item) => item.trim()).filter(Boolean),
      supported_question_families: draft.value.supported_question_families.map((item) => item.trim()).filter(Boolean),
      multi_step_composition_rules: draft.value.multi_step_composition_rules.map((item) => item.trim()).filter(Boolean),
    }
    if (!payload.business_goals.length) {
      payload.business_goals = ['']
    }
    if (!payload.supported_question_families.length) {
      payload.supported_question_families = ['']
    }
    if (!payload.multi_step_composition_rules.length) {
      payload.multi_step_composition_rules = ['']
    }

    if (artifact.value) {
      await updatePmArtifact(project.value.id, artifact.value.id, {
        title: 'Business Summary',
        status: persistedPmArtifactStatus(isProductSummaryComplete(payload)),
        data: payload,
      })
    } else {
      await createPmArtifact(project.value.id, {
        id: productDesignArtifactId(project.value.id, PRODUCT_SUMMARY_ARTIFACT_TYPE),
        title: 'Business Summary',
        data: payload,
      })
    }
    await loadProject(project.value.id)
    editing.value = false
  } catch (err) {
    saveError.value = err instanceof Error ? err.message : String(err)
  } finally {
    saving.value = false
  }
}

async function removeArtifact() {
  if (readOnlyMode.value || !project.value || !artifact.value) return
  const confirmed = await requestConfirmation({
    title: 'Delete Business Summary?',
    message: 'This removes the saved Product Design business summary from the project.',
    confirmLabel: 'Delete Summary',
    cancelLabel: 'Cancel',
    tone: 'danger',
  })
  if (!confirmed) return
  deleting.value = true
  try {
    await deletePmArtifact(project.value.id, artifact.value.id)
    await loadProject(project.value.id)
    editing.value = false
  } finally {
    deleting.value = false
  }
}
</script>

<template>
  <div class="product-editor">
    <template v-if="project">
      <section class="page-header">
        <button class="back-link" type="button" @click="router.push(`/design/projects/${project.id}/pm`)">
          &larr; Back to Product Overview
        </button>
        <div class="page-kicker">Product Design</div>
        <h1>Business Summary</h1>
        <p>
          Capture the product-level framing PM and business stakeholders expect to survive the rest of the Studio flow:
          why this system exists, what problem it solves, what governed behavior matters, and what success looks like.
        </p>
      </section>

      <ProjectIssueBanner :issue="pageIssue" title="Business Summary diagnostics" />

      <div v-if="saveError" class="banner banner-error">{{ saveError }}</div>
      <div v-if="readOnlyMode" class="banner banner-warning readonly-banner">{{ readOnlyReason }}</div>

      <section class="panel" :class="{ 'field-error-card': pageHasIssue }">
        <div class="panel-header">
          <div>
            <h2>Business Framing</h2>
            <p class="panel-copy">
              This page stays in PM language. It should define intent and outcomes, not technical contracts.
            </p>
          </div>
          <div class="actions">
            <button v-if="!editing" class="btn btn-secondary" type="button" :disabled="readOnlyMode" @click="startEditing">
              {{ artifact ? 'Edit Summary' : 'Add Summary' }}
            </button>
            <button v-if="editing" class="btn btn-secondary" :disabled="!hasChanges" @click="discardChanges">Discard Changes</button>
            <button v-if="editing" class="btn btn-secondary" :disabled="readOnlyMode || !artifact || deleting" @click="removeArtifact">
              {{ deleting ? 'Deleting...' : 'Delete' }}
            </button>
            <button v-if="editing" class="btn btn-primary" :disabled="readOnlyMode || saving" @click="save">
              {{ saving ? 'Saving...' : 'Save to Project' }}
            </button>
          </div>
        </div>

        <div v-if="!editing && artifact" class="summary-grid">
          <article class="summary-card summary-card-wide">
            <span>Product Purpose</span>
            <p>{{ baseData.product_purpose || 'Not captured' }}</p>
          </article>
          <article class="summary-card summary-card-wide">
            <span>Business Problem</span>
            <p>{{ baseData.business_problem || 'Not captured' }}</p>
          </article>
          <article class="summary-card">
            <span>Business Goals</span>
            <strong>{{ baseData.business_goals.filter(Boolean).length }}</strong>
            <details class="view-details">
              <summary>View goals</summary>
              <ul class="detail-list">
                <li v-for="goal in baseData.business_goals.filter(Boolean)" :key="goal">{{ goal }}</li>
                <li v-if="!baseData.business_goals.filter(Boolean).length">Not captured</li>
              </ul>
            </details>
          </article>
          <article class="summary-card">
            <span>Question Families</span>
            <strong>{{ baseData.supported_question_families.filter(Boolean).length }}</strong>
            <details class="view-details">
              <summary>View question families</summary>
              <ul class="detail-list">
                <li v-for="family in baseData.supported_question_families.filter(Boolean)" :key="family">{{ family }}</li>
                <li v-if="!baseData.supported_question_families.filter(Boolean).length">Not captured</li>
              </ul>
            </details>
          </article>
          <article class="summary-card summary-card-wide">
            <span>Governed Behavior</span>
            <p>{{ baseData.governed_behavior_summary || 'Not captured' }}</p>
          </article>
          <article class="summary-card summary-card-wide">
            <span>Approval Posture</span>
            <p>{{ baseData.approval_posture_summary || 'Not captured' }}</p>
          </article>
          <article class="summary-card summary-card-wide">
            <span>All Saved Values</span>
            <details class="view-details">
              <summary>View complete business summary</summary>
              <div class="detail-grid">
                <div class="detail-wide"><span>Product Purpose</span><p>{{ baseData.product_purpose || 'Not captured' }}</p></div>
                <div class="detail-wide"><span>Business Problem</span><p>{{ baseData.business_problem || 'Not captured' }}</p></div>
                <div class="detail-wide"><span>Governed Behavior Summary</span><p>{{ baseData.governed_behavior_summary || 'Not captured' }}</p></div>
                <div class="detail-wide"><span>Approval Posture Summary</span><p>{{ baseData.approval_posture_summary || 'Not captured' }}</p></div>
                <div class="detail-wide"><span>Why Now</span><p>{{ baseData.why_now || 'Not captured' }}</p></div>
                <div class="detail-wide"><span>Success Outcome Summary</span><p>{{ baseData.success_outcome_summary || 'Not captured' }}</p></div>
                <div class="detail-wide">
                  <span>Multi-Step Composition Rules</span>
                  <ul class="detail-list">
                    <li v-for="rule in baseData.multi_step_composition_rules.filter(Boolean)" :key="rule">{{ rule }}</li>
                    <li v-if="!baseData.multi_step_composition_rules.filter(Boolean).length">Not captured</li>
                  </ul>
                </div>
              </div>
            </details>
          </article>
        </div>

        <div v-else-if="!editing" class="empty-editor-state">
          <strong>No business summary saved yet.</strong>
          <p>Create one when you are ready to capture PM-owned intent and outcomes.</p>
        </div>

        <div v-else class="field-grid">
          <label class="field field-full" :class="{ 'field-error': missingText(draft.product_purpose) }">
            <span class="field-label">Product Purpose</span>
            <span class="field-help">Describe what this product or agent is for in one clear paragraph.</span>
            <textarea v-model="draft.product_purpose" class="field-input textarea" rows="4" />
            <small v-if="missingText(draft.product_purpose)" class="field-error-copy">Product purpose is required.</small>
          </label>

          <label class="field field-full" :class="{ 'field-error': missingText(draft.business_problem) }">
            <span class="field-label">Business Problem</span>
            <span class="field-help">State the core business pain or operating gap this product is meant to address.</span>
            <textarea v-model="draft.business_problem" class="field-input textarea" rows="4" />
            <small v-if="missingText(draft.business_problem)" class="field-error-copy">Business problem is required.</small>
          </label>

          <div class="field field-full" :class="{ 'field-error': missingList(draft.business_goals) }">
            <span class="field-label">Business Goals</span>
            <span class="field-help">List the goals PM and business stakeholders expect the product to achieve.</span>
            <div class="list-stack">
              <div v-for="(goal, index) in draft.business_goals" :key="index" class="list-row">
                <input :value="goal" class="field-input" type="text" @input="setGoal(index, ($event.target as HTMLInputElement).value)" />
                <button class="btn btn-tertiary" type="button" :disabled="readOnlyMode" @click="removeGoal(index)">Remove</button>
              </div>
            </div>
            <button class="btn btn-secondary" type="button" :disabled="readOnlyMode" @click="addGoal">Add Goal</button>
            <small v-if="missingList(draft.business_goals)" class="field-error-copy">At least one business goal is required.</small>
          </div>

          <div class="field field-full" :class="{ 'field-error': missingList(draft.supported_question_families) }">
            <span class="field-label">Supported Question Families</span>
            <span class="field-help">Use human-readable labels, not technical ids. These are PM-facing question families such as “Pipeline and Forecast” or “Risk and Account Review”.</span>
            <div v-if="businessAreaSuggestions.length" class="suggestion-row">
              <button
                v-for="suggestion in businessAreaSuggestions"
                :key="suggestion"
                class="suggestion-chip"
                type="button"
                :disabled="readOnlyMode"
                @click="addSuggestedQuestionFamily(suggestion)"
              >
                Add {{ suggestion }}
              </button>
            </div>
            <div class="list-stack">
              <div v-for="(item, index) in draft.supported_question_families" :key="`question-${index}`" class="list-row">
                <input :value="item" class="field-input" type="text" placeholder="e.g. Pipeline and Forecast" @input="setQuestionFamily(index, ($event.target as HTMLInputElement).value)" />
                <button class="btn btn-tertiary" type="button" :disabled="readOnlyMode" @click="removeQuestionFamily(index)">Remove</button>
              </div>
            </div>
            <button class="btn btn-secondary" type="button" :disabled="readOnlyMode" @click="addQuestionFamily">Add Question Family</button>
            <small v-if="missingList(draft.supported_question_families)" class="field-error-copy">At least one supported question family is required.</small>
          </div>

          <label class="field field-full" :class="{ 'field-error': missingText(draft.governed_behavior_summary) }">
            <span class="field-label">Governed Behavior Summary</span>
            <span class="field-help">Summarize the important approval, denial, restriction, masking, or clarification behavior the product must preserve.</span>
            <textarea v-model="draft.governed_behavior_summary" class="field-input textarea" rows="4" />
            <small v-if="missingText(draft.governed_behavior_summary)" class="field-error-copy">Governed behavior summary is required.</small>
          </label>

          <label class="field field-full" :class="{ 'field-error': missingText(draft.approval_posture_summary) }">
            <span class="field-label">Approval Posture Summary</span>
            <span class="field-help">Describe when the product should proceed directly, when it should stop for approval, and how that boundary should be understood in business terms.</span>
            <textarea v-model="draft.approval_posture_summary" class="field-input textarea" rows="4" />
            <small v-if="missingText(draft.approval_posture_summary)" class="field-error-copy">Approval posture summary is required.</small>
          </label>

          <div class="field field-full">
            <span class="field-label">Multi-Step Composition Rules</span>
            <span class="field-help">List the important business rules for compound or cross-service flows, especially where work should stop, clarify, or hand off.</span>
            <div class="list-stack">
              <div v-for="(item, index) in draft.multi_step_composition_rules" :key="`composition-${index}`" class="list-row">
                <input :value="item" class="field-input" type="text" @input="setCompositionRule(index, ($event.target as HTMLInputElement).value)" />
                <button class="btn btn-tertiary" type="button" :disabled="readOnlyMode" @click="removeCompositionRule(index)">Remove</button>
              </div>
            </div>
            <button class="btn btn-secondary" type="button" :disabled="readOnlyMode" @click="addCompositionRule">Add Composition Rule</button>
          </div>

          <label class="field">
            <span class="field-label">Why Now</span>
            <span class="field-help">Record the timing, business pressure, or organizational reason this work matters now.</span>
            <textarea v-model="draft.why_now" class="field-input textarea" rows="4" />
          </label>

          <label class="field">
            <span class="field-label">Success Outcome Summary</span>
            <span class="field-help">Describe the outcome the business expects if this product works as intended.</span>
            <textarea v-model="draft.success_outcome_summary" class="field-input textarea" rows="4" />
          </label>
        </div>

        <div class="status-row">
          <span class="status-pill" :class="{ ready: isComplete }">{{ isComplete ? 'Ready' : 'Needs PM input' }}</span>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.product-editor {
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
  margin-bottom: 0.4rem;
}

.page-header h1 {
  margin: 0 0 0.5rem;
  font-size: 32px;
  line-height: 1.15;
  font-weight: 700;
  color: var(--text-primary);
}

.page-header p {
  max-width: 78ch;
  color: var(--text-secondary);
  line-height: 1.6;
}

.back-link {
  margin-bottom: 0.9rem;
  border: none;
  background: transparent;
  color: var(--accent);
  padding: 0;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
}

.back-link:hover {
  color: var(--accent-hover);
}

.panel {
  background: var(--surface-depth-panel);
  border: 1px solid var(--surface-border-panel);
  border-radius: 22px;
  padding: 1.35rem;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 1.35rem;
}

.panel-header h2 {
  margin: 0;
  font-size: 20px;
  line-height: 1.25;
}

.panel-copy {
  margin: 0.5rem 0 0;
  color: var(--text-secondary);
  line-height: 1.6;
  max-width: 72ch;
}

.actions {
  display: flex;
  flex-wrap: nowrap;
  gap: 0.75rem;
  justify-content: flex-end;
  align-items: center;
  white-space: nowrap;
}

.actions .btn,
.field > .btn {
  width: auto;
  max-width: max-content;
  align-self: flex-start;
  justify-self: flex-start;
}

.field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1.05rem;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}

.summary-card,
.empty-editor-state {
  border: 1px solid var(--surface-border-card);
  border-radius: 16px;
  background: var(--surface-depth-card);
  padding: 1rem;
}

.summary-card-wide {
  grid-column: 1 / -1;
}

.summary-card span {
  display: block;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.05em;
  margin-bottom: 0.4rem;
  text-transform: uppercase;
}

.summary-card strong {
  color: var(--text-primary);
  font-size: 20px;
}

.summary-card p,
.empty-editor-state p {
  color: var(--text-secondary);
  line-height: 1.55;
  margin: 0;
}

.view-details {
  border-top: 1px solid rgba(148, 163, 184, 0.12);
  margin-top: 0.85rem;
  padding-top: 0.75rem;
}

.view-details summary {
  color: #bfdbfe;
  cursor: pointer;
  font-size: 13px;
  font-weight: 800;
}

.detail-grid {
  display: grid;
  gap: 0.75rem;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin-top: 0.85rem;
}

.detail-grid > div {
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  background: var(--surface-depth-inset);
  padding: 0.75rem;
}

.detail-wide {
  grid-column: 1 / -1;
}

.detail-grid span {
  color: var(--text-secondary);
  display: block;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.06em;
  margin-bottom: 0.35rem;
  text-transform: uppercase;
}

.detail-grid p,
.detail-list {
  color: var(--text-primary);
  line-height: 1.5;
  margin: 0;
}

.detail-list {
  padding-left: 1rem;
}

.detail-list li + li {
  margin-top: 0.35rem;
}

.empty-editor-state strong {
  color: var(--text-primary);
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  min-width: 0;
}

.field-full {
  grid-column: 1 / -1;
}

.field-label {
  font-size: 0.92rem;
  font-weight: 700;
  color: var(--text-primary);
}

.field-help {
  color: var(--text-secondary);
  font-size: 0.84rem;
  line-height: 1.5;
}

.field-input {
  width: 100%;
  min-width: 0;
  max-width: 100%;
  box-sizing: border-box;
  border-radius: 12px;
  border: 1px solid var(--surface-border-card);
  background: var(--surface-depth-card);
  color: var(--text-primary);
  padding: 0.78rem 0.9rem;
  font: inherit;
  line-height: 1.45;
}

.textarea {
  resize: vertical;
}

.list-stack {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin: 0.35rem 0 0.9rem;
}

.suggestion-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
  margin: 0.35rem 0 0.9rem;
}

.suggestion-chip {
  border: 1px solid rgba(96, 165, 250, 0.24);
  background: rgba(30, 41, 59, 0.55);
  color: #bfdbfe;
  border-radius: 999px;
  padding: 0.42rem 0.78rem;
  cursor: pointer;
  font: inherit;
  font-size: 12px;
  font-weight: 700;
}

.suggestion-chip:hover {
  background: rgba(30, 64, 175, 0.22);
  border-color: rgba(147, 197, 253, 0.42);
}

.list-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 0.75rem;
  align-items: center;
}

.list-row .btn {
  width: auto;
  max-width: max-content;
  justify-self: end;
}

.status-row {
  margin-top: 1.25rem;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  padding: 0.35rem 0.7rem;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.15);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
}

.status-pill.ready {
  background: rgba(16, 185, 129, 0.16);
  color: #86efac;
}

.btn {
  min-height: 38px;
  border-radius: 12px;
  font-weight: 700;
}

.btn-secondary {
  background: var(--surface-depth-card);
  color: #dbeafe;
  border-color: rgba(96, 165, 250, 0.24);
}

.btn-secondary:hover:not(:disabled) {
  background: rgba(30, 64, 175, 0.22);
  border-color: rgba(147, 197, 253, 0.42);
}

.btn-tertiary {
  background: var(--surface-depth-card);
  border-color: rgba(148, 163, 184, 0.18);
  color: var(--text-secondary);
}

@media (max-width: 900px) {
  .field-grid,
  .summary-grid,
  .detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>
<style scoped src="./product-inline-errors.css"></style>
