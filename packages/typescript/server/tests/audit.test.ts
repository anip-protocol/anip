import { describe, it, expect, beforeEach } from "vitest";
import { InMemoryStorage } from "../src/storage.js";
import { AuditLog } from "../src/audit.js";

describe("AuditLog lineage fields", () => {
  let storage: InMemoryStorage;
  let auditLog: AuditLog;

  beforeEach(() => {
    storage = new InMemoryStorage();
    auditLog = new AuditLog(storage);
  });

  it("entry includes lineage fields", async () => {
    const entry = await auditLog.logEntry({
      capability: "search_flights",
      token_id: "tok-1",
      root_principal: "human:alice",
      success: true,
      invocation_id: "inv-abc-123",
      client_reference_id: "ref-xyz-456",
    });

    expect(entry.invocation_id).toBe("inv-abc-123");
    expect(entry.client_reference_id).toBe("ref-xyz-456");
  });

  it("lineage fields default to null", async () => {
    const entry = await auditLog.logEntry({
      capability: "search_flights",
      token_id: "tok-1",
      root_principal: "human:alice",
      success: true,
    });

    expect(entry.invocation_id).toBeNull();
    expect(entry.client_reference_id).toBeNull();
  });

  it("lineage fields persisted and queryable", async () => {
    await auditLog.logEntry({
      capability: "search_flights",
      token_id: "tok-1",
      root_principal: "human:alice",
      success: true,
      invocation_id: "inv-persist-1",
      client_reference_id: "ref-persist-1",
    });

    const results = await auditLog.query({ capability: "search_flights" });
    expect(results).toHaveLength(1);
    expect(results[0].invocation_id).toBe("inv-persist-1");
    expect(results[0].client_reference_id).toBe("ref-persist-1");
  });

  it("query by invocation_id", async () => {
    await auditLog.logEntry({
      capability: "search_flights",
      token_id: "tok-1",
      root_principal: "human:alice",
      success: true,
      invocation_id: "inv-aaa",
    });

    await auditLog.logEntry({
      capability: "book_flight",
      token_id: "tok-2",
      root_principal: "human:bob",
      success: true,
      invocation_id: "inv-bbb",
    });

    const results = await auditLog.query({ invocationId: "inv-aaa" });
    expect(results).toHaveLength(1);
    expect(results[0].capability).toBe("search_flights");
    expect(results[0].invocation_id).toBe("inv-aaa");
  });

  it("query by client_reference_id", async () => {
    await auditLog.logEntry({
      capability: "search_flights",
      token_id: "tok-1",
      root_principal: "human:alice",
      success: true,
      client_reference_id: "ref-shared",
    });

    await auditLog.logEntry({
      capability: "book_flight",
      token_id: "tok-2",
      root_principal: "human:alice",
      success: true,
      client_reference_id: "ref-shared",
    });

    await auditLog.logEntry({
      capability: "cancel_flight",
      token_id: "tok-3",
      root_principal: "human:bob",
      success: false,
      client_reference_id: "ref-different",
    });

    const results = await auditLog.query({ clientReferenceId: "ref-shared" });
    expect(results).toHaveLength(2);
    expect(results.every((e) => e.client_reference_id === "ref-shared")).toBe(true);
  });
});
