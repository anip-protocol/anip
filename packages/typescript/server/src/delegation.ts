/**
 * Trust-safe delegation engine.
 *
 * Wraps delegation logic with instance-level storage and enforces trust
 * boundaries at the API level:
 *
 * - `issueRootToken()` creates root tokens with `issuer` derived from
 *   `serviceId` and `root_principal` from `authenticatedPrincipal`.
 * - `delegate()` creates child tokens with `issuer` derived from
 *   `parentToken.subject` and `root_principal` inherited from the parent
 *   chain.  Validates scope narrowing before creation.
 *
 * There is no raw `issueToken(issuer, rootPrincipal)` in the public API.
 */

import { randomUUID } from "crypto";
import { hostname } from "os";
import type {
  DelegationToken as DelegationTokenType,
  ANIPFailure as ANIPFailureType,
  Budget as BudgetType,
} from "@anip-dev/core";
import { recoveryClassForAction } from "@anip-dev/core";
import type { StorageBackend } from "./storage.js";

// Use plain objects matching the Zod-inferred type shapes from @anip-dev/core.
// We avoid Zod runtime parsing here; construction uses object literals.

export interface IssueRootTokenOpts {
  authenticatedPrincipal: string;
  subject: string;
  scope: string[];
  capability: string;
  purposeParameters?: Record<string, unknown>;
  ttlHours?: number;
  maxDelegationDepth?: number;
  budget?: BudgetType | null;
  /** v0.23: bind a session identity for session_bound ApprovalGrant validation. */
  sessionId?: string | null;
}

export interface DelegateOpts {
  parentToken: DelegationTokenType;
  subject: string;
  scope: string[];
  capability: string;
  purposeParameters?: Record<string, unknown>;
  ttlHours?: number;
  budget?: BudgetType | null;
}

export class DelegationEngine {
  private _storage: StorageBackend;
  private _serviceId: string;
  private _exclusiveTtl: number;

  constructor(
    storage: StorageBackend,
    opts: { serviceId: string; exclusiveTtl?: number },
  ) {
    this._storage = storage;
    this._serviceId = opts.serviceId;
    this._exclusiveTtl = opts.exclusiveTtl ?? 60;
  }

  // ------------------------------------------------------------------
  // Exclusivity
  // ------------------------------------------------------------------

  private _getHolderId(): string {
    return `${hostname()}:${process.pid}`;
  }

  /**
   * Acquire an exclusive lock for a token whose constraints require it.
   *
   * Returns `null` on success (lock acquired or not needed).
   * Returns an `ANIPFailure` if the lock is already held by another holder.
   */
  async acquireExclusiveLock(
    token: DelegationTokenType,
  ): Promise<ANIPFailureType | null> {
    if (token.constraints?.concurrent_branches !== "exclusive") return null;
    const root = await this.getRootPrincipal(token);
    const key = `exclusive:${this._serviceId}:${root}`;
    const acquired = await this._storage.tryAcquireExclusive(
      key,
      this._getHolderId(),
      this._exclusiveTtl,
    );
    if (!acquired) {
      return {
        type: "concurrent_request_rejected",
        detail: `concurrent_branches is exclusive and another request from ${root} is in progress`,
        resolution: {
          action: "wait_and_retry",
          recovery_class: recoveryClassForAction("wait_and_retry"),
          grantable_by: root,
        },
        retry: true,
      } as ANIPFailureType;
    }
    return null;
  }

  /**
   * Release an exclusive lock previously acquired for a token.
   *
   * No-op if the token does not require exclusivity.
   */
  async releaseExclusiveLock(token: DelegationTokenType): Promise<void> {
    if (token.constraints?.concurrent_branches !== "exclusive") return;
    const root = await this.getRootPrincipal(token);
    const key = `exclusive:${this._serviceId}:${root}`;
    await this._storage.releaseExclusive(key, this._getHolderId());
  }

