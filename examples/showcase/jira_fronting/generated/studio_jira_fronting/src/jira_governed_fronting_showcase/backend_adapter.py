"""Backend execution seam for generated capabilities."""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

BackendInvocationPlan = dict[str, Any]
GeneratedCapability = dict[str, Any]


def _jira_env() -> tuple[str, str, str] | None:
    base_url = os.getenv("JIRA_BASE_URL", "").rstrip("/")
    email = os.getenv("JIRA_EMAIL", "")
    token = os.getenv("JIRA_API_TOKEN", "")
    if not base_url or not email or not token:
        return None
    return base_url, email, token


def _bounded_limit(value: Any) -> int:
    try:
        limit = int(value)
    except (TypeError, ValueError):
        limit = 25
    return max(1, min(limit, 50))


def _jql_string(value: Any) -> str:
    text = str(value or "").strip()
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _jira_get_json(base_url: str, email: str, token: str, path: str, query: dict[str, str]) -> dict[str, Any]:
    credentials = base64.b64encode(f"{email}:{token}".encode("utf-8")).decode("ascii")
    url = f"{base_url}{path}?{urllib.parse.urlencode(query)}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Basic {credentials}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return {
            "error": "jira_http_error",
            "status": exc.code,
            "detail": detail,
        }


def _jira_post_json(base_url: str, email: str, token: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
    credentials = base64.b64encode(f"{email}:{token}".encode("utf-8")).decode("ascii")
    request = urllib.request.Request(
        f"{base_url}{path}",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return {
            "error": "jira_http_error",
            "status": exc.code,
            "detail": detail,
        }


def _adf_doc(text: Any) -> dict[str, Any]:
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": str(text or "").strip()}],
            }
        ],
    }


def _labels(value: Any) -> list[str]:
    if isinstance(value, list):
        raw = value
    elif isinstance(value, str) and value.strip():
        raw = [item.strip() for item in value.split(",")]
    else:
        raw = []
    labels: list[str] = []
    for item in raw:
        label = str(item).strip().replace(" ", "-")
        if label and label not in labels:
            labels.append(label[:255])
    return labels


def _priority_for_severity(severity: Any) -> str:
    value = str(severity or "").lower()
    if value in {"sev1", "sev2"}:
        return "High"
    if value == "sev4":
        return "Low"
    return "Medium"


def _approval_grant_from_context(ctx: Any) -> dict[str, Any] | None:
    grant = getattr(ctx, "approval_grant", None)
    if isinstance(grant, dict) and grant.get("grant_id") and grant.get("approval_request_id"):
        return grant
    return None


