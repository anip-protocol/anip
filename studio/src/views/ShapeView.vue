<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { projectStore, loadProject, refreshArtifacts, setActiveShape } from '../design/project-store'
import { createShape, getShape, updateShape, getShapeExpectations, explainShapeWithAssistant } from '../design/project-api'
import type { ShapeRecord, AssistantExplanation, DeveloperBaselineData } from '../design/project-types'
import type { ShapeData, ShapeService, CoordinationEdge, DomainConcept, DerivedExpectation } from '../design/shape-types'
import StudioAssistantPanel from '../design/components/StudioAssistantPanel.vue'
import { requestConfirmation } from '../design/confirm'
import { formatStudioTimestamp } from '../design/time'
import { findDeveloperBaselineArtifact } from '../design/traceability'

const route = useRoute()
const router = useRouter()

const projectId = computed(() => route.params.projectId as string)
const shapeId = computed(() => route.params.id as string)
const readOnlyMode = computed(() => projectStore.runtimeStatus?.read_only_mode !== false)
const readOnlyReason = computed(() =>
  projectStore.runtimeStatus?.read_only_reason
  || 'Studio is running in read-only mode. Explore the design, then download and run Studio locally to make changes.',
)

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
const assistantLoading = ref(false)
const assistantError = ref<string | null>(null)
const assistantExplanation = ref<AssistantExplanation | null>(null)
const inlineHelpSection = ref<string | null>(null)
const helpDialogSection = ref<string | null>(null)

const isEditing = computed(() => shape.value?.status === 'draft' && !readOnlyMode.value)
const linkedRequirements = computed(() =>
  projectStore.artifacts.requirements.find((item) => item.id === shape.value?.requirements_id) ?? null,
)
const observedServicesCount = computed(() => projectStore.artifacts.serviceMetadata.length)
const baselineArtifact = computed(() => findDeveloperBaselineArtifact(projectStore.artifacts.pmArtifacts))
const baseline = computed(() =>
  (baselineArtifact.value?.data as DeveloperBaselineData | undefined) ?? null,
)
const artifactIsLockedForDevelopment = computed(() =>
  !!baseline.value && baseline.value.source_inputs.shape_id === shape.value?.id,
)
const artifactIsWorkingRevision = computed(() =>
  !!baseline.value && !artifactIsLockedForDevelopment.value,
)

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
  if (readOnlyMode.value || !shape.value || !projectId.value) return
  saving.value = true
  saveError.value = null
  try {
    if (artifactIsLockedForDevelopment.value) {
      const title = shape.value.title || 'Service Design'
      const match = title.match(/^(.*?)(?:\s+Revision\s+(\d+))?$/i)
      const base = (match?.[1] || title).trim()
      const next = match?.[2] ? Number(match[2]) + 1 : 2
      const created = await createShape(projectId.value, {
        id: `shape-${crypto.randomUUID()}`,
        title: `${base} Revision ${next}`,
        requirements_id: shape.value.requirements_id,
        data: shape.value.data,
      })
      setActiveShape(created.id)
      await refreshArtifacts()
      router.push(`/design/projects/${projectId.value}/shapes/${created.id}`)
      return
    }

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
  return formatStudioTimestamp(iso, 'date')
}

// --- Inline edit helpers ---

function addNote() {
  if (readOnlyMode.value) return
  if (!shapeData.value) return
  const target = shape.value!.data.shape ?? shape.value!.data
  if (!target.notes) target.notes = []
  target.notes.push('')
}

async function removeNote(index: number) {
  if (readOnlyMode.value) return
  const confirmed = await requestConfirmation({
    title: 'Remove this note?',
    message: 'This will remove the selected design note.',
    confirmLabel: 'Remove Note',
    cancelLabel: 'Cancel',
    tone: 'danger',
  })
  if (!confirmed) return
  const target = shape.value!.data.shape ?? shape.value!.data
  if (target.notes) target.notes.splice(index, 1)
}

function updateNote(index: number, value: string) {
  if (readOnlyMode.value) return
  const target = shape.value!.data.shape ?? shape.value!.data
  if (target.notes) target.notes[index] = value
}

function editableShape(): ShapeData | null {
  if (readOnlyMode.value || !shape.value) return null
  const target = (shape.value.data.shape ?? shape.value.data) as ShapeData
  target.notes = Array.isArray(target.notes) ? target.notes : []
  target.services = Array.isArray(target.services) ? target.services : []
  target.coordination = Array.isArray(target.coordination) ? target.coordination : []
  target.domain_concepts = Array.isArray(target.domain_concepts) ? target.domain_concepts : []
  return target
}

function splitLines(value: string): string[] {
  return value
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean)
}

function joinLines(value: string[] | undefined): string {
  return Array.isArray(value) ? value.join('\n') : ''
}

function slugValue(value: string, fallback: string): string {
  const slug = value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
  return slug || fallback
}

function identifierValue(value: string, fallback: string): string {
  const identifier = value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^[_-]+|[_-]+$/g, '')
  return identifier || fallback
}

function updateShapeField(field: 'name' | 'type', value: string) {
  const target = editableShape()
  if (!target) return
  if (field === 'type') {
    target.type = value === 'multi_service' ? 'multi_service' : 'single_service'
    return
  }
  target.name = value
}

function addService() {
  const target = editableShape()
  if (!target) return
  const count = target.services.length + 1
  target.services.push({
    id: `service-${crypto.randomUUID().slice(0, 8)}`,
    name: `Service ${count}`,
    role: 'business capability service',
    responsibilities: ['Own a bounded business capability surface.'],
    capabilities: [],
    owns_concepts: [],
  })
  if (target.services.length > 1) target.type = 'multi_service'
}

async function removeService(index: number) {
  const target = editableShape()
  if (!target) return
  const service = target.services[index]
  const confirmed = await requestConfirmation({
    title: 'Remove this service?',
    message: `This removes ${service?.name || 'the service'} from the Service Design. Coordination edges that reference it should be reviewed after removal.`,
    confirmLabel: 'Remove Service',
    cancelLabel: 'Cancel',
    tone: 'danger',
  })
  if (!confirmed) return
  target.services.splice(index, 1)
  if (target.services.length <= 1) target.type = 'single_service'
}

function updateServiceField(index: number, field: 'id' | 'name' | 'role', value: string) {
  const target = editableShape()
  if (!target) return
  const service = target.services[index]
  if (!service) return
  service[field] = field === 'id' ? slugValue(value, service.id || `service-${index + 1}`) : value
}

function updateServiceList(index: number, field: 'responsibilities' | 'capabilities' | 'owns_concepts', value: string) {
  const target = editableShape()
  if (!target) return
  const service = target.services[index]
  if (!service) return
  service[field] = splitLines(value)
}

