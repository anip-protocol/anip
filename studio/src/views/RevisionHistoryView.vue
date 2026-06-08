<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  developerDefinitionArtifactId,
  findDeveloperDefinitionRevisionArtifacts,
  findLatestDeveloperDefinitionRevisionArtifact,
} from '../design/developer-definition'
import {
  findLatestProductDesignRevisionArtifact,
  findProductDesignRevisionArtifacts,
  productDesignSourceArtifacts,
  type ProductDesignRevisionData,
} from '../design/product-design'
import { createPmArtifact, deletePmArtifact, updatePmArtifact } from '../design/project-api'
import { loadProject, projectStore } from '../design/project-store'
import type { ArtifactRecord, DeveloperBaselineData, DeveloperDefinitionData } from '../design/project-types'
import { requestConfirmation } from '../design/confirm'
import { findReleaseRecordArtifacts } from '../design/release-lineage'
import { formatStudioTimestamp } from '../design/time'
import { DESIGN_TRACEABILITY_ARTIFACT_TYPE, findDeveloperBaselineArtifact } from '../design/traceability'

type RevisionLane = 'product' | 'developer'
type RevisionStatus = 'latest' | 'active' | 'published' | 'superseded'
type DiffKind = 'added' | 'removed' | 'changed' | 'unchanged'

interface RevisionRow {
  key: string
  lane: RevisionLane
  revisionNumber: number
  artifactId: string
  previousArtifactId: string | null
  savedAt: string | null
  hash: string | null
  title: string
  status: RevisionStatus
  badges: string[]
  artifact: ArtifactRecord
  data: Record<string, any>
}

interface RevisionDiffItem {
  key: string
  section: string
  label: string
  before: string
  after: string
  kind: DiffKind
}

const route = useRoute()
const projectId = computed(() => route.params.projectId as string)
const project = computed(() => projectStore.activeProject)
const selectedKey = ref<string | null>(null)
const compareLane = ref<RevisionLane>('product')
const compareFromKey = ref<string | null>(null)
const compareToKey = ref<string | null>(null)
const copied = ref(false)
const creatingDraft = ref(false)
const draftActionError = ref<string | null>(null)
const draftActionMessage = ref<string | null>(null)
const readOnlyMode = computed(() => projectStore.runtimeStatus?.read_only_mode !== false)
const readOnlyReason = computed(() =>
  projectStore.runtimeStatus?.read_only_reason
  || 'Studio is running in read-only mode. Explore the design, then download and run Studio locally to make changes.',
)

async function ensureLoaded() {
  if (!projectId.value) return
  if (projectStore.activeProject?.id === projectId.value) return
  await loadProject(projectId.value)
}

onMounted(ensureLoaded)
watch(projectId, ensureLoaded)

const baseline = computed(() =>
  (findDeveloperBaselineArtifact(projectStore.artifacts.pmArtifacts)?.data as DeveloperBaselineData | undefined) ?? null,
)

const latestDeveloperRevisionArtifact = computed(() =>
  findLatestDeveloperDefinitionRevisionArtifact(projectStore.artifacts.pmArtifacts),
)

const latestProductRevisionArtifact = computed(() =>
  findLatestProductDesignRevisionArtifact(projectStore.artifacts.pmArtifacts),
)

const registryPublicationArtifacts = computed(() =>
  projectStore.artifacts.pmArtifacts.filter((artifact) =>
    artifact.data?.artifact_type === 'developer_registry_publication',
  ),
)
const pmApprovalArtifact = computed(() =>
  projectStore.artifacts.pmArtifacts.find((artifact) =>
    artifact.data?.artifact_type === DESIGN_TRACEABILITY_ARTIFACT_TYPE
    && artifact.data?.pm_review_status === 'approved',
  ) ?? null,
)
const releaseArtifacts = computed(() => findReleaseRecordArtifacts(projectStore.artifacts.pmArtifacts))

function revisionPublicationBadges(lane: RevisionLane, artifactId: string): string[] {
  const authorities = registryPublicationArtifacts.value
    .filter((artifact) => {
      const data = artifact.data ?? {}
      const published = data.published_from_saved_revision as Record<string, unknown> | undefined
      if (lane === 'product') {
        const publishedProduct = String(published?.product_revision_artifact_id ?? '')
        const packageProduct = String(data.package?.product_revision_ref ?? '')
        return publishedProduct === artifactId || packageProduct.includes(artifactId)
      }
      const publishedDeveloper = String(published?.revision_artifact_id ?? '')
      const packageDeveloper = String(data.package?.developer_revision_ref ?? '')
      return publishedDeveloper === artifactId || packageDeveloper.includes(artifactId)
    })
    .map((artifact) => String(artifact.data?.authority ?? 'published'))

  return [...new Set(authorities)].map((authority) =>
    authority === 'local-studio' ? 'local publication' : authority === 'remote-registry' ? 'registry publication' : authority,
  )
}

