"""GitLab REST backend seam for the governed fronting showcase."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

BackendInvocationPlan = dict[str, Any]
GeneratedCapability = dict[str, Any]


def _gitlab_token() -> str | None:
    return os.getenv("GITLAB_TOKEN", "").strip() or None


def _api_base() -> str:
    return os.getenv("GITLAB_API_BASE", "https://gitlab.com/api/v4").rstrip("/")


def _csv_env(name: str) -> set[str]:
    return {item.strip() for item in os.getenv(name, "").split(",") if item.strip()}


def _project_allowed(project_id: str) -> bool:
    key = project_id.lower()
    blocked = {item.lower() for item in _csv_env("ANIP_GITLAB_BLOCKED_PROJECTS")}
    allowed = {item.lower() for item in _csv_env("ANIP_GITLAB_ALLOWED_PROJECTS")}
    if key in blocked:
        return False
    return not allowed or key in allowed


def _bounded_limit(value: Any, *, default: int = 20, maximum: int = 50) -> int:
    try:
        limit = int(value)
    except (TypeError, ValueError):
        limit = default
    return max(1, min(limit, maximum))


def _list_of_strings(value: Any) -> list[str]:
    if isinstance(value, list):
        raw = value
    elif isinstance(value, str) and value.strip():
        raw = [item.strip() for item in value.split(",")]
    else:
        raw = []
    result: list[str] = []
    for item in raw:
        text = str(item).strip()
        if text and text not in result:
            result.append(text)
    return result


def _project_path(project_id: str) -> str:
    return urllib.parse.quote(project_id, safe="")


def _project_id_from_params(params: dict[str, Any]) -> str:
    explicit = str(params.get("project_id") or "").strip()
    if explicit:
        return explicit
    namespace = str(params.get("namespace") or "").strip().strip("/")
    project = str(params.get("project") or "").strip().strip("/")
    if namespace and project:
        return f"{namespace}/{project}"
    return ""


def _gitlab_request_json(method: str, path: str, token: str, body: dict[str, Any] | None = None) -> Any:
    request = urllib.request.Request(
        f"{_api_base()}{path}",
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "PRIVATE-TOKEN": token,
            "User-Agent": "anip-gitlab-fronting-showcase",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        return {
            "error": "gitlab_http_error",
            "status": exc.code,
            "detail": exc.read().decode("utf-8", errors="replace"),
        }


def _approval_grant_from_context(ctx: Any) -> dict[str, Any] | None:
    grant = getattr(ctx, "approval_grant", None)
    if isinstance(grant, dict) and grant.get("grant_id") and grant.get("approval_request_id"):
        return grant
    return None


def _mutation_enabled(ctx: Any) -> bool:
    return os.getenv("ANIP_GITLAB_ALLOW_MUTATION", "").lower() == "true" and _approval_grant_from_context(ctx) is not None


def _metadata(capability: GeneratedCapability, plan: BackendInvocationPlan) -> dict[str, Any]:
    return {
        "capability_id": capability["capability_id"],
        "selected_backend": plan["selected_binding"],
        "semantic_input": plan["semantic_input"],
    }


def _restricted_project_response(capability: GeneratedCapability, plan: BackendInvocationPlan, project_id: str) -> dict[str, Any]:
    return {
        "execution_status": "restricted",
        **_metadata(capability, plan),
        "project_id": project_id,
        "reason": "GitLab project is outside the configured ANIP project policy.",
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
        token = _gitlab_token()
        if token is None:
            return {"execution_status": "backend_error", **_metadata(capability, plan), "gitlab_error": {"error": "missing_gitlab_token"}}
        capability_id = capability["capability_id"]
        if capability_id == "gitlab.project.search_context":
            return self._search_project_context(capability, plan, _params, token)
        if capability_id == "gitlab.issue.prepare":
            return self._prepare_or_create_issue(capability, plan, _params, token, ctx)
        if capability_id == "gitlab.mr.comment.prepare":
            return self._prepare_mr_comment(capability, plan, _params, token, ctx)
        if capability_id == "gitlab.pipeline.trigger.request":
            return self._prepare_pipeline_trigger(capability, plan, _params, token, ctx)
        if capability_id == "gitlab.release_notes.prepare":
            return self._prepare_release_notes(capability, plan, _params, token)
        return {
            "execution_status": "backend_execution_stub",
            **_metadata(capability, plan),
            "backend_input_contract": plan["backend_input_contract"],
        }

    def _project_metadata_or_error(
        self,
        capability: GeneratedCapability,
        plan: BackendInvocationPlan,
        params: dict[str, Any],
        token: str,
    ) -> tuple[str, dict[str, Any], dict[str, Any] | None]:
        project_id = _project_id_from_params(params)
        if not _project_allowed(project_id):
            return project_id, {}, _restricted_project_response(capability, plan, project_id)
        project = _gitlab_request_json("GET", f"/projects/{_project_path(project_id)}", token)
        if isinstance(project, dict) and project.get("error"):
            return project_id, {}, {"execution_status": "backend_error", **_metadata(capability, plan), "gitlab_error": project}
        return project_id, project, None

    def _search_project_context(
        self,
        capability: GeneratedCapability,
        plan: BackendInvocationPlan,
        params: dict[str, Any],
        token: str,
    ) -> dict[str, Any]:
        project_id = _project_id_from_params(params)
        if not _project_allowed(project_id):
            return _restricted_project_response(capability, plan, project_id)
        query = str(params.get("query") or "").strip()
        limit = _bounded_limit(params.get("limit"))
        encoded = urllib.parse.urlencode({"search": query, "per_page": str(limit)})
        issues = _gitlab_request_json("GET", f"/projects/{_project_path(project_id)}/issues?{encoded}", token)
        merge_requests = _gitlab_request_json("GET", f"/projects/{_project_path(project_id)}/merge_requests?{encoded}", token)
        if isinstance(issues, dict) and issues.get("error"):
            return {"execution_status": "backend_error", **_metadata(capability, plan), "gitlab_error": issues}
        if isinstance(merge_requests, dict) and merge_requests.get("error"):
            return {"execution_status": "backend_error", **_metadata(capability, plan), "gitlab_error": merge_requests}
        items = [
            {"kind": "issue", "iid": item.get("iid"), "title": item.get("title"), "state": item.get("state"), "web_url": item.get("web_url")}
            for item in list(issues or [])[:limit]
        ]
        remaining = max(0, limit - len(items))
        items.extend(
            {"kind": "merge_request", "iid": item.get("iid"), "title": item.get("title"), "state": item.get("state"), "web_url": item.get("web_url")}
            for item in list(merge_requests or [])[:remaining]
        )
        return {
            "execution_status": "completed",
            **_metadata(capability, plan),
            "gitlab_query": query,
            "result": {"items": items, "count": len(items), "project_id": project_id},
        }

    def _prepare_or_create_issue(
        self,
        capability: GeneratedCapability,
        plan: BackendInvocationPlan,
        params: dict[str, Any],
        token: str,
        ctx: Any,
    ) -> dict[str, Any]:
        project_id, project, error = self._project_metadata_or_error(capability, plan, params, token)
        if error is not None:
            return error
        body: dict[str, Any] = {
            "title": str(params.get("title") or "").strip(),
            "description": str(params.get("body") or params.get("description") or "").strip(),
        }
        labels = _list_of_strings(params.get("labels"))
        if labels:
            body["labels"] = ",".join(labels)
        preview = self._write_preview(capability, plan, "issues.create", f"/projects/{project_id}/issues", body, project)
        if not _mutation_enabled(ctx):
            return preview
        created = _gitlab_request_json("POST", f"/projects/{_project_path(project_id)}/issues", token, body)
        if isinstance(created, dict) and created.get("error"):
            return {**preview, "execution_status": "backend_error", "gitlab_error": created}
        return {
            **preview,
            "execution_status": "completed",
            "approval_required": False,
            "mutation_performed": True,
            "created_issue": {"iid": created.get("iid"), "web_url": created.get("web_url"), "state": created.get("state")},
        }

    def _prepare_mr_comment(self, capability: GeneratedCapability, plan: BackendInvocationPlan, params: dict[str, Any], token: str, ctx: Any) -> dict[str, Any]:
        project_id, project, error = self._project_metadata_or_error(capability, plan, params, token)
        if error is not None:
            return error
        iid = str(params.get("merge_request_iid") or "").strip()
        mr = _gitlab_request_json("GET", f"/projects/{_project_path(project_id)}/merge_requests/{_project_path(iid)}", token)
        if isinstance(mr, dict) and mr.get("error"):
            return {"execution_status": "backend_error", **_metadata(capability, plan), "gitlab_error": mr}
        body = {"body": f"[{params.get('comment_purpose')}] {params.get('context')}".strip()}
        preview = self._write_preview(capability, plan, "merge_requests.createNote", f"/projects/{project_id}/merge_requests/{iid}/notes", body, project)
        preview["merge_request"] = {"iid": mr.get("iid"), "title": mr.get("title"), "state": mr.get("state")}
        return preview

    def _prepare_pipeline_trigger(self, capability: GeneratedCapability, plan: BackendInvocationPlan, params: dict[str, Any], token: str, ctx: Any) -> dict[str, Any]:
        project_id, project, error = self._project_metadata_or_error(capability, plan, params, token)
        if error is not None:
            return error
        body = {
            "ref": str(params.get("ref") or "").strip(),
            "variables": params.get("variables") or {},
            "purpose": str(params.get("pipeline_purpose") or "").strip(),
        }
        return self._write_preview(capability, plan, "pipeline.trigger", f"/projects/{project_id}/pipeline", body, project)

    def _prepare_release_notes(self, capability: GeneratedCapability, plan: BackendInvocationPlan, params: dict[str, Any], token: str) -> dict[str, Any]:
        project_id, project, error = self._project_metadata_or_error(capability, plan, params, token)
        if error is not None:
            return error
        release_range = str(params.get("range") or "").strip()
        return {
            "execution_status": "completed",
            **_metadata(capability, plan),
            "mutation_performed": False,
            "result": {
                "title": f"Release notes for {project.get('path_with_namespace') or project_id} {release_range}",
                "audience": str(params.get("audience") or "internal").strip(),
                "project": self._project_summary(project),
                "range": release_range,
                "sections": [
                    {"title": "Highlights", "items": ["Review bounded GitLab context before publishing release notes."]},
                    {"title": "Governance", "items": ["This capability drafts content only and does not create a GitLab release."]},
                ],
            },
        }

    def _write_preview(self, capability: GeneratedCapability, plan: BackendInvocationPlan, action: str, path: str, body: dict[str, Any], project: dict[str, Any]) -> dict[str, Any]:
        return {
            "execution_status": "prepared",
            **_metadata(capability, plan),
            "approval_required": True,
            "mutation_performed": False,
            "gitlab_action": action,
            "gitlab_metadata": self._project_summary(project),
            "gitlab_request": {"method": "POST", "path": path, "body": body},
            "note": "Prepared a GitLab request payload. No GitLab mutation was performed.",
        }

    def _project_summary(self, project: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": project.get("id"),
            "path_with_namespace": project.get("path_with_namespace"),
            "default_branch": project.get("default_branch"),
            "visibility": project.get("visibility"),
            "web_url": project.get("web_url"),
        }


backend_adapter = DefaultBackendAdapter()
