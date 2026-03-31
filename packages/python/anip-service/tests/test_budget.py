"""Tests for budget enforcement in the invoke path (v0.13)."""
import pytest
from anip_service import ANIPService, Capability, InvocationContext
from anip_core import (
    BindingRequirement,
    Budget,
    CapabilityDeclaration,
    CapabilityInput,
    CapabilityOutput,
    Cost,
    CostCertainty,
    FinancialCost,
    SideEffect,
    SideEffectType,
)


def _fixed_cost_cap(amount: float = 50.0, currency: str = "USD"):
    return Capability(
        declaration=CapabilityDeclaration(
            name="translate",
            description="Translate text",
            inputs=[CapabilityInput(name="text", type="string", required=True, description="text")],
            output=CapabilityOutput(type="object", fields=["translated"]),
            side_effect=SideEffect(type=SideEffectType.READ),
            minimum_scope=["translate"],
            cost=Cost(
                certainty=CostCertainty.FIXED,
                financial=FinancialCost(currency=currency, amount=amount),
            ),
        ),
        handler=lambda ctx, params: {"translated": params["text"]},
    )


def _estimated_cost_cap_with_binding():
    return Capability(
        declaration=CapabilityDeclaration(
            name="book_flight",
            description="Book a flight",
            inputs=[
                CapabilityInput(name="route", type="string", required=True, description="route"),
                CapabilityInput(name="quote", type="object", required=False, description="quote reference"),
            ],
            output=CapabilityOutput(type="object", fields=["booking_id"]),
            side_effect=SideEffect(type=SideEffectType.WRITE),
            minimum_scope=["book"],
            cost=Cost(
                certainty=CostCertainty.ESTIMATED,
                financial=FinancialCost(currency="USD", range_min=100, range_max=600, typical=300),
            ),
            requires_binding=[
                BindingRequirement(type="quote", field="quote", source_capability="get_quote"),
            ],
        ),
        handler=lambda ctx, params: {"booking_id": "BK-001"},
    )


def _estimated_cost_cap_no_binding():
    return Capability(
        declaration=CapabilityDeclaration(
            name="estimate_only",
            description="Estimated cost with no binding",
            inputs=[CapabilityInput(name="input", type="string", required=True, description="input")],
            output=CapabilityOutput(type="object", fields=["result"]),
            side_effect=SideEffect(type=SideEffectType.READ),
            minimum_scope=["estimate"],
            cost=Cost(
                certainty=CostCertainty.ESTIMATED,
                financial=FinancialCost(currency="USD", range_min=50, range_max=200, typical=100),
            ),
        ),
        handler=lambda ctx, params: {"result": "done"},
    )


def _dynamic_cost_cap(upper_bound: float = 200.0):
    return Capability(
        declaration=CapabilityDeclaration(
            name="compute",
            description="Dynamic cost compute",
            inputs=[CapabilityInput(name="query", type="string", required=True, description="query")],
            output=CapabilityOutput(type="object", fields=["answer"]),
            side_effect=SideEffect(type=SideEffectType.READ),
            minimum_scope=["compute"],
            cost=Cost(
                certainty=CostCertainty.DYNAMIC,
                financial=FinancialCost(currency="USD", upper_bound=upper_bound),
            ),
        ),
        handler=lambda ctx, params: {"answer": "42"},
    )


async def _issue_token(service, scope, capability, budget=None):
    token, _ = await service._engine.issue_root_token(
        authenticated_principal="human:test@example.com",
        subject="human:test@example.com",
        scope=scope,
        capability=capability,
        ttl_hours=1,
        budget=budget,
    )
    return token


# --- Tests ---


async def test_budget_enforcement_fixed_cost():
    """Token budget $100, fixed cost $50 -> success."""
    service = ANIPService(
        service_id="test-budget",
        capabilities=[_fixed_cost_cap(amount=50.0)],
        storage=":memory:",
    )
    token = await _issue_token(service, ["translate"], "translate", budget=Budget(currency="USD", max_amount=100))
    result = await service.invoke("translate", token, {"text": "hello"})
    assert result["success"] is True


async def test_budget_exceeded_fixed_cost():
    """Token budget $30, fixed cost $50 -> rejected."""
    service = ANIPService(
        service_id="test-budget",
        capabilities=[_fixed_cost_cap(amount=50.0)],
        storage=":memory:",
    )
    token = await _issue_token(service, ["translate"], "translate", budget=Budget(currency="USD", max_amount=30))
    result = await service.invoke("translate", token, {"text": "hello"})
    assert result["success"] is False
    assert result["failure"]["type"] == "budget_exceeded"
    assert result["budget_context"]["budget_max"] == 30
    assert result["budget_context"]["cost_check_amount"] == 50.0


async def test_budget_narrowing_child_within():
    """Child budget $300 narrowed from parent $500 -> success with fixed $50 cost."""
    service = ANIPService(
        service_id="test-budget",
        capabilities=[_fixed_cost_cap(amount=50.0)],
        storage=":memory:",
    )
    token = await _issue_token(service, ["translate"], "translate", budget=Budget(currency="USD", max_amount=500))
    # Invoke with a narrower budget hint
    result = await service.invoke("translate", token, {"text": "hello"}, budget={"currency": "USD", "max_amount": 300})
    assert result["success"] is True
    # The effective budget should be 300 (narrowed from 500)
    assert result["budget_context"]["budget_max"] == 300


async def test_budget_narrowing_child_exceeds():
    """Child tries $600 from parent $500 -> effective stays $500, cost $50 still within budget."""
    service = ANIPService(
        service_id="test-budget",
        capabilities=[_fixed_cost_cap(amount=50.0)],
        storage=":memory:",
    )
    token = await _issue_token(service, ["translate"], "translate", budget=Budget(currency="USD", max_amount=500))
    # Try to widen budget — should be clamped to token max
    result = await service.invoke("translate", token, {"text": "hello"}, budget={"currency": "USD", "max_amount": 600})
    assert result["success"] is True
    assert result["budget_context"]["budget_max"] == 500  # clamped


