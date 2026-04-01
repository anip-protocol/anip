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
