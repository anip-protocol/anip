<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  useDeveloperDefinitionEditor,
} from '../design/use-developer-definition-editor'
import ProjectIssueBanner from '../components/ProjectIssueBanner.vue'
import { useProjectIssue } from '../design/use-project-issue'
import { useDeveloperIssueTargets } from '../design/use-developer-issue-targets'
import { developerLabel } from '../design/developer-vocabulary'
import {
  effectivePermissionCapabilityIds,
  rbacDecisionForRule,
  rbacDecisionLabel,
} from '../design/rbac-model'
import type { DeveloperActorExpectationBinding, DeveloperPermissionIntentRuleBinding } from '../design/project-types'
import { projectStore } from '../design/project-store'

const router = useRouter()
const editingActorId = ref<string | null>(null)
const editingUnmatchedPermissions = ref(false)
const expandedPermissionActors = ref<Set<string>>(new Set())
const {
  project,
  baseline,
  baselineAligned,
  definition,
  serviceOptions,
  saveDraft,
  resetDefinition,
  saving,
  saveError,
} = useDeveloperDefinitionEditor()
const pageIssue = useProjectIssue('project-developer-governance-bindings')
const {
  messagesForPath,
  messagesForPrefix,
  hasIssueForPath,
  hasIssueForPrefix,
} = useDeveloperIssueTargets({ definition, project })

const ACCESS_POSTURE_OPTIONS = [
  {
    value: 'allowed',
    label: 'Allowed access',
    description: 'The actor can use this business area when normal capability rules pass.',
  },
  {
    value: 'bounded',
    label: 'Limited access',
    description: 'The actor can use it only with declared limits, scope, or safe result boundaries.',
  },
  {
    value: 'approval_required',
    label: 'Needs approval',
    description: 'The actor must stop for approval before the governed action can continue.',
  },
  {
    value: 'restricted',
    label: 'Restricted access',
    description: 'The actor is blocked unless a declared condition, role, or authority check passes.',
  },
  {
    value: 'denied',
    label: 'Not allowed',
    description: 'The implementation must refuse this request for this actor.',
  },
]

const anyEditing = computed(() => editingActorId.value !== null || editingUnmatchedPermissions.value)
const readOnly = computed(() => projectStore.runtimeStatus?.read_only_mode !== false)

function policyDecisionLabel(rule: DeveloperPermissionIntentRuleBinding): string {
  return rbacDecisionLabel(rbacDecisionForRule(rule))
}

function startActorEditing(actorId: string) {
  if (readOnly.value) return
  editingActorId.value = actorId
}

function startUnmatchedEditing() {
  if (readOnly.value) return
  editingUnmatchedPermissions.value = true
}

function cancelEditing() {
  resetDefinition()
  editingActorId.value = null
  editingUnmatchedPermissions.value = false
}

async function saveAndReview() {
  if (readOnly.value) return
  await saveDraft()
  if (!saveError.value) {
    editingActorId.value = null
    editingUnmatchedPermissions.value = false
  }
}

function actorExpectationPath(actorId: string, field: string): string {
  return `actor_expectations.${actorId}.${field}`
}

function actorExpectationHasIssue(actorId: string): boolean {
  return hasIssueForPrefix(`actor_expectations.${actorId}`)
}

function permissionBindingPath(ruleId: string, field: string): string {
  return `permission_intent_bindings.${ruleId}.${field}`
}

function permissionBindingHasIssue(ruleId: string): boolean {
  return hasIssueForPrefix(`permission_intent_bindings.${ruleId}`)
}

function actorKey(value: string): string {
  return value.trim().toLowerCase()
}

function actorIsEditing(actorId: string): boolean {
  return editingActorId.value === actorId
}

function actorPermissionsExpanded(actorId: string): boolean {
  return expandedPermissionActors.value.has(actorId)
}

function toggleActorPermissions(actorId: string) {
  const next = new Set(expandedPermissionActors.value)
  if (next.has(actorId)) {
    next.delete(actorId)
  } else {
    next.add(actorId)
  }
  expandedPermissionActors.value = next
}

function permissionRulesForActor(actor: DeveloperActorExpectationBinding): DeveloperPermissionIntentRuleBinding[] {
  const actorId = actorKey(actor.actor_id)
  return definition.value?.permission_intent_bindings.filter((rule) => actorKey(rule.actor_id) === actorId) ?? []
}

function capabilityOptionsForRule(rule: DeveloperPermissionIntentRuleBinding) {
  const serviceIds = new Set(rule.target_service_ids)
  return definition.value?.capability_formalizations.filter((capability) => serviceIds.has(capability.service_id)) ?? []
}

