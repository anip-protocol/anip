import { readFileSync } from 'node:fs'

type JsonObject = Record<string, any>

interface Difference {
  path: string
  expected: unknown
  actual: unknown
}

function usage(): never {
  console.error('Usage: tsx scripts/compare-package-semantics.ts <expected-package.json> <actual-package.json>')
  process.exit(2)
}

const [expectedPath, actualPath] = process.argv.slice(2)
if (!expectedPath || !actualPath) usage()

function loadJson(path: string): JsonObject {
  return JSON.parse(readFileSync(path, 'utf8')) as JsonObject
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function splitList(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value
      .flatMap((entry) => String(entry ?? '').split(/[;,]/))
      .map((entry) => entry.trim())
      .filter(Boolean)
      .sort()
  }
  if (typeof value === 'string') {
    return value.split(/[;,]/).map((entry) => entry.trim()).filter(Boolean).sort()
  }
  return []
}

function capabilityId(capability: JsonObject): string {
  return String(capability.capability_id ?? capability.id ?? capability.name ?? '').trim()
}

function inputName(input: JsonObject): string {
  return String(input.input_name ?? input.name ?? '').trim()
}

function inputList(capability: JsonObject): JsonObject[] {
  const inputs = capability.input_contract?.inputs ?? capability.inputs ?? capability.input_specs ?? []
  return asArray(inputs).filter((input): input is JsonObject => Boolean(input && typeof input === 'object' && !Array.isArray(input)))
}

function normalizeResolution(value: unknown): JsonObject | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  const source = value as JsonObject
  return {
    mode: source.mode ?? null,
    resolver_ref: source.resolver_ref ?? null,
    on_missing: source.on_missing ?? null,
    on_ambiguous: source.on_ambiguous ?? null,
    on_unresolved: source.on_unresolved ?? null,
  }
}

function normalizeInput(input: JsonObject): JsonObject {
  return {
    required: input.required === true,
    input_type: input.input_type ?? input.type ?? null,
    semantic_type: input.semantic_type ?? null,
    entity_reference: input.entity_reference === true,
    allowed_values: splitList(input.allowed_values),
    catalog_ref: input.catalog_ref ?? null,
    default_value: input.default_value ?? input.default ?? null,
    resolution: normalizeResolution(input.resolution),
  }
}

function normalizeComposition(composition: unknown): JsonObject | null {
  if (!composition || typeof composition !== 'object' || Array.isArray(composition)) return null
  const source = composition as JsonObject
  return {
    authority_boundary: source.authority_boundary ?? null,
    steps: asArray(source.steps).map((step) => ({
      id: (step as JsonObject)?.id ?? null,
      capability: (step as JsonObject)?.capability ?? null,
      step_order: (step as JsonObject)?.step_order ?? null,
      empty_result_source: (step as JsonObject)?.empty_result_source === true,
      empty_result_path: (step as JsonObject)?.empty_result_path ?? null,
    })),
    input_mapping: source.input_mapping ?? {},
    output_mapping: source.output_mapping ?? {},
    empty_result_policy: source.empty_result_policy ?? null,
    empty_result_output: source.empty_result_output ?? null,
    failure_policy: source.failure_policy ?? {},
    audit_policy: source.audit_policy ?? {},
  }
}

function normalizeCapability(capability: JsonObject): JsonObject {
  const inputs = Object.fromEntries(
    inputList(capability)
      .map((input) => [inputName(input), normalizeInput(input)] as const)
      .filter(([name]) => Boolean(name)),
  )
  return {
    service_id: capability.service_id ?? capability.service_ref ?? capability.service ?? null,
    kind: capability.kind ?? null,
    operation_type: capability.operation_type ?? null,
    side_effect_level: capability.side_effect_level ?? null,
    grant_policy: capability.grant_policy ?? null,
    business_effects: {
      produces: splitList(capability.business_effects?.produces),
      does_not_produce: splitList(capability.business_effects?.does_not_produce),
    },
    inputs,
    composition: normalizeComposition(capability.composition ?? capability.composition_metadata),
  }
}

function normalizePackage(path: string): JsonObject {
  const bundle = loadJson(path)
  const serviceDefinition = bundle.service_definition ?? bundle.serviceDefinition
  if (!serviceDefinition || typeof serviceDefinition !== 'object') {
    throw new Error(`${path} does not contain service_definition`)
  }
  const capabilities = asArray((serviceDefinition as JsonObject).capability_formalizations)
    .filter((capability): capability is JsonObject => Boolean(capability && typeof capability === 'object' && !Array.isArray(capability)))
  return {
    anip_spec_version: bundle.manifest?.anip_spec_version ?? null,
    capabilities: Object.fromEntries(
      capabilities
        .map((capability) => [capabilityId(capability), normalizeCapability(capability)] as const)
        .filter(([id]) => Boolean(id)),
    ),
  }
}

function stable(value: unknown): string {
  return JSON.stringify(value, [...flattenKeys(value)].sort(), 2)
}

function flattenKeys(value: unknown, keys = new Set<string>()): Set<string> {
  if (Array.isArray(value)) value.forEach((entry) => flattenKeys(entry, keys))
  else if (value && typeof value === 'object') {
    Object.entries(value as JsonObject).forEach(([key, entry]) => {
      keys.add(key)
      flattenKeys(entry, keys)
    })
  }
  return keys
}

function compare(expected: unknown, actual: unknown, path: string, differences: Difference[]): void {
  if (stable(expected) === stable(actual)) return
  if (
    !expected
    || !actual
    || typeof expected !== 'object'
    || typeof actual !== 'object'
    || Array.isArray(expected)
    || Array.isArray(actual)
  ) {
    differences.push({ path, expected, actual })
    return
  }
  const keys = new Set([...Object.keys(expected as JsonObject), ...Object.keys(actual as JsonObject)])
  for (const key of [...keys].sort()) {
    compare((expected as JsonObject)[key], (actual as JsonObject)[key], path ? `${path}.${key}` : key, differences)
  }
}

const expected = normalizePackage(expectedPath)
const actual = normalizePackage(actualPath)
const differences: Difference[] = []
compare(expected, actual, '', differences)

if (differences.length) {
  console.error(`Package semantic comparison failed: ${differences.length} difference${differences.length === 1 ? '' : 's'}.`)
  for (const diff of differences.slice(0, 80)) {
    console.error(`\n${diff.path}`)
    console.error(`  expected: ${JSON.stringify(diff.expected)}`)
    console.error(`  actual:   ${JSON.stringify(diff.actual)}`)
  }
  if (differences.length > 80) console.error(`\n... ${differences.length - 80} additional differences omitted.`)
  process.exit(1)
}

console.log('Package semantic comparison passed.')
