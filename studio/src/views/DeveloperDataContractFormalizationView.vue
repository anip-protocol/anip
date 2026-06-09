<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useDeveloperDefinitionEditor } from '../design/use-developer-definition-editor'
import ProjectIssueBanner from '../components/ProjectIssueBanner.vue'
import { useProjectIssue } from '../design/use-project-issue'
import { useDeveloperIssueTargets } from '../design/use-developer-issue-targets'

const router = useRouter()
const editing = ref(false)
const pageIssue = useProjectIssue('project-developer-data-contract-formalization')
const {
  project,
  baseline,
  baselineAligned,
  definition,
  saveDraft,
  saving,
  saveError,
} = useDeveloperDefinitionEditor()
const {
  messagesForPath,
  messagesForPrefix,
  hasIssueForPath,
  hasIssueForPrefix,
} = useDeveloperIssueTargets({ definition, project })

function conceptPath(conceptId: string, field: string): string {
  return `domain_concept_bindings.${conceptId}.${field}`
}

function conceptHasIssue(conceptId: string): boolean {
  return hasIssueForPrefix(`domain_concept_bindings.${conceptId}`)
}

function applicationObjectPath(objectDef: { object_id?: string; name?: string }, field: string): string {
  const objectPath = objectDef.object_id || objectDef.name || 'application_object'
  return `application_object_model.${objectPath}.${field}`
}

function applicationObjectHasIssue(objectDef: { object_id?: string; name?: string }): boolean {
  const objectPath = objectDef.object_id || objectDef.name || 'application_object'
  return hasIssueForPrefix(`application_object_model.${objectPath}`)
}

function addDataMetric() {
  if (!definition.value) return
  definition.value.data_domain.metrics.push({ key: '', label: '', description: '' })
}

function addDataDimension() {
  if (!definition.value) return
  definition.value.data_domain.dimensions.push({ key: '', label: '', description: '' })
}

function addDataFilter() {
  if (!definition.value) return
  definition.value.data_domain.filters.push({ key: '', label: '', description: '' })
}

function addApplicationObject() {
  if (!definition.value) return
  definition.value.application_object_model.push({
    object_id: '',
    name: '',
    summary: '',
    key_field: '',
    fields: [],
    relationships: [],
    sensitive_field_names: [],
  })
}

function addObjectField(objectIndex: number) {
  if (!definition.value) return
  definition.value.application_object_model[objectIndex]?.fields.push({
    field_name: '',
    field_type: '',
    required: false,
    filterable: false,
    writable: false,
    sensitive: false,
    summary: '',
  })
}

function addObjectRelationship(objectIndex: number) {
  if (!definition.value) return
  definition.value.application_object_model[objectIndex]?.relationships.push({
    relationship_name: '',
    target_object_name: '',
    cardinality: '',
    summary: '',
  })
}
</script>

