from fastapi import FastAPI
from anip_core import (
    CapabilityDeclaration, CapabilityInput, CapabilityOutput,
    SideEffect, SideEffectType,
)
from anip_fastapi import mount_anip
from anip_service import ANIPService, Capability


# Your business logic. Nothing here knows about ANIP.
def do_search(origin, destination):
    return [
        {"flight_number": "AA100", "origin": origin, "destination": destination, "price": 420},
        {"flight_number": "DL310", "origin": origin, "destination": destination, "price": 280},
    ]


def do_book(flight_number):
    return {"booking_id": "BK-0001", "flight_number": flight_number}


# A capability that only reads.
search_flights = Capability(
    declaration=CapabilityDeclaration(
        name="search_flights",
        description="Search available flights between two airports",
        contract_version="1.0",
        inputs=[
            CapabilityInput(name="origin", type="string", description="Departure airport"),
            CapabilityInput(name="destination", type="string", description="Arrival airport"),
        ],
        output=CapabilityOutput(type="object", fields=["flights"]),
        side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
        minimum_scope=["travel.search"],
    ),
    handler=lambda ctx, params: {"flights": do_search(params["origin"], params["destination"])},
)

# A capability that cannot be undone, and needs a different scope.
book_flight = Capability(
    declaration=CapabilityDeclaration(
        name="book_flight",
        description="Book a flight",
        contract_version="1.0",
        inputs=[
            CapabilityInput(name="flight_number", type="string", description="Flight to book"),
        ],
        output=CapabilityOutput(type="object", fields=["booking_id", "flight_number"]),
        side_effect=SideEffect(type=SideEffectType.IRREVERSIBLE, rollback_window="none"),
        minimum_scope=["travel.book"],
    ),
    handler=lambda ctx, params: do_book(params["flight_number"]),
)

service = ANIPService(
    service_id="quickstart-flights",
    capabilities=[search_flights, book_flight],
    storage=":memory:",
    trust="signed",
    # Who is calling? Map your own API keys or sessions to a principal.
    authenticate=lambda bearer: {"demo-key": "human:demo@example.com"}.get(bearer),
)

app = FastAPI()
mount_anip(app, service)
