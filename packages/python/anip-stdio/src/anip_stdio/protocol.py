"""JSON-RPC 2.0 protocol helpers for ANIP stdio transport."""
from __future__ import annotations

from typing import Any

# --- Valid ANIP methods ---

VALID_METHODS: frozenset[str] = frozenset({
    "anip.discovery",
    "anip.manifest",
    "anip.jwks",
    "anip.tokens.issue",
    "anip.permissions",
    "anip.invoke",
    "anip.audit.query",
    "anip.checkpoints.list",
    "anip.checkpoints.get",
})

# --- JSON-RPC 2.0 error codes ---

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
AUTH_ERROR = -32001
SCOPE_ERROR = -32002
NOT_FOUND = -32004
INTERNAL_ERROR = -32603

# --- ANIP failure type to JSON-RPC error code mapping ---

FAILURE_TYPE_TO_CODE: dict[str, int] = {
    "authentication_required": AUTH_ERROR,
    "invalid_token": AUTH_ERROR,
    "token_expired": AUTH_ERROR,
    "scope_insufficient": SCOPE_ERROR,
    "budget_exceeded": SCOPE_ERROR,
    "purpose_mismatch": SCOPE_ERROR,
    "unknown_capability": NOT_FOUND,
    "not_found": NOT_FOUND,
    "internal_error": INTERNAL_ERROR,
    "unavailable": INTERNAL_ERROR,
    "concurrent_lock": INTERNAL_ERROR,
}


# --- Message constructors ---


def make_response(request_id: int | str | None, result: Any) -> dict[str, Any]:
    """Build a JSON-RPC 2.0 success response."""
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def make_error(
    request_id: int | str | None,
    code: int,
    message: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a JSON-RPC 2.0 error response."""
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


def make_notification(method: str, params: dict[str, Any]) -> dict[str, Any]:
    """Build a JSON-RPC 2.0 notification (no id)."""
    return {"jsonrpc": "2.0", "method": method, "params": params}


# --- Request validation ---


def validate_request(msg: dict[str, Any]) -> str | None:
    """Validate a JSON-RPC 2.0 request.

    Returns None if valid, or an error description string if invalid.
    """
    if not isinstance(msg, dict):
        return "Request must be a JSON object"
    if msg.get("jsonrpc") != "2.0":
        return "Missing or invalid 'jsonrpc' field (must be '2.0')"
    if "method" not in msg:
        return "Missing 'method' field"
    if not isinstance(msg["method"], str):
        return "'method' must be a string"
    if "id" not in msg:
        return "Missing 'id' field (notifications not supported as requests)"
    return None


# --- Auth extraction ---


def extract_auth(params: dict[str, Any] | None) -> str | None:
    """Extract bearer token from params.auth.bearer.

    Returns the bearer string, or None if not present.
    """
    if params is None:
        return None
    auth = params.get("auth")
    if auth is None:
        return None
    if not isinstance(auth, dict):
        return None
    return auth.get("bearer")
