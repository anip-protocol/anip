<!-- studio/src/design/components/ScenarioSummary.vue -->
<script setup lang="ts">
import { computed } from 'vue'
import { generateScenarioSummary } from '../guided/scenario-summary'

const props = defineProps<{
  scenario: Record<string, any>
}>()

const paragraphs = computed(() => generateScenarioSummary(props.scenario))
</script>

<template>
  <div class="scenario-summary" v-if="paragraphs.length > 0">
    <h3 class="summary-title">Scenario Summary</h3>
    <div class="summary-body">
      <p v-for="(para, i) in paragraphs" :key="i" class="summary-paragraph">
        {{ para }}
      </p>
    </div>
  </div>
</template>

<style scoped>
.scenario-summary {
  background: rgba(96, 165, 250, 0.04);
  border: 1px solid rgba(96, 165, 250, 0.15);
  border-radius: var(--radius-sm, 6px);
  padding: 16px 20px;
  margin-bottom: 16px;
}

.summary-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 8px;
}

.summary-body {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.summary-paragraph {
  margin: 0 0 6px;
}

.summary-paragraph:last-child {
  margin-bottom: 0;
}
</style>