  // ------------------------------------------------------------------
  // Public API
  // ------------------------------------------------------------------

  /**
   * Issue a root delegation token.
   *
   * `issuer` is always `serviceId`.
   * `root_principal` is always `authenticatedPrincipal`.
   */
  async issueRootToken(opts: IssueRootTokenOpts): Promise<{
    token: DelegationTokenType;
    tokenId: string;
  }> {
    return this._createToken({
      issuer: this._serviceId,
      subject: opts.subject,
      scope: opts.scope,
      capability: opts.capability,
      rootPrincipal: opts.authenticatedPrincipal,
      parentToken: null,
      purposeParameters: opts.purposeParameters ?? {},
      ttlHours: opts.ttlHours ?? 2,
      maxDelegationDepth: opts.maxDelegationDepth ?? 3,
      budget: opts.budget ?? null,
      sessionId: opts.sessionId ?? null,
    });
  }

  /**
   * Create a child delegation token from `parentToken`.
   *
   * `issuer` is derived from `parentToken.subject`.
   * `root_principal` is inherited from the parent chain.
   *
   * Returns `{ token, tokenId }` on success, or an `ANIPFailure` object if
   * scope widening or constraint escalation is detected.
   */
  async delegate(
    opts: DelegateOpts,
  ): Promise<{ token: DelegationTokenType; tokenId: string } | ANIPFailureType> {
    const rootPrincipal = await this.getRootPrincipal(opts.parentToken);

    // Pre-validate scope narrowing before creating the token
    const parentScopeBases = new Set(
      opts.parentToken.scope.map((s) => s.split(":")[0]),
    );
    for (const childScope of opts.scope) {
      const childBase = childScope.split(":")[0];
      let matched = false;
      for (const parentBase of parentScopeBases) {
        if (
          childBase === parentBase ||
          childBase.startsWith(parentBase + ".")
        ) {
          matched = true;
          break;
        }
      }
      if (!matched) {
        return {
          type: "scope_escalation",
          detail: `child token scope '${childBase}' is not a subset of parent token scopes: ${[...parentScopeBases].sort().join(", ")}`,
          resolution: {
            action: "request_new_delegation",
            recovery_class: recoveryClassForAction("request_new_delegation"),
            requires: "child scope must be subset of parent scope",
            grantable_by: rootPrincipal,
          },
          retry: false,
        } as ANIPFailureType;
      }

      // Check budget constraints
      for (const parentScopeStr of opts.parentToken.scope) {
        const pBase = parentScopeStr.split(":")[0];
        if (pBase === childBase && parentScopeStr.includes(":max_$")) {
          const parentBudget = parseFloat(
            parentScopeStr.split(":max_$")[1],
          );
          if (!childScope.includes(":max_$")) {
            return {
              type: "scope_escalation",
              detail: `child dropped budget constraint from scope '${childBase}' (parent has max $${parentBudget})`,
              resolution: {
                action: "request_new_delegation",
                recovery_class: recoveryClassForAction("request_new_delegation"),
                requires: `scope '${childBase}' must include budget <= $${parentBudget}`,
                grantable_by: rootPrincipal,
              },
              retry: false,
            } as ANIPFailureType;
          }
          const childBudget = parseFloat(childScope.split(":max_$")[1]);
          if (childBudget > parentBudget) {
            return {
              type: "scope_escalation",
              detail: `child budget $${childBudget} exceeds parent budget $${parentBudget} for scope '${childBase}'`,
              resolution: {
                action: "request_new_delegation",
                recovery_class: recoveryClassForAction("request_new_delegation"),
                requires: `budget must be <= $${parentBudget}`,
                grantable_by: rootPrincipal,
              },
              retry: false,
            } as ANIPFailureType;
          }
        }
      }
    }

    // Enforce budget narrowing on constraints-level budget
    let effectiveBudget: BudgetType | null = opts.budget ?? null;
    const parentConstraints = opts.parentToken.constraints;
    if (parentConstraints?.budget) {
      if (effectiveBudget === null) {
        // Child inherits parent budget
        effectiveBudget = parentConstraints.budget;
      } else if (effectiveBudget.currency !== parentConstraints.budget.currency) {
        return {
          type: "budget_currency_mismatch",
          detail: `Child budget currency ${effectiveBudget.currency} does not match parent ${parentConstraints.budget.currency}`,
          resolution: {
            action: "request_matching_currency_delegation",
            recovery_class: recoveryClassForAction("request_matching_currency_delegation"),
            requires: `budget currency must be ${parentConstraints.budget.currency}`,
            grantable_by: rootPrincipal,
          },
          retry: false,
        } as ANIPFailureType;
      } else if (effectiveBudget.max_amount > parentConstraints.budget.max_amount) {
        return {
          type: "budget_exceeded",
          detail: `Child budget $${effectiveBudget.max_amount} exceeds parent budget $${parentConstraints.budget.max_amount}`,
          resolution: {
            action: "request_new_delegation",
            recovery_class: recoveryClassForAction("request_new_delegation"),
            requires: `budget must be <= $${parentConstraints.budget.max_amount}`,
            grantable_by: rootPrincipal,
          },
          retry: false,
        } as ANIPFailureType;
      }
    }

    return this._createToken({
      issuer: opts.parentToken.subject,
      subject: opts.subject,
      scope: opts.scope,
      capability: opts.capability,
      rootPrincipal,
      parentToken: opts.parentToken,
      purposeParameters: opts.purposeParameters ?? {},
      ttlHours: opts.ttlHours ?? 2,
      maxDelegationDepth: Math.min(
        opts.parentToken.constraints.max_delegation_depth,
        opts.parentToken.constraints.max_delegation_depth,
      ),
      budget: effectiveBudget,
    });
  }

