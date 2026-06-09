#!/usr/bin/env tsx

import * as crypto from 'crypto'
import { execFileSync } from 'child_process'
import * as fs from 'fs'
import * as path from 'path'
import { fileURLToPath } from 'url'

import {
  buildDeveloperDefinitionContract,
  buildDeveloperDefinitionData,
  buildExtensionManifest,
  buildGeneratedRuntimeTarget,
  buildGeneratedStructureSummary,
  buildIntegrationAdapterBindings,
  buildLocalConformanceReport,
  findDeveloperDefinitionArtifact,
  findLatestDeveloperDefinitionRevisionArtifact,
  stableStringify,
  validateDeveloperDefinitionRequiredFields,
} from '../src/design/developer-definition'
import { STUDIO_PROTOCOL_VERSION } from '../src/version'
import {
  analyzeAgentConsumptionReadiness,
  applyReadinessFindingReviews,
  normalizeReadinessFindingReviews,
} from '../src/design/agent-consumption-readiness'
import { buildAgentConsumabilityMetadata } from '../src/design/agent-consumability'
import { KNOWN_EFFECT_IDS, isKnownEffect } from '../src/design/effect-vocabulary'
import { buildTraceabilityRecord } from '../src/design/traceability'
import type {
  ArtifactRecord,
  DeveloperBaselineData,
  DeveloperCompiledContractIdentity,
  DeveloperDefinitionData,
  ProjectDocumentRecord,
  ProjectDetail,
  RequirementsRecord,
  ShapeRecord,
} from '../src/design/project-types'

type Args = {
  projectId: string | null
  packageId: string | null
  packageVersion: string
  outputDir: string
  registryUrl: string
  studioApiBase: string
  publish: boolean
  publishViaStudio: boolean
  persistReadiness: boolean
  allowSourceIdDrift: boolean
}

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const repoRoot = path.resolve(__dirname, '..', '..')

function parseArgs(): Args {
  const args = process.argv.slice(2)
  const value = (name: string, fallback: string) => {
    const index = args.indexOf(name)
    return index >= 0 && args[index + 1] ? args[index + 1] : fallback
  }
  return {
    projectId: value('--project-id', ''),
    packageId: value('--package-id', ''),
    packageVersion: value('--package-version', '0.3.0'),
    outputDir: path.resolve(value('--output-dir', path.join(repoRoot, 'examples/showcase/gtm/registry-packages'))),
    registryUrl: value('--registry-url', process.env.ANIP_REGISTRY_URL || 'http://127.0.0.1:8200'),
    studioApiBase: value('--studio-api-base', process.env.STUDIO_API_BASE || 'http://127.0.0.1:8100'),
    publish: args.includes('--publish'),
    publishViaStudio: args.includes('--publish-via-studio'),
    persistReadiness: args.includes('--persist-readiness'),
    allowSourceIdDrift: args.includes('--allow-source-id-drift'),
  }
}

function loadGtmSeed(): any {
  const script = [
    'import json, sys',
    `sys.path.insert(0, ${JSON.stringify(path.join(repoRoot, 'studio'))})`,
    'from server.seed_catalog import SEED_PROJECTS',
    'print(json.dumps(next(item for item in SEED_PROJECTS if item["project"]["id"] == "gtm-pipeline-q2-review")))',
  ].join('; ')
  return JSON.parse(execFileSync('python3', ['-c', script], { encoding: 'utf8', cwd: repoRoot }))
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  const body = await response.text()
  if (!response.ok) {
    throw new Error(`${init?.method ?? 'GET'} ${url} failed (${response.status}): ${body}`)
  }
  return (body ? JSON.parse(body) : undefined) as T
}

function contentHash(data: unknown): string {
  return crypto.createHash('sha256').update(stableStringify(data)).digest('hex')
}

type PackageSourceDocument = ProjectDocumentRecord & {
  content?: string
}

function buildUsageCommands(packageId: string, packageVersion: string): Record<string, string> {
  return {
    generate_python_from_bundle: `go run ./cmd/anip-generate --package-bundle <downloaded-package>.anip-package.json --target python --dependency-source local --output ./generated/${packageId} --force`,
    generate_python_from_registry: `go run ./cmd/anip-generate --registry-url <registry-url> --package-id ${packageId} --package-version ${packageVersion} --target python --dependency-source registry --output ./generated/${packageId} --force`,
    verify_definition_file: 'go run ./cmd/anip-verify --definition anip-service-definition.json',
    verify_registry_package: `go run ./cmd/anip-verify --registry-url <registry-url> --package-id ${packageId} --package-version ${packageVersion}`,
  }
}

function buildPackageReadme(source: PackageSource, packageId: string, packageVersion: string, capabilityIds: string[], serviceIds: string[]): string {
  const project = source.project
  const commands = buildUsageCommands(packageId, packageVersion)
  const capabilityPreview = capabilityIds.slice(0, 12)
  const servicePreview = serviceIds.slice(0, 8)
  return [
    `# ${project.name}`,
    '',
    project.summary || 'ANIP service blueprint generated from a reviewed Studio project.',
    '',
    'This package contains the signed ANIP behavior contract, recommended lock file, and tooling metadata for agent integration.',
    'Custom implementation code is not embedded in the behavior contract unless it is explicitly attached as implementation material.',
    '',
    `Project: ${project.id}`,
    `Package: ${packageId}@${packageVersion}`,
    `Services: ${serviceIds.length}${servicePreview.length ? ` (${servicePreview.join(', ')}${serviceIds.length > servicePreview.length ? ', ...' : ''})` : ''}`,
    `Capabilities: ${capabilityIds.length}${capabilityPreview.length ? ` (${capabilityPreview.join(', ')}${capabilityIds.length > capabilityPreview.length ? ', ...' : ''})` : ''}`,
    '',
    '## Generate',
    '',
    'From a downloaded package bundle:',
    '',
    '```bash',
    commands.generate_python_from_bundle,
    '```',
    '',
    'From a trusted registry package:',
    '',
    '```bash',
    commands.generate_python_from_registry,
    '```',
    '',
    '## Verify',
    '',
    '```bash',
    commands.verify_definition_file,
    commands.verify_registry_package,
    '```',
  ].join('\n')
}

