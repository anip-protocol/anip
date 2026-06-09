<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { loadProject, projectStore } from '../design/project-store'
import {
  createPmArtifact,
  createRequirements,
  createScenario,
  deletePmArtifact,
  updatePmArtifact,
} from '../design/project-api'
import { buildBusinessBrief, buildPmSpec, downloadTextDocument } from '../design/shared-artifacts'
import { requestConfirmation } from '../design/confirm'
import { formatStudioTimestamp } from '../design/time'
import { DESIGN_TRACEABILITY_ARTIFACT_TYPE } from '../design/traceability'
import { makeRequirementsTemplate, slugify } from '../design/intent-drafts'
import { refreshArtifacts, setActiveRequirements, setActiveScenario } from '../design/project-store'
import {
  ACTOR_MODEL_ARTIFACT_TYPE,
  BUSINESS_AREAS_ARTIFACT_TYPE,
  NON_GOALS_ARTIFACT_TYPE,
  PERMISSION_INTENT_ARTIFACT_TYPE,
  PRODUCT_SUMMARY_ARTIFACT_TYPE,
  SUCCESS_CRITERIA_ARTIFACT_TYPE,
  cloneProductDesignData,
  defaultActorModelData,
  defaultBusinessAreasData,
  defaultNonGoalsData,
  defaultPermissionIntentData,
  defaultProductSummaryData,
  defaultSuccessCriteriaData,
  findActorModelArtifact,
  findBusinessAreasArtifact,
  findNonGoalsArtifact,
  findPermissionIntentArtifact,
  findProductSummaryArtifact,
  findSuccessCriteriaArtifact,
  isActorModelComplete,
  isBusinessAreasComplete,
  isNonGoalsComplete,
  isPermissionIntentComplete,
  isProductSummaryComplete,
  isSuccessCriteriaComplete,
  persistedPmArtifactStatus,
  productDesignArtifactId,
} from '../design/product-design'

const route = useRoute()
const router = useRouter()

const projectId = computed(() => route.params.projectId as string)
const project = computed(() => projectStore.activeProject)
const loading = computed(() => projectStore.loading)
const error = computed(() => projectStore.error)
const savingType = ref<string | null>(null)
const saveError = ref<string | null>(null)
const promotingArtifactId = ref<string | null>(null)
const promoteError = ref<string | null>(null)
const readOnlyMode = computed(() => projectStore.runtimeStatus?.read_only_mode !== false)
const readOnlyReason = computed(() =>
  projectStore.runtimeStatus?.read_only_reason
  || 'Studio is running in read-only mode. Explore the design, then download and run Studio locally to make changes.',
)
const assistantArtifactFilter = computed(() => {
  const raw = route.query.assistantType
  return typeof raw === 'string' && raw.trim().length > 0 ? raw.trim() : null
})

async function ensureLoaded() {
  if (!projectId.value) return
  if (projectStore.activeProject?.id === projectId.value) return
  await loadProject(projectId.value)
}

onMounted(ensureLoaded)
watch(projectId, ensureLoaded)

const activeRequirements = computed(() =>
  projectStore.artifacts.requirements.find((item) => item.id === projectStore.activeRequirementsId)
  ?? projectStore.artifacts.requirements.find((item) => item.role === 'primary')
  ?? projectStore.artifacts.requirements[0]
  ?? null,
)

const activeScenario = computed(() =>
  projectStore.artifacts.scenarios.find((item) => item.id === projectStore.activeScenarioId)
  ?? projectStore.artifacts.scenarios[0]
  ?? null,
)

const activeShape = computed(() =>
  projectStore.artifacts.shapes.find((item) => item.id === projectStore.activeShapeId)
  ?? projectStore.artifacts.shapes[0]
  ?? null,
)

const latestEvaluation = computed(() => {
  const records = [...projectStore.artifacts.evaluations]
  records.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
  return records[0] ?? null
})

const pmSpecContent = computed(() => buildPmSpec({
  project: project.value,
  requirements: activeRequirements.value,
  scenarios: projectStore.artifacts.scenarios,
  scenario: activeScenario.value,
  shape: activeShape.value,
  evaluation: latestEvaluation.value,
}))

const businessBriefContent = computed(() => buildBusinessBrief({
  project: project.value,
  requirements: activeRequirements.value,
  scenario: activeScenario.value,
  shape: activeShape.value,
  evaluation: latestEvaluation.value,
}))

