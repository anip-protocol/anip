<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { designStore, setActivePack, runLiveValidation } from '../design/store'

const route = useRoute()

const pack = computed(() => {
  const id = route.params.pack as string
  if (id) setActivePack(id)
  return designStore.packs.find(p => p.meta.id === id) ?? null
})

const isLive = computed(() => designStore.liveEvaluation !== null)

const evaluation = computed(() => {
  if (designStore.liveEvaluation) {
    return designStore.liveEvaluation.evaluation
  }
  return pack.value?.evaluation?.evaluation ?? null
})

function clearLive() {
  designStore.liveEvaluation = null
  designStore.validationError = null
}

function categoryColor(cat: string): string {
  const colors: Record<string, string> = {
    safety: 'var(--design-category-safety)',
    orchestration: 'var(--design-category-orchestration)',
    observability: 'var(--design-category-observability)',
    cross_service: 'var(--design-category-cross-service)',
  }
  return colors[cat] || 'var(--text-muted)'
}
</script>

<template>
  <div class="evaluation-view" v-if="pack && evaluation">
    <div class="header-row">
      <h1 class="page-title">Evaluation: {{ pack.meta.name }}</h1>
      <div class="header-actions">
        <span class="source-badge live" v-if="isLive">Live result</span>
        <span class="source-badge precomputed" v-else>Pre-computed</span>
        <button
          v-if="designStore.apiAvailable && !designStore.validating"
          class="run-btn"
          @click="runLiveValidation"
        >Run Validation</button>
        <span v-if="designStore.validating" class="spinner"></span>
        <button
          v-if="isLive"
          class="reset-btn"
          @click="clearLive"
        >Reset to pre-computed</button>
      </div>
    </div>

    <!-- Validation error -->
    <div class="validation-error" v-if="designStore.validationError">
      {{ designStore.validationError }}
    </div>

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

.header-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
}

.page-title {
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.source-badge {
  display: inline-block;
  font-size: 11px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 10px;
}

.source-badge.live {
  background: rgba(59, 130, 246, 0.15);
  color: #3b82f6;
}

.source-badge.precomputed {
  background: rgba(156, 163, 175, 0.15);
  color: #9ca3af;
}

.run-btn {
  font-size: 12px;
  font-weight: 600;
  padding: 5px 14px;
  border-radius: 6px;
  border: 1px solid rgba(59, 130, 246, 0.4);
  background: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
  cursor: pointer;
  transition: background 0.15s;
}

.run-btn:hover {
  background: rgba(59, 130, 246, 0.2);
}

.reset-btn {
  font-size: 12px;
  font-weight: 500;
  padding: 5px 12px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: background 0.15s;
}

.reset-btn:hover {
  background: rgba(156, 163, 175, 0.1);
}

.spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(59, 130, 246, 0.3);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.validation-error {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #ef4444;
  font-size: 13px;
  padding: 8px 12px;
  border-radius: 6px;
  margin-bottom: 1rem;
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
