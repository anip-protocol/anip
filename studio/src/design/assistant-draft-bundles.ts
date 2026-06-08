import {
  createPmArtifact,
  deletePmArtifact,
  updatePmArtifact,
} from './project-api'
import type { ArtifactRecord, RuntimeStatus } from './project-types'
import type { ProductDesignDraftBundle } from './product-design-draft-bundle'
import type { DeveloperDesignDraftBundle } from './developer-design-draft-bundle'

export type AssistantDraftBundleLane = 'pm' | 'dev'

export const ASSISTANT_PRODUCT_DRAFT_BUNDLE_ARTIFACT_TYPE = 'assistant_product_design_draft_bundle'
export const ASSISTANT_DEVELOPER_DRAFT_BUNDLE_ARTIFACT_TYPE = 'assistant_developer_design_draft_bundle'

export type StoredAssistantDraftBundle = ProductDesignDraftBundle | DeveloperDesignDraftBundle

export interface AssistantDraftBundleStorageContext {
  source_document_id?: string | null
  source_document_title?: string | null
  source_documents?: Array<{
    id: string
    title: string
    kind?: string
    filename?: string
  }>
  baseline_locked_at?: string | null
  assistant_runtime?: {
    provider?: string | null
    model?: string | null
    base_url?: string | null
  }
}

interface AssistantDraftBundleArtifactData {
  artifact_type: string
  lane: AssistantDraftBundleLane
  bundle: StoredAssistantDraftBundle
  created_at: string
  source_document_id?: string | null
  source_document_title?: string | null
  source_documents?: AssistantDraftBundleStorageContext['source_documents']
  baseline_locked_at?: string | null
  assistant_runtime?: AssistantDraftBundleStorageContext['assistant_runtime']
}

function artifactTypeForLane(lane: AssistantDraftBundleLane) {
  return lane === 'pm'
    ? ASSISTANT_PRODUCT_DRAFT_BUNDLE_ARTIFACT_TYPE
    : ASSISTANT_DEVELOPER_DRAFT_BUNDLE_ARTIFACT_TYPE
}

export function assistantRuntimeContext(runtimeStatus: RuntimeStatus | null | undefined) {
  return {
    provider: runtimeStatus?.assistant_provider ?? null,
    model: runtimeStatus?.assistant_model ?? null,
    base_url: runtimeStatus?.assistant_base_url ?? null,
  }
}

export function findLatestAssistantDraftBundleArtifact(
  artifacts: ArtifactRecord[],
  lane: AssistantDraftBundleLane,
): ArtifactRecord | null {
  const artifactType = artifactTypeForLane(lane)
  return [...artifacts]
    .filter((artifact) => artifact.data?.artifact_type === artifactType && artifact.data?.lane === lane)
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())[0] ?? null
}

export function bundleFromArtifact<T extends StoredAssistantDraftBundle>(artifact: ArtifactRecord | null): T | null {
  const bundle = artifact?.data?.bundle
  return bundle && typeof bundle === 'object' ? bundle as T : null
}

export async function persistAssistantDraftBundle(args: {
  projectId: string
  lane: AssistantDraftBundleLane
  bundle: StoredAssistantDraftBundle
  context?: AssistantDraftBundleStorageContext
  artifactId?: string | null
}): Promise<ArtifactRecord> {
  const data: AssistantDraftBundleArtifactData = {
    artifact_type: artifactTypeForLane(args.lane),
    lane: args.lane,
    bundle: args.bundle,
    created_at: args.bundle.createdAt,
    source_document_id: args.context?.source_document_id ?? null,
    source_document_title: args.context?.source_document_title ?? null,
    source_documents: args.context?.source_documents ?? [],
    baseline_locked_at: args.context?.baseline_locked_at ?? null,
    assistant_runtime: args.context?.assistant_runtime,
  }
  const title = args.lane === 'pm' ? 'PM AI Assistant Draft Bundle' : 'Developer AI Assistant Draft Bundle'
  if (args.artifactId) {
    return updatePmArtifact(args.projectId, args.artifactId, {
      title,
      status: 'draft',
      data,
    })
  }
  return createPmArtifact(args.projectId, {
    id: `assistant-draft-bundle-${args.lane}-${crypto.randomUUID()}`,
    title,
    data,
  })
}

export function deleteAssistantDraftBundle(projectId: string, artifactId: string): Promise<void> {
  return deletePmArtifact(projectId, artifactId)
}