const sourceInputs = computed(() => ({
  requirements: activeRequirements.value
    ? {
        id: activeRequirements.value.id,
        title: activeRequirements.value.title,
        hash: activeRequirements.value.content_hash,
        updated_at: activeRequirements.value.updated_at,
      }
    : null,
  scenario: activeScenario.value
    ? {
        id: activeScenario.value.id,
        title: activeScenario.value.title,
        hash: activeScenario.value.content_hash,
        updated_at: activeScenario.value.updated_at,
      }
    : null,
  shape: activeShape.value
    ? {
        id: activeShape.value.id,
        title: activeShape.value.title,
        hash: activeShape.value.content_hash,
        updated_at: activeShape.value.updated_at,
      }
    : null,
  evaluation: latestEvaluation.value
    ? {
        id: latestEvaluation.value.id,
        created_at: latestEvaluation.value.created_at,
        requirements_hash: latestEvaluation.value.requirements_hash,
        scenario_hash: latestEvaluation.value.scenario_hash,
        shape_hash: latestEvaluation.value.shape_hash,
      }
    : null,
}))

const persistedArtifacts = computed(() => {
  return projectStore.artifacts.pmArtifacts
    .filter((artifact) =>
      artifact.data?.artifact_type !== DESIGN_TRACEABILITY_ARTIFACT_TYPE
      && (artifact.data?.artifact_type === 'pm_spec' || artifact.data?.artifact_type === 'business_brief'),
    )
    .sort((a, b) =>
    new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
  )
})

const assistantArtifacts = computed(() => {
  return projectStore.artifacts.pmArtifacts
    .filter((artifact) =>
      ['assistant_product_design_draft_bundle', 'assistant_developer_design_draft_bundle', 'assistant_audit_log', 'assistant_requirement_candidates', 'assistant_scenario_candidates', 'assistant_business_summary_candidates', 'assistant_actor_model_candidates', 'assistant_business_area_candidates', 'assistant_permission_intent_candidates', 'assistant_non_goal_candidates', 'assistant_success_criteria_candidates', 'assistant_service_design_candidates', 'assistant_capability_formalization_candidates', 'assistant_runtime_policy_binding_candidates', 'assistant_input_contract_candidates', 'assistant_verification_expectation_candidates', 'assistant_backend_binding_candidates', 'assistant_missing_business_info', 'assistant_section_clarifications']
        .includes(String(artifact.data?.artifact_type ?? ''))
      && (!assistantArtifactFilter.value || assistantArtifactFilter.value === String(artifact.data?.artifact_type ?? '')),
    )
    .sort((a, b) =>
      new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
    )
})

function artifactContent(record: Record<string, any>): string {
  return String(record?.content ?? '')
}

function artifactTypeLabel(type: string): string {
  return type === 'business_brief' ? 'Business Brief' : 'PM Spec'
}

function assistantArtifactTypeLabel(type: string): string {
  if (type === 'assistant_product_design_draft_bundle') return 'Assistant Product Design Draft Bundle'
  if (type === 'assistant_developer_design_draft_bundle') return 'Assistant Developer Design Draft Bundle'
  if (type === 'assistant_audit_log') return 'Assistant Audit Log'
  if (type === 'assistant_requirement_candidates') return 'Assistant Requirement Candidates'
  if (type === 'assistant_scenario_candidates') return 'Assistant Scenario Candidates'
  if (type === 'assistant_business_summary_candidates') return 'Assistant Business Summary Candidates'
  if (type === 'assistant_actor_model_candidates') return 'Assistant Actor Model Candidates'
  if (type === 'assistant_business_area_candidates') return 'Assistant Business Area Candidates'
  if (type === 'assistant_permission_intent_candidates') return 'Assistant Permission Intent Candidates'
  if (type === 'assistant_non_goal_candidates') return 'Assistant Non-Goal Candidates'
  if (type === 'assistant_success_criteria_candidates') return 'Assistant Success Criteria Candidates'
  if (type === 'assistant_service_design_candidates') return 'Assistant Service Design Candidates'
  if (type === 'assistant_capability_formalization_candidates') return 'Assistant Capability Formalization Candidates'
  if (type === 'assistant_runtime_policy_binding_candidates') return 'Assistant Runtime Policy Binding Candidates'
  if (type === 'assistant_input_contract_candidates') return 'Assistant Input Contract Candidates'
  if (type === 'assistant_verification_expectation_candidates') return 'Assistant Verification Expectation Candidates'
  if (type === 'assistant_backend_binding_candidates') return 'Assistant Backend Binding Candidates'
  if (type === 'assistant_missing_business_info') return 'Assistant Missing Business Info'
  if (type === 'assistant_section_clarifications') return 'Assistant Section Clarifications'
  return 'Assistant Proposal'
}

function clearAssistantArtifactFilter() {
  if (!project.value) return
  router.replace(`/design/projects/${project.value.id}/pm-artifacts`)
}

