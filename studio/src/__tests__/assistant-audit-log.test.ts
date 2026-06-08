import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  appendAssistantAuditEvent,
  ASSISTANT_AUDIT_LOG_ARTIFACT_TYPE,
  assistantAuditLogFromArtifact,
  findAssistantAuditLogArtifact,
} from '../design/assistant-audit-log'
import type { ArtifactRecord } from '../design/project-types'

const api = vi.hoisted(() => ({
  appendProjectAssistantAuditEvent: vi.fn(),
}))

vi.mock('../design/project-api', async () => {
  const actual = await vi.importActual<typeof import('../design/project-api')>('../design/project-api')
  return {
    ...actual,
    appendProjectAssistantAuditEvent: (...args: any[]) => api.appendProjectAssistantAuditEvent(...args),
  }
})

function artifact(overrides: Partial<ArtifactRecord>): ArtifactRecord {
  return {
    id: 'artifact-1',
    project_id: 'proj-1',
    title: 'Artifact',
    status: 'active',
    data: {},
    content_hash: 'hash',
    created_at: '2026-04-20T00:00:00Z',
    updated_at: '2026-04-20T00:00:00Z',
    ...overrides,
  }
}

describe('assistant-audit-log', () => {
  beforeEach(() => {
    api.appendProjectAssistantAuditEvent.mockReset()
  })

  it('delegates audit appends to the backend append endpoint', async () => {
    api.appendProjectAssistantAuditEvent.mockResolvedValue({ id: 'assistant-audit-log-proj-1' })

    await appendAssistantAuditEvent({
      projectId: 'proj-1',
      event: {
        event_type: 'draft_created',
        lane: 'pm',
        bundle_artifact_id: 'bundle-1',
        section_count: 6,
        assistant_runtime: { provider: 'openai', model: 'gpt-5.4', base_url: null },
      },
    })

    expect(api.appendProjectAssistantAuditEvent).toHaveBeenCalledWith('proj-1', {
      event_type: 'draft_created',
      lane: 'pm',
      bundle_artifact_id: 'bundle-1',
      section_count: 6,
      assistant_runtime: { provider: 'openai', model: 'gpt-5.4', base_url: null },
    })
  })

  it('finds and reads audit log artifacts defensively', () => {
    const audit = artifact({
      id: 'audit-1',
      data: {
        artifact_type: ASSISTANT_AUDIT_LOG_ARTIFACT_TYPE,
        updated_at: '2026-04-20T00:00:00Z',
        events: [],
      },
    })

    expect(findAssistantAuditLogArtifact([artifact({ id: 'other' }), audit])?.id).toBe('audit-1')
    expect(assistantAuditLogFromArtifact(audit)?.artifact_type).toBe(ASSISTANT_AUDIT_LOG_ARTIFACT_TYPE)
  })
})
