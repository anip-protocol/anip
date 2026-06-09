<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { createPmArtifact, deletePmArtifact, updatePmArtifact } from '../design/project-api'
import { requestConfirmation } from '../design/confirm'
import {
  findBusinessAreasArtifact,
  cloneProductDesignData,
  defaultPermissionIntentData,
  findActorModelArtifact,
  findPermissionIntentArtifact,
  isPermissionIntentComplete,
  makeBlankPermissionRule,
  PERMISSION_INTENT_ARTIFACT_TYPE,
  persistedPmArtifactStatus,
  productDesignArtifactId,
  type PermissionIntentData,
  type PermissionIntentOutcomeType,
  type PermissionIntentPosture,
} from '../design/product-design'
import { loadProject, projectStore } from '../design/project-store'
import ProjectIssueBanner from '../components/ProjectIssueBanner.vue'
import { useProjectIssue } from '../design/use-project-issue'
import { developerLabel } from '../design/developer-vocabulary'

const route = useRoute()
const router = useRouter()

const projectId = computed(() => route.params.projectId as string)
const project = computed(() => projectStore.activeProject)
const artifact = computed(() => findPermissionIntentArtifact(projectStore.artifacts.pmArtifacts))
const baseData = ref<PermissionIntentData>(defaultPermissionIntentData())
const draft = ref<PermissionIntentData>(defaultPermissionIntentData())
const saving = ref(false)
const deleting = ref(false)
const saveError = ref<string | null>(null)
const editing = ref(false)
const pageIssue = useProjectIssue('project-permission-intent')
const readOnlyMode = computed(() => projectStore.runtimeStatus?.read_only_mode !== false)
const readOnlyReason = computed(() =>
  projectStore.runtimeStatus?.read_only_reason
  || 'Studio is running in read-only mode. Explore the design, then run Studio locally to make changes.',
)

const postureOptions: Array<{ value: PermissionIntentPosture; label: string }> = [
  { value: 'allowed', label: 'Allowed' },
  { value: 'bounded', label: 'Bounded' },
  { value: 'restricted', label: 'Restricted' },
  { value: 'denied', label: 'Denied' },
  { value: 'approval_required', label: 'Approval Required' },
]

const outcomeTypeOptions: Array<{ value: PermissionIntentOutcomeType; label: string }> = [
  { value: 'direct_result', label: 'Direct Result' },
  { value: 'bounded_result', label: 'Bounded Result' },
  { value: 'masked_or_restricted_result', label: 'Masked or Restricted Result' },
  { value: 'deny_request', label: 'Deny Request' },
  { value: 'approval_stop', label: 'Approval Stop' },
  { value: 'clarification_required', label: 'Clarification Required' },
]

async function ensureLoaded() {
  if (!projectId.value) return
  if (projectStore.activeProject?.id === projectId.value) return
  await loadProject(projectId.value)
}

function syncDraft() {
  const next = artifact.value?.data
    ? cloneProductDesignData(artifact.value.data as PermissionIntentData)
    : defaultPermissionIntentData()
  if (!next.rules.length) {
    next.rules = [makeBlankPermissionRule()]
  }
  next.rules = next.rules.map((rule) => ({
    ...makeBlankPermissionRule(),
    ...rule,
  }))
  baseData.value = cloneProductDesignData(next)
  draft.value = cloneProductDesignData(next)
}

onMounted(async () => {
  await ensureLoaded()
  syncDraft()
})

watch(
  () => [projectId.value, artifact.value?.updated_at] as const,
  async () => {
    await ensureLoaded()
    syncDraft()
  },
)

