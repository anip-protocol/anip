export type ExternalCliProvenanceStatus = 'aligned' | 'mismatch' | 'incomplete' | 'unpublished'

export interface ExternalCliRevisionRef {
  ref?: string | null
  artifact_id?: string | null
  revision_number?: number | null
  contract_signature?: string | null
}

export interface ExternalCliPublicationContext {
  publicationArtifactId?: string | null
  packageId?: string | null
  packageVersion?: string | null
  productRevision?: ExternalCliRevisionRef | null
  developerRevision?: ExternalCliRevisionRef | null
  receiptSignature?: string | null
}

export interface ExternalCliProvenanceSummary {
  status: ExternalCliProvenanceStatus
  label: string
  detail: string
  sourceTool: 'anip-verify' | 'anip-generate' | 'anip-cli'
  packageLabel: string
  receiptStatus: string
  receiptSignature: string
  registrySigningMode?: string | null
  registryActiveKeyID?: string | null
  registryTrustPostureLabel?: string | null
  registryTrustPostureDetail?: string | null
  productRevisionLabel: string
  developerRevisionLabel: string
  matchedPublicationArtifactId: string | null
}

export function parseExternalCliResult(text: string): Record<string, any> {
  const parsed = JSON.parse(text)
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('CLI result must be a JSON object.')
  }
  if (!stringOrNull(parsed.package_id) || !stringOrNull(parsed.package_version)) {
    throw new Error('CLI result must include package_id and package_version.')
  }
  return parsed as Record<string, any>
}

export function summarizeExternalCliResult(
  result: Record<string, any>,
  context: ExternalCliPublicationContext | null,
): ExternalCliProvenanceSummary {
  const sourceTool = detectSourceTool(result)
  const packageId = stringOrNull(result.package_id)
  const packageVersion = stringOrNull(result.package_version)
  const packageLabel = packageId && packageVersion ? `${packageId}@${packageVersion}` : 'unknown-package'
  const receiptSignature = stringOrNull(result.registry_receipt_signature ?? result.receipt_signature) ?? 'Not recorded'
  const receiptStatus = stringOrNull(result.receipt_status)
    ?? (receiptSignature === 'Not recorded' ? 'none' : 'present')
  const registrySigningMode = stringOrNull(result.registry_signing_mode)
  const registryActiveKeyID = stringOrNull(result.registry_active_key_id)
  const registryTrustPosture = summarizeRegistryTrustPosture(result)
  const productRevision = normalizeRevision(result.product_revision ?? result.lineage?.product_revision)
  const developerRevision = normalizeRevision(result.developer_revision ?? result.lineage?.developer_revision)
  const productRevisionLabel = formatRevisionLabel('Product', productRevision)
  const developerRevisionLabel = formatRevisionLabel('Developer', developerRevision)

  if (!context?.packageId || !context.packageVersion) {
    return {
      status: 'unpublished',
      label: 'No publication to reconcile',
      detail: 'Studio has no local or Registry publication record to compare with this CLI result.',
      sourceTool,
      packageLabel,
      receiptStatus,
      receiptSignature,
      registrySigningMode,
      registryActiveKeyID,
      registryTrustPostureLabel: registryTrustPosture.label,
      registryTrustPostureDetail: registryTrustPosture.detail,
      productRevisionLabel,
      developerRevisionLabel,
      matchedPublicationArtifactId: null,
    }
  }

  const packageMatches = packageId === context.packageId && packageVersion === context.packageVersion
  const productMatches = revisionMatches(productRevision, context.productRevision ?? null)
  const developerMatches = revisionMatches(developerRevision, context.developerRevision ?? null)
  const receiptMatches = receiptSignature === 'Not recorded'
    || !context.receiptSignature
    || receiptSignature === context.receiptSignature
  const cliStatus = stringOrNull(result.status)

  if (cliStatus && !['ok', 'pass', 'passed'].includes(cliStatus)) {
    return mismatch('CLI reported a non-passing status.', sourceTool, packageLabel, receiptStatus, receiptSignature, registrySigningMode, registryActiveKeyID, registryTrustPosture, productRevisionLabel, developerRevisionLabel, context)
  }
  if (!packageMatches) {
    return mismatch(`CLI package ${packageLabel} does not match Studio publication ${context.packageId}@${context.packageVersion}.`, sourceTool, packageLabel, receiptStatus, receiptSignature, registrySigningMode, registryActiveKeyID, registryTrustPosture, productRevisionLabel, developerRevisionLabel, context)
  }
  if (receiptStatus === 'failed') {
    return mismatch('CLI receipt verification failed.', sourceTool, packageLabel, receiptStatus, receiptSignature, registrySigningMode, registryActiveKeyID, registryTrustPosture, productRevisionLabel, developerRevisionLabel, context)
  }
  if (!receiptMatches) {
    return mismatch('CLI receipt signature does not match the Studio publication receipt.', sourceTool, packageLabel, receiptStatus, receiptSignature, registrySigningMode, registryActiveKeyID, registryTrustPosture, productRevisionLabel, developerRevisionLabel, context)
  }
  if (productMatches === false || developerMatches === false) {
    return mismatch('CLI revision lineage does not match the Studio publication lineage.', sourceTool, packageLabel, receiptStatus, receiptSignature, registrySigningMode, registryActiveKeyID, registryTrustPosture, productRevisionLabel, developerRevisionLabel, context)
  }
  if (productMatches === null || developerMatches === null) {
    return {
      status: 'incomplete',
      label: 'CLI provenance incomplete',
      detail: 'Package identity matches, but the CLI result does not include enough Product/Developer revision lineage to prove it is the same publication lineage.',
      sourceTool,
      packageLabel,
      receiptStatus,
      receiptSignature,
      registrySigningMode,
      registryActiveKeyID,
      registryTrustPostureLabel: registryTrustPosture.label,
      registryTrustPostureDetail: registryTrustPosture.detail,
      productRevisionLabel,
      developerRevisionLabel,
      matchedPublicationArtifactId: context.publicationArtifactId ?? null,
    }
  }

  return {
    status: 'aligned',
    label: 'CLI result aligned',
    detail: 'The CLI result matches Studio publication package identity, receipt state, and Product/Developer revision lineage.',
    sourceTool,
    packageLabel,
    receiptStatus,
    receiptSignature,
    registrySigningMode,
    registryActiveKeyID,
    registryTrustPostureLabel: registryTrustPosture.label,
    registryTrustPostureDetail: registryTrustPosture.detail,
    productRevisionLabel,
    developerRevisionLabel,
    matchedPublicationArtifactId: context.publicationArtifactId ?? null,
  }
}

