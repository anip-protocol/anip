import { defineCapability, ANIPError } from "@anip-dev/service";
import type { InvocationContext } from "@anip-dev/service";
import type { CapabilityDeclaration } from "@anip-dev/core";
import { createBooking, getFlight } from "../domain/flights.js";

const DECLARATION: CapabilityDeclaration = {
  name: "book_flight",
  description: "Book a confirmed flight reservation",
  contract_version: "1.0",
  inputs: [
    { name: "flight_number", type: "string", required: true, default: null, description: "Flight to book" },
    { name: "date", type: "date", required: true, default: null, description: "Travel date (YYYY-MM-DD)" },
    { name: "passengers", type: "integer", required: false, default: 1, description: "Number of passengers" },
    { name: "quote_id", type: "object", required: true, default: null, description: "Priced quote from search_flights" },
  ],
  output: { type: "booking_confirmation", fields: ["booking_id", "flight_number", "departure_time", "total_cost"] },
  side_effect: { type: "irreversible", rollback_window: "none" },
  minimum_scope: ["travel.book"],
  cost: {
    certainty: "estimated",
    financial: { currency: "USD", amount: null, range_min: 280, range_max: 500, typical: 420, upper_bound: null },
    determined_by: "search_flights",
    factors: null,
    compute: { latency_p50: "2s", tokens: 1500 },
    rate_limit: null,
  },
  requires: [{ capability: "search_flights", reason: "must select from available flights before booking" }],
  composes_with: [],
  session: { type: "stateless" },
  response_modes: ["unary"],
  requires_binding: [
    {
      type: "quote",
      field: "quote_id",
      source_capability: "search_flights",
      max_age: "PT15M",
    },
  ],
  control_requirements: [],
  observability: {
    logged: true,
    retention: "P90D",
    fields_logged: ["capability", "delegation_chain", "parameters", "result", "cost_actual"],
    audit_accessible_by: ["delegation.root_principal"],
  },
};

export const bookFlight = defineCapability({
  declaration: DECLARATION,
  handler: (ctx: InvocationContext, params) => {
    const flightNumber = params.flight_number as string | undefined;
    const date = params.date as string | undefined;
    const passengers = (params.passengers as number) ?? 1;

    if (!flightNumber || !date) {
      throw new ANIPError("invalid_parameters", "flight_number and date are required");
    }

    const flight = getFlight(flightNumber, date);
    if (!flight) {
      throw new ANIPError("capability_unavailable", `flight ${flightNumber} on ${date} not found`);
    }

    const booking = createBooking(flight, passengers, ctx.subject, ctx.rootPrincipal);

    ctx.setCostActual({ financial: { amount: booking.total_cost, currency: booking.flight.currency } });

    return {
      booking_id: booking.booking_id,
      flight_number: booking.flight.flight_number,
      departure_time: booking.flight.departure_time,
      total_cost: booking.total_cost,
      currency: booking.flight.currency,
    };
  },
});
