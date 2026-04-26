import { describe, it, expect } from "vitest";
import {
  ANIPFailure,
  ApprovalGrant,
  ApprovalRequest,
  ApprovalRequiredMetadata,
  AuditPolicy,
  CapabilityDeclaration,
  Composition,
  CompositionStep,
  FailurePolicy,
  GrantPolicy,
  InvokeRequest,
  IssueApprovalGrantRequest,
  IssueApprovalGrantResponse,
  Resolution,
} from "../src/index.js";

const grantPolicy = () =>
  GrantPolicy.parse({
    allowed_grant_types: ["one_time", "session_bound"],
    default_grant_type: "one_time",
    expires_in_seconds: 900,
    max_uses: 1,
  });

const composedDecl = () =>
  CapabilityDeclaration.parse({
    name: "at_risk_account_enrichment_summary",
    description: "Composed example",
    inputs: [{ name: "quarter", type: "string", required: true, default: null, description: "" }],
    output: { type: "enriched", fields: ["count", "accounts"] },
    side_effect: { type: "read", rollback_window: "not_applicable" },
    minimum_scope: ["gtm.read"],
    kind: "composed",
    composition: {
      authority_boundary: "same_service",
      steps: [
        { id: "select", capability: "select_at_risk", empty_result_source: true, empty_result_path: null },
        { id: "enrich", capability: "enrich_accounts", empty_result_source: false, empty_result_path: null },
      ],
      input_mapping: {
        select: { quarter: "$.input.quarter" },
        enrich: { accounts: "$.steps.select.output.accounts" },
      },
      output_mapping: {
        count: "$.steps.enrich.output.count",
        accounts: "$.steps.enrich.output.accounts",
      },
      empty_result_policy: "return_success_no_results",
      empty_result_output: { count: 0, accounts: [] },
      failure_policy: {
        child_clarification: "propagate",
        child_denial: "propagate",
        child_approval_required: "propagate",
        child_error: "fail_parent",
      },
      audit_policy: { record_child_invocations: true, parent_task_lineage: true },
    },
  });

const grant = () =>
  ApprovalGrant.parse({
    grant_id: "grant_test",
    approval_request_id: "apr_test",
    grant_type: "one_time",
    capability: "finance.transfer_funds",
    scope: ["finance.write"],
    approved_parameters_digest: "sha256:params",
    preview_digest: "sha256:preview",
    requester: { principal: "u1" },
    approver: { principal: "u2" },
    issued_at: "2026-01-01T00:00:00Z",
    expires_at: "2026-01-01T00:15:00Z",
    max_uses: 1,
    use_count: 0,
    session_id: null,
    signature: "sig",
  });

describe("v0.23 — CapabilityKind", () => {
  it("atomic is the default kind", () => {
    const d = CapabilityDeclaration.parse({
      name: "cap",
      description: "d",
      inputs: [],
      output: { type: "x", fields: [] },
      side_effect: { type: "read", rollback_window: "not_applicable" },
      minimum_scope: ["s"],
    });
    expect(d.kind).toBe("atomic");
    expect(d.composition).toBeNull();
  });

  it("composed declaration round-trips", () => {
    const d = composedDecl();
    const data = JSON.parse(JSON.stringify(d));
    const d2 = CapabilityDeclaration.parse(data);
    expect(d2.kind).toBe("composed");
    expect(d2.composition).not.toBeNull();
    expect(d2.composition!.steps[0].empty_result_source).toBe(true);
    expect(d2.composition!.steps[1].empty_result_source).toBe(false);
    expect(d2.composition!.empty_result_policy).toBe("return_success_no_results");
    expect(d2.composition!.empty_result_output).toEqual({ count: 0, accounts: [] });
    expect(d2.composition!.failure_policy.child_error).toBe("fail_parent");
  });

  it("CompositionStep defaults", () => {
    const s = CompositionStep.parse({ id: "s1", capability: "c1" });
    expect(s.empty_result_source).toBe(false);
    expect(s.empty_result_path).toBeNull();
  });
});

describe("v0.23 — ApprovalRequest lifecycle", () => {
  const baseFields = {
    approval_request_id: "apr_test",
    capability: "cap",
    scope: ["s"],
    requester: { principal: "u1" },
    parent_invocation_id: null,
    preview: { k: "v" },
    preview_digest: "sha256:preview",
    requested_parameters: { k: "v" },
    requested_parameters_digest: "sha256:params",
    grant_policy: grantPolicy(),
    created_at: "2026-01-01T00:00:00Z",
    expires_at: "2026-01-01T00:15:00Z",
  };

  it("pending status round-trips", () => {
    const r = ApprovalRequest.parse({
      ...baseFields,
      status: "pending",
      approver: null,
      decided_at: null,
    });
    expect(r.status).toBe("pending");
    expect(r.approver).toBeNull();
    expect(r.decided_at).toBeNull();
  });

  it("approved status round-trips", () => {
    const r = ApprovalRequest.parse({
      ...baseFields,
      status: "approved",
      approver: { principal: "u2" },
      decided_at: "2026-01-01T00:01:00Z",
    });
    expect(r.status).toBe("approved");
    expect(r.approver).toEqual({ principal: "u2" });
  });

  it("expired status round-trips with null approver", () => {
    const r = ApprovalRequest.parse({
      ...baseFields,
      status: "expired",
      approver: null,
      decided_at: "2026-01-01T00:15:01Z",
    });
    expect(r.status).toBe("expired");
    expect(r.approver).toBeNull();
    expect(r.decided_at).toBeTruthy();
  });
});

