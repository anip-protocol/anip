"""Superset REST backend seam for the governed fronting showcase."""
from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

BackendInvocationPlan = dict[str, Any]
GeneratedCapability = dict[str, Any]


def _base_url() -> str:
    return os.getenv("SUPERSET_BASE_URL", "http://127.0.0.1:8088").rstrip("/")


def _csv_env(name: str) -> set[str]:
    return {item.strip().lower() for item in os.getenv(name, "").split(",") if item.strip()}


def _scope_allowed(scope: str) -> bool:
    key = scope.strip().lower()
    blocked = _csv_env("ANIP_SUPERSET_BLOCKED_WORKSPACES")
    allowed = _csv_env("ANIP_SUPERSET_ALLOWED_WORKSPACES")
    if key in blocked:
        return False
    return not allowed or key in allowed


def _dataset_allowed(dataset_ref: str) -> bool:
    allowed = _csv_env("ANIP_SUPERSET_ALLOWED_DATASETS")
    return not allowed or dataset_ref.strip().lower() in allowed


def _bounded_limit(value: Any, *, default: int = 20, maximum: int = 100) -> int:
    try:
        limit = int(value)
    except (TypeError, ValueError):
        limit = default
    return max(1, min(limit, maximum))


def _approval_grant_from_context(ctx: Any) -> dict[str, Any] | None:
    grant = getattr(ctx, "approval_grant", None)
    if isinstance(grant, dict) and grant.get("grant_id") and grant.get("approval_request_id"):
        return grant
    return None


def _mutation_enabled(ctx: Any) -> bool:
    return os.getenv("ANIP_SUPERSET_ALLOW_MUTATION", "").lower() == "true" and _approval_grant_from_context(ctx) is not None


def _access_token() -> str | None:
    direct = os.getenv("SUPERSET_ACCESS_TOKEN", "").strip()
    if direct:
        return direct
    username = os.getenv("SUPERSET_USERNAME", "").strip()
    password = os.getenv("SUPERSET_PASSWORD", "").strip()
    if not username or not password:
        return None
    response = _request_json(
        "POST",
        "/api/v1/security/login",
        None,
        {
            "username": username,
            "password": password,
            "provider": os.getenv("SUPERSET_AUTH_PROVIDER", "db"),
            "refresh": True,
        },
    )
    if isinstance(response, dict) and response.get("access_token"):
        return str(response["access_token"])
    return None


def _request_json(method: str, path: str, token: str | None, body: dict[str, Any] | None = None) -> Any:
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "anip-superset-fronting-showcase",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        f"{_base_url()}{path}",
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        return {
            "error": "superset_http_error",
            "status": exc.code,
            "detail": exc.read().decode("utf-8", errors="replace"),
        }
    except urllib.error.URLError as exc:
        return {"error": "superset_connection_error", "detail": str(exc)}
    except (ConnectionError, OSError, TimeoutError, socket.timeout) as exc:
        return {"error": "superset_connection_error", "detail": str(exc)}


def _metadata(capability: GeneratedCapability, plan: BackendInvocationPlan) -> dict[str, Any]:
    return {
        "capability_id": capability["capability_id"],
        "selected_backend": plan["selected_binding"],
        "semantic_input": plan["semantic_input"],
    }


def _restricted_response(capability: GeneratedCapability, plan: BackendInvocationPlan, reason: str) -> dict[str, Any]:
    return {"execution_status": "restricted", **_metadata(capability, plan), "reason": reason}


def _backend_error(capability: GeneratedCapability, plan: BackendInvocationPlan, error: Any) -> dict[str, Any]:
    return {"execution_status": "backend_error", **_metadata(capability, plan), "superset_error": error}


def _list_result(response: Any) -> list[dict[str, Any]]:
    if not isinstance(response, dict):
        return []
    raw = response.get("result")
    if isinstance(raw, dict):
        if isinstance(raw.get("data"), list):
            return raw["data"]
        if isinstance(raw.get("result"), list):
            return raw["result"]
    if isinstance(raw, list):
        return raw
    return []


