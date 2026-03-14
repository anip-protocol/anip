"""Detached JWS operations for ANIP signed artifacts."""

from .keys import KeyManager


def sign_jws_detached(key_manager: KeyManager, payload: bytes) -> str:
    """Sign with the delegation key (for manifests)."""
    return key_manager.sign_jws_detached(payload)


def verify_jws_detached(key_manager: KeyManager, jws: str, payload: bytes) -> None:
    """Verify with the delegation public key."""
    key_manager.verify_jws_detached(jws, payload)


def sign_jws_detached_audit(key_manager: KeyManager, payload: bytes) -> str:
    """Sign with the audit key (for checkpoints)."""
    return key_manager.sign_jws_detached_audit(payload)


def verify_jws_detached_audit(key_manager: KeyManager, jws: str, payload: bytes) -> None:
    """Verify with the audit public key."""
    key_manager.verify_jws_detached_audit(jws, payload)
