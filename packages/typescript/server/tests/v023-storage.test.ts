/**
 * Storage tests for v0.23 approval requests + grants.
 *
 * Mirrors anip-server/tests/test_v023_storage.py. Parameterized over both
 * InMemoryStorage and SQLiteStorage.
 */
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { unlinkSync } from "node:fs";
import { randomUUID } from "node:crypto";
import {
  InMemoryStorage,
  SQLiteStorage,
  type StorageBackend,
} from "../src/storage.js";

function nowIso(): string {
  return new Date().toISOString();
}

function futureIso(seconds = 900): string {
  return new Date(Date.now() + seconds * 1000).toISOString();
}

function pastIso(seconds = 1): string {
  return new Date(Date.now() - seconds * 1000).toISOString();
}

function approvalRequest(opts?: {
  request_id?: string;
  capability?: string;
  expires_at?: string;
}): Record<string, unknown> {
  return {
    approval_request_id: opts?.request_id ?? "apr_test",
    capability: opts?.capability ?? "finance.transfer_funds",
    scope: ["finance.write"],
    requester: { principal: "user_123" },
    parent_invocation_id: null,
    preview: { amount: 50000 },
    preview_digest: "sha256:preview",
    requested_parameters: { amount: 50000 },
    requested_parameters_digest: "sha256:params",
    grant_policy: {
      allowed_grant_types: ["one_time"],
      default_grant_type: "one_time",
      expires_in_seconds: 900,
      max_uses: 1,
    },
    status: "pending",
    approver: null,
    decided_at: null,
    created_at: nowIso(),
    expires_at: opts?.expires_at ?? futureIso(),
  };
}

function grant(opts?: {
  grant_id?: string;
  request_id?: string;
  grant_type?: string;
  max_uses?: number;
  session_id?: string | null;
  expires_at?: string;
}): Record<string, unknown> {
  return {
    grant_id: opts?.grant_id ?? "grant_test",
    approval_request_id: opts?.request_id ?? "apr_test",
    grant_type: opts?.grant_type ?? "one_time",
    capability: "finance.transfer_funds",
    scope: ["finance.write"],
    approved_parameters_digest: "sha256:params",
    preview_digest: "sha256:preview",
    requester: { principal: "user_123" },
    approver: { principal: "manager_456" },
    issued_at: nowIso(),
    expires_at: opts?.expires_at ?? futureIso(),
    max_uses: opts?.max_uses ?? 1,
    use_count: 0,
    session_id: opts?.session_id ?? null,
    signature: "sig_test",
  };
}

async function ensureApprovalRequestFor(
  store: StorageBackend,
  request_id: string = "apr_test",
): Promise<void> {
  // SQLite enforces an FK on approval_request_id; seed a parent row so the
  // FK is satisfied. InMemoryStorage tolerates missing parents.
  if (store instanceof SQLiteStorage) {
    await store.storeApprovalRequest(approvalRequest({ request_id }));
  }
}

type Backend = "inmem" | "sqlite";

const BACKENDS: Backend[] = ["inmem", "sqlite"];

