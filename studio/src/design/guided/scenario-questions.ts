// studio/src/design/guided/scenario-questions.ts

import type { GuidedSection } from './types'

/** Common expected_behavior suggestions by category */
export const BEHAVIOR_SUGGESTIONS: Record<string, string[]> = {
  safety: [
    'do_not_execute',
    'explain_budget_conflict',
    'explain_authority_gap',
    'prefer_escalation_or_replan_over_blind_retry',
    'preserve_task_identity',
    'preserve_parent_invocation_lineage',
    'produce_audit_entry',
  ],
  recovery: [
    'retry_with_backoff',
    'escalate_to_human_on_failure',
    'preserve_task_identity',
    'produce_audit_entry',
    'do_not_retry_blindly',
  ],
  orchestration: [
    'preserve_task_identity',
    'preserve_parent_invocation_lineage',
    'produce_audit_entry',
    'system_does_not_execute_blindly_if_budget_control_exists',
    'operator_can_reconstruct_the_cross_service_chain',
  ],
  cross_service: [
    'preserve_task_identity',
    'preserve_parent_invocation_lineage',
    'both_services_produce_useful_audit_entries',
    'operator_can_reconstruct_the_cross_service_chain',
    'produce_audit_entry',
  ],
  observability: [
    'produce_audit_entry',
    'preserve_task_identity',
    'audit_entries_are_searchable',
    'operator_can_trace_invocation_chain',
  ],
}

/** Common expected_anip_support suggestions by category */
export const SUPPORT_SUGGESTIONS: Record<string, string[]> = {
  safety: [
    'cost_visibility',
    'side_effect_visibility',
    'structured_failure',
    'permission_discovery',
    'resolution_guidance',
    'task_id_support',
    'parent_invocation_id_support',
    'audit_queryability',
  ],
  recovery: [
    'structured_failure',
    'resolution_guidance',
    'task_id_support',
    'parent_invocation_id_support',
    'audit_queryability',
  ],
  orchestration: [
    'permission_discovery',
    'side_effect_visibility',
    'cost_visibility',
    'task_id_support',
    'parent_invocation_id_support',
    'audit_queryability',
    'structured_failure',
  ],
  cross_service: [
    'task_id_support',
    'parent_invocation_id_support',
    'audit_queryability',
    'cross_service_verification_guidance',
    'structured_failure',
  ],
  observability: [
    'task_id_support',
    'parent_invocation_id_support',
    'audit_queryability',
  ],
}

