# Showcase App: Travel Booking — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a rich travel booking showcase app at `examples/showcase/travel/` that demonstrates ANIP's core value proposition — cost awareness, budget enforcement, delegation, capability prerequisites, streaming, and audit trails — in an accessible, easy-to-understand domain.

**Architecture:** Standalone Python FastAPI service with 4 capabilities (`search_flights`, `check_availability`, `book_flight`, `cancel_booking`), mounting all four HTTP surfaces (ANIP protocol + REST + GraphQL + MCP Streamable HTTP). Includes a `demo.py` agent interaction script. Follows the exact same patterns as `examples/anip/` but with richer capabilities and a more complete demo flow.

**Tech Stack:** Python 3.11+, FastAPI, `anip-service`, `anip-fastapi`, `anip-rest`, `anip-graphql`, `anip-mcp`, `httpx` (for demo client).

---

## File Structure

```
examples/showcase/travel/
├── README.md                    # What this demonstrates, how to run it
├── app.py                       # FastAPI app with all 4 surfaces mounted
├── capabilities.py              # 4 capability declarations + handlers
├── data.py                      # Static flight/booking data
├── demo.py                      # Scripted agent interaction (8 steps)
└── requirements.txt             # Python deps
```

---

## Task 1: Data Layer + Capability Declarations

**Files:**
- Create: `examples/showcase/travel/data.py`
- Create: `examples/showcase/travel/capabilities.py`

- [ ] **Step 1: Create data.py**

Static flight data + booking store. Richer than the simple example — more flights, multiple routes, price variation to make budget enforcement meaningful.

```python
"""Static flight data and in-memory booking store for the travel showcase."""
import uuid
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class Flight:
    flight_number: str
    origin: str
    destination: str
    departure_time: str
    arrival_time: str
    price: float
    currency: str = "USD"
    stops: int = 0
    available_seats: int = 50

FLIGHTS = [
    Flight("AA100", "SEA", "SFO", "08:00", "10:15", 420.00, stops=0),
    Flight("UA205", "SEA", "SFO", "11:30", "13:45", 380.00, stops=0),
    Flight("DL310", "SEA", "SFO", "14:00", "18:30", 280.00, stops=1),
    Flight("AA200", "SFO", "SEA", "09:00", "11:15", 390.00, stops=0),
    Flight("SW400", "SEA", "LAX", "07:00", "09:30", 250.00, stops=0),
    Flight("UA501", "SEA", "LAX", "12:00", "16:00", 180.00, stops=1),
    Flight("DL600", "LAX", "SEA", "15:00", "17:30", 320.00, stops=0),
    Flight("AA700", "SEA", "JFK", "06:00", "14:30", 550.00, stops=1),
]

@dataclass
class Booking:
    booking_id: str
    flight_number: str
    origin: str
    destination: str
    departure_time: str
    price: float
    currency: str
    passengers: int
    total_cost: float
    booked_by: str
    on_behalf_of: str
    status: str = "confirmed"
    booked_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

# In-memory booking store
_bookings: dict[str, Booking] = {}

def search_flights(origin: str, destination: str) -> list[Flight]:
    return [f for f in FLIGHTS if f.origin == origin and f.destination == destination]

def get_flight(flight_number: str) -> Flight | None:
    return next((f for f in FLIGHTS if f.flight_number == flight_number), None)

def check_availability(flight_number: str) -> dict:
    flight = get_flight(flight_number)
    if not flight:
        return {"available": False, "reason": "flight_not_found"}
    booked = sum(1 for b in _bookings.values()
                 if b.flight_number == flight_number and b.status == "confirmed")
    remaining = flight.available_seats - booked
    return {
        "available": remaining > 0,
        "remaining_seats": remaining,
        "flight_number": flight_number,
        "price": flight.price,
        "currency": flight.currency,
    }

def create_booking(flight: Flight, passengers: int, booked_by: str, on_behalf_of: str) -> Booking:
    booking = Booking(
        booking_id=f"BK-{uuid.uuid4().hex[:6].upper()}",
        flight_number=flight.flight_number,
        origin=flight.origin,
        destination=flight.destination,
        departure_time=flight.departure_time,
        price=flight.price,
        currency=flight.currency,
        passengers=passengers,
        total_cost=flight.price * passengers,
        booked_by=booked_by,
        on_behalf_of=on_behalf_of,
    )
    _bookings[booking.booking_id] = booking
    return booking

def cancel_booking(booking_id: str) -> Booking | None:
    booking = _bookings.get(booking_id)
    if booking and booking.status == "confirmed":
        booking.status = "cancelled"
        return booking
    return None

def get_booking(booking_id: str) -> Booking | None:
    return _bookings.get(booking_id)
```

