"""Read-only live smoke for the Notion fronting showcase.

Expected environment:
- NOTION_TOKEN
- NOTION_WORKSPACE_SCOPE
- NOTION_PARENT_PAGE_ID
- NOTION_DATABASE_ID

The smoke never mutates Notion: it sets ANIP_NOTION_ALLOW_MUTATION=false, so
even a granted invocation returns a preview. It authenticates through the
generated service's ANIP_API_KEYS_JSON, which it sets itself: one API key per
actor that the 0.2.0 policy bindings select, and principals no binding
selects. It checks that:

- each capability succeeds for notion_governance_reviewer, whose bindings
  allow everything;
- governed_notion_requester gets approval_required on page creation and page
  updates, and a preview after notion_change_approver issues a grant through
  POST /anip/approval_grants;
- a principal without an actor claim, an actor no binding names, and the
  requester's deny bindings are refused.
"""
from __future__ import annotations

import json
import os
from typing import Any

from fastapi.testclient import TestClient
from notion_governed_fronting_showcase.app import create_app
from notion_governed_fronting_showcase.runtime_target import (
    GENERATED_CAPABILITY_METADATA,
)

# API key -> ANIP principal. The actor_id claims are the actors the 0.2.0
# runtime policy bindings select.
SMOKE_KEYS = {
    "smoke-governance-reviewer": "human:live-notion-smoke|actor_id=notion_governance_reviewer",
    "smoke-requester": "human:live-notion-smoke|actor_id=governed_notion_requester",
    "smoke-change-approver": "human:live-notion-approver|actor_id=notion_change_approver",
    "smoke-no-actor": "human:live-notion-smoke",
    "smoke-unknown-actor": "human:live-notion-smoke|actor_id=notion_unknown_actor",
}
APPROVER_KEY = "smoke-change-approver"
NO_BINDING_DETAIL = "No runtime policy binding matches the current actor for this capability."


def capability_scope(capability_id: str) -> list[str]:
    for capability in GENERATED_CAPABILITY_METADATA:
        if capability.get("capability_id") == capability_id:
            return list(capability.get("minimum_scope") or [capability_id])
    return [capability_id]


class Smoke:
    def __init__(self, client: TestClient) -> None:
        self.client = client

    def token(self, key: str, capability_id: str, scope: list[str] | None = None) -> str:
        response = self.client.post(
            "/anip/tokens",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "capability": capability_id,
                "scope": scope or capability_scope(capability_id),
                "subject": "agent:live-notion-smoke",
                "purpose_parameters": {"source": "live-smoke"},
            },
        )
        response.raise_for_status()
        return response.json()["token"]

    def invoke(self, key: str, capability_id: str, parameters: dict, approval_grant: str | None = None) -> dict:
        body: dict[str, Any] = {"parameters": parameters}
        if approval_grant:
            body["approval_grant"] = approval_grant
        response = self.client.post(
            f"/anip/invoke/{capability_id}",
            headers={"Authorization": f"Bearer {self.token(key, capability_id)}"},
            json=body,
        )
        return response.json()

    def grant(self, token: str, approval_request_id: str) -> dict:
        response = self.client.post(
            "/anip/approval_grants",
            headers={"Authorization": f"Bearer {token}"},
            json={"approval_request_id": approval_request_id, "grant_type": "one_time"},
        )
        return response.json()


def expect_result(capability_id: str, payload: dict, status: str, mutation: bool | None) -> dict:
    if not payload.get("success"):
        raise AssertionError(f"{capability_id}: expected {status}, got failure: {payload}")
    result = payload["result"]
    if result.get("execution_status") != status:
        raise AssertionError(f"{capability_id}: expected {status}, got {result.get('execution_status')}: {result}")
    if mutation is not None and result.get("mutation_performed") is not mutation:
        raise AssertionError(f"{capability_id}: unexpected mutation posture: {result}")
    return result


def expect_failure(capability_id: str, payload: dict, failure_type: str, detail: str | None = None) -> dict:
    failure = payload.get("failure") or {}
    if payload.get("success") is not False or failure.get("type") != failure_type:
        raise AssertionError(f"{capability_id}: expected failure {failure_type}, got {payload}")
    if detail is not None and failure.get("detail") != detail:
        raise AssertionError(f"{capability_id}: expected detail {detail!r}, got {failure.get('detail')!r}")
    return failure


def run_with_approval(smoke: Smoke, key: str, capability_id: str, parameters: dict, check_approver_scope: bool) -> tuple[dict, dict]:
    failure = expect_failure(capability_id, smoke.invoke(key, capability_id, parameters), "approval_required")
    approval_request_id = (failure.get("approval_required") or {}).get("approval_request_id")
    if not approval_request_id:
        raise AssertionError(f"{capability_id}: approval_required carried no approval_request_id: {failure}")
    if check_approver_scope:
        # A token without approver:<capability> scope cannot issue the grant.
        refused = smoke.grant(smoke.token(key, capability_id), approval_request_id)
        expect_failure(capability_id, refused, "approver_not_authorized")
    grant = smoke.grant(smoke.token(APPROVER_KEY, capability_id, scope=[f"approver:{capability_id}"]), approval_request_id)
    grant_id = grant.get("grant_id")
    if not grant_id:
        raise AssertionError(f"{capability_id}: approval grant was not issued: {grant}")
    result = expect_result(capability_id, smoke.invoke(key, capability_id, parameters, approval_grant=grant_id), "prepared", False)
    return result, {"approval_request_id": approval_request_id, "grant_id": grant_id}


