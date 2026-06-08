<script setup lang="ts">
import { computed } from 'vue'
import StatusBadge from './StatusBadge.vue'
import JsonPanel from './JsonPanel.vue'
import type { GlueAnalysis } from '../design/project-types'
import { developerLabel } from '../design/developer-vocabulary'

const props = defineProps<{
  result: Record<string, any> | null
  capabilityName?: string | null
  sideEffectType?: string | null
}>()

const isSuccess = computed(() => props.result?.success === true)
const failure = computed(() => props.result?.failure || null)
const resolution = computed(() => failure.value?.resolution || null)
const recoveryClass = computed(() => resolution.value?.recovery_class || null)

const RECOVERY_CLASS_COLORS: Record<string, string> = {
  retry_now: 'rc-blue',
  wait_then_retry: 'rc-yellow',
  refresh_then_retry: 'rc-orange',
  redelegation_then_retry: 'rc-purple',
  revalidate_then_retry: 'rc-cyan',
  terminal: 'rc-red',
}

const recoveryClassColor = computed(() =>
  recoveryClass.value ? (RECOVERY_CLASS_COLORS[recoveryClass.value] || 'rc-default') : ''
)

type RuntimeGlueSignal = Pick<
  GlueAnalysis,
  'gap_category' | 'likely_owner' | 'fix_priority' | 'recommended_fix' | 'diagnostic_evidence'
> & {
  title: string
}

const runtimeGlueSignal = computed<RuntimeGlueSignal | null>(() => {
  if (isSuccess.value || !failure.value) return null

  const detail = String(failure.value.detail || '').toLowerCase()
  const action = String(resolution.value?.action || '').toLowerCase()
  const requires = String(resolution.value?.requires || '').toLowerCase()
  const failureType = String(failure.value.type || '').toLowerCase()
  const recovery = String(recoveryClass.value || '').toLowerCase()
  const sideEffect = String(props.sideEffectType || '').toLowerCase()
  const diagnosticEvidence = {
    capability_id: props.capabilityName || null,
    reason_code: failure.value.type || null,
    agent_behavior: recoveryClass.value || resolution.value?.action || null,
    backend_context: resolution.value?.requires || null,
  }

  if (
    recovery === 'redelegation_then_retry' ||
    action.includes('approval') ||
    action.includes('request_broader_scope') ||
    requires.includes('approval') ||
    requires.includes('scope')
  ) {
    return {
      title: 'Authority Posture Mismatch',
      gap_category: action.includes('approval') || requires.includes('approval')
        ? 'approval_control_missing'
        : 'agent_planning_misaligned',
      likely_owner: action.includes('approval') || requires.includes('approval')
        ? 'developer_design'
        : 'consuming_agent',
      fix_priority: sideEffect === 'write' || sideEffect === 'transactional' || sideEffect === 'irreversible'
        ? 'high'
        : 'medium',
      recommended_fix: action.includes('approval') || requires.includes('approval')
        ? 'Issue an approval-bound retry path with an explicit binding or stronger delegated token before retrying.'
        : 'Retry only after obtaining the required delegation, broader scope, or approval binding.',
      diagnostic_evidence: diagnosticEvidence,
    }
  }

  if (detail.includes('ambiguous') || detail.includes('missing') || detail.includes('clarif')) {
    return {
      title: 'Clarification Not Resolved',
      gap_category: detail.includes('clarif') ? 'clarification_loop_detected' : 'service_metadata_insufficient',
      likely_owner: detail.includes('clarif') ? 'consuming_agent' : 'service_implementation',
      fix_priority: 'high',
      recommended_fix: detail.includes('clarif')
        ? 'Stop retrying until the missing business inputs are resolved or the service returns a clearer clarification target.'
        : 'Expose the missing inputs or clarification targets more explicitly so the caller can resolve them before retrying.',
      diagnostic_evidence: diagnosticEvidence,
    }
  }

  if (recovery === 'revalidate_then_retry') {
    return {
      title: 'Revalidation Needed',
      gap_category: 'backend_semantics_mismatch',
      likely_owner: 'backend',
      fix_priority: 'medium',
      recommended_fix: 'Revalidate backend state or freshness before retrying the capability.',
      diagnostic_evidence: diagnosticEvidence,
    }
  }

  if (
    failureType.includes('restrict') ||
    action.includes('narrow') ||
    action.includes('restrict') ||
    requires.includes('narrow')
  ) {
    return {
      title: 'Restriction Mapping Missing',
      gap_category: 'restriction_mapping_missing',
      likely_owner: 'developer_design',
      fix_priority: 'medium',
      recommended_fix: 'Define the safe narrowing rule explicitly so the next restricted attempt can proceed instead of failing again.',
      diagnostic_evidence: diagnosticEvidence,
    }
  }

  return {
    title: 'Runtime Drift Detected',
    gap_category: 'developer_binding_incomplete',
    likely_owner: 'service_implementation',
    fix_priority: sideEffect === 'read' ? 'medium' : 'high',
    recommended_fix: 'Review the service contract and failure handling so the next safe step is clearer to the caller.',
    diagnostic_evidence: diagnosticEvidence,
  }
})

