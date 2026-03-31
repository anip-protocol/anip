import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { Hono } from "hono";
import { createANIPService } from "@anip-dev/service";
import { mountAnip } from "@anip-dev/hono";
import { searchFlights } from "./capabilities/search-flights.js";
import { bookFlight } from "./capabilities/book-flight.js";
import { createOidcValidator } from "./oidc.js";

const __dirname = dirname(fileURLToPath(import.meta.url));

const API_KEYS: Record<string, string> = {
  "demo-human-key": "human:samir@example.com",
  "demo-agent-key": "agent:demo-agent",
};

const serviceId = process.env.ANIP_SERVICE_ID ?? "anip-flight-service";

// Optional OIDC authentication — enabled when OIDC_ISSUER_URL is set
const oidcValidator = process.env.OIDC_ISSUER_URL
  ? createOidcValidator({
      issuerUrl: process.env.OIDC_ISSUER_URL,
      audience: process.env.OIDC_AUDIENCE ?? serviceId,
      jwksUrl: process.env.OIDC_JWKS_URL,
    })
  : null;

const service = createANIPService({
  serviceId,
  capabilities: [searchFlights, bookFlight],
  trust: (process.env.ANIP_TRUST_LEVEL as "signed" | "anchored") ?? "signed",
  keyPath: process.env.ANIP_KEY_PATH ?? resolve(__dirname, "../anip-keys"),
  storage: { type: process.env.ANIP_STORAGE === "sqlite" ? "sqlite" : "memory" },
  authenticate: async (bearer: string) => {
    // 1. API key map
    const principal = API_KEYS[bearer];
    if (principal) return principal;
    // 2. OIDC (if configured)
    if (oidcValidator) return oidcValidator(bearer);
    // 3. Not recognized — service will try ANIP JWT separately
    return null;
  },
});

const app = new Hono();
const { stop } = await mountAnip(app, service);

export { app, stop };
