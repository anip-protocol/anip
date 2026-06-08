<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { designStore, updateDraftField, setRequirementsMode, updateGuidedAnswer, discardEdits } from '../design/store'
import { loadProject, projectStore, openArtifactForEditing, refreshArtifacts } from '../design/project-store'
import {
  createRequirements,
  deleteRequirements,
  setRequirementsRole,
  updateRequirements,
} from '../design/project-api'
import { GUIDED_SECTIONS } from '../design/guided/questions'
import { hydrateAnswersFromArtifact } from '../design/guided/mappings'
import { evaluateCompleteness } from '../design/guided/hints'
import GuidedSection from '../design/components/GuidedSection.vue'
import RequirementsSummary from '../design/components/RequirementsSummary.vue'
import CompletenessHints from '../design/components/CompletenessHints.vue'
import EditorToolbar from '../design/components/EditorToolbar.vue'
import KeyValueEditor from '../design/components/KeyValueEditor.vue'
import { requestConfirmation } from '../design/confirm'
import type {
  DeveloperBaselineData,
} from '../design/project-types'
import { findDeveloperBaselineArtifact } from '../design/traceability'

const route = useRoute()
const router = useRouter()

const projectId = computed(() => route.params.projectId as string)
const requirementsListPath = computed(() => `/design/projects/${projectId.value}/requirements`)

onMounted(() => {
  if (projectId.value && projectStore.activeProject?.id !== projectId.value) {
    loadProject(projectId.value)
  }
})

watch(projectId, (id) => {
  if (id && projectStore.activeProject?.id !== id) {
    loadProject(id)
  }
})

const projectRecord = computed(() => {
  const id = route.params.id as string
  return projectStore.artifacts.requirements.find(r => r.id === id) ?? null
})
const readOnlyMode = computed(() => projectStore.runtimeStatus?.read_only_mode !== false)
const readOnlyReason = computed(() =>
  projectStore.runtimeStatus?.read_only_reason
  || 'Studio is running in read-only mode. Explore the design, then run Studio locally to make changes.',
)

// Hydrate design store when project record changes
watch(projectRecord, (record) => {
  if (record) {
    openArtifactForEditing('requirements', record)
    if (readOnlyMode.value) {
      discardEdits()
    }
  }
}, { immediate: true })

const artifactTitle = ref('')

watch(
  projectRecord,
  (record) => {
    artifactTitle.value = record?.title ?? ''
  },
  { immediate: true },
)

const isEditing = computed(() => designStore.editState === 'draft' && !readOnlyMode.value)

// Display name for the title
const artifactName = computed(() => {
  return artifactTitle.value || projectRecord.value?.title || 'Requirements'
})

const hasData = computed(() => !!projectRecord.value)

// Source data: draft when editing, stored project record otherwise
const req = computed(() => {
  if (isEditing.value && designStore.draftRequirements) {
    return designStore.draftRequirements as Record<string, any>
  }
  return projectRecord.value?.data ?? null
})

const guidedAnswers = computed(() => {
  if (isEditing.value) return designStore.guidedAnswers
  return hydrateAnswersFromArtifact(req.value ?? {})
})

const completenessHints = computed(() => {
  if (isEditing.value) return designStore.completenessHints
  return evaluateCompleteness(req.value ?? {})
})

const transportKeys = computed(() => req.value?.transports ? Object.keys(req.value.transports) : [])
const authKeys = computed(() => req.value?.auth ? Object.keys(req.value.auth) : [])
const permissionKeys = computed(() => req.value?.permissions ? Object.keys(req.value.permissions) : [])
const auditKeys = computed(() => req.value?.audit ? Object.keys(req.value.audit) : [])
const lineageKeys = computed(() => req.value?.lineage ? Object.keys(req.value.lineage) : [])
const businessConstraintKeys = computed(() => req.value?.business_constraints ? Object.keys(req.value.business_constraints) : [])

const riskCapabilities = computed(() => {
  if (!req.value?.risk_profile) return []
  return Object.entries(req.value.risk_profile)
})

const sectionDisplay = {
  transports: {
    title: 'Experience Surfaces',
    copy: 'Which user or system-facing surfaces the product should support. This is product posture, not adapter implementation detail.',
  },
  trust: {
    title: 'Trust and Verification Posture',
    copy: 'The business-level confidence and verification posture the product expects before relying on callers or delegated work.',
  },
  auth: {
    title: 'Identity and Delegation Posture',
    copy: 'How identity, delegation, and scoped authority should behave from a product perspective. Developers formalize the mechanism later.',
  },
  permissions: {
    title: 'Access and Control Boundaries',
    copy: 'Which control behaviors the business expects when work is restricted, denied, discoverable, or approval-gated.',
  },
  audit: {
    title: 'Evidence Retention',
    copy: 'What durable evidence the business expects to keep for review, support, governance, or compliance.',
  },
  lineage: {
    title: 'Execution Traceability',
    copy: 'How clearly the business expects execution chains to be reconstructable later across tasks, invocations, and client references.',
  },
  risk: {
    title: 'Risk Signals',
    copy: 'Important risk signals and sensitivities that shape later developer formalization and verification.',
  },
  businessConstraints: {
    title: 'Operating Constraints',
    copy: 'Product-level boundaries, approval expectations, and failure posture the implementation must respect.',
  },
  scale: {
    title: 'Delivery and Availability',
    copy: 'Business expectations for delivery shape and uptime. Developers decide the technical implementation later.',
  },
} as const

