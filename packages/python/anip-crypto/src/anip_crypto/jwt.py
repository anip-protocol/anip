"""JWT signing and verification for ANIP delegation tokens."""

from .keys import KeyManager


def sign_jwt(key_manager: KeyManager, payload: dict) -> str:
    """Sign a JWT with the delegation key (ES256)."""
    return key_manager.sign_jwt(payload)


def verify_jwt(key_manager: KeyManager, token: str, *, audience: str) -> dict:
    """Verify a JWT signature and audience."""
    return key_manager.verify_jwt(token, audience=audience)
