/**
 * Caller-class-aware disclosure resolution.
 *
 * Two modes:
 * - Fixed mode (disclosureLevel != "policy"): returns the fixed level.
 * - Policy mode ("policy"): resolves from token claims via disclosurePolicy.
 */

const SCOPE_TO_CLASS: Record<string, string> = {
  "audit:full": "audit_full",
};

function resolveCallerClass(
  tokenClaims: Record<string, unknown> | null,
): string {
  if (tokenClaims == null) return "default";

  const callerClass = tokenClaims["anip:caller_class"];
  if (callerClass != null) return String(callerClass);

  const scopes = tokenClaims.scope;
  if (Array.isArray(scopes)) {
    for (const scope of scopes) {
      if (typeof scope === "string" && scope in SCOPE_TO_CLASS) {
        return SCOPE_TO_CLASS[scope];
      }
    }
  }

  return "default";
}

export function resolveDisclosureLevel(
  disclosureLevel: string,
  tokenClaims: Record<string, unknown> | null,
  disclosurePolicy?: Record<string, string>,
): string {
  if (disclosureLevel !== "policy") return disclosureLevel;

  const callerClass = resolveCallerClass(tokenClaims);

  if (disclosurePolicy == null) return "redacted";

  const level = disclosurePolicy[callerClass];
  if (level != null) return level;

  return disclosurePolicy["default"] ?? "redacted";
}
