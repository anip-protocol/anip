"""Validation of invocation parameters against declared inputs (SPEC.md §6.3).

The check runs in the invoke pipeline after delegation, budget, binding and
control-requirement enforcement, and before the exclusive lock, the approval
grant and the handler. It looks at the parameters as the caller sent them.
"""
from __future__ import annotations

import math
from typing import Any

import pytest
from anip_core import (
    AuditPolicy,
    BindingRequirement,
    CapabilityDeclaration,
    CapabilityInput,
    CapabilityOutput,
    Composition,
    CompositionStep,
    ControlRequirement,
    Cost,
    CostCertainty,
    FailurePolicy,
    FinancialCost,
    GrantPolicy,
    ResponseMode,
    SideEffect,
    SideEffectType,
)

from anip_service import ANIPError, ANIPService, Capability
from anip_service.hooks import ANIPHooks, LoggingHooks, MetricsHooks
from anip_service.input_validation import (
    INVALID_PARAMETERS_RESOLUTION,
    check_declared_inputs,
)

EXPECTED_RESOLUTION = {
    "action": "retry_now",
    "recovery_class": "retry_now",
    "requires": "parameters that match the capability's declared inputs",
}


def _inputs(*specs: tuple) -> list[CapabilityInput]:
    built = []
    for spec in specs:
        name, type_ = spec[0], spec[1]
        extra = spec[2] if len(spec) > 2 else {}
        built.append(CapabilityInput(name=name, type=type_, **extra))
    return built


# ---------------------------------------------------------------------------
# The check itself
# ---------------------------------------------------------------------------