- [ ] **Step 2: Create capabilities.py**

Four capabilities with full declarations:

```python
"""ANIP capability declarations and handlers for the travel showcase."""
from anip_service import Capability, InvocationContext, ANIPError
from anip_core import (
    CapabilityDeclaration, CapabilityInput, CapabilityOutput,
    CapabilityRequirement, Cost, SideEffect,
)
from . import data

# --- 1. search_flights (read, streaming) ---

search_flights = Capability(
    declaration=CapabilityDeclaration(
        name="search_flights",
        description="Search available flights by origin and destination",
        contract_version="1.0",
        inputs=[
            CapabilityInput(name="origin", type="airport_code", description="Departure airport (e.g. SEA)"),
            CapabilityInput(name="destination", type="airport_code", description="Arrival airport (e.g. SFO)"),
        ],
        output=CapabilityOutput(type="flight_list", fields=["flight_number", "price", "departure_time", "arrival_time", "stops"]),
        side_effect=SideEffect(type="read", rollback_window="not_applicable"),
        minimum_scope=["travel.search"],
        cost=Cost(certainty="fixed", compute={"latency_p50": "200ms"}),
        response_modes=["unary", "streaming"],
    ),
    handler=_handle_search_flights,
)

async def _handle_search_flights(ctx: InvocationContext, params: dict) -> dict:
    origin = params.get("origin", "").upper()
    destination = params.get("destination", "").upper()
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
            }
            for f in flights
        ],
        "count": len(flights),
    }

# --- 2. check_availability (read) ---

check_availability = Capability(
    declaration=CapabilityDeclaration(
        name="check_availability",
        description="Check seat availability and current price for a specific flight",
        contract_version="1.0",
        inputs=[
            CapabilityInput(name="flight_number", type="string", description="Flight number (e.g. AA100)"),
        ],
        output=CapabilityOutput(type="availability", fields=["available", "remaining_seats", "price"]),
        side_effect=SideEffect(type="read", rollback_window="not_applicable"),
        minimum_scope=["travel.search"],
    ),
    handler=_handle_check_availability,
)

async def _handle_check_availability(ctx: InvocationContext, params: dict) -> dict:
    flight_number = params.get("flight_number", "").upper()
    if not flight_number:
        raise ANIPError("invalid_parameters", "flight_number is required")
    return data.check_availability(flight_number)

# --- 3. book_flight (irreversible, financial cost) ---

book_flight = Capability(
    declaration=CapabilityDeclaration(
        name="book_flight",
        description="Book a confirmed flight reservation (irreversible — charges are final)",
        contract_version="1.0",
        inputs=[
            CapabilityInput(name="flight_number", type="string", description="Flight to book"),
            CapabilityInput(name="passengers", type="integer", required=False, default=1, description="Number of passengers"),
        ],
        output=CapabilityOutput(type="booking_confirmation", fields=["booking_id", "flight_number", "total_cost", "status"]),
        side_effect=SideEffect(type="irreversible", rollback_window="none"),
        minimum_scope=["travel.book"],
        cost=Cost(
            certainty="estimated",
            financial={"range_min": 180, "range_max": 550, "typical": 380, "currency": "USD"},
            determined_by="search_flights",
        ),
        requires=[
            CapabilityRequirement(capability="search_flights", reason="Must search available flights before booking"),
        ],
    ),
    handler=_handle_book_flight,
)

async def _handle_book_flight(ctx: InvocationContext, params: dict) -> dict:
    flight_number = params.get("flight_number", "").upper()
    passengers = params.get("passengers", 1)
    if not flight_number:
        raise ANIPError("invalid_parameters", "flight_number is required")

    flight = data.get_flight(flight_number)
    if not flight:
        raise ANIPError("not_found", f"Flight {flight_number} not found")

    avail = data.check_availability(flight_number)
    if not avail["available"]:
        raise ANIPError("unavailable", f"Flight {flight_number} is fully booked")

    booking = data.create_booking(flight, passengers, ctx.subject, ctx.root_principal)
    ctx.set_cost_actual({"financial": {"amount": booking.total_cost, "currency": booking.currency}})

    return {
        "booking_id": booking.booking_id,
        "flight_number": booking.flight_number,
        "origin": booking.origin,
        "destination": booking.destination,
        "departure_time": booking.departure_time,
        "total_cost": booking.total_cost,
        "currency": booking.currency,
        "passengers": booking.passengers,
        "status": booking.status,
    }

# --- 4. cancel_booking (transactional, rollback window) ---

cancel_booking = Capability(
    declaration=CapabilityDeclaration(
        name="cancel_booking",
        description="Cancel a confirmed booking within the cancellation window",
        contract_version="1.0",
        inputs=[
            CapabilityInput(name="booking_id", type="string", description="Booking ID to cancel (e.g. BK-ABC123)"),
        ],
        output=CapabilityOutput(type="cancellation", fields=["booking_id", "status", "refund_amount"]),
        side_effect=SideEffect(type="transactional", rollback_window="PT24H"),
        minimum_scope=["travel.book"],
    ),
    handler=_handle_cancel_booking,
)

async def _handle_cancel_booking(ctx: InvocationContext, params: dict) -> dict:
    booking_id = params.get("booking_id", "")
    if not booking_id:
        raise ANIPError("invalid_parameters", "booking_id is required")

    booking = data.cancel_booking(booking_id)
    if not booking:
        raise ANIPError("not_found", f"Booking {booking_id} not found or already cancelled")

    return {
        "booking_id": booking.booking_id,
        "status": "cancelled",
        "refund_amount": booking.total_cost,
        "currency": booking.currency,
    }
```

