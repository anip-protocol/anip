import type {
  ConformanceCheck,
  IntendedDesignMetadata,
  ObservedServiceCapability,
  ObservedServiceMetadata,
  ServiceMetadataComparison,
  SurfaceEvidence,
} from './types'
import type { ArtifactRecord } from './project-types'

function uniqueStrings(values: Array<string | null | undefined>): string[] {
  return Array.from(new Set(values.map((value) => String(value || '').trim()).filter(Boolean)))
}

function asObject(value: any, key?: string): Record<string, any> {
  if (!value || typeof value !== 'object') return {}
  if (key && value[key] && typeof value[key] === 'object') return value[key]
  return value
}

function slugPart(value: string | null | undefined): string {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 80)
}

function firstString(...values: any[]): string | null {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) return value.trim()
  }
  return null
}

function firstBoolean(...values: any[]): boolean | null {
  for (const value of values) {
    if (typeof value === 'boolean') return value
  }
  return null
}

function listOfStrings(value: any): string[] {
  if (!Array.isArray(value)) return []
  return uniqueStrings(value.map((item) => (item == null ? null : String(item))))
}

function keysOfTruthyRecord(value: any): string[] {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return []
  return uniqueStrings(
    Object.entries(value)
      .filter(([, enabled]) => enabled !== false && enabled != null)
      .map(([key]) => key),
  )
}

function extractRawManifest(manifestDoc: any): Record<string, any> {
  if (manifestDoc?.raw && typeof manifestDoc.raw === 'object') return manifestDoc.raw
  return asObject(manifestDoc)
}

function extractCapabilityObject(value: any): Record<string, any> {
  if (!value || typeof value !== 'object') return {}
  if (value.raw && typeof value.raw === 'object') return value.raw
  return value
}

function normalizeCapability(
  id: string,
  discoveryCapability: any,
  manifestCapability: any,
): ObservedServiceCapability {
  const discovery = extractCapabilityObject(discoveryCapability)
  const manifest = extractCapabilityObject(manifestCapability)
  const manifestCrossService = asObject(manifest.crossService || manifest.cross_service)

  const sideEffect =
    firstString(
      manifest.sideEffect?.type,
      manifest.side_effect?.type,
      manifest.sideEffect,
      manifest.side_effect,
      discovery.sideEffect?.type,
      discovery.side_effect?.type,
      discovery.sideEffect,
      discovery.side_effect,
    ) || null

  const minimumScope = uniqueStrings([
    ...listOfStrings(manifest.minimumScope),
    ...listOfStrings(manifest.minimum_scope),
    ...listOfStrings(discovery.minimumScope),
    ...listOfStrings(discovery.minimum_scope),
  ])

  const contract =
    firstString(
      manifest.contract,
      manifest.contract?.name,
      discovery.contract,
      discovery.contract?.name,
    ) || null

  const requiresBinding = uniqueStrings([
    ...listOfStrings(manifest.requiresBinding),
    ...listOfStrings(manifest.requires_binding),
    ...listOfStrings(discovery.requiresBinding),
    ...listOfStrings(discovery.requires_binding),
  ])

  const controlRequirements = uniqueStrings([
    ...keysOfTruthyRecord(manifest.controlRequirements),
    ...keysOfTruthyRecord(manifest.control_requirements),
    ...keysOfTruthyRecord(discovery.controlRequirements),
    ...keysOfTruthyRecord(discovery.control_requirements),
  ])

  return {
    id,
    side_effect: sideEffect,
    minimum_scope: minimumScope,
    financial: Boolean(
      manifest.financial ??
      manifest.cost?.financial ??
      discovery.financial ??
      discovery.cost?.financial,
    ),
    contract,
    requires_binding: requiresBinding,
    control_requirements: controlRequirements,
    refresh_via: uniqueStrings([
      ...listOfStrings(manifest.refreshVia),
      ...listOfStrings(manifest.refresh_via),
      ...listOfStrings(discovery.refreshVia),
      ...listOfStrings(discovery.refresh_via),
      ...listOfStrings(manifestCrossService.refresh_via),
    ]),
    verify_via: uniqueStrings([
      ...listOfStrings(manifest.verifyVia),
      ...listOfStrings(manifest.verify_via),
      ...listOfStrings(discovery.verifyVia),
      ...listOfStrings(discovery.verify_via),
      ...listOfStrings(manifestCrossService.verify_via),
    ]),
    followup_via: uniqueStrings([
      ...listOfStrings(manifest.followupVia),
      ...listOfStrings(manifest.followup_via),
      ...listOfStrings(discovery.followupVia),
      ...listOfStrings(discovery.followup_via),
      ...listOfStrings(manifestCrossService.followup_via),
    ]),
    cross_service_handoff: uniqueStrings([
      ...listOfStrings(manifestCrossService.handoff_to),
    ]),
    cross_service_refresh: uniqueStrings([
      ...listOfStrings(manifestCrossService.refresh_via),
    ]),
    cross_service_verify: uniqueStrings([
      ...listOfStrings(manifestCrossService.verify_via),
    ]),
    cross_service_followup: uniqueStrings([
      ...listOfStrings(manifestCrossService.followup_via),
    ]),
  }
}

