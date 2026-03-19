"""Tests for permission discovery."""
from datetime import datetime, timezone

from anip_core import (
    CapabilityDeclaration,
    CapabilityOutput,
    ConcurrentBranches,
    DelegationConstraints,
    DelegationToken,
    Purpose,
    SideEffect,
    SideEffectType,
)
from anip_server.permissions import discover_permissions


def test_available_capability():
    token = DelegationToken(
        token_id="tok-1", issuer="svc", subject="agent",
        scope=["travel.search"],
        purpose=Purpose(capability="search_flights", parameters={}, task_id="t1"),
        parent=None,
        expires=datetime(2099, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
        constraints=DelegationConstraints(max_delegation_depth=3, concurrent_branches=ConcurrentBranches.ALLOWED),
    )
    caps = {
        "search_flights": CapabilityDeclaration(
            name="search_flights", description="Search", contract_version="1.0",
            inputs=[], output=CapabilityOutput(type="object", fields=[]),
            side_effect=SideEffect(type=SideEffectType.READ, rollback_window=None),
            minimum_scope=["travel.search"],
        ),
    }
    result = discover_permissions(token, caps)
    assert len(result.available) == 1
    assert result.available[0].capability == "search_flights"


def test_denied_capability():
    token = DelegationToken(
        token_id="tok-1", issuer="svc", subject="agent",
        scope=["travel.search"],
        purpose=Purpose(capability="search_flights", parameters={}, task_id="t1"),
        parent=None,
        expires=datetime(2099, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
        constraints=DelegationConstraints(max_delegation_depth=3, concurrent_branches=ConcurrentBranches.ALLOWED),
    )
    caps = {
        "book_flight": CapabilityDeclaration(
            name="book_flight", description="Book", contract_version="1.0",
            inputs=[], output=CapabilityOutput(type="object", fields=[]),
            side_effect=SideEffect(type=SideEffectType.IRREVERSIBLE, rollback_window=None),
            minimum_scope=["travel.book"],
        ),
    }
    result = discover_permissions(token, caps)
    assert len(result.denied) == 0
    assert len(result.restricted) == 1
