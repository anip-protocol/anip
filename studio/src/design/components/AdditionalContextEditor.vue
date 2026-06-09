<script setup lang="ts">
import { computed } from 'vue'
import { requestConfirmation } from '../confirm'
import type { ScenarioAdditionalContextSemanticType } from '../types'

export interface AdditionalContextEntry {
  key: string
  value: string
  semantic_type: ScenarioAdditionalContextSemanticType
  description: string
}

const SEMANTIC_TYPE_OPTIONS: Array<{
  value: ScenarioAdditionalContextSemanticType
  label: string
  hint: string
  implementation_effect: string
}> = [
  {
    value: 'descriptive_only',
    label: 'Descriptive Only',
    hint: 'Reference-only context. Developer Design should not treat this as generation-driving input.',
    implementation_effect: 'No direct code-generation effect. This stays as source context for review and verification only.',
  },
  {
    value: 'actor_context',
    label: 'Actor Context',
    hint: 'Use when this entry defines who is calling or which caller posture the scenario depends on.',
    implementation_effect: 'Prefills the scenario actor context in Developer Definition, which can affect approvals, restrictions, trust posture, and visibility behavior.',
  },
  {
    value: 'business_scope',
    label: 'Business Scope',
    hint: 'Use for region, tenant, segment, team, or ownership boundaries that implementation must preserve.',
    implementation_effect: 'Prefills the scenario business scope in Developer Definition, which should constrain generated filters, ownership boundaries, or scoped access behavior.',
  },
  {
    value: 'time_scope',
    label: 'Time Scope',
    hint: 'Use for quarters, date windows, reporting periods, or other explicit time boundaries.',
    implementation_effect: 'Prefills the scenario time scope in Developer Definition, which should constrain generated filters, bounded reads, or time-windowed verification.',
  },
  {
    value: 'participating_services',
    label: 'Participating Services',
    hint: 'Use when this entry names which service boundaries are involved in the scenario.',
    implementation_effect: 'Prefills which services this scenario should involve so generation and verification do not assume every service participates.',
  },
  {
    value: 'orchestration_step',
    label: 'Orchestration Step',
    hint: 'Use when this entry defines one ordered step or handoff the implementation must preserve.',
    implementation_effect: 'Prefills ordered scenario steps in Developer Definition so orchestration is explicit instead of inferred from narrative text.',
  },
]

const props = defineProps<{
  modelValue: AdditionalContextEntry[]
  readonly?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: AdditionalContextEntry[]]
}>()

const entries = computed(() => props.modelValue ?? [])

function updateEntry(index: number, patch: Partial<AdditionalContextEntry>) {
  const next = entries.value.map((entry, currentIndex) => {
    if (currentIndex !== index) return entry
    return { ...entry, ...patch }
  })
  emit('update:modelValue', next)
}

function addEntry() {
  emit('update:modelValue', [
    ...entries.value,
    {
      key: '',
      value: '',
      semantic_type: 'descriptive_only',
      description: '',
    },
  ])
}

async function removeEntry(index: number) {
  const confirmed = await requestConfirmation({
    title: 'Remove this context entry?',
    message: 'This will remove the key, value, semantic meaning, and description from the scenario.',
    confirmLabel: 'Remove Entry',
    cancelLabel: 'Cancel',
    tone: 'danger',
  })
  if (!confirmed) return
  emit('update:modelValue', entries.value.filter((_, currentIndex) => currentIndex !== index))
}
</script>

