/**
 * book_flight capability — irreversible, financial side effect.
 */

import { createBooking, getFlight } from "../data/flights.js";
import {
  checkBudgetAuthority,
  getRootPrincipal,
} from "../primitives/delegation.js";
import type {
  CapabilityDeclaration,
  DelegationToken,
  InvokeResponse,
} from "../types.js";

export const DECLARATION: CapabilityDeclaration = {
  name: "book_flight",
  description: "Book a confirmed flight reservation",
  contract_version: "1.0",
  inputs: [
    {
      name: "flight_number",
      type: "string",
      required: true,
      default: null,
      description: "Flight to book",
    },
    {
      name: "date",
      type: "date",
      required: true,
      default: null,
      description: "Travel date (YYYY-MM-DD)",
    },
    {
      name: "passengers",
      type: "integer",
      required: false,
      default: 1,
      description: "Number of passengers",
    },
  ],
  output: {
    type: "booking_confirmation",
    fields: ["booking_id", "flight_number", "departure_time", "total_cost"],
  },
  side_effect: { type: "irreversible", rollback_window: "none" },
  required_scope: "travel.book",
  cost: {
    certainty: "estimated",
    financial: {
      range_min: 280,
      range_max: 500,
      typical: 420,
      currency: "USD",
    },
    determined_by: "search_flights",
    factors: null,
    compute: { latency_p50: "2s", tokens: 1500 },
    rate_limit: null,
  },
  requires: [
    {
      capability: "search_flights",
      reason: "must select from available flights before booking",
    },
  ],
  composes_with: [],
  session: { type: "stateless" },
  observability: {
    logged: true,
    retention: "P90D",
    fields_logged: [
      "capability",
      "delegation_chain",
      "parameters",
      "result",
      "cost_actual",
    ],
    audit_accessible_by: ["delegation.root_principal"],
  },
};

export function invoke(
  token: DelegationToken,
  parameters: Record<string, unknown>
): InvokeResponse {
  const flightNumber = parameters["flight_number"] as string | undefined;
  const date = parameters["date"] as string | undefined;
  const passengers = (parameters["passengers"] as number) ?? 1;

  if (!flightNumber || !date) {
    return {
      success: false,
      result: null,
      cost_actual: null,
      failure: {
        type: "invalid_parameters",
        detail: "flight_number and date are required",
        resolution: {
          action: "fix_parameters",
          requires: null,
          grantable_by: null,
          estimated_availability: null,
        },
        retry: true,
      },
      session: null,
    };
  }

  // Look up the flight
  const flight = getFlight(flightNumber, date);
  if (flight === null) {
    return {
      success: false,
      result: null,
      cost_actual: null,
      failure: {
        type: "capability_unavailable",
        detail: `flight ${flightNumber} on ${date} not found`,
        resolution: {
          action: "search_flights_first",
          requires: null,
          grantable_by: null,
          estimated_availability: null,
        },
        retry: true,
      },
      session: null,
    };
  }

  // Check budget authority in delegation chain
  const totalCost = flight.price * passengers;
  const budgetFailure = checkBudgetAuthority(token, totalCost);
  if (budgetFailure !== null) {
    return {
      success: false,
      result: null,
      cost_actual: null,
      failure: budgetFailure,
      session: null,
    };
  }

  // Book it
  const booking = createBooking(
    flight,
    passengers,
    token.subject,
    getRootPrincipal(token)
  );

  // Calculate variance from the typical estimate
  const typicalEstimate = 420.0;
  const variancePct =
    ((booking.total_cost - typicalEstimate) / typicalEstimate) * 100;
  const varianceStr = `${variancePct >= 0 ? "+" : ""}${variancePct.toFixed(1)}%`;

  return {
    success: true,
    result: {
      booking_id: booking.booking_id,
      flight_number: booking.flight.flight_number,
      departure_time: booking.flight.departure_time,
      total_cost: booking.total_cost,
      currency: booking.flight.currency,
      side_effect_executed: "irreversible",
      rollback_window: "none",
    },
    cost_actual: {
      financial: {
        amount: booking.total_cost,
        currency: booking.flight.currency,
      },
      variance_from_estimate: varianceStr,
    },
    failure: null,
    session: null,
  };
}
