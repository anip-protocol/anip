/**
 * Approval request creation + grant issuance + continuation tests (v0.23).
 *
 * Mirrors anip-service/tests/test_v023_approval_grants.py.
 */
import { describe, it, expect, beforeEach } from "vitest";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  createANIPService,
  defineCapability,
  ANIPError,
  validateContinuationGrant,
  utcNowIso,
  type ANIPService,
  type CapabilityDef,
} from "../src/index.js";
import type {
  CapabilityDeclaration,
  DelegationToken,
  GrantPolicy,
} from "@anip-dev/core";
import { InMemoryStorage } from "@anip-dev/server";
import type { StorageBackend } from "@anip-dev/server";
import { KeyManager } from "@anip-dev/crypto";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function defaultGrantPolicy(): GrantPolicy {
  return {
    allowed_grant_types: ["one_time", "session_bound"],
    default_grant_type: "one_time",
    expires_in_seconds: 900,
    max_uses: 1,
  } as GrantPolicy;
}

function approvalRequiredCapability(opts?: {
  grantPolicy?: GrantPolicy;
}): CapabilityDef {
  const decl: CapabilityDeclaration = {
    name: "transfer_funds",
    description: "High-value transfer",
    contract_version: "1.0",
    inputs: [
      { name: "amount", type: "number", required: true, description: "amount" },
      {
        name: "to_account",
        type: "string",
        required: true,
        description: "to_account",
      },
    ],
    output: { type: "transfer_confirmation", fields: ["transfer_id"] },
    side_effect: { type: "irreversible", rollback_window: "none" },
    minimum_scope: ["finance.write"],
    grant_policy: opts?.grantPolicy ?? defaultGrantPolicy(),
  } as unknown as CapabilityDeclaration;
  return defineCapability({
    declaration: decl,
    handler: async (_ctx, params) => {
      const amount = (params.amount as number) ?? 0;
      if (amount > 10000) {
        throw new ANIPError(
          "approval_required",
          "transfer_funds requires approval for amounts above $10000",
          undefined,
          false,
          {
            preview: { amount, to_account: params.to_account },
          },
        );
      }
      return { transfer_id: "tx-1234" };
    },
  });
}

function makeKeyPath(): string {
  // KeyManager expects a file path; pass a unique non-existent path so a
  // fresh key pair is generated for this test (no persistence needed).
  const dir = mkdtempSync(join(tmpdir(), "anip-v023-keys-"));
  return join(dir, "keys.json");
}

function makeService(opts?: {
  caps?: CapabilityDef[];
  storage?: StorageBackend;
}): { service: ANIPService; storage: StorageBackend } {
  const storage = opts?.storage ?? new InMemoryStorage();
  const service = createANIPService({
    serviceId: "test-finance",
    capabilities: opts?.caps ?? [approvalRequiredCapability()],
    storage,
    keyPath: makeKeyPath(),
  });
  return { service, storage };
}

async function issueResolvedToken(
  service: ANIPService,
  opts?: { scope?: string[]; capability?: string; sessionId?: string },
): Promise<DelegationToken> {
  const issued = (await service.issueToken("human:samir@example.com", {
    subject: "human:samir@example.com",
    scope: opts?.scope ?? ["finance.write"],
    capability: opts?.capability ?? "transfer_funds",
    ttl_hours: 1,
    ...(opts?.sessionId !== undefined ? { session_id: opts.sessionId } : {}),
  })) as Record<string, unknown>;
  return service.resolveBearerToken(issued.token as string);
}

// ---------------------------------------------------------------------------
// ApprovalRequest creation
// ---------------------------------------------------------------------------

