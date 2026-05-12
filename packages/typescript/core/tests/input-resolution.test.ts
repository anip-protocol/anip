import { describe, it, expect } from "vitest";
import { CapabilityInput, InputResolution, InputMeaning, ResolutionMode, ResolutionBehavior } from "../src/models";

describe("v0.24 input resolution", () => {
  it("parses minimal v0.23-shaped input unchanged", () => {
    const inp = CapabilityInput.parse({ name: "q", type: "string" });
    expect(inp.resolution).toBeNull();
    expect(inp.semantic_type).toBeNull();
    expect(inp.catalog_ref).toBeNull();
    expect(inp.entity_reference).toBe(false);
  });

  it("parses closed_values resolution", () => {
    const inp = CapabilityInput.parse({
      name: "forecast_mode",
      type: "string",
      required: false,
      default: "risk_adjusted",
      allowed_values: ["risk_adjusted", "likely", "best_case"],
      semantic_type: "business_category",
      resolution: { mode: "closed_values", on_missing: "use_default", on_ambiguous: "clarify" },
    });
    expect(inp.resolution?.mode).toBe("closed_values");
  });

  it("parses backend_resolved resolution with catalog_ref", () => {
    const inp = CapabilityInput.parse({
      name: "cohort_ref",
      type: "string",
      semantic_type: "cohort_reference",
      entity_reference: true,
      catalog_ref: "gtm.cohort_catalog",
      resolution: { mode: "backend_resolved", resolver_ref: "gtm.cohort_catalog", on_missing: "clarify" },
    });
    expect(inp.resolution?.resolver_ref).toBe("gtm.cohort_catalog");
    expect(inp.catalog_ref).toBe("gtm.cohort_catalog");
    expect(inp.entity_reference).toBe(true);
  });

  it("rejects unknown mode (schema-level)", () => {
    expect(() => InputResolution.parse({ mode: "not_real" })).toThrow();
  });

  it("rejects unknown behavior (schema-level)", () => {
    expect(() => InputResolution.parse({ mode: "clarify", on_missing: "bogus" })).toThrow();
  });

  it("rejects missing mode (required field)", () => {
    expect(() => InputResolution.parse({})).toThrow();
  });

  it("rejects closed_values without allowed_values", () => {
    expect(() => CapabilityInput.parse({
      name: "x",
      type: "string",
      resolution: { mode: "closed_values" },
    })).toThrow();
  });

  it("rejects use_default without default", () => {
    expect(() => CapabilityInput.parse({
      name: "x",
      type: "string",
      resolution: { mode: "clarify", on_missing: "use_default" },
    })).toThrow();
  });

  it("round-trips JSON", () => {
    const original = {
      name: "cohort_ref",
      type: "string",
      required: true,
      default: null,
      description: "",
      semantic_type: "cohort_reference",
      entity_reference: true,
      allowed_values: null,
      catalog_ref: "gtm.cohort_catalog",
      input_meanings: null,
      resolution: { mode: "backend_resolved", resolver_ref: "gtm.cohort_catalog", on_missing: "clarify", on_ambiguous: null, on_unresolved: null },
    };
    const parsed = CapabilityInput.parse(original);
    const serialized = JSON.parse(JSON.stringify(parsed));
    expect(serialized).toEqual(original);
  });
});