**Important:** The handler functions must be defined BEFORE the `Capability()` calls that reference them. In the code above, move the handler function definitions above the `Capability()` instantiations, or use a factory pattern. The exact Python pattern used in `examples/anip/` should be followed — read how that example structures it.

- [ ] **Step 3: Verify capability import structure**

The capabilities need to work as a module import. Create `examples/showcase/travel/__init__.py` if needed, or structure as flat files.

- [ ] **Step 4: Commit**

```bash
git add examples/showcase/travel/data.py examples/showcase/travel/capabilities.py
git commit -m "feat(showcase): add travel booking data layer and capabilities"
```

---

## Task 2: FastAPI App with All Surfaces

**Files:**
- Create: `examples/showcase/travel/app.py`
- Create: `examples/showcase/travel/requirements.txt`

- [ ] **Step 1: Create app.py**

```python
"""ANIP Travel Booking Showcase — demonstrates cost awareness, budget enforcement,
delegation, prerequisites, streaming, and audit in an accessible domain."""
import os
from fastapi import FastAPI
from anip_service import ANIPService
from anip_fastapi import mount_anip
from anip_rest import mount_anip_rest
from anip_graphql import mount_anip_graphql
from anip_mcp import mount_anip_mcp_http

from capabilities import search_flights, check_availability, book_flight, cancel_booking

API_KEYS = {
    "demo-human-key": "human:samir@example.com",
    "demo-agent-key": "agent:demo-agent",
}

service = ANIPService(
    service_id="anip-travel-showcase",
    capabilities=[search_flights, check_availability, book_flight, cancel_booking],
    storage=os.getenv("ANIP_STORAGE", ":memory:"),
    trust=os.getenv("ANIP_TRUST_LEVEL", "signed"),
    key_path=os.getenv("ANIP_KEY_PATH", "./anip-keys"),
    authenticate=lambda bearer: API_KEYS.get(bearer),
)

app = FastAPI(title="ANIP Travel Booking Showcase")

# Mount all four HTTP surfaces
mount_anip(app, service, health_endpoint=True)
mount_anip_rest(app, service)
mount_anip_graphql(app, service)
mount_anip_mcp_http(app, service)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
```

