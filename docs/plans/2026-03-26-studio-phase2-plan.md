# ANIP Studio Phase 2: Invocation — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add interactive capability invocation to ANIP Studio — form-based invoke, permissions inspection, and structured success/failure display.

**Architecture:** New `/invoke/:capability?` route with four components: `InvokeView` (orchestrator), `InvokeForm` (dumb form from manifest inputs), `PermissionsPanel` (auto-check with five states), `InvokeResult` (success/failure rendering). Two new API functions in `api.ts`. Deep links from Manifest's `CapabilityCard`. Single-column stacked layout.

**Tech Stack:** Vue 3, vue-router, TypeScript, Vite (existing Studio stack — no new dependencies)

**Spec:** `docs/specs/2026-03-26-studio-phase2-design.md`

---

## File Structure

```
studio/src/
├── api.ts                              # MODIFY: add invokeCapability, fetchPermissions
├── router.ts                           # MODIFY: add /invoke/:capability? route
├── App.vue                             # MODIFY: add Invoke nav item to sidebar
├── views/
│   └── InvokeView.vue                  # CREATE: orchestrator page
├── components/
│   ├── CapabilityCard.vue              # MODIFY: add router-link to /invoke/:name
│   ├── InvokeForm.vue                  # CREATE: dumb form from manifest inputs
│   ├── PermissionsPanel.vue            # CREATE: auto-check permissions display
│   └── InvokeResult.vue               # CREATE: success/failure result rendering
```

---

## Task 1: API Layer — `invokeCapability` and `fetchPermissions`

**Files:**
- Modify: `studio/src/api.ts`

- [ ] **Step 1: Add `invokeCapability` to `api.ts`**

```typescript
export async function invokeCapability(
  baseUrl: string,
  bearer: string,
  capability: string,
  inputs: Record<string, any>,
): Promise<any> {
  const res = await fetch(`${baseUrl}/anip/invoke/${capability}`, {
    method: 'POST',
    headers: headers(bearer),
    body: JSON.stringify({ parameters: inputs }),
  })
  // ANIP returns invocation failures as non-2xx JSON bodies.
  // Parse the body regardless of status — InvokeResult needs the full
  // { success, failure, invocation_id } payload for structured failure UX.
  const contentType = res.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    return res.json()
  }
  // Non-JSON response is a transport error — throw.
  throw new Error(`Invoke ${capability}: ${res.status} (non-JSON response)`)
}
```

- [ ] **Step 2: Add `fetchPermissions` to `api.ts`**

```typescript
export async function fetchPermissions(
  baseUrl: string,
  bearer: string,
  capability?: string,
): Promise<any> {
  const res = await fetch(`${baseUrl}/anip/permissions`, {
    method: 'POST',
    headers: headers(bearer),
    body: JSON.stringify(capability ? { capability } : {}),
  })
  if (!res.ok) throw new Error(`Permissions: ${res.status}`)
  return res.json()
}
```

- [ ] **Step 3: Verify build**

Run: `cd studio && npx vue-tsc --noEmit`
Expected: no type errors

- [ ] **Step 4: Commit**

```bash
git add studio/src/api.ts
git commit -m "feat(studio): add invokeCapability and fetchPermissions API functions"
```

---

## Task 2: Route and Navigation

**Files:**
- Modify: `studio/src/router.ts`
- Modify: `studio/src/App.vue`

- [ ] **Step 1: Add invoke route to `router.ts`**

Add after the checkpoints route in the `routes` array:

```typescript
  {
    path: '/invoke/:capability?',
    name: 'invoke',
    component: () => import('./views/InvokeView.vue'),
  },
```

- [ ] **Step 2: Add Invoke nav item to `App.vue`**

Add to the `navItems` array after the checkpoints entry:

```typescript
  { name: 'invoke', label: 'Invoke', icon: '\u26A1', path: '/invoke' },
```

- [ ] **Step 3: Add deep link to `CapabilityCard.vue`**

Add a `<router-link>` in the `.cap-header` div, before the `.cap-version` span (no import needed — `router-link` is globally registered by vue-router):

