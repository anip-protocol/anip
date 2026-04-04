<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { projectStore, loadProject, refreshArtifacts, setActiveShape } from '../design/project-store'
import { getShape, updateShape, getShapeExpectations } from '../design/project-api'
import type { ShapeRecord } from '../design/project-types'
import type { ShapeData, ShapeService, CoordinationEdge, DomainConcept, DerivedExpectation } from '../design/shape-types'

const route = useRoute()
const router = useRouter()

const projectId = computed(() => route.params.projectId as string)
const shapeId = computed(() => route.params.id as string)

const shape = ref<ShapeRecord | null>(null)
const shapeData = computed<ShapeData | null>(() => {
  const raw = shape.value?.data
  if (!raw) return null
  return (raw.shape ?? raw) as ShapeData
})

const loading = ref(false)
const saving = ref(false)
const saveError = ref<string | null>(null)
const expectations = ref<DerivedExpectation[]>([])
const expectationsLoading = ref(false)

const isEditing = computed(() => shape.value?.status === 'draft')

onMounted(async () => {
  if (projectId.value && projectStore.activeProject?.id !== projectId.value) {
    await loadProject(projectId.value)
  }
  await loadShape()
})

watch([projectId, shapeId], async () => {
  await loadShape()
})

async function loadShape() {
  if (!projectId.value || !shapeId.value) return
  loading.value = true
  try {
    shape.value = await getShape(projectId.value, shapeId.value)
    setActiveShape(shapeId.value)
    await loadExpectations()
  } catch {
    shape.value = null
  } finally {
    loading.value = false
  }
}

async function loadExpectations() {
  if (!projectId.value || !shapeId.value) return
  expectationsLoading.value = true
  try {
    expectations.value = await getShapeExpectations(projectId.value, shapeId.value)
  } catch {
    expectations.value = []
  } finally {
    expectationsLoading.value = false
  }
}

