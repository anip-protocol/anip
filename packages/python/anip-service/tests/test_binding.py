"""Tests for binding requirement enforcement in the invoke path (v0.13)."""
import time

from anip_service import ANIPService, Capability
from anip_core import (
    BindingRequirement,
    CapabilityDeclaration,
    CapabilityInput,
    CapabilityOutput,
    SideEffect,
    SideEffectType,
)


def _cap_with_binding(max_age: str | None = None):
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
            requires_binding=[
                BindingRequirement(
                    type="quote",
                    field="quote",
                    source_capability="get_quote",
                    max_age=max_age,
                ),
            ],
        ),
        handler=lambda ctx, params: {"booking_id": "BK-001"},
    )


async def _issue_token(service, scope, capability):
    token, _ = await service._engine.issue_root_token(
        authenticated_principal="human:test@example.com",
        subject="human:test@example.com",
        scope=scope,
        capability=capability,
        ttl_hours=1,
    )
    return token


async def test_binding_present_succeeds():
    """Required binding field present -> success."""
    service = ANIPService(
        service_id="test-binding",
        capabilities=[_cap_with_binding()],
        storage=":memory:",
    )
    token = await _issue_token(service, ["book"], "book_flight")
    result = await service.invoke("book_flight", token, {
        "route": "NYC-LAX",
        "quote": {"quote_id": "qt-abc", "price": 280},
    })
    assert result["success"] is True


async def test_binding_missing_rejected():
    """Required binding field absent -> binding_missing."""
    service = ANIPService(
        service_id="test-binding",
        capabilities=[_cap_with_binding()],
        storage=":memory:",
    )
    token = await _issue_token(service, ["book"], "book_flight")
    result = await service.invoke("book_flight", token, {"route": "NYC-LAX"})
    assert result["success"] is False
    assert result["failure"]["type"] == "binding_missing"
    assert "quote" in result["failure"]["detail"]


async def test_binding_stale_rejected():
    """Binding older than max_age -> binding_stale."""
    service = ANIPService(
        service_id="test-binding",
        capabilities=[_cap_with_binding(max_age="PT5M")],
        storage=":memory:",
    )
    token = await _issue_token(service, ["book"], "book_flight")
    # Provide a quote that was issued 10 minutes ago
    old_time = time.time() - 600  # 10 minutes ago
    result = await service.invoke("book_flight", token, {
        "route": "NYC-LAX",
        "quote": {"quote_id": "qt-old", "price": 280, "issued_at": old_time},
    })
    assert result["success"] is False
    assert result["failure"]["type"] == "binding_stale"
    assert "PT5M" in result["failure"]["detail"]


async def test_binding_no_max_age_no_staleness_check():
    """No max_age on binding -> success regardless of age."""
    service = ANIPService(
        service_id="test-binding",
        capabilities=[_cap_with_binding(max_age=None)],
        storage=":memory:",
    )
    token = await _issue_token(service, ["book"], "book_flight")
    # Even a very old quote should succeed without max_age
    old_time = time.time() - 86400  # 1 day ago
    result = await service.invoke("book_flight", token, {
        "route": "NYC-LAX",
        "quote": {"quote_id": "qt-old", "price": 280, "issued_at": old_time},
    })
    assert result["success"] is True
