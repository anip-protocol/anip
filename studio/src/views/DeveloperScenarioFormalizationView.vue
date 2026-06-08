<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  SCENARIO_CORE_FIELD_GUIDE,
  SCENARIO_FORMALIZATION_HELP,
  useDeveloperDefinitionEditor,
} from '../design/use-developer-definition-editor'
import { useDeveloperIssueTargets } from '../design/use-developer-issue-targets'
import ProjectIssueBanner from '../components/ProjectIssueBanner.vue'
import { useProjectIssue } from '../design/use-project-issue'
import { projectStore } from '../design/project-store'

const router = useRouter()
const editing = ref(false)
const pageIssue = useProjectIssue('project-developer-scenario-formalization')
const readOnly = computed(() => projectStore.runtimeStatus?.read_only_mode !== false)
const {
  project,
  baseline,
  baselineAligned,
  definition,
  serviceOptions,
  expandedScenarioHelpCards,
  activeScenarioHelpCard,
  scenarioAdditionalContext,
  scenarioPrimaryCapabilitySuggestion,
  toggleScenarioFormalizationService,
  saveDraft,
  resetDefinition,
  saving,
  saveError,
  toggleScenarioHelpCard,
  openScenarioHelpCard,
  closeScenarioHelpCard,
  semanticTypeLabel,
} = useDeveloperDefinitionEditor()

const {
  messagesForPath,
  messagesForPrefix,
  hasIssueForPath,
  hasIssueForPrefix,
} = useDeveloperIssueTargets({ definition, project })

function scenarioPath(scenarioId: string, field: string): string {
  return `scenario_formalizations.${scenarioId}.${field}`
}

function scenarioHasIssue(scenarioId: string): boolean {
  return hasIssueForPrefix(`scenario_formalizations.${scenarioId}`)
}

function enterEdit() {
  if (readOnly.value) return
  editing.value = true
}

function cancelEdit() {
  resetDefinition()
  editing.value = false
}

async function saveEdit() {
  if (readOnly.value) return
  await saveDraft()
  if (!saveError.value) editing.value = false
}

watch(readOnly, (isReadOnly) => {
  if (isReadOnly) editing.value = false
})
</script>

