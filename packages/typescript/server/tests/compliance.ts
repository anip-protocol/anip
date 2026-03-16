/**
 * Backend compliance test suite for StorageBackend implementations.
 *
 * Each fixture is an async function that accepts a {@link StorageBackend} and
 * exercises one aspect of the contract.  The {@link ALL_COMPLIANCE_TESTS}
 * array collects them so that test runners can iterate over them for every
 * backend variant (InMemoryStorage, SQLiteStorage, etc.).
 */

import { expect } from "vitest";
import type { StorageBackend } from "../src/storage.js";

// ---------------------------------------------------------------------------
// Token fixtures
// ---------------------------------------------------------------------------

export async function complianceTokenRoundtrip(storage: StorageBackend): Promise<void> {
  const token = {
    token_id: "tok-c1",
    issuer: "svc",
    subject: "agent",
    scope: ["a.b"],
    purpose: { capability: "c", parameters: {}, task_id: "t" },
    parent: null,
    expires: "2099-01-01T00:00:00Z",
    constraints: { max_delegation_depth: 3, concurrent_branches: "allowed" },
    root_principal: "human:alice",
  };
  await storage.storeToken(token);
  const loaded = await storage.loadToken("tok-c1");
  expect(loaded).not.toBeNull();
  expect(loaded!.token_id).toBe("tok-c1");
  expect(loaded!.scope).toEqual(["a.b"]);
}

export async function complianceTokenNotFound(storage: StorageBackend): Promise<void> {
  expect(await storage.loadToken("nonexistent")).toBeNull();
}

// ---------------------------------------------------------------------------
// Audit fixtures
// ---------------------------------------------------------------------------

export async function complianceAuditRoundtrip(storage: StorageBackend): Promise<void> {
  const entry = {
    sequence_number: 1,
    timestamp: "2026-01-01T00:00:00Z",
    capability: "search",
    token_id: "tok-1",
    root_principal: "human:alice",
    success: true,
    invocation_id: "inv-aabbccddeeff",
    client_reference_id: "ref-1",
    previous_hash: "sha256:0",
    signature: null,
  };
  await storage.storeAuditEntry(entry);
  const results = await storage.queryAuditEntries({ capability: "search" });
  expect(results.length).toBeGreaterThanOrEqual(1);
  expect(results[0].capability).toBe("search");
}

export async function complianceAuditLineageFilters(storage: StorageBackend): Promise<void> {
  for (let i = 0; i < 3; i++) {
    await storage.storeAuditEntry({
      sequence_number: i + 1,
      timestamp: `2026-01-0${i + 1}T00:00:00Z`,
      capability: "cap",
      root_principal: "human:a",
      success: true,
      invocation_id: `inv-${"0".repeat(11)}${i}`,
      client_reference_id: "ref-shared",
      previous_hash: "sha256:0",
      signature: null,
    });
  }
  const byInv = await storage.queryAuditEntries({ invocationId: "inv-000000000001" });
  expect(byInv).toHaveLength(1);
  const byRef = await storage.queryAuditEntries({ clientReferenceId: "ref-shared" });
  expect(byRef).toHaveLength(3);
}

export async function complianceAuditOrdering(storage: StorageBackend): Promise<void> {
  for (let i = 0; i < 5; i++) {
    await storage.storeAuditEntry({
      sequence_number: i + 1,
      timestamp: `2026-01-0${i + 1}T00:00:00Z`,
      capability: "cap",
      root_principal: "human:a",
      success: true,
      previous_hash: "sha256:0",
      signature: null,
    });
  }
  const entries = await storage.queryAuditEntries({ rootPrincipal: "human:a", limit: 10 });
  const seqNums = entries.map((e) => e.sequence_number as number);
  // Descending order (most recent first)
  expect(seqNums).toEqual([...seqNums].sort((a, b) => b - a));
}