function cleanLinkTitle(value: unknown, fallback: string): string {
  const text = String(value ?? '').replace(/\s+/g, ' ').trim()
  return (text || fallback).slice(0, 120)
}

function cleanHttpUrl(value: unknown): string {
  const text = String(value ?? '').trim().replace(/[),.;\]]+$/, '')
  if (!/^https?:\/\//i.test(text)) return ''
  try {
    const url = new URL(text)
    if (url.protocol !== 'http:' && url.protocol !== 'https:') return ''
    return url.toString().slice(0, 1024)
  } catch {
    return ''
  }
}

function pushSourceLink(
  links: Array<{ title: string; url: string }>,
  seen: Set<string>,
  title: unknown,
  url: unknown,
  fallbackTitle: string,
): void {
  const normalizedUrl = cleanHttpUrl(url)
  if (!normalizedUrl || seen.has(normalizedUrl)) return
  seen.add(normalizedUrl)
  links.push({ title: cleanLinkTitle(title, fallbackTitle), url: normalizedUrl })
}

function reviewedSourceLinks(source: PackageSource): Array<{ title?: unknown; url?: unknown }> {
  const traceability = (source.traceabilityArtifact?.data ?? {}) as Record<string, any>
  const candidates = [
    traceability.registry_metadata?.source_links,
    traceability.package_metadata?.source_links,
    traceability.publication_metadata?.source_links,
  ]
  return candidates.flatMap((value) => Array.isArray(value) ? value : [])
}

function buildPackageSourceLinks(source: PackageSource): Array<{ title: string; url: string }> {
  const links: Array<{ title: string; url: string }> = []
  const seen = new Set<string>()

  for (const item of reviewedSourceLinks(source)) {
    pushSourceLink(links, seen, item.title, item.url, 'Reviewed source link')
  }

  for (const document of source.sourceDocuments) {
    pushSourceLink(links, seen, document.title, document.source_path, 'Source document')

    const content = document.content ?? ''
    for (const match of content.matchAll(/\[([^\]]{1,120})\]\((https?:\/\/[^)\s]+)\)/gi)) {
      pushSourceLink(links, seen, match[1], match[2], document.title || 'Source document')
    }
    for (const match of content.matchAll(/https?:\/\/[^\s<>"')\]]+/gi)) {
      pushSourceLink(links, seen, document.title, match[0], document.title || 'Source document')
    }
  }

  return links.slice(0, 8)
}

function buildManifestSourceSummary(source: PackageSource, productRevisionRef: string, developerRevisionRef: string): Record<string, unknown> {
  const publicSourceUrl = source.sourceDocuments
    .map((document) => cleanHttpUrl(document.source_path))
    .find(Boolean)
  return {
    product_revision_ref: productRevisionRef,
    developer_revision_ref: developerRevisionRef,
    source_document_count: source.sourceDocuments.length,
    source_documents: source.sourceDocuments.slice(0, 12).map((document) => ({
      id: document.id,
      title: document.title,
      kind: document.kind,
    })),
    ...(publicSourceUrl ? { business_source_url: publicSourceUrl } : {}),
  }
}

function sha256Digest(data: unknown): string {
  return `sha256:${crypto.createHash('sha256').update(stableStringify(data)).digest('hex')}`
}

function artifactRecord(seed: any, projectId: string, now: string): ArtifactRecord {
  return {
    id: seed.id,
    project_id: projectId,
    title: seed.title,
    status: seed.status ?? 'accepted',
    data: seed.data,
    content_hash: contentHash(seed.data),
    created_at: now,
    updated_at: now,
  }
}

function requirementsRecord(seed: any, projectId: string, now: string): RequirementsRecord {
  return {
    ...artifactRecord(seed, projectId, now),
    role: 'primary',
  }
}

function shapeRecord(seed: any, projectId: string, now: string): ShapeRecord {
  return {
    ...artifactRecord(seed, projectId, now),
    requirements_id: 'req-gtm-pipeline-q2-review',
  }
}

function contractIdentityPayload(baseContract: Record<string, any>) {
  const payload = JSON.parse(JSON.stringify(baseContract))
  delete payload.generated_at
  delete payload.compiled_contract_identity
  if (payload.source?.developer_definition_revision) {
    payload.source.developer_definition_revision.saved_at = null
  }
  return payload
}

function writeJson(filePath: string, payload: unknown) {
  fs.writeFileSync(filePath, `${JSON.stringify(payload, null, 2)}\n`, 'utf8')
}

function assertKnownEffectList(path: string, value: unknown) {
  if (!Array.isArray(value)) {
    throw new Error(`${path} must be an array of canonical effect IDs`)
  }
  for (const [index, item] of value.entries()) {
    const effectId = String(item ?? '').trim()
    if (!effectId || isKnownEffect(effectId)) continue
    throw new Error(`${path}[${index}] declares unknown effect "${effectId}". Use canonical effect IDs: ${KNOWN_EFFECT_IDS.join(', ')}.`)
  }
}