<template>
  <div class="developer-definition">
    <template v-if="project">
      <section class="page-header">
        <button class="back-link" type="button" @click="router.push(`/design/projects/${project.id}/developer`)">
          &larr; Back to Developer Design
        </button>
        <div class="page-kicker">Developer Design</div>
        <h1>Scenario Coverage Intent</h1>
        <p>
          Review how Product Design real situations should be covered by the Developer Definition. This page records scenario evidence for readiness, simulator, and verification checks; runtime behavior still belongs in capabilities, roles, approvals, and service implementation.
        </p>
      </section>
      <ProjectIssueBanner :issue="pageIssue" title="Scenario coverage diagnostics" />
      <section v-if="!baseline" class="panel empty-panel">
        <h2>Developer baseline is not locked</h2>
        <p>Return to Developer Overview and lock Product Design before reviewing scenario coverage.</p>
      </section>

      <section v-else-if="!baselineAligned" class="panel empty-panel">
        <h2>Locked baseline is out of sync</h2>
        <p>Product Design changed after the current developer baseline was locked. Re-lock the baseline before continuing.</p>
      </section>

      <section v-else-if="definition" class="grid" :class="{ 'review-mode': !editing, 'edit-mode': editing }">
        <article id="scenario-context" class="panel panel-full scenario-coverage-panel">
          <div class="panel-header">
            <h2>Per-Scenario Coverage Intent</h2>
            <div class="header-actions">
              <button v-if="!editing" class="btn btn-secondary" type="button" :disabled="readOnly" @click="enterEdit">
                Edit Scenarios
              </button>
              <button v-if="editing" class="btn btn-secondary" type="button" :disabled="saving" @click="cancelEdit">
                Cancel
              </button>
              <button v-if="editing" class="btn btn-primary" :disabled="readOnly || saving" @click="saveEdit">
                {{ saving ? 'Saving…' : 'Save Formalization' }}
              </button>
            </div>
          </div>
          <p v-if="saveError" class="error">{{ saveError }}</p>
          <p class="panel-copy">
            Each card records how a Product Design scenario should be covered by services and verification. Treat this as coverage intent and review evidence. If a value must change generated runtime behavior, move that decision into Capability Formalization, Roles & Access, approval policy, or service implementation.
          </p>

          <details class="details-panel">
            <summary>How scenario coverage affects the Developer Definition</summary>
            <div class="details-grid">
              <div class="details-card">
                <h3>What one scenario represents</h3>
                <p>A scenario is one important real situation from Product Design. It gives reviewers and simulators evidence about the behavior the package should support.</p>
              </div>
              <div class="details-card">
                <h3>Is it per service?</h3>
                <p>Not by default. A scenario can involve one service or several services. Participating services record expected coverage, not a hidden service implementation rule.</p>
              </div>
              <div class="details-card">
                <h3>What this page does not do</h3>
                <p>It does not by itself generate authorization, approval, data shaping, or custom orchestration. Those decisions must be formalized on the pages that own runtime behavior.</p>
              </div>
              <div class="details-card">
                <h3>How verification uses it</h3>
                <p>Verification and readiness checks use these fields to see whether important Product Design scenarios are represented and whether more explicit capability or app-glue decisions are needed.</p>
              </div>
            </div>
          </details>

          <div
            v-for="formalization in definition.scenario_formalizations"
            :key="formalization.scenario_id"
            class="scenario-formalization-card"
            :class="{ 'field-error-card': scenarioHasIssue(formalization.scenario_id) }"
          >
            <div class="panel-header edit-only">
              <div>
                <h3>{{ formalization.scenario_title }}</h3>
                <p class="panel-copy small-copy scenario-source-key">
                  Source scenario key:
                  <code class="source-key-code">{{ formalization.scenario_key || 'not specified' }}</code>
                </p>
                <p
                  v-for="message in messagesForPrefix(`scenario_formalizations.${formalization.scenario_id}`)"
                  :key="message"
                  class="inline-field-error"
                >
                  {{ message }}
                </p>
              </div>
            </div>

            <div class="scenario-help-row compact-help-row edit-only">
              <button class="help-link" type="button" @click="toggleScenarioHelpCard('coreFields')">
                {{ expandedScenarioHelpCards.coreFields ? 'Hide help' : 'What does this mean?' }}
              </button>
              <button class="help-link secondary" type="button" @click="openScenarioHelpCard('coreFields')">
                More detail
              </button>
            </div>
            <div v-if="expandedScenarioHelpCards.coreFields" class="inline-help edit-only">
              <p class="inline-help-summary">{{ SCENARIO_FORMALIZATION_HELP.coreFields.summary }}</p>
              <ul class="inline-help-list">
                <li v-for="detail in SCENARIO_FORMALIZATION_HELP.coreFields.inlineDetails" :key="detail">{{ detail }}</li>
              </ul>
            </div>

            <details class="review-collapse review-only">
              <summary>
                <div class="review-collapse-summary">
                  <div class="review-collapse-title">
                    <h3>{{ formalization.scenario_title }}</h3>
                    <p class="review-collapse-meta">
                      {{ formalization.scenario_key || 'Scenario key not specified' }}
                    </p>
                  </div>
                  <div class="review-collapse-badges">
                    <span class="review-collapse-badge">{{ formalization.primary_capability || 'capability?' }}</span>
                    <span class="review-collapse-badge">{{ formalization.participating_service_ids.length }} services</span>
                    <span class="review-collapse-badge">{{ scenarioAdditionalContext(formalization.scenario_id).length }} context</span>
                    <span class="review-collapse-toggle">View all saved values</span>
                  </div>
                </div>
              </summary>
              <div class="review-collapse-body">
                <div class="review-summary-grid">
                  <div class="review-summary-card"><strong>Primary Capability</strong><span>{{ formalization.primary_capability || scenarioPrimaryCapabilitySuggestion(formalization.scenario_id) || 'Not set' }}</span></div>
                  <div class="review-summary-card"><strong>Actor Context</strong><span>{{ formalization.actor_context || 'Not set' }}</span></div>
                  <div class="review-summary-card"><strong>Business Scope</strong><span>{{ formalization.business_scope || 'Not set' }}</span></div>
                  <div class="review-summary-card"><strong>Time Scope</strong><span>{{ formalization.time_scope || 'Not set' }}</span></div>
                  <div class="review-summary-card"><strong>Participating Services</strong><span>{{ formalization.participating_service_ids.length }}</span></div>
                  <div class="review-summary-card"><strong>Product Context</strong><span>{{ scenarioAdditionalContext(formalization.scenario_id).length }} entries</span></div>
                  <div class="review-summary-card field-wide"><strong>Permission Formalization</strong><p>{{ formalization.permission_formalization || 'Not formalized yet.' }}</p></div>
                  <div class="review-summary-card field-wide"><strong>Side Effects</strong><p>{{ formalization.side_effect_formalization || 'Not formalized yet.' }}</p></div>
                </div>
              </div>
            </details>

            <div class="scenario-block scenario-block-core edit-only">
              <div class="settings-grid">
                <label
                  :id="`scenario-formalization-${formalization.scenario_id}-primary_capability`"
                  class="field"
                  :class="{ 'field-error': hasIssueForPath(scenarioPath(formalization.scenario_id, 'primary_capability')) }"
                >
                  <span>Primary Capability</span>
                  <input v-model="formalization.primary_capability" class="input" :placeholder="scenarioPrimaryCapabilitySuggestion(formalization.scenario_id) || 'e.g. service.capability_id'" />
                  <small v-for="message in messagesForPath(scenarioPath(formalization.scenario_id, 'primary_capability'))" :key="message" class="field-error-copy">{{ message }}</small>
                </label>
                <label
                  :id="`scenario-formalization-${formalization.scenario_id}-actor_context`"
                  class="field"
                  :class="{ 'field-error': hasIssueForPath(scenarioPath(formalization.scenario_id, 'actor_context')) }"
                >
                  <span>Actor Context</span>
                  <input v-model="formalization.actor_context" class="input" placeholder="e.g. internal_operator" />
                  <small v-for="message in messagesForPath(scenarioPath(formalization.scenario_id, 'actor_context'))" :key="message" class="field-error-copy">{{ message }}</small>
                </label>
                <label
                  :id="`scenario-formalization-${formalization.scenario_id}-business_scope`"
                  class="field"
                  :class="{ 'field-error': hasIssueForPath(scenarioPath(formalization.scenario_id, 'business_scope')) }"
                >
                  <span>Business Scope</span>
                  <input v-model="formalization.business_scope" class="input" placeholder="e.g. enterprise_accounts" />
                  <small v-for="message in messagesForPath(scenarioPath(formalization.scenario_id, 'business_scope'))" :key="message" class="field-error-copy">{{ message }}</small>
                </label>
                <label
                  :id="`scenario-formalization-${formalization.scenario_id}-time_scope`"
                  class="field"
                  :class="{ 'field-error': hasIssueForPath(scenarioPath(formalization.scenario_id, 'time_scope')) }"
                >
                  <span>Time Scope</span>
                  <input v-model="formalization.time_scope" class="input" placeholder="e.g. fy2026_q2" />
                  <small v-for="message in messagesForPath(scenarioPath(formalization.scenario_id, 'time_scope'))" :key="message" class="field-error-copy">{{ message }}</small>
                </label>
              </div>
            </div>

            <div class="scenario-block edit-only">
              <div class="scenario-section-header">
                <span class="summary-label">Operational Posture</span>
              </div>
              <div class="settings-grid">
                <label :id="`scenario-formalization-${formalization.scenario_id}-side_effect_formalization`" class="field">
                  <span>Side-Effect Formalization</span>
                  <textarea
                    v-model="formalization.side_effect_formalization"
                    class="textarea"
                    rows="3"
                    placeholder="Describe how side effects should be surfaced, bounded, or prevented for this scenario."
                  />
                </label>
                <label :id="`scenario-formalization-${formalization.scenario_id}-expected_cost_formalization`" class="field">
                  <span>Expected Cost Formalization</span>
                  <textarea
                    v-model="formalization.expected_cost_formalization"
                    class="textarea"
                    rows="3"
                    placeholder="Describe how expected cost should be exposed or bounded for this scenario."
                  />
                </label>
                <label :id="`scenario-formalization-${formalization.scenario_id}-budget_guard_formalization`" class="field">
                  <span>Budget Guard Formalization</span>
                  <textarea
                    v-model="formalization.budget_guard_formalization"
                    class="textarea"
                    rows="3"
                    placeholder="Describe budget or spend expectations this scenario should verify. Put enforceable rules in capability or policy formalization."
                  />
                </label>
                <label :id="`scenario-formalization-${formalization.scenario_id}-permission_formalization`" class="field">
                  <span>Permission Formalization</span>
                  <textarea
                    v-model="formalization.permission_formalization"
                    class="textarea"
                    rows="3"
                    placeholder="Describe how permission posture should be represented for this scenario."
                  />
                </label>
                <label :id="`scenario-formalization-${formalization.scenario_id}-task_tracking_formalization`" class="field field-wide">
                  <span>Task Tracking Formalization</span>
                  <textarea
                    v-model="formalization.task_tracking_formalization"
                    class="textarea"
                    rows="3"
                    placeholder="Describe task IDs or work tracking evidence expected for this scenario."
                  />
                </label>
              </div>
            </div>

            <div
              :id="`scenario-formalization-${formalization.scenario_id}-participating_service_ids`"
              class="scenario-block protocol-section edit-only"
              :class="{ 'field-error-card': hasIssueForPath(scenarioPath(formalization.scenario_id, 'participating_service_ids')) }"
            >
              <div class="scenario-section-header">
                <span class="summary-label required-label">Participating Services</span>
                <div class="question-help-actions">
                  <button class="help-link" type="button" @click="toggleScenarioHelpCard('participatingServices')">
                    {{ expandedScenarioHelpCards.participatingServices ? 'Hide help' : 'What does this mean?' }}
                  </button>
                  <button class="help-link secondary" type="button" @click="openScenarioHelpCard('participatingServices')">More detail</button>
                </div>
              </div>
              <div v-if="expandedScenarioHelpCards.participatingServices" class="inline-help">
                <p class="inline-help-summary">{{ SCENARIO_FORMALIZATION_HELP.participatingServices.summary }}</p>
                <ul class="inline-help-list">
                  <li v-for="detail in SCENARIO_FORMALIZATION_HELP.participatingServices.inlineDetails" :key="detail">{{ detail }}</li>
                </ul>
              </div>
              <div class="chip-grid">
                <button
                  v-for="service in serviceOptions"
                  :key="service.id"
                  class="chip"
                  :class="{ active: formalization.participating_service_ids.includes(service.id) }"
                  type="button"
                  @click="toggleScenarioFormalizationService(formalization.scenario_id, service.id)"
                >
                  {{ service.label }}
                </button>
              </div>
              <small v-for="message in messagesForPath(scenarioPath(formalization.scenario_id, 'participating_service_ids'))" :key="message" class="field-error-copy">{{ message }}</small>
            </div>
            <div class="reference-block" v-if="scenarioAdditionalContext(formalization.scenario_id).length">
              <span class="summary-label">Product Design Scenario Context</span>
              <p class="panel-copy small-copy">
                Product Design defines scenario context here. Typed entries can prefill coverage fields above. Descriptive-only entries stay as review evidence and should not be treated as generated behavior.
              </p>
              <ul class="reference-list">
                <li v-for="entry in scenarioAdditionalContext(formalization.scenario_id)" :key="`${formalization.scenario_id}-${entry.key}-${entry.value}`">
                  <strong>{{ entry.key }}</strong>: {{ entry.value }}
                  <span class="reference-badge">{{ semanticTypeLabel(entry.semantic_type) }}</span>
                  <span v-if="entry.description"> — {{ entry.description }}</span>
                </li>
              </ul>
            </div>
          </div>
        </article>
      </section>
    </template>
  </div>

  <div v-if="activeScenarioHelpCard" class="help-dialog-backdrop" @click.self="closeScenarioHelpCard">
    <div class="help-dialog">
      <div class="help-dialog-header">
        <h2>{{ SCENARIO_FORMALIZATION_HELP[activeScenarioHelpCard].title }}</h2>
        <button class="help-dialog-close" type="button" @click="closeScenarioHelpCard">Close</button>
      </div>
      <p class="inline-help-summary">{{ SCENARIO_FORMALIZATION_HELP[activeScenarioHelpCard].summary }}</p>
      <ul class="inline-help-list">
        <li v-for="detail in SCENARIO_FORMALIZATION_HELP[activeScenarioHelpCard].bullets" :key="detail">{{ detail }}</li>
      </ul>
      <div v-if="activeScenarioHelpCard === 'coreFields'" class="details-grid">
        <div v-for="entry in SCENARIO_CORE_FIELD_GUIDE" :key="entry.field" class="details-card">
          <h3>{{ entry.field }}</h3>
          <p><strong>Definition:</strong> {{ entry.definition }}</p>
          <p><strong>How Studio uses it:</strong> {{ entry.usage }}</p>
          <p><strong>Value source:</strong> {{ entry.predefined }}</p>
        </div>
      </div>
      <p v-if="SCENARIO_FORMALIZATION_HELP[activeScenarioHelpCard].example" class="help-dialog-example">
        <strong>Example:</strong> {{ SCENARIO_FORMALIZATION_HELP[activeScenarioHelpCard].example }}
      </p>
    </div>
  </div>
