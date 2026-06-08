"""Live smoke for the GitHub fronting showcase.

Expected environment:
- GITHUB_TOKEN
- GITHUB_OWNER
- GITHUB_REPO

Run after generating the Python service with the GitHub custom bundle.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

from fastapi.testclient import TestClient

from github_governed_fronting_showcase.app import create_app
from github_governed_fronting_showcase.runtime_target import GENERATED_CAPABILITY_METADATA


def github_request(path: str) -> dict:
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


def issue_token(client: TestClient, capability_id: str) -> str:
    response = client.post(
        "/anip/tokens",
        headers={"Authorization": "Bearer dev-admin-key"},
        json={
            "capability": capability_id,
            "scope": capability_scope(capability_id),
            "subject": "agent:live-github-smoke",
            "purpose_parameters": {"actor_id": "github_fronting_consumer", "source": "live-smoke"},
        },
    )
    response.raise_for_status()
    return response.json()["token"]


def invoke(client: TestClient, capability_id: str, parameters: dict) -> dict:
    token = issue_token(client, capability_id)
    response = client.post(
        f"/anip/invoke/{capability_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": parameters},
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success"):
        raise RuntimeError(payload)
    return payload["result"]


def main() -> None:
    owner = os.environ["GITHUB_OWNER"]
    repo = os.environ["GITHUB_REPO"]
    os.environ.setdefault("ANIP_GITHUB_ALLOWED_REPOS", f"{owner}/{repo}")
    repo_params = {"owner": owner, "repo": repo}
    client = TestClient(create_app())

    cases = {
        "github.repo.search_context": {
            "parameters": {**repo_params, "query": "is:issue", "limit": 5},
            "expected_status": "completed",
            "expect_mutation": None,
        },
        "github.issue.prepare": {
            "parameters": {
                **repo_params,
                "title": "ANIP governed GitHub issue preview",
                "body": "Preview only. This smoke must not create a GitHub issue.",
            },
            "expected_status": "prepared",
            "expect_mutation": False,
        },
        "github.release_notes.prepare": {
            "parameters": {**repo_params, "range": "HEAD", "audience": "internal"},
            "expected_status": "completed",
            "expect_mutation": False,
        },
    }

    pulls = github_request(f"/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}/pulls?state=all&per_page=1")
    if pulls:
        cases["github.pr.comment.prepare"] = {
            "parameters": {
                **repo_params,
                "pull_number": pulls[0]["number"],
                "comment_purpose": "triage_update",
                "context": "Preview only. This smoke must not post a pull request comment.",
            },
            "expected_status": "prepared",
            "expect_mutation": False,
        }

    workflows = github_request(f"/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}/actions/workflows?per_page=1")
    workflow_items = workflows.get("workflows", []) if isinstance(workflows, dict) else []
    if workflow_items:
        cases["github.workflow.dispatch.request"] = {
            "parameters": {
                **repo_params,
                "workflow_id": workflow_items[0]["id"],
                "ref": github_request(f"/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}").get("default_branch", "main"),
                "inputs": {},
            },
            "expected_status": "prepared",
            "expect_mutation": False,
        }

    summary: dict[str, dict] = {}
    for capability_id, case in cases.items():
        result = invoke(client, capability_id, case["parameters"])
        execution_status = result.get("execution_status")
        expected_status = case["expected_status"]
        if execution_status != expected_status:
            raise AssertionError(f"{capability_id}: expected {expected_status}, got {execution_status}: {result}")
        expected_mutation = case["expect_mutation"]
        if expected_mutation is not None and result.get("mutation_performed") is not expected_mutation:
            raise AssertionError(f"{capability_id}: unexpected mutation posture: {result}")
        summary[capability_id] = {
            "execution_status": execution_status,
            "mutation_performed": result.get("mutation_performed"),
            "approval_required": result.get("approval_required"),
            "github_action": result.get("github_action"),
        }

    print(json.dumps({"repository": f"{owner}/{repo}", "capabilities_tested": len(summary), "results": summary}, indent=2))


if __name__ == "__main__":
    main()
