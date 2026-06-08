import { appendProjectAssistantAuditEvent } from './project-api'
import type { ArtifactRecord } from './project-types'
import type { AssistantDraftBundleLane } from './assistant-draft-bundles'

export const ASSISTANT_AUDIT_LOG_ARTIFACT_TYPE = 'assistant_audit_log'

export type AssistantAuditEventType =
  | 'draft_created'
  | 'clarification_answers_saved'
  | 'section_regenerated'
  | 'section_regeneration_failed'
  | 'section_saved'
  | 'draft_discarded'

export interface AssistantAuditRuntimeContext {
  provider?: string | null
  model?: string | null
  base_url?: string | null
}

export interface AssistantAuditEvent {
  id: string
  event_type: AssistantAuditEventType
  lane: AssistantDraftBundleLane
  project_id: string
  created_at: string
  bundle_artifact_id?: string | null
  section_id?: string | null
  section_title?: string | null
  selected_ids?: string[]
  clarification_question_ids?: string[]
  source_document_id?: string | null
  source_document_title?: string | null
  baseline_locked_at?: string | null
  section_count?: number
  draft_mode?: 'ai' | 'deterministic'
  status?: 'ok' | 'failed'
  error?: string | null
  assistant_runtime?: AssistantAuditRuntimeContext
}

export interface AssistantAuditLogData {
  artifact_type: typeof ASSISTANT_AUDIT_LOG_ARTIFACT_TYPE
  events: AssistantAuditEvent[]
  updated_at: string
}

export function findAssistantAuditLogArtifact(artifacts: ArtifactRecord[]): ArtifactRecord | null {
  return artifacts.find((artifact) => artifact.data?.artifact_type === ASSISTANT_AUDIT_LOG_ARTIFACT_TYPE) ?? null
}

export function assistantAuditLogFromArtifact(artifact: ArtifactRecord | null): AssistantAuditLogData | null {
  const data = artifact?.data
  if (!data || data.artifact_type !== ASSISTANT_AUDIT_LOG_ARTIFACT_TYPE) return null
  return {
    artifact_type: ASSISTANT_AUDIT_LOG_ARTIFACT_TYPE,
    events: Array.isArray(data.events) ? data.events as AssistantAuditEvent[] : [],
    updated_at: typeof data.updated_at === 'string' ? data.updated_at : artifact?.updated_at ?? new Date().toISOString(),
  }
}

export async function appendAssistantAuditEvent(args: {
  projectId: string
  event: Omit<AssistantAuditEvent, 'id' | 'project_id' | 'created_at'>
}): Promise<ArtifactRecord> {
  return appendProjectAssistantAuditEvent(args.projectId, args.event)
}
