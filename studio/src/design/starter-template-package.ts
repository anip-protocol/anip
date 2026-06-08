import {
  type StarterTemplate,
  validateStarterTemplate,
} from './starter-templates'
import { STUDIO_PROTOCOL_VERSION, STUDIO_VERSION } from '../version'

export const STARTER_TEMPLATE_PACKAGE_SCHEMA = 'anip-starter-template-package/v0'

export const STARTER_TEMPLATE_PACKAGE_LIMITS = {
  maxPackageBytes: 2 * 1024 * 1024,
  maxTemplateBytes: 1024 * 1024,
  maxTemplateDocumentBytes: 20 * 1024,
  maxManifestBytes: 128 * 1024,
  maxJsonDepth: 32,
  maxWarnings: 12,
} as const

export interface StarterTemplatePackageManifest {
  schema: 'anip-starter-template-manifest/v0'
  template_id: string
  template_title: string
  template_kind: string
  package_version: string
  anip_spec_version: string
  studio_version: string
  template_digest: string
  counts: {
    documents: number
    connections: number
    discovery_records: number
    capability_mappings: number
  }
}

export interface StarterTemplatePackage {
  schema: typeof STARTER_TEMPLATE_PACKAGE_SCHEMA
  package_kind: 'anip_starter_template'
  package_version: string
  exported_at: string
  exported_by: {
    studio_version: string
    anip_spec_version: string
  }
  source_project: {
    id: string
    name: string
    project_type: string
    domain?: string
  }
  manifest: StarterTemplatePackageManifest
  selection: StarterTemplatePackageManifest['counts']
  warnings: string[]
  template: StarterTemplate
}

function byteLength(value: string): number {
  return new TextEncoder().encode(value).length
}

function canonicalJson(value: unknown): string {
  return JSON.stringify(sortJson(value))
}

function sortJson(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sortJson)
  if (!value || typeof value !== 'object') return value
  const input = value as Record<string, unknown>
  const output: Record<string, unknown> = {}
  Object.keys(input).sort().forEach((key) => {
    output[key] = sortJson(input[key])
  })
  return output
}

