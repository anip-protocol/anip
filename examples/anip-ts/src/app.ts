import { Hono } from "hono";
import { createANIPService } from "@anip/service";
import { mountAnip } from "@anip/hono";
import { searchFlights } from "./capabilities/search-flights.js";
import { bookFlight } from "./capabilities/book-flight.js";

const API_KEYS: Record<string, string> = {
  "demo-human-key": "human:samir@example.com",
  "demo-agent-key": "agent:demo-agent",
};

const service = createANIPService({
  serviceId: process.env.ANIP_SERVICE_ID ?? "anip-flight-service",
  capabilities: [searchFlights, bookFlight],
  storage: {
    type: process.env.ANIP_DB_PATH ? "sqlite" : "memory",
    path: process.env.ANIP_DB_PATH ?? ":memory:",
  },
  trust: (process.env.ANIP_TRUST_LEVEL as "signed" | "anchored") ?? "signed",
  keyPath: process.env.ANIP_KEY_PATH ?? "./anip-keys",
  authenticate: (bearer: string) => API_KEYS[bearer] ?? null,
});

const app = new Hono();
const { stop } = mountAnip(app, service);

export { app, stop };