describe("v0.23 — ApprovalGrant", () => {
  it("one_time grant round-trips", () => {
    const g = grant();
    const g2 = ApprovalGrant.parse(JSON.parse(JSON.stringify(g)));
    expect(g2.grant_type).toBe("one_time");
    expect(g2.session_id).toBeNull();
    expect(g2.use_count).toBe(0);
  });

  it("session_bound grant round-trips", () => {
    const g = ApprovalGrant.parse({
      ...grant(),
      grant_type: "session_bound",
      session_id: "sess_1",
      max_uses: 5,
    });
    expect(g.grant_type).toBe("session_bound");
    expect(g.session_id).toBe("sess_1");
    expect(g.max_uses).toBe(5);
  });

  it("approval_request_id is required and present after round-trip", () => {
    const g = grant();
    const data = JSON.parse(JSON.stringify(g));
    const g2 = ApprovalGrant.parse(data);
    expect(g2.approval_request_id).toBe("apr_test");
  });
});

describe("v0.23 — ANIPFailure with approval_required", () => {
  it("attaches metadata for approval_required failures", () => {
    const f = ANIPFailure.parse({
      type: "approval_required",
      detail: "needs approval",
      resolution: Resolution.parse({
        action: "contact_service_owner",
        recovery_class: "terminal",
      }),
      retry: false,
      approval_required: ApprovalRequiredMetadata.parse({
        approval_request_id: "apr_test",
        preview_digest: "sha256:preview",
        requested_parameters_digest: "sha256:params",
        grant_policy: grantPolicy(),
      }),
    });
    expect(f.approval_required).not.toBeNull();
    expect(f.approval_required!.approval_request_id).toBe("apr_test");
  });

  it("approval_required is null for non-approval failures", () => {
    const f = ANIPFailure.parse({
      type: "budget_exceeded",
      detail: "too expensive",
      resolution: { action: "request_budget_increase", recovery_class: "redelegation_then_retry" },
    });
    expect(f.approval_required).toBeNull();
  });
});

describe("v0.23 — InvokeRequest with approval_grant", () => {
  it("approval_grant defaults to null", () => {
    const ir = InvokeRequest.parse({ token: "jwt" });
    expect(ir.approval_grant).toBeNull();
  });

  it("approval_grant round-trips", () => {
    const ir = InvokeRequest.parse({ token: "jwt", approval_grant: "grant_test" });
    expect(ir.approval_grant).toBe("grant_test");
  });
});

describe("v0.23 — IssueApprovalGrant request/response", () => {
  it("request round-trips", () => {
    const req = IssueApprovalGrantRequest.parse({
      approval_request_id: "apr_test",
      grant_type: "one_time",
      expires_in_seconds: 600,
      max_uses: 1,
    });
    expect(req.grant_type).toBe("one_time");
    expect(req.session_id).toBeNull();
  });

  it("response wraps a grant", () => {
    const resp = IssueApprovalGrantResponse.parse({ grant: grant() });
    expect(resp.grant.grant_id).toBe("grant_test");
  });

  it("session_bound issuance requires session_id", () => {
    expect(() =>
      IssueApprovalGrantRequest.parse({
        approval_request_id: "apr_test",
        grant_type: "session_bound",
      }),
    ).toThrow();
  });

  it("one_time issuance rejects session_id", () => {
    expect(() =>
      IssueApprovalGrantRequest.parse({
        approval_request_id: "apr_test",
        grant_type: "one_time",
        session_id: "sess_1",
      }),
    ).toThrow();
  });

  it("one_time issuance rejects max_uses != 1", () => {
    expect(() =>
      IssueApprovalGrantRequest.parse({
        approval_request_id: "apr_test",
        grant_type: "one_time",
        max_uses: 5,
      }),
    ).toThrow();
  });
});

// --- Negative validators (security invariants) ---

describe("v0.23 — ApprovalGrant invariants", () => {
  const baseGrant = () => ({
    grant_id: "g1",
    approval_request_id: "apr_1",
    capability: "cap",
    scope: ["s"],
    approved_parameters_digest: "d1",
    preview_digest: "d2",
    requester: { principal: "u1" },
    approver: { principal: "u2" },
    issued_at: "2026-01-01T00:00:00Z",
    expires_at: "2026-01-01T00:15:00Z",
    use_count: 0,
    signature: "sig",
  });

  it("rejects one_time with max_uses > 1", () => {
    expect(() =>
      ApprovalGrant.parse({
        ...baseGrant(),
        grant_type: "one_time",
        max_uses: 5,
        session_id: null,
      }),
    ).toThrow();
  });

  it("rejects one_time with non-null session_id", () => {
    expect(() =>
      ApprovalGrant.parse({
        ...baseGrant(),
        grant_type: "one_time",
        max_uses: 1,
        session_id: "sess_1",
      }),
    ).toThrow();
  });

  it("rejects session_bound without session_id", () => {
    expect(() =>
      ApprovalGrant.parse({
        ...baseGrant(),
        grant_type: "session_bound",
        max_uses: 5,
        session_id: null,
      }),
    ).toThrow();
  });

  it("accepts session_bound with non-null session_id", () => {
    const g = ApprovalGrant.parse({
      ...baseGrant(),
      grant_type: "session_bound",
      max_uses: 5,
      session_id: "sess_1",
    });
    expect(g.session_id).toBe("sess_1");
  });
});