function prettyDate(value: string | null | undefined): string {
  return formatStudioTimestamp(value)
}

function assistantAcceptedPayload(record: Record<string, any>): Array<Record<string, any>> {
  const payload = record?.accepted_payload
  return Array.isArray(payload) ? payload.filter((item): item is Record<string, any> => typeof item === 'object' && item !== null) : []
}

function promotedArtifactIds(record: Record<string, any>): string[] {
  const ids = record?.promoted_artifact_ids
  return Array.isArray(ids) ? ids.map((value) => String(value)).filter(Boolean) : []
}

function canPromoteArtifact(record: Record<string, any>): boolean {
  const type = String(record?.artifact_type ?? '')
  return (
    (type === 'assistant_requirement_candidates'
      || type === 'assistant_scenario_candidates'
      || type === 'assistant_business_summary_candidates'
      || type === 'assistant_actor_model_candidates'
      || type === 'assistant_business_area_candidates'
      || type === 'assistant_permission_intent_candidates'
      || type === 'assistant_non_goal_candidates'
      || type === 'assistant_success_criteria_candidates')
    && assistantAcceptedPayload(record).length > 0
  )
}

function makeArtifactPayload(type: 'pm_spec' | 'business_brief') {
  const generatedAt = new Date().toISOString()
  return {
    artifact_type: type,
    generated_at: generatedAt,
    content: type === 'pm_spec' ? pmSpecContent.value : businessBriefContent.value,
    source_inputs: sourceInputs.value,
    snapshot_linkage: latestEvaluation.value
      ? {
          kind: 'evaluation_input_snapshot',
          evaluation_id: latestEvaluation.value.id,
        }
      : null,
  }
}

async function saveFrozenArtifact(type: 'pm_spec' | 'business_brief') {
  if (readOnlyMode.value || !project.value) return
  savingType.value = type
  saveError.value = null
  try {
    const titlePrefix = type === 'pm_spec' ? 'PM Spec Snapshot' : 'Business Brief Snapshot'
    const generatedAt = new Date().toISOString()
    const stamp = generatedAt.replace(/[:.]/g, '-')
    await createPmArtifact(project.value.id, {
      id: `${type}-${stamp}`,
      title: `${titlePrefix} ${formatStudioTimestamp(generatedAt)}`,
      data: makeArtifactPayload(type),
    })
    await loadProject(project.value.id)
  } catch (err) {
    saveError.value = err instanceof Error ? err.message : String(err)
  } finally {
    savingType.value = null
  }
}

async function removeFrozenArtifact(artifactId: string) {
  if (readOnlyMode.value || !project.value) return
  const confirmed = await requestConfirmation({
    title: 'Delete this PM artifact?',
    message: 'This removes the saved frozen export from Studio history.',
    confirmLabel: 'Delete Artifact',
    cancelLabel: 'Cancel',
    tone: 'danger',
  })
  if (!confirmed) return
  await deletePmArtifact(project.value.id, artifactId)
  await loadProject(project.value.id)
}

async function archiveAssistantArtifact(artifactId: string) {
  if (readOnlyMode.value || !project.value) return
  const confirmed = await requestConfirmation({
    title: 'Archive this assistant artifact?',
    message: 'This removes the accepted proposal review artifact from Studio history. Promoted requirements or scenarios are not affected.',
    confirmLabel: 'Archive Artifact',
    cancelLabel: 'Cancel',
    tone: 'danger',
  })
  if (!confirmed) return
  await deletePmArtifact(project.value.id, artifactId)
  await loadProject(project.value.id)
}

function requirementDataFromAssistantItem(item: Record<string, any>) {
  const template = makeRequirementsTemplate(project.value?.name || 'new-service', project.value?.domain || '')
  const constraints = (template.business_constraints ?? {}) as Record<string, any>
  constraints.assistant_candidate_summary = String(item.body ?? '')
  constraints.assistant_candidate_rationale = String(item.rationale ?? '')
  return template
}

function scenarioDataFromAssistantItem(item: Record<string, any>) {
  const title = String(item.title ?? '').trim() || 'Scenario'
  const narrative = String(item.body ?? '').trim() || 'Describe the real business situation this design should handle.'
  const rationale = String(item.rationale ?? '').trim()
  return {
    scenario: {
      name: slugify(title) || `scenario-${crypto.randomUUID()}`,
      category: 'safety',
      narrative,
      context: {},
      participating_services: [],
      orchestration_steps: [],
      expected_behavior: [narrative],
      expected_anip_support: rationale ? [rationale] : ['Make the bounded behavior and stop conditions explicit in the contract.'],
    },
  }
}

