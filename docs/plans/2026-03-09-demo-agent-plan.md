# Demo Agent Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a demo agent that proves ANIP helps agents reason before acting — an 8-step narrative showing discovery, reasoning, budget failure, human delegation, booking, and audit verification.

**Architecture:** Fixed 8-step flow with injectable reasoning. `reason(step, state)` is the only seam — simulated mode returns canned text, live mode calls Claude API. ANIP HTTP calls are always real (server must be running). See `docs/plans/2026-03-09-demo-agent-design.md` for full design.

**Tech Stack:** Python, httpx, anthropic SDK (optional, live mode only)

---

### Task 1: ANIP HTTP Client

**Files:**
- Create: `examples/agent/anip_client.py`

**Context:** This is a thin wrapper over the ANIP endpoints. It makes raw HTTP calls and returns parsed JSON. No business logic. The reference server runs on `http://localhost:8000`.

**Step 1: Create the ANIP client module**

```python
"""Thin HTTP client for ANIP service endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx


class ANIPClient:
    """Stateless client for an ANIP-compliant service."""

    def __init__(self, base_url: str = "http://localhost:8000", timeout: float = 10):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _get(self, path: str) -> dict[str, Any]:
        with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
            resp = client.get(path)
            resp.raise_for_status()
            return resp.json()

    def _post(self, path: str, json: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
            resp = client.post(path, json=json)
            resp.raise_for_status()
            return resp.json()

    def discover(self) -> dict[str, Any]:
        """Fetch the ANIP discovery document."""
        return self._get("/.well-known/anip")

    def get_manifest(self) -> dict[str, Any]:
        """Fetch the full ANIP manifest."""
        return self._get("/anip/manifest")

    def register_token(self, token: dict[str, Any]) -> dict[str, Any]:
        """Register a delegation token with the service."""
        return self._post("/anip/tokens", token)

    def check_permissions(self, token: dict[str, Any]) -> dict[str, Any]:
        """Query what the agent can do given its delegation token."""
        return self._post("/anip/permissions", token)

    def get_graph(self, capability: str) -> dict[str, Any]:
        """Get prerequisite and composition graph for a capability."""
        return self._get(f"/anip/graph/{capability}")

    def invoke(
        self, capability: str, token: dict[str, Any], parameters: dict[str, Any]
    ) -> dict[str, Any]:
        """Invoke an ANIP capability."""
        return self._post(
            f"/anip/invoke/{capability}",
            {"delegation_token": token, "parameters": parameters},
        )

    def query_audit(
        self, token: dict[str, Any], capability: str | None = None
    ) -> dict[str, Any]:
        """Query the audit log."""
        params = ""
        if capability:
            params = f"?capability={capability}"
        return self._post(f"/anip/audit{params}", token)


def make_token(
    token_id: str,
    issuer: str,
    subject: str,
    scope: list[str],
    capability: str,
    parent: str | None = None,
    max_delegation_depth: int = 2,
    concurrent_branches: str = "allowed",
    ttl_hours: int = 2,
) -> dict[str, Any]:
    """Build a delegation token dict."""
    expires = (datetime.now(timezone.utc) + timedelta(hours=ttl_hours)).isoformat()
    return {
        "token_id": token_id,
        "issuer": issuer,
        "subject": subject,
        "scope": scope,
        "purpose": {"capability": capability, "parameters": {}, "task_id": f"demo-{token_id}"},
        "parent": parent,
        "expires": expires,
        "constraints": {
            "max_delegation_depth": max_delegation_depth,
            "concurrent_branches": concurrent_branches,
        },
    }
```

**Step 2: Verify it works manually**

Start the server and test from Python REPL:

```bash
cd examples/anip && uvicorn anip_server.main:app &
cd examples/agent && python3 -c "
from anip_client import ANIPClient
c = ANIPClient()
d = c.discover()
print(d['anip_discovery']['protocol'])
"
```

Expected: `anip/1.0`

**Step 3: Commit**

```bash
git add examples/agent/anip_client.py
git commit -m "feat(demo-agent): add ANIP HTTP client"
```

---

### Task 2: Reasoning Module

**Files:**
- Create: `examples/agent/reasoning.py`

**Context:** This module contains the `reason()` function — the only seam between simulated and live modes. In simulated mode it returns canned reasoning text. In live mode it sends ANIP metadata to the Claude API and returns the model's reasoning.

**Step 1: Create the reasoning module**