</template>

<style scoped src="./developer-definition-shared.css"></style>
<style scoped>
.panel > .panel-copy {
  margin: 0 0 1.25rem;
  max-width: 92rem;
}

.panel-header {
  margin-bottom: 1.1rem;
}

.settings-grid {
  gap: 1rem;
}

.field {
  gap: 0.5rem;
}

.field > span {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.input,
.select,
.textarea {
  background: var(--surface-depth-control);
}

.details-panel {
  margin: 0 0 1.15rem;
  border-radius: 16px;
  background:
    linear-gradient(135deg, rgba(59, 130, 246, 0.08), rgba(14, 165, 233, 0.04)),
    rgba(15, 23, 42, 0.28);
}

.details-panel summary {
  color: var(--text-primary);
  letter-spacing: 0.01em;
}

.details-card {
  background: var(--surface-depth-inset);
}

.details-card p {
  color: var(--text-secondary);
  line-height: 1.55;
}

.scenario-coverage-panel .scenario-formalization-card {
  margin-top: 1rem;
  border: 1px solid var(--surface-border-card);
  border-radius: 18px;
  padding: 1rem;
  background: var(--surface-depth-card);
  box-shadow: var(--surface-shadow-card);
}

.scenario-coverage-panel .scenario-formalization-card:first-of-type {
  margin-top: 1rem;
}

.scenario-coverage-panel .review-collapse {
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
  overflow: visible;
}

.scenario-coverage-panel .review-collapse summary {
  padding: 0;
}

.scenario-coverage-panel .review-collapse-body {
  padding: 0;
}

.scenario-formalization-card > .panel-header {
  align-items: flex-start;
  margin-bottom: 1rem;
  padding-bottom: 0.9rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
}

.scenario-formalization-card h3 {
  margin: 0 0 0.4rem;
  font-size: 18px;
}

.scenario-source-key {
  margin: 0;
}

.source-key-code {
  overflow-wrap: anywhere;
}

.scenario-help-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem;
  align-items: center;
  margin: 0.1rem 0 1rem;
}

