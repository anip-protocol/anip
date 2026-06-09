<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  OUTCOME_TYPE_OPTIONS,
  SCENARIO_FORMALIZATION_HELP,
  STEP_KIND_OPTIONS,
  STOP_CONDITION_OPTIONS,
  useDeveloperDefinitionEditor,
} from '../design/use-developer-definition-editor'
import { useDeveloperIssueTargets } from '../design/use-developer-issue-targets'
import ProjectIssueBanner from '../components/ProjectIssueBanner.vue'
import { useProjectIssue } from '../design/use-project-issue'
import { projectStore } from '../design/project-store'

const router = useRouter()
const editing = ref(false)
const pageIssue = useProjectIssue('project-developer-scenario-execution-semantics')
const {
  project,
  baseline,
  baselineAligned,
  definition,
  serviceOptions,
  expandedScenarioHelpCards,
  activeScenarioHelpCard,
  scenarioSourceValues,
  toggleScenarioFormalizationValue,
  orchestrationStepsForScenario,
  addOrchestrationStep,
  updateOrchestrationStep,
  removeOrchestrationStep,
  saveDraft,
  resetDefinition,
  saving,
  saveError,
  toggleCompositionRuleScenario,
  toggleScenarioHelpCard,
  openScenarioHelpCard,
  closeScenarioHelpCard,
  humanizeContractValue,
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

function scenarioPath(scenarioId: string, field: string): string {
  return `scenario_formalizations.${scenarioId}.${field}`
}

function stepPath(scenarioId: string, stepId: string, field: string): string {
  return `scenario_formalizations.${scenarioId}.orchestration_steps.${stepId}.${field}`
}

function scenarioExecutionHasIssue(scenarioId: string): boolean {
  return [
    'orchestration_steps',
    'required_behaviors',
    'required_anip_support',
  ].some((field) => hasIssueForPath(scenarioPath(scenarioId, field)))
    || hasIssueForPrefix(`${scenarioPath(scenarioId, 'orchestration_steps')}.`)
}

function stepHasIssue(scenarioId: string, stepId: string): boolean {
  return hasIssueForPrefix(`scenario_formalizations.${scenarioId}.orchestration_steps.${stepId}`)
}

function enterEdit() {
  if (readOnlyMode.value) return
  editing.value = true
}

function cancelEdit() {
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
  <div class="developer-definition">
    <template v-if="project">
      <section class="page-header">
        <button class="back-link" type="button" @click="router.push(`/design/projects/${project.id}/developer`)">
          &larr; Back to Developer Design
        </button>
        <div class="page-kicker">Developer Design</div>
        <h1>Scenario Execution Semantics</h1>
        <p>
          Review how each scenario is expected to unfold. This page owns structured orchestration evidence, required behaviors, ANIP-visible expectations, implementation notes, and product-wide compound behavior rules.
        </p>
      </section>
      <div v-if="readOnlyMode" class="banner banner-warning readonly-banner">
        {{ readOnlyReason }}
      </div>
      <ProjectIssueBanner :issue="pageIssue" title="Scenario Execution diagnostics" />
      <section v-if="!baseline" class="panel empty-panel">
        <h2>Developer baseline is not locked</h2>
        <p>Return to Developer Overview and lock Product Design before formalizing scenario execution semantics.</p>
      </section>

      <section v-else-if="!baselineAligned" class="panel empty-panel">
        <h2>Locked baseline is out of sync</h2>
        <p>Product Design changed after the current developer baseline was locked. Re-lock the baseline before continuing.</p>
      </section>

      <section v-else-if="definition" class="grid" :class="{ 'review-mode': !editing, 'edit-mode': editing }">
        <article id="scenario-execution-semantics" class="panel panel-full">
          <div class="panel-header">
            <h2>Per-Scenario Execution Semantics</h2>
            <div class="header-actions">
              <button v-if="!editing" class="btn btn-secondary" type="button" :disabled="readOnlyMode" @click="enterEdit">
                Edit Execution
              </button>
              <button v-if="editing" class="btn btn-secondary" type="button" :disabled="readOnlyMode || saving" @click="cancelEdit">
                Cancel
              </button>
              <button v-if="editing" class="btn btn-primary" :disabled="readOnlyMode || saving" @click="saveEdit">
                {{ saving ? 'Saving…' : 'Save Formalization' }}
              </button>
            </div>
          </div>
          <p v-if="saveError" class="error">{{ saveError }}</p>
          <p class="panel-copy">
            Use this page to define the reviewed scenario flow: execution steps, capability bindings, bounded outcomes, visible stop conditions, and protocol-visible behavior the implementation or app layer must preserve.
          </p>

          <details class="details-panel">
            <summary>How execution semantics affect readiness and verification</summary>
            <div class="details-grid">
              <div class="details-card">
                <h3>Structured orchestration</h3>
                <p>Each step tells Studio which service is expected to own the work, whether the step is executable or handoff-only, which capability it binds to, and which stop condition must be preserved.</p>
              </div>
              <div class="details-card">
                <h3>Required behaviors</h3>
                <p>These are scenario-level behavior tokens readiness and verification should preserve. They do not automatically apply to every service; orchestration and capability bindings determine where they belong.</p>
              </div>
              <div class="details-card">
                <h3>Required ANIP support</h3>
                <p>These tokens identify which protocol-visible ANIP behaviors must be present for the scenario, such as approval-required or clarification-required outcomes.</p>
              </div>
              <div class="details-card">
                <h3>Implementation notes</h3>
                <p>These are review-only notes for developers and PMs. They help explain design intent, but generation should not depend on them.</p>
              </div>
            </div>
          </details>

          <div
            v-for="formalization in definition.scenario_formalizations"
            :key="formalization.scenario_id"
            class="scenario-formalization-card"
            :class="{ 'field-error-card': scenarioExecutionHasIssue(formalization.scenario_id) }"
          >
            <div class="panel-header">
              <div>
                <h3>{{ formalization.scenario_title }}</h3>
                <p class="panel-copy small-copy scenario-source-key">
                  Source scenario key:
                  <code class="source-key-code">{{ formalization.scenario_key || 'not specified' }}</code>
                </p>
                <p
                  v-for="message in messagesForPrefix(`scenario_formalizations.${formalization.scenario_id}.orchestration_steps`)"
                  :key="message"
                  class="inline-field-error"
                >
                  {{ message }}
                </p>
                <p
                  v-for="message in [...messagesForPath(scenarioPath(formalization.scenario_id, 'required_behaviors')), ...messagesForPath(scenarioPath(formalization.scenario_id, 'required_anip_support'))]"
                  :key="message"
                  class="inline-field-error"
                >
                  {{ message }}
                </p>
              </div>
            </div>

            <div class="review-summary-grid review-only">
              <div class="review-summary-card"><strong>Orchestration Steps</strong><span>{{ orchestrationStepsForScenario(formalization.scenario_id).length }}</span></div>
              <div class="review-summary-card"><strong>Required Behaviors</strong><span>{{ formalization.required_behaviors.map(humanizeContractValue).join(', ') || 'None selected' }}</span></div>
              <div class="review-summary-card"><strong>Required ANIP Support</strong><span>{{ formalization.required_anip_support.map(humanizeContractValue).join(', ') || 'None selected' }}</span></div>
              <div class="review-summary-card field-wide"><strong>Implementation Notes</strong><p>{{ formalization.implementation_notes || 'No notes recorded.' }}</p></div>
            </div>

            <label
              :id="`scenario-formalization-${formalization.scenario_id}-orchestration_steps`"
              class="field field-wide scenario-block edit-only"
              :class="{ 'field-error': hasIssueForPrefix(`${scenarioPath(formalization.scenario_id, 'orchestration_steps')}`) }"
            >
              <div class="scenario-section-header">
                <span class="summary-label">Orchestration Steps</span>
                <div class="question-help-actions">
                  <button class="help-link" type="button" @click="toggleScenarioHelpCard('orchestrationSteps')">
                    {{ expandedScenarioHelpCards.orchestrationSteps ? 'Hide help' : 'What does this mean?' }}
                  </button>
                  <button class="help-link secondary" type="button" @click="openScenarioHelpCard('orchestrationSteps')">More detail</button>
                </div>
              </div>
              <div v-if="expandedScenarioHelpCards.orchestrationSteps" class="inline-help">
                <p class="inline-help-summary">{{ SCENARIO_FORMALIZATION_HELP.orchestrationSteps.summary }}</p>
                <ul class="inline-help-list">
                  <li v-for="detail in SCENARIO_FORMALIZATION_HELP.orchestrationSteps.inlineDetails" :key="detail">{{ detail }}</li>
                </ul>
              </div>
              <div class="scenario-help-row nested-help-row">
                <button class="help-link" type="button" @click="toggleScenarioHelpCard('orchestrationStepFields')">
                  {{ expandedScenarioHelpCards.orchestrationStepFields ? 'Hide step field help' : 'What do the step fields mean?' }}
                </button>
                <button class="help-link secondary" type="button" @click="openScenarioHelpCard('orchestrationStepFields')">More detail</button>
              </div>
              <div v-if="expandedScenarioHelpCards.orchestrationStepFields" class="inline-help">
                <p class="inline-help-summary">{{ SCENARIO_FORMALIZATION_HELP.orchestrationStepFields.summary }}</p>
                <ul class="inline-help-list">
                  <li v-for="detail in SCENARIO_FORMALIZATION_HELP.orchestrationStepFields.inlineDetails" :key="detail">{{ detail }}</li>
                </ul>
              </div>
              <div class="orchestration-list">
                <div
                  v-for="(step, index) in orchestrationStepsForScenario(formalization.scenario_id)"
                  :key="step.id"
                  class="orchestration-step-card"
                  :class="{ 'field-error-card': stepHasIssue(formalization.scenario_id, step.id) }"
                >
                  <div class="orchestration-step-header">
                    <strong>Step {{ index + 1 }}</strong>
                    <button class="btn btn-secondary btn-compact" type="button" :disabled="readOnlyMode" @click="removeOrchestrationStep(formalization.scenario_id, step.id)">Remove</button>
                  </div>
                  <div class="settings-grid orchestration-grid">
                    <label class="field" :class="{ 'field-error': hasIssueForPath(stepPath(formalization.scenario_id, step.id, 'service_id')) }">
                      <span class="required-label">Service</span>
                      <select :value="step.service_id" class="select" :disabled="readOnlyMode" @change="updateOrchestrationStep(formalization.scenario_id, step.id, 'service_id', ($event.target as HTMLSelectElement).value)">
                        <option value="">Select a service</option>
                        <option v-for="service in serviceOptions" :key="service.id" :value="service.id">{{ service.label }}</option>
                      </select>
                      <small class="hint">Which service boundary owns or performs this step.</small>
                      <small v-for="message in messagesForPath(stepPath(formalization.scenario_id, step.id, 'service_id'))" :key="message" class="field-error-copy">{{ message }}</small>
                    </label>
                    <label class="field" :class="{ 'field-error': hasIssueForPath(stepPath(formalization.scenario_id, step.id, 'step_kind')) }">
                      <span class="required-label">Step Kind</span>
                      <select :value="step.step_kind" class="select" :disabled="readOnlyMode" @change="updateOrchestrationStep(formalization.scenario_id, step.id, 'step_kind', ($event.target as HTMLSelectElement).value)">
                        <option v-for="option in STEP_KIND_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
                      </select>
                      <small class="hint">{{ STEP_KIND_OPTIONS.find((option) => option.value === step.step_kind)?.description }}</small>
                      <small v-for="message in messagesForPath(stepPath(formalization.scenario_id, step.id, 'step_kind'))" :key="message" class="field-error-copy">{{ message }}</small>
                    </label>
                    <label class="field" :class="{ 'field-error': hasIssueForPath(stepPath(formalization.scenario_id, step.id, 'capability_id')) }">
                      <span :class="step.step_kind === 'capability_execution' ? 'required-label' : ''">Capability ID</span>
                      <input :value="step.capability_id" class="input" placeholder="e.g. operations.prepare_assignment_preview" :disabled="readOnlyMode || step.step_kind === 'handoff_only'" @input="updateOrchestrationStep(formalization.scenario_id, step.id, 'capability_id', ($event.target as HTMLInputElement).value)" />
                      <small class="hint">{{ step.step_kind === 'capability_execution' ? 'Required for executable steps. This is the exact capability surface generation and verification should bind to.' : 'Not used for handoff-only steps.' }}</small>
                      <small v-for="message in messagesForPath(stepPath(formalization.scenario_id, step.id, 'capability_id'))" :key="message" class="field-error-copy">{{ message }}</small>
                    </label>
                    <label class="field" :class="{ 'field-error': hasIssueForPath(stepPath(formalization.scenario_id, step.id, 'outcome_type')) }">
                      <span class="required-label">Outcome Type</span>
                      <select :value="step.outcome_type" class="select" :disabled="readOnlyMode" @change="updateOrchestrationStep(formalization.scenario_id, step.id, 'outcome_type', ($event.target as HTMLSelectElement).value)">
                        <option v-for="option in OUTCOME_TYPE_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
                      </select>
                      <small class="hint">{{ OUTCOME_TYPE_OPTIONS.find((option) => option.value === step.outcome_type)?.description }}</small>
                      <small v-for="message in messagesForPath(stepPath(formalization.scenario_id, step.id, 'outcome_type'))" :key="message" class="field-error-copy">{{ message }}</small>
                    </label>
                    <label class="field field-wide">
                      <span>Outcome Notes</span>
                      <input :value="step.outcome_notes" class="input" placeholder="Optional explanatory detail about this step outcome." :disabled="readOnlyMode" @input="updateOrchestrationStep(formalization.scenario_id, step.id, 'outcome_notes', ($event.target as HTMLInputElement).value)" />
                      <small class="hint">Optional notes for humans and review. This does not drive generation directly.</small>
                    </label>
                    <label class="field" :class="{ 'field-error': hasIssueForPath(stepPath(formalization.scenario_id, step.id, 'stop_condition')) }">
                      <span class="required-label">Stop Condition</span>
                      <select :value="step.stop_condition" class="select" :disabled="readOnlyMode" @change="updateOrchestrationStep(formalization.scenario_id, step.id, 'stop_condition', ($event.target as HTMLSelectElement).value)">
                        <option v-for="option in STOP_CONDITION_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
                      </select>
                      <small class="hint">{{ STOP_CONDITION_OPTIONS.find((option) => option.value === step.stop_condition)?.description }}</small>
                      <small v-for="message in messagesForPath(stepPath(formalization.scenario_id, step.id, 'stop_condition'))" :key="message" class="field-error-copy">{{ message }}</small>
                    </label>
                  </div>
                </div>
              </div>
              <button class="btn btn-secondary add-step-button" type="button" :disabled="readOnlyMode" @click="addOrchestrationStep(formalization.scenario_id)">+ Add Step</button>
            </label>

            <div
              :id="`scenario-formalization-${formalization.scenario_id}-required_behaviors`"
              class="scenario-block protocol-section edit-only"
              :class="{ 'field-error-card': hasIssueForPath(scenarioPath(formalization.scenario_id, 'required_behaviors')) }"
            >
              <div class="scenario-section-header">
                <span class="summary-label required-label">Required Behaviors</span>
                <div class="question-help-actions">
                  <button class="help-link" type="button" @click="toggleScenarioHelpCard('requiredBehaviors')">
                    {{ expandedScenarioHelpCards.requiredBehaviors ? 'Hide help' : 'What does this mean?' }}
                  </button>
                  <button class="help-link secondary" type="button" @click="openScenarioHelpCard('requiredBehaviors')">More detail</button>
                </div>
              </div>
              <div v-if="expandedScenarioHelpCards.requiredBehaviors" class="inline-help">
                <p class="inline-help-summary">{{ SCENARIO_FORMALIZATION_HELP.requiredBehaviors.summary }}</p>
                <ul class="inline-help-list">
                  <li v-for="detail in SCENARIO_FORMALIZATION_HELP.requiredBehaviors.inlineDetails" :key="detail">{{ detail }}</li>
                </ul>
              </div>
              <div class="chip-grid">
                <button v-for="behavior in scenarioSourceValues(formalization.scenario_id, 'expected_behavior')" :key="behavior" class="chip" :class="{ active: formalization.required_behaviors.includes(behavior) }" type="button" :disabled="readOnlyMode" @click="toggleScenarioFormalizationValue(formalization.scenario_id, 'required_behaviors', behavior)">
                  {{ humanizeContractValue(behavior) }}
                </button>
              </div>
              <small v-for="message in messagesForPath(scenarioPath(formalization.scenario_id, 'required_behaviors'))" :key="message" class="field-error-copy">{{ message }}</small>
            </div>

            <div
              :id="`scenario-formalization-${formalization.scenario_id}-required_anip_support`"
              class="scenario-block protocol-section edit-only"
              :class="{ 'field-error-card': hasIssueForPath(scenarioPath(formalization.scenario_id, 'required_anip_support')) }"
            >
              <div class="scenario-section-header">
                <span class="summary-label required-label">Required ANIP Support</span>
                <div class="question-help-actions">
                  <button class="help-link" type="button" @click="toggleScenarioHelpCard('requiredAnipSupport')">
                    {{ expandedScenarioHelpCards.requiredAnipSupport ? 'Hide help' : 'What does this mean?' }}
                  </button>
                  <button class="help-link secondary" type="button" @click="openScenarioHelpCard('requiredAnipSupport')">More detail</button>
                </div>
              </div>
              <div v-if="expandedScenarioHelpCards.requiredAnipSupport" class="inline-help">
                <p class="inline-help-summary">{{ SCENARIO_FORMALIZATION_HELP.requiredAnipSupport.summary }}</p>
                <ul class="inline-help-list">
                  <li v-for="detail in SCENARIO_FORMALIZATION_HELP.requiredAnipSupport.inlineDetails" :key="detail">{{ detail }}</li>
                </ul>
              </div>
              <div class="chip-grid">
                <button v-for="support in scenarioSourceValues(formalization.scenario_id, 'expected_anip_support')" :key="support" class="chip" :class="{ active: formalization.required_anip_support.includes(support) }" type="button" :disabled="readOnlyMode" @click="toggleScenarioFormalizationValue(formalization.scenario_id, 'required_anip_support', support)">
                  {{ humanizeContractValue(support) }}
                </button>
              </div>
              <small v-for="message in messagesForPath(scenarioPath(formalization.scenario_id, 'required_anip_support'))" :key="message" class="field-error-copy">{{ message }}</small>
            </div>

            <label class="field field-wide scenario-block edit-only">
              <div class="scenario-section-header">
                <span class="summary-label">Implementation Notes</span>
                <div class="question-help-actions">
                  <button class="help-link" type="button" @click="toggleScenarioHelpCard('implementationNotes')">
                    {{ expandedScenarioHelpCards.implementationNotes ? 'Hide help' : 'What does this mean?' }}
                  </button>
                  <button class="help-link secondary" type="button" @click="openScenarioHelpCard('implementationNotes')">More detail</button>
                </div>
              </div>
              <div v-if="expandedScenarioHelpCards.implementationNotes" class="inline-help">
                <p class="inline-help-summary">{{ SCENARIO_FORMALIZATION_HELP.implementationNotes.summary }}</p>
                <ul class="inline-help-list">
                  <li v-for="detail in SCENARIO_FORMALIZATION_HELP.implementationNotes.inlineDetails" :key="detail">{{ detail }}</li>
                </ul>
              </div>
              <textarea v-model="formalization.implementation_notes" class="textarea" rows="3" placeholder="Explain service ownership, stop conditions, approval boundaries, or other implementation-specific handling." :disabled="readOnlyMode" />
            </label>
          </div>
        </article>

        <article id="compound-workflow-rules" class="panel panel-full">
          <div class="panel-header">
            <h2>Compound Workflow Rules</h2>
          </div>
          <p class="panel-copy">
            Product-wide multi-step composition rules become explicit technical formalization here. Tie each rule to the affected scenarios and describe how orchestration, stop conditions, or bounded handoffs should preserve it.
          </p>
          <div v-if="definition.composition_rules.length" class="composition-rule-list">
            <div v-for="rule in definition.composition_rules" :key="rule.id" class="composition-rule-card">
              <div class="section-head">
                <h3>{{ rule.rule }}</h3>
              </div>
              <div class="review-summary-grid review-only">
                <div class="review-summary-card"><strong>Affected Scenarios</strong><span>{{ rule.affected_scenario_ids.length }}</span></div>
                <div class="review-summary-card field-wide"><strong>Formalization Strategy</strong><p>{{ rule.formalization_strategy || 'Not formalized yet.' }}</p></div>
              </div>
              <div class="settings-grid edit-only">
                <div class="field field-wide">
                  <span class="summary-label required-label">Affected Scenarios</span>
                  <div class="chip-grid">
                    <button
                      v-for="scenario in definition.scenario_formalizations"
                      :key="scenario.scenario_id"
                      class="chip"
                      :class="{ active: rule.affected_scenario_ids.includes(scenario.scenario_id) }"
                      type="button"
                      :disabled="readOnlyMode"
                      @click="toggleCompositionRuleScenario(rule.id, scenario.scenario_id)"
                    >
                      {{ scenario.scenario_title }}
                    </button>
                  </div>
                </div>
                <label class="field field-wide">
                  <span class="summary-label required-label">Formalization Strategy</span>
                  <textarea
                    v-model="rule.formalization_strategy"
                    class="textarea"
                    rows="3"
                    placeholder="Describe how scenario orchestration, stop conditions, approvals, or service handoffs should preserve this compound workflow rule."
                    :disabled="readOnlyMode"
                  />
                </label>
              </div>
            </div>
          </div>
          <p v-else class="panel-copy">No multi-step composition rules are defined on the locked Product Design baseline.</p>
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
      <p v-if="SCENARIO_FORMALIZATION_HELP[activeScenarioHelpCard].example" class="help-dialog-example">
        <strong>Example:</strong> {{ SCENARIO_FORMALIZATION_HELP[activeScenarioHelpCard].example }}
      </p>
    </div>
  </div>
</template>

<style scoped src="./developer-definition-shared.css"></style>
<style scoped>
.panel > .panel-copy {
  max-width: 92rem;
  margin: 0 0 1.25rem;
}

.panel-header {
  margin-bottom: 1.15rem;
}

.readonly-banner {
  margin: 0 0 1rem;
}

.btn:disabled,
.chip:disabled,
.input:disabled,
.select:disabled,
.textarea:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.panel-header h2,
.panel-header h3,
.section-head h3 {
  margin: 0;
}

.scenario-formalization-card,
.composition-rule-card {
  border: 1px solid var(--surface-border-card);
  border-radius: 18px;
  padding: 1.1rem;
  background: var(--surface-depth-card);
}

.scenario-formalization-card {
  margin-top: 1.15rem;
}

.scenario-formalization-card > .panel-header {
  margin-bottom: 1.05rem;
  padding-bottom: 0.95rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
}

.scenario-formalization-card h3,
.composition-rule-card h3 {
  font-size: 18px;
  line-height: 1.35;
}

.scenario-source-key {
  margin: 0.45rem 0 0;
}

.scenario-block {
  margin-top: 1.4rem;
  padding-top: 1.2rem;
  border-top: 1px solid rgba(148, 163, 184, 0.12);
}

.scenario-section-header {
  align-items: center;
  margin-bottom: 0.9rem;
}

.summary-label,
.field > span {
  margin: 0;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.question-help-actions {
  gap: 0.75rem;
}

.help-link {
  color: var(--accent);
  font-weight: 650;
}

.help-link.secondary {
  color: var(--text-secondary);
}

.nested-help-row {
  justify-content: flex-start;
  margin: 0 0 0.9rem;
}

.inline-help {
  margin: 0 0 0.95rem;
}

.details-panel {
  margin-top: 1rem;
  background: var(--surface-depth-card);
}

.details-card {
  background: var(--surface-depth-inset);
}

.orchestration-list {
  gap: 1rem;
}

.orchestration-step-card {
  border-radius: 16px;
  background: var(--surface-depth-inset);
}

.orchestration-step-header {
  margin-bottom: 1rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
}

.settings-grid {
  gap: 1rem;
}

.field {
  gap: 0.5rem;
}

.input,
.select,
.textarea {
  background: var(--surface-depth-control);
}

.textarea {
  min-height: 8rem;
}

.hint {
  display: block;
  margin-top: 0.1rem;
}

.chip-grid {
  margin-top: 0.15rem;
}

.chip {
  max-width: 100%;
  overflow-wrap: anywhere;
  text-align: left;
}

.add-step-button {
  margin-top: 1rem;
}

.composition-rule-list {
  display: flex;
  flex-direction: column;
  gap: 1.1rem;
}

.composition-rule-card {
  margin-top: 0;
}

.composition-rule-card .section-head {
  margin-bottom: 1rem;
  padding-bottom: 0.9rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
}

@media (max-width: 960px) {
  .scenario-section-header,
  .scenario-help-row {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
