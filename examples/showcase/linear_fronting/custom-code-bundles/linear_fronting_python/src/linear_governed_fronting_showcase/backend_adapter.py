"""Linear GraphQL backend seam for the governed fronting showcase."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

BackendInvocationPlan = dict[str, Any]
GeneratedCapability = dict[str, Any]


def _linear_token() -> str | None:
    return os.getenv("LINEAR_API_KEY", "").strip() or None


def _api_url() -> str:
    return os.getenv("LINEAR_API_URL", "https://api.linear.app/graphql").strip()


def _csv_env(name: str) -> set[str]:
    return {item.strip().lower() for item in os.getenv(name, "").split(",") if item.strip()}


def _team_allowed(team_key: str) -> bool:
    key = team_key.strip().lower()
    blocked = _csv_env("ANIP_LINEAR_BLOCKED_TEAMS")
    allowed = _csv_env("ANIP_LINEAR_ALLOWED_TEAMS")
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


def _linear_graphql(token: str, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    request = urllib.request.Request(
        _api_url(),
        data=json.dumps({"query": query, "variables": variables or {}}).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": token,
            "User-Agent": "anip-linear-fronting-showcase",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        return {
            "errors": [
                {
                    "message": "linear_http_error",
                    "status": exc.code,
                    "detail": exc.read().decode("utf-8", errors="replace"),
                }
            ]
        }


def _approval_grant_from_context(ctx: Any) -> dict[str, Any] | None:
    grant = getattr(ctx, "approval_grant", None)
    if isinstance(grant, dict) and grant.get("grant_id") and grant.get("approval_request_id"):
        return grant
    return None


def _mutation_enabled(ctx: Any) -> bool:
    return os.getenv("ANIP_LINEAR_ALLOW_MUTATION", "").lower() == "true" and _approval_grant_from_context(ctx) is not None


def _metadata(capability: GeneratedCapability, plan: BackendInvocationPlan) -> dict[str, Any]:
    return {
        "capability_id": capability["capability_id"],
        "selected_backend": plan["selected_binding"],
        "semantic_input": plan["semantic_input"],
    }


def _backend_error(capability: GeneratedCapability, plan: BackendInvocationPlan, errors: Any) -> dict[str, Any]:
    return {"execution_status": "backend_error", **_metadata(capability, plan), "linear_error": errors}


def _restricted_team_response(capability: GeneratedCapability, plan: BackendInvocationPlan, team_key: str) -> dict[str, Any]:
    return {
        "execution_status": "restricted",
        **_metadata(capability, plan),
        "team_key": team_key,
        "reason": "Linear team is outside the configured ANIP team policy.",
    }


def _team_query(token: str, team_key: str) -> dict[str, Any]:
    return _linear_graphql(
        token,
        """
        query TeamByKey($key: String!) {
          teams(filter: { key: { eq: $key } }, first: 1) {
            nodes { id key name }
          }
        }
        """,
        {"key": team_key},
    )


def _team_from_response(response: dict[str, Any]) -> dict[str, Any] | None:
    nodes = (((response.get("data") or {}).get("teams") or {}).get("nodes") or [])
    return nodes[0] if nodes else None


def _issue_query(token: str, issue_id: str) -> dict[str, Any]:
    return _linear_graphql(
        token,
        """
        query IssueById($id: String!) {
          issue(id: $id) {
            id identifier title url
            state { id name }
            team { id key name }
          }
        }
        """,
        {"id": issue_id},
    )


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
        token = _linear_token()
        if token is None:
            return {"execution_status": "backend_error", **_metadata(capability, plan), "linear_error": {"error": "missing_linear_api_key"}}
        capability_id = capability["capability_id"]
        if capability_id == "linear.issue.search_context":
            return self._search_issue_context(capability, plan, _params, token)
        if capability_id == "linear.issue.prepare":
            return self._prepare_or_create_issue(capability, plan, _params, token, ctx)
        if capability_id == "linear.comment.prepare":
            return self._prepare_or_post_comment(capability, plan, _params, token, ctx)
        if capability_id == "linear.status_transition.request":
            return self._prepare_status_transition(capability, plan, _params, token)
        if capability_id == "linear.cycle_move.request":
            return self._prepare_cycle_move(capability, plan, _params, token)
        return {
            "execution_status": "backend_execution_stub",
            **_metadata(capability, plan),
            "backend_input_contract": plan["backend_input_contract"],
        }

    def _team_or_error(
        self,
        capability: GeneratedCapability,
        plan: BackendInvocationPlan,
        team_key: str,
        token: str,
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        if not _team_allowed(team_key):
            return {}, _restricted_team_response(capability, plan, team_key)
        response = _team_query(token, team_key)
        if response.get("errors"):
            return {}, _backend_error(capability, plan, response["errors"])
        team = _team_from_response(response)
        if not team:
            return {}, {"execution_status": "not_found", **_metadata(capability, plan), "team_key": team_key}
        return team, None

    def _search_issue_context(
        self,
        capability: GeneratedCapability,
        plan: BackendInvocationPlan,
        params: dict[str, Any],
        token: str,
    ) -> dict[str, Any]:
        team_key = str(params.get("team_key") or "").strip()
        team, error = self._team_or_error(capability, plan, team_key, token)
        if error is not None:
            return error
        query = str(params.get("query") or "").strip()
        limit = _bounded_limit(params.get("limit"))
        response = _linear_graphql(
            token,
            """
            query IssueSearch($teamId: ID!, $first: Int!) {
              issues(filter: { team: { id: { eq: $teamId } } }, first: $first, orderBy: updatedAt) {
                nodes {
                  id identifier title url updatedAt
                  state { name }
                  assignee { name email }
                }
              }
            }
            """,
            {"teamId": team["id"], "first": limit},
        )
        if response.get("errors"):
            return _backend_error(capability, plan, response["errors"])
        nodes = (((response.get("data") or {}).get("issues") or {}).get("nodes") or [])
        lowered = query.lower()
        items = [
            {
                "id": item.get("id"),
                "identifier": item.get("identifier"),
                "title": item.get("title"),
                "url": item.get("url"),
                "state": (item.get("state") or {}).get("name"),
                "updated_at": item.get("updatedAt"),
            }
            for item in nodes
            if not lowered or lowered in str(item.get("title") or "").lower() or lowered in str(item.get("identifier") or "").lower()
        ][:limit]
        return {
            "execution_status": "completed",
            **_metadata(capability, plan),
            "linear_query": query,
            "result": {"team": self._team_summary(team), "items": items, "count": len(items)},
        }

    def _prepare_or_create_issue(
        self,
        capability: GeneratedCapability,
        plan: BackendInvocationPlan,
        params: dict[str, Any],
        token: str,
        ctx: Any,
    ) -> dict[str, Any]:
        team_key = str(params.get("team_key") or "").strip()
        team, error = self._team_or_error(capability, plan, team_key, token)
        if error is not None:
            return error
        body: dict[str, Any] = {
            "teamId": team["id"],
            "title": str(params.get("title") or "").strip(),
            "description": str(params.get("description") or "").strip(),
        }
        if params.get("project_id"):
            body["projectId"] = str(params["project_id"]).strip()
        preview = self._write_preview(capability, plan, "issueCreate", body, {"team": team, "labels": _list_of_strings(params.get("labels"))})
        if not _mutation_enabled(ctx):
            return preview
        created = _linear_graphql(
            token,
            """
            mutation CreateIssue($input: IssueCreateInput!) {
              issueCreate(input: $input) {
                success
                issue { id identifier title url state { name } }
              }
            }
            """,
            {"input": body},
        )
        if created.get("errors"):
            return {**preview, "execution_status": "backend_error", "linear_error": created["errors"]}
        issue = (((created.get("data") or {}).get("issueCreate") or {}).get("issue") or {})
        return {
            **preview,
            "execution_status": "completed",
            "approval_required": False,
            "mutation_performed": True,
            "created_issue": {
                "id": issue.get("id"),
                "identifier": issue.get("identifier"),
                "url": issue.get("url"),
                "state": (issue.get("state") or {}).get("name"),
            },
        }

    def _prepare_or_post_comment(
        self,
        capability: GeneratedCapability,
        plan: BackendInvocationPlan,
        params: dict[str, Any],
        token: str,
        ctx: Any,
    ) -> dict[str, Any]:
        issue_id = str(params.get("issue_id") or "").strip()
        issue_response = _issue_query(token, issue_id)
        if issue_response.get("errors"):
            return _backend_error(capability, plan, issue_response["errors"])
        issue = ((issue_response.get("data") or {}).get("issue") or {})
        if not issue:
            return {"execution_status": "not_found", **_metadata(capability, plan), "issue_id": issue_id}
        body = {"issueId": issue["id"], "body": f"[{params.get('comment_purpose')}] {params.get('context')}".strip()}
        preview = self._write_preview(capability, plan, "commentCreate", body, {"issue": self._issue_summary(issue)})
        if not _mutation_enabled(ctx):
            return preview
        posted = _linear_graphql(
            token,
            """
            mutation CreateComment($input: CommentCreateInput!) {
              commentCreate(input: $input) {
                success
                comment { id url body }
              }
            }
            """,
            {"input": body},
        )
        if posted.get("errors"):
            return {**preview, "execution_status": "backend_error", "linear_error": posted["errors"]}
        comment = (((posted.get("data") or {}).get("commentCreate") or {}).get("comment") or {})
        return {**preview, "execution_status": "completed", "approval_required": False, "mutation_performed": True, "created_comment": comment}

    def _prepare_status_transition(
        self,
        capability: GeneratedCapability,
        plan: BackendInvocationPlan,
        params: dict[str, Any],
        token: str,
    ) -> dict[str, Any]:
        issue_id = str(params.get("issue_id") or "").strip()
        issue_response = _issue_query(token, issue_id)
        if issue_response.get("errors"):
            return _backend_error(capability, plan, issue_response["errors"])
        issue = ((issue_response.get("data") or {}).get("issue") or {})
        if not issue:
            return {"execution_status": "not_found", **_metadata(capability, plan), "issue_id": issue_id}
        return self._write_preview(
            capability,
            plan,
            "issueUpdate.state",
            {"issueId": issue["id"], "target_status": str(params.get("target_status") or "").strip(), "reason": str(params.get("reason") or "").strip()},
            {"issue": self._issue_summary(issue)},
        )

    def _prepare_cycle_move(
        self,
        capability: GeneratedCapability,
        plan: BackendInvocationPlan,
        params: dict[str, Any],
        token: str,
    ) -> dict[str, Any]:
        issue_id = str(params.get("issue_id") or "").strip()
        issue_response = _issue_query(token, issue_id)
        if issue_response.get("errors"):
            return _backend_error(capability, plan, issue_response["errors"])
        issue = ((issue_response.get("data") or {}).get("issue") or {})
        if not issue:
            return {"execution_status": "not_found", **_metadata(capability, plan), "issue_id": issue_id}
        return self._write_preview(
            capability,
            plan,
            "issueUpdate.cycle",
            {"issueId": issue["id"], "target_cycle": str(params.get("target_cycle") or "").strip(), "reason": str(params.get("reason") or "").strip()},
            {"issue": self._issue_summary(issue)},
        )

    def _write_preview(self, capability: GeneratedCapability, plan: BackendInvocationPlan, action: str, body: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
        return {
            "execution_status": "prepared",
            **_metadata(capability, plan),
            "approval_required": True,
            "mutation_performed": False,
            "linear_action": action,
            "linear_metadata": metadata,
            "linear_request": {"operation": action, "input": body},
            "note": "Prepared a Linear GraphQL mutation payload. No Linear mutation was performed.",
        }

    def _team_summary(self, team: dict[str, Any]) -> dict[str, Any]:
        return {"id": team.get("id"), "key": team.get("key"), "name": team.get("name")}

    def _issue_summary(self, issue: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": issue.get("id"),
            "identifier": issue.get("identifier"),
            "title": issue.get("title"),
            "url": issue.get("url"),
            "state": (issue.get("state") or {}).get("name"),
            "team": self._team_summary(issue.get("team") or {}),
        }


backend_adapter = DefaultBackendAdapter()
