<script setup lang="ts">
import { computed, ref } from 'vue'
import type { GuidedQuestion } from '../guided/types'
import FieldChip from './FieldChip.vue'
import CustomSelect from './CustomSelect.vue'

const props = defineProps<{
  question: GuidedQuestion
  modelValue: any
  showMappings: boolean
  readonly: boolean
  errors?: string[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: any]
}>()

const helpExpanded = ref(false)
const helpDialogOpen = ref(false)

const charCount = computed(() => {
  if (props.question.answerType !== 'text' || !props.question.maxLength) return null
  const len = typeof props.modelValue === 'string' ? props.modelValue.length : 0
  return { current: len, max: props.question.maxLength, over: len > props.question.maxLength }
})

const defaultInlineSummary = computed(() => {
  if (props.question.helpText) return props.question.helpText
  if (props.question.answerType === 'boolean') return 'Choose Yes when this requirement should be explicitly expected in the system.'
  if (props.question.answerType === 'select') return 'Choose the option that best matches the intended product behavior.'
  return 'Answer in plain language so the business intent is clear before developer design begins.'
})

const defaultInlineDetails = computed(() => {
  if (props.question.inlineDetails?.length) return props.question.inlineDetails
  if (props.question.answerType === 'boolean') {
    return ['Use this to mark whether the behavior is required, not just technically possible.']
  }
  if (props.question.answerType === 'select') {
    return ['Each option maps to a structured value used later in the design flow.']
  }
  return ['This answer should describe intent in business terms rather than implementation detail.']
})

const defaultHelpDialog = computed(() => {
  const custom = props.question.helpDialog
  if (custom?.summary || custom?.bullets?.length || custom?.example || custom?.decisionOwner) {
    return custom
  }

  const bullets: string[] = []

  if (props.question.answerType === 'boolean') {
    bullets.push('Answer Yes when this should be an explicit product or governance expectation.')
    bullets.push('Answer No when the system does not need to guarantee this behavior.')
  } else if (props.question.answerType === 'select') {
    bullets.push('Choose the option that best captures the intended behavior at the current design stage.')
    if (props.question.options?.length) {
      bullets.push(`Available options: ${props.question.options.map((option) => option.label).join(', ')}.`)
    }
  } else {
    bullets.push('Use clear business language rather than internal implementation terms.')
    if (props.question.maxLength) {
      bullets.push(`Keep the answer within ${props.question.maxLength} characters.`)
    }
  }

  bullets.push('This answer feeds the project requirements summary and later design steps.')

  return {
    title: props.question.prompt,
    summary: defaultInlineSummary.value,
    bullets,
  }
})

const hasInlineHelp = computed(() => {
  return Boolean(defaultInlineSummary.value || defaultInlineDetails.value.length)
})

const hasHelpDialog = computed(() => {
  const dialog = defaultHelpDialog.value
  return Boolean(dialog?.summary || dialog?.bullets?.length || dialog?.example || dialog?.decisionOwner)
})

function onBooleanToggle() {
  if (props.readonly) return
  emit('update:modelValue', !props.modelValue)
}

function onTextInput(event: Event) {
  if (props.readonly) return
  emit('update:modelValue', (event.target as HTMLInputElement | HTMLTextAreaElement).value)
}

function toggleHelp() {
  helpExpanded.value = !helpExpanded.value
}

function openHelpDialog() {
  helpDialogOpen.value = true
}

function closeHelpDialog() {
  helpDialogOpen.value = false
}
</script>

