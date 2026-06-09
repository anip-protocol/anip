import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { Hono } from "hono";
import { createANIPService } from "@anip-dev/service";
import { mountAnip } from "@anip-dev/hono";
import { generatedCapabilities, generatedCapabilityMetadata } from "./generated/capabilities.js";
import { runtimeTarget } from "./generated/runtime-target.js";

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

function readServiceMap(): Record<string, string> {
  const raw = process.env.GTM_BACKEND_SERVICES_JSON;
  const defaults = {
    "gtm-pipeline-service": "http://127.0.0.1:4100",
    "gtm-prioritization-service": "http://127.0.0.1:4102",
  };
  if (!raw) return defaults;
  try {
    return { ...defaults, ...(JSON.parse(raw) as Record<string, string>) };
  } catch {
    return defaults;
  }
}

async function proxyJson(serviceId: string, path: string, request: Request): Promise<Response> {
  const serviceUrl = readServiceMap()[serviceId];
  if (!serviceUrl) {
    return Response.json({ detail: `No downstream GTM service URL configured for ${serviceId}` }, { status: 503 });
  }
  const url = new URL(request.url);
  const target = `${serviceUrl.replace(/\/$/, "")}${path}${url.search}`;
  const response = await fetch(target, {
    method: request.method,
    headers: { authorization: request.headers.get("authorization") || "" },
  });
  const text = await response.text();
  return new Response(text, {
    status: response.status,
    headers: { "content-type": response.headers.get("content-type") || "application/json" },
  });
}

const apiKeys = readApiKeys();
const serviceId = process.env.ANIP_SERVICE_ID ?? runtimeTarget.system_name;
const serviceFilter = process.env.GTM_SERVICE_FILTER?.trim();

for (const capability of generatedCapabilityMetadata) {
  if (capability.capability_id !== "gtm.bottleneck_account_outreach_draft") continue;
  capability.grant_policy = capability.grant_policy ?? {
    allowed_grant_types: ["one_time", "session_bound"],
    default_grant_type: "one_time",
    expires_in_seconds: 900,
    max_uses: 1,
  };
  const targetRef = capability.required_inputs.find((input) => input.input_name === "target_ref");
  if (!targetRef) continue;
  capability.required_inputs = capability.required_inputs.filter((input) => input.input_name !== "target_ref");
  if (!capability.optional_inputs.some((input) => input.input_name === "target_ref")) {
    capability.optional_inputs = [targetRef, ...capability.optional_inputs];
  }
}

const activeCapabilities = serviceFilter
  ? generatedCapabilities.filter((_, index) => generatedCapabilityMetadata[index]?.service_id === serviceFilter)
  : generatedCapabilities;
const bridgedCapabilities = activeCapabilities.map((capability) => {
  const inputs = capability.declaration.inputs.map((input) =>
    capability.declaration.name === "gtm.bottleneck_account_outreach_draft" && input.name === "target_ref"
      ? { ...input, required: false }
      : input,
  );
  const grant_policy = capability.declaration.name === "gtm.bottleneck_account_outreach_draft"
    ? capability.declaration.grant_policy ?? {
      allowed_grant_types: ["one_time", "session_bound"],
      default_grant_type: "one_time",
      expires_in_seconds: 900,
      max_uses: 1,
    }
    : capability.declaration.grant_policy;
  if (capability.declaration.kind !== "composed") {
    return {
      ...capability,
      declaration: {
        ...capability.declaration,
        grant_policy,
        inputs,
      },
    };
  }
  return {
    ...capability,
    declaration: {
      ...capability.declaration,
      grant_policy,
      inputs,
      kind: "atomic" as const,
      composition: null,
    },
  };
});

export const service = createANIPService({
  serviceId,
  capabilities: bridgedCapabilities,
  trust: (process.env.ANIP_TRUST_LEVEL as "signed" | "anchored") ?? "signed",
  keyPath: process.env.ANIP_KEY_PATH ?? resolve(__dirname, "../anip-keys"),
  storage: { type: process.env.ANIP_STORAGE === "sqlite" ? "sqlite" : "memory" },
  authenticate: async (bearer: string) => apiKeys[bearer] ?? null,
});

export const app = new Hono();

app.get("/gtm/approvals", (c) => proxyJson("gtm-pipeline-service", "/gtm/approvals", c.req.raw));
app.post("/gtm/approvals/:approval_request_id/approve", (c) =>
  proxyJson("gtm-pipeline-service", `/gtm/approvals/${c.req.param("approval_request_id")}/approve`, c.req.raw),
);
app.get("/gtm/pipeline/approvals", (c) => proxyJson("gtm-pipeline-service", "/gtm/approvals", c.req.raw));
app.post("/gtm/pipeline/approvals/:approval_request_id/approve", (c) =>
  proxyJson("gtm-pipeline-service", `/gtm/approvals/${c.req.param("approval_request_id")}/approve`, c.req.raw),
);
app.get("/gtm/prioritization/approvals", (c) => proxyJson("gtm-prioritization-service", "/gtm/approvals", c.req.raw));
app.post("/gtm/prioritization/approvals/:approval_request_id/approve", (c) =>
  proxyJson("gtm-prioritization-service", `/gtm/approvals/${c.req.param("approval_request_id")}/approve`, c.req.raw),
);

const mounted = await mountAnip(app, service, { healthEndpoint: true });
export const stop = mounted.stop;
