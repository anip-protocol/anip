import { describe, it, expect, beforeEach, afterEach, afterAll } from "vitest";
import { InMemoryStorage, SQLiteStorage } from "../src/storage.js";
import { unlinkSync } from "fs";
import { randomUUID } from "crypto";
import { ALL_COMPLIANCE_TESTS } from "./compliance.js";

const TEST_DB = `/tmp/anip-test-${randomUUID()}.db`;

describe("SQLiteStorage", () => {
  let storage: SQLiteStorage;

  beforeEach(() => {
    storage = new SQLiteStorage(TEST_DB);
  });

  afterEach(async () => {
    await storage.terminate();
    try {
      unlinkSync(TEST_DB);
      unlinkSync(TEST_DB + "-wal");
      unlinkSync(TEST_DB + "-shm");
    } catch {
      // Files may not exist
    }
  });

  it("stores and loads a delegation token", async () => {
    const token = {
      token_id: "tok-1",
      issuer: "svc",
      subject: "agent",
      scope: ["travel.search"],
      purpose: { capability: "search", parameters: {} },
      parent: null,
      expires: "2026-12-31T23:59:59Z",
      constraints: { max_delegation_depth: 3 },
      root_principal: "human:alice",
    };
    await storage.storeToken(token);
    const loaded = await storage.loadToken("tok-1");
    expect(loaded).not.toBeNull();
    expect(loaded!.token_id).toBe("tok-1");
    expect(loaded!.scope).toEqual(["travel.search"]);
    expect(loaded!.constraints).toEqual({ max_delegation_depth: 3 });
  });

  it("returns null for nonexistent token", async () => {
    expect(await storage.loadToken("nonexistent")).toBeNull();
  });

  it("stores and queries audit entries", async () => {
    const entry = {
      sequence_number: 1,
      timestamp: "2026-01-01T00:00:00Z",
      capability: "search_flights",
      token_id: "tok-1",
      issuer: "svc",
      subject: "agent",
      root_principal: "human:alice",
      parameters: { origin: "SFO" },
      success: true,
      result_summary: { count: 5 },
      failure_type: null,
      cost_actual: null,
      delegation_chain: ["tok-1"],
      previous_hash: "sha256:0",
      signature: null,
    };
    await storage.storeAuditEntry(entry);

    const results = await storage.queryAuditEntries({ capability: "search_flights" });
    expect(results).toHaveLength(1);
    expect(results[0].capability).toBe("search_flights");
    expect(results[0].success).toBe(true);
    expect(results[0].parameters).toEqual({ origin: "SFO" });
    expect(results[0].delegation_chain).toEqual(["tok-1"]);
  });

  it("getLastAuditEntry returns latest by sequence number", async () => {
    await storage.storeAuditEntry({
      sequence_number: 1, timestamp: "2026-01-01T00:00:00Z",
      capability: "a", previous_hash: "sha256:0", success: true,
    });
    await storage.storeAuditEntry({
      sequence_number: 2, timestamp: "2026-01-01T00:01:00Z",
      capability: "b", previous_hash: "sha256:1", success: false,
    });
    const last = await storage.getLastAuditEntry();
    expect(last!.sequence_number).toBe(2);
    expect(last!.capability).toBe("b");
    expect(last!.success).toBe(false);
  });

  it("stores and retrieves checkpoints", async () => {
    const body = {
      checkpoint_id: "ckpt-1",
      range: { first_sequence: 1, last_sequence: 10 },
      merkle_root: "sha256:abc",
      previous_checkpoint: null,
      timestamp: "2026-01-01T00:00:00Z",
      entry_count: 10,
    };
    await storage.storeCheckpoint(body, "sig-1");

    const checkpoints = await storage.getCheckpoints();
    expect(checkpoints).toHaveLength(1);
    expect(checkpoints[0].checkpoint_id).toBe("ckpt-1");
    expect(checkpoints[0].signature).toBe("sig-1");

    const byId = await storage.getCheckpointById("ckpt-1");
    expect(byId).not.toBeNull();
    expect(byId!.merkle_root).toBe("sha256:abc");
  });
});

// ---------------------------------------------------------------------------
// v0.8: event_class, retention_tier, expires_at tests — SQLiteStorage
// ---------------------------------------------------------------------------