function assertKnownEffectsInPayload(pathPrefix: string, value: unknown) {
  if (Array.isArray(value)) {
    value.forEach((item, index) => assertKnownEffectsInPayload(`${pathPrefix}[${index}]`, item))
    return
  }
  if (!value || typeof value !== 'object') return
  const record = value as Record<string, unknown>
  for (const [key, item] of Object.entries(record)) {
    const path = `${pathPrefix}.${key}`
    if (key === 'business_effects') {
      if (!item || typeof item !== 'object' || Array.isArray(item)) {
        throw new Error(`${path} must be an object`)
      }
      const effects = item as Record<string, unknown>
      if ('produces' in effects) assertKnownEffectList(`${path}.produces`, effects.produces)
      if ('does_not_produce' in effects) assertKnownEffectList(`${path}.does_not_produce`, effects.does_not_produce)
      assertKnownEffectsInPayload(path, item)
      continue
    }
    if (key === 'unsupported_effects' || key === 'suppress_unsupported_effects') {
      assertKnownEffectList(path, item)
      continue
    }
    assertKnownEffectsInPayload(path, item)
  }
}

type PackageSource = {
  project: ProjectDetail
  requirements: RequirementsRecord
  scenarios: ArtifactRecord[]
  shape: ShapeRecord | null
  pmArtifacts: ArtifactRecord[]
  baseline: DeveloperBaselineData
  baselineLockedAt: string
  traceabilityArtifact: ArtifactRecord | null
  developerDefinitionArtifact: ArtifactRecord | null
  sourceDocuments: PackageSourceDocument[]
  sourceDeclaredIdentity: SourceDeclaredIdentity
  productRevisionRef: string
  developerRevisionRefPrefix: string
}

type SourceDeclaredIdentity = {
  capabilityIds: string[]
  serviceIds: string[]
}

function seedReviewedAgentConsumabilityRules(): Record<string, any> {
  return {
    'gtm.pipeline_summary': {
      capability_id: 'gtm.pipeline_summary',
      reviewed_at: '2026-05-06T00:00:00Z',
      business_language_rules: [
        {
          id: 'bounded-risk-concentration',
          meaning: 'Risk concentration at the pipeline-summary level means bounded risk distribution or concentration evidence, not raw export or hidden row-level detail.',
          owner: 'agent_app_glue',
          applies_when: {
            all_terms: ['risk'],
            any_terms: ['concentration', 'concentrated'],
            exclude_terms: ['raw', 'export', 'csv', 'download'],
          },
          interpretation: 'Treat bounded risk concentration wording as supported summary intent for this capability.',
          agent_action: 'treat_as_supported',
        },
      ],
    },
    'gtm.route_leads': {
      capability_id: 'gtm.route_leads',
      reviewed_at: '2026-05-06T00:00:00Z',
      business_language_rules: [
        {
          id: 'follow-up-as-routing-purpose',
          meaning: 'Account-executive follow-up can describe the destination or purpose of a routing preview. It is not outreach drafting unless the user asks to draft, write, generate, send, email, message, or create content.',
          owner: 'agent_app_glue',
          applies_when: {
            all_terms: ['follow-up'],
            any_terms: ['account executive', 'ae', 'sales'],
            exclude_terms: ['draft', 'write', 'generate', 'send', 'email', 'message', 'content', 'linkedin'],
          },
          interpretation: 'Keep this as routing/approval-preview intent, not outreach-content intent.',
          agent_action: 'treat_as_purpose',
        },
      ],
    },
  }
}

function reviewedAgentConsumabilityRules(source: PackageSource): Record<string, any> | undefined {
  const existing = (source.traceabilityArtifact?.data as any)?.agent_consumability_reviews
  if (existing && typeof existing === 'object') {
    return existing
  }
  return source.project.id === 'gtm-pipeline-q2-review' ? seedReviewedAgentConsumabilityRules() : undefined
}

function primaryProductArtifacts(pmArtifacts: ArtifactRecord[]): ArtifactRecord[] {
  return pmArtifacts.filter((artifact) => {
    const artifactType = String((artifact.data as Record<string, any> | undefined)?.artifact_type ?? '')
    return ![
      'agent_consumption_readiness',
      'anip_registry_publication',
      'design_traceability',
      'developer_baseline',
      'developer_definition',
      'developer_generation_run',
      'external_cli_provenance',
      'product_design_revision',
    ].includes(artifactType)
  })
}

function resolveRevisionRef(sourceInputs: Record<string, any>, fallback: string): string {
  const artifactId = typeof sourceInputs.product_revision_artifact_id === 'string'
    ? sourceInputs.product_revision_artifact_id.trim()
    : ''
  const revisionNumber = typeof sourceInputs.product_revision_number === 'number'
    ? sourceInputs.product_revision_number
    : null
  if (artifactId) return revisionNumber ? `${artifactId}@r${revisionNumber}` : artifactId
  return fallback
}