  /**
   * Validate a delegation token for invoking a capability.
   *
   * Returns the stored `DelegationToken` if valid (callers MUST use it for
   * all downstream operations), or an `ANIPFailure`.
   */
  async validateDelegation(
    token: DelegationTokenType,
    minimumScope: string[],
    capabilityName: string,
  ): Promise<DelegationTokenType | ANIPFailureType> {
    // 0. Resolve to stored token (prevents forged inline fields)
    const resolved = await this.resolveRegisteredToken(token);
    if (_isFailure(resolved)) return resolved;
    token = resolved;

    // 1. Check expiry
    const expiresDate = new Date(token.expires);
    if (expiresDate < new Date()) {
      return {
        type: "token_expired",
        detail: `delegation token ${token.token_id} expired at ${token.expires}`,
        resolution: {
          action: "request_new_delegation",
          recovery_class: recoveryClassForAction("request_new_delegation"),
          grantable_by: await this.getRootPrincipal(token),
        },
        retry: true,
      } as ANIPFailureType;
    }

    // 2. Check scope — token must carry ALL required scopes (prefix match)
    const tokenScopeBases = token.scope.map((s) => s.split(":")[0]);
    const missingScopes: string[] = [];
    for (const requiredScope of minimumScope) {
      const scopeMatched = tokenScopeBases.some(
        (scopeBase) =>
          scopeBase === requiredScope ||
          requiredScope.startsWith(scopeBase + "."),
      );
      if (!scopeMatched) {
        missingScopes.push(requiredScope);
      }
    }
    if (missingScopes.length > 0) {
      const rootPrincipal = await this.getRootPrincipal(token);
      return {
        type: "scope_insufficient",
        detail: `delegation chain lacks scope(s): ${missingScopes.join(", ")}`,
        resolution: {
          action: "request_broader_scope",
          recovery_class: recoveryClassForAction("request_broader_scope"),
          requires: `delegation.scope += ${missingScopes.join(", ")}`,
          grantable_by: rootPrincipal,
        },
        retry: true,
      } as ANIPFailureType;
    }

    // 3. Check purpose binding
    if (token.purpose.capability !== capabilityName) {
      return {
        type: "purpose_mismatch",
        detail: `delegation token purpose is ${token.purpose.capability} but request is for ${capabilityName}`,
        resolution: {
          action: "request_new_delegation",
          recovery_class: recoveryClassForAction("request_new_delegation"),
          grantable_by: await this.getRootPrincipal(token),
        },
        retry: true,
      } as ANIPFailureType;
    }

    // 4. Verify delegation chain is complete
    const chain = await this.getChain(token);
    if (chain[0].parent !== null && chain[0].parent !== undefined) {
      return {
        type: "broken_delegation_chain",
        detail: `delegation chain is incomplete — ancestor token '${chain[0].parent}' is not registered`,
        resolution: {
          action: "request_deeper_delegation",
          recovery_class: recoveryClassForAction("request_deeper_delegation"),
          grantable_by: await this.getRootPrincipal(token),
        },
        retry: true,
      } as ANIPFailureType;
    }

    // 5. Check delegation depth
    const maxDepth = token.constraints.max_delegation_depth;
    const actualDepth = chain.length - 1;
    if (actualDepth > maxDepth) {
      return {
        type: "delegation_depth_exceeded",
        detail: `delegation chain depth is ${actualDepth}, max allowed is ${maxDepth}`,
        resolution: {
          action: "request_deeper_delegation",
          recovery_class: recoveryClassForAction("request_deeper_delegation"),
          requires: `max_delegation_depth >= ${actualDepth}`,
          grantable_by: await this.getRootPrincipal(token),
        },
        retry: true,
      } as ANIPFailureType;
    }

    // 6. Validate parent chain — every parent must be valid and not expired
    for (const ancestor of chain.slice(0, -1)) {
      const ancestorExpires = new Date(ancestor.expires);
      if (ancestorExpires < new Date()) {
        return {
          type: "parent_token_expired",
          detail: `ancestor token ${ancestor.token_id} in delegation chain has expired`,
          resolution: {
            action: "refresh_binding",
            recovery_class: recoveryClassForAction("refresh_binding"),
            grantable_by: await this.getRootPrincipal(token),
          },
          retry: true,
        } as ANIPFailureType;
      }
    }

    return token; // all checks passed
  }