<template>
  <div class="additional-context-editor">
    <div class="editor-help">
      Product Design should define the meaning of scenario context here. Developer Design will consume typed entries deterministically instead of guessing from raw key names.
    </div>

    <details class="help-panel">
      <summary>How Additional Context affects implementation</summary>
      <div class="help-grid">
        <div v-for="option in SEMANTIC_TYPE_OPTIONS" :key="option.value" class="help-card">
          <h4>{{ option.label }}</h4>
          <p><strong>Use it for:</strong> {{ option.hint }}</p>
          <p><strong>Implementation effect:</strong> {{ option.implementation_effect }}</p>
        </div>
      </div>
    </details>

    <div v-if="entries.length === 0" class="empty-state">
      No additional context entries yet.
    </div>

    <div v-for="(entry, index) in entries" :key="index" class="context-entry">
      <div class="entry-header">
        <div class="entry-main">
          <div class="entry-grid">
            <label class="field">
              <span class="field-label">Key</span>
              <input
                class="field-input"
                type="text"
                :value="entry.key"
                :disabled="readonly"
                placeholder="e.g. actor"
                @input="updateEntry(index, { key: ($event.target as HTMLInputElement).value })"
              />
            </label>

            <label class="field">
              <span class="field-label">Value</span>
              <input
                class="field-input"
                type="text"
                :value="entry.value"
                :disabled="readonly"
                placeholder="e.g. rev_ops_manager"
                @input="updateEntry(index, { value: ($event.target as HTMLInputElement).value })"
              />
            </label>
          </div>

          <label class="field semantic-field">
            <span class="field-label">Meaning In Developer Design</span>
            <select
              class="field-select"
              :value="entry.semantic_type"
              :disabled="readonly"
              @change="updateEntry(index, { semantic_type: ($event.target as HTMLSelectElement).value as ScenarioAdditionalContextSemanticType })"
            >
              <option
                v-for="option in SEMANTIC_TYPE_OPTIONS"
                :key="option.value"
                :value="option.value"
              >
                {{ option.label }}
              </option>
            </select>
            <small class="field-note">
              {{ SEMANTIC_TYPE_OPTIONS.find((option) => option.value === entry.semantic_type)?.hint }}
            </small>
          </label>
        </div>

        <button
          v-if="!readonly"
          class="remove-btn"
          type="button"
          @click="removeEntry(index)"
        >
          Remove
        </button>
      </div>

      <label class="field description-field">
        <span class="field-label">Description</span>
        <textarea
          class="field-textarea"
          :value="entry.description"
          :disabled="readonly"
          rows="3"
          placeholder="Explain what this means and why it matters in the scenario."
          @input="updateEntry(index, { description: ($event.target as HTMLTextAreaElement).value })"
        ></textarea>
      </label>
    </div>

    <button v-if="!readonly" class="add-btn" type="button" @click="addEntry">
      + Add Context Entry
    </button>
  </div>
</template>

<style scoped>
.additional-context-editor {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.empty-state {
  font-size: 13px;
  color: var(--text-muted);
  padding: 12px 14px;
  border: 1px dashed var(--border);
  border-radius: 8px;
}

.editor-help {
  font-size: 13px;
  line-height: 1.5;
  color: var(--text-secondary);
}

.help-panel {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px 14px;
  background: rgba(255, 255, 255, 0.02);
}

.help-panel summary {
  cursor: pointer;
  font-weight: 600;
}

.help-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
  margin-top: 12px;
}

.help-card {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.02);
}

.help-card h4 {
  margin: 0 0 8px;
}

.help-card p {
  margin: 0 0 8px;
  font-size: 13px;
  line-height: 1.5;
  color: var(--text-secondary);
}

.help-card p:last-child {
  margin-bottom: 0;
}

.context-entry {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px;
  background: rgba(255, 255, 255, 0.02);
}

.entry-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.entry-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 12px;
  flex: 1;
}

.entry-main {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 12px;
}

.semantic-field {
  max-width: 420px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.field-input,
.field-select,
.field-textarea {
  width: 100%;
  box-sizing: border-box;
  font-size: 13px;
  padding: 8px 10px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  outline: none;
  font-family: inherit;
}

.field-note {
  font-size: 12px;
  line-height: 1.4;
  color: var(--text-muted);
}

.field-textarea {
  resize: vertical;
  line-height: 1.5;
  max-width: 100%;
  min-width: 0;
  overflow-wrap: anywhere;
}

.description-field {
  margin-top: 12px;
}

.remove-btn,
.add-btn {
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-secondary);
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.add-btn:hover {
  border-color: var(--accent);
  color: var(--text-primary);
}

.remove-btn {
  color: var(--error);
  border-color: rgba(248, 113, 113, 0.3);
}

.remove-btn:hover {
  background: rgba(248, 113, 113, 0.1);
}

.add-btn {
  align-self: flex-start;
}

@media (max-width: 960px) {
  .entry-header {
    flex-direction: column;
  }

  .entry-grid {
    grid-template-columns: 1fr;
  }
}
</style>
