from datetime import datetime, timezone

from anip_service.retention import (
    DEFAULT_CLASS_TO_TIER,
    DEFAULT_TIER_TO_DURATION,
    RetentionPolicy,
)


# --- Default class-to-tier mapping (all 5 event classes) ---

def test_default_class_to_tier_high_risk_success():
    assert DEFAULT_CLASS_TO_TIER["high_risk_success"] == "long"


def test_default_class_to_tier_high_risk_denial():
    assert DEFAULT_CLASS_TO_TIER["high_risk_denial"] == "medium"


def test_default_class_to_tier_low_risk_success():
    assert DEFAULT_CLASS_TO_TIER["low_risk_success"] == "short"


def test_default_class_to_tier_repeated_low_value_denial():
    assert DEFAULT_CLASS_TO_TIER["repeated_low_value_denial"] == "aggregate_only"


def test_default_class_to_tier_malformed_or_spam():
    assert DEFAULT_CLASS_TO_TIER["malformed_or_spam"] == "short"


# --- Default tier-to-duration mapping (all 4 tiers) ---

def test_default_tier_to_duration_long():
    assert DEFAULT_TIER_TO_DURATION["long"] == "P365D"


def test_default_tier_to_duration_medium():
    assert DEFAULT_TIER_TO_DURATION["medium"] == "P90D"


def test_default_tier_to_duration_short():
    assert DEFAULT_TIER_TO_DURATION["short"] == "P7D"


def test_default_tier_to_duration_aggregate_only():
    assert DEFAULT_TIER_TO_DURATION["aggregate_only"] == "P1D"


# --- resolve_tier uses defaults ---

def test_resolve_tier_defaults():
    policy = RetentionPolicy()
    assert policy.resolve_tier("high_risk_success") == "long"
    assert policy.resolve_tier("high_risk_denial") == "medium"
    assert policy.resolve_tier("low_risk_success") == "short"
    assert policy.resolve_tier("repeated_low_value_denial") == "aggregate_only"
    assert policy.resolve_tier("malformed_or_spam") == "short"


def test_resolve_tier_unknown_class_falls_back_to_short():
    policy = RetentionPolicy()
    assert policy.resolve_tier("totally_unknown") == "short"


# --- resolve_tier with custom override ---

def test_resolve_tier_custom_override():
    policy = RetentionPolicy(class_to_tier={"high_risk_denial": "long"})
    assert policy.resolve_tier("high_risk_denial") == "long"
    # Other defaults still work
    assert policy.resolve_tier("high_risk_success") == "long"
    assert policy.resolve_tier("low_risk_success") == "short"


# --- compute_expires_at ---

def test_compute_expires_at_short_tier():
    policy = RetentionPolicy()
    now = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    result = policy.compute_expires_at("short", now=now)
    assert result == "2025-01-08T00:00:00+00:00"


def test_compute_expires_at_long_tier():
    policy = RetentionPolicy()
    now = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    result = policy.compute_expires_at("long", now=now)
    assert result == "2026-01-01T00:00:00+00:00"


def test_compute_expires_at_returns_none_for_null_duration():
    policy = RetentionPolicy(tier_to_duration={"custom": None})
    now = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    result = policy.compute_expires_at("custom", now=now)
    assert result is None


# --- aggregate_only maps to P1D (shorter than short/P7D) ---

def test_aggregate_only_expires_at_p1d():
    policy = RetentionPolicy()
    now = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    agg_result = policy.compute_expires_at("aggregate_only", now=now)
    assert agg_result == "2025-06-16T12:00:00+00:00"


def test_aggregate_only_differs_from_short():
    policy = RetentionPolicy()
    now = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    short_result = policy.compute_expires_at("short", now=now)
    agg_result = policy.compute_expires_at("aggregate_only", now=now)
    assert short_result != agg_result


# --- Full pipeline: classify -> resolve tier -> compute expires_at ---

def test_full_pipeline():
    from anip_service.classification import classify_event

    policy = RetentionPolicy()
    now = datetime(2025, 3, 1, 0, 0, 0, tzinfo=timezone.utc)

    # write + success -> high_risk_success -> long -> P365D
    event_class = classify_event("write", True, None)
    tier = policy.resolve_tier(event_class)
    expires = policy.compute_expires_at(tier, now=now)

    assert event_class == "high_risk_success"
    assert tier == "long"
    assert expires == "2026-03-01T00:00:00+00:00"
