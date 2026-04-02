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
  <div class="scenario-detail" v-if="pack">
    <h1 class="page-title">{{ pack.scenario.scenario.name }}</h1>
    <p class="narrative">{{ pack.scenario.scenario.narrative }}</p>
    <div class="section">
      <h2>Expected Behavior</h2>
      <ul>
        <li v-for="(item, i) in pack.scenario.scenario.expected_behavior" :key="i">{{ item }}</li>
      </ul>
    </div>
    <div class="section">
      <h2>Expected ANIP Support</h2>
      <ul>
        <li v-for="(item, i) in pack.scenario.scenario.expected_anip_support" :key="i">{{ item }}</li>
      </ul>
    </div>
  </div>
  <div v-else class="not-found">Pack not found.</div>
</template>

<style scoped>
.scenario-detail {
  padding: 2rem;
}

.page-title {
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 0.5rem;
}

.narrative {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 0 0 1.5rem;
  max-width: 640px;
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

.not-found {
  padding: 2rem;
  color: var(--text-muted);
}
</style>