```vue
<router-link
  :to="'/invoke/' + name"
  class="invoke-link"
  @click.stop
>
  Invoke
</router-link>
```

Add the style:

```css
.invoke-link {
  margin-left: auto;
  font-size: 11px;
  color: var(--accent);
  text-decoration: none;
  padding: 2px 8px;
  border-radius: 4px;
  transition: background 150ms ease;
}

.invoke-link:hover {
  background: var(--accent-glow);
}
```

And move the existing `.cap-version` `margin-left: auto` to `margin-left: 8px` since the invoke link now uses `margin-left: auto`.

- [ ] **Step 4: Create stub `InvokeView.vue`**

Create `studio/src/views/InvokeView.vue` with a minimal placeholder so the route resolves:

```vue
<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()
const capability = route.params.capability as string | undefined
</script>

<template>
  <div class="view">
    <div class="view-header">
      <h2>Invoke</h2>
      <span class="view-subtitle">/anip/invoke/{{ capability || '...' }}</span>
    </div>
    <div class="placeholder">
      <p>Invoke view — under construction</p>
    </div>
  </div>
</template>

<style scoped>
.view { height: 100%; display: flex; flex-direction: column; }
.view-header { padding: 24px 32px 16px; border-bottom: 1px solid var(--border); }
.view-header h2 { font-size: 20px; font-weight: 600; color: var(--text-primary); margin-bottom: 4px; }
.view-subtitle { font-size: 13px; color: var(--text-muted); font-family: 'SF Mono', 'Fira Code', monospace; }
.placeholder { flex: 1; display: flex; align-items: center; justify-content: center; color: var(--text-muted); }
</style>
```

- [ ] **Step 5: Verify build and navigation**

Run: `cd studio && npx vue-tsc --noEmit`
Expected: no type errors

Run: `cd studio && npx vite build`
Expected: build succeeds

- [ ] **Step 6: Commit**

```bash
git add studio/src/router.ts studio/src/App.vue studio/src/components/CapabilityCard.vue studio/src/views/InvokeView.vue
git commit -m "feat(studio): add invoke route, nav item, and deep links from manifest"
```

---

## Task 3: `InvokeForm.vue`

**Files:**
- Create: `studio/src/components/InvokeForm.vue`

- [ ] **Step 1: Create `InvokeForm.vue`**

```vue
<script setup lang="ts">
import { ref, watch, computed } from 'vue'

const props = defineProps<{
  declaration: Record<string, any>
  capabilityName: string
  initialValues?: Record<string, string>
  disabled?: boolean
}>()

const emit = defineEmits<{
  submit: [inputs: Record<string, string>]
  update: [inputs: Record<string, string>]
}>()

const inputs = ref<Record<string, string>>({})

// Initialize from defaults and initialValues
function initInputs() {
  const values: Record<string, string> = {}
  const fields = props.declaration.inputs || []
  for (const field of fields) {
    values[field.name] = props.initialValues?.[field.name]
      ?? (field.default != null ? String(field.default) : '')
  }
  inputs.value = values
}

initInputs()
// Re-init only when the declaration changes (capability switch), not on
// every initialValues echo-back — avoids redundant reactivity churn.
watch(() => props.declaration, initInputs)

watch(inputs, (val) => emit('update', { ...val }), { deep: true })

const fields = computed(() => props.declaration.inputs || [])

const canSubmit = computed(() => {
  if (props.disabled) return false
  for (const field of fields.value) {
    if (field.required !== false && !inputs.value[field.name]?.trim()) {
      return false
    }
  }
  return true
})

function onSubmit() {
  if (canSubmit.value) {
    emit('submit', { ...inputs.value })
  }
}
</script>

<template>
  <div class="invoke-form">
    <div class="section-label">Inputs</div>
    <div v-if="!fields.length" class="no-inputs">This capability takes no inputs.</div>
    <div v-else class="fields">
      <div v-for="field in fields" :key="field.name" class="field">
        <label class="field-label">
          <span class="field-name">{{ field.name }}</span>
          <span class="field-type">{{ field.type || 'string' }}</span>
          <span v-if="field.required !== false" class="field-required">*</span>
        </label>
        <input
          v-model="inputs[field.name]"
          type="text"
          class="field-input"
          :placeholder="field.description || field.name"
        />
      </div>
    </div>
    <button
      class="invoke-btn"
      :disabled="!canSubmit"
      @click="onSubmit"
    >
      Invoke {{ capabilityName }}
    </button>
  </div>
</template>

<style scoped>
.invoke-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.no-inputs {
  font-size: 13px;
  color: var(--text-muted);
  padding: 8px 0;
}

.fields {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.field-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}

.field-name {
  font-family: 'SF Mono', 'Fira Code', monospace;
  color: var(--text-primary);
  font-weight: 500;
}

.field-type {
  color: var(--text-muted);
  font-size: 11px;
}

.field-required {
  color: #f87171;
  font-weight: 600;
}

.field-input {
  height: 34px;
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

.field-input::placeholder {
  color: var(--text-muted);
}

.field-input:focus {
  border-color: var(--border-focus);
  box-shadow: 0 0 0 3px var(--accent-glow);
}

.invoke-btn {
  height: 38px;
  padding: 0 24px;
  background: var(--accent);
  border: none;
  border-radius: var(--radius-sm);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background 150ms ease;
  margin-top: 4px;
}

.invoke-btn:hover:not(:disabled) {
  background: var(--accent-hover);
}

.invoke-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
```

