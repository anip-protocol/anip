<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { projectStore, checkDbAvailable, loadProjects, loadWorkspace } from '../design/project-store'
import {
  acceptFirstDesign,
  cloneProject,
  createProject,
  deleteProject,
  downloadRegistryTemplatePackage,
  interpretProjectIntentWithAssistant,
  listRegistryTemplates,
  type RegistryTemplateSummary,
} from '../design/project-api'
import { labelsWithConsumerMode, type ProjectConsumerMode } from '../design/consumer-mode'
import { requestConfirmation } from '../design/confirm'
import { createInitialFrontingSetup } from '../design/fronting-initial-setup'
import { getStarterTemplate, starterTemplatesForProjectType, type StarterTemplate } from '../design/starter-templates'
import { validateStarterTemplatePackage, type StarterTemplatePackage } from '../design/starter-template-package'

const route = useRoute()
const router = useRouter()
const workspaceId = computed(() => route.params.workspaceId as string)

const showCreateForm = ref(false)
const newName = ref('')
const newDomain = ref('')
const newSummary = ref('')
const newIntentBrief = ref('')
const newProjectType = ref<'standard' | 'governed_service_project'>('standard')
const selectedStarterTemplateId = ref('')
const selectedRegistryTemplateKey = ref('')
const selectedTemplateDocumentIds = ref<string[]>([])
const registryTemplateFilter = ref('')
const registryTemplates = ref<RegistryTemplateSummary[]>([])
const registryTemplatePackage = ref<StarterTemplatePackage | null>(null)
const registryTemplatesLoading = ref(false)
const registryTemplateLoading = ref(false)
const registryTemplateError = ref('')
const creating = ref<'empty' | 'brief' | null>(null)
const deletingProjectId = ref<string | null>(null)
const cleaningJunk = ref(false)

const dbAvailable = computed(() => projectStore.dbAvailable)
const projects = computed(() => projectStore.projects)
const loading = computed(() => projectStore.loading)
const error = computed(() => projectStore.error)
const workspace = computed(() => projectStore.activeWorkspace)
const readOnlyMode = computed(() => projectStore.runtimeStatus?.read_only_mode !== false)
const readOnlyReason = computed(
  () =>
    projectStore.runtimeStatus?.read_only_reason ||
    'Studio is running in read-only mode. Explore the design here, then run Studio locally to make changes.',
)
const junkProjects = computed(() =>
  projects.value.filter(project =>
    project.id.startsWith('proj-') &&
    !project.domain &&
    !project.summary &&
    (!project.labels || project.labels.length === 0),
  ),
)
const selectedIntegrationKind = computed(() => 'none' as const)
const availableStarterTemplates = computed(() => starterTemplatesForProjectType(newProjectType.value))
const availableRegistryTemplates = computed(() =>
  registryTemplates.value
    .filter((template) => template.project_type === newProjectType.value)
    .filter((template) => {
      const query = registryTemplateFilter.value.trim().toLowerCase()
      if (!query) return true
      const searchable = [
        template.template_id,
        template.template_version,
        template.template_kind,
        template.project_type,
        template.anip_spec_version,
        template.domain,
        template.industry,
        ...(template.systems ?? []),
        String(template.manifest?.template_title ?? ''),
      ].filter(Boolean).join(' ').toLowerCase()
      return searchable.includes(query)
    }),
)
const selectedStarterTemplate = computed(() => getStarterTemplate(selectedStarterTemplateId.value))
const selectedRegistryTemplateSummary = computed(() => {
  if (!selectedRegistryTemplateKey.value) return null
  return availableRegistryTemplates.value.find((template) => registryTemplateKey(template) === selectedRegistryTemplateKey.value) ?? null
})
const activeStarterTemplate = computed<StarterTemplate | null>(() => registryTemplatePackage.value?.template ?? selectedStarterTemplate.value)
const selectedStarterTemplatePreview = computed(() => {
  const template = activeStarterTemplate.value
  if (!template) return null
  return {
    documents: template.documents,
    connections: template.connections,
    discoveryRecords: template.discoveryRecords,
    capabilityMappings: template.capabilityMappings,
  }
})
const selectedStarterTemplateSource = computed(() => {
  if (registryTemplatePackage.value) return 'registry'
  if (selectedStarterTemplate.value) return 'built-in'
  return 'none'
})
const registryTemplateErrorTone = computed(() =>
  registryTemplateError.value.startsWith('Registry templates are unavailable')
    ? 'banner-warning'
    : 'banner-error',
)
const selectedTemplateDocumentIdSet = computed(() => new Set(selectedTemplateDocumentIds.value))