const auditQuery = computed(() => {
  if (!props.result || !props.capabilityName) return null
  return {
    capability: props.capabilityName,
    invocationId: props.result.invocation_id || undefined,
    taskId: props.result.task_id || undefined,
    parentInvocationId: props.result.parent_invocation_id || undefined,
  }
})
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

      <div v-if="result.task_id" class="result-meta">
        <span class="meta-label">task_id</span>
        <span class="meta-value">{{ result.task_id }}</span>
      </div>
      <div v-if="result.parent_invocation_id" class="result-meta">
        <span class="meta-label">parent_invocation_id</span>
        <span class="meta-value">{{ result.parent_invocation_id }}</span>
      </div>

      <div v-if="result.cost_actual" class="result-meta">
        <span class="meta-label">cost_actual</span>
        <span class="meta-value">
          {{ result.cost_actual.currency }} {{ result.cost_actual.amount }}
        </span>
      </div>

      <!-- Budget Context -->
      <div v-if="result.budget_context" class="budget-callout">
        <div class="budget-title">Budget Context</div>
        <div class="budget-fields">
          <div class="result-meta">
            <span class="meta-label">Budget</span>
            <span class="meta-value">{{ result.budget_context.budget_currency }} {{ result.budget_context.budget_max }}</span>
          </div>
          <div class="result-meta">
            <span class="meta-label">Check Amount</span>
            <span class="meta-value">{{ result.budget_context.cost_check_amount }}</span>
          </div>
          <div class="result-meta">
            <span class="meta-label">Certainty</span>
            <span class="meta-value">{{ result.budget_context.cost_certainty }}</span>
          </div>
          <div v-if="result.budget_context.cost_actual != null" class="result-meta">
            <span class="meta-label">Actual Cost</span>
            <span class="meta-value">{{ result.budget_context.cost_actual }}</span>
          </div>
          <div class="result-meta">
            <span class="meta-label">Within Budget</span>
            <span :class="result.budget_context.within_budget ? 'status-ok' : 'status-error'">
              {{ result.budget_context.within_budget ? 'Yes' : 'No' }}
            </span>
          </div>
        </div>
      </div>

      <JsonPanel :data="result.result" title="Result Data" :collapsed="false" />
    </div>

    <!-- Failure -->
    <div v-else class="result-body">
      <div class="result-status-line">
        <StatusBadge label="Failed" type="danger" />
        <StatusBadge v-if="failure?.type" :label="failure.type" type="warning" />
        <span
          v-if="recoveryClass"
          class="recovery-class-badge"
          :class="recoveryClassColor"
        >{{ recoveryClass }}</span>
        <span class="invocation-id">{{ result.invocation_id }}</span>
      </div>

      <div v-if="result.client_reference_id" class="result-meta">
        <span class="meta-label">client_reference_id</span>
        <span class="meta-value">{{ result.client_reference_id }}</span>
      </div>

      <div v-if="result.task_id" class="result-meta">
        <span class="meta-label">task_id</span>
        <span class="meta-value">{{ result.task_id }}</span>
      </div>
      <div v-if="result.parent_invocation_id" class="result-meta">
        <span class="meta-label">parent_invocation_id</span>
        <span class="meta-value">{{ result.parent_invocation_id }}</span>
      </div>

      <!-- Failure detail -->
      <p v-if="failure?.detail" class="failure-detail">{{ failure.detail }}</p>

      <div v-if="runtimeGlueSignal" class="runtime-glue-callout">
        <div class="runtime-glue-title">Runtime Drift Signals</div>
        <div class="runtime-glue-body">
          <div class="runtime-glue-summary">{{ runtimeGlueSignal.title }}</div>
          <div class="runtime-glue-badges">
            <span class="runtime-glue-pill">{{ developerLabel(runtimeGlueSignal.gap_category) }}</span>
            <span class="runtime-glue-pill">{{ developerLabel(runtimeGlueSignal.likely_owner) }}</span>
            <span class="runtime-glue-pill">{{ runtimeGlueSignal.fix_priority }} priority</span>
          </div>
          <div class="runtime-glue-meta">
            <span>capability: {{ capabilityName || 'unknown' }}</span>
            <span v-if="runtimeGlueSignal.diagnostic_evidence.reason_code">
              reason: {{ runtimeGlueSignal.diagnostic_evidence.reason_code }}
            </span>
            <span v-if="runtimeGlueSignal.diagnostic_evidence.agent_behavior">
              behavior: {{ runtimeGlueSignal.diagnostic_evidence.agent_behavior }}
            </span>
            <span v-if="runtimeGlueSignal.diagnostic_evidence.backend_context">
              backend: {{ runtimeGlueSignal.diagnostic_evidence.backend_context }}
            </span>
          </div>
          <p class="runtime-glue-fix">{{ runtimeGlueSignal.recommended_fix }}</p>
          <router-link
            v-if="auditQuery"
            class="runtime-glue-link"
            :to="{ name: 'audit', query: auditQuery }"
          >
            Open filtered audit trail
          </router-link>
        </div>
      </div>

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

      <!-- Budget Context (failure path) -->
      <div v-if="result.budget_context" class="budget-callout">
        <div class="budget-title">Budget Context</div>
        <div class="budget-fields">
          <div class="result-meta">
            <span class="meta-label">Budget</span>
            <span class="meta-value">{{ result.budget_context.budget_currency }} {{ result.budget_context.budget_max }}</span>
          </div>
          <div class="result-meta">
            <span class="meta-label">Check Amount</span>
            <span class="meta-value">{{ result.budget_context.cost_check_amount }}</span>
          </div>
          <div class="result-meta">
            <span class="meta-label">Certainty</span>
            <span class="meta-value">{{ result.budget_context.cost_certainty }}</span>
          </div>
          <div v-if="result.budget_context.cost_actual != null" class="result-meta">
            <span class="meta-label">Actual Cost</span>
            <span class="meta-value">{{ result.budget_context.cost_actual }}</span>
          </div>
          <div class="result-meta">
            <span class="meta-label">Within Budget</span>
            <span :class="result.budget_context.within_budget ? 'status-ok' : 'status-error'">
              {{ result.budget_context.within_budget ? 'Yes' : 'No' }}
            </span>
          </div>
        </div>
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

