/**
 * Stub flight data — in-memory, no database.
 */

export interface Flight {
  flight_number: string;
  origin: string;
  destination: string;
  date: string;
  departure_time: string;
  arrival_time: string;
  price: number;
  currency: string;
  stops: number;
}

export interface Booking {
  booking_id: string;
  flight: Flight;
  passengers: number;
  total_cost: number;
  booked_by: string; // delegation chain subject
  on_behalf_of: string; // root principal
}

// Stub flight inventory
export const FLIGHTS: Flight[] = [
  {
    flight_number: "AA100",
    origin: "SEA",
    destination: "SFO",
    date: "2026-03-10",
    departure_time: "08:00",
    arrival_time: "10:15",
    price: 420.0,
    currency: "USD",
    stops: 0,
  },
  {
    flight_number: "UA205",
    origin: "SEA",
    destination: "SFO",
    date: "2026-03-10",
    departure_time: "11:30",
    arrival_time: "13:45",
    price: 380.0,
    currency: "USD",
    stops: 0,
  },
  {
    flight_number: "DL310",
    origin: "SEA",
    destination: "SFO",
    date: "2026-03-10",
    departure_time: "14:00",
    arrival_time: "18:30",
    price: 280.0,
    currency: "USD",
    stops: 1,
  },
  {
    flight_number: "AA101",
    origin: "SEA",
    destination: "SFO",
    date: "2026-03-11",
    departure_time: "08:00",
    arrival_time: "10:15",
    price: 310.0,
    currency: "USD",
    stops: 0,
  },
  {
    flight_number: "UA450",
    origin: "SEA",
    destination: "LAX",
    date: "2026-03-10",
    departure_time: "09:00",
    arrival_time: "11:30",
    price: 350.0,
    currency: "USD",
    stops: 0,
  },
  {
    flight_number: "DL520",
    origin: "SFO",
    destination: "JFK",
    date: "2026-03-12",
    departure_time: "06:00",
    arrival_time: "14:30",
    price: 580.0,
    currency: "USD",
    stops: 0,
  },
];

// In-memory booking store
const bookings: Map<string, Booking> = new Map();
let nextBookingId = 1;

export function searchFlights(
  origin: string,
  destination: string,
  date: string
): Flight[] {
  return FLIGHTS.filter(
    (f) => f.origin === origin && f.destination === destination && f.date === date
  );
}

export function getFlight(
  flightNumber: string,
  date: string
): Flight | null {
  for (const f of FLIGHTS) {
    if (f.flight_number === flightNumber && f.date === date) {
      return f;
    }
  }
  return null;
}

export function createBooking(
  flight: Flight,
  passengers: number,
  bookedBy: string,
  onBehalfOf: string
): Booking {
  const bookingId = `BK-${String(nextBookingId).padStart(4, "0")}`;
  nextBookingId += 1;
  const booking: Booking = {
    booking_id: bookingId,
    flight,
    passengers,
    total_cost: flight.price * passengers,
    booked_by: bookedBy,
    on_behalf_of: onBehalfOf,
  };
  bookings.set(bookingId, booking);
  return booking;
}

export function getBooking(bookingId: string): Booking | null {
  return bookings.get(bookingId) ?? null;
}
