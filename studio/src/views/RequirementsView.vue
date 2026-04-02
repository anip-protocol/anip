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
  <div class="requirements-view" v-if="pack">
    <h1 class="page-title">Requirements: {{ pack.meta.name }}</h1>
    <div class="section">
      <h2>System</h2>
      <dl class="info-grid">
        <dt>Name</dt><dd>{{ pack.requirements.system.name }}</dd>
        <dt>Domain</dt><dd>{{ pack.requirements.system.domain }}</dd>
        <dt>Deployment Intent</dt><dd>{{ pack.requirements.system.deployment_intent }}</dd>
      </dl>
    </div>
    <div class="section">
      <h2>Trust</h2>
      <dl class="info-grid">
        <dt>Mode</dt><dd>{{ pack.requirements.trust.mode }}</dd>
        <dt>Checkpoints</dt><dd>{{ pack.requirements.trust.checkpoints ? 'Yes' : 'No' }}</dd>
      </dl>
    </div>
  </div>
  <div v-else class="not-found">Pack not found.</div>
</template>

<style scoped>
.requirements-view {
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
  margin: 0 0 0.75rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border);
}

.info-grid {
  display: grid;
  grid-template-columns: 160px 1fr;
  gap: 0.5rem 1rem;
  margin: 0;
}

.info-grid dt {
  font-size: 13px;
  color: var(--text-muted);
  font-weight: 500;
}

.info-grid dd {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0;
}

.not-found {
  padding: 2rem;
  color: var(--text-muted);
}
</style>
