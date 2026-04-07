/**
 * Discovery normalization — maps raw ANIP discovery responses into a
 * consumer-friendly shape with resolved endpoints and capability lists.
 */

import type { NormalizedDiscovery } from "./types.js";

/**
 * Normalize a raw ANIP discovery document.
 *
 * Expected wire format:
 * ```json
 * {
 *   "protocol": "anip/0.22",
 *   "compliance": "full",
 *   "trust": { "level": "signed" },
 *   "endpoints": {
 *     "manifest": "/anip/manifest",
 *     "invoke": "/anip/invoke/{capability}",
 *     "permissions": "/anip/permissions",
 *     "token": "/anip/token",
 *     "audit": "/anip/audit",
 *     "graph": "/anip/graph/{capability}",
 *     "checkpoints": "/anip/checkpoints"
 *   },
 *   "profiles": { "core": "1.0", "cost": "1.0" },
 *   "capabilities": ["search_flights", "book_flight"]
 * }
 * ```
 */
export function normalizeDiscovery(raw: any): NormalizedDiscovery {
  if (!raw || typeof raw !== "object") {
    return {
      protocol: "unknown",
      compliance: "unknown",
      endpoints: {},
      profiles: {},
      capabilities: [],
    };
  }

  // Real ANIP discovery wraps everything in `anip_discovery`.
  const doc = raw.anip_discovery ?? raw;

  const endpoints: Record<string, string> = {};
  if (doc.endpoints && typeof doc.endpoints === "object") {
    for (const [key, value] of Object.entries(doc.endpoints)) {
      if (typeof value === "string") {
        endpoints[key] = value;
      }
    }
  }

  const profiles: Record<string, string> = {};
  // Accept both `profile` (spec) and `profiles` (common variant).
  const profileSource = doc.profile ?? doc.profiles;
  if (profileSource && typeof profileSource === "object") {
    for (const [key, value] of Object.entries(profileSource)) {
      if (typeof value === "string") {
        profiles[key] = value;
      }
    }
  }

  // Capabilities can be:
  // - an array of strings: ["search_flights", "book_flight"]
  // - an object map: { search_flights: { contract: "1.0", ... }, ... }
  let capabilities: string[] = [];
  if (Array.isArray(doc.capabilities)) {
    capabilities = doc.capabilities.filter((c: unknown) => typeof c === "string");
  } else if (doc.capabilities && typeof doc.capabilities === "object") {
    capabilities = Object.keys(doc.capabilities);
  }

  return {
    protocol: doc.protocol ?? "unknown",
    compliance: doc.compliance ?? "unknown",
    trustLevel: doc.trust?.level ?? undefined,
    endpoints,
    profiles,
    capabilities,
  };
}
