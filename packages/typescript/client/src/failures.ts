/**
 * Failure normalization — maps raw ANIP failure payloads to a stable
 * consumer-friendly shape with retryability, permission classification,
 * recovery targets, and a human-safe display summary.
 */

import type { NormalizedFailure } from "./types.js";

// Failure types that indicate the operation can be retried.
const RETRYABLE_TYPES = new Set([
  "rate_limited",
  "temporary_unavailable",
  "service_overloaded",
  "timeout",
  "transient_error",
  "concurrent_conflict",
]);

// Failure types that are permission-related.
const PERMISSION_RELATED_TYPES = new Set([
  "insufficient_authority",
  "scope_insufficient",
  "scope_mismatch",
  "delegation_depth_exceeded",
  "budget_exceeded",
  "budget_currency_mismatch",
  "token_expired",
  "token_revoked",
  "non_delegable_action",
  "caller_class_insufficient",
]);

// Human-safe summaries keyed by failure type.
const DISPLAY_SUMMARIES: Record<string, string> = {
  scope_insufficient: "Additional permissions are required to perform this action.",
  scope_mismatch: "The provided token does not have the correct permissions.",
  insufficient_authority: "You do not have sufficient authority for this action.",
  delegation_depth_exceeded: "The delegation chain is too deep to continue.",
  budget_exceeded: "The budget for this operation has been exceeded.",
  budget_currency_mismatch: "The budget currency does not match what is required.",
  token_expired: "Your session has expired. Please re-authenticate.",
  token_revoked: "Your session has been revoked.",
  non_delegable_action: "This action cannot be delegated further.",
  caller_class_insufficient: "Your caller class does not meet the requirements.",
  rate_limited: "Too many requests. Please wait and try again.",
  temporary_unavailable: "The service is temporarily unavailable. Please try again shortly.",
  service_overloaded: "The service is currently overloaded. Please try again later.",
  timeout: "The request timed out. Please try again.",
  transient_error: "A temporary error occurred. Please try again.",
  concurrent_conflict: "A concurrent operation conflict occurred. Please retry.",
  capability_not_found: "The requested capability was not found.",
  invalid_parameters: "The provided parameters are invalid.",
  binding_required: "A required binding is missing for this operation.",
  cost_ceiling_exceeded: "The estimated cost exceeds the allowed ceiling.",
};

/**
 * Normalize a raw ANIP failure payload into a consumer-friendly shape.
 *
 * The raw payload is expected to match the ANIPFailure wire format:
 * ```json
 * {
 *   "type": "scope_insufficient",
 *   "detail": "...",
 *   "retry": false,
 *   "resolution": {
 *     "action": "request_broader_scope",
 *     "recovery_class": "redelegation_then_retry",
 *     "requires": "travel.book",
 *     "grantable_by": "root",
 *     "recovery_target": { ... }
 *   }
 * }
 * ```
 */
export function normalizeFailure(raw: any): NormalizedFailure {
  if (!raw || typeof raw !== "object") {
    return {
      type: "unknown",
      detail: "An unknown error occurred.",
      retryable: false,
      permissionRelated: false,
      displaySummary: "An unknown error occurred.",
    };
  }

  const type: string = raw.type ?? "unknown";
  const detail: string = raw.detail ?? "";
  const resolution = raw.resolution;

  // Retryable: use the wire `retry` field if present, otherwise infer from type.
  const retryable: boolean =
    typeof raw.retry === "boolean" ? raw.retry : RETRYABLE_TYPES.has(type);

  const permissionRelated: boolean = PERMISSION_RELATED_TYPES.has(type);

  const recoveryClass: string | undefined = resolution?.recovery_class ?? undefined;

  let recoveryTarget: NormalizedFailure["recoveryTarget"] | undefined;
  if (resolution?.recovery_target) {
    const rt = resolution.recovery_target;
    recoveryTarget = {
      kind: rt.kind,
      target: rt.target
        ? { service: rt.target.service, capability: rt.target.capability }
        : undefined,
      continuity: rt.continuity ?? undefined,
      retryAfterTarget: rt.retry_after_target ?? false,
    };
  }

  let normalizedResolution: NormalizedFailure["resolution"] | undefined;
  if (resolution) {
    normalizedResolution = {
      action: resolution.action,
      requires: resolution.requires ?? undefined,
      grantableBy: resolution.grantable_by ?? undefined,
    };
  }

  const displaySummary: string =
    DISPLAY_SUMMARIES[type] ?? (detail || "An error occurred.");

  return {
    type,
    detail,
    retryable,
    permissionRelated,
    recoveryClass,
    recoveryTarget,
    resolution: normalizedResolution,
    displaySummary,
  };
}
