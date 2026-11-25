/**
 * `required` defaults to `true` on a declared input (SPEC.md §4.1 "Inputs").
 */
import { describe, expect, it } from "vitest";
import { CapabilityDeclaration, CapabilityInput } from "../src/index.js";

describe("CapabilityInput.required (SPEC.md §4.1)", () => {
  it("defaults to true when a declaration does not state it", () => {
    expect(CapabilityInput.parse({ name: "origin", type: "airport_code" }).required).toBe(true);
    expect(CapabilityInput.parse({ name: "origin", type: "airport_code", required: false }).required).toBe(false);
  });

  it("is written explicitly when a decoded declaration is serialised", () => {
    const decoded = CapabilityInput.parse(JSON.parse('{"name":"origin","type":"airport_code"}'));
    expect(JSON.parse(JSON.stringify(decoded)).required).toBe(true);
  });

  it("applies inside a decoded capability declaration", () => {
    const declaration = CapabilityDeclaration.parse({
      name: "search_flights",
      description: "Search flights",
      inputs: [
        { name: "origin", type: "airport_code" },
        { name: "cabin", type: "string", required: false },
      ],
      output: { type: "flight_list", fields: [] },
      side_effect: { type: "read" },
      minimum_scope: ["travel.search"],
    });
    expect(declaration.inputs.map((i) => [i.name, i.required])).toEqual([
      ["origin", true],
      ["cabin", false],
    ]);
  });
});
