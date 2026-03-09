/**
 * Permission discovery — query what you can do before trying it.
 */

import type {
  AvailableCapability,
  CapabilityDeclaration,
  DelegationToken,
  DeniedCapability,
  PermissionResponse,
  RestrictedCapability,
} from "../types.js";
import { getRootPrincipal } from "./delegation.js";

function isAdminScope(scope: string): boolean {
  return scope.startsWith("admin.");
}

export function discoverPermissions(
  token: DelegationToken,
  capabilities: Record<string, CapabilityDeclaration>
): PermissionResponse {
  /** Given a delegation token, return what the agent can and can't do. */
  const available: AvailableCapability[] = [];
  const restricted: RestrictedCapability[] = [];
  const denied: DeniedCapability[] = [];

  // Build scope base list: "travel.book:max_$500" → ["travel.book", "travel.book:max_$500"]
  const tokenScopeBases: Array<[string, string]> = token.scope.map((s) => [
    s.split(":")[0],
    s,
  ]);

  const rootPrincipal = getRootPrincipal(token);

  for (const [name, cap] of Object.entries(capabilities)) {
    const requiredScopes = cap.minimum_scope;

    // Check if ALL required scopes are present (prefix match —
    // same logic as invocation validation in delegation.ts)
    const matchedScopes: string[] = [];
    const missingScopes: string[] = [];
    let hasAdminScope = false;

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
        matchedScopes.push(matchedFull);
      } else if (isAdminScope(required)) {
        hasAdminScope = true;
        missingScopes.push(required);
      } else {
        missingScopes.push(required);
      }
    }

    if (missingScopes.length === 0) {
      const constraints: Record<string, unknown> = {};

      // Extract budget constraint if present from any matched scope
      for (const scopeStr of matchedScopes) {
        if (scopeStr.includes(":max_$")) {
          const maxBudget = parseFloat(scopeStr.split(":max_$")[1]);
          constraints["budget_remaining"] = maxBudget;
          constraints["currency"] = "USD";
        }
      }

      available.push({
        capability: name,
        scope_match: matchedScopes.join(", "),
        constraints,
      });
    } else if (hasAdminScope) {
      denied.push({
        capability: name,
        reason:
          "requires admin principal, current chain root is standard user",
      });
    } else {
      restricted.push({
        capability: name,
        reason: `delegation chain lacks scope: ${missingScopes.join(", ")}`,
        grantable_by: rootPrincipal,
      });
    }
  }

  return { available, restricted, denied };
}
