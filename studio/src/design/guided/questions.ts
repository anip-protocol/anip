import type { GuidedSection } from './types'

export const GUIDED_SECTIONS: GuidedSection[] = [
  {
    id: 'system-basics',
    title: 'System Basics',
    description: 'What is this system and how will it be deployed?',
    questions: [
      {
        id: 'system-name',
        prompt: 'What is the name of your system?',
        answerType: 'text',
        fieldMappings: [{ path: 'system.name', label: 'System Name' }],
        defaultValue: '',
      },
      {
        id: 'system-domain',
        prompt: 'What domain does this system operate in?',
        helpText: 'e.g. fintech, healthcare, devops, e-commerce',
        answerType: 'text',
        fieldMappings: [{ path: 'system.domain', label: 'Domain' }],
        defaultValue: '',
      },
      {
        id: 'deployment-intent',
        prompt: 'How will this system be deployed?',
        helpText:
          'Describe the deployment target — e.g. "production SaaS", "internal tooling", "embedded in CLI"',
        answerType: 'text',
        multiline: true,
        fieldMappings: [{ path: 'system.deployment_intent', label: 'Deployment Intent' }],
        defaultValue: '',
      },
      {
        id: 'scale-shape',
        prompt: 'What is the expected scale and shape of this system?',
        answerType: 'select',
        options: [
          {
            value: 'embedded_single_process',
            label: 'Embedded Single Process',
            description: 'Agent logic runs inside your application process — e.g. a CLI or desktop app',
          },
          {
            value: 'production_single_service',
            label: 'Production Single Service',
            description: 'A standalone deployed service handling agent requests',
          },
          {
            value: 'horizontally_scaled',
            label: 'Horizontally Scaled',
            description: 'Multiple instances of a single service behind a load balancer',
          },
          {
            value: 'control_plane_worker_split',
            label: 'Control Plane / Worker Split',
            description: 'Separate orchestration and execution tiers',
          },
          {
            value: 'multi_service_estate',
            label: 'Multi-Service Estate',
            description: 'Multiple services each owning part of the agent execution surface',
          },
        ],
        fieldMappings: [{ path: 'scale.shape_preference', label: 'Shape Preference' }],
        defaultValue: 'production_single_service',
      },
      {
        id: 'high-availability',
        prompt: 'Does this system require high availability?',
        answerType: 'boolean',
        fieldMappings: [{ path: 'scale.high_availability', label: 'High Availability' }],
        defaultValue: false,
      },
      {
        id: 'trust-mode',
        prompt: 'What trust mode will this system use?',
        helpText:
          'Unsigned: no verification. Signed: cryptographic signatures. Anchored: trust anchored to known roots. Attested: hardware-backed attestation.',
        answerType: 'select',
        options: [
          {
            value: 'unsigned',
            label: 'Unsigned',
            description: 'No cryptographic verification of requests',
          },
          {
            value: 'signed',
            label: 'Signed',
            description: 'Requests carry cryptographic signatures',
          },
          {
            value: 'anchored',
            label: 'Anchored',
            description: 'Trust is anchored to known roots of authority',
          },
          {
            value: 'attested',
            label: 'Attested',
            description: 'Hardware-backed attestation of identity',
          },
        ],
        fieldMappings: [{ path: 'trust.mode', label: 'Trust Mode' }],
        defaultValue: 'unsigned',
      },
      {
        id: 'trust-checkpoints',
        prompt: 'Should trust be verified at key execution checkpoints?',
        helpText:
          'Checkpoints allow verifying trust state at key points during execution',
        answerType: 'boolean',
        fieldMappings: [{ path: 'trust.checkpoints', label: 'Trust Checkpoints' }],
        defaultValue: false,
      },
    ],
  },
  {
    id: 'risk-side-effects',
    title: 'Risk and Side Effects',
    description: 'Can actions spend money, cause irreversible changes, or carry high risk?',
    questions: [
      {
        id: 'has-spending',
        prompt: 'Can actions in this system spend money or incur costs?',
        helpText: 'e.g. purchasing, billing, resource provisioning with cost',
        answerType: 'boolean',
        fieldMappings: [
          { path: 'business_constraints.spending_possible', label: 'Spending Possible' },
        ],
        defaultValue: false,
      },
      {
        id: 'has-irreversible',
        prompt: 'Can actions in this system cause irreversible changes?',
        helpText: 'e.g. deleting data, sending emails, executing trades',
        answerType: 'boolean',
        fieldMappings: [
          {
            path: 'business_constraints.irreversible_actions_present',
            label: 'Irreversible Actions Present',
          },
        ],
        defaultValue: false,
      },
      {
        id: 'cost-visibility',
        prompt: 'Should costs be visible to callers before actions execute?',
        answerType: 'boolean',
        fieldMappings: [
          {
            path: 'business_constraints.cost_visibility_required',
            label: 'Cost Visibility Required',
          },
        ],
        defaultValue: false,
      },
    ],
  },
  {
    id: 'authority-approval',
    title: 'Authority and Approval Expectations',
    description: 'What control or approval posture is expected for this system?',
    questions: [
      {
        id: 'preflight-discovery',
        prompt: 'Should agents be able to discover what they are allowed to do before acting?',
        helpText:
          'Agents can discover what they are allowed to do before attempting actions',
        answerType: 'boolean',
        fieldMappings: [
          { path: 'permissions.preflight_discovery', label: 'Preflight Discovery' },
        ],
        defaultValue: false,
      },
      {
        id: 'grantable-restrictions',
        prompt: 'Can restricted actions be unlocked by granting additional authority?',
        helpText:
          'Some actions may be restricted but upgradeable if the right authority grants access',
        answerType: 'boolean',
        fieldMappings: [
          { path: 'permissions.grantable_requirements', label: 'Grantable Requirements' },
        ],
        defaultValue: false,
      },
      {
        id: 'restricted-vs-denied',
        prompt: 'Should the system distinguish between restricted and denied actions?',
        helpText:
          '"Restricted" means potentially grantable; "denied" means never allowed',
        answerType: 'boolean',
        fieldMappings: [
          { path: 'permissions.restricted_vs_denied', label: 'Restricted vs Denied' },
        ],
        defaultValue: false,
      },
      {
        id: 'delegation-tokens',
        prompt: 'Will this system use delegation tokens to carry scoped authority?',
        helpText: 'Delegation tokens carry scoped authority from a principal to an agent',
        answerType: 'boolean',
        fieldMappings: [{ path: 'auth.delegation_tokens', label: 'Delegation Tokens' }],
        defaultValue: false,
      },
      {
        id: 'scoped-authority',
        prompt: 'Should authority be scoped to limit what agents can do?',
        answerType: 'boolean',
        fieldMappings: [{ path: 'auth.scoped_authority', label: 'Scoped Authority' }],
        defaultValue: false,
      },
      {
        id: 'purpose-binding',
        prompt: 'Should delegated authority be bound to a specific purpose?',
        helpText:
          'Purpose binding ensures agents act within the intent of their delegated authority',
        answerType: 'boolean',
        fieldMappings: [{ path: 'auth.purpose_binding', label: 'Purpose Binding' }],
        defaultValue: false,
      },
      {
        id: 'approval-expectation',
        prompt: 'Should high-risk actions require explicit approval before execution?',
        helpText:
          'This captures approval intent as a business constraint — the system does not yet have a first-class approval model',
        answerType: 'boolean',
        fieldMappings: [
          {
            path: 'business_constraints.approval_expected_for_high_risk',
            label: 'Approval Expected for High Risk',
          },
        ],
        defaultValue: false,
      },
    ],
  },
  {
    id: 'recovery-expectations',
    title: 'Recovery Expectations',
    description: 'How should blocked or failed work be handled?',
    questions: [
      {
        id: 'recovery-sensitive',
        prompt: 'Does this system need explicit recovery guidance for failures?',
        helpText:
          'e.g. should the system have explicit guidance for retrying, re-validating, or escalating',
        answerType: 'boolean',
        fieldMappings: [
          { path: 'business_constraints.recovery_sensitive', label: 'Recovery Sensitive' },
        ],
        defaultValue: false,
      },
      {
        id: 'blocked-failure-expectation',
        prompt: 'What should happen when an action is blocked or fails?',
        helpText:
          'Describe the expected behavior — this is captured as a business constraint',
        answerType: 'select',
        options: [
          {
            value: 'not_specified',
            label: 'Not Specified',
            description: 'No specific posture required',
          },
          {
            value: 'retry_with_backoff',
            label: 'Retry with Backoff',
            description: 'Automatically retry failed actions with exponential backoff',
          },
          {
            value: 'escalate_to_human',
            label: 'Escalate to Human',
            description: 'Surface blocked actions to a human for resolution',
          },
          {
            value: 'fail_safe',
            label: 'Fail Safe',
            description: 'Halt execution and leave the system in a safe known state',
          },
        ],
        fieldMappings: [
          {
            path: 'business_constraints.blocked_failure_posture',
            label: 'Blocked Failure Posture',
          },
        ],
        defaultValue: 'not_specified',
      },
    ],
  },
  {
    id: 'audit-traceability',
    title: 'Audit and Traceability',
    description: 'Do you need to know what happened later?',
    questions: [
      {
        id: 'needs-audit',
        prompt: 'Should this system maintain a durable audit log?',
        helpText: 'Durable audit means actions are recorded in a way that survives restarts',
        answerType: 'boolean',
        fieldMappings: [{ path: 'audit.durable', label: 'Durable Audit' }],
        defaultValue: false,
      },
      {
        id: 'needs-searchable',
        prompt: 'Should the audit log be searchable?',
        helpText: 'Searchable audit allows querying by time, action, actor, etc.',
        answerType: 'boolean',
        fieldMappings: [{ path: 'audit.searchable', label: 'Searchable Audit' }],
        defaultValue: false,
      },
      {
        id: 'invocation-tracking',
        prompt: 'Should every invocation be assigned a unique ID?',
        helpText: 'Invocation IDs let you trace exactly what happened for each call',
        answerType: 'boolean',
        fieldMappings: [{ path: 'lineage.invocation_id', label: 'Invocation ID' }],
        defaultValue: false,
      },
      {
        id: 'task-tracking',
        prompt: 'Should related invocations be grouped under a task ID?',
        helpText: 'Task IDs group multiple invocations into a logical unit of work',
        answerType: 'boolean',
        fieldMappings: [{ path: 'lineage.task_id', label: 'Task ID' }],
        defaultValue: false,
      },
      {
        id: 'parent-tracking',
        prompt: 'Should invocations track their parent call for chain reconstruction?',
        helpText:
          'Parent invocation IDs create a call chain for debugging and reconstruction',
        answerType: 'boolean',
        fieldMappings: [
          { path: 'lineage.parent_invocation_id', label: 'Parent Invocation ID' },
        ],
        defaultValue: false,
      },
      {
        id: 'client-reference',
        prompt: 'Should external systems be able to supply their own reference IDs?',
        helpText:
          'Client reference IDs let external systems correlate their requests with your system',
        answerType: 'boolean',
        fieldMappings: [
          { path: 'lineage.client_reference_id', label: 'Client Reference ID' },
        ],
        defaultValue: false,
      },
    ],
  },
  {
    id: 'multi-service',
    title: 'Multi-Service Expectations',
    description: 'Will work cross multiple services?',
    questions: [
      {
        id: 'service-handoffs',
        prompt: 'Will authority need to be passed between services?',
        helpText: 'Service-to-service handoffs require coordinated authority passing',
        answerType: 'boolean',
        fieldMappings: [
          {
            path: 'auth.service_to_service_handoffs',
            label: 'Service-to-Service Handoffs',
          },
        ],
        defaultValue: false,
      },
      {
        id: 'cross-service-reconstruction',
        prompt: 'Should a request be traceable across service boundaries after the fact?',
        helpText:
          'Cross-service reconstruction lets you trace a request across service boundaries',
        answerType: 'boolean',
        fieldMappings: [
          {
            path: 'audit.cross_service_reconstruction_required',
            label: 'Cross-Service Reconstruction Required',
          },
        ],
        defaultValue: false,
      },
      {
        id: 'cross-service-continuity',
        prompt: 'Should invocation chains be preserved as work moves across services?',
        helpText: 'Cross-service continuity preserves invocation chains across services',
        answerType: 'boolean',
        fieldMappings: [
          {
            path: 'lineage.cross_service_continuity_required',
            label: 'Cross-Service Continuity Required',
          },
        ],
        defaultValue: false,
      },
    ],
  },
]
