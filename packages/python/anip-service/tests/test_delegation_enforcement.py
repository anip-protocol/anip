"""Delegation enforcement (SPEC.md §3.2, §6.3 and the behavioral-conformance list).

The cross-runtime versions of these checks live in
``conformance/test_delegation.py``; the Go, Java and C# runtimes carry the
same service-level tests.

- Purpose binding: "a token issued for book_flight cannot invoke
  search_flights", even when its scope would cover both.
- Only the holder of a token (its subject) may delegate from it.
- A delegated token cannot widen its parent's scope or scope budget.
- Chains deeper than max_delegation_depth are rejected.
- A delegation token is a credential for delegating, never for root issuance.

Composed capabilities (§4.6) run inside the SDK: each child step is invoked
through the normal pipeline with its own token, delegated from the caller's
token and bound to the child capability, and its audit entry links back to
the parent invocation.
"""
from __future__ import annotations

import pytest
from anip_core import (
    AuditPolicy,
    CapabilityDeclaration,
    CapabilityInput,
    CapabilityOutput,
    Composition,
    CompositionStep,
    FailurePolicy,
    SideEffect,
    SideEffectType,
)

from anip_service import ANIPService, Capability
from anip_service.types import ANIPError

HUMAN = "human:test@example.com"


def _decl(name: str, scope: list[str], **extra) -> CapabilityDeclaration:
    return CapabilityDeclaration(
        name=name,
        description=name,
        inputs=[CapabilityInput(name="q", type="string", required=False, description="q")],
        output=CapabilityOutput(type="object", fields=[]),
        side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
        minimum_scope=scope,
        **extra,
    )


def _summary_composition(**overrides) -> Composition:
    fields = dict(
        authority_boundary="same_service",
        steps=[
            CompositionStep(id="select", capability="select_cap"),
            CompositionStep(id="enrich", capability="enrich_cap"),
        ],
        input_mapping={
            "select": {"q": "$.input.q"},
            "enrich": {"items": "$.steps.select.output.items"},
        },
        output_mapping={"count": "$.steps.enrich.output.count"},
        failure_policy=FailurePolicy(),
        audit_policy=AuditPolicy(record_child_invocations=True, parent_task_lineage=True),
    )
    fields.update(overrides)
    return Composition(**fields)


def _service(seen: dict | None = None, *, composition: Composition | None = None,
             enrich_scope: list[str] | None = None) -> ANIPService:
    seen = seen if seen is not None else {}

    def recording(name: str, scope: list[str], result: dict) -> Capability:
        def handler(ctx, params):
            seen[name] = {"token": ctx.token, "params": dict(params)}
            return result
        return Capability(declaration=_decl(name, scope), handler=handler)

    def composed_handler(ctx, params):
        seen["summary_handler_called"] = True
        return {"count": -1}

    return ANIPService(
        service_id="test-service",
        capabilities=[
            recording("search_flights", ["travel.search"], {"flights": ["FL-001"]}),
            recording("book_flight", ["travel.book"], {"booking_id": "BK-001"}),
            recording("select_cap", ["inv.read"], {"items": ["a", "b"]}),
            recording("enrich_cap", enrich_scope or ["inv.read"], {"count": 2}),
            Capability(
                declaration=_decl("summary", ["inv.read"], kind="composed",
                                  composition=composition or _summary_composition()),
                handler=composed_handler,
            ),
        ],
        storage=":memory:",
        authenticate=lambda bearer: HUMAN if bearer == "test-key" else None,
    )


async def _issue(service: ANIPService, principal: str, **request) -> dict:
    return await service.issue_token(principal, request)


async def _bound_token(service: ANIPService, capability: str, scope: list[str]):
    issued = await _issue(service, HUMAN, subject=HUMAN, scope=scope, capability=capability)
    return await service.resolve_bearer_token(issued["token"])


# --- purpose binding (already enforced; kept as the reference) ---------------


