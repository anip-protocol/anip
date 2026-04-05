<script setup lang="ts">
import { ref, watch } from 'vue'
import type { IntentInterpretation } from '../project-types'

const props = defineProps<{
  title: string
  description: string
  result: IntentInterpretation | null
  loading: boolean
  error: string | null
  pendingIntent?: string
}>()

const emit = defineEmits<{
  run: [intent: string]
  reviewResult: []
  discardResult: []
}>()

const intent = ref('')

watch(
  () => props.pendingIntent,
  (value) => {
    if (value) intent.value = value
  },
  { immediate: true },
)

function handleRun() {
  emit('run', intent.value.trim())
}
</script>

<template>
  <section class="intent-panel">
    <div class="intent-head">
      <div>
        <div class="intent-kicker">Studio Assistant</div>
        <h2 class="intent-title">{{ title }}</h2>
        <p class="intent-desc">{{ description }}</p>
      </div>
      <span class="intent-badge">Powered by ANIP</span>
    </div>

    <label class="intent-label">Describe what you are trying to build</label>
    <textarea
      v-model="intent"
      class="intent-input"
      rows="5"
      placeholder="Example: We need a travel booking service that searches options, books flights, blocks bookings over budget, and escalates exceptions for approval."
    ></textarea>

    <div class="intent-actions">
      <button class="intent-btn" :disabled="loading || !intent.trim()" @click="handleRun">
        {{ loading ? 'Shaping...' : 'Help Me Shape This' }}
      </button>
    </div>

    <div v-if="error" class="intent-error">{{ error }}</div>

    <div v-if="result" class="intent-result">
      <div class="proposal-banner">
        <div>
          <div class="section-title">Suggested First Design Ready</div>
          <h3 class="result-title">{{ result.title }}</h3>
          <p class="result-summary">{{ result.summary }}</p>
        </div>
        <div class="draft-actions">
          <button class="intent-btn intent-btn-primary" :disabled="loading" @click="emit('reviewResult')">
            Review Suggested First Design
          </button>
          <button class="intent-btn" :disabled="loading" @click="emit('discardResult')">
            Discard Suggestion
          </button>
        </div>
      </div>

      <div class="proposal-note">
        Nothing has been saved yet. Review the proposed first design, then accept the parts you want to turn into real Studio artifacts.
      </div>
    </div>
  </section>
</template>

<style scoped>
.intent-panel {
  margin: 0 0 1.5rem;
  padding: 1.25rem;
  border: 1px solid rgba(15, 23, 42, 0.1);
  border-radius: var(--radius);
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.03), rgba(15, 23, 42, 0.05));
}

.intent-head {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
  margin-bottom: 1rem;
}

.intent-kicker,
.section-title {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.intent-title {
  margin: 0.2rem 0 0.35rem;
  font-size: 20px;
  color: var(--text-primary);
}

.intent-desc,
.result-summary,
.shape-recommendation p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.55;
}

.intent-badge {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 0.35rem 0.6rem;
  border-radius: 999px;
  background: rgba(59, 130, 246, 0.12);
  color: #2563eb;
}

.intent-label {
  display: block;
  margin-bottom: 0.45rem;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
}

.intent-input {
  width: 100%;
  min-height: 120px;
  box-sizing: border-box;
  padding: 0.9rem 1rem;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--bg-app);
  color: var(--text-primary);
  font: inherit;
  line-height: 1.55;
  resize: vertical;
}

.intent-actions {
  margin-top: 0.85rem;
}

.intent-btn {
  padding: 0.65rem 1rem;
  border: 1px solid rgba(59, 130, 246, 0.35);
  border-radius: 8px;
  background: rgba(59, 130, 246, 0.1);
  color: #2563eb;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.intent-btn:disabled {
  opacity: 0.6;
  cursor: default;
}

.intent-error {
  margin-top: 0.85rem;
  color: #dc2626;
  font-size: 13px;
}

.intent-result {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid rgba(15, 23, 42, 0.08);
}

.draft-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem;
}

.result-title {
  margin: 0 0 0.4rem;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.proposal-banner {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
}

.proposal-note {
  margin-top: 0.9rem;
  padding: 0.85rem 0.95rem;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.52);
  color: var(--text-secondary);
  line-height: 1.55;
}

.shape-recommendation {
  margin-top: 1rem;
  padding: 0.9rem 1rem;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.45);
}

.shape-pill {
  display: inline-block;
  margin: 0.5rem 0 0.65rem;
  padding: 0.3rem 0.6rem;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.shape-pill.single_service {
  background: rgba(16, 185, 129, 0.14);
  color: #047857;
}

.shape-pill.multi_service {
  background: rgba(234, 179, 8, 0.16);
  color: #a16207;
}

.result-section {
  margin-top: 1rem;
}

.result-section ul {
  margin: 0.45rem 0 0;
  padding-left: 1.1rem;
  color: var(--text-secondary);
}

.result-section li + li {
  margin-top: 0.35rem;
}

.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  margin-top: 0.55rem;
}

.chip {
  padding: 0.35rem 0.6rem;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.06);
  color: var(--text-primary);
  font-size: 12px;
  font-weight: 600;
}

.intent-btn-primary {
  border-color: #2563eb;
  background: #2563eb;
  color: #fff;
}
</style>