function addCoordination() {
  const target = editableShape()
  if (!target) return
  const first = target.services[0]?.id || ''
  const second = target.services[1]?.id || first
  target.coordination!.push({
    from: first,
    to: second,
    relationship: 'handoff',
    description: 'Describe the bounded handoff or verification step.',
  })
}

async function removeCoordination(index: number) {
  const target = editableShape()
  if (!target) return
  const confirmed = await requestConfirmation({
    title: 'Remove this coordination edge?',
    message: 'This removes the service handoff from the Service Design.',
    confirmLabel: 'Remove Edge',
    cancelLabel: 'Cancel',
    tone: 'danger',
  })
  if (!confirmed) return
  target.coordination!.splice(index, 1)
}

function updateCoordination(index: number, field: keyof CoordinationEdge, value: string) {
  const target = editableShape()
  if (!target) return
  const edge = target.coordination?.[index]
  if (!edge) return
  if (field === 'relationship') {
    edge.relationship = value === 'verification' || value === 'async_followup' ? value : 'handoff'
    return
  }
  edge[field] = value as never
}

function addDomainConcept() {
  const target = editableShape()
  if (!target) return
  const count = target.domain_concepts!.length + 1
  target.domain_concepts!.push({
    id: `concept-${crypto.randomUUID().slice(0, 8)}`,
    name: `Concept ${count}`,
    meaning: 'Define the business meaning this service protects.',
    owner: target.services[0]?.id || '',
    sensitivity: 'none',
    risk_note: '',
  })
}

async function removeDomainConcept(index: number) {
  const target = editableShape()
  if (!target) return
  const concept = target.domain_concepts?.[index]
  const confirmed = await requestConfirmation({
    title: 'Remove this domain concept?',
    message: `This removes ${concept?.name || 'the concept'} from the Service Design.`,
    confirmLabel: 'Remove Concept',
    cancelLabel: 'Cancel',
    tone: 'danger',
  })
  if (!confirmed) return
  target.domain_concepts!.splice(index, 1)
}

function updateDomainConcept(index: number, field: keyof DomainConcept, value: string) {
  const target = editableShape()
  if (!target) return
  const concept = target.domain_concepts?.[index]
  if (!concept) return
  if (field === 'id') {
    concept.id = identifierValue(value, concept.id || `concept_${index + 1}`)
    return
  }
  if (field === 'sensitivity') {
    concept.sensitivity = value === 'medium' || value === 'high' ? value : 'none'
    return
  }
  concept[field] = value as never
}

const services = computed<ShapeService[]>(() => shapeData.value?.services ?? [])
const coordination = computed<CoordinationEdge[]>(() => shapeData.value?.coordination ?? [])
const domainConcepts = computed<DomainConcept[]>(() => shapeData.value?.domain_concepts ?? [])
const serviceCount = computed(() => services.value.length)
const coordinationCount = computed(() => coordination.value.length)

const sectionHelp: Record<string, {
  inline: string[]
  summary: string
  bullets: string[]
  example: string
  decisionOwner: string
}> = {
  notes: {
    inline: [
      'Capture the business or governance reasons behind this service split.',
      'These notes should explain why the design exists, not repeat the service inventory.',
    ],
    summary: 'This section records the rationale behind the service decomposition so later implementation and conformance work can be judged against explicit intent.',
    bullets: [
      'Explain why work is split across services instead of remaining in one boundary.',
      'Call out where governance must remain service-owned rather than orchestration-owned.',
      'Record tradeoffs or constraints that developers should preserve during generation and refinement.',
    ],
    example: 'Keep approvals and actor policy in the business services so compound flows do not silently widen authority.',
    decisionOwner: 'Usually the architect or senior developer, with PM input when the split changes product scope.',
  },
  services: {
    inline: [
      'Define what each service owns and which capabilities it is responsible for exposing.',
      'Capability ownership here should line up with later generated services and observed metadata.',
    ],
    summary: 'This is the core service boundary record. It should tell Studio which business capabilities and concepts belong to each service.',
    bullets: [
      'Use responsibilities to describe business responsibility, not infrastructure detail.',
      'Keep exact capability IDs visible so later code generation and conformance checks have a stable target.',
      'Owned concepts should identify which service protects the meaning and policy around a concept.',
    ],
    example: 'A Reporting Service owns forecast, bottleneck, and review-summary capabilities because those remain part of the same business-state review.',
    decisionOwner: 'Usually the architect or design lead, with PM review when the split changes user-facing product scope.',
  },
  coordination: {
    inline: [
      'Describe bounded handoffs or verification steps between services.',
      'This is where you explain compound ANIP flows without hiding them in prompts.',
    ],
    summary: 'Coordination records how work is allowed to move between services once the system is live.',
    bullets: [
      'Use handoff when one service intentionally provides the bounded next step for another.',
      'Use verification when one service checks or enriches context before the next service proceeds.',
      'Avoid vague orchestration language; record only the bounded cross-service behavior you expect to preserve.',
    ],
    example: 'Pipeline reads identify the bounded account set that enrichment should explain next.',
    decisionOwner: 'Usually the architect or developer design owner.',
  },
  concepts: {
    inline: [
      'Domain concepts are the business nouns each service owns and protects.',
      'Sensitivity and risk notes explain where masking, restrictions, or approval posture may matter later.',
    ],
    summary: 'This section defines the shared business concepts that anchor the service design and later ANIP semantics.',
    bullets: [
      'The owner field should identify which service is authoritative for that concept.',
      'Sensitivity should reflect the business risk of mishandling the concept, not generic data classification jargon.',
      'Risk notes help downstream developers preserve the right control boundaries in generated or refined code.',
    ],
    example: 'Assignment Preview is high sensitivity because changing work allocation must not bypass approval posture.',
    decisionOwner: 'Usually the architect with security, governance, or PM input where business sensitivity matters.',
  },
  expectations: {
    inline: [
      'These expectations are derived from the design and linked requirements.',
      'They show what ANIP behavior Studio believes should emerge once the service design is implemented.',
    ],
    summary: 'This section connects the service design draft to the ANIP contract and conformance story.',
    bullets: [
      'Derived expectations should explain what later generated services and observed metadata are expected to show.',
      'Use this section to check whether the design is rich enough to drive meaningful verification.',
      'If nothing is derived here, the design or requirements are probably still too weak.',
    ],
    example: 'A design with coordination edges between services should derive cross-service continuity and handoff expectations.',
    decisionOwner: 'Studio derives these automatically; the design owner uses them to judge whether the draft is specific enough.',
  },
}

