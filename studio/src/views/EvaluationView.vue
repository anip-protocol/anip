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

const evaluation = computed(() => pack.value?.evaluation?.evaluation ?? null)

const categoryColors: Record<string, string> = {
  auth: '#60a5fa',
  discovery: '#a78bfa',
  transport: '#34d399',
  audit: '#fbbf24',
  lineage: '#f472b6',
  checkpoints: '#fb923c',
  permissions: '#2dd4bf',
  manifest: '#818cf8',
}

function categoryColor(cat: string): string {
  const lower = cat.toLowerCase()
  for (const [key, color] of Object.entries(categoryColors)) {
    if (lower.includes(key)) return color
  }
  return '#94a3b8'
}
</script>

<template>
  <div class="evaluation-view" v-if="pack && evaluation">
    <h1 class="page-title">Evaluation: {{ pack.meta.name }}</h1>

    <!-- Result badge -->
    <div class="result-badge" :class="'result-' + evaluation.result.toLowerCase().replace('_', '-')">
      {{ evaluation.result }}
    </div>

    <!-- Confidence -->
    <div class="confidence" v-if="evaluation.confidence">
      <span class="confidence-label">Confidence:</span>
      <span class="confidence-value">{{ evaluation.confidence }}</span>
    </div>

    <!-- Glue categories -->
    <div class="categories-section" v-if="evaluation.glue_category && evaluation.glue_category.length">
      <h2>Categories</h2>
      <div class="pill-row">
        <span
          class="cat-pill"
          v-for="(cat, i) in evaluation.glue_category"
          :key="i"
          :style="{ background: categoryColor(cat) + '1a', color: categoryColor(cat), borderColor: categoryColor(cat) + '4d' }"
        >{{ cat }}</span>
      </div>
    </div>

    <!-- Handled by ANIP -->
    <div class="section">
      <h2>Handled by ANIP</h2>
      <ul>
        <li v-for="(item, i) in evaluation.handled_by_anip" :key="i">{{ item }}</li>
      </ul>
    </div>

    <!-- Glue You Will Still Write -->
    <div class="section" v-if="evaluation.glue_you_will_still_write && evaluation.glue_you_will_still_write.length">
      <h2>Glue You Will Still Write</h2>
      <ul class="glue-list">
        <li v-for="(item, i) in evaluation.glue_you_will_still_write" :key="i">{{ item }}</li>
      </ul>
    </div>

    <!-- Why -->
    <div class="section">
      <h2>Why</h2>
      <ul>
        <li v-for="(item, i) in evaluation.why" :key="i">{{ item }}</li>
      </ul>
    </div>

    <!-- What Would Improve -->
    <div class="section" v-if="evaluation.what_would_improve && evaluation.what_would_improve.length">
      <h2>What Would Improve</h2>
      <ul>
        <li v-for="(item, i) in evaluation.what_would_improve" :key="i">{{ item }}</li>
      </ul>
    </div>

    <!-- Notes -->
    <div class="section" v-if="evaluation.notes && evaluation.notes.length">
      <h2>Notes</h2>
      <ul class="notes-list">
        <li v-for="(note, i) in evaluation.notes" :key="i">{{ note }}</li>
      </ul>
    </div>
  </div>
  <div v-else-if="pack" class="not-found">No evaluation available for this pack.</div>
  <div v-else class="not-found">Pack not found.</div>
</template>

<style scoped>
.evaluation-view {
  padding: 2rem;
  max-width: 800px;
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
  margin-bottom: 0.75rem;
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

/* Confidence */
.confidence {
  margin-bottom: 1rem;
  font-size: 13px;
}

.confidence-label {
  color: var(--text-muted);
  font-weight: 500;
  margin-right: 6px;
}

.confidence-value {
  color: var(--text-secondary);
  font-weight: 600;
}

/* Categories */
.categories-section {
  margin-bottom: 1.5rem;
}

.categories-section h2 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 0.5rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border);
}

.pill-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.cat-pill {
  display: inline-block;
  font-size: 12px;
  font-weight: 600;
  padding: 3px 12px;
  border-radius: 12px;
  border: 1px solid;
}

.section {
  margin-bottom: 1.5rem;
}

.section h2 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 0.5rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border);
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

.notes-list li {
  color: var(--text-muted);
  font-style: italic;
}

.not-found {
  padding: 2rem;
  color: var(--text-muted);
}
</style>
