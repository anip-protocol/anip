import type { ArtifactRecord, TraceabilityRecordData } from './project-types'
import { DESIGN_TRACEABILITY_ARTIFACT_TYPE } from './traceability'

export const ANIP_RELEASE_RECORD_ARTIFACT_TYPE = 'anip_release_record'

export type ApprovalLineageStatus = 'current' | 'superseded' | 'mismatch' | 'pending' | 'changes_requested' | 'missing'

export interface RevisionChainContext {
  productRevisionArtifactId?: string | null
  productRevisionNumber?: number | null
  developerRevisionArtifactId?: string | null
  developerRevisionNumber?: number | null
  contractSignature?: string | null
}

export interface ApprovalLineageSummary {
  status: ApprovalLineageStatus
  label: string
  detail: string
  artifactId: string | null
  reviewedAt: string | null
  productLabel: string
  developerLabel: string
  contractSignature: string
}

export interface ReleaseRecordData {
  artifact_type: typeof ANIP_RELEASE_RECORD_ARTIFACT_TYPE
  release_id: string
  released_at: string
  release_status: 'released'
  publication_artifact_id: string
  approval_artifact_id: string
  package_id: string
  package_version: string
  authority: string
  receipt_signature: string
  approved_revision_chain: {
    product_revision_artifact_id: string | null
    product_revision_number: number | null
    developer_revision_artifact_id: string | null
    developer_revision_number: number | null
    contract_signature: string | null
  }
}

export function findPmApprovalArtifact(pmArtifacts: ArtifactRecord[]): ArtifactRecord | null {
  return (
    [...pmArtifacts]
      .filter((artifact) => artifact.data?.artifact_type === DESIGN_TRACEABILITY_ARTIFACT_TYPE)
      .sort((a, b) => new Date(b.updated_at || b.created_at).getTime() - new Date(a.updated_at || a.created_at).getTime())[0]
    ?? null
  )
}

export function summarizeApprovalLineage(
  pmArtifacts: ArtifactRecord[],
  context: RevisionChainContext,
): ApprovalLineageSummary {
  const artifact = findPmApprovalArtifact(pmArtifacts)
  if (!artifact) {
    return missingApproval(context, 'No PM review record exists for this project yet.')
  }

  const data = artifact.data as TraceabilityRecordData
  const status = data.pm_review_status
  const productArtifactId = stringOrNull(data.pm_review_product_revision_artifact_id)
  const productRevisionNumber = numberOrNull(data.pm_review_product_revision_number)
  const developerArtifactId = stringOrNull(data.pm_review_definition_revision_artifact_id)
  const developerRevisionNumber = numberOrNull(data.pm_review_definition_revision_number)
  const approvalSignature = stringOrNull(data.pm_review_contract_signature)
  const base = {
    artifactId: artifact.id,
    reviewedAt: stringOrNull(data.pm_reviewed_at),
    productLabel: formatRevisionLabel('Product', productArtifactId, productRevisionNumber),
    developerLabel: formatRevisionLabel('Developer', developerArtifactId, developerRevisionNumber),
    contractSignature: approvalSignature ?? 'Not recorded',
  }

  if (status === 'changes_requested') {
    return {
      status: 'changes_requested',
      label: 'Changes requested',
      detail: 'PM review requested changes. Remote Registry publication and release should wait for a new approval.',
      ...base,
    }
  }
  if (status !== 'approved') {
    return {
      status: 'pending',
      label: 'Pending PM approval',
      detail: 'PM review exists but is not approved for release lineage yet.',
      ...base,
    }
  }

  const currentSignature = stringOrNull(context.contractSignature)
  if (!currentSignature || !approvalSignature || currentSignature !== approvalSignature) {
    return {
      status: 'mismatch',
      label: 'Approval contract mismatch',
      detail: 'PM approval targets a different contract signature than the current saved Developer revision.',
      ...base,
    }
  }
  if (
    !revisionMatches(productArtifactId, productRevisionNumber, context.productRevisionArtifactId, context.productRevisionNumber)
    || !revisionMatches(developerArtifactId, developerRevisionNumber, context.developerRevisionArtifactId, context.developerRevisionNumber)
  ) {
    return {
      status: 'superseded',
      label: 'Approval superseded',
      detail: 'PM approval targets an older Product or Developer revision than the current saved lineage.',
      ...base,
    }
  }

  return {
    status: 'current',
    label: 'PM approved current lineage',
    detail: 'The current Product and Developer revision chain has PM approval.',
    ...base,
  }
}

export function findReleaseRecordArtifacts(pmArtifacts: ArtifactRecord[]): ArtifactRecord[] {
  const artifacts = pmArtifacts.filter((artifact) => artifact.data?.artifact_type === ANIP_RELEASE_RECORD_ARTIFACT_TYPE)
  artifacts.sort((a, b) =>
    releaseTime(b) - releaseTime(a),
  )
  return artifacts
}

function releaseTime(artifact: ArtifactRecord): number {
  const releasedAt = typeof artifact.data?.released_at === 'string' ? artifact.data.released_at : ''
  return new Date(releasedAt || artifact.updated_at || artifact.created_at).getTime()
}

function missingApproval(context: RevisionChainContext, detail: string): ApprovalLineageSummary {
  return {
    status: 'missing',
    label: 'No PM approval',
    detail,
    artifactId: null,
    reviewedAt: null,
    productLabel: formatRevisionLabel('Product', context.productRevisionArtifactId, context.productRevisionNumber),
    developerLabel: formatRevisionLabel('Developer', context.developerRevisionArtifactId, context.developerRevisionNumber),
    contractSignature: context.contractSignature || 'Not recorded',
  }
}

function revisionMatches(
  approvedArtifactId: string | null,
  approvedRevisionNumber: number | null,
  currentArtifactId: string | null | undefined,
  currentRevisionNumber: number | null | undefined,
): boolean {
  if (approvedArtifactId && currentArtifactId) return approvedArtifactId === currentArtifactId
  if (approvedRevisionNumber != null && currentRevisionNumber != null) return approvedRevisionNumber === currentRevisionNumber
  return !approvedArtifactId && approvedRevisionNumber == null && !currentArtifactId && currentRevisionNumber == null
}

export function formatRevisionLabel(kind: string, artifactId: string | null | undefined, revisionNumber: number | null | undefined): string {
  if (revisionNumber != null) return `${kind} r${revisionNumber}`
  return artifactId || `${kind} revision not recorded`
}

function stringOrNull(value: unknown): string | null {
  const text = typeof value === 'string' ? value.trim() : ''
  return text || null
}

function numberOrNull(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}
