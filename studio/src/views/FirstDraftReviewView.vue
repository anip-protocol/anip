<script setup lang="ts">
import { computed, ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  projectStore,
  loadProject,
  setActiveRequirements,
  setActiveScenario,
  setActiveShape,
  setPendingIntentDraft,
  refreshArtifacts,
} from '../design/project-store'
import {
  createRequirements,
  createScenario,
  createShape,
} from '../design/project-api'
import {
  makeRequirementsTemplateFromIntent,
  makeScenarioTemplatesFromIntent,
  makeShapeTemplateFromIntent,
} from '../design/intent-drafts'
import { consumerModeFromLabels } from '../design/consumer-mode'

const route = useRoute()
const router = useRouter()

const projectId = computed(() => route.params.projectId as string)
const project = computed(() => projectStore.activeProject)
const pendingDraft = computed(() => projectStore.pendingIntentDraft)
const interpretation = computed(() => pendingDraft.value?.interpretation ?? null)
const sourceIntent = computed(() => pendingDraft.value?.source_intent ?? '')

const creating = ref<'all' | 'requirements' | 'scenarios' | 'shape' | null>(null)
const draftStatus = ref<string | null>(null)

onMounted(async () => {
  if (projectId.value && projectStore.activeProject?.id !== projectId.value) {
    await loadProject(projectId.value)
  }
  if (!pendingDraft.value) {
    router.replace(`/design/projects/${projectId.value}`)
  }
})

watch(projectId, async (id) => {
  if (id && projectStore.activeProject?.id !== id) {
    await loadProject(id)
  }
})

watch(pendingDraft, (draft) => {
  if (!draft && projectId.value) {
    router.replace(`/design/projects/${projectId.value}`)
  }
})

const projectSummary = computed(() =>
  project.value?.summary || 'Studio shaped this first design from your plain-language brief.',
)
const projectConsumerMode = computed(() => consumerModeFromLabels(project.value?.labels))

function returnToBrief() {
  router.push(`/design/projects/${projectId.value}`)
}

function discardSuggestion() {
  setPendingIntentDraft(null)
  draftStatus.value = null
  router.push(`/design/projects/${projectId.value}`)
}

async function createRequirementsDraft() {
  if (!projectId.value || !interpretation.value || !project.value) return
  creating.value = 'requirements'
  draftStatus.value = null
  try {
    const created = await createRequirements(projectId.value, {
      id: `req-${crypto.randomUUID()}`,
      title: projectStore.artifacts.requirements.length === 0 ? 'Requirements' : `Requirements ${projectStore.artifacts.requirements.length + 1}`,
      data: makeRequirementsTemplateFromIntent(
        interpretation.value,
        sourceIntent.value,
        project.value.name,
        project.value.domain,
        projectConsumerMode.value,
      ),
    })
    await refreshArtifacts()
    setActiveRequirements(created.id)
    draftStatus.value = 'Created the first What Matters draft from the recommendation.'
    router.push(`/design/projects/${projectId.value}/requirements/${created.id}`)
  } finally {
    creating.value = null
  }
}

async function createScenarioStarters() {
  if (!projectId.value || !interpretation.value) return
  creating.value = 'scenarios'
  draftStatus.value = null
  try {
    const templates = makeScenarioTemplatesFromIntent(interpretation.value, projectConsumerMode.value)
    const createdIds: string[] = []
    for (const template of templates) {
      const created = await createScenario(projectId.value, {
        id: `scn-${crypto.randomUUID()}`,
        title: template.title,
        data: template.data,
      })
      createdIds.push(created.id)
    }
    await refreshArtifacts()
    setActiveScenario(createdIds[0] || null)
    draftStatus.value = `Created ${createdIds.length} real situation starter${createdIds.length === 1 ? '' : 's'} from the recommendation.`
    if (createdIds[0]) {
      router.push(`/design/projects/${projectId.value}/scenarios/${createdIds[0]}`)
    }
  } finally {
    creating.value = null
  }
}

async function createServiceDesignDraft() {
  if (!projectId.value || !interpretation.value || !project.value) return
  const requirementsId = projectStore.activeRequirementsId || projectStore.artifacts.requirements[0]?.id || null
  if (!requirementsId) {
    draftStatus.value = 'Create or select What Matters before creating a service design.'
    return
  }
  creating.value = 'shape'
  draftStatus.value = null
  try {
    const created = await createShape(projectId.value, {
      id: `shape-${crypto.randomUUID()}`,
      title: projectStore.artifacts.shapes.length === 0 ? 'Service Shape' : `Service Shape ${projectStore.artifacts.shapes.length + 1}`,
      requirements_id: requirementsId,
      data: makeShapeTemplateFromIntent(interpretation.value, project.value.name, projectConsumerMode.value),
    })
    await refreshArtifacts()
    setActiveShape(created.id)
    draftStatus.value = 'Created the first Service Design draft from the recommendation.'
    router.push(`/design/projects/${projectId.value}/shapes/${created.id}`)
  } finally {
    creating.value = null
  }
}

