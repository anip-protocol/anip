import type {
  ArtifactRecord,
  EvaluationRecord,
  ProjectDetail,
  RequirementsRecord,
  ShapeRecord,
} from './project-types'
import { consumerModeFromLabels, consumerModeLabel } from './consumer-mode'

interface ShareableArtifactContext {
  project: ProjectDetail | null
  sourceIntent?: string
  sourceRequirements?: RequirementsRecord | null
  requirements: RequirementsRecord | null
  scenarios?: ArtifactRecord[]
  scenario: ArtifactRecord | null
  shape: ShapeRecord | null
  evaluation: EvaluationRecord | null
}

export function buildPmSpec(context: ShareableArtifactContext): string {
  const { project, sourceRequirements, requirements, scenarios = [], scenario, shape, evaluation } = context
  const sourceRequirementData = (sourceRequirements?.data ?? {}) as Record<string, any>
  const sourceDocument = (sourceRequirementData.source_document ?? {}) as Record<string, any>
  const businessSpec = (sourceRequirementData.business_spec ?? {}) as Record<string, any>
  const requirementData = unwrap(requirements?.data, 'requirements')
  const scenarioData = unwrap(scenario?.data, 'scenario')
  const evaluationData = evaluation?.data?.evaluation ?? {}
  const behaviorTranslation = (requirementData?.behavior_translation ?? {}) as Record<string, any>
  const scenarioRecords = scenarios.length ? scenarios : (scenario ? [scenario] : [])

  const goalLines = stringList(businessSpec.business_goal)
  const behaviorFamilyLines = array(behaviorTranslation.behavior_families).map((item: any) => {
    const label = labelize(String(item?.class || 'behavior_class'))
    const expectation = String(item?.studio_expectation || '').trim()
    return expectation ? `${label} (Studio key: ${expectation})` : label
  })
  const representativeRequests = stringList(behaviorTranslation.representative_requests)
  const mustDo = goalLines.length
    ? goalLines
    : stringList(behaviorTranslation.goal_translation).map(item => labelize(item))
  const mustNot = stringList(businessSpec.non_goals).map(item => sentenceize(item))
  if (
    (requirementData?.business_constraints?.approval_required
      || requirementData?.business_constraints?.followup_execution_must_stop_for_approval
      || requirementData?.business_constraints?.approval_expected_for_high_risk)
    && !mustNot.includes('No downstream mutations without approval')
  ) {
    mustNot.push('No downstream mutations without approval')
  }
  const safetyPosture = pmSafetyPostureLines(requirementData)
  const validationLines = [
    'this PM spec is representative, not exhaustive',
    'this business spec is visible as a source artifact',
    'Studio translates this spec into bounded requirements and scenarios',
    'Studio developer design derives an implementation shape from those requirements',
    'the running service code is generated from that design path, then completed and run',
    'Studio validates the running service against observed ANIP metadata and runtime behavior',
    'more than one agent runtime can consume the same governed service correctly',
  ]
  const translationLines = [
    `Source artifact: ${sourceRequirements?.title || 'None linked'}${sourceDocument.path ? ` (${sourceDocument.path})` : ''}`,
    `Translated requirements: ${requirements?.title || 'None selected'}`,
    `Scenario pack size: ${scenarioRecords.length}`,
    `Active scenario: ${scenario?.title || 'None selected'}`,
    `Service design: ${shape?.title || 'None selected'}`,
    `Evaluation status: ${describeEvaluation(evaluation)}`,
  ]

  return [
    `# PM Spec: ${project?.name || sourceRequirements?.title || 'Unnamed Project'}`,
    '',
    `Generated: ${new Date().toLocaleString()}`,
    '',
    '## Traceability',
    bulletLines(traceabilityLines(context, 'Canonical PM Spec')),
    '',
    '## Purpose',
    businessSpec.summary
      ? `${businessSpec.summary}`
      : 'Canonical PM-readable business specification derived from the linked source business document and current Studio translation.',
    '',
    sourceDocument.path ? `Source document: ${sourceDocument.path}` : null,
    'This PM spec captures behavior classes and representative scenario requests, not an exhaustive inventory of every possible user utterance.',
    '',
    '## Business Source',
    '',
    '### Problem',
    project?.summary || context.sourceIntent || 'The business problem still needs to be described clearly.',
    '',
    '### Business Goal',
    bulletLines(mustDo.length ? mustDo : ['Define the bounded business goals for this capability.']),
    '',
    '### What The Agent Must Be Able To Do',
    bulletLines(mustDo.length ? mustDo : ['No bounded capability goals are captured yet.']),
    '',
    '### What It Must Not Do',
    bulletLines(mustNot.length ? mustNot : ['No explicit non-goals are recorded yet.']),
    '',
    '### Behavior Classes',
    bulletLines(behaviorFamilyLines.length ? behaviorFamilyLines : ['No behavior families are recorded yet.']),
    '',
    '### Representative Scenario Requests',
    'These requests are representative, not exhaustive.',
    bulletLines(representativeRequests.length ? representativeRequests : scenarioRecords.map(item => item.title)),
    '',
    '### Business Safety Posture',
    bulletLines(safetyPosture.length ? safetyPosture : ['No explicit business safety posture is recorded yet.']),
    '',
    '## Validation Intent',
    bulletLines(validationLines),
    '',
    '## Studio Translation',
    bulletLines(translationLines),
    '',
    '### Active Scenario',
    scenario?.title || 'None selected',
    '',
    '#### Business Behavior Expectations',
    bulletLines([
      scenarioData?.narrative ? `Narrative: ${scenarioData.narrative}` : 'Narrative not defined yet.',
      ...stringList(scenarioData?.expected_behavior).map(item => `Expected behavior: ${item}`),
    ]),
    '',
    '#### ANIP / Implementation Expectations',
    bulletLines(
      stringList(scenarioData?.expected_anip_support).map(item => `Expected ANIP support: ${item}`)
        .length
        ? stringList(scenarioData?.expected_anip_support).map(item => `Expected ANIP support: ${item}`)
        : ['No explicit ANIP / implementation expectations are recorded yet.'],
    ),
    '',
    '## Current Validation Readout',
    bulletLines([
      pmValidationStatusLine(context),
      ...validationConformanceLines(context),
      ...stringList(evaluationData?.what_would_improve).slice(0, 4).map(item => `Next change: ${item}`),
    ]),
  ].filter(Boolean).join('\n')
}

