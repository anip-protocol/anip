"""search_flights capability -- read-only, no side effects."""
from anip_service import Capability, InvocationContext, ANIPError
from anip_core import (
    CapabilityDeclaration, CapabilityInput, CapabilityOutput,
    Cost, CostCertainty, ObservabilityContract, SessionInfo, SideEffect, SideEffectType,
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
)


def _handle_search(ctx: InvocationContext, params: dict) -> dict:
    origin = params.get("origin")
    destination = params.get("destination")
    date = params.get("date")

    if not all([origin, destination, date]):
        raise ANIPError("invalid_parameters", "origin, destination, and date are all required")

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
