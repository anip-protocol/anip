import { describe, it, expect } from "vitest";
import { classifyEvent } from "../src/classification.js";

describe("classifyEvent", () => {
  it("write + success = high_risk_success", () => {
    expect(classifyEvent("write", true, null)).toBe("high_risk_success");
  });

  it("irreversible + success = high_risk_success", () => {
    expect(classifyEvent("irreversible", true, null)).toBe("high_risk_success");
  });

  it("transactional + success = high_risk_success", () => {
    expect(classifyEvent("transactional", true, null)).toBe("high_risk_success");
  });

  it("read + success = low_risk_success", () => {
    expect(classifyEvent("read", true, null)).toBe("low_risk_success");
  });

  it("write + scope_insufficient = high_risk_denial", () => {
    expect(classifyEvent("write", false, "scope_insufficient")).toBe(
      "high_risk_denial",
    );
  });

  it("read + invalid_token = high_risk_denial", () => {
    expect(classifyEvent("read", false, "invalid_token")).toBe(
      "high_risk_denial",
    );
  });

  it("read + scope_insufficient = high_risk_denial", () => {
    expect(classifyEvent("read", false, "scope_insufficient")).toBe(
      "high_risk_denial",
    );
  });

  it("read + insufficient_authority = high_risk_denial", () => {
    expect(classifyEvent("read", false, "insufficient_authority")).toBe(
      "high_risk_denial",
    );
  });

  it("null + unknown_capability = malformed_or_spam", () => {
    expect(classifyEvent(null, false, "unknown_capability")).toBe(
      "malformed_or_spam",
    );
  });

  it("read + streaming_not_supported = malformed_or_spam", () => {
    expect(classifyEvent("read", false, "streaming_not_supported")).toBe(
      "malformed_or_spam",
    );
  });

  it("write + internal_error = malformed_or_spam", () => {
    expect(classifyEvent("write", false, "internal_error")).toBe(
      "malformed_or_spam",
    );
  });

  it("null + invalid_token = malformed_or_spam (pre-resolution)", () => {
    expect(classifyEvent(null, false, "invalid_token")).toBe(
      "malformed_or_spam",
    );
  });

  it("null + unknown_capability = malformed_or_spam (pre-resolution)", () => {
    expect(classifyEvent(null, false, "unknown_capability")).toBe(
      "malformed_or_spam",
    );
  });

  it("write + not_found = high_risk_denial (handler error)", () => {
    expect(classifyEvent("write", false, "not_found")).toBe(
      "high_risk_denial",
    );
  });

  it("read + not_found = high_risk_denial (handler error)", () => {
    expect(classifyEvent("read", false, "not_found")).toBe(
      "high_risk_denial",
    );
  });
});