function sanitizeObservedCapability(capability: any): ObservedServiceCapability {
  const item = extractCapabilityObject(capability)
  return {
    id: firstString(item.id) || 'unknown-capability',
    side_effect: firstString(item.side_effect, item.sideEffect) || null,
    minimum_scope: uniqueStrings([
      ...listOfStrings(item.minimum_scope),
      ...listOfStrings(item.minimumScope),
    ]),
    financial: Boolean(item.financial),
    contract: firstString(item.contract, item.contract?.name) || null,
    requires_binding: uniqueStrings([
      ...listOfStrings(item.requires_binding),
      ...listOfStrings(item.requiresBinding),
    ]),
    control_requirements: uniqueStrings([
      ...listOfStrings(item.control_requirements),
      ...keysOfTruthyRecord(item.control_requirements),
      ...keysOfTruthyRecord(item.controlRequirements),
    ]),
    refresh_via: uniqueStrings([
      ...listOfStrings(item.refresh_via),
      ...listOfStrings(item.refreshVia),
    ]),
    verify_via: uniqueStrings([
      ...listOfStrings(item.verify_via),
      ...listOfStrings(item.verifyVia),
    ]),
    followup_via: uniqueStrings([
      ...listOfStrings(item.followup_via),
      ...listOfStrings(item.followupVia),
    ]),
    cross_service_handoff: uniqueStrings([
      ...listOfStrings(item.cross_service_handoff),
      ...listOfStrings(item.crossServiceHandoff),
    ]),
    cross_service_refresh: uniqueStrings([
      ...listOfStrings(item.cross_service_refresh),
      ...listOfStrings(item.crossServiceRefresh),
    ]),
    cross_service_verify: uniqueStrings([
      ...listOfStrings(item.cross_service_verify),
      ...listOfStrings(item.crossServiceVerify),
    ]),
    cross_service_followup: uniqueStrings([
      ...listOfStrings(item.cross_service_followup),
      ...listOfStrings(item.crossServiceFollowup),
    ]),
  }
}

function sanitizeObservedMetadata(observed: ObservedServiceMetadata): ObservedServiceMetadata {
  return {
    ...observed,
    source: observed.source || 'inspect_discovery',
    capabilities: Array.isArray(observed.capabilities)
      ? observed.capabilities.map((capability) => sanitizeObservedCapability(capability))
      : [],
  }
}