export function buildDeveloperSpec(context: ShareableArtifactContext & { proposal?: ArtifactRecord | null }): string {
  const { project, sourceRequirements, requirements, scenarios = [], scenario, proposal, shape, evaluation } = context
  const sourceRequirementData = (sourceRequirements?.data ?? {}) as Record<string, any>
  const sourceDocument = (sourceRequirementData.source_document ?? {}) as Record<string, any>
  const requirementData = unwrap(requirements?.data, 'requirements')
  const scenarioData = unwrap(scenario?.data, 'scenario')
  const proposalData = unwrap(proposal?.data, 'proposal')
  const shapeData = unwrap(shape?.data, 'shape')
  const evaluationData = evaluation?.data?.evaluation ?? {}
  const scenarioRecords = scenarios.length ? scenarios : (scenario ? [scenario] : [])

  const developerTranslation = (proposalData.developer_translation ?? {}) as Record<string, any>
  const implementationContract = (shapeData.implementation_contract ?? {}) as Record<string, any>
  const metadataContract = (shapeData.metadata_contract ?? {}) as Record<string, any>
  const implementationTrace = (shapeData.implementation_trace ?? {}) as Record<string, any>
  const capabilityContracts = array(shapeData.capability_contracts)
  const crossServiceContract = ((proposalData.cross_service_contract ?? shapeData.cross_service_contract) ?? {}) as Record<string, any>
  const serviceBehaviorCoverage = stringList(developerTranslation.service_behavior_coverage)
  const orchestrationContractCoverage = stringList(developerTranslation.orchestration_contract_coverage)
  const runtimeGlueInventory = stringList(developerTranslation.runtime_glue_inventory)
  const actorPolicyModel = (developerTranslation.actor_policy_model ?? {}) as Record<string, any>

  const translationLines = [
    `Source business spec: ${sourceRequirements?.title || 'None linked'}${sourceDocument.path ? ` (${sourceDocument.path})` : ''}`,
    `Translated requirements: ${requirements?.title || 'None selected'}`,
    `Active scenario: ${scenario?.title || 'None selected'}`,
    `Proposal: ${proposal?.title || 'None selected'}`,
    `Service design: ${shape?.title || 'None selected'}`,
    `Evaluation status: ${describeEvaluation(evaluation)}`,
  ]
  const requirementSignals = [
    requirementData?.system?.deployment_intent ? `Deployment intent: ${requirementData.system.deployment_intent}` : null,
    ...developerRequirementSignals(requirementData?.business_constraints ?? {}).map(item => `Business constraint: ${item}`),
    ...truthyLabels(requirementData?.auth ?? {}).map(item => `Auth signal: ${item}`),
    ...developerPermissionSignals(requirementData?.permissions ?? {}, requirementData?.business_constraints ?? {}).map(item => `Permission signal: ${item}`),
    ...truthyLabels(requirementData?.audit ?? {}).map(item => `Audit signal: ${item}`),
  ].filter(Boolean) as string[]
  const implementationLines = [
    `Implementation language: ${implementationContract.implementation_language || 'not recorded'}`,
    `Runtime profile: ${implementationContract.runtime_profile || 'not recorded'}`,
    `Transport profile: ${implementationContract.transport_profile || 'not recorded'}`,
    `Semantic backends: ${stringList(implementationContract.semantic_backends).join(', ') || 'not recorded'}`,
    `Implementation root: ${implementationContract.implementation_root || 'not recorded'}`,
    `Runtime entrypoint: ${implementationContract.runtime_entrypoint || 'not recorded'}`,
  ]
  const generatedFrom = (implementationContract.generated_from ?? {}) as Record<string, any>
  const generatedLines = [
    `Studio generation path: ${generatedFrom.studio_flow || 'not recorded'}`,
    `Generated scaffolds: ${stringList(generatedFrom.generated_artifacts).join(', ') || 'not recorded'}`,
    `Showcase runtime files: ${stringList(generatedFrom.showcase_runtime_files).join(', ') || 'not recorded'}`,
  ]
  const metadataLines = [
    ...truthyLabels(metadataContract).map(item => `Requirement: ${item}`),
    ...stringList(metadataContract.conformance_checks).map(item => `Conformance check: ${item}`),
  ]
  const traceLines = [
    `Business source artifact: ${implementationTrace.business_source_artifact_id || 'not recorded'}`,
    `Requirements artifact: ${implementationTrace.requirements_artifact_id || 'not recorded'}`,
    `Scenario artifact: ${implementationTrace.scenario_artifact_id || 'not recorded'}`,
    `Proposal artifact: ${implementationTrace.proposal_artifact_id || 'not recorded'}`,
    `Shape artifact: ${implementationTrace.shape_artifact_id || 'not recorded'}`,
    `Generated code used for showcase: ${yesNo(implementationTrace.generated_code_used_for_showcase)}`,
    `Running service: ${implementationTrace.running_service_id || 'not recorded'}`,
    ...stringList(implementationTrace.validation_method).map(item => `Validation method: ${item}`),
  ]

  return [
    `# Developer Spec: ${project?.name || 'Unnamed Project'}`,
    '',
    `Generated: ${new Date().toLocaleString()}`,
    '',
    '## Traceability',
    bulletLines(traceabilityLines(context, 'Canonical Developer Spec')),
    '',
    '## Technical Purpose',
    developerTranslation.translation_goal
      || 'Translate the bounded business behavior into an explicit service contract that can be implemented and validated.',
    '',
    '## Translation Chain',
    bulletLines(translationLines),
    '',
    '## Developer Enrichment',
    bulletLines(
      [
        ...stringList(developerTranslation.translation_principles).map(item => `Principle: ${item}`),
        ...stringList(developerTranslation.service_contract_decisions).map(item => `Decision: ${item}`),
      ].length
        ? [
            ...stringList(developerTranslation.translation_principles).map(item => `Principle: ${item}`),
            ...stringList(developerTranslation.service_contract_decisions).map(item => `Decision: ${item}`),
          ]
        : ['No explicit developer translation guidance is recorded yet.'],
    ),
    '',
    '## Behavior Placement',
    'Studio should make behavior placement explicit. Important behavior should live in the service contract or an explicit orchestration contract. Remaining runtime glue should stay thin, mechanical, and visible.',
    '',
    '### Service-Covered Behavior',
    bulletLines(serviceBehaviorCoverage.length ? serviceBehaviorCoverage : ['No explicit service-covered behavior inventory is recorded yet.']),
    '',
    '### Orchestration-Covered Behavior',
    bulletLines(orchestrationContractCoverage.length ? orchestrationContractCoverage : ['No explicit orchestration-covered behavior inventory is recorded yet.']),
    '',
    '### Cross-Service Contract',
    formatCrossServiceContract(crossServiceContract),
    '',
    '### Remaining Runtime Glue',
    bulletLines(runtimeGlueInventory.length ? runtimeGlueInventory : ['No remaining runtime glue inventory is recorded yet.']),
    '',
    '## Actor, Authority, And Audit Policy',
    formatActorPolicyModel(actorPolicyModel),
    '',
    '## Requirements Signals',
    bulletLines(requirementSignals.length ? requirementSignals : ['No structured requirement signals are recorded yet.']),
    '',
    '## Active Scenario Contract',
    bulletLines([
      scenarioData?.narrative ? `Narrative: ${scenarioData.narrative}` : 'Narrative not defined yet.',
      ...stringList(scenarioData?.expected_behavior).map(item => `Expected behavior: ${item}`),
      ...stringList(scenarioData?.expected_anip_support).map(item => `Expected ANIP support: ${item}`),
      `Scenario pack size: ${scenarioRecords.length}`,
    ]),
    '',
    '## Service Implementation Contract',
    bulletLines(implementationLines),
    '',
    '## Capability Contracts',
    formatCapabilityContracts(capabilityContracts),
    '',
    '## Metadata And Conformance Requirements',
    bulletLines(metadataLines.length ? metadataLines : ['No metadata contract is recorded yet.']),
    '',
    '## Generated Implementation Trace',
    bulletLines([...generatedLines, ...traceLines]),
    '',
    '## Current Runtime Validation',
    bulletLines([
      developerValidationStatusLine(context),
      ...validationConformanceLines(context),
      ...stringList(evaluationData?.glue_you_will_still_write).slice(0, 4).map(item => `Runtime gap: ${item}`),
      ...stringList(evaluationData?.what_would_improve).slice(0, 4).map(item => `Next change: ${item}`),
    ]),
  ].filter(Boolean).join('\n')
}

