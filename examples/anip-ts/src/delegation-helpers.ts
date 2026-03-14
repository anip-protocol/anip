/**
 * Delegation helpers that have no SDK equivalent.
 *
 * These are example-specific functions kept locally after migrating the
 * core delegation logic to DelegationEngine from @anip/server.
 */

import type { ANIPFailure, DelegationToken } from "@anip/core";
import { engine, ensureInit } from "./sdk.js";

function getEngine() { ensureInit(); return engine; }

// Active request tracking for concurrent_branches enforcement
const activeRequests: Set<string> = new Set();

/**
 * Type guard: check if a value is an ANIPFailure (has `type`, `detail`, `resolution`).
 */
export function isANIPFailure(value: DelegationToken | ANIPFailure): value is ANIPFailure {
  return "type" in value && "detail" in value && "resolution" in value;
}

/**
 * Validate that a token's parent exists in the store.
 * Returns null if valid (or no parent), or an ANIPFailure if the parent is missing.
 *
 * Used by the v0.1 trust-on-declaration code path.
 */
export function validateParentExists(token: DelegationToken): ANIPFailure | null {
  if (token.parent === null) {
    return null;
  }
  const parent = getEngine().getToken(token.parent);
  if (parent === null) {
    return {
      type: "parent_not_found",
      detail: `parent token '${token.parent}' is not registered`,
      resolution: {
        action: "register_parent_token_first",
        requires: `token '${token.parent}' must be registered before its children`,
        grantable_by: token.issuer,
        estimated_availability: null,
      },
      retry: true,
    };
  }
  return null;
}

/**
 * Validate that a child token's scope is a subset of its parent's scope.
 * Returns null if valid (or no parent), or an ANIPFailure if scope widens.
 *
 * Used by the v0.1 trust-on-declaration code path.
 */
export function validateScopeNarrowing(token: DelegationToken): ANIPFailure | null {
  if (token.parent === null) {
    return null;
  }

  const parent = getEngine().getToken(token.parent);
  if (parent === null) {
    return {
      type: "parent_not_found",
      detail: `parent token '${token.parent}' is not registered — cannot validate scope narrowing`,
      resolution: {
        action: "register_parent_token_first",
        requires: `token '${token.parent}' must be registered before its children`,
        grantable_by: token.issuer,
        estimated_availability: null,
      },
      retry: true,
    };
  }

  const parentScopeBases = new Set(parent.scope.map((s) => s.split(":")[0]));

  for (const childScope of token.scope) {
    const childBase = childScope.split(":")[0];
    let matched = false;
    for (const parentBase of parentScopeBases) {
      if (childBase === parentBase || childBase.startsWith(parentBase + ".")) {
        matched = true;
        break;
      }
    }

    if (!matched) {
      return {
        type: "scope_escalation",
        detail: `child token scope '${childBase}' is not a subset of parent token scopes: ${[...parentScopeBases].sort().join(", ")}`,
        resolution: {
          action: "narrow_scope",
          requires: "child scope must be subset of parent scope",
          grantable_by: getEngine().getRootPrincipal(parent),
          estimated_availability: null,
        },
        retry: false,
      };
    }

    for (const parentScopeStr of parent.scope) {
      const pBase = parentScopeStr.split(":")[0];
      if (pBase === childBase && parentScopeStr.includes(":max_$")) {
        const parentBudget = parseFloat(parentScopeStr.split(":max_$")[1]);
        if (!childScope.includes(":max_$")) {
          return {
            type: "scope_escalation",
            detail: `child dropped budget constraint from scope '${childBase}' (parent has max $${parentBudget})`,
            resolution: {
              action: "preserve_budget_constraint",
              requires: `scope '${childBase}' must include budget <= $${parentBudget}`,
              grantable_by: getEngine().getRootPrincipal(parent),
              estimated_availability: null,
            },
            retry: false,
          };
        }
        const childBudget = parseFloat(childScope.split(":max_$")[1]);
        if (childBudget > parentBudget) {
          return {
            type: "scope_escalation",
            detail: `child budget $${childBudget} exceeds parent budget $${parentBudget} for scope '${childBase}'`,
            resolution: {
              action: "narrow_budget",
              requires: `budget must be <= $${parentBudget}`,
              grantable_by: getEngine().getRootPrincipal(parent),
              estimated_availability: null,
            },
            retry: false,
          };
        }
      }
    }
  }

  return null;
}

/**
 * Validate that a child token's constraints don't weaken its parent's.
 * Returns null if valid (or no parent), or an ANIPFailure if constraints widen.
 *
 * Used by the v0.1 trust-on-declaration code path.
 */
export function validateConstraintsNarrowing(token: DelegationToken): ANIPFailure | null {
  if (token.parent === null) {
    return null;
  }

  const parent = getEngine().getToken(token.parent);
  if (parent === null) {
    return null;
  }

  if (token.constraints.max_delegation_depth > parent.constraints.max_delegation_depth) {
    return {
      type: "constraint_escalation",
      detail: `child max_delegation_depth (${token.constraints.max_delegation_depth}) exceeds parent (${parent.constraints.max_delegation_depth})`,
      resolution: {
        action: "narrow_constraints",
        requires: `max_delegation_depth must be <= ${parent.constraints.max_delegation_depth}`,
        grantable_by: getEngine().getRootPrincipal(parent),
        estimated_availability: null,
      },
      retry: false,
    };
  }

  if (
    parent.constraints.concurrent_branches === "exclusive" &&
    token.constraints.concurrent_branches === "allowed"
  ) {
    return {
      type: "constraint_escalation",
      detail: "child weakened concurrent_branches from 'exclusive' to 'allowed'",
      resolution: {
        action: "preserve_constraint",
        requires: "concurrent_branches must remain 'exclusive'",
        grantable_by: getEngine().getRootPrincipal(parent),
        estimated_availability: null,
      },
      retry: false,
    };
  }

  return null;
}

/**
 * Check if the delegation chain carries sufficient budget authority.
 */
export function checkBudgetAuthority(
  token: DelegationToken,
  amount: number,
): ANIPFailure | null {
  for (const scope of token.scope) {
    if (scope.includes(":max_$")) {
      const maxBudget = parseFloat(scope.split(":max_$")[1]);
      if (amount > maxBudget) {
        return {
          type: "budget_exceeded",
          detail: `capability costs $${amount} but delegation chain authority is max $${maxBudget}`,
          resolution: {
            action: "request_budget_increase",
            requires: `delegation.scope budget raised to $${amount}`,
            grantable_by: getEngine().getRootPrincipal(token),
            estimated_availability: null,
          },
          retry: true,
        };
      }
    }
  }
  return null;
}

/**
 * Acquire exclusive lock if the token's concurrent_branches is "exclusive".
 */
export function acquireExclusiveLock(token: DelegationToken): void {
  if (token.constraints.concurrent_branches === "exclusive") {
    activeRequests.add(getEngine().getRootPrincipal(token));
  }
}

/**
 * Release exclusive lock.
 */
export function releaseExclusiveLock(token: DelegationToken): void {
  if (token.constraints.concurrent_branches === "exclusive") {
    activeRequests.delete(getEngine().getRootPrincipal(token));
  }
}
