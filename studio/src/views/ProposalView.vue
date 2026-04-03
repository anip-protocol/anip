<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { designStore, setActivePack, updateDeclaredSurface, composeDraftProposal } from '../design/store'
import { loadProject, projectStore, openArtifactForEditing, refreshArtifacts } from '../design/project-store'
import { updateProposal } from '../design/project-api'
import EditorToolbar from '../design/components/EditorToolbar.vue'

const route = useRoute()

// --- Dual-route detection ---
const isProjectMode = computed(() => !!route.params.projectId)
const projectId = computed(() => route.params.projectId as string | undefined)

onMounted(() => {
  if (isProjectMode.value && projectId.value && projectStore.activeProject?.id !== projectId.value) {
    loadProject(projectId.value)
  }
})

watch(projectId, (id) => {
  if (isProjectMode.value && id && projectStore.activeProject?.id !== id) {
    loadProject(id)
  }
})

// Project mode: look up record from projectStore.artifacts.proposals
const projectRecord = computed(() => {
  if (!isProjectMode.value) return null
  const id = route.params.id as string
  return projectStore.artifacts.proposals.find(p => p.id === id) ?? null
})

// Legacy mode: look up pack from designStore.packs
const pack = computed(() => {
  if (isProjectMode.value) return null
  const id = route.params.packId as string
  if (id) setActivePack(id)
  return designStore.packs.find(p => p.meta.id === id) ?? null
})

// Hydrate design store when project record changes
watch(projectRecord, (record) => {
  if (record) {
    openArtifactForEditing('proposal', record)
  }
}, { immediate: true })

const proposal = computed(() => {
  if (isProjectMode.value) {
    return projectRecord.value?.data?.proposal ?? null
  }
  return pack.value?.proposal?.proposal ?? null
})

const isEditing = computed(() => {
  if (!isProjectMode.value) return false // Legacy mode is read-only
  return designStore.editState === 'draft'
})

// Whether we have data to display
const hasData = computed(() => {
  if (isProjectMode.value) return !!projectRecord.value
  return !!pack.value
})

// Display name for the title
const artifactName = computed(() => {
  if (isProjectMode.value) {
    return projectRecord.value?.title ?? 'Approach'
  }
  return pack.value?.meta.name ?? 'Approach'
})

const glueCategories = computed(() => {
  if (!proposal.value?.expected_glue_reduction) return []
  return Object.entries(proposal.value.expected_glue_reduction)
})

// Surface definitions: key -> human-readable label
const SURFACE_LABELS: Record<string, string> = {
  budget_enforcement: 'Budget Enforcement',
  binding_requirements: 'Binding Requirements',
  authority_posture: 'Authority Posture',
  recovery_class: 'Recovery Class',
  refresh_via: 'Refresh Via',
  verify_via: 'Verify Via',
  followup_via: 'Follow-up Via',
  cross_service_handoff: 'Cross-Service Handoff',
  cross_service_continuity: 'Cross-Service Continuity',
  cross_service_reconstruction: 'Cross-Service Reconstruction',
}

const surfaceKeys = computed(() => Object.keys(SURFACE_LABELS))

const draftSurfaces = computed(() => designStore.draftDeclaredSurfaces)
const saving = ref(false)
const saveError = ref<string | null>(null)

function toggleSurface(key: string) {
  const current = draftSurfaces.value?.[key as keyof typeof draftSurfaces.value] ?? false
  updateDeclaredSurface(key, !current)
}

