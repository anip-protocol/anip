/**
 * One HTTP status per failure type (SPEC.md §6.3 "HTTP Status Codes").
 */
import { describe, expect, it } from "vitest";
import {
  DEFAULT_FAILURE_STATUS_CODE,
  FAILURE_STATUS_CODES,
  failureStatusCode,
} from "../src/index.js";

// The table of SPEC.md §6.3, row by row.
const TABLE: Record<number, string[]> = {
  400: [
    "invalid_parameters",
    "streaming_not_supported",
    "approval_required",
    "grant_not_found",
    "grant_capability_mismatch",
    "grant_scope_mismatch",
    "grant_param_drift",
    "grant_session_invalid",
    "grant_type_not_allowed_by_policy",
  ],
  401: ["authentication_required", "invalid_token", "token_expired", "token_not_registered"],
  403: [
    "scope_insufficient",
    "insufficient_authority",
    "purpose_mismatch",
    "scope_escalation",
    "constraint_escalation",
    "broken_delegation_chain",
    "delegation_depth_exceeded",
    "parent_token_expired",
    "budget_exceeded",
    "budget_currency_mismatch",
    "budget_not_enforceable",
    "binding_missing",
    "binding_stale",
    "control_requirement_unsatisfied",
    "approver_not_authorized",
    "grant_requester_mismatch",
  ],
  404: ["unknown_capability", "not_found", "approval_request_not_found"],
  409: [
    "grant_consumed",
    "grant_expired",
    "approval_request_already_decided",
    "approval_request_expired",
    "concurrent_lock",
    "concurrent_request_rejected",
    "unavailable",
  ],
  500: ["internal_error"],
  503: ["service_unavailable"],
};

describe("failureStatusCode", () => {
  for (const [status, types] of Object.entries(TABLE)) {
    for (const type of types) {
      it(`${type} is ${status}`, () => {
        expect(failureStatusCode(type)).toBe(Number(status));
      });
    }
  }

  it("has exactly the rows of the table", () => {
    const listed = Object.values(TABLE).flat().sort();
    expect(Object.keys(FAILURE_STATUS_CODES).sort()).toEqual(listed);
    expect(new Set(listed).size).toBe(listed.length);
  });

  it("is 400 for a type the table does not list", () => {
    expect(DEFAULT_FAILURE_STATUS_CODE).toBe(400);
    for (const type of ["capability_unavailable", "handler_defined_failure", "", "INTERNAL_ERROR"]) {
      expect(failureStatusCode(type)).toBe(400);
    }
    expect(failureStatusCode(undefined)).toBe(400);
    expect(failureStatusCode(null)).toBe(400);
  });

  it("is 400 for a type that names a member of Object.prototype", () => {
    for (const type of ["constructor", "toString", "hasOwnProperty", "__proto__"]) {
      expect(failureStatusCode(type)).toBe(400);
    }
  });
});
