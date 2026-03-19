/**
 * Tests for v0.10 horizontal-scaling StorageBackend methods.
 */
import { describe, it, expect, beforeEach, afterEach, afterAll } from "vitest";
import { InMemoryStorage, SQLiteStorage } from "../src/storage.js";
import { unlinkSync } from "fs";
import { randomUUID } from "crypto";

// ---------------------------------------------------------------------------
// InMemoryStorage horizontal-scaling tests
// ---------------------------------------------------------------------------

describe("InMemoryStorage horizontal-scaling methods", () => {
  let store: InMemoryStorage;

  beforeEach(() => {
    store = new InMemoryStorage();
  });

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
});

// ---------------------------------------------------------------------------
// SQLiteStorage horizontal-scaling tests
// ---------------------------------------------------------------------------

describe("SQLiteStorage horizontal-scaling methods", () => {
  const dbPath = `/tmp/anip-hz-${randomUUID()}.db`;
  let store: SQLiteStorage;

  beforeEach(() => {
    store = new SQLiteStorage(dbPath);
  });

  afterEach(async () => {
    await store.terminate();
    try {
      unlinkSync(dbPath);
      unlinkSync(dbPath + "-wal");
      unlinkSync(dbPath + "-shm");
    } catch {
      // Files may not exist
    }
  });

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
});
