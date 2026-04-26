/**
 * Composition validation + execution tests (v0.23 §4.6).
 *
 * Mirrors anip-service/tests/test_v023_composition.py.
 */
import { describe, it, expect } from "vitest";
import type {
  CapabilityDeclaration,
  Composition,
} from "@anip-dev/core";
import {
  CompositionValidationError,
  executeComposition,
  sha256Digest,
  validateComposition,
  ANIPError,
} from "../src/index.js";

// ---------------------------------------------------------------------------
// Builders
// ---------------------------------------------------------------------------

function atomicDecl(
  name: string,
  opts?: { fields?: string[] },
): CapabilityDeclaration {
  return {
    name,
    description: `atomic ${name}`,
    contract_version: "1.0",
    inputs: [{ name: "x", type: "string", required: true, description: "x" }],
    output: { type: "x", fields: opts?.fields ?? ["x"] },
    side_effect: { type: "read", rollback_window: "not_applicable" },
    minimum_scope: ["s"],
    cost: null,
    requires: [],
    composes_with: [],
    session: { type: "stateless" },
    observability: null,
    response_modes: ["unary"],
    requires_binding: [],
    control_requirements: [],
    refresh_via: [],
    verify_via: [],
    cross_service: null,
    kind: "atomic",
    composition: null,
    grant_policy: null,
  } as unknown as CapabilityDeclaration;
}

function composedDecl(opts: {
  name?: string;
  composition: Composition;
}): CapabilityDeclaration {
  return {
    name: opts.name ?? "summary",
    description: "composed",
    contract_version: "1.0",
    inputs: [],
    output: { type: "x", fields: ["count", "items"] },
    side_effect: { type: "read", rollback_window: "not_applicable" },
    minimum_scope: ["s"],
    cost: null,
    requires: [],
    composes_with: [],
    session: { type: "stateless" },
    observability: null,
    response_modes: ["unary"],
    requires_binding: [],
    control_requirements: [],
    refresh_via: [],
    verify_via: [],
    cross_service: null,
    kind: "composed",
    composition: opts.composition,
    grant_policy: null,
  } as unknown as CapabilityDeclaration;
}

function basicComposition(): Composition {
  return {
    authority_boundary: "same_service",
    steps: [
      {
        id: "select",
        capability: "select_cap",
        empty_result_source: true,
        empty_result_path: null,
      },
      {
        id: "enrich",
        capability: "enrich_cap",
        empty_result_source: false,
        empty_result_path: null,
      },
    ],
    input_mapping: {
      select: { q: "$.input.q" },
      enrich: { items: "$.steps.select.output.items" },
    },
    output_mapping: {
      count: "$.steps.enrich.output.count",
      items: "$.steps.enrich.output.items",
    },
    empty_result_policy: "return_success_no_results",
    empty_result_output: { count: 0, items: [] },
    failure_policy: {
      child_clarification: "propagate",
      child_denial: "propagate",
      child_approval_required: "propagate",
      child_error: "fail_parent",
    },
    audit_policy: {
      record_child_invocations: true,
      parent_task_lineage: true,
    },
  } as unknown as Composition;
}

function registry(): Record<string, CapabilityDeclaration> {
  return {
    select_cap: atomicDecl("select_cap", { fields: ["items"] }),
    enrich_cap: atomicDecl("enrich_cap", { fields: ["count", "items"] }),
  };
}

// ---------------------------------------------------------------------------
// validateComposition: registration-time invariants
// ---------------------------------------------------------------------------