- [ ] **Step 2: Verify build**

Run: `cd studio && npx vue-tsc --noEmit`
Expected: no type errors

- [ ] **Step 3: Commit**

```bash
git add studio/src/components/InvokeForm.vue
git commit -m "feat(studio): add InvokeForm component"
```

---

## Task 4: `PermissionsPanel.vue`

**Files:**
- Create: `studio/src/components/PermissionsPanel.vue`

The ANIP permissions response shape (from `anip-core/models.py`):
```json
{
  "available": [{ "capability": "search_flights", "scope_match": "flights:search", "constraints": {} }],
  "restricted": [{ "capability": "book_flight", "reason": "missing scope", "grantable_by": "human" }],
  "denied": [{ "capability": "admin_reset", "reason": "requires admin principal" }]
}
```

- [ ] **Step 1: Create `PermissionsPanel.vue`**

```vue
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
```

- [ ] **Step 2: Verify build**

Run: `cd studio && npx vue-tsc --noEmit`
Expected: no type errors

- [ ] **Step 3: Commit**

```bash
git add studio/src/components/PermissionsPanel.vue
git commit -m "feat(studio): add PermissionsPanel component with five-state display"
```

---

## Task 5: `InvokeResult.vue`

**Files:**
- Create: `studio/src/components/InvokeResult.vue`

- [ ] **Step 1: Create `InvokeResult.vue`**

