import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { Hono } from "hono";
import { createANIPService } from "@anip/service";
import { mountAnip } from "@anip/hono";
import { searchFlights } from "./capabilities/search-flights.js";
import { bookFlight } from "./capabilities/book-flight.js";

const __dirname = dirname(fileURLToPath(import.meta.url));

const API_KEYS: Record<string, string> = {
  "demo-human-key": "human:samir@example.com",
  "demo-agent-key": "agent:demo-agent",
};

const service = createANIPService({
  serviceId: process.env.ANIP_SERVICE_ID ?? "anip-flight-service",
  capabilities: [searchFlights, bookFlight],
  trust: (process.env.ANIP_TRUST_LEVEL as "signed" | "anchored") ?? "signed",
  keyPath: process.env.ANIP_KEY_PATH ?? resolve(__dirname, "../anip-keys"),
  authenticate: (bearer: string) => API_KEYS[bearer] ?? null,
});

const app = new Hono();
const { stop } = mountAnip(app, service);

export { app, stop };