const hasChanges = computed(() => JSON.stringify(draft.value) !== JSON.stringify(baseData.value))
const isComplete = computed(() => isPermissionIntentComplete(draft.value))
const pageHasIssue = computed(() => Boolean(pageIssue.value?.count) && !isComplete.value)
const actorOptions = computed(() => {
  const actorArtifact = findActorModelArtifact(projectStore.artifacts.pmArtifacts)
  const actors = ((actorArtifact?.data as { actors?: Array<{ actor_id?: string; title?: string }> } | undefined)?.actors ?? [])
  const canonical = actors
    .map((actor) => ({
      value: actor.actor_id?.trim() ?? '',
      label: [actor.title?.trim() ?? '', actor.actor_id?.trim() ?? ''].filter(Boolean).join(' · '),
      missing: false,
    }))
    .filter((actor, index, source) =>
      actor.value.length > 0 && source.findIndex((entry) => entry.value === actor.value) === index,
    )

  const legacy = draft.value.rules
    .map((rule) => rule.actor_id.trim())
    .filter((value) => value.length > 0 && !canonical.some((actor) => actor.value === value))
    .map((value) => ({
      value,
      label: `${value} · Missing from Actor Model`,
      missing: true,
    }))

  return [...canonical, ...legacy]
})

function missingText(value: string): boolean {
  return pageHasIssue.value && !value.trim()
}

function ruleHasIssue(index: number): boolean {
  const rule = draft.value.rules[index]
  return pageHasIssue.value && Boolean(rule) && (
    !rule.actor_id.trim()
    || !rule.business_area.trim()
    || !rule.governed_outcome_type.trim()
    || !rule.governed_outcome.trim()
  )
}

function missingRuleField(index: number, field: 'actor_id' | 'business_area' | 'governed_outcome_type' | 'governed_outcome'): boolean {
  return pageHasIssue.value && !draft.value.rules[index]?.[field]?.trim()
}
const businessAreaOptions = computed(() => {
  const businessAreaArtifact = findBusinessAreasArtifact(projectStore.artifacts.pmArtifacts)
  const entries = ((businessAreaArtifact?.data as { entries?: Array<{ business_area_id?: string; label?: string }> } | undefined)?.entries ?? [])
  const canonical = entries
    .map((entry) => ({
      value: entry.business_area_id?.trim() ?? '',
      label: [entry.label?.trim() ?? '', entry.business_area_id?.trim() ?? ''].filter(Boolean).join(' · '),
      missing: false,
    }))
    .filter((entry, index, source) =>
      entry.value.length > 0 && source.findIndex((candidate) => candidate.value === entry.value) === index,
    )

  const legacy = draft.value.rules
    .map((rule) => rule.business_area.trim())
    .filter((value) => value.length > 0 && !canonical.some((entry) => entry.value === value))
    .map((value) => ({
      value,
      label: `${value} · Missing from Business Areas`,
      missing: true,
    }))

  return [...canonical, ...legacy]
})

function addRule() {
  if (readOnlyMode.value) return
  draft.value.rules.push(makeBlankPermissionRule())
}

function removeRule(index: number) {
  if (readOnlyMode.value) return
  draft.value.rules.splice(index, 1)
  if (!draft.value.rules.length) {
    draft.value.rules.push(makeBlankPermissionRule())
  }
}

function startEditing() {
  if (readOnlyMode.value) return
  editing.value = true
}

function discardChanges() {
  draft.value = cloneProductDesignData(baseData.value)
  editing.value = false
}

async function save() {
  if (readOnlyMode.value || !project.value) return
  saving.value = true
  saveError.value = null
  try {
    const payload: PermissionIntentData = {
      ...cloneProductDesignData(draft.value),
      artifact_type: PERMISSION_INTENT_ARTIFACT_TYPE,
      rules: draft.value.rules.filter((rule) =>
        rule.actor_id.trim().length > 0
        || rule.business_area.trim().length > 0
        || rule.governed_outcome_type.trim().length > 0
        || rule.governed_outcome.trim().length > 0
        || rule.notes.trim().length > 0,
      ),
    }
    if (!payload.rules.length) {
      payload.rules = [makeBlankPermissionRule()]
    }
    if (artifact.value) {
      await updatePmArtifact(project.value.id, artifact.value.id, {
        title: 'Permission Intent',
        status: persistedPmArtifactStatus(isPermissionIntentComplete(payload)),
        data: payload,
      })
    } else {
      await createPmArtifact(project.value.id, {
        id: productDesignArtifactId(project.value.id, PERMISSION_INTENT_ARTIFACT_TYPE),
        title: 'Permission Intent',
        data: payload,
      })
    }
    await loadProject(project.value.id)
    editing.value = false
  } catch (err) {
    saveError.value = err instanceof Error ? err.message : String(err)
  } finally {
    saving.value = false
  }
}

