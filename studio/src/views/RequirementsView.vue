<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { designStore, setActivePack, updateDraftField, setRequirementsMode, updateGuidedAnswer } from '../design/store'
import { GUIDED_SECTIONS } from '../design/guided/questions'
import { hydrateAnswersFromArtifact } from '../design/guided/mappings'
import { evaluateCompleteness } from '../design/guided/hints'
import GuidedSection from '../design/components/GuidedSection.vue'
import RequirementsSummary from '../design/components/RequirementsSummary.vue'
import CompletenessHints from '../design/components/CompletenessHints.vue'
import EditorToolbar from '../design/components/EditorToolbar.vue'
import KeyValueEditor from '../design/components/KeyValueEditor.vue'

const route = useRoute()

const pack = computed(() => {
  const id = route.params.pack as string
  if (id) setActivePack(id)
  return designStore.packs.find(p => p.meta.id === id) ?? null
})

const isEditing = computed(() => designStore.editState === 'draft')

// Source data: draft when editing, original pack data otherwise
const req = computed(() => {
  if (isEditing.value && designStore.draftRequirements) {
    return designStore.draftRequirements as Record<string, any>
  }
  return pack.value?.requirements ?? null
})

const guidedAnswers = computed(() => {
  if (isEditing.value) return designStore.guidedAnswers
  return hydrateAnswersFromArtifact(req.value ?? {})
})

const completenessHints = computed(() => {
  if (isEditing.value) return designStore.completenessHints
  return evaluateCompleteness(req.value ?? {})
})

const transportKeys = computed(() => req.value?.transports ? Object.keys(req.value.transports) : [])
const authKeys = computed(() => req.value?.auth ? Object.keys(req.value.auth) : [])
const permissionKeys = computed(() => req.value?.permissions ? Object.keys(req.value.permissions) : [])
const auditKeys = computed(() => req.value?.audit ? Object.keys(req.value.audit) : [])
const lineageKeys = computed(() => req.value?.lineage ? Object.keys(req.value.lineage) : [])
const businessConstraintKeys = computed(() => req.value?.business_constraints ? Object.keys(req.value.business_constraints) : [])

const riskCapabilities = computed(() => {
  if (!req.value?.risk_profile) return []
  return Object.entries(req.value.risk_profile)
})

// --- Draft helpers ---
function setField(path: string, value: any) {
  updateDraftField('requirements', path, value)
}

function toggleTransport(key: string) {
  setField(`transports.${key}`, !req.value?.transports?.[key])
}

function toggleAuth(key: string) {
  setField(`auth.${key}`, !req.value?.auth?.[key])
}

function togglePermission(key: string) {
  setField(`permissions.${key}`, !req.value?.permissions?.[key])
}

function toggleAudit(key: string) {
  setField(`audit.${key}`, !req.value?.audit?.[key])
}

function toggleLineage(key: string) {
  setField(`lineage.${key}`, !req.value?.lineage?.[key])
}

function setTrustMode(event: Event) {
  setField('trust.mode', (event.target as HTMLSelectElement).value)
}

function toggleTrustCheckpoints() {
  setField('trust.checkpoints', !req.value?.trust?.checkpoints)
}

function setScaleShapePreference(event: Event) {
  setField('scale.shape_preference', (event.target as HTMLSelectElement).value)
}

function toggleScaleHA() {
  setField('scale.high_availability', !req.value?.scale?.high_availability)
}
</script>

