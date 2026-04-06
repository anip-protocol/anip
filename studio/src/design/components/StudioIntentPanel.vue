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
          <div class="proposal-kicker">Suggested First Design Ready</div>
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
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-input);
}

.intent-head {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
  margin-bottom: 1rem;
}

.intent-kicker,
.proposal-kicker {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.intent-title {
  margin: 0.2rem 0 0.35rem;
  font-size: 20px;
  line-height: 1.25;
  color: var(--text-primary);
}

.intent-desc,
.result-summary {
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

.intent-input:focus {
  outline: none;
  border-color: var(--border-focus);
}

.intent-actions {
  margin-top: 0.85rem;
}

.intent-btn {
  height: 34px;
  padding: 0 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-app);
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background var(--transition), border-color var(--transition), color var(--transition);
}

.intent-btn:disabled {
  opacity: 0.6;
  cursor: default;
}

.intent-btn:hover:not(:disabled) {
  background: var(--bg-hover);
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
  padding: 0.95rem 1rem;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.55);
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

.intent-btn-primary {
  border-color: rgba(59, 130, 246, 0.35);
  background: rgba(59, 130, 246, 0.1);
  color: #2563eb;
}

.intent-btn-primary:hover:not(:disabled) {
  background: rgba(59, 130, 246, 0.16);
}

@media (max-width: 720px) {
  .intent-head,
  .proposal-banner {
    flex-direction: column;
  }

  .draft-actions {
    width: 100%;
  }

  .draft-actions .intent-btn {
    width: 100%;
  }
}
</style>
