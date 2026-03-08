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

  // Build a map of scope base -> full scope string
  const tokenScopes: Record<string, string> = {};
  for (const s of token.scope) {
    const base = s.split(":")[0];
    tokenScopes[base] = s;
  }

  const rootPrincipal = getRootPrincipal(token);

  for (const [name, cap] of Object.entries(capabilities)) {
    const requiredScopes = cap.minimum_scope;

    // Check if ALL required scopes are present (AND semantics)
    const matchedScopes: string[] = [];
    const missingScopes: string[] = [];
    let hasAdminScope = false;

    for (const required of requiredScopes) {
      if (required in tokenScopes) {
        matchedScopes.push(tokenScopes[required]);
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
