<script setup lang="ts">
import { computed } from 'vue'
import { MarkerType, Position, VueFlow, type Edge, type Node, type NodeMouseEvent, useVueFlow } from '@vue-flow/core'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'

export type DeveloperDesignMapStatus = 'ready' | 'draftable' | 'needs_clarification' | 'blocked'

export interface DeveloperDesignMapBlock {
  key: string
  title: string
  detail: string
  contribution: string
  status: DeveloperDesignMapStatus
  path: string
  issuePath?: string
  issues: string[]
  issueCount?: number
  completionLabel?: string
  subPages?: Array<{
    key: string
    label: string
    path: string
    status: DeveloperDesignMapStatus
    issueCount: number
  }>
}

export interface DeveloperDesignMapGroup {
  key: string
  title: string
  summary: string
  blocks: DeveloperDesignMapBlock[]
}

interface StudioMapNodeData {
  kind: 'block'
  title: string
  detail: string
  contribution: string
  status: DeveloperDesignMapStatus
  path: string
  issuePath?: string
  issues: string[]
  issueCount: number
  completionLabel: string
  subPages: DeveloperDesignMapBlock['subPages']
}

interface StudioMapGroupData {
  kind: 'group'
  title: string
  summary: string
  status: DeveloperDesignMapStatus
  count: number
}

const props = defineProps<{
  groups: DeveloperDesignMapGroup[]
  ready: boolean
  headline?: string
  summary?: string
  readyLabel?: string
  blockedLabel?: string
}>()

const emit = defineEmits<{
  navigate: [path: string]
}>()

const flowId = `developer-design-map-${Math.random().toString(36).slice(2)}`
const { fitView, zoomIn, zoomOut } = useVueFlow(flowId)

const groupWidth = 330
const groupGap = 64
const nodeWidth = 268
const nodeHeight = 214
const nodeGap = 36
const groupTop = 132
const groupPaddingX = 28
const groupPaddingBottom = 34

function statusLabel(status: DeveloperDesignMapStatus): string {
  switch (status) {
    case 'ready':
      return 'Ready'
    case 'draftable':
      return 'Draftable'
    case 'needs_clarification':
      return 'Needs review'
    default:
      return 'Blocked'
  }
}

function targetPath(block: DeveloperDesignMapBlock): string {
  return block.issues.length && block.issuePath ? block.issuePath : block.path
}

function issueCount(block: DeveloperDesignMapBlock): number {
  return block.issueCount ?? block.issues.length
}

function completionLabel(block: DeveloperDesignMapBlock): string {
  return block.completionLabel ?? statusLabel(block.status)
}

function previewIssue(issues: string[], detail: string): string {
  return issues.find((issue) => issue.trim() && issue.trim() !== detail.trim()) ?? ''
}

function mergedStatus(statuses: DeveloperDesignMapStatus[]): DeveloperDesignMapStatus {
  if (statuses.includes('blocked')) return 'blocked'
  if (statuses.includes('needs_clarification')) return 'needs_clarification'
  if (statuses.includes('draftable')) return 'draftable'
  return 'ready'
}

function edgeColor(status: DeveloperDesignMapStatus): string {
  switch (status) {
    case 'ready':
      return '#2dd4bf'
    case 'draftable':
      return '#60a5fa'
    case 'needs_clarification':
      return '#fbbf24'
    default:
      return '#f87171'
  }
}

