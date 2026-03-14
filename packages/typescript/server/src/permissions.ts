/**
 * Permission discovery — query what you can do before trying it.
 */

import type {
  DelegationToken as DelegationTokenType,
  CapabilityDeclaration as CapabilityDeclarationType,
} from "@anip/core";

export interface PermissionResult {
  available: Array<{
    capability: string;
    scope_match: string;
    constraints: Record<string, unknown>;
  }>;
  restricted: Array<{
    capability: string;
    reason: string;
    grantable_by: string;
  }>;
  denied: Array<{
    capability: string;
    reason: string;
  }>;
}

/**
 * Given a delegation token and a map of capabilities, return what the agent
 * can and cannot do.
 */
export function discoverPermissions(
  token: DelegationTokenType,
  capabilities: Record<string, CapabilityDeclarationType>,
): PermissionResult {
  const available: PermissionResult["available"] = [];
  const restricted: PermissionResult["restricted"] = [];
  const denied: PermissionResult["denied"] = [];

  const tokenScopeBases: Array<[string, string]> = token.scope.map((s) => [
    s.split(":")[0],
    s,
  ]);
  const rootPrincipal = token.root_principal ?? token.issuer;

  for (const [name, cap] of Object.entries(capabilities)) {
    const requiredScopes = cap.minimum_scope;
    const matchedScopeStrs: string[] = [];
    const missing: string[] = [];

    for (const required of requiredScopes) {
      let matchedFull: string | null = null;
      for (const [scopeBase, fullScope] of tokenScopeBases) {
        if (
          scopeBase === required ||
          required.startsWith(scopeBase + ".")
        ) {
          matchedFull = fullScope;
          break;
        }
      }
      if (matchedFull !== null) {
        matchedScopeStrs.push(matchedFull);
      } else {
        missing.push(required);
      }
    }

    if (missing.length === 0) {
      const constraints: Record<string, unknown> = {};
      for (const scopeStr of matchedScopeStrs) {
        if (scopeStr.includes(":max_$")) {
          const maxBudget = parseFloat(scopeStr.split(":max_$")[1]);
          constraints.budget_remaining = maxBudget;
          constraints.currency = "USD";
        }
      }
      available.push({
        capability: name,
        scope_match: matchedScopeStrs.join(", "),
        constraints,
      });
    } else if (missing.some((s) => s.startsWith("admin."))) {
      denied.push({
        capability: name,
        reason: "requires admin principal",
      });
    } else {
      restricted.push({
        capability: name,
        reason: `delegation chain lacks scope(s): ${missing.join(", ")}`,
        grantable_by: rootPrincipal,
      });
    }
  }

  return { available, restricted, denied };
}
