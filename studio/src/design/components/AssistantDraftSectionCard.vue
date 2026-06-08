<script setup lang="ts">
import type { DeveloperDesignDraftSection } from '../developer-design-draft-bundle'
import type {
  AssistantClarificationAnswerContext,
  ProductDesignDraftSection,
} from '../product-design-draft-bundle'
import type { AssistantClarificationQuestion } from '../project-types'
import { developerLabel } from '../developer-vocabulary'

type AssistantDraftSection = ProductDesignDraftSection | DeveloperDesignDraftSection

const props = defineProps<{
  section: AssistantDraftSection
  itemCount: number
  selectedCount: number
  patchPreviewSource?: Record<string, unknown> | null
  saveBusy: boolean
  savingCurrent: boolean
  regenerateBusy: boolean
  regeneratingCurrent: boolean
  readOnly: boolean
  canRegenerate: boolean
  clarificationPlaceholder: string
}>()

const emit = defineEmits<{
  selectAll: []
  clearSelection: []
  toggleItem: [itemId: string]
  updateClarificationAnswer: [payload: { questionId: string; value: string }]
  persistAnswers: []
  regenerate: []
  save: []
}>()

function clarificationQuestions(section: AssistantDraftSection): AssistantClarificationQuestion[] {
  const proposal = section.envelope?.proposal
  return proposal?.proposal_kind === 'clarification_questions' ? proposal.questions : []
}

function isClarificationSection(section: AssistantDraftSection): boolean {
  return clarificationQuestions(section).length > 0
}

function clarificationAnswer(section: AssistantDraftSection, questionId: string): string {
  return section.clarificationAnswers?.[questionId] ?? ''
}

function usedClarificationAnswers(section: AssistantDraftSection): AssistantClarificationAnswerContext[] {
  return section.usedClarificationAnswers ?? []
}

function proposalItems(section: AssistantDraftSection) {
  const proposal = section.envelope?.proposal
  if (!proposal) return []
  if (proposal.proposal_kind === 'candidate_blocks') {
    return proposal.items.map((item) => ({
      id: item.client_id,
      title: item.title,
      body: item.body,
      rationale: item.rationale,
      confidence: item.confidence,
    }))
  }
  if (proposal.proposal_kind === 'clarification_questions') {
    return proposal.questions.map((question) => ({
      id: question.question_id,
      title: question.prompt,
      body: question.why_it_matters,
      rationale: `Target artifact: ${question.target_artifact}`,
      confidence: 'clarification',
    }))
  }
  return proposal.patches.map((patch, index) => ({
    id: String(index),
    title: `${patch.op.toUpperCase()} ${patch.path}`,
    body: typeof patch.value === 'object' ? JSON.stringify(patch.value, null, 2) : String(patch.value ?? ''),
    rationale: patch.rationale,
    confidence: 'patch',
  }))
}

function pointerParts(path: string): string[] {
  if (!path.startsWith('/')) return []
  return path.slice(1).split('/').map((part) => part.replace(/~1/g, '/').replace(/~0/g, '~'))
}

function readJsonPointer(source: Record<string, unknown> | null | undefined, path: string): unknown {
  if (!source) return undefined
  let cursor: unknown = source
  for (const part of pointerParts(path)) {
    if (Array.isArray(cursor)) {
      const index = Number(part)
      cursor = Number.isInteger(index) ? cursor[index] : undefined
    } else if (cursor && typeof cursor === 'object') {
      cursor = (cursor as Record<string, unknown>)[part]
    } else {
      return undefined
    }
  }
  return cursor
}

function formatPreviewValue(value: unknown): string {
  if (value === undefined) return 'Not set'
  if (value === null) return 'null'
  if (typeof value === 'string') return value || 'Empty string'
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  return JSON.stringify(value, null, 2)
}

