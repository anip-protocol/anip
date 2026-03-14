"""Tests for delegation engine."""
from anip_server.delegation import DelegationEngine
from anip_server.storage import SQLiteStorage
from anip_core import DelegationToken, ANIPFailure


def make_engine():
    storage = SQLiteStorage(":memory:")
    return DelegationEngine(storage, service_id="test-svc")


def test_issue_root_and_validate():
    """Root token issuance requires authenticated_principal from the application layer."""
    engine = make_engine()
    token, token_id = engine.issue_root_token(
        authenticated_principal="human:alice@example.com",
        subject="agent",
        scope=["travel.search"],
        capability="search_flights",
    )
    # root_principal is derived from authenticated_principal, not caller-supplied
    assert token.root_principal == "human:alice@example.com"
    assert token.issuer == "test-svc"  # derived from engine's service_id
    result = engine.validate_delegation(token, ["travel.search"], "search_flights")
    assert isinstance(result, DelegationToken)


def test_delegate_from_parent():
    """Child token issuance derives issuer and root_principal from parent chain."""
    engine = make_engine()
    parent, _ = engine.issue_root_token(
        authenticated_principal="human:alice@example.com",
        subject="agent-a",
        scope=["travel.search", "travel.book"],
        capability="search_flights",
    )
    child, _ = engine.delegate(
        parent_token=parent,
        subject="agent-b",
        scope=["travel.search"],
        capability="search_flights",
    )
    # root_principal inherited from parent chain, issuer is parent's subject
    assert child.root_principal == "human:alice@example.com"
    assert child.issuer == "agent-a"
    result = engine.validate_delegation(child, ["travel.search"], "search_flights")
    assert isinstance(result, DelegationToken)


def test_expired_token_rejected():
    engine = make_engine()
    token, _ = engine.issue_root_token(
        authenticated_principal="human:alice@example.com",
        subject="agent",
        scope=["travel.search"],
        capability="search_flights",
        ttl_hours=-1,  # already expired
    )
    result = engine.validate_delegation(token, ["travel.search"], "search_flights")
    assert isinstance(result, ANIPFailure)
    assert result.type == "token_expired"


def test_scope_insufficient():
    engine = make_engine()
    token, _ = engine.issue_root_token(
        authenticated_principal="human:alice@example.com",
        subject="agent",
        scope=["travel.search"],
        capability="search_flights",
    )
    result = engine.validate_delegation(token, ["travel.book"], "book_flight")
    assert isinstance(result, ANIPFailure)
    assert result.type == "scope_insufficient"


def test_child_scope_narrowing():
    engine = make_engine()
    parent, _ = engine.issue_root_token(
        authenticated_principal="human:alice@example.com",
        subject="agent",
        scope=["travel.search", "travel.book"],
        capability="search_flights",
    )
    child, _ = engine.delegate(
        parent_token=parent,
        subject="sub-agent",
        scope=["travel.search"],
        capability="search_flights",
    )
    result = engine.validate_delegation(child, ["travel.search"], "search_flights")
    assert isinstance(result, DelegationToken)


def test_child_scope_widening_rejected():
    engine = make_engine()
    parent, _ = engine.issue_root_token(
        authenticated_principal="human:alice@example.com",
        subject="agent",
        scope=["travel.search"],
        capability="search_flights",
    )
    result = engine.delegate(
        parent_token=parent,
        subject="sub-agent",
        scope=["travel.search", "travel.book"],
        capability="search_flights",
    )
    # Should return ANIPFailure for scope escalation
    assert isinstance(result, ANIPFailure)