async function removeArtifact() {
  if (readOnlyMode.value || !project.value || !artifact.value) return
  const confirmed = await requestConfirmation({
    title: 'Delete Permission Intent?',
    message: 'This removes the saved Product Design permission intent from the project.',
    confirmLabel: 'Delete Permission Intent',
    cancelLabel: 'Cancel',
    tone: 'danger',
  })
  if (!confirmed) return
  deleting.value = true
  try {
    await deletePmArtifact(project.value.id, artifact.value.id)
    await loadProject(project.value.id)
    editing.value = false
  } finally {
    deleting.value = false
  }
}
</script>

<template>
  <div class="product-editor">
    <template v-if="project">
      <section class="page-header">
        <button class="back-link" type="button" @click="router.push(`/design/projects/${project.id}/pm`)">
          &larr; Back to Product Overview
        </button>
        <div class="page-kicker">Product Design</div>
        <h1>Permission Intent</h1>
        <p>
          Record the PM and business expectation for who should be allowed, bounded, restricted, denied, or stopped for
          approval across the major business areas in scope.
        </p>
      </section>

      <ProjectIssueBanner :issue="pageIssue" title="Permission Intent diagnostics" />

      <div v-if="saveError" class="banner banner-error">{{ saveError }}</div>
      <div v-if="readOnlyMode" class="banner banner-warning readonly-banner">{{ readOnlyReason }}</div>

      <section class="panel" :class="{ 'field-error-card': pageHasIssue }">
        <div class="panel-header">
          <div>
            <h2>Permission Posture</h2>
            <p class="panel-copy">
              This is still a business artifact. Use it to describe who can ask for what, how the product should respond,
              and when the system should proceed directly versus stop, restrict, deny, or require approval.
            </p>
          </div>
          <div class="actions">
            <button v-if="!editing" class="btn btn-secondary" type="button" :disabled="readOnlyMode" @click="startEditing">
              {{ artifact ? 'Edit Permission Intent' : 'Add Permission Intent' }}
            </button>
            <button v-if="editing" class="btn btn-secondary" :disabled="!hasChanges" @click="discardChanges">Discard Changes</button>
            <button v-if="editing" class="btn btn-secondary" :disabled="readOnlyMode || !artifact || deleting" @click="removeArtifact">
              {{ deleting ? 'Deleting...' : 'Delete' }}
            </button>
            <button v-if="editing" class="btn btn-primary" :disabled="readOnlyMode || saving" @click="save">
              {{ saving ? 'Saving...' : 'Save to Project' }}
            </button>
          </div>
        </div>

        <div v-if="!editing && artifact" class="card-stack">
          <article class="entry-card summary-entry-card">
            <div class="entry-header">
              <h3>Policy Summary</h3>
              <span class="summary-chip">{{ baseData.rules.length }} rule{{ baseData.rules.length === 1 ? '' : 's' }}</span>
            </div>
            <p>{{ baseData.policy_summary || 'No policy summary captured.' }}</p>
            <details class="view-details">
              <summary>View all saved values</summary>
              <div class="detail-grid">
                <div class="detail-wide"><span>Policy Summary</span><p>{{ baseData.policy_summary || 'Not captured' }}</p></div>
              </div>
            </details>
          </article>
          <article v-for="(rule, index) in baseData.rules" :key="`summary-${index}`" class="entry-card summary-entry-card">
            <div class="entry-header">
              <h3>Rule {{ index + 1 }}</h3>
              <span class="summary-chip">{{ developerLabel(rule.access_posture, 'Posture missing') }}</span>
            </div>
            <p>{{ rule.actor_id || 'Actor missing' }} · {{ rule.business_area || 'Business area missing' }}</p>
            <small>{{ rule.governed_outcome || 'No governed outcome captured.' }}</small>
            <details class="view-details">
              <summary>View all saved values</summary>
              <div class="detail-grid">
                <div><span>Actor ID</span><strong>{{ rule.actor_id || 'Not captured' }}</strong></div>
                <div><span>Business Area</span><strong>{{ rule.business_area || 'Not captured' }}</strong></div>
                <div><span>Access Posture</span><strong>{{ developerLabel(rule.access_posture, 'Not captured') }}</strong></div>
                <div><span>Outcome Class</span><strong>{{ developerLabel(rule.governed_outcome_type, 'Not captured') }}</strong></div>
                <div class="detail-wide"><span>Governed Outcome</span><p>{{ rule.governed_outcome || 'Not captured' }}</p></div>
                <div class="detail-wide"><span>Notes</span><p>{{ rule.notes || 'Not captured' }}</p></div>
              </div>
            </details>
          </article>
        </div>

        <div v-else-if="!editing" class="empty-editor-state">
          <strong>No permission intent saved yet.</strong>
          <p>Add permission posture when actor and business-area expectations are ready.</p>
        </div>

        <template v-else>
        <label class="field field-full summary-field" :class="{ 'field-error': missingText(draft.policy_summary) }">
          <span class="field-label">Policy Summary</span>
          <span class="field-help">Capture the product-wide permission intent in plain business language, including the overall trust and governance posture.</span>
          <textarea v-model="draft.policy_summary" class="field-input textarea" rows="4" />
          <small v-if="missingText(draft.policy_summary)" class="field-error-copy">Policy summary is required.</small>
        </label>

        <article class="guidance-card">
          <h3>How to use this matrix</h3>
          <p>
            Add one row for each actor and business area combination that matters. PM should define the intended trust
            posture and the governed outcome class the product should return before developers formalize it into policy,
            capability contracts, and verification.
          </p>
          <div class="definition-grid">
            <div class="definition-card">
              <strong>Allowed</strong>
              <span>The actor can proceed directly and receive a normal governed result.</span>
            </div>
            <div class="definition-card">
              <strong>Bounded</strong>
              <span>The actor can proceed, but the result should stay narrowed, limited, or preview-oriented.</span>
            </div>
            <div class="definition-card">
              <strong>Restricted</strong>
              <span>The actor can continue only with masking, partial visibility, or reduced scope.</span>
            </div>
            <div class="definition-card">
              <strong>Denied</strong>
              <span>The product should refuse the request rather than attempt the workflow.</span>
            </div>
            <div class="definition-card">
              <strong>Approval Required</strong>
              <span>The product may prepare the step, but it must stop before execution and surface the approval boundary.</span>
            </div>
          </div>
        </article>

        <div class="card-stack">
          <article v-for="(rule, index) in draft.rules" :key="index" class="entry-card" :class="{ 'field-error-card': ruleHasIssue(index) }">
            <div class="entry-header">
              <h3>Rule {{ index + 1 }}</h3>
              <button class="btn btn-tertiary" type="button" :disabled="readOnlyMode" @click="removeRule(index)">Remove</button>
            </div>
            <div class="field-grid">
              <label class="field" :class="{ 'field-error': missingRuleField(index, 'actor_id') }">
                <span class="field-label">Actor ID</span>
                <span class="field-help">
                  {{
                    actorOptions.length
                      ? 'Select the Actor Model identifier this rule applies to. Permission Intent should reuse PM-owned actors, not invent new free-text ids.'
                      : 'Define and save actors on Actor Model first. Permission Intent should only reference PM-owned actor ids.'
                  }}
                </span>
                <select v-model="rule.actor_id" class="field-input" :disabled="!actorOptions.length">
                  <option value="" disabled>{{ actorOptions.length ? 'Select actor' : 'No saved actors available' }}</option>
                  <option
                    v-for="actor in actorOptions"
                    :key="actor.value"
                    :value="actor.value"
                  >
                    {{ actor.label }}
                  </option>
                </select>
                <small v-if="missingRuleField(index, 'actor_id')" class="field-error-copy">Actor ID is required.</small>
              </label>
              <label class="field" :class="{ 'field-error': missingRuleField(index, 'business_area') }">
                <span class="field-label">Business Area</span>
                <span class="field-help">
                  {{
                    businessAreaOptions.length
                      ? 'Select the Business Areas identifier this rule applies to. Permission Intent should reuse PM-owned business-area ids, not invent new ones here.'
                      : 'Define and save Business Areas first. Permission Intent should only reference PM-owned business-area ids.'
                  }}
                </span>
                <select v-model="rule.business_area" class="field-input" :disabled="!businessAreaOptions.length">
                  <option value="" disabled>{{ businessAreaOptions.length ? 'Select business area' : 'No saved business areas available' }}</option>
                  <option
                    v-for="area in businessAreaOptions"
                    :key="area.value"
                    :value="area.value"
                  >
                    {{ area.label }}
                  </option>
                </select>
                <small v-if="missingRuleField(index, 'business_area')" class="field-error-copy">Business area is required.</small>
              </label>
              <label class="field">
                <span class="field-label">Access Posture</span>
                <span class="field-help">Describe the intended trust boundary before developers formalize it.</span>
                <select v-model="rule.access_posture" class="field-input">
                  <option v-for="option in postureOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
                </select>
              </label>
              <label class="field" :class="{ 'field-error': missingRuleField(index, 'governed_outcome_type') }">
                <span class="field-label">Governed Outcome Class</span>
                <span class="field-help">Choose the broad business response the product should return for this actor and business area.</span>
                <select v-model="rule.governed_outcome_type" class="field-input">
                  <option value="" disabled>Select outcome class</option>
                  <option v-for="option in outcomeTypeOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
                </select>
                <small v-if="missingRuleField(index, 'governed_outcome_type')" class="field-error-copy">Governed outcome class is required.</small>
              </label>
              <label class="field field-full" :class="{ 'field-error': missingRuleField(index, 'governed_outcome') }">
                <span class="field-label">Governed Outcome Details</span>
                <span class="field-help">Describe what the user should actually experience, such as bounded answer, approval stop, denial, masking, or clarification.</span>
                <textarea v-model="rule.governed_outcome" class="field-input textarea" rows="3" />
                <small v-if="missingRuleField(index, 'governed_outcome')" class="field-error-copy">Governed outcome details are required.</small>
              </label>
              <label class="field field-full">
                <span class="field-label">Notes</span>
                <span class="field-help">Call out important approval, masking, denial, or clarification nuance.</span>
                <textarea v-model="rule.notes" class="field-input textarea" rows="3" />
              </label>
            </div>
          </article>
        </div>

        <div class="footer-row">
          <button class="btn btn-secondary" type="button" :disabled="readOnlyMode" @click="addRule">Add Rule</button>
          <span class="status-pill" :class="{ ready: isComplete }">{{ isComplete ? 'Ready' : 'Needs PM input' }}</span>
        </div>
        </template>
      </section>
    </template>
  </div>
