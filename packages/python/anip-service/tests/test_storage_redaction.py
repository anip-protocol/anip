"""Tests for storage-side redaction."""
import pytest
from anip_service.storage_redaction import storage_redact_entry

_LOW_VALUE_CLASSES = ["low_risk_success", "malformed_or_spam", "repeated_low_value_denial"]
_HIGH_VALUE_CLASSES = ["high_risk_success", "high_risk_denial"]


def _make_entry(event_class: str) -> dict:
    return {
        "sequence_number": 1,
        "timestamp": "2026-01-01T00:00:00Z",
        "capability": "search_flights",
        "token_id": "tok-1",
        "root_principal": "user@example.com",
        "parameters": {"origin": "JFK", "destination": "LAX"},
        "success": event_class.endswith("success"),
        "failure_type": None if event_class.endswith("success") else "scope_insufficient",
        "event_class": event_class,
        "retention_tier": "short",
        "invocation_id": "inv-000000000001",
    }


class TestStorageRedaction:
    @pytest.mark.parametrize("event_class", _LOW_VALUE_CLASSES)
    def test_low_value_strips_parameters(self, event_class: str):
        entry = _make_entry(event_class)
        result = storage_redact_entry(entry)
        assert "parameters" not in result or result["parameters"] is None
        assert result["storage_redacted"] is True

    @pytest.mark.parametrize("event_class", _HIGH_VALUE_CLASSES)
    def test_high_value_preserves_parameters(self, event_class: str):
        entry = _make_entry(event_class)
        result = storage_redact_entry(entry)
        assert result["parameters"] == {"origin": "JFK", "destination": "LAX"}
        assert result["storage_redacted"] is False

    def test_preserves_envelope_fields(self):
        entry = _make_entry("low_risk_success")
        result = storage_redact_entry(entry)
        assert result["timestamp"] == "2026-01-01T00:00:00Z"
        assert result["capability"] == "search_flights"
        assert result["token_id"] == "tok-1"
        assert result["event_class"] == "low_risk_success"
        assert result["invocation_id"] == "inv-000000000001"

    def test_does_not_mutate_original(self):
        entry = _make_entry("low_risk_success")
        original_params = entry["parameters"].copy()
        storage_redact_entry(entry)
        assert entry["parameters"] == original_params

    def test_no_event_class_treated_as_high_value(self):
        """Entry without event_class is not redacted (safe default)."""
        entry = _make_entry("high_risk_success")
        del entry["event_class"]
        result = storage_redact_entry(entry)
        assert result["parameters"] is not None
        assert result["storage_redacted"] is False