const pageRoleCards = [
  {
    label: 'Page Role',
    value: 'Author + Review',
    detail: 'This page is the saved Service Design authoring surface. Product owners and architects can review the shape while developers preserve it downstream.',
  },
  {
    label: 'Saved Design Data',
    value: 'Services, capabilities, coordination, and domain concepts',
    detail: 'These fields are authored here and saved into the Service Design artifact before Developer Design locks a baseline.',
  },
  {
    label: 'Derived Analysis',
    value: 'What ANIP Should Expose',
    detail: 'Studio derives this from the saved Service Design and linked requirements. It is not authored directly.',
  },
]

const sectionSourceMeta: Record<string, { label: string; tone: 'authored' | 'snapshot' | 'derived'; detail: string }> = {
  notes: {
    label: 'Authored Here',
    tone: 'authored',
    detail: 'This section is edited on this page and saved back into the Service Design artifact.',
  },
  services: {
    label: 'Authored Here',
    tone: 'authored',
    detail: 'This section defines service boundaries, service-owned capabilities, and the concept ids each service owns.',
  },
  coordination: {
    label: 'Authored Here',
    tone: 'authored',
    detail: 'This section defines bounded service-to-service handoffs that Developer Design must preserve.',
  },
  concepts: {
    label: 'Authored Here',
    tone: 'authored',
    detail: 'This section defines the business concepts each service owns and the sensitivity/risk posture developers must preserve.',
  },
  expectations: {
    label: 'Derived',
    tone: 'derived',
    detail: 'Studio derives this section automatically from the saved Service Design artifact and linked requirements. It is not authored directly anywhere.',
  },
}

const serviceDesignEditPath = computed(() => `/design/projects/${projectId.value}/shapes`)

function openServiceDesignAuthoring() {
  if (readOnlyMode.value) return
  router.push(serviceDesignEditPath.value)
}

const activeHelp = computed(() => (helpDialogSection.value ? sectionHelp[helpDialogSection.value] ?? null : null))

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

