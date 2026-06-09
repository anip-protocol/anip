import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  ASSISTANT_PRODUCT_DRAFT_BUNDLE_ARTIFACT_TYPE,
  bundleFromArtifact,
  findLatestAssistantDraftBundleArtifact,
  persistAssistantDraftBundle,
} from '../design/assistant-draft-bundles'
import type { ArtifactRecord } from '../design/project-types'

const api = vi.hoisted(() => ({
  createPmArtifact: vi.fn(),
  updatePmArtifact: vi.fn(),
}))

vi.mock('../design/project-api', async () => {
  const actual = await vi.importActual<typeof import('../design/project-api')>('../design/project-api')
  return {
    ...actual,
    createPmArtifact: (...args: any[]) => api.createPmArtifact(...args),
    updatePmArtifact: (...args: any[]) => api.updatePmArtifact(...args),
  }
})

function artifact(overrides: Partial<ArtifactRecord>): ArtifactRecord {
  return {
    id: 'artifact-1',
    project_id: 'proj-1',
    title: 'Artifact',
    status: 'draft',
    data: {},
    content_hash: 'hash',
    created_at: '2026-04-20T00:00:00Z',
    updated_at: '2026-04-20T00:00:00Z',
    ...overrides,
  }
}

function bundle() {
  return {
    title: 'Product Design Draft: Revenue Ops',
    summary: 'Review before saving.',
    sourceText: 'Business spec',
    sections: [],
    createdAt: '2026-04-20T00:00:00Z',
  }
}

describe('assistant-draft-bundles', () => {
  beforeEach(() => {
    vi.stubGlobal('crypto', { randomUUID: () => 'uuid-1' })
    api.createPmArtifact.mockReset()
    api.updatePmArtifact.mockReset()
  })

  it('creates a durable assistant bundle artifact for a new draft', async () => {
    api.createPmArtifact.mockResolvedValue({ id: 'assistant-draft-bundle-pm-uuid-1' })

    await persistAssistantDraftBundle({
      projectId: 'proj-1',
      lane: 'pm',
      bundle: bundle(),
      context: {
        source_document_id: 'doc-1',
        source_document_title: 'Business Spec',
        assistant_runtime: { provider: 'openai', model: 'gpt-5.4', base_url: null },
      },
    })

    expect(api.createPmArtifact).toHaveBeenCalledWith('proj-1', expect.objectContaining({
      id: 'assistant-draft-bundle-pm-uuid-1',
      title: 'PM AI Assistant Draft Bundle',
      data: expect.objectContaining({
        artifact_type: ASSISTANT_PRODUCT_DRAFT_BUNDLE_ARTIFACT_TYPE,
        lane: 'pm',
        source_document_id: 'doc-1',
        source_document_title: 'Business Spec',
        assistant_runtime: { provider: 'openai', model: 'gpt-5.4', base_url: null },
      }),
    }))
  })

  it('updates an existing assistant bundle artifact after section acceptance', async () => {
    api.updatePmArtifact.mockResolvedValue({ id: 'bundle-1' })

    await persistAssistantDraftBundle({
      projectId: 'proj-1',
      lane: 'pm',
      bundle: bundle(),
      artifactId: 'bundle-1',
    })

    expect(api.updatePmArtifact).toHaveBeenCalledWith('proj-1', 'bundle-1', expect.objectContaining({
      title: 'PM AI Assistant Draft Bundle',
      status: 'draft',
    }))
  })

  it('loads the latest bundle artifact for a lane', () => {
    const older = artifact({
      id: 'older',
      data: { artifact_type: ASSISTANT_PRODUCT_DRAFT_BUNDLE_ARTIFACT_TYPE, lane: 'pm', bundle: bundle() },
      updated_at: '2026-04-20T00:00:00Z',
    })
    const newer = artifact({
      id: 'newer',
      data: { artifact_type: ASSISTANT_PRODUCT_DRAFT_BUNDLE_ARTIFACT_TYPE, lane: 'pm', bundle: { ...bundle(), title: 'Newer' } },
      updated_at: '2026-04-21T00:00:00Z',
    })

    const found = findLatestAssistantDraftBundleArtifact([older, newer], 'pm')

    expect(found?.id).toBe('newer')
    expect(bundleFromArtifact(found)?.title).toBe('Newer')
  })
})