function buildSeedSource(args: Args): PackageSource {
  const seed = loadGtmSeed()
  const now = new Date().toISOString()
  const projectSeed = seed.project
  const project: ProjectDetail = {
    id: projectSeed.id,
    workspace_id: projectSeed.workspace_id ?? '',
    name: projectSeed.name,
    summary: projectSeed.summary,
    domain: projectSeed.domain,
    labels: projectSeed.labels ?? [],
    project_type: projectSeed.project_type ?? 'standard',
    integration_profile: projectSeed.integration_profile ?? { kind: 'none', systems: [] },
    created_at: now,
    updated_at: now,
    requirements_count: 1 + (seed.additional_requirements?.length ?? 0),
    scenarios_count: (seed.scenario ? 1 : 0) + (seed.additional_scenarios?.length ?? 0),
    proposals_count: seed.proposal ? 1 : 0,
    evaluations_count: seed.evaluation ? 1 : 0,
    shapes_count: seed.shape ? 1 : 0,
    documents_count: seed.requirements?.data?.source_documents?.length ?? 0,
    pm_artifacts_count: seed.pm_artifacts?.length ?? 0,
  }
  const requirements = requirementsRecord(seed.requirements, project.id, now)
  const scenarios = [
    ...(seed.scenario ? [seed.scenario] : []),
    ...(seed.additional_scenarios ?? []),
  ].map((scenario) => artifactRecord(scenario, project.id, now))
  const shape = seed.shape ? shapeRecord(seed.shape, project.id, now) : null
  const seedPmArtifacts = (seed.pm_artifacts ?? []).map((artifact: any) => artifactRecord(artifact, project.id, now))
  const staticPmArtifacts = loadStaticPmArtifacts(seed, project.id, now)
  const staticArtifactByType = (artifactType: string) =>
    staticPmArtifacts.find((artifact) => (artifact.data as Record<string, any> | undefined)?.artifact_type === artifactType) ?? null
  const productDesignHash = contentHash({
    requirements: requirements.data,
    scenarios: scenarios.map((scenario) => scenario.data),
    shape: shape?.data ?? null,
    pm_artifacts: seedPmArtifacts.map((artifact) => artifact.data),
  })
  const scenarioSetHash = contentHash(scenarios.map((scenario) => `${scenario.id}:${scenario.content_hash}`))
  const baselineLockedAt = '2026-04-27T00:00:00Z'
  const generatedBaseline: DeveloperBaselineData = {
    artifact_type: 'developer_baseline',
    source_inputs: {
      product_revision_artifact_id: 'req-gtm-revenue-operations-business-spec',
      product_revision_number: 2,
      product_design_hash: productDesignHash,
      requirements_id: requirements.id,
      requirements_hash: requirements.content_hash,
      scenario_ids: scenarios.map((scenario) => scenario.id),
      primary_scenario_id: scenarios[0]?.id ?? null,
      scenario_set_hash: scenarioSetHash,
      shape_id: shape?.id ?? null,
      shape_hash: shape?.content_hash ?? null,
    },
    locked_at: baselineLockedAt,
    note: 'Seed-derived baseline for the v0.24 GTM Registry package.',
  }
  const baselineArtifact = staticArtifactByType('developer_baseline')
  const baseline = (baselineArtifact?.data as DeveloperBaselineData | undefined) ?? generatedBaseline
  const traceabilityArtifact = staticArtifactByType('design_traceability')
  const developerDefinitionArtifact =
    staticArtifactByType('developer_definition_revision')
    ?? staticArtifactByType('developer_definition')
  const productRevisionArtifact = staticArtifactByType('product_design_revision')
  const staticProductRevision = productRevisionArtifact?.data as Record<string, any> | undefined
  const pmArtifacts = [
    ...seedPmArtifacts,
    ...staticPmArtifacts.filter((artifact) => {
      const artifactType = (artifact.data as Record<string, any> | undefined)?.artifact_type
      return artifactType === 'product_design_revision'
    }),
  ]
  return {
    project,
    requirements,
    scenarios,
    shape,
    pmArtifacts,
    baseline,
    baselineLockedAt: baseline.locked_at ?? baselineLockedAt,
    traceabilityArtifact,
    developerDefinitionArtifact,
    sourceDocuments: [],
    sourceDeclaredIdentity: extractSourceDeclaredIdentity(
      (seed.project_documents ?? [])
        .map((document: any) => String(document.content ?? ''))
        .join('\n\n'),
    ),
    productRevisionRef: staticProductRevision?.revision_artifact_id
      ? `${staticProductRevision.revision_artifact_id}@r${staticProductRevision.revision_number ?? 1}`
      : 'seed:gtm-revenue-operations-business-spec:v2',
    developerRevisionRefPrefix: `studio:${project.id}:developer-definition`,
  }
}

function loadStaticPmArtifacts(seed: any, projectId: string, now: string): ArtifactRecord[] {
  const sourcePath = typeof seed.static_pm_artifacts_path === 'string'
    ? seed.static_pm_artifacts_path.trim()
    : ''
  if (!sourcePath) return []
  const filePath = path.join(repoRoot, sourcePath)
  if (!fs.existsSync(filePath)) return []
  const payload = JSON.parse(fs.readFileSync(filePath, 'utf8')) as unknown
  if (!Array.isArray(payload)) {
    throw new Error(`Static PM artifact file must contain a list: ${sourcePath}`)
  }
  return payload.map((artifact: any) => artifactRecord(artifact, projectId, now))
}

