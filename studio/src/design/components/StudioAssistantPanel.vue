<script setup lang="ts">
import { ref } from 'vue'
import type { AssistantExplanation } from '../project-types'

const props = defineProps<{
  title: string
  description: string
  buttonLabel: string
  explanation: AssistantExplanation | null
  loading: boolean
  error: string | null
}>()

const emit = defineEmits<{
  run: [question: string]
}>()

const question = ref('')

function handleRun() {
  emit('run', question.value.trim())
}
</script>

<template>
  <section class="assistant-panel">
    <div class="assistant-head">
      <div>
        <div class="assistant-kicker">Studio Assistant</div>
        <h2 class="assistant-title">{{ title }}</h2>
        <p class="assistant-desc">{{ description }}</p>
      </div>
      <span class="assistant-badge">Powered by ANIP</span>
    </div>

    <label class="assistant-label">What should be clarified?</label>
    <textarea
      v-model="question"
      class="assistant-question"
      rows="3"
      placeholder="Optional. Ask why this design was shaped this way, what the main risk is, or what should change next."
    ></textarea>

    <div class="assistant-actions">
      <button class="assistant-btn" :disabled="loading" @click="handleRun">
        {{ loading ? 'Thinking...' : buttonLabel }}
      </button>
      <span v-if="loading" class="assistant-spinner"></span>
    </div>

    <div v-if="error" class="assistant-error">{{ error }}</div>

    <div v-if="explanation" class="assistant-result">
      <h3 class="result-title">{{ explanation.title }}</h3>
      <p class="result-summary">{{ explanation.summary }}</p>

      <div v-if="explanation.focused_answer" class="result-focus">
        <div class="result-section-title">Focused Answer</div>
        <p>{{ explanation.focused_answer }}</p>
      </div>

      <div v-if="explanation.highlights?.length" class="result-section">
        <div class="result-section-title">Highlights</div>
        <ul>
          <li v-for="(item, i) in explanation.highlights" :key="`highlight-${i}`">{{ item }}</li>
        </ul>
      </div>

      <div v-if="explanation.watchouts?.length" class="result-section">
        <div class="result-section-title">Watchouts</div>
        <ul>
          <li v-for="(item, i) in explanation.watchouts" :key="`watchout-${i}`">{{ item }}</li>
        </ul>
      </div>

      <div v-if="explanation.next_steps?.length" class="result-section">
        <div class="result-section-title">Suggested Next Steps</div>
        <ul>
          <li v-for="(item, i) in explanation.next_steps" :key="`next-${i}`">{{ item }}</li>
        </ul>
      </div>
    </div>
  </section>
</template>

<style scoped>
.assistant-panel {
  margin: 1.25rem 0 1.75rem;
  padding: 1.25rem;
  border: 1px solid rgba(59, 130, 246, 0.18);
  border-radius: var(--radius);
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.03), rgba(15, 23, 42, 0.06));
}

.assistant-head {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
  margin-bottom: 1rem;
}

.assistant-kicker {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: 0.25rem;
}

.assistant-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 0.35rem;
}

.assistant-desc {
  margin: 0;
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.5;
}

.assistant-badge {
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

.assistant-label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 0.4rem;
}

.assistant-question {
  width: 100%;
  min-height: 92px;
  padding: 0.85rem 0.95rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-app);
  color: var(--text-primary);
  font: inherit;
  line-height: 1.5;
  resize: vertical;
  box-sizing: border-box;
}

.assistant-actions {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  margin-top: 0.85rem;
}

.assistant-btn {
  font-size: 13px;
  font-weight: 600;
  padding: 0.6rem 1rem;
  border-radius: 8px;
  border: 1px solid rgba(59, 130, 246, 0.35);
  background: rgba(59, 130, 246, 0.1);
  color: #2563eb;
  cursor: pointer;
}

.assistant-btn:disabled {
  opacity: 0.6;
  cursor: default;
}

.assistant-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(59, 130, 246, 0.18);
  border-top-color: #2563eb;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

.assistant-error {
  margin-top: 0.85rem;
  color: #dc2626;
  font-size: 13px;
}

.assistant-result {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid rgba(15, 23, 42, 0.08);
}

.result-title {
  margin: 0 0 0.4rem;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.result-summary {
  margin: 0 0 0.9rem;
  color: var(--text-secondary);
  line-height: 1.55;
}

.result-focus {
  margin-bottom: 1rem;
  padding: 0.85rem 0.95rem;
  background: rgba(59, 130, 246, 0.06);
  border: 1px solid rgba(59, 130, 246, 0.14);
  border-radius: var(--radius-sm);
}

.result-focus p {
  margin: 0.3rem 0 0;
  line-height: 1.55;
  color: var(--text-primary);
}

.result-section {
  margin-top: 0.9rem;
}

.result-section-title {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: 0.4rem;
}

.result-section ul {
  margin: 0;
  padding-left: 1.1rem;
  color: var(--text-secondary);
}

.result-section li + li {
  margin-top: 0.35rem;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