class DefaultBackendAdapter:
    async def execute(
        self,
        capability: GeneratedCapability,
        plan: BackendInvocationPlan,
        _params: dict[str, Any],
        ctx: Any = None,
    ) -> dict[str, Any]:
        if plan["unresolved_required_backend_inputs"]:
            return {
                "execution_status": "backend_input_incomplete",
                **_metadata(capability, plan),
                "backend_input_contract": plan["backend_input_contract"],
                "unresolved_required_backend_inputs": plan["unresolved_required_backend_inputs"],
            }
        token = _access_token()
        if token is None:
            return {"execution_status": "backend_error", **_metadata(capability, plan), "superset_error": {"error": "missing_superset_credentials"}}
        capability_id = capability["capability_id"]
        if capability_id == "superset.analytics.discover_context":
            return self._discover_context(capability, plan, _params, token)
        if capability_id == "superset.analytics.answer_question":
            return self._answer_question(capability, plan, _params, token)
        if capability_id == "superset.chart.preview.create":
            return self._chart_preview(capability, plan, _params, token)
        if capability_id == "superset.chart.publish.request":
            return self._chart_publish_request(capability, plan, _params, ctx)
        if capability_id == "superset.dashboard.draft.prepare":
            return self._dashboard_draft(capability, plan, _params)
        if capability_id == "superset.dataset.draft.prepare":
            return self._dataset_draft(capability, plan, _params, ctx)
        return {"execution_status": "backend_execution_stub", **_metadata(capability, plan)}

    def _discover_context(self, capability: GeneratedCapability, plan: BackendInvocationPlan, params: dict[str, Any], token: str) -> dict[str, Any]:
        workspace_scope = str(params.get("workspace_scope") or "").strip()
        if not _scope_allowed(workspace_scope):
            return _restricted_response(capability, plan, "Workspace scope is outside the configured ANIP policy.")
        query = str(params.get("query") or "").strip()
        limit = _bounded_limit(params.get("limit"), maximum=50)
        asset_type = str(params.get("asset_type") or "").strip()
        endpoints = [("dataset", "/api/v1/dataset/"), ("chart", "/api/v1/chart/"), ("dashboard", "/api/v1/dashboard/")]
        if asset_type:
            endpoints = [entry for entry in endpoints if entry[0] == asset_type]
        items: list[dict[str, Any]] = []
        for kind, endpoint in endpoints:
            response = _request_json("GET", f"{endpoint}?page_size={limit}", token)
            if isinstance(response, dict) and response.get("error"):
                return _backend_error(capability, plan, response)
            for item in _list_result(response):
                title = str(item.get("table_name") or item.get("slice_name") or item.get("dashboard_title") or item.get("name") or item.get("id"))
                if query.lower() and query.lower() not in title.lower():
                    continue
                items.append({"asset_type": kind, "id": item.get("id"), "title": title, "url": item.get("url")})
                if len(items) >= limit:
                    break
            if len(items) >= limit:
                break
        return {"execution_status": "completed", **_metadata(capability, plan), "result": {"workspace_scope": workspace_scope, "items": items, "count": len(items)}}

    def _answer_question(self, capability: GeneratedCapability, plan: BackendInvocationPlan, params: dict[str, Any], token: str) -> dict[str, Any]:
        dataset_ref = str(params.get("dataset_ref") or "").strip()
        if not _dataset_allowed(dataset_ref):
            return _restricted_response(capability, plan, "Dataset is outside the configured ANIP policy.")
        return {
            "execution_status": "completed",
            **_metadata(capability, plan),
            "mutation_performed": False,
            "result": {
                "question": params.get("question"),
                "dataset_ref": dataset_ref,
                "metric": params.get("metric"),
                "dimension": params.get("dimension"),
                "time_window": params.get("time_window"),
                "answer": "Governed analytics answer placeholder. The service owns SQL generation and execution policy.",
                "raw_sql_disclosed": False,
            },
        }

    def _chart_preview(self, capability: GeneratedCapability, plan: BackendInvocationPlan, params: dict[str, Any], token: str) -> dict[str, Any]:
        dataset_ref = str(params.get("dataset_ref") or "").strip()
        if not _dataset_allowed(dataset_ref):
            return _restricted_response(capability, plan, "Dataset is outside the configured ANIP policy.")
        body = {
            "dataset_ref": dataset_ref,
            "metric": params.get("metric"),
            "dimension": params.get("dimension"),
            "visualization_type": params.get("visualization_type"),
            "title": params.get("title") or f"{params.get('metric')} by {params.get('dimension') or 'time'}",
            "save_chart": False,
        }
        return self._write_preview(capability, plan, "chart.preview", body, {"dataset_ref": dataset_ref})

    def _chart_publish_request(self, capability: GeneratedCapability, plan: BackendInvocationPlan, params: dict[str, Any], ctx: Any) -> dict[str, Any]:
        body = {
            "chart_preview_ref": params.get("chart_preview_ref"),
            "dashboard_scope": params.get("dashboard_scope"),
            "reason": params.get("reason"),
            "title": params.get("title"),
        }
        preview = self._write_preview(capability, plan, "chart.publish", body, {"dashboard_scope": params.get("dashboard_scope")})
        if not _mutation_enabled(ctx):
            return preview
        return {**preview, "execution_status": "completed", "approval_required": False, "mutation_performed": False, "note": "Approved publish request recorded. Concrete chart save is intentionally left to deployment-specific Superset adapter code."}

    def _dashboard_draft(self, capability: GeneratedCapability, plan: BackendInvocationPlan, params: dict[str, Any]) -> dict[str, Any]:
        body = {
            "dashboard_scope": params.get("dashboard_scope"),
            "objective": params.get("objective"),
            "chart_refs": params.get("chart_refs") or [],
            "layout_hint": params.get("layout_hint"),
            "audience": params.get("audience"),
        }
        return self._write_preview(capability, plan, "dashboard.draft", body, {"dashboard_scope": params.get("dashboard_scope")})

    def _dataset_draft(self, capability: GeneratedCapability, plan: BackendInvocationPlan, params: dict[str, Any], ctx: Any) -> dict[str, Any]:
        body = {
            "database_ref": params.get("database_ref"),
            "dataset_purpose": params.get("dataset_purpose"),
            "query_intent": params.get("query_intent"),
            "source_tables": params.get("source_tables") or [],
            "metrics": params.get("metrics") or [],
            "raw_sql_accepted": False,
        }
        preview = self._write_preview(capability, plan, "dataset.draft", body, {"database_ref": params.get("database_ref")})
        if not _mutation_enabled(ctx):
            return preview
        return {**preview, "execution_status": "completed", "approval_required": False, "mutation_performed": False, "note": "Approved dataset draft recorded. Raw SQL generation remains deployment-owned."}

    def _write_preview(self, capability: GeneratedCapability, plan: BackendInvocationPlan, action: str, body: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
        return {
            "execution_status": "prepared",
            **_metadata(capability, plan),
            "approval_required": True,
            "mutation_performed": False,
            "superset_action": action,
            "superset_metadata": metadata,
            "superset_request": {"operation": action, "body": body},
            "note": "Prepared a governed Superset analytics request. No Superset mutation was performed.",
        }


backend_adapter = DefaultBackendAdapter()