function registryTemplateKey(template: Pick<RegistryTemplateSummary, 'template_id' | 'template_version'>): string {
  return `${template.template_id}@${template.template_version}`
}

function setProjectListError(err: unknown) {
  projectStore.error = err instanceof Error ? err.message : String(err)
}

function clearProjectListError() {
  projectStore.error = null
}

function formatRegistryTemplateDiscoveryError(err: unknown): string {
  const message = err instanceof Error ? err.message : String(err)
  if (
    message.includes('/api/registry/templates') ||
    message.includes('Registry templates request failed') ||
    message.includes('Connection refused')
  ) {
    return 'Registry templates are unavailable. You can still create an empty project or use built-in templates. Configure a Registry in Settings, or start a local Registry, to use shared starter templates.'
  }
  return message
}

function routeForCreatedProject(projectId: string) {
  if (newProjectType.value === 'governed_service_project') {
    return {
      path: `/design/projects/${projectId}/fronting`,
    }
  }

  return { path: `/design/projects/${projectId}/pm` }
}

function inferredConsumerMode(): ProjectConsumerMode {
  return newProjectType.value === 'governed_service_project' ? 'agent_anip' : 'hybrid'
}

function resetCreateForm() {
  newName.value = ''
  newDomain.value = ''
  newSummary.value = ''
  newIntentBrief.value = ''
  newProjectType.value = 'standard'
  selectedStarterTemplateId.value = ''
  selectedRegistryTemplateKey.value = ''
  registryTemplateFilter.value = ''
  registryTemplatePackage.value = null
  selectedTemplateDocumentIds.value = []
}

function cancelCreateProject() {
  if (creating.value !== null) return
  resetCreateForm()
  showCreateForm.value = false
}

onMounted(async () => {
  await checkDbAvailable()
  if (projectStore.dbAvailable && workspaceId.value) {
    await loadWorkspace(workspaceId.value)
    await loadProjects(workspaceId.value)
  }
})

watch(workspaceId, async (id) => {
  if (projectStore.dbAvailable && id) {
    await loadWorkspace(id)
    await loadProjects(id)
  }
})

watch(newProjectType, () => {
  if (!availableStarterTemplates.value.some((template) => template.id === selectedStarterTemplateId.value)) {
    selectedStarterTemplateId.value = ''
  }
  if (!availableRegistryTemplates.value.some((template) => registryTemplateKey(template) === selectedRegistryTemplateKey.value)) {
    selectedRegistryTemplateKey.value = ''
    registryTemplatePackage.value = null
  }
})

watch(selectedStarterTemplateId, (templateId) => {
  const template = getStarterTemplate(templateId)
  if (!template) return
  selectedRegistryTemplateKey.value = ''
  registryTemplatePackage.value = null
  selectedTemplateDocumentIds.value = template.documents.map((document) => document.idSuffix)
  if (!newDomain.value.trim() && template.domain) newDomain.value = template.domain
  if (!newSummary.value.trim()) newSummary.value = template.summary
  if (!newIntentBrief.value.trim() && template.recommendedBrief) newIntentBrief.value = template.recommendedBrief
})

watch(showCreateForm, async (visible) => {
  if (visible && registryTemplates.value.length === 0) {
    await refreshRegistryTemplates()
  }
})

async function refreshRegistryTemplates() {
  registryTemplatesLoading.value = true
  registryTemplateError.value = ''
  try {
    const result = await listRegistryTemplates()
    registryTemplates.value = result.items
    if (result.warning && result.items.length === 0) {
      registryTemplateError.value = result.warning
    }
  } catch (err) {
    registryTemplateError.value = formatRegistryTemplateDiscoveryError(err)
  } finally {
    registryTemplatesLoading.value = false
  }
}