<template>
  <div class="requirements-view" v-if="pack && req">
    <h1 class="page-title">Requirements: {{ pack.meta.name }}</h1>

    <!-- Mode toggle -->
    <div class="mode-toggle">
      <button
        class="mode-btn"
        :class="{ active: designStore.requirementsMode === 'guided' }"
        @click="setRequirementsMode('guided')"
        type="button"
      >
        Guided
      </button>
      <button
        class="mode-btn"
        :class="{ active: designStore.requirementsMode === 'advanced' }"
        @click="setRequirementsMode('advanced')"
        type="button"
      >
        Advanced
      </button>
    </div>

    <EditorToolbar artifact="requirements" />

    <!-- Guided mode -->
    <template v-if="designStore.requirementsMode === 'guided'">
      <RequirementsSummary :requirements="req" />
      <CompletenessHints :hints="completenessHints" />

      <div class="mapping-toggle" v-if="isEditing">
        <label class="mapping-label">
          <input
            type="checkbox"
            :checked="designStore.showFieldMappings"
            @change="designStore.showFieldMappings = !designStore.showFieldMappings"
          />
          Show technical field mappings
        </label>
      </div>

      <GuidedSection
        v-for="section in GUIDED_SECTIONS"
        :key="section.id"
        :section="section"
        :answers="guidedAnswers"
        :showMappings="designStore.showFieldMappings"
        :readonly="!isEditing"
        @update:answer="updateGuidedAnswer"
      />
    </template>

    <!-- Advanced mode -->
    <template v-else>
    <!-- System -->
    <div class="section">
      <h2>System</h2>
      <template v-if="isEditing">
        <div class="form-grid">
          <label class="form-label">Name</label>
          <input
            class="form-input"
            type="text"
            :value="req.system.name"
            @input="setField('system.name', ($event.target as HTMLInputElement).value)"
          />
          <label class="form-label">Domain</label>
          <input
            class="form-input"
            type="text"
            :value="req.system.domain"
            @input="setField('system.domain', ($event.target as HTMLInputElement).value)"
          />
          <label class="form-label">Deployment Intent</label>
          <input
            class="form-input"
            type="text"
            :value="req.system.deployment_intent"
            @input="setField('system.deployment_intent', ($event.target as HTMLInputElement).value)"
          />
        </div>
      </template>
      <template v-else>
        <dl class="info-grid">
          <dt>Name</dt><dd>{{ req.system.name }}</dd>
          <dt>Domain</dt><dd>{{ req.system.domain }}</dd>
          <dt>Deployment Intent</dt><dd>{{ req.system.deployment_intent }}</dd>
        </dl>
      </template>
    </div>

    <!-- Transports -->
    <div class="section" v-if="transportKeys.length">
      <h2>Transports</h2>
      <template v-if="isEditing">
        <div class="toggle-grid">
          <div class="toggle-row" v-for="key in transportKeys" :key="key">
            <span class="toggle-label">{{ key }}</span>
            <button
              class="toggle-switch"
              :class="{ on: req.transports[key], off: !req.transports[key] }"
              @click="toggleTransport(key)"
              type="button"
            >
              {{ req.transports[key] ? 'ON' : 'OFF' }}
            </button>
          </div>
        </div>
      </template>
      <template v-else>
        <div class="pill-row">
          <span
            v-for="key in transportKeys"
            :key="key"
            class="check-pill"
            :class="{ enabled: req.transports[key], disabled: !req.transports[key] }"
          >
            <span class="check-mark">{{ req.transports[key] ? '&#x2713;' : '&#x2717;' }}</span>
            {{ key }}
          </span>
        </div>
      </template>
    </div>

    <!-- Trust -->
    <div class="section">
      <h2>Trust</h2>
      <template v-if="isEditing">
        <div class="form-grid">
          <label class="form-label">Mode</label>
          <select class="form-select" :value="req.trust.mode" @change="setTrustMode">
            <option value="unsigned">unsigned</option>
            <option value="signed">signed</option>
            <option value="anchored">anchored</option>
            <option value="attested">attested</option>
          </select>
          <label class="form-label">Checkpoints</label>
          <button
            class="toggle-switch"
            :class="{ on: req.trust.checkpoints, off: !req.trust.checkpoints }"
            @click="toggleTrustCheckpoints"
            type="button"
          >
            {{ req.trust.checkpoints ? 'ON' : 'OFF' }}
          </button>
        </div>
      </template>
      <template v-else>
        <dl class="info-grid">
          <dt>Trust Mode</dt><dd>{{ req.trust.mode }}</dd>
          <dt>Checkpoints</dt><dd>{{ req.trust.checkpoints ? 'Yes' : 'No' }}</dd>
        </dl>
      </template>
    </div>

    <!-- Auth -->
    <div class="section" v-if="authKeys.length">
      <h2>Auth</h2>
      <template v-if="isEditing">
        <div class="toggle-grid">
          <div class="toggle-row" v-for="key in authKeys" :key="key">
            <span class="toggle-label">{{ key }}</span>
            <button
              class="toggle-switch"
              :class="{ on: req.auth![key], off: !req.auth![key] }"
              @click="toggleAuth(key)"
              type="button"
            >
              {{ req.auth![key] ? 'ON' : 'OFF' }}
            </button>
          </div>
        </div>
      </template>
      <template v-else>
        <dl class="info-grid">
          <template v-for="key in authKeys" :key="key">
            <dt>{{ key }}</dt><dd>{{ req.auth![key] ? 'Yes' : 'No' }}</dd>
          </template>
        </dl>
      </template>
    </div>

    <!-- Permissions -->
    <div class="section" v-if="permissionKeys.length">
      <h2>Permissions</h2>
      <template v-if="isEditing">
        <div class="toggle-grid">
          <div class="toggle-row" v-for="key in permissionKeys" :key="key">
            <span class="toggle-label">{{ key }}</span>
            <button
              class="toggle-switch"
              :class="{ on: req.permissions![key], off: !req.permissions![key] }"
              @click="togglePermission(key)"
              type="button"
            >
              {{ req.permissions![key] ? 'ON' : 'OFF' }}
            </button>
          </div>
        </div>
      </template>
      <template v-else>
        <dl class="info-grid">
          <template v-for="key in permissionKeys" :key="key">
            <dt>{{ key }}</dt><dd>{{ req.permissions![key] ? 'Yes' : 'No' }}</dd>
          </template>
        </dl>
      </template>
    </div>

    <!-- Audit -->
    <div class="section" v-if="auditKeys.length">
      <h2>Audit</h2>
      <template v-if="isEditing">
        <div class="toggle-grid">
          <div class="toggle-row" v-for="key in auditKeys" :key="key">
            <span class="toggle-label">{{ key }}</span>
            <button
              class="toggle-switch"
              :class="{ on: req.audit![key], off: !req.audit![key] }"
              @click="toggleAudit(key)"
              type="button"
            >
              {{ req.audit![key] ? 'ON' : 'OFF' }}
            </button>
          </div>
        </div>
      </template>
      <template v-else>
        <dl class="info-grid">
          <template v-for="key in auditKeys" :key="'audit-' + key">
            <dt>{{ key }}</dt><dd>{{ req.audit![key] ? 'Yes' : 'No' }}</dd>
          </template>
        </dl>
      </template>
    </div>

    <!-- Lineage -->
    <div class="section" v-if="lineageKeys.length">
      <h2>Lineage</h2>
      <template v-if="isEditing">
        <div class="toggle-grid">
          <div class="toggle-row" v-for="key in lineageKeys" :key="key">
            <span class="toggle-label">{{ key }}</span>
            <button
              class="toggle-switch"
              :class="{ on: req.lineage![key], off: !req.lineage![key] }"
              @click="toggleLineage(key)"
              type="button"
            >
              {{ req.lineage![key] ? 'ON' : 'OFF' }}
            </button>
          </div>
        </div>
      </template>
      <template v-else>
        <dl class="info-grid">
          <template v-for="key in lineageKeys" :key="'lineage-' + key">
            <dt>{{ key }}</dt><dd>{{ req.lineage![key] ? 'Yes' : 'No' }}</dd>
          </template>
        </dl>
      </template>
    </div>

    <!-- Risk Profile -->
    <div class="section" v-if="riskCapabilities.length || isEditing">
      <h2>Risk Profile</h2>
      <template v-if="isEditing">
        <KeyValueEditor
          :modelValue="req.risk_profile ?? {}"
          @update:modelValue="setField('risk_profile', $event)"
        />
      </template>
      <template v-else>
        <div class="risk-cards" v-if="riskCapabilities.length">
          <div class="risk-card" v-for="[capName, capData] in riskCapabilities" :key="capName">
            <h3 class="risk-cap-name">{{ capName }}</h3>
            <dl class="risk-fields">
              <template v-for="(val, field) in (capData as Record<string, any>)" :key="field">
                <dt>{{ field }}</dt>
                <dd>{{ typeof val === 'object' ? JSON.stringify(val) : val }}</dd>
              </template>
            </dl>
          </div>
        </div>
      </template>
    </div>

    <!-- Business Constraints -->
    <div class="section" v-if="businessConstraintKeys.length || isEditing">
      <h2>Business Constraints</h2>
      <template v-if="isEditing">
        <KeyValueEditor
          :modelValue="req.business_constraints ?? {}"
          @update:modelValue="setField('business_constraints', $event)"
        />
      </template>
      <template v-else>
        <dl class="info-grid" v-if="businessConstraintKeys.length">
          <template v-for="key in businessConstraintKeys" :key="key">
            <dt>{{ key }}</dt><dd>{{ typeof req.business_constraints![key] === 'boolean' ? (req.business_constraints![key] ? 'Yes' : 'No') : req.business_constraints![key] }}</dd>
          </template>
        </dl>
      </template>
    </div>

    <!-- Scale -->
    <div class="section" v-if="req.scale || isEditing">
      <h2>Scale</h2>
      <template v-if="isEditing">
        <div class="form-grid">
          <label class="form-label">Shape Preference</label>
          <select
            class="form-select"
            :value="req.scale?.shape_preference ?? ''"
            @change="setScaleShapePreference"
          >
            <option value="">-- select --</option>
            <option value="embedded_single_process">embedded_single_process</option>
            <option value="production_single_service">production_single_service</option>
            <option value="horizontally_scaled">horizontally_scaled</option>
            <option value="control_plane_worker_split">control_plane_worker_split</option>
            <option value="multi_service_estate">multi_service_estate</option>
          </select>
          <label class="form-label">High Availability</label>
          <button
            class="toggle-switch"
            :class="{ on: req.scale?.high_availability, off: !req.scale?.high_availability }"
            @click="toggleScaleHA"
            type="button"
          >
            {{ req.scale?.high_availability ? 'ON' : 'OFF' }}
          </button>
        </div>
      </template>
      <template v-else>
        <dl class="info-grid">
          <template v-for="(val, key) in req.scale" :key="key">
            <dt>{{ key }}</dt>
            <dd>{{ typeof val === 'object' ? JSON.stringify(val) : val }}</dd>
          </template>
        </dl>
      </template>
    </div>
    </template>
  </div>
  <div v-else class="not-found">Pack not found.</div>