class TestCheckDeclaredInputs:
    def test_resolution_constant_is_the_one_the_spec_gives(self):
        assert INVALID_PARAMETERS_RESOLUTION == EXPECTED_RESOLUTION

    def test_valid_parameters_pass(self):
        inputs = _inputs(("a", "string"), ("b", "integer"), ("c", "number"),
                         ("d", "boolean"), ("e", "array"), ("f", "object"))
        assert check_declared_inputs("cap", inputs, {
            "a": "x", "b": 3, "c": 1.5, "d": False, "e": [], "f": {},
        }) is None

    def test_missing_inputs_are_named_in_declaration_order(self):
        inputs = _inputs(("zeta", "string"), ("alpha", "string"), ("mid", "string"))
        assert check_declared_inputs("book_flight", inputs, {"mid": "x"}) == (
            "book_flight is missing required input(s): zeta, alpha"
        )

    def test_null_is_missing(self):
        inputs = _inputs(("a", "string"), ("b", "string"))
        assert check_declared_inputs("cap", inputs, {"a": None, "b": "x"}) == (
            "cap is missing required input(s): a"
        )

    @pytest.mark.parametrize("parameters", [None, {}])
    def test_absent_parameters_count_as_empty(self, parameters):
        inputs = _inputs(("a", "string"))
        assert check_declared_inputs("cap", inputs, parameters) == (
            "cap is missing required input(s): a"
        )

    def test_required_is_the_default(self):
        declared = CapabilityInput(name="a", type="string")
        assert declared.required is True
        assert declared.model_dump()["required"] is True
        assert CapabilityInput.model_validate({"name": "a", "type": "string"}).required is True

    def test_a_declared_default_does_not_satisfy_required(self):
        inputs = _inputs(("a", "string", {"default": "fallback"}))
        assert check_declared_inputs("cap", inputs, {}) == (
            "cap is missing required input(s): a"
        )

    def test_optional_input_absent_or_null_is_not_checked(self):
        inputs = _inputs(("a", "integer", {"required": False}))
        assert check_declared_inputs("cap", inputs, {}) is None
        assert check_declared_inputs("cap", inputs, {"a": None}) is None

    def test_optional_input_with_a_value_is_type_checked(self):
        inputs = _inputs(("a", "integer", {"required": False}))
        assert check_declared_inputs("cap", inputs, {"a": "5"}) == (
            "cap has invalid input(s): 'a' must be integer, got string"
        )

    def test_missing_is_reported_before_wrong_types(self):
        inputs = _inputs(("a", "string"), ("b", "integer"))
        assert check_declared_inputs("cap", inputs, {"b": "x"}) == (
            "cap is missing required input(s): a"
        )

    def test_every_wrong_type_is_named_in_declaration_order(self):
        inputs = _inputs(("passengers", "integer"), ("flight", "string"),
                         ("quote_id", "object"))
        assert check_declared_inputs(
            "book_flight", inputs,
            {"quote_id": ["a"], "flight": "AA1", "passengers": "two"},
        ) == (
            "book_flight has invalid input(s): 'passengers' must be integer, got string; "
            "'quote_id' must be object, got array"
        )

    @pytest.mark.parametrize("declared,value,received", [
        ("string", 1, "number"), ("string", 1.5, "number"), ("string", True, "boolean"),
        ("string", [], "array"), ("string", {}, "object"),
        ("integer", "1", "string"), ("integer", 1.5, "number"), ("integer", True, "boolean"),
        ("integer", False, "boolean"), ("integer", [1], "array"), ("integer", {}, "object"),
        ("number", "1", "string"), ("number", True, "boolean"), ("number", [], "array"),
        ("number", {}, "object"),
        ("boolean", "true", "string"), ("boolean", 1, "number"), ("boolean", 0, "number"),
        ("boolean", [], "array"), ("boolean", {}, "object"),
        ("array", "x", "string"), ("array", 1, "number"), ("array", True, "boolean"),
        ("array", {}, "object"),
        ("object", "x", "string"), ("object", 1, "number"), ("object", True, "boolean"),
        ("object", [], "array"),
    ])
    def test_wrong_json_type_is_refused(self, declared, value, received):
        inputs = _inputs(("v", declared))
        assert check_declared_inputs("cap", inputs, {"v": value}) == (
            f"cap has invalid input(s): 'v' must be {declared}, got {received}"
        )

    @pytest.mark.parametrize("value", [5, 5.0, 1e2, -3.0, 0, 2**80, -(2**80), 1e300])
    def test_integer_accepts_any_integral_number(self, value):
        assert check_declared_inputs("cap", _inputs(("n", "integer")), {"n": value}) is None

    @pytest.mark.parametrize("value", [1.5, -0.25, math.nan, math.inf, -math.inf])
    def test_integer_rejects_fractional_and_non_finite_numbers(self, value):
        assert check_declared_inputs("cap", _inputs(("n", "integer")), {"n": value}) == (
            "cap has invalid input(s): 'n' must be integer, got number"
        )

    @pytest.mark.parametrize("value", [5, 5.0, 1.5, -2, 2**80])
    def test_number_accepts_every_number(self, value):
        assert check_declared_inputs("cap", _inputs(("n", "number")), {"n": value}) is None

    def test_tuple_is_an_array(self):
        assert check_declared_inputs("cap", _inputs(("v", "array")), {"v": (1, 2)}) is None

    @pytest.mark.parametrize("declared", [
        "airport_code", "date", "String", "INTEGER", "int", "bool", "list", "dict", "",
    ])
    def test_other_type_names_are_not_checked(self, declared):
        inputs = _inputs(("v", declared))
        for value in ("x", 1, 1.5, True, [], {}):
            assert check_declared_inputs("cap", inputs, {"v": value}) is None

    def test_undeclared_parameters_are_ignored(self):
        inputs = _inputs(("a", "string"))
        assert check_declared_inputs("cap", inputs, {"a": "x", "extra": object()}) is None

    def test_allowed_values_are_not_enforced(self):
        inputs = _inputs(("a", "string", {"allowed_values": ["x", "y"]}))
        assert check_declared_inputs("cap", inputs, {"a": "z"}) is None


