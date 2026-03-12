/**
 * Manifest and profile handshake.
 */

import { createHash } from "crypto";
import { DECLARATION as searchFlightsDeclaration } from "../capabilities/search-flights.js";
import { DECLARATION as bookFlightDeclaration } from "../capabilities/book-flight.js";
import type { ANIPManifest } from "../types.js";

export function buildManifest(): ANIPManifest {
  const capabilities = {
    search_flights: searchFlightsDeclaration,
    book_flight: bookFlightDeclaration,
  };

  // Compute sha256 over capabilities
  const capsJson = JSON.stringify(capabilities, Object.keys(capabilities).sort());
  const sha256 = createHash("sha256").update(capsJson).digest("hex");

  const now = new Date();
  const expiresAt = new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000); // 30 days

  return {
    protocol: "anip/0.2",
    profile: {
      core: "1.0",
      cost: "1.0",
      capability_graph: "1.0",
      state_session: "1.0",
      observability: "1.0",
    },
    capabilities,
    service_identity: {
      id: "anip-flight-service",
      jwks_uri: "/.well-known/jwks.json",
      issuer_mode: "first-party",
    },
    manifest_metadata: {
      version: "0.2.0",
      sha256,
      issued_at: now.toISOString(),
      expires_at: expiresAt.toISOString(),
    },
  };
}
