<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useDeveloperDefinitionEditor } from '../design/use-developer-definition-editor'
import ProjectIssueBanner from '../components/ProjectIssueBanner.vue'
import { useProjectIssue } from '../design/use-project-issue'
import { useDeveloperIssueTargets } from '../design/use-developer-issue-targets'
import { projectStore } from '../design/project-store'

const router = useRouter()
const editing = ref(false)
const pageIssue = useProjectIssue('project-developer-verification-expectations')
const {
  project,
  baseline,
  baselineAligned,
  definition,
  serviceOptions,
  toggleVerificationTargetService,
  saveDraft,
  resetDefinition,
  saving,
  saveError,
} = useDeveloperDefinitionEditor()
const {
  messagesForPath,
  messagesForPrefix,
  hasIssueForPath,
  hasIssueForPrefix,
} = useDeveloperIssueTargets({ definition, project })

const readOnlyMode = computed(() => projectStore.runtimeStatus?.read_only_mode !== false)
const readOnlyReason = computed(() =>
  projectStore.runtimeStatus?.read_only_reason
  || 'Studio is running in read-only mode. Explore the design, then download and run Studio locally to make changes.',
)

watch(readOnlyMode, (readOnly) => {
  if (readOnly) editing.value = false
})

function verificationPath(collection: string, id: string, field: string): string {
  return `verification.${collection}.${id}.${field}`
}

function verificationItemHasIssue(collection: string, id: string): boolean {
  return hasIssueForPrefix(`verification.${collection}.${id}`)
}

function enterEdit() {
  if (readOnlyMode.value) return
  editing.value = true
}

function cancelEdit() {
  if (readOnlyMode.value) return
  resetDefinition()
  editing.value = false
}

async function saveEdit() {
  if (readOnlyMode.value) return
  await saveDraft()
  if (!saveError.value) editing.value = false
}
</script>