function mergeCapabilities(
  existing: ObservedServiceCapability[],
  incoming: ObservedServiceCapability[],
): ObservedServiceCapability[] {
  const map = new Map<string, ObservedServiceCapability>()

  for (const capability of existing) {
    map.set(capability.id, {
      ...capability,
      minimum_scope: [...capability.minimum_scope],
      requires_binding: [...capability.requires_binding],
      control_requirements: [...capability.control_requirements],
      refresh_via: [...capability.refresh_via],
      verify_via: [...capability.verify_via],
      followup_via: [...capability.followup_via],
      cross_service_handoff: [...capability.cross_service_handoff],
      cross_service_refresh: [...capability.cross_service_refresh],
      cross_service_verify: [...capability.cross_service_verify],
      cross_service_followup: [...capability.cross_service_followup],
    })
  }

  for (const capability of incoming) {
    const prior = map.get(capability.id)
    if (!prior) {
      map.set(capability.id, {
        ...capability,
        minimum_scope: [...capability.minimum_scope],
        requires_binding: [...capability.requires_binding],
        control_requirements: [...capability.control_requirements],
        refresh_via: [...capability.refresh_via],
        verify_via: [...capability.verify_via],
        followup_via: [...capability.followup_via],
        cross_service_handoff: [...capability.cross_service_handoff],
        cross_service_refresh: [...capability.cross_service_refresh],
        cross_service_verify: [...capability.cross_service_verify],
        cross_service_followup: [...capability.cross_service_followup],
      })
      continue
    }

    map.set(capability.id, {
      ...prior,
      ...capability,
      side_effect: capability.side_effect ?? prior.side_effect ?? null,
      contract: capability.contract ?? prior.contract ?? null,
      financial: capability.financial || prior.financial,
      minimum_scope: uniqueStrings([...prior.minimum_scope, ...capability.minimum_scope]),
      requires_binding: uniqueStrings([...prior.requires_binding, ...capability.requires_binding]),
      control_requirements: uniqueStrings([...prior.control_requirements, ...capability.control_requirements]),
      refresh_via: uniqueStrings([...prior.refresh_via, ...capability.refresh_via]),
      verify_via: uniqueStrings([...prior.verify_via, ...capability.verify_via]),
      followup_via: uniqueStrings([...prior.followup_via, ...capability.followup_via]),
      cross_service_handoff: uniqueStrings([...prior.cross_service_handoff, ...capability.cross_service_handoff]),
      cross_service_refresh: uniqueStrings([...prior.cross_service_refresh, ...capability.cross_service_refresh]),
      cross_service_verify: uniqueStrings([...prior.cross_service_verify, ...capability.cross_service_verify]),
      cross_service_followup: uniqueStrings([...prior.cross_service_followup, ...capability.cross_service_followup]),
    })
  }

  return Array.from(map.values())
}

function mergedSource(
  existing?: ObservedServiceMetadata['source'] | null,
  incoming?: ObservedServiceMetadata['source'] | null,
): ObservedServiceMetadata['source'] {
  if (existing === 'inspect_discovery_manifest' || incoming === 'inspect_discovery_manifest') {
    return 'inspect_discovery_manifest'
  }
  if (existing && incoming && existing !== incoming) return 'inspect_discovery_manifest'
  return incoming || existing || 'inspect_discovery'
}

function relevantCapabilities(
  observed: ObservedServiceMetadata,
  intendedCapabilityIds: string[],
): ObservedServiceCapability[] {
  const intended = observed.capabilities.filter((capability) => intendedCapabilityIds.includes(capability.id))
  return intended.length ? intended : observed.capabilities
}

function describeCoverage(label: string, supported: number, total: number): string {
  if (supported >= total) return `${label} observed for all relevant capabilities.`
  if (supported === 0) return `${label} was not visible in the observed service metadata.`
  return `${label} observed for ${supported} of ${total} relevant capabilities.`
}

function summarizeSurfaceEvidence(
  surface: string,
  supported: number,
  total: number,
  detailWhenMissing?: string,
): SurfaceEvidence {
  if (total === 0) {
    return {
      surface,
      status: 'needs_deeper_inspection',
      detail: 'No relevant capabilities were available to validate this surface.',
    }
  }
  if (supported >= total) {
    return { surface, status: 'observed', detail: describeCoverage(surface, supported, total) }
  }
  if (supported > 0) {
    return { surface, status: 'partially_observed', detail: describeCoverage(surface, supported, total) }
  }
  return {
    surface,
    status: 'not_observed',
    detail: detailWhenMissing || describeCoverage(surface, supported, total),
  }
}