function decodePointerToken(token: string) {
  return token.replace(/~1/g, '/').replace(/~0/g, '~')
}

function cloneJson<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function applyAcceptedPatches<T>(base: T, patches: Array<Record<string, any>>): T {
  const root = cloneJson(base) as any

  for (const patch of patches) {
    const path = String(patch.path ?? '')
    const op = String(patch.op ?? '').toLowerCase()
    if (!path.startsWith('/')) continue
    const segments = path.split('/').slice(1).map(decodePointerToken)
    if (!segments.length) continue

    let target = root
    for (let index = 0; index < segments.length - 1; index += 1) {
      const segment = segments[index]
      const nextSegment = segments[index + 1]
      if (Array.isArray(target)) {
        const arrayIndex = segment === '-' ? target.length : Number(segment)
        if (!Number.isInteger(arrayIndex) || arrayIndex < 0) break
        if (target[arrayIndex] == null) {
          target[arrayIndex] = nextSegment === '-' || /^\d+$/.test(nextSegment) ? [] : {}
        }
        target = target[arrayIndex]
      } else {
        if (!(segment in target) || target[segment] == null) {
          target[segment] = nextSegment === '-' || /^\d+$/.test(nextSegment) ? [] : {}
        }
        target = target[segment]
      }
    }

    const last = segments[segments.length - 1]
    if (Array.isArray(target)) {
      const arrayIndex = last === '-' ? target.length : Number(last)
      if (!Number.isInteger(arrayIndex) || arrayIndex < 0) continue
      if (op === 'remove') {
        target.splice(arrayIndex, 1)
      } else if (op === 'add') {
        if (last === '-') target.push(cloneJson(patch.value))
        else target.splice(arrayIndex, 0, cloneJson(patch.value))
      } else {
        target[arrayIndex] = cloneJson(patch.value)
      }
      continue
    }

    if (op === 'remove') {
      delete target[last]
    } else {
      target[last] = cloneJson(patch.value)
    }
  }

  return root as T
}

function buildProductDesignPromotion(record: Record<string, any>) {
  const artifactType = String(record?.artifact_type ?? '')
  const patches = assistantAcceptedPayload(record)

  if (artifactType === 'assistant_business_summary_candidates') {
    const existing = (findProductSummaryArtifact(projectStore.artifacts.pmArtifacts)?.data as Record<string, any> | undefined) ?? defaultProductSummaryData()
    const data = applyAcceptedPatches(cloneProductDesignData(existing), patches)
    return {
      artifactId: productDesignArtifactId(project.value!.id, PRODUCT_SUMMARY_ARTIFACT_TYPE),
      title: 'Business Summary',
      status: persistedPmArtifactStatus(isProductSummaryComplete(data as any)),
      data,
      path: `/design/projects/${project.value!.id}/product-summary`,
    }
  }

  if (artifactType === 'assistant_actor_model_candidates') {
    const existing = (findActorModelArtifact(projectStore.artifacts.pmArtifacts)?.data as Record<string, any> | undefined) ?? defaultActorModelData()
    const data = applyAcceptedPatches(cloneProductDesignData(existing), patches)
    return {
      artifactId: productDesignArtifactId(project.value!.id, ACTOR_MODEL_ARTIFACT_TYPE),
      title: 'Actor Model',
      status: persistedPmArtifactStatus(isActorModelComplete(data as any)),
      data,
      path: `/design/projects/${project.value!.id}/actor-model`,
    }
  }

  if (artifactType === 'assistant_business_area_candidates') {
    const existing = (findBusinessAreasArtifact(projectStore.artifacts.pmArtifacts)?.data as Record<string, any> | undefined) ?? defaultBusinessAreasData()
    const data = applyAcceptedPatches(cloneProductDesignData(existing), patches)
    return {
      artifactId: productDesignArtifactId(project.value!.id, BUSINESS_AREAS_ARTIFACT_TYPE),
      title: 'Business Areas',
      status: persistedPmArtifactStatus(isBusinessAreasComplete(data as any)),
      data,
      path: `/design/projects/${project.value!.id}/business-areas`,
    }
  }

  if (artifactType === 'assistant_permission_intent_candidates') {
    const existing = (findPermissionIntentArtifact(projectStore.artifacts.pmArtifacts)?.data as Record<string, any> | undefined) ?? defaultPermissionIntentData()
    const data = applyAcceptedPatches(cloneProductDesignData(existing), patches)
    return {
      artifactId: productDesignArtifactId(project.value!.id, PERMISSION_INTENT_ARTIFACT_TYPE),
      title: 'Permission Intent',
      status: persistedPmArtifactStatus(isPermissionIntentComplete(data as any)),
      data,
      path: `/design/projects/${project.value!.id}/permission-intent`,
    }
  }

  if (artifactType === 'assistant_non_goal_candidates') {
    const existing = (findNonGoalsArtifact(projectStore.artifacts.pmArtifacts)?.data as Record<string, any> | undefined) ?? defaultNonGoalsData()
    const data = applyAcceptedPatches(cloneProductDesignData(existing), patches)
    return {
      artifactId: productDesignArtifactId(project.value!.id, NON_GOALS_ARTIFACT_TYPE),
      title: 'Non-Goals',
      status: persistedPmArtifactStatus(isNonGoalsComplete(data as any)),
      data,
      path: `/design/projects/${project.value!.id}/non-goals`,
    }
  }

  if (artifactType === 'assistant_success_criteria_candidates') {
    const existing = (findSuccessCriteriaArtifact(projectStore.artifacts.pmArtifacts)?.data as Record<string, any> | undefined) ?? defaultSuccessCriteriaData()
    const data = applyAcceptedPatches(cloneProductDesignData(existing), patches)
    return {
      artifactId: productDesignArtifactId(project.value!.id, SUCCESS_CRITERIA_ARTIFACT_TYPE),
      title: 'Success Criteria',
      status: persistedPmArtifactStatus(isSuccessCriteriaComplete(data as any)),
      data,
      path: `/design/projects/${project.value!.id}/success-criteria`,
    }
  }

  return null
}

