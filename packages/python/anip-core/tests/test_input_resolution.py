"""v0.24 input resolution metadata — parse and round-trip."""
import pytest
from anip_core.models import (
    CapabilityInput,
    InputResolution,
    InputMeaning,
    ResolutionMode,
    ResolutionBehavior,
)
from pydantic import ValidationError


def test_minimal_input_no_resolution_block():
    """v0.23-compatible input parses unchanged."""
    inp = CapabilityInput(name="quarter", type="string")
    assert inp.resolution is None
    assert inp.semantic_type is None
    assert inp.entity_reference is False
    assert inp.allowed_values is None
    assert inp.catalog_ref is None
    assert inp.input_meanings is None


def test_closed_values_resolution():
    inp = CapabilityInput(
        name="forecast_mode",
        type="string",
        required=False,
        default="risk_adjusted",
        allowed_values=["risk_adjusted", "likely", "best_case"],
        semantic_type="business_category",
        resolution=InputResolution(
            mode=ResolutionMode.CLOSED_VALUES,
            on_missing=ResolutionBehavior.USE_DEFAULT,
            on_ambiguous=ResolutionBehavior.CLARIFY,
        ),
    )
    assert inp.resolution.mode == ResolutionMode.CLOSED_VALUES


def test_backend_resolved_resolution():
    inp = CapabilityInput(
        name="cohort_ref",
        type="string",
        required=True,
        semantic_type="cohort_reference",
        entity_reference=True,
        catalog_ref="gtm.cohort_catalog",
        resolution=InputResolution(
            mode=ResolutionMode.BACKEND_RESOLVED,
            resolver_ref="gtm.cohort_catalog",
            on_missing=ResolutionBehavior.CLARIFY,
        ),
    )
    assert inp.resolution.resolver_ref == "gtm.cohort_catalog"
    assert inp.catalog_ref == "gtm.cohort_catalog"
    assert inp.entity_reference is True


def test_actor_policy_or_explicit_resolution():
    inp = CapabilityInput(
        name="owner_scope",
        type="string",
        required=False,
        semantic_type="scope_reference",
        resolution=InputResolution(
            mode=ResolutionMode.ACTOR_POLICY_OR_EXPLICIT,
            on_missing=ResolutionBehavior.USE_ACTOR_SCOPE,
            on_unresolved=ResolutionBehavior.DENY_OR_CLARIFY,
        ),
    )
    assert inp.resolution.mode == ResolutionMode.ACTOR_POLICY_OR_EXPLICIT


def test_input_meanings():
    inp = CapabilityInput(
        name="priority",
        type="string",
        input_meanings=[
            InputMeaning(label="High", value="P0", description="critical"),
            InputMeaning(label="Medium", value="P1"),
        ],
    )
    assert len(inp.input_meanings) == 2
    assert inp.input_meanings[1].description == ""  # default


def test_unknown_mode_rejected():
    """Schema-level enum rejection (no specific error string assertion)."""
    with pytest.raises(ValidationError):
        InputResolution(mode="not_a_real_mode")


def test_unknown_behavior_rejected():
    with pytest.raises(ValidationError):
        InputResolution(mode=ResolutionMode.CLARIFY, on_missing="not_real")


def test_missing_mode_rejected():
    """resolution.mode is required; {} body must fail decode."""
    with pytest.raises(ValidationError):
        InputResolution.model_validate({})


def test_closed_values_without_allowed_values_rejected():
    """D1.7 hard cross-field rule."""
    with pytest.raises(ValidationError):
        CapabilityInput(
            name="x",
            type="string",
            resolution=InputResolution(mode=ResolutionMode.CLOSED_VALUES),
        )


def test_use_default_without_default_rejected():
    """D1.7 hard cross-field rule."""
    with pytest.raises(ValidationError):
        CapabilityInput(
            name="x",
            type="string",
            default=None,
            resolution=InputResolution(
                mode=ResolutionMode.CLARIFY,
                on_missing=ResolutionBehavior.USE_DEFAULT,
            ),
        )


def test_round_trip_json():
    inp = CapabilityInput(
        name="cohort_ref",
        type="string",
        semantic_type="cohort_reference",
        entity_reference=True,
        catalog_ref="gtm.cohort_catalog",
        resolution=InputResolution(
            mode=ResolutionMode.BACKEND_RESOLVED,
            resolver_ref="gtm.cohort_catalog",
            on_missing=ResolutionBehavior.CLARIFY,
        ),
    )
    raw = inp.model_dump_json()
    parsed = CapabilityInput.model_validate_json(raw)
    assert parsed == inp


def test_v023_manifest_still_parses():
    v023_json = {"name": "q", "type": "string", "required": True}
    inp = CapabilityInput.model_validate(v023_json)
    assert inp.resolution is None
    assert inp.semantic_type is None
    assert inp.catalog_ref is None
