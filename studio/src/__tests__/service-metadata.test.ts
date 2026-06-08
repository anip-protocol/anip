import { describe, expect, it } from 'vitest'
import {
  buildObservedServiceMetadataArtifactId,
  compareIntendedToObservedMetadata,
  extractIntendedDesignMetadata,
  mergeObservedServiceMetadata,
  normalizeInspectionToObservedServiceMetadata,
  selectObservedServiceMetadata,
} from '../design/service-metadata'

describe('service metadata helpers', () => {
  it('normalizes combined discovery and manifest metadata into observed service metadata', () => {
    const observed = normalizeInspectionToObservedServiceMetadata({
      discoveryDoc: {
        protocol: 'anip/0.2',
        compliance: 'full',
        trustLevel: 'anchored',
        baseUrl: 'http://localhost:9100',
        serviceIdentity: { id: 'svc-booking' },
        posture: {
          audit: { retention: '30d' },
          failure_disclosure: { detail_level: 'summary' },
          anchoring: { enabled: true },
        },
        capabilities: {
          'booking.search': {
            sideEffect: 'read',
            minimumScope: ['bookings.read'],
            financial: false,
            contract: 'BookingSearch',
          },
        },
      },
      manifestDoc: {
        protocol: 'anip/0.2',
        signature: 'sig-demo',
        manifestMetadata: { version: '1' },
        serviceIdentity: {
          id: 'svc-booking',
          jwks_uri: 'http://localhost:9100/.well-known/jwks.json',
          issuer_mode: 'self',
        },
        trust: {
          level: 'anchored',
          anchoring: { cadence: 'daily' },
        },
        capabilities: {
          'booking.search': {
            raw: {
              requires_binding: ['customer_binding'],
              control_requirements: {
                recovery_class: true,
                budget_enforcement: true,
              },
              verify_via: ['booking.verify'],
            },
          },
        },
      },
    })

    expect(observed).toEqual(expect.objectContaining({
      source: 'inspect_discovery_manifest',
      service_id: 'svc-booking',
      protocol: 'anip/0.2',
      trust_level: 'anchored',
      audit_retention: '30d',
      failure_detail_level: 'summary',
      anchoring_enabled: true,
      signature_present: true,
      manifest_version: '1',
      issuer_mode: 'self',
      jwks_uri_present: true,
    }))
    expect(observed?.capabilities).toEqual([
      expect.objectContaining({
        id: 'booking.search',
        side_effect: 'read',
        minimum_scope: ['bookings.read'],
        contract: 'BookingSearch',
        requires_binding: ['customer_binding'],
        control_requirements: ['recovery_class', 'budget_enforcement'],
        verify_via: ['booking.verify'],
      }),
    ])
  })

  it('merges observed metadata artifacts from discovery and manifest inspection', () => {
    const merged = mergeObservedServiceMetadata(
      {
        source: 'inspect_discovery',
        observed_at: '2026-04-11T12:00:00Z',
        service_id: 'svc-gtm',
        protocol: 'anip/0.2',
        capabilities: [
          {
            id: 'gtm.account_risk_summary',
            minimum_scope: ['accounts.read'],
            financial: false,
            contract: null,
            requires_binding: [],
            control_requirements: [],
            refresh_via: [],
            verify_via: [],
            followup_via: [],
            cross_service_handoff: [],
            cross_service_refresh: [],
            cross_service_verify: [],
            cross_service_followup: [],
          },
        ],
      },
      {
        source: 'inspect_manifest',
        observed_at: '2026-04-11T12:05:00Z',
        service_id: 'svc-gtm',
        manifest_version: '1',
        signature_present: true,
        capabilities: [
          {
            id: 'gtm.account_risk_summary',
            minimum_scope: [],
            financial: false,
            contract: 'AccountRiskSummary',
            requires_binding: ['account_binding'],
            control_requirements: ['recovery_class'],
            refresh_via: [],
            verify_via: ['gtm.verify_outcome'],
            followup_via: [],
            cross_service_handoff: [],
            cross_service_refresh: [],
            cross_service_verify: [],
            cross_service_followup: [],
          },
        ],
      },
    )

    expect(merged).toEqual(expect.objectContaining({
      source: 'inspect_discovery_manifest',
      manifest_version: '1',
      signature_present: true,
    }))
    expect(merged?.capabilities).toEqual([
      expect.objectContaining({
        id: 'gtm.account_risk_summary',
        minimum_scope: ['accounts.read'],
        contract: 'AccountRiskSummary',
        requires_binding: ['account_binding'],
        control_requirements: ['recovery_class'],
        verify_via: ['gtm.verify_outcome'],
      }),
    ])
  })

  it('compares intended design metadata against observed capabilities and conformance checks', () => {
    const intended = extractIntendedDesignMetadata({
      scenario: {
        scenario: {
          context: {
            capability: 'gtm.account_risk_summary',
          },
        },
      },
      proposal: {
        proposal: {
          recommended_shape: 'single_service',
          declared_surfaces: {
            authority_posture: true,
            binding_requirements: true,
            verify_via: true,
          },
        },
      },
      shape: {
        shape: {
          type: 'governed_capability',
          services: [
            {
              name: 'gtm-core',
              capabilities: ['gtm.account_risk_summary', 'gtm.prepare_followup_tasks'],
            },
          ],
        },
      },
    })

    expect(intended).toEqual({
      shape_type: 'governed_capability',
      services: ['gtm-core'],
      capabilities: ['gtm.account_risk_summary', 'gtm.prepare_followup_tasks'],
      declared_surfaces: ['authority_posture', 'binding_requirements', 'verify_via'],
    })

    const comparison = compareIntendedToObservedMetadata({
      scenario: {
        scenario: {
          context: { capability: 'gtm.account_risk_summary' },
        },
      },
      proposal: {
        proposal: {
          declared_surfaces: {
            authority_posture: true,
            binding_requirements: true,
            verify_via: true,
          },
        },
      },
      shape: {
        shape: {
          type: 'governed_capability',
          services: [
            {
              name: 'gtm-core',
              capabilities: ['gtm.account_risk_summary', 'gtm.prepare_followup_tasks'],
            },
          ],
        },
      },
      observed: {
        source: 'inspect_discovery_manifest',
        observed_at: '2026-04-11T12:00:00Z',
        service_id: 'svc-gtm',
        protocol: 'anip/0.2',
        profile: 'governed_capability',
        trust_level: 'anchored',
        signature_present: true,
        manifest_version: '1',
        jwks_uri_present: true,
        capabilities: [
          {
            id: 'gtm.account_risk_summary',
            minimum_scope: ['accounts.read'],
            financial: false,
            contract: 'AccountRiskSummary',
            requires_binding: ['account_binding'],
            control_requirements: ['recovery_class'],
            refresh_via: [],
            verify_via: ['gtm.verify_outcome'],
            followup_via: [],
            cross_service_handoff: [],
            cross_service_refresh: [],
            cross_service_verify: [],
            cross_service_followup: [],
          },
          {
            id: 'gtm.pipeline_summary',
            minimum_scope: ['pipeline.read'],
            financial: false,
            contract: 'PipelineSummary',
            requires_binding: [],
            control_requirements: [],
            refresh_via: [],
            verify_via: [],
            followup_via: [],
            cross_service_handoff: [],
            cross_service_refresh: [],
            cross_service_verify: [],
            cross_service_followup: [],
          },
        ],
      },
    })

    expect(comparison.aligned_capabilities).toEqual(['gtm.account_risk_summary'])
    expect(comparison.missing_capabilities).toEqual(['gtm.prepare_followup_tasks'])
    expect(comparison.extra_capabilities).toEqual(['gtm.pipeline_summary'])
    expect(comparison.surface_evidence).toEqual([
      expect.objectContaining({ surface: 'authority_posture', status: 'observed' }),
      expect.objectContaining({ surface: 'binding_requirements', status: 'observed' }),
      expect.objectContaining({ surface: 'verify_via', status: 'observed' }),
    ])
    expect(comparison.conformance_checks).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ id: 'protocol_declared', status: 'conformant' }),
        expect.objectContaining({ id: 'manifest_signature_present', status: 'conformant' }),
        expect.objectContaining({ id: 'jwks_uri_declared', status: 'conformant' }),
        expect.objectContaining({ id: 'binding_requirements_surface', status: 'conformant' }),
      ]),
    )
  })

  it('selects the persisted observed metadata artifact for the current service', () => {
    const selected = selectObservedServiceMetadata(
      [
        {
          id: buildObservedServiceMetadataArtifactId({ service_id: 'svc-other' }),
          project_id: 'proj-1',
          title: 'Observed Service Metadata: svc-other',
          status: 'active',
          content_hash: '',
          created_at: '2026-04-11T12:00:00Z',
          updated_at: '2026-04-11T12:00:00Z',
          data: {
            source: 'inspect_discovery',
            observed_at: '2026-04-11T12:00:00Z',
            service_id: 'svc-other',
            capabilities: [],
          },
        },
        {
          id: buildObservedServiceMetadataArtifactId({ service_id: 'svc-gtm' }),
          project_id: 'proj-1',
          title: 'Observed Service Metadata: svc-gtm',
          status: 'active',
          content_hash: '',
          created_at: '2026-04-11T12:00:00Z',
          updated_at: '2026-04-11T12:05:00Z',
          data: {
            source: 'inspect_discovery_manifest',
            observed_at: '2026-04-11T12:05:00Z',
            service_id: 'svc-gtm',
            capabilities: [{ id: 'gtm.account_risk_summary' }],
          },
        },
      ] as any,
      { serviceId: 'svc-gtm' },
    )

    expect(selected).toEqual(expect.objectContaining({
      service_id: 'svc-gtm',
    }))
  })
})
