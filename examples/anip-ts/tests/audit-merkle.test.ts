import { describe, it, expect, beforeAll } from "vitest";
import { logAuditEntry, getMerkleSnapshot, getMerkleInclusionProof } from "../src/data/database";

// Use an in-memory database for test isolation
beforeAll(() => {
  process.env.ANIP_DB_PATH = ":memory:";
});

describe("Merkle integration with audit log", () => {
  it("merkle root advances with entries", () => {
    const snap1 = getMerkleSnapshot();
    logAuditEntry({
      capability: "test_merkle",
      timestamp: new Date().toISOString(),
      token_id: "test-merkle-1",
      root_principal: "human:test@example.com",
      success: true,
      result_summary: null,
      failure_type: null,
      cost_actual: null,
      cost_variance: null,
      delegation_chain: [],
    });
    const snap2 = getMerkleSnapshot();
    expect(snap2.leaf_count).toBe(snap1.leaf_count + 1);
    expect(snap2.root).not.toBe(snap1.root);
  });

  it("inclusion proof works for audit entry", () => {
    logAuditEntry({
      capability: "test_merkle_proof",
      timestamp: new Date().toISOString(),
      token_id: "test-merkle-2",
      root_principal: "human:test@example.com",
      success: true,
      result_summary: null,
      failure_type: null,
      cost_actual: null,
      cost_variance: null,
      delegation_chain: [],
    });
    const snap = getMerkleSnapshot();
    const proof = getMerkleInclusionProof(snap.leaf_count - 1);
    expect(proof).not.toBeNull();
    expect(proof!.path.length).toBeGreaterThanOrEqual(0);
  });
});
