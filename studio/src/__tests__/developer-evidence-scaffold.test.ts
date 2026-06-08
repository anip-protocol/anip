import { describe, expect, it } from 'vitest'
import { buildDeveloperEvidenceScaffoldFiles } from '../design/developer-evidence-scaffold'
import type { ArtifactRecord, ShapeRecord } from '../design/project-types'

function artifact(data: Record<string, any>): ArtifactRecord {
  return {
    id: 'artifact-1',
    project_id: 'project-1',
    title: 'Artifact',
    status: 'frozen',
    data,
    content_hash: 'hash',
    created_at: '2026-05-27T00:00:00.000Z',
    updated_at: '2026-05-27T00:00:00.000Z',
  }
}

describe('developer evidence scaffold', () => {
  it('builds governance and input-contract worksheets from locked service shape capabilities', () => {
    const shape = artifact({
      shape: {
        services: [
          {
            id: 'pipeline-service',
            name: 'Pipeline Service',
            role: 'Returns bounded pipeline summaries.',
            capabilities: ['demo.pipeline_summary', 'demo.prepare_followup'],
          },
        ],
      },
    }) as ShapeRecord

    const files = buildDeveloperEvidenceScaffoldFiles({
      projectId: 'Demo Project',
      shape,
      pmArtifacts: [
        artifact({
          artifact_type: 'product_design_revision',
          revision_number: 3,
          revision_artifact_id: 'demo-product-r3',
          product_design_hash: 'design-hash-123',
        }),
      ],
      generatedAt: '2026-05-27T00:00:00.000Z',
    })

    expect(files.map((file) => file.filename)).toEqual([
      'demo-project-developer-evidence-readme.md',
      'demo-project-developer-evidence-manifest.json',
      'demo-project-capability-runtime-governance.todo.csv',
      'demo-project-capability-input-contracts.todo.csv',
      'demo-project-capability-composition.todo.csv',
    ])
    expect(files[0].content).toContain('# Developer Evidence Worksheets')
    expect(files[0].content).toContain('Recommended AI Assistant Prompt')
    expect(files[0].content).toContain('needs_developer_input=true')
    expect(files[0].content).toContain('provider owns the derivation internally')
    expect(files[0].content).toContain('keep the capability atomic')
    expect(files[0].content).toContain('demo-project-capability-runtime-governance.todo.csv')
    const manifest = JSON.parse(files[1].content)
    expect(manifest).toMatchObject({
      artifact_type: 'developer_source_evidence_manifest',
      schema_version: 'anip-studio-developer-evidence/v1',
      project_id: 'Demo Project',
      product_revision_artifact_id: 'demo-product-r3',
      product_revision_number: '3',
      product_design_hash: 'design-hash-123',
      capability_count: 2,
    })
    expect(manifest.files[0]).toMatchObject({
      filename: 'demo-project-developer-evidence-readme.md',
      schema: 'developer-evidence-readme/v1',
    })
    expect(manifest.instructions).toContain('Do not mark provider-owned internal derivation as composition unless the child ANIP steps and mappings can be declared.')
    expect(files[2].content).toContain('project_id,product_revision_artifact_id,product_revision_number,product_design_hash,capability_id,service_id,service_name,kind,operation_type')
    expect(files[2].content).toContain('Demo Project,demo-product-r3,3,design-hash-123,demo.pipeline_summary,pipeline-service,Pipeline Service,,,,,,')
    expect(files[2].content).toContain('true,"Fill operation/side-effect posture')
    expect(files[3].content).toContain('project_id,product_revision_artifact_id,product_revision_number,product_design_hash,capability_id,input_name,input_type,required')
    expect(files[3].content).toContain('Demo Project,demo-product-r3,3,design-hash-123,demo.prepare_followup,,,,,,,,,,,,,,,,true,')
    expect(files[4].content).toContain('project_id,product_revision_artifact_id,product_revision_number,product_design_hash,capability_id,composition_required,authority_boundary')
    expect(files[4].content).toContain('Demo Project,demo-product-r3,3,design-hash-123,demo.pipeline_summary,,,,,,,,,,true,')
  })
})