```vue
<script setup lang="ts">
import { computed } from 'vue'
import StatusBadge from './StatusBadge.vue'
import JsonPanel from './JsonPanel.vue'

const props = defineProps<{
  result: Record<string, any> | null
}>()

const isSuccess = computed(() => props.result?.success === true)
const failure = computed(() => props.result?.failure || null)
const resolution = computed(() => failure.value?.resolution || null)
</script>

<template>
  <div v-if="result" class="invoke-result">
    <div class="section-label">Result</div>

    <!-- Success -->
    <div v-if="isSuccess" class="result-body">
      <div class="result-status-line">
        <StatusBadge label="Success" type="success" />
        <span class="invocation-id">{{ result.invocation_id }}</span>
      </div>

      <div v-if="result.client_reference_id" class="result-meta">
        <span class="meta-label">client_reference_id</span>
        <span class="meta-value">{{ result.client_reference_id }}</span>
      </div>

      <div v-if="result.cost_actual" class="result-meta">
        <span class="meta-label">cost_actual</span>
        <span class="meta-value">
          {{ result.cost_actual.currency }} {{ result.cost_actual.amount }}
        </span>
      </div>

      <JsonPanel :data="result.result" title="Result Data" :collapsed="false" />
    </div>

    <!-- Failure -->
    <div v-else class="result-body">
      <div class="result-status-line">
        <StatusBadge label="Failed" type="danger" />
        <StatusBadge v-if="failure?.type" :label="failure.type" type="warning" />
        <span class="invocation-id">{{ result.invocation_id }}</span>
      </div>

      <div v-if="result.client_reference_id" class="result-meta">
        <span class="meta-label">client_reference_id</span>
        <span class="meta-value">{{ result.client_reference_id }}</span>
      </div>

      <!-- Failure detail -->
      <p v-if="failure?.detail" class="failure-detail">{{ failure.detail }}</p>

      <!-- Resolution callout -->
      <div v-if="resolution" class="resolution-callout">
        <div class="resolution-title">Resolution</div>
        <div v-if="resolution.action" class="resolution-field">
          <span class="meta-label">Action</span>
          <span class="meta-value">{{ resolution.action }}</span>
        </div>
        <div v-if="resolution.requires" class="resolution-field">
          <span class="meta-label">Requires</span>
          <span class="meta-value">{{ resolution.requires }}</span>
        </div>
        <div v-if="resolution.grantable_by" class="resolution-field">
          <span class="meta-label">Grantable by</span>
          <span class="meta-value">{{ resolution.grantable_by }}</span>
        </div>
        <div v-if="resolution.estimated_availability" class="resolution-field">
          <span class="meta-label">Availability</span>
          <span class="meta-value">{{ resolution.estimated_availability }}</span>
        </div>
      </div>

      <!-- Retry -->
      <div class="result-meta">
        <span class="meta-label">Retryable</span>
        <span class="meta-value">{{ failure?.retry ? 'yes' : 'no' }}</span>
      </div>

      <JsonPanel :data="result" title="Raw Response" :collapsed="true" />
    </div>
  </div>
</template>

<style scoped>
.invoke-result {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.result-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.result-status-line {
  display: flex;
  align-items: center;
  gap: 8px;
}

.invocation-id {
  margin-left: auto;
  font-size: 11px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  color: var(--text-muted);
  user-select: all;
}

.result-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.meta-label {
  font-size: 11px;
  color: var(--text-muted);
}

.meta-value {
  font-size: 12px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  color: var(--text-primary);
}

.failure-detail {
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.5;
  margin: 0;
}

.resolution-callout {
  background: rgba(108, 99, 255, 0.08);
  border-left: 3px solid var(--accent);
  padding: 10px 14px;
  border-radius: 0 6px 6px 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.resolution-title {
  font-size: 10px;
  text-transform: uppercase;
  color: var(--accent);
  font-weight: 600;
  letter-spacing: 0.5px;
}

.resolution-field {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
```

- [ ] **Step 2: Verify build**

Run: `cd studio && npx vue-tsc --noEmit`
Expected: no type errors

- [ ] **Step 3: Commit**

```bash
git add studio/src/components/InvokeResult.vue
git commit -m "feat(studio): add InvokeResult component with structured failure display"
```

---

## Task 6: `InvokeView.vue` — Full Orchestrator

**Files:**
- Modify: `studio/src/views/InvokeView.vue` (replace the stub from Task 2)

- [ ] **Step 1: Replace `InvokeView.vue` with full implementation**

```vue
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
  if (name && name !== selectedCapability.value) {
    selectedCapability.value = name
    invokeResult.value = null
  }
}, { immediate: true })

const capabilities = computed(() => manifest.value?.capabilities || {})
const capabilityNames = computed(() => Object.keys(capabilities.value))
const declaration = computed(() =>
  selectedCapability.value ? capabilities.value[selectedCapability.value] : null
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
    invokeResult.value = await invokeCapability(
      store.baseUrl, store.bearer, selectedCapability.value, inputs
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
</style>
```

- [ ] **Step 2: Verify build**

Run: `cd studio && npx vue-tsc --noEmit`
Expected: no type errors