function revisionApprovalBadges(lane: RevisionLane, artifactId: string): string[] {
  const approval = pmApprovalArtifact.value?.data as Record<string, unknown> | undefined
  if (!approval) return []
  const target = lane === 'product'
    ? String(approval.pm_review_product_revision_artifact_id ?? '')
    : String(approval.pm_review_definition_revision_artifact_id ?? '')
  return target === artifactId ? ['PM approved'] : []
}

function revisionReleaseBadges(lane: RevisionLane, artifactId: string): string[] {
  const matches = releaseArtifacts.value.some((artifact) => {
    const chain = artifact.data?.approved_revision_chain as Record<string, unknown> | undefined
    const target = lane === 'product'
      ? String(chain?.product_revision_artifact_id ?? '')
      : String(chain?.developer_revision_artifact_id ?? '')
    return target === artifactId
  })
  return matches ? ['released'] : []
}

function statusForRevision(args: {
  lane: RevisionLane
  artifactId: string
  latestArtifactId: string | null
  activeArtifactId: string | null
  publicationBadges: string[]
}): RevisionStatus {
  if (args.activeArtifactId === args.artifactId) return 'active'
  if (args.latestArtifactId === args.artifactId) return 'latest'
  if (args.publicationBadges.length > 0) return 'published'
  return 'superseded'
}

const productRevisionRows = computed<RevisionRow[]>(() => {
  const latestArtifactId = latestProductRevisionArtifact.value?.id ?? null
  const activeArtifactId = baseline.value?.source_inputs.product_revision_artifact_id ?? null
  return findProductDesignRevisionArtifacts(projectStore.artifacts.pmArtifacts)
    .map((artifact) => {
      const data = artifact.data as ProductDesignRevisionData
      const publicationBadges = revisionPublicationBadges('product', data.revision_artifact_id)
      const approvalBadges = revisionApprovalBadges('product', data.revision_artifact_id)
      const releaseBadges = revisionReleaseBadges('product', data.revision_artifact_id)
      const status = statusForRevision({
        lane: 'product',
        artifactId: data.revision_artifact_id,
        latestArtifactId,
        activeArtifactId,
        publicationBadges,
      })
      return {
        key: `product:${data.revision_artifact_id}`,
        lane: 'product' as const,
        revisionNumber: data.revision_number,
        artifactId: data.revision_artifact_id,
        previousArtifactId: data.previous_revision_artifact_id,
        savedAt: data.saved_at,
        hash: data.product_design_hash,
        title: `Product Revision ${data.revision_number}`,
        status,
        badges: [
          ...(status === 'active' ? ['active baseline'] : status === 'latest' ? ['latest'] : []),
          ...approvalBadges,
          ...publicationBadges,
          ...releaseBadges,
        ],
        artifact,
        data: data as unknown as Record<string, any>,
      }
    })
    .sort((a, b) => b.revisionNumber - a.revisionNumber)
})

const developerRevisionRows = computed<RevisionRow[]>(() => {
  const latestArtifactId = latestDeveloperRevisionArtifact.value?.id ?? null
  return findDeveloperDefinitionRevisionArtifacts(projectStore.artifacts.pmArtifacts)
    .map((artifact) => {
      const data = artifact.data as DeveloperDefinitionData
      const savedRevision = data.saved_revision
      const artifactId = savedRevision?.revision_artifact_id ?? artifact.id
      const publicationBadges = revisionPublicationBadges('developer', artifactId)
      const approvalBadges = revisionApprovalBadges('developer', artifactId)
      const releaseBadges = revisionReleaseBadges('developer', artifactId)
      const status = statusForRevision({
        lane: 'developer',
        artifactId,
        latestArtifactId,
        activeArtifactId: latestArtifactId,
        publicationBadges,
      })
      return {
        key: `developer:${artifactId}`,
        lane: 'developer' as const,
        revisionNumber: savedRevision?.revision_number ?? 0,
        artifactId,
        previousArtifactId: savedRevision?.previous_revision_artifact_id ?? null,
        savedAt: savedRevision?.saved_at ?? data.saved_at ?? null,
        hash: data.compiled_contract_identity?.signature ?? null,
        title: `Developer Revision ${savedRevision?.revision_number ?? '?'}`,
        status,
        badges: [
          ...(status === 'active' ? ['active developer'] : status === 'latest' ? ['latest'] : []),
          ...approvalBadges,
          ...publicationBadges,
          ...releaseBadges,
        ],
        artifact,
        data: data as unknown as Record<string, any>,
      }
    })
    .sort((a, b) => b.revisionNumber - a.revisionNumber)
})

const allRevisionRows = computed(() => [...productRevisionRows.value, ...developerRevisionRows.value])
const compareRows = computed(() =>
  compareLane.value === 'product' ? productRevisionRows.value : developerRevisionRows.value,
)