describe("validateComposition", () => {
  it("atomic_declaration_passes", () => {
    const decl = atomicDecl("a");
    expect(() =>
      validateComposition("a", decl, { otherCapabilities: {} }),
    ).not.toThrow();
  });

  it("composed_happy_path", () => {
    const decl = composedDecl({ composition: basicComposition() });
    expect(() =>
      validateComposition("summary", decl, { otherCapabilities: registry() }),
    ).not.toThrow();
  });

  it("validate_composition_catches_missing_composition", () => {
    // If the model is constructed without composition (e.g. via cast), the
    // second-line defense in validateComposition must still reject.
    const decl = composedDecl({ composition: basicComposition() });
    (decl as unknown as Record<string, unknown>).composition = null;
    expect(() =>
      validateComposition("summary", decl, { otherCapabilities: registry() }),
    ).toThrow(CompositionValidationError);
    expect(() =>
      validateComposition("summary", decl, { otherCapabilities: registry() }),
    ).toThrow(/composition is missing/);
  });

  it("unsupported_authority_boundary", () => {
    const comp = basicComposition();
    (comp as unknown as Record<string, unknown>).authority_boundary = "same_package";
    expect(() =>
      validateComposition(
        "summary",
        composedDecl({ composition: comp }),
        { otherCapabilities: registry() },
      ),
    ).toThrow(/composition_unsupported_authority_boundary/);
  });

  it("duplicate_step_ids", () => {
    const comp = basicComposition();
    comp.steps = [
      { id: "a", capability: "select_cap", empty_result_source: false, empty_result_path: null },
      { id: "a", capability: "enrich_cap", empty_result_source: false, empty_result_path: null },
    ];
    comp.input_mapping = { a: {} };
    comp.output_mapping = {};
    (comp as unknown as Record<string, unknown>).empty_result_policy = null;
    (comp as unknown as Record<string, unknown>).empty_result_output = null;
    expect(() =>
      validateComposition(
        "summary",
        composedDecl({ composition: comp }),
        { otherCapabilities: registry() },
      ),
    ).toThrow(/duplicate step ids/);
  });

  it("self_reference_rejected", () => {
    const comp = basicComposition();
    comp.steps[0].capability = "summary";
    expect(() =>
      validateComposition(
        "summary",
        composedDecl({ composition: comp }),
        { otherCapabilities: registry() },
      ),
    ).toThrow(/self-references/);
  });

  it("unknown_step_capability", () => {
    const comp = basicComposition();
    comp.steps[0].capability = "does_not_exist";
    expect(() =>
      validateComposition(
        "summary",
        composedDecl({ composition: comp }),
        { otherCapabilities: registry() },
      ),
    ).toThrow(/composition_unknown_capability/);
  });

  it("composed_referencing_composed_rejected", () => {
    const select = composedDecl({
      name: "select_cap",
      composition: basicComposition(),
    });
    const reg = { select_cap: select, enrich_cap: atomicDecl("enrich_cap") };
    expect(() =>
      validateComposition(
        "summary",
        composedDecl({ composition: basicComposition() }),
        { otherCapabilities: reg },
      ),
    ).toThrow(/kind='composed'/);
  });

  it("at_most_one_empty_result_source", () => {
    const comp = basicComposition();
    comp.steps[1].empty_result_source = true;
    expect(() =>
      validateComposition(
        "summary",
        composedDecl({ composition: comp }),
        { otherCapabilities: registry() },
      ),
    ).toThrow(/at most one/);
  });

  it("input_mapping_unknown_step_key", () => {
    const comp = basicComposition();
    comp.input_mapping = { nope: { q: "$.input.q" } };
    expect(() =>
      validateComposition(
        "summary",
        composedDecl({ composition: comp }),
        { otherCapabilities: registry() },
      ),
    ).toThrow(/not a declared step id/);
  });

  it("input_mapping_forward_reference_rejected", () => {
    const comp = basicComposition();
    comp.input_mapping["select"] = { items: "$.steps.enrich.output.items" };
    expect(() =>
      validateComposition(
        "summary",
        composedDecl({ composition: comp }),
        { otherCapabilities: registry() },
      ),
    ).toThrow(/forward-references/);
  });

  it("output_mapping_unknown_step", () => {
    const comp = basicComposition();
    comp.output_mapping = { count: "$.steps.bogus.output.count" };
    expect(() =>
      validateComposition(
        "summary",
        composedDecl({ composition: comp }),
        { otherCapabilities: registry() },
      ),
    ).toThrow(/references unknown step/);
  });

  it("empty_result_policy_clarify_with_output_rejected", () => {
    const comp = basicComposition();
    comp.empty_result_policy = "clarify";
    // empty_result_output remains set from basicComposition
    expect(() =>
      validateComposition(
        "summary",
        composedDecl({ composition: comp }),
        { otherCapabilities: registry() },
      ),
    ).toThrow(/forbidden/);
  });

  it("empty_result_policy_return_success_without_output_rejected", () => {
    const comp = basicComposition();
    (comp as unknown as Record<string, unknown>).empty_result_output = null;
    expect(() =>
      validateComposition(
        "summary",
        composedDecl({ composition: comp }),
        { otherCapabilities: registry() },
      ),
    ).toThrow(/requires empty_result_output/);
  });

  it("empty_result_output_referencing_skipped_step_rejected", () => {
    const comp = basicComposition();
    comp.empty_result_output = { items: "$.steps.enrich.output.items" };
    expect(() =>
      validateComposition(
        "summary",
        composedDecl({ composition: comp }),
        { otherCapabilities: registry() },
      ),
    ).toThrow(/only the empty_result_source/);
  });

  it("empty_result_output_input_reference_allowed", () => {
    const comp = basicComposition();
    comp.empty_result_output = { q: "$.input.q", items: [] };
    expect(() =>
      validateComposition(
        "summary",
        composedDecl({ composition: comp }),
        { otherCapabilities: registry() },
      ),
    ).not.toThrow();
  });

  it("step_with_empty_result_source_requires_policy", () => {
    const comp = basicComposition();
    (comp as unknown as Record<string, unknown>).empty_result_policy = null;
    (comp as unknown as Record<string, unknown>).empty_result_output = null;
    expect(() =>
      validateComposition(
        "summary",
        composedDecl({ composition: comp }),
        { otherCapabilities: registry() },
      ),
    ).toThrow(/empty_result_source/);
  });
});

