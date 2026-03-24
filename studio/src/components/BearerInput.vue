<script setup lang="ts">
import { ref } from 'vue'
import { store } from '../store'

const emit = defineEmits<{
  authenticated: []
}>()

const tokenInput = ref('')

function apply() {
  if (!tokenInput.value.trim()) return
  store.bearer = tokenInput.value.trim()
  emit('authenticated')
}

function clear() {
  store.bearer = ''
  tokenInput.value = ''
}

function truncated(token: string): string {
  if (token.length <= 20) return token
  return token.slice(0, 10) + '...' + token.slice(-6)
}
</script>

<template>
  <div class="bearer-input">
    <div v-if="store.bearer" class="token-badge">
      <span class="lock-icon">&#x1F512;</span>
      <span class="token-value" :title="store.bearer">{{ truncated(store.bearer) }}</span>
      <button class="clear-btn" @click="clear" title="Clear token">&times;</button>
    </div>
    <div v-else class="token-form">
      <span class="lock-icon">&#x1F513;</span>
      <input
        v-model="tokenInput"
        type="text"
        class="token-input"
        placeholder="Bearer token or API key"
        @keyup.enter="apply"
      />
      <button class="apply-btn" @click="apply" :disabled="!tokenInput.trim()">Apply</button>
    </div>
  </div>
</template>

<style scoped>
.bearer-input {
  display: flex;
  align-items: center;
}

.token-form {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.lock-icon {
  font-size: 14px;
  flex-shrink: 0;
}

.token-input {
  flex: 1;
  max-width: 360px;
  height: 32px;
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

.token-input::placeholder {
  color: var(--text-muted);
}

.token-input:focus {
  border-color: var(--border-focus);
  box-shadow: 0 0 0 3px var(--accent-glow);
}

.apply-btn {
  height: 32px;
  padding: 0 16px;
  background: var(--accent);
  border: none;
  border-radius: var(--radius-sm);
  color: #fff;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: background 150ms ease;
}

.apply-btn:hover:not(:disabled) {
  background: var(--accent-hover);
}

.apply-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.token-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.token-value {
  font-size: 12px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  color: var(--text-secondary);
  user-select: all;
}

.clear-btn {
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: 16px;
  cursor: pointer;
  padding: 0 4px;
  line-height: 1;
  transition: color 150ms ease;
}

.clear-btn:hover {
  color: var(--error);
}
</style>
