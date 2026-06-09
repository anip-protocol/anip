import { describe, expect, it } from 'vitest'
import { parseExternalCliResult, summarizeExternalCliResult } from '../design/external-cli-provenance'

const context = {
  publicationArtifactId: 'publication-1',
  packageId: 'work-item-fronting',
  packageVersion: '0.2.0',
  productRevision: {
    ref: 'product-r3',
    artifact_id: 'product-r3',
    revision_number: 3,
  },
  developerRevision: {
    ref: 'developer-r5',
    artifact_id: 'developer-r5',
    revision_number: 5,
    contract_signature: 'sha256:contract',
  },
  receiptSignature: 'sha256:receipt',
}

describe('external CLI provenance', () => {
  it('classifies matching verifier output as aligned', () => {
    const result = summarizeExternalCliResult({
      status: 'ok',
      package_id: 'work-item-fronting',
      package_version: '0.2.0',
      receipt_status: 'verified',
      registry_receipt_signature: 'sha256:receipt',
      registry_signing_mode: 'production',
      registry_active_key_id: 'registry-prod-2026-04',
      product_revision: {
        ref: 'product-r3',
        artifact_id: 'product-r3',
        revision_number: 3,
      },
      developer_revision: {
        ref: 'developer-r5',
        artifact_id: 'developer-r5',
        revision_number: 5,
      },
      checks: [{ name: 'registry_receipt_signature_valid', status: 'pass' }],
    }, context)

    expect(result.status).toBe('aligned')
    expect(result.sourceTool).toBe('anip-verify')
    expect(result.receiptStatus).toBe('verified')
    expect(result.registrySigningMode).toBe('production')
    expect(result.registryActiveKeyID).toBe('registry-prod-2026-04')
    expect(result.registryTrustPostureLabel).toBe('Trusted production Registry')
  })

  it('classifies Registry trust policy failures', () => {
    const result = summarizeExternalCliResult({
      status: 'failed',
      package_id: 'work-item-fronting',
      package_version: '0.2.0',
      receipt_status: 'verified',
      registry_receipt_signature: 'sha256:receipt',
      registry_signing_mode: 'dev',
      registry_active_key_id: 'anip-registry-dev-ed25519-v1',
      product_revision: context.productRevision,
      developer_revision: context.developerRevision,
      checks: [
        { name: 'registry_receipt_signature_valid', status: 'pass' },
        { name: 'registry_trust_policy_signing_mode_matches', status: 'fail' },
      ],
    }, context)

    expect(result.status).toBe('mismatch')
    expect(result.registryTrustPostureLabel).toBe('Untrusted / policy mismatch')
    expect(result.registryTrustPostureDetail).toContain('registry_trust_policy_signing_mode_matches')
  })

  it('classifies package mismatch as mismatch', () => {
    const result = summarizeExternalCliResult({
      status: 'ok',
      package_id: 'other-package',
      package_version: '0.2.0',
      receipt_status: 'verified',
      registry_receipt_signature: 'sha256:receipt',
      product_revision: context.productRevision,
      developer_revision: context.developerRevision,
    }, context)

    expect(result.status).toBe('mismatch')
  })

  it('classifies missing revision lineage as incomplete', () => {
    const result = summarizeExternalCliResult({
      status: 'ok',
      package_id: 'work-item-fronting',
      package_version: '0.2.0',
      receipt_status: 'verified',
      registry_receipt_signature: 'sha256:receipt',
    }, context)

    expect(result.status).toBe('incomplete')
  })

  it('requires package identity when parsing raw JSON', () => {
    expect(() => parseExternalCliResult('{"status":"ok"}')).toThrow(/package_id/)
  })
})
