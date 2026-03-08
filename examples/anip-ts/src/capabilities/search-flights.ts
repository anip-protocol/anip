/**
 * search_flights capability — read-only, no side effects.
 */

import { searchFlights as doSearch } from "../data/flights.js";
import type {
  CapabilityDeclaration,
  DelegationToken,
  InvokeResponse,
} from "../types.js";

export const DECLARATION: CapabilityDeclaration = {
  name: "search_flights",
  description: "Search available flights by origin, destination, and date",
  contract_version: "1.0",
  inputs: [
    {
      name: "origin",
      type: "airport_code",
      required: true,
      default: null,
      description: "Departure airport",
    },
    {
      name: "destination",
      type: "airport_code",
      required: true,
      default: null,
      description: "Arrival airport",
    },
    {
      name: "date",
      type: "date",
      required: true,
      default: null,
      description: "Travel date (YYYY-MM-DD)",
    },
  ],
  output: {
    type: "flight_list",
    fields: [
      "flight_number",
      "departure_time",
      "arrival_time",
      "price",
      "stops",
    ],
  },
  side_effect: { type: "read", rollback_window: "not_applicable" },
  required_scope: "travel.search",
  cost: {
    certainty: "fixed",
    financial: { amount: 0.0, currency: "USD" },
    determined_by: null,
    factors: null,
    compute: { latency_p50: "200ms", tokens: 500 },
    rate_limit: null,
  },
  requires: [],
  composes_with: [],
  session: { type: "stateless" },
  observability: {
    logged: true,
    retention: "P90D",
    fields_logged: ["capability", "parameters", "result_count"],
    audit_accessible_by: ["delegation.root_principal"],
  },
};

export function invoke(
  _token: DelegationToken,
  parameters: Record<string, unknown>
): InvokeResponse {
  const origin = parameters["origin"] as string | undefined;
  const destination = parameters["destination"] as string | undefined;
  const date = parameters["date"] as string | undefined;

  if (!origin || !destination || !date) {
    return {
      success: false,
      result: null,
      cost_actual: null,
      failure: {
        type: "invalid_parameters",
        detail: "origin, destination, and date are all required",
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

  const flights = doSearch(origin, destination, date);

  return {
    success: true,
    result: {
      flights: flights.map((f) => ({
        flight_number: f.flight_number,
        departure_time: f.departure_time,
        arrival_time: f.arrival_time,
        price: f.price,
        currency: f.currency,
        stops: f.stops,
      })),
      count: flights.length,
    },
    cost_actual: null,
    failure: null,
    session: null,
  };
}
