import { describe, it, expect } from "vitest";
import { storageRedactEntry } from "../src/storage-redaction.js";

const LOW_VALUE_CLASSES = ["low_risk_success", "malformed_or_spam", "repeated_low_value_denial"];
const HIGH_VALUE_CLASSES = ["high_risk_success", "high_risk_denial"];

function makeEntry(eventClass: string): Record<string, unknown> {
  return {
    sequence_number: 1,
    timestamp: "2026-01-01T00:00:00Z",
    capability: "search_flights",
    token_id: "tok-1",
    root_principal: "user@example.com",
    parameters: { origin: "JFK", destination: "LAX" },
    success: eventClass.endsWith("success"),
    failure_type: eventClass.endsWith("success") ? null : "scope_insufficient",
    event_class: eventClass,
    retention_tier: "short",
    invocation_id: "inv-000000000001",
  };
}

describe("storageRedactEntry", () => {
  for (const ec of LOW_VALUE_CLASSES) {
    it(`strips parameters for ${ec}`, () => {
      const result = storageRedactEntry(makeEntry(ec));
      expect(result.parameters).toBeNull();
      expect(result.storage_redacted).toBe(true);
    });
  }

  for (const ec of HIGH_VALUE_CLASSES) {
    it(`preserves parameters for ${ec}`, () => {
      const result = storageRedactEntry(makeEntry(ec));
      expect(result.parameters).toEqual({ origin: "JFK", destination: "LAX" });
      expect(result.storage_redacted).toBe(false);
    });
  }

  it("preserves envelope fields", () => {
    const result = storageRedactEntry(makeEntry("low_risk_success"));
    expect(result.timestamp).toBe("2026-01-01T00:00:00Z");
    expect(result.capability).toBe("search_flights");
    expect(result.invocation_id).toBe("inv-000000000001");
  });

  it("does not mutate original", () => {
    const entry = makeEntry("low_risk_success");
    storageRedactEntry(entry);
    expect(entry.parameters).toEqual({ origin: "JFK", destination: "LAX" });
  });

  it("no event_class treated as high value", () => {
    const entry = makeEntry("high_risk_success");
    delete entry.event_class;
    const result = storageRedactEntry(entry);
    expect(result.parameters).not.toBeNull();
    expect(result.storage_redacted).toBe(false);
  });
});
