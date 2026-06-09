import type {
  DeveloperCapabilityFormalization,
  DeveloperCapabilityInputFormalization,
  DeveloperCapabilityInputResolution,
  DeveloperCapabilityInputResolutionBehavior,
  DeveloperCapabilityInputResolutionMode,
  ArtifactRecord,
  ShapeRecord,
} from './project-types'

export interface ParsedInputContractCapability {
  capability_id: string
  inputs: DeveloperCapabilityInputFormalization[]
}

export interface ParsedInputContractEvidence {
  capabilities: ParsedInputContractCapability[]
  warnings: string[]
}

export interface InputContractEvidenceCoverage {
  expectedCapabilityIds: string[]
  coveredCapabilityIds: string[]
  missingCapabilityIds: string[]
  incompleteCapabilityIds: string[]
  unknownCapabilityIds: string[]
  weakInputClassifications: Array<{
    capability_id: string
    input_name: string
    reason: string
  }>
}

export interface AppliedInputContractEvidence {
  matchedCapabilityIds: string[]
  unknownCapabilityIds: string[]
  missingInputCapabilityIds: string[]
}

export interface ParsedCapabilityFormalizationEvidence {
  capabilities: DeveloperCapabilityFormalization[]
  warnings: string[]
}

type JsonObject = Record<string, unknown>

const RESOLUTION_MODES = new Set<DeveloperCapabilityInputResolutionMode>([
  'closed_values',
  'backend_resolved',
  'app_selected',
  'actor_policy',
  'actor_policy_or_explicit',
  'explicit_only',
  'clarify',
])

const RESOLUTION_BEHAVIORS = new Set<DeveloperCapabilityInputResolutionBehavior>([
  'clarify',
  'use_default',
  'use_actor_scope',
  'app_select_or_clarify',
  'deny',
  'deny_or_clarify',
  'omit',
])

function asObject(value: unknown): JsonObject | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as JsonObject : null
}

function asString(value: unknown): string {
  return String(value ?? '').trim()
}

function asBoolean(value: unknown): boolean {
  return value === true || value === 'true'
}

function isCanonicalCapabilityId(value: string): boolean {
  return /^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+$/.test(value.trim())
}

function isCanonicalInputName(value: string): boolean {
  return /^[A-Za-z][A-Za-z0-9_]*$/.test(value.trim())
}

function stringList(value: unknown): string[] {
  if (Array.isArray(value)) return value.map((item) => asString(item)).filter(Boolean)
  if (typeof value === 'string') {
    return value.split(/[,;]+/).map((item) => item.trim()).filter(Boolean)
  }
  return []
}

function resolutionBehavior(value: unknown): DeveloperCapabilityInputResolutionBehavior | undefined {
  const candidate = asString(value) as DeveloperCapabilityInputResolutionBehavior
  return RESOLUTION_BEHAVIORS.has(candidate) ? candidate : undefined
}

function normalizeResolution(value: unknown, required: boolean): DeveloperCapabilityInputResolution {
  const source = asObject(value) ?? {}
  const mode = asString(source.mode) as DeveloperCapabilityInputResolutionMode
  const result: DeveloperCapabilityInputResolution = {
    mode: RESOLUTION_MODES.has(mode) ? mode : required ? 'clarify' : 'explicit_only',
  }
  const resolverRef = asString(source.resolver_ref)
  if (resolverRef) result.resolver_ref = resolverRef
  result.on_missing = resolutionBehavior(source.on_missing) ?? (required ? 'clarify' : 'omit')
  const onAmbiguous = resolutionBehavior(source.on_ambiguous)
  if (onAmbiguous) result.on_ambiguous = onAmbiguous
  const onUnresolved = resolutionBehavior(source.on_unresolved)
  if (onUnresolved) result.on_unresolved = onUnresolved
  return result
}

