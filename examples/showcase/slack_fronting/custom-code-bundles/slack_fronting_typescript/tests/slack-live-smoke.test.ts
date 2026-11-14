import { describe, expect, it } from "vitest";
import type { InvocationContext } from "@anip-dev/service";
import { backendAdapter } from "../src/runtime/backend-adapter.js";
import { generatedCapabilities } from "../src/generated/capabilities.js";
import { generatedCapabilityMetadata, type BackendInvocationPlan, type GeneratedCapabilityRuntimeMetadata } from "../src/generated/runtime-target.js";

const configured = Boolean(process.env.SLACK_BOT_TOKEN && process.env.SLACK_CHANNEL_ID);

// Package 0.2.1 binds every capability to the collaborator actor
// (allow_with_limits) and requires approval nowhere.
const COLLABORATOR = "human:local-dev|actor_id=collaborator";
const NO_BINDING_DETAIL = "No runtime policy binding matches the current actor for this capability.";

function capability(id: string): GeneratedCapabilityRuntimeMetadata {
  const found = generatedCapabilityMetadata.find((item) => item.capability_id === id);
  if (!found) throw new Error(`Missing capability ${id}`);
  return found;
}

function plan(parameters: Record<string, unknown>): BackendInvocationPlan {
  return {
    selected_binding: null,
    semantic_input: parameters,
    adapter_input: parameters,
    backend_input_contract: { mode: "explicit", required: [], optional: [] },
    unresolved_required_backend_inputs: [],
  };
}

async function slackPost(path: string, body: Record<string, unknown>): Promise<Record<string, unknown>> {
  const form = new URLSearchParams();
  for (const [key, value] of Object.entries(body)) form.set(key, String(value));
  const response = await fetch(`https://slack.com/api/${path}`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${process.env.SLACK_BOT_TOKEN}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: form,
  });
  expect(response.ok).toBe(true);
  return await response.json() as Record<string, unknown>;
}

describe.skipIf(!configured)("Slack live backend adapter", () => {
  it("executes bounded reads and prepares governed previews without mutation", async () => {
    const channelId = process.env.SLACK_CHANNEL_ID!;
    process.env.ANIP_SLACK_ALLOWED_CHANNELS ??= channelId;
    const history = await slackPost("conversations.history", { channel: channelId, limit: 1 });
    expect(history.ok).toBe(true);
    const messages = (history.messages ?? []) as Record<string, unknown>[];
    const threadTs = messages.length > 0 ? String(messages[0].thread_ts ?? messages[0].ts) : null;

    const context = await backendAdapter.execute(capability("slack.channel.read_context"), plan({ channel_id: channelId, limit: 5 }), { channel_id: channelId, limit: 5 }, {});
    expect(context.execution_status).toBe("completed");

    if (threadTs) {
      const thread = await backendAdapter.execute(capability("slack.thread.summarize"), plan({ channel_id: channelId, thread_ts: threadTs, limit: 10 }), { channel_id: channelId, thread_ts: threadTs, limit: 10 }, {});
      expect(thread.execution_status).toBe("completed");
    }

    const previews: Array<[string, Record<string, unknown>]> = [
      ["slack.message.prepare", { channel_id: channelId, text: "ANIP Slack TypeScript smoke preview" }],
      ["slack.incident_update.prepare", { channel_id: channelId, incident_id: "INC-123", status: "monitoring", summary: "Preview only", next_update_time: "in 30 minutes" }],
      ["slack.announcement.request", { channel_id: channelId, announcement: "Preview governed announcement only", audience: "internal" }],
    ];
    for (const [id, parameters] of previews) {
      const result = await backendAdapter.execute(capability(id), plan(parameters), parameters, {});
      expect(result.execution_status).toBe("prepared");
      expect(result.mutation_performed).toBe(false);
    }

    if (process.env.ANIP_SLACK_ALLOW_SEND === "true") {
      const sendParameters = { channel_id: channelId, text: `ANIP approved Slack TypeScript post at ${Date.now()}` };
      const sent = await backendAdapter.execute(capability("slack.message.prepare"), plan(sendParameters), sendParameters, { approvalGrant: "grant_live_typescript_smoke" });
      expect(sent.execution_status).toBe("completed");
      expect(sent.mutation_performed).toBe(true);
      expect((sent.posted_message as Record<string, unknown>).ts).toBeTruthy();
    }
  });

  it("routes approved sends through the generated handler", async () => {
    const channelId = process.env.SLACK_CHANNEL_ID!;
    process.env.ANIP_SLACK_ALLOWED_CHANNELS ??= channelId;
    const capabilityDef = generatedCapabilities.find((item) => item.declaration.name === "slack.announcement.request");
    expect(capabilityDef).toBeTruthy();
    const parameters = {
      channel_id: channelId,
      announcement: `ANIP approved Slack TypeScript generated handler post at ${Date.now()}`,
      audience: "test",
    };

    // Without a grant the collaborator gets a preview; nothing is posted.
    const preview = await capabilityDef!.handler(testContext(COLLABORATOR, null), parameters);
    expect(preview.execution_status).toBe("prepared");
    expect(preview.mutation_performed).toBe(false);

    if (process.env.ANIP_SLACK_ALLOW_SEND === "true") {
      // The runtime sets approvalGrant only after validating the grant.
      const sent = await capabilityDef!.handler(testContext(COLLABORATOR, "grant_live_typescript_handler_smoke"), parameters);
      expect(sent.execution_status).toBe("completed");
      expect(sent.mutation_performed).toBe(true);
      expect((sent.posted_message as Record<string, unknown>).ts).toBeTruthy();
    }
  });
});

describe("Slack generated handler policy", () => {
  // The generated policy refuses a principal no binding selects before the
  // backend adapter runs, so this needs no Slack credentials.
  it("refuses principals no binding selects", async () => {
    const capabilityDef = generatedCapabilities.find((item) => item.declaration.name === "slack.announcement.request");
    expect(capabilityDef).toBeTruthy();
    const parameters = { channel_id: "C0SMOKE01", announcement: "Refused", audience: "test" };
    for (const principal of ["human:local-dev", "human:local-dev|actor_id=slack_requester"]) {
      await expect(capabilityDef!.handler(testContext(principal, "grant_live_typescript_handler_smoke"), parameters)).rejects.toMatchObject({
        errorType: "denied",
        detail: NO_BINDING_DETAIL,
      });
    }
  });
});

function testContext(rootPrincipal: string, approvalGrant: string | null): InvocationContext {
  return {
    token: {} as InvocationContext["token"],
    rootPrincipal,
    subject: "agent:slack-live-smoke",
    scopes: ["slack.announcement.request"],
    delegationChain: [],
    invocationId: "inv-test",
    clientReferenceId: null,
    taskId: null,
    parentInvocationId: null,
    upstreamService: null,
    approvalGrant,
    setCostActual: () => {},
    emitProgress: async () => {},
  };
}
