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
  <div class="proposal-view" v-if="pack && pack.proposal">
    <h1 class="page-title">Proposal: {{ pack.meta.name }}</h1>
    <div class="section">
      <h2>Recommended Shape</h2>
      <p class="shape">{{ pack.proposal.proposal.recommended_shape }}</p>
    </div>
    <div class="section">
      <h2>Rationale</h2>
      <ul>
        <li v-for="(item, i) in pack.proposal.proposal.rationale" :key="i">{{ item }}</li>
      </ul>
    </div>
    <div class="section">
      <h2>Required Components</h2>
      <ul>
        <li v-for="(item, i) in pack.proposal.proposal.required_components" :key="i">{{ item }}</li>
      </ul>
    </div>
    <div class="section" v-if="pack.proposal.proposal.anti_pattern_warnings.length">
      <h2>Anti-pattern Warnings</h2>
      <ul class="warnings">
        <li v-for="(item, i) in pack.proposal.proposal.anti_pattern_warnings" :key="i">{{ item }}</li>
      </ul>
    </div>
  </div>
  <div v-else-if="pack" class="not-found">No proposal available for this pack.</div>
  <div v-else class="not-found">Pack not found.</div>
</template>

<style scoped>
.proposal-view {
  padding: 2rem;
}

.page-title {
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 1.5rem;
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

.shape {
  font-size: 14px;
  color: var(--accent);
  font-weight: 600;
  margin: 0;
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

.warnings li {
  color: var(--design-glue, #f87171);
}

.not-found {
  padding: 2rem;
  color: var(--text-muted);
}
</style>