function patchDiffItems(section: AssistantDraftSection) {
  const proposal = section.envelope?.proposal
  if (proposal?.proposal_kind !== 'patch_candidates') return []
  return proposal.patches.map((patch, index) => ({
    id: String(index),
    path: patch.path,
    op: patch.op,
    rationale: patch.rationale,
    currentValue: formatPreviewValue(readJsonPointer(props.patchPreviewSource, patch.path)),
    proposedValue: patch.op === 'remove' ? 'Removed' : formatPreviewValue(patch.value),
    selected: section.selectedIds.includes(String(index)),
  }))
}
</script>

<template>
  <article class="draft-section-card" :class="`status-${section.status}`">
    <details class="draft-section-details" :open="section.status !== 'saved'">
      <summary class="draft-section-header">
        <div>
          <h3>{{ section.title }}</h3>
          <p v-if="section.envelope">{{ section.envelope.summary }}</p>
          <p v-if="section.error" class="error-copy">{{ section.error }}</p>
        </div>
        <span class="draft-section-header-side">
          <span v-if="section.envelope" class="selection-count">{{ selectedCount }} / {{ itemCount }} selected</span>
          <span class="status-chip" :class="{ ready: section.status === 'saved' || section.status === 'proposed' }">
            {{ developerLabel(section.status) }}
          </span>
        </span>
      </summary>

      <div class="draft-section-content">
        <div v-if="section.envelope?.watchouts.length" class="section-note">
          <strong>Watchouts</strong>
          <ul>
            <li v-for="watchout in section.envelope.watchouts" :key="watchout">{{ watchout }}</li>
          </ul>
        </div>

        <div v-if="section.envelope" class="selection-toolbar">
          <span>{{ selectedCount }} / {{ itemCount }} selected</span>
          <button class="mini-btn" type="button" @click="emit('selectAll')">Select all</button>
          <button class="mini-btn" type="button" @click="emit('clearSelection')">Clear</button>
        </div>

        <div v-if="section.envelope" class="proposal-items">
          <label v-for="item in proposalItems(section)" :key="item.id" class="proposal-item">
            <input
              type="checkbox"
              :checked="section.selectedIds.includes(item.id)"
              @change="emit('toggleItem', item.id)"
            />
            <span class="proposal-copy">
              <span class="proposal-title-row">
                <strong>{{ item.title }}</strong>
                <em>{{ item.confidence }}</em>
              </span>
              <span class="proposal-body">{{ item.body }}</span>
              <small>{{ item.rationale }}</small>
            </span>
          </label>
        </div>

        <div v-if="patchDiffItems(section).length" class="patch-preview-panel">
          <strong>Patch preview</strong>
          <div
            v-for="patch in patchDiffItems(section)"
            :key="patch.id"
            class="patch-preview-item"
            :class="{ muted: !patch.selected }"
          >
            <div class="patch-preview-header">
              <span>{{ patch.op.toUpperCase() }} {{ patch.path }}</span>
              <em>{{ patch.selected ? 'selected' : 'not selected' }}</em>
            </div>
            <div class="patch-preview-grid">
              <div>
                <small>Current</small>
                <pre>{{ patch.currentValue }}</pre>
              </div>
              <div>
                <small>Proposed</small>
                <pre>{{ patch.proposedValue }}</pre>
              </div>
            </div>
            <small>{{ patch.rationale }}</small>
          </div>
        </div>

        <div v-if="isClarificationSection(section)" class="clarification-answer-panel">
          <strong>Answer selected questions, then regenerate this section</strong>
          <label
            v-for="question in clarificationQuestions(section)"
            :key="question.question_id"
            class="clarification-answer"
            :class="{ muted: !section.selectedIds.includes(question.question_id) }"
          >
            <span>{{ question.prompt }}</span>
            <textarea
              class="form-input"
              rows="3"
              :disabled="readOnly || !section.selectedIds.includes(question.question_id)"
              :value="clarificationAnswer(section, question.question_id)"
              :placeholder="clarificationPlaceholder"
              @input="emit('updateClarificationAnswer', { questionId: question.question_id, value: ($event.target as HTMLTextAreaElement).value })"
              @blur="emit('persistAnswers')"
            />
          </label>
        </div>

        <div v-if="usedClarificationAnswers(section).length" class="clarification-context-panel">
          <strong>Clarification context used for latest regeneration</strong>
          <div
            v-for="answer in usedClarificationAnswers(section)"
            :key="`${answer.questionId}-${answer.answeredAt}`"
            class="clarification-context-item"
          >
            <span>{{ answer.prompt }}</span>
            <p>{{ answer.answer }}</p>
            <small>Target artifact: {{ answer.targetArtifact }}</small>
          </div>
        </div>

        <div v-if="section.envelope || section.status === 'failed'" class="section-actions">
          <button
            v-if="isClarificationSection(section) || section.status === 'failed'"
            class="btn btn-secondary"
            :disabled="regenerateBusy || readOnly || !canRegenerate"
            @click="emit('regenerate')"
          >
            {{ regeneratingCurrent ? 'Regenerating...' : section.status === 'failed' ? 'Retry Section' : 'Regenerate Section' }}
          </button>
          <button
            v-else
            class="btn btn-secondary"
            :disabled="saveBusy || section.selectedIds.length === 0 || section.status === 'saved' || readOnly"
            @click="emit('save')"
          >
            {{ savingCurrent ? 'Saving...' : section.status === 'saved' ? 'Saved' : 'Save Accepted Section' }}
          </button>
        </div>
      </div>
    </details>
  </article>
