"""book_flight capability -- irreversible, financial side effect."""
from anip_service import (
    ANIPError, Capability, INVALID_PARAMETERS_RESOLUTION, InvocationContext,
)
from anip_core import (
    BindingRequirement, CapabilityDeclaration, CapabilityInput, CapabilityOutput,
    CapabilityRequirement, Cost, CostCertainty, CrossServiceHints, FinancialCost,
    GrantPolicy, ObservabilityContract, ServiceCapabilityRef, SessionInfo, SideEffect,
    SideEffectType,
)
from anip_flight_demo.domain.flights import create_booking, get_flight

# Bookings for this many passengers or more need an approval grant (SPEC.md §4.7).
GROUP_BOOKING_APPROVAL_THRESHOLD = 5

DECLARATION = CapabilityDeclaration(
    name="book_flight",
    description="Book a confirmed flight reservation",
    contract_version="1.0",
    inputs=[
        CapabilityInput(name="flight_number", type="string", description="Flight to book"),
        CapabilityInput(name="date", type="date", description="Travel date (YYYY-MM-DD)"),
        CapabilityInput(
            name="passengers", type="integer", required=False, default=1,
            description=(
                "Number of passengers. Bookings for "
                f"{GROUP_BOOKING_APPROVAL_THRESHOLD} or more require approval"
            ),
        ),
        CapabilityInput(
            name="quote_id", type="object", required=False,
            description="Priced quote from search_flights containing id, price, and issued_at",
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
    requires_binding=[
        BindingRequirement(
            type="quote",
            field="quote_id",
            source_capability="search_flights",
            max_age="PT15M",
        ),
    ],
    refresh_via=["search_flights"],
    session=SessionInfo(),
    observability=ObservabilityContract(
        logged=True, retention="P90D",
        fields_logged=["capability", "delegation_chain", "parameters", "result", "cost_actual"],
        audit_accessible_by=["delegation.root_principal"],
    ),
    # Cross-service hints (illustrative — this is a single-service demo)
    cross_service=CrossServiceHints(
        refresh_via=[ServiceCapabilityRef(service="travel-search", capability="search_flights")],
    ),
    # What an approver may issue for a group booking (SPEC.md §4.7).
    grant_policy=GrantPolicy(
        allowed_grant_types=["one_time", "session_bound"],
        default_grant_type="one_time",
        expires_in_seconds=900,
        max_uses=2,
    ),
)


def _invalid(detail: str) -> ANIPError:
    return ANIPError(
        "invalid_parameters", detail,
        resolution=dict(INVALID_PARAMETERS_RESOLUTION), retry=False,
    )


def _handle_book(ctx: InvocationContext, params: dict) -> dict:
    flight_number = params.get("flight_number")
    date = params.get("date")
    # The runtime has checked that passengers is a whole number; JSON may
    # still have written it with a fraction part (5.0).
    passengers = int(params.get("passengers", 1))

    # The runtime refuses missing inputs and wrong primitive types before the
    # handler runs (SPEC.md §6.3). What is left is what it cannot know: an
    # empty flight number, and `date`, whose declared type is not a primitive.
    if not flight_number.strip():
        raise _invalid("flight_number must not be empty")
    if not isinstance(date, str) or not date.strip():
        raise _invalid("date must be a YYYY-MM-DD string")
    if passengers < 1:
        raise _invalid("passengers must be at least 1")

    # Group bookings need an approver's grant. On the continuation invocation
    # the runtime has already validated and reserved the grant.
    if passengers >= GROUP_BOOKING_APPROVAL_THRESHOLD and not ctx.approval_grant:
        raise ANIPError(
            "approval_required",
            f"bookings for {GROUP_BOOKING_APPROVAL_THRESHOLD} or more passengers require approval",
            resolution={"action": "request_approval", "recovery_class": "wait_then_retry"},
        )

    flight = get_flight(flight_number, date)
    if flight is None:
        raise ANIPError(
            "capability_unavailable",
            f"flight {flight_number} on {date} not found",
            resolution={
                "action": "search_flights",
                "recovery_class": "refresh_then_retry",
                "recovery_target": {
                    "kind": "refresh",
                    "target": {"service": "travel-booking", "capability": "search_flights"},
                    "continuity": "same_task",
                    "retry_after_target": True,
                },
            },
        )

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
