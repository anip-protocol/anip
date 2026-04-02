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

const proposal = computed(() => pack.value?.proposal?.proposal ?? null)

const glueCategories = computed(() => {
  if (!proposal.value?.expected_glue_reduction) return []
  return Object.entries(proposal.value.expected_glue_reduction)
})
</script>

<template>
  <div class="proposal-view" v-if="pack && proposal">
    <h1 class="page-title">Proposal: {{ pack.meta.name }}</h1>

    <!-- Shape header -->
    <div class="shape-header">
      <span class="shape-label">Recommended Shape</span>
      <span class="shape-value">{{ proposal.recommended_shape }}</span>
    </div>

    <!-- Rationale -->
    <div class="section">
      <h2>Rationale</h2>
      <ul>
        <li v-for="(item, i) in proposal.rationale" :key="i">{{ item }}</li>
      </ul>
    </div>

    <!-- Required Components -->
    <div class="section">
      <h2>Required Components</h2>
      <div class="pill-row">
        <span class="component-pill required" v-for="(item, i) in proposal.required_components" :key="i">
          {{ item }}
        </span>
      </div>
    </div>

    <!-- Optional Components -->
    <div class="section" v-if="proposal.optional_components && proposal.optional_components.length">
      <h2>Optional Components</h2>
      <div class="pill-row">
        <span class="component-pill optional" v-for="(item, i) in proposal.optional_components" :key="i">
          {{ item }}
        </span>
      </div>
    </div>

    <!-- Key Runtime Requirements -->
    <div class="section" v-if="proposal.key_runtime_requirements && proposal.key_runtime_requirements.length">
      <h2>Key Runtime Requirements</h2>
      <ul>
        <li v-for="(item, i) in proposal.key_runtime_requirements" :key="i">{{ item }}</li>
      </ul>
    </div>

    <!-- Anti-pattern Warnings -->
    <div class="section" v-if="proposal.anti_pattern_warnings && proposal.anti_pattern_warnings.length">
      <h2>Anti-pattern Warnings</h2>
      <ul class="warnings">
        <li v-for="(item, i) in proposal.anti_pattern_warnings" :key="i">{{ item }}</li>
      </ul>
    </div>

    <!-- Expected Glue Reduction -->
    <div class="section" v-if="glueCategories.length">
      <h2>Expected Glue Reduction</h2>
      <div class="glue-groups">
        <div class="glue-group" v-for="[category, items] in glueCategories" :key="category">
          <h3 class="glue-category-name">{{ category }}</h3>
          <ul>
            <li v-for="(item, i) in (items as string[])" :key="i">{{ item }}</li>
          </ul>
        </div>
      </div>
    </div>
  </div>
  <div v-else-if="pack" class="not-found">No proposal available for this pack.</div>
  <div v-else class="not-found">Pack not found.</div>
</template>

<style scoped>
.proposal-view {
  padding: 2rem;
  max-width: 800px;
}

.page-title {
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 1rem;
}

/* Shape header */
.shape-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 18px;
  background: var(--bg-input, #1a1a2e);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm, 6px);
  margin-bottom: 1.5rem;
}

.shape-label {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-muted);
}

.shape-value {
  font-size: 18px;
  font-weight: 700;
  color: var(--accent);
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

/* Component pills */
.pill-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.component-pill {
  display: inline-block;
  font-size: 13px;
  font-weight: 500;
  padding: 4px 14px;
  border-radius: 14px;
  border: 1px solid var(--border);
}

.component-pill.required {
  background: rgba(96, 165, 250, 0.12);
  color: #60a5fa;
  border-color: rgba(96, 165, 250, 0.3);
}

.component-pill.optional {
  background: transparent;
  color: var(--text-muted);
  opacity: 0.7;
}

/* Warning styling */
.warnings li {
  color: var(--design-glue, #f87171);
  font-weight: 500;
}

.warnings li::marker {
  content: '\26A0\0020';
}

/* Glue reduction groups */
.glue-groups {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.glue-group {
  padding: 12px 16px;
  background: var(--bg-input, #1a1a2e);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm, 6px);
}

.glue-category-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--accent);
  margin: 0 0 0.5rem;
}

.glue-group ul {
  list-style: disc;
  padding-left: 1.25rem;
  margin: 0;
}

.glue-group li {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
  margin-bottom: 0.2rem;
}

.not-found {
  padding: 2rem;
  color: var(--text-muted);
}
</style>
