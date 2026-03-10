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

        # Extract cost info from book_flight for reasoning state
        book_cap = manifest["capabilities"]["book_flight"]
        book_cost = book_cap["cost"]["financial"]
        self.state.update({
            "manifest": manifest,
            "book_cost_min": book_cost["range_min"],
            "book_cost_max": book_cost["range_max"],
            "book_cost_typical": book_cost["typical"],
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

        print_action("POST", "/anip/permissions (search token)")
        search_perms = self.client.check_permissions(search_token)
        search_available = [c["capability"] for c in search_perms.get("available", [])]
        print_result(f"Search token grants: {', '.join(search_available)}")

        print_action("POST", "/anip/permissions (book token)")
        book_perms = self.client.check_permissions(book_token)
        book_available = [c["capability"] for c in book_perms.get("available", [])]
        print_result(f"Book token grants: {', '.join(book_available)}")

        print_reasoning(reason("permissions", self.state, self.live))

    def step_3_pre_invocation(self) -> None:
        print_header(3, "PRE-INVOCATION REASONING")

        # No HTTP call — this step is pure reasoning from manifest metadata
        # already fetched in Step 1. The agent reviews what it knows before acting.
        book_cap = self.state["manifest"]["capabilities"]["book_flight"]
        requires = [r["capability"] for r in book_cap.get("requires", [])]
        side_effect = book_cap.get("side_effect", "unknown")
        print(f"\nFrom manifest (already fetched):")
        print(f"  book_flight side_effect: {side_effect}")
        print(f"  book_flight prerequisites: {', '.join(requires)}")

        print_reasoning(reason("pre_invocation", self.state, self.live))


def main() -> None:
    parser = argparse.ArgumentParser(description="ANIP Demo Agent")
    parser.add_argument("--live", action="store_true", help="Use live LLM reasoning (requires ANTHROPIC_API_KEY)")
    parser.add_argument("--base-url", default="http://localhost:8000", help="ANIP service URL")
    args = parser.parse_args()

    agent = DemoAgent(base_url=args.base_url, live=args.live)
    try:
        agent.run()
    except httpx.ConnectError:
        print(f"\nError: Cannot connect to ANIP server at {args.base_url}")
        print("Start the server first: cd examples/anip && uvicorn anip_server.main:app")
        sys.exit(1)


if __name__ == "__main__":
    main()