<template>
  <div class="developer-definition verification-expectations-page">
    <template v-if="project">
      <section class="page-header">
        <button class="back-link" type="button" @click="router.push(`/design/projects/${project.id}/developer`)">
          &larr; Back to Developer Design
        </button>
        <div class="page-kicker">Developer Design</div>
        <h1>Evidence & Verification Plan</h1>
        <p>
          Developers define how locked PM goals, non-goals, question families, and success conditions will be proven.
          PMs confirm this plan from PM Review; this page authors the delivery evidence plan.
        </p>
      </section>
      <div v-if="readOnlyMode" class="banner banner-warning readonly-banner">
        {{ readOnlyReason }}
      </div>
      <ProjectIssueBanner :issue="pageIssue" title="Evidence & Verification Plan diagnostics" />
      <section v-if="!baseline" class="panel empty-panel">
        <h2>Developer baseline is not locked</h2>
        <p>Return to Developer Overview and lock Product Design before defining evidence and verification planning.</p>
      </section>

      <section v-else-if="!baselineAligned" class="panel empty-panel">
        <h2>Locked baseline is out of sync</h2>
        <p>Product Design changed after the current developer baseline was locked. Re-lock the baseline before continuing.</p>
      </section>

      <section v-else-if="definition" class="grid verification-layout" :class="{ 'review-mode': !editing, 'edit-mode': editing }">
        <article class="panel panel-full verification-contract-panel">
          <div class="panel-header">
            <div>
              <h2>Evidence Plan</h2>
              <p class="panel-copy compact-copy">
                These rows define planned proof. They do not verify the system by themselves; verification evidence is attached later through generation runs, evaluator results, registry/package checks, simulator reports, and observed service metadata.
              </p>
            </div>
            <div class="header-actions">
              <button v-if="!editing" class="btn btn-secondary" type="button" :disabled="readOnlyMode" @click="enterEdit">
                Edit Plan
              </button>
              <button v-if="editing" class="btn btn-secondary" type="button" :disabled="readOnlyMode || saving" @click="cancelEdit">
                Cancel
              </button>
              <button v-if="editing" class="btn btn-primary" :disabled="readOnlyMode || saving" @click="saveEdit">
                {{ saving ? 'Saving…' : 'Save Plan' }}
              </button>
            </div>
          </div>
          <p v-if="saveError" class="error">{{ saveError }}</p>
        </article>

        <article id="verification-question-families" class="panel panel-full">
          <div class="panel-header">
            <div>
              <h2>Supported Question Families</h2>
              <p class="panel-copy">
                Each family should map to the services that must support it and the evidence that will prove support still
                exists after generation and implementation changes.
              </p>
            </div>
          </div>
          <div v-if="definition.verification.supported_question_family_bindings.length" class="verification-list">
            <div
              v-for="binding in definition.verification.supported_question_family_bindings"
              :key="binding.id"
              class="verification-card"
              :class="{ 'field-error-card': verificationItemHasIssue('supported_question_family_bindings', binding.id) }"
            >
              <div class="verification-head">
                <h3>{{ binding.question_family }}</h3>
                <p
                  v-for="message in messagesForPrefix(`verification.supported_question_family_bindings.${binding.id}`)"
                  :key="message"
                  class="inline-field-error"
                >
                  {{ message }}
                </p>
              </div>
              <div class="review-summary-grid review-only">
                <div class="review-summary-card"><strong>Target Services</strong><span>{{ binding.target_service_ids.length }}</span></div>
                <div class="review-summary-card"><strong>Evidence Signal</strong><span>{{ binding.evidence_signal || 'Not set' }}</span></div>
                <div class="review-summary-card field-wide"><strong>Verification Strategy</strong><p>{{ binding.verification_strategy || 'Not formalized yet.' }}</p></div>
              </div>
              <div class="settings-grid edit-only">
                <div class="field field-wide" :class="{ 'field-error': hasIssueForPath(verificationPath('supported_question_family_bindings', binding.id, 'target_service_ids')) }">
                  <span class="summary-label required-label">Target Services</span>
                  <div class="chip-grid">
                    <button
                      v-for="service in serviceOptions"
                      :key="service.id"
                      type="button"
                      class="chip"
                      :class="{ active: binding.target_service_ids.includes(service.id) }"
                      :disabled="readOnlyMode"
                      @click="toggleVerificationTargetService('supported_question_family_bindings', binding.id, service.id)"
                    >
                      {{ service.label }}
                    </button>
                  </div>
                  <p class="hint">Select the services that must expose or preserve this supported question family.</p>
                  <small v-for="message in messagesForPath(verificationPath('supported_question_family_bindings', binding.id, 'target_service_ids'))" :key="message" class="field-error-copy">{{ message }}</small>
                </div>
                <label class="field" :class="{ 'field-error': hasIssueForPath(verificationPath('supported_question_family_bindings', binding.id, 'verification_strategy')) }">
                  <span class="summary-label required-label">Verification Strategy</span>
                  <textarea
                    v-model="binding.verification_strategy"
                    class="textarea"
                    rows="3"
                    placeholder="Describe how verification should prove this question family is still supported."
                    :disabled="readOnlyMode"
                  />
                  <small v-for="message in messagesForPath(verificationPath('supported_question_family_bindings', binding.id, 'verification_strategy'))" :key="message" class="field-error-copy">{{ message }}</small>
                </label>
                <label class="field">
                  <span class="summary-label">Evidence Signal</span>
                  <input
                    v-model="binding.evidence_signal"
                    class="input"
                    type="text"
                    placeholder="Observed capability, evaluation case, runtime metadata, regression pack, etc."
                    :disabled="readOnlyMode"
                  />
                </label>
              </div>
            </div>
          </div>
          <p v-else class="panel-copy">No supported question families are defined on the locked Product Design baseline.</p>
        </article>

        <article id="verification-business-goals" class="panel panel-full">
          <div class="panel-header">
            <div>
              <h2>Business Goal Coverage</h2>
              <p class="panel-copy">
                Each business goal should have a concrete verification strategy. This is how PM intent becomes something
                delivery can actually prove.
              </p>
            </div>
          </div>
          <div v-if="definition.verification.business_goal_bindings.length" class="verification-list">
            <div
              v-for="binding in definition.verification.business_goal_bindings"
              :key="binding.id"
              class="verification-card"
              :class="{ 'field-error-card': verificationItemHasIssue('business_goal_bindings', binding.id) }"
            >
              <div class="verification-head">
                <h3>{{ binding.business_goal }}</h3>
                <p
                  v-for="message in messagesForPrefix(`verification.business_goal_bindings.${binding.id}`)"
                  :key="message"
                  class="inline-field-error"
                >
                  {{ message }}
                </p>
              </div>
              <div class="review-summary-grid review-only">
                <div class="review-summary-card"><strong>Target Services</strong><span>{{ binding.target_service_ids.length }}</span></div>
                <div class="review-summary-card"><strong>Evidence Signal</strong><span>{{ binding.evidence_signal || 'Not set' }}</span></div>
                <div class="review-summary-card field-wide"><strong>Verification Strategy</strong><p>{{ binding.verification_strategy || 'Not formalized yet.' }}</p></div>
              </div>
              <div class="settings-grid edit-only">
                <div class="field field-wide" :class="{ 'field-error': hasIssueForPath(verificationPath('business_goal_bindings', binding.id, 'target_service_ids')) }">
                  <span class="summary-label required-label">Target Services</span>
                  <div class="chip-grid">
                    <button
                      v-for="service in serviceOptions"
                      :key="service.id"
                      type="button"
                      class="chip"
                      :class="{ active: binding.target_service_ids.includes(service.id) }"
                      :disabled="readOnlyMode"
                      @click="toggleVerificationTargetService('business_goal_bindings', binding.id, service.id)"
                    >
                      {{ service.label }}
                    </button>
                  </div>
                  <p class="hint">Select the services that materially contribute to this business goal.</p>
                  <small v-for="message in messagesForPath(verificationPath('business_goal_bindings', binding.id, 'target_service_ids'))" :key="message" class="field-error-copy">{{ message }}</small>
                </div>
                <label class="field" :class="{ 'field-error': hasIssueForPath(verificationPath('business_goal_bindings', binding.id, 'verification_strategy')) }">
                  <span class="summary-label required-label">Verification Strategy</span>
                  <textarea
                    v-model="binding.verification_strategy"
                    class="textarea"
                    rows="3"
                    placeholder="Describe how evaluation or runtime evidence should show this goal is being satisfied."
                    :disabled="readOnlyMode"
                  />
                  <small v-for="message in messagesForPath(verificationPath('business_goal_bindings', binding.id, 'verification_strategy'))" :key="message" class="field-error-copy">{{ message }}</small>
                </label>
                <label class="field">
                  <span class="summary-label">Evidence Signal</span>
                  <input
                    v-model="binding.evidence_signal"
                    class="input"
                    type="text"
                    placeholder="Named evaluation, KPI, audit trail, runtime outcome, etc."
                    :disabled="readOnlyMode"
                  />
                </label>
              </div>
            </div>
          </div>
          <p v-else class="panel-copy">No business goals are defined on the locked Product Design baseline.</p>
        </article>

        <article id="verification-non-goals" class="panel panel-full">
          <div class="panel-header">
            <div>
              <h2>Non-Goal Guards</h2>
              <p class="panel-copy">
                Non-goals need explicit guard strategies so scope does not silently expand during generation or manual implementation.
              </p>
            </div>
          </div>
          <div v-if="definition.verification.non_goal_guards.length" class="verification-list">
            <div
              v-for="guard in definition.verification.non_goal_guards"
              :key="guard.id"
              class="verification-card"
              :class="{ 'field-error-card': verificationItemHasIssue('non_goal_guards', guard.id) }"
            >
              <div class="verification-head">
                <h3>{{ guard.non_goal }}</h3>
                <p
                  v-for="message in messagesForPrefix(`verification.non_goal_guards.${guard.id}`)"
                  :key="message"
                  class="inline-field-error"
                >
                  {{ message }}
                </p>
              </div>
              <div class="review-summary-grid review-only">
                <div class="review-summary-card"><strong>Evidence Signal</strong><span>{{ guard.evidence_signal || 'Not set' }}</span></div>
                <div class="review-summary-card field-wide"><strong>Guard Strategy</strong><p>{{ guard.guard_strategy || 'Not formalized yet.' }}</p></div>
              </div>
              <div class="settings-grid edit-only">
                <label class="field" :class="{ 'field-error': hasIssueForPath(verificationPath('non_goal_guards', guard.id, 'guard_strategy')) }">
                  <span class="summary-label required-label">Guard Strategy</span>
                  <textarea
                    v-model="guard.guard_strategy"
                    class="textarea"
                    rows="3"
                    placeholder="Describe the technical guard, refusal path, omitted scaffold, or verification check that preserves this non-goal."
                    :disabled="readOnlyMode"
                  />
                  <small v-for="message in messagesForPath(verificationPath('non_goal_guards', guard.id, 'guard_strategy'))" :key="message" class="field-error-copy">{{ message }}</small>
                </label>
                <label class="field" :class="{ 'field-error': hasIssueForPath(verificationPath('non_goal_guards', guard.id, 'evidence_signal')) }">
                  <span class="summary-label required-label">Evidence Signal</span>
                  <input
                    v-model="guard.evidence_signal"
                    class="input"
                    type="text"
                    placeholder="Policy check, missing capability by design, negative regression, runtime denial, etc."
                    :disabled="readOnlyMode"
                  />
                  <small v-for="message in messagesForPath(verificationPath('non_goal_guards', guard.id, 'evidence_signal'))" :key="message" class="field-error-copy">{{ message }}</small>
                </label>
              </div>
            </div>
          </div>
          <p v-else class="panel-copy">No non-goals are defined on the locked Product Design baseline.</p>
        </article>

        <article id="verification-success-criteria" class="panel panel-full">
          <div class="panel-header">
            <div>
              <h2>Success Criteria Evidence</h2>
              <p class="panel-copy">
                Success criteria already define business-facing evidence. This page adds the technical verification strategy that
                should produce or collect that evidence.
              </p>
            </div>
          </div>
          <div v-if="definition.verification.success_criteria_checks.length" class="verification-list">
            <div
              v-for="check in definition.verification.success_criteria_checks"
              :key="check.id"
              class="verification-card"
              :class="{ 'field-error-card': verificationItemHasIssue('success_criteria_checks', check.id) }"
            >
              <div class="verification-head">
                <h3>{{ check.success_criterion }}</h3>
                <p
                  v-for="message in messagesForPrefix(`verification.success_criteria_checks.${check.id}`)"
                  :key="message"
                  class="inline-field-error"
                >
                  {{ message }}
                </p>
              </div>
              <div class="review-summary-grid review-only">
                <div class="review-summary-card"><strong>PM Review Method</strong><span>{{ check.review_method || 'Not specified' }}</span></div>
                <div class="review-summary-card field-wide"><strong>PM Evidence Expectation</strong><p>{{ check.evidence_expectation || 'No explicit PM evidence expectation recorded.' }}</p></div>
                <div class="review-summary-card field-wide"><strong>Technical Verification Strategy</strong><p>{{ check.verification_strategy || 'Not formalized yet.' }}</p></div>
              </div>
              <div class="settings-grid edit-only">
                <label class="field">
                  <span class="summary-label">PM Evidence Expectation</span>
                  <textarea
                    :value="check.evidence_expectation || 'No explicit PM evidence expectation recorded.'"
                    class="textarea"
                    rows="3"
                    readonly
                  />
                </label>
                <label class="field">
                  <span class="summary-label">PM Review Method</span>
                  <input
                    :value="check.review_method || 'Not specified'"
                    class="input"
                    type="text"
                    readonly
                  />
                </label>
                <label class="field field-wide" :class="{ 'field-error': hasIssueForPath(verificationPath('success_criteria_checks', check.id, 'technical_verification_strategy')) }">
                  <span class="summary-label required-label">Technical Verification Strategy</span>
                  <textarea
                    v-model="check.verification_strategy"
                    class="textarea"
                    rows="3"
                    placeholder="Describe how verification or CI should produce evidence for this success criterion."
                    :disabled="readOnlyMode"
                  />
                  <small v-for="message in messagesForPath(verificationPath('success_criteria_checks', check.id, 'technical_verification_strategy'))" :key="message" class="field-error-copy">{{ message }}</small>
                </label>
              </div>
            </div>
          </div>
          <p v-else class="panel-copy">No success criteria are defined on the locked Product Design baseline.</p>
        </article>

      </section>
    </template>
  </div>
