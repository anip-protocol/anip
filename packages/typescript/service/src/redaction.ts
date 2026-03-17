/**
 * Failure detail redaction for v0.8 security hardening.
 *
 * Shapes failure responses based on disclosure level before they reach the caller.
 * Storage always records the full unredacted failure.
 */

const GENERIC_MESSAGES: Record<string, string> = {
  scope_insufficient: "Insufficient scope for this capability",
  invalid_token: "Authentication failed",
  token_expired: "Token has expired",
  purpose_mismatch: "Token purpose does not match this capability",
  insufficient_authority: "Insufficient authority for this action",
  unknown_capability: "Capability not found",
  not_found: "Resource not found",
  unavailable: "Service temporarily unavailable",
  concurrent_lock: "Operation conflict",
  internal_error: "Internal error",
  streaming_not_supported: "Streaming not supported for this capability",
  scope_escalation: "Scope escalation not permitted",
};

const DEFAULT_GENERIC = "Request failed";

export function redactFailure(
  failure: Record<string, unknown>,
  disclosureLevel: string,
): Record<string, unknown> {
  let level = disclosureLevel;
  if (level === "policy") {
    level = "redacted";
  }

  if (level === "full") {
    return failure;
  }

  const result = { ...failure };
  const resolution = { ...((failure.resolution as Record<string, unknown>) || {}) };

  if (level === "reduced") {
    resolution.grantable_by = null;
    const detail = (result.detail as string) || "";
    if (detail.length > 200) {
      result.detail = detail.slice(0, 200);
    }
  } else if (level === "redacted") {
    const failureType = (result.type as string) || "";
    result.detail = GENERIC_MESSAGES[failureType] || DEFAULT_GENERIC;
    resolution.requires = null;
    resolution.grantable_by = null;
    resolution.estimated_availability = null;
  }

  if (Object.keys(resolution).length > 0) {
    result.resolution = resolution;
  }

  return result;
}
