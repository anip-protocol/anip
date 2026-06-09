import type { ProjectDocumentRecord } from './project-types'
import {
  createIntegrationDiscoveryRecord,
  createPmArtifact,
  createProjectDocument,
  createWorkspaceConnection,
} from './project-api'
import { expandStarterTemplate, getStarterTemplate, type StarterTemplate } from './starter-templates'

type SourceDocumentSeed = {
  id: string
  title: string
  kind: string
  filename: string
  content: string
}

export interface FrontingInitialSetupPlan {
  documents: SourceDocumentSeed[]
  starterTemplateId?: string
}

export interface FrontingInitialSetupInput {
  projectId: string
  projectName: string
  domain?: string
  brief: string
  starterTemplateId?: string
  starterTemplate?: StarterTemplate
  selectedDocumentIdSuffixes?: string[]
}

function slugify(value: string, fallback = 'fronting'): string {
  const slug = value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
  return slug || fallback
}

export function buildFrontingInitialSetupPlan(input: FrontingInitialSetupInput): FrontingInitialSetupPlan {
  const starterTemplate = input.starterTemplate ?? getStarterTemplate(input.starterTemplateId)
  if (starterTemplate) {
    const expanded = expandStarterTemplate(input.projectId, starterTemplate)
    const selectedDocumentIds = input.selectedDocumentIdSuffixes
      ? new Set(input.selectedDocumentIdSuffixes)
      : null
    return {
      starterTemplateId: starterTemplate.id,
      documents: expanded.documents
        .filter((document) => !selectedDocumentIds || selectedDocumentIds.has(document.idSuffix))
        .map((document) => ({
          id: document.id,
          title: document.title,
          kind: document.kind,
          filename: document.filename,
          content: document.kind === 'business_intent'
            ? [
                document.content,
                '',
                '## User-provided project brief',
                input.brief,
              ].join('\n')
            : document.content,
        })),
    }
  }

  const domain = input.domain?.trim()
  const projectSlug = slugify(domain || input.projectName, 'fronting')
  return {
    documents: [
      {
        id: `${input.projectId}-fronting-intent`,
        title: `${input.projectName} fronting intent`,
        kind: 'business_intent',
        filename: `${projectSlug}-fronting-intent.md`,
        content: [
          `# ${input.projectName} Fronting Intent`,
          '',
          input.brief,
          '',
          '## Next review step',
          'Add integration evidence from a real source before contract generation. Use uploaded OpenAPI, GraphQL, MCP schema, API docs, permission matrices, live discovery, or manual operation entry. Studio must not invent backend operations from the project name or domain.',
        ].join('\n'),
      },
    ],
  }
}

function encodeBase64Utf8(value: string): string {
  const bytes = new TextEncoder().encode(value)
  let binary = ''
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte)
  })
  return btoa(binary)
}

export async function createInitialFrontingSetup(
  projectId: string,
  workspaceId: string,
  input: Omit<FrontingInitialSetupInput, 'projectId'>,
): Promise<ProjectDocumentRecord[]> {
  const plan = buildFrontingInitialSetupPlan({ projectId, ...input })
  const starterTemplate = input.starterTemplate ?? getStarterTemplate(input.starterTemplateId)
  const expandedTemplate = starterTemplate ? expandStarterTemplate(projectId, starterTemplate) : null
  const documents: ProjectDocumentRecord[] = []
  for (const document of plan.documents) {
    documents.push(await createProjectDocument(projectId, {
      id: document.id,
      title: document.title,
      kind: document.kind,
      filename: document.filename,
      media_type: 'text/markdown',
      content_base64: encodeBase64Utf8(document.content),
    }))
  }
  if (expandedTemplate) {
    for (const connection of expandedTemplate.connections) {
      await createWorkspaceConnection(workspaceId, connection)
    }
    for (const record of expandedTemplate.discoveryRecords) {
      await createIntegrationDiscoveryRecord(projectId, record)
    }
    for (const mapping of expandedTemplate.capabilityMappings) {
      await createPmArtifact(projectId, {
        id: mapping.data.id,
        title: mapping.title,
        data: mapping.data,
      })
    }
  }
  return documents
}
