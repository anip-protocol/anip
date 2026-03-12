"""Key management and cryptographic operations for ANIP trust layer."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import jwt
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import (
    decode_dss_signature,
    encode_dss_signature,
)


def _b64url_encode(data: bytes) -> str:
    """Base64url encode without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    """Base64url decode, adding padding as needed."""
    s += "=" * (4 - len(s) % 4)
    return base64.urlsafe_b64decode(s)


class KeyManager:
    """Manages EC P-256 key pairs for JWT signing and JWKS publication."""

    def __init__(self, key_path: str | None = None) -> None:
        if key_path and Path(key_path).exists():
            self._load_keys(key_path)
        else:
            self._generate_keys()
            if key_path:
                self._save_keys(key_path)

    # ------------------------------------------------------------------ #
    # Key lifecycle
    # ------------------------------------------------------------------ #

    def _generate_keys(self) -> None:
        self._private_key = ec.generate_private_key(ec.SECP256R1())
        self._public_key = self._private_key.public_key()
        self._kid = self._derive_kid()

    def _derive_kid(self) -> str:
        pub_der = self._public_key.public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return hashlib.sha256(pub_der).hexdigest()[:16]

    def _save_keys(self, path: str) -> None:
        pem = self._private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode("utf-8")
        data = {"private_key_pem": pem, "kid": self._kid}
        Path(path).write_text(json.dumps(data))

    def _load_keys(self, path: str) -> None:
        data = json.loads(Path(path).read_text())
        loaded_key = serialization.load_pem_private_key(
            data["private_key_pem"].encode("utf-8"), password=None
        )
        if not isinstance(loaded_key, ec.EllipticCurvePrivateKey):
            raise TypeError("Expected EC private key, got " + type(loaded_key).__name__)
        self._private_key = loaded_key
        self._public_key = self._private_key.public_key()
        self._kid = data["kid"]

    # ------------------------------------------------------------------ #
    # Properties
    # ------------------------------------------------------------------ #

    @property
    def private_key(self) -> ec.EllipticCurvePrivateKey:
        return self._private_key

    @property
    def public_key(self) -> ec.EllipticCurvePublicKey:
        return self._public_key

    # ------------------------------------------------------------------ #
    # JWKS
    # ------------------------------------------------------------------ #

    def get_jwks(self) -> dict:
        """Return a JWKS containing the public key (no private material)."""
        numbers = self._public_key.public_numbers()
        x_bytes = numbers.x.to_bytes(32, "big")
        y_bytes = numbers.y.to_bytes(32, "big")
        return {
            "keys": [
                {
                    "kty": "EC",
                    "crv": "P-256",
                    "alg": "ES256",
                    "use": "sig",
                    "kid": self._kid,
                    "x": _b64url_encode(x_bytes),
                    "y": _b64url_encode(y_bytes),
                }
            ]
        }

    # ------------------------------------------------------------------ #
    # JWT operations
    # ------------------------------------------------------------------ #

    def sign_jwt(self, payload: dict) -> str:
        """Sign a JWT with ES256, including kid in the header."""
        return jwt.encode(
            payload,
            self._private_key,
            algorithm="ES256",
            headers={"kid": self._kid},
        )

    def verify_jwt(
        self, token: str, audience: str = "anip-flight-service"
    ) -> dict:
        """Verify a JWT signature and audience claim."""
        return jwt.decode(
            token,
            self._public_key,
            algorithms=["ES256"],
            audience=audience,
        )

    # ------------------------------------------------------------------ #
    # Detached JWS
    # ------------------------------------------------------------------ #

    def sign_jws_detached(self, payload: bytes) -> str:
        """Create a detached JWS (header..signature with empty payload)."""
        header = json.dumps(
            {"alg": "ES256", "kid": self._kid}, separators=(",", ":")
        )
        header_b64 = _b64url_encode(header.encode("utf-8"))
        payload_b64 = _b64url_encode(payload)

        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
        der_sig = self._private_key.sign(signing_input, ec.ECDSA(hashes.SHA256()))

        # Convert DER signature to raw r||s (32 bytes each for P-256)
        r, s = decode_dss_signature(der_sig)
        raw_sig = r.to_bytes(32, "big") + s.to_bytes(32, "big")
        sig_b64 = _b64url_encode(raw_sig)

        return f"{header_b64}..{sig_b64}"

    def verify_jws_detached(self, jws: str, payload: bytes) -> None:
        """Verify a detached JWS against the provided payload."""
        parts = jws.split(".")
        assert len(parts) == 3 and parts[1] == "", "Invalid detached JWS format"
        header_b64, _, sig_b64 = parts

        payload_b64 = _b64url_encode(payload)
        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")

        raw_sig = _b64url_decode(sig_b64)
        r = int.from_bytes(raw_sig[:32], "big")
        s = int.from_bytes(raw_sig[32:], "big")
        der_sig = encode_dss_signature(r, s)

        self._public_key.verify(der_sig, signing_input, ec.ECDSA(hashes.SHA256()))