export function buildBusinessBrief(context: ShareableArtifactContext): string {
  const { project, sourceIntent, requirements, scenario, shape, evaluation } = context
  const requirementData = unwrap(requirements?.data, 'requirements')
  const scenarioData = unwrap(scenario?.data, 'scenario')
  const shapeData = unwrap(shape?.data, 'shape')
  const evaluationData = evaluation?.data?.evaluation ?? {}

  const businessConstraints = truthyLabels(requirementData?.business_constraints ?? {})
  const designSummary = describeBusinessShape(shapeData)
  const serviceNames = namedServices(shapeData)
  const workingWell = stringList(evaluationData?.handled_by_anip).slice(0, 4)
  const changesNext = (
    stringList(evaluationData?.what_would_improve).length
      ? stringList(evaluationData?.what_would_improve)
      : stringList(evaluationData?.glue_you_will_still_write)
  ).slice(0, 5)
  const conformanceLines = validationConformanceLines(context)

  return [
    `# Business Brief: ${project?.name || 'Unnamed Project'}`,
    '',
    `Generated: ${new Date().toLocaleString()}`,
    '',
    '## Traceability',
    bulletLines(traceabilityLines(context, 'Canonical Business Brief')),
    '',
    '## What We Are Building',
    project?.summary || 'No project summary has been written yet.',
    '',
    sourceIntent ? '### Original Plain-Language Brief' : null,
    sourceIntent || null,
    '',
    '## What Matters Most',
    bulletLines(businessConstraints.length
      ? businessConstraints
      : ['The project still needs clearer business constraints before this brief becomes persuasive.']),
    '',
    '## Current Service Design',
    designSummary,
    ...(serviceNames.length
      ? ['', '### Named Services', bulletLines(serviceNames)]
      : []),
    '',
    '## Real Situation Under Review',
    scenario?.title || 'No active real situation selected yet.',
    scenarioData?.narrative ? '' : null,
    scenarioData?.narrative || null,
    '',
    '## Latest Design Readout',
    evaluation
      ? `Result: ${evaluation.result}.`
      : 'No evaluation has been run yet.',
    '',
    '### Working Well',
    bulletLines(workingWell.length ? workingWell : ['No strong support areas have been recorded yet.']),
    '',
    '### ANIP Conformance Snapshot',
    bulletLines(conformanceLines),
    '',
    '### What Needs To Change',
    bulletLines(changesNext.length ? changesNext : ['No concrete next changes are recorded yet.']),
  ].filter(Boolean).join('\n')
}

