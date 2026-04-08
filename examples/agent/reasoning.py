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
        f"Two tokens registered, one per capability. "
        f"Search token: travel.search scope, grants search_flights. "
        f"Book token: travel.book scope, budget cap ${state['budget_cap']}. "
        f"My booking authority is limited to ${state['budget_cap']}."
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

ANIP uses purpose-bound delegation tokens. An agent may hold multiple tokens, each \
scoped to a single capability. When you see permission responses from different tokens, \
each showing the other's capability as "restricted," that is normal — permissions are \
per-token, not global. Only flag a conflict if the same token both requires and blocks \
the same action.

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

    try:
        client = anthropic.Anthropic()

        # Exclude raw manifest and token dicts (large, redundant with extracted fields)
        exclude = {"manifest", "search_token", "book_token", "new_token"}
        llm_state = {k: v for k, v in state.items() if k not in exclude}

        user_prompt = (
            f"Step: {step}\n\n"
            f"Current state:\n{json.dumps(llm_state, indent=2, default=str)}\n\n"
            f"Reason about what you observe and what the agent should do next."
        )

        message = client.messages.create(
            model="claude-sonnet-4-6-20250620",
            max_tokens=300,
            system=LIVE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        return message.content[0].text  # type: ignore[union-attr]
    except Exception as e:
        return f"[Live reasoning failed: {e}]"
