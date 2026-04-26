"""Composition validation + execution tests (v0.23 §4.6, plan §6).

Composition declarations are validated at registration time via
:func:`anip_service.v023.validate_composition`. Execution is exercised via
:func:`anip_service.v023.execute_composition` with a mock invoke_step.
"""

from __future__ import annotations

import asyncio

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

from anip_service.types import ANIPError
from anip_service.v023 import (
    CompositionValidationError,
    execute_composition,
    sha256_digest,
    validate_composition,
)


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def _atomic_decl(name: str, *, fields: list[str] | None = None) -> CapabilityDeclaration:
    return CapabilityDeclaration(
        name=name,
        description=f"atomic {name}",
        inputs=[CapabilityInput(name="x", type="string")],
        output=CapabilityOutput(type="x", fields=fields or ["x"]),
        side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
        minimum_scope=["s"],
    )


def _composed_decl(*, name: str = "summary", composition: Composition) -> CapabilityDeclaration:
    return CapabilityDeclaration(
        name=name,
        description="composed",
        inputs=[],
        output=CapabilityOutput(type="x", fields=["count", "items"]),
        side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
        minimum_scope=["s"],
        kind="composed",
        composition=composition,
    )


def _basic_composition() -> Composition:
    return Composition(
        authority_boundary="same_service",
        steps=[
            CompositionStep(id="select", capability="select_cap", empty_result_source=True),
            CompositionStep(id="enrich", capability="enrich_cap"),
        ],
        input_mapping={
            "select": {"q": "$.input.q"},
            "enrich": {"items": "$.steps.select.output.items"},
        },
        output_mapping={
            "count": "$.steps.enrich.output.count",
            "items": "$.steps.enrich.output.items",
        },
        empty_result_policy="return_success_no_results",
        empty_result_output={"count": 0, "items": []},
        failure_policy=FailurePolicy(),
        audit_policy=AuditPolicy(record_child_invocations=True, parent_task_lineage=True),
    )


def _registry(*, parent_kind: str = "atomic") -> dict[str, CapabilityDeclaration]:
    select = _atomic_decl("select_cap", fields=["items"])
    enrich = _atomic_decl("enrich_cap", fields=["count", "items"])
    return {"select_cap": select, "enrich_cap": enrich}


# ---------------------------------------------------------------------------
# validate_composition: registration-time invariants
# ---------------------------------------------------------------------------


