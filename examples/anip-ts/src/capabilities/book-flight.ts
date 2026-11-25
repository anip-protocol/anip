import { defineCapability, ANIPError } from "@anip-dev/service";
import type { InvocationContext } from "@anip-dev/service";
import type { CapabilityDeclaration } from "@anip-dev/core";
import { createBooking, getFlight } from "../domain/flights.js";

// Bookings for this many passengers or more need an approval grant (SPEC.md §4.7).
const GROUP_BOOKING_APPROVAL_THRESHOLD = 5;

const DECLARATION: CapabilityDeclaration = {
  name: "book_flight",
  description: "Book a confirmed flight reservation",
  contract_version: "1.0",
  inputs: [
    { name: "flight_number", type: "string", required: true, default: null, description: "Flight to book", semantic_type: null, entity_reference: false, allowed_values: null, catalog_ref: null, input_meanings: null, resolution: null },
    { name: "date", type: "date", required: true, default: null, description: "Travel date (YYYY-MM-DD)", semantic_type: null, entity_reference: false, allowed_values: null, catalog_ref: null, input_meanings: null, resolution: null },
    { name: "passengers", type: "integer", required: false, default: 1, description: `Number of passengers. Bookings for ${GROUP_BOOKING_APPROVAL_THRESHOLD} or more require approval`, semantic_type: null, entity_reference: false, allowed_values: null, catalog_ref: null, input_meanings: null, resolution: null },
    // Optional as an input: requires_binding below is what demands it (binding_missing).
    { name: "quote_id", type: "object", required: false, default: null, description: "Priced quote from search_flights", semantic_type: null, entity_reference: false, allowed_values: null, catalog_ref: null, input_meanings: null, resolution: null },
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
  refresh_via: ["search_flights"],
  verify_via: [],
  // Cross-service hints (illustrative — this is a single-service showcase)
  cross_service: {
    handoff_to: [],
    refresh_via: [{ service: "travel-search", capability: "search_flights" }],
    verify_via: [],
    followup_via: [],
  },
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
  // v0.23 — atomic capability, no composition
  kind: "atomic",
  composition: null,
  // What an approver may issue for a group booking (SPEC.md §4.7).
  grant_policy: {
    allowed_grant_types: ["one_time", "session_bound"],
    default_grant_type: "one_time",
    expires_in_seconds: 900,
    max_uses: 2,
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

    // Group bookings need an approver's grant. On the continuation invocation
    // the runtime has already validated and reserved the grant.
    if (passengers >= GROUP_BOOKING_APPROVAL_THRESHOLD && !(ctx.approvalGrant ?? "").trim()) {
      throw new ANIPError(
        "approval_required",
        `bookings for ${GROUP_BOOKING_APPROVAL_THRESHOLD} or more passengers require approval`,
        { action: "request_approval", recovery_class: "wait_then_retry" },
      );
    }

    const flight = getFlight(flightNumber, date);
    if (!flight) {
      throw new ANIPError(
        "capability_unavailable",
        `flight ${flightNumber} on ${date} not found`,
        {
          action: "search_flights",
          recovery_class: "refresh_then_retry",
          recovery_target: {
            kind: "refresh",
            target: { service: "travel-booking", capability: "search_flights" },
            continuity: "same_task",
            retry_after_target: true,
          },
        },
      );
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
