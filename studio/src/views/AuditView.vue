<script setup lang="ts">
import { ref, watch, onMounted, computed } from 'vue'
import { store } from '../store'
import { fetchDiscovery, fetchAudit } from '../api'
import StatusBadge from '../components/StatusBadge.vue'
import BearerInput from '../components/BearerInput.vue'
import JsonPanel from '../components/JsonPanel.vue'

const data = ref<any>(null)
const loading = ref(false)
const error = ref('')
const expandedEntry = ref<number | null>(null)

// Filters
const capabilityFilter = ref('')
const sinceFilter = ref('')
const limitFilter = ref(50)
const taskIdFilter = ref('')
const parentInvocationIdFilter = ref('')

// Capability list from discovery (for the dropdown)
const capabilityNames = ref<string[]>([])

onMounted(async () => {
  if (store.connected) {
    try {
      const disc = await fetchDiscovery(store.baseUrl)
      const caps = disc?.anip_discovery?.capabilities || disc?.capabilities || {}
      capabilityNames.value = Object.keys(caps)
    } catch { /* silently skip */ }
  }
})

watch(() => store.connected, async (connected) => {
  if (!connected) {
    data.value = null
    capabilityNames.value = []
  } else {
    try {
      const disc = await fetchDiscovery(store.baseUrl)
      const caps = disc?.anip_discovery?.capabilities || disc?.capabilities || {}
      capabilityNames.value = Object.keys(caps)
    } catch { /* silently skip */ }
  }
})

async function fetchEntries() {
  if (!store.connected || !store.bearer) return
  loading.value = true
  error.value = ''
  try {
    const filters: Record<string, string> = {}
    if (capabilityFilter.value) filters.capability = capabilityFilter.value
    if (sinceFilter.value) filters.since = sinceFilter.value
    if (limitFilter.value) filters.limit = String(limitFilter.value)
    if (taskIdFilter.value) filters.task_id = taskIdFilter.value
    if (parentInvocationIdFilter.value) filters.parent_invocation_id = parentInvocationIdFilter.value
    data.value = await fetchAudit(store.baseUrl, store.bearer, filters)
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Failed to fetch audit entries'
  } finally {
    loading.value = false
  }
}

function onAuthenticated() {
  fetchEntries()
}

const entries = computed(() => {
  const raw = data.value?.entries || []
  // Newest first
  return [...raw].reverse()
})

function toggleEntry(idx: number) {
  expandedEntry.value = expandedEntry.value === idx ? null : idx
}

function statusType(entry: any): 'success' | 'danger' {
  return entry.success ? 'success' : 'danger'
}

function statusLabel(entry: any): string {
  if (entry.success) return 'SUCCESS'
  return `FAILED (${entry.failure_type || 'unknown'})`
}

function eventClassType(ec: string): 'success' | 'danger' | 'neutral' | 'warning' {
  const map: Record<string, 'success' | 'danger' | 'neutral' | 'warning'> = {
    high_risk_success: 'success',
    high_risk_denial: 'danger',
    low_risk_success: 'neutral',
    repeated_low_value_denial: 'neutral',
    malformed_or_spam: 'warning',
  }
  return map[ec] || 'neutral'
}

function formatTimestamp(ts: string): string {
  if (!ts) return '\u2014'
  try {
    const d = new Date(ts)
    return d.toLocaleString()
  } catch {
    return ts
  }
}
</script>

