import { describe, it, expect } from "vitest";
import {
  DEFAULT_CLASS_TO_TIER,
  DEFAULT_TIER_TO_DURATION,
  RetentionPolicy,
} from "../src/retention.js";
import { classifyEvent } from "../src/classification.js";

describe("DEFAULT_CLASS_TO_TIER", () => {
  it("maps high_risk_success to long", () => {
    expect(DEFAULT_CLASS_TO_TIER.high_risk_success).toBe("long");
  });

  it("maps high_risk_denial to medium", () => {
    expect(DEFAULT_CLASS_TO_TIER.high_risk_denial).toBe("medium");
  });

  it("maps low_risk_success to short", () => {
    expect(DEFAULT_CLASS_TO_TIER.low_risk_success).toBe("short");
  });

  it("maps repeated_low_value_denial to short", () => {
    expect(DEFAULT_CLASS_TO_TIER.repeated_low_value_denial).toBe("short");
  });

  it("maps malformed_or_spam to short", () => {
    expect(DEFAULT_CLASS_TO_TIER.malformed_or_spam).toBe("short");
  });
});

describe("DEFAULT_TIER_TO_DURATION", () => {
  it("maps long to P365D", () => {
    expect(DEFAULT_TIER_TO_DURATION.long).toBe("P365D");
  });

  it("maps medium to P90D", () => {
    expect(DEFAULT_TIER_TO_DURATION.medium).toBe("P90D");
  });

  it("maps short to P7D", () => {
    expect(DEFAULT_TIER_TO_DURATION.short).toBe("P7D");
  });

  it("maps aggregate_only to P7D", () => {
    expect(DEFAULT_TIER_TO_DURATION.aggregate_only).toBe("P7D");
  });
});

describe("RetentionPolicy.resolveTier", () => {
  it("resolves all default event classes", () => {
    const policy = new RetentionPolicy();
    expect(policy.resolveTier("high_risk_success")).toBe("long");
    expect(policy.resolveTier("high_risk_denial")).toBe("medium");
    expect(policy.resolveTier("low_risk_success")).toBe("short");
    expect(policy.resolveTier("repeated_low_value_denial")).toBe("short");
    expect(policy.resolveTier("malformed_or_spam")).toBe("short");
  });

  it("falls back to short for unknown class", () => {
    const policy = new RetentionPolicy();
    expect(policy.resolveTier("totally_unknown")).toBe("short");
  });

  it("accepts custom override", () => {
    const policy = new RetentionPolicy({
      classToTier: { high_risk_denial: "long" },
    });
    expect(policy.resolveTier("high_risk_denial")).toBe("long");
    // Other defaults still work
    expect(policy.resolveTier("high_risk_success")).toBe("long");
    expect(policy.resolveTier("low_risk_success")).toBe("short");
  });
});

describe("RetentionPolicy.computeExpiresAt", () => {
  it("computes short tier (P7D = 7 days later)", () => {
    const policy = new RetentionPolicy();
    const now = new Date("2025-01-01T00:00:00.000Z");
    const result = policy.computeExpiresAt("short", now);
    expect(result).toBe("2025-01-08T00:00:00.000Z");
  });

  it("computes long tier (P365D = 365 days later)", () => {
    const policy = new RetentionPolicy();
    const now = new Date("2025-01-01T00:00:00.000Z");
    const result = policy.computeExpiresAt("long", now);
    expect(result).toBe("2026-01-01T00:00:00.000Z");
  });

  it("returns null for null duration", () => {
    const policy = new RetentionPolicy({
      tierToDuration: { custom: null },
    });
    const now = new Date("2025-01-01T00:00:00.000Z");
    const result = policy.computeExpiresAt("custom", now);
    expect(result).toBeNull();
  });

  it("aggregate_only has same expiry as short in v0.8", () => {
    const policy = new RetentionPolicy();
    const now = new Date("2025-06-15T12:00:00.000Z");
    const shortResult = policy.computeExpiresAt("short", now);
    const aggResult = policy.computeExpiresAt("aggregate_only", now);
    expect(shortResult).toBe(aggResult);
  });
});

describe("Full pipeline: classify -> resolve tier -> compute expires_at", () => {
  it("write + success -> high_risk_success -> long -> P365D", () => {
    const policy = new RetentionPolicy();
    const now = new Date("2025-03-01T00:00:00.000Z");

    const eventClass = classifyEvent("write", true, null);
    const tier = policy.resolveTier(eventClass);
    const expires = policy.computeExpiresAt(tier, now);

    expect(eventClass).toBe("high_risk_success");
    expect(tier).toBe("long");
    expect(expires).toBe("2026-03-01T00:00:00.000Z");
  });
});