async function promoteAssistantArtifact(artifactId: string) {
  if (readOnlyMode.value || !project.value) return
  const artifact = projectStore.artifacts.pmArtifacts.find((item) => item.id === artifactId)
  if (!artifact) return

  const artifactType = String(artifact.data?.artifact_type ?? '')
  const acceptedItems = assistantAcceptedPayload(artifact.data)
  if (!acceptedItems.length) return

  promotingArtifactId.value = artifactId
  promoteError.value = null
  try {
    const createdIds: string[] = []
    if (artifactType === 'assistant_requirement_candidates') {
      for (const item of acceptedItems) {
        const created = await createRequirements(project.value.id, {
          id: `req-${crypto.randomUUID()}`,
          title: String(item.title ?? 'Requirements Candidate').trim() || 'Requirements Candidate',
          data: requirementDataFromAssistantItem(item),
        })
        createdIds.push(created.id)
      }
      if (createdIds[0]) {
        setActiveRequirements(createdIds[0])
      }
    } else if (artifactType === 'assistant_scenario_candidates') {
      for (const item of acceptedItems) {
        const created = await createScenario(project.value.id, {
          id: `scn-${crypto.randomUUID()}`,
          title: String(item.title ?? 'Scenario Candidate').trim() || 'Scenario Candidate',
          data: scenarioDataFromAssistantItem(item),
        })
        createdIds.push(created.id)
      }
      if (createdIds[0]) {
        setActiveScenario(createdIds[0])
      }
    } else if (
      artifactType === 'assistant_business_summary_candidates'
      || artifactType === 'assistant_actor_model_candidates'
      || artifactType === 'assistant_business_area_candidates'
      || artifactType === 'assistant_permission_intent_candidates'
      || artifactType === 'assistant_non_goal_candidates'
      || artifactType === 'assistant_success_criteria_candidates'
    ) {
      const promotion = buildProductDesignPromotion(artifact.data)
      if (!promotion) return
      const existing = projectStore.artifacts.pmArtifacts.find((item) => item.id === promotion.artifactId)
      if (existing) {
        await updatePmArtifact(project.value.id, promotion.artifactId, {
          title: promotion.title,
          status: promotion.status,
          data: promotion.data,
        })
      } else {
        await createPmArtifact(project.value.id, {
          id: promotion.artifactId,
          title: promotion.title,
          data: promotion.data,
        })
      }
      createdIds.push(promotion.artifactId)
    } else {
      return
    }

    await updatePmArtifact(project.value.id, artifact.id, {
      data: {
        ...artifact.data,
        promoted_artifact_ids: [...new Set([...promotedArtifactIds(artifact.data), ...createdIds])],
      },
    })
    await refreshArtifacts()

    if (artifactType === 'assistant_requirement_candidates' && createdIds[0]) {
      router.push(`/design/projects/${project.value.id}/requirements/${createdIds[0]}`)
      return
    }
    if (artifactType === 'assistant_scenario_candidates' && createdIds[0]) {
      router.push(`/design/projects/${project.value.id}/scenarios/${createdIds[0]}`)
      return
    }
    if (createdIds[0]) {
      const promotion = buildProductDesignPromotion(artifact.data)
      if (promotion) {
        router.push(promotion.path)
      }
    }
  } catch (err) {
    promoteError.value = err instanceof Error ? err.message : String(err)
  } finally {
    promotingArtifactId.value = null
  }
}

