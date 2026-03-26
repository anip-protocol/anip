<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { store } from '../store'
import { fetchPermissions } from '../api'

const props = defineProps<{
  bearer: string
  capability: string | null
}>()

const loading = ref(false)
const result = ref<any>(null)
const error = ref('')

async function check() {
  if (!props.bearer || !props.capability) return
  loading.value = true
  error.value = ''
  result.value = null
  try {
    result.value = await fetchPermissions(store.baseUrl, props.bearer)
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Failed to check permissions'
  } finally {
    loading.value = false
  }
}

watch(() => [props.bearer, props.capability], () => {
  if (props.bearer && props.capability) check()
  else { result.value = null; error.value = '' }
}, { immediate: true })

// Derive the status for the selected capability from the full permissions response
const status = computed<'none' | 'loading' | 'available' | 'restricted' | 'denied' | 'error'>(() => {
  if (!props.bearer || !props.capability) return 'none'
  if (loading.value) return 'loading'
  if (error.value) return 'error'
  if (!result.value) return 'none'

  const cap = props.capability
  const available = (result.value.available || []).find((a: any) => a.capability === cap)
  if (available) return 'available'
  const restricted = (result.value.restricted || []).find((r: any) => r.capability === cap)
  if (restricted) return 'restricted'
  const denied = (result.value.denied || []).find((d: any) => d.capability === cap)
  if (denied) return 'denied'

  // Capability not in any bucket — treat as unavailable
  return 'denied'
})

const detail = computed(() => {
  if (!result.value || !props.capability) return null
  const cap = props.capability
  const available = (result.value.available || []).find((a: any) => a.capability === cap)
  if (available) return { scope: available.scope_match }
  const restricted = (result.value.restricted || []).find((r: any) => r.capability === cap)
  if (restricted) return { reason: restricted.reason, grantable_by: restricted.grantable_by }
  const denied = (result.value.denied || []).find((d: any) => d.capability === cap)
  if (denied) return { reason: denied.reason }
  return null
})
</script>

<template>
  <div class="permissions-panel">
    <div class="panel-header">
      <span class="section-label">Permissions</span>
      <button
        v-if="status !== 'none' && status !== 'loading'"
        class="refresh-btn"
        @click="check"
      >
        Refresh
      </button>
    </div>

    <!-- No token or no capability -->
    <div v-if="status === 'none'" class="perm-status neutral">
      <span class="dot neutral-dot"></span>
      <span v-if="!bearer">Enter a bearer token to inspect permissions</span>
      <span v-else-if="!capability">Select a capability to inspect permissions</span>
      <span v-else>Enter a bearer token to inspect permissions</span>
    </div>

    <!-- Loading -->
    <div v-else-if="status === 'loading'" class="perm-status neutral">
      <span class="mini-spinner"></span>
      <span>Checking permissions...</span>
    </div>

    <!-- Available -->
    <div v-else-if="status === 'available'" class="perm-status">
      <span class="dot available-dot"></span>
      <span class="perm-label">Available</span>
      <span v-if="detail?.scope" class="perm-detail">Scope: {{ detail.scope }}</span>
    </div>

    <!-- Restricted -->
    <div v-else-if="status === 'restricted'" class="perm-status">
      <span class="dot restricted-dot"></span>
      <span class="perm-label">Restricted</span>
      <span v-if="detail?.reason" class="perm-detail">{{ detail.reason }}</span>
      <span v-if="detail?.grantable_by" class="perm-detail">Grantable by: {{ detail.grantable_by }}</span>
    </div>

    <!-- Denied -->
    <div v-else-if="status === 'denied'" class="perm-status">
      <span class="dot denied-dot"></span>
      <span class="perm-label">Denied</span>
      <span v-if="detail?.reason" class="perm-detail">{{ detail.reason }}</span>
    </div>

    <!-- Error -->
    <div v-else-if="status === 'error'" class="perm-status">
      <span class="dot error-dot"></span>
      <span class="perm-label">Unable to check permissions</span>
      <span class="perm-detail error-text">{{ error }}</span>
    </div>

    <div class="perm-advisory">Advisory — the invocation result is authoritative</div>
  </div>
</template>

<style scoped>
.permissions-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.section-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.refresh-btn {
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: 11px;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
  transition: all 150ms ease;
}

.refresh-btn:hover {
  color: var(--accent);
  background: var(--accent-glow);
}

.perm-status {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--text-secondary);
  flex-wrap: wrap;
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

.available-dot { background: var(--success); box-shadow: 0 0 6px rgba(52, 211, 153, 0.4); }
.restricted-dot { background: #fbbf24; box-shadow: 0 0 6px rgba(251, 191, 36, 0.4); }
.denied-dot { background: var(--error); box-shadow: 0 0 6px rgba(248, 113, 113, 0.4); }
.error-dot { background: var(--text-muted); }
.neutral-dot { background: var(--text-muted); }

.perm-label {
  font-weight: 600;
  color: var(--text-primary);
}

.perm-detail {
  font-size: 11px;
  color: var(--text-muted);
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.error-text {
  color: var(--error) !important;
}

.mini-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  flex-shrink: 0;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.perm-advisory {
  font-size: 10px;
  color: var(--text-muted);
  font-style: italic;
}
</style>