for (const backend of BACKENDS) {
  describe(`v0.23 storage (${backend})`, () => {
    let store: StorageBackend;
    let dbPath: string | null;

    beforeEach(() => {
      if (backend === "inmem") {
        store = new InMemoryStorage();
        dbPath = null;
      } else {
        dbPath = `/tmp/anip-v023-${randomUUID()}.db`;
        store = new SQLiteStorage(dbPath);
      }
    });

    afterEach(async () => {
      if (store instanceof SQLiteStorage) {
        await store.terminate();
      }
      if (dbPath !== null) {
        for (const suffix of ["", "-wal", "-shm"]) {
          try {
            unlinkSync(dbPath + suffix);
          } catch {
            // ignore
          }
        }
      }
    });

    // -- store / get round-trips ------------------------------------------------

    it("store_and_get_approval_request_round_trip", async () => {
      const req = approvalRequest();
      await store.storeApprovalRequest(req);
      const loaded = await store.getApprovalRequest("apr_test");
      expect(loaded).not.toBeNull();
      expect(loaded!.approval_request_id).toBe("apr_test");
      expect(loaded!.capability).toBe("finance.transfer_funds");
      expect(loaded!.status).toBe("pending");
      expect(loaded!.scope).toEqual(["finance.write"]);
      expect((loaded!.grant_policy as Record<string, unknown>).expires_in_seconds).toBe(900);
    });

    it("get_approval_request_missing_returns_null", async () => {
      expect(await store.getApprovalRequest("nope")).toBeNull();
    });

    it("store_approval_request_idempotent_same_content", async () => {
      // SPEC.md §4.7: re-storing identical content under same id is a no-op.
      const req = approvalRequest();
      await store.storeApprovalRequest(req);
      await store.storeApprovalRequest({ ...req });
      const loaded = await store.getApprovalRequest("apr_test");
      expect(loaded).not.toBeNull();
      expect(loaded!.approval_request_id).toBe("apr_test");
    });

    it("store_approval_request_conflict_raises", async () => {
      // SPEC.md §4.7: re-storing different content under same id is an error.
      const req = approvalRequest();
      await store.storeApprovalRequest(req);
      const mutated = { ...req, preview: { amount: 99999 } };
      await expect(store.storeApprovalRequest(mutated)).rejects.toThrow(
        /already stored with different content/,
      );
      // Original content preserved.
      const loaded = await store.getApprovalRequest("apr_test");
      expect(loaded!.preview).toEqual({ amount: 50000 });
    });

    it("store_and_get_grant_round_trip", async () => {
      await ensureApprovalRequestFor(store);
      const g = grant();
      await store.storeGrant(g);
      const loaded = await store.getGrant("grant_test");
      expect(loaded).not.toBeNull();
      expect(loaded!.grant_id).toBe("grant_test");
      expect(loaded!.approval_request_id).toBe("apr_test");
      expect(loaded!.use_count).toBe(0);
    });

    // -- approveRequestAndStoreGrant -----------------------------------------

    it("approve_request_and_store_grant_happy_path", async () => {
      const req = approvalRequest();
      await store.storeApprovalRequest(req);
      const result = await store.approveRequestAndStoreGrant(
        "apr_test",
        grant(),
        { principal: "manager_456" },
        nowIso(),
        nowIso(),
      );
      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.grant.grant_id).toBe("grant_test");
      }
      const loadedReq = await store.getApprovalRequest("apr_test");
      expect(loadedReq!.status).toBe("approved");
      expect(loadedReq!.approver).toEqual({ principal: "manager_456" });
      const loadedGrant = await store.getGrant("grant_test");
      expect(loadedGrant).not.toBeNull();
    });

    it("approve_request_not_found", async () => {
      const result = await store.approveRequestAndStoreGrant(
        "nope",
        grant(),
        {},
        nowIso(),
        nowIso(),
      );
      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.reason).toBe("approval_request_not_found");
      }
    });

    it("approve_already_decided", async () => {
      const req = approvalRequest();
      await store.storeApprovalRequest(req);
      await store.approveRequestAndStoreGrant(
        "apr_test",
        grant({ grant_id: "g1" }),
        { principal: "u2" },
        nowIso(),
        nowIso(),
      );
      const result = await store.approveRequestAndStoreGrant(
        "apr_test",
        grant({ grant_id: "g2" }),
        { principal: "u3" },
        nowIso(),
        nowIso(),
      );
      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.reason).toBe("approval_request_already_decided");
      }
    });

    it("approve_request_expired", async () => {
      const req = approvalRequest({ expires_at: pastIso() });
      await store.storeApprovalRequest(req);
      const result = await store.approveRequestAndStoreGrant(
        "apr_test",
        grant(),
        { principal: "u2" },
        nowIso(),
        nowIso(),
      );
      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.reason).toBe("approval_request_expired");
      }
    });

    it("concurrent_approve_request_and_store_grant", async () => {
      // Concurrent approval attempts: exactly 1 succeeds, N-1 receive
      // approval_request_already_decided.
      const req = approvalRequest();
      await store.storeApprovalRequest(req);
      const n = 10;
      const grants = Array.from({ length: n }, (_, i) =>
        grant({ grant_id: `g${i}` }),
      );
      const results = await Promise.all(
        grants.map((g, i) =>
          store.approveRequestAndStoreGrant(
            "apr_test",
            g,
            { principal: `u${i}` },
            nowIso(),
            nowIso(),
          ),
        ),
      );
      const successes = results.filter((r) => r.ok);
      const failures = results.filter((r) => !r.ok);
      expect(successes).toHaveLength(1);
      expect(failures).toHaveLength(n - 1);
      for (const f of failures) {
        if (!f.ok) {
          expect(f.reason).toBe("approval_request_already_decided");
        }
      }
      const loadedReq = await store.getApprovalRequest("apr_test");
      expect(loadedReq!.status).toBe("approved");
    });

    // -- tryReserveGrant -----------------------------------------------------

    it("try_reserve_grant_happy_path", async () => {
      await ensureApprovalRequestFor(store);
      await store.storeGrant(grant());
      const result = await store.tryReserveGrant("grant_test", nowIso());
      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.grant.use_count).toBe(1);
      }
    });

    it("try_reserve_grant_not_found", async () => {
      const result = await store.tryReserveGrant("nope", nowIso());
      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.reason).toBe("grant_not_found");
      }
    });

    it("try_reserve_grant_expired", async () => {
      await ensureApprovalRequestFor(store);
      await store.storeGrant(grant({ expires_at: pastIso() }));
      const result = await store.tryReserveGrant("grant_test", nowIso());
      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.reason).toBe("grant_expired");
      }
    });

    it("try_reserve_grant_one_time_consumed", async () => {
      await ensureApprovalRequestFor(store);
      await store.storeGrant(grant({ max_uses: 1 }));
      const first = await store.tryReserveGrant("grant_test", nowIso());
      expect(first.ok).toBe(true);
      const second = await store.tryReserveGrant("grant_test", nowIso());
      expect(second.ok).toBe(false);
      if (!second.ok) {
        expect(second.reason).toBe("grant_consumed");
      }
    });

    it("try_reserve_grant_session_bound_max_uses", async () => {
      await ensureApprovalRequestFor(store);
      await store.storeGrant(
        grant({ grant_type: "session_bound", max_uses: 3, session_id: "sess_1" }),
      );
      for (let i = 0; i < 3; i++) {
        const r = await store.tryReserveGrant("grant_test", nowIso());
        expect(r.ok).toBe(true);
      }
      const fourth = await store.tryReserveGrant("grant_test", nowIso());
      expect(fourth.ok).toBe(false);
      if (!fourth.ok) {
        expect(fourth.reason).toBe("grant_consumed");
      }
    });

    it("concurrent_try_reserve_grant_one_time", async () => {
      // N parallel reservations: exactly 1 succeeds, N-1 receive grant_consumed.
      await ensureApprovalRequestFor(store);
      await store.storeGrant(grant({ max_uses: 1 }));
      const n = 10;
      const results = await Promise.all(
        Array.from({ length: n }, () =>
          store.tryReserveGrant("grant_test", nowIso()),
        ),
      );
      const successes = results.filter((r) => r.ok);
      const failures = results.filter((r) => !r.ok);
      expect(successes).toHaveLength(1);
      expect(failures).toHaveLength(n - 1);
      for (const f of failures) {
        if (!f.ok) {
          expect(f.reason).toBe("grant_consumed");
        }
      }
    });

    it("concurrent_try_reserve_session_bound_respects_max_uses", async () => {
      await ensureApprovalRequestFor(store);
      await store.storeGrant(
        grant({ grant_type: "session_bound", max_uses: 3, session_id: "sess_1" }),
      );
      const n = 10;
      const results = await Promise.all(
        Array.from({ length: n }, () =>
          store.tryReserveGrant("grant_test", nowIso()),
        ),
      );
      const successes = results.filter((r) => r.ok);
      const failures = results.filter((r) => !r.ok);
      expect(successes).toHaveLength(3);
      expect(failures).toHaveLength(7);
    });
  });
}