</template>

<style scoped>
.product-editor {
  width: 100%;
  max-width: none;
  padding: 2rem;
}

.page-header {
  margin-bottom: 1.75rem;
}

.page-kicker {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 0.4rem;
}

.page-header h1 {
  margin: 0 0 0.5rem;
  font-size: 32px;
  line-height: 1.15;
  font-weight: 700;
  color: var(--text-primary);
}

.page-header p {
  max-width: 78ch;
  color: var(--text-secondary);
  line-height: 1.6;
}

.back-link {
  margin-bottom: 0.9rem;
  border: none;
  background: transparent;
  color: var(--accent);
  padding: 0;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
}

.back-link:hover {
  color: var(--accent-hover);
}

.panel {
  background: var(--surface-depth-panel);
  border: 1px solid var(--surface-border-panel);
  border-radius: 22px;
  padding: 1.35rem;
}

.panel-header,
.entry-header,
.footer-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}

.panel-header {
  margin-bottom: 1.25rem;
}

.entry-header {
  margin-bottom: 1.15rem;
}

.footer-row {
  margin-top: 1.25rem;
}

.panel-header h2,
.entry-header h3 {
  margin: 0;
}

.panel-header h2 {
  font-size: 20px;
  line-height: 1.25;
}

.entry-header h3 {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  padding: 0 0.75rem;
  border: 1px solid rgba(96, 165, 250, 0.26);
  border-radius: 999px;
  background: rgba(96, 165, 250, 0.1);
  color: #bfdbfe;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.panel-copy {
  margin: 0.5rem 0 0;
  color: var(--text-secondary);
  max-width: 72ch;
  line-height: 1.6;
}