async function loadStudioProjectSource(args: Args): Promise<PackageSource> {
  if (!args.projectId) throw new Error('--project-id is required for Studio project loading')
  const apiBase = args.studioApiBase.replace(/\/$/, '')
  const [project, requirementsRows, scenarioRows, shapeRows, pmArtifactRows, documentRows] = await Promise.all([
    fetchJson<ProjectDetail>(`${apiBase}/api/projects/${encodeURIComponent(args.projectId)}`),
    fetchJson<RequirementsRecord[]>(`${apiBase}/api/projects/${encodeURIComponent(args.projectId)}/requirements`),
    fetchJson<ArtifactRecord[]>(`${apiBase}/api/projects/${encodeURIComponent(args.projectId)}/scenarios`),
    fetchJson<ShapeRecord[]>(`${apiBase}/api/projects/${encodeURIComponent(args.projectId)}/shapes`),
    fetchJson<ArtifactRecord[]>(`${apiBase}/api/projects/${encodeURIComponent(args.projectId)}/pm-artifacts`),
    fetchJson<ProjectDocumentRecord[]>(`${apiBase}/api/projects/${encodeURIComponent(args.projectId)}/documents`),
  ])
  const baselineArtifact = pmArtifactRows.find((artifact) =>
    (artifact.data as Record<string, any> | undefined)?.artifact_type === 'developer_baseline',
  )
  if (!baselineArtifact) throw new Error(`Project ${args.projectId} has no locked Developer baseline artifact.`)
  const baseline = baselineArtifact.data as DeveloperBaselineData
  const sourceInputs = (baseline.source_inputs ?? {}) as Record<string, any>
  const requirements = requirementsRows.find((row) => row.id === sourceInputs.requirements_id)
    ?? requirementsRows.find((row) => row.role === 'primary')
    ?? requirementsRows[0]
  if (!requirements) throw new Error(`Project ${args.projectId} has no requirements artifact.`)
  const scenarioIds = Array.isArray(sourceInputs.scenario_ids)
    ? sourceInputs.scenario_ids.map((value) => String(value)).filter(Boolean)
    : []
  const scenarioById = new Map(scenarioRows.map((scenario) => [scenario.id, scenario]))
  const baselineScenarios = scenarioIds.length
    ? scenarioIds.map((id) => scenarioById.get(id)).filter((scenario): scenario is ArtifactRecord => Boolean(scenario))
    : scenarioRows
  const scenarios = baselineScenarios.length ? baselineScenarios : scenarioRows
  const shape = shapeRows.find((row) => row.id === sourceInputs.shape_id) ?? shapeRows[0] ?? null
  const traceabilityArtifact = pmArtifactRows.find((artifact) =>
    (artifact.data as Record<string, any> | undefined)?.artifact_type === 'design_traceability',
  ) ?? null
  const developerDefinitionArtifact = findLatestDeveloperDefinitionRevisionArtifact(pmArtifactRows)
    ?? findDeveloperDefinitionArtifact(pmArtifactRows)
  const documentPreviews = await Promise.allSettled(documentRows.map((document) =>
    fetchJson<{ content: string }>(
      `${apiBase}/api/projects/${encodeURIComponent(args.projectId)}/documents/${encodeURIComponent(document.id)}/preview`,
    ),
  ))
  const sourceDocuments: PackageSourceDocument[] = documentRows.map((document, index) => ({
    ...document,
    content: documentPreviews[index]?.status === 'fulfilled' ? documentPreviews[index].value.content : '',
  }))
  const sourceDeclaredIdentity = extractSourceDeclaredIdentity(
    sourceDocuments
      .map((document) => document.content ?? '')
      .join('\n\n'),
  )

  return {
    project,
    requirements,
    scenarios,
    shape,
    pmArtifacts: primaryProductArtifacts(pmArtifactRows),
    baseline,
    baselineLockedAt: baseline.locked_at,
    traceabilityArtifact,
    developerDefinitionArtifact,
    sourceDocuments,
    sourceDeclaredIdentity,
    productRevisionRef: resolveRevisionRef(sourceInputs, `baseline:${baseline.locked_at}`),
    developerRevisionRefPrefix: `studio:${project.id}:developer-definition`,
  }
}

