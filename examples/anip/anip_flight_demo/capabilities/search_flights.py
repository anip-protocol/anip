"""search_flights capability — read-only, no side effects."""

from __future__ import annotations

from ..data.flights import search_flights as do_search
from ..primitives.models import (
    ANIPFailure,
    CapabilityDeclaration,
    CapabilityInput,
    CapabilityOutput,
    Cost,
    CostCertainty,
    DelegationToken,
    InvokeResponse,
    ObservabilityContract,
    Resolution,
    SessionInfo,
    SideEffect,
    SideEffectType,
)

DECLARATION = CapabilityDeclaration(
    name="search_flights",
    description="Search available flights by origin, destination, and date",
    contract_version="1.0",
    inputs=[
        CapabilityInput(name="origin", type="airport_code", description="Departure airport"),
        CapabilityInput(name="destination", type="airport_code", description="Arrival airport"),
        CapabilityInput(name="date", type="date", description="Travel date (YYYY-MM-DD)"),
    ],
    output=CapabilityOutput(
        type="flight_list",
        fields=["flight_number", "departure_time", "arrival_time", "price", "stops"],
    ),
    side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
    minimum_scope=["travel.search"],
    cost=Cost(
        certainty=CostCertainty.FIXED,
        financial=None,
        compute={"latency_p50": "200ms", "tokens": 500},
    ),
    session=SessionInfo(),
    observability=ObservabilityContract(
        logged=True,
        retention="P90D",
        fields_logged=["capability", "parameters", "result_count"],
        audit_accessible_by=["delegation.root_principal"],
    ),
)


def invoke(token: DelegationToken, parameters: dict) -> InvokeResponse:
    origin = parameters.get("origin")
    destination = parameters.get("destination")
    date = parameters.get("date")

    if not all([origin, destination, date]):
        return InvokeResponse(
            success=False,
            failure=ANIPFailure(
                type="invalid_parameters",
                detail="origin, destination, and date are all required",
                resolution=Resolution(action="fix_parameters"),
                retry=True,
            ),
        )

    flights = do_search(origin, destination, date)

    return InvokeResponse(
        success=True,
        result={
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
        },
    )