<template>
  <div class="developer-definition">
    <template v-if="project">
      <section class="page-header">
        <button class="back-link" type="button" @click="router.push(`/design/projects/${project.id}/developer`)">
          &larr; Back to Developer Design
        </button>
        <div class="page-kicker">Developer Design</div>
        <h1>Data Contract Formalization</h1>
        <p>
          Formalize the canonical data domain and application object model here. The current Data Access Pattern and Integration Pattern pages should consume these definitions instead of owning them.
        </p>
      </section>
      <ProjectIssueBanner :issue="pageIssue" title="Data Contract diagnostics" />
      <section v-if="!baseline" class="panel empty-panel">
        <h2>Developer baseline is not locked</h2>
        <p>Return to Developer Overview and lock Product Design before formalizing data contracts.</p>
      </section>

      <section v-else-if="!baselineAligned" class="panel empty-panel">
        <h2>Locked baseline is out of sync</h2>
        <p>Product Design changed after the current developer baseline was locked. Re-lock the baseline before continuing.</p>
      </section>

      <section v-else-if="definition" class="grid" :class="{ 'review-mode': !editing, 'edit-mode': editing }">
        <article
          id="data-domain"
          class="panel panel-full"
          :class="{ 'field-error-card': hasIssueForPrefix('data_domain') }"
        >
          <div class="panel-header">
            <h2>Data Domain</h2>
            <div class="header-actions">
              <button class="btn btn-secondary" type="button" @click="editing = !editing">
                {{ editing ? 'Review Data Contract' : 'Edit Data Contract' }}
              </button>
              <button v-if="editing" class="btn btn-primary" :disabled="saving" @click="saveDraft">
                {{ saving ? 'Saving…' : 'Save Formalization' }}
              </button>
            </div>
          </div>
          <p v-if="saveError" class="error">{{ saveError }}</p>
          <p class="panel-copy">
            Use this page for canonical data-shape truth only. The old Data Access Pattern page should follow this model, not invent it.
          </p>
          <p
            v-for="message in messagesForPrefix('data_domain')"
            :key="message"
            class="inline-field-error"
          >
            {{ message }}
          </p>
          <div class="review-summary-grid review-only">
            <div class="review-summary-card"><strong>Domain</strong><span>{{ definition.data_domain.domain_name || 'Not set' }}</span></div>
            <div class="review-summary-card"><strong>Grains</strong><span>{{ definition.data_domain.grains.join(', ') || 'Not specified' }}</span></div>
            <div class="review-summary-card"><strong>Result Modes</strong><span>{{ definition.data_domain.result_modes.join(', ') || 'Not specified' }}</span></div>
            <div class="review-summary-card"><strong>Metrics</strong><span>{{ definition.data_domain.metrics.length }}</span></div>
            <div class="review-summary-card"><strong>Dimensions</strong><span>{{ definition.data_domain.dimensions.length }}</span></div>
            <div class="review-summary-card"><strong>Filters</strong><span>{{ definition.data_domain.filters.length }}</span></div>
          </div>

          <div class="settings-grid edit-only">
            <label class="field field-wide" :class="{ 'field-error': hasIssueForPath('data_domain.domain_name') }">
              <span class="required-label">Domain Name</span>
              <input v-model="definition.data_domain.domain_name" class="input" placeholder="e.g. revenue_analytics" />
              <small v-for="message in messagesForPath('data_domain.domain_name')" :key="message" class="field-error-copy">{{ message }}</small>
            </label>
            <label class="field">
              <span>Grains</span>
              <input
                :value="definition.data_domain.grains.join(', ')"
                class="input"
                placeholder="aggregate, entity_detail"
                @input="definition.data_domain.grains = ($event.target as HTMLInputElement).value.split(',').map((value) => value.trim()).filter(Boolean)"
              />
            </label>
            <label class="field">
              <span>Result Modes</span>
              <input
                :value="definition.data_domain.result_modes.join(', ')"
                class="input"
                placeholder="exploratory, decision_grade"
                @input="definition.data_domain.result_modes = ($event.target as HTMLInputElement).value.split(',').map((value) => value.trim()).filter(Boolean)"
              />
            </label>
          </div>

          <div class="subsection">
            <div class="section-head">
              <h3>Metrics</h3>
              <button v-if="editing" class="btn btn-secondary" type="button" @click="addDataMetric">Add Metric</button>
            </div>
            <div v-if="!definition.data_domain.metrics.length" class="panel-copy">No metrics formalized yet.</div>
            <div v-for="(metric, index) in definition.data_domain.metrics" :key="`metric-${index}`" class="formalization-card">
              <div class="review-summary-grid review-only">
                <div class="review-summary-card"><strong>Key</strong><span>{{ metric.key || 'Not set' }}</span></div>
                <div class="review-summary-card"><strong>Label</strong><span>{{ metric.label || 'Not set' }}</span></div>
                <div class="review-summary-card field-wide"><strong>Description</strong><p>{{ metric.description || 'No description recorded.' }}</p></div>
              </div>
              <div class="settings-grid edit-only">
                <label class="field"><span>Key</span><input v-model="metric.key" class="input" /></label>
                <label class="field"><span>Label</span><input v-model="metric.label" class="input" /></label>
                <label class="field field-wide"><span>Description</span><textarea v-model="metric.description" class="textarea" rows="2" /></label>
              </div>
              <button v-if="editing" class="btn btn-danger" type="button" @click="definition.data_domain.metrics.splice(index, 1)">Remove Metric</button>
            </div>
          </div>

          <div class="subsection">
            <div class="section-head">
              <h3>Dimensions</h3>
              <button v-if="editing" class="btn btn-secondary" type="button" @click="addDataDimension">Add Dimension</button>
            </div>
            <div v-if="!definition.data_domain.dimensions.length" class="panel-copy">No dimensions formalized yet.</div>
            <div v-for="(dimension, index) in definition.data_domain.dimensions" :key="`dimension-${index}`" class="formalization-card">
              <div class="review-summary-grid review-only">
                <div class="review-summary-card"><strong>Key</strong><span>{{ dimension.key || 'Not set' }}</span></div>
                <div class="review-summary-card"><strong>Label</strong><span>{{ dimension.label || 'Not set' }}</span></div>
                <div class="review-summary-card field-wide"><strong>Description</strong><p>{{ dimension.description || 'No description recorded.' }}</p></div>
              </div>
              <div class="settings-grid edit-only">
                <label class="field"><span>Key</span><input v-model="dimension.key" class="input" /></label>
                <label class="field"><span>Label</span><input v-model="dimension.label" class="input" /></label>
                <label class="field field-wide"><span>Description</span><textarea v-model="dimension.description" class="textarea" rows="2" /></label>
              </div>
              <button v-if="editing" class="btn btn-danger" type="button" @click="definition.data_domain.dimensions.splice(index, 1)">Remove Dimension</button>
            </div>
          </div>

          <div class="subsection">
            <div class="section-head">
              <h3>Filters</h3>
              <button v-if="editing" class="btn btn-secondary" type="button" @click="addDataFilter">Add Filter</button>
            </div>
            <div v-if="!definition.data_domain.filters.length" class="panel-copy">No filters formalized yet.</div>
            <div v-for="(filterDef, index) in definition.data_domain.filters" :key="`filter-${index}`" class="formalization-card">
              <div class="review-summary-grid review-only">
                <div class="review-summary-card"><strong>Key</strong><span>{{ filterDef.key || 'Not set' }}</span></div>
                <div class="review-summary-card"><strong>Label</strong><span>{{ filterDef.label || 'Not set' }}</span></div>
                <div class="review-summary-card field-wide"><strong>Description</strong><p>{{ filterDef.description || 'No description recorded.' }}</p></div>
              </div>
              <div class="settings-grid edit-only">
                <label class="field"><span>Key</span><input v-model="filterDef.key" class="input" /></label>
                <label class="field"><span>Label</span><input v-model="filterDef.label" class="input" /></label>
                <label class="field field-wide"><span>Description</span><textarea v-model="filterDef.description" class="textarea" rows="2" /></label>
              </div>
              <button v-if="editing" class="btn btn-danger" type="button" @click="definition.data_domain.filters.splice(index, 1)">Remove Filter</button>
            </div>
          </div>
        </article>

        <article id="domain-concept-bindings" class="panel panel-full">
          <div class="panel-header">
            <h2>Domain Concept Bindings</h2>
          </div>
          <p class="panel-copy">
            Formalize how each Service Design domain concept is represented in the canonical data contract and object model.
          </p>
          <div v-if="definition.domain_concept_bindings.length" class="formalization-list">
            <article
              v-for="concept in definition.domain_concept_bindings"
              :key="concept.id"
              class="formalization-card"
              :class="{ 'field-error-card': conceptHasIssue(concept.id) }"
            >
              <div class="panel-header">
                <div>
                  <h3>{{ concept.concept_name }}</h3>
                  <p class="panel-copy">{{ concept.concept_detail || 'No concept detail recorded on the Service Design.' }}</p>
                  <p
                    v-for="message in messagesForPrefix(`domain_concept_bindings.${concept.id}`)"
                    :key="message"
                    class="inline-field-error"
                  >
                    {{ message }}
                  </p>
                </div>
              </div>
              <div class="review-summary-grid review-only">
                <div class="review-summary-card field-wide"><strong>Technical Representation</strong><p>{{ concept.technical_representation || 'Not formalized yet.' }}</p></div>
              </div>
              <div class="settings-grid edit-only">
                <label class="field field-wide" :class="{ 'field-error': hasIssueForPath(conceptPath(concept.id, 'technical_representation')) }">
                  <span class="required-label">Technical Representation</span>
                  <textarea
                    v-model="concept.technical_representation"
                    class="textarea"
                    rows="3"
                    placeholder="Explain how this domain concept is represented in metrics, dimensions, filters, objects, fields, or relationships."
                  />
                  <small v-for="message in messagesForPath(conceptPath(concept.id, 'technical_representation'))" :key="message" class="field-error-copy">{{ message }}</small>
                </label>
              </div>
            </article>
          </div>
          <p v-else class="panel-copy">No domain concepts are defined on the locked Service Design.</p>
        </article>

        <article id="application-object-model" class="panel panel-full">
          <div class="panel-header">
            <h2>Application Object Model</h2>
            <button v-if="editing" class="btn btn-secondary" type="button" @click="addApplicationObject">Add Object</button>
          </div>
          <p class="panel-copy">
            Formalize the canonical application object model here. The Integration Pattern page should reflect this model instead of owning it.
          </p>
          <div v-if="definition.application_object_model.length" class="formalization-list">
            <article
              v-for="(objectDef, objectIndex) in definition.application_object_model"
              :key="`object-${objectIndex}`"
              class="formalization-card"
              :class="{ 'field-error-card': applicationObjectHasIssue(objectDef) }"
            >
              <p
                v-for="message in messagesForPrefix(`application_object_model.${objectDef.object_id || objectDef.name || 'application_object'}`)"
                :key="message"
                class="inline-field-error"
              >
                {{ message }}
              </p>
              <div class="review-summary-grid review-only">
                <div class="review-summary-card"><strong>Object ID</strong><span>{{ objectDef.object_id || 'Not set' }}</span></div>
                <div class="review-summary-card"><strong>Name</strong><span>{{ objectDef.name || 'Not set' }}</span></div>
                <div class="review-summary-card"><strong>Key Field</strong><span>{{ objectDef.key_field || 'Not specified' }}</span></div>
                <div class="review-summary-card"><strong>Fields</strong><span>{{ objectDef.fields.length }}</span></div>
                <div class="review-summary-card"><strong>Relationships</strong><span>{{ objectDef.relationships.length }}</span></div>
                <div class="review-summary-card"><strong>Sensitive Fields</strong><span>{{ objectDef.sensitive_field_names.join(', ') || 'None recorded' }}</span></div>
                <div class="review-summary-card field-wide"><strong>Summary</strong><p>{{ objectDef.summary || 'No summary recorded.' }}</p></div>
              </div>
              <div class="settings-grid edit-only">
                <label class="field" :class="{ 'field-error': hasIssueForPath(applicationObjectPath(objectDef, 'object_id')) }">
                  <span class="required-label">Object ID</span>
                  <input v-model="objectDef.object_id" class="input" />
                  <small v-for="message in messagesForPath(applicationObjectPath(objectDef, 'object_id'))" :key="message" class="field-error-copy">{{ message }}</small>
                </label>
                <label class="field" :class="{ 'field-error': hasIssueForPath(applicationObjectPath(objectDef, 'name')) }">
                  <span class="required-label">Name</span>
                  <input v-model="objectDef.name" class="input" />
                  <small v-for="message in messagesForPath(applicationObjectPath(objectDef, 'name'))" :key="message" class="field-error-copy">{{ message }}</small>
                </label>
                <label class="field"><span>Key Field</span><input v-model="objectDef.key_field" class="input" /></label>
                <label class="field field-wide"><span>Summary</span><textarea v-model="objectDef.summary" class="textarea" rows="2" /></label>
                <label class="field field-wide">
                  <span>Sensitive Fields</span>
                  <input
                    :value="objectDef.sensitive_field_names.join(', ')"
                    class="input"
                    placeholder="ssn, email"
                    @input="objectDef.sensitive_field_names = ($event.target as HTMLInputElement).value.split(',').map((value) => value.trim()).filter(Boolean)"
                  />
                </label>
              </div>

              <div class="subsection">
                <div class="section-head">
                  <h3>Fields</h3>
                  <button v-if="editing" class="btn btn-secondary" type="button" @click="addObjectField(objectIndex)">Add Field</button>
                </div>
                <div v-if="!objectDef.fields.length" class="panel-copy">No fields formalized yet.</div>
                <div v-for="(field, fieldIndex) in objectDef.fields" :key="`field-${fieldIndex}`" class="nested-card">
                  <div class="review-summary-grid review-only">
                    <div class="review-summary-card"><strong>Name</strong><span>{{ field.field_name || 'Not set' }}</span></div>
                    <div class="review-summary-card"><strong>Type</strong><span>{{ field.field_type || 'Not set' }}</span></div>
                    <div class="review-summary-card"><strong>Flags</strong><span>{{ [field.required ? 'required' : '', field.filterable ? 'filterable' : '', field.writable ? 'writable' : '', field.sensitive ? 'sensitive' : ''].filter(Boolean).join(', ') || 'None' }}</span></div>
                    <div class="review-summary-card field-wide"><strong>Summary</strong><p>{{ field.summary || 'No summary recorded.' }}</p></div>
                  </div>
                  <div class="settings-grid edit-only">
                    <label class="field"><span>Name</span><input v-model="field.field_name" class="input" /></label>
                    <label class="field"><span>Type</span><input v-model="field.field_type" class="input" /></label>
                    <label class="field"><span>Required</span><select v-model="field.required" class="select"><option :value="true">Yes</option><option :value="false">No</option></select></label>
                    <label class="field"><span>Filterable</span><select v-model="field.filterable" class="select"><option :value="true">Yes</option><option :value="false">No</option></select></label>
                    <label class="field"><span>Writable</span><select v-model="field.writable" class="select"><option :value="true">Yes</option><option :value="false">No</option></select></label>
                    <label class="field"><span>Sensitive</span><select v-model="field.sensitive" class="select"><option :value="true">Yes</option><option :value="false">No</option></select></label>
                    <label class="field field-wide"><span>Summary</span><textarea v-model="field.summary" class="textarea" rows="2" /></label>
                  </div>
                  <button v-if="editing" class="btn btn-danger" type="button" @click="objectDef.fields.splice(fieldIndex, 1)">Remove Field</button>
                </div>
              </div>

              <div class="subsection">
                <div class="section-head">
                  <h3>Relationships</h3>
                  <button v-if="editing" class="btn btn-secondary" type="button" @click="addObjectRelationship(objectIndex)">Add Relationship</button>
                </div>
                <div v-if="!objectDef.relationships.length" class="panel-copy">No relationships formalized yet.</div>
                <div
                  v-for="(relationship, relationshipIndex) in objectDef.relationships"
                  :key="`relationship-${relationshipIndex}`"
                  class="nested-card"
                >
                  <div class="review-summary-grid review-only">
                    <div class="review-summary-card"><strong>Name</strong><span>{{ relationship.relationship_name || 'Not set' }}</span></div>
                    <div class="review-summary-card"><strong>Target</strong><span>{{ relationship.target_object_name || 'Not set' }}</span></div>
                    <div class="review-summary-card"><strong>Cardinality</strong><span>{{ relationship.cardinality || 'Not set' }}</span></div>
                    <div class="review-summary-card field-wide"><strong>Summary</strong><p>{{ relationship.summary || 'No summary recorded.' }}</p></div>
                  </div>
                  <div class="settings-grid edit-only">
                    <label class="field"><span>Name</span><input v-model="relationship.relationship_name" class="input" /></label>
                    <label class="field"><span>Target Object</span><input v-model="relationship.target_object_name" class="input" /></label>
                    <label class="field"><span>Cardinality</span><input v-model="relationship.cardinality" class="input" /></label>
                    <label class="field field-wide"><span>Summary</span><textarea v-model="relationship.summary" class="textarea" rows="2" /></label>
                  </div>
                  <button v-if="editing" class="btn btn-danger" type="button" @click="objectDef.relationships.splice(relationshipIndex, 1)">Remove Relationship</button>
                </div>
              </div>

              <button v-if="editing" class="btn btn-danger" type="button" @click="definition.application_object_model.splice(objectIndex, 1)">Remove Object</button>
            </article>
          </div>
          <p v-else class="panel-copy">No application objects are available yet from the linked developer drafts.</p>
        </article>
      </section>
    </template>
  </div>
</template>

<style scoped src="./developer-definition-shared.css"></style>
<style scoped>
.formalization-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.formalization-card {
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  padding: 1rem;
  background: var(--surface-depth-card);
}

.formalization-card.field-error-card {
  border-color: rgba(248, 113, 113, 0.66);
  background:
    linear-gradient(135deg, rgba(127, 29, 29, 0.26), rgba(15, 23, 42, 0.28)),
    rgba(15, 23, 42, 0.24);
  box-shadow: 0 0 0 1px rgba(248, 113, 113, 0.18), 0 18px 40px rgba(127, 29, 29, 0.12);
}

.subsection {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid rgba(148, 163, 184, 0.16);
}

.nested-card {
  border: 1px solid var(--surface-border-card);
  border-radius: 12px;
  padding: 0.85rem;
  background: var(--surface-depth-card);
}
</style>