describe("ApprovalRequest creation", () => {
  it("handler_raise_creates_persistent_approval_request", async () => {
    const { service, storage } = makeService();
    const token = await issueResolvedToken(service);
    const result = await service.invoke("transfer_funds", token, {
      amount: 50000,
      to_account: "acct-2",
    });
    expect(result.success).toBe(false);
    const failure = result.failure as Record<string, unknown>;
    expect(failure.type).toBe("approval_required");
    expect(failure.approval_required).toBeDefined();
    const meta = failure.approval_required as Record<string, unknown>;
    expect((meta.approval_request_id as string).startsWith("apr_")).toBe(true);
    expect((meta.preview_digest as string).startsWith("sha256:")).toBe(true);
    expect(
      (meta.requested_parameters_digest as string).startsWith("sha256:"),
    ).toBe(true);
    expect(
      (meta.grant_policy as Record<string, unknown>).expires_in_seconds,
    ).toBe(900);
    const requestId = meta.approval_request_id as string;
    const stored = await storage.getApprovalRequest(requestId);
    expect(stored).not.toBeNull();
    expect(stored!.status).toBe("pending");
    expect(stored!.capability).toBe("transfer_funds");
    expect(stored!.requested_parameters).toEqual({
      amount: 50000,
      to_account: "acct-2",
    });
    expect(stored!.preview).toEqual({ amount: 50000, to_account: "acct-2" });
  });

  it("no_approval_when_amount_under_threshold", async () => {
    const { service } = makeService();
    const token = await issueResolvedToken(service);
    const result = await service.invoke("transfer_funds", token, {
      amount: 5000,
      to_account: "acct-2",
    });
    expect(result.success).toBe(true);
    expect((result.result as Record<string, unknown>).transfer_id).toBe(
      "tx-1234",
    );
  });

  it("storage_failure_returns_service_unavailable", async () => {
    // If store_approval_request fails, the agent sees service_unavailable,
    // not approval_required. SPEC.md §4.7.
    const { service, storage } = makeService();
    (storage as unknown as Record<string, unknown>).storeApprovalRequest =
      async () => {
        throw new Error("storage offline");
      };
    const token = await issueResolvedToken(service);
    const result = await service.invoke("transfer_funds", token, {
      amount: 50000,
      to_account: "acct-2",
    });
    expect(result.success).toBe(false);
    const failure = result.failure as Record<string, unknown>;
    expect(failure.type).toBe("service_unavailable");
    expect(failure.approval_required).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// issueApprovalGrant SPI
// ---------------------------------------------------------------------------

describe("issueApprovalGrant SPI", () => {
  let service: ANIPService;
  let storage: StorageBackend;

  beforeEach(() => {
    ({ service, storage } = makeService());
  });

  async function triggerApproval(): Promise<string> {
    const token = await issueResolvedToken(service);
    const result = await service.invoke("transfer_funds", token, {
      amount: 50000,
      to_account: "acct-2",
    });
    return ((result.failure as Record<string, unknown>).approval_required as Record<
      string,
      unknown
    >).approval_request_id as string;
  }

  it("issue_grant_happy_path_one_time", async () => {
    const requestId = await triggerApproval();
    const grant = await service.issueApprovalGrant(requestId, "one_time", {
      principal: "manager_456",
    });
    expect((grant.grant_id as string).startsWith("grant_")).toBe(true);
    expect(grant.approval_request_id).toBe(requestId);
    expect(grant.grant_type).toBe("one_time");
    expect(grant.max_uses).toBe(1);
    expect(grant.use_count).toBe(0);
    expect(grant.capability).toBe("transfer_funds");
    expect(grant.scope).toEqual(["finance.write"]);
    expect(grant.session_id).toBeNull();
    expect(grant.signature).not.toBe("");
    const stored = await storage.getApprovalRequest(requestId);
    expect(stored!.status).toBe("approved");
    expect(stored!.approver).toEqual({ principal: "manager_456" });
    expect(stored!.decided_at).not.toBeNull();
  });

  it("issue_grant_happy_path_session_bound", async () => {
    const requestId = await triggerApproval();
    const grant = await service.issueApprovalGrant(
      requestId,
      "session_bound",
      { principal: "manager_456" },
      { sessionId: "sess-X" },
    );
    expect(grant.grant_type).toBe("session_bound");
    expect(grant.session_id).toBe("sess-X");
  });

  it("issue_grant_unknown_request_id", async () => {
    await expect(
      service.issueApprovalGrant("apr_does_not_exist", "one_time", { p: "u" }),
    ).rejects.toMatchObject({ errorType: "approval_request_not_found" });
  });

  it("issue_grant_already_decided", async () => {
    const requestId = await triggerApproval();
    await service.issueApprovalGrant(requestId, "one_time", { p: "u1" });
    await expect(
      service.issueApprovalGrant(requestId, "one_time", { p: "u2" }),
    ).rejects.toMatchObject({ errorType: "approval_request_already_decided" });
  });

  it("issue_grant_type_not_in_policy", async () => {
    const policy: GrantPolicy = {
      allowed_grant_types: ["one_time"],
      default_grant_type: "one_time",
      expires_in_seconds: 900,
      max_uses: 1,
    } as GrantPolicy;
    const { service: svc } = makeService({
      caps: [approvalRequiredCapability({ grantPolicy: policy })],
    });
    const token = await issueResolvedToken(svc);
    const result = await svc.invoke("transfer_funds", token, {
      amount: 50000,
      to_account: "x",
    });
    const requestId = ((result.failure as Record<string, unknown>)
      .approval_required as Record<string, unknown>).approval_request_id as string;
    await expect(
      svc.issueApprovalGrant(
        requestId,
        "session_bound",
        { p: "u" },
        { sessionId: "s1" },
      ),
    ).rejects.toMatchObject({ errorType: "grant_type_not_allowed_by_policy" });
  });

  it("issue_grant_session_bound_requires_session_id", async () => {
    const requestId = await triggerApproval();
    await expect(
      service.issueApprovalGrant(requestId, "session_bound", { p: "u" }),
    ).rejects.toMatchObject({ errorType: "grant_type_not_allowed_by_policy" });
  });

  it("issue_grant_one_time_rejects_session_id", async () => {
    const requestId = await triggerApproval();
    await expect(
      service.issueApprovalGrant(
        requestId,
        "one_time",
        { p: "u" },
        { sessionId: "s1" },
      ),
    ).rejects.toMatchObject({ errorType: "grant_type_not_allowed_by_policy" });
  });

  it("issue_grant_clamps_max_uses_to_policy_for_session_bound", async () => {
    // Policy with max_uses=2; session_bound issuance asking for 99 must reject.
    const policy: GrantPolicy = {
      allowed_grant_types: ["session_bound"],
      default_grant_type: "session_bound",
      expires_in_seconds: 900,
      max_uses: 2,
    } as GrantPolicy;
    const { service: svc } = makeService({
      caps: [approvalRequiredCapability({ grantPolicy: policy })],
    });
    const token = await issueResolvedToken(svc);
    const result = await svc.invoke("transfer_funds", token, {
      amount: 50000,
      to_account: "x",
    });
    const reqId = ((result.failure as Record<string, unknown>)
      .approval_required as Record<string, unknown>).approval_request_id as string;
    await expect(
      svc.issueApprovalGrant(
        reqId,
        "session_bound",
        { p: "u" },
        { sessionId: "s1", maxUses: 99 },
      ),
    ).rejects.toMatchObject({ errorType: "grant_type_not_allowed_by_policy" });
  });

  it("issue_grant_clamps_expires_in_seconds_to_policy", async () => {
    const requestId = await triggerApproval();
    await expect(
      service.issueApprovalGrant(
        requestId,
        "one_time",
        { p: "u" },
        { expiresInSeconds: 999999 },
      ),
    ).rejects.toMatchObject({ errorType: "grant_type_not_allowed_by_policy" });
  });

  it("issue_grant_capability_scope_copied_from_request", async () => {
    // Grant fields MUST come from the approval_request, not from caller args.
    // Per SPEC.md §4.9 step 8.
    const requestId = await triggerApproval();
    const request = await storage.getApprovalRequest(requestId);
    const grant = await service.issueApprovalGrant(requestId, "one_time", {
      p: "u",
    });
    expect(grant.capability).toBe(request!.capability);
    expect(grant.scope).toEqual(request!.scope);
    expect(grant.approved_parameters_digest).toBe(
      request!.requested_parameters_digest,
    );
    expect(grant.preview_digest).toBe(request!.preview_digest);
    expect(grant.requester).toEqual(request!.requester);
  });
});

// ---------------------------------------------------------------------------
// validateContinuationGrant
// ---------------------------------------------------------------------------

describe("validateContinuationGrant", () => {
  let service: ANIPService;
  let storage: StorageBackend;
  let keyDir: string;

  beforeEach(() => {
    keyDir = makeKeyPath();
    storage = new InMemoryStorage();
    service = createANIPService({
      serviceId: "test-finance",
      capabilities: [approvalRequiredCapability()],
      storage,
      keyPath: keyDir,
    });
  });

  async function makeGrant(): Promise<{
    grantId: string;
    token: DelegationToken;
  }> {
    const token = await issueResolvedToken(service);
    const result = await service.invoke("transfer_funds", token, {
      amount: 50000,
      to_account: "x",
    });
    const requestId = ((result.failure as Record<string, unknown>)
      .approval_required as Record<string, unknown>).approval_request_id as string;
    const grant = await service.issueApprovalGrant(requestId, "one_time", {
      p: "u",
    });
    return { grantId: grant.grant_id as string, token };
  }

  it("capability_mismatch", async () => {
    const { grantId, token } = await makeGrant();
    const keyManager = new KeyManager(keyDir);
    await keyManager.ready();
    const [g, fail] = await validateContinuationGrant({
      storage,
      grantId,
      capability: "some_other_capability",
      parameters: { amount: 50000, to_account: "x" },
      tokenScope: token.scope ?? [],
      tokenSessionId: null,
      keyManager,
      nowIso: utcNowIso(),
    });
    expect(g).toBeNull();
    expect(fail).toBe("grant_capability_mismatch");
  });

  it("scope_mismatch", async () => {
    const { grantId } = await makeGrant();
    const keyManager = new KeyManager(keyDir);
    await keyManager.ready();
    const [g, fail] = await validateContinuationGrant({
      storage,
      grantId,
      capability: "transfer_funds",
      parameters: { amount: 50000, to_account: "x" },
      tokenScope: ["other.scope"], // missing finance.write
      tokenSessionId: null,
      keyManager,
      nowIso: utcNowIso(),
    });
    expect(g).toBeNull();
    expect(fail).toBe("grant_scope_mismatch");
  });

  it("param_drift", async () => {
    const { grantId, token } = await makeGrant();
    const keyManager = new KeyManager(keyDir);
    await keyManager.ready();
    const [g, fail] = await validateContinuationGrant({
      storage,
      grantId,
      capability: "transfer_funds",
      parameters: { amount: 99999, to_account: "y" }, // changed from approved
      tokenScope: token.scope ?? [],
      tokenSessionId: null,
      keyManager,
      nowIso: utcNowIso(),
    });
    expect(g).toBeNull();
    expect(fail).toBe("grant_param_drift");
  });

  it("expired", async () => {
    const { grantId, token } = await makeGrant();
    const keyManager = new KeyManager(keyDir);
    await keyManager.ready();
    const futureNow = new Date(Date.now() + 9999 * 1000).toISOString();
    const [g, fail] = await validateContinuationGrant({
      storage,
      grantId,
      capability: "transfer_funds",
      parameters: { amount: 50000, to_account: "x" },
      tokenScope: token.scope ?? [],
      tokenSessionId: null,
      keyManager,
      nowIso: futureNow,
    });
    expect(g).toBeNull();
    expect(fail).toBe("grant_expired");
  });

  it("session_mismatch", async () => {
    const token = await issueResolvedToken(service);
    const result = await service.invoke("transfer_funds", token, {
      amount: 50000,
      to_account: "x",
    });
    const requestId = ((result.failure as Record<string, unknown>)
      .approval_required as Record<string, unknown>).approval_request_id as string;
    const grant = await service.issueApprovalGrant(
      requestId,
      "session_bound",
      { p: "u" },
      { sessionId: "sess-A" },
    );
    const keyManager = new KeyManager(keyDir);
    await keyManager.ready();
    const [g, fail] = await validateContinuationGrant({
      storage,
      grantId: grant.grant_id as string,
      capability: "transfer_funds",
      parameters: { amount: 50000, to_account: "x" },
      tokenScope: token.scope ?? [],
      tokenSessionId: "sess-B", // wrong session
      keyManager,
      nowIso: utcNowIso(),
    });
    expect(g).toBeNull();
    expect(fail).toBe("grant_session_invalid");
  });
});

// ---------------------------------------------------------------------------
// Continuation invocation end-to-end
// ---------------------------------------------------------------------------

describe("Continuation invocation", () => {
  it("happy_path_consumes_grant_and_second_use_returns_grant_consumed", async () => {
    const { service, storage } = makeService();
    const token = await issueResolvedToken(service);
    const first = await service.invoke("transfer_funds", token, {
      amount: 50000,
      to_account: "x",
    });
    const requestId = ((first.failure as Record<string, unknown>)
      .approval_required as Record<string, unknown>).approval_request_id as string;
    const grant = await service.issueApprovalGrant(requestId, "one_time", {
      p: "u",
    });
    const grantId = grant.grant_id as string;
    const token2 = await issueResolvedToken(service);
    await service.invoke(
      "transfer_funds",
      token2,
      { amount: 50000, to_account: "x" },
      { approvalGrant: grantId },
    );
    const reservedGrant = await storage.getGrant(grantId);
    expect(reservedGrant!.use_count).toBe(1);
    const result2 = await service.invoke(
      "transfer_funds",
      token2,
      { amount: 50000, to_account: "x" },
      { approvalGrant: grantId },
    );
    expect(result2.success).toBe(false);
    expect((result2.failure as Record<string, unknown>).type).toBe(
      "grant_consumed",
    );
  });

  it("grant_not_found", async () => {
    const { service } = makeService();
    const token = await issueResolvedToken(service);
    const result = await service.invoke(
      "transfer_funds",
      token,
      { amount: 5000, to_account: "x" },
      { approvalGrant: "grant_does_not_exist" },
    );
    expect(result.success).toBe(false);
    expect((result.failure as Record<string, unknown>).type).toBe(
      "grant_not_found",
    );
  });

  it("param_drift_on_continuation", async () => {
    const { service } = makeService();
    const token = await issueResolvedToken(service);
    const first = await service.invoke("transfer_funds", token, {
      amount: 50000,
      to_account: "x",
    });
    const requestId = ((first.failure as Record<string, unknown>)
      .approval_required as Record<string, unknown>).approval_request_id as string;
    const grant = await service.issueApprovalGrant(requestId, "one_time", {
      p: "u",
    });
    const token2 = await issueResolvedToken(service);
    const result = await service.invoke(
      "transfer_funds",
      token2,
      { amount: 99999, to_account: "y" }, // changed
      { approvalGrant: grant.grant_id as string },
    );
    expect(result.success).toBe(false);
    expect((result.failure as Record<string, unknown>).type).toBe(
      "grant_param_drift",
    );
  });
});

// ---------------------------------------------------------------------------
// Audit linkage
// ---------------------------------------------------------------------------

describe("Audit linkage", () => {
  it("full_audit_chain_reconstructible", async () => {
    // SPEC.md §4.9: every approval flow must be reconstructible from audit
    // entries via parent_invocation_id → approval_request_id → grant_id →
    // continuation_invocation_id.
    const { service, storage } = makeService();
    const token = await issueResolvedToken(service);
    const first = await service.invoke("transfer_funds", token, {
      amount: 50000,
      to_account: "x",
    });
    const firstInvocationId = first.invocation_id as string;
    const approvalRequestId = ((first.failure as Record<string, unknown>)
      .approval_required as Record<string, unknown>)
      .approval_request_id as string;

    const grant = await service.issueApprovalGrant(
      approvalRequestId,
      "one_time",
      { principal: "manager_456" },
    );
    const grantId = grant.grant_id as string;

    const token2 = await issueResolvedToken(service);
    const cont = await service.invoke(
      "transfer_funds",
      token2,
      { amount: 50000, to_account: "x" },
      { approvalGrant: grantId },
    );
    const continuationInvocationId = cont.invocation_id as string;

    const allEntries = await storage.queryAuditEntries({ limit: 100 });

    // 3a. The original failure carries approval_request_id.
    const original = allEntries.filter(
      (e) => e.invocation_id === firstInvocationId,
    );
    expect(original.length).toBeGreaterThanOrEqual(1);
    const failureEntry = original.find(
      (e) => e.failure_type === "approval_required",
    );
    expect(failureEntry).toBeDefined();
    expect(failureEntry!.approval_request_id).toBe(approvalRequestId);

    // 3b. approval_request_created event with parent_invocation_id pointing
    // to the original invocation.
    const requestCreated = allEntries.filter(
      (e) =>
        e.entry_type === "approval_request_created" &&
        e.approval_request_id === approvalRequestId,
    );
    expect(requestCreated).toHaveLength(1);
    expect(requestCreated[0].parent_invocation_id).toBe(firstInvocationId);

    // 3b'. Persisted ApprovalRequest carries parent_invocation_id = the
    // invocation that raised approval_required (not the inbound caller's
    // parent). SPEC.md §4.7 line 916.
    const persisted = await storage.getApprovalRequest(approvalRequestId);
    expect(persisted).not.toBeNull();
    expect(persisted!.parent_invocation_id).toBe(firstInvocationId);

    // 3c. approval_grant_issued event links request_id ↔ grant_id.
    const grantIssued = allEntries.filter(
      (e) =>
        e.entry_type === "approval_grant_issued" &&
        e.approval_grant_id === grantId,
    );
    expect(grantIssued).toHaveLength(1);
    expect(grantIssued[0].approval_request_id).toBe(approvalRequestId);

    // 3d. Continuation audit entry references the grant.
    const continuation = allEntries.filter(
      (e) => e.invocation_id === continuationInvocationId,
    );
    expect(continuation.length).toBeGreaterThanOrEqual(1);
    expect(
      continuation.some((e) => e.approval_grant_id === grantId),
    ).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Concurrent issuance
// ---------------------------------------------------------------------------

describe("Concurrent issuance", () => {
  it("only_one_succeeds", async () => {
    const { service, storage } = makeService();
    const token = await issueResolvedToken(service);
    const result = await service.invoke("transfer_funds", token, {
      amount: 50000,
      to_account: "x",
    });
    const requestId = ((result.failure as Record<string, unknown>)
      .approval_required as Record<string, unknown>)
      .approval_request_id as string;

    const n = 10;
    const outcomes = await Promise.all(
      Array.from({ length: n }, async (_, i) => {
        try {
          return await service.issueApprovalGrant(requestId, "one_time", {
            p: `u${i}`,
          });
        } catch (e) {
          if (e instanceof ANIPError) return e.errorType;
          throw e;
        }
      }),
    );
    const successes = outcomes.filter((o) => typeof o === "object");
    const rejections = outcomes.filter((o) => typeof o === "string");
    expect(successes).toHaveLength(1);
    expect(rejections).toHaveLength(n - 1);
    for (const r of rejections) {
      expect(r).toBe("approval_request_already_decided");
    }
    const stored = await storage.getApprovalRequest(requestId);
    expect(stored!.status).toBe("approved");
  });
});