</template>

<style scoped src="./developer-definition-shared.css"></style>
<style scoped>
.verification-expectations-page .page-header {
  max-width: 1040px;
}

.verification-layout {
  align-items: start;
}

.verification-expectations-page .panel-header h2,
.verification-expectations-page .verification-head h3 {
  margin: 0;
}

.readonly-banner {
  margin: 0 0 1rem;
}

.verification-expectations-page .btn:disabled,
.verification-expectations-page .chip:disabled,
.verification-expectations-page .input:disabled,
.verification-expectations-page .textarea:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.compact-copy {
  margin: 0.35rem 0 0;
}

.verification-expectations-page .header-actions {
  flex: 0 0 auto;
  justify-content: flex-end;
}

.verification-expectations-page .btn {
  width: auto;
  white-space: nowrap;
}

.verification-contract-panel {
  background:
    radial-gradient(circle at top left, rgba(59, 130, 246, 0.14), transparent 32%),
    rgba(15, 23, 42, 0.46);
}

.verification-expectations-page article.panel-full + article.panel-full {
  margin-top: 0.15rem;
}

.verification-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  margin-top: 1rem;
}

.verification-card {
  border: 1px solid var(--surface-border-card);
  border-radius: 18px;
  padding: 1rem;
  background:
    linear-gradient(180deg, rgba(15, 23, 42, 0.38), rgba(15, 23, 42, 0.22));
}