```python
"""Agent reasoning — simulated or live LLM."""

from __future__ import annotations

import json
from typing import Any

# Canned reasoning for simulated mode — keyed by step name.
# Each entry is a function that takes state and returns reasoning text.
SIMULATED_REASONING: dict[str, Any] = {
    "discovery": lambda state: (
        f"Two capabilities found. search_flights is read-only and free — no side effects, "
        f"no financial cost. book_flight is irreversible with estimated cost "
        f"${state['book_cost_min']}-${state['book_cost_max']} (typical ${state['book_cost_typical']}). "
        f"search_flights is a declared prerequisite for book_flight — I must search before booking."
    ),
    "permissions": lambda state: (
        f"Permission check complete. I can invoke search_flights (scope: travel.search) "
        f"and book_flight (scope: travel.book, budget cap: ${state['budget_cap']}). "
        f"My authority is limited to ${state['budget_cap']} per booking."
    ),
    "pre_invocation": lambda state: (
        "Before acting, I note three things from the manifest:\n"
        "  1. book_flight is irreversible — once executed, there is no rollback.\n"
        "  2. Cost is estimated, not fixed — the actual price comes from search results.\n"
        "  3. search_flights is a declared prerequisite — I must search first.\n"
        "I will search to get actual prices before committing to anything."
    ),
    "search_results": lambda state: (
        f"Search returned {state['flight_count']} flights:\n"
        + "\n".join(
            f"  - {f['flight_number']}: ${f['price']}, {f['stops']} stop(s), "
            f"{f['departure_time']}-{f['arrival_time']}"
            for f in state["flights"]
        )
        + f"\n\n{state['preferred_flight']} is the best option — nonstop, earliest arrival. "
        f"But ${state['preferred_price']} exceeds my ${state['budget_cap']} authority. "
        f"I'll attempt it anyway — if blocked, the failure will tell me how to resolve it."
    ),
    "booking_blocked": lambda state: (
        f"Blocked: {state['failure_type']}. {state['failure_detail']}\n"
        f"Resolution: {state['resolution_action']} — grantable by {state['grantable_by']}.\n"
        f"I cannot proceed without additional authority. I need to request a budget increase."
    ),
    "human_delegation": lambda state: (
        f"Human granted a fresh delegation with budget ${state['new_budget_cap']}. "
        f"This is a new token directly from the human — not a child of my original token, "
        f"because widening budget would violate scope narrowing rules. "
        f"It is purpose-bound to book_flight only."
    ),
    "booking_success": lambda state: (
        f"Booking confirmed: {state['booking_id']}.\n"
        f"  Flight: {state['flight_number']}, {state['departure_time']}\n"
        f"  Actual cost: ${state['total_cost']} (declared estimate: "
        f"${state['book_cost_min']}-${state['book_cost_max']})\n"
        f"  Side effect: irreversible — no undo."
    ),
    "audit": lambda state: (
        f"Audit trail verified. {state['audit_count']} entries found.\n"
        f"  Who acted: {state['subject']}\n"
        f"  On whose authority: {state['root_principal']}\n"
        f"  Actual cost: ${state['total_cost']}\n"
        f"  Delegation chain recorded: {' -> '.join(state['chain'])}\n\n"
        "Through the REST adapter, this same booking loses delegation-chain fidelity "
        "and purpose-bound authority, so the workflow is less expressive than native ANIP."
    ),
}


LIVE_SYSTEM_PROMPT = """\
You are an AI agent reasoning about an ANIP (Agent-Native Interface Protocol) service.
You are given metadata from the service (manifest, permissions, responses, failures)
and must reason concisely about what you observe and what to do next.

Keep your reasoning to 2-4 sentences. Be factual and specific — reference actual
numbers, scope names, and capability properties. Do not use filler language."""


def reason(step: str, state: dict[str, Any], live: bool = False) -> str:
    """Generate agent reasoning for the given step.

    In simulated mode, returns deterministic canned reasoning.
    In live mode, sends state to Claude API and returns model reasoning.
    """
    if not live:
        fn = SIMULATED_REASONING.get(step)
        if fn is None:
            return f"[No simulated reasoning for step '{step}']"
        return fn(state)

    return _live_reason(step, state)


def _live_reason(step: str, state: dict[str, Any]) -> str:
    """Call Claude API with ANIP metadata and return reasoning."""
    try:
        import anthropic
    except ImportError:
        return "[Live mode requires 'anthropic' package: pip install anthropic]"

    client = anthropic.Anthropic()

    user_prompt = (
        f"Step: {step}\n\n"
        f"Current state:\n{json.dumps(state, indent=2, default=str)}\n\n"
        f"Reason about what you observe and what the agent should do next."
    )

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=300,
        system=LIVE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    return message.content[0].text
```

**Step 2: Test simulated reasoning**

```bash
cd examples/agent && python3 -c "
from reasoning import reason
state = {'book_cost_min': 280, 'book_cost_max': 500, 'book_cost_typical': 420}
print(reason('discovery', state))
"
```

Expected: Prints the canned discovery reasoning text.

**Step 3: Commit**