<template>
  <div class="view">
    <div class="view-header">
      <h2>Audit Log</h2>
      <span class="view-subtitle">/anip/audit</span>
    </div>

    <div v-if="!store.connected" class="placeholder">
      <div class="placeholder-icon">&#x1F4CA;</div>
      <p>Connect to an ANIP service to browse its audit trail.</p>
    </div>

    <div v-else class="content-area">
      <!-- Bearer Input -->
      <section class="section">
        <h3 class="section-title">Authentication</h3>
        <BearerInput @authenticated="onAuthenticated" />
      </section>

      <!-- Filter Bar -->
      <section class="section" v-if="store.bearer">
        <h3 class="section-title">Filters</h3>
        <div class="filter-bar">
          <div class="filter-group">
            <label class="filter-label">Capability</label>
            <select v-model="capabilityFilter" class="filter-select">
              <option value="">All</option>
              <option v-for="c in capabilityNames" :key="c" :value="c">{{ c }}</option>
            </select>
          </div>
          <div class="filter-group">
            <label class="filter-label">Since</label>
            <input v-model="sinceFilter" type="datetime-local" class="filter-input" />
          </div>
          <div class="filter-group">
            <label class="filter-label">Limit</label>
            <input v-model.number="limitFilter" type="number" class="filter-input num-input" min="1" max="1000" />
          </div>
          <div class="filter-group">
            <label class="filter-label">Task ID</label>
            <input v-model="taskIdFilter" type="text" class="filter-input" placeholder="Filter by task_id" />
          </div>
          <div class="filter-group">
            <label class="filter-label">Parent Invocation ID</label>
            <input v-model="parentInvocationIdFilter" type="text" class="filter-input" placeholder="Filter by parent_invocation_id" />
          </div>
          <button class="fetch-btn" @click="fetchEntries" :disabled="loading">
            {{ loading ? 'Loading...' : 'Fetch' }}
          </button>
        </div>
      </section>

      <!-- Error -->
      <div v-if="error" class="error-bar">{{ error }}</div>

      <!-- Summary -->
      <section class="section" v-if="data">
        <div class="summary-bar">
          <div class="summary-item">
            <span class="summary-label">Entries</span>
            <span class="summary-value">{{ data.count }}</span>
          </div>
          <div class="summary-item" v-if="data.root_principal">
            <span class="summary-label">Root Principal</span>
            <span class="summary-value mono">{{ data.root_principal }}</span>
          </div>
          <div class="summary-item" v-if="data.capability_filter">
            <span class="summary-label">Capability</span>
            <span class="summary-value mono">{{ data.capability_filter }}</span>
          </div>
        </div>
      </section>

      <!-- Entries Table -->
      <section class="section" v-if="data && entries.length">
        <h3 class="section-title">Entries</h3>
        <div class="table-wrapper">
          <table class="data-table">
            <thead>
              <tr>
                <th></th>
                <th>#</th>
                <th>Timestamp</th>
                <th>Capability</th>
                <th>Status</th>
                <th>Event Class</th>
                <th>Task ID</th>
                <th>Parent Inv.</th>
                <th>Retention</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="(entry, idx) in entries" :key="idx">
                <tr class="entry-row" @click="toggleEntry(idx)">
                  <td class="expand-cell">
                    <span class="expand-icon">{{ expandedEntry === idx ? '\u25BC' : '\u25B6' }}</span>
                  </td>
                  <td class="mono-cell">{{ entry.sequence_number || idx + 1 }}</td>
                  <td class="ts-cell">{{ formatTimestamp(entry.timestamp) }}</td>
                  <td class="mono-cell">{{ entry.capability }}</td>
                  <td>
                    <StatusBadge
                      :label="statusLabel(entry)"
                      :type="statusType(entry)"
                    />
                  </td>
                  <td>
                    <StatusBadge
                      v-if="entry.event_class"
                      :label="entry.event_class"
                      :type="eventClassType(entry.event_class)"
                    />
                    <span v-else class="dash">&mdash;</span>
                  </td>
                  <td>
                    <span v-if="entry.task_id" class="mono-cell">{{ entry.task_id }}</span>
                    <span v-else class="dash">&mdash;</span>
                  </td>
                  <td>
                    <span v-if="entry.parent_invocation_id" class="mono-cell">{{ entry.parent_invocation_id }}</span>
                    <span v-else class="dash">&mdash;</span>
                  </td>
                  <td>
                    <span v-if="entry.retention_tier" class="retention-chip">{{ entry.retention_tier }}</span>
                    <span v-else class="dash">&mdash;</span>
                  </td>
                </tr>
                <tr v-if="expandedEntry === idx" class="detail-row">
                  <td :colspan="9">
                    <div class="entry-detail">
                      <div v-if="entry.budget_context" class="audit-context-row">
                        <span class="context-label">Budget:</span>
                        <span class="context-value">{{ entry.budget_context.budget_currency }} {{ entry.budget_context.budget_max }}</span>
                        <span :class="entry.budget_context.within_budget ? 'status-ok' : 'status-error'">
                          {{ entry.budget_context.within_budget ? '\u2713' : '\u2717' }}
                        </span>
                      </div>
                      <div v-if="entry.binding_context" class="audit-context-row">
                        <span class="context-label">Bindings:</span>
                        <span class="context-value">{{ entry.binding_context.bindings_provided?.join(', ') || 'none' }} / {{ entry.binding_context.bindings_required?.join(', ') }}</span>
                      </div>
                      <JsonPanel :data="entry" title="Entry Detail" :collapsed="false" />
                    </div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </section>

      <!-- Empty state -->
      <div v-else-if="data && entries.length === 0" class="empty-state">
        <p>No audit entries found matching the current filters.</p>
      </div>

      <!-- No bearer prompt -->
      <div v-if="!store.bearer" class="empty-state">
        <p>Provide a bearer token above to query audit entries.</p>
      </div>

      <!-- Raw JSON -->
      <section class="section" v-if="data">
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

