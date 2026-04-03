<script setup lang="ts">
defineProps<{
  path: string
  label?: string
}>()
</script>

<template>
  <span class="field-chip" :title="path">
    {{ label ?? path }}
  </span>
</template>

<style scoped>
.field-chip {
  display: inline-flex;
  align-items: center;
  font-size: 11px;
  font-family: var(--font-mono, monospace);
  color: var(--text-muted);
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 1px 6px;
  white-space: nowrap;
  cursor: default;
}
</style>
