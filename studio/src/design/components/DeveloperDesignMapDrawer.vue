<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  developerDesignBlockOrder,
  developerDesignContexts,
  developerDesignPath,
  developerDesignStatusLabel,
  type DeveloperDesignContextBlockSummary,
  type DeveloperDesignContextBlock,
  type DeveloperDesignContextStatus,
} from '../developer-design-context'

type DrawerTab = 'business' | 'technical'

const props = defineProps<{
  open: boolean
  projectId: string
  currentBlock: DeveloperDesignContextBlock
  currentPageKey?: string
  currentStatus?: DeveloperDesignContextStatus
  currentIssues?: string[]
  blockSummaries: Record<DeveloperDesignContextBlock, DeveloperDesignContextBlockSummary>
}>()

const emit = defineEmits<{
  close: []
  navigate: [path: string]
}>()

const activeTab = ref<DrawerTab>('business')

const currentContext = computed(() => developerDesignContexts[props.currentBlock])
const currentSummary = computed(() => props.blockSummaries[props.currentBlock])
const currentIssueCount = computed(() => currentSummary.value?.issueCount ?? props.currentIssues?.length ?? 0)
const displayStatus = computed<DeveloperDesignContextStatus>(() => currentSummary.value?.status ?? props.currentStatus ?? 'draftable')

watch(() => props.open, (isOpen) => {
  if (isOpen) activeTab.value = 'business'
})

function blockStatus(block: DeveloperDesignContextBlock): DeveloperDesignContextStatus {
  return props.blockSummaries[block]?.status ?? (block === props.currentBlock ? displayStatus.value : 'ready')
}

function selectPath(block: DeveloperDesignContextBlock): string {
  return developerDesignPath(props.projectId, block)
}

function navigate(block: DeveloperDesignContextBlock) {
  const summary = props.blockSummaries[block]
  emit('navigate', summary?.issueCount ? summary.issuePath : selectPath(block))
}

function blockIssueCount(block: DeveloperDesignContextBlock): number {
  return props.blockSummaries[block]?.issueCount ?? 0
}

function blockIssues(block: DeveloperDesignContextBlock): string[] {
  return props.blockSummaries[block]?.issues ?? []
}

function sourceRows(block: DeveloperDesignContextBlock) {
  return props.blockSummaries[block]?.sources ?? []
}

