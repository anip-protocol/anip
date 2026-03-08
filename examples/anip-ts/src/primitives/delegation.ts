/**
 * Delegation chain validation.
 *
 * Validates the full delegation DAG: token expiry, scope sufficiency,
 * purpose binding, delegation depth, and parent chain.
 */

import type { ANIPFailure, DelegationToken } from "../types.js";

// In-memory token store — maps token_id to DelegationToken
// In production this would be a database or token verification service
const tokenStore: Map<string, DelegationToken> = new Map();

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
  const chain = getChain(token);
  return chain[0].issuer;
}

export function validateDelegation(
  token: DelegationToken,
  requiredScopes: string[],
  capabilityName: string
): ANIPFailure | null {
  /**
   * Validate a delegation token for invoking a capability.
   * Returns null if valid, or an ANIPFailure describing what's wrong.
   */

  // 1. Check expiry
  const expiresDate = new Date(token.expires);
  if (expiresDate < new Date()) {
    return {
      type: "token_expired",
      detail: `delegation token ${token.token_id} expired at ${token.expires}`,
      resolution: {
        action: "request_new_delegation",
        grantable_by: token.issuer,
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
        grantable_by: token.issuer,
        requires: null,
        estimated_availability: null,
      },
      retry: true,
    };
  }

  // 4. Check delegation depth — walk the chain and count
  const chain = getChain(token);
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

  // 5. Validate parent chain — every parent must also be valid and not expired
  for (const ancestor of chain.slice(0, -1)) {
    // all except the current token
    const ancestorExpires = new Date(ancestor.expires);
    if (ancestorExpires < new Date()) {
      return {
        type: "parent_token_expired",
        detail: `ancestor token ${ancestor.token_id} in delegation chain has expired`,
        resolution: {
          action: "refresh_delegation_chain",
          grantable_by: ancestor.issuer,
          requires: null,
          estimated_availability: null,
        },
        retry: true,
      };
    }
  }

  return null; // all checks passed
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
