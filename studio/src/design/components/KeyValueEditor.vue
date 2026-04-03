<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  modelValue: Record<string, any>
  depth?: number
}>()

const emit = defineEmits<{
  'update:modelValue': [value: Record<string, any>]
}>()

const currentDepth = computed(() => props.depth ?? 0)
const maxDepth = 2

const entries = computed(() => Object.entries(props.modelValue))

function detectType(value: any): 'string' | 'number' | 'boolean' | 'object' {
  if (typeof value === 'boolean') return 'boolean'
  if (typeof value === 'number') return 'number'
  if (typeof value === 'object' && value !== null && !Array.isArray(value)) return 'object'
  return 'string'
}

function updateKey(oldKey: string, newKey: string) {
  if (newKey === oldKey) return
  const result: Record<string, any> = {}
  for (const [k, v] of entries.value) {
    if (k === oldKey) {
      result[newKey] = v
    } else {
      result[k] = v
    }
  }
  emit('update:modelValue', result)
}

function updateValue(key: string, newValue: any) {
  emit('update:modelValue', { ...props.modelValue, [key]: newValue })
}

function parseValue(raw: string, currentType: string): any {
  if (currentType === 'number') {
    const n = Number(raw)
    return isNaN(n) ? raw : n
  }
  return raw
}

function addEntry() {
  let newKey = 'new_key'
  let i = 1
  while (newKey in props.modelValue) {
    newKey = `new_key_${i++}`
  }
  emit('update:modelValue', { ...props.modelValue, [newKey]: '' })
}

function removeEntry(key: string) {
  const copy = { ...props.modelValue }
  delete copy[key]
  emit('update:modelValue', copy)
}

function toggleBoolean(key: string) {
  emit('update:modelValue', { ...props.modelValue, [key]: !props.modelValue[key] })
}

function handleNestedUpdate(key: string, nestedValue: Record<string, any>) {
  emit('update:modelValue', { ...props.modelValue, [key]: nestedValue })
}
</script>

<template>
  <div class="kv-editor" :class="{ nested: currentDepth > 0 }">
    <div class="kv-row" v-for="[key, value] in entries" :key="key">
      <input
        class="kv-key"
        type="text"
        :value="key"
        @change="updateKey(key, ($event.target as HTMLInputElement).value)"
        placeholder="key"
      />

      <!-- Nested object (recurse up to maxDepth) -->
      <template v-if="detectType(value) === 'object' && currentDepth < maxDepth">
        <div class="kv-nested">
          <KeyValueEditor
            :modelValue="value"
            :depth="currentDepth + 1"
            @update:modelValue="handleNestedUpdate(key, $event)"
          />
        </div>
      </template>

      <!-- Boolean toggle -->
      <template v-else-if="detectType(value) === 'boolean'">
        <button
          class="kv-toggle"
          :class="{ on: value, off: !value }"
          @click="toggleBoolean(key)"
          type="button"
        >
          {{ value ? 'true' : 'false' }}
        </button>
      </template>

      <!-- Number input -->
      <template v-else-if="detectType(value) === 'number'">
        <input
          class="kv-value"
          type="number"
          :value="value"
          @input="updateValue(key, parseValue(($event.target as HTMLInputElement).value, 'number'))"
        />
      </template>

      <!-- String input (default, including nested objects beyond maxDepth) -->
      <template v-else>
        <input
          class="kv-value"
          type="text"
          :value="detectType(value) === 'object' ? JSON.stringify(value) : String(value ?? '')"
          @input="updateValue(key, ($event.target as HTMLInputElement).value)"
          placeholder="value"
        />
      </template>

      <button class="kv-delete" @click="removeEntry(key)" type="button" title="Remove entry">
        &#x2715;
      </button>
    </div>

    <button class="kv-add" @click="addEntry" type="button">
      + Add
    </button>
  </div>
</template>

<style scoped>
.kv-editor {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.kv-editor.nested {
  padding-left: 16px;
  border-left: 2px solid var(--border);
  margin-left: 4px;
}

.kv-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.kv-key {
  width: 160px;
  flex-shrink: 0;
  font-size: 13px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  padding: 6px 10px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  outline: none;
}

.kv-key:focus {
  border-color: var(--border-focus);
}

.kv-value {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  padding: 6px 10px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  outline: none;
}

.kv-value:focus {
  border-color: var(--border-focus);
}

.kv-nested {
  flex: 1;
  min-width: 0;
}

.kv-toggle {
  padding: 6px 14px;
  font-size: 12px;
  font-weight: 600;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  cursor: pointer;
  transition: all var(--transition);
  min-width: 70px;
}

.kv-toggle.on {
  background: rgba(52, 211, 153, 0.12);
  color: var(--success);
  border-color: rgba(52, 211, 153, 0.3);
}

.kv-toggle.off {
  background: transparent;
  color: var(--text-muted);
}

.kv-toggle:hover {
  background: var(--bg-hover);
}

.kv-delete {
  flex-shrink: 0;
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition);
}

.kv-delete:hover {
  color: var(--error);
  border-color: rgba(248, 113, 113, 0.3);
  background: rgba(248, 113, 113, 0.06);
}

.kv-add {
  align-self: flex-start;
  font-size: 12px;
  font-weight: 600;
  padding: 5px 14px;
  background: transparent;
  border: 1px dashed var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition);
}

.kv-add:hover {
  color: var(--accent);
  border-color: var(--accent);
  background: var(--accent-glow);
}
</style>
