import { readFile, readdir } from 'node:fs/promises'
import { basename, resolve } from 'node:path'
import { webcrypto } from 'node:crypto'

import {
  createPmArtifact,
  createProject,
  createProjectDocument,
  createWorkspace,
  getProject,
  listPmArtifacts,
  listProjectDocuments,
  listRequirements,
  listScenarios,
  listShapes,
  updatePmArtifact,
  updateShape,
} from '../src/design/project-api'
import type {
  ArtifactRecord,
  DeveloperDefinitionData,
  ProjectDetail,
  RequirementsRecord,
  ShapeRecord,
  TraceabilityCoverageItem,
  TraceabilityRecordData,
} from '../src/design/project-types'
import {
  draftProductDesignBundle,
  redraftProductDesignSection,
  saveAcceptedProductDesignSection,
  type ProductDesignDraftSection,
} from '../src/design/product-design-draft-bundle'
import {
  buildDeveloperBaselineSourceText,
  draftDeveloperDesignBundle,
  redraftDeveloperDesignSection,
  saveAcceptedDeveloperDesignSection,
  type DeveloperDesignDraftSection,
} from '../src/design/developer-design-draft-bundle'
import {
  buildProductDesignRevision,
  productDesignRevisionArtifactId,
} from '../src/design/product-design'
import {
  buildDeveloperBaseline,
  developerBaselineArtifactId,
  summarizeCoverage,
  traceabilityArtifactId,
  buildTraceabilityRecord,
} from '../src/design/traceability'
import {
  analyzeAgentConsumptionReadiness,
} from '../src/design/agent-consumption-readiness'
import {
  buildDeveloperDefinitionData,
  developerDefinitionArtifactId,
  developerDefinitionTargetStatus,
  stableStringify,
  validateDeveloperDefinitionRequiredFields,
} from '../src/design/developer-definition'
import { buildHighRiskConfirmationReport } from '../src/design/high-risk-confirmations'

const repoRoot = resolve(new URL('../..', import.meta.url).pathname)
const apiBase = process.env.STUDIO_API_BASE || 'http://127.0.0.1:8100'
const nowStamp = new Date().toISOString().replace(/[-:.TZ]/g, '').slice(0, 14)
const workspaceId = process.env.PAGE_ASSISTANT_WORKSPACE_ID || `ws-gtm-page-assistant-${nowStamp}`
const projectId = process.env.PAGE_ASSISTANT_PROJECT_ID || `gtm-page-assistant-${nowStamp}`
const customCodeBundlePath = process.env.PAGE_ASSISTANT_CUSTOM_CODE_BUNDLE
  || 'examples/showcase/gtm/custom-code-bundles/gtm_pipeline_python'

const SOURCE_DOCS = [
  'docs/examples/gtm-showcase/gtm-revenue-operations-business-spec.md',
  'docs/examples/gtm-showcase/pipeline-forecast-business-spec.md',
  'docs/examples/gtm-showcase/stage-bottleneck-business-spec.md',
  'docs/examples/gtm-showcase/sales-team-performance-business-spec.md',
  'docs/examples/gtm-showcase/product-pipeline-business-spec.md',
  'docs/examples/gtm-showcase/prepare-reassignment-business-spec.md',
  'docs/examples/gtm-showcase/enrichment-business-spec.md',
  'docs/examples/gtm-showcase/prioritization-business-spec.md',
  'docs/examples/gtm-showcase/outreach-business-spec.md',
]

interface DeclaredBundleCapability {
  capabilityId: string
  relativePath: string
  description: string
  implementationCalls: string[]
  inputs: DeclaredBundleInput[]
}

interface DeclaredBundleInput {
  name: string
  type: string
  required: boolean
  defaultValue: string
  allowedValues: string[]
  description: string
  semanticType: string
  entityReference: boolean
  catalogRef: string
  resolution: Record<string, string>
}

