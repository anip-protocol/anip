import { describe, it, expect, beforeAll } from "vitest";
import {
  createCheckpoint,
  getCheckpoints,
  getMerkleSnapshot,
  logAuditEntry,
  setCheckpointPolicy,
  setCheckpointSignFn,
  hasNewEntriesSinceCheckpoint,
} from "../src/data/database";
import { CheckpointPolicy, CheckpointScheduler } from "../src/checkpoint";

// Use an in-memory database for test isolation
beforeAll(() => {
  process.env.ANIP_DB_PATH = ":memory:";
});

// For tests, create a mock sign function that returns a valid detached JWS format
const mockSign = (payload: Buffer) => {
  // Return a fake detached JWS: header..signature
  const header = Buffer.from('{"alg":"ES256"}').toString("base64url");
  const sig = Buffer.from("fakesig").toString("base64url");
  return `${header}..${sig}`;
};

function addAuditEntry() {
  logAuditEntry({
    capability: "test_cap",
    timestamp: new Date().toISOString(),
    token_id: "test-1",
    root_principal: "human:test@example.com",
    success: true,
    result_summary: null,
    failure_type: null,
    cost_actual: null,
    cost_variance: null,
    delegation_chain: [],
  });
}

describe("Checkpoint", () => {
  it("creates checkpoint with body and detached signature", () => {
    addAuditEntry();
    addAuditEntry();
    const snap = getMerkleSnapshot();
    const [body, sig] = createCheckpoint(mockSign);
    expect(body.merkle_root).toBe(snap.root);
    expect(body.range.last_sequence).toBe(snap.leaf_count);
    expect(body).not.toHaveProperty("signature");
    expect(sig.split(".")).toHaveLength(3);
    expect(sig.split(".")[1]).toBe("");
  });

  it("stores checkpoint in database", () => {
    addAuditEntry();
    createCheckpoint(mockSign);
    const checkpoints = getCheckpoints();
    expect(checkpoints.length).toBeGreaterThanOrEqual(1);
  });

  it("chains checkpoints", () => {
    addAuditEntry();
    createCheckpoint(mockSign);
    addAuditEntry();
    createCheckpoint(mockSign);
    const checkpoints = getCheckpoints();
    expect(checkpoints[0].previous_checkpoint).toBeNull();
    expect(checkpoints[1].previous_checkpoint).not.toBeNull();
  });
});

describe("CheckpointPolicy", () => {
  it("triggers on entry count", () => {
    const policy = new CheckpointPolicy({ entryCount: 5 });
    expect(policy.shouldCheckpoint(4)).toBe(false);
    expect(policy.shouldCheckpoint(5)).toBe(true);
  });

  it("never triggers without policy", () => {
    const policy = new CheckpointPolicy({});
    expect(policy.shouldCheckpoint(1000)).toBe(false);
  });
});

describe("Auto-checkpointing", () => {
  it("triggers checkpoint after N entries", () => {
    // Configure policy and sign function
    setCheckpointPolicy(new CheckpointPolicy({ entryCount: 3 }));
    setCheckpointSignFn(mockSign);

    const initialCheckpoints = getCheckpoints().length;

    for (let i = 0; i < 3; i++) {
      addAuditEntry();
    }

    const checkpoints = getCheckpoints();
    expect(checkpoints.length).toBeGreaterThan(initialCheckpoints);
  });

  it("does not trigger before threshold", () => {
    setCheckpointPolicy(new CheckpointPolicy({ entryCount: 10 }));
    setCheckpointSignFn(mockSign);

    const initialCheckpoints = getCheckpoints().length;

    // Add fewer entries than the threshold
    for (let i = 0; i < 2; i++) {
      addAuditEntry();
    }

    expect(getCheckpoints().length).toBe(initialCheckpoints);
  });

  it("hasNewEntriesSinceCheckpoint tracks state", () => {
    // After a checkpoint, adding an entry should flip the flag
    createCheckpoint(mockSign);
    expect(hasNewEntriesSinceCheckpoint()).toBe(false);

    addAuditEntry();
    expect(hasNewEntriesSinceCheckpoint()).toBe(true);
  });

  it("scheduler fires on interval", async () => {
    setCheckpointSignFn(mockSign);

    // Add an entry so there's something to checkpoint
    addAuditEntry();
    const initial = getCheckpoints().length;

    const scheduler = new CheckpointScheduler(
      0.3, // 300ms interval
      () => createCheckpoint(mockSign),
      hasNewEntriesSinceCheckpoint,
    );
    scheduler.start();
    await new Promise((r) => setTimeout(r, 500));
    scheduler.stop();

    expect(getCheckpoints().length).toBeGreaterThan(initial);
  });
});