# ---------------------------------------------------------------------------
# The check in the invoke pipeline
# ---------------------------------------------------------------------------


def _declaration(name: str = "book", **overrides: Any) -> CapabilityDeclaration:
    fields: dict[str, Any] = dict(
        name=name,
        description="Book something",
        inputs=[
            CapabilityInput(name="flight_number", type="string"),
            CapabilityInput(name="date", type="date"),
            CapabilityInput(name="passengers", type="integer", required=False, default=1),
            CapabilityInput(name="notes", type="string", required=False),
        ],
        output=CapabilityOutput(type="object", fields=["ok"]),
        side_effect=SideEffect(type=SideEffectType.IRREVERSIBLE, rollback_window="none"),
        minimum_scope=["book"],
    )
    fields.update(overrides)
    return CapabilityDeclaration(**fields)


class _Recorder:
    """A handler that records the parameters of every call."""

    def __init__(self, result: dict[str, Any] | None = None):
        self.calls: list[dict[str, Any]] = []
        self.result = result or {"ok": True}

    def __call__(self, ctx, params):
        self.calls.append(params)
        return dict(self.result)


def _service(*capabilities: Capability, **kwargs: Any) -> ANIPService:
    return ANIPService(
        service_id="test-input-validation",
        capabilities=list(capabilities),
        storage=":memory:",
        **kwargs,
    )


async def _token(service: ANIPService, scope: list[str], capability: str, **kwargs: Any):
    token, _ = await service._engine.issue_root_token(
        authenticated_principal="human:test@example.com",
        subject="human:test@example.com",
        scope=scope,
        capability=capability,
        ttl_hours=1,
        **kwargs,
    )
    return token


async def _audit_entry(service: ANIPService, token, invocation_id: str) -> dict[str, Any]:
    found = await service.query_audit(token, {"invocation_id": invocation_id})
    entries = [e for e in found["entries"] if e.get("invocation_id") == invocation_id]
    assert len(entries) == 1, f"expected one audit entry for {invocation_id}, got {entries}"
    return entries[0]


def _assert_invalid_parameters(result: dict[str, Any], detail: str) -> None:
    assert result["success"] is False
    assert "result" not in result
    assert result["failure"] == {
        "type": "invalid_parameters",
        "detail": detail,
        "resolution": EXPECTED_RESOLUTION,
        "retry": False,
    }
    assert result["invocation_id"].startswith("inv-")


VALID = {"flight_number": "AA100", "date": "2026-03-10"}


