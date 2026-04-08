/**
 * Permission normalization — maps raw ANIP permission query responses
 * into a consumer-friendly shape with available/restricted/denied lists.
 */

import type { NormalizedPermissions } from "./types.js";

/**
 * Normalize a raw ANIP permission response payload.
 *
 * Expected wire format:
 * ```json
 * {
 *   "available": [{ "capability": "search_flights", "scope_match": "..." }],
 *   "restricted": [{ "capability": "book_flight", "reason_type": "scope_insufficient", "resolution_hint": "..." }],
 *   "denied": [{ "capability": "admin_override", "reason_type": "non_delegable_action" }]
 * }
 * ```
 */
export function normalizePermissions(raw: any): NormalizedPermissions {
  if (!raw || typeof raw !== "object") {
    return { available: [], restricted: [], denied: [] };
  }

  const available: NormalizedPermissions["available"] = Array.isArray(raw.available)
    ? raw.available.map((a: any) => ({
        capability: a.capability ?? a,
        scopeMatch: a.scope_match ?? undefined,
      }))
    : [];

  const restricted: NormalizedPermissions["restricted"] = Array.isArray(
    raw.restricted,
  )
    ? raw.restricted.map((r: any) => ({
        capability: r.capability,
        reasonType: r.reason_type ?? "unknown",
        reason: r.reason ?? undefined,
        resolutionHint: r.resolution_hint ?? undefined,
        grantableBy: r.grantable_by ?? undefined,
      }))
    : [];

  const denied: NormalizedPermissions["denied"] = Array.isArray(raw.denied)
    ? raw.denied.map((d: any) => ({
        capability: d.capability,
        reasonType: d.reason_type ?? "unknown",
        reason: d.reason ?? undefined,
      }))
    : [];

  return { available, restricted, denied };
}