function humanizeIdentifier(value: string): string {
  return value
    .replace(/^svc-/, '')
    .replace(/^concept-/, '')
    .replace(/[_\-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

function capabilityLabel(capability: string): string {
  return humanizeIdentifier(capability)
}

function expectationLabel(surface: string): string {
  return humanizeIdentifier(surface)
}

async function handleExplainShape(question: string) {
  if (readOnlyMode.value || !projectId.value || !shapeId.value) return
  assistantLoading.value = true
  assistantError.value = null
  try {
    assistantExplanation.value = await explainShapeWithAssistant(projectId.value, shapeId.value, question)
  } catch (err) {
    assistantError.value = err instanceof Error ? err.message : String(err)
  } finally {
    assistantLoading.value = false
  }
}
</script>

<template>
  <div class="shape-view">
    <div v-if="loading && !shape" class="loading-state">Loading shape...</div>

    <template v-if="shape && shapeData">
      <!-- Header -->
      <div class="shape-header">
        <div class="header-top">
          <button class="back-link" @click="router.push(`/design/projects/${projectId}/shapes`)">
            &larr; Back to Service Design
          </button>
        </div>
        <div class="page-kicker">Service Design Draft</div>
        <div class="title-row">
          <h1 class="page-title">{{ shapeData.name || shape.title }}</h1>
          <span class="type-badge" :class="'type-' + shapeData.type">
            {{ shapeData.type === 'single_service' ? 'One Service' : 'Multiple Services' }}
          </span>
          <span class="status-badge" :class="'status-' + shape.status">{{ shape.status }}</span>
        </div>
        <div class="shape-meta">
          <span class="meta-date">Updated {{ formatDate(shape.updated_at) }}</span>
        </div>
        <p class="shape-intro">
          Record the intended service architecture here: what each service owns, how services coordinate, and what ANIP-visible behavior this design should imply before implementation is compared against it.
        </p>
        <div class="page-source-banner">
          <strong>This page is the manual Service Design authoring surface.</strong>
          <span>
            Define service boundaries, capability ownership, coordination, and domain concepts here before locking the Developer baseline.
            Developer Design consumes this saved shape deterministically; it should not infer the topology from generic placeholders.
          </span>
        </div>
        <section class="page-role-grid">
          <article v-for="card in pageRoleCards" :key="card.label" class="page-role-card">
            <span class="page-role-label">{{ card.label }}</span>
            <strong>{{ card.value }}</strong>
            <p>{{ card.detail }}</p>
          </article>
        </section>
        <div v-if="artifactIsLockedForDevelopment" class="revision-banner locked">
          Locked for development. Saving changes will create a new working revision instead of modifying the locked baseline service design.
        </div>
        <div v-else-if="artifactIsWorkingRevision" class="revision-banner working">
          Working revision. This service design is newer than the current locked developer baseline.
        </div>
        <div v-if="readOnlyMode" class="readonly-banner">
          {{ readOnlyReason }}
        </div>
      </div>

      <section class="info-grid">
        <article class="info-card">
          <h2>Design scope</h2>
          <div class="summary-row">
            <span class="summary-label">Linked What Matters</span>
            <strong>{{ linkedRequirements?.title || 'Not linked yet' }}</strong>
          </div>
          <div class="summary-row">
            <span class="summary-label">Delivery shape</span>
            <strong>{{ shapeData.type === 'single_service' ? 'One Service' : 'Multiple Coordinated Services' }}</strong>
          </div>
          <div class="summary-row">
            <span class="summary-label">Current draft</span>
            <strong>{{ serviceCount }} service{{ serviceCount === 1 ? '' : 's' }} · {{ coordinationCount }} coordination link{{ coordinationCount === 1 ? '' : 's' }}</strong>
          </div>
        </article>
        <article class="info-card">
          <h2>What belongs here</h2>
          <ul>
            <li>Service boundaries and capability ownership.</li>
            <li>Which concepts each service owns and protects.</li>
            <li>How work crosses boundaries through bounded handoffs or follow-up steps.</li>
            <li>What ANIP semantics should be visible once the design is implemented.</li>
          </ul>
        </article>
      </section>

      <section class="linkage-grid">
        <article class="linkage-card">
          <div class="linkage-kicker">Feeds Developer Design</div>
          <h2>Use this draft to drive generated service design</h2>
          <p>
            This draft should inform the downstream Developer Design surfaces that eventually shape generated ANIP services.
          </p>
          <div class="button-row">
            <button class="btn btn-secondary btn-sm" @click="router.push(`/design/projects/${projectId}/developer/service-formalization`)">Open Service Formalization</button>
            <button class="btn btn-secondary btn-sm" @click="router.push(`/design/projects/${projectId}/developer/data-contract-formalization`)">Open Data Contract Formalization</button>
          </div>
        </article>
        <article class="linkage-card">
          <div class="linkage-kicker">Feeds Verification</div>
          <h2>Use this draft to compare intent against observation</h2>
          <p>
            Observed services: <strong>{{ observedServicesCount }}</strong>. Use Verification and Discovery to compare this intended design against live ANIP metadata.
          </p>
          <div class="button-row">
            <button class="btn btn-secondary btn-sm" @click="router.push(`/design/projects/${projectId}/verification`)">Open Verification</button>
            <button class="btn btn-secondary btn-sm" @click="router.push('/inspect/discovery')">Open Discovery</button>
          </div>
        </article>
      </section>

      <StudioAssistantPanel
        title="Explain This Design"
        description="Ask Studio to explain what this shape is optimizing for, which ANIP semantics it expects to expose, and what looks weak or incomplete."
        button-label="Explain This Design"
        :explanation="assistantExplanation"
        :loading="assistantLoading"
        :error="assistantError"
        :readOnly="readOnlyMode"
        :readOnlyReason="readOnlyReason"
        @run="handleExplainShape"
      />

      <!-- Editor toolbar -->
      <div class="toolbar" v-if="isEditing">
        <button class="btn btn-primary" :disabled="saving" @click="handleSave">
          {{ saving ? 'Saving...' : 'Save Changes' }}
        </button>
        <span v-if="saveError" class="save-error">{{ saveError }}</span>
      </div>

      <section v-if="isEditing" class="shape-section authoring-section">
        <div class="section-header">
          <div>
            <h2 class="section-title">Service Design Basics</h2>
            <p class="section-desc">Name the architecture and choose whether this Product Design expects one service or multiple coordinated services.</p>
          </div>
        </div>
        <div class="authoring-grid two-col">
          <label class="editor-field">
            <span>Design name</span>
            <input class="editor-input" :value="shapeData.name" @input="updateShapeField('name', ($event.target as HTMLInputElement).value)" />
          </label>
          <label class="editor-field">
            <span>Delivery shape</span>
            <select class="editor-input" :value="shapeData.type" @change="updateShapeField('type', ($event.target as HTMLSelectElement).value)">
              <option value="single_service">One service</option>
              <option value="multi_service">Multiple coordinated services</option>
            </select>
          </label>
        </div>
      </section>

      <!-- Notes -->
      <section class="shape-section">
        <div class="section-header">
          <div class="section-title-row">
            <h2 class="section-title">Why This Design</h2>
            <span class="section-source-chip" :class="`tone-${sectionSourceMeta.notes.tone}`">{{ sectionSourceMeta.notes.label }}</span>
          </div>
          <div class="section-help-actions">
            <button class="help-link" type="button" @click="inlineHelpSection = inlineHelpSection === 'notes' ? null : 'notes'">
              {{ inlineHelpSection === 'notes' ? 'Hide help' : 'What does this mean?' }}
            </button>
            <button class="help-link secondary" type="button" @click="helpDialogSection = 'notes'">More detail</button>
          </div>
        </div>
        <p class="section-source-detail">{{ sectionSourceMeta.notes.detail }}</p>
        <div v-if="inlineHelpSection === 'notes'" class="inline-help">
          <ul class="inline-help-list">
            <li v-for="detail in sectionHelp.notes.inline" :key="detail">{{ detail }}</li>
          </ul>
        </div>
        <div v-if="shapeData.notes && shapeData.notes.length > 0" class="notes-list">
          <div v-for="(note, i) in shapeData.notes" :key="i" class="note-item">
            <template v-if="isEditing">
              <textarea
                class="note-input"
                :value="note"
                rows="3"
                @input="updateNote(i, ($event.target as HTMLTextAreaElement).value)"
                placeholder="Design rationale..."
              ></textarea>
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
        <div class="section-header">
          <div class="section-title-row">
            <h2 class="section-title">Service Responsibilities ({{ services.length }})</h2>
            <span class="section-source-chip" :class="`tone-${sectionSourceMeta.services.tone}`">{{ sectionSourceMeta.services.label }}</span>
          </div>
          <div class="section-help-actions">
            <button class="help-link" type="button" @click="inlineHelpSection = inlineHelpSection === 'services' ? null : 'services'">
              {{ inlineHelpSection === 'services' ? 'Hide help' : 'What does this mean?' }}
            </button>
            <button class="help-link secondary" type="button" @click="helpDialogSection = 'services'">More detail</button>
          </div>
        </div>
        <p class="section-source-detail">{{ sectionSourceMeta.services.detail }}</p>
        <div class="section-origin-callout">
          <strong>Source of truth:</strong> saved Service Design artifact.
          <span>Edit services, capability ownership, and owned concepts from the Service Design authoring surface.</span>
          <button class="section-action-link" type="button" :disabled="readOnlyMode" @click="openServiceDesignAuthoring">Edit Service Design</button>
        </div>
        <div v-if="inlineHelpSection === 'services'" class="inline-help">
          <ul class="inline-help-list">
            <li v-for="detail in sectionHelp.services.inline" :key="detail">{{ detail }}</li>
          </ul>
        </div>
        <div v-if="services.length === 0" class="empty-hint">No services defined yet. Start by naming the service or service estate you want to shape.</div>
        <div v-for="(svc, serviceIndex) in services" :key="svc.id" class="service-card">
          <div class="service-header">
            <template v-if="isEditing">
              <label class="editor-field compact">
                <span>Service id</span>
                <input class="editor-input mono" :value="svc.id" @input="updateServiceField(serviceIndex, 'id', ($event.target as HTMLInputElement).value)" />
              </label>
              <label class="editor-field">
                <span>Service name</span>
                <input class="editor-input" :value="svc.name" @input="updateServiceField(serviceIndex, 'name', ($event.target as HTMLInputElement).value)" />
              </label>
              <label class="editor-field">
                <span>Role</span>
                <input class="editor-input" :value="svc.role" @input="updateServiceField(serviceIndex, 'role', ($event.target as HTMLInputElement).value)" />
              </label>
              <button class="remove-btn large" type="button" title="Remove service" @click="removeService(serviceIndex)">&times;</button>
            </template>
            <template v-else>
              <span class="service-name">{{ svc.name }}</span>
              <span class="service-role">{{ svc.role }}</span>
            </template>
          </div>
          <template v-if="isEditing">
            <div class="authoring-grid three-col">
              <label class="editor-field">
                <span>Responsibilities</span>
                <textarea class="editor-input textarea" rows="5" :value="joinLines(svc.responsibilities)" @input="updateServiceList(serviceIndex, 'responsibilities', ($event.target as HTMLTextAreaElement).value)" placeholder="One responsibility per line"></textarea>
              </label>
              <label class="editor-field">
                <span>Capability ids</span>
                <textarea class="editor-input textarea mono" rows="5" :value="joinLines(svc.capabilities)" @input="updateServiceList(serviceIndex, 'capabilities', ($event.target as HTMLTextAreaElement).value)" placeholder="gtm.pipeline_summary"></textarea>
              </label>
              <label class="editor-field">
                <span>Owned concept ids</span>
                <textarea class="editor-input textarea mono" rows="5" :value="joinLines(svc.owns_concepts)" @input="updateServiceList(serviceIndex, 'owns_concepts', ($event.target as HTMLTextAreaElement).value)" placeholder="pipeline_snapshot"></textarea>
              </label>
            </div>
          </template>
          <div v-if="svc.responsibilities && svc.responsibilities.length" class="service-detail">
            <span class="detail-label">Responsibilities</span>
            <ul class="detail-list">
              <li v-for="(r, i) in svc.responsibilities" :key="i">{{ r }}</li>
            </ul>
          </div>
          <div v-if="svc.capabilities && svc.capabilities.length" class="service-detail">
            <span class="detail-label">Capabilities</span>
            <ul class="detail-list">
              <li v-for="(c, i) in svc.capabilities" :key="i" class="capability-item">
                <span class="capability-label">{{ capabilityLabel(c) }}</span>
                <code class="capability-id">{{ c }}</code>
              </li>
            </ul>
          </div>
          <div v-if="svc.owns_concepts && svc.owns_concepts.length" class="service-detail">
            <span class="detail-label">Owned Concepts</span>
            <div class="concept-pills">
              <span v-for="(c, i) in svc.owns_concepts" :key="i" class="concept-pill">{{ c }}</span>
            </div>
          </div>
        </div>
        <button v-if="isEditing" class="btn btn-secondary btn-sm" type="button" @click="addService">+ Add Service</button>
      </section>

      <!-- Coordination -->
      <section class="shape-section" v-if="isEditing || coordination.length > 0">
        <div class="section-header">
          <div class="section-title-row">
            <h2 class="section-title">How Services Coordinate ({{ coordination.length }})</h2>
            <span class="section-source-chip" :class="`tone-${sectionSourceMeta.coordination.tone}`">{{ sectionSourceMeta.coordination.label }}</span>
          </div>
          <div class="section-help-actions">
            <button class="help-link" type="button" @click="inlineHelpSection = inlineHelpSection === 'coordination' ? null : 'coordination'">
              {{ inlineHelpSection === 'coordination' ? 'Hide help' : 'What does this mean?' }}
            </button>
            <button class="help-link secondary" type="button" @click="helpDialogSection = 'coordination'">More detail</button>
          </div>
        </div>
        <p class="section-source-detail">{{ sectionSourceMeta.coordination.detail }}</p>
        <div class="section-origin-callout">
          <strong>Source of truth:</strong> saved Service Design artifact.
          <span>This coordination list is not generated. It comes from the authored Service Design and is shown here for review.</span>
          <button class="section-action-link" type="button" :disabled="readOnlyMode" @click="openServiceDesignAuthoring">Edit Service Design</button>
        </div>
        <div v-if="inlineHelpSection === 'coordination'" class="inline-help">
          <ul class="inline-help-list">
            <li v-for="detail in sectionHelp.coordination.inline" :key="detail">{{ detail }}</li>
          </ul>
        </div>
        <p class="section-desc">Record bounded service-to-service handoffs that Product Design expects Developer Design to preserve.</p>
        <div class="coordination-list">
          <div v-for="(edge, i) in coordination" :key="i" class="coordination-edge">
            <template v-if="isEditing">
              <label class="editor-field compact">
                <span>From</span>
                <select class="editor-input" :value="edge.from" @change="updateCoordination(i, 'from', ($event.target as HTMLSelectElement).value)">
                  <option v-for="svc in services" :key="svc.id" :value="svc.id">{{ svc.name }} ({{ svc.id }})</option>
                </select>
              </label>
              <label class="editor-field compact">
                <span>To</span>
                <select class="editor-input" :value="edge.to" @change="updateCoordination(i, 'to', ($event.target as HTMLSelectElement).value)">
                  <option v-for="svc in services" :key="svc.id" :value="svc.id">{{ svc.name }} ({{ svc.id }})</option>
                </select>
              </label>
              <label class="editor-field compact">
                <span>Relationship</span>
                <select class="editor-input" :value="edge.relationship" @change="updateCoordination(i, 'relationship', ($event.target as HTMLSelectElement).value)">
                  <option value="handoff">Handoff</option>
                  <option value="verification">Verification</option>
                  <option value="async_followup">Async follow-up</option>
                </select>
              </label>
              <label class="editor-field wide">
                <span>Description</span>
                <input class="editor-input" :value="edge.description || ''" @input="updateCoordination(i, 'description', ($event.target as HTMLInputElement).value)" />
              </label>
              <button class="remove-btn large" type="button" title="Remove coordination edge" @click="removeCoordination(i)">&times;</button>
            </template>
            <template v-else>
              <span class="edge-from">{{ edge.from }}</span>
              <span class="edge-arrow">&rarr;</span>
              <span class="edge-to">{{ edge.to }}</span>
              <span class="edge-relationship" :class="'rel-' + edge.relationship">
                {{ relationshipLabel(edge.relationship) }}
              </span>
              <span v-if="edge.description" class="edge-desc">{{ edge.description }}</span>
            </template>
          </div>
        </div>
        <button v-if="isEditing" class="btn btn-secondary btn-sm" type="button" @click="addCoordination">+ Add Coordination</button>
      </section>

      <!-- Domain Concepts -->
      <section class="shape-section" v-if="isEditing || domainConcepts.length > 0">
        <div class="section-header">
          <div class="section-title-row">
            <h2 class="section-title">Domain Concepts ({{ domainConcepts.length }})</h2>
            <span class="section-source-chip" :class="`tone-${sectionSourceMeta.concepts.tone}`">{{ sectionSourceMeta.concepts.label }}</span>
          </div>
          <div class="section-help-actions">
            <button class="help-link" type="button" @click="inlineHelpSection = inlineHelpSection === 'concepts' ? null : 'concepts'">
              {{ inlineHelpSection === 'concepts' ? 'Hide help' : 'What does this mean?' }}
            </button>
            <button class="help-link secondary" type="button" @click="helpDialogSection = 'concepts'">More detail</button>
          </div>
        </div>
        <p class="section-source-detail">{{ sectionSourceMeta.concepts.detail }}</p>
        <div class="section-origin-callout">
          <strong>Source of truth:</strong> saved Service Design artifact.
          <span>These domain concepts are authored in this Service Design, then consumed by Developer Design as saved product intent.</span>
          <button class="section-action-link" type="button" :disabled="readOnlyMode" @click="openServiceDesignAuthoring">Edit Service Design</button>
        </div>
        <div v-if="inlineHelpSection === 'concepts'" class="inline-help">
          <ul class="inline-help-list">
            <li v-for="detail in sectionHelp.concepts.inline" :key="detail">{{ detail }}</li>
          </ul>
        </div>
        <div v-if="isEditing" class="concept-editor-list">
          <article v-for="(concept, conceptIndex) in domainConcepts" :key="concept.id" class="concept-editor-card">
            <div class="authoring-grid three-col">
              <label class="editor-field compact">
                <span>Concept id</span>
                <input class="editor-input mono" :value="concept.id" @input="updateDomainConcept(conceptIndex, 'id', ($event.target as HTMLInputElement).value)" />
              </label>
              <label class="editor-field">
                <span>Name</span>
                <input class="editor-input" :value="concept.name" @input="updateDomainConcept(conceptIndex, 'name', ($event.target as HTMLInputElement).value)" />
              </label>
              <label class="editor-field">
                <span>Owner</span>
                <select class="editor-input" :value="concept.owner || ''" @change="updateDomainConcept(conceptIndex, 'owner', ($event.target as HTMLSelectElement).value)">
                  <option value="">Unassigned</option>
                  <option v-for="svc in services" :key="svc.id" :value="svc.id">{{ svc.name }} ({{ svc.id }})</option>
                </select>
              </label>
              <label class="editor-field wide">
                <span>Meaning</span>
                <textarea class="editor-input textarea" rows="3" :value="concept.meaning" @input="updateDomainConcept(conceptIndex, 'meaning', ($event.target as HTMLTextAreaElement).value)"></textarea>
              </label>
              <label class="editor-field compact">
                <span>Sensitivity</span>
                <select class="editor-input" :value="concept.sensitivity || 'none'" @change="updateDomainConcept(conceptIndex, 'sensitivity', ($event.target as HTMLSelectElement).value)">
                  <option value="none">None</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                </select>
              </label>
              <label class="editor-field wide">
                <span>Risk note</span>
                <textarea class="editor-input textarea" rows="3" :value="concept.risk_note || ''" @input="updateDomainConcept(conceptIndex, 'risk_note', ($event.target as HTMLTextAreaElement).value)"></textarea>
              </label>
              <button class="remove-btn large" type="button" title="Remove concept" @click="removeDomainConcept(conceptIndex)">&times;</button>
            </div>
          </article>
          <button class="btn btn-secondary btn-sm" type="button" @click="addDomainConcept">+ Add Domain Concept</button>
        </div>
        <table v-else class="concepts-table">
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
        <div class="section-header">
          <div class="section-title-row">
            <h2 class="section-title">What ANIP Should Expose</h2>
            <span class="section-source-chip" :class="`tone-${sectionSourceMeta.expectations.tone}`">{{ sectionSourceMeta.expectations.label }}</span>
          </div>
          <div class="section-help-actions">
            <button class="help-link" type="button" @click="inlineHelpSection = inlineHelpSection === 'expectations' ? null : 'expectations'">
              {{ inlineHelpSection === 'expectations' ? 'Hide help' : 'What does this mean?' }}
            </button>
            <button class="help-link secondary" type="button" @click="helpDialogSection = 'expectations'">More detail</button>
          </div>
        </div>
        <p class="section-source-detail">{{ sectionSourceMeta.expectations.detail }}</p>
        <div class="section-origin-callout derived">
          <strong>Source of truth:</strong> automatic derivation.
          <span>Studio computes this from the saved Service Design plus linked requirements. To change it, change the saved design or requirements, not this section directly.</span>
        </div>
        <div v-if="inlineHelpSection === 'expectations'" class="inline-help">
          <ul class="inline-help-list">
            <li v-for="detail in sectionHelp.expectations.inline" :key="detail">{{ detail }}</li>
          </ul>
        </div>
        <p class="section-desc">These ANIP semantics are implied by this shape and its linked requirements. They are derived from the design rather than authored directly.</p>
        <div v-if="expectationsLoading" class="loading-hint">Loading expectations...</div>
        <div v-else-if="expectations.length === 0" class="empty-hint">
          No expectations were derived yet. This usually means the shape or requirements are still too incomplete to evaluate confidently.
        </div>
        <div v-else class="expectations-list">
          <div v-for="(exp, i) in expectations" :key="i" class="expectation-item">
            <span class="expectation-surface">
              <span class="expectation-label">{{ expectationLabel(exp.surface) }}</span>
              <code class="expectation-id">{{ exp.surface }}</code>
            </span>
            <span class="expectation-reason">{{ exp.reason }}</span>
          </div>
        </div>
      </section>
    </template>

    <div v-else-if="!loading" class="not-found">Shape not found.</div>

    <div v-if="activeHelp" class="help-dialog-backdrop" @click.self="helpDialogSection = null">
      <div class="help-dialog">
        <div class="help-dialog-header">
          <h3 class="help-dialog-title">{{ activeHelp.summary ? 'Service Design Guidance' : 'Detail' }}</h3>
          <button class="help-dialog-close" type="button" @click="helpDialogSection = null">Close</button>
        </div>
        <p class="help-dialog-summary">{{ activeHelp.summary }}</p>
        <ul class="help-dialog-list">
          <li v-for="item in activeHelp.bullets" :key="item">{{ item }}</li>
        </ul>
        <div class="help-dialog-block">
          <span class="help-dialog-label">Example</span>
          <p class="help-dialog-text">{{ activeHelp.example }}</p>
        </div>
        <div class="help-dialog-block">
          <span class="help-dialog-label">Who usually decides this?</span>
          <p class="help-dialog-text">{{ activeHelp.decisionOwner }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.shape-view {
  padding: 2rem;
  width: 100%;
  max-width: none;
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
  margin-bottom: 1.75rem;
}

.header-top {
  margin-bottom: 0.35rem;
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

.page-kicker {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 0.45rem;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.page-title {
  font-size: 28px;
  line-height: 1.15;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}

.type-badge {
  display: inline-flex;
  align-items: center;
  font-size: 11px;
  font-weight: 700;
  padding: 0.22rem 0.6rem;
  border-radius: 999px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border: 1px solid transparent;
}

.type-single_service {
  background: rgba(59, 130, 246, 0.15);
  border-color: rgba(96, 165, 250, 0.28);
  color: #bfdbfe;
}

.type-multi_service {
  background: rgba(168, 85, 247, 0.15);
  border-color: rgba(168, 85, 247, 0.28);
  color: #d8b4fe;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  font-size: 11px;
  font-weight: 700;
  padding: 0.22rem 0.6rem;
  border-radius: 999px;
  text-transform: capitalize;
  background: rgba(148, 163, 184, 0.14);
  color: var(--text-muted);
  border: 1px solid var(--surface-border-card);
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
  margin-top: 0.55rem;
}

.meta-date {
  font-size: 12px;
  color: var(--text-muted);
}

.shape-intro {
  margin: 0.9rem 0 0;
  max-width: 84rem;
  color: var(--text-secondary);
  line-height: 1.6;
}

.page-source-banner {
  margin-top: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  padding: 1rem 1.15rem;
  border-radius: 18px;
  border: 1px solid rgba(96, 165, 250, 0.24);
  background:
    radial-gradient(circle at top left, rgba(59, 130, 246, 0.12), transparent 36%),
    rgba(15, 23, 42, 0.52);
  color: var(--text-secondary);
  max-width: 84rem;
}

.page-source-banner strong {
  color: #dbeafe;
  font-size: 13px;
}

.section-origin-callout {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.55rem;
  margin: 0.95rem 0 1.1rem;
  padding: 0.85rem 0.95rem;
  border-radius: 14px;
  border: 1px solid var(--surface-border-card);
  background: var(--surface-depth-card);
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.5;
}

.section-origin-callout strong {
  color: var(--text-primary);
}

.section-origin-callout.derived {
  border-color: rgba(96, 165, 250, 0.2);
  background: var(--surface-depth-card);
}

.section-action-link {
  margin-left: auto;
  background: transparent;
  border: 1px solid rgba(96, 165, 250, 0.28);
  color: #bfdbfe;
  border-radius: 999px;
  padding: 0.35rem 0.75rem;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background var(--transition), border-color var(--transition), color var(--transition);
}

.section-action-link:hover:not(:disabled) {
  background: rgba(30, 64, 175, 0.22);
  border-color: rgba(147, 197, 253, 0.48);
  color: #dbeafe;
}

.section-action-link:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.page-role-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0.85rem;
  margin-top: 1.05rem;
}

.page-role-card {
  background:
    linear-gradient(180deg, rgba(15, 23, 42, 0.6), rgba(15, 23, 42, 0.42));
  border: 1px solid var(--surface-border-card);
  border-radius: 18px;
  padding: 1rem 1.05rem;
}

.page-role-label {
  display: block;
  margin-bottom: 0.25rem;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.page-role-card strong {
  display: block;
  color: var(--text-primary);
  font-size: 15px;
  line-height: 1.35;
}

.page-role-card p {
  margin: 0.45rem 0 0;
  font-size: 13px;
  line-height: 1.5;
  color: var(--text-secondary);
}

.revision-banner {
  margin-top: 1rem;
  padding: 0.9rem 1rem;
  border-radius: 14px;
  font-size: 14px;
  line-height: 1.5;
}

.revision-banner.locked {
  background: rgba(251, 191, 36, 0.12);
  border: 1px solid rgba(251, 191, 36, 0.32);
  color: #fde68a;
}

.revision-banner.working {
  background: rgba(59, 130, 246, 0.12);
  border: 1px solid rgba(96, 165, 250, 0.32);
  color: #bfdbfe;
}

.readonly-banner {
  margin-top: 1rem;
  padding: 0.9rem 1rem;
  border-radius: 14px;
  border: 1px solid rgba(251, 191, 36, 0.28);
  background: rgba(251, 191, 36, 0.12);
  color: #fbbf24;
  font-size: 14px;
  line-height: 1.5;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
  margin-bottom: 1.35rem;
}

.linkage-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
  margin-bottom: 1.35rem;
}

.info-card,
.linkage-card {
  background: var(--surface-depth-card);
  border: 1px solid var(--surface-border-card);
  border-radius: 20px;
  padding: 1.25rem;
}

.info-card h2 {
  margin: 0 0 1rem;
  font-size: 17px;
}

.info-card ul {
  margin: 0;
  padding-left: 1.1rem;
  color: var(--text-secondary);
  line-height: 1.55;
}

.summary-row + .summary-row {
  margin-top: 0.85rem;
}

.summary-label {
  display: block;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: 0.2rem;
}

.summary-row strong {
  color: var(--text-primary);
  font-size: 15px;
  line-height: 1.35;
}

.linkage-kicker {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 0.45rem;
}

.linkage-card h2 {
  margin: 0 0 0.65rem;
  font-size: 18px;
}

.linkage-card p {
  margin: 0 0 0.9rem;
  color: var(--text-secondary);
  line-height: 1.55;
}

.button-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.7rem;
  margin-top: 1rem;
}

/* Toolbar */
.toolbar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1.5rem;
}

.save-error {
  font-size: 13px;
  color: var(--error);
}

/* Buttons */
.btn {
  min-height: 38px;
  padding: 0.62rem 0.95rem;
  border: 1px solid var(--surface-border-card);
  border-radius: 12px;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition: background var(--transition), border-color var(--transition), color var(--transition);
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
  background: var(--surface-depth-card);
  color: #dbeafe;
  border-color: rgba(96, 165, 250, 0.24);
}

.btn-secondary:hover:not(:disabled) {
  background: rgba(30, 64, 175, 0.22);
  border-color: rgba(147, 197, 253, 0.42);
  color: var(--text-primary);
}

.btn-sm {
  min-height: 32px;
  padding: 0.48rem 0.75rem;
  font-size: 12px;
}

/* Sections */
.shape-section {
  margin-bottom: 1.35rem;
  background: var(--surface-depth-card);
  border: 1px solid var(--surface-border-card);
  border-radius: 20px;
  padding: 1.3rem;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1.25rem;
  margin-bottom: 0.7rem;
}

.section-title-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.section-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}

.section-source-chip {
  display: inline-flex;
  align-items: center;
  padding: 3px 8px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  border: 1px solid transparent;
}

.section-source-chip.tone-authored {
  background: rgba(52, 211, 153, 0.12);
  border-color: rgba(52, 211, 153, 0.28);
  color: #86efac;
}

.section-source-chip.tone-snapshot {
  background: rgba(96, 165, 250, 0.12);
  border-color: rgba(96, 165, 250, 0.28);
  color: #bfdbfe;
}

.section-source-chip.tone-derived {
  background: rgba(251, 191, 36, 0.12);
  border-color: rgba(251, 191, 36, 0.28);
  color: #fde68a;
}

.section-source-detail {
  margin: 0.15rem 0 0.9rem;
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.5;
}

.section-help-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.help-link {
  border: none;
  background: transparent;
  color: var(--accent, #8b8cff);
  font-size: 12px;
  font-weight: 600;
  padding: 0;
  cursor: pointer;
}

.help-link.secondary {
  color: var(--text-muted);
}

.inline-help {
  margin: 0 0 1rem;
  padding: 0.85rem 0.95rem;
  border-radius: 14px;
  background: rgba(96, 165, 250, 0.08);
  border: 1px solid rgba(96, 165, 250, 0.18);
}

.inline-help-list {
  margin: 0;
  padding-left: 18px;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.section-desc {
  font-size: 13px;
  color: var(--text-muted);
  margin: 0.15rem 0 0.95rem;
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
  gap: 0.65rem;
  margin-bottom: 0.9rem;
}

.note-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.note-text {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.note-input {
  flex: 1;
  min-height: 76px;
  padding: 10px 12px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 13px;
  outline: none;
  transition: border-color var(--transition);
  line-height: 1.45;
  resize: vertical;
  font-family: inherit;
  box-sizing: border-box;
}

.note-input:focus {
  border-color: var(--border-focus);
}

.authoring-section {
  border-color: rgba(96, 165, 250, 0.26);
  background:
    radial-gradient(circle at top left, rgba(59, 130, 246, 0.08), transparent 34%),
    var(--surface-depth-card);
}

.authoring-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.8rem;
}

.authoring-grid.two-col {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.authoring-grid.three-col {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.editor-field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  min-width: 0;
}

.editor-field span {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted);
}

.editor-field.compact {
  min-width: 180px;
}

.editor-field.wide {
  grid-column: span 2;
}

.editor-input {
  width: 100%;
  min-height: 38px;
  padding: 9px 11px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font: inherit;
  font-size: 13px;
  outline: none;
  box-sizing: border-box;
}

.editor-input:focus {
  border-color: var(--border-focus);
}

.editor-input.textarea {
  min-height: 96px;
  line-height: 1.45;
  resize: vertical;
}

.editor-input.mono {
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 12px;
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

.remove-btn.large {
  width: 32px;
  height: 32px;
  margin-left: auto;
  border: 1px solid rgba(248, 113, 113, 0.18);
}

/* Service cards */
.service-card {
  background:
    linear-gradient(180deg, rgba(15, 23, 42, 0.66), rgba(15, 23, 42, 0.44));
  border: 1px solid var(--surface-border-card);
  border-radius: 18px;
  padding: 1.05rem;
  margin-bottom: 0.85rem;
}

.service-header {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 0.85rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
}

.service-header .editor-field {
  flex: 1 1 220px;
}

.service-name {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}

.service-role {
  font-size: 12px;
  color: #bfdbfe;
  padding: 0.18rem 0.55rem;
  border-radius: 999px;
  border: 1px solid rgba(96, 165, 250, 0.22);
  background: rgba(96, 165, 250, 0.08);
}

.service-detail {
  margin-top: 0.75rem;
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
  line-height: 1.55;
}

.capability-item {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.capability-label {
  color: var(--text-primary);
  font-weight: 500;
}

.capability-id {
  font-size: 12px;
  color: var(--text-muted);
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.concept-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.concept-pill {
  font-size: 11px;
  font-weight: 500;
  padding: 0.22rem 0.55rem;
  border-radius: 999px;
  background: rgba(168, 85, 247, 0.12);
  color: #d8b4fe;
  border: 1px solid rgba(168, 85, 247, 0.25);
}

/* Coordination */
.coordination-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.coordination-edge {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.85rem 0.95rem;
  background: var(--surface-depth-card);
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  flex-wrap: wrap;
}

.coordination-edge .editor-field {
  flex: 1 1 180px;
}

.coordination-edge .editor-field.wide {
  flex: 2 1 340px;
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
  font-weight: 700;
  padding: 0.22rem 0.55rem;
  border-radius: 999px;
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
.concept-editor-list {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.concept-editor-card {
  padding: 1rem;
  border: 1px solid var(--surface-border-card);
  border-radius: 16px;
  background: rgba(15, 23, 42, 0.42);
}

.concepts-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  overflow: hidden;
}

.concepts-table th {
  text-align: left;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted);
  padding: 0.75rem 0.85rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.16);
  background: var(--surface-depth-card);
}

.concepts-table td {
  padding: 0.8rem 0.85rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.1);
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
  background:
    radial-gradient(circle at top left, rgba(251, 191, 36, 0.09), transparent 32%),
    rgba(15, 23, 42, 0.46);
  border: 1px solid var(--surface-border-card);
  border-radius: 20px;
  padding: 1.3rem;
}

.expectations-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.expectation-item {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  padding: 0.85rem 0.95rem;
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  background: var(--surface-depth-card);
}

.expectation-item:last-child {
  border-bottom: 1px solid rgba(148, 163, 184, 0.14);
}

.expectation-surface {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  min-width: 180px;
}

.expectation-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--accent);
}

.expectation-id {
  font-size: 12px;
  color: var(--text-muted);
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.expectation-reason {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.4;
}

.help-dialog-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(10, 10, 15, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  z-index: 200;
}

.help-dialog {
  width: min(720px, 100%);
  max-height: min(80vh, 760px);
  overflow: auto;
  background: var(--bg-panel, #13131d);
  border: 1px solid var(--border);
  border-radius: 12px;
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.35);
  padding: 20px 22px;
}

.help-dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.help-dialog-title {
  margin: 0;
  font-size: 18px;
}

.help-dialog-close {
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-secondary);
  border-radius: 8px;
  padding: 6px 10px;
  cursor: pointer;
}

.help-dialog-summary {
  margin: 0 0 14px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.help-dialog-list {
  margin: 0 0 14px;
  padding-left: 18px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.help-dialog-block + .help-dialog-block {
  margin-top: 14px;
}

.help-dialog-label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted);
  margin-bottom: 6px;
}

.help-dialog-text {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.6;
}

@media (max-width: 900px) {
  .info-grid {
    grid-template-columns: 1fr;
  }

  .linkage-grid {
    grid-template-columns: 1fr;
  }

  .title-row {
    flex-direction: column;
    align-items: flex-start;
  }

  .section-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .expectation-item {
    flex-direction: column;
    gap: 4px;
  }

  .expectation-surface {
    min-width: 0;
  }

  .authoring-grid.two-col,
  .authoring-grid.three-col {
    grid-template-columns: 1fr;
  }

  .editor-field.wide {
    grid-column: auto;
  }
}
</style>