class TestRefusal:
    async def test_missing_required_input_is_refused_and_audited(self):
        handler = _Recorder()
        service = _service(Capability(declaration=_declaration(), handler=handler))
        token = await _token(
            service, ["book"], "book", purpose_parameters={"task_id": "task-1"})

        result = await service.invoke(
            "book", token, {"passengers": 2},
            client_reference_id="ref-1", task_id="task-1",
            parent_invocation_id="inv-aaaaaaaaaaaa", upstream_service="upstream",
        )

        _assert_invalid_parameters(
            result, "book is missing required input(s): flight_number, date")
        assert handler.calls == []
        assert result["client_reference_id"] == "ref-1"
        assert result["task_id"] == "task-1"
        assert result["parent_invocation_id"] == "inv-aaaaaaaaaaaa"
        assert result["upstream_service"] == "upstream"
        entry = await _audit_entry(service, token, result["invocation_id"])
        assert entry["success"] is False
        assert entry["failure_type"] == "invalid_parameters"
        assert entry["capability"] == "book"
        assert entry["client_reference_id"] == "ref-1"
        assert entry["task_id"] == "task-1"
        assert entry["parent_invocation_id"] == "inv-aaaaaaaaaaaa"
        assert entry["upstream_service"] == "upstream"

    async def test_wrong_type_is_refused(self):
        handler = _Recorder()
        service = _service(Capability(declaration=_declaration(), handler=handler))
        token = await _token(service, ["book"], "book")

        result = await service.invoke(
            "book", token, {**VALID, "passengers": "two", "notes": 7})

        _assert_invalid_parameters(
            result,
            "book has invalid input(s): 'passengers' must be integer, got string; "
            "'notes' must be string, got number",
        )
        assert handler.calls == []

    async def test_null_parameters_are_an_empty_object(self):
        handler = _Recorder()
        service = _service(Capability(declaration=_declaration(), handler=handler))
        token = await _token(service, ["book"], "book")

        result = await service.invoke("book", token, None)  # type: ignore[arg-type]

        _assert_invalid_parameters(
            result, "book is missing required input(s): flight_number, date")
        assert handler.calls == []

    async def test_a_default_does_not_satisfy_required(self):
        handler = _Recorder()
        declaration = _declaration(inputs=[
            CapabilityInput(name="region", type="string", default="eu"),
        ])
        service = _service(Capability(declaration=declaration, handler=handler))
        token = await _token(service, ["book"], "book")

        result = await service.invoke("book", token, {})

        _assert_invalid_parameters(result, "book is missing required input(s): region")
        assert handler.calls == []

    async def test_valid_call_reaches_the_handler_with_defaults_and_extras(self):
        handler = _Recorder()
        service = _service(Capability(declaration=_declaration(), handler=handler))
        token = await _token(service, ["book"], "book")

        result = await service.invoke("book", token, {**VALID, "undeclared": {"k": [1]}})

        assert result["success"] is True, result
        assert handler.calls == [
            {**VALID, "passengers": 1, "undeclared": {"k": [1]}},
        ]

    async def test_integral_float_reaches_the_handler(self):
        handler = _Recorder()
        service = _service(Capability(declaration=_declaration(), handler=handler))
        token = await _token(service, ["book"], "book")

        result = await service.invoke("book", token, {**VALID, "passengers": 5.0})

        assert result["success"] is True, result
        assert handler.calls[0]["passengers"] == 5

    async def test_capability_without_inputs_accepts_anything(self):
        handler = _Recorder()
        service = _service(Capability(declaration=_declaration(inputs=[]), handler=handler))
        token = await _token(service, ["book"], "book")

        for parameters in ({}, None, {"anything": 1}):
            result = await service.invoke("book", token, parameters)  # type: ignore[arg-type]
            assert result["success"] is True, result

    async def test_hooks_see_the_refusal(self):
        ended: list[dict[str, Any]] = []
        durations: list[dict[str, Any]] = []
        started: list[dict[str, Any]] = []
        hooks = ANIPHooks(
            logging=LoggingHooks(
                on_invocation_start=started.append, on_invocation_end=ended.append),
            metrics=MetricsHooks(on_invocation_duration=durations.append),
        )
        service = _service(
            Capability(declaration=_declaration(), handler=_Recorder()), hooks=hooks)
        token = await _token(service, ["book"], "book")

        result = await service.invoke("book", token, {})

        assert result["failure"]["type"] == "invalid_parameters"
        assert started == []
        assert len(ended) == 1
        assert ended[0]["success"] is False
        assert ended[0]["failure_type"] == "invalid_parameters"
        assert ended[0]["invocation_id"] == result["invocation_id"]
        assert [(d["capability"], d["success"]) for d in durations] == [("book", False)]

    async def test_streaming_invocation_is_refused_the_same_way(self):
        handler = _Recorder()
        events: list[dict[str, Any]] = []

        async def sink(event):
            events.append(event)

        declaration = _declaration(
            response_modes=[ResponseMode.UNARY, ResponseMode.STREAMING])
        service = _service(Capability(declaration=declaration, handler=handler))
        token = await _token(service, ["book"], "book")

        result = await service.invoke(
            "book", token, {"flight_number": 7, "date": "2026-03-10"},
            stream=True, _progress_sink=sink)

        _assert_invalid_parameters(
            result, "book has invalid input(s): 'flight_number' must be string, got number")
        assert handler.calls == []
        assert events == []
        entry = await _audit_entry(service, token, result["invocation_id"])
        assert entry["failure_type"] == "invalid_parameters"

    async def test_handler_raised_invalid_parameters_gets_the_same_resolution(self):
        def handler(ctx, params):
            raise ANIPError("invalid_parameters", "flight_number must not be empty")

        service = _service(Capability(declaration=_declaration(), handler=handler))
        token = await _token(service, ["book"], "book")

        result = await service.invoke("book", token, {**VALID, "flight_number": ""})

        assert result["failure"] == {
            "type": "invalid_parameters",
            "detail": "flight_number must not be empty",
            "resolution": EXPECTED_RESOLUTION,
            "retry": False,
        }

    async def test_handler_raised_invalid_parameters_keeps_its_own_resolution(self):
        own = {"action": "check_manifest", "recovery_class": "revalidate_then_retry"}

        def handler(ctx, params):
            raise ANIPError("invalid_parameters", "unknown flight class", resolution=dict(own))

        service = _service(Capability(declaration=_declaration(), handler=handler))
        token = await _token(service, ["book"], "book")

        result = await service.invoke("book", token, dict(VALID))

        assert result["failure"] == {
            "type": "invalid_parameters",
            "detail": "unknown flight class",
            "resolution": own,
            "retry": False,
        }


