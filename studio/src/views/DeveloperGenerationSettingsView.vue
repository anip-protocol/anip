<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  ADAPTER_OPTIONS,
  LAYOUT_OPTIONS,
  PROTOCOL_OPTIONS,
  SCALABILITY_OPTIONS,
  SERVICE_GENERATION_OPTIONS,
  useDeveloperDefinitionEditor,
} from '../design/use-developer-definition-editor'
import ProjectIssueBanner from '../components/ProjectIssueBanner.vue'
import { useProjectIssue } from '../design/use-project-issue'
import { useDeveloperIssueTargets } from '../design/use-developer-issue-targets'
import { formatDeveloperList, optionLabel } from '../design/developer-vocabulary'
import { projectStore } from '../design/project-store'

const router = useRouter()
const editing = ref(false)
const pageIssue = useProjectIssue('project-developer-generation-settings')
const {
  project,
  baseline,
  baselineAligned,
  definition,
  serviceOptions,
  generatedCodeSummary,
  toggleProtocol,
  toggleServiceSelection,
  saveDraft,
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

function toggleEditing() {
  if (readOnlyMode.value) return
  editing.value = !editing.value
}

async function saveSettings() {
  if (readOnlyMode.value) return
  await saveDraft()
}
</script>

<template>
  <div class="developer-definition generation-settings-page">
    <template v-if="project">
      <section class="page-header">
        <button class="back-link" type="button" @click="router.push(`/design/projects/${project.id}/developer`)">
          &larr; Back to Developer Design
        </button>
        <div class="page-kicker">Developer Design</div>
        <h1>Generation Settings</h1>
        <p>
          These are the implementation decisions that directly change generated scaffolds: service count, protocols, scaling posture, target adapter, repository shape, and naming.
        </p>
      </section>
      <div v-if="readOnlyMode" class="banner banner-warning readonly-banner">
        {{ readOnlyReason }}
      </div>
      <ProjectIssueBanner :issue="pageIssue" title="Generation Settings diagnostics" />
      <section v-if="!baseline" class="panel empty-panel">
        <h2>Developer baseline is not locked</h2>
        <p>Return to Developer Overview and lock Product Design before setting generation posture.</p>
      </section>

      <section v-else-if="!baselineAligned" class="panel empty-panel">
        <h2>Locked baseline is out of sync</h2>
        <p>Product Design changed after the current developer baseline was locked. Re-lock the baseline before continuing.</p>
      </section>

      <section v-else-if="definition" class="grid generation-layout" :class="{ 'review-mode': !editing, 'edit-mode': editing }">
        <article
          id="generation-settings"
          class="panel panel-full"
          :class="{ 'field-error-card': hasIssueForPrefix('generation') || hasIssueForPrefix('naming') }"
        >
          <div class="panel-header">
            <div>
              <h2>Generation Settings</h2>
              <p class="panel-copy compact-copy">Generated code should be reproducible from these explicit choices.</p>
            </div>
            <div class="header-actions">
              <button class="btn btn-secondary" type="button" :disabled="readOnlyMode" @click="toggleEditing">
                {{ editing ? 'Review Settings' : 'Edit Settings' }}
              </button>
              <button v-if="editing" class="btn btn-primary" :disabled="readOnlyMode || saving" @click="saveSettings">
                {{ saving ? 'Saving…' : 'Save Settings' }}
              </button>
            </div>
          </div>
          <p v-if="saveError" class="error">{{ saveError }}</p>
          <p class="panel-copy">
            If a developer cannot explain how generated code changes when one of these values changes, the contract is still underspecified.
          </p>
          <p class="panel-copy why-copy">
            Why this matters: these choices turn the reviewed design into generated service boundaries, protocols, package names, and runtime scaffolds. Keep the summary understandable first; use the exact names as technical traceability.
          </p>
          <p
            v-for="message in [...messagesForPrefix('generation'), ...messagesForPrefix('naming')]"
            :key="message"
            class="inline-field-error"
          >
            {{ message }}
          </p>
          <div class="review-summary-grid review-only">
            <div class="review-summary-card"><strong>Service Generation</strong><span>{{ optionLabel(SERVICE_GENERATION_OPTIONS, definition.generation.service_generation_mode) }}</span></div>
            <div class="review-summary-card"><strong>Scalability</strong><span>{{ optionLabel(SCALABILITY_OPTIONS, definition.generation.scalability_profile) }}</span></div>
            <div class="review-summary-card"><strong>Adapter</strong><span>{{ optionLabel(ADAPTER_OPTIONS, definition.generation.codegen_adapter) }}</span></div>
            <div class="review-summary-card"><strong>Layout</strong><span>{{ optionLabel(LAYOUT_OPTIONS, definition.generation.layout_strategy) }}</span></div>
            <div class="review-summary-card"><strong>Namespace</strong><span>{{ definition.naming.namespace || 'Not set' }}</span></div>
            <div class="review-summary-card"><strong>Service Prefix</strong><span>{{ definition.naming.service_name_prefix || 'Not set' }}</span></div>
            <div class="review-summary-card field-wide"><strong>Rationale</strong><p>{{ definition.rationale || 'No rationale recorded.' }}</p></div>
          </div>
          <div class="settings-grid edit-only">
            <label class="field generation-field" :class="{ 'field-error': hasIssueForPath('generation.service_generation_mode') }">
              <span class="required-label">How many services should generation produce?</span>
              <select v-model="definition.generation.service_generation_mode" class="select" :disabled="readOnlyMode">
                <option v-for="option in SERVICE_GENERATION_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
              </select>
              <small class="hint">{{ SERVICE_GENERATION_OPTIONS.find((option) => option.value === definition.generation.service_generation_mode)?.description }}</small>
              <small v-for="message in messagesForPath('generation.service_generation_mode')" :key="message" class="field-error-copy">{{ message }}</small>
            </label>

            <label class="field generation-field" :class="{ 'field-error': hasIssueForPath('generation.scalability_profile') }">
              <span class="required-label">Scalability posture</span>
              <select v-model="definition.generation.scalability_profile" class="select" :disabled="readOnlyMode">
                <option v-for="option in SCALABILITY_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
              </select>
              <small class="hint">{{ SCALABILITY_OPTIONS.find((option) => option.value === definition.generation.scalability_profile)?.description }}</small>
              <small v-for="message in messagesForPath('generation.scalability_profile')" :key="message" class="field-error-copy">{{ message }}</small>
            </label>

            <label class="field generation-field" :class="{ 'field-error': hasIssueForPath('generation.codegen_adapter') }">
              <span class="required-label">Primary code generation adapter</span>
              <select v-model="definition.generation.codegen_adapter" class="select" :disabled="readOnlyMode">
                <option v-for="option in ADAPTER_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
              </select>
              <small class="hint">{{ ADAPTER_OPTIONS.find((option) => option.value === definition.generation.codegen_adapter)?.description }}</small>
              <small v-for="message in messagesForPath('generation.codegen_adapter')" :key="message" class="field-error-copy">{{ message }}</small>
            </label>

            <label class="field generation-field" :class="{ 'field-error': hasIssueForPath('generation.layout_strategy') }">
              <span class="required-label">Repository / package layout</span>
              <select v-model="definition.generation.layout_strategy" class="select" :disabled="readOnlyMode">
                <option v-for="option in LAYOUT_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
              </select>
              <small class="hint">{{ LAYOUT_OPTIONS.find((option) => option.value === definition.generation.layout_strategy)?.description }}</small>
              <small v-for="message in messagesForPath('generation.layout_strategy')" :key="message" class="field-error-copy">{{ message }}</small>
            </label>

            <label class="field generation-field" :class="{ 'field-error': hasIssueForPath('naming.namespace') }">
              <span class="required-label">Package namespace</span>
              <input v-model="definition.naming.namespace" class="input" placeholder="e.g. revenue_operations" :disabled="readOnlyMode" />
              <small v-for="message in messagesForPath('naming.namespace')" :key="message" class="field-error-copy">{{ message }}</small>
            </label>

            <label class="field generation-field" :class="{ 'field-error': hasIssueForPath('naming.package_prefix') }">
              <span class="required-label">Package prefix</span>
              <input v-model="definition.naming.package_prefix" class="input" placeholder="e.g. operations_ops" :disabled="readOnlyMode" />
              <small v-for="message in messagesForPath('naming.package_prefix')" :key="message" class="field-error-copy">{{ message }}</small>
            </label>

            <label class="field generation-field" :class="{ 'field-error': hasIssueForPath('naming.service_name_prefix') }">
              <span class="required-label">Service name prefix</span>
              <input v-model="definition.naming.service_name_prefix" class="input" placeholder="e.g. operations" :disabled="readOnlyMode" />
              <small v-for="message in messagesForPath('naming.service_name_prefix')" :key="message" class="field-error-copy">{{ message }}</small>
            </label>

            <label class="field field-wide generation-field">
              <span>Formalization Rationale</span>
              <textarea v-model="definition.rationale" class="textarea" rows="3" placeholder="Explain why this generation profile is the right technical formalization of the locked Product Design baseline." :disabled="readOnlyMode" />
            </label>
          </div>

          <div class="protocol-section generation-selection-section edit-only" :class="{ 'field-error-card': hasIssueForPath('generation.protocols') }">
            <div class="selection-heading">
              <span class="summary-label required-label">Protocols</span>
              <p class="panel-copy small-copy">Choose every protocol surface the generated service must expose.</p>
            </div>
            <div class="chip-grid">
              <button
                v-for="protocol in PROTOCOL_OPTIONS"
                :key="protocol.value"
                class="chip"
                :class="{ active: definition.generation.protocols.includes(protocol.value) }"
                type="button"
                :disabled="readOnlyMode"
                @click="toggleProtocol(protocol.value)"
              >
                {{ protocol.label }}
              </button>
            </div>
            <small v-for="message in messagesForPath('generation.protocols')" :key="message" class="field-error-copy">{{ message }}</small>
          </div>

          <div class="review-summary-grid review-only">
            <div class="review-summary-card"><strong>Protocols</strong><span>{{ formatDeveloperList(definition.generation.protocols) }}</span></div>
            <div class="review-summary-card"><strong>Selected Services</strong><span>{{ definition.generation.selected_service_ids.length }} / {{ serviceOptions.length }}</span></div>
          </div>

          <div
            class="protocol-section generation-selection-section edit-only"
            :class="{ 'field-error-card': hasIssueForPath('generation.selected_service_ids') }"
            v-if="serviceOptions.length"
          >
            <div class="selection-heading">
              <span class="summary-label required-label">Service Boundaries Selected For Generation</span>
              <p class="panel-copy small-copy">Only selected formalized service boundaries will be emitted by generation.</p>
            </div>
            <div class="chip-grid">
              <button
                v-for="service in serviceOptions"
                :key="service.id"
                class="chip"
                :class="{ active: definition.generation.selected_service_ids.includes(service.id) }"
                type="button"
                :disabled="readOnlyMode"
                @click="toggleServiceSelection(service.id)"
              >
                {{ service.label }}
              </button>
            </div>
            <small v-for="message in messagesForPath('generation.selected_service_ids')" :key="message" class="field-error-copy">{{ message }}</small>
          </div>
        </article>

        <article class="panel panel-full generation-output-panel">
          <div class="panel-header">
            <div>
              <h2>What This Will Generate</h2>
              <p class="panel-copy compact-copy">A readable summary of the generated scaffold implied by the current settings.</p>
            </div>
          </div>
          <ul class="summary-list generated-summary-list">
            <li v-for="line in generatedCodeSummary" :key="line">{{ line }}</li>
          </ul>
        </article>
      </section>
    </template>
  </div>
</template>

<style scoped src="./developer-definition-shared.css"></style>

<style scoped>
.generation-settings-page .page-header {
  max-width: 980px;
}

.generation-layout {
  align-items: start;
}

.generation-settings-page .panel-header h2 {
  margin: 0;
}

.readonly-banner {
  margin: 0 0 1rem;
}

.generation-settings-page .btn:disabled,
.generation-settings-page .chip:disabled,
.generation-settings-page .input:disabled,
.generation-settings-page .select:disabled,
.generation-settings-page .textarea:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.compact-copy {
  margin: 0.35rem 0 0;
}

.why-copy {
  color: var(--text-primary);
  background: rgba(14, 165, 233, 0.08);
  border: 1px solid rgba(125, 211, 252, 0.16);
  border-radius: 14px;
  padding: 0.75rem 0.9rem;
}

.generation-settings-page .header-actions {
  flex: 0 0 auto;
  justify-content: flex-end;
}

.generation-settings-page .btn {
  width: auto;
  white-space: nowrap;
}

.generation-settings-page .settings-grid {
  margin-top: 1.25rem;
  gap: 1rem;
}

.generation-field {
  border: 1px solid var(--surface-border-card);
  border-radius: 16px;
  padding: 1rem;
  background: var(--surface-depth-card);
}

.generation-field.field-error,
.generation-selection-section.field-error-card {
  border-color: rgba(248, 113, 113, 0.66);
  background:
    linear-gradient(135deg, rgba(127, 29, 29, 0.26), rgba(15, 23, 42, 0.28)),
    rgba(15, 23, 42, 0.24);
  box-shadow: 0 0 0 1px rgba(248, 113, 113, 0.18), 0 18px 40px rgba(127, 29, 29, 0.12);
}

.generation-field > span {
  color: var(--text-primary);
  font-weight: 700;
}

.generation-field .hint {
  margin-top: 0.1rem;
}

.generation-selection-section {
  margin-top: 1.25rem;
  padding-top: 1.25rem;
  border-top: 1px solid rgba(148, 163, 184, 0.14);
}

.selection-heading {
  margin-bottom: 0.7rem;
}

.selection-heading .summary-label {
  margin-bottom: 0.25rem;
}

.generation-settings-page .chip-grid {
  gap: 0.6rem;
}

.generation-settings-page .chip {
  padding: 0.45rem 0.85rem;
  border-radius: 999px;
}

.generation-output-panel {
  background:
    radial-gradient(circle at top left, rgba(59, 130, 246, 0.14), transparent 34%),
    rgba(15, 23, 42, 0.42);
}

.generated-summary-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
  padding: 0;
  list-style: none;
}

.generated-summary-list li {
  margin: 0;
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  padding: 0.85rem 0.95rem;
  background: var(--surface-depth-card);
  color: var(--text-primary);
  line-height: 1.5;
}

.generated-summary-list li::before {
  content: '';
  display: inline-block;
  width: 0.42rem;
  height: 0.42rem;
  margin-right: 0.55rem;
  border-radius: 999px;
  background: #60a5fa;
  vertical-align: 0.08rem;
}

@media (max-width: 960px) {
  .generation-settings-page .panel-header {
    flex-direction: column;
    align-items: stretch;
  }

  .generation-settings-page .header-actions {
    justify-content: flex-start;
  }

  .generated-summary-list {
    grid-template-columns: 1fr;
  }
}
</style>
