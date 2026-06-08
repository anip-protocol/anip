<script setup lang="ts">
import { ref, computed } from 'vue'
import type { GuidedSection } from '../guided/types'
import GuidedQuestion from './GuidedQuestion.vue'

const props = defineProps<{
  section: GuidedSection
  answers: Record<string, any>
  showMappings: boolean
  readonly: boolean
  /** Map from question ID → error messages */
  questionErrors?: Record<string, string[]>
  /** Errors not mapped to any question in this section */
  unmappedErrors?: string[]
}>()

const emit = defineEmits<{
  'update:answer': [questionId: string, value: any]
}>()

const collapsed = ref(false)
const helpExpanded = ref(false)
const helpDialogOpen = ref(false)

const sectionErrorCount = computed(() => {
  if (!props.questionErrors) return 0
  let count = 0
  for (const q of props.section.questions) {
    count += (props.questionErrors[q.id]?.length ?? 0)
  }
  count += (props.unmappedErrors?.length ?? 0)
  return count
})

function onAnswerUpdate(questionId: string, value: any) {
  emit('update:answer', questionId, value)
}

const hasInlineHelp = computed(() => {
  return Boolean(props.section.inlineDetails?.length)
})

const hasHelpDialog = computed(() => {
  const dialog = props.section.helpDialog
  return Boolean(dialog?.summary || dialog?.bullets?.length || dialog?.example || dialog?.decisionOwner)
})
</script>

<template>
  <div class="guided-section">
    <div class="section-header" @click="collapsed = !collapsed">
      <div class="section-title-row">
        <span class="collapse-icon">{{ collapsed ? '\u25b8' : '\u25be' }}</span>
        <h2 class="section-title">{{ section.title }}</h2>
        <span v-if="sectionErrorCount > 0" class="section-error-badge">{{ sectionErrorCount }} {{ sectionErrorCount === 1 ? 'error' : 'errors' }}</span>
        <span class="question-count">{{ section.questions.length }} questions</span>
      </div>
      <p class="section-description">{{ section.description }}</p>
      <div v-if="hasInlineHelp || hasHelpDialog" class="section-help-actions" @click.stop>
        <button v-if="hasInlineHelp" class="help-link" type="button" @click="helpExpanded = !helpExpanded">
          {{ helpExpanded ? 'Hide help' : 'What does this mean?' }}
        </button>
        <button v-if="hasHelpDialog" class="help-link secondary" type="button" @click="helpDialogOpen = true">
          More detail
        </button>
      </div>
      <div v-if="helpExpanded && section.inlineDetails?.length" class="inline-help">
        <ul class="inline-help-list">
          <li v-for="detail in section.inlineDetails" :key="detail">{{ detail }}</li>
        </ul>
      </div>
    </div>
    <div v-if="!collapsed" class="section-body">
      <GuidedQuestion
        v-for="q in section.questions"
        :key="q.id"
        :question="q"
        :modelValue="answers[q.id]"
        :showMappings="showMappings"
        :readonly="readonly"
        :errors="props.questionErrors?.[q.id]"
        @update:modelValue="onAnswerUpdate(q.id, $event)"
      />
      <div v-if="props.unmappedErrors?.length" class="unmapped-errors">
        <span v-for="(err, i) in props.unmappedErrors" :key="i" class="unmapped-error">{{ err }}</span>
      </div>
    </div>

    <div v-if="helpDialogOpen && section.helpDialog" class="help-dialog-backdrop" @click.self="helpDialogOpen = false">
      <div class="help-dialog">
        <div class="help-dialog-header">
          <h3 class="help-dialog-title">{{ section.helpDialog.title ?? section.title }}</h3>
          <button class="help-dialog-close" type="button" @click="helpDialogOpen = false">Close</button>
        </div>
        <p v-if="section.helpDialog.summary" class="help-dialog-summary">{{ section.helpDialog.summary }}</p>
        <ul v-if="section.helpDialog.bullets?.length" class="help-dialog-list">
          <li v-for="item in section.helpDialog.bullets" :key="item">{{ item }}</li>
        </ul>
        <div v-if="section.helpDialog.example" class="help-dialog-block">
          <span class="help-dialog-label">Example</span>
          <p class="help-dialog-text">{{ section.helpDialog.example }}</p>
        </div>
        <div v-if="section.helpDialog.decisionOwner" class="help-dialog-block">
          <span class="help-dialog-label">Who usually decides this?</span>
          <p class="help-dialog-text">{{ section.helpDialog.decisionOwner }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.guided-section {
  background: var(--bg-input, #1a1a2e);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm, 6px);
  margin-bottom: 16px;
  overflow: visible;
}

.section-header {
  padding: 16px 20px 12px;
  cursor: pointer;
  user-select: none;
}

.section-header:hover {
  background: rgba(255, 255, 255, 0.02);
}

.section-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.collapse-icon {
  font-size: 12px;
  color: var(--text-muted);
  width: 12px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  flex: 1;
}

.question-count {
  font-size: 12px;
  color: var(--text-muted);
}

.section-description {
  font-size: 13px;
  color: var(--text-muted);
  margin: 4px 0 0 20px;
}

.section-help-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin: 10px 0 0 20px;
}

.help-link {
  border: none;
  background: transparent;
  color: var(--accent, #8b8cff);
  font-size: 12px;
  font-weight: 600;
  padding: 0;
  cursor: pointer;
}

.help-link.secondary {
  color: var(--text-muted);
}

.inline-help {
  margin: 10px 0 0 20px;
  padding: 12px 14px;
  border-radius: 8px;
  background: rgba(96, 165, 250, 0.04);
  border: 1px solid rgba(96, 165, 250, 0.15);
}

.inline-help-list {
  margin: 0;
  padding-left: 18px;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.section-body {
  padding: 0 20px 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.04);
}

.section-error-badge {
  font-size: 11px;
  font-weight: 600;
  color: var(--error, #f87171);
  background: rgba(248, 113, 113, 0.1);
  border: 1px solid rgba(248, 113, 113, 0.25);
  border-radius: 10px;
  padding: 2px 10px;
}

.unmapped-errors {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 0;
  border-top: 1px solid rgba(248, 113, 113, 0.15);
  margin-top: 8px;
}

.unmapped-error {
  font-size: 12px;
  color: var(--error, #f87171);
  font-weight: 500;
}

.help-dialog-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(10, 10, 15, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  z-index: 200;
}

.help-dialog {
  width: min(720px, 100%);
  max-height: min(80vh, 760px);
  overflow: auto;
  background: var(--bg-panel, #13131d);
  border: 1px solid var(--border);
  border-radius: 12px;
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.35);
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
  border-radius: 8px;
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.help-dialog-summary,
.help-dialog-text {
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-secondary);
  margin: 0;
}

.help-dialog-list {
  margin: 14px 0;
  padding-left: 18px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.help-dialog-block {
  margin-top: 14px;
}

.help-dialog-label {
  display: block;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: 4px;
}
</style>
