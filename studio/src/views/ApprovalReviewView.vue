<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { store } from '../store'
import BearerInput from '../components/BearerInput.vue'
import JsonPanel from '../components/JsonPanel.vue'
import StatusBadge from '../components/StatusBadge.vue'

const route = useRoute()

const listPath = ref('/approvals')
const approvePathTemplate = ref('/approvals/{approvalRequestId}/approve')
const statusFilter = ref('')
const loading = ref(false)
const actionLoadingId = ref<string | null>(null)
const error = ref('')
const responseData = ref<any | null>(null)
const lastAction = ref<any | null>(null)

const entries = computed<any[]>(() => {
  const payload = responseData.value
  if (Array.isArray(payload)) return payload
  if (Array.isArray(payload?.entries)) return payload.entries
  if (Array.isArray(payload?.approvals)) return payload.approvals
  if (Array.isArray(payload?.approvals?.entries)) return payload.approvals.entries
  return []
})

function syncFromRoute() {
  listPath.value = typeof route.query.listPath === 'string' && route.query.listPath.trim()
    ? route.query.listPath
    : '/approvals'
  approvePathTemplate.value = typeof route.query.approvePathTemplate === 'string' && route.query.approvePathTemplate.trim()
    ? route.query.approvePathTemplate
    : '/approvals/{approvalRequestId}/approve'
  statusFilter.value = typeof route.query.status === 'string' ? route.query.status : ''
}

function normalizePath(path: string) {
  const trimmed = path.trim()
  if (!trimmed) return ''
  return trimmed.startsWith('/') ? trimmed : `/${trimmed}`
}

function buildUrl(path: string, params?: Record<string, string>) {
  const normalizedPath = normalizePath(path)
  if (!store.baseUrl || !normalizedPath) return ''
  const url = new URL(`${store.baseUrl.replace(/\/+$/, '')}${normalizedPath}`)
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value) url.searchParams.set(key, value)
    }
  }
  return url.toString()
}

function approvalRequestIdFor(entry: any) {
  return String(entry?.approval_request_id || entry?.id || '').trim()
}

function actorSummary(entry: any) {
  const requestedBy = entry?.requested_by || {}
  const actorId = String(requestedBy.actor_id || '').trim()
  const role = String(requestedBy.role || '').trim()
  if (actorId && role) return `${actorId} (${role})`
  return actorId || role || '-'
}

function approverSummary(entry: any) {
  const approvedBy = entry?.approved_by || {}
  const actorId = String(approvedBy.actor_id || '').trim()
  const role = String(approvedBy.role || '').trim()
  if (actorId && role) return `${actorId} (${role})`
  return actorId || role || '-'
}

function statusType(status: string): 'success' | 'warning' | 'danger' | 'info' | 'neutral' {
  const normalized = status.trim().toLowerCase()
  if (normalized === 'approved') return 'success'
  if (normalized === 'pending') return 'warning'
  if (normalized === 'denied' || normalized === 'rejected') return 'danger'
  if (normalized === 'approval_required') return 'info'
  return 'neutral'
}

async function fetchApprovals() {
  if (!store.connected || !store.bearer) return
  loading.value = true
  error.value = ''
  try {
    const url = buildUrl(listPath.value, statusFilter.value ? { status: statusFilter.value } : undefined)
    if (!url) throw new Error('Approval list path is required.')
    const response = await fetch(url, {
      headers: {
        Authorization: `Bearer ${store.bearer}`,
      },
    })
    const payload = await response.json()
    if (!response.ok) {
      throw new Error(payload?.detail || `Request failed with status ${response.status}`)
    }
    responseData.value = payload
  } catch (err: any) {
    error.value = err?.message || 'Failed to fetch approvals.'
  } finally {
    loading.value = false
  }
}

