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
import { CheckpointPolicy, CheckpointScheduler } from "@anip/server";
import { app } from "../src/server";

// Use an in-memory database for test isolation
beforeAll(() => {
  process.env.ANIP_DB_PATH = ":memory:";
});

// For tests, create a mock async sign function that returns a valid detached JWS format
const mockSign = async (payload: Buffer): Promise<string> => {
  // Return a fake detached JWS: header..signature
  const header = Buffer.from('{"alg":"ES256"}').toString("base64url");
  const sig = Buffer.from("fakesig").toString("base64url");
  return `${header}..${sig}`;
};

async function addAuditEntry() {
  await logAuditEntry({
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
  it("creates checkpoint with body and detached signature", async () => {
    await addAuditEntry();
    await addAuditEntry();
    const snap = getMerkleSnapshot();
    const [body, sig] = await createCheckpoint(mockSign);
    expect(body.merkle_root).toBe(snap.root);
    expect(body.range.last_sequence).toBe(snap.leaf_count);
    expect(body).not.toHaveProperty("signature");
    expect(sig.split(".")).toHaveLength(3);
    expect(sig.split(".")[1]).toBe("");
  });

  it("stores checkpoint in database", async () => {
    await addAuditEntry();
    await createCheckpoint(mockSign);
    const checkpoints = getCheckpoints();
    expect(checkpoints.length).toBeGreaterThanOrEqual(1);
  });

  it("chains checkpoints", async () => {
    await addAuditEntry();
    await createCheckpoint(mockSign);
    await addAuditEntry();
    await createCheckpoint(mockSign);
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
  it("triggers checkpoint after N entries", async () => {
    // Configure policy and sign function
    setCheckpointPolicy(new CheckpointPolicy({ entryCount: 3 }));
    setCheckpointSignFn(mockSign);

    const initialCheckpoints = getCheckpoints().length;

    for (let i = 0; i < 3; i++) {
      await addAuditEntry();
    }

    // Auto-checkpoint is fire-and-forget async — wait for it to complete
    await new Promise((r) => setTimeout(r, 50));

    const checkpoints = getCheckpoints();
    expect(checkpoints.length).toBeGreaterThan(initialCheckpoints);
  });

  it("does not trigger before threshold", async () => {
    setCheckpointPolicy(new CheckpointPolicy({ entryCount: 10 }));
    setCheckpointSignFn(mockSign);

    const initialCheckpoints = getCheckpoints().length;

    // Add fewer entries than the threshold
    for (let i = 0; i < 2; i++) {
      await addAuditEntry();
    }

    expect(getCheckpoints().length).toBe(initialCheckpoints);
  });

  it("hasNewEntriesSinceCheckpoint tracks state", async () => {
    // After a checkpoint, adding an entry should flip the flag
    await createCheckpoint(mockSign);
    expect(hasNewEntriesSinceCheckpoint()).toBe(false);

    await addAuditEntry();
    expect(hasNewEntriesSinceCheckpoint()).toBe(true);
  });

  it("scheduler fires on interval", async () => {
    setCheckpointSignFn(mockSign);

    // Add an entry so there's something to checkpoint
    await addAuditEntry();
    const initial = getCheckpoints().length;

    const scheduler = new CheckpointScheduler(
      0.3, // 300ms interval
      () => { createCheckpoint(mockSign).catch(() => {}); },
      hasNewEntriesSinceCheckpoint,
    );
    scheduler.start();
    await new Promise((r) => setTimeout(r, 500));
    scheduler.stop();

    expect(getCheckpoints().length).toBeGreaterThan(initial);
  });
});

describe("Checkpoint endpoints", () => {
  it("GET /anip/checkpoints returns list", async () => {
    await addAuditEntry();
    await createCheckpoint(mockSign);
    const res = await app.request("/anip/checkpoints");
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.checkpoints.length).toBeGreaterThanOrEqual(1);
    expect(data.checkpoints[0]).toHaveProperty("merkle_root");
    expect(data.checkpoints[0]).toHaveProperty("range");
    expect(data.checkpoints[0]).toHaveProperty("signature");
  });

  it("GET /anip/checkpoints?limit=1 respects limit", async () => {
    const res = await app.request("/anip/checkpoints?limit=1");
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.checkpoints.length).toBeLessThanOrEqual(1);
  });

  it("GET /anip/checkpoints/:id with inclusion proof", async () => {
    for (let i = 0; i < 3; i++) await addAuditEntry();
    await createCheckpoint(mockSign);
    const checkpoints = getCheckpoints();
    const id = checkpoints[checkpoints.length - 1].checkpoint_id;
    const res = await app.request(
      `/anip/checkpoints/${id}?include_proof=true&leaf_index=0`
    );
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data).toHaveProperty("checkpoint");
    expect(data).toHaveProperty("inclusion_proof");
    expect(data.inclusion_proof).toHaveProperty("path");
    expect(data.inclusion_proof).toHaveProperty("merkle_root");
    expect(data.inclusion_proof).toHaveProperty("leaf_count");
  });

  it("GET /anip/checkpoints/:id with consistency proof", async () => {
    for (let i = 0; i < 3; i++) await addAuditEntry();
    await createCheckpoint(mockSign);
    for (let i = 0; i < 3; i++) await addAuditEntry();
    await createCheckpoint(mockSign);
    const checkpoints = getCheckpoints();
    const oldId = checkpoints[checkpoints.length - 2].checkpoint_id;
    const newId = checkpoints[checkpoints.length - 1].checkpoint_id;
    const res = await app.request(
      `/anip/checkpoints/${newId}?consistency_from=${oldId}`
    );
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data).toHaveProperty("consistency_proof");
    expect(data.consistency_proof).toHaveProperty("old_size");
    expect(data.consistency_proof).toHaveProperty("new_size");
    expect(data.consistency_proof).toHaveProperty("path");
  });

  it("GET /anip/checkpoints/:id returns 404 for unknown", async () => {
    const res = await app.request("/anip/checkpoints/ckpt-nonexistent");
    expect(res.status).toBe(404);
  });
});