.runtime-glue-callout {
  padding: 12px 14px;
  border: 1px solid rgba(249, 115, 22, 0.26);
  background: rgba(249, 115, 22, 0.08);
  border-radius: 8px;
}

.runtime-glue-title {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #9a3412;
  margin-bottom: 6px;
}

.runtime-glue-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.runtime-glue-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.runtime-glue-pill {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(249, 115, 22, 0.14);
  color: #9a3412;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.runtime-glue-summary {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.runtime-glue-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 11px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  color: var(--text-muted);
}

.runtime-glue-fix {
  margin: 0;
  font-size: 13px;
  line-height: 1.5;
  color: var(--text-secondary);
}

.runtime-glue-link {
  width: fit-content;
  font-size: 12px;
  font-weight: 600;
  color: var(--accent);
  text-decoration: none;
}

.runtime-glue-link:hover {
  text-decoration: underline;
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

.budget-callout {
  background: rgba(108, 99, 255, 0.08);
  border-left: 3px solid var(--accent);
  padding: 10px 14px;
  border-radius: 0 6px 6px 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.budget-title {
  font-size: 10px;
  text-transform: uppercase;
  color: var(--accent);
  font-weight: 600;
  letter-spacing: 0.5px;
}

.budget-fields {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.status-ok {
  font-size: 12px;
  font-weight: 600;
  color: var(--success);
}

.status-error {
  font-size: 12px;
  font-weight: 600;
  color: var(--error);
}

/* Recovery class badge */
.recovery-class-badge {
  font-size: 10px;
  font-weight: 600;
  font-family: 'SF Mono', 'Fira Code', monospace;
  padding: 2px 7px;
  border-radius: 10px;
  letter-spacing: 0.3px;
  text-transform: none;
  white-space: nowrap;
}

.rc-blue {
  background: rgba(59, 130, 246, 0.15);
  color: #3b82f6;
  border: 1px solid rgba(59, 130, 246, 0.3);
}

.rc-yellow {
  background: rgba(234, 179, 8, 0.15);
  color: #ca8a04;
  border: 1px solid rgba(234, 179, 8, 0.3);
}

.rc-orange {
  background: rgba(249, 115, 22, 0.15);
  color: #ea580c;
  border: 1px solid rgba(249, 115, 22, 0.3);
}

.rc-purple {
  background: rgba(168, 85, 247, 0.15);
  color: #a855f7;
  border: 1px solid rgba(168, 85, 247, 0.3);
}

.rc-cyan {
  background: rgba(6, 182, 212, 0.15);
  color: #0891b2;
  border: 1px solid rgba(6, 182, 212, 0.3);
}

.rc-red {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.rc-default {
  background: rgba(100, 116, 139, 0.15);
  color: #64748b;
  border: 1px solid rgba(100, 116, 139, 0.3);
}
</style>
