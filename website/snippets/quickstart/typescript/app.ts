import { serve } from "@hono/node-server";
import { Hono } from "hono";
import { mountAnip } from "@anip-dev/hono";
import { createANIPService, defineCapability } from "@anip-dev/service";

// Your business logic. Nothing here knows about ANIP.
function doSearch(origin: string, destination: string) {
  return [
    { flight_number: "AA100", origin, destination, price: 420 },
    { flight_number: "DL310", origin, destination, price: 280 },
  ];
}

function doBook(flightNumber: string) {
  return { booking_id: "BK-0001", flight_number: flightNumber };
}

// A capability that only reads.
const searchFlights = defineCapability({
  declaration: {
    name: "search_flights",
    description: "Search available flights between two airports",
    contract_version: "1.0",
    inputs: [
      { name: "origin", type: "string", description: "Departure airport" },
      { name: "destination", type: "string", description: "Arrival airport" },
    ],
    output: { type: "object", fields: ["flights"] },
    side_effect: { type: "read", rollback_window: "not_applicable" },
    minimum_scope: ["travel.search"],
  },
  handler: async (ctx, params) => ({
    flights: doSearch(String(params.origin), String(params.destination)),
  }),
});

// A capability that cannot be undone, and needs a different scope.
const bookFlight = defineCapability({
  declaration: {
    name: "book_flight",
    description: "Book a flight",
    contract_version: "1.0",
    inputs: [
      { name: "flight_number", type: "string", description: "Flight to book" },
    ],
    output: { type: "object", fields: ["booking_id", "flight_number"] },
    side_effect: { type: "irreversible", rollback_window: "none" },
    minimum_scope: ["travel.book"],
  },
  handler: async (ctx, params) => doBook(String(params.flight_number)),
});

const service = createANIPService({
  serviceId: "quickstart-flights",
  capabilities: [searchFlights, bookFlight],
  storage: { type: "memory" },
  trust: "signed",
  // Who is calling? Map your own API keys or sessions to a principal.
  authenticate: (bearer) =>
    ({ "demo-key": "human:demo@example.com" })[bearer] ?? null,
});

const app = new Hono();
await mountAnip(app, service);

const port = Number(process.env.PORT ?? 9100);
serve({ fetch: app.fetch, port });
console.log(`ANIP service listening on http://localhost:${port}`);