.summary-field {
  margin-bottom: 1.25rem;
}

.guidance-card {
  margin-bottom: 1.25rem;
  padding: 1.05rem 1.15rem;
  border: 1px solid var(--surface-border-card);
  border-radius: 18px;
  background:
    radial-gradient(circle at top left, rgba(59, 130, 246, 0.1), transparent 34%),
    rgba(15, 23, 42, 0.48);
}

.guidance-card h3 {
  margin: 0 0 0.6rem;
  color: var(--text-primary);
  font-size: 17px;
}

.guidance-card p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.5;
}

.definition-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 0.75rem;
  margin-top: 1.05rem;
}

.definition-card {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  padding: 0.9rem 0.95rem;
  border-radius: 16px;
  border: 1px solid var(--surface-border-card);
  background: var(--surface-depth-card);
  color: var(--text-secondary);
}

.definition-card strong {
  color: var(--text-primary);
  font-size: 14px;
}

.actions,
.footer-row {
  flex-wrap: wrap;
}

.actions {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  justify-content: flex-end;
}

.actions .btn,
.footer-row .btn,
.entry-header .btn {
  width: auto;
}

.card-stack {
  display: grid;
  gap: 1.1rem;
}

.entry-card {
  border: 1px solid var(--surface-border-card);
  border-radius: 20px;
  background:
    linear-gradient(180deg, rgba(15, 23, 42, 0.66), rgba(15, 23, 42, 0.46));
  padding: 1.1rem;
}