</template>

<style scoped>
.requirements-view {
  padding: 2rem;
  max-width: 800px;
}

.page-title {
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 1.5rem;
}

.section {
  margin-bottom: 1.5rem;
}

.section h2 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 0.75rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border);
}

.info-grid {
  display: grid;
  grid-template-columns: 200px 1fr;
  gap: 0.5rem 1rem;
  margin: 0;
}

.info-grid dt {
  font-size: 13px;
  color: var(--text-muted);
  font-weight: 500;
}

.info-grid dd {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0;
}

/* Transport / check pills */
.pill-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.check-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  font-weight: 500;
  padding: 4px 12px;
  border-radius: 14px;
  border: 1px solid var(--border);
}

.check-pill.enabled {
  background: rgba(52, 211, 153, 0.1);
  color: var(--design-handled, #34d399);
  border-color: rgba(52, 211, 153, 0.3);
}

.check-pill.disabled {
  background: transparent;
  color: var(--text-muted);
  opacity: 0.6;
}

.check-mark {
  font-size: 12px;
}

/* Risk profile cards */
.risk-cards {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.risk-card {
  flex: 1 1 240px;
  max-width: 360px;
  padding: 12px 16px;
  background: var(--bg-input, #1a1a2e);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm, 6px);
}

.risk-cap-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 0.5rem;
}

.risk-fields {
  display: grid;
  grid-template-columns: 140px 1fr;
  gap: 0.25rem 0.75rem;
  margin: 0;
}

.risk-fields dt {
  font-size: 12px;
  color: var(--text-muted);
  font-weight: 500;
}

.risk-fields dd {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 0;
  word-break: break-word;
}

.not-found {
  padding: 2rem;
  color: var(--text-muted);
}

/* ---- Edit-mode form controls ---- */
.form-grid {
  display: grid;
  grid-template-columns: 200px 1fr;
  gap: 0.75rem 1rem;
  align-items: center;
}

.form-label {
  font-size: 13px;
  color: var(--text-muted);
  font-weight: 500;
}

.form-input {
  font-size: 13px;
  padding: 6px 10px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  outline: none;
  width: 100%;
  box-sizing: border-box;
}

.form-input:focus {
  border-color: var(--border-focus);
}

.form-select {
  font-size: 13px;
  padding: 6px 10px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  outline: none;
  cursor: pointer;
}

.form-select:focus {
  border-color: var(--border-focus);
}

/* Toggle grid */
.toggle-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.toggle-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.toggle-label {
  font-size: 13px;
  color: var(--text-muted);
  font-weight: 500;
  min-width: 200px;
}

.toggle-switch {
  padding: 4px 14px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border-radius: 12px;
  border: 1px solid var(--border);
  cursor: pointer;
  transition: all var(--transition);
  min-width: 60px;
  text-align: center;
}

.toggle-switch.on {
  background: rgba(52, 211, 153, 0.12);
  color: var(--success);
  border-color: rgba(52, 211, 153, 0.3);
}

.toggle-switch.off {
  background: transparent;
  color: var(--text-muted);
}

.toggle-switch:hover {
  background: var(--bg-hover);
}

.mode-toggle {
  display: flex;
  gap: 0;
  margin-bottom: 1rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  overflow: hidden;
  width: fit-content;
}

.mode-btn {
  padding: 6px 20px;
  font-size: 13px;
  font-weight: 500;
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition);
}

.mode-btn.active {
  background: var(--accent);
  color: var(--text-primary);
}

.mode-btn:hover:not(.active) {
  background: var(--bg-hover);
}

.mapping-toggle {
  margin-bottom: 16px;
}

.mapping-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-muted);
  cursor: pointer;
}

.mapping-label input[type="checkbox"] {
  cursor: pointer;
}
</style>
