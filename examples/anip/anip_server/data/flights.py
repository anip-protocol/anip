"""Flight data — static inventory + SQLite-persisted bookings."""

from __future__ import annotations

from dataclasses import dataclass

from .database import load_booking, next_booking_id, store_booking


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
    booked_by: str  # delegation chain subject
    on_behalf_of: str  # root principal


# Stub flight inventory (static — doesn't need persistence)
FLIGHTS: list[Flight] = [
    Flight("AA100", "SEA", "SFO", "2026-03-10", "08:00", "10:15", 420.00),
    Flight("UA205", "SEA", "SFO", "2026-03-10", "11:30", "13:45", 380.00),
    Flight("DL310", "SEA", "SFO", "2026-03-10", "14:00", "18:30", 280.00, stops=1),
    Flight("AA101", "SEA", "SFO", "2026-03-11", "08:00", "10:15", 310.00),
    Flight("UA450", "SEA", "LAX", "2026-03-10", "09:00", "11:30", 350.00),
    Flight("DL520", "SFO", "JFK", "2026-03-12", "06:00", "14:30", 580.00),
]


def search_flights(origin: str, destination: str, date: str) -> list[Flight]:
    return [
        f for f in FLIGHTS
        if f.origin == origin and f.destination == destination and f.date == date
    ]


def get_flight(flight_number: str, date: str) -> Flight | None:
    for f in FLIGHTS:
        if f.flight_number == flight_number and f.date == date:
            return f
    return None


def create_booking(
    flight: Flight,
    passengers: int,
    booked_by: str,
    on_behalf_of: str,
) -> Booking:
    booking_id = next_booking_id()
    booking = Booking(
        booking_id=booking_id,
        flight=flight,
        passengers=passengers,
        total_cost=flight.price * passengers,
        booked_by=booked_by,
        on_behalf_of=on_behalf_of,
    )
    # Persist to SQLite
    store_booking({
        "booking_id": booking_id,
        "flight_number": flight.flight_number,
        "flight_date": flight.date,
        "passengers": passengers,
        "total_cost": booking.total_cost,
        "currency": flight.currency,
        "booked_by": booked_by,
        "on_behalf_of": on_behalf_of,
    })
    return booking


def get_booking(booking_id: str) -> dict | None:
    return load_booking(booking_id)
