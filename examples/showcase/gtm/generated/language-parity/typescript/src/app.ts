import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { Hono } from "hono";
import { createANIPService } from "@anip-dev/service";
import { mountAnip } from "@anip-dev/hono";
import { generatedCapabilities, generatedCapabilityMetadata } from "./generated/capabilities.js";
import { runtimeTarget } from "./generated/runtime-target.js";
import { actorPolicyFromPrincipal } from "./runtime/actor.js";
import { approveRequest, listApprovals } from "./runtime/approval-store.js";

const __dirname = dirname(fileURLToPath(import.meta.url));

function readApiKeys(): Record<string, string> {
  const raw = process.env.ANIP_API_KEYS_JSON;
  if (!raw) return { "dev-admin-key": "human:local-developer" };
  try {
    return JSON.parse(raw) as Record<string, string>;
  } catch {
    return { "dev-admin-key": "human:local-developer" };
  }
}

const apiKeys = readApiKeys();
const serviceId = process.env.ANIP_SERVICE_ID ?? runtimeTarget.system_name;
const serviceFilter = process.env.GTM_SERVICE_FILTER?.trim();

const activeCapabilities = serviceFilter
  ? generatedCapabilities.filter((_, index) => generatedCapabilityMetadata[index]?.service_id === serviceFilter)
  : generatedCapabilities;

export const service = createANIPService({
  serviceId,
  capabilities: activeCapabilities,
  trust: (process.env.ANIP_TRUST_LEVEL as "signed" | "anchored") ?? "signed",
  keyPath: process.env.ANIP_KEY_PATH ?? resolve(__dirname, "../anip-keys"),
  storage: { type: process.env.ANIP_STORAGE === "sqlite" ? "sqlite" : "memory" },
  authenticate: async (bearer: string) => apiKeys[bearer] ?? null,
});

export const app = new Hono();

function actorForBearer(c: { req: { header(name: string): string | undefined } }) {
  const auth = c.req.header("authorization") || "";
  const bearer = auth.toLowerCase().startsWith("bearer ") ? auth.slice(7).trim() : "";
  const principal = apiKeys[bearer] || "";
  return actorPolicyFromPrincipal(principal);
}

app.get("/gtm/approvals", (c) => {
  const actor = actorForBearer(c);
  const status = c.req.query("status");
  const entries = listApprovals(status).filter((entry) => {
    if (actor.can_approve_followup || actor.can_approve_routing) return true;
    return entry.requested_by.actor_id === actor.actor_id;
  });
  return c.json({ entries });
});

app.post("/gtm/approvals/:approval_request_id/approve", (c) => {
  const actor = actorForBearer(c);
  if (!actor.can_approve_followup && !actor.can_approve_routing) {
    return c.json({ detail: "This actor cannot approve GTM actions" }, 403);
  }
  const approval = approveRequest(c.req.param("approval_request_id"), actor);
  if (!approval) return c.json({ detail: "Approval request not found" }, 404);
  return c.json({ approval });
});

const mounted = await mountAnip(app as unknown as Parameters<typeof mountAnip>[0], service, { healthEndpoint: true });
export const stop = mounted.stop;
