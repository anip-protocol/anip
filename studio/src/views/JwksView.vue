<script setup lang="ts">
import { store } from '../store'
</script>

<template>
  <div class="view">
    <div class="view-header">
      <h2>JWKS</h2>
      <span class="view-subtitle">/.well-known/jwks.json</span>
    </div>
    <div v-if="!store.connected" class="placeholder">
      <div class="placeholder-icon">&#x1F511;</div>
      <p>Connect to an ANIP service to inspect its JSON Web Key Set.</p>
    </div>
    <div v-else-if="store.loading" class="placeholder">
      <div class="spinner"></div>
      <p>Loading JWKS...</p>
    </div>
    <div v-else class="content-area">
      <!-- Implemented in Task 2 -->
    </div>
  </div>
</template>

<style scoped>
.view {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.view-header {
  padding: 24px 32px 16px;
  border-bottom: 1px solid var(--border);
}

.view-header h2 {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.view-subtitle {
  font-size: 13px;
  color: var(--text-muted);
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.placeholder {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: var(--text-muted);
}

.placeholder-icon {
  font-size: 48px;
  opacity: 0.4;
}

.placeholder p {
  font-size: 14px;
  max-width: 320px;
  text-align: center;
  line-height: 1.5;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.content-area {
  flex: 1;
  padding: 24px 32px;
  overflow-y: auto;
}
</style>
