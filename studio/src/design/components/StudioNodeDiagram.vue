<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { MarkerType, Position, VueFlow, type Edge, type Node, type NodeMouseEvent, useVueFlow } from '@vue-flow/core'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'

export type StudioDiagramStatus = 'ready' | 'draftable' | 'needs_clarification' | 'blocked'
export interface StudioDiagramChoice {
  label: string
  path: string
}

export interface StudioDiagramGroupItem {
  label: string
  path?: string
  choices?: StudioDiagramChoice[]
}

export interface StudioDiagramGroup {
  title: string
  count?: number
  path?: string
  items: Array<string | StudioDiagramGroupItem>
  mediumItemLimit?: number
  expandedItemLimit?: number
  moreLabel?: string
  tone?: 'capability' | 'behavior' | 'authority' | 'glue' | 'neutral'
}

export interface StudioDiagramNode {
  id: string
  title: string
  subtitle?: string
  detail: string
  status: StudioDiagramStatus
  path?: string
  x: number
  y: number
  mediumY?: number
  expandedY?: number
  width?: number
  height?: number
  meta?: string[]
  detailGroups?: StudioDiagramGroup[]
  expandedMeta?: string[]
  compactHeight?: number
  mediumHeight?: number
  expandedHeight?: number
  compactDetailLines?: number
  mediumDetailLines?: number
  expandedDetailLines?: number
  compactMetaLimit?: number
  mediumMetaLimit?: number
  expandedMetaLimit?: number
  sourcePosition?: Position
  targetPosition?: Position
}

export interface StudioDiagramEdge {
  id: string
  source: string
  target: string
  label?: string
  status?: StudioDiagramStatus
  animated?: boolean
  type?: 'default' | 'straight' | 'step' | 'smoothstep'
  dashed?: boolean
}

interface DiagramNodeData extends StudioDiagramNode {}

const props = defineProps<{
  headline: string
  summary: string
  nodes: StudioDiagramNode[]
  edges: StudioDiagramEdge[]
  height?: number
  fitVersion?: number
}>()

const emit = defineEmits<{
  navigate: [path: string]
}>()

const flowId = `studio-node-diagram-${Math.random().toString(36).slice(2)}`
const { fitView, viewport, zoomIn, zoomOut } = useVueFlow(flowId)
const activeChoiceKey = ref<string | null>(null)
const fitOptions = { padding: 0.18, maxZoom: 0.9 }

const zoomLevel = computed(() => viewport.value.zoom)
const detailLevel = computed<'compact' | 'medium' | 'expanded'>(() => {
  if (zoomLevel.value < 0.98) return 'compact'
  if (zoomLevel.value < 1.28) return 'medium'
  return 'expanded'
})

