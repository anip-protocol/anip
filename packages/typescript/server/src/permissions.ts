/**
 * Permission discovery — query what you can do before trying it.
 */

import type {
  DelegationToken as DelegationTokenType,
  CapabilityDeclaration as CapabilityDeclarationType,
} from "@anip-dev/core";

export interface PermissionResult {
  available: Array<{
    capability: string;
    scope_match: string;
    constraints: Record<string, unknown>;
  }>;
  restricted: Array<{
    capability: string;
    reason: string;
    reason_type: string;
    grantable_by: string;
    unmet_token_requirements?: string[];
    resolution_hint?: string | null;
  }>;
  denied: Array<{
    capability: string;
    reason: string;
    reason_type: string;
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
      // Check token-evaluable control requirements
      const controlRequirements = (cap as any).control_requirements ?? [];
      const unmet: string[] = [];
      const constraintsObj = token.constraints as Record<string, unknown> | undefined;
      for (const req of controlRequirements as Array<Record<string, unknown>>) {
        const reqType = req.type as string;
        if (reqType === "cost_ceiling" && (!constraintsObj || !constraintsObj.budget)) {
          unmet.push("cost_ceiling");
        } else if (reqType === "stronger_delegation_required") {
          const tokenHasExplicitBinding = (
            token.purpose !== null &&
            token.purpose !== undefined &&
            token.purpose.capability === name
          );
          if (!tokenHasExplicitBinding) {
            unmet.push("stronger_delegation_required");
          }
        }
      }

      if (
        unmet.length > 0 &&
        controlRequirements.some(
          (r: Record<string, unknown>) =>
            r.enforcement === "reject" && unmet.includes(r.type as string),
        )
      ) {
        const ctrlResolutionHint = unmet.includes("cost_ceiling")
          ? "request_budget_bound_delegation"
          : "request_capability_binding";
        restricted.push({
          capability: name,
          reason: `missing control requirements: ${unmet.join(", ")}`,
          reason_type: "unmet_control_requirement",
          grantable_by: rootPrincipal,
          unmet_token_requirements: unmet,
          resolution_hint: ctrlResolutionHint,
        });
        continue;
      }

      const constraints: Record<string, unknown> = {};
      for (const scopeStr of matchedScopeStrs) {
        if (scopeStr.includes(":max_$")) {
          const maxBudget = parseFloat(scopeStr.split(":max_$")[1]);
          constraints.budget_remaining = maxBudget;
          constraints.currency = "USD";
        }
      }
      // Include constraints-level budget info if present
      if (constraintsObj?.budget) {
        const budget = constraintsObj.budget as Record<string, unknown>;
        constraints.budget_remaining = budget.max_amount;
        constraints.currency = budget.currency;
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
        reason_type: "non_delegable",
      });
    } else {
      restricted.push({
        capability: name,
        reason: `delegation chain lacks scope(s): ${missing.join(", ")}`,
        reason_type: "insufficient_scope",
        grantable_by: rootPrincipal,
        resolution_hint: "request_broader_scope",
      });
    }
  }

  return { available, restricted, denied };
}
