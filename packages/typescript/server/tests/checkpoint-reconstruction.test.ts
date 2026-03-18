import { describe, it, expect } from "vitest";
import { InMemoryStorage } from "../src/storage.js";
import { reconstructAndCreateCheckpoint } from "../src/checkpoint.js";

describe("reconstructAndCreateCheckpoint", () => {
  it("creates correct merkle root from entries", async () => {
    const store = new InMemoryStorage();
    await store.appendAuditEntry({ capability: "a", success: true, timestamp: "2026-01-01T00:00:00Z" });
    await store.appendAuditEntry({ capability: "b", success: true, timestamp: "2026-01-01T00:00:01Z" });

    const result = await reconstructAndCreateCheckpoint({ storage: store, serviceId: "test-svc" });
    expect(result).not.toBeNull();
    expect(result!.body.merkle_root).toMatch(/^sha256:/);
    expect(result!.body.entry_count).toBe(2);
  });

  it("returns null if no entries", async () => {
    const store = new InMemoryStorage();
    const result = await reconstructAndCreateCheckpoint({ storage: store, serviceId: "test-svc" });
    expect(result).toBeNull();
  });

  it("returns null if no new entries since last checkpoint", async () => {
    const store = new InMemoryStorage();
    await store.appendAuditEntry({ capability: "a", success: true, timestamp: "2026-01-01T00:00:00Z" });

    const result = await reconstructAndCreateCheckpoint({ storage: store, serviceId: "test-svc" });
    expect(result).not.toBeNull();
    await store.storeCheckpoint(result!.body, result!.signature);

    const result2 = await reconstructAndCreateCheckpoint({ storage: store, serviceId: "test-svc" });
    expect(result2).toBeNull();
  });

  it("cumulative root covers all entries", async () => {
    const store = new InMemoryStorage();
    await store.appendAuditEntry({ capability: "a", success: true, timestamp: "2026-01-01T00:00:00Z" });
    const r1 = await reconstructAndCreateCheckpoint({ storage: store, serviceId: "test-svc" });
    await store.storeCheckpoint(r1!.body, r1!.signature);

    await store.appendAuditEntry({ capability: "b", success: true, timestamp: "2026-01-01T00:00:01Z" });
    const r2 = await reconstructAndCreateCheckpoint({ storage: store, serviceId: "test-svc" });

    expect(r2!.body.entry_count).toBe(2);
    expect(r2!.body.merkle_root).not.toBe(r1!.body.merkle_root);
  });
});
