/**
 * Tests for PostgresStorage backend.
 *
 * These tests are skipped unless the ANIP_TEST_POSTGRES_DSN environment
 * variable is set (e.g. "postgresql://user:pass@localhost:5432/anip_test").
 */
import { describe, it, expect, beforeEach, afterAll } from "vitest";
import { PostgresStorage } from "../src/postgres.js";
import { ALL_COMPLIANCE_TESTS } from "./compliance.js";

const POSTGRES_DSN = process.env.ANIP_TEST_POSTGRES_DSN;
const describeIf = POSTGRES_DSN ? describe : describe.skip;

describeIf("PostgresStorage", () => {
  let store: PostgresStorage;

  beforeEach(async () => {
    store = new PostgresStorage(POSTGRES_DSN!);
    await store.initialize();
    await store.clearAll();
  });

  afterAll(async () => {
    if (store) {
      await store.close();
    }
  });

  // -----------------------------------------------------------------------
  // Horizontal-scaling methods
  // -----------------------------------------------------------------------

  describe("appendAuditEntry", () => {
    it("first entry gets sequence 1", async () => {
      const entry = await store.appendAuditEntry({
        capability: "test",
        success: true,
        timestamp: "2026-01-01T00:00:00Z",
      });
      expect(entry.sequence_number).toBe(1);
      expect(entry.previous_hash).toBe("sha256:0");
    });

    it("sequential entries increment", async () => {
      await store.appendAuditEntry({
        capability: "a",
        success: true,
        timestamp: "2026-01-01T00:00:00Z",
      });
      const e2 = await store.appendAuditEntry({
        capability: "b",
        success: true,
        timestamp: "2026-01-01T00:00:01Z",
      });
      expect(e2.sequence_number).toBe(2);
      expect(e2.previous_hash).not.toBe("sha256:0");
    });

    it("previous hash chains", async () => {
      await store.appendAuditEntry({
        capability: "a",
        success: true,
        timestamp: "2026-01-01T00:00:00Z",
      });
      const e2 = await store.appendAuditEntry({
        capability: "b",
        success: true,
        timestamp: "2026-01-01T00:00:01Z",
      });
      expect((e2.previous_hash as string).startsWith("sha256:")).toBe(true);
      expect((e2.previous_hash as string).length).toBeGreaterThan(10);
    });
  });

  describe("updateAuditSignature", () => {
    it("updates signature on existing entry", async () => {
      const entry = await store.appendAuditEntry({
        capability: "test",
        success: true,
        timestamp: "2026-01-01T00:00:00Z",
      });
      await store.updateAuditSignature(entry.sequence_number as number, "sig-abc");
      const last = await store.getLastAuditEntry();
      expect(last).not.toBeNull();
      expect(last!.signature).toBe("sig-abc");
    });
  });

  describe("getMaxAuditSequence", () => {
    it("returns null when empty", async () => {
      expect(await store.getMaxAuditSequence()).toBeNull();
    });

    it("returns highest sequence number", async () => {
      await store.appendAuditEntry({
        capability: "a",
        success: true,
        timestamp: "2026-01-01T00:00:00Z",
      });
      await store.appendAuditEntry({
        capability: "b",
        success: true,
        timestamp: "2026-01-01T00:00:01Z",
      });
      expect(await store.getMaxAuditSequence()).toBe(2);
    });
  });

  describe("exclusive leases", () => {
    it("acquire and release", async () => {
      expect(await store.tryAcquireExclusive("key1", "holder-a", 30)).toBe(true);
      expect(await store.tryAcquireExclusive("key1", "holder-b", 30)).toBe(false);
      await store.releaseExclusive("key1", "holder-a");
      expect(await store.tryAcquireExclusive("key1", "holder-b", 30)).toBe(true);
    });

    it("same holder can reacquire", async () => {
      expect(await store.tryAcquireExclusive("key1", "holder-a", 30)).toBe(true);
      expect(await store.tryAcquireExclusive("key1", "holder-a", 30)).toBe(true);
    });

    it("wrong holder cannot release", async () => {
      await store.tryAcquireExclusive("key1", "holder-a", 30);
      await store.releaseExclusive("key1", "holder-b"); // wrong holder
      expect(await store.tryAcquireExclusive("key1", "holder-b", 30)).toBe(false);
    });
  });

  describe("leader leases", () => {
    it("acquire leader", async () => {
      expect(await store.tryAcquireLeader("checkpoint", "replica-1", 60)).toBe(true);
      expect(await store.tryAcquireLeader("checkpoint", "replica-2", 60)).toBe(false);
    });

    it("release and reacquire", async () => {
      await store.tryAcquireLeader("checkpoint", "replica-1", 60);
      await store.releaseLeader("checkpoint", "replica-1");
      expect(await store.tryAcquireLeader("checkpoint", "replica-2", 60)).toBe(true);
    });
  });

  // -----------------------------------------------------------------------
  // Backend compliance suite
  // -----------------------------------------------------------------------

  describe("compliance", () => {
    for (const test of ALL_COMPLIANCE_TESTS) {
      it(test.name, async () => {
        await test.fn(store);
      });
    }
  });

  // -----------------------------------------------------------------------
  // Postgres-specific tests
  // -----------------------------------------------------------------------

  describe("token storage", () => {
    it("stores and loads a delegation token", async () => {
      const token = {
        token_id: "tok-pg-1",
        issuer: "svc",
        subject: "agent",
        scope: ["travel.search"],
        purpose: { capability: "search", parameters: {} },
        parent: null,
        expires: "2026-12-31T23:59:59Z",
        constraints: { max_delegation_depth: 3 },
        root_principal: "human:alice",
      };
      await store.storeToken(token);
      const loaded = await store.loadToken("tok-pg-1");
      expect(loaded).not.toBeNull();
      expect(loaded!.token_id).toBe("tok-pg-1");
      expect(loaded!.scope).toEqual(["travel.search"]);
      expect(loaded!.constraints).toEqual({ max_delegation_depth: 3 });
    });

    it("returns null for nonexistent token", async () => {
      expect(await store.loadToken("nonexistent")).toBeNull();
    });
  });

  describe("audit v0.8 fields", () => {
    it("stores and queries entry with event_class, retention_tier, expires_at", async () => {
      const entry = {
        sequence_number: 1,
        timestamp: "2026-03-16T12:00:00Z",
        capability: "test.cap",
        token_id: "t1",
        issuer: "svc",
        subject: "agent",
        root_principal: "human",
        parameters: null,
        success: true,
        result_summary: null,
        failure_type: null,
        cost_actual: null,
        delegation_chain: null,
        invocation_id: "inv-1",
        client_reference_id: null,
        stream_summary: null,
        previous_hash: "sha256:0000",
        signature: null,
        event_class: "high_risk_success",
        retention_tier: "long",
        expires_at: "2027-03-16T12:00:00Z",
      };
      await store.storeAuditEntry(entry);
      const rows = await store.queryAuditEntries({ capability: "test.cap" });
      expect(rows).toHaveLength(1);
      expect(rows[0].event_class).toBe("high_risk_success");
      expect(rows[0].retention_tier).toBe("long");
      expect(rows[0].expires_at).toBe("2027-03-16T12:00:00Z");
    });

    it("deletes expired audit entries", async () => {
      const base = {
        timestamp: "2026-03-16T12:00:00Z",
        capability: "test.cap",
        token_id: "t1",
        issuer: "svc",
        subject: "agent",
        root_principal: "human",
        parameters: null,
        success: true,
        result_summary: null,
        failure_type: null,
        cost_actual: null,
        delegation_chain: null,
        invocation_id: null,
        client_reference_id: null,
        stream_summary: null,
        previous_hash: "sha256:0000",
        signature: null,
        event_class: "malformed_or_spam",
        retention_tier: "short",
      };
      await store.storeAuditEntry({ ...base, sequence_number: 1, expires_at: "2026-03-10T00:00:00Z" });
      await store.storeAuditEntry({ ...base, sequence_number: 2, expires_at: "2026-03-20T00:00:00Z" });
      await store.storeAuditEntry({ ...base, sequence_number: 3, expires_at: null });
      const deleted = await store.deleteExpiredAuditEntries("2026-03-16T12:00:00Z");
      expect(deleted).toBe(1);
      const remaining = await store.queryAuditEntries();
      expect(remaining).toHaveLength(2);
    });
  });

  describe("checkpoints", () => {
    it("stores and retrieves checkpoints", async () => {
      const body = {
        checkpoint_id: "ckpt-1",
        range: { first_sequence: 1, last_sequence: 10 },
        merkle_root: "sha256:abc",
        previous_checkpoint: null,
        timestamp: "2026-01-01T00:00:00Z",
        entry_count: 10,
      };
      await store.storeCheckpoint(body, "sig-1");

      const checkpoints = await store.getCheckpoints();
      expect(checkpoints).toHaveLength(1);
      expect(checkpoints[0].checkpoint_id).toBe("ckpt-1");
      expect(checkpoints[0].signature).toBe("sig-1");

      const byId = await store.getCheckpointById("ckpt-1");
      expect(byId).not.toBeNull();
      expect(byId!.merkle_root).toBe("sha256:abc");
    });
  });

  describe("lifecycle", () => {
    it("throws if used before initialize", async () => {
      const uninit = new PostgresStorage(POSTGRES_DSN!);
      await expect(uninit.loadToken("x")).rejects.toThrow(/not initialized/);
    });

    it("clearAll resets append head", async () => {
      await store.appendAuditEntry({
        capability: "test",
        success: true,
        timestamp: "2026-01-01T00:00:00Z",
      });
      await store.clearAll();
      const entry = await store.appendAuditEntry({
        capability: "test2",
        success: true,
        timestamp: "2026-01-01T00:00:01Z",
      });
      expect(entry.sequence_number).toBe(1);
      expect(entry.previous_hash).toBe("sha256:0");
    });
  });
});
