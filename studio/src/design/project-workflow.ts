import { buildProjectIssueIndex, type ProjectIssueSummary } from './project-issues'
import type { ArtifactRecord, ProjectDetail, ProjectDocumentRecord, RequirementsRecord, ShapeRecord } from './project-types'

export interface ProjectWorkflowGate {
  ready: boolean
  issue: ProjectIssueSummary | null
  count: number
  messages: string[]
}

export function productDesignGate(params: {
  project: ProjectDetail | null | undefined
  pmArtifacts: ArtifactRecord[]
  requirements: RequirementsRecord[]
  scenarios: ArtifactRecord[]
  documents: ProjectDocumentRecord[]
  shapes: ShapeRecord[]
}): ProjectWorkflowGate {
  const issue = buildProjectIssueIndex(params)['project-product-design'] ?? null
  if (!issue || issue.count === 0) {
    return { ready: true, issue: null, count: 0, messages: [] }
  }
  return {
    ready: false,
    issue,
    count: issue.count,
    messages: issue.messages,
  }
}

export function firstProductDesignGateMessage(gate: ProjectWorkflowGate): string {
  if (gate.ready) return 'Product Design is ready for Developer Design.'
  return gate.messages[0] || `Resolve ${gate.count} Product Design issue${gate.count === 1 ? '' : 's'} before entering Developer Design.`
}