function effectiveTargetCapabilityIds(rule: DeveloperPermissionIntentRuleBinding): string[] {
  return definition.value ? effectivePermissionCapabilityIds(definition.value, rule) : []
}

function toggleTargetCapability(rule: DeveloperPermissionIntentRuleBinding, capabilityId: string) {
  const current = effectiveTargetCapabilityIds(rule)
  rule.target_capability_ids = current.includes(capabilityId)
    ? current.filter((value) => value !== capabilityId)
    : [...current, capabilityId]
}

const unmatchedPermissionRules = computed(() => {
  const actorIds = new Set((definition.value?.actor_expectations ?? []).map((actor) => actorKey(actor.actor_id)))
  return definition.value?.permission_intent_bindings.filter((rule) => !actorIds.has(actorKey(rule.actor_id))) ?? []
})

function optionLabel(
  options: Array<{ value: string; label: string }>,
  value: string,
  fallback = 'Not set',
): string {
  if (!value) {
    return fallback
  }
  return options.find((option) => option.value === value)?.label ?? developerLabel(value)
}

function accessPostureDescription(value: string): string {
  return ACCESS_POSTURE_OPTIONS.find((option) => option.value === value)?.description
    ?? 'No access meaning recorded for this assignment.'
}

function nextPermissionRuleId(): string {
  const existingIds = new Set(definition.value?.permission_intent_bindings.map((rule) => rule.id) ?? [])
  let index = existingIds.size + 1
  while (existingIds.has(`permission_rule_${index}`)) {
    index += 1
  }
  return `permission_rule_${index}`
}

function addPermissionRule(actor: DeveloperActorExpectationBinding) {
  if (readOnly.value) return
  if (!definition.value) {
    return
  }
  definition.value.permission_intent_bindings.push({
    id: nextPermissionRuleId(),
    actor_id: actor.actor_id,
    business_area: '',
    business_area_label: '',
    access_posture: 'bounded',
    governed_outcome_type: 'bounded_result',
    governed_outcome: '',
    target_service_ids: [],
    target_capability_ids: [],
    formalization_strategy: '',
  })
}

function removePermissionRule(ruleId: string) {
  if (readOnly.value) return
  if (!definition.value) {
    return
  }
  definition.value.permission_intent_bindings = definition.value.permission_intent_bindings.filter((rule) => rule.id !== ruleId)
}