async function handleSave() {
  if (!isProjectMode.value || !projectRecord.value) return
  const proposalData = composeDraftProposal()
  if (!proposalData) return

  saving.value = true
  saveError.value = null
  try {
    await updateProposal(projectRecord.value.project_id, projectRecord.value.id, {
      title: projectRecord.value.title,
      status: projectRecord.value.status,
      data: proposalData,
    })
    designStore.originalProposal = JSON.parse(JSON.stringify(proposalData))
    await refreshArtifacts()
  } catch (err) {
    saveError.value = err instanceof Error ? err.message : String(err)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="proposal-view" v-if="hasData && proposal">
    <h1 class="page-title">Approach: {{ artifactName }}</h1>

    <EditorToolbar
      artifact="proposal"
      :canSave="isProjectMode"
      :saving="saving"
      :saveError="saveError"
      @save="handleSave"
    />

    <!-- Declared Surfaces (editable when in draft mode) -->
    <div class="section">
      <h2>Declared Surfaces</h2>
      <template v-if="isEditing && draftSurfaces">
        <div class="surfaces-grid">
          <div
            class="surface-toggle"
            v-for="key in surfaceKeys"
            :key="key"
          >
            <button
              class="surface-btn"
              :class="{ on: (draftSurfaces as Record<string, boolean>)[key], off: !(draftSurfaces as Record<string, boolean>)[key] }"
              @click="toggleSurface(key)"
              type="button"
            >
              <span class="surface-indicator">
                {{ (draftSurfaces as Record<string, boolean>)[key] ? '&#x2713;' : '&#x2717;' }}
              </span>
              <span class="surface-name">{{ SURFACE_LABELS[key] }}</span>
              <span class="surface-state">
                {{ (draftSurfaces as Record<string, boolean>)[key] ? 'ON' : 'OFF' }}
              </span>
            </button>
          </div>
        </div>
      </template>
      <template v-else>
        <div class="surfaces-grid">
          <div
            class="surface-toggle"
            v-for="key in surfaceKeys"
            :key="key"
          >
            <div
              class="surface-display"
              :class="{ on: proposal.declared_surfaces?.[key], off: !proposal.declared_surfaces?.[key] }"
            >
              <span class="surface-indicator">
                {{ proposal.declared_surfaces?.[key] ? '&#x2713;' : '&#x2717;' }}
              </span>
              <span class="surface-name">{{ SURFACE_LABELS[key] }}</span>
              <span class="surface-state">
                {{ proposal.declared_surfaces?.[key] ? 'ON' : 'OFF' }}
              </span>
            </div>
          </div>
        </div>
      </template>
    </div>

    <!-- Shape header -->
    <div class="shape-header">
      <span class="shape-label">Recommended Shape</span>
      <span class="shape-value">{{ proposal.recommended_shape }}</span>
    </div>

    <!-- Rationale -->
    <div class="section">
      <h2>Rationale</h2>
      <ul>
        <li v-for="(item, i) in proposal.rationale" :key="i">{{ item }}</li>
      </ul>
    </div>

    <!-- Required Components -->
    <div class="section">
      <h2>Required Components</h2>
      <div class="pill-row">
        <span class="component-pill required" v-for="(item, i) in proposal.required_components" :key="i">
          {{ item }}
        </span>
      </div>
    </div>

    <!-- Optional Components -->
    <div class="section" v-if="proposal.optional_components && proposal.optional_components.length">
      <h2>Optional Components</h2>
      <div class="pill-row">
        <span class="component-pill optional" v-for="(item, i) in proposal.optional_components" :key="i">
          {{ item }}
        </span>
      </div>
    </div>

    <!-- Key Runtime Requirements -->
    <div class="section" v-if="proposal.key_runtime_requirements && proposal.key_runtime_requirements.length">
      <h2>Key Runtime Requirements</h2>
      <ul>
        <li v-for="(item, i) in proposal.key_runtime_requirements" :key="i">{{ item }}</li>
      </ul>
    </div>

    <!-- Anti-pattern Warnings -->
    <div class="section" v-if="proposal.anti_pattern_warnings && proposal.anti_pattern_warnings.length">
      <h2>Anti-pattern Warnings</h2>
      <ul class="warnings">
        <li v-for="(item, i) in proposal.anti_pattern_warnings" :key="i">{{ item }}</li>
      </ul>
    </div>

    <!-- Expected Glue Reduction -->
    <div class="section" v-if="glueCategories.length">
      <h2>Expected Glue Reduction</h2>
      <div class="glue-groups">
        <div class="glue-group" v-for="[category, items] in glueCategories" :key="category">
          <h3 class="glue-category-name">{{ category }}</h3>
          <ul>
            <li v-for="(item, i) in (items as string[])" :key="i">{{ item }}</li>
          </ul>
        </div>
      </div>
    </div>
  </div>
  <div v-else-if="hasData" class="not-found">No approach data available.</div>
  <div v-else class="not-found">{{ isProjectMode ? 'Approach not found.' : 'Pack not found.' }}</div>
</template>

<style scoped>
.proposal-view {
  padding: 2rem;
  max-width: 800px;
}

.page-title {
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 1rem;
}

/* Declared Surfaces grid */
.surfaces-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.surface-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  cursor: pointer;
  transition: all var(--transition);
  font-size: 13px;
  text-align: left;
}

.surface-display {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  font-size: 13px;
}

.surface-btn.on,
.surface-display.on {
  background: rgba(52, 211, 153, 0.08);
  border-color: rgba(52, 211, 153, 0.25);
}

.surface-btn.off,
.surface-display.off {
  background: transparent;
}

.surface-btn:hover {
  background: var(--bg-hover);
}

.surface-btn.on:hover {
  background: rgba(52, 211, 153, 0.14);
}

.surface-indicator {
  font-size: 12px;
  width: 18px;
  text-align: center;
  flex-shrink: 0;
}

.surface-btn.on .surface-indicator,
.surface-display.on .surface-indicator {
  color: var(--success);
}

.surface-btn.off .surface-indicator,
.surface-display.off .surface-indicator {
  color: var(--text-muted);
}

.surface-name {
  flex: 1;
  font-weight: 500;
  color: var(--text-primary);
}

.surface-btn.off .surface-name,
.surface-display.off .surface-name {
  color: var(--text-muted);
}

.surface-state {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  flex-shrink: 0;
}

.surface-btn.on .surface-state,
.surface-display.on .surface-state {
  color: var(--success);
}

.surface-btn.off .surface-state,
.surface-display.off .surface-state {
  color: var(--text-muted);
  opacity: 0.5;
}

/* Shape header */
.shape-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 18px;
  background: var(--bg-input, #1a1a2e);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm, 6px);
  margin-bottom: 1.5rem;
}

.shape-label {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-muted);
}