function normalizeInput(value: unknown): DeveloperCapabilityInputFormalization | null {
  const source = asObject(value)
  if (!source) return null
  const inputName = asString(source.input_name ?? source.name)
  if (!inputName || !isCanonicalInputName(inputName)) return null
  const required = asBoolean(source.required)
  const defaultValue = source.default_value ?? source.default
  const resolution = normalizeResolution(source.resolution, required)
  const input: DeveloperCapabilityInputFormalization = {
    input_name: inputName,
    input_type: asString(source.input_type ?? source.type) || 'string',
    required,
    summary: asString(source.summary ?? source.description) || `Reviewed input contract for ${inputName}.`,
    default_value: defaultValue === null || defaultValue === undefined ? '' : String(defaultValue),
    allowed_values: stringList(source.allowed_values),
    entity_reference: asBoolean(source.entity_reference),
    semantic_type: asString(source.semantic_type),
    normalization_hint: asString(source.normalization_hint),
    normalization_context: asString(source.normalization_context),
    input_format: asString(source.input_format),
    validation_pattern: asString(source.validation_pattern),
    clarification_hint: asString(source.clarification_hint),
    resolution,
  }
  const catalogRef = asString(source.catalog_ref)
  if (catalogRef) {
    input.catalog_ref = catalogRef
    if (['backend_resolved', 'closed_values'].includes(resolution.mode) && !resolution.resolver_ref) {
      resolution.resolver_ref = catalogRef
    }
  }
  const referenceCatalog = stringList(source.reference_catalog)
  if (referenceCatalog.length) input.reference_catalog = referenceCatalog
  const semanticAliases = stringList(source.semantic_aliases)
  if (semanticAliases.length) input.semantic_aliases = semanticAliases
  return input
}

function inputsFromObject(source: JsonObject): DeveloperCapabilityInputFormalization[] {
  const inputs = source.inputs ?? source.input_specs ?? source.parameters
  if (!Array.isArray(inputs)) return []
  return inputs
    .map((item) => normalizeInput(item))
    .filter((item): item is DeveloperCapabilityInputFormalization => Boolean(item))
}

function capabilityFromObject(source: JsonObject): ParsedInputContractCapability | null {
  const capabilityId = asString(source.capability_id ?? source.id)
  if (!capabilityId || !isCanonicalCapabilityId(capabilityId)) return null
  return {
    capability_id: capabilityId,
    inputs: inputsFromObject(source),
  }
}

function stringRecordList(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => asString(item)).filter(Boolean) : []
}

function normalizeBusinessEffects(value: unknown): DeveloperCapabilityFormalization['business_effects'] {
  const source = asObject(value)
  if (!source) return undefined
  return {
    produces: stringRecordList(source.produces),
    does_not_produce: stringRecordList(source.does_not_produce),
  }
}

function normalizeImplementationFit(value: unknown): DeveloperCapabilityFormalization['implementation_fit'] {
  const source = asObject(value)
  if (!source) return undefined
  return {
    category: asString(source.category) as NonNullable<DeveloperCapabilityFormalization['implementation_fit']>['category'] || 'custom_service_logic',
    rationale: asString(source.rationale),
  }
}

function capabilityFormalizationFromObject(source: JsonObject): DeveloperCapabilityFormalization | null {
  const capabilityId = asString(source.capability_id ?? source.id)
  if (!capabilityId) return null
  return {
    id: asString(source.id) || `capability:${capabilityId}`,
    kind: source.kind === 'composed' ? 'composed' : 'atomic',
    composition: asObject(source.composition) as DeveloperCapabilityFormalization['composition'] ?? null,
    grant_policy: asObject(source.grant_policy) as DeveloperCapabilityFormalization['grant_policy'] ?? null,
    source_kind: source.source_kind === 'application_integration' || source.source_kind === 'data_access'
      ? source.source_kind
      : 'contract_native',
    service_id: asString(source.service_id),
    capability_id: capabilityId,
    title: asString(source.title) || capabilityId,
    summary: asString(source.summary),
    entity_targeted: asBoolean(source.entity_targeted),
    subject_kind: asString(source.subject_kind),
    context_type: asString(source.context_type),
    output_intent: asString(source.output_intent),
    intent_type: asString(source.intent_type),
    operation_type: asString(source.operation_type),
    side_effect_level: asString(source.side_effect_level),
    implementation_fit: normalizeImplementationFit(source.implementation_fit),
    business_effects: normalizeBusinessEffects(source.business_effects),
    minimum_scope: stringRecordList(source.minimum_scope),
    backend_operation: asString(source.backend_operation),
    path_template: asString(source.path_template),
    output_shape: asString(source.output_shape),
    inputs: inputsFromObject(source),
  }
}

function collectCapabilityFormalizations(value: unknown, capabilities: DeveloperCapabilityFormalization[]): void {
  if (Array.isArray(value)) {
    value.forEach((item) => collectCapabilityFormalizations(item, capabilities))
    return
  }
  const source = asObject(value)
  if (!source) return

  if (Array.isArray(source.capability_formalizations)) {
    source.capability_formalizations.forEach((item) => {
      const itemObject = asObject(item)
      if (!itemObject) return
      const capability = capabilityFormalizationFromObject(itemObject)
      if (capability) capabilities.push(capability)
    })
  }

  const developerDefinition = asObject(source.developer_definition)
  if (developerDefinition) collectCapabilityFormalizations(developerDefinition, capabilities)
}