async def test_budget_currency_mismatch():
    """USD budget, EUR cost -> rejected."""
    service = ANIPService(
        service_id="test-budget",
        capabilities=[_fixed_cost_cap(amount=50.0, currency="EUR")],
        storage=":memory:",
    )
    token = await _issue_token(service, ["translate"], "translate", budget=Budget(currency="USD", max_amount=100))
    result = await service.invoke("translate", token, {"text": "hello"})
    assert result["success"] is False
    assert result["failure"]["type"] == "budget_currency_mismatch"


async def test_budget_not_enforceable():
    """Estimated cost with no requires_binding -> rejected when budget present."""
    service = ANIPService(
        service_id="test-budget",
        capabilities=[_estimated_cost_cap_no_binding()],
        storage=":memory:",
    )
    token = await _issue_token(service, ["estimate"], "estimate_only", budget=Budget(currency="USD", max_amount=500))
    result = await service.invoke("estimate_only", token, {"input": "data"})
    assert result["success"] is False
    assert result["failure"]["type"] == "budget_not_enforceable"


async def test_budget_with_bound_price_within():
    """Estimated cost + binding, $280 price, $500 budget -> success."""
    service = ANIPService(
        service_id="test-budget",
        capabilities=[_estimated_cost_cap_with_binding()],
        storage=":memory:",
    )
    token = await _issue_token(service, ["book"], "book_flight", budget=Budget(currency="USD", max_amount=500))
    result = await service.invoke("book_flight", token, {
        "route": "NYC-LAX",
        "quote": {"price": 280, "quote_id": "qt-abc"},
    })
    assert result["success"] is True
    assert result["budget_context"]["cost_check_amount"] == 280.0


async def test_budget_with_bound_price_exceeds():
    """Estimated cost + binding, $550 price, $500 budget -> rejected."""
    service = ANIPService(
        service_id="test-budget",
        capabilities=[_estimated_cost_cap_with_binding()],
        storage=":memory:",
    )
    token = await _issue_token(service, ["book"], "book_flight", budget=Budget(currency="USD", max_amount=500))
    result = await service.invoke("book_flight", token, {
        "route": "NYC-LAX",
        "quote": {"price": 550, "quote_id": "qt-abc"},
    })
    assert result["success"] is False
    assert result["failure"]["type"] == "budget_exceeded"


async def test_budget_dynamic_upper_bound():
    """Dynamic cost with upper_bound $200, budget $300 -> success."""
    service = ANIPService(
        service_id="test-budget",
        capabilities=[_dynamic_cost_cap(upper_bound=200.0)],
        storage=":memory:",
    )
    token = await _issue_token(service, ["compute"], "compute", budget=Budget(currency="USD", max_amount=300))
    result = await service.invoke("compute", token, {"query": "test"})
    assert result["success"] is True
    assert result["budget_context"]["cost_check_amount"] == 200.0


async def test_budget_invocation_hint_lower():
    """Token $500, hint $300, cost $250 -> success (effective $300)."""
    service = ANIPService(
        service_id="test-budget",
        capabilities=[_fixed_cost_cap(amount=250.0)],
        storage=":memory:",
    )
    token = await _issue_token(service, ["translate"], "translate", budget=Budget(currency="USD", max_amount=500))
    result = await service.invoke("translate", token, {"text": "hello"}, budget={"currency": "USD", "max_amount": 300})
    assert result["success"] is True
    assert result["budget_context"]["budget_max"] == 300


async def test_budget_invocation_hint_higher_ignored():
    """Token $500, hint $800 -> effective stays $500."""
    service = ANIPService(
        service_id="test-budget",
        capabilities=[_fixed_cost_cap(amount=250.0)],
        storage=":memory:",
    )
    token = await _issue_token(service, ["translate"], "translate", budget=Budget(currency="USD", max_amount=500))
    result = await service.invoke("translate", token, {"text": "hello"}, budget={"currency": "USD", "max_amount": 800})
    assert result["success"] is True
    assert result["budget_context"]["budget_max"] == 500  # clamped to token budget


async def test_budget_estimated_binding_without_price_rejected():
    """Token has budget, capability has estimated cost + requires_binding, but binding is a plain string (no resolvable price) -> budget_not_enforceable."""
    service = ANIPService(
        service_id="test-budget",
        capabilities=[_estimated_cost_cap_with_binding()],
        storage=":memory:",
    )
    token = await _issue_token(service, ["book"], "book_flight", budget=Budget(currency="USD", max_amount=500))
    result = await service.invoke("book_flight", token, {
        "route": "NYC-LAX",
        "quote": "qt-abc123",  # plain string, no embedded price
    })
    assert result["success"] is False
    assert result["failure"]["type"] == "budget_not_enforceable"


async def test_budget_context_in_response():
    """budget_context present in successful response with budget."""
    service = ANIPService(
        service_id="test-budget",
        capabilities=[_fixed_cost_cap(amount=50.0)],
        storage=":memory:",
    )
    token = await _issue_token(service, ["translate"], "translate", budget=Budget(currency="USD", max_amount=100))
    result = await service.invoke("translate", token, {"text": "hello"})
    assert result["success"] is True
    assert "budget_context" in result
    bc = result["budget_context"]
    assert bc["budget_max"] == 100
    assert bc["budget_currency"] == "USD"
    assert bc["cost_check_amount"] == 50.0
    assert bc["cost_certainty"] == "fixed"
    assert bc["within_budget"] is True
