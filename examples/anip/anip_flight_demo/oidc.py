"""OIDC token validation for the ANIP example app.

Validates external OIDC/OAuth2 JWTs against a provider's JWKS endpoint.
Maps OIDC claims to ANIP principal identifiers.

This is example-app code, not an SDK package. Real deployments should
define their own claim-to-principal mapping policy.
"""
from __future__ import annotations

import time
from typing import Any

import httpx
import jwt as pyjwt
from jwt import PyJWKClient


class OidcValidator:
    """Validates OIDC bearer tokens and maps claims to ANIP principals.

    Fully synchronous — the ANIPService authenticate callback is sync.
    JWKS discovery and fetching use httpx sync client. PyJWKClient
    handles JWKS caching and kid-miss refresh internally.

    Args:
        issuer_url: Expected issuer (iss claim).
        audience: Expected audience (aud claim).
        jwks_url: Explicit JWKS URL. If not set, discovered from issuer.
    """

    def __init__(
        self,
        issuer_url: str,
        audience: str,
        jwks_url: str | None = None,
    ):
        self.issuer_url = issuer_url.rstrip("/")
        self.audience = audience
        self._jwks_url = jwks_url
        self._jwk_client: PyJWKClient | None = None
        self._discovery_done = False

    def _get_jwk_client(self) -> PyJWKClient | None:
        """Get or create the JWKS client, discovering the URL if needed."""
        if self._jwk_client is not None:
            return self._jwk_client

        jwks_url = self._jwks_url

        # Discover JWKS URL from OIDC discovery if not explicit
        if not jwks_url and not self._discovery_done:
            self._discovery_done = True
            try:
                discovery_url = f"{self.issuer_url}/.well-known/openid-configuration"
                resp = httpx.get(discovery_url, timeout=10)
                if resp.status_code == 200:
                    jwks_url = resp.json().get("jwks_uri")
            except Exception:
                return None

        if not jwks_url:
            return None

        # PyJWKClient handles caching and kid-miss refresh internally
        self._jwk_client = PyJWKClient(jwks_url)
        return self._jwk_client

    def validate(self, bearer: str) -> str | None:
        """Validate an OIDC bearer token and return an ANIP principal, or None.

        Synchronous — matches the ANIPService authenticate callback signature.
        """
        try:
            client = self._get_jwk_client()
            if client is None:
                return None

            # Resolve signing key by kid from JWT header
            signing_key = client.get_signing_key_from_jwt(bearer)

            # Verify and decode
            claims = pyjwt.decode(
                bearer,
                signing_key.key,
                algorithms=["RS256"],
                issuer=self.issuer_url,
                audience=self.audience,
                options={"verify_exp": True},
            )

            return _map_claims_to_principal(claims)
        except Exception:
            return None


def _map_claims_to_principal(claims: dict[str, Any]) -> str | None:
    """Map OIDC JWT claims to an ANIP principal identifier.

    Deployment policy, not protocol meaning:
    - email → "human:{email}"
    - preferred_username → "human:{username}"
    - sub → "oidc:{sub}"
    """
    email = claims.get("email")
    if email:
        return f"human:{email}"

    username = claims.get("preferred_username")
    if username:
        return f"human:{username}"

    sub = claims.get("sub")
    if sub:
        return f"oidc:{sub}"

    return None
