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
