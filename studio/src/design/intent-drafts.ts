import type { IntentInterpretation } from './project-types'
import { consumerModeLabel, type ProjectConsumerMode } from './consumer-mode'

export function slugify(input: string): string {
  return input
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

export function normalizedWords(...parts: string[]): Set<string> {
  return new Set(
    parts
      .join(' ')
      .toLowerCase()
      .split(/[^a-z0-9]+/)
      .map(item => item.trim())
      .filter(Boolean),
  )
}

export function titleize(input: string): string {
  return input
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (match) => match.toUpperCase())
}

export function cleanSentence(input: string): string {
  return input.replace(/\s+/g, ' ').trim()
}

export function scenarioTitleFromStarter(text: string, index: number): string {
  const cleaned = cleanSentence(text).replace(/^add a scenario where\s+/i, '').replace(/^describe\s+/i, '')
  const compact = cleaned.replace(/\.$/, '')
  if (!compact) return `Scenario ${index}`
  const shortened = compact.length > 72 ? `${compact.slice(0, 69).trim()}...` : compact
  return titleize(shortened)
}

export function inferScenarioCategory(text: string): 'safety' | 'recovery' | 'orchestration' | 'cross_service' | 'observability' {
  const words = normalizedWords(text)
  if (
    words.has('handoff') ||
    words.has('handoffs') ||
    words.has('cross') ||
    words.has('services') ||
    words.has('service')
  ) {
    return 'cross_service'
  }
  if (words.has('verify') || words.has('verification') || words.has('confirm') || words.has('reconcile')) {
    return 'observability'
  }
  if (words.has('refresh') || words.has('stale') || words.has('expired') || words.has('revalidate')) {
    return 'recovery'
  }
  if (words.has('follow') || words.has('followup') || words.has('async') || words.has('approval')) {
    return 'orchestration'
  }
  return 'safety'
}

export function makeRequirementsTemplate(name: string, domain: string) {
  return {
    system: {
      name: slugify(name) || 'new-service',
      domain: domain || 'general',
      deployment_intent: 'public_http_service',
    },
    transports: { http: true, stdio: false, grpc: false },
    trust: { mode: 'signed', checkpoints: false },
    auth: {
      delegation_tokens: true,
      purpose_binding: true,
      scoped_authority: true,
    },
    permissions: {
      preflight_discovery: true,
      restricted_vs_denied: true,
    },
    audit: { durable: true, searchable: true },
    lineage: {
      invocation_id: true,
      client_reference_id: true,
      task_id: true,
      parent_invocation_id: true,
    },
    risk_profile: {},
    business_constraints: {},
    scale: {
      shape_preference: 'production_single_service',
      high_availability: false,
    },
  }
}

export function makeRequirementsTemplateFromIntent(
  result: IntentInterpretation,
  intent: string,
  projectName: string,
  projectDomain: string,
  consumerMode: ProjectConsumerMode = 'hybrid',
) {
  const data = makeRequirementsTemplate(projectName, projectDomain)
  const words = normalizedWords(
    intent,
    result.summary,
    result.recommended_shape_reason,
    ...result.requirements_focus,
    ...result.scenario_starters,
    ...result.next_steps,
  )

  data.system.name = slugify(projectName || result.title || 'new-service') || 'new-service'
  data.scale.shape_preference =
    result.recommended_shape_type === 'multi_service'
      ? 'multi_service_estate'
      : 'production_single_service'

  const constraints = data.business_constraints as Record<string, any>
  const mentionsBudget =
    words.has('budget') || words.has('cost') || words.has('spend') || words.has('price') || words.has('pricing')
  const mentionsApproval =
    words.has('approval') || words.has('approve') || words.has('approver') || words.has('escalate') || words.has('escalation')
  const mentionsRecovery =
    words.has('refresh') || words.has('stale') || words.has('expired') || words.has('revalidate') || words.has('recovery')
  const mentionsRisk =
    words.has('risk') || words.has('danger') || words.has('dangerous') || words.has('destructive') || words.has('delete')

  constraints.spending_possible = mentionsBudget
  constraints.cost_visibility_required = mentionsBudget
  constraints.approval_expected_for_high_risk = mentionsApproval || mentionsRisk
  constraints.recovery_sensitive = mentionsRecovery
  constraints.primary_consumer = consumerModeLabel(consumerMode)
  constraints.agent_consumed_flow = consumerMode === 'agent_anip' || consumerMode === 'hybrid'
  constraints.human_operated_flow = consumerMode === 'human_app' || consumerMode === 'hybrid'
  if (consumerMode === 'agent_anip') {
    constraints.low_glue_machine_consumption_required = true
  } else if (consumerMode === 'human_app') {
    constraints.operator_explainability_required = true
  } else {
    constraints.hybrid_handoff_expected = true
  }
  constraints.blocked_failure_posture = mentionsBudget || mentionsApproval || mentionsRecovery || mentionsRisk
    ? 'structured_blocked'
    : 'basic_failure_surface'

  return data
}

