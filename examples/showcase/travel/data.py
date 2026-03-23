"""Static flight data and in-memory booking store for the travel showcase."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import timezone
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
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Static flight inventory — 8 flights across multiple routes
# ---------------------------------------------------------------------------

FLIGHTS: list[Flight] = [
    Flight("AA100", "SEA", "SFO", "08:00", "10:15", 420.00, stops=0),
    Flight("UA205", "SEA", "SFO", "11:30", "13:45", 380.00, stops=0),
    Flight("DL310", "SEA", "SFO", "14:00", "18:30", 280.00, stops=1),
    Flight("AA200", "SFO", "SEA", "09:00", "11:15", 390.00, stops=0),
    Flight("SW400", "SEA", "LAX", "07:00", "09:30", 250.00, stops=0),
    Flight("UA501", "SEA", "LAX", "12:00", "16:00", 180.00, stops=1),
    Flight("DL600", "LAX", "SEA", "15:00", "17:30", 320.00, stops=0),
    Flight("AA700", "SEA", "JFK", "06:00", "14:30", 550.00, stops=1),
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