# ---------------------------------------------------------------------------
# Position in the pipeline
# ---------------------------------------------------------------------------


class TestOrder:
    async def test_scope_is_checked_first(self):
        service = _service(Capability(declaration=_declaration(), handler=_Recorder()))
        token = await _token(service, ["other"], "book")

        result = await service.invoke("book", token, {})

        assert result["failure"]["type"] in ("scope_insufficient", "insufficient_authority")

    async def test_purpose_is_checked_first(self):
        service = _service(
            Capability(declaration=_declaration(), handler=_Recorder()),
            Capability(declaration=_declaration("other"), handler=_Recorder()),
        )
        token = await _token(service, ["book"], "other")

        result = await service.invoke("book", token, {})

        assert result["failure"]["type"] == "purpose_mismatch"

    async def test_binding_is_checked_first(self):
        declaration = _declaration(
            inputs=[
                CapabilityInput(name="flight_number", type="string"),
                CapabilityInput(name="quote", type="object", required=False),
            ],
            requires_binding=[BindingRequirement(type="quote", field="quote")],
        )
        service = _service(Capability(declaration=declaration, handler=_Recorder()))
        token = await _token(service, ["book"], "book")

        missing_both = await service.invoke("book", token, {})
        assert missing_both["failure"]["type"] == "binding_missing"

        with_binding = await service.invoke("book", token, {"quote": {"id": "q"}})
        _assert_invalid_parameters(
            with_binding, "book is missing required input(s): flight_number")

        wrong_binding_type = await service.invoke(
            "book", token, {"flight_number": "AA1", "quote": "qt-1"})
        _assert_invalid_parameters(
            wrong_binding_type, "book has invalid input(s): 'quote' must be object, got string")

    async def test_budget_is_checked_first(self):
        declaration = _declaration(
            cost=Cost(certainty=CostCertainty.FIXED,
                      financial=FinancialCost(currency="USD", amount=500)),
        )
        service = _service(Capability(declaration=declaration, handler=_Recorder()))
        token = await _token(service, ["book"], "book")

        result = await service.invoke(
            "book", token, {}, budget={"currency": "USD", "max_amount": 1})

        assert result["failure"]["type"] == "budget_exceeded"

    async def test_control_requirement_is_checked_first(self):
        declaration = _declaration(
            control_requirements=[ControlRequirement(type="cost_ceiling")])
        service = _service(Capability(declaration=declaration, handler=_Recorder()))
        token = await _token(service, ["book"], "book")

        result = await service.invoke("book", token, {})
        assert result["failure"]["type"] == "control_requirement_unsatisfied"

        with_budget = await service.invoke(
            "book", token, {}, budget={"currency": "USD", "max_amount": 10})
        assert with_budget["failure"]["type"] == "invalid_parameters"

    async def test_no_lock_is_taken(self):
        service = _service(Capability(
            declaration=_declaration(), handler=_Recorder(), exclusive_lock=True))
        token = await _token(service, ["book"], "book")
        acquired: list[Any] = []
        original = service._engine.acquire_exclusive_lock

        async def spy(*args, **kwargs):
            acquired.append(args)
            return await original(*args, **kwargs)

        service._engine.acquire_exclusive_lock = spy  # type: ignore[method-assign]

        refused = await service.invoke("book", token, {})
        assert refused["failure"]["type"] == "invalid_parameters"
        assert acquired == []

        accepted = await service.invoke("book", token, dict(VALID))
        assert accepted["success"] is True, accepted
        assert len(acquired) == 1