async function copy(content: string) {
  await navigator.clipboard.writeText(content)
}

function download(filename: string, content: string) {
  downloadTextDocument(filename, content)
}
</script>

<template>
  <div class="pm-artifacts-view">
    <div v-if="loading && !project" class="empty-state">Loading PM artifacts...</div>
    <div v-else-if="error" class="banner banner-error">{{ error }}</div>
    <template v-else-if="project">
      <section class="page-header">
        <div class="page-kicker">PM Artifacts</div>
        <h1>{{ project.name }}</h1>
        <p>Studio can generate PM-facing exports from current project state and freeze them as durable artifacts with source-input traceability.</p>
      </section>

      <div v-if="saveError" class="banner banner-error">{{ saveError }}</div>
      <div v-if="promoteError" class="banner banner-error">{{ promoteError }}</div>
      <div v-if="readOnlyMode" class="banner banner-warning readonly-banner">
        {{ readOnlyReason }}
      </div>

      <section class="grid">
        <article class="panel">
          <div class="panel-header">
            <div>
              <h2>Current PM Spec</h2>
              <div class="panel-meta">Generated on demand from the active requirements, scenario, shape, and latest evaluation.</div>
            </div>
            <div class="actions">
              <button class="btn btn-secondary" @click="copy(pmSpecContent)">Copy</button>
              <button class="btn btn-secondary" @click="download(`${project.id}-pm-spec.md`, pmSpecContent)">Download</button>
              <button class="btn btn-primary" :disabled="readOnlyMode || savingType === 'pm_spec'" @click="saveFrozenArtifact('pm_spec')">
                {{ savingType === 'pm_spec' ? 'Freezing…' : 'Save / Freeze' }}
              </button>
            </div>
          </div>
          <div class="trace-card">
            <div class="trace-row"><span>Generated At</span><strong>{{ prettyDate(new Date().toISOString()) }}</strong></div>
            <div class="trace-row"><span>Requirements</span><strong>{{ sourceInputs.requirements?.id || 'Not selected' }}</strong></div>
            <div class="trace-row"><span>Scenario</span><strong>{{ sourceInputs.scenario?.id || 'Not selected' }}</strong></div>
            <div class="trace-row"><span>Shape</span><strong>{{ sourceInputs.shape?.id || 'Not selected' }}</strong></div>
            <div class="trace-row"><span>Snapshot Linkage</span><strong>{{ sourceInputs.evaluation?.id || 'No evaluation snapshot linked' }}</strong></div>
          </div>
          <textarea class="artifact-preview" readonly :value="pmSpecContent"></textarea>
        </article>

        <article class="panel">
          <div class="panel-header">
            <div>
              <h2>Current Business Brief</h2>
              <div class="panel-meta">Shorter PM-facing export generated from the same active project state.</div>
            </div>
            <div class="actions">
              <button class="btn btn-secondary" @click="copy(businessBriefContent)">Copy</button>
              <button class="btn btn-secondary" @click="download(`${project.id}-business-brief.md`, businessBriefContent)">Download</button>
              <button class="btn btn-primary" :disabled="readOnlyMode || savingType === 'business_brief'" @click="saveFrozenArtifact('business_brief')">
                {{ savingType === 'business_brief' ? 'Freezing…' : 'Save / Freeze' }}
              </button>
            </div>
          </div>
          <div class="trace-card">
            <div class="trace-row"><span>Generated At</span><strong>{{ prettyDate(new Date().toISOString()) }}</strong></div>
            <div class="trace-row"><span>Requirements</span><strong>{{ sourceInputs.requirements?.id || 'Not selected' }}</strong></div>
            <div class="trace-row"><span>Scenario</span><strong>{{ sourceInputs.scenario?.id || 'Not selected' }}</strong></div>
            <div class="trace-row"><span>Shape</span><strong>{{ sourceInputs.shape?.id || 'Not selected' }}</strong></div>
            <div class="trace-row"><span>Snapshot Linkage</span><strong>{{ sourceInputs.evaluation?.id || 'No evaluation snapshot linked' }}</strong></div>
          </div>
          <textarea class="artifact-preview" readonly :value="businessBriefContent"></textarea>
        </article>
      </section>

      <section class="saved-section">
        <div class="saved-section-header">
          <h2>Saved PM Artifacts</h2>
          <span class="saved-count">{{ persistedArtifacts.length }}</span>
        </div>
        <div v-if="persistedArtifacts.length === 0" class="empty-state">
          No frozen PM artifacts yet. Use “Save / Freeze” to preserve a timestamped export with source input metadata.
        </div>
        <div v-else class="saved-grid">
          <article v-for="artifact in persistedArtifacts" :key="artifact.id" class="saved-card">
            <div class="saved-card-header">
              <div>
                <div class="saved-kicker">{{ artifactTypeLabel(String(artifact.data?.artifact_type || 'pm_spec')) }}</div>
                <h3>{{ artifact.title }}</h3>
              </div>
              <div class="actions">
                <button class="btn btn-secondary" @click="copy(artifactContent(artifact.data))">Copy</button>
                <button class="btn btn-secondary" @click="download(`${artifact.id}.md`, artifactContent(artifact.data))">Download</button>
                <button class="btn btn-danger" :disabled="readOnlyMode" @click="archiveAssistantArtifact(artifact.id)">Archive</button>
              </div>
            </div>
            <div class="trace-card">
              <div class="trace-row"><span>Generated At</span><strong>{{ prettyDate(artifact.data?.generated_at) }}</strong></div>
              <div class="trace-row"><span>Requirements</span><strong>{{ artifact.data?.source_inputs?.requirements?.id || 'Not recorded' }}</strong></div>
              <div class="trace-row"><span>Scenario</span><strong>{{ artifact.data?.source_inputs?.scenario?.id || 'Not recorded' }}</strong></div>
              <div class="trace-row"><span>Shape</span><strong>{{ artifact.data?.source_inputs?.shape?.id || 'Not recorded' }}</strong></div>
              <div class="trace-row"><span>Snapshot Linkage</span><strong>{{ artifact.data?.snapshot_linkage?.evaluation_id || 'None' }}</strong></div>
            </div>
            <textarea class="artifact-preview saved-preview" readonly :value="artifactContent(artifact.data)"></textarea>
          </article>
        </div>
      </section>

      <section class="saved-section">
        <div class="saved-section-header">
          <div>
            <h2>Assistant Review Artifacts</h2>
            <div v-if="assistantArtifactFilter" class="panel-meta">
              Filtered to {{ assistantArtifactTypeLabel(assistantArtifactFilter) }}
            </div>
          </div>
          <button
            v-if="assistantArtifactFilter"
            class="btn btn-secondary"
            type="button"
            @click="clearAssistantArtifactFilter"
          >
            Clear Filter
          </button>
          <span class="saved-count">{{ assistantArtifacts.length }}</span>
        </div>
        <div v-if="assistantArtifacts.length === 0" class="empty-state">
          No assistant proposal artifacts yet.
        </div>
        <div v-else class="saved-grid">
          <article v-for="artifact in assistantArtifacts" :key="artifact.id" class="saved-card">
            <div class="saved-card-header">
              <div>
                <div class="saved-kicker">{{ assistantArtifactTypeLabel(String(artifact.data?.artifact_type || 'assistant')) }}</div>
                <h3>{{ artifact.title }}</h3>
              </div>
              <div class="actions">
                <button
                  v-if="canPromoteArtifact(artifact.data)"
                  class="btn btn-primary"
                  :disabled="readOnlyMode || promotingArtifactId === artifact.id"
                  @click="promoteAssistantArtifact(artifact.id)"
                >
                  {{ promotingArtifactId === artifact.id ? 'Promoting…' : 'Promote Accepted Items' }}
                </button>
                <button class="btn btn-danger" :disabled="readOnlyMode" @click="removeFrozenArtifact(artifact.id)">Delete</button>
              </div>
            </div>
            <div class="trace-card">
              <div class="trace-row"><span>Source Capability</span><strong>{{ artifact.data?.source_capability || 'Unknown' }}</strong></div>
              <div class="trace-row"><span>Accepted Items</span><strong>{{ assistantAcceptedPayload(artifact.data).length }}</strong></div>
              <div class="trace-row"><span>Rejected Items</span><strong>{{ Array.isArray(artifact.data?.rejected_item_ids) ? artifact.data.rejected_item_ids.length : 0 }}</strong></div>
              <div class="trace-row"><span>Promoted Artifacts</span><strong>{{ promotedArtifactIds(artifact.data).length ? promotedArtifactIds(artifact.data).join(', ') : 'Not promoted yet' }}</strong></div>
            </div>
            <div class="assistant-artifact-list" v-if="assistantAcceptedPayload(artifact.data).length">
              <article
                v-for="item in assistantAcceptedPayload(artifact.data)"
                :key="String(item.client_id ?? item.question_id ?? Math.random())"
                class="assistant-artifact-item"
              >
                <strong>{{ item.title || item.prompt || item.question_id }}</strong>
                <p>{{ item.body || item.why_it_matters || 'No additional detail.' }}</p>
                <small v-if="item.rationale">{{ item.rationale }}</small>
              </article>
            </div>
          </article>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.pm-artifacts-view {
  width: 100%;
  max-width: none;
  padding: 2rem;
}

