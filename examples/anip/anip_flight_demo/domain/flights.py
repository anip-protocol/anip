"""Flight data and booking logic -- pure business domain, ANIP-free."""
from __future__ import annotations

from dataclasses import dataclass
import uuid


@dataclass
class Flight:
    flight_number: str
    origin: str
    destination: str
    date: str
    departure_time: str
    arrival_time: str
    price: float
    currency: str = "USD"
    stops: int = 0


@dataclass
class Booking:
    booking_id: str
    flight: Flight
    passengers: int
    total_cost: float
    booked_by: str
    on_behalf_of: str


# Static flight inventory
FLIGHTS: list[Flight] = [
    Flight("AA100", "SEA", "SFO", "2026-03-10", "08:00", "10:15", 420.00),
    Flight("UA205", "SEA", "SFO", "2026-03-10", "11:30", "13:45", 380.00),
    Flight("DL310", "SEA", "SFO", "2026-03-10", "14:00", "18:30", 280.00, stops=1),
    Flight("AA101", "SEA", "SFO", "2026-03-11", "08:00", "10:15", 310.00),
    Flight("UA450", "SEA", "LAX", "2026-03-10", "09:00", "11:30", 350.00),
    Flight("DL520", "SFO", "JFK", "2026-03-12", "06:00", "14:30", 580.00),
]

_bookings: dict[str, Booking] = {}


def search_flights(origin: str, destination: str, date: str) -> list[Flight]:
    return [f for f in FLIGHTS if f.origin == origin and f.destination == destination and f.date == date]


def get_flight(flight_number: str, date: str) -> Flight | None:
    for f in FLIGHTS:
        if f.flight_number == flight_number and f.date == date:
            return f
    return None


def create_booking(flight: Flight, passengers: int, booked_by: str, on_behalf_of: str) -> Booking:
    booking = Booking(
        booking_id=f"BK-{uuid.uuid4().hex[:8].upper()}",
        flight=flight,
        passengers=passengers,
        total_cost=flight.price * passengers,
        booked_by=booked_by,
        on_behalf_of=on_behalf_of,
    )
    _bookings[booking.booking_id] = booking
    return booking


def get_booking(booking_id: str) -> Booking | None:
    return _bookings.get(booking_id)