.help-link {
  border: none;
  border-radius: 999px;
  background: rgba(96, 165, 250, 0.12);
  color: #bfdbfe;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  padding: 0.38rem 0.75rem;
}

.help-link.secondary {
  background: rgba(148, 163, 184, 0.12);
  color: var(--text-secondary);
}

.inline-help {
  margin-bottom: 1rem;
  border: 1px solid rgba(96, 165, 250, 0.2);
  border-radius: 14px;
  background: var(--surface-depth-card);
  padding: 0.9rem 1rem;
}

.scenario-block {
  margin-top: 1.2rem;
  padding-top: 1rem;
}

.scenario-block-core {
  margin-top: 0;
  padding-top: 0;
  border-top: none;
}

.scenario-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 0.95rem;
}

.scenario-section-header .summary-label {
  margin: 0;
  color: var(--text-secondary);
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.question-help-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
  justify-content: flex-end;
}

.chip-grid {
  margin-top: 0;
}

.reference-block {
  margin-top: 1.15rem;
  border: 1px solid var(--surface-border-card);
  border-radius: 16px;
  background: var(--surface-depth-inset);
  padding: 1rem;
}

.reference-block .summary-label {
  margin-bottom: 0.5rem;
  color: var(--text-secondary);
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.reference-list {
  margin-top: 0.75rem;
}

.reference-list li {
  line-height: 1.55;
}

@media (max-width: 960px) {
  .settings-grid {
    grid-template-columns: 1fr;
  }

  .field-wide {
    grid-column: span 1;
  }

  .scenario-section-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .question-help-actions {
    justify-content: flex-start;
  }
}
</style>
