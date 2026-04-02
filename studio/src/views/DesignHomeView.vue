<script setup lang="ts">
import { useRouter } from 'vue-router'
import { getPackMetas } from '../design/store'

const router = useRouter()
const packMetas = getPackMetas()

function browsePacks() {
  router.push('/design/scenarios')
}
</script>

<template>
  <div class="design-home">
    <h1 class="page-title">Design Mode</h1>
    <p class="page-desc">Explore scenario packs to understand what ANIP handles and where you still need glue code.</p>
    <p class="pack-count">{{ packMetas.length }} packs available</p>
    <button class="browse-btn" @click="browsePacks">Browse Scenarios</button>
  </div>
</template>

<style scoped>
.design-home {
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
  margin: 0 0 1rem;
  max-width: 520px;
  line-height: 1.6;
}

.pack-count {
  font-size: 13px;
  color: var(--text-muted);
  margin: 0 0 1.5rem;
}

.browse-btn {
  height: 38px;
  padding: 0 24px;
  background: var(--accent);
  border: none;
  border-radius: var(--radius-sm);
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background var(--transition);
}

.browse-btn:hover {
  background: var(--accent-hover);
}
</style>
