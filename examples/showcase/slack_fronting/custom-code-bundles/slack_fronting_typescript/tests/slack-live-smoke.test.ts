import { describe, expect, it } from "vitest";
import type { InvocationContext } from "@anip-dev/service";
import { backendAdapter } from "../src/runtime/backend-adapter.js";
import { generatedCapabilities } from "../src/generated/capabilities.js";
import { generatedCapabilityMetadata, type BackendInvocationPlan, type GeneratedCapabilityRuntimeMetadata } from "../src/generated/runtime-target.js";

const configured = Boolean(process.env.SLACK_BOT_TOKEN && process.env.SLACK_CHANNEL_ID);

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

    await expect(capabilityDef!.handler(testContext(null), parameters)).rejects.toMatchObject({
      errorType: "approval_required",
    });

    if (process.env.ANIP_SLACK_ALLOW_SEND === "true") {
      const sent = await capabilityDef!.handler(testContext("grant_live_typescript_handler_smoke"), parameters);
      expect(sent.execution_status).toBe("completed");
      expect(sent.mutation_performed).toBe(true);
      expect((sent.posted_message as Record<string, unknown>).ts).toBeTruthy();
    }
  });
});

function testContext(approvalGrant: string | null): InvocationContext {
  return {
    token: {} as InvocationContext["token"],
    rootPrincipal: "human:local-dev|actor_id=slack_requester",
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