watch(
  allRevisionRows,
  (rows) => {
    if (selectedKey.value && rows.some((row) => row.key === selectedKey.value)) return
    selectedKey.value = rows[0]?.key ?? null
  },
  { immediate: true },
)

watch(
  compareRows,
  (rows) => {
    if (compareFromKey.value && rows.some((row) => row.key === compareFromKey.value)) {
      if (!compareToKey.value || !rows.some((row) => row.key === compareToKey.value) || compareToKey.value === compareFromKey.value) {
        compareToKey.value = rows.find((row) => row.key !== compareFromKey.value)?.key ?? null
      }
      return
    }
    compareFromKey.value = rows[1]?.key ?? rows[0]?.key ?? null
    compareToKey.value = rows[0]?.key ?? null
    if (compareFromKey.value === compareToKey.value) {
      compareToKey.value = rows.find((row) => row.key !== compareFromKey.value)?.key ?? null
    }
  },
  { immediate: true },
)

const selectedRevision = computed(() =>
  allRevisionRows.value.find((row) => row.key === selectedKey.value) ?? null,
)

const selectedJson = computed(() =>
  selectedRevision.value ? JSON.stringify(selectedRevision.value.data, null, 2) : '',
)

const compareFromRevision = computed(() =>
  compareRows.value.find((row) => row.key === compareFromKey.value) ?? null,
)

const compareToRevision = computed(() =>
  compareRows.value.find((row) => row.key === compareToKey.value) ?? null,
)