function navigatePath(path: string) {
  emit('navigate', path)
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="drawer-shell" role="dialog" aria-modal="true" aria-labelledby="developer-map-drawer-title">
      <button class="drawer-backdrop" type="button" aria-label="Close design map" @click="emit('close')" />
      <aside class="drawer-panel">
        <header class="drawer-header">
          <div>
            <span class="drawer-kicker">Developer Design Map</span>
            <h2 id="developer-map-drawer-title">Where this page fits</h2>
            <p>
              Inspect the business and technical map without leaving the current page.
              The highlighted block is the page you opened this from.
            </p>
          </div>
          <button class="close-button" type="button" @click="emit('close')">Close</button>
        </header>

        <section class="current-strip" :class="`status-${displayStatus}`">
          <div>
            <span>{{ currentContext.lane }}</span>
            <strong>{{ currentContext.title }}</strong>
            <p>{{ currentContext.current }}</p>
          </div>
          <div class="current-meta">
            <span class="status-chip" :class="`status-${displayStatus}`">
              {{ developerDesignStatusLabel(displayStatus) }}
            </span>
            <span v-if="currentIssueCount" class="issue-chip">{{ currentIssueCount }} issue{{ currentIssueCount === 1 ? '' : 's' }}</span>
          </div>
        </section>

        <nav class="drawer-tabs" aria-label="Design map tabs">
          <button type="button" :class="{ active: activeTab === 'business' }" @click="activeTab = 'business'">
            Business Map
          </button>
          <button type="button" :class="{ active: activeTab === 'technical' }" @click="activeTab = 'technical'">
            Technical Flow
          </button>
        </nav>

        <section v-if="activeTab === 'business'" class="drawer-content">
          <div class="map-grid">
            <article
              v-for="block in developerDesignBlockOrder"
              :key="block"
              class="map-card"
              :class="[`status-${blockStatus(block)}`, { active: block === currentBlock }]"
            >
              <button type="button" class="map-card-main" @click="navigate(block)">
                <span class="card-kicker">{{ developerDesignContexts[block].lane }}</span>
                <strong>{{ developerDesignContexts[block].title }}</strong>
                <p>{{ developerDesignContexts[block].purpose }}</p>
                <span class="card-contribution">
                  <span>Business meaning</span>
                  {{ developerDesignContexts[block].produces }}
                </span>
                <span class="card-footer">
                  <span class="status-chip" :class="`status-${blockStatus(block)}`">
                    {{ developerDesignStatusLabel(blockStatus(block)) }}
                  </span>
                  <span v-if="blockIssueCount(block)" class="issue-chip">
                    {{ blockIssueCount(block) }} issue{{ blockIssueCount(block) === 1 ? '' : 's' }}
                  </span>
                  <span v-if="block === currentBlock" class="active-chip">Current page</span>
                </span>
                <span v-if="blockIssues(block).length" class="card-issue-preview">
                  {{ blockIssues(block)[0] }}
                </span>
              </button>
              <div v-if="block === currentBlock || sourceRows(block).some((source) => source.issueCount)" class="subpage-list">
                <button
                  v-for="source in sourceRows(block)"
                  :key="source.key"
                  type="button"
                  class="subpage-row"
                  :class="[`status-${source.status}`, { active: source.current }]"
                  @click.stop="navigatePath(source.path)"
                >
                  <span>{{ source.label }}</span>
                  <span class="subpage-meta">
                    <span v-if="source.current" class="mini-current">Current</span>
                    <span v-if="source.issueCount" class="mini-issue">
                      {{ source.issueCount }} issue{{ source.issueCount === 1 ? '' : 's' }}
                    </span>
                    <span v-else class="mini-ready">{{ developerDesignStatusLabel(source.status) }}</span>
                  </span>
                </button>
              </div>
            </article>
          </div>
        </section>

        <section v-else class="drawer-content">
          <div class="technical-track">
            <template v-for="(block, index) in developerDesignBlockOrder" :key="block">
              <article
                class="technical-node"
                :class="[`status-${blockStatus(block)}`, { active: block === currentBlock }]"
              >
                <button type="button" class="technical-node-main" @click="navigate(block)">
                  <span>{{ developerDesignContexts[block].artifact }}</span>
                  <strong>{{ developerDesignContexts[block].title }}</strong>
                  <p>{{ developerDesignContexts[block].downstream }}</p>
                  <span class="status-chip" :class="`status-${blockStatus(block)}`">
                    {{ developerDesignStatusLabel(blockStatus(block)) }}
                  </span>
                  <span v-if="blockIssues(block).length" class="node-issue-preview">{{ blockIssues(block)[0] }}</span>
                  <span class="technical-fields">
                    <code v-for="field in developerDesignContexts[block].technical.slice(0, 3)" :key="field">{{ field }}</code>
                  </span>
                </button>
                <div v-if="block === currentBlock || sourceRows(block).some((source) => source.issueCount)" class="technical-subpages">
                  <button
                    v-for="source in sourceRows(block)"
                    :key="source.key"
                    type="button"
                    class="technical-subpage"
                    :class="[`status-${source.status}`, { active: source.current }]"
                    @click.stop="navigatePath(source.path)"
                  >
                    {{ source.label }}
                    <small v-if="source.issueCount">{{ source.issueCount }}</small>
                  </button>
                </div>
              </article>
              <span v-if="index < developerDesignBlockOrder.length - 1" class="technical-arrow" aria-hidden="true">→</span>
            </template>
          </div>
        </section>

        <section v-if="currentSummary?.issues.length" class="drawer-issues">
          <strong>Current page issues</strong>
          <ul>
            <li v-for="issue in currentSummary.issues" :key="issue">{{ issue }}</li>
          </ul>
        </section>

        <footer class="drawer-footer">
          <button class="secondary-button" type="button" @click="emit('navigate', `/design/projects/${projectId}/developer/diagrams`)">
            Open diagrams page
          </button>
          <button class="secondary-button" type="button" @click="emit('navigate', `/design/projects/${projectId}/developer/diagrams`)">
            Open artifact flow
          </button>
        </footer>
      </aside>
    </div>
  </Teleport>
</template>

<style scoped>
.drawer-shell {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: grid;
  justify-items: end;
}

.drawer-backdrop {
  position: absolute;
  inset: 0;
  border: 0;
  background: rgba(2, 6, 23, 0.68);
  cursor: pointer;
}

.drawer-panel {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-rows: auto auto auto minmax(0, 1fr) auto auto;
  gap: 1rem;
  width: min(1040px, calc(100vw - 2rem));
  height: calc(100vh - 2rem);
  margin: 1rem;
  border: 1px solid rgba(125, 211, 252, 0.2);
  border-radius: 24px;
  padding: 1.15rem;
  overflow: auto;
  background:
    radial-gradient(circle at top left, rgba(14, 165, 233, 0.18), transparent 32%),
    linear-gradient(135deg, rgba(15, 23, 42, 0.98), rgba(2, 6, 23, 0.96));
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.45);
}

