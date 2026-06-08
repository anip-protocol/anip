"""Jira REST implementation seam for the governed Jira fronting showcase."""
from __future__ import annotations

import base64
import json
import os
import re
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


def _auth_headers(email: str, token: str) -> dict[str, str]:
    credentials = base64.b64encode(f"{email}:{token}".encode("utf-8")).decode("ascii")
    return {
        "Accept": "application/json",
        "Authorization": f"Basic {credentials}",
    }


def _bounded_limit(value: Any, default: int = 25, maximum: int = 50) -> int:
    try:
        limit = int(value)
    except (TypeError, ValueError):
        limit = default
    return max(1, min(limit, maximum))


def _safe_jql_value(value: Any) -> str:
    text = str(value or "").strip()
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _safe_label(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9_.-]+", "-", text).strip("-")
    return text[:255]


def _list_value(value: Any) -> list[str]:
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


def _labels(value: Any) -> list[str]:
    return [label for label in (_safe_label(item) for item in _list_value(value)) if label]


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


def _plain_text_from_adf(value: Any) -> str:
    parts: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "text" and isinstance(node.get("text"), str):
                parts.append(node["text"])
            for child in node.get("content") or []:
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(value)
    return " ".join(part.strip() for part in parts if part.strip())


def _priority_for_severity(severity: Any) -> str:
    value = str(severity or "").lower()
    if value in {"sev1", "sev2"}:
        return "High"
    if value == "sev4":
        return "Low"
    return "Medium"


