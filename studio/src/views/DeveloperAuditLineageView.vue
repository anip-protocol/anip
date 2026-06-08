<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useDeveloperDefinitionEditor } from '../design/use-developer-definition-editor'
import { useDeveloperIssueTargets } from '../design/use-developer-issue-targets'
import ProjectIssueBanner from '../components/ProjectIssueBanner.vue'
import { useProjectIssue } from '../design/use-project-issue'
import { projectStore } from '../design/project-store'

const router = useRouter()
const editing = ref(false)
const readOnly = computed(() => projectStore.runtimeStatus?.read_only_mode !== false)
const {
  project,
  baseline,
  baselineAligned,
  definition,
  saveDraft,
  resetDefinition,
  saving,
  saveError,
} = useDeveloperDefinitionEditor()
const pageIssue = useProjectIssue('project-developer-audit-lineage')
const {
  messagesForPath,
  hasIssueForPath,
} = useDeveloperIssueTargets({ definition, project })

function yesNo(value: boolean): string {
  return value ? 'Yes' : 'No'
}

function startEditing() {
  if (readOnly.value) return
  editing.value = true
}

function cancelEditing() {
  resetDefinition()
  editing.value = false
}

async function saveAndReview() {
  if (readOnly.value) return
  await saveDraft()
  if (!saveError.value) {
    editing.value = false
  }
}

function auditPath(field: string): string {
  return `audit.${field}`
}

watch(readOnly, (isReadOnly) => {
  if (isReadOnly) editing.value = false
})
</script>