export function buildEngineeringContract(context: ShareableArtifactContext): string {
  const { project, requirements, scenario, shape, evaluation } = context
  const requirementData = unwrap(requirements?.data, 'requirements')
  const scenarioData = unwrap(scenario?.data, 'scenario')
  const shapeData = unwrap(shape?.data, 'shape')
  const evaluationData = evaluation?.data?.evaluation ?? {}
  const services = array(shapeData?.services)
  const concepts = array(shapeData?.domain_concepts)
  const coordination = array(shapeData?.coordination)
  const derivedExpectations = array((evaluation as any)?.derived_expectations)

  const requirementSignals = [
    requirementData?.system?.deployment_intent ? `Deployment intent: ${requirementData.system.deployment_intent}` : null,
    ...truthyLabels(requirementData?.auth ?? {}).map(item => `Auth: ${item}`),
    ...truthyLabels(requirementData?.permissions ?? {}).map(item => `Permissions: ${item}`),
    ...truthyLabels(requirementData?.audit ?? {}).map(item => `Audit: ${item}`),
    ...truthyLabels(requirementData?.lineage ?? {}).map(item => `Lineage: ${item}`),
    ...truthyLabels(requirementData?.business_constraints ?? {}).map(item => `Constraint: ${item}`),
  ].filter(Boolean) as string[]

  const serviceLines = services.map((service: any) => {
    const responsibilities = stringList(service?.responsibilities)
    const capabilities = stringList(service?.capabilities)
    const owns = stringList(service?.owns_concepts)
    return [
      `### ${service?.name || service?.id || 'Unnamed service'}`,
      `- Service ID: ${service?.id || 'no-id'}`,
      '- Responsibilities:',
      indentedBulletLines(responsibilities.length ? responsibilities : ['none listed']),
      '- Capabilities:',
      indentedBulletLines(capabilities.length ? capabilities : ['none listed']),
      '- Owns Concepts:',
      indentedBulletLines(owns.length ? owns : ['none listed']),
    ].join('\n')
  })

  const conceptLines = concepts.map((concept: any) =>
    `- ${concept?.name || concept?.id || 'Unnamed concept'}: owner=${concept?.owner || 'shared'}, sensitivity=${concept?.sensitivity || 'none'}`
  )

  const coordinationLines = coordination.map((edge: any) =>
    `- ${edge?.from || 'unknown'} -> ${edge?.to || 'unknown'} (${edge?.relationship || 'unspecified'}): ${edge?.description || 'no description'}`
  )

  const evaluationLines = [
    evaluation ? `Result: ${evaluation.result}` : 'No evaluation has been run yet.',
    ...stringList(evaluationData?.why).slice(0, 4).map(item => `Why: ${item}`),
    ...stringList(evaluationData?.glue_you_will_still_write).slice(0, 5).map(item => `Additional implementation work: ${item}`),
    ...stringList(evaluationData?.what_would_improve).slice(0, 5).map(item => `Improve: ${item}`),
  ]
  const conformanceLines = validationConformanceLines(context)

  return [
    `# Engineering Contract: ${project?.name || 'Unnamed Project'}`,
    '',
    `Generated: ${new Date().toLocaleString()}`,
    '',
    '## Traceability',
    bulletLines(traceabilityLines(context, 'Canonical Engineering Contract')),
    '',
    '## Active Context',
    `- Project: ${project?.name || 'Unknown project'}`,
    `- Requirements: ${requirements?.title || 'None selected'}`,
    `- Scenario: ${scenario?.title || 'None selected'}`,
    `- Service Design: ${shape?.title || 'None selected'}`,
    `- Evaluation: ${describeEvaluation(evaluation)}`,
    '',
    '## Requirements Signals',
    bulletLines(requirementSignals.length ? requirementSignals : ['No strong structured requirement signals are available yet.']),
    '',
    '## Scenario Contract',
    bulletLines([
      scenarioData?.narrative ? `Narrative: ${scenarioData.narrative}` : 'Narrative not defined yet.',
      ...stringList(scenarioData?.expected_behavior).map(item => `Expected behavior: ${item}`),
      ...stringList(scenarioData?.expected_anip_support).map(item => `Expected ANIP support: ${item}`),
    ]),
    '',
    '## Service Design',
    serviceLines.length ? serviceLines.join('\n') : '- No services defined yet.',
    '',
    '## Domain Concepts',
    conceptLines.length ? conceptLines.join('\n') : '- No domain concepts defined yet.',
    '',
    '## Coordination',
    coordinationLines.length ? coordinationLines.join('\n') : '- No coordination edges defined yet.',
    '',
    '## Derived Expectations',
    bulletLines(derivedExpectations.length
      ? derivedExpectations.map((item: any) => `${item.surface || 'surface'}: ${item.reason || 'no reason recorded'}`)
      : ['No derived expectations recorded yet.']),
    '',
    '## Latest Evaluation',
    bulletLines(evaluationLines),
    '',
    '## ANIP Conformance Snapshot',
    bulletLines(conformanceLines),
  ].filter(Boolean).join('\n')
}

