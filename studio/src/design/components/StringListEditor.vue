<script setup lang="ts">
const props = defineProps<{
  modelValue: string[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string[]]
}>()

function updateItem(index: number, value: string) {
  const copy = [...props.modelValue]
  copy[index] = value
  emit('update:modelValue', copy)
}

function removeItem(index: number) {
  const copy = [...props.modelValue]
  copy.splice(index, 1)
  emit('update:modelValue', copy)
}

function addItem() {
  emit('update:modelValue', [...props.modelValue, ''])
}
</script>

<template>
  <div class="sl-editor">
    <div class="sl-row" v-for="(item, i) in modelValue" :key="i">
      <input
        class="sl-input"
        type="text"
        :value="item"
        @input="updateItem(i, ($event.target as HTMLInputElement).value)"
        placeholder="Enter value..."
      />
      <button class="sl-delete" @click="removeItem(i)" type="button" title="Remove item">
        &#x2715;
      </button>
    </div>

    <button class="sl-add" @click="addItem" type="button">
      + Add item
    </button>
  </div>
</template>

<style scoped>
.sl-editor {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.sl-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.sl-input {
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

.sl-input:focus {
  border-color: var(--border-focus);
}

.sl-delete {
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

.sl-delete:hover {
  color: var(--error);
  border-color: rgba(248, 113, 113, 0.3);
  background: rgba(248, 113, 113, 0.06);
}

.sl-add {
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

.sl-add:hover {
  color: var(--accent);
  border-color: var(--accent);
  background: var(--accent-glow);
}
</style>
