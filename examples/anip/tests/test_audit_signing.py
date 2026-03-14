"""Tests for audit entry signing."""

from anip_flight_demo.data.database import log_invocation, query_audit_log


def test_audit_entries_have_signatures():
    log_invocation(
        capability="test_signed",
        token_id="test-sig-001",
        issuer="human:sig@example.com",
        subject="agent:test",
        root_principal="human:sig@example.com",
        parameters={"action": "test"},
        success=True,
    )
    entries = query_audit_log(root_principal="human:sig@example.com")
    signed_entries = [e for e in entries if e["capability"] == "test_signed"]
    assert len(signed_entries) >= 1
    assert signed_entries[0]["signature"] is not None
    assert len(signed_entries[0]["signature"]) > 0


def test_audit_jwks_has_audit_key():
    """JWKS should contain both delegation and audit keys."""
    from anip_flight_demo.primitives.crypto import KeyManager
    km = KeyManager()
    jwks = km.get_jwks()
    keys = jwks["keys"]
    assert len(keys) == 2
    uses = {k["use"] for k in keys}
    assert "sig" in uses
    assert "audit" in uses