export function downloadTextDocument(filename: string, content: string): void {
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function unwrap(data: Record<string, any> | undefined, key: string): Record<string, any> {
  return (data?.[key] ?? data ?? {}) as Record<string, any>
}

function stringList(value: any): string[] {
  return Array.isArray(value)
    ? value
        .filter(item => item !== null && item !== undefined)
        .map(item => String(item).trim())
        .filter(Boolean)
    : []
}

function array(value: any): any[] {
  return Array.isArray(value) ? value : []
}

function truthyLabels(record: Record<string, any>): string[] {
  return Object.entries(record)
    .filter(([, value]) => value === true || (typeof value === 'string' && value.trim()))
    .map(([key, value]) =>
      value === true
        ? labelize(key)
        : `${labelize(key)}: ${String(value).trim()}`,
    )
}

function labelize(value: string): string {
  return value
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, match => match.toUpperCase())
}

function bulletLines(items: string[]): string {
  return items.map(item => `- ${item}`).join('\n')
}

function indentedBulletLines(items: string[]): string {
  return items.map(item => `  - ${item}`).join('\n')
}

function describeBusinessShape(shapeData: Record<string, any>): string {
  const services = array(shapeData?.services)
  const concepts = array(shapeData?.domain_concepts)
  const type = shapeData?.type === 'multi_service' ? 'multi-service' : 'single-service'
  if (!services.length) {
    return 'The service design has not been defined yet.'
  }
  return `The current design is a ${type} starting point with ${services.length} service${services.length === 1 ? '' : 's'} and ${concepts.length} named domain concept${concepts.length === 1 ? '' : 's'}.`
}