</template>

<style scoped>
.draft-section-card {
  padding: 0;
  border-radius: 20px;
  border: 1px solid var(--surface-border-card);
  background:
    linear-gradient(180deg, rgba(15, 23, 42, 0.66), rgba(15, 23, 42, 0.46));
  overflow: hidden;
}

.draft-section-card.status-saved {
  border-color: rgba(34, 197, 94, 0.28);
}

.draft-section-card.status-failed {
  border-color: rgba(248, 113, 113, 0.28);
}

.draft-section-details {
  display: block;
}

.draft-section-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
  padding: 1.05rem 1.1rem;
  cursor: pointer;
  list-style: none;
}

.draft-section-header::-webkit-details-marker {
  display: none;
}

.draft-section-header::before {
  content: '▸';
  flex: 0 0 auto;
  margin-top: 0.1rem;
  color: #93c5fd;
  font-size: 14px;
  transition: transform 0.18s ease;
}

.draft-section-details[open] > .draft-section-header::before {
  transform: rotate(90deg);
}

.draft-section-header-side {
  display: flex;
  flex: 0 0 auto;
  gap: 0.5rem;
  align-items: center;
}

.selection-count {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 800;
  white-space: nowrap;
}

.draft-section-content {
  display: grid;
  gap: 0.95rem;
  padding: 0 1.1rem 1.1rem;
}

.draft-section-header h3 {
  margin: 0 0 0.3rem;
  color: var(--text-primary);
  font-size: 18px;
  line-height: 1.25;
  font-weight: 800;
}

.draft-section-header p,
.proposal-body,
.proposal-item small,
.error-copy {
  color: var(--text-secondary);
}

.section-note {
  display: grid;
  gap: 0.45rem;
  padding: 0.9rem;
  border-radius: 14px;
  background: var(--surface-depth-card);
}

.section-note ul {
  margin: 0;
  padding-left: 1.1rem;
  color: var(--text-secondary);
}

.selection-toolbar,
.section-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem;
  align-items: center;
  justify-content: flex-end;
}

.selection-toolbar {
  justify-content: flex-start;
  color: var(--text-secondary);
  font-size: 13px;
}

.mini-btn {
  border: 1px solid var(--surface-border-card);
  border-radius: 999px;
  background: var(--surface-depth-card);
  color: #dbeafe;
  padding: 0.35rem 0.7rem;
  cursor: pointer;
  font: inherit;
  font-size: 12px;
  font-weight: 700;
}