describe("SQLiteStorage v0.8 audit fields", () => {
  let storage: SQLiteStorage;

  beforeEach(() => {
    storage = new SQLiteStorage(TEST_DB);
  });

  afterEach(async () => {
    await storage.terminate();
    try {
      unlinkSync(TEST_DB);
      unlinkSync(TEST_DB + "-wal");
      unlinkSync(TEST_DB + "-shm");
    } catch {
      // Files may not exist
    }
  });

  it("stores and queries audit entry with event_class, retention_tier, expires_at", async () => {
    const entry = {
      sequence_number: 1, timestamp: "2026-03-16T12:00:00Z",
      capability: "test.cap", token_id: "t1", issuer: "svc",
      subject: "agent", root_principal: "human", parameters: null,
      success: true, result_summary: null, failure_type: null,
      cost_actual: null, delegation_chain: null, invocation_id: "inv-1",
      client_reference_id: null, stream_summary: null,
      previous_hash: "sha256:0000", signature: null,
      event_class: "high_risk_success", retention_tier: "long",
      expires_at: "2027-03-16T12:00:00Z",
    };
    await storage.storeAuditEntry(entry);
    const rows = await storage.queryAuditEntries({ capability: "test.cap" });
    expect(rows).toHaveLength(1);
    expect(rows[0].event_class).toBe("high_risk_success");
    expect(rows[0].retention_tier).toBe("long");
    expect(rows[0].expires_at).toBe("2027-03-16T12:00:00Z");
  });

  it("queries audit entries by event_class", async () => {
    const base = {
      timestamp: "2026-03-16T12:00:00Z", capability: "test.cap",
      token_id: "t1", issuer: "svc", subject: "agent",
      root_principal: "human", parameters: null, success: true,
      result_summary: null, failure_type: null, cost_actual: null,
      delegation_chain: null, invocation_id: null,
      client_reference_id: null, stream_summary: null,
      previous_hash: "sha256:0000", signature: null,
      retention_tier: "short", expires_at: "2026-03-23T12:00:00Z",
    };
    await storage.storeAuditEntry({ ...base, sequence_number: 1, event_class: "high_risk_success" });
    await storage.storeAuditEntry({ ...base, sequence_number: 2, event_class: "malformed_or_spam" });
    await storage.storeAuditEntry({ ...base, sequence_number: 3, event_class: "high_risk_success" });
    const rows = await storage.queryAuditEntries({ eventClass: "high_risk_success" });
    expect(rows).toHaveLength(2);
    expect(rows.every((r) => r.event_class === "high_risk_success")).toBe(true);
  });

  it("deletes expired audit entries", async () => {
    const base = {
      timestamp: "2026-03-16T12:00:00Z", capability: "test.cap",
      token_id: "t1", issuer: "svc", subject: "agent",
      root_principal: "human", parameters: null, success: true,
      result_summary: null, failure_type: null, cost_actual: null,
      delegation_chain: null, invocation_id: null,
      client_reference_id: null, stream_summary: null,
      previous_hash: "sha256:0000", signature: null,
      event_class: "malformed_or_spam", retention_tier: "short",
    };
    await storage.storeAuditEntry({ ...base, sequence_number: 1, expires_at: "2026-03-10T00:00:00Z" });
    await storage.storeAuditEntry({ ...base, sequence_number: 2, expires_at: "2026-03-20T00:00:00Z" });
    await storage.storeAuditEntry({ ...base, sequence_number: 3, expires_at: null });
    const deleted = await storage.deleteExpiredAuditEntries("2026-03-16T12:00:00Z");
    expect(deleted).toBe(1);
    const remaining = await storage.queryAuditEntries();
    expect(remaining).toHaveLength(2);
  });
});

// ---------------------------------------------------------------------------
// v0.8: event_class, retention_tier, expires_at tests — InMemoryStorage
// ---------------------------------------------------------------------------

