/**
 * defineCapability takes a declaration as a person writes it: fields that have
 * defaults are left out. It must fill those defaults in and reject a malformed
 * declaration when the capability is defined.
 *
 * Before this, defineCapability returned its argument unchanged. A declaration
 * only type-checked with every optional field spelled out (or a cast), and with
 * a cast the defaults were never applied: an input was not marked required, a
 * capability had no kind.
 */
import { describe, it, expect } from "vitest";
import { createANIPService, defineCapability } from "../src/index.js";
import { InMemoryStorage } from "@anip-dev/server";

// No cast: this is the shape the quickstart shows.
const minimal = () =>
  defineCapability({
    declaration: {
      name: "search_flights",
      description: "Search flights",
      inputs: [
        { name: "origin", type: "string", description: "Departure airport" },
        { name: "limit", type: "integer", description: "Max results", required: false },
      ],
      output: { type: "object", fields: ["flights"] },
      side_effect: { type: "read", rollback_window: "not_applicable" },
      minimum_scope: ["travel.search"],
    },
    handler: () => ({ flights: [] }),
  });

describe("defineCapability", () => {
  it("fills in the defaults of a hand-written declaration", () => {
    const { declaration } = minimal();

    expect(declaration.contract_version).toBe("1.0");
    expect(declaration.kind).toBe("atomic");
    expect(declaration.composition).toBeNull();
    expect(declaration.cost).toBeNull();
    expect(declaration.response_modes).toEqual(["unary"]);
    expect(declaration.inputs[0].required).toBe(true);
    expect(declaration.inputs[1].required).toBe(false);
  });

  it("rejects a malformed declaration, naming the capability and the field", () => {
    const define = () =>
      defineCapability({
        declaration: {
          name: "book_flight",
          description: "Book a flight",
          inputs: [],
          output: { type: "object", fields: [] },
          // @ts-expect-error "sometimes" is not a side-effect type
          side_effect: { type: "sometimes" },
          minimum_scope: ["travel.book"],
        },
        handler: () => ({}),
      });

    expect(define).toThrowError(/Invalid declaration for capability 'book_flight'.*side_effect/);
  });

  it("is idempotent: a defined capability can be defined again", () => {
    const first = minimal();
    const second = defineCapability(first);

    expect(second.declaration).toEqual(first.declaration);
  });
});

describe("createANIPService", () => {
  it("applies the same defaults to a capability built without defineCapability", async () => {
    const service = createANIPService({
      serviceId: "test-service",
      capabilities: [
        {
          declaration: {
            name: "search_flights",
            description: "Search flights",
            inputs: [{ name: "origin", type: "string", description: "Departure airport" }],
            output: { type: "object", fields: ["flights"] },
            side_effect: { type: "read", rollback_window: "not_applicable" },
            minimum_scope: ["travel.search"],
          },
          handler: () => ({ flights: [] }),
        },
      ],
      storage: new InMemoryStorage(),
      authenticate: () => null,
    });

    const manifest = service.getManifest() as {
      capabilities: Record<string, { kind: string; inputs: Array<{ required: boolean }> }>;
    };
    expect(manifest.capabilities.search_flights.kind).toBe("atomic");
    expect(manifest.capabilities.search_flights.inputs[0].required).toBe(true);
  });

  it("rejects a malformed declaration when the service is created", () => {
    const create = () =>
      createANIPService({
        serviceId: "test-service",
        capabilities: [
          {
            // @ts-expect-error minimum_scope is missing
            declaration: {
              name: "search_flights",
              description: "Search flights",
              inputs: [],
              output: { type: "object", fields: [] },
              side_effect: { type: "read", rollback_window: "not_applicable" },
            },
            handler: () => ({}),
          },
        ],
        storage: new InMemoryStorage(),
        authenticate: () => null,
      });

    expect(create).toThrowError(/Invalid declaration for capability 'search_flights'.*minimum_scope/);
  });
});