function namedServices(shapeData: Record<string, any>): string[] {
  return array(shapeData?.services)
    .map((service: any) => String(service?.name || '').trim())
    .filter(Boolean)
}

function traceabilityLines(context: ShareableArtifactContext, role: string): string[] {
  const consumerMode = consumerModeFromLabels(context.project?.labels)
  return [
    `Artifact role: ${role}`,
    `Project: ${context.project?.name || context.project?.id || 'Unknown project'}`,
    `Primary consumer: ${consumerModeLabel(consumerMode)}`,
    `Requirements set: ${context.requirements?.title || context.requirements?.id || 'None selected'}`,
    `Scenario: ${context.scenario?.title || context.scenario?.id || 'None selected'}`,
    `Service design: ${context.shape?.title || context.shape?.id || 'None selected'}`,
    `Evaluation: ${describeEvaluation(context.evaluation)}`,
  ]
}

function describeEvaluation(evaluation: EvaluationRecord | null): string {
  if (!evaluation) return 'Not run yet'
  const result = evaluation.result || evaluation.data?.evaluation?.result || 'not run yet'
  return evaluation.created_at
    ? `${evaluation.id} (${result}, ${evaluation.created_at})`
    : `${evaluation.id} (${result})`
}

function validationConformanceLines(context: ShareableArtifactContext): string[] {
  const observed = (context.evaluation?.input_snapshot?.service_metadata ?? {}) as Record<string, any>
  const shapeData = unwrap(context.shape?.data, 'shape')
  const scenarioData = unwrap(context.scenario?.data, 'scenario')

  if (!Object.keys(observed).length) {
    return ['No observed ANIP service metadata was saved with the current evaluation.']
  }

  const intendedCapabilities = dedupeStrings([
    ...array(shapeData?.services).flatMap((service: any) => stringList(service?.capabilities)),
    ...stringList([scenarioData?.context?.capability]),
  ])
  const observedCapabilities = dedupeStrings(
    array(observed.capabilities)
      .map((item: any) => String(item?.id || '').trim())
      .filter(Boolean),
  )

  const missingCapabilities = intendedCapabilities.filter(item => !observedCapabilities.includes(item))
  const extraCapabilities = observedCapabilities.filter(item => !intendedCapabilities.includes(item))

  return [
    `Observed metadata source: ${observed.source || 'unknown'}`,
    `Observed service: ${observed.service_id || observed.base_url || 'unknown'}`,
    `Protocol declared: ${observed.protocol || 'missing'}`,
    `Manifest signature: ${describePresence(observed.signature_present)}`,
    `JWKS URI: ${describePresence(observed.jwks_uri_present)}`,
    `Missing intended capabilities: ${missingCapabilities.length ? missingCapabilities.join(', ') : 'none'}`,
    `Broader than intended: ${extraCapabilities.length ? extraCapabilities.join(', ') : 'none'}`,
  ]
}

function describePresence(value: unknown): string {
  if (value === true) return 'present'
  if (value === false) return 'missing'
  return 'not inspected'
}

function dedupeStrings(items: string[]): string[] {
  return Array.from(new Set(items.map(item => String(item || '').trim()).filter(Boolean)))
}

function sentenceize(value: string): string {
  const cleaned = String(value || '').replace(/[_-]+/g, ' ').trim()
  if (!cleaned) return ''
  return cleaned.charAt(0).toUpperCase() + cleaned.slice(1)
}

function developerRequirementSignals(record: Record<string, any>): string[] {
  const lines: string[] = []
  if (record.pm_defines_behavior_families_not_every_utterance) {
    lines.push('PM defines behavior families and representative scenarios, not every user utterance')
  }
  if (record.raw_row_level_exports_are_out_of_scope) {
    lines.push('Raw row-level exports are out of scope for the Phase 1 service')
  }
  if (record.followup_execution_must_stop_for_approval) {
    lines.push('Follow-up execution must stop until approval exists')
  }
  if (record.q2_pipeline_review_must_be_reproducible_locally) {
    lines.push('Q2 pipeline review must stay reproducible locally')
  }
  if (record.approval_expected_for_high_risk) {
    lines.push('High-risk work requires approval review')
  }
  if (record.recovery_sensitive) {
    lines.push('Recovery-sensitive behavior must remain reviewable')
  }
  const posture = String(record.blocked_failure_posture || '').trim()
  if (posture === 'human_review_for_unresolved_or_approval_gated_work') {
    lines.push('Escalate to human review only for unresolved or approval-gated work')
  } else if (posture) {
    lines.push(`Blocked failure posture: ${posture}`)
  }
  if (record.clarification_required_for_missing_quarter) {
    lines.push('Quarter must be clarified when missing')
  }
  if (record.clarification_required_for_missing_ranking_basis) {
    lines.push('Ranking basis must be clarified when missing')
  }
  const exportPosture = String(record.phase_1_export_posture || '').trim()
  if (exportPosture === 'deny_raw_row_level_exports') {
    lines.push('Phase 1 export posture: deny raw row-level export requests')
  } else if (exportPosture) {
    lines.push(`Phase 1 export posture: ${exportPosture}`)
  }
  return lines
}

