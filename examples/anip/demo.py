#!/usr/bin/env python3
"""ANIP Demo — An agent interacting with an ANIP-compliant flight service.

Demonstrates the full protocol flow:
1. Profile handshake
2. Delegation chain construction (human → orchestrator → booking agent)
3. Permission discovery
4. Capability graph traversal
5. Capability invocation (search, then book)
6. Failure scenarios (insufficient scope, budget exceeded, purpose mismatch)

Run the server first:
    cd examples/anip
    pip install -e .
    uvicorn anip_server.main:app --reload

Then run this demo:
    python demo.py
"""

from __future__ import annotations

import httpx
from datetime import datetime, timedelta, timezone


BASE = "http://localhost:8000"
BLUE = "\033[94m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def header(text: str) -> None:
    print(f"\n{'='*70}")
    print(f"{BOLD}{text}{RESET}")
    print(f"{'='*70}")


def step(text: str) -> None:
    print(f"\n{BLUE}→ {text}{RESET}")


def success(text: str) -> None:
    print(f"  {GREEN}✓ {text}{RESET}")


def fail(text: str) -> None:
    print(f"  {RED}✗ {text}{RESET}")


def info(text: str) -> None:
    print(f"  {DIM}{text}{RESET}")


def warn(text: str) -> None:
    print(f"  {YELLOW}⚠ {text}{RESET}")


def dump(label: str, data: dict, indent: int = 4) -> None:
    import json
    print(f"  {label}:")
    for line in json.dumps(data, indent=2, default=str).split("\n"):
        print(f"{' ' * indent}{line}")


