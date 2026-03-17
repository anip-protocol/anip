/**
 * Event classification for v0.8 security hardening.
 */

const MALFORMED_FAILURE_TYPES = new Set([
  "unknown_capability",
  "streaming_not_supported",
  "internal_error",
]);

const HIGH_RISK_SIDE_EFFECTS = new Set([
  "write",
  "irreversible",
  "transactional",
]);

export function classifyEvent(
  sideEffectType: string | null,
  success: boolean,
  failureType: string | null,
): string {
  if (sideEffectType === null) {
    return "malformed_or_spam";
  }
  if (success) {
    if (HIGH_RISK_SIDE_EFFECTS.has(sideEffectType)) {
      return "high_risk_success";
    }
    return "low_risk_success";
  }
  if (failureType !== null && MALFORMED_FAILURE_TYPES.has(failureType)) {
    return "malformed_or_spam";
  }
  return "high_risk_denial";
}