// ---------------------------------------------------------------------------
// executeComposition: runtime
// ---------------------------------------------------------------------------

function makeStepRunner(
  scripted: Record<string, Record<string, unknown> | Error>,
): {
  runner: (
    capability: string,
    params: Record<string, unknown>,
  ) => Promise<Record<string, unknown>>;
  calls: Array<[string, Record<string, unknown>]>;
} {
  const calls: Array<[string, Record<string, unknown>]> = [];
  const runner = async (
    capability: string,
    params: Record<string, unknown>,
  ): Promise<Record<string, unknown>> => {
    calls.push([capability, params]);
    const result = scripted[capability];
    if (result instanceof Error) throw result;
    return result;
  };
  return { runner, calls };
}

describe("executeComposition", () => {
  it("happy_path_all_steps_succeed", async () => {
    const decl = composedDecl({ composition: basicComposition() });
    const { runner, calls } = makeStepRunner({
      select_cap: { success: true, result: { items: [{ id: 1 }, { id: 2 }] } },
      enrich_cap: { success: true, result: { count: 2, items: ["a", "b"] } },
    });
    const out = await executeComposition(
      "summary",
      decl,
      { q: "test" },
      { invokeStep: runner },
    );
    expect(out).toEqual({ count: 2, items: ["a", "b"] });
    expect(calls[0]).toEqual(["select_cap", { q: "test" }]);
    expect(calls[1]).toEqual(["enrich_cap", { items: [{ id: 1 }, { id: 2 }] }]);
  });

  it("empty_result_return_success_no_results", async () => {
    const decl = composedDecl({ composition: basicComposition() });
    const { runner, calls } = makeStepRunner({
      select_cap: { success: true, result: { items: [] } },
    });
    const out = await executeComposition(
      "summary",
      decl,
      { q: "test" },
      { invokeStep: runner },
    );
    expect(out).toEqual({ count: 0, items: [] });
    // enrich_cap is NEVER called because select's output was empty.
    expect(calls).toHaveLength(1);
  });

  it("empty_result_clarify_raises", async () => {
    const comp = basicComposition();
    comp.empty_result_policy = "clarify";
    (comp as unknown as Record<string, unknown>).empty_result_output = null;
    const decl = composedDecl({ composition: comp });
    const { runner } = makeStepRunner({
      select_cap: { success: true, result: { items: [] } },
    });
    await expect(
      executeComposition("summary", decl, { q: "x" }, { invokeStep: runner }),
    ).rejects.toMatchObject({
      errorType: "composition_empty_result_clarification_required",
    });
  });

  it("empty_result_deny_raises", async () => {
    const comp = basicComposition();
    comp.empty_result_policy = "deny";
    (comp as unknown as Record<string, unknown>).empty_result_output = null;
    const decl = composedDecl({ composition: comp });
    const { runner } = makeStepRunner({
      select_cap: { success: true, result: { items: [] } },
    });
    await expect(
      executeComposition("summary", decl, { q: "x" }, { invokeStep: runner }),
    ).rejects.toMatchObject({
      errorType: "composition_empty_result_denied",
    });
  });

  it("child_failure_propagates_by_default", async () => {
    const decl = composedDecl({ composition: basicComposition() });
    const { runner } = makeStepRunner({
      select_cap: {
        success: false,
        failure: {
          type: "scope_insufficient",
          detail: "select_cap requires more scope",
          resolution: {
            action: "request_broader_scope",
            recovery_class: "redelegation_then_retry",
          },
        },
      },
    });
    let caught: ANIPError | null = null;
    try {
      await executeComposition(
        "summary",
        decl,
        { q: "x" },
        { invokeStep: runner },
      );
    } catch (e) {
      if (e instanceof ANIPError) caught = e;
    }
    expect(caught).not.toBeNull();
    // Default failure_policy.child_denial = "propagate".
    expect(caught!.errorType).toBe("scope_insufficient");
  });

  it("child_error_fails_parent", async () => {
    // Default child_error policy is fail_parent — collapses to a generic
    // composition_child_failed parent error per SPEC.md §4.6.
    const decl = composedDecl({ composition: basicComposition() });
    const { runner } = makeStepRunner({
      select_cap: {
        success: false,
        failure: {
          type: "internal_error",
          detail: "boom",
          resolution: { action: "retry_now", recovery_class: "retry_now" },
        },
      },
    });
    let caught: ANIPError | null = null;
    try {
      await executeComposition(
        "summary",
        decl,
        { q: "x" },
        { invokeStep: runner },
      );
    } catch (e) {
      if (e instanceof ANIPError) caught = e;
    }
    expect(caught).not.toBeNull();
    // SPEC.md §4.6: fail_parent collapses to a generic parent error type.
    expect(caught!.errorType).toBe("composition_child_failed");
    // Original child type captured in the detail for diagnostics.
    expect(caught!.detail).toContain("internal_error");
    expect(caught!.detail).toContain("child step");
  });
});

// ---------------------------------------------------------------------------
// Digest helpers
// ---------------------------------------------------------------------------

describe("sha256Digest", () => {
  it("canonical_json_sorts_keys", () => {
    const d1 = sha256Digest({ a: 1, b: 2 });
    const d2 = sha256Digest({ b: 2, a: 1 });
    expect(d1).toBe(d2);
  });

  it("canonical_json_ignores_trivia", () => {
    const a = sha256Digest({ a: [1, 2, 3] });
    const b = sha256Digest({ a: [1, 2, 3] });
    expect(a).toBe(b);
  });

  it("distinct_inputs_produce_distinct_digests", () => {
    expect(sha256Digest({ a: 1 })).not.toBe(sha256Digest({ a: 2 }));
  });

  it("digest_starts_with_sha256_prefix", () => {
    expect(sha256Digest({ x: 1 }).startsWith("sha256:")).toBe(true);
  });
});
