import { describe, expect, it } from 'vitest'
import { classifyPublicationLineage } from '../design/publication-lineage'
import type { ArtifactRecord } from '../design/project-types'

function publicationArtifact(overrides: Record<string, any> = {}): ArtifactRecord {
  return {
    id: 'publication-1',
    project_id: 'proj-1',
    title: 'Publication',
    status: 'draft',
    content_hash: 'hash',
    created_at: '2026-04-24T12:00:00Z',
    updated_at: '2026-04-24T12:00:00Z',
    data: {
      artifact_type: 'developer_registry_publication',
      authority: 'local-studio',
      publication: {
        package_id: 'work-item-fronting',
        package_version: '0.1.4',
        published_at: '2026-04-24T12:00:00Z',
      },
      package: {
        package_id: 'work-item-fronting',
        package_version: '0.1.4',
        contract_signature: 'sha256:contract-4',
        lineage: {
          project_ref: 'proj-1',
          product_revision: {
            ref: 'product-revision-2',
            artifact_id: 'product-revision-2',
            revision_number: 2,
          },
          developer_revision: {
            ref: 'developer-revision-4',
            artifact_id: 'developer-revision-4',
            revision_number: 4,
            contract_signature: 'sha256:contract-4',
          },
        },
      },
      receipt: {
        registry_signature: 'sha256:receipt',
        authority: 'local-studio',
      },
      ...overrides,
    },
  }
}

describe('publication lineage classifier', () => {
  it('classifies a publication as current when lineage matches saved revisions', () => {
    const result = classifyPublicationLineage(publicationArtifact(), {
      productRevisionArtifactId: 'product-revision-2',
      productRevisionNumber: 2,
      developerRevisionArtifactId: 'developer-revision-4',
      developerRevisionNumber: 4,
      contractSignature: 'sha256:contract-4',
    })

    expect(result.status).toBe('current')
    expect(result.productLabel).toBe('Product r2')
    expect(result.developerLabel).toBe('Developer r4')
    expect(result.receiptAuthority).toBe('local-studio')
    expect(result.receiptStatus).toBe('present')
  })

  it('surfaces persisted local verification receipt status', () => {
    const result = classifyPublicationLineage(publicationArtifact({
      local_verification: {
        status: 'ok',
        receipt_status: 'verified',
      },
    }), {
      productRevisionArtifactId: 'product-revision-2',
      productRevisionNumber: 2,
      developerRevisionArtifactId: 'developer-revision-4',
      developerRevisionNumber: 4,
      contractSignature: 'sha256:contract-4',
    })

    expect(result.receiptStatus).toBe('verified')
    expect(result.localVerificationStatus).toBe('ok')
  })

  it('classifies older revision lineage as superseded', () => {
    const result = classifyPublicationLineage(publicationArtifact(), {
      productRevisionArtifactId: 'product-revision-3',
      productRevisionNumber: 3,
      developerRevisionArtifactId: 'developer-revision-5',
      developerRevisionNumber: 5,
      contractSignature: 'sha256:contract-4',
    })

    expect(result.status).toBe('superseded')
  })

  it('classifies contract signature differences as mismatch', () => {
    const result = classifyPublicationLineage(publicationArtifact(), {
      productRevisionArtifactId: 'product-revision-2',
      productRevisionNumber: 2,
      developerRevisionArtifactId: 'developer-revision-4',
      developerRevisionNumber: 4,
      contractSignature: 'sha256:contract-5',
    })

    expect(result.status).toBe('mismatch')
  })

  it('classifies missing publication evidence as unpublished', () => {
    const result = classifyPublicationLineage(null, {
      productRevisionArtifactId: 'product-revision-2',
      productRevisionNumber: 2,
      developerRevisionArtifactId: 'developer-revision-4',
      developerRevisionNumber: 4,
      contractSignature: 'sha256:contract-4',
    })

    expect(result.status).toBe('unpublished')
    expect(result.packageLabel).toBe('No publication')
  })
})
