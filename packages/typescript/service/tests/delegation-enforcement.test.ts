/**
 * Delegation enforcement (SPEC.md §3.2, §6.3 and the behavioral-conformance list).
 *
 * The cross-runtime versions of these checks live in
 * conformance/test_delegation.py; the Python, Go, Java and C# runtimes carry
 * the same service-level tests.
 *
 * - Purpose binding: "a token issued for book_flight cannot invoke
 *   search_flights", even when its scope would cover both.
 * - Only the holder of a token (its subject) may delegate from it.
 * - A delegated token cannot widen its parent's scope or scope budget.
 * - A delegation token is a credential for delegating, never for root issuance.
 *
 * Composed capabilities (§4.6): each child step runs with its own token,
 * delegated from the caller's token and bound to the child capability, and
 * its audit entry links back to the parent invocation.
 */
import { describe, it, expect } from "vitest";
import { createANIPService, defineCapability, ANIPError } from "../src/index.js";
import type { CapabilityDef } from "../src/index.js";
import type { CapabilityDeclaration, DelegationToken } from "@anip-dev/core";
import { InMemoryStorage } from "@anip-dev/server";

const HUMAN = "human:test@example.com";

type Seen = Record<string, { token: DelegationToken; params: Record<string, unknown> }>;

function declaration(name: string, scope: string[], extra: Record<string, unknown> = {}): CapabilityDeclaration {
  return {
    name,
    description: name,
    contract_version: "1.0",
    inputs: [{ name: "q", type: "string", required: false, description: "q" }],
    output: { type: "object", fields: [] },
    side_effect: { type: "read", rollback_window: "not_applicable" },
    minimum_scope: scope,
    kind: "atomic",
    ...extra,
  } as CapabilityDeclaration;
}

function makeService(seen: Seen = {}, opts: { enrichScope?: string[] } = {}) {
  const recording = (name: string, scope: string[], result: Record<string, unknown>): CapabilityDef =>
    defineCapability({
      declaration: declaration(name, scope),
      handler: (ctx, params) => {
        seen[name] = { token: ctx.token, params: { ...params } };
        return result;
      },
    });

  const summary = defineCapability({
    declaration: declaration("summary", ["inv.read"], {
      kind: "composed",
      composition: {
        authority_boundary: "same_service",
        steps: [
          { id: "select", capability: "select_cap" },
          { id: "enrich", capability: "enrich_cap" },
        ],
        input_mapping: {
          select: { q: "$.input.q" },
          enrich: { items: "$.steps.select.output.items" },
        },
        output_mapping: { count: "$.steps.enrich.output.count" },
        failure_policy: {
          child_clarification: "propagate",
          child_denial: "propagate",
          child_approval_required: "propagate",
          child_error: "fail_parent",
        },
        audit_policy: { record_child_invocations: true, parent_task_lineage: true },
      },
    }),
    handler: () => ({ count: -1 }),
  });

  return createANIPService({
    serviceId: "test-service",
    capabilities: [
      recording("search_flights", ["travel.search"], { flights: ["FL-001"] }),
      recording("book_flight", ["travel.book"], { booking_id: "BK-001" }),
      recording("select_cap", ["inv.read"], { items: ["a", "b"] }),
      recording("enrich_cap", opts.enrichScope ?? ["inv.read"], { count: 2 }),
      summary,
    ],
    storage: new InMemoryStorage(),
    authenticate: (bearer: string) => (bearer === "test-key" ? HUMAN : null),
  });
}

type Service = ReturnType<typeof makeService>;

async function issue(service: Service, principal: string, request: Record<string, unknown>) {
  return service.issueToken(principal, request) as Promise<{ issued: boolean; token: string; token_id: string }>;
}

async function boundToken(service: Service, capability: string, scope: string[]) {
  const issued = await issue(service, HUMAN, {
    subject: HUMAN, scope, capability, purpose_parameters: { task_id: "task-under-test" },
  });
  return service.resolveBearerToken(issued.token);
}

