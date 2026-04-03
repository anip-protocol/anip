<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { designStore, setActivePack, updateDraftField, setScenarioMode, updateGuidedScenarioAnswer } from '../design/store'
import { projectStore, openArtifactForEditing } from '../design/project-store'
import EditorToolbar from '../design/components/EditorToolbar.vue'
import KeyValueEditor from '../design/components/KeyValueEditor.vue'
import StringListEditor from '../design/components/StringListEditor.vue'
import { SCENARIO_GUIDED_SECTIONS, BEHAVIOR_SUGGESTIONS, SUPPORT_SUGGESTIONS } from '../design/guided/scenario-questions'
import { hydrateScenarioAnswers } from '../design/guided/scenario-mappings'
import { evaluateScenarioCompleteness } from '../design/guided/scenario-hints'
import GuidedSection from '../design/components/GuidedSection.vue'
import ScenarioSummary from '../design/components/ScenarioSummary.vue'
import CompletenessHints from '../design/components/CompletenessHints.vue'
import SuggestionChips from '../design/components/SuggestionChips.vue'

const route = useRoute()
const router = useRouter()

// --- Dual-route detection ---
const isProjectMode = computed(() => !!route.params.projectId)

// Project mode: look up record from projectStore.artifacts.scenarios
const projectRecord = computed(() => {
  if (!isProjectMode.value) return null
  const id = route.params.id as string
  return projectStore.artifacts.scenarios.find(s => s.id === id) ?? null
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
    openArtifactForEditing('scenario', record)
  }
}, { immediate: true })

const isEditing = computed(() => {
  if (!isProjectMode.value) return false // Legacy mode is read-only
  return designStore.editState === 'draft'
})

// Whether we have data to display
const hasData = computed(() => {
  if (isProjectMode.value) return !!projectRecord.value
  return !!pack.value
})

// Source data: draft when editing, original record/pack data otherwise
const scenario = computed(() => {
  if (isEditing.value && designStore.draftScenario) {
    return (designStore.draftScenario as Record<string, any>).scenario ?? {}
  }
  if (isProjectMode.value) {
    return projectRecord.value?.data?.scenario ?? {}
  }
  return pack.value?.scenario?.scenario ?? {}
})

const context = computed(() => scenario.value?.context ?? {})
const contextKeys = computed(() => Object.keys(context.value))

function navigateTo(view: string) {
  if (isProjectMode.value) {
    const pid = route.params.projectId as string
    // Map view names to project-route artifact segments
    const routeMap: Record<string, string> = {
      requirements: projectStore.activeRequirementsId ? `requirements/${projectStore.activeRequirementsId}` : '',
      proposal: projectStore.activeProposalId ? `proposals/${projectStore.activeProposalId}` : '',
      evaluation: '', // evaluations don't have a single default
    }
    const segment = routeMap[view]
    if (segment) {
      router.push(`/design/projects/${pid}/${segment}`)
    }
    return
  }
  if (!pack.value) return
  router.push(`/design/packs/${pack.value.meta.id}/${view}`)
}

// --- Draft helpers ---
function setField(path: string, value: any) {
  updateDraftField('scenario', `scenario.${path}`, value)
}

const CATEGORY_OPTIONS = ['safety', 'recovery', 'orchestration', 'cross_service', 'observability']
const NAME_PATTERN = /^[a-z0-9_\-]+$/

// Full scenario wrapper object (includes .scenario sub-key)
const scenarioWrapper = computed(() => {
  if (isProjectMode.value) {
    return projectRecord.value?.data ?? {}
  }
  return pack.value?.scenario ?? {}
})

const guidedScenarioAnswers = computed(() => {
  if (isEditing.value) return designStore.guidedScenarioAnswers
  return hydrateScenarioAnswers(scenarioWrapper.value)
})

const scenarioHints = computed(() => {
  if (isEditing.value) return designStore.scenarioHints
  return evaluateScenarioCompleteness(scenarioWrapper.value)
})

const currentCategory = computed(() => {
  return scenario.value?.category ?? 'safety'
})