function deriveSurfaceEvidence(
  surfaces: string[],
  observed: ObservedServiceMetadata,
  intendedCapabilityIds: string[],
): SurfaceEvidence[] {
  const capabilities = relevantCapabilities(observed, intendedCapabilityIds)

  return surfaces.map((surface) => {
    if (surface === 'binding_requirements') {
      const supported = capabilities.filter((capability) => capability.requires_binding.length > 0 || capability.contract).length
      return summarizeSurfaceEvidence(
        surface,
        supported,
        capabilities.length,
        'No binding requirements or contracts were visible in the observed service metadata.',
      )
    }
    if (surface === 'authority_posture') {
      const supported = capabilities.filter((capability) => capability.minimum_scope.length > 0).length
      return summarizeSurfaceEvidence(
        surface,
        supported,
        capabilities.length,
        'No minimum scope requirements were visible in the observed service metadata.',
      )
    }
    if (surface === 'refresh_via') {
      const supported = capabilities.filter((capability) => capability.refresh_via.length > 0 || capability.cross_service_refresh.length > 0).length
      return summarizeSurfaceEvidence(surface, supported, capabilities.length)
    }
    if (surface === 'verify_via') {
      const supported = capabilities.filter((capability) => capability.verify_via.length > 0 || capability.cross_service_verify.length > 0).length
      return summarizeSurfaceEvidence(surface, supported, capabilities.length)
    }
    if (surface === 'followup_via') {
      const supported = capabilities.filter((capability) => capability.followup_via.length > 0 || capability.cross_service_followup.length > 0).length
      return summarizeSurfaceEvidence(surface, supported, capabilities.length)
    }
    if (surface === 'cross_service_handoff') {
      const supported = capabilities.filter((capability) => capability.cross_service_handoff.length > 0).length
      return summarizeSurfaceEvidence(surface, supported, capabilities.length)
    }
    if (surface === 'cross_service_continuity') {
      const supported = capabilities.filter((capability) =>
        capability.cross_service_handoff.length > 0 ||
        capability.cross_service_refresh.length > 0 ||
        capability.cross_service_verify.length > 0 ||
        capability.cross_service_followup.length > 0,
      ).length
      return summarizeSurfaceEvidence(surface, supported, capabilities.length)
    }
    if (surface === 'cross_service_reconstruction') {
      const supported = capabilities.filter((capability) =>
        capability.cross_service_refresh.length > 0 || capability.cross_service_verify.length > 0,
      ).length
      return summarizeSurfaceEvidence(surface, supported, capabilities.length)
    }
    if (surface === 'budget_enforcement') {
      const supported = capabilities.filter((capability) =>
        capability.control_requirements.some((item) => item.includes('budget') || item.includes('spend')),
      ).length
      return summarizeSurfaceEvidence(surface, supported, capabilities.length)
    }
    if (surface === 'recovery_class') {
      const supported = capabilities.filter((capability) =>
        capability.control_requirements.some((item) => item.includes('recovery') || item.includes('retry')),
      ).length
      return summarizeSurfaceEvidence(surface, supported, capabilities.length)
    }
    return {
      surface,
      status: 'needs_deeper_inspection',
      detail: 'This surface needs manifest or runtime inspection beyond the currently observed metadata.',
    }
  })
}

