/**
 * Discovery normalization — maps raw ANIP discovery responses into a
 * consumer-friendly shape with resolved endpoints and capability lists.
 */

import type { NormalizedDiscovery } from "./types.js";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function stringRecord(value: unknown): Record<string, string> {
  const result: Record<string, string> = {};
  if (isRecord(value)) {
    for (const [key, entry] of Object.entries(value)) {
      if (typeof entry === "string") {
        result[key] = entry;
      }
    }
  }
  return result;
}

function optionalString(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined;
}

/**
 * Normalize a raw ANIP discovery document (SPEC.md §6.1).
 *
 * Wire format, as every runtime sends it:
 * ```json
 * {
 *   "anip_discovery": {
 *     "protocol": "anip/0.24",
 *     "compliance": "anip-compliant",
 *     "base_url": "https://flights.example.com",
 *     "profile": { "core": "1.0", "cost": "1.0" },
 *     "capabilities": {
 *       "search_flights": {
 *         "description": "Search available flights",
 *         "side_effect": "read",
 *         "minimum_scope": ["travel.search"],
 *         "financial": false,
 *         "contract": "1.0"
 *       }
 *     },
 *     "trust_level": "signed",
 *     "posture": { "audit": { "retention": "P90D" } },
 *     "endpoints": {
 *       "manifest": "/anip/manifest",
 *       "invoke": "/anip/invoke/{capability}",
 *       "permissions": "/anip/permissions",
 *       "tokens": "/anip/tokens"
 *     }
 *   }
 * }
 * ```
 *
 * Discovery carries lightweight capability metadata: `side_effect` is the
 * side-effect type as a string and the trust level is the top-level
 * `trust_level` string. The object forms (`side_effect: { type }`,
 * `trust: { level }`) belong to the manifest, not to this document.
 *
 * A field that is absent or not in the specified shape is reported as
 * `"unknown"` / `undefined` / empty. It is never replaced by a benign-looking
 * default: a capability whose side effect cannot be read must not be
 * presented as `"read"`.
 */
export function normalizeDiscovery(raw: unknown): NormalizedDiscovery {
  const doc = isRecord(raw) ? raw.anip_discovery : undefined;
  if (!isRecord(doc)) {
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

  const capabilities: NormalizedDiscovery["capabilities"] = {};
  if (isRecord(doc.capabilities)) {
    for (const [name, decl] of Object.entries(doc.capabilities)) {
      const rawDecl = isRecord(decl) ? decl : {};
      capabilities[name] = {
        name,
        description: optionalString(rawDecl.description),
        sideEffect: optionalString(rawDecl.side_effect) ?? "unknown",
        minimumScope: Array.isArray(rawDecl.minimum_scope)
          ? rawDecl.minimum_scope.filter((value): value is string => typeof value === "string")
          : [],
        financial: rawDecl.financial === true,
        contract: optionalString(rawDecl.contract),
        raw: rawDecl,
      };
    }
  }

  return {
    protocol: optionalString(doc.protocol) ?? "unknown",
    compliance: optionalString(doc.compliance) ?? "unknown",
    trustLevel: optionalString(doc.trust_level),
    baseUrl: optionalString(doc.base_url),
    endpoints: stringRecord(doc.endpoints),
    profiles: stringRecord(doc.profile),
    capabilityNames: Object.keys(capabilities),
    capabilities,
    posture: isRecord(doc.posture) ? doc.posture : undefined,
    raw: doc,
  };
}