const nodes = computed<Node<StudioMapNodeData | StudioMapGroupData>[]>(() => {
  const items: Node<StudioMapNodeData | StudioMapGroupData>[] = []
  props.groups.forEach((group, groupIndex) => {
    const x = groupIndex * (groupWidth + groupGap)
    const height = groupTop + Math.max(1, group.blocks.length) * nodeHeight + Math.max(0, group.blocks.length - 1) * nodeGap + groupPaddingBottom
    const groupStatus = mergedStatus(group.blocks.map((block) => block.status))
    items.push({
      id: `group-${group.key}`,
      type: 'studioGroup',
      position: { x, y: 0 },
      draggable: false,
      selectable: false,
      data: {
        kind: 'group',
        title: group.title,
        summary: group.summary,
        status: groupStatus,
        count: group.blocks.length,
      },
      style: {
        width: `${groupWidth}px`,
        height: `${height}px`,
        zIndex: 0,
      },
    })
    group.blocks.forEach((block, blockIndex) => {
      items.push({
        id: `${group.key}-${block.key}`,
        type: 'studioBlock',
        parentNode: `group-${group.key}`,
        extent: 'parent',
        position: {
          x: groupPaddingX,
          y: groupTop + blockIndex * (nodeHeight + nodeGap),
        },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
        draggable: false,
        selectable: false,
        data: {
          kind: 'block',
          title: block.title,
          detail: block.detail,
          contribution: block.contribution,
          status: block.status,
          path: targetPath(block),
          issuePath: block.issuePath,
          issues: block.issues,
          issueCount: issueCount(block),
          completionLabel: completionLabel(block),
          subPages: block.subPages,
        },
        style: {
          width: `${nodeWidth}px`,
          height: `${nodeHeight}px`,
          zIndex: 1,
        },
      })
    })
  })
  return items
})

const edges = computed<Edge[]>(() => {
  const items: Edge[] = []
  props.groups.forEach((group) => {
    group.blocks.forEach((block, index) => {
      const next = group.blocks[index + 1]
      if (!next) return
      const color = edgeColor(mergedStatus([block.status, next.status]))
      items.push({
        id: `edge-${group.key}-${block.key}-${next.key}`,
        source: `${group.key}-${block.key}`,
        target: `${group.key}-${next.key}`,
        type: 'smoothstep',
        animated: block.status !== 'ready' || next.status !== 'ready',
        markerEnd: { type: MarkerType.ArrowClosed, color },
        style: { stroke: color, strokeWidth: 2.2 },
      })
    })
  })
  props.groups.forEach((group, index) => {
    const nextGroup = props.groups[index + 1]
    const source = group.blocks[group.blocks.length - 1]
    const target = nextGroup?.blocks[0]
    if (!nextGroup || !source || !target) return
    const color = edgeColor(mergedStatus([source.status, target.status]))
    items.push({
      id: `edge-${group.key}-${nextGroup.key}`,
      source: `${group.key}-${source.key}`,
      target: `${nextGroup.key}-${target.key}`,
      type: 'smoothstep',
      animated: source.status !== 'ready' || target.status !== 'ready',
      markerEnd: { type: MarkerType.ArrowClosed, color },
      style: { stroke: color, strokeWidth: 2.6 },
    })
  })
  return items
})

const diagramHeight = computed(() => {
  const tallest = Math.max(
    1,
    ...props.groups.map((group) =>
      groupTop + Math.max(1, group.blocks.length) * nodeHeight + Math.max(0, group.blocks.length - 1) * nodeGap + groupPaddingBottom,
    ),
  )
  return Math.min(900, Math.max(420, tallest + 22))
})

function onNodeClick(event: NodeMouseEvent) {
  const data = event.node.data as StudioMapNodeData | StudioMapGroupData | undefined
  if (data?.kind === 'block' && data.path) {
    emit('navigate', data.path)
  }
}

function navigateTo(path: string) {
  emit('navigate', path)
}
</script>