def _approval_capability(handler_calls: list[dict[str, Any]]) -> Capability:
    declaration = _declaration(
        "transfer",
        inputs=[
            CapabilityInput(name="amount", type="number"),
            CapabilityInput(name="to_account", type="string"),
        ],
        grant_policy=GrantPolicy(
            allowed_grant_types=["one_time"], default_grant_type="one_time",
            expires_in_seconds=900, max_uses=1),
    )

    def handler(ctx, params):
        handler_calls.append(params)
        if params["amount"] > 10000 and not ctx.approval_grant:
            raise ANIPError(
                "approval_required", "needs approval",
                resolution={"action": "request_approval", "recovery_class": "wait_then_retry"})
        return {"ok": True}

    return Capability(declaration=declaration, handler=handler)


class TestApprovals:
    async def test_invalid_call_creates_no_approval_request(self):
        calls: list[dict[str, Any]] = []
        service = _service(_approval_capability(calls))
        token = await _token(service, ["book"], "transfer")

        control = await service.invoke(
            "transfer", token, {"amount": 50000, "to_account": "acct-1"})
        assert control["failure"]["type"] == "approval_required"
        assert len(calls) == 1

        refused = await service.invoke(
            "transfer", token, {"amount": 50000, "to_account": 12345})

        _assert_invalid_parameters(
            refused, "transfer has invalid input(s): 'to_account' must be string, got number")
        assert "approval_required" not in refused["failure"]
        assert len(calls) == 1
        entry = await _audit_entry(service, token, refused["invocation_id"])
        assert entry.get("approval_request_id") is None

    async def test_invalid_continuation_does_not_spend_the_grant(self):
        calls: list[dict[str, Any]] = []
        service = _service(_approval_capability(calls))
        token = await _token(service, ["book"], "transfer")
        approved = {"amount": 50000, "to_account": "acct-1"}
        first = await service.invoke("transfer", token, dict(approved))
        request_id = first["failure"]["approval_required"]["approval_request_id"]
        grant = await service.issue_approval_grant(
            request_id, "one_time", {"subject": "human:approver"})

        refused = await service.invoke(
            "transfer", token, {"amount": 50000, "to_account": 12345},
            approval_grant=grant["grant_id"])

        _assert_invalid_parameters(
            refused, "transfer has invalid input(s): 'to_account' must be string, got number")
        stored = await service._storage.get_grant(grant["grant_id"])
        assert stored["use_count"] == 0

        continued = await service.invoke(
            "transfer", token, dict(approved), approval_grant=grant["grant_id"])
        assert continued["success"] is True, continued
        stored = await service._storage.get_grant(grant["grant_id"])
        assert stored["use_count"] == 1