.verification-card.field-error-card {
  border-color: rgba(248, 113, 113, 0.66);
  background:
    linear-gradient(135deg, rgba(127, 29, 29, 0.26), rgba(15, 23, 42, 0.28)),
    rgba(15, 23, 42, 0.24);
  box-shadow: 0 0 0 1px rgba(248, 113, 113, 0.18), 0 18px 40px rgba(127, 29, 29, 0.12);
}

.verification-card .review-summary-grid {
  grid-template-columns: 1fr;
}

.verification-card .review-summary-card,
.verification-card .review-summary-card.field-wide {
  grid-column: 1 / -1;
}

.verification-head {
  margin-bottom: 1rem;
  padding-bottom: 0.85rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.13);
}

.verification-head h3 {
  max-width: 1040px;
  color: var(--text-primary);
  font-size: 18px;
  line-height: 1.35;
}

.verification-expectations-page .settings-grid {
  gap: 1rem;
}

.verification-expectations-page .field {
  border: 1px solid var(--surface-border-card);
  border-radius: 16px;
  padding: 0.95rem;
  background: var(--surface-depth-card);
}

.verification-expectations-page .field > .summary-label {
  margin-bottom: 0.35rem;
}

.verification-expectations-page .hint {
  margin: 0.25rem 0 0;
}

.verification-expectations-page .textarea[readonly],
.verification-expectations-page .input[readonly] {
  color: var(--text-secondary);
  background: var(--surface-depth-card);
  border-color: rgba(148, 163, 184, 0.14);
}

.verification-expectations-page .chip-grid {
  gap: 0.6rem;
}

.verification-expectations-page .chip {
  padding: 0.45rem 0.85rem;
  border-radius: 999px;
}

@media (max-width: 960px) {
  .verification-expectations-page .panel-header {
    flex-direction: column;
    align-items: stretch;
  }

  .verification-expectations-page .header-actions {
    justify-content: flex-start;
  }

}
</style>
