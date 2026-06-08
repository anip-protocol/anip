import type { ProjectIssueSummary } from './project-issues'

export type DeveloperDesignContextBlock =
  | 'business'
  | 'services'
  | 'capabilities'
  | 'scenarios'
  | 'governance'
  | 'consumability'
  | 'delivery'

export type DeveloperDesignContextStatus = 'ready' | 'draftable' | 'needs_clarification' | 'blocked'

export interface DeveloperDesignContext {
  lane: string
  title: string
  purpose: string
  produces: string
  next: string
  upstream: string
  current: string
  downstream: string
  artifact: string
  technical: string[]
  routeSuffix: string
  issueSources: Array<{ key: string; label: string; routeSuffix: string }>
}

export interface DeveloperDesignContextSourceSummary {
  key: string
  label: string
  path: string
  status: DeveloperDesignContextStatus
  issues: string[]
  issueCount: number
  current: boolean
}

export interface DeveloperDesignContextBlockSummary {
  block: DeveloperDesignContextBlock
  status: DeveloperDesignContextStatus
  issues: string[]
  issueCount: number
  issuePath: string
  sources: DeveloperDesignContextSourceSummary[]
}

export const developerDesignBlockOrder: DeveloperDesignContextBlock[] = [
  'business',
  'services',
  'capabilities',
  'scenarios',
  'governance',
  'consumability',
  'delivery',
]