class TestComposition:
    def _service(self, child_handler) -> ANIPService:
        read = SideEffect(type=SideEffectType.READ, rollback_window="not_applicable")
        child = CapabilityDeclaration(
            name="lookup", description="child",
            inputs=[CapabilityInput(name="q", type="string")],
            output=CapabilityOutput(type="object", fields=["items"]),
            side_effect=read, minimum_scope=["s"],
        )
        parent = CapabilityDeclaration(
            name="summary", description="composed",
            inputs=[
                CapabilityInput(name="q", type="string"),
                CapabilityInput(name="limit", type="integer", required=False),
            ],
            output=CapabilityOutput(type="object", fields=["items"]),
            side_effect=read, minimum_scope=["s"],
            kind="composed",
            composition=Composition(
                authority_boundary="same_service",
                steps=[CompositionStep(id="find", capability="lookup", empty_result_source=True)],
                input_mapping={"find": {"q": "$.input.q"}},
                output_mapping={"items": "$.steps.find.output.items"},
                empty_result_policy="return_success_no_results",
                empty_result_output={"items": []},
                failure_policy=FailurePolicy(),
                audit_policy=AuditPolicy(
                    record_child_invocations=True, parent_task_lineage=True),
            ),
        )
        return _service(
            Capability(declaration=child, handler=child_handler),
            Capability(declaration=parent, handler=lambda ctx, params: {}),
        )

    async def test_composed_capability_is_checked_before_any_child_step(self):
        child = _Recorder({"items": [1]})
        service = self._service(child)
        token = await _token(service, ["s"], "summary")

        control = await service.invoke("summary", token, {"q": "x"})
        assert control["success"] is True, control
        assert len(child.calls) == 1

        refused = await service.invoke("summary", token, {"q": "x", "limit": "ten"})

        _assert_invalid_parameters(
            refused, "summary has invalid input(s): 'limit' must be integer, got string")
        assert len(child.calls) == 1

    async def test_child_step_is_checked_against_the_child_declaration(self):
        child = _Recorder({"items": [1]})
        service = self._service(child)
        token = await _token(service, ["s"], "summary")
        # The parent declares q as a string too, so reach the child directly
        # with what a mapping could hand it.
        result = await service._invoke_composition_child(
            "lookup", {"q": 5},
            caller_token=token, parent_invocation_id="inv-aaaaaaaaaaaa",
            task_id=None, client_reference_id=None, upstream_service=None,
        )

        assert result["failure"]["type"] == "invalid_parameters"
        assert result["failure"]["detail"] == (
            "lookup has invalid input(s): 'q' must be string, got number")
        assert child.calls == []


# ---------------------------------------------------------------------------
# Inputs that declare resolution.on_missing (SPEC.md §6.3 exception, §4.10)
# ---------------------------------------------------------------------------

ON_MISSING_VALUES = [
    "clarify", "use_default", "use_actor_scope", "app_select_or_clarify",
    "deny", "deny_or_clarify", "omit",
]


def _resolution_input(on_missing: str | None, *, type_: str = "string") -> CapabilityInput:
    resolution: dict[str, Any] = {"mode": "clarify"}
    if on_missing is not None:
        resolution["on_missing"] = on_missing
    extra: dict[str, Any] = {"default": "eu"} if on_missing == "use_default" else {}
    return CapabilityInput(name="region", type=type_, required=True, resolution=resolution, **extra)