function mismatch(
  detail: string,
  sourceTool: ExternalCliProvenanceSummary['sourceTool'],
  packageLabel: string,
  receiptStatus: string,
  receiptSignature: string,
  registrySigningMode: string | null,
  registryActiveKeyID: string | null,
  registryTrustPosture: { label: string | null, detail: string | null },
  productRevisionLabel: string,
  developerRevisionLabel: string,
  context: ExternalCliPublicationContext,
): ExternalCliProvenanceSummary {
  return {
    status: 'mismatch',
    label: 'CLI result mismatch',
    detail,
    sourceTool,
    packageLabel,
    receiptStatus,
    receiptSignature,
    registrySigningMode,
    registryActiveKeyID,
    registryTrustPostureLabel: registryTrustPosture.label,
    registryTrustPostureDetail: registryTrustPosture.detail,
    productRevisionLabel,
    developerRevisionLabel,
    matchedPublicationArtifactId: context.publicationArtifactId ?? null,
  }
}

function summarizeRegistryTrustPosture(result: Record<string, any>): { label: string | null, detail: string | null } {
  const checks = Array.isArray(result.checks) ? result.checks : []
  const policyFailures = checks
    .filter((check: any) =>
      check
      && typeof check === 'object'
      && typeof check.name === 'string'
      && check.name.startsWith('registry_trust_policy_')
      && check.status === 'fail')
    .map((check: any) => check.name)
  if (policyFailures.length) {
    return {
      label: 'Untrusted / policy mismatch',
      detail: `Registry verifier trust policy failed: ${policyFailures.join(', ')}`,
    }
  }
  const signingMode = stringOrNull(result.registry_signing_mode)?.toLowerCase() ?? null
  const activeKeyID = stringOrNull(result.registry_active_key_id) ?? 'not reported'
  if (signingMode === 'production') {
    return {
      label: 'Trusted production Registry',
      detail: `Registry reports production signing mode with active key ${activeKeyID}.`,
    }
  }
  if (signingMode === 'dev') {
    return {
      label: 'Development Registry',
      detail: `Registry reports development signing mode with active key ${activeKeyID}.`,
    }
  }
  if (signingMode) {
    return {
      label: `${signingMode} Registry`,
      detail: `Registry reports signing mode ${signingMode} with active key ${activeKeyID}.`,
    }
  }
  return { label: null, detail: null }
}

function detectSourceTool(result: Record<string, any>): ExternalCliProvenanceSummary['sourceTool'] {
  if (Array.isArray(result.checks) || result.receipt_status || result.registry_receipt_signature) return 'anip-verify'
  if (result.file_count != null || result.output || result.target) return 'anip-generate'
  return 'anip-cli'
}

function normalizeRevision(value: unknown): ExternalCliRevisionRef | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  const record = value as Record<string, unknown>
  return {
    ref: stringOrNull(record.ref),
    artifact_id: stringOrNull(record.artifact_id),
    revision_number: numberOrNull(record.revision_number),
    contract_signature: stringOrNull(record.contract_signature),
  }
}

function revisionMatches(actual: ExternalCliRevisionRef | null, expected: ExternalCliRevisionRef | null): boolean | null {
  if (!actual || !expected) return null
  if (actual.artifact_id && expected.artifact_id) return actual.artifact_id === expected.artifact_id
  if (actual.ref && expected.ref) return actual.ref === expected.ref
  if (actual.revision_number != null && expected.revision_number != null) return actual.revision_number === expected.revision_number
  return null
}

function formatRevisionLabel(kind: string, revision: ExternalCliRevisionRef | null): string {
  if (!revision) return `${kind} revision not recorded`
  const ref = revision.ref || revision.artifact_id
  if (revision.revision_number != null && ref) return `${kind} r${revision.revision_number} (${ref})`
  if (revision.revision_number != null) return `${kind} r${revision.revision_number}`
  return ref || `${kind} revision not recorded`
}

function stringOrNull(value: unknown): string | null {
  const text = typeof value === 'string' ? value.trim() : ''
  return text || null
}

function numberOrNull(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}
