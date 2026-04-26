/**
 * Tests for the POST /anip/approval_grants HTTP endpoint (v0.23 §4.9).
 *
 * Mirrors anip-fastapi/tests/test_v023_approval_grants_endpoint.py.
 */
import { describe, it, expect } from "vitest";
import { Hono } from "hono";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  createANIPService,
  defineCapability,
  ANIPError,
} from "@anip-dev/service";
import { mountAnip } from "../src/routes.js";
import { InMemoryStorage } from "@anip-dev/server";
import type { CapabilityDeclaration, GrantPolicy } from "@anip-dev/core";

const API_KEY = "test-key-123";

function approvalRequiredCap() {
  const decl: CapabilityDeclaration = {
    name: "transfer_funds",
    description: "High-value transfer",
    contract_version: "1.0",
    inputs: [
      { name: "amount", type: "number", required: true, description: "amount" },
      {
        name: "to_account",
        type: "string",
        required: true,
        description: "to_account",
      },
    ],
    output: { type: "x", fields: ["transfer_id"] },
    side_effect: { type: "irreversible", rollback_window: "none" },
    minimum_scope: ["finance.write"],
    grant_policy: {
      allowed_grant_types: ["one_time", "session_bound"],
      default_grant_type: "one_time",
      expires_in_seconds: 900,
      max_uses: 1,
    } as GrantPolicy,
  } as unknown as CapabilityDeclaration;
  return defineCapability({
    declaration: decl,
    handler: async (_ctx, params) => {
      const amount = (params.amount as number) ?? 0;
      if (amount > 10000) {
        throw new ANIPError("approval_required", "needs approval", undefined, false, {
          preview: { amount, to_account: params.to_account },
        });
      }
      return { transfer_id: "tx" };
    },
  });
}

async function makeApp() {
  const dir = mkdtempSync(join(tmpdir(), "anip-v023-hono-keys-"));
  const keyPath = join(dir, "keys.json");
  const service = createANIPService({
    serviceId: "test-fin",
    capabilities: [approvalRequiredCap()],
    storage: new InMemoryStorage(),
    keyPath,
    authenticate: (bearer) =>
      bearer === API_KEY ? "human:samir@example.com" : null,
  });
  const app = new Hono();
  await mountAnip(app, service);
  return { app, service };
}

