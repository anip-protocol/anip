<script setup lang="ts">
import { ref } from 'vue'
import type { GuidedSection } from '../guided/types'
import GuidedQuestion from './GuidedQuestion.vue'

defineProps<{
  section: GuidedSection
  answers: Record<string, any>
  showMappings: boolean
  readonly: boolean
}>()

const emit = defineEmits<{
  'update:answer': [questionId: string, value: any]
}>()

const collapsed = ref(false)

function onAnswerUpdate(questionId: string, value: any) {
  emit('update:answer', questionId, value)
}
</script>

<template>
  <div class="guided-section">
    <div class="section-header" @click="collapsed = !collapsed">
      <div class="section-title-row">
        <span class="collapse-icon">{{ collapsed ? '\u25b8' : '\u25be' }}</span>
        <h2 class="section-title">{{ section.title }}</h2>
        <span class="question-count">{{ section.questions.length }} questions</span>
      </div>
      <p class="section-description">{{ section.description }}</p>
    </div>
    <div v-if="!collapsed" class="section-body">
      <GuidedQuestion
        v-for="q in section.questions"
        :key="q.id"
        :question="q"
        :modelValue="answers[q.id]"
        :showMappings="showMappings"
        :readonly="readonly"
        @update:modelValue="onAnswerUpdate(q.id, $event)"
      />
    </div>
  </div>
</template>

<style scoped>
.guided-section {
  background: var(--bg-input, #1a1a2e);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm, 6px);
  margin-bottom: 16px;
  overflow: hidden;
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

.section-body {
  padding: 0 20px 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.04);
}
</style>
