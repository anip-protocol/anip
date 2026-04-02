<script setup lang="ts">
import { ref, computed } from 'vue'
import StatusBadge from './StatusBadge.vue'

const props = defineProps<{
  name: string
  capability: Record<string, any>
}>()

const expanded = ref(false)

const sideEffectType = computed(() => {
  const se = props.capability.side_effect
  return se?.type || 'read'
})

const sideEffectBadge = computed<{ label: string; type: 'success' | 'warning' | 'danger' | 'info' | 'neutral' }>(() => {
  const map: Record<string, { label: string; type: 'success' | 'warning' | 'danger' | 'info' | 'neutral' }> = {
    read: { label: 'Read', type: 'success' },
    write: { label: 'Write', type: 'warning' },
    transactional: { label: 'Transactional', type: 'warning' },
    irreversible: { label: 'Irreversible', type: 'danger' },
  }
  return map[sideEffectType.value] || { label: sideEffectType.value, type: 'neutral' }
})

const inputs = computed(() => props.capability.inputs || [])
const output = computed(() => props.capability.output)
const cost = computed(() => props.capability.cost)
const requires = computed(() => props.capability.requires || [])
const responseModes = computed(() => props.capability.response_modes || ['unary'])
const scope = computed(() => props.capability.minimum_scope || [])
const observability = computed(() => props.capability.observability)
const requiresBinding = computed(() => props.capability.requires_binding || [])
const controlRequirements = computed(() => props.capability.control_requirements || [])
const refreshVia = computed(() => props.capability.refresh_via || [])
const verifyVia = computed(() => props.capability.verify_via || [])
const crossService = computed(() => props.capability.cross_service || null)
const csHandoffTo = computed(() => crossService.value?.handoff_to || [])
const csRefreshVia = computed(() => crossService.value?.refresh_via || [])
const csVerifyVia = computed(() => crossService.value?.verify_via || [])
const csFollowupVia = computed(() => crossService.value?.followup_via || [])
</script>