function collectCapabilities(value: unknown, capabilities: ParsedInputContractCapability[]): void {
  if (Array.isArray(value)) {
    value.forEach((item) => collectCapabilities(item, capabilities))
    return
  }
  const source = asObject(value)
  if (!source) return
  const direct = capabilityFromObject(source)
  if (direct) capabilities.push(direct)

  for (const key of ['capabilities', 'capability_contracts', 'input_contracts', 'capability_inputs', 'capability_formalizations']) {
    const nested = source[key]
    if (Array.isArray(nested)) collectCapabilities(nested, capabilities)
  }

  for (const [key, entry] of Object.entries(source)) {
    if (!key.includes('.') || !asObject(entry)) continue
    const entryObject = entry as JsonObject
    const withId = { ...entryObject, capability_id: entryObject.capability_id ?? key }
    const mapped = capabilityFromObject(withId)
    if (mapped) capabilities.push(mapped)
  }
}

export function parseInputContractEvidence(raw: string): ParsedInputContractEvidence {
  const text = raw.trim()
  if (!text) throw new Error('Paste reviewed input-contract JSON before importing.')
  let parsed: unknown
  try {
    parsed = JSON.parse(text)
  } catch (error) {
    throw new Error(`Input-contract evidence must be valid JSON: ${(error as Error).message}`)
  }
  const collected: ParsedInputContractCapability[] = []
  collectCapabilities(parsed, collected)

  const byId = new Map<string, ParsedInputContractCapability>()
  const warnings: string[] = []
  collected.forEach((capability) => {
    if (!capability.capability_id) return
    if (capability.inputs.length === 0) {
      warnings.push(`${capability.capability_id} did not include any inputs.`)
    }
    const existing = byId.get(capability.capability_id)
    byId.set(capability.capability_id, {
      capability_id: capability.capability_id,
      inputs: existing ? [...existing.inputs, ...capability.inputs] : capability.inputs,
    })
  })

  const capabilities = [...byId.values()]
  if (capabilities.length === 0) throw new Error('No capability input contracts were found in the pasted JSON.')
  return { capabilities, warnings }
}

function cleanMarkdownCell(value: string): string {
  return value
    .trim()
    .replace(/^`|`$/g, '')
    .replace(/<br\s*\/?>/gi, ', ')
    .trim()
}

function splitMarkdownTableRow(line: string): string[] {
  const trimmed = line.trim()
  if (!trimmed.includes('|')) return []
  return trimmed
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map(cleanMarkdownCell)
}

function isMarkdownDividerRow(cells: string[]): boolean {
  return cells.length > 0 && cells.every((cell) => /^:?-{3,}:?$/.test(cell.trim()))
}