export async function complianceAuditConcurrentOrdering(storage: StorageBackend): Promise<void> {
  const insert = async (seq: number) => {
    await storage.storeAuditEntry({
      sequence_number: seq,
      timestamp: "2026-01-01T00:00:00Z",
      capability: "cap",
      root_principal: "human:a",
      success: true,
      previous_hash: "sha256:0",
      signature: null,
    });
  };

  await Promise.all(Array.from({ length: 20 }, (_, i) => insert(i + 1)));
  const entries = await storage.queryAuditEntries({ rootPrincipal: "human:a", limit: 100 });
  expect(entries).toHaveLength(20);
  const seqNums = entries.map((e) => e.sequence_number as number);
  expect(seqNums).toEqual([...seqNums].sort((a, b) => b - a));
  const last = await storage.getLastAuditEntry();
  expect(last).not.toBeNull();
  expect(last!.sequence_number).toBe(20);
}

// ---------------------------------------------------------------------------
// Checkpoint fixtures
// ---------------------------------------------------------------------------

export async function complianceCheckpointRoundtrip(storage: StorageBackend): Promise<void> {
  const body = {
    checkpoint_id: "cp-1",
    merkle_root: "sha256:abc",
    range: { first_sequence: 1, last_sequence: 5 },
    timestamp: "2026-01-01T00:00:00Z",
    entry_count: 5,
  };
  await storage.storeCheckpoint(body, "sig-123");
  const loaded = await storage.getCheckpointById("cp-1");
  expect(loaded).not.toBeNull();
  expect(loaded!.checkpoint_id).toBe("cp-1");
  expect(loaded!.merkle_root).toBe("sha256:abc");
}

export async function complianceCheckpointNotFound(storage: StorageBackend): Promise<void> {
  expect(await storage.getCheckpointById("nonexistent")).toBeNull();
}

export async function complianceCheckpointListing(storage: StorageBackend): Promise<void> {
  for (let i = 0; i < 5; i++) {
    await storage.storeCheckpoint(
      { checkpoint_id: `cp-${i}`, merkle_root: `sha256:${i}`, sequence_number: i + 1 },
      `sig-${i}`,
    );
  }
  const results = await storage.getCheckpoints(3);
  expect(results).toHaveLength(3);
}

// ---------------------------------------------------------------------------
// Audit range fixture
// ---------------------------------------------------------------------------

export async function complianceAuditEntriesRange(storage: StorageBackend): Promise<void> {
  for (let i = 0; i < 10; i++) {
    await storage.storeAuditEntry({
      sequence_number: i + 1,
      timestamp: `2026-01-${String(i + 1).padStart(2, "0")}T00:00:00Z`,
      capability: "cap",
      root_principal: "human:a",
      success: true,
      previous_hash: "sha256:0",
      signature: null,
    });
  }
  const entries = await storage.getAuditEntriesRange(3, 7);
  const seqNums = entries.map((e) => e.sequence_number as number);
  expect(seqNums.every((s) => s >= 3 && s <= 7)).toBe(true);
}

// ---------------------------------------------------------------------------
// Collected list
// ---------------------------------------------------------------------------

export const ALL_COMPLIANCE_TESTS = [
  { name: "token roundtrip", fn: complianceTokenRoundtrip },
  { name: "token not found", fn: complianceTokenNotFound },
  { name: "audit roundtrip", fn: complianceAuditRoundtrip },
  { name: "audit lineage filters", fn: complianceAuditLineageFilters },
  { name: "audit ordering", fn: complianceAuditOrdering },
  { name: "audit concurrent ordering", fn: complianceAuditConcurrentOrdering },
  { name: "checkpoint roundtrip", fn: complianceCheckpointRoundtrip },
  { name: "checkpoint not found", fn: complianceCheckpointNotFound },
  { name: "checkpoint listing", fn: complianceCheckpointListing },
  { name: "audit entries range", fn: complianceAuditEntriesRange },
];