function developerPermissionSignals(permissions: Record<string, any>, constraints: Record<string, any>): string[] {
  const lines: string[] = []
  if (permissions.preflight_discovery) {
    lines.push('Preflight discovery is required')
  }
  if (permissions.grantable_requirements) {
    lines.push('Grantable requirements are visible')
  }
  if (permissions.restricted_vs_denied) {
    if (String(constraints.phase_1_export_posture || '').trim() === 'deny_raw_row_level_exports') {
      lines.push('The permission model distinguishes restricted vs denied; Phase 1 export policy currently uses denied')
    } else {
      lines.push('The permission model distinguishes restricted vs denied outcomes')
    }
  }
  return lines
}

function formatCapabilityContracts(items: any[]): string {
  if (!items.length) return '- No capability contracts are recorded yet.'
  const blocks = items
    .filter(item => item && typeof item === 'object')
    .map((item: any) => [
      `### ${item?.id || 'Unnamed capability'}`,
      `- Purpose: ${item?.purpose || 'not recorded'}`,
      `- Side effect contract: ${item?.side_effect_detail || item?.side_effect_type || 'not recorded'}`,
      `- Minimum scope: ${stringList(item?.minimum_scope).join(', ') || 'not recorded'}`,
      '- Clarification required when:',
      indentedBulletLines(stringList(item?.clarification_required_when).length ? stringList(item?.clarification_required_when) : ['none recorded']),
      '- Denied when:',
      indentedBulletLines(stringList(item?.denied_when).length ? stringList(item?.denied_when) : ['none recorded']),
      '- Approval required when:',
      indentedBulletLines(stringList(item?.approval_required_when).length ? stringList(item?.approval_required_when) : ['none recorded']),
      '- Bounded evidence:',
      indentedBulletLines(stringList(item?.bounded_evidence).length ? stringList(item?.bounded_evidence) : ['none recorded']),
      '- Implementation notes:',
      indentedBulletLines(stringList(item?.implementation_notes).length ? stringList(item?.implementation_notes) : ['none recorded']),
    ].join('\n'))
  return blocks.length ? blocks.join('\n\n') : '- No capability contracts are recorded yet.'
}

function formatCrossServiceContract(contract: Record<string, any>): string {
  if (!contract || typeof contract !== 'object') return '- No explicit cross-service contract is recorded yet.'
  const hasItems = ['handoff', 'followup', 'verification'].some(key => array(contract[key]).length)
  if (!hasItems) return '- No explicit cross-service contract is recorded yet.'

  const labels: Record<string, string> = {
    handoff: 'Handoff',
    followup: 'Follow-up',
    verification: 'Verification',
  }
  const blocks: string[] = []
  for (const key of ['handoff', 'followup', 'verification']) {
    const items = array(contract[key])
    if (!items.length) continue
    const lines: string[] = [`#### ${labels[key]}`]
    for (const item of items) {
      if (!item || typeof item !== 'object') continue
      const target = (item.target ?? {}) as Record<string, any>
      lines.push(`- Target service: ${target.service || 'not recorded'}`)
      lines.push(`- Target capability: ${target.capability || 'not recorded'}`)
      lines.push(`- Continuity: ${item.continuity || 'not recorded'}`)
      lines.push(`- Completion mode: ${item.completion_mode || 'not recorded'}`)
      lines.push(`- Required for task completion: ${yesNo(item.required_for_task_completion)}`)
      const carry = stringList(item.carry_fields)
      if (carry.length) lines.push('- Carry fields:', indentedBulletLines(carry))
      const rationale = String(item.rationale || '').trim()
      if (rationale) lines.push(`- Rationale: ${rationale}`)
    }
    blocks.push(lines.join('\n'))
  }
  return blocks.length ? blocks.join('\n\n') : '- No explicit cross-service contract is recorded yet.'
}

