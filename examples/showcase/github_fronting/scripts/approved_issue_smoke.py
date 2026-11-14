"""Approved issue-creation smoke for the GitHub fronting showcase.

This test intentionally creates one GitHub issue. Use only with a disposable
repository and a generated Python service that includes the GitHub custom bundle.

Expected environment:
- GITHUB_TOKEN
- GITHUB_OWNER
- GITHUB_REPO
- ANIP_GITHUB_ALLOW_MUTATION=true

The smoke follows the approval path a client takes. It invokes
github.issue.prepare as issue_requester, the actor whose 0.2.0 binding requires
approval, and expects approval_required. An approver then issues a one-time
grant through POST /anip/approval_grants, and the requester invokes again with
the same parameters and the top-level approval_grant. The GitHub adapter
creates the issue only on that granted invocation.
"""
from __future__ import annotations

import json
import os
import time

from fastapi.testclient import TestClient
from github_governed_fronting_showcase.app import create_app

REQUESTER_KEY = "smoke-issue-requester"
APPROVER_KEY = "smoke-approver"
SMOKE_KEYS = {
    REQUESTER_KEY: "human:live-github-smoke|actor_id=issue_requester",
    # Approval authority comes from the approver token's approver:<capability> scope.
    APPROVER_KEY: "human:live-github-approver|actor_id=github_change_approver",
}
CAPABILITY_ID = "github.issue.prepare"


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def _token(client: TestClient, key: str, scope: list[str]) -> str:
    response = client.post(
        "/anip/tokens",
        headers={"Authorization": f"Bearer {key}"},
        json={"capability": CAPABILITY_ID, "scope": scope, "subject": "agent:live-github-approved-issue"},
    )
    response.raise_for_status()
    return response.json()["token"]


def _invoke(client: TestClient, params: dict, approval_grant: str | None = None) -> dict:
    body: dict = {"parameters": params}
    if approval_grant:
        body["approval_grant"] = approval_grant
    token = _token(client, REQUESTER_KEY, [CAPABILITY_ID])
    return client.post(f"/anip/invoke/{CAPABILITY_ID}", headers={"Authorization": f"Bearer {token}"}, json=body).json()


def main() -> None:
    owner = _require_env("GITHUB_OWNER")
    repo = _require_env("GITHUB_REPO")
    _require_env("GITHUB_TOKEN")
    if os.getenv("ANIP_GITHUB_ALLOW_MUTATION", "").lower() != "true":
        raise RuntimeError("ANIP_GITHUB_ALLOW_MUTATION=true is required for approved issue smoke")
    os.environ.setdefault("ANIP_GITHUB_ALLOWED_REPOS", f"{owner}/{repo}")
    os.environ["ANIP_API_KEYS_JSON"] = json.dumps(SMOKE_KEYS)
    client = TestClient(create_app())

    params = {
        "owner": owner,
        "repo": repo,
        "title": f"ANIP approved GitHub issue through generated service at {int(time.time())}",
        "body": "Created by explicit ANIP GitHub approved-issue smoke.",
    }
    first = _invoke(client, params)
    failure = first.get("failure") or {}
    approval_request_id = (failure.get("approval_required") or {}).get("approval_request_id")
    if first.get("success") is not False or failure.get("type") != "approval_required" or not approval_request_id:
        raise AssertionError(f"expected approval_required with an approval_request_id, got {first}")

    approver_token = _token(client, APPROVER_KEY, [f"approver:{CAPABILITY_ID}"])
    grant = client.post(
        "/anip/approval_grants",
        headers={"Authorization": f"Bearer {approver_token}"},
        json={"approval_request_id": approval_request_id, "grant_type": "one_time"},
    ).json()
    if not grant.get("grant_id"):
        raise AssertionError(f"approval grant was not issued: {grant}")

    sent = _invoke(client, params, approval_grant=grant["grant_id"])
    result = sent.get("result") or {}
    if not sent.get("success") or result.get("execution_status") != "completed" or result.get("mutation_performed") is not True:
        raise AssertionError(f"expected approved issue creation to complete, got {sent}")
    print(
        json.dumps(
            {
                "repository": f"{owner}/{repo}",
                "approval_request_id": approval_request_id,
                "approval_grant_id": grant["grant_id"],
                "created_issue": result.get("created_issue"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