function extractSourceDeclaredIdentity(sourceText: string): SourceDeclaredIdentity {
  const codeSpans = Array.from(sourceText.matchAll(/`([^`]+)`/g)).map((match) => match[1].trim())
  const capabilityIds = uniqueStrings(codeSpans.filter((value) =>
    /^[a-z][a-z0-9]*(?:[._][a-z0-9]+)+$/i.test(value)
    && value.includes('.')
    && !/\.(md|json|ya?ml)$/i.test(value),
  ))
  const serviceIds = uniqueStrings(codeSpans.filter((value) =>
    /^[a-z][a-z0-9]*(?:-[a-z0-9]+)+$/i.test(value)
    && /\bservice\b/i.test(value.replace(/-/g, ' '))
    && !/\.(md|json|ya?ml)$/i.test(value),
  ))
  return { capabilityIds, serviceIds }
}

function uniqueStrings(values: string[]): string[] {
  const seen = new Set<string>()
  const result: string[] = []
  for (const value of values) {
    const trimmed = value.trim()
    if (!trimmed || seen.has(trimmed)) continue
    seen.add(trimmed)
    result.push(trimmed)
  }
  return result
}

function assertSourceDeclaredIdentityPreserved(args: Args, source: PackageSource, definition: DeveloperDefinitionData) {
  if (args.allowSourceIdDrift) return
  const declaredCapabilityIds = source.sourceDeclaredIdentity.capabilityIds
  const declaredServiceIds = source.sourceDeclaredIdentity.serviceIds
  if (declaredCapabilityIds.length === 0 && declaredServiceIds.length === 0) return

  const generatedCapabilityIds = new Set((definition.capability_formalizations ?? []).map((capability) => capability.capability_id))
  const generatedServiceIds = new Set((definition.service_topology_bindings ?? []).map((service) => service.service_id))
  const missingCapabilityIds = declaredCapabilityIds.filter((id) => !generatedCapabilityIds.has(id))
  const missingServiceIds = declaredServiceIds.filter((id) => !generatedServiceIds.has(id))
  if (missingCapabilityIds.length === 0 && missingServiceIds.length === 0) return

  const details = [
    missingServiceIds.length ? `missing source-declared service ids: ${missingServiceIds.slice(0, 12).join(', ')}` : '',
    missingCapabilityIds.length ? `missing source-declared capability ids: ${missingCapabilityIds.slice(0, 20).join(', ')}` : '',
  ].filter(Boolean).join('; ')
  throw new Error(
    `Source-declared contract identity drift detected (${details}). `
    + 'Preserve these IDs in Developer Definition, remove/defer them in reviewed source design, or rerun with --allow-source-id-drift for an intentional breaking rename.',
  )
}

async function persistReadiness(args: Args, traceabilityArtifact: ArtifactRecord | null, traceability: Record<string, any>) {
  if (!args.persistReadiness || !args.projectId) return
  if (!traceabilityArtifact) throw new Error(`Project ${args.projectId} has no traceability artifact to persist readiness into.`)
  const apiBase = args.studioApiBase.replace(/\/$/, '')
  await fetchJson(`${apiBase}/api/projects/${encodeURIComponent(args.projectId)}/pm-artifacts/${encodeURIComponent(traceabilityArtifact.id)}`, {
    method: 'PUT',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      data: {
        ...(traceabilityArtifact.data as Record<string, any>),
        agent_consumption_readiness: traceability.agent_consumption_readiness,
      },
    }),
  })
}

async function buildPackageArtifacts(args: Args) {
  const source = args.projectId ? await loadStudioProjectSource(args) : buildSeedSource(args)
  const now = new Date().toISOString()
  const {
    project,
    requirements,
    scenarios,
    shape,
    pmArtifacts,
    baseline,
    baselineLockedAt,
    productRevisionRef,
    developerRevisionRefPrefix,
  } = source
  const traceability = buildTraceabilityRecord({
    pmArtifacts,
    requirements,
    scenarios,
    primaryScenarioId: scenarios[0]?.id ?? null,
    shape,
    baselineLockedAt,
    existing: (source.traceabilityArtifact?.data as any) ?? null,
  })
  const fallbackSavedRevision = {
    revision_number: args.projectId ? 1 : 2,
    revision_artifact_id: `${developerRevisionRefPrefix}:r${args.projectId ? 1 : 2}`,
    previous_revision_artifact_id: args.projectId ? null : `${developerRevisionRefPrefix}:r1`,
    saved_at: now,
  }
  const savedDefinition = source.developerDefinitionArtifact?.data as DeveloperDefinitionData | undefined
  const definition = savedDefinition
    ? JSON.parse(JSON.stringify(savedDefinition)) as DeveloperDefinitionData
    : buildDeveloperDefinitionData({
        project,
        baseline,
        requirements,
        scenarios,
        shape,
        pmArtifacts,
      })
  const savedRevision = definition.saved_revision ?? fallbackSavedRevision
  definition.saved_revision = savedRevision
  definition.saved_at = definition.saved_at ?? now
  const validationIssues = validateDeveloperDefinitionRequiredFields(definition)
  if (validationIssues.length > 0) {
    const details = validationIssues
      .slice(0, 20)
      .map((issue) => `${issue.path}: ${issue.message}`)
      .join('\n')
    throw new Error(
      `Developer Definition is not package-ready; ${validationIssues.length} validation issue(s) remain.\n${details}`,
    )
  }
  assertSourceDeclaredIdentityPreserved(args, source, definition)

  const baseContract = buildDeveloperDefinitionContract({
    project,
    baseline,
    requirements,
    scenarios,
    shape,
    traceability,
    developerDefinition: definition,
  }) as Record<string, any>
  const signature = sha256Digest(contractIdentityPayload(baseContract))
  const identity: DeveloperCompiledContractIdentity = {
    artifact_name: `${project.id}-developer-definition.json`,
    canonical_format: 'stable-json-v1',
    signature_algorithm: 'sha256',
    signature,
    generated_at: now,
  }
  definition.compiled_contract_identity = identity
  const readiness = applyReadinessFindingReviews(
    analyzeAgentConsumptionReadiness(definition),
    normalizeReadinessFindingReviews((source.traceabilityArtifact?.data as any)?.agent_consumption_readiness?.finding_reviews),
  )
  const consumability = buildAgentConsumabilityMetadata({
    definition,
    readiness,
    manualReviews: reviewedAgentConsumabilityRules(source),
  })
  traceability.agent_consumption_readiness = JSON.parse(JSON.stringify(readiness))
  await persistReadiness(args, source.traceabilityArtifact, traceability as Record<string, any>)

  const serviceDefinition = {
    ...baseContract,
    compiled_contract_identity: {
      ...identity,
      revision_number: savedRevision.revision_number,
      revision_artifact_id: savedRevision.revision_artifact_id,
      previous_revision_artifact_id: savedRevision.previous_revision_artifact_id,
      requirements_hash: definition.source_inputs.requirements_hash,
      scenario_set_hash: definition.source_inputs.scenario_set_hash,
      service_design_hash: definition.source_inputs.shape_hash,
      baseline_locked_at: definition.source_inputs.baseline_locked_at,
      developer_definition_saved_at: definition.saved_at,
    },
  }

  const runtimeTarget = buildGeneratedRuntimeTarget(definition)
  const extensionManifestEntries = buildExtensionManifest(definition)
  const adapterBindings = buildIntegrationAdapterBindings(definition)
  const conformanceReport = buildLocalConformanceReport({
    definition,
    runtimeTarget,
    extensionManifest: extensionManifestEntries,
    generatedOutputKinds: buildGeneratedStructureSummary(definition).generated_output_kinds,
    generatedAt: now,
  })
  const serviceIds = serviceDefinition.service_topology_bindings.map((service: any) => service.service_id)
  const capabilityIds = serviceDefinition.capability_formalizations.map((capability: any) => capability.capability_id)
  const packageId = args.packageId || project.id
  const lineage = {
    project_ref: `studio:${project.id}`,
    product_revision: {
      ref: productRevisionRef,
      artifact_id: baseline.source_inputs.product_revision_artifact_id ?? requirements.id,
      revision_number: baseline.source_inputs.product_revision_number ?? null,
      baseline_locked_at: baseline.locked_at,
    },
    developer_revision: {
      ref: savedRevision.revision_artifact_id,
      artifact_id: savedRevision.revision_artifact_id,
      revision_number: savedRevision.revision_number,
      contract_signature: signature,
    },
  }
  const manifest = {
    package_kind: 'anip_service_blueprint',
    artifact_type: 'anip_package_manifest',
    blueprint_id: packageId,
    package_id: packageId,
    name: `${project.name} Service Blueprint`,
    version: args.packageVersion,
    package_version: args.packageVersion,
    schema_version: serviceDefinition.contract_schema_version ?? 'anip-service-definition/v1',
    anip_spec_version: STUDIO_PROTOCOL_VERSION,
    publisher: {
      id: 'local-studio',
      display_name: 'Local Studio Export',
    },
    service_definition: 'anip-service-definition.json',
    service_definition_digest: signature,
    service_definition_digest_algorithm: 'sha256',
    build_packs: {
      recommended: ['anip-build-pack@local'],
    },
    verifier_packs: {
      recommended: ['anip-verifier@local'],
    },
    readme: buildPackageReadme(source, packageId, args.packageVersion, capabilityIds, serviceIds),
    usage_commands: buildUsageCommands(packageId, args.packageVersion),
    source_links: buildPackageSourceLinks(source),
    capability_count: capabilityIds.length,
    service_count: serviceIds.length,
    service_ids: serviceIds,
    lineage,
    source: buildManifestSourceSummary(source, productRevisionRef, savedRevision.revision_artifact_id),
    agent_consumption_readiness: readiness,
    agent_consumability: consumability,
    generated_at: now,
  }
  assertKnownEffectsInPayload('service_definition', serviceDefinition)
  assertKnownEffectsInPayload('manifest', manifest)
  const recommendedLock = {
    lock_kind: 'publisher_recommended_lock',
    artifact_type: 'anip_package_lock',
    blueprint_id: packageId,
    blueprint_version: args.packageVersion,
    package_id: packageId,
    package_version: args.packageVersion,
    service_definition_digest: signature,
    schema_version: manifest.schema_version,
    anip_spec_version: STUDIO_PROTOCOL_VERSION,
    build_packs: manifest.build_packs.recommended,
    verifier_packs: manifest.verifier_packs.recommended,
    runtime_packages: [],
    extension_packs: [],
    regression_packs: [],
    selected_service_ids: serviceIds,
    capability_ids: capabilityIds,
    contract_signature: signature,
    lineage,
    agent_consumption_readiness: {
      status: readiness.status,
      score: readiness.score,
      summary: readiness.summary,
    },
    agent_consumability: {
      schema_version: consumability.schema_version,
      capability_count: Object.keys(consumability.capabilities).length,
    },
    generated_at: now,
  }
  assertKnownEffectsInPayload('recommended_lock', recommendedLock)
  const payload = {
    package_id: packageId,
    package_version: args.packageVersion,
    project_ref: `studio:${project.id}`,
    product_revision_ref: productRevisionRef,
    developer_revision_ref: savedRevision.revision_artifact_id,
    contract_signature: signature,
    lineage,
    schema_version: serviceDefinition.contract_schema_version ?? 'anip-service-definition/v1',
    manifest,
    service_definition: serviceDefinition,
    recommended_lock: recommendedLock,
    readme: String(manifest.readme ?? ''),
    source_links: Array.isArray(manifest.source_links) ? manifest.source_links : [],
  }
  const blueprintPackage = {
    package_kind: 'anip_blueprint_package_export',
    generated_at: now,
    files: {
      'manifest.json': manifest,
      'anip-service-definition.json': serviceDefinition,
      'anip.recommended.lock': recommendedLock,
      'metadata/agent-consumability.json': consumability,
      'extensions/extension-manifest.json': {
        manifest_kind: 'anip_extension_manifest',
        service_definition_digest: signature,
        extension_points: extensionManifestEntries,
      },
      'bindings/integration-adapter-bindings.json': {
        binding_kind: 'anip_integration_adapter_bindings',
        service_definition_digest: signature,
        bindings: adapterBindings,
      },
      'verification/conformance-plan.json': {
        plan_kind: 'anip_local_conformance_plan',
        service_definition_digest: signature,
        required_checks: [
          'schema_valid',
          'dependencies_resolved',
          'generated',
          'extension_hooks_bound',
          'runtime_surface_valid',
          'contract_evidence_aligned',
        ],
      },
      'verification/anip-conformance-report.json': conformanceReport,
    },
  }

  return { payload, serviceDefinition, manifest, recommendedLock, blueprintPackage, lineage, readiness, consumability }
}

async function publishPackage(args: Args, payload: any) {
  const token = process.env.ANIP_REGISTRY_PUBLISH_TOKEN || process.env.STUDIO_REGISTRY_PUBLISH_TOKEN || ''
  const headers: Record<string, string> = { 'content-type': 'application/json' }
  if (token) {
    headers.authorization = `Bearer ${token}`
  }
  if (args.publishViaStudio) {
    const response = await fetch(`${args.studioApiBase.replace(/\/$/, '')}/api/registry/publications`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload),
    })
    const body = await response.json().catch(() => ({}))
    if (response.status === 409) {
      return lookupPublishedPackage(args.registryUrl, payload)
    }
    if (!response.ok) {
      throw new Error(`Studio Registry publish failed (${response.status}): ${JSON.stringify(body)}`)
    }
    const keyPayload = await fetch(`${args.registryUrl.replace(/\/$/, '')}/registry-api/v1/keys`).then((response) =>
      response.ok ? response.json() : { items: [] },
    ).catch(() => ({ items: [] }))
    return { ...body, registry_keys: keyPayload.items ?? [] }
  }
  const apiBase = `${args.registryUrl.replace(/\/$/, '')}/registry-api/v1`
  const response = await fetch(`${apiBase}/publications`, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  })
  const body = await response.json().catch(() => ({}))
  if (response.status === 409) {
    return lookupPublishedPackage(args.registryUrl, payload)
  }
  if (!response.ok) {
    throw new Error(`Registry publish failed (${response.status}): ${JSON.stringify(body)}`)
  }
  const keysResponse = await fetch(`${apiBase}/keys`)
  const keyPayload = keysResponse.ok ? await keysResponse.json() : { items: [] }
  return { ...body, registry_keys: keyPayload.items ?? [] }
}

async function lookupPublishedPackage(registryUrl: string, payload: any) {
  const apiBase = `${registryUrl.replace(/\/$/, '')}/registry-api/v1`
  const [packageResponse, receiptResponse, keysResponse] = await Promise.all([
    fetch(`${apiBase}/packages/${encodeURIComponent(payload.package_id)}/${encodeURIComponent(payload.package_version)}`),
    fetch(`${apiBase}/packages/${encodeURIComponent(payload.package_id)}/${encodeURIComponent(payload.package_version)}/receipt`),
    fetch(`${apiBase}/keys`),
  ])
  if (!packageResponse.ok || !receiptResponse.ok || !keysResponse.ok) {
    throw new Error(`Registry package already exists, but existing package lookup failed (${packageResponse.status}/${receiptResponse.status}/${keysResponse.status})`)
  }
  const packageRecord = await packageResponse.json()
  const receipt = await receiptResponse.json()
  const keyPayload = await keysResponse.json()
  return {
    publication: {
      package_id: packageRecord.package_id,
      package_version: packageRecord.package_version,
      project_ref: packageRecord.project_ref,
      product_revision_ref: packageRecord.product_revision_ref,
      developer_revision_ref: packageRecord.developer_revision_ref,
      contract_signature: packageRecord.contract_signature,
      publisher_id: packageRecord.publisher_id,
      publisher_type: packageRecord.publisher_type,
      lineage: packageRecord.lineage,
      published_at: packageRecord.published_at,
    },
    package: packageRecord,
    receipt,
    registry_keys: keyPayload.items ?? [],
  }
}

async function main() {
  const args = parseArgs()
  fs.mkdirSync(args.outputDir, { recursive: true })
  const artifacts = await buildPackageArtifacts(args)
  const base = path.join(args.outputDir, `${artifacts.payload.package_id}-${args.packageVersion}`)
  writeJson(`${base}-service-definition.json`, artifacts.serviceDefinition)
  writeJson(`${base}-manifest.json`, artifacts.manifest)
  writeJson(`${base}-lock.json`, artifacts.recommendedLock)
  writeJson(`${base}-publish-request.json`, artifacts.payload)
  writeJson(`${base}-blueprint-package.json`, artifacts.blueprintPackage)

  if (!args.publish) {
    const localDefinitionDigest = sha256Digest(artifacts.serviceDefinition)
    const localIssuedAt = artifacts.payload.manifest.generated_at
    const localReceiptSignature = sha256Digest({
      package_id: artifacts.payload.package_id,
      package_version: artifacts.payload.package_version,
      contract_signature: artifacts.payload.contract_signature,
      definition_digest: localDefinitionDigest,
      manifest_digest: sha256Digest(artifacts.manifest),
      issued_at: localIssuedAt,
      authority: 'local-studio',
      lineage: artifacts.lineage,
    })
    const localBundle = {
      bundle_schema_version: 'anip-package-bundle/v1',
      authority: 'local-studio',
      publication: {
        package_id: artifacts.payload.package_id,
        package_version: artifacts.payload.package_version,
        project_ref: artifacts.payload.project_ref,
        product_revision_ref: artifacts.payload.product_revision_ref,
        developer_revision_ref: artifacts.payload.developer_revision_ref,
        contract_signature: artifacts.payload.contract_signature,
        publisher_id: 'local-studio',
        publisher_type: 'local',
        lineage: artifacts.lineage,
        published_at: artifacts.payload.manifest.generated_at,
      },
      package: {
        package_id: artifacts.payload.package_id,
        package_version: artifacts.payload.package_version,
        contract_signature: artifacts.payload.contract_signature,
        publisher_id: 'local-studio',
        publisher_type: 'local',
        lineage: artifacts.lineage,
        schema_version: artifacts.payload.schema_version,
        manifest_digest: sha256Digest(artifacts.manifest),
        definition_digest: localDefinitionDigest,
        lock_digest: sha256Digest(artifacts.recommendedLock),
        manifest: artifacts.manifest,
        service_definition: artifacts.serviceDefinition,
        recommended_lock: artifacts.recommendedLock,
      },
      receipt: {
        registry_signature: localReceiptSignature,
        issued_at: localIssuedAt,
        authority: 'local-studio',
      },
      lineage: artifacts.lineage,
      manifest: artifacts.manifest,
      service_definition: artifacts.serviceDefinition,
      lock: artifacts.recommendedLock,
      registry_keys: [],
      digests: {
        manifest: sha256Digest(artifacts.manifest),
        service_definition: localDefinitionDigest,
        lock: sha256Digest(artifacts.recommendedLock),
        receipt: localReceiptSignature,
      },
    }
    writeJson(`${base}.anip-package.json`, localBundle)
  } else {
    const result = await publishPackage(args, artifacts.payload)
    const bundle = {
      bundle_schema_version: 'anip-package-bundle/v1',
      authority: 'remote-registry',
      publication: result.publication,
      package: result.package,
      receipt: {
        ...result.receipt,
        authority: 'remote-registry',
      },
      lineage: result.package?.lineage ?? artifacts.lineage,
      manifest: result.package?.manifest ?? artifacts.manifest,
      service_definition: result.package?.service_definition ?? artifacts.serviceDefinition,
      lock: result.package?.recommended_lock ?? artifacts.recommendedLock,
      registry_keys: result.registry_keys ?? [],
      digests: {
        manifest: result.package?.manifest_digest,
        service_definition: result.package?.definition_digest,
        lock: result.package?.lock_digest,
        receipt: result.receipt?.registry_signature,
      },
    }
    writeJson(`${base}.anip-package.json`, bundle)
  }

  const composed = artifacts.serviceDefinition.capability_formalizations
    .filter((capability: any) => capability.kind === 'composed')
    .map((capability: any) => capability.capability_id)
  console.log(JSON.stringify({
    package_id: artifacts.payload.package_id,
    package_version: artifacts.payload.package_version,
    capability_count: artifacts.serviceDefinition.capability_formalizations.length,
    service_count: artifacts.serviceDefinition.service_topology_bindings.length,
    readiness: {
      status: artifacts.readiness.status,
      score: artifacts.readiness.score,
      summary: artifacts.readiness.summary,
    },
    composed,
    output_base: base,
    published: args.publish,
  }, null, 2))
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error))
  process.exit(1)
})
