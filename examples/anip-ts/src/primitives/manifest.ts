/**
 * Manifest and profile handshake.
 */

import { createHash } from "crypto";
import { DECLARATION as searchFlightsDeclaration } from "../capabilities/search-flights.js";
import { DECLARATION as bookFlightDeclaration } from "../capabilities/book-flight.js";
import type { ANIPManifest, TrustPosture, AnchoringPolicy } from "../types.js";

export function buildManifest(): ANIPManifest {
  const capabilities = {
    search_flights: searchFlightsDeclaration,
    book_flight: bookFlightDeclaration,
  };

  // Build trust posture from environment
  const trustLevel = (process.env.ANIP_TRUST_LEVEL ?? "signed") as TrustPosture["level"];
  let anchoring: AnchoringPolicy | null = null;
  if (trustLevel === "anchored" || trustLevel === "attested") {
    // cadence: ISO 8601 duration for max time between checkpoints
    const intervalStr = process.env.ANIP_CHECKPOINT_INTERVAL ?? null;
    const cadence = intervalStr ? `PT${intervalStr}S` : null;
    // max_lag: max uncheckpointed entry count from ANIP_CHECKPOINT_CADENCE
    const cadenceStr = process.env.ANIP_CHECKPOINT_CADENCE ?? null;
    const maxLag = cadenceStr ? parseInt(cadenceStr, 10) : null;
    // sink: qualifying URIs required for anchored (file:// is dev-only)
    const sinkEnv = process.env.ANIP_CHECKPOINT_SINK ?? null;
    const sink = sinkEnv ? sinkEnv.split(",").map((s) => s.trim()) : null;

    // Validate: anchored/attested requires at least one qualifying sink
    const QUALIFYING_SCHEMES = ["witness:", "https:"];
    const qualifying = (sink ?? []).filter((s) =>
      QUALIFYING_SCHEMES.some((p) => s.startsWith(p))
    );
    if (qualifying.length === 0) {
      throw new Error(
        `ANIP_TRUST_LEVEL=${trustLevel} requires ANIP_CHECKPOINT_SINK with at least one ` +
        `qualifying sink URI (witness: or https:). file:// sinks are non-qualifying per spec §7.6.`
      );
    }

    anchoring = { cadence, max_lag: maxLag, sink };
  }
  const trust: TrustPosture = { level: trustLevel, anchoring };

  // Compute sha256 over capabilities
  const capsJson = JSON.stringify(capabilities, Object.keys(capabilities).sort());
  const sha256 = createHash("sha256").update(capsJson).digest("hex");

  const now = new Date();
  const expiresAt = new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000); // 30 days

  return {
    protocol: "anip/0.3",
    profile: {
      core: "1.0",
      cost: "1.0",
      capability_graph: "1.0",
      state_session: "1.0",
      observability: "1.0",
    },
    capabilities,
    trust,
    service_identity: {
      id: "anip-flight-service",
      jwks_uri: "/.well-known/jwks.json",
      issuer_mode: "first-party",
    },
    manifest_metadata: {
      version: "0.3.0",
      sha256,
      issued_at: now.toISOString(),
      expires_at: expiresAt.toISOString(),
    },
  };
}