.drawer-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
}

.drawer-kicker,
.card-kicker {
  color: #7dd3fc;
  font-size: 10px;
  font-weight: 850;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.drawer-header h2 {
  margin: 0.25rem 0 0;
  color: var(--text-primary);
}

.drawer-header p {
  margin: 0.45rem 0 0;
  max-width: 680px;
  color: var(--text-secondary);
  line-height: 1.55;
}

.close-button,
.secondary-button,
.drawer-tabs button {
  border: 1px solid var(--surface-border-card);
  border-radius: 999px;
  padding: 0.52rem 0.82rem;
  background: var(--surface-depth-card);
  color: #dbeafe;
  font-weight: 850;
  cursor: pointer;
}

.close-button:hover,
.secondary-button:hover,
.drawer-tabs button:hover {
  border-color: rgba(125, 211, 252, 0.45);
  background: rgba(14, 165, 233, 0.14);
}

.current-strip {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  border: 1px solid rgba(125, 211, 252, 0.2);
  border-radius: 18px;
  padding: 0.9rem;
  background: var(--surface-depth-inset);
}

.current-strip.status-blocked {
  border-color: rgba(248, 113, 113, 0.36);
  background: rgba(127, 29, 29, 0.14);
}

.current-strip.status-needs_clarification {
  border-color: rgba(251, 191, 36, 0.34);
  background: rgba(120, 53, 15, 0.14);
}

.current-strip span {
  color: #93c5fd;
  font-size: 11px;
  font-weight: 850;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.current-strip strong {
  display: block;
  margin-top: 0.25rem;
  color: var(--text-primary);
}

.current-strip p {
  margin: 0.35rem 0 0;
  color: var(--text-secondary);
  line-height: 1.45;
}

.current-meta,
.card-footer {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  align-items: flex-start;
  justify-content: flex-end;
}

.drawer-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
}

.drawer-tabs button.active {
  border-color: rgba(125, 211, 252, 0.56);
  background: rgba(14, 165, 233, 0.18);
  color: #e0f2fe;
}

.drawer-content {
  min-height: 0;
}

.map-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.8rem;
}

.map-card,
.technical-node {
  display: grid;
  gap: 0.45rem;
  width: 100%;
  border: 1px solid var(--surface-border-card);
  border-radius: 18px;
  padding: 0.9rem;
  background: var(--surface-depth-card);
  color: inherit;
  text-align: left;
}

.map-card:hover,
.technical-node:hover {
  border-color: rgba(125, 211, 252, 0.45);
  background: rgba(14, 116, 144, 0.14);
}

.map-card.active,
.technical-node.active {
  border-color: rgba(125, 211, 252, 0.62);
  background:
    radial-gradient(circle at top left, rgba(14, 165, 233, 0.2), transparent 42%),
    rgba(15, 23, 42, 0.76);
}