  // ------------------------------------------------------------------
  // Chain helpers
  // ------------------------------------------------------------------

  /** Walk the DAG upward from `token` to the root, returning root-first. */
  async getChain(token: DelegationTokenType): Promise<DelegationTokenType[]> {
    const chain: DelegationTokenType[] = [token];
    let current = token;
    while (current.parent !== null && current.parent !== undefined) {
      const parent = await this.getToken(current.parent);
      if (parent === null) break;
      chain.push(parent);
      current = parent;
    }
    return chain.reverse();
  }

  /** Return the root principal (human) from the delegation chain. */
  async getRootPrincipal(token: DelegationTokenType): Promise<string> {
    if (token.root_principal !== null && token.root_principal !== undefined) {
      return token.root_principal;
    }
    // Fallback for v0.1 tokens without root_principal field
    const chain = await this.getChain(token);
    return chain[0].issuer;
  }

  /** Return token IDs in the delegation chain (for audit logging). */
  async getChainTokenIds(token: DelegationTokenType): Promise<string[]> {
    return (await this.getChain(token)).map((t) => t.token_id);
  }

  // ------------------------------------------------------------------
  // Token storage helpers (public for direct access)
  // ------------------------------------------------------------------

  async registerToken(token: DelegationTokenType): Promise<void> {
    await this._storage.storeToken({
      token_id: token.token_id,
      issuer: token.issuer,
      subject: token.subject,
      scope: token.scope,
      purpose: token.purpose,
      parent: token.parent,
      expires: token.expires,
      constraints: token.constraints,
      root_principal: token.root_principal,
      caller_class: token.caller_class ?? null,
      // v0.23: persist session identity bound to the token.
      session_id: token.session_id ?? null,
    });
  }

