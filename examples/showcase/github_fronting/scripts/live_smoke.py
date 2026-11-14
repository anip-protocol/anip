"""Read-only live smoke for the GitHub fronting showcase.

Expected environment:
- GITHUB_TOKEN
- GITHUB_OWNER
- GITHUB_REPO

Run after generating the Python service with the GitHub custom bundle.

The smoke never mutates GitHub: it sets ANIP_GITHUB_ALLOW_MUTATION=false, so
even a granted invocation returns a preview. It authenticates through the
generated service's ANIP_API_KEYS_JSON, which it sets itself: one API key per
actor that the 0.2.0 policy bindings select, an approver, and principals no
binding selects. It checks that:

- each capability succeeds for an actor whose binding allows it;
- an actor whose binding requires approval gets approval_required, and a
  preview after an approver issues a grant through POST /anip/approval_grants;
- a principal without an actor claim, an actor no binding names for the
  capability, a deny binding and a clarify binding are refused.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Any

from fastapi.testclient import TestClient
from github_governed_fronting_showcase.app import create_app
from github_governed_fronting_showcase.runtime_target import (
    GENERATED_CAPABILITY_METADATA,
)

# API key -> ANIP principal. The actor_id claims are the actors the 0.2.0
# runtime policy bindings select. Approval authority comes from the approver
# token's approver:<capability> scope, not from a binding.
SMOKE_KEYS = {
    "smoke-release-notes-drafter": "human:live-github-smoke|actor_id=release_notes_drafter",
    "smoke-repository-operator": "human:live-github-smoke|actor_id=repository_operator",
    "smoke-issue-requester": "human:live-github-smoke|actor_id=issue_requester",
    "smoke-pr-comment-requester": "human:live-github-smoke|actor_id=pr_comment_requester",
    "smoke-workflow-requester": "human:live-github-smoke|actor_id=workflow_requester",
    "smoke-approver": "human:live-github-approver|actor_id=github_change_approver",
    "smoke-no-actor": "human:live-github-smoke",
    "smoke-unknown-actor": "human:live-github-smoke|actor_id=github_unknown_actor",
}
APPROVER_KEY = "smoke-approver"
NO_BINDING_DETAIL = "No runtime policy binding matches the current actor for this capability."


def github_request(path: str) -> Any:
    token = os.environ["GITHUB_TOKEN"]
    request = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "anip-github-fronting-showcase",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode())


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
                "subject": "agent:live-github-smoke",
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
    owner = os.environ["GITHUB_OWNER"]
    repo = os.environ["GITHUB_REPO"]
    os.environ.setdefault("ANIP_GITHUB_ALLOWED_REPOS", f"{owner}/{repo}")
    os.environ["ANIP_GITHUB_ALLOW_MUTATION"] = "false"
    os.environ["ANIP_API_KEYS_JSON"] = json.dumps(SMOKE_KEYS)
    repo_params = {"owner": owner, "repo": repo}
    repo_path = f"/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}"
    smoke = Smoke(TestClient(create_app()))

    search = {**repo_params, "query": "is:issue", "limit": 5}
    issue = {
        **repo_params,
        "title": "ANIP governed GitHub issue preview",
        "body": "Preview only. This smoke must not create a GitHub issue.",
    }
    release_notes = {**repo_params, "range": "HEAD", "audience": "internal"}
    # (capability, API key, parameters, expected execution_status, expected mutation_performed)
    allowed: list[tuple[str, str, dict[str, Any], str, bool | None]] = [
        ("github.repo.search_context", "smoke-release-notes-drafter", search, "completed", None),
        ("github.issue.prepare", "smoke-release-notes-drafter", issue, "prepared", False),
        ("github.release_notes.prepare", "smoke-repository-operator", release_notes, "completed", False),
    ]
    # Actors whose binding requires approval: (capability, requester API key, parameters).
    gated: list[tuple[str, str, dict[str, Any]]] = [("github.issue.prepare", "smoke-issue-requester", issue)]

    pulls = github_request(f"{repo_path}/pulls?state=all&per_page=1")
    if pulls:
        comment = {
            **repo_params,
            "pull_number": pulls[0]["number"],
            "comment_purpose": "triage_update",
            "context": "Preview only. This smoke must not post a pull request comment.",
        }
        allowed.append(("github.pr.comment.prepare", "smoke-release-notes-drafter", comment, "prepared", False))
        gated.append(("github.pr.comment.prepare", "smoke-pr-comment-requester", comment))

    workflows = github_request(f"{repo_path}/actions/workflows?per_page=1")
    workflow_items = workflows.get("workflows", []) if isinstance(workflows, dict) else []
    if workflow_items:
        dispatch = {
            **repo_params,
            # The capability declares workflow_id as a string; GitHub returns a number.
            "workflow_id": str(workflow_items[0]["id"]),
            "ref": github_request(repo_path).get("default_branch", "main"),
            "inputs": {},
        }
        allowed.append(("github.workflow.dispatch.request", "smoke-release-notes-drafter", dispatch, "prepared", False))
        # workflow_requester has both an approval_required and a clarify
        # binding; approval_required takes precedence.
        gated.append(("github.workflow.dispatch.request", "smoke-workflow-requester", dispatch))

    # (label, capability, API key, parameters, expected failure type, expected detail)
    refused: list[tuple[str, str, str, dict[str, Any], str, str | None]] = [
        ("principal without an actor claim", "github.repo.search_context", "smoke-no-actor", search, "denied", NO_BINDING_DETAIL),
        ("actor no binding names", "github.repo.search_context", "smoke-unknown-actor", search, "denied", NO_BINDING_DETAIL),
        ("actor bound only to other capabilities", "github.issue.prepare", "smoke-pr-comment-requester", issue, "denied", NO_BINDING_DETAIL),
        ("deny binding", "github.repo.search_context", "smoke-repository-operator", search, "denied", None),
        ("clarify binding", "github.release_notes.prepare", "smoke-release-notes-drafter", release_notes, "clarification_required", None),
    ]

    results: list[dict] = []
    for capability_id, key, parameters, status, mutation in allowed:
        result = expect_result(capability_id, smoke.invoke(key, capability_id, parameters), status, mutation)
        results.append({
            "capability_id": capability_id,
            "actor": SMOKE_KEYS[key],
            "execution_status": result.get("execution_status"),
            "mutation_performed": result.get("mutation_performed"),
            "github_action": result.get("github_action"),
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
            "github_action": result.get("github_action"),
        })
    refusals = []
    for label, capability_id, key, parameters, failure_type, detail in refused:
        expect_failure(capability_id, smoke.invoke(key, capability_id, parameters), failure_type, detail)
        refusals.append({"check": label, "capability_id": capability_id, "actor": SMOKE_KEYS[key], "failure": failure_type})

    print(json.dumps({
        "repository": f"{owner}/{repo}",
        "invocations_checked": len(results),
        "results": results,
        "refusals": refusals,
    }, indent=2))


if __name__ == "__main__":
    main()