async function createFirstDraftSet() {
  if (!projectId.value || !interpretation.value || !project.value) return
  creating.value = 'all'
  draftStatus.value = null
  try {
    const requirementsCreated = await createRequirements(projectId.value, {
      id: `req-${crypto.randomUUID()}`,
      title: projectStore.artifacts.requirements.length === 0 ? 'Requirements' : `Requirements ${projectStore.artifacts.requirements.length + 1}`,
      data: makeRequirementsTemplateFromIntent(
        interpretation.value,
        sourceIntent.value,
        project.value.name,
        project.value.domain,
        projectConsumerMode.value,
      ),
    })

    const templates = makeScenarioTemplatesFromIntent(interpretation.value, projectConsumerMode.value)
    const createdScenarioIds: string[] = []
    for (const template of templates) {
      const created = await createScenario(projectId.value, {
        id: `scn-${crypto.randomUUID()}`,
        title: template.title,
        data: template.data,
      })
      createdScenarioIds.push(created.id)
    }

    const shapeCreated = await createShape(projectId.value, {
      id: `shape-${crypto.randomUUID()}`,
      title: projectStore.artifacts.shapes.length === 0 ? 'Service Shape' : `Service Shape ${projectStore.artifacts.shapes.length + 1}`,
      requirements_id: requirementsCreated.id,
      data: makeShapeTemplateFromIntent(interpretation.value, project.value.name, projectConsumerMode.value),
    })

    await refreshArtifacts()
    setActiveRequirements(requirementsCreated.id)
    setActiveScenario(createdScenarioIds[0] || null)
    setActiveShape(shapeCreated.id)
    setPendingIntentDraft(null)
    draftStatus.value = 'Created the first draft set from the recommendation.'
    router.push(`/design/projects/${projectId.value}/shapes/${shapeCreated.id}`)
  } finally {
    creating.value = null
  }
}
</script>

<template>
  <div class="first-draft-review">
    <div v-if="!interpretation" class="loading-state">Loading first draft review...</div>

    <template v-else>
      <div class="page-header">
        <button class="back-link" @click="router.push(`/design/projects/${projectId}`)">&larr; Project</button>
        <h1 class="page-title">Suggested First Design</h1>
        <p class="page-summary">{{ projectSummary }}</p>
      </div>

      <section class="hero-card">
        <div class="hero-copy">
          <div class="hero-kicker">From your plain-language brief</div>
          <h2 class="hero-title">{{ interpretation.title }}</h2>
          <p class="hero-description">{{ interpretation.summary }}</p>
          <div class="proposal-note">
            This is a proposed starting point only. Nothing is persisted until you accept the whole recommendation or accept a section below.
          </div>
        </div>
        <div class="hero-actions">
          <button class="btn btn-primary hero-btn" :disabled="creating !== null" @click="createFirstDraftSet">
            {{ creating === 'all' ? 'Accepting proposal...' : 'Accept Entire Recommendation' }}
          </button>
          <button class="btn btn-secondary hero-btn-secondary" :disabled="creating !== null" @click="returnToBrief">
            Keep Editing Brief
          </button>
          <button class="btn btn-secondary hero-btn-secondary" :disabled="creating !== null" @click="discardSuggestion">
            Discard Suggestion
          </button>
          <p class="hero-detail">Accept everything in one move, or accept each section separately below.</p>
        </div>
      </section>

      <section class="brief-card">
        <div class="section-title">Original Plain-Language Brief</div>
        <p class="brief-text">{{ sourceIntent }}</p>
      </section>

      <div v-if="draftStatus" class="banner banner-success">{{ draftStatus }}</div>

      <div class="review-grid">
        <section class="review-card">
          <h2 class="section-title">What Matters</h2>
          <p class="section-desc">These are the main constraints and pressures the design should respect first.</p>
          <ul class="bullet-list">
            <li v-for="(item, i) in interpretation.requirements_focus" :key="`req-${i}`">{{ item }}</li>
          </ul>
          <button class="btn btn-secondary" :disabled="creating !== null" @click="createRequirementsDraft">
            {{ creating === 'requirements' ? 'Accepting...' : 'Accept What Matters Draft' }}
          </button>
        </section>

        <section class="review-card">
          <h2 class="section-title">Real Situations</h2>
          <p class="section-desc">These are the first situations Studio believes should pressure and validate the design.</p>
          <ul class="bullet-list">
            <li v-for="(item, i) in interpretation.scenario_starters" :key="`scenario-${i}`">{{ item }}</li>
          </ul>
          <button class="btn btn-secondary" :disabled="creating !== null" @click="createScenarioStarters">
            {{ creating === 'scenarios' ? 'Accepting...' : 'Accept Real Situation Starters' }}
          </button>
        </section>

        <section class="review-card">
          <h2 class="section-title">Suggested Service Design</h2>
          <p class="section-desc">This is the recommended starting structure before deeper refinement.</p>
          <div class="shape-pill" :class="interpretation.recommended_shape_type">
            {{ interpretation.recommended_shape_type === 'multi_service' ? 'Multi Service' : 'Single Service' }}
          </div>
          <p class="shape-reason">{{ interpretation.recommended_shape_reason }}</p>
          <ul class="bullet-list" v-if="interpretation.service_suggestions.length">
            <li v-for="(item, i) in interpretation.service_suggestions" :key="`service-${i}`">{{ item }}</li>
          </ul>
          <button class="btn btn-secondary" :disabled="creating !== null" @click="createServiceDesignDraft">
            {{ creating === 'shape' ? 'Accepting...' : 'Accept Service Design Draft' }}
          </button>
        </section>

        <section class="review-card">
          <h2 class="section-title">Why This Is The Right Starting Point</h2>
          <p class="section-desc">Studio is turning the brief into a first recommendation, not a final answer.</p>
          <div class="chip-row" v-if="interpretation.domain_concepts.length">
            <span v-for="(item, i) in interpretation.domain_concepts" :key="`concept-${i}`" class="chip">{{ item }}</span>
          </div>
          <ul class="bullet-list" v-if="interpretation.next_steps.length">
            <li v-for="(item, i) in interpretation.next_steps" :key="`next-${i}`">{{ item }}</li>
          </ul>
        </section>
      </div>
    </template>
  </div>
