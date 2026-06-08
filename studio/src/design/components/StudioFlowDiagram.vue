<script setup lang="ts">
import { computed } from 'vue'
import { MarkerType, Position, VueFlow, type Edge, type Node, type NodeMouseEvent, useVueFlow } from '@vue-flow/core'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'

export type StudioFlowDiagramStatus = 'ready' | 'draftable' | 'needs_clarification' | 'blocked'

export interface StudioFlowDiagramNode {
  key: string
  title: string
  kicker: string
  detail: string
  status: StudioFlowDiagramStatus
  path: string
  meta?: string
  issues?: string[]
}

interface FlowNodeData {
  title: string
  kicker: string
  detail: string
  status: StudioFlowDiagramStatus
  path: string
  meta?: string
  issues: string[]
}

const props = defineProps<{
  nodes: StudioFlowDiagramNode[]
  headline: string
  summary: string
}>()

const emit = defineEmits<{
  navigate: [path: string]
}>()

const flowId = `studio-flow-diagram-${Math.random().toString(36).slice(2)}`
const { fitView, zoomIn, zoomOut } = useVueFlow(flowId)

function statusLabel(status: StudioFlowDiagramStatus): string {
  switch (status) {
    case 'ready':
      return 'Ready'
    case 'draftable':
      return 'Ready to create'
    case 'needs_clarification':
      return 'Needs review'
    default:
      return 'Blocked'
  }
}

