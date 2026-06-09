import { describe, expect, it } from 'vitest'
import {
  buildProductDesignRevision,
  findLatestProductDesignRevisionArtifact,
  productDesignSourceHash,
} from '../design/product-design'
import {
  buildDeveloperBaseline,
  developerBaselineMatchesCurrentContext,
} from '../design/traceability'
import type { ArtifactRecord, RequirementsRecord, ShapeRecord } from '../design/project-types'

function artifact(overrides: Partial<ArtifactRecord>): ArtifactRecord {
  return {
    id: 'artifact-1',
    project_id: 'project-1',
    title: 'Artifact',
    status: 'draft',
    data: {},
    content_hash: 'hash',
    created_at: '2026-04-24T00:00:00.000Z',
    updated_at: '2026-04-24T00:00:00.000Z',
    ...overrides,
  }
}

const requirements = artifact({
  id: 'requirements-1',
  content_hash: 'requirements-hash',
  data: {},
}) as ArtifactRecord as RequirementsRecord
requirements.role = 'primary'

const scenario = artifact({
  id: 'scenario-1',
  content_hash: 'scenario-hash',
  data: {},
})

const shape = artifact({
  id: 'shape-1',
  content_hash: 'shape-hash',
  data: {},
}) as ArtifactRecord as ShapeRecord
shape.requirements_id = 'requirements-1'

describe('product design revisions', () => {
  it('hashes only PM-owned product design source artifacts', () => {
    const hash = productDesignSourceHash([
      artifact({
        id: 'summary',
        data: { artifact_type: 'product_summary', product_purpose: 'A' },
        content_hash: 'summary-hash',
      }),
      artifact({
        id: 'developer-definition',
        data: { artifact_type: 'developer_definition' },
        content_hash: 'developer-hash',
      }),
    ])

    expect(hash).toBe('product_summary:summary:summary-hash')
  })

  it('creates immutable product revision snapshots with monotonically increasing numbers', () => {
    const first = buildProductDesignRevision({
      projectId: 'project-1',
      savedAt: '2026-04-24T00:00:00.000Z',
      pmArtifacts: [
        artifact({
          id: 'summary',
          title: 'Business Summary',
          data: { artifact_type: 'product_summary', product_purpose: 'A' },
          content_hash: 'summary-hash',
        }),
      ],
    })
    const second = buildProductDesignRevision({
      projectId: 'project-1',
      savedAt: '2026-04-24T00:01:00.000Z',
      pmArtifacts: [
        artifact({
          id: first.revision_artifact_id,
          title: 'Product Design Revision 1',
          data: first,
        }),
        artifact({
          id: 'summary',
          title: 'Business Summary',
          data: { artifact_type: 'product_summary', product_purpose: 'B' },
          content_hash: 'summary-hash-2',
        }),
      ],
    })

    expect(first.revision_number).toBe(1)
    expect(first.revision_artifact_id).toBe('project-1-product-design-revision-1')
    expect(second.revision_number).toBe(2)
    expect(second.previous_revision_artifact_id).toBe(first.revision_artifact_id)
    expect(second.snapshot.map((item) => item.artifact_id)).toEqual(['summary'])
  })

  it('returns the highest product revision as latest', () => {
    const latest = findLatestProductDesignRevisionArtifact([
      artifact({
        id: 'revision-1',
        data: { artifact_type: 'product_design_revision', revision_number: 1 },
      }),
      artifact({
        id: 'revision-3',
        data: { artifact_type: 'product_design_revision', revision_number: 3 },
      }),
      artifact({
        id: 'revision-2',
        data: { artifact_type: 'product_design_revision', revision_number: 2 },
      }),
    ])

    expect(latest?.id).toBe('revision-3')
  })

  it('marks a developer baseline stale when Product Design changes after lock', () => {
    const pmArtifacts = [
      artifact({
        id: 'summary',
        data: { artifact_type: 'product_summary', product_purpose: 'A' },
        content_hash: 'summary-hash',
      }),
    ]
    const productRevision = buildProductDesignRevision({
      projectId: 'project-1',
      pmArtifacts,
      savedAt: '2026-04-24T00:00:00.000Z',
    })
    const baseline = buildDeveloperBaseline({
      requirements,
      scenarios: [scenario],
      shape,
      pmArtifacts,
      productRevision,
      existing: null,
    })
    const changedPmArtifacts = [
      artifact({
        id: productRevision.revision_artifact_id,
        data: productRevision,
      }),
      artifact({
        id: 'summary',
        data: { artifact_type: 'product_summary', product_purpose: 'B' },
        content_hash: 'summary-hash-2',
      }),
    ]

    expect(developerBaselineMatchesCurrentContext({
      baseline,
      requirements,
      scenarios: [scenario],
      shape,
      pmArtifacts: [
        artifact({
          id: productRevision.revision_artifact_id,
          data: productRevision,
        }),
        ...pmArtifacts,
      ],
    })).toBe(true)
    expect(developerBaselineMatchesCurrentContext({
      baseline,
      requirements,
      scenarios: [scenario],
      shape,
      pmArtifacts: changedPmArtifacts,
    })).toBe(false)
  })
})