async function handleSave() {
  if (!shape.value || !projectId.value) return
  saving.value = true
  saveError.value = null
  try {
    shape.value = await updateShape(projectId.value, shape.value.id, {
      title: shape.value.title,
      data: shape.value.data,
    })
    await refreshArtifacts()
    await loadExpectations()
  } catch (err) {
    saveError.value = err instanceof Error ? err.message : String(err)
  } finally {
    saving.value = false
  }
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

// --- Inline edit helpers ---

function addNote() {
  if (!shapeData.value) return
  const target = shape.value!.data.shape ?? shape.value!.data
  if (!target.notes) target.notes = []
  target.notes.push('')
}

function removeNote(index: number) {
  const target = shape.value!.data.shape ?? shape.value!.data
  if (target.notes) target.notes.splice(index, 1)
}

function updateNote(index: number, value: string) {
  const target = shape.value!.data.shape ?? shape.value!.data
  if (target.notes) target.notes[index] = value
}

const services = computed<ShapeService[]>(() => shapeData.value?.services ?? [])
const coordination = computed<CoordinationEdge[]>(() => shapeData.value?.coordination ?? [])
const domainConcepts = computed<DomainConcept[]>(() => shapeData.value?.domain_concepts ?? [])

function relationshipLabel(rel: string): string {
  const labels: Record<string, string> = {
    handoff: 'Handoff',
    verification: 'Verification',
    async_followup: 'Async Followup',
  }
  return labels[rel] || rel
}

function sensitivityLabel(s: string | undefined): string {
  if (!s || s === 'none') return 'None'
  if (s === 'medium') return 'Medium'
  if (s === 'high') return 'High'
  return s
}
</script>

<template>
  <div class="shape-view">
    <div v-if="loading && !shape" class="loading-state">Loading shape...</div>

    <template v-if="shape && shapeData">
      <!-- Header -->
      <div class="shape-header">
        <div class="header-top">
          <button class="back-link" @click="router.push(`/design/projects/${projectId}`)">
            &larr; Project
          </button>
        </div>
        <div class="title-row">
          <h1 class="page-title">{{ shapeData.name || shape.title }}</h1>
          <span class="type-badge" :class="'type-' + shapeData.type">
            {{ shapeData.type === 'single_service' ? 'Single Service' : 'Multi Service' }}
          </span>
          <span class="status-badge" :class="'status-' + shape.status">{{ shape.status }}</span>
        </div>
        <div class="shape-meta">
          <span class="meta-date">Updated {{ formatDate(shape.updated_at) }}</span>
        </div>
      </div>

      <!-- Editor toolbar -->
      <div class="toolbar" v-if="isEditing">
        <button class="btn btn-primary" :disabled="saving" @click="handleSave">
          {{ saving ? 'Saving...' : 'Save Changes' }}
        </button>
        <span v-if="saveError" class="save-error">{{ saveError }}</span>
      </div>

      <!-- Notes -->
      <section class="shape-section">
        <h2 class="section-title">Why This Shape</h2>
        <div v-if="shapeData.notes && shapeData.notes.length > 0" class="notes-list">
          <div v-for="(note, i) in shapeData.notes" :key="i" class="note-item">
            <template v-if="isEditing">
              <input
                class="note-input"
                :value="note"
                @input="updateNote(i, ($event.target as HTMLInputElement).value)"
                placeholder="Design rationale..."
              />
              <button class="remove-btn" @click="removeNote(i)" title="Remove note">&times;</button>
            </template>
            <span v-else class="note-text">{{ note }}</span>
          </div>
        </div>
        <div v-else-if="!isEditing" class="empty-hint">No notes yet. Capture the main boundary or tradeoff decisions behind this shape.</div>
        <button v-if="isEditing" class="btn btn-secondary btn-sm" @click="addNote">+ Add Note</button>
      </section>

      <!-- Services -->
      <section class="shape-section">
        <h2 class="section-title">Service Responsibilities ({{ services.length }})</h2>
        <div v-if="services.length === 0" class="empty-hint">No services defined yet. Start by naming the service or service estate you want to shape.</div>
        <div v-for="svc in services" :key="svc.id" class="service-card">
          <div class="service-header">
            <span class="service-name">{{ svc.name }}</span>
            <span class="service-role">{{ svc.role }}</span>
          </div>
          <div v-if="svc.responsibilities && svc.responsibilities.length" class="service-detail">
            <span class="detail-label">Responsibilities</span>
            <ul class="detail-list">
              <li v-for="(r, i) in svc.responsibilities" :key="i">{{ r }}</li>
            </ul>
          </div>
          <div v-if="svc.capabilities && svc.capabilities.length" class="service-detail">
            <span class="detail-label">Capabilities</span>
            <ul class="detail-list">
              <li v-for="(c, i) in svc.capabilities" :key="i">{{ c }}</li>
            </ul>
          </div>
          <div v-if="svc.owns_concepts && svc.owns_concepts.length" class="service-detail">
            <span class="detail-label">Owned Concepts</span>
            <div class="concept-pills">
              <span v-for="(c, i) in svc.owns_concepts" :key="i" class="concept-pill">{{ c }}</span>
            </div>
          </div>
        </div>
      </section>

      <!-- Coordination -->
      <section class="shape-section" v-if="coordination.length > 0">
        <h2 class="section-title">How Services Coordinate ({{ coordination.length }})</h2>
        <div class="coordination-list">
          <div v-for="(edge, i) in coordination" :key="i" class="coordination-edge">
            <span class="edge-from">{{ edge.from }}</span>
            <span class="edge-arrow">&rarr;</span>
            <span class="edge-to">{{ edge.to }}</span>
            <span class="edge-relationship" :class="'rel-' + edge.relationship">
              {{ relationshipLabel(edge.relationship) }}
            </span>
            <span v-if="edge.description" class="edge-desc">{{ edge.description }}</span>
          </div>
        </div>
      </section>

      <!-- Domain Concepts -->
      <section class="shape-section" v-if="domainConcepts.length > 0">
        <h2 class="section-title">Domain Concepts ({{ domainConcepts.length }})</h2>
        <table class="concepts-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Meaning</th>
              <th>Owner</th>
              <th>Sensitivity</th>
              <th>Risk Note</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="concept in domainConcepts" :key="concept.id">
              <td class="concept-name">{{ concept.name }}</td>
              <td>{{ concept.meaning }}</td>
              <td>{{ concept.owner || '--' }}</td>
              <td>
                <span class="sensitivity-badge" :class="'sensitivity-' + (concept.sensitivity || 'none')">
                  {{ sensitivityLabel(concept.sensitivity) }}
                </span>
              </td>
              <td>{{ concept.risk_note || '--' }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <!-- Derived Contract Expectations -->
      <section class="shape-section expectations-section">
        <h2 class="section-title">What ANIP Should Expose</h2>
        <p class="section-desc">These ANIP semantics are implied by this shape and its linked requirements. They are derived from the design rather than authored directly.</p>
        <div v-if="expectationsLoading" class="loading-hint">Loading expectations...</div>
        <div v-else-if="expectations.length === 0" class="empty-hint">
          No expectations were derived yet. This usually means the shape or requirements are still too incomplete to evaluate confidently.
        </div>
        <div v-else class="expectations-list">
          <div v-for="(exp, i) in expectations" :key="i" class="expectation-item">
            <span class="expectation-surface">{{ exp.surface }}</span>
            <span class="expectation-reason">{{ exp.reason }}</span>
          </div>
        </div>
      </section>
    </template>

    <div v-else-if="!loading" class="not-found">Shape not found.</div>
  </div>
</template>

<style scoped>
.shape-view {
  padding: 2rem;
  max-width: 900px;
}

.loading-state,
.not-found {
  padding: 2rem;
  text-align: center;
  color: var(--text-muted);
  font-size: 14px;
}

/* Header */
.shape-header {
  margin-bottom: 1.5rem;
}

.header-top {
  margin-bottom: 0.5rem;
}

.back-link {
  background: none;
  border: none;
  color: var(--accent);
  font-size: 13px;
  cursor: pointer;
  padding: 0;
  transition: color var(--transition);
}

.back-link:hover {
  color: var(--accent-hover);
}

.title-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.page-title {
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.type-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 10px;
  border-radius: 10px;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.type-single_service {
  background: rgba(59, 130, 246, 0.15);
  color: #3b82f6;
}

.type-multi_service {
  background: rgba(168, 85, 247, 0.15);
  color: #a855f7;
}

.status-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 10px;
  text-transform: capitalize;
  background: var(--bg-hover);
  color: var(--text-muted);
}

.status-active {
  background: rgba(52, 211, 153, 0.15);
  color: #34d399;
}

.status-draft {
  background: rgba(251, 191, 36, 0.15);
  color: #fbbf24;
}

.status-archived {
  background: rgba(156, 163, 175, 0.15);
  color: #9ca3af;
}

.shape-meta {
  margin-top: 0.25rem;
}

.meta-date {
  font-size: 12px;
  color: var(--text-muted);
}

/* Toolbar */
.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 1.5rem;
}

.save-error {
  font-size: 13px;
  color: var(--error);
}

/* Buttons */
.btn {
  height: 34px;
  padding: 0 16px;
  border: none;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background var(--transition);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: var(--accent);
  color: #fff;
}

.btn-primary:hover:not(:disabled) {
  background: var(--accent-hover);
}

.btn-secondary {
  background: var(--bg-input);
  color: var(--text-secondary);
  border: 1px solid var(--border);
}

.btn-secondary:hover:not(:disabled) {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.btn-sm {
  height: 28px;
  padding: 0 12px;
  font-size: 12px;
}

/* Sections */
.shape-section {
  margin-bottom: 1.5rem;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 0.5rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border);
}

.section-desc {
  font-size: 13px;
  color: var(--text-muted);
  margin: 0 0 0.75rem;
}

.empty-hint {
  font-size: 13px;
  color: var(--text-muted);
  padding: 8px 0;
}

.loading-hint {
  font-size: 13px;
  color: var(--text-muted);
  padding: 8px 0;
}

/* Notes */
.notes-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 8px;
}

