<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()
const capability = route.params.capability as string | undefined
</script>

<template>
  <div class="view">
    <div class="view-header">
      <h2>Invoke</h2>
      <span class="view-subtitle">/anip/invoke/{{ capability || '...' }}</span>
    </div>
    <div class="placeholder">
      <p>Invoke view — under construction</p>
    </div>
  </div>
</template>

<style scoped>
.view { height: 100%; display: flex; flex-direction: column; }
.view-header { padding: 24px 32px 16px; border-bottom: 1px solid var(--border); }
.view-header h2 { font-size: 20px; font-weight: 600; color: var(--text-primary); margin-bottom: 4px; }
.view-subtitle { font-size: 13px; color: var(--text-muted); font-family: 'SF Mono', 'Fira Code', monospace; }
.placeholder { flex: 1; display: flex; align-items: center; justify-content: center; color: var(--text-muted); }
</style>
