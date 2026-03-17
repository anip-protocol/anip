"""Event classification for v0.8 security hardening."""

_MALFORMED_FAILURE_TYPES = frozenset({
    "unknown_capability",
    "streaming_not_supported",
    "internal_error",
})

_HIGH_RISK_SIDE_EFFECTS = frozenset({
    "write",
    "irreversible",
    "transactional",
})


def classify_event(
    side_effect_type: str | None,
    success: bool,
    failure_type: str | None,
) -> str:
    if side_effect_type is None:
        return "malformed_or_spam"
    if success:
        if side_effect_type in _HIGH_RISK_SIDE_EFFECTS:
            return "high_risk_success"
        return "low_risk_success"
    if failure_type in _MALFORMED_FAILURE_TYPES:
        return "malformed_or_spam"
    return "high_risk_denial"
