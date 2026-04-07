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

  const endpoints: Record<string, string> = {};
  if (raw.endpoints && typeof raw.endpoints === "object") {
    for (const [key, value] of Object.entries(raw.endpoints)) {
      if (typeof value === "string") {
        endpoints[key] = value;
      }
    }
  }

  const profiles: Record<string, string> = {};
  if (raw.profiles && typeof raw.profiles === "object") {
    for (const [key, value] of Object.entries(raw.profiles)) {
      if (typeof value === "string") {
        profiles[key] = value;
      }
    }
  }
  // Also accept profile (singular) as some discovery docs use that key.
  if (!Object.keys(profiles).length && raw.profile && typeof raw.profile === "object") {
    for (const [key, value] of Object.entries(raw.profile)) {
      if (typeof value === "string") {
        profiles[key] = value;
      }
    }
  }

  const capabilities: string[] = Array.isArray(raw.capabilities)
    ? raw.capabilities.filter((c: unknown) => typeof c === "string")
    : [];

  return {
    protocol: raw.protocol ?? "unknown",
    compliance: raw.compliance ?? "unknown",
    trustLevel: raw.trust?.level ?? undefined,
    endpoints,
    profiles,
    capabilities,
  };
}