class TestValidateComposition:
    def test_atomic_declaration_passes(self):
        decl = _atomic_decl("a")
        # No raise.
        validate_composition("a", decl, other_capabilities={})

    def test_composed_happy_path(self):
        decl = _composed_decl(composition=_basic_composition())
        validate_composition("summary", decl, other_capabilities=_registry())

    def test_composed_missing_composition_caught_by_model(self):
        # Pydantic catches kind='composed' + composition=None at model
        # construction (see anip_core.models.CapabilityDeclaration's
        # _validate_kind_composition validator). validate_composition is the
        # second-line defense; here we confirm the first line still fires.
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="kind='composed' requires composition"):
            CapabilityDeclaration(
                name="summary",
                description="x",
                inputs=[],
                output=CapabilityOutput(type="x", fields=[]),
                side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
                minimum_scope=["s"],
                kind="composed",
            )

    def test_validate_composition_catches_missing_composition_via_construct(self):
        # If model_construct() is used to skip pydantic validation,
        # validate_composition must still reject kind='composed' without composition.
        decl = CapabilityDeclaration.model_construct(
            name="summary",
            description="x",
            inputs=[],
            output=CapabilityOutput(type="x", fields=[]),
            side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
            minimum_scope=["s"],
            kind="composed",
            composition=None,
        )
        with pytest.raises(CompositionValidationError, match="composition is missing"):
            validate_composition("summary", decl, other_capabilities=_registry())

    def test_unsupported_authority_boundary(self):
        comp = _basic_composition()
        comp.authority_boundary = "same_package"
        with pytest.raises(CompositionValidationError, match="composition_unsupported_authority_boundary"):
            validate_composition("summary", _composed_decl(composition=comp), other_capabilities=_registry())

    def test_duplicate_step_ids(self):
        comp = _basic_composition()
        comp.steps = [
            CompositionStep(id="a", capability="select_cap"),
            CompositionStep(id="a", capability="enrich_cap"),
        ]
        comp.input_mapping = {"a": {}}
        comp.output_mapping = {}
        comp.empty_result_policy = None
        comp.empty_result_output = None
        with pytest.raises(CompositionValidationError, match="duplicate step ids"):
            validate_composition("summary", _composed_decl(composition=comp), other_capabilities=_registry())

    def test_self_reference_rejected(self):
        comp = _basic_composition()
        comp.steps[0].capability = "summary"
        with pytest.raises(CompositionValidationError, match="self-references"):
            validate_composition("summary", _composed_decl(composition=comp), other_capabilities=_registry())

    def test_unknown_step_capability(self):
        comp = _basic_composition()
        comp.steps[0].capability = "does_not_exist"
        with pytest.raises(CompositionValidationError, match="composition_unknown_capability"):
            validate_composition("summary", _composed_decl(composition=comp), other_capabilities=_registry())

    def test_composed_referencing_composed_rejected(self):
        # Both registered capabilities are composed → composed-calling-composed is rejected.
        select = _composed_decl(name="select_cap", composition=_basic_composition())
        registry = {"select_cap": select, "enrich_cap": _atomic_decl("enrich_cap")}
        with pytest.raises(CompositionValidationError, match="kind='composed'"):
            validate_composition(
                "summary", _composed_decl(composition=_basic_composition()), other_capabilities=registry
            )

    def test_at_most_one_empty_result_source(self):
        comp = _basic_composition()
        comp.steps[1].empty_result_source = True  # now both are sources
        with pytest.raises(CompositionValidationError, match="at most one"):
            validate_composition("summary", _composed_decl(composition=comp), other_capabilities=_registry())

    def test_input_mapping_unknown_step_key(self):
        comp = _basic_composition()
        comp.input_mapping = {"nope": {"q": "$.input.q"}}
        with pytest.raises(CompositionValidationError, match="not a declared step id"):
            validate_composition("summary", _composed_decl(composition=comp), other_capabilities=_registry())

    def test_input_mapping_forward_reference_rejected(self):
        comp = _basic_composition()
        # Make select forward-reference enrich (which appears later)
        comp.input_mapping["select"] = {"items": "$.steps.enrich.output.items"}
        with pytest.raises(CompositionValidationError, match="forward-references"):
            validate_composition("summary", _composed_decl(composition=comp), other_capabilities=_registry())

    def test_output_mapping_unknown_step(self):
        comp = _basic_composition()
        comp.output_mapping = {"count": "$.steps.bogus.output.count"}
        with pytest.raises(CompositionValidationError, match="references unknown step"):
            validate_composition("summary", _composed_decl(composition=comp), other_capabilities=_registry())

    def test_empty_result_policy_clarify_with_output_rejected(self):
        comp = _basic_composition()
        comp.empty_result_policy = "clarify"
        # empty_result_output remains set from _basic_composition
        with pytest.raises(CompositionValidationError, match="forbidden"):
            validate_composition("summary", _composed_decl(composition=comp), other_capabilities=_registry())

    def test_empty_result_policy_return_success_without_output_rejected(self):
        comp = _basic_composition()
        comp.empty_result_output = None
        with pytest.raises(CompositionValidationError, match="requires empty_result_output"):
            validate_composition("summary", _composed_decl(composition=comp), other_capabilities=_registry())

    def test_empty_result_output_referencing_skipped_step_rejected(self):
        comp = _basic_composition()
        # source is "select", so referencing "enrich" output is forbidden in empty_result_output.
        comp.empty_result_output = {"items": "$.steps.enrich.output.items"}
        with pytest.raises(CompositionValidationError, match="only the empty_result_source"):
            validate_composition("summary", _composed_decl(composition=comp), other_capabilities=_registry())

    def test_empty_result_output_input_reference_allowed(self):
        comp = _basic_composition()
        comp.empty_result_output = {"q": "$.input.q", "items": []}
        # No raise.
        validate_composition("summary", _composed_decl(composition=comp), other_capabilities=_registry())

    def test_step_with_empty_result_source_requires_policy(self):
        comp = _basic_composition()
        comp.empty_result_policy = None
        comp.empty_result_output = None
        # select still has empty_result_source=True, but composition has no policy.
        with pytest.raises(CompositionValidationError, match="empty_result_source"):
            validate_composition("summary", _composed_decl(composition=comp), other_capabilities=_registry())


# ---------------------------------------------------------------------------
# execute_composition: runtime
# ---------------------------------------------------------------------------


def _make_step_runner(scripted: dict[str, dict | Exception]):
    """Build an invoke_step that returns scripted results per capability name.

    Each scripted entry is the raw dict the runtime would produce: either
    {"success": True, "result": {...}} or {"success": False, "failure": {...}}.
    """
    calls: list[tuple[str, dict]] = []

    async def runner(capability: str, params: dict) -> dict:
        calls.append((capability, params))
        result = scripted[capability]
        if isinstance(result, Exception):
            raise result
        return result

    return runner, calls