<template>
  <section class="developer-map-panel">
    <div class="map-panel-header">
      <div>
        <h2>{{ headline ?? 'Developer Design Map' }}</h2>
        <p>
          {{ summary ?? 'A clickable diagram of how Developer Design turns locked Product Design into contract shape, controls, app-glue review, generation, and evidence.' }}
        </p>
      </div>
      <span class="status-chip" :class="{ ready }">
        {{ ready ? (readyLabel ?? 'Map green to generate') : (blockedLabel ?? 'Map shows blockers') }}
      </span>
    </div>

    <div class="diagram-frame" :style="{ height: `${diagramHeight}px` }">
      <VueFlow
        :id="flowId"
        class="developer-flow"
        :nodes="nodes"
        :edges="edges"
        :nodes-draggable="false"
        :nodes-connectable="false"
        :elements-selectable="false"
        :connect-on-click="false"
        :zoom-on-scroll="false"
        :zoom-on-pinch="true"
        :zoom-on-double-click="false"
        :pan-on-drag="true"
        :pan-on-scroll="false"
        :fit-view-on-init="true"
        :min-zoom="0.35"
        :max-zoom="1.4"
        @node-click="onNodeClick"
      >
        <template #node-studioGroup="{ data }">
          <div class="diagram-group" :class="`diagram-status-${data.status}`">
            <span class="group-kicker">{{ data.count }} block{{ data.count === 1 ? '' : 's' }}</span>
            <h3>{{ data.title }}</h3>
            <p>{{ data.summary }}</p>
          </div>
        </template>

        <template #node-studioBlock="{ data }">
          <article class="diagram-node" :class="`diagram-status-${data.status}`">
            <div class="node-topline">
              <span class="node-status-dot" aria-hidden="true"></span>
              <span class="node-status-label">{{ data.completionLabel }}</span>
            </div>
            <h4>{{ data.title }}</h4>
            <p class="node-detail">{{ data.detail }}</p>
            <p class="node-contribution">{{ data.contribution }}</p>
            <div class="node-footer">
              <span v-if="data.issueCount" class="issue-count">{{ data.issueCount }} issue{{ data.issueCount === 1 ? '' : 's' }}</span>
              <span v-else class="issue-count clear">0 issues</span>
              <span v-if="data.issuePath" class="node-action">Open owner</span>
            </div>
            <p v-if="previewIssue(data.issues, data.detail)" class="node-issue">
              {{ previewIssue(data.issues, data.detail) }}
            </p>
            <div v-if="data.subPages?.length" class="node-subpages">
              <button
                v-for="page in data.subPages"
                :key="page.key"
                type="button"
                class="subpage-pill"
                :class="`subpage-status-${page.status}`"
                @click.stop="navigateTo(page.path)"
              >
                <span>{{ page.label }}</span>
                <strong v-if="page.issueCount">{{ page.issueCount }}</strong>
              </button>
            </div>
          </article>
        </template>
      </VueFlow>
      <div class="diagram-controls" aria-label="Diagram zoom controls">
        <button type="button" @click="zoomOut()">−</button>
        <button type="button" @click="fitView({ padding: 0.18 })">Fit</button>
        <button type="button" @click="zoomIn()">+</button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.developer-map-panel {
  width: 100%;
}

.map-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 1rem;
}

.map-panel-header h2 {
  margin: 0;
  color: var(--text-primary);
}

.map-panel-header p {
  margin: 0.45rem 0 0;
  color: var(--text-secondary);
  line-height: 1.6;
}

.diagram-frame {
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(125, 211, 252, 0.18);
  border-radius: 24px;
  background:
    radial-gradient(circle at 12% 18%, rgba(14, 165, 233, 0.16), transparent 30%),
    radial-gradient(circle at 86% 16%, rgba(45, 212, 191, 0.12), transparent 28%),
    linear-gradient(135deg, rgba(2, 6, 23, 0.96), rgba(15, 23, 42, 0.78));
}

.diagram-controls {
  position: absolute;
  right: 1rem;
  bottom: 1rem;
  z-index: 6;
  display: inline-flex;
  overflow: hidden;
  border: 1px solid var(--surface-border-card);
  border-radius: 13px;
  background: rgba(2, 6, 23, 0.86);
  box-shadow: 0 12px 32px rgba(2, 6, 23, 0.32);
}

