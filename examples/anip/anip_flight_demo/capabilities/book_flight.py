"""book_flight capability -- irreversible, financial side effect."""
from anip_service import Capability, InvocationContext, ANIPError
from anip_core import (
    CapabilityDeclaration, CapabilityInput, CapabilityOutput, CapabilityRequirement,
    Cost, CostCertainty, FinancialCost, ObservabilityContract, SessionInfo, SideEffect, SideEffectType,
)
from anip_flight_demo.domain.flights import create_booking, get_flight

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
    output=CapabilityOutput(type="booking_confirmation", fields=["booking_id", "flight_number", "departure_time", "total_cost"]),
    side_effect=SideEffect(type=SideEffectType.IRREVERSIBLE, rollback_window="none"),
    minimum_scope=["travel.book"],
    cost=Cost(
        certainty=CostCertainty.ESTIMATED,
        financial=FinancialCost(
            currency="USD",
            range_min=280,
            range_max=500,
            typical=420,
        ),
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
        logged=True, retention="P90D",
        fields_logged=["capability", "delegation_chain", "parameters", "result", "cost_actual"],
        audit_accessible_by=["delegation.root_principal"],
    ),
)


def _handle_book(ctx: InvocationContext, params: dict) -> dict:
    flight_number = params.get("flight_number")
    date = params.get("date")
    passengers = params.get("passengers", 1)

    if not flight_number or not date:
        raise ANIPError("invalid_parameters", "flight_number and date are required")

    flight = get_flight(flight_number, date)
    if flight is None:
        raise ANIPError("capability_unavailable", f"flight {flight_number} on {date} not found")

    booking = create_booking(
        flight=flight,
        passengers=passengers,
        booked_by=ctx.subject,
        on_behalf_of=ctx.root_principal,
    )

    # Track actual cost via context
    ctx.set_cost_actual({"financial": {"amount": booking.total_cost, "currency": booking.flight.currency}})

    return {
        "booking_id": booking.booking_id,
        "flight_number": booking.flight.flight_number,
        "departure_time": booking.flight.departure_time,
        "total_cost": booking.total_cost,
        "currency": booking.flight.currency,
    }


book_flight = Capability(declaration=DECLARATION, handler=_handle_book)