async function approve(entry: any) {
  if (!store.connected || !store.bearer) return
  const approvalRequestId = approvalRequestIdFor(entry)
  if (!approvalRequestId) return
  actionLoadingId.value = approvalRequestId
  error.value = ''
  lastAction.value = null
  try {
    const path = normalizePath(approvePathTemplate.value)
      .replace('{approvalRequestId}', encodeURIComponent(approvalRequestId))
      .replace('{id}', encodeURIComponent(approvalRequestId))
    if (!path) throw new Error('Approval action path template is required.')
    const response = await fetch(buildUrl(path), {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${store.bearer}`,
      },
    })
    const payload = await response.json()
    if (!response.ok) {
      throw new Error(payload?.detail || `Approval failed with status ${response.status}`)
    }
    lastAction.value = payload
    await fetchApprovals()
  } catch (err: any) {
    error.value = err?.message || 'Failed to approve request.'
  } finally {
    actionLoadingId.value = null
  }
}

function onAuthenticated() {
  fetchApprovals()
}

onMounted(syncFromRoute)
watch(() => route.query, syncFromRoute)
</script>

<template>
  <div class="view">
    <div class="view-header">
      <h2>Approval Review</h2>
      <span class="view-subtitle">Linked approval surface over the connected service</span>
    </div>

    <div v-if="!store.connected" class="placeholder">
      <div class="placeholder-icon">&#x2714;</div>
      <p>Connect to a service, provide a bearer, and point Studio at its approval list and approval-action endpoints.</p>
    </div>

    <div v-else class="content-area">
      <section class="section">
        <h3 class="section-title">Authentication</h3>
        <BearerInput @authenticated="onAuthenticated" />
      </section>

      <section class="section">
        <h3 class="section-title">Approval Surface</h3>
        <div class="filter-bar">
          <div class="filter-group">
            <label class="filter-label">List Path</label>
            <input v-model="listPath" type="text" class="filter-input wide-input" placeholder="/approvals or /domain/approvals" />
          </div>
          <div class="filter-group">
            <label class="filter-label">Approve Path Template</label>
            <input
              v-model="approvePathTemplate"
              type="text"
              class="filter-input wide-input"
              placeholder="/approvals/{approvalRequestId}/approve"
            />
          </div>
          <div class="filter-group">
            <label class="filter-label">Status</label>
            <select v-model="statusFilter" class="filter-select">
              <option value="">All</option>
              <option value="pending">Pending</option>
              <option value="approved">Approved</option>
            </select>
          </div>
          <button class="fetch-btn" @click="fetchApprovals" :disabled="loading || !store.bearer">
            {{ loading ? 'Loading...' : 'Fetch' }}
          </button>
        </div>
      </section>

      <div v-if="error" class="error-bar">{{ error }}</div>

      <section class="section" v-if="responseData">
        <div class="summary-bar">
          <div class="summary-item">
            <span class="summary-label">Entries</span>
            <span class="summary-value">{{ entries.length }}</span>
          </div>
          <div class="summary-item">
            <span class="summary-label">Base URL</span>
            <span class="summary-value mono">{{ store.baseUrl }}</span>
          </div>
        </div>
      </section>

      <section class="section" v-if="entries.length">
        <h3 class="section-title">Requests</h3>
        <div class="table-wrapper">
          <table class="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Status</th>
                <th>Capability</th>
                <th>Requested By</th>
                <th>Required Role</th>
                <th>Approved By</th>
                <th>Requested At</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="entry in entries" :key="approvalRequestIdFor(entry)">
                <td class="mono-cell">{{ approvalRequestIdFor(entry) || '-' }}</td>
                <td>
                  <StatusBadge
                    :label="String(entry.status || 'unknown').toUpperCase()"
                    :type="statusType(String(entry.status || 'unknown'))"
                  />
                </td>
                <td class="mono-cell">{{ entry.capability || '-' }}</td>
                <td>{{ actorSummary(entry) }}</td>
                <td class="mono-cell">{{ entry.required_role || '-' }}</td>
                <td>{{ approverSummary(entry) }}</td>
                <td class="mono-cell">{{ entry.requested_at || '-' }}</td>
                <td>
                  <button
                    class="fetch-btn approve-btn"
                    @click="approve(entry)"
                    :disabled="actionLoadingId === approvalRequestIdFor(entry) || String(entry.status || '') !== 'pending' || !store.bearer"
                  >
                    {{ actionLoadingId === approvalRequestIdFor(entry) ? 'Approving...' : 'Approve' }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <div v-else-if="responseData" class="empty-state">
        <p>No approval requests were returned for the current surface and filter.</p>
      </div>

      <div v-if="!store.bearer" class="empty-state">
        <p>Provide a bearer token above to review approval requests.</p>
      </div>

      <section class="section" v-if="lastAction">
        <JsonPanel :data="lastAction" title="Last Approval Action" :collapsed="false" />
      </section>

      <section class="section" v-if="responseData">
        <JsonPanel :data="responseData" title="Raw Response" :collapsed="true" />
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
  font-size: 42px;
  opacity: 0.4;
}

.placeholder p {
  font-size: 14px;
  max-width: 420px;
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

.filter-input,
.filter-select {
  height: 32px;
  padding: 0 10px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 12px;
  outline: none;
}

.wide-input {
  min-width: 320px;
}

.filter-select {
  min-width: 120px;
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
}

.fetch-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.approve-btn {
  height: 28px;
  padding: 0 12px;
}

.error-bar {
  padding: 10px 14px;
  background: rgba(248, 113, 113, 0.1);
  border: 1px solid rgba(248, 113, 113, 0.3);
  border-radius: var(--radius-sm);
  color: var(--error);
  font-size: 13px;
}

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

.summary-value.mono,
.mono-cell {
  font-family: 'SF Mono', 'Fira Code', monospace;
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

.empty-state {
  padding: 40px 0;
  text-align: center;
  color: var(--text-muted);
  font-size: 14px;
}
</style>