.summary-entry-card p,
.summary-entry-card small,
.empty-editor-state p {
  color: var(--text-secondary);
  line-height: 1.55;
  margin: 0;
}

.summary-entry-card small {
  display: block;
  margin-top: 0.55rem;
}

.view-details {
  border-top: 1px solid rgba(148, 163, 184, 0.12);
  margin-top: 0.85rem;
  padding-top: 0.75rem;
}

.view-details summary {
  color: #bfdbfe;
  cursor: pointer;
  font-size: 13px;
  font-weight: 800;
}

.detail-grid {
  display: grid;
  gap: 0.75rem;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin-top: 0.85rem;
}

.detail-grid > div {
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  background: var(--surface-depth-inset);
  padding: 0.75rem;
}

.detail-wide {
  grid-column: 1 / -1;
}

.detail-grid span {
  color: var(--text-secondary);
  display: block;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.06em;
  margin-bottom: 0.35rem;
  text-transform: uppercase;
}

.detail-grid strong,
.detail-grid p {
  color: var(--text-primary);
  line-height: 1.5;
  margin: 0;
  overflow-wrap: anywhere;
}

.summary-chip {
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.12);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 800;
  padding: 0.35rem 0.7rem;
}

.empty-editor-state {
  border: 1px solid var(--surface-border-card);
  border-radius: 16px;
  background: var(--surface-depth-card);
  padding: 1rem;
}

.empty-editor-state strong {
  color: var(--text-primary);
}

.field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1.05rem;
}

.field {
  display: grid;
  gap: 0.45rem;
  min-width: 0;
}

.field-full {
  grid-column: 1 / -1;
}

.field-label {
  font-weight: 700;
  color: var(--text-primary);
}

.field-help {
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.5;
}

.field-input {
  width: 100%;
  min-width: 0;
  max-width: 100%;
  box-sizing: border-box;
  border-radius: 12px;
  border: 1px solid var(--surface-border-card);
  background: var(--surface-depth-card);
  color: var(--text-primary);
  padding: 0.75rem 0.9rem;
  font: inherit;
  line-height: 1.45;
}

.textarea {
  resize: vertical;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  padding: 0.35rem 0.7rem;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.15);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
}

.status-pill.ready {
  background: rgba(16, 185, 129, 0.16);
  color: #86efac;
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

.btn-tertiary {
  background: var(--surface-depth-card);
  border-color: rgba(148, 163, 184, 0.18);
  color: var(--text-secondary);
}

@media (max-width: 900px) {
  .field-grid,
  .detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>
<style scoped src="./product-inline-errors.css"></style>