</template>

<style scoped>
.first-draft-review {
  padding: 2rem;
  max-width: 960px;
}

.loading-state {
  padding: 2rem;
  color: var(--text-muted);
}

.page-header {
  margin-bottom: 1.25rem;
}

.back-link {
  background: none;
  border: none;
  color: var(--accent);
  font-size: 13px;
  cursor: pointer;
  padding: 0;
  margin-bottom: 0.6rem;
}

.page-title {
  margin: 0 0 0.35rem;
  font-size: 24px;
  color: var(--text-primary);
}

.page-summary {
  margin: 0;
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-secondary);
}

.hero-card {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 1.25rem;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: var(--radius);
  background: rgba(255, 255, 255, 0.55);
  margin-bottom: 1rem;
}

.hero-copy {
  flex: 1;
}

.proposal-note,
.brief-card {
  margin-top: 0.9rem;
  padding: 0.9rem 1rem;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.52);
}

.hero-kicker {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.hero-title {
  margin: 0.35rem 0;
  font-size: 22px;
  color: var(--text-primary);
}

.hero-description,
.section-desc,
.shape-reason,
.hero-detail {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.6;
}

.hero-actions {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
  width: 250px;
  max-width: 100%;
  flex-shrink: 0;
}

.hero-btn {
  width: 100%;
}

.hero-btn-secondary {
  width: 100%;
}

.hero-detail {
  margin-top: 0.6rem;
  font-size: 12px;
}

.brief-card {
  margin-bottom: 1rem;
}

.brief-text {
  margin: 0.35rem 0 0;
  color: var(--text-secondary);
  line-height: 1.6;
  white-space: pre-wrap;
}

.review-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1rem;
}

.review-card {
  padding: 1rem;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: var(--radius);
  background: rgba(255, 255, 255, 0.55);
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 0.35rem;
}

.section-desc {
  margin-bottom: 0.75rem;
  font-size: 13px;
}

.bullet-list {
  margin: 0 0 1rem;
  padding-left: 1.1rem;
  color: var(--text-secondary);
}

.bullet-list li + li {
  margin-top: 0.35rem;
}

.review-card .btn {
  width: 100%;
}

.shape-pill {
  display: inline-block;
  margin: 0 0 0.75rem;
  padding: 0.3rem 0.6rem;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.shape-pill.single_service {
  background: rgba(16, 185, 129, 0.14);
  color: #047857;
}

.shape-pill.multi_service {
  background: rgba(234, 179, 8, 0.16);
  color: #a16207;
}

.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin: 0 0 1rem;
}

.chip {
  padding: 0.3rem 0.65rem;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.06);
  color: var(--text-primary);
  font-size: 12px;
  font-weight: 600;
}

.banner {
  margin: 0 0 1rem;
  padding: 0.85rem 1rem;
  border-radius: var(--radius-sm);
  font-size: 13px;
}

.banner-success {
  background: rgba(34, 197, 94, 0.08);
  border: 1px solid rgba(34, 197, 94, 0.2);
  color: #15803d;
}

@media (max-width: 720px) {
  .hero-card {
    flex-direction: column;
  }

  .hero-actions {
    width: 100%;
  }
}
</style>
