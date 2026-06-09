<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  developerDesignContexts,
  developerDesignStatusLabel,
  summarizeDeveloperDesignBlocks,
  type DeveloperDesignContextBlock,
  type DeveloperDesignContextStatus,
} from '../developer-design-context'
import { buildProjectIssueIndex } from '../project-issues'
import { projectStore } from '../project-store'
import DeveloperDesignMapDrawer from './DeveloperDesignMapDrawer.vue'

const props = defineProps<{
  projectId: string
  block: DeveloperDesignContextBlock
  pageKey?: string
  status?: DeveloperDesignContextStatus
  issues?: string[]
}>()

const router = useRouter()
const mapDrawerOpen = ref(false)
const context = developerDesignContexts[props.block]
const issueIndex = computed(() => buildProjectIssueIndex({
  project: projectStore.activeProject,
  pmArtifacts: projectStore.artifacts.pmArtifacts,
  requirements: projectStore.artifacts.requirements,
  scenarios: projectStore.artifacts.scenarios,
  documents: projectStore.artifacts.documents,
  shapes: projectStore.artifacts.shapes,
}))
const blockSummaries = computed(() => summarizeDeveloperDesignBlocks({
  projectId: props.projectId,
  issueIndex: issueIndex.value,
  currentBlock: props.block,
  currentPageKey: props.pageKey,
  currentStatus: props.status,
  currentIssues: props.issues,
}))

function statusLabel(status: DeveloperDesignContextStatus): string {
  return developerDesignStatusLabel(status)
}

function navigateFromDrawer(path: string) {
  mapDrawerOpen.value = false
  router.push(path)
}
</script>

<template>
  <section class="context-panel">
    <div>
      <span class="context-kicker">{{ context.lane }}</span>
      <h2>{{ context.title }}</h2>
      <p>{{ context.purpose }}</p>
    </div>
    <div v-if="status || issues?.length" class="context-status-row">
      <span v-if="status" class="context-status-chip" :class="`status-${status}`">
        {{ statusLabel(status) }}
      </span>
      <span v-if="issues?.length" class="context-issue-count">
        {{ issues.length }} issue{{ issues.length === 1 ? '' : 's' }}
      </span>
      <span v-if="issues?.length" class="context-issue-preview">{{ issues[0] }}</span>
    </div>
    <div class="context-grid">
      <div>
        <strong>This page contributes</strong>
        <span>{{ context.produces }}</span>
      </div>
      <div>
        <strong>Used next by</strong>
        <span>{{ context.next }}</span>
      </div>
    </div>
    <details class="focused-map">
      <summary>
        <span>Show where this page fits</span>
        <small>{{ context.artifact }}</small>
      </summary>
      <div class="focused-flow" aria-label="Focused Developer Design map">
        <div class="focused-step">
          <span class="focused-step-label">Upstream</span>
          <strong>What feeds this</strong>
          <p>{{ context.upstream }}</p>
        </div>
        <div class="focused-arrow" aria-hidden="true">→</div>
        <div class="focused-step focused-step-current">
          <span class="focused-step-label">This page</span>
          <strong>{{ context.title }}</strong>
          <p>{{ context.current }}</p>
          <span v-if="status" class="focused-mini-status" :class="`status-${status}`">
            {{ statusLabel(status) }}
          </span>
        </div>
        <div class="focused-arrow" aria-hidden="true">→</div>
        <div class="focused-step">
          <span class="focused-step-label">Downstream</span>
          <strong>What consumes it</strong>
          <p>{{ context.downstream }}</p>
        </div>
      </div>
      <div v-if="issues?.length" class="focused-issues">
        <strong>Current blockers or warnings</strong>
        <ul>
          <li v-for="issue in issues" :key="issue">{{ issue }}</li>
        </ul>
      </div>
      <details class="technical-details">
        <summary>Technical contract fields</summary>
        <div class="technical-list">
          <code v-for="field in context.technical" :key="field">{{ field }}</code>
        </div>
      </details>
    </details>
    <div class="context-actions">
      <button class="context-link" type="button" @click="mapDrawerOpen = true">
        Open design map
      </button>
      <RouterLink class="context-link secondary-link" :to="`/design/projects/${projectId}/developer/diagrams`">
        Open diagrams page
      </RouterLink>
    </div>
    <DeveloperDesignMapDrawer
      :open="mapDrawerOpen"
      :project-id="projectId"
      :current-block="block"
      :current-page-key="pageKey"
      :current-status="status"
      :current-issues="issues"
      :block-summaries="blockSummaries"
      @close="mapDrawerOpen = false"
      @navigate="navigateFromDrawer"
    />
  </section>
</template>

<style scoped>
.context-panel {
  display: grid;
  gap: 0.9rem;
  border: 1px solid rgba(125, 211, 252, 0.2);
  border-radius: 18px;
  padding: 1rem;
  margin: 1rem 0;
  background:
    radial-gradient(circle at top left, rgba(14, 165, 233, 0.16), transparent 32%),
    rgba(15, 23, 42, 0.42);
}

.context-kicker {
  display: block;
  margin-bottom: 0.35rem;
  color: #7dd3fc;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.context-panel h2 {
  margin: 0;
  color: var(--text-primary);
}

.context-panel p {
  margin: 0.45rem 0 0;
  color: var(--text-secondary);
  line-height: 1.55;
}

.context-status-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  padding: 0.65rem 0.75rem;
  background: var(--surface-depth-inset);
}

