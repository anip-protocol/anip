/**
 * Tests for the POST /anip/approval_grants HTTP endpoint (v0.23 §4.9).
 *
 * Mirrors anip-fastapi/tests/test_v023_approval_grants_endpoint.py.
 */
import { describe, it, expect, afterEach } from "vitest";
import express from "express";
import request from "supertest";
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
  const dir = mkdtempSync(join(tmpdir(), "anip-v023-express-keys-"));
  const keyPath = join(dir, "keys.json");
  const app = express();
  const service = createANIPService({
    serviceId: "test-fin",
    capabilities: [approvalRequiredCap()],
    storage: new InMemoryStorage(),
    keyPath,
    authenticate: (bearer) =>
      bearer === API_KEY ? "human:samir@example.com" : null,
  });
  const { stop } = await mountAnip(app, service);
  return { app, stop };
}

async function issueToken(
  app: express.Express,
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
  const res = await request(app)
    .post("/anip/tokens")
    .set("Authorization", `Bearer ${API_KEY}`)
    .send(body);
  expect(res.status).toBe(200);
  return res.body.token as string;
}

async function triggerApproval(
  app: express.Express,
  token: string,
): Promise<string> {
  const res = await request(app)
    .post("/anip/invoke/transfer_funds")
    .set("Authorization", `Bearer ${token}`)
    .send({ parameters: { amount: 50000, to_account: "x" } });
  const failure = res.body.failure as Record<string, unknown> | undefined;
  expect(failure).toBeDefined();
  expect(failure!.approval_required).toBeDefined();
  return ((failure!.approval_required as Record<string, unknown>)
    .approval_request_id) as string;
}

describe("Express POST /anip/approval_grants", () => {
  let stopFn: (() => void) | undefined;
  afterEach(() => {
    stopFn?.();
    stopFn = undefined;
  });

  it("happy_path_one_time", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;
    const token = await issueToken(app, { scope: ["finance.write"] });
    const requestId = await triggerApproval(app, token);
    const approverToken = await issueToken(app, {
      scope: ["finance.write", "approver:*"],
    });
    const r = await request(app)
      .post("/anip/approval_grants")
      .set("Authorization", `Bearer ${approverToken}`)
      .send({ approval_request_id: requestId, grant_type: "one_time" });
    expect(r.status).toBe(200);
    expect(r.body.approval_request_id).toBe(requestId);
    expect(r.body.grant_type).toBe("one_time");
    expect(r.body.max_uses).toBe(1);
    expect(r.body.use_count).toBe(0);
    expect(r.body.signature).not.toBe("");
  });

  it("unauthorized_without_token", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;
    const r = await request(app)
      .post("/anip/approval_grants")
      .send({ approval_request_id: "apr_x", grant_type: "one_time" });
    expect(r.status).toBe(401);
  });

  it("approval_request_not_found", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;
    const approverToken = await issueToken(app, {
      scope: ["finance.write", "approver:*"],
    });
    const r = await request(app)
      .post("/anip/approval_grants")
      .set("Authorization", `Bearer ${approverToken}`)
      .send({
        approval_request_id: "apr_does_not_exist",
        grant_type: "one_time",
      });
    expect(r.status).toBe(404);
    expect(r.body.failure.type).toBe("approval_request_not_found");
  });

  it("approver_not_authorized", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;
    const token = await issueToken(app, { scope: ["finance.write"] });
    const requestId = await triggerApproval(app, token);
    const nonApproverToken = await issueToken(app, {
      scope: ["finance.write"],
    });
    const r = await request(app)
      .post("/anip/approval_grants")
      .set("Authorization", `Bearer ${nonApproverToken}`)
      .send({ approval_request_id: requestId, grant_type: "one_time" });
    expect(r.status).toBe(403);
    expect(r.body.failure.type).toBe("approver_not_authorized");
  });

  it("approver_specific_capability_scope", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;
    const token = await issueToken(app, { scope: ["finance.write"] });
    const requestId = await triggerApproval(app, token);
    const approverToken = await issueToken(app, {
      scope: ["finance.write", "approver:transfer_funds"],
    });
    const r = await request(app)
      .post("/anip/approval_grants")
      .set("Authorization", `Bearer ${approverToken}`)
      .send({ approval_request_id: requestId, grant_type: "one_time" });
    expect(r.status).toBe(200);
  });

  it("approval_request_already_decided", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;
    const token = await issueToken(app, { scope: ["finance.write"] });
    const requestId = await triggerApproval(app, token);
    const approverToken = await issueToken(app, {
      scope: ["finance.write", "approver:*"],
    });
    await request(app)
      .post("/anip/approval_grants")
      .set("Authorization", `Bearer ${approverToken}`)
      .send({ approval_request_id: requestId, grant_type: "one_time" });
    const r = await request(app)
      .post("/anip/approval_grants")
      .set("Authorization", `Bearer ${approverToken}`)
      .send({ approval_request_id: requestId, grant_type: "one_time" });
    expect(r.body.failure.type).toBe("approval_request_already_decided");
  });

  it("invalid_body_returns_400", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;
    const approverToken = await issueToken(app, {
      scope: ["finance.write", "approver:*"],
    });
    const r = await request(app)
      .post("/anip/approval_grants")
      .set("Authorization", `Bearer ${approverToken}`)
      .send({ approval_request_id: "apr_x" }); // missing grant_type
    expect(r.status).toBe(400);
  });

  it("discovery_advertises_endpoint", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;
    const r = await request(app).get("/.well-known/anip");
    expect(r.status).toBe(200);
    expect(r.body.anip_discovery.endpoints.approval_grants).toBe(
      "/anip/approval_grants",
    );
  });
});

