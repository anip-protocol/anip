<script setup lang="ts">
defineProps<{
  label: string
  type: 'success' | 'warning' | 'danger' | 'info' | 'neutral'
}>()
</script>

<template>
  <span class="status-badge" :class="type">{{ label }}</span>
</template>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.3px;
  white-space: nowrap;
  text-transform: uppercase;
}

.success {
  background: rgba(52, 211, 153, 0.15);
  color: #34d399;
}

.warning {
  background: rgba(251, 191, 36, 0.15);
  color: #fbbf24;
}

.danger {
  background: rgba(248, 113, 113, 0.15);
  color: #f87171;
}

.info {
  background: rgba(96, 165, 250, 0.15);
  color: #60a5fa;
}

.neutral {
  background: rgba(160, 160, 192, 0.12);
  color: #a0a0c0;
}
</style>
