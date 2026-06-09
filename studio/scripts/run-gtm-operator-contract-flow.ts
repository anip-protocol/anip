import { readFile, readdir } from 'node:fs/promises'
import { basename, resolve } from 'node:path'
import { createHash, webcrypto } from 'node:crypto'

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
  DeveloperCompiledContractIdentity,
  DeveloperDefinitionData,
  DeveloperDefinitionRevisionData,
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
  traceabilityArtifactId,
  buildTraceabilityRecord,
} from '../src/design/traceability'
import {
  analyzeAgentConsumptionReadiness,
  applyReadinessFindingReviews,
  type AgentConsumptionReadinessFinding,
  type AgentConsumptionReadinessFindingReview,
} from '../src/design/agent-consumption-readiness'
import {
  buildDeveloperDefinitionContract,
  buildDeveloperDefinitionData,
  developerDefinitionArtifactId,
  developerDefinitionRevisionArtifactId,
  developerDefinitionTargetStatus,
  stableStringify,
  validateDeveloperDefinitionRequiredFields,
} from '../src/design/developer-definition'
import { buildHighRiskConfirmationReport } from '../src/design/high-risk-confirmations'
import {
  mergeSemanticInterpretationRule,
  semanticInterpretationRuleForFinding,
} from '../src/design/semantic-interpretation-rules'
import {
  buildAgentConsumabilityMetadata,
  type AgentConsumabilityCapabilityReview,
} from '../src/design/agent-consumability'

const repoRoot = resolve(new URL('../..', import.meta.url).pathname)
const apiBase = process.env.STUDIO_API_BASE || 'http://127.0.0.1:8100'
const nowStamp = new Date().toISOString().replace(/[-:.TZ]/g, '').slice(0, 14)
const workspaceId = process.env.OPERATOR_WORKSPACE_ID || `ws-gtm-operator-contract-${nowStamp}`
const projectId = process.env.OPERATOR_PROJECT_ID || `gtm-operator-contract-${nowStamp}`
const resumeExisting = process.env.OPERATOR_RESUME_EXISTING === '1'
const allowDeterministicFallback = process.env.OPERATOR_ALLOW_DETERMINISTIC_FALLBACK === '1'
const customCodeBundlePath = process.env.OPERATOR_CUSTOM_CODE_BUNDLE
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

interface ProjectState {
  project: ProjectDetail
  pmArtifacts: ArtifactRecord[]
  documents: Awaited<ReturnType<typeof listProjectDocuments>>
  requirements: RequirementsRecord[]
  scenarios: ArtifactRecord[]
  shapes: ShapeRecord[]
}

function log(message: string) {
  process.stdout.write(`[operator-flow] ${message}\n`)
}