export async function sha256Digest(value: unknown): Promise<string> {
  const bytes = new TextEncoder().encode(canonicalJson(value))
  const digest = await crypto.subtle.digest('SHA-256', bytes)
  return `sha256:${Array.from(new Uint8Array(digest)).map((byte) => byte.toString(16).padStart(2, '0')).join('')}`
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function inspectJson(value: unknown, path: string, depth: number, errors: string[]): void {
  if (depth > STARTER_TEMPLATE_PACKAGE_LIMITS.maxJsonDepth) {
    errors.push(`${path} exceeds maximum JSON nesting depth ${STARTER_TEMPLATE_PACKAGE_LIMITS.maxJsonDepth}.`)
    return
  }
  if (Array.isArray(value)) {
    value.forEach((item, index) => inspectJson(item, `${path}[${index}]`, depth + 1, errors))
    return
  }
  if (isRecord(value)) {
    for (const [key, item] of Object.entries(value)) {
      const normalizedKey = key.toLowerCase()
      if (['script', 'scripts', 'postinstall', 'preinstall', 'install', 'command', 'commands'].includes(normalizedKey)) {
        errors.push(`${path}.${key} is not allowed in starter template packages.`)
      }
      inspectJson(item, `${path}.${key}`, depth + 1, errors)
    }
    return
  }
  if (typeof value === 'string') {
    for (const char of value) {
      const code = char.charCodeAt(0)
      if (code < 0x20 && char !== '\n' && char !== '\r' && char !== '\t') {
        errors.push(`${path} contains unsafe control characters.`)
        break
      }
    }
    const lowerPath = path.toLowerCase()
    const trimmed = value.trim().toLowerCase()
    if (
      (lowerPath.includes('content') || lowerPath.includes('payload') || lowerPath.includes('attachment'))
      && (trimmed.startsWith('data:application/octet-stream') || trimmed.startsWith('data:binary'))
    ) {
      errors.push(`${path} contains a suspicious binary payload.`)
    }
  }
}

function packageCounts(template: StarterTemplate): StarterTemplatePackageManifest['counts'] {
  return {
    documents: template.documents.length,
    connections: template.connections.length,
    discovery_records: template.discoveryRecords.length,
    capability_mappings: template.capabilityMappings.length,
  }
}

export async function buildStarterTemplatePackageEnvelope(args: {
  packageVersion?: string
  exportedAt?: string
  sourceProject: StarterTemplatePackage['source_project']
  template: StarterTemplate
  warnings?: string[]
}): Promise<StarterTemplatePackage> {
  const templateDigest = await sha256Digest(args.template)
  const packageVersion = args.packageVersion ?? '0.1.0'
  const manifest: StarterTemplatePackageManifest = {
    schema: 'anip-starter-template-manifest/v0',
    template_id: args.template.id,
    template_title: args.template.title,
    template_kind: args.template.kind,
    package_version: packageVersion,
    anip_spec_version: args.template.anipSpecVersion,
    studio_version: STUDIO_VERSION,
    template_digest: templateDigest,
    counts: packageCounts(args.template),
  }
  const pkg: StarterTemplatePackage = {
    schema: STARTER_TEMPLATE_PACKAGE_SCHEMA,
    package_kind: 'anip_starter_template',
    package_version: packageVersion,
    exported_at: args.exportedAt ?? new Date().toISOString(),
    exported_by: {
      studio_version: STUDIO_VERSION,
      anip_spec_version: STUDIO_PROTOCOL_VERSION,
    },
    source_project: args.sourceProject,
    manifest,
    selection: manifest.counts,
    warnings: args.warnings ?? [],
    template: args.template,
  }
  const errors = await validateStarterTemplatePackage(pkg)
  if (errors.length > 0) {
    throw new Error(`Exported starter template package is invalid: ${errors.join(' ')}`)
  }
  return pkg
}

export async function validateStarterTemplatePackage(value: unknown): Promise<string[]> {
  const errors: string[] = []
  if (!isRecord(value)) return ['Starter template package must be an object.']
  const packageJson = JSON.stringify(value)
  if (byteLength(packageJson) > STARTER_TEMPLATE_PACKAGE_LIMITS.maxPackageBytes) {
    errors.push(`package exceeds ${STARTER_TEMPLATE_PACKAGE_LIMITS.maxPackageBytes} bytes.`)
  }
  inspectJson(value, 'package', 0, errors)
  if (value.schema !== STARTER_TEMPLATE_PACKAGE_SCHEMA) {
    errors.push(`schema must be ${STARTER_TEMPLATE_PACKAGE_SCHEMA}.`)
  }
  if (value.package_kind !== 'anip_starter_template') {
    errors.push('package_kind must be anip_starter_template.')
  }
  if (!isRecord(value.manifest)) {
    errors.push('manifest must be an object.')
  } else if (byteLength(JSON.stringify(value.manifest)) > STARTER_TEMPLATE_PACKAGE_LIMITS.maxManifestBytes) {
    errors.push(`manifest exceeds ${STARTER_TEMPLATE_PACKAGE_LIMITS.maxManifestBytes} bytes.`)
  }
  if (!isRecord(value.template)) {
    errors.push('template must be an object.')
    return errors
  }
  if (byteLength(JSON.stringify(value.template)) > STARTER_TEMPLATE_PACKAGE_LIMITS.maxTemplateBytes) {
    errors.push(`template exceeds ${STARTER_TEMPLATE_PACKAGE_LIMITS.maxTemplateBytes} bytes.`)
  }
  errors.push(...validateStarterTemplate(value.template))
  const templateDocuments = Array.isArray((value.template as Record<string, unknown>).documents)
    ? (value.template as Record<string, unknown>).documents as unknown[]
    : []
  templateDocuments.forEach((document, index) => {
    if (!isRecord(document)) return
    const content = typeof document.content === 'string' ? document.content : ''
    if (byteLength(content) > STARTER_TEMPLATE_PACKAGE_LIMITS.maxTemplateDocumentBytes) {
      errors.push(`template.documents[${index}].content exceeds ${STARTER_TEMPLATE_PACKAGE_LIMITS.maxTemplateDocumentBytes} bytes.`)
    }
  })
  if (Array.isArray(value.warnings) && value.warnings.length > STARTER_TEMPLATE_PACKAGE_LIMITS.maxWarnings) {
    errors.push(`warnings exceeds ${STARTER_TEMPLATE_PACKAGE_LIMITS.maxWarnings} entries.`)
  }
  if (isRecord(value.manifest)) {
    const template = value.template as unknown as StarterTemplate
    const counts = packageCounts(template)
    const manifestCounts = isRecord(value.manifest.counts) ? value.manifest.counts : {}
    for (const [field, count] of Object.entries(counts)) {
      if (manifestCounts[field] !== count) {
        errors.push(`manifest.counts.${field} must match template ${field} count.`)
      }
    }
    const actualDigest = await sha256Digest(value.template)
    if (value.manifest.template_digest !== actualDigest) {
      errors.push('manifest.template_digest must match the canonical template digest.')
    }
    if (value.manifest.anip_spec_version !== template.anipSpecVersion) {
      errors.push('manifest.anip_spec_version must match template.anipSpecVersion.')
    }
    if (value.manifest.anip_spec_version !== STUDIO_PROTOCOL_VERSION) {
      errors.push(`manifest.anip_spec_version must be ${STUDIO_PROTOCOL_VERSION}.`)
    }
    if (value.manifest.template_id !== template.id) {
      errors.push('manifest.template_id must match template.id.')
    }
  }
  return errors
}