<template>
  <div class="developer-definition">
    <template v-if="project">
      <section class="page-header">
        <button class="back-link" type="button" @click="router.push(`/design/projects/${project.id}/developer`)">
          &larr; Back to Developer Design
        </button>
        <div class="page-kicker">Developer Design</div>
        <h1>Audit & Lineage</h1>
        <p>
          Define the evidence generated services must preserve: durable records, invocation history, task lineage, client references, and cross-service reconstruction.
        </p>
      </section>

      <ProjectIssueBanner :issue="pageIssue" title="Audit and lineage diagnostics" />

      <section v-if="!baseline" class="panel empty-panel">
        <h2>Developer baseline is not locked</h2>
        <p>Return to Developer Overview and lock Product Design before formalizing audit and lineage.</p>
      </section>

      <section v-else-if="!baselineAligned" class="panel empty-panel">
        <h2>Locked baseline is out of sync</h2>
        <p>Product Design changed after the current developer baseline was locked. Re-lock the baseline before continuing.</p>
      </section>

      <section v-else-if="definition" class="grid" :class="{ 'review-mode': !editing, 'edit-mode': editing }">
        <article id="audit-lineage" class="panel panel-full studio-surface">
          <div class="panel-header">
            <h2>Evidence Contract</h2>
            <div class="header-actions">
              <button v-if="!editing" class="btn btn-secondary" type="button" :disabled="readOnly" @click="startEditing">
                Edit Audit
              </button>
              <button v-if="editing" class="btn btn-secondary" type="button" :disabled="saving" @click="cancelEditing">
                Cancel
              </button>
              <button v-if="editing" class="btn btn-primary" type="button" :disabled="readOnly || saving" @click="saveAndReview">
                {{ saving ? 'Saving...' : 'Save Audit' }}
              </button>
            </div>
          </div>
          <p v-if="saveError" class="error">{{ saveError }}</p>
          <p class="panel-copy">
            Audit and lineage controls are separate from actor permissions. They define what generated services must record so behavior can be traced back to the locked contract and invoking actor.
          </p>
          <div v-if="!editing" class="review-summary-grid">
            <div class="review-summary-card"><strong>Durable Records</strong><span>{{ yesNo(definition.audit.durable_records_required) }}</span></div>
            <div class="review-summary-card"><strong>Searchable History</strong><span>{{ yesNo(definition.audit.searchable_history_required) }}</span></div>
            <div class="review-summary-card"><strong>Invocation Tracking</strong><span>{{ yesNo(definition.audit.invocation_tracking) }}</span></div>
            <div class="review-summary-card"><strong>Task Tracking</strong><span>{{ yesNo(definition.audit.task_tracking) }}</span></div>
            <div class="review-summary-card"><strong>Parent Invocation Tracking</strong><span>{{ yesNo(definition.audit.parent_invocation_tracking) }}</span></div>
            <div class="review-summary-card"><strong>Client Reference IDs</strong><span>{{ yesNo(definition.audit.client_reference_ids) }}</span></div>
            <div class="review-summary-card"><strong>Service Handoffs</strong><span>{{ yesNo(definition.audit.service_handoffs_required) }}</span></div>
            <div class="review-summary-card"><strong>Cross-Service Reconstruction</strong><span>{{ yesNo(definition.audit.cross_service_reconstruction_required) }}</span></div>
            <div class="review-summary-card"><strong>Cross-Service Continuity</strong><span>{{ yesNo(definition.audit.cross_service_continuity_required) }}</span></div>
          </div>
          <div v-if="editing" class="settings-grid">
            <label id="audit-durable-records" class="field" :class="{ 'field-error': hasIssueForPath(auditPath('durable_records_required')) }">
              <span>Durable Records</span>
              <select v-model="definition.audit.durable_records_required" class="select"><option :value="true">Yes</option><option :value="false">No</option></select>
              <small v-for="message in messagesForPath(auditPath('durable_records_required'))" :key="message" class="field-error-copy">{{ message }}</small>
            </label>
            <label id="audit-searchable-history" class="field" :class="{ 'field-error': hasIssueForPath(auditPath('searchable_history_required')) }">
              <span>Searchable History</span>
              <select v-model="definition.audit.searchable_history_required" class="select"><option :value="true">Yes</option><option :value="false">No</option></select>
              <small v-for="message in messagesForPath(auditPath('searchable_history_required'))" :key="message" class="field-error-copy">{{ message }}</small>
            </label>
            <label id="audit-invocation-tracking" class="field" :class="{ 'field-error': hasIssueForPath(auditPath('invocation_tracking')) }">
              <span>Invocation Tracking</span>
              <select v-model="definition.audit.invocation_tracking" class="select"><option :value="true">Yes</option><option :value="false">No</option></select>
              <small v-for="message in messagesForPath(auditPath('invocation_tracking'))" :key="message" class="field-error-copy">{{ message }}</small>
            </label>
            <label id="audit-task-tracking" class="field" :class="{ 'field-error': hasIssueForPath(auditPath('task_tracking')) }">
              <span>Task Tracking</span>
              <select v-model="definition.audit.task_tracking" class="select"><option :value="true">Yes</option><option :value="false">No</option></select>
              <small v-for="message in messagesForPath(auditPath('task_tracking'))" :key="message" class="field-error-copy">{{ message }}</small>
            </label>
            <label id="audit-parent-invocation-tracking" class="field" :class="{ 'field-error': hasIssueForPath(auditPath('parent_invocation_tracking')) }">
              <span>Parent Invocation Tracking</span>
              <select v-model="definition.audit.parent_invocation_tracking" class="select"><option :value="true">Yes</option><option :value="false">No</option></select>
              <small v-for="message in messagesForPath(auditPath('parent_invocation_tracking'))" :key="message" class="field-error-copy">{{ message }}</small>
            </label>
            <label id="audit-client-reference-ids" class="field" :class="{ 'field-error': hasIssueForPath(auditPath('client_reference_ids')) }">
              <span>Client Reference IDs</span>
              <select v-model="definition.audit.client_reference_ids" class="select"><option :value="true">Yes</option><option :value="false">No</option></select>
              <small v-for="message in messagesForPath(auditPath('client_reference_ids'))" :key="message" class="field-error-copy">{{ message }}</small>
            </label>
            <label id="audit-service-handoffs" class="field" :class="{ 'field-error': hasIssueForPath(auditPath('service_handoffs_required')) }">
              <span>Service Handoffs</span>
              <select v-model="definition.audit.service_handoffs_required" class="select"><option :value="true">Yes</option><option :value="false">No</option></select>
              <small v-for="message in messagesForPath(auditPath('service_handoffs_required'))" :key="message" class="field-error-copy">{{ message }}</small>
            </label>
            <label id="audit-cross-service-reconstruction" class="field" :class="{ 'field-error': hasIssueForPath(auditPath('cross_service_reconstruction_required')) }">
              <span>Cross-Service Reconstruction</span>
              <select v-model="definition.audit.cross_service_reconstruction_required" class="select"><option :value="true">Yes</option><option :value="false">No</option></select>
              <small v-for="message in messagesForPath(auditPath('cross_service_reconstruction_required'))" :key="message" class="field-error-copy">{{ message }}</small>
            </label>
            <label id="audit-cross-service-continuity" class="field" :class="{ 'field-error': hasIssueForPath(auditPath('cross_service_continuity_required')) }">
              <span>Cross-Service Continuity</span>
              <select v-model="definition.audit.cross_service_continuity_required" class="select"><option :value="true">Yes</option><option :value="false">No</option></select>
              <small v-for="message in messagesForPath(auditPath('cross_service_continuity_required'))" :key="message" class="field-error-copy">{{ message }}</small>
            </label>
          </div>
        </article>
      </section>
    </template>
  </div>
</template>

<style scoped src="./developer-definition-shared.css"></style>