def _jira_json(
    configured: tuple[str, str, str],
    method: str,
    path: str,
    query: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base_url, email, token = configured
    url = f"{base_url}{path}"
    if query:
        url = f"{url}?{urllib.parse.urlencode(query)}"
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = _auth_headers(email, token)
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return {"error": "jira_http_error", "status": exc.code, "detail": detail}
    except urllib.error.URLError as exc:
        return {"error": "jira_url_error", "detail": str(exc)}


def _issue_summary(issue: dict[str, Any]) -> dict[str, Any]:
    fields = issue.get("fields") or {}
    return {
        "key": issue.get("key"),
        "summary": fields.get("summary"),
        "status": ((fields.get("status") or {}).get("name")),
        "issue_type": ((fields.get("issuetype") or {}).get("name")),
        "project_key": ((fields.get("project") or {}).get("key")),
        "assignee": ((fields.get("assignee") or {}).get("displayName")),
        "priority": ((fields.get("priority") or {}).get("name")),
    }


def _issue_query_jql(project_key: str, query_text: str) -> str:
    jql = f'project = "{_safe_jql_value(project_key)}"'
    if query_text:
        jql += f' AND text ~ "{_safe_jql_value(query_text)}"'
    return f"{jql} ORDER BY updated DESC"


def _search_issues(configured: tuple[str, str, str], jql: str, limit: int, fields: str) -> dict[str, Any]:
    return _jira_json(
        configured,
        "GET",
        "/rest/api/3/search/jql",
        {"jql": jql, "maxResults": str(limit), "fields": fields},
    )


def _preview_result(
    capability: GeneratedCapability,
    plan: BackendInvocationPlan,
    action: str,
    request: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "execution_status": "prepared",
        "capability_id": capability["capability_id"],
        "selected_backend": plan["selected_binding"],
        "semantic_input": plan["semantic_input"],
        "approval_required": capability.get("operation_type") == "approval_gated" or capability.get("execution_posture") == "prepare_only",
        "mutation_performed": False,
        "jira_action": action,
        "jira_request_preview": request,
        "jira_metadata": metadata or {},
        "note": "Prepared a governed Jira request preview. No Jira mutation was performed.",
    }


class DefaultBackendAdapter:
    async def execute(
        self,
        capability: GeneratedCapability,
        plan: BackendInvocationPlan,
        adapter_input: dict[str, Any],
        _context: dict[str, Any],
    ) -> dict[str, Any]:
        if plan["unresolved_required_backend_inputs"]:
            return {
                "execution_status": "backend_input_incomplete",
                "capability_id": capability["capability_id"],
                "backend_input_contract": plan["backend_input_contract"],
                "unresolved_required_backend_inputs": plan["unresolved_required_backend_inputs"],
                "note": "Generated host is runnable, but backend-only inputs still require extension completion.",
            }

        configured = _jira_env()
        capability_id = capability["capability_id"]
        if capability_id == "jira.backlog.search_context":
            return self._search_backlog(capability, plan, adapter_input, configured)
        if capability_id == "jira.issue.get_context":
            return self._get_issue_context(capability, plan, adapter_input, configured)
        if capability_id == "jira.release_notes.prepare":
            return self._prepare_release_notes(capability, plan, adapter_input, configured)
        if capability_id == "jira.incident_bug.prepare":
            return self._prepare_issue_create(capability, plan, adapter_input, configured, issue_type_name="Bug")
        if capability_id == "jira.story.prepare":
            return self._prepare_issue_create(capability, plan, adapter_input, configured, issue_type_name="Story")
        if capability_id == "jira.subtask.prepare":
            return self._prepare_subtask(capability, plan, adapter_input, configured)
        if capability_id == "jira.customer_escalation.comment.prepare":
            return self._prepare_comment(capability, plan, adapter_input, configured)
        if capability_id == "jira.workflow_transition.request":
            return self._prepare_transition(capability, plan, adapter_input, configured)
        if capability_id == "jira.sprint_move.request":
            return self._prepare_sprint_move(capability, plan, adapter_input, configured)
        if capability_id == "jira.assignee_change.request":
            return self._prepare_assignee_change(capability, plan, adapter_input, configured)
        if capability_id == "jira.issue_link.request":
            return self._prepare_issue_link(capability, plan, adapter_input, configured)
        return {
            "execution_status": "backend_execution_stub",
            "capability_id": capability_id,
            "selected_backend": plan["selected_binding"],
            "semantic_input": plan["semantic_input"],
            "backend_input_contract": plan["backend_input_contract"],
            "note": "No Jira custom handler is registered for this capability.",
        }

    def _search_backlog(
        self,
        capability: GeneratedCapability,
        plan: BackendInvocationPlan,
        params: dict[str, Any],
        configured: tuple[str, str, str] | None,
    ) -> dict[str, Any]:
        project_key = str(params.get("project_key") or "").strip()
        query_text = str(params.get("query") or "").strip()
        limit = _bounded_limit(params.get("limit"))
        jql = _issue_query_jql(project_key, query_text)
        issue_type = str(params.get("issue_type") or "").strip()
        status = str(params.get("status") or "").strip()
        if issue_type:
            jql += f' AND issuetype = "{_safe_jql_value(issue_type)}"'
        if status:
            jql += f' AND status = "{_safe_jql_value(status)}"'
        if configured is None:
            return {
                "execution_status": "backend_not_configured",
                "capability_id": capability["capability_id"],
                "selected_backend": plan["selected_binding"],
                "semantic_input": plan["semantic_input"],
                "jql_preview": jql,
                "note": "Set JIRA_BASE_URL, JIRA_EMAIL, and JIRA_API_TOKEN to run the live Jira query.",
            }
        payload = _search_issues(configured, jql, limit, "summary,status,issuetype,project,assignee,priority")
        if payload.get("error"):
            return self._backend_error(capability, plan, payload)
        issues = [_issue_summary(issue) for issue in payload.get("issues", [])]
        return {
            "execution_status": "completed",
            "capability_id": capability["capability_id"],
            "selected_backend": plan["selected_binding"],
            "semantic_input": plan["semantic_input"],
            "jql": jql,
            "result": {"issues": issues, "count": len(issues), "is_last": payload.get("isLast")},
        }

    def _get_issue_context(
        self,
        capability: GeneratedCapability,
        plan: BackendInvocationPlan,
        params: dict[str, Any],
        configured: tuple[str, str, str] | None,
    ) -> dict[str, Any]:
        issue_key = str(params.get("issue_key") or "").strip()
        if configured is None:
            return {
                "execution_status": "backend_not_configured",
                "capability_id": capability["capability_id"],
                "selected_backend": plan["selected_binding"],
                "semantic_input": plan["semantic_input"],
                "path_preview": f"/rest/api/3/issue/{issue_key}",
            }
        payload = _jira_json(
            configured,
            "GET",
            f"/rest/api/3/issue/{urllib.parse.quote(issue_key)}",
            {"fields": "summary,status,issuetype,project,assignee,priority,description"},
        )
        if payload.get("error"):
            return self._backend_error(capability, plan, payload)
        result = _issue_summary(payload)
        description = (payload.get("fields") or {}).get("description")
        if description:
            result["description_excerpt"] = _plain_text_from_adf(description)[:500]
        if str(params.get("include_comments") or "").lower() == "true":
            comments = _jira_json(configured, "GET", f"/rest/api/3/issue/{urllib.parse.quote(issue_key)}/comment", {"maxResults": "5"})
            if not comments.get("error"):
                result["comments"] = [
                    {
                        "author": ((comment.get("author") or {}).get("displayName")),
                        "body_excerpt": _plain_text_from_adf(comment.get("body"))[:500],
                        "created": comment.get("created"),
                    }
                    for comment in comments.get("comments", [])
                ]
        return {
            "execution_status": "completed",
            "capability_id": capability["capability_id"],
            "selected_backend": plan["selected_binding"],
            "semantic_input": plan["semantic_input"],
            "result": result,
        }

    def _prepare_release_notes(
        self,
        capability: GeneratedCapability,
        plan: BackendInvocationPlan,
        params: dict[str, Any],
        configured: tuple[str, str, str] | None,
    ) -> dict[str, Any]:
        project_key = str(params.get("project_key") or "").strip()
        release_ref = str(params.get("release_ref") or "").strip()
        issue_query = str(params.get("issue_query") or "").strip()
        audience = str(params.get("audience") or "internal").strip()
        limit = _bounded_limit(params.get("limit"), default=20, maximum=50)
        if release_ref.lower() in {"unversioned", "none", "no-version", "no version"}:
            jql = f'project = "{_safe_jql_value(project_key)}" AND fixVersion is EMPTY'
        else:
            jql = f'project = "{_safe_jql_value(project_key)}" AND fixVersion = "{_safe_jql_value(release_ref)}"'
        if issue_query:
            jql += f' AND text ~ "{_safe_jql_value(issue_query)}"'
        jql += " ORDER BY priority DESC, updated DESC"
        if configured is None:
            issues: list[dict[str, Any]] = []
        else:
            payload = _search_issues(configured, jql, limit, "summary,status,issuetype,project")
            if payload.get("error"):
                return self._backend_error(capability, plan, payload)
            issues = [_issue_summary(issue) for issue in payload.get("issues", [])]
        return {
            "execution_status": "prepared",
            "capability_id": capability["capability_id"],
            "selected_backend": plan["selected_binding"],
            "semantic_input": plan["semantic_input"],
            "jql": jql,
            "result": {
                "audience": audience,
                "issue_count": len(issues),
                "issues": issues,
                "draft": self._release_note_draft(audience, release_ref, issues),
            },
            "note": "Prepared release notes only. No Jira mutation or publication was performed.",
        }

    def _prepare_issue_create(
        self,
        capability: GeneratedCapability,
        plan: BackendInvocationPlan,
        params: dict[str, Any],
        configured: tuple[str, str, str] | None,
        issue_type_name: str,
    ) -> dict[str, Any]:
        project_key = str(params.get("project_key") or "").strip()
        fields: dict[str, Any] = {
            "project": {"key": project_key},
            "issuetype": {"name": issue_type_name},
            "summary": str(params.get("summary") or "").strip(),
        }
        if capability["capability_id"] == "jira.incident_bug.prepare":
            fields["description"] = _adf_doc(params.get("description"))
            fields["priority"] = {"name": _priority_for_severity(params.get("severity"))}
        if capability["capability_id"] == "jira.story.prepare":
            fields["description"] = _adf_doc(f"Acceptance criteria:\n{params.get('acceptance_criteria') or ''}")
            priority = str(params.get("priority") or "").strip()
            if priority:
                fields["priority"] = {"name": priority.title()}
        labels = _labels(params.get("labels"))
        if labels:
            fields["labels"] = labels
        metadata: dict[str, Any] = {"project_key": project_key, "requested_issue_type": issue_type_name}
        if configured is not None:
            issue_type = self._resolve_issue_type(configured, project_key, issue_type_name)
            if issue_type:
                fields["issuetype"] = {"id": issue_type.get("id")}
                metadata["selected_issue_type"] = {"id": issue_type.get("id"), "name": issue_type.get("name")}
        return _preview_result(capability, plan, "create_issue", {"method": "POST", "path": "/rest/api/3/issue", "body": {"fields": fields}}, metadata)

    def _prepare_subtask(
        self,
        capability: GeneratedCapability,
        plan: BackendInvocationPlan,
        params: dict[str, Any],
        configured: tuple[str, str, str] | None,
    ) -> dict[str, Any]:
        parent_issue_key = str(params.get("parent_issue_key") or "").strip()
        project_key = ""
        parent_id = None
        if configured is not None:
            parent = _jira_json(configured, "GET", f"/rest/api/3/issue/{urllib.parse.quote(parent_issue_key)}", {"fields": "project"})
            if not parent.get("error"):
                parent_id = parent.get("id")
                project_key = (((parent.get("fields") or {}).get("project") or {}).get("key")) or ""
        fields: dict[str, Any] = {
            "parent": {"key": parent_issue_key},
            "issuetype": {"name": "Sub-task"},
            "summary": str(params.get("summary") or "").strip(),
            "description": _adf_doc(params.get("description")),
        }
        if project_key:
            fields["project"] = {"key": project_key}
        if parent_id:
            fields["parent"] = {"id": parent_id}
        assignee = str(params.get("assignee") or "").strip()
        metadata = {"parent_issue_key": parent_issue_key, "project_key": project_key}
        if assignee:
            metadata["assignee_ref"] = assignee
        return _preview_result(capability, plan, "create_subtask", {"method": "POST", "path": "/rest/api/3/issue", "body": {"fields": fields}}, metadata)

    def _prepare_comment(
        self,
        capability: GeneratedCapability,
        plan: BackendInvocationPlan,
        params: dict[str, Any],
        _configured: tuple[str, str, str] | None,
    ) -> dict[str, Any]:
        issue_key = str(params.get("issue_key") or "").strip()
        purpose = str(params.get("comment_purpose") or "").strip()
        visibility = str(params.get("visibility") or "internal").strip()
        body_text = f"[{purpose}] {params.get('context') or ''}".strip()
        return _preview_result(
            capability,
            plan,
            "add_comment",
            {
                "method": "POST",
                "path": f"/rest/api/3/issue/{issue_key}/comment",
                "body": {"body": _adf_doc(body_text), "visibility": visibility},
            },
            {"issue_key": issue_key, "visibility": visibility, "comment_purpose": purpose},
        )

    def _prepare_transition(
        self,
        capability: GeneratedCapability,
        plan: BackendInvocationPlan,
        params: dict[str, Any],
        configured: tuple[str, str, str] | None,
    ) -> dict[str, Any]:
        issue_key = str(params.get("issue_key") or "").strip()
        target_status = str(params.get("target_status") or "").strip()
        transition_id = None
        transitions: list[dict[str, Any]] = []
        if configured is not None:
            payload = _jira_json(configured, "GET", f"/rest/api/3/issue/{urllib.parse.quote(issue_key)}/transitions")
            if not payload.get("error"):
                transitions = payload.get("transitions") or []
                selected = next((item for item in transitions if str(item.get("name") or "").lower() == target_status.lower()), None)
                transition_id = (selected or {}).get("id")
        body: dict[str, Any] = {"transition": {"id": transition_id or target_status}}
        comment = str(params.get("comment") or "").strip()
        if comment:
            body["update"] = {"comment": [{"add": {"body": _adf_doc(comment)}}]}
        return _preview_result(
            capability,
            plan,
            "transition_issue",
            {"method": "POST", "path": f"/rest/api/3/issue/{issue_key}/transitions", "body": body},
            {"issue_key": issue_key, "target_status": target_status, "available_transitions": [item.get("name") for item in transitions]},
        )

    def _prepare_sprint_move(
        self,
        capability: GeneratedCapability,
        plan: BackendInvocationPlan,
        params: dict[str, Any],
        _configured: tuple[str, str, str] | None,
    ) -> dict[str, Any]:
        issue_keys = _list_value(params.get("issue_keys"))
        target_sprint = str(params.get("target_sprint") or "").strip()
        return _preview_result(
            capability,
            plan,
            "move_issues_to_sprint",
            {"method": "POST", "path": f"/rest/agile/1.0/sprint/{target_sprint}/issue", "body": {"issues": issue_keys}},
            {"issue_keys": issue_keys, "target_sprint": target_sprint},
        )

    def _prepare_assignee_change(
        self,
        capability: GeneratedCapability,
        plan: BackendInvocationPlan,
        params: dict[str, Any],
        _configured: tuple[str, str, str] | None,
    ) -> dict[str, Any]:
        issue_key = str(params.get("issue_key") or "").strip()
        assignee_ref = str(params.get("assignee_ref") or "").strip()
        return _preview_result(
            capability,
            plan,
            "assign_issue",
            {"method": "PUT", "path": f"/rest/api/3/issue/{issue_key}/assignee", "body": {"accountId": assignee_ref}},
            {"issue_key": issue_key, "assignee_ref": assignee_ref},
        )

    def _prepare_issue_link(
        self,
        capability: GeneratedCapability,
        plan: BackendInvocationPlan,
        params: dict[str, Any],
        configured: tuple[str, str, str] | None,
    ) -> dict[str, Any]:
        source_issue_key = str(params.get("source_issue_key") or "").strip()
        target_issue_key = str(params.get("target_issue_key") or "").strip()
        link_type = str(params.get("link_type") or "").strip()
        link_types: list[str] = []
        if configured is not None:
            payload = _jira_json(configured, "GET", "/rest/api/3/issueLinkType")
            if not payload.get("error"):
                link_types = [item.get("name") for item in payload.get("issueLinkTypes", []) if item.get("name")]
        return _preview_result(
            capability,
            plan,
            "link_issues",
            {
                "method": "POST",
                "path": "/rest/api/3/issueLink",
                "body": {
                    "type": {"name": link_type},
                    "inwardIssue": {"key": source_issue_key},
                    "outwardIssue": {"key": target_issue_key},
                    "comment": {"body": _adf_doc(params.get("reason"))},
                },
            },
            {"available_link_types": link_types, "requested_link_type": link_type},
        )

    def _resolve_issue_type(self, configured: tuple[str, str, str], project_key: str, issue_type_name: str) -> dict[str, Any] | None:
        payload = _jira_json(configured, "GET", f"/rest/api/3/issue/createmeta/{urllib.parse.quote(project_key)}/issuetypes")
        if payload.get("error"):
            return None
        issue_types = payload.get("issueTypes") or []
        selected = next((item for item in issue_types if str(item.get("name") or "").lower() == issue_type_name.lower()), None)
        if selected is not None:
            return selected
        if issue_type_name.lower() == "story":
            return next((item for item in issue_types if not item.get("subtask")), None)
        return None

    def _release_note_draft(self, audience: str, release_ref: str, issues: list[dict[str, Any]]) -> str:
        heading = f"Release {release_ref} notes for {audience}"
        if not issues:
            return f"{heading}\n\nNo matching Jira issues were returned for the bounded query."
        lines = [heading, ""]
        for issue in issues:
            lines.append(f"- {issue.get('key')}: {issue.get('summary')} ({issue.get('status')})")
        return "\n".join(lines)

    def _backend_error(self, capability: GeneratedCapability, plan: BackendInvocationPlan, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "execution_status": "backend_error",
            "capability_id": capability["capability_id"],
            "selected_backend": plan["selected_binding"],
            "semantic_input": plan["semantic_input"],
            "jira_error": payload,
        }


backend_adapter = DefaultBackendAdapter()
