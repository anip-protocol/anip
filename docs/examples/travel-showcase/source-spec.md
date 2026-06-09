# Travel Booking Showcase Source Specification

This is the Studio source document for the Travel Booking Showcase example package.
It is intentionally compact: the example is for learning ANIP contracts, registry packages,
and generated code, not for production business completeness.

## Purpose

Travel booking example focused on scoped search, quote binding, booking authority, and recovery from stale or unavailable options.

## Service Boundary

- Service ID: `travel-booking-service`
- Service name: Travel Booking Service
- Legacy implementation reference: `examples/showcase/travel`

The generated ANIP substrate should expose the contract and leave domain-specific behavior in
implementation material or backend adapters.

## Capabilities

- `travel.search_flights`: Search available flights by origin and destination and return priced quote references. Scope: `travel.search`. Side effect: `read`.
- `travel.check_availability`: Check seat availability and current price for a specific flight. Scope: `travel.search`. Side effect: `read`.
- `travel.book_flight`: Book a confirmed flight reservation from a current quote. Scope: `travel.book`. Side effect: `irreversible`.
- `travel.cancel_booking`: Cancel an existing booking within the transactional cancellation window. Scope: `travel.book`. Side effect: `transactional`.

## Review Decisions

- Keep the example single-service unless a tutorial explicitly demonstrates cross-service behavior.
- Treat write, transactional, irreversible, and approval-gated operations as authority-sensitive.
- Require explicit business inputs rather than guessing missing identifiers, account names, service names, quote IDs, or quantities.
- Preserve the old hand-built app as reference implementation material, not as the signed behavior contract.