watch(readOnly, (isReadOnly) => {
  if (!isReadOnly) return
  editingActorId.value = null
  editingUnmatchedPermissions.value = false
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
        <h1>Roles & Access</h1>
        <p>
          Review each actor as a role and assign the permissions that role receives. Services own capabilities, and each capability declares which permissions it requires.
        </p>
      </section>

      <ProjectIssueBanner :issue="pageIssue" title="Role access diagnostics" />
      <section v-if="!baseline" class="panel empty-panel">
        <h2>Developer baseline is not locked</h2>
        <p>Return to Developer Overview and lock Product Design before formalizing actors, permissions, and audit posture.</p>
      </section>

      <section v-else-if="!baselineAligned" class="panel empty-panel">
        <h2>Locked baseline is out of sync</h2>
        <p>Product Design changed after the current developer baseline was locked. Re-lock the baseline before continuing.</p>
      </section>

      <section v-else-if="definition" class="grid" :class="{ 'review-mode': !anyEditing, 'edit-mode': anyEditing }">
        <article class="panel panel-full studio-surface">
          <div class="panel-header">
            <h2>RBAC Model</h2>
            <div class="header-actions">
              <button class="btn btn-secondary" type="button" @click="router.push(`/design/projects/${project.id}/developer/audit-lineage`)">
                Open Audit & Lineage
              </button>
            </div>
          </div>
          <p v-if="saveError" class="error">{{ saveError }}</p>
          <p class="panel-copy">
            Role access answers one question: which permissions does this role hold? Capability requirements and service enforcement are shown separately so actors, permissions, and services do not collapse into one bucket.
          </p>
        </article>

        <article id="actor-expectations" class="panel panel-full studio-surface">
          <div class="panel-header">
            <h2>Roles</h2>
          </div>
          <p class="panel-copy">
            Review each role with its assigned permissions. The same permission can be required by multiple capabilities and enforced by multiple services.
          </p>
          <div v-if="definition.actor_expectations.length" class="actor-expectation-list">
            <div
              v-for="actor in definition.actor_expectations"
              :key="actor.id"
              class="actor-expectation-card studio-surface-card"
              :class="{
                'field-error-card': actorExpectationHasIssue(actor.id) || permissionRulesForActor(actor).some((rule) => permissionBindingHasIssue(rule.id)),
              }"
            >
              <div class="section-head">
                <div>
                  <h3>{{ actor.actor_title || actor.actor_id || 'Actor' }}</h3>
                  <p class="actor-summary-line">
                    {{ permissionRulesForActor(actor).length }} permission{{ permissionRulesForActor(actor).length === 1 ? '' : 's' }} assigned to this role.
                  </p>
                  <p
                    v-for="message in messagesForPrefix(`actor_expectations.${actor.id}`)"
                    :key="message"
                    class="inline-field-error"
                  >
                    {{ message }}
                  </p>
                </div>
                <div class="header-actions">
                  <button v-if="!actorIsEditing(actor.id)" class="btn btn-secondary" type="button" :disabled="readOnly" @click="startActorEditing(actor.id)">
                    Edit Actor
                  </button>
                  <button v-if="actorIsEditing(actor.id)" class="btn btn-secondary" type="button" :disabled="saving" @click="cancelEditing">
                    Cancel
                  </button>
                  <button v-if="actorIsEditing(actor.id)" class="btn btn-primary" type="button" :disabled="readOnly || saving" @click="saveAndReview">
                    {{ saving ? 'Saving…' : 'Save Actor' }}
                  </button>
                </div>
              </div>
              <details v-if="!actorIsEditing(actor.id)" class="role-context-details">
                <summary>
                  <span>Role context from Product Design</span>
                  <small>Reference only. Runtime access is controlled by assigned permissions below.</small>
                </summary>
                <div class="review-summary-grid">
                  <div class="review-summary-card field-wide"><strong>Role Description</strong><p>{{ actor.summary_formalization || 'Not formalized yet.' }}</p></div>
                  <div class="review-summary-card field-wide"><strong>Visibility Expectations</strong><p>{{ actor.visibility_formalization || 'Not formalized yet.' }}</p></div>
                  <div class="review-summary-card field-wide"><strong>Allowed Requests</strong><p>{{ actor.action_formalization || 'Not formalized yet.' }}</p></div>
                  <div class="review-summary-card field-wide"><strong>Approval Boundaries</strong><p>{{ actor.approval_formalization || 'Not formalized yet.' }}</p></div>
                </div>
              </details>
              <div v-if="actorIsEditing(actor.id)" class="settings-grid">
                <label class="field" :class="{ 'field-error': hasIssueForPath(actorExpectationPath(actor.id, 'summary_formalization')) }">
                  <span class="summary-label required-label">Role Description</span>
                  <textarea v-model="actor.summary_formalization" class="textarea" rows="3" placeholder="Describe who this role represents. Permissions below define what it can actually do." />
                  <small v-for="message in messagesForPath(actorExpectationPath(actor.id, 'summary_formalization'))" :key="message" class="field-error-copy">{{ message }}</small>
                </label>
                <label class="field" :class="{ 'field-error': hasIssueForPath(actorExpectationPath(actor.id, 'visibility_formalization')) }">
                  <span class="summary-label required-label">Visibility Expectations</span>
                  <textarea v-model="actor.visibility_formalization" class="textarea" rows="3" placeholder="Capture visibility expectations from Product Design. Use permissions below for enforceable access." />
                  <small v-for="message in messagesForPath(actorExpectationPath(actor.id, 'visibility_formalization'))" :key="message" class="field-error-copy">{{ message }}</small>
                </label>
                <label class="field" :class="{ 'field-error': hasIssueForPath(actorExpectationPath(actor.id, 'action_formalization')) }">
                  <span class="summary-label required-label">Allowed Requests</span>
                  <textarea v-model="actor.action_formalization" class="textarea" rows="3" placeholder="Capture the kinds of requests this role is expected to make. Capability permissions below are the enforceable part." />
                  <small v-for="message in messagesForPath(actorExpectationPath(actor.id, 'action_formalization'))" :key="message" class="field-error-copy">{{ message }}</small>
                </label>
                <label class="field" :class="{ 'field-error': hasIssueForPath(actorExpectationPath(actor.id, 'approval_formalization')) }">
                  <span class="summary-label required-label">Approval Boundaries</span>
                  <textarea v-model="actor.approval_formalization" class="textarea" rows="3" placeholder="Capture approval expectations for this role. Capability grant policy defines approval mechanics." />
                  <small v-for="message in messagesForPath(actorExpectationPath(actor.id, 'approval_formalization'))" :key="message" class="field-error-copy">{{ message }}</small>
                </label>
              </div>

              <div
                class="actor-permission-section"
                :class="{ collapsed: !actorIsEditing(actor.id) && !actorPermissionsExpanded(actor.id) }"
              >
                <div class="subsection-head">
                  <div>
                    <h4>Permissions For This Role</h4>
                  </div>
                  <button
                    v-if="!actorIsEditing(actor.id) && permissionRulesForActor(actor).length"
                    class="btn btn-secondary"
                    type="button"
                    :aria-expanded="actorPermissionsExpanded(actor.id)"
                    @click="toggleActorPermissions(actor.id)"
                  >
                    {{ actorPermissionsExpanded(actor.id) ? 'Hide Permissions' : `Show ${permissionRulesForActor(actor).length} Permissions` }}
                  </button>
                  <button
                    v-if="actorIsEditing(actor.id)"
                    class="btn btn-secondary"
                    type="button"
                    @click="addPermissionRule(actor)"
                  >
                    Add Permission
                  </button>
                </div>
                <div v-if="permissionRulesForActor(actor).length && (actorIsEditing(actor.id) || actorPermissionsExpanded(actor.id))" class="permission-rule-list">
                  <div
                    v-for="rule in permissionRulesForActor(actor)"
                    :key="rule.id"
                    class="permission-rule-card"
                    :class="{ 'field-error-card': permissionBindingHasIssue(rule.id) }"
                  >
                    <div class="section-head compact-head">
                      <div>
                        <h5>{{ rule.business_area_label || rule.business_area || 'Permission' }}</h5>
                        <p class="panel-copy">
                          {{ policyDecisionLabel(rule) }} · required by {{ effectiveTargetCapabilityIds(rule).length }} capabilit{{ effectiveTargetCapabilityIds(rule).length === 1 ? 'y' : 'ies' }}
                        </p>
                        <p
                          v-for="message in messagesForPrefix(`permission_intent_bindings.${rule.id}`)"
                          :key="message"
                          class="inline-field-error"
                        >
                          {{ message }}
                        </p>
                      </div>
                      <button
                        v-if="actorIsEditing(actor.id)"
                        class="btn btn-danger"
                        type="button"
                        @click="removePermissionRule(rule.id)"
                      >
                        Remove
                      </button>
                    </div>
                    <div v-if="!actorIsEditing(actor.id)" class="review-summary-grid">
                      <div class="review-summary-card">
                        <strong>Access</strong>
                        <span>{{ optionLabel(ACCESS_POSTURE_OPTIONS, rule.access_posture) }}</span>
                      </div>
                      <div class="review-summary-card field-wide">
                        <strong>Meaning</strong>
                        <p>{{ accessPostureDescription(rule.access_posture) }}</p>
                      </div>
                      <details class="permission-detail-card permission-detail-row">
                        <summary>Show permission details</summary>
                        <div class="review-summary-grid">
                          <div class="review-summary-card">
                            <strong>Runtime Decision</strong>
                            <span>{{ policyDecisionLabel(rule) }}</span>
                          </div>
                          <div class="review-summary-card"><strong>Required By Capabilities</strong><span>{{ effectiveTargetCapabilityIds(rule).length }}</span></div>
                          <div class="review-summary-card"><strong>Enforced By Services</strong><span>{{ rule.target_service_ids.length }}</span></div>
                          <div class="review-summary-card field-wide"><strong>Permission Meaning</strong><p>{{ rule.governed_outcome || 'No permission meaning recorded.' }}</p></div>
                          <div class="review-summary-card field-wide"><strong>Implementation Notes</strong><p>{{ rule.formalization_strategy || 'Not formalized yet.' }}</p></div>
                        </div>
                      </details>
                    </div>
                    <div v-if="actorIsEditing(actor.id)" class="settings-grid">
                      <label class="field" :class="{ 'field-error': hasIssueForPath(permissionBindingPath(rule.id, 'business_area')) }">
                        <span class="summary-label required-label">Permission</span>
                        <input v-model="rule.business_area_label" class="input" placeholder="e.g. Account Enrichment" />
                        <small v-for="message in messagesForPath(permissionBindingPath(rule.id, 'business_area'))" :key="message" class="field-error-copy">{{ message }}</small>
                      </label>
                      <label class="field" :class="{ 'field-error': hasIssueForPath(permissionBindingPath(rule.id, 'access_posture')) }">
                        <span class="summary-label required-label">Assignment Type</span>
                        <select v-model="rule.access_posture" class="select">
                          <option v-for="option in ACCESS_POSTURE_OPTIONS" :key="option.value" :value="option.value">
                            {{ option.label }}
                          </option>
                        </select>
                        <small v-for="message in messagesForPath(permissionBindingPath(rule.id, 'access_posture'))" :key="message" class="field-error-copy">{{ message }}</small>
                      </label>
                      <div class="field">
                        <span>Runtime Decision</span>
                        <div class="readonly-pill">{{ policyDecisionLabel(rule) }}</div>
                      </div>
                      <label class="field field-wide" :class="{ 'field-error': hasIssueForPath(permissionBindingPath(rule.id, 'governed_outcome')) }">
                        <span class="summary-label required-label">Permission Meaning</span>
                        <textarea
                          v-model="rule.governed_outcome"
                          class="textarea"
                          rows="3"
                          placeholder="Describe what authority this permission grants or limits in plain language."
                        />
                        <small v-for="message in messagesForPath(permissionBindingPath(rule.id, 'governed_outcome'))" :key="message" class="field-error-copy">{{ message }}</small>
                      </label>
                      <div class="field field-wide" :class="{ 'field-error': hasIssueForPath(permissionBindingPath(rule.id, 'target_service_ids')) }">
                        <span class="summary-label required-label">Enforced By Services</span>
                        <div class="chip-grid">
                          <button
                            v-for="service in serviceOptions"
                            :key="service.id"
                            type="button"
                            class="chip"
                            :class="{ active: rule.target_service_ids.includes(service.id) }"
                            @click="
                              rule.target_service_ids = rule.target_service_ids.includes(service.id)
                                ? rule.target_service_ids.filter((value) => value !== service.id)
                                : [...rule.target_service_ids, service.id]
                            "
                          >
                            {{ service.label }}
                          </button>
                        </div>
                        <small v-for="message in messagesForPath(permissionBindingPath(rule.id, 'target_service_ids'))" :key="message" class="field-error-copy">{{ message }}</small>
                      </div>
                      <div class="field field-wide" :class="{ 'field-error': hasIssueForPath(permissionBindingPath(rule.id, 'target_capability_ids')) }">
                        <span class="summary-label required-label">Required By Capabilities</span>
                        <div class="chip-grid">
                          <button
                            v-for="capability in capabilityOptionsForRule(rule)"
                            :key="capability.capability_id"
                            type="button"
                            class="chip"
                            :class="{ active: effectiveTargetCapabilityIds(rule).includes(capability.capability_id) }"
                            @click="toggleTargetCapability(rule, capability.capability_id)"
                          >
                            {{ capability.title || capability.capability_id }}
                          </button>
                        </div>
                        <small v-for="message in messagesForPath(permissionBindingPath(rule.id, 'target_capability_ids'))" :key="message" class="field-error-copy">{{ message }}</small>
                      </div>
                      <label class="field field-wide" :class="{ 'field-error': hasIssueForPath(permissionBindingPath(rule.id, 'formalization_strategy')) }">
                        <span class="summary-label required-label">Implementation Notes</span>
                        <textarea
                          v-model="rule.formalization_strategy"
                          class="textarea"
                          rows="3"
                          placeholder="Explain how this permission is enforced by generated runtime policy and service capabilities."
                        />
                        <small v-for="message in messagesForPath(permissionBindingPath(rule.id, 'formalization_strategy'))" :key="message" class="field-error-copy">{{ message }}</small>
                      </label>
                    </div>
                  </div>
                </div>
                <p v-else-if="actorIsEditing(actor.id)" class="empty-state">No permissions are assigned to this role.</p>
              </div>
            </div>
          </div>
          <p v-else class="panel-copy">No PM actor or role expectations are defined on the locked Product Design baseline.</p>
        </article>

        <article v-if="unmatchedPermissionRules.length" id="permission-intent-bindings" class="panel panel-full studio-surface">
          <div class="panel-header">
            <h2>Unmatched Permissions</h2>
            <div class="header-actions">
              <button v-if="!editingUnmatchedPermissions" class="btn btn-secondary" type="button" :disabled="readOnly" @click="startUnmatchedEditing">
                Edit Unmatched
              </button>
              <button v-if="editingUnmatchedPermissions" class="btn btn-secondary" type="button" :disabled="saving" @click="cancelEditing">
                Cancel
              </button>
              <button v-if="editingUnmatchedPermissions" class="btn btn-primary" type="button" :disabled="readOnly || saving" @click="saveAndReview">
                {{ saving ? 'Saving…' : 'Save Permissions' }}
              </button>
            </div>
          </div>
          <p class="panel-copy">
            These permissions reference actors that do not currently have a role card. Fix the actor source or review these mappings explicitly.
          </p>
          <div class="actor-expectation-list">
            <div
              v-for="rule in unmatchedPermissionRules"
              :key="rule.id"
              class="actor-expectation-card studio-surface-card"
              :class="{ 'field-error-card': permissionBindingHasIssue(rule.id) }"
            >
              <div class="section-head">
                <div>
                  <h3>{{ rule.actor_id }} · {{ rule.business_area_label || rule.business_area }}</h3>
                  <p
                    v-for="message in messagesForPrefix(`permission_intent_bindings.${rule.id}`)"
                    :key="message"
                    class="inline-field-error"
                  >
                    {{ message }}
                  </p>
                </div>
                <button
                  v-if="editingUnmatchedPermissions"
                  class="btn btn-danger"
                  type="button"
                  @click="removePermissionRule(rule.id)"
                >
                  Remove
                </button>
              </div>
              <p class="panel-copy">
                {{ policyDecisionLabel(rule) }} · required by {{ effectiveTargetCapabilityIds(rule).length }} capabilit{{ effectiveTargetCapabilityIds(rule).length === 1 ? 'y' : 'ies' }}
              </p>
              <div v-if="!editingUnmatchedPermissions" class="review-summary-grid">
                <div class="review-summary-card">
                  <strong>Access</strong>
                  <span>{{ optionLabel(ACCESS_POSTURE_OPTIONS, rule.access_posture) }}</span>
                </div>
                <div class="review-summary-card field-wide">
                  <strong>Meaning</strong>
                  <p>{{ accessPostureDescription(rule.access_posture) }}</p>
                </div>
                <details class="permission-detail-card permission-detail-row">
                  <summary>Show permission details</summary>
                  <div class="review-summary-grid">
                    <div class="review-summary-card">
                      <strong>Runtime Decision</strong>
                      <span>{{ policyDecisionLabel(rule) }}</span>
                    </div>
                    <div class="review-summary-card"><strong>Required By Capabilities</strong><span>{{ effectiveTargetCapabilityIds(rule).length }}</span></div>
                    <div class="review-summary-card"><strong>Enforced By Services</strong><span>{{ rule.target_service_ids.length }}</span></div>
                    <div class="review-summary-card field-wide"><strong>Permission Meaning</strong><p>{{ rule.governed_outcome || 'No permission meaning recorded.' }}</p></div>
                    <div class="review-summary-card field-wide"><strong>Implementation Notes</strong><p>{{ rule.formalization_strategy || 'Not formalized yet.' }}</p></div>
                  </div>
                </details>
              </div>
              <div v-if="editingUnmatchedPermissions" class="settings-grid">
                <label class="field">
                  <span class="summary-label required-label">Actor ID</span>
                  <input v-model="rule.actor_id" class="input" placeholder="Match this to an actor expectation ID." />
                </label>
                <label class="field" :class="{ 'field-error': hasIssueForPath(permissionBindingPath(rule.id, 'business_area')) }">
                  <span class="summary-label required-label">Business Area</span>
                  <input v-model="rule.business_area_label" class="input" placeholder="e.g. Pipeline Review" />
                  <small v-for="message in messagesForPath(permissionBindingPath(rule.id, 'business_area'))" :key="message" class="field-error-copy">{{ message }}</small>
                </label>
                <label class="field" :class="{ 'field-error': hasIssueForPath(permissionBindingPath(rule.id, 'access_posture')) }">
                  <span class="summary-label required-label">Assignment Type</span>
                  <select v-model="rule.access_posture" class="select">
                    <option v-for="option in ACCESS_POSTURE_OPTIONS" :key="option.value" :value="option.value">
                      {{ option.label }}
                    </option>
                  </select>
                  <small v-for="message in messagesForPath(permissionBindingPath(rule.id, 'access_posture'))" :key="message" class="field-error-copy">{{ message }}</small>
                </label>
                <div class="field">
                  <span>Runtime Decision</span>
                  <div class="readonly-pill">{{ policyDecisionLabel(rule) }}</div>
                </div>
                <label class="field field-wide" :class="{ 'field-error': hasIssueForPath(permissionBindingPath(rule.id, 'governed_outcome')) }">
                  <span class="summary-label required-label">Permission Meaning</span>
                  <textarea
                    v-model="rule.governed_outcome"
                    class="textarea"
                    rows="3"
                    placeholder="Describe the allowed, bounded, approval-gated, or denied business behavior in plain language."
                  />
                  <small v-for="message in messagesForPath(permissionBindingPath(rule.id, 'governed_outcome'))" :key="message" class="field-error-copy">{{ message }}</small>
                </label>
                <div class="field field-wide" :class="{ 'field-error': hasIssueForPath(permissionBindingPath(rule.id, 'target_service_ids')) }">
                  <span class="summary-label required-label">Enforced By Services</span>
                  <div class="chip-grid">
                    <button
                      v-for="service in serviceOptions"
                      :key="service.id"
                      type="button"
                      class="chip"
                      :class="{ active: rule.target_service_ids.includes(service.id) }"
                      @click="
                        rule.target_service_ids = rule.target_service_ids.includes(service.id)
                          ? rule.target_service_ids.filter((value) => value !== service.id)
                          : [...rule.target_service_ids, service.id]
                      "
                    >
                      {{ service.label }}
                    </button>
                  </div>
                  <small v-for="message in messagesForPath(permissionBindingPath(rule.id, 'target_service_ids'))" :key="message" class="field-error-copy">{{ message }}</small>
                </div>
                <div class="field field-wide" :class="{ 'field-error': hasIssueForPath(permissionBindingPath(rule.id, 'target_capability_ids')) }">
                  <span class="summary-label required-label">Required By Capabilities</span>
                  <div class="chip-grid">
                    <button
                      v-for="capability in capabilityOptionsForRule(rule)"
                      :key="capability.capability_id"
                      type="button"
                      class="chip"
                      :class="{ active: effectiveTargetCapabilityIds(rule).includes(capability.capability_id) }"
                      @click="toggleTargetCapability(rule, capability.capability_id)"
                    >
                      {{ capability.title || capability.capability_id }}
                    </button>
                  </div>
                  <small v-for="message in messagesForPath(permissionBindingPath(rule.id, 'target_capability_ids'))" :key="message" class="field-error-copy">{{ message }}</small>
                </div>
                <label class="field field-wide" :class="{ 'field-error': hasIssueForPath(permissionBindingPath(rule.id, 'formalization_strategy')) }">
                  <span class="summary-label required-label">Implementation Notes</span>
                  <textarea
                    v-model="rule.formalization_strategy"
                    class="textarea"
                    rows="3"
                    placeholder="Explain how this permission is enforced by generated runtime policy and service capabilities."
                  />
                  <small v-for="message in messagesForPath(permissionBindingPath(rule.id, 'formalization_strategy'))" :key="message" class="field-error-copy">{{ message }}</small>
                </label>
              </div>
            </div>
          </div>
        </article>
      </section>
    </template>
  </div>
</template>

<style scoped src="./developer-definition-shared.css"></style>
<style scoped>
.panel > .panel-copy {
  margin: 0 0 1.2rem;
  max-width: 92rem;
}

.panel-header {
  margin-bottom: 1.1rem;
}

.settings-grid {
  gap: 1rem;
}

.field {
  gap: 0.5rem;
}

.field > span,
.checkbox-row span {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.input,
.select,
.textarea {
  background: var(--surface-depth-control);
}

.readonly-pill {
  min-height: 2.45rem;
  display: flex;
  align-items: center;
  padding: 0.65rem 0.85rem;
  border: 1px solid var(--surface-border-card);
  border-radius: 12px;
  background: var(--surface-depth-inset);
  color: var(--text-primary);
  font-weight: 700;
}

.service-governance-stack {
  display: flex;
  flex-direction: column;
  gap: 1.1rem;
  margin-top: 1.05rem;
}

.service-governance-section {
  border: 1px solid var(--surface-border-card);
  border-radius: 16px;
  padding: 1rem;
  background: var(--surface-depth-card);
  box-shadow: var(--surface-shadow-card);
}

.section-head {
  align-items: center;
  margin-bottom: 0.95rem;
  padding-bottom: 0.8rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
}

.section-head h3 {
  margin: 0;
  font-size: 16px;
}

.section-head h5,
.subsection-head h4 {
  margin: 0;
}

.section-head h5 {
  font-size: 14px;
}

.section-head .btn {
  margin-left: auto;
}

.compact-head {
  margin-bottom: 0.85rem;
  padding-bottom: 0.7rem;
}

.actor-summary-line,
.subsection-head p,
.permission-rule-card .panel-copy {
  margin: 0.25rem 0 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.45;
}

.role-context-details {
  margin-top: 0.85rem;
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  background: var(--surface-depth-card-nested);
  box-shadow: var(--surface-shadow-card-nested);
}

.role-context-details summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.8rem 0.95rem;
  cursor: pointer;
  color: var(--text-primary);
  font-weight: 700;
}

.role-context-details summary small {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 500;
}

.role-context-details .review-summary-grid {
  padding: 0 0.95rem 0.95rem;
}

.permission-detail-card {
  border: 1px solid var(--surface-border-card);
  border-radius: 12px;
  background: var(--surface-depth-inset);
}

.permission-detail-card summary {
  padding: 0.7rem 0.85rem;
  cursor: pointer;
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 700;
}

.permission-detail-card .review-summary-grid {
  padding: 0 0.85rem 0.85rem;
}

.permission-detail-row {
  grid-column: 1 / -1;
}

.actor-permission-section {
  margin-top: 1rem;
  border: 1px solid var(--surface-border-card);
  border-radius: 16px;
  padding: 1rem;
  background: var(--surface-depth-card-nested);
  box-shadow: var(--surface-shadow-card-nested);
}

.actor-permission-section.collapsed {
  margin-top: 0.75rem;
  padding: 0.65rem 0.75rem;
  border-radius: 12px;
}

.actor-permission-section.collapsed .subsection-head {
  align-items: center;
  margin-bottom: 0;
  padding-bottom: 0;
  border-bottom: 0;
}

.actor-permission-section.collapsed .subsection-head h4 {
  font-size: 13px;
}

.actor-permission-section.collapsed .btn {
  min-height: 2rem;
  padding: 0.4rem 0.7rem;
  font-size: 12px;
}

.subsection-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 0.9rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
}

