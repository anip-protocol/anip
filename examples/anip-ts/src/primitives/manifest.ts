/**
 * Manifest and profile handshake.
 */

import { DECLARATION as searchFlightsDeclaration } from "../capabilities/search-flights.js";
import { DECLARATION as bookFlightDeclaration } from "../capabilities/book-flight.js";
import type { ANIPManifest } from "../types.js";

export function buildManifest(): ANIPManifest {
  const capabilities = {
    search_flights: searchFlightsDeclaration,
    book_flight: bookFlightDeclaration,
  };

  return {
    protocol: "anip/1.0",
    profile: {
      core: "1.0",
      cost: "1.0",
      capability_graph: "1.0",
      state_session: "1.0",
      observability: "1.0",
    },
    capabilities,
  };
}
