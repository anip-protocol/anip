<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { designStore, setActivePack } from '../design/store'

const route = useRoute()

const pack = computed(() => {
  const id = route.params.pack as string
  if (id) setActivePack(id)
  return designStore.packs.find(p => p.meta.id === id) ?? null
})

const req = computed(() => pack.value?.requirements ?? null)

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
</script>

<template>
  <div class="requirements-view" v-if="pack && req">
    <h1 class="page-title">Requirements: {{ pack.meta.name }}</h1>

    <!-- System -->
    <div class="section">
      <h2>System</h2>
      <dl class="info-grid">
        <dt>Name</dt><dd>{{ req.system.name }}</dd>
        <dt>Domain</dt><dd>{{ req.system.domain }}</dd>
        <dt>Deployment Intent</dt><dd>{{ req.system.deployment_intent }}</dd>
      </dl>
    </div>

    <!-- Transports -->
    <div class="section" v-if="transportKeys.length">
      <h2>Transports</h2>
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
    </div>

    <!-- Trust & Auth -->
    <div class="section">
      <h2>Trust &amp; Auth</h2>
      <dl class="info-grid">
        <dt>Trust Mode</dt><dd>{{ req.trust.mode }}</dd>
        <dt>Checkpoints</dt><dd>{{ req.trust.checkpoints ? 'Yes' : 'No' }}</dd>
        <template v-for="key in authKeys" :key="key">
          <dt>{{ key }}</dt><dd>{{ req.auth![key] ? 'Yes' : 'No' }}</dd>
        </template>
      </dl>
    </div>

    <!-- Permissions -->
    <div class="section" v-if="permissionKeys.length">
      <h2>Permissions</h2>
      <dl class="info-grid">
        <template v-for="key in permissionKeys" :key="key">
          <dt>{{ key }}</dt><dd>{{ req.permissions![key] ? 'Yes' : 'No' }}</dd>
        </template>
      </dl>
    </div>

    <!-- Audit & Lineage -->
    <div class="section" v-if="auditKeys.length || lineageKeys.length">
      <h2>Audit &amp; Lineage</h2>
      <dl class="info-grid">
        <template v-for="key in auditKeys" :key="'audit-' + key">
          <dt>{{ key }}</dt><dd>{{ req.audit![key] ? 'Yes' : 'No' }}</dd>
        </template>
        <template v-for="key in lineageKeys" :key="'lineage-' + key">
          <dt>{{ key }}</dt><dd>{{ req.lineage![key] ? 'Yes' : 'No' }}</dd>
        </template>
      </dl>
    </div>

    <!-- Risk Profile -->
    <div class="section" v-if="riskCapabilities.length">
      <h2>Risk Profile</h2>
      <div class="risk-cards">
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
    </div>

    <!-- Business Constraints -->
    <div class="section" v-if="businessConstraintKeys.length">
      <h2>Business Constraints</h2>
      <dl class="info-grid">
        <template v-for="key in businessConstraintKeys" :key="key">
          <dt>{{ key }}</dt><dd>{{ req.business_constraints![key] ? 'Yes' : 'No' }}</dd>
        </template>
      </dl>
    </div>

    <!-- Scale -->
    <div class="section" v-if="req.scale">
      <h2>Scale</h2>
      <dl class="info-grid">
        <template v-for="(val, key) in req.scale" :key="key">
          <dt>{{ key }}</dt>
          <dd>{{ typeof val === 'object' ? JSON.stringify(val) : val }}</dd>
        </template>
      </dl>
    </div>
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
</style>