function buildConformanceChecks(
  intended: IntendedDesignMetadata,
  observed: ObservedServiceMetadata,
  surfaceEvidence: SurfaceEvidence[],
): ConformanceCheck[] {
  const capabilities = relevantCapabilities(observed, intended.capabilities)
  const alignedCapabilities = capabilities.filter((capability) => intended.capabilities.includes(capability.id))
  const targetCapabilities = alignedCapabilities.length ? alignedCapabilities : capabilities
  const checks: ConformanceCheck[] = []
  const hasManifest = observed.source === 'inspect_manifest' || observed.source === 'inspect_discovery_manifest'
  const hasDiscovery = observed.source === 'inspect_discovery' || observed.source === 'inspect_discovery_manifest'

  checks.push({
    id: 'protocol_declared',
    label: 'Protocol declared',
    status: observed.protocol ? 'conformant' : 'non_conformant',
    detail: observed.protocol
      ? `Observed protocol ${observed.protocol}.`
      : 'No ANIP protocol was visible in the observed service metadata.',
    source: hasManifest && hasDiscovery ? 'combined' : hasManifest ? 'manifest' : 'discovery',
  })

  checks.push({
    id: 'service_identity_declared',
    label: 'Service identity declared',
    status: observed.service_id ? 'conformant' : 'non_conformant',
    detail: observed.service_id
      ? `Observed service identity ${observed.service_id}.`
      : 'No stable service identity was visible in the observed metadata.',
    source: hasManifest && hasDiscovery ? 'combined' : hasManifest ? 'manifest' : 'discovery',
  })

  checks.push({
    id: 'manifest_signature_present',
    label: 'Manifest signature present',
    status: !hasManifest
      ? 'insufficient_metadata'
      : observed.signature_present
        ? 'conformant'
        : 'non_conformant',
    detail: !hasManifest
      ? 'Manifest metadata was not loaded, so signature conformance could not be checked.'
      : observed.signature_present
        ? 'Observed a manifest signature.'
        : 'Manifest metadata was loaded but no signature was present.',
    source: 'manifest',
  })

  checks.push({
    id: 'jwks_uri_declared',
    label: 'JWKS URI declared',
    status: !hasManifest
      ? 'insufficient_metadata'
      : observed.jwks_uri_present
        ? 'conformant'
        : 'non_conformant',
    detail: !hasManifest
      ? 'Manifest metadata was not loaded, so JWKS declaration could not be checked.'
      : observed.jwks_uri_present
        ? 'Observed a JWKS URI in service identity metadata.'
        : 'Manifest service identity did not include a JWKS URI.',
    source: 'manifest',
  })

  checks.push({
    id: 'trust_posture_declared',
    label: 'Trust posture declared',
    status: observed.trust_level ? 'conformant' : 'non_conformant',
    detail: observed.trust_level
      ? `Observed trust posture ${observed.trust_level}.`
      : 'No trust posture was visible in the observed service metadata.',
    source: hasManifest && hasDiscovery ? 'combined' : hasManifest ? 'manifest' : 'discovery',
  })

  const contractCoverage = targetCapabilities.filter((capability) => Boolean(capability.contract)).length
  checks.push({
    id: 'capability_contracts_declared',
    label: 'Capability contracts declared',
    status: targetCapabilities.length === 0
      ? 'insufficient_metadata'
      : contractCoverage === targetCapabilities.length
        ? 'conformant'
        : 'non_conformant',
    detail: targetCapabilities.length === 0
      ? 'No relevant capabilities were available to validate capability contracts.'
      : describeCoverage('Capability contracts', contractCoverage, targetCapabilities.length),
    source: hasManifest ? 'combined' : 'discovery',
  })

  for (const evidence of surfaceEvidence) {
    checks.push({
      id: `${evidence.surface}_surface`,
      label: `${evidence.surface.replace(/_/g, ' ')} surface`,
      status:
        evidence.status === 'observed'
          ? 'conformant'
          : evidence.status === 'needs_deeper_inspection'
            ? 'insufficient_metadata'
            : 'non_conformant',
      detail: evidence.detail,
      source: evidence.status === 'needs_deeper_inspection' ? 'combined' : hasManifest && hasDiscovery ? 'combined' : hasManifest ? 'manifest' : 'discovery',
      related_surface: evidence.surface,
    })
  }

  return checks
}

export function buildObservedServiceMetadataArtifactId(metadata: {
  service_id?: string | null
  base_url?: string | null
}): string {
  const suffix = slugPart(metadata.service_id || metadata.base_url || 'service')
  return `service-metadata-${suffix || 'service'}`
}

export function buildObservedServiceMetadataTitle(metadata: {
  service_id?: string | null
  base_url?: string | null
}): string {
  const label = metadata.service_id || metadata.base_url || 'Connected Service'
  return `Observed Service Metadata: ${label}`
}