const behaviorSuggestions = computed(() => {
  return BEHAVIOR_SUGGESTIONS[currentCategory.value] ?? []
})

const supportSuggestions = computed(() => {
  return SUPPORT_SUGGESTIONS[currentCategory.value] ?? []
})

/** Context keys managed by guided questions — excluded from the fallback editor */
const GUIDED_CONTEXT_KEYS = new Set([
  'capability', 'side_effect', 'expected_cost', 'budget_limit', 'permissions_state', 'task_id',
])

/** Context entries NOT managed by guided questions — shown in the fallback editor */
const extraContext = computed(() => {
  const ctx = scenario.value?.context ?? {}
  const filtered: Record<string, any> = {}
  for (const [key, value] of Object.entries(ctx)) {
    if (!GUIDED_CONTEXT_KEYS.has(key)) {
      filtered[key] = value
    }
  }
  return filtered
})

/** Merge extra context changes back, preserving guided-managed keys */
function setExtraContext(newExtra: Record<string, any>) {
  const ctx = scenario.value?.context ?? {}
  const merged: Record<string, any> = {}
  // Keep guided-managed keys from the current context
  for (const key of GUIDED_CONTEXT_KEYS) {
    if (ctx[key] !== undefined) {
      merged[key] = ctx[key]
    }
  }
  // Add the user-edited extra keys
  Object.assign(merged, newExtra)
  setField('context', merged)
}
</script>

