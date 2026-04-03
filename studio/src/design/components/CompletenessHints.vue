<script setup lang="ts">
import { ref } from 'vue'
import type { CompletenessHint } from '../guided/types'
import FieldChip from './FieldChip.vue'

defineProps<{
  hints: CompletenessHint[]
}>()

const expandedIds = ref<Set<string>>(new Set())

function toggleExpanded(id: string) {
  if (expandedIds.value.has(id)) {
    expandedIds.value.delete(id)
  } else {
    expandedIds.value.add(id)
  }
}
</script>

<template>
  <div class="completeness-hints" v-if="hints.length > 0">
    <h3 class="hints-title">
      Design Hints
      <span class="hint-count">{{ hints.length }}</span>
    </h3>
    <div
      v-for="hint in hints"
      :key="hint.id"
      class="hint-item"
      :class="hint.severity"
    >
      <div class="hint-header" @click="toggleExpanded(hint.id)">
        <span class="hint-icon">{{ hint.severity === 'warning' ? '\u26a0' : '\u2139' }}</span>
        <span class="hint-message">{{ hint.message }}</span>
        <span class="expand-icon">{{ expandedIds.has(hint.id) ? '\u25be' : '\u25b8' }}</span>
      </div>
      <div v-if="expandedIds.has(hint.id)" class="hint-detail">
        <p class="hint-explanation">{{ hint.explanation }}</p>
        <div class="hint-fields">
          <FieldChip
            v-for="field in hint.relatedFields"
            :key="field"
            :path="field"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.completeness-hints {
  margin-bottom: 16px;
}

.hints-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.hint-count {
  font-size: 11px;
  font-weight: 700;
  color: var(--text-muted);
  background: rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  padding: 1px 8px;
}

.hint-item {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm, 6px);
  margin-bottom: 6px;
  overflow: hidden;
}

.hint-item.warning {
  border-color: rgba(251, 191, 36, 0.3);
  background: rgba(251, 191, 36, 0.04);
}

.hint-item.info {
  border-color: rgba(96, 165, 250, 0.3);
  background: rgba(96, 165, 250, 0.04);
}

.hint-header {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 14px;
  cursor: pointer;
  user-select: none;
}

.hint-header:hover {
  background: rgba(255, 255, 255, 0.02);
}

.hint-icon {
  font-size: 14px;
  flex-shrink: 0;
  margin-top: 1px;
}

.hint-message {
  font-size: 13px;
  color: var(--text-secondary);
  flex: 1;
}

.expand-icon {
  font-size: 12px;
  color: var(--text-muted);
  flex-shrink: 0;
}

.hint-detail {
  padding: 0 14px 12px 36px;
}

.hint-explanation {
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.5;
  margin: 0 0 8px;
}

.hint-fields {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
</style>
