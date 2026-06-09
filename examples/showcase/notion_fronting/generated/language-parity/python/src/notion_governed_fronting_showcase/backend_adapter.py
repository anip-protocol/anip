"""Notion API backend seam for the governed fronting showcase."""
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


def _notion_token() -> str | None:
    return os.getenv("NOTION_TOKEN", "").strip() or None


def _api_base() -> str:
    return os.getenv("NOTION_API_BASE", "https://api.notion.com/v1").rstrip("/")


def _notion_version() -> str:
    return os.getenv("NOTION_VERSION", "2026-03-11")


def _csv_env(name: str) -> set[str]:
    return {item.strip().lower() for item in os.getenv(name, "").split(",") if item.strip()}


def _scope_allowed(scope: str) -> bool:
    key = scope.strip().lower()
    blocked = _csv_env("ANIP_NOTION_BLOCKED_WORKSPACES")
    allowed = _csv_env("ANIP_NOTION_ALLOWED_WORKSPACES")
    if key in blocked:
        return False
    return not allowed or key in allowed


def _id_allowed(value: str, env_name: str) -> bool:
    allowed = _csv_env(env_name)
    return not allowed or value.strip().lower() in allowed


def _configured_data_source_id() -> str:
    return (
        os.getenv("NOTION_DATA_SOURCE_ID", "").strip()
        or os.getenv("ANIP_NOTION_DATA_SOURCE_ID", "").strip()
    )


def _bounded_limit(value: Any, *, default: int = 20, maximum: int = 50) -> int:
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
    return os.getenv("ANIP_NOTION_ALLOW_MUTATION", "").lower() == "true" and _approval_grant_from_context(ctx) is not None