.diagram-controls button {
  min-width: 38px;
  border: 0;
  border-right: 1px solid rgba(148, 163, 184, 0.18);
  padding: 0.44rem 0.62rem;
  background: transparent;
  color: #dbeafe;
  font-weight: 900;
  cursor: pointer;
}

.diagram-controls button:last-child {
  border-right: 0;
}

.diagram-controls button:hover {
  background: rgba(14, 165, 233, 0.18);
}

.developer-flow {
  width: 100%;
  height: 100%;
}

.developer-flow :deep(.vue-flow__pane) {
  cursor: grab;
}

.developer-flow :deep(.vue-flow__node) {
  color: inherit;
}

.developer-flow :deep(.vue-flow__edge-path) {
  filter: drop-shadow(0 0 7px rgba(14, 165, 233, 0.25));
}

.developer-flow :deep(.vue-flow__handle) {
  width: 8px;
  height: 8px;
  border: 1px solid rgba(226, 232, 240, 0.8);
  background: #0f172a;
}

.diagram-group {
  width: 100%;
  height: 100%;
  border: 1px solid var(--surface-border-card);
  border-radius: 26px;
  padding: 1rem;
  background:
    linear-gradient(180deg, rgba(15, 23, 42, 0.86), rgba(15, 23, 42, 0.42)),
    repeating-linear-gradient(135deg, rgba(148, 163, 184, 0.07) 0, rgba(148, 163, 184, 0.07) 1px, transparent 1px, transparent 14px);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.diagram-group.diagram-status-ready {
  border-color: rgba(45, 212, 191, 0.3);
}

.diagram-group.diagram-status-draftable {
  border-color: rgba(96, 165, 250, 0.3);
}

.diagram-group.diagram-status-needs_clarification {
  border-color: rgba(251, 191, 36, 0.34);
}

.diagram-group.diagram-status-blocked {
  border-color: rgba(248, 113, 113, 0.38);
}

.group-kicker {
  display: inline-flex;
  border-radius: 999px;
  padding: 0.24rem 0.55rem;
  background: rgba(125, 211, 252, 0.12);
  color: #bae6fd;
  font-size: 10px;
  font-weight: 850;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.diagram-group h3 {
  margin: 0.55rem 0 0;
  color: var(--text-primary);
  font-size: 15px;
}

.diagram-group p {
  margin: 0.32rem 0 0;
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
  color: var(--text-secondary);
  font-size: 11px;
  line-height: 1.4;
}

.diagram-node {
  display: flex;
  flex-direction: column;
  gap: 0.34rem;
  width: 100%;
  height: 100%;
  overflow: hidden;
  border: 1px solid var(--surface-border-card);
  border-radius: 18px;
  padding: 0.78rem;
  background:
    radial-gradient(circle at top left, rgba(125, 211, 252, 0.1), transparent 40%),
    rgba(2, 6, 23, 0.82);
  color: inherit;
  cursor: pointer;
  box-shadow: 0 16px 44px rgba(2, 6, 23, 0.26);
  transition: border-color 0.16s ease, transform 0.16s ease, background 0.16s ease;
}

.diagram-node:hover {
  transform: translateY(-1px);
  border-color: rgba(125, 211, 252, 0.52);
  background:
    radial-gradient(circle at top left, rgba(125, 211, 252, 0.16), transparent 42%),
    rgba(14, 116, 144, 0.22);
}

.diagram-node.diagram-status-ready {
  border-color: rgba(45, 212, 191, 0.34);
}

.diagram-node.diagram-status-draftable {
  border-color: rgba(96, 165, 250, 0.34);
}

.diagram-node.diagram-status-needs_clarification {
  border-color: rgba(251, 191, 36, 0.42);
  background:
    radial-gradient(circle at top left, rgba(251, 191, 36, 0.14), transparent 40%),
    rgba(120, 53, 15, 0.22);
}

.diagram-node.diagram-status-blocked {
  border-color: rgba(248, 113, 113, 0.46);
  background:
    radial-gradient(circle at top left, rgba(248, 113, 113, 0.15), transparent 40%),
    rgba(127, 29, 29, 0.2);
}

.node-topline,
.node-footer {
  display: flex;
  align-items: center;
  gap: 0.42rem;
}

.node-topline {
  justify-content: space-between;
}

.node-status-dot {
  width: 9px;
  height: 9px;
  border-radius: 999px;
  background: #94a3b8;
}

.diagram-status-ready .node-status-dot {
  background: #2dd4bf;
}

.diagram-status-draftable .node-status-dot {
  background: #60a5fa;
}

.diagram-status-needs_clarification .node-status-dot {
  background: #fbbf24;
}

.diagram-status-blocked .node-status-dot {
  background: #f87171;
}

.node-status-label,
.issue-count,
.node-action {
  border-radius: 999px;
  padding: 0.18rem 0.42rem;
  background: rgba(148, 163, 184, 0.12);
  color: #cbd5e1;
  font-size: 9px;
  font-weight: 850;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  white-space: nowrap;
}

.diagram-status-ready .node-status-label,
.issue-count.clear {
  background: rgba(20, 184, 166, 0.14);
  color: #99f6e4;
}

.diagram-status-draftable .node-status-label {
  background: rgba(59, 130, 246, 0.14);
  color: #bfdbfe;
}

.diagram-status-needs_clarification .node-status-label {
  background: rgba(251, 191, 36, 0.16);
  color: #fde68a;
}

.diagram-status-blocked .node-status-label,
.issue-count:not(.clear) {
  background: rgba(248, 113, 113, 0.16);
  color: #fecaca;
}

.node-action {
  background: rgba(14, 165, 233, 0.12);
  color: #bae6fd;
}

.diagram-node h4 {
  margin: 0;
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 900;
  line-height: 1.2;
}

.node-detail,
.node-contribution,
.node-issue {
  margin: 0;
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  line-height: 1.32;
}

.node-detail {
  -webkit-line-clamp: 2;
  color: var(--text-secondary);
  font-size: 11px;
}

.node-contribution {
  -webkit-line-clamp: 2;
  border-top: 1px solid rgba(148, 163, 184, 0.12);
  padding-top: 0.36rem;
  color: #dbeafe;
  font-size: 10px;
}

.node-issue {
  -webkit-line-clamp: 1;
  color: #fecaca;
  font-size: 10px;
}

.node-footer {
  flex-wrap: wrap;
  margin-top: auto;
}

.node-subpages {
  display: flex;
  flex-wrap: wrap;
  gap: 0.28rem;
  max-height: 58px;
  overflow: auto;
  border-top: 1px solid rgba(148, 163, 184, 0.12);
  padding-top: 0.34rem;
  scrollbar-width: none;
}

.node-subpages::-webkit-scrollbar {
  display: none;
}

.subpage-pill {
  min-width: 0;
  border: 1px solid var(--surface-border-card);
  border-radius: 999px;
  padding: 0.2rem 0.42rem;
  background: rgba(15, 23, 42, 0.74);
  color: #dbeafe;
  font-size: 9px;
  font-weight: 800;
  cursor: pointer;
}

.subpage-pill span {
  display: block;
  max-width: 84px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.subpage-pill strong {
  margin-left: 0.28rem;
  color: #fecaca;
}

.subpage-pill.subpage-status-blocked {
  border-color: rgba(248, 113, 113, 0.4);
}

.subpage-pill.subpage-status-needs_clarification {
  border-color: rgba(251, 191, 36, 0.38);
}

.status-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  padding: 0.28rem 0.55rem;
  background: rgba(248, 113, 113, 0.16);
  color: #fecaca;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  white-space: nowrap;
}

.status-chip.ready {
  background: rgba(20, 184, 166, 0.14);
  color: #99f6e4;
}

@media (max-width: 760px) {
  .map-panel-header {
    flex-direction: column;
  }

  .diagram-frame {
    height: 620px !important;
  }
}
</style>