<template>
  <div class="scenario-detail" v-if="hasData">
    <div class="layout">
      <!-- Main content -->
      <div class="main">
        <h1 class="page-title" v-if="!isEditing">{{ scenario.name }}</h1>

        <div class="mode-toggle">
          <button class="mode-btn" :class="{ active: designStore.scenarioMode === 'guided' }" @click="setScenarioMode('guided')" type="button">Guided</button>
          <button class="mode-btn" :class="{ active: designStore.scenarioMode === 'advanced' }" @click="setScenarioMode('advanced')" type="button">Advanced</button>
        </div>

        <EditorToolbar artifact="scenario" />

        <template v-if="designStore.scenarioMode === 'guided'">
          <ScenarioSummary :scenario="designStore.draftScenario ?? scenarioWrapper" />
          <CompletenessHints :hints="scenarioHints" />

          <div class="mapping-toggle" v-if="isEditing">
            <label class="mapping-label">
              <input type="checkbox" :checked="designStore.showFieldMappings" @change="designStore.showFieldMappings = !designStore.showFieldMappings" />
              Show technical field mappings
            </label>
          </div>

          <GuidedSection
            v-for="section in SCENARIO_GUIDED_SECTIONS"
            :key="section.id"
            :section="section"
            :answers="guidedScenarioAnswers"
            :showMappings="designStore.showFieldMappings"
            :readonly="!isEditing"
            @update:answer="updateGuidedScenarioAnswer"
          />

          <!-- Expected Behavior with suggestions -->
          <div class="guided-section-card">
            <h2 class="guided-section-title">Expected Behavior</h2>
            <p class="guided-section-desc">What should the system do in this situation?</p>
            <SuggestionChips
              :modelValue="scenario.expected_behavior ?? []"
              :suggestions="behaviorSuggestions"
              :readonly="!isEditing"
              placeholder="Add custom behavior..."
              @update:modelValue="setField('expected_behavior', $event)"
            />
          </div>

          <!-- Expected ANIP Support with suggestions -->
          <div class="guided-section-card">
            <h2 class="guided-section-title">Expected ANIP Support</h2>
            <p class="guided-section-desc">What should the protocol/interface itself make visible or explicit?</p>
            <SuggestionChips
              :modelValue="scenario.expected_anip_support ?? []"
              :suggestions="supportSuggestions"
              :readonly="!isEditing"
              placeholder="Add custom ANIP support..."
              @update:modelValue="setField('expected_anip_support', $event)"
            />
          </div>

          <!-- Additional context editor — only shows keys NOT managed by guided questions -->
          <div class="guided-section-card" v-if="isEditing">
            <h2 class="guided-section-title">Additional Context</h2>
            <p class="guided-section-desc">Add domain-specific context keys beyond the guided questions above.</p>
            <KeyValueEditor
              :modelValue="extraContext"
              @update:modelValue="setExtraContext($event)"
            />
          </div>
        </template>

        <template v-else>
        <!-- Editable fields when in draft mode -->
        <template v-if="isEditing">
          <div class="section">
            <h2>Scenario Details</h2>
            <div class="form-grid">
              <label class="form-label">Name</label>
              <div class="form-field">
                <input
                  class="form-input"
                  type="text"
                  :value="scenario.name"
                  @input="setField('name', ($event.target as HTMLInputElement).value)"
                  placeholder="e.g. budget_exhaustion"
                  :pattern="NAME_PATTERN.source"
                />
                <span
                  class="field-hint"
                  :class="{ error: scenario.name && !NAME_PATTERN.test(scenario.name) }"
                >
                  lowercase, digits, hyphens, underscores only
                </span>
              </div>
              <label class="form-label">Category</label>
              <select
                class="form-select"
                :value="scenario.category"
                @change="setField('category', ($event.target as HTMLSelectElement).value)"
              >
                <option v-for="cat in CATEGORY_OPTIONS" :key="cat" :value="cat">{{ cat }}</option>
              </select>
              <label class="form-label">Narrative</label>
              <textarea
                class="form-textarea"
                :value="scenario.narrative"
                @input="setField('narrative', ($event.target as HTMLTextAreaElement).value)"
                rows="4"
                placeholder="Describe the scenario..."
              ></textarea>
            </div>
          </div>

          <div class="section">
            <h2>Context</h2>
            <KeyValueEditor
              :modelValue="scenario.context ?? {}"
              @update:modelValue="setField('context', $event)"
            />
          </div>

          <div class="section">
            <h2>Expected Behavior</h2>
            <StringListEditor
              :modelValue="scenario.expected_behavior ?? []"
              @update:modelValue="setField('expected_behavior', $event)"
            />
          </div>

          <div class="section">
            <h2>Expected ANIP Support</h2>
            <StringListEditor
              :modelValue="scenario.expected_anip_support ?? []"
              @update:modelValue="setField('expected_anip_support', $event)"
            />
          </div>
        </template>

        <!-- Read-only display -->
        <template v-else>
          <span class="category-badge">{{ scenario.category }}</span>
          <div class="result-row" v-if="!isProjectMode && pack?.meta.result">
            <span class="result-badge" :class="'result-' + pack.meta.result.toLowerCase().replace('_', '-')">
              {{ pack.meta.result }}
            </span>
          </div>
          <div class="result-row" v-else-if="!isProjectMode">
            <span class="result-badge result-none">Not evaluated</span>
          </div>

          <p class="narrative">{{ scenario.narrative }}</p>

          <!-- Scenario Context -->
          <div class="section" v-if="contextKeys.length">
            <h2>Scenario Context</h2>
            <dl class="info-grid">
              <template v-for="key in contextKeys" :key="key">
                <dt>{{ key }}</dt>
                <dd>{{ typeof context[key] === 'object' ? JSON.stringify(context[key]) : context[key] }}</dd>
              </template>
            </dl>
          </div>

          <!-- Expected Behavior -->
          <div class="section">
            <h2>Expected Behavior</h2>
            <ul>
              <li v-for="(item, i) in scenario.expected_behavior" :key="i">{{ item }}</li>
            </ul>
          </div>

          <!-- Expected ANIP Support -->
          <div class="section">
            <h2>Expected ANIP Support</h2>
            <ul>
              <li v-for="(item, i) in scenario.expected_anip_support" :key="i">{{ item }}</li>
            </ul>
          </div>
        </template>
        </template>
      </div>

      <!-- Sidebar with quick links -->
      <aside class="quick-links">
        <h3>{{ isProjectMode ? 'Project Artifacts' : 'Pack Artifacts' }}</h3>
        <button class="link-btn" @click="navigateTo('requirements')" :disabled="isProjectMode && !projectStore.activeRequirementsId">
          <span class="link-icon">&#x1F4CB;</span> Requirements
        </button>
        <button class="link-btn" @click="navigateTo('proposal')" :disabled="isProjectMode ? !projectStore.activeProposalId : !pack?.proposal">
          <span class="link-icon">&#x1F4A1;</span> Proposal
        </button>
        <button v-if="!isProjectMode" class="link-btn" @click="navigateTo('evaluation')" :disabled="!pack?.evaluation">
          <span class="link-icon">&#x2713;</span> Evaluation
        </button>
      </aside>
    </div>
  </div>
  <div v-else class="not-found">{{ isProjectMode ? 'Scenario not found.' : 'Pack not found.' }}</div>