.context-status-chip,
.context-issue-count {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 0.24rem 0.52rem;
  font-size: 11px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.context-status-chip.status-ready {
  background: rgba(20, 184, 166, 0.14);
  color: #99f6e4;
}

.context-status-chip.status-draftable {
  background: rgba(59, 130, 246, 0.14);
  color: #bfdbfe;
}

.context-status-chip.status-needs_clarification {
  background: rgba(251, 191, 36, 0.16);
  color: #fde68a;
}

.context-status-chip.status-blocked {
  background: rgba(248, 113, 113, 0.16);
  color: #fecaca;
}

.context-issue-count {
  background: rgba(251, 191, 36, 0.12);
  color: #fcd34d;
}

.context-issue-preview {
  color: #fecaca;
  font-size: 12px;
  line-height: 1.35;
}

.context-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
}

.context-grid div {
  display: grid;
  gap: 0.25rem;
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  padding: 0.75rem;
  background: var(--surface-depth-inset);
}

.context-grid strong {
  color: var(--text-primary);
}

.context-grid span {
  color: var(--text-secondary);
  line-height: 1.45;
}

.focused-map {
  border: 1px solid rgba(125, 211, 252, 0.16);
  border-radius: 16px;
  background: var(--surface-depth-inset);
  overflow: hidden;
}

.focused-map > summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.78rem 0.85rem;
  cursor: pointer;
  color: #e0f2fe;
  font-weight: 850;
}

.focused-map > summary::marker {
  color: #7dd3fc;
}

.focused-map > summary small {
  color: #93c5fd;
  font-size: 12px;
  font-weight: 800;
}

.focused-flow {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1.15fr) auto minmax(0, 1fr);
  gap: 0.7rem;
  align-items: stretch;
  padding: 0 0.85rem 0.85rem;
}

.focused-step {
  display: grid;
  gap: 0.35rem;
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  padding: 0.8rem;
  background: var(--surface-depth-card);
}

.focused-step-current {
  border-color: rgba(125, 211, 252, 0.34);
  background:
    radial-gradient(circle at top left, rgba(14, 165, 233, 0.16), transparent 40%),
    rgba(15, 23, 42, 0.66);
}

.focused-step-label,
.focused-mini-status {
  justify-self: start;
  border-radius: 999px;
  padding: 0.22rem 0.48rem;
  font-size: 10px;
  font-weight: 850;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.focused-step-label {
  background: rgba(148, 163, 184, 0.12);
  color: #cbd5e1;
}

.focused-mini-status.status-ready {
  background: rgba(20, 184, 166, 0.14);
  color: #99f6e4;
}

.focused-mini-status.status-draftable {
  background: rgba(59, 130, 246, 0.14);
  color: #bfdbfe;
}

.focused-mini-status.status-needs_clarification {
  background: rgba(251, 191, 36, 0.16);
  color: #fde68a;
}

.focused-mini-status.status-blocked {
  background: rgba(248, 113, 113, 0.16);
  color: #fecaca;
}

.focused-step strong {
  color: var(--text-primary);
}

.focused-step p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.5;
}

.focused-arrow {
  display: grid;
  align-items: center;
  color: #7dd3fc;
  font-size: 20px;
  font-weight: 900;
}

.focused-issues {
  display: grid;
  gap: 0.45rem;
  margin: 0 0.85rem 0.85rem;
  border: 1px solid rgba(248, 113, 113, 0.2);
  border-radius: 14px;
  padding: 0.75rem;
  background: rgba(127, 29, 29, 0.12);
}

.focused-issues strong {
  color: #fecaca;
}

.focused-issues ul {
  display: grid;
  gap: 0.35rem;
  margin: 0;
  padding-left: 1rem;
  color: #fee2e2;
  font-size: 12px;
  line-height: 1.4;
}

.technical-details {
  margin: 0 0.85rem 0.85rem;
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  background: var(--surface-depth-card);
}

.technical-details > summary {
  padding: 0.62rem 0.7rem;
  cursor: pointer;
  color: #cbd5e1;
  font-size: 12px;
  font-weight: 850;
}

.technical-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  padding: 0 0.7rem 0.7rem;
}

.technical-list code {
  border: 1px solid var(--surface-border-card);
  border-radius: 999px;
  padding: 0.22rem 0.48rem;
  background: var(--surface-depth-inset);
  color: #dbeafe;
  font-size: 11px;
}

.context-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.7rem;
}

.context-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(125, 211, 252, 0.24);
  border-radius: 999px;
  padding: 0.45rem 0.72rem;
  background: rgba(14, 165, 233, 0.1);
  justify-self: start;
  color: #bae6fd;
  font: inherit;
  font-weight: 800;
  text-decoration: none;
  cursor: pointer;
  transition: border-color 0.16s ease, background 0.16s ease, transform 0.16s ease;
}

.context-link:hover {
  transform: translateY(-1px);
  border-color: rgba(125, 211, 252, 0.5);
  background: rgba(14, 165, 233, 0.16);
}

.secondary-link {
  border-color: rgba(148, 163, 184, 0.2);
  background: rgba(148, 163, 184, 0.08);
  color: #dbeafe;
}

@media (max-width: 720px) {
  .context-grid {
    grid-template-columns: 1fr;
  }

  .context-actions {
    display: grid;
  }

  .focused-map > summary {
    align-items: flex-start;
    flex-direction: column;
  }

  .focused-flow {
    grid-template-columns: 1fr;
  }

  .focused-arrow {
    justify-items: center;
    transform: rotate(90deg);
  }
}
</style>