.note-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.note-text {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.note-input {
  flex: 1;
  height: 32px;
  padding: 0 10px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 13px;
  outline: none;
  transition: border-color var(--transition);
}

.note-input:focus {
  border-color: var(--border-focus);
}

.remove-btn {
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  color: var(--text-muted);
  font-size: 16px;
  cursor: pointer;
  border-radius: var(--radius-sm);
  transition: all var(--transition);
  display: flex;
  align-items: center;
  justify-content: center;
}

.remove-btn:hover {
  background: rgba(248, 113, 113, 0.12);
  color: var(--error);
}

/* Service cards */
.service-card {
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1rem;
  margin-bottom: 8px;
}

.service-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 0.5rem;
}

.service-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.service-role {
  font-size: 12px;
  color: var(--text-muted);
  font-style: italic;
}

.service-detail {
  margin-top: 0.5rem;
}

.detail-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  color: var(--text-muted);
  display: block;
  margin-bottom: 4px;
}

.detail-list {
  list-style: disc;
  padding-left: 1.25rem;
  margin: 0;
}

.detail-list li {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.concept-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.concept-pill {
  font-size: 11px;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 8px;
  background: rgba(168, 85, 247, 0.1);
  color: #a855f7;
  border: 1px solid rgba(168, 85, 247, 0.25);
}

/* Coordination */
.coordination-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.coordination-edge {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  flex-wrap: wrap;
}

.edge-from,
.edge-to {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.edge-arrow {
  color: var(--text-muted);
  font-size: 14px;
}

.edge-relationship {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 8px;
}

.rel-handoff {
  background: rgba(59, 130, 246, 0.12);
  color: #3b82f6;
}

.rel-verification {
  background: rgba(52, 211, 153, 0.12);
  color: #34d399;
}

.rel-async_followup {
  background: rgba(251, 191, 36, 0.12);
  color: #fbbf24;
}

.edge-desc {
  font-size: 12px;
  color: var(--text-muted);
  flex-basis: 100%;
  margin-top: 2px;
}

/* Domain Concepts table */
.concepts-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.concepts-table th {
  text-align: left;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  color: var(--text-muted);
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
}

.concepts-table td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
  color: var(--text-secondary);
}

.concept-name {
  font-weight: 500;
  color: var(--text-primary);
}

.sensitivity-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 6px;
}

.sensitivity-none {
  background: rgba(156, 163, 175, 0.12);
  color: var(--text-muted);
}

.sensitivity-medium {
  background: rgba(251, 191, 36, 0.12);
  color: #fbbf24;
}

.sensitivity-high {
  background: rgba(248, 113, 113, 0.12);
  color: #f87171;
}

/* Expectations */
.expectations-section {
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.25rem;
}

.expectations-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.expectation-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid var(--border);
}

.expectation-item:last-child {
  border-bottom: none;
}

.expectation-surface {
  font-size: 12px;
  font-weight: 600;
  color: var(--accent);
  min-width: 180px;
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.expectation-reason {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.4;
}
</style>
