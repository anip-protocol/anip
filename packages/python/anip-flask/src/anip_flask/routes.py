"""Mount ANIP routes onto a Flask application."""
from __future__ import annotations

from flask import Flask, Blueprint, Request, request, jsonify, Response

from anip_service import ANIPService, ANIPError


class ANIPHandle:
    """Lifecycle handle returned by mount_anip."""

    def __init__(self, service: ANIPService) -> None:
        self._service = service

    def stop(self) -> None:
        self._service.stop()


def mount_anip(
    app: Flask,
    service: ANIPService,
    prefix: str = "",
) -> ANIPHandle:
    """Mount all ANIP protocol routes onto a Flask app.

    Routes:
        GET  {prefix}/.well-known/anip          → discovery
        GET  {prefix}/.well-known/jwks.json     → JWKS
        GET  {prefix}/anip/manifest             → full manifest (signed)
        POST {prefix}/anip/tokens               → issue token
        POST {prefix}/anip/permissions           → discover permissions
        POST {prefix}/anip/invoke/<capability>   → invoke capability
        POST {prefix}/anip/audit                → query audit log
        GET  {prefix}/anip/checkpoints          → list checkpoints
        GET  {prefix}/anip/checkpoints/<id>     → get checkpoint
    """
    bp = Blueprint(f"anip_{id(service)}", __name__)

    # --- Discovery & Identity ---

    @bp.route("/.well-known/anip")
    def discovery():
        return jsonify(service.get_discovery())

    @bp.route("/.well-known/jwks.json")
    def jwks():
        return jsonify(service.get_jwks())

    @bp.route("/anip/manifest")
    def manifest():
        body_bytes, signature = service.get_signed_manifest()
        return Response(
            body_bytes,
            content_type="application/json",
            headers={"X-ANIP-Signature": signature},
        )

    # --- Tokens ---

    @bp.route("/anip/tokens", methods=["POST"])
    def issue_token():
        principal = _extract_principal(request, service)
        if principal is None:
            return jsonify({"error": "Authentication required"}), 401

        body = request.get_json(force=True)
        try:
            result = service.issue_token(principal, body)
            return jsonify(result)
        except ANIPError as e:
            return _error_response(e)

    # --- Permissions ---

    @bp.route("/anip/permissions", methods=["POST"])
    def permissions():
        token = _resolve_token(request, service)
        if token is None:
            return jsonify({"error": "Authentication required"}), 401
        return jsonify(service.discover_permissions(token))

    # --- Invoke ---

    @bp.route("/anip/invoke/<capability>", methods=["POST"])
    def invoke(capability: str):
        token = _resolve_token(request, service)
        if token is None:
            return jsonify({"error": "Authentication required"}), 401

        body = request.get_json(force=True)
        params = body.get("parameters", body)
        client_reference_id = body.get("client_reference_id")
        result = service.invoke(
            capability, token, params,
            client_reference_id=client_reference_id,
        )

        if not result.get("success"):
            status = _failure_status(result.get("failure", {}).get("type"))
            return jsonify(result), status

        return jsonify(result)

    # --- Audit ---

    @bp.route("/anip/audit", methods=["POST"])
    def audit():
        token = _resolve_token(request, service)
        if token is None:
            return jsonify({"error": "Authentication required"}), 401

        filters = {
            "capability": request.args.get("capability"),
            "since": request.args.get("since"),
            "limit": int(request.args.get("limit", "50")),
        }
        return jsonify(service.query_audit(token, filters))

    # --- Checkpoints ---

    @bp.route("/anip/checkpoints")
    def list_checkpoints():
        limit = int(request.args.get("limit", "10"))
        return jsonify(service.get_checkpoints(limit))

    @bp.route("/anip/checkpoints/<checkpoint_id>")
    def get_checkpoint(checkpoint_id: str):
        options = {
            "include_proof": request.args.get("include_proof") == "true",
            "leaf_index": request.args.get("leaf_index"),
            "consistency_from": request.args.get("consistency_from"),
        }
        result = service.get_checkpoint(checkpoint_id, options)
        if result is None:
            return jsonify({"error": "Checkpoint not found"}), 404
        return jsonify(result)

    app.register_blueprint(bp, url_prefix=prefix or None)
    service.start()
    return ANIPHandle(service)


def _extract_principal(req: Request, service: ANIPService) -> str | None:
    auth = req.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    bearer_value = auth[7:].strip()
    return service.authenticate_bearer(bearer_value)


def _resolve_token(req: Request, service: ANIPService):
    auth = req.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    jwt_str = auth[7:].strip()
    try:
        return service.resolve_bearer_token(jwt_str)
    except ANIPError:
        return None


def _failure_status(failure_type: str | None) -> int:
    mapping = {
        "invalid_token": 401,
        "token_expired": 401,
        "scope_insufficient": 403,
        "insufficient_authority": 403,
        "purpose_mismatch": 403,
        "unknown_capability": 404,
        "not_found": 404,
        "unavailable": 409,
        "concurrent_lock": 409,
        "internal_error": 500,
    }
    return mapping.get(failure_type or "", 400)


def _error_response(error: ANIPError):
    status = _failure_status(error.error_type)
    return jsonify(
        {"success": False, "failure": {"type": error.error_type, "detail": error.detail}}
    ), status