export const developerDesignContexts: Record<DeveloperDesignContextBlock, DeveloperDesignContext> = {
  business: {
    lane: 'Business Handoff',
    title: 'Locked Product Baseline',
    purpose: 'Freezes PM-owned intent so developer work starts from reviewed Product Design truth.',
    produces: 'A stable baseline for Developer Design and future revision comparison.',
    next: 'Formalize service boundaries, capabilities, controls, and delivery settings against this baseline.',
    upstream: 'Source documents and reviewed Product Design.',
    current: 'Locked PM baseline selected for this Developer revision.',
    downstream: 'Every Developer Design page uses this as the reviewed business truth.',
    artifact: 'Developer baseline lock',
    technical: ['product_revision_id', 'developer_baseline', 'baseline_digest'],
    routeSuffix: '/developer/handoff',
    issueSources: [
      { key: 'project-developer-handoff', label: 'Locked Product Handoff', routeSuffix: '/developer/handoff' },
    ],
  },
  services: {
    lane: 'Contract Shape',
    title: 'Service Boundaries',
    purpose: 'Defines system identity, service ownership, runtime backends, and authority posture.',
    produces: 'Service topology, runtime backend, and ownership metadata used by generation and verification.',
    next: 'Capability, governance, and generation pages consume these service boundaries.',
    upstream: 'Locked Product Design service intent and business ownership.',
    current: 'Concrete services, ownership, responsibilities, runtime backends, and authority posture.',
    downstream: 'Capability ownership, generated service entrypoints, Registry package topology, and verifier expectations.',
    artifact: 'Developer service topology',
    technical: ['services[]', 'service_id', 'service_owner', 'backend_bindings'],
    routeSuffix: '/developer/service-formalization',
    issueSources: [
      { key: 'project-developer-service-formalization', label: 'Service Formalization', routeSuffix: '/developer/service-formalization' },
    ],
  },
  capabilities: {
    lane: 'Contract Shape',
    title: 'Capabilities and Data',
    purpose: 'Defines the ANIP-facing operations, inputs, outputs, data surfaces, and behavior metadata.',
    produces: 'Capability and data contracts that become the package/service definition.',
    next: 'Coverage, simulator, generator, verifier, and Registry publication consume these contracts.',
    upstream: 'Reviewed scenarios, service boundaries, and product capability expectations.',
    current: 'ANIP-facing capability names, inputs, outputs, behavior, data contracts, and effects.',
    downstream: 'Contract definition, generated handlers, simulator probes, verifier checks, and app-consumability hints.',
    artifact: 'Capability and data contract',
    technical: ['capabilities[]', 'inputs[]', 'outputs', 'business_effects', 'agent_consumability'],
    routeSuffix: '/developer/capability-formalization',
    issueSources: [
      { key: 'project-developer-capability-formalization', label: 'Capability Formalization', routeSuffix: '/developer/capability-formalization' },
      { key: 'project-developer-data-contract-formalization', label: 'Data Contract Formalization', routeSuffix: '/developer/data-contract-formalization' },
    ],
  },
  scenarios: {
    lane: 'Contract Shape',
    title: 'Scenario Behavior',
    purpose: 'Turns PM scenarios into formal actor context, business scope, execution semantics, and expected outcomes.',
    produces: 'Scenario behavior that guides readiness checks, simulator probes, and verification expectations.',
    next: 'Coverage and verification use these scenarios to prove the implementation still reflects Product Design.',
    upstream: 'PM-owned scenarios and acceptance intent from the locked baseline.',
    current: 'Actor context, execution semantics, expected outcomes, and scenario-to-capability coverage.',
    downstream: 'Readiness checks, simulator probes, verification expectations, and traceability evidence.',
    artifact: 'Scenario execution contract',
    technical: ['scenarios[]', 'actor_context', 'execution_semantics', 'expected_outcomes'],
    routeSuffix: '/developer/scenario-formalization',
    issueSources: [
      { key: 'project-developer-scenario-formalization', label: 'Scenario Coverage Intent', routeSuffix: '/developer/scenario-formalization' },
      { key: 'project-developer-scenario-execution-semantics', label: 'Scenario Execution Semantics', routeSuffix: '/developer/scenario-execution-semantics' },
    ],
  },
  governance: {
    lane: 'Controls and Consumability',
    title: 'Roles, Access, and Evidence',
    purpose: 'Defines roles, permissions, capability requirements, and audit evidence without mixing them into one editing surface.',
    produces: 'Runtime control metadata that prevents capability behavior from becoming implicit app code.',
    next: 'Generation and verification consume these controls as part of the compiled contract.',
    upstream: 'Service boundaries, capability effects, data sensitivity, and PM-owned permission expectations.',
    current: 'Role access review, service capability requirements, and audit lineage.',
    downstream: 'Generated runtime policy, verifier enforcement, and service integration handoff.',
    artifact: 'Governance and binding contract',
    technical: ['actor_expectations', 'permission_intent_bindings', 'runtime_policy_bindings', 'audit'],
    routeSuffix: '/developer/governance-bindings',
    issueSources: [
      { key: 'project-developer-governance-bindings', label: 'Roles & Access', routeSuffix: '/developer/governance-bindings' },
      { key: 'project-developer-audit-lineage', label: 'Audit & Lineage', routeSuffix: '/developer/audit-lineage' },
      { key: 'project-integration-fronting', label: 'Govern API / MCP', routeSuffix: '/developer/integration-fronting' },
    ],
  },
  consumability: {
    lane: 'Controls and Consumability',
    title: 'Agent Readiness and App Glue',
    purpose: 'Reviews what an ANIP-aware app can consume natively and what explicit app glue remains acceptable.',
    produces: 'Readiness decisions and optional app-consumability metadata packaged with the contract.',
    next: 'Simulator, generator, Registry package export, and app handoff use this as reviewed guidance.',
    upstream: 'Capabilities, scenarios, business effects, approval boundaries, and simulator evidence.',
    current: 'Reviewed readiness findings, acceptable warnings, explicit app glue, and app-consumption hints.',
    downstream: 'Package handoff, generated guidance files, simulator regression evidence, and app implementation planning.',
    artifact: 'Readiness and app-glue review',
    technical: ['agent_consumption_readiness', 'app_glue', 'readiness_findings', 'simulator_report'],
    routeSuffix: '/developer/app-glue',
    issueSources: [
      { key: 'project-developer-coverage', label: 'Agent & App Glue', routeSuffix: '/developer/app-glue' },
    ],
  },
  delivery: {
    lane: 'Delivery',
    title: 'Generation and Evidence',
    purpose: 'Controls generation settings, compiled definition identity, extension points, and proof expectations.',
    produces: 'A saved revision that generator, verifier, and Registry publication can reference exactly.',
    next: 'Generate, publish, verify, and attach runtime evidence to the same contract identity.',
    upstream: 'All locked Developer Design authoring surfaces and reviewed readiness decisions.',
    current: 'Compiled definition, generation settings, package identity, publication state, and verification evidence.',
    downstream: 'Registry publication, generated services, verifier receipts, runtime evidence, and future revision comparison.',
    artifact: 'Compiled Developer Definition',
    technical: ['developer_definition', 'definition_digest', 'package_manifest', 'generation_settings', 'verification_evidence'],
    routeSuffix: '/developer/definition',
    issueSources: [
      { key: 'project-developer-generation-settings', label: 'Generation Settings', routeSuffix: '/developer/generation-settings' },
      { key: 'project-developer-verification-expectations', label: 'Evidence & Verification Plan', routeSuffix: '/developer/verification-expectations' },
      { key: 'project-developer-definition', label: 'Developer Definition', routeSuffix: '/developer/definition' },
    ],
  },
}