export function normalizeInspectionToObservedServiceMetadata(input: {
  discoveryDoc?: any
  manifestDoc?: any
  fallback?: { serviceId?: string | null; baseUrl?: string | null }
}): ObservedServiceMetadata | null {
  const discoveryDoc = input.discoveryDoc && typeof input.discoveryDoc === 'object' ? input.discoveryDoc : null
  const manifestDoc = input.manifestDoc && typeof input.manifestDoc === 'object' ? input.manifestDoc : null
  const fallback = input.fallback || {}
  if (!discoveryDoc && !manifestDoc) return null

  const rawManifest = extractRawManifest(manifestDoc)
  const manifestCapabilities = asObject(manifestDoc?.capabilities || rawManifest.capabilities)
  const discoveryCapabilities = asObject(discoveryDoc?.capabilities)
  const capabilityIds = uniqueStrings([
    ...Object.keys(discoveryCapabilities),
    ...Object.keys(manifestCapabilities),
  ])

  const capabilities = capabilityIds.map((id) =>
    normalizeCapability(id, discoveryCapabilities[id], manifestCapabilities[id]))

  const manifestIdentity = asObject(manifestDoc?.serviceIdentity || rawManifest.service_identity)
  const discoveryIdentity = asObject(discoveryDoc?.serviceIdentity || discoveryDoc?.service_identity)
  const manifestTrust = asObject(manifestDoc?.trust || rawManifest.trust)
  const discoveryPosture = asObject(discoveryDoc?.posture)

  const source: ObservedServiceMetadata['source'] =
    discoveryDoc && manifestDoc
      ? 'inspect_discovery_manifest'
      : manifestDoc
        ? 'inspect_manifest'
        : 'inspect_discovery'

  return {
    source,
    observed_at: new Date().toISOString(),
    service_id: firstString(
      discoveryIdentity.id,
      manifestIdentity.id,
      fallback.serviceId,
    ),
    base_url: firstString(
      discoveryDoc?.baseUrl,
      rawManifest.base_url,
      fallback.baseUrl,
    ),
    protocol: firstString(manifestDoc?.protocol, rawManifest.protocol, discoveryDoc?.protocol),
    profile: firstString(rawManifest.profile, manifestDoc?.profile),
    compliance: firstString(discoveryDoc?.compliance, rawManifest.compliance),
    trust_level: firstString(discoveryDoc?.trustLevel, manifestTrust.level),
    audit_retention: firstString(
      discoveryPosture.audit?.retention,
      rawManifest.posture?.audit?.retention,
    ),
    failure_detail_level: firstString(
      discoveryPosture.failure_disclosure?.detail_level,
      rawManifest.posture?.failure_disclosure?.detail_level,
    ),
    anchoring_enabled: firstBoolean(
      discoveryPosture.anchoring?.enabled,
      manifestTrust.anchoring?.enabled,
      typeof manifestTrust.anchoring?.cadence === 'string' ? true : null,
    ),
    signature_present: manifestDoc ? Boolean(firstString(manifestDoc?.signature, rawManifest?.signature)) : null,
    manifest_version: firstString(manifestDoc?.manifestMetadata?.version, rawManifest.manifest_metadata?.version),
    issuer_mode: firstString(manifestIdentity.issuer_mode),
    jwks_uri_present: manifestDoc ? Boolean(firstString(manifestIdentity.jwks_uri)) : null,
    capabilities,
  }
}

export function normalizeDiscoveryToObservedServiceMetadata(
  discoveryDoc: any,
  fallback: { serviceId?: string | null; baseUrl?: string | null } = {},
): ObservedServiceMetadata | null {
  return normalizeInspectionToObservedServiceMetadata({ discoveryDoc, fallback })
}

export function normalizeManifestToObservedServiceMetadata(
  manifestDoc: any,
  fallback: { serviceId?: string | null; baseUrl?: string | null } = {},
): ObservedServiceMetadata | null {
  return normalizeInspectionToObservedServiceMetadata({ manifestDoc, fallback })
}

