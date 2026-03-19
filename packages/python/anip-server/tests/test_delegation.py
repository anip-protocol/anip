"""Tests for delegation engine."""
from anip_server.delegation import DelegationEngine
from anip_server.storage import InMemoryStorage
from anip_core import DelegationToken, ANIPFailure


def make_engine():
    storage = InMemoryStorage()
    return DelegationEngine(storage, service_id="test-svc")


async def test_issue_root_and_validate():
    """Root token issuance requires authenticated_principal from the application layer."""
    engine = make_engine()
    token, token_id = await engine.issue_root_token(
        authenticated_principal="human:alice@example.com",
        subject="agent",
        scope=["travel.search"],
        capability="search_flights",
    )
    # root_principal is derived from authenticated_principal, not caller-supplied
    assert token.root_principal == "human:alice@example.com"
    assert token.issuer == "test-svc"  # derived from engine's service_id
    result = await engine.validate_delegation(token, ["travel.search"], "search_flights")
    assert isinstance(result, DelegationToken)


async def test_delegate_from_parent():
    """Child token issuance derives issuer and root_principal from parent chain."""
    engine = make_engine()
    parent, _ = await engine.issue_root_token(
        authenticated_principal="human:alice@example.com",
        subject="agent-a",
        scope=["travel.search", "travel.book"],
        capability="search_flights",
    )
    delegate_result = await engine.delegate(
        parent_token=parent,
        subject="agent-b",
        scope=["travel.search"],
        capability="search_flights",
    )
    assert isinstance(delegate_result, tuple)
    child, _ = delegate_result
    # root_principal inherited from parent chain, issuer is parent's subject
    assert child.root_principal == "human:alice@example.com"
    assert child.issuer == "agent-a"
    result = await engine.validate_delegation(child, ["travel.search"], "search_flights")
    assert isinstance(result, DelegationToken)


async def test_expired_token_rejected():
    engine = make_engine()
    token, _ = await engine.issue_root_token(
        authenticated_principal="human:alice@example.com",
        subject="agent",
        scope=["travel.search"],
        capability="search_flights",
        ttl_hours=-1,  # already expired
    )
    result = await engine.validate_delegation(token, ["travel.search"], "search_flights")
    assert isinstance(result, ANIPFailure)
    assert result.type == "token_expired"


async def test_scope_insufficient():
    engine = make_engine()
    token, _ = await engine.issue_root_token(
        authenticated_principal="human:alice@example.com",
        subject="agent",
        scope=["travel.search"],
        capability="search_flights",
    )
    result = await engine.validate_delegation(token, ["travel.book"], "book_flight")
    assert isinstance(result, ANIPFailure)
    assert result.type == "scope_insufficient"


async def test_child_scope_narrowing():
    engine = make_engine()
    parent, _ = await engine.issue_root_token(
        authenticated_principal="human:alice@example.com",
        subject="agent",
        scope=["travel.search", "travel.book"],
        capability="search_flights",
    )
    delegate_result = await engine.delegate(
        parent_token=parent,
        subject="sub-agent",
        scope=["travel.search"],
        capability="search_flights",
    )
    assert isinstance(delegate_result, tuple)
    child, _ = delegate_result
    result = await engine.validate_delegation(child, ["travel.search"], "search_flights")
    assert isinstance(result, DelegationToken)


async def test_child_scope_widening_rejected():
    engine = make_engine()
    parent, _ = await engine.issue_root_token(
        authenticated_principal="human:alice@example.com",
        subject="agent",
        scope=["travel.search"],
        capability="search_flights",
    )
    result = await engine.delegate(
        parent_token=parent,
        subject="sub-agent",
        scope=["travel.search", "travel.book"],
        capability="search_flights",
    )
    # Should return ANIPFailure for scope escalation
    assert isinstance(result, ANIPFailure)