interface ProjectState {
  project: ProjectDetail
  pmArtifacts: ArtifactRecord[]
  documents: Awaited<ReturnType<typeof listProjectDocuments>>
  requirements: RequirementsRecord[]
  scenarios: ArtifactRecord[]
  shapes: ShapeRecord[]
}

if (!globalThis.crypto) {
  Object.defineProperty(globalThis, 'crypto', { value: webcrypto })
}

const nativeFetch = globalThis.fetch.bind(globalThis)
globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) => {
  if (typeof input === 'string' && input.startsWith('/')) {
    return nativeFetch(`${apiBase}${input}`, init)
  }
  return nativeFetch(input, init)
}) as typeof globalThis.fetch

function log(message: string) {
  process.stdout.write(`[page-assistant-flow] ${message}\n`)
}

async function assertAssistantReady() {
  const response = await fetch('/api/runtime-status')
  if (!response.ok) {
    throw new Error(`Studio runtime status is unavailable: HTTP ${response.status}`)
  }
  const runtime = await response.json() as {
    llm_ready?: boolean
    assistant_provider?: string | null
    assistant_model?: string | null
    api_key_configured?: boolean
  }
  if (!runtime.llm_ready) {
    throw new Error(`Page-by-page assistant requires LLM-ready Studio runtime. provider=${runtime.assistant_provider ?? 'not set'} model=${runtime.assistant_model ?? 'not set'} api_key=${runtime.api_key_configured ? 'configured' : 'missing'}`)
  }
  log(`Assistant ready: provider=${runtime.assistant_provider ?? 'unknown'} model=${runtime.assistant_model ?? 'unknown'}`)
}

async function loadState(projectRef: string): Promise<ProjectState> {
  const [project, pmArtifacts, documents, requirements, scenarios, shapes] = await Promise.all([
    getProject(projectRef),
    listPmArtifacts(projectRef),
    listProjectDocuments(projectRef),
    listRequirements(projectRef),
    listScenarios(projectRef),
    listShapes(projectRef),
  ])
  return { project, pmArtifacts, documents, requirements, scenarios, shapes }
}

async function upsertArtifact(projectRef: string, payload: { id: string; title: string; data: Record<string, any> }) {
  const existing = (await listPmArtifacts(projectRef)).find((artifact) => artifact.id === payload.id)
  if (existing) {
    return updatePmArtifact(projectRef, payload.id, {
      title: payload.title,
      status: 'draft',
      data: payload.data,
    })
  }
  return createPmArtifact(projectRef, payload)
}

