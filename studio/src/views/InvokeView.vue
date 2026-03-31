<script setup lang="ts">
import { ref, watch, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { store } from '../store'
import { fetchManifest, invokeCapability } from '../api'
import StatusBadge from '../components/StatusBadge.vue'
import BearerInput from '../components/BearerInput.vue'
import PermissionsPanel from '../components/PermissionsPanel.vue'
import InvokeForm from '../components/InvokeForm.vue'
import InvokeResult from '../components/InvokeResult.vue'

const route = useRoute()
const router = useRouter()

const manifest = ref<any>(null)
const loading = ref(false)
const error = ref('')
const selectedCapability = ref<string | null>(null)
const userInputs = ref<Record<string, Record<string, string>>>({})
const invokeResult = ref<any>(null)
const invoking = ref(false)
const taskId = ref('')
const parentInvocationId = ref('')

// Load manifest
async function loadManifest() {
  if (!store.connected) return
  loading.value = true
  error.value = ''
  try {
    const result = await fetchManifest(store.baseUrl)
    manifest.value = result.manifest
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Failed to load manifest'
  } finally {
    loading.value = false
  }
}

onMounted(loadManifest)
watch(() => store.connected, (connected) => {
  if (connected) loadManifest()
  else { manifest.value = null }
})

// Sync route param → selected capability
watch(() => route.params.capability, (cap) => {
  const name = cap as string | undefined
  if (name) {
    if (name !== selectedCapability.value) {
      selectedCapability.value = name
      invokeResult.value = null
    }
  } else {
    // Back to picker — clear selection
    selectedCapability.value = null
    invokeResult.value = null
  }
}, { immediate: true })

const capabilities = computed(() => manifest.value?.capabilities || {})
const capabilityNames = computed(() => Object.keys(capabilities.value))

// Validate selected capability exists in manifest — handles invalid deep links
const declaration = computed(() => {
  if (!selectedCapability.value) return null
  return capabilities.value[selectedCapability.value] || null
})
const invalidCapability = computed(() =>
  selectedCapability.value != null && manifest.value != null && declaration.value == null
)

const sideEffectType = computed(() => {
  const se = declaration.value?.side_effect
  return se?.type || 'read'
})

const sideEffectBadge = computed<{ label: string; type: 'success' | 'warning' | 'danger' | 'info' | 'neutral' }>(() => {
  const map: Record<string, { label: string; type: 'success' | 'warning' | 'danger' | 'info' | 'neutral' }> = {
    read: { label: 'Read', type: 'success' },
    write: { label: 'Write', type: 'warning' },
    transactional: { label: 'Transactional', type: 'warning' },
    irreversible: { label: 'Irreversible', type: 'danger' },
  }
  return map[sideEffectType.value] || { label: sideEffectType.value, type: 'warning' }
})

const scope = computed(() => declaration.value?.minimum_scope || [])
const cost = computed(() => declaration.value?.cost)
const responseModes = computed(() => declaration.value?.response_modes || ['unary'])
const hasStreaming = computed(() => responseModes.value.includes('streaming'))

function selectCapability(name: string) {
  router.push(`/invoke/${name}`)
}

function onFormUpdate(inputs: Record<string, string>) {
  if (selectedCapability.value) {
    userInputs.value[selectedCapability.value] = inputs
  }
}

async function onInvoke(inputs: Record<string, string>) {
  if (!selectedCapability.value || !store.bearer) return
  invoking.value = true
  invokeResult.value = null
  try {
    const opts: Record<string, string> = {}
    if (taskId.value.trim()) opts.task_id = taskId.value.trim()
    if (parentInvocationId.value.trim()) opts.parent_invocation_id = parentInvocationId.value.trim()
    invokeResult.value = await invokeCapability(
      store.baseUrl, store.bearer, selectedCapability.value, inputs, opts
    )
  } catch (e: unknown) {
    // Transport error — wrap as a failure-like object for InvokeResult
    invokeResult.value = {
      success: false,
      failure: {
        type: 'transport_error',
        detail: e instanceof Error ? e.message : 'Network error',
        retry: true,
        resolution: { action: 'Check the service is running and reachable' },
      },
    }
  } finally {
    invoking.value = false
  }
}
</script>

<template>
  <div class="view">
    <div class="view-header">
      <h2>Invoke</h2>
      <span class="view-subtitle">/anip/invoke/{{ selectedCapability || '...' }}</span>
    </div>

    <!-- Not connected -->
    <div v-if="!store.connected" class="placeholder">
      <div class="placeholder-icon">&#x26A1;</div>
      <p>Connect to an ANIP service to invoke capabilities.</p>
    </div>

    <!-- Loading manifest -->
    <div v-else-if="loading" class="placeholder">
      <div class="spinner"></div>
      <p>Loading manifest...</p>
    </div>

    <!-- Manifest error -->
    <div v-else-if="error" class="placeholder">
      <p class="error-text">{{ error }}</p>
      <button class="retry-btn" @click="loadManifest">Retry</button>
    </div>

    <!-- Invalid capability -->
    <div v-else-if="invalidCapability" class="placeholder">
      <p class="error-text">Unknown capability: {{ selectedCapability }}</p>
      <button class="retry-btn" @click="router.push('/invoke')">Back to picker</button>
    </div>

    <!-- Main content -->
    <div v-else class="content-area">
      <!-- 1. Declaration summary bar / capability picker -->
      <section class="section">
        <div v-if="!selectedCapability" class="picker">
          <div class="section-label">Select Capability</div>
          <div class="picker-list">
            <div
              v-for="name in capabilityNames"
              :key="name"
              class="picker-item"
              @click="selectCapability(name)"
            >
              <span class="picker-name">{{ name }}</span>
              <StatusBadge
                :label="{ read: 'Read', write: 'Write', transactional: 'Transactional', irreversible: 'Irreversible' }[capabilities[name]?.side_effect?.type || 'read'] || capabilities[name]?.side_effect?.type || 'Read'"
                :type="(capabilities[name]?.side_effect?.type || 'read') === 'read' ? 'success' : (capabilities[name]?.side_effect?.type === 'irreversible' ? 'danger' : 'warning')"
              />
            </div>
          </div>
        </div>
        <div v-else class="declaration-bar">
          <button class="back-btn" @click="router.push('/invoke')" title="Back to picker">&larr;</button>
          <span class="cap-name">{{ selectedCapability }}</span>
          <StatusBadge :label="sideEffectBadge.label" :type="sideEffectBadge.type" />
          <span v-for="s in scope" :key="s" class="scope-chip">{{ s }}</span>
          <span v-if="cost?.financial" class="cost-summary">
            {{ cost.financial.currency }} {{ cost.financial.range_min }}&ndash;{{ cost.financial.range_max }}
          </span>
          <span v-if="hasStreaming" class="streaming-note">
            Streaming supported; Studio currently invokes in unary mode.
          </span>
        </div>
      </section>

      <!-- Only show the rest when a capability is selected -->
      <template v-if="selectedCapability && declaration">
        <!-- 2. Auth bar -->
        <section class="section">
          <div class="section-label">Auth</div>
          <BearerInput />
        </section>

        <!-- 3. Permissions panel -->
        <section class="section">
          <PermissionsPanel
            :bearer="store.bearer"
            :capability="selectedCapability"
          />
        </section>

        <!-- 4. Input form + 5. Invoke button -->
        <section class="section">
          <InvokeForm
            :declaration="declaration"
            :capability-name="selectedCapability"
            :initial-values="userInputs[selectedCapability]"
            :disabled="!store.bearer || invoking"
            @submit="onInvoke"
            @update="onFormUpdate"
          />
          <div v-if="invoking" class="invoking-indicator">
            <div class="mini-spinner"></div>
            <span>Invoking...</span>
          </div>
        </section>

        <!-- Optional: task_id and parent_invocation_id -->
        <section class="section">
          <div class="section-label">Lineage (optional)</div>
          <div class="lineage-fields">
            <div class="lineage-field">
              <label class="lineage-label">task_id</label>
              <input
                v-model="taskId"
                type="text"
                class="lineage-input"
                placeholder="Group related invocations"
              />
            </div>
            <div class="lineage-field">
              <label class="lineage-label">parent_invocation_id</label>
              <input
                v-model="parentInvocationId"
                type="text"
                class="lineage-input"
                placeholder="Invocation that triggered this one"
              />
            </div>
          </div>
        </section>

        <!-- 6. Result panel -->
        <section class="section">
          <InvokeResult :result="invokeResult" />
        </section>
      </template>
    </div>
  </div>
</template>

<style scoped>
.view { height: 100%; display: flex; flex-direction: column; }
.view-header { padding: 24px 32px 16px; border-bottom: 1px solid var(--border); }
.view-header h2 { font-size: 20px; font-weight: 600; color: var(--text-primary); margin-bottom: 4px; }
.view-subtitle { font-size: 13px; color: var(--text-muted); font-family: 'SF Mono', 'Fira Code', monospace; }

.placeholder {
  flex: 1; display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 16px; color: var(--text-muted);
}
.placeholder-icon { font-size: 48px; opacity: 0.4; }
.placeholder p { font-size: 14px; max-width: 320px; text-align: center; line-height: 1.5; }
.error-text { color: var(--error) !important; }
.retry-btn {
  padding: 6px 16px; background: var(--accent); border: none;
  border-radius: var(--radius-sm); color: #fff; font-size: 13px; cursor: pointer;
}
.retry-btn:hover { background: var(--accent-hover); }

.spinner {
  width: 32px; height: 32px; border: 3px solid var(--border);
  border-top-color: var(--accent); border-radius: 50%; animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.content-area {
  flex: 1; padding: 24px 32px; overflow-y: auto;
  display: flex; flex-direction: column; gap: 24px;
}

.section { display: flex; flex-direction: column; gap: 10px; }
.section-label {
  font-size: 11px; font-weight: 600; color: var(--text-muted);
  text-transform: uppercase; letter-spacing: 0.5px;
}

/* Capability picker */
.picker-list { display: flex; flex-direction: column; gap: 4px; }
.picker-item {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 14px; border: 1px solid var(--border); border-radius: var(--radius-sm);
  cursor: pointer; transition: all 150ms ease;
}
.picker-item:hover { background: var(--bg-hover); border-color: rgba(108, 99, 255, 0.3); }
.picker-name {
  font-size: 14px; font-weight: 600; font-family: 'SF Mono', 'Fira Code', monospace;
  color: var(--text-primary);
}

/* Declaration bar */
.declaration-bar {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  padding: 10px 14px; background: var(--bg-hover); border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}
.back-btn {
  background: none; border: none; color: var(--text-muted);
  font-size: 16px; cursor: pointer; padding: 0 4px;
}
.back-btn:hover { color: var(--text-primary); }
.cap-name {
  font-size: 14px; font-weight: 600; font-family: 'SF Mono', 'Fira Code', monospace;
  color: var(--text-primary);
}
.scope-chip {
  display: inline-flex; align-items: center; padding: 2px 8px; border-radius: 4px;
  background: rgba(108, 99, 255, 0.1); color: var(--accent);
  font-size: 11px; font-family: 'SF Mono', 'Fira Code', monospace;
}
.cost-summary {
  font-size: 11px; font-family: 'SF Mono', 'Fira Code', monospace; color: var(--text-muted);
}
.streaming-note {
  font-size: 11px; color: var(--text-muted); font-style: italic;
}

/* Invoking state */
.invoking-indicator {
  display: flex; align-items: center; gap: 8px;
  font-size: 12px; color: var(--text-muted);
}
.mini-spinner {
  width: 14px; height: 14px; border: 2px solid var(--border);
  border-top-color: var(--accent); border-radius: 50%; animation: spin 0.8s linear infinite;
}

/* Lineage fields */
.lineage-fields {
  display: flex; gap: 16px; flex-wrap: wrap;
}
.lineage-field {
  display: flex; flex-direction: column; gap: 4px; flex: 1; min-width: 200px;
}
.lineage-label {
  font-size: 12px; font-family: 'SF Mono', 'Fira Code', monospace;
  color: var(--text-muted); font-weight: 500;
}
.lineage-input {
  height: 34px; padding: 0 12px;
  background: var(--bg-input); border: 1px solid var(--border);
  border-radius: var(--radius-sm); color: var(--text-primary);
  font-size: 13px; font-family: 'SF Mono', 'Fira Code', monospace;
  outline: none; transition: border-color 150ms ease, box-shadow 150ms ease;
}
.lineage-input::placeholder { color: var(--text-muted); }
.lineage-input:focus {
  border-color: var(--border-focus);
  box-shadow: 0 0 0 3px var(--accent-glow);
}
</style>
