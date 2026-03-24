<script setup lang="ts">
import { ref, watch, onMounted, computed } from 'vue'
import { store } from '../store'
import { fetchJwks } from '../api'
import JsonPanel from '../components/JsonPanel.vue'

const data = ref<any>(null)
const loading = ref(false)
const error = ref('')
const expandedKey = ref<string | null>(null)

async function load() {
  if (!store.connected) return
  loading.value = true
  error.value = ''
  try {
    data.value = await fetchJwks(store.baseUrl)
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Failed to load JWKS'
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => store.connected, (connected) => {
  if (connected) load()
  else data.value = null
})

const keys = computed(() => data.value?.keys || [])

function toggleKey(kid: string) {
  expandedKey.value = expandedKey.value === kid ? null : kid
}

const kidCopied = ref('')
async function copyKid(kid: string) {
  try {
    await navigator.clipboard.writeText(kid)
    kidCopied.value = kid
    setTimeout(() => { kidCopied.value = '' }, 1500)
  } catch { /* clipboard not available */ }
}
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

    <div v-else-if="loading" class="placeholder">
      <div class="spinner"></div>
      <p>Loading JWKS...</p>
    </div>

    <div v-else-if="error" class="placeholder">
      <p class="error-text">{{ error }}</p>
      <button class="retry-btn" @click="load">Retry</button>
    </div>

    <div v-else-if="data" class="content-area">
      <section class="section">
        <h3 class="section-title">Keys ({{ keys.length }})</h3>
        <div class="table-wrapper">
          <table class="data-table">
            <thead>
              <tr>
                <th></th>
                <th>Key ID (kid)</th>
                <th>Algorithm (alg)</th>
                <th>Key Type (kty)</th>
                <th>Curve (crv)</th>
                <th>Use</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="key in keys" :key="key.kid">
                <tr class="key-row" @click="toggleKey(key.kid)">
                  <td class="expand-cell">
                    <span class="expand-icon">{{ expandedKey === key.kid ? '\u25BC' : '\u25B6' }}</span>
                  </td>
                  <td class="kid-cell">
                    <span class="kid-value" @click.stop="copyKid(key.kid)" :title="kidCopied === key.kid ? 'Copied!' : 'Click to copy'">
                      {{ key.kid }}
                    </span>
                  </td>
                  <td class="mono-cell">{{ key.alg || '\u2014' }}</td>
                  <td class="mono-cell">{{ key.kty }}</td>
                  <td class="mono-cell">{{ key.crv || '\u2014' }}</td>
                  <td>{{ key.use || '\u2014' }}</td>
                </tr>
                <tr v-if="expandedKey === key.kid" class="detail-row">
                  <td :colspan="6">
                    <div class="key-detail">
                      <JsonPanel :data="key" title="Full JWK" :collapsed="false" />
                    </div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </section>

      <!-- Raw JSON -->
      <section class="section">
        <JsonPanel :data="data" title="Raw JWKS" :collapsed="true" />
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

.key-row {
  cursor: pointer;
  transition: background 150ms ease;
}

.key-row:hover td {
  background: rgba(108, 99, 255, 0.04);
}

.expand-cell {
  width: 30px;
}

.expand-icon {
  font-size: 10px;
  color: var(--text-muted);
}

.kid-cell {
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.kid-value {
  color: var(--accent);
  cursor: pointer;
  user-select: all;
  padding: 2px 6px;
  border-radius: 3px;
  transition: background 150ms ease;
}

.kid-value:hover {
  background: var(--accent-glow);
}

.mono-cell {
  font-family: 'SF Mono', 'Fira Code', monospace;
  color: var(--text-primary);
}

.detail-row td {
  padding: 0;
  border-bottom: 1px solid var(--border);
}

.key-detail {
  padding: 8px 12px 12px;
}
</style>