describe("v0.23 — ApprovalRequest invariants", () => {
  const baseFields = () => ({
    approval_request_id: "apr_1",
    capability: "cap",
    scope: ["s"],
    requester: { principal: "u1" },
    parent_invocation_id: null,
    preview: { k: "v" },
    preview_digest: "d2",
    requested_parameters: { k: "v" },
    requested_parameters_digest: "d1",
    grant_policy: grantPolicy(),
    created_at: "2026-01-01T00:00:00Z",
    expires_at: "2026-01-01T00:15:00Z",
  });

  it("rejects pending with approver", () => {
    expect(() =>
      ApprovalRequest.parse({
        ...baseFields(),
        status: "pending",
        approver: { principal: "u2" },
        decided_at: null,
      }),
    ).toThrow();
  });

  it("rejects pending with decided_at", () => {
    expect(() =>
      ApprovalRequest.parse({
        ...baseFields(),
        status: "pending",
        approver: null,
        decided_at: "2026-01-01T00:01:00Z",
      }),
    ).toThrow();
  });

  it("rejects approved without approver", () => {
    expect(() =>
      ApprovalRequest.parse({
        ...baseFields(),
        status: "approved",
        approver: null,
        decided_at: "2026-01-01T00:01:00Z",
      }),
    ).toThrow();
  });

  it("rejects expired with non-null approver", () => {
    expect(() =>
      ApprovalRequest.parse({
        ...baseFields(),
        status: "expired",
        approver: { principal: "u2" },
        decided_at: "2026-01-01T00:15:01Z",
      }),
    ).toThrow();
  });

  it("rejects expired without decided_at", () => {
    expect(() =>
      ApprovalRequest.parse({
        ...baseFields(),
        status: "expired",
        approver: null,
        decided_at: null,
      }),
    ).toThrow();
  });
});

describe("v0.23 — ANIPFailure approval_required invariants", () => {
  const baseResolution = () =>
    Resolution.parse({ action: "contact_service_owner", recovery_class: "terminal" });

  it("rejects approval_required without metadata", () => {
    expect(() =>
      ANIPFailure.parse({
        type: "approval_required",
        detail: "needs approval",
        resolution: baseResolution(),
      }),
    ).toThrow();
  });

  it("rejects non-approval failure with metadata", () => {
    expect(() =>
      ANIPFailure.parse({
        type: "budget_exceeded",
        detail: "too expensive",
        resolution: baseResolution(),
        approval_required: {
          approval_request_id: "apr_1",
          preview_digest: "d2",
          requested_parameters_digest: "d1",
          grant_policy: grantPolicy(),
        },
      }),
    ).toThrow();
  });
});

describe("v0.23 — GrantPolicy invariants", () => {
  it("rejects default_grant_type not in allowed_grant_types", () => {
    expect(() =>
      GrantPolicy.parse({
        allowed_grant_types: ["one_time"],
        default_grant_type: "session_bound",
        expires_in_seconds: 900,
        max_uses: 1,
      }),
    ).toThrow();
  });

  it("accepts default_grant_type when listed in allowed_grant_types", () => {
    const p = GrantPolicy.parse({
      allowed_grant_types: ["one_time", "session_bound"],
      default_grant_type: "session_bound",
      expires_in_seconds: 900,
      max_uses: 1,
    });
    expect(p.default_grant_type).toBe("session_bound");
  });
});

describe("v0.23 — CapabilityDeclaration kind/composition invariants", () => {
  const baseFields = () => ({
    name: "cap",
    description: "d",
    inputs: [],
    output: { type: "x", fields: [] },
    side_effect: { type: "read", rollback_window: "not_applicable" },
    minimum_scope: ["s"],
  });

  it("rejects composed without composition", () => {
    expect(() =>
      CapabilityDeclaration.parse({
        ...baseFields(),
        kind: "composed",
      }),
    ).toThrow();
  });

  it("rejects atomic with composition", () => {
    const comp = composedDecl().composition;
    expect(() =>
      CapabilityDeclaration.parse({
        ...baseFields(),
        kind: "atomic",
        composition: comp,
      }),
    ).toThrow();
  });

  it("rejects omitted-kind with composition (defaults to atomic)", () => {
    const comp = composedDecl().composition;
    expect(() =>
      CapabilityDeclaration.parse({
        ...baseFields(),
        composition: comp,
      }),
    ).toThrow();
  });
});