function stringifyValue(value: unknown): string {
  if (value == null || value === '') return 'not recorded'
  if (Array.isArray(value)) return value.length ? value.map((item) => stringifyValue(item)).join(', ') : 'none'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function fieldDiff(
  section: string,
  label: string,
  before: unknown,
  after: unknown,
): RevisionDiffItem {
  const beforeText = stringifyValue(before)
  const afterText = stringifyValue(after)
  return {
    key: `${section}:${label}`,
    section,
    label,
    before: beforeText,
    after: afterText,
    kind: beforeText === afterText ? 'unchanged' : 'changed',
  }
}

function productDiffItems(before: RevisionRow, after: RevisionRow): RevisionDiffItem[] {
  const beforeData = before.data as unknown as ProductDesignRevisionData
  const afterData = after.data as unknown as ProductDesignRevisionData
  const items: RevisionDiffItem[] = [
    fieldDiff('Product lineage', 'Product design hash', beforeData.product_design_hash, afterData.product_design_hash),
    fieldDiff('Product lineage', 'Snapshot item count', beforeData.snapshot?.length ?? 0, afterData.snapshot?.length ?? 0),
  ]
  const beforeByType = new Map((beforeData.snapshot ?? []).map((item) => [item.artifact_type, item]))
  const afterByType = new Map((afterData.snapshot ?? []).map((item) => [item.artifact_type, item]))
  const artifactTypes = [...new Set([...beforeByType.keys(), ...afterByType.keys()])].sort()
  for (const artifactType of artifactTypes) {
    const beforeItem = beforeByType.get(artifactType)
    const afterItem = afterByType.get(artifactType)
    if (!beforeItem && afterItem) {
      items.push({
        key: `product:${artifactType}`,
        section: 'Product artifacts',
        label: artifactType,
        before: 'missing',
        after: afterItem.content_hash,
        kind: 'added',
      })
      continue
    }
    if (beforeItem && !afterItem) {
      items.push({
        key: `product:${artifactType}`,
        section: 'Product artifacts',
        label: artifactType,
        before: beforeItem.content_hash,
        after: 'removed',
        kind: 'removed',
      })
      continue
    }
    items.push({
      key: `product:${artifactType}`,
      section: 'Product artifacts',
      label: artifactType,
      before: beforeItem?.content_hash ?? 'missing',
      after: afterItem?.content_hash ?? 'missing',
      kind: beforeItem?.content_hash === afterItem?.content_hash ? 'unchanged' : 'changed',
    })
  }
  return items
}

function developerCapabilityIds(data: DeveloperDefinitionData): string[] {
  return (data.capability_formalizations ?? [])
    .map((capability) => capability.capability_id || capability.id || capability.title)
    .filter((value): value is string => typeof value === 'string' && value.trim().length > 0)
    .sort()
}

function developerDiffItems(before: RevisionRow, after: RevisionRow): RevisionDiffItem[] {
  const beforeData = before.data as unknown as DeveloperDefinitionData
  const afterData = after.data as unknown as DeveloperDefinitionData
  return [
    fieldDiff('Contract identity', 'Compiled signature', beforeData.compiled_contract_identity?.signature, afterData.compiled_contract_identity?.signature),
    fieldDiff('Product lineage', 'Product revision', beforeData.source_inputs?.product_revision_number, afterData.source_inputs?.product_revision_number),
    fieldDiff('Product lineage', 'Product revision artifact', beforeData.source_inputs?.product_revision_artifact_id, afterData.source_inputs?.product_revision_artifact_id),
    fieldDiff('Product lineage', 'Product design hash', beforeData.source_inputs?.product_design_hash, afterData.source_inputs?.product_design_hash),
    fieldDiff('Source inputs', 'Baseline locked at', beforeData.source_inputs?.baseline_locked_at, afterData.source_inputs?.baseline_locked_at),
    fieldDiff('Identity', 'System name', beforeData.identity?.system_name, afterData.identity?.system_name),
    fieldDiff('Identity', 'Delivery model', beforeData.identity?.delivery_model, afterData.identity?.delivery_model),
    fieldDiff('Identity', 'Architecture shape', beforeData.identity?.architecture_shape, afterData.identity?.architecture_shape),
    fieldDiff('Generation', 'Codegen adapter', beforeData.generation?.codegen_adapter, afterData.generation?.codegen_adapter),
    fieldDiff('Generation', 'Layout strategy', beforeData.generation?.layout_strategy, afterData.generation?.layout_strategy),
    fieldDiff('Generation', 'Protocols', beforeData.generation?.protocols, afterData.generation?.protocols),
    fieldDiff('Generation', 'Selected services', beforeData.generation?.selected_service_ids, afterData.generation?.selected_service_ids),
    fieldDiff('Capabilities', 'Capability count', beforeData.capability_formalizations?.length ?? 0, afterData.capability_formalizations?.length ?? 0),
    fieldDiff('Capabilities', 'Capability ids', developerCapabilityIds(beforeData), developerCapabilityIds(afterData)),
    fieldDiff('Backend bindings', 'Service backend binding count', beforeData.service_backend_bindings?.length ?? 0, afterData.service_backend_bindings?.length ?? 0),
    fieldDiff('Verification', 'Question family binding count', beforeData.verification?.supported_question_family_bindings?.length ?? 0, afterData.verification?.supported_question_family_bindings?.length ?? 0),
    fieldDiff('Verification', 'Business goal binding count', beforeData.verification?.business_goal_bindings?.length ?? 0, afterData.verification?.business_goal_bindings?.length ?? 0),
  ]
}

const revisionDiffItems = computed<RevisionDiffItem[]>(() => {
  if (!compareFromRevision.value || !compareToRevision.value || compareFromRevision.value.key === compareToRevision.value.key) return []
  return compareLane.value === 'product'
    ? productDiffItems(compareFromRevision.value, compareToRevision.value)
    : developerDiffItems(compareFromRevision.value, compareToRevision.value)
})

const changedDiffItems = computed(() => revisionDiffItems.value.filter((item) => item.kind !== 'unchanged'))
const unchangedDiffItems = computed(() => revisionDiffItems.value.filter((item) => item.kind === 'unchanged'))

function selectRevision(row: RevisionRow) {
  selectedKey.value = row.key
  copied.value = false
  draftActionError.value = null
  draftActionMessage.value = null
}

async function copySelectedJson() {
  if (!selectedJson.value || typeof navigator === 'undefined' || !navigator.clipboard) return
  await navigator.clipboard.writeText(selectedJson.value)
  copied.value = true
  window.setTimeout(() => {
    copied.value = false
  }, 1500)
}

function exportSelectedJson() {
  if (!selectedRevision.value || !selectedJson.value) return
  const blob = new Blob([selectedJson.value], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${selectedRevision.value.artifactId}.json`
  a.click()
  URL.revokeObjectURL(url)
}

async function createProductDraftFromRevision(row: RevisionRow) {
  if (readOnlyMode.value) {
    draftActionError.value = readOnlyReason.value
    return
  }
  if (!project.value) return
  const data = row.data as unknown as ProductDesignRevisionData
  const confirmed = await requestConfirmation({
    title: `Create Product draft from r${row.revisionNumber}?`,
    message: 'This replaces the editable Product Design artifacts with the selected revision snapshot. Existing immutable revisions and baselines are not changed.',
    confirmLabel: 'Create draft',
    cancelLabel: 'Cancel',
    tone: 'danger',
  })
  if (!confirmed) return

  const snapshotTypes = new Set((data.snapshot ?? []).map((item) => item.artifact_type))
  const currentProductArtifacts = productDesignSourceArtifacts(projectStore.artifacts.pmArtifacts)
  for (const artifact of currentProductArtifacts) {
    if (!snapshotTypes.has(artifact.data?.artifact_type)) {
      await deletePmArtifact(project.value.id, artifact.id)
    }
  }

  for (const snapshot of data.snapshot ?? []) {
    const existing = projectStore.artifacts.pmArtifacts.find((artifact) =>
      artifact.data?.artifact_type === snapshot.artifact_type,
    )
    const payload = {
      title: snapshot.title,
      status: 'draft',
      data: JSON.parse(JSON.stringify(snapshot.data)) as Record<string, any>,
    }
    if (existing) {
      await updatePmArtifact(project.value.id, existing.id, payload)
    } else {
      await createPmArtifact(project.value.id, {
        id: snapshot.artifact_id,
        title: snapshot.title,
        data: payload.data,
      })
    }
  }
  await loadProject(project.value.id)
  draftActionMessage.value = `Created editable Product Design draft from Product Revision ${row.revisionNumber}. Baseline was not changed.`
}

async function createDeveloperDraftFromRevision(row: RevisionRow) {
  if (readOnlyMode.value) {
    draftActionError.value = readOnlyReason.value
    return
  }
  if (!project.value) return
  const confirmed = await requestConfirmation({
    title: `Create Developer draft from r${row.revisionNumber}?`,
    message: 'This replaces the editable Developer Definition draft with the selected revision content, clears saved-revision metadata, and requires saving a new revision before generation.',
    confirmLabel: 'Create draft',
    cancelLabel: 'Cancel',
    tone: 'danger',
  })
  if (!confirmed) return

  const revisionData = JSON.parse(JSON.stringify(row.data)) as DeveloperDefinitionData
  const draftData: DeveloperDefinitionData = {
    ...revisionData,
    artifact_type: 'developer_definition',
    compiled_contract_identity: null,
    saved_revision: null,
    saved_at: null,
  }
  const artifactId = developerDefinitionArtifactId(project.value.id)
  const existing = projectStore.artifacts.pmArtifacts.find((artifact) =>
    artifact.data?.artifact_type === 'developer_definition',
  )
  if (existing) {
    await updatePmArtifact(project.value.id, existing.id, {
      title: 'Developer Definition',
      status: 'draft',
      data: draftData as unknown as Record<string, any>,
    })
  } else {
    await createPmArtifact(project.value.id, {
      id: artifactId,
      title: 'Developer Definition',
      data: draftData as unknown as Record<string, any>,
    })
  }
  await loadProject(project.value.id)
  draftActionMessage.value = `Created editable Developer Definition draft from Developer Revision ${row.revisionNumber}. Save it to create a new revision before generation.`
}

async function createDraftFromSelectedRevision() {
  if (readOnlyMode.value) {
    draftActionError.value = readOnlyReason.value
    return
  }
  if (!selectedRevision.value || creatingDraft.value) return
  creatingDraft.value = true
  draftActionError.value = null
  draftActionMessage.value = null
  try {
    if (selectedRevision.value.lane === 'product') {
      await createProductDraftFromRevision(selectedRevision.value)
    } else {
      await createDeveloperDraftFromRevision(selectedRevision.value)
    }
  } catch (err) {
    draftActionError.value = err instanceof Error ? err.message : String(err)
  } finally {
    creatingDraft.value = false
  }
}

function statusLabel(status: RevisionStatus) {
  switch (status) {
    case 'active':
      return 'Active'
    case 'latest':
      return 'Latest'
    case 'published':
      return 'Published'
    default:
      return 'Superseded'
  }
}
</script>

<template>
  <div class="revision-page">
    <header class="revision-hero">
      <div>
        <p class="eyebrow">Revision History</p>
        <h1>{{ project?.name || 'Project' }}</h1>
        <p class="hero-copy">
          Inspect immutable Product and Developer revisions. Selection here is read-only and does not change generation, verification, or publication targets.
        </p>
      </div>
      <div class="hero-stats">
        <div class="stat-card">
          <span class="stat-value">{{ productRevisionRows.length }}</span>
          <span class="stat-label">Product revisions</span>
        </div>
        <div class="stat-card">
          <span class="stat-value">{{ developerRevisionRows.length }}</span>
          <span class="stat-label">Developer revisions</span>
        </div>
      </div>
    </header>

    <div v-if="readOnlyMode" class="readonly-banner">
      <strong>Read-only showcase mode</strong>
      <span>{{ readOnlyReason }}</span>
    </div>

    <section class="compare-panel">
      <div class="compare-header">
        <div>
          <p class="eyebrow">Compare</p>
          <h2>What changed between revisions?</h2>
        </div>
        <div class="compare-lane-toggle" aria-label="Compare lane">
          <button
            type="button"
            :class="{ active: compareLane === 'product' }"
            @click="compareLane = 'product'"
          >
            Product
          </button>
          <button
            type="button"
            :class="{ active: compareLane === 'developer' }"
            @click="compareLane = 'developer'"
          >
            Developer
          </button>
        </div>
      </div>
      <div class="compare-controls">
        <label>
          <span>From</span>
          <select v-model="compareFromKey">
            <option
              v-for="row in compareRows"
              :key="`from-${row.key}`"
              :value="row.key"
            >
              r{{ row.revisionNumber }} · {{ row.artifactId }}
            </option>
          </select>
        </label>
        <span class="compare-arrow">→</span>
        <label>
          <span>To</span>
          <select v-model="compareToKey">
            <option
              v-for="row in compareRows"
              :key="`to-${row.key}`"
              :value="row.key"
            >
              r{{ row.revisionNumber }} · {{ row.artifactId }}
            </option>
          </select>
        </label>
      </div>
      <div v-if="compareFromRevision && compareToRevision && compareFromKey !== compareToKey" class="compare-summary">
        <strong>{{ compareFromRevision.title }} → {{ compareToRevision.title }}</strong>
        <span>{{ changedDiffItems.length }} changed · {{ unchangedDiffItems.length }} unchanged</span>
      </div>
      <div v-if="changedDiffItems.length" class="diff-list">
        <article
          v-for="item in changedDiffItems"
          :key="item.key"
          class="diff-item"
          :class="`diff-${item.kind}`"
        >
          <div class="diff-title">
            <span>{{ item.section }}</span>
            <strong>{{ item.label }}</strong>
            <em>{{ item.kind }}</em>
          </div>
          <div class="diff-values">
            <p><span>Before</span>{{ item.before }}</p>
            <p><span>After</span>{{ item.after }}</p>
          </div>
        </article>
      </div>
      <p v-else-if="compareFromKey === compareToKey" class="empty-state">
        Choose two different revisions in the same lane to compare.
      </p>
      <p v-else class="empty-state">
        No changed fields in the structured comparison.
      </p>
    </section>

    <div class="revision-grid">
      <section class="revision-column">
        <div class="section-heading">
          <h2>Product</h2>
          <span>{{ baseline?.source_inputs.product_revision_number ? `baseline r${baseline.source_inputs.product_revision_number}` : 'no baseline revision' }}</span>
        </div>
        <button
          v-for="row in productRevisionRows"
          :key="row.key"
          class="revision-row"
          :class="{ selected: selectedKey === row.key }"
          type="button"
          @click="selectRevision(row)"
        >
          <span class="row-main">
            <strong>r{{ row.revisionNumber }}</strong>
            <span>{{ row.artifactId }}</span>
          </span>
          <span class="row-meta">
            <span class="status-pill" :class="`status-${row.status}`">{{ statusLabel(row.status) }}</span>
            <span v-for="badge in row.badges" :key="badge" class="mini-pill">{{ badge }}</span>
          </span>
          <span class="row-time">{{ row.savedAt ? formatStudioTimestamp(row.savedAt) : 'time unknown' }}</span>
        </button>
        <p v-if="!productRevisionRows.length" class="empty-state">
          No Product revisions yet. Lock Developer Baseline to create Product Revision 1.
        </p>
      </section>

      <section class="revision-column">
        <div class="section-heading">
          <h2>Developer</h2>
          <span>{{ latestDeveloperRevisionArtifact ? 'latest saved revision' : 'no saved revision' }}</span>
        </div>
        <button
          v-for="row in developerRevisionRows"
          :key="row.key"
          class="revision-row"
          :class="{ selected: selectedKey === row.key }"
          type="button"
          @click="selectRevision(row)"
        >
          <span class="row-main">
            <strong>r{{ row.revisionNumber }}</strong>
            <span>{{ row.artifactId }}</span>
          </span>
          <span class="row-meta">
            <span class="status-pill" :class="`status-${row.status}`">{{ statusLabel(row.status) }}</span>
            <span v-for="badge in row.badges" :key="badge" class="mini-pill">{{ badge }}</span>
          </span>
          <span class="row-time">{{ row.savedAt ? formatStudioTimestamp(row.savedAt) : 'time unknown' }}</span>
        </button>
        <p v-if="!developerRevisionRows.length" class="empty-state">
          No Developer revisions yet. Save Developer Definition to create Developer Revision 1.
        </p>
      </section>

      <aside class="revision-detail">
        <div class="section-heading">
          <h2>Selected Revision</h2>
          <span v-if="selectedRevision">{{ selectedRevision.lane }}</span>
        </div>
        <div v-if="selectedRevision" class="detail-body">
          <dl class="detail-list">
            <div>
              <dt>Revision</dt>
              <dd>{{ selectedRevision.title }}</dd>
            </div>
            <div>
              <dt>Artifact ID</dt>
              <dd>{{ selectedRevision.artifactId }}</dd>
            </div>
            <div>
              <dt>Previous</dt>
              <dd>{{ selectedRevision.previousArtifactId || 'none' }}</dd>
            </div>
            <div>
              <dt>Saved</dt>
              <dd>{{ selectedRevision.savedAt ? formatStudioTimestamp(selectedRevision.savedAt) : 'unknown' }}</dd>
            </div>
            <div>
              <dt>Hash / Signature</dt>
              <dd>{{ selectedRevision.hash || 'not recorded' }}</dd>
            </div>
          </dl>
          <div class="detail-actions">
            <button type="button" class="primary-action" :disabled="readOnlyMode || creatingDraft" @click="createDraftFromSelectedRevision">
              {{ creatingDraft ? 'Creating draft...' : `Create ${selectedRevision.lane} draft from this revision` }}
            </button>
            <button type="button" @click="copySelectedJson">{{ copied ? 'Copied' : 'Copy JSON' }}</button>
            <button type="button" @click="exportSelectedJson">Export JSON</button>
          </div>
          <p v-if="draftActionMessage" class="action-message">{{ draftActionMessage }}</p>
          <p v-if="draftActionError" class="action-error">{{ draftActionError }}</p>
          <pre class="json-preview">{{ selectedJson }}</pre>
        </div>
        <p v-else class="empty-state">
          Select a revision to inspect its immutable snapshot.
        </p>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.revision-page {
  max-width: 1440px;
  margin: 0 auto;
  padding: 32px;
}

.revision-hero {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  padding: 28px;
  border: 1px solid var(--border);
  border-radius: 24px;
  background:
    radial-gradient(circle at top left, rgba(52, 211, 153, 0.14), transparent 32%),
    linear-gradient(135deg, rgba(15, 23, 42, 0.94), rgba(30, 41, 59, 0.74));
}

.eyebrow {
  margin: 0 0 8px;
  color: var(--accent);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.revision-hero h1 {
  margin: 0;
  font-size: 32px;
  letter-spacing: -0.04em;
}

.readonly-banner {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem 0.7rem;
  align-items: center;
  margin: 18px 0;
  padding: 0.85rem 1rem;
  border: 1px solid rgba(251, 191, 36, 0.34);
  border-radius: 16px;
  background: rgba(251, 191, 36, 0.1);
  color: #fde68a;
}

.readonly-banner span {
  color: var(--text-secondary);
}

.hero-copy {
  max-width: 760px;
  margin: 10px 0 0;
  color: var(--text-secondary);
}

.hero-stats {
  display: flex;
  gap: 12px;
  align-items: stretch;
}

.stat-card {
  min-width: 128px;
  padding: 16px;
  border: 1px solid var(--surface-border-card);
  border-radius: 18px;
  background: var(--surface-depth-card);
}

.stat-value {
  display: block;
  font-size: 28px;
  font-weight: 800;
}

.stat-label {
  color: var(--text-secondary);
  font-size: 12px;
}

.compare-panel {
  margin-top: 20px;
  padding: 20px;
  border: 1px solid var(--border);
  border-radius: 22px;
  background:
    linear-gradient(135deg, rgba(2, 6, 23, 0.76), rgba(15, 23, 42, 0.58)),
    radial-gradient(circle at top right, rgba(96, 165, 250, 0.12), transparent 34%);
}

.compare-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
}

.compare-header h2 {
  margin: 0;
  font-size: 18px;
}

.compare-lane-toggle {
  display: inline-flex;
  overflow: hidden;
  border: 1px solid rgba(71, 85, 105, 0.78);
  border-radius: 999px;
}

.compare-lane-toggle button {
  height: 32px;
  padding: 0 14px;
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 12px;
  font-weight: 800;
}

.compare-lane-toggle button.active {
  background: rgba(52, 211, 153, 0.14);
  color: rgba(187, 247, 208, 0.98);
}

.compare-controls {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  gap: 12px;
  align-items: end;
  margin-top: 16px;
}

.compare-controls label {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.compare-controls label span {
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.compare-controls select {
  min-width: 0;
  height: 36px;
  padding: 0 10px;
  border: 1px solid rgba(71, 85, 105, 0.78);
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.9);
  color: var(--text-primary);
}

.compare-arrow {
  color: var(--text-muted);
  font-size: 20px;
  line-height: 36px;
}

.compare-summary {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-top: 14px;
  color: var(--text-secondary);
  font-size: 13px;
}

.compare-summary strong {
  color: var(--text-primary);
}

.diff-list {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}

.diff-item {
  padding: 14px;
  border: 1px solid rgba(71, 85, 105, 0.62);
  border-radius: 16px;
  background: var(--surface-depth-inset);
}

.diff-added {
  border-color: rgba(52, 211, 153, 0.36);
}

.diff-removed {
  border-color: rgba(248, 113, 113, 0.42);
}

.diff-changed {
  border-color: rgba(96, 165, 250, 0.36);
}

.diff-title {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.diff-title span {
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.diff-title strong {
  color: var(--text-primary);
}

.diff-title em {
  margin-left: auto;
  color: var(--text-muted);
  font-size: 11px;
  font-style: normal;
  font-weight: 800;
  text-transform: uppercase;
}

.diff-values {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-top: 10px;
}

.diff-values p {
  min-width: 0;
  margin: 0;
  padding: 10px;
  overflow-wrap: anywhere;
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.72);
  color: var(--text-secondary);
  font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
  font-size: 11px;
}

.diff-values p span {
  display: block;
  margin-bottom: 4px;
  color: var(--text-muted);
  font-family: inherit;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.revision-grid {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) minmax(260px, 1fr) minmax(360px, 1.15fr);
  gap: 18px;
  margin-top: 20px;
}

.revision-column,
.revision-detail {
  min-width: 0;
  padding: 18px;
  border: 1px solid var(--border);
  border-radius: 20px;
  background: var(--surface-depth-card);
}

.section-heading {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  margin-bottom: 14px;
}

.section-heading h2 {
  margin: 0;
  font-size: 16px;
}

.section-heading span {
  color: var(--text-muted);
  font-size: 12px;
}

.revision-row {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  margin-bottom: 10px;
  padding: 14px;
  border: 1px solid rgba(71, 85, 105, 0.78);
  border-radius: 16px;
  background: var(--surface-depth-inset);
  color: var(--text-primary);
  cursor: pointer;
  text-align: left;
  transition: border-color var(--transition), background var(--transition), transform var(--transition);
}

.revision-row:hover,
.revision-row.selected {
  border-color: rgba(52, 211, 153, 0.58);
  background: rgba(15, 23, 42, 0.92);
  transform: translateY(-1px);
}

.row-main {
  display: flex;
  gap: 10px;
  align-items: baseline;
  min-width: 0;
}

.row-main strong {
  color: rgba(187, 247, 208, 0.98);
}

.row-main span {
  overflow: hidden;
  color: var(--text-secondary);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.row-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.status-pill,
.mini-pill {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
}

.status-pill {
  background: rgba(148, 163, 184, 0.12);
  color: rgba(226, 232, 240, 0.9);
}

.status-active {
  background: rgba(52, 211, 153, 0.14);
  color: rgba(187, 247, 208, 0.98);
}

.status-latest {
  background: rgba(96, 165, 250, 0.14);
  color: rgba(191, 219, 254, 0.98);
}

.status-published {
  background: rgba(251, 191, 36, 0.14);
  color: rgba(254, 240, 138, 0.98);
}

.status-superseded {
  background: rgba(148, 163, 184, 0.1);
  color: rgba(203, 213, 225, 0.82);
}

.mini-pill {
  background: rgba(30, 41, 59, 0.9);
  color: var(--text-secondary);
}

.row-time {
  color: var(--text-muted);
  font-size: 11px;
}

.empty-state {
  margin: 0;
  color: var(--text-muted);
  font-size: 13px;
}

.detail-body {
  min-width: 0;
}

.detail-list {
  display: grid;
  gap: 10px;
  margin: 0;
}

.detail-list div {
  min-width: 0;
}

.detail-list dt {
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.detail-list dd {
  margin: 2px 0 0;
  overflow-wrap: anywhere;
  color: var(--text-secondary);
  font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
  font-size: 12px;
}

.detail-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 16px 0;
}

.detail-actions button {
  height: 32px;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.82);
  color: var(--text-primary);
  cursor: pointer;
}

.detail-actions button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.detail-actions .primary-action {
  border-color: rgba(52, 211, 153, 0.48);
  background: rgba(20, 83, 45, 0.28);
  color: rgba(187, 247, 208, 0.98);
}

.action-message,
.action-error {
  margin: -4px 0 14px;
  padding: 10px 12px;
  border-radius: 12px;
  font-size: 12px;
}

.action-message {
  border: 1px solid rgba(52, 211, 153, 0.3);
  background: rgba(20, 83, 45, 0.18);
  color: rgba(187, 247, 208, 0.96);
}

.action-error {
  border: 1px solid rgba(248, 113, 113, 0.36);
  background: rgba(127, 29, 29, 0.22);
  color: rgba(254, 202, 202, 0.96);
}

.json-preview {
  max-height: 520px;
  margin: 0;
  padding: 14px;
  overflow: auto;
  border: 1px solid rgba(71, 85, 105, 0.7);
  border-radius: 14px;
  background: var(--surface-depth-inset);
  color: rgba(226, 232, 240, 0.9);
  font-size: 11px;
  line-height: 1.5;
}

@media (max-width: 1180px) {
  .revision-grid {
    grid-template-columns: 1fr;
  }

  .revision-hero {
    flex-direction: column;
  }

  .compare-header,
  .compare-summary {
    flex-direction: column;
    align-items: flex-start;
  }

  .compare-controls,
  .diff-values {
    grid-template-columns: 1fr;
  }

  .compare-arrow {
    display: none;
  }

  .hero-stats {
    flex-wrap: wrap;
  }
}
</style>
