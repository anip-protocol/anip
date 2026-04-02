<script setup lang="ts">
import { useRouter } from 'vue-router'
import { getPackMetas } from '../design/store'

const router = useRouter()
const packMetas = getPackMetas()

function selectPack(id: string) {
  router.push(`/design/scenarios/${id}`)
}
</script>

<template>
  <div class="scenario-browser">
    <h1 class="page-title">Scenario Packs</h1>
    <p class="page-desc">Select a pack to explore its requirements, proposal, and evaluation.</p>
    <div class="pack-grid">
      <div
        v-for="pack in packMetas"
        :key="pack.id"
        class="pack-card"
        @click="selectPack(pack.id)"
      >
        <div class="pack-header">
          <span class="pack-domain">{{ pack.domain }}</span>
          <span v-if="pack.result" class="pack-result" :class="'result-' + pack.result.toLowerCase().replace('_', '-')">{{ pack.result }}</span>
        </div>
        <h3 class="pack-name">{{ pack.name }}</h3>
        <p class="pack-narrative">{{ pack.narrative }}</p>
        <span class="pack-category">{{ pack.category }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.scenario-browser {
  padding: 2rem;
}

.page-title {
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 0.5rem;
}

.page-desc {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0 0 1.5rem;
  line-height: 1.6;
}

.pack-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

.pack-card {
  padding: 1.25rem;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  cursor: pointer;
  transition: all var(--transition);
}

.pack-card:hover {
  border-color: var(--accent);
  background: var(--bg-hover);
}

.pack-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.pack-domain {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-muted);
}

.pack-result {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 10px;
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

.pack-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 0.5rem;
}

.pack-narrative {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
  margin: 0 0 0.75rem;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.pack-category {
  font-size: 11px;
  color: var(--text-muted);
  text-transform: capitalize;
}
</style>