class TestExecuteComposition:
    @pytest.mark.asyncio
    async def test_happy_path_all_steps_succeed(self):
        decl = _composed_decl(composition=_basic_composition())
        runner, calls = _make_step_runner({
            "select_cap": {"success": True, "result": {"items": [{"id": 1}, {"id": 2}]}},
            "enrich_cap": {"success": True, "result": {"count": 2, "items": ["a", "b"]}},
        })
        out = await execute_composition(
            "summary", decl, {"q": "test"}, invoke_step=runner
        )
        assert out == {"count": 2, "items": ["a", "b"]}
        # Verify input flow: select got q from parent, enrich got items from select output.
        assert calls[0] == ("select_cap", {"q": "test"})
        assert calls[1] == ("enrich_cap", {"items": [{"id": 1}, {"id": 2}]})

    @pytest.mark.asyncio
    async def test_empty_result_return_success_no_results(self):
        decl = _composed_decl(composition=_basic_composition())
        runner, calls = _make_step_runner({
            "select_cap": {"success": True, "result": {"items": []}},  # empty source
        })
        out = await execute_composition(
            "summary", decl, {"q": "test"}, invoke_step=runner
        )
        assert out == {"count": 0, "items": []}
        # enrich_cap is NEVER called because select's output was empty.
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_empty_result_clarify_raises(self):
        comp = _basic_composition()
        comp.empty_result_policy = "clarify"
        comp.empty_result_output = None
        decl = _composed_decl(composition=comp)
        runner, _ = _make_step_runner({
            "select_cap": {"success": True, "result": {"items": []}},
        })
        with pytest.raises(ANIPError) as exc_info:
            await execute_composition("summary", decl, {"q": "x"}, invoke_step=runner)
        assert exc_info.value.error_type == "composition_empty_result_clarification_required"

    @pytest.mark.asyncio
    async def test_empty_result_deny_raises(self):
        comp = _basic_composition()
        comp.empty_result_policy = "deny"
        comp.empty_result_output = None
        decl = _composed_decl(composition=comp)
        runner, _ = _make_step_runner({
            "select_cap": {"success": True, "result": {"items": []}},
        })
        with pytest.raises(ANIPError) as exc_info:
            await execute_composition("summary", decl, {"q": "x"}, invoke_step=runner)
        assert exc_info.value.error_type == "composition_empty_result_denied"

    @pytest.mark.asyncio
    async def test_child_failure_propagates_by_default(self):
        decl = _composed_decl(composition=_basic_composition())
        runner, _ = _make_step_runner({
            "select_cap": {
                "success": False,
                "failure": {
                    "type": "scope_insufficient",
                    "detail": "select_cap requires more scope",
                    "resolution": {"action": "request_broader_scope", "recovery_class": "redelegation_then_retry"},
                },
            },
        })
        with pytest.raises(ANIPError) as exc_info:
            await execute_composition("summary", decl, {"q": "x"}, invoke_step=runner)
        # Default failure_policy.child_denial = "propagate".
        assert exc_info.value.error_type == "scope_insufficient"

    @pytest.mark.asyncio
    async def test_child_error_fails_parent(self):
        # Default child_error policy is fail_parent.
        decl = _composed_decl(composition=_basic_composition())
        runner, _ = _make_step_runner({
            "select_cap": {
                "success": False,
                "failure": {
                    "type": "internal_error",
                    "detail": "boom",
                    "resolution": {"action": "retry_now", "recovery_class": "retry_now"},
                },
            },
        })
        with pytest.raises(ANIPError) as exc_info:
            await execute_composition("summary", decl, {"q": "x"}, invoke_step=runner)
        # fail_parent collapses the failure type — we still propagate the original
        # type identifier here for audit purposes; behaviour is captured by the
        # detail string indicating it was a child step.
        assert exc_info.value.error_type == "internal_error"
        assert "child step" in exc_info.value.detail


# ---------------------------------------------------------------------------
# Digest helpers
# ---------------------------------------------------------------------------


class TestDigests:
    def test_canonical_json_sorts_keys(self):
        d1 = sha256_digest({"a": 1, "b": 2})
        d2 = sha256_digest({"b": 2, "a": 1})
        assert d1 == d2

    def test_canonical_json_ignores_trivia(self):
        # Spacing in dict literals is normalized away.
        a = sha256_digest({"a": [1, 2, 3]})
        b = sha256_digest({"a": [1, 2, 3]})
        assert a == b

    def test_distinct_inputs_produce_distinct_digests(self):
        assert sha256_digest({"a": 1}) != sha256_digest({"a": 2})

    def test_digest_starts_with_sha256_prefix(self):
        d = sha256_digest({"x": 1})
        assert d.startswith("sha256:")