// -- defense-in-depth ------------------------------------------------------

describe("v0.23 storage defense-in-depth (sqlite)", () => {
  let store: SQLiteStorage;
  let dbPath: string;

  beforeEach(() => {
    dbPath = `/tmp/anip-v023-fk-${randomUUID()}.db`;
    store = new SQLiteStorage(dbPath);
  });

  afterEach(async () => {
    await store.terminate();
    for (const suffix of ["", "-wal", "-shm"]) {
      try {
        unlinkSync(dbPath + suffix);
      } catch {
        // ignore
      }
    }
  });

  it("grants_unique_approval_request_id_constraint_sqlite", async () => {
    // Defense-in-depth: even if a flawed implementation bypassed the
    // conditional UPDATE in approveRequestAndStoreGrant, the grants table
    // must enforce UNIQUE(approval_request_id). Exercised end-to-end via
    // approveRequestAndStoreGrant: a second approval attempt against an
    // already-approved request must fail with approval_request_already_decided
    // (which is what the worker translates the UNIQUE violation into when
    // the conditional UPDATE matches but the INSERT collides — see the
    // try/catch around the INSERT in sqlite-worker.ts).
    await store.storeApprovalRequest(approvalRequest({ request_id: "apr_x" }));
    const g1 = grant({ grant_id: "g1", request_id: "apr_x" });
    const r1 = await store.approveRequestAndStoreGrant(
      "apr_x",
      g1,
      { principal: "u1" },
      nowIso(),
      nowIso(),
    );
    expect(r1.ok).toBe(true);
    const g2 = grant({ grant_id: "g2", request_id: "apr_x" });
    const r2 = await store.approveRequestAndStoreGrant(
      "apr_x",
      g2,
      { principal: "u2" },
      nowIso(),
      nowIso(),
    );
    expect(r2.ok).toBe(false);
    if (!r2.ok) {
      expect(r2.reason).toBe("approval_request_already_decided");
    }
    // Only the first grant exists.
    const stored1 = await store.getGrant("g1");
    expect(stored1).not.toBeNull();
    const stored2 = await store.getGrant("g2");
    expect(stored2).toBeNull();
  });
});
