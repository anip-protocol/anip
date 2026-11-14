"""GitHub REST backend seam for the governed fronting showcase."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

BackendInvocationPlan = dict[str, Any]
GeneratedCapability = dict[str, Any]


def _github_token() -> str | None:
    return os.getenv("GITHUB_TOKEN", "").strip() or None


def _csv_env(name: str) -> set[str]:
    return {item.strip() for item in os.getenv(name, "").split(",") if item.strip()}


def _repo_key(owner: str, repo: str) -> str:
    return f"{owner}/{repo}".lower()


def _repo_allowed(owner: str, repo: str) -> bool:
    key = _repo_key(owner, repo)
    blocked = {item.lower() for item in _csv_env("ANIP_GITHUB_BLOCKED_REPOS")}
    allowed = {item.lower() for item in _csv_env("ANIP_GITHUB_ALLOWED_REPOS")}
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


def _github_request_json(method: str, path: str, token: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    request = urllib.request.Request(
        f"https://api.github.com{path}",
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
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        return {
            "error": "github_http_error",
            "status": exc.code,
            "detail": exc.read().decode("utf-8", errors="replace"),
        }


def _quote_path(value: str) -> str:
    return urllib.parse.quote(value, safe="")


def _approval_grant_from_context(ctx: Any) -> dict[str, Any] | None:
    grant = getattr(ctx, "approval_grant", None)
    if isinstance(grant, dict) and grant.get("grant_id") and grant.get("approval_request_id"):
        return grant
    return None


def _mutation_enabled(ctx: Any) -> bool:
    return os.getenv("ANIP_GITHUB_ALLOW_MUTATION", "").lower() == "true" and _approval_grant_from_context(ctx) is not None


def _metadata(capability: GeneratedCapability, plan: BackendInvocationPlan) -> dict[str, Any]:
    return {
        "capability_id": capability["capability_id"],
        "selected_backend": plan["selected_binding"],
        "semantic_input": plan["semantic_input"],
    }


def _restricted_repo_response(capability: GeneratedCapability, plan: BackendInvocationPlan, owner: str, repo: str) -> dict[str, Any]:
    return {
        "execution_status": "restricted",
        **_metadata(capability, plan),
        "repository": {"owner": owner, "repo": repo},
        "reason": "GitHub repository is outside the configured ANIP repository policy.",
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
                "note": "Generated host is runnable, but backend-only inputs still require extension completion.",
            }
        token = _github_token()
        if token is None:
            return {"execution_status": "backend_error", **_metadata(capability, plan), "github_error": {"error": "missing_github_token"}}
        capability_id = capability["capability_id"]
        if capability_id == "github.repo.search_context":
            return self._search_repository_context(capability, plan, _params, token)
        if capability_id == "github.issue.prepare":
            return self._prepare_or_create_issue(capability, plan, _params, token, ctx)
        if capability_id == "github.pr.comment.prepare":
            return self._prepare_pr_comment(capability, plan, _params, token, ctx)
        if capability_id == "github.workflow.dispatch.request":
            return self._prepare_workflow_dispatch(capability, plan, _params, token, ctx)
        if capability_id == "github.release_notes.prepare":
            return self._prepare_release_notes(capability, plan, _params, token)
        return {
            "execution_status": "backend_execution_stub",
            **_metadata(capability, plan),
            "backend_input_contract": plan["backend_input_contract"],
            "note": "Replace DefaultBackendAdapter.execute() with provider-specific backend execution.",
        }

    def _repo_metadata_or_error(
        self,
        capability: GeneratedCapability,
        plan: BackendInvocationPlan,
        params: dict[str, Any],
        token: str,
    ) -> tuple[str, str, dict[str, Any], dict[str, Any] | None]:
        owner = str(params.get("owner") or "").strip()
        repo = str(params.get("repo") or "").strip()
        if not _repo_allowed(owner, repo):
            return owner, repo, {}, _restricted_repo_response(capability, plan, owner, repo)
        metadata = _github_request_json("GET", f"/repos/{_quote_path(owner)}/{_quote_path(repo)}", token)
        if metadata.get("error"):
            return owner, repo, {}, {"execution_status": "backend_error", **_metadata(capability, plan), "github_error": metadata}
        return owner, repo, metadata, None

    def _search_repository_context(
        self,
        capability: GeneratedCapability,
        plan: BackendInvocationPlan,
        params: dict[str, Any],
        token: str,
    ) -> dict[str, Any]:
        owner = str(params.get("owner") or "").strip()
        repo = str(params.get("repo") or "").strip()
        if not _repo_allowed(owner, repo):
            return _restricted_repo_response(capability, plan, owner, repo)
        query = str(params.get("query") or "").strip()
        limit = _bounded_limit(params.get("limit"))
        search_query = f"repo:{owner}/{repo} {query}".strip()
        payload = _github_request_json(
            "GET",
            f"/search/issues?{urllib.parse.urlencode({'q': search_query, 'per_page': str(limit)})}",
            token,
        )
        if payload.get("error"):
            return {"execution_status": "backend_error", **_metadata(capability, plan), "github_error": payload}
        items = [
            {
                "number": item.get("number"),
                "title": item.get("title"),
                "state": item.get("state"),
                "html_url": item.get("html_url"),
                "kind": "pull_request" if item.get("pull_request") else "issue",
            }
            for item in payload.get("items", [])[:limit]
        ]
        return {
            "execution_status": "completed",
            **_metadata(capability, plan),
            "github_query": search_query,
            "result": {"items": items, "count": len(items), "total_count": payload.get("total_count")},
        }

    def _prepare_or_create_issue(
        self,
        capability: GeneratedCapability,
        plan: BackendInvocationPlan,
        params: dict[str, Any],
        token: str,
        ctx: Any,
    ) -> dict[str, Any]:
        owner, repo, repo_payload, error = self._repo_metadata_or_error(capability, plan, params, token)
        if error is not None:
            return error
        body: dict[str, Any] = {
            "title": str(params.get("title") or "").strip(),
            "body": str(params.get("body") or "").strip(),
        }
        labels = _list_of_strings(params.get("labels"))
        assignees = _list_of_strings(params.get("assignees"))
        if labels:
            body["labels"] = labels
        if assignees:
            body["assignees"] = assignees
        preview = self._write_preview(capability, plan, "issues.create", f"/repos/{owner}/{repo}/issues", body, repo_payload)
        if not _mutation_enabled(ctx):
            return preview
        created = _github_request_json("POST", f"/repos/{_quote_path(owner)}/{_quote_path(repo)}/issues", token, body)
        if created.get("error"):
            return {**preview, "execution_status": "backend_error", "github_error": created}
        return {
            **preview,
            "execution_status": "completed",
            "approval_required": False,
            "mutation_performed": True,
            "created_issue": {"number": created.get("number"), "html_url": created.get("html_url"), "state": created.get("state")},
            "note": "Created GitHub issue after the ANIP runtime validated and reserved an approval grant.",
        }

    def _prepare_pr_comment(
        self,
        capability: GeneratedCapability,
        plan: BackendInvocationPlan,
        params: dict[str, Any],
        token: str,
        ctx: Any,
    ) -> dict[str, Any]:
        owner, repo, repo_payload, error = self._repo_metadata_or_error(capability, plan, params, token)
        if error is not None:
            return error
        pull_number = str(params.get("pull_number") or "").strip()
        pull = _github_request_json("GET", f"/repos/{_quote_path(owner)}/{_quote_path(repo)}/pulls/{_quote_path(pull_number)}", token)
        if pull.get("error"):
            return {"execution_status": "backend_error", **_metadata(capability, plan), "github_error": pull}
        body = {
            "body": self._comment_body(params),
        }
        preview = self._write_preview(capability, plan, "issues.createComment", f"/repos/{owner}/{repo}/issues/{pull_number}/comments", body, repo_payload)
        preview["pull_request"] = {"number": pull.get("number"), "title": pull.get("title"), "state": pull.get("state")}
        if not _mutation_enabled(ctx):
            return preview
        posted = _github_request_json("POST", f"/repos/{_quote_path(owner)}/{_quote_path(repo)}/issues/{_quote_path(pull_number)}/comments", token, body)
        if posted.get("error"):
            return {**preview, "execution_status": "backend_error", "github_error": posted}
        return {
            **preview,
            "execution_status": "completed",
            "approval_required": False,
            "mutation_performed": True,
            "posted_comment": {"id": posted.get("id"), "html_url": posted.get("html_url")},
            "note": "Posted pull request comment after the ANIP runtime validated and reserved an approval grant.",
        }

    def _prepare_workflow_dispatch(
        self,
        capability: GeneratedCapability,
        plan: BackendInvocationPlan,
        params: dict[str, Any],
        token: str,
        ctx: Any,
    ) -> dict[str, Any]:
        owner, repo, repo_payload, error = self._repo_metadata_or_error(capability, plan, params, token)
        if error is not None:
            return error
        workflow_id = str(params.get("workflow_id") or "").strip()
        body = {"ref": str(params.get("ref") or "").strip(), "inputs": params.get("inputs") or {}}
        preview = self._write_preview(
            capability,
            plan,
            "actions.createWorkflowDispatch",
            f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches",
            body,
            repo_payload,
        )
        if not _mutation_enabled(ctx):
            return preview
        dispatched = _github_request_json(
            "POST",
            f"/repos/{_quote_path(owner)}/{_quote_path(repo)}/actions/workflows/{_quote_path(workflow_id)}/dispatches",
            token,
            body,
        )
        if dispatched.get("error"):
            return {**preview, "execution_status": "backend_error", "github_error": dispatched}
        return {
            **preview,
            "execution_status": "completed",
            "approval_required": False,
            "mutation_performed": True,
            "dispatched_workflow": {"workflow_id": workflow_id, "ref": body["ref"]},
            "note": "Dispatched GitHub workflow after the ANIP runtime validated and reserved an approval grant.",
        }

    def _prepare_release_notes(
        self,
        capability: GeneratedCapability,
        plan: BackendInvocationPlan,
        params: dict[str, Any],
        token: str,
    ) -> dict[str, Any]:
        owner, repo, repo_payload, error = self._repo_metadata_or_error(capability, plan, params, token)
        if error is not None:
            return error
        release_range = str(params.get("range") or "").strip()
        audience = str(params.get("audience") or "internal").strip()
        result: dict[str, Any] = {
            "title": f"Release notes for {owner}/{repo} {release_range}",
            "audience": audience,
            "repository": self._repo_summary(repo_payload),
            "range": release_range,
            "sections": [
                {"title": "Highlights", "items": ["Review bounded GitHub context before publishing release notes."]},
                {"title": "Governance", "items": ["This capability drafts content only and does not create a GitHub release."]},
            ],
        }
        if "..." in release_range:
            base, head = release_range.split("...", 1)
            compare = _github_request_json("GET", f"/repos/{_quote_path(owner)}/{_quote_path(repo)}/compare/{_quote_path(base)}...{_quote_path(head)}", token)
            if not compare.get("error"):
                result["compare"] = {
                    "status": compare.get("status"),
                    "ahead_by": compare.get("ahead_by"),
                    "behind_by": compare.get("behind_by"),
                    "total_commits": compare.get("total_commits"),
                    "html_url": compare.get("html_url"),
                }
        return {
            "execution_status": "completed",
            **_metadata(capability, plan),
            "result": result,
            "mutation_performed": False,
        }

    def _write_preview(
        self,
        capability: GeneratedCapability,
        plan: BackendInvocationPlan,
        action: str,
        path: str,
        body: dict[str, Any],
        repo_payload: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "execution_status": "prepared",
            **_metadata(capability, plan),
            "approval_required": True,
            "mutation_performed": False,
            "github_action": action,
            "github_metadata": self._repo_summary(repo_payload),
            "github_request": {"method": "POST", "path": path, "body": body},
            "note": "Prepared a GitHub request payload. No GitHub mutation was performed.",
        }

    def _repo_summary(self, repo_payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "owner": (repo_payload.get("owner") or {}).get("login"),
            "repo": repo_payload.get("name"),
            "default_branch": repo_payload.get("default_branch"),
            "private": repo_payload.get("private"),
            "html_url": repo_payload.get("html_url"),
        }

    def _comment_body(self, params: dict[str, Any]) -> str:
        purpose = str(params.get("comment_purpose") or "triage_update").strip()
        context = str(params.get("context") or "").strip()
        return f"[{purpose}] {context}".strip()


backend_adapter = DefaultBackendAdapter()