describe("Express /anip/invoke continuation with approval_grant", () => {
  let stopFn: (() => void) | undefined;
  afterEach(() => {
    stopFn?.();
    stopFn = undefined;
  });

  it("invoke_with_grant_consumes_grant", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;
    const token = await issueToken(app, { scope: ["finance.write"] });
    const requestId = await triggerApproval(app, token);
    const approverToken = await issueToken(app, {
      scope: ["finance.write", "approver:*"],
    });
    const grantResp = await request(app)
      .post("/anip/approval_grants")
      .set("Authorization", `Bearer ${approverToken}`)
      .send({ approval_request_id: requestId, grant_type: "one_time" });
    const grantId = grantResp.body.grant_id as string;

    await request(app)
      .post("/anip/invoke/transfer_funds")
      .set("Authorization", `Bearer ${token}`)
      .send({
        parameters: { amount: 50000, to_account: "x" },
        approval_grant: grantId,
      });
    const r2 = await request(app)
      .post("/anip/invoke/transfer_funds")
      .set("Authorization", `Bearer ${token}`)
      .send({
        parameters: { amount: 50000, to_account: "x" },
        approval_grant: grantId,
      });
    expect(r2.body.failure.type).toBe("grant_consumed");
  });

  it("invoke_with_session_bound_grant_uses_token_session_id", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;
    const sessTokenA = await issueToken(app, {
      scope: ["finance.write"],
      sessionId: "sess-A",
    });
    const requestId = await triggerApproval(app, sessTokenA);
    const approverToken = await issueToken(app, {
      scope: ["finance.write", "approver:*"],
    });
    const grantResp = await request(app)
      .post("/anip/approval_grants")
      .set("Authorization", `Bearer ${approverToken}`)
      .send({
        approval_request_id: requestId,
        grant_type: "session_bound",
        session_id: "sess-A",
      });
    expect(grantResp.status).toBe(200);
    const grantId = grantResp.body.grant_id as string;

    await request(app)
      .post("/anip/invoke/transfer_funds")
      .set("Authorization", `Bearer ${sessTokenA}`)
      .send({
        parameters: { amount: 50000, to_account: "x" },
        approval_grant: grantId,
      });

    const wrongToken = await issueToken(app, {
      scope: ["finance.write"],
      sessionId: "sess-B",
    });
    const r2 = await request(app)
      .post("/anip/invoke/transfer_funds")
      .set("Authorization", `Bearer ${wrongToken}`)
      .send({
        parameters: { amount: 50000, to_account: "x" },
        approval_grant: grantId,
        session_id: "sess-A", // MUST be ignored
      });
    expect(r2.body.failure.type).toBe("grant_session_invalid");
  });

  it("invoke_with_unknown_grant_returns_grant_not_found", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;
    const token = await issueToken(app, { scope: ["finance.write"] });
    const r = await request(app)
      .post("/anip/invoke/transfer_funds")
      .set("Authorization", `Bearer ${token}`)
      .send({
        parameters: { amount: 5000, to_account: "x" },
        approval_grant: "grant_unknown",
      });
    expect(r.body.failure.type).toBe("grant_not_found");
  });
});
