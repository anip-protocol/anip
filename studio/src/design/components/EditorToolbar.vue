<script setup lang="ts">
import { computed, ref } from 'vue'
import { designStore, startEditing, discardEdits, validateDraft, getActivePack, composeDraftProposal } from '../store'
import { diffObjects } from '../diff'
import { downloadYaml, copyYamlToClipboard } from '../io'

const props = defineProps<{
  artifact: 'requirements' | 'scenario' | 'proposal'
}>()

const showErrors = ref(false)
const copyFeedback = ref(false)

const isEditing = computed(() => designStore.editState === 'draft')
const errors = computed(() => designStore.validationErrors)
const hasErrors = computed(() => errors.value.length > 0)

const changeCount = computed(() => {
  if (!isEditing.value) return 0

  if (props.artifact === 'proposal') {
    const pack = getActivePack()
    const allChanges: ReturnType<typeof diffObjects> = []
    if (designStore.draftDeclaredSurfaces && pack?.proposal?.proposal?.declared_surfaces) {
      const surfaceChanges = diffObjects(
        pack.proposal.proposal.declared_surfaces,
        designStore.draftDeclaredSurfaces,
      )
      allChanges.push(...surfaceChanges.map(c => ({ ...c, path: `declared_surfaces.${c.path}` })))
    }
    return allChanges.length
  }

  const original = props.artifact === 'requirements'
    ? designStore.originalRequirements
    : designStore.originalScenario
  const draft = props.artifact === 'requirements'
    ? designStore.draftRequirements
    : designStore.draftScenario
  return diffObjects(original, draft).length
})

function handleStartEditing() {
  startEditing()
}

function handleDiscard() {
  discardEdits()
}

function handleExport() {
  if (props.artifact === 'proposal') {
    const draftProposal = composeDraftProposal()
    if (draftProposal) downloadYaml(draftProposal, 'proposal.yaml')
    return
  }
  const draft = props.artifact === 'requirements'
    ? designStore.draftRequirements
    : designStore.draftScenario
  if (draft) {
    downloadYaml(draft, `${props.artifact}.yaml`)
  }
}

async function handleCopy() {
  let data: Record<string, any> | null = null
  if (props.artifact === 'proposal') {
    data = composeDraftProposal()
  } else {
    data = props.artifact === 'requirements'
      ? designStore.draftRequirements
      : designStore.draftScenario
  }
  if (data) {
    await copyYamlToClipboard(data)
    copyFeedback.value = true
    setTimeout(() => { copyFeedback.value = false }, 1500)
  }
}

function handleValidate() {
  validateDraft()
  showErrors.value = true
}

</script>

<template>
  <div class="editor-toolbar">
    <div class="toolbar-row">
      <!-- Left: status indicators -->
      <div class="toolbar-left">
        <template v-if="isEditing">
          <span class="change-badge" :class="{ dirty: changeCount > 0 }">
            {{ changeCount > 0 ? `${changeCount} change${changeCount > 1 ? 's' : ''}` : 'No changes' }}
          </span>
          <button
            class="status-btn"
            :class="{ 'has-errors': hasErrors, 'valid': !hasErrors }"
            @click="handleValidate"
            title="Validate draft"
          >
            <template v-if="hasErrors">
              <span class="error-icon">&#x2717;</span> {{ errors.length }} error{{ errors.length > 1 ? 's' : '' }}
            </template>
            <template v-else>
              <span class="valid-icon">&#x2713;</span> Valid
            </template>
          </button>
        </template>
      </div>

      <!-- Right: action buttons -->
      <div class="toolbar-right">
        <template v-if="isEditing">
          <button class="tb-btn secondary" @click="handleExport" title="Export as YAML file">
            Export YAML
          </button>
          <button class="tb-btn secondary" @click="handleCopy" title="Copy YAML to clipboard">
            {{ copyFeedback ? 'Copied!' : 'Copy YAML' }}
          </button>
          <button class="tb-btn danger" @click="handleDiscard" title="Discard all changes">
            Discard changes
          </button>
        </template>
        <template v-else>
          <button class="tb-btn primary" @click="handleStartEditing">
            Start Editing
          </button>
        </template>
      </div>
    </div>

    <!-- Error list (expandable) -->
    <div class="error-list" v-if="isEditing && hasErrors && showErrors">
      <div class="error-list-header">
        <span>Validation Errors</span>
        <button class="close-errors" @click="showErrors = false">&#x2715;</button>
      </div>
      <ul>
        <li v-for="(err, i) in errors" :key="i">
          <code>{{ err.path }}</code> &mdash; {{ err.message }}
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.editor-toolbar {
  margin-bottom: 1.5rem;
}

.toolbar-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 16px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.change-badge {
  font-size: 12px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 10px;
  background: rgba(128, 128, 128, 0.15);
  color: var(--text-muted);
}

.change-badge.dirty {
  background: rgba(251, 191, 36, 0.15);
  color: var(--design-partial);
}

.status-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 10px;
  border: none;
  cursor: pointer;
  background: transparent;
}

.status-btn.valid {
  color: var(--success);
}

.status-btn.has-errors {
  color: var(--error);
}

.valid-icon,
.error-icon {
  font-size: 11px;
}

.tb-btn {
  font-size: 12px;
  font-weight: 600;
  padding: 6px 14px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  cursor: pointer;
  transition: all var(--transition);
}

.tb-btn.primary {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}

.tb-btn.primary:hover {
  background: var(--accent-hover);
}

.tb-btn.secondary {
  background: transparent;
  color: var(--text-secondary);
}

.tb-btn.secondary:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.tb-btn.danger {
  background: transparent;
  color: var(--error);
  border-color: rgba(248, 113, 113, 0.3);
}

.tb-btn.danger:hover {
  background: rgba(248, 113, 113, 0.1);
}

/* Error list */
.error-list {
  margin-top: 8px;
  padding: 12px 16px;
  background: rgba(248, 113, 113, 0.06);
  border: 1px solid rgba(248, 113, 113, 0.2);
  border-radius: var(--radius-sm);
}

.error-list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  font-weight: 600;
  color: var(--error);
  margin-bottom: 8px;
}

.close-errors {
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 14px;
  padding: 0 4px;
}

.close-errors:hover {
  color: var(--text-primary);
}

.error-list ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.error-list li {
  font-size: 12px;
  color: var(--text-secondary);
  padding: 4px 0;
  border-bottom: 1px solid rgba(248, 113, 113, 0.1);
}

.error-list li:last-child {
  border-bottom: none;
}

.error-list code {
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 11px;
  color: var(--error);
  background: rgba(248, 113, 113, 0.1);
  padding: 1px 5px;
  border-radius: 3px;
}
</style>
