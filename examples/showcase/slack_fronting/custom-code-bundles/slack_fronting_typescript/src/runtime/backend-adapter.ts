import type { BackendInvocationPlan, GeneratedCapabilityRuntimeMetadata } from "../generated/runtime-target.js";

export type GeneratedBackendInvocationContext = {
  rootPrincipal?: string;
  approvalGrant?: string | null;
};

export interface GeneratedBackendAdapter {
  execute(capability: GeneratedCapabilityRuntimeMetadata, plan: BackendInvocationPlan, adapterInput: Record<string, unknown>, context: GeneratedBackendInvocationContext): Promise<Record<string, unknown>>;
}

function slackToken(): string | null {
  const token = process.env.SLACK_BOT_TOKEN?.trim() ?? "";
  return token || null;
}

function csvEnv(name: string): Set<string> {
  return new Set((process.env[name] ?? "").split(",").map((item) => item.trim()).filter(Boolean));
}

function channelAllowed(channelId: string): boolean {
  const blocked = csvEnv("ANIP_SLACK_BLOCKED_CHANNELS");
  const allowed = csvEnv("ANIP_SLACK_ALLOWED_CHANNELS");
  if (blocked.has(channelId)) return false;
  return allowed.size === 0 || allowed.has(channelId);
}

function boundedLimit(value: unknown, defaultValue = 20, maximum = 50): number {
  const parsed = Number.parseInt(String(value ?? ""), 10);
  const limit = Number.isFinite(parsed) ? parsed : defaultValue;
  return Math.max(1, Math.min(limit, maximum));
}

async function slackPost(path: string, token: string, body: Record<string, unknown>): Promise<Record<string, unknown>> {
  const form = new URLSearchParams();
  for (const [key, value] of Object.entries(body)) {
    if (value !== null && value !== undefined) form.set(key, String(value));
  }
  const response = await fetch(`https://slack.com/api/${path}`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: form,
  });
  const payload = await response.json() as Record<string, unknown>;
  if (!response.ok) return { ok: false, error: "slack_http_error", status: response.status, detail: payload };
  return payload;
}

function messageSummary(message: Record<string, unknown>): Record<string, unknown> {
  return {
    ts: message.ts,
    user: message.user ?? message.bot_id,
    text: message.text,
    thread_ts: message.thread_ts,
  };
}

function result(capability: GeneratedCapabilityRuntimeMetadata, plan: BackendInvocationPlan, status: string, extra: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    execution_status: status,
    capability_id: capability.capability_id,
    selected_backend: plan.selected_binding,
    semantic_input: plan.semantic_input,
    backend_input_contract: plan.backend_input_contract,
    ...extra,
  };
}

function restricted(capability: GeneratedCapabilityRuntimeMetadata, plan: BackendInvocationPlan, channelId: string): Record<string, unknown> {
  return result(capability, plan, "restricted", {
    channel_id: channelId,
    reason: "Slack channel is outside the configured ANIP channel policy.",
  });
}

function backendError(capability: GeneratedCapabilityRuntimeMetadata, plan: BackendInvocationPlan, payload: Record<string, unknown>): Record<string, unknown> {
  return result(capability, plan, "backend_error", { slack_error: payload });
}

function messageText(capability: GeneratedCapabilityRuntimeMetadata, params: Record<string, unknown>): string {
  if (capability.capability_id === "slack.incident_update.prepare") {
    return [
      `Incident ${params.incident_id}: ${params.status}`,
      String(params.summary ?? "").trim(),
      params.next_update_time ? `Next update: ${params.next_update_time}` : "",
    ].filter(Boolean).join("\n");
  }
  if (capability.capability_id === "slack.announcement.request") {
    const audience = String(params.audience ?? "").trim();
    return `${audience ? `[${audience}] ` : ""}${String(params.announcement ?? "").trim()}`;
  }
  return String(params.text ?? "").trim();
}

function mutationEnabled(context: GeneratedBackendInvocationContext): boolean {
  return process.env.ANIP_SLACK_ALLOW_SEND === "true" && Boolean(context.approvalGrant);
}