function normalizeMarkdownHeader(value: string): string {
  return value
    .toLowerCase()
    .replace(/`/g, '')
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
}

function markdownBoolean(value: string): boolean {
  return ['true', 'yes', 'y', 'required', '1'].includes(value.trim().toLowerCase())
}

function markdownInputFromRow(headers: string[], cells: string[]): DeveloperCapabilityInputFormalization | null {
  const row: Record<string, string> = {}
  headers.forEach((header, index) => {
    row[header] = cells[index] ?? ''
  })
  const name = row.input_name || row.name || row.input || row.parameter || row.field
  if (!name || !isCanonicalInputName(name)) return null
  const required = markdownBoolean(row.required || row.is_required || '')
  const mode = row.resolution_mode || row.resolution || row.mode
  const catalogRef = row.catalog_ref || ''
  const input: DeveloperCapabilityInputFormalization = {
    input_name: name,
    input_type: row.input_type || row.type || 'string',
    required,
    summary: row.summary || row.description || `Reviewed input contract for ${name}.`,
    default_value: row.default_value || row.default || '',
    allowed_values: stringList(row.allowed_values || row.values || ''),
    entity_reference: markdownBoolean(row.entity_reference || row.entity_ref || ''),
    semantic_type: row.semantic_type || '',
    normalization_hint: row.normalization_hint || '',
    normalization_context: row.normalization_context || '',
    input_format: row.input_format || row.format || '',
    validation_pattern: row.validation_pattern || row.pattern || '',
    clarification_hint: row.clarification_hint || row.clarification || '',
    resolution: normalizeResolution({
      mode,
      resolver_ref: row.resolver_ref || catalogRef,
      on_missing: row.on_missing || '',
      on_ambiguous: row.on_ambiguous || '',
      on_unresolved: row.on_unresolved || '',
    }, required),
  }
  if (catalogRef) input.catalog_ref = catalogRef
  const referenceCatalog = stringList(row.reference_catalog || '')
  if (referenceCatalog.length) input.reference_catalog = referenceCatalog
  const semanticAliases = stringList(row.semantic_aliases || row.aliases || '')
  if (semanticAliases.length) input.semantic_aliases = semanticAliases
  return input
}

function parseMarkdownInputTables(sectionText: string): DeveloperCapabilityInputFormalization[] {
  const lines = sectionText.split(/\r?\n/)
  const inputs: DeveloperCapabilityInputFormalization[] = []
  for (let index = 0; index < lines.length; index += 1) {
    const headerCells = splitMarkdownTableRow(lines[index])
    if (!headerCells.length) continue
    const normalizedHeaders = headerCells.map(normalizeMarkdownHeader)
    const hasInputHeader = normalizedHeaders.some((header) =>
      ['input_name', 'name', 'input', 'parameter', 'field'].includes(header),
    )
    const hasTypeHeader = normalizedHeaders.some((header) =>
      ['input_type', 'type'].includes(header),
    )
    if (!hasInputHeader || !hasTypeHeader) continue
    const dividerCells = splitMarkdownTableRow(lines[index + 1] ?? '')
    if (!isMarkdownDividerRow(dividerCells)) continue
    index += 2
    while (index < lines.length) {
      const rowCells = splitMarkdownTableRow(lines[index])
      if (!rowCells.length || isMarkdownDividerRow(rowCells)) break
      const input = markdownInputFromRow(normalizedHeaders, rowCells)
      if (input) inputs.push(input)
      index += 1
    }
  }
  return inputs
}

function parseMarkdownCapabilitySections(raw: string): ParsedInputContractEvidence | null {
  const text = raw.trim()
  if (!text) return null
  const headingPattern = /^#{2,6}[ \t]+(?:(?:Capability|Capability ID|Capability Contract)[ \t]*[:\-][ \t]*)?`?([A-Za-z][A-Za-z0-9_-]*(?:\.[A-Za-z0-9_-]+)+)`?(?:[ \t]+.*)?$/gm
  const matches = [...text.matchAll(headingPattern)]
  if (!matches.length) return null
  const capabilities: ParsedInputContractCapability[] = []
  const warnings: string[] = []
  matches.forEach((match, index) => {
    const capabilityId = cleanMarkdownCell(match[1] ?? '')
    const start = (match.index ?? 0) + match[0].length
    const end = index < matches.length - 1 ? matches[index + 1].index ?? text.length : text.length
    if (!capabilityId) return
    const inputs = parseMarkdownInputTables(text.slice(start, end))
    if (!inputs.length) warnings.push(`${capabilityId} did not include any Markdown input table rows.`)
    capabilities.push({ capability_id: capabilityId, inputs })
  })
  const byId = new Map<string, ParsedInputContractCapability>()
  capabilities.forEach((capability) => {
    const existing = byId.get(capability.capability_id)
    byId.set(capability.capability_id, {
      capability_id: capability.capability_id,
      inputs: existing ? [...existing.inputs, ...capability.inputs] : capability.inputs,
    })
  })
  const uniqueCapabilities = [...byId.values()]
  return uniqueCapabilities.length ? { capabilities: uniqueCapabilities, warnings } : null
}

function parseCsvRows(raw: string): string[][] {
  const rows: string[][] = []
  let row: string[] = []
  let cell = ''
  let inQuotes = false

  for (let index = 0; index < raw.length; index += 1) {
    const char = raw[index]
    const next = raw[index + 1]
    if (char === '"') {
      if (inQuotes && next === '"') {
        cell += '"'
        index += 1
      } else {
        inQuotes = !inQuotes
      }
      continue
    }
    if (char === ',' && !inQuotes) {
      row.push(cell.trim())
      cell = ''
      continue
    }
    if ((char === '\n' || char === '\r') && !inQuotes) {
      if (char === '\r' && next === '\n') index += 1
      row.push(cell.trim())
      if (row.some(Boolean)) rows.push(row)
      row = []
      cell = ''
      continue
    }
    cell += char
  }

  row.push(cell.trim())
  if (row.some(Boolean)) rows.push(row)
  return rows
}

function parseCsvInputContractEvidence(raw: string): ParsedInputContractEvidence | null {
  const rows = parseCsvRows(raw)
  const headerIndex = rows.findIndex((row) => {
    const normalized = row.map((cell) => normalizeMarkdownHeader(cell))
    return normalized.includes('capability_id')
      && normalized.includes('input_name')
      && normalized.includes('input_type')
      && normalized.includes('required')
  })
  if (headerIndex < 0) return null

  const headers = rows[headerIndex].map(normalizeMarkdownHeader)
  const byId = new Map<string, ParsedInputContractCapability>()
  const warnings: string[] = []

  for (const cells of rows.slice(headerIndex + 1)) {
    if (cells.length < headers.length) break
    const normalizedCells = cells.map((cell) => normalizeMarkdownHeader(cell))
    if (normalizedCells.includes('capability_id')) break
    const row: Record<string, string> = {}
    headers.forEach((header, index) => {
      row[header] = cells[index] ?? ''
    })
    const capabilityId = asString(row.capability_id)
    const inputName = asString(row.input_name)
    if (!capabilityId || !inputName) continue
    if (!isCanonicalCapabilityId(capabilityId) || !isCanonicalInputName(inputName)) continue

    const required = markdownBoolean(row.required || '')
    const mode = row.resolution_mode || row.resolution || row.mode
    const catalogRef = row.catalog_ref || ''
    const input: DeveloperCapabilityInputFormalization = {
      input_name: inputName,
      input_type: row.input_type || 'string',
      required,
      summary: row.summary || row.description || `Reviewed input contract for ${inputName}.`,
      default_value: row.default_value || row.default || '',
      allowed_values: stringList(row.allowed_values || row.values || ''),
      entity_reference: markdownBoolean(row.entity_reference || row.entity_ref || ''),
      semantic_type: row.semantic_type || '',
      normalization_hint: row.normalization_hint || '',
      normalization_context: row.normalization_context || '',
      input_format: row.input_format || row.format || '',
      validation_pattern: row.validation_pattern || row.pattern || '',
      clarification_hint: row.clarification_hint || row.clarification || '',
      resolution: normalizeResolution({
        mode,
        resolver_ref: row.resolver_ref || catalogRef,
        on_missing: row.on_missing || '',
        on_ambiguous: row.on_ambiguous || '',
        on_unresolved: row.on_unresolved || '',
      }, required),
    }
    if (catalogRef) input.catalog_ref = catalogRef
    const referenceCatalog = stringList(row.reference_catalog || '')
    if (referenceCatalog.length) input.reference_catalog = referenceCatalog
    const semanticAliases = stringList(row.semantic_aliases || row.aliases || '')
    if (semanticAliases.length) input.semantic_aliases = semanticAliases

    const existing = byId.get(capabilityId)
    if (existing) {
      existing.inputs.push(input)
    } else {
      byId.set(capabilityId, { capability_id: capabilityId, inputs: [input] })
    }
  }

  const capabilities = [...byId.values()]
  capabilities.forEach((capability) => {
    if (capability.inputs.length === 0) warnings.push(`${capability.capability_id} did not include any CSV input rows.`)
  })
  return capabilities.length ? { capabilities, warnings } : null
}

export function inputContractEvidenceJsonCandidates(raw: string): string[] {
  const text = raw.trim()
  if (!text) return []
  const candidates: string[] = []
  const addCandidatesFromText = (candidateText: string) => {
    const trimmed = candidateText.trim()
    if (!trimmed) return
    if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
      candidates.push(trimmed)
    }
    const fencedJsonPattern = /```(?:json)?\s*([\s\S]*?)```/gi
    let match: RegExpExecArray | null
    while ((match = fencedJsonPattern.exec(trimmed)) != null) {
      if (match[1]?.trim()) candidates.push(match[1].trim())
    }
    const firstObject = trimmed.indexOf('{')
    const lastObject = trimmed.lastIndexOf('}')
    if (firstObject >= 0 && lastObject > firstObject) {
      candidates.push(trimmed.slice(firstObject, lastObject + 1))
    }
    const firstArray = trimmed.indexOf('[')
    const lastArray = trimmed.lastIndexOf(']')
    if (firstArray >= 0 && lastArray > firstArray) {
      candidates.push(trimmed.slice(firstArray, lastArray + 1))
    }
  }
  addCandidatesFromText(text)
  const sourceEvidenceMarker = '# Source Evidence Available To Developer Design'
  const markerIndex = text.indexOf(sourceEvidenceMarker)
  if (markerIndex >= 0) {
    const sourceEvidenceText = text.slice(markerIndex + sourceEvidenceMarker.length)
    const nextDraftEvidenceIndex = sourceEvidenceText.search(/\n# Draft Developer /)
    addCandidatesFromText(nextDraftEvidenceIndex >= 0
      ? sourceEvidenceText.slice(0, nextDraftEvidenceIndex)
      : sourceEvidenceText)
  }
  return [...new Set(candidates.map((candidate) => candidate.trim()).filter(Boolean))]
}

export function parseInputContractEvidenceFromSourceText(raw: string): ParsedInputContractEvidence {
  const errors: string[] = []
  for (const candidate of inputContractEvidenceJsonCandidates(raw)) {
    try {
      return parseInputContractEvidence(candidate)
    } catch (error) {
      errors.push(error instanceof Error ? error.message : String(error))
    }
  }
  const markdownEvidence = parseMarkdownCapabilitySections(raw)
  if (markdownEvidence) return markdownEvidence
  const csvEvidence = parseCsvInputContractEvidence(raw)
  if (csvEvidence) return csvEvidence
  throw new Error(errors[0] || 'No reviewed input-contract JSON evidence was found in the selected source text.')
}

function sortedUnique(values: string[]): string[] {
  return [...new Set(values.map((value) => value.trim()).filter(Boolean))].sort((a, b) => a.localeCompare(b))
}

function hasExplicitInputClassification(input: DeveloperCapabilityInputFormalization): boolean {
  return Boolean(
    String(input.semantic_type ?? '').trim()
    || String(input.input_format ?? '').trim()
    || String(input.validation_pattern ?? '').trim()
    || String(input.clarification_hint ?? '').trim()
    || input.entity_reference === true
    || (input.allowed_values ?? []).length > 0,
  )
}

export function expectedCapabilityIdsFromShape(shape: ShapeRecord | null | undefined): string[] {
  if (!shape?.data) return []
  const shapeData = (shape.data.shape ?? shape.data) as Record<string, unknown>
  const services = Array.isArray(shapeData.services) ? shapeData.services : []
  return sortedUnique(services.flatMap((service) => {
    if (!service || typeof service !== 'object') return []
    const capabilities = (service as Record<string, unknown>).capabilities
    if (!Array.isArray(capabilities)) return []
    return capabilities.map((capability) => asString(capability))
  }))
}

export function inputContractEvidenceCoverage(args: {
  sourceText: string
  expectedCapabilityIds: string[]
}): InputContractEvidenceCoverage {
  const expectedCapabilityIds = sortedUnique(args.expectedCapabilityIds)
  let evidence: ParsedInputContractEvidence | null = null
  try {
    evidence = parseInputContractEvidenceFromSourceText(args.sourceText)
  } catch {
    evidence = null
  }
  const evidenceById = new Map((evidence?.capabilities ?? []).map((capability) => [capability.capability_id, capability] as const))
  const coveredCapabilityIds = expectedCapabilityIds.filter((capabilityId) =>
    (evidenceById.get(capabilityId)?.inputs ?? []).length > 0,
  )
  const incompleteCapabilityIds = expectedCapabilityIds.filter((capabilityId) =>
    evidenceById.has(capabilityId) && (evidenceById.get(capabilityId)?.inputs ?? []).length === 0,
  )
  const missingCapabilityIds = expectedCapabilityIds.filter((capabilityId) => !evidenceById.has(capabilityId))
  const unknownCapabilityIds = sortedUnique((evidence?.capabilities ?? [])
    .map((capability) => capability.capability_id)
    .filter((capabilityId) => !expectedCapabilityIds.includes(capabilityId)))
  const weakInputClassifications = expectedCapabilityIds.flatMap((capabilityId) => {
    const capability = evidenceById.get(capabilityId)
    if (!capability) return []
    return capability.inputs
      .filter((input) => input.required && !hasExplicitInputClassification(input))
      .map((input) => ({
        capability_id: capabilityId,
        input_name: input.input_name,
        reason: 'Required input is missing semantic_type, entity_reference, allowed_values, input_format, validation_pattern, or clarification_hint.',
      }))
  })
  return {
    expectedCapabilityIds,
    coveredCapabilityIds,
    missingCapabilityIds,
    incompleteCapabilityIds,
    unknownCapabilityIds,
    weakInputClassifications,
  }
}

function collectStructuredInputContractCapabilities(value: unknown, collected: ParsedInputContractCapability[]): void {
  const record = asObject(value)
  if (!record) return
  const directCapabilities = record.capabilities
  if (Array.isArray(directCapabilities)) {
    directCapabilities.forEach((capability) => {
      const capabilityRecord = asObject(capability)
      if (!capabilityRecord) return
      const capabilityId = asString(capabilityRecord.capability_id ?? capabilityRecord.id)
      const inputs = Array.isArray(capabilityRecord.inputs)
        ? capabilityRecord.inputs.map(normalizeInput).filter(Boolean) as DeveloperCapabilityInputFormalization[]
        : []
      if (capabilityId) collected.push({ capability_id: capabilityId, inputs })
    })
  }
  const nested = record.structured_data ?? record.accepted_payload ?? record.source_proposal
  if (nested && nested !== value) collectStructuredInputContractCapabilities(nested, collected)
  const items = record.items ?? record.accepted_payload
  if (Array.isArray(items)) {
    items.forEach((item) => collectStructuredInputContractCapabilities(item, collected))
  }
}

function acceptedInputContractCapabilitiesFromArtifacts(pmArtifacts: ArtifactRecord[]): ParsedInputContractCapability[] {
  const collected: ParsedInputContractCapability[] = []
  pmArtifacts.forEach((artifact) => {
    const data = asObject(artifact.data)
    if (!data) return
    const artifactType = asString(data.artifact_type)
    if (!['assistant_input_contract_candidates', 'assistant_capability_formalization_candidates'].includes(artifactType)) return
    const acceptedPayload = Array.isArray(data.accepted_payload) ? data.accepted_payload : []
    if (!acceptedPayload.length) return
    collectStructuredInputContractCapabilities({ items: acceptedPayload }, collected)
  })
  return collected
}

function frontingMappingInputContractCapabilitiesFromArtifacts(pmArtifacts: ArtifactRecord[]): ParsedInputContractCapability[] {
  return pmArtifacts.flatMap((artifact) => {
    const data = asObject(artifact.data)
    if (!data || asString(data.artifact_type) !== 'integration_fronting_capability_mapping') return []
    const capabilityId = asString(data.capability_id)
    if (!capabilityId || !isCanonicalCapabilityId(capabilityId)) return []
    const inputMetadata = Array.isArray(data.input_metadata) ? data.input_metadata : []
    const inputs = inputMetadata
      .map((input) => normalizeInput(input))
      .filter((input): input is DeveloperCapabilityInputFormalization => Boolean(input))
    return [{
      capability_id: capabilityId,
      inputs,
    }]
  })
}

function coverageFromCapabilities(args: {
  expectedCapabilityIds: string[]
  capabilities: ParsedInputContractCapability[]
}): InputContractEvidenceCoverage {
  const expectedCapabilityIds = sortedUnique(args.expectedCapabilityIds)
  const evidenceById = new Map<string, ParsedInputContractCapability>()
  args.capabilities.forEach((capability) => {
    const existing = evidenceById.get(capability.capability_id)
    evidenceById.set(capability.capability_id, {
      capability_id: capability.capability_id,
      inputs: [...(existing?.inputs ?? []), ...capability.inputs],
    })
  })
  const coveredCapabilityIds = expectedCapabilityIds.filter((capabilityId) =>
    (evidenceById.get(capabilityId)?.inputs ?? []).length > 0,
  )
  const incompleteCapabilityIds = expectedCapabilityIds.filter((capabilityId) =>
    evidenceById.has(capabilityId) && (evidenceById.get(capabilityId)?.inputs ?? []).length === 0,
  )
  const missingCapabilityIds = expectedCapabilityIds.filter((capabilityId) => !evidenceById.has(capabilityId))
  const unknownCapabilityIds = sortedUnique([...evidenceById.keys()].filter((capabilityId) => !expectedCapabilityIds.includes(capabilityId)))
  const weakInputClassifications = expectedCapabilityIds.flatMap((capabilityId) => {
    const capability = evidenceById.get(capabilityId)
    if (!capability) return []
    return capability.inputs
      .filter((input) => input.required && !hasExplicitInputClassification(input))
      .map((input) => ({
        capability_id: capabilityId,
        input_name: input.input_name,
        reason: 'Required input is missing semantic_type, entity_reference, allowed_values, input_format, validation_pattern, or clarification_hint.',
      }))
  })
  return {
    expectedCapabilityIds,
    coveredCapabilityIds,
    missingCapabilityIds,
    incompleteCapabilityIds,
    unknownCapabilityIds,
    weakInputClassifications,
  }
}

export function inputContractReviewedEvidenceCoverage(args: {
  sourceText: string
  expectedCapabilityIds: string[]
  pmArtifacts?: ArtifactRecord[]
  capabilityFormalizations?: Array<{ capability_id: string; inputs?: DeveloperCapabilityInputFormalization[] }>
}): InputContractEvidenceCoverage {
  const sourceCapabilities = (() => {
    try {
      return parseInputContractEvidenceFromSourceText(args.sourceText).capabilities
    } catch {
      return [] as ParsedInputContractCapability[]
    }
  })()
  const definitionCapabilities = (args.capabilityFormalizations ?? []).map((capability) => ({
    capability_id: capability.capability_id,
    inputs: capability.inputs ?? [],
  }))
  return coverageFromCapabilities({
    expectedCapabilityIds: args.expectedCapabilityIds,
    capabilities: [
      ...sourceCapabilities,
      ...acceptedInputContractCapabilitiesFromArtifacts(args.pmArtifacts ?? []),
      ...frontingMappingInputContractCapabilitiesFromArtifacts(args.pmArtifacts ?? []),
      ...definitionCapabilities,
    ],
  })
}

export function parseCapabilityFormalizationEvidence(raw: string): ParsedCapabilityFormalizationEvidence {
  const text = raw.trim()
  if (!text) throw new Error('Paste reviewed capability-formalization JSON before importing.')
  let parsed: unknown
  try {
    parsed = JSON.parse(text)
  } catch (error) {
    throw new Error(`Capability-formalization evidence must be valid JSON: ${(error as Error).message}`)
  }

  const collected: DeveloperCapabilityFormalization[] = []
  collectCapabilityFormalizations(parsed, collected)
  const byId = new Map<string, DeveloperCapabilityFormalization>()
  const warnings: string[] = []
  collected.forEach((capability) => {
    if (!capability.capability_id) return
    if (capability.inputs.length === 0) warnings.push(`${capability.capability_id} did not include any inputs.`)
    if (!capability.service_id) warnings.push(`${capability.capability_id} did not include a service_id.`)
    byId.set(capability.capability_id, capability)
  })

  const capabilities = [...byId.values()]
  if (capabilities.length === 0) throw new Error('No capability formalizations were found in the pasted JSON.')
  return { capabilities, warnings }
}

export function parseCapabilityFormalizationEvidenceFromSourceText(raw: string): ParsedCapabilityFormalizationEvidence {
  const errors: string[] = []
  for (const candidate of inputContractEvidenceJsonCandidates(raw)) {
    try {
      return parseCapabilityFormalizationEvidence(candidate)
    } catch (error) {
      errors.push(error instanceof Error ? error.message : String(error))
    }
  }
  throw new Error(errors[0] || 'No reviewed capability-formalization JSON evidence was found in the selected source text.')
}

export function applyInputContractEvidence(
  capabilities: DeveloperCapabilityFormalization[],
  evidence: ParsedInputContractEvidence,
): AppliedInputContractEvidence {
  const byCapabilityId = new Map(capabilities.map((capability) => [capability.capability_id, capability]))
  const matchedCapabilityIds: string[] = []
  const unknownCapabilityIds: string[] = []
  const missingInputCapabilityIds: string[] = []

  evidence.capabilities.forEach((entry) => {
    const capability = byCapabilityId.get(entry.capability_id)
    if (!capability) {
      unknownCapabilityIds.push(entry.capability_id)
      return
    }
    if (entry.inputs.length === 0) {
      missingInputCapabilityIds.push(entry.capability_id)
      return
    }
    capability.inputs = entry.inputs.map((input) => ({ ...input }))
    matchedCapabilityIds.push(entry.capability_id)
  })

  return { matchedCapabilityIds, unknownCapabilityIds, missingInputCapabilityIds }
}

export function inputContractEvidenceArtifactItems(evidence: ParsedInputContractEvidence): Array<Record<string, unknown>> {
  return evidence.capabilities.map((capability) => ({
    client_id: `input-contract-${capability.capability_id.replace(/[^a-zA-Z0-9_-]+/g, '-')}`,
    title: `Reviewed input contract for ${capability.capability_id}`,
    structured_data: {
      capabilities: [
        {
          capability_id: capability.capability_id,
          inputs: capability.inputs,
        },
      ],
    },
  }))
}

export function capabilityFormalizationEvidenceArtifactItems(
  evidence: ParsedCapabilityFormalizationEvidence,
): Array<Record<string, unknown>> {
  return [{
    client_id: 'canonical-capability-formalizations',
    title: 'Canonical capability formalizations',
    body: `Preserved ${evidence.capabilities.length} reviewed capability formalization${evidence.capabilities.length === 1 ? '' : 's'} from developer source evidence.`,
    structured_data: {
      capabilities: evidence.capabilities,
    },
  }]
}