<template>
  <div class="guided-question" :class="{ readonly, 'has-error': props.errors?.length }">
    <div class="question-header">
      <div class="question-title-row">
        <span class="question-prompt">{{ question.prompt }}</span>
        <div v-if="hasInlineHelp || hasHelpDialog" class="question-help-actions">
          <button v-if="hasInlineHelp" class="help-link" type="button" @click.stop="toggleHelp">
            {{ helpExpanded ? 'Hide help' : 'What does this mean?' }}
          </button>
          <button v-if="hasHelpDialog" class="help-link secondary" type="button" @click.stop="openHelpDialog">
            More detail
          </button>
        </div>
      </div>
      <div v-if="helpExpanded && hasInlineHelp" class="inline-help">
        <p v-if="defaultInlineSummary" class="inline-help-summary">{{ defaultInlineSummary }}</p>
        <ul v-if="defaultInlineDetails.length" class="inline-help-list">
          <li v-for="detail in defaultInlineDetails" :key="detail">{{ detail }}</li>
        </ul>
      </div>
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
        <CustomSelect
          :modelValue="modelValue"
          :options="question.options ?? []"
          :disabled="readonly"
          @update:modelValue="emit('update:modelValue', $event)"
        />
      </template>

      <template v-else-if="question.answerType === 'text'">
        <div class="text-input-wrapper">
          <textarea
            v-if="question.multiline"
            class="form-textarea"
            :value="modelValue"
            :disabled="readonly"
            :placeholder="question.helpText ?? ''"
            :maxlength="question.maxLength"
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
            :maxlength="question.maxLength"
            @input="onTextInput"
          />
          <span v-if="charCount && !readonly" class="char-counter" :class="{ over: charCount.over }">
            {{ charCount.current }}/{{ charCount.max }}
          </span>
        </div>
      </template>
    </div>

    <div v-if="props.errors?.length" class="question-errors">
      <span v-for="(err, i) in props.errors" :key="i" class="question-error">{{ err }}</span>
    </div>

    <div v-if="showMappings && question.fieldMappings.length > 0" class="field-mappings">
      <FieldChip
        v-for="mapping in question.fieldMappings"
        :key="mapping.path"
        :path="mapping.path"
        :label="mapping.label"
      />
    </div>

    <div v-if="helpDialogOpen && defaultHelpDialog" class="help-dialog-backdrop" @click.self="closeHelpDialog">
      <div class="help-dialog">
        <div class="help-dialog-header">
          <h3 class="help-dialog-title">{{ defaultHelpDialog.title ?? question.prompt }}</h3>
          <button class="help-dialog-close" type="button" @click="closeHelpDialog">Close</button>
        </div>
        <p v-if="defaultHelpDialog.summary" class="help-dialog-summary">
          {{ defaultHelpDialog.summary }}
        </p>
        <ul v-if="defaultHelpDialog.bullets?.length" class="help-dialog-list">
          <li v-for="item in defaultHelpDialog.bullets" :key="item">{{ item }}</li>
        </ul>
        <div v-if="defaultHelpDialog.example" class="help-dialog-block">
          <span class="help-dialog-label">Example</span>
          <p class="help-dialog-text">{{ defaultHelpDialog.example }}</p>
        </div>
        <div v-if="defaultHelpDialog.decisionOwner" class="help-dialog-block">
          <span class="help-dialog-label">Who usually decides this?</span>
          <p class="help-dialog-text">{{ defaultHelpDialog.decisionOwner }}</p>
        </div>
      </div>
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

.question-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.question-prompt {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  display: block;
  margin-bottom: 2px;
}

.question-help-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.help-link {
  border: none;
  background: transparent;
  color: var(--accent, #8b8cff);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  padding: 0;
}

.help-link.secondary {
  color: var(--text-muted);
}

.help-link:hover {
  text-decoration: underline;
}

.inline-help {
  margin-top: 8px;
  padding: 10px 12px;
  border: 1px solid rgba(139, 140, 255, 0.18);
  background: rgba(139, 140, 255, 0.06);
  border-radius: var(--radius-sm, 6px);
}

.inline-help-summary {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 0;
}

.inline-help-list {
  margin: 8px 0 0;
  padding-left: 18px;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.5;
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
  max-width: 600px;
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

.text-input-wrapper {
  display: flex;
  flex-direction: column;
  width: 100%;
  max-width: 600px;
}

.text-input-wrapper .form-input,
.text-input-wrapper .form-textarea {
  max-width: 100%;
}

.char-counter {
  font-size: 11px;
  color: var(--text-muted);
  text-align: right;
  margin-top: 2px;
  font-variant-numeric: tabular-nums;
}

.char-counter.over {
  color: var(--error, #f87171);
  font-weight: 600;
}

.guided-question.has-error {
  border-left: 3px solid var(--error, #f87171);
  padding-left: 12px;
  margin-left: -15px;
}

.help-dialog-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(7, 10, 20, 0.72);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  z-index: 1000;
}

.help-dialog {
  width: min(720px, 100%);
  max-height: min(80vh, 760px);
  overflow-y: auto;
  background: #11172a;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 14px;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.45);
  padding: 20px 22px;
}

.help-dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.help-dialog-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}

.help-dialog-close {
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-secondary);
  border-radius: 999px;
  padding: 6px 12px;
  cursor: pointer;
}

.help-dialog-summary,
.help-dialog-text {
  margin: 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.help-dialog-list {
  margin: 14px 0 0;
  padding-left: 20px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.help-dialog-block {
  margin-top: 16px;
}

.help-dialog-label {
  display: block;
  margin-bottom: 6px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.03em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.question-errors {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: 4px;
}

.question-error {
  font-size: 12px;
  color: var(--error, #f87171);
  font-weight: 500;
}
</style>