.subsection-head .btn {
  flex: 0 0 auto;
}

.review-summary-card p {
  margin: 0.35rem 0 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.45;
}

.permission-rule-list {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.permission-rule-card {
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  padding: 0.95rem;
  background: var(--surface-depth-card-nested);
  box-shadow: var(--surface-shadow-card-nested);
}

.rule-help {
  margin: -0.35rem 0 0.95rem;
  max-width: 78rem;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.55;
}

.rule-card {
  border: 1px solid var(--surface-border-card);
  border-radius: 14px;
  padding: 1rem;
  background: var(--surface-depth-card-nested);
  box-shadow: var(--surface-shadow-card-nested);
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.rule-card + .rule-card {
  margin-top: 0.85rem;
}

.outcome-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 0.75rem;
}

.checkbox-row {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  min-height: 2.6rem;
  padding: 0.7rem 0.85rem;
  border: 1px solid var(--surface-border-card);
  border-radius: 12px;
  background: var(--surface-depth-inset);
}

.empty-state {
  padding: 0.9rem 1rem;
  border: 1px dashed rgba(148, 163, 184, 0.18);
  border-radius: 12px;
  background: var(--surface-depth-inset);
  color: var(--text-secondary);
}

.actor-expectation-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  margin-top: 1.05rem;
}

