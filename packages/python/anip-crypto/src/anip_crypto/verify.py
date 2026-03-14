"""Verification helpers for ANIP signed artifacts."""

import hashlib

import jwt as pyjwt

from .canonicalize import canonicalize
from .keys import KeyManager


def verify_audit_entry_signature(
    key_manager: KeyManager, entry: dict, signature: str
) -> dict:
    """Verify an audit entry's signature using the audit public key.

    Returns the decoded JWT claims on success, raises on failure.
    """
    claims = pyjwt.decode(
        signature,
        key_manager.audit_public_key,
        algorithms=["ES256"],
    )
    canonical = canonicalize(entry, exclude={"signature", "id"})
    expected_hash = hashlib.sha256(canonical).hexdigest()
    if claims.get("audit_hash") != expected_hash:
        raise ValueError("Audit hash mismatch")
    return claims
