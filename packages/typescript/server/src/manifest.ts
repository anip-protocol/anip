/**
 * Manifest builder for ANIP services.
 *
 * Fully parameterized — no environment variable parsing.
 */

import { createHash } from "crypto";
import {
  PROTOCOL_VERSION,
  MANIFEST_VERSION,
  DEFAULT_PROFILE,
} from "@anip/core";
import type {
  ANIPManifest as ANIPManifestType,
  CapabilityDeclaration as CapabilityDeclarationType,
  TrustPosture as TrustPostureType,
  ServiceIdentity as ServiceIdentityType,
} from "@anip/core";

export interface BuildManifestOpts {
  capabilities: Record<string, CapabilityDeclarationType>;
  trust: TrustPostureType;
  serviceIdentity: ServiceIdentityType;
  expiresDays?: number;
}

/**
 * Build an ANIP manifest from parameters (no env-var parsing).
 */
export function buildManifest(opts: BuildManifestOpts): ANIPManifestType {
  const { capabilities, trust, serviceIdentity, expiresDays = 30 } = opts;

  const capsJson = JSON.stringify(capabilities, Object.keys(capabilities).sort());
  const sha256 = createHash("sha256").update(capsJson).digest("hex");

  const now = new Date();
  const expiresAt = new Date(
    now.getTime() + expiresDays * 24 * 60 * 60 * 1000,
  );

  return {
    protocol: PROTOCOL_VERSION,
    profile: { ...DEFAULT_PROFILE },
    capabilities,
    manifest_metadata: {
      version: MANIFEST_VERSION,
      sha256,
      issued_at: now.toISOString(),
      expires_at: expiresAt.toISOString(),
    },
    service_identity: serviceIdentity,
    trust,
  } as ANIPManifestType;
}
