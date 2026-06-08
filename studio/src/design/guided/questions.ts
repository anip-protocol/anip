import type { GuidedSection } from './types'

export const GUIDED_SECTIONS: GuidedSection[] = [
  {
    id: 'system-basics',
    title: 'System Basics',
    description: 'What is this system, how is it delivered, and what business-level trust posture does it need?',
    questions: [
      {
        id: 'system-name',
        prompt: 'What is the name of your system?',
        answerType: 'text',
        maxLength: 128,
        fieldMappings: [{ path: 'system.name', label: 'System Name' }],
        defaultValue: '',
      },
      {
        id: 'system-domain',
        prompt: 'What domain does this system operate in?',
        helpText: 'e.g. fintech, healthcare, devops, e-commerce',
        answerType: 'text',
        maxLength: 64,
        fieldMappings: [{ path: 'system.domain', label: 'Domain' }],
        defaultValue: '',
      },
      {
        id: 'deployment-intent',
        prompt: 'How will this system be deployed?',
        helpText:
          'Describe the deployment target — e.g. "production SaaS", "internal tooling", "embedded in CLI"',
        inlineDetails: [
          'This should read like a short business description, not an internal enum or topology label.',
          'Good answers explain where the system runs and how people will consume it.',
        ],
        helpDialog: {
          title: 'Deployment Intent',
          summary: 'This is the PM-facing description of how the system shows up in the real world.',
          bullets: [
            'Use plain language that a PM, buyer, or stakeholder can understand.',
            'Describe the delivery posture, such as internal tool, customer-facing service, or embedded product feature.',
            'Do not put engineering topology here. Internal architecture belongs lower in the design flow.',
          ],
          example: 'A coordinated multi-service production system used by revenue operations teams through a governed agent interface.',
          decisionOwner: 'Usually PM with input from architecture or platform leads.',
        },
        answerType: 'text',
        multiline: true,
        maxLength: 512,
        fieldMappings: [{ path: 'system.deployment_intent', label: 'Deployment Intent' }],
        defaultValue: '',
      },
      {
        id: 'scale-shape',
        prompt: 'How should this system be delivered?',
        helpText: 'Choose the business-level delivery shape, not the internal infrastructure topology.',
        inlineDetails: [
          'Embedded means ANIP is a feature inside another product.',
          'One standalone service means one main deployable backend owns the experience.',
          'Multiple coordinated services means separate business services work together.',
        ],
        helpDialog: {
          title: 'Delivery Shape',
          summary: 'This question is about the business-facing delivery model, not about workers, queues, or replica counts.',
          bullets: [
            'Pick Embedded if ANIP capabilities live inside an existing app or backend.',
            'Pick One Standalone Service if one main service owns the full surface.',
            'Pick Multiple Coordinated Services if separate services own different parts of the business workflow.',
            'Do not use this question to capture horizontal scaling, worker pools, or control-plane details.',
          ],
          example: 'A governed operations assistant may use Multiple Coordinated Services because reporting, eligibility review, routing, and notification drafting are separate bounded services.',
          decisionOwner: 'Usually PM with architecture input when the product boundary is still being defined.',
        },
        answerType: 'select',
        options: [
          {
            value: 'embedded_single_process',
            label: 'Embedded in an Existing Product',
            description: 'The ANIP capabilities live inside another application, such as a CLI, desktop app, or existing backend',
          },
          {
            value: 'production_single_service',
            label: 'One Standalone Service',
            description: 'One main deployed service owns the full ANIP surface for this system',
          },
          {
            value: 'multi_service_estate',
            label: 'Multiple Coordinated Services',
            description: 'Several business services each own part of the ANIP surface and work together',
          },
        ],
        fieldMappings: [{ path: 'scale.shape_preference', label: 'Delivery Shape' }],
        defaultValue: 'production_single_service',
      },
      {
        id: 'high-availability',
        prompt: 'Does this system require high availability?',
        helpText: 'Use this when outages materially affect the business or user workflow.',
        inlineDetails: [
          'This is about business tolerance for downtime, not about the exact failover design.',
          'If the answer is yes, developer design can later decide how to achieve it.',
        ],
        helpDialog: {
          title: 'High Availability',
          summary: 'High availability is a business requirement about uptime expectations, not a specific infrastructure implementation.',
          bullets: [
            'Answer yes when the system needs strong uptime guarantees or low interruption tolerance.',
            'Answer no when occasional downtime is acceptable for the expected users or rollout stage.',
            'The exact architecture for achieving availability belongs in developer design.',
          ],
          example: 'A revenue operations assistant used daily by multiple teams may need high availability if outages block operational work.',
          decisionOwner: 'Usually PM, operations leadership, or platform owners together.',
        },
        answerType: 'boolean',
        fieldMappings: [{ path: 'scale.high_availability', label: 'High Availability' }],
        defaultValue: false,
      },
      {
        id: 'trust-mode',
        prompt: 'What caller-verification posture should the business require?',
        helpText:
          'Choose the level of caller verification the product should rely on, not the low-level implementation mechanism.',
        inlineDetails: [
          'Unsigned means the product does not depend on cryptographic caller verification.',
          'Signed, anchored, and attested progressively raise the confidence and governance posture the product expects.',
        ],
        helpDialog: {
          title: 'Caller Verification Posture',
          summary: 'This is the business expectation for how trustworthy a caller or delegated action must be before the system relies on it.',
          bullets: [
            'Use Unsigned when the product does not need cryptographic proof of caller identity.',
            'Use Signed when requests should carry signatures the system can verify.',
            'Use Anchored when trust should chain back to a known authority or trust root.',
            'Use Attested when the product needs the strongest identity posture, such as hardware-backed attestation.',
            'Developers will later turn this into concrete trust and authority controls.',
          ],
          example: 'A sensitive multi-service assistant that can trigger operational changes may need anchored or attested caller verification instead of unsigned access.',
          decisionOwner: 'Usually PM with strong input from platform, security, or governance leads.',
        },
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
        prompt: 'Should the system re-check trust and authority at important execution steps?',
        helpText:
          'Use this when business risk is high enough that one trust check at the start is not sufficient.',
        inlineDetails: [
          'This is about business safety posture for multi-step or high-risk work.',
          'Developer design will later decide where those checkpoints actually live.',
        ],
        helpDialog: {
          title: 'Checkpoint Verification',
          summary: 'This asks whether the product should re-confirm trust and authority as execution progresses, rather than assuming one initial check is enough.',
          bullets: [
            'Choose yes when long-running, cross-service, or high-risk work should revalidate trust before key transitions.',
            'Choose no when one initial verification is enough for the expected business risk.',
            'This is about the required posture, not about the exact technical mechanism.',
          ],
          example: 'A system may need to re-check authority before moving from analysis into an approval-gated operational step.',
          decisionOwner: 'Usually PM with governance or platform input.',
        },
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
        inlineDetails: [
          'This includes direct money movement and indirect platform or usage costs.',
          'Answer yes when actions can trigger spend that should be treated as a real business concern.',
        ],
        helpDialog: {
          title: 'Spending or Cost-Creating Actions',
          summary: 'This asks whether the system can trigger actions that create financial or materially billable cost.',
          bullets: [
            'Examples include purchases, bookings, billable API calls, infrastructure provisioning, paid vendor actions, and other usage-based charges.',
            'This is about business impact, not just whether the backend does any computation.',
            'If the cost is meaningful enough that a user, approver, or operator should care before the action runs, treat it as spending-capable.',
          ],
          example: 'Creating cloud resources, purchasing inventory, or triggering a paid enrichment batch all count as spending or cost-creating actions.',
          decisionOwner: 'Usually PM with finance, operations, or platform input.',
        },
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
        inlineDetails: [
          'Use this when an action cannot simply be undone by retrying or rolling back a local state change.',
          'This often implies a stronger need for approval, audit, or explicit warnings.',
        ],
        helpDialog: {
          title: 'Irreversible Actions',
          summary: 'This asks whether the system can trigger outcomes that are difficult or impossible to undo once they happen.',
          bullets: [
            'Examples include sending outbound communication, executing a trade, deleting records, triggering external side effects, or changing state in a way that cannot be cleanly reversed.',
            'This is different from a reversible action that can be safely retried, canceled, or rolled back.',
            'Irreversibility often changes the approval, audit, and recovery requirements for the whole system.',
          ],
          example: 'Drafting an email is reversible. Actually sending it is usually irreversible for product and governance purposes.',
          decisionOwner: 'Usually PM with compliance, legal, or business operations input when needed.',
        },
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
        helpText: 'Use this when users or approvers should see expected spend or billable impact before the action runs.',
        inlineDetails: [
          'Cost can mean money, billed usage, or expensive resource consumption.',
          'Visible means surfaced in the product response, preview, or approval step before execution.',
        ],
        helpDialog: {
          title: 'Cost Visibility Before Execution',
          summary: 'This asks whether the system should surface expected cost before an action is allowed to proceed.',
          bullets: [
            'Cost can include direct spend, vendor usage fees, compute-heavy work, provisioning cost, or other billable resource impact.',
            'Visibility can mean a price estimate, a usage preview, a cost band, or an approval note shown before execution.',
            'This matters most when users or approvers need to make an informed decision before committing to the action.',
            'It is not about exact accounting precision; it is about whether cost should be exposed as part of the decision flow.',
          ],
          example: 'Before triggering a large enrichment run or infrastructure action, the UI or agent response may show an estimated cost or usage impact.',
          decisionOwner: 'Usually PM with finance, operations, or platform stakeholders.',
        },
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
        inlineDetails: [
          'This helps agents ask for the right bounded action instead of guessing and failing late.',
          'It is especially useful when permissions vary by role, actor, or service.',
        ],
        helpDialog: {
          title: 'Preflight Authority Discovery',
          summary: 'This means the system can expose what an actor is allowed to do before the agent tries the action.',
          bullets: [
            'It reduces blind trial-and-error by letting the agent inspect boundaries first.',
            'It is useful in systems with restrictions, approvals, or actor-scoped access.',
            'This does not widen authority. It only makes the current boundaries visible.',
          ],
          example: 'An agent can see that a routing or assignment action is approval-gated before trying to execute it directly.',
          decisionOwner: 'Usually PM and platform/security leads together.',
        },
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
        inlineDetails: [
          'Restricted means not available right now, but potentially available with the right grant or approval.',
          'This is different from a hard deny, where the action should never proceed.',
        ],
        helpDialog: {
          title: 'Grantable Restrictions',
          summary: 'This captures whether some blocked actions can become allowed after an explicit authority change.',
          bullets: [
            'Use yes when some actions can become available after a grant, approval, or higher-trust context.',
            'Use no when blocked actions should remain blocked regardless of additional authority.',
            'This creates a cleaner distinction between temporary restriction and permanent denial.',
          ],
          example: 'A regional manager may be restricted from a broader data slice until a higher-level grant is provided.',
          decisionOwner: 'Usually PM with security, governance, or compliance input.',
        },
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
        inlineDetails: [
          'This gives the product a more precise failure model than a single generic no.',
          'It helps users understand whether asking differently or getting approval could change the outcome.',
        ],
        helpDialog: {
          title: 'Restricted vs Denied',
          summary: 'This determines whether the system exposes two different blocked outcomes instead of collapsing them into one.',
          bullets: [
            'Restricted means the action is not currently allowed but could be unlocked with the right authority or scope.',
            'Denied means the action is fundamentally out of policy or out of scope.',
            'This distinction is important for trust, user guidance, and audit clarity.',
          ],
          example: 'Cross-region account access may be restricted, while raw CRM export may be denied outright.',
          decisionOwner: 'Usually PM, governance, and security together.',
        },
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
        inlineDetails: [
          'This is an advanced authority model and usually needs platform or security input.',
          'If this is unfamiliar, the safe PM answer is often to leave it off until developer design clarifies the need.',
        ],
        helpDialog: {
          title: 'Delegation Tokens',
          summary: 'Delegation tokens let an agent act with authority derived from a user or service, but only within defined bounds.',
          bullets: [
            'They are useful when an agent needs to carry limited, scoped authority across requests or services.',
            'They should not be treated as a generic permission shortcut.',
            'This is typically a deeper platform capability, not a casual product toggle.',
          ],
          example: 'A user grants an agent authority to prepare follow-up work only for accounts in a specific region.',
          decisionOwner: 'Usually platform/security architecture, with PM aware of the business need.',
        },
        answerType: 'boolean',
        fieldMappings: [{ path: 'auth.delegation_tokens', label: 'Delegation Tokens' }],
        defaultValue: false,
      },
      {
        id: 'scoped-authority',
        prompt: 'Should authority be scoped to limit what agents can do?',
        helpText: 'Scoped authority keeps the system from treating all permissions as global or unlimited.',
        inlineDetails: [
          'Scope can apply to region, account set, action type, service, or purpose.',
          'This is usually a good default when the system has meaningful boundaries.',
        ],
        helpDialog: {
          title: 'Scoped Authority',
          summary: 'Scoped authority means permissions are limited to specific boundaries instead of being universally valid everywhere.',
          bullets: [
            'It helps contain risk by preventing broad implied access.',
            'It makes actor-aware behavior more precise and auditable.',
            'This is a common requirement when different users should see or do different things.',
          ],
          example: 'An account manager can view only owned or regional accounts, not the full company dataset.',
          decisionOwner: 'Usually PM and security/governance stakeholders together.',
        },
        answerType: 'boolean',
        fieldMappings: [{ path: 'auth.scoped_authority', label: 'Scoped Authority' }],
        defaultValue: false,
      },
      {
        id: 'purpose-binding',
        prompt: 'Should delegated authority be bound to a specific purpose?',
        helpText:
          'Purpose binding ensures agents act within the intent of their delegated authority',
        inlineDetails: [
          'This prevents a grant intended for one use from silently being reused for something broader.',
          'It is especially useful when agents compose multiple steps on behalf of users.',
        ],
        helpDialog: {
          title: 'Purpose Binding',
          summary: 'Purpose binding ties delegated authority to a specific intended use, not just a generic permission bucket.',
          bullets: [
            'It reduces the chance that an agent reuses authority outside the context it was granted for.',
            'It supports clearer audit trails and more predictable safety boundaries.',
            'This matters most when delegation crosses services or compound workflows.',
          ],
          example: 'Authority granted to prepare assignment previews should not also allow direct execution or external dispatch.',
          decisionOwner: 'Usually PM with strong input from governance and platform architecture.',
        },
        answerType: 'boolean',
        fieldMappings: [{ path: 'auth.purpose_binding', label: 'Purpose Binding' }],
        defaultValue: false,
      },
      {
        id: 'approval-expectation',
        prompt: 'Should high-risk actions require explicit approval before execution?',
        helpText:
          'This captures approval intent as a business constraint — the system does not yet have a first-class approval model',
        inlineDetails: [
          'Use yes when a user or manager should explicitly approve risky or write-adjacent actions.',
          'This is a business control expectation, even if the exact approval mechanism is designed later.',
        ],
        helpDialog: {
          title: 'Approval Expectations',
          summary: 'This captures whether high-risk or write-adjacent actions should stop for explicit approval before they progress.',
          bullets: [
            'Approval is appropriate when the action could cause operational, financial, reputational, or access risk.',
            'The PM decision is about whether approval is required, not about the exact UI or backend workflow.',
            'Developer design can later define how approval records, approvers, and transitions work.',
          ],
          example: 'Preparing reassignment or routing actions may be allowed, but actual progression should stop until an approver signs off.',
          decisionOwner: 'Usually PM with business operations or governance stakeholders.',
        },
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
        inlineDetails: [
          'Use this when failure handling should be a product requirement, not just an engineering afterthought.',
          'This matters more when blocked or failed actions have operational or user-facing consequences.',
        ],
        helpDialog: {
          title: 'Recovery Guidance',
          summary: 'This asks whether the system should have an explicit expected posture for failures instead of leaving recovery entirely implicit.',
          bullets: [
            'Choose yes when failures need a clear expected response such as retrying, escalating, or failing safely.',
            'Choose no when normal engineering defaults are sufficient and no special business posture is required.',
            'This is about the expectation that recovery be designed intentionally, not about the exact implementation mechanism.',
          ],
          example: 'A system that prepares sensitive operational actions may need a clear recovery posture if approval or policy checks fail midway through execution.',
          decisionOwner: 'Usually PM with operations or platform input.',
        },
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
        inlineDetails: [
          'This is the product-level expectation for failure handling, not a low-level retry implementation detail.',
          'Choose the default posture you want the system to follow when work cannot proceed safely.',
        ],
        helpDialog: {
          title: 'Blocked or Failed Action Posture',
          summary: 'This asks what the system should do by default when an action cannot proceed or when execution fails.',
          bullets: [
            'Retry with Backoff means the system should try again automatically using a controlled retry pattern.',
            'Escalate to Human means the system should stop and hand the case to a person for review or resolution.',
            'Fail Safe means the system should halt and leave the system in a safe known state instead of trying to push through.',
            'Not Specified means you are not yet defining a product-level expectation for blocked or failed work.',
            'This choice should reflect business risk and operational posture, not just engineering convenience.',
          ],
          example: 'A follow-up preparation flow might escalate to a human when authority is unclear, while a non-critical transient fetch could retry with backoff.',
          decisionOwner: 'Usually PM with operations, governance, or platform input depending on the risk level.',
        },
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
    title: 'Evidence and Traceability',
    description: 'What evidence should the business be able to review later about what happened and why?',
    questions: [
      {
        id: 'needs-audit',
        prompt: 'Should this system keep a durable record of important actions?',
        helpText: 'Use this when business, compliance, or operational review requires records that survive restarts.',
        inlineDetails: [
          'This is about retained evidence, not about the exact storage technology.',
          'Choose yes when later review, dispute handling, or governance depends on durable records.',
        ],
        helpDialog: {
          title: 'Durable Action Records',
          summary: 'This asks whether the business needs the system to preserve records of important actions for later review.',
          bullets: [
            'Choose yes when actions need to be reviewable after the fact for governance, compliance, support, or operations.',
            'Choose no when lightweight logs are enough and durable business evidence is not required.',
            'Developer design will later define how those records are stored and accessed.',
          ],
          example: 'Approval-gated or externally visible actions often need durable records so teams can confirm what happened later.',
          decisionOwner: 'Usually PM with governance, compliance, or operations input.',
        },
        answerType: 'boolean',
        fieldMappings: [{ path: 'audit.durable', label: 'Durable Audit' }],
        defaultValue: false,
      },
      {
        id: 'needs-searchable',
        prompt: 'Should those records be searchable later?',
        helpText: 'Use this when teams need to find records by actor, action, time, or related business context.',
        answerType: 'boolean',
        fieldMappings: [{ path: 'audit.searchable', label: 'Searchable Audit' }],
        defaultValue: false,
      },
      {
        id: 'invocation-tracking',
        prompt: 'Should each execution be traceable as its own identifiable event?',
        helpText: 'Use this when support, audit, or engineering teams need to refer to one exact execution later.',
        answerType: 'boolean',
        fieldMappings: [{ path: 'lineage.invocation_id', label: 'Invocation ID' }],
        defaultValue: false,
      },
      {
        id: 'task-tracking',
        prompt: 'Should related executions be grouped into one traceable unit of work?',
        helpText: 'Use this when a single business action can span several internal executions or retries.',
        answerType: 'boolean',
        fieldMappings: [{ path: 'lineage.task_id', label: 'Task ID' }],
        defaultValue: false,
      },
      {
        id: 'parent-tracking',
        prompt: 'Should the system preserve parent-child execution chains for later reconstruction?',
        helpText:
          'Use this when teams need to reconstruct how one action led to another across a workflow.',
        answerType: 'boolean',
        fieldMappings: [
          { path: 'lineage.parent_invocation_id', label: 'Parent Invocation ID' },
        ],
        defaultValue: false,
      },
      {
        id: 'client-reference',
        prompt: 'Should external systems be able to attach their own reference IDs?',
        helpText:
          'Use this when outside systems need to correlate their business records with this system later.',
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
    title: 'Cross-Service Expectations',
    description: 'How should work behave when it moves across more than one service?',
    questions: [
      {
        id: 'service-handoffs',
        prompt: 'Will work need to carry authority across service boundaries?',
        helpText: 'Use this when one service begins work and another service must continue it under controlled authority.',
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
        prompt: 'Should teams be able to reconstruct work across service boundaries later?',
        helpText:
          'Use this when multi-service behavior must be reviewable as one connected story after the fact.',
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
        prompt: 'Should execution chains stay intact as work moves across services?',
        helpText: 'Use this when downstream services should preserve the same execution trail instead of starting fresh.',
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