describe("InMemoryStorage v0.8 audit fields", () => {
  it("stores and queries audit entry with event_class, retention_tier, expires_at", async () => {
    const storage = new InMemoryStorage();
    const entry = {
      sequence_number: 1, timestamp: "2026-03-16T12:00:00Z",
      capability: "test.cap", token_id: "t1", issuer: "svc",
      subject: "agent", root_principal: "human", parameters: null,
      success: true, result_summary: null, failure_type: null,
      cost_actual: null, delegation_chain: null, invocation_id: "inv-1",
      client_reference_id: null, stream_summary: null,
      previous_hash: "sha256:0000", signature: null,
      event_class: "high_risk_success", retention_tier: "long",
      expires_at: "2027-03-16T12:00:00Z",
    };
    await storage.storeAuditEntry(entry);
    const rows = await storage.queryAuditEntries({ capability: "test.cap" });
    expect(rows).toHaveLength(1);
    expect(rows[0].event_class).toBe("high_risk_success");
    expect(rows[0].retention_tier).toBe("long");
    expect(rows[0].expires_at).toBe("2027-03-16T12:00:00Z");
  });

  it("queries audit entries by event_class", async () => {
    const storage = new InMemoryStorage();
    const base = {
      timestamp: "2026-03-16T12:00:00Z", capability: "test.cap",
      token_id: "t1", issuer: "svc", subject: "agent",
      root_principal: "human", parameters: null, success: true,
      result_summary: null, failure_type: null, cost_actual: null,
      delegation_chain: null, invocation_id: null,
      client_reference_id: null, stream_summary: null,
      previous_hash: "sha256:0000", signature: null,
      retention_tier: "short", expires_at: "2026-03-23T12:00:00Z",
    };
    await storage.storeAuditEntry({ ...base, sequence_number: 1, event_class: "high_risk_success" });
    await storage.storeAuditEntry({ ...base, sequence_number: 2, event_class: "malformed_or_spam" });
    await storage.storeAuditEntry({ ...base, sequence_number: 3, event_class: "high_risk_success" });
    const rows = await storage.queryAuditEntries({ eventClass: "high_risk_success" });
    expect(rows).toHaveLength(2);
    expect(rows.every((r) => r.event_class === "high_risk_success")).toBe(true);
  });

  it("deletes expired audit entries", async () => {
    const storage = new InMemoryStorage();
    const base = {
      timestamp: "2026-03-16T12:00:00Z", capability: "test.cap",
      token_id: "t1", issuer: "svc", subject: "agent",
      root_principal: "human", parameters: null, success: true,
      result_summary: null, failure_type: null, cost_actual: null,
      delegation_chain: null, invocation_id: null,
      client_reference_id: null, stream_summary: null,
      previous_hash: "sha256:0000", signature: null,
      event_class: "malformed_or_spam", retention_tier: "short",
    };
    await storage.storeAuditEntry({ ...base, sequence_number: 1, expires_at: "2026-03-10T00:00:00Z" });
    await storage.storeAuditEntry({ ...base, sequence_number: 2, expires_at: "2026-03-20T00:00:00Z" });
    await storage.storeAuditEntry({ ...base, sequence_number: 3, expires_at: null });
    const deleted = await storage.deleteExpiredAuditEntries("2026-03-16T12:00:00Z");
    expect(deleted).toBe(1);
    const remaining = await storage.queryAuditEntries();
    expect(remaining).toHaveLength(2);
  });
});

// ---------------------------------------------------------------------------
// Backend compliance suite — InMemoryStorage
// ---------------------------------------------------------------------------

describe("InMemoryStorage compliance", () => {
  for (const test of ALL_COMPLIANCE_TESTS) {
    it(test.name, async () => {
      const storage = new InMemoryStorage();
      await test.fn(storage);
    });
  }
});

// ---------------------------------------------------------------------------
// Backend compliance suite — SQLiteStorage
//
// A single SQLiteStorage instance is shared across all compliance tests to
// avoid repeated worker-thread create/terminate cycles.  The database is
// cleared between tests via clearAll() so each test starts with a clean
// slate.  This sidesteps a native-module flakiness issue with
// better-sqlite3 + worker_threads on Node 25 inside vitest forks.
// ---------------------------------------------------------------------------

describe("SQLiteStorage compliance", () => {
  const dbPath = `/tmp/anip-compliance-${randomUUID()}.db`;
  const storage = new SQLiteStorage(dbPath);

  afterEach(async () => {
    await storage.clearAll();
  });

  afterAll(async () => {
    await storage.terminate();
    try {
      unlinkSync(dbPath);
      unlinkSync(dbPath + "-wal");
      unlinkSync(dbPath + "-shm");
    } catch {
      // Files may not exist
    }
  });

  for (const test of ALL_COMPLIANCE_TESTS) {
    it(test.name, async () => {
      await test.fn(storage);
    });
  }
});
