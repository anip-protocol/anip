"""Tests for caller-class-aware disclosure resolution."""
import pytest
from anip_service.disclosure import resolve_disclosure_level


class TestFixedMode:
    def test_full_returns_full(self):
        assert resolve_disclosure_level("full", token_claims={}) == "full"

    def test_reduced_returns_reduced(self):
        assert resolve_disclosure_level("reduced", token_claims={}) == "reduced"

    def test_redacted_returns_redacted(self):
        assert resolve_disclosure_level("redacted", token_claims={}) == "redacted"

    def test_fixed_mode_ignores_token_claims(self):
        """In fixed mode, token caller_class is irrelevant."""
        result = resolve_disclosure_level(
            "redacted",
            token_claims={"anip:caller_class": "internal"},
            disclosure_policy={"internal": "full"},
        )
        assert result == "redacted"


class TestPolicyMode:
    def test_resolves_from_caller_class(self):
        result = resolve_disclosure_level(
            "policy",
            token_claims={"anip:caller_class": "internal"},
            disclosure_policy={"internal": "full", "default": "redacted"},
        )
        assert result == "full"

    def test_falls_back_to_default(self):
        result = resolve_disclosure_level(
            "policy",
            token_claims={"anip:caller_class": "unknown_class"},
            disclosure_policy={"internal": "full", "default": "reduced"},
        )
        assert result == "reduced"

    def test_falls_back_to_redacted_when_no_default(self):
        result = resolve_disclosure_level(
            "policy",
            token_claims={"anip:caller_class": "unknown_class"},
            disclosure_policy={"internal": "full"},
        )
        assert result == "redacted"

    def test_no_token_claim_uses_default(self):
        result = resolve_disclosure_level(
            "policy",
            token_claims={},
            disclosure_policy={"internal": "full", "default": "reduced"},
        )
        assert result == "reduced"

    def test_scope_derived_class(self):
        """If no anip:caller_class claim, derive from scope."""
        result = resolve_disclosure_level(
            "policy",
            token_claims={"scope": ["audit:full", "travel.search"]},
            disclosure_policy={"audit_full": "full", "default": "redacted"},
        )
        assert result == "full"

    def test_no_policy_in_policy_mode_returns_redacted(self):
        result = resolve_disclosure_level(
            "policy",
            token_claims={"anip:caller_class": "internal"},
            disclosure_policy=None,
        )
        assert result == "redacted"

    def test_policy_mode_with_none_claims(self):
        result = resolve_disclosure_level(
            "policy",
            token_claims=None,
            disclosure_policy={"default": "reduced"},
        )
        assert result == "reduced"