def _notion_request_json(method: str, path: str, token: str, body: dict[str, Any] | None = None) -> Any:
    request = urllib.request.Request(
        f"{_api_base()}{path}",
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "Notion-Version": _notion_version(),
            "User-Agent": "anip-notion-fronting-showcase",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        return {
            "error": "notion_http_error",
            "status": exc.code,
            "detail": exc.read().decode("utf-8", errors="replace"),
        }
    except (urllib.error.URLError, ConnectionError, OSError, TimeoutError, socket.timeout) as exc:
        return {
            "error": "notion_connection_error",
            "detail": str(exc),
        }


def _metadata(capability: GeneratedCapability, plan: BackendInvocationPlan) -> dict[str, Any]:
    return {
        "capability_id": capability["capability_id"],
        "selected_backend": plan["selected_binding"],
        "semantic_input": plan["semantic_input"],
    }


def _restricted_response(capability: GeneratedCapability, plan: BackendInvocationPlan, reason: str) -> dict[str, Any]:
    return {"execution_status": "restricted", **_metadata(capability, plan), "reason": reason}


def _rich_text(text: str) -> list[dict[str, Any]]:
    return [{"type": "text", "text": {"content": text[:1900]}}]


def _title_from_page(page: dict[str, Any]) -> str:
    properties = page.get("properties") or {}
    for value in properties.values():
        if value.get("type") == "title":
            title = value.get("title") or []
            return "".join(part.get("plain_text") or "" for part in title).strip()
    return ""


def _summarize_object(item: dict[str, Any]) -> dict[str, Any]:
    object_type = item.get("object")
    title = _title_from_page(item) if object_type == "page" else item.get("title") or []
    if isinstance(title, list):
        title = "".join(part.get("plain_text") or "" for part in title)
    return {
        "id": item.get("id"),
        "object": object_type,
        "title": title or item.get("url") or item.get("id"),
        "url": item.get("url"),
        "created_time": item.get("created_time"),
        "last_edited_time": item.get("last_edited_time"),
    }


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
        token = _notion_token()
        if token is None:
            return {"execution_status": "backend_error", **_metadata(capability, plan), "notion_error": {"error": "missing_notion_token"}}
        capability_id = capability["capability_id"]
        if capability_id == "notion.workspace.search_context":
            return self._search_workspace(capability, plan, _params, token)
        if capability_id == "notion.database.query_context":
            return self._query_database(capability, plan, _params, token)
        if capability_id == "notion.page.create.prepare":
            return self._prepare_or_create_page(capability, plan, _params, token, ctx)
        if capability_id == "notion.page.update.prepare":
            return self._prepare_page_update(capability, plan, _params, token, ctx)
        if capability_id == "notion.comment.prepare":
            return self._prepare_or_post_comment(capability, plan, _params, token, ctx)
        return {"execution_status": "backend_execution_stub", **_metadata(capability, plan)}

    def _search_workspace(self, capability: GeneratedCapability, plan: BackendInvocationPlan, params: dict[str, Any], token: str) -> dict[str, Any]:
        workspace_scope = str(params.get("workspace_scope") or "").strip()
        if not _scope_allowed(workspace_scope):
            return _restricted_response(capability, plan, "Workspace scope is outside the configured ANIP policy.")
        limit = _bounded_limit(params.get("limit"))
        response = _notion_request_json(
            "POST",
            "/search",
            token,
            {"query": str(params.get("query") or "").strip(), "page_size": limit},
        )
        if isinstance(response, dict) and response.get("error"):
            return {"execution_status": "backend_error", **_metadata(capability, plan), "notion_error": response}
        results = [_summarize_object(item) for item in (response.get("results") or [])[:limit]]
        return {
            "execution_status": "completed",
            **_metadata(capability, plan),
            "notion_query": params.get("query"),
            "result": {"workspace_scope": workspace_scope, "items": results, "count": len(results)},
        }

    def _query_database(self, capability: GeneratedCapability, plan: BackendInvocationPlan, params: dict[str, Any], token: str) -> dict[str, Any]:
        database_id = str(params.get("database_id") or "").strip()
        if not _id_allowed(database_id, "ANIP_NOTION_ALLOWED_DATABASES"):
            return _restricted_response(capability, plan, "Database is outside the configured ANIP policy.")
        limit = _bounded_limit(params.get("limit"))
        data_source_id = _configured_data_source_id()
        if data_source_id:
            if not _id_allowed(data_source_id, "ANIP_NOTION_ALLOWED_DATA_SOURCES"):
                return _restricted_response(capability, plan, "Data source is outside the configured ANIP policy.")
        else:
            database = _notion_request_json("GET", f"/databases/{urllib.parse.quote(database_id)}", token)
            if isinstance(database, dict) and database.get("error"):
                return {"execution_status": "backend_error", **_metadata(capability, plan), "notion_error": database}
            data_sources = database.get("data_sources") or []
            if data_sources:
                data_source_id = str(data_sources[0].get("id") or "").strip()
        if data_source_id:
            response = _notion_request_json("POST", f"/data_sources/{urllib.parse.quote(data_source_id)}/query", token, {"page_size": limit})
        else:
            response = _notion_request_json("POST", f"/databases/{urllib.parse.quote(database_id)}/query", token, {"page_size": limit})
        if isinstance(response, dict) and response.get("error"):
            return {"execution_status": "backend_error", **_metadata(capability, plan), "notion_error": response}
        results = [_summarize_object(item) for item in (response.get("results") or [])[:limit]]
        return {"execution_status": "completed", **_metadata(capability, plan), "result": {"database_id": database_id, "data_source_id": data_source_id, "items": results, "count": len(results)}}

    def _prepare_or_create_page(self, capability: GeneratedCapability, plan: BackendInvocationPlan, params: dict[str, Any], token: str, ctx: Any) -> dict[str, Any]:
        parent_id = str(params.get("parent_id") or "").strip()
        if not _id_allowed(parent_id, "ANIP_NOTION_ALLOWED_PARENTS"):
            return _restricted_response(capability, plan, "Parent page/database is outside the configured ANIP policy.")
        title = str(params.get("title") or "").strip()
        content_summary = str(params.get("content_summary") or "").strip()
        body = {
            "parent": {"page_id": parent_id},
            "properties": {"title": {"title": _rich_text(title)}},
            "children": [{"object": "block", "type": "paragraph", "paragraph": {"rich_text": _rich_text(content_summary)}}],
        }
        preview = self._write_preview(capability, plan, "pages.create", body, {"parent_id": parent_id})
        if not _mutation_enabled(ctx):
            return preview
        created = _notion_request_json("POST", "/pages", token, body)
        if isinstance(created, dict) and created.get("error"):
            return {**preview, "execution_status": "backend_error", "notion_error": created}
        return {
            **preview,
            "execution_status": "completed",
            "approval_required": False,
            "mutation_performed": True,
            "created_page": _summarize_object(created),
        }

    def _prepare_page_update(self, capability: GeneratedCapability, plan: BackendInvocationPlan, params: dict[str, Any], token: str, ctx: Any) -> dict[str, Any]:
        page_id = str(params.get("page_id") or "").strip()
        if not _id_allowed(page_id, "ANIP_NOTION_ALLOWED_PAGES"):
            return _restricted_response(capability, plan, "Page is outside the configured ANIP policy.")
        body = {
            "archived": False,
            "change_summary": str(params.get("change_summary") or "").strip(),
            "content_patch": str(params.get("content_patch") or "").strip(),
        }
        return self._write_preview(capability, plan, "pages.update.preview", body, {"page_id": page_id})

    def _prepare_or_post_comment(self, capability: GeneratedCapability, plan: BackendInvocationPlan, params: dict[str, Any], token: str, ctx: Any) -> dict[str, Any]:
        page_id = str(params.get("page_id") or "").strip()
        if not _id_allowed(page_id, "ANIP_NOTION_ALLOWED_PAGES"):
            return _restricted_response(capability, plan, "Page is outside the configured ANIP policy.")
        body = {
            "parent": {"page_id": page_id},
            "rich_text": _rich_text(f"[{params.get('comment_purpose')}] {params.get('context')}".strip()),
        }
        preview = self._write_preview(capability, plan, "comments.create", body, {"page_id": page_id})
        if not _mutation_enabled(ctx):
            return preview
        created = _notion_request_json("POST", "/comments", token, body)
        if isinstance(created, dict) and created.get("error"):
            return {**preview, "execution_status": "backend_error", "notion_error": created}
        return {**preview, "execution_status": "completed", "approval_required": False, "mutation_performed": True, "created_comment": created}

    def _write_preview(self, capability: GeneratedCapability, plan: BackendInvocationPlan, action: str, body: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
        return {
            "execution_status": "prepared",
            **_metadata(capability, plan),
            "approval_required": True,
            "mutation_performed": False,
            "notion_action": action,
            "notion_metadata": metadata,
            "notion_request": {"operation": action, "body": body},
            "note": "Prepared a Notion API payload. No Notion mutation was performed.",
        }


backend_adapter = DefaultBackendAdapter()
