"""Unit tests for JSON-RPC 2.0 protocol helpers."""
from anip_stdio.protocol import (
    AUTH_ERROR,
    FAILURE_TYPE_TO_CODE,
    INTERNAL_ERROR,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    NOT_FOUND,
    PARSE_ERROR,
    SCOPE_ERROR,
    VALID_METHODS,
    extract_auth,
    make_error,
    make_notification,
    make_response,
    validate_request,
)


# --- VALID_METHODS ---

class TestValidMethods:
    def test_method_count(self):
        assert len(VALID_METHODS) == 9

    def test_all_methods_present(self):
        expected = {
            "anip.discovery", "anip.manifest", "anip.jwks",
            "anip.tokens.issue", "anip.permissions", "anip.invoke",
            "anip.audit.query", "anip.checkpoints.list", "anip.checkpoints.get",
        }
        assert VALID_METHODS == expected


# --- Error code mapping ---

class TestErrorCodeMapping:
    def test_auth_errors(self):
        for t in ("authentication_required", "invalid_token", "token_expired"):
            assert FAILURE_TYPE_TO_CODE[t] == AUTH_ERROR

    def test_scope_errors(self):
        for t in ("scope_insufficient", "budget_exceeded", "purpose_mismatch"):
            assert FAILURE_TYPE_TO_CODE[t] == SCOPE_ERROR

    def test_not_found_errors(self):
        for t in ("unknown_capability", "not_found"):
            assert FAILURE_TYPE_TO_CODE[t] == NOT_FOUND

    def test_internal_errors(self):
        for t in ("internal_error", "unavailable", "concurrent_lock"):
            assert FAILURE_TYPE_TO_CODE[t] == INTERNAL_ERROR


# --- make_response ---

class TestMakeResponse:
    def test_basic(self):
        resp = make_response(1, {"key": "value"})
        assert resp == {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"key": "value"},
        }

    def test_null_id(self):
        resp = make_response(None, "ok")
        assert resp["id"] is None

    def test_string_id(self):
        resp = make_response("abc-123", [1, 2, 3])
        assert resp["id"] == "abc-123"
        assert resp["result"] == [1, 2, 3]


# --- make_error ---

class TestMakeError:
    def test_basic(self):
        resp = make_error(1, -32600, "Invalid request")
        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == 1
        assert resp["error"]["code"] == -32600
        assert resp["error"]["message"] == "Invalid request"
        assert "data" not in resp["error"]

    def test_with_data(self):
        resp = make_error(2, -32001, "Auth required", {"type": "authentication_required"})
        assert resp["error"]["data"]["type"] == "authentication_required"

    def test_null_id(self):
        resp = make_error(None, PARSE_ERROR, "Parse error")
        assert resp["id"] is None


# --- make_notification ---

class TestMakeNotification:
    def test_basic(self):
        notif = make_notification("anip.invoke.progress", {"invocation_id": "inv-1"})
        assert notif["jsonrpc"] == "2.0"
        assert notif["method"] == "anip.invoke.progress"
        assert notif["params"]["invocation_id"] == "inv-1"
        assert "id" not in notif


# --- validate_request ---

class TestValidateRequest:
    def test_valid_request(self):
        msg = {"jsonrpc": "2.0", "id": 1, "method": "anip.discovery"}
        assert validate_request(msg) is None

    def test_missing_jsonrpc(self):
        msg = {"id": 1, "method": "anip.discovery"}
        assert validate_request(msg) is not None

    def test_wrong_jsonrpc(self):
        msg = {"jsonrpc": "1.0", "id": 1, "method": "anip.discovery"}
        assert validate_request(msg) is not None

    def test_missing_method(self):
        msg = {"jsonrpc": "2.0", "id": 1}
        assert validate_request(msg) is not None

    def test_non_string_method(self):
        msg = {"jsonrpc": "2.0", "id": 1, "method": 42}
        assert validate_request(msg) is not None

    def test_missing_id(self):
        msg = {"jsonrpc": "2.0", "method": "anip.discovery"}
        assert validate_request(msg) is not None

    def test_not_a_dict(self):
        assert validate_request("not a dict") is not None  # type: ignore[arg-type]


# --- extract_auth ---

class TestExtractAuth:
    def test_extracts_bearer(self):
        params = {"auth": {"bearer": "my-token"}}
        assert extract_auth(params) == "my-token"

    def test_no_params(self):
        assert extract_auth(None) is None

    def test_no_auth(self):
        assert extract_auth({"capability": "echo"}) is None

    def test_auth_not_dict(self):
        assert extract_auth({"auth": "string"}) is None

    def test_no_bearer(self):
        assert extract_auth({"auth": {"type": "basic"}}) is None

    def test_empty_params(self):
        assert extract_auth({}) is None