.map-card-main,
.technical-node-main {
  display: grid;
  gap: 0.45rem;
  width: 100%;
  border: 0;
  padding: 0;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.map-card.status-blocked.active,
.technical-node.status-blocked.active {
  border-color: rgba(248, 113, 113, 0.52);
}

.map-card.status-needs_clarification.active,
.technical-node.status-needs_clarification.active {
  border-color: rgba(251, 191, 36, 0.52);
}

.map-card strong,
.technical-node strong {
  color: var(--text-primary);
}

.map-card p,
.technical-node p,
.card-issue-preview,
.node-issue-preview {
  margin: 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.45;
}

.card-issue-preview,
.node-issue-preview {
  border-left: 2px solid rgba(248, 113, 113, 0.52);
  padding-left: 0.55rem;
  color: #fecaca;
}

.card-contribution {
  display: grid;
  gap: 0.25rem;
  border-top: 1px solid rgba(148, 163, 184, 0.12);
  padding-top: 0.55rem;
  color: #cbd5e1;
  font-size: 12px;
  line-height: 1.4;
}

.card-contribution span {
  color: #93c5fd;
  font-size: 10px;
  font-weight: 850;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.subpage-list,
.technical-subpages {
  display: grid;
  gap: 0.35rem;
  border-top: 1px solid rgba(148, 163, 184, 0.12);
  padding-top: 0.55rem;
}

.subpage-row,
.technical-subpage {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  border: 1px solid var(--surface-border-card);
  border-radius: 12px;
  padding: 0.42rem 0.5rem;
  background: var(--surface-depth-inset);
  color: #dbeafe;
  font-size: 11px;
  font-weight: 750;
  text-align: left;
  cursor: pointer;
}

.subpage-row:hover,
.technical-subpage:hover {
  border-color: rgba(125, 211, 252, 0.42);
  background: rgba(14, 165, 233, 0.12);
}

.subpage-row.active,
.technical-subpage.active {
  border-color: rgba(125, 211, 252, 0.5);
  background: rgba(14, 165, 233, 0.14);
}

.subpage-row.status-blocked,
.technical-subpage.status-blocked {
  border-color: rgba(248, 113, 113, 0.34);
}

.subpage-row.status-needs_clarification,
.technical-subpage.status-needs_clarification {
  border-color: rgba(251, 191, 36, 0.32);
}

.subpage-meta {
  display: inline-flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.3rem;
}

.mini-current,
.mini-issue,
.mini-ready,
.technical-subpage small {
  border-radius: 999px;
  padding: 0.16rem 0.36rem;
  font-size: 9px;
  font-weight: 850;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  white-space: nowrap;
}

.mini-current {
  background: rgba(125, 211, 252, 0.14);
  color: #bae6fd;
}

.mini-issue,
.technical-subpage small {
  background: rgba(248, 113, 113, 0.15);
  color: #fecaca;
}

.mini-ready {
  background: rgba(20, 184, 166, 0.12);
  color: #99f6e4;
}

.technical-track {
  display: grid;
  grid-template-columns: repeat(7, minmax(160px, 1fr));
  gap: 0.55rem;
  align-items: stretch;
  overflow-x: auto;
  padding-bottom: 0.35rem;
}

.technical-node {
  min-height: 220px;
}

.technical-node-main > span:first-child {
  color: #93c5fd;
  font-size: 10px;
  font-weight: 850;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.technical-arrow {
  display: none;
}

.technical-fields {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin-top: auto;
}

.technical-fields code {
  border: 1px solid var(--surface-border-card);
  border-radius: 999px;
  padding: 0.2rem 0.42rem;
  background: var(--surface-depth-inset);
  color: #dbeafe;
  font-size: 10px;
}

.status-chip,
.issue-chip,
.active-chip {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 0.24rem 0.5rem;
  font-size: 10px;
  font-weight: 850;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.status-chip.status-ready {
  background: rgba(20, 184, 166, 0.14);
  color: #99f6e4;
}

.status-chip.status-draftable {
  background: rgba(59, 130, 246, 0.14);
  color: #bfdbfe;
}

.status-chip.status-needs_clarification {
  background: rgba(251, 191, 36, 0.16);
  color: #fde68a;
}

.status-chip.status-blocked {
  background: rgba(248, 113, 113, 0.16);
  color: #fecaca;
}

.issue-chip {
  background: rgba(248, 113, 113, 0.14);
  color: #fecaca;
}

.active-chip {
  background: rgba(125, 211, 252, 0.14);
  color: #bae6fd;
}

.drawer-issues {
  display: grid;
  gap: 0.45rem;
  border: 1px solid rgba(248, 113, 113, 0.24);
  border-radius: 16px;
  padding: 0.8rem;
  background: rgba(127, 29, 29, 0.13);
}

.drawer-issues strong {
  color: #fecaca;
}

.drawer-issues ul {
  display: grid;
  gap: 0.35rem;
  margin: 0;
  padding-left: 1rem;
  color: #fee2e2;
  font-size: 12px;
  line-height: 1.4;
}

.drawer-footer {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.55rem;
}

@media (max-width: 900px) {
  .drawer-panel {
    width: calc(100vw - 1rem);
    height: calc(100vh - 1rem);
    margin: 0.5rem;
  }

  .drawer-header,
  .current-strip {
    display: grid;
  }

  .current-meta {
    justify-content: flex-start;
  }

  .map-grid {
    grid-template-columns: 1fr;
  }

  .technical-track {
    grid-template-columns: 1fr;
    overflow-x: visible;
  }
}
</style>
