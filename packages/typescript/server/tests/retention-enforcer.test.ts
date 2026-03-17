import { describe, it, expect, beforeEach } from "vitest";
import { InMemoryStorage } from "../src/storage.js";
import { RetentionEnforcer } from "../src/retention-enforcer.js";

describe("RetentionEnforcer", () => {
  let storage: InMemoryStorage;

  beforeEach(() => {
    storage = new InMemoryStorage();
  });

  it("deletes expired entries", async () => {
    const base = {
      timestamp: "2026-03-10T00:00:00Z",
      capability: "test",
      success: true,
      previous_hash: "sha256:0000",
      event_class: "malformed_or_spam",
      retention_tier: "short",
    };
    await storage.storeAuditEntry({ ...base, sequence_number: 1, expires_at: "2026-03-10T00:00:00Z" });
    await storage.storeAuditEntry({ ...base, sequence_number: 2, expires_at: "2027-03-16T00:00:00Z" });
    await storage.storeAuditEntry({ ...base, sequence_number: 3, expires_at: null });

    const enforcer = new RetentionEnforcer(storage, 1);
    const deleted = await enforcer.sweep();
    expect(deleted).toBe(1);
    const remaining = await storage.queryAuditEntries();
    expect(remaining.length).toBe(2);
  });

  it("start and stop lifecycle", () => {
    const enforcer = new RetentionEnforcer(storage, 60);
    enforcer.start();
    // @ts-expect-error accessing private for test
    expect(enforcer._timer).not.toBeNull();
    enforcer.stop();
    // @ts-expect-error accessing private for test
    expect(enforcer._timer).toBeNull();
  });

  it("start is idempotent", () => {
    const enforcer = new RetentionEnforcer(storage, 60);
    enforcer.start();
    // @ts-expect-error accessing private for test
    const timer1 = enforcer._timer;
    enforcer.start();
    // @ts-expect-error accessing private for test
    expect(enforcer._timer).toBe(timer1);
    enforcer.stop();
  });
});
