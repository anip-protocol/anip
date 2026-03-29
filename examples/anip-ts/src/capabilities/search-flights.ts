import { defineCapability, ANIPError } from "@anip-dev/service";
import type { CapabilityDeclaration } from "@anip-dev/core";
import { searchFlights as doSearch } from "../domain/flights.js";

const DECLARATION: CapabilityDeclaration = {
  name: "search_flights",
  description: "Search available flights by origin, destination, and date",
  contract_version: "1.0",
  inputs: [
    { name: "origin", type: "airport_code", required: true, default: null, description: "Departure airport" },
    { name: "destination", type: "airport_code", required: true, default: null, description: "Arrival airport" },
    { name: "date", type: "date", required: true, default: null, description: "Travel date (YYYY-MM-DD)" },
  ],
  output: { type: "flight_list", fields: ["flight_number", "departure_time", "arrival_time", "price", "stops"] },
  side_effect: { type: "read", rollback_window: "not_applicable" },
  minimum_scope: ["travel.search"],
  cost: {
    certainty: "fixed",
    financial: null,
    determined_by: null,
    factors: null,
    compute: { latency_p50: "200ms", tokens: 500 },
    rate_limit: null,
  },
  requires: [],
  composes_with: [],
  session: { type: "stateless" },
  response_modes: ["unary"],
  observability: {
    logged: true,
    retention: "P90D",
    fields_logged: ["capability", "parameters", "result_count"],
    audit_accessible_by: ["delegation.root_principal"],
  },
};

export const searchFlights = defineCapability({
  declaration: DECLARATION,
  handler: (_ctx, params) => {
    const origin = params.origin as string | undefined;
    const destination = params.destination as string | undefined;
    const date = params.date as string | undefined;

    if (!origin || !destination || !date) {
      throw new ANIPError("invalid_parameters", "origin, destination, and date are all required");
    }

    const flights = doSearch(origin, destination, date);
    return {
      flights: flights.map((f) => ({
        flight_number: f.flight_number,
        departure_time: f.departure_time,
        arrival_time: f.arrival_time,
        price: f.price,
        currency: f.currency,
        stops: f.stops,
      })),
      count: flights.length,
    };
  },
});