async function declaredCustomBundleCapabilities(): Promise<DeclaredBundleCapability[]> {
  const bundleRoot = resolve(repoRoot, customCodeBundlePath)
  const files: string[] = []
  async function walk(directory: string) {
    let entries: Awaited<ReturnType<typeof readdir>>
    try {
      entries = await readdir(directory, { withFileTypes: true })
    } catch {
      return
    }
    for (const entry of entries) {
      const absolute = resolve(directory, entry.name)
      if (entry.isDirectory()) {
        await walk(absolute)
      } else if (entry.isFile() && entry.name.endsWith('.py')) {
        files.push(absolute)
      }
    }
  }
  await walk(bundleRoot)
  const results: DeclaredBundleCapability[] = []
  for (const file of files) {
    const content = await readFile(file, 'utf8')
    const declarationStarts = [...content.matchAll(/CapabilityDeclaration\s*\(/gi)].map((match) => match.index ?? 0)
    for (let index = 0; index < declarationStarts.length; index += 1) {
      const start = declarationStarts[index]
      const end = declarationStarts[index + 1] ?? content.length
      const block = content.slice(start, end)
      const match = block.match(/name\s*=\s*["']([a-z][a-z0-9]*(?:[._][a-z0-9]+)+)["']/i)
      if (!match) continue
      results.push({
        capabilityId: match[1],
        relativePath: file.replace(`${repoRoot}/`, ''),
        description: matchStringArg(block, 'description'),
        implementationCalls: implementationCallHints(content, match[1]),
        inputs: parseDeclaredBundleInputs(block),
      })
    }
  }
  const byId = new Map<string, DeclaredBundleCapability>()
  for (const item of results) byId.set(item.capabilityId, item)
  return [...byId.values()].sort((a, b) => a.capabilityId.localeCompare(b.capabilityId))
}

function parseDeclaredBundleInputs(block: string): DeclaredBundleInput[] {
  const inputBlocks = [...block.matchAll(/CapabilityInput\s*\(([\s\S]*?)\)/gi)]
  return inputBlocks.flatMap((match) => {
    const inputBlock = match[1] ?? ''
    const name = matchStringArg(inputBlock, 'name')
    if (!name) return []
    return [{
      name,
      type: matchStringArg(inputBlock, 'type') || 'string',
      required: matchBooleanArg(inputBlock, 'required'),
      defaultValue: matchStringArg(inputBlock, 'default'),
      allowedValues: matchStringListArg(inputBlock, 'allowed_values'),
      description: matchStringArg(inputBlock, 'description'),
      semanticType: matchStringArg(inputBlock, 'semantic_type'),
      entityReference: matchBooleanArg(inputBlock, 'entity_reference'),
      catalogRef: matchStringArg(inputBlock, 'catalog_ref'),
      resolution: matchStringDictArg(inputBlock, 'resolution'),
    }]
  })
}

function matchStringArg(block: string, key: string): string {
  const match = block.match(new RegExp(`${key}\\s*=\\s*["']([^"']*)["']`, 'i'))
  return match?.[1]?.trim() ?? ''
}

function matchBooleanArg(block: string, key: string): boolean {
  const match = block.match(new RegExp(`${key}\\s*=\\s*(True|False|true|false)`, 'i'))
  return (match?.[1] ?? '').toLowerCase() === 'true'
}

function matchStringListArg(block: string, key: string): string[] {
  const match = block.match(new RegExp(`${key}\\s*=\\s*\\[([^\\]]*)\\]`, 'i'))
  if (!match) return []
  return [...match[1].matchAll(/["']([^"']+)["']/g)].map((item) => item[1].trim()).filter(Boolean)
}

function matchStringDictArg(block: string, key: string): Record<string, string> {
  const match = block.match(new RegExp(`${key}\\s*=\\s*\\{([\\s\\S]*?)\\}`, 'i'))
  if (!match) return {}
  return Object.fromEntries(
    [...match[1].matchAll(/["']?([a-z_]+)["']?\s*(?::|=)\s*["']([^"']+)["']/gi)]
      .map((item) => [item[1].trim(), item[2].trim()])
      .filter(([dictKey, value]) => dictKey && value),
  )
}

function implementationCallHints(content: string, capabilityId: string): string[] {
  const handlerName = `_handle_${capabilityId.replace(/[^a-z0-9]+/gi, '_')}`
  const handlerStart = content.search(new RegExp(`(?:async\\s+)?def\\s+${handlerName}\\s*\\(`, 'i'))
  if (handlerStart < 0) return []
  const handlerRest = content.slice(handlerStart)
  const nextTopLevel = handlerRest.slice(1).search(/\n(?=\S)/)
  const handlerBlock = nextTopLevel >= 0 ? handlerRest.slice(0, nextTopLevel + 1) : handlerRest
  const ignored = new Set(['ANIPError', 'bool', 'dict', 'int', 'len', 'list', 'print', 'range', 'str'])
  const calls = [...handlerBlock.matchAll(/\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(/g)]
    .map((match) => match[1])
    .filter((name) => !name.startsWith('_') && !ignored.has(name))
  return Array.from(new Set(calls)).slice(0, 12)
}

function implementationSurfaceDocument(capabilities: DeclaredBundleCapability[]): string {
  return [
    `# Source: ${customCodeBundlePath} implementation surface`,
    '',
    'This custom code bundle declares implementation capabilities. If this bundle is used for generation, each declared capability must either be present in the contract or intentionally removed from the bundle before generation.',
    '',
    ...capabilities.flatMap((capability) => [
      `- \`${capability.capabilityId}\` from \`${capability.relativePath}\``,
      capability.description ? `  - declared behavior: ${capability.description}` : '',
      capability.implementationCalls.length ? `  - implementation calls: ${capability.implementationCalls.join(', ')}` : '',
      ...(capability.inputs.length
        ? capability.inputs.map((input) => {
            const details = [
              `type=${input.type}`,
              `required=${input.required ? 'true' : 'false'}`,
              input.defaultValue ? `default=${input.defaultValue}` : '',
              input.allowedValues.length ? `allowed=${input.allowedValues.join('|')}` : '',
              input.semanticType ? `semantic_type=${input.semanticType}` : '',
              input.entityReference ? 'entity_reference=true' : '',
              input.catalogRef ? `catalog_ref=${input.catalogRef}` : '',
              Object.keys(input.resolution).length ? `resolution=${JSON.stringify(input.resolution)}` : '',
              input.description ? `description=${input.description}` : '',
            ].filter(Boolean).join(', ')
            return `  - input \`${input.name}\`: ${details}`
          })
        : ['  - inputs: not declared in bundle surface']),
    ].filter(Boolean)),
  ].join('\n')
}

async function sourceTextFromDocs(): Promise<string> {
  const chunks: string[] = []
  for (const relativePath of SOURCE_DOCS) {
    const absolutePath = resolve(repoRoot, relativePath)
    const content = await readFile(absolutePath, 'utf8')
    chunks.push(`# Source: ${relativePath}\n\n${content.trim()}`)
  }
  const bundleCapabilities = await declaredCustomBundleCapabilities()
  if (bundleCapabilities.length > 0) {
    chunks.push(implementationSurfaceDocument(bundleCapabilities))
  }
  return chunks.join('\n\n---\n\n')
}

async function seedSourceDocuments(projectRef: string) {
  for (const relativePath of SOURCE_DOCS) {
    const absolutePath = resolve(repoRoot, relativePath)
    const content = await readFile(absolutePath, 'utf8')
    await createProjectDocument(projectRef, {
      id: `${projectRef}-doc-${basename(relativePath).replace(/[^a-z0-9]+/gi, '-').replace(/^-+|-+$/g, '').toLowerCase()}`,
      title: basename(relativePath),
      kind: 'source_document',
      filename: basename(relativePath),
      media_type: 'text/markdown',
      source_path: relativePath,
      content_base64: Buffer.from(content, 'utf8').toString('base64'),
    })
  }
  const bundleCapabilities = await declaredCustomBundleCapabilities()
  if (bundleCapabilities.length > 0) {
    const content = implementationSurfaceDocument(bundleCapabilities)
    await createProjectDocument(projectRef, {
      id: `${projectRef}-doc-custom-code-bundle-surface`,
      title: 'Custom Code Bundle Capability Surface',
      kind: 'source_document',
      filename: 'custom-code-bundle-capability-surface.md',
      media_type: 'text/markdown',
      source_path: customCodeBundlePath,
      content_base64: Buffer.from(content, 'utf8').toString('base64'),
    })
  }
}

function tokenSet(value: string): Set<string> {
  return new Set(String(value ?? '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .split(/\s+/)
    .map((token) => token.trim())
    .filter((token) => token.length > 2 && !['app', 'src', 'service', 'services', 'capability'].includes(token)))
}

function tokenOverlapScore(source: string, target: string): number {
  const sourceTokens = tokenSet(source)
  const targetTokens = tokenSet(target)
  let score = 0
  for (const token of sourceTokens) {
    if (targetTokens.has(token)) score += 1
  }
  return score
}

function serviceIdFromBundlePath(relativePath: string, services: Array<Record<string, any>>): string {
  const serviceDir = relativePath.match(/\/services\/([^/]+)\//)?.[1]
  if (!serviceDir) return ''
  const normalized = serviceDir.replace(/_/g, '-')
  const candidates = new Set([
    normalized,
    normalized.replace(/-service$/, ''),
    normalized.endsWith('-service') ? normalized : `${normalized}-service`,
  ])
  for (const service of services) {
    const serviceId = String(service.id ?? service.name ?? '').trim()
    if (candidates.has(serviceId)) return serviceId
  }
  return ''
}

async function alignShapeWithCustomBundleCapabilities(projectRef: string): Promise<void> {
  const declared = await declaredCustomBundleCapabilities()
  if (declared.length === 0) return
  const shapes = await listShapes(projectRef)
  const shape = shapes[0]
  const data = shape?.data as Record<string, any> | undefined
  const shapeData = data?.shape && typeof data.shape === 'object' ? data.shape as Record<string, any> : data
  const services = Array.isArray(shapeData?.services) ? shapeData.services as Array<Record<string, any>> : []
  if (!shape || !shapeData || services.length === 0) return
  let changed = false
  const contracts = Array.isArray(shapeData.capability_contracts)
    ? [...shapeData.capability_contracts] as Array<Record<string, any>>
    : []
  for (const capability of declared) {
    const sourceInputs = capability.inputs.map((input) => ({
      input_name: input.name,
      input_type: input.type || 'string',
      required: input.required,
      summary: input.description,
      default_value: input.defaultValue,
      allowed_values: input.allowedValues,
      semantic_type: input.semanticType,
      entity_reference: input.entityReference,
      catalog_ref: input.catalogRef,
      resolution: Object.keys(input.resolution).length ? input.resolution : undefined,
    }))
    const existingContract = contracts.find((contract) => String(contract.id ?? contract.capability_id ?? '').trim() === capability.capabilityId)
    if (!existingContract) {
      contracts.push({
        id: capability.capabilityId,
        capability_id: capability.capabilityId,
        purpose: capability.description,
        summary: capability.description,
        source_kind: 'custom_code_bundle',
        source_path: capability.relativePath,
        implementation_notes: capability.implementationCalls.length
          ? [`Implementation call hints: ${capability.implementationCalls.join(', ')}`]
          : [],
        inputs: sourceInputs,
      })
      changed = true
    } else {
      const existingInputs = Array.isArray(existingContract.inputs)
        ? existingContract.inputs as Array<Record<string, any>>
        : []
      const byInputName = new Map(existingInputs.map((input) => [String(input.input_name ?? input.name ?? '').trim(), input]))
      const mergedInputs = sourceInputs.map((sourceInput) => {
        const prior = byInputName.get(sourceInput.input_name) ?? {}
        return {
          ...prior,
          ...sourceInput,
        }
      })
      const priorInputSignature = stableStringify(existingInputs)
      const nextInputSignature = stableStringify(mergedInputs)
      if (priorInputSignature !== nextInputSignature) {
        existingContract.inputs = mergedInputs
        changed = true
      }
    }
    const preferredServiceId = serviceIdFromBundlePath(capability.relativePath, services)
    if (preferredServiceId) {
      for (const service of services) {
        const capabilities = Array.isArray(service.capabilities) ? service.capabilities : []
        const hasCapability = capabilities.includes(capability.capabilityId)
        if (String(service.id ?? service.name ?? '').trim() === preferredServiceId) {
          if (!hasCapability) {
            service.capabilities = Array.from(new Set([...capabilities, capability.capabilityId]))
            changed = true
          }
        } else if (hasCapability) {
          service.capabilities = capabilities.filter((item) => item !== capability.capabilityId)
          changed = true
        }
      }
      continue
    }
    if (services.some((service) => Array.isArray(service.capabilities) && service.capabilities.includes(capability.capabilityId))) continue
    const scored = services
      .map((service) => {
        const serviceText = [
          service.id,
          service.name,
          service.role,
          ...(Array.isArray(service.responsibilities) ? service.responsibilities : []),
          capability.relativePath,
        ].join(' ')
        return { service, score: tokenOverlapScore(capability.capabilityId, serviceText) }
      })
      .filter((entry) => entry.score > 0)
      .sort((a, b) => b.score - a.score)
    if (scored.length === 0) continue
    const target = scored[0].service
    target.capabilities = Array.from(new Set([...(Array.isArray(target.capabilities) ? target.capabilities : []), capability.capabilityId]))
    changed = true
  }
  if (!changed) return
  shapeData.capability_contracts = contracts
  shapeData.notes = Array.from(new Set([
    ...(Array.isArray(shapeData.notes) ? shapeData.notes : []),
    'Studio aligned custom code bundle capability declarations into the service shape so generation can validate bundle/contract parity before codegen.',
  ]))
  await updateShape(projectRef, shape.id, {
    data: data?.shape ? { ...data, shape: shapeData } : shapeData,
  })
}

function clarificationAnswer(sectionTitle: string): string {
  return [
    `${sectionTitle}: use the uploaded GTM source documents as authoritative.`,
    'Preserve source-declared service IDs, capability IDs, approval boundaries, and non-goals when present.',
    'If a target group, quarter, actor scope, send/export/mutate behavior, or downstream action is ambiguous, encode clarification or explicit app-owned glue rather than guessing.',
  ].join(' ')
}

async function resolveProductClarification(projectRef: string, section: ProductDesignDraftSection, sourceText: string): Promise<ProductDesignDraftSection> {
  if (section.status !== 'needs_clarification' || !section.envelope || section.envelope.proposal.proposal_kind !== 'clarification_questions') {
    return section
  }
  const answers = Object.fromEntries(section.envelope.proposal.questions.map((question) => [question.question_id, clarificationAnswer(section.title)]))
  return redraftProductDesignSection({
    projectId: projectRef,
    section: { ...section, clarificationAnswers: answers },
    sourceText: `${sourceText}\n\n# Page assistant clarification answers for ${section.title}\n\n${Object.entries(answers).map(([id, answer]) => `- ${id}: ${answer}`).join('\n')}`,
    useDeterministic: false,
  })
}

async function resolveDeveloperClarification(
  projectRef: string,
  section: DeveloperDesignDraftSection,
  baselineText: string,
  requirementsId: string | null,
  shapeId: string | null,
  serviceCount: number,
): Promise<DeveloperDesignDraftSection> {
  if (section.status !== 'needs_clarification' || !section.envelope || section.envelope.proposal.proposal_kind !== 'clarification_questions') {
    return section
  }
  const answers = Object.fromEntries(section.envelope.proposal.questions.map((question) => [question.question_id, clarificationAnswer(section.title)]))
  return redraftDeveloperDesignSection({
    projectId: projectRef,
    section: { ...section, clarificationAnswers: answers },
    baselineText: `${baselineText}\n\n# Page assistant clarification answers for ${section.title}\n\n${Object.entries(answers).map(([id, answer]) => `- ${id}: ${answer}`).join('\n')}`,
    sourceRequirementsId: requirementsId,
    sourceShapeId: shapeId,
    useDeterministic: false,
    serviceTopologyPreference: {
      granularity: 'source_defined',
      target_service_count: serviceCount,
      preserve_source_services: true,
      rationale: 'Page-by-page validation should preserve source-declared service and capability identities so later package exports remain compatible with source-owned implementation bundles.',
    },
  })
}

function serviceCountFromShape(shape: ShapeRecord | null): number {
  const data = shape?.data as Record<string, any> | undefined
  const services = data?.shape?.services ?? data?.services
  return Array.isArray(services) ? services.length : 0
}

function applyAutomaticCoverageStatuses(traceability: TraceabilityRecordData, definition: DeveloperDefinitionData): TraceabilityRecordData {
  const coverage = traceability.coverage.map((item): TraceabilityCoverageItem => {
    if (item.mapping_mode !== 'automatic') return item
    return {
      ...item,
      status: item.mapping_target_key
        ? developerDefinitionTargetStatus(item.mapping_target_key, { developerDefinition: definition })
        : 'not_addressed',
    }
  })
  return { ...traceability, coverage }
}

async function saveReviewArtifacts(state: ProjectState) {
  const baselineArtifact = state.pmArtifacts.find((artifact) => artifact.id === developerBaselineArtifactId(state.project.id))
  const baseline = (baselineArtifact?.data ?? null) as any
  const requirements = state.requirements[0] ?? null
  const shape = state.shapes[0] ?? null
  const definition = buildDeveloperDefinitionData({
    project: state.project,
    baseline,
    requirements,
    scenarios: state.scenarios,
    shape,
    pmArtifacts: state.pmArtifacts,
  })
  const validationIssues = validateDeveloperDefinitionRequiredFields(definition)
  const rawTraceability = buildTraceabilityRecord({
    pmArtifacts: state.pmArtifacts,
    requirements,
    scenarios: state.scenarios,
    shape,
    baselineLockedAt: baseline?.locked_at ?? null,
    existing: null,
  })
  const traceability = applyAutomaticCoverageStatuses(rawTraceability, definition)
  const readiness = analyzeAgentConsumptionReadiness(definition)
  const highRisk = buildHighRiskConfirmationReport({
    project: state.project,
    pmArtifacts: state.pmArtifacts,
    documents: state.documents,
    requirements: state.requirements,
    scenarios: state.scenarios,
    shapes: state.shapes,
  })
  await upsertArtifact(state.project.id, {
    id: traceabilityArtifactId(state.project.id),
    title: 'Design Traceability',
    data: {
      ...traceability,
      developer_status: 'in_review',
      developer_note: 'Page-by-page assistant drafted PM and Developer Design. Review decisions remain explicit and are not auto-confirmed.',
      developer_marked_at: new Date().toISOString(),
      agent_consumption_readiness: JSON.parse(JSON.stringify(readiness)),
      high_risk_confirmations: highRisk,
    } as Record<string, any>,
  })
  await upsertArtifact(state.project.id, {
    id: developerDefinitionArtifactId(state.project.id),
    title: 'Developer Definition',
    data: definition as Record<string, any>,
  })
  return {
    definition,
    validationIssues,
    readiness,
    highRisk,
    coverage: summarizeCoverage(traceability.coverage),
  }
}

async function main() {
  await assertAssistantReady()
  log(`Creating workspace ${workspaceId}`)
  await createWorkspace({
    id: workspaceId,
    name: `GTM Page Assistant ${nowStamp}`,
    summary: 'Fresh page-by-page assistant validation workspace seeded from GTM source documents.',
  })
  log(`Creating project ${projectId}`)
  await createProject({
    id: projectId,
    workspace_id: workspaceId,
    name: `GTM Page Assistant ${nowStamp}`,
    summary: 'Fresh page-by-page GTM validation project.',
    domain: 'gtm',
    labels: ['gtm-showcase', 'page-assistant-validation'],
    project_type: 'standard',
  })

  log('Uploading source documents')
  await seedSourceDocuments(projectId)
  const sourceText = await sourceTextFromDocs()

  log('Drafting Product Design one assistant section at a time')
  const productBundle = await draftProductDesignBundle({
    projectId,
    projectName: `GTM Page Assistant ${nowStamp}`,
    sourceText,
    useDeterministic: false,
    onProgress: (message) => log(`PM: ${message}`),
  })
  let state = await loadState(projectId)
  for (const originalSection of productBundle.sections) {
    let section = await resolveProductClarification(projectId, originalSection, sourceText)
    section = await resolveProductClarification(projectId, section, sourceText)
    if (section.status === 'failed') throw new Error(`PM section ${section.title} failed: ${section.error}`)
    if (section.status === 'needs_clarification') throw new Error(`PM section ${section.title} still needs clarification`)
    log(`Saving PM page: ${section.title}`)
    await saveAcceptedProductDesignSection({
      project: state.project,
      section,
      pmArtifacts: state.pmArtifacts,
      requirements: state.requirements,
    })
    state = await loadState(projectId)
  }

  const productRevision = buildProductDesignRevision({
    projectId,
    pmArtifacts: state.pmArtifacts,
  })
  await upsertArtifact(projectId, {
    id: productDesignRevisionArtifactId(projectId, productRevision.revision_number),
    title: `Product Design Revision ${productRevision.revision_number}`,
    data: productRevision as Record<string, any>,
  })
  await alignShapeWithCustomBundleCapabilities(projectId)
  state = await loadState(projectId)

  const requirements = state.requirements[0] ?? null
  const shape = state.shapes[0] ?? null
  const baseline = buildDeveloperBaseline({
    requirements,
    scenarios: state.scenarios,
    primaryScenarioId: state.scenarios[0]?.id,
    shape,
    pmArtifacts: state.pmArtifacts,
    productRevision,
  })
  await upsertArtifact(projectId, {
    id: developerBaselineArtifactId(projectId),
    title: 'Developer Baseline',
    data: baseline as Record<string, any>,
  })
  state = await loadState(projectId)

  const serviceCount = serviceCountFromShape(shape)
  const baselineText = buildDeveloperBaselineSourceText({
    projectName: state.project.name,
    requirements,
    scenarios: state.scenarios,
    shape,
    baselineLockedAt: baseline.locked_at,
  })
  log('Drafting Developer Design one assistant section at a time')
  const developerBundle = await draftDeveloperDesignBundle({
    projectId,
    projectName: state.project.name,
    baselineText,
    sourceRequirementsId: requirements?.id,
    sourceShapeId: shape?.id,
    useDeterministic: false,
    serviceTopologyPreference: {
      granularity: 'source_defined',
      target_service_count: serviceCount,
      preserve_source_services: true,
      rationale: 'Page-by-page validation should preserve source-declared service and capability identities so later package exports remain compatible with source-owned implementation bundles.',
    },
    onProgress: (message) => log(`Dev: ${message}`),
  })
  for (const originalSection of developerBundle.sections) {
    let section = await resolveDeveloperClarification(projectId, originalSection, baselineText, requirements?.id ?? null, shape?.id ?? null, serviceCount)
    section = await resolveDeveloperClarification(projectId, section, baselineText, requirements?.id ?? null, shape?.id ?? null, serviceCount)
    if (section.status === 'failed') throw new Error(`Developer section ${section.title} failed: ${section.error}`)
    if (section.status === 'needs_clarification') throw new Error(`Developer section ${section.title} still needs clarification`)
    log(`Saving Developer page: ${section.title}`)
    await saveAcceptedDeveloperDesignSection({
      projectId,
      section,
      notes: 'Page-by-page assistant proposal accepted for review.',
    })
  }

  state = await loadState(projectId)
  const review = await saveReviewArtifacts(state)
  log(`Coverage: addressed=${review.coverage.addressed} missing=${review.coverage.missing} deferred=${review.coverage.deferred}`)
  log(`Readiness: ${review.readiness.status} ${review.readiness.score}/100 blockers=${review.readiness.summary.blockers} warnings=${review.readiness.summary.warnings}`)
  log(`High-risk confirmations unresolved: ${review.highRisk.summary.unresolved}`)
  log(`Definition validation issues: ${review.validationIssues.length}`)
  log(`Capabilities: ${review.definition.capability_formalizations.length}`)
  log(`Project URL: http://localhost:5173/studio/design/projects/${projectId}/pm/assistant`)
}

main().catch((err) => {
  process.stderr.write(`[page-assistant-flow] failed: ${err instanceof Error ? err.stack ?? err.message : String(err)}\n`)
  process.exitCode = 1
})