async function issueToken(
  app: Hono,
  opts: { scope: string[]; capability?: string; sessionId?: string },
): Promise<string> {
  const body: Record<string, unknown> = {
    subject: "human:samir@example.com",
    scope: opts.scope,
    capability: opts.capability ?? "transfer_funds",
    ttl_hours: 1,
  };
  if (opts.sessionId !== undefined) {
    body.session_id = opts.sessionId;
  }
  const r = await app.request("/anip/tokens", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${API_KEY}`,
    },
    body: JSON.stringify(body),
  });
  expect(r.status).toBe(200);
  const data = (await r.json()) as Record<string, unknown>;
  return data.token as string;
}

async function triggerApproval(app: Hono, token: string): Promise<string> {
  const r = await app.request("/anip/invoke/transfer_funds", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ parameters: { amount: 50000, to_account: "x" } }),
  });
  const body = (await r.json()) as Record<string, unknown>;
  const failure = body.failure as Record<string, unknown> | undefined;
  expect(failure).toBeDefined();
  expect(failure!.approval_required).toBeDefined();
  return ((failure!.approval_required as Record<string, unknown>)
    .approval_request_id) as string;
}

describe("Hono POST /anip/approval_grants", () => {
  it("happy_path_one_time", async () => {
    const { app } = await makeApp();
    const token = await issueToken(app, { scope: ["finance.write"] });
    const requestId = await triggerApproval(app, token);
    const approverToken = await issueToken(app, {
      scope: ["finance.write", "approver:*"],
    });
    const r = await app.request("/anip/approval_grants", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${approverToken}`,
      },
      body: JSON.stringify({
        approval_request_id: requestId,
        grant_type: "one_time",
      }),
    });
    expect(r.status).toBe(200);
    const grant = (await r.json()) as Record<string, unknown>;
    // SPEC.md §4.9: 200 response IS the signed ApprovalGrant (no wrapper).
    expect(grant.approval_request_id).toBe(requestId);
    expect(grant.grant_type).toBe("one_time");
    expect(grant.max_uses).toBe(1);
    expect(grant.use_count).toBe(0);
    expect(grant.signature).not.toBe("");
  });

  it("unauthorized_without_token", async () => {
    const { app } = await makeApp();
    const r = await app.request("/anip/approval_grants", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        approval_request_id: "apr_x",
        grant_type: "one_time",
      }),
    });
    expect(r.status).toBe(401);
  });

  it("approval_request_not_found", async () => {
    const { app } = await makeApp();
    const approverToken = await issueToken(app, {
      scope: ["finance.write", "approver:*"],
    });
    const r = await app.request("/anip/approval_grants", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${approverToken}`,
      },
      body: JSON.stringify({
        approval_request_id: "apr_does_not_exist",
        grant_type: "one_time",
      }),
    });
    expect(r.status).toBe(404);
    const body = (await r.json()) as Record<string, unknown>;
    expect((body.failure as Record<string, unknown>).type).toBe(
      "approval_request_not_found",
    );
  });

  it("approver_not_authorized", async () => {
    const { app } = await makeApp();
    const token = await issueToken(app, { scope: ["finance.write"] });
    const requestId = await triggerApproval(app, token);
    const nonApproverToken = await issueToken(app, {
      scope: ["finance.write"],
    });
    const r = await app.request("/anip/approval_grants", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${nonApproverToken}`,
      },
      body: JSON.stringify({
        approval_request_id: requestId,
        grant_type: "one_time",
      }),
    });
    expect(r.status).toBe(403);
    const body = (await r.json()) as Record<string, unknown>;
    expect((body.failure as Record<string, unknown>).type).toBe(
      "approver_not_authorized",
    );
  });

  it("approver_specific_capability_scope", async () => {
    // approver:transfer_funds suffices.
    const { app } = await makeApp();
    const token = await issueToken(app, { scope: ["finance.write"] });
    const requestId = await triggerApproval(app, token);
    const approverToken = await issueToken(app, {
      scope: ["finance.write", "approver:transfer_funds"],
    });
    const r = await app.request("/anip/approval_grants", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${approverToken}`,
      },
      body: JSON.stringify({
        approval_request_id: requestId,
        grant_type: "one_time",
      }),
    });
    expect(r.status).toBe(200);
  });

  it("approval_request_already_decided", async () => {
    const { app } = await makeApp();
    const token = await issueToken(app, { scope: ["finance.write"] });
    const requestId = await triggerApproval(app, token);
    const approverToken = await issueToken(app, {
      scope: ["finance.write", "approver:*"],
    });
    await app.request("/anip/approval_grants", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${approverToken}`,
      },
      body: JSON.stringify({
        approval_request_id: requestId,
        grant_type: "one_time",
      }),
    });
    const r = await app.request("/anip/approval_grants", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${approverToken}`,
      },
      body: JSON.stringify({
        approval_request_id: requestId,
        grant_type: "one_time",
      }),
    });
    const body = (await r.json()) as Record<string, unknown>;
    expect((body.failure as Record<string, unknown>).type).toBe(
      "approval_request_already_decided",
    );
  });

  it("invalid_body_returns_400", async () => {
    const { app } = await makeApp();
    const approverToken = await issueToken(app, {
      scope: ["finance.write", "approver:*"],
    });
    const r = await app.request("/anip/approval_grants", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${approverToken}`,
      },
      body: JSON.stringify({ approval_request_id: "apr_x" }), // missing grant_type
    });
    expect(r.status).toBe(400);
  });

  it("discovery_advertises_endpoint", async () => {
    const { app } = await makeApp();
    const r = await app.request("/.well-known/anip");
    expect(r.status).toBe(200);
    const body = (await r.json()) as Record<string, unknown>;
    const endpoints = (body.anip_discovery as Record<string, unknown>)
      .endpoints as Record<string, string>;
    expect(endpoints.approval_grants).toBe("/anip/approval_grants");
  });
});