.page-header {
  margin-bottom: 1.5rem;
}

.page-kicker {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 0.45rem;
}

.page-header h1 {
  margin: 0 0 0.45rem;
  font-size: 30px;
  color: var(--text-primary);
}

.page-header p,
.empty-state {
  color: var(--text-secondary);
}

.saved-section {
  margin-top: 1.5rem;
}

.saved-section-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.saved-section-header h2 {
  margin: 0;
  font-size: 18px;
}

.saved-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 26px;
  height: 26px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.16);
  color: var(--text-primary);
  font-size: 12px;
  font-weight: 700;
}

.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}

.panel {
  background: var(--surface-depth-panel);
  border: 1px solid var(--surface-border-panel);
  border-radius: 18px;
  padding: 1.25rem;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: center;
  margin-bottom: 1rem;
}

.panel-header h2 {
  margin: 0;
  font-size: 16px;
}

.panel-meta,
.saved-kicker {
  font-size: 12px;
  color: var(--text-secondary);
}

.actions {
  display: flex;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.artifact-preview {
  width: 100%;
  max-width: 100%;
  min-width: 0;
  min-height: 560px;
  box-sizing: border-box;
  padding: 1rem;
  border-radius: 14px;
  border: 1px solid var(--surface-border-card);
  background: var(--surface-depth-card);
  color: var(--text-primary);
  font-size: 12px;
  line-height: 1.55;
  resize: vertical;
  overflow-wrap: anywhere;
}

.saved-preview {
  min-height: 260px;
}

.saved-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1rem;
}

