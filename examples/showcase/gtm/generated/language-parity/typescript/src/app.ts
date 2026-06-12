import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { Hono } from "hono";
import { createANIPService } from "@anip-dev/service";
import { mountAnip } from "@anip-dev/hono";
import { generatedCapabilities } from "./generated/capabilities.js";
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

const apiKeys = readApiKeys();
const serviceId = process.env.ANIP_SERVICE_ID ?? runtimeTarget.system_name;

export const service = createANIPService({
  serviceId,
  capabilities: generatedCapabilities,
  trust: (process.env.ANIP_TRUST_LEVEL as "signed" | "anchored") ?? "signed",
  keyPath: process.env.ANIP_KEY_PATH ?? resolve(__dirname, "../anip-keys"),
  storage: { type: process.env.ANIP_STORAGE === "sqlite" ? "sqlite" : "memory" },
  authenticate: async (bearer: string) => apiKeys[bearer] ?? null,
});

export const app = new Hono();
const mounted = await mountAnip(app, service, { healthEndpoint: true });
export const stop = mounted.stop;