describe("Hono /anip/invoke continuation with approval_grant", () => {
  it("invoke_with_grant_consumes_grant", async () => {
    const { app } = await makeApp();
    const token = await issueToken(app, { scope: ["finance.write"] });
    const requestId = await triggerApproval(app, token);
    const approverToken = await issueToken(app, {
      scope: ["finance.write", "approver:*"],
    });
    const grantResp = await app.request("/anip/approval_grants", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${approverToken}`,
      },
      body: JSON.stringify({
        approval_request_id: requestId,
        grant_type: "one_time",
      }),
    });
    const grantBody = (await grantResp.json()) as Record<string, unknown>;
    const grantId = grantBody.grant_id as string;

    await app.request("/anip/invoke/transfer_funds", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        parameters: { amount: 50000, to_account: "x" },
        approval_grant: grantId,
      }),
    });
    // Second use → grant_consumed.
    const r2 = await app.request("/anip/invoke/transfer_funds", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        parameters: { amount: 50000, to_account: "x" },
        approval_grant: grantId,
      }),
    });
    const body = (await r2.json()) as Record<string, unknown>;
    expect((body.failure as Record<string, unknown>).type).toBe(
      "grant_consumed",
    );
  });

  it("invoke_with_session_bound_grant_uses_token_session_id", async () => {
    // SPEC.md §4.8: session_id for session_bound validation is read from the
    // signed token, never from caller input.
    const { app } = await makeApp();
    const sessTokenA = await issueToken(app, {
      scope: ["finance.write"],
      sessionId: "sess-A",
    });
    const requestId = await triggerApproval(app, sessTokenA);
    const approverToken = await issueToken(app, {
      scope: ["finance.write", "approver:*"],
    });
    const grantResp = await app.request("/anip/approval_grants", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${approverToken}`,
      },
      body: JSON.stringify({
        approval_request_id: requestId,
        grant_type: "session_bound",
        session_id: "sess-A",
      }),
    });
    expect(grantResp.status).toBe(200);
    const grantBody = (await grantResp.json()) as Record<string, unknown>;
    const grantId = grantBody.grant_id as string;

    // Continuation with the SAME session-bound token → reservation succeeds.
    await app.request("/anip/invoke/transfer_funds", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${sessTokenA}`,
      },
      body: JSON.stringify({
        parameters: { amount: 50000, to_account: "x" },
        approval_grant: grantId,
      }),
    });

    // A fresh token bound to a DIFFERENT session must be rejected as
    // grant_session_invalid even if the body claims session-A.
    const wrongToken = await issueToken(app, {
      scope: ["finance.write"],
      sessionId: "sess-B",
    });
    const r2 = await app.request("/anip/invoke/transfer_funds", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${wrongToken}`,
      },
      body: JSON.stringify({
        parameters: { amount: 50000, to_account: "x" },
        approval_grant: grantId,
        session_id: "sess-A", // MUST be ignored — token is sess-B
      }),
    });
    const body = (await r2.json()) as Record<string, unknown>;
    expect((body.failure as Record<string, unknown>).type).toBe(
      "grant_session_invalid",
    );
  });

  it("invoke_with_unknown_grant_returns_grant_not_found", async () => {
    const { app } = await makeApp();
    const token = await issueToken(app, { scope: ["finance.write"] });
    const r = await app.request("/anip/invoke/transfer_funds", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        parameters: { amount: 5000, to_account: "x" },
        approval_grant: "grant_unknown",
      }),
    });
    const body = (await r.json()) as Record<string, unknown>;
    expect((body.failure as Record<string, unknown>).type).toBe(
      "grant_not_found",
    );
  });
});