export function mergeObservedServiceMetadata(
  existing: ObservedServiceMetadata | null,
  incoming: ObservedServiceMetadata | null,
): ObservedServiceMetadata | null {
  if (!existing) return incoming
  if (!incoming) return existing

  return {
    source: mergedSource(existing.source, incoming.source),
    observed_at: incoming.observed_at || existing.observed_at,
    service_id: incoming.service_id || existing.service_id || null,
    base_url: incoming.base_url || existing.base_url || null,
    protocol: incoming.protocol || existing.protocol || null,
    profile: incoming.profile || existing.profile || null,
    compliance: incoming.compliance || existing.compliance || null,
    trust_level: incoming.trust_level || existing.trust_level || null,
    audit_retention: incoming.audit_retention || existing.audit_retention || null,
    failure_detail_level: incoming.failure_detail_level || existing.failure_detail_level || null,
    anchoring_enabled: incoming.anchoring_enabled ?? existing.anchoring_enabled ?? null,
    signature_present: incoming.signature_present ?? existing.signature_present ?? null,
    manifest_version: incoming.manifest_version || existing.manifest_version || null,
    issuer_mode: incoming.issuer_mode || existing.issuer_mode || null,
    jwks_uri_present: incoming.jwks_uri_present ?? existing.jwks_uri_present ?? null,
    capabilities: mergeCapabilities(existing.capabilities || [], incoming.capabilities || []),
  }
}

export function selectObservedServiceMetadata(
  artifacts: ArtifactRecord[],
  preference: { serviceId?: string | null; baseUrl?: string | null } = {},
): ObservedServiceMetadata | null {
  if (!artifacts.length) return null
  const selected = findObservedServiceMetadataArtifact(artifacts, preference)
  return selected?.data ? selected.data as ObservedServiceMetadata : null
}

export function findObservedServiceMetadataArtifact(
  artifacts: ArtifactRecord[],
  preference: { serviceId?: string | null; baseUrl?: string | null } = {},
): ArtifactRecord | null {
  if (!artifacts.length) return null
  const byId = preference.serviceId
    ? artifacts.find((item) => item.data?.service_id === preference.serviceId)
    : null
  if (byId) return byId

  const byBaseUrl = preference.baseUrl
    ? artifacts.find((item) => item.data?.base_url === preference.baseUrl)
    : null
  if (byBaseUrl) return byBaseUrl

  return artifacts[0] ?? null
}

export function extractIntendedDesignMetadata(input: {
  scenario?: Record<string, any> | null
  proposal?: Record<string, any> | null
  shape?: Record<string, any> | null
}): IntendedDesignMetadata {
  const scenario = asObject(input.scenario, 'scenario')
  const proposal = asObject(input.proposal, 'proposal')
  const shape = asObject(input.shape, 'shape')
  const services = Array.isArray(shape.services) ? shape.services : []

  const intendedCapabilities = uniqueStrings([
    ...services.flatMap((service: any) =>
      Array.isArray(service?.capabilities) ? service.capabilities.map((item: any) => String(item)) : [],
    ),
    scenario?.context?.capability,
  ])

  const declaredSurfaces = Object.entries(proposal?.declared_surfaces || {})
    .filter(([, enabled]) => Boolean(enabled))
    .map(([key]) => key)

  return {
    shape_type: shape?.type || proposal?.recommended_shape || null,
    services: uniqueStrings(services.map((service: any) => service?.name || service?.id)),
    capabilities: intendedCapabilities,
    declared_surfaces: declaredSurfaces,
  }
}

export function compareIntendedToObservedMetadata(input: {
  scenario?: Record<string, any> | null
  proposal?: Record<string, any> | null
  shape?: Record<string, any> | null
  observed: ObservedServiceMetadata
}): ServiceMetadataComparison {
  const intended = extractIntendedDesignMetadata(input)
  const observed = sanitizeObservedMetadata(input.observed)
  const observedCapabilities = uniqueStrings(observed.capabilities.map((capability) => capability.id))
  const alignedCapabilities = intended.capabilities.filter((capability) => observedCapabilities.includes(capability))
  const missingCapabilities = intended.capabilities.filter((capability) => !observedCapabilities.includes(capability))
  const extraCapabilities = observedCapabilities.filter((capability) => !intended.capabilities.includes(capability))
  const surfaceEvidence = deriveSurfaceEvidence(intended.declared_surfaces, observed, intended.capabilities)

  return {
    intended,
    observed,
    aligned_capabilities: alignedCapabilities,
    missing_capabilities: missingCapabilities,
    extra_capabilities: extraCapabilities,
    surface_evidence: surfaceEvidence,
    conformance_checks: buildConformanceChecks(intended, observed, surfaceEvidence),
  }
}
