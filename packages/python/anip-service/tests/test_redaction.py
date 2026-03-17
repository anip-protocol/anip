"""Tests for failure detail redaction (v0.8)."""

from anip_service.redaction import redact_failure


class TestRedactFailure:

    SAMPLE_FAILURE = {
        "type": "scope_insufficient",
        "detail": "Token scope ['read'] does not include required scope 'admin:write' for capability 'dangerous.action'",
        "retry": True,
        "resolution": {
            "action": "request_scope",
            "requires": "admin:write",
            "grantable_by": "org-admin@example.com",
            "estimated_availability": "PT1H",
        },
    }

    def test_full_returns_unchanged(self):
        result = redact_failure(self.SAMPLE_FAILURE, "full")
        assert result == self.SAMPLE_FAILURE

    def test_reduced_strips_grantable_by(self):
        result = redact_failure(self.SAMPLE_FAILURE, "reduced")
        assert result["type"] == "scope_insufficient"
        assert result["retry"] is True
        assert result["resolution"]["grantable_by"] is None
        assert result["resolution"]["action"] == "request_scope"
        assert result["resolution"]["requires"] == "admin:write"
        assert result["resolution"]["estimated_availability"] == "PT1H"

    def test_reduced_truncates_detail(self):
        long_detail = "x" * 300
        failure = {**self.SAMPLE_FAILURE, "detail": long_detail}
        result = redact_failure(failure, "reduced")
        assert len(result["detail"]) <= 200

    def test_reduced_preserves_short_detail(self):
        result = redact_failure(self.SAMPLE_FAILURE, "reduced")
        assert result["detail"] == self.SAMPLE_FAILURE["detail"]

    def test_redacted_uses_generic_detail(self):
        result = redact_failure(self.SAMPLE_FAILURE, "redacted")
        assert result["type"] == "scope_insufficient"
        assert result["detail"] != self.SAMPLE_FAILURE["detail"]
        assert "admin:write" not in result["detail"]

    def test_redacted_strips_resolution_fields(self):
        result = redact_failure(self.SAMPLE_FAILURE, "redacted")
        assert result["resolution"]["requires"] is None
        assert result["resolution"]["grantable_by"] is None
        assert result["resolution"]["estimated_availability"] is None
        assert result["resolution"]["action"] == "request_scope"

    def test_redacted_preserves_retry(self):
        result = redact_failure(self.SAMPLE_FAILURE, "redacted")
        assert result["retry"] is True

    def test_type_is_never_redacted(self):
        for level in ("full", "reduced", "redacted"):
            result = redact_failure(self.SAMPLE_FAILURE, level)
            assert result["type"] == "scope_insufficient"

    def test_policy_treated_as_redacted(self):
        result = redact_failure(self.SAMPLE_FAILURE, "policy")
        redacted = redact_failure(self.SAMPLE_FAILURE, "redacted")
        assert result == redacted

    def test_failure_without_resolution(self):
        failure = {"type": "internal_error", "detail": "Something broke", "retry": False}
        result = redact_failure(failure, "redacted")
        assert result["type"] == "internal_error"