Run: `cd studio && npx vite build`
Expected: build succeeds

- [ ] **Step 3: Commit**

```bash
git add studio/src/views/InvokeView.vue
git commit -m "feat(studio): implement InvokeView orchestrator with full Phase 2 layout"
```

---

## Task 7: Build, Sync, and Verify

**Files:**
- No new files — build and sync existing work

- [ ] **Step 1: Build Studio**

Run: `cd studio && npx vite build`
Expected: build succeeds, output in `studio/dist/`

- [ ] **Step 2: Sync to Python adapter**

Run: `cd studio && bash sync.sh`
Expected: `Synced studio/dist/ → packages/python/anip-studio/src/anip_studio/static/`

- [ ] **Step 3: Manual verification**

Start a showcase app (from repo root):

```bash
cd examples/showcase/travel && python app.py &
APP_PID=$!
sleep 3
```

Open `http://localhost:9100/studio` in a browser. Verify:

1. New "Invoke" nav item appears in sidebar (with zap icon)
2. Clicking it shows the capability picker
3. Selecting a capability shows: declaration bar, auth input, permissions panel, input form, invoke button
4. On the Manifest page, each capability card shows an "Invoke" link
5. Clicking the "Invoke" link navigates to `/studio/invoke/{capabilityName}`
6. Enter `demo-human-key` as bearer token — permissions auto-check triggers
7. Fill in sample inputs and invoke — success result with `invocation_id` shown
8. Try invoking with invalid inputs — structured failure with resolution callout shown

Clean up:

```bash
kill $APP_PID 2>/dev/null || true
```

- [ ] **Step 4: Commit synced assets**

```bash
git add packages/python/anip-studio/src/anip_studio/static/
git commit -m "build(studio): sync Phase 2 assets to Python adapter"
```

- [ ] **Step 5: Final combined commit if needed**

If any fixes were needed during verification:

```bash
git add studio/ packages/python/anip-studio/
git commit -m "fix(studio): address Phase 2 verification findings"
```

---

## Task 8: CI Workflow for Studio

**Files:**
- Create: `.github/workflows/ci-studio.yml`

Studio is a separate Vue 3 project — not part of the TypeScript SDK workspace. It needs its own CI workflow that type-checks and builds on changes.

- [ ] **Step 1: Create `.github/workflows/ci-studio.yml`**

```yaml
name: CI — Studio

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  changes:
    runs-on: ubuntu-latest
    outputs:
      should_test: ${{ steps.filter.outputs.src }}
    steps:
      - uses: actions/checkout@v4
      - uses: dorny/paths-filter@v3
        id: filter
        with:
          filters: |
            src:
              - "studio/**"
              - "packages/python/anip-studio/**"
              - ".github/workflows/ci-studio.yml"

  build:
    needs: changes
    if: needs.changes.outputs.should_test == 'true'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Node 22
        uses: actions/setup-node@v4
        with:
          node-version: 22

      - name: Install dependencies
        working-directory: studio
        run: npm ci

      - name: Type check
        working-directory: studio
        run: npx vue-tsc --noEmit

      - name: Build
        working-directory: studio
        run: npx vite build

      - name: Verify synced assets are up to date
        run: |
          bash studio/sync.sh
          if [ -n "$(git status --porcelain packages/python/anip-studio/src/anip_studio/static/)" ]; then
            echo "ERROR: Studio assets are stale. Run 'cd studio && npm run build && bash sync.sh' and commit the result."
            git diff --stat packages/python/anip-studio/src/anip_studio/static/
            exit 1
          fi
          echo "Studio assets are in sync."

  studio-ci:
    if: always()
    needs: [changes, build]
    runs-on: ubuntu-latest
    steps:
      - name: Passed
        if: needs.build.result == 'success' || needs.build.result == 'skipped'
        run: echo "Studio CI passed"
      - name: Failed
        if: needs.build.result == 'failure' || needs.build.result == 'cancelled'
        run: exit 1
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci-studio.yml
git commit -m "ci: add Studio type-check and build workflow"
```
