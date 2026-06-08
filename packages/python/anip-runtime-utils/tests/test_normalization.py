from anip_runtime_utils.normalization import (
    apply_input_metadata_defaults_and_enums,
    infer_allowed_value_from_history,
    normalize_by_allowed_values,
    semantic_key,
)


def test_semantic_key_normalizes_free_text() -> None:
    assert semantic_key("Implementation Risk") == "implementation_risk"


def test_normalize_by_allowed_values_canonicalizes_alias_shape() -> None:
    value, change = normalize_by_allowed_values("implementation risk", ["pricing", "implementation_risk"])
    assert value == "implementation_risk"
    assert change == {
        "reason": "canonicalized_allowed_value",
        "from": "implementation risk",
        "to": "implementation_risk",
    }


def test_infer_allowed_value_from_history_carries_forward_single_match() -> None:
    history = [{"role": "user", "content": "Use inbound_last_week."}]
    assert infer_allowed_value_from_history(["inbound_last_week", "webinar_q2"], history) == "inbound_last_week"


def test_apply_input_metadata_defaults_and_enums_uses_defaults_and_history() -> None:
    normalized, applied = apply_input_metadata_defaults_and_enums(
        parameters={"channel": "call follow up"},
        metadata={
            "input_specs": [
                {"name": "objective", "allowed_values": ["first_touch", "follow_up"], "default": "first_touch"},
                {"name": "channel", "allowed_values": ["email", "linkedin", "call_follow_up"]},
            ]
        },
        history=[{"role": "user", "content": "Use follow_up."}],
    )
    assert normalized == {"channel": "call_follow_up", "objective": "follow_up"}
    assert applied == [
        {"field": "objective", "reason": "carried_forward_from_history", "from": None, "to": "follow_up"},
        {"field": "channel", "reason": "canonicalized_allowed_value", "from": "call follow up", "to": "call_follow_up"},
    ]
