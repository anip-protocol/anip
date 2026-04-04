<script setup lang="ts">
import type { GuidedQuestion } from '../guided/types'
import FieldChip from './FieldChip.vue'

const props = defineProps<{
  question: GuidedQuestion
  modelValue: any
  showMappings: boolean
  readonly: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: any]
}>()

function onBooleanToggle() {
  if (props.readonly) return
  emit('update:modelValue', !props.modelValue)
}

function onSelectChange(event: Event) {
  if (props.readonly) return
  emit('update:modelValue', (event.target as HTMLSelectElement).value)
}

function onTextInput(event: Event) {
  if (props.readonly) return
  emit('update:modelValue', (event.target as HTMLInputElement | HTMLTextAreaElement).value)
}
</script>

<template>
  <div class="guided-question" :class="{ readonly }">
    <div class="question-header">
      <span class="question-prompt">{{ question.prompt }}</span>
      <span v-if="question.helpText" class="question-help">{{ question.helpText }}</span>
    </div>

    <div class="question-answer">
      <template v-if="question.answerType === 'boolean'">
        <button
          class="toggle-switch"
          :class="{ on: modelValue, off: !modelValue }"
          :disabled="readonly"
          type="button"
          @click="onBooleanToggle"
        >
          {{ modelValue ? 'Yes' : 'No' }}
        </button>
      </template>

      <template v-else-if="question.answerType === 'select'">
        <select
          class="form-select"
          :value="modelValue"
          :disabled="readonly"
          @change="onSelectChange"
        >
          <option
            v-for="opt in question.options"
            :key="opt.value"
            :value="opt.value"
          >
            {{ opt.label }}
          </option>
        </select>
        <span
          v-if="question.options?.find(o => o.value === modelValue)?.description"
          class="option-desc"
        >
          {{ question.options?.find(o => o.value === modelValue)?.description }}
        </span>
      </template>

      <template v-else-if="question.answerType === 'text'">
        <textarea
          v-if="question.multiline"
          class="form-textarea"
          :value="modelValue"
          :disabled="readonly"
          :placeholder="question.helpText ?? ''"
          rows="4"
          @input="onTextInput"
        ></textarea>
        <input
          v-else
          class="form-input"
          type="text"
          :value="modelValue"
          :disabled="readonly"
          :placeholder="question.helpText ?? ''"
          @input="onTextInput"
        />
      </template>
    </div>

    <div v-if="showMappings && question.fieldMappings.length > 0" class="field-mappings">
      <FieldChip
        v-for="mapping in question.fieldMappings"
        :key="mapping.path"
        :path="mapping.path"
        :label="mapping.label"
      />
    </div>
  </div>
</template>

<style scoped>
.guided-question {
  padding: 12px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.guided-question:last-child {
  border-bottom: none;
}

.question-header {
  margin-bottom: 8px;
}

.question-prompt {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  display: block;
  margin-bottom: 2px;
}

.question-help {
  font-size: 12px;
  color: var(--text-muted);
  display: block;
}

.question-answer {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.option-desc {
  font-size: 12px;
  color: var(--text-muted);
}

.field-mappings {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 4px;
}

.toggle-switch {
  padding: 4px 14px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border-radius: 12px;
  border: 1px solid var(--border);
  cursor: pointer;
  transition: all var(--transition);
  min-width: 60px;
  text-align: center;
  background: transparent;
  color: var(--text-muted);
}

.toggle-switch.on {
  background: rgba(52, 211, 153, 0.12);
  color: var(--success);
  border-color: rgba(52, 211, 153, 0.3);
}

.toggle-switch:disabled {
  opacity: 0.5;
  cursor: default;
}

.toggle-switch:hover:not(:disabled) {
  background: var(--bg-hover);
}

.form-select {
  font-size: 13px;
  padding: 6px 10px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  outline: none;
  cursor: pointer;
}

.form-select:disabled {
  opacity: 0.5;
  cursor: default;
}

.form-input,
.form-textarea {
  font-size: 13px;
  padding: 6px 10px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  outline: none;
  width: 100%;
  max-width: 400px;
  box-sizing: border-box;
}

.form-textarea {
  min-height: 92px;
  resize: vertical;
  line-height: 1.45;
  font-family: inherit;
}

.form-input:disabled,
.form-textarea:disabled {
  opacity: 0.5;
  cursor: default;
}

.readonly .question-prompt {
  color: var(--text-secondary);
}
</style>