async function assertOperatorAssistantReady() {
  const response = await fetch('/api/runtime-status')
  if (!response.ok) {
    throw new Error(`Studio runtime status is unavailable: HTTP ${response.status}`)
  }
  const runtime = await response.json() as {
    llm_ready?: boolean
    llm_enabled?: boolean
    assistant_provider?: string | null
    assistant_model?: string | null
    api_key_configured?: boolean
    provider_source?: string | null
    model_source?: string | null
    api_key_source?: string | null
  }
  if (runtime.llm_ready) {
    log(`Assistant ready: provider=${runtime.assistant_provider ?? 'unknown'} model=${runtime.assistant_model ?? 'unknown'}`)
    return
  }
  if (allowDeterministicFallback) {
    log('Assistant is not LLM-ready; OPERATOR_ALLOW_DETERMINISTIC_FALLBACK=1 allows deterministic fallback for controlled regression only.')
    return
  }
  const reason = !runtime.llm_enabled
    ? 'assistant provider is not enabled'
    : !runtime.api_key_configured
      ? 'assistant API key is missing'
      : !runtime.assistant_model
        ? 'assistant model is missing'
        : 'assistant runtime is incomplete'
  throw new Error([
    `Operator flow requires an LLM-ready assistant; ${reason}.`,
    `provider=${runtime.assistant_provider ?? 'not set'} (${runtime.provider_source ?? 'unknown source'})`,
    `model=${runtime.assistant_model ?? 'not set'} (${runtime.model_source ?? 'unknown source'})`,
    `api_key=${runtime.api_key_configured ? `configured (${runtime.api_key_source ?? 'unknown source'})` : 'missing'}`,
    'Configure Studio assistant settings, or set OPERATOR_ALLOW_DETERMINISTIC_FALLBACK=1 when intentionally running a deterministic fallback/control flow.',
  ].join(' '))
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
      const nameMatch = block.match(/name\s*=\s*["']([a-z][a-z0-9]*(?:[._][a-z0-9]+)+)["']/i)
      if (!nameMatch) continue
      results.push({
        capabilityId: nameMatch[1],
        relativePath: file.replace(`${repoRoot}/`, ''),
        description: matchStringArg(block, 'description'),
        implementationCalls: implementationCallHints(content, nameMatch[1]),
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

function implementationCallHints(content: string, capabilityId: string): string[] {
  const handlerName = `_handle_${capabilityId.replace(/[^a-z0-9]+/gi, '_')}`
  const handlerStart = content.search(new RegExp(`(?:async\\s+)?def\\s+${handlerName}\\s*\\(`, 'i'))
  if (handlerStart < 0) return []
  const handlerRest = content.slice(handlerStart)
  const nextTopLevel = handlerRest.slice(1).search(/\n(?=\S)/)
  const handlerBlock = nextTopLevel >= 0 ? handlerRest.slice(0, nextTopLevel + 1) : handlerRest
  const ignored = new Set([
    'ANIPError',
    'dict',
    'int',
    'len',
    'list',
    'str',
    'range',
    'print',
    'bool',
  ])
  const calls = [...handlerBlock.matchAll(/\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(/g)]
    .map((match) => match[1])
    .filter((name) => !name.startsWith('_') && !ignored.has(name))
  return Array.from(new Set(calls)).slice(0, 12)
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
    ?? block.match(new RegExp(`${key}\\s*=\\s*dict\\s*\\(([\\s\\S]*?)\\)`, 'i'))
  if (!match) return {}
  return Object.fromEntries(
    [...match[1].matchAll(/["']?([a-z_]+)["']?\s*(?::|=)\s*["']([^"']+)["']/gi)]
      .map((item) => [item[1].trim(), item[2].trim()])
      .filter(([dictKey, value]) => dictKey && value),
  )
}

function implementationSurfaceDocument(capabilities: DeclaredBundleCapability[]): string {
  return [
    `# Source: ${customCodeBundlePath} implementation surface`,
    '',
    'This custom code bundle declares implementation capabilities. If this bundle is used for generation, each declared capability must either be present in the contract or intentionally removed from the bundle before generation.',
    'Treat declared implementation input names, required flags, defaults, and allowed values as source-owned runtime surface. Do not rename them into prettier aliases in the generated contract.',
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

async function compactServiceDesignSourceText(sourceText: string): Promise<string> {
  const bundleCapabilities = await declaredCustomBundleCapabilities()
  const sourceSummary = SOURCE_DOCS
    .map((doc) => `- ${basename(doc, '.md')}`)
    .join('\n')
  const bundleSurface = bundleCapabilities.length > 0
    ? implementationSurfaceDocument(bundleCapabilities)
    : 'No custom code bundle capability declarations were discovered.'
  return [
    '# Compact Operator Service Design Source',
    '',
    'Use this compact source only to draft the product service shape. Preserve source-declared service boundaries and capability IDs. Do not copy every capability to every service.',
    '',
    '## Uploaded Source Documents',
    sourceSummary,
    '',
    bundleSurface,
    '',
    '## Source Excerpt',
    sourceText.slice(0, 12000),
  ].join('\n')
}

async function compactCapabilityFormalizationBaselineText(baselineText: string): Promise<string> {
  const bundleCapabilities = await declaredCustomBundleCapabilities()
  const bundleSurface = bundleCapabilities.length > 0
    ? implementationSurfaceDocument(bundleCapabilities)
    : 'No custom code bundle capability declarations were discovered.'
  return [
    '# Compact Operator Capability Formalization Baseline',
    '',
    'Use this compact source only to draft developer capability formalization. Preserve source-declared capability IDs, owning services, input names, required flags, allowed values, approval boundaries, and implementation behavior.',
    '',
    bundleSurface,
    '',
    '## Locked Baseline Excerpt',
    baselineText.slice(0, 16000),
  ].join('\n')
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
        return {
          service,
          score: tokenOverlapScore(capability.capabilityId, serviceText),
        }
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

async function resolveProductClarification(
  projectRef: string,
  section: ProductDesignDraftSection,
  sourceText: string,
): Promise<ProductDesignDraftSection> {
  if (section.status !== 'needs_clarification' || !section.envelope || section.envelope.proposal.proposal_kind !== 'clarification_questions') {
    return section
  }
  const answers = Object.fromEntries(
    section.envelope.proposal.questions.map((question) => [question.question_id, clarificationAnswer(section.title)]),
  )
  const answeredSource = `${sourceText}\n\n# Operator clarification answers for ${section.title}\n\n${Object.entries(answers)
    .map(([id, answer]) => `- ${id}: ${answer}`)
    .join('\n')}`
  return redraftProductDesignSection({
    projectId: projectRef,
    section: { ...section, clarificationAnswers: answers },
    sourceText: answeredSource,
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
  const answers = Object.fromEntries(
    section.envelope.proposal.questions.map((question) => [question.question_id, clarificationAnswer(section.title)]),
  )
  const answeredBaseline = `${baselineText}\n\n# Operator clarification answers for ${section.title}\n\n${Object.entries(answers)
    .map(([id, answer]) => `- ${id}: ${answer}`)
    .join('\n')}`
  return redraftDeveloperDesignSection({
    projectId: projectRef,
    section: { ...section, clarificationAnswers: answers },
    baselineText: answeredBaseline,
    sourceRequirementsId: requirementsId,
    sourceShapeId: shapeId,
    useDeterministic: false,
    serviceTopologyPreference: {
      granularity: 'source_defined',
      target_service_count: serviceCount,
      preserve_source_services: true,
      rationale: 'Operator validation must preserve source-declared service and capability identities so package exports remain compatible with source-owned implementation bundles.',
    },
  })
}

function contractIdentityPayload(baseContract: Record<string, any>) {
  const payload = JSON.parse(JSON.stringify(baseContract))
  delete payload.generated_at
  delete payload.compiled_contract_identity
  if (payload.source?.developer_definition_revision) {
    payload.source.developer_definition_revision = null
  }
  return payload
}

function contractSignature(baseContract: Record<string, any>): string {
  return createHash('sha256').update(stableStringify(contractIdentityPayload(baseContract))).digest('hex')
}

function serviceCountFromShape(shape: ShapeRecord | null): number {
  const data = shape?.data as Record<string, any> | undefined
  const services = data?.shape?.services ?? data?.services
  return Array.isArray(services) ? services.length : 0
}

function readinessReviewForFinding(finding: AgentConsumptionReadinessFinding, reviewedAt: string): AgentConsumptionReadinessFindingReview {
  if (finding.category === 'derived_target' || finding.category === 'app_glue' || finding.owner === 'agent_app_glue') {
    return {
      id: finding.id,
      decision: 'explicit_app_glue',
      note: 'Operator review classified this as consuming-app guidance. The contract remains valid; the app profile owns selection, framing, or clarification behavior without changing generic ANIP invocation.',
      reviewed_at: reviewedAt,
      review_method: 'manual',
    }
  }
  if (finding.severity === 'blocker') {
    return {
      id: finding.id,
      decision: 'follow_up',
      note: 'Operator review left this as follow-up because blocker-level contract behavior should not be auto-accepted.',
      reviewed_at: reviewedAt,
      review_method: 'manual',
    }
  }
  return {
    id: finding.id,
    decision: 'acceptable_warning',
    note: 'Operator review accepted this as a reviewed limitation for this contract-generation validation run.',
    reviewed_at: reviewedAt,
    review_method: 'manual',
  }
}

function capabilityById(definition: DeveloperDefinitionData, capabilityId: string | undefined) {
  if (!capabilityId) return null
  return definition.capability_formalizations.find((capability) => capability.capability_id === capabilityId) ?? null
}

function buildConsumabilityReviews(
  definition: DeveloperDefinitionData,
  findings: AgentConsumptionReadinessFinding[],
  findingReviews: Record<string, AgentConsumptionReadinessFindingReview>,
): Record<string, AgentConsumabilityCapabilityReview> {
  const reviews: Record<string, AgentConsumabilityCapabilityReview> = {}
  for (const finding of findings) {
    const review = findingReviews[finding.id]
    if (review?.decision !== 'explicit_app_glue' || !finding.capability_id) continue
    const capability = capabilityById(definition, finding.capability_id)
    const current = reviews[finding.capability_id]
    const semanticRule = semanticInterpretationRuleForFinding(finding, review.note)
    reviews[finding.capability_id] = {
      capability_id: finding.capability_id,
      reviewed_at: review.reviewed_at,
      intent_category: current?.intent_category ?? finding.capability_id.replace(/[_-]+/g, '.'),
      intent_summary: current?.intent_summary ?? capability?.summary ?? capability?.title ?? finding.title,
      app_glue_required: true,
      app_glue_reason: current?.app_glue_reason ?? review.note,
      intent_rules: current?.intent_rules ?? [{
        id: finding.category,
        meaning: finding.detail,
        owner: 'agent_app_glue',
        agent_action: 'Select, clarify, or frame the request before invoking the ANIP capability.',
      }],
      business_language_rules: mergeSemanticInterpretationRule(current?.business_language_rules, semanticRule),
      input_meanings: current?.input_meanings,
      reference_catalogs: current?.reference_catalogs,
      app_boundaries: current?.app_boundaries,
      selection_hints: current?.selection_hints,
    }
  }

  const metadata = buildAgentConsumabilityMetadata({
    definition,
    manualReviews: reviews,
  })
  for (const capability of definition.capability_formalizations) {
    if (!capability.capability_id || reviews[capability.capability_id]) continue
    const capabilityMetadata = metadata.capabilities[capability.capability_id]
    const requiresAppGlue =
      capability.implementation_fit?.category === 'agent_app_glue'
      || capabilityMetadata?.app_glue?.required === true
    if (!requiresAppGlue) continue
    const reason = capabilityMetadata?.app_glue?.reason?.trim()
      || 'Operator review classified this as consuming-app guidance. The contract remains valid; the app profile owns presentation, selection, framing, or clarification behavior without changing generic ANIP invocation.'
    reviews[capability.capability_id] = {
      capability_id: capability.capability_id,
      reviewed_at: new Date().toISOString(),
      intent_category: capabilityMetadata?.intent.category ?? capability.capability_id.replace(/[_-]+/g, '.'),
      intent_summary: capabilityMetadata?.intent.summary ?? capability.summary ?? capability.title ?? capability.capability_id,
      app_glue_required: true,
      app_glue_reason: reason,
      intent_rules: capabilityMetadata?.intent_rules ?? [],
      business_language_rules: capabilityMetadata?.business_language_rules ?? [],
      input_meanings: capabilityMetadata?.input_meanings,
      reference_catalogs: capabilityMetadata?.reference_catalogs,
      app_boundaries: capabilityMetadata?.app_boundaries,
    }
  }
  return reviews
}

function applyOperatorCoordinationCoverageDecisions(
  traceability: TraceabilityRecordData,
  definition: DeveloperDefinitionData,
  reviewedAt: string,
): TraceabilityRecordData {
  const serviceHandoffsContracted = Boolean(
    definition.audit.service_handoffs_required
    || definition.audit.cross_service_continuity_required
    || definition.audit.cross_service_reconstruction_required,
  )
  if (serviceHandoffsContracted) return traceability

  const coverage = traceability.coverage.map((item): TraceabilityCoverageItem => {
    if (!item.id.startsWith('shape:coordination:') || item.status !== 'not_addressed') return item
    return {
      ...item,
      status: 'deferred',
      rationale: [
        `Operator reviewed ${item.label || 'this service coordination edge'} as consuming-app or implementation orchestration.`,
        'The generated ANIP service contract does not declare cross-service handoff execution for this package revision.',
        'Keep the relationship explicit as app glue or implementation material instead of implying hidden generated service behavior.',
      ].join(' '),
      linked_surfaces: ['generation_and_extensions'],
      operator_resolution: {
        choice_id: 'app_owned',
        applied_at: reviewedAt,
        target_artifact: 'Developer Coverage / Agent & App Glue',
        summary: 'Cross-service coordination is reviewed as app/implementation-owned orchestration, not generated ANIP handoff behavior.',
        requires_review: true,
        changes: [
          `Marked "${item.label || item.id}" intentionally deferred from contract-owned service behavior.`,
          'Recorded that the consuming app or implementation material must coordinate this relationship explicitly if needed.',
          `Preserved source detail: ${item.detail || 'No source detail provided.'}`,
        ],
      },
    }
  })
  return { ...traceability, coverage }
}

function applyAutomaticCoverageStatuses(
  traceability: TraceabilityRecordData,
  definition: DeveloperDefinitionData,
): TraceabilityRecordData {
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

async function saveDefinitionArtifacts(state: ProjectState) {
  const sourcePmArtifacts = state.pmArtifacts.filter((artifact) => {
    const artifactType = String(artifact.data?.artifact_type ?? '').trim()
    return artifactType !== 'developer_definition'
      && artifactType !== 'developer_definition_revision'
      && artifactType !== 'design_traceability'
  })
  const baselineArtifact = sourcePmArtifacts.find((artifact) => artifact.id === developerBaselineArtifactId(state.project.id))
  const baseline = (baselineArtifact?.data ?? null) as any
  const requirements = state.requirements[0] ?? null
  const shape = state.shapes[0] ?? null
  const firstTraceability = buildTraceabilityRecord({
    pmArtifacts: sourcePmArtifacts,
    requirements,
    scenarios: state.scenarios,
    shape,
    baselineLockedAt: baseline?.locked_at ?? null,
    existing: null,
  })
  const definition = buildDeveloperDefinitionData({
    project: state.project,
    baseline,
    requirements,
    scenarios: state.scenarios,
    shape,
    pmArtifacts: sourcePmArtifacts,
  })
  const validationIssues = validateDeveloperDefinitionRequiredFields(definition)
  if (validationIssues.length > 0) {
    throw new Error(`Developer Definition has ${validationIssues.length} missing fields: ${validationIssues.slice(0, 12).map((issue) => issue.message).join(' ')}`)
  }

  const reviewedAt = new Date().toISOString()
  const readiness = analyzeAgentConsumptionReadiness(definition)
  const readinessReviews = Object.fromEntries(
    readiness.findings.map((finding) => [finding.id, readinessReviewForFinding(finding, reviewedAt)]),
  )
  const blockerFollowUps = Object.values(readinessReviews).filter((review) => review.decision === 'follow_up')
  if (blockerFollowUps.length > 0) {
    throw new Error(`Operator flow found ${blockerFollowUps.length} blocker readiness findings that require real review: ${blockerFollowUps.map((review) => review.id).join(', ')}`)
  }
  const reviewedReadiness = applyReadinessFindingReviews(readiness, readinessReviews)
  const reviewedTraceability = applyOperatorCoordinationCoverageDecisions(
    applyAutomaticCoverageStatuses(firstTraceability, definition),
    definition,
    reviewedAt,
  )
  const traceabilityWithReadiness: TraceabilityRecordData = {
    ...reviewedTraceability,
    developer_status: 'ready_for_pm_review',
    developer_note: 'Operator validation generated and reviewed Developer Definition readiness artifacts.',
    developer_marked_at: reviewedAt,
    agent_consumption_readiness: JSON.parse(JSON.stringify(reviewedReadiness)),
    agent_consumability_reviews: buildConsumabilityReviews(definition, readiness.findings, readinessReviews),
  }

  await upsertArtifact(state.project.id, {
    id: traceabilityArtifactId(state.project.id),
    title: 'Design Traceability',
    data: traceabilityWithReadiness as Record<string, any>,
  })

  const refreshedForHighRisk = await loadState(state.project.id)
  const refreshedSourcePmArtifacts = refreshedForHighRisk.pmArtifacts.filter((artifact) => {
    const artifactType = String(artifact.data?.artifact_type ?? '').trim()
    return artifactType !== 'developer_definition'
      && artifactType !== 'developer_definition_revision'
      && artifactType !== 'design_traceability'
  })
  const pmArtifactsForHighRisk: ArtifactRecord[] = [
    ...refreshedSourcePmArtifacts,
    {
      id: traceabilityArtifactId(state.project.id),
      project_id: state.project.id,
      title: 'Design Traceability',
      status: 'active',
      data: traceabilityWithReadiness as unknown as Record<string, any>,
      content_hash: contractSignature(traceabilityWithReadiness as unknown as Record<string, any>),
      created_at: reviewedAt,
      updated_at: reviewedAt,
    } as ArtifactRecord,
    {
      id: developerDefinitionArtifactId(state.project.id),
      project_id: state.project.id,
      title: 'Developer Definition',
      status: 'active',
      data: definition as unknown as Record<string, any>,
      content_hash: contractSignature(definition as unknown as Record<string, any>),
      created_at: reviewedAt,
      updated_at: reviewedAt,
    } as ArtifactRecord,
  ]
  const highRiskInitial = buildHighRiskConfirmationReport({
    project: refreshedForHighRisk.project,
    pmArtifacts: pmArtifactsForHighRisk,
    documents: refreshedForHighRisk.documents,
    requirements: refreshedForHighRisk.requirements,
    scenarios: refreshedForHighRisk.scenarios,
    shapes: refreshedForHighRisk.shapes,
  })
  const highRiskReport = buildHighRiskConfirmationReport({
    project: refreshedForHighRisk.project,
    pmArtifacts: pmArtifactsForHighRisk,
    documents: refreshedForHighRisk.documents,
    requirements: refreshedForHighRisk.requirements,
    scenarios: refreshedForHighRisk.scenarios,
    shapes: refreshedForHighRisk.shapes,
    existing: {
      ...highRiskInitial,
      reviews: Object.fromEntries(highRiskInitial.items.map((item) => [item.id, {
        id: item.id,
        status: 'confirmed',
        note: 'Operator validation confirmed this item for contract generation; it remains visible as review evidence.',
        reviewed_at: reviewedAt,
      }])),
    },
  })
  const traceabilityFinal: TraceabilityRecordData = {
    ...traceabilityWithReadiness,
    high_risk_confirmations: highRiskReport,
  }
  await upsertArtifact(state.project.id, {
    id: traceabilityArtifactId(state.project.id),
    title: 'Design Traceability',
    data: traceabilityFinal as Record<string, any>,
  })

  const baseContract = buildDeveloperDefinitionContract({
    project: state.project,
    baseline,
    requirements,
    scenarios: state.scenarios,
    shape,
    traceability: traceabilityFinal,
    developerDefinition: definition,
  }) as Record<string, any>
  const savedAt = new Date().toISOString()
  const savedRevision = {
    revision_number: 1,
    revision_artifact_id: developerDefinitionRevisionArtifactId(state.project.id, 1),
    previous_revision_artifact_id: null,
    saved_at: savedAt,
  }
  const identity: DeveloperCompiledContractIdentity = {
    artifact_name: `${state.project.id}-developer-definition.json`,
    canonical_format: 'stable-json-v1',
    signature_algorithm: 'sha256',
    signature: contractSignature(baseContract),
    generated_at: savedAt,
  }
  const payload: DeveloperDefinitionData = {
    ...definition,
    compiled_contract_identity: identity,
    saved_revision: savedRevision,
    saved_at: savedAt,
  }
  const revisionPayload: DeveloperDefinitionRevisionData = {
    ...payload,
    artifact_type: 'developer_definition_revision',
  }
  await upsertArtifact(state.project.id, {
    id: savedRevision.revision_artifact_id,
    title: `Developer Definition Revision ${savedRevision.revision_number}`,
    data: revisionPayload,
  })
  await upsertArtifact(state.project.id, {
    id: developerDefinitionArtifactId(state.project.id),
    title: 'Developer Definition',
    data: payload,
  })
  return { readiness: reviewedReadiness, definition: payload, highRiskReport }
}

async function main() {
  await assertOperatorAssistantReady()

  if (resumeExisting) {
    log(`Resuming existing project ${projectId}`)
    await alignShapeWithCustomBundleCapabilities(projectId)
    const state = await loadState(projectId)
    const saved = await saveDefinitionArtifacts(state)
    log(`Readiness: ${saved.readiness.status} ${saved.readiness.score}/100`)
    log(`High-risk confirmations unresolved: ${saved.highRiskReport.summary.unresolved}`)
    log(`Capabilities: ${saved.definition.capability_formalizations.length}`)
    log(`Project URL: http://localhost:5173/studio/design/projects/${projectId}/pm/assistant`)
    log(`Package command: cd studio && node_modules/.bin/tsx scripts/build-registry-package.ts --project-id ${projectId} --package-id gtm-pipeline-q2-review --package-version 0.3.7 --output-dir /tmp/anip-operator-validation/${projectId} --studio-api-base ${apiBase} --persist-readiness`)
    return
  }

  log(`Creating workspace ${workspaceId}`)
  await createWorkspace({
    id: workspaceId,
    name: `GTM Operator Contract ${nowStamp}`,
    summary: 'Fresh operator-mode validation workspace seeded from GTM source documents.',
  })
  log(`Creating project ${projectId}`)
  await createProject({
    id: projectId,
    workspace_id: workspaceId,
    name: `GTM Operator Contract ${nowStamp}`,
    summary: 'Fresh operator-mode GTM validation project.',
    domain: 'gtm',
    labels: ['gtm-showcase', 'operator-validation'],
    project_type: 'standard',
  })

  log('Uploading source documents')
  await seedSourceDocuments(projectId)
  const sourceText = await sourceTextFromDocs()

  log('Drafting Product Design with assistant')
  const productBundle = await draftProductDesignBundle({
    projectId,
    projectName: `GTM Operator Contract ${nowStamp}`,
    sourceText,
    useDeterministic: false,
    onProgress: (message) => log(`PM: ${message}`),
  })
  let state = await loadState(projectId)
  for (const originalSection of productBundle.sections) {
    let section = await resolveProductClarification(projectId, originalSection, sourceText)
    if (section.status === 'failed') {
      if (section.id === 'service_design') {
        log(`PM section ${section.title} failed assistant validation; retrying with compact service-design source`)
        section = await redraftProductDesignSection({
          projectId,
          section,
          sourceText: await compactServiceDesignSourceText(sourceText),
          useDeterministic: false,
          serviceTopologyPreference: {
            granularity: 'source_defined',
            preserve_source_services: true,
          },
        })
      }
    }
    if (section.status === 'failed') {
      if (!allowDeterministicFallback) {
        throw new Error(`PM section ${section.title} failed assistant validation: ${section.error}`)
      }
      log(`PM section ${section.title} failed assistant validation; retrying deterministic fallback`)
      section = await redraftProductDesignSection({
        projectId,
        section,
        sourceText,
        useDeterministic: true,
      })
    }
    section = await resolveProductClarification(projectId, section, sourceText)
    if (section.status === 'failed') throw new Error(`PM section ${section.title} failed: ${section.error}`)
    if (section.status === 'needs_clarification') throw new Error(`PM section ${section.title} still needs clarification`)
    log(`Saving PM section ${section.title}`)
    await saveAcceptedProductDesignSection({
      project: state.project,
      section,
      pmArtifacts: state.pmArtifacts,
      requirements: state.requirements,
      notes: 'Operator-mode validation accepted this assistant proposal from source documents.',
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
  state = await loadState(projectId)
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
  log('Drafting Developer Design with assistant')
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
      rationale: 'Operator validation must preserve source-declared service and capability identities so package exports remain compatible with source-owned implementation bundles.',
    },
    onProgress: (message) => log(`Dev: ${message}`),
  })
  for (const originalSection of developerBundle.sections) {
    let section = await resolveDeveloperClarification(projectId, originalSection, baselineText, requirements?.id ?? null, shape?.id ?? null, serviceCount)
    if (section.status === 'failed') {
      if (section.id === 'capability_formalization') {
        log(`Developer section ${section.title} failed assistant validation; retrying with compact capability surface`)
        section = await redraftDeveloperDesignSection({
          projectId,
          section,
          baselineText: await compactCapabilityFormalizationBaselineText(baselineText),
          sourceRequirementsId: requirements?.id,
          sourceShapeId: shape?.id,
          useDeterministic: false,
          serviceTopologyPreference: {
            granularity: 'source_defined',
            target_service_count: serviceCount,
            preserve_source_services: true,
            rationale: 'Operator validation must preserve source-declared service and capability identities so package exports remain compatible with source-owned implementation bundles.',
          },
        })
      }
    }
    if (section.status === 'failed') {
      if (!allowDeterministicFallback) {
        throw new Error(`Developer section ${section.title} failed assistant validation: ${section.error}`)
      }
      log(`Developer section ${section.title} failed assistant validation; retrying deterministic fallback`)
      section = await redraftDeveloperDesignSection({
        projectId,
        section,
        baselineText,
        sourceRequirementsId: requirements?.id,
        sourceShapeId: shape?.id,
        useDeterministic: true,
        serviceTopologyPreference: {
          granularity: 'source_defined',
          target_service_count: serviceCount,
          preserve_source_services: true,
          rationale: 'Operator validation must preserve source-declared service and capability identities so package exports remain compatible with source-owned implementation bundles.',
        },
      })
    }
    section = await resolveDeveloperClarification(projectId, section, baselineText, requirements?.id ?? null, shape?.id ?? null, serviceCount)
    if (section.status === 'failed') throw new Error(`Developer section ${section.title} failed: ${section.error}`)
    if (section.status === 'needs_clarification') throw new Error(`Developer section ${section.title} still needs clarification`)
    log(`Saving Developer section ${section.title}`)
    await saveAcceptedDeveloperDesignSection({
      projectId,
      section,
      notes: 'Operator-mode validation accepted this locked-baseline assistant proposal.',
    })
  }

  state = await loadState(projectId)
  log('Saving Developer Definition, readiness, app glue, and high-risk confirmations')
  const saved = await saveDefinitionArtifacts(state)
  log(`Readiness: ${saved.readiness.status} ${saved.readiness.score}/100`)
  log(`High-risk confirmations unresolved: ${saved.highRiskReport.summary.unresolved}`)
  log(`Capabilities: ${saved.definition.capability_formalizations.length}`)
  log(`Project URL: http://localhost:5173/studio/design/projects/${projectId}/pm/assistant`)
  log(`Package command: cd studio && node_modules/.bin/tsx scripts/build-registry-package.ts --project-id ${projectId} --package-id gtm-pipeline-q2-review --package-version 0.3.7 --output-dir /tmp/anip-operator-validation/${projectId} --studio-api-base ${apiBase} --persist-readiness`)
}

main().catch((err) => {
  process.stderr.write(`[operator-flow] failed: ${err instanceof Error ? err.stack ?? err.message : String(err)}\n`)
  process.exitCode = 1
})
