"""Tests for permission discovery."""
from anip_core import DelegationToken, CapabilityDeclaration
from anip_server.permissions import discover_permissions


def test_available_capability():
    token = DelegationToken(
        token_id="tok-1", issuer="svc", subject="agent",
        scope=["travel.search"], purpose={"capability": "search_flights", "parameters": {}, "task_id": "t1"},
        parent=None, expires="2099-12-31T23:59:59Z",
        constraints={"max_delegation_depth": 3, "concurrent_branches": "allowed"},
    )
    caps = {
        "search_flights": CapabilityDeclaration(
            name="search_flights", description="Search", contract_version="1.0",
            inputs=[], output={"type": "object", "fields": []},
            side_effect={"type": "read", "rollback_window": None},
            minimum_scope=["travel.search"],
        ),
    }
    result = discover_permissions(token, caps)
    assert len(result.available) == 1
    assert result.available[0].capability == "search_flights"


def test_denied_capability():
    token = DelegationToken(
        token_id="tok-1", issuer="svc", subject="agent",
        scope=["travel.search"], purpose={"capability": "search_flights", "parameters": {}, "task_id": "t1"},
        parent=None, expires="2099-12-31T23:59:59Z",
        constraints={"max_delegation_depth": 3, "concurrent_branches": "allowed"},
    )
    caps = {
        "book_flight": CapabilityDeclaration(
            name="book_flight", description="Book", contract_version="1.0",
            inputs=[], output={"type": "object", "fields": []},
            side_effect={"type": "irreversible", "rollback_window": None},
            minimum_scope=["travel.book"],
        ),
    }
    result = discover_permissions(token, caps)
    assert len(result.denied) == 0
    assert len(result.restricted) == 1
