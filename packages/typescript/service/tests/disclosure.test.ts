import { describe, it, expect } from "vitest";
import { resolveDisclosureLevel } from "../src/disclosure.js";

describe("Fixed mode", () => {
  it("full returns full", () => {
    expect(resolveDisclosureLevel("full", {})).toBe("full");
  });
  it("reduced returns reduced", () => {
    expect(resolveDisclosureLevel("reduced", {})).toBe("reduced");
  });
  it("redacted returns redacted", () => {
    expect(resolveDisclosureLevel("redacted", {})).toBe("redacted");
  });
  it("ignores token claims in fixed mode", () => {
    expect(
      resolveDisclosureLevel("redacted", { "anip:caller_class": "internal" }, { internal: "full" }),
    ).toBe("redacted");
  });
});

describe("Policy mode", () => {
  it("resolves from caller class", () => {
    expect(
      resolveDisclosureLevel("policy", { "anip:caller_class": "internal" }, { internal: "full", default: "redacted" }),
    ).toBe("full");
  });
  it("falls back to default", () => {
    expect(
      resolveDisclosureLevel("policy", { "anip:caller_class": "unknown" }, { internal: "full", default: "reduced" }),
    ).toBe("reduced");
  });
  it("falls back to redacted when no default", () => {
    expect(
      resolveDisclosureLevel("policy", { "anip:caller_class": "unknown" }, { internal: "full" }),
    ).toBe("redacted");
  });
  it("no token claim uses default", () => {
    expect(
      resolveDisclosureLevel("policy", {}, { internal: "full", default: "reduced" }),
    ).toBe("reduced");
  });
  it("no policy returns redacted", () => {
    expect(
      resolveDisclosureLevel("policy", { "anip:caller_class": "internal" }),
    ).toBe("redacted");
  });
  it("null claims uses default", () => {
    expect(
      resolveDisclosureLevel("policy", null, { default: "reduced" }),
    ).toBe("reduced");
  });
});
