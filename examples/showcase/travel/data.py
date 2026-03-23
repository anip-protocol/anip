"""Static flight data and in-memory booking store for the travel showcase."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Flight:
    """A scheduled flight."""
    flight_number: str
    origin: str
    destination: str
    departure_time: str
    arrival_time: str
    price: float
    currency: str = "USD"
    stops: int = 0
    seats_available: int = 42


@dataclass
class Booking:
    """A confirmed booking."""
    booking_id: str
    flight: Flight
    passengers: int
    total_cost: float
    booked_by: str
    on_behalf_of: str
    status: str = "confirmed"
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


# ---------------------------------------------------------------------------
# Static flight inventory — 8 flights across multiple routes
# ---------------------------------------------------------------------------

FLIGHTS: list[Flight] = [
    Flight("SK100", "SEA", "SFO", "2026-04-01T08:00", "2026-04-01T10:15", 180.00),
    Flight("SK101", "SFO", "SEA", "2026-04-01T12:30", "2026-04-01T14:45", 195.00),
    Flight("SK200", "SEA", "LAX", "2026-04-01T07:00", "2026-04-01T09:45", 220.00),
    Flight("SK201", "LAX", "SEA", "2026-04-01T16:00", "2026-04-01T18:45", 235.00),
    Flight("SK300", "SEA", "JFK", "2026-04-01T06:00", "2026-04-01T14:30", 450.00, stops=1),
    Flight("SK301", "SEA", "SFO", "2026-04-01T17:00", "2026-04-01T19:15", 210.00),
    Flight("SK302", "SEA", "LAX", "2026-04-01T14:00", "2026-04-01T16:45", 250.00),
    Flight("SK303", "SEA", "JFK", "2026-04-01T10:00", "2026-04-01T18:00", 550.00, stops=0),
]

_FLIGHT_INDEX: dict[str, Flight] = {f.flight_number: f for f in FLIGHTS}

# In-memory booking store
_BOOKINGS: dict[str, Booking] = {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def search_flights(origin: str, destination: str) -> list[Flight]:
    """Return all flights matching origin and destination."""
    origin_upper = origin.upper()
    dest_upper = destination.upper()
    return [f for f in FLIGHTS if f.origin == origin_upper and f.destination == dest_upper]


def get_flight(number: str) -> Flight | None:
    """Look up a single flight by number."""
    return _FLIGHT_INDEX.get(number.upper())


def check_availability(number: str) -> dict:
    """Return availability info for a flight."""
    flight = _FLIGHT_INDEX.get(number.upper())
    if flight is None:
        return {"available": False, "reason": "flight_not_found"}
    return {
        "available": flight.seats_available > 0,
        "seats_remaining": flight.seats_available,
        "flight_number": flight.flight_number,
        "price": flight.price,
        "currency": flight.currency,
    }


def create_booking(
    flight: Flight,
    passengers: int,
    booked_by: str,
    on_behalf_of: str,
) -> Booking:
    """Create a new booking, decrementing seat availability."""
    if flight.seats_available < passengers:
        raise ValueError(f"Only {flight.seats_available} seats left on {flight.flight_number}")
    flight.seats_available -= passengers
    booking = Booking(
        booking_id=f"BK-{uuid.uuid4().hex[:8].upper()}",
        flight=flight,
        passengers=passengers,
        total_cost=round(flight.price * passengers, 2),
        booked_by=booked_by,
        on_behalf_of=on_behalf_of,
    )
    _BOOKINGS[booking.booking_id] = booking
    return booking


def cancel_booking(booking_id: str) -> Booking:
    """Cancel a booking, restoring seat availability."""
    booking = _BOOKINGS.get(booking_id)
    if booking is None:
        raise KeyError(f"Booking {booking_id} not found")
    if booking.status == "cancelled":
        raise ValueError(f"Booking {booking_id} is already cancelled")
    booking.status = "cancelled"
    booking.flight.seats_available += booking.passengers
    return booking
