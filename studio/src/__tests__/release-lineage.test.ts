import { describe, expect, it } from 'vitest'
import { findReleaseRecordArtifacts, summarizeApprovalLineage } from '../design/release-lineage'
import type { ArtifactRecord } from '../design/project-types'

function artifact(id: string, data: Record<string, any>): ArtifactRecord {
  return {
    id,
    project_id: 'project-1',
    title: id,
    status: 'draft',
    data,
    content_hash: `${id}-hash`,
    created_at: '2026-04-24T10:00:00Z',
    updated_at: '2026-04-24T10:00:00Z',
  }
}

describe('release lineage', () => {
  it('marks approval current when it targets the selected Product and Developer revisions', () => {
    const summary = summarizeApprovalLineage([
      artifact('traceability', {
        artifact_type: 'design_traceability',
        pm_review_status: 'approved',
        pm_reviewed_at: '2026-04-24T10:00:00Z',
        pm_review_product_revision_artifact_id: 'product-r2',
        pm_review_product_revision_number: 2,
        pm_review_definition_revision_artifact_id: 'developer-r5',
        pm_review_definition_revision_number: 5,
        pm_review_contract_signature: 'sha256:contract',
      }),
    ], {
      productRevisionArtifactId: 'product-r2',
      productRevisionNumber: 2,
      developerRevisionArtifactId: 'developer-r5',
      developerRevisionNumber: 5,
      contractSignature: 'sha256:contract',
    })

    expect(summary.status).toBe('current')
    expect(summary.artifactId).toBe('traceability')
  })

  it('marks approval superseded when revision ids move ahead', () => {
    const summary = summarizeApprovalLineage([
      artifact('traceability', {
        artifact_type: 'design_traceability',
        pm_review_status: 'approved',
        pm_review_product_revision_artifact_id: 'product-r1',
        pm_review_product_revision_number: 1,
        pm_review_definition_revision_artifact_id: 'developer-r4',
        pm_review_definition_revision_number: 4,
        pm_review_contract_signature: 'sha256:contract',
      }),
    ], {
      productRevisionArtifactId: 'product-r2',
      productRevisionNumber: 2,
      developerRevisionArtifactId: 'developer-r5',
      developerRevisionNumber: 5,
      contractSignature: 'sha256:contract',
    })

    expect(summary.status).toBe('superseded')
  })

  it('lists release records newest first', () => {
    const releases = findReleaseRecordArtifacts([
      artifact('old-release', {
        artifact_type: 'anip_release_record',
        released_at: '2026-04-23T10:00:00Z',
      }),
      {
        ...artifact('new-release', {
          artifact_type: 'anip_release_record',
          released_at: '2026-04-24T10:00:00Z',
        }),
        updated_at: '2026-04-24T10:00:00Z',
      },
    ])

    expect(releases.map((item) => item.id)).toEqual(['new-release', 'old-release'])
  })
})