async function prepareOrSendMessage(capability: GeneratedCapabilityRuntimeMetadata, plan: BackendInvocationPlan, params: Record<string, unknown>, token: string | null, context: GeneratedBackendInvocationContext): Promise<Record<string, unknown>> {
  const channelId = String(params.channel_id ?? "").trim();
  if (!channelAllowed(channelId)) return restricted(capability, plan, channelId);
  const body: Record<string, unknown> = { channel: channelId, text: messageText(capability, params) };
  if (params.thread_ts) body.thread_ts = String(params.thread_ts);
  const preview = result(capability, plan, "prepared", {
    approval_required: true,
    mutation_performed: false,
    slack_action: "chat.postMessage",
    post_message_request: { method: "POST", path: "/api/chat.postMessage", body },
    note: "Prepared a Slack message payload. No Slack message was sent.",
  });
  if (!mutationEnabled(context)) return preview;
  if (!token) return { ...preview, execution_status: "backend_error", slack_error: { ok: false, error: "missing_slack_token" } };
  const posted = await slackPost("chat.postMessage", token, body);
  if (!posted.ok) return { ...preview, execution_status: "backend_error", slack_error: posted };
  return {
    ...preview,
    execution_status: "completed",
    approval_required: false,
    mutation_performed: true,
    posted_message: { channel: posted.channel, ts: posted.ts },
    approval_grant_id: context.approvalGrant,
    note: "Sent Slack message after the ANIP runtime validated and reserved an approval grant.",
  };
}

export function createDefaultBackendAdapter(): GeneratedBackendAdapter {
  return {
    async execute(capability, plan, adapterInput, context) {
      if (plan.unresolved_required_backend_inputs.length > 0) {
        return result(capability, plan, "backend_input_incomplete", { unresolved_required_backend_inputs: plan.unresolved_required_backend_inputs });
      }
      const token = slackToken();
      const params = adapterInput;
      switch (capability.capability_id) {
        case "slack.channel.read_context": {
          if (!token) return result(capability, plan, "backend_not_configured", { missing_env: "SLACK_BOT_TOKEN" });
          const channelId = String(params.channel_id ?? "").trim();
          if (!channelAllowed(channelId)) return restricted(capability, plan, channelId);
          const limit = boundedLimit(params.limit);
          const query = String(params.query ?? "").trim().toLowerCase();
          const payload = await slackPost("conversations.history", token, { channel: channelId, limit });
          if (!payload.ok) return backendError(capability, plan, payload);
          let messages = ((payload.messages as Record<string, unknown>[] | undefined) ?? []).map(messageSummary);
          if (query) messages = messages.filter((message) => String(message.text ?? "").toLowerCase().includes(query));
          messages = messages.slice(0, limit);
          return result(capability, plan, "completed", { result: { messages, count: messages.length, channel_id: channelId } });
        }
        case "slack.thread.summarize": {
          if (!token) return result(capability, plan, "backend_not_configured", { missing_env: "SLACK_BOT_TOKEN" });
          const channelId = String(params.channel_id ?? "").trim();
          if (!channelAllowed(channelId)) return restricted(capability, plan, channelId);
          const threadTs = String(params.thread_ts ?? "").trim();
          const limit = boundedLimit(params.limit, 50, 100);
          const payload = await slackPost("conversations.replies", token, { channel: channelId, ts: threadTs, limit });
          if (!payload.ok) return backendError(capability, plan, payload);
          const messages = ((payload.messages as Record<string, unknown>[] | undefined) ?? []).map(messageSummary);
          return result(capability, plan, "completed", { result: { messages, count: messages.length, channel_id: channelId, thread_ts: threadTs } });
        }
        case "slack.message.prepare":
        case "slack.incident_update.prepare":
        case "slack.announcement.request":
          return prepareOrSendMessage(capability, plan, params, token, context);
        default:
          return result(capability, plan, "backend_execution_stub", { note: "No Slack custom handler is registered for this capability." });
      }
    },
  };
}

export const backendAdapter = createDefaultBackendAdapter();
