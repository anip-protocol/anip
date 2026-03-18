/**
 * Storage-side redaction — strips parameters from low-value audit entries before persistence.
 *
 * The persisted redacted entry is the canonical hashed form for checkpointing.
 * This is independent of response-boundary redaction (disclosure level).
 */

const LOW_VALUE_CLASSES = new Set([
  "low_risk_success",
  "malformed_or_spam",
  "repeated_low_value_denial",
]);

export function storageRedactEntry(
  entry: Record<string, unknown>,
): Record<string, unknown> {
  const result = { ...entry };
  const eventClass = result.event_class as string | undefined;

  if (eventClass != null && LOW_VALUE_CLASSES.has(eventClass)) {
    result.parameters = null;
    result.storage_redacted = true;
  } else {
    result.storage_redacted = false;
  }

  return result;
}
