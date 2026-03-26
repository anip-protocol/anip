<script setup lang="ts">
import { ref, watch, computed } from 'vue'

const props = defineProps<{
  declaration: Record<string, any>
  capabilityName: string
  initialValues?: Record<string, string>
  disabled?: boolean
}>()

const emit = defineEmits<{
  submit: [inputs: Record<string, string>]
  update: [inputs: Record<string, string>]
}>()

const inputs = ref<Record<string, string>>({})

// Initialize from defaults and initialValues
function initInputs() {
  const values: Record<string, string> = {}
  const fields = props.declaration.inputs || []
  for (const field of fields) {
    values[field.name] = props.initialValues?.[field.name]
      ?? (field.default != null ? String(field.default) : '')
  }
  inputs.value = values
}

initInputs()
// Re-init only when the declaration changes (capability switch), not on
// every initialValues echo-back — avoids redundant reactivity churn.
watch(() => props.declaration, initInputs)

watch(inputs, (val) => emit('update', { ...val }), { deep: true })

const fields = computed(() => props.declaration.inputs || [])

const canSubmit = computed(() => {
  if (props.disabled) return false
  for (const field of fields.value) {
    if (field.required !== false && !inputs.value[field.name]?.trim()) {
      return false
    }
  }
  return true
})

function onSubmit() {
  if (canSubmit.value) {
    emit('submit', { ...inputs.value })
  }
}
</script>

<template>
  <div class="invoke-form">
    <div class="section-label">Inputs</div>
    <div v-if="!fields.length" class="no-inputs">This capability takes no inputs.</div>
    <div v-else class="fields">
      <div v-for="field in fields" :key="field.name" class="field">
        <label class="field-label">
          <span class="field-name">{{ field.name }}</span>
          <span class="field-type">{{ field.type || 'string' }}</span>
          <span v-if="field.required !== false" class="field-required">*</span>
        </label>
        <input
          v-model="inputs[field.name]"
          type="text"
          class="field-input"
          :placeholder="field.description || field.name"
        />
      </div>
    </div>
    <button
      class="invoke-btn"
      :disabled="!canSubmit"
      @click="onSubmit"
    >
      Invoke {{ capabilityName }}
    </button>
  </div>
</template>

<style scoped>
.invoke-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.no-inputs {
  font-size: 13px;
  color: var(--text-muted);
  padding: 8px 0;
}

.fields {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.field-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}

.field-name {
  font-family: 'SF Mono', 'Fira Code', monospace;
  color: var(--text-primary);
  font-weight: 500;
}

.field-type {
  color: var(--text-muted);
  font-size: 11px;
}

.field-required {
  color: #f87171;
  font-weight: 600;
}

.field-input {
  height: 34px;
  padding: 0 12px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 13px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  outline: none;
  transition: border-color 150ms ease, box-shadow 150ms ease;
}

.field-input::placeholder {
  color: var(--text-muted);
}

.field-input:focus {
  border-color: var(--border-focus);
  box-shadow: 0 0 0 3px var(--accent-glow);
}

.invoke-btn {
  height: 38px;
  padding: 0 24px;
  background: var(--accent);
  border: none;
  border-radius: var(--radius-sm);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background 150ms ease;
  margin-top: 4px;
}

.invoke-btn:hover:not(:disabled) {
  background: var(--accent-hover);
}

.invoke-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