.actor-expectation-card {
  border: 1px solid var(--surface-border-card);
  border-radius: 16px;
  padding: 1rem;
  background: var(--surface-depth-card);
  box-shadow: var(--surface-shadow-card);
}

.actor-expectation-card.field-error-card,
.service-governance-section.field-error-card,
.permission-rule-card.field-error-card,
.rule-card.field-error-card {
  border-color: rgba(248, 113, 113, 0.66);
  background:
    linear-gradient(135deg, rgba(127, 29, 29, 0.26), rgba(15, 23, 42, 0.28)),
    rgba(15, 23, 42, 0.24);
  box-shadow: 0 0 0 1px rgba(248, 113, 113, 0.18), 0 18px 40px rgba(127, 29, 29, 0.12);
}

.actor-expectation-card > .panel-copy {
  margin: 0 0 1rem;
}

.chip-grid {
  margin: 0.2rem 0 0.15rem;
}

.btn-danger {
  align-self: flex-start;
  color: #fca5a5;
  border: 1px solid rgba(248, 113, 113, 0.28);
  background: rgba(127, 29, 29, 0.16);
}

.disabled {
  opacity: 0.58;
}

@media (max-width: 960px) {
  .settings-grid {
    grid-template-columns: 1fr;
  }

  .field-wide {
    grid-column: span 1;
  }
}
</style>