.proposal-items {
  display: grid;
  gap: 0.75rem;
}

.proposal-item {
  display: flex;
  gap: 0.7rem;
  align-items: flex-start;
  padding: 0.9rem;
  border-radius: 14px;
  border: 1px solid var(--surface-border-card);
  background: var(--surface-depth-card);
}

.proposal-copy {
  display: grid;
  gap: 0.35rem;
  min-width: 0;
  width: 100%;
}

.proposal-title-row {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  align-items: flex-start;
}

.proposal-body {
  white-space: pre-wrap;
}

.proposal-title-row strong {
  color: var(--text-primary);
  font-weight: 800;
}

.proposal-title-row em {
  color: #93c5fd;
  font-size: 12px;
  font-style: normal;
}

.patch-preview-panel {
  display: grid;
  gap: 0.75rem;
  padding: 0.95rem;
  border-radius: 14px;
  border: 1px solid rgba(34, 197, 94, 0.18);
  background: rgba(34, 197, 94, 0.07);
}

.patch-preview-item {
  display: grid;
  gap: 0.55rem;
  padding: 0.75rem;
  border-radius: 12px;
  background: var(--surface-depth-card);
}

.patch-preview-item.muted {
  opacity: 0.58;
}

.patch-preview-header {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  color: var(--text-primary);
  font-size: 13px;
}

.patch-preview-header em,
.patch-preview-item small {
  color: var(--text-secondary);
  font-size: 12px;
  font-style: normal;
}

.patch-preview-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.65rem;
}

.patch-preview-grid pre {
  margin: 0.25rem 0 0;
  max-height: 160px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  border: 1px solid var(--surface-border-card);
  border-radius: 10px;
  padding: 0.65rem;
  background: var(--surface-depth-inset);
  color: var(--text-primary);
}

.clarification-answer-panel {
  display: grid;
  gap: 0.75rem;
  padding: 0.95rem;
  border-radius: 14px;
  border: 1px solid rgba(251, 191, 36, 0.2);
  background: rgba(251, 191, 36, 0.08);
}

.clarification-answer {
  display: grid;
  gap: 0.4rem;
  color: var(--text-secondary);
  font-size: 13px;
}

.clarification-answer.muted {
  opacity: 0.56;
}

.clarification-answer textarea {
  resize: vertical;
}

.clarification-context-panel {
  display: grid;
  gap: 0.7rem;
  padding: 0.95rem;
  border-radius: 14px;
  border: 1px solid rgba(96, 165, 250, 0.18);
  background: rgba(96, 165, 250, 0.08);
}

.clarification-context-item {
  display: grid;
  gap: 0.25rem;
  color: var(--text-secondary);
  font-size: 13px;
}

.clarification-context-item p {
  margin: 0;
  color: var(--text-primary);
}

.clarification-context-item small {
  color: var(--text-secondary);
}

.status-chip {
  border: 1px solid var(--surface-border-card);
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.12);
  color: var(--text-secondary);
  padding: 0.32rem 0.68rem;
  font-size: 12px;
  font-weight: 700;
  text-transform: capitalize;
}

.status-chip.ready {
  border-color: rgba(34, 197, 94, 0.28);
  background: rgba(34, 197, 94, 0.12);
  color: #bbf7d0;
}

.form-input {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--surface-border-card);
  border-radius: 12px;
  padding: 0.78rem 0.9rem;
  background: var(--surface-depth-card);
  color: var(--text-primary);
  font: inherit;
  line-height: 1.45;
}

.btn {
  min-height: 38px;
  border-radius: 12px;
  font-weight: 700;
}

.btn-secondary {
  background: var(--surface-depth-card);
  color: #dbeafe;
  border-color: rgba(96, 165, 250, 0.24);
}

.btn-secondary:hover:not(:disabled) {
  background: rgba(30, 64, 175, 0.22);
  border-color: rgba(147, 197, 253, 0.42);
}
</style>