function statusLabel(status: StudioDiagramStatus): string {
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

function statusColor(status: StudioDiagramStatus): string {
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

const flowNodes = computed<Node<DiagramNodeData>[]>(() =>
  props.nodes.map((node) => ({
    id: node.id,
    type: 'studioDiagramNode',
    position: { x: node.x, y: nodeY(node) },
    sourcePosition: node.sourcePosition ?? Position.Bottom,
    targetPosition: node.targetPosition ?? Position.Top,
    draggable: false,
    selectable: false,
    data: node,
    style: {
      width: `${node.width ?? 240}px`,
      height: `${nodeHeight(node)}px`,
      '--compact-detail-lines': String(node.compactDetailLines ?? 2),
      '--medium-detail-lines': String(node.mediumDetailLines ?? 4),
      '--expanded-detail-lines': String(node.expandedDetailLines ?? 6),
    } as Record<string, string>,
  })),
)

function nodeY(node: StudioDiagramNode): number {
  if (detailLevel.value === 'expanded') return node.expandedY ?? node.mediumY ?? node.y
  if (detailLevel.value === 'medium') return node.mediumY ?? node.y
  return node.y
}

function nodeHeight(node: StudioDiagramNode): number {
  if (detailLevel.value === 'compact') return node.compactHeight ?? node.height ?? 154
  if (detailLevel.value === 'medium') return node.mediumHeight ?? node.height ?? 154
  return node.expandedHeight ?? node.height ?? 154
}

function metaLimit(node: StudioDiagramNode): number {
  if (detailLevel.value === 'compact') return node.compactMetaLimit ?? 1
  if (detailLevel.value === 'medium') return node.mediumMetaLimit ?? 3
  return node.expandedMetaLimit ?? node.meta?.length ?? 3
}

const flowEdges = computed<Edge[]>(() =>
  props.edges.map((edge) => {
    const color = statusColor(edge.status ?? 'ready')
    return {
      id: edge.id,
      source: edge.source,
      target: edge.target,
      label: edge.label,
      type: edge.type ?? 'smoothstep',
      animated: edge.animated ?? (edge.status === 'blocked' || edge.status === 'needs_clarification'),
      markerEnd: { type: MarkerType.ArrowClosed, color },
      style: { stroke: color, strokeWidth: 2.5, strokeDasharray: edge.dashed ? '7 7' : undefined },
      labelStyle: { fill: '#cbd5e1', fontWeight: 800, fontSize: 10 },
      labelBgStyle: { fill: 'rgba(15, 23, 42, 0.9)' },
      labelBgPadding: [8, 4],
      labelBgBorderRadius: 8,
    }
  }),
)

function onNodeClick(event: NodeMouseEvent) {
  const data = event.node.data as DiagramNodeData | undefined
  if (data?.path) {
    emit('navigate', data.path)
  }
}

function groupItemLabel(item: string | StudioDiagramGroupItem): string {
  return typeof item === 'string' ? item : item.label
}

function groupItemPath(item: string | StudioDiagramGroupItem): string | undefined {
  return typeof item === 'string' ? undefined : item.path
}

function groupItemChoices(item: string | StudioDiagramGroupItem): StudioDiagramChoice[] {
  return typeof item === 'string' ? [] : item.choices ?? []
}

function groupItemKey(nodeId: string, groupTitle: string, item: string | StudioDiagramGroupItem, index: string | number): string {
  return `${nodeId}:${groupTitle}:${groupItemLabel(item)}:${index}`
}

function visibleGroupItems(group: StudioDiagramGroup): Array<string | StudioDiagramGroupItem> {
  if (detailLevel.value === 'compact') return []
  const limit = detailLevel.value === 'medium' ? group.mediumItemLimit ?? 4 : group.expandedItemLimit ?? 8
  if (group.items.length <= limit) return group.items
  const visible = group.items.slice(0, Math.max(0, limit - 1))
  const hiddenCount = group.items.length - visible.length
  return [...visible, `+${hiddenCount} ${group.moreLabel ?? 'more'}`]
}

function onGroupClick(path: string | undefined) {
  if (path) emit('navigate', path)
}

function onItemClick(item: string | StudioDiagramGroupItem, key: string) {
  const choices = groupItemChoices(item)
  if (choices.length > 1) {
    activeChoiceKey.value = activeChoiceKey.value === key ? null : key
    return
  }
  const path = groupItemPath(item) ?? choices[0]?.path
  if (path) emit('navigate', path)
}

async function fitDiagram() {
  await nextTick()
  window.setTimeout(() => {
    void fitView(fitOptions)
  }, 80)
  window.setTimeout(() => {
    void fitView(fitOptions)
  }, 240)
}

onMounted(fitDiagram)
watch(
  () => [
    props.headline,
    props.fitVersion ?? 0,
    props.nodes.map((node) => `${node.id}:${node.x}:${node.y}:${node.mediumY ?? ''}:${node.expandedY ?? ''}:${node.width ?? ''}:${node.height ?? ''}:${node.compactHeight ?? ''}:${node.mediumHeight ?? ''}:${node.expandedHeight ?? ''}`).join('|'),
    props.edges.map((edge) => `${edge.id}:${edge.source}:${edge.target}`).join('|'),
  ],
  () => {
    void fitDiagram()
  },
)
</script>

<template>
  <section class="studio-node-diagram">
    <div class="diagram-header">
      <div>
        <h2>{{ headline }}</h2>
        <p>{{ summary }}</p>
      </div>
    </div>
    <div class="diagram-frame" :style="{ height: `${height ?? 560}px` }">
      <VueFlow
        :id="flowId"
        class="diagram-flow"
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
        :fit-view-on-init="false"
        :min-zoom="0.32"
        :max-zoom="1.5"
        @node-click="onNodeClick"
      >
        <template #node-studioDiagramNode="{ data }">
          <article class="diagram-node" :class="[`diagram-status-${data.status}`, `detail-${detailLevel}`]">
            <div class="node-topline">
              <span class="node-dot" aria-hidden="true"></span>
              <span class="status-chip" :class="`status-${data.status}`">{{ statusLabel(data.status) }}</span>
            </div>
            <span v-if="data.subtitle" class="node-subtitle">{{ data.subtitle }}</span>
            <h3>{{ data.title }}</h3>
            <p>{{ data.detail }}</p>
            <ul v-if="data.meta?.length" class="node-meta">
              <li v-for="item in data.meta.slice(0, metaLimit(data))" :key="item">{{ item }}</li>
            </ul>
            <div v-if="data.detailGroups?.length" class="node-detail-groups" :class="`groups-${detailLevel}`">
              <section
                v-for="group in data.detailGroups"
                :key="group.title"
                class="node-detail-group"
                :class="`group-${group.tone ?? 'neutral'}`"
              >
                <button
                  type="button"
                  class="group-heading"
                  :class="{ clickable: !!group.path }"
                  @click.stop="onGroupClick(group.path)"
                >
                  <span>{{ group.title }}</span>
                  <strong v-if="typeof group.count === 'number'">{{ group.count }}</strong>
                </button>
                <div v-if="detailLevel !== 'compact'" class="group-items">
                  <div
                    v-for="(item, itemIndex) in visibleGroupItems(group)"
                    :key="groupItemKey(data.id, group.title, item, itemIndex)"
                    class="group-item-wrap"
                  >
                    <button
                      type="button"
                      class="group-item"
                      :class="{ clickable: !!groupItemPath(item) || groupItemChoices(item).length > 0 }"
                      @click.stop="onItemClick(item, groupItemKey(data.id, group.title, item, itemIndex))"
                    >
                      {{ groupItemLabel(item) }}
                    </button>
                    <div
                      v-if="activeChoiceKey === groupItemKey(data.id, group.title, item, itemIndex)"
                      class="group-choice-list"
                      @click.stop
                    >
                      <span>Choose capability</span>
                      <button
                        v-for="choice in groupItemChoices(item)"
                        :key="choice.path"
                        type="button"
                        @click.stop="emit('navigate', choice.path)"
                      >
                        {{ choice.label }}
                      </button>
                    </div>
                  </div>
                </div>
              </section>
            </div>
            <ul v-if="detailLevel === 'expanded' && data.expandedMeta?.length" class="node-expanded-meta">
              <li v-for="item in data.expandedMeta.slice(0, 4)" :key="item">{{ item }}</li>
            </ul>
          </article>
        </template>
      </VueFlow>
      <div class="diagram-controls" aria-label="Diagram zoom controls">
        <span class="zoom-level">{{ Math.round(zoomLevel * 100) }}%</span>
        <button type="button" @click="zoomOut()">−</button>
        <button type="button" @click="fitDiagram()">Fit</button>
        <button type="button" @click="zoomIn()">+</button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.studio-node-diagram {
  width: 100%;
}

.diagram-header {
  margin-bottom: 1rem;
}

.diagram-header h2 {
  margin: 0;
  color: var(--text-primary);
}

.diagram-header p {
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
    radial-gradient(circle at 10% 12%, rgba(59, 130, 246, 0.16), transparent 32%),
    radial-gradient(circle at 84% 18%, rgba(45, 212, 191, 0.11), transparent 28%),
    radial-gradient(circle at 62% 90%, rgba(251, 191, 36, 0.08), transparent 28%),
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

.zoom-level {
  min-width: 52px;
  border-right: 1px solid rgba(148, 163, 184, 0.18);
  padding: 0.44rem 0.62rem;
  color: #93c5fd;
  font-size: 11px;
  font-weight: 900;
  line-height: 1.3;
  text-align: center;
}

.diagram-controls button:last-child {
  border-right: 0;
}

.diagram-controls button:hover {
  background: rgba(14, 165, 233, 0.18);
}

.diagram-flow {
  width: 100%;
  height: 100%;
}

.diagram-flow :deep(.vue-flow__pane) {
  cursor: grab;
}

.diagram-flow :deep(.vue-flow__edge-path) {
  filter: drop-shadow(0 0 7px rgba(14, 165, 233, 0.22));
}

.diagram-flow :deep(.vue-flow__handle) {
  width: 8px;
  height: 8px;
  border: 1px solid rgba(226, 232, 240, 0.78);
  background: #0f172a;
}

.diagram-node {
  display: grid;
  gap: 0.38rem;
  width: 100%;
  height: 100%;
  overflow: hidden;
  border: 1px solid var(--surface-border-card);
  border-radius: 19px;
  padding: 0.86rem;
  background:
    radial-gradient(circle at top left, rgba(125, 211, 252, 0.1), transparent 42%),
    rgba(2, 6, 23, 0.82);
  box-shadow: 0 16px 44px rgba(2, 6, 23, 0.26);
  cursor: pointer;
  transition: border-color 0.16s ease, transform 0.16s ease, background 0.16s ease;
}

.diagram-node:hover {
  transform: translateY(-1px);
  border-color: rgba(125, 211, 252, 0.52);
  background:
    radial-gradient(circle at top left, rgba(125, 211, 252, 0.17), transparent 42%),
    rgba(14, 116, 144, 0.22);
}

.diagram-status-ready {
  border-color: rgba(45, 212, 191, 0.34);
}

.diagram-status-draftable {
  border-color: rgba(96, 165, 250, 0.34);
}

.diagram-status-needs_clarification {
  border-color: rgba(251, 191, 36, 0.42);
  background:
    radial-gradient(circle at top left, rgba(251, 191, 36, 0.14), transparent 40%),
    rgba(120, 53, 15, 0.22);
}

.diagram-status-blocked {
  border-color: rgba(248, 113, 113, 0.46);
  background:
    radial-gradient(circle at top left, rgba(248, 113, 113, 0.15), transparent 40%),
    rgba(127, 29, 29, 0.2);
}

.node-topline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.node-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: #94a3b8;
}

.diagram-status-ready .node-dot {
  background: #2dd4bf;
}

.diagram-status-draftable .node-dot {
  background: #60a5fa;
}

.diagram-status-needs_clarification .node-dot {
  background: #fbbf24;
}

.diagram-status-blocked .node-dot {
  background: #f87171;
}

.status-chip,
.node-subtitle {
  border-radius: 999px;
  padding: 0.2rem 0.46rem;
  background: rgba(148, 163, 184, 0.12);
  color: #cbd5e1;
  font-size: 9px;
  font-weight: 850;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  white-space: nowrap;
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

.node-subtitle {
  justify-self: start;
  color: #bae6fd;
  background: rgba(14, 165, 233, 0.12);
}

.diagram-node h3 {
  margin: 0;
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 900;
  line-height: 1.22;
}

.diagram-node p {
  margin: 0;
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: var(--medium-detail-lines, 4);
  color: var(--text-secondary);
  font-size: 11px;
  line-height: 1.36;
}

.detail-expanded p {
  -webkit-line-clamp: var(--expanded-detail-lines, 6);
}

.detail-compact p {
  -webkit-line-clamp: var(--compact-detail-lines, 2);
}

.node-meta {
  display: grid;
  gap: 0.18rem;
  margin: 0;
  padding: 0;
  list-style: none;
  color: #dbeafe;
  font-size: 10px;
  line-height: 1.28;
}

.node-meta li {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-expanded-meta {
  display: grid;
  gap: 0.16rem;
  margin: 0;
  padding-left: 1rem;
  color: #cbd5e1;
  font-size: 9px;
  line-height: 1.25;
}

.detail-compact {
  align-content: center;
}

.detail-compact .node-subtitle {
  display: none;
}

.node-detail-groups {
  display: grid;
  gap: 0.36rem;
  min-width: 0;
}

.node-detail-group {
  overflow: hidden;
  border: 1px solid var(--surface-border-card);
  border-radius: 13px;
  background: var(--surface-depth-card);
}

.group-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  width: 100%;
  border: 0;
  padding: 0.42rem 0.5rem;
  background: transparent;
  color: #dbeafe;
  font-size: 10px;
  font-weight: 900;
  letter-spacing: 0.04em;
  text-align: left;
  text-transform: uppercase;
}

.group-heading.clickable {
  cursor: pointer;
}

.group-heading.clickable:hover {
  background: rgba(125, 211, 252, 0.08);
}

.group-heading strong {
  min-width: 1.55rem;
  border-radius: 999px;
  padding: 0.12rem 0.36rem;
  background: var(--surface-depth-card);
  color: #f8fafc;
  font-size: 10px;
  text-align: center;
}

.group-capability {
  border-color: rgba(96, 165, 250, 0.26);
  background: rgba(30, 64, 175, 0.16);
}

.group-behavior {
  border-color: rgba(45, 212, 191, 0.26);
  background: rgba(15, 118, 110, 0.14);
}

.group-authority {
  border-color: rgba(251, 191, 36, 0.3);
  background: rgba(146, 64, 14, 0.16);
}

.group-glue {
  border-color: rgba(244, 114, 182, 0.32);
  background: rgba(157, 23, 77, 0.16);
}

.group-neutral {
  border-color: rgba(148, 163, 184, 0.18);
}

.group-items {
  display: flex;
  flex-wrap: wrap;
  gap: 0.24rem;
  padding: 0 0.5rem 0.48rem;
}

.group-item-wrap {
  position: relative;
  min-width: 0;
}

.group-item {
  max-width: 100%;
  overflow: hidden;
  border: 1px solid rgba(226, 232, 240, 0.1);
  border-radius: 999px;
  padding: 0.14rem 0.38rem;
  background: var(--surface-depth-inset);
  color: #e0f2fe;
  font-size: 9px;
  font-weight: 800;
  line-height: 1.25;
  cursor: default;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.group-item.clickable {
  cursor: pointer;
}

.group-item.clickable:hover {
  border-color: rgba(125, 211, 252, 0.4);
  background: rgba(14, 165, 233, 0.22);
}

.group-choice-list {
  position: absolute;
  top: calc(100% + 0.3rem);
  left: 0;
  z-index: 9;
  display: grid;
  gap: 0.24rem;
  min-width: 180px;
  max-width: 240px;
  border: 1px solid rgba(125, 211, 252, 0.28);
  border-radius: 12px;
  padding: 0.45rem;
  background: rgba(2, 6, 23, 0.96);
  box-shadow: 0 18px 48px rgba(2, 6, 23, 0.44);
}

.group-choice-list span {
  color: #93c5fd;
  font-size: 9px;
  font-weight: 900;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.group-choice-list button {
  border: 0;
  border-radius: 9px;
  padding: 0.34rem 0.42rem;
  background: rgba(15, 23, 42, 0.88);
  color: #e0f2fe;
  font-size: 10px;
  font-weight: 800;
  text-align: left;
  cursor: pointer;
}

.group-choice-list button:hover {
  background: rgba(14, 165, 233, 0.26);
}

.groups-compact .node-detail-group {
  border-radius: 999px;
}

.groups-compact {
  gap: 0.26rem;
}
</style>
