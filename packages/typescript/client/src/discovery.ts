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
      capabilityNames: [],
      endpoints: {},
      profiles: {},
      capabilities: {},
      raw: {},
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
  let capabilityNames: string[] = [];
  const capabilities: NormalizedDiscovery["capabilities"] = {};
  if (Array.isArray(doc.capabilities)) {
    capabilityNames = doc.capabilities.filter((c: unknown) => typeof c === "string");
    for (const name of capabilityNames) {
      capabilities[name] = {
        name,
        sideEffect: "read",
        minimumScope: [],
        financial: false,
        raw: {},
      };
    }
  } else if (doc.capabilities && typeof doc.capabilities === "object") {
    capabilityNames = Object.keys(doc.capabilities);
    for (const [name, decl] of Object.entries(doc.capabilities)) {
      const rawDecl = decl && typeof decl === "object" ? (decl as Record<string, unknown>) : {};
      capabilities[name] = {
        name,
        sideEffect:
          typeof rawDecl.side_effect === "object" &&
          rawDecl.side_effect &&
          typeof (rawDecl.side_effect as { type?: unknown }).type === "string"
            ? ((rawDecl.side_effect as { type: string }).type)
            : "read",
        minimumScope: Array.isArray(rawDecl.minimum_scope)
          ? rawDecl.minimum_scope.filter((value): value is string => typeof value === "string")
          : [],
        financial: Boolean(rawDecl.financial || (rawDecl.cost as any)?.financial),
        contract: typeof rawDecl.contract === "string" ? rawDecl.contract : undefined,
        raw: rawDecl,
      };
    }
  }

  return {
    protocol: doc.protocol ?? "unknown",
    compliance: doc.compliance ?? "unknown",
    trustLevel: doc.trust?.level ?? undefined,
    baseUrl: doc.base_url ?? undefined,
    endpoints,
    profiles,
    capabilityNames,
    capabilities,
    posture: doc.posture ?? undefined,
    raw: doc,
  };
}