function formatActorPolicyModel(model: Record<string, any>): string {
  if (!model || typeof model !== 'object') return '- No explicit actor, authority, and audit policy is recorded yet.'

  const identitySource = String(model.identity_source || '').trim()
  const policyAxes = stringList(model.policy_axes)
  const visibilityRules = array(model.visibility_rules)
  const approvalRules = array(model.approval_rules)
  const auditExpectations = stringList(model.audit_expectations)
  const approvalSurface = (model.approval_surface ?? {}) as Record<string, any>
  const blocks: string[] = []

  const overviewLines: string[] = []
  if (identitySource) overviewLines.push(`- Identity source: ${identitySource}`)
  if (policyAxes.length) overviewLines.push('- Policy axes:', indentedBulletLines(policyAxes))
  if (overviewLines.length) blocks.push(['### Actor Model', ...overviewLines].join('\n'))

  if (visibilityRules.length) {
    const lines: string[] = ['### Visibility And Restriction Rules']
    for (const rule of visibilityRules) {
      if (!rule || typeof rule !== 'object') continue
      lines.push(`- Applies when: ${rule.when || 'not recorded'}`)
      lines.push(`- Governed outcome: ${rule.outcome || 'not recorded'}`)
      const rationale = String(rule.rationale || '').trim()
      if (rationale) lines.push(`- Rationale: ${rationale}`)
    }
    blocks.push(lines.join('\n'))
  }

  if (approvalRules.length) {
    const lines: string[] = ['### Approval Authority Rules']
    for (const rule of approvalRules) {
      if (!rule || typeof rule !== 'object') continue
      lines.push(`- Action: ${rule.action || 'not recorded'}`)
      lines.push(`- Requester posture: ${rule.requester_posture || 'not recorded'}`)
      lines.push(`- Approver requirement: ${rule.approver_requirement || 'not recorded'}`)
      const notes = stringList(rule.notes)
      if (notes.length) lines.push('- Notes:', indentedBulletLines(notes))
    }
    blocks.push(lines.join('\n'))
  }

  if (auditExpectations.length) {
    blocks.push(['### Audit Review Expectations', bulletLines(auditExpectations)].join('\n'))
  }

  if (Object.keys(approvalSurface).length && (approvalSurface.list_path || approvalSurface.approve_path_template)) {
    const lines: string[] = ['### Linked Approval Review Surface']
    if (approvalSurface.list_path) lines.push(`- List path: ${approvalSurface.list_path}`)
    if (approvalSurface.approve_path_template) lines.push(`- Approve path template: ${approvalSurface.approve_path_template}`)
    const notes = stringList(approvalSurface.notes)
    if (notes.length) lines.push('- Notes:', indentedBulletLines(notes))
    blocks.push(lines.join('\n'))
  }

  return blocks.length ? blocks.join('\n\n') : '- No explicit actor, authority, and audit policy is recorded yet.'
}

function pmSafetyPostureLines(requirementData: Record<string, any>): string[] {
  const constraints = (requirementData?.business_constraints ?? {}) as Record<string, any>
  const lines: string[] = []
  if (constraints.clarification_required_for_missing_quarter || constraints.clarification_required_for_missing_ranking_basis) {
    lines.push('The system must not guess missing critical parameters such as quarter or ranking basis.')
  }
  if (constraints.phase_1_export_posture === 'deny_raw_row_level_exports' || constraints.raw_row_level_exports_are_out_of_scope) {
    lines.push('For Phase 1, the system must deny raw row-level exports instead of improvising a narrower interpretation.')
  }
  if (constraints.followup_execution_must_stop_for_approval || constraints.approval_expected_for_high_risk) {
    lines.push('The system must not execute downstream mutations without approval.')
  }
  if (constraints.blocked_failure_posture) {
    lines.push('Unsafe, unresolved, or approval-gated work should stop cleanly and surface for human review when required.')
  }
  return lines
}

function pmValidationStatusLine(context: ShareableArtifactContext): string {
  const evaluation = context.evaluation
  if (!evaluation) return 'Status: Not run yet'
  const result = evaluation.result || evaluation.data?.evaluation?.result || 'not run yet'
  const observed = evaluation.input_snapshot?.service_metadata ?? null
  if (observed && Object.keys(observed).length > 0) {
    return `Status: ${result}`
  }
  return `Status: ${result}, but no runtime metadata captured yet`
}

function developerValidationStatusLine(context: ShareableArtifactContext): string {
  const evaluation = context.evaluation
  if (!evaluation) return 'Status: Not run yet'
  const result = evaluation.result || evaluation.data?.evaluation?.result || 'not run yet'
  const conformanceStatus = String(evaluation.data?.evaluation?.conformance_status || '').trim().toLowerCase()
  const observed = evaluation.input_snapshot?.service_metadata ?? null
  if (observed && Object.keys(observed).length > 0) {
    if (conformanceStatus === 'partial') {
      return `Status: ${result}; runtime metadata captured with open conformance gaps.`
    }
    return `Status: ${result}; runtime metadata captured and compared against the developer contract.`
  }
  return `Status: ${result}; runtime metadata has not been captured yet for this developer validation.`
}

function yesNo(value: unknown): string {
  return value ? 'yes' : 'no'
}