  async getToken(tokenId: string): Promise<DelegationTokenType | null> {
    const data = await this._storage.loadToken(tokenId);
    if (data === null) return null;
    return data as unknown as DelegationTokenType;
  }

  async resolveRegisteredToken(
    token: DelegationTokenType,
  ): Promise<DelegationTokenType | ANIPFailureType> {
    const stored = await this.getToken(token.token_id);
    if (stored === null) {
      return {
        type: "token_not_registered",
        detail: `delegation token '${token.token_id}' is not registered — register via /anip/tokens first`,
        resolution: {
          action: "request_new_delegation",
          recovery_class: recoveryClassForAction("request_new_delegation"),
          requires: "token must be registered before use",
          grantable_by: token.issuer,
        },
        retry: true,
      } as ANIPFailureType;
    }
    return stored;
  }

  private async _createToken(opts: {
    issuer: string;
    subject: string;
    scope: string[];
    capability: string;
    rootPrincipal: string;
    parentToken: DelegationTokenType | null;
    purposeParameters: Record<string, unknown>;
    ttlHours: number;
    maxDelegationDepth: number;
    budget?: BudgetType | null;
    sessionId?: string | null;
  }): Promise<{ token: DelegationTokenType; tokenId: string }> {
    const tokenId = `anip-${randomUUID().replace(/-/g, "").slice(0, 12)}`;
    const now = new Date();
    const expires = new Date(
      now.getTime() + opts.ttlHours * 60 * 60 * 1000,
    );

    let concurrent: "allowed" | "exclusive" = "allowed";
    let maxDepth = opts.maxDelegationDepth;
    if (opts.parentToken !== null) {
      maxDepth = Math.min(
        maxDepth,
        opts.parentToken.constraints.max_delegation_depth,
      );
      concurrent = opts.parentToken.constraints.concurrent_branches;
    }

    // task_id: use caller-supplied value, auto-generate only if purposeParameters is absent
    const pp: Record<string, any> = opts.purposeParameters ? { ...opts.purposeParameters } : {};
    const callerTaskId = pp.task_id as string | undefined;
    let resolvedTaskId: string | null;
    if (callerTaskId !== undefined && callerTaskId !== null) {
      resolvedTaskId = callerTaskId;
      delete pp.task_id;
    } else if (opts.purposeParameters === undefined || opts.purposeParameters === null) {
      resolvedTaskId = `task-${tokenId}`;
    } else {
      resolvedTaskId = null;
    }

    const token: DelegationTokenType = {
      token_id: tokenId,
      issuer: opts.issuer,
      subject: opts.subject,
      scope: opts.scope,
      purpose: {
        capability: opts.capability,
        parameters: pp,
        task_id: resolvedTaskId,
      },
      parent: opts.parentToken ? opts.parentToken.token_id : null,
      expires: expires.toISOString(),
      constraints: {
        max_delegation_depth: maxDepth,
        concurrent_branches: concurrent,
        budget: opts.budget ?? null,
      },
      root_principal: opts.rootPrincipal,
      caller_class: null,
      // v0.23: child tokens inherit parent.session_id; roots may set it via opts.
      session_id: opts.parentToken
        ? opts.parentToken.session_id ?? null
        : opts.sessionId ?? null,
    };

    await this.registerToken(token);
    return { token, tokenId };
  }
}

// ------------------------------------------------------------------
// Helpers
// ------------------------------------------------------------------

/** Type guard: check if a value is an ANIPFailure (has a `type` field). */
function _isFailure(
  value: DelegationTokenType | ANIPFailureType,
): value is ANIPFailureType {
  return (
    typeof value === "object" &&
    value !== null &&
    "type" in value &&
    "detail" in value &&
    "resolution" in value
  );
}