async function handleRegistryTemplateSelected() {
  selectedStarterTemplateId.value = ''
  registryTemplatePackage.value = null
  selectedTemplateDocumentIds.value = []
  registryTemplateError.value = ''
  const summary = selectedRegistryTemplateSummary.value
  if (!summary) return
  registryTemplateLoading.value = true
  try {
    const downloaded = await downloadRegistryTemplatePackage(summary.template_id, summary.template_version)
    const validationErrors = await validateStarterTemplatePackage(downloaded)
    if (validationErrors.length > 0) {
      throw new Error(`Registry starter template package failed Studio validation: ${validationErrors.join(' ')}`)
    }
    registryTemplatePackage.value = downloaded
    const template = downloaded.template
    selectedTemplateDocumentIds.value = []
    if (!newDomain.value.trim() && template.domain) newDomain.value = template.domain
    if (!newSummary.value.trim()) newSummary.value = template.summary
    if (!newIntentBrief.value.trim() && template.recommendedBrief) newIntentBrief.value = template.recommendedBrief
  } catch (err) {
    registryTemplateError.value = err instanceof Error ? err.message : String(err)
    selectedRegistryTemplateKey.value = ''
    registryTemplatePackage.value = null
  } finally {
    registryTemplateLoading.value = false
  }
}

function toggleTemplateDocument(idSuffix: string, checked: boolean) {
  const next = new Set(selectedTemplateDocumentIds.value)
  if (checked) {
    next.add(idSuffix)
  } else {
    next.delete(idSuffix)
  }
  selectedTemplateDocumentIds.value = Array.from(next)
}

function handleTemplateDocumentToggle(idSuffix: string, event: Event) {
  toggleTemplateDocument(idSuffix, Boolean((event.target as HTMLInputElement | null)?.checked))
}

function openProject(id: string) {
  const selectedProject = projects.value.find(project => project.id === id)
  if (selectedProject?.project_type === 'governed_service_project') {
    router.push({ path: `/design/projects/${id}/fronting` })
    return
  }
  router.push({ path: `/design/projects/${id}`, query: { view: 'overview' } })
}

async function handleCreate() {
  if (readOnlyMode.value) return
  const name = newName.value.trim()
  if (!name) return
  creating.value = 'empty'
  clearProjectListError()
  try {
    const id = crypto.randomUUID()
    await createProject({
      id,
      workspace_id: workspaceId.value,
      name,
      domain: newDomain.value.trim() || undefined,
      summary: newSummary.value.trim() || undefined,
      labels: labelsWithConsumerMode([], inferredConsumerMode()),
      project_type: newProjectType.value,
      integration_profile: { kind: selectedIntegrationKind.value, systems: [] },
    })
    const nextRoute = routeForCreatedProject(id)
    resetCreateForm()
    showCreateForm.value = false
    await loadProjects(workspaceId.value)
    router.push(nextRoute)
  } catch (err) {
    setProjectListError(err)
  } finally {
    creating.value = null
  }
}

function summaryFromBrief(brief: string): string {
  const cleaned = brief.replace(/\s+/g, ' ').trim()
  if (!cleaned) return ''
  if (cleaned.length <= 180) return cleaned
  return `${cleaned.slice(0, 177).trim()}...`
}

async function handleCreateFromBrief() {
  if (readOnlyMode.value) return
  const name = newName.value.trim()
  const brief = newIntentBrief.value.trim()
  if (!name || !brief) return
  creating.value = 'brief'
  clearProjectListError()
  const id = crypto.randomUUID()
  try {
    await createProject({
      id,
      workspace_id: workspaceId.value,
      name,
      domain: newDomain.value.trim() || undefined,
      summary: newSummary.value.trim() || summaryFromBrief(brief),
      labels: labelsWithConsumerMode([], inferredConsumerMode()),
      project_type: newProjectType.value,
      integration_profile: { kind: selectedIntegrationKind.value, systems: [] },
    })
    if (newProjectType.value === 'governed_service_project') {
      const template = activeStarterTemplate.value ?? undefined
      await createInitialFrontingSetup(id, workspaceId.value, {
        projectName: name,
        domain: newDomain.value.trim() || undefined,
        brief,
        starterTemplateId: selectedStarterTemplateId.value || undefined,
        starterTemplate: template,
        selectedDocumentIdSuffixes: template ? selectedTemplateDocumentIds.value : undefined,
      })
    } else {
      const interpretation = await interpretProjectIntentWithAssistant(id, brief)
      await acceptFirstDesign(id, brief, interpretation)
    }
    const nextRoute = routeForCreatedProject(id)
    resetCreateForm()
    showCreateForm.value = false
    await loadProjects(workspaceId.value)
    router.push(nextRoute)
  } catch (err) {
    try {
      await deleteProject(id)
      await loadProjects(workspaceId.value)
    } catch {
      // If cleanup fails, keep the original setup failure visible.
    }
    setProjectListError(
      err instanceof Error
        ? `Initial project setup failed and the partial project was removed: ${err.message}`
        : `Initial project setup failed and the partial project was removed: ${String(err)}`,
    )
  } finally {
    creating.value = null
  }
}

