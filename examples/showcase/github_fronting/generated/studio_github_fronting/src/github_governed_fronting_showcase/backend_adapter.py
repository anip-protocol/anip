"""Backend execution seam for generated capabilities."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

BackendInvocationPlan = dict[str, Any]
GeneratedCapability = dict[str, Any]


def _github_env() -> str | None:
    return os.getenv("GITHUB_TOKEN", "").strip() or None


def _bounded_limit(value: Any) -> int:
    try:
        limit = int(value)
    except (TypeError, ValueError):
        limit = 20
    return max(1, min(limit, 50))


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


def _github_request_json(method: str, path: str, token: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"https://api.github.com{path}"
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "anip-github-fronting-showcase",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return {"error": "github_http_error", "status": exc.code, "detail": detail}


def _approval_grant_from_context(ctx: Any) -> dict[str, Any] | None:
    grant = getattr(ctx, "approval_grant", None)
    if isinstance(grant, dict) and grant.get("grant_id") and grant.get("approval_request_id"):
        return grant
    return None


def _mutation_enabled(ctx: Any) -> bool:
    if os.getenv("ANIP_GITHUB_ALLOW_MUTATION", "").lower() != "true":
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
        token = _github_env()
        if capability["capability_id"] == "github.repo.search_context" and token is not None:
            return self._search_repository_context(capability, plan, _params, token)
        if capability["capability_id"] == "github.issue.prepare" and token is not None:
            return self._prepare_issue(capability, plan, _params, token, ctx)
        return {
            "execution_status": "backend_execution_stub",
            "capability_id": capability["capability_id"],
            "selected_backend": plan["selected_binding"],
            "semantic_input": plan["semantic_input"],
            "backend_input_contract": plan["backend_input_contract"],
            "note": "Replace DefaultBackendAdapter.execute() with provider-specific backend execution.",
        }

    def _search_repository_context(
        self,
        capability: GeneratedCapability,
        plan: BackendInvocationPlan,
        params: dict[str, Any],
        token: str,
    ) -> dict[str, Any]:
        owner = str(params.get("owner") or "").strip()
        repo = str(params.get("repo") or "").strip()
        query = str(params.get("query") or "").strip()
        limit = _bounded_limit(params.get("limit"))
        search_query = f"repo:{owner}/{repo} {query}".strip()
        payload = _github_request_json(
            "GET",
            f"/search/issues?{urllib.parse.urlencode({'q': search_query, 'per_page': str(limit)})}",
            token,
        )
        if payload.get("error"):
            return {
                "execution_status": "backend_error",
                "capability_id": capability["capability_id"],
                "selected_backend": plan["selected_binding"],
                "semantic_input": plan["semantic_input"],
                "github_error": payload,
            }
        items = []
        for item in payload.get("items", [])[:limit]:
            items.append(
                {
                    "number": item.get("number"),
                    "title": item.get("title"),
                    "state": item.get("state"),
                    "html_url": item.get("html_url"),
                    "kind": "pull_request" if item.get("pull_request") else "issue",
                }
            )
        return {
            "execution_status": "completed",
            "capability_id": capability["capability_id"],
            "selected_backend": plan["selected_binding"],
            "semantic_input": plan["semantic_input"],
            "github_query": search_query,
            "result": {"items": items, "count": len(items), "total_count": payload.get("total_count")},
        }

    def _prepare_issue(
        self,
        capability: GeneratedCapability,
        plan: BackendInvocationPlan,
        params: dict[str, Any],
        token: str,
        ctx: Any,
    ) -> dict[str, Any]:
        owner = str(params.get("owner") or "").strip()
        repo = str(params.get("repo") or "").strip()
        repo_payload = _github_request_json("GET", f"/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}", token)
        if repo_payload.get("error"):
            return {
                "execution_status": "backend_error",
                "capability_id": capability["capability_id"],
                "selected_backend": plan["selected_binding"],
                "semantic_input": plan["semantic_input"],
                "github_error": repo_payload,
            }
        body = {
            "title": str(params.get("title") or "").strip(),
            "body": str(params.get("body") or "").strip(),
        }
        labels = _list_of_strings(params.get("labels"))
        assignees = _list_of_strings(params.get("assignees"))
        if labels:
            body["labels"] = labels
        if assignees:
            body["assignees"] = assignees
        preview = {
            "execution_status": "prepared",
            "capability_id": capability["capability_id"],
            "selected_backend": plan["selected_binding"],
            "semantic_input": plan["semantic_input"],
            "approval_required": True,
            "mutation_performed": False,
            "github_metadata": {
                "owner": owner,
                "repo": repo,
                "default_branch": repo_payload.get("default_branch"),
                "private": repo_payload.get("private"),
            },
            "create_issue_request": {
                "method": "POST",
                "path": f"/repos/{owner}/{repo}/issues",
                "body": body,
            },
            "note": "Prepared a GitHub create-issue payload from live repository metadata. No GitHub mutation was performed.",
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
        created = _github_request_json("POST", f"/repos/{owner}/{repo}/issues", token, body)
        if created.get("error"):
            preview["execution_status"] = "backend_error"
            preview["github_error"] = created
            return preview
        return {
            **preview,
            "execution_status": "completed",
            "approval_required": False,
            "mutation_performed": True,
            "created_issue": {
                "number": created.get("number"),
                "html_url": created.get("html_url"),
                "state": created.get("state"),
            },
            "note": "Created GitHub issue after the ANIP runtime validated and reserved an approval grant.",
        }

backend_adapter = DefaultBackendAdapter()