export function developerDesignPath(projectId: string, block: DeveloperDesignContextBlock): string {
  return `/design/projects/${projectId}${developerDesignContexts[block].routeSuffix}`
}

export function developerDesignStatusLabel(status: DeveloperDesignContextStatus): string {
  switch (status) {
    case 'ready':
      return 'Ready'
    case 'draftable':
      return 'Draftable'
    case 'needs_clarification':
      return 'Needs review'
    default:
      return 'Blocked'
  }
}

export function summarizeDeveloperDesignBlocks(params: {
  projectId: string
  issueIndex: Record<string, ProjectIssueSummary | undefined>
  currentBlock?: DeveloperDesignContextBlock
  currentPageKey?: string
  currentStatus?: DeveloperDesignContextStatus
  currentIssues?: string[]
}): Record<DeveloperDesignContextBlock, DeveloperDesignContextBlockSummary> {
  return Object.fromEntries(developerDesignBlockOrder.map((block) => {
    const context = developerDesignContexts[block]
    const sourceIssues = context.issueSources
      .map((source) => ({ source, issue: params.issueIndex[source.key] }))
      .filter((item): item is { source: { key: string; label: string; routeSuffix: string }; issue: ProjectIssueSummary } => Boolean(item.issue))
    const currentIssueMessages = block === params.currentBlock ? (params.currentIssues ?? []) : []
    const currentSource = context.issueSources.find((source) => source.key === params.currentPageKey)
    const messages = [
      ...sourceIssues.flatMap(({ source, issue }) =>
        issue.messages.map((message) => `${source.label}: ${message}`),
      ),
      ...currentIssueMessages,
    ]
    const uniqueMessages = [...new Set(messages)]
    const hasError = sourceIssues.some(({ issue }) => issue.severity === 'error') || (block === params.currentBlock && params.currentStatus === 'blocked')
    const status: DeveloperDesignContextStatus = hasError
      ? 'blocked'
      : uniqueMessages.length > 0
        ? 'needs_clarification'
        : block === params.currentBlock && params.currentStatus
          ? params.currentStatus
          : 'ready'
    const firstIssueSource = sourceIssues[0]?.source
    const sources = context.issueSources.map((source) => {
      const sourceIssue = params.issueIndex[source.key]
      const isCurrent = source.key === params.currentPageKey
      const sourceCurrentMessages = isCurrent ? (params.currentIssues ?? []) : []
      const sourceMessages = [
        ...(sourceIssue?.messages ?? []),
        ...sourceCurrentMessages,
      ]
      const uniqueSourceMessages = [...new Set(sourceMessages)]
      const sourceStatus: DeveloperDesignContextStatus = sourceIssue?.severity === 'error' || (isCurrent && params.currentStatus === 'blocked')
        ? 'blocked'
        : uniqueSourceMessages.length > 0
          ? 'needs_clarification'
          : isCurrent && params.currentStatus
            ? params.currentStatus
            : 'ready'
      return {
        key: source.key,
        label: source.label,
        path: `/design/projects/${params.projectId}${source.routeSuffix}`,
        status: sourceStatus,
        issues: uniqueSourceMessages.slice(0, 4),
        issueCount: uniqueSourceMessages.length,
        current: isCurrent,
      }
    })
    return [block, {
      block,
      status,
      issues: uniqueMessages.slice(0, 4),
      issueCount: uniqueMessages.length,
      issuePath: firstIssueSource
        ? `/design/projects/${params.projectId}${firstIssueSource.routeSuffix}`
        : currentSource
          ? `/design/projects/${params.projectId}${currentSource.routeSuffix}`
          : developerDesignPath(params.projectId, block),
      sources,
    }]
  })) as Record<DeveloperDesignContextBlock, DeveloperDesignContextBlockSummary>
}
