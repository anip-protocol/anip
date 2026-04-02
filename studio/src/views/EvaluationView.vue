<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { designStore, setActivePack } from '../design/store'

const route = useRoute()

const pack = computed(() => {
  const id = route.params.pack as string
  if (id) setActivePack(id)
  return designStore.packs.find(p => p.meta.id === id) ?? null
})
</script>

<template>
  <div class="evaluation-view" v-if="pack && pack.evaluation">
    <h1 class="page-title">Evaluation: {{ pack.meta.name }}</h1>
    <div class="result-badge" :class="'result-' + pack.evaluation.evaluation.result.toLowerCase().replace('_', '-')">
      {{ pack.evaluation.evaluation.result }}
    </div>
    <div class="section">
      <h2>Handled by ANIP</h2>
      <ul>
        <li v-for="(item, i) in pack.evaluation.evaluation.handled_by_anip" :key="i">{{ item }}</li>
      </ul>
    </div>
    <div class="section" v-if="pack.evaluation.evaluation.glue_you_will_still_write.length">
      <h2>Glue You Will Still Write</h2>
      <ul class="glue-list">
        <li v-for="(item, i) in pack.evaluation.evaluation.glue_you_will_still_write" :key="i">{{ item }}</li>
      </ul>
    </div>
    <div class="section">
      <h2>Why</h2>
      <ul>
        <li v-for="(item, i) in pack.evaluation.evaluation.why" :key="i">{{ item }}</li>
      </ul>
    </div>
    <div class="section" v-if="pack.evaluation.evaluation.what_would_improve.length">
      <h2>What Would Improve</h2>
      <ul>
        <li v-for="(item, i) in pack.evaluation.evaluation.what_would_improve" :key="i">{{ item }}</li>
      </ul>
    </div>
  </div>
  <div v-else-if="pack" class="not-found">No evaluation available for this pack.</div>
  <div v-else class="not-found">Pack not found.</div>
</template>

<style scoped>
.evaluation-view {
  padding: 2rem;
}

.page-title {
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 1rem;
}

.result-badge {
  display: inline-block;
  font-size: 13px;
  font-weight: 700;
  padding: 4px 14px;
  border-radius: 14px;
  margin-bottom: 1.5rem;
}

.result-handled {
  background: rgba(52, 211, 153, 0.15);
  color: var(--design-handled, #34d399);
}

.result-partial {
  background: rgba(251, 191, 36, 0.15);
  color: var(--design-partial, #fbbf24);
}

.result-requires-glue {
  background: rgba(248, 113, 113, 0.15);
  color: var(--design-glue, #f87171);
}

.section {
  margin-bottom: 1.5rem;
}

.section h2 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 0.5rem;
}

.section ul {
  list-style: disc;
  padding-left: 1.25rem;
  margin: 0;
}

.section li {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: 0.25rem;
}

.glue-list li {
  color: var(--design-glue, #f87171);
}

.not-found {
  padding: 2rem;
  color: var(--text-muted);
}
</style>