```bash
git add examples/agent/reasoning.py
git commit -m "feat(demo-agent): add reasoning module with simulated and live modes"
```

---

### Task 3: Agent Demo Runner — Steps 1-3 (Discovery, Permissions, Pre-invocation)

**Files:**
- Create: `examples/agent/agent_demo.py`

**Context:** This is the main entry point. It runs the 8-step narrative sequentially. We build it incrementally — this task covers steps 1-3. The server must be running at `http://localhost:8000`.

**Step 1: Create the demo runner with steps 1-3**

```python
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

        # Human delegates to agent with limited budget
        token = make_token(
            token_id="demo-agent-token",
            issuer="human:samir@example.com",
            subject="agent:demo-agent",
            scope=["travel.search", "travel.book:max_$300"],
            capability="search_flights",
        )

        print_action("POST", "/anip/tokens")
        reg = self.client.register_token(token)
        print_result(f"Token registered: {reg.get('token_id', 'N/A')}")

        self.state["agent_token"] = token
        self.state["budget_cap"] = 300

        print_action("POST", "/anip/permissions")
        permissions = self.client.check_permissions(token)
        available = [c["capability"] for c in permissions.get("available", [])]
        print_result(f"Available capabilities: {', '.join(available)}")

        print_reasoning(reason("permissions", self.state, self.live))

    def step_3_pre_invocation(self) -> None:
        print_header(3, "PRE-INVOCATION REASONING")

        print_action("GET", "/anip/graph/book_flight")
        graph = self.client.get_graph("book_flight")
        requires = [r["capability"] for r in graph.get("requires", [])]
        print_result(f"Prerequisites for book_flight: {', '.join(requires)}")

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
    import httpx
    main()
```

**Step 2: Test steps 1-3 against the running server**

```bash
cd examples/anip && uvicorn anip_server.main:app &
sleep 2
cd examples/agent && python3 agent_demo.py
```

Expected: Steps 1-3 print cleanly. Steps 4-8 will fail (not implemented yet). Kill the server afterward.

**Step 3: Commit**

```bash
git add examples/agent/agent_demo.py
git commit -m "feat(demo-agent): add agent runner with steps 1-3"
```

---

### Task 4: Agent Demo Runner — Steps 4-5 (Search, Budget Block)

**Files:**
- Modify: `examples/agent/agent_demo.py`

**Context:** Add the search step and the budget-blocked booking attempt. The agent searches SEA→SFO, finds 3 flights, prefers AA100 ($420 nonstop) but it exceeds the $300 budget. Agent tries to book anyway and gets a structured `budget_exceeded` failure.

**Step 1: Add step_4_search and step_5_booking_blocked**

Add these methods to the `DemoAgent` class:

```python
    def step_4_search(self) -> None:
        print_header(4, "SEARCH AND COMPARE")

        # Need a search-purpose token
        search_token = make_token(
            token_id="demo-search-token",
            issuer="human:samir@example.com",
            subject="agent:demo-agent",
            scope=["travel.search"],
            capability="search_flights",
        )
        self.client.register_token(search_token)

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
            "search_token": search_token,
        })

        print_reasoning(reason("search_results", self.state, self.live))

    def step_5_booking_blocked(self) -> None:
        print_header(5, "BOOKING ATTEMPT — BLOCKED")

        # Try to book with the $300-capped token
        book_token = make_token(
            token_id="demo-book-token-v1",
            issuer="human:samir@example.com",
            subject="agent:demo-agent",
            scope=["travel.book:max_$300"],
            capability="book_flight",
        )
        self.client.register_token(book_token)

        print_action("POST", f"/anip/invoke/book_flight")
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
```

**Step 2: Test steps 1-5**

```bash
cd examples/agent && python3 agent_demo.py
```

Expected: Steps 1-5 print cleanly. Step 5 shows `budget_exceeded` failure with resolution guidance. Steps 6-8 will fail.

**Step 3: Commit**

```bash
git add examples/agent/agent_demo.py
git commit -m "feat(demo-agent): add search and budget-blocked booking (steps 4-5)"
```

---

### Task 5: Agent Demo Runner — Steps 6-8 (Delegation, Booking, Audit)

**Files:**
- Modify: `examples/agent/agent_demo.py`

**Context:** The human grants a fresh delegation with higher budget. Agent retries the booking. Then agent queries the audit trail and provides a brief REST contrast.

**Step 1: Add steps 6-8**

Add these methods to the `DemoAgent` class:

```python
    def step_6_human_delegation(self) -> None:
        print_header(6, "HUMAN GRANTS FRESH DELEGATION")

        # Human issues a new root token (not a child — widening budget
        # would violate scope narrowing rules)
        new_token = make_token(
            token_id="demo-book-token-v2",
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
        # Find the successful booking entry
        success_entries = [e for e in entries if e.get("success")]
        entry = success_entries[-1] if success_entries else {}

        self.state.update({
            "audit_count": len(entries),
            "subject": self.state["new_token"]["subject"],
            "root_principal": audit.get("root_principal", "unknown"),
            "chain": entry.get("delegation_chain", []),
        })

        print_result(f"{len(entries)} audit entries for book_flight")
        print_reasoning(reason("audit", self.state, self.live))
```

**Step 2: Test the full 8-step demo**

```bash
cd examples/agent && python3 agent_demo.py
```

Expected: All 8 steps print cleanly. The full narrative runs from discovery through audit verification. The "DEMO COMPLETE" summary prints at the end.

**Step 3: Commit**

```bash
git add examples/agent/agent_demo.py
git commit -m "feat(demo-agent): add delegation, booking, and audit steps (6-8)"
```

---

### Task 6: Requirements and README

**Files:**
- Create: `examples/agent/requirements.txt`
- Create: `examples/agent/README.md`

**Step 1: Create requirements.txt**

```
httpx>=0.27
anthropic>=0.40  # optional, only needed for --live mode
```

**Step 2: Create README.md**

```markdown
# ANIP Demo Agent

An AI agent that consumes an ANIP-compliant flight booking service, demonstrating why agent-native interfaces matter.

## What This Proves

The [reference implementation](../anip/) proves ANIP can be implemented. This demo proves something different: **an actual agent can use ANIP to do something better than it could with a normal API surface.**

Specifically:
- ANIP helps the agent **decide before acting** (discovery, cost awareness, prerequisite checking)
- **Failures are recoverable**, not opaque (structured resolution with actionable guidance)
- **Authorization survives into execution** (delegation chain, budget enforcement, purpose binding)
- **Auditability is part of the interface** (who acted, on whose authority, at what cost)

## The Demo

The agent is asked to book a SEA-to-SFO flight. It:

1. **Discovers** the service — learns capabilities, side effects, cost models
2. **Checks permissions** — confirms what it can do within its delegation
3. **Reasons before acting** — notes irreversibility, cost uncertainty, prerequisites
4. **Searches flights** — compares 3 options, prefers the nonstop at $420
5. **Gets blocked** — $420 exceeds its $300 budget authority; failure says who can fix it
6. **Receives fresh delegation** — human grants exactly enough ($450), purpose-bound
7. **Books successfully** — with full awareness of cost and irreversibility
8. **Verifies the audit trail** — confirms who acted, on whose authority, at what cost

## Running

Start the ANIP reference server:

```bash
cd examples/anip
pip install -e .
uvicorn anip_server.main:app
```

Run the demo (in a separate terminal):

```bash
cd examples/agent
pip install -r requirements.txt

# Simulated mode (default) — deterministic, no API key needed
python agent_demo.py

# Live mode — real LLM reasoning via Claude API
ANTHROPIC_API_KEY=sk-... python agent_demo.py --live
```

## Modes

**Simulated (default):** The agent follows the same 8-step flow with pre-written reasoning. Deterministic, reproducible, no API key required. This is the version you'd record for a demo video.

**Live (`--live`):** Same flow, but at each decision point the agent sends ANIP metadata to Claude and prints the model's actual reasoning. Proves the interface is usable by a real LLM, not just a hand-authored walkthrough.

In both modes, the ANIP HTTP calls are real — the agent talks to the actual reference server.
```

**Step 3: Commit**

```bash
git add examples/agent/requirements.txt examples/agent/README.md
git commit -m "docs(demo-agent): add requirements and README"
```

---

### Task 7: End-to-End Verification

**Context:** Run the full demo end-to-end against a fresh server instance and verify the output matches expectations.

**Step 1: Start fresh server**

```bash
cd examples/anip
# Remove any stale SQLite DB
rm -f anip.db
uvicorn anip_server.main:app &
sleep 2
```

**Step 2: Run the demo**

```bash
cd examples/agent && python3 agent_demo.py
```

Expected output should show:
- Step 1: Protocol anip/1.0, 2 capabilities
- Step 2: Token registered, available capabilities listed
- Step 3: Prerequisites discovered, reasoning about irreversibility
- Step 4: 3 flights found, AA100 preferred but over budget
- Step 5: budget_exceeded failure with resolution guidance
- Step 6: New token registered with $450 budget
- Step 7: Booking confirmed with actual cost $420
- Step 8: Audit entries verified with delegation chain

**Step 3: Fix any issues found during verification**

If output doesn't match expectations, fix and re-run.

**Step 4: Final commit if needed**

```bash
git add -A examples/agent/
git commit -m "fix(demo-agent): end-to-end verification fixes"
```

**Step 5: Kill the server**

```bash
kill %1
```
