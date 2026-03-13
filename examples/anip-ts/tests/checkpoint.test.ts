import { describe, it, expect, beforeAll } from "vitest";
import { createCheckpoint, getCheckpoints, getMerkleSnapshot, logAuditEntry } from "../src/data/database";
import { CheckpointPolicy } from "../src/checkpoint";

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
