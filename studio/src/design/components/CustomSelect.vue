<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  modelValue: string
  options: Array<{ value: string; label: string; description?: string }>
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const selectedLabel = computed(() => {
  const opt = props.options.find(o => o.value === props.modelValue)
  return opt?.label ?? props.modelValue
})

const selectedDescription = computed(() => {
  const opt = props.options.find(o => o.value === props.modelValue)
  return opt?.description
})

function select(event: Event) {
  if (props.disabled) return
  emit('update:modelValue', (event.target as HTMLSelectElement).value)
}
</script>

<template>
  <label class="custom-select" :class="{ disabled }">
    <span class="sr-only">{{ selectedLabel }}</span>
    <select class="select-trigger" :value="modelValue" :disabled="disabled" @change="select">
      <option v-for="opt in options" :key="opt.value" :value="opt.value">
        {{ opt.label }}
      </option>
    </select>
    <span v-if="selectedDescription" class="select-desc">{{ selectedDescription }}</span>
  </label>
</template>

<style scoped>
.custom-select {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.select-trigger {
  font-size: 13px;
  padding: 6px 32px 6px 10px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  cursor: pointer;
  min-width: 140px;
  text-align: left;
}

.select-trigger:hover:not(:disabled) {
  border-color: var(--border-focus, #6366f1);
}

.select-trigger:disabled {
  opacity: 0.5;
  cursor: default;
}

.select-desc {
  font-size: 12px;
  color: var(--text-muted);
}

.disabled .select-trigger {
  opacity: 0.5;
  cursor: default;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
</style>
