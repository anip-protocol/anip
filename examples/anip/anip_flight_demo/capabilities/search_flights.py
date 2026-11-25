"""search_flights capability -- read-only, no side effects."""
from anip_service import (
    ANIPError, Capability, INVALID_PARAMETERS_RESOLUTION, InvocationContext,
)
from anip_core import (
    CapabilityDeclaration, CapabilityInput, CapabilityOutput,
    Cost, CostCertainty, CrossServiceHints, ObservabilityContract, ServiceCapabilityRef,
    SessionInfo, SideEffect, SideEffectType,
)
from anip_flight_demo.domain.flights import search_flights as do_search

DECLARATION = CapabilityDeclaration(
    name="search_flights",
    description="Search available flights by origin, destination, and date",
    contract_version="1.0",
    inputs=[
        CapabilityInput(name="origin", type="airport_code", description="Departure airport"),
        CapabilityInput(name="destination", type="airport_code", description="Arrival airport"),
        CapabilityInput(name="date", type="date", description="Travel date (YYYY-MM-DD)"),
    ],
    output=CapabilityOutput(type="flight_list", fields=["flight_number", "departure_time", "arrival_time", "price", "stops"]),
    side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
    minimum_scope=["travel.search"],
    cost=Cost(certainty=CostCertainty.FIXED, financial=None, compute={"latency_p50": "200ms", "tokens": 500}),
    session=SessionInfo(),
    observability=ObservabilityContract(
        logged=True, retention="P90D",
        fields_logged=["capability", "parameters", "result_count"],
        audit_accessible_by=["delegation.root_principal"],
    ),
    # Cross-service hints (illustrative — this is a single-service demo)
    cross_service=CrossServiceHints(
        handoff_to=[ServiceCapabilityRef(service="travel-booking", capability="book_flight")],
    ),
)


def _handle_search(ctx: InvocationContext, params: dict) -> dict:
    origin = params.get("origin")
    destination = params.get("destination")
    date = params.get("date")

    # The runtime refuses missing inputs before the handler runs (SPEC.md
    # §6.3). `airport_code` and `date` are not primitive types, so the
    # handler checks that the values are non-empty strings.
    invalid = [
        name for name, value in (("origin", origin), ("destination", destination), ("date", date))
        if not isinstance(value, str) or not value.strip()
    ]
    if invalid:
        raise ANIPError(
            "invalid_parameters",
            f"{', '.join(invalid)} must be non-empty text",
            resolution=dict(INVALID_PARAMETERS_RESOLUTION),
            retry=False,
        )

    flights = do_search(origin, destination, date)
    return {
        "flights": [
            {
                "flight_number": f.flight_number,
                "departure_time": f.departure_time,
                "arrival_time": f.arrival_time,
                "price": f.price,
                "currency": f.currency,
                "stops": f.stops,
            }
            for f in flights
        ],
        "count": len(flights),
    }


search_flights = Capability(declaration=DECLARATION, handler=_handle_search)
