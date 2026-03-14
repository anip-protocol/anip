"""book_flight capability — irreversible, financial side effect."""

from __future__ import annotations

from ..data.flights import create_booking, get_flight
from .. import engine as sdk
from anip_core import (
    ANIPFailure,
    CapabilityDeclaration,
    CapabilityInput,
    CapabilityOutput,
    CapabilityRequirement,
    Cost,
    CostActual,
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
    name="book_flight",
    description="Book a confirmed flight reservation",
    contract_version="1.0",
    inputs=[
        CapabilityInput(name="flight_number", type="string", description="Flight to book"),
        CapabilityInput(name="date", type="date", description="Travel date (YYYY-MM-DD)"),
        CapabilityInput(
            name="passengers", type="integer", required=False, default=1,
            description="Number of passengers",
        ),
    ],
    output=CapabilityOutput(
        type="booking_confirmation",
        fields=["booking_id", "flight_number", "departure_time", "total_cost"],
    ),
    side_effect=SideEffect(type=SideEffectType.IRREVERSIBLE, rollback_window="none"),
    minimum_scope=["travel.book"],
    cost=Cost(
        certainty=CostCertainty.ESTIMATED,
        financial={
            "range_min": 280,
            "range_max": 500,
            "typical": 420,
            "currency": "USD",
        },
        determined_by="search_flights",
        compute={"latency_p50": "2s", "tokens": 1500},
    ),
    requires=[
        CapabilityRequirement(
            capability="search_flights",
            reason="must select from available flights before booking",
        ),
    ],
    session=SessionInfo(),
    observability=ObservabilityContract(
        logged=True,
        retention="P90D",
        fields_logged=["capability", "delegation_chain", "parameters", "result", "cost_actual"],
        audit_accessible_by=["delegation.root_principal"],
    ),
)


def invoke(token: DelegationToken, parameters: dict) -> InvokeResponse:
    flight_number = parameters.get("flight_number")
    date = parameters.get("date")
    passengers = parameters.get("passengers", 1)

    if not flight_number or not date:
        return InvokeResponse(
            success=False,
            failure=ANIPFailure(
                type="invalid_parameters",
                detail="flight_number and date are required",
                resolution=Resolution(action="fix_parameters"),
                retry=True,
            ),
        )

    # Look up the flight
    flight = get_flight(flight_number, date)
    if flight is None:
        return InvokeResponse(
            success=False,
            failure=ANIPFailure(
                type="capability_unavailable",
                detail=f"flight {flight_number} on {date} not found",
                resolution=Resolution(action="search_flights_first"),
                retry=True,
            ),
        )

    # Check budget authority in delegation chain
    total_cost = flight.price * passengers
    budget_failure = sdk.engine.check_budget_authority(token, total_cost)
    if budget_failure is not None:
        return InvokeResponse(success=False, failure=budget_failure)

    # Book it
    booking = create_booking(
        flight=flight,
        passengers=passengers,
        booked_by=token.subject,
        on_behalf_of=sdk.engine.get_root_principal(token),
    )

    # Calculate variance from the typical estimate
    typical_estimate = 420.0
    variance_pct = ((booking.total_cost - typical_estimate) / typical_estimate) * 100
    variance_str = f"{variance_pct:+.1f}%"

    return InvokeResponse(
        success=True,
        result={
            "booking_id": booking.booking_id,
            "flight_number": booking.flight.flight_number,
            "departure_time": booking.flight.departure_time,
            "total_cost": booking.total_cost,
            "currency": booking.flight.currency,
            "side_effect_executed": "irreversible",
            "rollback_window": "none",
        },
        cost_actual=CostActual(
            financial={"amount": booking.total_cost, "currency": booking.flight.currency},
            variance_from_estimate=variance_str,
        ),
    )
