<!-- studio/src/design/components/SuggestionChips.vue -->
<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{
  modelValue: string[]
  suggestions: string[]
  readonly: boolean
  placeholder?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string[]]
}>()

const newEntry = ref('')

function isSelected(suggestion: string): boolean {
  return props.modelValue.includes(suggestion)
}

function toggleSuggestion(suggestion: string) {
  if (props.readonly) return
  if (isSelected(suggestion)) {
    emit('update:modelValue', props.modelValue.filter(s => s !== suggestion))
  } else {
    emit('update:modelValue', [...props.modelValue, suggestion])
  }
}

function addCustomEntry() {
  if (props.readonly) return
  const entry = newEntry.value.trim()
  if (entry && !props.modelValue.includes(entry)) {
    emit('update:modelValue', [...props.modelValue, entry])
  }
  newEntry.value = ''
}

function removeEntry(entry: string) {
  if (props.readonly) return
  emit('update:modelValue', props.modelValue.filter(s => s !== entry))
}
</script>

<template>
  <div class="suggestion-chips">
    <!-- Suggestions -->
    <div class="chip-grid" v-if="suggestions.length > 0">
      <button
        v-for="suggestion in suggestions"
        :key="suggestion"
        class="chip"
        :class="{ selected: isSelected(suggestion), readonly }"
        :disabled="readonly"
        type="button"
        @click="toggleSuggestion(suggestion)"
      >
        {{ suggestion.replace(/_/g, ' ') }}
      </button>
    </div>

    <!-- Custom entry input -->
    <div class="custom-entry" v-if="!readonly">
      <input
        class="form-input"
        type="text"
        v-model="newEntry"
        :placeholder="placeholder ?? 'Add custom entry...'"
        @keydown.enter.prevent="addCustomEntry"
      />
      <button class="add-btn" type="button" @click="addCustomEntry" :disabled="!newEntry.trim()">
        Add
      </button>
    </div>

    <!-- Selected entries (showing custom ones not in suggestions) -->
    <div class="selected-list" v-if="modelValue.length > 0">
      <div
        v-for="entry in modelValue"
        :key="entry"
        class="selected-entry"
      >
        <span class="entry-text">{{ entry.replace(/_/g, ' ') }}</span>
        <button
          v-if="!readonly"
          class="remove-btn"
          type="button"
          @click="removeEntry(entry)"
          title="Remove"
        >
          &#x2715;
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.suggestion-chips {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.chip-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.chip {
  font-size: 12px;
  padding: 4px 12px;
  border-radius: 14px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition);
}

.chip.selected {
  background: rgba(52, 211, 153, 0.12);
  color: var(--success);
  border-color: rgba(52, 211, 153, 0.3);
}

.chip:hover:not(:disabled):not(.selected) {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.chip.readonly {
  cursor: default;
}

.chip:disabled {
  opacity: 0.5;
  cursor: default;
}

.custom-entry {
  display: flex;
  gap: 8px;
}

.form-input {
  flex: 1;
  font-size: 13px;
  padding: 6px 10px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  outline: none;
}

.add-btn {
  font-size: 12px;
  font-weight: 600;
  padding: 6px 14px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--transition);
}

.add-btn:hover:not(:disabled) {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.add-btn:disabled {
  opacity: 0.4;
  cursor: default;
}

.selected-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.selected-entry {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: var(--text-secondary);
}

.remove-btn {
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 12px;
  padding: 0 4px;
}

.remove-btn:hover {
  color: var(--error);
}
</style>
