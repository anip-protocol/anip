import { mkdir, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { createHash, webcrypto } from 'node:crypto'

import {
  getProject,
  listPmArtifacts,
  listRequirements,
  listScenarios,
  listShapes,
} from '../src/design/project-api'
import {
  buildDeveloperDefinitionContract,
  DEVELOPER_DEFINITION_ARTIFACT_TYPE,
  DEVELOPER_DEFINITION_REVISION_ARTIFACT_TYPE,
  stableStringify,
} from '../src/design/developer-definition'

const apiBase = process.env.STUDIO_API_BASE || 'http://127.0.0.1:8100'
const projectId = process.argv[2]
const outputPath = process.argv[3]

if (!projectId || !outputPath) {
  throw new Error('Usage: tsx studio/scripts/export-project-service-definition.ts <project-id> <output-path>')
}

if (!globalThis.crypto) {
  Object.defineProperty(globalThis, 'crypto', { value: webcrypto })
}

const nativeFetch = globalThis.fetch.bind(globalThis)
globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) => {
  if (typeof input === 'string' && input.startsWith('/')) {
    return nativeFetch(`${apiBase}${input}`, init)
  }
  return nativeFetch(input, init)
}) as typeof globalThis.fetch

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function contractIdentityPayload(baseContract: Record<string, any>) {
  const payload = clone(baseContract)
  delete payload.generated_at
  delete payload.compiled_contract_identity
  if (payload.source?.developer_definition_revision) {
    payload.source.developer_definition_revision = null
  }
  return payload
}

function sha256Hex(value: string): string {
  return createHash('sha256').update(value).digest('hex')
}

function latestByRevision(artifacts: Array<Record<string, any>>) {
  return artifacts
    .filter((artifact) => artifact.data?.artifact_type === DEVELOPER_DEFINITION_REVISION_ARTIFACT_TYPE)
    .sort((left, right) => {
      const leftRevision = Number(left.data?.saved_revision?.revision_number ?? 0)
      const rightRevision = Number(right.data?.saved_revision?.revision_number ?? 0)
      return rightRevision - leftRevision
    })[0] ?? null
}

async function main() {
  const [project, pmArtifacts, requirements, scenarios, shapes] = await Promise.all([
    getProject(projectId),
    listPmArtifacts(projectId),
    listRequirements(projectId),
    listScenarios(projectId),
    listShapes(projectId),
  ])
  const baseline = pmArtifacts.find((artifact) => artifact.data?.artifact_type === 'developer_baseline')?.data ?? null
  const traceability = pmArtifacts.find((artifact) => artifact.data?.artifact_type === 'design_traceability')?.data ?? null
  const latestRevision = latestByRevision(pmArtifacts as Array<Record<string, any>>)
  const developerDefinition = (
    latestRevision?.data
    ?? pmArtifacts.find((artifact) => artifact.data?.artifact_type === DEVELOPER_DEFINITION_ARTIFACT_TYPE)?.data
    ?? null
  )
  if (!developerDefinition) {
    throw new Error(`Project ${projectId} does not have a saved Developer Definition.`)
  }
  const baseContract = buildDeveloperDefinitionContract({
    project,
    baseline: baseline as any,
    requirements: requirements[0] ?? null,
    scenarios,
    shape: shapes[0] ?? null,
    traceability: traceability as any,
    developerDefinition: developerDefinition as any,
  })
  const canonicalJson = stableStringify(contractIdentityPayload(baseContract))
  const identity = {
    artifact_name: `${project.id}-developer-definition.json`,
    canonical_format: 'stable-json-v1',
    signature_algorithm: 'sha256',
    signature: sha256Hex(canonicalJson),
    generated_at: new Date().toISOString(),
    revision_number: developerDefinition.saved_revision?.revision_number ?? null,
    revision_artifact_id: developerDefinition.saved_revision?.revision_artifact_id ?? null,
    previous_revision_artifact_id: developerDefinition.saved_revision?.previous_revision_artifact_id ?? null,
    requirements_hash: developerDefinition.source_inputs?.requirements_hash ?? null,
    scenario_set_hash: developerDefinition.source_inputs?.scenario_set_hash ?? null,
    service_design_hash: developerDefinition.source_inputs?.shape_hash ?? null,
    baseline_locked_at: developerDefinition.source_inputs?.baseline_locked_at ?? null,
    developer_definition_saved_at: developerDefinition.saved_at ?? null,
  }
  const contract = {
    ...baseContract,
    compiled_contract_identity: identity,
  }
  await mkdir(dirname(resolve(outputPath)), { recursive: true })
  await writeFile(resolve(outputPath), `${JSON.stringify(contract, null, 2)}\n`, 'utf8')
  process.stdout.write(JSON.stringify({
    project_id: projectId,
    output: resolve(outputPath),
    contract_signature: identity.signature,
    revision_artifact_id: identity.revision_artifact_id,
  }, null, 2) + '\n')
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
