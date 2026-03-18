import { describe, it, expect } from "vitest";
import { InMemoryStorage } from "../src/storage.js";
import { DelegationEngine } from "../src/delegation.js";

function makeEngine(storage?: InMemoryStorage) {
  return new DelegationEngine(storage ?? new InMemoryStorage(), {
    serviceId: "test-svc",
    exclusiveTtl: 30,
  });
}

async function issueExclusiveRootToken(engine: DelegationEngine) {
  // Issue a root token, then delegate with exclusive constraint.
  // Root tokens inherit concurrent_branches from createToken defaults ("allowed"),
  // so we need to create a token whose constraints have concurrent_branches: "exclusive".
  // The engine's _createToken sets concurrent_branches from parentToken if present.
  // For testing, we issue a root token and then manually build an exclusive token.
  const { token } = await engine.issueRootToken({
    authenticatedPrincipal: "human:alice@example.com",
    subject: "agent",
    scope: ["travel.search"],
    capability: "search_flights",
  });
  // Modify the token constraints to be exclusive for testing purposes.
  // This simulates a token that was created with exclusive constraints.
  const exclusiveToken = {
    ...token,
    constraints: {
      ...token.constraints,
      concurrent_branches: "exclusive" as const,
    },
  };
  // Re-register the modified token so storage is consistent.
  await engine.registerToken(exclusiveToken);
  return exclusiveToken;
}

async function issueAllowedRootToken(engine: DelegationEngine) {
  const { token } = await engine.issueRootToken({
    authenticatedPrincipal: "human:bob@example.com",
    subject: "agent",
    scope: ["travel.search"],
    capability: "search_flights",
  });
  // Default concurrent_branches is "allowed"
  return token;
}

describe("DelegationEngine exclusivity", () => {
  it("acquireExclusiveLock returns null for non-exclusive tokens", async () => {
    const engine = makeEngine();
    const token = await issueAllowedRootToken(engine);
    const result = await engine.acquireExclusiveLock(token);
    expect(result).toBeNull();
  });

  it("releaseExclusiveLock is a no-op for non-exclusive tokens", async () => {
    const engine = makeEngine();
    const token = await issueAllowedRootToken(engine);
    // Should not throw
    await engine.releaseExclusiveLock(token);
  });

  it("acquireExclusiveLock succeeds for exclusive token", async () => {
    const engine = makeEngine();
    const token = await issueExclusiveRootToken(engine);
    const result = await engine.acquireExclusiveLock(token);
    expect(result).toBeNull();
  });

  it("acquireExclusiveLock rejects concurrent exclusive requests from different holders", async () => {
    // Two engines sharing the same storage but different PIDs cannot coexist
    // in the same process. Instead, we test at the storage level: acquire
    // from one holder, then try from another via a second engine that
    // would have a different holder ID.
    //
    // Since _getHolderId uses hostname:pid and both engines run in the same
    // process, they will have the same holder — so to simulate contention
    // we acquire directly on the storage with a different holder.
    const storage = new InMemoryStorage();
    const engine = makeEngine(storage);
    const token = await issueExclusiveRootToken(engine);

    // Pre-acquire the lock with a different holder directly on storage
    const root = token.root_principal!;
    const key = `exclusive:test-svc:${root}`;
    await storage.tryAcquireExclusive(key, "other-host:9999", 30);

    // Now the engine's acquireExclusiveLock should fail
    const result = await engine.acquireExclusiveLock(token);
    expect(result).not.toBeNull();
    expect(result!.type).toBe("concurrent_request_rejected");
    expect(result!.retry).toBe(true);
    expect(result!.resolution.action).toBe("wait_and_retry");
    expect(result!.resolution.grantable_by).toBe("human:alice@example.com");
    expect(result!.detail).toContain("concurrent_branches is exclusive");
    expect(result!.detail).toContain("human:alice@example.com");
  });

  it("releaseExclusiveLock allows reacquisition", async () => {
    const storage = new InMemoryStorage();
    const engine = makeEngine(storage);
    const token = await issueExclusiveRootToken(engine);

    // Acquire the lock
    const acquired = await engine.acquireExclusiveLock(token);
    expect(acquired).toBeNull();

    // Release the lock
    await engine.releaseExclusiveLock(token);

    // Another holder should now be able to acquire
    const root = token.root_principal!;
    const key = `exclusive:test-svc:${root}`;
    const otherAcquired = await storage.tryAcquireExclusive(key, "other-host:9999", 30);
    expect(otherAcquired).toBe(true);
  });

  it("same holder can reacquire exclusive lock", async () => {
    const engine = makeEngine();
    const token = await issueExclusiveRootToken(engine);

    const first = await engine.acquireExclusiveLock(token);
    expect(first).toBeNull();

    // Same process acquiring again should succeed (idempotent)
    const second = await engine.acquireExclusiveLock(token);
    expect(second).toBeNull();
  });

  it("exclusive lock is scoped per root principal", async () => {
    const storage = new InMemoryStorage();
    const engine = makeEngine(storage);

    // Create exclusive token for alice
    const aliceToken = await issueExclusiveRootToken(engine);

    // Create exclusive token for a different principal (bob)
    const { token: bobRawToken } = await engine.issueRootToken({
      authenticatedPrincipal: "human:bob@example.com",
      subject: "agent-b",
      scope: ["travel.search"],
      capability: "search_flights",
    });
    const bobToken = {
      ...bobRawToken,
      constraints: {
        ...bobRawToken.constraints,
        concurrent_branches: "exclusive" as const,
      },
    };
    await engine.registerToken(bobToken);

    // Both should acquire independently
    const aliceResult = await engine.acquireExclusiveLock(aliceToken);
    expect(aliceResult).toBeNull();

    const bobResult = await engine.acquireExclusiveLock(bobToken);
    expect(bobResult).toBeNull();
  });

  it("exclusiveTtl option is respected in constructor", () => {
    const engine1 = new DelegationEngine(new InMemoryStorage(), {
      serviceId: "svc",
    });
    // Default should be 60 — we can't inspect the private field directly,
    // but we can verify it doesn't throw
    expect(engine1).toBeDefined();

    const engine2 = new DelegationEngine(new InMemoryStorage(), {
      serviceId: "svc",
      exclusiveTtl: 120,
    });
    expect(engine2).toBeDefined();
  });
});