async def test_invoke_rejects_token_bound_to_another_capability():
    service = _service()
    token = await _bound_token(service, "book_flight", ["travel.search", "travel.book"])

    result = await service.invoke("search_flights", token, {})

    assert result["success"] is False
    assert result["failure"]["type"] == "purpose_mismatch"


# --- who may ask for a token --------------------------------------------------


async def test_authenticate_issuer_accepts_bootstrap_credential_and_tokens():
    service = _service()

    bootstrap = await service.authenticate_issuer("test-key")
    assert bootstrap is not None
    assert (bootstrap.principal, bootstrap.via_token) == (HUMAN, False)

    held = await _issue(service, HUMAN, subject="agent:helper", scope=["travel.search"],
                        capability="search_flights")
    via_token = await service.authenticate_issuer(held["token"])
    assert via_token is not None
    # The holder of the token, not the root principal of its chain.
    assert (via_token.principal, via_token.via_token) == ("agent:helper", True)

    assert await service.authenticate_issuer("not-a-credential") is None


async def test_authenticate_bearer_is_bootstrap_only():
    """A delegation token must not authenticate as its chain's root principal.

    Transports that turned ``authenticate_bearer`` output into an issuing
    principal (stdio, gRPC) would otherwise let any token holder act as the
    human at the root of its chain.
    """
    service = _service()
    held = await _issue(service, HUMAN, subject="agent:helper", scope=["travel.search"],
                        capability="search_flights")

    assert await service.authenticate_bearer("test-key") == HUMAN
    assert await service.authenticate_bearer(held["token"]) is None


async def test_token_credential_cannot_issue_a_root_token():
    service = _service()
    held = await _issue(service, HUMAN, subject="agent:helper", scope=["travel.search"],
                        capability="search_flights")
    issuer = await service.authenticate_issuer(held["token"])

    # No parent_token: this asks for a root token, with more scope than the
    # agent was ever given.
    with pytest.raises(ANIPError) as exc:
        await service.issue_token_as(issuer, {
            "scope": ["travel.search", "travel.book"], "capability": "book_flight",
        })

    assert exc.value.error_type == "insufficient_authority"


async def test_holder_delegates_with_token_credential():
    service = _service()
    held = await _issue(service, HUMAN, subject="agent:helper", scope=["travel.search"],
                        capability="search_flights")
    issuer = await service.authenticate_issuer(held["token"])

    child = await service.issue_token_as(issuer, {
        "subject": "agent:sub-helper", "scope": ["travel.search"],
        "capability": "search_flights", "parent_token": held["token_id"],
    })

    token = await service.resolve_bearer_token(child["token"])
    assert token.root_principal == HUMAN
    assert token.issuer == "agent:helper"


async def test_bootstrap_credential_issues_a_root_token():
    service = _service()
    issuer = await service.authenticate_issuer("test-key")

    root = await service.issue_token_as(issuer, {
        "scope": ["travel.search"], "capability": "search_flights",
    })

    assert root["issued"] is True


# --- scope narrowing ----------------------------------------------------------


@pytest.mark.parametrize("parent_scope, child_scope, allowed", [
    ("travel.search", "travel.search", True),
    ("travel", "travel.search", True),
    ("travel.search", "travel.book", False),
    ("travel", "travelogue.read", False),
    ("travel.book:max_$500", "travel.book:max_$500", True),
    ("travel.book:max_$500", "travel.book:max_$100", True),
    ("travel.book:max_$500", "travel.book", False),
    ("travel.book:max_$500", "travel.book:max_$900", False),
    # A budget on a parent scope bounds every scope beneath it.
    ("travel:max_$500", "travel.book:max_$500", True),
    ("travel:max_$500", "travel.book", False),
    ("travel:max_$500", "travel.book:max_$900", False),
    # A budget that is not a finite, non-negative number must fail closed:
    # NaN compares false against everything.
    ("travel.book:max_$500", "travel.book:max_$NaN", False),
    ("travel.book:max_$500", "travel.book:max_$inf", False),
    ("travel.book:max_$500", "travel.book:max_$-1", False),
    ("travel.book:max_$500", "travel.book:max_$lots", False),
])
async def test_scope_narrowing_rules(parent_scope, child_scope, allowed):
    service = _service()
    root = await _issue(service, HUMAN, subject=HUMAN, scope=[parent_scope], capability="book_flight")

    request = dict(scope=[child_scope], capability="book_flight", parent_token=root["token_id"])
    if allowed:
        child = await _issue(service, HUMAN, **request)
        assert child["issued"] is True
    else:
        with pytest.raises(ANIPError) as exc:
            await _issue(service, HUMAN, **request)
        assert exc.value.error_type == "scope_escalation"