def _mutation_enabled(ctx: Any) -> bool:
    if os.getenv("ANIP_JIRA_ALLOW_MUTATION", "").lower() != "true":
        return False
    return _approval_grant_from_context(ctx) is not None


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
                "capability_id": capability["capability_id"],
                "backend_input_contract": plan["backend_input_contract"],
                "unresolved_required_backend_inputs": plan["unresolved_required_backend_inputs"],
                "note": "Generated host is runnable, but backend-only inputs still require extension completion.",
            }
        if capability["capability_id"] == "jira.backlog.search":
            configured = _jira_env()
            if configured is not None:
                return self._search_jira_backlog(capability, plan, _params, configured)
        if capability["capability_id"] == "jira.bug.prepare":
            configured = _jira_env()
            if configured is not None:
                return self._prepare_jira_bug(capability, plan, _params, configured, ctx)
        return {
            "execution_status": "backend_execution_stub",
            "capability_id": capability["capability_id"],
            "selected_backend": plan["selected_binding"],
            "semantic_input": plan["semantic_input"],
            "backend_input_contract": plan["backend_input_contract"],
            "note": "Replace DefaultBackendAdapter.execute() with provider-specific backend execution.",
        }

    def _search_jira_backlog(
        self,
        capability: GeneratedCapability,
        plan: BackendInvocationPlan,
        params: dict[str, Any],
        configured: tuple[str, str, str],
    ) -> dict[str, Any]:
        base_url, email, token = configured
        project_key = _jql_string(params.get("project_key"))
        query_text = _jql_string(params.get("query"))
        limit = _bounded_limit(params.get("limit"))
        jql = f'project = "{project_key}"'
        if query_text:
            jql += f' AND text ~ "{query_text}"'
        jql += " ORDER BY created DESC"
        payload = _jira_get_json(
            base_url,
            email,
            token,
            "/rest/api/3/search/jql",
            {
                "jql": jql,
                "maxResults": str(limit),
                "fields": "summary,status,issuetype,project",
            },
        )
        if payload.get("error"):
            return {
                "execution_status": "backend_error",
                "capability_id": capability["capability_id"],
                "selected_backend": plan["selected_binding"],
                "semantic_input": plan["semantic_input"],
                "jira_error": payload,
            }
        issues = [
            {
                "key": issue.get("key"),
                "summary": (issue.get("fields") or {}).get("summary"),
                "status": ((issue.get("fields") or {}).get("status") or {}).get("name"),
                "issue_type": ((issue.get("fields") or {}).get("issuetype") or {}).get("name"),
                "project_key": (((issue.get("fields") or {}).get("project") or {}).get("key")),
            }
            for issue in payload.get("issues", [])
        ]
        return {
            "execution_status": "completed",
            "capability_id": capability["capability_id"],
            "selected_backend": plan["selected_binding"],
            "semantic_input": plan["semantic_input"],
            "jql": jql,
            "result": {
                "issues": issues,
                "count": len(issues),
                "is_last": payload.get("isLast"),
            },
        }

    def _prepare_jira_bug(
        self,
        capability: GeneratedCapability,
        plan: BackendInvocationPlan,
        params: dict[str, Any],
        configured: tuple[str, str, str],
        ctx: Any,
    ) -> dict[str, Any]:
        base_url, email, token = configured
        project_key = str(params.get("project_key") or "").strip()
        issue_types = _jira_get_json(
            base_url,
            email,
            token,
            f"/rest/api/3/issue/createmeta/{urllib.parse.quote(project_key)}/issuetypes",
            {},
        )
        if issue_types.get("error"):
            return {
                "execution_status": "backend_error",
                "capability_id": capability["capability_id"],
                "selected_backend": plan["selected_binding"],
                "semantic_input": plan["semantic_input"],
                "jira_error": issue_types,
            }
        available = issue_types.get("issueTypes") or []
        selected = next((item for item in available if item.get("name") == "Bug"), None)
        if selected is None:
            selected = next((item for item in available if not item.get("subtask")), None)
        if selected is None:
            return {
                "execution_status": "backend_error",
                "capability_id": capability["capability_id"],
                "selected_backend": plan["selected_binding"],
                "semantic_input": plan["semantic_input"],
                "jira_error": {"error": "no_supported_issue_type", "project_key": project_key},
            }
        fields_meta = _jira_get_json(
            base_url,
            email,
            token,
            f"/rest/api/3/issue/createmeta/{urllib.parse.quote(project_key)}/issuetypes/{selected['id']}",
            {},
        )
        if fields_meta.get("error"):
            return {
                "execution_status": "backend_error",
                "capability_id": capability["capability_id"],
                "selected_backend": plan["selected_binding"],
                "semantic_input": plan["semantic_input"],
                "jira_error": fields_meta,
            }
        available_fields = {field.get("key") for field in fields_meta.get("fields", [])}
        labels = _labels(params.get("labels"))
        fields: dict[str, Any] = {
            "project": {"key": project_key},
            "issuetype": {"id": selected["id"]},
            "summary": str(params.get("summary") or "").strip(),
        }
        if "description" in available_fields:
            fields["description"] = _adf_doc(params.get("description"))
        if labels and "labels" in available_fields:
            fields["labels"] = labels
        if "priority" in available_fields:
            fields["priority"] = {"name": _priority_for_severity(params.get("severity"))}
        preview = {
            "execution_status": "prepared",
            "capability_id": capability["capability_id"],
            "selected_backend": plan["selected_binding"],
            "semantic_input": plan["semantic_input"],
            "approval_required": True,
            "mutation_performed": False,
            "jira_metadata": {
                "project_key": project_key,
                "selected_issue_type": {
                    "id": selected.get("id"),
                    "name": selected.get("name"),
                },
                "available_field_keys": sorted(key for key in available_fields if key),
            },
            "create_issue_request": {
                "method": "POST",
                "path": "/rest/api/3/issue",
                "body": {"fields": fields},
            },
            "note": "Prepared a Jira create-issue payload from live metadata. No Jira mutation was performed.",
        }
        approval_grant = _approval_grant_from_context(ctx)
        if approval_grant is not None:
            preview["approval_grant"] = {
                "grant_id": approval_grant.get("grant_id"),
                "approval_request_id": approval_grant.get("approval_request_id"),
                "grant_type": approval_grant.get("grant_type"),
            }
        if not _mutation_enabled(ctx):
            return preview
        created = _jira_post_json(base_url, email, token, "/rest/api/3/issue", preview["create_issue_request"]["body"])
        if created.get("error"):
            preview["execution_status"] = "backend_error"
            preview["jira_error"] = created
            return preview
        return {
            **preview,
            "execution_status": "completed",
            "approval_required": False,
            "mutation_performed": True,
            "created_issue": {
                "id": created.get("id"),
                "key": created.get("key"),
                "self": created.get("self"),
            },
            "note": "Created Jira issue after the ANIP runtime validated and reserved an approval grant.",
        }

backend_adapter = DefaultBackendAdapter()