</template>

<style scoped>
.scenario-detail {
  padding: 2rem;
}

.layout {
  display: flex;
  gap: 2rem;
}

.main {
  flex: 1;
  min-width: 0;
  max-width: 720px;
}

.page-title {
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 0.5rem;
}

.category-badge {
  display: inline-block;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 2px 10px;
  border-radius: 10px;
  background: var(--accent-glow);
  color: var(--accent);
  margin-bottom: 0.5rem;
}

.result-row {
  margin-bottom: 1rem;
}

.result-badge {
  display: inline-block;
  font-size: 12px;
  font-weight: 700;
  padding: 3px 12px;
  border-radius: 12px;
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

.result-none {
  background: rgba(128, 128, 128, 0.15);
  color: var(--text-muted);
}

.narrative {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 0 0 1.5rem;
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

.info-grid {
  display: grid;
  grid-template-columns: 200px 1fr;
  gap: 0.5rem 1rem;
  margin: 0;
}

.info-grid dt {
  font-size: 13px;
  color: var(--text-muted);
  font-weight: 500;
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.info-grid dd {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0;
  word-break: break-word;
}

/* Quick links sidebar */
.quick-links {
  width: 200px;
  flex-shrink: 0;
  padding-top: 0.5rem;
}

.quick-links h3 {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-muted);
  margin: 0 0 0.75rem;
}

.link-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 12px;
  margin-bottom: 4px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm, 6px);
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.link-btn:hover:not(:disabled) {
  background: var(--bg-hover);
  color: var(--text-primary);
  border-color: var(--accent);
}

.link-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.link-icon {
  font-size: 14px;
  width: 20px;
  text-align: center;
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
  align-items: start;
}

.form-label {
  font-size: 13px;
  color: var(--text-muted);
  font-weight: 500;
  padding-top: 6px;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.field-hint {
  font-size: 11px;
  color: var(--text-muted);
}

.field-hint.error {
  color: var(--error);
}

.form-input {
  font-size: 13px;
  padding: 6px 10px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
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
  padding: 6px 10px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  outline: none;
  cursor: pointer;
}

.form-select:focus {
  border-color: var(--border-focus);
}

.form-textarea {
  font-size: 13px;
  padding: 8px 10px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  outline: none;
  resize: vertical;
  width: 100%;
  box-sizing: border-box;
  font-family: inherit;
  line-height: 1.5;
}

.form-textarea:focus {
  border-color: var(--border-focus);
}

.mode-toggle {
  display: flex;
  gap: 0;
  margin-bottom: 1rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  overflow: hidden;
  width: fit-content;
}

.mode-btn {
  padding: 6px 20px;
  font-size: 13px;
  font-weight: 500;
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition);
}

.mode-btn.active {
  background: var(--accent);
  color: var(--text-primary);
}

.mode-btn:hover:not(.active) {
  background: var(--bg-hover);
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

.guided-section-card {
  background: var(--bg-input, #1a1a2e);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm, 6px);
  padding: 16px 20px;
  margin-bottom: 16px;
}

.guided-section-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 4px;
}

.guided-section-desc {
  font-size: 13px;
  color: var(--text-muted);
  margin: 0 0 12px;
}
</style>