async function handleDeleteProject(projectId: string, projectName: string, event: Event) {
  if (readOnlyMode.value) return
  event.stopPropagation()
  const confirmed = await requestConfirmation({
    title: 'Delete project?',
    message: `Delete project "${projectName}"? This will remove its requirements, scenarios, shapes, and evaluations.`,
    confirmLabel: 'Delete Project',
    cancelLabel: 'Cancel',
    tone: 'danger',
  })
  if (!confirmed) {
    return
  }

  deletingProjectId.value = projectId
  try {
    await deleteProject(projectId)
    await loadProjects(workspaceId.value)
  } finally {
    deletingProjectId.value = null
  }
}

async function handleCloneProject(projectId: string, projectName: string, projectSummary: string, event: Event) {
  if (readOnlyMode.value) return
  event.stopPropagation()
  const cloneName = `${projectName} Copy`
  const confirmed = await requestConfirmation({
    title: 'Clone project?',
    message: `Create a full copy of "${projectName}" in this workspace as "${cloneName}"?`,
    confirmLabel: 'Clone Project',
    cancelLabel: 'Cancel',
    tone: 'neutral',
  })
  if (!confirmed) {
    return
  }

  const clone = await cloneProject(projectId, {
    workspace_id: workspaceId.value,
    name: cloneName,
    summary: projectSummary ? `${projectSummary} (copy)` : undefined,
  })
  await loadProjects(workspaceId.value)
  router.push({ path: `/design/projects/${clone.id}`, query: { view: 'overview' } })
}

async function handleCleanJunkProjects() {
  if (readOnlyMode.value) return
  if (junkProjects.value.length === 0) return
  const confirmed = await requestConfirmation({
    title: 'Delete test projects?',
    message: `Delete ${junkProjects.value.length} test projects from the local Studio database?`,
    confirmLabel: 'Delete Projects',
    cancelLabel: 'Cancel',
    tone: 'danger',
  })
  if (!confirmed) {
    return
  }

  cleaningJunk.value = true
  try {
    for (const project of junkProjects.value) {
      await deleteProject(project.id)
    }
    await loadProjects(workspaceId.value)
  } finally {
    cleaningJunk.value = false
  }
}
</script>

