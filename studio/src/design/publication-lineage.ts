import type { ArtifactRecord } from './project-types'
import type { RegistryRevisionLineage } from './project-api'

export type PublicationLineageStatus = 'current' | 'superseded' | 'mismatch' | 'unpublished'

export interface PublicationLineageContext {
  productRevisionArtifactId?: string | null
  productRevisionNumber?: number | null
  developerRevisionArtifactId?: string | null
  developerRevisionNumber?: number | null
  contractSignature?: string | null
}

export interface PublicationLineageSummary {
  status: PublicationLineageStatus
  label: string
  detail: string
  packageLabel: string
  authority: string
  productLabel: string
  developerLabel: string
  contractSignature: string
  receiptAuthority: string
  receiptSignature: string
  receiptStatus: string
  publishedAt: string | null
  localPublicationId: string | null
  localVerificationStatus: string | null
}

export function findRegistryPublicationArtifacts(pmArtifacts: ArtifactRecord[]): ArtifactRecord[] {
  const artifacts = pmArtifacts.filter((artifact) => artifact.data?.artifact_type === 'developer_registry_publication')
  artifacts.sort((a, b) => new Date(b.updated_at || b.created_at).getTime() - new Date(a.updated_at || a.created_at).getTime())
  return artifacts
}

export function classifyPublicationLineage(
  artifact: ArtifactRecord | null | undefined,
  context: PublicationLineageContext,
): PublicationLineageSummary {
  if (!artifact) {
    return {
      status: 'unpublished',
      label: 'Unpublished',
      detail: 'No local or Registry publication has been recorded for this project yet.',
      packageLabel: 'No publication',
      authority: 'none',
      productLabel: formatRevisionLabel('Product', context.productRevisionArtifactId, context.productRevisionNumber),
      developerLabel: formatRevisionLabel('Developer', context.developerRevisionArtifactId, context.developerRevisionNumber),
      contractSignature: context.contractSignature || 'Not recorded',
      receiptAuthority: 'none',
      receiptSignature: 'Not recorded',
      receiptStatus: 'none',
      publishedAt: null,
      localPublicationId: null,
      localVerificationStatus: null,
    }
  }

  const data = artifact.data ?? {}
  const packageRecord = (data.package ?? {}) as Record<string, any>
  const publication = (data.publication ?? {}) as Record<string, any>
  const lineage = resolveLineage(data, packageRecord)
  const published = (data.published_from_saved_revision ?? {}) as Record<string, any>
  const productArtifactId = stringOrNull(lineage?.product_revision?.artifact_id ?? published.product_revision_artifact_id)
  const productRevisionNumber = numberOrNull(lineage?.product_revision?.revision_number ?? published.product_revision_number)
  const developerArtifactId = stringOrNull(lineage?.developer_revision?.artifact_id ?? published.revision_artifact_id)
  const developerRevisionNumber = numberOrNull(lineage?.developer_revision?.revision_number ?? published.revision_number)
  const packageContractSignature = stringOrNull(packageRecord.contract_signature ?? publication.contract_signature ?? lineage?.developer_revision?.contract_signature)
  const packageLabel = `${String(packageRecord.package_id ?? publication.package_id ?? 'unknown-package')}@${String(packageRecord.package_version ?? publication.package_version ?? 'unknown-version')}`
  const authority = String(data.authority ?? packageRecord.authority ?? 'published')
  const receipt = (data.receipt ?? {}) as Record<string, any>
  const localVerification = (data.local_verification ?? {}) as Record<string, any>
  const promotedVerification = (data.promoted_from_local_publication ?? {}) as Record<string, any>
  const currentContractSignature = stringOrNull(context.contractSignature)

  let status: PublicationLineageStatus = 'current'
  let label = 'Published current revision'
  let detail = 'The latest publication matches the current saved Product and Developer revision lineage.'

  if (!currentContractSignature || !packageContractSignature || currentContractSignature !== packageContractSignature) {
    status = 'mismatch'
    label = 'Published contract mismatch'
    detail = 'The latest publication contract signature does not match the current saved Developer Definition signature.'
  } else if (
    !revisionMatches(productArtifactId, productRevisionNumber, context.productRevisionArtifactId, context.productRevisionNumber)
    || !revisionMatches(developerArtifactId, developerRevisionNumber, context.developerRevisionArtifactId, context.developerRevisionNumber)
  ) {
    status = 'superseded'
    label = 'Published but superseded'
    detail = 'The latest publication targets an older Product or Developer revision than the current saved lineage.'
  }

  return {
    status,
    label,
    detail,
    packageLabel,
    authority,
    productLabel: formatRevisionLabel('Product', productArtifactId, productRevisionNumber),
    developerLabel: formatRevisionLabel('Developer', developerArtifactId, developerRevisionNumber),
    contractSignature: packageContractSignature ?? 'Not recorded',
    receiptAuthority: stringOrNull(receipt.authority) ?? authority,
    receiptSignature: stringOrNull(receipt.registry_signature) ?? 'Not recorded',
    receiptStatus: stringOrNull(localVerification.receipt_status ?? promotedVerification.receipt_status)
      ?? inferReceiptStatus(receipt, authority),
    publishedAt: stringOrNull(publication.published_at ?? packageRecord.published_at ?? artifact.created_at),
    localPublicationId: stringOrNull(data.local_publication_id ?? data.promoted_from_local_publication?.local_publication_id),
    localVerificationStatus: stringOrNull(localVerification.status ?? promotedVerification.verification_status),
  }
}

function resolveLineage(data: Record<string, any>, packageRecord: Record<string, any>): RegistryRevisionLineage | null {
  const lineage = data.lineage ?? packageRecord.lineage ?? packageRecord.manifest?.lineage ?? packageRecord.recommended_lock?.lineage
  return lineage && typeof lineage === 'object' ? lineage as RegistryRevisionLineage : null
}

function revisionMatches(
  publishedArtifactId: string | null,
  publishedRevisionNumber: number | null,
  currentArtifactId: string | null | undefined,
  currentRevisionNumber: number | null | undefined,
): boolean {
  if (publishedArtifactId && currentArtifactId) return publishedArtifactId === currentArtifactId
  if (publishedRevisionNumber != null && currentRevisionNumber != null) return publishedRevisionNumber === currentRevisionNumber
  return !publishedArtifactId && publishedRevisionNumber == null && !currentArtifactId && currentRevisionNumber == null
}

function formatRevisionLabel(kind: string, artifactId: string | null | undefined, revisionNumber: number | null | undefined): string {
  if (revisionNumber != null) return `${kind} r${revisionNumber}`
  return artifactId || `${kind} revision not recorded`
}

function inferReceiptStatus(receipt: Record<string, any>, authority: string): string {
  if (!stringOrNull(receipt.registry_signature)) return 'none'
  if (authority === 'remote-registry' && stringOrNull(receipt.key_id)) return 'signed'
  return 'present'
}

function stringOrNull(value: unknown): string | null {
  const text = typeof value === 'string' ? value.trim() : ''
  return text || null
}

function numberOrNull(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}