export function makeScenarioTemplatesFromIntent(result: IntentInterpretation, consumerMode: ProjectConsumerMode = 'hybrid') {
  const starters = result.scenario_starters.length
    ? result.scenario_starters.slice(0, 3)
    : ['Describe the normal success path that the service should handle cleanly.']
  const biasedStarters = [...starters]
  if (consumerMode === 'agent_anip') {
    biasedStarters.push('Add a scenario where an ANIP consumer must recover from a blocked action without hidden UI-only workflow knowledge.')
  } else if (consumerMode === 'human_app') {
    biasedStarters.push('Add a scenario where a human operator needs a clear explanation for why work was blocked or routed elsewhere.')
  } else {
    biasedStarters.push('Add a scenario where a person starts the flow and an agent or tool continues it through a bounded handoff.')
  }

  return biasedStarters.map((starter, index) => {
    const category = inferScenarioCategory(starter)
    const title = scenarioTitleFromStarter(starter, index + 1)
    const scenarioName = slugify(title) || `scenario-${index + 1}`
    const words = normalizedWords(starter)
    const actionCapability =
      words.has('book') || words.has('booking')
        ? 'book_the_primary_action'
        : words.has('verify') || words.has('verification')
          ? 'verify_the_outcome'
          : words.has('refresh') || words.has('stale')
            ? 'refresh_or_revalidate_before_acting'
            : words.has('approval') || words.has('approve')
              ? 'request_or_record_approval'
              : 'handle_the_primary_action'

    const expectedBehavior = [
      starter,
      category === 'cross_service'
        ? 'The service boundary should remain clear across the handoff.'
        : 'The system should make the intended control decision explicit.',
    ]

    const expectedSupport = [
      category === 'recovery'
        ? 'The contract should make refresh or recovery guidance explicit.'
        : category === 'observability'
          ? 'The contract should expose enough context to verify and explain the outcome.'
          : category === 'cross_service'
            ? 'The contract should preserve continuity and handoff meaning across services.'
            : 'The contract should make purpose, constraints, and blocked-action meaning explicit.',
    ]

    return {
      title,
      data: {
        scenario: {
          name: scenarioName,
          category,
          narrative: starter,
          context: {
            capability: actionCapability,
          },
          expected_behavior: expectedBehavior,
          expected_anip_support: expectedSupport,
        },
      },
    }
  })
}