<template>
  <div class="project-list">
    <template v-if="!dbAvailable">
      <div class="banner banner-warning">Studio API unavailable — design workspaces are unavailable.</div>
    </template>
    <template v-else>
      <button class="back-link" @click="router.push('/design')">&larr; Workspaces</button>
      <h1 class="page-title">{{ workspace?.name || 'Workspace Projects' }}</h1>
      <p class="page-desc">{{ workspace?.summary || 'Manage the projects inside this workspace.' }}</p>
      <div v-if="readOnlyMode" class="banner banner-warning">
        {{ readOnlyReason }}
      </div>
      <div v-if="!readOnlyMode" class="toolbar">
        <button
          class="btn btn-primary"
          :disabled="readOnlyMode"
          @click="showCreateForm ? cancelCreateProject() : showCreateForm = true"
        >
          {{ showCreateForm ? 'Cancel' : 'Create Project' }}
        </button>
        <button
          v-if="junkProjects.length > 0"
          class="btn btn-secondary"
          @click="handleCleanJunkProjects"
          :disabled="cleaningJunk || readOnlyMode"
        >
          {{ cleaningJunk ? 'Cleaning...' : `Clean Test Projects (${junkProjects.length})` }}
        </button>
      </div>

      <!-- Inline create form -->
      <div v-if="showCreateForm && !readOnlyMode" class="create-form">
        <div class="field-group">
          <label class="field-label required-label">Project Name</label>
          <input
            v-model="newName"
            class="form-input form-input-lg"
            placeholder="Project name"
            @keyup.enter="handleCreate"
          />
        </div>
        <div class="field-group">
          <label class="field-label">Domain</label>
          <input
            v-model="newDomain"
            class="form-input"
            placeholder="Domain (for example: travel, devops, finance)"
          />
          <div class="field-help">
            Used as a lightweight business/domain hint for badges, first-draft templates, and generated definition defaults. Leave blank if the domain is not clear yet.
          </div>
        </div>
        <div class="field-group">
          <label class="field-label required-label">Project Type</label>
          <select v-model="newProjectType" class="form-select">
            <option value="standard">Standard ANIP project</option>
            <option value="governed_service_project">Govern an existing API or MCP server</option>
          </select>
          <div class="field-help">
            Use this when ANIP should sit in front of existing REST, GraphQL, MCP, database, or internal-service access. Studio opens these projects in Express Mode by default, with full advanced pages still available.
          </div>
        </div>
        <div v-if="newProjectType === 'governed_service_project'" class="field-group info-field">
          <label class="field-label">Fronting evidence comes next</label>
          <div class="field-help">
            Add API, MCP, GraphQL, database, or internal-service evidence in Express Mode. Studio uses that evidence to propose governed capabilities; the backend shape stays implementation metadata, not contract identity.
          </div>
        </div>
        <div v-if="availableStarterTemplates.length || registryTemplates.length || registryTemplatesLoading || registryTemplateError" class="field-group starter-template-field">
          <label class="field-label">Starter Template</label>
          <div class="template-source-grid">
            <div>
              <label class="field-sublabel">Built-in templates</label>
              <select v-model="selectedStarterTemplateId" class="form-select">
                <option value="">No built-in template</option>
                <option
                  v-for="template in availableStarterTemplates"
                  :key="template.id"
                  :value="template.id"
                >
                  {{ template.title }}
                </option>
              </select>
            </div>
            <div>
              <div class="template-row-label">
                <label class="field-sublabel">Registry templates</label>
                <button
                  class="action-link"
                  type="button"
                  :disabled="registryTemplatesLoading || registryTemplateLoading"
                  @click="refreshRegistryTemplates"
                >
                  {{ registryTemplatesLoading ? 'Loading...' : 'Refresh' }}
                </button>
              </div>
              <input
                v-model="registryTemplateFilter"
                class="form-input template-filter-input"
                placeholder="Filter by kind, spec, domain, industry, system, or title"
                :disabled="registryTemplatesLoading || registryTemplateLoading"
              />
              <select
                v-model="selectedRegistryTemplateKey"
                class="form-select"
                :disabled="registryTemplatesLoading || registryTemplateLoading"
                @change="handleRegistryTemplateSelected"
              >
                <option value="">No registry template</option>
                <option
                  v-for="template in availableRegistryTemplates"
                  :key="registryTemplateKey(template)"
                  :value="registryTemplateKey(template)"
                >
                  {{ template.manifest?.template_title || template.template_id }} @{{ template.template_version }}
                </option>
              </select>
            </div>
          </div>
          <div class="field-help">
            Optional. Starter templates import draft source docs, connection refs, backend operations, and mappings as template-suggested data. Registry templates are validated again by Studio, and source documents are opt-in before import.
          </div>
          <div v-if="registryTemplateError" :class="['banner', registryTemplateErrorTone, 'template-error']">{{ registryTemplateError }}</div>
          <div v-if="registryTemplateLoading" class="starter-template-card">
            Loading registry template package...
          </div>
          <div v-if="activeStarterTemplate" class="starter-template-card">
            <div class="starter-template-header">
              <div>
                <strong>{{ activeStarterTemplate.title }}</strong>
                <p>{{ activeStarterTemplate.description }}</p>
              </div>
              <span class="starter-template-id">
                {{ selectedStarterTemplateSource === 'registry' ? 'registry' : 'built-in' }}
                · {{ activeStarterTemplate.id }} · {{ activeStarterTemplate.anipSpecVersion }}
              </span>
            </div>
            <div class="starter-template-warning">
              Template-suggested data is imported as draft evidence. Review source docs, backend mappings, and governance before locking or generation.
              Source documents are imported only when selected below.
            </div>
            <div v-if="selectedStarterTemplatePreview" class="starter-template-metrics">
              <span>{{ selectedStarterTemplatePreview.documents.length }} source docs</span>
              <span>{{ selectedStarterTemplatePreview.connections.length }} connections</span>
              <span>{{ selectedStarterTemplatePreview.discoveryRecords.length }} backend operations</span>
              <span>{{ selectedStarterTemplatePreview.capabilityMappings.length }} capability mappings</span>
            </div>
            <div v-if="selectedStarterTemplatePreview" class="starter-template-preview-grid">
              <div class="starter-preview-section">
                <h4>Source Docs</h4>
                <ul>
                  <li
                    v-for="document in selectedStarterTemplatePreview.documents"
                    :key="document.idSuffix"
                  >
                    <label class="template-doc-choice">
                      <input
                        type="checkbox"
                        :checked="selectedTemplateDocumentIdSet.has(document.idSuffix)"
                        @change="handleTemplateDocumentToggle(document.idSuffix, $event)"
                      />
                      <span>{{ document.title }}</span>
                    </label>
                    <code>{{ document.filename }}</code>
                  </li>
                </ul>
              </div>
              <div class="starter-preview-section">
                <h4>Connections</h4>
                <ul>
                  <li
                    v-for="connection in selectedStarterTemplatePreview.connections"
                    :key="connection.idSuffix"
                  >
                    <span>{{ connection.display_name }}</span>
                    <code>{{ connection.backend_kind }} · {{ connection.secret_ref }}</code>
                  </li>
                </ul>
              </div>
              <div class="starter-preview-section">
                <h4>Backend Operations</h4>
                <ul>
                  <li
                    v-for="record in selectedStarterTemplatePreview.discoveryRecords"
                    :key="record.idSuffix"
                  >
                    <span>{{ record.operation_id }}</span>
                    <code>{{ record.method }} {{ record.path_template }}</code>
                  </li>
                </ul>
              </div>
              <div class="starter-preview-section">
                <h4>Capability Mappings</h4>
                <ul>
                  <li
                    v-for="mapping in selectedStarterTemplatePreview.capabilityMappings"
                    :key="mapping.idSuffix"
                  >
                    <span>{{ mapping.data.capability_id }}</span>
                    <code>{{ mapping.data.side_effect_level || mapping.data.execution_posture || 'mapped' }}</code>
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </div>
        <div class="field-group">
          <label class="field-label">Summary</label>
          <textarea
            v-model="newSummary"
            class="form-textarea"
            placeholder="What problem should this project explore?"
          ></textarea>
          <div class="field-help">
            Optional context for the project tile and first drafts. If you create from a brief and leave this blank, Studio derives a short summary from the brief.
          </div>
        </div>
        <div class="field-group">
          <label class="field-label">Plain-Language Brief</label>
          <textarea
            v-model="newIntentBrief"
            class="form-textarea form-textarea-brief"
            placeholder="Describe the product or service in normal language. Studio can turn this into the first requirements set, scenarios, and service design for you."
          ></textarea>
          <div class="field-help">
            Required for initial setup. When a starter template is selected, Studio combines this brief with the template-suggested source docs, connections, operations, and mappings.
          </div>
        </div>
        <div class="form-actions">
          <button
            v-if="!activeStarterTemplate"
            class="btn btn-primary btn-create"
            @click="handleCreate"
            :disabled="!newName.trim() || creating !== null"
          >
            {{ creating === 'empty' ? 'Creating...' : 'Create Empty Project' }}
          </button>
          <button
            class="btn btn-primary btn-create"
            @click="handleCreateFromBrief"
            :disabled="!newName.trim() || !newIntentBrief.trim() || creating !== null"
          >
            {{
              creating === 'brief'
                ? 'Shaping Project...'
                : activeStarterTemplate
                  ? 'Create From Template'
                  : 'Create Initial Project Setup'
            }}
          </button>
          <button
            class="btn btn-secondary btn-create"
            type="button"
            :disabled="creating !== null"
            @click="cancelCreateProject"
          >
            Cancel
          </button>
        </div>
      </div>

      <div v-if="!showCreateForm && loading && projects.length === 0" class="empty-state">
        Loading projects...
      </div>

      <div v-if="error" class="banner banner-error">{{ error }}</div>

      <div v-if="!showCreateForm && !loading && projects.length === 0 && !error" class="empty-state">
        No projects in this workspace yet. Create one to start shaping services and evaluating scenarios.
      </div>

      <div v-if="!showCreateForm" class="pack-grid">
        <div
          v-for="project in projects"
          :key="project.id"
          class="pack-card"
          @click="openProject(project.id)"
        >
          <div class="pack-header">
            <span class="domain-badge">{{ project.domain || 'general' }}</span>
          </div>
          <h3 class="card-name">{{ project.name }}</h3>
          <div v-if="project.project_type === 'governed_service_project'" class="project-type-line">
            Govern API / MCP project
          </div>
          <p class="card-summary">{{ project.summary || 'No summary' }}</p>
          <div v-if="!readOnlyMode || project.labels?.length" class="card-meta">
            <span v-if="project.labels?.length" class="card-labels">
              <span v-for="label in project.labels" :key="label" class="label-chip">{{ label }}</span>
            </span>
            <button
              v-if="!readOnlyMode"
              class="action-link"
              :disabled="deletingProjectId !== null || cleaningJunk || readOnlyMode"
              @click="handleCloneProject(project.id, project.name, project.summary, $event)"
            >
              Clone
            </button>
            <button
              v-if="!readOnlyMode"
              class="delete-link"
              :disabled="deletingProjectId !== null || cleaningJunk || readOnlyMode"
              @click="handleDeleteProject(project.id, project.name, $event)"
            >
              {{ deletingProjectId === project.id ? 'Deleting...' : 'Delete' }}
            </button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.project-list {
  padding: 2rem;
}

