"""ANIP Crypto — key management, JWT, JWS, JWKS."""

from .canonicalize import canonicalize
from .jwks import build_jwks
from .jws import (
    sign_jws_detached,
    sign_jws_detached_audit,
    verify_jws_detached,
    verify_jws_detached_audit,
)
from .jwt import sign_jwt, verify_jwt
from .keys import KeyManager
from .verify import verify_audit_entry_signature

__all__ = [
    "KeyManager",
    "canonicalize",
    "sign_jwt",
    "verify_jwt",
    "sign_jws_detached",
    "verify_jws_detached",
    "sign_jws_detached_audit",
    "verify_jws_detached_audit",
    "build_jwks",
    "verify_audit_entry_signature",
]
