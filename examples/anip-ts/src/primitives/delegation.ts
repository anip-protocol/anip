/**
 * Delegation chain validation.
 *
 * Validates the full delegation DAG: token expiry, scope sufficiency,
 * purpose binding, delegation depth, and parent chain.
 */

import { randomUUID } from "crypto";
import type { ANIPFailure, DelegationToken } from "../types.js";

// In-memory token store — maps token_id to DelegationToken
// In production this would be a database or token verification service
const tokenStore: Map<string, DelegationToken> = new Map();

// Active request tracking for concurrent_branches enforcement
const activeRequests: Set<string> = new Set();

export function validateParentExists(token: DelegationToken): ANIPFailure | null {
  /**
   * Validate that a token's parent exists in the store.
   * Returns null if valid (or no parent), or an ANIPFailure if the parent is missing.
   */
  if (token.parent === null) {
    return null; // root token
  }
  const parent = getToken(token.parent);
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

export function registerToken(token: DelegationToken): void {
  tokenStore.set(token.token_id, token);
}

export function getToken(tokenId: string): DelegationToken | null {
  return tokenStore.get(tokenId) ?? null;
}

export function getChain(token: DelegationToken): DelegationToken[] {
  /** Walk the DAG upward from a token to the root, returning the full chain. */
  const chain: DelegationToken[] = [token];
  let current = token;
  while (current.parent !== null) {
    const parent = getToken(current.parent);
    if (parent === null) {
      break;
    }
    chain.push(parent);
    current = parent;
  }
  return chain.reverse(); // root first
}

export function getRootPrincipal(token: DelegationToken): string {
  /** Get the root principal (human) from a delegation chain. */
  if (token.root_principal !== null) {
    return token.root_principal;
  }
  // Fallback for v0.1 tokens without root_principal field
  const chain = getChain(token);
  return chain[0].issuer;
}

export function resolveRegisteredToken(token: DelegationToken): DelegationToken | ANIPFailure {
  /**
   * Look up the stored version of a token and return it.
   * Returns the stored DelegationToken if the token_id is registered,
   * or an ANIPFailure if not. Callers MUST use the returned token for
   * all downstream operations — this prevents forged inline fields
   * (issuer, scope, constraints) from bypassing registration-time validation.
   */
  const stored = getToken(token.token_id);
  if (stored === null) {
    return {
      type: "token_not_registered",
      detail: `delegation token '${token.token_id}' is not registered — register via /anip/tokens first`,
      resolution: {
        action: "register_token",
        requires: "token must be registered before use",
        grantable_by: token.issuer,
        estimated_availability: null,
      },
      retry: true,
    };
  }
  return stored;
}

export function isANIPFailure(value: DelegationToken | ANIPFailure): value is ANIPFailure {
  return "type" in value && "detail" in value && "resolution" in value;
}

export function validateDelegation(
  token: DelegationToken,
  requiredScopes: string[],
  capabilityName: string
): DelegationToken | ANIPFailure {
  /**
   * Validate a delegation token for invoking a capability.
   * Returns the stored DelegationToken if valid (callers MUST use this for
   * all downstream operations), or an ANIPFailure describing what's wrong.
   */

  // 0. Resolve to stored token (prevents forged inline fields)
  const resolved = resolveRegisteredToken(token);
  if (isANIPFailure(resolved)) {
    return resolved;
  }
  token = resolved; // use stored token for all subsequent checks

  // 1. Check expiry
  const expiresDate = new Date(token.expires);
  if (expiresDate < new Date()) {
    return {
      type: "token_expired",
      detail: `delegation token ${token.token_id} expired at ${token.expires}`,
      resolution: {
        action: "request_new_delegation",
        grantable_by: getRootPrincipal(token),
        requires: null,
        estimated_availability: null,
      },
      retry: true,
    };
  }

  // 2. Check scope — the token must carry ALL required scopes (AND semantics)
  const missingScopes: string[] = [];
  for (const requiredScope of requiredScopes) {
    let scopeMatched = false;
    for (const scope of token.scope) {
      const scopeBase = scope.split(":")[0]; // "travel.book:max_$500" -> "travel.book"
      if (
        scopeBase === requiredScope ||
        requiredScope.startsWith(scopeBase + ".")
      ) {
        scopeMatched = true;
        break;
      }
    }
    if (!scopeMatched) {
      missingScopes.push(requiredScope);
    }
  }
  if (missingScopes.length > 0) {
    const rootPrincipal = getRootPrincipal(token);
    return {
      type: "insufficient_authority",
      detail: `delegation chain lacks scope: ${missingScopes.join(", ")}`,
      resolution: {
        action: "request_scope_grant",
        requires: `delegation.scope += ${missingScopes.join(", ")}`,
        grantable_by: rootPrincipal,
        estimated_availability: null,
      },
      retry: true,
    };
  }

  // 3. Check purpose binding — token purpose must match the capability
  if (token.purpose.capability !== capabilityName) {
    return {
      type: "purpose_mismatch",
      detail: `delegation token purpose is ${token.purpose.capability} but request is for ${capabilityName}`,
      resolution: {
        action: "request_new_delegation",
        grantable_by: getRootPrincipal(token),
        requires: null,
        estimated_availability: null,
      },
      retry: true,
    };
  }

  // 4. Verify the delegation chain is complete (no missing ancestors)
  const chain = getChain(token);
  // If the token has a parent but get_chain didn't reach a root (parent=null),
  // the chain is broken — an ancestor is unregistered
  if (chain[0].parent !== null) {
    return {
      type: "broken_delegation_chain",
      detail: `delegation chain is incomplete — ancestor token '${chain[0].parent}' is not registered`,
      resolution: {
        action: "register_missing_ancestor",
        grantable_by: getRootPrincipal(token),
        requires: null,
        estimated_availability: null,
      },
      retry: true,
    };
  }

  // 5. Check delegation depth
  const maxDepth = token.constraints.max_delegation_depth;
  // Depth is number of delegations (edges), not nodes
  const actualDepth = chain.length - 1;
  if (actualDepth > maxDepth) {
    return {
      type: "delegation_depth_exceeded",
      detail: `delegation chain depth is ${actualDepth}, max allowed is ${maxDepth}`,
      resolution: {
        action: "reduce_delegation_depth",
        requires: `max_delegation_depth >= ${actualDepth}`,
        grantable_by: getRootPrincipal(token),
        estimated_availability: null,
      },
      retry: true,
    };
  }

  // 6. Enforce concurrent_branches — reject if exclusive and another request is active
  if (token.constraints.concurrent_branches === "exclusive") {
    const root = getRootPrincipal(token);
    if (activeRequests.has(root)) {
      return {
        type: "concurrent_request_rejected",
        detail: `concurrent_branches is exclusive and another request from ${root} is in progress`,
        resolution: {
          action: "wait_and_retry",
          grantable_by: root,
          requires: null,
          estimated_availability: null,
        },
        retry: true,
      };
    }
  }

  // 7. Validate parent chain — every parent must also be valid and not expired
  for (const ancestor of chain.slice(0, -1)) {
    // all except the current token
    const ancestorExpires = new Date(ancestor.expires);
    if (ancestorExpires < new Date()) {
      return {
        type: "parent_token_expired",
        detail: `ancestor token ${ancestor.token_id} in delegation chain has expired`,
        resolution: {
          action: "refresh_delegation_chain",
          grantable_by: getRootPrincipal(token),
          requires: null,
          estimated_availability: null,
        },
        retry: true,
      };
    }
  }

  return token; // all checks passed — return stored token for downstream use
}

export function acquireExclusiveLock(token: DelegationToken): void {
  if (token.constraints.concurrent_branches === "exclusive") {
    activeRequests.add(getRootPrincipal(token));
  }
}

export function releaseExclusiveLock(token: DelegationToken): void {
  if (token.constraints.concurrent_branches === "exclusive") {
    activeRequests.delete(getRootPrincipal(token));
  }
}

export function validateScopeNarrowing(token: DelegationToken): ANIPFailure | null {
  /**
   * Validate that a child token's scope is a subset of its parent's scope.
   * Returns null if valid (or no parent), or an ANIPFailure if scope widens.
   */
  if (token.parent === null) {
    return null; // root tokens have no parent to narrow from
  }

  const parent = getToken(token.parent);
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

    // Child scope base must match or be narrower than a parent scope base
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
          grantable_by: getRootPrincipal(parent),
          estimated_availability: null,
        },
        retry: false,
      };
    }

    // Check budget constraints: if parent has a budget on this scope,
    // child MUST preserve it (same or tighter). Dropping it is escalation.
    for (const parentScopeStr of parent.scope) {
      const pBase = parentScopeStr.split(":")[0];
      if (pBase === childBase && parentScopeStr.includes(":max_$")) {
        const parentBudget = parseFloat(parentScopeStr.split(":max_$")[1]);
        if (!childScope.includes(":max_$")) {
          // Child dropped the budget constraint entirely
          return {
            type: "scope_escalation",
            detail: `child dropped budget constraint from scope '${childBase}' (parent has max $${parentBudget})`,
            resolution: {
              action: "preserve_budget_constraint",
              requires: `scope '${childBase}' must include budget <= $${parentBudget}`,
              grantable_by: getRootPrincipal(parent),
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
              grantable_by: getRootPrincipal(parent),
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

export function validateConstraintsNarrowing(token: DelegationToken): ANIPFailure | null {
  /**
   * Validate that a child token's constraints don't weaken its parent's.
   * Returns null if valid (or no parent), or an ANIPFailure if constraints widen.
   */
  if (token.parent === null) {
    return null;
  }

  const parent = getToken(token.parent);
  if (parent === null) {
    return null; // parent existence is checked separately
  }

  // max_delegation_depth: child cannot raise it
  if (token.constraints.max_delegation_depth > parent.constraints.max_delegation_depth) {
    return {
      type: "constraint_escalation",
      detail: `child max_delegation_depth (${token.constraints.max_delegation_depth}) exceeds parent (${parent.constraints.max_delegation_depth})`,
      resolution: {
        action: "narrow_constraints",
        requires: `max_delegation_depth must be <= ${parent.constraints.max_delegation_depth}`,
        grantable_by: getRootPrincipal(parent),
        estimated_availability: null,
      },
      retry: false,
    };
  }

  // concurrent_branches: child cannot weaken from exclusive to allowed
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
        grantable_by: getRootPrincipal(parent),
        estimated_availability: null,
      },
      retry: false,
    };
  }

  return null;
}

export function issueToken(
  subject: string,
  scope: string[],
  capability: string,
  issuerId: string,
  parentToken: DelegationToken | null,
  purposeParameters: Record<string, unknown>,
  ttlHours: number,
  rootPrincipal: string | null = null,
): { token: DelegationToken; tokenId: string } {
  const tokenId = `anip-${randomUUID().replace(/-/g, "").slice(0, 12)}`;
  const now = new Date();
  const expires = new Date(now.getTime() + ttlHours * 3600 * 1000);

  let maxDepth = 3;
  let concurrent: "allowed" | "exclusive" = "allowed";
  if (parentToken !== null) {
    maxDepth = Math.min(maxDepth, parentToken.constraints.max_delegation_depth);
    concurrent = parentToken.constraints.concurrent_branches;
  }

  const token: DelegationToken = {
    token_id: tokenId,
    issuer: issuerId,
    subject,
    scope,
    purpose: {
      capability,
      parameters: purposeParameters,
      task_id: `task-${tokenId}`,
    },
    parent: parentToken?.token_id ?? null,
    expires: expires.toISOString(),
    constraints: {
      max_delegation_depth: maxDepth,
      concurrent_branches: concurrent,
    },
    root_principal: rootPrincipal,
  };

  // Validate narrowing if child token
  if (parentToken !== null) {
    const scopeFailure = validateScopeNarrowing(token);
    if (scopeFailure !== null) {
      throw new Error(scopeFailure.detail);
    }
    const constraintFailure = validateConstraintsNarrowing(token);
    if (constraintFailure !== null) {
      throw new Error(constraintFailure.detail);
    }
  }

  registerToken(token);
  return { token, tokenId };
}

export function getChainTokenIds(token: DelegationToken): string[] {
  return getChain(token).map((t) => t.token_id);
}

export function checkBudgetAuthority(
  token: DelegationToken,
  amount: number
): ANIPFailure | null {
  /** Check if the delegation chain carries sufficient budget authority. */
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
            grantable_by: getRootPrincipal(token),
            estimated_availability: null,
          },
          retry: true,
        };
      }
    }
  }
  return null;
}