export const SCENARIO_GUIDED_SECTIONS: GuidedSection[] = [
  // Section 1: Scenario Basics
  {
    id: 'scenario-basics',
    title: 'Scenario Basics',
    description: 'What is this situation and what kind of problem does it represent?',
    questions: [
      {
        id: 'scenario-title',
        prompt: 'Give this scenario a descriptive title',
        helpText:
          'A human-friendly name — the technical slug will be derived automatically (e.g. "Book Flight Over Budget" becomes book_flight_over_budget)',
        answerType: 'text',
        fieldMappings: [{ path: 'scenario.name', label: 'scenario.name' }],
        defaultValue: '',
      },
      {
        id: 'scenario-category',
        prompt: 'What kind of scenario is this?',
        helpText: 'This determines which validation rules apply and which suggestions appear',
        answerType: 'select',
        options: [
          {
            value: 'safety',
            label: 'Safety',
            description:
              'Actions that must be blocked or controlled — budget, permissions, irreversible operations',
          },
          {
            value: 'recovery',
            label: 'Recovery',
            description: 'Handling blocked, failed, or degraded work',
          },
          {
            value: 'orchestration',
            label: 'Orchestration',
            description: 'Coordinating work across steps, services, or agents',
          },
          {
            value: 'cross_service',
            label: 'Cross-Service',
            description: 'Work that crosses service boundaries with handoff expectations',
          },
          {
            value: 'observability',
            label: 'Observability',
            description: 'Audit, traceability, and operational visibility',
          },
        ],
        fieldMappings: [{ path: 'scenario.category', label: 'scenario.category' }],
        defaultValue: 'safety',
      },
    ],
  },

  // Section 2: Narrative
  {
    id: 'scenario-narrative',
    title: 'Narrative',
    description: 'What is happening in this situation? Tell the story.',
    questions: [
      {
        id: 'scenario-narrative-text',
        prompt: 'Describe the scenario in plain language',
        helpText:
          'e.g. "An agent is helping a user book travel within a budget, but the selected flight exceeds the budget limit."',
        answerType: 'text',
        fieldMappings: [{ path: 'scenario.narrative', label: 'scenario.narrative' }],
        defaultValue: '',
      },
    ],
  },

  // Section 3: Execution Context
  {
    id: 'scenario-context',
    title: 'Execution Context',
    description: 'What does the system know at decision time? What facts matter?',
    questions: [
      {
        id: 'context-capability',
        prompt: 'What capability or action is being attempted?',
        helpText: 'e.g. "book_flight", "delete_cluster", "deploy_service"',
        answerType: 'text',
        fieldMappings: [
          { path: 'scenario.context.capability', label: 'scenario.context.capability' },
        ],
        defaultValue: '',
      },
      {
        id: 'context-side-effect',
        prompt: 'What kind of side effect does this action have?',
        answerType: 'select',
        options: [
          { value: '', label: 'Not specified', description: 'No side effect information' },
          { value: 'none', label: 'None', description: 'Read-only, no state changes' },
          { value: 'reversible', label: 'Reversible', description: 'Can be undone' },
          {
            value: 'irreversible',
            label: 'Irreversible',
            description: 'Cannot be undone — e.g. sending email, deleting data',
          },
        ],
        fieldMappings: [
          { path: 'scenario.context.side_effect', label: 'scenario.context.side_effect' },
        ],
        defaultValue: '',
      },
      {
        id: 'context-expected-cost',
        prompt: 'What is the expected cost of this action?',
        helpText: 'Leave blank if cost is not relevant. Numeric value — e.g. 800',
        answerType: 'text',
        fieldMappings: [
          { path: 'scenario.context.expected_cost', label: 'scenario.context.expected_cost' },
        ],
        defaultValue: '',
      },
      {
        id: 'context-budget-limit',
        prompt: 'What is the budget limit?',
        helpText: 'Leave blank if there is no budget constraint. Numeric value — e.g. 500',
        answerType: 'text',
        fieldMappings: [
          { path: 'scenario.context.budget_limit', label: 'scenario.context.budget_limit' },
        ],
        defaultValue: '',
      },
      {
        id: 'context-permissions',
        prompt: 'What is the current permissions state?',
        answerType: 'select',
        options: [
          {
            value: '',
            label: 'Not specified',
            description: 'Permissions are not relevant to this scenario',
          },
          {
            value: 'available',
            label: 'Available',
            description: 'The agent has the required permissions',
          },
          {
            value: 'denied',
            label: 'Denied',
            description: 'The agent does not have required permissions',
          },
          {
            value: 'restricted',
            label: 'Restricted',
            description: 'Permissions exist but are restricted/grantable',
          },
        ],
        fieldMappings: [
          {
            path: 'scenario.context.permissions_state',
            label: 'scenario.context.permissions_state',
          },
        ],
        defaultValue: '',
      },
      {
        id: 'context-task-id',
        prompt: 'What is the task ID for this work?',
        helpText:
          'Leave blank if task tracking is not relevant. Additional lineage fields (parent_invocation_id, client_reference_id) can be added in the context editor below.',
        answerType: 'text',
        fieldMappings: [
          { path: 'scenario.context.task_id', label: 'scenario.context.task_id' },
        ],
        defaultValue: '',
      },
    ],
  },

  // Sections 4 (Expected Behavior) and 5 (Expected ANIP Support) are NOT part of
  // SCENARIO_GUIDED_SECTIONS. They use SuggestionChips with category-aware suggestions
  // instead of the generic GuidedQuestion component, because expected_behavior and
  // expected_anip_support are string arrays — not single-value answers. The SuggestionChips
  // component writes directly to the draft artifact via updateDraftField.
]
