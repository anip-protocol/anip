<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { store } from '../store'
import { fetchDiscovery } from '../api'
import StatusBadge from '../components/StatusBadge.vue'
import JsonPanel from '../components/JsonPanel.vue'

const data = ref<any>(null)
const loading = ref(false)
const error = ref('')

async function load() {
  if (!store.connected) return
  loading.value = true
  error.value = ''
  try {
    data.value = await fetchDiscovery(store.baseUrl)
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Failed to load discovery'
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => store.connected, (connected) => {
  if (connected) load()
  else data.value = null
})

const discovery = () => data.value?.anip_discovery || data.value || {}

function trustBadgeType(level: string): 'success' | 'info' | 'warning' | 'neutral' {
  const map: Record<string, 'success' | 'info' | 'warning' | 'neutral'> = {
    anchored: 'success',
    attested: 'success',
    signed: 'info',
    self_declared: 'warning',
  }
  return map[level] || 'neutral'
}

function sideEffectType(se: string): 'success' | 'warning' | 'danger' | 'neutral' {
  const map: Record<string, 'success' | 'warning' | 'danger' | 'neutral'> = {
    read: 'success',
    write: 'warning',
    transactional: 'warning',
    irreversible: 'danger',
  }
  return map[se] || 'neutral'
}
</script>

<template>
  <div class="view">
    <div class="view-header">
      <h2>Discovery</h2>
      <span class="view-subtitle">/.well-known/anip</span>
    </div>

    <div v-if="!store.connected" class="placeholder">
      <div class="placeholder-icon">&#x1F50D;</div>
      <p>Connect to an ANIP service to inspect its discovery document.</p>
    </div>

    <div v-else-if="loading" class="placeholder">
      <div class="spinner"></div>
      <p>Loading discovery data...</p>
    </div>

    <div v-else-if="error" class="placeholder">
      <p class="error-text">{{ error }}</p>
      <button class="retry-btn" @click="load">Retry</button>
    </div>

    <div v-else-if="data" class="content-area">
      <!-- Service Identity -->
      <section class="section">
        <h3 class="section-title">Service Identity</h3>
        <div class="identity-row">
          <StatusBadge :label="discovery().protocol || 'unknown'" type="info" />
          <StatusBadge :label="discovery().compliance || 'unknown'" type="success" />
          <StatusBadge
            :label="discovery().trust_level || 'unknown'"
            :type="trustBadgeType(discovery().trust_level)"
          />
          <span v-if="discovery().base_url" class="base-url">{{ discovery().base_url }}</span>
        </div>
      </section>

      <!-- Posture Summary -->
      <section class="section" v-if="discovery().posture">
        <h3 class="section-title">Posture</h3>
        <div class="posture-bar">
          <div class="posture-card">
            <div class="posture-label">Audit</div>
            <div class="posture-values">
              <span class="posture-item">
                Retention: <strong>{{ discovery().posture.audit?.retention || 'N/A' }}</strong>
              </span>
              <span class="posture-item">
                Enforced:
                <StatusBadge
                  :label="discovery().posture.audit?.retention_enforced ? 'yes' : 'no'"
                  :type="discovery().posture.audit?.retention_enforced ? 'success' : 'neutral'"
                />
              </span>
            </div>
          </div>
          <div class="posture-card">
            <div class="posture-label">Failure Disclosure</div>
            <div class="posture-values">
              <span class="posture-item">
                Detail:
                <StatusBadge
                  :label="discovery().posture.failure_disclosure?.detail_level || 'redacted'"
                  :type="discovery().posture.failure_disclosure?.detail_level === 'full' ? 'success' : discovery().posture.failure_disclosure?.detail_level === 'redacted' ? 'danger' : 'warning'"
                />
              </span>
              <span class="posture-item" v-if="discovery().posture.failure_disclosure?.caller_classes">
                Classes: {{ discovery().posture.failure_disclosure.caller_classes.join(', ') }}
              </span>
            </div>
          </div>
          <div class="posture-card">
            <div class="posture-label">Anchoring</div>
            <div class="posture-values">
              <span class="posture-item">
                <StatusBadge
                  :label="discovery().posture.anchoring?.enabled ? 'enabled' : 'disabled'"
                  :type="discovery().posture.anchoring?.enabled ? 'success' : 'neutral'"
                />
              </span>
              <span class="posture-item" v-if="discovery().posture.anchoring?.proofs_available">
                Proofs available
              </span>
            </div>
          </div>
        </div>
      </section>

      <!-- Capabilities Table -->
      <section class="section" v-if="discovery().capabilities">
        <h3 class="section-title">Capabilities</h3>
        <div class="table-wrapper">
          <table class="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Side Effect</th>
                <th>Scope</th>
                <th>Financial</th>
                <th>Contract</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(cap, name) in discovery().capabilities" :key="name">
                <td class="mono-cell">{{ name }}</td>
                <td>
                  <StatusBadge
                    :label="cap.side_effect || 'unknown'"
                    :type="sideEffectType(cap.side_effect)"
                  />
                </td>
                <td>
                  <span v-for="s in (cap.minimum_scope || [])" :key="s" class="scope-chip">{{ s }}</span>
                </td>
                <td class="center-cell">
                  <span v-if="cap.financial" class="check-mark">&#x2713;</span>
                  <span v-else class="dash">&mdash;</span>
                </td>
                <td class="mono-cell">{{ cap.contract || '\u2014' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- Endpoints -->
      <section class="section" v-if="discovery().endpoints">
        <h3 class="section-title">Endpoints</h3>
        <div class="endpoints-list">
          <div v-for="(path, name) in discovery().endpoints" :key="name" class="endpoint-item">
            <span class="endpoint-name">{{ name }}</span>
            <span class="endpoint-path">{{ path }}</span>
          </div>
        </div>
      </section>

      <!-- Raw JSON -->
      <section class="section">
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

/* Identity */
.identity-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.base-url {
  font-size: 13px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  color: var(--text-secondary);
  padding: 2px 10px;
  background: var(--bg-hover);
  border-radius: 4px;
}

/* Posture */
.posture-bar {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.posture-card {
  flex: 1;
  min-width: 200px;
  padding: 14px 16px;
  background: var(--bg-hover);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}

.posture-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.posture-values {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.posture-item {
  font-size: 12px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 6px;
}

.posture-item strong {
  color: var(--text-primary);
  font-family: 'SF Mono', 'Fira Code', monospace;
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

.data-table tr:hover td {
  background: rgba(108, 99, 255, 0.04);
}

.mono-cell {
  font-family: 'SF Mono', 'Fira Code', monospace;
  color: var(--text-primary);
}

.center-cell {
  text-align: center;
}

.scope-chip {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  margin-right: 4px;
  border-radius: 4px;
  background: rgba(108, 99, 255, 0.1);
  color: var(--accent);
  font-size: 11px;
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.check-mark {
  color: var(--success);
  font-size: 16px;
}

.dash {
  color: var(--text-muted);
}

/* Endpoints */
.endpoints-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.endpoint-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 12px;
  border-radius: var(--radius-sm);
  transition: background 150ms ease;
}

.endpoint-item:hover {
  background: var(--bg-hover);
}

.endpoint-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  min-width: 120px;
}

.endpoint-path {
  font-size: 13px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  color: var(--text-primary);
  user-select: all;
}
</style>
