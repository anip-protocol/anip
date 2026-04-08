"""Travel booking capabilities — ANIP capability declarations and handlers."""
import time
import uuid

from anip_service import Capability, InvocationContext, ANIPError
from anip_core import (
    BindingRequirement, CapabilityDeclaration, CapabilityInput, CapabilityOutput,
    CapabilityRequirement, Cost, CostCertainty, CrossServiceHints, FinancialCost,
    ObservabilityContract, ResponseMode, ServiceCapabilityRef, SessionInfo, SideEffect,
    SideEffectType,
)
import data

# ---------------------------------------------------------------------------
# 1. search_flights — read-only, streaming response mode
# ---------------------------------------------------------------------------

_SEARCH_DECL = CapabilityDeclaration(
    name="search_flights",
    description="Search available flights by origin and destination",
    contract_version="1.0",
    inputs=[
        CapabilityInput(name="origin", type="airport_code", description="Departure airport (IATA code)"),
        CapabilityInput(name="destination", type="airport_code", description="Arrival airport (IATA code)"),
    ],
    output=CapabilityOutput(
        type="flight_list",
        fields=["flight_number", "origin", "destination", "departure_time", "arrival_time", "price", "stops", "quote_id"],
    ),
    side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
    minimum_scope=["travel.search"],
    cost=Cost(certainty=CostCertainty.FIXED, financial=None, compute={"latency_p50": "150ms", "tokens": 400}),
    session=SessionInfo(),
    response_modes=[ResponseMode.UNARY, ResponseMode.STREAMING],
    observability=ObservabilityContract(
        logged=True, retention="P90D",
        fields_logged=["capability", "parameters", "result_count"],
        audit_accessible_by=["delegation.root_principal"],
    ),
    # Cross-service hints (illustrative — this is a single-service showcase)
    cross_service=CrossServiceHints(
        handoff_to=[ServiceCapabilityRef(service="travel-booking", capability="book_flight")],
    ),
)


def _handle_search(ctx: InvocationContext, params: dict) -> dict:
    origin = params.get("origin")
    destination = params.get("destination")
    if not origin or not destination:
        raise ANIPError("invalid_parameters", "origin and destination are required")

    flights = data.search_flights(origin, destination)
    return {
        "flights": [
            {
                "flight_number": f.flight_number,
                "origin": f.origin,
                "destination": f.destination,
                "departure_time": f.departure_time,
                "arrival_time": f.arrival_time,
                "price": f.price,
                "currency": f.currency,
                "stops": f.stops,
                "quote_id": {
                    "id": f"qt-{uuid.uuid4().hex[:8]}-{int(time.time())}",
                    "price": f.price,
                    "issued_at": int(time.time()),
                },
            }
            for f in flights
        ],
        "count": len(flights),
    }


search_flights = Capability(declaration=_SEARCH_DECL, handler=_handle_search)


# ---------------------------------------------------------------------------
# 2. check_availability — read-only
# ---------------------------------------------------------------------------

_AVAIL_DECL = CapabilityDeclaration(
    name="check_availability",
    description="Check seat availability and price for a specific flight",
    contract_version="1.0",
    inputs=[
        CapabilityInput(name="flight_number", type="string", description="Flight number to check"),
    ],
    output=CapabilityOutput(
        type="availability_info",
        fields=["available", "seats_remaining", "flight_number", "price"],
    ),
    side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
    minimum_scope=["travel.search"],
    cost=Cost(certainty=CostCertainty.FIXED, financial=None, compute={"latency_p50": "50ms", "tokens": 200}),
    session=SessionInfo(),
    observability=ObservabilityContract(
        logged=True, retention="P90D",
        fields_logged=["capability", "parameters", "result"],
        audit_accessible_by=["delegation.root_principal"],
    ),
)


def _handle_availability(ctx: InvocationContext, params: dict) -> dict:
    flight_number = params.get("flight_number")
    if not flight_number:
        raise ANIPError("invalid_parameters", "flight_number is required")

    result = data.check_availability(flight_number)
    if not result["available"] and result.get("reason") == "flight_not_found":
        raise ANIPError("capability_unavailable", f"Flight {flight_number} not found")
    return result


check_availability = Capability(declaration=_AVAIL_DECL, handler=_handle_availability)


# ---------------------------------------------------------------------------
# 3. book_flight — irreversible, financial cost, requires search_flights
# ---------------------------------------------------------------------------