.assistant-artifact-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.assistant-artifact-item {
  padding: 0.9rem 1rem;
  border-radius: 14px;
  border: 1px solid var(--surface-border-card);
  background: var(--surface-depth-card);
}

.assistant-artifact-item strong {
  display: block;
  margin-bottom: 0.35rem;
  color: var(--text-primary);
}

.assistant-artifact-item p {
  margin: 0 0 0.35rem;
  color: var(--text-secondary);
  line-height: 1.5;
  white-space: pre-wrap;
}

.assistant-artifact-item small {
  color: var(--text-muted);
}

.saved-card {
  background: var(--surface-depth-card);
  border: 1px solid var(--surface-border-card);
  border-radius: 18px;
  padding: 1.25rem;
}

.saved-card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 1rem;
}

.saved-card-header h3 {
  margin: 0.15rem 0 0;
  font-size: 16px;
}

.trace-card {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.65rem 1rem;
  padding: 0.9rem 1rem;
  margin-bottom: 1rem;
  border-radius: 14px;
  border: 1px solid var(--surface-border-card);
  background: var(--surface-depth-card);
}

.trace-row {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.trace-row span {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
}

.trace-row strong {
  font-size: 13px;
  color: var(--text-primary);
  word-break: break-word;
}

.btn {
  border: 1px solid var(--surface-border-card);
  border-radius: 12px;
  padding: 0.75rem 1rem;
  font-size: 14px;
  cursor: pointer;
}

.btn-secondary {
  background: var(--surface-depth-card);
  color: var(--text-primary);
}

.btn-primary {
  background: rgba(59, 130, 246, 0.16);
  color: #dbeafe;
  border-color: rgba(59, 130, 246, 0.35);
}

.btn-danger {
  background: rgba(248, 113, 113, 0.12);
  color: #fecaca;
  border-color: rgba(248, 113, 113, 0.28);
}

.banner {
  padding: 0.75rem 0.95rem;
  border-radius: 12px;
  margin-bottom: 1rem;
}

.banner-error {
  background: rgba(248, 113, 113, 0.12);
  border: 1px solid rgba(248, 113, 113, 0.28);
  color: var(--error);
}

.banner-warning {
  background: rgba(245, 158, 11, 0.12);
  border: 1px solid rgba(245, 158, 11, 0.3);
  color: #fbbf24;
}

.readonly-banner {
  margin-bottom: 1.25rem;
}

.btn:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

@media (max-width: 980px) {
  .grid {
    grid-template-columns: 1fr;
  }

  .trace-card {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .pm-artifacts-view {
    padding: 1.25rem;
  }

  .panel-header {
    flex-direction: column;
    align-items: stretch;
  }

  .saved-card-header {
    flex-direction: column;
  }
}
</style>