- [ ] **Step 2: Create requirements.txt**

```
anip-service
anip-fastapi
anip-rest
anip-graphql
anip-mcp
uvicorn
httpx
```

Note: These are editable installs from the repo. The requirements may need paths like `-e ../../packages/python/anip-service` etc. Check how the existing `examples/anip/` handles this.

- [ ] **Step 3: Start the app and smoke test**

```bash
cd examples/showcase/travel
pip install -r requirements.txt  # or editable install
python app.py &
sleep 3
curl -sf http://localhost:8000/.well-known/anip | head -c 200
curl -sf http://localhost:8000/rest/openapi.json | head -c 200
curl -sf http://localhost:8000/schema.graphql | head -c 200
kill %1
```

- [ ] **Step 4: Commit**

```bash
git add examples/showcase/travel/app.py examples/showcase/travel/requirements.txt
git commit -m "feat(showcase): add travel booking FastAPI app with all surfaces"
```

---

## Task 3: Demo Script

**Files:**
- Create: `examples/showcase/travel/demo.py`

The demo script runs an 8-step agent interaction that demonstrates the core ANIP value propositions. It uses `httpx` directly (not the Claude agent loop — that's the existing `examples/agent/`). This is a scripted walkthrough, not an autonomous agent.

- [ ] **Step 1: Create demo.py**

The demo flow:

1. **Discovery** — fetch `/.well-known/anip`, show capabilities and posture
2. **Token issuance** — request search token (travel.search) and booking token (travel.book:max_$300)
3. **Permission check** — verify what the agent can do with each token
4. **Search flights** — invoke `search_flights` SEA→SFO, show results with prices
5. **Budget wall** — attempt to book AA100 ($420) with $300 budget → budget_exceeded failure with resolution
6. **Budget increase** — request new token with $500 budget (simulated human approval)
7. **Successful booking** — book with new token, show cost_actual
8. **Audit verification** — query audit log, show the full trail

Each step prints formatted output showing what's happening and what ANIP metadata is involved.

```python
#!/usr/bin/env python3
"""Travel Booking Showcase Demo — 8-step scripted agent interaction."""
import json
import sys
import httpx

BASE_URL = "http://127.0.0.1:8000"
API_KEY = "demo-human-key"

def main():
    client = httpx.Client(base_url=BASE_URL, timeout=10)

    print("=" * 70)
    print("ANIP Travel Booking Showcase")
    print("=" * 70)

    # Step 1: Discovery
    print("\n--- Step 1: Discovery ---")
    discovery = client.get("/.well-known/anip").json()
    caps = discovery["anip_discovery"]["capabilities"]
    print(f"Service: {discovery['anip_discovery'].get('base_url', BASE_URL)}")
    print(f"Protocol: {discovery['anip_discovery']['protocol']}")
    print(f"Capabilities: {', '.join(caps.keys())}")
    for name, cap in caps.items():
        print(f"  {name}: {cap['side_effect']} | scope: {cap['minimum_scope']}")

    # Step 2: Token issuance with scope narrowing
    print("\n--- Step 2: Token Issuance (Scope Narrowing) ---")
    # First: human gets a broad travel token
    broad_resp = client.post("/anip/tokens",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"subject": "agent:travel-bot", "scope": ["travel.search", "travel.book:max_$300"],
              "capability": "search_flights"}).json()
    broad_jwt = broad_resp["token"]
    print(f"Broad token: {broad_resp['token_id']} (scope: travel.search + travel.book:max_$300)")

    # Then: agent narrows to search-only child token
    search_resp = client.post("/anip/tokens",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"subject": "agent:travel-bot", "scope": ["travel.search"],
              "capability": "search_flights", "parent_token": broad_jwt}).json()
    search_jwt = search_resp["token"]
    print(f"  → Narrowed search token: {search_resp['token_id']} (scope: travel.search only)")

    # And: agent narrows to booking-only child token
    book_resp = client.post("/anip/tokens",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"subject": "agent:travel-bot", "scope": ["travel.book:max_$300"],
              "capability": "book_flight", "parent_token": broad_jwt}).json()
    book_jwt = book_resp["token"]
    print(f"  → Narrowed booking token: {book_resp['token_id']} (scope: travel.book, budget: $300)")

    # Step 3: Permission check
    print("\n--- Step 3: Permission Check ---")
    search_perms = client.post("/anip/permissions",
        headers={"Authorization": f"Bearer {search_jwt}"}).json()
    print(f"With search token: {len(search_perms.get('available', []))} available, "
          f"{len(search_perms.get('restricted', []))} restricted")

    book_perms = client.post("/anip/permissions",
        headers={"Authorization": f"Bearer {book_jwt}"}).json()
    print(f"With booking token: {len(book_perms.get('available', []))} available, "
          f"{len(book_perms.get('restricted', []))} restricted")

    # Step 4: Search flights
    print("\n--- Step 4: Search Flights (SEA → SFO) ---")
    search_result = client.post("/anip/invoke/search_flights",
        headers={"Authorization": f"Bearer {search_jwt}"},
        json={"parameters": {"origin": "SEA", "destination": "SFO"}}).json()

    if search_result.get("success"):
        flights = search_result["result"]["flights"]
        print(f"Found {len(flights)} flights:")
        for f in flights:
            budget_note = "← within budget" if f["price"] <= 300 else "← EXCEEDS $300 budget"
            print(f"  {f['flight_number']}: {f['departure_time']}→{f['arrival_time']} "
                  f"${f['price']} ({f['stops']} stops) {budget_note}")

    # Step 5: Budget wall
    print("\n--- Step 5: Budget Wall ---")
    print("Attempting to book AA100 ($420) with $300 budget...")
    book_attempt = client.post("/anip/invoke/book_flight",
        headers={"Authorization": f"Bearer {book_jwt}"},
        json={"parameters": {"flight_number": "AA100"}})
    result = book_attempt.json()

    if not result.get("success"):
        failure = result.get("failure", {})
        print(f"BLOCKED: {failure.get('type')}")
        print(f"Detail: {failure.get('detail')}")
        resolution = failure.get("resolution", {})
        if resolution:
            print(f"Resolution: {resolution.get('action')} "
                  f"(grantable by: {resolution.get('grantable_by', 'N/A')})")

    # Step 6: Budget increase
    print("\n--- Step 6: Budget Increase ---")
    print("Requesting new token with $500 budget (simulated human approval)...")
    new_book_resp = client.post("/anip/tokens",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"subject": "agent:travel-bot", "scope": ["travel.book:max_$500"],
              "capability": "book_flight"}).json()
    new_book_jwt = new_book_resp["token"]
    print(f"New booking token: {new_book_resp['token_id']} (budget: $500)")

    # Step 7: Successful booking
    print("\n--- Step 7: Successful Booking ---")
    book_result = client.post("/anip/invoke/book_flight",
        headers={"Authorization": f"Bearer {new_book_jwt}"},
        json={"parameters": {"flight_number": "AA100"}}).json()

    if book_result.get("success"):
        r = book_result["result"]
        print(f"BOOKED: {r['booking_id']}")
        print(f"Flight: {r['flight_number']} {r['origin']}→{r['destination']}")
        print(f"Cost: ${r['total_cost']} {r['currency']}")
        if book_result.get("cost_actual"):
            ca = book_result["cost_actual"]
            print(f"Cost actual: ${ca.get('financial', {}).get('amount', 'N/A')}")

    # Step 8: Audit verification
    print("\n--- Step 8: Audit Verification ---")
    audit = client.post("/anip/audit",
        headers={"Authorization": f"Bearer {new_book_jwt}"},
        json={}).json()

    entries = audit.get("entries", [])
    print(f"Audit entries: {len(entries)}")
    for entry in entries[-5:]:  # Show last 5
        status = "SUCCESS" if entry.get("success") else f"FAILED ({entry.get('failure_type', 'unknown')})"
        print(f"  [{entry.get('capability', 'unknown')}] {status} "
              f"(class: {entry.get('event_class', 'N/A')})")

    print("\n" + "=" * 70)
    print("Demo complete. All ANIP primitives exercised.")
    print("=" * 70)

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test the demo**

```bash
cd examples/showcase/travel
python app.py &
sleep 3
python demo.py
kill %1
```

- [ ] **Step 3: Commit**

```bash
git add examples/showcase/travel/demo.py
git commit -m "feat(showcase): add travel booking demo script"
```

---

## Task 4: README + Conformance

**Files:**
- Create: `examples/showcase/travel/README.md`

- [ ] **Step 1: Create README.md**

```markdown
# ANIP Travel Booking Showcase

A rich demonstration of ANIP's core protocol features using a travel booking domain.

## What This Demonstrates

| ANIP Feature | How It Appears |
|---|---|
| Cost estimation vs actual | Search shows price estimates; booking confirms actual cost |
| Budget enforcement | Agent has a $300 budget; nonstop flights exceed it |
| Scope narrowing | Broad travel token → narrowed search-only and booking-only child tokens |
| Capability prerequisites | `book_flight` requires prior `search_flights` |
| Permission discovery | Agent checks what it can do before acting |
| Delegation chain | Human delegates to agent with bounded authority |
| Audit trail | Full invocation history with event classification |
| Side-effect typing | read (search), irreversible (book), transactional (cancel) |
| Streaming | Search results arrive as progressive SSE events |

## Capabilities

- `search_flights` — read, streaming. Search by origin/destination.
- `check_availability` — read. Check seats and price for a specific flight.
- `book_flight` — irreversible, financial cost. Book a confirmed reservation.
- `cancel_booking` — transactional, 24h rollback window. Cancel within window.

## Running

```bash
# Install dependencies (from repo root)
pip install -e packages/python/anip-service
pip install -e packages/python/anip-fastapi
pip install -e packages/python/anip-rest
pip install -e packages/python/anip-graphql
pip install -e packages/python/anip-mcp
pip install uvicorn httpx

# Start the service
cd examples/showcase/travel
python app.py

# In another terminal: run the demo
python demo.py
```

## Endpoints

- **ANIP Protocol:** `http://localhost:8000/.well-known/anip`
- **REST API:** `http://localhost:8000/rest/openapi.json`
- **GraphQL:** `http://localhost:8000/graphql`
- **MCP:** `http://localhost:8000/mcp`
- **Health:** `http://localhost:8000/-/health`

## Configuration

| Variable | Default | Description |
|---|---|---|
| `ANIP_STORAGE` | `:memory:` | Storage DSN (`:memory:` or `sqlite:///path.db`) |
| `ANIP_TRUST_LEVEL` | `signed` | Trust level (`signed` or `anchored`) |
| `ANIP_KEY_PATH` | `./anip-keys` | Key directory |
| `PORT` | `8000` | HTTP port |
```

- [ ] **Step 2: Run conformance**

```bash
cd examples/showcase/travel
python app.py &
sleep 3
pytest ../../conformance/ \
  --base-url=http://localhost:8000 \
  --bootstrap-bearer=demo-human-key \
  --sample-inputs=../../conformance/samples/flight-service.json \
  -v
kill %1
```

Expected: 43 passed, 1 skipped

- [ ] **Step 3: Commit and create PR**

```bash
git add examples/showcase/travel/
git commit -m "feat(showcase): complete travel booking showcase app"
```
