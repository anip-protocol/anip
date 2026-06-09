<script setup lang="ts">
import { confirmationStore, resolveConfirmation } from '../confirm'
</script>

<template>
  <div
    v-if="confirmationStore.open"
    class="confirm-backdrop"
    @click.self="resolveConfirmation(false)"
  >
    <div class="confirm-dialog">
      <div class="confirm-header">
        <h3 class="confirm-title">{{ confirmationStore.title }}</h3>
      </div>
      <p class="confirm-message">{{ confirmationStore.message }}</p>
      <div class="confirm-actions">
        <button class="confirm-btn secondary" type="button" @click="resolveConfirmation(false)">
          {{ confirmationStore.cancelLabel }}
        </button>
        <button
          class="confirm-btn"
          :class="confirmationStore.tone === 'danger' ? 'danger' : 'primary'"
          type="button"
          @click="resolveConfirmation(true)"
        >
          {{ confirmationStore.confirmLabel }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.confirm-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(10, 10, 15, 0.58);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  z-index: 400;
}

.confirm-dialog {
  width: min(520px, 100%);
  background: var(--bg-panel, #13131d);
  border: 1px solid var(--border);
  border-radius: 14px;
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.35);
  padding: 20px 22px;
}

.confirm-header {
  margin-bottom: 8px;
}

.confirm-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}

.confirm-message {
  margin: 0;
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-secondary);
}

.confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 18px;
}

.confirm-btn {
  border-radius: 10px;
  padding: 8px 14px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  border: 1px solid var(--border);
}

.confirm-btn.secondary {
  background: transparent;
  color: var(--text-secondary);
}

.confirm-btn.primary {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}

.confirm-btn.danger {
  background: transparent;
  color: var(--error);
  border-color: rgba(248, 113, 113, 0.3);
}

.confirm-btn.danger:hover {
  background: rgba(248, 113, 113, 0.1);
}
</style>
