<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { AssistantExplanation } from '../project-types'
import { assistantStepActionsForText } from '../assistant-step-actions'
import AssistantWorkingOverlay from './AssistantWorkingOverlay.vue'

const props = defineProps<{
  title: string
  description: string
  buttonLabel: string
  explanation: AssistantExplanation | null
  loading: boolean
  error: string | null
  readOnly?: boolean
  readOnlyReason?: string
}>()

const emit = defineEmits<{
  run: [question: string]
}>()

const question = ref('')
const route = useRoute()
const router = useRouter()
const projectId = computed(() => String(route.params.projectId ?? '').trim())

const nextStepRows = computed(() =>
  (props.explanation?.next_steps ?? []).map((step) => ({
    step,
    actions: assistantStepActionsForText(step, projectId.value).filter((action) => Boolean(action.path)),
  })),
)

function handleRun() {
  if (props.readOnly) return
  emit('run', question.value.trim())
}

function open(path: string) {
  router.push(path)
}
</script>

<template>
  <section class="assistant-panel">
    <AssistantWorkingOverlay
      :active="loading"
      title="Assistant is thinking"
      message="Studio is asking the configured assistant model to inspect this design context and produce reviewed next steps."
      detail="This may take a little while. The panel is blocked to avoid duplicate assistant calls."
    />

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
      :disabled="props.readOnly"
      placeholder="Optional. Ask why this design was shaped this way, what the main risk is, or what should change next."
    ></textarea>

    <div class="assistant-actions">
      <button class="assistant-btn" :disabled="loading || props.readOnly" @click="handleRun">
        {{ loading ? 'Thinking...' : buttonLabel }}
      </button>
      <span v-if="loading" class="assistant-spinner"></span>
      <span v-if="props.readOnly" class="assistant-readonly-note">
        {{ props.readOnlyReason || 'Assistant actions are disabled in read-only mode.' }}
      </span>
    </div>

    <div v-if="error" class="assistant-error">{{ error }}</div>

    <div v-if="explanation" class="assistant-result">
      <h3 class="result-title">{{ explanation.title }}</h3>
      <p class="result-summary">{{ explanation.summary }}</p>
      <div v-if="explanation.action_path && explanation.action_label" class="result-actions">
        <button class="result-action result-action-primary" type="button" @click="open(explanation.action_path)">
          {{ explanation.action_label }}
        </button>
      </div>

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
        <ul class="next-step-list">
          <li v-for="(item, i) in nextStepRows" :key="`next-${i}`">
            <p>{{ item.step }}</p>
            <div v-if="item.actions.length" class="result-actions">
              <button
                v-for="action in item.actions"
                :key="action.id"
                class="result-action"
                :class="{ 'result-action-primary': action.tone === 'primary' }"
                type="button"
                @click="action.path && open(action.path)"
              >
                {{ action.label }}
              </button>
            </div>
          </li>
        </ul>
      </div>
    </div>
  </section>
</template>

<style scoped>
.assistant-panel {
  margin: 1.25rem 0 1.75rem;
  padding: 1.25rem;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-content);
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
  background: var(--accent-glow);
  color: var(--accent-hover);
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
  border: 1px solid var(--accent);
  background: var(--accent-glow);
  color: var(--accent-hover);
  cursor: pointer;
}

.assistant-btn:disabled {
  opacity: 0.6;
  cursor: default;
}

.assistant-readonly-note {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.45;
}

.assistant-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid var(--accent-glow);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

.assistant-error {
  margin-top: 0.85rem;
  color: var(--error);
  font-size: 13px;
}

.assistant-result {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border);
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

.result-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.55rem;
}

.result-action {
  min-height: 30px;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0.35rem 0.65rem;
  background: var(--bg-app);
  color: var(--text-primary);
  font: inherit;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.result-action:hover {
  border-color: var(--accent);
  color: var(--accent-hover);
}

.result-action-primary {
  border-color: var(--accent);
  background: var(--accent-glow);
  color: var(--accent-hover);
}

.result-focus {
  margin-bottom: 1rem;
  padding: 0.85rem 0.95rem;
  background: var(--bg-app);
  border: 1px solid var(--border);
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

.result-section .next-step-list {
  display: grid;
  gap: 0.65rem;
  padding-left: 0;
  list-style: none;
}

.next-step-list li {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 0.7rem;
  background: var(--bg-app);
}

.next-step-list p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.5;
}

.result-section li + li {
  margin-top: 0.35rem;
}

.next-step-list li + li {
  margin-top: 0;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