async function failureOf(promise: Promise<unknown>): Promise<string> {
  try {
    await promise;
  } catch (e) {
    if (e instanceof ANIPError) return e.errorType;
    throw e;
  }
  return "(issued)";
}

describe("purpose binding", () => {
  it("rejects a token bound to another capability", async () => {
    const service = makeService();
    const token = await boundToken(service, "book_flight", ["travel.search", "travel.book"]);

    const result = await service.invoke("search_flights", token, {});

    expect(result.success).toBe(false);
    expect((result.failure as { type: string }).type).toBe("purpose_mismatch");
  });
});

describe("who may ask for a token", () => {
  it("authenticateIssuer accepts the bootstrap credential and tokens", async () => {
    const service = makeService();

    expect(await service.authenticateIssuer("test-key")).toEqual({ principal: HUMAN, viaToken: false });

    const held = await issue(service, HUMAN, {
      subject: "agent:helper", scope: ["travel.search"], capability: "search_flights",
    });
    // The holder of the token, not the root principal of its chain.
    expect(await service.authenticateIssuer(held.token)).toEqual({ principal: "agent:helper", viaToken: true });

    expect(await service.authenticateIssuer("not-a-credential")).toBeNull();
  });

  it("authenticateBearer is bootstrap-only", async () => {
    // A delegation token must not authenticate as its chain's root principal:
    // token endpoints that used this as the issuing principal let any token
    // holder act as the human who started the chain.
    const service = makeService();
    const held = await issue(service, HUMAN, {
      subject: "agent:helper", scope: ["travel.search"], capability: "search_flights",
    });

    expect(await service.authenticateBearer("test-key")).toBe(HUMAN);
    expect(await service.authenticateBearer(held.token)).toBeNull();
  });

  it("a token credential cannot issue a root token", async () => {
    const service = makeService();
    const held = await issue(service, HUMAN, {
      subject: "agent:helper", scope: ["travel.search"], capability: "search_flights",
    });
    const issuer = (await service.authenticateIssuer(held.token))!;

    // No parent_token: this asks for a root token, with more scope than the
    // agent was ever given.
    const failure = await failureOf(service.issueTokenAs(issuer, {
      scope: ["travel.search", "travel.book"], capability: "book_flight",
    }));

    expect(failure).toBe("insufficient_authority");
  });

  it("the holder delegates with its token as credential", async () => {
    const service = makeService();
    const held = await issue(service, HUMAN, {
      subject: "agent:helper", scope: ["travel.search"], capability: "search_flights",
    });
    const issuer = (await service.authenticateIssuer(held.token))!;

    const child = (await service.issueTokenAs(issuer, {
      subject: "agent:sub-helper", scope: ["travel.search"], capability: "search_flights",
      parent_token: held.token_id,
    })) as { token: string };

    const token = await service.resolveBearerToken(child.token);
    expect(token.root_principal).toBe(HUMAN);
    expect(token.issuer).toBe("agent:helper");
  });

  it("the bootstrap credential issues a root token", async () => {
    const service = makeService();
    const issuer = (await service.authenticateIssuer("test-key"))!;

    const root = await service.issueTokenAs(issuer, { scope: ["travel.search"], capability: "search_flights" });

    expect(root.issued).toBe(true);
  });

  it("only the holder of a token delegates from it", async () => {
    const service = makeService();
    const root = await issue(service, HUMAN, { subject: HUMAN, scope: ["travel.search"], capability: "search_flights" });

    const failure = await failureOf(issue(service, "agent:someone-else", {
      scope: ["travel.search"], capability: "search_flights", parent_token: root.token_id,
    }));

    expect(failure).toBe("insufficient_authority");
  });
});