const valueLabelOverrides: Record<string, string> = {
  rest: 'REST / HTTP',
  http: 'HTTP',
  graphql: 'GraphQL',
  grpc: 'gRPC',
  mcp: 'MCP',
  delegation_tokens: 'Delegated Authority',
  scoped_authority: 'Scoped Authority',
  purpose_binding: 'Purpose-Bound Authority',
  service_to_service_handoffs: 'Cross-Service Authority Handoffs',
  preflight_discovery: 'Pre-Action Boundary Discovery',
  grantable_requirements: 'Grantable Restrictions',
  restricted_vs_denied: 'Restricted vs Denied Outcomes',
  durable: 'Durable Records',
  searchable: 'Searchable Records',
  invocation_id: 'Per-Execution Trace IDs',
  task_id: 'Grouped Work Tracking',
  parent_invocation_id: 'Parent-Child Execution Chains',
  client_reference_id: 'External Reference IDs',
  cross_service_reconstruction_required: 'Cross-Service Reconstruction',
  cross_service_continuity_required: 'Cross-Service Continuity',
  shape_preference: 'Delivery Shape',
  high_availability: 'High Availability',
}

const titleDirty = computed(() => (artifactTitle.value.trim() || '') !== (projectRecord.value?.title?.trim() || ''))

const saving = ref(false)
const saveError = ref<string | null>(null)

watch(readOnlyMode, (readOnly) => {
  if (readOnly && designStore.editState === 'draft') {
    discardEdits()
  }
}, { immediate: true })

const baselineArtifact = computed(() => findDeveloperBaselineArtifact(projectStore.artifacts.pmArtifacts))
const baseline = computed(() =>
  (baselineArtifact.value?.data as DeveloperBaselineData | undefined) ?? null,
)
const artifactIsLockedForDevelopment = computed(() =>
  !!baseline.value && baseline.value.source_inputs.requirements_id === projectRecord.value?.id,
)
const artifactIsWorkingRevision = computed(() =>
  !!baseline.value && !artifactIsLockedForDevelopment.value,
)
function humanizeLabel(value: unknown) {
  if (value == null) return ''
  const text = String(value).trim()
  if (!text) return ''
  return text
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .replace(/\b\w/g, (match) => match.toUpperCase())
}

function displayLabel(value: unknown) {
  const key = String(value ?? '').trim()
  if (!key) return ''
  return valueLabelOverrides[key] ?? humanizeLabel(key)
}

function describeDeploymentIntent(value: unknown) {
  const key = String(value ?? '').trim().toLowerCase()
  const descriptions: Record<string, string> = {
    business_source_document: 'As a source business document that drives downstream PM and engineering work.',
    embedded_single_process: 'As an embedded single-process component.',
    production_single_service: 'As a single production service.',
    public_http_service: 'As a public HTTP service.',
    control_plane_worker_split: 'As a control plane with separate worker processes.',
    multi_service_estate: 'As a coordinated multi-service production system.',
    horizontally_scaled: 'As a horizontally scaled production service.',
    testing: 'Primarily for testing and evaluation.',
    production: 'For production use.',
    prod: 'For production use.',
  }
  return descriptions[key] ?? humanizeLabel(value)
}

function renderValue(value: unknown) {
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (typeof value === 'string') return humanizeLabel(value)
  return typeof value === 'object' ? JSON.stringify(value) : value
}

function nextRevisionTitle(title: string): string {
  const trimmed = title.trim() || 'Requirements'
  const match = trimmed.match(/^(.*?)(?:\s+Revision\s+(\d+))?$/i)
  if (!match) return `${trimmed} Revision 2`
  const base = (match[1] || trimmed).trim()
  const current = match[2] ? Number(match[2]) : 1
  return `${base} Revision ${current + 1}`
}