.back-link {
  background: none;
  border: none;
  color: var(--accent);
  font-size: 13px;
  cursor: pointer;
  padding: 0;
  margin-bottom: 0.75rem;
}

.page-title {
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 0.5rem;
}

.page-desc {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0 0 1.5rem;
  line-height: 1.6;
}

.banner {
  padding: 10px 16px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 1rem;
}

.banner-warning {
  background: rgba(251, 191, 36, 0.12);
  border: 1px solid rgba(251, 191, 36, 0.3);
  color: #fbbf24;
}

.banner-error {
  background: rgba(248, 113, 113, 0.12);
  border: 1px solid rgba(248, 113, 113, 0.3);
  color: var(--error);
}

.toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 1rem;
}

.btn {
  height: 36px;
  padding: 0 20px;
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

.create-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 1.5rem;
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.03), rgba(15, 23, 42, 0.06));
  border: 1px solid rgba(59, 130, 246, 0.18);
  border-radius: var(--radius);
  margin-bottom: 1rem;
  width: 100%;
  max-width: 760px;
  box-sizing: border-box;
}

.form-input,
.form-select {
  display: block;
  width: 100%;
  min-height: 48px;
  padding: 12px 16px;
  background: var(--bg-app);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 15px;
  outline: none;
  transition: border-color var(--transition);
  box-sizing: border-box;
  line-height: 1.2;
}

