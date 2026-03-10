#!/usr/bin/env python3
"""ANIP Demo Agent — proving agents can reason before acting.

This demo shows an AI agent consuming an ANIP-compliant flight booking
service. Unlike the protocol walkthrough (demo.py), this demonstrates
agent-level reasoning: discovering capabilities, evaluating cost and
side effects before acting, handling budget failures with structured
resolution, receiving narrowly scoped human delegation, and verifying
the audit trail.

Two modes:
  - Simulated (default): deterministic reasoning, always reproducible
  - Live (--live): real LLM reasoning via Claude API

The ANIP HTTP calls are real in both modes — the reference server must
be running.

Start the server:
    cd examples/anip && uvicorn anip_server.main:app

Run the demo:
    python agent_demo.py              # simulated (default)
    python agent_demo.py --live       # live LLM reasoning
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import httpx

from anip_client import ANIPClient, make_token
from reasoning import reason


def print_header(step_num: int, title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"STEP {step_num}: {title}")
    print(f"{'=' * 60}")


def print_reasoning(text: str) -> None:
    print(f"\nAgent reasoning: {text}")


def print_action(method: str, path: str) -> None:
    print(f"\nAction: {method} {path}")


def print_result(text: str) -> None:
    print(f"Result: {text}")


class DemoAgent:
    """An agent that consumes an ANIP service with pre-action reasoning."""

    def __init__(self, base_url: str, live: bool = False):
        self.client = ANIPClient(base_url)
        self.live = live
        self.state: dict[str, Any] = {}

    def run(self) -> None:
        print("ANIP Demo Agent")
        print(f"Mode: {'live (LLM reasoning)' if self.live else 'simulated'}")
        print(f"Server: {self.client.base_url}")
        print(f"Task: Book a flight from SEA to SFO under budget")

        self.step_1_discovery()
        self.step_2_permissions()
        self.step_3_pre_invocation()
        self.step_4_search()
        self.step_5_booking_blocked()
        self.step_6_human_delegation()
        self.step_7_booking_success()
        self.step_8_audit()

        print(f"\n{'=' * 60}")
        print("DEMO COMPLETE")
        print(f"{'=' * 60}")
        print("\nThis demo proved:")
        print("  - ANIP helps the agent decide before acting")
        print("  - Failures are recoverable, not opaque")
        print("  - Authorization survives into execution")
        print("  - Auditability is part of the interface")

    def step_1_discovery(self) -> None:
        print_header(1, "DISCOVERY")

        print_action("GET", "/.well-known/anip")
        discovery = self.client.discover()
        disco = discovery["anip_discovery"]
        print_result(
            f"Protocol {disco['protocol']}, compliance: {disco['compliance']}, "
            f"{len(disco['capabilities'])} capabilities"
        )

        print_action("GET", "/anip/manifest")
        manifest = self.client.get_manifest()
        print_result("Full capability declarations retrieved")

        # Extract capability metadata for reasoning state
        book_cap = manifest["capabilities"]["book_flight"]
        search_cap = manifest["capabilities"]["search_flights"]
        book_cost = book_cap["cost"]["financial"]
        self.state.update({
            "manifest": manifest,
            "book_cost_min": book_cost["range_min"],
            "book_cost_max": book_cost["range_max"],
            "book_cost_typical": book_cost["typical"],
            # Store capability declarations for live mode reasoning
            "book_flight_declaration": book_cap,
            "search_flights_declaration": search_cap,
        })

        print_reasoning(reason("discovery", self.state, self.live))

    def step_2_permissions(self) -> None:
        print_header(2, "PERMISSION CHECK")

        # Human delegates to agent — one token per capability (purpose-bound)
        search_token = make_token(
            issuer="human:samir@example.com",
            subject="agent:demo-agent",
            scope=["travel.search"],
            capability="search_flights",
        )
        book_token = make_token(
            issuer="human:samir@example.com",
            subject="agent:demo-agent",
            scope=["travel.book:max_$300"],
            capability="book_flight",
        )

        print_action("POST", "/anip/tokens (search)")
        self.client.register_token(search_token)
        print_result(f"Token registered: {search_token['token_id']}")

        print_action("POST", "/anip/tokens (book)")
        self.client.register_token(book_token)
        print_result(f"Token registered: {book_token['token_id']}")

        self.state["search_token"] = search_token
        self.state["book_token"] = book_token
        self.state["budget_cap"] = 300
        self.state["token_strategy"] = (
            "two purpose-bound tokens, one per capability; "
            "permissions are evaluated per token, not globally"
        )

        print_action("POST", "/anip/permissions (search token)")
        search_perms = self.client.check_permissions(search_token)
        search_available = [c["capability"] for c in search_perms.get("available", [])]
        print_result(f"Search token grants: {', '.join(search_available)}")

        print_action("POST", "/anip/permissions (book token)")
        book_perms = self.client.check_permissions(book_token)
        book_available = [c["capability"] for c in book_perms.get("available", [])]
        print_result(f"Book token grants: {', '.join(book_available)}")

        # Store permission responses for live mode reasoning
        self.state["search_permissions"] = search_perms
        self.state["book_permissions"] = book_perms

        print_reasoning(reason("permissions", self.state, self.live))

    def step_3_pre_invocation(self) -> None:
        print_header(3, "PRE-INVOCATION REASONING")

        # No HTTP call — this step is pure reasoning from manifest metadata
        # already fetched in Step 1. The agent reviews what it knows before acting.
        book_cap = self.state["manifest"]["capabilities"]["book_flight"]
        requires = [r["capability"] for r in book_cap.get("requires", [])]
        side_effect = book_cap.get("side_effect", {})
        side_type = side_effect.get("type", "unknown") if isinstance(side_effect, dict) else side_effect
        print(f"\nFrom manifest (already fetched):")
        print(f"  book_flight side_effect: {side_type}")
        print(f"  book_flight prerequisites: {', '.join(requires)}")

        print_reasoning(reason("pre_invocation", self.state, self.live))

    def step_4_search(self) -> None:
        print_header(4, "SEARCH AND COMPARE")

        # Reuse the search token registered in Step 2
        search_token = self.state["search_token"]

        print_action("POST", "/anip/invoke/search_flights")
        result = self.client.invoke(
            "search_flights",
            search_token,
            {"origin": "SEA", "destination": "SFO", "date": "2026-03-10"},
        )
        flights = result["result"]["flights"]
        print_result(f"{result['result']['count']} flights found")

        # Find the preferred flight (nonstop, earliest)
        nonstop = [f for f in flights if f["stops"] == 0]
        preferred = min(nonstop, key=lambda f: f["departure_time"]) if nonstop else flights[0]

        self.state.update({
            "flights": flights,
            "flight_count": len(flights),
            "preferred_flight": preferred["flight_number"],
            "preferred_price": preferred["price"],
        })

        print_reasoning(reason("search_results", self.state, self.live))

    def step_5_booking_blocked(self) -> None:
        print_header(5, "BOOKING ATTEMPT — BLOCKED")

        # Reuse the $300-capped book token from Step 2
        book_token = self.state["book_token"]

        print_action("POST", "/anip/invoke/book_flight")
        result = self.client.invoke(
            "book_flight",
            book_token,
            {
                "flight_number": self.state["preferred_flight"],
                "date": "2026-03-10",
                "passengers": 1,
            },
        )

        failure = result["failure"]
        self.state.update({
            "failure_type": failure["type"],
            "failure_detail": failure["detail"],
            "resolution_action": failure["resolution"]["action"],
            "grantable_by": failure["resolution"].get("grantable_by", "unknown"),
        })

        print_result(f"Blocked: {failure['type']}")
        print_reasoning(reason("booking_blocked", self.state, self.live))

    def step_6_human_delegation(self) -> None:
        print_header(6, "HUMAN GRANTS FRESH DELEGATION")

        # Human issues a new root token (not a child — widening budget
        # would violate scope narrowing rules)
        new_token = make_token(
            issuer="human:samir@example.com",
            subject="agent:demo-agent",
            scope=["travel.book:max_$450"],
            capability="book_flight",
        )

        print_action("POST", "/anip/tokens")
        reg = self.client.register_token(new_token)
        print_result(f"New token registered: {reg.get('token_id', 'N/A')}")

        self.state.update({
            "new_token": new_token,
            "new_budget_cap": 450,
        })

        print_reasoning(reason("human_delegation", self.state, self.live))

    def step_7_booking_success(self) -> None:
        print_header(7, "BOOKING SUCCEEDS")

        print_action("POST", "/anip/invoke/book_flight")
        result = self.client.invoke(
            "book_flight",
            self.state["new_token"],
            {
                "flight_number": self.state["preferred_flight"],
                "date": "2026-03-10",
                "passengers": 1,
            },
        )

        booking = result["result"]
        self.state.update({
            "booking_id": booking["booking_id"],
            "flight_number": booking["flight_number"],
            "departure_time": booking["departure_time"],
            "total_cost": booking["total_cost"],
        })

        print_result(f"Booking confirmed: {booking['booking_id']}")
        print_reasoning(reason("booking_success", self.state, self.live))

    def step_8_audit(self) -> None:
        print_header(8, "AUDIT VERIFICATION AND REST CONTRAST")

        print_action("POST", "/anip/audit")
        audit = self.client.query_audit(
            self.state["new_token"],
            capability="book_flight",
        )

        entries = audit.get("entries", [])
        # Find the successful booking entry and read values FROM the audit
        # record, not from local state — this proves the audit trail is real.
        success_entries = [e for e in entries if e.get("success")]
        entry = success_entries[-1] if success_entries else {}

        # These values come from the server's audit log, not our local state
        audit_subject = entry.get("subject", "unknown")
        audit_root = entry.get("root_principal", "unknown")
        audit_cost = entry.get("cost_actual", {})
        audit_financial = audit_cost.get("financial", {}) if audit_cost else {}
        audit_total = audit_financial.get("amount", "unknown")
        audit_chain = entry.get("delegation_chain", [])

        self.state.update({
            "audit_count": len(entries),
            "subject": audit_subject,
            "root_principal": audit_root,
            "total_cost": audit_total,
            "chain": audit_chain,
        })

        print_result(f"{len(entries)} audit entries for book_flight")
        print_reasoning(reason("audit", self.state, self.live))


def main() -> None:
    parser = argparse.ArgumentParser(description="ANIP Demo Agent")
    parser.add_argument("--live", action="store_true", help="Use live LLM reasoning (requires ANTHROPIC_API_KEY)")
    parser.add_argument("--agent", action="store_true", help="Run as autonomous agent (requires ANTHROPIC_API_KEY)")
    parser.add_argument("--human-in-the-loop", action="store_true", help="Interactive human delegation (with --agent)")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="ANIP service URL")
    args = parser.parse_args()

    if args.agent:
        from agent_loop import run_agent_loop
        try:
            run_agent_loop(
                base_url=args.base_url,
                human_in_the_loop=args.human_in_the_loop,
            )
        except httpx.ConnectError:
            print(f"\nError: Cannot connect to ANIP server at {args.base_url}")
            print("Start the server first: cd examples/anip && uvicorn anip_server.main:app")
            sys.exit(1)
        except httpx.HTTPStatusError as e:
            print(f"\nError: Server returned {e.response.status_code} for {e.request.url}")
            print("Check that the ANIP reference server is running correctly.")
            sys.exit(1)
        return

    agent = DemoAgent(base_url=args.base_url, live=args.live)
    try:
        agent.run()
    except httpx.ConnectError:
        print(f"\nError: Cannot connect to ANIP server at {args.base_url}")
        print("Start the server first: cd examples/anip && uvicorn anip_server.main:app")
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        print(f"\nError: Server returned {e.response.status_code} for {e.request.url}")
        print("Check that the ANIP reference server is running correctly.")
        sys.exit(1)


if __name__ == "__main__":
    main()