class TestOnMissing:
    @pytest.mark.parametrize("on_missing", ON_MISSING_VALUES)
    @pytest.mark.parametrize("parameters", [{}, {"region": None}])
    def test_required_input_with_on_missing_is_not_missing(self, on_missing, parameters):
        inputs = [_resolution_input(on_missing)]
        assert inputs[0].required is True
        assert check_declared_inputs("cap", inputs, parameters) is None

    def test_resolution_without_on_missing_keeps_the_input_required(self):
        inputs = [_resolution_input(None)]
        assert inputs[0].resolution is not None and inputs[0].resolution.on_missing is None
        assert check_declared_inputs("cap", inputs, {}) == (
            "cap is missing required input(s): region")

    def test_on_ambiguous_or_on_unresolved_alone_keep_the_input_required(self):
        declared = CapabilityInput(
            name="region", type="string",
            resolution={"mode": "clarify", "on_ambiguous": "clarify", "on_unresolved": "deny"})
        assert check_declared_inputs("cap", [declared], {}) == (
            "cap is missing required input(s): region")

    def test_only_the_inputs_without_on_missing_are_named(self):
        inputs = [
            CapabilityInput(name="a", type="string"),
            _resolution_input("clarify"),
            CapabilityInput(name="z", type="string"),
        ]
        assert check_declared_inputs("cap", inputs, {}) == (
            "cap is missing required input(s): a, z")

    @pytest.mark.parametrize("on_missing", ON_MISSING_VALUES)
    def test_a_supplied_value_is_still_type_checked(self, on_missing):
        inputs = [_resolution_input(on_missing)]
        assert check_declared_inputs("cap", inputs, {"region": 5}) == (
            "cap has invalid input(s): 'region' must be string, got number")
        assert check_declared_inputs("cap", inputs, {"region": "eu"}) is None

    async def test_missing_on_missing_input_reaches_the_handler(self):
        handler = _Recorder()
        declaration = _declaration(inputs=[
            CapabilityInput(name="flight_number", type="string"),
            _resolution_input("clarify"),
        ])
        service = _service(Capability(declaration=declaration, handler=handler))
        token = await _token(service, ["book"], "book")

        absent = await service.invoke("book", token, {"flight_number": "AA1"})
        null = await service.invoke("book", token, {"flight_number": "AA1", "region": None})

        assert absent["success"] is True, absent
        assert null["success"] is True, null
        assert handler.calls == [
            {"flight_number": "AA1"}, {"flight_number": "AA1", "region": None},
        ]

    async def test_same_input_without_a_resolution_block_is_refused(self):
        handler = _Recorder()
        declaration = _declaration(inputs=[
            CapabilityInput(name="flight_number", type="string"),
            CapabilityInput(name="region", type="string", required=True),
        ])
        service = _service(Capability(declaration=declaration, handler=handler))
        token = await _token(service, ["book"], "book")

        result = await service.invoke("book", token, {"flight_number": "AA1"})

        _assert_invalid_parameters(result, "book is missing required input(s): region")
        assert handler.calls == []

    async def test_resolution_without_on_missing_is_refused(self):
        handler = _Recorder()
        declaration = _declaration(inputs=[
            CapabilityInput(name="flight_number", type="string"),
            _resolution_input(None),
        ])
        service = _service(Capability(declaration=declaration, handler=handler))
        token = await _token(service, ["book"], "book")

        result = await service.invoke("book", token, {"flight_number": "AA1"})

        _assert_invalid_parameters(result, "book is missing required input(s): region")
        assert handler.calls == []

    async def test_wrong_typed_value_for_an_on_missing_input_is_refused(self):
        handler = _Recorder()
        declaration = _declaration(inputs=[
            CapabilityInput(name="flight_number", type="string"),
            _resolution_input("clarify"),
        ])
        service = _service(Capability(declaration=declaration, handler=handler))
        token = await _token(service, ["book"], "book")

        result = await service.invoke("book", token, {"flight_number": "AA1", "region": ["eu"]})

        _assert_invalid_parameters(
            result, "book has invalid input(s): 'region' must be string, got array")
        assert handler.calls == []

    async def test_use_default_applies_the_default_for_the_handler(self):
        handler = _Recorder()
        declaration = _declaration(inputs=[_resolution_input("use_default")])
        service = _service(Capability(declaration=declaration, handler=handler))
        token = await _token(service, ["book"], "book")

        result = await service.invoke("book", token, {})

        assert result["success"] is True, result
        assert handler.calls == [{"region": "eu"}]