.form-input::placeholder {
  color: var(--text-muted);
}

.form-input:focus,
.form-select:focus {
  border-color: var(--border-focus);
}

.form-select {
  cursor: pointer;
}

.form-input-lg {
  min-height: 56px;
  padding: 14px 18px;
  font-size: 17px;
  font-weight: 600;
  border-width: 2px;
  line-height: 1.2;
}

.form-textarea {
  width: 100%;
  min-height: 132px;
  padding: 14px 16px;
  background: var(--bg-app);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 14px;
  line-height: 1.5;
  outline: none;
  resize: vertical;
  font-family: inherit;
  box-sizing: border-box;
}

.field-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.field-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.field-sublabel {
  display: block;
  margin-bottom: 6px;
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 700;
}

.template-source-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.template-row-label {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.template-filter-input {
  margin-bottom: 8px;
}

.template-error {
  margin: 0;
}

.required-label::after {
  content: ' *';
  color: #fca5a5;
  font-size: 14px;
  font-weight: 800;
  letter-spacing: 0;
  line-height: 0;
}

.field-help {
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-secondary);
}

.starter-template-card {
  display: grid;
  gap: 12px;
  padding: 14px;
  border: 1px solid rgba(59, 130, 246, 0.2);
  border-radius: var(--radius-sm);
  background: rgba(59, 130, 246, 0.07);
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.45;
}

