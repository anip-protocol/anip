<script setup lang="ts">
import { ref, watch, onMounted, computed } from 'vue'
import { store } from '../store'
import { fetchCheckpoints } from '../api'
import JsonPanel from '../components/JsonPanel.vue'

const data = ref<any>(null)
const loading = ref(false)
const error = ref('')
const expandedCheckpoint = ref<string | null>(null)

async function load() {
  if (!store.connected) return
  loading.value = true
  error.value = ''
  try {
    data.value = await fetchCheckpoints(store.baseUrl)
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Failed to load checkpoints'
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => store.connected, (connected) => {
  if (connected) load()
  else data.value = null
})

const checkpoints = computed(() => data.value?.checkpoints || [])

function toggleCheckpoint(id: string) {
  expandedCheckpoint.value = expandedCheckpoint.value === id ? null : id
}

function truncateHash(hash: string): string {
  if (!hash || hash.length <= 16) return hash || '\u2014'
  return hash.slice(0, 8) + '...' + hash.slice(-8)
}

function formatTimestamp(ts: string): string {
  if (!ts) return '\u2014'
  try {
    return new Date(ts).toLocaleString()
  } catch {
    return ts
  }
}

const rootCopied = ref('')
async function copyRoot(root: string) {
  try {
    await navigator.clipboard.writeText(root)
    rootCopied.value = root
    setTimeout(() => { rootCopied.value = '' }, 1500)
  } catch { /* clipboard not available */ }
}
</script>

<template>
  <div class="view">
    <div class="view-header">
      <h2>Checkpoints</h2>
      <span class="view-subtitle">/anip/checkpoints</span>
    </div>

    <div v-if="!store.connected" class="placeholder">
      <div class="placeholder-icon">&#x2713;</div>
      <p>Connect to an ANIP service to view its checkpoint history.</p>
    </div>

    <div v-else-if="loading" class="placeholder">
      <div class="spinner"></div>
      <p>Loading checkpoints...</p>
    </div>

    <div v-else-if="error" class="placeholder">
      <p class="error-text">{{ error }}</p>
      <button class="retry-btn" @click="load">Retry</button>
    </div>

    <div v-else-if="data" class="content-area">
      <!-- Empty State -->
      <div v-if="checkpoints.length === 0" class="empty-state">
        <p>No checkpoints yet. Checkpoints are created periodically based on the checkpoint policy.</p>
      </div>

      <!-- Checkpoints Table -->
      <section class="section" v-else>
        <h3 class="section-title">Checkpoints ({{ checkpoints.length }})</h3>
        <div class="table-wrapper">
          <table class="data-table">
            <thead>
              <tr>
                <th></th>
                <th>ID</th>
                <th>Timestamp</th>
                <th>Entries</th>
                <th>Range</th>
                <th>Merkle Root</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="cp in checkpoints" :key="cp.checkpoint_id">
                <tr class="cp-row" @click="toggleCheckpoint(cp.checkpoint_id)">
                  <td class="expand-cell">
                    <span class="expand-icon">{{ expandedCheckpoint === cp.checkpoint_id ? '\u25BC' : '\u25B6' }}</span>
                  </td>
                  <td class="mono-cell id-cell">{{ cp.checkpoint_id }}</td>
                  <td class="ts-cell">{{ formatTimestamp(cp.timestamp) }}</td>
                  <td class="mono-cell">{{ cp.entry_count }}</td>
                  <td class="mono-cell">
                    <span v-if="cp.range">{{ cp.range.first_sequence }} &ndash; {{ cp.range.last_sequence }}</span>
                    <span v-else>&mdash;</span>
                  </td>
                  <td class="hash-cell" :title="cp.merkle_root">
                    {{ truncateHash(cp.merkle_root) }}
                  </td>
                </tr>
                <tr v-if="expandedCheckpoint === cp.checkpoint_id" class="detail-row">
                  <td :colspan="6">
                    <div class="cp-detail">
                      <div class="detail-grid">
                        <div class="detail-item">
                          <span class="detail-label">Merkle Root</span>
                          <span class="detail-value mono" @click="copyRoot(cp.merkle_root)" :title="rootCopied === cp.merkle_root ? 'Copied!' : 'Click to copy'">
                            {{ cp.merkle_root }}
                          </span>
                        </div>
                        <div class="detail-item" v-if="cp.previous_checkpoint">
                          <span class="detail-label">Previous Checkpoint</span>
                          <span class="detail-value mono">{{ cp.previous_checkpoint }}</span>
                        </div>
                        <div class="detail-item" v-if="cp.range">
                          <span class="detail-label">Range</span>
                          <span class="detail-value mono">{{ cp.range.first_sequence }} &ndash; {{ cp.range.last_sequence }}</span>
                        </div>
                      </div>
                      <JsonPanel :data="cp" title="Full Checkpoint" :collapsed="false" />
                    </div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </section>

      <!-- Raw JSON -->
      <section class="section" v-if="checkpoints.length > 0">
        <JsonPanel :data="data" title="Raw Response" :collapsed="true" />
      </section>
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

.error-text {
  color: var(--error) !important;
}

.retry-btn {
  padding: 6px 16px;
  background: var(--accent);
  border: none;
  border-radius: var(--radius-sm);
  color: #fff;
  font-size: 13px;
  cursor: pointer;
}

.retry-btn:hover {
  background: var(--accent-hover);
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
  display: flex;
  flex-direction: column;
  gap: 28px;
}

.section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin: 0;
}

/* Empty state */
.empty-state {
  padding: 60px 0;
  text-align: center;
  color: var(--text-muted);
  font-size: 14px;
}

/* Data Table */
.table-wrapper {
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.data-table th {
  text-align: left;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
  color: var(--text-muted);
  font-weight: 600;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.data-table td {
  padding: 8px 12px;
  border-bottom: 1px solid rgba(42, 42, 69, 0.5);
  color: var(--text-secondary);
}

.cp-row {
  cursor: pointer;
  transition: background 150ms ease;
}

.cp-row:hover td {
  background: rgba(108, 99, 255, 0.04);
}

.expand-cell {
  width: 30px;
}

.expand-icon {
  font-size: 10px;
  color: var(--text-muted);
}

.mono-cell {
  font-family: 'SF Mono', 'Fira Code', monospace;
  color: var(--text-primary);
}

.id-cell {
  white-space: nowrap;
  user-select: all;
}

.ts-cell {
  font-size: 12px;
  white-space: nowrap;
}

.hash-cell {
  font-family: 'SF Mono', 'Fira Code', monospace;
  color: var(--text-secondary);
  cursor: help;
  font-size: 12px;
}

.detail-row td {
  padding: 0;
  border-bottom: 1px solid var(--border);
}

.cp-detail {
  padding: 12px 16px 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.detail-grid {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.detail-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.detail-value {
  font-size: 13px;
  color: var(--text-primary);
}

.detail-value.mono {
  font-family: 'SF Mono', 'Fira Code', monospace;
  user-select: all;
  cursor: pointer;
  word-break: break-all;
}

.detail-value.mono:hover {
  color: var(--accent);
}
</style>