function formatPathLabel(path: string) {
  const stripped = path.replace(/^requirements\/?/, '').replace(/^\//, '')
  if (!stripped) return 'Requirements'
  return stripped
    .split('/')
    .filter(Boolean)
    .map((part) => /^\d+$/.test(part) ? `#${Number(part) + 1}` : displayLabel(part))
    .join(' / ')
}

function formatValidationMessage(path: string, message: string, params?: Record<string, unknown>) {
  const additionalProperty = typeof params?.additionalProperty === 'string' ? params.additionalProperty : ''
  if (additionalProperty) {
    return `${formatPathLabel(path)} has unsupported field "${additionalProperty}".`
  }
  return `${formatPathLabel(path)}: ${message}`
}

function formatSectionValidationMessage(sectionTitle: string, questionPrompt: string | null, message: string) {
  if (questionPrompt) {
    return `Review "${sectionTitle}" -> "${questionPrompt}": ${message}`
  }
  return `Review "${sectionTitle}": ${message}`
}

/**
 * Maps validation errors to guided sections and questions.
 * Returns per-section maps of questionId → error messages,
 * plus unmapped errors for each section and globally.
 */
const errorsBySection = computed(() => {
  const errors = designStore.validationErrors
  const result: Record<string, { questionErrors: Record<string, string[]>; unmappedErrors: string[] }> = {}
  const globalUnmapped: string[] = []

  // Build a lookup: fieldPath → { sectionId, questionId }
  const fieldLookup: Record<string, { sectionId: string; questionId: string; sectionTitle: string; questionPrompt: string }> = {}
  // Also build section-level path prefixes for partial matching
  const sectionPrefixes: { prefix: string; sectionId: string; sectionTitle: string; questionPrompts: string[] }[] = []

  for (const section of GUIDED_SECTIONS) {
    result[section.id] = { questionErrors: {}, unmappedErrors: [] }
    for (const q of section.questions) {
      for (const mapping of q.fieldMappings) {
        // mapping.path is like "system.name", error path is like "requirements/system/name"
        fieldLookup[mapping.path] = {
          sectionId: section.id,
          questionId: q.id,
          sectionTitle: section.title,
          questionPrompt: q.prompt,
        }
      }
    }
  }

  // Build section prefix map from questions' field paths
  for (const section of GUIDED_SECTIONS) {
    const prefixes = new Map<string, string[]>()
    for (const q of section.questions) {
      for (const mapping of q.fieldMappings) {
        const topLevel = mapping.path.split('.')[0]
        const prompts = prefixes.get(topLevel) ?? []
        prompts.push(q.prompt)
        prefixes.set(topLevel, prompts)
      }
    }
    for (const [prefix, prompts] of prefixes.entries()) {
      sectionPrefixes.push({
        prefix,
        sectionId: section.id,
        sectionTitle: section.title,
        questionPrompts: Array.from(new Set(prompts)),
      })
    }
  }

  for (const err of errors) {
    // err.path is like "requirements/system/name" or "requirements/system"
    const stripped = err.path.replace(/^requirements\/?/, '')
    const dotPath = stripped.replace(/\//g, '.')

    // For "required property" errors, construct the full field path
    // e.g. path="requirements/system", message="must have required property 'name'" → "system.name"
    let resolvedPath = dotPath
    const requiredMatch = err.message.match(/must have required property '(\w+)'/)
    if (requiredMatch) {
      const prop = requiredMatch[1]
      resolvedPath = dotPath ? `${dotPath}.${prop}` : prop
    }

    // Try exact match to a question
    const exact = fieldLookup[resolvedPath]
    if (exact) {
      const sec = result[exact.sectionId]
      if (!sec.questionErrors[exact.questionId]) sec.questionErrors[exact.questionId] = []
      sec.questionErrors[exact.questionId].push(err.message)
      continue
    }

    // Try matching to a section by path prefix
    const topLevel = (resolvedPath || dotPath).split('.')[0]
    const sectionMatch = sectionPrefixes.find(sp => sp.prefix === topLevel)
    if (sectionMatch) {
      result[sectionMatch.sectionId].unmappedErrors.push(
        formatSectionValidationMessage(
          sectionMatch.sectionTitle,
          sectionMatch.questionPrompts.length === 1 ? sectionMatch.questionPrompts[0] : null,
          formatValidationMessage(err.path, err.message, err.params),
        ),
      )
      continue
    }

    // Completely unmapped
    globalUnmapped.push(formatValidationMessage(err.path, err.message, err.params))
  }

  return { sections: result, globalUnmapped: Array.from(new Set(globalUnmapped)) }
})

const sectionValidationIssueCount = computed(() =>
  Object.values(errorsBySection.value.sections).reduce((total, section) =>
    total
    + section.unmappedErrors.length
    + Object.values(section.questionErrors).reduce((innerTotal, messages) => innerTotal + messages.length, 0),
  0),
)

const validationIssueSummary = computed(() => {
  const count = designStore.validationErrors.length
  if (count === 0) return 'Requirements structure is valid.'
  const globalCount = errorsBySection.value.globalUnmapped.length
  const sectionCount = sectionValidationIssueCount.value
  if (globalCount > 0 && sectionCount > 0) {
    return `${count} validation issues: ${globalCount} structural and ${sectionCount} section-level.`
  }
  if (globalCount > 0) return `${count} structural validation issue${count === 1 ? '' : 's'} found.`
  return `${count} section-level validation issue${count === 1 ? '' : 's'} found.`
})

// --- Draft helpers ---
function setField(path: string, value: any) {
  if (readOnlyMode.value) return
  updateDraftField('requirements', path, value)
}

function updateGuidedAnswerFromEditor(questionId: string, value: any) {
  if (readOnlyMode.value) return
  updateGuidedAnswer(questionId, value)
}

function toggleTransport(key: string) {
  setField(`transports.${key}`, !req.value?.transports?.[key])
}

function toggleAuth(key: string) {
  setField(`auth.${key}`, !req.value?.auth?.[key])
}

function togglePermission(key: string) {
  setField(`permissions.${key}`, !req.value?.permissions?.[key])
}

function toggleAudit(key: string) {
  setField(`audit.${key}`, !req.value?.audit?.[key])
}

function toggleLineage(key: string) {
  setField(`lineage.${key}`, !req.value?.lineage?.[key])
}

function setTrustMode(event: Event) {
  setField('trust.mode', (event.target as HTMLSelectElement).value)
}

const trustModeOptions = [
  { value: 'unsigned', label: 'Unsigned' },
  { value: 'signed', label: 'Signed' },
  { value: 'anchored', label: 'Anchored' },
  { value: 'attested', label: 'Attested' },
  { value: 'not_applicable', label: 'Not Applicable' },
  { value: 'caller_verification_required', label: 'Caller Verification Required' },
  { value: 'actor_aware_governed_access', label: 'Actor-Aware Governed Access' },
]

function toggleTrustCheckpoints() {
  setField('trust.checkpoints', !req.value?.trust?.checkpoints)
}

function setScaleShapePreference(event: Event) {
  setField('scale.shape_preference', (event.target as HTMLSelectElement).value)
}

function toggleScaleHA() {
  setField('scale.high_availability', !req.value?.scale?.high_availability)
}

async function handleSave() {
  if (readOnlyMode.value || !projectRecord.value || !designStore.draftRequirements) return

  saving.value = true
  saveError.value = null
  try {
    if (artifactIsLockedForDevelopment.value) {
      const created = await createRequirements(projectRecord.value.project_id, {
        id: `req-${crypto.randomUUID()}`,
        title: nextRevisionTitle(artifactTitle.value.trim() || projectRecord.value.title || 'Requirements'),
        data: designStore.draftRequirements,
      })
      await setRequirementsRole(projectRecord.value.project_id, created.id, projectRecord.value.role)
      designStore.originalRequirements = JSON.parse(JSON.stringify(designStore.draftRequirements))
      await refreshArtifacts()
      router.push(`/design/projects/${projectRecord.value.project_id}/requirements/${created.id}`)
      return
    }

    await updateRequirements(projectRecord.value.project_id, projectRecord.value.id, {
      title: artifactTitle.value.trim() || projectRecord.value.title || 'Requirements',
      status: projectRecord.value.status,
      data: designStore.draftRequirements,
    })
    designStore.originalRequirements = JSON.parse(JSON.stringify(designStore.draftRequirements))
    await refreshArtifacts()
  } catch (err) {
    saveError.value = err instanceof Error ? err.message : String(err)
  } finally {
    saving.value = false
  }
}

async function handleDelete() {
  if (readOnlyMode.value || !projectRecord.value) return
  const confirmed = await requestConfirmation({
    title: 'Delete these requirements?',
    message: 'This will permanently remove the requirements artifact from the current project.',
    confirmLabel: 'Delete Requirements',
    cancelLabel: 'Cancel',
    tone: 'danger',
  })
  if (!confirmed) return

  saving.value = true
  saveError.value = null
  try {
    await deleteRequirements(projectRecord.value.project_id, projectRecord.value.id)
    await refreshArtifacts()
    router.push(requirementsListPath.value)
  } catch (err) {
    saveError.value = err instanceof Error ? err.message : String(err)
  } finally {
    saving.value = false
  }
}

function handleDiscardTitle() {
  artifactTitle.value = projectRecord.value?.title ?? ''
}

</script>

<template>
  <div class="requirements-view" v-if="hasData && req">
    <RouterLink class="back-link" :to="requirementsListPath">← Back to Requirements</RouterLink>
    <div class="page-header">
      <div class="page-header-main">
        <label class="title-field">
          <span class="title-label">Requirements Title</span>
          <input
            v-if="isEditing"
            class="title-input"
            type="text"
            v-model="artifactTitle"
            placeholder="Name these requirements"
          />
          <h1 v-else class="page-title">Requirements: {{ artifactName }}</h1>
        </label>
        <p class="page-intro">
          This title is the human-facing Product Design artifact name. Keep it business-legible; it is separate from the payload fields below.
        </p>
        <div v-if="artifactIsLockedForDevelopment" class="revision-banner locked">
          Locked for development. Saving changes will create a new working revision instead of modifying the locked baseline.
        </div>
        <div v-else-if="artifactIsWorkingRevision" class="revision-banner working">
          Working revision. This artifact is newer than the current locked developer baseline.
        </div>
        <div v-if="readOnlyMode" class="revision-banner readonly">
          {{ readOnlyReason }}
        </div>
      </div>
      <button v-if="isEditing" class="delete-btn" type="button" :disabled="readOnlyMode" @click="handleDelete">
        Delete Requirements
      </button>
    </div>

    <!-- Mode toggle -->
    <div class="mode-toggle">
      <button
        class="mode-btn"
        :class="{ active: designStore.requirementsMode === 'guided' }"
        @click="setRequirementsMode('guided')"
        type="button"
      >
        Guided
      </button>
      <button
        class="mode-btn"
        :class="{ active: designStore.requirementsMode === 'advanced' }"
        @click="setRequirementsMode('advanced')"
        type="button"
      >
        Advanced
      </button>
    </div>

    <EditorToolbar
      artifact="requirements"
      :canSave="true"
      :saving="saving"
      :saveError="saveError"
      :externalDirty="titleDirty"
      :readOnly="readOnlyMode"
      @save="handleSave"
      @discard="handleDiscardTitle"
    />

    <section class="assistant-link-panel">
      <div>
        <strong>Need AI help?</strong>
        <p>Use the dedicated project AI Assistant page to draft Product Design from source docs and save reviewed sections back into Studio.</p>
      </div>
      <button class="mode-btn" type="button" @click="router.push(`/design/projects/${projectId}/pm/assistant`)">
        Open Product Design AI Assistant
      </button>
    </section>

    <section
      class="validation-overview"
      :class="{ invalid: designStore.validationErrors.length > 0, valid: designStore.validationErrors.length === 0 }"
    >
      <div>
        <strong>{{ designStore.validationErrors.length > 0 ? 'Validation Needs Attention' : 'Validation Ready' }}</strong>
        <p>{{ validationIssueSummary }}</p>
      </div>
      <ul v-if="errorsBySection.globalUnmapped.length > 0" class="validation-overview-list">
        <li v-for="err in errorsBySection.globalUnmapped" :key="err">{{ err }}</li>
      </ul>
      <p v-else-if="sectionValidationIssueCount > 0" class="validation-overview-note">
        Section-specific issues are highlighted directly in the guided sections below.
      </p>
    </section>

    <!-- Guided mode -->
    <template v-if="designStore.requirementsMode === 'guided'">
      <RequirementsSummary :requirements="req" />
      <CompletenessHints :hints="completenessHints" />

      <div class="mapping-toggle" v-if="isEditing">
        <label class="mapping-label">
          <input
            type="checkbox"
            :checked="designStore.showFieldMappings"
            @change="designStore.showFieldMappings = !designStore.showFieldMappings"
          />
          Show technical field mappings
        </label>
      </div>

      <GuidedSection
        v-for="section in GUIDED_SECTIONS"
        :key="section.id"
        :section="section"
        :answers="guidedAnswers"
        :showMappings="designStore.showFieldMappings"
        :readonly="!isEditing"
        :questionErrors="errorsBySection.sections[section.id]?.questionErrors"
        :unmappedErrors="errorsBySection.sections[section.id]?.unmappedErrors"
        @update:answer="updateGuidedAnswerFromEditor"
      />

    </template>

    <!-- Advanced mode -->
    <template v-else>
    <!-- System -->
    <div class="section">
      <h2>System</h2>
      <template v-if="isEditing">
        <div class="form-grid">
          <label class="form-label">Name</label>
          <input
            class="form-input"
            type="text"
            :value="req.system.name"
            @input="setField('system.name', ($event.target as HTMLInputElement).value)"
          />
          <label class="form-label">Domain</label>
          <input
            class="form-input"
            type="text"
            :value="req.system.domain"
            @input="setField('system.domain', ($event.target as HTMLInputElement).value)"
          />
          <label class="form-label">Deployment Intent</label>
          <input
            class="form-input"
            type="text"
            :value="req.system.deployment_intent"
            @input="setField('system.deployment_intent', ($event.target as HTMLInputElement).value)"
          />
        </div>
      </template>
      <template v-else>
        <dl class="info-grid">
          <dt>Name</dt><dd>{{ req.system.name }}</dd>
          <dt>Domain</dt><dd>{{ humanizeLabel(req.system.domain) }}</dd>
          <dt>Deployment Intent</dt><dd>{{ describeDeploymentIntent(req.system.deployment_intent) }}</dd>
        </dl>
      </template>
    </div>

    <!-- Experience Surfaces -->
    <div class="section" v-if="transportKeys.length">
      <h2>{{ sectionDisplay.transports.title }}</h2>
      <p class="section-copy">{{ sectionDisplay.transports.copy }}</p>
      <template v-if="isEditing">
        <div class="toggle-grid">
          <div class="toggle-row" v-for="key in transportKeys" :key="key">
            <span class="toggle-label">{{ key }}</span>
            <button
              class="toggle-switch"
              :class="{ on: req.transports[key], off: !req.transports[key] }"
              @click="toggleTransport(key)"
              type="button"
            >
              {{ req.transports[key] ? 'ON' : 'OFF' }}
            </button>
          </div>
        </div>
      </template>
      <template v-else>
        <div class="pill-row">
          <span
            v-for="key in transportKeys"
            :key="key"
            class="check-pill"
            :class="{ enabled: req.transports[key], disabled: !req.transports[key] }"
          >
            <span class="check-mark">{{ req.transports[key] ? '&#x2713;' : '&#x2717;' }}</span>
            {{ displayLabel(key) }}
          </span>
        </div>
      </template>
    </div>

    <!-- Trust and Verification Posture -->
    <div class="section">
      <h2>{{ sectionDisplay.trust.title }}</h2>
      <p class="section-copy">{{ sectionDisplay.trust.copy }}</p>
      <template v-if="isEditing">
        <div class="form-grid">
          <label class="form-label">Verification posture</label>
          <select class="form-select" :value="req.trust.mode" @change="setTrustMode">
            <option
              v-for="option in trustModeOptions"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </option>
          </select>
          <label class="form-label">Re-check at key steps</label>
          <button
            class="toggle-switch"
            :class="{ on: req.trust.checkpoints, off: !req.trust.checkpoints }"
            @click="toggleTrustCheckpoints"
            type="button"
          >
            {{ req.trust.checkpoints ? 'ON' : 'OFF' }}
          </button>
        </div>
      </template>
      <template v-else>
        <dl class="info-grid">
          <dt>Verification posture</dt><dd>{{ humanizeLabel(req.trust.mode) }}</dd>
          <dt>Re-check at key steps</dt><dd>{{ req.trust.checkpoints ? 'Yes' : 'No' }}</dd>
        </dl>
      </template>
    </div>

    <!-- Identity and Delegation Posture -->
    <div class="section" v-if="authKeys.length">
      <h2>{{ sectionDisplay.auth.title }}</h2>
      <p class="section-copy">{{ sectionDisplay.auth.copy }}</p>
      <template v-if="isEditing">
        <div class="toggle-grid">
          <div class="toggle-row" v-for="key in authKeys" :key="key">
            <span class="toggle-label">{{ displayLabel(key) }}</span>
            <button
              class="toggle-switch"
              :class="{ on: req.auth![key], off: !req.auth![key] }"
              @click="toggleAuth(key)"
              type="button"
            >
              {{ req.auth![key] ? 'ON' : 'OFF' }}
            </button>
          </div>
        </div>
      </template>
      <template v-else>
        <dl class="info-grid">
          <template v-for="key in authKeys" :key="key">
            <dt>{{ displayLabel(key) }}</dt><dd>{{ req.auth![key] ? 'Yes' : 'No' }}</dd>
          </template>
        </dl>
      </template>
    </div>

    <!-- Access and Control Boundaries -->
    <div class="section" v-if="permissionKeys.length">
      <h2>{{ sectionDisplay.permissions.title }}</h2>
      <p class="section-copy">{{ sectionDisplay.permissions.copy }}</p>
      <template v-if="isEditing">
        <div class="toggle-grid">
          <div class="toggle-row" v-for="key in permissionKeys" :key="key">
            <span class="toggle-label">{{ displayLabel(key) }}</span>
            <button
              class="toggle-switch"
              :class="{ on: req.permissions![key], off: !req.permissions![key] }"
              @click="togglePermission(key)"
              type="button"
            >
              {{ req.permissions![key] ? 'ON' : 'OFF' }}
            </button>
          </div>
        </div>
      </template>
      <template v-else>
        <dl class="info-grid">
          <template v-for="key in permissionKeys" :key="key">
            <dt>{{ displayLabel(key) }}</dt><dd>{{ req.permissions![key] ? 'Yes' : 'No' }}</dd>
          </template>
        </dl>
      </template>
    </div>

    <!-- Evidence Retention -->
    <div class="section" v-if="auditKeys.length">
      <h2>{{ sectionDisplay.audit.title }}</h2>
      <p class="section-copy">{{ sectionDisplay.audit.copy }}</p>
      <template v-if="isEditing">
        <div class="toggle-grid">
          <div class="toggle-row" v-for="key in auditKeys" :key="key">
            <span class="toggle-label">{{ displayLabel(key) }}</span>
            <button
              class="toggle-switch"
              :class="{ on: req.audit![key], off: !req.audit![key] }"
              @click="toggleAudit(key)"
              type="button"
            >
              {{ req.audit![key] ? 'ON' : 'OFF' }}
            </button>
          </div>
        </div>
      </template>
      <template v-else>
        <dl class="info-grid">
          <template v-for="key in auditKeys" :key="'audit-' + key">
            <dt>{{ displayLabel(key) }}</dt><dd>{{ req.audit![key] ? 'Yes' : 'No' }}</dd>
          </template>
        </dl>
      </template>
    </div>

    <!-- Execution Traceability -->
    <div class="section" v-if="lineageKeys.length">
      <h2>{{ sectionDisplay.lineage.title }}</h2>
      <p class="section-copy">{{ sectionDisplay.lineage.copy }}</p>
      <template v-if="isEditing">
        <div class="toggle-grid">
          <div class="toggle-row" v-for="key in lineageKeys" :key="key">
            <span class="toggle-label">{{ displayLabel(key) }}</span>
            <button
              class="toggle-switch"
              :class="{ on: req.lineage![key], off: !req.lineage![key] }"
              @click="toggleLineage(key)"
              type="button"
            >
              {{ req.lineage![key] ? 'ON' : 'OFF' }}
            </button>
          </div>
        </div>
      </template>
      <template v-else>
        <dl class="info-grid">
          <template v-for="key in lineageKeys" :key="'lineage-' + key">
            <dt>{{ displayLabel(key) }}</dt><dd>{{ req.lineage![key] ? 'Yes' : 'No' }}</dd>
          </template>
        </dl>
      </template>
    </div>

    <!-- Risk Signals -->
    <div class="section" v-if="riskCapabilities.length || isEditing">
      <h2>{{ sectionDisplay.risk.title }}</h2>
      <p class="section-copy">{{ sectionDisplay.risk.copy }}</p>
      <template v-if="isEditing">
        <KeyValueEditor
          :modelValue="req.risk_profile ?? {}"
          @update:modelValue="setField('risk_profile', $event)"
        />
      </template>
      <template v-else>
        <div class="risk-cards" v-if="riskCapabilities.length">
          <div class="risk-card" v-for="[capName, capData] in riskCapabilities" :key="capName">
            <h3 class="risk-cap-name">{{ capName }}</h3>
            <dl class="risk-fields">
              <template v-for="(val, field) in (capData as Record<string, any>)" :key="field">
                <dt>{{ displayLabel(field) }}</dt>
                <dd>{{ renderValue(val) }}</dd>
              </template>
            </dl>
          </div>
        </div>
      </template>
    </div>

    <!-- Operating Constraints -->
    <div class="section" v-if="businessConstraintKeys.length || isEditing">
      <h2>{{ sectionDisplay.businessConstraints.title }}</h2>
      <p class="section-copy">{{ sectionDisplay.businessConstraints.copy }}</p>
      <template v-if="isEditing">
        <KeyValueEditor
          :modelValue="req.business_constraints ?? {}"
          @update:modelValue="setField('business_constraints', $event)"
        />
      </template>
      <template v-else>
        <dl class="info-grid" v-if="businessConstraintKeys.length">
          <template v-for="key in businessConstraintKeys" :key="key">
            <dt>{{ displayLabel(key) }}</dt><dd>{{ renderValue(req.business_constraints![key]) }}</dd>
          </template>
        </dl>
      </template>
    </div>

    <!-- Delivery and Availability -->
    <div class="section" v-if="req.scale || isEditing">
      <h2>{{ sectionDisplay.scale.title }}</h2>
      <p class="section-copy">{{ sectionDisplay.scale.copy }}</p>
      <template v-if="isEditing">
        <div class="form-grid">
          <label class="form-label">Delivery shape</label>
          <select
            class="form-select"
            :value="req.scale?.shape_preference ?? ''"
            @change="setScaleShapePreference"
          >
            <option value="">-- select --</option>
            <option value="embedded_single_process">Embedded Single Process</option>
            <option value="production_single_service">Production Single Service</option>
            <option value="horizontally_scaled">Horizontally Scaled</option>
            <option value="control_plane_worker_split">Control Plane Worker Split</option>
            <option value="multi_service_estate">Multiple service boundaries</option>
          </select>
          <label class="form-label">High availability</label>
          <button
            class="toggle-switch"
            :class="{ on: req.scale?.high_availability, off: !req.scale?.high_availability }"
            @click="toggleScaleHA"
            type="button"
          >
            {{ req.scale?.high_availability ? 'ON' : 'OFF' }}
          </button>
        </div>
      </template>
      <template v-else>
        <dl class="info-grid">
          <template v-for="(val, key) in req.scale" :key="key">
            <dt>{{ displayLabel(key) }}</dt>
            <dd>{{ renderValue(val) }}</dd>
          </template>
        </dl>
      </template>
    </div>
    </template>
  </div>
  <div v-else class="not-found">Requirements not found.</div>
</template>

<style scoped>
.requirements-view {
  padding: 2rem;
  width: 100%;
  max-width: none;
}

.back-link {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  margin-bottom: 0.95rem;
  font-size: 13px;
  font-weight: 600;
  color: var(--accent);
  text-decoration: none;
}

.back-link:hover {
  color: var(--accent-hover);
}

.page-title {
  font-size: 28px;
  line-height: 1.15;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1.25rem;
  margin-bottom: 1.15rem;
}

.page-header-main {
  flex: 1;
  min-width: 0;
}

.title-field {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.title-label {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.title-input {
  width: 100%;
  min-height: 3rem;
  padding: 0.9rem 1rem;
  border-radius: 18px;
  border: 1px solid var(--surface-border-card);
  background: var(--surface-depth-card);
  color: var(--text-primary);
  font-size: 1.45rem;
  font-weight: 700;
  line-height: 1.2;
}

.page-intro {
  margin: 0.65rem 0 0;
  color: var(--text-secondary);
  line-height: 1.55;
}

.assistant-panel {
  margin-bottom: 1.5rem;
  padding: 1rem;
  border: 1px solid var(--border);
  border-radius: 16px;
  background: var(--surface-depth-card);
}

.assistant-panel-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}

.assistant-panel-header h2 {
  margin: 0 0 0.35rem;
  font-size: 16px;
  color: var(--text-primary);
}

.assistant-panel-header p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.5;
  max-width: 68ch;
}

.assistant-actions {
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
  flex-wrap: wrap;
}

.assistant-recommendation {
  margin: 1rem 0;
  padding: 0.9rem 1rem;
  border-radius: 14px;
  border: 1px solid rgba(96, 165, 250, 0.24);
  background: var(--surface-depth-card);
}

.assistant-recommendation strong {
  display: block;
  margin-bottom: 0.35rem;
  color: var(--text-primary);
}

.assistant-recommendation p {
  margin: 0 0 0.45rem;
  color: var(--text-secondary);
  line-height: 1.5;
}

.assistant-recommendation ul {
  margin: 0;
  padding-left: 1rem;
  color: var(--text-secondary);
}

.inline-status {
  text-transform: lowercase;
}

.assistant-btn {
  padding: 0.75rem 1rem;
  border-radius: 12px;
  border: 1px solid rgba(96, 165, 250, 0.28);
  background: rgba(30, 64, 175, 0.28);
  color: #dbeafe;
  font-size: 0.92rem;
  font-weight: 600;
  cursor: pointer;
}

.assistant-btn.secondary {
  border-color: var(--border);
  background: transparent;
  color: var(--text-secondary);
}

.assistant-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.assistant-source {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  margin-bottom: 1rem;
}

.assistant-source span {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-secondary);
}

.assistant-source textarea {
  width: 100%;
  min-height: 9rem;
  padding: 0.85rem 1rem;
  border-radius: 14px;
  border: 1px solid var(--border);
  background: var(--bg-input);
  color: var(--text-primary);
  resize: vertical;
  box-sizing: border-box;
}

.assistant-error {
  margin-bottom: 1rem;
  padding: 0.75rem 0.9rem;
  border-radius: 12px;
  border: 1px solid rgba(248, 113, 113, 0.24);
  background: rgba(127, 29, 29, 0.18);
  color: #fecaca;
  font-size: 13px;
}

.assistant-results {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.assistant-summary h3 {
  margin: 0 0 0.35rem;
  font-size: 15px;
  color: var(--text-primary);
}

.assistant-summary p {
  margin: 0 0 0.75rem;
  color: var(--text-secondary);
  line-height: 1.5;
}

.assistant-meta-block {
  margin-top: 0.75rem;
}

.assistant-meta-block strong {
  display: block;
  margin-bottom: 0.35rem;
  color: var(--text-primary);
  font-size: 13px;
}

.assistant-meta-block ul {
  margin: 0;
  padding-left: 1.25rem;
  color: var(--text-secondary);
}

.assistant-selection-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.assistant-selection-item {
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
  padding: 0.85rem 0.95rem;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--surface-depth-card);
}

.assistant-selection-copy {
  flex: 1;
  min-width: 0;
}

.assistant-selection-title-row {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.35rem;
}

.assistant-selection-copy p {
  margin: 0 0 0.35rem;
  color: var(--text-secondary);
  line-height: 1.45;
  white-space: pre-wrap;
}

.assistant-selection-copy small {
  color: var(--text-muted);
}

.assistant-confidence {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
}

.assistant-footer {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.assistant-saved {
  font-size: 13px;
  color: #86efac;
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

.delete-btn {
  padding: 0.75rem 1rem;
  border-radius: 12px;
  border: 1px solid rgba(248, 113, 113, 0.28);
  background: rgba(127, 29, 29, 0.22);
  color: #fecaca;
  font-size: 0.92rem;
  font-weight: 600;
  cursor: pointer;
}

.section {
  margin-bottom: 1.35rem;
  background: var(--surface-depth-card);
  border: 1px solid var(--surface-border-card);
  border-radius: 20px;
  padding: 1.3rem;
}

.section-copy {
  margin: 0 0 1rem;
  color: var(--text-secondary);
  line-height: 1.55;
  max-width: 78ch;
}

.section h2 {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 0.9rem;
}

.info-grid {
  display: grid;
  grid-template-columns: 200px 1fr;
  gap: 0.5rem 1rem;
  margin: 0;
}

.info-grid dt {
  font-size: 12px;
  color: var(--text-muted);
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.info-grid dd {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0;
}

/* Transport / check pills */
.pill-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.check-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  font-weight: 700;
  padding: 0.35rem 0.75rem;
  border-radius: 999px;
  border: 1px solid var(--surface-border-card);
}

.check-pill.enabled {
  background: rgba(52, 211, 153, 0.1);
  color: var(--design-handled, #34d399);
  border-color: rgba(52, 211, 153, 0.3);
}

.check-pill.disabled {
  background: transparent;
  color: var(--text-muted);
  opacity: 0.6;
}

.check-mark {
  font-size: 12px;
}

/* Risk profile cards */
.risk-cards {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.risk-card {
  flex: 1 1 240px;
  max-width: 360px;
  padding: 1rem;
  background: var(--surface-depth-card);
  border: 1px solid var(--surface-border-card);
  border-radius: 16px;
}

.risk-cap-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 0.5rem;
}

.risk-fields {
  display: grid;
  grid-template-columns: 140px 1fr;
  gap: 0.25rem 0.75rem;
  margin: 0;
}

.risk-fields dt {
  font-size: 12px;
  color: var(--text-muted);
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.risk-fields dd {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 0;
  word-break: break-word;
}

.not-found {
  padding: 2rem;
  color: var(--text-muted);
}

/* ---- Edit-mode form controls ---- */
.form-grid {
  display: grid;
  grid-template-columns: 200px 1fr;
  gap: 0.75rem 1rem;
  align-items: center;
}

.form-label {
  font-size: 13px;
  color: var(--text-muted);
  font-weight: 700;
}

.form-input {
  font-size: 13px;
  padding: 0.65rem 0.75rem;
  background: var(--surface-depth-card);
  border: 1px solid var(--surface-border-card);
  border-radius: 12px;
  color: var(--text-primary);
  outline: none;
  width: 100%;
  box-sizing: border-box;
}

.form-input:focus {
  border-color: var(--border-focus);
}

.form-select {
  font-size: 13px;
  padding: 0.65rem 0.75rem;
  background: var(--surface-depth-card);
  border: 1px solid var(--surface-border-card);
  border-radius: 12px;
  color: var(--text-primary);
  outline: none;
  cursor: pointer;
}

.form-select:focus {
  border-color: var(--border-focus);
}

/* Toggle grid */
.toggle-grid {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.toggle-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.8rem 0.9rem;
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  background: var(--surface-depth-card);
}

.toggle-label {
  font-size: 13px;
  color: var(--text-muted);
  font-weight: 700;
  min-width: 200px;
}

.toggle-switch {
  padding: 0.35rem 0.8rem;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border-radius: 999px;
  border: 1px solid var(--surface-border-card);
  cursor: pointer;
  transition: all var(--transition);
  min-width: 60px;
  text-align: center;
}

.toggle-switch.on {
  background: rgba(52, 211, 153, 0.12);
  color: var(--success);
  border-color: rgba(52, 211, 153, 0.3);
}

.toggle-switch.off {
  background: var(--surface-depth-card);
  color: var(--text-muted);
}

.toggle-switch:hover {
  background: rgba(148, 163, 184, 0.12);
}

.assistant-link-panel {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: center;
  margin: 1rem 0 1.25rem;
  padding: 1rem 1.1rem;
  border: 1px solid var(--surface-border-card);
  border-radius: 18px;
  background:
    radial-gradient(circle at top left, rgba(99, 102, 241, 0.1), transparent 34%),
    rgba(15, 23, 42, 0.46);
}

.assistant-link-panel p {
  margin: 0.3rem 0 0;
  color: var(--text-secondary);
}

.mode-toggle {
  display: flex;
  gap: 0;
  margin-bottom: 1rem;
  border: 1px solid var(--surface-border-card);
  border-radius: 12px;
  overflow: hidden;
  width: fit-content;
  background: var(--surface-depth-card);
}

.mode-btn {
  padding: 0.62rem 1.35rem;
  font-size: 13px;
  font-weight: 700;
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition);
}

.mode-btn.active {
  background: var(--accent);
  color: #fff;
}

.mode-btn:hover:not(.active) {
  background: rgba(148, 163, 184, 0.12);
  color: var(--text-primary);
}

.mapping-toggle {
  margin-bottom: 16px;
}

.mapping-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-muted);
  cursor: pointer;
}

.mapping-label input[type="checkbox"] {
  cursor: pointer;
}

.validation-overview {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin: 1.15rem 0 1.35rem;
  padding: 1rem 1.1rem;
  border-radius: 18px;
  border: 1px solid rgba(52, 211, 153, 0.24);
  background:
    radial-gradient(circle at top left, rgba(16, 185, 129, 0.12), transparent 34%),
    rgba(6, 78, 59, 0.14);
}

.validation-overview.invalid {
  border-color: rgba(248, 113, 113, 0.32);
  background:
    radial-gradient(circle at top left, rgba(248, 113, 113, 0.12), transparent 34%),
    rgba(127, 29, 29, 0.18);
}

.validation-overview strong {
  display: block;
  margin-bottom: 0.35rem;
  color: var(--text-primary);
}

.validation-overview p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.5;
}

.validation-overview-list {
  flex: 1;
  min-width: 280px;
  max-width: 620px;
  margin: 0;
  padding-left: 1.1rem;
  color: #fecaca;
  font-size: 13px;
  line-height: 1.55;
}

.validation-overview-note {
  max-width: 420px;
}
</style>
