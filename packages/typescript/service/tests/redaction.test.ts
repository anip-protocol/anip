import { describe, it, expect } from "vitest";
import { redactFailure } from "../src/redaction.js";

describe("redactFailure", () => {
  const SAMPLE_FAILURE = {
    type: "scope_insufficient",
    detail:
      "Token scope ['read'] does not include required scope 'admin:write' for capability 'dangerous.action'",
    retry: true,
    resolution: {
      action: "request_scope",
      requires: "admin:write",
      grantable_by: "org-admin@example.com",
      estimated_availability: "PT1H",
    },
  };

  it("full returns unchanged", () => {
    const result = redactFailure(SAMPLE_FAILURE, "full");
    expect(result).toEqual(SAMPLE_FAILURE);
  });

  it("reduced strips grantable_by", () => {
    const result = redactFailure(SAMPLE_FAILURE, "reduced");
    expect(result.type).toBe("scope_insufficient");
    expect(result.retry).toBe(true);
    const res = result.resolution as Record<string, unknown>;
    expect(res.grantable_by).toBeNull();
    expect(res.action).toBe("request_scope");
    expect(res.requires).toBe("admin:write");
    expect(res.estimated_availability).toBe("PT1H");
  });

  it("reduced truncates long detail", () => {
    const longDetail = "x".repeat(300);
    const failure = { ...SAMPLE_FAILURE, detail: longDetail };
    const result = redactFailure(failure, "reduced");
    expect((result.detail as string).length).toBeLessThanOrEqual(200);
  });

  it("reduced preserves short detail", () => {
    const result = redactFailure(SAMPLE_FAILURE, "reduced");
    expect(result.detail).toBe(SAMPLE_FAILURE.detail);
  });

  it("redacted uses generic detail", () => {
    const result = redactFailure(SAMPLE_FAILURE, "redacted");
    expect(result.type).toBe("scope_insufficient");
    expect(result.detail).not.toBe(SAMPLE_FAILURE.detail);
    expect(result.detail as string).not.toContain("admin:write");
  });

  it("redacted strips resolution fields", () => {
    const result = redactFailure(SAMPLE_FAILURE, "redacted");
    const res = result.resolution as Record<string, unknown>;
    expect(res.requires).toBeNull();
    expect(res.grantable_by).toBeNull();
    expect(res.estimated_availability).toBeNull();
    expect(res.action).toBe("request_scope");
  });

  it("redacted preserves retry", () => {
    const result = redactFailure(SAMPLE_FAILURE, "redacted");
    expect(result.retry).toBe(true);
  });

  it("type is never redacted", () => {
    for (const level of ["full", "reduced", "redacted"]) {
      const result = redactFailure(SAMPLE_FAILURE, level);
      expect(result.type).toBe("scope_insufficient");
    }
  });

  it("policy treated as redacted", () => {
    const result = redactFailure(SAMPLE_FAILURE, "policy");
    const redacted = redactFailure(SAMPLE_FAILURE, "redacted");
    expect(result).toEqual(redacted);
  });

  it("failure without resolution", () => {
    const failure = { type: "internal_error", detail: "Something broke", retry: false };
    const result = redactFailure(failure, "redacted");
    expect(result.type).toBe("internal_error");
    expect(result.detail).toBe("Internal error");
    expect(result.retry).toBe(false);
    expect(result.resolution).toBeUndefined();
  });
});