function edgeColor(status: StudioFlowDiagramStatus): string {
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

function mergedStatus(statuses: StudioFlowDiagramStatus[]): StudioFlowDiagramStatus {
  if (statuses.includes('blocked')) return 'blocked'
  if (statuses.includes('needs_clarification')) return 'needs_clarification'
  if (statuses.includes('draftable')) return 'draftable'
  return 'ready'
}

const flowNodes = computed<Node<FlowNodeData>[]>(() =>
  props.nodes.map((node, index) => ({
    id: node.key,
    type: 'artifact',
    position: {
      x: index * 250,
      y: index % 2 === 0 ? 28 : 160,
    },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    draggable: false,
    selectable: false,
    data: {
      title: node.title,
      kicker: node.kicker,
      detail: node.detail,
      status: node.status,
      path: node.path,
      meta: node.meta,
      issues: node.issues ?? [],
    },
    style: {
      width: '216px',
      height: '160px',
    },
  })),
)

const flowEdges = computed<Edge[]>(() =>
  props.nodes.slice(0, -1).map((node, index) => {
    const next = props.nodes[index + 1]
    const status = mergedStatus([node.status, next.status])
    const color = edgeColor(status)
    return {
      id: `edge-${node.key}-${next.key}`,
      source: node.key,
      target: next.key,
      type: 'smoothstep',
      animated: status !== 'ready',
      markerEnd: { type: MarkerType.ArrowClosed, color },
      style: { stroke: color, strokeWidth: 2.6 },
    }
  }),
)

function onNodeClick(event: NodeMouseEvent) {
  const data = event.node.data as FlowNodeData | undefined
  if (data?.path) {
    emit('navigate', data.path)
  }
}
</script>

<template>
  <section class="studio-flow-diagram">
    <div class="flow-header">
      <div>
        <h2>{{ headline }}</h2>
        <p>{{ summary }}</p>
      </div>
    </div>
    <div class="flow-frame">
      <VueFlow
        :id="flowId"
        class="artifact-flow"
        :nodes="flowNodes"
        :edges="flowEdges"
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
        :min-zoom="0.45"
        :max-zoom="1.5"
        @node-click="onNodeClick"
      >
        <template #node-artifact="{ data }">
          <article class="artifact-node" :class="`artifact-status-${data.status}`">
            <div class="artifact-kicker-row">
              <span class="artifact-dot" aria-hidden="true"></span>
              <span class="artifact-kicker">{{ data.kicker }}</span>
            </div>
            <h3>{{ data.title }}</h3>
            <p>{{ data.detail }}</p>
            <code v-if="data.meta">{{ data.meta }}</code>
            <div class="artifact-footer">
              <span class="status-chip" :class="`status-${data.status}`">{{ statusLabel(data.status) }}</span>
              <span v-if="data.issues.length" class="issue-count">{{ data.issues.length }} issue{{ data.issues.length === 1 ? '' : 's' }}</span>
            </div>
            <span v-if="data.issues.length" class="issue-preview">{{ data.issues[0] }}</span>
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
.studio-flow-diagram {
  width: 100%;
}

.flow-header {
  margin-bottom: 1rem;
}

.flow-header h2 {
  margin: 0;
  color: var(--text-primary);
}

.flow-header p {
  margin: 0.45rem 0 0;
  color: var(--text-secondary);
  line-height: 1.6;
}

.flow-frame {
  position: relative;
  height: 380px;
  overflow: hidden;
  border: 1px solid rgba(125, 211, 252, 0.18);
  border-radius: 24px;
  background:
    radial-gradient(circle at 12% 20%, rgba(59, 130, 246, 0.16), transparent 34%),
    radial-gradient(circle at 78% 70%, rgba(20, 184, 166, 0.12), transparent 30%),
    linear-gradient(135deg, rgba(2, 6, 23, 0.96), rgba(15, 23, 42, 0.76));
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

.artifact-flow {
  width: 100%;
  height: 100%;
}

.artifact-flow :deep(.vue-flow__pane) {
  cursor: grab;
}

.artifact-flow :deep(.vue-flow__edge-path) {
  filter: drop-shadow(0 0 7px rgba(14, 165, 233, 0.24));
}

.artifact-flow :deep(.vue-flow__handle) {
  width: 8px;
  height: 8px;
  border: 1px solid rgba(226, 232, 240, 0.78);
  background: #0f172a;
}

.artifact-node {
  display: grid;
  gap: 0.38rem;
  width: 100%;
  height: 100%;
  overflow: hidden;
  border: 1px solid var(--surface-border-card);
  border-radius: 18px;
  padding: 0.82rem;
  background:
    radial-gradient(circle at top left, rgba(125, 211, 252, 0.11), transparent 40%),
    rgba(2, 6, 23, 0.82);
  color: inherit;
  cursor: pointer;
  box-shadow: 0 16px 44px rgba(2, 6, 23, 0.26);
  transition: border-color 0.16s ease, transform 0.16s ease, background 0.16s ease;
}

.artifact-node:hover {
  transform: translateY(-1px);
  border-color: rgba(125, 211, 252, 0.52);
  background:
    radial-gradient(circle at top left, rgba(125, 211, 252, 0.17), transparent 42%),
    rgba(14, 116, 144, 0.22);
}

.artifact-status-ready {
  border-color: rgba(45, 212, 191, 0.34);
}

.artifact-status-draftable {
  border-color: rgba(96, 165, 250, 0.34);
}

.artifact-status-needs_clarification {
  border-color: rgba(251, 191, 36, 0.42);
  background:
    radial-gradient(circle at top left, rgba(251, 191, 36, 0.14), transparent 40%),
    rgba(120, 53, 15, 0.22);
}

.artifact-status-blocked {
  border-color: rgba(248, 113, 113, 0.46);
  background:
    radial-gradient(circle at top left, rgba(248, 113, 113, 0.15), transparent 40%),
    rgba(127, 29, 29, 0.2);
}

.artifact-kicker-row,
.artifact-footer {
  display: flex;
  align-items: center;
  gap: 0.42rem;
}

.artifact-kicker-row {
  justify-content: space-between;
}

.artifact-dot {
  width: 9px;
  height: 9px;
  border-radius: 999px;
  background: #94a3b8;
}

.artifact-status-ready .artifact-dot {
  background: #2dd4bf;
}

.artifact-status-draftable .artifact-dot {
  background: #60a5fa;
}

.artifact-status-needs_clarification .artifact-dot {
  background: #fbbf24;
}

.artifact-status-blocked .artifact-dot {
  background: #f87171;
}

.artifact-kicker,
.status-chip,
.issue-count {
  border-radius: 999px;
  padding: 0.2rem 0.44rem;
  background: rgba(148, 163, 184, 0.12);
  color: #cbd5e1;
  font-size: 9px;
  font-weight: 850;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  white-space: nowrap;
}

.artifact-kicker {
  color: #bae6fd;
  background: rgba(14, 165, 233, 0.12);
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

.status-chip.status-blocked,
.issue-count {
  background: rgba(248, 113, 113, 0.16);
  color: #fecaca;
}

.artifact-node h3 {
  margin: 0;
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 900;
  line-height: 1.2;
}

.artifact-node p,
.issue-preview {
  margin: 0;
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  line-height: 1.34;
}

.artifact-node p {
  -webkit-line-clamp: 3;
  color: var(--text-secondary);
  font-size: 11px;
}

.artifact-node code {
  display: block;
  max-width: 100%;
  overflow: hidden;
  color: #dbeafe;
  font-size: 10px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.artifact-footer {
  flex-wrap: wrap;
  margin-top: auto;
}

.issue-preview {
  -webkit-line-clamp: 1;
  color: #fecaca;
  font-size: 10px;
}

@media (max-width: 760px) {
  .flow-frame {
    height: 520px;
  }
}
</style>