export function makeShapeTemplateFromIntent(result: IntentInterpretation, projectName: string, consumerMode: ProjectConsumerMode = 'hybrid') {
  const rootName = projectName || 'new-service'
  const shapeName = titleize(rootName)
  const primaryServiceId = slugify(rootName) || 'primary-service'
  const conceptIds = result.domain_concepts.map((concept) => ({
    id: slugify(concept) || `concept-${crypto.randomUUID()}`,
    name: concept,
  }))

  const primaryService = {
    id: primaryServiceId,
    name: shapeName,
    role: 'primary service',
    responsibilities: [
      consumerMode === 'human_app'
        ? 'Keep the human-facing workflow easy to understand and explain.'
        : consumerMode === 'agent_anip'
          ? 'Keep the ANIP capability surface explicit so tools and agents do not need hidden local glue.'
          : 'Own the main workflow in a way that stays understandable for people and explicit for ANIP consumers.',
      'Own the main action and the core control checks around it.',
      ...result.requirements_focus.slice(0, 2),
    ],
    capabilities: [
      'handle_primary_action',
      ...result.scenario_starters.slice(0, 2).map((item) => slugify(item) || 'support_scenario'),
    ],
    owns_concepts: conceptIds.slice(0, Math.max(1, conceptIds.length - 1)).map((concept) => concept.id),
  }

  const services: Array<Record<string, any>> = [primaryService]
  const coordination: Array<Record<string, any>> = []

  if (result.recommended_shape_type === 'multi_service') {
    const lowerSuggestions = result.service_suggestions.map((item) => item.toLowerCase())

    if (lowerSuggestions.some((item) => item.includes('approval'))) {
      services.push({
        id: 'approval-service',
        name: 'Approval Service',
        role: 'approval boundary',
        responsibilities: ['Track approvals and decisions that should not be hidden inside the main action.'],
        capabilities: ['request_approval', 'record_approval_decision'],
        owns_concepts: conceptIds.filter((concept) => concept.name.toLowerCase().includes('approval')).map((concept) => concept.id),
      })
      coordination.push({
        from: primaryServiceId,
        to: 'approval-service',
        relationship: 'handoff',
        description: 'Send blocked or exceptional work for approval before the main action proceeds.',
      })
    }

    if (lowerSuggestions.some((item) => item.includes('verification'))) {
      services.push({
        id: 'verification-service',
        name: 'Verification Service',
        role: 'verification boundary',
        responsibilities: ['Verify the outcome after the initial action completes.'],
        capabilities: ['verify_outcome', 'record_verification_result'],
        owns_concepts: conceptIds.filter((concept) => concept.name.toLowerCase().includes('outcome')).map((concept) => concept.id),
      })
      coordination.push({
        from: primaryServiceId,
        to: 'verification-service',
        relationship: 'verification',
        description: 'Verify that the completed action actually reached the intended end state.',
      })
    }

    if (lowerSuggestions.some((item) => item.includes('refresh') || item.includes('revalidation'))) {
      services.push({
        id: 'revalidation-service',
        name: 'Revalidation Service',
        role: 'refresh boundary',
        responsibilities: ['Refresh stale or expired inputs before the main action continues.'],
        capabilities: ['refresh_input', 'revalidate_input'],
        owns_concepts: conceptIds.filter((concept) => concept.name.toLowerCase().includes('quote')).map((concept) => concept.id),
      })
      coordination.push({
        from: primaryServiceId,
        to: 'revalidation-service',
        relationship: 'verification',
        description: 'Refresh or revalidate inputs before the main action proceeds.',
      })
    }
  }

  if (result.recommended_shape_type === 'multi_service' && services.length === 1) {
    services.push({
      id: 'support-service',
      name: 'Support Service',
      role: 'supporting responsibility',
      responsibilities: ['Handle the secondary follow-up, coordination, or verification responsibility implied by the brief.'],
      capabilities: ['handle_followup_or_coordination'],
      owns_concepts: [],
    })
    coordination.push({
      from: primaryServiceId,
      to: 'support-service',
      relationship: 'handoff',
      description: 'Separate the secondary responsibility instead of hiding it inside one oversized service.',
    })
  }

  return {
    shape: {
      id: slugify(`${shapeName}-shape`) || 'service-shape',
      name: shapeName,
      type: result.recommended_shape_type === 'multi_service' ? 'multi_service' : 'single_service',
      notes: [result.recommended_shape_reason, ...result.service_suggestions.slice(0, 2)],
      services,
      coordination,
      domain_concepts: conceptIds.map((concept, index) => ({
        id: concept.id,
        name: concept.name,
        meaning: `Business concept: ${concept.name}`,
        owner: services.length > 1 && concept.name.toLowerCase().includes('approval')
          ? 'approval-service'
          : index === conceptIds.length - 1 && services.length > 1
            ? 'shared'
            : primaryServiceId,
        sensitivity: concept.name.toLowerCase().includes('approval') || concept.name.toLowerCase().includes('budget') ? 'medium' : 'none',
      })),
    },
  }
}
