"""JWKS construction for ANIP services."""

from .keys import KeyManager


def build_jwks(key_manager: KeyManager) -> dict:
    """Build a JWKS response containing both public keys."""
    return key_manager.get_jwks()
