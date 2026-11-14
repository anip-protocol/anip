/**
 * Every refusal made before the handler is audited (SPEC.md §6.3): budget,
 * binding and control-requirement refusals are recorded like scope,
 * purpose and parameter refusals, on unary and streaming invocations.
 */
import { describe, it, expect } from "vitest";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { classifyEvent, createANIPService, defineCapability } from "../src/index.js";
import type { CapabilityDeclaration } from "@anip-dev/core";
import { InMemoryStorage } from "@anip-dev/server";

const HUMAN = "human:test@example.com";
const NOW = Math.floor(Date.now() / 1000);

const ESTIMATED = {
  cost: { certainty: "estimated", financial: { currency: "USD", range_min: 100, range_max: 500 } },
  requires_binding: [{ type: "quote", field: "quote", max_age: "PT15M" }],
};
const FIXED = { cost: { certainty: "fixed", financial: { currency: "USD", amount: 500 } } };

const CASES: Array<[string, Record<string, unknown>, Record<string, unknown>, Record<string, unknown> | undefined, string]> = [
  ["budget_exceeded (fixed)", FIXED, {}, { currency: "USD", max_amount: 1 }, "budget_exceeded"],
  ["budget_exceeded (bound price)", ESTIMATED, { quote: { price: 420, issued_at: NOW } }, { currency: "USD", max_amount: 100 }, "budget_exceeded"],
  ["budget_currency_mismatch", FIXED, {}, { currency: "EUR", max_amount: 1000 }, "budget_currency_mismatch"],
  ["budget_not_enforceable", ESTIMATED, { quote: { issued_at: NOW } }, { currency: "USD", max_amount: 1000 }, "budget_not_enforceable"],
  ["binding_missing", ESTIMATED, {}, undefined, "binding_missing"],
  ["binding_stale", ESTIMATED, { quote: { price: 420, issued_at: NOW - 86400 } }, undefined, "binding_stale"],
  ["control requirement", { control_requirements: [{ type: "cost_ceiling", enforcement: "reject" }] }, {}, undefined, "control_requirement_unsatisfied"],
];

async function setup(extra: Record<string, unknown>) {
  const calls: unknown[] = [];
  const service = createANIPService({
    serviceId: "test-prehandler-audit",
    capabilities: [
      defineCapability({
        declaration: {
          name: "book",
          description: "book",
          contract_version: "1.0",
          inputs: [{ name: "quote", type: "object", required: false, description: "quote" }],
          output: { type: "object", fields: [] },
          side_effect: { type: "irreversible", rollback_window: "none" },
          minimum_scope: ["book"],
          response_modes: ["unary", "streaming"],
          ...extra,
        } as unknown as CapabilityDeclaration,
        handler: async (_ctx, params) => {
          calls.push(params);
          return { ok: true };
        },
      }),
    ],
    storage: new InMemoryStorage(),
    keyPath: join(mkdtempSync(join(tmpdir(), "anip-prehandler-audit-")), "keys.json"),
    authenticate: (bearer: string) => (bearer === "test-key" ? HUMAN : null),
  });
  const issued = await service.issueToken(HUMAN, { subject: HUMAN, scope: ["book"], capability: "book" });
  const token = await service.resolveBearerToken(issued.token as string);
  return { service, token, calls };
}

describe("refusals before the handler are audited", () => {
  for (const stream of [false, true]) {
    for (const [name, extra, parameters, budget, expected] of CASES) {
      it(`${name} (${stream ? "streaming" : "unary"})`, async () => {
        const { service, token, calls } = await setup(extra);
        const events: unknown[] = [];

        const result = await service.invoke("book", token, { ...parameters }, {
          budget: budget ?? null,
          ...(stream ? { stream: true, progressSink: async (e: unknown) => { events.push(e); } } : {}),
        } as any);

        expect(result.success).toBe(false);
        expect((result.failure as Record<string, unknown>).type).toBe(expected);
        expect(calls).toEqual([]);
        expect(events).toEqual([]);
        const audit = (await service.queryAudit(token, { invocation_id: result.invocation_id as string })) as {
          entries: Array<Record<string, unknown>>;
        };
        expect(audit.entries).toHaveLength(1);
        expect(audit.entries[0].success).toBe(false);
        expect(audit.entries[0].failure_type).toBe(expected);
        expect(audit.entries[0].event_class).toBe(classifyEvent("irreversible", false, expected));
      });
    }
  }
});