.shape-value {
  font-size: 18px;
  font-weight: 700;
  color: var(--accent);
}

.section {
  margin-bottom: 1.5rem;
}

.section h2 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 0.5rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border);
}

.section ul {
  list-style: disc;
  padding-left: 1.25rem;
  margin: 0;
}

.section li {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: 0.25rem;
}

/* Component pills */
.pill-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.component-pill {
  display: inline-block;
  font-size: 13px;
  font-weight: 500;
  padding: 4px 14px;
  border-radius: 14px;
  border: 1px solid var(--border);
}

.component-pill.required {
  background: rgba(96, 165, 250, 0.12);
  color: #60a5fa;
  border-color: rgba(96, 165, 250, 0.3);
}

.component-pill.optional {
  background: transparent;
  color: var(--text-muted);
  opacity: 0.7;
}

/* Warning styling */
.warnings li {
  color: var(--design-glue, #f87171);
  font-weight: 500;
}

.warnings li::marker {
  content: '\26A0\0020';
}

/* Glue reduction groups */
.glue-groups {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.glue-group {
  padding: 12px 16px;
  background: var(--bg-input, #1a1a2e);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm, 6px);
}

.glue-category-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--accent);
  margin: 0 0 0.5rem;
}

.glue-group ul {
  list-style: disc;
  padding-left: 1.25rem;
  margin: 0;
}

.glue-group li {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
  margin-bottom: 0.2rem;
}

.not-found {
  padding: 2rem;
  color: var(--text-muted);
}
</style>
