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
  requirements: RequirementsRecord | null
  scenario: ArtifactRecord | null
  shape: ShapeRecord | null
  evaluation: EvaluationRecord | null
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
    ...stringList(evaluationData?.glue_you_will_still_write).slice(0, 5).map(item => `Gap: ${item}`),
    ...stringList(evaluationData?.what_would_improve).slice(0, 5).map(item => `Improve: ${item}`),
  ]

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
  return Array.isArray(value) ? value.map(item => String(item).trim()).filter(Boolean) : []
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
  if (!evaluation) return 'None selected'
  return evaluation.created_at
    ? `${evaluation.id} (${evaluation.result}, ${evaluation.created_at})`
    : `${evaluation.id} (${evaluation.result})`
}
