#!/usr/bin/env python3
"""Travel Booking Showcase Demo — 8-step scripted ANIP interaction.

A deterministic walkthrough of every ANIP protocol feature using the
travel booking showcase app.  Not an autonomous agent loop — each step
is a scripted HTTP call with formatted output.

Start the server first:
    python app.py &

Run the demo:
    python demo.py
    python demo.py --base-url http://some-other-host:9000
    BASE_URL=http://... python demo.py
"""

from __future__ import annotations

import argparse
import os
import sys

import httpx

# ---------------------------------------------------------------------------
# Formatting helpers (matches agent_demo.py style)
# ---------------------------------------------------------------------------

def print_header(step: int, title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"STEP {step}: {title}")
    print(f"{'=' * 60}")


def print_action(method: str, path: str) -> None:
    print(f"\n  -> {method} {path}")


def print_kv(key: str, value: object, indent: int = 6) -> None:
    print(f"{' ' * indent}{key}: {value}")


# ---------------------------------------------------------------------------
# Demo runner
# ---------------------------------------------------------------------------

class TravelDemo:
    """Eight-step scripted ANIP interaction against the travel showcase."""

    API_KEY_HUMAN = "demo-human-key"
    API_KEY_AGENT = "demo-agent-key"

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(base_url=self.base_url, timeout=10)

        # State accumulated across steps
        self.parent_token_id: str = ""
        self.parent_jwt: str = ""
        self.search_token_jwt: str = ""
        self.book_token_jwt: str = ""
        self.upgraded_jwt: str = ""

    # -- helpers --

    def _auth_api_key(self, key: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {key}"}

    def _auth_jwt(self, jwt: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {jwt}"}

    def _post(self, path: str, *, json_body: dict | None = None,
              headers: dict[str, str] | None = None,
              params: dict[str, str] | None = None) -> dict:
        resp = self.client.post(path, json=json_body, headers=headers, params=params)
        return resp.json()

    def _get(self, path: str) -> dict:
        resp = self.client.get(path)
        resp.raise_for_status()
        return resp.json()

    # -- steps --

    def run(self) -> None:
        print("ANIP Travel Booking Showcase")
        print(f"Server: {self.base_url}")
        print(f"Human key: {self.API_KEY_HUMAN} -> human:samir@example.com")
        print(f"Agent key: {self.API_KEY_AGENT} -> agent:demo-agent")

        steps = [
            self.step_1_discovery,
            self.step_2_token_issuance,
            self.step_3_permissions,
            self.step_4_search,
            self.step_5_scope_wall,
            self.step_6_book_token,
            self.step_7_booking,
            self.step_8_audit,
        ]
        for step_fn in steps:
            try:
                step_fn()
            except Exception as exc:
                print(f"\n  !! Error: {exc}")
                print("     (continuing to next step)")

        print(f"\n{'=' * 60}")
        print("DEMO COMPLETE")
        print(f"{'=' * 60}")
        print("\nFeatures demonstrated:")
        print("  1. Discovery — machine-readable capability advertisement")
        print("  2. Hierarchical token delegation with scope narrowing")
        print("  3. Permission introspection before acting")
        print("  4. Capability invocation with structured results")
        print("  5. Scope enforcement with structured failure + resolution")
        print("  6. Human re-delegation with broader scope")
        print("  7. Successful booking with cost tracking")
        print("  8. Audit trail with event classification")

    # ---- Step 1: Discovery ----

    def step_1_discovery(self) -> None:
        print_header(1, "DISCOVERY")
        print_action("GET", "/.well-known/anip")

        disco = self._get("/.well-known/anip")
        anip = disco["anip_discovery"]

        print_kv("protocol", anip["protocol"])
        print_kv("compliance", anip["compliance"])
        print_kv("capabilities", len(anip["capabilities"]))

        # Fetch manifest once for side-effect info
        manifest = self._get("/anip/manifest")
        print("\n      Capabilities and side effects:")
        for cap_name in anip["capabilities"]:
            cap = manifest["capabilities"].get(cap_name, {})
            se = cap.get("side_effect", {})
            se_type = se.get("type", "unknown") if isinstance(se, dict) else se
            scope = cap.get("minimum_scope", [])
            print(f"        - {cap_name:20s}  side_effect={se_type:15s}  scope={scope}")

    # ---- Step 2: Token Issuance with Scope Narrowing ----

    def step_2_token_issuance(self) -> None:
        print_header(2, "TOKEN ISSUANCE WITH SCOPE NARROWING")

        # Human issues a broad parent token delegating to the agent
        print_action("POST", "/anip/tokens (parent: search + book)")
        parent_resp = self._post(
            "/anip/tokens",
            json_body={
                "subject": "agent:demo-agent",
                "scope": ["travel.search", "travel.book"],
                "capability": "search_flights",
            },
            headers=self._auth_api_key(self.API_KEY_HUMAN),
        )
        if not parent_resp.get("issued"):
            print_kv("ERROR", parent_resp)
            return
        self.parent_token_id = parent_resp["token_id"]
        self.parent_jwt = parent_resp["token"]
        print_kv("parent token_id", self.parent_token_id)
        print_kv("parent scopes", "travel.search, travel.book")
        print_kv("parent expires", parent_resp["expires"])

        # Agent sub-delegates to itself with narrowed scope (search-only)
        # The agent authenticates with its own API key because it is the
        # parent token's subject ("agent:demo-agent").
        print_action("POST", "/anip/tokens (child: search-only via parent_token)")
        search_resp = self._post(
            "/anip/tokens",
            json_body={
                "subject": "agent:demo-agent",
                "scope": ["travel.search"],
                "capability": "search_flights",
                "parent_token": self.parent_token_id,
            },
            headers=self._auth_api_key(self.API_KEY_AGENT),
        )
        if not search_resp.get("issued"):
            print_kv("ERROR", search_resp)
            return
        self.search_token_jwt = search_resp["token"]
        print_kv("search child token_id", search_resp["token_id"])
        print_kv("search child scope", "travel.search (narrowed from parent)")

        # Agent sub-delegates a booking-only child token
        print_action("POST", "/anip/tokens (child: book-only via parent_token)")
        book_resp = self._post(
            "/anip/tokens",
            json_body={
                "subject": "agent:demo-agent",
                "scope": ["travel.book"],
                "capability": "book_flight",
                "parent_token": self.parent_token_id,
            },
            headers=self._auth_api_key(self.API_KEY_AGENT),
        )
        if not book_resp.get("issued"):
            print_kv("ERROR", book_resp)
            return
        self.book_token_jwt = book_resp["token"]
        print_kv("book child token_id", book_resp["token_id"])
        print_kv("book child scope", "travel.book (narrowed from parent)")

        print("\n      Hierarchy: human -> parent (search+book) -> child (search) + child (book)")

    # ---- Step 3: Permission Check ----

    def step_3_permissions(self) -> None:
        print_header(3, "PERMISSION CHECK")

        # Check what the search token can access
        print_action("POST", "/anip/permissions (search token)")
        search_perms = self._post(
            "/anip/permissions",
            headers=self._auth_jwt(self.search_token_jwt),
        )
        available = [c["capability"] for c in search_perms.get("available", [])]
        restricted = [c["capability"] for c in search_perms.get("restricted", [])]
        print_kv("available", ", ".join(available) if available else "(none)")
        print_kv("restricted", ", ".join(restricted) if restricted else "(none)")

        # Check what the book token can access
        print_action("POST", "/anip/permissions (book token)")
        book_perms = self._post(
            "/anip/permissions",
            headers=self._auth_jwt(self.book_token_jwt),
        )
        available = [c["capability"] for c in book_perms.get("available", [])]
        restricted = [c["capability"] for c in book_perms.get("restricted", [])]
        print_kv("available", ", ".join(available) if available else "(none)")
        print_kv("restricted", ", ".join(restricted) if restricted else "(none)")

    # ---- Step 4: Search Flights ----

    def step_4_search(self) -> None:
        print_header(4, "SEARCH FLIGHTS")
        print_action("POST", "/anip/invoke/search_flights (SEA -> SFO)")

        result = self._post(
            "/anip/invoke/search_flights",
            json_body={"parameters": {"origin": "SEA", "destination": "SFO"}},
            headers=self._auth_jwt(self.search_token_jwt),
        )

        if not result.get("success"):
            print_kv("FAILURE", result.get("failure", result))
            return

        flights = result["result"]["flights"]
        budget = 300
        print_kv("flights found", result["result"]["count"])
        print(f"\n      {'Flight':<10} {'Route':<12} {'Depart':<18} {'Price':>8}  Budget")
        print(f"      {'-'*10} {'-'*12} {'-'*18} {'-'*8}  {'-'*10}")
        for f in flights:
            price = f["price"]
            status = "OVER $300" if price > budget else "OK"
            route = f"{f['origin']}->{f['destination']}"
            print(f"      {f['flight_number']:<10} {route:<12} {f['departure_time']:<18} ${price:>7.2f}  {status}")

    # ---- Step 5: Scope Wall ----

    def step_5_scope_wall(self) -> None:
        print_header(5, "SCOPE WALL")

        # Try booking with the search-only token — should fail with
        # scope_insufficient or purpose_mismatch because the search token
        # does not carry travel.book scope.
        flight = "SK100"
        print(f"\n      Attempting to book {flight} using the search-only token...")
        print_action("POST", f"/anip/invoke/book_flight ({flight}) [search token]")

        result = self._post(
            "/anip/invoke/book_flight",
            json_body={"parameters": {"flight_number": flight, "passengers": 1}},
            headers=self._auth_jwt(self.search_token_jwt),
        )

        if result.get("success"):
            print("      Unexpected success — scope enforcement may not be active")
            return

        failure = result.get("failure", {})
        print_kv("blocked", "yes")
        print_kv("failure type", failure.get("type", "unknown"))
        print_kv("detail", failure.get("detail", ""))

        resolution = failure.get("resolution", {})
        if resolution:
            print_kv("resolution action", resolution.get("action", ""))
            print_kv("requires", resolution.get("requires", ""))
            print_kv("grantable_by", resolution.get("grantable_by", ""))
        print("\n      The agent needs a book-scoped token to proceed.")

    # ---- Step 6: Book Token (human re-delegation) ----

    def step_6_book_token(self) -> None:
        print_header(6, "HUMAN RE-DELEGATION")
        print("      Human approves booking with a fresh delegation...")

        print_action("POST", "/anip/tokens (fresh book token from human)")
        resp = self._post(
            "/anip/tokens",
            json_body={
                "subject": "agent:demo-agent",
                "scope": ["travel.book"],
                "capability": "book_flight",
            },
            headers=self._auth_api_key(self.API_KEY_HUMAN),
        )

        if not resp.get("issued"):
            print_kv("ERROR", resp)
            return

        self.upgraded_jwt = resp["token"]
        print_kv("new token_id", resp["token_id"])
        print_kv("scope", "travel.book")
        print_kv("expires", resp["expires"])
        print("\n      Agent now holds a purpose-bound booking token.")

    # ---- Step 7: Successful Booking ----

    def step_7_booking(self) -> None:
        print_header(7, "SUCCESSFUL BOOKING")

        flight = "SK100"
        print_action("POST", f"/anip/invoke/book_flight ({flight}, $180)")

        result = self._post(
            "/anip/invoke/book_flight",
            json_body={"parameters": {"flight_number": flight, "passengers": 1}},
            headers=self._auth_jwt(self.upgraded_jwt),
        )

        if not result.get("success"):
            print_kv("FAILURE", result.get("failure", result))
            return

        booking = result["result"]
        print_kv("booking_id", booking["booking_id"])
        print_kv("flight", booking["flight_number"])
        print_kv("departure", booking["departure_time"])
        print_kv("total_cost", f"${booking['total_cost']:.2f}")

        cost_actual = result.get("cost_actual", {})
        if cost_actual:
            fin = cost_actual.get("financial", {})
            print_kv("cost_actual", f"${fin.get('amount', '?')} {fin.get('currency', '')}")

    # ---- Step 8: Audit Verification ----

    def step_8_audit(self) -> None:
        print_header(8, "AUDIT VERIFICATION")
        print_action("POST", "/anip/audit?capability=book_flight")

        audit = self._post(
            "/anip/audit",
            headers=self._auth_jwt(self.upgraded_jwt),
            params={"capability": "book_flight"},
        )

        entries = audit.get("entries", [])
        print_kv("total entries", len(entries))

        if entries:
            print(f"\n      {'#':<4} {'Capability':<16} {'Success':<9} {'Event Class':<22} {'Subject'}")
            print(f"      {'-'*4} {'-'*16} {'-'*9} {'-'*22} {'-'*20}")
            for i, entry in enumerate(entries[-5:], 1):
                cap = entry.get("capability", "?")
                ok = entry.get("success", "?")
                ec = entry.get("event_class", "?")
                sub = entry.get("subject", "?")
                print(f"      {i:<4} {cap:<16} {str(ok):<9} {ec:<22} {sub}")

            # Highlight the last successful booking from the audit trail
            success_entries = [e for e in entries if e.get("success")]
            if success_entries:
                last = success_entries[-1]
                print(f"\n      Last successful booking audit detail:")
                print_kv("root_principal", last.get("root_principal", "?"))
                print_kv("subject", last.get("subject", "?"))
                cost = last.get("cost_actual", {})
                if cost:
                    fin = cost.get("financial", {})
                    print_kv("cost_actual", f"${fin.get('amount', '?')} {fin.get('currency', '')}")
                chain = last.get("delegation_chain", [])
                if chain:
                    print_kv("delegation_chain", " -> ".join(chain))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="ANIP Travel Booking Showcase Demo")
    parser.add_argument(
        "--base-url",
        default=os.getenv("BASE_URL", "http://127.0.0.1:8000"),
        help="Base URL of the travel showcase server (default: $BASE_URL or http://127.0.0.1:8000)",
    )
    args = parser.parse_args()

    demo = TravelDemo(args.base_url)
    try:
        demo.run()
    except httpx.ConnectError:
        print(f"\nError: Cannot connect to server at {args.base_url}")
        print("Start the server first: python app.py")
        sys.exit(1)
    finally:
        demo.client.close()


if __name__ == "__main__":
    main()