<template>
  <div class="cap-card" :class="{ expanded }">
    <div class="cap-header" @click="expanded = !expanded">
      <span class="expand-icon">{{ expanded ? '\u25BC' : '\u25B6' }}</span>
      <span class="cap-name">{{ name }}</span>
      <StatusBadge :label="sideEffectBadge.label" :type="sideEffectBadge.type" />
      <span v-for="s in scope" :key="s" class="scope-chip">{{ s }}</span>
      <router-link
        :to="'/invoke/' + name"
        class="invoke-link"
        @click.stop
      >
        Invoke
      </router-link>
      <span class="cap-version" v-if="capability.contract_version">v{{ capability.contract_version }}</span>
    </div>

    <div v-if="expanded" class="cap-body">
      <p v-if="capability.description" class="cap-desc">{{ capability.description }}</p>

      <!-- Side effect detail -->
      <div class="cap-section" v-if="capability.side_effect?.rollback_window">
        <div class="section-label">Rollback Window</div>
        <span class="mono-value">{{ capability.side_effect.rollback_window }}</span>
      </div>

      <!-- Cost -->
      <div class="cap-section" v-if="cost">
        <div class="section-label">Cost</div>
        <div class="cost-grid">
          <div class="cost-item">
            <span class="cost-label">Certainty</span>
            <StatusBadge
              :label="cost.certainty"
              :type="cost.certainty === 'fixed' ? 'success' : cost.certainty === 'estimated' ? 'warning' : 'info'"
            />
          </div>
          <div class="cost-item" v-if="cost.financial">
            <span class="cost-label">Financial</span>
            <span class="mono-value">
              {{ cost.financial.currency }} {{ cost.financial.range_min }}&ndash;{{ cost.financial.range_max }}
              <span v-if="cost.financial.typical" class="cost-typical">(typical: {{ cost.financial.typical }})</span>
            </span>
          </div>
          <div class="cost-item" v-if="cost.determined_by">
            <span class="cost-label">Determined by</span>
            <span class="mono-value">{{ cost.determined_by }}</span>
          </div>
          <div class="cost-item" v-if="cost.compute">
            <span class="cost-label">Compute</span>
            <span class="mono-value">
              <span v-for="(v, k) in cost.compute" :key="k" class="compute-tag">{{ k }}: {{ v }}</span>
            </span>
          </div>
        </div>
      </div>

      <!-- Prerequisites -->
      <div class="cap-section" v-if="requires.length">
        <div class="section-label">Prerequisites</div>
        <div v-for="req in requires" :key="req.capability" class="prereq-item">
          <span class="mono-value">{{ req.capability }}</span>
          <span class="prereq-reason">&mdash; {{ req.reason }}</span>
        </div>
      </div>

      <!-- Response Modes -->
      <div class="cap-section" v-if="responseModes.length > 1 || responseModes[0] !== 'unary'">
        <div class="section-label">Response Modes</div>
        <span v-for="m in responseModes" :key="m" class="scope-chip">{{ m }}</span>
      </div>

      <!-- Inputs Table -->
      <div class="cap-section" v-if="inputs.length">
        <div class="section-label">Inputs</div>
        <table class="inputs-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Required</th>
              <th>Default</th>
              <th>Description</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="input in inputs" :key="input.name">
              <td class="mono-value">{{ input.name }}</td>
              <td class="mono-value">{{ input.type }}</td>
              <td>
                <StatusBadge
                  :label="input.required !== false ? 'yes' : 'no'"
                  :type="input.required !== false ? 'info' : 'neutral'"
                />
              </td>
              <td class="mono-value">{{ input.default ?? '\u2014' }}</td>
              <td>{{ input.description || '\u2014' }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Output -->
      <div class="cap-section" v-if="output">
        <div class="section-label">Output</div>
        <div class="output-info">
          <span class="cost-label">Type:</span>
          <span class="mono-value">{{ output.type }}</span>
        </div>
        <div class="output-info" v-if="output.fields?.length">
          <span class="cost-label">Fields:</span>
          <span v-for="f in output.fields" :key="f" class="scope-chip">{{ f }}</span>
        </div>
      </div>

      <!-- Observability -->
      <div class="cap-section" v-if="observability">
        <div class="section-label">Observability</div>
        <div class="cost-grid">
          <div class="cost-item">
            <span class="cost-label">Logged</span>
            <StatusBadge :label="observability.logged ? 'yes' : 'no'" :type="observability.logged ? 'success' : 'neutral'" />
          </div>
          <div class="cost-item" v-if="observability.retention">
            <span class="cost-label">Retention</span>
            <span class="mono-value">{{ observability.retention }}</span>
          </div>
          <div class="cost-item" v-if="observability.fields_logged?.length">
            <span class="cost-label">Fields logged</span>
            <span class="mono-value">{{ observability.fields_logged.join(', ') }}</span>
          </div>
        </div>
      </div>

      <!-- Binding Requirements -->
      <div class="cap-section" v-if="requiresBinding.length">
        <div class="section-label">Binding Requirements</div>
        <div v-for="binding in requiresBinding" :key="binding.field" class="binding-item">
          <span class="scope-chip">{{ binding.type }}</span>
          <span class="cost-label">Field:</span>
          <code class="mono-value">{{ binding.field }}</code>
          <span v-if="binding.source_capability" class="cost-label">from <span class="mono-value">{{ binding.source_capability }}</span></span>
          <span v-if="binding.max_age" class="cost-label">expires after <span class="mono-value">{{ binding.max_age }}</span></span>
        </div>
      </div>

      <!-- Control Requirements -->
      <div class="cap-section" v-if="controlRequirements.length">
        <div class="section-label">Control Requirements</div>
        <div v-for="req in controlRequirements" :key="req.type" class="control-item">
          <span class="badge-reject">{{ req.type }}</span>
        </div>
      </div>

      <!-- Refresh Via -->
      <div class="cap-section" v-if="refreshVia.length">
        <div class="section-label">Refresh Via</div>
        <div class="hint-row">
          <span v-for="cap in refreshVia" :key="cap" class="hint-badge hint-badge--refresh">{{ cap }}</span>
        </div>
      </div>

      <!-- Verify Via -->
      <div class="cap-section" v-if="verifyVia.length">
        <div class="section-label">Verify Via</div>
        <div class="hint-row">
          <span v-for="cap in verifyVia" :key="cap" class="hint-badge hint-badge--verify">{{ cap }}</span>
        </div>
      </div>

      <!-- Cross-Service Hints -->
      <div class="cap-section" v-if="crossService && (csHandoffTo.length || csRefreshVia.length || csVerifyVia.length || csFollowupVia.length)">
        <div class="section-label">Cross-Service Hints</div>
        <div v-if="csHandoffTo.length" class="cs-group">
          <span class="cs-group-label">Handoff to</span>
          <div class="hint-row">
            <span v-for="ref in csHandoffTo" :key="ref.service + ':' + ref.capability" class="hint-badge hint-badge--cs-handoff">{{ ref.service }}:{{ ref.capability }}</span>
          </div>
        </div>
        <div v-if="csRefreshVia.length" class="cs-group">
          <span class="cs-group-label">Refresh via</span>
          <div class="hint-row">
            <span v-for="ref in csRefreshVia" :key="ref.service + ':' + ref.capability" class="hint-badge hint-badge--cs-refresh">{{ ref.service }}:{{ ref.capability }}</span>
          </div>
        </div>
        <div v-if="csVerifyVia.length" class="cs-group">
          <span class="cs-group-label">Verify via</span>
          <div class="hint-row">
            <span v-for="ref in csVerifyVia" :key="ref.service + ':' + ref.capability" class="hint-badge hint-badge--cs-verify">{{ ref.service }}:{{ ref.capability }}</span>
          </div>
        </div>
        <div v-if="csFollowupVia.length" class="cs-group">
          <span class="cs-group-label">Follow-up via</span>
          <div class="hint-row">
            <span v-for="ref in csFollowupVia" :key="ref.service + ':' + ref.capability" class="hint-badge hint-badge--cs-followup">{{ ref.service }}:{{ ref.capability }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.cap-card {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  transition: border-color 150ms ease;
}

.cap-card:hover {
  border-color: rgba(108, 99, 255, 0.3);
}

.cap-card.expanded {
  border-color: rgba(108, 99, 255, 0.4);
}

.cap-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: var(--bg-hover);
  cursor: pointer;
  user-select: none;
  transition: background 150ms ease;
}

.cap-header:hover {
  background: var(--bg-active);
}

.expand-icon {
  font-size: 10px;
  color: var(--text-muted);
  width: 14px;
  flex-shrink: 0;
}

.cap-name {
  font-size: 14px;
  font-weight: 600;
  font-family: 'SF Mono', 'Fira Code', monospace;
  color: var(--text-primary);
}

.cap-version {
  margin-left: 8px;
  font-size: 11px;
  color: var(--text-muted);
  font-family: 'SF Mono', 'Fira Code', monospace;
}

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

.scope-chip {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 4px;
  background: rgba(108, 99, 255, 0.1);
  color: var(--accent);
  font-size: 11px;
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.cap-body {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  border-top: 1px solid var(--border);
}

.cap-desc {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
  margin: 0;
}

.cap-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.mono-value {
  font-size: 13px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  color: var(--text-primary);
}

.cost-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 24px;
}

.cost-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.cost-label {
  font-size: 12px;
  color: var(--text-muted);
}

.cost-typical {
  color: var(--text-muted);
  font-size: 12px;
}

.compute-tag {
  display: inline-flex;
  padding: 1px 6px;
  margin-right: 6px;
  border-radius: 3px;
  background: var(--bg-hover);
  font-size: 11px;
}

.prereq-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.prereq-reason {
  font-size: 12px;
  color: var(--text-secondary);
}

.inputs-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.inputs-table th {
  text-align: left;
  padding: 6px 10px;
  border-bottom: 1px solid var(--border);
  color: var(--text-muted);
  font-weight: 600;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.inputs-table td {
  padding: 6px 10px;
  border-bottom: 1px solid rgba(42, 42, 69, 0.5);
  color: var(--text-secondary);
}

.inputs-table tr:hover td {
  background: rgba(108, 99, 255, 0.04);
}

.output-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.binding-item {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.control-item {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.badge-reject {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 4px;
  background: rgba(248, 113, 113, 0.15);
  color: var(--error);
  font-size: 11px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-weight: 600;
}

.hint-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.hint-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-weight: 500;
}

.hint-badge--refresh {
  background: rgba(52, 211, 153, 0.12);
  color: #34d399;
}

.hint-badge--verify {
  background: rgba(251, 191, 36, 0.12);
  color: #fbbf24;
}

.cs-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.cs-group-label {
  font-size: 11px;
  color: var(--text-muted);
  font-weight: 500;
  text-transform: capitalize;
}

/* handoff = blue */
.hint-badge--cs-handoff {
  background: rgba(96, 165, 250, 0.14);
  color: #60a5fa;
}

/* refresh = green */
.hint-badge--cs-refresh {
  background: rgba(52, 211, 153, 0.14);
  color: #34d399;
}

/* verify = amber */
.hint-badge--cs-verify {
  background: rgba(251, 191, 36, 0.14);
  color: #fbbf24;
}

/* followup = purple */
.hint-badge--cs-followup {
  background: rgba(167, 139, 250, 0.14);
  color: #a78bfa;
}
</style>