.starter-template-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.starter-template-card strong {
  color: var(--text-primary);
  font-size: 13px;
}

.starter-template-card p {
  margin: 0;
}

.starter-template-id,
.starter-preview-section code {
  color: var(--text-muted);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}

.starter-template-warning {
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  border: 1px solid rgba(251, 191, 36, 0.28);
  background: rgba(251, 191, 36, 0.10);
  color: #fbbf24;
  font-size: 12px;
}

.starter-template-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 8px;
}

.starter-template-metrics span {
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-input);
  color: var(--text-primary);
  font-weight: 700;
}

.starter-template-preview-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.starter-preview-section {
  min-width: 0;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-app);
}

.starter-preview-section h4 {
  margin: 0 0 8px;
  color: var(--text-primary);
  font-size: 12px;
  font-weight: 800;
}

.starter-preview-section ul {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.starter-preview-section li {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.starter-preview-section span,
.starter-preview-section code {
  overflow-wrap: anywhere;
}

.starter-preview-section span {
  color: var(--text-primary);
  font-weight: 600;
}

.starter-preview-section code {
  font-size: 11px;
}

.template-doc-choice {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  color: var(--text-primary);
}

.template-doc-choice input {
  margin-top: 2px;
}

.form-textarea-brief {
  min-height: 180px;
}

.form-actions {
  display: flex;
  justify-content: flex-start;
  gap: 12px;
  flex-wrap: wrap;
}

.btn-create {
  width: auto;
  min-width: 160px;
}

.empty-state {
  padding: 2rem;
  text-align: center;
  color: var(--text-muted);
  font-size: 14px;
}

.pack-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

.pack-card {
  padding: 1.25rem;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  cursor: pointer;
  transition: all var(--transition);
}

.pack-card:hover {
  border-color: var(--accent);
  background: var(--bg-hover);
}

.pack-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.domain-badge {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-muted);
}

.result-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 10px;
}

.result-handled {
  background: rgba(52, 211, 153, 0.15);
  color: var(--design-handled, #34d399);
}

.result-partial {
  background: rgba(251, 191, 36, 0.15);
  color: var(--design-partial, #fbbf24);
}

.result-requires-glue {
  background: rgba(248, 113, 113, 0.15);
  color: var(--design-glue, #f87171);
}

.card-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 0.5rem;
}

.project-type-line {
  display: inline-flex;
  width: fit-content;
  margin: 0 0 0.5rem;
  padding: 3px 8px;
  border-radius: 999px;
  background: rgba(59, 130, 246, 0.10);
  color: var(--accent);
  font-size: 11px;
  font-weight: 600;
}

.card-summary {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
  margin: 0 0 0.5rem;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.card-labels {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.label-chip {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 8px;
  background: var(--bg-hover);
  color: var(--text-muted);
}

.delete-link {
  border: none;
  background: transparent;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  padding: 0;
}

.action-link {
  border: none;
  background: transparent;
  color: var(--accent);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  padding: 0;
}

.action-link:hover:not(:disabled) {
  color: var(--accent-hover);
}

.delete-link {
  color: #ef4444;
}

.delete-link:hover:not(:disabled) {
  color: #dc2626;
}

.delete-link:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

@media (max-width: 760px) {
  .template-source-grid,
  .starter-template-header,
  .starter-template-preview-grid {
    grid-template-columns: 1fr;
  }

  .starter-template-header {
    display: grid;
  }
}
</style>