def main() -> None:
    workspace_scope = os.environ["NOTION_WORKSPACE_SCOPE"]
    parent_id = os.environ["NOTION_PARENT_PAGE_ID"]
    database_id = os.environ["NOTION_DATABASE_ID"]
    os.environ.setdefault("ANIP_NOTION_ALLOWED_WORKSPACES", workspace_scope)
    os.environ.setdefault("ANIP_NOTION_ALLOWED_PARENTS", parent_id)
    os.environ.setdefault("ANIP_NOTION_ALLOWED_PAGES", parent_id)
    os.environ.setdefault("ANIP_NOTION_ALLOWED_DATABASES", database_id)
    os.environ["ANIP_NOTION_ALLOW_MUTATION"] = "false"
    os.environ["ANIP_API_KEYS_JSON"] = json.dumps(SMOKE_KEYS)
    smoke = Smoke(TestClient(create_app()))

    search = {"workspace_scope": workspace_scope, "query": "ANIP", "limit": 5}
    query = {"database_id": database_id, "limit": 5}
    create = {
        "parent_id": parent_id,
        "title": "ANIP governed Notion page preview",
        "content_summary": "Preview only. This smoke must not create a Notion page.",
    }
    update = {
        "page_id": parent_id,
        "change_summary": "Preview only. This smoke must not update a Notion page.",
        "content_patch": "No update should be applied.",
    }
    comment = {
        "page_id": parent_id,
        "comment_purpose": "smoke-test",
        "context": "Preview only. This smoke must not post a Notion comment.",
    }
    # (capability, API key, parameters, expected execution_status, expected mutation_performed)
    allowed: list[tuple[str, str, dict[str, Any], str, bool | None]] = [
        ("notion.workspace.search_context", "smoke-governance-reviewer", search, "completed", None),
        ("notion.page.create.prepare", "smoke-governance-reviewer", create, "prepared", False),
        ("notion.database.query_context", "smoke-governance-reviewer", query, "completed", None),
        ("notion.page.update.prepare", "smoke-governance-reviewer", update, "prepared", False),
        ("notion.comment.prepare", "smoke-governance-reviewer", comment, "prepared", False),
        ("notion.database.query_context", "smoke-requester", query, "completed", None),
    ]
    # Actors whose binding requires approval: (capability, requester API key, parameters).
    gated: list[tuple[str, str, dict[str, Any]]] = [
        ("notion.page.create.prepare", "smoke-requester", create),
        ("notion.page.update.prepare", "smoke-requester", update),
    ]
    # (label, capability, API key, parameters, expected failure type, expected detail)
    refused: list[tuple[str, str, str, dict[str, Any], str, str | None]] = [
        ("principal without an actor claim", "notion.database.query_context", "smoke-no-actor", query, "denied", NO_BINDING_DETAIL),
        ("actor no binding names", "notion.database.query_context", "smoke-unknown-actor", query, "denied", NO_BINDING_DETAIL),
        ("deny binding over approval", "notion.comment.prepare", "smoke-requester", comment, "denied", None),
        ("deny binding over clarify", "notion.workspace.search_context", "smoke-requester", search, "denied", None),
    ]

    results: list[dict] = []
    for capability_id, key, parameters, status, mutation in allowed:
        result = expect_result(capability_id, smoke.invoke(key, capability_id, parameters), status, mutation)
        results.append({
            "capability_id": capability_id,
            "actor": SMOKE_KEYS[key],
            "execution_status": result.get("execution_status"),
            "mutation_performed": result.get("mutation_performed"),
            "notion_action": result.get("notion_action"),
        })
    for index, (capability_id, key, parameters) in enumerate(gated):
        result, approval = run_with_approval(smoke, key, capability_id, parameters, check_approver_scope=index == 0)
        results.append({
            "capability_id": capability_id,
            "actor": SMOKE_KEYS[key],
            "first_attempt": "approval_required",
            **approval,
            "execution_status": result.get("execution_status"),
            "mutation_performed": result.get("mutation_performed"),
            "notion_action": result.get("notion_action"),
        })
    refusals = []
    for label, capability_id, key, parameters, failure_type, detail in refused:
        expect_failure(capability_id, smoke.invoke(key, capability_id, parameters), failure_type, detail)
        refusals.append({"check": label, "capability_id": capability_id, "actor": SMOKE_KEYS[key], "failure": failure_type})

    print(json.dumps({
        "workspace_scope": workspace_scope,
        "invocations_checked": len(results),
        "results": results,
        "refusals": refusals,
    }, indent=2))


if __name__ == "__main__":
    main()