def main():
    client = httpx.Client(base_url=BASE, timeout=10)
    expires = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()

    # =================================================================
    # PHASE 1: Profile Handshake
    # =================================================================
    header("PHASE 1: Profile Handshake")
    step("Agent checks if service meets its requirements")

    resp = client.post("/anip/handshake", json={
        "required_profiles": {"core": "1.0", "cost": "1.0", "observability": "1.0"}
    })
    handshake = resp.json()

    if handshake["compatible"]:
        success(f"Service is compatible — profiles: {handshake['service_profiles']}")
    else:
        fail(f"Service incompatible — missing: {handshake['missing']}")
        return

    step("Agent fetches full manifest")
    resp = client.get("/anip/manifest")
    manifest = resp.json()
    caps = list(manifest["capabilities"].keys())
    success(f"Manifest received — protocol: {manifest['protocol']}, capabilities: {caps}")

    # Show what the agent learns from the manifest
    book_cap = manifest["capabilities"]["book_flight"]
    info(f"book_flight: side_effect={book_cap['side_effect']['type']}, "
         f"rollback_window={book_cap['side_effect']['rollback_window']}")
    info(f"book_flight: cost={book_cap['cost']['financial']}")
    info(f"book_flight: observability.retention={book_cap['observability']['retention']}")

    # =================================================================
    # PHASE 2: Delegation Chain Construction
    # =================================================================
    header("PHASE 2: Delegation Chain Construction")
    info("Simulating: Human (Samir) → Orchestrator Agent → Booking Agent")

    # Token 1: Human delegates to orchestrator
    step("Human (Samir) creates root delegation to orchestrator agent")
    root_token = {
        "token_id": "tok_root_001",
        "issuer": "human:samir@example.com",
        "subject": "agent:orchestrator-7x",
        "scope": ["travel.search", "travel.book:max_$500"],
        "purpose": {
            "capability": "book_flight",
            "parameters": {"from": "SEA", "to": "SFO"},
            "task_id": "task_001"
        },
        "parent": None,
        "expires": expires,
        "constraints": {
            "max_delegation_depth": 3,
            "concurrent_branches": "allowed"
        }
    }
    resp = client.post("/anip/tokens/register", json=root_token)
    success(f"Root token registered: {resp.json()['token_id']}")
    info(f"  issuer: {root_token['issuer']}")
    info(f"  subject: {root_token['subject']}")
    info(f"  scope: {root_token['scope']}")
    info(f"  purpose: book_flight SEA→SFO")

    # Token 2: Orchestrator delegates to booking agent
    step("Orchestrator delegates to booking agent (narrower scope)")
    booking_token = {
        "token_id": "tok_booking_002",
        "issuer": "agent:orchestrator-7x",
        "subject": "agent:booking-agent-3a",
        "scope": ["travel.search", "travel.book:max_$500"],
        "purpose": {
            "capability": "book_flight",
            "parameters": {"from": "SEA", "to": "SFO", "date": "2026-03-10"},
            "task_id": "task_001"
        },
        "parent": "tok_root_001",
        "expires": expires,
        "constraints": {
            "max_delegation_depth": 3,
            "concurrent_branches": "allowed"
        }
    }
    resp = client.post("/anip/tokens/register", json=booking_token)
    success(f"Booking agent token registered: {resp.json()['token_id']}")
    info(f"  issuer: {booking_token['issuer']}")
    info(f"  subject: {booking_token['subject']}")
    info(f"  parent: {booking_token['parent']} (orchestrator's token)")
    info(f"  Chain: human:samir → orchestrator-7x → booking-agent-3a")

    # =================================================================
    # PHASE 3: Permission Discovery
    # =================================================================
    header("PHASE 3: Permission Discovery")
    step("Booking agent queries: 'What can I do here?'")

    resp = client.post("/anip/permissions", json=booking_token)
    perms = resp.json()

    for cap in perms["available"]:
        constraints_str = f" (constraints: {cap['constraints']})" if cap["constraints"] else ""
        success(f"Available: {cap['capability']} — scope: {cap['scope_match']}{constraints_str}")
    for cap in perms.get("restricted", []):
        warn(f"Restricted: {cap['capability']} — {cap['reason']}")
    for cap in perms.get("denied", []):
        fail(f"Denied: {cap['capability']} — {cap['reason']}")

    # =================================================================
    # PHASE 4: Capability Graph
    # =================================================================
    header("PHASE 4: Capability Graph Traversal")
    step("Agent checks: 'What do I need before I can book?'")

    resp = client.get("/anip/capabilities/book_flight/graph")
    graph = resp.json()

    for req in graph["requires"]:
        info(f"Prerequisite: {req['capability']} — {req['reason']}")
    success("Agent now knows: must search_flights before book_flight")

    # =================================================================
    # PHASE 5: Search Flights (read, no side effects)
    # =================================================================
    header("PHASE 5: Invoke search_flights (read-only)")
    step("Booking agent searches for SEA→SFO on 2026-03-10")

    # Need a search-purpose token for purpose binding
    search_token = {
        "token_id": "tok_search_003",
        "issuer": "agent:orchestrator-7x",
        "subject": "agent:booking-agent-3a",
        "scope": ["travel.search"],
        "purpose": {
            "capability": "search_flights",
            "parameters": {"origin": "SEA", "destination": "SFO", "date": "2026-03-10"},
            "task_id": "task_001"
        },
        "parent": "tok_root_001",
        "expires": expires,
        "constraints": {"max_delegation_depth": 3, "concurrent_branches": "allowed"}
    }
    client.post("/anip/tokens/register", json=search_token)

    resp = client.post("/anip/invoke/search_flights", json={
        "delegation_token": search_token,
        "parameters": {
            "origin": "SEA",
            "destination": "SFO",
            "date": "2026-03-10"
        }
    })
    result = resp.json()

    if result["success"]:
        flights = result["result"]["flights"]
        success(f"Found {len(flights)} flights:")
        for f in flights:
            info(f"  {f['flight_number']}: {f['departure_time']}→{f['arrival_time']} "
                 f"${f['price']} ({f['stops']} stops)")
    else:
        fail(f"Search failed: {result['failure']}")
        return

    # =================================================================
    # PHASE 6: Book Flight (irreversible, financial)
    # =================================================================
    header("PHASE 6: Invoke book_flight (irreversible)")
    step("Agent decides on AA100 ($420) — checks delegation chain has authority")
    info(f"  Delegation scope: travel.book:max_$500")
    info(f"  Flight cost: $420")
    info(f"  Side effect: irreversible, rollback_window: none")
    info(f"  Agent confirms: PROCEED")

    resp = client.post("/anip/invoke/book_flight", json={
        "delegation_token": booking_token,
        "parameters": {
            "flight_number": "AA100",
            "date": "2026-03-10",
            "passengers": 1
        }
    })
    result = resp.json()

    if result["success"]:
        r = result["result"]
        success(f"Booked! {r['booking_id']} — {r['flight_number']} — ${r['total_cost']}")
        info(f"  side_effect_executed: {r['side_effect_executed']}")
        info(f"  rollback_window: {r['rollback_window']}")
    else:
        fail(f"Booking failed: {result['failure']}")

    # =================================================================
    # PHASE 7: Failure Scenarios
    # =================================================================
    header("PHASE 7: Failure Scenarios — ANIP tells you WHY things fail")

    # Scenario A: Insufficient scope
    step("Scenario A: Agent tries to book without travel.book scope")
    limited_token = {
        "token_id": "tok_limited_004",
        "issuer": "human:samir@example.com",
        "subject": "agent:read-only-agent",
        "scope": ["travel.search"],  # no travel.book!
        "purpose": {
            "capability": "book_flight",
            "parameters": {"from": "SEA", "to": "SFO"},
            "task_id": "task_002"
        },
        "parent": None,
        "expires": expires,
        "constraints": {"max_delegation_depth": 3, "concurrent_branches": "allowed"}
    }
    client.post("/anip/tokens/register", json=limited_token)

    resp = client.post("/anip/invoke/book_flight", json={
        "delegation_token": limited_token,
        "parameters": {"flight_number": "AA100", "date": "2026-03-10"}
    })
    result = resp.json()
    failure = result["failure"]
    fail(f"Failed: {failure['type']}")
    info(f"  Detail: {failure['detail']}")
    info(f"  Resolution: {failure['resolution']['action']} — {failure['resolution']['requires']}")
    info(f"  Grantable by: {failure['resolution']['grantable_by']}")
    info(f"  Retry: {failure['retry']}")
    warn("Agent knows EXACTLY what's missing and who can fix it")

    # Scenario B: Budget exceeded
    step("Scenario B: Agent tries to book $580 flight with $500 budget authority")
    budget_token = {
        "token_id": "tok_budget_005",
        "issuer": "human:samir@example.com",
        "subject": "agent:booking-agent-3a",
        "scope": ["travel.search", "travel.book:max_$500"],
        "purpose": {
            "capability": "book_flight",
            "parameters": {"from": "SFO", "to": "JFK"},
            "task_id": "task_003"
        },
        "parent": None,
        "expires": expires,
        "constraints": {"max_delegation_depth": 3, "concurrent_branches": "allowed"}
    }
    client.post("/anip/tokens/register", json=budget_token)

    resp = client.post("/anip/invoke/book_flight", json={
        "delegation_token": budget_token,
        "parameters": {"flight_number": "DL520", "date": "2026-03-12"}
    })
    result = resp.json()
    failure = result["failure"]
    fail(f"Failed: {failure['type']}")
    info(f"  Detail: {failure['detail']}")
    info(f"  Resolution: {failure['resolution']['action']} — {failure['resolution']['requires']}")
    info(f"  Grantable by: {failure['resolution']['grantable_by']}")
    warn("Agent knows the cost exceeded its authority and can request a budget increase")

    # Scenario C: Purpose mismatch
    step("Scenario C: Agent reuses a book_flight token for a different route")
    info("Token was issued for SEA→SFO but agent tries to use it for search_flights")

    resp = client.post("/anip/invoke/search_flights", json={
        "delegation_token": booking_token,  # purpose is book_flight, not search_flights
        "parameters": {"origin": "SEA", "destination": "LAX", "date": "2026-03-10"}
    })
    result = resp.json()
    failure = result["failure"]
    fail(f"Failed: {failure['type']}")
    info(f"  Detail: {failure['detail']}")
    info(f"  Resolution: {failure['resolution']['action']}")
    warn("Purpose binding prevents token reuse beyond intended scope")

    # =================================================================
    # SUMMARY
    # =================================================================
    header("SUMMARY")
    print(f"""
{BOLD}What this demo showed:{RESET}

  {GREEN}1. Profile Handshake{RESET}
     Agent verified service compatibility BEFORE any interaction.

  {GREEN}2. Delegation Chain (DAG){RESET}
     Human → Orchestrator → Booking Agent
     Each link carries scoped authority, purpose binding, and constraints.

  {GREEN}3. Permission Discovery{RESET}
     Agent queried its full permission surface BEFORE attempting anything.

  {GREEN}4. Capability Graph{RESET}
     Agent discovered prerequisites (search before book) programmatically.

  {GREEN}5. Side-effect Awareness{RESET}
     Agent knew book_flight was irreversible with no rollback BEFORE invoking.

  {GREEN}6. Cost Awareness{RESET}
     Agent knew the cost (~$420±10%) and checked budget authority ($500 max).

  {GREEN}7. Failure Semantics{RESET}
     Every failure told the agent: what went wrong, how to fix it,
     and who can grant the missing authority.

{BOLD}Compare this to REST:{RESET} 401 → 403 → surprise charge → no undo → no audit.

{DIM}This is what agent-native interfaces look like.{RESET}
""")


if __name__ == "__main__":
    main()