.content-area {
  flex: 1;
  padding: 24px 32px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 24px;
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

/* Filter Bar */
.filter-bar {
  display: flex;
  align-items: flex-end;
  gap: 16px;
  flex-wrap: wrap;
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.filter-label {
  font-size: 11px;
  color: var(--text-muted);
  font-weight: 500;
}

.filter-select,
.filter-input {
  height: 32px;
  padding: 0 10px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 12px;
  outline: none;
  transition: border-color 150ms ease;
}

.filter-select {
  min-width: 160px;
}

.filter-input {
  min-width: 160px;
}

.num-input {
  min-width: 80px;
  width: 80px;
}

.filter-select:focus,
.filter-input:focus {
  border-color: var(--border-focus);
  box-shadow: 0 0 0 3px var(--accent-glow);
}

.fetch-btn {
  height: 32px;
  padding: 0 20px;
  background: var(--accent);
  border: none;
  border-radius: var(--radius-sm);
  color: #fff;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: background 150ms ease;
}

.fetch-btn:hover:not(:disabled) {
  background: var(--accent-hover);
}

.fetch-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Error */
.error-bar {
  padding: 10px 14px;
  background: rgba(248, 113, 113, 0.1);
  border: 1px solid rgba(248, 113, 113, 0.3);
  border-radius: var(--radius-sm);
  color: var(--error);
  font-size: 13px;
}

/* Summary */
.summary-bar {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
  padding: 12px 16px;
  background: var(--bg-hover);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}

.summary-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.summary-label {
  font-size: 12px;
  color: var(--text-muted);
}

.summary-value {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.summary-value.mono {
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-weight: 400;
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

.entry-row {
  cursor: pointer;
  transition: background 150ms ease;
}

.entry-row:hover td {
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

.ts-cell {
  font-size: 12px;
  white-space: nowrap;
}

.retention-chip {
  display: inline-flex;
  padding: 2px 8px;
  border-radius: 4px;
  background: rgba(108, 99, 255, 0.1);
  color: var(--accent);
  font-size: 11px;
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.dash {
  color: var(--text-muted);
}

.detail-row td {
  padding: 0;
  border-bottom: 1px solid var(--border);
}

.entry-detail {
  padding: 8px 12px 12px;
}

/* Audit context rows */
.audit-context-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
}

.context-label {
  font-size: 12px;
  color: var(--text-muted);
  font-weight: 500;
}

.context-value {
  font-size: 12px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  color: var(--text-primary);
}

.status-ok {
  font-size: 13px;
  font-weight: 600;
  color: var(--success);
}

.status-error {
  font-size: 13px;
  font-weight: 600;
  color: var(--error);
}

/* Empty state */
.empty-state {
  padding: 40px 0;
  text-align: center;
  color: var(--text-muted);
  font-size: 14px;
}
</style>