# --- composed capabilities ----------------------------------------------------


async def test_composed_capability_is_run_by_the_sdk_with_child_bound_tokens():
    seen: dict = {}
    service = _service(seen)
    token = await _bound_token(service, "summary", ["inv.read"])

    result = await service.invoke("summary", token, {"q": "x"})

    assert result["success"] is True, result
    # The SDK ran the composition; the registered handler is not consulted.
    assert "summary_handler_called" not in seen
    assert result["result"] == {"count": 2}
    assert seen["select_cap"]["params"] == {"q": "x"}
    assert seen["enrich_cap"]["params"] == {"items": ["a", "b"]}

    for child in ("select_cap", "enrich_cap"):
        child_token = seen[child]["token"]
        assert child_token.purpose.capability == child
        assert child_token.parent == token.token_id

    audit = await service.query_audit(token)
    by_capability = {entry["capability"]: entry for entry in audit["entries"]}
    parent_entry = by_capability["summary"]
    for child in ("select_cap", "enrich_cap"):
        entry = by_capability[child]
        assert entry["success"] is True
        assert entry["parent_invocation_id"] == result["invocation_id"]
        assert entry["task_id"] and entry["task_id"] == parent_entry["task_id"]


async def test_composed_capability_cannot_reach_a_child_beyond_the_callers_scope():
    """The caller's token covers the parent and the first child, not the second."""
    seen: dict = {}
    service = _service(seen, enrich_scope=["inv.admin"])
    token = await _bound_token(service, "summary", ["inv.read"])

    result = await service.invoke("summary", token, {"q": "x"})

    assert result["success"] is False
    assert "enrich_cap" not in seen, "the child handler must not run"
    # Default failure_policy propagates a child denial unchanged: the caller
    # is told its token lacks the scope the step needs.
    assert result["failure"]["type"] == "scope_insufficient"
    assert "inv.admin" in result["failure"]["detail"]


async def test_composed_capability_keeps_the_callers_scope_budget_on_child_tokens():
    seen: dict = {}
    service = _service(seen)
    token = await _bound_token(service, "summary", ["inv:max_$50"])

    result = await service.invoke("summary", token, {"q": "x"})

    assert result["success"] is True, result
    # "inv:max_$50" covers "inv.read"; the child keeps the budget.
    assert seen["select_cap"]["token"].scope == ["inv.read:max_$50"]


async def test_composed_capability_applies_failure_policy_to_child_errors():
    seen: dict = {}

    def failing(ctx, params):
        raise ANIPError("unavailable", "backend down")

    service = _service(seen)
    service._capabilities["enrich_cap"] = Capability(
        declaration=service._capabilities["enrich_cap"].declaration, handler=failing)
    token = await _bound_token(service, "summary", ["inv.read"])

    result = await service.invoke("summary", token, {"q": "x"})

    # Default failure_policy.child_error is fail_parent.
    assert result["success"] is False
    assert result["failure"]["type"] == "composition_child_failed"


async def test_composed_capability_resolves_input_references_in_output_mapping():
    service = _service(composition=_summary_composition(
        output_mapping={"count": "$.steps.enrich.output.count", "query": "$.input.q"},
    ))
    token = await _bound_token(service, "summary", ["inv.read"])

    result = await service.invoke("summary", token, {"q": "x"})

    assert result["success"] is True, result
    assert result["result"] == {"count": 2, "query": "x"}