describe("scope narrowing", () => {
  const cases: Array<[string, string, string, boolean]> = [
    ["same scope", "travel.search", "travel.search", true],
    ["sub-scope of parent", "travel", "travel.search", true],
    ["sibling scope", "travel.search", "travel.book", false],
    ["prefix without a dot boundary", "travel", "travelogue.read", false],
    ["keeps scope budget", "travel.book:max_$500", "travel.book:max_$500", true],
    ["lowers scope budget", "travel.book:max_$500", "travel.book:max_$100", true],
    ["drops scope budget", "travel.book:max_$500", "travel.book", false],
    ["raises scope budget", "travel.book:max_$500", "travel.book:max_$900", false],
    // A budget on a parent scope bounds every scope beneath it.
    ["sub-scope keeps parent budget", "travel:max_$500", "travel.book:max_$500", true],
    ["sub-scope drops parent budget", "travel:max_$500", "travel.book", false],
    ["sub-scope raises parent budget", "travel:max_$500", "travel.book:max_$900", false],
    // A budget that is not a finite, non-negative number must fail closed:
    // NaN compares false against everything.
    ["NaN scope budget", "travel.book:max_$500", "travel.book:max_$NaN", false],
    ["infinite scope budget", "travel.book:max_$500", "travel.book:max_$Infinity", false],
    ["negative scope budget", "travel.book:max_$500", "travel.book:max_$-1", false],
    ["unparseable scope budget", "travel.book:max_$500", "travel.book:max_$lots", false],
    // parseFloat would read "100abc" as 100; the whole value must be a number.
    ["budget with trailing text", "travel.book:max_$500", "travel.book:max_$100abc", false],
  ];

  it.each(cases)("%s", async (_name, parentScope, childScope, allowed) => {
    const service = makeService();
    const root = await issue(service, HUMAN, { subject: HUMAN, scope: [parentScope], capability: "book_flight" });

    const failure = await failureOf(issue(service, HUMAN, {
      scope: [childScope], capability: "book_flight", parent_token: root.token_id,
    }));

    expect(failure).toBe(allowed ? "(issued)" : "scope_escalation");
  });
});

describe("composed capabilities", () => {
  it("run children with child-bound tokens and linked audit entries", async () => {
    const seen: Seen = {};
    const service = makeService(seen);
    const token = await boundToken(service, "summary", ["inv.read"]);

    const result = await service.invoke("summary", token, { q: "x" });

    expect(result.success).toBe(true);
    expect(result.result).toEqual({ count: 2 });
    expect(seen.select_cap.params).toEqual({ q: "x" });
    for (const child of ["select_cap", "enrich_cap"]) {
      expect(seen[child].token.purpose.capability).toBe(child);
      expect(seen[child].token.parent).toBe(token.token_id);
    }

    const audit = (await service.queryAudit(token)) as { entries: Array<Record<string, unknown>> };
    const byCapability = Object.fromEntries(audit.entries.map((e) => [e.capability as string, e]));
    for (const child of ["select_cap", "enrich_cap"]) {
      expect(byCapability[child].success).toBe(true);
      expect(byCapability[child].parent_invocation_id).toBe(result.invocation_id);
      expect(byCapability[child].task_id).toBeTruthy();
      expect(byCapability[child].task_id).toBe(byCapability.summary.task_id);
    }
  });

  it("cannot reach a child beyond the caller's scope", async () => {
    const seen: Seen = {};
    const service = makeService(seen, { enrichScope: ["inv.admin"] });
    const token = await boundToken(service, "summary", ["inv.read"]);

    const result = await service.invoke("summary", token, { q: "x" });

    expect(result.success).toBe(false);
    expect(seen.enrich_cap).toBeUndefined();
    // Default failure_policy propagates a child denial unchanged: the caller
    // is told its token lacks the scope the step needs.
    const failure = result.failure as { type: string; detail: string };
    expect(failure.type).toBe("scope_insufficient");
    expect(failure.detail).toContain("inv.admin");
  });

  it("keep the caller's scope budget on child tokens", async () => {
    const seen: Seen = {};
    const service = makeService(seen);
    // "inv:max_$50" covers "inv.read"; the child keeps the budget.
    const token = await boundToken(service, "summary", ["inv:max_$50"]);

    const result = await service.invoke("summary", token, { q: "x" });

    expect(result.success).toBe(true);
    expect(seen.select_cap.token.scope).toEqual(["inv.read:max_$50"]);
  });
});