_BOOK_DECL = CapabilityDeclaration(
    name="book_flight",
    description="Book a confirmed flight reservation",
    contract_version="1.0",
    inputs=[
        CapabilityInput(name="flight_number", type="string", description="Flight to book"),
        CapabilityInput(name="quote_id", type="object", required=True, description="Priced quote from search_flights containing id, price, and issued_at"),
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
        financial=FinancialCost(
            currency="USD",
            range_min=280,
            range_max=500,
            typical=420,
        ),
        determined_by="search_flights",
        compute={"latency_p50": "1s", "tokens": 1000},
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
    # Cross-service hints (illustrative — this is a single-service showcase)
    cross_service=CrossServiceHints(
        refresh_via=[ServiceCapabilityRef(service="travel-search", capability="search_flights")],
    ),
)


def _handle_book(ctx: InvocationContext, params: dict) -> dict:
    flight_number = params.get("flight_number")
    passengers = params.get("passengers", 1)
    quote_id = params.get("quote_id")
    if isinstance(quote_id, dict):
        booking_ref = quote_id.get("id", "")
        quoted_price = quote_id.get("price")
    else:
        booking_ref = quote_id  # backward compat for plain strings
        quoted_price = None

    if not flight_number:
        raise ANIPError("invalid_parameters", "flight_number is required")

    flight = data.get_flight(flight_number)
    if flight is None:
        raise ANIPError(
            "capability_unavailable",
            f"Flight {flight_number} not found",
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

    if flight.seats_available < passengers:
        raise ANIPError(
            "capability_unavailable",
            f"Only {flight.seats_available} seats left on {flight_number}",
            resolution={
                "action": "check_availability",
                "recovery_class": "refresh_then_retry",
                "recovery_target": {
                    "kind": "refresh",
                    "target": {"service": "travel-booking", "capability": "check_availability"},
                    "continuity": "same_task",
                    "retry_after_target": True,
                },
            },
        )

    booking = data.create_booking(
        flight=flight,
        passengers=passengers,
        booked_by=ctx.subject,
        on_behalf_of=ctx.root_principal,
    )

    ctx.set_cost_actual({"financial": {"amount": booking.total_cost, "currency": booking.flight.currency}})

    return {
        "booking_id": booking.booking_id,
        "flight_number": booking.flight.flight_number,
        "departure_time": booking.flight.departure_time,
        "total_cost": booking.total_cost,
        "currency": booking.flight.currency,
    }


book_flight = Capability(declaration=_BOOK_DECL, handler=_handle_book)


# ---------------------------------------------------------------------------
# 4. cancel_booking — transactional, rollback window PT24H
# ---------------------------------------------------------------------------

_CANCEL_DECL = CapabilityDeclaration(
    name="cancel_booking",
    description="Cancel an existing flight booking",
    contract_version="1.0",
    inputs=[
        CapabilityInput(name="booking_id", type="string", description="Booking ID to cancel"),
    ],
    output=CapabilityOutput(
        type="cancellation_confirmation",
        fields=["booking_id", "status", "refund_amount"],
    ),
    side_effect=SideEffect(type=SideEffectType.TRANSACTIONAL, rollback_window="PT24H"),
    minimum_scope=["travel.book"],
    cost=Cost(certainty=CostCertainty.FIXED, financial=None, compute={"latency_p50": "500ms", "tokens": 300}),
    session=SessionInfo(),
    observability=ObservabilityContract(
        logged=True, retention="P90D",
        fields_logged=["capability", "delegation_chain", "parameters", "result"],
        audit_accessible_by=["delegation.root_principal"],
    ),
)


def _handle_cancel(ctx: InvocationContext, params: dict) -> dict:
    booking_id = params.get("booking_id")
    if not booking_id:
        raise ANIPError("invalid_parameters", "booking_id is required")

    try:
        booking = data.cancel_booking(booking_id)
    except KeyError:
        raise ANIPError(
            "capability_unavailable",
            f"Booking {booking_id} not found",
            resolution={
                "action": "revalidate_booking_id",
                "recovery_class": "revalidation",
                "recovery_target": {
                    "kind": "revalidation",
                    "continuity": "same_task",
                    "retry_after_target": True,
                },
            },
        )
    except ValueError as exc:
        raise ANIPError("invalid_parameters", str(exc))

    return {
        "booking_id": booking.booking_id,
        "status": booking.status,
        "refund_amount": booking.total_cost,
        "currency": booking.flight.currency,
    }


cancel_booking = Capability(declaration=_CANCEL_DECL, handler=_handle_cancel)
